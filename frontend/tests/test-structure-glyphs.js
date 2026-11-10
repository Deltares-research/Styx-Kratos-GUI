/* ══════════════════════════════════════════════════════════════════
   test-structure-glyphs.js — how a sheet pile, an anchor and an interface look.

   `App.StructureGlyphs` turns a part's line into triangles a fixed number of
   pixels wide. It is arithmetic only -- no three.js, no DOM -- so it runs
   headless; viewport.js puts the triangles on screen.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var G = App.StructureGlyphs;

  /* The 2D section as the viewport sees it: looking down -z at the x-y plane. */
  function sectionView(px) {
    return { toCamera: [0, 0, 1], right: [1, 0, 0], up: [0, 1, 0], px: px };
  }

  var PROJECT = {
    beams: [{ id: 'sheetpile', points: [[5, 0], [5, -13]] }],
    anchors: [{ id: 'strut', head: [5, -1.5], tail: [0, -4] }],
    interfaces: [
      { id: 'wall_contact', structure: 'sheetpile', side: 'both', stretch: null },
      { id: 'slip', structure: null, side: 'left', points: [[20, 0], [24, -8]] }
    ]
  };

  /* Every vertex of a flat triangle list, as [x, y, z]. */
  function vertices(flat) {
    var out = [];
    for (var i = 0; i < flat.length; i += 3) out.push([flat[i], flat[i + 1], flat[i + 2]]);
    return out;
  }

  function extent(flat, axis) {
    var values = vertices(flat).map(function (v) { return v[axis]; });
    return [Math.min.apply(null, values), Math.max.apply(null, values)];
  }

  /* ── Which glyph a part takes ── */

  T.test('a part is drawn as the kind of structure the project says it is', function () {
    T.eq(G.kindOf('sheetpile', PROJECT), 'pile');
    T.eq(G.kindOf('strut', PROJECT), 'anchor');
    T.eq(G.kindOf('wall_contact', PROJECT), 'interface');
    T.eq(G.kindOf('slip', PROJECT), 'interface');
    T.eq(G.kindOf('soil_L1', PROJECT), null, 'soil keeps its own drawing');
    T.eq(G.kindOf('sheetpile', null), null);
  });

  T.test('a section\'s edges become one two-point line per segment', function () {
    var paths = G.edgePaths([0, 0, 0, 1, 0, 0, 1, 0, 0, 1, 2, 0]);
    T.eq(paths.length, 2);
    T.eq(paths[1].points, [[1, 0, 0], [1, 2, 0]]);
  });

  /* ── Where an interface goes ── */

  T.test('an interface on both faces of a pile is drawn on each side of it', function () {
    var record = PROJECT.interfaces[0];
    var paths = G.interfacePaths(record, [[5, 0], [5, -13]], ['left', 'right'], 0);
    T.eq(paths.length, 2);
    T.eq(paths.map(function (p) { return p.face; }), [G.FACE.left, G.FACE.right]);
    paths.forEach(function (p) { T.eq(p.offset, G.BESIDE_PILE); });
    T.eq(paths[0].points[1], [5, -13, 0]);
  });

  T.test('an interface on one face of a pile is drawn on that side only', function () {
    var record = { structure: 'sheetpile', side: 'right' };
    var paths = G.interfacePaths(record, [[5, 0], [5, -13]], ['left', 'right'], 0);
    T.eq(paths.length, 1);
    T.eq(paths[0].face, G.FACE.right);
    // On a flat pile "left" is the first face the line has: below.
    record = { structure: 'strut_beam', side: 'left' };
    paths = G.interfacePaths(record, [[0, -2], [10, -2]], ['below', 'above'], 0);
    T.eq(paths[0].face, G.FACE.below);
  });

  T.test('an interface on a line of its own is drawn on the line', function () {
    var paths = G.interfacePaths(PROJECT.interfaces[1], [[20, 0], [24, -8]], null, 0.5);
    T.eq(paths.length, 1);
    T.ok(!paths[0].offset, 'no pile to clear');
    T.eq(paths[0].points, [[20, 0, 0.5], [24, -8, 0.5]]);
  });

  T.test('an interface with nothing to run along draws nothing', function () {
    T.eq(G.interfacePaths({ structure: 'gone', side: 'both' }, [], null, 0), []);
  });

  /* ── Size on screen ── */

  T.test('a pile is its style\'s width in pixels at every zoom', function () {
    var path = [{ points: [[5, 0, 0], [5, -13, 0]] }];
    [0.01, 0.1, 2].forEach(function (px) {
      var x = extent(G.triangles(path, G.STYLES.pile, sectionView(px)), 0);
      T.near(x[1] - x[0], G.STYLES.pile.width * px, 1e-9, 'at ' + px + ' m/px');
      T.near((x[0] + x[1]) / 2, 5, 1e-9, 'centred on the pile');
    });
  });

  T.test('a glyph is lifted toward the camera, over the soil it lies in', function () {
    var flat = G.triangles([{ points: [[5, 0, 0], [5, -13, 0]] }], G.STYLES.pile,
                           sectionView(0.1));
    vertices(flat).forEach(function (v) { T.ok(v[2] > 0, 'z ' + v[2]); });
  });

  T.test('a pile with no width on screen yet is a band of no width on its line', function () {
    var flat = G.triangles([{ points: [[5, 0, 0], [5, -13, 0]] }], G.STYLES.pile,
                           sectionView(0));
    T.eq(extent(flat, 0), [5, 5]);
    T.eq(extent(flat, 1), [-13, 0]);
  });

  T.test('interface dashes sit beside the pile, on the face they belong to', function () {
    var px = 0.1;
    var clear = (G.STYLES.pile.width / 2) * px;
    // Drawn top-down and bottom-up: "left" is toward -x either way.
    [[[5, 0], [5, -13]], [[5, -13], [5, 0]]].forEach(function (pile) {
      var paths = G.interfacePaths({ structure: 'p', side: 'both' }, pile,
                                   ['left', 'right'], 0);
      var left = extent(G.triangles([paths[0]], G.STYLES.interface, sectionView(px)), 0);
      var right = extent(G.triangles([paths[1]], G.STYLES.interface, sectionView(px)), 0);
      T.ok(left[1] < 5 - clear, 'left dashes clear of the pile: ' + left);
      T.ok(right[0] > 5 + clear, 'right dashes clear of the pile: ' + right);
    });
  });

  T.test('an anchor has a dot at each end', function () {
    var anchor = [{ points: [[5, -1.5, 0], [0, -4, 0]] }];
    var flat = G.triangles(anchor, G.STYLES.anchor, sectionView(0.1));
    var triangles = flat.length / 9;
    T.ok(triangles > 2, 'more than the band\'s two triangles: ' + triangles);
    var x = extent(flat, 0);
    T.near(x[1], 5 + G.STYLES.anchor.dot * 0.1, 1e-9, 'the head\'s dot reaches past the head');
    T.near(x[0], 0 - G.STYLES.anchor.dot * 0.1, 1e-9, 'the tail\'s dot reaches past the tail');
  });

  /* ── Dashes ── */

  T.test('dashes keep their rhythm across a bend', function () {
    // 10 then 10 along a right angle, dash 4 and gap 3: dashes at 0-4, 7-11 and
    // 14-18 along the line. The one from 7 to 11 carries on round the corner at 10
    // rather than the pattern restarting there.
    var pieces = G.dashes([[0, 0, 0], [10, 0, 0], [10, 10, 0]], 4, 3);
    var lengths = pieces.map(function (piece) {
      var d = [piece[1][0] - piece[0][0], piece[1][1] - piece[0][1]];
      return Math.sqrt(d[0] * d[0] + d[1] * d[1]);
    });
    T.near(lengths.reduce(function (a, b) { return a + b; }, 0), 3 * 4, 1e-9);
    T.eq(pieces.length, 4, 'three dashes, one of them in two pieces');
    T.eq(pieces[1], [[7, 0, 0], [10, 0, 0]]);
    T.eq(pieces[2], [[10, 0, 0], [10, 1, 0]]);
    T.eq(pieces[3], [[10, 4, 0], [10, 8, 0]]);
  });

  T.test('a dashed line zoomed far in stays a bounded number of dashes', function () {
    var pieces = G.dashes([[0, 0, 0], [0, -1000, 0]], 0.001, 0.001);
    T.ok(pieces.length <= G.MAX_DASHES + 1, pieces.length + ' dashes');
  });

  /* ── Picking ── */

  /* The section seen at one model unit per pixel, y up the screen. */
  function toScreen(p) { return { x: p[0], y: -p[1] }; }

  T.test('a click in the gap between an interface\'s dashes still lands on it', function () {
    var paths = [{ points: [[0, 0, 0], [100, 0, 0]] }];
    var style = G.STYLES.interface;
    // 9 on, 6 off: x = 12 is in the first gap.
    T.eq(G.screenDistance(paths, style, 1, toScreen, { x: 12, y: 0 }), 0);
    T.near(G.screenDistance(paths, style, 1, toScreen, { x: 50, y: 5 }), 5 - style.width / 2, 1e-9);
    T.ok(G.nearest([{ distance: 3.5, order: 31 }]), 'a few pixels off still picks');
    T.eq(G.nearest([{ distance: G.PICK_PX + 1, order: 31 }]), null);
  });

  T.test('an interface beside a pile is told from the pile by where the click is', function () {
    var pile = [{ points: [[0, 0, 0], [0, -100, 0]] }];
    var contact = G.interfacePaths(PROJECT.interfaces[0], [[0, 0], [0, -100]], ['left', 'right'], 0);
    function pick(x) {
      var click = { x: x, y: 50 };
      return G.nearest([
        { key: 'pile', order: G.STYLES.pile.order,
          distance: G.screenDistance(pile, G.STYLES.pile, 1, toScreen, click) },
        { key: 'contact', order: G.STYLES.interface.order,
          distance: G.screenDistance(contact, G.STYLES.interface, 1, toScreen, click) }
      ]).key;
    }
    T.eq(pick(0), 'pile');
    T.eq(pick(G.BESIDE_PILE), 'contact');
    T.eq(pick(-G.BESIDE_PILE - 4), 'contact', 'just outside the left dashes');
  });

  T.test('nothing off screen is in reach', function () {
    var paths = [{ points: [[0, 0, 0], [10, 0, 0]] }];
    T.eq(G.screenDistance(paths, G.STYLES.pile, 1, function () { return null; }, { x: 0, y: 0 }),
         Infinity);
  });

  /* ── Pixel size ── */

  T.test('an orthographic pixel is the visible height over the canvas height', function () {
    var ortho = { ortho: true, top: 30, bottom: -30, zoom: 2 };
    T.near(G.pixelSize(ortho, [0, 0, 0], 600), 60 / 2 / 600, 1e-12);
  });

  T.test('a perspective pixel grows with the distance from the eye', function () {
    var persp = { ortho: false, fov: 90, position: [0, 0, 10] };
    var near = G.pixelSize(persp, [0, 0, 5], 500);
    var far = G.pixelSize(persp, [0, 0, -10], 500);
    T.near(near, 2 * 5 * Math.tan(Math.PI / 4) / 500, 1e-12);
    T.near(far / near, 4, 1e-9);
  });

})();
