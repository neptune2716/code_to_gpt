// Register an Alpine.js component for code panel
document.addEventListener('alpine:init', () => {
  Alpine.data('codePanel', () => ({
    tab: 'options', // Default to options tab
    active: 'px-4 py-2 rounded bg-blue-600 text-white',
    code: '// Select files and click the Code tab to generate.',
    treeStructure: '// Tree structure not generated yet.',

    fetchCode() {
      this.tab = 'code'; // Switch to code tab when fetching
      const tree = $('#tree').jstree(true);
      if (!tree) {
        this.code = '// Tree not initialized yet.';
        return;
      }
      // Get IDs of checked nodes that are files (not folders)
      const selected = tree.get_checked(false).filter(id => {
        const node = tree.get_node(id);
        // Check if it's a file (leaf node)
        return node && !tree.is_parent(node);
      });

      if (!selected.length) {
        this.code = '// No files selected or checked in the tree.';
        return;
      }

      this.code = '// Loading code...'; // Show loading state
      fetch(`/api/code?paths=${encodeURIComponent(JSON.stringify(selected))}`)
        .then(res => res.json())
        .then(data => {
          this.code = data.code || '// Failed to load code.';
        })
        .catch(err => {
          console.error('Failed to fetch code:', err);
          this.code = '// Error fetching code.';
        });
    },

    async fetchTreeStructure() {
      // Fetch tree structure from backend
      try {
        const response = await fetch('/api/tree_structure'); // New endpoint needed
        const data = await response.json();
        this.treeStructure = data.tree || '// Failed to get tree structure';
      } catch (error) {
        console.error('Failed to fetch tree structure:', error);
        this.treeStructure = '// Error fetching tree structure';
      }
    },

    copyToClipboard(text) {
      navigator.clipboard.writeText(text).then(() => {
        alert('Copied to clipboard!'); // Simple feedback
      }).catch(err => {
        console.error('Failed to copy text: ', err);
        alert('Failed to copy to clipboard.');
      });
    },

    async copyTree() {
      await this.fetchTreeStructure();
      this.copyToClipboard(this.treeStructure);
    },

    copyCode() {
      this.copyToClipboard(this.code);
    },

    async copyAll() {
      await this.fetchTreeStructure();
      const combined = `${this.treeStructure}\n\n${this.code}`;
      this.copyToClipboard(combined);
    }
  }));

  // Register options panel component
  Alpine.data('optionsPanel', () => ({
    known_extensions: [],
    selected_extensions: [],
    favorites: [],
    newFav: '',
    hidden: [],
    newHidden: '',
    async fetchOptions() {
      try {
        const res = await fetch('/api/options');
        const data = await res.json();
        this.known_extensions = data.known_extensions;
        this.selected_extensions = data.selected_extensions;
        this.favorites = data.favorites;
      } catch (e) {
        console.error('Failed to load options', e);
      }
    },
    async fetchHidden() {
      try {
        const res = await fetch('/api/options/hidden');
        this.hidden = await res.json();
      } catch (e) {
        console.error('Failed to load hidden items', e);
      }
    },
    selectAll() {
      this.selected_extensions = [...this.known_extensions];
      this.saveExtensions(); // Save immediately and refresh tree
    },
    clearAll() {
      this.selected_extensions = [];
      this.saveExtensions(); // Save immediately and refresh tree
    },
    async saveExtensions() {
      try {
        await fetch('/api/options/extensions', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({extensions: this.selected_extensions})
        });
        // Refresh file tree after saving filters
        setTimeout(() => {
          const tree = $('#tree').jstree(true);
          if (tree) {
            tree.refresh();
          }
        }, 0);
      } catch (e) {
        console.error('Failed to save extensions', e);
      }
    },
    init() {
      this.$watch('selected_extensions', () => {
        clearTimeout(this.saveTimeout);
        this.saveTimeout = setTimeout(() => {
          this.saveExtensions();
        }, 500); // Save after 500ms of inactivity
      });
    },
    saveTimeout: null,
    async addFavorite() {
      if (!this.newFav) return;
      if (!this.favorites.includes(this.newFav)) {
        this.favorites.push(this.newFav);
        this.favorites.sort(); // Keep sorted
        await this._saveFavs();
      }
      this.newFav = '';
    },
    async removeFavorite(fav) {
      this.favorites = this.favorites.filter(f => f !== fav);
      await this._saveFavs();
    },
    async _saveFavs() {
      try {
        await fetch('/api/options/favorites', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({favorites: this.favorites})
        });
      } catch (e) {
        console.error('Failed to save favorites', e);
      }
    },
    async addHidden() {
      if (!this.newHidden) return;
      if (!this.hidden.includes(this.newHidden)) {
        this.hidden.push(this.newHidden);
        this.hidden.sort(); // Keep sorted
        await this._saveHidden();
      }
      this.newHidden = '';
    },
    async removeHidden(hid) {
      this.hidden = this.hidden.filter(h => h !== hid);
      await this._saveHidden();
    },
    async _saveHidden() {
      try {
        await fetch('/api/options/hidden', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({hidden: this.hidden})
        });
        if (!window.showHidden) {
          setTimeout(() => {
            const tree = $('#tree').jstree(true);
            if (tree) {
              tree.refresh();
            }
          }, 0);
        }
      } catch (e) {
        console.error('Failed to save hidden items', e);
      }
    }
  }));
});
