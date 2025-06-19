from flask import Flask, render_template_string, request, jsonify
import threading
import time
from .core import MHTMLProcessor


# Auto-save thread
class AutoSaveManager:
    def __init__(self):
        self.processor = None
        self.running = False
        self.thread = None

    def start(self, processor):
        self.processor = processor
        self.running = True
        self.thread = threading.Thread(target=self._auto_save_loop)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.running = False

    def _auto_save_loop(self):
        while self.running:
            time.sleep(5)  # Auto-save co 5 sekund
            if self.processor and self.processor.filepath:
                try:
                    self.processor.pack_from_qra_folder()
                    print(f"Auto-save: {self.processor.filepath}")
                except Exception as e:
                    print(f"Auto-save error: {e}")


auto_save_manager = AutoSaveManager()


def create_app():
    app = Flask(__name__)

    EDITOR_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>QRA Editor</title>
    <meta charset="utf-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
               background: #1e1e1e; color: #d4d4d4; height: 100vh; overflow: hidden; }

        .container { display: flex; height: 100vh; }
        .sidebar { width: 300px; background: #252526; border-right: 1px solid #3e3e42; 
                   display: flex; flex-direction: column; }
        .main-content { flex: 1; display: flex; flex-direction: column; }

        .header { background: #2d2d30; padding: 10px 20px; border-bottom: 1px solid #3e3e42;
                  display: flex; justify-content: between; align-items: center; }
        .header h1 { font-size: 18px; color: #cccccc; }
        .save-status { font-size: 12px; color: #608b4e; margin-left: auto; }

        .file-list { flex: 1; overflow-y: auto; }
        .file-item { padding: 12px 20px; cursor: pointer; border-bottom: 1px solid #3e3e42;
                     display: flex; justify-content: space-between; align-items: center; }
        .file-item:hover { background: #2a2d2e; }
        .file-item.active { background: #094771; }
        .file-name { font-weight: 500; }
        .file-type { font-size: 11px; color: #969696; text-transform: uppercase; }
        .file-size { font-size: 11px; color: #969696; }

        .editor-area { flex: 1; display: flex; }
        .editor { flex: 1; display: flex; flex-direction: column; }
        .preview { flex: 1; background: white; border-left: 1px solid #3e3e42; }

        .editor-header { background: #2d2d30; padding: 8px 20px; border-bottom: 1px solid #3e3e42;
                         font-size: 13px; color: #cccccc; }

        #code-editor { flex: 1; background: #1e1e1e; color: #d4d4d4; border: none; outline: none;
                       font-family: 'Consolas', 'Monaco', monospace; font-size: 14px; line-height: 1.4;
                       padding: 20px; resize: none; }

        #preview-frame { width: 100%; height: 100%; border: none; background: white; }

        .controls { background: #2d2d30; padding: 10px 20px; border-top: 1px solid #3e3e42;
                    display: flex; gap: 10px; }
        .btn { background: #0e639c; color: white; border: none; padding: 8px 16px; 
               border-radius: 4px; cursor: pointer; font-size: 13px; }
        .btn:hover { background: #1177bb; }
        .btn.secondary { background: #5a5a5a; }
        .btn.secondary:hover { background: #6a6a6a; }

        .loading { display: none; position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                   background: rgba(0,0,0,0.8); color: white; padding: 20px; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <div class="header">
                <h1>QRA Editor</h1>
                <div class="save-status" id="save-status">●</div>
            </div>
            <div class="file-list" id="file-list">
                <!-- Files will be loaded here -->
            </div>
            <div class="controls">
                <button class="btn" onclick="saveAll()">Zapisz wszystko</button>
                <button class="btn secondary" onclick="addFile()">Nowy plik</button>
            </div>
        </div>

        <div class="main-content">
            <div class="editor-area">
                <div class="editor">
                    <div class="editor-header" id="editor-header">
                        Wybierz plik do edycji
                    </div>
                    <textarea id="code-editor" placeholder="Wybierz plik z listy po lewej stronie..."></textarea>
                </div>
                <div class="preview">
                    <iframe id="preview-frame" src="/preview"></iframe>
                </div>
            </div>
        </div>
    </div>

    <div class="loading" id="loading">Ładowanie...</div>

    <script>
        let currentFile = null;
        let files = [];
        let autoSaveTimer = null;

        // Załaduj listę plików
        function loadFiles() {
            fetch('/api/files')
            .then(response => response.json())
            .then(data => {
                files = data.files;
                renderFileList();
                if (files.length > 0 && !currentFile) {
                    selectFile(files[0]);
                }
            })
            .catch(error => console.error('Error loading files:', error));
        }

        function renderFileList() {
            const fileList = document.getElementById('file-list');
            fileList.innerHTML = files.map(file => `
                <div class="file-item ${currentFile && currentFile.name === file.name ? 'active' : ''}" 
                     onclick="selectFile('${file.name}')">
                    <div>
                        <div class="file-name">${file.name}</div>
                        <div class="file-type">${file.type}</div>
                    </div>
                    <div class="file-size">${formatFileSize(file.size)}</div>
                </div>
            `).join('');
        }

        function selectFile(fileName) {
            const file = files.find(f => f.name === fileName || f === fileName);
            if (!file) return;

            currentFile = typeof file === 'string' ? files.find(f => f.name === file) : file;

            document.getElementById('editor-header').textContent = `Edycja: ${currentFile.name}`;
            document.getElementById('code-editor').value = currentFile.content;

            // Ustaw tryb edytora na podstawie typu pliku
            const editor = document.getElementById('code-editor');
            editor.setAttribute('data-language', currentFile.type);

            renderFileList();
            scheduleAutoSave();
        }

        function formatFileSize(bytes) {
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + ' KB';
            return Math.round(bytes / (1024 * 1024)) + ' MB';
        }

        function scheduleAutoSave() {
            clearTimeout(autoSaveTimer);
            autoSaveTimer = setTimeout(() => {
                if (currentFile) {
                    saveCurrentFile();
                }
            }, 2000); // Auto-save po 2 sekundach od ostatniej zmiany
        }

        function saveCurrentFile() {
            if (!currentFile) return;

            const content = document.getElementById('code-editor').value;
            currentFile.content = content;

            fetch('/api/save-file', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    filename: currentFile.name,
                    content: content
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateSaveStatus('saved');
                    // Odśwież podgląd
                    document.getElementById('preview-frame').src = '/preview?' + Date.now();
                }
            })
            .catch(error => {
                console.error('Save error:', error);
                updateSaveStatus('error');
            });
        }

        function saveAll() {
            updateSaveStatus('saving');
            fetch('/api/save-all', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateSaveStatus('saved');
                    alert('Wszystkie pliki zostały zapisane do MHTML');
                }
            })
            .catch(error => {
                console.error('Save all error:', error);
                updateSaveStatus('error');
            });
        }

        function updateSaveStatus(status) {
            const statusEl = document.getElementById('save-status');
            switch(status) {
                case 'saved':
                    statusEl.style.color = '#608b4e';
                    statusEl.textContent = '●';
                    break;
                case 'saving':
                    statusEl.style.color = '#dcdcaa';
                    statusEl.textContent = '◐';
                    break;
                case 'modified':
                    statusEl.style.color = '#f44747';
                    statusEl.textContent = '●';
                    break;
                case 'error':
                    statusEl.style.color = '#f44747';
                    statusEl.textContent = '✕';
                    break;
            }
        }

        function addFile() {
            const name = prompt('Nazwa nowego pliku:');
            if (!name) return;

            fetch('/api/add-file', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: name })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    loadFiles();
                }
            });
        }

        // Event listeners
        document.getElementById('code-editor').addEventListener('input', () => {
            updateSaveStatus('modified');
            scheduleAutoSave();
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                if (e.key === 's') {
                    e.preventDefault();
                    saveCurrentFile();
                } else if (e.key === 'n') {
                    e.preventDefault();
                    addFile();
                }
            }
        });

        // Initialize
        loadFiles();

        // Auto-refresh preview every 10 seconds
        setInterval(() => {
            const frame = document.getElementById('preview-frame');
            if (frame.src.includes('/preview')) {
                frame.src = '/preview?' + Date.now();
            }
        }, 10000);
    </script>
</body>
</html>
    '''

    @app.route('/')
    def index():
        return render_template_string(EDITOR_TEMPLATE)

    @app.route('/api/files')
    def get_files():
        try:
            current_file = app.config.get('CURRENT_FILE')
            if current_file:
                processor = MHTMLProcessor(current_file)
                files = processor.get_qra_files()
                return jsonify({'success': True, 'files': files})
            else:
                return jsonify({'success': True, 'files': []})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/save-file', methods=['POST'])
    def save_file():
        try:
            data = request.get_json()
            filename = data['filename']
            content = data['content']

            current_file = app.config.get('CURRENT_FILE')
            if current_file:
                processor = MHTMLProcessor(current_file)
                processor.save_file_content(filename, content)
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'Brak aktywnego pliku'}), 400

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/save-all', methods=['POST'])
    def save_all():
        try:
            current_file = app.config.get('CURRENT_FILE')
            if current_file:
                processor = MHTMLProcessor(current_file)
                processor.pack_from_qra_folder()
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'Brak aktywnego pliku'}), 400

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/add-file', methods=['POST'])
    def add_file():
        try:
            data = request.get_json()
            filename = data['filename']

            # Dodaj rozszerzenie jeśli nie ma
            if '.' not in filename:
                filename += '.html'

            current_file = app.config.get('CURRENT_FILE')
            if current_file:
                processor = MHTMLProcessor(current_file)

                # Zawartość domyślna na podstawie rozszerzenia
                ext = filename.split('.')[-1].lower()
                if ext == 'html':
                    content = '<!DOCTYPE html>\n<html>\n<head>\n    <title>New Page</title>\n</head>\n<body>\n    <h1>New Page</h1>\n</body>\n</html>'
                elif ext == 'css':
                    content = '/* New stylesheet */\nbody {\n    font-family: Arial, sans-serif;\n}\n'
                elif ext == 'js':
                    content = '// New JavaScript file\nconsole.log("Hello from new file");\n'
                else:
                    content = ''

                processor.save_file_content(filename, content)
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'Brak aktywnego pliku'}), 400

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/preview')
    def preview():
        try:
            current_file = app.config.get('CURRENT_FILE')
            if not current_file:
                return '<html><body><h1>Brak aktywnego pliku</h1><p>Użyj <code>qra edit filename.mhtml</code></p></body></html>'

            processor = MHTMLProcessor(current_file)
            files = processor.get_qra_files()

            # Znajdź główny plik HTML
            html_file = None
            for file in files:
                if file['name'].endswith('.html') or file['type'] == 'html':
                    html_file = file
                    break

            if not html_file:
                return '<html><body><h1>Brak pliku HTML</h1><p>Dodaj plik .html aby zobaczyć podgląd</p></body></html>'

            return html_file['content']

        except Exception as e:
            return f'<html><body><h1>Błąd podglądu</h1><p>{str(e)}</p></body></html>'

    # Start auto-save when app starts
    @app.before_first_request
    def start_auto_save():
        current_file = app.config.get('CURRENT_FILE')
        if current_file:
            processor = MHTMLProcessor(current_file)
            auto_save_manager.start(processor)

    return app