import os
import datetime
import logging
from tkinter import messagebox

class SearchManager:
    def __init__(self, base_path, excluded_dirs, hidden_manager):
        self.base_path = base_path
        self.excluded_dirs = excluded_dirs
        self.hidden_manager = hidden_manager

    def validate_criteria(self, name, ext, date):
        if date:
            try:
                datetime.datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                return "Date invalide (YYYY-MM-DD)."
        if ext:
            for e in [x.strip() for x in ext.split(',')]:
                if not e.startswith('.'):
                    return f"Extension '{e}' invalide."
        return None

    def search_thread(self, queue, name, ext, date):
        try:
            queue.put(('status', "Recherche..."))
            matches = []
            name = name.lower() if name else ""
            exts = [e.strip().lower() for e in ext.split(',')] if ext else []
            date_obj = None
            if date:
                date_obj = datetime.datetime.strptime(date, "%Y-%m-%d")

            for root_dir, dirs, files in os.walk(self.base_path):
                dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
                for file in files:
                    file_path = os.path.join(root_dir, file)
                    if self.hidden_manager.is_hidden(file_path):
                        continue
                    basename = file.lower()

                    if name and name not in basename:
                        continue
                    if exts and os.path.splitext(file)[1].lower() not in exts:
                        continue
                    if date_obj:
                        mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                        if mod_time < date_obj:
                            continue
                    matches.append(file_path)

            queue.put(('search_results', matches))
            queue.put(('status', "Terminé"))
        except Exception as e:
            logging.error(f"Erreur recherche: {e}")
            queue.put(('error_message', f"Erreur recherche: {e}"))
            queue.put(('status', "Erreur"))
