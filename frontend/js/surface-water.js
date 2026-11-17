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
     through the tails -- the triangle or trapezoid of a water pressure. */
  function glyph(list, length, spacing) {
    var spec = { arrows: [], tails: [], deepest: 0 };
    list.forEach(function (piece) {
      spec.deepest = Math.max(spec.deepest, piece.depth[0], piece.depth[1]);
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
      var axis = Math.abs(b[0] - a[0]) >= Math.abs(b[1] - a[1]) ? 0 : 1;
      var lo = Math.min(a[axis], b[axis]), hi = Math.max(a[axis], b[axis]);
      if (!(hi > lo)) return;
      for (var g = Math.ceil(lo / spacing) * spacing; g < hi; g += spacing) {
        var t = (g - a[axis]) / (b[axis] - a[axis]);
        var depth = piece.depth[0] + (piece.depth[1] - piece.depth[0]) * t;
        var s = size(depth);
        if (s < length * 0.05) continue;
        spec.arrows.push({ tip: [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t],
                           direction: n.slice(), length: s });
      }
    });
    return spec;
  }

  return { pieces: pieces, glyph: glyph, level: level };
})();
