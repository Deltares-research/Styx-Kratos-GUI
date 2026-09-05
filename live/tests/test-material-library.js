(function () {
  test('material library copies defaults with unique ids and names across projects', function () {
    var saved = App.MATERIALS;
    try {
      App.MATERIALS = [];
      var preset = App.MaterialLibrary.soils()[0];
      var first = App.MaterialLibrary.addSoil(preset.id);
      var second = App.MaterialLibrary.addSoil(preset.id);
      T.ok(first.id !== second.id);
      T.ok(first.name !== second.name);
      first.E = 123;
      preset.E = 456;
      T.ok(App.MaterialLibrary.soils()[0].E !== 123);
      T.ok(App.MaterialLibrary.soils()[0].E !== 456);
      App.MATERIALS = [{ id: second.id, name: second.name }];
      var third = App.MaterialLibrary.addSoil(App.MaterialLibrary.soils()[0].id);
      T.ok(third.id !== second.id);
      T.eq(App.Model.materialsToServer([third])[0].r_inter, third.rInter);
    } finally { App.MATERIALS = saved; }
  });

  test('interface presets change only interface properties and remain reusable', function () {
    var m = Object.assign({}, App.MATERIALS[0]);
    var before = Object.assign({}, m);
    var preset = App.MaterialLibrary.interfaces()[0];
    App.MaterialLibrary.applyInterface(m, preset.id);
    T.eq(m.rInter, preset.rInter);
    T.eq(m.interfacePerm, preset.interfacePerm);
    m.rInter = before.rInter; m.interfacePerm = before.interfacePerm;
    T.eq(m, before);
    preset.rInter = 0.01;
    T.ok(App.MaterialLibrary.interfaces()[0].rInter !== 0.01);
  });

  test('material library rejects missing presets without changing the project', function () {
    var before = JSON.stringify(App.MATERIALS);
    return T.rejects(function () { App.MaterialLibrary.addSoil('missing'); }).then(function () {
      T.eq(JSON.stringify(App.MATERIALS), before);
      return T.rejects(function () { App.MaterialLibrary.applyInterface(App.MATERIALS[0], 'missing'); });
    }).then(function () { T.eq(JSON.stringify(App.MATERIALS), before); });
  });

  test('material dialog adds library soil, applies interface preset and cancels both', function () {
    var saved = App.MATERIALS;
    var host = document.createElement('div'); host.id = 'modal-layer'; document.body.appendChild(host);
    App.MATERIALS = [];
    try {
      App.Dialogs.materials();
      var apply = host.querySelector('[data-action="apply-interface-preset"]');
      T.ok(apply.disabled);
      host.querySelector('[data-action="add-soil-preset"]').click();
      T.eq(App.MATERIALS.length, 1);
      T.ok(!apply.disabled);
      apply.click();
      T.eq(App.MATERIALS[0].rInter, App.MaterialLibrary.interfaces()[0].rInter);
      Array.from(host.querySelectorAll('.dlg-foot button')).find(function (b) {
        return b.textContent === 'Cancel';
      }).click();
      T.eq(App.MATERIALS.length, 0);
    } finally {
      if (host.querySelector('.dlg-x')) host.querySelector('.dlg-x').click();
      host.remove(); App.MATERIALS = saved;
    }
  });
})();
