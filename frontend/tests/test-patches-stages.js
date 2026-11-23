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
                 'INTERFACES', 'INTERFACE_SECTIONS', 'NORMAL_LOADS',
                 'viewportContextMenu', 'Menu'];

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
    // The shell's viewport menu (js/app.js), reduced to what it hands App.Menu: a
    // title row and one of its own.
    App.Menu = { openAt: function (items, x, y, onPick) {
      ctx.menu = { items: items, pick: onPick };
    } };
    App.viewportContextMenu = function (event, key) {
      App.Menu.openAt([{ title: key }, { label: 'Zoom to fit', action: 'zoomFit' }],
                      0, 0, function () {});
    };
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
     mechanical stage only), time integration and, for a mechanical stage, the
     convergence criterion -- and its Reset displacements box. */
  function stageControls(ctx) {
    var grid = ctx.layer.querySelector('.stages-overview .pgrid');
    var selects = grid.querySelectorAll('select');
    return { select: selects[0], selects: selects,
             reset: grid.querySelector('input.pgrid-check') };
  }

  function values(select) {
    return Array.prototype.map.call(select.options, function (o) { return o.value; });
  }

  test('stages window: a stage chooses its calculation type, stress initialisation, ' +
       'time integration and convergence criterion', function () {
    var ctx = rig(model());
    try {
      App.runAction({ action: 'stages' });
      var selects = stageControls(ctx).selects;
      T.eq(selects.length, 4);
      T.eq(values(selects[0]), ['mechanical', 'flow']);
      T.eq(values(selects[1]), ['K0', 'gravity', 'none']);
      T.eq(values(selects[2]), ['static', 'dynamic']);
      T.eq(values(selects[3]), ['residual_criterion', 'displacement_criterion']);
      T.eq(selects[1].value, model().stages[0].stress_initialisation);
    } finally { ctx.restore(); }
  });

  /* Gravity has no switch of its own: the initial stage's stress initialisation is it,
     and the row under it says which (`core.model.stages.gravity`). */
  test('stages window: the initial stage says whether its stresses bring gravity',
       function () {
    function gravityRow(stresses) {
      var project = JSON.parse(JSON.stringify(model()));
      project.stages[0].stress_initialisation = stresses;
      var ctx = rig(project);
      try {
        App.runAction({ action: 'stages' });
        var rows = ctx.layer.querySelectorAll('.stages-overview .pgrid .pgrid-row');
        var row = Array.prototype.filter.call(rows, function (r) {
          var key = r.querySelector('.pgrid-key');
          return key && key.textContent === 'Gravity';
        })[0];
        return row ? row.querySelector('.pgrid-val').textContent : null;
      } finally { ctx.restore(); }
    }
    T.eq(gravityRow('K0'), 'On: every body has its self weight');
    T.eq(gravityRow('gravity'), 'On: every body has its self weight');
    T.eq(gravityRow('none'), 'Off: no body has a self weight');
  });

  test('stages window: a later stage shows the calculation type and has no stress ' +
       'initialisation', function () {
    var ctx = rig(model());
    try {
      App.state.phase = model().stages[2].id;
      App.runAction({ action: 'stages' });
      var grid = ctx.layer.querySelector('.stages-overview .pgrid');
      T.eq(grid.querySelectorAll('select').length, 2,
           'only time integration and the convergence criterion to choose');
      T.ok(/from the initial stage/.test(grid.textContent));
      T.ok(!/Stress initialisation/.test(grid.textContent));
    } finally { ctx.restore(); }
  });

  test('stages window: flow is a calculation type of the initial stage, and choosing it ' +
       'is one PATCH that makes every stage a flow stage', function () {
    var ctx = rig(model());
    App.runAction({ action: 'stages' });
    var select = stageControls(ctx).select;
    T.ok(values(select).indexOf('flow') >= 0, 'the select offers flow');
    T.ok(!stageControls(ctx).reset.disabled, 'a mechanical stage can reset displacements');
    select.value = 'flow';
    select.dispatchEvent(new Event('change'));
    return done(ctx, new Promise(function (r) { setTimeout(r, 20); }).then(function () {
      T.eq(ctx.patches.length, 1);
      T.ok(ctx.patches[0].body.stages.every(function (stage) {
        return stage.calculation === 'flow' && stage.stress_initialisation === 'none' &&
          stage.convergence_criterion === 'water_pressure_criterion';
      }), 'not every stage became a flow stage');
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

  test('stages window: choosing a convergence criterion is one PATCH', function () {
    var ctx = rig(model());
    App.runAction({ action: 'stages' });
    var select = stageControls(ctx).selects[3];
    select.value = 'displacement_criterion';
    select.dispatchEvent(new Event('change'));
    return done(ctx, new Promise(function (r) { setTimeout(r, 20); }).then(function () {
      T.eq(ctx.patches.length, 1);
      T.eq(ctx.patches[0].body.stages[0].convergence_criterion, 'displacement_criterion');
    }));
  });

  test('stages window: a flow stage converges on the water pressure or the residual',
       function () {
    var flow = JSON.parse(JSON.stringify(model()));
    flow.stages.forEach(function (stage) {
      stage.calculation = 'flow';
      stage.stress_initialisation = 'none';
      stage.convergence_criterion = 'residual_criterion';
    });
    var ctx = rig(flow);
    try {
      App.runAction({ action: 'stages' });
      var grid = ctx.layer.querySelector('.stages-overview .pgrid');
      var selects = stageControls(ctx).selects;
      T.eq(selects.length, 3, 'calculation type, time integration, convergence criterion');
      T.eq(values(selects[2]), ['water_pressure_criterion', 'residual_criterion']);
      T.eq(selects[2].value, 'residual_criterion');
      T.ok(/Absolute tolerance/.test(grid.textContent));
    } finally { ctx.restore(); }
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
      T.eq(stageControls(ctx).selects.length, 3,
           'no stress initialisation row: calculation type, time integration, ' +
           'convergence criterion');
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
    T.eq(Array.prototype.map.call(buttons, function (b) { return b.getAttribute('data-action'); }),
         ['addStage', 'insertStage', 'duplicateStage', 'deleteStage']);
    T.eq(buttons[0].getAttribute('aria-label'), 'Add stage');
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

  test('stage list: a stage that is added, inserted or duplicated is selected', function () {
    var ctx = rig(model());
    var before = model().stages.map(function (stage) { return stage.id; });
    function fresh() {
      var last = ctx.patches[ctx.patches.length - 1].body.stages;
      return last.filter(function (stage) { return before.indexOf(stage.id) < 0; })
        .map(function (stage) { return stage.id; });
    }
    function press(index) {
      App.state.phase = model().stages[1].id;
      App.Explorer.mountPhases();
      ctx.dock.querySelectorAll('.stage-toolbar button.tbtn')[index].click();
      return new Promise(function (r) { setTimeout(r, 20); });
    }
    return done(ctx, [0, 1, 2].reduce(function (chain, index) {
      return chain.then(function () { return press(index); }).then(function () {
        T.eq(fresh().length, 1, 'one new stage');
        T.eq(App.state.phase, fresh()[0], 'button ' + index + ' selects the stage it made');
        App.Model.apply(JSON.parse(JSON.stringify(model())));
      });
    }, Promise.resolve()));
  });

  function windowButtons(ctx) {
    return ctx.layer.querySelectorAll('.dialog > .stage-toolbar button.tbtn');
  }

  function later() { return new Promise(function (r) { setTimeout(r, 20); }); }

  test('stages window: it has the panel\'s add, insert, duplicate and delete buttons',
       function () {
    var ctx = rig(model());
    try {
      App.runAction({ action: 'stages' });
      T.eq(Array.prototype.map.call(windowButtons(ctx), function (b) {
        return b.getAttribute('data-action'); }),
        ['addStage', 'insertStage', 'duplicateStage', 'deleteStage']);
      T.ok(Array.prototype.every.call(windowButtons(ctx), function (b) { return !b.disabled; }));
    } finally { ctx.restore(); }
  });

  test('stages window: a stage added there is listed and shown without closing it',
       function () {
    var ctx = rig(model());
    App.state.phase = model().stages[1].id;
    App.runAction({ action: 'stages' });
    windowButtons(ctx)[0].click();
    return done(ctx, later().then(function () {
      T.eq(ctx.patches.length, 1, 'one PATCH');
      var rows = windowRows(ctx);
      T.eq(rows.length, model().stages.length + 1, 'the window lists the new stage');
      var made = ctx.patches[0].body.stages[ctx.patches[0].body.stages.length - 1];
      T.eq(App.state.phase, made.id, 'and selects it');
      T.ok(rows[rows.length - 1].classList.contains('selected'));
      T.ok(ctx.layer.querySelector('.stages-overview'), 'the window is still open');
    }));
  });

  test('stages window: duplicate and delete act on the stage selected in the window',
       function () {
    var ctx = rig(model());
    App.runAction({ action: 'stages' });
    windowRows(ctx)[2].click();
    var gone = model().stages[2].id;
    windowButtons(ctx)[3].click();
    return done(ctx, later().then(function () {
      T.ok(ctx.patches[0].body.stages.every(function (stage) { return stage.id !== gone; }),
           'the stage selected in the window is deleted');
      T.eq(windowRows(ctx).length, model().stages.length - 1);
      windowButtons(ctx)[2].click();
      return later();
    }).then(function () {
      T.eq(ctx.patches[1].body.stages.length, model().stages.length, 'one duplicated');
    }));
  });

  test('stages window: a project with no stages gets its first one from the window',
       function () {
    var bare = JSON.parse(JSON.stringify(model()));
    bare.stages = [];
    var ctx = rig(bare);
    App.runAction({ action: 'stages' });
    T.eq(Array.prototype.map.call(windowButtons(ctx), function (b) { return b.disabled; }),
         [false, true, true, true], 'only Add stage, with nothing selected');
    windowButtons(ctx)[0].click();
    return done(ctx, later().then(function () {
      T.eq(windowRows(ctx).length, 1, 'the initial stage is listed');
    }));
  });

  test('stages window: a deck\'s stages have no buttons', function () {
    var ctx = rig(model());
    try {
      App.PROJECT.deck = { parameters: 'ProjectParameters_stage1.json' };
      App.runAction({ action: 'stages' });
      T.eq(windowButtons(ctx).length, 0);
    } finally { ctx.restore(); }
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

  test('staged mode: clicking a part only selects it', function () {
    var ctx = rig(model());
    var stage = model().stages[model().stages.length - 1];
    App.state.phase = stage.id;
    var key = App.Stages.stageableKeys(App.PROJECT)[0];
    App.selectObject(key, 'viewport');
    return done(ctx, new Promise(function (r) { setTimeout(r, 20); }).then(function () {
      T.eq(ctx.selected, [key], 'selected');
      T.eq(ctx.patches.length, 0, 'a click is not an edit of the stage');
    }));
  });

  function menuRow(ctx, action) {
    return (ctx.menu.items || []).filter(function (item) {
      return item && item.action === action;
    })[0];
  }

  test('staged mode: the right-click menu activates and deactivates in this stage alone',
       function () {
    var ctx = rig(model());
    var list = App.Stages.order(App.PROJECT);
    var stage = list[list.length - 2], after = list[list.length - 1];
    App.state.phase = stage.id;
    var key = App.Stages.activeParts(App.PROJECT, stage.id)[0];
    var stillAfter = App.Stages.activeParts(App.PROJECT, after.id).indexOf(key) >= 0;

    App.viewportContextMenu({ clientX: 0, clientY: 0 }, key);
    T.ok(ctx.menu.items[0].title, 'the title row stays first');
    T.ok(menuRow(ctx, 'stageActivate').disabled, 'already active: Activate is greyed');
    var off = menuRow(ctx, 'stageDeactivate');
    T.ok(off && !off.disabled, 'Deactivate is offered');
    T.ok(off.label.indexOf(stage.name) >= 0, off.label);
    ctx.menu.pick(off);
    return done(ctx, new Promise(function (r) { setTimeout(r, 20); }).then(function () {
      T.eq(ctx.patches.length, 1, 'one PATCH of the sequence');
      var sent = { stageable_parts: App.PROJECT.stageable_parts,
                   stages: ctx.patches[0].body.stages };
      T.ok(App.Stages.activeParts(sent, stage.id).indexOf(key) < 0, 'off in this stage');
      T.eq(App.Stages.activeParts(sent, after.id).indexOf(key) >= 0, stillAfter,
           'the next stage keeps what it had');
      T.ok(ctx.lines.some(function (l) { return /deactivated in/.test(l); }),
           ctx.lines.join(' | '));
    }));
  });

  test('the viewport menu switches a part in the stage in Soil, Structures and Flow ' +
       'conditions', function () {
    var ctx = rig(model());
    try {
      ['soil', 'structures', 'flow'].forEach(function (mode) {
        App.state.mode = mode;
        ctx.menu = null;
        App.viewportContextMenu({ clientX: 0, clientY: 0 },
                                App.Stages.stageableKeys(App.PROJECT)[0]);
        T.ok(menuRow(ctx, 'stageActivate') && menuRow(ctx, 'stageDeactivate'), mode);
      });
    } finally { ctx.restore(); }
  });

  test('in Mesh and Results the viewport menu has no stage rows', function () {
    /* One mesh serves every stage; Results shows a run, not the project's stages. */
    var ctx = rig(model());
    try {
      ['mesh', 'results'].forEach(function (mode) {
        App.state.mode = mode;
        ctx.menu = null;
        App.viewportContextMenu({ clientX: 0, clientY: 0 },
                                App.Stages.stageableKeys(App.PROJECT)[0]);
        T.ok(!menuRow(ctx, 'stageActivate') && !menuRow(ctx, 'stageDeactivate'), mode);
      });
    } finally { ctx.restore(); }
  });

  /* ── The expert solver settings ──────────────────────────────────────── */

  function expert(ctx) {
    return ctx.layer.querySelector('.stages-overview .pgrid-expert');
  }

  function expertRow(ctx, label) {
    var rows = expert(ctx).querySelectorAll('.pgrid-row');
    return Array.prototype.filter.call(rows, function (r) {
      return r.querySelector('.pgrid-key').textContent === label;
    })[0] || null;
  }

  test('stages window: the expert settings start closed, and open on a click', function () {
    var ctx = rig(model());
    try {
      App.runAction({ action: 'stages' });
      var section = expert(ctx);
      T.ok(section, 'the grid has an expert settings section');
      T.ok(!section.querySelector('.pgrid-row'), 'closed, it holds no rows');
      section.querySelector('.pgrid-toggle').click();
      T.ok(App.state.stageExpert, 'it stays open for the session');
      T.eq(expertRow(ctx, 'Strategy').querySelector('select').value, 'newton_raphson');
      var linear = expertRow(ctx, 'Linear solver').querySelector('select');
      T.ok(linear, 'Newton-Raphson offers the linear solver');
      T.eq(linear.value, 'LinearSolversApplication.sparse_lu');
      T.ok(!expertRow(ctx, 'Newmark beta'), 'a static stage has no time scheme');
    } finally { ctx.restore(); }
  });

  test('stages window: a dynamic stage shows its Rayleigh damping among its own ' +
       'settings, not the expert ones', function () {
    var dynamic = JSON.parse(JSON.stringify(model()));
    dynamic.stages.forEach(function (stage) {
      stage.calculation = 'mechanical';
      stage.time_integration = 'dynamic';
    });
    var ctx = rig(dynamic);
    App.state.stageExpert = true;
    try {
      App.runAction({ action: 'stages' });
      var grid = ctx.layer.querySelector('.stages-overview .pgrid');
      var groups = Array.prototype.map.call(grid.querySelectorAll(':scope > .pgrid-group'),
                                            function (g) { return g.textContent; });
      T.ok(groups.indexOf('Damping') === 1, 'right after General: ' + groups.join(', '));
      T.ok(!expertRow(ctx, 'Rayleigh mass damping'), 'not an expert setting');
      T.ok(expertRow(ctx, 'Newmark beta'), 'the Newmark coefficients still are');
    } finally { ctx.restore(); }
  });

  test('stages window: choosing a strategy is one PATCH of the stage\'s own expert ' +
       'settings', function () {
    var ctx = rig(model());
    App.state.stageExpert = true;
    App.runAction({ action: 'stages' });
    var select = expertRow(ctx, 'Strategy').querySelector('select');
    select.value = 'quasi_newton';
    select.dispatchEvent(new Event('change'));
    return done(ctx, new Promise(function (r) { setTimeout(r, 20); }).then(function () {
      T.eq(ctx.patches.length, 1, 'one PATCH of the sequence');
      var first = ctx.patches[0].body.stages[0];
      T.eq(first.solver_settings, { strategy_type: 'quasi_newton' });
      var linear = expertRow(ctx, 'Linear solver');
      T.ok(!linear.querySelector('select'),
           'the dialog redraws, and the quasi-Newton strategy fixes the linear solver');
      T.ok(/Sparse LU/.test(linear.textContent), linear.textContent);
    }));
  });

  test('stages window: a changed expert setting says so, and its button puts the ' +
       'default back', function () {
    var changed = JSON.parse(JSON.stringify(model()));
    changed.stages[0].solver_settings = { min_iterations: 3 };
    var ctx = rig(changed);
    App.state.stageExpert = true;
    App.runAction({ action: 'stages' });
    T.ok(/1 changed/.test(expert(ctx).querySelector('.pgrid-toggle').textContent));
    var row = expertRow(ctx, 'Min iterations');
    T.ok(row.querySelector('.pgrid-key.changed'), 'marked as changed');
    row.querySelector('button.pgrid-reset').click();
    return done(ctx, new Promise(function (r) { setTimeout(r, 20); }).then(function () {
      T.eq(ctx.patches[0].body.stages[0].solver_settings, {});
    }));
  });

  /* ── The stage list beside the mode tabs ─────────────────────────────── */

  function picker() { return document.getElementById('stage-picker'); }

  /* The tab bar as the app draws it, with the stage list put in by install(). */
  function mountTabs() {
    App.Toolbars.mountModes();
    return document.getElementById('modetabs');
  }

  test('stage list: beside Soil, Structures and Flow conditions, one row per stage', function () {
    var ctx = rig(model());
    try {
      var bar = mountTabs();
      var select = picker();
      T.ok(select, 'the stage list is in the tab bar');
      var group = select.closest('.mode-group');
      var before = group.previousElementSibling.previousElementSibling;
      T.ok(before.querySelector('.mode-tab[data-mode="flow"]'),
           'it follows the group that holds Flow conditions');
      T.ok(group.nextElementSibling, 'the Calculation group comes after it');
      T.eq(select.options.length, model().stages.length);
      T.eq(select.value, App.Stages.selectedId(App.PROJECT, App.state.phase));
      App.Toolbars.mountModes();
      T.eq(bar.querySelectorAll('#stage-picker').length, 1, 'drawn once per mount');
    } finally { ctx.restore(); }
  });

  test('stage list: the staged tab is called Calculation settings', function () {
    var ctx = rig(model());
    try {
      var bar = mountTabs();
      T.eq(bar.querySelector('.mode-tab[data-mode="staged"]').textContent.trim(),
           'Calculation settings');
    } finally { ctx.restore(); }
  });

  test('stage list: choosing a stage selects it for every tab, and the viewport follows', function () {
    var ctx = rig(model());
    try {
      mountTabs();
      App.setMode('soil');
      var last = model().stages[model().stages.length - 1];
      var select = picker();
      select.value = last.id;
      select.dispatchEvent(new Event('change'));
      T.eq(App.state.phase, last.id);
      T.ok(ctx.visibility > 0, 'the viewport was asked to redraw the stage');
      T.ok(ctx.lines.indexOf('note:Current stage: ' + last.name) >= 0);
      App.setMode('structures');
      T.eq(picker().value, last.id, 'the next tab shows the same stage');
    } finally { ctx.restore(); }
  });

  test('stage list: a stage chosen in the stages panel is chosen in the list too', function () {
    var ctx = rig(model());
    try {
      mountTabs();
      App.setMode('staged');
      App.Explorer.mountPhases();
      var rows = ctx.dock.querySelectorAll('.phase-row');
      rows[rows.length - 1].click();
      T.eq(picker().value, App.state.phase);
    } finally { ctx.restore(); }
  });

  test('stage list: greyed in the Mesh tab, where one mesh serves every stage', function () {
    var ctx = rig(model());
    try {
      mountTabs();
      App.setMode('mesh');
      T.ok(picker().disabled);
      T.ok(/mesh/i.test(picker().title));
      App.setMode('flow');
      T.ok(!picker().disabled, 'back in a model tab it can be used again');
    } finally { ctx.restore(); }
  });

  test('stage list: in Results it chooses the stage of the run', function () {
    var ctx = rig(model());
    var results = App.Results;
    var typed = [];
    App.Results = Object.assign({}, results, {
      state: function () {
        return { run: 'run_1', stage: 1, stages: [
          { index: 1, stage: 'Initial stage', results: true },
          { index: 2, stage: 'Dig', results: true }] };
      },
      projectStage: function () { return null; },
      handleCommand: function (text) { typed.push(text); return null; }
    });
    try {
      mountTabs();
      App.setMode('results');
      var select = picker();
      T.eq(select.options.length, 2);
      T.eq(select.value, '1');
      select.value = '2';
      select.dispatchEvent(new Event('change'));
      T.eq(typed, ['results stage 2']);
    } finally { App.Results = results; ctx.restore(); }
  });

  test('stage list: Results opens on the stage chosen in the other tabs', function () {
    var ctx = rig(model());
    var results = App.Results;
    var order = App.Stages.order(App.PROJECT);
    var typed = [];
    App.Results = Object.assign({}, results, {
      state: function () {
        return { run: 'run_1', stage: order.length, stages: order.map(function (s, i) {
          return { index: i + 1, stage: s.name, results: true };
        }) };
      },
      // The run is of this project, and shows its last stage.
      projectStage: function () { return { stage: order[order.length - 1].id }; },
      handleCommand: function (text) { typed.push(text); return null; }
    });
    try {
      mountTabs();
      App.state.phase = order[1].id;
      App.setMode('soil');
      App.setMode('results');
      T.eq(typed, ['results stage 2']);
      typed = [];
      App.setMode('results');
      T.eq(typed, [], 'staying in Results does not choose again');
    } finally { App.Results = results; ctx.restore(); }
  });

  /* ── Calculation settings: the Stages explorer alone ────────────────── */

  function dockRig() {
    var dock = document.createElement('div');
    dock.id = 'dock';
    ['panel-model', 'split-dock1', 'panel-selection', 'split-dock2', 'panel-phases']
      .forEach(function (id) {
        var node = document.createElement('section');
        node.id = id;
        if (/^panel/.test(id)) node.className = 'dock-panel';
        dock.appendChild(node);
      });
    document.body.appendChild(dock);
    return dock;
  }

  test('calculation settings: the Stages explorer is the whole dock', function () {
    var ctx = rig(model());
    var dock = dockRig();
    try {
      App.setMode('staged');
      T.ok(dock.classList.contains('stages-only'));
      ['panel-model', 'split-dock1', 'panel-selection', 'split-dock2'].forEach(function (id) {
        T.ok(document.getElementById(id).hidden, id + ' is still shown');
      });
      T.ok(!document.getElementById('panel-phases').hidden);
      App.setMode('soil');
      T.ok(!dock.classList.contains('stages-only'));
      ['panel-model', 'split-dock1', 'panel-selection'].forEach(function (id) {
        T.ok(!document.getElementById(id).hidden, id + ' did not come back');
      });
    } finally { dock.remove(); ctx.restore(); }
  });

})();
