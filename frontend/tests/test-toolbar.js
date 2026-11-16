/* Toolbar wiring: every button does something, and the 3D-only ones stop being
   available once the model is a plane-strain section. */

(function () {

  /* The test page loads no js/app.js, so there is no frozen App.runAction for the
     overlay to wrap. This gives it one, installs, and puts everything back. */
  function withInstall(body) {
    var saved = { action: App.runAction, command: App.Command };
    var notes = [];
    App.runAction = function (item) { notes.push('frozen:' + (item && item.action)); };
    App.Command = { note: function (t) { notes.push(t); }, ok: function (t) { notes.push(t); },
                    err: function (t) { notes.push(t); }, write: function () {}, run: function () {} };
    App.LivePatches.install();
    try { return body(notes); }
    finally {
      App.runAction = saved.action; App.Command = saved.command;
      App.LivePatches.resetForTests();
    }
  }

  /* ── Every button is wired ─────────────────────────────────────── */

  test('every main toolbar button carries an action', function () {
    withInstall(function () {});
    var dead = App.TOOLBAR.filter(function (t) { return t !== '|' && !t.action; })
                          .map(function (t) { return t.tip; });
    T.eq(dead, [], 'toolbar buttons without an action do nothing when clicked');
  });

  test('File and Edit menu items that mirror toolbar buttons carry the same actions', function () {
    withInstall(function () {});
    function action(menuLabel, itemLabel) {
      var menu = App.MENUS.filter(function (m) { return m.label === menuLabel; })[0];
      var item = menu.items.filter(function (i) { return i.label === itemLabel; })[0];
      return item && item.action;
    }
    T.eq(action('File', 'New project…'), 'newProject');
    T.eq(action('File', 'Open project…'), 'openProject');
    T.eq(action('File', 'Save'), 'saveProject');
    T.eq(action('Edit', 'Undo'), 'undo');
    T.eq(action('Edit', 'Redo'), 'redo');
  });

  /* ── 2D gating ─────────────────────────────────────────────────── */

  test('the 3D-only actions are what a 2D section cannot serve', function () {
    /* The camera ones a locked section view cannot do, plus the objects a plane has
       no room for. A sheet pile is not among them: that tool makes the wall of
       whichever dimension is open. */
    T.eq(App.LivePatches.THREE_D_ONLY.slice().sort(), [
      'createMember', 'drawBox', 'drawCylinder', 'navRotate', 'toggleProjection',
      'viewFront', 'viewIso', 'viewSide', 'viewTop'
    ]);
    T.eq(App.LivePatches.availableIn2D('zoomFit'), true);
    T.eq(App.LivePatches.availableIn2D('viewIso'), false);
    T.eq(App.LivePatches.availableIn2D('createMember'), false);
    T.eq(App.LivePatches.availableIn2D('createSheetPile'), true);
    T.eq(App.LivePatches.availableIn2D('createAnchor'), true);
  });

  test('the 2D-only actions are what the solid model cannot serve', function () {
    /* An interface is a zero-thickness contact along a line in the section. Every
       reference deck that has one is plane strain, and the 3D element is a surface
       with a different node layout and no fixture to pin it -- so the tool is closed
       in 3D rather than writing something nobody has checked. */
    /* A normal load is plane strain for the same reason: the condition it writes
       is a line one (see NORMAL_LOAD_CONDITIONS in core/kratos/writer.py). */
    /* And the rulers, which measure the two named axes of one section plane: in 3D
       the screen edges are three axes mixed by the orbit. See test-ruler.js. */
    /* And a boundary condition drawn along a line or at a point, which the section
       embeds as a normal load's line is. */
    T.eq(App.LivePatches.TWO_D_ONLY,
         ['interface', 'createNormalLoad', 'drawLine', 'createLineByCoordinates',
          'toggleRuler', 'createSupportLine',
          'createSupportPoint', 'createWaterPressureLine', 'createWaterPressurePoint',
          'createSeepageLine']);
    T.eq(App.LivePatches.availableIn3D('interface'), false);
    T.eq(App.LivePatches.availableIn3D('createNormalLoad'), false);
    T.eq(App.LivePatches.availableIn3D('createSheetPile'), true);
    T.eq(App.LivePatches.availableIn2D('interface'), true);
    T.eq(App.LivePatches.availableIn2D('createNormalLoad'), true);
  });

  test('the frozen interface button and menu item are given a live action', function () {
    withInstall(function () {});
    var tool = (App.RAILS.structures || []).filter(function (t) {
      return t && t.icon === 'interface' && t.tip;
    })[0];
    T.ok(tool, 'the rail still has its interface button');
    T.eq(tool.action, 'interface');

    var menu = App.MENUS.filter(function (m) { return m.label === 'Structures'; })[0];
    var items = (menu.items || []).filter(function (i) {
      return i && i.label === 'Create interface';
    });
    T.eq(items.length, 1, 'one Create interface entry, not the frozen one plus a twin');
    T.eq(items[0].action, 'interface');
  });

  test('a 2D-only action asked for in 3D is refused with a reason, not silently run', function () {
    var contacts = App.Interfaces;
    App.state = App.state || {};
    var wasMode = App.state.modelMode;
    var started = 0;
    App.Interfaces = { start: function () { started += 1; } };
    App.state.modelMode = '3d';
    try {
      withInstall(function (notes) {
        App.runAction({ action: 'interface', tip: 'Create interface' });
        T.eq(started, 0, 'the solid model has no plane-strain contact to make');
        T.ok(notes.some(function (n) { return /plane-strain/.test(n); }),
             'and the log says why: ' + notes.join(' | '));
      });
    } finally { App.Interfaces = contacts; App.state.modelMode = wasMode; }
  });

  test('the interface tool reaches App.Interfaces rather than the frozen action', function () {
    var saved = App.Interfaces;
    App.state = App.state || {};
    var wasMode = App.state.modelMode;
    var started = 0;
    App.Interfaces = { start: function () { started += 1; } };
    // The tool is 2D-only; pinned so a mode left behind by an earlier test cannot refuse it.
    App.state.modelMode = '2d';
    try {
      withInstall(function (notes) {
        App.runAction({ action: 'interface' });
        T.eq(started, 1);
        T.eq(notes.filter(function (n) { return n === 'frozen:interface'; }), []);
      });
    } finally { App.Interfaces = saved; App.state.modelMode = wasMode; }
  });

  test('switching to 2D disables the 3D-only toolbar buttons and re-enables them in 3D', function () {
    // The page's own toolbar host, as the app has exactly one; a second #maintoolbar would never be found.
    var bar = document.getElementById('maintoolbar');
    var created = !bar;
    if (created) {
      bar = document.createElement('div');
      bar.id = 'maintoolbar';
      document.body.appendChild(bar);
    }
    var previous = Array.prototype.slice.call(bar.childNodes);
    bar.textContent = '';
    ['viewIso', 'navRotate', 'toggleProjection', 'zoomFit'].forEach(function (action) {
      var b = document.createElement('button');
      b.className = 'tbtn';
      b.dataset.action = action;
      bar.appendChild(b);
    });
    function btn(action) { return bar.querySelector('[data-action="' + action + '"]'); }

    try {
      App.LivePatches.syncDimensionAvailability(true);
      T.ok(btn('viewIso').classList.contains('disabled'), 'isometric view is 3D only');
      T.ok(btn('viewIso').disabled, 'and refuses the click, not just the styling');
      T.ok(btn('navRotate').classList.contains('disabled'), 'orbiting a section does nothing');
      T.ok(btn('toggleProjection').classList.contains('disabled'), '2D is always orthographic');
      T.ok(!btn('zoomFit').classList.contains('disabled'), 'zoom is not a 3D feature');

      App.LivePatches.syncDimensionAvailability(false);
      T.ok(!btn('viewIso').classList.contains('disabled'), 'back in 3D the presets return');
      T.ok(!btn('viewIso').disabled);
    } finally {
      if (created) bar.remove();
      else { bar.textContent = ''; previous.forEach(function (n) { bar.appendChild(n); }); }
    }
  });

  test('2D greys out the same entries in the menus', function () {
    withInstall(function () {});
    function item(menuLabel, action) {
      var menu = App.MENUS.filter(function (m) { return m.label === menuLabel; })[0];
      return menu.items.filter(function (i) { return i && i.action === action; })[0];
    }
    try {
      App.LivePatches.syncDimensionAvailability(true);
      T.eq(item('View', 'viewIso').disabled, true);
      T.eq(item('View', 'toggleProjection').disabled, true);
      T.eq(!!item('View', 'zoomFit').disabled, false);
      App.LivePatches.syncDimensionAvailability(false);
      T.eq(!!item('View', 'viewIso').disabled, false);
    } finally {
      App.LivePatches.syncDimensionAvailability(false);
    }
  });

  test('a 3D-only action asked for in 2D is refused with a reason, not silently run', function () {
    var savedState = App.state;
    App.state = { modelMode: '2d', mode: 'soil' };
    try {
      withInstall(function (notes) {
        App.runAction({ action: 'viewIso' });
        T.eq(notes.filter(function (n) { return /^frozen:/.test(n); }), [],
             'the frozen dispatcher must never see it');
        T.ok(/2D/.test(notes[0] || ''), 'and the log says why: ' + notes[0]);
      });
    } finally {
      App.state = savedState;
    }
  });

  /* ── Navigation mode (the pan / rotate pair) ───────────────────── */

  test('a 2D model always navigates by panning, whatever the toolbar last said', function () {
    App.Viewport.setNavMode('rotate');
    T.eq(App.Viewport.effectiveNavMode(3), 'rotate');
    T.eq(App.Viewport.effectiveNavMode(2), 'pan', 'there is nothing to orbit in a section');
    App.Viewport.setNavMode('pan');
    T.eq(App.Viewport.effectiveNavMode(3), 'pan');
    App.Viewport.setNavMode('rotate');
  });

  test('pan mode turns a plain left-drag into the pan gesture js/orbit.js already knows', function () {
    var event = new MouseEvent('mousedown', { button: 0, shiftKey: false });
    T.eq(App.Viewport.forcePanIfNeeded(event, 'pan'), true);
    T.eq(event.shiftKey, true, 'js/orbit.js:86 reads shiftKey to choose pan over orbit');

    var rotating = new MouseEvent('mousedown', { button: 0, shiftKey: false });
    T.eq(App.Viewport.forcePanIfNeeded(rotating, 'rotate'), false);
    T.eq(rotating.shiftKey, false);

    var middle = new MouseEvent('mousedown', { button: 1, shiftKey: false });
    T.eq(App.Viewport.forcePanIfNeeded(middle, 'pan'), false, 'middle-drag already pans');
  });

  /* ── Undo / redo ───────────────────────────────────────────────── */

  test('history records a project change and undo puts the previous one back', function () {
    var put = [], applied = [];
    var stub = { put: function (path, body) { put.push([path, body]); return Promise.resolve(body); },
                 apply: function (project) { applied.push(project); } };
    var savedProject = App.PROJECT;
    App.PROJECT = { name: 'second' };
    return App.History.withEnv(stub, function () {
      App.History.reset();
      T.eq(App.History.canUndo(), false, 'a freshly loaded project has no history');

      App.History.record({ name: 'first' }, { name: 'second' });
      T.eq(App.History.canUndo(), true);
      App.History.record({ name: 'second' }, { name: 'second' });
      T.eq(App.History.depth().undo, 1, 'an unchanged project is not a step');

      return App.History.undo().then(function () {
        T.eq(put.length, 1);
        T.eq(put[0][0], '/api/project');
        T.eq(put[0][1], { name: 'first' });
        T.eq(applied, [{ name: 'first' }], 'the restored project is what gets rebuilt');
        T.eq(App.History.canUndo(), false);
        T.eq(App.History.canRedo(), true);
        return App.History.redo();
      }).then(function () {
        T.eq(put[1][1], { name: 'second' });
        T.eq(App.History.canRedo(), false);
      });
    }).then(function () { App.PROJECT = savedProject; },
            function (err) { App.PROJECT = savedProject; throw err; });
  });

  test('a new recorded step drops the redo branch', function () {
    var stub = { put: function (p, b) { return Promise.resolve(b); }, apply: function () {} };
    var savedProject = App.PROJECT;
    App.PROJECT = { n: 2 };
    return App.History.withEnv(stub, function () {
      App.History.reset();
      App.History.record({ n: 1 }, { n: 2 });
      return App.History.undo().then(function () {
        T.eq(App.History.canRedo(), true);
        App.History.record({ n: 1 }, { n: 3 });
        T.eq(App.History.canRedo(), false, 'redoing onto a diverged model would be a lie');
      });
    }).then(function () { App.PROJECT = savedProject; },
            function (err) { App.PROJECT = savedProject; throw err; });
  });

  test('history snapshots are deep copies, not references into the live project', function () {
    App.History.reset();
    var live = { layers: [{ id: 'L1' }] };
    App.History.record(live, { layers: [] });
    live.layers[0].id = 'mutated';
    T.eq(App.History.peekUndo(), { layers: [{ id: 'L1' }] });
  });

  test('history without an injected environment restores the model and refreshes the view', function () {
    var saved = { Api: App.Api, Model: App.Model, Viewport: App.Viewport,
                  PROJECT: App.PROJECT, Command: App.Command };
    var puts = [], applied = [], refreshed = 0;
    App.PROJECT = { name: 'after' };
    App.Command = { ok: function () {}, note: function () {}, err: function () {} };
    App.Api = { put: function (path, body) {
      puts.push([path, body]); return Promise.resolve(body);
    } };
    App.Model = { apply: function (project) { applied.push(project); App.PROJECT = project; } };
    App.Viewport = { refresh: function () { refreshed += 1; return Promise.resolve(); } };
    function restore() { App.History.reset(); Object.assign(App, saved); }
    return Promise.resolve().then(function () {
      App.History.reset();
      App.History.record({ name: 'before' }, App.PROJECT);
      return App.History.undo();
    }).then(function (changed) {
      T.eq(changed, true);
      T.eq(puts, [['/api/project', { name: 'before' }]]);
      T.eq(applied, [{ name: 'before' }]);
      T.eq(refreshed, 1);
      T.eq(App.History.depth(), { undo: 0, redo: 1 });
    }).then(restore, function (error) { restore(); throw error; });
  });

  test('history restores its environment when a test body throws synchronously', function () {
    var failure = new Error('test body failed'), caught;
    try {
      App.History.withEnv({}, function () { throw failure; });
    } catch (error) { caught = error; }
    T.eq(caught, failure);
  });

  test('history reports rejected writes and keeps the undo step available for retry', function () {
    var command = App.Command, errors = [];
    App.Command = { err: function (text) { errors.push(text); }, ok: function () {}, note: function () {} };
    return App.History.withEnv({
      put: function () { return Promise.reject(new Error('Project is locked')); }
    }, function () {
      App.History.reset();
      App.History.record({ name: 'before' }, { name: 'after' });
      return App.History.undo().then(function (changed) {
        T.eq(changed, false);
        T.eq(App.History.depth(), { undo: 1, redo: 0 });
        T.eq(errors, ['Could not undo: Project is locked']);
      });
    }).then(function () {
      return T.rejects(function () {
        return App.History.withEnv({}, function () {
          return Promise.reject(new Error('asynchronous test failure'));
        });
      });
    }).then(function (error) {
      T.eq(error.message, 'asynchronous test failure');
      return App.History.withEnv({ put: function (path, body) { return Promise.resolve(body); } },
        function () { return App.History.undo(); });
    }).then(function (changed) {
      T.eq(changed, true, 'the default injected apply callback accepts the retry');
    }).then(function () {
      App.History.reset(); App.Command = command;
    }, function (error) {
      App.History.reset(); App.Command = command; throw error;
    });
  });

  test('navigation, ruler and mesh-label switches notify the user and forward their state', function () {
    var saved = { Viewport: App.Viewport, Ruler: App.Ruler, Toolbars: App.Toolbars,
                  Command: App.Command, state: App.state };
    var notes = [], navigation = [], enabled = [], labelChanges = [], on = false;
    App.state = { modelMode: '2d', ruler: true };
    App.Command = { note: function (text) { notes.push(text); } };
    App.Ruler = { setEnabled: function (value) { enabled.push(value); } };
    App.Toolbars = { setToolbarState: function () {} };
    App.Viewport = {
      setNavMode: function (value) { navigation.push(value); return value; },
      syncRulers: function () {},
      labelsOn: function () { return on; },
      setLabels: function (kind, value, done) {
        labelChanges.push([kind, value]); on = value;
        if (done) done(12);
      }
    };
    try {
      App.LivePatches.setNavigation('pan');
      T.eq(navigation, ['pan']);
      T.ok(/left-drag pans/.test(notes[0]));
      App.LivePatches.toggleRulers();
      T.eq(App.state.ruler, false);
      T.eq(enabled, [false]);
      T.ok(/Rulers hidden/.test(notes[1]));
      App.LivePatches.toggleLabels('nodes');
      App.LivePatches.toggleLabels('nodes');
      T.eq(labelChanges, [['nodes', true], ['nodes', false]]);
      T.ok(/12 nodes/.test(notes[2]));
      T.eq(notes[3], 'Node ID labels hidden.');
    } finally { Object.assign(App, saved); }
  });

  test('turned on in a tab that does not draw the mesh, the IDs stay on for one that does',
       function () {
    var saved = { Viewport: App.Viewport, Command: App.Command, state: App.state };
    var notes = [], changes = [], on = false;
    App.Command = { note: function (text) { notes.push(text); } };
    App.Viewport = {
      hasMesh: function () { return true; },
      labelsOn: function () { return on; },
      setLabels: function (kind, value, done) {
        changes.push(value); on = value;
        if (done) done(0);                        // nothing drawn here to number
      }
    };
    try {
      App.state = { mode: 'structures' };
      App.LivePatches.toggleLabels('nodes');
      T.eq(changes, [true], 'left on');
      T.ok(/Mesh tab and in Results/.test(notes[0]), notes[0]);
      on = false;
      App.state = { mode: 'results' };
      App.LivePatches.toggleLabels('nodes');
      T.eq(changes, [true, true, false], 'Results with no result: off again');
      T.eq(notes[1], 'Nothing to label — open a result first.');
    } finally { Object.assign(App, saved); }
  });

  /* ── Structures rail order ─────────────────────────────────────── */

  /* Every live tool was appended to the frozen rail, so sheet piles, anchors and
     the import tools ended up after the frozen tools instead of beside the members
     they belong with. The rail is composed in build order now; the tools with
     nothing behind them are taken out. */
  test('the Structures rail is ordered by how a model is built', function () {
    withInstall(function () {});
    var keys = (App.RAILS.structures || []).map(function (tool) {
      return tool === '-' ? '-' : (tool.action || tool.icon);
    });
    T.eq(keys, [
      'select',
      '-', 'drawLine', 'drawPolygon', 'drawBox',
      '-', 'createSheetPile', 'createMember', 'createAnchor', 'interface',
      '-', 'createLoad', 'createBoundaryCondition',
      '-', 'importModel'
    ]);
  });

  test('the frozen node-to-node anchor tool gives way to the live anchor tool', function () {
    withInstall(function () {});
    var anchors = (App.RAILS.structures || []).filter(function (tool) {
      return tool && tool.icon === 'anchor';
    });
    T.eq(anchors.length, 1, 'one anchor button, not a dead twin next to the real one');
    T.eq(anchors[0].action, 'createAnchor');
  });

  test('ordering the rail keeps a tool it does not recognise rather than dropping it', function () {
    var mine = { icon: 'star', tip: 'Something new', action: 'doSomething' };
    var keys = App.LivePatches.orderStructuresRail([
      mine, '-', { icon: 'beam', tip: 'Create beam' }, { icon: 'select', tip: 'Select' }
    ]).map(function (tool) { return tool === '-' ? '-' : tool.action || tool.icon; });
    T.eq(keys, ['select', '-', 'beam', '-', 'doSomething']);
  });

  test('ordering the rail twice changes nothing the second time', function () {
    var once = App.LivePatches.orderStructuresRail(App.RAILS.structures || []);
    T.eq(App.LivePatches.orderStructuresRail(once), once);
  });

  test('the Soil rail reads Select, material sets, soil layers; no borehole', function () {
    withInstall(function () {});
    var keys = (App.RAILS.soil || []).map(function (tool) {
      return tool === '-' ? '-' : tool.action || tool.icon;
    });
    T.eq(keys, ['select', '-', 'materials', 'soilLayers', '-', 'createSoilVolume']);
  });

  test('the Soil menu reads as its rail: material sets, soil layers; no borehole',
       function () {
    withInstall(function () {});
    var soil = App.MENUS.filter(function (m) { return m.label === 'Soil'; })[0];
    var keys = soil.items.map(function (item) { return item === '-' ? '-' : item.action; });
    T.eq(keys, ['materials', 'soilLayers', '-', 'createSoilVolume']);
  });

  test('Flow conditions comes before Mesh, on the mode tabs and in the menu bar', function () {
    withInstall(function () {});
    var modes = App.MODES.map(function (m) { return m.id; });
    T.eq(modes.slice(0, 5), ['soil', 'structures', 'flow', 'mesh', 'staged']);
    var menus = App.MENUS.map(function (m) { return m.label; });
    T.ok(menus.indexOf('Flow conditions') + 1 === menus.indexOf('Mesh'),
      'Flow conditions sits right before Mesh: ' + menus.join(', '));
    var groupOf = {};
    App.MODES.forEach(function (m) { groupOf[m.id] = m.group; });
    T.eq(groupOf.flow, groupOf.soil, 'Flow conditions is grouped under Geometry with Soil');
    T.ok(groupOf.mesh !== groupOf.flow, 'Mesh stays under Calculation');
  });

  test('moving an entry before another leaves a list already in order alone', function () {
    var keyOf = function (s) { return s; };
    T.eq(App.LivePatches.moveBefore(['a', 'mesh', 'flow', 'b'], keyOf, 'flow', 'mesh'),
      ['a', 'flow', 'mesh', 'b']);
    T.eq(App.LivePatches.moveBefore(['flow', 'mesh'], keyOf, 'flow', 'mesh'), ['flow', 'mesh']);
    T.eq(App.LivePatches.moveBefore(['mesh'], keyOf, 'flow', 'mesh'), ['mesh']);
  });

  test('the Soil-mode hint speaks of materials and layers, not boreholes', function () {
    var soil = App.MODES.filter(function (mode) { return mode.id === 'soil'; })[0];
    T.ok(!/borehole/i.test(soil.hint), soil.hint);
    T.ok(/layers/.test(soil.hint), soil.hint);
  });

  test('ordering the Soil rail keeps a tool it does not recognise', function () {
    var mine = { icon: 'star', tip: 'Something new', action: 'doSomething' };
    var keys = App.LivePatches.orderSoilRail([
      { icon: 'soillayers', action: 'soilLayers' }, mine, '-',
      { icon: 'materials', action: 'materials' }, { icon: 'select', tip: 'Select' }
    ]).map(function (tool) { return tool === '-' ? '-' : tool.action || tool.icon; });
    T.eq(keys, ['select', '-', 'materials', 'soilLayers', '-', 'doSomething']);
  });

  /* ── New / open / save ─────────────────────────────────────────── */

  test('new project asks the server for an empty site rather than inventing one', function () {
    var saved = { post: App.Api.post, command: App.Command, model: App.Model, viewport: App.Viewport };
    var posted = [], applied = null;
    App.Api.post = function (path) { posted.push(path); return Promise.resolve({ project: { name: 'Untitled project' } }); };
    App.Command = { note: function () {}, ok: function () {}, err: function () {}, write: function () {}, run: function () {} };
    App.Model = { apply: function (p) { applied = p; return p; } };
    App.Viewport = { refresh: function () { return Promise.resolve(); } };
    function restore() {
      App.Api.post = saved.post; App.Command = saved.command;
      App.Model = saved.model; App.Viewport = saved.viewport;
    }
    return App.LivePatches.newProject().then(function () {
      T.eq(posted, ['/api/project/new']);
      T.eq(applied, { name: 'Untitled project' });
      T.eq(App.History.canUndo(), false, 'a new document starts with an empty history');
    }).then(restore, function (err) { restore(); throw err; });
  });

  test('a saved project is named after the project, not after the page', function () {
    T.eq(App.LivePatches.projectFileName({ name: 'Deep excavation — Rotterdam' }),
         'Deep excavation — Rotterdam.json');
    T.eq(App.LivePatches.projectFileName({ name: 'pit / east: v2' }), 'pit - east- v2.json',
         'the characters a path separator would swallow are the ones replaced');
    T.eq(App.LivePatches.projectFileName({}), 'project.json');
  });

  /* The name inside the document is whatever it was called when it was written --
     "Deep excavation — Rotterdam Zuid" for anything derived from the seed -- so the
     title bar said that no matter which file was opened. The file the user picked is
     the name they know the project by. */
  test('an opened project takes its name from the file', function () {
    T.eq(App.LivePatches.projectNameFromFile('Deep_excavation_with_load.json'),
         'Deep_excavation_with_load');
    T.eq(App.LivePatches.projectNameFromFile('Pit east.JSON'), 'Pit east');
    T.eq(App.LivePatches.projectNameFromFile('  spaced.json  '), 'spaced');
    T.eq(App.LivePatches.projectNameFromFile('no-extension'), 'no-extension');
  });

  test('a file with nothing but an extension leaves the name in the document alone',
       function () {
    T.eq(App.LivePatches.projectNameFromFile('.json'), '');
    T.eq(App.LivePatches.projectNameFromFile(''), '');
    T.eq(App.LivePatches.projectNameFromFile(null), '');
  });

  test('open and save agree: the file saved is the file that was opened', function () {
    var opened = 'Deep_excavation_with_load.json';
    T.eq(App.LivePatches.projectFileName(
           { name: App.LivePatches.projectNameFromFile(opened) }), opened);
  });

  test('opening a file rejects anything that is not a project document', function () {
    T.eq(App.LivePatches.projectFromFileText('{"name":"x","layers":[]}'), { name: 'x', layers: [] });
    var bad = null;
    try { App.LivePatches.projectFromFileText('not json'); } catch (err) { bad = err.message; }
    T.ok(/not a project file/i.test(bad || ''), 'got: ' + bad);
    try { App.LivePatches.projectFromFileText('[1,2,3]'); } catch (err) { bad = err.message; }
    T.ok(/not a project file/i.test(bad || ''), 'got: ' + bad);
  });

})();
