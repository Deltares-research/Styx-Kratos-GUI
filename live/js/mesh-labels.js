/* ══════════════════════════════════════════════════════════════════
   mesh-labels.js — the number, drawn on the thing it names.

   Node IDs started here, ported from D:/MyTools/Kratos-productivity-tools/Node_ViZ,
   which exists because a .mdpa is read by number: a solver message names node 4711 or
   element 902, and the only way to find it is to see the number on the mesh. Node_ViZ
   does that with a Plotly text trace per node plus, for nodes that share a position, a
   fan of labels around a small circle with leader lines back to the point. Both ideas
   are kept; the surroundings differ.

   Element IDs have no counterpart in Node_ViZ -- it reads a node table and nothing else
   -- so they are this app's own: an element's number goes at its centroid, which the
   server computes in the same pass that numbers it (server/app/kratos.py
   `_element_labels`). Everything downstream of "a number at a point" is then shared,
   which is why this module is about labels rather than about nodes: a kind is a list of
   points, a colour, and nothing more. Element edges, faces and whatever else comes next
   only have to say where their number goes.

   Three things had to change coming out of Node_ViZ:

   *   The mesh is a three.js scene, not a 2D Plotly figure, so a point's screen place is
       the camera's answer and changes every frame. The labels are therefore painted on
       an overlay canvas from the render tick -- the same arrangement ruler.js already
       uses, and for the same reason: a hundred absolutely-positioned elements per frame
       is not a thing to do inside requestAnimationFrame.
   *   A real mesh has far more nodes than a screen has room for. Node_ViZ answers that
       with a checkbox ("show all labels"); here the answer is a screen-space declutter
       grid plus a hard cap, so turning labels on is never a way to freeze the tab. The
       nearest point to the camera wins its cell, the two kinds share one grid so they
       cannot be drawn over each other, and what was dropped is counted so the caller can
       say "showing 800 of 41 000 — zoom in for more".
   *   The numbers are Kratos IDs, from the only two places that know them: an imported
       deck's own tables, and -- for a mesh this app generated -- the export numbering,
       which renumbers gmsh's tags 1..N *after* the interface split. A gmsh tag would be
       a different, wrong number.

   The arithmetic (groupCoincident, fanOffsets, plan) is deliberately separate from the
   painting: where a label goes is the part that can be wrong, so it is the part that is
   tested. See live/tests/test-mesh-labels.js.
   ══════════════════════════════════════════════════════════════════ */

(function (App) {
  'use strict';

  /* The label kinds, in the order they are planned. Nodes first: they are the numbers a
     solver message names most often, so they win a contested cell. */
  var KINDS = ['nodes', 'elements'];

  var DECIMALS = 6;
  /* Micrometres at metre scale. Two points this close are the same point -- which is
     exactly what an interface split leaves behind -- and one label would hide the other. */

  var FAN_RADIUS = 24;          // px from the shared point to each fanned label
  var FAN_START = -60;          // degrees, Node_ViZ's own opening angle
  var FAN_SPREAD = 240;         // degrees the fan is spread over
  var CELL = [46, 18];          // declutter grid, px: roughly one label's box
  var MAX_LABELS = 1500;        // beyond this the screen is a grey smudge anyway
  var MARGIN = 24;              // px outside the viewport a label may still be planned

  var FONT = '11px Consolas, monospace';
  var HALO = 'rgba(16, 22, 32, 0.85)';

  /* One colour per kind, and they have to be told apart at a glance: a node number and
     an element number sit within a couple of millimetres of each other on screen, and
     reading the wrong one is worse than not reading either. */
  var STYLE = {
    nodes:    { text: '#f2f6ff', dot: 'rgba(255, 213, 79, 0.95)',
                leader: 'rgba(210, 222, 240, 0.55)' },
    elements: { text: '#8fe3b4', dot: 'rgba(143, 227, 180, 0.95)',
                leader: 'rgba(143, 227, 180, 0.5)' }
  };

  /* ── Where the numbers come from ────────────────────────────── */

  function dedupe(points) {
    var seen = {}, out = [];
    points.forEach(function (point) {
      if (seen[point.id]) return;       // one entity, however many sections draw it
      seen[point.id] = true;
      out.push(point);
    });
    return out;
  }

  /* `[id, x, y, z]` rows, as POST /api/mesh/labels returns both tables and as an
     imported section carries its elements. */
  function pointsFromTable(rows) {
    return (rows || []).map(function (row) {
      return { id: row[0], x: row[1], y: row[2], z: row[3] };
    });
  }

  /* An imported deck's sections: each carries its own slice of the file's node table
     (server/app/mdpa_import.py `_section_dict`), one id per position triple. */
  function nodesFromSections(sections) {
    var out = [];
    (sections || []).forEach(function (section) {
      var ids = section && section.node_ids;
      var positions = section && section.positions;
      if (!ids || !positions) return;   // an older payload: say nothing rather than guess
      for (var i = 0; i < ids.length; i++) {
        out.push({ id: ids[i], x: positions[3 * i], y: positions[3 * i + 1],
                   z: positions[3 * i + 2] });
      }
    });
    return dedupe(out);
  }

  /* The same sections' elements, already reduced to a number and the point it goes at. */
  function elementsFromSections(sections) {
    var out = [];
    (sections || []).forEach(function (section) {
      if (!section || !section.elements) return;
      out = out.concat(pointsFromTable(section.elements));
    });
    return dedupe(out);
  }

  /* ── Coincident points ──────────────────────────────────────── */

  function groupCoincident(points, decimals) {
    var places = decimals === undefined ? DECIMALS : decimals;
    var byPlace = {}, groups = [];
    (points || []).forEach(function (point) {
      var key = point.x.toFixed(places) + '|' + point.y.toFixed(places) + '|'
              + point.z.toFixed(places);
      var group = byPlace[key];
      if (!group) {
        group = byPlace[key] = { x: point.x, y: point.y, z: point.z, ids: [] };
        groups.push(group);
      }
      group.ids.push(point.id);
    });
    groups.forEach(function (group) {
      group.ids.sort(function (a, b) { return a - b; });
    });
    return groups;
  }

  /* Where each label of a fan sits relative to the shared point, in screen pixels
     (y down). One label is not a fan and never reaches here. */
  function fanOffsets(count, radius) {
    var r = radius === undefined ? FAN_RADIUS : radius;
    var step = count > 1 ? FAN_SPREAD / (count - 1) : 0;
    var out = [];
    for (var i = 0; i < count; i++) {
      var angle = (FAN_START + i * step) * Math.PI / 180;
      out.push([r * Math.cos(angle), -r * Math.sin(angle)]);
    }
    return out;
  }

  /* ── Planning ───────────────────────────────────────────────── */

  /* `project(x, y, z)` is the camera's own answer -- {x, y, depth} in CSS pixels with y
     down, or null for a point behind it -- injected rather than taken, so this stays
     arithmetic and testable without a scene.

     `taken` is the occupancy grid, passed in when two kinds are on at once so the second
     cannot be planned into a cell the first already holds.

     Returns every label to paint, plus what it could not: `hidden` is the count the
     caller reports, because a label overlay that silently shows a tenth of the mesh is
     worse than one that says so. */
  function plan(options) {
    var groups = options.groups || [];
    var project = options.project;
    var width = options.width, height = options.height;
    var cell = options.cell || CELL;
    var max = options.max === undefined ? MAX_LABELS : options.max;
    var radius = options.radius === undefined ? FAN_RADIUS : options.radius;
    var taken = options.taken || {};

    var total = 0;
    var placed = [];
    groups.forEach(function (group) {
      total += group.ids.length;
      var p = project(group.x, group.y, group.z);
      if (!p) return;
      if (p.x < -MARGIN || p.y < -MARGIN || p.x > width + MARGIN || p.y > height + MARGIN) return;
      placed.push({ group: group, p: p });
    });

    // Nearest first, so the point in front is the one that keeps its number where two
    // compete for the same patch of screen.
    placed.sort(function (a, b) { return a.p.depth - b.p.depth; });

    var labels = [];
    for (var i = 0; i < placed.length; i++) {
      var group = placed[i].group, p = placed[i].p;
      var key = Math.floor(p.x / cell[0]) + ':' + Math.floor(p.y / cell[1]);
      if (taken[key]) continue;
      // Whole or not at all: half a fan reads as a point with fewer entities on it than
      // it has, which is the one thing these labels exist to show.
      if (labels.length + group.ids.length > max) continue;
      taken[key] = true;

      if (group.ids.length === 1) {
        labels.push({ id: group.ids[0], x: p.x, y: p.y - 6, ax: p.x, ay: p.y,
                      leader: false });
      } else {
        var offsets = fanOffsets(group.ids.length, radius);
        group.ids.forEach(function (id, index) {
          labels.push({ id: id, x: p.x + offsets[index][0], y: p.y + offsets[index][1],
                        ax: p.x, ay: p.y, leader: true });
        });
      }
    }

    return { labels: labels, shown: labels.length, hidden: total - labels.length,
             total: total, taken: taken };
  }

  /* ── State ──────────────────────────────────────────────────── */

  /* One layer per kind: whether it is on, the points it labels, and those points grouped
     by position. `last` is the most recent plan per kind, for the status line. */
  var layers = {};
  KINDS.forEach(function (kind) {
    layers[kind] = { on: false, points: [], groups: [] };
  });
  var last = {};

  function layer(kind) { return layers[kind]; }

  function setPoints(kind, list) {
    var it = layers[kind];
    if (!it) return;
    it.points = list || [];
    it.groups = groupCoincident(it.points);
    last[kind] = null;
  }

  function setActive(kind, on) {
    if (layers[kind]) layers[kind].on = !!on;
  }

  function isActive(kind) { return !!(layers[kind] && layers[kind].on); }
  function anyActive() { return KINDS.some(isActive); }
  function count(kind) { return layers[kind] ? layers[kind].points.length : 0; }
  function lastPlan(kind) { return last[kind] || null; }

  /* Everything off and every list dropped: what a new project means. */
  function reset() {
    KINDS.forEach(function (kind) {
      layers[kind] = { on: false, points: [], groups: [] };
      last[kind] = null;
    });
  }

  /* ── The menu ───────────────────────────────────────────────── */

  /* The viewport's right-click row. The two kinds are independent toggles, not a choice
     of one: a node number and the number of the element it belongs to are read together
     as often as apart, and they are drawn in different colours at different points for
     exactly that reason. */
  function menuItem() {
    return {
      label: 'Show labels', icon: 'vertex',
      sub: [
        { label: 'Node IDs', action: 'toggleNodeLabels', checked: isActive('nodes') },
        { label: 'Element IDs', action: 'toggleElementLabels',
          checked: isActive('elements') }
      ]
    };
  }

  /* ── The DOM ────────────────────────────────────────────────── */

  var canvas = null, host = null;

  function install(container) {
    host = container || document.getElementById('viewport');
    if (!host) return null;
    if (canvas) uninstall();
    canvas = document.createElement('canvas');
    canvas.className = 'vp-mesh-labels';
    canvas.hidden = true;
    host.appendChild(canvas);
    return canvas;
  }

  function uninstall() {
    if (canvas && canvas.parentNode) canvas.parentNode.removeChild(canvas);
    canvas = null;
  }

  function hide() {
    if (canvas) canvas.hidden = true;
    KINDS.forEach(function (kind) { last[kind] = null; });
  }

  function paintLayer(ctx, result, style) {
    // The leaders first, so a number is never drawn under a line pointing at it.
    ctx.strokeStyle = style.leader;
    ctx.lineWidth = 1;
    ctx.beginPath();
    result.labels.forEach(function (label) {
      if (!label.leader) return;
      ctx.moveTo(label.ax, label.ay);
      ctx.lineTo(label.x, label.y);
    });
    ctx.stroke();

    // One dot per shared point: the fan says "these numbers", the dot says "are here".
    ctx.fillStyle = style.dot;
    result.labels.forEach(function (label) {
      if (!label.leader) return;
      ctx.beginPath();
      ctx.arc(label.ax, label.ay, 1.8, 0, Math.PI * 2);
      ctx.fill();
    });

    result.labels.forEach(function (label) {
      var text = String(label.id);
      // A halo rather than a filled box: over a dense wireframe a box hides the mesh
      // the number is about, and over a light face plain text is unreadable.
      ctx.strokeStyle = HALO;
      ctx.lineWidth = 3;
      ctx.strokeText(text, label.x, label.y);
      ctx.fillStyle = style.text;
      ctx.fillText(text, label.x, label.y);
    });
  }

  function paint(plans, ratio) {
    var width = canvas.clientWidth, height = canvas.clientHeight;
    if (!(width > 0 && height > 0)) return;
    canvas.width = Math.floor(width * ratio);
    canvas.height = Math.floor(height * ratio);
    var ctx = canvas.getContext('2d');
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);

    ctx.font = FONT;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.lineJoin = 'round';

    plans.forEach(function (entry) {
      paintLayer(ctx, entry.result, STYLE[entry.kind]);
    });
  }

  /* Called from the render tick with the camera's own projector, so a label cannot
     disagree with where its node or element is drawn. */
  function sync(state) {
    if (!canvas) return null;
    if (!state || !state.active || !anyActive()) { hide(); return null; }
    var width = state.width || host.clientWidth;
    var height = state.height || host.clientHeight;
    if (!(width > 0 && height > 0)) { hide(); return null; }

    // One grid across both kinds: planned in KINDS order, so an element number is never
    // laid over a node number that is already there.
    var taken = {};
    var plans = [];
    KINDS.forEach(function (kind) {
      var it = layers[kind];
      if (!it.on || !it.points.length) { last[kind] = null; return; }
      last[kind] = plan({ groups: it.groups, project: state.project,
                          width: width, height: height,
                          max: state.max, cell: state.cell, taken: taken });
      plans.push({ kind: kind, result: last[kind] });
    });
    if (!plans.length) { hide(); return null; }

    canvas.hidden = false;
    paint(plans, state.ratio || window.devicePixelRatio || 1);
    return plans;
  }

  /* A one-line account of what is on screen, for the command log. Says what was left
     out, because that is the part a reader cannot see. */
  function summary(kind) {
    var noun = kind === 'elements' ? 'Element' : 'Node';
    var result = last[kind];
    if (!result) return 'No ' + noun.toLowerCase() + ' labels on screen.';
    if (!result.hidden) return noun + ' IDs shown for all ' + result.total + ' in view.';
    return noun + ' IDs: ' + result.shown + ' of ' + result.total
         + ' drawn — zoom in to label the rest.';
  }

  App.MeshLabels = {
    KINDS: KINDS,
    groupCoincident: groupCoincident, fanOffsets: fanOffsets, plan: plan,
    nodesFromSections: nodesFromSections, elementsFromSections: elementsFromSections,
    pointsFromTable: pointsFromTable,
    setPoints: setPoints, count: count, layer: layer, reset: reset,
    setActive: setActive, isActive: isActive, anyActive: anyActive,
    menuItem: menuItem,
    install: install, uninstall: uninstall, sync: sync, hide: hide,
    lastPlan: lastPlan, summary: summary,
    MAX_LABELS: MAX_LABELS
  };

})(window.App = window.App || {});
