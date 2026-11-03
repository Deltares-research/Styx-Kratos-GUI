/* The Stages window and the docked stage list (frontend/js/patches.js).

   Both are DOM built through the real App.UI / App.Dialogs, opened the way the app opens
   them (`App.runAction({action: 'stages'})`, and `mountLiveStages` behind the dock), on
   the recorded test model -- seven stages, parts switched off and on along the way.
   What reaches the server is recorded as the PATCH it would be. */

(function () {

  /* Everything App.Model.apply and LivePatches.install write, put back afterwards so
     the suites that run later see the page as it was. */
  var GLOBALS = ['Api', 'Command', 'Viewport', 'Model', 'PROJECT', 'state', 'runAction',
                 'selectObject', 'setMode', 'LAYERS', 'MATERIALS', 'LOADS',
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
    App.state = { mode: 'staged', stage: null };
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
        next.stages = body.stages;
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
      applyStageVisibility: function () { ctx.visibility = (ctx.visibility || 0) + 1; }
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
    return Array.prototype.slice.call(ctx.layer.querySelectorAll('.stages-overview .phase-row'));
  }

  function done(ctx, promise) {
    return Promise.resolve(promise).then(function () { ctx.restore(); },
                                         function (e) { ctx.restore(); throw e; });
  }

  test('stages window: one row per stage, with the properties and the log of the selected one', function () {
    var ctx = rig(model());
    try {
      App.runAction({ action: 'stages' });
      var rows = windowRows(ctx);
      T.eq(rows.length, model().stages.length);
      var right = ctx.layer.querySelector('.stages-overview > div:nth-child(2)');
      T.ok(/Staged construction/.test(right.textContent), 'what the stage changes is listed');
      T.ok(/Log info for last calculation/.test(
        ctx.layer.querySelector('.stages-overview-log').textContent));
    } finally { ctx.restore(); }
  });

  test('stages window: clicking a stage selects it, and the viewport follows', function () {
    var ctx = rig(model());
    try {
      App.runAction({ action: 'stages' });
      var last = windowRows(ctx)[model().stages.length - 1];
      last.click();
      T.eq(App.state.phase, model().stages[model().stages.length - 1].id);
      T.ok(ctx.visibility > 0, 'the viewport was asked to redraw the stage');
      T.ok(windowRows(ctx)[model().stages.length - 1].classList.contains('selected'));
    } finally { ctx.restore(); }
  });

  test('stages window: a part switched off can be switched back on from the list', function () {
    var ctx = rig(model());
    App.runAction({ action: 'stages' });
    windowRows(ctx)[model().stages.length - 1].click();
    var button = Array.prototype.filter.call(ctx.layer.querySelectorAll('button'), function (b) {
      return b.textContent === 'Switch on';
    })[0];
    T.ok(button, 'the last stage has dug something away');
    button.click();
    return done(ctx, Promise.resolve().then(function () {
      T.eq(ctx.patches.length, 1);
      T.eq(ctx.patches[0].path, '/api/project/stages');
      T.ok(ctx.lines.some(function (l) { return /switched on in/.test(l); }), ctx.lines.join(' | '));
    }));
  });

  test("stages window: renaming a stage writes the sequence with the new name", function () {
    var ctx = rig(model());
    App.runAction({ action: 'stages' });
    var input = ctx.layer.querySelector('.stages-overview .pgrid input.cell-input');
    T.ok(input, 'the name is editable');
    input.value = 'Renamed stage';
    input.dispatchEvent(new Event('change'));
    return done(ctx, new Promise(function (r) { setTimeout(r, 20); }).then(function () {
      T.eq(ctx.patches.length, 1);
      T.ok(ctx.patches[0].body.stages.some(function (p) { return p.name === 'Renamed stage'; }));
    }));
  });

  /* The selects of the selected stage -- calculation type, stress initialisation (a
     mechanical stage only) and time integration -- and its Reset displacements box. */
  function stageControls(ctx) {
    var grid = ctx.layer.querySelector('.stages-overview .pgrid');
    var selects = grid.querySelectorAll('select');
    return { select: selects[0], selects: selects,
             reset: grid.querySelector('input.pgrid-check') };
  }

  function values(select) {
    return Array.prototype.map.call(select.options, function (o) { return o.value; });
  }

  test('stages window: a stage chooses its calculation type, stress initialisation and ' +
       'time integration', function () {
    var ctx = rig(model());
    try {
      App.runAction({ action: 'stages' });
      var selects = stageControls(ctx).selects;
      T.eq(selects.length, 3);
      T.eq(values(selects[0]), ['mechanical', 'flow']);
      T.eq(values(selects[1]), ['K0', 'gravity', 'none']);
      T.eq(values(selects[2]), ['static', 'dynamic']);
      T.eq(selects[1].value, model().stages[0].stress_initialisation);
    } finally { ctx.restore(); }
  });

  test('stages window: flow is a calculation type, and choosing it is one PATCH that ' +
       'drops the stress initialisation', function () {
    var ctx = rig(model());
    App.runAction({ action: 'stages' });
    var select = stageControls(ctx).select;
    T.ok(values(select).indexOf('flow') >= 0, 'the select offers flow');
    T.ok(!stageControls(ctx).reset.disabled, 'a mechanical stage can reset displacements');
    select.value = 'flow';
    select.dispatchEvent(new Event('change'));
    return done(ctx, new Promise(function (r) { setTimeout(r, 20); }).then(function () {
      T.eq(ctx.patches.length, 1);
      T.eq(ctx.patches[0].body.stages[0].calculation, 'flow');
      T.eq(ctx.patches[0].body.stages[0].stress_initialisation, 'none');
    }));
  });

  test('stages window: choosing dynamic time integration is one PATCH', function () {
    var ctx = rig(model());
    App.runAction({ action: 'stages' });
    var select = stageControls(ctx).selects[2];
    select.value = 'dynamic';
    select.dispatchEvent(new Event('change'));
    return done(ctx, new Promise(function (r) { setTimeout(r, 20); }).then(function () {
      T.eq(ctx.patches.length, 1);
      T.eq(ctx.patches[0].body.stages[0].time_integration, 'dynamic');
    }));
  });

  test('stages window: a flow stage has no stress initialisation and greys out Reset ' +
       'displacements', function () {
    var flow = JSON.parse(JSON.stringify(model()));
    flow.stages.forEach(function (stage) {
      stage.calculation = 'flow';
      stage.stress_initialisation = 'none';
      stage.reset_displacements = true;
    });
    var ctx = rig(flow);
    try {
      App.runAction({ action: 'stages' });
      T.eq(stageControls(ctx).selects.length, 2, 'no stress initialisation row');
      var reset = stageControls(ctx).reset;
      T.ok(reset.disabled, 'the box cannot be changed');
      T.ok(/no displacements/.test(reset.title), 'its tooltip says why');
      reset.click();
      T.eq(ctx.patches.length, 0, 'nothing is sent');
    } finally { ctx.restore(); }
  });

  test('stages window: a project with no stages says how to make them', function () {
    var bare = JSON.parse(JSON.stringify(model()));
    bare.stages = [];
    var ctx = rig(bare);
    try {
      App.runAction({ action: 'stages' });
      T.ok(/no stages yet/.test(ctx.layer.textContent));
    } finally { ctx.restore(); }
  });

  /* The dock is `App.Explorer.mountPhases`, which patches.js replaces on install with
     its own -- the frozen one lists js/data.js's mockup stages. */

  test('stage list: the dock lists every stage, and a click selects one', function () {
    var ctx = rig(model());
    try {
      App.Explorer.mountPhases();
      var rows = ctx.dock.querySelectorAll('.phase-row');
      T.eq(rows.length, model().stages.length);
      rows[2].click();
      T.eq(App.state.phase, model().stages[2].id);
      T.ok(ctx.dock.querySelectorAll('.phase-row')[2].classList.contains('selected'),
           'redrawn with the new selection');
    } finally { ctx.restore(); }
  });

  test('stage list: the toolbar adds and deletes stages through one PATCH each', function () {
    var ctx = rig(model());
    App.state.phase = model().stages[1].id;
    App.Explorer.mountPhases();
    var buttons = ctx.dock.querySelectorAll('.stage-toolbar button.tbtn');
    T.eq(buttons.length, 4, 'add, insert, duplicate, delete');
    buttons[0].click();
    return done(ctx, new Promise(function (r) { setTimeout(r, 20); }).then(function () {
      T.eq(ctx.patches[0].body.stages.length, model().stages.length + 1, 'one added');
      App.state.phase = model().stages[1].id;
      App.Explorer.mountPhases();
      ctx.dock.querySelectorAll('.stage-toolbar button.tbtn')[3].click();
      return new Promise(function (r) { setTimeout(r, 20); });
    }).then(function () {
      T.eq(ctx.patches.length, 2);
      T.ok(ctx.patches[1].body.stages.every(function (p) { return p.id !== model().stages[1].id; }),
           'the selected stage is gone');
    }));
  });

  test("stage list: the dock's Stages… button opens the window", function () {
    var ctx = rig(model());
    try {
      App.Explorer.mountPhases();
      var open = Array.prototype.filter.call(ctx.dock.querySelectorAll('button'), function (b) {
        return b.textContent === 'Stages…'; })[0];
      open.click();
      T.eq(windowRows(ctx).length, model().stages.length);
    } finally { ctx.restore(); }
  });

  test('stage list: with no stages there are no defaults to create, only Add stage',
       function () {
    var bare = JSON.parse(JSON.stringify(model()));
    bare.stages = [];
    var ctx = rig(bare);
    try {
      App.Explorer.mountPhases();
      T.ok(!Array.prototype.some.call(ctx.dock.querySelectorAll('button'), function (b) {
        return /default/i.test(b.textContent);
      }), 'no button to create default stages');
      T.ok(/Add stage/.test(ctx.dock.textContent), 'the hint says how to start');
    } finally { ctx.restore(); }
  });

  test('staged mode: clicking a part switches it for the selected stage', function () {
    var ctx = rig(model());
    var stage = model().stages[model().stages.length - 1];
    App.state.phase = stage.id;
    var key = App.Stages.stageableKeys(App.PROJECT)[0];
    App.selectObject(key, 'viewport');
    return done(ctx, new Promise(function (r) { setTimeout(r, 20); }).then(function () {
      T.eq(ctx.patches.length, 1, 'one PATCH of the sequence');
      T.ok(ctx.lines.some(function (l) { return /switched (on|off) in/.test(l); }),
           ctx.lines.join(' | '));
    }));
  });

})();
