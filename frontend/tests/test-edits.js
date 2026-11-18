/* ══════════════════════════════════════════════════════════════════════
   test-edits.js — what the GUI's Delete sends, held to the command line's.

   The GUI deletes a record by sending the whole new list, or a DELETE; kratos-cli
   removes it by id. fixtures/edits.js is written from the Python by
   tests/cli/test_edit_parity.py, which checks that the server, given each request,
   makes the edit kratos-cli makes. This suite checks that the GUI sends exactly that
   request, driven the way the user drives it.

   A Structure-mode Delete is one function call, so it runs without a browser too. The
   windows, the stage list, the tree and the command box need the DOM and the live
   layer (patches.js `install`): those run in the browser suite only.
   ══════════════════════════════════════════════════════════════════════ */

(function () {

  var F = window.EDITS_FIXTURE;

  function copy(value) { return JSON.parse(JSON.stringify(value)); }

  /* ── A Structure-mode Delete: App.<c.call>(c.target) ───────────────── */

  /* Each project list, and the global the Structure mode reads it from. */
  var GLOBALS = {
    beams: 'BEAMS', beam_sections: 'BEAM_SECTIONS', panel_sections: 'PANEL_SECTIONS',
    anchors: 'ANCHORS', anchor_sections: 'ANCHOR_SECTIONS', interfaces: 'INTERFACES',
    interface_sections: 'INTERFACE_SECTIONS', loads: 'LOADS', normal_loads: 'NORMAL_LOADS',
    boundary_conditions: 'BOUNDARY_CONDITIONS', layers: 'LAYERS', lines: 'LINES'
  };
  var STUBBED = ['Api', 'Model', 'Viewport', 'Command', 'Explorer', 'state',
                 'selectObject', 'PROJECT'].concat(Object.keys(GLOBALS).map(function (k) {
                   return GLOBALS[k];
                 }));

  function sentBy(c) {
    var saved = {};
    STUBBED.forEach(function (key) { saved[key] = App[key]; });
    function restore() { STUBBED.forEach(function (key) { App[key] = saved[key]; }); }

    var project = F.projects[c.project];
    var sent = [];
    App.PROJECT = copy(project);
    Object.keys(GLOBALS).forEach(function (field) {
      App[GLOBALS[field]] = copy(project[field] || []);
    });
    App.Api = {
      patch: function (path, body) {
        sent.push({ method: 'PATCH', path: path, body: copy(body) });
        return Promise.resolve({ project: App.PROJECT });
      }
    };
    App.Model = { apply: function () {}, load: function () { return Promise.resolve(); } };
    App.Viewport = { refresh: function () { return Promise.resolve(); } };
    App.Command = { ok: function () {}, err: function () {}, note: function () {} };
    App.Explorer = null;
    App.state = { selection: null };
    App.selectObject = null;

    var parts = c.call.split('.');
    return Promise.resolve()
      .then(function () { return App[parts[0]][parts[1]](c.target); })
      .then(function () { restore(); return sent; },
            function (error) { restore(); throw error; });
  }

  /* ── The live GUI: the project applied, patches.js installed ───────── */

  /* Everything App.Model.apply and LivePatches.install write, put back afterwards. */
  var LIVE = ['Api', 'Model', 'Viewport', 'Command', 'Explorer', 'Dialogs', 'History',
              'state', 'PROJECT', 'runAction', 'selectObject', 'setMode', 'deleteLayerById',
              'commitSelectionEdit', 'OBJECT_PROPS', 'LAYERS', 'MATERIALS', 'LOADS', 'BEAMS',
              'BEAM_SECTIONS', 'PANEL_SECTIONS', 'ANCHORS', 'ANCHOR_SECTIONS', 'INTERFACES',
              'INTERFACE_SECTIONS', 'NORMAL_LOADS', 'BOUNDARY_CONDITIONS'];

  /* `drive(c, layer, dock)` on the live GUI holding c's project; gives back each
     request it made, a PATCH through App.Api or a DELETE through fetch. */
  function live(c, drive) {
    var saved = { trees: {}, fetch: window.fetch };
    LIVE.forEach(function (key) { saved[key] = App[key]; });
    Object.keys(App.TREES || {}).forEach(function (m) { saved.trees[m] = App.TREES[m]; });
    var hosts = ['modal-layer', 'list-phases'].map(function (id) {
      var node = document.createElement('div');
      node.id = id;
      document.body.appendChild(node);
      return node;
    });
    var sent = [], refusals = [];

    App.OBJECT_PROPS = Object.assign({}, App.OBJECT_PROPS);
    App.state = { mode: 'soil', stage: null, selection: null };
    App.Model.apply(copy(F.projects[c.project]));
    App.Model = Object.assign({}, App.Model, {
      apply: function () {}, load: function () { return Promise.resolve(); }
    });
    function answer() { return Promise.resolve({ project: App.PROJECT, edit_notes: [] }); }
    function recorded(method) {
      return function (path, body) {
        sent.push({ method: method, path: path, body: body === undefined ? null : copy(body) });
        return answer();
      };
    }
    App.Api = { base: '', told: function (reply) { return reply; },
                patch: recorded('PATCH'), post: recorded('POST'), put: recorded('PUT') };
    window.fetch = function (url, options) {
      sent.push({ method: (options && options.method) || 'GET', path: url, body: null });
      return Promise.resolve({ ok: true, status: 200, json: answer });
    };
    App.Command = { ok: function () {}, note: function () {}, write: function () {},
                    err: function (text) { refusals.push(text); }, run: function () {} };
    App.Viewport = Object.assign({}, App.Viewport, {
      refresh: function () { return Promise.resolve(); }, applyStageVisibility: function () {}
    });
    // Copies, because install() writes into them.
    App.Explorer = Object.assign({}, App.Explorer, {
      mountTree: function () {}, mountSelection: function () {}
    });
    App.Dialogs = Object.assign({}, App.Dialogs);
    App.History = { install: function () {}, reset: function () {},
                    canUndo: function () { return false; }, canRedo: function () { return false; } };
    // The shell's own functions, which install() wraps -- js/app.js is not on this page.
    App.runAction = function () {};
    App.selectObject = function () {};
    App.setMode = function (mode) { App.state.mode = mode; };
    App.LivePatches.resetForTests();
    App.LivePatches.install();

    function restore() {
      hosts.forEach(function (node) { node.remove(); });
      App.LivePatches.resetForTests();
      window.fetch = saved.fetch;
      LIVE.forEach(function (key) { App[key] = saved[key]; });
      Object.keys(saved.trees).forEach(function (m) { App.TREES[m] = saved.trees[m]; });
      App.Model.rebuildDerived();
    }
    return Promise.resolve()
      .then(function () { return drive(c, hosts[0], hosts[1]); })
      .then(function () { return new Promise(function (done) { setTimeout(done, 20); }); })
      .then(function () {
        restore();
        T.eq(refusals, [], 'the GUI refused nothing');
        return sent;
      }, function (error) { restore(); throw error; });
  }

  function press(root, selector, label) {
    var button = Array.prototype.filter.call(root.querySelectorAll(selector), function (b) {
      return b.textContent.trim() === label;
    })[0];
    if (!button) throw new Error('no ' + label + ' button in ' + selector);
    button.click();
  }

  function at(records, id) {
    return records.map(function (record) { return record.id; }).indexOf(id);
  }

  var DRIVERS = {
    /* The soil layers window: the layer's row picked, Delete, then OK. */
    'Dialogs.soilLayers': function (c, layer) {
      App.Dialogs.soilLayers();
      var row = layer.querySelectorAll('.lay-table-wrap tbody tr')[at(App.LAYERS, c.target)];
      row.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
      press(layer, '.lay-pane > .lay-toolbar button', 'Delete');
      press(layer, '.dlg-foot .btn', 'OK');
    },
    /* The model tree's Delete on a layer row: what js/explorer.js `deleteLayerNode`
       calls. */
    'deleteLayerById': function (c) {
      var refused = App.deleteLayerById(c.target);
      if (refused) throw new Error(refused);
      return App.commitSelectionEdit(null);
    },
    /* The stage list: the stage selected, then the toolbar's Delete. */
    'Explorer.mountPhases': function (c, layer, dock) {
      App.state.mode = 'staged';
      App.state.phase = c.target;
      App.Explorer.mountPhases();
      var drawn = App.UI.icon('delete').innerHTML;
      Array.prototype.filter.call(dock.querySelectorAll('.stage-toolbar button.tbtn'),
                                  function (b) {
                                    return b.querySelector('svg').innerHTML === drawn;
                                  })[0].click();
    },
    /* The Material sets window: the set picked, Delete, then OK. */
    'Dialogs.materials': function (c, layer) {
      App.Dialogs.materials();
      layer.querySelector('[data-material="' + c.target + '"]').click();
      layer.querySelector('[data-action="delete"]').click();
      press(layer, '.dlg-foot .btn', 'OK');
    },
    /* The model tree's Delete on a custom volume (patches.js `deleteObject`). */
    'LivePatches.deleteCustomPart': function (c) {
      return App.LivePatches.deleteCustomPart(c.target);
    },
    /* The model tree's Delete part on one part of a cut layer (patches.js
       `deleteBodyPart`, after its OK). */
    'LivePatches.deleteBody': function (c) {
      return App.LivePatches.deleteBody(c.target);
    },
    /* The command box: `cleargeometry`. */
    'Command.run': function () { return App.Command.run('cleargeometry'); }
  };

  F.cases.forEach(function (c) {
    var drive = DRIVERS[c.call];
    if (drive && typeof document === 'undefined') return;   // the browser suite drives it
    T.test('a Delete sends what kratos-cli removes: ' + c.title, function () {
      return (drive ? live(c, drive) : sentBy(c)).then(function (sent) {
        T.eq(sent.map(function (s) { return s.method + ' ' + s.path; }),
             [c.method + ' ' + c.route], 'one request');
        T.eq(sent[0].body, c.body);
      });
    });
  });

})();
