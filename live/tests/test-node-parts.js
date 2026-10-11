/* ══════════════════════════════════════════════════════════════════
   test-node-parts.js — which SubModelParts a node is in.

   `App.NodeParts` turns what `/api/mesh/node-parts` sends (the deck's node table, and
   per part the nodes it names) into answers: the parts of one node, the nodes sharing
   its position, the node nearest a point, and the text the command log and the status
   bar show. No DOM, so it runs headless; the right-click item, the hover and the
   marker on the mesh are patches.js and viewport.js.

   The fixture is a sheet-pile wall at (5, -5.75), as the exported deck has it: the pile's
   node 89 and the two soil copies the interface split left beside it.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var N = App.NodeParts;

  function payload() {
    return {
      nodes: [[1, 0, 0, 0], [89, 5, -5.75, 0], [3925, 5, -5.75, 0], [3926, 5, -5.75, 0],
              [4000, 20, -10, 0]],
      parts: [
        { name: 'SheetPileWall', kind: 'body', nodes: [89] },
        { name: 'Soil_Top', kind: 'body', nodes: [1, 3925] },
        { name: 'Soil_Top_lift3', kind: 'body', nodes: [3926] },
        { name: 'Interface_Soil_Top', kind: 'body', nodes: [89, 3925] },
        { name: 'Interface_Soil_Top_lift3', kind: 'body', nodes: [89, 3926] },
        { name: 'WaterLoad_Stage3', kind: 'load', nodes: [89] },
        { name: 'Top_Surface', kind: 'boundary', nodes: [1] }
      ]
    };
  }

  var index = N.build(payload());

  /* ── The parts of a node ─────────────────────────────────────────────── */

  T.test('a node is in every part that names it, in deck order', function () {
    T.eq(N.partsOf(index, 89), ['SheetPileWall', 'Interface_Soil_Top',
                                'Interface_Soil_Top_lift3', 'WaterLoad_Stage3']);
    T.eq(N.partsOf(index, 3926), ['Soil_Top_lift3', 'Interface_Soil_Top_lift3']);
  });

  T.test('a node no part names is in none', function () {
    T.eq(N.partsOf(index, 4000), []);
  });

  T.test('a node the deck does not have is unknown, not partless', function () {
    T.eq(N.partsOf(index, 12345), null);
  });

  /* ── Nodes at the same position ──────────────────────────────────────── */

  T.test('the nodes sharing a position are found, the node itself first', function () {
    T.eq(N.samePosition(index, 3925), [3925, 89, 3926]);
    T.eq(N.samePosition(index, 1), [1]);
  });

  /* ── The nearest node ────────────────────────────────────────────────── */

  T.test('the nearest node to a point is found', function () {
    T.eq(N.nearest(index, { x: 19, y: -9.5, z: 0 }).id, 4000);
  });

  T.test('at a split position the lowest id wins, so a point always names one node',
         function () {
    T.eq(N.nearest(index, { x: 5.01, y: -5.74, z: 0 }).id, 89);
  });

  T.test('nothing is nearest when every node is further than asked', function () {
    T.eq(N.nearest(index, { x: 50, y: -50, z: 0 }, 1), null);
  });

  /* ── What the command log says ───────────────────────────────────────── */

  T.test('the report names the node, where it is, and its parts', function () {
    var lines = N.report(index, 3926);
    T.ok(/Node 3926/.test(lines[0]) && /5\.000/.test(lines[0]) && /-5\.750/.test(lines[0]),
         lines[0]);
    T.ok(lines.some(function (line) {
      return /Soil_Top_lift3/.test(line) && /Interface_Soil_Top_lift3/.test(line);
    }), lines.join('\n'));
  });

  T.test('the report lists every node at the same position, each with its parts',
         function () {
    var text = N.report(index, 89).join('\n');
    T.ok(/3925/.test(text) && /Soil_Top,/.test(text), text);
    T.ok(/3926/.test(text) && /Soil_Top_lift3/.test(text), text);
  });

  T.test('a node in no part says so', function () {
    T.ok(/no SubModelPart/i.test(N.report(index, 4000).join('\n')));
  });

  T.test('an unknown node says so, and how many there are', function () {
    var text = N.report(index, 12345).join('\n');
    T.ok(/12345/.test(text) && /5 nodes/.test(text), text);
  });

  /* ── What the status bar says ────────────────────────────────────────── */

  T.test('the hover hint is one line: the node, its parts, and the others by number',
         function () {
    /* "+2 nodes here" said there were others without saying which: the numbers are
       what lets the user go and click them. */
    var hint = N.hint(index, 89);
    T.ok(/^node 89 · SheetPileWall/.test(hint), hint);
    T.ok(/also here: node 3925, node 3926$/.test(hint), hint);
    T.ok(hint.indexOf('\n') < 0);
  });

  /* ── Clicking a node on the mesh ─────────────────────────────────────────
     Picked on screen, not in the model: the click is a pixel, and "near" is a few
     pixels whatever the zoom, in 2D and 3D alike. The projection is the viewport's;
     here it is a plain scale so the arithmetic can be checked. */

  function scale(xyz) { return { x: xyz[0] * 10, y: -xyz[1] * 10 }; }

  T.test('a click within reach of a node picks it', function () {
    T.eq(N.pickOnScreen(index, scale, { x: 203, y: 98 }, 8), 4000);
  });

  T.test('a click further than the reach from every node picks nothing', function () {
    T.eq(N.pickOnScreen(index, scale, { x: 120, y: 30 }, 8), null);
  });

  T.test('a click on a split position picks the lowest number there', function () {
    T.eq(N.pickOnScreen(index, scale, { x: 51, y: 57 }, 8), 89);
  });

  T.test('only the nodes allowed are picked -- a hidden part is not clickable', function () {
    var allowed = { 1: true, 4000: true };
    T.eq(N.pickOnScreen(index, scale, { x: 51, y: 57 }, 8, allowed), null);
    T.eq(N.pickOnScreen(index, scale, { x: 203, y: 98 }, 8, allowed), 4000);
  });

  T.test('a node the projection cannot place (behind the camera) is skipped', function () {
    function behind(xyz) { return xyz[0] === 20 ? null : scale(xyz); }
    T.eq(N.pickOnScreen(index, behind, { x: 203, y: 98 }, 8), null);
  });

  /* ── Overlapping nodes, fanned apart on screen ──────────────────────────
     Node_ViZ's answer to an interface split: the nodes at one point are drawn around
     it, each on its own short leader line, so each can be clicked. The fan is in
     pixels, from the viewport (`fan(count)` -> [[dx, dy], ...], mesh-labels.js's
     arithmetic); here a fixed one so the positions can be checked. Members are fanned
     in number order, as the node labels are, so a dot sits under its own number. */

  function fan(count) {
    return [[10, 10], [10, -10], [-14, 0]].slice(0, count);
  }

  T.test('each node at a shared point gets its own fanned target', function () {
    var targets = N.screenTargets(index, scale, fan);
    var at = {};
    targets.filter(function (t) { return t.fanned; }).forEach(function (t) { at[t.id] = t; });
    // (5, -5.75) projects to (50, 57.5); 89, 3925, 3926 in number order.
    T.eq([at[89].x, at[89].y], [60, 67.5]);
    T.eq([at[3925].x, at[3925].y], [60, 47.5]);
    T.eq([at[3926].x, at[3926].y], [36, 57.5]);
    T.eq([at[3926].ax, at[3926].ay], [50, 57.5], 'the leader line starts at the point');
  });

  T.test('a fan opens only when zoomed in far enough for it to have room', function () {
    /* Node_ViZ fans in model units, so the fan opens as the user zooms in. Here: the
       split point fans only while its nearest other position is at least `minGapPx`
       away on screen. Node 1 at (0, 0) is its nearest, 7.6 m off -- 76 px at this
       projection's 10 px per metre. */
    function fannedIds(minGapPx) {
      return N.screenTargets(index, scale, fan, null, minGapPx)
        .filter(function (t) { return t.fanned; })
        .map(function (t) { return t.id; });
    }
    T.eq(fannedIds(50), [89, 3925, 3926], 'zoomed in: fanned');
    T.eq(fannedIds(100), [], 'zoomed out: one dot, the lowest number');
    T.eq(N.pickOnScreen(index, scale, { x: 50, y: 57 }, 8, null, fan, 100), 89);
  });

  T.test('a node alone at its point is not fanned', function () {
    var lone = N.screenTargets(index, scale, fan).filter(function (t) { return t.id === 4000; });
    T.eq(lone.length, 1);
    T.ok(!lone[0].fanned);
    T.eq([lone[0].x, lone[0].y], [200, 100]);
  });

  T.test('clicking a fanned dot picks that node, not the lowest one', function () {
    T.eq(N.pickOnScreen(index, scale, { x: 37, y: 58 }, 8, null, fan), 3926);
    T.eq(N.pickOnScreen(index, scale, { x: 60, y: 47 }, 8, null, fan), 3925);
    T.eq(N.pickOnScreen(index, scale, { x: 59, y: 67 }, 8, null, fan), 89);
  });

  T.test('clicking the shared point itself still picks the lowest number', function () {
    T.eq(N.pickOnScreen(index, scale, { x: 50, y: 57 }, 5, null, fan), 89);
  });

  T.test('a hidden node is left out of the fan, and the rest close up', function () {
    var allowed = { 89: true, 3926: true, 1: true, 4000: true };
    var fanned = N.screenTargets(index, scale, fan, allowed)
      .filter(function (t) { return t.fanned; })
      .map(function (t) { return t.id; });
    T.eq(fanned, [89, 3926]);
  });

  T.test('one shown node of a split point is not fanned', function () {
    var targets = N.screenTargets(index, scale, fan, { 3926: true });
    T.eq(targets.length, 1);
    T.ok(!targets[0].fanned);
  });

  /* ── What the Selection explorer shows for a picked node ─────────────── */

  function rows(def, group) { return def.groups[group]; }

  T.test('the node is titled by its number, with its coordinates', function () {
    var def = N.selectionProps(index, 3926);
    T.eq(def.title, 'Node 3926');
    T.eq(rows(def, 'Node'), [['Number', '3926', '', true], ['X', '5.000', 'm', true],
                             ['Y', '-5.750', 'm', true], ['Z', '0.000', 'm', true]]);
  });

  T.test('each SubModelPart the node is in is a row, with its kind', function () {
    T.eq(rows(N.selectionProps(index, 3926), 'SubModelParts'),
         [['Soil_Top_lift3', 'body', '', true],
          ['Interface_Soil_Top_lift3', 'body', '', true]]);
  });

  T.test('a node in no part says so rather than showing an empty group', function () {
    T.eq(rows(N.selectionProps(index, 4000), 'SubModelParts'),
         [['(none)', 'in no SubModelPart', '', true]]);
  });

  T.test('the nodes at the same position are listed with their parts', function () {
    T.eq(rows(N.selectionProps(index, 89), 'Same position'), [
      ['Node 3925', 'Soil_Top, Interface_Soil_Top', '', true],
      ['Node 3926', 'Soil_Top_lift3, Interface_Soil_Top_lift3', '', true]
    ]);
  });

  T.test('a node alone at its position has no "Same position" group', function () {
    T.ok(!('Same position' in N.selectionProps(index, 4000).groups));
  });

  /* ── The command ─────────────────────────────────────────────────────── */

  T.test('`node <id>` asks for that node', function () {
    T.eq(N.parse('node 89'), { id: 89 });
    T.eq(N.parse('  NODE   3925 '), { id: 3925 });
  });

  T.test('anything that is not `node` is not this command', function () {
    T.eq(N.parse('nodes 89'), false);
    T.eq(N.parse('mesh'), false);
  });

  T.test('`node` with no id, or not a whole number, says how to use it', function () {
    ['node', 'node wall', 'node 8.5', 'node -3'].forEach(function (text) {
      var parsed = N.parse(text);
      T.ok(parsed && parsed.error && /node <id>/.test(parsed.error), text);
    });
  });

})();
