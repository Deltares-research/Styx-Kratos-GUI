(function () {
  test('view presets select a stable reference grid plane', function () {
    var box = [0, 0, -25, 50, 40, 0];
    T.eq(App.Viewport.gridReference('top', box), { plane: 'xy', offset: -25 });
    T.eq(App.Viewport.gridReference('iso', box), { plane: 'xy', offset: -25 });
    T.eq(App.Viewport.gridReference('front', box), { plane: 'xz', offset: 0 });
    T.eq(App.Viewport.gridReference('side', box), { plane: 'yz', offset: 50 });
  });

  /* A drawn/imported part's THREE.Group exists (buildGroups makes one per section key)
     but setMode() only shows keys present in modeGroups[mode] -- so a custom part that
     computeModeGroups leaves out of every mode is created, then invisible forever,
     regardless of the eye toggle. The default project has simple_example: true, which
     used to hard-code modeGroups to soilKeys only. */

  test('a custom part is visible in every mode of a simple_example project', function () {
    var groups = App.Viewport.computeModeGroups(['soil_L1', 'soil_L2'], ['drawn_0'], true);
    ['soil', 'structures', 'mesh', 'flow', 'staged'].forEach(function (mode) {
      T.ok(groups[mode].indexOf('drawn_0') >= 0, mode + ' is missing the custom part');
    });
  });

  test('in a full (non-simple_example) project, a custom part follows the structural ' +
       'parts -- everywhere but the soil-only mode', function () {
    var groups = App.Viewport.computeModeGroups(['soil_L1'], ['drawn_0'], false);
    ['structures', 'mesh', 'flow', 'staged'].forEach(function (mode) {
      T.ok(groups[mode].indexOf('drawn_0') >= 0, mode + ' is missing the custom part');
    });
    T.eq(groups.soil.indexOf('drawn_0'), -1, 'soil mode stays soil-only, like wall/struts');
  });

  test('with no custom parts, mode groups are unchanged from before', function () {
    var groups = App.Viewport.computeModeGroups(['soil_L1', 'soil_L2'], [], true);
    T.eq(groups.structures, ['soil_L1', 'soil_L2']);
    T.eq(groups.mesh, ['soil_L1', 'soil_L2', 'mesh']);
  });

  /* Sheet piles and anchors are drawn as their own sections (server/app/tessellate.py
     :112-126), so each gets a THREE.Group keyed by its id -- but no mode listed those
     keys, which left every pile and anchor invisible in every mode. */
  test('sheet piles and anchors are visible where the other structures are', function () {
    [true, false].forEach(function (simple) {
      var groups = App.Viewport.computeModeGroups(
        ['soil_L1'], [], simple, ['load_1'], ['beam_1', 'anchor_1']);
      ['structures', 'mesh', 'staged'].forEach(function (mode) {
        ['beam_1', 'anchor_1'].forEach(function (key) {
          T.ok(groups[mode].indexOf(key) >= 0,
               mode + ' hides ' + key + (simple ? ' (simple_example)' : ''));
        });
      });
      T.eq(groups.soil.indexOf('beam_1'), -1, 'soil mode stays soil-only');
    });
  });

  /* What the Model explorer's group rows toggle: one checkbox standing for a family
     of part keys, the way the Soil row already stood for its layers. */
  test('a tree group row names the part keys it stands for', function () {
    var keys = App.Viewport.computeGroupKeys(
      ['soil_L1', 'soil_L2'], ['drawn_0'], ['load_1'], ['beam_1'], ['anchor_1']);
    T.eq(keys.soil, ['soil_L1', 'soil_L2']);
    T.eq(keys['group:custom'], ['drawn_0']);
    T.eq(keys['group:loads'], ['load_1']);
    T.eq(keys['group:sheetpiles'], ['beam_1']);
    T.eq(keys['group:anchors'], ['anchor_1']);
  });
})();

/* ── Step 1 of 2D mode: the camera and grid, before any geometry changes ──
   The switch is view-only for now, so everything asserted here is pure: which
   angles a view preset resolves to, and which plane the reference grid takes.
   See plan/plan_2d_mode.md. */

(function () {
  var DOMAIN = { domain: { x0: 0, x1: 50, y0: 0, y1: 40, z_top: 0, z_bottom: -25 } };

  test('an explicit section_offset wins over the domain midpoint', function () {
    T.near(App.Viewport.sectionOffset({ domain: DOMAIN.domain, section_offset: 12.5 }),
           12.5, 1e-9);
  });

  test('in 3D the view presets are unchanged', function () {
    T.near(App.Viewport.cameraAngles('top', 3).phi, 0.035, 1e-9);
    T.near(App.Viewport.cameraAngles('side', 3).theta, 0, 1e-9);
    // An unknown name still lands on iso, as setView has always done.
    T.eq(App.Viewport.cameraAngles('nonsense', 3), App.Viewport.cameraAngles('iso', 3));
  });

  test('in 2D every view preset collapses to the section view', function () {
    // Elevation: theta -pi/2 with phi pi/2 puts the camera on -y looking along +y,
    // so x runs right and z up. Front/top/side/iso must not rotate out of it.
    ['iso', 'front', 'side', 'top', 'nonsense'].forEach(function (name) {
      var a = App.Viewport.cameraAngles(name, 2, 'xz');
      T.near(a.theta, -Math.PI / 2, 1e-9, name + ' theta');
      T.near(a.phi, Math.PI / 2, 1e-9, name + ' phi');
    });
  });

  test('a plan section looks down, at the same tilt as the frozen top view', function () {
    // Not straight down: 0.035 rad is what js/viewport.js's `top` preset uses, and
    // the next test says why it cannot be zero.
    T.near(App.Viewport.cameraAngles('iso', 2, 'xy').phi, 0.035, 1e-9);
    // ...and the other elevation looks along -x.
    T.near(App.Viewport.cameraAngles('iso', 2, 'yz').theta, 0, 1e-9);
    T.near(App.Viewport.cameraAngles('iso', 2, 'yz').phi, Math.PI / 2, 1e-9);
  });

  test('no section camera is degenerate against the fixed up vector', function () {
    /* js/orbit.js:32 hard-codes camera.up = (0, 0, 1). If a view direction is
       parallel to that, lookAt() builds a degenerate basis and three.js draws
       nothing at all -- an empty viewport with no error in the console, which is
       exactly what a phi of 0.0001 produced. |forward x up| is sin(phi), so the
       test is really "keep the camera off the pole". */
    ['xz', 'yz', 'xy'].forEach(function (plane) {
      var a = App.Viewport.cameraAngles('iso', 2, plane);
      var separation = Math.abs(Math.sin(a.phi));
      T.ok(separation > 0.02,
           plane + ' camera is degenerate: |forward x up| = ' + separation);
    });
  });

  test('a drag that rotates out of the section view is clamped back', function () {
    var clamped = App.Viewport.clampAngles({ theta: -1.1, phi: 0.4 }, 2, 'xz');
    T.near(clamped.theta, -Math.PI / 2, 1e-9);
    T.near(clamped.phi, Math.PI / 2, 1e-9);
    T.ok(clamped.changed, 'the caller needs to know it has to re-render');

    var plan = App.Viewport.clampAngles({ theta: -1.1, phi: 0.4 }, 2, 'xy');
    T.near(plan.phi, 0.0001, 0.05);
    T.ok(plan.changed);
  });

  test('clamping is a no-op in 3D and when already on the section plane', function () {
    T.eq(App.Viewport.clampAngles({ theta: -1.1, phi: 0.4 }, 3, 'xz').changed, false);
    T.eq(App.Viewport.clampAngles(
      App.Viewport.cameraAngles('iso', 2, 'xz'), 2, 'xz').changed, false);
  });

  test('in 2D the reference grid is the section plane itself, whatever the view', function () {
    var box = [0, 0, -25, 50, 40, 0];
    ['top', 'iso', 'front', 'side'].forEach(function (name) {
      T.eq(App.Viewport.gridReference(name, box, 'xz', 20), { plane: 'xz', offset: 20 }, name);
      T.eq(App.Viewport.gridReference(name, box, 'xy', -6), { plane: 'xy', offset: -6 }, name);
    });
  });

  test('the section offset travels along the plane normal', function () {
    var domain = { x0: 0, x1: 50, y0: 0, y1: 40, z_top: 0, z_bottom: -25 };
    T.near(App.Viewport.sectionOffset({ domain: domain, section_plane: 'xz' }), 20, 1e-9);
    T.near(App.Viewport.sectionOffset({ domain: domain, section_plane: 'xy' }), -12.5, 1e-9);
    T.near(App.Viewport.sectionOffset({ domain: domain, section_plane: 'yz' }), 25, 1e-9);
    T.near(App.Viewport.sectionOffset({ domain: domain, section_plane: 'xy',
                                        section_offset: -6 }), -6, 1e-9);
    T.near(App.Viewport.sectionOffset(null), 0, 1e-9);
  });
})();

/* A project that is already 2D when it loads must come up in 2D. Without this the
   camera is a free 3D orbit over a flat section, which reads as a rendering fault. */

(function () {
  test('the viewport adopts the dimension the loaded project already has', function () {
    var saved = { project: App.PROJECT, state: App.state };
    var applied = [];
    App.state = {};
    try {
      App.PROJECT = { dimension: 2, section_plane: 'xz', section_offset: 20,
                      domain: { x0: 0, x1: 50, y0: 0, y1: 40, z_top: 0, z_bottom: -25 } };
      T.eq(App.Viewport.viewModeOf(App.PROJECT), 'elevation');
      T.eq(App.Viewport.viewModeOf({ dimension: 2, section_plane: 'xy' }), 'plan');
      T.eq(App.Viewport.viewModeOf({ dimension: 3 }), 'solid');
      T.eq(App.Viewport.viewModeOf(null), 'solid', 'no project yet means the 3D default');
    } finally {
      App.PROJECT = saved.project; App.state = saved.state;
    }
    T.eq(applied, []);
  });
})();

/* 2D forces the orthographic camera, whose frustum the frozen code sizes with two
   constants tuned for the 3D perspective demo (s = 30, orthoBase = 46). Applied to
   a flat section that leaves the model at a fraction of the viewport -- present,
   but far too small to read as "the model". The frustum has to come from the
   section's own extent instead. */

(function () {
  var BOX = [0, 0, -25, 50, 40, 0];

  function fits(plane, width, height, aspect) {
    var frame = App.Buffers.bounds(BOX);
    var s = App.Viewport.orthoHalfHeight(frame, plane, aspect);
    // js/orbit.js:40 sets camera.zoom = orthoBase / radius, so at the home radius
    // the visible half-height is s * homeRadius / orthoBase.
    var halfH = s * frame.homeRadius / App.Viewport.ORTHO_BASE;
    return { halfH: halfH, halfW: halfH * aspect, needH: height / 2, needW: width / 2 };
  }

  test('the 2D frustum contains the whole section, on every plane', function () {
    [['xz', 50, 25], ['xy', 50, 40], ['yz', 40, 25]].forEach(function (c) {
      var f = fits(c[0], c[1], c[2], 2);
      T.ok(f.halfH >= f.needH, c[0] + ' too short: ' + f.halfH + ' < ' + f.needH);
      T.ok(f.halfW >= f.needW, c[0] + ' too narrow: ' + f.halfW + ' < ' + f.needW);
    });
  });

  test('...without leaving the section adrift in empty space', function () {
    // The old constants put the xz section in a frustum 5x too tall. Anything under
    // 1.5x the model is a fit a person would call a fit.
    [['xz', 50, 25], ['xy', 50, 40], ['yz', 40, 25]].forEach(function (c) {
      var f = fits(c[0], c[1], c[2], 2);
      T.ok(f.halfH < f.needH * 1.5 || f.halfW < f.needW * 1.5,
           c[0] + ' is padded out to ' + f.halfH + ' vs ' + f.needH);
    });
  });

  test('a tall, narrow viewport widens the frustum instead of clipping', function () {
    var narrow = fits('xz', 50, 25, 0.5);
    T.ok(narrow.halfW >= narrow.needW, 'the section must still fit across');
  });

  test('with no frame yet, the frozen constant is kept', function () {
    T.eq(App.Viewport.orthoHalfHeight(null, 'xz', 1.5), 30);
  });
})();

/* ── The 2D grid is the drawing surface, not a footprint ────────────────────────
   In 3D the grid is a plane the model stands on, so model-sized is right. In 2D it
   is the paper the section is drawn on and has to reach the edges of the viewport
   at any pan or zoom -- a grid that stops mid-screen reads as the edge of the
   model. sectionGridSpec is what it has to be for the rectangle now in view. */
(function () {
  var CELL = 2.5;

  function spec(center, halfW, halfH) {
    return App.Viewport.sectionGridSpec(CELL, center, halfW, halfH);
  }

  test('the grid covers the whole visible rectangle, not just the model', function () {
    var g = spec([25, -12.5], 60, 30);
    T.ok(g.span / 2 >= 60, 'too narrow: ' + g.span);
    T.ok(Math.abs(g.u - 25) + 60 <= g.span / 2 + 1e-9, 'the view has slid off the grid');
    T.ok(Math.abs(g.v + 12.5) + 30 <= g.span / 2 + 1e-9, 'the view has slid off the grid');
  });

  test('its lines stay on one lattice while the view is panned', function () {
    var a = spec([0, 0], 40, 30), b = spec([7.3, -3.1], 40, 30);
    T.eq(a.cell, b.cell);
    T.near((b.u - a.u) % a.cell, 0, 1e-9, 'the centre must snap to a cell');
    T.near((b.v - a.v) % a.cell, 0, 1e-9);
    T.eq(a.divisions % 2, 0, 'an even count keeps the lines symmetric about the centre');
  });

  test('zooming out coarsens the cell rather than drawing ten thousand lines', function () {
    var near = spec([0, 0], 40, 30), far = spec([0, 0], 4000, 3000);
    T.eq(near.cell, CELL, 'at working zoom the cell is the one the model chose');
    T.ok(far.cell > near.cell, 'a wide view has to coarsen: ' + far.cell);
    T.ok(far.cell % CELL === 0, 'and stay a multiple of it, so lines survive the change');
    T.ok(far.divisions <= App.Viewport.MAX_GRID_DIVISIONS, 'unbounded line count: ' + far.divisions);
    T.ok(far.span / 2 >= 4000, 'still has to cover the view');
  });

  test('a grid is rebuilt when the view leaves it, and left alone when it has not', function () {
    var g = spec([0, 0], 40, 30);
    T.eq(App.Viewport.sectionGridNeedsRebuild(g, spec([0.5, 0.5], 40, 30)), false,
         'a small pan inside the same lattice is not a rebuild');
    T.eq(App.Viewport.sectionGridNeedsRebuild(g, spec([400, 0], 40, 30)), true);
    T.eq(App.Viewport.sectionGridNeedsRebuild(g, spec([0, 0], 4000, 3000)), true);
    T.eq(App.Viewport.sectionGridNeedsRebuild(null, g), true, 'nothing drawn yet');
  });
})();

/* WebGL can simply be unavailable -- hardware acceleration switched off, a
   blocklisted driver, or a headless/remote session. Chrome no longer falls back to
   software rendering by default, so `new THREE.WebGLRenderer()` throws outright.

   That throw used to happen inside init(), which is called from the middle of
   js/app.js boot(), so it took the splitters, the mode setup and the whole model
   tree down with it. The user saw an empty window and no explanation. */

(function () {
  test('the renderer is built through a try, not through a support probe', function () {
    // A probe asks a *different* canvas whether WebGL works and then throws that
    // answer away. It can disagree with the real construction in both directions,
    // and it costs a third live context on a machine that may be short of them.
    // Attempting the real thing cannot be wrong about the real thing.
    var built = { real: true };
    T.eq(App.Viewport.makeRenderer(function () { return built; }), built);
  });

  test('a renderer that refuses to construct falls back instead of throwing', function () {
    // The point of catching the throw is not to report it prettily. It is to get a
    // renderer anyway: a blank viewport cannot be told apart from a model that
    // failed to build, which is what made this so expensive to diagnose.
    var soft = { isSoftware: true };
    T.eq(App.Viewport.makeRenderer(
      function () { throw new Error('Error creating WebGL context.'); },
      function () { return soft; }), soft);
  });

  test('the software fallback is a real renderer, not a stub', function () {
    // Whatever init() reaches for when WebGL is gone has to satisfy the three calls
    // the viewport makes of a renderer, or the fallback merely moves the crash.
    var r = new App.CanvasRenderer(document.createElement('canvas'));
    ['setPixelRatio', 'setSize', 'render'].forEach(function (name) {
      T.ok(typeof r[name] === 'function', name + ' must exist on the fallback');
    });
  });

  test('the failure message says what to actually do about it', function () {
    var text = App.Viewport.WEBGL_HELP;
    T.ok(/WebGL/i.test(text), 'name the missing thing');
    T.ok(/acceleration/i.test(text), 'name the setting that usually fixes it');
    T.ok(/chrome:\/\/gpu|graphics/i.test(text), 'point at where to look');
  });
})();

/* With no WebGL the viewport never initialises: there is no renderer, no orbit and
   no scene. Every entry point the rest of the app calls has to survive that, or the
   first toolbar click replaces one missing panel with a broken application. This
   test page never calls init(), so it is exactly that state. */

(function () {
  test('the public API is safe on an uninitialised viewport', function () {
    ['setView', 'zoomFit', 'setGrid', 'setProjection', 'setViewMode', 'resize'].forEach(
      function (name) {
        T.ok(typeof App.Viewport[name] === 'function', name + ' must exist');
      });
    // Each of these reaches for orbit, scene or renderer in the initialised case.
    App.Viewport.setView('top');
    App.Viewport.zoomFit();
    App.Viewport.dolly(1);
    App.Viewport.setGrid(true);
    App.Viewport.setProjection(false);
    App.Viewport.setViewMode('2d');
    App.Viewport.resize();
    T.ok(true, 'none of the above threw');
  });

  /* refresh() is not a viewport-only call: it is what every geometry-changing action
     in patches.js ends with -- switching to 2D, editing layers, drawing a part. With
     no scene to build into, `scene.add` threw and the action reported "Cannot read
     properties of undefined (reading 'add')" instead of doing its half of the work. */
  test('refresh loads the project and skips the scene it cannot build', function () {
    var asked = [];
    var saved = { Model: App.Model, Api: App.Api, setMode: App.setMode };
    function restore() {
      App.Model = saved.Model; App.Api = saved.Api; App.setMode = saved.setMode;
    }
    App.Model = { load: function () { asked.push('project'); return Promise.resolve(); } };
    App.Api = { get: function (path) { asked.push(path); return Promise.resolve(null); } };
    App.setMode = function () { asked.push('setMode'); };

    return App.Viewport.refresh().then(function () {
      // The project and the tree still update -- only the picture is missing. Asking
      // for geometry would be a wasted round trip: there is nowhere to put it.
      T.eq(asked, ['project', 'setMode']);
    }).then(restore, function (err) { restore(); throw err; });
  });

  test('mode and visibility changes survive an empty scene', function () {
    // setMode reaches for groups.mesh, which only exists once buildGroups has run.
    App.Viewport.setMode('mesh');
    App.Viewport.setVisible('mesh', true);
    App.Viewport.select(null);
    T.eq(App.Viewport.hasMesh(), false);
  });

  /* An imported .mdpa's preview lives outside `groups`/`frame` entirely (viewport.js's
     importedMeshGroup), so it must not need a real scene to be called safely -- the
     same "no WebGL, no throw" contract refresh() and setMode() already hold above. */
  test('an imported-mesh preview survives an empty scene', function () {
    App.Viewport.showImportedMesh({
      bbox: [0, 0, 0, 1, 1, 1],
      sections: [{ key: 'imported_continuum', color: '#d9dee6',
                  positions: [0, 0, 0, 1, 0, 0, 0, 1, 0], indices: [0, 1, 2], edges: [] }]
    });
    T.eq(App.Viewport.hasImportedMesh(), false, 'no scene to add it to');
    App.Viewport.setVisible('imported_continuum', false);
    App.Viewport.isVisible('imported_continuum');
    App.Viewport.frameImportedSection('imported_continuum');
    App.Viewport.removeImportedSection('imported_continuum');
    App.Viewport.setImportedGroupKeys(['imported_continuum']);
    T.ok(true, 'per-section toggle/frame/remove with nothing shown does not throw');
    App.Viewport.clearImportedMesh();
    T.ok(true, 'clearing with nothing shown does not throw');
  });
})();

/* The working window used to name its axes twice: two floating labels stuck on the
   bounding box, and the triad in the corner. The labels sat in world space, so they
   drifted away from the model as it was orbited and told the user nothing the triad
   did not. The triad is the one that stays put, so it is the one that survives -- and
   in 2D it shows the axes the section is actually drawn in, not a third one the
   camera cannot turn towards. */

(function () {
  test('the triad shows the axes the model is drawn in', function () {
    T.eq(App.Viewport.triadAxes(3, 'xz'), ['x', 'y', 'z']);
    T.eq(App.Viewport.triadAxes(2, 'xz'), ['x', 'z'], 'an elevation is drawn in x and z');
    T.eq(App.Viewport.triadAxes(2, 'xy'), ['x', 'y'], 'a plan is drawn in x and y');
    T.eq(App.Viewport.triadAxes(2, 'yz'), ['y', 'z']);
  });

  test('the axis normal to the section is the one left out', function () {
    // Not simply "drop z in 2D": which axis goes depends on the plane being cut.
    ['xz', 'xy', 'yz'].forEach(function (plane) {
      var shown = App.Viewport.triadAxes(2, plane);
      T.eq(shown.length, 2, plane + ' should show two axes');
      shown.forEach(function (axis) {
        T.ok(plane.indexOf(axis) >= 0, axis + ' lies in the ' + plane + ' plane');
      });
    });
  });
})();
