import logging
from tkinter import messagebox
from tkinterdnd2 import TkinterDnD
from app import ProjectExplorerApp

if __name__ == "__main__":
    try:
        root = TkinterDnD.Tk()
        app = ProjectExplorerApp(root)
        root.mainloop()
    except Exception as e:
        logging.error(f"Erreur lors de l'initialisation: {e}")
        messagebox.showerror("Erreur", f"Erreur lors de l'initialisation: {e}")
