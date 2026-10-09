/* ══════════════════════════════════════════════════════════════════
   node-parts.js — which SubModelParts a node is in.

   `/api/mesh/node-parts` sends the deck's node table and, per SubModelPart, the nodes
   it names -- read back off the `.mdpa` the export writes, so the names and numbers are
   exactly Kratos' (server/app/node_parts.py). This module turns that into answers:

       partsOf       the parts one node is in
       samePosition  the nodes at its position -- an interface split leaves two or
                     three, and which part holds which is usually the question
       nearest       the node closest to a point (the right-click, the hover)
       report/hint   what the command log and the status bar say
       parse         `node <id>`

   No DOM and no three.js, so the headless runner executes it
   (live/tests/test-node-parts.js). Fetching, the right-click item, the hover and the
   marker on the mesh are patches.js and viewport.js.
   ══════════════════════════════════════════════════════════════════ */

(function (App) {
  'use strict';

  /* Micrometres at metre scale, as mesh-labels.js groups coincident labels: closer
     than this is the same point, which is what an interface split leaves behind. */
  var DECIMALS = 6;

  function positionKey(xyz) {
    return xyz.map(function (v) { return Number(v).toFixed(DECIMALS); }).join(',');
  }

  function build(payload) {
    var coords = {}, partsOf = {}, at = {}, ids = [], kinds = {};
    (payload.nodes || []).forEach(function (row) {
      var id = row[0], xyz = [row[1], row[2], row[3]];
      ids.push(id);
      coords[id] = xyz;
      partsOf[id] = [];
      var key = positionKey(xyz);
      (at[key] = at[key] || []).push(id);
    });
    (payload.parts || []).forEach(function (part) {
      kinds[part.name] = part.kind;
      part.nodes.forEach(function (id) {
        if (partsOf[id] && partsOf[id].indexOf(part.name) < 0) partsOf[id].push(part.name);
      });
    });
    return { ids: ids, coords: coords, partsOf: partsOf, at: at, kinds: kinds,
             count: ids.length, parts: (payload.parts || []).length };
  }

  /* The parts a node is in, in deck order; `null` for a node the deck does not have. */
  function partsOf(index, id) {
    return index.partsOf[id] ? index.partsOf[id].slice() : null;
  }

  /* Every node at `id`'s position, `id` first and the rest in number order. */
  function samePosition(index, id) {
    var xyz = index.coords[id];
    if (!xyz) return [];
    var others = (index.at[positionKey(xyz)] || []).filter(function (other) {
      return other !== id;
    }).sort(function (a, b) { return a - b; });
    return [id].concat(others);
  }

  /* `{id, distance}` for the node nearest `point`, or null if none is within
     `maxDistance` (when given). Ties -- a split position -- go to the lowest number, so
     the same point always names the same node. */
  function nearest(index, point, maxDistance) {
    var best = null;
    index.ids.forEach(function (id) {
      var c = index.coords[id];
      var dx = c[0] - point.x, dy = c[1] - point.y, dz = c[2] - (point.z || 0);
      var d = Math.sqrt(dx * dx + dy * dy + dz * dz);
      if (best === null || d < best.distance - 1e-12
          || (Math.abs(d - best.distance) <= 1e-12 && id < best.id)) {
        best = { id: id, distance: d };
      }
    });
    if (best && typeof maxDistance === 'number' && best.distance > maxDistance) return null;
    return best;
  }

  /* Where each node can be clicked on screen: `[{id, x, y, ax, ay, fanned}]`.

     `project([x, y, z])` gives the viewport's `{x, y}` in pixels, or null for a point it
     cannot place (behind the camera), which is left out. A node alone at its point is
     a target there. The nodes an interface split left at one point -- the ones still
     shown, `allowed` being `{id: true}` when given -- are fanned around it, Node_ViZ's
     way: `fan(count)` gives each one's pixel offset, in number order (the order the
     node labels fan in, so each dot sits under its own number), and `ax, ay` is the
     point itself, where its leader line starts. The point itself stays a target too,
     for the lowest number there, so clicking right on it still picks something. */
  /* The coordinates of the nearest *other* position to the one keyed `key`: what says
     how much room a fan there has. Found lazily and kept, from the positions sorted by
     x -- a window either side of `key`'s x, narrowed as closer ones turn up -- so a
     large deck is not an all-pairs search. */
  function neighbourOf(index, key) {
    index.neighbour = index.neighbour || {};
    if (key in index.neighbour) return index.neighbour[key];
    if (!index.sorted) {
      index.sorted = Object.keys(index.at).map(function (k) {
        return { key: k, c: index.coords[index.at[k][0]] };
      }).sort(function (a, b) { return a.c[0] - b.c[0]; });
      index.order = {};
      index.sorted.forEach(function (entry, i) { index.order[entry.key] = i; });
    }
    var list = index.sorted, i = index.order[key], c = list[i].c;
    var best = null, bestD = Infinity;
    function look(j) {
      var o = list[j].c;
      if (Math.abs(o[0] - c[0]) >= bestD) return false;
      var d = Math.sqrt((o[0] - c[0]) * (o[0] - c[0]) + (o[1] - c[1]) * (o[1] - c[1])
                        + (o[2] - c[2]) * (o[2] - c[2]));
      if (d < bestD) { bestD = d; best = o; }
      return true;
    }
    for (var up = i + 1; up < list.length && look(up); up++) {}
    for (var down = i - 1; down >= 0 && look(down); down--) {}
    index.neighbour[key] = best;
    return best;
  }

  function screenTargets(index, project, fan, allowed, minGapPx) {
    var out = [];
    Object.keys(index.at).forEach(function (key) {
      var ids = index.at[key].filter(function (id) { return !allowed || allowed[id]; })
        .sort(function (a, b) { return a - b; });
      if (!ids.length) return;
      var p = project(index.coords[ids[0]]);
      if (!p) return;
      // Zoomed out, the next position is too close on screen for a fan to fit: one
      // dot, the lowest number, until the user zooms in.
      var room = true;
      if (ids.length > 1 && fan && minGapPx) {
        var other = neighbourOf(index, key);
        var q = other && project(other);
        room = !q || Math.sqrt((q.x - p.x) * (q.x - p.x) + (q.y - p.y) * (q.y - p.y))
                     >= minGapPx;
      }
      if (ids.length === 1 || !fan || !room) {
        out.push({ id: ids[0], x: p.x, y: p.y, ax: p.x, ay: p.y, fanned: false });
        return;
      }
      var offsets = fan(ids.length);
      ids.forEach(function (id, i) {
        out.push({ id: id, x: p.x + offsets[i][0], y: p.y + offsets[i][1],
                   ax: p.x, ay: p.y, fanned: true });
      });
      out.push({ id: ids[0], x: p.x, y: p.y, ax: p.x, ay: p.y, fanned: false });
    });
    return out;
  }

  /* The node a click at `click` picks: the nearest target (`screenTargets`) within
     `maxPx`, or null -- a click on an element away from any node is not a node pick.
     Ties go to the lowest number. */
  function pickOnScreen(index, project, click, maxPx, allowed, fan, minGapPx) {
    var best = null;
    screenTargets(index, project, fan, allowed, minGapPx).forEach(function (target) {
      var dx = target.x - click.x, dy = target.y - click.y;
      var d = Math.sqrt(dx * dx + dy * dy);
      if (d > maxPx) return;
      if (best === null || d < best.d - 1e-9
          || (Math.abs(d - best.d) <= 1e-9 && target.id < best.id)) {
        best = { id: target.id, d: d };
      }
    });
    return best ? best.id : null;
  }

  /* What the Selection explorer shows for a picked node, in `App.OBJECT_PROPS`' own
     shape (js/explorer.js `mountSelection`): the node and where it is, the parts it is
     in with their kind, and -- where an interface split the position -- every other
     node there with its parts. All read-only: an imported deck is looked at, not
     edited. */
  function selectionProps(index, id) {
    var xyz = index.coords[id];
    var parts = partsOf(index, id) || [];
    var groups = {
      'Node': [['Number', String(id), '', true],
               ['X', Number(xyz[0]).toFixed(3), 'm', true],
               ['Y', Number(xyz[1]).toFixed(3), 'm', true],
               ['Z', Number(xyz[2]).toFixed(3), 'm', true]],
      'SubModelParts': parts.length
        ? parts.map(function (name) { return [name, index.kinds[name] || '', '', true]; })
        : [['(none)', 'in no SubModelPart', '', true]]
    };
    var twins = samePosition(index, id).slice(1);
    if (twins.length) {
      groups['Same position'] = twins.map(function (other) {
        return ['Node ' + other, partList(partsOf(index, other)), '', true];
      });
    }
    return { title: 'Node ' + id, icon: 'vertex', groups: groups };
  }

  function where(xyz) {
    return '(' + xyz.map(function (v) { return Number(v).toFixed(3); }).join(', ') + ')';
  }

  function partList(parts) {
    return parts.length ? parts.join(', ') : 'no SubModelPart';
  }

  /* The lines `node <id>` writes to the command log. */
  function report(index, id) {
    var parts = partsOf(index, id);
    if (parts === null) {
      return ['Node ' + id + ' is not in this deck, which has ' + index.count
              + ' nodes (numbered as the .mdpa is written).'];
    }
    var lines = ['Node ' + id + ' at ' + where(index.coords[id]),
                 '  SubModelParts: ' + partList(parts)];
    var twins = samePosition(index, id).slice(1);
    if (twins.length) {
      lines.push('  Same position (split by an interface):');
      twins.forEach(function (other) {
        lines.push('    node ' + other + ': ' + partList(partsOf(index, other)));
      });
    }
    return lines;
  }

  /* One line for the status bar while the pointer is over a node. The others at its
     point are named, not counted: the number is what the user goes and clicks next. */
  function hint(index, id) {
    var parts = partsOf(index, id) || [];
    var twins = samePosition(index, id).slice(1);
    return 'node ' + id + ' · ' + partList(parts)
         + (twins.length ? ' · also here: ' + twins.map(function (other) {
             return 'node ' + other;
           }).join(', ') : '');
  }

  var USAGE = 'Use `node <id>`, with the number the .mdpa gives the node, e.g. node 89.';

  /* `{id}` for `node <id>`, `{error}` for a malformed one, `false` for another command. */
  function parse(text) {
    var words = String(text || '').trim().split(/\s+/);
    if ((words[0] || '').toLowerCase() !== 'node') return false;
    if (words.length !== 2 || !/^\d+$/.test(words[1])) return { error: USAGE };
    return { id: parseInt(words[1], 10) };
  }

  App.NodeParts = {
    build: build, partsOf: partsOf, samePosition: samePosition, nearest: nearest,
    pickOnScreen: pickOnScreen, screenTargets: screenTargets,
    selectionProps: selectionProps,
    report: report, hint: hint, parse: parse
  };

})(window.App = window.App || {});
