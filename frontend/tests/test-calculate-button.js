/* Calculate is greyed out until there is something to calculate, and while a run is
   under way the toolbar button is Stop and cannot start a second run (js/calculate.js
   `state`, js/patches.js `syncCalculate`). */

(function () {

  function project(overrides) {
    var base = { name: 'pit', dimension: 3, soil_body_keys: ['soil_L1'], custom_parts: [],
                 stages: [], deck: null, mesh: { element_size: 2.5, order: 1 } };
    Object.keys(overrides || {}).forEach(function (key) { base[key] = overrides[key]; });
    return base;
  }

  var SOIL = project();
  var BLANK = project({ name: 'blank', soil_body_keys: [] });

  /* ── The rule ─────────────────────────────────────────────────────────── */

  test('calculate state: a project with soil can be calculated', function () {
    T.eq(App.Calculate.state(SOIL, false), { ok: true, running: false, reason: '' });
  });

  test('calculate state: a run under way comes first, whatever the project', function () {
    var now = App.Calculate.state(BLANK, true);
    T.eq(now.ok, false);
    T.eq(now.running, true);
    T.ok(/^Calculating…/.test(now.reason), now.reason);
    T.eq(App.Calculate.state(null, true).running, true);
  });

  test('calculate state: no project yet is waited for, not refused for its content', function () {
    T.eq(App.Calculate.state(null, false),
         { ok: false, running: false, reason: 'Loading the project…' });
  });

  test('calculate state: nothing to mesh is refused in the words of the CLI and the server', function () {
    var now = App.Calculate.state(BLANK, false);
    T.eq(now.ok, false);
    T.eq(now.running, false);
    // core.session.nothing_to_mesh, capitalised as the start of a sentence.
    T.ok(now.reason.indexOf('The model has nothing to mesh: no soil layer and no solid.') === 0,
         now.reason);
    T.ok(/Modify soil layers…/.test(now.reason) && /soil volume/.test(now.reason),
         'and how to give it something: ' + now.reason);
    T.ok(/soil surface/.test(App.Calculate.state(project({ dimension: 2, soil_body_keys: [] }),
                                                 false).reason),
         'a section draws a soil surface, not a volume');
  });

  test('calculate state: a solid of its own is something to mesh', function () {
    var drawn = project({ soil_body_keys: [], custom_parts: [{ key: 'drawn_0' }] });
    T.eq(App.Calculate.state(drawn, false).ok, true);
  });

  test('calculate state: a deck case is run as it is, with no soil of its own', function () {
    var deck = project({ soil_body_keys: [], deck: { directory: 'C:\\decks\\a',
                                                     parameters: 'ProjectParameters.json' } });
    T.eq(App.Calculate.state(deck, false).ok, true);
  });

  test('calculate state: a stage tree with no single order is refused with its reason', function () {
    var branched = project({ stages: [
      { id: 'p0', name: 'Initial', parent: null },
      { id: 'p1', name: 'Dig A', parent: 'p0' },
      { id: 'p2', name: 'Dig B', parent: 'p0' }
    ] });
    var now = App.Calculate.state(branched, false);
    T.eq(now.ok, false);
    T.eq(now.reason, App.Stages.branchProblem(branched));
    T.ok(/"Dig A" and "Dig B"/.test(now.reason), now.reason);
  });

  /* ── The buttons ──────────────────────────────────────────────────────── */

  function calculateButton() {
    return document.querySelector('#maintoolbar .tbtn[data-action="calculate"]');
  }

  function railButton() {
    var tools = (App.RAILS.staged || []).filter(function (t) { return t !== '-'; });
    var at = -1;
    tools.forEach(function (t, i) { if (t.action === 'calculate') at = i; });
    return document.querySelectorAll('#toolrail .rail-btn')[at];
  }

  function menuItem() {
    var found = null;
    (App.MENUS || []).forEach(function (menu) {
      (menu.items || []).forEach(function (item) {
        if (item && item.action === 'calculate') found = item;
      });
    });
    return found;
  }

  function finished() {
    return { ok: true, returncode: 0, seconds: 3, directory: 'C:\\runs\\pit_1', run: 'pit_1',
             inputs: [], outputs: ['pit.post.res'], log: 'kratos.log', error: null,
             stats: { nodes: 10, elements: 4 }, warnings: [] };
  }

  /* Installs the overlay on a toolbar and a Staged construction rail, with `start` as
     the open project and a server that answers when the test says so. */
  function withButton(start, body) {
    var saved = { action: App.runAction, command: App.Command, project: App.PROJECT,
                  state: App.state, api: App.Api, results: App.Results,
                  exporter: App.Export, setMode: App.setMode };
    var ctx = { notes: [], posts: 0, pending: [] };
    function push(kind) { return function (t) { ctx.notes.push(kind + ':' + t); }; }
    App.runAction = function (item) { ctx.notes.push('frozen:' + (item && item.action)); };
    App.Command = { note: push('note'), ok: push('ok'), err: push('err'),
                    write: function () {}, run: function (t) { ctx.notes.push('frozen:' + t); } };
    App.state = { mode: 'staged', modelMode: '3d' };
    App.setMode = function () {};
    App.Export = { meshRequest: function () { return { element_size: 1 }; } };
    App.Results = { remember: function () { return Promise.resolve(); },
                    handleCommand: function () { return false; } };
    ctx.paths = [];
    App.Api = { post: function (path) {
      ctx.posts += 1;
      ctx.paths.push(path);
      return new Promise(function (resolve, reject) {
        ctx.pending.push({ resolve: resolve, reject: reject });
      });
    } };
    App.PROJECT = start;

    function restore() {
      App.runAction = saved.action; App.Command = saved.command; App.PROJECT = saved.project;
      App.state = saved.state; App.Api = saved.api; App.Results = saved.results;
      App.Export = saved.exporter; App.setMode = saved.setMode;
      if (ctx.dropLayer) ctx.dropLayer();
      App.LivePatches.resetForTests();
      App.LivePatches.syncCalculate();
    }

    /* Every request still open is answered first, so a test that failed half-way does
       not leave a run going for the tests after it. */
    function settled() {
      ctx.pending.forEach(function (open) { open.resolve(finished()); });
      return tick();
    }

    var outcome;
    try {
      App.LivePatches.install();
      App.Toolbars.mountMain();
      App.Toolbars.mountRail('staged');
      outcome = body(ctx);
    } catch (err) {
      if (!ctx.pending.length) { restore(); throw err; }
      return settled().then(function () { restore(); throw err; });
    }
    if (outcome && typeof outcome.then === 'function') {
      return outcome.then(function (v) { return settled().then(function () { restore(); return v; }); },
                          function (e) { return settled().then(function () { restore(); throw e; }); });
    }
    if (ctx.pending.length) return settled().then(function () { restore(); return outcome; });
    restore();
    return outcome;
  }

  function tick() { return new Promise(function (resolve) { setTimeout(resolve, 0); }); }

  function greyed(button) {
    return button.classList.contains('disabled')
        && button.getAttribute('aria-disabled') === 'true';
  }

  test('each rail button carries its action and its tip, so a script or a reader can name it', function () {
    withButton(SOIL, function () {
      T.eq(document.querySelector('#toolrail .rail-btn[data-action="calculate"]'), railButton());
      T.ok(/Calculate/.test(railButton().getAttribute('aria-label')),
           railButton().getAttribute('aria-label'));
      var tools = (App.RAILS.staged || []).filter(function (t) { return t !== '-'; });
      var buttons = document.querySelectorAll('#toolrail .rail-btn');
      tools.forEach(function (tool, i) {
        T.eq(buttons[i].getAttribute('data-tool'), tool.action || tool.icon);
      });
    });
  });

  test('with nothing to mesh, every Calculate is greyed out and its tip says why', function () {
    withButton(BLANK, function () {
      var reason = App.Calculate.state(BLANK, false).reason;
      T.ok(greyed(calculateButton()), 'the toolbar button');
      T.eq(String(App.LivePatches.calculateTip), reason, 'its tip is the reason');
      T.eq(menuItem().disabled, true, 'the Stages menu item');
      T.ok(railButton().classList.contains('disabled') && railButton().disabled,
           'the Staged construction rail tool');

      App.Toolbars.mountMain();
      T.ok(greyed(calculateButton()), 'and a remount of the toolbar keeps it greyed');
    });
  });

  test('a model with soil makes Calculate available again', function () {
    withButton(BLANK, function () {
      App.PROJECT = SOIL;
      App.LivePatches.syncCalculate();
      T.ok(!calculateButton().classList.contains('disabled'));
      T.eq(calculateButton().getAttribute('aria-disabled'), 'false');
      T.eq(String(App.LivePatches.calculateTip), App.LivePatches.CALCULATE_TIP);
      T.eq(menuItem().disabled, false);
      T.ok(!railButton().disabled);
    });
  });

  /* App.Model as the overlay finds it, reduced to what the rule reads: App.PROJECT.
     The harness puts the real one back after the test. */
  function modelStub(loaded) {
    return {
      apply: function (p) { App.PROJECT = p; return p; },
      load: function () {
        return Promise.resolve(loaded).then(function (p) { App.PROJECT = p; return p; });
      }
    };
  }

  test('a project adopted through App.Model.apply re-greys the button by itself', function () {
    App.Model = modelStub(null);
    withButton(SOIL, function () {
      T.ok(!greyed(calculateButton()));
      App.Model.apply(BLANK);
      T.ok(greyed(calculateButton()), 'greyed without anyone calling syncCalculate');
      App.Model.apply(SOIL);
      T.ok(!greyed(calculateButton()));
    });
  });

  test('the first load, which bypasses App.Model.apply, ungreys it as well', function () {
    App.Model = modelStub(SOIL);
    return withButton(null, function () {
      T.ok(greyed(calculateButton()), 'greyed while the project is on its way');
      T.eq(String(App.LivePatches.calculateTip), 'Loading the project…');
      return App.Model.load().then(tick).then(function () {
        T.ok(!greyed(calculateButton()));
      });
    });
  });

  test('the greyed button shows its reason as a tip on hover', function () {
    return withButton(BLANK, function () {
      calculateButton().dispatchEvent(new MouseEvent('mouseenter'));
      return new Promise(function (resolve) { setTimeout(resolve, 600); }).then(function () {
        var tips = document.querySelectorAll('.vp-tooltip');
        var text = tips.length ? tips[tips.length - 1].textContent : '';
        App.UI.hideTip();
        T.eq(text, App.Calculate.state(BLANK, false).reason);
      });
    });
  });

  test('a press with nothing to calculate is refused with the reason, not sent', function () {
    withButton(BLANK, function (ctx) {
      calculateButton().click();
      App.runAction({ action: 'calculate' });          // F9, a stale menu
      T.eq(ctx.posts, 0, 'nothing reached the server');
      var reason = App.Calculate.state(BLANK, false).reason;
      T.eq(ctx.notes.filter(function (n) { return n === 'note:' + reason; }).length, 2,
           ctx.notes.join(' | '));
    });
  });

  test('calculate in the command box is refused the same way', function () {
    return withButton(BLANK, function (ctx) {
      return Promise.resolve(App.Command.run('calculate')).then(function () {
        T.eq(ctx.posts, 0);
        T.ok(ctx.notes.indexOf('note:' + App.Calculate.state(BLANK, false).reason) >= 0,
             ctx.notes.join(' | '));
        T.ok(ctx.notes.indexOf('frozen:calculate') < 0, 'not the mockup answer');
      });
    });
  });

  /* `App.Calculate.askStop` stood in for, so a press does not open the dialog. */
  function withoutAsking(ctx) {
    var real = App.Calculate.askStop;
    ctx.asked = 0;
    App.Calculate.askStop = function () { ctx.asked += 1; return Promise.resolve(false); };
    return function () { App.Calculate.askStop = real; };
  }

  test('while a run is under way the button is Stop, and no press starts a second run', function () {
    return withButton(SOIL, function (ctx) {
      calculateButton().click();
      T.eq(ctx.posts, 1);
      T.eq(App.Calculate.running(), true);

      var button = calculateButton();
      T.ok(button.classList.contains('stop-calc'), 'the Stop look');
      T.ok(!button.classList.contains('calculating'));
      T.ok(!greyed(button), 'it can be pressed, to stop');
      T.eq(button.getAttribute('aria-busy'), 'true');
      T.eq(button.querySelector('span').textContent, 'Stop');
      T.eq(String(App.LivePatches.calculateTip), App.Calculate.STOP_TIP);
      T.eq(menuItem().label, 'Stop calculation');
      T.eq(menuItem().disabled, false);
      T.ok(railButton().disabled && railButton().classList.contains('calculating'),
           'the rail only spins');

      var back = withoutAsking(ctx);
      try {
        button.click();
        App.runAction(menuItem());
        App.runAction({ action: 'calculate' });          // F9
      } finally { back(); }
      T.eq(ctx.asked, 2, 'the button and the menu item ask to stop');
      T.eq(ctx.posts, 1, 'no second request');
      T.ok(ctx.notes.some(function (n) { return /^note:Calculating…/.test(n); }),
           'F9 is refused with the reason: ' + ctx.notes.join(' | '));

      App.Toolbars.mountMain();
      T.eq(calculateButton().querySelector('span').textContent, 'Stop',
           'a remount while it runs keeps the label');

      ctx.pending[0].resolve(finished());
      return tick().then(function () {
        var after = calculateButton();
        T.eq(App.Calculate.running(), false);
        T.ok(!after.classList.contains('calculating') && !greyed(after), 'live again');
        T.eq(after.getAttribute('aria-busy'), null);
        T.eq(after.querySelector('span').textContent, 'Calculate');
        T.eq(menuItem().label, 'Calculate');
        T.eq(menuItem().disabled, false);
        T.ok(!railButton().disabled && !railButton().classList.contains('calculating'));
      });
    });
  });

  test('a confirmed stop is sent, the button says Stopping…, and the run reports it', function () {
    return withButton(SOIL, function (ctx) {
      calculateButton().click();
      var stopped = App.Calculate.stop();
      T.eq(ctx.paths[1], '/api/calculate/stop');
      var button = calculateButton();
      T.eq(button.querySelector('span').textContent, 'Stopping…');
      T.ok(button.classList.contains('calculating') && greyed(button),
           'once asked, it spins and is not pressed again');
      T.eq(menuItem().label, 'Stopping…');
      T.eq(menuItem().disabled, true);
      ctx.pending[1].resolve({ stopped: true });
      return stopped.then(function (answer) {
        T.eq(answer, true);
        T.ok(ctx.notes.indexOf('note:Stopping Kratos…') >= 0, ctx.notes.join(' | '));
        var result = finished();
        result.ok = false;
        result.stopped = true;
        result.stage = { index: 2, of: 3, name: '2_Dig' };
        ctx.pending[0].resolve(result);
        return tick();
      }).then(function () {
        T.eq(App.Calculate.running(), false);
        T.eq(App.Calculate.stopping(), false);
        var after = calculateButton();
        T.ok(!after.classList.contains('stop-calc') && !after.classList.contains('calculating'));
        T.eq(after.querySelector('span').textContent, 'Calculate');
        T.ok(ctx.notes.some(function (n) {
          return /^note:Calculation stopped after 3 s, in stage 2 of 3/.test(n);
        }), ctx.notes.join(' | '));
        T.ok(!ctx.notes.some(function (n) { return /^err:/.test(n); }), 'not a failure');
      });
    });
  });

  /* The Stop question is a dialog, and a dialog needs the page's layer. Made after
     Calculate is pressed, so the Convergence window does not open and poll a server
     these tests do not stand in for. */
  function dialogLayer(ctx) {
    var layer = document.getElementById('modal-layer');
    var own = !layer;
    if (own) {
      layer = document.createElement('div');
      layer.id = 'modal-layer';
      document.body.appendChild(layer);
    }
    ctx.dropLayer = function () {
      Array.prototype.forEach.call(layer.querySelectorAll('.dlg-calc-stop .dlg-x'),
                                   function (x) { x.click(); });
      if (own) layer.remove();
    };
  }

  test('Stop asks first, and "Keep running" leaves the run alone', function () {
    return withButton(SOIL, function (ctx) {
      calculateButton().click();
      dialogLayer(ctx);
      calculateButton().click();
      var dialog = document.querySelector('#modal-layer .dlg-calc-stop');
      T.ok(dialog, 'a question, not a stop');
      T.eq(ctx.posts, 1);
      var keep = Array.prototype.filter.call(dialog.querySelectorAll('button'),
                                             function (b) { return b.textContent === 'Keep running'; })[0];
      keep.click();
      T.ok(!document.querySelector('#modal-layer .dlg-calc-stop'), 'the question is gone');
      T.eq(ctx.posts, 1, 'nothing was sent');
      T.eq(App.Calculate.stopping(), false);
      calculateButton().click();
      var again = document.querySelector('#modal-layer .dlg-calc-stop');
      Array.prototype.filter.call(again.querySelectorAll('button'),
                                  function (b) { return b.textContent === 'Stop calculation'; })[0].click();
      T.eq(ctx.paths[1], '/api/calculate/stop');
      ctx.pending[1].resolve({ stopped: true });
      ctx.pending[0].resolve(finished());
      return tick();
    });
  });

  test('calculate stop in the command box stops without asking', function () {
    return withButton(SOIL, function (ctx) {
      calculateButton().click();
      var typed = App.Command.run('calculate stop');
      T.ok(!document.querySelector('#modal-layer .dlg-calc-stop'), 'typed: no question');
      T.eq(ctx.paths[1], '/api/calculate/stop');
      ctx.pending[1].resolve({ stopped: true });
      return Promise.resolve(typed).then(function () {
        ctx.pending[0].resolve(finished());
        return tick();
      });
    });
  });

  test('calculate stop with nothing running says so', function () {
    return withButton(SOIL, function (ctx) {
      var typed = App.Command.run('calculate stop');
      T.eq(ctx.paths[0], '/api/calculate/stop', 'asked: a run of another tab is stopped too');
      ctx.pending[0].resolve({ stopped: false });
      return Promise.resolve(typed).then(function () {
        T.ok(ctx.notes.indexOf('note:No calculation is running.') >= 0, ctx.notes.join(' | '));
        T.eq(App.Calculate.running(), false);
      });
    });
  });

  test('a failed run clears the running look too', function () {
    return withButton(SOIL, function (ctx) {
      calculateButton().click();
      T.ok(calculateButton().classList.contains('stop-calc'));
      ctx.pending[0].reject(new Error('Cannot reach the model server'));
      return tick().then(function () {
        T.eq(App.Calculate.running(), false);
        T.ok(!calculateButton().classList.contains('calculating'));
        T.ok(!calculateButton().classList.contains('stop-calc'));
        T.ok(!greyed(calculateButton()));
        T.ok(ctx.notes.some(function (n) { return /^err:Calculation failed/.test(n); }));
      });
    });
  });

  test('a server still busy with an earlier run says so rather than "failed"', function () {
    return withButton(SOIL, function (ctx) {
      calculateButton().click();
      var busy = new Error('A calculation is already running.');
      busy.status = 409;
      ctx.pending[0].reject(busy);
      return tick().then(function () {
        T.ok(ctx.notes.some(function (n) {
          return /^err:Kratos is still running an earlier calculation/.test(n);
        }), ctx.notes.join(' | '));
        T.ok(!calculateButton().classList.contains('calculating'));
      });
    });
  });
})();
