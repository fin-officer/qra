import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape


class TemplateManager:
    def __init__(self):
        self.templates_dir = Path(__file__).parent
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )

    def get_template_files(self, template_name):
        """Pobierz wszystkie pliki dla danego template"""
        template_path = self.templates_dir / template_name

        if not template_path.exists():
            template_path = self.templates_dir / 'basic'  # fallback

        files = []

        # Główny HTML
        html_file = template_path / 'index.html'
        if html_file.exists():
            template = self.env.get_template(f'{template_name}/index.html')
            content = template.render()
            files.append({
                'filename': 'index.html',
                'content': content,
                'type': 'text/html'
            })

        # CSS
        css_file = template_path / 'styles.css'
        if css_file.exists():
            with open(css_file, 'r', encoding='utf-8') as f:
                files.append({
                    'filename': 'styles.css',
                    'content': f.read(),
                    'type': 'text/css'
                })

        # JavaScript
        js_file = template_path / 'script.js'
        if js_file.exists():
            with open(js_file, 'r', encoding='utf-8') as f:
                files.append({
                    'filename': 'script.js',
                    'content': f.read(),
                    'type': 'application/javascript'
                })

        # Dodatkowe pliki
        for extra_file in template_path.glob('*.json'):
            with open(extra_file, 'r', encoding='utf-8') as f:
                files.append({
                    'filename': extra_file.name,
                    'content': f.read(),
                    'type': 'application/json'
                })

        return files

    def get_markdown_template(self, title, content):
        """Pobierz template dla konwersji Markdown"""
        template = self.env.get_template('markdown/index.html')
        html_content = template.render(title=title, content=content)

        css_file = self.templates_dir / 'markdown' / 'styles.css'
        with open(css_file, 'r', encoding='utf-8') as f:
            css_content = f.read()

        return [
            {
                'filename': 'index.html',
                'content': html_content,
                'type': 'text/html'
            },
            {
                'filename': 'styles.css',
                'content': css_content,
                'type': 'text/css'
            }
        ]

    def list_available_templates(self):
        """Lista dostępnych templates"""
        templates = []
        for item in self.templates_dir.iterdir():
            if item.is_dir() and not item.name.startswith('_'):
                templates.append(item.name)
        return sorted(templates)