/* Structure-mode load authoring: one project contract for 2D lines and 3D pads. */

(function () {
  var SECTION = {
    dimension: 2, section_plane: 'xz', section_offset: 20,
    domain: { x0: 0, x1: 50, y0: 0, y1: 40, z_top: 0, z_bottom: -25 },
    loads: []
  };
  var SOLID = {
    dimension: 3,
    domain: { x0: 0, x1: 50, y0: 0, y1: 40, z_top: 0, z_bottom: -25 },
    loads: []
  };

  test('2D load capture creates a dimension-native line with no hidden y values', function () {
    var load = App.Loads.draftFromPoints(SECTION, [[9, 20, 0], [2, 20, 0]]);
    T.eq(load.kind, 'line');
    T.eq([load.x0, load.x1, load.z], [2, 9, 0]);
    T.eq(load.components, [0, -20]);
    T.eq('y' in load || 'y0' in load || 'y1' in load, false);
    T.eq(load.name, 'LineLoad_1');
  });

  test('3D load capture becomes the rectangle drawn on the ground surface', function () {
    var load = App.Loads.draftFromPoints(SOLID, [[12, 25, 0], [3, 7, 0]]);
    T.eq([load.x0, load.x1, load.y0, load.y1], [3, 12, 7, 25]);
    T.eq(load.name, 'SurfaceLoad_1');
  });

  test('a 2D point load draft accepts x and z with no hidden y value', function () {
    var load = App.Loads.draftPoint(SECTION, [8.5, -3]);
    T.eq(load.kind, 'point');
    T.eq([load.x, load.z], [8.5, -3]);
    T.eq(load.components, [0, -20]);
    T.eq('y' in load, false);
    T.eq(load.name, 'PointLoad_1');
  });

  test('a surface-load coordinate draft starts inside the project domain', function () {
    var load = App.Loads.draftSurface(SOLID);
    T.eq(load.kind, 'surface');
    T.ok(load.x0 >= SOLID.domain.x0 && load.x1 <= SOLID.domain.x1);
    T.ok(load.y0 >= SOLID.domain.y0 && load.y1 <= SOLID.domain.y1);
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

  test('2D loads are authored only in the x-z structural section', function () {
    var section = Object.assign({}, SECTION, { section_plane: 'yz' });
    var error = null;
    try { App.Loads.draftFromPoints(section, [[20, 18, 0], [20, 6, 0]]); }
    catch (caught) { error = caught; }
    T.ok(error && /x-z/.test(error.message));
  });

  test('load capture refuses a zero-width line or surface', function () {
    var error = null;
    try { App.Loads.draftFromPoints(SECTION, [[4, 20, 0], [4, 20, 0]]); }
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
    T.ok(tool.flyout.every(function (item) { return item.action === 'createLoad'; }));
    T.eq(tool.flyout.map(function (item) { return item.loadKind; }), ['point', 'line', 'surface']);
  });

  test('the load flyout enables point and line in 2D, and only surface in 3D', function () {
    var tool = (App.RAILS.structures || []).filter(function (item) {
      return item && item.icon === 'load';
    })[0];
    App.LivePatches.syncDimensionAvailability(true);
    T.eq(tool.flyout.map(function (item) { return !!item.disabled; }), [false, false, true]);
    App.LivePatches.syncDimensionAvailability(false);
    T.eq(tool.flyout.map(function (item) { return !!item.disabled; }), [true, true, false]);
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
    T.eq(spec.anchors, [[8, 20, -3]]);
    T.eq(spec.direction, [0, 0, -1]);
    T.eq(spec.kind, 'point');
  });

  test('a 2D line load is indicated by repeated arrows along the loaded interval', function () {
    var load = App.Loads.draftFromPoints(SECTION, [[4, 20, 0], [14, 20, 0]]);
    var spec = App.Viewport.loadGlyphSpec(load, SECTION);
    T.eq(spec.kind, 'line');
    T.eq(spec.anchors.length, 5);
    T.eq(spec.anchors[0], [4, 20, 0]);
    T.eq(spec.anchors[4], [14, 20, 0]);
  });

  test('a 3D surface load is indicated by an arrow grid over its footprint', function () {
    var load = App.Loads.draftFromPoints(SOLID, [[3, 7, 0], [12, 25, 0]]);
    var spec = App.Viewport.loadGlyphSpec(load, SOLID);
    T.eq(spec.kind, 'surface');
    T.eq(spec.anchors.length, 9);
    T.ok(spec.anchors.every(function (point) {
      return point[0] >= 3 && point[0] <= 12 && point[1] >= 7 && point[1] <= 25 && point[2] === 0;
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
})();
