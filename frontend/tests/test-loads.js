/* Structure-mode load authoring: one project contract for 2D lines and 3D pads. */

(function () {
  var SECTION = {
    dimension: 2, section_offset: 20,
    domain: { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 },
    loads: []
  };
  var SOLID = {
    dimension: 3,
    domain: { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 },
    loads: []
  };

  test('2D load capture creates a dimension-native line with no hidden z values', function () {
    var load = App.Loads.draftFromPoints(SECTION, [[9, 0, 20], [2, 0, 20]]);
    T.eq(load.kind, 'line');
    T.eq([load.x0, load.x1, load.y], [2, 9, 0]);
    T.eq(load.components, [0, -20000], '20 kN/m down, in the N/m of an SI project');
    T.eq('z' in load || 'z0' in load || 'z1' in load, false);
    T.eq(load.name, 'LineLoad_1');
  });

  test('a new load is stated in the units of its project', function () {
    var kn = Object.assign({}, SECTION, { unit_system: 'kN' });
    T.eq(App.Loads.draftFromPoints(kn, [[9, 0, 20], [2, 0, 20]]).components, [0, -20]);
    T.eq(App.Loads.draftPoint(kn, [8.5, -3]).components, [0, -20]);
  });

  test('3D load capture becomes the rectangle drawn on the ground surface', function () {
    var load = App.Loads.draftFromPoints(SOLID, [[12, 25, 0], [3, 7, 0]]);
    T.eq([load.x0, load.x1, load.z0, load.z1], [3, 12, 7, 25]);
    T.eq(load.name, 'SurfaceLoad_1');
  });

  test('a 2D point load draft accepts x and y with no hidden z value', function () {
    var load = App.Loads.draftPoint(SECTION, [8.5, -3]);
    T.eq(load.kind, 'point');
    T.eq([load.x, load.y], [8.5, -3]);
    T.eq(load.components, [0, -20000]);
    T.eq('z' in load, false);
    T.eq(load.name, 'PointLoad_1');
  });

  test('a surface-load coordinate draft starts inside the project domain', function () {
    var load = App.Loads.draftSurface(SOLID);
    T.eq(load.kind, 'surface');
    T.ok(load.x0 >= SOLID.domain.x0 && load.x1 <= SOLID.domain.x1);
    T.ok(load.z0 >= SOLID.domain.z0 && load.z1 <= SOLID.domain.z1);
  });

  test('load kinds are constrained by model dimension', function () {
    T.eq(App.Loads.available('point', SECTION), true);
    T.eq(App.Loads.available('line', SECTION), true);
    T.eq(App.Loads.available('surface', SECTION), false);
    T.eq(App.Loads.available('point', SOLID), false);
    T.eq(App.Loads.available('line', SOLID), false);
    T.eq(App.Loads.available('surface', SOLID), true);
  });

  test('an unavailable load kind is refused before opening its editor', function () {
    var saved = { project: App.PROJECT, dialogs: App.Dialogs, command: App.Command };
    var opened = 0, notes = [];
    App.PROJECT = SECTION;
    App.Dialogs = { open: function () { opened += 1; } };
    App.Command = { note: function (message) { notes.push(message); } };
    App.Loads.start('surface');
    App.PROJECT = saved.project; App.Dialogs = saved.dialogs; App.Command = saved.command;
    T.eq(opened, 0);
    T.ok(/3D/.test(notes[0] || ''));
  });

  test('load creation opens the coordinate editor without requiring canvas picks', function () {
    var saved = { project: App.PROJECT, dialogs: App.Dialogs, draw: App.DrawInput };
    var titles = [], buttonLabels = [], drawStarts = 0;
    App.PROJECT = SECTION;
    App.Dialogs = { open: function (options) {
      titles.push(options.title);
      buttonLabels.push(options.buttons.map(function (button) { return button.label; }));
      return { close: function () {} };
    } };
    App.DrawInput = { start: function () { drawStarts += 1; } };
    App.Loads.start('point');
    App.Loads.start('line');
    App.PROJECT = SOLID;
    App.Loads.start('surface');
    App.PROJECT = saved.project; App.Dialogs = saved.dialogs; App.DrawInput = saved.draw;
    T.eq(titles, ['Create point load', 'Create line load', 'Create surface load']);
    T.eq(buttonLabels[0], ['Pick on model…', 'Save', 'Cancel']);
    T.eq(drawStarts, 0);
  });

  test('2D loads are available in the section and surface loads are not', function () {
    T.eq(App.Loads.available('line', SECTION), true);
    T.eq(App.Loads.available('point', SECTION), true);
    T.eq(App.Loads.available('surface', SECTION), false);
    T.eq(App.Loads.available('surface', SOLID), true);
    T.eq(App.Loads.available('line', SOLID), false);
  });

  /* ── The surface-load editor's elevation field ────────────────────
     A pad is placed by x/z in plan and y in elevation, and y is what says which face
     it loads. The dialog offered only the plan extents, so a pad could be read out of
     the Selection explorer at y = 5 with no way to move it from the form it was
     authored in. y is optional server-side (SurfaceLoad.y): null means "the top of
     the model", so the field has to round-trip blank as blank -- Number('') is 0,
     which would silently drop the pad to datum. */

  function openDialog(load) {
    var saved = { PROJECT: App.PROJECT, Dialogs: App.Dialogs, LOADS: App.LOADS };
    var captured = null;
    App.PROJECT = SOLID;
    App.LOADS = [];
    App.Dialogs = { open: function (options) {
      captured = options;
      captured.form = document.createElement('div');
      options.build(captured.form);
      return { close: function () { captured.closed = true; } };
    } };
    try { App.Loads.open(load); } finally { Object.assign(App, saved); }
    return captured;
  }

  function fieldNamed(dialog, label) {
    var kids = Array.prototype.slice.call(dialog.form.firstChild.children);
    for (var i = 0; i < kids.length; i += 1) {
      if (kids[i].textContent === label && kids[i].tagName === 'LABEL') return kids[i + 1];
    }
    return null;
  }

  var PAD = { id: 'surfaceload_1', name: 'SurfaceLoad_1', kind: 'surface',
              x0: 8, x1: 12, z0: 0, z1: 20, thickness: 0.15,
              components: [0, -20, 0], distribution: 'Uniform', active: true };

  test('the surface-load editor offers the elevation the pad lies at', function () {
    var field = fieldNamed(openDialog(Object.assign({}, PAD, { y: 5 })), 'y');
    T.ok(field, 'the form gives no way to move the pad in elevation');
    T.eq(field.value, '5');
  });

  test('the editor reads x, then y, then z, like the Selection explorer does', function () {
    var dialog = openDialog(Object.assign({}, PAD, { y: 5 }));
    var labels = Array.prototype.slice.call(dialog.form.firstChild.children)
      .filter(function (node) { return node.tagName === 'LABEL'; })
      .map(function (node) { return node.textContent; });
    T.eq(labels.slice(1, 6), ['x min', 'x max', 'y', 'z min', 'z max']);
  });

  test('a pad with no elevation opens with the field blank', function () {
    var field = fieldNamed(openDialog(Object.assign({}, PAD, { y: null })), 'y');
    T.ok(field, 'the row should be there either way');
    T.eq(field.value, '', 'a blank field reads as "the top of the model"');
  });

  test('saving an untouched blank elevation keeps it blank, not zero', function () {
    var sent = null;
    var saved = { Api: App.Api, PROJECT: App.PROJECT, Dialogs: App.Dialogs,
                  LOADS: App.LOADS, Model: App.Model, Viewport: App.Viewport,
                  Command: App.Command, Explorer: App.Explorer,
                  selectObject: App.selectObject };
    App.Api = { patch: function (path, body) {
      sent = body;
      return Promise.resolve({ project: SOLID });
    } };
    App.Model = { apply: function () {}, load: function () { return Promise.resolve(); } };
    App.Viewport = { refresh: function () { return Promise.resolve(); } };
    App.Command = { ok: function () {}, err: function () {}, note: function () {} };
    App.Explorer = null; App.selectObject = null;

    try {
      var dialog = openDialog(Object.assign({}, PAD, { y: null }));
      dialog.buttons.filter(function (b) { return b.label === 'Save'; })[0].onClick();
    } finally { Object.assign(App, saved); }
    T.ok(sent, 'the save never reached the server');
    T.eq(sent.loads[0].y, null, 'a blank field must not become a pad at y = 0');
  });

  test('an edited elevation is what gets saved', function () {
    var sent = null;
    var saved = { Api: App.Api, PROJECT: App.PROJECT, Dialogs: App.Dialogs,
                  LOADS: App.LOADS, Model: App.Model, Viewport: App.Viewport,
                  Command: App.Command, Explorer: App.Explorer,
                  selectObject: App.selectObject };
    App.Api = { patch: function (path, body) {
      sent = body;
      return Promise.resolve({ project: SOLID });
    } };
    App.Model = { apply: function () {}, load: function () { return Promise.resolve(); } };
    App.Viewport = { refresh: function () { return Promise.resolve(); } };
    App.Command = { ok: function () {}, err: function () {}, note: function () {} };
    App.Explorer = null; App.selectObject = null;

    try {
      var dialog = openDialog(Object.assign({}, PAD, { y: 5 }));
      var field = fieldNamed(dialog, 'y');
      T.ok(field, 'the form has no elevation field to edit');
      field.value = '2.5';
      dialog.buttons.filter(function (b) { return b.label === 'Save'; })[0].onClick();
    } finally { Object.assign(App, saved); }
    T.eq(sent.loads[0].y, 2.5);
  });

  test('load capture refuses a zero-width line or surface', function () {
    var error = null;
    try { App.Loads.draftFromPoints(SECTION, [[4, 0, 20], [4, 0, 20]]); }
    catch (caught) { error = caught; }
    T.ok(error && /width/.test(error.message));
  });

  test('saving a load patches structures, adopts the project, refreshes and selects it', function () {
    var saved = {
      loads: App.LOADS, project: App.PROJECT, api: App.Api, model: App.Model,
      viewport: App.Viewport, explorer: App.Explorer, select: App.selectObject
    };
    var calls = [], selected = null;
    var load = App.Loads.draftFromPoints(SECTION, [[2, 20, 0], [9, 20, 0]]);
    App.LOADS = [];
    App.PROJECT = SECTION;
    App.Api = { patch: function (path, body) {
      calls.push([path, body]);
      return Promise.resolve({ project: Object.assign({}, SECTION, { loads: body.loads }) });
    } };
    App.Model = { apply: function (project) { calls.push(['apply', project]); App.PROJECT = project; } };
    App.Viewport = { refresh: function () { calls.push(['refresh']); return Promise.resolve(); } };
    App.Explorer = { mountTree: function () { calls.push(['tree']); } };
    App.state = App.state || {}; App.state.mode = 'structures';
    App.selectObject = function (key) { selected = key; };

    return App.Loads.save(load).then(function () {
      T.eq(calls[0][0], '/api/project/structures');
      T.eq(calls[0][1].loads[0].id, 'load_1');
      T.ok(calls.some(function (call) { return call[0] === 'refresh'; }));
      T.eq(selected, 'load_1');
    }).then(restore, function (error) { restore(); throw error; });

    function restore() {
      App.LOADS = saved.loads; App.PROJECT = saved.project; App.Api = saved.api;
      App.Model = saved.model; App.Viewport = saved.viewport; App.Explorer = saved.explorer;
      App.selectObject = saved.select;
    }
  });

  test('saving a 2D load preserves an incompatible saved 3D surface load', function () {
    var saved = {
      loads: App.LOADS, project: App.PROJECT, api: App.Api, model: App.Model,
      viewport: App.Viewport, explorer: App.Explorer, select: App.selectObject
    };
    var surface = App.Loads.draftFromPoints(SOLID, [[12, 25, 0], [3, 7, 0]]);
    var project = Object.assign({}, SECTION, { loads: [surface] });
    var line = App.Loads.draftFromPoints(project, [[2, 20, 0], [9, 20, 0]]);
    var submitted = null;
    App.LOADS = [];
    App.PROJECT = project;
    App.Api = { patch: function (_, body) {
      submitted = body.loads;
      return Promise.resolve({ project: Object.assign({}, project, { loads: body.loads }) });
    } };
    App.Model = { apply: function (response) { App.PROJECT = response; } };
    App.Viewport = { refresh: function () { return Promise.resolve(); } };
    App.Explorer = { mountTree: function () {} };
    App.selectObject = function () {};

    return App.Loads.save(line).then(function () {
      T.eq(submitted.map(function (load) { return load.kind; }), ['surface', 'line']);
      restore();
    }, function (error) { restore(); throw error; });

    function restore() {
      App.LOADS = saved.loads; App.PROJECT = saved.project; App.Api = saved.api;
      App.Model = saved.model; App.Viewport = saved.viewport; App.Explorer = saved.explorer;
      App.selectObject = saved.select;
    }
  });

  test('a refused load edit reloads the stored project before reporting failure', function () {
    var saved = {
      loads: App.LOADS, project: App.PROJECT, api: App.Api, model: App.Model,
      viewport: App.Viewport, command: App.Command
    };
    var calls = [];
    var load = App.Loads.draftFromPoints(SECTION, [[2, 20, 0], [9, 20, 0]]);
    App.LOADS = [load]; App.PROJECT = SECTION;
    App.Api = { patch: function () { return Promise.reject(new Error('rejected')); } };
    App.Model = { load: function () { calls.push('load'); return Promise.resolve(); } };
    App.Viewport = { refresh: function () { calls.push('refresh'); return Promise.resolve(); } };
    App.Command = { err: function () {} };

    return App.Loads.save(load).then(function () {
      restore(); throw new Error('save should reject');
    }, function () {
      restore();
      T.eq(calls, ['load', 'refresh']);
    });

    function restore() {
      App.LOADS = saved.loads; App.PROJECT = saved.project; App.Api = saved.api;
      App.Model = saved.model; App.Viewport = saved.viewport; App.Command = saved.command;
    }
  });

  test('the load draw mode returns two coordinates without creating generic geometry', function () {
    var savedViewport = App.Viewport, savedFetch = window.fetch;
    var canvas = document.createElement('canvas'), captured = null, fetched = false;
    App.Viewport = {
      getCanvas: function () { return canvas; }, getScene: function () { return { add: function () {}, remove: function () {} }; },
      getCamera: function () { return {}; }, resize: function () {}
    };
    window.fetch = function () { fetched = true; return Promise.reject(new Error('unexpected fetch')); };
    App.DrawInput.start('load', { onComplete: function (points) { captured = points; } });
    App.DrawInput.handleCommand('2 20 0');
    App.DrawInput.handleCommand('9 20 0');
    T.eq(captured, [[2, 20, 0], [9, 20, 0]]);
    T.eq(fetched, false);
    App.Viewport = savedViewport; window.fetch = savedFetch;
  });

  test('optional point-load picking completes after one coordinate', function () {
    var savedViewport = App.Viewport;
    var canvas = document.createElement('canvas'), captured = null;
    App.Viewport = {
      getCanvas: function () { return canvas; },
      getScene: function () { return { add: function () {}, remove: function () {} }; },
      getCamera: function () { return {}; }, resize: function () {}
    };
    App.DrawInput.start('load', {
      count: 1, onComplete: function (points) { captured = points; }
    });
    App.DrawInput.handleCommand('8 12 -3');
    App.Viewport = savedViewport;
    T.eq(captured, [[8, 12, -3]]);
  });

  test('the Structures toolbar exposes the real load action for 2D and 3D', function () {
    var tool = (App.RAILS.structures || []).filter(function (item) {
      return item && item.icon === 'load';
    })[0];
    T.ok(tool, 'load tool exists');
    T.eq(tool.action, 'createLoad');
    var vectorKinds = tool.flyout.filter(function (item) {
      return item.action === 'createLoad';
    });
    T.eq(vectorKinds.map(function (item) { return item.loadKind; }),
         ['point', 'line', 'surface']);
  });

  test('the load flyout offers the normal load beside the three vector kinds', function () {
    /* A pressure on a polyline is not something App.Loads makes, but it is still a
       load as far as anyone looking for one is concerned, so it shares this flyout
       and carries its own action through to App.NormalLoads. */
    var tool = (App.RAILS.structures || []).filter(function (item) {
      return item && item.icon === 'load';
    })[0];
    var normal = tool.flyout.filter(function (item) {
      return item.action === 'createNormalLoad';
    });
    T.eq(normal.length, 1, 'exactly one, however many times the patch runs');
    T.eq(normal[0].loadKind, undefined, 'it is not one of the three vector kinds');
  });

  test('the load flyout enables point and line in 2D, and only surface in 3D', function () {
    var tool = (App.RAILS.structures || []).filter(function (item) {
      return item && item.icon === 'load';
    })[0];
    function disabledByAction() {
      var out = {};
      tool.flyout.forEach(function (item) {
        out[item.loadKind || item.action] = !!item.disabled;
      });
      return out;
    }
    App.LivePatches.syncDimensionAvailability(true);
    T.eq(disabledByAction(), { point: false, line: false, surface: true,
                               createNormalLoad: false });
    App.LivePatches.syncDimensionAvailability(false);
    T.eq(disabledByAction(), { point: true, line: true, surface: false,
                               createNormalLoad: true });
  });

  test('the Structures menu invokes load creation directly', function () {
    var menu = (App.MENUS || []).filter(function (item) { return item.label === 'Structures'; })[0];
    var item = (menu.items || []).filter(function (entry) { return entry && entry.label === 'Create load'; })[0];
    T.eq(item.action, 'createLoad');
    T.eq(item.sub, false);
  });

  test('named loads are visible in the Structures and Staged modes', function () {
    var groups = App.Viewport.computeModeGroups(
      ['soil_L1'], [], false, ['load_wind', 'load_surcharge']
    );
    ['structures', 'staged'].forEach(function (mode) {
      T.ok(groups[mode].indexOf('load_wind') >= 0);
      T.ok(groups[mode].indexOf('load_surcharge') >= 0);
    });
  });

  test('a point load uses one standard force arrow ending at its coordinate', function () {
    var load = App.Loads.draftPoint(SECTION, [8, -3]);
    load.components = [0, -100];
    var spec = App.Viewport.loadGlyphSpec(load, SECTION);
    T.eq(spec.anchors, [[8, -3, 20]]);
    T.eq(spec.direction, [0, -1, 0]);
    T.eq(spec.kind, 'point');
  });

  test('a 2D line load is indicated by repeated arrows along the loaded interval', function () {
    var load = App.Loads.draftFromPoints(SECTION, [[4, 0, 20], [14, 0, 20]]);
    var spec = App.Viewport.loadGlyphSpec(load, SECTION);
    T.eq(spec.kind, 'line');
    T.eq(spec.anchors.length, 5);
    T.eq(spec.anchors[0], [4, 0, 20]);
    T.eq(spec.anchors[4], [14, 0, 20]);
  });

  test('a 2D line load joins the tails of its arrows with a straight line', function () {
    /* The usual symbol: the line stands where the arrows start, off the loaded face,
       and stays straight when the load pushes at an angle. */
    var load = App.Loads.draftFromPoints(SECTION, [[4, 0, 20], [14, 0, 20]]);
    load.components = [3, -4];
    var spec = App.Viewport.loadGlyphSpec(load, SECTION);
    T.eq(spec.tails.length, 1);
    var line = spec.tails[0];
    T.eq(line.length, 2);
    [[0, 0], [1, 4]].forEach(function (pair) {
      var anchor = spec.anchors[pair[1]];
      T.near(line[pair[0]][0], anchor[0] - 0.6 * spec.length, 1e-9);
      T.near(line[pair[0]][1], anchor[1] + 0.8 * spec.length, 1e-9);
    });
  });

  test('a 3D surface load is indicated by an arrow grid over its footprint', function () {
    var load = App.Loads.draftFromPoints(SOLID, [[3, 7, 0], [12, 25, 0]]);
    var spec = App.Viewport.loadGlyphSpec(load, SOLID);
    T.eq(spec.kind, 'surface');
    T.eq(spec.anchors.length, 9);
    T.ok(spec.anchors.every(function (point) {
      return point[0] >= 3 && point[0] <= 12 && point[2] >= 7 && point[2] <= 25 && point[1] === 0;
    }));
  });

  test('load glyphs carry the load key so their arrowheads select the load', function () {
    var load = App.Loads.draftPoint(SECTION, [8, -3]);
    var group = App.Viewport.loadGlyphGroup(load, SECTION);
    var selectable = [];
    group.traverse(function (object) {
      if (object.isMesh && object.userData.key === load.id) selectable.push(object);
    });
    T.ok(selectable.length >= 1);
  });

  /* ── Sized against the model ──────────────────────────────────────
     The arrow used to have a 0.75 m floor, so on a 0.1 x 1 m column it was three
     quarters as tall as the model it was drawn on. Nothing about a load symbol has
     a length in metres of its own: it is a fraction of what is on screen. */

  var COLUMN = {
    dimension: 2, section_offset: 0.5,
    domain: { x0: 0, x1: 0.1, z0: 0, z1: 1, y_top: 0, y_bottom: -1 },
    loads: []
  };

  test('the arrow is a fraction of the model, however small the model is', function () {
    var load = App.Loads.draftPoint(COLUMN, [0.05, 0]);
    var length = App.Viewport.loadGlyphSpec(load, COLUMN).length;
    T.ok(length > 0 && length < 0.2,
         'an arrow on a 1 m column must not be 0.75 m long: ' + length);
    T.near(length / 1, App.Viewport.loadGlyphSpec(
      App.Loads.draftPoint(SECTION, [8, -3]), SECTION).length / 50, 1e-9,
      'the same fraction of the model at either scale');
  });

  test('the arrow keeps the size it had on the demo domain', function () {
    var load = App.Loads.draftPoint(SECTION, [8, -3]);
    T.near(App.Viewport.loadGlyphSpec(load, SECTION).length, 4, 1e-9);
  });

  /* The domain is what was declared, not what is on screen: a 0.1 x 1 m column
     drawn inside the default 20 m block is still a 1 m model, and the arrow has to
     be a fraction of the column. The viewport's own frame is what it frames. */

  test('the span is taken from the framed model when there is one', function () {
    var wide = Object.assign({}, COLUMN, {
      domain: { x0: -10, x1: 10, z0: 0, z1: 20, y_top: 10, y_bottom: -10 }
    });
    T.near(App.Viewport.modelSpan(wide, [0.1, 1, 1]), 1, 1e-9,
           'the column, not the 20 m block it was drawn in');
    T.near(App.Viewport.modelSpan(wide, null), 20, 1e-9,
           'with nothing framed yet, the domain is all there is to go on');
  });

  test('a 2D section is sized by what is on screen, not the out-of-plane thickness', function () {
    // 40 m of thickness behind the section is edge-on: it cannot make the arrow
    // drawn on a 1 m column 3 m long. Out of plane is z, so that is size[2].
    T.near(App.Viewport.modelSpan(COLUMN, [0.1, 1, 40]), 1, 1e-9);
    T.near(App.Viewport.modelSpan({ dimension: 3, domain: COLUMN.domain }, [0.1, 1, 40]),
           40, 1e-9, 'in 3D every axis is on screen');
  });

  test('the arrowhead and the point marker scale with the shaft', function () {
    var load = App.Loads.draftPoint(COLUMN, [0.05, 0]);
    var spec = App.Viewport.loadGlyphSpec(load, COLUMN);
    var group = App.Viewport.loadGlyphGroup(load, COLUMN);
    var sizes = [];
    group.traverse(function (object) {
      if (object.geometry && object.geometry.parameters
          && object.geometry.parameters.radius !== undefined) {
        sizes.push(object.geometry.parameters.radius);
      }
    });
    T.ok(sizes.length > 0, 'the cone head and the sphere marker are both radii');
    T.ok(sizes.every(function (r) { return r < spec.length; }),
         'nothing on the glyph is wider than the glyph is long: ' + sizes.join(', '));
  });
  /* ── Standing on a drawn layer ────────────────────────────────────
     `Domain` is the block the layers fill; an embankment drawn on top of it
     reaches above `y_top`. A load placed there is on model geometry, and refusing it
     as "outside the model domain" is the bug App.Model.extentOf fixes -- it mirrors
     the server's `Project.extent`. */

  var EMBANKMENT = { key: 'drawn_1', label: 'Embankment', source: 'gui',
                     bbox: [0, 0, 0, 50, 4, 40] };

  test('a point load on a drawn layer above ground is accepted', function () {
    var project = Object.assign({}, SECTION, { custom_parts: [EMBANKMENT] });
    var load = App.Loads.draftPoint(project, [10, 2]);
    T.eq(load.y, 2);
  });

  test('a point load above everything in the model is still refused', function () {
    var project = Object.assign({}, SECTION, { custom_parts: [EMBANKMENT] });
    var error = null;
    try { App.Loads.draftPoint(project, [10, 9]); } catch (e) { error = e; }
    T.ok(error, 'the check is relaxed, not removed');
  });

  test('with no drawn parts the domain is still the limit', function () {
    var error = null;
    try { App.Loads.draftPoint(SECTION, [10, 2]); } catch (e) { error = e; }
    T.ok(error, 'nothing sticks out, so y_top still applies');
  });

  test('a line load drawn over a raised layer sits on top of it', function () {
    /* Its level has to match the server's `Project.ground_y` or the switch to 3D
       will not translate it into a surface load -- the regression this pins down. */
    var project = Object.assign({}, SECTION, { custom_parts: [EMBANKMENT] });
    var load = App.Loads.draftFromPoints(project, [[9, 0, 20], [2, 0, 20]]);
    T.eq(load.y, 4);
  });

  test('a 3D surface load records the elevation it was drawn at', function () {
    /* The server places the pad from this (`Project.elevation_of`); leaving it out
       makes it fall back to a bounding box padded by 1e-7. */
    var project = Object.assign({}, SOLID, { custom_parts: [EMBANKMENT] });
    var load = App.Loads.draftFromPoints(project, [[12, 25, 0], [3, 7, 0]]);
    T.eq(load.y, 4);
  });

  /* ── Where the arrows are drawn ───────────────────────────────────
     The glyph is the load, as far as the user is concerned. Its 3D branch anchored
     every arrow at `domain.y_top` -- the top of the *layer* block -- so a load put
     on an embankment in 2D jumped down onto the layer soil on the switch to 3D,
     while the 2D branch had used `load.y` all along. Mirrors the server's
     `Project.elevation_of`. */

  var RAISED_SOLID = { dimension: 3,
    domain: { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 },
    custom_parts: [EMBANKMENT], loads: [] };

  function surfaceLoad(y) {
    return { id: 'load_1', name: 'SurfaceLoad_1', kind: 'surface',
             x0: 4, x1: 16, z0: 5, z1: 10, y: y, thickness: 0.15,
             components: [0, -20, 0], distribution: 'Uniform', active: true };
  }

  test('a 3D surface load draws its arrows at its own elevation', function () {
    var spec = App.Viewport.loadGlyphSpec(surfaceLoad(4), RAISED_SOLID);
    T.ok(spec.anchors.length, 'the glyph has anchors');
    T.eq(spec.anchors.every(function (a) { return a[1] === 4; }), true,
         'every arrow sits on the embankment, not on the layer soil: '
         + JSON.stringify(spec.anchors.map(function (a) { return a[1]; })));
  });

  test('a surface load with no elevation falls back to the top of the model', function () {
    var spec = App.Viewport.loadGlyphSpec(surfaceLoad(null), RAISED_SOLID);
    T.eq(spec.anchors.every(function (a) { return a[1] === 4; }), true,
         'older records still mean the model top, which the embankment raised');
  });

  test('with nothing drawn the model top is still the domain top', function () {
    var plain = Object.assign({}, RAISED_SOLID, { custom_parts: [] });
    var spec = App.Viewport.loadGlyphSpec(surfaceLoad(null), plain);
    T.eq(spec.anchors.every(function (a) { return a[1] === 0; }), true);
  });

  test('the surface load outline joins the tails of the arrows on its pad', function () {
    /* The pad outline had its own copy of `domain.y_top`, so fixing only the arrows
       would have left the rectangle behind on the layer soil. It is drawn through the
       arrows' tails: one arrow length above the pad, for a load pushing down. */
    var length = App.Viewport.loadGlyphSpec(surfaceLoad(4), RAISED_SOLID).length;
    var group = App.Viewport.loadGlyphGroup(surfaceLoad(4), RAISED_SOLID);
    var outline = null;
    group.traverse(function (object) {
      if (object.geometry && object.geometry.attributes
          && object.type === 'Line' && object.userData.noPick) outline = object;
    });
    T.ok(outline, 'the pad has an outline');
    var xyz = outline.geometry.attributes.position.array;
    var levels = [];
    for (var i = 1; i < xyz.length; i += 3) levels.push(xyz[i]);
    T.eq(levels.every(function (v) { return Math.abs(v - (4 + length)) < 1e-6; }), true,
         'outline levels: ' + JSON.stringify(levels));
  });

})();
