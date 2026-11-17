/* What Styx does not do yet is greyed, everywhere it is drawn, by one rule
   (patches.js NOT_YET / `implemented`) -- and the menu twins of tools that do work
   carry the tool's action, so a menu row and its button cannot disagree. */

(function () {

  /* The test page loads no js/app.js, so there is no frozen App.runAction for the
     overlay to wrap. This gives it one, installs, and puts everything back. */
  function withInstall(body) {
    var saved = { action: App.runAction, command: App.Command };
    var ctx = { notes: [], frozen: [], typed: [] };
    App.runAction = function (item) { ctx.frozen.push(item && item.action); };
    App.Command = { note: function (t) { ctx.notes.push(t); },
                    ok: function (t) { ctx.notes.push(t); },
                    err: function (t) { ctx.notes.push(t); },
                    write: function (kind, t) { ctx.notes.push(kind + ':' + t); },
                    run: function (t) { ctx.typed.push(t); } };
    App.LivePatches.install();
    // Whatever install() itself logged is not the test's business.
    ctx.notes.length = 0;
    ctx.frozen.length = 0;
    try { return body(ctx); }
    finally {
      App.runAction = saved.action; App.Command = saved.command;
      App.LivePatches.resetForTests();
    }
  }

  function menu(label) {
    return App.MENUS.filter(function (m) { return m.label === label; })[0];
  }

  function row(menuLabel, pattern) {
    return (menu(menuLabel).items || []).filter(function (i) {
      return i && i.label && pattern.test(i.label);
    });
  }

  /* ── The rule ──────────────────────────────────────────────────────── */

  test('a control works when it has an action not on NOT_YET, or opens a real submenu',
       function () {
    var implemented = App.LivePatches.implemented;
    T.eq(implemented({ label: 'Print…' }), false, 'no action: nothing behind it');
    T.eq(implemented({ label: 'Zoom to fit', action: 'zoomFit' }), true);
    T.eq(implemented({ label: 'Import soil layers…', action: 'importSoilLayers' }), false,
         'an action that runs, but not what its label says');
    T.eq(implemented({ label: 'Recent projects', sub: true }), false,
         "the mockup's placeholder submenu is not a submenu");
    T.eq(implemented({ label: 'Stage', sub: [] }), true, 'a submenu a caller fills is');
    T.eq(implemented('-'), true, 'a separator is not a control');
    T.eq(implemented({ title: 'Standard views' }), true, 'nor is a caption');
    T.eq(App.LivePatches.NOT_YET.slice().sort(),
         ['coarsenMesh', 'drawPoint', 'importSoilLayers', 'refineMesh',
          'resetMeshRefinement']);
  });

  test('every menu row that does nothing is greyed, submenus included', function () {
    withInstall(function () {});
    var live = [];
    function walk(items, path) {
      (items || []).forEach(function (item) {
        if (!item || typeof item !== 'object' || item.title) return;
        if (!App.LivePatches.implemented(item) && !item.disabled) live.push(path + item.label);
        if (Array.isArray(item.sub)) walk(item.sub, path + item.label + ' > ');
      });
    }
    App.MENUS.forEach(function (m) { walk(m.items, m.label + ' > '); });
    T.eq(live, [], 'rows that look ready and do nothing');
  });

  test('the rows the mockup drew without anything behind them are greyed by name',
       function () {
    withInstall(function () {});
    [['File', /^Recent projects$/], ['File', /^Pack project/], ['File', /^Print/],
     ['File', /^Exit$/], ['Edit', /^Select all$/],
     ['Structures', /^Create point$/],
     ['Soil', /^Import soil layers/], ['Structures', /^Create plate$/],
     ['Structures', /^Create beam$/], ['Structures', /^Create embedded beam$/],
     ['Structures', /^Tunnel designer/], ['Mesh', /^Refine mesh$/],
     ['Mesh', /^Coarsen mesh$/], ['Mesh', /^Reset local refinement$/],
     ['Flow conditions', /^Create well$/], ['Flow conditions', /^Create drain$/],
     ['Flow conditions', /^Flow functions/], ['Flow conditions', /^Global water level$/],
     ['Stages', /^Add stage$/], ['Stages', /^Insert stage$/],
     ['Expert', /^Examine commands/], ['Expert', /^Macro library/],
     ['Expert', /^Configure remote scripting/], ['Expert', /^Python interpreter/],
     ['Help', /^Reference manual$/], ['Help', /^Tutorial manual$/]
    ].forEach(function (pair) {
      var found = row(pair[0], pair[1]);
      T.eq(found.length, 1, pair[0] + ' > ' + pair[1]);
      T.eq(found[0].disabled, true, pair[0] + ' > ' + found[0].label + ' is greyed');
    });
    T.eq(!!row('Flow conditions', /^Global water level$/)[0].checked, false,
         'a tick nobody can change is not shown');
  });

  test('the rows that work are left alone', function () {
    withInstall(function () {});
    [['File', /^Export model/], ['View', /^Zoom to fit$/], ['Soil', /^Modify soil layers/],
     ['Help', /^Command reference$/], ['Help', /^About/]
    ].forEach(function (pair) {
      T.eq(!!row(pair[0], pair[1])[0].disabled, false, pair[0] + ' > ' + pair[1]);
    });
  });

  /* ── The rail ──────────────────────────────────────────────────────── */

  function notYetTips(mode) {
    return (App.RAILS[mode] || []).filter(function (t) { return t && t.notYet; })
      .map(function (t) { return t.tip.replace(App.LivePatches.NOT_YET_TIP, ''); });
  }

  test('the rail tools with nothing behind them are marked, in every mode', function () {
    withInstall(function () {});
    T.eq(notYetTips('soil'), []);
    T.eq(notYetTips('structures'), ['Select multiple objects', 'Create point', 'Create plate',
         'Create beam', 'Create embedded beam row', 'Tunnel designer']);
    T.eq(notYetTips('mesh'), ['Refine mesh', 'Coarsen mesh', 'Reset local refinement']);
    T.eq(notYetTips('flow'), ['Create well', 'Create drain', 'Flow functions']);
    T.eq(notYetTips('staged'), ['Select multiple objects', 'Activate selection',
         'Deactivate selection', 'Preview stage']);
  });

  test('a greyed rail tool says so in its tip, and loses a flyout of nothing', function () {
    withInstall(function () {});
    var plate = App.RAILS.structures.filter(function (t) { return t && t.icon === 'plate'; })[0];
    T.eq(plate.tip, 'Create plate' + App.LivePatches.NOT_YET_TIP);
    T.eq(plate.flyout, undefined);
    withInstall(function () {});
    T.eq(plate.tip, 'Create plate' + App.LivePatches.NOT_YET_TIP,
         'a second install does not say it twice');
  });

  test('Select is never greyed: it is the pointer, and picking works', function () {
    withInstall(function () {});
    Object.keys(App.RAILS).forEach(function (mode) {
      var select = App.RAILS[mode].filter(function (t) { return t && t.icon === 'select'; })[0];
      if (!select) return;
      T.eq(select.action, 'select', mode);
      T.eq(!!select.notYet, false, mode);
    });
  });

  test('choosing Select ends a draw tool and says nothing of a missing feature',
       function () {
    var savedDraw = App.DrawInput;
    var cancelled = 0;
    App.DrawInput = { cancel: function () { cancelled += 1; } };
    try {
      withInstall(function (ctx) {
        App.runAction({ action: 'select', tip: 'Select' });
        T.eq(cancelled, 1);
        T.eq(ctx.frozen, [], 'the frozen dispatcher would call it a mockup');
        T.eq(ctx.notes, []);
      });
    } finally { App.DrawInput = savedDraw; }
  });

  test('a greyed tool is drawn greyed but keeps its tip; Select stays live', function () {
    var savedState = App.state;
    App.state = { mode: 'structures', modelMode: '2d' };
    try {
      withInstall(function (ctx) {
        App.Toolbars.mountRail('structures');
        var tools = App.RAILS.structures.filter(function (t) { return t !== '-'; });
        var buttons = document.querySelectorAll('#toolrail .rail-btn');
        function button(icon) {
          return buttons[tools.map(function (t) { return t.icon; }).indexOf(icon)];
        }
        var tunnel = button('tunnel');
        T.ok(tunnel.classList.contains('disabled'), 'Tunnel designer is drawn greyed');
        T.ok(tunnel.classList.contains('not-yet'), 'and keeps its pointer events');
        T.eq(tunnel.getAttribute('aria-disabled'), 'true');
        T.eq(tunnel.disabled, false, 'a disabled button gets no mouseenter, so no tip');
        tunnel.click();
        T.eq(ctx.notes, [], 'the click goes nowhere: no "not implemented" note');
        T.eq(ctx.frozen, []);
        T.eq(tunnel.classList.contains('active'), false, 'nor does it become the tool');
        T.eq(button('select').classList.contains('disabled'), false);
        T.eq(button('line').classList.contains('disabled'), false, 'Create line works');
        T.eq(button('line').classList.contains('not-yet'), false);
        T.eq(button('line').hasAttribute('aria-disabled'), false);
        T.ok(button('point').classList.contains('not-yet'),
             'Create point is greyed: the server has no point recipe');
      });
    } finally {
      App.state = savedState;
      App.UI.clear(document.getElementById('toolrail'));
    }
  });

  /* ── Refusal ───────────────────────────────────────────────────────── */

  test('a NOT_YET action that still arrives is refused, not run', function () {
    withInstall(function (ctx) {
      App.runAction({ action: 'importSoilLayers', label: 'Import soil layers…' });
      App.runAction({ action: 'refineMesh', tip: 'Refine mesh' + App.LivePatches.NOT_YET_TIP });
      T.eq(ctx.frozen, [], 'the frozen dispatcher would open the mockup dialog');
      T.eq(ctx.notes, ['"Import soil layers…" is not available in Styx yet.',
                       '"Refine mesh" is not available in Styx yet.']);
    });
  });

  /* ── No boreholes ────────────────────────────────────────────────────
     A layer has one top and one bottom, so there is no borehole to make: not from the
     menu, not from the rail and not typed. */

  test('there is no borehole to make, from the menu, the rail or the command box',
       function () {
    withInstall(function () {});
    T.eq(row('Soil', /borehole/i).length, 0, 'Soil > Create borehole');
    T.eq((App.RAILS.soil || []).filter(function (t) {
      return t && /borehole/i.test(t.action || t.icon || '');
    }).length, 0, 'the Soil rail');
    T.eq(App.LivePatches.COMMANDS.filter(function (c) { return /borehole/.test(c[0]); })
           .length, 0, 'help');
    T.eq(App.LivePatches.shellAnswers('borehole'), false, 'typed: an unknown command');
  });

  /* ── Menu twins ────────────────────────────────────────────────────── */

  test('the menu twins of working tools carry the tool’s action', function () {
    withInstall(function () {});
    T.eq(row('Structures', /^Create point$/)[0].action, 'drawPoint');
    T.eq(row('Structures', /^Create line$/)[0].action, 'drawLine');
    T.eq(row('Structures', /^Create surface$/)[0].action, 'drawPolygon');
    T.eq(row('Mesh', /^View mesh$/)[0].action, 'viewMesh');
    T.eq(row('Edit', /^Deselect all$/)[0].action, 'deselectAll');
    var water = row('Flow conditions', /water pressure line/);
    T.eq(water.length, 1, 'named as the rail button is');
    T.eq(water[0].action, 'createWaterPressureLine');
    T.eq(row('Flow conditions', /^Create water level$/), []);
  });

  test('the water pressure line row is plane strain, like its rail button', function () {
    withInstall(function () {});
    var water = row('Flow conditions', /water pressure line/)[0];
    try {
      App.LivePatches.syncDimensionAvailability(false);
      T.eq(water.disabled, true);
      App.LivePatches.syncDimensionAvailability(true);
      T.eq(water.disabled, false);
    } finally { App.LivePatches.syncDimensionAvailability(true); }
  });

  test('one Create anchor row, and it is the working one', function () {
    withInstall(function () {});
    var anchors = row('Structures', /^Create anchor/);
    T.eq(anchors.length, 1, 'not the dead frozen row beside the live one');
    T.eq(anchors[0].action, 'createAnchor');
  });

  test('Deselect all clears the selection, as Esc does', function () {
    var savedSelect = App.selectObject;
    var picked = 'unset';
    App.selectObject = function (key) { picked = key; };
    try {
      withInstall(function (ctx) {
        App.runAction({ action: 'deselectAll', label: 'Deselect all' });
        T.eq(picked, null);
        T.eq(ctx.frozen, []);
      });
    } finally { App.selectObject = savedSelect; }
  });

  test('Edit > Undo starts greyed, as the toolbar Undo does', function () {
    App.History.reset();
    withInstall(function () {});
    T.eq(row('Edit', /^Undo$/)[0].disabled, true);
    T.eq(row('Edit', /^Redo$/)[0].disabled, true);
  });

  /* ── Ticks ─────────────────────────────────────────────────────────── */

  test('the menu ticks follow the state they describe', function () {
    var savedState = App.state;
    var made = [];
    ['vp-triad', 'cmdpanel'].forEach(function (id) {
      if (document.getElementById(id)) return;
      var node = document.createElement('div');
      node.id = id;
      node.hidden = true;
      document.body.appendChild(node);
      made.push(node);
    });
    var triad = document.getElementById('vp-triad');
    var panel = document.getElementById('cmdpanel');
    var was = { triad: triad.style.display, panel: panel.style.display };
    try {
      withInstall(function () {});
      function tick(menuLabel, pattern) { return !!row(menuLabel, pattern)[0].checked; }

      App.state = { modelMode: '3d', projection: true, grid: false };
      triad.style.display = 'none';
      panel.style.display = '';
      App.LivePatches.syncCheckMarks();
      T.eq(tick('View', /^Perspective projection$/), true);
      T.eq(tick('View', /^Show grid$/), false);
      T.eq(tick('View', /^Show axes triad$/), false);
      T.eq(tick('View', /^Show command panel$/), true);
      T.eq(tick('Expert', /^Command line$/), true);

      App.state = { modelMode: '3d', projection: false, grid: true };
      panel.style.display = 'none';
      App.LivePatches.syncCheckMarks();
      T.eq(tick('View', /^Perspective projection$/), false, 'orthographic');
      T.eq(tick('View', /^Show grid$/), true);
      T.eq(tick('Expert', /^Command line$/), false);

      App.state = { modelMode: '2d', projection: true };
      App.LivePatches.syncCheckMarks();
      T.eq(tick('View', /^Perspective projection$/), false, 'a section is never perspective');
    } finally {
      App.state = savedState;
      triad.style.display = was.triad;
      panel.style.display = was.panel;
      made.forEach(function (node) { node.remove(); });
      App.LivePatches.syncCheckMarks();
    }
  });

  test('a frozen toggle run through App.runAction moves its menu tick', function () {
    var savedState = App.state;
    App.state = { modelMode: '3d', projection: true, grid: true };
    try {
      withInstall(function () {
        // The frozen stand-in records the call; the state is flipped here, as
        // js/app.js:167 would.
        App.state.grid = false;
        App.runAction({ action: 'toggleGrid' });
        T.eq(!!row('View', /^Show grid$/)[0].checked, false);
      });
    } finally { App.state = savedState; App.LivePatches.syncCheckMarks(); }
  });

  /* ── Viewport menu and flyouts ─────────────────────────────────────── */

  test('the viewport menu greys the 3D views over a section', function () {
    var savedState = App.state;
    App.state = { modelMode: '2d', projection: true };
    try {
      var items = App.LivePatches.gateViewportItems([
        { label: 'Zoom to fit', action: 'zoomFit' },
        { label: 'Isometric view', action: 'viewIso' },
        { label: 'Perspective projection', action: 'toggleProjection', checked: true },
        '-', { label: 'Hide selected' }
      ]);
      T.eq(!!items[0].disabled, false);
      T.eq(items[1].disabled, true);
      T.eq(items[2].disabled, true);
      T.eq(items[2].checked, false);
      T.eq(!!items[4].disabled, false, 'a row its own callback answers is not ours to grey');

      App.state = { modelMode: '3d', projection: true };
      items = App.LivePatches.gateViewportItems([
        { label: 'Isometric view', action: 'viewIso' },
        { label: 'Perspective projection', action: 'toggleProjection' }]);
      T.eq(!!items[0].disabled, false);
      T.eq(items[1].checked, true);
    } finally { App.state = savedState; }
  });

  test('the sheet-pile flyout greys the kind the open model cannot hold', function () {
    withInstall(function () {});
    var tool = App.RAILS.structures.filter(function (t) {
      return t && t.action === 'createSheetPile';
    })[0];
    function off(pattern) {
      return !!tool.flyout.filter(function (i) { return pattern.test(i.label); })[0].disabled;
    }
    try {
      App.LivePatches.syncDimensionAvailability(true);
      T.eq(off(/^Sheet pile/), false);
      T.eq(off(/^Wall panel/), true);
      T.eq(off(/^Member/), true);
      App.LivePatches.syncDimensionAvailability(false);
      T.eq(off(/^Sheet pile/), true);
      T.eq(off(/^Wall panel/), false);
      T.eq(off(/^Member/), false);
    } finally { App.LivePatches.syncDimensionAvailability(true); }
  });

  /* ── The frozen dialogs and the tree ───────────────────────────────── */

  test("the frozen tree menu's dead Properties… is greyed; the live one is not touched",
       function () {
    var saved = { project: App.PROJECT, menu: App.Menu };
    var opened = null;
    App.PROJECT = { custom_parts: [] };
    App.Menu = { openAt: function (items) { opened = items; } };
    var row = document.createElement('div');
    row.className = 'tree-row';
    // A group row: a soil layer's row is the live menu's now (its Rename window).
    row.dataset.obj = 'grp_soil';
    try {
      App.LivePatches.onTreeContextMenu({ target: row, preventDefault: function () {},
                                          stopImmediatePropagation: function () {} });
      // What js/explorer.js:102 then does, inside the same event.
      App.Menu.openAt([{ label: 'Zoom to object', action: 'zoomFit' },
                       { label: 'Properties…', icon: 'settings' }], 0, 0, function () {});
      T.ok(opened, 'the frozen menu still opens');
      T.eq(!!opened[0].disabled, false);
      T.eq(opened[1].disabled, true);
      var again = null;
      App.Menu.openAt = function (items) { again = items; };
      App.Menu.openAt([{ label: 'Properties…' }]);
      T.eq(!!again[0].disabled, false, 'the loan is for one menu only');
    } finally { App.PROJECT = saved.project; App.Menu = saved.menu; }
  });
})();
