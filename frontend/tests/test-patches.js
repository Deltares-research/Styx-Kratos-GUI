/* Stage-5 overlays: frozen callbacks must report the server's mesh statistics. */

(function () {
  test('mesh summaries use computed counts and timing', function () {
    T.eq(
      App.LivePatches.meshSummary({ elements: 82809, nodes: 146321, seconds: 5.125 }),
      'Mesh generated: 82 809 elements, 146 321 nodes (5.1 s).'
    );
  });

  test('generate-mesh actions bypass the frozen hard-coded callback', function () {
    var saved = {
      action: App.runAction, viewport: App.Viewport, command: App.Command,
      state: App.state, setMode: App.setMode, select: App.selectObject,
      explorerMountTree: App.Explorer && App.Explorer.mountTree, menu: App.Menu
    };
    var lines = [], selected = null;
    App.state = { mode: 'soil' };
    App.setMode = function (mode) { App.state.mode = mode; };
    App.selectObject = function (key) { selected = key; };
    // install() remounts the menubar; the test page has no #menubar to mount into.
    App.Menu = { mountBar: function () {}, openAt: function () {} };
    App.Command = {
      write: function (kind, text) { lines.push(kind + ':' + text); },
      ok: function (text) { lines.push('ok:' + text); },
      note: function () {}, run: function () {}
    };
    App.Viewport = {
      generateMesh: function (done) { done({ elements: 12, nodes: 34, seconds: 0.5 }); }
    };
    App.runAction = function () { throw new Error('frozen action should not run'); };

    try {
      App.LivePatches.install();
      App.runAction({ action: 'generateMesh' });
      T.eq(App.state.mode, 'mesh');
      T.eq(selected, 'mesh');
      T.ok(lines.indexOf('ok:Mesh generated: 12 elements, 34 nodes (0.5 s).') >= 0);
    } finally {
      App.runAction = saved.action; App.Viewport = saved.viewport; App.Command = saved.command;
      App.state = saved.state; App.setMode = saved.setMode; App.selectObject = saved.select;
      App.Menu = saved.menu;
      if (App.Explorer && saved.explorerMountTree) App.Explorer.mountTree = saved.explorerMountTree;
      App.LivePatches.resetForTests();
    }
  });

  test('clear mesh drops the mesh and its statistics, and says when there is none', function () {
    var saved = {
      action: App.runAction, viewport: App.Viewport, command: App.Command,
      state: App.state, setMode: App.setMode, select: App.selectObject,
      menu: App.Menu, model: App.Model
    };
    var lines = [], selected = 'mesh', meshed = true, statsCleared = 0;
    App.state = { mode: 'mesh', selection: 'mesh' };
    App.setMode = function (mode) { App.state.mode = mode; };
    App.selectObject = function (key) { selected = key; App.state.selection = key; };
    App.Menu = { mountBar: function () {}, openAt: function () {} };
    App.Command = {
      write: function (kind, text) { lines.push(kind + ':' + text); },
      ok: function (text) { lines.push('ok:' + text); },
      note: function (text) { lines.push('note:' + text); }, run: function () {}
    };
    App.Viewport = {
      clearMesh: function () { var had = meshed; meshed = false; return had; },
      hasMesh: function () { return meshed; }
    };
    App.Model = { clearMeshStats: function () { statsCleared += 1; } };
    App.runAction = function () { throw new Error('frozen action should not run'); };

    try {
      App.LivePatches.install();
      App.runAction({ action: 'clearMesh' });
      T.eq(meshed, false);
      T.eq(statsCleared, 1, 'the Mesh statistics read "—" again');
      T.eq(selected, null, 'the cleared mesh is no longer selected');
      T.ok(/^ok:Mesh cleared/.test(lines[lines.length - 1]), lines.join(' | '));
      App.runAction({ action: 'clearMesh' });
      T.eq(lines[lines.length - 1], 'note:There is no mesh to clear.');
      T.eq(statsCleared, 1);
      var menu = (App.MENUS || []).filter(function (m) { return m.label === 'Mesh'; })[0];
      var labels = menu.items.map(function (i) { return i && i.label; });
      T.eq(labels[labels.indexOf('Generate mesh…') + 1], 'Clear mesh',
           'Clear mesh sits under Generate mesh');
      T.ok((App.RAILS.mesh || []).some(function (tool) {
        return tool && tool.action === 'clearMesh';
      }), 'the Mesh rail has the tool');
    } finally {
      App.runAction = saved.action; App.Viewport = saved.viewport; App.Command = saved.command;
      App.state = saved.state; App.setMode = saved.setMode; App.selectObject = saved.select;
      App.Menu = saved.menu; App.Model = saved.model;
      App.LivePatches.resetForTests();
    }
  });

  test('layer snapshots are deep and can restore cancelled edits', function () {
    var saved = App.LAYERS;
    App.LAYERS = [{ id: 'L1', top: 0, bottom: -8 }];
    var snapshot = App.LivePatches.snapshotLayers();
    App.LAYERS[0].bottom = -12;
    App.LivePatches.restoreLayers(snapshot);
    T.eq(App.LAYERS[0].bottom, -8);
    T.ok(App.LAYERS !== snapshot, 'restore must not reuse the mutable snapshot array');
    App.LAYERS = saved;
  });

  /* ── Model explorer: Delete for drawn/imported geometry ──────────

     js/explorer.js:91 hard-codes Delete disabled on every tree row -- the frozen
     mockup never had anything real to delete. These prove the live override enables
     it for custom parts only, and that clicking it actually removes the part. */

  test('isDeletableCustomPart only accepts a key the project actually has', function () {
    var saved = App.PROJECT;
    App.PROJECT = { custom_parts: [{ key: 'drawn_0' }, { key: 'imported_0' }] };
    try {
      T.eq(App.LivePatches.isDeletableCustomPart('drawn_0'), true);
      T.eq(App.LivePatches.isDeletableCustomPart('imported_0'), true);
      T.eq(App.LivePatches.isDeletableCustomPart('soil_L1'), false, 'soil is not a custom part');
      T.eq(App.LivePatches.isDeletableCustomPart(null), false);
    } finally {
      App.PROJECT = saved;
    }
  });

  test('tagTreeRowsWithObjKeys correctly tags rows from the real rendered tree', function () {
    // The unit test below proves the pairing logic against a synthetic tree; this one
    // renders through the actual js/explorer.js so a real structural mismatch (not just
    // a hypothetical one) would be caught.
    var savedState = App.state, savedSoilTree = App.TREES.soil;
    App.state = { mode: 'soil', selection: null };
    App.TREES.soil = [
      { obj: 'soil', label: 'Soil', children: [{ obj: 'soil_L1', label: 'Soil_1' }] },
      { label: 'Custom geometry', children: [{ obj: 'drawn_0', label: 'Box_1' }] }
    ];

    var host = document.createElement('div');
    host.id = 'tree-model';
    document.body.appendChild(host);

    try {
      App.Explorer.mountTree('soil');
      App.LivePatches.tagTreeRowsWithObjKeys('soil');

      var rows = host.querySelectorAll('.tree-row');
      var tagged = Array.prototype.map.call(rows, function (r) {
        return r.querySelector('.tree-label').textContent + '=' + (r.dataset.obj || '');
      });
      T.eq(tagged, ['Soil=soil', 'Soil_1=soil_L1', 'Custom geometry=', 'Box_1=drawn_0'], tagged.join(' | '));
    } finally {
      document.body.removeChild(host);
      App.state = savedState;
      App.TREES.soil = savedSoilTree;
    }
  });

  test('tagTreeRowsWithObjKeys stamps rows with their tree node key, in document order', function () {
    // explorer.js builds one DOM row per App.TREES[mode] node, depth-first: a parent
    // row, then each child row, before the next sibling -- the only order this can rely on.
    var savedTrees = App.TREES;
    var host = document.createElement('div');
    host.id = 'tree-model';
    host.innerHTML =
      '<div class="tree-row" id="r0"></div>' +
      '<div class="tree-row" id="r1"></div>' +
      '<div class="tree-row" id="r1a"></div>';
    document.body.appendChild(host);
    App.TREES = { soil: [
      { obj: 'soil' },
      { obj: 'customGeometry', children: [{ obj: 'drawn_0' }] }
    ] };

    try {
      App.LivePatches.tagTreeRowsWithObjKeys('soil');
      T.eq(document.getElementById('r0').dataset.obj, 'soil');
      T.eq(document.getElementById('r1').dataset.obj, 'customGeometry');
      T.eq(document.getElementById('r1a').dataset.obj, 'drawn_0');
    } finally {
      document.body.removeChild(host);
      App.TREES = savedTrees;
    }
  });

  test('onTreeContextMenu ignores a row that is no live object', function () {
    var saved = { project: App.PROJECT, menu: App.Menu };
    App.PROJECT = { custom_parts: [] };
    var openedMenu = false;
    App.Menu = { openAt: function () { openedMenu = true; } };

    var row = document.createElement('div');
    row.className = 'tree-row';
    row.dataset.obj = 'soil_no_such_layer';
    var prevented = false;
    var event = {
      target: row,
      preventDefault: function () { prevented = true; },
      stopImmediatePropagation: function () {}
    };

    try {
      App.LivePatches.onTreeContextMenu(event);
      T.eq(prevented, false, 'a normal tree row must fall through to the frozen menu');
      T.eq(openedMenu, false);
    } finally {
      App.PROJECT = saved.project;
      App.Menu = saved.menu;
    }
  });

  test('onTreeContextMenu opens an enabled Delete for a custom part, and it deletes', function () {
    var saved = {
      project: App.PROJECT, menu: App.Menu, viewport: App.Viewport, api: App.Api,
      model: App.Model, state: App.state, explorer: App.Explorer, command: App.Command,
      selectObject: App.selectObject, fetch: window.fetch
    };

    App.PROJECT = { custom_parts: [{ key: 'drawn_0' }] };
    App.Api = { base: '' };
    App.Viewport = { isVisible: function () { return true; }, refresh: function () { return Promise.resolve(); } };
    App.Model = { load: function () { return Promise.resolve(); } };
    App.state = { mode: 'structures', selection: 'drawn_0' };
    var mountedMode = null;
    App.Explorer = { mountTree: function (mode) { mountedMode = mode; } };
    var selected = 'unset';
    App.selectObject = function (key) { selected = key; };
    var lines = [];
    App.Command = {
      note: function (t) { lines.push('note:' + t); },
      ok: function (t) { lines.push('ok:' + t); },
      err: function (t) { lines.push('err:' + t); }
    };

    var capturedItems = null, capturedPick = null;
    App.Menu = { openAt: function (items, x, y, onPick) { capturedItems = items; capturedPick = onPick; } };

    var deleteCall = null;
    window.fetch = function (url, options) {
      deleteCall = { url: url, method: options.method };
      return Promise.resolve({ ok: true, json: function () { return Promise.resolve({ ok: true }); } });
    };

    var row = document.createElement('div');
    row.className = 'tree-row';
    row.dataset.obj = 'drawn_0';
    var prevented = false, stopped = false;
    var event = {
      target: row, clientX: 10, clientY: 20,
      preventDefault: function () { prevented = true; },
      stopImmediatePropagation: function () { stopped = true; }
    };

    function restore() {
      App.PROJECT = saved.project; App.Menu = saved.menu; App.Viewport = saved.viewport;
      App.Api = saved.api; App.Model = saved.model; App.state = saved.state;
      App.Explorer = saved.explorer; App.Command = saved.command; App.selectObject = saved.selectObject;
      window.fetch = saved.fetch;
    }

    App.LivePatches.onTreeContextMenu(event);
    T.ok(prevented, 'the frozen row menu must not also open');
    T.ok(stopped);
    T.ok(capturedItems, 'a menu was opened');
    var del = capturedItems.filter(function (it) { return it && it.label === 'Delete'; })[0];
    T.ok(del, 'menu has a Delete item');
    T.eq(!!del.disabled, false, 'Delete must be enabled for a custom part');

    return Promise.resolve(capturedPick(del)).then(function () {
      T.ok(deleteCall, 'Delete must call the API');
      T.eq(deleteCall.method, 'DELETE');
      T.eq(deleteCall.url, '/api/geometry/parts/drawn_0');
      T.eq(selected, null, 'the deleted object must be deselected');
      T.eq(mountedMode, 'structures', 'the tree must refresh after delete');
      T.ok(lines.some(function (l) { return /^ok:Deleted drawn_0/.test(l); }), lines.join(' | '));
    }).then(restore, function (err) { restore(); throw err; });
  });

  /* ── Model explorer: Rename/Delete for beams, anchors and loads ──────────

     js/explorer.js:89-98 only ever wires up Rename/Delete for a soil layer --
     every other live-owned tree row (a sheet pile or wall, an anchor, a load)
     showed both disabled. These prove the same context menu now works for them,
     routed through each module's own save/remove rather than a bespoke path. */

  test('objectKind names the module that owns a key, or null for anything else', function () {
    var saved = { project: App.PROJECT, beams: App.BEAMS, anchors: App.ANCHORS, loads: App.LOADS };
    App.PROJECT = { custom_parts: [{ key: 'drawn_0' }] };
    App.BEAMS = [{ id: 'beam_1', kind: 'beam' }];
    App.ANCHORS = [{ id: 'anchor_1', kind: 'anchor' }];
    App.LOADS = [{ id: 'point_1', kind: 'point' }];
    try {
      T.eq(App.LivePatches.objectKind('drawn_0'), 'part');
      T.eq(App.LivePatches.objectKind('beam_1'), 'beam');
      T.eq(App.LivePatches.objectKind('anchor_1'), 'anchor');
      T.eq(App.LivePatches.objectKind('point_1'), 'load');
      // A soil layer is live too: its Rename must not fall to the frozen prompt.
      T.eq(App.LivePatches.objectKind('soil_' + App.LAYERS[0].id), 'layer');
      T.eq(App.LivePatches.objectKind('soil_no_such_layer'), null);
      T.eq(App.LivePatches.objectKind(null), null);
    } finally {
      App.PROJECT = saved.project; App.BEAMS = saved.beams;
      App.ANCHORS = saved.anchors; App.LOADS = saved.loads;
    }
  });

  test('renameObject asks for a name in the Rename window and saves the beam under it', function () {
    var saved = { beams: App.BEAMS, beamsModule: App.Beams, ask: App.NameDialog };
    var beam = { id: 'beam_1', name: 'Sheet pile 1' };
    App.BEAMS = [beam];
    App.NameDialog = { ask: function (options) {
      T.eq(options.value, 'Sheet pile 1');
      T.eq(options.title, 'Rename');
      return Promise.resolve('New name');
    } };
    var savedWith = null;
    App.Beams = Object.assign({}, App.Beams, {
      save: function (b) { savedWith = b; return Promise.resolve(b); }
    });

    function restore() {
      App.BEAMS = saved.beams; App.Beams = saved.beamsModule; App.NameDialog = saved.ask;
    }

    return Promise.resolve(App.LivePatches.renameObject('beam', 'beam_1')).then(function () {
      T.eq(beam.name, 'New name');
      T.eq(savedWith, beam, 'save is called with the renamed object');
    }).then(restore, function (e) { restore(); throw e; });
  });

  test('renameObject saves an anchor, an interface, a normal load and a load through their own modules', function () {
    var saved = { anchors: App.ANCHORS, interfaces: App.INTERFACES,
                  normalLoads: App.NORMAL_LOADS, loads: App.LOADS,
                  anchorsModule: App.Anchors, interfacesModule: App.Interfaces,
                  normalLoadsModule: App.NormalLoads, loadsModule: App.Loads,
                  ask: App.NameDialog };
    var objects = {
      anchor: { id: 'anchor_1', name: 'Anchor 1' },
      interface: { id: 'interface_1', name: 'Interface 1' },
      normal_load: { id: 'normal_1', name: 'Normal load 1' },
      load: { id: 'point_1', name: 'Point load 1' }
    };
    App.ANCHORS = [objects.anchor];
    App.INTERFACES = [objects.interface];
    App.NORMAL_LOADS = [objects.normal_load];
    App.LOADS = [objects.load];
    var savedWith = {};
    function saver(kind) {
      return { save: function (item) { savedWith[kind] = item; return Promise.resolve(item); } };
    }
    App.Anchors = Object.assign({}, App.Anchors, saver('anchor'));
    App.Interfaces = Object.assign({}, App.Interfaces, saver('interface'));
    App.NormalLoads = Object.assign({}, App.NormalLoads, saver('normal_load'));
    App.Loads = Object.assign({}, App.Loads, saver('load'));
    var offered = [];
    App.NameDialog = { ask: function (options) {
      offered.push(options.value);
      return Promise.resolve('Renamed ' + options.value);
    } };

    function restore() {
      App.ANCHORS = saved.anchors; App.INTERFACES = saved.interfaces;
      App.NORMAL_LOADS = saved.normalLoads; App.LOADS = saved.loads;
      App.Anchors = saved.anchorsModule; App.Interfaces = saved.interfacesModule;
      App.NormalLoads = saved.normalLoadsModule; App.Loads = saved.loadsModule;
      App.NameDialog = saved.ask;
    }

    var kinds = Object.keys(objects);
    return Promise.all(kinds.map(function (kind) {
      return Promise.resolve(App.LivePatches.renameObject(kind, objects[kind].id));
    })).then(function () {
      T.eq(offered, ['Anchor 1', 'Interface 1', 'Normal load 1', 'Point load 1'],
           'the Rename window offers each object\'s current name');
      kinds.forEach(function (kind) {
        T.eq(savedWith[kind], objects[kind], kind + ' is saved through its own module');
        T.ok(/^Renamed /.test(objects[kind].name), kind + ' carries the new name');
      });
    }).then(restore, function (e) { restore(); throw e; });
  });

  test('renameObject does nothing when the Rename window is cancelled', function () {
    var saved = { beams: App.BEAMS, beamsModule: App.Beams, ask: App.NameDialog };
    var beam = { id: 'beam_1', name: 'Sheet pile 1' };
    App.BEAMS = [beam];
    var saveCalled = false;
    App.Beams = Object.assign({}, App.Beams, {
      save: function () { saveCalled = true; return Promise.resolve(); }
    });

    // A blank name never leaves the window: see the Rename window's own test.
    App.NameDialog = { ask: function () { return Promise.resolve(null); } };
    function restore() {
      App.BEAMS = saved.beams; App.Beams = saved.beamsModule; App.NameDialog = saved.ask;
    }
    return App.LivePatches.renameObject('beam', 'beam_1').then(function () {
      T.eq(beam.name, 'Sheet pile 1', 'a cancelled rename must not touch the name');
      T.eq(saveCalled, false);
    }).then(restore, function (e) { restore(); throw e; });
  });

  test('onTreeContextMenu opens a working Rename and Delete for an anchor, and Delete removes it', function () {
    var saved = { project: App.PROJECT, anchors: App.ANCHORS, menu: App.Menu,
                  viewport: App.Viewport, anchorsModule: App.Anchors };
    var anchor = { id: 'anchor_1', name: 'Anchor 1' };
    App.PROJECT = { custom_parts: [] };
    App.ANCHORS = [anchor];
    App.Viewport = { isVisible: function () { return true; } };
    var removedId = null;
    App.Anchors = Object.assign({}, App.Anchors, {
      remove: function (id) { removedId = id; return Promise.resolve(true); }
    });

    var capturedItems = null, capturedPick = null;
    App.Menu = { openAt: function (items, x, y, onPick) { capturedItems = items; capturedPick = onPick; } };

    var row = document.createElement('div');
    row.className = 'tree-row';
    row.dataset.obj = 'anchor_1';
    var prevented = false, stopped = false;
    var event = {
      target: row, clientX: 0, clientY: 0,
      preventDefault: function () { prevented = true; },
      stopImmediatePropagation: function () { stopped = true; }
    };

    function restore() {
      App.PROJECT = saved.project; App.ANCHORS = saved.anchors; App.Menu = saved.menu;
      App.Viewport = saved.viewport; App.Anchors = saved.anchorsModule;
    }

    App.LivePatches.onTreeContextMenu(event);
    T.ok(prevented && stopped, 'the frozen row menu must not also open');
    var rename = capturedItems.filter(function (it) { return it.label === 'Rename…'; })[0];
    var del = capturedItems.filter(function (it) { return it.label === 'Delete'; })[0];
    T.eq(!!rename.disabled, false, 'Rename must be enabled for an anchor');
    T.eq(!!del.disabled, false, 'Delete must be enabled for an anchor');

    return Promise.resolve(capturedPick(del)).then(function () {
      T.eq(removedId, 'anchor_1');
    }).then(restore, function (err) { restore(); throw err; });
  });
})();

/* ── Step 1 of 2D mode: the toggle that reaches the frozen UI ──
   js/ is served as the same bytes from file:// and from the server, so the 2D
   switch is injected here rather than added to js/data.js. */

(function () {
  /* 2D and 3D are modes, not views: a view moves the camera, whereas this changes
     what the model *is* -- the server cuts a planar section and meshes that instead
     of the solid. So they live in the toolbar as a labelled pair, not under View. */

  test('there are exactly two modes, labelled and ordered 2D then 3D', function () {
    var modes = App.LivePatches.MODES;
    T.eq(modes.map(function (m) { return m.id; }), ['2d', '3d']);
    T.eq(modes.map(function (m) { return m.label; }), ['2D', '3D']);
    modes.forEach(function (m) {
      T.ok(App.ICONS[m.icon], m.id + ' needs an icon that exists in App.ICONS');
    });
  });

  test('the sheet pile tool and its flyout have a glyph of their own', function () {
    var tool = (App.RAILS.structures || []).filter(function (item) {
      return item && item.action === 'createSheetPile';
    })[0];
    T.ok(tool, 'the sheet pile tool exists');
    [tool].concat(tool.flyout || []).forEach(function (item) {
      T.ok(App.ICONS[item.icon], (item.label || item.tip) + ' needs an icon in App.ICONS');
    });
    T.ok(App.ICONS.wall !== App.ICONS.info, 'not the info glyph');
  });

  test('the sheet pile and anchor icons share the faded ground line', function () {
    var ground = '<path d="M2 15h8.5M10.5 8.5H22" opacity=".32"/>';
    T.ok(App.ICONS.wall.indexOf(ground) >= 0, 'the sheet pile icon has the ground');
    T.ok(App.ICONS.anchor.indexOf(ground) >= 0, 'the anchor icon has the ground');
    T.ok(App.ICONS.wall !== App.ICONS.anchor, 'and each draws its own part over it');
  });

  test('each mode maps to the patch body the server expects', function () {
    T.eq(App.LivePatches.patchFor('2d'), { dimension: 2 });
    T.eq(App.LivePatches.patchFor('3d'), { dimension: 3 });
  });

  test('both modes are toolbar buttons carrying their own label', function () {
    ['viewMode2D', 'viewMode3D'].forEach(function (action) {
      var hits = App.TOOLBAR.filter(function (t) { return t && t.action === action; });
      T.eq(hits.length, 1, action + ': install() must be idempotent across reloads');
      // `wide` is what js/toolbars.js renders as text beside the icon. Without it
      // the pair is two unlabelled cubes.
      T.ok(hits[0].wide, action + ' needs a visible label');
    });
    var two = App.TOOLBAR.findIndex(function (t) { return t && t.action === 'viewMode2D'; });
    var three = App.TOOLBAR.findIndex(function (t) { return t && t.action === 'viewMode3D'; });
    T.ok(two < three, '2D comes before 3D');
    T.eq(App.TOOLBAR[two - 1], '|', 'the pair is its own group, not part of the view tools');
  });

  test('File > Export model… is no longer inert', function () {
    /* js/data.js:99 ships the item with no `action`, so the frozen App.runAction
       only logs that it is not implemented. patches.js gives it one, and the
       wrapper routes it to the exporter. */
    var ran = 0;
    return withStubs(stubs({ Export: { run: function () { ran++; } } }), function () {
      var file = App.MENUS.filter(function (m) { return m.label === 'File'; })[0];
      var item = file.items.filter(function (i) {
        return i && i.label === 'Export model…';
      })[0];
      T.eq(item.action, 'exportModel');

      App.runAction(item);
      T.eq(ran, 1, 'the menu item reaches the exporter');
    });
  });

  test('the View menu no longer offers them', function () {
    var view = App.MENUS.filter(function (m) { return m.label === 'View'; })[0];
    T.eq(view.items.filter(function (i) {
      return i && /^viewMode/.test(i.action || '');
    }), []);
    T.eq(view.items.filter(function (i) { return i && i.action === 'setViewMode'; }), []);
  });

  /* These are async: the switch is not local, it goes to the server and back. So
     the stubs have to be restored when the promise settles, not when the test
     function returns -- a `finally` around the `return` runs immediately and pulls
     App.Command out from under the continuation. */
  function withStubs(stubs, body) {
    var keys = Object.keys(stubs), saved = {};
    keys.forEach(function (k) { saved[k] = App[k]; App[k] = stubs[k]; });
    function restore() {
      keys.forEach(function (k) { App[k] = saved[k]; });
      App.LivePatches.resetForTests();
    }
    App.LivePatches.resetForTests();
    App.LivePatches.install();
    return Promise.resolve().then(body).then(
      function (v) { restore(); return v; },
      function (e) { restore(); throw e; }
    );
  }

  function stubs(extra) {
    return Object.assign({
      state: { mode: 'soil', modelMode: '3d' },
      Command: { write: function () {}, ok: function () {}, run: function () {},
                 note: function () {}, err: function () {} },
      Toolbars: { setToolbarState: function () {} },
      Viewport: { setViewMode: function () {}, refresh: function () { return Promise.resolve(); } },
      // The switch adopts the server's answer through App.Model.apply (so Undo can take
      // it back); these answers are two-field stand-ins, not projects a model can build.
      Model: { apply: function (project) { App.PROJECT = project; },
               load: function () { return Promise.resolve(); } },
      runAction: function () { throw new Error('frozen action should not run'); },
      PROJECT: null
    }, extra);
  }

  test('the toolbar button sends the mode to the server before redrawing', function () {
    var patched = null, order = [];
    return withStubs(stubs({
      Api: Object.assign({}, App.Api, {
        patch: function (path, body) {
          patched = [path, body];
          return Promise.resolve({ project: { dimension: 2, section_offset: 20 } });
        }
      }),
      Viewport: {
        setViewMode: function (m) { order.push('viewport:' + m); },
        refresh: function () { order.push('refresh'); return Promise.resolve(); }
      }
    }), function () {
      return App.runAction({ action: 'viewMode2D' }).then(function () {
        T.eq(patched[0], '/api/project/dimension');
        T.eq(patched[1], { dimension: 2 });
        T.eq(App.state.modelMode, '2d');
        T.eq(App.state.dimension, 2);
        // The camera must not move before the server has agreed, and the scene must
        // be refetched after it has: the section is cut by OCC, not projected here.
        T.eq(order, ['viewport:elevation', 'refresh']);
        T.eq(App.PROJECT.section_offset, 20, 'the patched project has to be adopted');
      });
    });
  });

  test('choosing the mode you are already in does not rebuild anything', function () {
    var calls = 0;
    return withStubs(stubs({
      Api: Object.assign({}, App.Api, {
        patch: function () { calls++; return Promise.resolve({ project: {} }); }
      })
    }), function () {
      return App.runAction({ action: 'viewMode3D' }).then(function () {
        T.eq(calls, 0, 'a section rebuild is expensive; do not spend one on a no-op');
        App.state.modelMode = '2d';
        App.PROJECT = { dimension: 2, section_offset: 20 };
        return App.runAction({ action: 'viewMode2D' }).then(function () {
          T.eq(calls, 0, 'already in the section too');
        });
      });
    });
  });

  /* The server opens on a plane-strain document, so the app does too. A switch that
     only agreed with that after /api/geometry answered would show the 3D toolbar,
     rail and camera for the second it took -- and then take them away again. */
  test('the app opens in 2D, so 2D is the no-op and 3D is the switch that costs',
       function () {
    var calls = 0;
    T.eq(App.LivePatches.DEFAULT_MODEL_MODE, '2d');
    return withStubs(stubs({
      state: { mode: 'soil' },          // nothing has said a dimension yet
      Api: Object.assign({}, App.Api, {
        patch: function (path, body) {
          calls++;
          return Promise.resolve({ project: { dimension: body.dimension } });
        }
      })
    }), function () {
      T.eq(App.state.modelMode, '2d', 'install() opens the document in the section');
      T.eq(App.state.dimension, 2);
      return App.LivePatches.setModelMode('2d').then(function () {
        T.eq(calls, 0, 'the project is already the section the server opened on');
        return App.LivePatches.setModelMode('3d');
      }).then(function () {
        T.eq(calls, 1, 'leaving the section is the switch that costs a rebuild');
        T.eq(App.state.modelMode, '3d');
      });
    });
  });

  test('a second switch is ignored while the first is still in flight', function () {
    var calls = 0, release;
    var pending = new Promise(function (resolve) { release = resolve; });
    return withStubs(stubs({
      Api: Object.assign({}, App.Api, {
        patch: function () {
          calls++;
          return pending.then(function () {
            return { project: { dimension: 2 } };
          });
        }
      })
    }), function () {
      var first = App.LivePatches.setModelMode('2d');
      var second = App.LivePatches.setModelMode('2d');
      release();
      return Promise.all([first, second]).then(function () {
        T.eq(calls, 1, 'double-clicking must not rebuild the model twice');
      });
    });
  });

  test('a refused switch leaves the mode where it was', function () {
    var errors = [], moved = false;
    return withStubs(stubs({
      Command: { write: function () {}, ok: function () {}, run: function () {},
                 note: function () {}, err: function (t) { errors.push(t); } },
      Api: Object.assign({}, App.Api, {
        patch: function () { return Promise.reject(new Error('section_offset: out of range')); }
      }),
      Viewport: { setViewMode: function () { moved = true; }, refresh: function () {} }
    }), function () {
      return App.LivePatches.setModelMode('2d').then(function () {
        T.eq(App.state.modelMode, '3d', 'the state must follow the server, not lead it');
        T.eq(moved, false, 'nothing should move for a switch that did not happen');
        T.ok(/out of range/.test(errors.join(' ')), 'the reason belongs in the command log');
      });
    });
  });

  test('only the active mode button is lit, and 2D disables the view cube', function () {
    var lit = {};
    var host = document.createElement('div');
    host.innerHTML = '<div id="vp-viewcube"><button data-view="iso"></button></div>';
    document.body.appendChild(host);
    var savedToolbars = App.Toolbars;
    App.Toolbars = { setToolbarState: function (a, on) { lit[a] = on; } };
    try {
      App.LivePatches.syncModelMode('2d');
      // Not an exact-object check: the same pass also repaints the navigation and
      // projection buttons, which 2D takes out of the user's hands.
      T.eq([lit.viewMode2D, lit.viewMode3D], [true, false]);
      // Front/top/side/iso all resolve to the section once the camera is locked.
      T.eq(host.querySelector('#vp-viewcube').classList.contains('off'), true);
      T.eq(host.querySelector('#vp-viewcube button').disabled, true);

      App.LivePatches.syncModelMode('3d');
      T.eq([lit.viewMode2D, lit.viewMode3D], [false, true]);
      T.eq(host.querySelector('#vp-viewcube').classList.contains('off'), false);
      T.eq(host.querySelector('#vp-viewcube button').disabled, false);
    } finally {
      App.Toolbars = savedToolbars;
      host.remove();
    }
  });

  test('syncing the mode also records it, so the buttons and the switch agree', function () {
    /* App.Viewport.refresh() adopts the project's dimension on load. If that only
       updated the toolbar's paint and not the state setModelMode() guards on, a
       project that loads in 2D would leave the switch believing it is in 3D. */
    var saved = { state: App.state, toolbars: App.Toolbars };
    App.state = {};
    App.Toolbars = { setToolbarState: function () {} };
    try {
      App.LivePatches.syncModelMode('2d');
      T.eq(App.state.modelMode, '2d');
      App.LivePatches.syncViewMode('solid');
      T.eq(App.state.modelMode, '3d');
    } finally {
      App.state = saved.state; App.Toolbars = saved.toolbars;
    }
  });

  /* Silent failure is what made this expensive to diagnose: a blank viewport, a
     command log that just stops, and the reason only in DevTools. */

  test('a stale viewport.js is named, not left to look like a model bug', function () {
    T.eq(App.LivePatches.missingViewportApi(App.Viewport), [],
         'the shipped pair must be compatible with each other');
    var stale = { refresh: function () {} };      // an old build, before the rename
    var missing = App.LivePatches.missingViewportApi(stale);
    T.ok(missing.indexOf('setViewMode') >= 0);
    T.ok(missing.length >= 2);
  });

  test('the staleness report tells the user what to actually do', function () {
    var text = App.LivePatches.staleMessage(['setViewMode', 'orthoHalfHeight']);
    T.ok(/viewport\.js/.test(text), 'name the file');
    T.ok(/setViewMode/.test(text), 'name what is missing');
    T.ok(/Ctrl\+Shift\+R/i.test(text), 'name the fix');
  });

  test('an uncaught error reaches the command log instead of only DevTools', function () {
    var saved = App.Command;
    var errors = [];
    App.Command = { write: function () {}, ok: function () {}, note: function () {},
                    run: function () {}, err: function (t) { errors.push(t); } };
    try {
      App.LivePatches.reportUncaught({ message: 'x is not a function',
                                       filename: '/live/js/viewport.js', lineno: 42 });
      T.eq(errors.length, 1);
      T.ok(/x is not a function/.test(errors[0]));
      T.ok(/viewport\.js:42/.test(errors[0]), 'where it happened matters most');
    } finally {
      App.Command = saved;
    }
  });

  test('a rejected promise with no handler is reported too', function () {
    var saved = App.Command;
    var errors = [];
    App.Command = { write: function () {}, ok: function () {}, note: function () {},
                    run: function () {}, err: function (t) { errors.push(t); } };
    try {
      App.LivePatches.reportUncaught({ reason: new Error('Failed to fetch') });
      T.ok(/Failed to fetch/.test(errors[0]));
    } finally {
      App.Command = saved;
    }
  });

  test('the viewport reports its plane-based mode and the toolbar still follows', function () {
    var lit = {};
    var savedToolbars = App.Toolbars;
    App.Toolbars = { setToolbarState: function (a, on) { lit[a] = on; } };
    try {
      // App.Viewport.refresh() speaks in section planes; the toolbar speaks in modes.
      App.LivePatches.syncViewMode('elevation');
      T.eq(lit.viewMode2D, true);
      App.LivePatches.syncViewMode('solid');
      T.eq(lit.viewMode3D, true);
    } finally {
      App.Toolbars = savedToolbars;
    }
  });
})();

(function () {
  test('the log names the axis the cut travels along, which is always z', function () {
    T.eq(App.LivePatches.sectionLabel({ section_offset: 20 }), 'z = 20');
    T.eq(App.LivePatches.sectionLabel({ section_offset: -12.5 }), 'z = -12.5');
    T.eq(App.LivePatches.sectionLabel({}), 'z = ?');
  });
})();

/* The rail button and the Soil menu are the two doors into the soil-body dialog.
   In 2D that dialog makes a surface, so the doors must not still promise a volume. */
(function () {
  test('the entry points are renamed with the mode', function () {
    // Restored afterwards: these are the arrays every other test reads, and a stub
    // left in App.MENUS is invisible here and baffling three files later.
    var saved = { menus: App.MENUS, rails: App.RAILS };
    App.RAILS = { soil: [{ icon: 'cube', tip: 'Create soil volume…', action: 'createSoilVolume' }] };
    App.MENUS = [{ label: 'Soil', items: [
      { label: 'Create soil volume…', icon: 'cube', action: 'createSoilVolume' }] }];

    try {
      App.LivePatches.nameSoilBodyActions('2d');
      T.eq(App.RAILS.soil[0].tip, 'Create soil surface…');
      T.eq(App.MENUS[0].items[0].label, 'Create soil surface…');

      App.LivePatches.nameSoilBodyActions('3d');
      T.eq(App.RAILS.soil[0].tip, 'Create soil volume…');
      T.eq(App.MENUS[0].items[0].label, 'Create soil volume…');
    } finally {
      App.MENUS = saved.menus; App.RAILS = saved.rails;
    }
  });
})();

(function () {
  /* There is no menu item for an example model, and that is the point. Models are
     opened by running the Python that builds them -- `run models/pit.py` in the
     command box, covered below -- which works for any model rather than only the one somebody
     thought to add a button for. A menu item for it existed and was removed; this is
     what stops it coming back. */

  test('no example model is loadable from the File menu', function () {
    App.LivePatches.install();
    var file = (App.MENUS || []).filter(function (m) { return m.label === 'File'; })[0];
    var items = file.items || [];
    T.ok(!items.some(function (i) { return i && /example/i.test(i.label || ''); }),
      'the File menu offers no example model');
    T.ok(!items.some(function (i) { return i && /Example$/.test(i.action || ''); }),
      'nor any other one-click example model');
  });
})();

(function () {
  /* The command line's `run <file.py>`: the scripting entry point. */

  function harness(overrides) {
    var saved = {
      api: App.Api, viewport: App.Viewport, command: App.Command, state: App.state,
      setMode: App.setMode, select: App.selectObject, model: App.Model,
      history: App.History, project: App.PROJECT, action: App.runAction,
      explorer: App.Explorer, resultsView: App.ResultsView, menu: App.Menu
    };
    var ctx = { posted: [], lines: [], meshed: 0, applied: null, frozen: [], saved: saved };
    App.state = { mode: 'soil' };
    App.setMode = function (m) { App.state.mode = m; };
    App.selectObject = function () {};
    App.runAction = function () {};
    // The frozen interpreter the live one wraps; a `run` it does not own falls through here.
    App.Command = {
      write: function () {}, ok: function (t) { ctx.lines.push('ok:' + t); },
      note: function () {}, err: function (t) { ctx.lines.push('err:' + t); },
      run: function (t) { ctx.frozen.push(t); }
    };
    App.Api = { post: function (path, body) {
      ctx.posted.push({ path: path, body: body });
      return (overrides && overrides.post) ? overrides.post(path, body)
        : Promise.resolve({ project: { name: 'scripted', mesh: {} } });
    } };
    App.Model = { apply: function (p) { ctx.applied = p; }, setImportedParts: function () {} };
    App.History = { install: function () {}, reset: function () {},
                    canUndo: function () { return false; }, canRedo: function () { return false; } };
    // Adopting a project remounts the tree and clears results; neither has a host here.
    App.Explorer = { mountTree: function () {} };
    App.ResultsView = { clear: function () {} };
    App.Menu = { mountBar: function () {}, openAt: function () {} };
    App.Viewport = {
      refresh: function () { return Promise.resolve(); },
      generateMesh: function (done) { ctx.meshed += 1; done({ elements: 1, nodes: 1, seconds: 0 }); }
    };
    App.LivePatches.resetForTests();
    App.LivePatches.install();
    return ctx;
  }

  function restore(ctx) {
    var s = ctx.saved;
    App.Api = s.api; App.Viewport = s.viewport; App.Command = s.command;
    App.state = s.state; App.setMode = s.setMode; App.selectObject = s.select;
    App.Model = s.model; App.History = s.history; App.PROJECT = s.project;
    App.runAction = s.action;
    App.Explorer = s.explorer; App.ResultsView = s.resultsView; App.Menu = s.menu;
    App.LivePatches.resetForTests();
  }

  test('run <file.py> builds the model from a script and meshes it', function () {
    var ctx = harness();
    return Promise.resolve(App.Command.run('run models/pit.py')).then(function () {
      T.eq(ctx.posted[0].path, '/api/project/script');
      T.eq(ctx.posted[0].body.path, 'models/pit.py');
      T.ok(ctx.applied && ctx.applied.name === 'scripted', 'the project is adopted');
      T.eq(ctx.meshed, 1, 'and meshed without a second command');
    }).then(function () { restore(ctx); }, function (e) { restore(ctx); throw e; });
  });

  test('run keeps a path with spaces in it intact', function () {
    var ctx = harness();
    return Promise.resolve(App.Command.run('run C:/my models/pit.py')).then(function () {
      T.eq(ctx.posted[0].body.path, 'C:/my models/pit.py');
    }).then(function () { restore(ctx); }, function (e) { restore(ctx); throw e; });
  });

  test('run with no path explains itself instead of posting', function () {
    var ctx = harness();
    return Promise.resolve(App.Command.run('run')).then(function () {
      T.eq(ctx.posted.length, 0);
      T.ok(ctx.lines.some(function (l) { return /Usage: run/.test(l); }), 'says how');
    }).then(function () { restore(ctx); }, function (e) { restore(ctx); throw e; });
  });

  test("a script error is shown as the server's own message", function () {
    var ctx = harness({ post: function () {
      return Promise.reject(new Error("model.py needs the Python package 'STEM'"));
    } });
    return Promise.resolve(App.Command.run('run model.py')).then(function () {
      T.ok(ctx.lines.some(function (l) { return /needs the Python package/.test(l); }),
           'the reason reaches the log');
      T.eq(ctx.meshed, 0, 'and nothing is meshed');
    }).then(function () { restore(ctx); }, function (e) { restore(ctx); throw e; });
  });

  /* `cleargeometry` is refused while a stage still uses one of the parts (finding F3).
     It used to report "cleared" whatever the server said. */
  function refusingFetch(detail) {
    var saved = window.fetch;
    window.fetch = function () {
      return Promise.resolve({ ok: false, status: 422,
        json: function () { return Promise.resolve({ detail: detail }); } });
    };
    return function () { window.fetch = saved; };
  }

  test("cleargeometry refused by the server says why, and not that it cleared", function () {
    var ctx = harness();
    var loaded = 0;
    App.Model.load = function () { loaded += 1; return Promise.resolve(); };
    var unfetch = refusingFetch("cannot delete a part that a stage still uses (stage 'dig_1' names drawn_0)");
    return Promise.resolve(App.Command.run('cleargeometry')).then(function () {
      T.ok(ctx.lines.some(function (l) { return /^err:.*dig_1/.test(l); }), ctx.lines.join(' | '));
      T.ok(!ctx.lines.some(function (l) { return /^ok:/.test(l); }), 'no success line');
      T.eq(loaded, 0, 'the model is not reloaded for a refusal');
    }).then(function () { unfetch(); restore(ctx); },
            function (e) { unfetch(); restore(ctx); throw e; });
  });

  /* The command panel's own words. The mockup's welcome, `help`, command reference,
     model history and canned answers described a demo that no longer exists. */
  function textOf(lines) {
    return lines.map(function (line) { return line[0] + ':' + line[1]; }).join('\n');
  }

  test('help lists the real commands and calls none of them a demo', function () {
    var ctx = harness();
    try {
      var help = textOf(App.CMD_RESPONSES.help);
      ['run <file.py>', 'calculate', 'units', 'stages', 'export', 'water', 'results']
        .forEach(function (word) { T.ok(help.indexOf(word) >= 0, 'help names ' + word + ':\n' + help); });
      T.ok(!/demo|mockup/i.test(help), help);
    } finally { restore(ctx); }
  });

  test('the welcome and the model history say nothing the project does not hold', function () {
    var ctx = harness();
    try {
      var welcome = textOf(App.CMD_WELCOME);
      T.ok(!/mockup|demo/i.test(welcome), welcome);
      T.ok(!/boreholes|soil layers|×/.test(welcome), 'no fixed model geometry:\n' + welcome);
      T.eq(App.CMD_HISTORY, [], 'no invented commands in the Model history tab');
    } finally { restore(ctx); }
  });

  test('a placeholder command builds nothing and does not say it did', function () {
    var ctx = harness();
    try {
      ['soillayer', 'plate', 'beam', 'anchor', 'surface', 'line', 'point'].forEach(function (word) {
        var answer = textOf(App.CMD_RESPONSES[word]);
        T.ok(!/^ok:/m.test(answer), word + ' claims success: ' + answer);
        T.ok(!/_\d+\b/.test(answer), word + ' names an object that does not exist: ' + answer);
      });
    } finally { restore(ctx); }
  });

  test('calculate in the command box runs the calculation', function () {
    var ctx = harness();
    var saved = App.Calculate, ran = 0;
    App.Calculate = { run: function () { ran += 1; return Promise.resolve(); } };
    return Promise.resolve(App.Command.run('calculate')).then(function () {
      T.eq(ran, 1);
      T.eq(ctx.frozen, [], 'not the mockup answer "no solver is attached"');
    }).then(function () { App.Calculate = saved; restore(ctx); },
            function (e) { App.Calculate = saved; restore(ctx); throw e; });
  });

  test('an unknown command points to help, not to a demo list', function () {
    var ctx = harness();
    return Promise.resolve(App.Command.run('frobnicate 3')).then(function () {
      T.eq(ctx.frozen, [], 'the mockup interpreter does not answer it');
      T.ok(ctx.lines.some(function (l) {
        return /^err:Unknown command "frobnicate"/.test(l) && /help/.test(l) && !/demo/.test(l);
      }), ctx.lines.join(' | '));
    }).then(function () { restore(ctx); }, function (e) { restore(ctx); throw e; });
  });

  test('a command the mockup interpreter owns still reaches it', function () {
    var ctx = harness();
    return Promise.resolve(App.Command.run('zoomfit')).then(function () {
      T.eq(ctx.frozen, ['zoomfit']);
    }).then(function () { restore(ctx); }, function (e) { restore(ctx); throw e; });
  });

  test('a menu item with no action says it is not available yet', function () {
    var ctx = harness();
    var notes = [];
    App.Command.note = function (text) { notes.push(text); };
    try {
      App.runAction({ label: 'Print…' });
      T.eq(notes, ['"Print…" is not available in Styx yet.']);
    } finally { restore(ctx); }
  });

  test('the command reference lists the commands help lists', function () {
    var ctx = harness();
    var layer = document.getElementById('modal-layer');
    var made = !layer;
    if (made) {
      layer = document.createElement('div');
      layer.id = 'modal-layer';
      document.body.appendChild(layer);
    }
    try {
      App.Dialogs.commandReference();
      var text = layer.textContent;
      ['calculate', 'results', 'units', 'run <file.py>'].forEach(function (word) {
        T.ok(text.indexOf(word) >= 0, 'the reference names ' + word + ': ' + text);
      });
      T.ok(!/demo|mockup|would list/i.test(text), text);
    } finally {
      App.UI.clear(layer);
      if (made) layer.remove();
      restore(ctx);
    }
  });
})();
