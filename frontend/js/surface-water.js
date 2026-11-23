/* ══════════════════════════════════════════════════════════════════
   surface-water.js — the water standing on the ground, as Staged construction
   draws it.

   Where the phreatic line is above the soil, the export adds the weight of that water
   as a normal load on the exposed ground below it -- the ground surface, the floor and
   faces of a pit, a wall's face -- worked out stage by stage on the mesh
   (core/kratos/writer.py `_water_surface_loads`). The user never draws that load, so
   without this they cannot see it. This finds the same surface on the drawn sections
   for the stage on screen, so stepping through the stages shows the water following
   the excavation.

   The rule is the writer's, read on the build's sections rather than on the mesh:

     • The water is each active Phreatic_Multi_Line condition the stage has on; one on
       a soil part stands on that part's bodies only. Where two reach the same stretch,
       the last in the writer's order (start values first, least specific target first)
       is the one there.
     • A stretch of a soil body's boundary is exposed where there is soil the stage has
       on one side of it and none on the other, except on the domain's own sides and
       bottom, where the ground goes on.
     • It is loaded where it is below the phreatic line -- held level past either end,
       as Kratos holds it -- and where the user drew no normal load of their own.
     • It always presses into the soil.

   A wall needs nothing of its own here: where water stands against it, the soil on
   its far side ends on the same line, and that is the stretch drawn.

   Flow conditions draws the same for the model as built: there the surface is where
   the export fixes the water pressure (writer.py `_wet_surface`). `along` is the
   pressure of a Hydrostatic condition on its own line or face, drawn the same way, and
   `pressureText` the deepest pressure written beside either.

   `stagesWithWater` says, per phreatic line, which stages have water on the ground:
   the Model explorer's row under the line (model.js `conditionChild`), so the user
   sees where the export adds it without stepping through every stage.

   Pure, no DOM and no three.js: viewport.js puts `glyph`'s arrows on screen.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.SurfaceWater = (function () {

  // The sections come rounded to 4 decimals (core/geometry/tessellation.py DECIMALS).
  var TOL = 1e-3;
  // How far to either side of a boundary its two sides are looked at.
  var SIDE = 1e-2;
  var TARGET_ORDER = ['domain', 'part', 'face', 'line', 'point'];
  var SECTION_FACES = ['top', 'bottom', 'left', 'right'];

  /* The soil the export meshes: the soil bodies and the custom parts with a material. */
  function soilKeys(project) {
    var keys = (project.soil_body_keys && project.soil_body_keys.length)
      ? project.soil_body_keys.slice()
      : (project.layers || []).map(function (layer) { return 'soil_' + layer.id; });
    (project.custom_parts || []).forEach(function (part) {
      if (part.mat && keys.indexOf(part.key) < 0) keys.push(part.key);
    });
    return keys;
  }

  /* The phreatic line conditions that put water on the ground, in the order the writer
     takes them: the last that reaches a stretch is the one there. */
  function waters(project, hidden) {
    var list = (project.boundary_conditions || []).filter(function (c) {
      return c.kind === 'water_pressure' && c.fluid_pressure_type === 'Phreatic_Multi_Line'
        && c.active !== false && !hidden[c.id]
        && (c.x_coordinates || []).length >= 2
        && (c.y_coordinates || []).length === c.x_coordinates.length
        && (c.on !== 'face' || SECTION_FACES.indexOf(c.face) >= 0);
    });
    return list.map(function (c, i) { return { c: c, i: i }; }).sort(function (a, b) {
      var fa = a.c.is_fixed === false ? 0 : 1, fb = b.c.is_fixed === false ? 0 : 1;
      return (fa - fb)
        || (TARGET_ORDER.indexOf(a.c.on) - TARGET_ORDER.indexOf(b.c.on))
        || (a.i - b.i);
    }).map(function (entry) { return entry.c; });
  }

  /* The height of `water`'s line at `x`, held level past either end. */
  function level(water, x) {
    var xs = water.x_coordinates, ys = water.y_coordinates;
    if (x <= xs[0]) return ys[0];
    for (var i = 1; i < xs.length; i += 1) {
      if (x <= xs[i]) {
        var span = xs[i] - xs[i - 1];
        return span ? ys[i - 1] + (ys[i] - ys[i - 1]) * (x - xs[i - 1]) / span : ys[i];
      }
    }
    return ys[ys.length - 1];
  }

  function bodyOf(water, key) {
    if (water.on !== 'part') return true;
    var part = water.part || '';
    return key === part || key.indexOf(part + '__') === 0;
  }

  /* The triangles of the sections `keys`, each with its bounding box. */
  function trianglesOf(sections, keys) {
    var out = [];
    sections.forEach(function (section) {
      if (keys.indexOf(section.key) < 0) return;
      var p = section.positions || [], idx = section.indices || [];
      for (var i = 0; i + 2 < idx.length; i += 3) {
        var a = idx[i] * 3, b = idx[i + 1] * 3, c = idx[i + 2] * 3;
        var t = [p[a], p[a + 1], p[b], p[b + 1], p[c], p[c + 1]];
        out.push({ t: t,
                   x0: Math.min(t[0], t[2], t[4]), x1: Math.max(t[0], t[2], t[4]),
                   y0: Math.min(t[1], t[3], t[5]), y1: Math.max(t[1], t[3], t[5]) });
      }
    });
    return out;
  }

  function inside(triangles, x, y) {
    for (var i = 0; i < triangles.length; i += 1) {
      var tr = triangles[i];
      if (x < tr.x0 || x > tr.x1 || y < tr.y0 || y > tr.y1) continue;
      var t = tr.t;
      var d1 = (t[2] - t[0]) * (y - t[1]) - (t[3] - t[1]) * (x - t[0]);
      var d2 = (t[4] - t[2]) * (y - t[3]) - (t[5] - t[3]) * (x - t[2]);
      var d3 = (t[0] - t[4]) * (y - t[5]) - (t[1] - t[5]) * (x - t[4]);
      if ((d1 >= 0 && d2 >= 0 && d3 >= 0) || (d1 <= 0 && d2 <= 0 && d3 <= 0)) return true;
    }
    return false;
  }

  function onPolyline(x, y, points) {
    for (var i = 0; i + 1 < points.length; i += 1) {
      var ax = points[i][0], ay = points[i][1];
      var dx = points[i + 1][0] - ax, dy = points[i + 1][1] - ay;
      var length2 = dx * dx + dy * dy;
      var t = length2 ? Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / length2)) : 0;
      var ex = ax + t * dx - x, ey = ay + t * dy - y;
      if (ex * ex + ey * ey <= TOL * TOL) return true;
    }
    return false;
  }

  /* The loaded surface in the stage whose switched-off parts are `hidden` ({key: true}):
     straight pieces `{a, b, inward, depth: [at a, at b], water}`, each wholly below
     its water, `inward` the unit normal into the soil. Empty in 3D, with no soil
     drawn, or with no phreatic line. `sections` are the build payload's. */
  function pieces(project, sections, hidden) {
    hidden = hidden || {};
    if (!project || project.dimension !== 2 || !sections) return [];
    var list = waters(project, hidden);
    if (!list.length) return [];
    var soil = soilKeys(project);
    var alive = soil.filter(function (key) { return !hidden[key]; });
    var soilSections = sections.filter(function (s) {
      return soil.indexOf(s.key) >= 0 && (s.indices || []).length;
    });
    if (!soilSections.length) return [];

    // The domain's cut faces are the soil's extremes, every soil body's -- the stage
    // does not move them (`cut` in `_water_surface_loads`).
    var xMin = Infinity, xMax = -Infinity, yMin = Infinity;
    soilSections.forEach(function (s) {
      var p = s.positions || [];
      for (var i = 0; i + 2 < p.length; i += 3) {
        xMin = Math.min(xMin, p[i]); xMax = Math.max(xMax, p[i]);
        yMin = Math.min(yMin, p[i + 1]);
      }
    });
    var solid = trianglesOf(sections, alive);
    var drawn = (project.normal_loads || []).filter(function (load) {
      return load.active !== false && !hidden[load.id] && (load.points || []).length > 1;
    }).map(function (load) { return load.points; });

    function near(a, b) { return Math.abs(a - b) <= TOL; }
    function cut(ax, ay, bx, by) {
      return (near(ax, xMin) && near(bx, xMin)) || (near(ax, xMax) && near(bx, xMax))
        || (near(ay, yMin) && near(by, yMin));
    }

    // Every corner of the soil, so an edge is cut where a neighbour's boundary meets it
    // part way along: a side of which only the top was dug away is exposed there only.
    var corners = [];
    soilSections.forEach(function (s) {
      var e = s.edges || [];
      for (var i = 0; i + 2 < e.length; i += 3) corners.push([e[i], e[i + 1]]);
    });
    function split(ax, ay, bx, by) {
      var dx = bx - ax, dy = by - ay, length2 = dx * dx + dy * dy;
      var x0 = Math.min(ax, bx) - TOL, x1 = Math.max(ax, bx) + TOL;
      var y0 = Math.min(ay, by) - TOL, y1 = Math.max(ay, by) + TOL;
      var ts = [0, 1];
      corners.forEach(function (c) {
        if (c[0] < x0 || c[0] > x1 || c[1] < y0 || c[1] > y1) return;
        var t = ((c[0] - ax) * dx + (c[1] - ay) * dy) / length2;
        if (t <= 1e-9 || t >= 1 - 1e-9) return;
        if (Math.hypot(ax + dx * t - c[0], ay + dy * t - c[1]) <= TOL) ts.push(t);
      });
      ts.sort(function (p, q) { return p - q; });
      var out = [];
      for (var k = 1; k < ts.length; k += 1) {
        if ((ts[k] - ts[k - 1]) * Math.sqrt(length2) <= TOL) continue;
        out.push([ax + dx * ts[k - 1], ay + dy * ts[k - 1], ax + dx * ts[k], ay + dy * ts[k]]);
      }
      return out;
    }

    var out = [];
    soilSections.forEach(function (section) {
      if (hidden[section.key]) return;
      var e = section.edges || [];
      // The water on this body: the last of the writer's order that reaches it.
      var water = null;
      list.forEach(function (w) { if (bodyOf(w, section.key)) water = w; });
      if (!water) return;
      var segments = [];
      for (var i = 0; i + 5 < e.length; i += 6) {
        if (Math.hypot(e[i + 3] - e[i], e[i + 4] - e[i + 1]) > TOL) {
          segments = segments.concat(split(e[i], e[i + 1], e[i + 3], e[i + 4]));
        }
      }
      segments.forEach(function (s) {
        var ax = s[0], ay = s[1], bx = s[2], by = s[3];
        var length = Math.hypot(bx - ax, by - ay);
        if (!(length > TOL) || cut(ax, ay, bx, by)) return;
        var nx = -(by - ay) / length, ny = (bx - ax) / length;
        var mx = (ax + bx) / 2, my = (ay + by) / 2;
        var left = inside(solid, mx + nx * SIDE, my + ny * SIDE);
        var right = inside(solid, mx - nx * SIDE, my - ny * SIDE);
        if (left === right) return;
        if (drawn.some(function (points) { return onPolyline(mx, my, points); })) return;
        var inward = left ? [nx, ny] : [-nx, -ny];
        wet(water, [ax, ay], [bx, by]).forEach(function (piece) {
          piece.inward = inward;
          piece.water = water.id;
          out.push(piece);
        });
      });
    });
    return out;
  }

  /* The parts of the segment a-b below `water`'s line, with the depth at each end.
     Split at the line's own corners, between which both are straight. */
  function wet(water, a, b) {
    var cuts = [0, 1];
    var dx = b[0] - a[0], dy = b[1] - a[1];
    if (dx) {
      water.x_coordinates.forEach(function (x) {
        var t = (x - a[0]) / dx;
        if (t > 0 && t < 1) cuts.push(t);
      });
    }
    cuts.sort(function (p, q) { return p - q; });
    function at(t) { return [a[0] + dx * t, a[1] + dy * t]; }
    function depth(t) { var p = at(t); return level(water, p[0]) - p[1]; }
    var out = [];
    for (var k = 1; k < cuts.length; k += 1) {
      var t0 = cuts[k - 1], t1 = cuts[k];
      if (t1 - t0 < 1e-12) continue;
      var d0 = depth(t0), d1 = depth(t1);
      if (d0 <= TOL && d1 <= TOL) continue;
      if (d0 < 0) { t0 = t0 + (t1 - t0) * d0 / (d0 - d1); d0 = 0; }
      else if (d1 < 0) { t1 = t0 + (t1 - t0) * d0 / (d0 - d1); d1 = 0; }
      out.push({ a: at(t0), b: at(t1), depth: [Math.max(0, d0), Math.max(0, d1)] });
    }
    return out;
  }

  /* What viewport.js draws for `list` (`pieces`): small arrows into the soil, longer
     under deeper water, and the line through their tails -- the shape of the
     pressure, kept small and sparse so it reads as context, not as a load the user
     drew. `length` is the deepest arrow's; `spacing` how far apart they stand, on one
     grid along x (or y, on a steep face) so pieces that meet keep the rhythm.

     An arrow's length is in proportion to the depth, as the pressure is: nought at the
     water line, the full `length` where the water is deepest, and a straight line
     through the tails -- the triangle or trapezoid of a water pressure.

     Given `lines` ({water id: its Phreatic_Multi_Line record}, `linesOf`), an arrow in
     the open water -- on a piece that faces up, as `waterBody` fills -- reaches from
     its water's line down to the ground instead, as long as the water is: it stands
     in the water the fill draws, connected to the line it hangs from. An arrow on an
     upright face keeps its length in proportion, as no line is above it. */
  function glyph(list, length, spacing, lines) {
    // `deepestAt` is where the water is deepest, and `deepestInward` its piece's
    // `inward`: where the pressure is written.
    var spec = { arrows: [], tails: [], deepest: 0, deepestAt: null, deepestInward: null };
    list.forEach(function (piece) {
      [0, 1].forEach(function (end) {
        if (piece.depth[end] > spec.deepest) {
          spec.deepest = piece.depth[end];
          spec.deepestAt = (end ? piece.b : piece.a).slice();
          spec.deepestInward = piece.inward ? piece.inward.slice() : null;
        }
      });
    });
    if (!(spec.deepest > 0) || !(length > 0) || !(spacing > 0)) return spec;
    function size(depth) { return length * Math.max(0, depth) / spec.deepest; }
    list.forEach(function (piece) {
      var a = piece.a, b = piece.b, n = piece.inward;
      function tail(p, depth) {
        var s = size(depth);
        return [p[0] - n[0] * s, p[1] - n[1] * s];
      }
      spec.tails.push([tail(a, piece.depth[0]), tail(b, piece.depth[1])]);
      var water = lines && facesUp(piece) ? lines[piece.water] : null;
      var axis = Math.abs(b[0] - a[0]) >= Math.abs(b[1] - a[1]) ? 0 : 1;
      var lo = Math.min(a[axis], b[axis]), hi = Math.max(a[axis], b[axis]);
      if (!(hi > lo)) return;
      for (var g = Math.ceil(lo / spacing) * spacing; g < hi; g += spacing) {
        var t = (g - a[axis]) / (b[axis] - a[axis]);
        var tip = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
        var depth = piece.depth[0] + (piece.depth[1] - piece.depth[0]) * t;
        var s = water ? reach(water, tip, n) : null;
        if (s === null) s = size(depth);
        if (s < length * 0.05) continue;
        spec.arrows.push({ tip: tip, direction: n.slice(), length: s });
      }
    });
    return spec;
  }

  /* A piece the open water stands on: its soil is below it. Upright and overhung faces
     are not, the pieces above them hold that water. */
  function facesUp(piece) { return !!piece.inward && piece.inward[1] < -0.2; }

  /* How far back from `tip`, against `inward` (pointing down into the soil), the line
     of `water` is: where an arrow on `tip` starts to hang from that line. The line is
     straight between its corners and level past its ends, so the distance is found
     one straight stretch at a time. Null where the line is not above `tip`. */
  function reach(water, tip, inward) {
    var nx = inward[0], ny = inward[1];
    if (!(ny < 0)) return null;
    function gap(s) { return tip[1] - ny * s - level(water, tip[0] - nx * s); }
    var stops = [0];
    if (Math.abs(nx) > 1e-12) {
      water.x_coordinates.forEach(function (x) {
        var s = (tip[0] - x) / nx;
        if (s > 0) stops.push(s);
      });
    }
    stops.sort(function (p, q) { return p - q; });
    for (var k = 0; k < stops.length; k += 1) {
      var s0 = stops[k], g0 = gap(s0);
      if (g0 >= 0) return s0;
      // Past the last corner the line is level and the gap closes at -ny per metre.
      if (k + 1 === stops.length) return s0 - g0 / -ny;
      var s1 = stops[k + 1], g1 = gap(s1);
      if (g1 >= 0) return s0 + (s1 - s0) * -g0 / (g1 - g0);
    }
    return null;
  }

  /* The Phreatic_Multi_Line conditions of `project` by id: the lines `glyph` hangs the
     arrows in the open water from. */
  function linesOf(project) {
    var out = {};
    ((project && project.boundary_conditions) || []).forEach(function (c) {
      if (c.kind === 'water_pressure' && c.fluid_pressure_type === 'Phreatic_Multi_Line'
          && (c.x_coordinates || []).length >= 2
          && (c.y_coordinates || []).length === c.x_coordinates.length) {
        out[c.id] = c;
      }
    });
    return out;
  }

  /* The lines of the soil's geometry in the section: the boundary of each soil body of
     the sections `keys`, as {a: [x, y], b: [x, y], key, outer}. `outer` is an edge of
     the soil's outer boundary, with soil on one side and none on the other; the others
     are inside the soil, between two bodies -- a layer boundary, a line that splits the
     soil (lines.js). Read on both sides of each edge rather than by matching the edges
     of neighbouring bodies, whose triangulations need not share their vertices, so a
     line between two bodies is there once for each.

     The build sends each triangle of a 2D section twice, once per winding (its front
     and its back), so a triangle is counted once whatever its winding: a body's own
     boundary is the edges one of its triangles has. */
  function geometryLines(sections, keys) {
    var triangles = trianglesOf(sections || [], keys || []);
    var out = [];
    (sections || []).forEach(function (section) {
      if ((keys || []).indexOf(section.key) < 0) return;
      var p = section.positions || [], idx = section.indices || [];
      var count = {};
      var ends = {};
      var seen = {};
      for (var i = 0; i + 2 < idx.length; i += 3) {
        var corners3 = [idx[i], idx[i + 1], idx[i + 2]];
        var triangle = corners3.slice().sort(function (m, n) { return m - n; }).join(':');
        if (seen[triangle]) continue;
        seen[triangle] = true;
        [[corners3[0], corners3[1]], [corners3[1], corners3[2]],
         [corners3[2], corners3[0]]].forEach(function (edge) {
          var name = Math.min(edge[0], edge[1]) + ':' + Math.max(edge[0], edge[1]);
          count[name] = (count[name] || 0) + 1;
          ends[name] = edge;
        });
      }
      Object.keys(count).forEach(function (name) {
        if (count[name] !== 1) return;
        var a = [p[ends[name][0] * 3], p[ends[name][0] * 3 + 1]];
        var b = [p[ends[name][1] * 3], p[ends[name][1] * 3 + 1]];
        var dx = b[0] - a[0], dy = b[1] - a[1];
        var length = Math.sqrt(dx * dx + dy * dy);
        if (!length) return;
        var mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
        var nx = -dy / length * SIDE, ny = dx / length * SIDE;
        out.push({ a: a, b: b, key: section.key,
                   outer: inside(triangles, mx + nx, my + ny)
                     !== inside(triangles, mx - nx, my - ny) });
      });
    });
    return out;
  }

  /* The soil's outer boundary in the section (`geometryLines`, `outer`). Where a seepage
     face and a flux can be (writer `_edge_conditions`). */
  function outline(sections, keys) {
    return geometryLines(sections, keys).filter(function (edge) { return edge.outer; });
  }

  /* Whether the polyline `points` runs along `edges` (`geometryLines`): each point and
     the middle of each stretch on one of them. A stretch from one side of the soil
     straight across to another has its middle in the soil, on none. */
  function runsAlong(edges, points) {
    if (!points || !points.length) return false;
    var probes = points.slice();
    for (var i = 1; i < points.length; i += 1) {
      probes.push([(points[i - 1][0] + points[i][0]) / 2,
                   (points[i - 1][1] + points[i][1]) / 2]);
    }
    return probes.every(function (q) {
      var near = nearestOn(edges, q[0], q[1]);
      return !!near && near.distance <= TOL;
    });
  }

  /* The point of `edges` (`outline`, `geometryLines`) nearest to (x, y), as
     {point: [x, y], distance}, or null with no edge. */
  function nearestOn(edges, x, y) {
    var best = null;
    (edges || []).forEach(function (edge) {
      var dx = edge.b[0] - edge.a[0], dy = edge.b[1] - edge.a[1];
      var length2 = dx * dx + dy * dy;
      var t = length2 ? Math.max(0, Math.min(1, ((x - edge.a[0]) * dx
                                                 + (y - edge.a[1]) * dy) / length2)) : 0;
      var px = edge.a[0] + t * dx, py = edge.a[1] + t * dy;
      var distance = Math.sqrt((px - x) * (px - x) + (py - y) * (py - y));
      if (!best || distance < best.distance) best = { point: [px, py], distance: distance };
    });
    return best;
  }

  /* The corners of the lines `edges` (`geometryLines`), as [[x, y], ...]: where a line
     turns, ends, or meets another -- a layer boundary reaching the side of the model, a
     line that splits the soil. The build splits a straight line into several edges, and
     a line between two bodies is there once for each; where it carries on straight is no
     corner. */
  var STRAIGHT = 1e-2;   // the sine of the largest bend that is still straight on, ~0.6°

  function corners(edges) {
    var at = {};
    (edges || []).forEach(function (edge) {
      [[edge.a, edge.b], [edge.b, edge.a]].forEach(function (end) {
        var name = Math.round(end[0][0] / TOL) + ':' + Math.round(end[0][1] / TOL);
        var node = at[name] = at[name] || { point: end[0], ways: [] };
        var ux = end[1][0] - end[0][0], uy = end[1][1] - end[0][1];
        var length = Math.sqrt(ux * ux + uy * uy);
        if (!length) return;
        var way = [ux / length, uy / length];
        // The same way out twice (the line of two bodies) is one way.
        if (!node.ways.some(function (w) {
          return Math.abs(w[0] * way[1] - w[1] * way[0]) < STRAIGHT
            && w[0] * way[0] + w[1] * way[1] > 0;
        })) node.ways.push(way);
      });
    });
    var out = [];
    Object.keys(at).forEach(function (name) {
      var p = at[name].point, ways = at[name].ways;
      // Two ways out, opposite: the line runs straight on.
      if (ways.length === 2 && Math.abs(ways[0][0] * ways[1][1] - ways[0][1] * ways[1][0])
          < STRAIGHT && ways[0][0] * ways[1][0] + ways[0][1] * ways[1][1] < 0) return;
      out.push([p[0], p[1]]);
    });
    return out;
  }

  /* To the micrometre, as a snapped click is (draw-input.js `snapTo`). */
  function micro(value) { return Math.round(value * 1e6) / 1e6; }

  /* Where `edge` crosses the grid lines `step` apart, within `step` of `q` along it. A
     grid line the edge runs along is not a crossing. */
  function crossings(edge, step, q) {
    var out = [];
    [0, 1].forEach(function (axis) {
      var from = edge.a[axis], span = edge.b[axis] - from;
      if (Math.abs(span) < TOL) return;
      var lo = Math.max(Math.min(from, from + span), q[axis] - step);
      var hi = Math.min(Math.max(from, from + span), q[axis] + step);
      for (var k = Math.ceil(lo / step - 1e-9); k <= Math.floor(hi / step + 1e-9); k += 1) {
        var t = (k * step - from) / span;
        var p = [edge.a[0] + t * (edge.b[0] - edge.a[0]), edge.a[1] + t * (edge.b[1] - edge.a[1])];
        p[axis] = k * step;
        out.push([micro(p[0]), micro(p[1])]);
      }
    });
    return out;
  }

  /* (x, y) moved onto the lines `edges` (`geometryLines`): to their nearest point,
     always -- a flow boundary condition is on a line of the geometry and nowhere else.
     With a snapping distance `step`, then on along the lines to the nearest, within
     `step`, of their `corners` (`corners`) and of the points where they cross a grid
     line of `step`: a corner of the soil, or a round coordinate, and still on the line.
     {point, distance} as `nearestOn`, or null with no edge. */
  function snapOnto(edges, cornerList, x, y, step) {
    var near = nearestOn(edges, x, y);
    if (!near || !(step > 0)) return near;
    var q = near.point;
    var best = null;
    function consider(p) {
      var d = Math.sqrt((p[0] - q[0]) * (p[0] - q[0]) + (p[1] - q[1]) * (p[1] - q[1]));
      if (d <= step + 1e-9 && (!best || d < best.away - 1e-9)) best = { point: p, away: d };
    }
    // The corners first, so a corner on a grid line is taken as the corner.
    (cornerList || []).forEach(consider);
    edges.forEach(function (edge) {
      // Only the edges that come within `step` of where the click landed.
      if (Math.min(edge.a[0], edge.b[0]) > q[0] + step
          || Math.max(edge.a[0], edge.b[0]) < q[0] - step
          || Math.min(edge.a[1], edge.b[1]) > q[1] + step
          || Math.max(edge.a[1], edge.b[1]) < q[1] - step) return;
      crossings(edge, step, q).forEach(consider);
    });
    if (!best) return near;
    var p = best.point;
    return { point: [p[0], p[1]],
             distance: Math.sqrt((p[0] - x) * (p[0] - x) + (p[1] - y) * (p[1] - y)) };
  }

  /* The soil body of the sections `keys` at (x, y), or null outside the soil. */
  function soilAt(sections, keys, x, y) {
    var found = null;
    (keys || []).some(function (key) {
      if (inside(trianglesOf(sections || [], [key]), x, y)) found = key;
      return !!found;
    });
    return found;
  }

  /* Which stages of `order` (App.Stages.order: the stages in execution order, empty
     for a model with no stages) have water on the ground, per phreatic line: `{water
     id: [stage name, ...]}`, or `{water id: [null]}` for a model with no stages.
     `hiddenOf(stage id)` is what that stage has switched off ({key: true}). */
  function stagesWithWater(project, sections, order, hiddenOf) {
    var out = {};
    var list = (order && order.length) ? order : [null];
    list.forEach(function (stage) {
      var hidden = stage ? hiddenOf(stage.id) : {};
      var seen = {};
      pieces(project, sections, hidden).forEach(function (piece) {
        if (seen[piece.water]) return;
        seen[piece.water] = true;
        (out[piece.water] = out[piece.water] || []).push(stage ? stage.name : null);
      });
    });
    return out;
  }

  /* The pressure of a Hydrostatic water pressure condition along the line it is on:
     `path` ([x, y] points, its drawn line or its face), in pieces as `pieces` gives
     them, wholly below its level. A pressure has no direction, so `inward` only says
     which side the diagram stands on: towards `centre` (the domain's middle), so a
     face's is drawn outside the soil, and a line's on the side away from the middle.
     Empty for any other type: a uniform pressure is its value, and a phreatic or head
     line is drawn as the line it is. */
  function along(record, path, centre) {
    if (!record || record.fluid_pressure_type !== 'Hydrostatic'
        || typeof record.reference_coordinate !== 'number' || !path) return [];
    var water = { x_coordinates: [0], y_coordinates: [record.reference_coordinate] };
    var out = [];
    for (var k = 0; k + 1 < path.length; k += 1) {
      var a = [path[k][0], path[k][1]], b = [path[k + 1][0], path[k + 1][1]];
      var length = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (!(length > TOL)) continue;
      var n = [-(b[1] - a[1]) / length, (b[0] - a[0]) / length];
      var mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
      if (centre && (centre[0] - mx) * n[0] + (centre[1] - my) * n[1] < 0) n = [-n[0], -n[1]];
      wet(water, a, b).forEach(function (piece) {
        piece.inward = n;
        piece.water = record.id;
        out.push(piece);
      });
    }
    return out;
  }

  /* The open water standing on the ground, as quads of [x, y] corners: each piece of
     `list` (`pieces`) that faces up, raised to its water's line. Together they fill
     the water between the ground and the phreatic line -- over a pit's floor, the pit
     -- so the water on the ground reads as water, apart from the lines. A face that
     is upright or overhung adds nothing: the pieces above it fill that water. */
  function waterBody(list) {
    return list.filter(facesUp).map(function (piece) {
      return [piece.a.slice(), piece.b.slice(),
              [piece.b[0], piece.b[1] + piece.depth[1]],
              [piece.a[0], piece.a[1] + piece.depth[0]]];
    });
  }

  /* The water's specific weight in the project's units, as the export takes it
     (`Project.water_specific_weight`): the project's own, or water's. Null where the
     unit tables are not loaded. */
  function specificWeight(project) {
    var given = project && project.water && project.water.specific_weight;
    if (typeof given === 'number') return given;
    if (!App.SoilModels || !App.Units) return null;
    var system = (project && project.unit_system) || undefined;
    var g = project ? project.gravity_acceleration : undefined;
    return App.SoilModels.water(system, null, null, null, g).DENSITY_WATER
      * App.Units.gravity(system, g);
  }

  /* "p = 10 kPa": the pressure under `depth` of water, in the project's units, or null
     where the weight is not known. */
  function pressureText(project, depth) {
    var weight = specificWeight(project);
    if (!(weight > 0) || !(depth > 0)) return null;
    var unit = App.Units && App.Units.label ? App.Units.label('stress', project.unit_system) : '';
    return 'p = ' + Number((weight * depth).toPrecision(3)) + (unit ? ' ' + unit : '');
  }

  return { pieces: pieces, glyph: glyph, level: level, stagesWithWater: stagesWithWater,
           along: along, waterBody: waterBody, specificWeight: specificWeight,
           pressureText: pressureText, linesOf: linesOf, reach: reach, waters: waters,
           geometryLines: geometryLines, outline: outline, runsAlong: runsAlong,
           nearestOn: nearestOn, corners: corners, snapOnto: snapOnto,
           soilAt: soilAt, soilKeys: soilKeys };
})();
