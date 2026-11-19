/* Built-in starting values: Kratos property sets, stated in SI and added to a project in
   its own unit system (App.Units). Project edits never alter this catalogue.

   The soils are the default soils of D-Stability and D-Settlement made into Kratos
   property sets (core/model/drafts.py `LIBRARY` says where each number comes from, and
   tests/test_draft_parity.py holds the two copies equal). DENSITY_SOLID is the unit
   weight over g, PERMEABILITY_XX the intrinsic permeability of the m/day conductivity.
   POROSITY is 0, as in Kratos' staged-excavation reference, so each soil weighs exactly
   DENSITY_SOLID g -- its unit weight -- above and below the water alike. Each soil is a
   Mohr-Coulomb one but Bedrock; added as the other model, a soil drops what that model
   does not read and takes its defaults for what it lacks. The water is the project's. */
App.MaterialLibrary = (function () {
  /* The intrinsic permeability, m2, of a soil that conducts water at 1 m/day. */
  var PER_M_PER_DAY = App.SOIL_MODEL_TABLE.constants.PERMEABILITY;
  /* Every soil's Poisson's ratio: a guess, so one value for all. */
  var POISSON_RATIO = 0.3;
  /* m/day: this permeable or less is FULLY_COUPLED with an impermeable interface. */
  var COUPLED_UP_TO = 0.1;

  /* A Mohr-Coulomb soil from its engineering numbers: unit weight in kN/m3, E and c' in
     Pa, phi' in degrees, k in m/day (drafts.py `_library_soil`). */
  function soil(id, name, color, weight, young, cohesion, friction, conductivity) {
    var coupled = conductivity <= COUPLED_UP_TO;
    return { id: id, model: 'mohr_coulomb', name: name, color: color,
             rInter: coupled ? 0.5 : 0.67, interfacePerm: coupled ? 'Impermeable' : 'Neutral',
             variables: { GEO_DRAINAGE_TYPE: coupled ? 'FULLY_COUPLED' : 'CONSTANT_PW_FIELD',
                          YOUNG_MODULUS: young, POISSON_RATIO: POISSON_RATIO,
                          DENSITY_SOLID: weight * 1000 / 9.81,
                          PERMEABILITY_XX: conductivity * PER_M_PER_DAY, POROSITY: 0.0,
                          GEO_COHESION: cohesion, GEO_FRICTION_ANGLE: friction } };
  }

  var soils = [
    //   id                     name                    colour     γ   E       c'    φ'  k
    soil('embankment',          'Embankment',           '#c9b27c', 18, 1.4e7, 7000, 30, 0.01),
    soil('clay_shallow',        'Clay, shallow',        '#8fa86b', 15, 2.9e6, 5000, 18, 0.01),
    soil('clay_deep',           'Clay, deep',           '#6f8f5a', 16, 1.4e7, 7000, 18, 0.01),
    soil('organic_clay',        'Organic clay',         '#7f8a6a', 14, 1.4e6, 5000, 15, 0.01),
    soil('peat_shallow',        'Peat, shallow',        '#8b6a4f', 11, 2.9e5, 5000, 15, 0.01),
    soil('peat_deep',           'Peat, deep',           '#6e5240', 11, 2.9e5, 5000, 15, 0.01),
    soil('clay_with_silt',      'Clay with silt',       '#a3b48a', 18, 1.4e7, 5000, 23, 0.1),
    soil('sand_with_clay',      'Sand with clay',       '#c2b06a', 18, 1.4e7, 3000, 28, 1.0),
    soil('sand',                'Sand',                 '#e3cf8b', 20, 3.0e7, 1000, 30, 30),
    soil('sand_permeable',      'Sand, permeable',      '#d6a84e', 19, 3.0e7, 1000, 30, 45),
    soil('sand_less_permeable', 'Sand, less permeable', '#bfb48e', 20, 3.0e7, 1000, 30, 15),
    { id: 'bedrock', model: 'linear_elastic', name: 'Bedrock', color: '#8d8d99', rInter: 1.0,
      interfacePerm: 'Impermeable',
      variables: { GEO_DRAINAGE_TYPE: 'CONSTANT_PW_FIELD', YOUNG_MODULUS: 2.0e9,
                   POISSON_RATIO: POISSON_RATIO, DENSITY_SOLID: 24 * 1000 / 9.81,
                   PERMEABILITY_XX: 0.0, POROSITY: 0.0 } }
  ];
  function copy(value) { return JSON.parse(JSON.stringify(value)); }
  function find(id) {
    var preset = soils.filter(function (item) { return item.id === id; })[0];
    if (!preset) throw new Error('Unknown material library preset: ' + id);
    return preset;
  }
  function dimension() { return App.PROJECT && App.PROJECT.dimension === 3 ? 3 : 2; }

  /* A preset as a project material of `model` (its own when not given): that model's law
     in the project's dimension, without what the model does not read, that model's
     defaults for what the preset does not give, and the variables in the project's unit
     system. What `model` filled in that the preset's own model would not have -- a
     bedrock made Mohr-Coulomb its strength -- is said in `notes`, as `kratos-cli material
     add --preset ... --model ...` says it (drafts.py `soil`). */
  function asMaterial(preset, model, notes) {
    model = model || preset.model;
    var flow = !!(App.Stages && App.PROJECT && App.Stages.groundwaterFlow(App.PROJECT));
    var law = App.SoilModels.law(model, dimension());
    var variables = copy(preset.variables);
    App.SoilModels.unread(law, variables).forEach(function (name) { delete variables[name]; });
    var filled = App.SoilModels.fill(null, {}, law, variables, 'SI', [], flow);
    var own = App.SoilModels.fill(null, {}, App.SoilModels.law(preset.model, dimension()),
                                  copy(preset.variables), 'SI', [], flow);
    var note = App.SoilModels.filledNote(model, filled.filter(function (name) {
      return own.indexOf(name) < 0;
    }));
    if (note && notes) notes.push(note);
    return { id: preset.id, name: preset.name, color: preset.color, constitutive_law: law,
             variables: App.Units.convertVariables(variables, 'SI', App.Units.current()),
             tables: {}, rInter: preset.rInter, interfacePerm: preset.interfacePerm };
  }

  /* The preset `id` as a material of `model`, not in the project: what the material
     window's library Properties… shows (`kratos-cli material presets ID`). */
  function preview(id, model, notes) {
    return asMaterial(copy(find(id)), model, notes);
  }

  /* The preset `id` added to the project as `model` (its own when not given). */
  function addSoil(id, model, notes) {
    return add(preview(id, model, notes));
  }

  /* A library material -- `preview`'s, as the user left it -- added to the project: a
     fresh id and name, and its own colour while no soil has it, another free one
     otherwise (App.SoilModels.freshColor, as `kratos-cli material add --preset` gives
     one). */
  function add(material) {
    material.color = App.SoilModels.freshColor(
      App.MATERIALS.map(function (m) { return m.color; }), material.color);
    var n = 1;
    while (App.MATERIALS.some(function (m) { return m.id === 'ml' + n; })) n++;
    material.id = 'ml' + n;
    var base = material.name;
    n = 2;
    while (App.MATERIALS.some(function (m) { return m.name === material.name; })) {
      material.name = base + ' (' + n++ + ')';
    }
    App.MATERIALS.push(material);
    return material;
  }
  return { soils: function () { return copy(soils); }, asMaterial: asMaterial,
           preview: preview, add: add, addSoil: addSoil };
})();
