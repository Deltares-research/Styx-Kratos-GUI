/* Import Dialog for 3D Models */

var App = window.App || {};

App.ImportDialog = (function () {
  function open() {
    var layer = document.getElementById('modal-layer');
    if (!layer || document.getElementById('import-dialog')) return;
    
    var el = App.UI.el;
    var scrim = el('div.scrim');
    var dialog = el('div.dialog.import-dialog', { id: 'import-dialog' });
    
    dialog.style.width = '500px';
    dialog.style.height = '400px';
    dialog.style.left = Math.max(20, (window.innerWidth - 500) / 2) + 'px';
    dialog.style.top = Math.max(20, (window.innerHeight - 400) / 2) + 'px';
    
    var closeButton = el('button.dlg-x', { text: '✕', type: 'button' });
    var head = el('div.dlg-head', null, [el('span.dlg-title', { text: 'Import 3D model' }), closeButton]);
    dialog.appendChild(head);
    App.Dialogs.draggable(head, dialog);
    
    var body = el('div.dlg-body');
    body.style.display = 'flex';
    body.style.flexDirection = 'column';
    body.style.padding = '20px';
    
    var dropZone = el('div.drop-zone', { text: 'Drag and drop a .step, .iges, .brep, .stl, or .obj file here, or click to browse.' });
    dropZone.style.flex = '1';
    dropZone.style.border = '2px dashed #999';
    dropZone.style.borderRadius = '8px';
    dropZone.style.display = 'flex';
    dropZone.style.alignItems = 'center';
    dropZone.style.justifyContent = 'center';
    dropZone.style.textAlign = 'center';
    dropZone.style.cursor = 'pointer';
    dropZone.style.padding = '20px';
    dropZone.style.marginBottom = '20px';
    dropZone.style.color = '#666';
    
    var fileInput = el('input', { type: 'file', accept: '.step,.stp,.iges,.igs,.brep,.stl,.obj' });
    fileInput.style.display = 'none';
    
    body.appendChild(dropZone);
    body.appendChild(fileInput);
    
    var message = el('div', { text: '' });
    message.style.color = 'red';
    body.appendChild(message);
    
    dialog.appendChild(body);
    layer.appendChild(scrim);
    layer.appendChild(dialog);
    
    function close() {
      if (scrim.parentNode) scrim.remove();
      if (dialog.parentNode) dialog.remove();
      document.removeEventListener('keydown', escape);
    }
    
    function escape(event) { if (event.key === 'Escape') close(); }
    
    function handleFile(file) {
      if (!file) return;
      message.textContent = 'Uploading and processing...';
      message.style.color = '#333';
      
      var formData = new FormData();
      formData.append('file', file);
      
      fetch(App.Api.base + '/api/geometry/import', {
        method: 'POST',
        body: formData
      })
      .then(function(res) {
        if (!res.ok) {
          return res.json().then(function(err) { throw new Error(err.detail || 'Import failed'); });
        }
        return res.json();
      })
      .then(function(data) {
        // success
        App.Command.ok('Successfully imported model: ' + file.name);
        close();
        return App.Model.load().then(function () {
          return App.Viewport.refresh();
        }).then(function () {
          if (App.Explorer && App.state) {
            App.Explorer.mountTree(App.state.mode);
            App.selectObject(data.parts[0].key, 'tree');
          }
        });
      })
      .catch(function(err) {
        message.textContent = err.message;
        message.style.color = 'red';
      });
    }
    
    dropZone.addEventListener('click', function() { fileInput.click(); });
    fileInput.addEventListener('change', function(e) { handleFile(e.target.files[0]); });
    
    dropZone.addEventListener('dragover', function(e) {
      e.preventDefault();
      dropZone.style.backgroundColor = '#eee';
    });
    dropZone.addEventListener('dragleave', function(e) {
      e.preventDefault();
      dropZone.style.backgroundColor = '';
    });
    dropZone.addEventListener('drop', function(e) {
      e.preventDefault();
      dropZone.style.backgroundColor = '';
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleFile(e.dataTransfer.files[0]);
      }
    });
    
    closeButton.addEventListener('click', close);
    scrim.addEventListener('click', close);
    document.addEventListener('keydown', escape);
  }
  
  return { open: open };
})();
