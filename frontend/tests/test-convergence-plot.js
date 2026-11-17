/* ══════════════════════════════════════════════════════════════════
   test-convergence-plot.js — `results convergence`, and the figure it draws.

   The cases are real Kratos logs parsed by the server's own parser
   (`frontend/tests/fixtures/convergence-cases.js`, written by
   `tests/test_convergence_parity.py`): seven excavation stages of one iteration each, a step
   that hit the iteration limit, a flow stage of twenty iterations, and made-up logs with
   nan, inf, zero and nothing at all. What is pinned here is that the figure draws them
   the right way -- a dot per iteration, the stages in order, the marks where they belong
   -- and that the CSV is the one `kratos-cli` writes, byte for byte.

   `App.ConvergencePlot` has no DOM in it, so all of this runs headless.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var P = App.ConvergencePlot;
  var CASES = window.CONVERGENCE_FIXTURE;
  var RUN = 'Staged_excavation_2026-09-22_16-28';
  var BASE = '/api/results/runs/' + RUN;

  var real = { Api: App.Api, Command: App.Command, Download: App.Download,
               Picture: App.Picture, current: App.Results && App.Results.current,
               Window: App.ConvergenceWindow };

  var log, api, saved, events;

  function data(name) { return JSON.parse(JSON.stringify(CASES[name].data)); }

  // A Convergence window that is closed: the command then picks the run itself.
  var CLOSED = { state: function () { return { open: false }; } };
  var OPEN = { state: function () { return { open: true }; } };

  function setup(answers, open) {
    App.ConvergenceWindow = CLOSED;
    log = [];
    api = { calls: [] };
    saved = [];
    events = [];
    App.Command = {
      note: function (line) { log.push(['note', line]); },
      ok:   function (line) { log.push(['ok', line]); },
      err:  function (line) { log.push(['err', line]); },
      write: function (kind, line) { log.push([kind, line]); }
    };
    App.Download = Object.assign({}, App.Download, {
      pickFile: function () { return Promise.resolve(null); },
      anchor: function (name, text, mime) { saved.push({ name: name, text: text, mime: mime }); }
    });
    App.Picture = { saveFigure: function (svg, name, kind) {
      saved.push({ name: name, text: svg, kind: kind });
      return Promise.resolve(1);
    } };
    App.Api = {
      base: '',
      get: function (path) {
        api.calls.push(path);
        if (Object.prototype.hasOwnProperty.call(answers || {}, path)) {
          var answer = answers[path];
          return answer instanceof Error ? Promise.reject(answer) : Promise.resolve(answer);
        }
        return Promise.reject(new Error('unexpected request ' + path));
      }
    };
    App.Results = App.Results || {};
    App.Results.current = function () { return open === undefined ? RUN : open; };
    P.forget();
    events = [];
  }

  P.onChange(function (event) { if (events) events.push(event || {}); });

  function text() { return log.map(function (line) { return line[1]; }).join('\n'); }

  function count(svg, cls) {
    return svg.split('class="' + cls + '"').length - 1;
  }

  function panels(svg) {
    var relative = svg.indexOf('<g class="cp-panel cp-relative">');
    var absolute = svg.indexOf('<g class="cp-panel cp-absolute">');
    return [svg.slice(relative, absolute), svg.slice(absolute)];
  }

  /* A panel's frame: [match, top, width, height]. */
  function frameOf(svg) {
    return /<rect x="64" y="(\d+)" width="(\d+)" height="(\d+)" fill="none"/.exec(svg);
  }

  function dots(panel) {
    var out = [], re = /class="cp-dot" cx="([\d.-]+)" cy="([\d.-]+)"/g, m;
    while ((m = re.exec(panel))) out.push([Number(m[1]), Number(m[2])]);
    return out;
  }

  /* ── The figure ───────────────────────────────────────────────────────── */

  test('two panels, relative above absolute, sharing the iteration axis', function () {
    var svg = P.svg(data('seepage'));
    T.ok(/^<svg[\s>]/.test(svg), 'an svg element');
    var both = panels(svg);
    T.ok(both[0].indexOf('Relative residual') !== -1);
    T.ok(both[1].indexOf('Absolute residual') !== -1);
    var upper = dots(both[0]), lower = dots(both[1]);
    T.eq(upper.length, 20);
    T.eq(upper.map(function (d) { return d[0]; }), lower.map(function (d) { return d[0]; }));
    T.ok(Math.max.apply(null, upper.map(function (d) { return d[1]; }))
         < Math.min.apply(null, lower.map(function (d) { return d[1]; })), 'relative is above');
    T.ok(svg.indexOf('>Iteration, counted over all stages</text>') !== -1,
         'the axis says its numbers are the run\'s');
  });

  test('a stage of one iteration still shows its dot, and every stage its band', function () {
    var svg = P.svg(data('staged_cut_lines'));
    var both = panels(svg);
    T.eq(dots(both[0]).length, 7);
    T.eq(count(both[0], 'cp-band'), 7);
    var xs = dots(both[0]).map(function (d) { return d[0]; });
    T.ok(xs.every(function (x, i) { return i === 0 || x > xs[i - 1]; }), 'in iteration order');
  });

  test('one line joins the dots of the whole run, across the stages', function () {
    var both = panels(P.svg(data('staged_cut_lines')));
    both.forEach(function (panel) {
      T.eq(count(panel, 'cp-line'), 1, 'one line, not one per stage');
      var points = /class="cp-line" points="([^"]+)"/.exec(panel)[1].split(' ');
      T.eq(points.length, 7, 'through all seven dots');
    });
  });

  test('the line breaks at nan and inf, and nowhere else', function () {
    var made = data('nan_and_zero');
    // Two finite values on each side of a nan: one piece of line each side.
    made.iterations = [made.iterations[0], made.iterations[0], made.iterations[1],
                       made.iterations[0], made.iterations[0]];
    T.eq(count(panels(P.svg(made))[0], 'cp-line'), 2);
  });

  test('a higher residual is drawn higher on its log axis', function () {
    var limit = data('iteration_limit');
    var upper = dots(panels(P.svg(limit))[0]);
    // Iteration 2 is 0.22, iteration 51 is 0.085, both in stage 2.
    T.ok(upper[1][1] < upper[50][1], 'the larger residual is further up the page');
  });

  test('a green X where the criterion was met, in both panels, and only there', function () {
    var limit = data('iteration_limit');
    var met = limit.iterations.filter(function (it) { return it.met; }).length;
    panels(P.svg(limit)).forEach(function (panel) {
      T.eq(count(panel, 'cp-met'), met);
    });
    T.eq(count(panels(P.svg(data('seepage')))[0], 'cp-met'), 20);
    var mark = /<path class="cp-met" d="M[\d.,-]+l[\d.]+,[\d.]+m0,-[\d.]+l-[\d.]+,[\d.]+"[^>]*>/
      .exec(P.svg(limit));
    T.ok(mark, 'an X, two strokes, not a ring');
    T.ok(mark[0].indexOf('stroke="#2ca02c"') !== -1, 'green');
    T.ok(P.svg(limit).indexOf('<circle class="cp-met"') === -1, 'no ring left');
  });

  test('the X sits on the dot it marks, and leaves the dot its tooltip', function () {
    var upper = panels(P.svg(data('seepage')))[0];
    var first = dots(upper)[0];
    var mark = /<path class="cp-met" d="M([\d.]+),([\d.]+)l([\d.]+),/.exec(upper);
    var half = Number(mark[3]) / 2;
    T.near(Number(mark[1]) + half, first[0], 0.11);
    T.near(Number(mark[2]) + half, first[1], 0.11);
    T.ok(/class="cp-met"[^>]*pointer-events="none"/.test(upper));
  });

  test('the fraction of unbalance: a red line with an x at each value, on a second axis',
       function () {
    var limit = data('iteration_limit');
    limit.fractions = [{ at: 1, value: 1 }, { at: 51, value: 0.5 }, { at: 60, value: 0 }];
    var svg = P.svg(limit);
    panels(svg).forEach(function (panel) {
      T.eq(count(panel, 'cp-fraction-line'), 1, 'in both panels');
      T.eq(count(panel, 'cp-fraction-mark'), 3, 'an x at each value');
      T.ok(panel.indexOf('>Fraction of unbalance</text>') !== -1, 'the axis is named');
      T.eq(count(panel, 'cp-tick cp-fraction-tick'), 6, '0 to 1 on the right');
      T.ok(/cp-fraction-tick"[^>]*fill="#d62728">1</.test(panel), 'in red');
    });
    var upper = panels(svg)[0];
    var frame = frameOf(upper);
    var top = Number(frame[1]);
    var tall = P.FIG.panel;
    var points = /class="cp-fraction-line" points="([^"]+)"/.exec(upper)[1].split(' ')
      .map(function (p) { return p.split(',').map(Number); });
    T.near(points[0][1], top, 0.11, '1 on the top edge');
    T.near(points[1][1], top + tall / 2, 0.11, '0.5 half way');
    T.near(points[2][1], top + tall, 0.11, '0 on the bottom edge');
    T.eq(points[1][0], dots(upper)[50][0], 'after the iteration Kratos printed it');
    T.ok(svg.indexOf('Fraction of unbalance 0.5000, after iteration 51') !== -1
         || svg.indexOf('Fraction of unbalance 0.5, after iteration 51') !== -1,
         'each x has a tooltip');
    T.ok(svg.indexOf('fraction of unbalance (right axis)</text>') !== -1, 'in the legend');
    T.eq(Number(frame[2]), P.FIG.width - P.FIG.fraction - P.FIG.left, 'room on the right');
  });

  test('no second axis when Kratos printed no fraction', function () {
    var svg = P.svg(data('iteration_limit'));
    T.eq(count(svg, 'cp-fraction'), 0);
    T.ok(svg.indexOf('Fraction of unbalance') === -1);
    T.ok(svg.indexOf('fraction of unbalance') === -1, 'nor a legend row');
    var frame = frameOf(svg);
    T.eq(Number(frame[2]), P.FIG.width - P.FIG.right - P.FIG.left, 'the panels keep the width');
  });

  test('a fraction the parser read from a log is drawn', function () {
    var made = data('nan_and_zero');
    T.eq(made.fractions, [{ at: 1, value: 0.5 }]);
    var upper = panels(P.svg(made))[0];
    T.eq(count(upper, 'cp-fraction-mark'), 1);
    T.eq(count(upper, 'cp-fraction-line'), 0, 'one value is a mark, not a line');
  });

  test('a red mark where a step hit the limit and was cut back, with both in words', function () {
    var svg = P.svg(data('iteration_limit'));
    var upper = panels(svg)[0];
    T.eq(count(upper, 'cp-event'), 1, 'one mark for one place');
    T.ok(upper.indexOf('step reached the iteration limit of 50; step cut back, factor 0.5')
         !== -1, upper.slice(upper.indexOf('cp-event'), upper.indexOf('cp-event') + 300));
  });

  test('every dot has a tooltip with its place and its numbers', function () {
    var svg = P.svg(data('staged_cut_lines'));
    T.ok(svg.indexOf('<title>Iteration 3 — stage 3 SheetPileWall installation, step 1\n'
                     + 'Relative residual 1.23e-10 (target 0.0010)') !== -1);
  });

  test('nan and inf are drawn on the top edge in red, zero on the bottom edge', function () {
    var svg = P.svg(data('nan_and_zero'));
    var upper = panels(svg)[0];
    T.eq(dots(upper).length, 1, 'only the zero is a dot');
    T.eq(count(upper, 'cp-nan'), 2);
    var bottom = frameOf(upper);
    T.eq(dots(upper)[0][1], Number(bottom[1]) + P.FIG.panel, 'zero sits on the bottom edge');
    T.ok(svg.indexOf('NaN') === -1 && svg.indexOf('Infinity') === -1);
  });

  test('stage labels say the name where it fits and only the number where it does not',
       function () {
    var staged = P.svg(data('staged_cut_lines'));
    T.ok(staged.indexOf('>1 Initial stage</text>') !== -1 || staged.indexOf('>1</text>') !== -1);
    var seepage = P.svg(data('seepage'));
    T.ok(seepage.indexOf('>1 Flow</text>') !== -1, 'one wide band has room for the name');
    var many = data('seepage');
    many.stages = many.iterations.map(function (it, i) {
      return { at: i, index: i + 1, of: 20, name: (i + 1) + '_A_long_stage_name' };
    });
    var narrow = P.svg(many);
    T.ok(narrow.indexOf('A long stage name</text>') === -1, 'no name squeezed into a band');
  });

  test('2 000 iterations are drawn, with smaller dots and no step line forest', function () {
    var big = data('seepage');
    var one = big.iterations[0];
    big.iterations = [];
    big.steps = [];
    for (var i = 0; i < 2000; i++) {
      big.iterations.push(Object.assign({}, one, { relative: Math.pow(10, -i / 400) }));
      big.steps.push({ at: i, time: i, cycle: 1 });
    }
    var svg = P.svg(big);
    T.eq(dots(panels(svg)[0]).length, 2000);
    T.ok(/class="cp-dot" cx="[\d.]+" cy="[\d.]+" r="1.4"/.test(svg));
    T.eq(count(svg, 'cp-step'), 0);
  });

  test('an empty log draws empty panels that say so', function () {
    var svg = P.svg(data('empty'));
    T.eq(dots(svg).length, 0);
    T.ok(svg.indexOf('no iterations yet') !== -1);
    T.ok(svg.indexOf('NaN') === -1);
  });

  test('a stage name is escaped', function () {
    var staged = data('staged_cut_lines');
    staged.stages[0].name = '1_Dig_<deep>_&_wide';
    var svg = P.svg(staged);
    T.ok(svg.indexOf('Dig &lt;deep&gt; &amp; wide') !== -1);
    T.ok(svg.indexOf('<deep>') === -1);
  });

  test('the log axis spans whole decades around the values and the targets', function () {
    T.eq(P.decades([0.5, 2e-3, 1.5e-4, 'nan', 0]), { lo: -4, hi: 0 });
    T.eq(P.decades([1e-3, 2e-2]), { lo: -4, hi: -1 }, 'a whole decade is not on the frame');
    T.eq(P.decades([1e-9]), { lo: -10, hi: -8 });
    T.eq(P.decades([]), { lo: -12, hi: 0 });
    T.eq(P.iterationTicks(7), [1, 2, 3, 4, 5, 6, 7]);
    T.eq(P.iterationTicks(51).slice(0, 3), [1, 10, 20]);
    T.eq(P.iterationTicks(50, 8, 2), [2, 10, 20, 30, 40, 50], 'one stage shown alone');
    T.eq(P.iterationTicks(5, 8, 58), [58, 59, 60, 61, 62]);
    T.eq(P.iterationTicks(30, 8, 9), [10, 15, 20, 25, 30, 35], 'no 9 against the 10');
  });

  /* ── The criteria ─────────────────────────────────────────────────────── */

  test('a run whose stages use different criteria shows each in its own colour', function () {
    var mixed = data('mixed_criteria');
    var svg = P.svg(mixed);
    var both = panels(svg);
    T.ok(both[0].indexOf('>Relative value</text>') !== -1, 'not called a residual');
    T.ok(both[1].indexOf('>Absolute value</text>') !== -1);
    T.ok(svg.indexOf('>residual</text>') !== -1, 'the legend names both');
    T.ok(svg.indexOf('>displacement change</text>') !== -1);
    T.eq(count(both[0], 'cp-line'), 1, 'stage 1 is one dot: the line starts in stage 2');
    T.ok(/class="cp-line"[^>]*stroke="#ff7f0e"/.test(both[0]), 'the displacement line');
    T.ok(/class="cp-dot"[^>]*fill="#1f77b4"/.test(both[0]), 'the residual dot');
    T.ok(/<title>Iteration 2 — stage 2 Null step, step 1\nRelative displacement change /
           .test(svg), 'tooltip');
    T.ok(svg.indexOf('— displacement change criterion</title>') !== -1, 'stage tooltip');
  });

  test('the line breaks where the criterion changes', function () {
    var made = data('staged_cut_lines');
    made.iterations.forEach(function (it, i) {
      it.criterion = i < 3 ? 'residual' : 'water_pressure';
    });
    var upper = panels(P.svg(made))[0];
    T.eq(count(upper, 'cp-line'), 2);
    T.ok(/class="cp-line"[^>]*stroke="#17becf"/.test(upper), 'the water pressure line');
  });

  test('a run on one criterion names it on the axes', function () {
    var made = data('seepage');
    made.iterations.forEach(function (it) { it.criterion = 'displacement'; });
    var both = panels(P.svg(made));
    T.ok(both[0].indexOf('>Relative displacement change</text>') !== -1);
    T.ok(both[1].indexOf('>Absolute displacement change</text>') !== -1);
    T.ok(/Relative displacement change/.test(P.lastText(made)));
  });

  /* ── One stage alone, and the window's size ───────────────────────────── */

  test('one stage alone: its iterations, numbered as in the whole run', function () {
    var limit = data('iteration_limit');
    var svg = P.svg(limit, { stage: 2 });
    var upper = panels(svg)[0];
    T.eq(dots(upper).length, 50);
    T.eq(count(upper, 'cp-band'), 1);
    T.ok(svg.indexOf('<title>Iteration 2 — stage 2 Push') !== -1, 'the run\'s numbers');
    T.ok(svg.indexOf('After iteration 51: step reached the iteration limit') !== -1);
    T.ok(/text-anchor="middle">2<\/text>/.test(panels(svg)[1]), 'the axis starts at 2');
    T.eq(count(panels(P.svg(limit, { stage: 1 }))[0], 'cp-dot'), 1);
    T.eq(P.svg(limit, { stage: 9 }), P.svg(limit), 'a stage it does not have: all');
  });

  test('a taller window gets taller panels, never shorter ones', function () {
    var seepage = data('seepage');
    T.eq(Number(frameOf(P.svg(seepage))[3]), P.FIG.panel, 'a saved figure');
    T.eq(Number(frameOf(P.svg(seepage, { height: 100 }))[3]), P.FIG.panel);
    var tall = P.svg(seepage, { height: 1000 });
    T.ok(Number(frameOf(tall)[3]) > 400, 'about half of the height each');
    T.ok(/viewBox="0 0 560 (999|1000)"/.test(tall),
         'the shape of the window: ' + /viewBox="[^"]+"/.exec(tall)[0]);
  });

  /* ── Words ────────────────────────────────────────────────────────────── */

  test('the status words say the stage and the last iteration', function () {
    var limit = data('iteration_limit');
    T.eq(P.stageText(limit), 'stage 2 of 2, Push');
    T.eq(P.lastText(limit), 'Iteration 51 (stage 2, step 1, iteration 50 of the step). '
                            + 'Relative residual 0.0849 (target 1.00e-4). '
                            + 'Absolute residual 0.5067 (target 1.00e-9).');
    T.eq(P.lastText(data('empty')), '');
    T.ok(/Criterion met\.$/.test(P.lastText(data('seepage'))));
  });

  /* ── The file ─────────────────────────────────────────────────────────── */

  test('the CSV is the one kratos-cli writes, byte for byte, for every case', function () {
    Object.keys(CASES).forEach(function (name) {
      T.eq(P.csv(CASES[name].data), CASES[name].csv, name);
      var stages = CASES[name].data.stages;
      if (stages.length) {
        T.eq(P.csv(CASES[name].data, stages[stages.length - 1].index),
             CASES[name].csv_last_stage, name + ', its last stage alone');
      }
    });
  });

  /* ── The command ──────────────────────────────────────────────────────── */

  test('results convergence loads the open run and asks for the window', function () {
    var answers = {};
    answers[BASE + '/convergence'] = Object.assign({ run: RUN, running: false,
                                                     failed_at: null, log: true },
                                                   data('staged_cut_lines'));
    setup(answers);
    return P.command('').then(function () {
      T.eq(api.calls, ['/api/calculate/status', BASE + '/convergence']);
      T.eq(P.state().run, RUN);
      T.ok(events.some(function (e) { return e.open; }), 'the window is asked for');
      T.ok(text().indexOf(RUN + ': 7 iterations in 7 stages.') !== -1, text());
    });
  });

  test('with no run open it takes the newest run on this machine', function () {
    var answers = { '/api/results/runs': { runs: [{ id: 'Newest_2026-11-12_10-00' },
                                                  { id: 'Older_2026-11-11_10-00' }] } };
    answers['/api/results/runs/Newest_2026-11-12_10-00/convergence'] =
      Object.assign({ run: 'Newest_2026-11-12_10-00', running: false, failed_at: null,
                      log: true }, data('seepage'));
    setup(answers, null);
    return P.command('').then(function () {
      T.eq(P.state().run, 'Newest_2026-11-12_10-00');
    });
  });

  test('a run Kratos is working on comes before the open run', function () {
    var answers = { '/api/calculate/status': { running: true, run: 'Live_2026-11-12_11-00' } };
    answers['/api/results/runs/Live_2026-11-12_11-00/convergence'] =
      Object.assign({ run: 'Live_2026-11-12_11-00', running: true, failed_at: null,
                      log: true }, data('seepage'));
    setup(answers);
    return P.command('').then(function () {
      T.eq(P.state().run, 'Live_2026-11-12_11-00');
      T.ok(/still running/.test(text()), text());
    });
  });

  test('with no runs at all it says how to make one', function () {
    setup({ '/api/results/runs': { runs: [] } }, null);
    return P.command('').then(function () {
      T.ok(/No runs yet/.test(text()), text());
      T.eq(events.length, 0);
    });
  });

  test('a log with no residuals says what to check', function () {
    var answers = {};
    var nothing = data('empty');
    nothing.stages = [{ at: 0, index: 1, of: 1, name: '1_Flow' }];
    answers[BASE + '/convergence'] = Object.assign({ run: RUN, running: false,
                                                     failed_at: null, log: true }, nothing);
    setup(answers);
    return P.command('').then(function () {
      T.ok(text().indexOf('echo_level') !== -1, text());
    });
  });

  test('results convergence csv, svg, png and pdf save the file', function () {
    var answers = {};
    answers[BASE + '/convergence'] = Object.assign({ run: RUN }, data('iteration_limit'));
    setup(answers);
    return P.command('csv').then(function () { return P.command('svg'); })
      .then(function () { return P.command('png'); })
      .then(function () {
        T.eq(saved.map(function (s) { return s.name; }),
             [RUN + '_convergence.csv', RUN + '_convergence.svg', RUN + '_convergence.png']);
        T.eq(saved[0].text, CASES.iteration_limit.csv);
        T.ok(/^<svg/.test(saved[1].text));
        T.eq(saved[2].kind, 'png');
      });
  });

  test('with the Convergence window open, a file is of the run it shows, asked for at once',
       function () {
    var shown = Object.assign({ run: RUN }, data('iteration_limit'));
    setup({}, 'Other_2026-11-01_10-00');
    P.show(RUN, shown);
    App.ConvergenceWindow = OPEN;
    var pending = P.command('png');
    T.eq(saved.length, 1, 'saved before any answer, so the click still opens the save window');
    return pending.then(function () { return P.command('csv'); }).then(function () {
      T.eq(api.calls, [], 'not the open run, nor any other');
      T.eq(saved.map(function (s) { return s.name; }),
           [RUN + '_convergence.png', RUN + '_convergence.csv']);
      T.eq(saved[1].text, CASES.iteration_limit.csv);
    });
  });

  test('with the Convergence window open and no run in it, nothing is saved', function () {
    setup({});
    App.ConvergenceWindow = OPEN;
    return P.command('png').then(function () {
      T.eq(saved, []);
      T.eq(api.calls, []);
      T.ok(/Nothing to save yet/.test(text()), text());
    });
  });

  test('results convergence stage N shows that stage alone, and its files are of it',
       function () {
    var answers = {};
    answers[BASE + '/convergence'] = Object.assign({ run: RUN }, data('iteration_limit'));
    setup(answers);
    return P.command('stage 2').then(function () {
      T.eq(P.state().stage, 2);
      T.ok(events.some(function (e) { return e.open; }), 'the window is asked for');
      T.ok(/Showing stage 2, Push, alone/.test(text()), text());
      return P.command('csv');
    }).then(function () {
      T.eq(saved[0].name, RUN + '_convergence_stage_2.csv');
      T.eq(saved[0].text, CASES.iteration_limit.csv_last_stage, 'the rows of --stage 2');
      App.ConvergenceWindow = OPEN;
      return P.command('stage initial');
    }).then(function () {
      T.eq(P.state().stage, 1, 'words of its name, on the run the window shows');
      return P.command('stage all');
    }).then(function () {
      T.eq(P.state().stage, null);
      return P.command('stage 9');
    }).then(function () {
      T.ok(/no stage with iterations matches "9". Its stages: 1 Initial, 2 Push/.test(text()),
           text());
    });
  });

  test('the stage shown alone stays with its run, and goes with another', function () {
    var answers = {};
    answers[BASE + '/convergence'] = Object.assign({ run: RUN }, data('iteration_limit'));
    answers['/api/results/runs/Other/convergence'] = Object.assign({ run: 'Other' },
                                                                   data('iteration_limit'));
    setup(answers);
    return P.load(RUN).then(function () {
      P.setStage(2);
      T.eq(P.state().stage, 2);
      return P.load(RUN, true);
    }).then(function () {
      T.eq(P.state().stage, 2, 'the window asks again every second');
      P.setStage(7);
      T.eq(P.state().stage, null, 'a stage the run does not have');
      P.setStage(2);
      return P.load('Other');
    }).then(function () {
      T.eq(P.state().stage, null);
    });
  });

  test('a word it does not know is refused with the ones it does', function () {
    setup({});
    return P.command('tiff').then(function () {
      T.ok(/No such convergence command: "tiff"/.test(text()), text());
      T.eq(api.calls, []);
    });
  });


  test('(the doubles are put back for the suites that follow)', function () {
    P.forget();
    App.Api = real.Api;
    App.Command = real.Command;
    App.Download = real.Download;
    App.Picture = real.Picture;
    App.ConvergenceWindow = real.Window;
    if (App.Results && real.current) App.Results.current = real.current;
  });

})();
