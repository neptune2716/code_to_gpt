import os
import sys
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from ttkbootstrap import Style
from PIL import Image, ImageTk
import shutil
import subprocess
import logging

from config import ConfigManager
from favorites import FavoritesManager
from hidden import HiddenItemsManager
from search import SearchManager

class ProjectExplorerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Explorateur de Projet")
        self.root.geometry("1400x800")

        self.config_manager = ConfigManager()
        self.favorites_manager = FavoritesManager()
        self.hidden_manager = HiddenItemsManager()

        self.path_var = tk.StringVar(value=self.config_manager.last_path)
        self.current_theme = self.config_manager.current_theme
        self.is_fullscreen = self.config_manager.is_fullscreen
        self.window_geometry = self.config_manager.window_geometry
        self.selected_extensions = self.config_manager.selected_extensions
        self.hidden_items = self.hidden_manager.hidden_items
        self.favorites = self.favorites_manager.favorites

        style = Style(theme=self.current_theme)
        style.configure('Treeview', rowheight=25)
        self.root.attributes('-fullscreen', self.is_fullscreen)
        if self.window_geometry:
            self.root.geometry(self.window_geometry)

        self.ext_vars = {}
        self.excluded_dirs = ['node_modules', '__pycache__', '.git', '__svn__', '__hg__', 'Google Drive']
        self.history_stack = []
        self.queue = queue.Queue()

        self.folder_icon, self.file_icon = self.load_icons('icons/folder_icon.png', 'icons/file_icon.png')

        self.create_widgets()
        self.bind_events()

        if self.path_var.get():
            self.on_path_change()

        self.root.after(100, self.process_queue)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_icons(self, folder_path, file_path, size=(16, 16)):
        try:
            folder_image = Image.open(folder_path).resize(size, Image.LANCZOS)
            file_image = Image.open(file_path).resize(size, Image.LANCZOS)
            return ImageTk.PhotoImage(folder_image), ImageTk.PhotoImage(file_image)
        except Exception as e:
            logging.warning(f"Impossible de charger les icônes: {e}")
            return None, None

    def create_widgets(self):
        path_frame = ttk.Frame(self.root, padding="10 10 10 10")
        path_frame.grid(row=0, column=0, columnspan=7, sticky='ew')
        path_frame.columnconfigure(1, weight=1)

        ttk.Label(path_frame, text="Chemin du projet:").grid(row=0, column=0, sticky='w')
        self.path_entry = ttk.Entry(path_frame, textvariable=self.path_var)
        self.path_entry.grid(row=0, column=1, sticky='ew', padx=5)
        ttk.Button(path_frame, text="Parcourir", command=self.on_browse).grid(row=0, column=2)

        self.back_button = ttk.Button(path_frame, text="Retour", command=self.on_back, state='disabled')
        self.back_button.grid(row=0, column=3, padx=5)

        hide_button = ttk.Button(path_frame, text="Masquer", command=self.hide_selected_items)
        hide_button.grid(row=0, column=4, padx=5)

        show_hidden_button = ttk.Button(path_frame, text="Afficher Masqués", command=self.show_hidden_items)
        show_hidden_button.grid(row=0, column=5, padx=5)

        self.status_var = tk.StringVar(value="Prêt")
        self.progress = ttk.Progressbar(self.root, orient='horizontal', mode='determinate')
        self.progress.grid(row=1, column=0, columnspan=7, sticky='ew', padx=10)
        self.status_label = ttk.Label(self.root, textvariable=self.status_var)
        self.status_label.grid(row=1, column=6, sticky='e', padx=10)

        self.loading_label = ttk.Label(self.root, text="Chargement en cours...", foreground="blue")
        self.loading_label.grid(row=10, column=0, columnspan=7, pady=5)
        self.loading_label.grid_remove()

        simple_search_frame = ttk.Frame(self.root)
        simple_search_frame.grid(row=2, column=0, columnspan=7, sticky='ew', padx=10, pady=5)
        simple_search_frame.columnconfigure(1, weight=1)

        ttk.Label(simple_search_frame, text="Rechercher:").grid(row=0, column=0, sticky='w')
        self.simple_search_var = tk.StringVar()
        self.simple_search_entry = ttk.Entry(simple_search_frame, textvariable=self.simple_search_var)
        self.simple_search_entry.grid(row=0, column=1, sticky='ew', padx=5)

        self.toggle_advanced_button = ttk.Button(simple_search_frame, text="Recherche Avancée", command=self.toggle_advanced_search)
        self.toggle_advanced_button.grid(row=0, column=2, padx=5)

        self.advanced_search_frame = ttk.LabelFrame(self.root, text="Recherche Avancée", padding="10 10 10 10")
        self.advanced_search_frame.grid(row=3, column=0, columnspan=7, sticky='ew', padx=10)
        self.advanced_search_frame.columnconfigure(1, weight=1)
        self.advanced_search_frame.grid_remove()

        ttk.Label(self.advanced_search_frame, text="Nom contient:").grid(row=0, column=0, sticky='w', pady=2)
        self.search_name_var = tk.StringVar()
        self.search_name_entry = ttk.Entry(self.advanced_search_frame, textvariable=self.search_name_var)
        self.search_name_entry.grid(row=0, column=1, sticky='ew', padx=5, pady=2)

        ttk.Label(self.advanced_search_frame, text="Type de Fichier:").grid(row=1, column=0, sticky='w', pady=2)
        self.search_ext_var = tk.StringVar()
        self.search_ext_entry = ttk.Entry(self.advanced_search_frame, textvariable=self.search_ext_var)
        self.search_ext_entry.grid(row=1, column=1, sticky='ew', padx=5, pady=2)
        ttk.Label(self.advanced_search_frame, text="(ex: .py, .txt)").grid(row=1, column=2, sticky='w', pady=2)

        ttk.Label(self.advanced_search_frame, text="Date de Modification après:").grid(row=2, column=0, sticky='w', pady=2)
        self.search_date_var = tk.StringVar()
        self.search_date_entry = ttk.Entry(self.advanced_search_frame, textvariable=self.search_date_var)
        self.search_date_entry.grid(row=2, column=1, sticky='ew', padx=5, pady=2)
        ttk.Label(self.advanced_search_frame, text="(format: YYYY-MM-DD)").grid(row=2, column=2, sticky='w', pady=2)

        ttk.Button(self.advanced_search_frame, text="Rechercher", command=self.on_advanced_search).grid(row=3, column=1, sticky='e', pady=5)

        self.root.columnconfigure(0, weight=3)
        self.root.columnconfigure(3, weight=2)
        self.root.rowconfigure(4, weight=3)
        self.root.rowconfigure(8, weight=2)

        tree_label = ttk.Label(self.root, text="Architecture du projet:")
        tree_label.grid(row=3, column=0, sticky='nw', padx=10, pady=(10, 0))
        tree_frame = ttk.Frame(self.root)
        tree_frame.grid(row=4, column=0, columnspan=3, sticky='nsew', padx=10, pady=5)
        self.tree_scroll = ttk.Scrollbar(tree_frame)
        self.tree_scroll.pack(side='right', fill='y')
        self.tree = ttk.Treeview(tree_frame, yscrollcommand=self.tree_scroll.set, selectmode="extended")
        self.tree.pack(fill='both', expand=True)
        self.tree_scroll.config(command=self.tree.yview)
        self.tree.heading('#0', text='Nom', anchor='w')
        self.tree.column('#0', stretch=True)
        self.tree.tag_configure('hidden', foreground='grey')

        ext_label = ttk.Label(self.root, text="Sélectionnez les extensions:")
        ext_label.grid(row=3, column=3, sticky='nw', padx=10, pady=(10, 0))
        self.ext_frame = ttk.Frame(self.root)
        self.ext_frame.grid(row=4, column=3, sticky='nw', padx=10, pady=5)

        ext_button_frame = ttk.Frame(self.root)
        ext_button_frame.grid(row=5, column=3, sticky='nw', padx=10)
        ttk.Button(ext_button_frame, text="Tout sélectionner", command=self.select_all_exts).pack(side='left', padx=5)
        ttk.Button(ext_button_frame, text="Tout désélectionner", command=self.deselect_all_exts).pack(side='left', padx=5)

        generate_button = ttk.Button(self.root, text="Générer le code", command=self.on_generate_code)
        generate_button.grid(row=6, column=3, sticky='e', padx=10, pady=5)

        code_label = ttk.Label(self.root, text="Code des fichiers sélectionnés:")
        code_label.grid(row=7, column=0, sticky='nw', padx=10, pady=(10, 0))
        self.code_text = ScrolledText(self.root, height=15, state='disabled')
        self.code_text.grid(row=8, column=0, columnspan=7, sticky='nsew', padx=10, pady=5)

        button_frame = ttk.Frame(self.root)
        button_frame.grid(row=9, column=0, columnspan=7, pady=10)
        ttk.Button(button_frame, text="Copier l'arborescence", command=self.copy_tree).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Copier le code", command=self.copy_code).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Tout copier", command=self.copy_all).pack(side='left', padx=5)

        favorites_label = ttk.Label(self.root, text="Favoris:")
        favorites_label.grid(row=3, column=4, sticky='nw', padx=10, pady=(10, 0))
        favorites_frame = ttk.Frame(self.root)
        favorites_frame.grid(row=4, column=4, rowspan=3, sticky='nsew', padx=10, pady=5)
        self.favorites_scroll = ttk.Scrollbar(favorites_frame)
        self.favorites_scroll.pack(side='right', fill='y')
        self.favorites_listbox = tk.Listbox(favorites_frame, yscrollcommand=self.favorites_scroll.set, selectmode='single')
        self.favorites_listbox.pack(side='left', fill='both', expand=True)
        self.favorites_scroll.config(command=self.favorites_listbox.yview)

        fav_button_frame = ttk.Frame(self.root)
        fav_button_frame.grid(row=7, column=4, sticky='n', padx=10, pady=5)
        ttk.Button(fav_button_frame, text="Ouvrir le Favori", command=self.open_selected_favorite).pack(pady=2)
        ttk.Button(fav_button_frame, text="Supprimer le Favori", command=self.remove_from_favorites).pack(pady=2)

        self.root.drop_target_register('DND_Files')
        self.root.dnd_bind('<<Drop>>', self.on_drop)

        self.create_context_menu()
        self.update_favorites_listbox()

        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)
        view_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label='Affichage', menu=view_menu)
        view_menu.add_command(label='Basculer Thème Sombre', command=self.toggle_theme)
        view_menu.add_command(label='Plein Écran', command=self.toggle_fullscreen)

    def bind_events(self):
        self.path_entry.bind('<Return>', self.on_path_change)
        self.root.bind('<Control-f>', lambda event: self.search_name_entry.focus_set())
        self.tree.bind('<<TreeviewOpen>>', self.on_treeview_open)
        self.tree.bind('<Double-1>', self.on_treeview_double_click)
        self.root.bind('<Control-o>', lambda event: self.on_browse())
        self.favorites_listbox.bind('<Double-1>', lambda event: self.open_selected_favorite())

    def create_context_menu(self):
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Ouvrir", command=self.open_item)
        self.context_menu.add_command(label="Renommer", command=self.rename_item)
        self.context_menu.add_command(label="Supprimer", command=self.delete_item)
        self.context_menu.add_command(label="Copier le Chemin", command=self.copy_path)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Ajouter aux Favoris", command=self.add_to_favorites)
        self.context_menu.add_command(label="Masquer", command=self.hide_selected_items)

        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Button-2>", self.show_context_menu)

    # Méthodes factorisées liées aux favoris, éléments masqués, recherche, etc.
    def hide_selected_items(self):
        selected_items = self.tree.selection()
        for item in selected_items:
            path = self.tree.item(item, 'values')[0]
            self.hidden_manager.add_hidden(path)
        self.hidden_items = self.hidden_manager.hidden_items
        self.refresh_tree()

    def show_hidden_items(self):
        hidden_window = tk.Toplevel(self.root)
        hidden_window.title("Éléments Masqués")
        hidden_window.geometry("400x300")

        hidden_listbox = tk.Listbox(hidden_window)
        hidden_listbox.pack(fill='both', expand=True)

        for item in self.hidden_items:
            hidden_listbox.insert(tk.END, item)

        def unhide_selected():
            selected = hidden_listbox.curselection()
            for index in selected[::-1]:
                item = hidden_listbox.get(index)
                self.hidden_manager.remove_hidden(item)
                hidden_listbox.delete(index)
            self.hidden_items = self.hidden_manager.hidden_items
            self.refresh_tree()

        unhide_button = ttk.Button(hidden_window, text="Rétablir", command=unhide_selected)
        unhide_button.pack(pady=5)

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.path_to_item = {}
        root_path = self.path_var.get()
        threading.Thread(target=self.insert_tree_items, args=('', root_path), daemon=True).start()

    def open_item(self):
        selected_items = self.tree.selection()
        for item in selected_items:
            path = self.tree.item(item, 'values')[0]
            try:
                if os.name == 'nt':
                    os.startfile(path)
                elif sys.platform == 'darwin':
                    subprocess.run(['open', path], check=True)
                else:
                    subprocess.run(['xdg-open', path], check=True)
            except Exception as e:
                logging.error(f"Erreur d'ouverture: {e}")
                messagebox.showerror("Erreur", f"Erreur: {e}")

    def rename_item(self):
        selected_item = self.tree.selection()
        if selected_item:
            item = selected_item[0]
            path = self.tree.item(item, 'values')[0]
            new_name = simpledialog.askstring("Renommer", "Nouveau nom:", initialvalue=os.path.basename(path))
            if new_name:
                new_path = os.path.join(os.path.dirname(path), new_name)
                if os.path.exists(new_path):
                    messagebox.showerror("Erreur", f"Le nom '{new_name}' existe déjà.")
                    return
                try:
                    os.rename(path, new_path)
                    self.tree.item(item, text=new_name, values=[new_path])
                    if path in self.favorites:
                        self.favorites_manager.remove_favorite(path)
                        self.favorites_manager.add_favorite(new_path)
                        self.favorites = self.favorites_manager.favorites
                        self.update_favorites_listbox()
                except Exception as e:
                    messagebox.showerror("Erreur", f"Impossible: {e}")

    def delete_item(self):
        selected_item = self.tree.selection()
        if selected_item:
            confirm = messagebox.askyesno("Confirmer", "Supprimer cet élément ?")
            if confirm:
                for item in selected_item:
                    path = self.tree.item(item, 'values')[0]
                    try:
                        if os.path.isdir(path):
                            shutil.rmtree(path)
                        else:
                            os.remove(path)
                        self.tree.delete(item)
                        if path in self.favorites:
                            self.favorites_manager.remove_favorite(path)
                            self.favorites = self.favorites_manager.favorites
                            self.update_favorites_listbox()
                    except Exception as e:
                        messagebox.showerror("Erreur", f"Erreur: {e}")

    def copy_path(self):
        selected_item = self.tree.selection()
        if selected_item:
            paths = [self.tree.item(item, 'values')[0] for item in selected_item]
            paths_str = '\n'.join(paths)
            self.root.clipboard_clear()
            self.root.clipboard_append(paths_str)
            messagebox.showinfo("Succès", "Chemin copié.")

    def add_to_favorites(self, path=None):
        if not path:
            selected_item = self.tree.selection()
            if not selected_item:
                return
            path = self.tree.item(selected_item[0], 'values')[0]
        self.favorites_manager.add_favorite(path)
        self.favorites = self.favorites_manager.favorites
        self.update_favorites_listbox()
        messagebox.showinfo("Succès", f"'{path}' ajouté aux favoris.")

    def remove_from_favorites(self):
        selection = self.favorites_listbox.curselection()
        if selection:
            path = sorted(self.favorites)[selection[0]]
            self.favorites_manager.remove_favorite(path)
            self.favorites = self.favorites_manager.favorites
            self.update_favorites_listbox()

    def update_favorites_listbox(self):
        self.favorites_listbox.delete(0, tk.END)
        favs_sorted = sorted(self.favorites)
        for fav in favs_sorted:
            display_text = self.get_truncated_path(fav)
            self.favorites_listbox.insert(tk.END, display_text)

    def open_selected_favorite(self):
        selection = self.favorites_listbox.curselection()
        if selection:
            favs_sorted = sorted(self.favorites)
            path = favs_sorted[selection[0]]
            if not os.path.exists(path):
                self.favorites_manager.remove_favorite(path)
                self.favorites = self.favorites_manager.favorites
                self.update_favorites_listbox()
                return
            if os.path.isdir(path):
                self.history_stack.clear()
                self.back_button.config(state='disabled')
                self.path_var.set(path)
                self.on_path_change()
            else:
                parent_dir = os.path.dirname(path)
                self.history_stack.clear()
                self.back_button.config(state='disabled')
                self.path_var.set(parent_dir)
                self.on_path_change()

    def get_truncated_path(self, path, max_depth=2):
        parts = path.split(os.sep)
        if len(parts) > max_depth:
            return os.sep.join(['...'] + parts[-max_depth:])
        else:
            return path

    def copy_tree(self):
        try:
            tree_str = self.get_full_treeview_items()
            self.root.clipboard_clear()
            self.root.clipboard_append(tree_str)
            messagebox.showinfo("Succès", "Arborescence copiée.")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur: {e}")

    def get_full_treeview_items(self):
        path = self.path_var.get()
        lines = []
        def recurse(p, prefix=''):
            try:
                items = os.listdir(p)
            except:
                return
            items.sort()
            items = [i for i in items if i not in self.excluded_dirs and not self.hidden_manager.is_hidden(os.path.join(p, i))]
            for idx, item in enumerate(items):
                connector = '├── ' if idx < len(items) - 1 else '└── '
                lines.append(f"{prefix}{connector}{item}")
                abs_p = os.path.join(p, item)
                if os.path.isdir(abs_p):
                    extension = '│   ' if idx < len(items) - 1 else '    '
                    recurse(abs_p, prefix + extension)
        recurse(path)
        return '\n'.join(lines)

    def copy_code(self):
        try:
            code_str = self.code_text.get('1.0', tk.END)
            self.root.clipboard_clear()
            self.root.clipboard_append(code_str)
            messagebox.showinfo("Succès", "Code copié.")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur: {e}")

    def copy_all(self):
        try:
            tree_str = self.get_full_treeview_items()
            code_str = self.code_text.get('1.0', tk.END)
            all_str = tree_str + '\n' + code_str
            self.root.clipboard_clear()
            self.root.clipboard_append(all_str)
            messagebox.showinfo("Succès", "Arborescence et code copiés.")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur: {e}")

    def on_browse(self):
        path = filedialog.askdirectory()
        if path:
            self.history_stack.clear()
            self.back_button.config(state='disabled')
            self.path_var.set(path)
            self.on_path_change()

    def on_back(self):
        if self.history_stack:
            previous_path = self.history_stack.pop()
            self.path_var.set(previous_path)
            self.on_path_change()
            if not self.history_stack:
                self.back_button.config(state='disabled')

    def on_path_change(self, event=None):
        current_path = self.path_var.get()
        if os.path.isdir(current_path):
            self.tree.delete(*self.tree.get_children())
            self.path_to_item = {}
            self.progress['value'] = 0
            self.status_var.set("Chargement...")
            self.loading_label.grid()
            threading.Thread(target=self.build_treeview_thread, args=(current_path,), daemon=True).start()
            threading.Thread(target=self.update_extensions, args=(current_path,), daemon=True).start()
        else:
            self.tree.delete(*self.tree.get_children())
            for widget in self.ext_frame.winfo_children():
                widget.destroy()
            self.ext_vars.clear()
            self.path_to_item = {}

    def build_treeview_thread(self, path):
        try:
            self.queue.put(('progress_max', 100))
            self.queue.put(('progress_value', 0))
            self.queue.put(('status', "Chargement..."))
            self.insert_tree_items('', path)
            self.queue.put(('progress_value', 100))
            self.queue.put(('status', "Terminé"))
        except Exception as e:
            self.queue.put(('error_message', f"Erreur chargement: {e}"))

    def insert_tree_items(self, parent, path):
        try:
            items = os.listdir(path)
        except:
            return
        items.sort()
        for item in items:
            if item in self.excluded_dirs:
                continue
            abs_path = os.path.join(path, item)
            if self.hidden_manager.is_hidden(abs_path):
                continue
            is_dir = os.path.isdir(abs_path)
            self.queue.put(('insert', parent, item, abs_path, is_dir))

    def on_treeview_open(self, event):
        node = self.tree.focus()
        if not node:
            return
        children = self.tree.get_children(node)
        for child in children:
            if not self.tree.get_children(child):
                self.tree.delete(child)
        item_values = self.tree.item(node, 'values')
        if not item_values:
            return
        current_path = item_values[0]
        threading.Thread(target=self.insert_tree_items, args=(node, current_path), daemon=True).start()

    def on_treeview_double_click(self, event):
        item_id = self.tree.focus()
        item_values = self.tree.item(item_id, 'values')
        if not item_values:
            return
        path = item_values[0]
        if os.path.isdir(path):
            current_root = self.path_var.get()
            self.history_stack.append(current_root)
            self.back_button.config(state='normal')
            self.path_var.set(path)
            self.on_path_change()

    def update_extensions(self, path):
        try:
            exts = self.get_text_extensions(path)
            self.queue.put(('clear_extensions',))
            for ext in exts:
                self.queue.put(('add_extension', ext))
        except Exception as e:
            logging.error(f"Erreur extensions: {e}")

    def get_text_extensions(self, path):
        known_text = {'.txt','.py','.md','.c','.cpp','.h','.java','.js','.html','.css','.json','.xml','.csv','.ini','.cfg','.bat','.sh','.rb','.php','.pl','.yaml','.yml','.sql','.r','.go','.kt','.swift','.ts','.tsx','.jsx','.tex'}
        exts = set()
        for root_dir, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in known_text:
                    exts.add(ext)
        return sorted(exts)

    def select_all_exts(self):
        for var in self.ext_vars.values():
            var.set(True)

    def deselect_all_exts(self):
        for var in self.ext_vars.values():
            var.set(False)

    def is_hidden(self, path):
        return self.hidden_manager.is_hidden(path)

    def on_generate_code(self):
        selected_exts = [ext for ext, var in self.ext_vars.items() if var.get()]
        path = self.path_var.get()
        self.code_text.configure(state='normal')
        self.code_text.delete('1.0', tk.END)
        if not selected_exts:
            messagebox.showwarning("Avertissement", "Aucune extension sélectionnée.")
            self.code_text.configure(state='disabled')
            return
        threading.Thread(target=self.generate_code_thread, args=(path, selected_exts), daemon=True).start()

    def generate_code_thread(self, path, selected_exts):
        try:
            self.queue.put(('status', "Génération du code..."))
            self.queue.put(('progress_max', 100))
            self.queue.put(('progress_value', 0))
            for root_dir, dirs, files in os.walk(path):
                if self.is_hidden(root_dir):
                    continue
                dirs[:] = [d for d in dirs if not self.is_hidden(os.path.join(root_dir, d))]
                for file in files:
                    ext = os.path.splitext(file)[1]
                    if ext in selected_exts:
                        file_path = os.path.join(root_dir, file)
                        if self.is_hidden(file_path):
                            continue
                        self.queue.put(('insert_code', f"# Chemin de {file_path}\n"))
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                                content = f.read()
                            self.queue.put(('insert_code', content + '\n\n--------\n\n'))
                        except Exception as e:
                            self.queue.put(('insert_code', f"Erreur lecture {file_path}: {e}\n\n--------\n\n"))
            self.queue.put(('status', "Terminé"))
            self.queue.put(('show_message', "Succès", "Génération du code terminée."))
        except Exception as e:
            self.queue.put(('error_message', f"Erreur code: {e}"))
            self.queue.put(('status', "Erreur"))

    def on_advanced_search(self):
        name = self.search_name_var.get()
        ext = self.search_ext_var.get()
        date = self.search_date_var.get()
        sm = SearchManager(self.path_var.get(), self.excluded_dirs, self.hidden_manager)
        if not sm.validate_criteria(name, ext, date):
            return
        threading.Thread(target=sm.search_thread, args=(self.queue, name, ext, date), daemon=True).start()

    def toggle_advanced_search(self):
        if self.advanced_search_frame.winfo_viewable():
            self.advanced_search_frame.grid_remove()
            self.toggle_advanced_button.config(text="Recherche Avancée")
        else:
            self.advanced_search_frame.grid()
            self.toggle_advanced_button.config(text="Masquer Recherche Avancée")

    def show_context_menu(self, event):
        selected_item = self.tree.identify_row(event.y)
        if selected_item:
            self.tree.selection_set(selected_item)
            item_values = self.tree.item(selected_item, 'values')
            if item_values:
                path = item_values[0]
                if path in self.favorites:
                    self.context_menu.entryconfigure("Ajouter aux Favoris", label="Retirer des Favoris",
                                                     command=lambda: self.remove_favorites_path(path))
                else:
                    self.context_menu.entryconfigure("Ajouter aux Favoris", label="Ajouter aux Favoris",
                                                     command=lambda: self.add_to_favorites(path))
                self.context_menu.post(event.x_root, event.y_root)

    def remove_favorites_path(self, path):
        self.favorites_manager.remove_favorite(path)
        self.favorites = self.favorites_manager.favorites
        self.update_favorites_listbox()

    def process_queue(self):
        try:
            while True:
                task = self.queue.get_nowait()
                if task[0] == 'insert':
                    _, parent, item, abs_path, is_dir = task
                    node = self.tree.insert(parent, 'end', text=item, open=False, values=[abs_path],
                                            image=self.folder_icon if (is_dir and self.folder_icon) else (self.file_icon if self.file_icon else ''))
                    if is_dir:
                        self.tree.insert(node, 'end')
                    if not hasattr(self, 'path_to_item'):
                        self.path_to_item = {}
                    self.path_to_item[abs_path] = node
                elif task[0] == 'progress_max':
                    _, max_value = task
                    self.progress['maximum'] = max_value
                elif task[0] == 'progress_value':
                    _, value = task
                    self.progress['value'] = value
                elif task[0] == 'status':
                    _, status = task
                    self.status_var.set(status)
                elif task[0] == 'clear_extensions':
                    for widget in self.ext_frame.winfo_children():
                        widget.destroy()
                    self.ext_vars.clear()
                elif task[0] == 'add_extension':
                    _, ext = task
                    var = tk.BooleanVar(value=(ext in self.selected_extensions))
                    cb = ttk.Checkbutton(self.ext_frame, text=ext, variable=var)
                    cb.pack(anchor='w', pady=2)
                    self.ext_vars[ext] = var
                elif task[0] == 'insert_code':
                    _, code = task
                    self.code_text.configure(state='normal')
                    self.code_text.insert(tk.END, code)
                    self.code_text.configure(state='disabled')
                elif task[0] == 'show_message':
                    _, title, message = task
                    messagebox.showinfo(title, message)
                elif task[0] == 'error_message':
                    _, message = task
                    messagebox.showerror("Erreur", message)
                elif task[0] == 'search_results':
                    _, matches = task
                    self.show_search_results(matches)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)

        if self.progress['value'] >= self.progress['maximum']:
            self.loading_label.grid_remove()

    def show_search_results(self, matches):
        results_window = tk.Toplevel(self.root)
        results_window.title("Résultats")
        results_window.geometry("800x600")

        ttk.Label(results_window, text=f"{len(matches)} éléments trouvés:").pack(pady=5)
        results_frame = ttk.Frame(results_window)
        results_frame.pack(fill='both', expand=True, padx=10, pady=10)
        results_scroll = ttk.Scrollbar(results_frame)
        results_scroll.pack(side='right', fill='y')
        results_listbox = tk.Listbox(results_frame, yscrollcommand=results_scroll.set)
        results_listbox.pack(side='left', fill='both', expand=True)
        results_scroll.config(command=results_listbox.yview)

        for p in matches:
            results_listbox.insert(tk.END, p)

        action_frame = ttk.Frame(results_window)
        action_frame.pack(pady=5)
        ttk.Button(action_frame, text="Ouvrir", command=lambda: self.open_selected_result(results_listbox)).pack(side='left', padx=5)
        ttk.Button(action_frame, text="Afficher dans l'arborescence", command=lambda: self.show_in_tree(results_listbox)).pack(side='left', padx=5)

    def open_selected_result(self, listbox):
        selection = listbox.curselection()
        if selection:
            path = listbox.get(selection[0])
            try:
                if os.name == 'nt':
                    os.startfile(path)
                elif sys.platform == 'darwin':
                    subprocess.run(['open', path], check=True)
                else:
                    subprocess.run(['xdg-open', path], check=True)
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur: {e}")

    def show_in_tree(self, listbox):
        selection = listbox.curselection()
        if selection:
            path = listbox.get(selection[0])
            if os.path.exists(path):
                self.open_parents(path)
                self.highlight_path(path)
            else:
                messagebox.showerror("Erreur", f"'{path}' n'existe plus.")

    def open_parents(self, path):
        # Simplifié : recharger l'arbo si besoin
        pass

    def highlight_path(self, path, delay=500):
        item = getattr(self, 'path_to_item', {}).get(path)
        if item:
            self.highlight_treeview_item(item)
        else:
            self.root.after(delay, lambda: self.highlight_path(path, delay))

    def highlight_treeview_item(self, item):
        parent = self.tree.parent(item)
        while parent:
            self.tree.item(parent, open=True)
            parent = self.tree.parent(parent)
        self.tree.selection_set(item)
        self.tree.focus(item)
        self.tree.see(item)

    def on_drop(self, event):
        files = self.root.splitlist(event.data)
        if files:
            path = files[0]
            if os.path.isdir(path):
                self.history_stack.clear()
                self.back_button.config(state='disabled')
                self.path_var.set(path)
                self.on_path_change()
            else:
                messagebox.showwarning("Avertissement", "Veuillez déposer un dossier.")

    def on_close(self):
        selected_extensions = [ext for ext, var in self.ext_vars.items() if var.get()]
        self.config_manager.save_preferences(
            window_geometry=self.root.geometry(),
            last_path=self.path_var.get(),
            selected_extensions=selected_extensions,
            hidden_items=list(self.hidden_items),
            current_theme=self.current_theme,
            is_fullscreen=self.is_fullscreen
        )
        self.favorites_manager.save_favorites()
        self.hidden_manager.save_hidden_items()
        self.root.destroy()

    def toggle_theme(self):
        if self.current_theme == 'flatly':
            self.current_theme = 'darkly'
        else:
            self.current_theme = 'flatly'
        Style(theme=self.current_theme)
        # Sauvegarder immédiatement le thème
        self.config_manager.save_preferences(
            window_geometry=self.root.geometry(),
            last_path=self.path_var.get(),
            selected_extensions=[ext for ext, var in self.ext_vars.items() if var.get()],
            hidden_items=list(self.hidden_items),
            current_theme=self.current_theme,
            is_fullscreen=self.is_fullscreen
        )

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes('-fullscreen', self.is_fullscreen)
        self.config_manager.save_preferences(
            window_geometry=self.root.geometry(),
            last_path=self.path_var.get(),
            selected_extensions=[ext for ext, var in self.ext_vars.items() if var.get()],
            hidden_items=list(self.hidden_items),
            current_theme=self.current_theme,
            is_fullscreen=self.is_fullscreen
        )
