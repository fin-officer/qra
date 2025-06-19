import email
import base64
import json
import os
import shutil
import re
import glob
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
import markdown
from bs4 import BeautifulSoup


class MHTMLProcessor:
    def __init__(self, filepath=None):
        self.filepath = filepath
        self.qra_dir = Path('.qra')
        self.components = {}

    def extract_to_qra_folder(self):
        """Rozpakuj plik MHTML do folderu .qra/"""
        if not self.filepath or not os.path.exists(self.filepath):
            raise FileNotFoundError(f"Plik {self.filepath} nie istnieje")

        # Usuń poprzedni folder .qra i utwórz nowy
        if self.qra_dir.exists():
            shutil.rmtree(self.qra_dir)
        self.qra_dir.mkdir(exist_ok=True)

        # Parsuj MHTML
        with open(self.filepath, 'rb') as f:
            msg = email.message_from_bytes(f.read())

        file_counter = 0

        def extract_parts(part, prefix=""):
            nonlocal file_counter

            if part.is_multipart():
                for i, subpart in enumerate(part.get_payload()):
                    extract_parts(subpart, f"{prefix}part_{i}_")
            else:
                content_type = part.get_content_type()
                content_location = part.get('Content-Location', '')

                # Dekoduj zawartość
                try:
                    if part.get('Content-Transfer-Encoding') == 'base64':
                        if content_type.startswith('text/'):
                            content = base64.b64decode(part.get_payload()).decode('utf-8', errors='ignore')
                        else:
                            content = part.get_payload()
                    elif part.get('Content-Transfer-Encoding') == 'quoted-printable':
                        content = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    else:
                        content = part.get_payload()
                except:
                    content = part.get_payload()

                # Określ nazwę pliku
                if content_location:
                    filename = os.path.basename(content_location)
                    if not filename or filename == '/':
                        filename = f"{prefix}file_{file_counter}"
                else:
                    filename = f"{prefix}file_{file_counter}"

                # Dodaj rozszerzenie na podstawie typu MIME
                if not '.' in filename:
                    ext_map = {
                        'text/html': '.html',
                        'text/css': '.css',
                        'text/javascript': '.js',
                        'application/javascript': '.js',
                        'image/jpeg': '.jpg',
                        'image/png': '.png',
                        'image/gif': '.gif',
                        'image/svg+xml': '.svg'
                    }
                    filename += ext_map.get(content_type, '.txt')

                file_path = self.qra_dir / filename

                # Zapisz plik
                if content_type.startswith('text/') or content_type in ['application/javascript']:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                else:
                    # Dla plików binarnych
                    if isinstance(content, str) and part.get('Content-Transfer-Encoding') == 'base64':
                        with open(file_path, 'wb') as f:
                            f.write(base64.b64decode(content))
                    else:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(str(content))

                # Zapisz metadane
                self.components[str(file_path)] = {
                    'content_type': content_type,
                    'content_location': content_location,
                    'encoding': part.get('Content-Transfer-Encoding', ''),
                    'original_name': filename
                }

                file_counter += 1

        extract_parts(msg)

        # Zapisz metadane do pliku JSON
        with open(self.qra_dir / 'metadata.json', 'w', encoding='utf-8') as f:
            json.dump(self.components, f, indent=2, ensure_ascii=False)

        return len(self.components)

    def pack_from_qra_folder(self):
        """Spakuj pliki z folderu .qra/ z powrotem do MHTML"""
        if not self.qra_dir.exists():
            raise FileNotFoundError("Folder .qra/ nie istnieje")

        # Wczytaj metadane
        metadata_file = self.qra_dir / 'metadata.json'
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        else:
            metadata = {}

        # Utwórz nową wiadomość MHTML
        msg = MIMEMultipart('related')
        msg['Subject'] = 'QRA Edited MHTML'
        msg['MIME-Version'] = '1.0'

        # Przejdź przez wszystkie pliki w .qra/
        for file_path in self.qra_dir.glob('*'):
            if file_path.name == 'metadata.json':
                continue

            file_key = str(file_path)
            file_metadata = metadata.get(file_key, {})

            content_type = file_metadata.get('content_type', 'text/plain')
            content_location = file_metadata.get('content_location', '')

            # Wczytaj zawartość pliku
            if content_type.startswith('text/') or content_type in ['application/javascript']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Utwórz część MIME
                if content_type == 'text/html':
                    part = MIMEText(content, 'html', 'utf-8')
                elif content_type == 'text/css':
                    part = MIMEText(content, 'css', 'utf-8')
                else:
                    part = MIMEText(content, 'plain', 'utf-8')
                    part['Content-Type'] = content_type
            else:
                # Pliki binarne
                with open(file_path, 'rb') as f:
                    content = f.read()

                part = MIMEBase('application', 'octet-stream')
                part.set_payload(base64.b64encode(content).decode())
                part['Content-Transfer-Encoding'] = 'base64'
                part['Content-Type'] = content_type

            if content_location:
                part['Content-Location'] = content_location

            msg.attach(part)

        # Zapisz do oryginalnego pliku
        if self.filepath:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                f.write(msg.as_string())

    def get_qra_files(self):
        """Pobierz listę plików z folderu .qra/"""
        if not self.qra_dir.exists():
            return []

        files = []
        for file_path in self.qra_dir.glob('*'):
            if file_path.name == 'metadata.json':
                continue

            # Określ typ pliku na podstawie rozszerzenia
            ext = file_path.suffix.lower()
            file_type = {
                '.html': 'html',
                '.css': 'css',
                '.js': 'javascript',
                '.json': 'json',
                '.xml': 'xml',
                '.svg': 'xml'
            }.get(ext, 'text')

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            files.append({
                'name': file_path.name,
                'path': str(file_path),
                'type': file_type,
                'content': content,
                'size': file_path.stat().st_size
            })

        return sorted(files, key=lambda x: x['name'])

    def save_file_content(self, filename, content):
        """Zapisz zawartość pliku w folderze .qra/"""
        file_path = self.qra_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def create_empty_mhtml(self, filepath):
        """Utwórz pusty plik MHTML"""
        msg = MIMEMultipart('related')
        msg['Subject'] = 'New MHTML Document'
        msg['MIME-Version'] = '1.0'

        # Dodaj podstawowy HTML
        html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>New Document</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; }
    </style>
</head>
<body>
    <h1>New Document</h1>
    <p>Start editing this document...</p>
</body>
</html>'''

        html_part = MIMEText(html_content, 'html', 'utf-8')
        html_part['Content-Location'] = 'index.html'
        msg.attach(html_part)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(msg.as_string())

        self.filepath = filepath

    def markdown_to_mhtml(self, md_file, mhtml_file):
        """Konwertuj Markdown do MHTML"""
        with open(md_file, 'r', encoding='utf-8') as f:
            md_content = f.read()

        # Konwertuj Markdown do HTML
        html_content = markdown.markdown(md_content, extensions=['extra', 'codehilite'])

        # Dodaj podstawowy CSS
        css_content = '''
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
               max-width: 800px; margin: 40px auto; line-height: 1.6; color: #333; }
        pre { background: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto; }
        code { background: #f5f5f5; padding: 2px 4px; border-radius: 3px; }
        blockquote { border-left: 4px solid #ddd; margin: 0; padding-left: 20px; color: #666; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        '''

        # Utwórz kompletny HTML
        full_html = f'''<!DOCTYPE html>
<html>
<head>
    <title>{os.path.basename(md_file)}</title>
    <style>{css_content}</style>
</head>
<body>
{html_content}
</body>
</html>'''

        # Utwórz MHTML
        msg = MIMEMultipart('related')
        msg['Subject'] = f'Converted from {md_file}'
        msg['MIME-Version'] = '1.0'

        html_part = MIMEText(full_html, 'html', 'utf-8')
        html_part['Content-Location'] = 'index.html'
        msg.attach(html_part)

        with open(mhtml_file, 'w', encoding='utf-8') as f:
            f.write(msg.as_string())

    def mhtml_to_markdown(self, md_file):
        """Konwertuj MHTML do Markdown"""
        if not self.filepath or not os.path.exists(self.filepath):
            raise FileNotFoundError("Brak pliku MHTML do konwersji")

        # Wyodrębnij HTML z MHTML
        with open(self.filepath, 'rb') as f:
            msg = email.message_from_bytes(f.read())

        html_content = ""
        for part in msg.walk():
            if part.get_content_type() == 'text/html':
                html_content = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                break

        if not html_content:
            raise ValueError("Nie znaleziono HTML w pliku MHTML")

        # Konwertuj HTML do Markdown (podstawowa konwersja)
        soup = BeautifulSoup(html_content, 'html.parser')

        # Usuń style i script
        for tag in soup(['style', 'script']):
            tag.decompose()

        # Podstawowa konwersja do Markdown
        text = soup.get_text()

        # Zapisz do pliku
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(text)

    def search_files(self, keywords, search_path='.'):
        """Wyszukaj pliki MHTML zawierające słowa kluczowe"""
        results = {}

        # Znajdź wszystkie pliki MHTML
        mhtml_files = glob.glob(os.path.join(search_path, '**/*.mhtml'), recursive=True)

        for file_path in mhtml_files:
            try:
                with open(file_path, 'rb') as f:
                    msg = email.message_from_bytes(f.read())

                # Przeszukaj wszystkie części
                matches = []
                for part in msg.walk():
                    if part.get_content_type().startswith('text/'):
                        try:
                            content = part.get_payload(decode=True).decode('utf-8', errors='ignore')

                            # Sprawdź czy wszystkie słowa kluczowe są obecne
                            content_lower = content.lower()
                            if all(keyword.lower() in content_lower for keyword in keywords):
                                # Znajdź kontekst dla każdego słowa kluczowego
                                for keyword in keywords:
                                    pattern = re.compile(f'.{{0,50}}{re.escape(keyword)}.{{0,50}}', re.IGNORECASE)
                                    for match in pattern.finditer(content):
                                        context = match.group().strip()
                                        if context not in matches:
                                            matches.append(context)
                        except:
                            continue

                if matches:
                    results[file_path] = matches

            except Exception:
                continue

        return results