document.addEventListener('DOMContentLoaded', function() {
  // Read baseDir from hidden input
  let baseDir = '';
  const baseInput = document.getElementById('baseDirInput');
  if (baseInput) baseDir = baseInput.value;
  // Parameters menu toggle
  const paramBtn = document.getElementById('paramBtn');
  const paramMenu = document.getElementById('paramMenu');
  if (paramBtn && paramMenu) {
    paramBtn.addEventListener('click', () => paramMenu.classList.toggle('hidden'));
  }
  // Theme toggle button in params menu
  const themeBtn = document.getElementById('themeBtn');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const isDark = document.documentElement.classList.toggle('dark');
      localStorage.setItem('theme', isDark ? 'dark' : 'light');
      themeBtn.blur();
    });
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
      $('#tree').jstree(true).refresh();
    });
  }
  // Navigation history stack
  let history = [], histIndex = -1;
  function updateNavButtons() {
    $('#btnBack').prop('disabled', histIndex <= 0);
    $('#btnForward').prop('disabled', histIndex >= history.length - 1);
  }
  // Build tree
  $('#tree').jstree({
    core: {
      data: function(node, callback) {
        let path = node.id === '#' ? baseDir : node.id;
        // Include showHidden flag for filtering
        $.getJSON('/api/tree', { path: path, showHidden: window.showHidden }, function(data) {
          callback(data);
        });
      },
      check_callback: false
    },
    plugins: ['types', 'checkbox', 'search'],
    types: {
      'default': { icon: 'jstree-icon jstree-file' },
      'folder': { icon: 'jstree-icon jstree-folder' }
    }
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
  $('#tree').on('loaded.jstree open_node.jstree', function(e, data) {
    data.instance.get_json('#', { flat: false }).forEach(function(node) {
      if (node.children && node.children.length) {
        data.instance.set_type(node.id, 'folder');
      }
    });
  });

  // Handle node selection for history and preview
  $('#tree').on('select_node.jstree', function(e, data) {
    const node = data.node;
    const inst = data.instance;
    // Directory navigation
    if (node.children.length) {
      // push history
      history = history.slice(0, histIndex + 1);
      history.push(node.id);
      histIndex++;
      updateNavButtons();
      // open directory
      inst.open_node(node);
    } else {
      // File preview
      fetch(`/api/preview?path=${encodeURIComponent(node.id)}`)
        .then(r => r.json())
        .then(d => {
          document.getElementById('file-preview').innerText = d.content || '// No preview';
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
