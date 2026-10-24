/* ══════════════════════════════════════════════════════════════════
   calculate.js — Calculate (F9): hand the deck to Kratos and say what happened.

   The whole feature is one request. The server meshes the project, writes the same
   three files the export writes, and runs them through Kratos' orchestrator in a
   directory of its own; this asks for that and turns the answer into command-log lines.

   Nothing else happens in the app. The viewport does not change, nothing is read back
   and no mode is entered: a calculation produces files, and this says where they are.
   The one thing it does hand on is the run's *name*, to `App.Results`, so that what
   was just written is the run `results` opens without anyone having to find it again.
   Reading the results themselves into the viewport is the next feature, not this one.

   Two things it deliberately does not do:

   *   it does not reuse the export's download path. A download is for taking the deck
       elsewhere; this one runs where the files are written, and the user never sees a
       save window because nothing is being saved to a place they chose.
   *   it does not poll. The request stays open for as long as the solver runs, which is
       what makes a progress bar possible later without changing anything here.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Calculate = (function () {

  var inFlight = false;
  var listeners = [];

  /* ── Can it calculate now? ────────────────────────────────────────────────

     One answer for every way in -- the toolbar's Calculate, the Phases menu, the
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
     *   a phase tree with no single order (`App.Phases.branchProblem`).

     A deck case is always worth a try: the server runs its files as they are, and
     its soil is in the deck, not in `soil_body_keys`. What the model is made of --
     its materials, its flow conditions, whether Kratos is installed -- is the
     server's to judge, after the press, with its full reason in the command log. */

  var RUNNING = 'Calculating… Kratos is running this model. The command log says '
              + 'when it finishes.';

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
    var branched = App.Phases && App.Phases.branchProblem
      ? App.Phases.branchProblem(project) : null;
    if (branched) return { ok: false, running: false, reason: branched };
    return { ok: true, running: false, reason: '' };
  }

  function running() { return inFlight; }

  /* Told when a run starts and when it ends, however it ends. Adding the same
     function twice adds it once: js/patches.js installs more than once in the tests. */
  function onChange(fn) {
    if (typeof fn === 'function' && listeners.indexOf(fn) < 0) listeners.push(fn);
  }

  /* A listener that throws must not turn a finished run into "Calculation failed":
     its error is rethrown on its own, where the page's error reporter sees it. */
  function setInFlight(value) {
    if (inFlight === value) return;
    inFlight = value;
    listeners.slice().forEach(function (fn) {
      try { fn(inFlight); } catch (err) { setTimeout(function () { throw err; }, 0); }
    });
  }

  function log(kind, line) {
    if (App.Command && App.Command[kind]) App.Command[kind](line);
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

  function report(result) {
    (result.warnings || []).forEach(function (warning) { log('note', warning); });

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
       between "it failed" and "phase 5 failed" is most of the message, so it is said
       before the reason rather than buried in it. */
    if (result.stage) {
      log('err', 'Phase ' + result.stage.index + ' of ' + result.stage.of + ' ("'
                 + result.stage.name + '") failed. The phases before it ran.');
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
    log('note', 'Meshing, writing the deck and running Kratos…');

    return App.Api.post('/api/calculate', request()).then(function (result) {
      setInFlight(false);
      /* The run just written becomes the one `results` opens, before anything is
         printed about it. No round trip: the response already carries the run id,
         so pressing Calculate and then typing `results files` works with nothing
         in between. */
      if (App.Results) App.Results.remember(result);
      report(result);
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

  return { run: run, request: request, results: results,
           state: state, running: running, onChange: onChange };
})();
