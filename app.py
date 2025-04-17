from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import json

app = Flask(__name__)

# Data directory
DATA_DIR = os.path.join(os.getcwd(), 'data')
# JSON config paths
PREF_FILE = os.path.join(DATA_DIR, 'preferences.json')
FAV_FILE = os.path.join(DATA_DIR, 'favorites.json')
HIDE_FILE = os.path.join(DATA_DIR, 'hidden_items.json')

# Serve the favicon
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static', 'images'), 'icone.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/')
def index():
    # Pass base directory path for tree initialization
    return render_template('index.html', baseDir=os.getcwd())

@app.route('/api/tree')
def get_tree():
    # Directory listing with extension and hidden filtering
    path = request.args.get('path', os.getcwd())
    # Convert URL-forwarded slashes to OS separator and normalize
    path = path.replace('/', os.sep)
    path = os.path.normpath(path)
    show_hidden = request.args.get('showHidden', 'false').lower() == 'true'
    # Load preferences and filters
    try:
        pref = json.load(open(PREF_FILE, 'r', encoding='utf-8'))
        selected_exts = pref.get('selected_extensions', [])
    except:
        selected_exts = []
    try:
        hidden = json.load(open(HIDE_FILE, 'r', encoding='utf-8'))
    except:
        hidden = []
    items = []
    try:
        entries = os.listdir(path)
    except Exception as e:
        app.logger.error(f"get_tree: cannot list {path}: {e}")
        return jsonify(items)
    for name in entries:
        full = os.path.join(path, name)
        is_dir = os.path.isdir(full)
        # Skip hidden unless showing
        if not show_hidden and full in hidden:
            continue
        # Filter files by extension
        if not is_dir and selected_exts and os.path.splitext(name)[1] not in selected_exts:
            continue
        node = {'text': name, 'id': full, 'children': is_dir}
        # Mark hidden state
        if show_hidden and full in hidden:
            node['state'] = {'disabled': True}
        items.append(node)
    return jsonify(items)

@app.route('/api/preview')
def preview_file():
    path = request.args.get('path', '')
    # Normalize and ensure file is within BASE_DIR
    path = os.path.normpath(path)
    if not path.startswith(os.getcwd()) or not os.path.isfile(path):
        return jsonify(content=''), 400
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = f.read()
    except Exception:
        data = ''
    return jsonify(content=data)

@app.route('/api/select', methods=['POST'])
def select_item():
    # TODO: toggle selection in memory or persist
    data = request.get_json()
    return jsonify(success=True, data=data)

@app.route('/api/code')
def get_code():
    # Read selected file paths from query params
    paths_json = request.args.get('paths', '[]')
    try:
        paths = json.loads(paths_json)
    except Exception:
        paths = []
    code_pieces = []
    for p in paths:
        # only include files within BASE_DIR
        if not p.startswith(os.getcwd()):
            continue
        if os.path.isfile(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    content = f.read()
                code_pieces.append(f"// === {p} ===\n{content}")
            except Exception:
                pass
    full_code = "\n\n".join(code_pieces)
    return jsonify(code=full_code)

@app.route('/api/options')
def get_options():
    # Return known extensions, selected extensions, and favorites
    try:
        with open(PREF_FILE, 'r', encoding='utf-8') as f:
            pref = json.load(f)
    except:
        pref = {}
    try:
        with open(FAV_FILE, 'r', encoding='utf-8') as f:
            fav = json.load(f)
    except:
        fav = []
    return jsonify(
        known_extensions=pref.get('known_extensions', []),
        selected_extensions=pref.get('selected_extensions', []),
        favorites=fav
    )

@app.route('/api/options/extensions', methods=['POST'])
def update_extensions():
    data = request.get_json()
    exts = data.get('extensions', [])
    try:
        pref = {}
        if os.path.exists(PREF_FILE):
            pref = json.load(open(PREF_FILE, 'r', encoding='utf-8'))
        pref['selected_extensions'] = exts
        json.dump(pref, open(PREF_FILE, 'w', encoding='utf-8'), indent=2)
        return jsonify(success=True)
    except:
        return jsonify(success=False), 500

@app.route('/api/options/favorites', methods=['POST'])
def update_favorites():
    data = request.get_json()
    favs = data.get('favorites', [])
    try:
        json.dump(favs, open(FAV_FILE, 'w', encoding='utf-8'), indent=2)
        return jsonify(success=True)
    except:
        return jsonify(success=False), 500

@app.route('/api/options/hidden', methods=['GET'])
def get_hidden():
    try:
        hidden = json.load(open(HIDE_FILE, 'r', encoding='utf-8'))
    except:
        hidden = []
    return jsonify(hidden)

@app.route('/api/options/hidden', methods=['POST'])
def update_hidden():
    data = request.get_json()
    hidden = data.get('hidden', [])
    try:
        json.dump(hidden, open(HIDE_FILE, 'w', encoding='utf-8'), indent=2)
        return jsonify(success=True)
    except:
        return jsonify(success=False), 500

if __name__ == '__main__':
    app.run(debug=True)
