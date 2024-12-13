import json
import os
import logging

class FavoritesManager:
    def __init__(self, filename='favorites.json'):
        self.filename = filename
        self.favorites = set()
        self.load_favorites()

    def load_favorites(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    self.favorites = set(json.load(f))
            except Exception as e:
                logging.error(f"Erreur chargement favoris: {e}")

    def save_favorites(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(list(self.favorites), f, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.error(f"Erreur sauvegarde favoris: {e}")

    def add_favorite(self, path):
        self.favorites.add(path)
        self.save_favorites()

    def remove_favorite(self, path):
        if path in self.favorites:
            self.favorites.remove(path)
            self.save_favorites()
