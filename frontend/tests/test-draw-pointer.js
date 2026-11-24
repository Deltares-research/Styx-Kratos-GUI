/* frontend/js/draw-input.js, through real pointer events and the raycaster.

   test-draw-input.js types vertices in through `handleCommand`. This puts a canvas on the
   page and a real camera in front of it, so a click becomes a model point the way the
   viewport makes it -- including the two planes a load is picked on, and the preview
   drawn while the pointer moves. */

(function () {

  function rig(project, cameraAt) {
    var saved = { viewport: App.Viewport, model: App.Model, fetch: window.fetch,
                  project: App.PROJECT, state: App.state, command: App.Command,
                  explorer: App.Explorer, select: App.selectObject };
    var canvas = document.createElement('canvas');
    canvas.style.cssText = 'position:fixed;left:0;top:0;width:200px;height:200px;';
    document.body.appendChild(canvas);
    var scene = new THREE.Scene();
    // A camera of the test's own (the section view's, below), or a perspective one at
    // `cameraAt` looking at the origin.
    var camera = cameraAt.isCamera ? cameraAt : new THREE.PerspectiveCamera(50, 1, 0.1, 1000);
    if (!cameraAt.isCamera) {
      camera.position.set(cameraAt[0], cameraAt[1], cameraAt[2]);
      // Looking straight down +Y would leave lookAt() without a basis; up is -Z then.
      camera.up.set(0, cameraAt[1] && !cameraAt[2] ? 0 : 1, cameraAt[1] && !cameraAt[2] ? -1 : 0);
      camera.lookAt(0, 0, 0);
    }
    camera.updateMatrixWorld(true);
    var ctx = { posted: [], notes: [], errors: [], scene: scene, canvas: canvas };
    App.Viewport = {
      getCanvas: function () { return canvas; },
      getScene: function () { return scene; },
      getCamera: function () { return camera; },
      resize: function () {}, refresh: function () { return Promise.resolve(); }
    };
    App.Model = { load: function () { return Promise.resolve(); } };
    App.Explorer = { mountTree: function () {} };
    App.selectObject = function () {};
    App.PROJECT = project;
    App.state = { mode: 'soil' };
    App.Command = { note: function (t) { ctx.notes.push(t); },
                    ok: function () {}, err: function (t) { ctx.errors.push(t); } };
    window.fetch = function (url, options) {
      ctx.posted.push(JSON.parse(options.body));
      return Promise.resolve({ ok: true, json: function () {
        return Promise.resolve({ parts: [{ key: 'drawn_0' }] }); } });
    };
    // A listener that throws does not throw into dispatchEvent's caller: it is reported
    // on the window. Caught here so the test can say so instead of leaking it.
    function onError(event) { ctx.errors.push(event.message); event.preventDefault(); }
    window.addEventListener('error', onError);
    ctx.restore = function () {
      App.DrawInput.cancel();
      window.removeEventListener('error', onError);
      canvas.remove();
      App.Viewport = saved.viewport; App.Model = saved.model; window.fetch = saved.fetch;
      App.PROJECT = saved.project; App.state = saved.state; App.Command = saved.command;
      App.Explorer = saved.explorer; App.selectObject = saved.select;
    };
    return ctx;
  }

  function at(ctx, type, dx, dy) {
    var r = ctx.canvas.getBoundingClientRect();
    ctx.canvas.dispatchEvent(new MouseEvent(type, {
      clientX: r.left + r.width / 2 + (dx || 0), clientY: r.top + r.height / 2 + (dy || 0),
      bubbles: true, cancelable: true, detail: 1 }));
  }

  function preview(ctx) {
    return ctx.scene.children.filter(function (c) { return c.name === 'draw-preview'; })[0];
  }

  var SECTION = { dimension: 2,
                  domain: { x0: 0, x1: 20, z0: 0, z1: 20, y_top: 3, y_bottom: -15 } };
  // The plan view, looking down on the ground plane y = 0, is the solid model's: a 2D
  // model is always seen face on, and every pick in it lands on the section.
  var SOLID = { dimension: 3, domain: SECTION.domain };
  var TOP_DOWN = [0, 10, 0];
  var FACE_ON = [0, 0, 10];

  test('draw: a rejected geometry recipe reports the server reason without reloading', function () {
    var ctx = rig(SOLID, TOP_DOWN), loaded = 0;
    App.Model.load = function () { loaded += 1; return Promise.resolve(); };
    window.fetch = function () {
      return Promise.resolve({ ok: false, json: function () {
        return Promise.resolve({ detail: 'The polygon intersects itself' });
      } });
    };
    var promise = Promise.resolve().then(function () {
      App.DrawInput.start('point');
      App.DrawInput.handleCommand('0 0 0');
      return new Promise(function (resolve) { setTimeout(resolve, 0); });
    }).then(function () {
      T.eq(ctx.errors, ['Error creating geometry: The polygon intersects itself']);
      T.eq(loaded, 0);
      T.eq(ctx.canvas.style.cursor, '', 'the draw mode ends even if the request fails');
    });
    return promise.then(function () { ctx.restore(); },
                        function (error) { ctx.restore(); throw error; });
  });

  test('draw: a completed recipe reloads, redraws and selects the created part in order', function () {
    var ctx = rig(SOLID, TOP_DOWN);
    var saved = { Explorer: App.Explorer, selectObject: App.selectObject }, calls = [];
    App.Model.load = function () { calls.push('load'); return Promise.resolve(); };
    App.Viewport.refresh = function () { calls.push('refresh'); return Promise.resolve(); };
    App.Explorer = { mountTree: function (mode) { calls.push('tree:' + mode); } };
    App.selectObject = function (key, source) { calls.push('select:' + key + ':' + source); };
    function restore() { Object.assign(App, saved); ctx.restore(); }
    return Promise.resolve().then(function () {
      App.DrawInput.start('point');
      App.DrawInput.handleCommand('0 0 0');
      return new Promise(function (resolve) { setTimeout(resolve, 0); });
    }).then(function () {
      T.eq(calls, ['load', 'refresh', 'tree:soil', 'select:drawn_0:tree']);
      T.eq(ctx.errors, []);
    }).then(restore, function (error) { restore(); throw error; });
  });

  /* What the viewport draws a 2D model with (js/viewport.js `camOrtho`, SECTION_VIEW):
     an orthographic camera facing -z, centred on the section rather than on the
     origin. Every ray it casts runs along z, so it meets the plane y = 0 nowhere --
     unlike FACE_ON's, which all start on that plane. 40 m across the 200 px canvas,
     centred on x = 10, y = -6: a pixel is 0.2 m. */
  function sectionCamera() {
    var camera = new THREE.OrthographicCamera(-20, 20, 20, -20, 0.1, 1000);
    camera.position.set(10, -6, 50);
    camera.lookAt(10, -6, 0);
    return camera;
  }

  test('draw: a click lands on the ground plane under the pointer', async function () {
    var ctx = rig(SOLID, TOP_DOWN);
    try {
      App.DrawInput.start('box');
      at(ctx, 'click');
      at(ctx, 'click', 40, 40);
      var recipe = ctx.posted[0];
      T.eq(recipe.kind, 'box');
      T.near(recipe.origin[0], 0, 1e-6);
      T.near(recipe.origin[1], 0, 1e-6);
      T.near(recipe.origin[2], 0, 1e-6);
      T.ok(recipe.size[0] !== 0, 'the second click is somewhere else');
    } finally { await new Promise(function (resolve) { setTimeout(resolve, 0); }); ctx.restore(); }
  });

  test('draw: with snapping on, a click lands on whole metres', async function () {
    var ctx = rig(SOLID, TOP_DOWN);
    try {
      App.state.snap = true;
      App.DrawInput.start('line');
      at(ctx, 'click', 13, 7);
      at(ctx, 'click', 57, 31);
      T.eq(ctx.posted.length, 0, 'a line waits for Enter or a right-click');
      at(ctx, 'contextmenu');
      ctx.posted[0].vertices.forEach(function (point) {
        point.forEach(function (c) { T.eq(c, Math.round(c), 'snapped: ' + point); });
      });
    } finally { await new Promise(function (resolve) { setTimeout(resolve, 0); }); ctx.restore(); }
  });

  test('draw: a click snaps to the status bar\'s snapping distance', async function () {
    var ctx = rig(SOLID, TOP_DOWN);
    try {
      App.state.snap = true;
      App.state.snapDistance = 0.25;
      App.DrawInput.start('line');
      at(ctx, 'click', 13, 7);
      at(ctx, 'click', 57, 31);
      at(ctx, 'contextmenu');
      ctx.posted[0].vertices.forEach(function (point) {
        point.forEach(function (c) {
          T.eq(c * 4, Math.round(c * 4), 'on a quarter metre: ' + point);
        });
      });
      T.ok(ctx.posted[0].vertices.some(function (point) {
        return point.some(function (c) { return c !== Math.round(c); });
      }), 'not merely whole metres: ' + JSON.stringify(ctx.posted[0].vertices));
    } finally { await new Promise(function (resolve) { setTimeout(resolve, 0); }); ctx.restore(); }
  });

  function key(target, name) {
    target.dispatchEvent(new KeyboardEvent('keydown', { key: name, bubbles: true }));
  }

  test('draw: Enter applying a typed value in a field does not finish the line',
       async function () {
    var ctx = rig(SOLID, TOP_DOWN);
    var field = document.createElement('input');
    field.value = field.defaultValue = '1';
    document.body.appendChild(field);
    try {
      App.DrawInput.start('line');
      at(ctx, 'click', 13, 7);
      at(ctx, 'click', 57, 31);
      field.value = '0.5';                       // typed, not yet applied
      key(field, 'Enter');
      T.eq(ctx.posted.length, 0, 'the Enter applying the edit is the field\'s');
      field.defaultValue = '0.5';                // applied, as app.js does on change
      key(field, 'Enter');
      T.eq(ctx.posted.length, 1, 'with nothing pending, Enter in the field finishes it');
    } finally {
      field.remove();
      await new Promise(function (resolve) { setTimeout(resolve, 0); }); ctx.restore();
    }
  });

  test('draw: Escape in a field cancels the drawing', async function () {
    var ctx = rig(SOLID, TOP_DOWN);
    var field = document.createElement('input');
    field.value = '0.5';                         // even with an edit pending
    document.body.appendChild(field);
    try {
      App.DrawInput.start('polygon');
      at(ctx, 'click', 13, 7);
      at(ctx, 'click', 57, 31);
      at(ctx, 'click', -20, 31);
      key(field, 'Escape');
      key(document, 'Enter');
      T.eq(ctx.posted.length, 0, 'cancelled, so a later Enter has nothing to finish');
    } finally {
      field.remove();
      await new Promise(function (resolve) { setTimeout(resolve, 0); }); ctx.restore();
    }
  });

  test('draw: a keyboard "click" (detail 0) places nothing', function () {
    var ctx = rig(SOLID, TOP_DOWN);
    try {
      App.DrawInput.start('box');
      ctx.canvas.dispatchEvent(new MouseEvent('click', { bubbles: true, detail: 0 }));
      at(ctx, 'click');
      T.eq(ctx.posted.length, 0, 'one real click so far, and a box needs two');
    } finally { ctx.restore(); }
  });

  test('draw: moving the pointer previews the shape being drawn', async function () {
    var ctx = rig(SOLID, TOP_DOWN);
    try {
      App.DrawInput.start('polygon');
      at(ctx, 'click');
      at(ctx, 'click', 30, 0);
      at(ctx, 'mousemove', 30, 30);
      var shapes = preview(ctx).children;
      T.ok(shapes.some(function (c) { return c.isMesh && c.geometry.type === 'ShapeGeometry'; }),
           'a polygon of three points is filled in');
      T.ok(shapes.some(function (c) { return c.isLine; }));
      at(ctx, 'click', 30, 30);
      at(ctx, 'contextmenu');
      T.eq(ctx.posted[0].kind, 'polygon');
      T.eq(preview(ctx).children.length, 0, 'the preview goes once it is committed');
    } finally { await new Promise(function (resolve) { setTimeout(resolve, 0); }); ctx.restore(); }
  });

  test('draw: a load in the section is picked on the section and put on the ground', function () {
    var ctx = rig(SECTION, FACE_ON);
    var completed = null;
    try {
      App.DrawInput.start('load', { onComplete: function (points) { completed = points; } });
      at(ctx, 'click', -20, 30);
      at(ctx, 'click', 20, 30);
      T.ok(completed, 'two clicks complete a load');
      completed.forEach(function (p) {
        T.eq(p[1], 3, 'on the ground surface, wherever the pointer was vertically');
        T.near(p[2], 0, 1e-6, 'on the section plane');
      });
      T.ok(completed[0][0] < completed[1][0]);
      T.eq(ctx.posted.length, 0, 'a load is handed back, not created as geometry');
    } finally { ctx.restore(); }
  });

  /* The Flow conditions tools "Water pressure line" and "Seepage line", and the
     Structures ones for a support line, start a 'line' that hands its points back
     (js/boundary-conditions.js `draw`). A line used to be picked on the ground plane
     y = 0 in 2D as well, which the section camera looks along: no click placed a
     vertex, and the right-click said "Not enough vertices for line". */
  test('draw: in the section a line is picked where the 2D camera points', function () {
    var ctx = rig(SECTION, sectionCamera());
    var completed = null;
    try {
      App.DrawInput.start('line', { count: 1,
                                    onComplete: function (points) { completed = points; } });
      at(ctx, 'click', -50, 0);
      at(ctx, 'click', 50, 25);
      at(ctx, 'mousemove', 60, 30);
      T.ok(preview(ctx).children.some(function (c) { return c.isLine; }),
           'the line is previewed from its clicks to the pointer');
      at(ctx, 'contextmenu', 60, 30);
      T.eq(ctx.errors, [], 'no "Not enough vertices for line"');
      T.ok(completed, 'two clicks and a right-click complete the line');
      T.eq(completed.length, 2);
      T.near(completed[0][0], 0, 1e-6, 'x under the first click');
      T.near(completed[0][1], -6, 1e-6, 'y under the first click: not the ground');
      T.near(completed[1][0], 20, 1e-6, 'x under the second click');
      T.near(completed[1][1], -11, 1e-6, 'y under the second click');
      completed.forEach(function (p) { T.near(p[2], 0, 1e-6, 'on the section plane'); });
      T.eq(ctx.posted.length, 0, 'handed back to the tool, not created as geometry');
    } finally { ctx.restore(); }
  });

  test('draw: in the section a drawn line is created where it was clicked', async function () {
    var ctx = rig(SECTION, sectionCamera());
    try {
      App.DrawInput.start('line');
      at(ctx, 'click', -50, 0);
      at(ctx, 'click', 50, 25);
      at(ctx, 'contextmenu');
      T.eq(ctx.posted.length, 1, 'Structures > Create line sends its recipe');
      T.eq(ctx.posted[0].vertices.map(function (p) {
        return p.map(function (c) { return Math.round(c * 1e6) / 1e6; });
      }), [[0, -6, 0], [20, -11, 0]]);
    } finally { await new Promise(function (resolve) { setTimeout(resolve, 0); }); ctx.restore(); }
  });

  /* "Water pressure point" and "Point prescribed displacement": one click, and the
     condition is there -- not moved up to the ground surface, as a line load is. */
  test('draw: a boundary condition point is where it was clicked', function () {
    var ctx = rig(SECTION, sectionCamera());
    var completed = null;
    try {
      App.DrawInput.start('load', { count: 1, atPointer: true,
                                    onComplete: function (points) { completed = points; } });
      at(ctx, 'click', 25, 50);
      T.ok(completed, 'one click places the point');
      T.near(completed[0][0], 15, 1e-6);
      T.near(completed[0][1], -16, 1e-6, 'at the click, below the ground at y = 3');
    } finally { ctx.restore(); }
  });

  test('draw: a load being placed is previewed as it is drawn', function () {
    var ctx = rig(SECTION, FACE_ON);
    try {
      App.DrawInput.start('load', { onComplete: function () {} });
      at(ctx, 'click', -20, 0);
      at(ctx, 'mousemove', 20, 0);
      T.ok(preview(ctx).children.some(function (c) { return c.isLine; }),
           'the load is drawn from the first click to the pointer');
    } finally { ctx.restore(); }
  });

  test('draw: a right-click while placing a load does not throw', function () {
    var ctx = rig(SECTION, FACE_ON);
    try {
      App.DrawInput.start('load', { onComplete: function () {} });
      at(ctx, 'click', -20, 0);
      at(ctx, 'contextmenu', 20, 0);
      T.eq(ctx.errors, [], 'no exception from the right-click');
    } finally { ctx.restore(); }
  });

  test('draw: in the solid model a load previews as its footprint in plan', function () {
    var ctx = rig({ dimension: 3, domain: SECTION.domain }, [0, 20, 0]);
    try {
      App.DrawInput.start('load', { onComplete: function () {} });
      at(ctx, 'click', -10, -10);
      at(ctx, 'mousemove', 10, 10);
      var line = preview(ctx).children.filter(function (c) { return c.isLine; })[0];
      var p = line.geometry.getAttribute('position');
      var xs = {}, zs = {}, ys = {};
      for (var i = 0; i < p.count; i++) {
        xs[p.getX(i).toFixed(6)] = 1; ys[p.getY(i).toFixed(6)] = 1; zs[p.getZ(i).toFixed(6)] = 1;
      }
      T.eq(p.count, 5, 'a closed rectangle');
      T.eq(Object.keys(ys).length, 1, 'flat on the ground');
      T.eq([Object.keys(xs).length, Object.keys(zs).length], [2, 2], 'spanning x and z');
    } finally { ctx.restore(); }
  });

  test('draw: in the solid model a load is picked on the ground surface', function () {
    var solid = { dimension: 3, domain: SECTION.domain };
    var ctx = rig(solid, [0, 20, 0]);
    var completed = null;
    try {
      App.DrawInput.start('load', { onComplete: function (points) { completed = points; } });
      at(ctx, 'click', -10, -10);
      at(ctx, 'click', 10, 10);
      completed.forEach(function (p) { T.near(p[1], 3, 1e-6, 'y = y_top'); });
      T.ok(completed[0][2] !== completed[1][2], 'a footprint in plan, not a line');
    } finally { ctx.restore(); }
  });

})();
