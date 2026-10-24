/* js/data.js (frozen) seeds App.LAYERS in the mockup's shape. The live app never draws
   that seed: js/model.js `apply` replaces it before the first draw. But a suite that puts
   back the layers it found would put the mockup's shape back, and the next rebuild of the
   Model explorer could not read it. So the test page starts from the seed project's
   layers as the server holds them (core/model/templates.py): one top and one bottom each. */
App.LAYERS = [
  { id: 'L1', name: 'Soil_1', mat: 'm2', top: 0, bottom: -8 },
  { id: 'L2', name: 'Soil_2', mat: 'm4', top: -8, bottom: -25 }
];
