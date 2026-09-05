/* Phase-5 overlays: frozen callbacks must report the server's mesh statistics. */

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
      explorerMountTree: App.Explorer && App.Explorer.mountTree
    };
    var lines = [], selected = null;
    App.state = { mode: 'soil' };
    App.setMode = function (mode) { App.state.mode = mode; };
    App.selectObject = function (key) { selected = key; };
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
      if (App.Explorer && saved.explorerMountTree) App.Explorer.mountTree = saved.explorerMountTree;
      App.LivePatches.resetForTests();
    }
  });

  test('layer snapshots are deep and can restore cancelled edits', function () {
    var saved = App.LAYERS;
    App.LAYERS = [{ id: 'L1', tops: { bh1: 0 }, bots: { bh1: -8 } }];
    var snapshot = App.LivePatches.snapshotLayers();
    App.LAYERS[0].bots.bh1 = -12;
    App.LivePatches.restoreLayers(snapshot);
    T.eq(App.LAYERS[0].bots.bh1, -8);
    T.ok(App.LAYERS !== snapshot, 'restore must not reuse the mutable snapshot array');
    App.LAYERS = saved;
  });

  test('pit refinement maps project extents to the mesh API schema', function () {
    var refinement = App.LivePatches.pitRefinement({
      domain: { z_bottom: -25, z_top: 0 },
      excavation: { x0: 12, x1: 38, y0: 10, y1: 30 },
      mesh: { element_size: 2.5 }
    }, 0.5);
    T.eq(refinement, { kind: 'box', size: 1.25, x_min: 12, x_max: 38,
      y_min: 10, y_max: 30, z_min: -25, z_max: 0 });
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

  test('onTreeContextMenu ignores a row that is not a custom part', function () {
    var saved = { project: App.PROJECT, menu: App.Menu };
    App.PROJECT = { custom_parts: [] };
    var openedMenu = false;
    App.Menu = { openAt: function () { openedMenu = true; } };

    var row = document.createElement('div');
    row.className = 'tree-row';
    row.dataset.obj = 'soil_L1';
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
      T.eq(App.LivePatches.objectKind('soil_L1'), null);
      T.eq(App.LivePatches.objectKind(null), null);
    } finally {
      App.PROJECT = saved.project; App.BEAMS = saved.beams;
      App.ANCHORS = saved.anchors; App.LOADS = saved.loads;
    }
  });

  test('renameObject prompts for a name and saves the beam under it', function () {
    var saved = { beams: App.BEAMS, beamsModule: App.Beams, prompt: window.prompt };
    var beam = { id: 'beam_1', name: 'Sheet pile 1' };
    App.BEAMS = [beam];
    window.prompt = function (message, current) {
      T.eq(current, 'Sheet pile 1');
      return '  New name  ';
    };
    var savedWith = null;
    App.Beams = Object.assign({}, App.Beams, {
      save: function (b) { savedWith = b; return Promise.resolve(b); }
    });

    function restore() {
      App.BEAMS = saved.beams; App.Beams = saved.beamsModule; window.prompt = saved.prompt;
    }

    return Promise.resolve(App.LivePatches.renameObject('beam', 'beam_1')).then(function () {
      T.eq(beam.name, 'New name', 'the field is trimmed before it is saved');
      T.eq(savedWith, beam, 'save is called with the renamed object');
    }).then(restore, function (e) { restore(); throw e; });
  });

  test('renameObject does nothing when the prompt is cancelled or blank', function () {
    var saved = { beams: App.BEAMS, beamsModule: App.Beams, prompt: window.prompt };
    var beam = { id: 'beam_1', name: 'Sheet pile 1' };
    App.BEAMS = [beam];
    var saveCalled = false;
    App.Beams = Object.assign({}, App.Beams, {
      save: function () { saveCalled = true; return Promise.resolve(); }
    });

    try {
      window.prompt = function () { return null; };
      App.LivePatches.renameObject('beam', 'beam_1');
      T.eq(beam.name, 'Sheet pile 1', 'a cancelled prompt must not touch the name');

      window.prompt = function () { return '   '; };
      App.LivePatches.renameObject('beam', 'beam_1');
      T.eq(beam.name, 'Sheet pile 1', 'a blank name must not be saved');
      T.eq(saveCalled, false);
    } finally {
      App.BEAMS = saved.beams; App.Beams = saved.beamsModule; window.prompt = saved.prompt;
    }
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

  test('each mode maps to the patch body the server expects', function () {
    T.eq(App.LivePatches.patchFor('2d'), { dimension: 2, section_plane: 'xz' });
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
          return Promise.resolve({ project: { dimension: 2, section_plane: 'xz',
                                              section_offset: 20 } });
        }
      }),
      Viewport: {
        setViewMode: function (m) { order.push('viewport:' + m); },
        refresh: function () { order.push('refresh'); return Promise.resolve(); }
      }
    }), function () {
      return App.runAction({ action: 'viewMode2D' }).then(function () {
        T.eq(patched[0], '/api/project/dimension');
        T.eq(patched[1], { dimension: 2, section_plane: 'xz' });
        T.eq(App.state.modelMode, '2d');
        T.eq(App.state.dimension, 2);
        // The camera must not move before the server has agreed, and the scene must
        // be refetched after it has: the section is cut by OCC, not projected here.
        T.eq(order, ['viewport:elevation', 'refresh']);
        T.eq(App.PROJECT.section_plane, 'xz', 'the patched project has to be adopted');
      });
    });
  });

  test('2D re-cuts when the project is on a different plane than the mode means', function () {
    /* A project can be 2D on a plane this UI no longer offers -- left over from an
       earlier session, or edited through the API. Guarding on the mode id alone
       would make the 2D button a no-op and strand the model on that plane, since
       nothing else in the UI can name it. */
    var sent = [];
    return withStubs(stubs({
      state: { mode: 'soil', modelMode: '2d' },
      PROJECT: { dimension: 2, section_plane: 'xy', section_offset: -12.5 },
      Api: Object.assign({}, App.Api, {
        patch: function (path, body) {
          sent.push(body.section_plane);
          return Promise.resolve({ project: { dimension: 2, section_plane: 'xz' } });
        }
      })
    }), function () {
      return App.LivePatches.setModelMode('2d').then(function () {
        T.eq(sent, ['xz'], 'the button must be able to correct the plane');
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
        App.PROJECT = { dimension: 2, section_plane: 'xz' };
        return App.runAction({ action: 'viewMode2D' }).then(function () {
          T.eq(calls, 0, 'already on this plane too');
        });
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
            return { project: { dimension: 2, section_plane: 'xz' } };
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
  test('the log names the axis the cut travels along, not one in the plane', function () {
    T.eq(App.LivePatches.sectionLabel({ section_plane: 'xz', section_offset: 20 }), 'y = 20');
    T.eq(App.LivePatches.sectionLabel({ section_plane: 'xy', section_offset: -12.5 }), 'z = -12.5');
    T.eq(App.LivePatches.sectionLabel({ section_plane: 'yz', section_offset: 25 }), 'x = 25');
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
