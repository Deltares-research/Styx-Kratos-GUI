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

  test('gravity says whether the self weight acts; it has no switch', function () {
    T.eq(BC().command('gravity', section()).message,
         'The self weight acts on every body, with g = 9.81 m/s².');
    T.eq(BC().command('gravity off', section()).ok, false);
    T.eq(BC().command('gravity ON', section()).ok, false);
    T.eq(BC().command('gravity maybe', section()).ok, false);
    var none = Object.assign(section(), { stages: [
      { id: 'initial', parent: null, calculation: 'mechanical', stress_initialisation: 'none' }] });
    T.eq(BC().command('gravity', none).message,
         'The self weight is off: the initial stage initialises no stresses (g = 9.81 m/s² '
         + 'when it acts).');
  });

  test('gravity with a number sets g, as kratos-cli gravity P G does', function () {
    var answer = BC().command('gravity 9.80665', section());
    T.eq(answer.body, { gravity_acceleration: 9.80665 });
    T.eq(answer.message, 'The self weight acts on every body, with g = 9.80665 m/s².');
    T.eq(BC().command('gravity 0', section()).ok, false);
    T.eq(BC().command('gravity -9.81', section()).ok, false);
  });

  test('a line that is not boundary or gravity is not this command', function () {
    T.eq(BC().command('water -2', section()), false);
    T.eq(BC().command('gravity off', section()).ok, false,
         'the self weight is the stress initialisation of the initial stage, not a switch');
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

  test('a seepage face draws its line and arrows out of the soil, without words', function () {
    var spec = App.Viewport.conditionGlyphSpec(
      seepage('exit', 'line', { points: [[20, -1], [20, -6]] }), section());
    T.eq(spec.lines[0], [[20, -1, 5], [20, -6, 5]]);
    T.ok(spec.symbols.length > 1 && spec.symbols.every(function (s) {
      return s.arrow && s.outward[0] === 1 && s.outward[1] === 0;
    }), 'every arrow points out of the right side');
    T.eq(spec.label, undefined, 'no word beside the symbol');
    var top = App.Viewport.conditionGlyphSpec(seepage('top', 'face', { face: 'top' }),
                                              section());
    T.eq(top.symbols[0].outward, [0, 1]);
  });

  test('a hydrostatic pressure on a line draws the pressure along that line', function () {
    var record = pressure('bank', 'line', { points: [[20, 0], [20, -6]] });
    var spec = App.Viewport.conditionGlyphSpec(record, section([record]));
    T.eq(spec.lines[0], [[0, -2, 5], [20, -2, 5]], 'its level, as before');
    T.ok(spec.diagram, 'and a diagram along the line');
    T.eq(spec.diagram.path, [[20, 0, 5], [20, -6, 5]]);
    T.near(spec.diagram.glyph.deepest, 4, 1e-9, 'deepest 4 m under the level');
    T.eq(spec.diagram.glyph.deepestInward, [-1, 0], 'drawn towards the middle');
    T.ok(/^p = 40000\b/.test(spec.diagram.text), spec.diagram.text);
    var whole = App.Viewport.conditionGlyphSpec(pressure('all', 'domain'),
                                                section([pressure('all', 'domain')]));
    T.eq(whole.diagram, undefined, 'on the whole soil it is the level alone');
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

  test('a drawn line becomes a phreatic line with x increasing', function () {
    T.eq(BC().phreaticPoints([[0, -1, 5], [10, -2, 5], [20, -3, 5]]),
         [[0, -1], [10, -2], [20, -3]]);
    T.eq(BC().phreaticPoints([[20, -3], [10, -2], [0, -1]]),
         [[0, -1], [10, -2], [20, -3]], 'a line drawn from right to left is turned round');
    T.eq(BC().phreaticPoints(null), []);
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

  test('the explorer says in which stages the water stands on the ground', function () {
    /* Read off the viewport's last build: one block of soil with its top at 0, the
       water at +1 in the second stage only. */
    var high = phreatic('pl', { x_coordinates: [0, 20], y_coordinates: [1, 1] });
    var low = phreatic('low', { x_coordinates: [0, 20], y_coordinates: [-3, -3] });
    var project = section(standard().concat([low, high]), {
      stages: [{ id: 's1', name: 'Dry', deactivate: ['pl'] },
               { id: 's2', name: 'Flooded', parent: 's1', activate: ['pl'],
                 deactivate: ['low'] }] });
    var block = { key: 'soil_L1', positions: [0, -15, 0, 20, -15, 0, 20, 0, 0, 0, 0, 0],
                  indices: [0, 1, 2, 0, 2, 3],
                  edges: [0, -15, 0, 20, -15, 0, 20, -15, 0, 20, 0, 0,
                          20, 0, 0, 0, 0, 0, 0, 0, 0, 0, -15, 0] };
    var built = App.Viewport.builtSections;
    App.Viewport.builtSections = function () { return [block]; };
    try {
      App.BOUNDARY_CONDITIONS = JSON.parse(JSON.stringify(project.boundary_conditions));
      App.PROJECT = project;
      App.Model.rebuildDerived();
    } finally { App.Viewport.builtSections = built; }
    var tree = App.TREES[Object.keys(App.TREES)[0]];
    var rows = tree.filter(function (n) {
      return n.label === 'Model conditions'; })[0].children[0].children;
    var flooded = rows.filter(function (n) { return n.obj === 'pl'; })[0];
    T.eq(flooded.children.map(function (n) { return n.label; }),
         ['Water on the ground  ·  stage Flooded']);
    T.ok(!rows.filter(function (n) { return n.obj === 'low'; })[0].children,
         'a line below the ground has no row');
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

  test('a support is one strip along its whole face; front and back draw nothing in 2D',
       function () {
    var project = section();
    var bottom = App.Viewport.conditionGlyphSpec(standard()[0], project);
    T.eq(bottom.symbols.length, 0);
    T.eq(bottom.strips.length, 1);
    T.eq([bottom.strips[0].from[0], bottom.strips[0].to[0]], [0, 20],
         'from one end of the face to the other');
    T.eq(bottom.strips[0].outward, [0, -1], 'x and y held: hatched ground');
    var left = App.Viewport.conditionGlyphSpec(standard()[1], project);
    T.eq(left.strips.length, 0, 'a roller is no strip');
    T.ok(left.symbols.length > 1, 'but a row of the point roller symbol');
    T.eq([left.symbols[0].roller, left.symbols[0].outward], [true, [-1, 0]]);
    var none = App.Viewport.conditionGlyphSpec(standard()[3], project);
    T.eq([none.symbols.length, none.strips.length], [0, 0]);
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
    var bare = App.Viewport.conditionGlyphSpec(standard()[1], project, {});
    T.eq([bare.symbols.length, bare.strips.length], [0, 0],
         'and then no face to draw a support on');
  });


  test('a support line is a strip per straight piece, a face met at a corner one symbol',
       function () {
    var project = section();
    var slope = App.Viewport.conditionGlyphSpec(support('slope', null, [true, true, false],
      { on: 'line', points: [[0, 0], [3, 3], [9, 3]] }), project);
    T.eq(slope.symbols.length, 0);
    T.eq(slope.strips.map(function (strip) {
      return [strip.from.slice(0, 2), strip.to.slice(0, 2)]; }),
      [[[0, 0], [3, 3]], [[3, 3], [9, 3]]], 'without a break from start to end');
    var h = Math.SQRT1_2;
    T.ok(Math.abs(slope.strips[0].outward[0] - h) < 1e-12
         && Math.abs(slope.strips[0].outward[1] + h) < 1e-12,
         'square to the piece, on the lower side: ' + slope.strips[0].outward);
    T.eq(slope.strips[1].outward, [0, -1]);
    var wall = App.Viewport.conditionGlyphSpec(support('wall', null, [true, true, false],
      { on: 'line', points: [[2, 0], [2, -5]] }), project);
    T.eq(wall.strips[0].outward, [-1, 0], 'an upright line stands out to -x');
    var corner = { left: [[0, 0, 5], [0, 0, 5]] };
    var touch = App.Viewport.conditionGlyphSpec(standard()[1], project, corner);
    T.eq([touch.symbols.length, touch.strips.length], [1, 0]);
  });

  test('a roller stands out along the component it holds', function () {
    var project = section();
    var bottomY = App.Viewport.conditionGlyphSpec(
      support('b', 'bottom', [false, true, false]), project);
    T.eq(bottomY.strips.length, 0);
    T.eq([bottomY.symbols[0].roller, bottomY.symbols[0].outward], [true, [0, -1]]);
    var bottomX = App.Viewport.conditionGlyphSpec(
      support('b', 'bottom', [true, false, false]), project);
    T.eq(bottomX.strips.length, 0, 'a face along the held component cannot roll on it');
    T.ok(bottomX.symbols.length > 1);
    T.eq([bottomX.symbols[0].roller, bottomX.symbols[0].outward], [true, [-1, 0]]);
    var line = App.Viewport.conditionGlyphSpec(
      support('l', null, [false, true, false], { on: 'line', points: [[0, -2], [20, -2]] }),
      project);
    T.eq(line.strips.length, 0, 'a roller on a line is no strip');
    T.ok(line.symbols.length > 1, 'but a row of the point roller symbol');
    T.eq([line.symbols[0].at.slice(0, 2), line.symbols[line.symbols.length - 1].at.slice(0, 2)],
         [[0, -2], [20, -2]], 'from one end of the line to the other');
    T.eq([line.symbols[0].roller, line.symbols[0].outward], [true, [0, -1]]);
    var point = App.Viewport.conditionGlyphSpec(
      support('p', null, [true, false, true], { on: 'point', points: [[3, -4]] }), project);
    T.eq([point.symbols.length, point.symbols[0].roller, point.symbols[0].outward],
         [1, true, [-1, 0]], 'z does not count in a section');
  });

  test('a water pressure draws its own level, without words beside it', function () {
    var spec = App.Viewport.conditionGlyphSpec(pressure('pore', 'domain'), section());
    T.eq(spec.lines[0], [[0, -2, 5], [20, -2, 5]]);
    T.eq(spec.label, undefined, 'no h = beside the level');
    T.eq(spec.dashed, true);
    var phreatic = App.Viewport.conditionGlyphSpec(pressure('line', 'domain', {
      fluid_pressure_type: 'Phreatic_Multi_Line', x_coordinates: [0, 20],
      y_coordinates: [-1, -3] }), section());
    T.eq(phreatic.lines[0], [[0, -1, 5], [20, -3, 5]]);
    T.eq(phreatic.label, undefined, 'no h = beside the phreatic line');
  });

  test('each condition is shown in its own tabs; Results shows only the water',
       function () {
    [true, false].forEach(function (layered) {
      var groups = App.Viewport.computeModeGroups(['soil_L1'], [], layered, [], [], [],
                                                  { supports: ['fixed_bottom'], water: ['pore'] });
      var tag = layered ? ' (layered soil)' : '';
      ['soil', 'structures', 'mesh'].forEach(function (mode) {
        T.ok(groups[mode].indexOf('fixed_bottom') >= 0, mode + ' shows the support' + tag);
        T.eq(groups[mode].indexOf('pore'), -1, mode + ' hides the flow condition' + tag);
      });
      T.ok(groups.flow.indexOf('pore') >= 0, 'flow shows the flow condition' + tag);
      T.eq(groups.flow.indexOf('fixed_bottom'), -1, 'flow hides the support' + tag);
      T.ok(groups.staged.indexOf('fixed_bottom') >= 0 && groups.staged.indexOf('pore') >= 0,
           'staged shows both' + tag);
      T.eq(groups.results.indexOf('fixed_bottom'), -1, 'no supports over the contour');
      T.ok(groups.results.indexOf('pore') >= 0, 'the water pressure over the contour');
    });
  });

  /* ── The water of each soil ───────────────────────────────────────── */

  function phreatic(id, extra) {
    return pressure(id, 'domain', Object.assign({
      fluid_pressure_type: 'Phreatic_Multi_Line', reference_coordinate: null,
      x_coordinates: [0, 20], y_coordinates: [-1, -1] }, extra || {}));
  }

  function head(id, extra) {
    return phreatic(id, Object.assign({ fluid_pressure_type: 'Head_Line',
                                        y_coordinates: [1, 3] }, extra || {}));
  }

  test('the water lines are the phreatic and head lines, on the soil or drawn', function () {
    var list = [head('head'), phreatic('pl', { on: 'line', points: [[0, -1], [20, -1]] }),
                pressure('level', 'domain'),
                pressure('dry', 'domain', { fluid_pressure_type: 'Uniform' }),
                head('left', { on: 'face', face: 'left' })];
    T.eq(BC().waterLines(list).map(function (r) { return r.id; }), ['head', 'pl']);
    T.eq(BC().phreaticLine(list).id, 'pl', 'drawn on a line, it is the phreatic line');
    T.eq(BC().headLines(list).map(function (r) { return r.id; }), ['head']);
    T.eq(BC().phreaticLine([pressure('level', 'domain')]), null);
  });

  test('a head line is said as one', function () {
    T.ok(/head line \(0, 1\) -> \(20, 3\), fixed/.test(BC().line(head('h'))));
    T.ok(/·  head line$/.test(BC().label(head('h'))));
  });

  test('a stage has one phreatic line on the soil or on a line', function () {
    BC().checkOnePhreatic([phreatic('pl')]);
    BC().checkOnePhreatic([phreatic('pl'), phreatic('pl2', { on: 'face', face: 'left' })]);
    BC().checkOnePhreatic([phreatic('pl'), phreatic('pl2', { active: false })]);
    var error = null;
    try {
      BC().checkOnePhreatic([phreatic('pl'), phreatic('pl2', { on: 'line' })]);
    } catch (e) { error = e; }
    T.ok(error && /one phreatic line, pl\. Switch pl2 off, or make it a head line/
      .test(error.message));
  });

  test('a staged project may switch from one phreatic line to another', function () {
    /* Which stage has which on is the server's to check. */
    BC().checkOnePhreatic([phreatic('pl'), phreatic('pl2')],
                          { stages: [{ id: 's1', name: 'First' }] });
    var list = [phreatic('pl'), phreatic('pl2')];
    T.eq(BC().phreaticLines(list).map(function (r) { return r.id; }), ['pl', 'pl2']);
    T.eq(BC().waterLineColor(list[1], list), BC().waterLineColor(list[0], list),
         'both in the phreatic blue');
  });

  test('a phreatic line made in a later stage is that stage\'s, in place of the one on', function () {
    var stages = [{ id: 's1', name: 'First', parent: null, activate: [], deactivate: [] },
                  { id: 's2', name: 'Second', parent: 's1', activate: [], deactivate: [] },
                  { id: 's3', name: 'Third', parent: 's2', activate: [], deactivate: [] }];
    var project = section(standard().concat([phreatic('pl')]),
                          { stages: stages, stageable_parts: ['pl', 'soil_L1'] });
    var made = phreatic('pl2', { on: 'line', points: [[0, -3], [20, -3]] });
    var staged = BC().stagedPhreatic(project, made, 's2');
    T.eq(staged.replaced, ['pl']);
    T.eq(staged.stages.map(function (s) { return [s.activate, s.deactivate]; }),
         [[[], ['pl2']], [['pl2'], ['pl']], [[], []]],
         'off in the initial stage, on from the second, the old one off from there');
    T.eq(project.stages[0].deactivate, [], 'the project is not edited');

    T.eq(BC().stagedPhreatic(project, made, 's1'), null, 'the initial stage: not a later one');
    T.eq(BC().stagedPhreatic(project, phreatic('pl'), 's2'), null, 'a line already there');
    T.eq(BC().stagedPhreatic(project, head('h'), 's2'), null, 'a head line');
    T.eq(BC().stagedPhreatic(section(standard()), made, 's2'), null, 'unstaged');

    var error = null;
    try { BC().checkInitialPhreatic(project, made, 's1'); } catch (e) { error = e; }
    T.ok(error && /First has pl\. To make this the phreatic line of a later stage, select/
      .test(error.message));
    BC().checkInitialPhreatic(project, made, 's2');
  });

  test('the whole soil row is the phreatic line, the head lines listed apart', function () {
    var project = section(standard().concat([head('head'), phreatic('pl')]));
    var whole = BC().grid(project).filter(function (row) { return !row.face; })[0];
    T.eq([whole.water, whole.waterId], ['Phreatic_Multi_Line', 'pl']);
    T.eq(BC().others(project).map(function (r) { return r.id; }), ['head']);
    var drawnLine = section(standard().concat(
      [phreatic('pl', { on: 'line', points: [[0, -1], [20, -1]] })]));
    T.eq(BC().grid(drawnLine).filter(function (row) { return !row.face; })[0].water, 'none',
         'a phreatic line drawn on a line is listed with the lines');
  });

  test('a soil takes the phreatic line, a head line, or is interpolated', function () {
    var list = [phreatic('pl', { on: 'line', points: [[0, -1], [20, -1]] }),
                head('head', { name: 'Aquifer head', on: 'line', points: [[0, 1], [20, 3]] }),
                pressure('level', 'domain')];
    T.eq(BC().soilWaterChoices(list), [
      ['', 'Phreatic line (pl)'], ['head', 'Head line (Aquifer head)'],
      ['interpolate', 'Interpolated between the soils above and below']]);
    T.eq(BC().soilWaterChoices([pressure('level', 'domain')])[0],
         ['', 'Phreatic line (none yet)']);
  });

  test('each soil has a row with its name and its water', function () {
    var project = section(standard(), {
      layers: [{ id: 'L1', name: 'Sand' }, { id: 'L2', name: 'Clay' }],
      soil_body_keys: ['soil_L1', 'soil_L2__a'], soil_body_labels: { soil_L2__a: 'Clay · A' },
      custom_parts: [{ key: 'peat', label: 'Peat', mat: 'm' }, { key: 'box', label: 'Box' }],
      soil_water: { soil_L2: 'interpolate', peat: 'head' } });
    T.eq(BC().soilWaterRows(project), [
      { key: 'soil_L1', label: 'Sand', water: '' },
      { key: 'soil_L2', label: 'Clay', water: 'interpolate' },
      { key: 'soil_L2__a', label: 'Clay · A', water: '' },
      { key: 'peat', label: 'Peat', water: 'head' }]);
  });

  test('a soil whose line is gone takes the whole soil water again', function () {
    var rows = [{ key: 'soil_L1', water: '' }, { key: 'soil_L2', water: 'interpolate' },
                { key: 'soil_L3', water: 'head' }, { key: 'soil_L4', water: 'gone' }];
    T.eq(BC().applySoilWater([phreatic('pl'), head('head')], rows),
         { soil_L2: 'interpolate', soil_L3: 'head' });
    T.eq(BC().applySoilWater([phreatic('pl'), pressure('head', 'domain')], rows),
         { soil_L2: 'interpolate' }, 'a hydrostatic level is no head line');
  });

  /* ── The colours of the water ─────────────────────────────────────── */

  test('the phreatic line and interpolated keep their colours, whatever the order',
       function () {
    var P = BC().PHREATIC_COLOR, I = BC().INTERPOLATE_COLOR;
    var a = [phreatic('pl'), head('h1'), head('h2')];
    var b = [head('h2'), head('h1'), phreatic('pl')];
    [a, b].forEach(function (list) {
      T.eq(BC().waterLineColor(list.filter(function (r) { return r.id === 'pl'; })[0], list), P);
    });
    var heads = a.slice(1).map(function (r) { return BC().waterLineColor(r, a); });
    T.ok(heads[0] !== heads[1], 'each head line its own colour');
    heads.forEach(function (color) { T.ok(color !== P && color !== I, color); });
    T.eq(BC().waterLineColor(pressure('level', 'domain'), a), null, 'a level is no line');
    var project = section(b, { layers: [{ id: 'L1', name: 'Sand' }],
                                soil_water: { soil_L1: 'interpolate' } });
    T.eq(BC().soilWaterColors(project, ['soil_L1']).soil_L1.color, I);
  });

  test('a piece of a layer takes its own water, else its layer\'s', function () {
    var project = section([phreatic('pl'), head('aq')], {
      soil_body_keys: ['soil_L1__a', 'soil_L1__b', 'soil_L2'],
      soil_water: { soil_L1: 'aq', soil_L1__b: 'interpolate', soil_L2: 'gone' } });
    T.eq(['soil_L1__a', 'soil_L1__b', 'soil_L2'].map(function (key) {
      return BC().soilWaterOf(project, key);
    }), ['aq', 'interpolate', ''], 'a line that is gone is the phreatic line');
    var colors = BC().soilWaterColors(project, ['soil_L1__a', 'soil_L2']);
    T.eq(colors.soil_L2.color, BC().PHREATIC_COLOR);
    T.eq(colors.soil_L2.fill, BC().tint(BC().PHREATIC_COLOR, 0.45));
    T.eq(colors.soil_L1__a.label, 'Head line: aq');
  });

  test('a project with no water line keeps the soils in their own colours', function () {
    var project = section([pressure('level', 'domain')]);
    T.eq(BC().soilWaterColors(project, ['soil_L1']), null);
    T.eq(BC().waterLegend(project, ['soil_L1']), []);
    var none = section([head('aq')], { soil_water: { soil_L2: 'aq' } });
    T.eq(BC().soilWaterColors(none, ['soil_L1']).soil_L1,
         { water: '', color: BC().NO_WATER_COLOR, fill: BC().tint(BC().NO_WATER_COLOR, 0.45),
           label: 'No water line' }, 'no phreatic line: no water line');
  });

  test('the legend has each water line, and interpolated when a soil takes it',
       function () {
    var project = section([head('aq', { name: 'Aquifer' }), phreatic('pl', { name: 'PL' })],
                          { soil_water: { soil_L2: 'interpolate' } });
    T.eq(BC().waterLegend(project, ['soil_L1', 'soil_L2']).map(function (row) {
      return [row.label, row.line];
    }), [['Phreatic line: PL', 'solid'], ['Head line: Aquifer', 'dashed'],
         ['Interpolated', null]]);
    T.eq(BC().waterLegend(project, ['soil_L1']).length, 2);
  });

  test('right-clicking a soil offers each water, the one it takes ticked', function () {
    var project = section([phreatic('pl'), head('aq', { name: 'Aquifer' })],
                          { soil_water: { soil_L1: 'aq' } });
    var menu = BC().soilWaterMenu(project, 'soil_L1');
    T.eq(menu.map(function (row) { return [row.soilWater, !!row.checked, !!row.disabled]; }),
         [['', false, false], ['aq', true, false], ['interpolate', false, false]]);
    T.eq(menu[1].action, 'soilWater');
    T.eq(menu[1].soilKey, 'soil_L1');
    var solid = BC().soilWaterMenu(Object.assign({}, project, { dimension: 3 }), 'soil_L1');
    T.eq(solid[2].disabled, true, 'interpolated is 2D only');
  });

  test('a soil set back on the phreatic line leaves its layer\'s water to the rest',
       function () {
    var project = section([phreatic('pl'), head('aq')], {
      soil_body_keys: ['soil_L1__a', 'soil_L1__b', 'soil_L1__c', 'soil_L2'],
      soil_water: { soil_L1: 'aq', soil_L1__c: 'interpolate' } });
    T.eq(BC().withSoilWater(project, 'soil_L1__a', ''),
         { soil_L1__b: 'aq', soil_L1__c: 'interpolate' });
    T.eq(BC().withSoilWater(project, 'soil_L2', 'aq'),
         { soil_L1: 'aq', soil_L1__c: 'interpolate', soil_L2: 'aq' });
    T.eq(BC().withSoilWater(project, 'soil_L1', ''), { soil_L1__c: 'interpolate' });
    T.eq(project.soil_water, { soil_L1: 'aq', soil_L1__c: 'interpolate' }, 'not changed');
  });

  test('the phreatic line is drawn solid with its mark, a head line dashed, no words',
       function () {
    var pl = phreatic('pl', { y_coordinates: [-1, -3] });
    var aq = head('aq', { name: 'Aquifer' });
    var project = section(standard().concat([pl, aq]));
    var line = App.Viewport.conditionGlyphSpec(pl, project);
    T.eq([line.waterLine, line.dashed, line.color], ['phreatic', false, BC().PHREATIC_COLOR]);
    T.eq(line.symbols.length, 1);
    T.eq(line.symbols[0].waterTable, true);
    T.eq(line.label, undefined, 'no words beside the phreatic line');
    var other = App.Viewport.conditionGlyphSpec(aq, project);
    T.eq([other.waterLine, other.dashed], ['head', true]);
    T.eq(other.color, BC().waterLineColor(aq, project.boundary_conditions));
    T.eq(other.label, undefined, 'no words beside the head line');
    T.eq(App.Viewport.alongPath([[0, 0, 5], [10, 0, 5], [10, 10, 5]], 0.75), [10, 5, 5]);
  });

  test('a condition is shown until it is hidden', function () {
    App.PROJECT = section(standard().concat([pressure('pore', 'domain')]));
    T.eq(App.Viewport.isVisible('roller_left'), true);
    T.eq(App.Viewport.isVisible('pore'), true);
    T.eq(App.Viewport.isVisible('soil_L1'), true, 'a part is shown as before');
  });

})();
