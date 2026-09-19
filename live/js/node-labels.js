/* ══════════════════════════════════════════════════════════════════
   node-labels.js — the node number, drawn next to the node.

   Ported from D:/MyTools/Kratos-productivity-tools/Node_ViZ, which exists because a
   .mdpa is read by node number: a solver message names node 4711, and the only way to
   find it is to see the number on the mesh. Node_ViZ does that with a Plotly text trace
   per node plus, for nodes that share a position, a fan of labels around a small circle
   with leader lines back to the point. Both ideas are kept; the surroundings differ.

   Three things had to change coming into this app:

   *   The mesh is a three.js scene, not a 2D Plotly figure, so a node's screen place is
       the camera's answer and changes every frame. The labels are therefore painted on
       an overlay canvas from the render tick -- the same arrangement ruler.js already
       uses, and for the same reason: a hundred absolutely-positioned elements per frame
       is not a thing to do inside requestAnimationFrame.
   *   A real mesh has far more nodes than a screen has room for. Node_ViZ answers that
       with a checkbox ("show all labels"); here the answer is a screen-space declutter
       grid plus a hard cap, so turning labels on is never a way to freeze the tab. The
       nearest node to the camera wins its cell, and what was dropped is counted so the
       caller can say "showing 800 of 41 000 — zoom in for more".
   *   The numbers are Kratos node IDs, from the only two places that know them: an
       imported deck's own node table, and -- for a mesh this app generated -- the
       export numbering, which is a gmsh tag renumbered 1..N *after* the interface split
       (see server/app/kratos.py). A gmsh tag would be a different, wrong number.

   The arithmetic (groupCoincident, fanOffsets, plan) is deliberately separate from the
   painting: where a label goes is the part that can be wrong, so it is the part that is
   tested. See live/tests/test-node-labels.js.
   ══════════════════════════════════════════════════════════════════ */

(function (App) {
  'use strict';

  var DECIMALS = 6;
  /* Micrometres at metre scale. Two nodes this close are the same point -- which is
     exactly what an interface split leaves behind -- and one label would hide the other. */

  var FAN_RADIUS = 24;          // px from the shared point to each fanned label
  var FAN_START = -60;          // degrees, Node_ViZ's own opening angle
  var FAN_SPREAD = 240;         // degrees the fan is spread over
  var CELL = [46, 18];          // declutter grid, px: roughly one label's box
  var MAX_LABELS = 1500;        // beyond this the screen is a grey smudge anyway
  var MARGIN = 24;              // px outside the viewport a label may still be planned

  var FONT = '11px Consolas, monospace';
  var TEXT = '#f2f6ff';
  var HALO = 'rgba(16, 22, 32, 0.85)';
  var LEADER = 'rgba(210, 222, 240, 0.55)';
  var DOT = 'rgba(255, 213, 79, 0.95)';

  /* ── Where the numbers come from ────────────────────────────── */

  /* An imported deck's sections: each carries its own slice of the file's node table
     (server/app/mdpa_import.py `_section_dict`), one id per position triple. A node two
     sections both draw is one node, so ids are de-duplicated across the whole list. */
  function nodesFromSections(sections) {
    var seen = {}, out = [];
    (sections || []).forEach(function (section) {
      var ids = section && section.node_ids;
      var positions = section && section.positions;
      if (!ids || !positions) return;            // an older payload: say nothing rather than guess
      for (var i = 0; i < ids.length; i++) {
        var id = ids[i];
        if (seen[id]) continue;
        seen[id] = true;
        out.push({ id: id, x: positions[3 * i], y: positions[3 * i + 1],
                   z: positions[3 * i + 2] });
      }
    });
    return out;
  }

  /* A generated mesh's table, as POST /api/mesh/nodes returns it: [id, x, y, z] rows in
     the deck's own numbering. */
  function nodesFromTable(rows) {
    return (rows || []).map(function (row) {
      return { id: row[0], x: row[1], y: row[2], z: row[3] };
    });
  }

  /* ── Coincident nodes ───────────────────────────────────────── */

  function groupCoincident(nodes, decimals) {
    var places = decimals === undefined ? DECIMALS : decimals;
    var byPlace = {}, groups = [];
    (nodes || []).forEach(function (node) {
      var key = node.x.toFixed(places) + '|' + node.y.toFixed(places) + '|'
              + node.z.toFixed(places);
      var group = byPlace[key];
      if (!group) {
        group = byPlace[key] = { x: node.x, y: node.y, z: node.z, ids: [] };
        groups.push(group);
      }
      group.ids.push(node.id);
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

    var total = 0;
    var placed = [];
    groups.forEach(function (group) {
      total += group.ids.length;
      var p = project(group.x, group.y, group.z);
      if (!p) return;
      if (p.x < -MARGIN || p.y < -MARGIN || p.x > width + MARGIN || p.y > height + MARGIN) return;
      placed.push({ group: group, p: p });
    });

    // Nearest first, so the node in front is the one that keeps its number where two
    // compete for the same patch of screen.
    placed.sort(function (a, b) { return a.p.depth - b.p.depth; });

    var taken = {}, labels = [];
    for (var i = 0; i < placed.length; i++) {
      var group = placed[i].group, p = placed[i].p;
      var key = Math.floor(p.x / cell[0]) + ':' + Math.floor(p.y / cell[1]);
      if (taken[key]) continue;
      // Whole or not at all: half a fan reads as a node with fewer nodes on it than it
      // has, which is the one thing these labels exist to show.
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
             total: total };
  }

  /* ── State ──────────────────────────────────────────────────── */

  var mode = null;               // null | 'nodes'  ('elements' is next; see menuItem)
  var nodes = [];
  var groups = [];
  var last = null;               // the last plan, for the status line

  function setNodes(list) {
    nodes = list || [];
    groups = groupCoincident(nodes);
    last = null;
  }

  function setMode(next) { mode = next || null; }
  function currentMode() { return mode; }
  function count() { return nodes.length; }
  function lastPlan() { return last; }

  /* ── The menu ───────────────────────────────────────────────── */

  /* The viewport's right-click menu row. Element IDs are named and disabled rather than
     left out: the shape of the submenu is the promise that they are coming, and a menu
     that grows a row later is harder to learn than one that was always there. */
  function menuItem() {
    return {
      label: 'Show labels', icon: 'vertex',
      sub: [
        { label: 'Node IDs', action: 'toggleNodeLabels', checked: mode === 'nodes' },
        { label: 'Element IDs', disabled: true }
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
    canvas.className = 'vp-node-labels';
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
    last = null;
  }

  function paint(result, ratio) {
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

    // The leaders first, so a number is never drawn under a line pointing at it.
    ctx.strokeStyle = LEADER;
    ctx.lineWidth = 1;
    ctx.beginPath();
    result.labels.forEach(function (label) {
      if (!label.leader) return;
      ctx.moveTo(label.ax, label.ay);
      ctx.lineTo(label.x, label.y);
    });
    ctx.stroke();

    // One dot per shared point: the fan says "these numbers", the dot says "are here".
    ctx.fillStyle = DOT;
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
      ctx.fillStyle = TEXT;
      ctx.fillText(text, label.x, label.y);
    });
  }

  /* Called from the render tick with the camera's own projector, so a label cannot
     disagree with where its node is drawn. */
  function sync(state) {
    if (!canvas) return null;
    if (!mode || !state || !state.active || !nodes.length) { hide(); return null; }
    var width = state.width || host.clientWidth;
    var height = state.height || host.clientHeight;
    if (!(width > 0 && height > 0)) { hide(); return null; }

    last = plan({ groups: groups, project: state.project, width: width, height: height,
                  max: state.max, cell: state.cell });
    canvas.hidden = false;
    paint(last, state.ratio || window.devicePixelRatio || 1);
    return last;
  }

  /* A one-line account of what is on screen, for the command log. Says what was left
     out, because that is the part a reader cannot see. */
  function summary(result) {
    var r = result || last;
    if (!r) return 'No node labels on screen.';
    if (!r.hidden) return 'Node IDs shown for all ' + r.total + ' nodes in view.';
    return 'Node IDs: ' + r.shown + ' of ' + r.total
         + ' drawn — zoom in to label the rest.';
  }

  App.NodeLabels = {
    groupCoincident: groupCoincident, fanOffsets: fanOffsets, plan: plan,
    nodesFromSections: nodesFromSections, nodesFromTable: nodesFromTable,
    setNodes: setNodes, count: count,
    setMode: setMode, mode: currentMode, menuItem: menuItem,
    install: install, uninstall: uninstall, sync: sync, hide: hide,
    lastPlan: lastPlan, summary: summary,
    MAX_LABELS: MAX_LABELS
  };

})(window.App = window.App || {});
