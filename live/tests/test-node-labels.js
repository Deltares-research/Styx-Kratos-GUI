/* Node-ID labels over a displayed mesh.

   Ported in spirit from Kratos-productivity-tools/Node_ViZ, which draws a node's number
   next to it and fans the numbers of *coincident* nodes out around a small circle with
   leader lines -- the case that matters in a Kratos deck, where an interface split
   leaves several nodes sharing one position and a single label would hide the rest.

   The arithmetic is kept apart from the painting for the same reason ruler.js keeps its
   own: where a label goes is the part that can be wrong, and therefore the part that is
   tested. */

(function () {

  /* A projector standing in for the camera: world x, y straight through as pixels,
     z as depth. Lets a test say exactly where a node lands on screen. */
  function flatProjector(width, height) {
    return function (x, y, z) {
      if (z > 100) return null;                  // behind the camera
      return { x: x, y: y, depth: z, width: width, height: height };
    };
  }

  function nodes(list) {
    return list.map(function (n) {
      return { id: n[0], x: n[1], y: n[2], z: n[3] || 0 };
    });
  }

  /* ── Coincident nodes ───────────────────────────────────────────────── */

  test('nodes sharing a position are grouped, and the rest stand alone', function () {
    var groups = App.NodeLabels.groupCoincident(nodes([
      [1, 0, 0], [2, 0, 0], [3, 5, 5]
    ]));
    T.eq(groups.length, 2);
    var shared = groups.filter(function (g) { return g.ids.length > 1; })[0];
    T.eq(shared.ids.join(','), '1,2');
    T.eq(shared.x, 0);
  });

  test('grouping rounds, so floating-point noise does not split a shared node',
       function () {
    var groups = App.NodeLabels.groupCoincident(nodes([
      [1, 1, 2], [2, 1 + 1e-12, 2]
    ]));
    T.eq(groups.length, 1);
    T.eq(groups[0].ids.length, 2);
  });

  test('ids within a group are sorted, so a fan is drawn in reading order', function () {
    var groups = App.NodeLabels.groupCoincident(nodes([[9, 0, 0], [2, 0, 0], [5, 0, 0]]));
    T.eq(groups[0].ids.join(','), '2,5,9');
  });

  /* ── The fan ────────────────────────────────────────────────────────── */

  test('a fan puts every label on the circle and no two in the same place', function () {
    var offsets = App.NodeLabels.fanOffsets(4, 20);
    T.eq(offsets.length, 4);
    offsets.forEach(function (o) {
      T.near(Math.sqrt(o[0] * o[0] + o[1] * o[1]), 20, 1e-6);
    });
    var seen = {};
    offsets.forEach(function (o) { seen[o[0].toFixed(3) + ',' + o[1].toFixed(3)] = 1; });
    T.eq(Object.keys(seen).length, 4);
  });

  /* ── Planning what is drawn ─────────────────────────────────────────── */

  function planOf(list, extra) {
    return App.NodeLabels.plan(Object.assign({
      groups: App.NodeLabels.groupCoincident(nodes(list)),
      project: flatProjector(200, 200),
      width: 200, height: 200
    }, extra || {}));
  }

  test('a lone node is labelled at its own projected point, with no leader', function () {
    var result = planOf([[7, 100, 100]]);
    T.eq(result.labels.length, 1);
    T.eq(result.labels[0].id, 7);
    T.eq(result.labels[0].ax, 100);
    T.eq(result.labels[0].ay, 100);
    T.eq(result.labels[0].leader, false);
  });

  test('nodes off screen or behind the camera are not planned', function () {
    var result = planOf([[1, 100, 100], [2, 900, 100], [3, 100, 100, 500]]);
    T.eq(result.labels.length, 1);
    T.eq(result.labels[0].id, 1);
  });

  test('coincident nodes fan out from the shared point, each with a leader', function () {
    var result = planOf([[1, 100, 100], [2, 100, 100], [3, 100, 100]]);
    T.eq(result.labels.length, 3);
    result.labels.forEach(function (label) {
      T.eq(label.leader, true);
      T.eq(label.ax, 100);
      T.eq(label.ay, 100);
      T.ok(label.x !== 100 || label.y !== 100, 'the label moved off the node');
    });
    var places = result.labels.map(function (l) { return l.x.toFixed(2) + ',' + l.y.toFixed(2); });
    T.eq(new Set(places).size, 3);
  });

  test('labels too close together are dropped, nearest to the camera first', function () {
    // Four nodes inside one declutter cell: only the nearest keeps its label.
    var result = planOf([[1, 100, 100, 9], [2, 101, 100, 5], [3, 102, 101, 7]],
                        { cell: [40, 20] });
    T.eq(result.labels.length, 1);
    T.eq(result.labels[0].id, 2, 'the nearest node wins the cell');
    T.eq(result.hidden, 2);
    T.eq(result.total, 3);
  });

  test('a cap bounds the work, whatever the mesh size', function () {
    var list = [];
    for (var i = 1; i <= 50; i++) list.push([i, i * 4, 10 + (i % 3) * 60]);
    var result = planOf(list, { max: 10, cell: [1, 1] });
    T.eq(result.labels.length, 10);
    T.eq(result.shown, 10);
    T.eq(result.hidden, 40);
  });

  test('a fan is kept whole or dropped whole, never half drawn', function () {
    var result = planOf([[1, 100, 100], [2, 100, 100], [3, 100, 100]], { max: 2 });
    T.eq(result.labels.length, 0, 'three labels do not fit under a cap of two');
    T.eq(result.hidden, 3);
  });

  /* ── Where the nodes come from ──────────────────────────────────────── */

  test('an imported deck\'s sections carry their own Kratos node numbers', function () {
    var list = App.NodeLabels.nodesFromSections([
      { key: 'imported:Soil', node_ids: [4, 9],
        positions: [0, 1, 2, 3, 4, 5] },
      { key: 'imported:Wall', node_ids: [4], positions: [0, 1, 2] }
    ]);
    // Node 4 is one node however many sections draw it.
    T.eq(list.length, 2);
    T.eq(list[0].id, 4);
    T.eq(list[0].y, 1);
    T.eq(list[1].id, 9);
    T.eq(list[1].z, 5);
  });

  test('a generated mesh\'s node table arrives as [id, x, y, z] rows', function () {
    var list = App.NodeLabels.nodesFromTable([[1, 0, 0, 0], [2, 1.5, -2, 0]]);
    T.eq(list.length, 2);
    T.eq(list[1].id, 2);
    T.eq(list[1].x, 1.5);
    T.eq(list[1].y, -2);
  });

  test('a section with no node_ids contributes nothing rather than guessing', function () {
    T.eq(App.NodeLabels.nodesFromSections([{ key: 'old', positions: [0, 0, 0] }]).length, 0);
  });

  /* ── The menu ───────────────────────────────────────────────────────── */

  test('"Show labels" carries a real submenu, with Node IDs in it', function () {
    var item = App.NodeLabels.menuItem();
    T.eq(item.label, 'Show labels');
    T.ok(Array.isArray(item.sub), 'a real submenu, not the frozen placeholder');
    var ids = item.sub.filter(function (s) { return s.action === 'toggleNodeLabels'; });
    T.eq(ids.length, 1);
    T.eq(ids[0].label, 'Node IDs');
  });

  test('the Node IDs row is checked while the labels are on', function () {
    var before = App.NodeLabels.mode();
    App.NodeLabels.setMode('nodes');
    T.eq(App.NodeLabels.menuItem().sub[0].checked, true);
    App.NodeLabels.setMode(null);
    T.eq(App.NodeLabels.menuItem().sub[0].checked, false);
    App.NodeLabels.setMode(before);
  });

  test('the element-ID row is listed but not yet wired', function () {
    var elements = App.NodeLabels.menuItem().sub.filter(function (s) {
      return /Element/i.test(s.label);
    })[0];
    T.ok(elements, 'named, so the menu says what is coming');
    T.eq(elements.disabled, true);
  });

  /* ── The row in the viewport's right-click menu ─────────────────────── */

  test('the labels row is appended to the frozen viewport menu, after a separator',
       function () {
    var frozen = [{ label: 'Zoom to fit' }, { label: 'Show grid' }];
    var items = App.LivePatches.withLabelRows(frozen);
    T.eq(items.length, 4);
    T.eq(frozen.length, 2, 'the frozen list is not mutated');
    T.eq(items[2], '-');
    T.eq(items[3].label, 'Show labels');
  });

  test('the wrapper opens the frozen menu with the extra row, then stands down',
       function () {
    var openAt = App.Menu.openAt;
    var frozenMenu = App.viewportContextMenu;
    var seen = null, picked = null;
    var stub = function (items) { seen = items; };
    try {
      App.Menu.openAt = stub;
      App.viewportContextMenu = function (event, key) {
        App.Menu.openAt([{ label: 'Zoom to fit' }], 0, 0, function (it) { picked = it; });
      };
      App.LivePatches.extendViewportMenu();
      App.viewportContextMenu({}, null);

      T.eq(seen.length, 3, 'the frozen row, a separator and the labels row');
      T.eq(seen[2].label, 'Show labels');
      T.ok(App.Menu.openAt === stub, 'the one-shot openAt put the real one back');
      T.eq(picked, null);
    } finally {
      App.Menu.openAt = openAt;
      App.viewportContextMenu = frozenMenu;
    }
  });

  /* ── The frozen menu renderer, taught real submenus ─────────────────── */

  test('App.Menu.build renders an array submenu as a flyout row', function () {
    var menu = App.Menu.build([{ label: 'Show labels', sub: [{ label: 'Node IDs' }] }],
                              function () {});
    var arrow = menu.querySelector('.mi-sub');
    T.eq(arrow.textContent, '▶');
  });

})();
