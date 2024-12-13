import json
import os
import logging

class ConfigManager:
    def __init__(self, filename='preferences.json'):
        self.filename = filename
        self.window_geometry = "1400x800+0+0"
        self.last_path = ""
        self.selected_extensions = []
        self.hidden_items_list = []
        self.current_theme = 'flatly'
        self.is_fullscreen = False
        self.load_preferences()

    def load_preferences(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    prefs = json.load(f)
                self.window_geometry = prefs.get("window_geometry", "1400x800+0+0")
                self.last_path = prefs.get("last_path", "")
                self.selected_extensions = prefs.get("selected_extensions", [])
                self.hidden_items_list = prefs.get("hidden_items", [])
                self.current_theme = prefs.get("current_theme", "flatly")
                self.is_fullscreen = prefs.get("is_fullscreen", False)
            except Exception as e:
                logging.error(f"Erreur chargement prefs: {e}")

    def save_preferences(self, window_geometry, last_path, selected_extensions, hidden_items, current_theme, is_fullscreen):
        prefs = {
            "window_geometry": window_geometry,
            "last_path": last_path,
            "selected_extensions": selected_extensions,
            "hidden_items": hidden_items,
            "current_theme": current_theme,
            "is_fullscreen": is_fullscreen
        }
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(prefs, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.error(f"Erreur sauvegarde prefs: {e}")
