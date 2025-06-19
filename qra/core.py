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

    def create_mhtml_from_template(self, filepath, template='basic'):
        """Utwórz plik MHTML na podstawie wybranego template"""
        templates = {
            'basic': self._get_basic_template(),
            'portfolio': self._get_portfolio_template(),
            'blog': self._get_blog_template(),
            'docs': self._get_docs_template(),
            'landing': self._get_landing_template()
        }

        template_data = templates.get(template, templates['basic'])

        msg = MIMEMultipart('related')
        msg['Subject'] = f'QRA Document - {template.title()}'
        msg['MIME-Version'] = '1.0'

        # Dodaj główny HTML
        html_part = MIMEText(template_data['html'], 'html', 'utf-8')
        html_part['Content-Location'] = 'index.html'
        msg.attach(html_part)

        # Dodaj CSS jeśli istnieje
        if template_data.get('css'):
            css_part = MIMEText(template_data['css'], 'css', 'utf-8')
            css_part['Content-Location'] = 'styles.css'
            msg.attach(css_part)

        # Dodaj JavaScript jeśli istnieje
        if template_data.get('js'):
            js_part = MIMEText(template_data['js'], 'javascript', 'utf-8')
            js_part['Content-Location'] = 'script.js'
            msg.attach(js_part)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(msg.as_string())

        self.filepath = filepath

    def create_empty_mhtml(self, filepath):
        """Utwórz pusty plik MHTML (backward compatibility)"""
        self.create_mhtml_from_template(filepath, 'basic')

    def _get_basic_template(self):
        """Podstawowy template HTML"""
        return {
            'html': '''<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nowy Dokument - QRA</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <header>
        <h1>Nowy Dokument</h1>
        <p class="subtitle">Utworzony przez QRA Editor</p>
    </header>

    <main>
        <section>
            <h2>Witaj w edytorze QRA!</h2>
            <p>Ten dokument został automatycznie utworzony. Możesz teraz:</p>
            <ul>
                <li>Edytować ten HTML w edytorze</li>
                <li>Modyfikować style CSS</li>
                <li>Dodawać nowe pliki</li>
                <li>Oglądać podgląd na żywo</li>
            </ul>
        </section>

        <section>
            <h2>Szybki start</h2>
            <p>Wybierz plik z listy po lewej stronie i zacznij edycję!</p>
        </section>
    </main>

    <footer>
        <p>Automatycznie zapisywane co 5 sekund</p>
    </footer>

    <script src="script.js"></script>
</body>
</html>''',
            'css': '''/* QRA Basic Template Styles */
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    line-height: 1.6;
    margin: 0;
    padding: 0;
    background: #f8f9fa;
    color: #333;
}

header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 2rem;
    text-align: center;
}

header h1 {
    margin: 0;
    font-size: 2.5rem;
    font-weight: 300;
}

.subtitle {
    margin: 0.5rem 0 0 0;
    opacity: 0.9;
    font-size: 1.1rem;
}

main {
    max-width: 800px;
    margin: 2rem auto;
    padding: 0 2rem;
}

section {
    background: white;
    margin: 2rem 0;
    padding: 2rem;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

h2 {
    color: #667eea;
    margin-top: 0;
}

ul {
    padding-left: 1.5rem;
}

li {
    margin: 0.5rem 0;
}

footer {
    text-align: center;
    padding: 2rem;
    color: #666;
    font-size: 0.9rem;
}

/* Responsive */
@media (max-width: 600px) {
    main {
        margin: 1rem;
        padding: 0 1rem;
    }

    section {
        padding: 1rem;
    }

    header {
        padding: 1rem;
    }

    header h1 {
        font-size: 2rem;
    }
}''',
            'js': '''// QRA Basic Template JavaScript
console.log('QRA Document loaded successfully!');

// Dodaj interaktywność
document.addEventListener('DOMContentLoaded', function() {
    // Smooth scroll dla linków
    const links = document.querySelectorAll('a[href^="#"]');
    links.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });

    // Animacja pojawiania się sekcji
    const sections = document.querySelectorAll('section');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    });

    sections.forEach(section => {
        section.style.opacity = '0';
        section.style.transform = 'translateY(20px)';
        section.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(section);
    });
});'''
        }

    def _get_portfolio_template(self):
        """Template portfolio"""
        return {
            'html': '''<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Portfolio - Twoje Imię</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <nav>
        <div class="nav-container">
            <h1 class="logo">Portfolio</h1>
            <ul class="nav-menu">
                <li><a href="#about">O mnie</a></li>
                <li><a href="#projects">Projekty</a></li>
                <li><a href="#contact">Kontakt</a></li>
            </ul>
        </div>
    </nav>

    <section class="hero">
        <div class="hero-content">
            <h1>Cześć, jestem <span class="highlight">Developerem</span></h1>
            <p>Tworzę nowoczesne aplikacje i rozwiązania web</p>
            <a href="#projects" class="cta-btn">Zobacz moje projekty</a>
        </div>
    </section>

    <section id="about" class="about">
        <div class="container">
            <h2>O mnie</h2>
            <p>Jestem pasjonatem technologii z doświadczeniem w tworzeniu aplikacji web. Specjalizuję się w nowoczesnych frameworkach i bibliotekach.</p>
        </div>
    </section>

    <section id="projects" class="projects">
        <div class="container">
            <h2>Moje Projekty</h2>
            <div class="project-grid">
                <div class="project-card">
                    <h3>Projekt 1</h3>
                    <p>Opis pierwszego projektu...</p>
                    <div class="tech-stack">React, Node.js, MongoDB</div>
                </div>
                <div class="project-card">
                    <h3>Projekt 2</h3>
                    <p>Opis drugiego projektu...</p>
                    <div class="tech-stack">Vue.js, Python, PostgreSQL</div>
                </div>
            </div>
        </div>
    </section>

    <section id="contact" class="contact">
        <div class="container">
            <h2>Kontakt</h2>
            <p>email@example.com | +48 123 456 789</p>
        </div>
    </section>

    <script src="script.js"></script>
</body>
</html>''',
            'css': '''/* Portfolio Template */
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    line-height: 1.6;
    color: #333;
}

.container { max-width: 1200px; margin: 0 auto; padding: 0 2rem; }

/* Navigation */
nav {
    background: #fff;
    box-shadow: 0 2px 20px rgba(0,0,0,0.1);
    position: fixed;
    width: 100%;
    top: 0;
    z-index: 1000;
}

.nav-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 2rem;
}

.logo { color: #007bff; }

.nav-menu {
    display: flex;
    list-style: none;
    gap: 2rem;
}

.nav-menu a {
    text-decoration: none;
    color: #333;
    font-weight: 500;
    transition: color 0.3s;
}

.nav-menu a:hover { color: #007bff; }

/* Hero Section */
.hero {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
}

.hero h1 { font-size: 3rem; margin-bottom: 1rem; }
.highlight { color: #ffd700; }
.hero p { font-size: 1.2rem; margin-bottom: 2rem; }

.cta-btn {
    display: inline-block;
    background: #ffd700;
    color: #333;
    padding: 1rem 2rem;
    text-decoration: none;
    border-radius: 5px;
    font-weight: bold;
    transition: transform 0.3s;
}

.cta-btn:hover { transform: translateY(-3px); }

/* Sections */
section { padding: 5rem 0; }
.about { background: #f8f9fa; }

h2 {
    font-size: 2.5rem;
    margin-bottom: 2rem;
    text-align: center;
    color: #333;
}

/* Projects */
.project-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 2rem;
    margin-top: 3rem;
}

.project-card {
    background: white;
    padding: 2rem;
    border-radius: 10px;
    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    transition: transform 0.3s;
}

.project-card:hover { transform: translateY(-5px); }

.project-card h3 {
    color: #007bff;
    margin-bottom: 1rem;
}

.tech-stack {
    margin-top: 1rem;
    padding: 0.5rem 1rem;
    background: #e9ecef;
    border-radius: 20px;
    font-size: 0.9rem;
    color: #666;
}

/* Contact */
.contact {
    background: #333;
    color: white;
    text-align: center;
}

/* Responsive */
@media (max-width: 768px) {
    .hero h1 { font-size: 2rem; }
    .nav-menu { flex-direction: column; gap: 1rem; }
    .project-grid { grid-template-columns: 1fr; }
}''',
            'js': '''// Portfolio Template JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Smooth scrolling
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Navbar background on scroll
    window.addEventListener('scroll', function() {
        const nav = document.querySelector('nav');
        if (window.scrollY > 100) {
            nav.style.background = 'rgba(255,255,255,0.95)';
        } else {
            nav.style.background = '#fff';
        }
    });

    // Project cards animation
    const cards = document.querySelectorAll('.project-card');
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    cards.forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(30px)';
        card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(card);
    });
});'''
        }

def _get_blog_template(self):
    """Template bloga"""
    return {
        'html': '''<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mój Blog</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <header class="site-header">
        <div class="container">
            <h1 class="site-title">Mój Blog</h1>
            <p class="site-description">Moje przemyślenia o technologii i życiu</p>
        </div>
    </header>

    <main class="container">
        <article class="post">
            <header class="post-header">
                <h1 class="post-title">Witaj na moim blogu!</h1>
                <div class="post-meta">
                    <time datetime="2024-01-01">1 stycznia 2024</time>
                    <span class="author">Autor</span>
                </div>
            </header>

            <div class="post-content">
                <p>To jest pierwszy wpis na moim nowym blogu utworzonym w QRA. Możesz edytować ten tekst i dodawać nowe wpisy.</p>

                <h2>O czym będę pisał?</h2>
                <ul>
                    <li>Programowanie i technologie</li>
                    <li>Najlepsze praktyki w development</li>
                    <li>Recenzje narzędzi i frameworków</li>
                    <li>Osobiste przemyślenia</li>
                </ul>

                <blockquote>
                    "Najlepszy sposób na naukę to dzielenie się wiedzą z innymi."
                </blockquote>
            </div>
        </article>

        <aside class="sidebar">
            <section class="widget">
                <h3>O mnie</h3>
                <p>Jestem programistą z pasją do tworzenia i dzielenia się wiedzą.</p>
            </section>

            <section class="widget">
                <h3>Ostatnie wpisy</h3>
                <ul class="recent-posts">
                    <li><a href="#">Witaj na moim blogu!</a></li>
                    <li><a href="#">Dodaj tutaj kolejne wpisy...</a></li>
                </ul>
            </section>
        </aside>
    </main>

    <script src="script.js"></script>
</body>
</html>''',
        'css': '''/* Blog Template */
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: Georgia, 'Times New Roman', serif;
    line-height: 1.7;
    color: #333;
    background: #fafafa;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 2rem;
}

/* Header */
.site-header {
    background: #2c3e50;
    color: white;
    padding: 3rem 0;
    text-align: center;
}

.site-title {
    font-size: 3rem;
    margin-bottom: 0.5rem;
    font-weight: normal;
}

.site-description {
    font-size: 1.2rem;
    opacity: 0.8;
    font-style: italic;
}

/* Main Layout */
main {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 3rem;
    margin: 3rem auto;
}

/* Post Styles */
.post {
    background: white;
    padding: 3rem;
    border-radius: 8px;
    box-shadow: 0 2px 20px rgba(0,0,0,0.1);
}

.post-title {
    font-size: 2.5rem;
    margin-bottom: 1rem;
    color: #2c3e50;
}

.post-meta {
    margin-bottom: 2rem;
    color: #666;
    border-bottom: 1px solid #eee;
    padding-bottom: 1rem;
}

.post-meta time, .post-meta .author {
    margin-right: 1rem;
}

.post-content {
    font-size: 1.1rem;
}

.post-content h2 {
    margin: 2rem 0 1rem 0;
    color: #34495e;
}

.post-content ul {
    margin: 1rem 0;
    padding-left: 2rem;
}

.post-content li {
    margin: 0.5rem 0;
}

blockquote {
    background: #ecf0f1;
    border-left: 4px solid #3498db;
    margin: 2rem 0;
    padding: 1rem 2rem;
    font-style: italic;
    color: #555;
}

/* Sidebar */
.sidebar {
    display: flex;
    flex-direction: column;
    gap: 2rem;
}

.widget {
    background: white;
    padding: 2rem;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.widget h3 {
    margin-bottom: 1rem;
    color: #2c3e50;
    border-bottom: 2px solid #3498db;
    padding-bottom: 0.5rem;
}

.recent-posts {
    list-style: none;
}

.recent-posts li {
    margin: 1rem 0;
    padding: 0.5rem 0;
    border-bottom: 1px solid #eee;
}

.recent-posts a {
    color: #3498db;
    text-decoration: none;
    transition: color 0.3s;
}

.recent-posts a:hover {
    color: #2980b9;
}

/* Responsive */
@media (max-width: 768px) {
    main {
        grid-template-columns: 1fr;
    }

    .post {
        padding: 2rem;
    }

    .site-title {
        font-size: 2rem;
    }

    .post-title {
        font-size: 2rem;
    }
}''',
        'js': '''// Blog Template JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Reading progress bar
    const progressBar = document.createElement('div');
    progressBar.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 0%;
        height: 3px;
        background: #3498db;
        z-index: 1000;
        transition: width 0.3s;
    `;
    document.body.appendChild(progressBar);

    window.addEventListener('scroll', function() {
        const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
        const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
        const scrolled = (winScroll / height) * 100;
        progressBar.style.width = scrolled + '%';
    });

    // Smooth reveal animation for post content
    const postContent = document.querySelector('.post-content');
    if (postContent) {
        const elements = postContent.querySelectorAll('h2, p, ul, blockquote');

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }
            });
        }, { threshold: 0.1 });

        elements.forEach(el => {
            el.style.opacity = '0';
            el.style.transform = 'translateY(20px)';
            el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
            observer.observe(el);
        });
    }
});'''
    }


def _get_docs_template(self):
    """Template dokumentacji"""
    return {
        'html': '''<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dokumentacja</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <nav class="sidebar">
        <div class="sidebar-content">
            <h1 class="project-title">Dokumentacja</h1>
            <ul class="nav-menu">
                <li><a href="#introduction" class="nav-link">Wprowadzenie</a></li>
                <li><a href="#installation" class="nav-link">Instalacja</a></li>
                <li><a href="#usage" class="nav-link">Użytkowanie</a></li>
                <li><a href="#api" class="nav-link">API Reference</a></li>
                <li><a href="#examples" class="nav-link">Przykłady</a></li>
            </ul>
        </div>
    </nav>

    <main class="content">
        <section id="introduction">
            <h1>Wprowadzenie</h1>
            <p>Witaj w dokumentacji! Ten szablon został stworzony dla projektów wymagających przejrzystej dokumentacji.</p>

            <div class="alert alert-info">
                <strong>Informacja:</strong> To jest przykładowa dokumentacja utworzona przez QRA.
            </div>
        </section>

        <section id="installation">
            <h2>Instalacja</h2>
            <p>Aby zainstalować projekt, wykonaj następujące kroki:</p>

            <pre><code>npm install your-package
# lub
yarn add your-package</code></pre>
        </section>

        <section id="usage">
            <h2>Użytkowanie</h2>
            <p>Podstawowe użytkowanie:</p>

            <pre><code>import YourPackage from 'your-package';

const instance = new YourPackage({
    option1: 'value1',
    option2: 'value2'
});

instance.doSomething();</code></pre>
        </section>

        <section id="api">
            <h2>API Reference</h2>

            <div class="api-method">
                <h3><code>doSomething(params)</code></h3>
                <p>Opis metody i jej działania.</p>

                <h4>Parametry:</h4>
                <ul>
                    <li><code>param1</code> (string) - Opis pierwszego parametru</li>
                    <li><code>param2</code> (number) - Opis drugiego parametru</li>
                </ul>

                <h4>Zwraca:</h4>
                <p><code>Promise&lt;string&gt;</code> - Opis zwracanej wartości</p>
            </div>
        </section>

        <section id="examples">
            <h2>Przykłady</h2>

            <h3>Przykład 1: Podstawowe użycie</h3>import email
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

            <h3>Przykład 1: Podstawowe użycie</h3>
            <pre><code>const result = await instance.doSomething({
    input: 'test data',
    options: { verbose: true }
});

console.log(result);</code></pre>

            <h3>Przykład 2: Zaawansowana konfiguracja</h3>
            <pre><code>const advancedInstance = new YourPackage({
    apiKey: 'your-api-key',
    timeout: 5000,
    retries: 3
});

try {
    const data = await advancedInstance.processData(input);
    console.log('Sukces:', data);
} catch (error) {
    console.error('Błąd:', error.message);
}</code></pre>
        </section>
    </main>

    <script src="script.js"></script>
</body>
</html>''',
        'css': '''/* Documentation Template */
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    line-height: 1.6;
    color: #333;
    display: flex;
    min-height: 100vh;
}

/* Sidebar */
.sidebar {
    width: 280px;
    background: #2c3e50;
    color: white;
    position: fixed;
    height: 100vh;
    overflow-y: auto;
    z-index: 1000;
}

.sidebar-content {
    padding: 2rem;
}

.project-title {
    font-size: 1.5rem;
    margin-bottom: 2rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid #34495e;
}

.nav-menu {
    list-style: none;
}

.nav-menu li {
    margin: 0.5rem 0;
}

.nav-link {
    display: block;
    color: #ecf0f1;
    text-decoration: none;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    transition: background 0.3s;
}

.nav-link:hover, .nav-link.active {
    background: #34495e;
    color: #3498db;
}

/* Content */
.content {
    flex: 1;
    margin-left: 280px;
    padding: 3rem;
    max-width: none;
}

section {
    margin-bottom: 3rem;
}

h1 {
    font-size: 2.5rem;
    margin-bottom: 1rem;
    color: #2c3e50;
    border-bottom: 3px solid #3498db;
    padding-bottom: 0.5rem;
}

h2 {
    font-size: 2rem;
    margin: 2rem 0 1rem 0;
    color: #34495e;
}

h3 {
    font-size: 1.5rem;
    margin: 1.5rem 0 1rem 0;
    color: #34495e;
}

h4 {
    font-size: 1.2rem;
    margin: 1rem 0 0.5rem 0;
    color: #555;
}

p {
    margin-bottom: 1rem;
    font-size: 1.05rem;
}

/* Code blocks */
pre {
    background: #f8f9fa;
    border: 1px solid #e9ecef;
    border-radius: 6px;
    padding: 1rem;
    margin: 1rem 0;
    overflow-x: auto;
    font-family: 'Monaco', 'Consolas', monospace;
    font-size: 0.9rem;
}

code {
    background: #f1f3f4;
    padding: 0.2rem 0.4rem;
    border-radius: 3px;
    font-family: 'Monaco', 'Consolas', monospace;
    font-size: 0.9em;
}

pre code {
    background: none;
    padding: 0;
}

/* Alerts */
.alert {
    padding: 1rem;
    margin: 1rem 0;
    border-radius: 6px;
    border-left: 4px solid;
}

.alert-info {
    background: #e3f2fd;
    border-color: #2196f3;
    color: #0d47a1;
}

.alert strong {
    font-weight: 600;
}

/* API Documentation */
.api-method {
    background: #f8f9fa;
    border: 1px solid #e9ecef;
    border-radius: 8px;
    padding: 1.5rem;
    margin: 1.5rem 0;
}

.api-method h3 {
    margin-top: 0;
    color: #e83e8c;
    font-family: 'Monaco', 'Consolas', monospace;
}

.api-method h4 {
    margin-top: 1.5rem;
    color: #495057;
}

.api-method ul {
    margin: 0.5rem 0;
    padding-left: 1.5rem;
}

.api-method li {
    margin: 0.3rem 0;
}

/* Responsive */
@media (max-width: 768px) {
    .sidebar {
        transform: translateX(-100%);
        transition: transform 0.3s ease;
    }

    .sidebar.open {
        transform: translateX(0);
    }

    .content {
        margin-left: 0;
        padding: 1rem;
    }

    h1 { font-size: 2rem; }
    h2 { font-size: 1.5rem; }
}

/* Scrollspy */
.nav-link.active {
    background: #3498db;
    color: white;
}''',
        'js': '''// Documentation Template JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Smooth scrolling for navigation links
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            const targetElement = document.querySelector(targetId);

            if (targetElement) {
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });

                // Update active link
                document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
                this.classList.add('active');
            }
        });
    });

    // Scrollspy - highlight current section in navigation
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-link');

    function updateActiveLink() {
        let current = '';

        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.clientHeight;

            if (window.scrollY >= sectionTop - 100) {
                current = section.getAttribute('id');
            }
        });

        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href') === `#${current}`) {
                link.classList.add('active');
            }
        });
    }

    window.addEventListener('scroll', updateActiveLink);
    updateActiveLink(); // Initial call

    // Copy code functionality
    document.querySelectorAll('pre code').forEach(codeBlock => {
        const button = document.createElement('button');
        button.className = 'copy-btn';
        button.textContent = 'Kopiuj';
        button.style.cssText = `
            position: absolute;
            top: 0.5rem;
            right: 0.5rem;
            background: #6c757d;
            color: white;
            border: none;
            padding: 0.25rem 0.5rem;
            border-radius: 3px;
            font-size: 0.75rem;
            cursor: pointer;
            opacity: 0;
            transition: opacity 0.3s;
        `;

        const pre = codeBlock.parentElement;
        pre.style.position = 'relative';
        pre.appendChild(button);

        pre.addEventListener('mouseenter', () => {
            button.style.opacity = '1';
        });

        pre.addEventListener('mouseleave', () => {
            button.style.opacity = '0';
        });

        button.addEventListener('click', () => {
            navigator.clipboard.writeText(codeBlock.textContent).then(() => {
                button.textContent = 'Skopiowano!';
                setTimeout(() => {
                    button.textContent = 'Kopiuj';
                }, 2000);
            });
        });
    });

    // Mobile menu toggle (if needed)
    if (window.innerWidth <= 768) {
        const sidebar = document.querySelector('.sidebar');
        const toggleBtn = document.createElement('button');
        toggleBtn.innerHTML = '☰ Menu';
        toggleBtn.style.cssText = `
            position: fixed;
            top: 1rem;
            left: 1rem;
            z-index: 1001;
            background: #2c3e50;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            cursor: pointer;
        `;

        document.body.appendChild(toggleBtn);

        toggleBtn.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }
});'''
    }


def _get_landing_template(self):
    """Template landing page"""
    return {
        'html': '''<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Landing Page - Twój Produkt</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <nav class="navbar">
        <div class="nav-container">
            <div class="logo">TwójProdukt</div>
            <ul class="nav-menu">
                <li><a href="#features">Funkcje</a></li>
                <li><a href="#pricing">Cennik</a></li>
                <li><a href="#contact">Kontakt</a></li>
                <li><a href="#" class="cta-nav">Rozpocznij</a></li>
            </ul>
        </div>
    </nav>

    <section class="hero">
        <div class="hero-container">
            <div class="hero-content">
                <h1 class="hero-title">Rewolucyjne rozwiązanie dla Twojego biznesu</h1>
                <p class="hero-subtitle">Odkryj moc nowoczesnych technologii i przekształć sposób pracy swojej firmy</p>
                <div class="hero-buttons">
                    <a href="#" class="btn btn-primary">Rozpocznij za darmo</a>
                    <a href="#" class="btn btn-outline">Zobacz demo</a>
                </div>
            </div>
            <div class="hero-image">
                <div class="hero-placeholder">🚀 Twój produkt tutaj</div>
            </div>
        </div>
    </section>

    <section id="features" class="features">
        <div class="container">
            <h2 class="section-title">Dlaczego warto wybrać nas?</h2>
            <div class="features-grid">
                <div class="feature-card">
                    <div class="feature-icon">⚡</div>
                    <h3>Szybkość</h3>
                    <p>Niezrównana wydajność która przyspieszy Twoją pracę o 300%</p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">🔒</div>
                    <h3>Bezpieczeństwo</h3>
                    <p>Najwyższe standardy bezpieczeństwa chronią Twoje dane 24/7</p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">📈</div>
                    <h3>Skalowalność</h3>
                    <p>Rozwiązanie które rośnie razem z Twoim biznesem</p>
                </div>
            </div>
        </div>
    </section>

    <section id="pricing" class="pricing">
        <div class="container">
            <h2 class="section-title">Proste cenniki</h2>
            <div class="pricing-grid">
                <div class="pricing-card">
                    <h3>Starter</h3>
                    <div class="price">0 zł<span>/miesiąc</span></div>
                    <ul class="features-list">
                        <li>✓ Podstawowe funkcje</li>
                        <li>✓ Do 100 użytkowników</li>
                        <li>✓ Email support</li>
                    </ul>
                    <a href="#" class="btn btn-outline">Wybierz plan</a>
                </div>
                <div class="pricing-card featured">
                    <h3>Pro</h3>
                    <div class="price">99 zł<span>/miesiąc</span></div>
                    <ul class="features-list">
                        <li>✓ Wszystkie funkcje</li>
                        <li>✓ Nieograniczeni użytkownicy</li>
                        <li>✓ 24/7 support</li>
                        <li>✓ Zaawansowane analytics</li>
                    </ul>
                    <a href="#" class="btn btn-primary">Wybierz plan</a>
                </div>
                <div class="pricing-card">
                    <h3>Enterprise</h3>
                    <div class="price">Indywidualnie</div>
                    <ul class="features-list">
                        <li>✓ Dedykowane rozwiązania</li>
                        <li>✓ Custom integracje</li>
                        <li>✓ Dedykowany manager</li>
                    </ul>
                    <a href="#" class="btn btn-outline">Skontaktuj się</a>
                </div>
            </div>
        </div>
    </section>

    <section id="contact" class="contact">
        <div class="container">
            <h2 class="section-title">Gotowy na start?</h2>
            <p class="contact-subtitle">Dołącz do tysięcy zadowolonych klientów już dziś</p>
            <a href="#" class="btn btn-primary btn-large">Rozpocznij bezpłatnie</a>
        </div>
    </section>

    <footer class="footer">
        <div class="container">
            <p>&copy; 2024 TwójProdukt. Wszystkie prawa zastrzeżone.</p>
        </div>
    </footer>

    <script src="script.js"></script>
</body>
</html>''',
        'css': '''/* Landing Page Template */
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    line-height: 1.6;
    color: #333;
}

.container { max-width: 1200px; margin: 0 auto; padding: 0 2rem; }

/* Navigation */
.navbar {
    background: rgba(255,255,255,0.95);
    backdrop-filter: blur(10px);
    position: fixed;
    width: 100%;
    top: 0;
    z-index: 1000;
    box-shadow: 0 2px 20px rgba(0,0,0,0.1);
}

.nav-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 2rem;
    max-width: 1200px;
    margin: 0 auto;
}

.logo {
    font-size: 1.5rem;
    font-weight: bold;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.nav-menu {
    display: flex;
    list-style: none;
    gap: 2rem;
    align-items: center;
}

.nav-menu a {
    text-decoration: none;
    color: #333;
    font-weight: 500;
    transition: color 0.3s;
}

.nav-menu a:hover { color: #667eea; }

.cta-nav {
    background: #667eea !important;
    color: white !important;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    transition: transform 0.3s;
}

.cta-nav:hover { transform: translateY(-2px); }

/* Hero Section */
.hero {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 8rem 0 4rem 0;
    margin-top: 70px;
}

.hero-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 2rem;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4rem;
    align-items: center;
}

.hero-title {
    font-size: 3.5rem;
    font-weight: 700;
    line-height: 1.2;
    margin-bottom: 1.5rem;
}

.hero-subtitle {
    font-size: 1.3rem;
    margin-bottom: 2rem;
    opacity: 0.9;
}

.hero-buttons {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
}

.hero-image {
    display: flex;
    justify-content: center;
    align-items: center;
}

.hero-placeholder {
    background: rgba(255,255,255,0.1);
    border: 2px dashed rgba(255,255,255,0.3);
    padding: 4rem 2rem;
    border-radius: 12px;
    text-align: center;
    font-size: 2rem;
}

/* Buttons */
.btn {
    display: inline-block;
    padding: 1rem 2rem;
    border-radius: 8px;
    text-decoration: none;
    font-weight: 600;
    transition: all 0.3s;
    border: 2px solid transparent;
    cursor: pointer;
}

.btn-primary {
    background: #ff6b6b;
    color: white;
}

.btn-primary:hover {
    background: #ff5252;
    transform: translateY(-2px);
    box-shadow: 0 10px 30px rgba(255,107,107,0.3);
}

.btn-outline {
    background: transparent;
    color: white;
    border-color: white;
}

.btn-outline:hover {
    background: white;
    color: #333;
}

.btn-large {
    padding: 1.5rem 3rem;
    font-size: 1.2rem;
}

/* Sections */
.section-title {
    text-align: center;
    font-size: 2.5rem;
    margin-bottom: 3rem;
    color: #333;
}

/* Features */
.features {
    padding: 6rem 0;
    background: #f8f9fa;
}

.features-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 3rem;
}

.feature-card {
    background: white;
    padding: 3rem 2rem;
    border-radius: 12px;
    text-align: center;
    box-shadow: 0 5px 30px rgba(0,0,0,0.1);
    transition: transform 0.3s;
}

.feature-card:hover {
    transform: translateY(-10px);
}

.feature-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
}

.feature-card h3 {
    font-size: 1.5rem;
    margin-bottom: 1rem;
    color: #333;
}

/* Pricing */
.pricing {
    padding: 6rem 0;
    background: white;
}

.pricing-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 2rem;
    max-width: 1000px;
    margin: 0 auto;
}

.pricing-card {
    background: white;
    border: 2px solid #e9ecef;
    border-radius: 12px;
    padding: 2.5rem 2rem;
    text-align: center;
    position: relative;
    transition: transform 0.3s;
}

.pricing-card:hover {
    transform: scale(1.05);
}

.pricing-card.featured {
    border-color: #667eea;
    transform: scale(1.1);
}

.pricing-card.featured::before {
    content: 'Najpopularniejszy';
    position: absolute;
    top: -12px;
    left: 50%;
    transform: translateX(-50%);
    background: #667eea;
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font-size: 0.8rem;
}

.pricing-card h3 {
    font-size: 1.5rem;
    margin-bottom: 1rem;
}

.price {
    font-size: 3rem;
    font-weight: bold;
    color: #667eea;
    margin-bottom: 2rem;
}

.price span {
    font-size: 1rem;
    color: #666;
}

.features-list {
    list-style: none;
    margin-bottom: 2rem;
}

.features-list li {
    padding: 0.5rem 0;
    color: #555;
}

/* Contact */
.contact {
    padding: 6rem 0;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    text-align: center;
}

.contact-subtitle {
    font-size: 1.2rem;
    margin-bottom: 2rem;
    opacity: 0.9;
}

/* Footer */
.footer {
    background: #2c3e50;
    color: white;
    padding: 2rem 0;
    text-align: center;
}

/* Responsive */
@media (max-width: 768px) {
    .hero-container {
        grid-template-columns: 1fr;
        text-align: center;
    }

    .hero-title {
        font-size: 2.5rem;
    }

    .nav-menu {
        display: none; /* Mobile menu would need JS */
    }

    .features-grid,
    .pricing-grid {
        grid-template-columns: 1fr;
    }

    .pricing-card.featured {
        transform: none;
    }
}''',
        'js': '''// Landing Page Template JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Smooth scrolling for navigation links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Navbar background on scroll
    const navbar = document.querySelector('.navbar');
    window.addEventListener('scroll', function() {
        if (window.scrollY > 100) {
            navbar.style.background = 'rgba(255,255,255,0.98)';
        } else {
            navbar.style.background = 'rgba(255,255,255,0.95)';
        }
    });

    // Animate elements on scroll
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    // Observe feature cards
    document.querySelectorAll('.feature-card, .pricing-card').forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(30px)';
        card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(card);
    });

    // Typing effect for hero title
    const heroTitle = document.querySelector('.hero-title');
    const originalText = heroTitle.textContent;
    heroTitle.textContent = '';

    let i = 0;
    function typeWriter() {
        if (i < originalText.length) {
            heroTitle.textContent += originalText.charAt(i);
            i++;
            setTimeout(typeWriter, 50);
        }
    }

    // Start typing effect after a short delay
    setTimeout(typeWriter, 500);

    // Add hover effects to buttons
    document.querySelectorAll('.btn').forEach(btn => {
        btn.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-3px)';
        });

        btn.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });

    // Pricing card selection
    document.querySelectorAll('.pricing-card .btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const plan = this.closest('.pricing-card').querySelector('h3').textContent;
            alert(`Wybrałeś plan: ${plan}. Tutaj będzie przekierowanie do płatności.`);
        });
    });
});'''
    }


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


def search_files(self, keywords, search_path='.', max_depth=3, verbose=False):
    """Wyszukaj pliki MHTML zawierające słowa kluczowe z kontrolą głębokości"""
    results = {}
    search_path = os.path.abspath(search_path)

    if verbose:
        print(f"Rozpoczynanie wyszukiwania w: {search_path}")
        print(f"Maksymalna głębokość: {max_depth}")

    def should_search_directory(dir_path, base_path, max_depth):
        """Sprawdź czy należy przeszukiwać katalog na podstawie głębokości"""
        try:
            relative_path = os.path.relpath(dir_path, base_path)
            if relative_path == '.':
                return True
            depth = len([p for p in relative_path.split(os.sep) if p and p != '..'])
            return depth <= max_depth
        except ValueError:
            return False

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