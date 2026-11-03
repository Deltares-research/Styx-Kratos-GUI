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
      first.variables.YOUNG_MODULUS = 123;
      preset.variables.YOUNG_MODULUS = 456;
      T.ok(App.MaterialLibrary.soils()[0].variables.YOUNG_MODULUS !== 123);
      T.ok(App.MaterialLibrary.soils()[0].variables.YOUNG_MODULUS !== 456);
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

  test('material dialog adds library soil, has no interface preset and cancels', function () {
    var saved = App.MATERIALS, savedLayers = App.LAYERS;
    var host = document.createElement('div'); host.id = 'modal-layer'; document.body.appendChild(host);
    // Closing the dialog remounts the Model explorer, which needs its host.
    var tree = document.createElement('div'); tree.id = 'tree-model'; document.body.appendChild(tree);
    // No materials means no layers: a layer pointing at a missing material is not a state the app can be in.
    App.MATERIALS = []; App.LAYERS = [];
    try {
      App.Dialogs.materials();
      T.eq(host.querySelector('[data-action="apply-interface-preset"]'), null);
      host.querySelector('[data-action="add-soil-preset"]').click();
      T.eq(App.MATERIALS.length, 1);
      Array.from(host.querySelectorAll('.dlg-foot button')).find(function (b) {
        return b.textContent === 'Cancel';
      }).click();
      T.eq(App.MATERIALS.length, 0);
    } finally {
      if (host.querySelector('.dlg-x')) host.querySelector('.dlg-x').click();
      host.remove(); tree.remove(); App.MATERIALS = saved; App.LAYERS = savedLayers;
    }
  });
})();

/* ── A material's Kratos block survives the round trip ──────────────────────
   PATCH /api/project/materials replaces the whole library, so a material the dialog
   never opened has to go back exactly as it came: every variable, a string, a list, a
   law nobody here knows. A variable dropped on the way is a variable the next save
   deletes -- which is how porosity and K0 were once lost without a word. */

(function () {
  function serverMaterial(extra) {
    return Object.assign({
      id: 'm9', name: 'Sand, dense', color: '#c4a86a',
      constitutive_law: 'SmallStrainUDSM2DPlaneStrainLaw',
      variables: { YOUNG_MODULUS: 4.5e7, POROSITY: 0.33, K0_NC: 0.46,
                   GEO_DRAINAGE_TYPE: 'CONSTANT_PW_FIELD', UDSM_PARAMETERS: [1, 2.5] },
      tables: {}, r_inter: 0.7, interface_permeability: 'Neutral'
    }, extra || {});
  }

  function roundTrip(extra) {
    var project = { domain: {}, layers: [], custom_parts: [],
                    materials: [serverMaterial(extra)] };
    return App.Model.materialsToServer(App.Model.fromProject(project).MATERIALS)[0];
  }

  test('every field the server sent comes back, for a material nothing touched',
       function () {
    var original = serverMaterial();
    var sent = roundTrip();
    Object.keys(original).forEach(function (key) {
      T.eq(sent[key], original[key], 'field ' + key + ' did not survive');
    });
    T.eq(Object.keys(sent).sort(), Object.keys(original).sort(),
         'the round trip changed the set of fields');
  });

  test('the browser\'s copy is its own: an edit does not reach the project it came from',
       function () {
    var project = { domain: {}, layers: [], custom_parts: [],
                    materials: [serverMaterial()] };
    var mapped = App.Model.fromProject(project).MATERIALS[0];
    mapped.variables.YOUNG_MODULUS = 1;
    T.eq(project.materials[0].variables.YOUNG_MODULUS, 4.5e7);
  });

  test('a library preset arrives in the project\'s units and dimension', function () {
    var saved = App.PROJECT, savedMaterials = App.MATERIALS;
    try {
      App.MATERIALS = [];
      App.PROJECT = { unit_system: 'kN', dimension: 3 };
      var m = App.MaterialLibrary.addSoil('m2');
      T.eq(m.constitutive_law, 'GeoMohrCoulombLaw3D', 'a soil with a strength is Mohr-Coulomb');
      T.near(m.variables.GEO_COHESION, 0.5, 1e-12, 'its own cohesion, in kPa');
      T.eq(m.variables.GEO_DILATANCY_ANGLE, 0, 'and the model\'s defaults for the rest');
      T.near(m.variables.YOUNG_MODULUS, 2.5e4, 1e-6);
      T.near(m.variables.DENSITY_SOLID, 18 / 9.81, 1e-9);
      T.eq(m.variables.GEO_FRICTION_ANGLE, 32.0);
      App.PROJECT = { unit_system: 'SI', dimension: 2 };
      var si = App.MaterialLibrary.addSoil('m2');
      T.eq(si.constitutive_law, 'GeoMohrCoulombLawPlaneStrain');
      T.eq(App.MaterialLibrary.addSoil('m6').constitutive_law, 'GeoLinearElasticPlaneStrain2DLaw',
           'bedrock has no strength: linear elastic');
      T.eq(si.variables.YOUNG_MODULUS, 2.5e7);
    } finally { App.PROJECT = saved; App.MATERIALS = savedMaterials; }
  });
})();
