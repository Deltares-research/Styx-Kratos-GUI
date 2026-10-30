/* ══════════════════════════════════════════════════════════════════════
   test-edits.js — what the GUI's Delete sends, held to the command line's.

   The GUI deletes a record by sending the whole new list; kratos-cli removes it by
   id. fixtures/edits.js is written from the Python by tests/cli/test_edit_parity.py,
   which checks that the server, given each body, makes the edit kratos-cli makes.
   This suite checks that the GUI's own function sends exactly that body.
   ══════════════════════════════════════════════════════════════════════ */

(function () {

  var F = window.EDITS_FIXTURE;

  /* Each project list, and the global the Structure mode reads it from. */
  var GLOBALS = {
    beams: 'BEAMS', beam_sections: 'BEAM_SECTIONS', panel_sections: 'PANEL_SECTIONS',
    anchors: 'ANCHORS', anchor_sections: 'ANCHOR_SECTIONS', interfaces: 'INTERFACES',
    interface_sections: 'INTERFACE_SECTIONS', loads: 'LOADS', normal_loads: 'NORMAL_LOADS',
    boundary_conditions: 'BOUNDARY_CONDITIONS', layers: 'LAYERS'
  };
  var STUBBED = ['Api', 'Model', 'Viewport', 'Command', 'Explorer', 'state',
                 'selectObject', 'PROJECT'].concat(Object.keys(GLOBALS).map(function (k) {
                   return GLOBALS[k];
                 }));

  function copy(value) { return JSON.parse(JSON.stringify(value)); }

  /* Call App.<c.call>(c.target) on c.project, and give back what it sent. */
  function sentBy(c) {
    var saved = {};
    STUBBED.forEach(function (key) { saved[key] = App[key]; });
    function restore() { STUBBED.forEach(function (key) { App[key] = saved[key]; }); }

    var sent = [];
    App.PROJECT = copy(c.project);
    Object.keys(GLOBALS).forEach(function (field) {
      App[GLOBALS[field]] = copy(c.project[field] || []);
    });
    App.Api = {
      patch: function (path, body) {
        sent.push({ path: path, body: copy(body) });
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

  F.cases.forEach(function (c) {
    T.test('a Delete sends what kratos-cli removes: ' + c.title, function () {
      if (c.call === 'SoilLayersDialog.remove') {
        var layers = copy(c.project.layers);
        var index = layers.map(function (layer) { return layer.id; }).indexOf(c.target);
        App.SoilLayersDialog.remove(layers, index);
        T.eq(layers, c.body.layers);
        return null;
      }
      return sentBy(c).then(function (sent) {
        T.eq(sent.length, 1, 'one request');
        T.eq(sent[0].path, c.route);
        T.eq(sent[0].body, c.body);
      });
    });
  });

})();
