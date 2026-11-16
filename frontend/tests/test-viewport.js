(function () {
  test('view presets select a stable reference grid plane', function () {
    // The model box, world (xmin, ymin, zmin, xmax, ymax, zmax): 50 across, 25 deep
    // below ground, 40 out of plane.
    var box = [0, -25, 0, 50, 0, 40];
    T.eq(App.Viewport.gridReference('top', box), { plane: 'xz', offset: -25 },
         'the top view backs the grid onto the model floor');
    T.eq(App.Viewport.gridReference('iso', box), { plane: 'xz', offset: -25 });
    T.eq(App.Viewport.gridReference('front', box), { plane: 'xy', offset: 0 },
         'the front view stands it up in the x-y plane at the near z');
    T.eq(App.Viewport.gridReference('side', box), { plane: 'yz', offset: 50 });
  });

  /* A drawn/imported part's THREE.Group exists (buildGroups makes one per section key)
     but setMode() only shows keys present in modeGroups[mode] -- so a custom part that
     computeModeGroups leaves out of every mode is created, then invisible forever,
     regardless of the eye toggle. The default project has layered_soil: true, which
     used to hard-code modeGroups to soilKeys only. */

  test('a custom part is visible in every mode of a layered_soil project', function () {
    var groups = App.Viewport.computeModeGroups(['soil_L1', 'soil_L2'], ['drawn_0'], true);
    ['soil', 'structures', 'mesh', 'flow', 'staged'].forEach(function (mode) {
      T.ok(groups[mode].indexOf('drawn_0') >= 0, mode + ' is missing the custom part');
    });
  });

  test('in a full (non-layered_soil) project, a custom part follows the structural ' +
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

  /* Sheet piles and anchors are drawn as their own sections (core/geometry/tessellation.py
     :112-126), so each gets a THREE.Group keyed by its id -- but no mode listed those
     keys, which left every pile and anchor invisible in every mode. */
  test('sheet piles and anchors are visible where the other structures are', function () {
    [true, false].forEach(function (simple) {
      var groups = App.Viewport.computeModeGroups(
        ['soil_L1'], [], simple, ['load_1'], ['beam_1', 'anchor_1']);
      ['structures', 'mesh', 'staged'].forEach(function (mode) {
        ['beam_1', 'anchor_1'].forEach(function (key) {
          T.ok(groups[mode].indexOf(key) >= 0,
               mode + ' hides ' + key + (simple ? ' (layered_soil)' : ''));
        });
      });
      T.eq(groups.soil.indexOf('beam_1'), -1, 'soil mode stays soil-only');
    });
  });

  test('free interfaces are listed in structural modes, separately from members', function () {
    [true, false].forEach(function (layered) {
      var groups = App.Viewport.computeModeGroups(
        ['soil_L1'], [], layered, [], ['beam_1', 'anchor_1'], [], null, ['contact_1']);
      ['structures', 'mesh', 'staged'].forEach(function (mode) {
        T.ok(groups[mode].indexOf('contact_1') >= 0,
             mode + ' omits the free interface' + (layered ? ' (layered soil)' : ''));
      });
      ['soil', 'flow', 'results'].forEach(function (mode) {
        T.eq(groups[mode].indexOf('contact_1'), -1,
             mode + ' should not show a free interface');
      });
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
  var DOMAIN = { domain: { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 } };

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

  test('in 2D every view preset collapses to the one section view', function () {
    // theta pi/2 with phi pi/2 puts the camera on +z looking along -z, so x runs
    // right and y up. Front/top/side/iso must not rotate out of it.
    ['iso', 'front', 'side', 'top', 'nonsense'].forEach(function (name) {
      var a = App.Viewport.cameraAngles(name, 2);
      T.near(a.theta, Math.PI / 2, 1e-9, name + ' theta');
      T.near(a.phi, Math.PI / 2, 1e-9, name + ' phi');
    });
  });

  test('the section view is square on, with no tilt to dodge a degenerate basis', function () {
    /* The frozen Z-up controller hard-codes camera.up = (0, 0, 1), so an elevation
       had to be nudged off the pole or lookAt() built a degenerate basis and three.js
       drew nothing at all -- an empty viewport, no error. frontend/js/orbit.js stands the
       camera up on +y instead, and the section looks along -z, which is square to it:
       |forward x up| is exactly 1. */
    var a = App.Viewport.cameraAngles('iso', 2);
    T.near(Math.abs(Math.sin(a.phi)), 1, 1e-12);
  });

  test('only the top view still needs a tilt, since it looks along the up vector', function () {
    var top = App.Viewport.cameraAngles('top', 3);
    T.near(top.phi, 0.035, 1e-9);
    T.ok(Math.abs(Math.sin(top.phi)) > 0.02,
         'the 3D top view is degenerate: |forward x up| = ' + Math.sin(top.phi));
  });

  test('a drag that rotates out of the section view is clamped back', function () {
    var clamped = App.Viewport.clampAngles({ theta: -1.1, phi: 0.4 }, 2);
    T.near(clamped.theta, Math.PI / 2, 1e-9);
    T.near(clamped.phi, Math.PI / 2, 1e-9);
    T.ok(clamped.changed, 'the caller needs to know it has to re-render');
  });

  test('clamping is a no-op in 3D and when already on the section plane', function () {
    T.eq(App.Viewport.clampAngles({ theta: -1.1, phi: 0.4 }, 3).changed, false);
    T.eq(App.Viewport.clampAngles(App.Viewport.cameraAngles('iso', 2), 2).changed, false);
  });

  test('in 2D the reference grid is the section plane itself, whatever the view', function () {
    var box = [0, -25, 0, 50, 0, 40];
    ['top', 'iso', 'front', 'side'].forEach(function (name) {
      T.eq(App.Viewport.gridReference(name, box, true), { plane: 'xy', offset: 0 }, name);
    });
  });

  test('the section offset travels along z, the axis the cut is normal to', function () {
    var domain = { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 };
    T.near(App.Viewport.sectionOffset({ domain: domain }), 20, 1e-9);
    T.near(App.Viewport.sectionOffset({ domain: domain, section_offset: -6 }), -6, 1e-9);
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
      App.PROJECT = { dimension: 2, section_offset: 20,
                      domain: { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 } };
      T.eq(App.Viewport.viewModeOf(App.PROJECT), 'elevation');
      T.eq(App.Viewport.viewModeOf({ dimension: 3 }), 'solid');
      T.eq(App.Viewport.viewModeOf(null), 'elevation',
           'no project yet means the 2D default the app opens on');
    } finally {
      App.PROJECT = saved.project; App.state = saved.state;
    }
    T.eq(applied, []);
  });

  /* The app is a 2D modeller, and the server opens on a plane-strain project. Booting
     the camera in 3D and correcting it when /api/geometry answers is a visible flip
     through a view the user never asked for, so the section angles and the parallel
     projection have to be what the first frame is drawn with. */
  test('the camera starts on the section rather than flipping to it a second later',
       function () {
    T.eq(App.Viewport.DEFAULT_VIEW_MODE, 'elevation');
    T.eq(App.Viewport.DEFAULT_DIMENSION, 2);
    T.eq(App.Viewport.cameraAngles('iso', App.Viewport.DEFAULT_DIMENSION),
         App.Viewport.cameraAngles(null, 2),
         'the opening angles are the section angles, not the iso ones');
  });
})();

/* 2D forces the orthographic camera, whose frustum the frozen code sizes with two
   constants tuned for the 3D perspective demo (s = 30, orthoBase = 46). Applied to
   a flat section that leaves the model at a fraction of the viewport -- present,
   but far too small to read as "the model". The frustum has to come from the
   section's own extent instead. */

(function () {
  var BOX = [0, -25, 0, 50, 0, 40];

  function fits(width, height, aspect) {
    var frame = App.Buffers.bounds(BOX);
    var s = App.Viewport.orthoHalfHeight(frame, aspect);
    // js/orbit.js:40 sets camera.zoom = orthoBase / radius, so at the home radius
    // the visible half-height is s * homeRadius / orthoBase.
    var halfH = s * frame.homeRadius / App.Viewport.ORTHO_BASE;
    return { halfH: halfH, halfW: halfH * aspect, needH: height / 2, needW: width / 2 };
  }

  test('the 2D frustum contains the whole section', function () {
    // The section is the x-y plane: 50 m across and 25 m down.
    var f = fits(50, 25, 2);
    T.ok(f.halfH >= f.needH, 'too short: ' + f.halfH + ' < ' + f.needH);
    T.ok(f.halfW >= f.needW, 'too narrow: ' + f.halfW + ' < ' + f.needW);
  });

  test('...without leaving the section adrift in empty space', function () {
    // The old constants put the section in a frustum 5x too tall. Anything under
    // 1.5x the model is a fit a person would call a fit.
    var f = fits(50, 25, 2);
    T.ok(f.halfH < f.needH * 1.5 || f.halfW < f.needW * 1.5,
         'padded out to ' + f.halfH + ' vs ' + f.needH);
  });

  test('the out-of-plane depth cannot size the frustum', function () {
    // 40 m of model behind the section is edge-on: it must not widen the view.
    var f = fits(50, 25, 2);
    T.ok(f.halfH < 40, 'the frustum is sized by x and y only: ' + f.halfH);
  });

  test('a tall, narrow viewport widens the frustum instead of clipping', function () {
    var narrow = fits(50, 25, 0.5);
    T.ok(narrow.halfW >= narrow.needW, 'the section must still fit across');
  });

  test('with no frame yet, the frozen constant is kept', function () {
    T.eq(App.Viewport.orthoHalfHeight(null, 1.5), 30);
  });
})();

/* The home view takes in what is drawn around the soil: a surcharge's arrows can
   stand 6.4 m above the ground, and a view of the soil box alone hid them under the
   top ruler. */

(function () {
  var SOIL = [0, -60, 0, 80, 0, 0];

  test('the home box grows to take in a load above the ground', function () {
    var grown = App.Viewport.growBBox(SOIL, [[5, 0, 5], [80, 6.4, 5]], true);
    T.eq(grown[4], 6.4, 'up to the tails of the arrows');
    T.eq(grown[0], 0); T.eq(grown[1], -60); T.eq(grown[3], 80);
  });

  test('...but in 2D not along the depth, which is edge-on', function () {
    var grown = App.Viewport.growBBox(SOIL, [[5, 0, 5], [80, 6.4, 5]], true);
    T.eq(grown[2], 0); T.eq(grown[5], 0);
    var solid = App.Viewport.growBBox(SOIL, [[5, 0, 5], [80, 6.4, 5]], false);
    T.eq(solid[5], 5, 'in 3D the depth counts');
  });

  test('a part inside the soil leaves the box as it was', function () {
    T.eq(App.Viewport.growBBox(SOIL, [[5, -13, 0], [5, 0, 0]], true).join(),
         SOIL.join());
  });
})();

/* ── How far the wheel may go ──────────────────────────────────────────────────
   js/orbit.js clamps the dolly between minRadius and maxRadius, and the live
   viewport used to hand it 8 and 6x the *provisional* demo frame. On a 0.1 x 1 m
   column the home radius is smaller than that floor, so the wheel did nothing at
   all and the readout sat stuck at 19%. Both limits have to come from the model. */
(function () {
  var DEMO = App.Buffers.bounds([0, 0, -25, 50, 40, 0]);
  var COLUMN = App.Buffers.bounds([0, 0, -1, 0.1, 1, 0]);

  test('the limits are the same multiples of the model at any scale', function () {
    var demo = App.Viewport.radiusLimits(DEMO);
    var column = App.Viewport.radiusLimits(COLUMN);
    T.near(demo.min / DEMO.homeRadius, column.min / COLUMN.homeRadius, 1e-12);
    T.near(demo.max / DEMO.homeRadius, column.max / COLUMN.homeRadius, 1e-12);
  });

  test('a small model can still be zoomed in on', function () {
    var limits = App.Viewport.radiusLimits(COLUMN);
    T.ok(limits.min < COLUMN.homeRadius,
         'the floor is above the fitted view: the wheel would be dead on arrival');
    T.ok(COLUMN.homeRadius / limits.min >= 10,
         'and there has to be room to get close: ' + COLUMN.homeRadius / limits.min);
    T.ok(limits.max > COLUMN.homeRadius, 'zooming out has to move too');
  });

  test('the demo domain keeps the reach the frozen constants gave it in 3D', function () {
    // The floor that also keeps the perspective camera's near plane out of the model.
    var limits = App.Viewport.radiusLimits(DEMO, 3);
    T.near(limits.min, 8, 0.5, 'the frozen minRadius, now expressed as a fraction');
    T.near(limits.max, DEMO.homeRadius * 6, 1e-9);
  });

  test('with no frame yet there are still limits, and they are ordered', function () {
    var limits = App.Viewport.radiusLimits(null);
    T.ok(limits.min > 0 && limits.max > limits.min);
  });

  /* An imported deck crowds dozens of nodes into the last few centimetres beside a
     sheet pile; 12.5x of a 70 m section still showed them as one smear. A 2D section
     is seen through the orthographic camera, whose near plane is far behind it, so
     there is nothing to clip however close it gets. 3D keeps its floor: the
     perspective camera's near plane (0.5) would cut into the model. */
  test('a 2D section can be zoomed in a thousand times or more', function () {
    var limits = App.Viewport.radiusLimits(DEMO, 2);
    T.ok(DEMO.homeRadius / limits.min >= 1000,
         'only ' + DEMO.homeRadius / limits.min + 'x');
    T.near(limits.max, DEMO.homeRadius * 6, 1e-9, 'zooming out is unchanged');
  });
})();

/* ── The coordinate readout ────────────────────────────────────────────────────
   The status bar reads the cursor off a plane. In 2D the camera looks straight
   down that plane's normal, so casting at the z = 0 ground plane instead sends the
   ray almost parallel to it -- which is where the reported y of 2.2e14 m came
   from. The plane has to be the section itself. */
(function () {
  function normalOf(plane) { return [plane.normal.x, plane.normal.y, plane.normal.z]; }

  test('2D reads the cursor off the section plane it is looking at', function () {
    // The section is the x-y plane at z = 0: the cut is taken at `section_offset`
    // but `build._section` moves the geometry there, so that is where a pick lands.
    var plane = App.Viewport.pickPlane(2);
    T.eq(normalOf(plane), [0, 0, 1]);
    T.eq(plane.constant, 0);
  });

  test('3D still reads off the ground', function () {
    var plane = App.Viewport.pickPlane(3);
    T.eq(normalOf(plane), [0, 1, 0], 'with Y up the ground is a plane of constant y');
    T.eq(plane.constant, 0);
  });

  test('the section ray meets the section plane instead of running along it', function () {
    // The camera the section uses: looking along -z, exactly parallel to the
    // horizontal ground plane.
    var ray = new THREE.Ray(new THREE.Vector3(5, -3, 100),
                            new THREE.Vector3(0, 0, -1));
    var onSection = ray.intersectPlane(App.Viewport.pickPlane(2), new THREE.Vector3());
    T.ok(onSection, 'the section plane is square to the view: it always has a hit');
    T.eq([onSection.x, onSection.y, onSection.z], [5, -3, 0]);
    T.eq(ray.intersectPlane(App.Viewport.pickPlane(3), new THREE.Vector3()),
         null, 'the ground plane is the one that gave 2.2e14 m');
  });
})();

/* ── The 2D grid is the drawing surface, not a footprint ────────────────────────
   In 3D the grid is a plane the model stands on, so model-sized is right. In 2D it
   is the paper the section is drawn on and has to reach the edges of the viewport
   at any pan or zoom -- a grid that stops mid-screen reads as the edge of the
   model. sectionGridSpec is what it has to be for the rectangle now in view. */
(function () {
  var CELL = 2;

  function spec(center, halfW, halfH) {
    return App.Viewport.sectionGridSpec(CELL, center, halfW, halfH);
  }

  function isNice(value) {
    var mantissa = value / Math.pow(10, Math.floor(Math.log10(value) + 1e-9));
    return [1, 2, 5, 10].some(function (m) { return Math.abs(mantissa - m) < 1e-6; });
  }

  test('the grid cell is a step the rulers also take: 1, 2 or 5 times a power of ten', function () {
    // A 3 m wide model used to get 0.6 m cells, off every ruler tick.
    [[3, 2], [0.4, 0.2], [12, 6], [37, 20], [250, 40], [1e-3, 1e-3]].forEach(function (size) {
      var cell = App.Viewport.gridCell({ size: [size[0], size[1], 1] });
      T.ok(isNice(cell), size[0] + ' m model: ' + cell);
      T.ok(Math.max(size[0], size[1]) * 1.6 / cell >= 8, 'too few cells: ' + cell);
    });
    T.eq(App.Viewport.gridCell({ size: [3, 2, 1] }), 0.5);
  });

  test('zooming in and out walks the 2D cell through 1, 2, 5, 10, on the ruler ticks', function () {
    var width = 800, seen = [];
    // From 2 m to 400 m across the screen.
    for (var halfW = 1; halfW <= 200; halfW *= 1.25) {
      var cell = App.Viewport.sectionGridCell(halfW, width, 0.5);
      var ruler = App.Ruler.plan({ center: [0, 0], halfW: halfW, halfH: halfW / 2,
                                   width: width, height: width / 2 });
      T.eq(cell, ruler.h.step, 'grid and ruler disagree at half-width ' + halfW);
      if (seen[seen.length - 1] !== cell) seen.push(cell);
    }
    T.eq(seen.join(' '), '0.2 0.5 1 2 5 10 20 50');
    T.eq(App.Viewport.sectionGridCell(10, 0, 0.5), 0.5, 'no size yet: the model cell');
  });

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
    T.ok(isNice(far.cell), 'and a step the rulers also take: ' + far.cell);
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

  /* A contact lies along the very line of the wall it holds, so the two would otherwise
     be decided by insertion order -- and the interface, having no width of its own, is
     the one that disappears. */
  test('an imported interface draws over the structure it shares a line with',
       function () {
    var wall = App.Viewport.importedLineOrder({ key: 'imported:Wall', kind: 'beam' });
    var contact = App.Viewport.importedLineOrder({ key: 'imported:Contact',
                                                   kind: 'interface' });
    T.ok(contact > wall, 'the contact is painted last');
    T.eq(App.Viewport.importedLineOrder({ kind: 'continuum' }), wall,
         'everything else keeps the one order it had');
  });

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
    T.eq(App.Viewport.triadAxes(3), ['x', 'y', 'z']);
    T.eq(App.Viewport.triadAxes(2), ['x', 'y'], 'the section is drawn in x and y');
  });

  test('every camera stands up on the same axis the model does', function () {
    /* The triad widget has its own camera, and it kept the frozen mockup's
       up = (0, 0, 1) after the scene camera moved to Y-up. In the 2D section that
       is parallel to the view direction, so lookAt() built a degenerate basis and
       the widget drew nothing -- the same failure mode the section view itself
       used to have. */
    T.eq(App.Viewport.WORLD_UP, [0, 1, 0]);

    // ...and it is square to the direction the section is viewed along.
    var a = App.Viewport.cameraAngles('iso', 2);
    var forward = [Math.sin(a.phi) * Math.cos(a.theta), Math.cos(a.phi),
                   Math.sin(a.phi) * Math.sin(a.theta)];
    var dot = forward[0] * App.Viewport.WORLD_UP[0]
            + forward[1] * App.Viewport.WORLD_UP[1]
            + forward[2] * App.Viewport.WORLD_UP[2];
    T.near(dot, 0, 1e-12, 'the section view must not look along the up vector');
  });

  test('the axis normal to the section is the one left out', function () {
    // z is the out-of-plane axis: the camera cannot be turned towards it, so an
    // arrow for it would point at nothing.
    T.eq(App.Viewport.triadAxes(2).indexOf('z'), -1);
  });
})();

(function () {
  /* A staged excavation is more bodies than layers. The viewport has to show all of
     them, and cannot work out the split for itself -- the project publishes it. */

  var LAYERS = [{ id: 'L_top' }, { id: 'L_mid' }, { id: 'L_bot' }];
  var BODIES = ['soil_L_top', 'soil_L_mid', 'soil_L_bot',
                'soil_L_top__lift1', 'soil_L_top__lift2', 'soil_L_top__lift3',
                'soil_L_mid__pit', 'soil_L_bot__pit'];

  test('the soil bodies come from the project, not from its layers', function () {
    T.eq(App.Viewport.soilKeysOf({ soil_body_keys: BODIES }, LAYERS), BODIES);
  });

  test('a project that publishes no bodies falls back to one key per layer', function () {
    T.eq(App.Viewport.soilKeysOf({}, LAYERS),
         ['soil_L_top', 'soil_L_mid', 'soil_L_bot']);
    T.eq(App.Viewport.soilKeysOf(null, LAYERS),
         ['soil_L_top', 'soil_L_mid', 'soil_L_bot']);
  });

  test('every staged body is visible in the modes soil is visible in', function () {
    var groups = App.Viewport.computeModeGroups(BODIES, [], true);
    BODIES.forEach(function (key) {
      T.ok(groups.soil.indexOf(key) >= 0, 'soil mode is missing ' + key);
    });
  });
})();

(function () {
  /* Which refinement boxes a mesh is built with. A model can carry a graded mesh of its
     own (a model script can refine its excavation and grade out to the far field), and
     the Generate-mesh button must not flatten a grading the project asked for. */

  var BOX = { kind: 'box', size: 0.75, thickness: 45, x_min: -1, x_max: 8,
              y_min: -16, y_max: 1, z_min: -1, z_max: 11 };

  function withState(project, run) {
    var saved = App.PROJECT;
    App.PROJECT = project;
    try { run(); } finally { App.PROJECT = saved; }
  }

  test("a model's own refinements are used", function () {
    withState({ mesh: { refinements: [BOX] } }, function () {
      T.eq(App.Viewport.meshRefinements().length, 1);
      T.eq(App.Viewport.meshRefinements()[0].thickness, 45);
    });
  });

  test('a project that asks for no refinement gets none', function () {
    withState({ mesh: {} }, function () {
      T.eq(App.Viewport.meshRefinements(), []);
    });
    withState(null, function () {
      T.eq(App.Viewport.meshRefinements(), []);
    });
  });
})();

/* ── The selection box ────────────────────────────────────────────────────
   Selecting the mesh drew a box 3 m wider than the model on both sides. The mesh group
   also holds the coloured-part overlays (viewport.js `buildPartColors`), hidden until
   switched on, and the water level's line among them overhangs the domain by its
   margin. `Box3.setFromObject` counts hidden children, so the box took the overhang
   as part of the mesh. `boundsOf` measures what is drawn, and never the overlay. */
(function () {
  function box(x0, x1) {
    var mesh = new THREE.Mesh(new THREE.BoxGeometry(x1 - x0, 1, 1));
    mesh.position.x = (x0 + x1) / 2;
    return mesh;
  }

  test('a hidden child does not widen the selection box', function () {
    var group = new THREE.Group();
    group.add(box(0, 80));
    var hidden = box(-3, 83);
    hidden.visible = false;
    group.add(hidden);
    group.updateMatrixWorld(true);
    var bounds = App.Viewport.boundsOf(group);
    T.near(bounds.min.x, 0, 1e-9);
    T.near(bounds.max.x, 80, 1e-9);
  });

  test('the coloured-part overlay is never part of the selection box', function () {
    /* Even switched on: colouring the water level must not make the mesh look wider
       than it is. */
    var group = new THREE.Group();
    group.add(box(0, 80));
    var overlay = new THREE.Group();
    overlay.userData.noBounds = true;
    overlay.add(box(-3, 83));
    group.add(overlay);
    group.updateMatrixWorld(true);
    var bounds = App.Viewport.boundsOf(group);
    T.near(bounds.min.x, 0, 1e-9);
    T.near(bounds.max.x, 80, 1e-9);
  });

  test('a group with nothing drawn has an empty box', function () {
    T.ok(App.Viewport.boundsOf(new THREE.Group()).isEmpty());
  });
})();

/* ── Loads in Staged construction ─────────────────────────────────────────
   A layered-soil project (the blank project, the test model) drew its loads in Structures mode
   and dropped them in Staged construction, the one mode where a load's stage matters:
   the surcharge vanished as soon as the user moved on from Structures. A stage that
   switches a load off still hides it -- that is `stageHidden`'s job, not this one's. */
(function () {
  test('a layered project draws its loads in Staged construction', function () {
    var groups = App.Viewport.computeModeGroups(
      ['soil_L1'], [], true, ['surcharge'], ['sheetpile'], ['water_1']);
    T.ok(groups.staged.indexOf('surcharge') >= 0, 'the surcharge is not drawn');
    T.ok(groups.staged.indexOf('water_1') >= 0, 'the water load is not drawn');
    T.ok(groups.staged.indexOf('sheetpile') >= 0);
    T.ok(groups.staged.indexOf('water') >= 0);
  });

  /* Results draws its own contoured mesh; over it go the loads and the water, so the
     user sees where the load is and where the water stands -- and nothing else. */
  test('Results draws the loads and the water over the contour, not the model',
       function () {
    [true, false].forEach(function (layered) {
      var groups = App.Viewport.computeModeGroups(
        ['soil_L1'], ['drawn_0'], layered, ['surcharge'], ['sheetpile'], ['water_1'],
        { supports: ['fixed_bottom'], water: ['phreatic'] });
      T.eq(groups.results, ['surcharge', 'water_1', 'water', 'phreatic'],
           layered ? 'layered' : 'full build');
    });
  });
})();

/* ── A line's seam goes with the line ─────────────────────────────────────
   Where a line splits a layer, the two pieces each draw an edge along it. Hiding the line
   in the Model explorer hid only its dashes, so the seam stayed and nothing seemed to go.
   The seam is drawn with the line instead; the outline of each layer stays the soil's. */
(function () {
  var PROJECT = {
    dimension: 2, layered_soil: true,
    domain: { x0: 0, x1: 10, y_top: 0, y_bottom: -12, z0: 0, z1: 0 },
    layers: [{ id: 'top', top: 0, bottom: -4 }, { id: 'low', top: -4, bottom: -12 }],
    lines: [{ id: 'pit_side', points: [[5, 0], [5, -4]] },
            { id: 'on_the_layers', points: [[0, -4], [10, -4]] }]
  };

  function outline(corners) {
    var flat = [];
    corners.forEach(function (from, index) {
      var to = corners[(index + 1) % corners.length];
      flat.push(from[0], from[1], 0, to[0], to[1], 0);
    });
    return flat;
  }

  // The left piece's edge along the line comes in two segments, as gmsh may mesh it.
  var SECTIONS = [
    { key: 'soil_top__part1', color: '#c8a165',
      edges: outline([[0, 0], [5, 0], [5, -2], [5, -4], [0, -4]]) },
    { key: 'soil_top__part2', color: '#c8a165',
      edges: outline([[5, 0], [10, 0], [10, -4], [5, -4]]) },
    { key: 'soil_low', color: '#8a6d3b',
      edges: outline([[0, -4], [10, -4], [10, -12], [0, -12]]) }
  ];

  function segments(flat) {
    var out = [];
    for (var i = 0; i < flat.length; i += 6) {
      out.push(flat.slice(i, i + 6).map(function (v) { return Math.round(v * 1e6) / 1e6; }));
    }
    return out;
  }

  test("the edges along a line that splits a layer are the line's", function () {
    var cut = App.Viewport.lineSeams(SECTIONS, PROJECT);
    T.eq(cut.seams.map(function (seam) { return [seam.line, seam.section.key]; }),
         [['pit_side', 'soil_top__part1'], ['pit_side', 'soil_top__part2']]);
    T.eq(segments(cut.seams[0].edges), [[5, 0, 0, 5, -2, 0], [5, -2, 0, 5, -4, 0]]);
    T.eq(segments(cut.seams[1].edges), [[5, -4, 0, 5, 0, 0]]);
    T.eq(segments(cut.edges.soil_top__part1),
         [[0, 0, 0, 5, 0, 0], [5, -4, 0, 0, -4, 0], [0, -4, 0, 0, 0, 0]],
         'the left piece keeps its outline, less the seam');
  });

  test("a layer's outline stays the soil's, even where a line runs along it", function () {
    var cut = App.Viewport.lineSeams(SECTIONS, PROJECT);
    T.eq(segments(cut.edges.soil_low), segments(SECTIONS[2].edges));
    T.eq(segments(cut.edges.soil_top__part2),
         [[5, 0, 0, 10, 0, 0], [10, 0, 0, 10, -4, 0], [10, -4, 0, 5, -4, 0]]);
  });

  test('in 3D the edge across the model where the line meets the ground goes too', function () {
    var solid = Object.assign({}, PROJECT, { dimension: 3,
      domain: Object.assign({}, PROJECT.domain, { z0: 0, z1: 6 }) });
    var sections = [{ key: 'soil_top__part1', color: '#c8a165',
                      edges: [5, 0, 0, 5, 0, 6,      // across, at the line's top
                              0, 0, 0, 0, 0, 6,      // across, at the domain's corner
                              5, -4, 6, 5, 0, 6] }]; // along the line, at the back
    var cut = App.Viewport.lineSeams(sections, solid);
    T.eq(segments(cut.seams[0].edges), [[5, 0, 0, 5, 0, 6], [5, -4, 6, 5, 0, 6]]);
    T.eq(segments(cut.edges.soil_top__part1), [[0, 0, 0, 0, 0, 6]]);
  });

  test("without lines every edge is the soil's", function () {
    var cut = App.Viewport.lineSeams(SECTIONS, Object.assign({}, PROJECT, { lines: [] }));
    T.eq(cut.seams, []);
    T.eq(cut.edges.soil_top__part1, SECTIONS[0].edges);
  });
})();

/* Generate mesh meshes the whole model, as kratos-cli mesh does: no volume_keys in
   the request, whatever is selected or hidden. This needs viewport.js, so it runs
   in the browser suite only. */

(function () {
  test('the viewport meshes the whole model, whatever is selected or hidden', function () {
    var saved = { PROJECT: App.PROJECT, state: App.state };
    try {
      App.PROJECT = { layers: [{ id: 'L1' }, { id: 'L2' }], mesh: { element_size: 2.5 } };
      App.state = { mode: 'mesh', selection: 'soil_L1' };
      T.eq(App.Viewport.meshSettings().volume_keys, undefined);
      T.eq(App.Viewport.meshSettings().element_size, 2.5);
    } finally {
      App.PROJECT = saved.PROJECT; App.state = saved.state;
    }
  });
})();
