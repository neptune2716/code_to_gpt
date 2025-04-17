document.addEventListener('DOMContentLoaded', function() {
  // Read baseDir from hidden input
  let baseDir = '';
  const baseInput = document.getElementById('baseDirInput');
  if (baseInput) baseDir = baseInput.value;

  // Global flag for showing hidden items
  window.showHidden = localStorage.getItem('showHidden') === 'true';

  // Parameters menu toggle
  const paramBtn = document.getElementById('paramBtn');
  const paramMenu = document.getElementById('paramMenu');
  if (paramBtn && paramMenu) {
    paramBtn.addEventListener('click', () => paramMenu.classList.toggle('hidden'));
  }

  // Close params menu when clicking outside
  document.addEventListener('click', (e) => {
    if (paramMenu && paramBtn && !paramMenu.contains(e.target) && !paramBtn.contains(e.target)) {
      paramMenu.classList.add('hidden');
    }
  });

  // Show Hidden toggle in menu
  const toggleHidden2 = document.getElementById('toggleHidden2');
  if (toggleHidden2) {
    toggleHidden2.checked = window.showHidden;
    toggleHidden2.addEventListener('change', function() {
      window.showHidden = this.checked;
      localStorage.setItem('showHidden', window.showHidden ? 'true' : 'false'); // Persist state
      const tree = $('#tree').jstree(true);
      if (tree) {
        tree.refresh();
      }
    });
  }

  // Navigation history stack
  let history = [], histIndex = -1;
  function updateNavButtons() {
    $('#btnBack').prop('disabled', histIndex <= 0);
    $('#btnForward').prop('disabled', histIndex >= history.length - 1);
  }

  // Debounce function
  function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  };

  // Debounced code fetch function
  const debouncedFetchCode = debounce(() => {
    const codePanelElement = document.querySelector('[x-data="codePanel()"]');
    if (codePanelElement && codePanelElement.__x) {
      if (codePanelElement.__x.$data.tab === 'code') {
         codePanelElement.__x.fetchCode();
      }
    }
  }, 500);

  // Build tree
  $('#tree').jstree({
    core: {
      data: function(node, callback) {
        let path = node.id === '#' ? baseDir : node.id;
        $.getJSON('/api/tree', { path: path, showHidden: window.showHidden }, function(data) {
          callback(data);
        }).fail(function() {
          callback([]);
          console.error('Failed to load tree data for path:', path);
        });
      },
      check_callback: true,
      themes: {
        name: localStorage.getItem('theme') === 'dark' ? 'default-dark' : 'default',
        responsive: true
      }
    },
    plugins: ['types', 'checkbox', 'search', 'contextmenu', 'wholerow'],
    types: {
      'default': { icon: 'jstree-icon jstree-file' },
      'folder': { icon: 'jstree-icon jstree-folder' }
    },
    checkbox: {
      keep_selected_style: false,
      three_state: false,
      cascade: ''
    },
    search: {
        show_only_matches: true,
        show_only_matches_children: true
    },
    contextmenu: {
      items: function(node) {
        const tree = $('#tree').jstree(true);
        const isDir = tree.is_parent(node);
        const path = node.id;
        const baseDir = document.getElementById('baseDirInput').value; // Get base directory

        // Helper function to get Alpine component data
        const getOptionsPanelData = () => {
          const el = document.querySelector('[x-data="optionsPanel()"]');
          return el ? el.__x.$data : null;
        };

        let menuItems = {
          preview: {
            label: "Preview",
            action: function(data) {
              fetch(`/api/preview?path=${encodeURIComponent(path)}`)
                .then(r => r.json())
                .then(d => {
                  document.getElementById('file-preview').innerText = d.content || '// No preview available or file is empty';
                }).catch(err => {
                  document.getElementById('file-preview').innerText = '// Error loading preview';
                  console.error('Preview error:', err);
                });
            },
            _disabled: isDir // Disable for folders
          },
          copyPath: {
            label: "Copy Path",
            action: function(data) {
              navigator.clipboard.writeText(path).then(() => {
                alert('Path copied to clipboard!');
              }).catch(err => {
                console.error('Failed to copy path: ', err);
                alert('Failed to copy path.');
              });
            }
          },
          separator1: {
            "separator_before": true,
            "separator_after": false,
            "label": "----"
          },
          toggleFavorite: {
            label: "Add to Favorites", // Default label
            action: function(data) {
              const optionsData = getOptionsPanelData();
              if (optionsData) {
                if (optionsData.favorites.includes(path)) {
                  optionsData.removeFavorite(path);
                } else {
                  // Need to simulate adding via input temporarily
                  optionsData.newFav = path;
                  optionsData.addFavorite();
                }
              }
            },
            // Dynamically update label based on favorite status
            _init: function(data) {
              const optionsData = getOptionsPanelData();
              if (optionsData && optionsData.favorites.includes(path)) {
                 setTimeout(() => {
                    const menu = $(data.reference).closest('.jstree-contextmenu');
                    menu.find('.vakata-contextmenu-sep').parent().find('a:contains("Add to Favorites"), a:contains("Remove from Favorites")').find('.vakata-contextmenu-label').text('Remove from Favorites');
                 }, 0);
              }
            }
          },
          toggleHidden: {
            label: "Hide", // Default label
            action: function(data) {
              const optionsData = getOptionsPanelData();
              if (optionsData) {
                if (optionsData.hidden.includes(path)) {
                  optionsData.removeHidden(path);
                } else {
                  // Need to simulate adding via input temporarily
                  optionsData.newHidden = path;
                  optionsData.addHidden();
                }
              }
            },
            // Dynamically update label based on hidden status
            _init: function(data) {
              const optionsData = getOptionsPanelData();
              if (optionsData && optionsData.hidden.includes(path)) {
                 setTimeout(() => {
                    const menu = $(data.reference).closest('.jstree-contextmenu');
                    menu.find('.vakata-contextmenu-sep').parent().find('a:contains("Hide"), a:contains("Show")').find('.vakata-contextmenu-label').text('Show');
                 }, 0);
              }
            }
          },
          renameItem: {
            label: "Rename",
            action: function(data) {
              const inst = $.jstree.reference(data.reference);
              const node = inst.get_node(data.reference);
              const oldName = node.text;
              const newName = prompt("Enter new name:", oldName);

              if (newName && newName !== oldName) {
                fetch('/api/fs/rename', {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({ oldPath: path, newName: newName })
                })
                .then(response => response.json())
                .then(result => {
                  if (result.success) {
                    const parentNode = inst.get_parent(node);
                    inst.refresh_node(parentNode);
                    alert('Renamed successfully!');
                    const optionsData = getOptionsPanelData();
                    if (optionsData) {
                        const newFullPath = result.newPath;
                        if (optionsData.favorites.includes(path)) {
                            optionsData.removeFavorite(path);
                            optionsData.newFav = newFullPath;
                            optionsData.addFavorite();
                        }
                        if (optionsData.hidden.includes(path)) {
                            optionsData.removeHidden(path);
                            optionsData.newHidden = newFullPath;
                            optionsData.addHidden();
                        }
                    }
                  } else {
                    alert(`Rename failed: ${result.message}`);
                  }
                })
                .catch(error => {
                  console.error('Rename error:', error);
                  alert('An error occurred during rename.');
                });
              }
            },
            _disabled: path === baseDir // Disable renaming the root node
          },
          deleteItem: {
            label: "Delete",
            action: function(data) {
              const inst = $.jstree.reference(data.reference);
              const node = inst.get_node(data.reference);
              const nodeName = node.text;

              if (confirm(`Are you sure you want to delete '${nodeName}'?`)) {
                fetch('/api/fs/delete', {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({ path: path })
                })
                .then(response => response.json())
                .then(result => {
                  if (result.success) {
                    inst.delete_node(node);
                    alert('Deleted successfully!');
                    const optionsData = getOptionsPanelData();
                    if (optionsData) {
                        if (optionsData.favorites.includes(path)) {
                            optionsData.removeFavorite(path);
                        }
                        if (optionsData.hidden.includes(path)) {
                            optionsData.removeHidden(path);
                        }
                    }
                  } else {
                    alert(`Delete failed: ${result.message}`);
                  }
                })
                .catch(error => {
                  console.error('Delete error:', error);
                  alert('An error occurred during delete.');
                });
              }
            },
            _disabled: path === baseDir // Disable deleting the root node
          },
          separator2: {
            "separator_before": true,
            "separator_after": false,
            "label": "----"
          },
          toggleSelect: {
            label: tree.is_checked(node) ? "Deselect" : "Select",
            action: function(data) {
              if (tree.is_checked(node)) {
                tree.uncheck_node(node);
              } else {
                tree.check_node(node);
              }
            }
          }
        };

        return menuItems;
      }
    }
  });

  // Trigger debounced code fetch on checkbox change
  $('#tree').on('check_node.jstree uncheck_node.jstree', function(e, data) {
    debouncedFetchCode();
  });

  // On ready, just enable navigation buttons without expanding tree
  $('#tree').on('ready.jstree', function() {
    updateNavButtons();
  });

  // Setup search debounce
  let searchTimeout = null;
  $('#treeSearch').on('input', function() {
    const term = this.value;
    if (searchTimeout) clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      $('#tree').jstree(true).search(term);
    }, 300);
  });

  // Assign folder type for directories
  $('#tree').on('loaded.jstree open_node.jstree refresh.jstree', function(e, data) {
    const inst = data.instance;
    const allNodes = inst.get_json('#', { flat: true });
    allNodes.forEach(function(nodeData) {
      const node = inst.get_node(nodeData.id);
      if (node && inst.is_parent(node)) {
        inst.set_type(node, 'folder');
      }
    });
  });

  // Handle node selection for history and preview
  $('#tree').on('select_node.jstree', function(e, data) {
    const node = data.node;
    const inst = data.instance;

    if (e.originalEvent && $(e.originalEvent.target).hasClass('jstree-checkbox')) {
        return;
    }

    if (inst.is_parent(node)) {
      inst.toggle_node(node);
    } else {
      fetch(`/api/preview?path=${encodeURIComponent(node.id)}`)
        .then(r => r.json())
        .then(d => {
          document.getElementById('file-preview').innerText = d.content || '// No preview available or file is empty';
        }).catch(err => {
            document.getElementById('file-preview').innerText = '// Error loading preview';
            console.error('Preview error:', err);
        });
    }
  });

  // Back/Forward button handlers
  $('#btnBack').on('click', function() {
    if (histIndex > 0) {
      histIndex--;
      const id = history[histIndex];
      $('#tree').jstree(true).deselect_all();
      $('#tree').jstree(true).select_node(id);
      updateNavButtons();
    }
  });
  $('#btnForward').on('click', function() {
    if (histIndex < history.length - 1) {
      histIndex++;
      const id = history[histIndex];
      $('#tree').jstree(true).deselect_all();
      $('#tree').jstree(true).select_node(id);
      updateNavButtons();
    }
  });
});
