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
       `core.run.runner` prints around each stage; null on a deck that finished, and on
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
    inFlight = true;
    log('note', 'Meshing, writing the deck and running Kratos…');

    return App.Api.post('/api/calculate', request()).then(function (result) {
      inFlight = false;
      /* The run just written becomes the one `results` opens, before anything is
         printed about it. No round trip: the response already carries the run id,
         so pressing Calculate and then typing `results files` works with nothing
         in between. */
      if (App.Results) App.Results.remember(result);
      report(result);
      if (done) done(result);
      return result;
    }).catch(function (err) {
      inFlight = false;
      log('err', 'Calculation failed: ' + err.message);
      if (done) done();
    });
  }

  return { run: run, request: request, results: results };
})();
