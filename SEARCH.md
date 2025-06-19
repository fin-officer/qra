Stworzę kompletne rozwiązanie cross-platform do przeszukiwania plików MHTML z danymi JSON, które będzie działać jako narzędzie CLI.Stworzyłem kompletne rozwiązanie cross-platform do przeszukiwania plików MHTML z danymi JSON. Oto jak z niego korzystać:

## Instalacja i przygotowanie

```bash
# Zapisz kod jako search.py
chmod +x search.py

# Zainstaluj opcjonalne zależności dla lepszej wydajności
pip install duckdb tqdm

# Możesz też utworzyć alias w ~/.bashrc lub ~/.zshrc
alias search="python3 /path/to/search.py"
```

## Przykłady użycia

### 1. Szybkie przeszukiwanie bez indeksowania
```bash
# Szukaj "John" w plikach MHTML w katalogu /data
./search.py --scan /data --query "John"

# Przeszukaj wiele katalogów
./search.py --scan /home/user/documents --query "email"
```

### 2. Indeksowanie dla szybszych przeszukiwań
```bash
# Zindeksuj pliki w katalogu
./search.py --index --path /data --path ~/documents

# Użyj custom bazy danych
./search.py --index --path /data --index-db /tmp/my_index.db
```

### 3. Zapytania SQL na zindeksowanych danych
```bash
# Podstawowe zapytanie SQL
./search.py --sql "SELECT file_path, json_data FROM mhtml_files WHERE json_data LIKE '%John%'"

# Zliczanie obiektów JSON per plik
./search.py --sql "SELECT file_path, COUNT(*) as json_count FROM mhtml_files f JOIN json_data j ON f.id = j.file_id GROUP BY file_path"

# Zaawansowane zapytania z DuckDB
./search.py --sql "SELECT file_path, json_extract(json_data, '$.name') as name FROM m