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

  /* ── Sized against the model ──────────────────────────────────────
     The arrow used to have a 0.75 m floor, so on a 0.1 x 1 m column it was three
     quarters as tall as the model it was drawn on. Nothing about a load symbol has
     a length in metres of its own: it is a fraction of what is on screen. */

  var COLUMN = {
    dimension: 2, section_plane: 'xz', section_offset: 0.5,
    domain: { x0: 0, x1: 0.1, y0: 0, y1: 1, z_top: 0, z_bottom: -1 },
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
      domain: { x0: -10, x1: 10, y0: 0, y1: 20, z_top: 10, z_bottom: -10 }
    });
    T.near(App.Viewport.modelSpan(wide, [0.1, 1, 1]), 1, 1e-9,
           'the column, not the 20 m block it was drawn in');
    T.near(App.Viewport.modelSpan(wide, null), 20, 1e-9,
           'with nothing framed yet, the domain is all there is to go on');
  });

  test('a 2D section is sized by what is on screen, not the out-of-plane thickness', function () {
    // 40 m of thickness behind the section is edge-on: it cannot make the arrow
    // drawn on a 1 m column 3 m long.
    T.near(App.Viewport.modelSpan(COLUMN, [0.1, 40, 1]), 1, 1e-9);
    T.near(App.Viewport.modelSpan({ dimension: 3, domain: COLUMN.domain }, [0.1, 40, 1]),
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
     `Domain` is the block the boreholes describe; an embankment drawn on top of it
     reaches above `z_top`. A load placed there is on model geometry, and refusing it
     as "outside the model domain" is the bug App.Model.extentOf fixes -- it mirrors
     the server's `Project.extent`. */

  var EMBANKMENT = { key: 'drawn_1', label: 'Embankment', source: 'gui',
                     bbox: [0, 0, 0, 50, 40, 4] };

  test('a point load on a drawn layer above ground is accepted', function () {
    var project = Object.assign({}, SECTION, { custom_parts: [EMBANKMENT] });
    var load = App.Loads.draftPoint(project, [10, 2]);
    T.eq(load.z, 2);
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
    T.ok(error, 'nothing sticks out, so z_top still applies');
  });

  test('a line load drawn over a raised layer sits on top of it', function () {
    /* Its z has to match the server's `Project.ground_z` or the switch to 3D will not
       translate it into a surface load -- the regression this pins down. */
    var project = Object.assign({}, SECTION, { custom_parts: [EMBANKMENT] });
    var load = App.Loads.draftFromPoints(project, [[9, 20, 0], [2, 20, 0]]);
    T.eq(load.z, 4);
  });

  test('a 3D surface load records the elevation it was drawn at', function () {
    /* The server places the pad from this (`Project.elevation_of`); leaving it out
       makes it fall back to a bounding box padded by 1e-7. */
    var project = Object.assign({}, SOLID, { custom_parts: [EMBANKMENT] });
    var load = App.Loads.draftFromPoints(project, [[12, 25, 0], [3, 7, 0]]);
    T.eq(load.z, 4);
  });

  /* ── Where the arrows are drawn ───────────────────────────────────
     The glyph is the load, as far as the user is concerned. Its 3D branch anchored
     every arrow at `domain.z_top` -- the top of the *borehole* block -- so a load put
     on an embankment in 2D jumped down onto the borehole soil on the switch to 3D,
     while the 2D branch had used `load.z` all along. Mirrors the server's
     `Project.elevation_of`. */

  var RAISED_SOLID = { dimension: 3,
    domain: { x0: 0, x1: 50, y0: 0, y1: 40, z_top: 0, z_bottom: -25 },
    custom_parts: [EMBANKMENT], loads: [] };

  function surfaceLoad(z) {
    return { id: 'load_1', name: 'SurfaceLoad_1', kind: 'surface',
             x0: 4, x1: 16, y0: 5, y1: 10, z: z, thickness: 0.15,
             components: [0, 0, -20], distribution: 'Uniform', active: true };
  }

  test('a 3D surface load draws its arrows at its own elevation', function () {
    var spec = App.Viewport.loadGlyphSpec(surfaceLoad(4), RAISED_SOLID);
    T.ok(spec.anchors.length, 'the glyph has anchors');
    T.eq(spec.anchors.every(function (a) { return a[2] === 4; }), true,
         'every arrow sits on the embankment, not on the borehole soil: '
         + JSON.stringify(spec.anchors.map(function (a) { return a[2]; })));
  });

  test('a surface load with no elevation falls back to the top of the model', function () {
    var spec = App.Viewport.loadGlyphSpec(surfaceLoad(null), RAISED_SOLID);
    T.eq(spec.anchors.every(function (a) { return a[2] === 4; }), true,
         'older records still mean the model top, which the embankment raised');
  });

  test('with nothing drawn the model top is still the domain top', function () {
    var plain = Object.assign({}, RAISED_SOLID, { custom_parts: [] });
    var spec = App.Viewport.loadGlyphSpec(surfaceLoad(null), plain);
    T.eq(spec.anchors.every(function (a) { return a[2] === 0; }), true);
  });

  test('the surface load outline is drawn at the same elevation as its arrows', function () {
    /* The pad outline had its own copy of `domain.z_top`, so fixing only the arrows
       would have left the rectangle behind on the borehole soil. */
    var group = App.Viewport.loadGlyphGroup(surfaceLoad(4), RAISED_SOLID);
    var outline = null;
    group.traverse(function (object) {
      if (object.geometry && object.geometry.attributes
          && object.type === 'Line' && object.userData.noPick) outline = object;
    });
    T.ok(outline, 'the pad has an outline');
    var z = outline.geometry.attributes.position.array;
    var levels = [];
    for (var i = 2; i < z.length; i += 3) levels.push(z[i]);
    T.eq(levels.every(function (v) { return v === 4; }), true,
         'outline levels: ' + JSON.stringify(levels));
  });

})();
