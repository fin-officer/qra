# QRA - MHTML Editor and Processor

QRA to zaawansowany edytor plików MHTML z podglądem na żywo, automatycznym zapisywaniem i możliwością konwersji między formatami.

## Instalacja

```bash
# Sklonuj repozytorium lub utwórz nowy projekt
poetry install
```

## Komendy

### Edycja plików MHTML

```bash
# Otwórz edytor dla konkretnego pliku
qra edit filename.mhtml

# Otwórz edytor bez pliku (wybierz z interfejsu)
qra edit
```

Edytor:
- Rozpakuje plik MHTML do folderu `.qra/`
- Otworzy przeglądarkę z interfejsem edycji
- Auto-save co 5 sekund
- Podgląd na żywo
- Kolorowanie składni dla HTML, CSS, JS
- Wszystkie pliki w jednym interfejsie

### Tworzenie nowych plików

```bash
# Utwórz nowy plik MHTML
qra create invoice.mhtml
qra mhtml create invoice.mhtml  # alternatywnie
```

### Konwersja formatów

```bash
# Markdown → MHTML
qra html readme.md              # Utworzy readme.mhtml
qra html readme.md output.mhtml # Własna nazwa

# MHTML → Markdown  
qra md index.mhtml              # Utworzy index.md
qra md index.mhtml output.md    # Własna nazwa
```

### Wyszukiwanie

```bash
# Wyszukaj pliki zawierające wszystkie słowa kluczowe
qra search "invoice"+"paypal"
qra search "dokumenty"+"2024"+"faktura"

# Wyszukaj w konkretnym folderze
qra search "test" --path ./documents/
```

## Struktura projektu

```
projekt/
├── filename.mhtml          # Oryginalny plik MHTML
├── .qra/                   # Rozpakowane komponenty (auto-generowane)
│   ├── index.html          # HTML główny
│   ├── style.css           # Style
│   ├── script.js           # JavaScript
│   ├── image1.jpg          # Obrazy i zasoby
│   └── metadata.json       # Metadane komponentów
├── pyproject.toml
└── README.md
```

## Funkcje edytora

### Interface
- **Lista plików**: Wszystkie komponenty z folderu `.qra/`
- **Edytor kodu**: Kolorowanie składni dla HTML, CSS, JS, JSON, XML
- **Podgląd na żywo**: Automatycznie odświeżany iframe
- **Status zapisu**: Wskaźnik stanu (zapisane/zmodyfikowane/błąd)

### Auto-save
- **Lokalne auto-save**: 2 sekundy po ostatniej zmianie
- **Globalne auto-save**: Co 5 sekund do pliku MHTML
- **Ręczny zapis**: Ctrl+S lub przycisk "Zapisz wszystko"

### Skróty klawiszowe
- `Ctrl+S` - Zapisz bieżący plik
- `Ctrl+N` - Dodaj nowy plik
- `Ctrl+Shift+S` - Zapisz wszystko do MHTML

## Przykłady użycia

### Edycja istniejącego pliku
```bash
qra edit newsletter.mhtml
# Otworzy edytor w przeglądarce
# Edytuj pliki w interfejsie
# Auto-save działa automatycznie
```

### Tworzenie od zera
```bash
qra create portfolio.mhtml
qra edit portfolio.mhtml
# Dodaj nowe pliki przez interface
# Przykład: dodaj "styles.css", "app.js"
```

### Konwersja dokumentacji
```bash
qra html documentation.md
qra edit documentation.mhtml
# Edytuj wynikowy MHTML
# Dodaj style, skrypty, obrazy
```

### Wyszukiwanie projektów
```bash
qra search "react"+"component"
# Znajdzie wszystkie pliki MHTML zawierające oba terminy
# Pokaże kontekst znalezionych dopasowań
```

## Struktura MHTML

QRA automatycznie zarządza strukturą MHTML:

1. **Rozpakowanie**: `filename.mhtml` → `.qra/*.*`
2. **Edycja**: Modyfikuj pliki w folderze `.qra/`
3. **Pakowanie**: `.qra/*.*` → `filename.mhtml` (auto-save)

### Metadane
Plik `.qra/metadata.json` przechowuje:
```json
{
  ".qra/index.html": {
    "content_type": "text/html",
    "content_location": "index.html",
    "encoding": "utf-8",
    "original_name": "index.html"
  }
}
```

## Zaawansowane funkcje

### Markdown z CSS
```bash
qra html article.md
# Automatycznie dodaje profesjonalne style CSS
# Wspiera code highlighting, tabele, blockquotes
```

### Wyszukiwanie z kontekstem
```bash
qra search "API"+"authentication"
# Wyświetla fragmenty tekstu z dopasowaniami
# Pokazuje kontekst ±50 znaków wokół słów kluczowych
```

### Dodawanie plików przez edytor
- Kliknij "Nowy plik" w edytorze
- Wpisz nazwę (rozszerzenie opcjonalne)
- Automatycznie wybierze template na podstawie rozszerzenia

## Rozwiązywanie problemów

### Plik nie otwiera się
```bash
# Sprawdź czy plik istnieje
ls -la *.mhtml

# Utwórz nowy jeśli nie istnieje
qra create filename.mhtml
```

### Błędy auto-save
- Sprawdź uprawnienia do zapisu
- Upewnij się że folder `.qra/` nie jest chroniony
- Uruchom ponownie `qra edit`

### Problemy z podglądem
- Sprawdź czy istnieje plik `.qra/*.html`
- Odśwież przeglądarkę (F5)
- Sprawdź konsolę deweloperską w przeglądarce

## Rozwój

### Dodawanie nowych typów plików
Edytuj `qra/core.py`, funkcję `get_qra_files()`:
```python
file_type = {
    '.html': 'html',
    '.css': 'css', 
    '.js': 'javascript',
    '.json': 'json',
    '.xml': 'xml',
    '.py': 'python',  # Dodaj nowy typ
    # ...
}.get(ext, 'text')
```

### Rozszerzanie wyszukiwania
Modyfikuj `search_files()` w `qra/core.py` dla dodatkowych formatów czy operatorów wyszukiwania.

## Testowanie

Projekt zawiera kompleksowe testy jednostkowe i integracyjne. Aby uruchomić testy:

```bash
# Zainstaluj zależności developerskie
poetry install --with dev

# Uruchom testy
make test

# Uruchom testy z pokryciem kodu
make test-cov

# Sprawdź jakość kodu
make lint

# Sformatuj kod
make format
```

### Struktura testów

- `tests/unit/` - Testy jednostkowe poszczególnych komponentów
  - `test_core.py` - Testy głównej logiki MHTMLProcessor
  - `test_server.py` - Testy serwera Flask
- `tests/integration/` - Testy integracyjne
  - `test_cli.py` - Testy interfejsu wiersza poleceń
- `tests/fixtures/` - Pliki testowe używane w testach

## Licencja

Apache Software License 2.0