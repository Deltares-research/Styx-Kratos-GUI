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

   Closing the window does not stop the run; it only stops the asking. Its Stop button
   does, after asking (`App.Calculate.askStop`): it is there while a run goes on, also
   one this page found going on, since this is where a run that goes wrong is seen.
   Modeless, like the plot window: it is read beside the model.

   The figure fills the window, and grows with it when the window is made bigger by its
   corner. With two stages or more, a slider under the status line shows one stage
   alone, or all of them (`results convergence stage N | all` does the same): with many
   stages, the early ones are too narrow to read.

   The figure and the words are `App.ConvergencePlot`'s, tested headless. This file is
   the DOM around them, tested in the browser (`frontend/tests/test-convergence-window.js`
   and `tests/e2e/test_convergence.py`).

   Its Save button saves what it shows, as `results convergence png | pdf | svg | csv`
   from the command box does while it is open.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.ConvergenceWindow = (function () {

  var POLL_MS = 1000;
  var SIZE = { width: 640, height: 660 };
  var STATUS = '/api/calculate/status';

  var win = null;           // the dialog handle while the window is open
  var phase = 'idle';       // idle, meshing, running, finished, stopped, failed, shown
  var calculating = false;  // this page's Calculate request is open
  var run = null;           // the run being followed or shown
  var ending = null;        // { seconds, stage, stopped } of the run this page started
  var generation = 0;       // bumped to stop a loop that is waiting for an answer
  var timer = null;
  var installed = false;
  var watcher = null;       // the ResizeObserver that redraws the figure to its size

  /* ── The window ───────────────────────────────────────────────────────── */

  function open() {
    if (win) return win;
    // No window without the page's dialog layer: a test page that drives Calculate
    // without one gets none, and nothing is asked of the server for it either.
    if (!App.Dialogs || !App.Dialogs.open || !document.getElementById('modal-layer')) {
      return null;
    }
    var saveMenu = null;
    var handle = App.Dialogs.open({
      title: 'Convergence',
      width: SIZE.width, height: SIZE.height,
      buttons: [
        { label: 'Save ▾', keepOpen: true, onClick: function () { saveMenu.toggle(); } },
        { label: 'Stop calculation', keepOpen: true,
          onClick: function () { if (App.Calculate) App.Calculate.askStop(); } },
        { label: 'Close', primary: true }
      ],
      onClose: function () {
        if (saveMenu) saveMenu.close();
        if (watcher) watcher.disconnect();
        watcher = null;
        win = null;
        stop();
      }
    });
    handle.dialog.classList.add('dlg-convergence');
    var footButtons = handle.dialog.querySelectorAll('.dlg-foot .btn');
    footButtons[1].classList.add('cv-stop');
    footButtons[1].hidden = true;
    // The same Save button as the plot window: a pick runs `results convergence png`
    // and the like, which saves what this window shows (see `App.ConvergencePlot`).
    // Before any run is shown there is nothing to save, and the command says so.
    saveMenu = App.Picture.saveMenu(handle.dialog.querySelector('.dlg-foot .btn'),
                                    function (format) {
                                      App.ConvergencePlot.command(format);
                                    });

    // Modeless: the scrim belongs to a modal dialog, and would take the viewport's
    // pointer events with it (see the plot window in patches.js).
    var layer = document.getElementById('modal-layer');
    var scrims = layer ? layer.querySelectorAll('.scrim') : [];
    if (scrims.length) {
      var scrim = scrims[scrims.length - 1];
      if (scrim.parentNode) scrim.parentNode.removeChild(scrim);
    }

    // Bottom right of the viewport: left of the dock, so the model tree stays in view,
    // and above the status bar. Without room beside the dock, at the page's right edge.
    var box = handle.dialog;
    var w = box.offsetWidth || SIZE.width, h = box.offsetHeight || SIZE.height;
    box.style.left = Math.max(8, rightEdge(w) - w) + 'px';
    box.style.top = Math.max(8, window.innerHeight - h - 48) + 'px';

    win = handle;
    render();
    return handle;
  }

  function close() {
    if (win) win.close();
  }

  /* Where the window's right side goes: 8 px left of the dock, when the dock is shown
     and leaves room for a window `width` wide beside it. */
  function rightEdge(width) {
    var dock = document.getElementById('dock');
    var left = dock && dock.offsetWidth ? dock.getBoundingClientRect().left : 0;
    return left - 8 >= width + 8 ? left - 8 : window.innerWidth - 16;
  }

  /* What the status line says, in two lines: what is going on, and the last numbers. */
  function words() {
    var P = App.ConvergencePlot;
    var data = P.state().data;
    var iterations = data && data.iterations ? data.iterations.length : 0;
    var last = data ? P.lastText(data) : '';
    var where = data ? P.stageText(data) : '';
    if (phase === 'meshing') {
      return [stopping() ? 'Stopping…' : 'Meshing and writing the deck…', ''];
    }
    if (phase === 'running') {
      if (stopping()) return ['Stopping Kratos…', last];
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
    var byUser = !!((ending && ending.stopped) || data.stopped);
    var stopped = failed ? (byUser ? 'Stopped by the user in stage ' : 'Stopped in stage ')
                           + failed.index + ' of ' + failed.of
                           + (failed.name ? ', ' + P.tidy(failed.name) : '')
                : byUser ? 'Stopped by the user' : '';
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

  function stopping() {
    return !!(App.Calculate && App.Calculate.stopping && App.Calculate.stopping());
  }

  /* The Stop button: there while a run goes on, "Stopping…" once asked. */
  function stopButton() {
    var button = win.dialog.querySelector('.cv-stop');
    if (!button) return;
    var data = App.ConvergencePlot.state().data;
    var live = phase === 'meshing' || phase === 'running'
               || (phase === 'shown' && !!(data && data.running));
    button.hidden = !live;
    button.disabled = stopping();
    button.textContent = stopping() ? 'Stopping…' : 'Stop calculation';
  }

  /* The window's parts, made once: a render while a run is followed (once a second)
     changes their contents, so the slider is not rebuilt under the pointer. */
  function build() {
    win.body.innerHTML = '<div class="cv-window">'
      + '<div class="cv-status" role="status" aria-live="polite">'
      + '<div class="cv-line1"></div><div class="cv-line2"></div></div>'
      + '<label class="cv-stages" hidden><span class="cv-stages-label">Show</span>'
      + '<input type="range" class="cv-stage-slider" min="0" max="1" step="1" value="0">'
      + '<span class="cv-stage-name"></span></label>'
      + '<div class="cv-host"></div></div>';
    var slider = win.body.querySelector('.cv-stage-slider');
    slider.addEventListener('input', function () {
      var stages = stagesOf(App.ConvergencePlot.state().data);
      var at = Number(slider.value);
      App.ConvergencePlot.setStage(at > 0 && stages[at - 1] ? stages[at - 1].index : null);
    });
    var host = win.body.querySelector('.cv-host');
    if (window.ResizeObserver) {
      var size = '';
      watcher = new ResizeObserver(function () {
        var now = host.clientWidth + 'x' + host.clientHeight;
        if (now !== size) { size = now; figure(); }
      });
      watcher.observe(host);
    }
  }

  /* The stages the slider steps through: those with a number. */
  function stagesOf(data) {
    return ((data && data.stages) || []).filter(function (stage) {
      return stage.index !== null && stage.index !== undefined;
    });
  }

  function part(selector) { return win.body.querySelector(selector); }

  /* The slider: 0 is every stage, 1 the first stage alone, and so on. */
  function slider(data, shown) {
    var stages = stagesOf(data);
    var at = 0;
    stages.forEach(function (stage, i) { if (stage.index === shown) at = i + 1; });
    part('.cv-stages').hidden = stages.length < 2;
    var input = part('.cv-stage-slider');
    input.max = String(Math.max(1, stages.length));
    if (Number(input.value) !== at) input.value = String(at);
    var stage = at ? stages[at - 1] : null;
    var name = stage ? 'Stage ' + stage.index + (stage.of ? ' of ' + stage.of : '')
                       + (stage.name ? ', ' + App.ConvergencePlot.tidy(stage.name) : '')
                     : 'All stages';
    part('.cv-stage-name').textContent = name;
    input.setAttribute('aria-valuetext', name);
    input.setAttribute('aria-label', 'Stages shown');
  }

  /* The figure, as tall as the window leaves room for. */
  function figure() {
    if (!win || !App.ConvergencePlot) return;
    var host = part('.cv-host');
    if (!host) return;
    var view = App.ConvergencePlot.state();
    if (!view.data && phase !== 'running' && phase !== 'meshing') {
      host.innerHTML = '';
      return;
    }
    var w = host.clientWidth, h = host.clientHeight;
    var height = w > 0 && h > 0 ? App.ConvergencePlot.FIG.width * h / w : undefined;
    host.innerHTML = App.ConvergencePlot.svg(view.data || {},
                                             { stage: view.stage, height: height });
  }

  function render() {
    if (!win || !App.ConvergencePlot) return;
    if (!part('.cv-window')) build();
    var lines = words();
    part('.cv-line1').textContent = lines[0];
    part('.cv-line2').textContent = lines[1];
    var view = App.ConvergencePlot.state();
    slider(view.data, view.stage);
    stopButton();
    figure();
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
    ending = { seconds: result.seconds, stage: result.stage || null,
               stopped: !!result.stopped };
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
    if (App.Calculate && App.Calculate.onStop) App.Calculate.onStop(render);
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
