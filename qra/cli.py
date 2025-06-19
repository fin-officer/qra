import os
import webbrowser
import threading
import time
import click
from pathlib import Path
from .core import MHTMLProcessor
from .server import create_app


@click.group()
def main():
    """QRA - MHTML Editor and Processor"""
    pass


@main.command()
@click.argument('filename', required=False)
@click.option('--port', '-p', default=5000, help='Port dla serwera')
@click.option('--host', '-h', default='127.0.0.1', help='Host dla serwera')
@click.option('--template', '-t', default='basic',
              type=click.Choice(['basic', 'portfolio', 'blog', 'docs', 'landing']),
              help='Template dla nowego pliku')
def edit(filename, port, host, template):
    """Otwórz edytor MHTML/EML w przeglądarce

    Jeśli plik nie istnieje, zostanie automatycznie utworzony.
    Obsługuje pliki .mhtml i .eml
    """
    if filename:
        # Sprawdź rozszerzenie i dodaj odpowiednie jeśli brak
        if not any(filename.endswith(ext) for ext in ['.mhtml', '.eml']):
            filename += '.mhtml'

    # Automatycznie utwórz plik jeśli nie istnieje
    if filename and not os.path.exists(filename):
        file_type = "EML" if filename.endswith('.eml') else "MHTML"
        click.echo(f"📄 Plik {filename} nie istnieje - tworzenie nowego pliku {file_type}...")

        processor = MHTMLProcessor()
        if filename.endswith('.eml'):
            processor.create_eml_from_template(filename, template)
        else:
            processor.create_mhtml_from_template(filename, template)

        click.echo(f"✅ Utworzono nowy plik {file_type}: {filename}")
        click.echo(f"📝 Użyty template: {template}")
        click.echo(f"🔧 Rozpakowywanie do folderu .qra/")

    # Uruchom serwer Flask
    app = create_app()

    if filename:
        app.config['CURRENT_FILE'] = os.path.abspath(filename)
        processor = MHTMLProcessor(filename)
        file_count = processor.extract_to_qra_folder()
        click.echo(f"📂 Rozpakowano {file_count} plików do folderu .qra/")

    # Otwórz przeglądarkę po krótkim opóźnieniu
    def open_browser():
        time.sleep(1.5)
        webbrowser.open(f'http://{host}:{port}')

    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()

    click.echo(f"🚀 Uruchamianie edytora na http://{host}:{port}")
    click.echo(f"💡 Użyj Ctrl+C aby zatrzymać serwer")

    try:
        app.run(host=host, port=port, debug=False)
    except KeyboardInterrupt:
        click.echo(f"\n👋 Edytor zatrzymany. Plik {filename} został zapisany.")
    pass


@main.command()
@click.argument('filename')
def create(filename):
    """Utwórz nowy plik MHTML"""
    if not filename.endswith('.mhtml'):
        filename += '.mhtml'

    if os.path.exists(filename):
        if not click.confirm(f"Plik {filename} już istnieje. Nadpisać?"):
            return

    processor = MHTMLProcessor()
    processor.create_empty_mhtml(filename)
    click.echo(f"Utworzono nowy plik MHTML: {filename}")


@main.command()
@click.argument('input_file')
@click.argument('output_file', required=False)
def html(input_file, output_file):
    """Konwertuj Markdown do MHTML"""
    if not input_file.endswith('.md'):
        input_file += '.md'

    if not os.path.exists(input_file):
        click.echo(f"Plik {input_file} nie istnieje")
        return

    if not output_file:
        output_file = input_file.replace('.md', '.mhtml')
    elif not output_file.endswith('.mhtml'):
        output_file += '.mhtml'

    processor = MHTMLProcessor()
    processor.markdown_to_mhtml(input_file, output_file)
    click.echo(f"Skonwertowano {input_file} → {output_file}")


@main.command()
@click.argument('input_file')
@click.argument('output_file', required=False)
def md(input_file, output_file):
    """Konwertuj MHTML do Markdown"""
    if not input_file.endswith('.mhtml'):
        input_file += '.mhtml'

    if not os.path.exists(input_file):
        click.echo(f"Plik {input_file} nie istnieje")
        return

    if not output_file:
        output_file = input_file.replace('.mhtml', '.md')
    elif not output_file.endswith('.md'):
        output_file += '.md'

    processor = MHTMLProcessor(input_file)
    processor.mhtml_to_markdown(output_file)
    click.echo(f"Skonwertowano {input_file} → {output_file}")


@main.command()
@click.argument('query')
@click.option('--path', '-p', default='.', help='Ścieżka do wyszukiwania')
@click.option('--level', '-L', default=3, help='Głębokość przeszukiwania (poziomy w głąb)')
@click.option('--scope', '-S', default=0, help='Poziomy wyżej od bieżącej pozycji')
@click.option('--verbose', '-v', is_flag=True, help='Pokaż więcej szczegółów')
def search(query, path, level, scope, verbose):
    """Wyszukaj pliki MHTML zawierające podane słowa kluczowe

    Przykłady:
      qra search "invoice"+"paypal"
      qra search "test" -L 2 -S 1
      qra search "docs" --path /home/user --level 5
    """
    keywords = [k.strip('"\'') for k in query.split('+')]

    # Oblicz rzeczywistą ścieżkę wyszukiwania na podstawie scope
    search_path = calculate_search_path(path, scope)

    if verbose:
        click.echo(f"Wyszukiwanie słów kluczowych: {', '.join(keywords)}")
        click.echo(f"Ścieżka bazowa: {path}")
        click.echo(f"Ścieżka wyszukiwania: {search_path}")
        click.echo(f"Głębokość: {level} poziomów")
        click.echo(f"Scope: {scope} poziomów wyżej")
        click.echo("-" * 50)

    processor = MHTMLProcessor()
    results = processor.search_files(keywords, search_path, max_depth=level, verbose=verbose)

    if not results:
        click.echo("Nie znaleziono plików pasujących do kryteriów")
        if verbose:
            click.echo(f"Przeszukano ścieżkę: {search_path}")
            click.echo(f"Z głębokością: {level}")
        return

    click.echo(f"Znaleziono {len(results)} plików:")

    for file_path, file_info in results.items():
        matches = file_info['matches']
        depth = file_info.get('depth', 0)
        size = file_info.get('size', 0)

        # Wyświetl informacje o pliku
        if verbose:
            relative_path = os.path.relpath(file_path, search_path)
            click.echo(f"\n📄 {relative_path}")
            click.echo(f"   Pełna ścieżka: {file_path}")
            click.echo(f"   Głębokość: {depth}, Rozmiar: {format_file_size(size)}")
            click.echo(f"   Dopasowań: {len(matches)}")
        else:
            click.echo(f"\n📄 {file_path}")

        # Pokaż dopasowania
        max_matches = 5 if verbose else 3
        for i, match in enumerate(matches[:max_matches]):
            if verbose:
                click.echo(f"   {i + 1:2d}. {match}")
            else:
                click.echo(f"   • {match}")

        if len(matches) > max_matches:
            click.echo(f"   ... i {len(matches) - max_matches} więcej")


@main.command()
@click.argument('input_file')
@click.argument('output_file')
def export(input_file, output_file):
    """Eksportuj HTML z pliku MHTML/EML do pliku HTML

    Przykład: qra export email.mhtml email.html
    """
    processor = MHTMLProcessor(input_file)
    processor.extract_to_qra_folder()
    html_path = '.qra/html_body.html'
    if not os.path.exists(html_path):
        # Fallback to index.html if html_body.html doesn't exist
        html_path = '.qra/index.html'
        if not os.path.exists(html_path):
            click.echo(f'Nie znaleziono HTML w {input_file} (brak .qra/html_body.html ani .qra/index.html)')
            return

    from bs4 import BeautifulSoup
    import re, mimetypes, base64

    with open(html_path, 'r', encoding='utf-8') as f_in:
        soup = BeautifulSoup(f_in, 'html.parser')

    # Inline CSS files
    for link in soup.find_all('link', rel='stylesheet'):
        href = link.get('href')
        if href:
            css_path = os.path.join('.qra', href)
            if os.path.exists(css_path):
                with open(css_path, 'r', encoding='utf-8') as f_css:
                    css_content = f_css.read()
                style_tag = soup.new_tag('style')
                style_tag.string = css_content
                link.replace_with(style_tag)

    # Inline JS files
    for script in soup.find_all('script', src=True):
        src = script.get('src')
        js_path = os.path.join('.qra', src)
        if os.path.exists(js_path):
            with open(js_path, 'r', encoding='utf-8') as f_js:
                js_content = f_js.read()
            script_tag = soup.new_tag('script')
            script_tag.string = js_content
            script.replace_with(script_tag)

    # Inline images and other assets (base64)
    for tag in soup.find_all(['img', 'audio', 'video', 'source']):
        src = tag.get('src')
        if src:
            asset_path = os.path.join('.qra', src)
            if os.path.exists(asset_path):
                mime, _ = mimetypes.guess_type(asset_path)
                with open(asset_path, 'rb') as f_asset:
                    b64 = base64.b64encode(f_asset.read()).decode('utf-8')
                tag['src'] = f'data:{mime};base64,{b64}'

    # Write the modified HTML
    with open(output_file, 'w', encoding='utf-8') as f_out:
        f_out.write(str(soup))
    click.echo(f'Wyeksportowano HTML z {input_file} do {output_file} (wszystkie assety inline)')


@main.command()
@click.argument('input_file')
@click.argument('output_file', required=False)
@click.option('--inline/--separate', default=True, help='Inline CSS/JS lub osobne pliki')
def export_html(input_file, output_file, inline):
    """Eksportuj MHTML do HTML dla przeglądarek"""
    if not output_file:
        output_file = input_file.replace('.mhtml', '.html')

    processor = MHTMLProcessor(input_file)
    processor.export_to_html(output_file, inline_assets=inline)

    click.echo(f"✅ Wyeksportowano: {input_file} → {output_file}")
    if inline:
        click.echo("📦 Wszystkie zasoby inline - plik gotowy do przeglądarki")
    else:
        click.echo("📁 Zasoby jako osobne pliki")


def calculate_search_path(base_path, scope_levels):
    """Oblicz ścieżkę wyszukiwania na podstawie scope"""
    if scope_levels <= 0:
        return base_path

    # Konwertuj na absolutną ścieżkę
    abs_path = os.path.abspath(base_path)

    # Idź poziomy wyżej
    for _ in range(scope_levels):
        parent = os.path.dirname(abs_path)
        if parent == abs_path:  # Osiągnęliśmy root
            break
        abs_path = parent

    return abs_path


def format_file_size(size_bytes):
    """Formatuj rozmiar pliku"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


if __name__ == '__main__':
    main()