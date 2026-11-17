/* ══════════════════════════════════════════════════════════════════
   structure-glyphs.js — how a sheet pile, an anchor and an interface look.

   The server sends a sheet pile, an anchor and a free interface as bare lines
   (core/geometry/tessellation.py `_overlay_section`): two end points per segment
   and no triangles. Drawn as a WebGL line that is one pixel wide whatever is asked
   for, so a sheet pile read as a faint hairline on the soil and vanished into
   the mesh, an anchor was lost under the load arrows, and an interface along a
   pile was not drawn at all.

   So each one is drawn as triangles of a fixed size *on screen*, in the
   convention a geotechnical engineer reads at a glance:

     • sheet pile  a thick dark steel band;
     • anchor      a thinner green band with a dot at each end;
     • interface   a dashed purple line. One along a pile runs beside it, on the
                   face or faces it unglues (`side`); one on its own line runs
                   along that line.

   Pixel-sized means the triangles are rebuilt when the camera moves, which is
   cheap -- a handful of segments per part. This file is the arithmetic only: it
   takes polylines in model coordinates and a description of the view, and gives
   back flat triangle positions. No three.js and no DOM, so it runs headless
   (frontend/tests/run_headless.py); viewport.js puts the result on screen.

   A view is `{ toCamera, right, up, px }`: unit vectors in model space, and the
   model length one screen pixel spans at the part.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.StructureGlyphs = (function () {
  'use strict';

  /* Widths, dashes and dot radii are in screen pixels. `order` stacks them: an
     interface's dashes over the pile they run beside, an anchor's head over both. */
  var STYLES = {
    pile:      { color: '#2b3442', width: 6, order: 30 },
    interface: { color: '#9b30d9', width: 3, dash: 9, gap: 6, order: 31 },
    anchor:    { color: '#16804c', width: 3, dot: 3.5, order: 32 }
  };

  /* How far an interface's dashes sit from the middle of the pile they run along:
     clear of the pile's own band, with a sliver of soil showing between. */
  var BESIDE_PILE = STYLES.pile.width / 2 + 2 + STYLES.interface.width / 2;

  /* A dashed line with more dashes than this has its pattern stretched instead:
     zoomed far in on a long interface, the dashes off screen would otherwise run
     to hundreds of thousands of triangles. */
  var MAX_DASHES = 2000;

  var DOT_SEGMENTS = 16;

  /* Unit vectors toward each face `side` can name, in the section's x-y plane. */
  var FACE = { left: [-1, 0], right: [1, 0], below: [0, -1], above: [0, 1] };

  /* ── Small vector arithmetic on [x, y, z] arrays ── */

  function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function add(a, b) { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
  function scale(a, s) { return [a[0] * s, a[1] * s, a[2] * s]; }
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function cross(a, b) {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  }
  function size(a) { return Math.sqrt(dot(a, a)); }
  function unit(a) { var s = size(a); return s > 1e-12 ? scale(a, 1 / s) : null; }

  /* ── Which glyph a part key takes ── */

  /* 'pile', 'anchor', 'interface', or null for a key that is none of them. Read
     from the project rather than from the key's spelling: ids are the user's. */
  function kindOf(key, project) {
    function has(list) {
      return (list || []).some(function (record) { return record.id === key; });
    }
    if (!project || !key) return null;
    if (has(project.beams)) return 'pile';
    if (has(project.anchors)) return 'anchor';
    if (has(project.interfaces)) return 'interface';
    return null;
  }

  /* A section's flat LineSegments pairs as two-point polylines. */
  function edgePaths(flat) {
    var paths = [];
    for (var i = 0; i + 5 < (flat || []).length; i += 6) {
      paths.push({ points: [[flat[i], flat[i + 1], flat[i + 2]],
                            [flat[i + 3], flat[i + 4], flat[i + 5]]] });
    }
    return paths;
  }

  /* The lines an interface is drawn as, in model coordinates at depth `z`.

     `path` is what it runs along (App.Interfaces.pathOf). Along a pile it is drawn
     beside the pile on each face it unglues -- both, for the usual retaining wall --
     so the pile stays visible between them. On a line of its own there is no pile
     to clear and it is drawn on the line. */
  function interfacePaths(record, path, faces, z) {
    if (!record || !path || path.length < 2) return [];
    var points = path.map(function (p) { return [p[0], p[1], z]; });
    if (!record.structure) return [{ points: points }];
    var names = faces || ['left', 'right'];
    var sides = record.side === 'both' ? names
      : [record.side === 'left' || record.side === 'below' ? names[0] : names[1]];
    return sides.map(function (side) {
      return { points: points, face: FACE[side], offset: BESIDE_PILE };
    });
  }

  /* ── Triangles ── */

  /* The screen-facing sideways direction of a segment: across it, in the plane the
     viewer sees it in. A segment pointing straight at the camera has no such
     direction; the screen's own up stands in. */
  function across(direction, view) {
    return unit(cross(direction, view.toCamera)) || view.up;
  }

  /* Where a path's segment sits once moved `offset` pixels toward `face`. The
     direction is the segment's own normal in the x-y plane, turned toward the face,
     so a pile drawn top-down or bottom-up puts "left" on the same side. */
  function shifted(a, b, path, px) {
    if (!path.face || !path.offset) return [a, b];
    var normal = unit([-(b[1] - a[1]), b[0] - a[0], 0]);
    if (!normal) return [a, b];
    if (normal[0] * path.face[0] + normal[1] * path.face[1] < 0) normal = scale(normal, -1);
    var by = scale(normal, path.offset * px);
    return [add(a, by), add(b, by)];
  }

  function pushQuad(out, a, b, side, half, lift) {
    var a0 = add(add(a, scale(side, -half)), lift), a1 = add(add(a, scale(side, half)), lift);
    var b0 = add(add(b, scale(side, -half)), lift), b1 = add(add(b, scale(side, half)), lift);
    out.push(a0[0], a0[1], a0[2], b0[0], b0[1], b0[2], b1[0], b1[1], b1[2],
             a0[0], a0[1], a0[2], b1[0], b1[1], b1[2], a1[0], a1[1], a1[2]);
  }

  function pushDot(out, centre, radius, view, lift) {
    var c = add(centre, lift);
    for (var i = 0; i < DOT_SEGMENTS; i++) {
      var t0 = (i / DOT_SEGMENTS) * 2 * Math.PI, t1 = ((i + 1) / DOT_SEGMENTS) * 2 * Math.PI;
      var p0 = add(c, add(scale(view.right, Math.cos(t0) * radius), scale(view.up, Math.sin(t0) * radius)));
      var p1 = add(c, add(scale(view.right, Math.cos(t1) * radius), scale(view.up, Math.sin(t1) * radius)));
      out.push(c[0], c[1], c[2], p0[0], p0[1], p0[2], p1[0], p1[1], p1[2]);
    }
  }

  /* The dashes of a path, as [from, to] pairs of model points. The pattern runs on
     across the path's bends rather than restarting at each, so a bent interface
     reads as one dashed line. */
  function dashes(points, dash, gap) {
    var total = 0, i;
    for (i = 1; i < points.length; i++) total += size(sub(points[i], points[i - 1]));
    var period = dash + gap;
    if (total / period > MAX_DASHES) {
      var stretch = total / period / MAX_DASHES;
      dash *= stretch; gap *= stretch; period = dash + gap;
    }
    var out = [];
    var phase = 0;                       // how far into the current period we are
    for (i = 1; i < points.length; i++) {
      var a = points[i - 1], b = points[i];
      var length = size(sub(b, a));
      if (length < 1e-12) continue;
      var walked = 0;
      while (walked < length) {
        var on = phase < dash;
        var step = Math.min(length - walked, on ? dash - phase : period - phase);
        if (on) {
          out.push([add(a, scale(sub(b, a), walked / length)),
                    add(a, scale(sub(b, a), (walked + step) / length))]);
        }
        walked += step;
        phase = (phase + step) % period;
      }
    }
    return out;
  }

  /* Flat triangle positions for `paths` drawn in `style`, as seen in `view`.

     Every point is lifted a few pixels toward the camera. The viewport draws these
     over everything regardless, but the software renderer has no depth test to
     switch off -- it paints far to near -- and on a section the soil and the pile
     sit at exactly the same depth. */
  function triangles(paths, style, view) {
    var out = [];
    var px = view.px;
    var half = (style.width / 2) * px;
    var lift = scale(view.toCamera, 4 * px);
    paths.forEach(function (path) {
      var points = path.points;
      for (var i = 1; i < points.length; i++) {
        var seg = shifted(points[i - 1], points[i], path, px);
        var direction = sub(seg[1], seg[0]);
        if (size(direction) < 1e-12) continue;
        var side = across(direction, view);
        if (style.dash) {
          // In pixels, so the pattern holds its look at every zoom.
          dashes(seg, style.dash * px, style.gap * px).forEach(function (piece) {
            pushQuad(out, piece[0], piece[1], side, half, lift);
          });
        } else {
          pushQuad(out, seg[0], seg[1], side, half, lift);
        }
        // A round join, so a bent pile has no notch where two bands meet.
        if (!style.dash && i > 1) pushDot(out, seg[0], half, view, lift);
      }
      if (style.dot) {
        pushDot(out, points[0], style.dot * px, view, lift);
        pushDot(out, points[points.length - 1], style.dot * px, view, lift);
      }
    });
    return out;
  }

  /* ── Picking ── */

  /* How far a pointer may be from a band's edge, in screen pixels, and still pick
     it. The bands are thin -- an interface is 3 px of dashes with gaps between --
     so a click had to land on a dash itself; the gaps took nothing. */
  var PICK_PX = 6;

  function pointToSegment(p, a, b) {
    var dx = b.x - a.x, dy = b.y - a.y;
    var length2 = dx * dx + dy * dy;
    var t = length2 > 0 ? ((p.x - a.x) * dx + (p.y - a.y) * dy) / length2 : 0;
    t = Math.max(0, Math.min(1, t));
    var ex = a.x + t * dx - p.x, ey = a.y + t * dy - p.y;
    return Math.sqrt(ex * ex + ey * ey);
  }

  /* How many screen pixels `click` is from the band `paths` are drawn as in
     `style`: 0 on it, and the gaps between an interface's dashes count as on it.
     `px` is the model length of a pixel (as for `triangles`), and `toScreen(p)` a
     model point's `{x, y}` in pixels, or null where it is off the view. Infinity
     when nothing of it is on screen. */
  function screenDistance(paths, style, px, toScreen, click) {
    var best = Infinity;
    function consider(distance) { if (distance < best) best = Math.max(0, distance); }
    (paths || []).forEach(function (path) {
      var points = path.points;
      for (var i = 1; i < points.length; i++) {
        var seg = shifted(points[i - 1], points[i], path, px);
        var a = toScreen(seg[0]), b = toScreen(seg[1]);
        if (a && b) consider(pointToSegment(click, a, b) - style.width / 2);
      }
      if (style.dot) {
        [points[0], points[points.length - 1]].forEach(function (end) {
          var c = toScreen(end);
          if (c) consider(pointToSegment(click, c, c) - style.dot);
        });
      }
    });
    return best;
  }

  /* Of `candidates` -- `{ distance, order }` each, plus whatever the caller keeps on
     them -- the one a click picks: the nearest within PICK_PX, and of two as near,
     the one drawn on top (an interface beside a pile over the pile). Null if none. */
  function nearest(candidates) {
    var best = null;
    (candidates || []).forEach(function (c) {
      if (!(c.distance <= PICK_PX)) return;
      if (!best || c.distance < best.distance - 1e-9
          || (Math.abs(c.distance - best.distance) <= 1e-9 && c.order > best.order)) best = c;
    });
    return best;
  }

  /* Model length per screen pixel at `point`: constant for an orthographic camera;
     for a perspective one it grows with the distance from the eye. */
  function pixelSize(camera, point, heightPx) {
    if (!heightPx) return 0;
    if (camera.ortho) return (camera.top - camera.bottom) / (camera.zoom || 1) / heightPx;
    var away = size(sub(point, camera.position));
    return 2 * away * Math.tan((camera.fov * Math.PI / 180) / 2) / heightPx;
  }

  /* The middle of a set of paths, which is where a perspective view is sized. */
  function centreOf(paths) {
    var sum = [0, 0, 0], n = 0;
    paths.forEach(function (path) {
      path.points.forEach(function (p) { sum = add(sum, p); n += 1; });
    });
    return n ? scale(sum, 1 / n) : sum;
  }

  return {
    STYLES: STYLES, BESIDE_PILE: BESIDE_PILE, MAX_DASHES: MAX_DASHES, FACE: FACE,
    kindOf: kindOf, edgePaths: edgePaths, interfacePaths: interfacePaths,
    dashes: dashes, triangles: triangles, pixelSize: pixelSize, centreOf: centreOf,
    PICK_PX: PICK_PX, screenDistance: screenDistance, nearest: nearest
  };
})();
