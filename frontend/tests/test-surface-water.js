/* ══════════════════════════════════════════════════════════════════
   test-surface-water.js — the water on the ground that Staged construction draws.

   `App.SurfaceWater` finds, on the build's sections and for one stage, the stretch of
   the soil's boundary the export puts the phreatic line's water on
   (core/kratos/writer.py `_water_surface_loads`), and the arrows that show it.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var W = App.SurfaceWater;

  /* A section as the build sends one: a rectangle's two triangles and its four edges.
     `cuts` are extra corners on its boundary, where a neighbour's meets it. */
  function rect(key, x0, y0, x1, y1) {
    var e = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]];
    var edges = [];
    for (var i = 1; i < e.length; i += 1) {
      edges.push(e[i - 1][0], e[i - 1][1], 0, e[i][0], e[i][1], 0);
    }
    return { key: key, positions: [x0, y0, 0, x1, y0, 0, x1, y1, 0, x0, y1, 0],
             indices: [0, 1, 2, 0, 2, 3], edges: edges };
  }

  /* A 20 m wide, 10 m deep site with a pit 4 m wide and 3 m deep dug out of the middle
     (`soil_L__lift1`). The blocks either side run the full depth in one edge, so the
     pit's sides meet them part way along. */
  function sections() {
    return [rect('soil_L', 0, -10, 8, 0), rect('soil_L__right', 12, -10, 20, 0),
            rect('soil_L__below', 8, -10, 12, -3), rect('soil_L__lift1', 8, -3, 12, 0)];
  }

  function phreatic(points, extra) {
    return Object.assign({
      id: 'phreatic', name: 'Phreatic', kind: 'water_pressure', on: 'domain',
      fluid_pressure_type: 'Phreatic_Multi_Line', is_fixed: true, active: true,
      x_coordinates: points.map(function (p) { return p[0]; }),
      y_coordinates: points.map(function (p) { return p[1]; })
    }, extra || {});
  }

  function project(conditions, extra) {
    return Object.assign({
      dimension: 2, layered_soil: true,
      domain: { x0: 0, x1: 20, z0: 0, z1: 1, y_top: 0, y_bottom: -10 },
      soil_body_keys: ['soil_L', 'soil_L__right', 'soil_L__below', 'soil_L__lift1'],
      custom_parts: [], normal_loads: [],
      boundary_conditions: conditions
    }, extra || {});
  }

  var DUG = { 'soil_L__lift1': true };

  function where(pieces, test) { return pieces.filter(test); }
  function length(list) {
    return list.reduce(function (sum, p) {
      return sum + Math.hypot(p.b[0] - p.a[0], p.b[1] - p.a[1]);
    }, 0);
  }

  T.test('water over the whole surface presses down on it, and nowhere else', function () {
    var pieces = W.pieces(project([phreatic([[0, 1], [20, 1]])]), sections(), {});
    T.ok(pieces.length > 0, 'something is loaded');
    pieces.forEach(function (p) {
      T.near(p.a[1], 0, 1e-9, 'on the ground surface');
      T.near(p.b[1], 0, 1e-9, 'on the ground surface');
      T.near(p.inward[1], -1, 1e-9, 'pressing down into the soil');
      T.near(p.depth[0], 1, 1e-9, 'under 1 m of water');
    });
    T.near(length(pieces), 20, 1e-9, 'all of it, and not the sides or bottom');
  });

  T.test('once the pit is dug, its floor and sides are loaded too', function () {
    var pieces = W.pieces(project([phreatic([[0, 1], [20, 1]])]), sections(), DUG);
    var floor = where(pieces, function (p) { return Math.abs(p.a[1] + 3) < 1e-9 && Math.abs(p.b[1] + 3) < 1e-9; });
    var left = where(pieces, function (p) { return Math.abs(p.a[0] - 8) < 1e-9 && Math.abs(p.b[0] - 8) < 1e-9; });
    var right = where(pieces, function (p) { return Math.abs(p.a[0] - 12) < 1e-9 && Math.abs(p.b[0] - 12) < 1e-9; });
    var top = where(pieces, function (p) { return Math.abs(p.a[1]) < 1e-9 && Math.abs(p.b[1]) < 1e-9; });

    T.near(length(floor), 4, 1e-9, 'the floor');
    floor.forEach(function (p) {
      T.near(p.inward[1], -1, 1e-9, 'down into the floor');
      T.near(p.depth[0], 4, 1e-9, '4 m of water over it');
    });
    T.near(length(left), 3, 1e-9, 'the dug part of the left side, not the soil below it');
    left.forEach(function (p) { T.near(p.inward[0], -1, 1e-9, 'into the left bank'); });
    T.near(length(right), 3, 1e-9, 'the dug part of the right side');
    right.forEach(function (p) { T.near(p.inward[0], 1, 1e-9, 'into the right bank'); });
    T.near(length(top), 16, 1e-9, 'the surface either side of the pit');
  });

  T.test('only what is below the phreatic line is loaded', function () {
    // From 1 m above the ground at x = 0 to 1 m below it at x = 20: wet up to x = 10.
    var pieces = W.pieces(project([phreatic([[0, 1], [20, -1]])]), sections(), {});
    T.near(length(pieces), 10, 1e-6, 'half the surface');
    pieces.forEach(function (p) {
      T.ok(Math.max(p.a[0], p.b[0]) <= 10 + 1e-6, 'left of where the line meets the ground');
    });
  });

  T.test('the line is held level past either end', function () {
    var water = phreatic([[5, 2], [15, 1]]);
    T.near(W.level(water, 0), 2, 1e-12);
    T.near(W.level(water, 10), 1.5, 1e-12);
    T.near(W.level(water, 20), 1, 1e-12);
  });

  T.test('no water on the ground when the line is below it', function () {
    T.eq(W.pieces(project([phreatic([[0, -1], [20, -1]])]), sections(), {}).length, 0);
  });

  T.test('a phreatic line the stage has switched off puts no water anywhere', function () {
    var p = project([phreatic([[0, 1], [20, 1]])]);
    T.eq(W.pieces(p, sections(), { phreatic: true }).length, 0, 'off in this stage');
    var off = project([phreatic([[0, 1], [20, 1]], { active: false })]);
    T.eq(W.pieces(off, sections(), {}).length, 0, 'not exported at all');
  });

  T.test('a head line is not water standing on the ground', function () {
    var head = phreatic([[0, 1], [20, 1]], { fluid_pressure_type: 'Head_Line' });
    T.eq(W.pieces(project([head]), sections(), {}).length, 0);
  });

  T.test('a phreatic line on one soil part stands on that part only', function () {
    var water = phreatic([[0, 1], [20, 1]], { on: 'part', part: 'soil_L__right' });
    var pieces = W.pieces(project([water]), sections(), {});
    T.near(length(pieces), 8, 1e-9);
    pieces.forEach(function (p) { T.ok(p.a[0] >= 12 - 1e-9, 'on the right block'); });
  });

  T.test('where the user drew a normal load, theirs is the load', function () {
    var p = project([phreatic([[0, 1], [20, 1]])], {
      normal_loads: [{ id: 'nl', active: true, points: [[8, -3], [12, -3]] }]
    });
    var pieces = W.pieces(p, sections(), DUG);
    T.eq(where(pieces, function (q) {
      return Math.abs(q.a[1] + 3) < 1e-9 && Math.abs(q.b[1] + 3) < 1e-9;
    }).length, 0, 'the pit floor is the drawn load\'s');
    T.ok(pieces.length > 0, 'the rest is still loaded');
  });

  T.test('nothing in 3D', function () {
    T.eq(W.pieces(project([phreatic([[0, 1], [20, 1]])], { dimension: 3 }), sections(), {})
      .length, 0);
  });

  T.test('the arrows point into the soil and grow with the depth of the water', function () {
    /* In proportion, as the pressure is, so the line through the tails is straight. */
    var pieces = W.pieces(project([phreatic([[0, 1], [20, 1]])]), sections(), DUG);
    var spec = W.glyph(pieces, 1, 1);
    T.near(spec.deepest, 4, 1e-9, 'the pit floor is the deepest');
    T.ok(spec.arrows.length > 0, 'arrows');
    var longest = 0;
    spec.arrows.forEach(function (arrow) {
      longest = Math.max(longest, arrow.length);
      T.ok(arrow.length <= 1 + 1e-9, 'none longer than asked');
    });
    T.near(longest, 1, 1e-9, 'the deepest water has the full length');
    var surface = spec.arrows.filter(function (a) { return Math.abs(a.tip[1]) < 1e-9; });
    T.ok(surface.length > 0, 'arrows on the surface too');
    surface.forEach(function (a) {
      T.near(a.length, 0.25, 1e-9, 'a quarter of the floor\'s, under a quarter the water');
      T.near(a.direction[1], -1, 1e-9, 'down into the ground');
    });
    T.eq(spec.tails.length, pieces.length, 'one tail line per loaded stretch');
    spec.tails.forEach(function (line) { T.eq(line.length, 2, 'a straight line'); });
  });

  T.test('no water, no arrows', function () {
    var spec = W.glyph([], 1, 1);
    T.eq(spec.arrows.length, 0);
    T.eq(spec.tails.length, 0);
  });

})();
