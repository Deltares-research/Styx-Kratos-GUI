test('ImportDialog.open creates the modal', function () {
  var origUI = App.UI;
  var origApi = App.Api;

  App.UI = {
    // Mirrors js/ui.js's el(): "tag.class1.class2" both names the element and applies
    // its classes -- import-dialog.js finds its own nodes back with .dlg-title etc.
    el: function (spec, attrs, children) {
      var parts = spec.split('.');
      var node = document.createElement(parts[0] || 'div');
      parts.slice(1).forEach(function (cls) { node.classList.add(cls); });
      if (attrs && attrs.id) node.id = attrs.id;
      if (attrs && attrs.text) node.textContent = attrs.text;
      (children || []).forEach(function (c) { node.appendChild(c); });
      return node;
    }
  };
  App.Api = { base: '' };

  var layer = document.createElement('div');
  layer.id = 'modal-layer';
  document.body.appendChild(layer);

  try {
    App.ImportDialog.open();
    var dialog = document.getElementById('import-dialog');
    T.ok(dialog, 'dialog is inserted into the DOM');

    var title = dialog.querySelector('.dlg-title');
    T.ok(title && title.textContent === 'Import 3D model', 'dialog has correct title');

    var closeButton = dialog.querySelector('.dlg-x');
    closeButton.click();

    T.ok(!document.getElementById('import-dialog'), 'dialog is removed on close click');
  } finally {
    document.body.removeChild(layer);
    App.UI = origUI;
    App.Api = origApi;
  }
});
