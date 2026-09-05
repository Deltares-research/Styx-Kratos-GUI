/* Built-in starting values in m / kN / day. Project edits never alter this catalog.
   Soil presets retain the demo's existing values; interfaces belong to a soil set. */
App.MaterialLibrary = (function () {
  var soils = [
  { id:'m1', name:'Fill',          model:'Mohr-Coulomb',  type:'Drained',   color:'#d8c48a',
    gUnsat:17.0, gSat:20.0, E:15000,  nu:0.30, c:1.0,  phi:30.0, k:1.0,
    rInter:0.70, interfacePerm:'Neutral' },
  { id:'m2', name:'Sand, loose',   model:'Hardening Soil',type:'Drained',   color:'#c4a86a',
    gUnsat:18.0, gSat:20.5, E:25000,  nu:0.28, c:0.5,  phi:32.0, k:1.5,
    rInter:0.70, interfacePerm:'Neutral' },
  { id:'m3', name:'Clay, soft',    model:'Soft Soil',     type:'Undrained (A)', color:'#8fa86b',
    gUnsat:15.0, gSat:16.0, E:4000,   nu:0.35, c:5.0,  phi:22.0, k:0.0001,
    rInter:0.50, interfacePerm:'Impermeable' },
  { id:'m4', name:'Clay, stiff',   model:'Mohr-Coulomb',  type:'Undrained (A)', color:'#6f8fa8',
    gUnsat:17.5, gSat:18.5, E:12000,  nu:0.33, c:15.0, phi:25.0, k:0.0005,
    rInter:0.55, interfacePerm:'Impermeable' },
  { id:'m5', name:'Sand, dense',   model:'Hardening Soil',type:'Drained',   color:'#b08a6a',
    gUnsat:19.0, gSat:21.0, E:45000,  nu:0.25, c:0.0,  phi:36.0, k:5.0,
    rInter:0.75, interfacePerm:'Neutral' },
  { id:'m6', name:'Bedrock',       model:'Linear Elastic',type:'Non-porous',color:'#8d8d99',
    gUnsat:24.0, gSat:24.0, E:2.0e6,  nu:0.20, c:null, phi:null, k:0.0,
    rInter:1.00, interfacePerm:'Impermeable' }
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
  function addSoil(id) {
    var material = copy(find(soils, id));
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
    addSoil: addSoil, applyInterface: applyInterface };
})();
