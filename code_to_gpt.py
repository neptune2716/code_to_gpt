# Modification de l'ordre des imports
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk, mainloop
import logging
from PIL import Image, ImageTk
import queue
import datetime
import sys
import json
import shutil
import subprocess
from tkinter import font
from ttkbootstrap import Style
from tkinterdnd2 import DND_FILES, TkinterDnD

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

        # Initialize selected_files and related variables VERY EARLY
        self.selected_files = {}             # Dictionary to store all selected files
        self.manual_selected_files = {}        # New: to store manual selections
        self.generate_code_after_id = None     # New: for debouncing multiple changes

        # Initialize theme and fullscreen variables before loading preferences
        self.current_theme = 'flatly'      # Default theme
        self.is_fullscreen = True         # Default full-screen state

        # Initialiser les variables avant le chargement des préférences
        self.current_theme = 'flatly'      # Default theme
        self.is_fullscreen = True          # Default full-screen state
        self.window_geometry = None
        self.path_var = tk.StringVar()
        self.font_size = 12
        self.code_font = "Courier"
        self.auto_refresh = True

        # Charger les préférences (qui peuvent écraser certaines valeurs par défaut)
        self.load_preferences()
        
        # Forcer le mode plein écran au démarrage, indépendamment des préférences
        self.is_fullscreen = True
        self.root.attributes('-fullscreen', True)

        # Remettre l'initialisation du style ttkbootstrap
        style = Style(theme=self.current_theme)
        style.configure('Treeview', rowheight=25)
        
        # Style pour les frames avec coins arrondis
        style.configure('Card.TFrame', borderwidth=1, relief='solid')
        style.configure('Card.TLabelframe', borderwidth=1, relief='solid')
        
        # Style pour les boutons avec coins arrondis
        style.configure('Toggle.TButton', borderwidth=1, relief='solid', padding=5)
        style.configure('Action.TButton', borderwidth=1, relief='solid', padding=5)
        
        # La configuration de 'Card.TListbox' n'est pas supportée par ttkbootstrap et a été enlevée
        # style.configure('Card.TListbox', borderwidth=1, relief='solid', padding=2)

        # Appliquer le mode plein écran si nécessaire
        self.root.attributes('-fullscreen', self.is_fullscreen)

        # Restaurer la géométrie de la fenêtre
        if self.window_geometry:
            self.root.geometry(self.window_geometry)

        self.ext_vars = {}
        self.excluded_dirs = ['node_modules', '__pycache__', '.git', '__svn__', '__hg__', 'Google Drive']  # Répertoires à exclure

        # Charger les icônes si disponibles et les redimensionner
        self.folder_icon, self.file_icon = self.load_icons(folder_path='icons/folder_icon.png', file_path='icons/file_icon.png', size=(16, 16))

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

        # Charger les préférences utilisateur (déjà effectuée plus haut)
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

        # Création de l'interface (nouvelle organisation avec un PanedWindow et Notebook)
        self.create_widgets()
        self.bind_events()

        # Si un chemin est chargé depuis les préférences, charger l'arborescence
        if self.path_var.get():
            self.on_path_change()

        # Démarrer la boucle de vérification de la queue
        self.root.after(100, self.process_queue)

        # Protocole de fermeture pour sauvegarder les préférences
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Ajouter un ensemble pour les extensions connues
        self.known_text_extensions = {
            '.txt', '.py', '.md', '.c', '.cpp', '.h', '.java', '.js', '.html', '.css',
            '.json', '.xml', '.csv', '.ini', '.cfg', '.bat', '.sh', '.rb', '.php', '.pl',
            '.yaml', '.yml', '.sql', '.r', '.go', '.kt', '.swift', '.ts', '.tsx', '.jsx', '.tex',
            '.log'
        }

        # Créer le menu principal
        self.create_menu()

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
        self.selected_extensions = []
        self.hidden_items_list = []
        
        if os.path.exists(self.preferences_file):
            try:
                with open(self.preferences_file, 'r', encoding='utf-8') as f:
                    prefs = json.load(f)
                self.window_geometry = prefs.get("window_geometry")
                self.path_var.set(prefs.get("last_path", ""))
                self.selected_extensions = prefs.get("selected_extensions", [])
                self.hidden_items_list = prefs.get("hidden_items", [])
                self.current_theme = prefs.get("current_theme", self.current_theme)
                # Ne pas charger is_fullscreen des préférences pour forcer le plein écran
                self.font_size = prefs.get("font_size", self.font_size)
                self.code_font = prefs.get("code_font", self.code_font)
                self.auto_refresh = prefs.get("auto_refresh", self.auto_refresh)
                
                # Charger les extensions connues
                known_extensions = prefs.get("known_extensions", [])
                if known_extensions:
                    self.known_text_extensions = set(known_extensions)
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
                "current_theme": self.current_theme,
                "is_fullscreen": self.is_fullscreen,
                # Sauvegarde des nouveaux paramètres
                "font_size": self.font_size,
                "code_font": self.code_font,
                "auto_refresh": self.auto_refresh,
                "known_extensions": list(self.known_text_extensions)  # Ajout des extensions connues
            }
            with open(self.preferences_file, 'w', encoding='utf-8') as f:
                json.dump(prefs, f, ensure_ascii=False, indent=4)
            logging.info("Préférences sauvegardées avec succès.")
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde des préférences: {e}")

    def create_widgets(self):
        """
        Crée tous les widgets de l'interface utilisateur avec une nouvelle organisation :
        - Une zone supérieure pour le chemin, la navigation et la recherche.
        - Un PanedWindow horizontal séparant l'exploration (arborescence) à gauche
          et un Notebook à droite pour les options (extensions et favoris) et le code généré.
        - Une barre de statut en bas.
        """
        # --- Zone supérieure : chemin et navigation ---
        path_frame = ttk.Frame(self.root, padding="10")
        path_frame.pack(side='top', fill='x')
        ttk.Label(path_frame, text="Chemin du projet:").pack(side='left')
        self.path_entry = ttk.Entry(path_frame, textvariable=self.path_var, width=60)
        self.path_entry.pack(side='left', fill='x', expand=True, padx=5)
        ttk.Button(path_frame, text="Parcourir", command=self.on_browse).pack(side='left', padx=5)
        self.back_button = ttk.Button(path_frame, text="Retour", command=self.on_back, state='disabled')
        self.back_button.pack(side='left', padx=5)
        # Case à cocher pour afficher les éléments masqués en gris
        self.show_hidden = tk.BooleanVar(value=False)
        chk_show_hidden = ttk.Checkbutton(
            path_frame,
            text="Afficher les éléments masqués",
            variable=self.show_hidden,
            command=lambda: [self.refresh_tree(), self.on_generate_code()]
        )
        chk_show_hidden.pack(side='left', padx=5)

        # --- Zone de recherche simple ---
        simple_search_frame = ttk.Frame(self.root, padding="10")
        simple_search_frame.pack(side='top', fill='x')
        ttk.Label(simple_search_frame, text="Rechercher:").pack(side='left')
        self.simple_search_var = tk.StringVar()
        self.simple_search_entry = ttk.Entry(simple_search_frame, textvariable=self.simple_search_var, width=30)
        self.simple_search_entry.pack(side='left', padx=5)
        ttk.Button(simple_search_frame, text="Recherche", command=self.on_search).pack(side='left', padx=5)
        self.toggle_advanced_button = ttk.Button(simple_search_frame, text="Recherche Avancée", command=self.toggle_advanced_search)
        self.toggle_advanced_button.pack(side='left', padx=5)

        # --- PanedWindow principal ---
        self.paned = ttk.PanedWindow(self.root, orient='horizontal')
        self.paned.pack(fill='both', expand=True, padx=10, pady=10)

        # Cadre gauche : arborescence et recherche avancée
        self.left_frame = ttk.Frame(self.paned)
        self.paned.add(self.left_frame, weight=3)

        # Cadre de recherche avancée (initialement masqué)
        self.advanced_search_frame = ttk.LabelFrame(self.left_frame, text="Recherche Avancée", padding="10")
        # Les widgets de recherche avancée :
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
        self.advanced_search_frame.pack_forget()  # Masquer initialement

        # Arborescence dans left_frame
        tree_label = ttk.Label(self.left_frame, text="Architecture du projet:")
        tree_label.pack(side='top', anchor='w', padx=5, pady=(5, 0))
        tree_frame = ttk.Frame(self.left_frame)
        tree_frame.pack(side='top', fill='both', expand=True, padx=5, pady=5)
        self.tree_scroll = ttk.Scrollbar(tree_frame)
        self.tree_scroll.pack(side='right', fill='y')
        self.tree = ttk.Treeview(tree_frame, yscrollcommand=self.tree_scroll.set, selectmode="extended")
        self.tree.pack(side='left', fill='both', expand=True)
        self.tree_scroll.config(command=self.tree.yview)
        self.tree.heading('#0', text='Nom', anchor='w')
        self.tree.column('#0', stretch=True)
        self.tree.tag_configure('hidden', foreground='grey')

        # --- Cadre droit : Notebook pour Options et Code ---
        self.right_frame = ttk.Frame(self.paned)
        self.paned.add(self.right_frame, weight=1)
        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.pack(fill='both', expand=True)

        # Onglet Options : Extensions et Favoris
        self.tab_options = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_options, text="Options")
        # Sélection des extensions
        ext_label = ttk.Label(self.tab_options, text="Sélectionnez les extensions:")
        ext_label.pack(side='top', anchor='w', padx=5, pady=(5, 0))
        
        # Frame pour les extensions avec style
        self.ext_frame = ttk.Frame(self.tab_options, style='Card.TFrame')
        self.ext_frame.pack(side='top', fill='x', padx=10, pady=5)
        
        # Frame pour le bouton de sélection
        ext_button_frame = ttk.Frame(self.tab_options)
        ext_button_frame.pack(side='top', anchor='w', padx=10, pady=5)
        
        self.toggle_select_button = ttk.Button(
            ext_button_frame,
            text="Tout sélectionner",
            style='Toggle.TButton',
            command=self.toggle_all_extensions
        )
        self.toggle_select_button.pack(side='left', padx=5)

        # Favoris
        favorites_label = ttk.Label(self.tab_options, text="Favoris:")
        favorites_label.pack(side='top', anchor='w', padx=5, pady=(10, 0))
        
        # Nouveau container pour les favoris avec une hauteur fixe
        favorites_container = ttk.Frame(self.tab_options)
        favorites_container.pack(side='top', fill='x', padx=5, pady=5)
        
        # Sous-frame pour la liste et la scrollbar
        favorites_frame = ttk.Frame(favorites_container)
        favorites_frame.pack(side='top', fill='both', expand=True)
        
        self.favorites_scroll = ttk.Scrollbar(favorites_frame)
        self.favorites_scroll.pack(side='right', fill='y')
        
        self.favorites_listbox = tk.Listbox(
            favorites_frame, 
            yscrollcommand=self.favorites_scroll.set, 
            selectmode='single',
            height=3  # Hauteur minimale initiale
        )
        self.favorites_listbox.pack(side='left', fill='both', expand=True)
        self.favorites_scroll.config(command=self.favorites_listbox.yview)
        
        # Boutons des favoris
        fav_button_frame = ttk.Frame(favorites_container)
        fav_button_frame.pack(side='bottom', anchor='w', padx=5, pady=5)
        ttk.Button(fav_button_frame, text="Ouvrir le Favori", 
                  command=self.open_selected_favorite).pack(side='left', padx=5)
        ttk.Button(fav_button_frame, text="Supprimer le Favori", 
                  command=self.remove_from_favorites).pack(side='left', padx=5)

        # Liste des fichiers selectionnés
        selected_files_label = ttk.Label(self.tab_options, text="Fichiers Sélectionnés:") # Label pour la liste
        selected_files_label.pack(side='top', anchor='w', padx=5, pady=(10, 0)) # Pack du label

        selected_files_frame = ttk.Frame(self.tab_options) # Frame pour la liste et la scrollbar
        selected_files_frame.pack(side='top', fill='both', expand=True, padx=5, pady=5) # Pack du frame

        self.selected_files_scroll = ttk.Scrollbar(selected_files_frame) # Scrollbar pour la liste
        self.selected_files_scroll.pack(side='right', fill='y') # Pack de la scrollbar

        self.selected_files_listbox = tk.Listbox(
            selected_files_frame, 
            yscrollcommand=self.selected_files_scroll.set, 
            selectmode='extended',  # Change 'single' to 'extended' for multi-selection
            height=5
        )
        self.selected_files_listbox.pack(side='left', fill='both', expand=True)
        
        selected_button_frame = ttk.Frame(self.tab_options) # Frame pour le bouton de deselection
        selected_button_frame.pack(side='top', anchor='w', padx=5, pady=5) # Pack du frame

        ttk.Button(
            selected_button_frame, 
            text="Désélectionner les fichiers", 
            command=self.deselect_multiple_from_selected_listbox
        ).pack(side='left', padx=5)

        # Onglet Code : affichage du code généré
        self.tab_code = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_code, text="Code généré")
        self.code_text = ScrolledText(self.tab_code, height=15, state='disabled')
        # Appliquer la police et taille définie dans les préférences
        self.code_text.config(font=(self.code_font, self.font_size))
        self.code_text.pack(side='top', fill='both', expand=True, padx=5, pady=5)
        button_frame = ttk.Frame(self.tab_code)
        button_frame.pack(side='top', pady=5)
        # Removed: bouton "Générer le code"
        # ttk.Button(button_frame, text="Générer le code", command=self.on_generate_code).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Copier l'arborescence", command=self.copy_tree).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Copier le code", command=self.copy_code).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Tout copier", command=self.copy_all).pack(side='left', padx=5)

        # --- Barre de statut ---
        status_frame = ttk.Frame(self.root, padding="5")
        status_frame.pack(side='bottom', fill='x')
        self.progress = ttk.Progressbar(status_frame, orient='horizontal', mode='determinate')
        self.progress.pack(side='left', fill='x', expand=True, padx=5)
        self.status_var = tk.StringVar(value="Prêt")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var)
        self.status_label.pack(side='right', padx=5)

        # Initialiser le drag & drop
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.on_drop)

        # Création du menu contextuel
        self.create_context_menu()

        # Remplir la liste des favoris
        self.update_favorites_listbox()
        self.update_selected_files_listbox() # Initialisation de la liste des fichiers selectionnés

        # Restaurer les sélections des extensions
        for ext, var in self.ext_vars.items():
            var.set(ext in self.selected_extensions)
            var.trace_add("write", lambda *args: self.update_selected_files()) # Ligne importante : trace sur les variables d'extension

    def bind_events(self):
        """
        Lie les événements aux widgets.
        """
        self.path_entry.bind('<Return>', self.on_path_change)
        self.root.bind('<Control-f>', lambda event: self.search_name_entry.focus_set())
        self.tree.bind('<<TreeviewOpen>>', self.on_treeview_open)
        self.tree.bind('<Double-1>', self.on_treeview_double_click)
        self.root.bind('<Control-o>', lambda event: self.on_browse())
        self.favorites_listbox.bind('<Double-1>', lambda event: self.open_selected_favorite())
        self.selected_files_listbox.bind('<Double-1>', lambda event: self.deselect_from_selected_listbox()) # Double click pour deselectionner
        self.root.bind('<F2>', lambda event: self.rename_item())
        self.root.bind('<Delete>', lambda event: self.delete_item())
        self.root.bind('<Control-Shift-F>', lambda event: self.toggle_advanced_search())
        self.root.bind('<Control-Tab>', lambda event: self.simple_search_entry.focus_set())

    def create_context_menu(self):
        """
        Crée le menu contextuel pour les éléments de l'arborescence.
        """
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Ouvrir", command=self.open_item)
        self.context_menu.add_command(label="Ouvrir avec...", command=self.open_with_item)
        self.context_menu.add_command(label="Renommer", command=self.rename_item)
        self.context_menu.add_command(label="Supprimer", command=self.delete_item)
        self.context_menu.add_command(label="Copier le Chemin", command=self.copy_path)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Ajouter aux Favoris", command=lambda: self.add_to_favorites())
        self.context_menu.add_command(label="Masquer", command=self.hide_selected_items)

        # Modification ici pour gerer la selection/deselection via context menu
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Sélectionner", command=self.select_from_context_menu)
        self.context_menu.add_command(label="Désélectionner", command=self.deselect_from_context_menu)

        self.tree.bind("<Button-3>", self.show_context_menu)  # Windows/Linux
        self.tree.bind("<Button-2>", self.show_context_menu)  # macOS

    def show_context_menu(self, event):
        """
        Affiche le menu contextuel à la position du curseur.
        """
        selected_item = self.tree.identify_row(event.y)
        if (selected_item):
            self.tree.selection_set(selected_item)
            item_values = self.tree.item(selected_item, 'values')
            if (item_values):
                path = item_values[0]
                is_selected_manually = path in self.manual_selected_files

                if (is_selected_manually):
                    self.context_menu.entryconfigure("Sélectionner", state="disabled") # Desactiver "Sélectionner" si deja selectionné
                    self.context_menu.entryconfigure("Désélectionner", state="normal") # Activer "Désélectionner"
                else:
                    self.context_menu.entryconfigure("Sélectionner", state="normal")   # Activer "Sélectionner"
                    self.context_menu.entryconfigure("Désélectionner", state="disabled") # Desactiver "Désélectionner" si pas selectionné

            if (item_values):
                path = item_values[0]
                if (path in self.favorites):
                    self.context_menu.entryconfigure("Ajouter aux Favoris", label="Retirer des Favoris",
                                                     command=lambda: self.remove_from_favorites(path))
                else:
                    self.context_menu.entryconfigure("Ajouter aux Favoris", label="Ajouter aux Favoris",
                                                     command=lambda: self.add_to_favorites(path))
                self.context_menu.post(event.x_root, event.y_root)

    def select_from_context_menu(self):
        selected_item = self.tree.selection()
        if (selected_item):
            item_values = self.tree.item(selected_item[0], 'values')
            if (item_values):
                path = item_values[0]
                self.add_selected_file(path)

    def deselect_from_context_menu(self):
        selected_item = self.tree.selection()
        if (selected_item):
            item_values = self.tree.item(selected_item[0], 'values')
            if (item_values):
                path = item_values[0]
                self.remove_selected_file(path)


    def hide_selected_items(self):
        """
        Masque les fichiers ou dossiers sélectionnés dans l'arborescence.
        """
        selected_items = self.tree.selection()
        for item in selected_items:
            path = self.tree.item(item, 'values')[0]
            self.hidden_items.add(path)
        self.save_preferences()
        self.refresh_tree()
        # Update generated code when items are hidden
        self.on_generate_code()

    def refresh_tree(self):
        """
        Réaffiche l'arborescence en tenant compte des éléments masqués et de la préférence d'affichage.
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

    def open_with_item(self):
        """
        Ouvre le fichier ou dossier sélectionné avec une commande personnalisée.
        """
        selected_items = self.tree.selection()
        if selected_items:
            item_values = self.tree.item(selected_items[0], 'values')
            if not item_values:
                messagebox.showwarning("Avertissement", "L'élément sélectionné n'a pas de chemin valide.")
                return
            path = item_values[0]
            command = simpledialog.askstring("Ouvrir avec...", "Entrez la commande pour ouvrir le fichier:", initialvalue="code")
            if command:
                try:
                    subprocess.run([command, path], check=True)
                except Exception as e:
                    logging.error(f"Erreur lors de l'ouverture avec '{command}' de '{path}': {e}")
                    messagebox.showerror("Erreur", f"Erreur lors de l'ouverture avec '{command}': {e}")

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
                    self.path_to_item[new_path] = self.path_to_item.pop(old_path)
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
                            shutil.rmtree(path)
                        else:
                            os.remove(path)
                        self.tree.delete(item)
                        logging.info(f"Supprimé '{path}'")
                        if path in self.path_to_item:
                            del self.path_to_item[path]
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
        """
        parts = path.split(os.sep)
        if len(parts) > max_depth:
            return os.sep.join(['...'] + parts[-max_depth:])
        else:
            return path

    def update_favorites_listbox(self):
        """
        Met à jour la liste des favoris dans l'interface en affichant des chemins tronqués 
        et ajuste la hauteur en fonction du contenu.
        """
        self.favorites_listbox.delete(0, tk.END)
        self.favorites_list_sorted = sorted(self.favorites)
        
        # Insérer les éléments
        for fav in self.favorites_list_sorted:
            display_text = self.get_truncated_path(fav)
            self.favorites_listbox.insert(tk.END, display_text)
        
        # Ajuster la hauteur
        num_items = len(self.favorites_list_sorted)
        current_height = self.favorites_listbox.cget('height')
        
        # Calculer la nouvelle hauteur (max 10 éléments)
        new_height = min(max(num_items, 3), 10)  # Minimum 3 lignes, maximum 10 lignes
        
        if int(current_height) != new_height:
            self.favorites_listbox.configure(height=new_height)

    def update_selected_files_listbox(self):
        """
        Met à jour la liste des fichiers selectionnés dans l'interface en affichant des chemins tronqués.
        """
        self.selected_files_listbox.delete(0, tk.END)
        selected_files_list_sorted = sorted(self.selected_files.keys()) # Tri par chemin
        for file_path in selected_files_list_sorted:
            display_text = self.get_truncated_path(file_path)
            self.selected_files_listbox.insert(tk.END, display_text)

    def deselect_from_selected_listbox(self):
        """
        Deselectionne un fichier via la liste des fichiers selectionnés.
        """
        selection_indices = self.selected_files_listbox.curselection()
        if selection_indices:
            index = selection_indices[0]
            truncated_path = self.selected_files_listbox.get(index)
            full_path_to_remove = None
            for full_path in self.selected_files.keys(): # Recherche du path complet correspondant au path tronqué
                if self.get_truncated_path(full_path) == truncated_path:
                    full_path_to_remove = full_path
                    break
            if full_path_to_remove:
                self.remove_selected_file(full_path_to_remove)
                self.update_selected_files_listbox() # Mise à jour de la liste après deselection

    def deselect_multiple_from_selected_listbox(self):
        """
        Désélectionne tous les fichiers sélectionnés dans la listbox.
        """
        selection_indices = self.selected_files_listbox.curselection()
        if not selection_indices:
            messagebox.showwarning("Attention", "Veuillez sélectionner au moins un fichier à désélectionner.")
            return

        paths_to_remove = []
        for index in selection_indices:
            truncated_path = self.selected_files_listbox.get(index)
            # Recherche des chemins complets correspondants
            for full_path in self.selected_files.keys():
                if self.get_truncated_path(full_path) == truncated_path:
                    paths_to_remove.append(full_path)
                    break

        # Désélection de tous les fichiers trouvés
        for path in paths_to_remove:
            self.remove_selected_file(path)

        self.update_selected_files_listbox()
        self.on_generate_code()  # Régénérer le code après la désélection

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
                self.highlight_path(path)
        else:
            messagebox.showwarning("Avertissement", "Veuillez sélectionner un favori à ouvrir.")

    def highlight_path(self, path, delay=500):
        """
        Surligne l'élément spécifié dans le Treeview.
        """
        item = self.path_to_item.get(path)
        if item:
            self.highlight_treeview_item(item)
        else:
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
            messagebox.showerror("Erreur lors de la copie de l'arborescence: {e}")

    def get_full_treeview_items(self):
        """
        Récupère tous les éléments de l'arborescence en parcourant le système de fichiers.
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
                if abs_path in self.hidden_items and not self.show_hidden.get():
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
            messagebox.showerror("Erreur lors de la copie du code: {e}")

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
            messagebox.showerror("Erreur lors de la copie de l'ensemble: {e}")

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
            self.tree.delete(*self.tree.get_children())
            self.path_to_item.clear()
            self.progress['value'] = 0
            self.status_var.set("Chargement de l'arborescence...")
            logging.info(f"Chargement du projet à partir de {current_path}")
            self.is_initial_loading = True
            threading.Thread(target=self.build_treeview_thread, args=(current_path,), daemon=True).start()
            threading.Thread(target=self.update_extensions, args=(current_path,), daemon=True).start()
            self.selected_files = {} # Reset selected files on path change.
            self.manual_selected_files = {} # Reset manual selection too
            self.on_generate_code() # Generate code after path change
        else:
            self.tree.delete(*self.tree.get_children())
            for widget in self.ext_frame.winfo_children():
                widget.destroy()
            self.ext_vars.clear()
            self.path_to_item.clear()

    def build_treeview_thread(self, path):
        """
        Construit l'arborescence du projet dans un thread séparé.
        """
        try:
            self.queue.put(('progress_max', 100))
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
            if abs_path in self.hidden_items and not self.show_hidden.get():
                continue
            tags = ()
            if abs_path in self.hidden_items:
                tags = ('hidden',)
            try:
                is_dir = os.path.isdir(abs_path)
                if is_dir:
                    node = self.tree.insert(parent, 'end', text=item, open=False, values=[abs_path],
                                            image=self.folder_icon if self.folder_icon else '', tags=tags)
                    self.tree.insert(node, 'end')
                else:
                    node = self.tree.insert(parent, 'end', text=item, values=[abs_path],
                                            image=self.file_icon if self.file_icon else '', tags=tags)
                self.path_to_item[abs_path] = node
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
        children = self.tree.get_children(node)
        for child in children:
            if not self.tree.get_children(child):
                self.tree.delete(child)
        item_values = self.tree.item(node, 'values')
        if not item_values:
            return
        current_path = item_values[0]
        logging.info(f"Chargement du sous-dossier: {current_path}")
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
            current_root = self.path_var.get()
            self.history_stack.append(current_root)
            self.back_button.config(state='normal')
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
            '.yaml', '.yml', '.sql', '.r', '.go', '.kt', '.swift', '.ts', '.tsx', '.jsx', '.tex',
            '.log'  # Ajout de l'extension .log
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
        # Appeler automatiquement la génération de code après modification
        self.update_selected_files()

    def deselect_all_exts(self):
        """
        Désélectionne toutes les extensions.
        """
        for var in self.ext_vars.values():
            var.set(False)
        # Appeler automatiquement la génération de code après modification
        self.update_selected_files()

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

    def schedule_generate_code(self, delay=100):
        """Debounce multiple changes by canceling previous and scheduling one call.""" 
        if self.generate_code_after_id:
            self.root.after_cancel(self.generate_code_after_id)
        self.generate_code_after_id = self.root.after(delay, self.on_generate_code)

    # Modified update_selected_files to combine extension-based and manual selections.
    def update_selected_files(self):
        print("update_selected_files CALLED from checkbox change!") # Debug print
        print("update_selected_files called") # Debug print
        repo_path = self.path_var.get()
        selected_exts = [ext for ext, var in self.ext_vars.items() if var.get()]
        print(f"Selected extensions: {selected_exts}") # Debug print
        dynamic_selected = {}
        # Parcours du répertoire
        for root_dir, dirs, files in os.walk(repo_path):
            # If a parent folder was manually selected, add all its files.
            if root_dir in self.manual_selected_files: # Changed to check root_dir in manual_selected_files keys
                for file in files:
                    dynamic_selected[os.path.join(root_dir, file)] = True
            else:
                for file in files:
                    file_path = os.path.join(root_dir, file)
                    if os.path.splitext(file)[1] in selected_exts:
                        dynamic_selected[file_path] = True
                        print(f"File with selected extension found: {file_path}") # Debug print
        # Combine computed selections with manual selections.
        self.selected_files = {}
        self.selected_files.update(dynamic_selected)
        self.selected_files.update(self.manual_selected_files)
        print("Selected Files:", self.selected_files) # Debug print
        self.update_selected_files_listbox() # Mettre à jour la liste des fichiers selectionnés
        self.schedule_generate_code()
        
        # Mettre à jour le texte du bouton en fonction de l'état des extensions
        all_selected = all(var.get() for var in self.ext_vars.values())
        self.toggle_select_button.config(
            text="Tout désélectionner" if all_selected else "Tout sélectionner"
        )

    # Update manual file selection to use the new manual_selected_files dict.
    def add_selected_file(self, path):
        print(f"add_selected_file called with path: {path}") # Debug print
        self.manual_selected_files[path] = True
        self.update_selected_files()

    def remove_selected_file(self, path):
        print(f"remove_selected_file called with path: {path}") # Debug print
        if path in self.manual_selected_files or path in self.selected_files: # Correction ici pour gerer la deselection manuelle et par extention
            if path in self.manual_selected_files:
                del self.manual_selected_files[path]
            if path in self.selected_files:
                del self.selected_files[path]
        self.update_selected_files()

    # The on_generate_code method is called via schedule_generate_code
    def on_generate_code(self):
        print("on_generate_code called") # Debug print
        self.code_text.configure(state='normal')
        self.code_text.delete('1.0', tk.END)
        code = ""
        first_file = True # Flag to track the first file
        for file_path in self.selected_files:
            if not first_file:
                code += "\n--------------------------\n\n" # Separator line with spaces
            else:
                first_file = False # Set flag to false after the first file

            code += f"{file_path}\n" # Display path
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    code += content + "\n\n" # Add content with extra space after
            except Exception as e:
                code += f"--- Erreur de lecture du fichier: {e} ---\n\n" # Error message with extra space

        self.code_text.insert('1.0', code)
        self.code_text.configure(state='disabled') # Disable after writing

    def on_search(self):
        """
        Recherche simple par nom via un thread séparé.
        """
        query = self.simple_search_var.get().strip()
        if not query:
            messagebox.showwarning("Attention", "Veuillez entrer un terme de recherche.")
            return
        threading.Thread(target=self.search_thread_simple, args=(query,), daemon=True).start()

    def search_thread_simple(self, query):
        """
        Thread pour effectuer une recherche simple par nom.
        """
        try:
            self.queue.put(('status', "Recherche en cours..."))
            path = self.path_var.get()
            matches = []
            for root_dir, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
                for file in files:
                    file_path = os.path.join(root_dir, file)
                    if query.lower() in file.lower():
                        matches.append(file_path)
            self.queue.put(('search_results', matches))
            logging.info(f"Recherche terminée. {len(matches)} éléments trouvés.")
            self.queue.put(('status', "Terminé"))
        except Exception as e:
            logging.error(f"Erreur lors de la recherche: {e}")
            self.queue.put(('error_message', f"Erreur lors de la recherche: {e}"))
            self.queue.put(('status', "Erreur lors de la recherche"))

    def on_advanced_search(self):
        """
        Recherche avancée basée sur plusieurs critères.
        """
        query_name = self.search_name_var.get().strip().lower()
        query_ext = self.search_ext_var.get().strip().lower()
        query_date = self.search_date_var.get().strip()
        if query_date:
            try:
                datetime.datetime.strptime(query_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Erreur de format", "La date doit être au format YYYY-MM-DD.")
                return
        if query_ext:
            exts = [e.strip() for e in query_ext.split(',')]
            for ext in exts:
                if not ext.startswith('.'):
                    messagebox.showerror("Erreur de format", f"L'extension '{ext}' n'est pas valide. Elle doit commencer par un point.")
                    return
        threading.Thread(target=self.search_thread_advanced, args=(query_name, query_ext, query_date), daemon=True).start()

    def search_thread_advanced(self, query_name, query_ext, query_date):
        """
        Thread pour effectuer la recherche avancée.
        """
        try:
            self.queue.put(('status', "Recherche en cours..."))
            path = self.path_var.get()
            matches = []
            for root_dir, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
                for file in files:
                    file_path = os.path.join(root_dir, file)
                    basename = file.lower()
                    if query_name and query_name not in basename:
                        continue
                    if query_ext:
                        file_ext = os.path.splitext(file)[1].lower()
                        ext_list = [e.strip().lower() for e in query_ext.split(',')]
                        if file_ext not in ext_list:
                            continue
                    if query_date:
                        try:
                            date_obj = datetime.datetime.strptime(query_date, "%Y-%m-%d")
                            mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                            if mod_time < date_obj:
                                continue
                        except ValueError:
                            continue
                    matches.append(file_path)
            self.queue.put(('search_results', matches))
            logging.info(f"Recherche terminée. {len(matches)} éléments trouvés.")
            self.queue.put(('status', "Terminé"))
        except Exception as e:
            logging.error(f"Erreur lors de la recherche avancée: {e}")
            self.queue.put(('error_message', f"Erreur lors de la recherche avancée: {e}"))
            self.queue.put(('status', "Erreur lors de la recherche avancée"))

    def show_search_results(self, matches):
        """
        Affiche les résultats de la recherche dans une nouvelle fenêtre.
        """
        results_window = tk.Toplevel(self.root)
        results_window.title("Résultats de la Recherche")
        results_window.geometry("800x600")
        ttk.Label(results_window, text=f"Résultats de la recherche ({len(matches)} éléments trouvés):").pack(pady=5)
        results_frame = ttk.Frame(results_window)
        results_frame.pack(fill='both', expand=True, padx=10, pady=10)
        results_scroll = ttk.Scrollbar(results_frame)
        results_scroll.pack(side='right', fill='y')
        results_listbox = tk.Listbox(results_frame, yscrollcommand=results_scroll.set)
        results_listbox.pack(side='left', fill='both', expand=True)
        results_scroll.config(command=results_listbox.yview)
        for path in matches:
            results_listbox.insert(tk.END, path)
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
        Affiche l'élément sélectionné dans le Treeview en le surlignant.
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
                    self.highlight_path(path)
                else:
                    messagebox.showerror("Erreur", f"Le chemin '{path}' n'existe plus.")
        else:
            messagebox.showwarning("Avertissement", "Veuillez sélectionner un élément à afficher.")

    def process_queue(self):
        """
        Traite les éléments de la queue pour mettre à jour l'interface de manière thread-safe.
        """
        try:
            while True:
                task = self.queue.get_nowait()
                if task[0] == 'insert':
                    _, parent, item, abs_path, is_dir = task
                    if is_dir:
                        node = self.tree.insert(parent, 'end', text=item, open=False, values=[abs_path],
                                                image=self.folder_icon if self.folder_icon else '')
                        self.tree.insert(node, 'end')
                    else:
                        node = self.tree.insert(parent, 'end', text=item, values=[abs_path],
                                                image=self.file_icon if self.file_icon else '')
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
                    # Ajout d'une fonction lambda pour le callback immédiat
                    var.trace_add("write", lambda *args: self.on_extension_change())
                    cb = ttk.Checkbutton(self.ext_frame, text=ext, variable=var)
                    cb.pack(anchor='w', pady=2)
                    self.ext_vars[ext] = var
                elif task[0] == 'delete':
                    _, item_id = task
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

        if self.is_initial_loading and self.progress['value'] >= self.progress['maximum']:
            self.status_var.set("Chargement terminé")
            self.is_initial_loading = False

    def on_extension_change(self):
        """
        Callback appelé immédiatement quand une checkbox d'extension change d'état
        """
        self.update_selected_files()
        self.on_generate_code()  # Force la mise à jour du code généré

    def highlight_treeview_item(self, item):
        """
        Surligne l'élément dans le Treeview et déplie les parents.
        """
        parent = self.tree.parent(item)
        while parent:
            self.tree.item(parent, open=True)
            parent = self.tree.parent(parent)
        self.tree.selection_set(item)
        self.tree.focus(item)
        self.tree.see(item)
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
        Trouve l'élément dans le Treeview correspondant au chemin donné.
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
                self.on_treeview_open(None)

    def on_drop(self, event):
        """
        Gère le dépôt lors du glisser-déposer.
        """
        files = self.root.splitlist(event.data)
        if files:
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
        Affiche ou masque la recherche avancée.
        """
        if self.advanced_search_frame.winfo_ismapped():
            self.advanced_search_frame.pack_forget()
            self.toggle_advanced_button.config(text="Recherche Avancée")
        else:
            self.advanced_search_frame.pack(side='top', fill='x', padx=5, pady=5)
            self.toggle_advanced_button.config(text="Masquer Recherche Avancée")

    def toggle_theme(self):
        """
        Bascule entre les thèmes clair et sombre.
        """
        if self.current_theme == 'flatly':
            self.current_theme = 'darkly'
        else:
            self.current_theme = 'flatly'
        style = Style(theme=self.current_theme)
        self.save_preferences()

    def toggle_fullscreen(self):
        """
        Bascule le mode plein écran.
        """
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes('-fullscreen', self.is_fullscreen)
        self.save_preferences()

    def create_menu(self):
        """Crée la barre de menu principale."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Menu Fichier
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Fichier", menu=file_menu)
        file_menu.add_command(label="Ouvrir...", command=self.on_browse)
        file_menu.add_separator()
        file_menu.add_command(label="Quitter", command=self.on_close)
        
        # Menu Edition
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edition", menu=edit_menu)
        edit_menu.add_command(label="Paramètres", command=self.open_settings)

    def open_settings(self):
        """Ouvre la fenêtre des paramètres."""
        settings_window = SettingsWindow(self.root, self)  # Passer self.root comme parent et self comme app
        settings_window.transient(self.root)
        settings_window.grab_set()

    def toggle_all_extensions(self):
        """
        Bascule entre la sélection et la désélection de toutes les extensions.
        """
        # Vérifier si toutes les extensions sont sélectionnées
        all_selected = all(var.get() for var in self.ext_vars.values())
        
        # Basculer l'état
        new_state = not all_selected
        for var in self.ext_vars.values():
            var.set(new_state)
            
        # Mettre à jour le texte du bouton
        self.toggle_select_button.config(
            text="Tout désélectionner" if new_state else "Tout sélectionner"
        )
        
        # Mettre à jour les fichiers sélectionnés
        self.update_selected_files()

class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, app):
        """
        Initialise la fenêtre des paramètres
        :param parent: La fenêtre parente (root)
        :param app: L'instance de ProjectExplorerApp
        """
        super().__init__(parent)
        self.app = app  # Stocker la référence à l'application principale
        self.title("Paramètres")
        self.geometry("600x700")
        
        # Création des onglets de paramètres
        notebook = ttk.Notebook(self)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Onglet Apparence
        appearance_frame = ttk.Frame(notebook)
        notebook.add(appearance_frame, text="Apparence")
        
        # Thème
        ttk.Label(appearance_frame, text="Thème:").pack(anchor='w', padx=5, pady=5)
        self.theme_var = tk.StringVar(value=self.app.current_theme)  # Utiliser app au lieu de parent
        themes_frame = ttk.Frame(appearance_frame)
        themes_frame.pack(fill='x', padx=5)
        ttk.Radiobutton(themes_frame, text="Clair", value="flatly", 
                       variable=self.theme_var).pack(side='left', padx=5)
        ttk.Radiobutton(themes_frame, text="Sombre", value="darkly", 
                       variable=self.theme_var).pack(side='left', padx=5)
        
        # Police et taille
        ttk.Label(appearance_frame, text="Police de code:").pack(anchor='w', padx=5, pady=5)
        fonts = list(font.families())
        fonts.sort()
        self.font_var = tk.StringVar(value=self.app.code_font)
        font_combo = ttk.Combobox(appearance_frame, textvariable=self.font_var, values=fonts)
        font_combo.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(appearance_frame, text="Taille de police:").pack(anchor='w', padx=5, pady=5)
        self.font_size_var = tk.IntVar(value=self.app.font_size)
        font_size_frame = ttk.Frame(appearance_frame)
        font_size_frame.pack(fill='x', padx=5)
        ttk.Entry(font_size_frame, textvariable=self.font_size_var, width=5).pack(side='left')
        
        # Onglet Extensions
        extensions_frame = ttk.Frame(notebook)
        notebook.add(extensions_frame, text="Extensions")
        
        # Liste des extensions connues
        ttk.Label(extensions_frame, text="Extensions reconnues:").pack(anchor='w', padx=5, pady=5)
        
        list_frame = ttk.Frame(extensions_frame)
        list_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.extensions_list = tk.Listbox(list_frame, selectmode='single')
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.extensions_list.yview)
        self.extensions_list.configure(yscrollcommand=scrollbar.set)
        
        self.extensions_list.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Boutons pour gérer les extensions
        btn_frame = ttk.Frame(extensions_frame)
        btn_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(btn_frame, text="Ajouter", command=self.add_extension).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Supprimer", command=self.remove_extension).pack(side='left', padx=5)
        
        # Remplir la liste avec les extensions existantes
        for ext in sorted(self.app.known_text_extensions):
            self.extensions_list.insert(tk.END, ext)
        
        # Boutons de validation
        buttons_frame = ttk.Frame(self)
        buttons_frame.pack(fill='x', padx=10, pady=10)
        ttk.Button(buttons_frame, text="Appliquer", command=self.apply_settings).pack(side='right', padx=5)
        ttk.Button(buttons_frame, text="Fermer", command=self.destroy).pack(side='right', padx=5)

    def add_extension(self):
        extension = simpledialog.askstring("Ajouter une extension", 
                                         "Entrez l'extension (avec le point, ex: .txt):")
        if extension:
            if not extension.startswith('.'):
                extension = '.' + extension
            extension = extension.lower()
            if extension not in self.app.known_text_extensions:
                self.app.known_text_extensions.add(extension)
                self.extensions_list.insert(tk.END, extension)
                self.app.save_preferences()

    def remove_extension(self):
        selection = self.extensions_list.curselection()
        if selection:
            ext = self.extensions_list.get(selection[0])
            self.app.known_text_extensions.remove(ext)
            self.extensions_list.delete(selection[0])
            self.app.save_preferences()

    def apply_settings(self):
        # Appliquer le thème
        new_theme = self.theme_var.get()
        if new_theme != self.app.current_theme:  # Utiliser app au lieu de parent
            self.app.current_theme = new_theme
            style = Style(theme=new_theme)
        
        # Appliquer la police et la taille
        self.app.code_font = self.font_var.get()
        self.app.font_size = self.font_size_var.get()
        self.app.code_text.configure(font=(self.app.code_font, self.app.font_size))
        
        # Sauvegarder les préférences
        self.app.save_preferences()
        
        messagebox.showinfo("Succès", "Les paramètres ont été appliqués avec succès!")

if __name__ == "__main__":
    try:
        # 1. Créer une fenêtre TkinterDnD
        root = TkinterDnD.Tk()
        
        # 2. Créer un style ttkbootstrap mais capturer les erreurs silencieusement
        try:
            style = Style(theme='darkly')
            style.configure('Treeview', rowheight=25)
            style.configure('Card.TFrame', borderwidth=1, relief='solid')
            style.configure('Card.TLabelframe', borderwidth=1, relief='solid')
            style.configure('Toggle.TButton', borderwidth=1, relief='solid', padding=5)
            style.configure('Action.TButton', borderwidth=1, relief='solid', padding=5)
        except Exception as style_error:
            # En cas d'erreur avec ttkbootstrap, utiliser le style ttk standard
            style = ttk.Style()
            style.theme_use('clam')  # Utiliser un thème ttk standard
            logging.warning(f"Utilisation du style ttk standard : {style_error}")
        
        # 3. Initialiser l'application
        app = ProjectExplorerApp(root)
        root.mainloop()
        
    except Exception as e:
        logging.error(f"Erreur lors de l'initialisation: {e}")
        messagebox.showerror("Erreur", f"Erreur lors de l'initialisation: {e}")
