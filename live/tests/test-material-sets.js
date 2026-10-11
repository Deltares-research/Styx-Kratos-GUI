/* ══════════════════════════════════════════════════════════════════
   test-material-sets.js — the Material sets dialog, for Kratos property sets.

   A soil is what Kratos reads: a constitutive law and its Variables, under Kratos'
   names, in the project's units (server/app/schemas.py). The dialog shows exactly that,
   labels each number in the project's system, edits it in place on App.MATERIALS (the
   contract patches.js saves through), and refuses what the server would refuse.
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

  T.test('the table shows the law and Kratos variables, headed in the project units', function () {
    withDialog(function (host) {
      var heads = Array.prototype.map.call(host.querySelectorAll('.material-sets th'),
                                           function (th) { return th.textContent; });
      T.ok(heads.indexOf('Constitutive law') >= 0, heads.join(' | '));
      T.ok(heads.indexOf('YOUNG_MODULUS [kPa]') >= 0, heads.join(' | '));
      T.ok(heads.indexOf('DENSITY_SOLID [t/m³]') >= 0, heads.join(' | '));
      var row = host.querySelector('.material-sets tbody tr');
      T.ok(/GeoLinearElasticPlaneStrain2DLaw/.test(row.textContent), row.textContent);
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

  T.test('the law is the user\'s to type', function () {
    withDialog(function (host) {
      openProperties(host);
      var law = host.querySelector('[data-field="constitutive_law"]');
      type(law, 'SmallStrainUDSM2DPlaneStrainLaw');
      T.eq(App.MATERIALS[0].constitutive_law, 'SmallStrainUDSM2DPlaneStrainLaw');
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
