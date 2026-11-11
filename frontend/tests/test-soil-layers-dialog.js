/* Tests for frontend/js/soil-layers-dialog.js — the Modify soil layers window.

   The stack edits are the browser's twin of core/session.py `update_layer`,
   `split_layer` and `remove_layer`, so they are tested as data first. The window is
   tested through its buttons: it edits a copy, OK sends the copy, and Cancel or Esc
   leave the project as it was. */

(function () {
  var D = App.SoilLayersDialog;

  function stack() {
    return [{ id: 'L1', name: 'Soil_1', mat: 'm2', top: 0, bottom: -8 },
            { id: 'L2', name: 'Soil_2', mat: 'm4', top: -8, bottom: -25 }];
  }

  function levels(layers) {
    return layers.map(function (layer) { return [layer.id, layer.top, layer.bottom]; });
  }

  /* ── The stack ─────────────────────────────────────────────────────── */

  test('a moved bottom moves the top of the layer below', function () {
    var layers = stack();
    T.eq(D.setBottom(layers, 0, -10), null);
    T.eq(levels(layers), [['L1', 0, -10], ['L2', -10, -25]]);
  });

  test('a moved top moves the bottom of the layer above', function () {
    var layers = stack();
    T.eq(D.setTop(layers, 1, -5), null);
    T.eq(levels(layers), [['L1', 0, -5], ['L2', -5, -25]]);
  });

  test('a level that would cross a neighbour is refused, and nothing moves', function () {
    var layers = stack();
    T.ok(/below the bottom of the layer below \(-25 m\)/.test(D.setBottom(layers, 0, -30)));
    T.ok(/above the top of the layer above \(0 m\)/.test(D.setTop(layers, 1, 2)));
    T.ok(/at or above the bottom/.test(D.setTop(layers, 0, -9)));
    T.ok(/at or below the top/.test(D.setBottom(layers, 1, -7)));
    T.eq(levels(layers), levels(stack()));
  });

  test('a thickness keeps the top and moves the bottom', function () {
    var layers = stack();
    T.eq(D.setThickness(layers, 0, 3), null);
    T.eq(levels(layers), [['L1', 0, -3], ['L2', -3, -25]]);
    T.ok(/0 or more/.test(D.setThickness(layers, 0, -1)));
  });

  test('Add puts a 5 m layer under the stack, and the first one at the ground', function () {
    var layers = stack();
    T.eq(D.add(layers, 'm2', 0), 2);
    T.eq(layers[2], { id: 'L3', name: 'Soil_3', mat: 'm2', top: -25, bottom: -30 });
    var empty = [];
    D.add(empty, 'm1', 1.5);
    T.eq(levels(empty), [['L1', 1.5, -3.5]]);
  });

  test('Insert halves a layer; the lower half is a new layer of the same material',
       function () {
    var layers = stack();
    T.eq(D.split(layers, 0), 1);
    T.eq(levels(layers), [['L1', 0, -4], ['L3', -4, -8], ['L2', -8, -25]]);
    T.eq(layers[1].mat, 'm2');
  });

  test('Delete closes the gap from above, or from below for the top layer', function () {
    var layers = stack();
    D.add(layers, 'm2', 0);
    D.remove(layers, 1);
    T.eq(levels(layers), [['L1', 0, -25], ['L3', -25, -30]]);
    D.remove(layers, 0);
    T.eq(levels(layers), [['L3', 0, -30]]);
  });

  test('a freed id is used again, never one still taken', function () {
    var layers = stack();
    D.remove(layers, 0);
    D.add(layers, 'm2', 0);
    T.eq(layers.map(function (layer) { return layer.id; }), ['L2', 'L1']);
  });

  /* ── The Model and Selection explorers ─────────────────────────────── */

  test('the Model explorer’s Delete closes the gap, and keeps the last layer',
       function () {
    var saved = App.LAYERS;
    try {
      App.LAYERS = stack();
      T.ok(/no longer exists/.test(D.removeById('L9')));
      T.eq(D.removeById('L1'), null);
      T.eq(levels(App.LAYERS), [['L2', 0, -25]]);
      T.ok(/at least one/.test(D.removeById('L2')));
    } finally { App.LAYERS = saved; }
  });

  test('the Selection explorer edits one level and the neighbour follows', function () {
    var saved = App.LAYERS;
    try {
      App.LAYERS = stack();
      var bottom = D.levelEditor(App.LAYERS[0], 'bottom');
      T.eq(bottom.get(), -8);
      T.eq(bottom.set(-6), null);
      T.eq(levels(App.LAYERS), [['L1', 0, -6], ['L2', -6, -25]]);
      T.ok(/below the bottom of the layer below/.test(bottom.set(-40)));
    } finally { App.LAYERS = saved; }
  });

  /* ── The column picture ────────────────────────────────────────────── */

  test('the column spans the stack and the water level, in whole ticks', function () {
    var range = D.columnRange(stack(), { y: 2.2 });
    T.eq([range.top, range.bottom, range.step], [5, -25, 5]);
    T.eq(D.columnRange([], { y: 0 }), null);
  });

  test('the column draws a band per layer and the water line', function () {
    var svg = D.drawColumn(stack(), { y: -1.5 }, 1, function () {});
    T.eq(svg.querySelectorAll('.soil-column-band').length, 2);
    T.eq(svg.querySelectorAll('.soil-column-band.sel').length, 1);
    T.eq(svg.querySelectorAll('.soil-column-water').length, 1);
    T.eq(D.drawColumn(stack(), null, 0, function () {})
           .querySelectorAll('.soil-column-water').length, 0);
  });

  /* ── The window ────────────────────────────────────────────────────── */

  /* The window, opened on `layers` with a stub server; `run(ui)` drives it. */
  function withWindow(layers, run, parts) {
    var saved = { layers: App.LAYERS, materials: App.MATERIALS, project: App.PROJECT,
                  api: App.Api, model: App.Model, viewport: App.Viewport,
                  command: App.Command, explorer: App.Explorer };
    var host = document.createElement('div'); host.id = 'modal-layer';
    document.body.appendChild(host);
    var sent = [], said = [];
    App.LAYERS = layers;
    App.MATERIALS = [{ id: 'm2', name: 'Sand', color: '#c4a86a' },
                     { id: 'm4', name: 'Clay', color: '#6f8fa8' }];
    App.PROJECT = { custom_parts: parts || [], water: { y: -1 } };
    App.Api = { patch: function (path, body) {
      sent.push([path, body]);
      return Promise.resolve({ project: { layers: body.layers } });
    } };
    App.Model = { materialsToServer: function (m) { return m; },
                  domain: function () { return { y_top: 0 }; },
                  apply: function (p) { App.LAYERS = p.layers; },
                  rebuildDerived: function () {} };
    App.Viewport = { refresh: function () { return Promise.resolve(); } };
    App.Explorer = { mountTree: function () {} };
    App.Command = { ok: function (t) { said.push(t); }, err: function (t) { said.push(t); } };
    function restore() {
      Array.prototype.slice.call(host.querySelectorAll('.dlg-x')).reverse().forEach(function (x) { x.click(); });
      host.remove();
      App.LAYERS = saved.layers; App.MATERIALS = saved.materials; App.PROJECT = saved.project;
      App.Api = saved.api; App.Model = saved.model; App.Viewport = saved.viewport;
      App.Command = saved.command; App.Explorer = saved.explorer;
    }
    var ui = {
      host: host, sent: sent, said: said,
      click: function (label) {
        Array.from(host.querySelectorAll('.lay-pane > .lay-toolbar button, .dlg-foot .btn'))
          .find(function (b) { return b.textContent === label; }).click();
      },
      rows: function () { return host.querySelectorAll('.lay-table-wrap tbody tr').length; },
      type: function (row, column, value) {
        var input = host.querySelectorAll('.lay-table-wrap tbody tr')[row]
          .querySelectorAll('td')[column].querySelector('input');
        input.value = value;
        input.dispatchEvent(new Event('change'));
      },
      hint: function () { return host.querySelector('.lay-pane > .lay-hint').textContent; }
    };
    D.open();
    return Promise.resolve().then(function () { return run(ui); })
      .then(function () { return new Promise(function (done) { setTimeout(done, 0); }); })
      .then(restore, function (error) { restore(); throw error; });
  }

  test('the window edits a copy: the project changes on OK, not before', function () {
    var layers = stack();
    return withWindow(layers, function (ui) {
      T.eq(ui.rows(), 2);
      ui.click('Add');
      ui.type(0, 3, '-10');               // the bottom of L1
      T.eq(ui.rows(), 3);
      T.eq(levels(App.LAYERS), levels(stack()), 'nothing changed before OK');
      T.eq(ui.sent, []);
      ui.click('Cancel');
    });
  });

  test('OK sends the layers with one top and one bottom each, and the library',
       function () {
    var sent;
    return withWindow(stack(), function (ui) {
      sent = ui.sent;
      ui.type(0, 3, '-10');
      ui.click('OK');
      return new Promise(function (done) { setTimeout(done, 0); }).then(function () {
        T.eq(ui.said, ['Soil layers updated — 2 layers.']);
        T.eq(ui.host.querySelectorAll('.dialog').length, 0, 'OK closes the window');
      });
    }).then(function () {
      T.eq(sent.length, 1);
      T.eq(sent[0][0], '/api/project/layers');
      T.eq(Object.keys(sent[0][1]).sort(), ['layers', 'materials']);
      T.eq(levels(sent[0][1].layers), [['L1', 0, -10], ['L2', -10, -25]]);
    });
  });

  test('Cancel and Esc drop the edits, and an added material set with them', function () {
    var layers = stack();
    return withWindow(layers, function (ui) {
      ui.click('Delete'); ui.click('Delete');
      ui.click('Cancel');
      T.eq(ui.sent, []);
      T.eq(App.LAYERS, layers);
      T.eq(levels(App.LAYERS), levels(stack()));

      App.MATERIALS = [];
      var addMaterial = App.addMaterial;
      App.addMaterial = function () {
        var m = { id: 'm9', name: 'New', color: '#000000' };
        App.MATERIALS.push(m);
        return m;
      };
      try {
        D.open();
        ui.click('Add');
        T.eq(App.MATERIALS.length, 1, 'Add needs a material set and makes one');
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        T.eq(App.MATERIALS, [], 'Esc puts the library back');
        T.eq(ui.host.querySelectorAll('.dialog').length, 0);
      } finally { App.addMaterial = addMaterial; }
    });
  });

  test('a refused level says why, and the cell shows the level kept', function () {
    return withWindow(stack(), function (ui) {
      ui.type(0, 3, '-30');
      T.ok(/below the bottom of the layer below/.test(ui.hint()), ui.hint());
      ui.type(0, 3, 'deep');
      T.ok(/is not a number/.test(ui.hint()), ui.hint());
      T.eq(ui.host.querySelector('.lay-table-wrap tbody tr td:nth-child(4) input').value,
           '-8.000');
      ui.click('Cancel');
    });
  });

  test('an empty stack supports Add, Insert and Delete', function () {
    return withWindow([], function (ui) {
      ui.click('Insert');
      T.eq(ui.rows(), 1);
      ui.click('Add'); ui.click('Insert');
      T.eq(ui.rows(), 3);
      ui.click('Delete'); ui.click('Delete'); ui.click('Delete');
      T.eq(ui.rows(), 0);
      T.ok(ui.host.querySelector('.soil-column-empty'), 'the column says there is nothing');
      ui.click('Add');
      T.eq(ui.rows(), 1);
      ui.click('Cancel');
    });
  });

  test('layer rows and the column select the same layer and editable cells save their values', function () {
    return withWindow(stack(), function (ui) {
      var rows = ui.host.querySelectorAll('.lay-table-wrap tbody tr');
      rows[1].dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
      T.ok(rows[1].classList.contains('sel'));
      ui.host.querySelector('.soil-column-band').dispatchEvent(new MouseEvent('mousedown'));
      T.ok(rows[0].classList.contains('sel'));
      ui.type(0, 0, '  Upper sand  ');
      ui.type(0, 2, '1');
      ui.type(1, 4, '15');
      var material = rows[0].querySelector('select');
      material.value = 'm4'; material.dispatchEvent(new Event('change'));
      var input = rows[0].querySelector('input');
      var enter = new KeyboardEvent('keydown', { key: 'Enter', cancelable: true });
      input.dispatchEvent(enter);
      T.ok(enter.defaultPrevented);
      ui.click('OK');
      return new Promise(function (done) { setTimeout(done, 0); }).then(function () {
        T.eq(ui.sent[0][1].layers[0].name, 'Upper sand');
        T.eq(ui.sent[0][1].layers[0].mat, 'm4');
        T.eq(levels(ui.sent[0][1].layers), [['L1', 1, -8], ['L2', -8, -23]]);
      });
    });
  });

  test('a failed layer save reports its reason and re-enables the footer for retry', function () {
    return withWindow(stack(), function (ui) {
      var patch = App.Api.patch;
      App.Api.patch = function () { return Promise.reject(new Error('Layer stack refused')); };
      ui.click('OK');
      return new Promise(function (done) { setTimeout(done, 0); }).then(function () {
        T.eq(ui.said, ['Layer stack refused']);
        T.eq(ui.host.querySelectorAll('.dialog').length, 1);
        Array.prototype.forEach.call(ui.host.querySelectorAll('.dlg-foot .btn'), function (b) {
          T.ok(!b.disabled);
        });
        App.Api.patch = patch;
        ui.click('OK');
        return new Promise(function (done) { setTimeout(done, 0); });
      }).then(function () {
        T.eq(ui.sent.length, 1);
        T.eq(ui.host.querySelectorAll('.dialog').length, 0);
      });
    });
  });

  test('Soil materials refreshes the layer material choices when its window closes', function () {
    return withWindow(stack(), function (ui) {
      var materials = App.Dialogs.materials, closed = 0;
      App.Dialogs.materials = function (onClose) {
        App.MATERIALS.push({ id: 'm9', name: 'Fill', color: '#123456' });
        closed += 1; onClose();
      };
      try {
        ui.click('Soil materials\u2026');
        T.eq(closed, 1);
        T.eq(ui.host.querySelectorAll('.lay-table-wrap tbody tr:first-child select option').length, 3);
      } finally { App.Dialogs.materials = materials; }
      ui.click('Cancel');
    });
  });

  test('custom soil rows save name and material edits and open their coordinates', function () {
    var saved = { commitSelectionEdit: App.commitSelectionEdit, state: App.state,
                  open: App.SoilVolumeDialog.open };
    var committed = [], opened;
    var parts = [{ key: 'fill_1', label: 'Fill 1', mat: 'm2', color: '#c4a86a' },
                 { key: 'fill_2', label: 'Fill 2', mat: 'm4', color: '#6f8fa8' }];
    function restore() {
      App.commitSelectionEdit = saved.commitSelectionEdit; App.state = saved.state;
      App.SoilVolumeDialog.open = saved.open;
    }
    return withWindow(stack(), function (ui) {
      App.state = { selection: 'fill_2' };
      App.commitSelectionEdit = function (key) { committed.push(key); return Promise.resolve(); };
      App.SoilVolumeDialog.open = function (part) { opened = part; };
      var rows = ui.host.querySelectorAll('.soil-body-section tbody tr');
      rows[1].dispatchEvent(new MouseEvent('mousedown'));
      T.ok(rows[1].classList.contains('selected'));
      T.ok(!rows[0].classList.contains('selected'));
      var name = rows[1].querySelector('input');
      name.value = 'Renamed fill'; name.dispatchEvent(new Event('change'));
      var select = rows[1].querySelector('select');
      select.value = 'm2'; select.dispatchEvent(new Event('change'));
      T.eq([parts[1].label, parts[1].mat, parts[1].color], ['Renamed fill', 'm2', '#c4a86a']);
      T.eq(committed, ['fill_2', 'fill_2']);
      rows[1].querySelector('button').click();
      T.eq(opened, parts[1]);
      T.eq(ui.host.querySelectorAll('.dialog').length, 0);
    }, parts).then(restore, function (error) { restore(); throw error; });
  });

  /* ── Custom soil volumes ───────────────────────────────────────────── */

  test('a custom volume action saves the stack first, then opens its form', function () {
    var opened, soil = App.SoilVolumeDialog;
    App.SoilVolumeDialog = { open: function (part, options) { opened = options; },
                             measure: soil.measure };
    return withWindow(stack(), function (ui) {
      var buttons = ui.host.querySelectorAll('.soil-body-section .lay-toolbar button');
      T.eq(Array.from(buttons).map(function (b) { return b.textContent; }),
           ['Add', 'Insert', 'Delete']);
      T.eq(buttons[2].disabled, true, 'nothing to delete');
      ui.type(0, 3, '-10');
      buttons[1].click();
      return new Promise(function (done) { setTimeout(done, 0); }).then(function () {
        T.eq(ui.sent.length, 1);
        T.eq(levels(ui.sent[0][1].layers), [['L1', 0, -10], ['L2', -10, -25]]);
        T.eq(opened.insertBefore, null);
        ui.click('Cancel');
      });
    }).then(function () { App.SoilVolumeDialog = soil; },
            function (error) { App.SoilVolumeDialog = soil; throw error; });
  });

  test('deleting a custom soil body saves the stack, deletes the selected body, then reloads and redraws', function () {
    var deleted = [], order = [];
    var parts = [{ key: 'fill one', label: 'Fill', mat: 'm2' }];
    return withWindow(stack(), function (ui) {
      var patches = App.LivePatches;
      App.LivePatches = Object.assign({}, patches, {
        deleteRequest: function (path) {
          T.eq(ui.sent.length, 1, 'the stack is saved before deleting geometry');
          deleted.push(path); order.push('delete');
          App.PROJECT.custom_parts = [];
          return Promise.resolve();
        }
      });
      App.Model.load = function () { order.push('load'); return Promise.resolve(); };
      App.Viewport.refresh = function () { order.push('refresh'); return Promise.resolve(); };
      var button = ui.host.querySelectorAll('.soil-body-section .lay-toolbar button')[2];
      button.click();
      T.ok(button.disabled, 'a pending delete cannot be submitted twice');
      function restore() { App.LivePatches = patches; }
      return new Promise(function (resolve) { setTimeout(resolve, 0); }).then(function () {
        T.eq(deleted, ['/api/geometry/parts/fill%20one']);
        T.eq(order, ['delete', 'load', 'refresh']);
        T.eq(ui.host.querySelectorAll('.soil-body-section tbody tr').length, 0);
        T.ok(ui.host.querySelectorAll('.soil-body-section .lay-toolbar button')[2].disabled);
        ui.click('Cancel');
      }).then(restore, function (error) { restore(); throw error; });
    }, parts);
  });

  test('a refused custom-soil deletion preserves its row and allows a retry', function () {
    var parts = [{ key: 'fill', label: 'Fill', mat: 'm2' }];
    return withWindow(stack(), function (ui) {
      var patches = App.LivePatches, loaded = 0;
      App.LivePatches = Object.assign({}, patches, {
        deleteRequest: function () { return Promise.reject(new Error('A stage still uses Fill')); }
      });
      App.Model.load = function () { loaded += 1; return Promise.resolve(); };
      var button = ui.host.querySelectorAll('.soil-body-section .lay-toolbar button')[2];
      button.click();
      function restore() { App.LivePatches = patches; }
      return new Promise(function (resolve) { setTimeout(resolve, 0); }).then(function () {
        T.eq(loaded, 0);
        T.eq(ui.host.querySelectorAll('.soil-body-section tbody tr').length, 1);
        T.eq(button.disabled, false);
        T.ok(ui.said.some(function (text) { return /A stage still uses Fill/.test(text); }));
        ui.click('Cancel');
      }).then(restore, function (error) { restore(); throw error; });
    }, parts);
  });

  test('the soil dialog and the Model explorer’s layer Delete are the live ones',
       function () {
    var command = App.Command, action = App.runAction;
    App.Command = { note: function () {}, ok: function () {}, err: function () {},
                    write: function () {}, run: function () {} };
    App.runAction = function () {};
    try {
      App.LivePatches.install();
      T.ok(App.Dialogs.soilLayers === D.open, 'App.Dialogs.soilLayers');
      T.ok(App.deleteLayerById === D.removeById, 'App.deleteLayerById');
    } finally {
      App.Command = command; App.runAction = action;
      App.LivePatches.resetForTests();
    }
  });
})();
