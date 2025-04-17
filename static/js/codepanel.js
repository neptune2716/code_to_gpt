// Register an Alpine.js component for code panel
document.addEventListener('alpine:init', () => {
  Alpine.data('codePanel', () => ({
    tab: 'options',
    active: 'px-4 py-2 rounded bg-blue-600 text-white',
    code: '',
    fetchCode() {
      const tree = $('#tree').jstree(true);
      const selected = tree.get_checked(false)
        .filter(id => !tree.get_node(id).children.length);
      if (!selected.length) {
        this.code = '// No files selected';
        document.getElementById('code-content').innerText = this.code;
        this.tab = 'code';
        return;
      }
      fetch(`/api/code?paths=${encodeURIComponent(JSON.stringify(selected))}`)
        .then(res => res.json())
        .then(data => {
          this.code = data.code;
          document.getElementById('code-content').innerText = this.code;
          this.tab = 'code';
        });
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
    },
    clearAll() {
      this.selected_extensions = [];
    },
    async saveExtensions() {
      try {
        await fetch('/api/options/extensions', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({extensions: this.selected_extensions})
        });
        alert('Extensions saved');
      } catch (e) {
        console.error('Failed to save extensions', e);
      }
    },
    async addFavorite() {
      if (!this.newFav) return;
      this.favorites.push(this.newFav);
      await this._saveFavs();
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
      this.hidden.push(this.newHidden);
      await this._saveHidden();
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
      } catch (e) {
        console.error('Failed to save hidden items', e);
      }
    }
  }));
});
