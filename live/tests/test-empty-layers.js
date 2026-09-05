(function () {
  test('empty custom layer section offers creation and preserves stack in its save request', function () {
    var saved = { project: App.PROJECT, api: App.Api, model: App.Model,
      soil: App.SoilVolumeDialog, materials: App.MATERIALS, layers: App.LAYERS, boreholes: App.BOREHOLES };
    var dialog = document.createElement('div');
    dialog.innerHTML = '<div class="lay-pane"></div>';
    var request, opened;
    App.PROJECT = { custom_parts: [] }; App.MATERIALS = []; App.LAYERS = [];
    App.BOREHOLES = [{ id: 'bh1' }];
    App.Api = { patch: function (path, body) {
      request = body; return Promise.resolve({ project: App.PROJECT });
    } };
    App.Model = { materialsToServer: saved.model.materialsToServer, apply: function () {} };
    App.SoilVolumeDialog = { open: function (part, options) { opened = options; } };
    App.LivePatches.addSoilBodySection(dialog);
    var buttons = dialog.querySelectorAll('.soil-body-section .lay-toolbar button');
    T.eq(Array.from(buttons).map(function (b) { return b.textContent; }), ['Add', 'Insert', 'Delete']);
    T.eq(buttons[2].disabled, true);
    buttons[1].click();
    return new Promise(function (resolve) { setTimeout(resolve, 0); }).then(function () {
      T.eq(request.layers, []); T.eq(request.boreholes, [{ id: 'bh1' }]);
      T.eq(request.materials.length, 1);
      T.eq(opened.insertBefore, null);
    }).then(restore, function (error) { restore(); throw error; });
    function restore() {
      App.PROJECT = saved.project; App.Api = saved.api; App.Model = saved.model;
      App.SoilVolumeDialog = saved.soil; App.MATERIALS = saved.materials;
      App.LAYERS = saved.layers; App.BOREHOLES = saved.boreholes;
    }
  });
  test('empty borehole stack supports add, insert, delete and collision-free re-add', function () {
    var saved = { layers: App.LAYERS, boreholes: App.BOREHOLES, materials: App.MATERIALS };
    var host = document.createElement('div'); host.id = 'modal-layer'; document.body.appendChild(host);
    App.LAYERS = []; App.MATERIALS = [];
    App.BOREHOLES = [{ id: 'bh1', name: 'BH-1', x: 0, y: 0, head: 0, water: -1 }];
    try {
      App.Dialogs.soilLayers();
      function click(label) {
        Array.from(host.querySelectorAll('.lay-toolbar button')).find(function (b) {
          return b.textContent === label;
        }).click();
      }
      click('Insert');
      T.eq(App.LAYERS.length, 1);
      T.ok(App.MATERIALS.some(function (m) { return m.id === App.LAYERS[0].mat; }));
      click('Add'); click('Insert');
      T.eq(App.LAYERS.length, 3);
      click('Delete'); click('Add');
      T.eq(new Set(App.LAYERS.map(function (l) { return l.id; })).size, 3);
      click('Delete'); click('Delete'); click('Delete');
      T.eq(App.LAYERS.length, 0);
      click('Add'); T.eq(App.LAYERS.length, 1);
    } finally {
      host.querySelector('.dlg-x').click(); host.remove();
      App.LAYERS = saved.layers; App.BOREHOLES = saved.boreholes; App.MATERIALS = saved.materials;
    }
  });
})();
