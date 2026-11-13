/* ══════════════════════════════════════════════════════════════════
   convergence-window.js — the Convergence window, live while Kratos runs.

   When Calculate is pressed, this small window opens at the bottom right of the page
   and shows how the solver converges as Kratos works: the figure of
   `convergence-plot.js`, and above it a status line in words and numbers, so the
   figure is not the only way to read it. When the run ends, the window stays open with
   the last figure and says how the run ended. `results convergence`, the Results
   menu's Convergence… and the Results rail open the same window on any run later.

   How it follows a run:

   *   While the server meshes and writes the deck, it says "Meshing…".
   *   Then it asks the server once a second: first which run Kratos works in
       (`/api/calculate/status`), then that run's convergence. The next question goes
       only after the last answer came back, so slow answers cannot pile up.
   *   When Calculate's request comes back, it asks one last time and says
       "Finished in 12.3 s" or "Stopped in stage 3 of 7".
   *   A page that loads while a run goes on -- a reload, a second tab -- opens the
       window and follows that run too.

   Closing the window does not stop the run; it only stops the asking. Modeless, like
   the plot window: it is read beside the model.

   The figure and the words are `App.ConvergencePlot`'s, tested headless. This file is
   the DOM around them, tested in the browser (`tests/e2e/test_flows.py`).
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.ConvergenceWindow = (function () {

  var POLL_MS = 1000;
  var SIZE = { width: 560, height: 480 };
  var STATUS = '/api/calculate/status';

  var win = null;           // the dialog handle while the window is open
  var phase = 'idle';       // idle, meshing, running, finished, stopped, failed, shown
  var calculating = false;  // this page's Calculate request is open
  var run = null;           // the run being followed or shown
  var ending = null;        // { seconds, stage } of the run this page started
  var generation = 0;       // bumped to stop a loop that is waiting for an answer
  var timer = null;
  var installed = false;

  function esc(text) {
    return String(text === undefined || text === null ? '' : text)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /* ── The window ───────────────────────────────────────────────────────── */

  function open() {
    if (win) return win;
    // No window without the page's dialog layer: a test page that drives Calculate
    // without one gets none, and nothing is asked of the server for it either.
    if (!App.Dialogs || !App.Dialogs.open || !document.getElementById('modal-layer')) {
      return null;
    }
    var handle = App.Dialogs.open({
      title: 'Convergence',
      width: SIZE.width, height: SIZE.height,
      buttons: [{ label: 'Close', primary: true }],
      onClose: function () { win = null; stop(); }
    });
    handle.dialog.classList.add('dlg-convergence');

    // Modeless: the scrim belongs to a modal dialog, and would take the viewport's
    // pointer events with it (see the plot window in patches.js).
    var layer = document.getElementById('modal-layer');
    var scrims = layer ? layer.querySelectorAll('.scrim') : [];
    if (scrims.length) {
      var scrim = scrims[scrims.length - 1];
      if (scrim.parentNode) scrim.parentNode.removeChild(scrim);
    }

    // Bottom right, clear of the model tree on the left and of the status bar.
    var box = handle.dialog;
    var w = box.offsetWidth || SIZE.width, h = box.offsetHeight || SIZE.height;
    box.style.left = Math.max(8, window.innerWidth - w - 16) + 'px';
    box.style.top = Math.max(8, window.innerHeight - h - 48) + 'px';

    win = handle;
    render();
    return handle;
  }

  function close() {
    if (win) win.close();
  }

  /* What the status line says, in two lines: what is going on, and the last numbers. */
  function words() {
    var P = App.ConvergencePlot;
    var data = P.state().data;
    var iterations = data && data.iterations ? data.iterations.length : 0;
    var last = data ? P.lastText(data) : '';
    var where = data ? P.stageText(data) : '';
    if (phase === 'meshing') return ['Meshing and writing the deck…', ''];
    if (phase === 'running') {
      if (!data) return ['Starting Kratos…', ''];
      return ['Running' + (where ? ': ' + where : '…'),
              last || 'Waiting for the first iteration…'];
    }
    if (phase === 'failed') {
      return ['The calculation did not run. The command log says why.', last];
    }
    if (!data) return ['', ''];
    var none = iterations ? '' : (data.stages && data.stages.length ? P.NO_RESIDUALS
                                  : data.log ? 'Kratos did not start solving.'
                                             : 'The run has no log.');
    var failed = (ending && ending.stage) || data.failed_at;
    var stopped = failed ? 'Stopped in stage ' + failed.index + ' of ' + failed.of
                           + (failed.name ? ', ' + P.tidy(failed.name) : '') : '';
    if (phase === 'finished' || phase === 'stopped') {
      var took = ending && ending.seconds !== undefined ? ' in ' + ending.seconds + ' s' : '';
      return [stopped ? stopped + took.replace(' in ', ' after ') : 'Finished' + took,
              none || last];
    }
    // Shown: a run opened from the menu or the command box.
    if (data.running) return ['Running' + (where ? ': ' + where : '…') + ' — ' + data.run,
                              last || 'Waiting for the first iteration…'];
    return [data.run + (stopped ? ' — ' + stopped.charAt(0).toLowerCase() + stopped.slice(1)
                                : ' — finished'), none || last];
  }

  function render() {
    if (!win || !App.ConvergencePlot) return;
    var lines = words();
    var data = App.ConvergencePlot.state().data;
    win.body.innerHTML = '<div class="cv-window">'
      + '<div class="cv-status" role="status" aria-live="polite">'
      + '<div class="cv-line1">' + esc(lines[0]) + '</div>'
      + '<div class="cv-line2">' + esc(lines[1]) + '</div></div>'
      + '<div class="cv-host">' + (data || phase === 'running' || phase === 'meshing'
        ? App.ConvergencePlot.svg(data || {}) : '') + '</div></div>';
  }

  /* ── Following a run ──────────────────────────────────────────────────── */

  function stop() {
    generation += 1;
    if (timer) clearTimeout(timer);
    timer = null;
  }

  /* Ask, once a second, until the run is over. `fromPage` is true for a run this page
     started (its own request says when it is over) and false for one it found going on
     (the run's data says so). */
  function follow(fromPage) {
    stop();
    var mine = generation;
    function again() {
      if (mine !== generation || !win) return;
      timer = setTimeout(ask, POLL_MS);
    }
    function ask() {
      timer = null;
      if (mine !== generation || !win) return;
      var which = run ? Promise.resolve({ running: true, run: run })
                      : App.Api.get(STATUS);
      which.then(function (status) {
        if (mine !== generation) return null;
        if (status && status.run) run = status.run;
        if (!run) {
          if (!fromPage && !(status && status.running)) { phase = 'idle'; render(); return null; }
          if (phase !== 'meshing') render();
          again();
          return null;
        }
        if (phase === 'meshing') phase = 'running';
        return App.ConvergencePlot.load(run, true).then(function (data) {
          if (mine !== generation) return;
          if (data) App.ConvergencePlot.show(run, data);
          if (fromPage ? calculating : !data || data.running) {
            again();
          } else if (!fromPage) {
            phase = 'shown';
            render();
          }
        });
      }).catch(function () { again(); });
    }
    ask();
  }

  /* ── What starts and ends it ──────────────────────────────────────────── */

  /* Calculate was pressed (`running` true), or its request came back with `result`. */
  function onCalculate(running, result) {
    if (running) {
      calculating = true;
      run = null;
      ending = null;
      phase = 'meshing';
      if (App.ConvergencePlot) App.ConvergencePlot.forget();
      open();
      render();
      follow(true);
      return;
    }
    calculating = false;
    stop();
    if (!result || !result.run) {
      phase = 'failed';
      render();
      // Refused because a run started elsewhere is going on (409): follow that one.
      followRunInProgress();
      return;
    }
    run = result.run;
    ending = { seconds: result.seconds, stage: result.stage || null };
    phase = result.ok ? 'finished' : 'stopped';
    if (!win) return;                     // closed during the run: it stays closed
    App.ConvergencePlot.load(run, true).then(function (data) {
      if (data && run === result.run) App.ConvergencePlot.show(run, data);
      else render();
    });
  }

  /* `results convergence` asked for the window, or a load changed what is shown. */
  function onPlot(event) {
    if (event && event.open) {
      var data = App.ConvergencePlot.state().data;
      if (!calculating) {
        run = data ? data.run : null;
        ending = null;
        phase = 'shown';
      }
      open();
      if (data && data.running && !calculating) follow(false);
    }
    render();
  }

  /* A page that loads during a run follows it. */
  function followRunInProgress() {
    if (!App.Api || !App.Api.get) return Promise.resolve();
    return App.Api.get(STATUS).then(function (status) {
      if (!status || !status.running || calculating) return;
      run = status.run || null;
      ending = null;
      phase = 'running';
      open();
      follow(false);
    }, function () { /* an older server, or none: nothing to follow */ });
  }

  function install() {
    if (installed) return;
    installed = true;
    if (App.Calculate && App.Calculate.onChange) App.Calculate.onChange(onCalculate);
    if (App.ConvergencePlot && App.ConvergencePlot.onChange) {
      App.ConvergencePlot.onChange(onPlot);
    }
    followRunInProgress();
  }

  return {
    install: install, open: open, close: close, render: render,
    state: function () { return { open: !!win, phase: phase, run: run }; },
    POLL_MS: POLL_MS
  };
})();
