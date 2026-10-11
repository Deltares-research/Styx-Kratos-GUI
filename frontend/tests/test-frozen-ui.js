/* The frozen mockup layer (js/menubar.js, toolbars.js, dialogs.js, explorer.js,
   command.js): every user action passes through it, and the files are not edited --
   so they are pinned here, from the outside, by what a click or a key does to the DOM. */

(function () {

  /* js/command.js is not on the page: loaded for good it would replace App.Command, which
     the live layer extends (with `err`, among others) and every other suite stands in.
     It is loaded for its own tests only, and the harness puts App.Command back after
     each one. */
  var FrozenCommand = null;
  function frozenCommand() {
    if (FrozenCommand) return Promise.resolve(FrozenCommand);
    var before = App.Command;
    return new Promise(function (resolve, reject) {
      var script = document.createElement('script');
      script.src = '../base/js/command.js';
      script.onload = function () {
        FrozenCommand = App.Command;
        App.Command = before;
        script.remove();
        resolve(FrozenCommand);
      };
      script.onerror = function () { reject(new Error('js/command.js did not load')); };
      document.head.appendChild(script);
    });
  }

  /* One menu layer for the page, never removed: App.UI caches the element the first time
     it finds it, so a layer made and removed per test leaves later popups in a detached
     node nobody can see. */
  if (!document.getElementById('menu-layer')) {
    var menuLayer = document.createElement('div');
    menuLayer.id = 'menu-layer';
    document.body.appendChild(menuLayer);
  }

  function host(id) {
    if (id === 'menu-layer') return { node: document.getElementById(id), remove: function () {} };
    var node = document.getElementById(id);
    var made = !node;
    if (made) {
      node = document.createElement('div');
      node.id = id;
      document.body.appendChild(node);
    }
    return { node: node, remove: function () { if (made) node.remove(); else App.UI.clear(node); } };
  }

  function mouse(target, type, init) {
    target.dispatchEvent(new MouseEvent(type, Object.assign({ bubbles: true, cancelable: true }, init)));
  }

  function key(target, name) {
    target.dispatchEvent(new KeyboardEvent('keydown', { key: name, bubbles: true, cancelable: true }));
  }

  function menus() { return document.querySelectorAll('#menu-layer .menu'); }

  /* ── js/menubar.js ────────────────────────────────────────────────────── */

  test('frozen menu: items, separators, titles, ticks and disabled entries render', function () {
    var picked = [];
    var menu = App.Menu.build([
      { title: 'Group' }, { label: 'One', key: 'Ctrl+1' }, '-',
      { label: 'Ticked', checked: true }, { label: 'Off', disabled: true }
    ], function (it) { picked.push(it.label); });
    T.eq(menu.querySelectorAll('.menu-title').length, 1);
    T.eq(menu.querySelectorAll('.menu-sep').length, 1);
    var rows = menu.querySelectorAll('.menu-item');
    T.eq(rows.length, 3);
    T.ok(rows[1].querySelector('.mi-check'), 'a ticked entry shows the tick');
    T.ok(rows[2].classList.contains('disabled'));
    rows[0].click();
    rows[2].click();
    T.eq(picked, ['One'], 'a disabled entry dispatches nothing');
  });

  test('frozen menu: hovering an entry with a submenu opens it beside the row', function () {
    var layer = host('menu-layer');
    try {
      App.Menu.openAt([{ label: 'Labels', sub: [{ label: 'Nodes' }, { label: 'Elements' }] }],
                      10, 10, function () {});
      mouse(document.querySelector('#menu-layer .menu .menu-item'), 'mouseenter');
      T.eq(menus().length, 2, 'the submenu is a second popup');
      T.eq(menus()[1].querySelectorAll('.menu-item').length, 2);
      App.UI.closePopups(0);
      T.eq(menus().length, 0);
    } finally { App.UI.closePopups(0); layer.remove(); }
  });

  test('frozen menu bar: one button per menu; a press opens it, a second press closes it', function () {
    var bar = host('menubar'), layer = host('menu-layer');
    var saved = App.runAction, ran = [];
    App.runAction = function (it) { ran.push(it.label); };
    try {
      App.Menu.mountBar();
      var buttons = bar.node.querySelectorAll('button.mb-item');
      T.eq(buttons.length, App.MENUS.length);
      mouse(buttons[0], 'mousedown');
      T.eq(menus().length, 1);
      T.ok(buttons[0].classList.contains('open'));
      mouse(buttons[1], 'mouseenter');
      T.ok(buttons[1].classList.contains('open') && !buttons[0].classList.contains('open'),
           'with one menu open, hovering another switches to it');
      var first = Array.prototype.filter.call(menus()[0].querySelectorAll('.menu-item'),
        function (r) { return !r.classList.contains('disabled') && !r.querySelector('.mi-sub').textContent; })[0];
      first.click();
      T.eq(ran.length, 1, 'picking an entry runs its action');
      T.eq(menus().length, 0, 'and closes the menu');
      mouse(buttons[0], 'mousedown');
      mouse(buttons[0], 'mousedown');
      T.eq(menus().length, 0, 'a second press on the open menu closes it');
    } finally { App.UI.closePopups(0); App.runAction = saved; bar.remove(); layer.remove(); }
  });

  test('frozen menu: Escape and a click elsewhere close an open menu', function () {
    var layer = host('menu-layer');
    try {
      App.Menu.openAt([{ label: 'A' }], 5, 5, function () {});
      key(document, 'Escape');
      T.eq(menus().length, 0, 'Escape');
      App.Menu.openAt([{ label: 'A' }], 5, 5, function () {});
      mouse(document.body, 'mousedown');
      T.eq(menus().length, 0, 'a click outside');
    } finally { App.UI.closePopups(0); layer.remove(); }
  });

  /* ── js/toolbars.js ───────────────────────────────────────────────────── */

  test('frozen toolbar: one button per entry, carrying its action, and toggles are exclusive', function () {
    var saved = { TOOLBAR: App.TOOLBAR, runAction: App.runAction };
    var ran = [];
    App.runAction = function (t) { ran.push(t.action); };
    App.TOOLBAR = [{ icon: 'new', action: 'newProject', tip: 'New' }, '|',
                   { icon: 'grid', action: 'navPan', toggle: 'nav', tip: 'Pan' },
                   { icon: 'grid', action: 'navRotate', toggle: 'nav', tip: 'Rotate', on: true }];
    try {
      App.Toolbars.mountMain();
      var bar = document.getElementById('maintoolbar');
      var buttons = bar.querySelectorAll('.tbtn');
      T.eq(buttons.length, 3);
      T.eq(bar.querySelectorAll('.tbsep').length, 1);
      T.eq(buttons[0].dataset.action, 'newProject');
      buttons[1].click();
      T.eq(ran, ['newProject'].slice(0, 0).concat(['navPan']));
      T.ok(buttons[1].classList.contains('active') && !buttons[2].classList.contains('active'),
           'one of a toggle group at a time');
      App.Toolbars.setToolbarState('newProject', true);
      T.ok(buttons[0].classList.contains('active'));
    } finally { App.TOOLBAR = saved.TOOLBAR; App.runAction = saved.runAction; }
  });

  test('frozen mode tabs: grouped under their labels, a click sets the mode, one is active', function () {
    var saved = App.setMode, set = [];
    App.setMode = function (m) { set.push(m); };
    try {
      App.Toolbars.mountModes();
      var tabs = document.querySelectorAll('#modetabs .mode-tab');
      T.eq(tabs.length, App.MODES.length);
      T.ok(document.querySelectorAll('#modetabs .mode-group-label').length >= 1);
      tabs[1].click();
      T.eq(set, [App.MODES[1].id]);
      App.Toolbars.highlightMode(App.MODES[1].id);
      T.eq(document.querySelectorAll('#modetabs .mode-tab.active').length, 1);
    } finally { App.setMode = saved; }
  });

  test('frozen tool rail: a tool runs its action; a tool without one says so', function () {
    var saved = { RAILS: App.RAILS, runAction: App.runAction, Command: App.Command };
    var ran = [], notes = [];
    App.runAction = function (t) { ran.push(t.action); };
    App.Command = { note: function (t) { notes.push(t); } };
    App.RAILS = Object.assign({}, App.RAILS, { testing: [
      { icon: 'select', tip: 'Select', action: 'select' }, '-',
      { icon: 'line', tip: 'Draw line…' }] });
    try {
      App.Toolbars.mountRail('testing');
      var buttons = document.querySelectorAll('#toolrail .rail-btn');
      T.eq(buttons.length, 2);
      buttons[0].click();
      buttons[1].click();
      T.eq(ran, ['select']);
      T.ok(/not implemented/.test(notes[0]));
      T.ok(buttons[1].classList.contains('active'), 'the last tool used is highlighted');
    } finally { Object.assign(App, saved); }
  });

  test("frozen tool rail: a tool's flyout opens from its corner", function () {
    var layer = host('menu-layer');
    var saved = { RAILS: App.RAILS, runAction: App.runAction };
    var ran = [];
    App.runAction = function (t) { ran.push(t.action); };
    App.RAILS = Object.assign({}, App.RAILS, { testing: [
      { icon: 'load', tip: 'Loads', action: 'load', flyout: [{ label: 'Line load', action: 'lineLoad' }] }] });
    try {
      App.Toolbars.mountRail('testing');
      var button = document.querySelector('#toolrail .rail-btn');
      var r = button.getBoundingClientRect();
      mouse(button, 'click', { clientX: r.right - 2, clientY: r.bottom - 2 });
      T.eq(menus().length, 1, 'the corner opens the flyout instead of the tool');
      menus()[0].querySelector('.menu-item').click();
      T.eq(ran, ['lineLoad']);
    } finally { App.UI.closePopups(0); Object.assign(App, saved); layer.remove(); }
  });

  /* ── js/dialogs.js ────────────────────────────────────────────────────── */

  function withLayer(fn) {
    var layer = host('modal-layer');
    try { return fn(layer.node); } finally { layer.remove(); }
  }

  test('frozen dialog: opens over a scrim, buttons run and close, keepOpen keeps it', function () {
    withLayer(function (layer) {
      var clicks = [], closed = 0;
      var handle = App.Dialogs.open({ title: 'Test', onClose: function () { closed += 1; },
        buttons: [{ label: 'Apply', keepOpen: true, onClick: function () { clicks.push('apply'); } },
                  { label: 'OK', primary: true, onClick: function () { clicks.push('ok'); } }],
        build: function (body) { body.appendChild(document.createTextNode('content')); } });
      T.eq(layer.querySelectorAll('.scrim').length, 1);
      T.ok(/content/.test(handle.body.textContent));
      var buttons = handle.dialog.querySelectorAll('.dlg-foot .btn');
      buttons[0].click();
      T.ok(handle.dialog.parentNode, 'Apply keeps it open');
      buttons[1].click();
      T.eq(clicks, ['apply', 'ok']);
      T.ok(!handle.dialog.parentNode && !layer.querySelector('.scrim'), 'OK closes it and its scrim');
      T.eq(closed, 1);
    });
  });

  test('frozen dialog: the ✕ and Escape close it', function () {
    withLayer(function (layer) {
      var a = App.Dialogs.open({ title: 'A' });
      a.dialog.querySelector('.dlg-x').click();
      T.ok(!a.dialog.parentNode);
      var b = App.Dialogs.open({ title: 'B' });
      key(document, 'Escape');
      T.ok(!b.dialog.parentNode);
      T.eq(layer.children.length, 0);
    });
  });

  test('frozen dialog: dragging the title bar moves it, the grip resizes it', function () {
    withLayer(function () {
      var d = App.Dialogs.open({ title: 'Drag', width: 400, height: 300 });
      var head = d.dialog.querySelector('.dlg-head');
      var left = parseFloat(d.dialog.style.left);
      mouse(head, 'mousedown', { clientX: 100, clientY: 100, button: 0 });
      mouse(document, 'mousemove', { clientX: 150, clientY: 130 });
      mouse(document, 'mouseup', {});
      T.near(parseFloat(d.dialog.style.left), left + 50, 1, 'moved with the pointer');
      var grip = d.dialog.querySelector('.dlg-resize');
      var width = parseFloat(d.dialog.style.width);
      mouse(grip, 'mousedown', { clientX: 0, clientY: 0, button: 0 });
      mouse(document, 'mousemove', { clientX: 60, clientY: 40 });
      mouse(document, 'mouseup', {});
      T.ok(parseFloat(d.dialog.style.width) > width, 'wider after dragging the grip');
      d.close();
    });
  });

  test('frozen dialogs: About, the command reference and "not implemented" each open', function () {
    withLayer(function (layer) {
      ['about', 'commandReference'].forEach(function (name) {
        App.Dialogs[name]();
        T.ok(layer.querySelector('.dialog'), name + ' opened');
        key(document, 'Escape');
      });
      App.Dialogs.notImplemented('Something');
      T.ok(/Something/.test(layer.textContent));
      key(document, 'Escape');
    });
  });

  /* ── js/explorer.js ───────────────────────────────────────────────────── */

  function treeRig(fn) {
    var tree = host('tree-model'), grid = host('grid-selection');
    var saved = { TREES: App.TREES, Viewport: App.Viewport, selectObject: App.selectObject,
                  state: App.state, Command: App.Command, OBJECT_PROPS: App.OBJECT_PROPS,
                  commitSelectionEdit: App.commitSelectionEdit };
    var ctx = { visible: { part_a: true }, selected: [], notes: [], commits: [] };
    App.TREES = { testing: [{ label: 'Parts', children: [
      { label: 'Part A', obj: 'part_a', eye: true, icon: 'cube' },
      { label: 'Part B', obj: 'part_b' }] }] };
    App.Viewport = { isVisible: function (k) { return ctx.visible[k] !== false; },
                     setVisible: function (k, on) { ctx.visible[k] = on; } };
    App.selectObject = function (k) { ctx.selected.push(k); };
    App.state = { selection: null, mode: 'testing' };
    App.Command = { note: function (t) { ctx.notes.push(t); }, ok: function () {},
                    write: function (k, t) { ctx.notes.push(k + ':' + t); } };
    App.commitSelectionEdit = function (key) { ctx.commits.push(key); };
    try { return fn(tree.node, grid.node, ctx); } finally {
      Object.assign(App, saved); tree.remove(); grid.remove();
    }
  }

  test('frozen explorer: the tree renders, folds, and selects what is clicked', function () {
    treeRig(function (tree, grid, ctx) {
      App.Explorer.mountTree('testing');
      var rows = tree.querySelectorAll('.tree-row');
      T.eq(rows.length, 3);
      var twisty = rows[0].querySelector('.tree-twisty');
      twisty.click();
      T.ok(tree.querySelector('.tree-children').classList.contains('collapsed'), 'folded');
      twisty.click();
      T.ok(!tree.querySelector('.tree-children').classList.contains('collapsed'), 'unfolded');
      rows[1].click();
      T.eq(ctx.selected, ['part_a']);
      App.Explorer.syncSelection('part_a');
      T.ok(rows[1].classList.contains('selected'));
    });
  });

  test("frozen explorer: a row's eye hides and shows its part", function () {
    treeRig(function (tree, grid, ctx) {
      App.Explorer.mountTree('testing');
      var eye = tree.querySelector('.tree-eye:not(.hidden-slot)');
      eye.click();
      T.eq(ctx.visible.part_a, false);
      T.ok(eye.classList.contains('off'));
      eye.click();
      T.eq(ctx.visible.part_a, true);
      T.ok(/Shown: Part A/.test(ctx.notes.join(' | ')));
    });
  });

  test('frozen explorer: the property grid edits through its editors and commits', function () {
    treeRig(function (tree, grid, ctx) {
      var value = 2;
      App.OBJECT_PROPS = { part_a: { title: 'Part A', groups: { General: [
        ['Size', '2.000', 'm', false, { kind: 'number', get: function () { return value; },
          set: function (v) { if (v <= 0) return 'Size must be positive.'; value = v; return null; } }],
        ['Kind', 'box', '', true],
        ['Active', true, '', true]] } } };
      App.Explorer.mountSelection('part_a');
      var input = grid.querySelector('input.cell-num');
      input.value = '3,5';
      input.dispatchEvent(new Event('change'));
      T.eq(value, 3.5, 'a decimal comma is read as a point');
      T.eq(ctx.commits, ['part_a']);
      input.value = '-1';
      input.dispatchEvent(new Event('change'));
      T.eq(value, 3.5, 'a refused value is not kept');
      T.eq(input.value, '3.500', 'and the box shows the value that is');
      T.ok(ctx.notes.some(function (n) { return /positive/.test(n); }));
      input.value = 'abc';
      input.dispatchEvent(new Event('change'));
      T.ok(ctx.notes.some(function (n) { return /not a number/.test(n); }));
      App.Explorer.mountSelection(null);
      T.ok(/No object selected/.test(grid.textContent));
    });
  });

  /* ── js/command.js ────────────────────────────────────────────────────── */

  function commandRig(fn) {
    return frozenCommand().then(function (Frozen) { return commandRigWith(Frozen, fn); });
  }

  function commandRigWith(FrozenCommand, fn) {
    var saved = { Command: App.Command, setMode: App.setMode, Viewport: App.Viewport,
                  runAction: App.runAction };
    var box = document.createElement('div');
    box.innerHTML = '<div class="cmd-tab active" data-tab="session"></div>'
      + '<div class="cmd-tab" data-tab="history"></div>'
      + '<div id="cmd-log"></div><div id="cmd-history" hidden></div>'
      + '<a id="cmd-ref" href="#"></a><input id="cmd-entry">';
    document.body.appendChild(box);
    var ctx = { modes: [], views: [], actions: [] };
    App.Command = FrozenCommand;
    App.setMode = function (m) { ctx.modes.push(m); };
    App.Viewport = { setView: function (v) { ctx.views.push(v); }, zoomFit: function () {} };
    App.runAction = function (a) { ctx.actions.push(a.action); };
    try {
      FrozenCommand.mount();
      return fn(box, ctx);
    } finally { box.remove(); Object.assign(App, saved); }
  }

  function enter(text) {
    var input = document.getElementById('cmd-entry');
    input.value = text;
    key(input, 'Enter');
  }

  function logLines() {
    return Array.prototype.map.call(document.querySelectorAll('#cmd-log .cmd-line'),
                                    function (l) { return l.textContent; });
  }

  test('frozen command: Enter runs a command; an empty line runs nothing', function () {
    return commandRig(function (box, ctx) {
      var before = logLines().length;
      enter('   ');
      T.eq(logLines().length, before, 'nothing written for an empty line');
      enter('gotomesh');
      T.eq(ctx.modes, ['mesh']);
      enter('view top');
      T.eq(ctx.views, ['top']);
      enter('view sideways');
      T.ok(/Usage: view/.test(logLines().join('\n')));
    });
  });

  test('frozen command: an unknown command says so', function () {
    return commandRig(function () {
      enter('frobnicate');
      T.ok(/Unknown command "frobnicate"/.test(logLines().join('\n')));
    });
  });

  test('frozen command: Up and Down walk the history, clear empties the log', function () {
    return commandRig(function () {
      enter('gotosoil');
      enter('gotomesh');
      var input = document.getElementById('cmd-entry');
      key(input, 'ArrowUp');
      T.eq(input.value, 'gotomesh');
      key(input, 'ArrowUp');
      T.eq(input.value, 'gotosoil');
      key(input, 'ArrowDown');
      T.eq(input.value, 'gotomesh');
      key(input, 'ArrowDown');
      T.eq(input.value, '');
      enter('clear');
      T.eq(logLines().length, 0);
    });
  });

  test('frozen command: the tabs switch between the session log and the history', function () {
    return commandRig(function (box, ctx) {
      box.querySelectorAll('.cmd-tab')[1].click();
      T.ok(document.getElementById('cmd-log').hidden);
      T.ok(!document.getElementById('cmd-history').hidden);
      document.getElementById('cmd-ref').click();
      T.eq(ctx.actions, ['cmdref'], 'the reference link opens the command reference');
    });
  });

})();
