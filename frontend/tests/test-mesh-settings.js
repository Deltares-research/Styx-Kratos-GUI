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

  test('mesh targets prefer the selected body and otherwise use visible bodies', function () {
    var project = { layers: [{ id: 'L1' }, { id: 'L2' }] };
    var visible = function (key) { return key === 'soil_L2'; };
    T.eq(App.MeshSettings.meshTargets(project, 'soil_L1', visible), ['soil_L1']);
    T.eq(App.MeshSettings.meshTargets(project, null, visible), ['soil_L2']);
  });

  test('body controls preserve multiple selections and independent sizes', function () {
    var rows = App.MeshSettings.bodyControls(
      { layers: [{ id: 'L1', name: 'Upper' }, { id: 'L2', name: 'Lower' }],
        mesh: { element_size: 2.5, body_sizes: { soil_L1: 1.0, soil_L2: 4.0 } } },
      ['soil_L1', 'soil_L2']
    );
    T.eq(rows, [
      { key: 'soil_L1', label: 'Upper', enabled: true, size: 1.0 },
      { key: 'soil_L2', label: 'Lower', enabled: true, size: 4.0 }
    ]);
  });

  test('the window keeps a size it has no row for', function () {
    var project = { mesh: { element_size: 5, body_sizes: {
      sheetpile: 0.5, soil_L1__lift3: 1.0, soil_L1: 2.0 } } };
    T.eq(App.MeshSettings.savedBodySizes(project, [{ key: 'soil_L1', size: 3 }]),
         { sheetpile: 0.5, soil_L1__lift3: 1.0, soil_L1: 3 });
  });

  test('a row still at the global size adds no size of its own', function () {
    var project = { mesh: { element_size: 5, body_sizes: { soil_L2: 5 } } };
    T.eq(App.MeshSettings.savedBodySizes(project, [
      { key: 'soil_L1', size: 5 }, { key: 'soil_L2', size: 5 }, { key: 'soil_L3', size: 2 }
    ]), { soil_L2: 5, soil_L3: 2 }, 'only a size the project has, or one typed');
  });

  test('a row left empty takes its size away', function () {
    var project = { mesh: { element_size: 5, body_sizes: { soil_L1: 2 } } };
    T.eq(App.MeshSettings.savedBodySizes(project, [{ key: 'soil_L1', size: 0 }]), {});
  });

  test('a choice is what was left out of it', function () {
    var project = { layers: [{ id: 'L1' }, { id: 'L2' }],
                    custom_parts: [{ key: 'drawn_0', mat: 'm1' }, { key: 'shown_only' }] };
    T.eq(App.MeshSettings.leftOutBodies(project, ['soil_L1', 'drawn_0']), ['soil_L2']);
    T.eq(App.MeshSettings.leftOutBodies(project, ['soil_L1', 'soil_L2', 'drawn_0']), []);
  });

  test('a choice names only the bodies the project still has', function () {
    var project = { layers: [{ id: 'L1' }, { id: 'L3' }],
                    custom_parts: [{ key: 'drawn_0', mat: 'm1' }] };
    T.eq(App.MeshSettings.chosenBodies(project, ['soil_L3', 'soil_L_deleted']),
         ['soil_L1', 'drawn_0']);
  });

  test('a body added after a choice is meshed, as kratos-cli meshes it', function () {
    var before = { layers: [{ id: 'L1' }, { id: 'L2' }] };
    var leftOut = App.MeshSettings.leftOutBodies(before, ['soil_L1']);
    var after = { layers: [{ id: 'L1' }, { id: 'L2' }, { id: 'L_new' }] };
    T.eq(App.MeshSettings.chosenBodies(after, leftOut), ['soil_L1', 'soil_L_new']);
  });

  test('no choice, or a choice with nothing left, is no choice', function () {
    var project = { layers: [{ id: 'L1' }] };
    T.eq(App.MeshSettings.chosenBodies(project, null), null);
    T.eq(App.MeshSettings.chosenBodies(project, undefined), null);
    T.eq(App.MeshSettings.chosenBodies(project, ['soil_L1']), null);
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
