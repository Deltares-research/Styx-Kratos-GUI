/* live/js/draw-input.js, through real pointer events and the raycaster.

   test-draw-input.js types vertices in through `handleCommand`. This puts a canvas on the
   page and a real camera in front of it, so a click becomes a model point the way the
   viewport makes it -- including the two planes a load is picked on, and the preview
   drawn while the pointer moves. */

(function () {

  function rig(project, cameraAt) {
    var saved = { viewport: App.Viewport, model: App.Model, fetch: window.fetch,
                  project: App.PROJECT, state: App.state, command: App.Command };
    var canvas = document.createElement('canvas');
    canvas.style.cssText = 'position:fixed;left:0;top:0;width:200px;height:200px;';
    document.body.appendChild(canvas);
    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(50, 1, 0.1, 1000);
    camera.position.set(cameraAt[0], cameraAt[1], cameraAt[2]);
    // Looking straight down +Y would leave lookAt() without a basis; up is -Z then.
    camera.up.set(0, cameraAt[1] && !cameraAt[2] ? 0 : 1, cameraAt[1] && !cameraAt[2] ? -1 : 0);
    camera.lookAt(0, 0, 0);
    camera.updateMatrixWorld(true);
    var ctx = { posted: [], notes: [], errors: [], scene: scene, canvas: canvas };
    App.Viewport = {
      getCanvas: function () { return canvas; },
      getScene: function () { return scene; },
      getCamera: function () { return camera; },
      resize: function () {}, refresh: function () { return Promise.resolve(); }
    };
    App.Model = { load: function () { return Promise.resolve(); } };
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
  var TOP_DOWN = [0, 10, 0];
  var FACE_ON = [0, 0, 10];

  test('draw: a click lands on the ground plane under the pointer', function () {
    var ctx = rig(SECTION, TOP_DOWN);
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
    } finally { ctx.restore(); }
  });

  test('draw: with snapping on, a click lands on whole metres', function () {
    var ctx = rig(SECTION, TOP_DOWN);
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
    } finally { ctx.restore(); }
  });

  test('draw: a keyboard "click" (detail 0) places nothing', function () {
    var ctx = rig(SECTION, TOP_DOWN);
    try {
      App.DrawInput.start('box');
      ctx.canvas.dispatchEvent(new MouseEvent('click', { bubbles: true, detail: 0 }));
      at(ctx, 'click');
      T.eq(ctx.posted.length, 0, 'one real click so far, and a box needs two');
    } finally { ctx.restore(); }
  });

  test('draw: moving the pointer previews the shape being drawn', function () {
    var ctx = rig(SECTION, TOP_DOWN);
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
    } finally { ctx.restore(); }
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
