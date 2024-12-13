import json
import os
import logging

class HiddenItemsManager:
    def __init__(self, filename='hidden_items.json'):
        self.filename = filename
        self.hidden_items = set()
        self.load_hidden_items()

    def load_hidden_items(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    self.hidden_items = set(json.load(f))
            except Exception as e:
                logging.error(f"Erreur chargement masqués: {e}")

    def save_hidden_items(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(list(self.hidden_items), f, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.error(f"Erreur sauvegarde masqués: {e}")

    def add_hidden(self, path):
        self.hidden_items.add(path)
        self.save_hidden_items()

    def remove_hidden(self, path):
        if path in self.hidden_items:
            self.hidden_items.remove(path)
            self.save_hidden_items()

    def is_hidden(self, path):
        path = os.path.abspath(path)
        for hidden_path in self.hidden_items:
            hidden_path = os.path.abspath(hidden_path)
            if path == hidden_path or path.startswith(hidden_path + os.sep):
                return True
        return False
