import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from ttkbootstrap import Style
from tkinter import ttk
import logging
from tkinterdnd2 import DND_FILES, TkinterDnD
from PIL import Image, ImageTk
import queue
import datetime
import sys
import json
import shutil  # Importé pour supprimer des dossiers non vides
import subprocess  # Ajouté pour une ouverture de fichiers plus sûre

# Configure logging
logging.basicConfig(filename='project_explorer.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class ProjectExplorerApp:
    """
    Classe principale de l'application Explorateur de Projet.
    Gère l'interface utilisateur et la logique métier.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Explorateur de Projet")
        self.root.geometry("1400x800")  # Ajusté pour plus d'espace

        # Appliquer le style ttkbootstrap
        style = Style(theme="flatly")
        style.configure('Treeview', rowheight=25)
        self.ext_vars = {}
        self.excluded_dirs = ['node_modules', '__pycache__', '.git', '__svn__', '__hg__', 'Google Drive']  # Répertoires à exclure

        # Charger les icônes si disponibles et les redimensionner
        self.folder_icon, self.file_icon = self.load_icons(folder_path='folder_icon.png', file_path='file_icon.png', size=(16, 16))

        # Pile d'historique pour la navigation "Retour"
        self.history_stack = []

        # Queue pour la communication entre threads
        self.queue = queue.Queue()

        # Structure de données pour les favoris
        self.favorites = set()
        self.favorites_file = 'favorites.json'
        self.load_favorites()

        # Ensemble des éléments masqués
        self.hidden_items = set()
        self.hidden_items_file = 'hidden_items.json'
        self.load_hidden_items()

        # Mapping chemin → identifiant Treeview
        self.path_to_item = {}

        # Charger les préférences utilisateur
        self.load_preferences()
        # Restaurer la taille de la fenêtre
        if self.window_geometry:
            self.root.geometry(self.window_geometry)
        # Restaurer les extensions sélectionnées
        for ext, var in self.ext_vars.items():
            var.set(ext in self.selected_extensions)
        # Restaurer les éléments masqués
        self.hidden_items = set(self.hidden_items_list)

        # Indicateur de chargement initial
        self.is_initial_loading = False

        self.create_widgets()
        self.bind_events()

        # Si un chemin est chargé depuis les préférences, charger l'arborescence
        if self.path_var.get():
            self.on_path_change()

        # Démarrer la boucle de vérification de la queue
        self.root.after(100, self.process_queue)

        # Protocole de fermeture pour sauvegarder les préférences
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_icons(self, folder_path, file_path, size=(16, 16)):
        """
        Charge et redimensionne les icônes des dossiers et des fichiers.
        """
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            folder_path = os.path.join(script_dir, folder_path)
            file_path = os.path.join(script_dir, file_path)

            # Charger et redimensionner l'icône du dossier
            folder_image = Image.open(folder_path)
            try:
                resample = Image.Resampling.LANCZOS
            except AttributeError:
                resample = Image.LANCZOS
            folder_image = folder_image.resize(size, resample)
            folder_icon = ImageTk.PhotoImage(folder_image)

            # Charger et redimensionner l'icône du fichier
            file_image = Image.open(file_path)
            file_image = file_image.resize(size, resample)
            file_icon = ImageTk.PhotoImage(file_image)

            return folder_icon, file_icon
        except (FileNotFoundError, tk.TclError) as e:
            logging.warning(f"Icons '{folder_path}' et/ou '{file_path}' non trouvés ou invalides. Les icônes ne seront pas affichées. Erreur: {e}")
            return None, None

    def load_favorites(self):
        """
        Charge les favoris à partir du fichier JSON.
        """
        if os.path.exists(self.favorites_file):
            try:
                with open(self.favorites_file, 'r', encoding='utf-8') as f:
                    self.favorites = set(json.load(f))
                logging.info("Favoris chargés avec succès.")
            except Exception as e:
                logging.error(f"Erreur lors du chargement des favoris: {e}")
                self.favorites = set()
        else:
            self.favorites = set()

    def save_favorites(self):
        """
        Sauvegarde les favoris dans le fichier JSON.
        """
        try:
            with open(self.favorites_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.favorites), f, ensure_ascii=False, indent=4)
            logging.info("Favoris sauvegardés avec succès.")
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde des favoris: {e}")

    def load_hidden_items(self):
        """
        Charge les éléments masqués à partir du fichier JSON.
        """
        if os.path.exists(self.hidden_items_file):
            try:
                with open(self.hidden_items_file, 'r', encoding='utf-8') as f:
                    self.hidden_items = set(json.load(f))
                logging.info("Éléments masqués chargés avec succès.")
            except Exception as e:
                logging.error(f"Erreur lors du chargement des éléments masqués: {e}")
                self.hidden_items = set()
        else:
            self.hidden_items = set()

    def save_hidden_items(self):
        """
        Sauvegarde les éléments masqués dans le fichier JSON.
        """
        try:
            with open(self.hidden_items_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.hidden_items), f, ensure_ascii=False, indent=4)
            logging.info("Éléments masqués sauvegardés avec succès.")
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde des éléments masqués: {e}")

    def load_preferences(self):
        """
        Charge les préférences utilisateur à partir du fichier JSON.
        """
        self.preferences_file = 'preferences.json'
        self.path_var = tk.StringVar()
        self.window_geometry = None
        self.selected_extensions = []
        self.hidden_items_list = []
        if os.path.exists(self.preferences_file):
            try:
                with open(self.preferences_file, 'r', encoding='utf-8') as f:
                    prefs = json.load(f)
                self.path_var.set(prefs.get("last_path", ""))
                self.window_geometry = prefs.get("window_geometry")
                self.selected_extensions = prefs.get("selected_extensions", [])
                self.hidden_items_list = prefs.get("hidden_items", [])
            except Exception as e:
                logging.error(f"Erreur lors du chargement des préférences: {e}")

    def save_preferences(self):
        """
        Sauvegarde les préférences utilisateur dans le fichier JSON.
        """
        try:
            selected_extensions = [ext for ext, var in self.ext_vars.items() if var.get()]
            prefs = {
                "window_geometry": self.root.geometry(),
                "last_path": self.path_var.get(),
                "selected_extensions": selected_extensions,
                "hidden_items": list(self.hidden_items),
            }
            with open(self.preferences_file, 'w', encoding='utf-8') as f:
                json.dump(prefs, f, ensure_ascii=False, indent=4)
            logging.info("Préférences sauvegardées avec succès.")
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde des préférences: {e}")

    def create_widgets(self):
        """
        Crée tous les widgets de l'interface utilisateur.
        """
        # Cadre pour le chemin du projet
        path_frame = ttk.Frame(self.root, padding="10 10 10 10")
        path_frame.grid(row=0, column=0, columnspan=7, sticky='ew')
        path_frame.columnconfigure(1, weight=1)

        ttk.Label(path_frame, text="Chemin du projet:").grid(row=0, column=0, sticky='w')
        self.path_entry = ttk.Entry(path_frame, textvariable=self.path_var)
        self.path_entry.grid(row=0, column=1, sticky='ew', padx=5)
        ttk.Button(path_frame, text="Parcourir", command=self.on_browse).grid(row=0, column=2)

        # Bouton "Retour"
        self.back_button = ttk.Button(path_frame, text="Retour", command=self.on_back, state='disabled')
        self.back_button.grid(row=0, column=3, padx=5)

        # Bouton "Masquer"
        hide_button = ttk.Button(path_frame, text="Masquer", command=self.hide_selected_items)
        hide_button.grid(row=0, column=4, padx=5)

        # Bouton "Afficher masqués"
        show_hidden_button = ttk.Button(path_frame, text="Afficher Masqués", command=self.show_hidden_items)
        show_hidden_button.grid(row=0, column=5, padx=5)

        # Barre de progression
        self.status_var = tk.StringVar()
        self.status_var.set("Prêt")
        self.progress = ttk.Progressbar(self.root, orient='horizontal', mode='determinate')
        self.progress.grid(row=1, column=0, columnspan=7, sticky='ew', padx=10)
        self.status_label = ttk.Label(self.root, textvariable=self.status_var)
        self.status_label.grid(row=1, column=6, sticky='e', padx=10)

        # Indicateur de chargement supplémentaire (UI Improvement)
        self.loading_label = ttk.Label(self.root, text="Chargement en cours...", foreground="blue")
        self.loading_label.grid(row=10, column=0, columnspan=7, pady=5)
        self.loading_label.grid_remove()  # Masquer par défaut

        # Remplacer la zone de recherche statique par un champ de recherche simple
        simple_search_frame = ttk.Frame(self.root)
        simple_search_frame.grid(row=2, column=0, columnspan=7, sticky='ew', padx=10, pady=5)
        simple_search_frame.columnconfigure(1, weight=1)

        ttk.Label(simple_search_frame, text="Rechercher:").grid(row=0, column=0, sticky='w')
        self.simple_search_var = tk.StringVar()
        self.simple_search_entry = ttk.Entry(simple_search_frame, textvariable=self.simple_search_var)
        self.simple_search_entry.grid(row=0, column=1, sticky='ew', padx=5)

        # Bouton pour déployer la recherche avancée
        self.toggle_advanced_button = ttk.Button(simple_search_frame, text="Recherche Avancée", command=self.toggle_advanced_search)
        self.toggle_advanced_button.grid(row=0, column=2, padx=5)

        # Cadre de recherche avancée (initialement masqué)
        self.advanced_search_frame = ttk.LabelFrame(self.root, text="Recherche Avancée", padding="10 10 10 10")
        self.advanced_search_frame.grid(row=3, column=0, columnspan=7, sticky='ew', padx=10)
        self.advanced_search_frame.columnconfigure(1, weight=1)
        self.advanced_search_frame.grid_remove()  # Masquer initialement

        # Déplacer les widgets de recherche avancée dans self.advanced_search_frame
        ttk.Label(self.advanced_search_frame, text="Nom contient:").grid(row=0, column=0, sticky='w', pady=2)
        self.search_name_var = tk.StringVar()
        self.search_name_entry = ttk.Entry(self.advanced_search_frame, textvariable=self.search_name_var)
        self.search_name_entry.grid(row=0, column=1, sticky='ew', padx=5, pady=2)

        # Critère d'extension
        ttk.Label(self.advanced_search_frame, text="Type de Fichier:").grid(row=1, column=0, sticky='w', pady=2)
        self.search_ext_var = tk.StringVar()
        self.search_ext_entry = ttk.Entry(self.advanced_search_frame, textvariable=self.search_ext_var)
        self.search_ext_entry.grid(row=1, column=1, sticky='ew', padx=5, pady=2)
        ttk.Label(self.advanced_search_frame, text="(ex: .py, .txt)").grid(row=1, column=2, sticky='w', pady=2)

        # Critère de date de modification
        ttk.Label(self.advanced_search_frame, text="Date de Modification après:").grid(row=2, column=0, sticky='w', pady=2)
        self.search_date_var = tk.StringVar()
        self.search_date_entry = ttk.Entry(self.advanced_search_frame, textvariable=self.search_date_var)
        self.search_date_entry.grid(row=2, column=1, sticky='ew', padx=5, pady=2)
        ttk.Label(self.advanced_search_frame, text="(format: YYYY-MM-DD)").grid(row=2, column=2, sticky='w', pady=2)

        # Bouton de recherche avancée
        ttk.Button(self.advanced_search_frame, text="Rechercher", command=self.on_advanced_search).grid(row=3, column=1, sticky='e', pady=5)

        # Ajuster les poids de la grille pour une meilleure réactivité
        self.root.columnconfigure(0, weight=3)  # Arborescence
        self.root.columnconfigure(3, weight=2)  # Sélection des extensions
        self.root.rowconfigure(4, weight=3)     # Ligne de l'arborescence
        self.root.rowconfigure(8, weight=2)     # Ligne de l'affichage du code

        # Treeview pour l'arborescence
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

        # Après avoir créé self.tree
        self.tree.tag_configure('hidden', foreground='grey')  # Les éléments masqués apparaîtront en gris

        # Sélection des extensions
        ext_label = ttk.Label(self.root, text="Sélectionnez les extensions:")
        ext_label.grid(row=3, column=3, sticky='nw', padx=10, pady=(10, 0))
        self.ext_frame = ttk.Frame(self.root)
        self.ext_frame.grid(row=4, column=3, sticky='nw', padx=10, pady=5)

        # Boutons de sélection des extensions
        ext_button_frame = ttk.Frame(self.root)
        ext_button_frame.grid(row=5, column=3, sticky='nw', padx=10)
        ttk.Button(ext_button_frame, text="Tout sélectionner", command=self.select_all_exts).pack(side='left', padx=5)
        ttk.Button(ext_button_frame, text="Tout désélectionner", command=self.deselect_all_exts).pack(side='left', padx=5)

        # Bouton pour générer le code
        generate_button = ttk.Button(self.root, text="Générer le code", command=self.on_generate_code)
        generate_button.grid(row=6, column=3, sticky='e', padx=10, pady=5)

        # Affichage du code
        code_label = ttk.Label(self.root, text="Code des fichiers sélectionnés:")
        code_label.grid(row=7, column=0, sticky='nw', padx=10, pady=(10, 0))
        self.code_text = ScrolledText(self.root, height=15, state='disabled')
        self.code_text.grid(row=8, column=0, columnspan=7, sticky='nsew', padx=10, pady=5)

        # Boutons de copie
        button_frame = ttk.Frame(self.root)
        button_frame.grid(row=9, column=0, columnspan=7, pady=10)
        ttk.Button(button_frame, text="Copier l'arborescence", command=self.copy_tree).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Copier le code", command=self.copy_code).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Tout copier", command=self.copy_all).pack(side='left', padx=5)

        # Section Favoris
        favorites_label = ttk.Label(self.root, text="Favoris:")
        favorites_label.grid(row=3, column=4, sticky='nw', padx=10, pady=(10, 0))
        favorites_frame = ttk.Frame(self.root)
        favorites_frame.grid(row=4, column=4, rowspan=3, sticky='nsew', padx=10, pady=5)
        self.favorites_scroll = ttk.Scrollbar(favorites_frame)
        self.favorites_scroll.pack(side='right', fill='y')
        self.favorites_listbox = tk.Listbox(favorites_frame, yscrollcommand=self.favorites_scroll.set, selectmode='single')
        self.favorites_listbox.pack(side='left', fill='both', expand=True)
        self.favorites_scroll.config(command=self.favorites_listbox.yview)

        # Boutons pour Favoris
        fav_button_frame = ttk.Frame(self.root)
        fav_button_frame.grid(row=7, column=4, sticky='n', padx=10, pady=5)
        ttk.Button(fav_button_frame, text="Ouvrir le Favori", command=self.open_selected_favorite).pack(pady=2)
        ttk.Button(fav_button_frame, text="Supprimer le Favori", command=self.remove_from_favorites).pack(pady=2)

        # Configuration de la grille
        self.root.columnconfigure(0, weight=2)
        self.root.columnconfigure(1, weight=1)
        self.root.columnconfigure(2, weight=1)
        self.root.columnconfigure(3, weight=1)
        self.root.columnconfigure(4, weight=1)
        self.root.columnconfigure(5, weight=1)
        self.root.columnconfigure(6, weight=1)
        self.root.rowconfigure(4, weight=3)
        self.root.rowconfigure(8, weight=2)

        # Initialisation des drag-and-drop
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.on_drop)

        # Création du menu contextuel
        self.create_context_menu()

        # Remplir la liste des favoris
        self.update_favorites_listbox()

        # Actualiser les sélections des extensions après la création des widgets
        for ext, var in self.ext_vars.items():
            var.set(ext in self.selected_extensions)

    def bind_events(self):
        """
        Lie les événements aux widgets.
        """
        self.path_entry.bind('<Return>', self.on_path_change)
        self.root.bind('<Control-f>', lambda event: self.search_name_entry.focus_set())
        self.tree.bind('<<TreeviewOpen>>', self.on_treeview_open)
        self.tree.bind('<Double-1>', self.on_treeview_double_click)  # Gestion du double-clic
        self.root.bind('<Control-o>', lambda event: self.on_browse())
        self.favorites_listbox.bind('<Double-1>', lambda event: self.open_selected_favorite())
        # La recherche avancée est déjà liée via le bouton "Rechercher"
        # Les événements de drag-and-drop sont gérés via tkinterdnd2

    def create_context_menu(self):
        """
        Crée le menu contextuel pour les éléments de l'arborescence.
        """
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Ouvrir", command=self.open_item)
        self.context_menu.add_command(label="Renommer", command=self.rename_item)
        self.context_menu.add_command(label="Supprimer", command=self.delete_item)
        self.context_menu.add_command(label="Copier le Chemin", command=self.copy_path)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Ajouter aux Favoris", command=self.add_to_favorites)
        self.context_menu.add_command(label="Masquer", command=self.hide_selected_items)

        # Lier le clic droit à l'arborescence
        self.tree.bind("<Button-3>", self.show_context_menu)  # Windows/Linux
        self.tree.bind("<Button-2>", self.show_context_menu)  # macOS

    def show_context_menu(self, event):
        """
        Affiche le menu contextuel à la position du curseur.
        """
        # Identifier l'élément sous le curseur
        selected_item = self.tree.identify_row(event.y)
        if selected_item:
            self.tree.selection_set(selected_item)
            item_values = self.tree.item(selected_item, 'values')
            if item_values:
                path = item_values[0]
                if path in self.favorites:
                    self.context_menu.entryconfigure("Ajouter aux Favoris", label="Retirer des Favoris",
                                                    command=lambda: self.remove_from_favorites(path))
                else:
                    self.context_menu.entryconfigure("Ajouter aux Favoris", label="Ajouter aux Favoris",
                                                    command=lambda: self.add_to_favorites(path))
                self.context_menu.post(event.x_root, event.y_root)

    def hide_selected_items(self):
        """
        Masque les fichiers ou dossiers sélectionnés dans l'arborescence.
        """
        selected_items = self.tree.selection()
        for item in selected_items:
            path = self.tree.item(item, 'values')[0]
            self.hidden_items.add(path)
        # Enregistrer les préférences mises à jour
        self.save_preferences()
        self.refresh_tree()

    def show_hidden_items(self):
        """
        Affiche une fenêtre pour gérer les éléments masqués.
        """
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
                self.hidden_items.remove(item)
                hidden_listbox.delete(index)
            self.save_hidden_items()
            self.refresh_tree()

        unhide_button = ttk.Button(hidden_window, text="Rétablir", command=unhide_selected)
        unhide_button.pack(pady=5)

    def refresh_tree(self):
        """
        Réaffiche l'arborescence en tenant compte des éléments masqués.
        """
        self.tree.delete(*self.tree.get_children())
        self.path_to_item.clear()
        root_path = self.path_var.get()
        threading.Thread(target=self.insert_tree_items, args=('', root_path), daemon=True).start()

    def open_item(self):
        """
        Ouvre le fichier ou dossier sélectionné avec l'application par défaut.
        """
        selected_items = self.tree.selection()
        for item in selected_items:
            item_values = self.tree.item(item, 'values')
            if not item_values:
                continue
            path = item_values[0]
            try:
                if os.name == 'nt':
                    os.startfile(path)
                elif sys.platform == 'darwin':
                    subprocess.run(['open', path], check=True)
                else:
                    subprocess.run(['xdg-open', path], check=True)
            except Exception as e:
                logging.error(f"Erreur lors de l'ouverture de '{path}': {e}")
                messagebox.showerror("Erreur", f"Erreur lors de l'ouverture de '{path}': {e}")

    def rename_item(self):
        """
        Renomme le fichier ou dossier sélectionné.
        """
        selected_item = self.tree.selection()
        if selected_item:
            item = selected_item[0]
            item_values = self.tree.item(item, 'values')
            if not item_values:
                messagebox.showerror("Erreur", "Impossible de renommer cet élément.")
                return
            old_path = item_values[0]
            new_name = simpledialog.askstring("Renommer", "Nouveau nom:", initialvalue=os.path.basename(old_path))
            if new_name:
                new_path = os.path.join(os.path.dirname(old_path), new_name)
                if os.path.exists(new_path):
                    messagebox.showerror("Erreur", f"Le nom '{new_name}' existe déjà dans ce répertoire.")
                    return
                try:
                    os.rename(old_path, new_path)
                    self.tree.item(item, text=new_name, values=[new_path])
                    logging.info(f"Renommé '{old_path}' en '{new_path}'")
                    # Mettre à jour le mapping
                    self.path_to_item[new_path] = self.path_to_item.pop(old_path)
                    # Mettre à jour les favoris si nécessaire
                    if old_path in self.favorites:
                        self.favorites.remove(old_path)
                        self.favorites.add(new_path)
                        self.save_favorites()
                        self.update_favorites_listbox()
                except FileNotFoundError:
                    messagebox.showerror("Erreur", "Le fichier ou dossier spécifié est introuvable.")
                except PermissionError:
                    messagebox.showerror("Erreur", "Permission refusée. Vous n'avez pas les droits nécessaires pour renommer cet élément.")
                except Exception as e:
                    logging.error(f"Erreur lors du renommage de '{old_path}': {e}")
                    messagebox.showerror("Erreur", f"Erreur lors du renommage: {e}")

    def delete_item(self):
        """
        Supprime le fichier ou dossier sélectionné après confirmation.
        """
        selected_item = self.tree.selection()
        if selected_item:
            confirm = messagebox.askyesno("Confirmer la suppression", "Êtes-vous sûr de vouloir supprimer cet élément ?")
            if confirm:
                for item in selected_item:
                    item_values = self.tree.item(item, 'values')
                    if not item_values:
                        continue
                    path = item_values[0]
                    try:
                        if os.path.isdir(path):
                            shutil.rmtree(path)  # Supprime les dossiers non vides
                        else:
                            os.remove(path)
                        self.tree.delete(item)
                        logging.info(f"Supprimé '{path}'")
                        # Supprimer du mapping
                        if path in self.path_to_item:
                            del self.path_to_item[path]
                        # Supprimer des favoris si nécessaire
                        if path in self.favorites:
                            self.favorites.remove(path)
                            self.save_favorites()
                            self.update_favorites_listbox()
                    except FileNotFoundError:
                        messagebox.showerror("Erreur", "Le fichier ou dossier spécifié est introuvable.")
                    except PermissionError:
                        messagebox.showerror("Erreur", "Permission refusée. Vous n'avez pas les droits nécessaires pour supprimer cet élément.")
                    except Exception as e:
                        logging.error(f"Erreur lors de la suppression de '{path}': {e}")
                        messagebox.showerror("Erreur", f"Erreur lors de la suppression: {e}")

    def copy_path(self):
        """
        Copie le chemin complet du fichier ou dossier sélectionné dans le presse-papiers.
        """
        selected_item = self.tree.selection()
        if selected_item:
            paths = [self.tree.item(item, 'values')[0] for item in selected_item if self.tree.item(item, 'values')]
            paths_str = '\n'.join(paths)
            self.root.clipboard_clear()
            self.root.clipboard_append(paths_str)
            messagebox.showinfo("Succès", "Le chemin a été copié dans le presse-papiers.")
            logging.info(f"Chemin(s) copié(s): {paths_str}")

    def add_to_favorites(self, path=None):
        """
        Ajoute un élément aux favoris.
        """
        if not path:
            selected_item = self.tree.selection()
            if not selected_item:
                messagebox.showwarning("Avertissement", "Veuillez sélectionner un élément à ajouter aux favoris.")
                return
            item_values = self.tree.item(selected_item[0], 'values')
            if not item_values:
                messagebox.showwarning("Avertissement", "L'élément sélectionné n'a pas de chemin valide.")
                return
            path = item_values[0]
        if path not in self.favorites:
            self.favorites.add(path)
            self.save_favorites()
            self.update_favorites_listbox()
            messagebox.showinfo("Succès", f"'{path}' a été ajouté aux favoris.")
            logging.info(f"Favori ajouté: {path}")
        else:
            messagebox.showinfo("Information", f"'{path}' est déjà dans les favoris.")

    def remove_from_favorites(self, path=None):
        """
        Retire un élément des favoris.
        """
        if not path:
            selected_item = self.tree.selection()
            if not selected_item:
                messagebox.showwarning("Avertissement", "Veuillez sélectionner un élément à retirer des favoris.")
                return
            item_values = self.tree.item(selected_item[0], 'values')
            if not item_values:
                messagebox.showwarning("Avertissement", "L'élément sélectionné n'a pas de chemin valide.")
                return
            path = item_values[0]
        if path in self.favorites:
            self.favorites.remove(path)
            self.save_favorites()
            self.update_favorites_listbox()
            messagebox.showinfo("Succès", f"'{path}' a été retiré des favoris.")
            logging.info(f"Favori retiré: {path}")
        else:
            messagebox.showinfo("Information", f"'{path}' n'est pas dans les favoris.")

    def get_truncated_path(self, path, max_depth=2):
        """
        Retourne une version tronquée du chemin, ne montrant que les deux derniers éléments.
        Par exemple, ".../1A/a.txt"
        """
        parts = path.split(os.sep)
        if len(parts) > max_depth:
            return os.sep.join(['...'] + parts[-max_depth:])
        else:
            return path

    def update_favorites_listbox(self):
        """
        Met à jour la liste des favoris dans l'interface utilisateur en affichant des chemins tronqués.
        """
        self.favorites_listbox.delete(0, tk.END)
        self.favorites_list_sorted = sorted(self.favorites)  # Liste triée des favoris
        for fav in self.favorites_list_sorted:
            display_text = self.get_truncated_path(fav)
            self.favorites_listbox.insert(tk.END, display_text)

    def open_selected_favorite(self):
        """
        Ouvre le favori sélectionné comme nouveau chemin dans l'application.
        """
        selection = self.favorites_listbox.curselection()
        if selection:
            index = selection[0]
            path = self.favorites_list_sorted[index]
            if not os.path.exists(path):
                messagebox.showerror("Erreur", f"Le chemin '{path}' n'existe plus.")
                self.favorites.remove(path)
                self.save_favorites()
                self.update_favorites_listbox()
                return

            if os.path.isdir(path):
                # Si c'est un dossier, définir le nouveau chemin et recharger l'arborescence
                self.history_stack.clear()
                self.back_button.config(state='disabled')
                self.path_var.set(path)
                self.on_path_change()
            else:
                # Si c'est un fichier, définir le chemin sur le répertoire parent et recharger l'arborescence
                parent_dir = os.path.dirname(path)
                self.history_stack.clear()
                self.back_button.config(state='disabled')
                self.path_var.set(parent_dir)
                self.on_path_change()
                # Surligner le fichier après qu'il a été chargé
                self.highlight_path(path)
        else:
            messagebox.showwarning("Avertissement", "Veuillez sélectionner un favori à ouvrir.")

    def highlight_path(self, path, delay=500):
        """
        Surligne l'élément spécifié dans le Treeview.
        Si l'élément n'est pas encore présent, réessaie après un délai.
        """
        item = self.path_to_item.get(path)
        if item:
            self.highlight_treeview_item(item)
        else:
            # Planifier une nouvelle tentative après un délai
            self.root.after(delay, lambda: self.highlight_path(path, delay))

    def copy_tree(self):
        """
        Copie l'arborescence dans le presse-papiers.
        """
        try:
            tree_str = self.get_full_treeview_items()
            self.root.clipboard_clear()
            self.root.clipboard_append(tree_str)
            messagebox.showinfo("Succès", "L'arborescence a été copiée dans le presse-papiers.")
            logging.info("Arborescence copiée dans le presse-papiers")
        except Exception as e:
            logging.error(f"Erreur lors de la copie de l'arborescence: {e}")
            messagebox.showerror("Erreur", f"Erreur lors de la copie de l'arborescence: {e}")

    def get_full_treeview_items(self):
        """
        Récupère tous les éléments de l'arborescence en parcourant le système de fichiers directement,
        au lieu de se baser uniquement sur le Treeview affiché.
        """
        path = self.path_var.get()
        lines = []
        def recurse(path, prefix=''):
            try:
                items = os.listdir(path)
            except (PermissionError, FileNotFoundError):
                return
            items.sort()
            for idx, item in enumerate(items):
                if item in self.excluded_dirs:
                    continue
                abs_path = os.path.join(path, item)
                if abs_path in self.hidden_items:
                    continue
                connector = '├── ' if idx < len(items) - 1 else '└── '
                lines.append(f"{prefix}{connector}{item}")
                if os.path.isdir(abs_path):
                    extension = '│   ' if idx < len(items) - 1 else '    '
                    recurse(abs_path, prefix + extension)
        recurse(path)
        return '\n'.join(lines)

    def copy_code(self):
        """
        Copie le code dans le presse-papiers.
        """
        try:
            code_str = self.code_text.get('1.0', tk.END)
            self.root.clipboard_clear()
            self.root.clipboard_append(code_str)
            messagebox.showinfo("Succès", "Le code a été copié dans le presse-papiers.")
            logging.info("Code copié dans le presse-papiers")
        except Exception as e:
            logging.error(f"Erreur lors de la copie du code: {e}")
            messagebox.showerror("Erreur", f"Erreur lors de la copie du code: {e}")

    def copy_all(self):
        """
        Copie l'arborescence et le code dans le presse-papiers.
        """
        try:
            tree_str = self.get_full_treeview_items()
            code_str = self.code_text.get('1.0', tk.END)
            all_str = tree_str + '\n' + code_str
            self.root.clipboard_clear()
            self.root.clipboard_append(all_str)
            messagebox.showinfo("Succès", "L'arborescence et le code ont été copiés dans le presse-papiers.")
            logging.info("Arborescence et code copiés dans le presse-papiers")
        except Exception as e:
            logging.error(f"Erreur lors de la copie de l'ensemble: {e}")
            messagebox.showerror("Erreur", f"Erreur lors de la copie de l'ensemble: {e}")

    def on_browse(self):
        """
        Ouvre une boîte de dialogue pour sélectionner le dossier du projet.
        """
        path = filedialog.askdirectory()
        if path:
            self.history_stack.clear()
            self.back_button.config(state='disabled')
            self.path_var.set(path)
            self.on_path_change()

    def on_back(self):
        """
        Retourne au répertoire précédent.
        """
        if self.history_stack:
            previous_path = self.history_stack.pop()
            self.path_var.set(previous_path)
            self.on_path_change()
            if not self.history_stack:
                self.back_button.config(state='disabled')

    def on_path_change(self, event=None, path=None):
        """
        Appelé lorsque le chemin du projet change.
        """
        if path:
            current_path = path
        else:
            current_path = self.path_var.get()
        if os.path.isdir(current_path):
            # Effacer l'arborescence
            self.tree.delete(*self.tree.get_children())
            self.path_to_item.clear()  # Réinitialiser le mapping
            # Réinitialiser la barre de progression
            self.progress['value'] = 0
            self.status_var.set("Chargement de l'arborescence...")
            self.loading_label.grid()  # Afficher l'indicateur de chargement
            logging.info(f"Chargement du projet à partir de {current_path}")
            # Activer l'indicateur de chargement initial
            self.is_initial_loading = True
            # Démarrer le thread pour construire l'arborescence
            threading.Thread(target=self.build_treeview_thread, args=(current_path,), daemon=True).start()
            # Mettre à jour les extensions
            threading.Thread(target=self.update_extensions, args=(current_path,), daemon=True).start()
        else:
            # Effacer l'arborescence et les extensions
            self.tree.delete(*self.tree.get_children())
            for widget in self.ext_frame.winfo_children():
                widget.destroy()
            self.ext_vars.clear()
            self.path_to_item.clear()

    def build_treeview_thread(self, path):
        """
        Construit l'arborescence du projet dans un thread séparé.
        Optimisé pour les grands projets.
        """
        try:
            # Élimination du comptage préalable des éléments
            self.queue.put(('progress_max', 100))  # Utiliser une estimation pour la barre de progression
            self.queue.put(('progress_value', 0))
            self.queue.put(('status', "Chargement de l'arborescence..."))
            self.insert_tree_items('', path)
            self.queue.put(('progress_value', 100))
            self.queue.put(('status', "Chargement terminé"))
            logging.info("Arborescence chargée avec succès")
        except Exception as e:
            logging.error(f"Erreur lors du chargement de l'arborescence: {e}")
            self.queue.put(('error_message', f"Erreur lors du chargement de l'arborescence: {e}"))

    def insert_tree_items(self, parent, path):
        """
        Insère les éléments dans le Treeview avec lazy loading.
        """
        try:
            items = os.listdir(path)
        except (PermissionError, FileNotFoundError):
            return
        items.sort()
        for idx, item in enumerate(items):
            if item in self.excluded_dirs:
                continue
            abs_path = os.path.join(path, item)
            if abs_path in self.hidden_items:
                continue
            try:
                is_dir = os.path.isdir(abs_path)
                if is_dir:
                    node = self.tree.insert(parent, 'end', text=item, open=False, values=[abs_path],
                                            image=self.folder_icon if self.folder_icon else '')
                    # Ajouter un élément vide pour les dossiers non explorés
                    self.tree.insert(node, 'end')
                else:
                    node = self.tree.insert(parent, 'end', text=item, values=[abs_path],
                                            image=self.file_icon if self.file_icon else '')
                # Mettre à jour le mapping
                self.path_to_item[abs_path] = node
                # Mise à jour de la barre de progression avec une estimation
                if self.is_initial_loading:
                    self.queue.put(('progress_increment',))
                    percentage = (self.progress['value'] + 1) % 100
                    self.queue.put(('status', f"Chargement... {percentage:.2f}%"))
            except (PermissionError, FileNotFoundError):
                continue

    def on_treeview_open(self, event):
        """
        Chargement paresseux des sous-dossiers lorsqu'un dossier est ouvert.
        """
        node = self.tree.focus()
        if not node:
            return

        # Vérifier et supprimer les placeholders
        children = self.tree.get_children(node)
        for child in children:
            if not self.tree.get_children(child):
                self.tree.delete(child)

        item_values = self.tree.item(node, 'values')
        if not item_values:
            return
        current_path = item_values[0]
        logging.info(f"Chargement du sous-dossier: {current_path}")

        # Insérer les vrais sous-éléments dans un thread
        threading.Thread(target=self.insert_tree_items, args=(node, current_path), daemon=True).start()

    def on_treeview_double_click(self, event):
        """
        Gère le double-clic sur un élément de l'arborescence pour naviguer dans le dossier.
        """
        item_id = self.tree.focus()
        item_values = self.tree.item(item_id, 'values')
        if not item_values:
            return
        path = item_values[0]
        if os.path.isdir(path):
            # Ajouter le chemin actuel à la pile d'historique
            current_root = self.path_var.get()
            self.history_stack.append(current_root)
            self.back_button.config(state='normal')

            # Définir le nouveau chemin comme le chemin de base
            self.path_var.set(path)
            self.on_path_change()

    def update_extensions(self, path):
        """
        Met à jour la liste des extensions disponibles.
        """
        try:
            extensions = self.get_text_extensions(path)
            self.queue.put(('clear_extensions',))
            for ext in extensions:
                self.queue.put(('add_extension', ext))
            logging.info("Extensions mises à jour")
        except Exception as e:
            logging.error(f"Erreur lors de la mise à jour des extensions: {e}")

    def get_text_extensions(self, path):
        """
        Récupère les extensions de fichiers textuels du projet.
        """
        text_extensions = set()
        known_text_extensions = {
            '.txt', '.py', '.md', '.c', '.cpp', '.h', '.java', '.js', '.html', '.css',
            '.json', '.xml', '.csv', '.ini', '.cfg', '.bat', '.sh', '.rb', '.php', '.pl',
            '.yaml', '.yml', '.sql', '.r', '.go', '.kt', '.swift', '.ts', '.tsx', '.jsx', '.tex'
            # Ajoutez d'autres extensions si nécessaire
        }
        for root_dir, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
            for file in files:
                ext = os.path.splitext(file)[1]
                if ext.lower() in known_text_extensions:
                    text_extensions.add(ext)
        return sorted(text_extensions)

    def select_all_exts(self):
        """
        Sélectionne toutes les extensions.
        """
        for var in self.ext_vars.values():
            var.set(True)

    def deselect_all_exts(self):
        """
        Désélectionne toutes les extensions.
        """
        for var in self.ext_vars.values():
            var.set(False)

    def is_hidden(self, path):
        """
        Vérifie si le chemin est masqué ou si l'un de ses dossiers parents est masqué.
        """
        path = os.path.abspath(path)
        for hidden_path in self.hidden_items:
            hidden_path = os.path.abspath(hidden_path)
            if path == hidden_path or path.startswith(hidden_path + os.sep):
                return True
        return False

    def on_generate_code(self):
        """
        Génère le code des fichiers sélectionnés.
        """
        selected_exts = [ext for ext, var in self.ext_vars.items() if var.get()]
        path = self.path_var.get()
        self.code_text.configure(state='normal')
        self.code_text.delete('1.0', tk.END)
        if not selected_exts:
            messagebox.showwarning("Avertissement", "Veuillez sélectionner au moins une extension.")
            self.code_text.configure(state='disabled')
            return
        # Exécuter dans un thread pour éviter le blocage de l'UI
        threading.Thread(target=self.generate_code_thread, args=(path, selected_exts), daemon=True).start()

    def generate_code_thread(self, path, selected_exts):
        """
        Thread pour générer le code des fichiers sélectionnés.
        """
        try:
            self.queue.put(('status', "Génération du code..."))
            # Utiliser une estimation pour la barre de progression
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
                            self.queue.put(('insert_code', f"Impossible de lire le fichier {file_path}: {e}\n\n--------\n\n"))
                        # Mise à jour de la barre de progression
                        current_value = self.progress['value'] + 1
                        self.queue.put(('progress_value', current_value % 100))
                        self.queue.put(('status', f"Génération du code... {current_value % 100:.2f}%"))
            self.queue.put(('status', "Génération terminée"))
            logging.info("Génération du code terminée")
            self.queue.put(('show_message', "Succès", "Génération du code terminée."))
        except Exception as e:
            logging.error(f"Erreur lors de la génération du code: {e}")
            self.queue.put(('error_message', f"Erreur lors de la génération du code: {e}"))
            self.queue.put(('status', "Erreur lors de la génération"))

    def on_search(self):
        """
        Méthode pour la recherche simple
        """
        query = self.simple_search_var.get().lower()
        if not query:
            messagebox.showwarning("Attention", "Veuillez entrer un terme de recherche.")
            return
        # Lancer la recherche dans un thread séparé
        threading.Thread(target=self.search_thread, args=(query,), daemon=True).start()

    def on_advanced_search(self):
        """
        Recherche les éléments correspondant aux critères avancés en parcourant le système de fichiers.
        """
        query_name = self.search_name_var.get().lower()
        query_ext = self.search_ext_var.get().lower()
        query_date = self.search_date_var.get()

        # Validation de la date
        if query_date:
            try:
                datetime.datetime.strptime(query_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Erreur de format", "La date doit être au format YYYY-MM-DD.")
                return

        # Validation des extensions
        if query_ext:
            exts = [e.strip() for e in query_ext.split(',')]
            for ext in exts:
                if not ext.startswith('.'):
                    messagebox.showerror("Erreur de format", f"L'extension '{ext}' n'est pas valide. Elle doit commencer par un point.")
                    return

        # Effacer les sélections précédentes
        self.tree.selection_remove(*self.tree.selection())

        # Démarrer le thread de recherche
        threading.Thread(target=self.search_thread, args=(query_name, query_ext, query_date), daemon=True).start()

    def search_thread(self, query):
        """
        Thread pour effectuer la recherche avancée en parcourant le système de fichiers.
        """
        try:
            self.queue.put(('status', "Recherche en cours..."))
            path = self.path_var.get()
            matches = []
            for root_dir, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
                for file in files:
                    file_path = os.path.join(root_dir, file)
                    basename = os.path.basename(file_path).lower()

                    # Critère de nom
                    if query and query not in basename:
                        continue

                    # Critère d'extension
                    if query:
                        file_ext = os.path.splitext(file)[1].lower()
                        ext_list = [e.strip() for e in query.split(',')]
                        if file_ext not in ext_list:
                            continue

                    # Critère de date de modification
                    if query:
                        try:
                            date_obj = datetime.datetime.strptime(query, "%Y-%m-%d")
                            mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                            if mod_time < date_obj:
                                continue
                        except ValueError:
                            continue

                    # Si tous les critères sont satisfaits, ajouter à la liste
                    matches.append(file_path)

            self.queue.put(('search_results', matches))
            logging.info(f"Recherche terminée. {len(matches)} éléments trouvés.")
        except Exception as e:
            logging.error(f"Erreur lors de la recherche: {e}")
            self.queue.put(('error_message', f"Erreur lors de la recherche: {e}"))
            self.queue.put(('status', "Erreur lors de la recherche"))

    def show_search_results(self, matches):
        """
        Affiche les résultats de la recherche dans une nouvelle fenêtre.
        """
        results_window = tk.Toplevel(self.root)
        results_window.title("Résultats de la Recherche")
        results_window.geometry("800x600")

        ttk.Label(results_window, text=f"Résultats de la recherche ({len(matches)} éléments trouvés):").pack(pady=5)

        # Liste des résultats avec scrollbar
        results_frame = ttk.Frame(results_window)
        results_frame.pack(fill='both', expand=True, padx=10, pady=10)

        results_scroll = ttk.Scrollbar(results_frame)
        results_scroll.pack(side='right', fill='y')

        results_listbox = tk.Listbox(results_frame, yscrollcommand=results_scroll.set)
        results_listbox.pack(side='left', fill='both', expand=True)

        results_scroll.config(command=results_listbox.yview)

        for path in matches:
            results_listbox.insert(tk.END, path)

        # Boutons pour les actions
        action_frame = ttk.Frame(results_window)
        action_frame.pack(pady=5)

        open_button = ttk.Button(action_frame, text="Ouvrir l'élément sélectionné",
                                 command=lambda: self.open_selected_result(results_listbox))
        open_button.pack(side='left', padx=5)

        show_in_tree_button = ttk.Button(action_frame, text="Afficher dans l'arborescence",
                                         command=lambda: self.show_in_tree(results_listbox))
        show_in_tree_button.pack(side='left', padx=5)

    def open_selected_result(self, listbox):
        """
        Ouvre l'élément sélectionné dans la liste des résultats de recherche.
        """
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
                logging.error(f"Erreur lors de l'ouverture de '{path}': {e}")
                messagebox.showerror("Erreur", f"Erreur lors de l'ouverture de '{path}': {e}")
        else:
            messagebox.showwarning("Avertissement", "Veuillez sélectionner un élément à ouvrir.")

    def show_in_tree(self, listbox):
        """
        Affiche l'élément sélectionné dans le Treeview en dépliant les nœuds parents et en le surlignant.
        """
        selection = listbox.curselection()
        if selection:
            path = listbox.get(selection[0])
            item = self.path_to_item.get(path)
            if item:
                self.highlight_treeview_item(item)
            else:
                if os.path.exists(path):
                    self.open_parents(path)
                    # Après avoir ouvert les parents, essayer de surligner
                    self.highlight_path(path)
                else:
                    messagebox.showerror("Erreur", f"Le chemin '{path}' n'existe plus.")
        else:
            messagebox.showwarning("Avertissement", "Veuillez sélectionner un élément à afficher.")

    def process_queue(self):
        """
        Traite les éléments de la queue pour mettre à jour l'interface utilisateur de manière thread-safe.
        """
        try:
            while True:
                task = self.queue.get_nowait()
                if task[0] == 'insert':
                    _, parent, item, abs_path, is_dir = task
                    if is_dir:
                        node = self.tree.insert(parent, 'end', text=item, open=False, values=[abs_path],
                                                image=self.folder_icon if self.folder_icon else '')
                        # Ajouter un élément vide pour les dossiers non explorés
                        self.tree.insert(node, 'end')
                    else:
                        node = self.tree.insert(parent, 'end', text=item, values=[abs_path],
                                                image=self.file_icon if self.file_icon else '')
                    # Mettre à jour le mapping
                    self.path_to_item[abs_path] = node
                elif task[0] == 'progress_max':
                    _, max_value = task
                    if self.is_initial_loading:
                        self.progress['maximum'] = max_value
                elif task[0] == 'progress_value':
                    _, value = task
                    if self.is_initial_loading:
                        self.progress['value'] = value
                elif task[0] == 'progress_increment':
                    if self.is_initial_loading:
                        self.progress['value'] += 1
                elif task[0] == 'status':
                    _, status = task
                    self.status_var.set(status)
                elif task[0] == 'clear_extensions':
                    for widget in self.ext_frame.winfo_children():
                        widget.destroy()
                    self.ext_vars.clear()
                elif task[0] == 'add_extension':
                    _, ext = task
                    var = tk.BooleanVar()
                    cb = ttk.Checkbutton(self.ext_frame, text=ext, variable=var)
                    cb.pack(anchor='w', pady=2)
                    self.ext_vars[ext] = var
                elif task[0] == 'delete':
                    _, item_id = task
                    # Trouver le chemin correspondant pour le mapping
                    path = self.tree.item(item_id, 'values')[0]
                    if path in self.path_to_item:
                        del self.path_to_item[path]
                    self.tree.delete(item_id)
                elif task[0] == 'insert_code':
                    _, code = task
                    self.code_text.insert(tk.END, code)
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

        # Masquer l'indicateur de chargement si le chargement est terminé
        if self.is_initial_loading and self.progress['value'] >= self.progress['maximum']:
            self.loading_label.grid_remove()
            self.status_var.set("Chargement terminé")
            self.is_initial_loading = False

    def highlight_treeview_item(self, item):
        """
        Surligne l'élément dans le Treeview et déplie les parents.
        """
        # Déplier tous les parents
        parent = self.tree.parent(item)
        while parent:
            self.tree.item(parent, open=True)
            parent = self.tree.parent(parent)

        # Surligner l'élément
        self.tree.selection_set(item)
        self.tree.focus(item)
        self.tree.see(item)

        # Appliquer le tag 'highlight'
        self.clear_highlights()
        self.tree.item(item, tags=('highlight',))
        self.tree.tag_configure('highlight', background='yellow')

    def clear_highlights(self):
        """
        Supprime tous les tags de surlignage.
        """
        for item in self.tree.tag_has('highlight'):
            self.tree.item(item, tags=())

    def find_treeview_item(self, path):
        """
        Trouve l'élément dans le Treeview correspondant au chemin donné en utilisant le mapping.
        """
        return self.path_to_item.get(path)

    def open_parents(self, path):
        """
        Ouvre tous les parents d'un chemin donné dans le Treeview.
        """
        parents = []
        current_path = os.path.dirname(path)
        base_path = self.path_var.get()
        while current_path and current_path != base_path:
            parents.insert(0, current_path)
            current_path = os.path.dirname(current_path)
        for parent in parents:
            parent_item = self.path_to_item.get(parent)
            if parent_item:
                self.tree.item(parent_item, open=True)
                self.on_treeview_open(None, parent)

    def on_drop(self, event):
        """
        Gère le dépôt lors du glisser-déposer.
        """
        # Récupère la liste des fichiers/dossiers déposés
        files = self.root.splitlist(event.data)
        if files:
            # Si plusieurs fichiers, prendre le premier dossier
            path = files[0]
            if os.path.isdir(path):
                self.history_stack.clear()
                self.back_button.config(state='disabled')
                self.path_var.set(path)
                self.on_path_change()
            else:
                messagebox.showwarning("Avertissement", "Veuillez déposer un dossier de projet.")

    def on_close(self):
        """
        Gère la fermeture de l'application en sauvegardant les préférences.
        """
        self.save_preferences()
        self.save_favorites()
        self.save_hidden_items()
        self.root.destroy()


    def toggle_advanced_search(self):
        """
        Méthode pour afficher ou masquer la recherche avancée
        """
        if self.advanced_search_frame.winfo_viewable():
            self.advanced_search_frame.grid_remove()
            self.toggle_advanced_button.config(text="Recherche Avancée")
        else:
            self.advanced_search_frame.grid()
            self.toggle_advanced_button.config(text="Masquer Recherche Avancée")


# Initialiser TkinterDnD
if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = ProjectExplorerApp(root)
    root.mainloop()
