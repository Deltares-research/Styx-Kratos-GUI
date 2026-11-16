/* ══════════════════════════════════════════════════════════════════
   test-convergence-window.js — the Convergence window: its Save button, and how it
   follows a run.

   The window is opened the way `results convergence` opens it, on a real log the
   server parsed (`fixtures/convergence-cases.js`), with the server's routes answered by
   a stand-in. Its Save button is the plot window's (`App.Picture.saveMenu`), and a
   pick saves the run the window shows, at once: nothing is asked of the server
   between the click and the save window, or the browser would not open that window.

   Calculate opens it and it follows the run, with the same stand-in. The same with a
   real server and Kratos stood in for is in `tests/e2e/test_convergence.py`.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var P = App.ConvergencePlot;
  var W = App.ConvergenceWindow;
  var CASES = window.CONVERGENCE_FIXTURE;
  var RUN = 'Staged_excavation_2026-09-22_16-28';
  var BASE = '/api/results/runs/' + RUN;

  function rig() {
    var saved = { Api: App.Api, Command: App.Command, Download: App.Download,
                  Picture: App.Picture, current: App.Results.current };
    var ctx = { calls: [], files: [], lines: [] };
    var layer = document.getElementById('modal-layer');
    var ownLayer = !layer;
    if (ownLayer) {
      layer = document.createElement('div');
      layer.id = 'modal-layer';
      document.body.appendChild(layer);
    }
    var answers = {};
    answers['/api/calculate/status'] = { running: false, run: null };
    answers[BASE + '/convergence'] = Object.assign(
      { run: RUN, running: false, failed_at: null, log: true },
      JSON.parse(JSON.stringify(CASES.iteration_limit.data)));
    App.Api = { base: '', get: function (path) {
      ctx.calls.push(path);
      return path in answers ? Promise.resolve(answers[path])
                             : Promise.reject(new Error('no ' + path));
    } };
    App.Command = { ok: function (t) { ctx.lines.push('ok:' + t); },
                    err: function (t) { ctx.lines.push('err:' + t); },
                    note: function (t) { ctx.lines.push('note:' + t); },
                    write: function () {} };
    App.Download = Object.assign({}, App.Download, {
      pickFile: function () { return Promise.resolve(null); },
      anchor: function (name, text) { ctx.files.push({ name: name, text: text }); }
    });
    App.Picture = Object.assign({}, App.Picture, {
      saveFigure: function (svg, name, kind) {
        ctx.files.push({ name: name, text: svg, kind: kind });
        return Promise.resolve(1);
      }
    });
    App.Results.current = function () { return RUN; };
    W.install();
    P.forget();

    ctx.layer = layer;
    ctx.restore = function () {
      W.close();
      P.forget();
      App.UI.closePopups(0);
      if (ownLayer) layer.remove();
      App.Api = saved.Api;
      App.Command = saved.Command;
      App.Download = saved.Download;
      App.Picture = saved.Picture;
      App.Results.current = saved.current;
    };
    return ctx;
  }

  function settle(ms) { return new Promise(function (r) { setTimeout(r, ms || 30); }); }

  function done(ctx, promise) {
    return Promise.resolve(promise).then(function () { ctx.restore(); },
                                         function (e) { ctx.restore(); throw e; });
  }

  function windowOf(ctx) { return ctx.layer.querySelector('.dlg-convergence'); }

  function button(dialog, label) {
    return Array.prototype.filter.call(dialog.querySelectorAll('button'), function (b) {
      return b.textContent === label;
    })[0];
  }

  function menuItem(label) {
    return Array.prototype.filter.call(document.querySelectorAll('#modal-layer .menu-item'),
                                       function (row) { return row.textContent.indexOf(label) === 0; })[0];
  }

  test('convergence window: one Save button offers PNG, PDF, SVG and CSV', function () {
    var ctx = rig();
    return done(ctx, P.command('').then(function () {
      var win = windowOf(ctx);
      T.ok(win, 'results convergence opens the window');
      var save = button(win, 'Save ▾');
      T.ok(save, 'beside Close');
      T.ok(button(win, 'Close'));
      T.eq(save.getAttribute('aria-haspopup'), 'menu');
      save.click();
      T.eq(save.getAttribute('aria-expanded'), 'true');
      T.eq(['PNG', 'PDF', 'SVG', 'CSV'].filter(menuItem).length, 4, 'every format is offered');
      var menu = document.querySelector('#modal-layer .menu');
      T.ok(win.compareDocumentPosition(menu) & Node.DOCUMENT_POSITION_FOLLOWING,
           'the menu is in front of the window');
      App.UI.closePopups(0);
    }));
  });

  test('convergence window: a pick saves the run it shows, with nothing asked first', function () {
    var ctx = rig();
    return done(ctx, P.command('').then(function () {
      var save = button(windowOf(ctx), 'Save ▾');
      ctx.calls = [];
      save.click();
      menuItem('CSV').click();
      save.click();
      menuItem('PNG').click();
      T.eq(ctx.calls, [], 'no request between the click and the save');
      return settle();
    }).then(function () {
      function named(ending) {
        return ctx.files.filter(function (f) { return f.name === RUN + '_convergence' + ending; })[0];
      }
      T.eq(ctx.files.length, 2);
      T.eq(named('.csv').text, CASES.iteration_limit.csv, 'the numbers kratos-cli writes');
      T.eq(named('.png').kind, 'png');
      T.ok(/^<svg/.test(named('.png').text), 'the figure on screen');
    }));
  });

  /* ── Following a run ────────────────────────────────────────────────────

     Calculate is pressed with the server stood in for: `/api/calculate` answers only
     when the test says so, and `/api/calculate/status` answers what `status()` says.
     The window asks once a second; here the clock is hurried, so a test does not wait
     for it. */

  function hurry() {
    var real = window.setTimeout;
    window.setTimeout = function (fn, ms) {
      return real(fn, ms === W.POLL_MS ? 0 : ms);
    };
    return function () { window.setTimeout = real; };
  }

  function live(ctx, status) {
    var get = App.Api.get;
    var asked = '/api/calculate/status';
    var convergence = BASE + '/convergence';
    ctx.running = true;
    App.Api.get = function (path) {
      if (path === asked) {
        var next = status();
        return next instanceof Error ? Promise.reject(next) : Promise.resolve(next);
      }
      if (path === convergence) {
        return get(path).then(function (data) {
          return Object.assign({}, data, { running: ctx.running });
        });
      }
      return get(path);
    };
    var answer = {};
    var calculated = new Promise(function (resolve, reject) {
      answer.resolve = resolve;
      answer.reject = reject;
    });
    App.Api.post = function () { return calculated; };
    var saved = { Export: App.Export, Results: App.Results };
    App.Export = { meshRequest: function () { return {}; } };
    App.Results = Object.assign({}, App.Results, {
      remember: function () { return Promise.resolve(); }
    });
    var slow = hurry();
    var restore = ctx.restore;
    ctx.restore = function () {
      slow();
      restore();
      App.Export = saved.Export;
      App.Results = saved.Results;
    };
    return answer;
  }

  function until(check, what) {
    var tries = 0;
    return new Promise(function (resolve, reject) {
      (function look() {
        if (check()) return resolve();
        if (++tries > 100) return reject(new Error('never: ' + what()));
        setTimeout(look, 10);
      })();
    });
  }

  function statusLine(ctx) {
    var win = windowOf(ctx);
    return win ? win.querySelector('.cv-line1').textContent : null;
  }

  test('convergence window: Calculate opens it, it follows the run and says how it ended', function () {
    var ctx = rig();
    var answers = [
      new Error('the server did not answer'),     // asked again a second later
      { running: true, run: null }                // still meshing
    ];
    var answer = live(ctx, function () {
      return answers.length ? answers.shift() : { running: true, run: RUN };
    });
    var calculated = App.Calculate.run();
    return done(ctx, until(function () { return W.state().open; },
                           function () { return 'the window opens'; })
      .then(function () {
        T.eq(statusLine(ctx), 'Meshing and writing the deck…');
        return until(function () { return W.state().phase === 'running'; },
                     function () { return 'running, but ' + W.state().phase; });
      }).then(function () {
        T.eq(W.state().run, RUN, 'the run the server named');
        return until(function () { return /^Running/.test(statusLine(ctx)); },
                     function () { return 'Running…, but ' + statusLine(ctx); });
      }).then(function () {
        T.ok(windowOf(ctx).querySelector('.cv-host svg'), 'the figure is drawn');
        ctx.running = false;
        answer.resolve({ ok: true, run: RUN, seconds: 12.5, outputs: [], directory: 'runs',
                         stats: { elements: 10, nodes: 20 }, warnings: [] });
        return calculated;
      }).then(function () {
        return until(function () { return statusLine(ctx) === 'Finished in 12.5 s'; },
                     function () { return 'Finished in 12.5 s, but ' + statusLine(ctx); });
      }).then(function () {
        T.eq(W.state().phase, 'finished');
        T.eq(W.state().open, true, 'the window stays open with the last figure');
      }));
  });

  test('convergence window: refused because another run goes on, it follows that run', function () {
    var ctx = rig();
    var refused = false;
    // While this page's request is open, Kratos works for nobody yet; once it is
    // refused, the run started elsewhere shows.
    var answer = live(ctx, function () {
      return { running: true, run: refused ? RUN : null };
    });
    var calculated = App.Calculate.run();
    return done(ctx, until(function () { return W.state().open; },
                           function () { return 'the window opens'; })
      .then(function () {
        var busy = new Error('busy');
        busy.status = 409;
        refused = true;
        answer.reject(busy);
        return calculated;
      }).then(function () {
        T.ok(ctx.lines.some(function (line) { return /earlier calculation/.test(line); }),
             'the command log says why');
        return until(function () { return W.state().run === RUN; },
                     function () { return 'the other run, but ' + W.state().run; });
      }).then(function () {
        T.eq(W.state().phase, 'running');
        ctx.running = false;
        return until(function () { return W.state().phase === 'shown'; },
                     function () { return 'shown, but ' + W.state().phase; });
      }).then(function () {
        T.ok(statusLine(ctx).indexOf(RUN) === 0, 'it names the run: ' + statusLine(ctx));
      }));
  });

  test('convergence window: closing it closes its Save menu', function () {
    var ctx = rig();
    return done(ctx, P.command('').then(function () {
      var win = windowOf(ctx);
      button(win, 'Save ▾').click();
      T.eq(document.querySelectorAll('#modal-layer .menu').length, 1);
      button(win, 'Close').click();
      T.eq(document.querySelectorAll('#modal-layer .menu').length, 0);
      T.eq(W.state().open, false);
    }));
  });

})();
