/* ══════════════════════════════════════════════════════════════════
   test-canvas-renderer.js

   A CPU renderer for the scene, used when the browser gives no WebGL context.
   It has to be a drop-in for the three calls viewport.js makes of a renderer --
   setPixelRatio, setSize, render -- because everything else the viewport does
   (the scene graph, both cameras, picking, the orbit, the 2D section) is
   arithmetic that never needed a GPU in the first place.

   The assertions run against a recording 2D context rather than pixels: what
   matters is which primitives were emitted, in which order, in what colour.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  /* Records every call and property set, so a test can assert on the drawing
     rather than on an image. */
  function recorder() {
    var calls = [];
    var ctx = {
      calls: calls,
      fillStyle: null, strokeStyle: null, lineWidth: 1, globalAlpha: 1,
      canvas: { width: 200, height: 100 }
    };
    ['save', 'restore', 'beginPath', 'moveTo', 'lineTo', 'closePath', 'fill',
     'stroke', 'clearRect', 'setTransform', 'scale', 'fillRect'].forEach(function (name) {
      ctx[name] = function () {
        calls.push({ op: name, args: Array.prototype.slice.call(arguments),
                     fill: ctx.fillStyle, stroke: ctx.strokeStyle, alpha: ctx.globalAlpha });
      };
    });
    return ctx;
  }

  function fakeCanvas() {
    var ctx = recorder();
    return { width: 200, height: 100, style: {},
             getContext: function () { return ctx; }, ctx: ctx };
  }

  /* An orthographic camera looking down -z at the origin: a triangle in the
     z = 0 plane maps predictably onto the middle of the canvas. */
  function orthoCamera() {
    var cam = new THREE.OrthographicCamera(-10, 10, 5, -5, 0.1, 100);
    cam.position.set(0, 0, 10);
    cam.up.set(0, 1, 0);
    cam.lookAt(0, 0, 0);
    cam.updateMatrixWorld(true);
    return cam;
  }

  function triangleAt(z, color) {
    var g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array([
      -2, -2, z, 2, -2, z, 0, 2, z
    ]), 3));
    return new THREE.Mesh(g, new THREE.MeshLambertMaterial({ color: color }));
  }

  function fillsIn(ctx) {
    return ctx.calls.filter(function (c) { return c.op === 'fill'; });
  }

  test('a mesh triangle is filled in its material colour', function () {
    var canvas = fakeCanvas();
    var r = new App.CanvasRenderer(canvas);
    var scene = new THREE.Scene();
    scene.add(triangleAt(0, 0xff0000));
    r.setSize(200, 100, false);
    r.render(scene, orthoCamera());

    var fills = fillsIn(canvas.ctx);
    T.eq(fills.length, 1, 'one triangle, one fill');
    // Lambert shading darkens the flat colour, so assert the hue, not the value.
    T.ok(/^rgb\(\d+, *0, *0\)$/.test(fills[0].fill), 'red stayed red: ' + fills[0].fill);
  });

  test('triangles are painted far to near', function () {
    var canvas = fakeCanvas();
    var r = new App.CanvasRenderer(canvas);
    var scene = new THREE.Scene();
    scene.add(triangleAt(2, 0x00ff00));    // nearer the camera at z = 10
    scene.add(triangleAt(-2, 0x0000ff));   // farther
    r.setSize(200, 100, false);
    r.render(scene, orthoCamera());

    // Without a depth buffer, order *is* the depth test: the far one must be laid
    // down first so the near one covers it.
    var fills = fillsIn(canvas.ctx);
    T.eq(fills.length, 2);
    T.ok(/0, *0, *\d+\)$/.test(fills[0].fill), 'blue (far) first: ' + fills[0].fill);
    T.ok(/0, *\d+, *0\)$/.test(fills[1].fill), 'green (near) second: ' + fills[1].fill);
  });

  test('invisible objects are not drawn', function () {
    var canvas = fakeCanvas();
    var r = new App.CanvasRenderer(canvas);
    var scene = new THREE.Scene();
    var group = new THREE.Group();
    group.add(triangleAt(0, 0xff0000));
    group.visible = false;               // how setMode/setVisible hide a body
    scene.add(group);
    r.setSize(200, 100, false);
    r.render(scene, orthoCamera());
    T.eq(fillsIn(canvas.ctx).length, 0, 'a hidden group draws nothing');
  });

  test('line segments are stroked, not filled', function () {
    var canvas = fakeCanvas();
    var r = new App.CanvasRenderer(canvas);
    var scene = new THREE.Scene();
    var g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(
      new Float32Array([-2, 0, 0, 2, 0, 0]), 3));
    scene.add(new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: 0x000000 })));
    r.setSize(200, 100, false);
    r.render(scene, orthoCamera());

    var ops = canvas.ctx.calls.map(function (c) { return c.op; });
    T.ok(ops.indexOf('stroke') >= 0, 'the edge was stroked');
    T.eq(fillsIn(canvas.ctx).length, 0, 'and not filled');
  });

  test('geometry behind the camera is dropped rather than mirrored', function () {
    // A perspective camera divides by w. A vertex behind the eye has w <= 0 and
    // projects to a mirrored ghost on screen if it is not clipped away first.
    var canvas = fakeCanvas();
    var r = new App.CanvasRenderer(canvas);
    var cam = new THREE.PerspectiveCamera(50, 2, 0.5, 100);
    cam.position.set(0, 0, 5);
    cam.lookAt(0, 0, 0);
    cam.updateMatrixWorld(true);

    var scene = new THREE.Scene();
    scene.add(triangleAt(20, 0xff0000));     // 15 units behind the camera
    r.setSize(200, 100, false);
    r.render(scene, cam);
    T.eq(fillsIn(canvas.ctx).length, 0, 'nothing behind the eye is drawn');
  });

  test('setSize and setPixelRatio size the backing store like WebGLRenderer', function () {
    var canvas = fakeCanvas();
    var r = new App.CanvasRenderer(canvas);
    r.setPixelRatio(2);
    r.setSize(200, 100, false);
    T.eq(canvas.width, 400, 'backing store is scaled by the ratio');
    T.eq(canvas.height, 200);
    // updateStyle false: the CSS size is the layout's business, as in three.js.
    T.eq(canvas.style.width, undefined);
  });

  /* Every other test here asserts on recorded draw calls, which proves the geometry
     was walked but not that anything reaches the screen. This one renders to a real
     canvas and reads the pixels back: it is the assertion that would have caught a
     blank viewport. */
  test('it puts actual pixels on a real canvas', function () {
    var canvas = document.createElement('canvas');
    var r = new App.CanvasRenderer(canvas);
    r.setSize(120, 80, false);

    var scene = new THREE.Scene();
    scene.add(triangleAt(0, 0xff0000));
    r.render(scene, orthoCamera());

    var data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
    var painted = 0;
    for (var i = 3; i < data.length; i += 4) if (data[i] > 0) painted++;
    T.ok(painted > 200, 'the triangle covered real pixels, got ' + painted);
  });

  test('it identifies itself as the software path', function () {
    T.eq(new App.CanvasRenderer(fakeCanvas()).isSoftware, true);
  });

  test('disposing a software renderer leaves the caller-owned canvas intact', function () {
    var canvas = fakeCanvas();
    var renderer = new App.CanvasRenderer(canvas);
    renderer.setSize(120, 80);
    renderer.dispose();
    renderer.dispose();
    T.eq(renderer.domElement, canvas);
    T.eq([canvas.width, canvas.height], [120, 80]);
    T.eq([canvas.style.width, canvas.style.height], ['120px', '80px']);
  });
})();
