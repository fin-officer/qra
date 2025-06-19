from flask import Flask, render_template_string, request, jsonify, send_from_directory
import threading
import time
from .core import MHTMLProcessor
import os, json

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
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/6.65.7/codemirror.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/6.65.7/theme/monokai.min.css">
    <link rel="stylesheet" href="/qra/styles.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/6.65.7/codemirror.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/6.65.7/mode/xml/xml.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/6.65.7/mode/css/css.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/6.65.7/mode/javascript/javascript.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/6.65.7/mode/htmlmixed/htmlmixed.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/6.65.7/mode/markdown/markdown.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/6.65.7/mode/python/python.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/6.65.7/mode/sql/sql.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/6.65.7/mode/yaml/yaml.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/6.65.7/mode/php/php.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/6.65.7/addon/edit/closebrackets.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/6.65.7/addon/edit/matchbrackets.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/6.65.7/addon/selection/active-line.min.js"></script>
    <script src="/qra/script.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
               background: #1e1e1e; color: #d4d4d4; height: 100vh; overflow: hidden; }

        .container { display: flex; height: 100vh; }
        .sidebar { width: 300px; background: #252526; border-right: 1px solid #3e3e42; 
                   display: flex; flex-direction: column; }
        .main-content { flex: 1; display: flex; flex-direction: column; }

        .header { background: #2d2d30; padding: 10px 20px; border-bottom: 1px solid #3e3e42;
                  display: flex; justify-content: space-between; align-items: center; }
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
                         font-size: 13px; color: #cccccc; display: flex; justify-content: space-between; align-items: center; }

        .editor-container { flex: 1; position: relative; }
        .CodeMirror { height: 100% !important; font-size: 14px; }

        #preview-frame { width: 100%; height: 100%; border: none; background: white; }

        .controls { background: #2d2d30; padding: 10px 20px; border-top: 1px solid #3e3e42;
                    display: flex; gap: 10px; }
        .btn { background: #0e639c; color: white; border: none; padding: 8px 16px; 
               border-radius: 4px; cursor: pointer; font-size: 13px; }
        .btn:hover { background: #1177bb; }
        .btn.secondary { background: #5a5a5a; }
        .btn.secondary:hover { background: #6a6a6a; }

        .file-type-badge { 
            background: #007acc; color: white; padding: 2px 6px; border-radius: 3px; 
            font-size: 10px; font-weight: bold; text-transform: uppercase;
        }
        .file-type-badge.html { background: #e34c26; }
        .file-type-badge.css { background: #1572b6; }
        .file-type-badge.javascript { background: #f1e05a; color: #333; }
        .file-type-badge.python { background: #3572a5; }
        .file-type-badge.markdown { background: #083fa1; }
        .file-type-badge.json { background: #292929; }
        .file-type-badge.xml { background: #0060ac; }

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
                        <span>Wybierz plik do edycji</span>
                        <span id="file-type-indicator"></span>
                    </div>
                    <div class="editor-container" id="editor-container">
                        <textarea id="code-editor" style="display: none;"></textarea>
                    </div>
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
        let editor = null;

        // Inicjalizuj CodeMirror
        function initializeEditor() {
            const textarea = document.getElementById('code-editor');
            editor = CodeMirror.fromTextArea(textarea, {
                lineNumbers: true,
                theme: 'monokai',
                autoCloseBrackets: true,
                matchBrackets: true,
                styleActiveLine: true,
                indentUnit: 2,
                tabSize: 2,
                lineWrapping: true
            });

            editor.on('change', function() {
                updateSaveStatus('modified');
                scheduleAutoSave();
            });
        }

        // Ustaw tryb edytora na podstawie typu pliku
        function setEditorMode(fileType) {
            const modeMap = {
                'html': 'htmlmixed',
                'css': 'css',
                'javascript': 'javascript',
                'json': {name: 'javascript', json: true},
                'xml': 'xml',
                'markdown': 'markdown',
                'python': 'python',
                'sql': 'sql',
                'yaml': 'yaml',
                'php': 'php'
            };

            const mode = modeMap[fileType] || 'text';
            editor.setOption('mode', mode);
        }

        // Załaduj listę plików
        function loadFiles() {
            fetch('/api/files')
            .then(response => response.json())
            .then(data => {
                files = data.files;
                renderFileList();
                if (files.length > 0 && !currentFile) {
                    selectFile(files[0].name);
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
                        <span class="file-type-badge ${file.type}">${file.type}</span>
                    </div>
                    <div class="file-size">${formatFileSize(file.size)}</div>
                </div>
            `).join('');
        }

        function selectFile(filename) {
            fetch(`/api/file?name=${encodeURIComponent(filename)}`)
                .then(res => res.json())
                .then(data => {
                    editor.setValue(data.content || "");
                    currentFile = filename;
                    updateEditorHeader(filename);
                    setEditorMode(getFileType(filename));
                    // If HTML, reload preview
                    if (getFileType(filename) === 'html') {
                        document.getElementById('preview-frame').src = '/preview?' + Date.now();
                    }
                });
        }

        function updateEditorHeader(filename) {
            document.getElementById('editor-header').innerHTML =
                `<span>${filename}</span><span id="file-type-indicator">${getFileType(filename)}</span>`;
        }

        function getFileType(filename) {
            const ext = filename.split('.').pop().toLowerCase();
            const map = {
                'js': 'javascript',
                'py': 'python',
                'md': 'markdown',
                'json': 'json',
                'html': 'html',
                'css': 'css',
                'xml': 'xml',
                'php': 'php',
                'sql': 'sql',
                'yml': 'yaml',
                'yaml': 'yaml'
            };
            return map[ext] || ext;
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
            }, 2000);
        }

        function saveCurrentFile() {
            if (!currentFile || !editor) return;

            const content = editor.getValue();
            fetch('/api/save-file', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    filename: currentFile,
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
                    alert('Wszystkie pliki zostały zapisane do MHTML/EML');
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
        document.addEventListener('DOMContentLoaded', function() {
            initializeEditor();
            loadFiles();
        });

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
        # Serve the main editor interface
        return EDITOR_TEMPLATE

    @app.route('/qra/<path:filename>')
    def serve_qra_file(filename):
        return send_from_directory('.qra', filename)

    @app.route('/api/files')
    def api_files():
        # List files in .qra/ directory with metadata
        qra_dir = '.qra'
        files = []
        for fname in os.listdir(qra_dir):
            fpath = os.path.join(qra_dir, fname)
            if os.path.isfile(fpath):
                ext = fname.split('.')[-1].lower() if '.' in fname else ''
                size = os.path.getsize(fpath)
                files.append({
                    'name': fname,
                    'type': ext,
                    'size': size
                })
        return json.dumps({'files': files}), 200, {'Content-Type': 'application/json'}

    @app.route('/api/file')
    def api_file():
        filename = request.args.get('name')
        if not filename:
            return 'Missing filename', 400
        fpath = os.path.join('.qra', filename)
        if not os.path.isfile(fpath):
            return 'File not found', 404
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return jsonify({'name': filename, 'content': content})

    @app.route('/preview')
    def preview():
        # Serve the main HTML part for preview
        for html_name in ['html_body.html', 'index.html']:
            html_path = os.path.join('.qra', html_name)
            if os.path.exists(html_path):
                with open(html_path, 'r', encoding='utf-8') as f:
                    return f.read(), 200, {'Content-Type': 'text/html'}
        return 'No preview available', 404

    # Return the Flask app object instead of the HTML template
    return app