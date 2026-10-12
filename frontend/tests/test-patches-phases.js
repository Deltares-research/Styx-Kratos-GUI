/* The Phases window and the docked phase list (frontend/js/patches.js).

   Both are DOM built through the real App.UI / App.Dialogs, opened the way the app opens
   them (`App.runAction({action: 'phases'})`, and `mountLivePhases` behind the dock), on
   the recorded test model -- seven phases, parts switched off and on along the way.
   What reaches the server is recorded as the PATCH it would be. */

(function () {

  /* Everything App.Model.apply and LivePatches.install write, put back afterwards so
     the suites that run later see the page as it was. */
  var GLOBALS = ['Api', 'Command', 'Viewport', 'Model', 'PROJECT', 'state', 'runAction',
                 'selectObject', 'setMode', 'LAYERS', 'MATERIALS', 'BOREHOLES', 'LOADS',
                 'BEAMS', 'BEAM_SECTIONS', 'PANEL_SECTIONS', 'ANCHORS', 'ANCHOR_SECTIONS',
                 'INTERFACES', 'INTERFACE_SECTIONS', 'NORMAL_LOADS'];

  function rig(project) {
    var saved = { props: App.OBJECT_PROPS, trees: {} };
    GLOBALS.forEach(function (k) { saved[k] = App[k]; });
    Object.keys(App.TREES || {}).forEach(function (m) { saved.trees[m] = App.TREES[m]; });
    var ctx = { patches: [], posts: [], lines: [], applied: 0, selected: [] };
    var layer = document.createElement('div');
    layer.id = 'modal-layer';
    var dock = document.createElement('div');
    dock.id = 'list-phases';
    document.body.appendChild(layer);
    document.body.appendChild(dock);
    App.OBJECT_PROPS = Object.assign({}, App.OBJECT_PROPS);
    App.state = { mode: 'staged', phase: null };
    App.Model.apply(JSON.parse(JSON.stringify(project)));
    var applyModel = App.Model.apply;
    App.Model = Object.assign({}, App.Model, {
      apply: function (p) { ctx.applied += 1; return applyModel(p); },
      load: function () { return Promise.resolve(); }
    });
    App.Api = {
      patch: function (path, body) {
        ctx.patches.push({ path: path, body: body });
        var next = JSON.parse(JSON.stringify(App.PROJECT));
        next.phases = body.phases;
        return Promise.resolve({ project: next });
      },
      post: function (path, body) {
        ctx.posts.push({ path: path, body: body });
        var next = JSON.parse(JSON.stringify(project));
        return Promise.resolve({ project: next });
      }
    };
    App.Command = { ok: function (t) { ctx.lines.push('ok:' + t); },
                    err: function (t) { ctx.lines.push('err:' + t); },
                    note: function (t) { ctx.lines.push('note:' + t); }, write: function () {},
                    run: function () {} };
    App.Viewport = Object.assign({}, App.Viewport, {
      refresh: function () { return Promise.resolve(); },
      applyPhaseVisibility: function () { ctx.visibility = (ctx.visibility || 0) + 1; }
    });
    // The shell's own functions, which install() wraps -- js/app.js is not on this page.
    App.runAction = function () {};
    App.selectObject = function (key) { ctx.selected.push(key); };
    App.setMode = function (mode) { App.state.mode = mode; };
    App.LivePatches.resetForTests();
    App.LivePatches.install();
    ctx.layer = layer;
    ctx.dock = dock;
    ctx.restore = function () {
      layer.remove();
      dock.remove();
      App.LivePatches.resetForTests();
      Object.keys(saved).forEach(function (k) {
        if (k !== 'props' && k !== 'trees') App[k] = saved[k];
      });
      App.OBJECT_PROPS = saved.props;
      Object.keys(saved.trees).forEach(function (m) { App.TREES[m] = saved.trees[m]; });
      App.Model.rebuildDerived();
    };
    return ctx;
  }

  function model() { return window.VIEWPORT_PAYLOADS.project; }

  function windowRows(ctx) {
    return Array.prototype.slice.call(ctx.layer.querySelectorAll('.phases-overview .phase-row'));
  }

  function done(ctx, promise) {
    return Promise.resolve(promise).then(function () { ctx.restore(); },
                                         function (e) { ctx.restore(); throw e; });
  }

  test('phases window: one row per phase, with the properties and the log of the selected one', function () {
    var ctx = rig(model());
    try {
      App.runAction({ action: 'phases' });
      var rows = windowRows(ctx);
      T.eq(rows.length, model().phases.length);
      var right = ctx.layer.querySelector('.phases-overview > div:nth-child(2)');
      T.ok(/Staged construction/.test(right.textContent), 'what the phase changes is listed');
      T.ok(/Log info for last calculation/.test(
        ctx.layer.querySelector('.phases-overview-log').textContent));
    } finally { ctx.restore(); }
  });

  test('phases window: clicking a phase selects it, and the viewport follows', function () {
    var ctx = rig(model());
    try {
      App.runAction({ action: 'phases' });
      var last = windowRows(ctx)[model().phases.length - 1];
      last.click();
      T.eq(App.state.phase, model().phases[model().phases.length - 1].id);
      T.ok(ctx.visibility > 0, 'the viewport was asked to redraw the phase');
      T.ok(windowRows(ctx)[model().phases.length - 1].classList.contains('selected'));
    } finally { ctx.restore(); }
  });

  test('phases window: a part switched off can be switched back on from the list', function () {
    var ctx = rig(model());
    App.runAction({ action: 'phases' });
    windowRows(ctx)[model().phases.length - 1].click();
    var button = Array.prototype.filter.call(ctx.layer.querySelectorAll('button'), function (b) {
      return b.textContent === 'Switch on';
    })[0];
    T.ok(button, 'the last phase has dug something away');
    button.click();
    return done(ctx, Promise.resolve().then(function () {
      T.eq(ctx.patches.length, 1);
      T.eq(ctx.patches[0].path, '/api/project/phases');
      T.ok(ctx.lines.some(function (l) { return /switched on in/.test(l); }), ctx.lines.join(' | '));
    }));
  });

  test("phases window: renaming a phase writes the sequence with the new name", function () {
    var ctx = rig(model());
    App.runAction({ action: 'phases' });
    var input = ctx.layer.querySelector('.phases-overview .pgrid input.cell-input');
    T.ok(input, 'the name is editable');
    input.value = 'Renamed phase';
    input.dispatchEvent(new Event('change'));
    return done(ctx, new Promise(function (r) { setTimeout(r, 20); }).then(function () {
      T.eq(ctx.patches.length, 1);
      T.ok(ctx.patches[0].body.phases.some(function (p) { return p.name === 'Renamed phase'; }));
    }));
  });

  test('phases window: a project with no phases says how to make them', function () {
    var bare = JSON.parse(JSON.stringify(model()));
    bare.phases = [];
    var ctx = rig(bare);
    try {
      App.runAction({ action: 'phases' });
      T.ok(/no phases yet/.test(ctx.layer.textContent));
    } finally { ctx.restore(); }
  });

  /* The dock is `App.Explorer.mountPhases`, which patches.js replaces on install with
     its own -- the frozen one lists js/data.js's mockup phases. */

  test('phase list: the dock lists every phase, and a click selects one', function () {
    var ctx = rig(model());
    try {
      App.Explorer.mountPhases();
      var rows = ctx.dock.querySelectorAll('.phase-row');
      T.eq(rows.length, model().phases.length);
      rows[2].click();
      T.eq(App.state.phase, model().phases[2].id);
      T.ok(ctx.dock.querySelectorAll('.phase-row')[2].classList.contains('selected'),
           'redrawn with the new selection');
    } finally { ctx.restore(); }
  });

  test('phase list: the toolbar adds and deletes phases through one PATCH each', function () {
    var ctx = rig(model());
    App.state.phase = model().phases[1].id;
    App.Explorer.mountPhases();
    var buttons = ctx.dock.querySelectorAll('.phase-toolbar button.tbtn');
    T.eq(buttons.length, 4, 'add, insert, duplicate, delete');
    buttons[0].click();
    return done(ctx, new Promise(function (r) { setTimeout(r, 20); }).then(function () {
      T.eq(ctx.patches[0].body.phases.length, model().phases.length + 1, 'one added');
      App.state.phase = model().phases[1].id;
      App.Explorer.mountPhases();
      ctx.dock.querySelectorAll('.phase-toolbar button.tbtn')[3].click();
      return new Promise(function (r) { setTimeout(r, 20); });
    }).then(function () {
      T.eq(ctx.patches.length, 2);
      T.ok(ctx.patches[1].body.phases.every(function (p) { return p.id !== model().phases[1].id; }),
           'the selected phase is gone');
    }));
  });

  test("phase list: the dock's Phases… button opens the window", function () {
    var ctx = rig(model());
    try {
      App.Explorer.mountPhases();
      var open = Array.prototype.filter.call(ctx.dock.querySelectorAll('button'), function (b) {
        return b.textContent === 'Phases…'; })[0];
      open.click();
      T.eq(windowRows(ctx).length, model().phases.length);
    } finally { ctx.restore(); }
  });

  test('phase list: with no phases the dock offers to create the defaults', function () {
    var bare = JSON.parse(JSON.stringify(model()));
    bare.phases = [];
    var ctx = rig(bare);
    App.Explorer.mountPhases();
    var button = Array.prototype.filter.call(ctx.dock.querySelectorAll('button'), function (b) {
      return /default/i.test(b.textContent);
    })[0];
    T.ok(button, 'a button to create the default phases');
    button.click();
    return done(ctx, new Promise(function (r) { setTimeout(r, 20); }).then(function () {
      T.eq(ctx.posts[0].path, '/api/project/phases/defaults');
    }));
  });

  test('staged mode: clicking a part switches it for the selected phase', function () {
    var ctx = rig(model());
    var phase = model().phases[model().phases.length - 1];
    App.state.phase = phase.id;
    var key = App.Phases.stageableKeys(App.PROJECT)[0];
    App.selectObject(key, 'viewport');
    return done(ctx, new Promise(function (r) { setTimeout(r, 20); }).then(function () {
      T.eq(ctx.patches.length, 1, 'one PATCH of the sequence');
      T.ok(ctx.lines.some(function (l) { return /switched (on|off) in/.test(l); }),
           ctx.lines.join(' | '));
    }));
  });

})();
