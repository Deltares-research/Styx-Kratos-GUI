/* Node- and element-ID labels over a displayed mesh.

   The node half is ported in spirit from Kratos-productivity-tools/Node_ViZ, which draws
   a node's number next to it and fans the numbers of *coincident* nodes out around a
   small circle with leader lines -- the case that matters in a Kratos deck, where an
   interface split leaves several nodes sharing one position and a single label would
   hide the rest. The element half has no counterpart there: an element's number goes at
   its centroid, which the server computes, and everything after "a number at a point" is
   shared between the two.

   The arithmetic is kept apart from the painting for the same reason ruler.js keeps its
   own: where a label goes is the part that can be wrong, and therefore the part that is
   tested. */

(function () {

  /* A projector standing in for the camera: world x, y straight through as pixels,
     z as depth. Lets a test say exactly where a point lands on screen. */
  function flatProjector(width, height) {
    return function (x, y, z) {
      if (z > 100) return null;                  // behind the camera
      return { x: x, y: y, depth: z, width: width, height: height };
    };
  }

  function points(list) {
    return list.map(function (n) {
      return { id: n[0], x: n[1], y: n[2], z: n[3] || 0 };
    });
  }

  /* ── Coincident points ──────────────────────────────────────────────── */

  test('points sharing a position are grouped, and the rest stand alone', function () {
    var groups = App.MeshLabels.groupCoincident(points([
      [1, 0, 0], [2, 0, 0], [3, 5, 5]
    ]));
    T.eq(groups.length, 2);
    var shared = groups.filter(function (g) { return g.ids.length > 1; })[0];
    T.eq(shared.ids.join(','), '1,2');
    T.eq(shared.x, 0);
  });

  test('grouping rounds, so floating-point noise does not split a shared node',
       function () {
    var groups = App.MeshLabels.groupCoincident(points([
      [1, 1, 2], [2, 1 + 1e-12, 2]
    ]));
    T.eq(groups.length, 1);
    T.eq(groups[0].ids.length, 2);
  });

  test('ids within a group are sorted, so a fan is drawn in reading order', function () {
    var groups = App.MeshLabels.groupCoincident(points([[9, 0, 0], [2, 0, 0], [5, 0, 0]]));
    T.eq(groups[0].ids.join(','), '2,5,9');
  });

  /* ── The fan ────────────────────────────────────────────────────────── */

  test('a fan puts every label on the circle and no two in the same place', function () {
    var offsets = App.MeshLabels.fanOffsets(4, 20);
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
    return App.MeshLabels.plan(Object.assign({
      groups: App.MeshLabels.groupCoincident(points(list)),
      project: flatProjector(200, 200),
      width: 200, height: 200
    }, extra || {}));
  }

  test('a lone point is labelled at its own projected place, with no leader', function () {
    var result = planOf([[7, 100, 100]]);
    T.eq(result.labels.length, 1);
    T.eq(result.labels[0].id, 7);
    T.eq(result.labels[0].ax, 100);
    T.eq(result.labels[0].ay, 100);
    T.eq(result.labels[0].leader, false);
  });

  test('points off screen or behind the camera are not planned', function () {
    var result = planOf([[1, 100, 100], [2, 900, 100], [3, 100, 100, 500]]);
    T.eq(result.labels.length, 1);
    T.eq(result.labels[0].id, 1);
  });

  test('coincident points fan out from the shared place, each with a leader', function () {
    var result = planOf([[1, 100, 100], [2, 100, 100], [3, 100, 100]]);
    T.eq(result.labels.length, 3);
    result.labels.forEach(function (label) {
      T.eq(label.leader, true);
      T.eq(label.ax, 100);
      T.eq(label.ay, 100);
      T.ok(label.x !== 100 || label.y !== 100, 'the label moved off the point');
    });
    var places = result.labels.map(function (l) { return l.x.toFixed(2) + ',' + l.y.toFixed(2); });
    T.eq(new Set(places).size, 3);
  });

  test('labels too close together are dropped, nearest to the camera first', function () {
    // Three points inside one declutter cell: only the nearest keeps its label.
    var result = planOf([[1, 100, 100, 9], [2, 101, 100, 5], [3, 102, 101, 7]],
                        { cell: [40, 20] });
    T.eq(result.labels.length, 1);
    T.eq(result.labels[0].id, 2, 'the nearest point wins the cell');
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

  test('a shared grid keeps a second kind off the first kind\'s cells', function () {
    // The same screen place, planned twice: the element number cannot land on the node
    // number that is already there.
    var taken = {};
    var nodes = planOf([[1, 100, 100]], { taken: taken });
    var elements = planOf([[77, 101, 101]], { taken: taken });
    T.eq(nodes.labels.length, 1);
    T.eq(elements.labels.length, 0);
    T.eq(elements.hidden, 1);
  });

  /* ── Where the numbers come from ────────────────────────────────────── */

  test('an imported deck\'s sections carry their own Kratos node numbers', function () {
    var list = App.MeshLabels.nodesFromSections([
      { key: 'imported:Soil', node_ids: [4, 9], positions: [0, 1, 2, 3, 4, 5] },
      { key: 'imported:Wall', node_ids: [4], positions: [0, 1, 2] }
    ]);
    // Node 4 is one node however many sections draw it.
    T.eq(list.length, 2);
    T.eq(list[0].id, 4);
    T.eq(list[0].y, 1);
    T.eq(list[1].id, 9);
    T.eq(list[1].z, 5);
  });

  test('an imported deck\'s sections carry their elements and where to label them',
       function () {
    var list = App.MeshLabels.elementsFromSections([
      { key: 'imported:Soil', elements: [[11, 1, 2, 3], [12, 4, 5, 6]] },
      { key: 'imported:Wall', elements: [[11, 1, 2, 3]] }
    ]);
    T.eq(list.length, 2);
    T.eq(list[0].id, 11);
    T.eq(list[1].id, 12);
    T.eq(list[1].x, 4);
  });

  test('a generated mesh\'s tables arrive as [id, x, y, z] rows', function () {
    var list = App.MeshLabels.pointsFromTable([[1, 0, 0, 0], [2, 1.5, -2, 0]]);
    T.eq(list.length, 2);
    T.eq(list[1].id, 2);
    T.eq(list[1].x, 1.5);
    T.eq(list[1].y, -2);
  });

  test('a section with no tables contributes nothing rather than guessing', function () {
    var bare = [{ key: 'old', positions: [0, 0, 0] }];
    T.eq(App.MeshLabels.nodesFromSections(bare).length, 0);
    T.eq(App.MeshLabels.elementsFromSections(bare).length, 0);
  });

  /* ── The two kinds are independent ──────────────────────────────────── */

  test('each kind is switched on and off by itself', function () {
    App.MeshLabels.reset();
    T.eq(App.MeshLabels.anyActive(), false);

    App.MeshLabels.setActive('elements', true);
    T.eq(App.MeshLabels.isActive('elements'), true);
    T.eq(App.MeshLabels.isActive('nodes'), false);
    T.eq(App.MeshLabels.anyActive(), true);

    App.MeshLabels.setActive('nodes', true);
    App.MeshLabels.setActive('elements', false);
    T.eq(App.MeshLabels.isActive('nodes'), true);
    T.eq(App.MeshLabels.anyActive(), true);
    App.MeshLabels.reset();
  });

  test('each kind keeps its own points', function () {
    App.MeshLabels.reset();
    App.MeshLabels.setPoints('nodes', App.MeshLabels.pointsFromTable([[1, 0, 0, 0]]));
    App.MeshLabels.setPoints('elements',
                             App.MeshLabels.pointsFromTable([[5, 1, 1, 1], [6, 2, 2, 2]]));
    T.eq(App.MeshLabels.count('nodes'), 1);
    T.eq(App.MeshLabels.count('elements'), 2);
    T.eq(App.MeshLabels.layer('elements').groups.length, 2);
    App.MeshLabels.reset();
  });

  /* ── The menu ───────────────────────────────────────────────────────── */

  test('"Show labels" carries a real submenu, with both kinds in it', function () {
    var item = App.MeshLabels.menuItem();
    T.eq(item.label, 'Show labels');
    T.ok(Array.isArray(item.sub), 'a real submenu, not the frozen placeholder');
    T.eq(item.sub.map(function (s) { return s.action; }).join(','),
         'toggleNodeLabels,toggleElementLabels');
    T.eq(item.sub[0].label, 'Node IDs');
    T.eq(item.sub[1].label, 'Element IDs');
  });

  test('each row is checked while its own labels are on, and neither is disabled',
       function () {
    App.MeshLabels.reset();
    App.MeshLabels.setActive('elements', true);
    var sub = App.MeshLabels.menuItem().sub;
    T.eq(sub[0].checked, false);
    T.eq(sub[1].checked, true);
    T.eq(!!sub[0].disabled, false);
    T.eq(!!sub[1].disabled, false);
    App.MeshLabels.reset();
  });

})();
