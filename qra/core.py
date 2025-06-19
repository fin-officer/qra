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
from .templates import TemplateManager


class MHTMLProcessor:
    def __init__(self, filepath=None):
        self.filepath = filepath
        self.qra_dir = Path('.qra')
        self.components = {}
        self.template_manager = TemplateManager()

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

    def create_mhtml_from_template(self, filepath, template='basic'):
        """Utwórz plik MHTML na podstawie wybranego template"""
        template_files = self.template_manager.get_template_files(template)

        msg = MIMEMultipart('related')
        msg['Subject'] = f'QRA Document - {template.title()}'
        msg['MIME-Version'] = '1.0'

        # Dodaj wszystkie pliki z template
        for file_info in template_files:
            if file_info['type'] == 'text/html':
                part = MIMEText(file_info['content'], 'html', 'utf-8')
            elif file_info['type'] == 'text/css':
                part = MIMEText(file_info['content'], 'css', 'utf-8')
            elif file_info['type'] == 'application/javascript':
                part = MIMEText(file_info['content'], 'javascript', 'utf-8')
            else:
                part = MIMEText(file_info['content'], 'plain', 'utf-8')
                part['Content-Type'] = file_info['type']

            part['Content-Location'] = file_info['filename']
            msg.attach(part)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(msg.as_string())

        self.filepath = filepath

    def create_empty_mhtml(self, filepath):
        """Utwórz pusty plik MHTML (backward compatibility)"""
        self.create_mhtml_from_template(filepath, 'basic')

    def markdown_to_mhtml(self, md_file, mhtml_file):
        """Konwertuj Markdown do MHTML"""
        with open(md_file, 'r', encoding='utf-8') as f:
            md_content = f.read()

        # Konwertuj Markdown do HTML
        html_content = markdown.markdown(md_content, extensions=['extra', 'codehilite'])

        # Użyj template dla Markdown
        template_files = self.template_manager.get_markdown_template(
            title=os.path.basename(md_file),
            content=html_content
        )

        # Utwórz MHTML
        msg = MIMEMultipart('related')
        msg['Subject'] = f'Converted from {md_file}'
        msg['MIME-Version'] = '1.0'

        for file_info in template_files:
            if file_info['type'] == 'text/html':
                part = MIMEText(file_info['content'], 'html', 'utf-8')
            elif file_info['type'] == 'text/css':
                part = MIMEText(file_info['content'], 'css', 'utf-8')

            part['Content-Location'] = file_info['filename']
            msg.attach(part)

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

    def search_files(self, keywords, search_path='.', max_depth=3, verbose=False):
        """Wyszukaj pliki MHTML zawierające słowa kluczowe z kontrolą głębokości"""
        results = {}
        search_path = os.path.abspath(search_path)

        if verbose:
            print(f"Rozpoczynanie wyszukiwania w: {search_path}")
            print(f"Maksymalna głębokość: {max_depth}")

        def find_mhtml_files(directory, base_path, current_depth=0):
            """Rekurencyjnie znajdź pliki MHTML z ograniczeniem głębokości"""
            found_files = []

            if current_depth > max_depth:
                return found_files

            try:
                for item in os.listdir(directory):
                    item_path = os.path.join(directory, item)

                    if os.path.isfile(item_path) and item.lower().endswith('.mhtml'):
                        relative_depth = current_depth
                        found_files.append((item_path, relative_depth))

                    elif os.path.isdir(item_path) and current_depth < max_depth:
                        # Rekurencyjnie przeszukaj podkatalogi
                        if not item.startswith('.'):  # Pomiń ukryte katalogi
                            found_files.extend(
                                find_mhtml_files(item_path, base_path, current_depth + 1)
                            )
            except PermissionError:
                if verbose:
                    print(f"Brak uprawnień do: {directory}")
            except Exception as e:
                if verbose:
                    print(f"Błąd przeszukiwania {directory}: {e}")

            return found_files

        # Znajdź wszystkie pliki MHTML w określonej głębokości
        mhtml_files = find_mhtml_files(search_path, search_path, 0)

        if verbose:
            print(f"Znaleziono {len(mhtml_files)} plików MHTML do przeszukania")

        # Przeszukaj każdy plik
        for file_path, depth in mhtml_files:
            try:
                file_size = os.path.getsize(file_path)

                with open(file_path, 'rb') as f:
                    msg = email.message_from_bytes(f.read())

                # Przeszukaj wszystkie części
                matches = []
                parts_searched = 0

                for part in msg.walk():
                    if part.get_content_type().startswith('text/'):
                        parts_searched += 1
                        try:
                            content = part.get_payload(decode=True)
                            if content:
                                content = content.decode('utf-8', errors='ignore')
                            else:
                                content = part.get_payload()

                            # Sprawdź czy wszystkie słowa kluczowe są obecne
                            content_lower = content.lower()
                            if all(keyword.lower() in content_lower for keyword in keywords):
                                # Znajdź kontekst dla każdego słowa kluczowego
                                for keyword in keywords:
                                    pattern = re.compile(
                                        f'.{{0,50}}{re.escape(keyword)}.{{0,50}}',
                                        re.IGNORECASE | re.DOTALL
                                    )
                                    for match in pattern.finditer(content):
                                        context = ' '.join(match.group().split())  # Usuń nadmierne spacje
                                        if context and context not in matches:
                                            matches.append(context)

                                        # Ogranicz liczbę dopasowań per plik
                                        if len(matches) >= 10:
                                            break

                                    if len(matches) >= 10:
                                        break
                        except Exception as e:
                            if verbose:
                                print(f"Błąd dekodowania części w {file_path}: {e}")
                            continue

                if matches:
                    results[file_path] = {
                        'matches': matches,
                        'depth': depth,
                        'size': file_size,
                        'parts_searched': parts_searched
                    }

                    if verbose:
                        print(f"✓ Dopasowania w: {os.path.relpath(file_path, search_path)} (głębokość: {depth})")

            except Exception as e:
                if verbose:
                    print(f"✗ Błąd przetwarzania {file_path}: {e}")
                continue

        return results