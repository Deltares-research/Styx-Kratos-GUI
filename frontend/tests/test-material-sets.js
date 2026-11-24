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
    var saved = { materials: App.MATERIALS, layers: App.LAYERS, project: App.PROJECT,
                  fluid: App.FLUID };
    var host = document.createElement('div'); host.id = 'modal-layer'; document.body.appendChild(host);
    var tree = document.createElement('div'); tree.id = 'tree-model'; document.body.appendChild(tree);
    App.MATERIALS = [sand()]; App.LAYERS = [];
    App.FLUID = { specific_weight: null, bulk_modulus: null, dynamic_viscosity: null };
    App.PROJECT = Object.assign({}, App.PROJECT || {}, { unit_system: 'kN', dimension: 2 });
    try {
      App.MaterialSets.open();
      return run(host);
    } finally {
      Array.prototype.slice.call(host.querySelectorAll('.dlg-x')).reverse().forEach(function (x) { x.click(); });
      host.remove(); tree.remove();
      App.MATERIALS = saved.materials; App.LAYERS = saved.layers; App.PROJECT = saved.project;
      App.FLUID = saved.fluid;
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

  T.test('selecting a material and editing its identification, colour and interface defaults persists', function () {
    withDialog(function (host) {
      host.querySelector('.material-sets tbody tr').click();
      openProperties(host);
      type(field(host, 'name'), '  Dense sand  ');
      T.eq(App.MATERIALS[0].name, 'Dense sand');
      var name = field(host, 'name');
      var enter = new KeyboardEvent('keydown', { key: 'Enter', cancelable: true });
      name.dispatchEvent(enter);
      T.ok(enter.defaultPrevented);
      var colour = field(host, 'color');
      colour.value = '#123456';
      colour.dispatchEvent(new Event('input'));
      T.eq(App.MATERIALS[0].color, '#123456');
      choose(field(host, 'soil-model'), 'mohr_coulomb');
      type(field(host, 'rInter'), '0.85');
      choose(field(host, 'interfacePerm'), 'Drain');
      T.eq([App.MATERIALS[0].rInter, App.MATERIALS[0].interfacePerm], [0.85, 'Drain']);
      type(field(host, 'rInter'), '2');
      T.eq(App.MATERIALS[0].rInter, 0.85, 'invalid interface strength is not committed');
      T.ok(/Rinter/.test(hint(host).textContent));
    });
  });

  T.test('the remove-variable button drops an optional variable but preserves required ones', function () {
    withDialog(function (host) {
      openProperties(host);
      host.querySelector('[data-remove="DENSITY_SOLID"]').click();
      T.eq(App.MATERIALS[0].variables.DENSITY_SOLID, 1.83486);
      T.ok(/DENSITY_SOLID/.test(hint(host).textContent));
      choose(field(host, 'soil-model'), 'other');
      type(field(host, 'constitutive_law'), 'SmallStrainUDSM2DPlaneStrainLaw');
      host.querySelector('[data-field="new-variable"]').value = 'OCR';
      host.querySelector('[data-field="new-value"]').value = '1.5';
      host.querySelector('[data-action="add-variable"]').click();
      T.eq(App.MATERIALS[0].variables.OCR, 1.5);
      host.querySelector('[data-remove="OCR"]').click();
      T.ok(!Object.prototype.hasOwnProperty.call(App.MATERIALS[0].variables, 'OCR'));
    });
  });

  T.test('the table shows the colour, the name, the soil model and the Properties button', function () {
    withDialog(function (host) {
      var heads = Array.prototype.map.call(host.querySelectorAll('.material-sets th'),
                                           function (th) { return th.textContent; });
      T.eq(heads, ['Colour', 'Name', 'Soil model', 'Properties']);
      var row = host.querySelector('.material-sets tbody tr');
      var m = App.MATERIALS[0];
      T.eq(row.children.length, 4);
      T.ok(row.children[0].querySelector('.material-swatch'), 'the colour swatch');
      T.eq(row.children[1].textContent, m.name);
      T.eq(row.children[2].textContent, App.SoilModels.label(App.SoilModels.modelOf(m.constitutive_law)));
      T.eq(row.children[2].title, m.constitutive_law, 'the law on hover');
      T.ok(row.children[3].querySelector('[data-action="material-properties"]'), 'the Properties button');
    });
  });

  T.test('the soil model column names a law of no model by its own name', function () {
    withDialog(function (host) {
      App.MATERIALS[0].constitutive_law = 'MyOwnLaw2D';
      host.querySelector('.material-sets tbody tr').click();  // a click redraws the rows
      T.eq(host.querySelector('.material-sets [data-column="soil-model"]').textContent, 'MyOwnLaw2D');
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
      T.ok(!('K0_NC' in App.MATERIALS[0].variables));
      T.eq(variableInput(host, 'K0_NC').placeholder, '0.388889 (derived)', 'what it derives, shown');
    });
  });

  T.test('porosity is the soil\'s: nothing derives it, and it is not blanked', function () {
    withDialog(function (host) {
      openProperties(host);
      type(variableInput(host, 'POROSITY'), '');
      T.eq(App.MATERIALS[0].variables.POROSITY, 0.3);
      host.querySelector('[data-action="create-soil"]').click();
      T.eq(variableInput(host, 'POROSITY').placeholder, '', 'no derived value shown');
    });
  });

  T.test('a variable its law needs cannot be blanked', function () {
    withDialog(function (host) {
      openProperties(host);
      type(variableInput(host, 'DENSITY_SOLID'), '');
      T.eq(App.MATERIALS[0].variables.DENSITY_SOLID, 1.83486);
    });
  });

  T.test('a soil model offers no variables to add: it lists what it reads', function () {
    withDialog(function (host) {
      openProperties(host);
      T.ok(!host.querySelector('[data-action="add-variable"]'), 'no Add row');
    });
  });

  T.test('a law of no model takes any other Kratos variable, text and lists too', function () {
    withDialog(function (host) {
      openProperties(host);
      choose(field(host, 'soil-model'), 'other');
      type(field(host, 'constitutive_law'), 'SmallStrainUDSM2DPlaneStrainLaw');
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

  T.test('the law of a soil model is not a field of its own, only named on hover', function () {
    withDialog(function (host) {
      openProperties(host);
      T.eq(field(host, 'soil-model').value, 'linear_elastic');
      T.ok(!field(host, 'constitutive_law'), 'no law row');
      T.eq(field(host, 'soil-model').closest('.pgrid-row').title, 'GeoLinearElasticPlaneStrain2DLaw');
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
      T.ok(titles.indexOf('Strength') >= 0, titles.join(' | '));
      T.ok(titles.indexOf('Flow') < 0, 'a soil that is not coupled has no flow: ' + titles.join(' | '));
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

  T.test('a text value is a drop-down of every value the soil can take', function () {
    withDialog(function (host) {
      openProperties(host);
      var drainage = variableInput(host, 'GEO_DRAINAGE_TYPE');
      T.eq(drainage.tagName, 'SELECT');
      T.eq(Array.prototype.map.call(drainage.options, function (o) { return o.value; }),
           ['CONSTANT_PW_FIELD', 'FULLY_COUPLED'],
           'no DRAINED: Kratos couples it; no UNDRAINED');
      T.eq(Array.prototype.map.call(drainage.options, function (o) { return o.text; }),
           ['Mechanical only', 'Fully coupled']);
      var note = function () {
        return host.querySelector('.material-variables [data-note="GEO_DRAINAGE_TYPE"]').textContent;
      };
      T.eq(note(), 'Solves displacements with prescribed pore pressures');
      choose(drainage, 'FULLY_COUPLED');
      T.eq(App.MATERIALS[0].variables.GEO_DRAINAGE_TYPE, 'FULLY_COUPLED');
      T.eq(note(), 'Solves pore pressures and displacements coupled with a UPw formulation');
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

  T.test('a value the model does not read is kept and named, given no field', function () {
    withDialog(function (host) {
      App.MATERIALS[0].variables.OCR = 1.5;
      App.MATERIALS[0].variables.GEO_COHESION = 2;
      openProperties(host);
      T.ok(!variableInput(host, 'OCR') && !variableInput(host, 'GEO_COHESION'), 'no fields');
      var row = host.querySelector('.material-variables [data-unread]');
      T.ok(/Not read by Linear elastic/.test(row.textContent), row.textContent);
      T.ok(/OCR, GEO_COHESION/.test(row.textContent), row.textContent);
      T.eq(App.MATERIALS[0].variables.OCR, 1.5, 'kept');
      host.querySelector('[data-action="leave-out-unread"]').click();
      T.ok(!('OCR' in App.MATERIALS[0].variables) && !('GEO_COHESION' in App.MATERIALS[0].variables));
      T.ok(!host.querySelector('.material-variables [data-unread]'), 'and the line is gone');
    });
  });

  T.test('a model chosen leaves out what it does not read, and gives it back chosen back', function () {
    withDialog(function (host) {
      openProperties(host);
      choose(field(host, 'soil-model'), 'mohr_coulomb');
      type(variableInput(host, 'GEO_COHESION'), '7');
      choose(field(host, 'soil-model'), 'linear_elastic');
      var m = App.MATERIALS[0];
      T.ok(!('GEO_COHESION' in m.variables) && !('GEO_FRICTION_ANGLE' in m.variables),
           JSON.stringify(m.variables));
      T.ok(!variableInput(host, 'GEO_COHESION'), 'no cohesion field');
      T.ok(!host.querySelector('.material-variables [data-unread]'), 'nothing named as unread');
      T.eq(m.variables.YOUNG_MODULUS, 2.5e4, 'what both read is kept');
      choose(field(host, 'soil-model'), 'mohr_coulomb');
      T.eq(m.variables.GEO_COHESION, 7, 'the typed cohesion, not the default');
    });
  });

  T.test('a linear elastic soil has no Rinter: it has no strength to give a contact', function () {
    withDialog(function (host) {
      openProperties(host);
      T.ok(!field(host, 'rInter'), 'no Rinter');
      var row = field(host, 'no-strength');
      T.ok(row && /Coulomb contact sets its own/.test(row.textContent), row && row.textContent);
      T.ok(/Set on the interface/.test(row.title), row.title);
      choose(field(host, 'soil-model'), 'mohr_coulomb');
      T.ok(field(host, 'rInter'), 'a Mohr-Coulomb soil has one');
      T.ok(!field(host, 'no-strength'));
    });
  });

  function titles(host) {
    return Array.prototype.map.call(host.querySelectorAll('.material-variables h4'),
                                    function (h) { return h.textContent; });
  }

  function key(host, name) {
    return variableInput(host, name).closest('.pgrid-row').querySelector('.pgrid-key');
  }

  function unit(host, name) {
    return variableInput(host, name).parentNode.querySelector('.unit').textContent;
  }

  T.test('a linear elastic soil shows no cohesion or friction angle', function () {
    withDialog(function (host) {
      openProperties(host);
      T.ok(!variableInput(host, 'GEO_COHESION') && !variableInput(host, 'GEO_FRICTION_ANGLE'));
      T.ok(titles(host).indexOf('Strength') < 0, titles(host).join(' | '));
    });
  });

  T.test('each value is named for a reader, its Kratos name on hover, its unit beside it', function () {
    withDialog(function (host) {
      openProperties(host);
      T.eq(key(host, 'YOUNG_MODULUS').textContent, 'Young\'s modulus');
      T.eq(key(host, 'YOUNG_MODULUS').title, 'YOUNG_MODULUS');
      T.eq(unit(host, 'YOUNG_MODULUS'), 'kPa');
      T.eq(unit(host, 'DENSITY_SOLID'), 't/m³');
      T.eq(unit(host, 'POROSITY'), '', 'a pure number has the slot, empty');
    });
  });

  T.test('the flow parameters come with a coupled soil, as intrinsic and Darcy permeabilities', function () {
    withDialog(function (host) {
      openProperties(host);
      T.ok(!variableInput(host, 'PERMEABILITY_XX'), 'not for a drained soil');
      choose(variableInput(host, 'GEO_DRAINAGE_TYPE'), 'FULLY_COUPLED');
      var kappa = App.MATERIALS[0].variables.PERMEABILITY_XX;
      T.near(kappa, 1.1574e-12, 1e-15, 'a metre a day, intrinsic');
      T.eq(key(host, 'PERMEABILITY_XX').textContent, 'Intrinsic permeability xx');
      T.eq(unit(host, 'PERMEABILITY_XX'), 'm²');
      T.ok(/1\.15741e-12 \(derived\)/.test(variableInput(host, 'PERMEABILITY_YY').placeholder),
           'yy is xx: ' + variableInput(host, 'PERMEABILITY_YY').placeholder);
      var darcy = host.querySelector('[data-computed="HYDRAULIC_CONDUCTIVITY_XX"]');
      T.ok(darcy, 'the Darcy permeability is shown');
      T.ok(/m\/s= 1 m\/day$/.test(darcy.textContent), darcy.textContent);
    });
  });

  T.test('the unit weights dry and saturated follow from the density and the porosity', function () {
    withDialog(function (host) {
      openProperties(host);
      var dry = host.querySelector('[data-computed="UNIT_WEIGHT_DRY"]');
      var wet = host.querySelector('[data-computed="UNIT_WEIGHT_SATURATED"]');
      // 0.7 * 1.83486 t/m3 * 9.81, and 0.3 * 10 kN/m3 on top.
      T.ok(/^Unit weight, dry12\.6\d*kN\/m³$/.test(dry.textContent), dry.textContent);
      T.ok(/^Unit weight, saturated15\.6\d*kN\/m³$/.test(wet.textContent), wet.textContent);
      type(variableInput(host, 'POROSITY'), '0');
      var solid = host.querySelector('[data-computed="UNIT_WEIGHT_SATURATED"]').textContent;
      T.ok(/saturated18kN/.test(solid), 'no pores, no water: ' + solid);
    });
  });

  T.test('a new soil is saturated below the phreatic level', function () {
    withDialog(function (host) {
      host.querySelector('[data-action="new"]').click();
      T.eq(App.MATERIALS[1].variables.RETENTION_LAW, 'SaturatedBelowPhreaticLevelLaw');
    });
  });

  T.test('the water is the project\'s, edited once for every soil', function () {
    withDialog(function (host) {
      var bulk = host.querySelector('[data-water="bulk_modulus"]');
      T.ok(/2\.2e6/.test(bulk.placeholder), 'water\'s, in kPa: ' + bulk.placeholder);
      type(bulk, '2e6');
      T.eq(App.FLUID.bulk_modulus, 2e6);
      type(bulk, '-1');
      T.eq(App.FLUID.bulk_modulus, 2e6, 'a negative modulus is refused');
      type(bulk, '');
      T.eq(App.FLUID.bulk_modulus, null, 'blank is water\'s own');
      openProperties(host);
      ['DENSITY_WATER', 'BULK_MODULUS_FLUID', 'DYNAMIC_VISCOSITY'].forEach(function (name) {
        T.ok(!variableInput(host, name), name + ' is not a soil\'s');
      });
    });
  });

  T.test('the water\'s unit weight is edited with its other properties', function () {
    withDialog(function (host) {
      var weight = host.querySelector('[data-water="specific_weight"]');
      T.eq(weight.tagName, 'INPUT', 'editable, not shown read-only');
      T.ok(/^10 /.test(weight.placeholder), 'water\'s 10 kN/m3: ' + weight.placeholder);
      type(weight, '9.81');
      T.eq(App.FLUID.specific_weight, 9.81);
      type(weight, '0');
      T.eq(App.FLUID.specific_weight, 9.81, 'zero is refused');
      openProperties(host);
      // 0.7 * 1.83486 t/m3 * 9.81 dry, and 0.3 * 9.81 kN/m3 of water on top.
      var wet = host.querySelector('[data-computed="UNIT_WEIGHT_SATURATED"]').textContent;
      T.ok(/saturated15\.5\d*kN/.test(wet), 'the soils weigh the water\'s weight: ' + wet);
    });
  });

  T.test('Water properties edits the same water, and Cancel puts it back', function () {
    withDialog(function (host) {
      App.MaterialSets.openWater();
      var dialogs = host.querySelectorAll('.dialog');
      var dialog = dialogs[dialogs.length - 1];
      T.eq(dialog.querySelector('.dlg-title').textContent, 'Water properties');
      ['specific_weight', 'bulk_modulus', 'dynamic_viscosity'].forEach(function (name) {
        T.ok(dialog.querySelector('input[data-water="' + name + '"]'), name);
      });
      type(dialog.querySelector('[data-water="specific_weight"]'), '9.5');
      T.eq(App.FLUID.specific_weight, 9.5);
      Array.prototype.filter.call(dialog.querySelectorAll('.dlg-foot .btn'), function (b) {
        return b.textContent === 'Cancel';
      })[0].click();
      T.eq(App.FLUID.specific_weight, null, 'cancelled: the water as it was');
    });
  });

  T.test('Create soil makes a blank drained linear elastic soil and opens it', function () {
    withDialog(function (host) {
      host.querySelector('[data-action="create-soil"]').click();
      var m = App.MATERIALS[1];
      T.ok(m.id !== App.MATERIALS[0].id);
      T.eq(m.constitutive_law, 'GeoLinearElasticPlaneStrain2DLaw');
      T.eq(m.variables.GEO_DRAINAGE_TYPE, 'CONSTANT_PW_FIELD');
      T.eq(m.variables.RETENTION_LAW, 'SaturatedBelowPhreaticLevelLaw');
      ['YOUNG_MODULUS', 'POISSON_RATIO', 'DENSITY_SOLID', 'POROSITY', 'K0_NC'].forEach(function (name) {
        T.ok(!(name in m.variables), name + ' is left blank');
      });
      T.ok(variableInput(host, 'YOUNG_MODULUS'), 'its properties are open');
      T.eq(variableInput(host, 'YOUNG_MODULUS').value, '');
      T.ok(/Still to fill in.*Young's modulus.*Poisson's ratio/.test(hint(host).textContent),
           hint(host).textContent);
      T.ok(/needs YOUNG_MODULUS/.test(App.PropertySets.validate('soil', m)), 'not ready to calculate');
      T.eq(App.PropertySets.validate('soil', m, true), null, 'but valid as far as it goes');
    });
  });

  T.test('the toolbar\'s new soil is the same blank soil', function () {
    withDialog(function (host) {
      host.querySelector('[data-action="new"]').click();
      T.eq(App.MATERIALS[1].variables.GEO_DRAINAGE_TYPE, 'CONSTANT_PW_FIELD');
      T.ok(!('YOUNG_MODULUS' in App.MATERIALS[1].variables));
    });
  });

  T.test('every soil added, new or duplicated, gets a colour no other soil has', function () {
    withDialog(function () {
      for (var i = 0; i < 20; i++) App.addMaterial();
      App.duplicateMaterial(App.MATERIALS[0]);
      var colours = App.MATERIALS.map(function (m) { return m.color.toLowerCase(); });
      colours.forEach(function (c, i) {
        T.ok(/^#[0-9a-f]{6}$/.test(c), c + ' is a colour the picker takes');
        T.eq(colours.indexOf(c), i, c + ' is not repeated');
      });
    });
  });

  T.test('a blank soil is filled in one value at a time, and K0 follows from it', function () {
    withDialog(function (host) {
      host.querySelector('[data-action="create-soil"]').click();
      var m = App.MATERIALS[1];
      T.eq(variableInput(host, 'K0_NC').placeholder, 'derived', 'nothing to derive it from yet');
      type(variableInput(host, 'YOUNG_MODULUS'), '20000');
      T.eq(m.variables.YOUNG_MODULUS, 20000, 'kept with the Poisson ratio still blank');
      type(variableInput(host, 'POISSON_RATIO'), '0.25');
      T.eq(m.variables.POISSON_RATIO, 0.25);
      T.eq(variableInput(host, 'K0_NC').placeholder, '0.333333 (derived)', 'nu / (1 - nu)');
      T.eq(hint(host).textContent,
           'Still to fill in before a calculation: Density of the solid, Porosity.');
      type(variableInput(host, 'POISSON_RATIO'), '0.6');
      T.eq(m.variables.POISSON_RATIO, 0.25, 'an invalid value is still refused');
      T.ok(/POISSON_RATIO/.test(hint(host).textContent), hint(host).textContent);
    });
  });

  T.test('a Mohr-Coulomb soil turns on linear hardening and gets its three slopes', function () {
    withDialog(function (host) {
      openProperties(host);
      var m = App.MATERIALS[0];
      choose(field(host, 'soil-model'), 'mohr_coulomb');
      var hardening = variableInput(host, 'GEO_COULOMB_HARDENING_TYPE');
      T.eq(hardening.value, 'None', 'off unless asked for');
      T.ok(!('GEO_COULOMB_HARDENING_TYPE' in m.variables), 'and not written');
      T.ok(!variableInput(host, 'GEO_COHESION_FUNCTION_COEFFICIENTS'));
      choose(hardening, 'Linear');
      T.eq(m.variables.GEO_COULOMB_HARDENING_TYPE, 'Linear');
      ['GEO_COHESION_FUNCTION_COEFFICIENTS', 'GEO_FRICTION_ANGLE_FUNCTION_COEFFICIENTS',
       'GEO_DILATANCY_ANGLE_FUNCTION_COEFFICIENTS'].forEach(function (name) {
        T.ok(variableInput(host, name), name + ' is listed');
        T.eq(m.variables[name], 0, name + ' starts flat');
      });
      type(variableInput(host, 'GEO_COHESION_FUNCTION_COEFFICIENTS'), '50000');
      T.eq(m.variables.GEO_COHESION_FUNCTION_COEFFICIENTS, 50000);
      type(variableInput(host, 'GEO_FRICTION_ANGLE_FUNCTION_COEFFICIENTS'), '-0.1');
      T.eq(m.variables.GEO_FRICTION_ANGLE_FUNCTION_COEFFICIENTS, 0, 'a softening slope is refused');
      T.ok(/cannot be negative/.test(hint(host).textContent), hint(host).textContent);
    });
  });

  T.test('a blank soil made Mohr-Coulomb gets no invented strength; K0 follows phi', function () {
    withDialog(function (host) {
      host.querySelector('[data-action="create-soil"]').click();
      var m = App.MATERIALS[1];
      choose(field(host, 'soil-model'), 'mohr_coulomb');
      T.eq(m.constitutive_law, 'GeoMohrCoulombLawPlaneStrain');
      ['YOUNG_MODULUS', 'POISSON_RATIO', 'DENSITY_SOLID', 'POROSITY', 'GEO_COHESION',
       'GEO_FRICTION_ANGLE', 'GEO_DILATANCY_ANGLE'].forEach(function (name) {
        T.ok(!(name in m.variables), name + ' is still the user\'s to type');
      });
      T.eq(m.variables.GEO_DRAINAGE_TYPE, 'CONSTANT_PW_FIELD');
      type(variableInput(host, 'GEO_FRICTION_ANGLE'), '30');
      T.eq(m.variables.GEO_FRICTION_ANGLE, 30);
      T.eq(variableInput(host, 'K0_NC').placeholder, '0.5 (derived)', '1 - sin(phi)');
    });
  });

  T.test('a complete soil made Mohr-Coulomb still gets the model\'s defaults', function () {
    withDialog(function (host) {
      openProperties(host);
      choose(field(host, 'soil-model'), 'mohr_coulomb');
      T.eq(App.MATERIALS[0].variables.GEO_FRICTION_ANGLE, 30);
    });
  });

  T.test('the default soil material library is always shown, below the soils', function () {
    withDialog(function (host) {
      var library = host.querySelector('.material-library');
      T.ok(library && library.tagName !== 'DETAILS', 'not collapsible');
      T.eq(library.querySelector('h3').textContent, 'Default soil material library');
      T.ok(host.querySelector('.material-sets').compareDocumentPosition(library) &
           Node.DOCUMENT_POSITION_FOLLOWING, 'after the soils table');
      T.ok(host.querySelector('[data-action="create-soil"]').compareDocumentPosition(library) &
           Node.DOCUMENT_POSITION_FOLLOWING, 'Create soil comes first');
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
