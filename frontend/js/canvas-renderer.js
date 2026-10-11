/* ══════════════════════════════════════════════════════════════════
   canvas-renderer.js — a CPU renderer, for when there is no WebGL context.

   Chrome no longer falls back to software rendering: if the GPU process refuses a
   context, `new THREE.WebGLRenderer()` throws and the viewport is simply blank.
   Blank is the worst possible answer, because a model that is there and a model
   that failed to build look identical.

   Almost none of the viewport needs a GPU. The scene graph, both cameras, the
   orbit, the raycaster used for picking and the whole 2D sectioning path are
   arithmetic. Only the last step -- turning triangles into pixels -- was ever
   WebGL's job, and viewport.js asks a renderer for exactly three things:

       setPixelRatio(r)   setSize(w, h, updateStyle)   render(scene, camera)

   So this implements those three against a 2D canvas context and is otherwise a
   drop-in. What it gives up is stated plainly rather than hidden:

   *   No depth buffer. Faces are sorted by view-space depth and painted far to
       near, which is exact for the convex, non-intersecting solids the server
       sends and wrong only where two faces interpenetrate.
   *   Flat shading, one directional term plus ambient, evaluated per face rather
       than per pixel. Smooth-shaded curves read as facets.
   *   No sprites. The axis labels are textured quads and are skipped.
   ══════════════════════════════════════════════════════════════════ */

(function (App) {
  'use strict';

  // Matches the hemisphere + two directional lights in viewport.js closely enough
  // that a body keeps its colour identity. Exactness is not the goal; legibility is.
  var AMBIENT = 0.45;
  var KEY_LIGHT = new THREE.Vector3(-0.35, -0.5, 0.79).normalize();

  /* Painting every triangle of a dense mesh through the 2D context is far slower
     than a GPU, and a wireframe of a real mesh can run to hundreds of thousands of
     segments. Past this the frame is dropped rather than freezing the tab; the
     viewport reports it instead of appearing to hang. */
  var MAX_PRIMITIVES = 120000;

  function CanvasRenderer(canvas) {
    this.domElement = canvas;
    this.isSoftware = true;
    this.dropped = 0;               // primitives skipped by the budget, last frame
    this._ctx = canvas.getContext('2d');
    this._ratio = 1;
    this._w = canvas.width || 1;
    this._h = canvas.height || 1;

    // Scratch, reused every frame: a renderer that allocates per triangle spends
    // more time in the garbage collector than in arithmetic.
    this._mv = new THREE.Matrix4();
    this._v = [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()];
    this._n = new THREE.Vector3();
    this._ab = new THREE.Vector3();
    this._ac = new THREE.Vector3();
  }

  CanvasRenderer.prototype.setPixelRatio = function (ratio) {
    this._ratio = ratio || 1;
  };

  /* Mirrors WebGLRenderer: the drawing buffer is w*ratio, and `updateStyle` false
     leaves the CSS size to the layout. */
  CanvasRenderer.prototype.setSize = function (w, h, updateStyle) {
    this._w = w;
    this._h = h;
    this.domElement.width = Math.floor(w * this._ratio);
    this.domElement.height = Math.floor(h * this._ratio);
    if (updateStyle !== false) {
      this.domElement.style.width = w + 'px';
      this.domElement.style.height = h + 'px';
    }
  };

  CanvasRenderer.prototype.dispose = function () {};

  /* ── Projection ─────────────────────────────────────────────────
     Vertices go object → view (for depth and lighting) → clip → screen. The view
     step is kept because both depth sorting and flat shading need it, and doing it
     twice is cheaper than reconstructing it from clip space. */

  function toScreen(view, camera, w, h, out) {
    out.copy(view).applyMatrix4(camera.projectionMatrix);
    // applyMatrix4 on a Vector3 performs the perspective divide for us; what it
    // cannot tell us is whether w was positive, so the caller checks view.z first.
    out.x = (out.x * 0.5 + 0.5) * w;
    out.y = (-out.y * 0.5 + 0.5) * h;
    return out;
  }

  function colorOf(material) {
    return (material && material.color) || null;
  }

  function shade(color, intensity, emissive) {
    var r = color.r * intensity, g = color.g * intensity, b = color.b * intensity;
    if (emissive) { r += emissive.r; g += emissive.g; b += emissive.b; }
    return 'rgb(' + Math.round(Math.min(r, 1) * 255) + ', '
                  + Math.round(Math.min(g, 1) * 255) + ', '
                  + Math.round(Math.min(b, 1) * 255) + ')';
  }

  function positionsOf(geometry) {
    var attr = geometry && geometry.attributes && geometry.attributes.position;
    return attr ? attr.array : null;
  }

  CanvasRenderer.prototype.render = function (scene, camera) {
    var ctx = this._ctx;
    if (!ctx) return;

    var w = this.domElement.width, h = this.domElement.height;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, w, h);

    scene.updateMatrixWorld(true);
    camera.updateMatrixWorld(true);
    if (camera.matrixWorldInverse) camera.matrixWorldInverse.copy(camera.matrixWorld).invert();

    var jobs = [];
    var self = this;
    this.dropped = 0;

    // traverseVisible skips a hidden object *and its subtree*, which is exactly how
    // setMode and the eye toggles hide a body: they set visible on the group.
    scene.traverseVisible(function (obj) {
      if (obj.isMesh) self._collectMesh(obj, camera, w, h, jobs);
      else if (obj.isLineSegments || obj.isLine) self._collectLine(obj, camera, w, h, jobs);
      // Sprites (the axis labels) and Points have no counterpart here.
    });

    // Far to near: with no depth buffer, paint order is the depth test.
    jobs.sort(function (a, b) { return a.depth - b.depth; });

    if (jobs.length > MAX_PRIMITIVES) {
      // Keep the nearest, which is what the user is looking at.
      this.dropped = jobs.length - MAX_PRIMITIVES;
      jobs = jobs.slice(jobs.length - MAX_PRIMITIVES);
    }

    for (var i = 0; i < jobs.length; i++) jobs[i].draw(ctx);
  };

  CanvasRenderer.prototype._collectMesh = function (mesh, camera, w, h, jobs) {
    var array = positionsOf(mesh.geometry);
    if (!array) return;
    var color = colorOf(mesh.material);
    if (!color) return;

    var index = mesh.geometry.index ? mesh.geometry.index.array : null;
    var count = index ? index.length : array.length / 3;
    if (count < 3) return;

    this._mv.multiplyMatrices(camera.matrixWorldInverse, mesh.matrixWorld);

    var material = mesh.material;
    var opacity = material.transparent ? (material.opacity === undefined ? 1 : material.opacity) : 1;
    var emissive = material.emissive;
    var v = this._v;

    for (var i = 0; i + 2 < count; i += 3) {
      var ok = true;
      for (var k = 0; k < 3; k++) {
        var at = (index ? index[i + k] : i + k) * 3;
        v[k].set(array[at], array[at + 1], array[at + 2]).applyMatrix4(this._mv);
        // In view space the camera looks down -z, so anything with z >= 0 is at or
        // behind the eye. Dropping the whole triangle is coarser than clipping it
        // against the near plane, but it never produces a mirrored ghost.
        if (v[k].z >= -1e-6) ok = false;
      }
      if (!ok) continue;

      this._ab.subVectors(v[1], v[0]);
      this._ac.subVectors(v[2], v[0]);
      this._n.crossVectors(this._ab, this._ac);
      if (this._n.lengthSq() < 1e-20) continue;      // degenerate
      this._n.normalize();

      // Two-sided: a section cut shows the inside of a solid, and there is no
      // back-face culling to hide it.
      var lambert = Math.abs(this._n.dot(KEY_LIGHT));
      var fill = shade(color, AMBIENT + (1 - AMBIENT) * lambert, emissive);

      var depth = (v[0].z + v[1].z + v[2].z) / 3;
      jobs.push(triangleJob(
        toScreen(v[0], camera, w, h, new THREE.Vector3()),
        toScreen(v[1], camera, w, h, new THREE.Vector3()),
        toScreen(v[2], camera, w, h, new THREE.Vector3()),
        fill, opacity, depth));
    }
  };

  function triangleJob(a, b, c, fill, opacity, depth) {
    return {
      depth: depth,
      draw: function (ctx) {
        ctx.globalAlpha = opacity;
        ctx.fillStyle = fill;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.lineTo(c.x, c.y);
        ctx.closePath();
        // A hairline stroke in the fill colour closes the seams between adjacent
        // triangles that antialiasing would otherwise leave as a visible mesh.
        ctx.strokeStyle = fill;
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.fill();
        ctx.globalAlpha = 1;
      }
    };
  }

  CanvasRenderer.prototype._collectLine = function (line, camera, w, h, jobs) {
    var array = positionsOf(line.geometry);
    if (!array) return;
    var color = colorOf(line.material);
    if (!color) return;

    var index = line.geometry.index ? line.geometry.index.array : null;
    var count = index ? index.length : array.length / 3;
    var strip = !line.isLineSegments;         // Line draws a continuous polyline
    var step = strip ? 1 : 2;

    this._mv.multiplyMatrices(camera.matrixWorldInverse, line.matrixWorld);

    var material = line.material;
    var opacity = material.transparent ? (material.opacity === undefined ? 1 : material.opacity) : 1;
    var stroke = shade(color, 1, null);
    var v = this._v;

    for (var i = 0; i + 1 < count; i += step) {
      var ok = true;
      for (var k = 0; k < 2; k++) {
        var at = (index ? index[i + k] : i + k) * 3;
        v[k].set(array[at], array[at + 1], array[at + 2]).applyMatrix4(this._mv);
        if (v[k].z >= -1e-6) ok = false;
      }
      if (!ok) continue;

      jobs.push(segmentJob(
        toScreen(v[0], camera, w, h, new THREE.Vector3()),
        toScreen(v[1], camera, w, h, new THREE.Vector3()),
        stroke, opacity, (v[0].z + v[1].z) / 2));
    }
  };

  function segmentJob(a, b, stroke, opacity, depth) {
    return {
      // Nudged towards the camera so an edge is not swallowed by the face it
      // outlines, which shares its depth almost exactly.
      depth: depth + 1e-3,
      draw: function (ctx) {
        ctx.globalAlpha = opacity;
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
    };
  }

  CanvasRenderer.MAX_PRIMITIVES = MAX_PRIMITIVES;
  App.CanvasRenderer = CanvasRenderer;

})(window.App = window.App || {});
