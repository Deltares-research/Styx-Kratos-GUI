/* Results mode's windows and actions (live/js/patches.js): "View results", the Choose
   results window, the plot window, "Results at node", and the Results menu.

   Opened the way the app opens them -- `App.runAction` after `LivePatches.install()` --
   with the server's results routes answered by a stand-in for one two-phase run. Every
   `results ...` command the windows issue goes through `App.Results.handleCommand`, and
   is recorded there: the windows are only ever a face on those commands. */

(function () {

  var RUN = 'Deck_2026-01-01_00-00';
  var BASE = '/api/results/runs/' + RUN;

  var STAGES = [
    { index: 1, name: '1_Initial', phase: 'Initial', base: 'Deck_1', results: true,
      results_file: 'Deck_1.post.res', mesh_file: 'Deck_1.post.msh', json: [] },
    { index: 2, name: '2_Dig', phase: 'Dig', base: 'Deck_2', results: true,
      results_file: 'Deck_2.post.res', mesh_file: 'Deck_2.post.msh',
      json: ['2_Dig__output_wall.json'] }
  ];

  var ANSWERS = {
    '/api/results/runs': { runs: [{ id: RUN, deck: 'Deck', started: '2026-01-01T00:00',
                                    repeat: 1, results: 2, files: 4, bytes: 2048 }],
                           root: '/runs' },
    run: { id: RUN, deck: 'Deck', started: '2026-01-01T00:00', repeat: 1, results: 2,
           files: [{ name: 'Deck.mdpa', bytes: 1024 }], bytes: 2048, complete: true,
           failed_at: null, log: 'kratos.log', stages: STAGES },
    mesh: { dimension: 2, bbox: [0, -1, 0, 1, 0, 0], sections: [{
      key: 'results:Soil', part: 'Soil', kind: 'continuum', node_ids: [1, 2, 3],
      positions: [0, 0, 0, 1, 0, 0, 0, -1, 0], indices: [0, 1, 2], edges: [] }] },
    fields: { stage: STAGES[1], groups: [
      { name: 'Deformations', fields: [
        { name: 'uy', label: 'u_y', unit: 'm', locations: ['nodes'] },
        { name: 'u', label: '|u|', unit: 'm', locations: ['nodes'] }] }] },
    members: { members: [{ name: 'wall', stages: [2], quantities: [
      { name: 'M', label: 'Bending moment', unit: 'kNm/m' },
      { name: 'N', label: 'Normal force', unit: 'kN/m' }] }] }
  };

  function field(name) {
    return { field: name, label: name, unit: 'm', location: 'nodes', ids: [1, 2, 3],
             values: [0, -0.01, -0.02], min: -0.02, max: 0 };
  }

  function plot(quantity) {
    return { member: 'wall', quantity: quantity, label: quantity, unit: 'kNm/m', stages: [
      { index: 2, name: '2_Dig', phase: 'Dig', points: [[0, -5], [10, -2], [0, 0]],
        nodes: [1, 2, 3], min: { value: 0, y: -5 }, max: { value: 10, y: -2 } }] };
  }

  function answer(path) {
    if (path === '/api/results/runs') return ANSWERS[path];
    if (path === BASE) return ANSWERS.run;
    if (/\/stages\/\d+\/mesh$/.test(path)) return ANSWERS.mesh;
    if (/\/stages\/\d+\/fields$/.test(path)) return ANSWERS.fields;
    if (/\/stages\/\d+\/displacement$/.test(path)) return { source: null, ids: [], values: [] };
    var f = /\/field\/([^?]+)/.exec(path);
    if (f) return field(decodeURIComponent(f[1]));
    if (path === BASE + '/members') return ANSWERS.members;
    var m = /\/members\/wall\/([^/]+)$/.exec(path);
    if (m) return plot(decodeURIComponent(m[1]));
    return null;
  }

  var GLOBALS = ['Api', 'Command', 'Viewport', 'state', 'runAction', 'selectObject',
                 'setMode', 'Download'];

  function rig() {
    var saved = {};
    GLOBALS.forEach(function (k) { saved[k] = App[k]; });
    var handle = App.Results.handleCommand;
    var download = App.Results.download;
    var prompt = window.prompt;
    var ctx = { commands: [], lines: [], downloads: [], requests: [] };
    var layer = document.createElement('div');
    layer.id = 'modal-layer';
    document.body.appendChild(layer);

    App.Api = { base: '', get: function (path) {
      ctx.requests.push(path);
      var found = answer(path);
      return found ? Promise.resolve(found) : Promise.reject(new Error('no ' + path));
    } };
    App.Command = { ok: function (t) { ctx.lines.push('ok:' + t); },
                    err: function (t) { ctx.lines.push('err:' + t); },
                    note: function (t) { ctx.lines.push('note:' + t); },
                    write: function () {}, run: function () {} };
    App.Viewport = Object.assign({}, App.Viewport, { requestRender: function () {},
                                                     getScene: function () { return null; } });
    App.Download = { anchor: function (name) { ctx.downloads.push(name); } };
    App.state = { mode: 'results' };
    App.runAction = function () {};
    App.selectObject = function () {};
    App.setMode = function (mode) { App.state.mode = mode; };
    App.Results.download = function (url, name) { ctx.downloads.push(name); };
    App.Results.handleCommand = function (text) {
      ctx.commands.push(text);
      return handle.apply(App.Results, arguments);
    };
    App.Results.forget();
    App.LivePatches.resetForTests();
    App.LivePatches.install();

    ctx.layer = layer;
    ctx.restore = function () {
      App.Results.forget();
      layer.remove();
      App.LivePatches.resetForTests();
      App.Results.handleCommand = handle;
      App.Results.download = download;
      window.prompt = prompt;
      GLOBALS.forEach(function (k) { App[k] = saved[k]; });
    };
    return ctx;
  }

  function settle(ms) { return new Promise(function (r) { setTimeout(r, ms || 30); }); }

  function done(ctx, promise) {
    return Promise.resolve(promise).then(function () { ctx.restore(); },
                                         function (e) { ctx.restore(); throw e; });
  }

  function dialogTitled(ctx, title) {
    return Array.prototype.filter.call(ctx.layer.querySelectorAll('.dialog'), function (d) {
      var t = d.querySelector('.dlg-title');
      return t && t.textContent === title;
    })[0];
  }

  function button(dialog, label) {
    return Array.prototype.filter.call(dialog.querySelectorAll('button'), function (b) {
      return b.textContent === label;
    })[0];
  }

  test('results: "View results" with nothing open opens the newest run on the machine', function () {
    var ctx = rig();
    App.state.mode = 'soil';
    App.runAction({ action: 'results' });
    return done(ctx, settle(60).then(function () {
      T.eq(App.state.mode, 'results');
      T.eq(ctx.commands.slice(0, 2), ['results runs', 'results open 1']);
      T.eq(App.Results.current(), RUN);
    }));
  });

  test('results: "View results" with nothing calculated says to calculate first', function () {
    var ctx = rig();
    var runs = ANSWERS['/api/results/runs'];
    ANSWERS['/api/results/runs'] = { runs: [], root: '/runs' };
    App.runAction({ action: 'results' });
    return done(ctx, settle(40).then(function () {
      T.ok(ctx.lines.some(function (l) { return /press Calculate/.test(l); }), ctx.lines.join(' | '));
    }).then(function () { ANSWERS['/api/results/runs'] = runs; },
            function (e) { ANSWERS['/api/results/runs'] = runs; throw e; }));
  });

  test('results: Choose results opens one modeless window, with the run in it', function () {
    var ctx = rig();
    return done(ctx, App.Results.handleCommand('results open ' + RUN).then(function () {
      App.runAction({ action: 'chooseResults' });
      App.runAction({ action: 'chooseResults' });
      var windows = ctx.layer.querySelectorAll('.dlg-results');
      T.eq(windows.length, 1, 'a second press brings the same window forward');
      T.eq(ctx.layer.querySelectorAll('.scrim').length, 0, 'no scrim: the viewport stays live');
      T.ok(windows[0].querySelector('[data-res="phase"]'), 'the phase can be chosen');
      T.ok(windows[0].textContent.indexOf(RUN) >= 0, 'the run is named');
    }));
  });

  test("results: the window's controls and buttons are the results commands", function () {
    var ctx = rig();
    return done(ctx, App.Results.handleCommand('results open ' + RUN).then(function () {
      App.runAction({ action: 'chooseResults' });
      var win = dialogTitled(ctx, 'Choose results');
      var phase = win.querySelector('[data-res="phase"]');
      phase.value = '1';
      phase.dispatchEvent(new Event('change'));
      return settle(40).then(function () {
        T.ok(ctx.commands.indexOf('results phase 1') >= 0, ctx.commands.join(' | '));
        T.eq(App.Results.stage(), 1);
        button(dialogTitled(ctx, 'Choose results'), 'Fit range').click();
        button(dialogTitled(ctx, 'Choose results'), 'Download run').click();
        return settle(20);
      }).then(function () {
        T.ok(ctx.commands.indexOf('results range auto') >= 0);
        T.ok(ctx.commands.indexOf('results zip') >= 0);
        T.ok(ctx.downloads.indexOf(RUN + '.zip') >= 0, 'the run is downloaded as a zip');
      });
    }));
  });

  test('results: closing the window lets it be opened again', function () {
    var ctx = rig();
    return done(ctx, App.Results.handleCommand('results open ' + RUN).then(function () {
      App.runAction({ action: 'chooseResults' });
      button(dialogTitled(ctx, 'Choose results'), 'Close').click();
      T.eq(ctx.layer.querySelectorAll('.dlg-results').length, 0);
      App.runAction({ action: 'chooseResults' });
      T.eq(ctx.layer.querySelectorAll('.dlg-results').length, 1);
    }));
  });

  test('results: a menu entry runs the command it carries', function () {
    var ctx = rig();
    return done(ctx, App.Results.handleCommand('results open ' + RUN).then(function () {
      App.runAction({ action: 'resultsRun', cmd: 'results field u' });
      return settle(30);
    }).then(function () {
      T.ok(ctx.commands.indexOf('results field u') >= 0);
      T.eq(App.Results.field().field, 'u');
    }));
  });

  test('results: "Results at node" asks for a number and refuses anything else', function () {
    var ctx = rig();
    return done(ctx, App.Results.handleCommand('results open ' + RUN).then(function () {
      window.prompt = function () { return ' 2 '; };
      App.runAction({ action: 'resultsAtNode' });
      window.prompt = function () { return 'two'; };
      App.runAction({ action: 'resultsAtNode' });
      window.prompt = function () { return null; };
      App.runAction({ action: 'resultsAtNode' });
      return settle(20);
    }).then(function () {
      T.ok(ctx.commands.indexOf('results at 2') >= 0, ctx.commands.join(' | '));
      T.ok(ctx.lines.some(function (l) { return /"two" is not a node number/.test(l); }));
      T.eq(ctx.commands.filter(function (c) { return /^results at/.test(c); }).length, 1,
           'a cancelled prompt asks nothing');
    }));
  });

  test('results: Plot opens the plot window, and its controls change the plot', function () {
    var ctx = rig();
    return done(ctx, App.Results.handleCommand('results open ' + RUN).then(function () {
      App.runAction({ action: 'plotResults' });
      return settle(60);
    }).then(function () {
      var win = dialogTitled(ctx, 'Plot along the wall');
      T.ok(win, 'the plot window is open');
      T.ok(win.querySelector('svg'), 'with the figure in it');
      var quantity = win.querySelector('[data-res="plot-quantity"]');
      quantity.value = 'N';
      quantity.dispatchEvent(new Event('change'));
      return settle(60);
    }).then(function () {
      T.ok(ctx.commands.indexOf('results plot wall N') >= 0, ctx.commands.join(' | '));
      button(dialogTitled(ctx, 'Plot along the wall'), 'Close').click();
      T.ok(!dialogTitled(ctx, 'Plot along the wall'));
    }));
  });

  test('results: the Results menu lists the phases and fields of the open run', function () {
    var ctx = rig();
    return done(ctx, App.Results.handleCommand('results open ' + RUN).then(function () {
      return settle(30);
    }).then(function () {
      var menu = (App.MENUS || []).filter(function (m) { return m.label === 'Results'; })[0];
      T.ok(menu, 'there is a Results menu');
      var phase = menu.items.filter(function (i) { return i && i.label === 'Phase'; })[0];
      var fields = menu.items.filter(function (i) { return i && i.label === 'Field'; })[0];
      T.eq(phase.sub.length, 2, 'one entry per phase');
      T.ok(phase.sub[1].checked, 'the phase on screen is ticked');
      T.ok(fields.sub.some(function (s) { return s.cmd === 'results field uy'; }));
    }));
  });

})();
