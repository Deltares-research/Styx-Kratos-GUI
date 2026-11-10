/* ══════════════════════════════════════════════════════════════════
   test-results-plot.js — `results plot`, and the figure it draws.

   The plot window imitates Kratos' own staged-excavation comparison
   figure: one panel per stage, the quantity along the
   horizontal axis, the level y up the vertical one, a line with a dot at every node.
   Whether the *numbers* are Kratos' is the server's test
   (`tests/test_result_members.py`, against Kratos' own run on the reference
   mesh). What is pinned here is that those numbers are drawn the right way up: a
   higher node higher on the page, a larger value further right, the panels in stage
   order, and the axis labels the figure has.

   `App.ResultsPlot` has no DOM in it, so all of this runs headless. The window that
   shows the figure is patches.js's and is only ever a host for `svg()`'s string.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var P = App.ResultsPlot;
  var RUN = 'Staged_excavation_2026-09-22_16-28';

  /* What `setup` replaces, kept so the last case can put it back: in the browser suite
     every file shares one `App`, and the suites after this one must get the real
     modules, not this file's recorders. */
  var real = { Api: App.Api, Command: App.Command, Download: App.Download,
               current: App.Results && App.Results.current };
  var BASE = '/api/results/runs/' + RUN;

  /* ── Doubles ──────────────────────────────────────────────────────────── */

  var log, api, saved, events;

  var QUANTITIES = {
    M: { name: 'M', label: 'Bending moment', unit: 'kNm/m' },
    Q: { name: 'Q', label: 'Shear force', unit: 'kN/m' },
    N: { name: 'N', label: 'Normal force', unit: 'kN/m' },
    ux: { name: 'ux', label: 'Horizontal total displacement', unit: 'm' },
    tn: { name: 'tn', label: 'Normal traction', unit: 'kN/m²' },
    ts: { name: 'ts', label: 'Shear traction', unit: 'kN/m²' }
  };

  var MEMBERS = { members: [
    { name: 'interface', stages: [3, 7],
      quantities: [QUANTITIES.tn, QUANTITIES.ts] },
    { name: 'wall', stages: [3, 7],
      quantities: [QUANTITIES.M, QUANTITIES.Q, QUANTITIES.N, QUANTITIES.ux] }
  ] };

  function stage(index, name, stage, points) {
    var low = null, high = null;
    points.forEach(function (p) {
      if (!low || p[0] < low.value) low = { value: p[0], y: p[1] };
      if (!high || p[0] > high.value) high = { value: p[0], y: p[1] };
    });
    return { index: index, name: name, stage: stage, points: points,
             nodes: points.map(function (_, i) { return 100 + i; }),
             min: low, max: high };
  }

  /* Stage 3 and 7 of a sheet pile's bending moment, a handful of points each: the shape of the
     real curve -- zero at both ends, a belly at -6 m -- at the real magnitudes. */
  function plotOf(quantity, member) {
    var q = QUANTITIES[quantity];
    return {
      member: member || 'wall', quantity: q.name, label: q.label, unit: q.unit,
      stages: [
        stage(3, '3_SheetPileWall_installation', 'SheetPileWall installation',
              [[0, -13], [20, -10], [53.9, -6], [30, -3], [0, 0]]),
        stage(7, '7_Third_excavation', 'Third excavation',
              [[-2, -13], [150, -9], [329, -6], [100, -3], [0, 0]])
      ]
    };
  }

  function setup(overrides) {
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
    App.Download = { anchor: function (name, text, mime) {
      saved.push({ name: name, text: text, mime: mime });
    } };

    var answers = overrides || {};
    App.Api = {
      base: '',
      get: function (path) {
        api.calls.push(path);
        if (Object.prototype.hasOwnProperty.call(answers, path)) {
          var answer = answers[path];
          return answer instanceof Error ? Promise.reject(answer) : Promise.resolve(answer);
        }
        if (path === BASE + '/members') return Promise.resolve(MEMBERS);
        var match = /\/members\/([^/]+)\/([^/]+)$/.exec(path);
        if (match) return Promise.resolve(plotOf(decodeURIComponent(match[2]),
                                                 decodeURIComponent(match[1])));
        return Promise.reject(new Error('unexpected request ' + path));
      }
    };

    App.Results = App.Results || {};
    App.Results.current = function () { return RUN; };

    P.forget();
    events = [];
  }

  // Once, as the window does: `forget` keeps its listeners.
  P.onChange(function (event) { if (events) events.push(event || {}); });

  test('forgetting clears what is plotted but keeps whoever is listening', function () {
    setup();
    return P.command('').then(function () {
      P.forget();
      T.eq(P.state().plot, null);
      events = [];
      return P.command('');
    }).then(function () {
      T.ok(events.some(function (e) { return e.open; }), 'still heard after forget');
    });
  });

  function errors() {
    return log.filter(function (line) { return line[0] === 'err'; });
  }

  function text() {
    return log.map(function (line) { return line[1]; }).join('\n');
  }

  /* ── Axes ─────────────────────────────────────────────────────────────── */

  test('the level axis is ticked every 2 m down a 13 m wall', function () {
    // What the reference figure shows: 0, -2, ... -12.
    T.eq(P.ticks(-13.65, 0.65, 6), [-12, -10, -8, -6, -4, -2, 0]);
  });

  test('a bending moment axis is ticked every 10 kNm/m up to 54', function () {
    T.eq(P.ticks(-2.7, 56.6, 5), [0, 10, 20, 30, 40, 50]);
  });

  test('a displacement axis in metres is ticked in round millimetres', function () {
    T.eq(P.ticks(-0.0234, -0.0036, 5), [-0.02, -0.015, -0.01, -0.005]);
  });

  test('tick labels carry the decimals of the step and no more', function () {
    T.eq(P.tickLabel(-0.015, 0.005), '-0.015');
    T.eq(P.tickLabel(40, 10), '40');
    T.eq(P.tickLabel(-0, 2), '0');
  });

  test('a range is padded by 5 % each side, as matplotlib does', function () {
    var range = P.padded(0, 100);
    T.near(range.min, -5, 1e-9);
    T.near(range.max, 105, 1e-9);
  });

  test('a flat curve still gets an axis to sit on', function () {
    var zero = P.padded(0, 0);
    T.ok(zero.min < 0 && zero.max > 0, 'all zero: ' + JSON.stringify(zero));
    var flat = P.padded(5, 5);
    T.ok(flat.min < 5 && flat.max > 5, 'all five: ' + JSON.stringify(flat));
  });

  /* ── The figure ───────────────────────────────────────────────────────── */

  function panels(svg) {
    return svg.split('<g class="rp-panel"').slice(1);
  }

  function linePoints(panel) {
    var found = /<polyline class="rp-line" points="([^"]*)"/.exec(panel);
    return found[1].trim().split(/\s+/).map(function (pair) {
      var xy = pair.split(',');
      return { x: parseFloat(xy[0]), y: parseFloat(xy[1]) };
    });
  }

  test('there is one panel per stage, in stage order, titled by the stage', function () {
    var svg = P.svg(plotOf('M'));
    T.ok(/^<svg[\s>]/.test(svg), 'an svg element');
    var all = panels(svg);
    T.eq(all.length, 2);
    T.ok(all[0].indexOf('3 SheetPileWall installation') !== -1, 'stage 3 first');
    T.ok(all[1].indexOf('7 Third excavation') !== -1, 'stage 7 second');
  });

  test('every panel is labelled like the reference figure', function () {
    var all = panels(P.svg(plotOf('M')));
    all.forEach(function (panel) {
      T.ok(panel.indexOf('Bending moment [kNm/m]') !== -1, 'x label');
    });
    // y [m] once per row, on the left, as matplotlib's subplots put it.
    T.ok(all[0].indexOf('y [m]') !== -1, 'y label on the first panel');
    T.ok(all[1].indexOf('y [m]') === -1, 'and not repeated along the row');
  });

  test('the wall is drawn upright: a higher node is higher on the page', function () {
    var points = linePoints(panels(P.svg(plotOf('M')))[0]);
    // Points come toe to top, so screen y has to fall as the level rises.
    for (var i = 1; i < points.length; i++) {
      T.ok(points[i].y < points[i - 1].y,
           'point ' + i + ' at ' + points[i].y + ' is not above ' + points[i - 1].y);
    }
  });

  test('a larger value is further right, and the curve has a dot per node', function () {
    var panel = panels(P.svg(plotOf('M')))[1];
    var points = linePoints(panel);
    T.eq(points.length, 5);
    // 329 at -6 m is the largest moment, so it is the right-most point.
    var right = points.reduce(function (a, b) { return b.x > a.x ? b : a; });
    T.eq(points.indexOf(right), 2);
    T.eq((panel.match(/<circle class="rp-dot"/g) || []).length, 5);
  });

  test('a densely meshed member is drawn as a line without a dot per node', function () {
    /* A long dike wall is 749 nodes over 18.7 m: a dot on each is a solid bar that hides
       the line it is meant to mark. */
    var plot = plotOf('M');
    var dense = [];
    for (var i = 0; i <= 400; i++) dense.push([Math.sin(i / 60), -12.5 + i * 0.0465]);
    plot.stages = [stage(20, '20_Bovenbelasting', 'Bovenbelasting', dense)];
    var panel = panels(P.svg(plot))[0];
    T.eq(linePoints(panel).length, 401);
    T.eq((panel.match(/<circle class="rp-dot"/g) || []).length, 0);
  });

  test('the largest magnitude in each panel is written beside it', function () {
    var all = panels(P.svg(plotOf('M')));
    T.ok(all[0].indexOf('53.9') !== -1, 'stage 3 peak');
    T.ok(all[1].indexOf('329') !== -1, 'stage 7 peak');
  });

  test('a negative extreme is the one labelled when it is the larger', function () {
    var plot = plotOf('Q');
    plot.stages = [stage(3, '3_x', 'x', [[5, -2], [-40, -1], [10, 0]])];
    T.ok(panels(P.svg(plot))[0].indexOf('-40') !== -1);
  });

  test('more stages than fit on a row wrap onto the next one', function () {
    var plot = plotOf('M');
    var one = plot.stages[0];
    plot.stages = [1, 2, 3, 4, 5, 6, 7].map(function (n) {
      return stage(n, n + '_s', 'stage ' + n, one.points);
    });
    var svg = P.svg(plot, { columns: 5 });
    var size = /viewBox="0 0 ([\d.]+) ([\d.]+)"/.exec(svg);
    var single = /viewBox="0 0 ([\d.]+) ([\d.]+)"/.exec(P.svg(plotOf('M'), { columns: 5 }));
    T.eq(panels(svg).length, 7);
    T.near(parseFloat(size[2]), 2 * parseFloat(single[2]), 1e-6, 'two rows high');
  });

  test('a stage with nothing to draw says so instead of drawing a line', function () {
    var plot = plotOf('M');
    plot.stages[0] = { index: 3, name: '3_x', stage: 'x', points: [], nodes: [],
                       min: null, max: null };
    var panel = panels(P.svg(plot))[0];
    T.ok(panel.indexOf('rp-line') === -1, 'no line');
    T.ok(panel.indexOf('no values') !== -1, 'a note');
  });

  test('a stage name is escaped, not injected', function () {
    var plot = plotOf('M');
    plot.stages[0].stage = 'Dig <deep> & wide';
    var svg = P.svg(plot);
    T.ok(svg.indexOf('Dig &lt;deep&gt; &amp; wide') !== -1);
    T.ok(svg.indexOf('<deep>') === -1);
  });

  /* ── The command ──────────────────────────────────────────────────────── */

  test('results plot is routed here from the results command', function () {
    setup();
    var answer = App.Results.handleCommand
      ? App.Results.handleCommand('results plot') : P.command('');
    return Promise.resolve(answer).then(function () {
      T.eq(api.calls, [BASE + '/members', BASE + '/members/wall/M']);
    });
  });

  test('with nothing named it plots the wall\'s bending moment and asks to be shown', function () {
    setup();
    return P.command('').then(function () {
      var state = P.state();
      T.eq([state.run, state.member, state.quantity], [RUN, 'wall', 'M']);
      T.eq(state.plot.stages.length, 2);
      T.ok(events.some(function (e) { return e.open; }), 'the window was asked for');
      T.eq(errors(), []);
    });
  });

  test('it prints the extremes of every stage, with the level', function () {
    setup();
    return P.command('').then(function () {
      var out = text();
      T.ok(/Bending moment \(kNm\/m\) along the wall/.test(out), out);
      T.ok(/3\s+SheetPileWall installation.*max 53\.9 at y = -6\.00/.test(out), out);
      T.ok(/7\s+Third excavation.*max 329 at y = -6\.00/.test(out), out);
    });
  });

  test('a member and a quantity can both be named, a quantity by its label', function () {
    setup();
    return P.command('interface normal').then(function () {
      T.eq(api.calls[api.calls.length - 1], BASE + '/members/interface/tn');
      T.eq([P.state().member, P.state().quantity], ['interface', 'tn']);
    });
  });

  test('a quantity alone finds the member that has it', function () {
    setup();
    return P.command('ts').then(function () {
      T.eq(api.calls[api.calls.length - 1], BASE + '/members/interface/ts');
    });
  });

  test('a quantity alone keeps the member on screen when that one has it', function () {
    setup();
    return P.command('interface').then(function () {
      return P.command('shear');
    }).then(function () {
      // "shear" is the wall's shear force and the interface's shear traction; the
      // interface is what is being looked at, so it is the interface's.
      T.eq([P.state().member, P.state().quantity], ['interface', 'ts']);
    });
  });

  test('names are not case sensitive', function () {
    setup();
    return P.command('Wall m').then(function () {
      T.eq([P.state().member, P.state().quantity], ['wall', 'M']);
    });
  });

  test('a quantity the member does not carry is refused, with what it does', function () {
    setup();
    return P.command('wall tn').then(function () {
      T.eq(errors().length, 1);
      T.ok(/wall/.test(errors()[0][1]) && /M, Q, N, ux/.test(errors()[0][1]),
           errors()[0][1]);
      T.eq(api.calls, [BASE + '/members']);
    });
  });

  test('a member the run does not have is refused, with the ones it has', function () {
    setup();
    return P.command('strut M').then(function () {
      T.ok(/strut/.test(text()) && /interface, wall/.test(text()), text());
    });
  });

  test('an unknown plot quantity lists each member and leaves the existing plot unchanged', function () {
    setup();
    return P.command('wall M').then(function () {
      var before = P.state().plot, count = api.calls.length;
      return P.command('not-a-quantity').then(function () {
        T.ok(/Nothing in this run can be plotted/.test(text()), text());
        T.ok(/interface: tn, ts/.test(text()), text());
        T.ok(/wall: M, Q, N, ux/.test(text()), text());
        T.eq(api.calls.length, count, 'a nonexistent quantity does not request plot data');
        T.eq(P.state().plot, before);
      });
    });
  });

  test('results plot members lists what can be plotted', function () {
    setup();
    return P.command('members').then(function () {
      T.ok(/wall\s+stages 3, 7\s+M, Q, N, ux/.test(text()), text());
      T.ok(/interface\s+stages 3, 7\s+tn, ts/.test(text()), text());
      T.eq(events.filter(function (e) { return e.open; }).length, 0,
           'listing does not open the window');
    });
  });

  test('the members are asked for once per run, not once per plot', function () {
    setup();
    return P.command('M').then(function () { return P.command('Q'); }).then(function () {
      T.eq(api.calls.filter(function (p) { return /\/members$/.test(p); }).length, 1);
    });
  });

  test('another run is read afresh', function () {
    setup();
    return P.command('M').then(function () {
      App.Results.current = function () { return 'column_new_2026-09-20_22-37'; };
      return P.command('M');
    }).then(function () {
      T.ok(api.calls.indexOf('/api/results/runs/column_new_2026-09-20_22-37/members') !== -1);
    });
  });

  test('with no run open it says how to open one', function () {
    setup();
    App.Results.current = function () { return null; };
    return P.command('').then(function () {
      T.ok(/No run is open/.test(errors()[0][1]));
      T.eq(api.calls, []);
    });
  });

  test('a run that wrote no member output says so', function () {
    var empty = {};
    empty[BASE + '/members'] = { members: [] };
    setup(empty);
    return P.command('').then(function () {
      T.ok(/no wall/i.test(text()), text());
      T.eq(events.filter(function (e) { return e.open; }).length, 0);
    });
  });

  test('results plot csv saves every stage of what is on screen', function () {
    setup();
    return P.command('').then(function () { return P.command('csv'); }).then(function () {
      T.eq(saved.length, 1);
      T.eq(saved[0].name, RUN + '_wall_M.csv');
      var lines = saved[0].text.trim().split('\n');
      T.eq(lines[0], 'stage,name,node,y [m],M [kNm/m]');
      T.eq(lines.length, 1 + 5 + 5);
      T.eq(lines[1], '3,SheetPileWall installation,100,-13,0');
    });
  });

  test('results plot svg saves the figure itself', function () {
    setup();
    return P.command('').then(function () { return P.command('svg'); }).then(function () {
      T.eq(saved[0].name, RUN + '_wall_M.svg');
      T.eq(saved[0].mime, 'image/svg+xml');
      T.ok(/^<svg[^>]*xmlns="http:\/\/www\.w3\.org\/2000\/svg"/.test(saved[0].text));
    });
  });

  test('saving with nothing plotted plots first', function () {
    setup();
    return P.command('csv').then(function () {
      T.eq(saved.length, 1);
      T.eq(saved[0].name, RUN + '_wall_M.csv');
    });
  });

  /* ── A wall with an interface on each face ───────────────────────────── */

  var FACES = { members: [
    { name: 'interface_left', stages: [3, 7], quantities: [QUANTITIES.tn, QUANTITIES.ts] },
    { name: 'interface_right', stages: [3, 7], quantities: [QUANTITIES.tn, QUANTITIES.ts] },
    { name: 'wall', stages: [3, 7],
      quantities: [QUANTITIES.M, QUANTITIES.Q, QUANTITIES.N, QUANTITIES.ux] }
  ] };

  function setupFaces() {
    var answers = {};
    answers[BASE + '/members'] = FACES;
    setup(answers);
  }

  test('a wall with an interface on each face offers both faces to choose from', function () {
    setupFaces();
    return P.command('').then(function () {
      T.eq(P.state().members.map(function (m) { return m.name; }),
           ['interface_left', 'interface_right', 'wall']);
      T.eq([P.state().member, P.state().quantity], ['wall', 'M']);
    });
  });

  test('each face is plotted when it is chosen, with the quantity on screen kept', function () {
    setupFaces();
    return P.command('interface_left tn').then(function () {
      T.eq(api.calls[api.calls.length - 1], BASE + '/members/interface_left/tn');
      // What the window's Member list sends when the other face is chosen.
      return P.command('interface_right');
    }).then(function () {
      T.eq(api.calls[api.calls.length - 1], BASE + '/members/interface_right/tn');
      T.eq([P.state().member, P.state().quantity], ['interface_right', 'tn']);
      T.eq(P.state().plot.member, 'interface_right');
      T.eq(errors(), []);
    });
  });

  test('results plot interface_right tn plots that face', function () {
    setupFaces();
    return P.command('interface_right tn').then(function () {
      T.eq(api.calls, [BASE + '/members', BASE + '/members/interface_right/tn']);
      T.ok(/Normal traction \(kN\/m²\) along the interface_right/.test(text()), text());
    });
  });

  test('a traction alone is plotted on a face, the one on screen first', function () {
    setupFaces();
    return P.command('tn').then(function () {
      T.eq([P.state().member, P.state().quantity], ['interface_left', 'tn']);
      return P.command('interface_right ts');
    }).then(function () {
      return P.command('tn');
    }).then(function () {
      T.eq([P.state().member, P.state().quantity], ['interface_right', 'tn']);
    });
  });

  test('the one interface of an older run is not a name a run with two faces has', function () {
    setupFaces();
    return P.command('interface tn').then(function () {
      T.ok(/no member called "interface"/.test(text()), text());
      T.ok(/interface_left, interface_right, wall/.test(text()), text());
      T.eq(api.calls, [BASE + '/members']);
    });
  });

  test('(the doubles are put back for the suites that follow)', function () {
    P.forget();
    App.Api = real.Api;
    App.Command = real.Command;
    App.Download = real.Download;
    if (App.Results && real.current) App.Results.current = real.current;
  });

})();
