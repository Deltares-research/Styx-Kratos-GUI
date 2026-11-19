/* ══════════════════════════════════════════════════════════════════
   calculate.js — Calculate (F9): hand the deck to Kratos and say what happened.

   The whole feature is one request. The server meshes the project, writes the same
   three files the export writes, and runs them through Kratos' orchestrator in a
   directory of its own; this asks for that and turns the answer into command-log lines.
   A model meshed already (Generate mesh, or the last calculation) is not meshed again:
   the server writes the deck from that mesh (`core/geometry/meshing.py` mesh_project).
   Without a mesh, the log says first that the run meshes the model with the global
   mesh settings (`noMesh`).

   Nothing else happens in the app. The viewport does not change, nothing is read back
   and no mode is entered: a calculation produces files, and this says where they are.
   The one thing it does hand on is the run's *name*, to `App.Results`, so that what
   was just written is the run `results` opens without anyone having to find it again.
   Reading the results themselves into the viewport is the next feature, not this one.

   Two things it deliberately does not do:

   *   it does not reuse the export's download path. A download is for taking the deck
       elsewhere; this one runs where the files are written, and the user never sees a
       save window because nothing is being saved to a place they chose.
   *   it does not poll. The request stays open for as long as the solver runs. The
       progress is the Convergence window's (`convergence-window.js`): it hears from
       `onChange` when a run starts and ends, and asks the server once a second how
       the solver converges in between.

   A run can be stopped (`stop`): while it runs, the toolbar's Calculate button is a
   Stop button, the Convergence window has one too, and `calculate stop` in the command
   box does the same. `askStop` asks first, because a click on the button a moment after
   Calculate would otherwise end the run at once. The server kills Kratos, and the open
   Calculate request then answers with `stopped`: what the run wrote stays, and the
   model is not touched.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Calculate = (function () {

  var inFlight = false;
  var stopping = false;     // a stop was asked, and the run has not answered yet
  var listeners = [];
  var stopListeners = [];

  /* ── Can it calculate now? ────────────────────────────────────────────────

     One answer for every way in -- the toolbar's Calculate, the Stages menu, the
     Staged construction rail, F9 and `calculate` in the command box -- so that what
     is greyed out and what is refused cannot disagree (js/patches.js `syncCalculate`).
     Pure: it reads the project it is given and nothing else, so the tests can ask it
     about any project without a server behind them.

     It refuses only what the open project already shows to be pointless, in the
     order a user meets them:

     *   a run under way. The request stays open while Kratos works (see the top of
         this file), and a second press would only be told 409 by the server.
     *   no project yet: the page has not heard from the server.
     *   nothing to mesh. The rule is `core.session.nothing_to_mesh`'s -- no soil body
         and no solid -- and so is the first sentence, so the GUI, `kratos-cli check`
         and the server's 422 say it the same way. What follows it is the GUI's own
         way to fix it, where the CLI names `layer add`.
     *   a stage tree with no single order (`App.Stages.branchProblem`).

     A deck case is always worth a try: the server runs its files as they are, and
     its soil is in the deck, not in `soil_body_keys`. What the model is made of --
     its materials, its flow conditions, whether Kratos is installed -- is the
     server's to judge, after the press, with its full reason in the command log. */

  var RUNNING = 'Calculating… Kratos is running this model. The Convergence window '
              + 'shows how it goes, and the command log says when it finishes. '
              + 'Press Stop to stop it.';

  var STOP_TIP = 'Stop the calculation. The stages that finished keep their results, '
               + 'and the model does not change.';

  function nothingToMesh(project) {
    var noun = project.dimension === 2 ? 'surface' : 'volume';
    return 'The model has nothing to mesh: no soil layer and no solid. In Soil mode, '
         + 'add a layer with Modify soil layers…, or create a soil ' + noun + '.';
  }

  function state(project, running) {
    if (running) return { ok: false, running: true, reason: RUNNING };
    if (!project) return { ok: false, running: false, reason: 'Loading the project…' };
    if (project.deck) return { ok: true, running: false, reason: '' };
    if (!(project.soil_body_keys || []).length && !(project.custom_parts || []).length) {
      return { ok: false, running: false, reason: nothingToMesh(project) };
    }
    var branched = App.Stages && App.Stages.branchProblem
      ? App.Stages.branchProblem(project) : null;
    if (branched) return { ok: false, running: false, reason: branched };
    return { ok: true, running: false, reason: '' };
  }

  function running() { return inFlight; }

  function isStopping() { return stopping; }

  /* Told when a run starts and when it ends, however it ends: `fn(running, result)`,
     with the server's answer as `result` when a run ended with one (none when the
     request failed). Adding the same function twice adds it once: js/patches.js
     installs more than once in the tests. */
  function onChange(fn) {
    if (typeof fn === 'function' && listeners.indexOf(fn) < 0) listeners.push(fn);
  }

  /* Told when a stop is asked and when the run has answered: `fn(stopping)`. */
  function onStop(fn) {
    if (typeof fn === 'function' && stopListeners.indexOf(fn) < 0) stopListeners.push(fn);
  }

  /* A listener that throws must not turn a finished run into "Calculation failed":
     its error is rethrown on its own, where the page's error reporter sees it. */
  function tell(fns, args) {
    fns.slice().forEach(function (fn) {
      try { fn.apply(null, args); } catch (err) { setTimeout(function () { throw err; }, 0); }
    });
  }

  function setInFlight(value, result) {
    if (inFlight === value) return;
    inFlight = value;
    if (!value) setStopping(false);
    tell(listeners, [inFlight, result]);
  }

  function setStopping(value) {
    if (stopping === value) return;
    stopping = value;
    tell(stopListeners, [stopping]);
  }

  function log(kind, line) {
    if (App.Command && App.Command[kind]) App.Command[kind](line);
  }

  /* Whether the model as it is now has a mesh: the one on screen, or the one the last
     calculation made. Both are kept on the server, so the run does not mesh again. */
  function meshed(viewport) {
    if (!viewport) return false;
    if (viewport.hasMesh && viewport.hasMesh()) return true;
    return !!(viewport.calculatedMeshFits && viewport.calculatedMeshFits());
  }

  /* Said before a run on a model with no mesh: the run makes one, with the settings
     of Mesh properties, and the user did not see it first. */
  function noMesh(settings) {
    var size = settings && settings.element_size;
    return 'Warning: the model has no mesh yet. Calculate meshes it first with the '
         + 'global mesh settings of Mesh properties'
         + (size ? ' (global element size ' + size + ' m)' : '') + '. '
         + 'To see the mesh before you calculate, generate it in the Mesh tab.';
  }

  function integer(value) {
    return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  /* The same mesh settings the export uses -- every meshable body, at the project's own
     size -- because the deck being run has to be the deck the user would have got by
     exporting. Borrowed from App.Export rather than restated, so the two cannot drift. */
  function request() {
    return App.Export.meshRequest();
  }

  /* A few names, then a count: a run writes one pair of files per stage, and a list of
     twelve tells nobody anything a directory listing would not. */
  function results(outputs) {
    if (!outputs || !outputs.length) return 'no result files';
    if (outputs.length <= 4) return outputs.join(', ');
    return outputs.slice(0, 3).join(', ') + ' and ' + (outputs.length - 3) + ' more';
  }

  /* What the server did about the mesh, when it is not what the line before the run
     said: `hadMesh` is whether the page saw a mesh for the model when the run began. */
  function reportMesh(result, hadMesh) {
    if (!result || !result.stats || result.mesh_reused === undefined) return;
    if (result.mesh_reused && !hadMesh) {
      log('note', 'The server still had a mesh of this model, so the deck was written '
                  + 'from it.');
    } else if (!result.mesh_reused && hadMesh) {
      log('note', 'The server no longer had the mesh, so it meshed the model again with '
                  + 'the same settings.');
    }
  }

  function report(result, hadMesh) {
    reportMesh(result, hadMesh);
    (result.notes || []).concat(result.warnings || []).forEach(function (line) {
      log('note', line);
    });

    /* Stopped by the user: not a failure, so no red line and no Kratos output. */
    if (result.stopped) {
      var where = result.stage
        ? ', in stage ' + result.stage.index + ' of ' + result.stage.of + ' ("'
          + result.stage.name + '"). The stages before it finished and keep their results'
        : '';
      log('note', 'Calculation stopped after ' + result.seconds + ' s' + where
                  + '. The model has not changed.');
      log('note', 'What the run wrote is in ' + result.directory);
      return;
    }

    if (result.ok) {
      log('ok', 'Calculation finished in ' + result.seconds + ' s: '
                + results(result.outputs) + ' written to ' + result.directory
                + ' (' + integer(result.stats.elements) + ' elements, '
                + integer(result.stats.nodes) + ' nodes).');
      log('note', 'It is now the open run: "results files" lists what it wrote, '
                  + '"results zip" downloads all of it.');
      return;
    }
    /* Which stage it died in, first and on its own line.

       `result.stage` is what `calculate.failed_stage` worked out from the markers
       `core.analysis.kratos_main` prints around each stage; null on a deck that finished, and on
       one that never reached a stage at all. On a seven-stage deck the difference
       between "it failed" and "stage 5 failed" is most of the message, so it is said
       before the reason rather than buried in it. */
    if (result.stage) {
      log('err', 'Stage ' + result.stage.index + ' of ' + result.stage.of + ' ("'
                 + result.stage.name + '") failed. The stages before it ran.');
    }
    // The server sends the tail of Kratos' output, which is where its reason is. The
    // whole of it is on disk, so the log file is named rather than the tail extended:
    // a stack trace in the command log buries everything else the user did.
    log('err', 'Calculation failed'
               + (result.returncode === null ? ' (timed out)' : '') + '. '
               + (result.error || 'Kratos exited without saying why.'));
    log('note', 'The deck and the full log (' + result.log + ') are in '
                + result.directory);
  }

  function run(done) {
    if (inFlight) {
      log('note', 'A calculation is already running.');
      if (done) done();
      return Promise.resolve();
    }
    setInFlight(true);
    var viewport = App.Viewport;
    var deck = !!(App.PROJECT && App.PROJECT.deck);
    var settings = request();
    var hadMesh = !deck && meshed(viewport);
    if (deck) {
      log('note', 'Running the deck with Kratos…');
    } else if (hadMesh) {
      log('note', 'Writing the deck from the existing mesh and running Kratos…');
    } else {
      log('note', noMesh(settings));
      log('note', 'Meshing, writing the deck and running Kratos…');
    }
    // The run meshes the model on the server when it has no mesh yet. Its key goes to
    // the viewport, so the Mesh tab can show that mesh afterwards instead of asking how
    // to make one. A deck case brings its own mesh, so there is nothing to remember.
    var meshKey = viewport && viewport.meshKey && !deck ? viewport.meshKey() : null;

    return App.Api.post('/api/calculate', settings).then(function (result) {
      setInFlight(false, result);
      // `stats` means the export, and so the mesh, was made -- even when Kratos failed.
      if (meshKey && result && result.stats && viewport.rememberCalculatedMesh) {
        viewport.rememberCalculatedMesh(meshKey);
      }
      /* The run just written becomes the one `results` opens, before anything is
         printed about it. No round trip: the response already carries the run id,
         so pressing Calculate and then typing `results files` works with nothing
         in between. */
      if (App.Results) App.Results.remember(result);
      report(result, hadMesh);
      if (done) done(result);
      return result;
    }).catch(function (err) {
      setInFlight(false);
      /* 409: the server is busy with a run this page did not start -- one from another
         tab, or from before the page was reloaded. This page cannot see it, so the
         button was not greyed out; say what is going on rather than "failed". */
      if (err && err.status === 409) {
        log('err', 'Kratos is still running an earlier calculation, started in another '
                   + 'tab or before this page was reloaded. Calculate again when it '
                   + 'has finished.');
      } else {
        log('err', 'Calculation failed: ' + err.message);
      }
      if (done) done();
    });
  }

  /* Stop the run now, without asking: `calculate stop` and the confirmed Stop button.

     Asked of the server even when this page started no run, so the Convergence window
     of a page loaded during a run can stop it too. When this page's run stops, its own
     Calculate request reports it; this only says that the stop is on its way. */
  function stop() {
    if (stopping) {
      log('note', 'The calculation is being stopped.');
      return Promise.resolve(true);
    }
    if (inFlight) setStopping(true);
    return App.Api.post('/api/calculate/stop', {}).then(function (answer) {
      var stopped = !!(answer && answer.stopped);
      if (!stopped) {
        setStopping(false);
        log('note', 'No calculation is running.');
      } else if (inFlight) {
        log('note', 'Stopping Kratos…');
      } else {
        log('note', 'The calculation that was running is stopped. What it wrote stays '
                    + 'in its run directory.');
      }
      return stopped;
    }).catch(function (err) {
      setStopping(false);
      log('err', 'The calculation could not be stopped: ' + err.message);
      return false;
    });
  }

  /* Stop, after asking: the Stop button of the toolbar, the Stages menu and the
     Convergence window. Without the page's dialog layer it stops at once. */
  function askStop() {
    if (stopping) return Promise.resolve(true);
    if (!App.Dialogs || !App.Dialogs.open || typeof document === 'undefined'
        || !document.getElementById('modal-layer')) {
      return stop();
    }
    return new Promise(function (resolve) {
      var answered = false;
      var handle = App.Dialogs.open({
        title: 'Stop calculation',
        width: 440, height: 210,
        buttons: [
          { label: 'Stop calculation', primary: true,
            onClick: function () { answered = true; resolve(stop()); } },
          { label: 'Keep running' }
        ],
        build: function (body) {
          var text = document.createElement('div');
          text.className = 'dlg-simple calc-stop-text';
          text.textContent = 'Stop Kratos now? The stages that finished keep their '
                           + 'results, and the run directory keeps its files and log. '
                           + 'The model does not change.';
          body.appendChild(text);
        },
        onClose: function () { if (!answered) resolve(false); }
      });
      handle.dialog.classList.add('dlg-calc-stop');
    });
  }

  return { run: run, request: request, results: results, meshed: meshed, noMesh: noMesh,
           state: state, running: running, onChange: onChange,
           stop: stop, askStop: askStop, stopping: isStopping, onStop: onStop,
           STOP_TIP: STOP_TIP };
})();
