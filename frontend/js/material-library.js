/* Built-in starting values: Kratos property sets, stated in SI and added to a project in
   its own unit system (App.Units). Project edits never alter this catalogue.

   The soils are the frozen demo's six (js/data.js), converted the way every project in
   the old kN/m3-kN/m2-m/day shape is (core/model/migration.py): DENSITY_SOLID is the unit
   weight over g, PERMEABILITY_XX the m/day value per second. POROSITY is 0, as in
   Kratos' staged-excavation reference, so each soil weighs exactly DENSITY_SOLID g -- its unit weight -- above
   and below the water alike (add a porosity and a RETENTION_LAW to tell the two apart).
   What a preset leaves out -- the water's density, the fluid constants -- the export
   derives, and says so.
   The interface presets belong to a soil set: they are its Rinter and permeability. */
App.MaterialLibrary = (function () {
  var soils = [
    { id: 'm1', name: 'Fill', color: '#d8c48a', rInter: 0.70, interfacePerm: 'Neutral',
      variables: { GEO_DRAINAGE_TYPE: 'CONSTANT_PW_FIELD', YOUNG_MODULUS: 1.5e7,
                   POISSON_RATIO: 0.30, DENSITY_SOLID: 17000 / 9.81,
                   PERMEABILITY_XX: 1.0 / 86400, POROSITY: 0.0, GEO_COHESION: 1000, GEO_FRICTION_ANGLE: 30.0 } },
    { id: 'm2', name: 'Sand, loose', color: '#c4a86a', rInter: 0.70, interfacePerm: 'Neutral',
      variables: { GEO_DRAINAGE_TYPE: 'CONSTANT_PW_FIELD', YOUNG_MODULUS: 2.5e7,
                   POISSON_RATIO: 0.28, DENSITY_SOLID: 18000 / 9.81,
                   PERMEABILITY_XX: 1.5 / 86400, POROSITY: 0.0, GEO_COHESION: 500, GEO_FRICTION_ANGLE: 32.0 } },
    { id: 'm3', name: 'Clay, soft', color: '#8fa86b', rInter: 0.50, interfacePerm: 'Impermeable',
      variables: { GEO_DRAINAGE_TYPE: 'FULLY_COUPLED', YOUNG_MODULUS: 4.0e6,
                   POISSON_RATIO: 0.35, DENSITY_SOLID: 15000 / 9.81,
                   PERMEABILITY_XX: 0.0001 / 86400, POROSITY: 0.0, GEO_COHESION: 5000, GEO_FRICTION_ANGLE: 22.0 } },
    { id: 'm4', name: 'Clay, stiff', color: '#6f8fa8', rInter: 0.55, interfacePerm: 'Impermeable',
      variables: { GEO_DRAINAGE_TYPE: 'FULLY_COUPLED', YOUNG_MODULUS: 1.2e7,
                   POISSON_RATIO: 0.33, DENSITY_SOLID: 17500 / 9.81,
                   PERMEABILITY_XX: 0.0005 / 86400, POROSITY: 0.0, GEO_COHESION: 15000, GEO_FRICTION_ANGLE: 25.0 } },
    { id: 'm5', name: 'Sand, dense', color: '#b08a6a', rInter: 0.75, interfacePerm: 'Neutral',
      variables: { GEO_DRAINAGE_TYPE: 'CONSTANT_PW_FIELD', YOUNG_MODULUS: 4.5e7,
                   POISSON_RATIO: 0.25, DENSITY_SOLID: 19000 / 9.81,
                   PERMEABILITY_XX: 5.0 / 86400, POROSITY: 0.0, GEO_COHESION: 0, GEO_FRICTION_ANGLE: 36.0 } },
    { id: 'm6', name: 'Bedrock', color: '#8d8d99', rInter: 1.00, interfacePerm: 'Impermeable',
      variables: { GEO_DRAINAGE_TYPE: 'CONSTANT_PW_FIELD', YOUNG_MODULUS: 2.0e9,
                   POISSON_RATIO: 0.20, DENSITY_SOLID: 24000 / 9.81, PERMEABILITY_XX: 0.0 , POROSITY: 0.0} }
  ];
  var interfaces = [
    { id: 'rough', name: 'Rough contact', rInter: 1.0, interfacePerm: 'Neutral' },
    { id: 'reduced', name: 'Reduced-strength contact', rInter: 0.7, interfacePerm: 'Neutral' },
    { id: 'sealed', name: 'Sealed contact', rInter: 0.5, interfacePerm: 'Impermeable' },
    { id: 'draining', name: 'Draining contact', rInter: 0.7, interfacePerm: 'Drain' }
  ];
  function copy(value) { return JSON.parse(JSON.stringify(value)); }
  function find(items, id) {
    var preset = items.filter(function (item) { return item.id === id; })[0];
    if (!preset) throw new Error('Unknown material library preset: ' + id);
    return preset;
  }
  function dimension() { return App.PROJECT && App.PROJECT.dimension === 3 ? 3 : 2; }

  /* A preset as a project material: the law of the project's dimension, and the
     variables in the project's unit system. */
  function asMaterial(preset) {
    return { id: preset.id, name: preset.name, color: preset.color,
             constitutive_law: App.PropertySets.lawFor('soil', dimension()),
             variables: App.Units.convertVariables(preset.variables, 'SI', App.Units.current()),
             tables: {}, rInter: preset.rInter, interfacePerm: preset.interfacePerm };
  }

  function addSoil(id) {
    var material = asMaterial(copy(find(soils, id)));
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
  function applyInterface(material, id) {
    var preset = find(interfaces, id);
    if (!material) throw new Error('Select a material set first.');
    material.rInter = preset.rInter;
    material.interfacePerm = preset.interfacePerm;
  }
  return { soils: function () { return copy(soils); },
    interfaces: function () { return copy(interfaces); },
    asMaterial: asMaterial, addSoil: addSoil, applyInterface: applyInterface };
})();
