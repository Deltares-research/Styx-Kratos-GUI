(function () {
  test('mesh settings map the project to the complete gmsh request controls', function () {
    var settings = App.MeshSettings.fromProject({ mesh: {
      element_size: 2.5, order: 2, algorithm_3d: 'hxt', optimization: 'netgen',
      smoothing: 7, curvature_points: 20, size_min_factor: 0.1,
      second_order_linear: false
    }});
    T.eq(settings.algorithm_3d, 'hxt');
    T.eq(settings.optimization, 'netgen');
    T.eq(settings.smoothing, 7);
    T.eq(settings.second_order_linear, false);
  });

  test('mesh settings validation rejects unsafe values before an API call', function () {
    var valid = App.MeshSettings.fromProject({ mesh: {} });
    T.ok(App.MeshSettings.validate(valid).element_size > 0);
    valid.element_size = 0;
    return T.rejects(function () { return Promise.resolve(App.MeshSettings.validate(valid)); })
      .then(function (error) { T.ok(/element size/i.test(error.message)); });
  });

  test('mesh bodies include material-bearing custom soil but not unassigned geometry', function () {
    var project = {
      layers: [{ id: 'L1', name: 'Upper' }],
      custom_parts: [{ key: 'fill', label: 'Backfill', mat: 'sand' },
                     { key: 'drawing', label: 'Unassigned geometry' }]
    };
    T.eq(App.MeshSettings.bodyControls(project).map(function (row) {
      return { key: row.key, label: row.label };
    }), [{ key: 'soil_L1', label: 'Upper' }, { key: 'fill', label: 'Backfill' }]);
  });

  test('body controls keep independent sizes', function () {
    var rows = App.MeshSettings.bodyControls(
      { layers: [{ id: 'L1', name: 'Upper' }, { id: 'L2', name: 'Lower' }],
        mesh: { element_size: 2.5, body_sizes: { soil_L1: 1.0, soil_L2: 4.0 } } }
    );
    T.eq(rows, [
      { key: 'soil_L1', label: 'Upper', size: 1.0, follows: false },
      { key: 'soil_L2', label: 'Lower', size: 4.0, follows: false }
    ]);
  });

  test('a row with no size of its own shows the global size and follows it', function () {
    var rows = App.MeshSettings.bodyControls(
      { layers: [{ id: 'L1', name: 'Upper' }], mesh: { element_size: 2.5, body_sizes: {} } }
    );
    T.eq(rows, [{ key: 'soil_L1', label: 'Upper', size: 2.5, follows: true }]);
  });

  test('the window keeps a size it has no row for', function () {
    var project = { mesh: { element_size: 5, body_sizes: {
      sheetpile: 0.5, soil_L1__lift3: 1.0, soil_L1: 2.0 } } };
    T.eq(App.MeshSettings.savedBodySizes(project, [{ key: 'soil_L1', size: 3, follows: false }]),
         { sheetpile: 0.5, soil_L1__lift3: 1.0, soil_L1: 3 });
  });

  test('a row that follows the global size adds no size of its own', function () {
    var project = { mesh: { element_size: 5, body_sizes: {} } };
    T.eq(App.MeshSettings.savedBodySizes(project, [{ key: 'soil_L1', size: 5, follows: true }]),
         {});
  });

  test('a typed size is saved even when it equals the global size', function () {
    var project = { mesh: { element_size: 5, body_sizes: {} } };
    T.eq(App.MeshSettings.savedBodySizes(project, [{ key: 'soil_L1', size: 5, follows: false }]),
         { soil_L1: 5 });
  });

  test('a row left empty takes its size away', function () {
    var project = { mesh: { element_size: 5, body_sizes: { soil_L1: 2 } } };
    T.eq(App.MeshSettings.savedBodySizes(project, [{ key: 'soil_L1', size: 0, follows: false }]),
         {});
  });

  /* ── Local mesh sizes ───────────────────────────────────────────────── */

  test('every node part of the deck has a row: structures, anchors, loads, conditions and faces', function () {
    var project = {
      dimension: 2,
      beams: [{ id: 'sheetpile', name: 'Wall' }], anchors: [{ id: 'strut', name: 'Strut' }],
      interfaces: [{ id: 'contact', name: 'Contact' }],
      normal_loads: [{ id: 'water_1', name: 'Water' }], lines: [{ id: 'floor', name: 'Floor' }],
      boundary_conditions: [{ id: 'left', name: 'Left roller', on: 'face', face: 'left' },
                            { id: 'pin', name: 'Pin', on: 'point' }],
      loads: [{ id: 'push', name: 'Push', kind: 'point' }, { id: 'strip', name: 'Strip', kind: 'line' }],
      mesh: { element_size: 5, body_sizes: { sheetpile: 0.5, face_left: 1 },
              size_bands: { sheetpile: 10 } }
    };
    var rows = App.MeshSettings.localControls(project);
    T.eq(rows.map(function (row) { return [row.key, row.size, row.band]; }),
         [['sheetpile', 0.5, 10], ['strut', null, null], ['contact', null, null],
          ['water_1', null, null], ['floor', null, null], ['pin', null, null],
          ['push', null, null], ['strip', null, null], ['face_bottom', null, null],
          ['face_left', 1, null], ['face_right', null, null], ['face_top', null, null]],
         'a section has no front and back face');
    T.eq(rows[9].label, 'Left face  ·  Left roller', 'a face names the conditions on it');
    T.eq(App.MeshSettings.localControls({ mesh: {} }).map(function (row) { return row.key; }),
         ['face_bottom', 'face_left', 'face_right', 'face_front', 'face_back', 'face_top'],
         'a solid model has all six faces');
  });

  test('a condition on a face has the size of the face, one on the whole soil has none', function () {
    var project = { boundary_conditions: [
      { id: 'fixed_bottom', on: 'face', face: 'bottom' }, { id: 'wet', on: 'part', part: 'soil_L1' },
      { id: 'pore', on: 'domain' }, { id: 'pin', on: 'point' }] };
    var of = App.MeshSettings.sizeKeyOf;
    T.eq(of(project, 'fixed_bottom'), 'face_bottom');
    T.eq(of(project, 'wet'), 'soil_L1');
    T.eq(of(project, 'pore'), null);
    T.eq(of(project, 'pin'), 'pin');
    T.eq(of(project, 'surcharge'), 'surcharge', 'anything else has its own');
  });

  test('a size is saved with its band, and a row left empty takes both away', function () {
    var mesh = { body_sizes: { soil_L1: 2, sheetpile: 0.5 }, size_bands: { sheetpile: 10 } };
    T.eq(App.MeshSettings.savedLocalSizes(mesh, [
      { key: 'sheetpile', size: null, band: null }, { key: 'floor', size: 0.25, band: 5 },
      { key: 'pin', size: 1, band: 0 }]),
         { body_sizes: { soil_L1: 2, floor: 0.25, pin: 1 }, size_bands: { floor: 5 } });
  });

  test('a band needs a size, and neither may be negative', function () {
    var problem = App.MeshSettings.localProblem;
    T.eq(problem(1, null), null);
    T.eq(problem(1, 10), null);
    T.eq(problem(null, null), null);
    T.ok(/before a band/.test(problem(null, 5)));
    T.ok(/greater than zero/.test(problem(0, null)));
    T.ok(/negative/.test(problem(1, -1)));
  });

  test("a layer row that follows the global size keeps it as its own when a band is typed", function () {
    var project = { mesh: { body_sizes: {} } };
    T.eq(App.MeshSettings.savedBodySizes(project, [
      { key: 'soil_L1', size: 5, follows: true, band: 10 },
      { key: 'soil_L2', size: 5, follows: true, band: null }]), { soil_L1: 5 });
  });

  test('what can take a size: the layers, their bodies, the objects and the faces', function () {
    var project = { dimension: 2, layers: [{ id: 'L1' }],
                    soil_body_keys: ['soil_L1__pit', 'soil_L1__kept'],
                    beams: [{ id: 'sheetpile' }], lines: [{ id: 'floor' }] };
    T.eq(App.MeshSettings.sizableKeys(project),
         ['soil_L1', 'soil_L1__pit', 'soil_L1__kept', 'sheetpile', 'floor',
          'face_bottom', 'face_left', 'face_right', 'face_top']);
  });

  test('refine halves the size an object is meshed at, coarsen doubles it', function () {
    var project = { mesh: { element_size: 4, body_sizes: { soil_L1: 2, sheetpile: 0.5 } } };
    T.eq(App.MeshSettings.sizeNow(project, 'sheetpile'), 0.5, 'its own');
    T.eq(App.MeshSettings.sizeNow(project, 'soil_L1__pit'), 2, "its layer's");
    T.eq(App.MeshSettings.sizeNow(project, 'floor'), 4, 'the global size');
  });
})();

/* The mesh dialog has to ask for the algorithm that will actually be used: gmsh
   reads Mesh.Algorithm in 2D and Mesh.Algorithm3D in 3D, and offering the wrong
   one lets someone pick a setting that is silently ignored. */

(function () {
  test('both algorithms survive a round trip, so switching dimension keeps each', function () {
    var settings = App.MeshSettings.fromProject({ mesh: {
      algorithm_3d: 'hxt', algorithm_2d: 'delaunay'
    }});
    T.eq(settings.algorithm_3d, 'hxt');
    T.eq(settings.algorithm_2d, 'delaunay');
  });

  test('a project without a 2D algorithm gets the default rather than undefined', function () {
    T.eq(App.MeshSettings.fromProject({ mesh: {} }).algorithm_2d, 'frontal');
  });

  test('validation rejects an unknown 2D algorithm', function () {
    var value = App.MeshSettings.fromProject({ mesh: {} });
    value.algorithm_2d = 'nonsense';
    return T.rejects(function () { return Promise.resolve(App.MeshSettings.validate(value)); })
      .then(function (error) { T.ok(/2D algorithm/i.test(error.message)); });
  });

  /* The dialog renders one algorithm select, not two, so the key for the dimension
     you are *not* in never appears among the form controls. Reading the form alone
     therefore produced a value with that key missing, and validate() rejected it:
     "Unknown 2D algorithm" on applying a 3D dialog, and the mirror image in 2D. The
     stored settings have to be the base the form is laid over. */
  test('the algorithm the dialog did not show survives being applied', function () {
    var project = { dimension: 3, mesh: { algorithm_3d: 'delaunay', algorithm_2d: 'meshadapt' } };
    var typed = { element_size: '2.5', order: '2', algorithm_3d: 'hxt',
                  optimization: 'gmsh', smoothing: '10', curvature_points: '16',
                  size_min_factor: '0.05', second_order_linear: true };
    var merged = App.MeshSettings.merge(project, typed);
    T.eq(merged.algorithm_3d, 'hxt', 'what the user chose wins');
    T.eq(merged.algorithm_2d, 'meshadapt', 'what the dialog never showed is kept');
    // The whole point: this must now survive validation rather than throwing.
    T.eq(App.MeshSettings.validate(merged).algorithm_2d, 'meshadapt');
  });

  test('the same holds in 2D, where the 3D algorithm is the hidden one', function () {
    var project = { dimension: 2, mesh: { algorithm_3d: 'hxt', algorithm_2d: 'frontal' } };
    var merged = App.MeshSettings.merge(project, { algorithm_2d: 'delaunay' });
    T.eq(merged.algorithm_2d, 'delaunay');
    T.eq(merged.algorithm_3d, 'hxt');
    T.eq(App.MeshSettings.validate(merged).algorithm_3d, 'hxt');
  });

  test('a project with no stored mesh block still validates', function () {
    // A fresh project has no mesh settings at all; the defaults have to fill both.
    var merged = App.MeshSettings.merge({ dimension: 3 }, { algorithm_3d: 'frontal' });
    T.eq(App.MeshSettings.validate(merged).algorithm_2d, 'frontal');
  });

  test('the dialog offers the algorithm for the dimension in use', function () {
    T.eq(App.MeshSettings.algorithmRow({ dimension: 2 }).name, 'algorithm_2d');
    T.eq(App.MeshSettings.algorithmRow({ dimension: 3 }).name, 'algorithm_3d');
    T.eq(App.MeshSettings.algorithmRow({}).name, 'algorithm_3d');
    T.ok(App.MeshSettings.algorithmRow({ dimension: 2 }).choices.length >= 2);
  });
})();

/* Clicking the Mesh tab is also how you look at a mesh you already have, so the
   properties dialog only offers itself there while there is nothing to look at.
   It is still one toolbar button away (`meshSettings`) once a mesh exists. */

(function () {
  test('the Mesh tab opens the properties dialog only while there is no mesh', function () {
    T.eq(App.MeshSettings.opensOnModeTab(false), true);
    T.eq(App.MeshSettings.opensOnModeTab(true), false);
  });

  test('after a calculation the Mesh tab shows its mesh instead of the dialog', function () {
    T.eq(App.MeshSettings.opensOnModeTab(false, true), false);
    T.eq(App.MeshSettings.meshesOnModeTab(false, true), true);
    // A mesh on screen is shown as it is, calculated or not.
    T.eq(App.MeshSettings.meshesOnModeTab(true, true), false);
    T.eq(App.MeshSettings.meshesOnModeTab(false, false), false);
  });

  test('a stage, a material or the name does not change what the mesh is made of', function () {
    var settings = { element_size: 2 };
    var project = { name: 'a', stages: [], materials: [], layers: [{ id: 'clay' }] };
    var key = App.MeshSettings.meshKey(project, settings);
    var edited = Object.assign({}, project, {
      name: 'b', stages: [{ id: 's1' }], materials: [{ id: 'm1' }],
      fluid: { density: 1 }, gravity_acceleration: 9.8
    });
    T.eq(App.MeshSettings.meshKey(edited, settings), key);
  });

  test('the geometry and the mesh settings do change what the mesh is made of', function () {
    var settings = { element_size: 2 };
    var project = { name: 'a', layers: [{ id: 'clay' }] };
    var key = App.MeshSettings.meshKey(project, settings);
    T.ok(App.MeshSettings.meshKey({ name: 'a', layers: [{ id: 'sand' }] }, settings) !== key);
    T.ok(App.MeshSettings.meshKey(project, { element_size: 1 }) !== key);
  });

  test('the properties dialog does not name the mesher', function () {
    T.ok(!/gmsh/i.test(App.MeshSettings.TITLE), App.MeshSettings.TITLE);
    App.MeshSettings.optimizationChoices().forEach(function (choice) {
      T.ok(!/gmsh/i.test(choice[1]), choice[1]);
    });
    [true, false].forEach(function (planar) {
      var help = App.MeshSettings.optimizationHelp(planar);
      T.ok(!/gmsh/i.test(help), help);
    });
  });

  test('the optimizer values sent to the server are unchanged', function () {
    T.eq(App.MeshSettings.optimizationChoices().map(function (c) { return c[0]; }),
         ['none', 'gmsh', 'netgen']);
  });
})();
