/* Tests for live/js/buffers.js — payload → THREE geometry.

   These run against the real three.js in vendor/, not a stub: the module is thin
   glue, so testing it against a fake THREE would only assert that the glue calls
   the functions the fake defines. */

(function () {

  /* A unit cube, wound counter-clockwise seen from outside — the same convention
     the server emits and THREE.FrontSide culling expects. */
  function cube() {
    return {
      key: 'test', color: '#4b6ea8',
      positions: [0,0,0, 1,0,0, 1,1,0, 0,1,0, 0,0,1, 1,0,1, 1,1,1, 0,1,1],
      indices: [0,2,1, 0,3,2,      // bottom, -z
                4,5,6, 4,6,7,      // top,    +z
                0,1,5, 0,5,4,      // front,  -y
                1,2,6, 1,6,5,      // right,  +x
                2,3,7, 2,7,6,      // back,   +y
                3,0,4, 3,4,7],     // left,   -x
      edges: [0,0,0, 1,0,0, 1,0,0, 1,1,0]
    };
  }

  function signedVolume(geo) {
    var p = geo.attributes.position.array, total = 0;
    for (var i = 0; i < p.length; i += 9) {
      total += p[i]   * (p[i+4] * p[i+8] - p[i+5] * p[i+7])
             - p[i+1] * (p[i+3] * p[i+8] - p[i+5] * p[i+6])
             + p[i+2] * (p[i+3] * p[i+7] - p[i+4] * p[i+6]);
    }
    return total / 6;
  }

  /* ── Triangles ───────────────────────────────────────────────── */

  test('geometry expands to non-indexed triangles', function () {
    var geo = App.Buffers.geometry(cube());
    T.eq(geo.getIndex(), null, 'index should be dropped');
    T.eq(geo.attributes.position.count, 36, 'twelve triangles, three corners each');
  });

  test('geometry uploads as Float32, not a plain Array', function () {
    var geo = App.Buffers.geometry(cube());
    T.ok(geo.attributes.position.array instanceof Float32Array, 'positions');
    T.ok(geo.attributes.normal.array instanceof Float32Array, 'normals');
  });

  test('normals are flat, not smoothed across corners', function () {
    // The whole reason for expanding to non-indexed. Shared cube corners would
    // average to (±1,±1,±1)/√3 and round the model off; per-face normals are
    // axis-aligned. This is the assertion that catches a dropped toNonIndexed().
    var n = App.Buffers.geometry(cube()).attributes.normal.array;
    for (var i = 0; i < n.length; i += 3) {
      var axes = [n[i], n[i+1], n[i+2]].filter(function (c) { return Math.abs(c) > 1e-6; });
      T.eq(axes.length, 1, 'normal ' + i / 3 + ' is not axis-aligned: '
                           + [n[i], n[i+1], n[i+2]]);
      T.near(Math.abs(axes[0]), 1, 1e-6, 'normal ' + i / 3 + ' is not unit length');
    }
  });

  test('winding is preserved, so the surface still encloses positive volume', function () {
    T.near(signedVolume(App.Buffers.geometry(cube())), 1, 1e-5);
  });

  test('an empty section yields a drawable empty geometry rather than throwing', function () {
    var geo = App.Buffers.geometry({ key: 'x', color: '#000', positions: [], indices: [], edges: [] });
    T.eq(geo.attributes.position.count, 0);
  });

  /* ── Edges ───────────────────────────────────────────────────── */

  test('edges become line-segment pairs straight from the payload', function () {
    var geo = App.Buffers.edges(cube());
    T.eq(geo.attributes.position.count, 4, 'two segments');
    T.eq(geo.getIndex(), null);
  });

  /* ── Camera framing ──────────────────────────────────────────── */

  test('bounds centres on the box and measures its half-diagonal', function () {
    var b = App.Buffers.bounds([0, 0, -25, 50, 40, 0]);
    T.eq(b.center, [25, 20, -12.5]);
    T.eq(b.size, [50, 40, 25]);
    T.near(b.radius, Math.sqrt(50 * 50 + 40 * 40 + 25 * 25) / 2, 1e-9);
  });

  test('bounds frames the frozen domain about where the frozen camera sat', function () {
    // js/viewport.js:435 hardcodes radius 118 for this exact 50×40×25 box. The
    // point of deriving it is that a different model gets a sensible camera too,
    // but the familiar view must not lurch when nothing has changed.
    var home = App.Buffers.bounds([0, 0, -25, 50, 40, 0]).homeRadius;
    T.ok(home > 90 && home < 135, 'homeRadius ' + home + ' is far from the frozen 118');
  });

  test('bounds scales with the model instead of assuming 50×40×25', function () {
    var small = App.Buffers.bounds([0, 0, 0, 5, 4, 2.5]);
    var big = App.Buffers.bounds([0, 0, 0, 500, 400, 250]);
    T.near(big.homeRadius / small.homeRadius, 100, 1e-6);
  });

})();
