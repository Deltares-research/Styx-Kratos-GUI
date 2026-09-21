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

/* ── Porosity and k0_nc survive the round trip ──────────────────────────────
   `Material.porosity` and `Material.k0_nc` were added server-side for the CROW
   reference (plan sec 7.4) under one rule: the user owns the value, and a derived
   default is only for when there is not one. The browser's own material record never
   learned either field, so fromProject dropped them on the way in and
   materialsToServer omitted them on the way out -- and PATCH /api/project/materials
   replaces the whole library. Opening the material dialog on a project that had them
   and pressing OK therefore reset both to null, silently: the deck then fell back to
   DEFAULT_POROSITY and to Jaky, and the user's numbers were gone with nothing said.

   Round-tripping them is the fix, and is what these assert. The editor rows on top of
   them are in js/dialogs.js' materialEditor. */

(function () {
  function serverMaterial(extra) {
    return Object.assign({
      id: 'm9', name: 'Sand, dense', model: 'Mohr-Coulomb', type: 'Drained',
      color: '#c4a86a', g_unsat: 18, g_sat: 20.5, E: 25000, nu: 0.28,
      c: 0.5, phi: 32, k: 1.5, r_inter: 0.7, interface_permeability: 'Neutral'
    }, extra || {});
  }

  function roundTrip(extra) {
    var project = { domain: {}, boreholes: [], layers: [], custom_parts: [],
                    materials: [serverMaterial(extra)] };
    return App.Model.materialsToServer(App.Model.fromProject(project).MATERIALS)[0];
  }

  test('a typed porosity survives the material round trip', function () {
    T.eq(roundTrip({ porosity: 0.42 }).porosity, 0.42);
  });

  test('a typed k0_nc survives the material round trip', function () {
    T.eq(roundTrip({ k0_nc: 0.62 }).k0_nc, 0.62);
  });

  /* Null is the value that means "derive it" -- DEFAULT_POROSITY for the one, Jaky's
     1 - sin(phi) for the other -- so it has to travel as null rather than be dropped
     or turned into a number here. Sending it absent would be read the same way by the
     server, but only by accident; saying it explicitly is what keeps the two ends
     agreeing about who decides. */
  test('an unset porosity and k0_nc travel as null, not as an invented default',
       function () {
    var sent = roundTrip();
    T.eq(sent.porosity, null, 'porosity was not sent as null');
    T.eq(sent.k0_nc, null, 'k0_nc was not sent as null');
  });

  /* The whole library goes in one PATCH, so a material the dialog never opened has to
     come back out byte for byte -- that is the case the original bug actually hit. */
  test('every field the server sent comes back, for a material nothing touched',
       function () {
    var original = serverMaterial({ porosity: 0.33, k0_nc: 0.46 });
    var sent = roundTrip({ porosity: 0.33, k0_nc: 0.46 });
    Object.keys(original).forEach(function (key) {
      T.eq(sent[key], original[key], 'field ' + key + ' did not survive');
    });
    T.eq(Object.keys(sent).sort(), Object.keys(original).sort(),
         'the round trip changed the set of fields');
  });
})();
