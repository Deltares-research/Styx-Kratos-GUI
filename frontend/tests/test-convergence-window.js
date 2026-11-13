/* ══════════════════════════════════════════════════════════════════
   test-convergence-window.js — the Convergence window's Save button.

   The window is opened the way `results convergence` opens it, on a real log the
   server parsed (`fixtures/convergence-cases.js`), with the server's routes answered by
   a stand-in. Its Save button is the plot window's (`App.Picture.saveMenu`), and a
   pick saves the run the window shows, at once: nothing is asked of the server
   between the click and the save window, or the browser would not open that window.

   The live part -- the window following a run -- is in `tests/e2e/test_convergence.py`.
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
