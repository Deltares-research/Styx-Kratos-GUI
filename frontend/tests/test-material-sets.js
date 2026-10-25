/* ══════════════════════════════════════════════════════════════════
   test-material-sets.js — the Material sets dialog, for Kratos property sets.

   A soil is what Kratos reads: a constitutive law and its Variables, under Kratos'
   names, in the project's units (core/model/schemas.py). The dialog shows exactly that,
   labels each number in the project's system, edits it in place on App.MATERIALS (the
   contract patches.js saves through), and refuses what the server would refuse. Its
   first choice is the soil model (App.SoilModels), which sets the law and the
   parameters listed, with their defaults.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  function sand() {
    return { id: 'm1', name: 'Sand', color: '#c4a86a',
             constitutive_law: 'GeoLinearElasticPlaneStrain2DLaw',
             variables: { GEO_DRAINAGE_TYPE: 'CONSTANT_PW_FIELD', YOUNG_MODULUS: 2.5e4,
                          POISSON_RATIO: 0.28, DENSITY_SOLID: 1.83486, POROSITY: 0.3 },
             tables: {}, rInter: 0.7, interfacePerm: 'Neutral' };
  }

  /* The dialog in a throwaway host, on a kN project holding one sand. */
  function withDialog(run) {
    var saved = { materials: App.MATERIALS, layers: App.LAYERS, project: App.PROJECT };
    var host = document.createElement('div'); host.id = 'modal-layer'; document.body.appendChild(host);
    var tree = document.createElement('div'); tree.id = 'tree-model'; document.body.appendChild(tree);
    App.MATERIALS = [sand()]; App.LAYERS = [];
    App.PROJECT = Object.assign({}, App.PROJECT || {}, { unit_system: 'kN', dimension: 2 });
    try {
      App.MaterialSets.open();
      return run(host);
    } finally {
      Array.prototype.slice.call(host.querySelectorAll('.dlg-x')).reverse().forEach(function (x) { x.click(); });
      host.remove(); tree.remove();
      App.MATERIALS = saved.materials; App.LAYERS = saved.layers; App.PROJECT = saved.project;
    }
  }

  function variableInput(host, name) {
    return host.querySelector('.material-variables [data-variable="' + name + '"]');
  }

  function type(input, text) {
    input.value = text;
    input.dispatchEvent(new Event('change'));
  }

  function openProperties(host) {
    host.querySelector('[data-action="material-properties"]').click();
  }

  function field(host, name) {
    return host.querySelector('.material-variables [data-field="' + name + '"]');
  }

  function choose(control, value) {
    control.value = value;
    control.dispatchEvent(new Event('change'));
  }

  function hint(host) {
    return host.querySelector('.material-variables').parentNode.querySelector('.lay-hint');
  }

  T.test('the table shows the soil model and Kratos variables, headed in the project units', function () {
    withDialog(function (host) {
      var heads = Array.prototype.map.call(host.querySelectorAll('.material-sets th'),
                                           function (th) { return th.textContent; });
      T.ok(heads.indexOf('Soil model') >= 0, heads.join(' | '));
      T.ok(heads.indexOf('YOUNG_MODULUS [kPa]') >= 0, heads.join(' | '));
      T.ok(heads.indexOf('DENSITY_SOLID [t/m³]') >= 0, heads.join(' | '));
      var row = host.querySelector('.material-sets tbody tr');
      T.ok(/Linear elastic/.test(row.textContent), row.textContent);
      T.eq(row.children[2].title, 'GeoLinearElasticPlaneStrain2DLaw');
      T.ok(/25000/.test(row.textContent), row.textContent);
    });
  });

  T.test('a variable typed in the editor is what the material holds, as a number', function () {
    withDialog(function (host) {
      openProperties(host);
      type(variableInput(host, 'YOUNG_MODULUS'), '3.5e4');
      T.eq(App.MATERIALS[0].variables.YOUNG_MODULUS, 3.5e4);
    });
  });

  T.test('a value the server would refuse is put back, and said', function () {
    withDialog(function (host) {
      openProperties(host);
      type(variableInput(host, 'POISSON_RATIO'), '0.6');
      T.eq(App.MATERIALS[0].variables.POISSON_RATIO, 0.28);
      var hint = host.querySelector('.material-variables').parentNode.querySelector('.lay-hint');
      T.ok(/POISSON_RATIO/.test(hint.textContent), hint.textContent);
    });
  });

  T.test('a derivable variable left blank is left out, for the export to derive', function () {
    withDialog(function (host) {
      openProperties(host);
      type(variableInput(host, 'POROSITY'), '');
      T.ok(!('POROSITY' in App.MATERIALS[0].variables));
      T.eq(variableInput(host, 'POROSITY').placeholder, 'derived');
    });
  });

  T.test('a variable its law needs cannot be blanked', function () {
    withDialog(function (host) {
      openProperties(host);
      type(variableInput(host, 'DENSITY_SOLID'), '');
      T.eq(App.MATERIALS[0].variables.DENSITY_SOLID, 1.83486);
    });
  });

  T.test('any other Kratos variable can be added, text and lists too', function () {
    withDialog(function (host) {
      openProperties(host);
      host.querySelector('[data-field="new-variable"]').value = 'ocr';
      host.querySelector('[data-field="new-value"]').value = '1.5';
      host.querySelector('[data-action="add-variable"]').click();
      T.eq(App.MATERIALS[0].variables.OCR, 1.5);
      host.querySelector('[data-field="new-variable"]').value = 'UDSM_PARAMETERS';
      host.querySelector('[data-field="new-value"]').value = '[1, 2]';
      host.querySelector('[data-action="add-variable"]').click();
      T.eq(App.MATERIALS[0].variables.UDSM_PARAMETERS, [1, 2]);
      T.ok(variableInput(host, 'OCR'), 'the new variable has a row');
    });
  });

  T.test('the law of a soil model is shown, not typed', function () {
    withDialog(function (host) {
      openProperties(host);
      T.eq(field(host, 'soil-model').value, 'linear_elastic');
      T.ok(field(host, 'constitutive_law').readOnly, 'read-only');
      T.eq(field(host, 'constitutive_law').value, 'GeoLinearElasticPlaneStrain2DLaw');
    });
  });

  T.test('any other law is the user\'s to type, under Other', function () {
    withDialog(function (host) {
      openProperties(host);
      choose(field(host, 'soil-model'), 'other');
      var law = field(host, 'constitutive_law');
      T.ok(!law.readOnly, 'typed');
      type(law, 'SmallStrainUDSM2DPlaneStrainLaw');
      T.eq(App.MATERIALS[0].constitutive_law, 'SmallStrainUDSM2DPlaneStrainLaw');
      T.eq(field(host, 'soil-model').value, 'other');
      T.ok(variableInput(host, 'YOUNG_MODULUS'), 'what the soil carries is still listed');
      T.ok(!variableInput(host, 'K0_NC'), 'no model\'s list for a law of no model');
    });
  });

  T.test('a Mohr-Coulomb law typed under Other is Mohr-Coulomb', function () {
    withDialog(function (host) {
      openProperties(host);
      choose(field(host, 'soil-model'), 'other');
      type(field(host, 'constitutive_law'), 'GeoMohrCoulombLawPlaneStrain');
      T.eq(field(host, 'soil-model').value, 'mohr_coulomb');
      T.eq(App.MATERIALS[0].variables.GEO_DILATANCY_ANGLE, 0);
    });
  });

  T.test('choosing Mohr-Coulomb sets its law and fills in its defaults, keeping typed values', function () {
    withDialog(function (host) {
      openProperties(host);
      choose(field(host, 'soil-model'), 'mohr_coulomb');
      var m = App.MATERIALS[0];
      T.eq(m.constitutive_law, 'GeoMohrCoulombLawPlaneStrain');
      T.eq(m.variables.YOUNG_MODULUS, 2.5e4, 'the typed stiffness is kept');
      T.eq(m.variables.POROSITY, 0.3, 'the typed porosity is kept');
      T.near(m.variables.GEO_COHESION, 1.0, 1e-12, '1 kPa in a kN project');
      T.eq(m.variables.GEO_FRICTION_ANGLE, 30);
      T.eq(m.variables.GEO_DILATANCY_ANGLE, 0);
      T.eq(m.variables.GEO_ENABLE_TENSION_CUT_OFF, false);
      T.eq(m.variables.RETENTION_LAW, 'SaturatedBelowPhreaticLevelLaw');
      T.eq(App.PropertySets.validate('soil', m), null);
      T.ok(/Filled in from the Mohr-Coulomb defaults: .*GEO_DILATANCY_ANGLE/.test(hint(host).textContent),
           hint(host).textContent);
      T.ok(!hint(host).classList.contains('invalid'), 'a notice, not an error');
      var titles = Array.prototype.map.call(host.querySelectorAll('.material-variables h4'),
                                            function (h) { return h.textContent; });
      T.ok(titles.indexOf('Strength') >= 0 && titles.indexOf('Flow') >= 0, titles.join(' | '));
    });
  });

  T.test('the soil model follows the project\'s dimension', function () {
    withDialog(function (host) {
      App.PROJECT.dimension = 3;
      openProperties(host);
      choose(field(host, 'soil-model'), 'mohr_coulomb');
      T.eq(App.MATERIALS[0].constitutive_law, 'GeoMohrCoulombLaw3D');
    });
  });

  T.test('a text value is a drop-down of every value Kratos accepts', function () {
    withDialog(function (host) {
      openProperties(host);
      var drainage = variableInput(host, 'GEO_DRAINAGE_TYPE');
      T.eq(drainage.tagName, 'SELECT');
      T.eq(Array.prototype.map.call(drainage.options, function (o) { return o.value; }),
           ['CONSTANT_PW_FIELD', 'FULLY_COUPLED', 'DRAINED', 'UNDRAINED']);
      choose(drainage, 'UNDRAINED');
      T.eq(App.MATERIALS[0].variables.GEO_DRAINAGE_TYPE, 'UNDRAINED');
      T.ok(variableInput(host, 'GEO_POISSON_UNDRAINED'), 'an undrained soil lists its Poisson ratio');
      var retention = variableInput(host, 'RETENTION_LAW');
      T.eq(retention.value, 'SaturatedLaw', 'left out, the retention law is SaturatedLaw');
      T.ok(!('RETENTION_LAW' in App.MATERIALS[0].variables), 'and stays left out');
    });
  });

  T.test('a retention law chosen lists its parameters, with their defaults', function () {
    withDialog(function (host) {
      openProperties(host);
      choose(field(host, 'soil-model'), 'mohr_coulomb');
      T.ok(!variableInput(host, 'VAN_GENUCHTEN_GN'));
      choose(variableInput(host, 'RETENTION_LAW'), 'VanGenuchtenLaw');
      var m = App.MATERIALS[0];
      T.eq(m.variables.RETENTION_LAW, 'VanGenuchtenLaw');
      T.eq(m.variables.VAN_GENUCHTEN_GN, 1.377);
      T.near(m.variables.VAN_GENUCHTEN_AIR_ENTRY_PRESSURE, 2.611, 1e-12, 'kPa');
      T.ok(variableInput(host, 'VAN_GENUCHTEN_GN'), 'listed');
    });
  });

  T.test('the tension cut-off is a check box, and on it lists the tensile strength', function () {
    withDialog(function (host) {
      openProperties(host);
      choose(field(host, 'soil-model'), 'mohr_coulomb');
      var box = variableInput(host, 'GEO_ENABLE_TENSION_CUT_OFF');
      T.eq(box.type, 'checkbox');
      T.ok(!box.checked);
      T.ok(!variableInput(host, 'GEO_TENSILE_STRENGTH'));
      box.checked = true;
      box.dispatchEvent(new Event('change'));
      T.eq(App.MATERIALS[0].variables.GEO_ENABLE_TENSION_CUT_OFF, true);
      T.eq(App.MATERIALS[0].variables.GEO_TENSILE_STRENGTH, 0);
      T.ok(variableInput(host, 'GEO_TENSILE_STRENGTH'), 'listed');
    });
  });

  T.test('a dilatancy above the friction angle is refused and put back, and said', function () {
    withDialog(function (host) {
      openProperties(host);
      choose(field(host, 'soil-model'), 'mohr_coulomb');
      type(variableInput(host, 'GEO_DILATANCY_ANGLE'), '40');
      T.eq(App.MATERIALS[0].variables.GEO_DILATANCY_ANGLE, 0);
      T.ok(/GEO_DILATANCY_ANGLE cannot be larger/.test(hint(host).textContent), hint(host).textContent);
      T.ok(hint(host).classList.contains('invalid'));
    });
  });

  T.test('a value the model does not read is kept, under Other variables', function () {
    withDialog(function (host) {
      App.MATERIALS[0].variables.OCR = 1.5;
      openProperties(host);
      var titles = Array.prototype.map.call(host.querySelectorAll('.material-variables h4'),
                                            function (h) { return h.textContent; });
      T.ok(titles.indexOf('Other variables') >= 0, titles.join(' | '));
      T.ok(variableInput(host, 'OCR'));
    });
  });

  T.test('a new material is a valid set in the project\'s units and dimension', function () {
    withDialog(function (host) {
      host.querySelector('[data-action="new"]').click();
      var m = App.MATERIALS[1];
      T.eq(m.constitutive_law, 'GeoLinearElasticPlaneStrain2DLaw');
      T.near(m.variables.YOUNG_MODULUS, 1.0e4, 1e-6, 'kPa in a kN project');
      T.eq(App.PropertySets.validate('soil', m), null);
      T.ok(m.id !== App.MATERIALS[0].id);
    });
  });

  T.test('a duplicate is a copy of its own', function () {
    withDialog(function (host) {
      host.querySelector('[data-action="copy"]').click();
      var copy = App.MATERIALS[1];
      copy.variables.YOUNG_MODULUS = 1;
      T.eq(App.MATERIALS[0].variables.YOUNG_MODULUS, 2.5e4);
    });
  });

  T.test('the Material sets action opens this dialog, not the frozen one', function () {
    T.ok(typeof App.Dialogs.materials === 'function');
    withDialog(function (host) {
      T.ok(host.querySelector('.material-sets'), 'the property-set table');
      T.ok(!/γunsat/.test(host.textContent), 'no unit weight column');
    });
  });

})();
