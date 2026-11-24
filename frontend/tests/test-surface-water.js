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

  T.test('where two lines reach a soil, the last in the writer\'s order is its water', function () {
    /* Start values first, then the least specific target first: listed out of that
       order on purpose, so the order is the sort's, not the list's. */
    function topOfRight(conditions) {
      var pieces = W.pieces(project(conditions), sections(), {});
      return where(pieces, function (p) { return Math.min(p.a[0], p.b[0]) >= 12 - 1e-9; });
    }
    var onPart = phreatic([[0, 2], [20, 2]], { id: 'part', on: 'part', part: 'soil_L__right' });
    var onDomain = phreatic([[0, 1], [20, 1]], { id: 'domain' });

    var right = topOfRight([onPart, onDomain]);
    T.ok(right.length > 0, 'the right block is loaded');
    right.forEach(function (p) {
      T.eq(p.water, 'part', 'the part\'s line, the more specific');
      T.near(p.depth[0], 2, 1e-9, 'under its 2 m of water');
    });

    var start = Object.assign({}, onPart, { is_fixed: false });
    topOfRight([onDomain, start]).forEach(function (p) {
      T.eq(p.water, 'domain', 'a start value goes first, so the fixed line is the last');
      T.near(p.depth[0], 1, 1e-9);
    });
  });

  T.test('the soil is the layers\' bodies and the custom parts with a material', function () {
    /* No soil body keys yet: the layers give them. A custom part counts as soil only
       with a material; the plate between the blocks has none, so the blocks' inner
       sides are open to the water, the full 10 m. */
    var p = project([phreatic([[0, 1], [20, 1]])], {
      soil_body_keys: [], layers: [{ id: 'L' }],
      custom_parts: [{ key: 'soil_L__right', mat: 'clay' }, { key: 'plate', mat: null }]
    });
    var pieces = W.pieces(p, [rect('soil_L', 0, -10, 8, 0), rect('soil_L__right', 12, -10, 20, 0),
                              rect('plate', 8, -1, 12, 0)], {});
    T.near(length(pieces), 8 + 8 + 10 + 10, 1e-9, 'both tops and both inner sides');
    T.ok(pieces.some(function (q) { return Math.min(q.a[0], q.b[0]) >= 12 - 1e-9; }),
         'on the custom part too');
    T.ok(pieces.every(function (q) {
      return Math.max(q.a[0], q.b[0]) <= 8 + 1e-9 || Math.min(q.a[0], q.b[0]) >= 12 - 1e-9;
    }), 'nothing on the plate');
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

  T.test('the arrows in the open water hang from the phreatic line', function () {
    /* The water at 1 over the ground at 0 and the pit floor at -3: each arrow on the
       ground starts on the line, so it is as long as the water is deep. */
    var p = project([phreatic([[0, 1], [20, 1]])]);
    var pieces = W.pieces(p, sections(), DUG);
    var spec = W.glyph(pieces, 1, 1, W.linesOf(p));
    var down = spec.arrows.filter(function (a) { return a.direction[1] < -0.2; });
    T.ok(down.length > 0, 'arrows on the ground');
    down.forEach(function (a) {
      T.near(a.tip[1] + a.length, 1, 1e-9, 'the tail on the water line');
    });
    T.ok(down.some(function (a) { return Math.abs(a.length - 4) < 1e-9; }),
         'the pit floor\'s reach the line 4 m up');
    var sides = spec.arrows.filter(function (a) { return a.direction[1] >= -0.2; });
    sides.forEach(function (a) {
      T.ok(a.length <= 1 + 1e-9, 'an upright face keeps its arrows in proportion');
    });
  });

  T.test('the reach to a sloping phreatic line, against the arrow', function () {
    var line = { x_coordinates: [0, 10], y_coordinates: [2, 4] };
    T.near(W.reach(line, [5, 0], [0, -1]), 3, 1e-9, 'straight up: the line at x = 5');
    T.near(W.reach(line, [12, 0], [0, -1]), 4, 1e-9, 'held level past its end');
    // Slanted up and to the left from (11, 0): across the line's last corner.
    var n = [Math.SQRT1_2, -Math.SQRT1_2];
    var s = W.reach(line, [11, 0], n);
    var at = [11 - n[0] * s, -n[1] * s];
    T.near(at[1], W.level(line, at[0]), 1e-9, 'it ends on the line');
    T.eq(W.reach(line, [5, 5], [0, -1]), 0, 'above the line, no reach');
    T.eq(W.reach(line, [5, 0], [1, 0]), null, 'an upright face has no line above it');
  });

  T.test('the stages with water on the ground, per phreatic line', function () {
    /* The pit is dug in the second stage; the water at -1 stands on its floor only. */
    var order = [{ id: 's1', name: 'First' }, { id: 's2', name: 'Dig' }];
    function hiddenOf(id) { return id === 's2' ? DUG : {}; }
    var p = project([phreatic([[0, -1], [20, -1]])]);
    T.eq(W.stagesWithWater(p, sections(), order, hiddenOf), { phreatic: ['Dig'] });
    T.eq(W.stagesWithWater(p, sections(), [], hiddenOf), {},
         'unstaged, the pit is not dug and the water is below the ground');
    var high = project([phreatic([[0, 1], [20, 1]])]);
    T.eq(W.stagesWithWater(high, sections(), [], hiddenOf), { phreatic: [null] },
         'a model with no stages has it in its one stage');
  });

  T.test('the pressure along a hydrostatic condition on a line, below its level only', function () {
    var record = { id: 'bank', fluid_pressure_type: 'Hydrostatic', reference_coordinate: -1 };
    // A bank from (0, 0) down to (3, -3), then level: wet from y = -1 down.
    var list = W.along(record, [[0, 0, 5], [3, -3, 5], [9, -3, 5]], [10, -20]);
    T.eq(list.length, 2);
    T.near(list[0].a[1], -1, 1e-9, 'the slope is wet from the level down');
    T.near(list[0].depth[0], 0, 1e-9);
    T.near(list[0].depth[1], 2, 1e-9);
    T.eq(list[1].depth, [2, 2]);
    T.ok(list.every(function (piece) { return piece.water === 'bank'; }));
    T.ok(list[1].inward[1] < 0, 'the diagram stands on the side of the centre');
    var spec = W.glyph(list, 1, 0.5);
    T.eq(spec.deepest, 2);
    T.ok(spec.deepestInward[1] < 0);
    T.eq(W.along(Object.assign({}, record, { fluid_pressure_type: 'Uniform' }),
                 [[0, 0], [1, -3]], [0, 0]), [], 'a uniform pressure has no diagram');
    T.eq(W.along(Object.assign({}, record, { reference_coordinate: -5 }),
                 [[0, 0], [3, -3]], [0, 0]), [], 'all above its level, nothing');
  });

  T.test('the pressure is the depth times the water\'s weight', function () {
    var p = { unit_system: 'SI', water: { y: 0 }, fluid: { specific_weight: 10000 } };
    T.ok(/^p = 25000\b/.test(W.pressureText(p, 2.5)), W.pressureText(p, 2.5));
    p.fluid.specific_weight = 9000;
    T.ok(/^p = 22500\b/.test(W.pressureText(p, 2.5)), 'the water\'s own weight: '
         + W.pressureText(p, 2.5));
    T.eq(W.pressureText(p, 0), null, 'no water, no pressure');
  });

  T.test('the deepest point of the water on the ground', function () {
    var p = project([phreatic([[0, 1], [20, 1]])]);
    var spec = W.glyph(W.pieces(p, sections(), {}), 1, 1);
    T.near(spec.deepest, 1, 1e-9);
    T.eq(spec.deepestInward, [0, -1], 'into the ground');
  });

  T.test('the open water fills from the ground up to its line', function () {
    // The pit is dug: the water at -1 stands 2 m deep in it, and not on the ground.
    var p = project([phreatic([[0, -1], [20, -1]])]);
    var body = W.waterBody(W.pieces(p, sections(), DUG));
    T.eq(body.length, 1, 'the floor only: the pit\'s sides are upright');
    var ys = body[0].map(function (corner) { return corner[1]; }).sort();
    T.eq(ys, [-1, -1, -3, -3]);
    var xs = body[0].map(function (corner) { return corner[0]; }).sort(function (a, b) {
      return a - b;
    });
    T.eq(xs, [8, 8, 12, 12]);
  });

  T.test('no water, no arrows', function () {
    var spec = W.glyph([], 1, 1);
    T.eq(spec.arrows.length, 0);
    T.eq(spec.tails.length, 0);
  });


  /* ── The soil's outer boundary, where a flow boundary condition goes ──── */

  test('the outline is the boundary with soil on one side only', function () {
    var edges = W.outline(sections(), ['soil_L', 'soil_L__right', 'soil_L__below']);
    function has(a, b) {
      return edges.some(function (e) {
        return (e.a[0] === a[0] && e.a[1] === a[1] && e.b[0] === b[0] && e.b[1] === b[1])
          || (e.a[0] === b[0] && e.a[1] === b[1] && e.b[0] === a[0] && e.b[1] === a[1]);
      });
    }
    T.ok(has([0, -10], [0, 0]), 'the left side');
    T.ok(has([8, -3], [12, -3]), 'the floor of the pit, dug out');
    T.ok(!has([8, -10], [8, -3]) && !edges.some(function (e) {
      return e.a[0] === 8 && e.b[0] === 8 && Math.min(e.a[1], e.b[1]) < -3;
    }), 'not the side two bodies share below the pit');
    T.eq(W.outline(null, ['soil_L']), []);
  });

  test('a point is moved to the nearest point of the outline', function () {
    var edges = W.outline(sections(), ['soil_L', 'soil_L__right', 'soil_L__below']);
    var near = W.nearestOn(edges, 10, -2.6);
    T.near(near.point[0], 10, 1e-9);
    T.near(near.point[1], -3, 1e-9);
    T.near(near.distance, 0.4, 1e-9);
    T.eq(W.nearestOn([], 1, 1), null);
  });

  /* An embankment-like soil over a second one: a top sloping from (0, -5) up to
     (20, 0), on a soil from -10 down to -20. */
  function slopeSections() {
    return [
      { key: 'soil_A', positions: [0, -10, 0, 20, -10, 0, 20, 0, 0, 0, -5, 0],
        indices: [0, 1, 2, 0, 2, 3] },
      { key: 'soil_B', positions: [0, -20, 0, 20, -20, 0, 20, -10, 0, 0, -10, 0],
        indices: [0, 1, 2, 0, 2, 3] }
    ];
  }

  function sorted(points) {
    return points.slice().sort(function (p, q) { return p[0] - q[0] || p[1] - q[1]; });
  }

  /* As the build sends a 2D section: every triangle twice, once per winding. */
  function bothWindings(sections) {
    return sections.map(function (section) {
      var twice = [];
      for (var i = 0; i < section.indices.length; i += 3) {
        var t = section.indices.slice(i, i + 3);
        twice.push(t[0], t[1], t[2], t[0], t[2], t[1]);
      }
      return Object.assign({}, section, { indices: twice });
    });
  }

  function key(edges) {
    return edges.map(function (e) {
      var ends = [e.a, e.b].sort(function (p, q) { return p[0] - q[0] || p[1] - q[1]; });
      return e.key + ' ' + JSON.stringify(ends) + (e.outer ? ' outer' : '');
    }).sort();
  }

  test('the geometry\'s lines: the outer boundary and the lines between bodies', function () {
    var edges = W.geometryLines(slopeSections(), ['soil_A', 'soil_B']);
    T.eq(key(edges), [
      'soil_A [[0,-10],[0,-5]] outer', 'soil_A [[0,-10],[20,-10]]',
      'soil_A [[0,-5],[20,0]] outer', 'soil_A [[20,-10],[20,0]] outer',
      'soil_B [[0,-10],[20,-10]]', 'soil_B [[0,-20],[0,-10]] outer',
      'soil_B [[0,-20],[20,-20]] outer', 'soil_B [[20,-20],[20,-10]] outer'
    ], 'the line between the two soils once for each, inside the soil');
    T.eq(key(W.geometryLines(bothWindings(slopeSections()), ['soil_A', 'soil_B'])),
         key(edges), 'a triangle sent with both windings is one triangle');
    T.eq(W.outline(bothWindings(slopeSections()), ['soil_A', 'soil_B']).length, 6,
         'the outer boundary, not nothing, as the build sends it');
  });

  test('a line runs along the outer boundary, or not', function () {
    var outer = W.outline(slopeSections(), ['soil_A', 'soil_B']);
    T.ok(W.runsAlong(outer, [[20, -15], [20, -5]]), 'up the right side, over two bodies');
    T.ok(W.runsAlong(outer, [[0, -5], [20, 0], [20, -10]]), 'round a corner');
    T.ok(!W.runsAlong(outer, [[0, -10], [20, -10]]), 'the line between the two soils');
    T.ok(!W.runsAlong(outer, [[0, -5], [20, -10]]), 'across the soil, both ends on it');
    T.ok(!W.runsAlong(outer, []));
  });

  test('the corners: where a line turns, ends or meets another', function () {
    var edges = W.geometryLines(slopeSections(), ['soil_A', 'soil_B']);
    T.eq(sorted(W.corners(edges)),
         [[0, -20], [0, -10], [0, -5], [20, -20], [20, -10], [20, 0]]);
    T.eq(sorted(W.corners(W.outline(slopeSections(), ['soil_A', 'soil_B']))),
         [[0, -20], [0, -5], [20, -20], [20, 0]],
         'the outer boundary alone runs straight on past the line between the soils');
    // A side the mesh splits into edges that carry on straight has no corner there.
    T.eq(sorted(W.corners([{ a: [0, 0], b: [5, 0], key: 's' },
                           { a: [5, 0], b: [10, 0], key: 's' },
                           { a: [10, 0], b: [10, -5], key: 's' }])),
         [[0, 0], [10, -5], [10, 0]]);
    T.eq(W.corners([]), []);
  });

  test('a point is always moved onto a line, however far off it is', function () {
    var edges = W.geometryLines(slopeSections(), ['soil_A', 'soil_B']);
    var corners = W.corners(edges);
    var deep = W.snapOnto(edges, corners, 10, -16, null);
    T.near(deep.point[0], 10, 1e-9);
    T.near(deep.point[1], -20, 1e-9, 'deep in the soil: onto the bottom, the nearest line');
    var between = W.snapOnto(edges, corners, 10, -11.5, null);
    T.near(between.point[1], -10, 1e-9, 'onto the line between the two soils');
    var above = W.snapOnto(edges, corners, 10, 5, null).point;
    T.near(above[1], -5 + 0.25 * above[0], 1e-9, 'above the slope: onto it');
    T.ok(above[0] !== Math.round(above[0]), 'with snapping off, wherever it lands');
    T.eq(W.snapOnto([], [], 1, 1, 1), null);
  });

  test('with a snapping distance a point snaps along the line', function () {
    var edges = W.geometryLines(slopeSections(), ['soil_A', 'soil_B']);
    var corners = W.corners(edges);
    T.eq(W.snapOnto(edges, corners, 10.3, 5, 1).point, [12, -2],
         'on the slope, where it crosses the grid line x = 12');
    T.eq(W.snapOnto(edges, corners, 25, -15.3, 1).point, [20, -15],
         'on the right side, at the grid line y = -15');
    T.eq(W.snapOnto(edges, corners, 21, -10.4, 3).point, [20, -10],
         'the two soils meet at -10: a corner, off the 3 m grid, taken first');
    T.eq(W.snapOnto(edges, corners, 21, -12.4, 3).point, [20, -12],
         'further from the corner than from the grid line: the grid line');
  });

  test('the soil at a point is the body there, or none', function () {
    var keys = ['soil_L', 'soil_L__right', 'soil_L__below'];
    T.eq(W.soilAt(sections(), keys, 4, -5), 'soil_L');
    T.eq(W.soilAt(sections(), keys, 10, -6), 'soil_L__below');
    T.eq(W.soilAt(sections(), keys, 10, -1), null, 'the pit, dug out');
  });

})();
