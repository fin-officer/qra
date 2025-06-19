#!/usr/bin/env python3
"""
Cross-Platform MHTML+JSON Search Tool
=====================================
Fast, SQL-like querying for MHTML files containing JSON data.
Works on Windows, Linux, macOS with any filesystem.

Usage:
    mhtml-search --scan /path/to/search --query "SELECT * FROM data WHERE name LIKE '%John%'"
    mhtml-search --index --path /data
    mhtml-search --sql "SELECT file_path, json_data FROM mhtml_index WHERE age > 25"
"""

import os
import sys
import json
import email
import sqlite3
import argparse
import threading
import mimetypes
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Dict, Any, Generator, Optional
import tempfile
import re
import time
from datetime import datetime

# Try to import optional dependencies
try:
    import duckdb

    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False

try:
    from tqdm import tqdm

    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


@dataclass
class SearchResult:
    file_path: str
    json_data: List[Dict[str, Any]]
    file_size: int
    modified_time: float


class PlatformFileScanner:
    """Cross-platform file scanner optimized for different filesystems"""

    def __init__(self, max_workers: int = None):
        if max_workers is None:
            # Auto-detect optimal thread count based on storage type
            max_workers = self._detect_optimal_threads()
        self.max_workers = max_workers
        self.stats = {
            'files_found': 0,
            'files_processed': 0,
            'errors': 0,
            'start_time': None
        }

    def _detect_optimal_threads(self) -> int:
        """Detect optimal thread count based on CPU and storage"""
        cpu_count = os.cpu_count() or 4

        # Check if we're on SSD (heuristic approach)
        if sys.platform == "win32":
            # Windows - try to detect SSD via PowerShell
            try:
                result = subprocess.run([
                    "powershell", "-Command",
                    "Get-PhysicalDisk | Select-Object MediaType"
                ], capture_output=True, text=True, timeout=5)
                if "SSD" in result.stdout:
                    return min(64, cpu_count * 8)  # SSD can handle more threads
            except:
                pass
        else:
            # Linux/macOS - check for SSD indicators
            try:
                # Check if main storage is SSD
                result = subprocess.run([
                    "lsblk", "-d", "-o", "name,rota"
                ], capture_output=True, text=True, timeout=5)
                if "0" in result.stdout:  # rota=0 means SSD
                    return min(64, cpu_count * 8)
            except:
                pass

        # Default to conservative thread count for HDD
        return min(8, cpu_count * 2)

    def find_mhtml_files(self, search_paths: List[str]) -> Generator[str, None, None]:
        """Find all MHTML files in given paths using platform-optimized methods"""
        self.stats['start_time'] = time.time()

        for search_path in search_paths:
            search_path = Path(search_path).resolve()

            if sys.platform == "win32":
                yield from self._scan_windows(search_path)
            else:
                yield from self._scan_unix(search_path)

    def _scan_windows(self, path: Path) -> Generator[str, None, None]:
        """Windows-optimized file scanning"""
        try:
            # Use dir command for fast scanning on Windows
            cmd = f'dir /s /b "{path}\\*.mhtml" "{path}\\*.mht"'
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                encoding='utf-8', errors='ignore'
            )

            for line in result.stdout.strip().split('\n'):
                if line and os.path.isfile(line):
                    self.stats['files_found'] += 1
                    yield line

        except Exception as e:
            print(f"Error scanning Windows path {path}: {e}")
            # Fallback to Python scanning
            yield from self._scan_python(path)

    def _scan_unix(self, path: Path) -> Generator[str, None, None]:
        """Unix-optimized file scanning using find command"""
        try:
            # Use find command for fast scanning on Unix systems
            cmd = [
                'find', str(path), '-type', 'f',
                '(', '-name', '*.mhtml', '-o', '-name', '*.mht', ')',
                '2>/dev/null'
            ]

            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, text=True,
                bufsize=8192
            )

            for line in process.stdout:
                file_path = line.strip()
                if file_path and os.path.isfile(file_path):
                    self.stats['files_found'] += 1
                    yield file_path

        except Exception as e:
            print(f"Error scanning Unix path {path}: {e}")
            # Fallback to Python scanning
            yield from self._scan_python(path)

    def _scan_python(self, path: Path) -> Generator[str, None, None]:
        """Pure Python fallback scanner"""
        try:
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file.lower().endswith(('.mhtml', '.mht')):
                        full_path = os.path.join(root, file)
                        self.stats['files_found'] += 1
                        yield full_path
        except Exception as e:
            print(f"Error in Python scan: {e}")


class MHTMLParser:
    """Fast MHTML parser with JSON extraction"""

    @staticmethod
    def extract_json_from_mhtml(file_path: str) -> List[Dict[str, Any]]:
        """Extract JSON data from MHTML file"""
        json_objects = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                msg = email.message_from_file(f)

            # Process all parts of MHTML
            for part in msg.walk():
                if part.get_content_type() in ['text/html', 'text/plain', 'application/json']:
                    content = part.get_payload(decode=True)
                    if content:
                        try:
                            content_str = content.decode('utf-8', errors='ignore')
                            json_objects.extend(MHTMLParser._extract_json_from_content(content_str))
                        except Exception:
                            continue

        except Exception as e:
            print(f"Error parsing MHTML {file_path}: {e}")

        return json_objects

    @staticmethod
    def _extract_json_from_content(content: str) -> List[Dict[str, Any]]:
        """Extract JSON objects from content string"""
        json_objects = []

        # Pattern 1: Look for JSON in script tags
        script_pattern = r'<script[^>]*>(.*?)</script>'
        for match in re.finditer(script_pattern, content, re.DOTALL | re.IGNORECASE):
            script_content = match.group(1)
            json_objects.extend(MHTMLParser._find_json_in_text(script_content))

        # Pattern 2: Look for data-* attributes
        data_pattern = r'data-[^=]*="({.*?})"'
        for match in re.finditer(data_pattern, content):
            try:
                json_obj = json.loads(match.group(1))
                json_objects.append(json_obj)
            except:
                continue

        # Pattern 3: Look for standalone JSON objects
        json_objects.extend(MHTMLParser._find_json_in_text(content))

        return json_objects

    @staticmethod
    def _find_json_in_text(text: str) -> List[Dict[str, Any]]:
        """Find JSON objects in text using regex"""
        json_objects = []

        # Look for JSON object patterns
        json_pattern = r'({[^{}]*(?:{[^{}]*}[^{}]*)*})'

        for match in re.finditer(json_pattern, text):
            try:
                json_str = match.group(1)
                # Basic validation - must contain at least one key-value pair
                if ':' in json_str and ('"' in json_str or "'" in json_str):
                    json_obj = json.loads(json_str)
                    if isinstance(json_obj, dict) and json_obj:
                        json_objects.append(json_obj)
            except:
                continue

        return json_objects


class SQLiteIndex:
    """SQLite-based index for fast searching"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(tempfile.gettempdir(), 'mhtml_search.db')

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.lock = threading.Lock()
        self._initialize_db()

    def _initialize_db(self):
        """Initialize database schema"""
        with self.lock:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS mhtml_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_size INTEGER,
                    modified_time REAL,
                    indexed_time REAL,
                    json_count INTEGER
                );

                CREATE TABLE IF NOT EXISTS json_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER,
                    json_text TEXT,
                    json_hash TEXT,
                    FOREIGN KEY (file_id) REFERENCES mhtml_files (id)
                );

                CREATE INDEX IF NOT EXISTS idx_file_path ON mhtml_files(file_path);
                CREATE INDEX IF NOT EXISTS idx_json_hash ON json_data(json_hash);
                CREATE INDEX IF NOT EXISTS idx_file_id ON json_data(file_id);

                -- Virtual table for full-text search
                CREATE VIRTUAL TABLE IF NOT EXISTS json_fts USING fts5(
                    json_content, file_path, content='json_data', content_rowid='id'
                );
            """)
            self.conn.commit()

    def add_file(self, file_path: str, json_objects: List[Dict[str, Any]]):
        """Add file and its JSON data to index"""
        try:
            stat = os.stat(file_path)
            file_size = stat.st_size
            modified_time = stat.st_mtime
            indexed_time = time.time()

            with self.lock:
                # Insert or update file record
                cursor = self.conn.execute("""
                    INSERT OR REPLACE INTO mhtml_files 
                    (file_path, file_size, modified_time, indexed_time, json_count)
                    VALUES (?, ?, ?, ?, ?)
                """, (file_path, file_size, modified_time, indexed_time, len(json_objects)))

                file_id = cursor.lastrowid

                # Clear old JSON data
                self.conn.execute("DELETE FROM json_data WHERE file_id = ?", (file_id,))

                # Insert JSON objects
                for json_obj in json_objects:
                    json_text = json.dumps(json_obj, ensure_ascii=False)
                    json_hash = str(hash(json_text))

                    self.conn.execute("""
                        INSERT INTO json_data (file_id, json_text, json_hash)
                        VALUES (?, ?, ?)
                    """, (file_id, json_text, json_hash))

                self.conn.commit()

        except Exception as e:
            print(f"Error indexing file {file_path}: {e}")

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Execute search query"""
        try:
            with self.lock:
                if query.upper().startswith('SELECT'):
                    # Direct SQL query
                    cursor = self.conn.execute(query)
                else:
                    # Full-text search
                    cursor = self.conn.execute("""
                        SELECT f.file_path, j.json_text
                        FROM json_fts 
                        JOIN json_data j ON json_fts.rowid = j.id
                        JOIN mhtml_files f ON j.file_id = f.id
                        WHERE json_fts MATCH ?
                    """, (query,))

                results = []
                for row in cursor.fetchall():
                    if len(row) >= 2:
                        results.append({
                            'file_path': row[0],
                            'json_data': row[1] if isinstance(row[1], str) else str(row[1])
                        })
                    else:
                        results.append(dict(zip([desc[0] for desc in cursor.description], row)))

                return results

        except Exception as e:
            print(f"Search error: {e}")
            return []


class DuckDBQueryEngine:
    """DuckDB-based query engine for advanced SQL operations"""

    def __init__(self):
        if not HAS_DUCKDB:
            raise ImportError("DuckDB not available. Install with: pip install duckdb")

        self.conn = duckdb.connect(':memory:')
        # Install JSON extension
        try:
            self.conn.execute("INSTALL json")
            self.conn.execute("LOAD json")
        except:
            pass

    def create_temp_table(self, search_results: List[SearchResult], table_name: str = 'mhtml_data'):
        """Create temporary table from search results"""
        # Prepare data for DuckDB
        rows = []
        for result in search_results:
            for json_obj in result.json_data:
                rows.append({
                    'file_path': result.file_path,
                    'file_size': result.file_size,
                    'modified_time': result.modified_time,
                    'json_data': json.dumps(json_obj)
                })

        if rows:
            # Create table from Python data
            self.conn.execute(f"""
                CREATE OR REPLACE TABLE {table_name} AS 
                SELECT * FROM (VALUES {','.join(['(?,?,?,?)'] * len(rows))})
                AS t(file_path, file_size, modified_time, json_data)
            """, [item for row in rows for item in
                  [row['file_path'], row['file_size'], row['modified_time'], row['json_data']]])

    def query(self, sql: str) -> List[Dict[str, Any]]:
        """Execute SQL query and return results"""
        try:
            result = self.conn.execute(sql).fetchall()
            columns = [desc[0] for desc in self.conn.description]
            return [dict(zip(columns, row)) for row in result]
        except Exception as e:
            print(f"DuckDB query error: {e}")
            return []


class MHTMLSearchTool:
    """Main search tool orchestrator"""

    def __init__(self, index_path: str = None, max_workers: int = None):
        self.scanner = PlatformFileScanner(max_workers)
        self.parser = MHTMLParser()
        self.index = SQLiteIndex(index_path)
        self.duckdb = None

        if HAS_DUCKDB:
            try:
                self.duckdb = DuckDBQueryEngine()
            except ImportError:
                pass

    def index_files(self, search_paths: List[str], show_progress: bool = True):
        """Index MHTML files from given paths"""
        print(f"🔍 Scanning for MHTML files in: {', '.join(search_paths)}")

        files = list(self.scanner.find_mhtml_files(search_paths))

        if not files:
            print("❌ No MHTML files found!")
            return

        print(f"📁 Found {len(files)} MHTML files")
        print(f"🔧 Processing with {self.scanner.max_workers} threads...")

        # Progress bar setup
        progress = None
        if HAS_TQDM and show_progress:
            progress = tqdm(total=len(files), desc="Indexing", unit="files")

        def process_file(file_path: str) -> bool:
            try:
                json_objects = self.parser.extract_json_from_mhtml(file_path)
                self.index.add_file(file_path, json_objects)
                self.scanner.stats['files_processed'] += 1

                if progress:
                    progress.update(1)
                    progress.set_postfix({
                        'JSON objects': len(json_objects),
                        'Current': os.path.basename(file_path)[:30]
                    })

                return True

            except Exception as e:
                self.scanner.stats['errors'] += 1
                if not HAS_TQDM:
                    print(f"❌ Error processing {file_path}: {e}")
                return False

        # Process files in parallel
        with ThreadPoolExecutor(max_workers=self.scanner.max_workers) as executor:
            futures = [executor.submit(process_file, file_path) for file_path in files]

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.scanner.stats['errors'] += 1

        if progress:
            progress.close()

        # Print statistics
        elapsed = time.time() - self.scanner.stats['start_time']
        print(f"\n✅ Indexing complete!")
        print(f"📊 Statistics:")
        print(f"   • Files processed: {self.scanner.stats['files_processed']}/{len(files)}")
        print(f"   • Errors: {self.scanner.stats['errors']}")
        print(f"   • Time elapsed: {elapsed:.2f}s")
        print(f"   • Processing rate: {self.scanner.stats['files_processed'] / elapsed:.1f} files/sec")

    def search(self, query: str, use_duckdb: bool = False) -> List[Dict[str, Any]]:
        """Search indexed data"""
        if use_duckdb and self.duckdb:
            # Advanced SQL with DuckDB
            print("🦆 Using DuckDB for advanced SQL queries...")
            # First get base data from SQLite
            base_results = self.index.search(
                "SELECT f.file_path, f.file_size, f.modified_time, j.json_text FROM mhtml_files f JOIN json_data j ON f.id = j.file_id")

            # Convert to SearchResult objects
            search_results = []
            current_file = None
            current_json = []

            for row in base_results:
                if current_file != row['file_path']:
                    if current_file:
                        stat = os.stat(current_file)
                        search_results.append(SearchResult(
                            file_path=current_file,
                            json_data=current_json,
                            file_size=stat.st_size,
                            modified_time=stat.st_mtime
                        ))
                    current_file = row['file_path']
                    current_json = []

                try:
                    json_obj = json.loads(row['json_data']) if isinstance(row['json_data'], str) else row['json_data']
                    current_json.append(json_obj)
                except:
                    pass

            # Add last file
            if current_file:
                stat = os.stat(current_file)
                search_results.append(SearchResult(
                    file_path=current_file,
                    json_data=current_json,
                    file_size=stat.st_size,
                    modified_time=stat.st_mtime
                ))

            # Create DuckDB table and query
            self.duckdb.create_temp_table(search_results)
            return self.duckdb.query(query)
        else:
            # Use SQLite
            return self.index.search(query)

    def quick_scan_and_search(self, search_paths: List[str], query: str) -> List[Dict[str, Any]]:
        """Quick scan and search without persistent indexing"""
        print(f"🚀 Quick scan mode - searching: {', '.join(search_paths)}")

        files = list(self.scanner.find_mhtml_files(search_paths))

        if not files:
            print("❌ No MHTML files found!")
            return []

        print(f"📁 Found {len(files)} MHTML files")

        results = []

        # Progress bar setup
        progress = None
        if HAS_TQDM:
            progress = tqdm(total=len(files), desc="Searching", unit="files")

        def process_file(file_path: str) -> Optional[SearchResult]:
            try:
                json_objects = self.parser.extract_json_from_mhtml(file_path)

                if progress:
                    progress.update(1)
                    progress.set_postfix({
                        'JSON found': len(json_objects),
                        'Current': os.path.basename(file_path)[:30]
                    })

                if json_objects:
                    stat = os.stat(file_path)
                    return SearchResult(
                        file_path=file_path,
                        json_data=json_objects,
                        file_size=stat.st_size,
                        modified_time=stat.st_mtime
                    )
                return None

            except Exception as e:
                return None

        # Process files and collect results
        with ThreadPoolExecutor(max_workers=self.scanner.max_workers) as executor:
            futures = [executor.submit(process_file, file_path) for file_path in files]

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception:
                    pass

        if progress:
            progress.close()

        print(f"📊 Found JSON data in {len(results)} files")

        # If we have DuckDB, use it for querying
        if self.duckdb and results:
            self.duckdb.create_temp_table(results)
            return self.duckdb.query(query)
        else:
            # Simple filtering for quick mode
            filtered_results = []
            query_lower = query.lower()

            for result in results:
                for json_obj in result.json_data:
                    json_str = json.dumps(json_obj).lower()
                    if query_lower in json_str:
                        filtered_results.append({
                            'file_path': result.file_path,
                            'json_data': json.dumps(json_obj),
                            'file_size': result.file_size
                        })

            return filtered_results


def main():
    parser = argparse.ArgumentParser(
        description="Cross-Platform MHTML+JSON Search Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Index files in directory
  mhtml-search --index --path /data --path ~/documents

  # Quick search without indexing
  mhtml-search --scan /data --query "name"

  # SQL query on indexed data
  mhtml-search --sql "SELECT file_path, json_data FROM mhtml_files WHERE json_data LIKE '%John%'"

  # Advanced DuckDB query
  mhtml-search --sql "SELECT file_path, COUNT(*) as json_count FROM mhtml_data GROUP BY file_path" --duckdb
        """
    )

    # Action arguments
    parser.add_argument('--index', action='store_true',
                        help='Index MHTML files for persistent searching')
    parser.add_argument('--scan', metavar='PATH',
                        help='Quick scan and search without indexing')
    parser.add_argument('--sql', metavar='QUERY',
                        help='Execute SQL query on indexed data')

    # Path arguments
    parser.add_argument('--path', action='append', dest='paths',
                        help='Path to search (can be used multiple times)')
    parser.add_argument('--query', metavar='QUERY',
                        help='Search query for quick scan mode')

    # Options
    parser.add_argument('--index-db', metavar='PATH',
                        help='Path to index database file')
    parser.add_argument('--threads', type=int,
                        help='Number of worker threads (auto-detected by default)')
    parser.add_argument('--duckdb', action='store_true',
                        help='Use DuckDB for advanced SQL queries')
    parser.add_argument('--output', choices=['json', 'table', 'csv'],
                        default='table', help='Output format')
    parser.add_argument('--limit', type=int, default=100,
                        help='Limit number of results (default: 100)')

    args = parser.parse_args()

    # Validate arguments
    if not any([args.index, args.scan, args.sql]):
        parser.error("Must specify one of --index, --scan, or --sql")

    if args.index and not args.paths:
        parser.error("--index requires --path")

    if args.scan and not args.query:
        parser.error("--scan requires --query")

    # Initialize tool
    try:
        tool = MHTMLSearchTool(args.index_db, args.threads)
    except Exception as e:
        print(f"❌ Failed to initialize tool: {e}")
        sys.exit(1)

    # Execute action
    try:
        if args.index:
            tool.index_files(args.paths)

        elif args.scan:
            results = tool.quick_scan_and_search([args.scan], args.query)
            print_results(results, args.output, args.limit)

        elif args.sql:
            results = tool.search(args.sql, args.duckdb)
            print_results(results, args.output, args.limit)

    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def print_results(results: List[Dict[str, Any]], output_format: str, limit: int):
    """Print search results in specified format"""
    if not results:
        print("🔍 No results found")
        return

    # Limit results
    if len(results) > limit:
        results = results[:limit]
        print(f"📊 Showing first {limit} of {len(results)} results")

    if output_format == 'json':
        print(json.dumps(results, indent=2, ensure_ascii=False))

    elif output_format == 'csv':
        if results:
            import csv
            import io

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
            print(output.getvalue())

    else:  # table format
        if results:
            # Simple table formatting
            headers = list(results[0].keys())

            # Calculate column widths
            widths = {}
            for header in headers:
                widths[header] = max(len(header),
                                     max(len(str(row.get(header, ''))) for row in results[:10]))
                widths[header] = min(widths[header], 80)  # Max width

            # Print header
            header_line = " | ".join(h.ljust(widths[h]) for h in headers)
            print(header_line)
            print("-" * len(header_line))

            # Print rows
            for row in results:
                row_line = " | ".join(
                    str(row.get(h, ''))[:widths[h]].ljust(widths[h])
                    for h in headers
                )
                print(row_line)


if __name__ == "__main__":
    main()