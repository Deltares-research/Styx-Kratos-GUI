test('MdpaImportDialog.open creates the modal', function () {
  var origUI = App.UI;
  var origApi = App.Api;

  App.UI = {
    // Mirrors js/ui.js's el(): "tag.class1.class2" both names the element and applies
    // its classes -- mdpa-import-dialog.js finds its own nodes back with .dlg-title etc.
    el: function (spec, attrs, children) {
      var parts = spec.split('.');
      var node = document.createElement(parts[0] || 'div');
      parts.slice(1).forEach(function (cls) { node.classList.add(cls); });
      if (attrs && attrs.id) node.id = attrs.id;
      if (attrs && attrs.text) node.textContent = attrs.text;
      if (attrs && attrs.type) node.type = attrs.type;
      if (attrs && attrs.accept) node.setAttribute('accept', attrs.accept);
      (children || []).forEach(function (c) { node.appendChild(c); });
      return node;
    }
  };
  App.Api = { base: '' };

  var layer = document.createElement('div');
  layer.id = 'modal-layer';
  document.body.appendChild(layer);

  try {
    App.MdpaImportDialog.open();
    var dialog = document.getElementById('mdpa-import-dialog');
    T.ok(dialog, 'dialog is inserted into the DOM');

    var title = dialog.querySelector('.dlg-title');
    T.ok(title && title.textContent === 'Import mesh (.mdpa)', 'dialog has correct title');

    var fileInput = dialog.querySelector('input[type="file"]');
    T.ok(fileInput && fileInput.getAttribute('accept') === '.mdpa',
      'file input only accepts .mdpa');

    // A second open() call is a no-op while one is already showing.
    App.MdpaImportDialog.open();
    T.eq(document.querySelectorAll('#mdpa-import-dialog').length, 1,
      'opening twice does not duplicate the dialog');

    var closeButton = dialog.querySelector('.dlg-x');
    closeButton.click();

    T.ok(!document.getElementById('mdpa-import-dialog'), 'dialog is removed on close click');
  } finally {
    document.body.removeChild(layer);
    App.UI = origUI;
    App.Api = origApi;
  }
});

test('the File menu offers Import mesh (.mdpa)…', function () {
  var fileMenu = (App.MENUS || []).filter(function (m) { return m.label === 'File'; })[0];
  T.ok(fileMenu, 'a File menu exists');

  var item = (fileMenu.items || []).filter(function (i) {
    return i && i.action === 'importMdpa';
  })[0];
  T.ok(item, 'File menu has an importMdpa entry');
  T.eq(item.label, 'Import mesh (.mdpa)…');

  // Grouped with the other file-format buttons, right after Export model, not tacked
  // on after Exit.
  var exportAt = fileMenu.items.findIndex(function (i) { return i && i.action === 'exportModel'; });
  var importAt = fileMenu.items.indexOf(item);
  T.eq(importAt, exportAt + 1, 'Import mesh sits directly after Export model');

  var exitAt = fileMenu.items.findIndex(function (i) { return i && i.label === 'Exit'; });
  T.ok(importAt < exitAt, 'Import mesh comes before the Exit separator');
});

/* ── The per-part checklist ──────────────────────────────────────────── */

(function () {
  var MODEL = {
    dimension: 2, nodes: 3, parts: [], bbox: [0, 0, 0, 1, 1, 0],
    sections: [
      { key: 'imported:Soil_1', color: '#c9a35c', part: 'Soil_1', kind: 'continuum',
        positions: [0, 0, 0, 1, 0, 0, 0, 1, 0], indices: [0, 1, 2], edges: [],
        bbox: [0, 0, 0, 1, 1, 0] },
      { key: 'imported_beam', color: '#b5573a', part: null, kind: 'beam',
        positions: [], indices: [], edges: [0, 0, 0, 1, 0, 0], bbox: [0, 0, 0, 1, 0, 0] }
    ]
  };

  function withDom(body) {
    var origUI = App.UI, origApi = App.Api, origViewport = App.Viewport, origModel = App.Model;
    App.UI = {
      el: function (spec, attrs, children) {
        var parts = spec.split('.');
        var node = document.createElement(parts[0] || 'div');
        parts.slice(1).forEach(function (cls) { node.classList.add(cls); });
        if (attrs && attrs.id) node.id = attrs.id;
        if (attrs && attrs.text) node.textContent = attrs.text;
        if (attrs && attrs.type) node.type = attrs.type;
        (children || []).forEach(function (c) { node.appendChild(c); });
        return node;
      }
    };
    App.Api = { base: '' };
    var layer = document.createElement('div');
    layer.id = 'modal-layer';
    document.body.appendChild(layer);
    try { body(layer); }
    finally {
      App.MdpaImportDialog.closeChecklist();
      document.body.removeChild(layer);
      App.UI = origUI; App.Api = origApi; App.Viewport = origViewport; App.Model = origModel;
    }
  }

  test('the checklist lists one row per section, named by part or by kind', function () {
    withDom(function () {
      App.MdpaImportDialog.openChecklist(MODEL, 'sheet_pile.mdpa');
      var panel = document.getElementById('mdpa-checklist');
      T.ok(panel, 'the checklist panel is inserted');
      T.eq(panel.querySelector('.dlg-title').textContent, 'sheet_pile.mdpa');

      var labels = Array.prototype.map.call(
        panel.querySelectorAll('input[type="checkbox"]'),
        function (cb) { return cb.parentNode.textContent.replace('⌖', '').trim(); });
      T.eq(labels, ['Soil_1', 'beam (ungrouped)']);
    });
  });

  test('opening a second import replaces the first checklist, not stacks it', function () {
    withDom(function () {
      App.MdpaImportDialog.openChecklist(MODEL, 'first.mdpa');
      App.MdpaImportDialog.openChecklist(MODEL, 'second.mdpa');
      T.eq(document.querySelectorAll('#mdpa-checklist').length, 1);
      T.eq(document.getElementById('mdpa-checklist').querySelector('.dlg-title').textContent,
           'second.mdpa');
    });
  });

  test("a row's checkbox toggles just that section's visibility", function () {
    withDom(function () {
      var calls = [];
      App.Viewport = { setVisible: function (key, on) { calls.push([key, on]); } };
      App.MdpaImportDialog.openChecklist(MODEL, 'x.mdpa');
      var checkbox = document.querySelectorAll('#mdpa-checklist input[type="checkbox"]')[0];
      checkbox.checked = false;
      checkbox.dispatchEvent(new Event('change'));
      T.eq(calls, [['imported:Soil_1', false]]);
    });
  });

  test("a row's frame button asks the viewport to frame that section, not toggle it", function () {
    withDom(function () {
      var framed = [], toggled = [];
      App.Viewport = {
        frameImportedSection: function (key) { framed.push(key); },
        setVisible: function (key, on) { toggled.push([key, on]); }
      };
      App.MdpaImportDialog.openChecklist(MODEL, 'x.mdpa');
      var button = document.querySelector('#mdpa-checklist button:not(.dlg-x):not(.btn-primary)');
      button.dispatchEvent(new Event('click', { cancelable: true }));
      T.eq(framed, ['imported:Soil_1']);
      T.eq(toggled, [], 'framing must not also flip the row checked/unchecked');
    });
  });

  test('closing the checklist with the ✕ clears the whole imported preview', function () {
    withDom(function () {
      var cleared = 0;
      App.Viewport = { clearImportedMesh: function () { cleared++; } };
      App.MdpaImportDialog.openChecklist(MODEL, 'x.mdpa');
      document.getElementById('mdpa-checklist').querySelector('.dlg-x').click();
      T.eq(cleared, 1);
      T.ok(!document.getElementById('mdpa-checklist'), 'the panel itself is gone too');
    });
  });

  test('a deck with nothing drawable says so instead of showing an empty list, with no Accept button', function () {
    withDom(function () {
      App.MdpaImportDialog.openChecklist(
        { dimension: 3, nodes: 0, parts: [], bbox: [0, 0, 0, 0, 0, 0], sections: [] }, 'empty.mdpa');
      var panel = document.getElementById('mdpa-checklist');
      T.eq(panel.querySelectorAll('input[type="checkbox"]').length, 0);
      T.ok(/nothing/i.test(panel.textContent), 'says nothing could be drawn');
      T.ok(!panel.querySelector('.btn-primary'), 'nothing to accept, so no Accept button');
    });
  });

  /* ── Accept ────────────────────────────────────────────────────────── */

  test('the checklist has an Accept button when there is something to accept', function () {
    withDom(function () {
      App.MdpaImportDialog.openChecklist(MODEL, 'x.mdpa');
      var accept = document.querySelector('#mdpa-checklist .btn-primary');
      T.ok(accept, 'an Accept button is present');
      T.eq(accept.textContent, 'Accept');
    });
  });

  test('Accept adds only the checked parts to the Model explorer', function () {
    withDom(function () {
      var savedParts = null;
      App.Model = { setImportedParts: function (parts) { savedParts = parts; } };
      App.Viewport = { removeImportedSection: function () {} };
      App.MdpaImportDialog.openChecklist(MODEL, 'x.mdpa');
      // Uncheck the second row (the ungrouped beam) before accepting.
      document.querySelectorAll('#mdpa-checklist input[type="checkbox"]')[1].checked = false;

      document.querySelector('#mdpa-checklist .btn-primary').click();

      T.eq(savedParts, [{ key: 'imported:Soil_1', label: 'Soil_1', color: '#c9a35c' }]);
    });
  });

  test('Accept drops the unchecked parts from the viewport entirely, not just hides them', function () {
    withDom(function () {
      var removed = [];
      App.Model = { setImportedParts: function () {} };
      App.Viewport = { removeImportedSection: function (key) { removed.push(key); } };
      App.MdpaImportDialog.openChecklist(MODEL, 'x.mdpa');
      document.querySelectorAll('#mdpa-checklist input[type="checkbox"]')[1].checked = false;

      document.querySelector('#mdpa-checklist .btn-primary').click();

      T.eq(removed, ['imported_beam']);
    });
  });

  /* ── Interfaces ───────────────────────────────────────────────────── */

  /* A wall and the zero-thickness contacts that hold the soil to it: the arrangement a
     .mdpa with a sheet pile actually contains. The contact draws as line work (there is
     no thickness for a face to span -- server/app/mdpa_import.py `_triangles_and_edges`),
     and nothing here treats it differently from any other part: it earns a checklist
     row, an eye in the Model explorer and a colour of its own by being a section. */
  var WALLED = {
    dimension: 2, nodes: 6, parts: [], bbox: [0, -5, 0, 4, 0, 0],
    sections: [
      { key: 'imported:Sheet_pile_1', color: '#c9a35c', part: 'Sheet_pile_1',
        kind: 'beam', positions: [], indices: [], edges: [4, 0, 0, 4, -5, 0],
        node_ids: [], elements: [], bbox: [4, -5, 0, 4, 0, 0] },
      { key: 'imported:Wall_contact', color: '#d4a017', part: 'Wall_contact',
        kind: 'interface', positions: [], indices: [], edges: [4, 0, 0, 4, -5, 0],
        node_ids: [], elements: [[1, 4, -2.5, 0]], bbox: [4, -5, 0, 4, 0, 0] }
    ]
  };

  test('an interface part gets its own checklist row, next to the wall it holds',
       function () {
    withDom(function () {
      App.MdpaImportDialog.openChecklist(WALLED, 'walled.mdpa');
      var labels = Array.prototype.map.call(
        document.querySelectorAll('#mdpa-checklist input[type="checkbox"]'),
        function (cb) { return cb.parentNode.textContent.replace('⌖', '').trim(); });
      T.eq(labels, ['Sheet_pile_1', 'Wall_contact']);
    });
  });

  test('an accepted interface reaches the Model explorer as a row of its own',
       function () {
    withDom(function () {
      var savedParts = null;
      App.Model = { setImportedParts: function (parts) { savedParts = parts; } };
      App.Viewport = { removeImportedSection: function () {} };
      App.MdpaImportDialog.openChecklist(WALLED, 'walled.mdpa');

      document.querySelector('#mdpa-checklist .btn-primary').click();

      T.eq(savedParts, [
        { key: 'imported:Sheet_pile_1', label: 'Sheet_pile_1', color: '#c9a35c' },
        { key: 'imported:Wall_contact', label: 'Wall_contact', color: '#d4a017' }
      ]);
    });
  });

  test('an interface can be turned off on its own, leaving the wall drawn', function () {
    withDom(function () {
      var calls = [];
      App.Viewport = { setVisible: function (key, on) { calls.push([key, on]); } };
      App.MdpaImportDialog.openChecklist(WALLED, 'walled.mdpa');
      var contact = document.querySelectorAll('#mdpa-checklist input[type="checkbox"]')[1];
      contact.checked = false;
      contact.dispatchEvent(new Event('change'));
      T.eq(calls, [['imported:Wall_contact', false]]);
    });
  });

  test('Accept closes the checklist but does not clear the whole preview', function () {
    withDom(function () {
      var cleared = 0;
      App.Model = { setImportedParts: function () {} };
      App.Viewport = { removeImportedSection: function () {}, clearImportedMesh: function () { cleared++; } };
      App.MdpaImportDialog.openChecklist(MODEL, 'x.mdpa');

      document.querySelector('#mdpa-checklist .btn-primary').click();

      T.eq(cleared, 0, 'Accept keeps the accepted parts drawn, unlike ✕');
      T.ok(!document.getElementById('mdpa-checklist'), 'the checklist panel still closes');
    });
  });
})();
