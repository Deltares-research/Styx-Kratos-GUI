/* The labels' browser half: the row in the viewport's right-click menu (patches.js)
   and the frozen menu renderer it relies on. The planning is test-mesh-labels.js,
   which runs headless as well (frontend/tests/run_headless.py). */

(function () {

  test('mesh labels report the current plan and remove their overlay on uninstall', function () {
    var labels = App.MeshLabels;
    var saved = labels.KINDS.map(function (kind) {
      return { kind: kind, points: labels.layer(kind).points, on: labels.isActive(kind) };
    });
    var host = document.createElement('div');
    host.style.cssText = 'position:fixed;width:200px;height:100px;';
    document.body.appendChild(host);
    try {
      labels.reset();
      T.eq(labels.lastPlan('nodes'), null);
      T.eq(labels.summary('nodes'), 'No node labels on screen.');
      var canvas = labels.install(host);
      canvas.style.cssText = 'width:200px;height:100px;';
      labels.setPoints('nodes', [{ id: 1, x: 0, y: 0, z: 0 },
                                 { id: 2, x: 10, y: 0, z: 0 }]);
      labels.setActive('nodes', true);
      var state = { active: true, width: 200, height: 100, ratio: 1,
                    project: function (x) { return { x: 40 + x * 10, y: 50, depth: 0 }; } };
      labels.sync(state);
      T.eq(labels.lastPlan('nodes').shown, 2);
      T.eq(labels.summary('nodes'), 'Node IDs shown for all 2 in view.');
      labels.sync(Object.assign({}, state, { max: 1 }));
      T.eq(labels.lastPlan('nodes').shown, 1);
      T.ok(/1 of 2/.test(labels.summary('nodes')));
      labels.uninstall();
      T.ok(!host.contains(canvas));
      T.eq(labels.sync(state), null);
      labels.uninstall();
    } finally {
      labels.uninstall();
      labels.reset();
      saved.forEach(function (item) {
        labels.setPoints(item.kind, item.points); labels.setActive(item.kind, item.on);
      });
      host.remove();
    }
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
