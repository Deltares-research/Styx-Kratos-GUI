/* ══════════════════════════════════════════════════════════════════
   test-results.js — the `results …` command set.

   Everything here runs headless, under quickjs, with no DOM and no browser: that is
   the point of the seam. `App.Results` parses, formats and decides; it reaches the
   server through `App.Api` and the page through `App.Command` and `App.Results.open`,
   all three of which are replaced below with recorders. Nothing in the module may
   touch `document` or `window.location`, and a test that needs either belongs in
   `index.html` instead.

   The one behaviour worth stating up front: `handleCommand` returns `false` for a
   command that is not ours. `patches.js` chains the live interpreters and falls back
   to the frozen one, so a module that swallowed everything would silently take
   `mesh`, `run` and `export` away from whoever owns them.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  /* ── Doubles ──────────────────────────────────────────────────────────── */

  var log, opened, api, saved;

  var RUNS = [
    { id: 'Staged_excavation_2026-09-22_00-49', deck: 'Staged_excavation',
      started: '2026-09-22T00:49', repeat: 1, results: 7, files: 30, bytes: 6234567 },
    { id: 'column_new_2026-09-20_22-37', deck: 'column_new',
      started: '2026-09-20T22:37', repeat: 1, results: 1, files: 7, bytes: 41234 }
  ];

  var DETAIL = {
    id: 'Staged_excavation_2026-09-22_00-49', deck: 'Staged_excavation',
    started: '2026-09-22T00:49', repeat: 1, results: 7, bytes: 6234567,
    complete: true, failed_at: null, log: 'kratos.log',
    stages: [
      { index: 1, name: '1_Initial_stage', stage: 'Initial stage',
        base: 'Staged_excavation_1_Initial_stage',
        results_file: 'Staged_excavation_1_Initial_stage.post.res',
        mesh_file: 'Staged_excavation_1_Initial_stage.post.msh',
        results: true, json: [] },
      { index: 2, name: '2_First_excavation', stage: 'First excavation',
        base: 'Staged_excavation_2_First_excavation',
        results_file: 'Staged_excavation_2_First_excavation.post.res',
        mesh_file: 'Staged_excavation_2_First_excavation.post.msh',
        results: true, json: ['2_First_excavation__output_wall.json'] }
    ],
    files: [
      { name: 'Staged_excavation.mdpa', bytes: 494424 },
      { name: 'kratos.log', bytes: 182962 }
    ]
  };

  function setup(overrides) {
    log = [];
    opened = [];
    api = { calls: [] };

    window.App = window.App || {};
    // The page shell's mode switch, which a finished calculation calls to open Results.
    if (typeof App.setMode !== 'function') App.setMode = function () {};
    App.Command = {
      note: function (line) { log.push(['note', line]); },
      ok:   function (line) { log.push(['ok', line]); },
      err:  function (line) { log.push(['err', line]); },
      write: function (kind, line) { log.push([kind, line]); }
    };

    var answers = overrides || {};
    App.Api = {
      base: '',
      get: function (path) {
        api.calls.push(path);
        if (Object.prototype.hasOwnProperty.call(answers, path)) {
          var answer = answers[path];
          if (answer instanceof Error) return Promise.reject(answer);
          return Promise.resolve(answer);
        }
        if (path === '/api/results/runs') {
          return Promise.resolve({ runs: RUNS, root: '/home/x/KratosGUI/runs' });
        }
        if (path === '/api/results/runs/' + DETAIL.id) return Promise.resolve(DETAIL);
        // Every run the listing offered must be openable, or `results open <n>` is
        // being tested against a server that does not have what it just advertised.
        for (var i = 0; i < RUNS.length; i++) {
          if (path === '/api/results/runs/' + RUNS[i].id) {
            var detail = JSON.parse(JSON.stringify(RUNS[i]));
            detail.complete = true;
            detail.failed_at = null;
            detail.log = 'kratos.log';
            detail.stages = [];
            detail.files = [];
            return Promise.resolve(detail);
          }
        }
        var missing = new Error("There is no run called 'nope'.");
        missing.status = 404;
        return Promise.reject(missing);
      }
    };

    // The two things the module does that need a page. Replaced, not stubbed out: a
    // download that silently did nothing would pass every test here.
    //   `Results.download`  - a link to a file the server already has.
    //   `Download.anchor`   - a file made here, which is how CSV leaves the app.
    App.Results.download = function (url, name) { opened.push([url, name]); };
    saved = [];
    // No save window here: a test must not depend on what the browser makes of its click.
    App.Download = Object.assign({}, App.Download, {
      pickFile: function () { return Promise.resolve(null); },
      anchor: function (name, text, mime) { saved.push([name, text, mime]); }
    });
    App.Results.forget();
  }

  function lines(kind) {
    return log.filter(function (entry) { return !kind || entry[0] === kind; })
              .map(function (entry) { return entry[1]; });
  }

  function said(text) {
    return lines().some(function (line) { return line.indexOf(text) !== -1; });
  }

  /* ── Not ours ─────────────────────────────────────────────────────────── */

  test('a command that is not ours is declined so the chain can continue', function () {
    setup();
    T.eq(App.Results.handleCommand('mesh'), false);
    T.eq(App.Results.handleCommand('run models/pit.py'), false);
    T.eq(App.Results.handleCommand(''), false);
    T.eq(App.Results.handleCommand('resultsomething'), false);
    T.eq(log.length, 0, 'a declined command must not write to the log');
  });

  test('the verb is recognised whatever the spacing and case', function () {
    setup();
    T.ok(App.Results.handleCommand('  RESULTS   runs  ') !== false);
  });

  /* ── Listing ──────────────────────────────────────────────────────────── */

  test('results runs asks the server once and lists newest first', function () {
    setup();
    return App.Results.handleCommand('results runs').then(function () {
      T.eq(api.calls, ['/api/results/runs']);
      var body = lines().join('\n');
      T.ok(body.indexOf('Staged_excavation') !== -1);
      T.ok(body.indexOf('column_new') !== -1);
      T.ok(body.indexOf('Staged_excavation') < body.indexOf('column_new'),
           'the newest run must be listed first');
    });
  });

  test('a run listing carries its index, date, stage count and size', function () {
    setup();
    return App.Results.handleCommand('results runs').then(function () {
      var first = lines().filter(function (line) {
        return line.indexOf('Staged_excavation_2026') !== -1;
      })[0];
      T.ok(first, 'the run was not listed at all');
      T.ok(/^\s*1\b/.test(first), 'the listing index is what `results open 1` takes');
      T.ok(first.indexOf('2026-09-22 00:49') !== -1, 'reads as a date, not as ISO');
      T.ok(first.indexOf('7 stages') !== -1);
      T.ok(first.indexOf('5.9 MB') !== -1);
    });
  });

  test('an empty runs root says so rather than printing nothing', function () {
    setup({ '/api/results/runs': { runs: [], root: '/home/x/KratosGUI/runs' } });
    return App.Results.handleCommand('results runs').then(function () {
      T.ok(said('No runs'), 'got: ' + lines().join(' | '));
      T.ok(said('/home/x/KratosGUI/runs'), 'say where it looked');
    });
  });

  /* ── Opening ──────────────────────────────────────────────────────────── */

  test('results open takes the index from the last listing', function () {
    setup();
    return App.Results.handleCommand('results runs').then(function () {
      return App.Results.handleCommand('results open 2');
    }).then(function () {
      T.eq(App.Results.current(), 'column_new_2026-09-20_22-37');
    });
  });

  test('results open takes a run id directly, with no listing first', function () {
    setup();
    return App.Results.handleCommand('results open ' + DETAIL.id).then(function () {
      T.eq(App.Results.current(), DETAIL.id);
      // The run itself first. Everything after it is the stage `open` goes straight
      // to — see "opening a run selects its last stage with results".
      T.eq(api.calls[0], '/api/results/runs/' + DETAIL.id);
    });
  });

  test('opening a run counts its files and the series of each stage', function () {
    setup();
    return App.Results.handleCommand('results open ' + DETAIL.id).then(function () {
      // The detail carries the files themselves, not a count as the listing does.
      T.ok(said(', 2 files, '), 'the file count: ' + lines().join(' | '));
      T.ok(!said('[object Object]'), 'no object in the summary: ' + lines().join(' | '));
      T.ok(said('+1 series'), 'one series: ' + lines().join(' | '));
      T.ok(!said('seriess'), '"series" is its own plural: ' + lines().join(' | '));
    });
  });

  test('an index with nothing listed yet is refused with advice', function () {
    setup();
    return App.Results.handleCommand('results open 1').then(function () {
      T.eq(App.Results.current(), null);
      T.ok(said('results runs'), 'say how to get a listing: ' + lines().join(' | '));
    });
  });

  test('an index past the end of the listing is refused', function () {
    setup();
    return App.Results.handleCommand('results runs').then(function () {
      return App.Results.handleCommand('results open 9');
    }).then(function () {
      T.eq(App.Results.current(), null);
      T.ok(said('9'));
    });
  });

  test('a run the server does not have leaves the current run alone', function () {
    setup();
    return App.Results.handleCommand('results open ' + DETAIL.id).then(function () {
      return App.Results.handleCommand('results open nope_2026-01-01_00-00');
    }).then(function () {
      T.eq(App.Results.current(), DETAIL.id, 'a failed open must not close what is open');
      T.ok(lines('err').length > 0);
    });
  });

  /* ── What an open run says ────────────────────────────────────────────── */

  test('opening a run reports its stages and whether it finished', function () {
    setup();
    return App.Results.handleCommand('results open ' + DETAIL.id).then(function () {
      T.ok(said('Initial stage'));
      T.ok(said('First excavation'));
      T.ok(said('2 stages'), 'got: ' + lines().join(' | '));
    });
  });

  test('a run that died names the stage, and says the ones before it are readable',
       function () {
    var died = JSON.parse(JSON.stringify(DETAIL));
    died.complete = false;
    died.failed_at = { index: 2, of: 7, name: '2_First_excavation' };
    // Built rather than written as a literal: this is ES5, which has no computed keys.
    var answers = {};
    answers['/api/results/runs/' + DETAIL.id] = died;
    setup(answers);
    return App.Results.handleCommand('results open ' + DETAIL.id).then(function () {
      T.ok(said('2 of 7'), 'got: ' + lines().join(' | '));
      T.ok(said('First excavation'));
    });
  });

  test('bare results with nothing open says how to open something', function () {
    setup();
    return App.Results.handleCommand('results').then(function () {
      T.ok(said('results runs'));
    });
  });

  test('bare results with a run open repeats what it is', function () {
    setup();
    return App.Results.handleCommand('results open ' + DETAIL.id).then(function () {
      log = [];
      return App.Results.handleCommand('results');
    }).then(function () {
      T.ok(said(DETAIL.id));
    });
  });

  /* ── Files ────────────────────────────────────────────────────────────── */

  test('results files lists the open run without asking the server again',
       function () {
    setup();
    return App.Results.handleCommand('results open ' + DETAIL.id).then(function () {
      api.calls = [];
      return App.Results.handleCommand('results files');
    }).then(function () {
      T.eq(api.calls, [], 'the file list came back with the run; do not re-fetch it');
      T.ok(said('Staged_excavation.mdpa'));
      T.ok(said('kratos.log'));
    });
  });

  test('results files with nothing open is refused', function () {
    setup();
    return App.Results.handleCommand('results files').then(function () {
      T.ok(said('No run'), 'got: ' + lines().join(' | '));
    });
  });

  /* ── Downloads ────────────────────────────────────────────────────────── */

  test('results get downloads one named file of the open run', function () {
    setup();
    return App.Results.handleCommand('results open ' + DETAIL.id).then(function () {
      return App.Results.handleCommand('results get kratos.log');
    }).then(function () {
      T.eq(opened, [['/api/results/runs/' + DETAIL.id + '/files/kratos.log',
                     'kratos.log']]);
    });
  });

  test('a file name is escaped into the url', function () {
    setup();
    T.eq(App.Results.fileUrl('r_2026-09-22_00-49', 'a b&c.json'),
         '/api/results/runs/r_2026-09-22_00-49/files/a%20b%26c.json');
  });

  test('results get refuses a name the open run does not have', function () {
    setup();
    return App.Results.handleCommand('results open ' + DETAIL.id).then(function () {
      return App.Results.handleCommand('results get nothing.json');
    }).then(function () {
      T.eq(opened, [], 'do not ask the server for a file the listing says is absent');
      T.ok(said('nothing.json'));
    });
  });

  test('results zip downloads the whole run under the run name', function () {
    setup();
    return App.Results.handleCommand('results open ' + DETAIL.id).then(function () {
      return App.Results.handleCommand('results zip');
    }).then(function () {
      T.eq(opened, [['/api/results/runs/' + DETAIL.id + '/archive',
                     DETAIL.id + '.zip']]);
    });
  });

  test('the download url honours a cross-origin api base', function () {
    setup();
    App.Api.base = 'http://127.0.0.1:8000';
    T.eq(App.Results.fileUrl('r_2026-09-22_00-49', 'kratos.log'),
         'http://127.0.0.1:8000/api/results/runs/r_2026-09-22_00-49/files/kratos.log');
  });

  /* ── The run that just finished ───────────────────────────────────────── */

  test('a finished calculation becomes the current run with no listing needed',
       function () {
    setup();
    App.Results.remember({ run: DETAIL.id, directory: 'C:\\x\\' + DETAIL.id, ok: true });

    T.eq(App.Results.current(), DETAIL.id);
  });

  test('a calculation that could not start leaves the current run alone', function () {
    setup();
    App.Results.remember({ run: DETAIL.id, ok: true });
    App.Results.remember(undefined);
    App.Results.remember({});

    T.eq(App.Results.current(), DETAIL.id);
  });

  test('an older server that sends no run id falls back to the directory name',
       function () {
    setup();
    App.Results.remember({ directory: 'C:\\Users\\x\\KratosGUI\\runs\\' + DETAIL.id });
    T.eq(App.Results.current(), DETAIL.id);

    App.Results.forget();
    App.Results.remember({ directory: '/home/x/KratosGUI/runs/' + DETAIL.id });
    T.eq(App.Results.current(), DETAIL.id);
  });

  /* ── The handoff from Calculate (P0.4) ────────────────────────────────── */

  /* The real `App.Calculate.run`, not a re-enactment of it: the point of these three
     is that pressing Calculate leaves a run open, and a test that called `remember`
     itself would pass even if calculate.js never did. */

  function calculating(answer) {
    App.Export = { meshRequest: function () { return { element_size: 1 }; } };
    App.Api.post = function (path, body) {
      api.calls.push(path);
      return answer instanceof Error ? Promise.reject(answer) : Promise.resolve(answer);
    };
  }

  var FINISHED = {
    ok: true, seconds: 12.5, directory: 'C:\\Users\\x\\KratosGUI\\runs\\' + DETAIL.id,
    run: DETAIL.id, outputs: ['a.post.res'], log: 'kratos.log',
    stats: { nodes: 4400, elements: 2100 }, warnings: []
  };

  test('a finished calculation leaves its run open, with no round trip', function () {
    setup();
    calculating(FINISHED);
    return App.Calculate.run().then(function () {
      T.eq(App.Results.current(), DETAIL.id);
      T.eq(api.calls[0], '/api/calculate', 'the run id came back with the run');
      T.ok(said('results files'), 'say that it is open: ' + lines().join(' | '));
    });
  });

  test('a finished calculation is READ, not just named', function () {
    /* The bug this pins: `remember` used to record the id and nothing else, so the
       run was "open" with no stages in it. The Results panel drew an empty stage
       dropdown, every field said "this stage wrote nothing", and the only way out
       was to type `results open <the id it was already showing>`.

       Pressing Calculate has to leave a run that can be looked at. */
    setup();
    viewing();
    calculating(FINISHED);
    return App.Calculate.run().then(function () {
      return App.Results.ready();
    }).then(function () {
      T.eq(App.Results.current(), DETAIL.id);
      T.eq(App.Results.state().stages.length, 2, 'the run was read');
      T.eq(App.Results.stage(), 2, 'and a stage was chosen');
    });
  });

  test('forgetting leaves no run, no field and the defaults back', function () {
    /* What `patches.js` calls when a different project is opened. A run's results
       belong to the document that produced them, and the contour lives in a group of
       its own that `Viewport.refresh()` does not touch -- so without this it sits over
       the new site looking like the new site's answer. */
    setup();
    viewing();
    return App.Results.handleCommand('results open ' + DETAIL.id).then(function () {
      return App.Results.handleCommand('results bands 8');
    }).then(function () {
      T.ok(App.Results.current(), 'a run is open to begin with');
      T.ok(App.Results.field(), 'and something is on screen');

      var beats = 0;
      App.Results.onChange(function () { beats += 1; });
      App.Results.forget();

      T.eq(App.Results.current(), null);
      T.eq(App.Results.field(), null);
      T.eq(App.Results.stage(), null);
      T.eq(App.Results.state().stages, []);
      T.eq(App.Results.options().bands, 32, 'display options go back to default');
      T.ok(beats > 0, 'and the panel is told, or it keeps offering the old stages');
    });
  });

  test('anything that changes what is on screen notifies whoever is drawing a panel',
       function () {
    /* The panel cannot poll and must not duplicate this module's state, so it
       subscribes. Without this the panel is built from whatever was true at the
       moment the mode was entered and never updates again -- which is what made a
       finished calculation look like an empty run. */
    setup();
    viewing();
    var beats = 0;
    App.Results.onChange(function () { beats += 1; });

    return App.Results.handleCommand('results open ' + DETAIL.id).then(function () {
      T.ok(beats > 0, 'opening a run is a change');
      var before = beats;
      return App.Results.handleCommand('results bands 6').then(function () {
        T.ok(beats > before, 'so is a display option');
      });
    });
  });

  test('a failed calculation still leaves its run open, because it wrote files too',
       function () {
    setup();
    var died = JSON.parse(JSON.stringify(FINISHED));
    died.ok = false;
    died.returncode = 1;
    died.error = 'the solver did not converge';
    died.stage = { index: 2, of: 7, name: '2_First_excavation' };
    calculating(died);
    return App.Calculate.run().then(function () {
      T.eq(App.Results.current(), DETAIL.id,
           'the deck and the log are there whether or not Kratos was happy');
    });
  });

  test('a calculation that never reached the server opens nothing', function () {
    setup();
    calculating(new Error('Cannot reach the model server'));
    return App.Calculate.run().then(function () {
      T.eq(App.Results.current(), null);
    });
  });

  /* ── Choosing a stage and a field (P2) ────────────────────────────────── */

  /* `App.Results.draw` is what the viewport implements. Replaced here, like
     `download`, so the decisions can be checked without a canvas: what is drawn, with
     which range, at which location, and how often. */

  var MESH = {
    dimension: 2, bbox: [0, -10, 0, 20, 0, 0],
    sections: [{ key: 'results:Soil_Top', part: 'Soil_Top', kind: 'continuum',
                 color: '#b6ac97', node_ids: [1, 2, 3],
                 positions: [0, 0, 0, 1, 0, 0, 0, 1, 0],
                 indices: [0, 1, 2], edges: [] }]
  };

  var CATALOGUE = {
    stage: { index: 1, name: '1_Initial_stage', stage: 'Initial stage' },
    groups: [
      { name: 'Deformations', fields: [
          { name: 'u', label: '|u|', unit: 'm', locations: ['nodes'] },
          { name: 'uy', label: 'u_y', unit: 'm', locations: ['nodes'] }] },
      { name: 'Effective stresses', fields: [
          { name: 'p', label: "p' (mean)", unit: 'kPa',
            locations: ['elements', 'nodes'] }] }
    ]
  };

  function FIELD(name, unit, location) {
    return { field: name, label: name, unit: unit || 'm',
             location: location || 'nodes',
             ids: [1, 2, 3], values: [0, -0.5, -1], min: -1, max: 0 };
  }

  var drawn;

  function viewing() {
    /* A server that answers the stage routes too. Layered over `setup`'s doubles. */
    drawn = [];
    var base = App.Api.get;
    App.Api.get = function (path) {
      api.calls.push(path);
      if (/\/stages\/\d+\/mesh$/.test(path)) return Promise.resolve(MESH);
      if (/\/stages\/\d+\/fields$/.test(path)) return Promise.resolve(CATALOGUE);
      var field = path.match(/\/field\/([^?]+)/);
      if (field) {
        var unit = field[1] === 'p' ? 'kPa' : 'm';
        var location = /location=elements/.test(path) ? 'elements' : 'nodes';
        return Promise.resolve(FIELD(field[1], unit, location));
      }
      if (/\/at\/\d+$/.test(path)) {
        return Promise.resolve({ node: 2, at: [1, 0, 0], values: [
          { group: 'Deformations', field: 'uy', label: 'u_y', unit: 'm', value: -0.5 },
          { group: 'Effective stresses', field: 'p', label: "p'", unit: 'kPa',
            value: null }] });
      }
      api.calls.pop();
      return base(path);
    };
    App.Results.draw = function (view) { drawn.push(view); };
  }

  /* Named `showing`, not `opened`: `opened` is the download recorder above, and
     `setup()` reassigns it to an array — a helper of that name is a function until the
     first test runs and an array afterwards. */
  function showing() {
    setup();
    viewing();
    return App.Results.handleCommand('results open ' + DETAIL.id);
  }

  test('opening a run selects its last stage with results', function () {
    /* The one you almost always want: the end of the construction sequence. */
    return showing().then(function () {
      T.eq(App.Results.stage(), 2);
    });
  });

  test('opening a run draws something without anything being typed', function () {
    /* An empty viewport in Results mode is indistinguishable from a broken one.
       This catalogue has no stage displacements, so the preference falls through to
       the next best thing it does have: total vertical displacement, which is the
       same quantity measured from the start of the model rather than of the stage. */
    return showing().then(function () {
      T.ok(drawn.length > 0, 'nothing was drawn');
      T.eq(drawn[drawn.length - 1].field.field, 'uy');
      T.eq(App.Results.field().field, 'uy');
    });
  });

  test('the default field is the vertical stage displacement when the stage has it',
       function () {
    /* What settles after an excavation step, and what gets looked at first. Chosen by
       name rather than by position so that a stage which did not write DISPLACEMENT
       falls through to whatever it did write instead of drawing nothing. */
    setup();
    viewing();
    var withStage = JSON.parse(JSON.stringify(CATALOGUE));
    withStage.groups.splice(1, 0, { name: 'Stage deformations', fields: [
      { name: 'du', label: '|Δu|', unit: 'm', locations: ['nodes'] },
      { name: 'duy', label: 'Δu_y', unit: 'm', locations: ['nodes'] }] });
    var base = App.Api.get;
    App.Api.get = function (path) {
      if (/\/fields$/.test(path)) { api.calls.push(path); return Promise.resolve(withStage); }
      return base(path);
    };

    return App.Results.handleCommand('results open ' + DETAIL.id).then(function () {
      T.eq(App.Results.field().field, 'duy');
    });
  });

  test('the default shading and colour map are what gets set up on every run',
       function () {
    setup();
    viewing();
    return App.Results.handleCommand('results open ' + DETAIL.id).then(function () {
      var options = App.Results.options();
      T.eq(options.bands, 32);
      T.eq(options.map, 'rainbow');
      T.eq(drawn[drawn.length - 1].options.bands, 32, 'and they reach the viewport');
      T.eq(drawn[drawn.length - 1].options.map, 'rainbow');
    });
  });

  test('a stage that offers nothing draws nothing rather than failing', function () {
    setup();
    viewing();
    var empty = { stage: { index: 1 }, groups: [] };
    var base = App.Api.get;
    App.Api.get = function (path) {
      return /\/fields$/.test(path) ? (api.calls.push(path), Promise.resolve(empty))
                                    : base(path);
    };
    return App.Results.handleCommand('results open ' + DETAIL.id).then(function () {
      T.eq(App.Results.field(), null);
      T.eq(drawn.length, 0);
    });
  });

  test('results stage chooses a stage by number', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results stage 1');
    }).then(function () {
      T.eq(App.Results.stage(), 1);
      T.ok(api.calls.some(function (p) { return /\/stages\/1\/mesh$/.test(p); }),
           'the stage mesh is fetched: ' + api.calls.join(' '));
    });
  });

  test('results stage chooses a stage by name, however it is spelled', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results stage first excavation');
    }).then(function () {
      T.eq(App.Results.stage(), 2, 'matched "2_First_excavation"');
    });
  });

  test('results stage + and - step through the construction sequence', function () {
    /* What the Results menu's "Next stage" and "Previous stage" run, and the thing
       this mode is most used for: one quantity, walked forwards through the build. */
    return showing().then(function () {
      T.eq(App.Results.stage(), 2, 'opened on the last stage');
      return App.Results.handleCommand('results stage -');
    }).then(function () {
      T.eq(App.Results.stage(), 1);
      return App.Results.handleCommand('results stage +');
    }).then(function () {
      T.eq(App.Results.stage(), 2);
    });
  });

  test('stepping past either end stays put and says so', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results stage +');
    }).then(function () {
      T.eq(App.Results.stage(), 2, 'already at the last stage');
      T.ok(said('last'), 'got: ' + lines().join(' | '));
      return App.Results.handleCommand('results stage 1');
    }).then(function () {
      log = [];
      return App.Results.handleCommand('results stage -');
    }).then(function () {
      T.eq(App.Results.stage(), 1);
      T.ok(said('first'), 'got: ' + lines().join(' | '));
    });
  });

  test('stepping skips a stage that wrote no results', function () {
    /* A run that died partway leaves gaps. Stepping has to land on something
       readable rather than on a stage that cannot be drawn. */
    setup();
    viewing();
    var gapped = JSON.parse(JSON.stringify(DETAIL));
    gapped.stages.push({ index: 3, name: '3_Strut', stage: 'Strut', results: false,
                         mesh_file: null, results_file: null, json: [] });
    gapped.stages.push({ index: 4, name: '4_Dig', stage: 'Dig', results: true,
                         mesh_file: 'm', results_file: 'r', json: [] });
    var base = App.Api.get;
    App.Api.get = function (path) {
      if (path === '/api/results/runs/' + DETAIL.id) {
        api.calls.push(path);
        return Promise.resolve(gapped);
      }
      return base(path);
    };
    return App.Results.handleCommand('results open ' + DETAIL.id).then(function () {
      T.eq(App.Results.stage(), 4, 'opened on the last readable stage');
      return App.Results.handleCommand('results stage -');
    }).then(function () {
      T.eq(App.Results.stage(), 2, 'stage 3 wrote nothing, so it is stepped over');
    });
  });

  test('a stage that does not exist leaves the current one alone', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results stage 9');
    }).then(function () {
      T.eq(App.Results.stage(), 2);
      T.ok(lines('err').length > 0);
    });
  });

  test('results fields lists what this stage offers, by group', function () {
    return showing().then(function () {
      log = [];
      return App.Results.handleCommand('results fields');
    }).then(function () {
      T.ok(said('Deformations'));
      T.ok(said('|u|'));
      T.ok(said('kPa'), 'the unit is shown: ' + lines().join(' | '));
    });
  });

  test('results field draws it and says its range', function () {
    return showing().then(function () {
      log = [];
      drawn = [];   // opening the run already drew the default field
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      T.eq(drawn.length, 1);
      T.eq(drawn[0].field.field, 'uy');
      T.eq(drawn[0].mesh.sections.length, 1);
      T.ok(said('-1'), 'the range is reported: ' + lines().join(' | '));
      T.ok(said('m'));
    });
  });

  test('a field is asked for at a location it supports', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results field p elements');
    }).then(function () {
      T.ok(api.calls.some(function (p) { return /location=elements/.test(p); }),
           'got: ' + api.calls.join(' '));
      T.eq(App.Results.location(), 'elements');
    });
  });

  test('a field this stage does not have is refused before any request', function () {
    return showing().then(function () {
      api.calls = [];
      return App.Results.handleCommand('results field wibble');
    }).then(function () {
      T.eq(api.calls, [], 'the catalogue already said it is not there');
      T.ok(said('wibble'));
      T.ok(said('results fields'), 'say how to find the real ones');
    });
  });

  test('changing stage redraws the field that was on screen', function () {
    /* Stepping through the construction sequence on one quantity is the single most
       useful thing this mode does, and having to retype the field each time would
       make it unusable. */
    return showing().then(function () {
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      drawn = [];
      return App.Results.handleCommand('results stage 1');
    }).then(function () {
      T.eq(drawn.length, 1);
      T.eq(drawn[0].field.field, 'uy');
    });
  });

  /* ── Display options ──────────────────────────────────────────────────── */

  test('bands and smooth toggle the same setting', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      return App.Results.handleCommand('results bands 8');
    }).then(function () {
      T.eq(drawn[drawn.length - 1].options.bands, 8);
      return App.Results.handleCommand('results smooth');
    }).then(function () {
      T.eq(drawn[drawn.length - 1].options.bands, 0);
    });
  });

  test('an option redraws without asking the server again', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      api.calls = [];
      drawn = [];
      return App.Results.handleCommand('results bands 6');
    }).then(function () {
      T.eq(api.calls, [], 'the values are already here; only the colours change');
      T.eq(drawn.length, 1);
    });
  });

  test('results range takes two numbers and holds them across a stage change', function () {
    /* What makes two stages comparable: a range that moves with each stage makes
       every stage look the same. */
    return showing().then(function () {
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      return App.Results.handleCommand('results range -2 0');
    }).then(function () {
      T.eq(drawn[drawn.length - 1].options.min, -2);
      T.eq(drawn[drawn.length - 1].options.max, 0);
      return App.Results.handleCommand('results stage 1');
    }).then(function () {
      T.eq(drawn[drawn.length - 1].options.min, -2, 'a typed range is not recomputed');
    });
  });

  test('results range auto follows the field again', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      return App.Results.handleCommand('results range -99 99');
    }).then(function () {
      return App.Results.handleCommand('results range auto');
    }).then(function () {
      T.eq(drawn[drawn.length - 1].options.min, -1, 'back to the field own minimum');
    });
  });

  /* The legend's Min and Max boxes in the Results panel. They do not set anything
     themselves: `limitsCommand` turns what was typed into the `results range` above,
     so the boxes, the command box and the menu are one implementation. */

  test('two typed limits become results range', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      T.eq(App.Results.limitsCommand('-2', '0.5'), 'results range -2 0.5');
    });
  });

  test('both limits emptied is the automatic range again', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      T.eq(App.Results.limitsCommand('', '  '), 'results range auto');
    });
  });

  test('one limit typed keeps the other end where the legend has it', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      // uy here runs -1 .. 0, so leaving Max empty keeps 0.
      T.eq(App.Results.limitsCommand('-0.5', ''), 'results range -0.5 0');
      return App.Results.handleCommand('results range -3 2');
    }).then(function () {
      // A typed range is what the legend has now, so it is the end that is kept.
      T.eq(App.Results.limitsCommand('', '5'), 'results range -3 5');
    });
  });

  test('a decimal comma is read as a decimal point', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      T.eq(App.Results.limitsCommand('-0,25', '1,5'), 'results range -0.25 1.5');
    });
  });

  test('a limit that is not a number is refused with a reason', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      log.length = 0;
      T.eq(App.Results.limitsCommand('abc', '1'), null);
      T.ok(log.some(function (line) { return line[0] === 'err' && /abc/.test(line[1]); }),
           JSON.stringify(log));
    });
  });

  test('equal limits are refused, since there would be no colours between them', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      T.eq(App.Results.limitsCommand('2', '2'), null);
    });
  });

  test('limits with nothing on screen are refused', function () {
    setup();
    T.eq(App.Results.limitsCommand('1', '2'), null);
  });

  /* ── Replies that arrive after the user has moved on (finding F7) ────────

     Pressing `results stage +` twice quickly, or picking one field and then another,
     leaves the first request in flight. Its reply must not be taken for the second's:
     it used to be tagged with whatever stage was current when it *arrived*, cached
     under that stage, and drawn there. */

  function held(pattern, answer) {
    /* App.Api.get, with requests matching `pattern` held until `release()`. */
    var waiting = [];
    var base = App.Api.get;
    App.Api.get = function (path) {
      var match = path.match(pattern);
      if (match) {
        return new Promise(function (resolve) {
          waiting.push(function () { resolve(answer(match)); });
        });
      }
      return base(path);
    };
    return function release() {
      App.Api.get = base;
      waiting.splice(0).forEach(function (go) { go(); });
    };
  }

  function markedMesh(stage) {
    var mesh = JSON.parse(JSON.stringify(MESH));
    mesh.which = stage;
    return mesh;
  }

  test('a late reply for a stage already left is dropped', function () {
    var release, first;
    return showing().then(function () {
      var base = App.Api.get;
      App.Api.get = function (path) {
        if (/\/stages\/2\/mesh$/.test(path)) return Promise.resolve(markedMesh(2));
        return base(path);
      };
      release = held(/\/stages\/(1)\/mesh$/, function () { return markedMesh(1); });
      first = App.Results.handleCommand('results stage 1');
      return App.Results.handleCommand('results stage 2');
    }).then(function () {
      release();
      return first;
    }).then(function () {
      T.eq(App.Results.stage(), 2, 'still on the stage chosen last');
      var last = drawn[drawn.length - 1];
      T.eq(last.stage, 2);
      T.eq(last.mesh.which, 2, 'drawn on the mesh of the stage shown');
    });
  });

  test("a late displacement reply is not cached as another stage's", function () {
    var release, firstStep;
    function vectors(stage) {
      return { source: 'TOTAL_DISPLACEMENT', ids: [1, 2, 3],
               values: [[stage, 0, 0], [stage, 0, 0], [stage, 0, 0]] };
    }
    return showing().then(function () {
      return App.Results.handleCommand('results deform 10');
    }).then(function () {
      var base = App.Api.get;
      App.Api.get = function (path) {
        var at = path.match(/\/stages\/(2)\/displacement$/);
        if (at) return Promise.resolve(vectors(2));
        return base(path);
      };
      release = held(/\/stages\/(1)\/displacement$/, function () { return vectors(1); });
      firstStep = App.Results.handleCommand('results stage 1');
    }).then(function () {
      return App.Results.handleCommand('results stage 2');
    }).then(function () {
      release();
      return firstStep;
    }).then(function () {
      return App.Results.handleCommand('results deform 20');
    }).then(function () {
      var last = drawn[drawn.length - 1];
      T.eq(last.stage, 2);
      T.ok(last.displacement && last.displacement.stage === 2,
           'displacement belongs to stage 2: ' + JSON.stringify(last.displacement));
      T.eq(last.displacement.values[0][0], 2, "stage 2's own vectors");
    });
  });

  test('a late field reply does not replace the field chosen after it', function () {
    var release, first;
    return showing().then(function () {
      release = held(/\/field\/(p)\?/, function () { return FIELD('p', 'kPa', 'nodes'); });
      first = App.Results.handleCommand('results field p');
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      release();
      return first;
    }).then(function () {
      T.eq(App.Results.field().field, 'uy');
      T.eq(drawn[drawn.length - 1].field.field, 'uy');
    });
  });

  test('a reply for a run no longer open is dropped', function () {
    var release, first;
    return showing().then(function () {
      release = held(/\/stages\/(1)\/fields$/, function () { return CATALOGUE; });
      first = App.Results.handleCommand('results stage 1');
      App.Results.forget();
      release();
      return first;
    }).then(function () {
      T.eq(App.Results.stage(), null, 'forgetting the run leaves nothing on screen');
    });
  });

  test('results deform takes a factor, auto, or off', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      return App.Results.handleCommand('results deform 50');
    }).then(function () {
      T.eq(drawn[drawn.length - 1].options.deform, 50);
      return App.Results.handleCommand('results deform off');
    }).then(function () {
      T.eq(drawn[drawn.length - 1].options.deform, 0);
      return App.Results.handleCommand('results deform auto');
    }).then(function () {
      T.eq(drawn[drawn.length - 1].options.deform, 'auto');
    });
  });

  test('a display option with no field on screen is remembered, not lost', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results bands 5');
    }).then(function () {
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      T.eq(drawn[drawn.length - 1].options.bands, 5);
    });
  });

  test('results reverse toggles, and on/off set it outright', function () {
    /* A bare `results reverse` flips it, which is what it is reached for. `on`/`off`
       exist so a checkbox and a ticked menu item can *set* it — toggling from a
       control that already shows the state inverts whatever the module happened to
       think, and the two drift apart the first time they disagree. */
    return showing().then(function () {
      T.eq(App.Results.options().reversed, false, 'not reversed by default');
      return App.Results.handleCommand('results reverse');
    }).then(function () {
      T.eq(App.Results.options().reversed, true);
      T.eq(drawn[drawn.length - 1].options.reversed, true, 'and it reaches the viewport');
      return App.Results.handleCommand('results reverse');
    }).then(function () {
      T.eq(App.Results.options().reversed, false);
      return App.Results.handleCommand('results reverse on');
    }).then(function () {
      T.eq(App.Results.options().reversed, true);
      return App.Results.handleCommand('results reverse on');
    }).then(function () {
      T.eq(App.Results.options().reversed, true, 'setting it twice is not a toggle');
      return App.Results.handleCommand('results reverse off');
    }).then(function () {
      T.eq(App.Results.options().reversed, false);
    });
  });

  test('results mesh draws the element outlines over the shading, and takes it off', function () {
    /* Off by default: a contour is read for its colours, and the line work is asked
       for when the mesh itself is the question. Toggled like `reverse`, and set
       outright by on/off so the panel's checkbox and the menu's tick cannot drift. */
    return showing().then(function () {
      T.eq(App.Results.options().mesh, false, 'no mesh by default');
      T.eq(drawn[drawn.length - 1].options.mesh, false, 'and the viewport is told so');
      return App.Results.handleCommand('results mesh');
    }).then(function () {
      T.eq(App.Results.options().mesh, true);
      T.eq(drawn[drawn.length - 1].options.mesh, true, 'it reaches the viewport');
      T.ok(log.some(function (line) { return /mesh on/.test(line[1]); }),
           'the settings line says so');
      return App.Results.handleCommand('results mesh');
    }).then(function () {
      T.eq(App.Results.options().mesh, false);
      return App.Results.handleCommand('results mesh on');
    }).then(function () {
      return App.Results.handleCommand('results mesh on');
    }).then(function () {
      T.eq(App.Results.options().mesh, true, 'setting it twice is not a toggle');
      return App.Results.handleCommand('results mesh off');
    }).then(function () {
      T.eq(App.Results.options().mesh, false);
    });
  });

  test('results loads takes the loads and the water off the shading, and puts them back',
       function () {
    /* On by default: the user reads a result against where the load is and where the
       water stands. Set and toggled like `mesh`. */
    return showing().then(function () {
      T.eq(App.Results.options().loads, true, 'shown by default');
      return App.Results.handleCommand('results loads off');
    }).then(function () {
      T.eq(App.Results.options().loads, false);
      T.ok(log.some(function (line) { return /loads off/.test(line[1]); }),
           'the settings line says so');
      return App.Results.handleCommand('results loads');
    }).then(function () {
      T.eq(App.Results.options().loads, true, 'a bare `results loads` toggles');
      App.Results.forget();
      T.eq(App.Results.options().loads, true, 'back on for the next project');
    });
  });

  /* ── The zero water pressure line ─────────────────────────────────────── */

  /* A run whose stages solved `calculation`, and a stage catalogue with a water
     pressure in it to trace the line on. */
  function showingWater(calculation, withPressure) {
    var detail = JSON.parse(JSON.stringify(DETAIL));
    detail.stages.forEach(function (s) { s.calculation = calculation; });
    var answers = {};
    answers['/api/results/runs/' + DETAIL.id] = detail;
    setup(answers);
    viewing();
    var catalogue = JSON.parse(JSON.stringify(CATALOGUE));
    if (withPressure !== false) {
      catalogue.groups.push({ name: 'Groundwater', fields: [
        { name: 'pw', label: 'Pore pressure', unit: 'kPa', locations: ['nodes'] }] });
    }
    var below = App.Api.get;
    App.Api.get = function (path) {
      if (/\/stages\/\d+\/fields$/.test(path)) {
        api.calls.push(path);
        return Promise.resolve(catalogue);
      }
      return below(path);
    };
    return App.Results.handleCommand('results open ' + DETAIL.id);
  }

  function pressureCalls() {
    return api.calls.filter(function (path) { return /\/field\/pw\?/.test(path); });
  }

  test('after a flow stage the zero pressure line is drawn without being asked for',
       function () {
    return showingWater('flow').then(function () {
      var last = drawn[drawn.length - 1];
      T.eq(last.field.field, 'uy', 'the field on screen is still the default one');
      T.ok(last.pressure, 'the water pressure travels with the payload');
      T.eq(last.pressure.field, 'pw');
      T.eq(pressureCalls(), ['/api/results/runs/' + DETAIL.id
                             + '/stages/2/field/pw?location=nodes']);
      T.eq(App.Results.options().zeroLine, false, 'the coupled setting is left alone');
      T.eq(App.Results.state().calculation, 'flow');
    });
  });

  test('a flow stage draws the line even with the coupled setting off', function () {
    return showingWater('flow').then(function () {
      return App.Results.handleCommand('results zeroline off');
    }).then(function () {
      T.ok(drawn[drawn.length - 1].pressure, 'still drawn');
    });
  });

  test('after a coupled stage the zero pressure line is off until it is asked for',
       function () {
    return showingWater('mechanical').then(function () {
      T.eq(drawn[drawn.length - 1].pressure, null, 'not drawn by default');
      T.eq(pressureCalls().length, 0, 'and not fetched either');
      return App.Results.handleCommand('results zeroline on');
    }).then(function () {
      T.eq(App.Results.options().zeroLine, true);
      T.eq(drawn[drawn.length - 1].pressure.field, 'pw');
      T.ok(log.some(function (line) { return /zero pressure line on/.test(line[1]); }),
           'the settings line says so');
      return App.Results.handleCommand('results stage 1');
    }).then(function () {
      T.ok(drawn[drawn.length - 1].pressure, 'kept on from one stage to the next');
      T.eq(pressureCalls().length, 2, 'fetched once per stage');
      return App.Results.handleCommand('results zeroline');
    }).then(function () {
      T.eq(App.Results.options().zeroLine, false, 'a bare `results zeroline` toggles');
      T.eq(drawn[drawn.length - 1].pressure, null);
      App.Results.handleCommand('results zeroline on');
      App.Results.forget();
      T.eq(App.Results.options().zeroLine, false, 'off again for the next project');
    });
  });

  test('the zero pressure line reuses the pore pressure when that is the field shown',
       function () {
    return showingWater('mechanical').then(function () {
      return App.Results.handleCommand('results field pw');
    }).then(function () {
      T.eq(pressureCalls().length, 1, 'the field itself');
      return App.Results.handleCommand('results zeroline on');
    }).then(function () {
      T.eq(pressureCalls().length, 1, 'the line is traced on the field already here');
      T.eq(drawn[drawn.length - 1].pressure, App.Results.field());
      return App.Results.handleCommand('results bands 8');
    }).then(function () {
      T.eq(pressureCalls().length, 1, 'a display option fetches nothing again');
      T.ok(drawn[drawn.length - 1].pressure);
    });
  });

  test('a stage with no water pressure has no zero pressure line', function () {
    return showingWater('flow', false).then(function () {
      T.eq(drawn[drawn.length - 1].pressure, null);
      T.eq(pressureCalls().length, 0);
      T.eq(App.Results.state().pressure, false);
      T.eq(App.Results.zeroLineShown(), false);
    });
  });

  test('a run that does not say what it solved is treated as coupled', function () {
    /* A run directory from before stages carried their calculation type. */
    return showingWater(undefined).then(function () {
      T.eq(App.Results.state().calculation, null);
      T.eq(drawn[drawn.length - 1].pressure, null);
    });
  });

  test('a pressure the server cannot send draws no line rather than an error', function () {
    return showingWater('mechanical').then(function () {
      var below = App.Api.get;
      App.Api.get = function (path) {
        if (/\/field\/pw\?/.test(path)) {
          api.calls.push(path);
          return Promise.reject(new Error('gone'));
        }
        return below(path);
      };
      log = [];
      return App.Results.handleCommand('results zeroline on');
    }).then(function () {
      T.eq(pressureCalls().length, 1, 'it was asked for');
      var last = drawn[drawn.length - 1];
      T.eq(last.pressure, null, 'no line');
      T.eq(last.field.field, 'uy', 'the contour is still drawn');
      T.eq(lines('err'), [], 'and nothing is reported as failed');
    });
  });

  test('the zero line carries the phreatic lines of the open project for the stage shown',
       function () {
    /* The open project is the one the run was made from: same deck name, same stages. */
    var saved = { project: App.PROJECT, stages: App.Stages, water: App.SurfaceWater };
    var asked = [];
    App.PROJECT = { name: 'Staged excavation', dimension: 2,
                    stages: [{ id: 's1', name: 'Initial stage' },
                             { id: 's2', name: 'First excavation' }] };
    App.Stages = {
      order: function (project) { return project.stages; },
      hiddenKeys: function (project, stage, kind) {
        asked.push([stage, kind]);
        return ['excavated'];
      }
    };
    App.SurfaceWater = {
      waters: function (project, hidden) {
        asked.push(hidden);
        return [{ x_coordinates: [0, 10, 20], y_coordinates: [-2, -3, -3] }];
      }
    };
    function restore() {
      App.PROJECT = saved.project;
      App.Stages = saved.stages;
      App.SurfaceWater = saved.water;
    }
    return showingWater('flow').then(function () {
      var last = drawn[drawn.length - 1];
      T.ok(last.pressure, 'the line is on');
      T.eq(last.phreatic, [[[0, -2], [10, -3], [20, -3]]], 'as [x, y] polylines');
      T.eq(asked[0], ['s2', 'staged'], "the stage on screen's own id");
      T.eq(asked[1], { excavated: true }, 'with what that stage takes away left out');
      App.PROJECT = Object.assign({}, App.PROJECT, { name: 'Another project' });
      return App.Results.handleCommand('results bands 8');
    }).then(function () {
      T.eq(drawn[drawn.length - 1].phreatic, [], "another project's water says nothing");
      restore();
    }, function (error) {
      restore();
      throw error;
    });
  });

  /* ── Saved pictures: walking the stages and fields ───────────────────── */

  test('the field names are every field the stage offers, in menu order', function () {
    return showing().then(function () {
      T.eq(App.Results.fieldNames(), ['u', 'uy', 'p']);
    });
  });

  test('show moves to a stage and field without a line in the log for each', function () {
    return showing().then(function () {
      log = [];
      return App.Results.show(1, 'p');
    }).then(function () {
      T.eq(App.Results.stage(), 1);
      T.eq(App.Results.field().field, 'p');
      T.eq(lines('ok'), [], 'quiet');
      return App.Results.show(1, 'p');
    }).then(function (answer) {
      T.eq(answer, null, 'already there: nothing to do');
      return App.Results.show(1);
    }).then(function (answer) {
      T.eq(answer, null, 'no field named: the stage alone');
    });
  });

  /* ── Integration points: per element or averaged to the nodes ────────── */

  function fieldCalls(name) {
    return api.calls.filter(function (path) {
      return path.indexOf('/field/' + name + '?') !== -1;
    });
  }

  test('an integration-point field is drawn per element until asked otherwise',
       function () {
    return showing().then(function () {
      return App.Results.handleCommand('results field p');
    }).then(function () {
      T.eq(App.Results.location(), 'elements');
      T.eq(App.Results.state().integration, 'elements');
      T.eq(App.Results.state().integrationField, true);
      T.ok(said('per element'), lines().join(' | '));
    });
  });

  test('results location nodes redraws the field averaged to the nodes, and keeps it',
       function () {
    return showing().then(function () {
      return App.Results.handleCommand('results field p');
    }).then(function () {
      return App.Results.handleCommand('results location nodes');
    }).then(function () {
      T.eq(App.Results.location(), 'nodes');
      T.ok(/location=nodes$/.test(fieldCalls('p').pop()));
      T.ok(said('averaged to the nodes'), lines().join(' | '));
      // A nodal field in between, then back: still averaged to the nodes.
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      T.eq(App.Results.state().integrationField, false, 'u_y is nodal only');
      return App.Results.handleCommand('results field p');
    }).then(function () {
      T.eq(App.Results.location(), 'nodes');
      return App.Results.handleCommand('results stage 1');
    }).then(function () {
      T.eq(App.Results.location(), 'nodes', 'and from one stage to the next');
      App.Results.forget();
      T.eq(App.Results.options().location, 'elements', 'per element for the next project');
    });
  });

  test('a location typed with the field is the choice for the next one too', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results field p nodes');
    }).then(function () {
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      return App.Results.handleCommand('results field p');
    }).then(function () {
      T.eq(App.Results.location(), 'nodes');
    });
  });

  test('results location with a nodal field on screen is remembered, not refused',
       function () {
    return showing().then(function () {
      api.calls = [];
      return App.Results.handleCommand('results location nodes');
    }).then(function () {
      T.eq(App.Results.options().location, 'nodes');
      T.eq(fieldCalls('uy').length, 0, 'u_y is not fetched again');
      T.eq(lines('err').length, 0);
      return App.Results.handleCommand('results location sideways');
    }).then(function () {
      T.ok(said('Usage: results location'));
    });
  });

  /* ── Arrows ───────────────────────────────────────────────────────────── */

  var VECTORS = { field: 'flux', label: '|q|', unit: 'm/s', source: 'FLUID_FLUX_VECTOR',
                  ids: [1, 2, 3], values: [[1, 0, 0], [0, 1, 0], [0, 0, 0]], max: 1 };

  /* The default catalogue, with the flux and the head of a flow stage. */
  function showingFlow() {
    setup();
    viewing();
    var catalogue = JSON.parse(JSON.stringify(CATALOGUE));
    catalogue.groups[0].fields.forEach(function (entry) { entry.vector = 'u'; });
    catalogue.groups.push({ name: 'Water pressure and head', fields: [
      { name: 'head', label: 'Hydraulic head', unit: 'm',
        locations: ['elements', 'nodes'] }] });
    catalogue.groups.push({ name: 'Groundwater flow', fields: [
      { name: 'flux', label: '|q|', unit: 'm/s', locations: ['nodes'], vector: 'flux' },
      { name: 'fluxx', label: 'q_x', unit: 'm/s', locations: ['nodes'], vector: 'flux' },
      { name: 'flow_rate', label: 'Nodal water flow rate (+ out)', unit: 'm³/s/m',
        locations: ['nodes'] }] });
    var below = App.Api.get;
    App.Api.get = function (path) {
      if (/\/stages\/\d+\/fields$/.test(path)) {
        api.calls.push(path);
        return Promise.resolve(catalogue);
      }
      if (/\/vectors\//.test(path)) {
        api.calls.push(path);
        var name = decodeURIComponent(path.split('/vectors/')[1]);
        return Promise.resolve(Object.assign({}, VECTORS, { field: name }));
      }
      if (/\/field\/flow_rate\?/.test(path)) {
        api.calls.push(path);
        var rate = FIELD('flow_rate', 'm³/s/m');
        rate.totals = { positive: 2.4e-5, negative: -2.4e-5, net: 0 };
        return Promise.resolve(rate);
      }
      return below(path);
    };
    return App.Results.handleCommand('results open ' + DETAIL.id);
  }

  function vectorCalls() {
    return api.calls.filter(function (path) { return /\/vectors\//.test(path); });
  }

  test('no arrows are drawn, or fetched, until they are asked for', function () {
    return showingFlow().then(function () {
      T.eq(drawn[drawn.length - 1].vectors, null);
      T.eq(vectorCalls().length, 0);
      T.eq(App.Results.state().vectors.map(function (v) { return v.name; }),
           ['u', 'flux'], 'one entry per vector, in menu order');
    });
  });

  test('results arrows on picks the vector of the field on screen', function () {
    return showingFlow().then(function () {
      return App.Results.handleCommand('results field fluxx');
    }).then(function () {
      return App.Results.handleCommand('results arrows on');
    }).then(function () {
      T.eq(App.Results.options().arrows, 'flux', 'a vector, not "the field on screen"');
      T.eq(App.Results.state().arrowsOf, 'flux');
      T.eq(vectorCalls(), ['/api/results/runs/' + DETAIL.id + '/stages/2/vectors/flux']);
      T.eq(drawn[drawn.length - 1].vectors.field, 'flux');
      return App.Results.handleCommand('results bands 8');
    }).then(function () {
      T.eq(vectorCalls().length, 1, 'a display option fetches nothing again');
      T.ok(drawn[drawn.length - 1].vectors);
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      T.eq(drawn[drawn.length - 1].vectors.field, 'flux', 'kept when the field changes');
    });
  });

  test('results arrows <field> draws that vector over whatever is shaded', function () {
    /* The flow net: the head shaded, the flux as arrows over it. */
    return showingFlow().then(function () {
      return App.Results.handleCommand('results field head');
    }).then(function () {
      return App.Results.handleCommand('results arrows flux');
    }).then(function () {
      var last = drawn[drawn.length - 1];
      T.eq(last.field.field, 'head');
      T.eq(last.vectors.field, 'flux');
      return App.Results.handleCommand('results stage 1');
    }).then(function () {
      T.eq(drawn[drawn.length - 1].vectors.field, 'flux', 'kept from stage to stage');
      T.eq(vectorCalls().length, 2, 'fetched once per stage');
      return App.Results.handleCommand('results arrows off');
    }).then(function () {
      T.eq(drawn[drawn.length - 1].vectors, null);
    });
  });

  test('results arrows on over a field that is not a vector picks the first vector',
       function () {
    return showingFlow().then(function () {
      return App.Results.handleCommand('results field head');
    }).then(function () {
      return App.Results.handleCommand('results arrows');
    }).then(function () {
      T.eq(App.Results.options().arrows, 'u', 'a bare `results arrows` toggles on');
      T.eq(drawn[drawn.length - 1].vectors.field, 'u');
      return App.Results.handleCommand('results arrows');
    }).then(function () {
      T.eq(App.Results.options().arrows, null, 'and off again');
      T.eq(drawn[drawn.length - 1].vectors, null);
    });
  });

  test('vectors the server cannot send draw no arrows rather than an error', function () {
    return showingFlow().then(function () {
      var below = App.Api.get;
      App.Api.get = function (path) {
        if (/\/vectors\//.test(path)) {
          api.calls.push(path);
          return Promise.reject(new Error('gone'));
        }
        return below(path);
      };
      log = [];
      return App.Results.handleCommand('results arrows flux');
    }).then(function () {
      T.eq(vectorCalls().length, 1, 'they were asked for');
      var last = drawn[drawn.length - 1];
      T.eq(last.vectors, null, 'no arrows');
      T.ok(last.field, 'the contour is still drawn');
      T.eq(lines('err'), [], 'and nothing is reported as failed');
    });
  });

  test('results arrows refuses a field that is not part of a vector', function () {
    return showingFlow().then(function () {
      log = [];
      return App.Results.handleCommand('results arrows head');
    }).then(function () {
      T.ok(said('not part of a vector'), lines().join(' | '));
      T.ok(said('u, flux'), 'and names the ones that are');
      T.eq(App.Results.options().arrows, null);
    });
  });

  test('the nodal water flow rate says what comes in and what goes out', function () {
    return showingFlow().then(function () {
      log = [];
      return App.Results.handleCommand('results field flow_rate');
    }).then(function () {
      T.ok(said('Out 2.40e-5'), lines().join(' | '));
      T.ok(said('in 2.40e-5'));
      T.ok(said('out − in 0 '));
    });
  });

  test('the mesh setting is kept from one stage to the next', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results mesh on');
    }).then(function () {
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      T.eq(drawn[drawn.length - 1].options.mesh, true);
    });
  });

  test('every colour map on offer can actually be selected', function () {
    /* The pickers are built from `ResultsRender.MAPS`, so anything listed there has to
       be a name this command takes. */
    return showing().then(function () {
      var names = Object.keys(App.ResultsRender.MAPS);
      return names.reduce(function (chain, name) {
        return chain.then(function () {
          log = [];
          return App.Results.handleCommand('results map ' + name).then(function () {
            T.eq(App.Results.options().map, name);
            T.eq(lines('err').length, 0, name + ' was refused');
          });
        });
      }, Promise.resolve());
    });
  });

  test('results map refuses a colour map that does not exist', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results map wibble');
    }).then(function () {
      T.ok(said('viridis'), 'name the ones that do: ' + lines().join(' | '));
    });
  });

  /* ── Probing and exporting ────────────────────────────────────────────── */

  test('results at prints every field at one node', function () {
    return showing().then(function () {
      log = [];
      return App.Results.handleCommand('results at 2');
    }).then(function () {
      T.ok(said('u_y'));
      T.ok(said('-0.5'));
      T.ok(said('kPa'));
    });
  });

  test('a field with no value at that node says so rather than printing nothing',
       function () {
    return showing().then(function () {
      log = [];
      return App.Results.handleCommand('results at 2');
    }).then(function () {
      var body = lines().join('\n');
      T.ok(body.indexOf('—') !== -1 || body.indexOf('-') !== -1,
           'the absent one is still listed: ' + body);
    });
  });

  test('results csv downloads the field on screen', function () {
    return showing().then(function () {
      return App.Results.handleCommand('results field uy');
    }).then(function () {
      return App.Results.handleCommand('results csv');
    }).then(function () {
      T.eq(saved.length, 1);
      var name = saved[0][0], body = saved[0][1];
      T.ok(name.indexOf('uy') !== -1, 'the file is named after the field: ' + name);
      T.ok(name.indexOf('.csv') !== -1, name);
      var rows = body.trim().split(String.fromCharCode(10));
      T.ok(rows[0].indexOf('node') !== -1, 'header: ' + rows[0]);
      T.eq(rows.length, 4, 'a header and three values');
    });
  });

  test('results csv with nothing on screen says what to do first', function () {
    /* Opening a run now draws a default field, so "nothing on screen" needs a stage
       that genuinely offers nothing -- a stage that wrote no results at all. */
    setup();
    viewing();
    var base = App.Api.get;
    App.Api.get = function (path) {
      if (/\/fields$/.test(path)) {
        api.calls.push(path);
        return Promise.resolve({ stage: { index: 1 }, groups: [] });
      }
      return base(path);
    };
    return App.Results.handleCommand('results open ' + DETAIL.id).then(function () {
      log = [];
      return App.Results.handleCommand('results csv');
    }).then(function () {
      T.eq(saved.length, 0);
      T.ok(said('results field'), 'got: ' + lines().join(' | '));
    });
  });

  /* ── The project behind the run ──────────────────────────────────────── */

  /* The Results view draws the open project's loads and water level over the contour,
     read in the stage on screen. Only for a run of that project: the deck is named
     after it and every stage after its place and name. */
  function excavation() {
    return {
      name: 'Staged excavation',
      stages: [{ id: 'initial', name: 'Initial stage', parent: null },
               { id: 'dig', name: 'First excavation', parent: 'initial' }]
    };
  }

  test('the stage on screen is matched to the project stage it was calculated from',
       function () {
    return showing().then(function () {
      T.eq(App.Results.projectStage(excavation()), { stage: 'dig' });
      return App.Results.handleCommand('results stage 1');
    }).then(function () {
      T.eq(App.Results.projectStage(excavation()), { stage: 'initial' });
    });
  });

  test('a run of another project, or of other stages, matches no project stage',
       function () {
    return showing().then(function () {
      var other = excavation();
      other.name = 'Dike';
      T.eq(App.Results.projectStage(other), null, 'another deck name');
      var renamed = excavation();
      renamed.stages[1].name = 'Second excavation';
      T.eq(App.Results.projectStage(renamed), null, 'a stage renamed since the run');
      var longer = excavation();
      longer.stages.push({ id: 'load', name: 'Load', parent: 'dig' });
      T.eq(App.Results.projectStage(longer), null, 'a stage added since the run');
      T.eq(App.Results.projectStage(null), null);
    });
  });

  test('a project with no stages matches its run, with every part on', function () {
    return showing().then(function () {
      T.eq(App.Results.projectStage({ name: 'Staged excavation', stages: [] }),
           { stage: null });
    });
  });

  test('with no run open there is no project stage', function () {
    setup();
    T.eq(App.Results.projectStage(excavation()), null);
  });

  /* ── Formatting ───────────────────────────────────────────────────────── */

  test('sizes are readable rather than exact', function () {
    T.eq(App.Results.size(0), '0 B');
    T.eq(App.Results.size(512), '512 B');
    T.eq(App.Results.size(41234), '40.3 KB');
    T.eq(App.Results.size(6234567), '5.9 MB');
  });

  test('a run stamp reads as a date and time', function () {
    T.eq(App.Results.when('2026-09-22T00:49'), '2026-09-22 00:49');
    T.eq(App.Results.when('nonsense'), 'nonsense');
  });

  test('usage is offered for a verb that does not exist', function () {
    setup();
    return App.Results.handleCommand('results wibble').then(function () {
      T.ok(said('results runs'), 'got: ' + lines().join(' | '));
    });
  });

})();
