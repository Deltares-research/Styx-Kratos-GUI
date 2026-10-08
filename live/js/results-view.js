/* ══════════════════════════════════════════════════════════════════
   results-view.js — the contoured mesh on screen.

   The three.js and the DOM of the Results mode, and nothing else. Every decision about
   *what* to draw — which value lands on which vertex, what colour it becomes, where the
   deformed position is, what the legend says — is made in `results-render.js`, which
   has no DOM in it and is therefore the only half a machine with no browser can test.
   This file is the half that cannot be tested here, so it is kept as thin as it can be:
   it allocates buffers, hands them to three.js, and writes text into a div.

   ── How it sits in the scene ─────────────────────────────────────────────

   One `THREE.Group` of its own, outside the viewport's `groups` map, in the same way
   `showImportedMesh` keeps an imported deck outside it. Nothing that walks the model
   tree finds these objects, and clearing the mode is one `remove` plus a dispose.

   ── One position buffer per section ──────────────────────────────────────

   The surface and its line work share a single position attribute. That is not a
   micro-optimisation: the deformation factor moves vertices, and two buffers would be
   two places to apply it and one of them would eventually be forgotten — drawing a
   sheet pile standing straight up through a settled mesh.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.ResultsView = (function () {

  var group = null;        // the THREE.Group holding everything we drew
  var drawn = [];          // per section: its buffers and the values on its vertices
  var shown = null;        // the last payload, for the probe and the legend
  var legendHost = null;

  function scene() {
    return App.Viewport && App.Viewport.getScene && App.Viewport.getScene();
  }

  function render() {
    if (App.Viewport && App.Viewport.requestRender) App.Viewport.requestRender();
  }

  /* ── Clearing ─────────────────────────────────────────────────────────── */

  function clear() {
    var host = scene();
    if (group && host) host.remove(group);
    if (group) {
      group.traverse(function (child) {
        if (child.geometry) child.geometry.dispose();
        if (child.material) child.material.dispose();
      });
    }
    group = null;
    drawn = [];
    shown = null;
    showLegend(null);
    render();
  }

  function isShowing() { return !!group; }

  /* ── Drawing ──────────────────────────────────────────────────────────── */

  /* `payload` is what `App.Results.present` assembles: {mesh, field, options, stage}. */
  function draw(payload) {
    var host = scene();
    if (!host || !payload || !payload.mesh || !payload.field) return;
    if (typeof THREE === 'undefined') return;

    clear();
    shown = payload;
    group = new THREE.Group();
    group.name = 'results';

    var factor = deformFactor(payload);

    (payload.mesh.sections || []).forEach(function (section) {
      var values = App.ResultsRender.vertexValues(section, payload.field);
      var colors = App.ResultsRender.colors(values, payload.options);
      var positions = factor
        ? App.ResultsRender.deform(section, displacementOf(payload), factor)
        : new Float32Array(section.positions);

      var position = new THREE.BufferAttribute(positions, 3);
      var color = new THREE.BufferAttribute(colors, 3);
      var objects = [];

      if (section.indices && section.indices.length) {
        objects.push(surface(section, position, color));
      }
      if (section.edge_indices && section.edge_indices.length) {
        objects.push(lines(section, position, color));
      }
      // Built only when asked for: on a 5 000-element deck the outlines are most of
      // the index data, and the contour is read without them most of the time.
      var outline = payload.options && payload.options.mesh
        && section.wire_indices && section.wire_indices.length
        ? wire(section, position) : null;
      if (outline) objects.push(outline);
      objects.forEach(function (object) { group.add(object); });
      drawn.push({ section: section, values: values.values, positions: positions,
                   objects: objects });
    });

    host.add(group);
    syncVisibility();
    showLegend(payload);
    render();
  }

  /* Each part's contour follows the eye of its row in the Model explorer -- the deck
     part of the same name, for a deck case (App.Deck.resultShown). A part with no row
     there is always drawn. */
  function syncVisibility() {
    var eyeOf = App.Viewport && App.Viewport.importedEye;
    if (!eyeOf || !App.Deck) return;
    drawn.forEach(function (entry) {
      var on = App.Deck.resultShown(entry.section.part, eyeOf);
      (entry.objects || []).forEach(function (object) { object.visible = on; });
    });
    render();
  }

  function surface(section, position, color) {
    var geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', position);
    geometry.setAttribute('color', color);
    geometry.setIndex(section.indices);
    var material = new THREE.MeshBasicMaterial({
      vertexColors: true,
      // Both faces: a 2D section is a single plane and a camera that ends up behind
      // it must not see through the model.
      side: THREE.DoubleSide
    });
    var mesh = new THREE.Mesh(geometry, material);
    mesh.name = section.key;
    mesh.userData.key = section.key;
    return mesh;
  }

  /* `results mesh on`: each element's own sides over the shading (the server's
     `wire_indices`, through the mid-side nodes). The shading's position buffer, not a
     copy, so the outline deforms with it. Dark and partly transparent, so the colours
     still read through a fine mesh; below the structural line work (renderOrder 20),
     so a sheet pile is not hatched over by the soil it sits in. */
  function wire(section, position) {
    var geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', position);
    geometry.setIndex(section.wire_indices);
    var material = new THREE.LineBasicMaterial({
      color: 0x37474f, transparent: true, opacity: 0.6, depthTest: false
    });
    var outline = new THREE.LineSegments(geometry, material);
    outline.name = section.key + ':mesh';
    outline.renderOrder = 15;
    return outline;
  }

  function lines(section, position, color) {
    var geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', position);
    geometry.setAttribute('color', color);
    geometry.setIndex(section.edge_indices);
    var material = new THREE.LineBasicMaterial({ vertexColors: true });
    var segments = new THREE.LineSegments(geometry, material);
    segments.name = section.key + ':lines';
    // Above the surface it sits on, so a wall drawn in the plane of the soil is not
    // half-swallowed by it.
    segments.renderOrder = 20;
    material.depthTest = false;
    return segments;
  }

  /* The displacement the deformation uses.

     `TOTAL_DISPLACEMENT` if the field on screen happens to be it, otherwise whatever
     the payload carries as `displacement`. `App.Results` fetches that alongside the
     field when the factor is not zero; with nothing to deform by, the factor is
     ignored rather than guessed at. */
  function displacementOf(payload) {
    return payload.displacement || { ids: [], values: [] };
  }

  function deformFactor(payload) {
    var wanted = payload.options && payload.options.deform;
    if (!wanted) return 0;
    var displacement = displacementOf(payload);
    if (!displacement.ids.length) return 0;
    if (wanted !== 'auto') return wanted;

    var largest = 0;
    displacement.values.forEach(function (d) {
      var size = Math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]);
      if (size > largest) largest = size;
    });
    return App.ResultsRender.autoFactor(largest, payload.mesh.bbox);
  }

  /* ── The legend ───────────────────────────────────────────────────────── */

  function host() {
    return typeof document === 'undefined'
      ? null : document.getElementById('viewport');
  }

  function ensureLegend() {
    var parent = host();
    if (!parent) return null;
    if (!legendHost || !legendHost.parentNode) {
      legendHost = document.createElement('div');
      legendHost.id = 'vp-legend';
      legendHost.className = 'vp-hud vp-legend';
      parent.appendChild(legendHost);
    }
    return legendHost;
  }

  function showLegend(payload) {
    var box = legendHost;
    if (!payload) {
      if (box) box.hidden = true;
      return;
    }
    box = ensureLegend();
    if (!box) return;

    var options = payload.options;
    var ticks = App.ResultsRender.legend(options, 7);

    /* The gradient comes from `ResultsRender.ramp`, which is the same banding and the
       same reversal the vertex colours went through. It used to be worked out here,
       which meant two implementations of "which way round is this" -- and a legend
       that reads backwards against the model it explains is worse than no legend. */
    var stops = App.ResultsRender.ramp(options, 24).map(function (stop) {
      return css(stop.rgb) + ' ' + Math.round(stop.t * 100) + '%';
    });

    var rows = ticks.map(function (tick) {
      return '<li style="top:' + ((1 - tick.t) * 100).toFixed(1) + '%">'
             + escape(tick.label) + '</li>';
    }).join('');

    box.hidden = false;
    box.innerHTML =
      '<div class="vp-legend-title">' + escape(payload.field.label) + '</div>'
      + '<div class="vp-legend-unit">' + escape(payload.field.unit) + '</div>'
      + '<div class="vp-legend-body">'
      + '<i style="background:linear-gradient(to top,' + stops.join(',') + ')"></i>'
      + '<ul>' + rows + '</ul>'
      + '</div>'
      + '<div class="vp-legend-foot">phase ' + payload.stage + '</div>';
  }

  function css(rgb) {
    return 'rgb(' + rgb.map(function (c) {
      return Math.round(Math.max(0, Math.min(1, c)) * 255);
    }).join(',') + ')';
  }

  function escape(text) {
    return String(text === undefined || text === null ? '' : text)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  /* ── The probe ────────────────────────────────────────────────────────── */

  /* The value at the vertex nearest a world point, with its node id.

     Nearest vertex rather than an interpolation across the triangle: the number a user
     is checking is the one the solver produced at a node, and an interpolated value is
     not a number that exists anywhere in the output. */
  function nearest(point) {
    var best = null;
    drawn.forEach(function (entry) {
      var positions = entry.positions;
      for (var i = 0; i < entry.section.node_ids.length; i++) {
        var dx = positions[i * 3] - point.x;
        var dy = positions[i * 3 + 1] - point.y;
        var dz = positions[i * 3 + 2] - point.z;
        var distance = dx * dx + dy * dy + dz * dz;
        if (best === null || distance < best.distance) {
          best = {
            distance: distance,
            node: entry.section.node_ids[i],
            part: entry.section.part,
            value: entry.values[i]
          };
        }
      }
    });
    return best;
  }

  /* What the status bar says while the pointer is over the model. */
  function describeAt(point) {
    if (!shown) return '';
    var found = nearest(point);
    if (!found) return '';
    return 'node ' + found.node + (found.part ? ' · ' + found.part : '')
         + ' · ' + shown.field.label + ' '
         + (found.value === null || found.value === undefined
            ? '—' : App.ResultsRender.format(found.value))
         + ' ' + shown.field.unit;
  }

  /* ── Extremes ─────────────────────────────────────────────────────────── */

  /* Where the largest and smallest values are, as `{min, max}` of
     `{node, part, value, point}` -- what the min/max markers label. */
  function extremes() {
    var low = null, high = null;
    drawn.forEach(function (entry) {
      entry.values.forEach(function (value, i) {
        if (value === null || value === undefined) return;
        var at = {
          node: entry.section.node_ids[i], part: entry.section.part, value: value,
          point: [entry.positions[i * 3], entry.positions[i * 3 + 1],
                  entry.positions[i * 3 + 2]]
        };
        if (low === null || value < low.value) low = at;
        if (high === null || value > high.value) high = at;
      });
    });
    return { min: low, max: high };
  }

  return {
    draw: draw, clear: clear, isShowing: isShowing, syncVisibility: syncVisibility,
    describeAt: describeAt, nearest: nearest, extremes: extremes,
    showLegend: showLegend
  };
})();
