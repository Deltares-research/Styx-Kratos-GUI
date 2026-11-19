/* ══════════════════════════════════════════════════════════════════
   results-render.js — turning a field into what gets drawn.

   Everything in here is arithmetic on arrays: a field's values onto a section's
   vertices, those values into a colour buffer, a displacement into deformed positions,
   a range into legend ticks, a field into CSV. The three.js that consumes all of it is
   in the viewport; none of it is here.

   That split is not tidiness. There is no Node and no browser on this machine, so the
   only JavaScript that gets executed automatically is JavaScript with no DOM in it —
   `frontend/tests/run_headless.py` runs this file under quickjs. Anything moved from here
   into the viewport stops being tested at all, so the rule is: if it can be decided
   without a canvas, it is decided here.

   ── The contract with the server ─────────────────────────────────────────

   A section from `/stages/{n}/mesh` has `node_ids[i]` and `positions[3i..3i+2]` for
   vertex *i*. A field from `/stages/{n}/field/{name}` has `ids` and `values`, sorted by
   id and *not* in the section's vertex order. Zipping the two positionally would look
   correct on a section whose vertices happen to be sorted and be silently wrong on
   every other one, so everything here goes through an id lookup.

   ── Holes are not zeroes ─────────────────────────────────────────────────

   A vertex can have no value: it belongs to a body this stage excavated, or to a part
   the GiD writer does not emit. `null` travels all the way to the colour buffer, where
   it becomes ABSENT grey. Substituting zero would paint a floor of "no stress" across
   an open pit, which reads as a result rather than as an absence.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.ResultsRender = (function () {

  /* ── Colour maps ──────────────────────────────────────────────────────── */

  /* Anchors at equal spacing, interpolated between, written as hex because that is
     the form these are published in and the form they can be checked against. Data,
     not code: a map is added by adding a line here and a label below, and nothing that
     uses one has to change. */
  var MAPS = {
    /* The rainbow, this app's default. Kept
       and defaulted to because comparing two runs is far easier when the pictures
       look alike -- not because it reads better than the perceptual maps under it. */
    rainbow:   ['#000099', '#0033ff', '#00b3ff', '#00ffb3', '#66ff33',
                '#e6ff00', '#ffbf00', '#ff6600', '#cc0000'],
    /* Google's rainbow, fixed: the same span of hues without the false bands that
       make a plain rainbow invent edges the data does not have. */
    turbo:     ['#30123b', '#4145ab', '#4675ed', '#39a2fc', '#1bcfd4', '#24eca6',
                '#61fc6c', '#a4fc3b', '#d1e834', '#f3c63a', '#fe9b2d', '#ea7026',
                '#cb2a04', '#7a0403'],
    /* Perceptually ordered and safe in greyscale, and what to reach for when a
       gradient has to be believed rather than merely looked at. */
    viridis:   ['#440154', '#482475', '#414487', '#355f8d', '#2a788e', '#21918c',
                '#22a884', '#44bf70', '#7ad151', '#bddf26', '#fde725'],
    plasma:    ['#0d0887', '#4b03a1', '#7d03a8', '#a82296', '#cb4679', '#e56b5d',
                '#f89441', '#fdc328', '#f0f921'],
    inferno:   ['#000004', '#1b0c41', '#4a0c6b', '#781c6d', '#a52c60', '#cf4446',
                '#ed6925', '#fb9b06', '#f7d13d', '#fcffa4'],
    /* Diverging, for a quantity whose sign matters more than its size -- a shear
       stress, a displacement component, anything read against zero. */
    diverging: ['#053061', '#4575b4', '#a6cee3', '#f7f7f7', '#f4a582', '#d6604d',
                '#67001f'],
    spectral:  ['#9e0142', '#d53e4f', '#f46d43', '#fdae61', '#fee08b', '#ffffbf',
                '#e6f598', '#abdda4', '#66c2a5', '#3288bd', '#5e4fa2'],
    /* Single hue, for a quantity with no meaningful zero. */
    blues:     ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6',
                '#2171b5', '#08519c', '#08306b'],
    /* For printing, and for a figure that has to survive being photocopied. */
    greyscale: ['#1a1a1a', '#404040', '#666666', '#8c8c8c', '#b3b3b3', '#d9d9d9',
                '#f5f5f5']
  };

  /* What the pickers show. Separate from the data so a map's name in a command stays
     short and typeable while its label can say what it is for. */
  var MAP_LABELS = {
    rainbow: 'Rainbow',
    turbo: 'Turbo (rainbow, even)',
    viridis: 'Viridis (perceptual)',
    plasma: 'Plasma',
    inferno: 'Inferno',
    diverging: 'Diverging (blue–red)',
    spectral: 'Spectral',
    blues: 'Blues',
    greyscale: 'Greyscale (print)'
  };

  /* Hex parsed once per colour, not once per vertex: a 4 400-node contour asks for a
     colour 4 400 times and every one of them would otherwise re-parse the same string. */
  var parsed = {};

  function rgbOf(hex) {
    if (!parsed[hex]) {
      parsed[hex] = [parseInt(hex.slice(1, 3), 16) / 255,
                     parseInt(hex.slice(3, 5), 16) / 255,
                     parseInt(hex.slice(5, 7), 16) / 255];
    }
    return parsed[hex];
  }

  /* The grey a vertex with no value takes. Deliberately unlike anything in the maps
     above: a hole has to be visible as a hole. */
  var ABSENT = [0.62, 0.62, 0.60];

  /* The fallback for a name nothing recognises. The same map `results.js`
     defaults to, so an unknown name degrades to what the app would have drawn
     anyway rather than to a different picture. */
  var DEFAULT_MAP = 'rainbow';

  /* How much of the model's diagonal the largest displacement becomes when the
     deformation factor is automatic. Big enough to read at a glance, small enough
     that the shape is still recognisably the model. */
  var AUTO_FRACTION = 0.06;

  function clamp01(value) {
    return value < 0 ? 0 : value > 1 ? 1 : value;
  }

  /* One colour off a map, at 0..1 along it. */
  function sample(name, t) {
    var anchors = MAPS[name] || MAPS[DEFAULT_MAP];
    var last = anchors.length - 1;
    var scaled = clamp01(t) * last;
    var low = Math.floor(scaled);
    if (low >= last) return rgbOf(anchors[last]).slice();
    var f = scaled - low;
    var a = rgbOf(anchors[low]), b = rgbOf(anchors[low + 1]);
    return [a[0] + (b[0] - a[0]) * f,
            a[1] + (b[1] - a[1]) * f,
            a[2] + (b[2] - a[2]) * f];
  }

  /* Where a value sits along the ramp: normalised, banded, then reversed.

     One function because there are two things painted from it -- the model and the
     legend beside it -- and two implementations of "which way round is this" would
     eventually disagree. A legend that reads backwards against the model it explains
     is worse than no legend at all. */
  function position(value, settings) {
    var span = settings.max - settings.min;
    // A flat field is the case that divides by zero and paints the model with NaN.
    // The middle of the ramp is the honest answer: every value is the same, so no
    // value is higher than any other.
    var t = span > 0 ? clamp01((value - settings.min) / span) : 0.5;
    var bands = settings.bands > 0 ? Math.floor(settings.bands) : 0;
    if (bands) t = Math.min(Math.floor(t * bands), bands - 1) / (bands - 1 || 1);
    return settings.reversed ? 1 - t : t;
  }

  /* The ramp itself, as `steps + 1` stops from the low end to the high. What the
     legend's gradient is built from, so it bands and reverses with the model. */
  function ramp(options, steps) {
    var settings = options || {};
    var n = Math.max(2, steps || 24);
    var map = settings.map || DEFAULT_MAP;
    var stops = [];
    for (var i = 0; i <= n; i++) {
      var t = i / n;
      stops.push({ t: t, rgb: sample(map, position(t, {
        min: 0, max: 1, bands: settings.bands, reversed: settings.reversed
      })) });
    }
    return stops;
  }

  /* ── A field onto a section's vertices ────────────────────────────────── */

  /* `{values: [...], missing: n}` — one entry per vertex, `null` where the field has
     nothing for it.

     Two shapes of field arrive here. A nodal one is keyed by node id and lands
     directly. An element one has no node ids at all, so its value is spread to the
     three vertices of each of its triangles and averaged where they overlap — the same
     rule the server uses to put a Gauss value on a node, applied on this side because
     only the section knows which vertices a triangle has. */
  function vertexValues(section, field) {
    var count = (section.node_ids || []).length;
    var values = new Array(count);
    var i;

    if (field.location === 'elements') {
      /* A per-element value has no node id, so it is spread to the vertices of the
         triangles that element produced and averaged where they overlap.

         Which triangle came from which element is *not* derivable here: a six-node
         triangle makes four of them, so the n-th triangle is not the n-th element.
         The server says so explicitly in `triangle_elements`, one id per triangle.
         Without it there is nothing safe to assume, so nothing is drawn — a smeared
         field would look plausible and be wrong. */
      var total = new Array(count), seen = new Array(count);
      for (i = 0; i < count; i++) { total[i] = 0; seen[i] = 0; }
      var byElement = lookup(field.ids, field.values);
      var indices = section.indices || [];
      var provenance = section.triangle_elements || [];

      for (i = 0; i < indices.length; i += 3) {
        var element = provenance[i / 3];
        var value = element === undefined ? undefined : byElement[element];
        if (value === undefined) continue;
        for (var k = 0; k < 3; k++) {
          var vertex = indices[i + k];
          total[vertex] += value;
          seen[vertex] += 1;
        }
      }
      var missingElements = 0;
      for (i = 0; i < count; i++) {
        if (seen[i]) values[i] = total[i] / seen[i];
        else { values[i] = null; missingElements++; }
      }
      return { values: values, missing: missingElements };
    }

    var byNode = lookup(field.ids, field.values);
    var missing = 0;
    for (i = 0; i < count; i++) {
      var found = byNode[section.node_ids[i]];
      if (found === undefined) { values[i] = null; missing++; }
      else values[i] = found;
    }
    return { values: values, missing: missing };
  }

  function lookup(ids, values) {
    var table = {};
    for (var i = 0; i < (ids || []).length; i++) table[ids[i]] = values[i];
    return table;
  }

  /* ── Colour ───────────────────────────────────────────────────────────── */

  /* A Float32Array of r,g,b per vertex, ready for a `color` buffer attribute.

     `options`: {min, max, map, bands}. Banding quantises the *ramp*, never the data —
     the probe still reports the value that was computed, and only the colour is
     stepped. */
  function colors(vertex, options) {
    var settings = options || {};
    var values = vertex.values || [];
    var out = new Float32Array(values.length * 3);
    var map = settings.map || DEFAULT_MAP;

    for (var i = 0; i < values.length; i++) {
      var rgb;
      if (values[i] === null || values[i] === undefined) {
        rgb = ABSENT;
      } else {
        rgb = sample(map, position(values[i], settings));
      }
      out[i * 3] = rgb[0];
      out[i * 3 + 1] = rgb[1];
      out[i * 3 + 2] = rgb[2];
    }
    return out;
  }

  /* ── The legend ───────────────────────────────────────────────────────── */

  /* Ticks from the top of the ramp down, because that is the way a colour bar is
     read: the maximum is at the top. */
  function legend(range, count) {
    var n = Math.max(2, count || 6);
    var ticks = [];
    for (var i = 0; i < n; i++) {
      var t = 1 - i / (n - 1);
      var value = range.min + (range.max - range.min) * t;
      ticks.push({ t: t, value: value, label: format(value) });
    }
    return ticks;
  }

  /* Short enough to sit beside a colour bar, and never in a notation that hides the
     magnitude. Three significant figures is what a contour legend can honestly
     claim. */
  function format(value) {
    var size = Math.abs(value);
    if (size === 0) return '0';
    if (size >= 1e5 || size < 1e-3) return value.toExponential(2);
    var decimals = size >= 100 ? 0 : size >= 10 ? 1 : size >= 1 ? 2 : 4;
    return value.toFixed(decimals);
  }

  /* The smallest and the largest value and where they are, as `kratos-cli results field`
     says them. For a saved picture, whatever the legend's limits were set to. `null` for a
     field with no values. */
  function rangeLines(field) {
    var low = null, high = null;
    (field.values || []).forEach(function (value, i) {
      if (value === null || value === undefined) return;
      if (low === null || value < field.values[low]) low = i;
      if (high === null || value > field.values[high]) high = i;
    });
    if (low === null) return null;
    var where = field.location === 'elements' ? 'element' : 'node';
    function say(name, i) {
      return name + ' value = ' + format(field.values[i]) + (field.unit ? ' ' + field.unit : '')
           + ' (' + where + ' ' + field.ids[i] + ')';
    }
    return [say('Maximum', high), say('Minimum', low)];
  }

  /* ── Deformation ──────────────────────────────────────────────────────── */

  /* Original positions plus `factor` times the displacement at each vertex. A vertex
     the displacement field says nothing about does not move. */
  function deform(section, displacement, factor) {
    var positions = section.positions || [];
    var out = new Float32Array(positions.length);
    var byNode = lookup(displacement.ids, displacement.values);

    for (var i = 0; i < section.node_ids.length; i++) {
      var d = byNode[section.node_ids[i]];
      for (var axis = 0; axis < 3; axis++) {
        var at = i * 3 + axis;
        out[at] = positions[at] + (d ? d[axis] * factor : 0);
      }
    }
    return out;
  }

  /* ── ID labels ────────────────────────────────────────────────────────── */

  /* Where the node and element numbers of one drawn section go, as `{id, x, y, z}`
     (frontend/js/mesh-labels.js). `positions` are the ones on screen -- deformed when
     the mesh is -- so a number stays on its node at any deformation factor.

     A node goes at its vertex. An element goes at the mean of the vertices it is drawn
     with: the triangles it makes (`triangle_elements`) and its line work
     (`edge_elements`). For the simplices a deck holds that is its centroid, as
     `writer._element_labels` places it -- a quadratic element's extra nodes are edge
     midpoints. A 3D section draws only its skin, so a solid's number sits on the face
     that is seen. */
  function labelPoints(section, positions, kind) {
    var at = positions || section.positions || [];
    function point(id, i) {
      return { id: id, x: at[3 * i], y: at[3 * i + 1], z: at[3 * i + 2] };
    }
    var nodeIds = section.node_ids || [];
    if (kind !== 'elements') {
      return nodeIds.map(function (id, i) { return point(id, i); });
    }
    var vertices = {}, order = [];
    function take(element, vertex) {
      if (element === undefined || element === null || vertex === undefined) return;
      if (!vertices[element]) { vertices[element] = {}; order.push(element); }
      vertices[element][vertex] = true;
    }
    var indices = section.indices || [];
    (section.triangle_elements || []).forEach(function (element, t) {
      for (var k = 0; k < 3; k++) take(element, indices[3 * t + k]);
    });
    var edges = section.edge_indices || [];
    (section.edge_elements || []).forEach(function (element, e) {
      take(element, edges[2 * e]);
      take(element, edges[2 * e + 1]);
    });
    return order.map(function (element) {
      var list = Object.keys(vertices[element]);
      var sum = [0, 0, 0];
      list.forEach(function (v) {
        for (var axis = 0; axis < 3; axis++) sum[axis] += at[3 * v + axis];
      });
      return { id: element, x: sum[0] / list.length, y: sum[1] / list.length,
               z: sum[2] / list.length };
    });
  }

  /* The factor that makes the largest movement a readable fraction of the model.

     A ceiling, not a normalisation: a model that has already moved further than that
     keeps a factor of 1, because exaggerating a collapse is misleading and shrinking
     it would be worse. */
  function autoFactor(largest, bbox) {
    if (!(largest > 0) || !bbox) return 1;
    var span = Math.max(bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2]);
    if (!(span > 0)) return 1;
    var wanted = AUTO_FRACTION * span / largest;
    return wanted > 1 ? wanted : 1;
  }

  /* ── Contour lines ────────────────────────────────────────────────────── */

  /* Where `values` crosses `level` across a section's triangles, as line segments: a
     Float32Array of x,y,z,x,y,z per segment, in the coordinates of `positions` (the
     drawn, possibly deformed, buffer -- so the line sits on the shading it explains).

     Marching triangles: a triangle with vertices on both sides of the level is cut
     once, between the two points where its sides cross it, each found by linear
     interpolation along that side. Neighbouring triangles interpolate the shared side
     the same way, so the pieces join into one line.

     "Below" is strictly less than the level and everything else is above. The zero
     water pressure line is what this is for, and a stage's pressure is often exactly
     zero over the dry ground (a tension cut-off, or no water at all): with the level
     itself counted as above, the line runs along the edge of the wet region instead
     of tracing every flat zero triangle, and a field that is zero everywhere has no
     line. A triangle with a hole in it has no value to interpolate and is skipped. */
  function isoline(section, values, positions, level) {
    var at = level || 0;
    var indices = (section && section.indices) || [];
    var points = [];
    var corner = [0, 0, 0], value = [0, 0, 0], below = [false, false, false];

    function cross(a, b) {
      var t = (at - value[a]) / (value[b] - value[a]);
      for (var c = 0; c < 3; c++) {
        var pa = positions[corner[a] * 3 + c], pb = positions[corner[b] * 3 + c];
        points.push(pa + t * (pb - pa));
      }
    }

    for (var i = 0; i + 2 < indices.length; i += 3) {
      var count = 0, usable = true;
      for (var k = 0; k < 3; k++) {
        corner[k] = indices[i + k];
        value[k] = values[corner[k]];
        if (value[k] === null || value[k] === undefined || !isFinite(value[k])) {
          usable = false;
          break;
        }
        below[k] = value[k] < at;
        if (below[k]) count++;
      }
      if (!usable || count === 0 || count === 3) continue;
      // The corner on its own side of the level; the line cuts the two sides it is on.
      var lone = below[0] !== below[1] && below[0] !== below[2] ? 0
               : below[1] !== below[0] && below[1] !== below[2] ? 1 : 2;
      // A lone corner exactly at the level touches it at a point: no segment.
      if (value[lone] === at) continue;
      cross(lone, (lone + 1) % 3);
      cross(lone, (lone + 2) % 3);
    }
    return new Float32Array(points);
  }

  /* The pieces of the polylines `lines` ([[x, y], ...] each) that lie outside every
     triangle of `meshes` ({indices, positions}, positions x,y,z as drawn), as line
     segments x,y,z,x,y,z at height `z`. In the section's plane: x and y only.

     What carries the zero pressure line on past the soil: inside it the calculation
     found where the water stands, outside it -- over a ditch, a pit, the water against
     a wall -- the phreatic line the user drew is the water's surface. The line's ends
     meet the soil's boundary where the boundary's prescribed pressure is nought, which
     is where the traced line ends too, so the two read as one line.

     A stretch running along the soil's boundary, within `OUTSIDE_TOL` of it, counts as
     inside: a phreatic line drawn on the ground surface would otherwise flicker in and
     out of the triangles along it on round-off alone. */
  var OUTSIDE_TOL = 1e-3;

  function outside(lines, meshes, z) {
    var triangles = [];
    (meshes || []).forEach(function (mesh) {
      var idx = mesh.indices || [], p = mesh.positions || [];
      for (var i = 0; i + 2 < idx.length; i += 3) {
        var a = idx[i] * 3, b = idx[i + 1] * 3, c = idx[i + 2] * 3;
        var t = [p[a], p[a + 1], p[b], p[b + 1], p[c], p[c + 1]];
        var area = (t[2] - t[0]) * (t[5] - t[1]) - (t[3] - t[1]) * (t[4] - t[0]);
        if (!area) continue;
        triangles.push({ t: t, sign: area > 0 ? 1 : -1,
                         x0: Math.min(t[0], t[2], t[4]) - OUTSIDE_TOL,
                         x1: Math.max(t[0], t[2], t[4]) + OUTSIDE_TOL,
                         y0: Math.min(t[1], t[3], t[5]) - OUTSIDE_TOL,
                         y1: Math.max(t[1], t[3], t[5]) + OUTSIDE_TOL });
      }
    });

    // The stretch [t0, t1] of a + t·d that is inside `tr`, or null: the segment cut by
    // each side's half-plane in turn.
    function within(tr, ax, ay, dx, dy) {
      var lo = 0, hi = 1, t = tr.t;
      for (var k = 0; k < 3; k++) {
        var px = t[k * 2], py = t[k * 2 + 1];
        var ex = t[((k + 1) % 3) * 2] - px, ey = t[((k + 1) % 3) * 2 + 1] - py;
        var f0 = tr.sign * (ex * (ay - py) - ey * (ax - px))
               + OUTSIDE_TOL * Math.sqrt(ex * ex + ey * ey);
        var f1 = tr.sign * (ex * dy - ey * dx);
        if (f1 === 0) {
          if (f0 < 0) return null;
        } else if (f1 > 0) {
          lo = Math.max(lo, -f0 / f1);
        } else {
          hi = Math.min(hi, -f0 / f1);
        }
        if (lo >= hi) return null;
      }
      return [lo, hi];
    }

    var points = [];
    var at = z || 0;
    (lines || []).forEach(function (line) {
      for (var k = 0; k + 1 < (line || []).length; k++) {
        var ax = line[k][0], ay = line[k][1];
        var dx = line[k + 1][0] - ax, dy = line[k + 1][1] - ay;
        var length = Math.sqrt(dx * dx + dy * dy);
        if (!(length > 0)) continue;
        var x0 = Math.min(ax, ax + dx), x1 = Math.max(ax, ax + dx);
        var y0 = Math.min(ay, ay + dy), y1 = Math.max(ay, ay + dy);
        var spans = [];
        triangles.forEach(function (tr) {
          if (tr.x1 < x0 || tr.x0 > x1 || tr.y1 < y0 || tr.y0 > y1) return;
          var span = within(tr, ax, ay, dx, dy);
          if (span) spans.push(span);
        });
        spans.sort(function (p, q) { return p[0] - q[0]; });
        var free = [], from = 0;
        spans.forEach(function (span) {
          if (span[0] > from) free.push([from, span[0]]);
          from = Math.max(from, span[1]);
        });
        if (from < 1) free.push([from, 1]);
        // The tolerance the triangles were grown by, given back where a piece meets
        // the soil, so it reaches the boundary the traced line ends on.
        var grown = OUTSIDE_TOL / length;
        free.forEach(function (piece) {
          // Slivers between two triangles that share a side are round-off, not water.
          if ((piece[1] - piece[0]) * length <= OUTSIDE_TOL) return;
          var t0 = piece[0] > 0 ? Math.max(0, piece[0] - grown) : 0;
          var t1 = piece[1] < 1 ? Math.min(1, piece[1] + grown) : 1;
          points.push(ax + dx * t0, ay + dy * t0, at,
                      ax + dx * t1, ay + dy * t1, at);
        });
      }
    });
    return new Float32Array(points);
  }

  /* ── Arrows ───────────────────────────────────────────────────────────── */

  /* How long the longest arrow is, as a fraction of the model's largest span: long
     enough to read a direction off. */
  var ARROW_FRACTION = 0.04;
  var ARROW_HEAD = 0.3;          // the head's length, as a fraction of the arrow's
  var ARROW_HEAD_ANGLE = 25 * Math.PI / 180;
  var ARROW_SMALLEST = 1e-3;     // shorter than this fraction of the longest: no arrow

  /* A vector field as arrows: line segments, x,y,z,x,y,z per segment, three per arrow
     (the shaft and the two sides of its head).

     `vectors` is the server's `{ids, values, max}`, one vector per node id. `placed` is
     where each node is drawn -- `[{node_ids, positions}]`, the sections with the drawn
     (possibly deformed) positions -- so an arrow starts at its node on the shading.
     Each arrow is to the same scale: the longest is `ARROW_FRACTION` of the model's
     largest span (`bbox`), and the others in proportion, so a length can be compared.

     One arrow at every node the vector was written at -- none thinned out, so what is
     drawn is what the calculation wrote. A node in no section, or whose vector is
     shorter than `ARROW_SMALLEST` of the longest (too short to see), has none. The
     heads lie in the plane of the section, the xy plane, which is the one this program
     draws. */
  function arrows(vectors, placed, bbox) {
    var ids = (vectors && vectors.ids) || [];
    var values = (vectors && vectors.values) || [];
    var largest = 0, i;
    for (i = 0; i < values.length; i++) largest = Math.max(largest, size(values[i]));
    if (!(largest > 0) || !bbox) return new Float32Array(0);
    var span = Math.max(bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2]);
    if (!(span > 0)) return new Float32Array(0);
    var length = ARROW_FRACTION * span;
    var scale = length / largest;

    // Where each node is drawn: the first section that has it.
    var where = {};
    (placed || []).forEach(function (entry) {
      var nodes = entry.node_ids || [];
      for (var k = 0; k < nodes.length; k++) {
        if (where[nodes[k]] === undefined) {
          where[nodes[k]] = [entry.positions[k * 3], entry.positions[k * 3 + 1],
                             entry.positions[k * 3 + 2]];
        }
      }
    });

    // One arrow per node the vector was written at, in the order written.
    var points = [];
    for (i = 0; i < ids.length; i++) {
      var p = where[ids[i]], v = values[i];
      if (!p || !v || size(v) < ARROW_SMALLEST * largest) continue;
      var tip = [p[0] + v[0] * scale, p[1] + v[1] * scale, p[2] + (v[2] || 0) * scale];
      points.push(p[0], p[1], p[2], tip[0], tip[1], tip[2]);
      // The head, back from the tip in the plane of the section.
      var bx = -v[0], by = -v[1], back = Math.sqrt(bx * bx + by * by);
      if (!(back > 0)) continue;
      var head = ARROW_HEAD * size(v) * scale;
      bx /= back; by /= back;
      [ARROW_HEAD_ANGLE, -ARROW_HEAD_ANGLE].forEach(function (angle) {
        var c = Math.cos(angle), s = Math.sin(angle);
        points.push(tip[0], tip[1], tip[2],
                    tip[0] + head * (c * bx - s * by), tip[1] + head * (s * bx + c * by),
                    tip[2]);
      });
    }
    return new Float32Array(points);
  }

  function size(v) {
    return Math.sqrt(v[0] * v[0] + v[1] * v[1] + (v[2] || 0) * (v[2] || 0));
  }

  /* ── CSV ──────────────────────────────────────────────────────────────── */

  /* One row per value, with the run and stage in the header so a file on someone's
     desk still says where it came from. */
  function csv(field, context) {
    var where = context || {};
    var idColumn = field.location === 'elements' ? 'element' : 'node';
    var head = idColumn + ',' + (field.field || 'value')
               + (field.unit ? ' [' + field.unit + ']' : '');
    var lines = [head];
    if (where.run) lines[0] += ',# ' + where.run
                               + (where.stage ? ' / ' + where.stage : '');
    for (var i = 0; i < field.ids.length; i++) {
      var value = field.values[i];
      // An empty cell, not a zero: a spreadsheet averaging a column of these must not
      // be handed zeroes for the nodes that had no value.
      lines.push(field.ids[i] + ',' + (value === null || value === undefined ? '' : value));
    }
    return lines.join('\n') + '\n';
  }

  return {
    MAPS: MAPS, MAP_LABELS: MAP_LABELS, ABSENT: ABSENT, DEFAULT_MAP: DEFAULT_MAP,
    AUTO_FRACTION: AUTO_FRACTION, ARROW_FRACTION: ARROW_FRACTION,
    sample: sample, position: position, ramp: ramp,
    vertexValues: vertexValues, colors: colors,
    legend: legend, format: format, rangeLines: rangeLines,
    deform: deform, autoFactor: autoFactor, isoline: isoline, outside: outside, arrows: arrows,
    csv: csv, labelPoints: labelPoints
  };
})();
