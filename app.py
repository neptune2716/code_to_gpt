from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import json
import sys
import subprocess
import shutil

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
    except:
        pref = {}
    selected_exts = pref.get('selected_extensions', [])
    known_exts = pref.get('known_extensions', [])
    hidden_exts = pref.get('hidden_extensions', [])
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
        # Filter files by extension: use selected_exts if set, else known_exts if available
        if not is_dir:
            ext = os.path.splitext(name)[1]
            # Skip hidden-defined extensions
            if ext in hidden_exts:
                continue
            if selected_exts:
                if ext not in selected_exts:
                    continue
            elif known_exts:
                if ext not in known_exts:
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
    # Load or initialize preferences
    try:
        with open(PREF_FILE, 'r', encoding='utf-8') as f:
            pref = json.load(f)
    except:
        pref = {}
    # Populate known_extensions if empty
    if not pref.get('known_extensions'):
        exts = set()
        for root, _, files in os.walk(os.getcwd()):
            for fn in files:
                ext = os.path.splitext(fn)[1]
                if ext:
                    exts.add(ext)
        pref['known_extensions'] = sorted(exts)
        pref.setdefault('selected_extensions', [])
        pref.setdefault('hidden_extensions', [])
        json.dump(pref, open(PREF_FILE, 'w', encoding='utf-8'), indent=2)
    # Read favorites
    try:
        with open(FAV_FILE, 'r', encoding='utf-8') as f:
            fav = json.load(f)
    except:
        fav = []
    # Return option sets
    return jsonify(
        known_extensions=[e for e in pref.get('known_extensions', []) if e not in pref.get('hidden_extensions', [])],
        selected_extensions=pref.get('selected_extensions', []),
        favorites=fav,
        hidden_extensions=pref.get('hidden_extensions', [])
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

# Add endpoint for hidden_extensions
@app.route('/api/options/hidden_extensions', methods=['POST'])
def update_hidden_extensions():
    data = request.get_json()
    hidden_exts = data.get('hidden_extensions', [])
    try:
        with open(PREF_FILE, 'r', encoding='utf-8') as f:
            pref = json.load(f)
        pref['hidden_extensions'] = hidden_exts
        json.dump(pref, open(PREF_FILE, 'w', encoding='utf-8'), indent=2)
        return jsonify(success=True)
    except Exception:
        return jsonify(success=False), 500

# Helper function to build tree structure string (similar to Tkinter version)
def build_tree_string(path, hidden_items, show_hidden, excluded_dirs):
    lines = []
    # Normalize excluded dirs for comparison
    excluded_dirs_norm = {os.path.normpath(d) for d in excluded_dirs}

    def recurse(current_path, prefix=''):
        try:
            # Filter excluded directories early
            base_name = os.path.basename(current_path)
            if base_name in excluded_dirs_norm or base_name.startswith('.'): # Also exclude hidden files/dirs by default
                 # Check if it's explicitly in hidden_items OR starts with '.' and show_hidden is false
                 norm_current_path = os.path.normpath(current_path)
                 is_hidden_explicitly = norm_current_path in hidden_items
                 is_hidden_convention = base_name.startswith('.')

                 if not show_hidden and (is_hidden_explicitly or is_hidden_convention):
                     return # Skip if hidden and not showing hidden
                 # If showing hidden, we continue but might style it later if needed

            items = os.listdir(current_path)
            items.sort()
        except (PermissionError, FileNotFoundError):
            return

        # Separate dirs and files to list dirs first (optional, for consistency)
        dirs = sorted([item for item in items if os.path.isdir(os.path.join(current_path, item))])
        files = sorted([item for item in items if not os.path.isdir(os.path.join(current_path, item))])
        sorted_items = dirs + files # List directories first

        for idx, item in enumerate(sorted_items):
            abs_path = os.path.join(current_path, item)
            norm_abs_path = os.path.normpath(abs_path)
            base_item_name = os.path.basename(item)

            # Skip excluded dirs
            if base_item_name in excluded_dirs_norm:
                continue

            # Check if hidden
            is_hidden_explicitly = norm_abs_path in hidden_items
            is_hidden_convention = base_item_name.startswith('.')
            is_hidden = is_hidden_explicitly or is_hidden_convention

            if not show_hidden and is_hidden:
                continue # Skip if hidden and not showing hidden

            # Determine connector
            is_last = (idx == len(sorted_items) - 1)
            connector = '└── ' if is_last else '├── '
            line = f"{prefix}{connector}{item}"
            if show_hidden and is_hidden:
                 line += " (hidden)" # Mark hidden items if shown
            lines.append(line)

            if os.path.isdir(abs_path):
                extension = '    ' if is_last else '│   ' # Corrected extension
                recurse(abs_path, prefix + extension)

    # Start recursion from the root path provided
    root_name = os.path.basename(path)
    lines.append(root_name) # Add the root directory name itself
    recurse(path, prefix='') # Start recursion for contents
    return '\n'.join(lines)

@app.route('/api/tree_structure')
def get_tree_structure():
    """Endpoint to get the formatted tree structure string."""
    base_path = os.getcwd() # Or get from a config/request param if needed
    show_hidden = request.args.get('showHidden', 'false').lower() == 'true'

    # Load hidden items
    try:
        with open(HIDE_FILE, 'r', encoding='utf-8') as f:
            hidden_set = set(json.load(f))
    except:
        hidden_set = set()

    # Define excluded dirs (consider making this configurable)
    excluded_dirs = ['node_modules', '__pycache__', '.git', '.venv', 'venv']

    try:
        tree_str = build_tree_string(base_path, hidden_set, show_hidden, excluded_dirs)
        return jsonify(tree=tree_str)
    except Exception as e:
        app.logger.error(f"Error generating tree structure: {e}")
        return jsonify(tree='// Error generating tree structure'), 500

# Helper function to update JSON list file
def update_json_list_file(filepath, old_item=None, new_item=None, remove_item=None):
    items = set()
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                items = set(json.load(f))
    except (json.JSONDecodeError, IOError) as e:
        app.logger.warning(f"Could not read JSON file {filepath}: {e}")
        items = set() # Reset on error

    updated = False
    if remove_item and remove_item in items:
        items.remove(remove_item)
        updated = True
    if old_item and old_item in items:
        items.remove(old_item)
        if new_item:
            items.add(new_item)
        updated = True
    elif new_item and not old_item and new_item not in items: # For adding new items if needed later
        items.add(new_item)
        updated = True

    if updated:
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(sorted(list(items)), f, ensure_ascii=False, indent=2)
            app.logger.info(f"Updated JSON file: {filepath}")
        except IOError as e:
            app.logger.error(f"Could not write JSON file {filepath}: {e}")

@app.route('/api/fs/rename', methods=['POST'])
def rename_item():
    data = request.get_json()
    old_path = data.get('oldPath')
    new_name = data.get('newName')
    base_dir = os.getcwd()

    if not old_path or not new_name:
        return jsonify(success=False, message="Missing path or new name."), 400

    # Security: Ensure paths are within the base directory
    norm_old_path = os.path.normpath(os.path.join(base_dir, old_path.replace(base_dir, '').lstrip(os.sep)))
    if not norm_old_path.startswith(base_dir):
        return jsonify(success=False, message="Invalid path."), 400

    # Prevent renaming the root itself or navigating up
    if norm_old_path == base_dir or '..' in new_name or '/' in new_name or '\\' in new_name:
        return jsonify(success=False, message="Invalid new name."), 400

    new_path = os.path.join(os.path.dirname(norm_old_path), new_name)

    if not os.path.exists(norm_old_path):
        return jsonify(success=False, message="Source path does not exist."), 404
    if os.path.exists(new_path):
        return jsonify(success=False, message="Target name already exists."), 409

    try:
        os.rename(norm_old_path, new_path)
        app.logger.info(f"Renamed '{norm_old_path}' to '{new_path}'")

        # Update favorites and hidden items
        update_json_list_file(FAV_FILE, old_item=norm_old_path, new_item=new_path)
        update_json_list_file(HIDE_FILE, old_item=norm_old_path, new_item=new_path)

        # Return the new path relative to the base_dir for frontend update
        relative_new_path = os.path.relpath(new_path, base_dir)
        return jsonify(success=True, newPath=relative_new_path.replace(os.sep, '/')) # Use forward slashes for consistency

    except Exception as e:
        app.logger.error(f"Error renaming '{norm_old_path}' to '{new_path}': {e}")
        return jsonify(success=False, message=f"Error renaming: {e}"), 500

@app.route('/api/fs/delete', methods=['POST'])
def delete_item():
    data = request.get_json()
    path_to_delete = data.get('path')
    base_dir = os.getcwd()

    if not path_to_delete:
        return jsonify(success=False, message="Missing path."), 400

    # Security: Ensure path is within the base directory
    norm_path = os.path.normpath(os.path.join(base_dir, path_to_delete.replace(base_dir, '').lstrip(os.sep)))
    if not norm_path.startswith(base_dir) or norm_path == base_dir:
        return jsonify(success=False, message="Invalid path."), 400

    if not os.path.exists(norm_path):
        # If it doesn't exist, still try to remove from JSON files just in case
        update_json_list_file(FAV_FILE, remove_item=norm_path)
        update_json_list_file(HIDE_FILE, remove_item=norm_path)
        return jsonify(success=False, message="Path does not exist."), 404

    try:
        if os.path.isdir(norm_path):
            shutil.rmtree(norm_path)
            app.logger.info(f"Deleted directory: {norm_path}")
        else:
            os.remove(norm_path)
            app.logger.info(f"Deleted file: {norm_path}")

        # Update favorites and hidden items
        update_json_list_file(FAV_FILE, remove_item=norm_path)
        update_json_list_file(HIDE_FILE, remove_item=norm_path)

        return jsonify(success=True)
    except Exception as e:
        app.logger.error(f"Error deleting '{norm_path}': {e}")
        return jsonify(success=False, message=f"Error deleting: {e}"), 500

if __name__ == '__main__':
    app.run(debug=True)
