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
        """Rozpakuj plik MHTML/EML do folderu .qra/"""
        if not self.filepath or not os.path.exists(self.filepath):
            raise FileNotFoundError(f"Plik {self.filepath} nie istnieje")

        # Usuń poprzedni folder .qra i utwórz nowy
        if self.qra_dir.exists():
            shutil.rmtree(self.qra_dir)
        self.qra_dir.mkdir(exist_ok=True)

        # Parsuj MHTML/EML
        with open(self.filepath, 'rb') as f:
            try:
                msg = email.message_from_bytes(f.read())
            except Exception as e:
                # Spróbuj jako string jeśli bytes nie działają
                f.seek(0)
                content = f.read().decode('utf-8', errors='ignore')
                msg = email.message_from_string(content)

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
                        content = part.get_payload(decode=True)
                        if isinstance(content, bytes):
                            content = content.decode('utf-8', errors='ignore')
                    else:
                        content = part.get_payload()
                        if isinstance(content, bytes):
                            content = content.decode('utf-8', errors='ignore')
                except Exception as e:
                    content = str(part.get_payload())

                # Określ nazwę pliku
                if content_location:
                    filename = os.path.basename(content_location)
                    if not filename or filename == '/':
                        filename = f"{prefix}file_{file_counter}"
                else:
                    # Dla EML użyj bardziej opisowych nazw
                    if content_type == 'text/html':
                        filename = f"{prefix}email_body.html"
                    elif content_type == 'text/plain':
                        filename = f"{prefix}email_text.txt"
                    else:
                        filename = f"{prefix}file_{file_counter}"

                # Dodaj rozszerzenie na podstawie typu MIME
                if not '.' in filename:
                    ext_map = {
                        'text/html': '.html',
                        'text/css': '.css',
                        'text/javascript': '.js',
                        'application/javascript': '.js',
                        'text/plain': '.txt',
                        'image/jpeg': '.jpg',
                        'image/png': '.png',
                        'image/gif': '.gif',
                        'image/svg+xml': '.svg',
                        'application/pdf': '.pdf',
                        'application/json': '.json',
                        'application/xml': '.xml',
                        'text/xml': '.xml'
                    }
                    filename += ext_map.get(content_type, '.txt')

                file_path = self.qra_dir / filename

                # Zapisz plik
                if content_type.startswith('text/') or content_type in ['application/javascript', 'application/json',
                                                                        'application/xml']:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(str(content))
                else:
                    # Dla plików binarnych
                    if isinstance(content, str) and part.get('Content-Transfer-Encoding') == 'base64':
                        try:
                            with open(file_path, 'wb') as f:
                                f.write(base64.b64decode(content))
                        except:
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(content)
                    else:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(str(content))

                # Zapisz metadane
                self.components[str(file_path)] = {
                    'content_type': content_type,
                    'content_location': content_location,
                    'encoding': part.get('Content-Transfer-Encoding', ''),
                    'original_name': filename,
                    'subject': msg.get('Subject', '') if hasattr(msg, 'get') else '',
                    'from': msg.get('From', '') if hasattr(msg, 'get') else '',
                    'to': msg.get('To', '') if hasattr(msg, 'get') else '',
                    'date': msg.get('Date', '') if hasattr(msg, 'get') else ''
                }

                file_counter += 1

        # Dla plików EML zapisz nagłówki jako osobny plik
        if self.filepath.lower().endswith('.eml'):
            headers = {
                'Subject': msg.get('Subject', ''),
                'From': msg.get('From', ''),
                'To': msg.get('To', ''),
                'Date': msg.get('Date', ''),
                'Message-ID': msg.get('Message-ID', ''),
                'Content-Type': msg.get('Content-Type', ''),
                'Reply-To': msg.get('Reply-To', ''),
                'CC': msg.get('CC', ''),
                'BCC': msg.get('BCC', '')
            }

            headers_content = "# Email Headers\n\n"
            for key, value in headers.items():
                if value:
                    headers_content += f"**{key}:** {value}\n\n"

            with open(self.qra_dir / 'email_headers.md', 'w', encoding='utf-8') as f:
                f.write(headers_content)

        extract_parts(msg)

        # Zapisz metadane do pliku JSON
        with open(self.qra_dir / 'metadata.json', 'w', encoding='utf-8') as f:
            json.dump(self.components, f, indent=2, ensure_ascii=False)

        return len(self.components)

    def pack_from_qra_folder(self):
        """Spakuj pliki z folderu .qra/ z powrotem do MHTML/EML"""
        if not self.qra_dir.exists():
            raise FileNotFoundError("Folder .qra/ nie istnieje")

        # Wczytaj metadane
        metadata_file = self.qra_dir / 'metadata.json'
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        else:
            metadata = {}

        # Utwórz nową wiadomość
        msg = MIMEMultipart('related')

        # Ustaw nagłówki na podstawie metadanych
        subject = next((meta.get('subject', '') for meta in metadata.values() if meta.get('subject')),
                       'QRA Edited Document')
        msg['Subject'] = subject
        msg['MIME-Version'] = '1.0'

        # Dla EML dodaj dodatkowe nagłówki
        if self.filepath and self.filepath.lower().endswith('.eml'):
            from_addr = next((meta.get('from', '') for meta in metadata.values() if meta.get('from')), '')
            to_addr = next((meta.get('to', '') for meta in metadata.values() if meta.get('to')), '')
            date = next((meta.get('date', '') for meta in metadata.values() if meta.get('date')), '')

            if from_addr:
                msg['From'] = from_addr
            if to_addr:
                msg['To'] = to_addr
            if date:
                msg['Date'] = date

        # Przejdź przez wszystkie pliki w .qra/
        for file_path in self.qra_dir.glob('*'):
            if file_path.name in ['metadata.json', 'email_headers.md']:
                continue

            file_key = str(file_path)
            file_metadata = metadata.get(file_key, {})

            content_type = file_metadata.get('content_type', self._guess_content_type(file_path.name))
            content_location = file_metadata.get('content_location', '')

            # Wczytaj zawartość pliku
            if content_type.startswith('text/') or content_type in ['application/javascript', 'application/json',
                                                                    'application/xml']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Utwórz część MIME
                if content_type == 'text/html':
                    part = MIMEText(content, 'html', 'utf-8')
                elif content_type == 'text/css':
                    part = MIMEText(content, 'css', 'utf-8')
                elif content_type == 'text/plain':
                    part = MIMEText(content, 'plain', 'utf-8')
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

    # Dodaj do qra/core.py

    def export_to_html(self, output_path, inline_assets=True):
        """Eksportuj MHTML do standalone HTML"""
        if not self.qra_dir.exists():
            self.extract_to_qra_folder()

        files = self.get_qra_files()

        # Znajdź główny HTML
        html_file = next((f for f in files if f['type'] == 'html'), None)
        if not html_file:
            raise ValueError("Brak pliku HTML w MHTML")

        html_content = html_file['content']

        if inline_assets:
            # Inline CSS
            for file in files:
                if file['type'] == 'css':
                    css_tag = f'<link rel="stylesheet" href="{file["name"]}">'
                    inline_css = f'<style>\n{file["content"]}\n</style>'
                    html_content = html_content.replace(css_tag, inline_css)

            # Inline JS
            for file in files:
                if file['type'] == 'javascript':
                    js_tag = f'<script src="{file["name"]}"></script>'
                    inline_js = f'<script>\n{file["content"]}\n</script>'
                    html_content = html_content.replace(js_tag, inline_js)

            # Inline images jako base64
            for file in files:
                if file['name'].endswith(('.jpg', '.png', '.gif', '.svg')):
                    # Convert to base64...
                    pass

        # Zapisz jako standalone HTML
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)


    def _guess_content_type(self, filename):
        """Zgadnij typ MIME na podstawie rozszerzenia"""
        ext = os.path.splitext(filename)[1].lower()
        type_map = {
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.txt': 'text/plain',
            '.md': 'text/plain',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.pdf': 'application/pdf'
        }
        return type_map.get(ext, 'text/plain')

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
                '.svg': 'xml',
                '.txt': 'text',
                '.md': 'markdown',
                '.py': 'python',
                '.php': 'php',
                '.sql': 'sql',
                '.yaml': 'yaml',
                '.yml': 'yaml'
            }.get(ext, 'text')

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except:
                content = "[Błąd odczytu pliku binarnego]"

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
        """Wyszukaj pliki MHTML/EML zawierające słowa kluczowe z kontrolą głębokości"""
        results = {}
        search_path = os.path.abspath(search_path)

        if verbose:
            print(f"Rozpoczynanie wyszukiwania w: {search_path}")
            print(f"Maksymalna głębokość: {max_depth}")

        def find_mhtml_files(directory, base_path, current_depth=0):
            """Rekurencyjnie znajdź pliki MHTML/EML z ograniczeniem głębokości"""
            found_files = []

            if current_depth > max_depth:
                return found_files

            try:
                for item in os.listdir(directory):
                    item_path = os.path.join(directory, item)

                    if os.path.isfile(item_path) and item.lower().endswith(('.mhtml', '.eml')):
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

        # Znajdź wszystkie pliki MHTML/EML w określonej głębokości
        mhtml_files = find_mhtml_files(search_path, search_path, 0)

        if verbose:
            print(f"Znaleziono {len(mhtml_files)} plików MHTML/EML do przeszukania")

        # Przeszukaj każdy plik
        for file_path, depth in mhtml_files:
            try:
                file_size = os.path.getsize(file_path)

                with open(file_path, 'rb') as f:
                    try:
                        msg = email.message_from_bytes(f.read())
                    except:
                        f.seek(0)
                        content = f.read().decode('utf-8', errors='ignore')
                        msg = email.message_from_string(content)

                # Przeszukaj wszystkie części
                matches = []
                parts_searched = 0

                for part in msg.walk():
                    if part.get_content_type().startswith('text/'):
                        parts_searched += 1
                        try:
                            content = part.get_payload(decode=True)
                            if content:
                                if isinstance(content, bytes):
                                    content = content.decode('utf-8', errors='ignore')
                            else:
                                content = str(part.get_payload())

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
                        'parts_searched': parts_searched,
                        'type': 'EML' if file_path.lower().endswith('.eml') else 'MHTML'
                    }

                    if verbose:
                        file_type = 'EML' if file_path.lower().endswith('.eml') else 'MHTML'
                        print(
                            f"✓ Dopasowania w: {os.path.relpath(file_path, search_path)} ({file_type}, głębokość: {depth})")

            except Exception as e:
                if verbose:
                    print(f"✗ Błąd przetwarzania {file_path}: {e}")
                continue

    def create_eml_from_template(self, filepath, template='basic'):
        """Utwórz plik EML na podstawie wybranego template"""
        # Dla EML użyj prostego template email
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        import datetime

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'QRA Email - {template.title()}'
        msg['From'] = 'sender@example.com'
        msg['To'] = 'recipient@example.com'
        msg['Date'] = datetime.datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
        msg['Message-ID'] = f'<qra-{int(datetime.datetime.now().timestamp())}@qra-editor>'

        # Treść tekstowa
        text_content = f"""Witaj!

To jest wiadomość email utworzona przez QRA Editor.
Template: {template}

Możesz edytować tę treść w edytorze.

Pozdrawiam,
QRA Editor
"""

        # Treść HTML
        if template == 'basic':
            html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>QRA Email</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .header { background: #f4f4f4; padding: 20px; text-align: center; }
        .content { padding: 20px; }
        .footer { background: #f4f4f4; padding: 10px; text-align: center; font-size: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Email z QRA Editor</h1>
    </div>
    <div class="content">
        <p>Witaj!</p>
        <p>To jest wiadomość email utworzona przez QRA Editor.</p>
        <p>Możesz edytować treść HTML w edytorze.</p>
    </div>
    <div class="footer">
        <p>Wysłane przez QRA Editor</p>
    </div>
</body>
</html>"""
        else:
            # Dla innych templates użyj ich HTML
            template_files = self.template_manager.get_template_files(template)
            html_content = next((f['content'] for f in template_files if f['type'] == 'text/html'),
                                text_content.replace('\n', '<br>'))

        # Dodaj części
        part1 = MIMEText(text_content, 'plain', 'utf-8')
        part2 = MIMEText(html_content, 'html', 'utf-8')

        msg.attach(part1)
        msg.attach(part2)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(msg.as_string())

        self.filepath = filepath

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