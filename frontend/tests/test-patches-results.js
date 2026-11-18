/* Results mode's windows and actions (frontend/js/patches.js): "View results", the Choose
   results window, the plot window, "Results at node", and the Results menu.

   Opened the way the app opens them -- `App.runAction` after `LivePatches.install()` --
   with the server's results routes answered by a stand-in for one two-stage run. Every
   `results ...` command the windows issue goes through `App.Results.handleCommand`, and
   is recorded there: the windows are only ever a face on those commands. */

(function () {

  var directDownload = App.Results.download;
  var RUN = 'Deck_2026-01-01_00-00';
  var BASE = '/api/results/runs/' + RUN;

  var STAGES = [
    { index: 1, name: '1_Initial', stage: 'Initial', base: 'Deck_1', results: true,
      results_file: 'Deck_1.post.res', mesh_file: 'Deck_1.post.msh', json: [] },
    { index: 2, name: '2_Dig', stage: 'Dig', base: 'Deck_2', results: true,
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
      { index: 2, name: '2_Dig', stage: 'Dig', points: [[0, -5], [10, -2], [0, 0]],
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
                 'setMode', 'Download', 'MODES', 'setCoords', 'ResultsView'];

  function rig(freshMode) {
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
    // No save window here: a test must not depend on what the browser makes of its click.
    App.Download = Object.assign({}, App.Download, {
      pickFile: function () { return Promise.resolve(null); },
      anchor: function (name) { ctx.downloads.push(name); }
    });
    App.state = { mode: 'results' };
    App.runAction = function () {};
    App.selectObject = function () {};
    App.setMode = function (mode) { App.state.mode = mode; };
    if (freshMode) {
      App.MODES = App.MODES.filter(function (mode) { return mode.id !== 'results'; });
      App.setCoords = function () {};
      App.ResultsView = {
        clear: function () {},
        isShowing: function () { return true; },
        describeAt: function (point) { return 'Probe x=' + point.x; }
      };
    }
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

  test('results: server downloads click a temporary anchor with the supplied URL and filename', function () {
    var click = HTMLAnchorElement.prototype.click, link;
    HTMLAnchorElement.prototype.click = function () {
      link = this;
      T.ok(this.isConnected, 'the link is attached before clicking');
      T.eq(this.getAttribute('href'), '/api/results/runs/run-1/archive');
      T.eq(this.download, 'run-1.zip');
    };
    try {
      directDownload('/api/results/runs/run-1/archive', 'run-1.zip');
      T.ok(link);
      T.eq(link.isConnected, false, 'the download leaves no link in the page');
    } finally {
      HTMLAnchorElement.prototype.click = click;
      if (link) link.remove();
    }
  });

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
      T.ok(windows[0].querySelector('[data-res="stage"]'), 'the stage can be chosen');
      T.ok(windows[0].textContent.indexOf(RUN) >= 0, 'the run is named');
    }));
  });

  test("results: the window's controls and buttons are the results commands", function () {
    var ctx = rig();
    return done(ctx, App.Results.handleCommand('results open ' + RUN).then(function () {
      App.runAction({ action: 'chooseResults' });
      var win = dialogTitled(ctx, 'Choose results');
      var stage = win.querySelector('[data-res="stage"]');
      stage.value = '1';
      stage.dispatchEvent(new Event('change'));
      return settle(40).then(function () {
        T.ok(ctx.commands.indexOf('results stage 1') >= 0, ctx.commands.join(' | '));
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

  test('results: "Value at a node" asks for a number in an app window and refuses anything else',
       function () {
    var ctx = rig();
    window.prompt = function () { throw new Error('the browser prompt must not open'); };
    function win() { return dialogTitled(ctx, 'Value at a node'); }
    function input() { return win().querySelector('input[name=name]'); }
    return done(ctx, App.Results.handleCommand('results open ' + RUN).then(function () {
      App.runAction({ action: 'resultsAtNode' });
      T.ok(win().classList.contains('name-dialog-window'), 'the app window, not a prompt');
      input().value = ' 2 ';
      button(win(), 'OK').click();
      return settle(20);
    }).then(function () {
      T.ok(ctx.commands.indexOf('results at 2') >= 0, ctx.commands.join(' | '));
      T.ok(!win(), 'closed after OK');
      App.runAction({ action: 'resultsAtNode' });
      input().value = 'two';
      button(win(), 'OK').click();
      T.ok(win(), 'a refused number keeps the window open');
      T.eq(win().querySelector('.mesh-settings-message').textContent,
           '"two" is not a node number.');
      button(win(), 'Cancel').click();
      return settle(20);
    }).then(function () {
      T.ok(!win());
      T.eq(ctx.commands.filter(function (c) { return /^results at/.test(c); }).length, 1,
           'a refused or cancelled number asks nothing');
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

  test('results: the Results menu lists the stages and fields of the open run', function () {
    var ctx = rig();
    return done(ctx, App.Results.handleCommand('results open ' + RUN).then(function () {
      return settle(30);
    }).then(function () {
      var menu = (App.MENUS || []).filter(function (m) { return m.label === 'Results'; })[0];
      T.ok(menu, 'there is a Results menu');
      var stage = menu.items.filter(function (i) { return i && i.label === 'Stage'; })[0];
      var fields = menu.items.filter(function (i) { return i && i.label === 'Field'; })[0];
      T.eq(stage.sub.length, 2, 'one entry per stage');
      T.ok(stage.sub[1].checked, 'the stage on screen is ticked');
      T.ok(fields.sub.some(function (s) { return s.cmd === 'results field uy'; }));
    }));
  });

  test('results: every display control issues its command and updates the shared options', function () {
    var ctx = rig();
    function change(name, value, checked) {
      var control = dialogTitled(ctx, 'Choose results').querySelector('[data-res="' + name + '"]');
      T.ok(control, name + ' is present');
      if (checked === undefined) control.value = value; else control.checked = checked;
      control.dispatchEvent(new Event('change'));
      return settle();
    }
    return done(ctx, App.Results.handleCommand('results open ' + RUN).then(function () {
      App.runAction({ action: 'chooseResults' });
      return change('field', 'u');
    }).then(function () { return change('bands', '8'); })
      .then(function () { return change('bands', '0'); })
      .then(function () { return change('map', 'viridis'); })
      .then(function () { return change('reverse', null, true); })
      .then(function () { return change('mesh', null, false); })
      .then(function () { return change('loads', null, false); })
      .then(function () { return change('deform', '10'); })
      .then(function () { return change('lim-min', '-0.03'); })
      .then(function () {
        var options = App.Results.options();
        T.eq(options.bands, 0);
        T.eq(options.reversed, true);
        T.eq(options.mesh, false);
        T.eq(options.loads, false);
        T.eq(options.deform, 10);
        T.near(options.min, -0.03, 1e-10);
        dialogTitled(ctx, 'Choose results').querySelector('[data-res="lim-auto"]').click();
        return settle();
      }).then(function () {
        T.eq(App.Results.options().min, null);
        ['results field u', 'results bands 8', 'results smooth', 'results reverse on',
         'results mesh off', 'results loads off', 'results deform 10', 'results range auto']
          .forEach(function (command) { T.ok(ctx.commands.indexOf(command) >= 0, command); });
      }));
  });

  /* A stage catalogue with a water pressure in it, and stages that solved
     `calculation`, for as long as `body` runs. */
  function withWater(calculation, body) {
    var fields = ANSWERS.fields, stages = ANSWERS.run.stages;
    ANSWERS.fields = JSON.parse(JSON.stringify(fields));
    ANSWERS.fields.groups.push({ name: 'Groundwater', fields: [
      { name: 'pw', label: 'Pore pressure', unit: 'kPa', locations: ['nodes'] }] });
    ANSWERS.run.stages = stages.map(function (s) {
      return Object.assign({}, s, { calculation: calculation });
    });
    function back() { ANSWERS.fields = fields; ANSWERS.run.stages = stages; }
    return Promise.resolve().then(body).then(back, function (e) { back(); throw e; });
  }

  test('results: a coupled stage offers the zero pressure line as a box, unticked', function () {
    return withWater('mechanical', function () {
      var ctx = rig();
      var box = function () {
        return dialogTitled(ctx, 'Choose results').querySelector('[data-res="zeroline"]');
      };
      return done(ctx, App.Results.handleCommand('results open ' + RUN).then(function () {
        App.runAction({ action: 'chooseResults' });
        return settle();
      }).then(function () {
        T.ok(box(), 'the box is there');
        T.eq(box().checked, false, 'unticked by default');
        box().checked = true;
        box().dispatchEvent(new Event('change'));
        return settle();
      }).then(function () {
        T.ok(ctx.commands.indexOf('results zeroline on') >= 0, ctx.commands.join(' | '));
        T.eq(App.Results.options().zeroLine, true);
        T.eq(box().checked, true, 'redrawn ticked');
        var menu = (App.MENUS || []).filter(function (m) { return m.label === 'Results'; })[0];
        var colours = menu.items.filter(function (i) { return i && i.label === 'Colours'; })[0];
        var item = colours && colours.sub.filter(function (s) {
          return s.label === 'Show zero pressure line';
        })[0];
        T.ok(item && item.checked, 'and the menu item is ticked with it');
      }));
    });
  });

  test('results: a flow stage has no zero pressure box: the line is always drawn', function () {
    return withWater('flow', function () {
      var ctx = rig();
      return done(ctx, App.Results.handleCommand('results open ' + RUN).then(function () {
        App.runAction({ action: 'chooseResults' });
        return settle();
      }).then(function () {
        T.ok(!dialogTitled(ctx, 'Choose results').querySelector('[data-res="zeroline"]'));
        T.ok(App.Results.zeroLineShown(), 'the line is on screen regardless');
      }));
    });
  });

  test('results: a stage with no water pressure has no zero pressure box', function () {
    var ctx = rig();
    return done(ctx, App.Results.handleCommand('results open ' + RUN).then(function () {
      App.runAction({ action: 'chooseResults' });
      return settle();
    }).then(function () {
      T.ok(!dialogTitled(ctx, 'Choose results').querySelector('[data-res="zeroline"]'));
    }));
  });

  /* App.UI keeps the first menu layer it finds, so this one stays for the whole page. */
  function menuLayer() {
    var layer = document.getElementById('menu-layer');
    if (!layer) {
      layer = document.createElement('div');
      layer.id = 'menu-layer';
      document.body.appendChild(layer);
    }
    return layer;
  }

  /* The Save menus open: in front of the dialogs, in their layer. */
  function saveMenus() { return document.querySelectorAll('#modal-layer .menu'); }

  function menuItem(label) {
    return Array.prototype.filter.call(document.querySelectorAll('#modal-layer .menu-item'), function (row) {
      return row.textContent.indexOf(label) === 0;
    })[0];
  }

  function press(target) {
    target.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
  }

  test('results: plot member selection and the Save menu use the plotted data', function () {
    var ctx = rig();
    menuLayer();
    return done(ctx, App.Results.handleCommand('results open ' + RUN).then(function () {
      App.runAction({ action: 'plotResults' });
      return settle(60);
    }).then(function () {
      var win = dialogTitled(ctx, 'Plot along the wall');
      var member = win.querySelector('[data-res="plot-member"]');
      member.dispatchEvent(new Event('change'));
      return settle(60);
    }).then(function () {
      var win = dialogTitled(ctx, 'Plot along the wall');
      T.ok(!button(win, 'Save SVG'), 'one Save button replaces the four');
      var save = button(win, 'Save ▾');
      T.eq(save.getAttribute('aria-haspopup'), 'menu');
      save.click();
      T.eq(save.getAttribute('aria-expanded'), 'true');
      var menu = saveMenus()[0];
      T.ok(menu && menu.parentNode === win.parentNode, 'the menu is in the dialogs\' layer');
      T.ok(win.compareDocumentPosition(menu) & Node.DOCUMENT_POSITION_FOLLOWING,
           'and in front of the plot window');
      T.eq(menuLayer().querySelectorAll('.menu').length, 0, 'not behind it, in the menu layer');
      T.eq(['PNG', 'PDF', 'SVG', 'CSV'].filter(menuItem).length, 4, 'every format is offered');
      menuItem('SVG').click();
      T.eq(save.getAttribute('aria-expanded'), 'false', 'a pick closes the menu');
      save.click();
      menuItem('CSV').click();
      return settle();
    }).then(function () {
      T.ok(ctx.commands.indexOf('results plot wall') >= 0);
      T.ok(ctx.commands.indexOf('results plot svg') >= 0);
      T.ok(ctx.commands.indexOf('results plot csv') >= 0);
      T.ok(ctx.downloads.some(function (name) { return /\.svg$/.test(name); }));
      T.ok(ctx.downloads.some(function (name) { return /\.csv$/.test(name); }));

      var save = button(dialogTitled(ctx, 'Plot along the wall'), 'Save ▾');
      function menus() { return saveMenus().length; }
      press(save);
      save.click();
      T.eq(menus(), 1, 'a click opens the menu');
      // The press closes it, as any press outside a menu does; its click must not reopen it.
      press(save);
      save.click();
      T.eq(menus(), 0, 'a second click closes it');
      return settle().then(function () {
        save.click();
        T.eq(menus(), 1, 'a keyboard click opens it');
        save.click();
        T.eq(menus(), 0, 'and closes it again');

        var bottom = window.innerHeight - 2;
        save.getBoundingClientRect = function () {
          return { left: 20, right: 90, top: bottom - 24, bottom: bottom, width: 70, height: 24 };
        };
        save.click();
        var menu = saveMenus()[0];
        T.ok(parseFloat(menu.style.top) + menu.getBoundingClientRect().height <= bottom - 24 + 1,
             'without room below, the menu opens above the button');
        delete save.getBoundingClientRect;
        App.UI.closePopups(0);
      });
    }));
  });

  test('results: the dock actions work and leaving Results closes both floating windows', function () {
    var dock = document.createElement('div');
    dock.id = 'dock';
    dock.innerHTML = '<div id="panel-results"><div id="panel-results-body"></div></div><span id="sb-hint"></span>';
    document.body.appendChild(dock);
    var ctx = rig(true);
    return done(ctx, App.Results.handleCommand('results open ' + RUN).then(function () {
      App.setMode('results');
      T.ok(dialogTitled(ctx, 'Choose results'), 'entering Results opens the chooser');
      App.setCoords(12, -3, 0);
      T.eq(dock.querySelector('#sb-hint').textContent, 'Probe x=12');
      dock.querySelector('[data-cmd="results range auto"]').click();
      App.runAction({ action: 'plotResults' });
      return settle(60);
    }).then(function () {
      T.ok(dialogTitled(ctx, 'Plot along the wall'), 'the plot opens beside the chooser');
      T.ok(ctx.commands.indexOf('results range auto') >= 0);
      button(dialogTitled(ctx, 'Plot along the wall'), 'Save ▾').click();
      T.eq(saveMenus().length, 1, 'the Save menu is open');
      App.setMode('soil');
      T.eq(dialogTitled(ctx, 'Choose results'), undefined);
      T.eq(dialogTitled(ctx, 'Plot along the wall'), undefined);
      T.eq(saveMenus().length, 0, 'its menu closes with it');
      T.eq(dock.querySelector('#panel-results').hidden, true);
    }).then(function () { dock.remove(); }, function (error) { dock.remove(); throw error; }));
  });

})();
