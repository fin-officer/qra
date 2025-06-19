import click
import os
import webbrowser
import threading
import time
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
def edit(filename, port, host):
    """Otwórz edytor MHTML w przeglądarce"""
    if filename and not filename.endswith('.mhtml'):
        filename += '.mhtml'

    if filename and not os.path.exists(filename):
        click.echo(f"Plik {filename} nie istnieje. Użyj 'qra create {filename}' aby go utworzyć.")
        return

    # Uruchom serwer Flask
    app = create_app()

    if filename:
        app.config['CURRENT_FILE'] = os.path.abspath(filename)
        processor = MHTMLProcessor(filename)
        processor.extract_to_qra_folder()
        click.echo(f"Rozpakowywanie {filename} do folderu .qra/")

    # Otwórz przeglądarkę po krótkim opóźnieniu
    def open_browser():
        time.sleep(1)
        webbrowser.open(f'http://{host}:{port}')

    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()

    click.echo(f"Uruchamianie edytora na http://{host}:{port}")
    app.run(host=host, port=port, debug=False)


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
def search(query, path):
    """Wyszukaj pliki MHTML zawierające podane słowa kluczowe"""
    keywords = [k.strip('"\'') for k in query.split('+')]

    processor = MHTMLProcessor()
    results = processor.search_files(keywords, path)

    if not results:
        click.echo("Nie znaleziono plików pasujących do kryteriów")
        return

    click.echo(f"Znaleziono {len(results)} plików:")
    for file_path, matches in results.items():
        click.echo(f"\n📄 {file_path}")
        for match in matches[:3]:  # Pokaż pierwsze 3 dopasowania
            click.echo(f"   • {match}")
        if len(matches) > 3:
            click.echo(f"   ... i {len(matches) - 3} więcej")


if __name__ == '__main__':
    main()