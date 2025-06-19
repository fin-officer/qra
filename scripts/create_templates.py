#!/usr/bin/env python3
"""
Skrypt do utworzenia wszystkich plików template dla QRA
Uruchom: python create_templates.py
"""

import os
from pathlib import Path


def create_portfolio_files():
    """Tworzy pliki dla template portfolio"""

    # CSS dla portfolio
    portfolio_css = '''/* Portfolio Template */
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
}'''

    # JavaScript dla portfolio
    portfolio_js = '''// Portfolio Template JavaScript
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

    return portfolio_css, portfolio_js


def create_directories():
    """Tworzy strukturę katalogów dla templates"""
    base_dir = Path('qra/templates')

    templates = ['basic', 'portfolio', 'blog', 'docs', 'landing', 'markdown']

    for template in templates:
        template_dir = base_dir / template
        template_dir.mkdir(parents=True, exist_ok=True)
        print(f"✓ Utworzono katalog: {template_dir}")


def create_portfolio_template():
    """Tworzy kompletny template portfolio"""
    portfolio_dir = Path('qra/templates/portfolio')

    css_content, js_content = create_portfolio_files()

    # Zapisz CSS
    with open(portfolio_dir / 'styles.css', 'w', encoding='utf-8') as f:
        f.write(css_content)

    # Zapisz JavaScript
    with open(portfolio_dir / 'script.js', 'w', encoding='utf-8') as f:
        f.write(js_content)

    print("✓ Utworzono pliki portfolio template")


def create_blog_template():
    """Tworzy template blog"""
    blog_dir = Path('qra/templates/blog')

    # HTML dla blog
    blog_html = '''<!DOCTYPE html>
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
</html>'''

    # CSS dla blog (skrócona wersja)
    blog_css = '''/* Blog Template */
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

main {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 3rem;
    margin: 3rem auto;
}

.post {
    background: white;
    padding: 3rem;
    border-radius: 8px;
    box-shadow: 0 2px 20px rgba(0,0,0,0.1);
}

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

@media (max-width: 768px) {
    main { grid-template-columns: 1fr; }
}'''

    # Zapisz pliki
    with open(blog_dir / 'index.html', 'w', encoding='utf-8') as f:
        f.write(blog_html)

    with open(blog_dir / 'styles.css', 'w', encoding='utf-8') as f:
        f.write(blog_css)

    with open(blog_dir / 'script.js', 'w', encoding='utf-8') as f:
        f.write('// Blog JavaScript\nconsole.log("Blog template loaded");')

    print("✓ Utworzono pliki blog template")


def main():
    """Główna funkcja tworzenia templates"""
    print("🚀 Tworzenie struktury templates dla QRA...")

    # Utwórz katalogi
    create_directories()

    # Utwórz templates
    create_portfolio_template()
    create_blog_template()

    print("\n✅ Wszystkie templates zostały utworzone!")
    print("\nDostępne templates:")
    print("- basic (już utworzony)")
    print("- portfolio ✓")
    print("- blog ✓")
    print("- docs (do utworzenia)")
    print("- landing (do utworzenia)")
    print("- markdown ✓")


if __name__ == "__main__":
    main()