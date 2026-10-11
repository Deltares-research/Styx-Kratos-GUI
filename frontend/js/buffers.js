/* ══════════════════════════════════════════════════════════════════
   buffers.js — server payload → THREE geometry.

   Pure functions, no DOM and no scene: everything here is testable in
   isolation, which matters because a winding or stride mistake shows up as
   plausible-looking garbage rather than an exception.

   The server sends flat arrays and no normals. That is deliberate: the STL
   tessellation it comes from has no parametric surface to query, and the
   faceted look wants flat shading anyway.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Buffers = (function () {

  var FOV_DEG = 42;          // js/viewport.js:429, so framing matches the frozen camera
  var FIT_MARGIN = 1.06;

  /* One section as a drawable, flat-shaded BufferGeometry.

     Expanded to non-indexed. Sharing a vertex between faces makes
     computeVertexNormals average their normals, which rounds every box corner
     off; per-triangle vertices give exact face normals. At this size (tens of
     thousands of triangles) the extra memory is not worth an index buffer. */
  function geometry(section) {
    var src = section.positions, idx = section.indices;
    var out = new Float32Array(idx.length * 3);

    for (var i = 0; i < idx.length; i++) {
      var v = idx[i] * 3;
      out[i * 3]     = src[v];
      out[i * 3 + 1] = src[v + 1];
      out[i * 3 + 2] = src[v + 2];
    }

    var geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(out, 3));
    geo.computeVertexNormals();
    return geo;
  }

  /* The B-rep edges, already in LineSegments order (pairs of endpoints). */
  function edges(section) {
    var geo = new THREE.BufferGeometry();
    geo.setAttribute('position',
      new THREE.BufferAttribute(new Float32Array(section.edges), 3));
    return geo;
  }

  /* Camera framing derived from the model instead of hardcoded.

     js/viewport.js:435 and :641 both use radius 118 and :704 divides by it for
     the zoom readout, all three assuming the 50 × 40 × 25 demo domain. Deriving
     it keeps that view familiar while letting a different model frame itself. */
  function bounds(bbox) {
    var center = [(bbox[0] + bbox[3]) / 2, (bbox[1] + bbox[4]) / 2, (bbox[2] + bbox[5]) / 2];
    var size = [bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2]];
    var radius = Math.sqrt(size[0] * size[0] + size[1] * size[1] + size[2] * size[2]) / 2;

    return {
      center: center,
      size: size,
      radius: radius,
      // Same rule as the frozen zoomFit (js/viewport.js:654).
      homeRadius: radius / Math.sin(FOV_DEG * Math.PI / 360) * FIT_MARGIN
    };
  }

  return { geometry: geometry, edges: edges, bounds: bounds, FOV_DEG: FOV_DEG };
})();
