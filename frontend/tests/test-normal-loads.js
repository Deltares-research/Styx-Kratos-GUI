/* Structure-mode normal loads.

   A normal load is a pressure applied perpendicular to a free polyline -- an exposed
   excavation face, a sloped boundary -- rather than the fixed x/y vector a LineLoad
   carries on a flat horizontal run. Sized either "Hydrostatic" (tracks the project's
   water level, the usual case for an exposed excavation face) or "Uniform" (a fixed
   pressure). Plane strain only; see NORMAL_LOAD_CONDITIONS in core/kratos/writer.py. */

(function () {
  function section(extra) {
    return Object.assign({
      dimension: 2, section_offset: 20,
      domain: { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 },
      materials: [{ id: 'mat_sand', name: 'Sand' }],
      loads: [], beams: [], beam_sections: [],
      water: { y: -3.5, specific_weight: 10.0 },
      normal_loads: []
    }, extra || {});
  }

  function solid(extra) {
    return Object.assign(section(), { dimension: 3 }, extra || {});
  }

  /* ── Where a normal load can be made ───────────────────────────────── */

  test('normal loads are authored in the 2D section and nowhere else', function () {
    T.eq(App.NormalLoads.available(section()), true);
    T.eq(App.NormalLoads.available(solid()), false);
    T.ok(App.NormalLoads.unavailableMessage(solid()));
  });

  test('drafting in the solid model refuses with a reason', function () {
    var error = null;
    try { App.NormalLoads.draft(solid()); } catch (e) { error = e; }
    T.ok(error, 'a 3D normal load is not a thing this exporter can write');
  });

  /* ── Drafting ───────────────────────────────────────────────────────── */

  test('a normal load drafts as a free line down the middle of the section', function () {
    var record = App.NormalLoads.draft(section());
    T.eq(record.points.length, 2);
    // Uniform, so the magnitude the form asks for is the magnitude that is applied:
    // hydrostatic derives its own from the water level and drops this one.
    T.eq(record.fluid_pressure_type, 'Uniform');
    T.eq(record.pressure, 0);
    T.eq(record.active, true);
    T.eq(record.id, 'normalload_1');
    T.eq(record.kind, 'normal');
  });

  test('drafted ids skip whichever numbers are already taken', function () {
    var project = section({ normal_loads: [{ id: 'normalload_1' }] });
    var record = App.NormalLoads.draft(project);
    T.eq(record.id, 'normalload_2');
  });

  /* ── Validation ─────────────────────────────────────────────────────── */

  test('a normal load needs a name, a known type and a finite pressure', function () {
    var ok = { id: 'normalload_1', name: 'River load', kind: 'normal',
              points: [[8, 0], [8, -5]], fluid_pressure_type: 'Hydrostatic',
              pressure: 0, active: true };
    T.eq(App.NormalLoads.validate(ok), null);
    T.ok(App.NormalLoads.validate(Object.assign({}, ok, { name: '  ' })));
    T.ok(App.NormalLoads.validate(Object.assign({}, ok, { fluid_pressure_type: 'Other' })));
    T.ok(App.NormalLoads.validate(Object.assign({}, ok, { pressure: NaN })));
  });

  test('a normal load needs a usable polyline', function () {
    var ok = { id: 'normalload_1', name: 'River load', kind: 'normal',
              points: [[8, 0], [8, -5]], fluid_pressure_type: 'Hydrostatic',
              pressure: 0, active: true };
    T.ok(App.NormalLoads.validate(Object.assign({}, ok, { points: [[8, 0]] })));
    T.ok(App.NormalLoads.validate(
      Object.assign({}, ok, { points: [[8, 0], [8, 0]] })),
      'cannot repeat the same point twice');
    T.ok(App.NormalLoads.validate(
      Object.assign({}, ok, { points: [[8, 0], [NaN, -1]] })));
  });

  /* ── Length ─────────────────────────────────────────────────────────── */

  test('length is the polyline it runs along, sloped and flat runs both', function () {
    var record = { points: [[8, 0], [8, -3], [12, -3]] };
    T.near(App.NormalLoads.length(record), 7, 1e-9);
  });

  /* ── Persistence ────────────────────────────────────────────────────── */

  test('saving a normal load writes it in one structures patch, loads unchanged', function () {
    var sent = null;
    var saved = { Api: App.Api, PROJECT: App.PROJECT, NORMAL_LOADS: App.NORMAL_LOADS,
                  Model: App.Model, Viewport: App.Viewport, Command: App.Command,
                  Explorer: App.Explorer, selectObject: App.selectObject };
    App.PROJECT = section();
    App.NORMAL_LOADS = [];
    App.Api = { patch: function (path, body) {
      sent = { path: path, body: body };
      return Promise.resolve({ project: section() });
    } };
    App.Model = { apply: function () {}, load: function () { return Promise.resolve(); } };
    App.Viewport = { refresh: function () { return Promise.resolve(); } };
    App.Command = { ok: function () {}, err: function () {}, note: function () {} };
    App.Explorer = null;
    App.selectObject = null;

    var record = App.NormalLoads.draft(App.PROJECT);
    return App.NormalLoads.save(record)
      .then(function () {
        T.eq(sent.path, '/api/project/structures');
        T.eq(sent.body.normal_loads.length, 1);
        T.ok('loads' in sent.body, 'the required loads collection travels with it');
        T.eq('beams' in sent.body, false,
             'a collection this write does not mention is left alone by the server');
      })
      .then(function () { Object.assign(App, saved); },
            function (e) { Object.assign(App, saved); throw e; });
  });

  test('deleting a normal load leaves the loads collection alone', function () {
    var sent = null;
    var saved = { Api: App.Api, PROJECT: App.PROJECT, NORMAL_LOADS: App.NORMAL_LOADS,
                  Model: App.Model, Viewport: App.Viewport, Command: App.Command,
                  Explorer: App.Explorer, state: App.state };
    var project = section({
      normal_loads: [{ id: 'normalload_1', name: 'River load', kind: 'normal',
                       points: [[8, 0], [8, -5]], fluid_pressure_type: 'Hydrostatic',
                       pressure: 0, active: true }]
    });
    App.PROJECT = project;
    App.NORMAL_LOADS = project.normal_loads.slice();
    App.Api = { patch: function (path, body) {
      sent = body;
      return Promise.resolve({ project: section() });
    } };
    App.Model = { apply: function () {}, load: function () { return Promise.resolve(); } };
    App.Viewport = { refresh: function () { return Promise.resolve(); } };
    App.Command = { ok: function () {}, err: function () {}, note: function () {} };
    App.Explorer = null;
    App.state = { selection: null };

    return App.NormalLoads.remove('normalload_1')
      .then(function (done) {
        T.eq(done, true);
        T.eq(sent.normal_loads, []);
        T.ok('loads' in sent, 'the required loads collection travels with it');
      })
      .then(function () { Object.assign(App, saved); },
            function (e) { Object.assign(App, saved); throw e; });
  });

  /* ── The form ───────────────────────────────────────────────────────── */

  test('starting a normal load asks before it writes anything', function () {
    /* A load nobody has given a position or a magnitude is not a load anyone meant,
       so the form opens first -- the order a line load is created in. */
    var saved = { Api: App.Api, PROJECT: App.PROJECT, NORMAL_LOADS: App.NORMAL_LOADS,
                  Dialogs: App.Dialogs, UI: App.UI, Command: App.Command };
    var opened = null, patched = false;
    App.PROJECT = section();
    App.NORMAL_LOADS = [];
    App.Api = { patch: function () { patched = true; return Promise.resolve({}); } };
    App.Command = { ok: function () {}, err: function () {}, note: function () {} };
    App.Dialogs = { open: function (spec) { opened = spec; return { close: function () {} }; } };
    try {
      App.NormalLoads.start();
      T.ok(opened, 'the form opened');
      T.eq(patched, false, 'and nothing was saved until it is submitted');
      T.ok(/Create normal load/.test(opened.title));
      T.eq(opened.buttons.map(function (b) { return b.label; }),
           ['Pick on model…', 'Save', 'Cancel']);
    } finally { Object.assign(App, saved); }
  });

  test('the form offers the points, the magnitude and the type', function () {
    /* Built against the real App.UI, so the row helper and the controls are the ones
       the dialog actually renders rather than doubles that agree with themselves. */
    var saved = { PROJECT: App.PROJECT, NORMAL_LOADS: App.NORMAL_LOADS,
                  Dialogs: App.Dialogs };
    var spec = null;
    App.PROJECT = section();
    App.NORMAL_LOADS = [];
    App.Dialogs = { open: function (s) { spec = s; return { close: function () {} }; } };
    try {
      App.NormalLoads.start();
      var body = document.createElement('div');
      spec.build(body);
      var labels = Array.prototype.map.call(
        body.querySelectorAll('.mesh-setting-label'),
        function (node) { return node.textContent; });
      ['Points', 'Type', 'Pressure', 'Active'].forEach(function (label) {
        T.ok(labels.indexOf(label) >= 0, label + ' is on the form');
      });
      T.eq(body.querySelectorAll('.line-point').length, 2, 'one row per point');
      var type = body.querySelector('select.mesh-setting-control');
      T.eq(Array.prototype.map.call(type.options, function (o) { return o.value; }),
           ['Uniform', 'Hydrostatic']);
      T.eq(type.value, 'Uniform', 'the mode that applies the magnitude asked for');
    } finally { Object.assign(App, saved); }
  });

  test('right-clicking the load and picking Properties opens the same form', function () {
    /* "Properties…" has been on the explorer's context menu since the mockup and did
       nothing for any kind: the callback handled delete, rename and the eye, and let
       every other label fall off the end. */
    var saved = { Menu: App.Menu, Viewport: App.Viewport, NormalLoads: App.NormalLoads,
                  Loads: App.Loads, Beams: App.Beams, Anchors: App.Anchors,
                  Interfaces: App.Interfaces };
    var edited = null, items = null, pick = null;
    App.Menu = { openAt: function (list, x, y, onPick) { items = list; pick = onPick; } };
    App.Viewport = { isVisible: function () { return true; } };
    App.Beams = { isBeamKey: function () { return false; } };
    App.Anchors = { isAnchorKey: function () { return false; } };
    App.Interfaces = { isInterfaceKey: function () { return false; } };
    App.Loads = { isLoadKey: function () { return false; } };
    App.NormalLoads = {
      isNormalLoadKey: function (key) { return key === 'normalload_1'; },
      edit: function (id) { edited = id; }
    };

    var row = document.createElement('div');
    row.className = 'tree-row';
    row.dataset.obj = 'normalload_1';
    try {
      App.LivePatches.onTreeContextMenu({
        target: row, clientX: 1, clientY: 2,
        preventDefault: function () {}, stopImmediatePropagation: function () {}
      });
      var properties = items.filter(function (item) {
        return item && /^Properties/.test(item.label || '');
      })[0];
      T.ok(properties, 'the menu offers it');
      pick(properties);
      T.eq(edited, 'normalload_1', 'and it opens the load form');
    } finally { Object.assign(App, saved); }
  });

  /* ── Drawn in the section ───────────────────────────────────────────── */

  test('a normal load is named in the modes a load is drawn in', function () {
    /* setMode() shows a key only if computeModeGroups named it, so one left out here
       is built, handed to the viewport, and then invisible in every mode whatever the
       eye says -- which is exactly what happened to the first cut of this feature. */
    var groups = App.Viewport.computeModeGroups(
      ['soil_L1'], [], false, ['load_1'], [], ['normalload_1']);
    T.ok(groups.structures.indexOf('normalload_1') >= 0, 'drawn in Structures');
    T.ok(groups.staged.indexOf('normalload_1') >= 0, 'drawn in Staged construction');
    T.eq(groups.soil.indexOf('normalload_1'), -1, 'not in Soil, like any other load');
  });

  test('a normal load is drawn with arrows along the line it loads', function () {
    /* The column case: a load along the top of a 0.1 x 1 m column, drawn left to
       right. A positive pressure pushes to the right of the walking direction, which
       here is straight down into the column. */
    var project = Object.assign(section(), {
      domain: { x0: 0, x1: 0.1, z0: 0, z1: 1, y_top: 1, y_bottom: 0 }
    });
    var spec = App.Viewport.normalLoadGlyphSpec(
      { id: 'normalload_1', points: [[0, 1], [0.1, 1]], pressure: 20,
        fluid_pressure_type: 'Uniform', active: true }, project);

    T.ok(spec.arrows.length >= 3, 'more than one arrow along the line');
    spec.arrows.forEach(function (arrow) {
      T.near(arrow.direction[0], 0, 1e-9);
      T.near(arrow.direction[1], -1, 1e-9, 'into the column, not out of it');
      T.near(arrow.tip[1], 1, 1e-9, 'standing on the loaded line');
    });
    T.eq(spec.outline, undefined, 'arrows only -- no line laid over the loaded face');
  });

  test('each segment of a bent line gets its own arrow direction', function () {
    /* Down an excavation face, then along its floor: one direction for the whole
       symbol would point the floor's arrows sideways. */
    var spec = App.Viewport.normalLoadGlyphSpec(
      { id: 'normalload_1', points: [[10, 0], [10, -5], [16, -5]], pressure: 20,
        fluid_pressure_type: 'Uniform', active: true }, section());

    var directions = spec.arrows.map(function (a) {
      return [Math.round(a.direction[0]), Math.round(a.direction[1])];
    });
    T.ok(directions.some(function (d) { return d[0] === -1 && d[1] === 0; }),
         'the vertical face is pushed sideways');
    T.ok(directions.some(function (d) { return d[0] === 0 && d[1] === -1; }),
         'the floor is pushed downwards');
  });

  /* The usual symbol of a spread load: the tails of the arrows joined by one straight
     line, parallel to the loaded segment, on a slope as well as on flat ground. */
  test('the tails of the arrows are joined by a straight line along each segment',
       function () {
    var slope = App.Viewport.normalLoadGlyphSpec(
      { id: 'normalload_1', points: [[0, 0], [8, -6]], pressure: 20,
        fluid_pressure_type: 'Uniform', active: true }, section());
    T.eq(slope.tails.length, 1, 'one line for one segment');
    var line = slope.tails[0];
    T.eq(line.length, 2, 'a straight line');
    [0, 2].forEach(function (k) {
      var arrow = slope.arrows[k];
      var tail = [arrow.tip[0] - arrow.direction[0] * slope.length,
                  arrow.tip[1] - arrow.direction[1] * slope.length];
      var end = line[k / 2];
      T.near(end[0], tail[0], 1e-9, 'the line starts and ends on an arrow tail');
      T.near(end[1], tail[1], 1e-9);
    });
    var middle = slope.arrows[1];
    var mx = middle.tip[0] - middle.direction[0] * slope.length;
    var my = middle.tip[1] - middle.direction[1] * slope.length;
    var cross = (line[1][0] - line[0][0]) * (my - line[0][1])
              - (line[1][1] - line[0][1]) * (mx - line[0][0]);
    T.near(cross, 0, 1e-9, 'the middle tail is on the line too');
  });

  test('a bent line has one tail line per segment, each ending on an arrow', function () {
    var spec = App.Viewport.normalLoadGlyphSpec(
      { id: 'normalload_1', points: [[10, 0], [10, -5], [16, -5]], pressure: 20,
        fluid_pressure_type: 'Uniform', active: true }, section());
    T.eq(spec.tails.length, 2);
    T.eq(spec.arrows.length, 6, 'the bend has an arrow for each segment');
    var straight = App.Viewport.normalLoadGlyphSpec(
      { id: 'normalload_1', points: [[0, 0], [5, 0], [10, 0]], pressure: 20,
        fluid_pressure_type: 'Uniform', active: true }, section());
    T.eq(straight.tails.length, 1, 'segments in line share one tail line');
    T.eq(straight.tails[0].length, 3);
    T.eq(straight.arrows.length, 5, 'and one arrow where they meet');
  });

  test('a uniform load is drawn whatever its magnitude, with arrows of one length',
       function () {
    /* The uniform one used to vanish when its pressure was nought, so the symbol read
       as the load itself coming and going. */
    [0, 20].forEach(function (pressure) {
      var spec = App.Viewport.normalLoadGlyphSpec(
        { id: 'normalload_1', points: [[10, 0], [10, -5], [16, -5]],
          pressure: pressure, fluid_pressure_type: 'Uniform', active: true }, section());
      T.ok(spec.arrows.length > 0, 'drawn at ' + pressure + ' kN/m²');
      spec.arrows.forEach(function (arrow) { T.near(arrow.length, spec.length, 1e-9); });
    });
  });

  /* A hydrostatic load is nought at its water level and grows with depth, and the
     symbol shows it: the arrows grow from nought at the level to the full length at
     the deepest point, so the line through their tails is slanted. */
  function wall(level) {
    return App.Viewport.normalLoadGlyphSpec(
      { id: 'water_1', points: [[10, 0], [10, -10]], pressure: 0,
        fluid_pressure_type: 'Hydrostatic', reference_coordinate: level,
        active: true }, section());
  }

  test('the arrows of a hydrostatic load grow with depth below its water level',
       function () {
    var spec = wall(0);
    T.ok(spec.arrows.length >= 5, 'enough arrows to show the growth');
    spec.arrows.forEach(function (arrow) {
      T.near(arrow.length, spec.length * -arrow.tip[1] / 10, 1e-9,
             'in proportion to the depth at y = ' + arrow.tip[1]);
    });
    var deepest = spec.arrows[spec.arrows.length - 1];
    T.near(deepest.length, spec.length, 1e-9, 'the full length at the deepest point');
    T.eq(spec.tails.length, 1);
    T.near(spec.tails[0][0][0], 10, 1e-9, 'the tail line starts on the wall, at the level');
    T.near(spec.tails[0][0][1], 0, 1e-9);
    T.near(Math.abs(spec.tails[0][1][0] - 10), spec.length, 1e-9,
           'and ends one full arrow off the wall at the bottom: a triangle');
  });

  test('a hydrostatic load is drawn under its water level only', function () {
    var spec = wall(-4);
    spec.arrows.forEach(function (arrow) {
      T.ok(arrow.tip[1] < -4, 'no arrow above the level: ' + arrow.tip[1]);
    });
    T.near(spec.tails[0][0][1], -4, 1e-9, 'the tail line starts at the level');
  });

  test('a hydrostatic load that is dry all along draws its line and no arrows',
       function () {
    var spec = wall(-20);
    T.eq(spec.arrows.length, 0);
    T.eq(spec.tails, [[[10, 0, 20], [10, -10, 20]]], 'so it still shows where it is');
  });

  test('a hydrostatic load with no level of its own reads the project water', function () {
    var spec = App.Viewport.normalLoadGlyphSpec(
      { id: 'water_1', points: [[10, 0], [10, -10]], pressure: 0,
        fluid_pressure_type: 'Hydrostatic', reference_coordinate: null, active: true },
      section());
    T.near(spec.tails[0][0][1], -3.5, 1e-9, 'the level of the section, y = -3.5');
  });

  test('a negative pressure turns the arrows round', function () {
    var spec = App.Viewport.normalLoadGlyphSpec(
      { id: 'normalload_1', points: [[0, 1], [0.1, 1]], pressure: -20,
        fluid_pressure_type: 'Uniform', active: true }, section());
    T.near(spec.arrows[0].direction[1], 1, 1e-9);
  });

  test('a drafted load carries no symbol geometry of its own', function () {
    /* The strip it used to carry stood proud of the model -- on a 0.1 x 1 m column a
       bar across the top of the loaded face. The arrows are the whole symbol now. */
    T.eq(App.NormalLoads.draft(section()).thickness, undefined);
  });

  test('the Normal loads explorer row toggles the loads under it', function () {
    var keys = App.Viewport.computeGroupKeys(
      ['soil_L1'], [], ['load_1'], [], [], [], ['normalload_1']);
    T.eq(keys['group:normal_loads'], ['normalload_1']);
    T.eq(keys['group:loads'], ['load_1'], 'and it is not doubled into the Loads row');
  });

  test('the form will not save a load with no magnitude given', function () {
    /* Blank on a new load rather than pre-filled with nought, so the pressure is
       something stated rather than something walked past -- and Number('') would
       read an empty box as a load of zero. */
    var saved = { Api: App.Api, PROJECT: App.PROJECT, NORMAL_LOADS: App.NORMAL_LOADS,
                  Dialogs: App.Dialogs };
    var spec = null, called = false;
    App.PROJECT = section();
    App.NORMAL_LOADS = [];
    App.Api = { patch: function () { called = true; return Promise.resolve({}); } };
    App.Dialogs = { open: function (s) { spec = s; return { close: function () {} }; } };
    try {
      App.NormalLoads.start();
      var body = document.createElement('div');
      spec.build(body);
      var pressure = body.querySelectorAll('input[type="number"]')[4];
      T.eq(pressure.value, '', 'nothing pre-filled to accept by accident');

      var save = spec.buttons.filter(function (b) { return b.label === 'Save'; })[0];
      save.onClick();
      T.eq(called, false, 'refused before any request');
      T.ok(/pressure/i.test(body.querySelector('.mesh-settings-message').textContent));
    } finally { Object.assign(App, saved); }
  });

  test('submitting the form saves what was typed into it', function () {
    var saved = { Api: App.Api, PROJECT: App.PROJECT, NORMAL_LOADS: App.NORMAL_LOADS,
                  Dialogs: App.Dialogs, Model: App.Model, Viewport: App.Viewport,
                  Command: App.Command, Explorer: App.Explorer,
                  selectObject: App.selectObject };
    var spec = null, sent = null, closed = false;
    App.PROJECT = section();
    App.NORMAL_LOADS = [];
    App.Dialogs = { open: function (s) { spec = s; return { close: function () { closed = true; } }; } };
    App.Api = { patch: function (path, body) {
      sent = body;
      return Promise.resolve({ project: section() });
    } };
    App.Model = { apply: function () {}, load: function () { return Promise.resolve(); } };
    App.Viewport = { refresh: function () { return Promise.resolve(); } };
    App.Command = { ok: function () {}, err: function () {}, note: function () {} };
    App.Explorer = null;
    App.selectObject = null;

    App.NormalLoads.start();
    var body = document.createElement('div');
    spec.build(body);
    var numbers = body.querySelectorAll('input[type="number"]');
    // x1, y1, x2, y2, then the pressure.
    [4, -1, 4, -9].forEach(function (value, i) { numbers[i].value = String(value); });
    body.querySelector('select.mesh-setting-control').value = 'Uniform';
    numbers[4].value = '32.5';

    var save = spec.buttons.filter(function (b) { return b.label === 'Save'; })[0];
    return Promise.resolve(save.onClick()).then(function () {
      var record = sent.normal_loads[0];
      T.eq(record.points, [[4, -1], [4, -9]]);
      T.eq(record.fluid_pressure_type, 'Uniform');
      T.eq(record.pressure, 32.5);
      T.eq(closed, true, 'the form closes once the save lands');
    }).then(function () { Object.assign(App, saved); },
            function (e) { Object.assign(App, saved); throw e; });
  });

  test('an invalid normal load is refused before any request is made', function () {
    var saved = { Api: App.Api, PROJECT: App.PROJECT, NORMAL_LOADS: App.NORMAL_LOADS };
    var called = false;
    App.PROJECT = section();
    App.NORMAL_LOADS = [];
    App.Api = { patch: function () { called = true; return Promise.resolve({}); } };
    var bad = { id: 'normalload_1', name: '', kind: 'normal',
               points: [[8, 0], [8, -5]], fluid_pressure_type: 'Hydrostatic',
               pressure: 0, active: true };
    return T.rejects(function () { return App.NormalLoads.save(bad); })
      .then(function () {
        T.eq(called, false);
        Object.assign(App, saved);
      }, function (e) { Object.assign(App, saved); throw e; });
  });
})();

/* Pick, edit and start, with the dialog and the drawing tool stood in. */
(function () {
  function project(dimension) {
    return {
      dimension: dimension, section_offset: 20,
      domain: { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 },
      materials: [], loads: [], beams: [], beam_sections: [],
      water: { y: -3.5, specific_weight: 10.0 },
      normal_loads: [{ id: 'normalload_1', name: 'Face', kind: 'normal',
                       points: [[10, 0], [10, -6]], fluid_pressure_type: 'Hydrostatic',
                       pressure: 0, active: true }]
    };
  }

  function rig(dimension) {
    var saved = { PROJECT: App.PROJECT, NORMAL_LOADS: App.NORMAL_LOADS, Dialogs: App.Dialogs,
                  DrawInput: App.DrawInput, Command: App.Command };
    var ctx = { opened: [], drawing: null, notes: [] };
    App.PROJECT = project(dimension);
    App.NORMAL_LOADS = App.PROJECT.normal_loads.slice();
    App.Dialogs = { open: function (config) {
      var body = document.createElement('div');
      config.build(body);
      ctx.opened.push({ config: config, body: body });
      return { close: function () {} };
    } };
    App.DrawInput = { start: function (mode, options) { ctx.drawing = { mode: mode, options: options }; } };
    App.Command = { note: function (t) { ctx.notes.push(t); }, ok: function () {}, err: function () {} };
    ctx.restore = function () { Object.assign(App, saved); };
    return ctx;
  }

  test('pick: the points picked on the model open the form at those points', function () {
    var ctx = rig(2);
    try {
      App.NormalLoads.pick();
      T.eq(ctx.drawing.mode, 'line', 'as many points as the user clicks, as a line');
      T.eq(ctx.drawing.options.count, undefined);
      ctx.drawing.options.onComplete([[4, 0, 0], [9, -3, 0]]);
      var inputs = ctx.opened[0].body.querySelectorAll('input');
      var values = Array.prototype.map.call(inputs, function (i) { return i.value; });
      T.ok(/Create normal load/.test(ctx.opened[0].config.title));
      T.ok(values.indexOf('4') >= 0 && values.indexOf('9') >= 0 && values.indexOf('-3') >= 0,
           'the picked x and y are in the form: ' + values.join(','));
    } finally { ctx.restore(); }
  });

  test("pick: the form's own Pick button starts picking", function () {
    var ctx = rig(2);
    try {
      App.NormalLoads.start();
      var pickButton = ctx.opened[0].config.buttons.filter(function (b) {
        return /Pick on model/.test(b.label); })[0];
      pickButton.onClick();
      T.eq(ctx.drawing && ctx.drawing.mode, 'line');
    } finally { ctx.restore(); }
  });

  test("pick: an existing load picked again keeps its name and its type", function () {
    var ctx = rig(2);
    try {
      App.NormalLoads.edit('normalload_1');
      ctx.opened[0].config.buttons.filter(function (b) {
        return /Pick on model/.test(b.label); })[0].onClick();
      ctx.drawing.options.onComplete([[0, -2, 0], [5, -2, 0], [5, 0, 0]]);
      var again = ctx.opened[1];
      T.ok(/Edit normal load/.test(again.config.title), 'still the load it was');
      T.eq(again.body.querySelector('input[type="text"]').value, 'Face');
      T.eq(again.body.querySelector('select').value, 'Hydrostatic');
      T.eq(again.body.querySelectorAll('.line-point').length, 3);
    } finally { ctx.restore(); }
  });

  test('edit: an existing load opens as Edit with its own pressure, an unknown id does nothing', function () {
    var ctx = rig(2);
    try {
      T.eq(App.NormalLoads.edit('normalload_9'), undefined);
      T.eq(ctx.opened.length, 0);
      App.NormalLoads.edit('normalload_1');
      T.ok(/Edit normal load/.test(ctx.opened[0].config.title));
      T.eq(ctx.opened[0].body.querySelector('select').value, 'Hydrostatic');
    } finally { ctx.restore(); }
  });

  test('start: in the solid model it says why and opens nothing', function () {
    var ctx = rig(3);
    try {
      T.eq(App.NormalLoads.start(), undefined);
      T.eq(ctx.opened.length, 0);
      T.ok(ctx.notes.length === 1);
    } finally { ctx.restore(); }
  });

  test('a normal load key is recognised, anything else is not', function () {
    var ctx = rig(2);
    try {
      T.ok(App.NormalLoads.isNormalLoadKey('normalload_1'));
      T.ok(!App.NormalLoads.isNormalLoadKey('load_1'));
    } finally { ctx.restore(); }
  });
})();
