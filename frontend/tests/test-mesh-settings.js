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

  test('mesh bodies include material-bearing custom soil but not unassigned geometry', function () {
    var project = {
      layers: [{ id: 'L1', name: 'Upper' }],
      custom_parts: [{ key: 'fill', label: 'Backfill', mat: 'sand' },
                     { key: 'drawing', label: 'Unassigned geometry' }]
    };
    T.eq(App.MeshSettings.bodyControls(project, ['fill']).map(function (row) {
      return { key: row.key, label: row.label, enabled: row.enabled };
    }), [{ key: 'soil_L1', label: 'Upper', enabled: false },
         { key: 'fill', label: 'Backfill', enabled: true }]);
    T.eq(App.MeshSettings.meshTargets(project, 'fill', function () { return false; }), ['fill']);
    T.eq(App.MeshSettings.meshTargets(project, 'drawing', function () { return true; }),
         ['soil_L1', 'fill']);
  });

  test('body controls preserve multiple selections and independent sizes', function () {
    var rows = App.MeshSettings.bodyControls(
      { layers: [{ id: 'L1', name: 'Upper' }, { id: 'L2', name: 'Lower' }],
        mesh: { element_size: 2.5, body_sizes: { soil_L1: 1.0, soil_L2: 4.0 } } },
      ['soil_L1', 'soil_L2']
    );
    T.eq(rows, [
      { key: 'soil_L1', label: 'Upper', enabled: true, size: 1.0, follows: false },
      { key: 'soil_L2', label: 'Lower', enabled: true, size: 4.0, follows: false }
    ]);
  });

  test('a row with no size of its own shows the global size and follows it', function () {
    var rows = App.MeshSettings.bodyControls(
      { layers: [{ id: 'L1', name: 'Upper' }], mesh: { element_size: 2.5, body_sizes: {} } },
      ['soil_L1']
    );
    T.eq(rows, [{ key: 'soil_L1', label: 'Upper', enabled: true, size: 2.5, follows: true }]);
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

  /* ── The structures' sizes and the refinement boxes ─────────────────── */

  test('each sheet pile has a row, with its own size or none', function () {
    var project = { beams: [{ id: 'sheetpile', name: 'Wall' }, { id: 'b2', name: 'Strut' }],
                    mesh: { element_size: 5, body_sizes: { sheetpile: 0.5 } } };
    T.eq(App.MeshSettings.structureControls(project), [
      { key: 'sheetpile', label: 'Wall', size: 0.5 },
      { key: 'b2', label: 'Strut', size: null }]);
    T.eq(App.MeshSettings.structureControls({ mesh: {} }), []);
  });

  test("a structure's size is saved, and a row left empty takes it away", function () {
    var project = { mesh: { body_sizes: { soil_L1: 2, sheetpile: 0.5 } } };
    T.eq(App.MeshSettings.savedStructureSizes(project.mesh.body_sizes, [
      { key: 'sheetpile', size: null }, { key: 'b2', size: 0.25 }]),
         { soil_L1: 2, b2: 0.25 });
  });

  test("the boxes the window lists are the model's own; a cylinder is kept as it is", function () {
    var box = { kind: 'box', size: 0.75, thickness: 45, x_min: -1, x_max: 8,
                y_min: -16, y_max: 1, z_min: -1, z_max: 11 };
    var cylinder = { kind: 'cylinder', size: 1, x: 0, y: 0, z: 0, axis_x: 0, axis_y: 1,
                     axis_z: 0, radius: 1 };
    var project = { mesh: { refinements: [box, cylinder] } };
    T.eq(App.MeshSettings.refinementBoxes(project), [box]);
    var moved = Object.assign({}, box, { size: 0.5 });
    T.eq(App.MeshSettings.savedRefinements(project, [moved]), [cylinder, moved]);
    T.eq(App.MeshSettings.savedRefinements(project, []), [cylinder]);
  });

  test('a new box is in the middle of the section, finer than the mesh, and spans z', function () {
    var project = { dimension: 2,
                    domain: { x0: 0, x1: 80, y_top: 0, y_bottom: -60, z0: 0, z1: 10 },
                    mesh: { element_size: 5 } };
    var box = App.MeshSettings.draftBox(project);
    T.eq(box.kind, 'box');
    T.ok(box.size < 5, 'finer than the mesh around it');
    T.ok(box.x_min > 0 && box.x_max < 80 && box.x_min < box.x_max);
    T.ok(box.y_min > -60 && box.y_max === 0 && box.y_min < box.y_max, 'from the surface down');
    T.ok(box.z_min < 0 && box.z_max > 10, 'the whole depth: a 2D section is cut anywhere in z');
  });

  test('a box is checked before it is saved', function () {
    var ok = { kind: 'box', size: 1, thickness: 0, x_min: 0, x_max: 1, y_min: -1, y_max: 0,
               z_min: 0, z_max: 1 };
    T.eq(App.MeshSettings.boxProblem(ok), null);
    T.ok(/size/.test(App.MeshSettings.boxProblem(Object.assign({}, ok, { size: 0 }))));
    T.ok(/band/.test(App.MeshSettings.boxProblem(Object.assign({}, ok, { thickness: -1 }))));
    T.ok(/x/.test(App.MeshSettings.boxProblem(Object.assign({}, ok, { x_max: 0 }))));
    T.ok(/y/.test(App.MeshSettings.boxProblem(Object.assign({}, ok, { y_min: 0 }))));
    T.ok(App.MeshSettings.boxProblem(Object.assign({}, ok, { x_min: NaN })));
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
