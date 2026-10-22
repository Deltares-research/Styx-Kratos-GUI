/* ══════════════════════════════════════════════════════════════════
   results.js — reaching what a calculation left behind.

   `calculate.js` prints a directory and forgets it. This is the other half: the run
   directories on the machine, listed, opened and downloaded from the command box,
   without anyone having to go and find a folder.

   ── The command line is the feature ──────────────────────────────────────

       results                 what is open
       results runs            every run on this machine, newest first
       results open <id|n>     make one current; a bare number indexes the last listing
       results phase <n|+|->   choose a construction phase, or step through them
       results fields          what this phase can show
       results field <name>    draw it
       results at <node id>    every field at one node
       results bands <n> | smooth | map <name> | deform <f|auto|off>
       results mesh [on|off]   the element outlines over the shading
       results range auto | <min> <max>
       results csv             the field on screen, as a file
       results files | get <file> | zip     the run directory itself

   The Results menu and the Results explorer are two more ways in, and neither is a
   second implementation: both build the same strings and hand them to
   `handleCommand`. Anything they can do is therefore covered by this module's tests,
   and a new entry in either is a line of data rather than a line of logic.

   ── Why there is no DOM in here ──────────────────────────────────────────

   There is no Node on this machine, so the only JavaScript that gets executed
   automatically is what `frontend/tests/run_headless.py` can run under quickjs — and that
   has no `document`, no `window.location` and no `fetch`. Everything here is
   therefore parsing, formatting and decisions, reaching the outside world through
   three things a test replaces: `App.Api`, `App.Command`, and `App.Results.download`,
   which is called through the module object for exactly that reason.

   The one consequence to remember: nothing in this file may touch `document`. A
   feature that needs it belongs in `patches.js`, where the browser suite can reach it.

   ── Declining is part of the contract ────────────────────────────────────

   `handleCommand` returns `false` for anything that is not ours, and `patches.js`
   falls through to the next interpreter and finally to the frozen one. A module that
   answered everything would take `mesh`, `run` and `export` away from their owners
   without any of them noticing.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Results = (function () {

  var ROOT = '/api/results/runs';

  var listed = [];      // the last `results runs`, so `results open 2` means something
  var openRun = null;   // the full record of the run that is current, or null

  /* What is on screen. `mesh` and `catalogue` belong to the stage, `field` to the
     quantity, and `options` to how it is drawn -- which is why an option change
     redraws without going near the server, and a stage change keeps the field. */
  var view = {
    stage: null, mesh: null, catalogue: null, field: null, location: 'nodes',
    displacement: null
  };

  /* How a result is drawn until somebody says otherwise.

     Rainbow and banded rather than a smooth perceptual ramp: banded contours
     are what values get read off, and that is worth more here than the gradient being
     easier on the eye. 32 bands is fine enough to read as a contour and coarse enough
     that the steps mean something. All three are changeable per run, and `results map
     viridis` / `results smooth` are a keystroke away. */
  var DEFAULTS = { map: 'rainbow', bands: 32, deform: 0, reversed: false,
                   mesh: false, min: null, max: null };

  /* The field to draw when a stage is opened and nothing has been asked for, most
     wanted first. Vertical phase displacement is what settles after an excavation
     step, so it is what gets looked at. By *name*, not by position: a stage that did
     not write DISPLACEMENT falls through to whatever it did write rather than to
     nothing. */
  var PREFERRED_FIELDS = ['duy', 'uy', 'u'];

  var options = {
    map: DEFAULTS.map, bands: DEFAULTS.bands, deform: DEFAULTS.deform,
    reversed: DEFAULTS.reversed, mesh: DEFAULTS.mesh,
    /* null means "follow the field". A typed range is kept across a change of stage
       on purpose: a range that re-fits itself every phase makes every phase look
       identical, which is the opposite of what stepping through them is for. */
    min: DEFAULTS.min, max: DEFAULTS.max
  };

  function log(kind, line) {
    if (App.Command && App.Command[kind]) App.Command[kind](line);
  }

  function echo(text) {
    if (App.Command && App.Command.write) App.Command.write('echo', '> ' + text);
  }

  /* ── Formatting ───────────────────────────────────────────────────────── */

  /* Readable rather than exact. Nobody reading a run listing wants 6234567, and the
     one question the number answers -- is this run big -- is answered better by two
     significant figures than by seven. */
  function size(bytes) {
    var n = Number(bytes) || 0;
    if (n < 1024) return n + ' B';
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB';
    if (n < 1024 * 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + ' MB';
    return (n / 1024 / 1024 / 1024).toFixed(1) + ' GB';
  }

  /* The stamp the server sends is ISO-ish because that is what sorts; a person reads
     a space. Anything that is not the expected shape is passed through untouched --
     a run directory from a future version of the exporter is still worth listing. */
  function when(stamp) {
    var text = String(stamp || '');
    return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(text)
      ? text.replace('T', ' ') : text;
  }

  function pad(text, width) {
    var out = String(text);
    while (out.length < width) out += ' ';
    return out;
  }

  /* `nouns` for the words whose plural is not an added s, such as "series". */
  function plural(count, noun, nouns) {
    return count + ' ' + (count === 1 ? noun : (nouns || noun + 's'));
  }

  function runLine(run, index) {
    return ' ' + pad(index + 1, 3) + pad(run.deck, 26) + '  ' + when(run.started)
           + '   ' + pad(plural(run.results, 'stage'), 10)
           + pad(size(run.bytes), 10) + run.id;
  }

  /* ── Where a file is ──────────────────────────────────────────────────── */

  function base() {
    return (App.Api && App.Api.base) || '';
  }

  /* `encodeURIComponent`, not a raw join: a stage name comes from a phase name the
     user typed, so an output file can legitimately carry a space or an ampersand. The
     server takes the decoded name and refuses anything with a separator in it. */
  function fileUrl(runId, name) {
    return base() + ROOT + '/' + encodeURIComponent(runId)
           + '/files/' + encodeURIComponent(name);
  }

  function archiveUrl(runId) {
    return base() + ROOT + '/' + encodeURIComponent(runId) + '/archive';
  }

  /* The only thing here that needs a page, and so the only thing replaced in the
     headless suite. A link rather than a fetch-and-blob: the server already sends
     Content-Disposition, and pulling six megabytes into memory to hand them straight
     back would be the same bytes twice for no gain. */
  function download(url, name) {
    var link = document.createElement('a');
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  /* ── State ────────────────────────────────────────────────────────────── */

  function current() {
    return openRun ? openRun.id : null;
  }

  /* Drop everything: no run open, nothing on screen, every display option back to its
     default. What `patches.js` calls when a different project is opened, because a
     run's results belong to the document that produced them.

     It notifies, like every other change: the panel and the menu are drawn from this
     module's state, and without it they would go on offering the phases of a run that
     is no longer open. */
  function forget() {
    ticket += 1;
    listed = [];
    openRun = null;
    pending = Promise.resolve();
    view = { stage: null, mesh: null, catalogue: null, field: null,
             location: 'nodes', displacement: null };
    options = { map: DEFAULTS.map, bands: DEFAULTS.bands, deform: DEFAULTS.deform,
                reversed: DEFAULTS.reversed, mesh: DEFAULTS.mesh,
                min: DEFAULTS.min, max: DEFAULTS.max };
    if (App.ResultsPlot) App.ResultsPlot.forget();
    changed();
  }

  function stage() { return view.stage; }
  function location() { return view.location; }
  function field() { return view.field; }

  /* Everything the Results panel draws itself from. One accessor rather than six, so
     the panel is a view of this module's state and not a second copy of it. */
  function state() {
    return {
      run: openRun && openRun.id,
      stages: stagesOf(),
      stage: view.stage,
      catalogue: view.catalogue,
      field: view.field,
      location: view.location
    };
  }

  /* What the viewport implements. Replaced wholesale in the headless suite, which is
     why it is reached through the module object: everything that decides *what* is
     drawn is testable here, and only the three.js that draws it is not. */
  function draw(payload) {
    if (App.ResultsView && App.ResultsView.draw) App.ResultsView.draw(payload);
  }

  /* Everything the viewport needs, in one object, with the range resolved.

     Synchronous on purpose: every display option redraws through here, and a redraw
     that awaited something would make stepping the band count feel like the network.
     The one thing it may have to fetch -- the displacement vectors a deformed mesh
     needs -- is fetched by `withDisplacement` *before* this is called, and cached per
     stage, so by the time anything gets here everything is in hand. */
  function present() {
    if (!view.mesh || !view.field) return;
    var displacement = view.displacement && view.displacement.stage === view.stage
      ? view.displacement : null;
    var range = {
      min: options.min === null ? view.field.min : options.min,
      max: options.max === null ? view.field.max : options.max
    };
    App.Results.draw({
      run: openRun && openRun.id,
      stage: view.stage,
      mesh: view.mesh,
      field: view.field,
      displacement: displacement,
      options: {
        map: options.map, bands: options.bands, deform: options.deform,
        reversed: options.reversed, mesh: options.mesh,
        min: range.min, max: range.max
      }
    });
  }

  /* The displacement vectors for the open stage, fetched once and kept.

     Only when something actually wants them: an undeformed contour is the common case
     and there is no reason to pull 4 000 vectors for it. */
  function withDisplacement() {
    if (!options.deform || !openRun || !view.stage) return Promise.resolve();
    if (view.displacement && view.displacement.stage === view.stage) {
      return Promise.resolve();
    }
    // Tagged with the stage it was asked *for*, and kept only if that stage is still
    // the one shown: by the time it arrives the user may have stepped on.
    var run = openRun, stage = view.stage;
    function keep(answer) {
      if (openRun === run && view.stage === stage) view.displacement = answer;
    }
    var path = ROOT + '/' + encodeURIComponent(run.id)
             + '/stages/' + stage + '/displacement';
    return App.Api.get(path).then(function (answer) {
      answer.stage = stage;
      keep(answer);
    }).catch(function () {
      // A stage with no displacement in it is not an error; it just cannot be
      // deformed, and `results-view` treats an empty one as a factor of zero.
      keep({ stage: stage, ids: [], values: [] });
    });
  }

  /* Fetch what is missing, then draw. Everything that changes the picture goes
     through this rather than calling `present` directly. */
  function redraw() {
    return withDisplacement().then(present);
  }

  /* The run that just finished, adopted and *read*.

     `POST /api/calculate` names the run but does not describe it, so this reads it as
     well. The id alone is not enough and was the bug: a run recorded by name only is
     "open" with no stages in it, which draws an empty phase list, reports every field
     as absent, and can only be recovered by typing `results open <the id already on
     screen>`. Pressing Calculate has to leave something that can be looked at.

     The id is set synchronously so `current()` is right immediately; the reading is a
     promise, and `ready()` is how a caller waits for it.

     `directory` is the fallback for a server too old to send `run`, split on both
     separators because the two platforms spell it differently and the browser cannot
     tell which wrote it. */
  function remember(result) {
    var id = result && (result.run || tail(result.directory));
    if (!id) return Promise.resolve();
    openRun = { id: id };
    changed();
    pending = openById(id, true);
    return pending;
  }

  /* ── Telling the panel ────────────────────────────────────────────────── */

  var listeners = [];
  var pending = Promise.resolve();

  /* Which request is the latest. Opening a run, choosing a stage and choosing a field
     each take a new ticket; a reply that comes back holding an older one is for
     something the user has already moved on from, and is dropped. Without it, two
     quick `results phase +` left the slower reply on screen labelled as the newer. */
  var ticket = 0;

  /* Subscribe to "something on screen changed". The Results panel is DOM and lives in
     `patches.js`, so it cannot be updated from here directly -- and it must not keep
     its own copy of this state, or the two drift. It redraws itself from `state()`
     whenever this fires. */
  function onChange(listener) {
    if (typeof listener === 'function') listeners.push(listener);
  }

  function changed() {
    listeners.forEach(function (listener) {
      try { listener(); } catch (error) { /* a broken panel must not stop the model */ }
    });
  }

  /* Whatever asynchronous work is outstanding. For tests, and for a caller that wants
     to act once the run it just started is readable. */
  function ready() {
    return pending;
  }

  function tail(path) {
    if (!path) return null;
    var parts = String(path).split(/[\\/]/).filter(function (p) { return p; });
    return parts.length ? parts[parts.length - 1] : null;
  }

  /* ── The verbs ────────────────────────────────────────────────────────── */

  var USAGE = [
    'results runs            every run on this machine, newest first',
    'results open <id|n>     open one; a bare number indexes the last listing',
    'results phase <n|name>  choose a construction phase; + and - step through them',
    'results fields          what this phase can show',
    'results field <name>    draw it, e.g. `results field p`',
    'results at <node id>    every field at one node',
    'results deform <f|auto|off> / bands <n> / smooth / range auto|<min> <max>',
    'results map <name>      rainbow, turbo, viridis, plasma, inferno, diverging,',
    '                        spectral, blues or greyscale',
    'results reverse         flip the colour ramp end for end',
    'results mesh [on|off]   draw the element outlines over the shading',
    'results csv             the field on screen, as a file',
    'results plot [member] [quantity]   M, Q, N, ux, tn, ts along the wall, per phase;',
    '                        `results plot members` lists them, `plot csv`/`svg` saves',
    'results files / get <file> / zip     the run directory itself'
  ];

  function usage() {
    USAGE.forEach(function (line) { log('note', '  ' + line); });
  }

  function listRuns() {
    return App.Api.get(ROOT).then(function (answer) {
      listed = answer.runs || [];
      if (!listed.length) {
        log('note', 'No runs yet in ' + answer.root
                    + ' — press Calculate (F9) and one will appear there.');
        return listed;
      }
      log('ok', plural(listed.length, 'run') + ' in ' + answer.root + ':');
      listed.forEach(function (run, index) { log('note', runLine(run, index)); });
      log('note', 'Open one with `results open <number>`.');
      return listed;
    }).catch(fail);
  }

  /* An id, or a position in the last listing. The number is the convenience -- nobody
     is going to retype `Staged_excavation_2026-09-22_00-49` -- and it is resolved
     here rather than sent, so the server has one kind of id and not two. */
  function resolve(token) {
    if (!/^\d+$/.test(token)) return token;
    var position = parseInt(token, 10);
    if (!listed.length) {
      log('err', 'Nothing has been listed yet, so there is no run ' + position
                 + '. Run `results runs` first, or give the run id.');
      return null;
    }
    if (position < 1 || position > listed.length) {
      log('err', 'There is no run ' + position + ' — the listing has '
                 + plural(listed.length, 'run') + '.');
      return null;
    }
    return listed[position - 1].id;
  }

  function openById(token, quiet) {
    if (!token) {
      log('err', 'Usage: results open <run id, or a number from `results runs`>');
      return Promise.resolve();
    }
    var id = resolve(token);
    if (!id) return Promise.resolve();

    var mine = ++ticket;
    return App.Api.get(ROOT + '/' + encodeURIComponent(id)).then(function (run) {
      if (mine !== ticket) return run;
      // Only now: a failed open must leave whatever was open still open, because the
      // alternative is losing a run you had in front of you to a typo.
      openRun = run;
      view = { stage: null, mesh: null, catalogue: null, field: null,
               location: 'nodes', displacement: null };
      if (!quiet) report(run);
      else log('ok', run.id + ' is open — ' + plural(run.stages.length, 'phase')
                     + '. Results mode shows it; `results fields` lists what it has.');
      changed();
      // Straight to the end of the construction sequence, which is what someone
      // opening a run is nearly always after. Quietly -- `report` has just said what
      // the run is, and a second paragraph about the stage would bury it.
      var last = lastReadable();
      return last === null ? run : useStage(last, true).then(function () { return run; });
    }).catch(fail);
  }

  function report(run) {
    log('ok', run.id + ' — ' + run.deck + ', ' + when(run.started) + ', '
              + plural(run.stages.length, 'stage') + ', ' + plural(run.files.length, 'file')
              + ', ' + size(run.bytes) + '.');
    run.stages.forEach(function (stage) {
      log('note', '  ' + pad(stage.index, 4) + pad(stage.phase, 30)
                  + (stage.results ? 'results' : 'no results')
                  + (stage.json.length ? '  +' + plural(stage.json.length, 'series', 'series') : ''));
    });
    if (run.failed_at) {
      log('err', 'The run stopped in phase ' + run.failed_at.index + ' of '
                 + run.failed_at.of + ' ("' + tidy(run.failed_at.name)
                 + '"). The phases before it are complete and can be read.');
    } else if (!run.complete) {
      log('note', 'Not every phase wrote results, and the log does not say why — '
                  + (run.log ? 'see ' + run.log + ' in the run directory.'
                             : 'there is no log in the run directory.'));
    }
  }

  /* `1_First_excavation` back to `First excavation`, the same way the server does it
     for a stage row. Applied to `failed_at.name`, which is the raw stage name. */
  function tidy(name) {
    return String(name || '').replace(/^\d+_/, '').replace(/_/g, ' ');
  }

  function needRun(verb) {
    if (openRun && openRun.files) return true;
    if (openRun) {
      log('err', 'The open run has not been read yet — `results open ' + openRun.id
                 + '` to read it.');
      return false;
    }
    log('err', 'No run is open. `results runs` lists them, `results open <n>` opens one.');
    return false;
  }

  function listFiles() {
    if (!needRun()) return Promise.resolve();
    log('ok', plural(openRun.files.length, 'file') + ' in ' + openRun.id + ':');
    openRun.files.forEach(function (entry) {
      log('note', '  ' + pad(entry.name, 52) + size(entry.bytes));
    });
    log('note', 'Download one with `results get <name>`, or all of them with `results zip`.');
    return Promise.resolve();
  }

  function getFile(name) {
    if (!name) {
      log('err', 'Usage: results get <file name, as `results files` lists it>');
      return Promise.resolve();
    }
    if (!needRun()) return Promise.resolve();
    var known = openRun.files.some(function (entry) { return entry.name === name; });
    if (!known) {
      log('err', openRun.id + ' has no file called "' + name
                 + '". `results files` lists what it does have.');
      return Promise.resolve();
    }
    App.Results.download(fileUrl(openRun.id, name), name);
    log('ok', 'Downloading ' + name + '.');
    return Promise.resolve();
  }

  function getArchive() {
    if (!needRun()) return Promise.resolve();
    var name = openRun.id + '.zip';
    App.Results.download(archiveUrl(openRun.id), name);
    log('ok', 'Downloading ' + name + ' — ' + plural(openRun.files.length, 'file')
              + ', ' + size(openRun.bytes) + ' before compression.');
    return Promise.resolve();
  }

  /* ── Choosing a stage ─────────────────────────────────────────────────── */

  function stagesOf() {
    return (openRun && openRun.stages) || [];
  }

  /* The last stage that wrote results: the end of the construction sequence, which is
     what someone opening a run almost always wants to see first. */
  function lastReadable() {
    var readable = stagesOf().filter(function (s) { return s.results; });
    return readable.length ? readable[readable.length - 1].index : null;
  }

  /* A number, or any part of a phase name. The name match is deliberately loose --
     `results phase first excavation` for `2_First_excavation` -- because the stage
     name is a mangling of something the user typed and nobody will retype the
     mangling. */
  function findStage(token) {
    var stages = stagesOf();
    if (/^\d+$/.test(token)) {
      var index = parseInt(token, 10);
      return stages.filter(function (s) { return s.index === index; })[0] || null;
    }
    var wanted = token.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
    return stages.filter(function (s) {
      return (s.phase || '').toLowerCase().indexOf(wanted) !== -1
          || (s.name || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').indexOf(wanted) !== -1;
    })[0] || null;
  }

  /* Load a stage's mesh and field menu, and put back whatever field was on screen.

     Keeping the field is the point of the whole mode: stepping through the phases on
     one quantity is the thing it is for, and retyping the field at every step would
     make that unusable. */
  function useStage(index, quiet) {
    var base = ROOT + '/' + encodeURIComponent(openRun.id) + '/stages/' + index;
    var wanted = view.field && view.field.field;
    var mine = ++ticket;
    return Promise.all([App.Api.get(base + '/mesh'),
                        App.Api.get(base + '/fields')]).then(function (both) {
      if (mine !== ticket) return;
      view.stage = index;
      view.displacement = null;
      view.mesh = both[0];
      view.catalogue = both[1];
      view.field = null;
      if (!quiet) log('ok', 'Phase ' + index + ' — ' + stageName(index) + ': '
                            + plural(both[0].sections.length, 'part') + ' drawn.');
      changed();
      if (wanted && offered(wanted)) return useField(wanted, view.location, true);
      if (wanted) log('note', '"' + wanted + '" is not available in this phase.');

      /* Nothing chosen yet: draw something rather than nothing. An empty viewport in
         Results mode is indistinguishable from a broken one, and "open a run, see a
         result" is the whole point of the mode. */
      var preferred = defaultField();
      if (preferred) return useField(preferred, null, true);
      return redraw();
    }).catch(fail);
  }

  function stageName(index) {
    var found = stagesOf().filter(function (s) { return s.index === index; })[0];
    return found ? found.phase : String(index);
  }

  /* One readable phase forwards or backwards. Phases that wrote nothing are stepped
     over rather than landed on: a run that died partway leaves gaps, and stopping on
     one would put the viewer on a phase it cannot draw. */
  function step(direction) {
    var readable = stagesOf().filter(function (s) { return s.results; });
    if (!readable.length) return null;
    var at = readable.map(function (s) { return s.index; }).indexOf(view.stage);
    if (at < 0) return readable[direction > 0 ? 0 : readable.length - 1];
    var next = at + direction;
    if (next < 0) {
      log('note', 'Already at the first phase with results.');
      return null;
    }
    if (next >= readable.length) {
      log('note', 'Already at the last phase with results.');
      return null;
    }
    return readable[next];
  }

  function chooseStage(token) {
    if (!openRun) {
      log('err', 'No run is open. `results runs` lists them.');
      return Promise.resolve();
    }
    if (!token) {
      listStages();
      return Promise.resolve();
    }
    // `+` and `-` are what the Results menu's Next/Previous run, and what makes
    // walking the construction sequence one keystroke rather than one number.
    if (token === '+' || token === 'next' || token === '-' || token === 'previous') {
      var stepped = step(token === '+' || token === 'next' ? 1 : -1);
      return stepped ? useStage(stepped.index) : Promise.resolve();
    }
    var found = findStage(token);
    if (!found) {
      log('err', 'No phase matches "' + token + '" in ' + openRun.id + '.');
      listStages();
      return Promise.resolve();
    }
    if (!found.results) {
      log('err', 'Phase ' + found.index + ' ("' + found.phase
                 + '") wrote no results — the run stopped before it.');
      return Promise.resolve();
    }
    return useStage(found.index);
  }

  function listStages() {
    stagesOf().forEach(function (s) {
      log('note', '  ' + pad(s.index, 4) + pad(s.phase, 30)
                  + (s.results ? '' : 'no results')
                  + (s.index === view.stage ? '   ← shown' : ''));
    });
  }

  /* ── Choosing a field ─────────────────────────────────────────────────── */

  function entries() {
    var all = [];
    ((view.catalogue && view.catalogue.groups) || []).forEach(function (group) {
      group.fields.forEach(function (entry) {
        all.push({ group: group.name, entry: entry });
      });
    });
    return all;
  }

  /* The most wanted field this stage actually has, or its first if it has none of
     them. `null` only when the stage offers nothing at all. */
  function defaultField() {
    for (var i = 0; i < PREFERRED_FIELDS.length; i++) {
      if (offered(PREFERRED_FIELDS[i])) return PREFERRED_FIELDS[i];
    }
    var first = entries()[0];
    return first ? first.entry.name : null;
  }

  function offered(name) {
    return entries().filter(function (row) { return row.entry.name === name; })[0];
  }

  function listFields() {
    if (!view.catalogue) {
      log('err', 'No phase is open. `results phase <n>` chooses one.');
      return Promise.resolve();
    }
    log('ok', 'Phase ' + view.stage + ' — ' + stageName(view.stage) + ' offers:');
    view.catalogue.groups.forEach(function (group) {
      log('note', '  ' + group.name);
      group.fields.forEach(function (entry) {
        log('note', '    ' + pad(entry.name, 10) + pad(entry.label, 24)
                    + pad(entry.unit, 6) + entry.locations.join('/'));
      });
    });
    log('note', 'Draw one with `results field <name>`.');
    return Promise.resolve();
  }

  function useField(name, where, quiet) {
    var row = offered(name);
    if (!row) {
      // Refused here rather than by the server: the catalogue already said what this
      // phase has, so there is no reason to spend a round trip learning it again.
      log('err', '"' + name + '" is not available in phase ' + view.stage
                 + '. `results fields` lists what is.');
      return Promise.resolve();
    }
    var at = where || row.entry.locations[0];
    if (row.entry.locations.indexOf(at) === -1) {
      log('err', '"' + name + '" can only be shown per '
                 + row.entry.locations.join(' or ') + '.');
      return Promise.resolve();
    }
    var path = ROOT + '/' + encodeURIComponent(openRun.id) + '/stages/' + view.stage
             + '/field/' + encodeURIComponent(name) + '?location=' + at;
    var mine = ++ticket;
    return App.Api.get(path).then(function (field) {
      if (mine !== ticket) return field;
      view.field = field;
      view.location = at;
      changed();
      if (!quiet) {
        log('ok', field.label + ' (' + field.unit + '), phase ' + view.stage + ': '
                  + App.ResultsRender.format(field.min) + ' to '
                  + App.ResultsRender.format(field.max)
                  + ' over ' + plural(field.ids.length, at === 'nodes' ? 'node' : 'element')
                  + '.');
      }
      return redraw().then(function () { return field; });
    }).catch(fail);
  }

  function needField(what) {
    if (view.field) return true;
    log('err', 'Nothing is on screen yet. `results field <name>` draws one'
               + (what ? ', then ' + what + '.' : '.'));
    return false;
  }

  /* ── Display options ──────────────────────────────────────────────────── */

  function setOption(verb, rest) {
    var token = (rest || '').trim().toLowerCase();

    if (verb === 'smooth') { options.bands = 0; }
    else if (verb === 'bands') {
      var n = parseInt(token, 10);
      if (!(n >= 2)) {
        log('err', 'Usage: results bands <a number of colour bands, 2 or more> '
                   + '— or `results smooth` for none.');
        return Promise.resolve();
      }
      options.bands = n;
    } else if (verb === 'map') {
      var maps = Object.keys(App.ResultsRender.MAPS);
      if (maps.indexOf(token) === -1) {
        log('err', 'No colour map called "' + token + '". There is '
                   + maps.join(', ') + '.');
        return Promise.resolve();
      }
      options.map = token;
    } else if (verb === 'deform') {
      if (token === 'off' || token === 'none' || token === '0') options.deform = 0;
      else if (token === 'auto' || token === '') options.deform = 'auto';
      else {
        var factor = parseFloat(token);
        if (!(factor >= 0)) {
          log('err', 'Usage: results deform <factor> | auto | off');
          return Promise.resolve();
        }
        options.deform = factor;
      }
    } else if (verb === 'reverse' || verb === 'reversed') {
      // A bare `results reverse` flips it, which is what it is reached for; `on` and
      // `off` are there so a menu item can set it rather than toggle it and get out
      // of step with the tick beside its own label.
      options.reversed = token === '' ? !options.reversed
                       : !(token === 'off' || token === 'no' || token === 'false');
    } else if (verb === 'mesh') {
      // The element outlines over the shading. Toggled and set exactly like `reverse`.
      options.mesh = token === '' ? !options.mesh
                   : !(token === 'off' || token === 'no' || token === 'false');
    } else if (verb === 'range') {
      if (token === 'auto' || token === '') { options.min = options.max = null; }
      else {
        var parts = token.split(/[\s,]+/).map(parseFloat);
        if (parts.length !== 2 || !isFinite(parts[0]) || !isFinite(parts[1])) {
          log('err', 'Usage: results range <min> <max> — or `results range auto`.');
          return Promise.resolve();
        }
        options.min = Math.min(parts[0], parts[1]);
        options.max = Math.max(parts[0], parts[1]);
      }
    }
    // No request for the values -- they are already here and only the colours change,
    // which is what makes stepping the band count feel instant. Turning deformation on
    // is the one exception, and `redraw` is what fetches the vectors for it.
    log('note', settingsLine());
    changed();
    return redraw();
  }

  function settingsLine() {
    return 'Shading ' + (options.bands ? options.bands + ' bands' : 'smooth')
         + ', map ' + options.map + (options.reversed ? ' reversed' : '')
         + ', deformation ' + (options.deform === 'auto' ? 'auto'
                               : options.deform ? '×' + options.deform : 'off')
         + ', mesh ' + (options.mesh ? 'on' : 'off')
         + ', range ' + (options.min === null ? 'auto' : options.min + ' to ' + options.max)
         + '.';
  }

  /* The legend's Min and Max boxes, as the `results range` they mean -- or `null`, with
     the reason logged, when they mean nothing. Both empty is the automatic range; one
     empty keeps that end where the legend has it now, so typing a single limit does
     what it looks like it does. A decimal comma is read as a point: half the people
     reading these numbers write 0,5. */
  function limitsCommand(minText, maxText) {
    if (!view.field) {
      log('err', 'Nothing is on screen yet, so there is no legend to set limits on.');
      return null;
    }
    var typed = [minText, maxText].map(function (text) {
      return String(text === undefined || text === null ? '' : text).trim();
    });
    if (!typed[0] && !typed[1]) return 'results range auto';

    var shown = [options.min === null ? view.field.min : options.min,
                 options.max === null ? view.field.max : options.max];
    var limits = [];
    for (var i = 0; i < 2; i++) {
      if (!typed[i]) { limits.push(shown[i]); continue; }
      var text = typed[i].replace(',', '.');
      var value = /^[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?$/i.test(text) ? parseFloat(text) : NaN;
      if (!isFinite(value)) {
        log('err', '"' + typed[i] + '" is not a number, so it cannot be the legend\'s '
                   + (i ? 'maximum' : 'minimum') + '.');
        return null;
      }
      limits.push(value);
    }
    if (limits[0] === limits[1]) {
      log('err', 'The minimum and the maximum are both ' + limits[0]
                 + ' — there would be no colours between them.');
      return null;
    }
    return 'results range ' + limits[0] + ' ' + limits[1];
  }

  /* ── Probing and exporting ────────────────────────────────────────────── */

  function atNode(token) {
    if (!view.stage) {
      log('err', 'No phase is open. `results phase <n>` chooses one.');
      return Promise.resolve();
    }
    if (!/^\d+$/.test((token || '').trim())) {
      log('err', 'Usage: results at <node id>');
      return Promise.resolve();
    }
    var path = ROOT + '/' + encodeURIComponent(openRun.id) + '/stages/' + view.stage
             + '/at/' + parseInt(token, 10);
    return App.Api.get(path).then(function (answer) {
      log('ok', 'Node ' + answer.node + ' at ('
                + answer.at.map(function (c) { return c.toFixed(3); }).join(', ')
                + ') in phase ' + view.stage + ':');
      var group = null;
      answer.values.forEach(function (row) {
        if (row.group !== group) { group = row.group; log('note', '  ' + group); }
        log('note', '    ' + pad(row.label, 26)
                    + pad(row.value === null || row.value === undefined ? '—'
                          : App.ResultsRender.format(row.value), 12)
                    + row.unit);
      });
      return answer;
    }).catch(fail);
  }

  function exportCsv() {
    if (!needField('`results csv` saves it')) return Promise.resolve();
    var name = [openRun.id, 'phase' + view.stage, view.field.field].join('_') + '.csv';
    App.Download.anchor(name, App.ResultsRender.csv(view.field, {
      run: openRun.id, stage: stageName(view.stage)
    }), 'text/csv');
    log('ok', 'Saved ' + name + ' — '
              + plural(view.field.ids.length, 'row') + '.');
    return Promise.resolve();
  }

  function describeCurrent() {
    if (openRun && openRun.files) {
      report(openRun);
    } else if (openRun) {
      return openById(openRun.id);
    } else {
      log('note', 'No run is open.');
      usage();
    }
    return Promise.resolve();
  }

  function fail(error) {
    log('err', (error && error.message) || String(error));
  }

  /* ── Dispatch ─────────────────────────────────────────────────────────── */

  /* `false` means "not mine", and must be returned *before* anything is logged --
     see this file's header. Everything else returns a promise, so `patches.js` can
     chain on it and a test can wait for it. */
  function handleCommand(text) {
    var trimmed = String(text || '').trim();
    var parts = trimmed.split(/\s+/);
    if (parts[0].toLowerCase() !== 'results') return false;

    echo(trimmed);
    var verb = (parts[1] || '').toLowerCase();
    var rest = trimmed.slice(trimmed.indexOf(parts[1] || '') + (parts[1] || '').length)
                      .trim();

    if (!verb) return describeCurrent();
    if (verb === 'runs' || verb === 'list') return listRuns();
    if (verb === 'open') return openById(parts[2]);
    if (verb === 'files') return listFiles();
    // The name is the rest of the line, not the next token: an output file is named
    // after a phase, and a phase name is something the user typed spaces into.
    if (verb === 'get') return getFile(rest);
    if (verb === 'zip' || verb === 'archive') return getArchive();

    // Phase and field. `phase` takes the rest of the line for the same reason `get`
    // does -- "first excavation" is two words and one phase.
    if (verb === 'phase' || verb === 'stage') return chooseStage(rest);
    if (verb === 'fields') return listFields();
    if (verb === 'field') {
      if (!view.catalogue) {
        log('err', 'No phase is open. `results phase <n>` chooses one.');
        return Promise.resolve();
      }
      return useField(parts[2], (parts[3] || '').toLowerCase() || null);
    }
    if (verb === 'at') return atNode(parts[2]);
    if (verb === 'csv') return exportCsv();
    // The wall and interface curves, phase by phase: frontend/js/results-plot.js.
    if (verb === 'plot' && App.ResultsPlot) return App.ResultsPlot.command(rest);
    if (verb === 'bands' || verb === 'smooth' || verb === 'map'
        || verb === 'deform' || verb === 'range' || verb === 'mesh'
        || verb === 'reverse' || verb === 'reversed') {
      return setOption(verb, rest);
    }

    log('err', 'No such results command: "' + verb + '".');
    usage();
    return Promise.resolve();
  }

  return {
    handleCommand: handleCommand,
    current: current, forget: forget, remember: remember,
    onChange: onChange, ready: ready,
    stage: stage, location: location, field: field, state: state,
    fileUrl: fileUrl, archiveUrl: archiveUrl, download: download,
    draw: draw, present: present, redraw: redraw,
    options: function () { return options; },
    limitsCommand: limitsCommand,
    size: size, when: when, runLine: runLine
  };
})();
