/* The boundary conditions (frontend/js/boundary-conditions.js).

   The drafts are held to core/model/drafts.py by test-drafts.js; this suite holds the
   rest: the `boundary` command, the standard supports put back, the
   dialog's face grid read off the records and written back to them, the one PATCH
   every write is, the explorer rows, and the symbols the viewport draws. */

(function () {
  var BC = function () { return App.BoundaryConditions; };

  function support(id, face, fixed, extra) {
    return Object.assign({ id: id, name: id, kind: 'displacement', on: 'face', face: face,
                           part: null, points: null, fixed: fixed, active: true }, extra || {});
  }

  function pressure(id, on, extra) {
    return Object.assign({ id: id, name: id, kind: 'water_pressure', on: on, face: null,
                           part: null, points: null, fluid_pressure_type: 'Hydrostatic',
                           is_fixed: true, value: 0, reference_coordinate: -2,
                           x_coordinates: null, y_coordinates: null, z_coordinates: null,
                           pressure_tension_cut_off: 0, active: true }, extra || {});
  }

  function standard() {
    return [support('fixed_bottom', 'bottom', [true, true, true]),
            support('roller_left', 'left', [true, false, false]),
            support('roller_right', 'right', [true, false, false]),
            support('roller_front', 'front', [false, false, true]),
            support('roller_back', 'back', [false, false, true])];
  }

  function section(conditions, extra) {
    return Object.assign({
      dimension: 2, section_offset: 5,
      domain: { x0: 0, x1: 20, z0: 0, z1: 10, y_top: 0, y_bottom: -15 },
      water: { y: -1.5 }, layers: [{ id: 'L1' }, { id: 'L2' }], custom_parts: [],
      boundary_conditions: conditions === undefined ? standard() : conditions
    }, extra || {});
  }

  /* ── The command box ──────────────────────────────────────────────── */

  test('boundary list says each condition as kratos-cli boundary list does', function () {
    var answer = BC().command('boundary list', section(standard().concat(
      [pressure('pore', 'domain')])));
    T.eq(answer.ok, true);
    T.eq(answer.body, null);
    var lines = answer.message.split('\n');
    T.eq(lines[0], 'fixed_bottom  fixed_bottom  displacement on the bottom face; fixed in x y z');
    T.eq(lines[3], 'pore  pore  water pressure on the whole soil; hydrostatic about -2 m, fixed');
    T.eq(lines.length, 5, 'a 2D list leaves the front and back supports out');
    T.ok(/kept for the solid model/.test(lines[4]));
    var solid = BC().command('boundary list', section(standard(), { dimension: 3 }));
    T.ok(/roller_front/.test(solid.message) && !/kept for the solid/.test(solid.message));
    T.eq(BC().command('boundary', section([])).message, 'No boundary conditions yet.');
  });

  test('a groundwater flow project notes that its supports are left out, as the CLI does',
       function () {
    var flow = section(standard().concat([pressure('pore', 'domain')]), {
      stages: [{ id: 'flow', name: 'Flow', calculation: 'flow' }] });
    var lines = BC().command('boundary list', flow).message.split('\n');
    T.eq(lines[lines.length - 1], 'A groundwater flow calculation leaves the supports out: '
         + 'it solves the water pressure alone.');
    var mixed = section(standard(), { stages: [
      { id: 'a', name: 'A', calculation: 'mechanical' },
      { id: 'flow', name: 'Flow', calculation: 'flow', parent: 'a' }] });
    T.ok(!/groundwater flow/.test(BC().command('boundary list', mixed).message),
         'a mix is not a flow project: the export refuses it');
    var water = section([pressure('pore', 'domain')], { stages: flow.stages });
    T.ok(!/groundwater flow/.test(BC().command('boundary list', water).message),
         'no support, no note');
  });

  test('boundary standard sends the standard supports and keeps the water', function () {
    var project = section([support('bottom', 'bottom', [false, true, false]),
                           pressure('pore', 'domain')]);
    var answer = BC().command('boundary standard', project);
    T.eq(answer.ok, true);
    T.eq(answer.body.boundary_conditions.map(function (c) { return c.id; }),
         ['fixed_bottom', 'roller_left', 'roller_right', 'roller_front', 'roller_back',
          'pore']);
  });

  test('a line that is not boundary is not this command', function () {
    T.eq(BC().command('water -2', section()), false);
    T.eq(BC().command('gravity off', section()), false,
         'gravity is the stress initialisation of the initial stage, not a command');
    T.eq(BC().command('boundary teleport', section()).ok, false);
  });

  /* ── The face grid ────────────────────────────────────────────────── */

  test('the grid reads each face and the whole soil off the conditions', function () {
    var rows = BC().grid(section(standard().concat([
      pressure('left_head', 'face', { face: 'left', reference_coordinate: -1 }),
      pressure('pore', 'domain', { is_fixed: false })])));
    T.eq(rows.map(function (r) { return r.face; }), ['bottom', 'left', 'right', 'top', null],
         'a 2D model has no front and back face');
    T.eq(rows[0].support, 'fixed');
    T.eq(rows[1].support, 'roller');
    T.eq([rows[1].water, rows[1].number], ['Hydrostatic', -1]);
    T.eq(rows[3].support, 'free');
    T.eq([rows[4].water, rows[4].initial], ['Hydrostatic', true]);
  });

  test('applying the grid changes, makes and removes the conditions of each row', function () {
    var project = section(standard().concat([pressure('pore', 'domain')]));
    var rows = BC().grid(project);
    rows[0].support = 'roller';                  // the bottom holds y only
    rows[1].support = 'free';                    // nothing on the left
    rows[2].water = 'Uniform'; rows[2].number = '-5000';
    rows[3].support = 'custom'; rows[3].fixed = [true, false, false];
    rows[4].water = 'none';                      // no pore pressure
    var list = BC().applyGrid(project, rows);
    var byId = {};
    list.forEach(function (c) { byId[c.id] = c; });
    T.eq(byId.fixed_bottom.fixed, [false, true, false]);
    T.eq(byId.roller_left, undefined);
    T.eq(byId.pore, undefined);
    var right = list.filter(function (c) { return c.kind === 'water_pressure'; })[0];
    T.eq([right.on, right.face, right.fluid_pressure_type, right.value],
         ['face', 'right', 'Uniform', -5000]);
    var top = list.filter(function (c) { return c.face === 'top'; })[0];
    T.eq([top.kind, top.fixed, top.name], ['displacement', [true, false, false], 'Support top']);
    T.ok(byId.roller_front && byId.roller_back, 'a face the grid does not show stays');
  });

  function seepage(id, on, extra) {
    return Object.assign({ id: id, name: id, kind: 'seepage', on: on, face: null,
                           part: null, points: null, active: true }, extra || {});
  }

  test('a seepage face is a choice of a face row, read and written back', function () {
    var project = section(standard().concat([seepage('out', 'face', { face: 'right' })]));
    var rows = BC().grid(project);
    T.eq([rows[2].water, rows[2].seepageId], ['seepage', 'out']);
    T.eq(BC().others(project).map(function (c) { return c.id; }), [],
         'a seepage face on a face is in the grid, not below it');
    rows[2].water = 'none';                     // the right face closed
    rows[3].water = 'seepage';                  // the top open
    var list = BC().applyGrid(project, rows);
    var faces = list.filter(function (c) { return c.kind === 'seepage'; });
    T.eq(faces.map(function (c) { return [c.on, c.face, c.name]; }),
         [['face', 'top', 'Seepage top']]);
    rows = BC().grid(project);
    rows[4].water = 'seepage';
    var error = null;
    try { BC().applyGrid(project, rows); } catch (e) { error = e; }
    T.ok(error && /on a face, not the whole soil/.test(error.message));
  });

  test('a seepage face says what it is, in the list and in the explorer', function () {
    var record = seepage('exit', 'line', { points: [[20, -1], [20, -6]] });
    T.eq(BC().line(record),
         'exit  exit  seepage on line (20, -1) -> (20, -6); water may leave the soil here');
    T.eq(BC().label(record), 'exit  ·  seepage');
  });

  test('a seepage face draws its line, arrows out of the soil and the word', function () {
    var spec = App.Viewport.conditionGlyphSpec(
      seepage('exit', 'line', { points: [[20, -1], [20, -6]] }), section());
    T.eq(spec.lines[0], [[20, -1, 5], [20, -6, 5]]);
    T.ok(spec.symbols.length > 1 && spec.symbols.every(function (s) {
      return s.arrow && s.outward[0] === 1 && s.outward[1] === 0;
    }), 'every arrow points out of the right side');
    T.eq(spec.label.text, 'seepage');
    var top = App.Viewport.conditionGlyphSpec(seepage('top', 'face', { face: 'top' }),
                                              section());
    T.eq(top.symbols[0].outward, [0, 1]);
  });

  test('a hydrostatic row with no level takes the water level', function () {
    var rows = BC().grid(section([]));
    rows[4].water = 'Hydrostatic';
    var list = BC().applyGrid(section([]), rows);
    T.eq([list[0].on, list[0].reference_coordinate], ['domain', -1.5]);
  });

  test('a phreatic line from the grid needs its points first', function () {
    var rows = BC().grid(section([]));
    rows[4].water = 'Phreatic_Multi_Line';
    var error = null;
    try { BC().applyGrid(section([]), rows); } catch (e) { error = e; }
    T.ok(error && /points of its line/.test(error.message));
  });

  test('the conditions the grid does not show are listed apart', function () {
    var line = support('strip', null, [false, true, false],
                       { on: 'line', points: [[0, -5], [5, -5]] });
    var rest = BC().others(section(standard().concat([line])));
    T.eq(rest.map(function (c) { return c.id; }), ['strip'],
         'a 2D model does not show its front and back supports');
    rest = BC().others(section(standard().concat([line]), { dimension: 3 }));
    T.eq(rest.map(function (c) { return c.id; }), ['strip'], 'in 3D the grid shows them');
  });

  test('a part condition may name each layer, each body and each soil part', function () {
    T.eq(BC().soilPartKeys(section([], { soil_body_keys: ['soil_L1', 'soil_L1__lift1'],
                                         custom_parts: [{ key: 'drawn_1', mat: 'm1' },
                                                        { key: 'drawn_2', mat: null }] })),
         ['soil_L1', 'soil_L2', 'soil_L1__lift1', 'drawn_1']);
  });

  test('the stage panel names the water conditions each stage has on', function () {
    var project = section(standard().concat([
      pressure('high', 'domain', { name: 'High' }),
      pressure('low', 'domain', { name: 'Low', reference_coordinate: -6 })]), {
      stageable_parts: ['soil_L1', 'soil_L2', 'high', 'low'],
      stages: [{ id: 'p1', name: 'One', parent: null, activate: [], deactivate: ['low'] },
               { id: 'p2', name: 'Two', parent: 'p1', activate: ['low'],
                 deactivate: ['high'] },
               { id: 'p3', name: 'Dry', parent: 'p2', activate: [], deactivate: ['low'] }]
    });
    T.eq(BC().waterIn(project, 'p1'), 'High');
    T.eq(BC().waterIn(project, 'p2'), 'Low');
    T.eq(BC().waterIn(project, 'p3'), 'None');
  });

  /* The rail's draw tools hand DrawInput a line or a one-click point. A point keeps
     the height it was clicked at (`atPointer`): without it DrawInput puts a 'load'
     on the ground surface, and a water pressure point deep in the soil with it.
     Where the clicks land is test-draw-pointer.js's. */
  test('the rail tools draw a line, or a point where it was clicked', function () {
    var savedDraw = App.DrawInput, savedProject = App.PROJECT;
    var started = [];
    App.DrawInput = { start: function (mode, options) { started.push([mode, options]); } };
    App.PROJECT = section();
    try {
      BC().draw('water_pressure', 'line');
      BC().draw('seepage', 'line');
      BC().draw('water_pressure', 'point');
      BC().draw('displacement', 'point');
    } finally { App.DrawInput = savedDraw; App.PROJECT = savedProject; }
    T.eq(started.map(function (s) { return s[0]; }), ['line', 'line', 'load', 'load']);
    started.forEach(function (s) {
      T.ok(s[1].atPointer, s[0] + ': where the pointer is, not on the ground');
      T.eq(typeof s[1].onComplete, 'function');
    });
  });

  test('points are typed as x y pairs', function () {
    T.eq(BC().parsePoints('0 -5, 5 -5'), [[0, -5], [5, -5]]);
    T.eq(BC().parsePoints('0 -5, 5'), null);
  });

  /* ── Writing ──────────────────────────────────────────────────────── */

  test('saving a condition writes the whole list in one conditions patch', function () {
    var sent = null;
    App.PROJECT = section();
    App.Api = { patch: function (path, body) {
      sent = { path: path, body: body };
      return Promise.resolve({ project: section() });
    } };
    App.Model = { apply: function () {}, load: function () { return Promise.resolve(); } };
    App.Viewport = { refresh: function () { return Promise.resolve(); } };
    App.Command = { ok: function () {}, err: function () {}, note: function () {} };
    App.Explorer = null;
    App.selectObject = null;
    var record = BC().draftWaterPressure(App.PROJECT, 'domain', {});
    return BC().save(record).then(function () {
      T.eq(sent.path, '/api/project/conditions');
      T.eq(sent.body.boundary_conditions.length, 6);
      T.eq(Object.keys(sent.body), ['boundary_conditions']);
    });
  });

  test('the explorer check box shows whether the conditions are active', function () {
    var project = section([support('fixed_bottom', 'bottom', [true, true, true]),
                           support('roller_left', 'left', [true, false, false],
                                   { active: false })]);
    T.eq(BC().activeState(['fixed_bottom'], project), 'on');
    T.eq(BC().activeState(['roller_left'], project), 'off');
    T.eq(BC().activeState(['fixed_bottom', 'roller_left'], project), 'mixed');
  });

  test('the explorer check box switches the conditions in one conditions patch', function () {
    var sent = null, said = null;
    App.PROJECT = section();
    App.Api = { patch: function (path, body) {
      sent = body;
      return Promise.resolve({ project: section() });
    } };
    App.Model = { apply: function () {}, load: function () { return Promise.resolve(); } };
    App.Viewport = { refresh: function () { return Promise.resolve(); } };
    App.Command = { ok: function (text) { said = text; }, err: function () {},
                    note: function () {} };
    App.Explorer = null;
    return BC().setActive(['roller_left', 'roller_right'], false).then(function () {
      var active = {};
      sent.boundary_conditions.forEach(function (record) { active[record.id] = record.active; });
      T.eq(active, { fixed_bottom: true, roller_left: false, roller_right: false,
                     roller_front: true, roller_back: true });
      T.eq(said, 'Boundary conditions roller_left, roller_right are inactive: kept in the '
                 + 'project, but not exported.');
    });
  });

  /* ── The explorer and the viewport ────────────────────────────────── */

  test('the explorer lists the conditions, and no gravity, under Model conditions',
       function () {
    var project = section(standard().concat([pressure('pore', 'domain')]));
    App.BOUNDARY_CONDITIONS = JSON.parse(JSON.stringify(project.boundary_conditions));
    App.PROJECT = project;
    App.Model.rebuildDerived();
    var tree = App.TREES[Object.keys(App.TREES)[0]];
    var node = tree.filter(function (n) { return n.label === 'Model conditions'; });
    T.eq(node.length, 1, 'one Model conditions node, the live one');
    var conditions = node[0].children[0];
    T.eq(conditions.count, 4, 'no front and back supports in a 2D model');
    T.eq(conditions.children[1].label, 'roller_left  ·  x fixed');
    T.eq(conditions.children[3].label, 'pore  ·  h = -2.00 m');
    T.eq(node[0].children.length, 1, 'gravity is in the Stage explorer');
    T.ok(App.OBJECT_PROPS.pore && !App.OBJECT_PROPS.gravity);
  });

  test('the explorer marks the supports of a groundwater flow project as left out',
       function () {
    var project = section(standard().concat([pressure('pore', 'domain')]), {
      stages: [{ id: 'flow', name: 'Flow', calculation: 'flow' }] });
    App.BOUNDARY_CONDITIONS = JSON.parse(JSON.stringify(project.boundary_conditions));
    App.PROJECT = project;
    App.Model.rebuildDerived();
    var tree = App.TREES[Object.keys(App.TREES)[0]];
    var conditions = tree.filter(function (n) {
      return n.label === 'Model conditions'; })[0].children[0];
    T.eq(conditions.children[1].label,
         'roller_left  ·  x fixed  (unused in flow)');
    T.eq(conditions.children[3].label, 'pore  ·  h = -2.00 m', 'the water is written');
  });

  test('a support is a row of symbols along its face; front and back draw nothing in 2D',
       function () {
    var project = section();
    var bottom = App.Viewport.conditionGlyphSpec(standard()[0], project);
    T.ok(bottom.symbols.length >= 2);
    T.eq(bottom.symbols[0].outward, [0, -1]);
    T.eq(bottom.symbols[0].roller, false, 'x and y held: the clamp');
    T.eq([bottom.symbols[0].at[0], bottom.symbols[bottom.symbols.length - 1].at[0]],
         [0, 20], 'from one end of the face to the other');
    var left = App.Viewport.conditionGlyphSpec(standard()[1], project);
    T.eq([left.symbols[0].roller, left.symbols[0].outward], [true, [-1, 0]]);
    T.eq(App.Viewport.conditionGlyphSpec(standard()[3], project).symbols.length, 0);
  });

  test('a face is where the soil is, not where the domain is', function () {
    // The domain goes down to -15; the layers stop at -10.
    var project = section();
    var soil = { key: 'soil_L1', positions: [0, 0, 5, 20, 0, 5, 20, -10, 5, 0, -10, 5,
                                             0, -4, 5, 20, -4, 5] };
    var other = { key: 'wall', positions: [3, 2, 5, 3, -14, 5] };
    var outlines = App.Viewport.soilFaceOutlines([soil, other], ['soil_L1'], project);
    T.eq(outlines.left, [[0, -10, 5], [0, 0, 5]]);
    T.eq(outlines.bottom, [[0, -10, 5], [20, -10, 5]]);
    var left = App.Viewport.conditionGlyphSpec(standard()[1], project, outlines);
    T.eq([left.symbols[0].at[1], left.symbols[left.symbols.length - 1].at[1]], [-10, 0]);
    T.eq(App.Viewport.soilFaceOutlines([other], ['soil_L1'], project), null,
         'nothing to measure with no soil drawn');
    T.eq(App.Viewport.conditionGlyphSpec(standard()[1], project, {}).symbols.length, 0,
         'and then no face to draw a support on');
  });


  test('a support line has symbols along it, a face met at a corner has one', function () {
    var project = section();
    var slope = App.Viewport.conditionGlyphSpec(support('slope', null, [true, true, false],
      { on: 'line', points: [[0, 0], [3, 3], [9, 3]] }), project);
    T.ok(slope.symbols.length > 3, 'between the corners too');
    T.eq(slope.symbols[0].at.slice(0, 2), [0, 0]);
    T.eq(slope.symbols[slope.symbols.length - 1].at.slice(0, 2), [9, 3]);
    var corner = { left: [[0, 0, 5], [0, 0, 5]] };
    T.eq(App.Viewport.conditionGlyphSpec(standard()[1], project, corner).symbols.length, 1);
  });

  test('a roller points along the component it holds', function () {
    var project = section();
    var bottomY = App.Viewport.conditionGlyphSpec(
      support('b', 'bottom', [false, true, false]), project);
    T.eq([bottomY.symbols[0].roller, bottomY.symbols[0].outward], [true, [0, -1]]);
    var bottomX = App.Viewport.conditionGlyphSpec(
      support('b', 'bottom', [true, false, false]), project);
    T.eq(bottomX.symbols[0].outward, [-1, 0]);
    var point = App.Viewport.conditionGlyphSpec(
      support('p', null, [true, false, true], { on: 'point', points: [[3, -4]] }), project);
    T.eq([point.symbols.length, point.symbols[0].roller, point.symbols[0].outward],
         [1, true, [-1, 0]], 'z does not count in a section');
  });

  test('a water pressure draws its own level, with h beside it', function () {
    var spec = App.Viewport.conditionGlyphSpec(pressure('pore', 'domain'), section());
    T.eq(spec.lines[0], [[0, -2, 5], [20, -2, 5]]);
    T.eq(spec.label.text, 'h = -2.00 m');
    T.eq(spec.dashed, true);
    var phreatic = App.Viewport.conditionGlyphSpec(pressure('line', 'domain', {
      fluid_pressure_type: 'Phreatic_Multi_Line', x_coordinates: [0, 20],
      y_coordinates: [-1, -3] }), section());
    T.eq(phreatic.lines[0], [[0, -1, 5], [20, -3, 5]]);
  });

  test('the conditions may be shown in every mode; Results shows only the water',
       function () {
    [true, false].forEach(function (layered) {
      var groups = App.Viewport.computeModeGroups(['soil_L1'], [], layered, [], [], [],
                                                  { supports: ['fixed_bottom'], water: ['pore'] });
      ['soil', 'structures', 'mesh', 'flow', 'staged'].forEach(function (mode) {
        T.ok(groups[mode].indexOf('fixed_bottom') >= 0 && groups[mode].indexOf('pore') >= 0,
             mode);
      });
      T.eq(groups.results.indexOf('fixed_bottom'), -1, 'no supports over the contour');
      T.ok(groups.results.indexOf('pore') >= 0, 'the water pressure over the contour');
    });
  });

  test('a condition is hidden until it is shown', function () {
    App.PROJECT = section(standard().concat([pressure('pore', 'domain')]));
    T.eq(App.Viewport.isVisible('roller_left'), false);
    T.eq(App.Viewport.isVisible('pore'), false);
    T.eq(App.Viewport.isVisible('soil_L1'), true, 'a part is shown as before');
  });

})();
