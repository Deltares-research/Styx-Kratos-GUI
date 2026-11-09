/* Live shell editing, with real model/explorer code and recorded server writes. */
(function () {
  var explorer = Object.assign({}, App.Explorer);
  var materialsDialog = App.Dialogs.materials;
  function copy(value) { return JSON.parse(JSON.stringify(value)); }
  function settle() { return new Promise(function (resolve) { setTimeout(resolve, 0); }); }

  function withShell(body) {
    var saved = Object.assign({}, App), prompt = window.prompt;
    var host = document.createElement('div');
    host.innerHTML = '<div id="tree-model"></div><div id="grid-selection"></div>'
      + '<div id="list-phases"></div><div id="modal-layer"></div>'
      + '<div id="dock"><div id="panel-results"><div id="panel-results-body"></div></div></div>';
    document.body.appendChild(host);
    var ctx = { requests: [], lines: [], selected: [], refreshed: 0, loaded: 0, failure: null };
    ['Model', 'Explorer', 'Dialogs', 'Calculate', 'Results'].forEach(function (key) {
      App[key] = Object.assign({}, App[key]);
    });
    App.Explorer = Object.assign({}, explorer);
    App.Dialogs.materials = materialsDialog;
    App.TREES = Object.assign({}, App.TREES);
    App.OBJECT_PROPS = Object.assign({}, App.OBJECT_PROPS);
    App.state = { mode: 'soil', modelMode: '2d', selection: null };
    App.Model.apply(copy(window.VIEWPORT_PAYLOADS.project));
    ctx.server = copy(App.PROJECT);
    App.Model.load = function () {
      ctx.loaded += 1;
      App.Model.apply(copy(ctx.server));
      return Promise.resolve(App.PROJECT);
    };
    App.Viewport = {
      refresh: function () { ctx.refreshed += 1; return Promise.resolve(); },
      isVisible: function () { return true; },
      setVisible: function () {}, setMode: function () {},
      coloredPartKeys: function () { return ['soil_L1', 'soil_L2']; },
      partColor: function () { return '#123456'; },
      syncPartColors: function () { ctx.colored = (ctx.colored || 0) + 1; },
      applyStageVisibility: function () {},
      getScene: function () { return null; },
      clearImportedMesh: function () {}, forgetConditionEyes: function () {}
    };
    App.Menu = { mountBar: function () {}, openAt: function () {} };
    App.ResultsView = { clear: function () {} };
    App.Command = {
      ok: function (text) { ctx.lines.push('ok:' + text); },
      note: function (text) { ctx.lines.push('note:' + text); },
      err: function (text) { ctx.lines.push('err:' + text); },
      write: function () {}, run: function () {}
    };
    function request(method, path, value) {
      ctx.requests.push({ method: method, path: path, body: copy(value) });
      if (ctx.failure) return Promise.reject(ctx.failure);
      ctx.server = method === 'PUT' && path === '/api/project'
        ? copy(value) : Object.assign({}, ctx.server, copy(value));
      return Promise.resolve(method === 'PUT' && path === '/api/project'
        ? copy(ctx.server) : { project: copy(ctx.server), notes: ['Converted library values'] });
    }
    App.Api = {
      base: '',
      patch: function (path, value) { return request('PATCH', path, value); },
      put: function (path, value) { return request('PUT', path, value); },
      post: function (path, value) { return request('POST', path, value || {}); }
    };
    App.runAction = function () {};
    App.setMode = function (mode) { App.state.mode = mode; };
    App.selectObject = function (key) { App.state.selection = key; ctx.selected.push(key); };
    App.LivePatches.resetForTests();
    App.LivePatches.install();

    function restore() {
      App.History.reset();
      App.PartColors.on.clear();
      App.LivePatches.resetForTests();
      host.remove();
      window.prompt = prompt;
      Object.keys(App).forEach(function (key) {
        if (!Object.prototype.hasOwnProperty.call(saved, key)) delete App[key];
      });
      Object.assign(App, saved);
      App.Model.rebuildDerived();
    }
    return Promise.resolve().then(function () { return body(ctx, host); })
      .then(settle, function (error) {
        return settle().then(function () { throw error; });
      }).then(restore, function (error) { restore(); throw error; });
  }

  test('mesh explorer colour squares track individual, mixed and group states after expand-all', function () {
    return withShell(function (ctx, host) {
      App.state.mode = 'mesh';
      App.TREES.mesh = [
        { label: 'Soil', obj: 'soil', children: [
          { label: 'Upper', obj: 'soil_L1', eye: true },
          { label: 'Lower', obj: 'soil_L2', eye: true }
        ] },
        { label: 'No elements', obj: 'unmeshed', eye: true }
      ];
      App.PartColors.on.clear();
      App.Explorer.mountTree('mesh');
      var squares = host.querySelectorAll('.tree-paint:not(.empty-slot)');
      T.eq(squares.length, 3);
      T.eq(host.querySelectorAll('.tree-paint.empty-slot').length, 1);
      squares[1].click();
      T.ok(squares[1].classList.contains('on'));
      T.ok(squares[0].classList.contains('mixed'));
      squares[0].click();
      T.eq(App.PartColors.on.stateOf(['soil_L1', 'soil_L2']), 'on');
      T.ok(squares[0].classList.contains('on'));
      squares[0].click();
      T.eq(App.PartColors.on.stateOf(['soil_L1', 'soil_L2']), 'off');
      T.eq(ctx.colored, 3);
      App.Explorer.expandAll(true);
      T.eq(host.querySelectorAll('.tree-paint:not(.empty-slot)').length, 3);
      T.ok(ctx.lines.some(function (text) { return text === 'note:Coloured: Upper'; }));
    });
  });

  test('staged explorer checks persist the selected stage and preserve their inherited state', function () {
    return withShell(function (ctx, host) {
      App.state.mode = 'staged';
      App.state.phase = App.PROJECT.stages[0].id;
      App.Explorer.mountTree('staged');
      var check = host.querySelector('.stage-check');
      T.ok(check, 'stageable model parts have checkboxes');
      var keys = check.dataset.keys.split('\n');
      var wasOn = App.Stages.stateIn(App.PROJECT, App.state.phase, keys) === 'on';
      check.click();
      return settle().then(function () {
        T.eq(ctx.requests[0].path, '/api/project/stages');
        T.eq(App.Stages.stateIn(App.PROJECT, App.state.phase, keys), wasOn ? 'off' : 'on');
        var current = Array.prototype.filter.call(host.querySelectorAll('.stage-check'), function (node) {
          return node.dataset.keys === keys.join('\n');
        })[0];
        T.ok(current, 'the saved stage is represented in the remounted tree');
        T.eq(current.classList.contains('off'), wasOn);
      });
    });
  });

  test('typed boundary, water, units and script writes refresh the model and report refusals', function () {
    return withShell(function (ctx) {
      var other = App.Units.systems().filter(function (system) {
        return system.name !== App.Units.current();
      })[0].name;
      var commands = [
        ['boundary standard', '/api/project/conditions'],
        ['water -4', '/api/project/water'],
        ['units ' + other, '/api/project/units'],
        ['script test-model.py', '/api/project/script/save']
      ];
      return commands.reduce(function (chain, entry) {
        return chain.then(function () {
          var before = ctx.requests.length;
          App.Command.run(entry[0]);
          return settle().then(function () {
            T.eq(ctx.requests.length, before + 1, entry[0]);
            T.eq(ctx.requests[before].path, entry[1]);
          });
        });
      }, Promise.resolve()).then(function () {
        T.ok(ctx.lines.some(function (line) { return /Converted library values/.test(line); }));
        T.eq(ctx.refreshed, 3, 'boundary, water and units refresh; saving a script does not');
        ctx.failure = new Error('Write refused');
        return ['boundary standard', 'water -5', 'units ' + App.Units.systems().filter(function (system) {
          return system.name !== App.Units.current();
        })[0].name, 'script refused.py'].reduce(function (chain, command) {
          return chain.then(function () { App.Command.run(command); return settle(); });
        }, Promise.resolve());
      }).then(function () {
        T.eq(ctx.lines.filter(function (line) { return /err:Write refused/.test(line); }).length, 4);
      });
    });
  });

  test('selection commits route every structural kind through its owner with the shared sections', function () {
    return withShell(function () {
      var cases = [
        ['Loads', 'LOADS', 'isLoadKey'],
        ['Beams', 'BEAMS', 'isBeamKey', 'BEAM_SECTIONS'],
        ['Anchors', 'ANCHORS', 'isAnchorKey', 'ANCHOR_SECTIONS'],
        ['Interfaces', 'INTERFACES', 'isInterfaceKey', 'INTERFACE_SECTIONS'],
        ['NormalLoads', 'NORMAL_LOADS', 'isNormalLoadKey'],
        ['BoundaryConditions', 'BOUNDARY_CONDITIONS', 'isConditionKey']
      ];
      var modules = {};
      cases.forEach(function (entry) {
        modules[entry[0]] = App[entry[0]];
        App[entry[0]] = Object.assign({}, App[entry[0]]);
      });
      return cases.reduce(function (chain, entry, index) {
        return chain.then(function () {
          var id = 'commit_' + index, record = { id: id, name: 'Edited' }, saved;
          App[entry[1]] = [record];
          App[entry[0]][entry[2]] = function (key) { return key === id; };
          App[entry[0]].save = function (value, sections) {
            saved = [value, sections]; return Promise.resolve(value);
          };
          return App.commitSelectionEdit(id).then(function () {
            T.eq(saved[0], record);
            if (entry[3]) T.eq(saved[1], App[entry[3]]);
          });
        });
      }, Promise.resolve()).then(function () {
        Object.keys(modules).forEach(function (key) { App[key] = modules[key]; });
      }, function (error) {
        Object.keys(modules).forEach(function (key) { App[key] = modules[key]; });
        throw error;
      });
    });
  });

  test('soil selection commits save geometry and roll rejected edits back to the stored project', function () {
    return withShell(function (ctx) {
      var original = App.LAYERS[0].name;
      App.LAYERS[0].name = 'Renamed layer';
      return App.commitSelectionEdit('soil_' + App.LAYERS[0].id).then(function () {
        T.eq(ctx.requests[0].path, '/api/project/layers');
        T.eq(ctx.requests[0].body.layers[0].name, 'Renamed layer');
        T.ok(ctx.requests[0].body.domain);
        T.ok(original !== App.LAYERS[0].name);
        App.LAYERS[0].name = 'Rejected rename';
        ctx.failure = new Error('Layer edit refused');
        return App.commitSelectionEdit('soil_' + App.LAYERS[0].id);
      }).then(function () {
        T.eq(ctx.loaded, 1);
        T.eq(App.LAYERS[0].name, 'Renamed layer');
        T.ok(ctx.lines.indexOf('err:Layer edit refused') >= 0);
      });
    });
  });

  test('opening a project reads the selected file, uses its filename, and reports invalid or rejected files', function () {
    return withShell(function (ctx) {
      var click = HTMLInputElement.prototype.click, input;
      HTMLInputElement.prototype.click = function () { input = this; };
      function choose(name, text) {
        App.LivePatches.openProject();
        T.eq(input.accept, '.json,application/json');
        Object.defineProperty(input, 'files', { value: [{
          name: name, text: function () { return Promise.resolve(text); }
        }] });
        input.dispatchEvent(new Event('change'));
        T.eq(input.isConnected, false);
        return settle();
      }
      function restore() { HTMLInputElement.prototype.click = click; }
      return choose('Opened site.json', JSON.stringify(ctx.server)).then(function () {
        T.eq(ctx.requests[0].method, 'POST');
        T.eq(ctx.requests[0].path, '/api/project/open');
        T.eq(ctx.requests[0].body.name, 'Opened site');
        T.eq(App.PROJECT.name, 'Opened site');
        return choose('Broken.json', 'not json');
      }).then(function () {
        T.eq(ctx.requests.length, 1, 'invalid JSON never reaches the server');
        T.ok(ctx.lines.some(function (line) { return /Could not open Broken.json/.test(line); }));
        ctx.failure = new Error('Unsupported project');
        return choose('Rejected.json', JSON.stringify(ctx.server));
      }).then(function () {
        T.eq(App.PROJECT.name, 'Opened site');
        T.ok(ctx.lines.some(function (line) { return /Unsupported project/.test(line); }));
        App.LivePatches.openProject();
        Object.defineProperty(input, 'files', { value: [] });
        input.dispatchEvent(new Event('change'));
        T.eq(input.isConnected, false);
        T.eq(ctx.requests.length, 2, 'cancelling does not write');
      }).then(restore, function (error) { restore(); throw error; });
    });
  });

  test('new project waits for confirmation and save failures report the picker error', function () {
    return withShell(function (ctx, host) {
      App.runAction({ action: 'newProject' });
      T.eq(ctx.requests, []);
      var dialog = host.querySelector('.dialog');
      T.ok(/New project/.test(dialog.textContent));
      var ok = Array.prototype.filter.call(dialog.querySelectorAll('button'), function (button) {
        return button.textContent === 'OK';
      })[0];
      ok.click();
      return settle().then(function () {
        T.eq(ctx.requests[0].path, '/api/project/new');
        App.Download = Object.assign({}, App.Download, {
          pickFile: function () { return Promise.reject(new Error('Picker unavailable')); }
        });
        return App.LivePatches.saveProject();
      }).then(function () {
        T.ok(ctx.lines.indexOf('err:Could not save the project: Picker unavailable') >= 0);
      });
    });
  });

  test('renaming a drawn body and a boundary condition saves through their respective owners', function () {
    return withShell(function (ctx) {
      App.PROJECT.custom_parts = [{ key: 'drawn_rename', label: 'Old body' }];
      window.prompt = function () { return '  New body  '; };
      return App.LivePatches.renameObject('part', 'drawn_rename').then(function () {
        T.eq(ctx.requests[0].body.custom_parts[0].label, 'New body');
        var record = App.BoundaryConditions.draftDisplacement(App.PROJECT, 'face', { face: 'bottom' });
        App.PROJECT.boundary_conditions = [record];
        App.BOUNDARY_CONDITIONS = [record];
        window.prompt = function () { return 'New support'; };
        return App.LivePatches.renameObject('condition', record.id);
      }).then(function () {
        T.eq(ctx.requests[1].path, '/api/project/conditions');
        T.eq(ctx.requests[1].body.boundary_conditions[0].name, 'New support');
      });
    });
  });

  test('node commands report memberships, mark coincident nodes, and surface index failures', function () {
    return withShell(function (ctx) {
      var index = App.NodeParts.build({
        nodes: [[1, 0, 0, 0], [2, 0, 0, 0]],
        parts: [{ name: 'Soil', kind: 'body', nodes: [1, 2] }]
      }), marked;
      App.Viewport.nodeParts = function () { return Promise.resolve(index); };
      App.Viewport.markNodes = function (points) { marked = points; };
      App.Command.run('node 1');
      return settle().then(function () {
        T.eq(marked, [[0, 0, 0], [0, 0, 0]]);
        T.ok(ctx.lines.some(function (line) { return /Soil/.test(line); }));
        App.Viewport.nodeParts = function () { return Promise.reject(new Error('Node index refused')); };
        App.Command.run('node 2');
        return settle();
      }).then(function () {
        T.ok(ctx.lines.indexOf('err:Node index refused') >= 0);
      });
    });
  });

  test('material save refusal preserves edits for retry and re-enables every footer button', function () {
    return withShell(function (ctx, host) {
      App.Dialogs.materials();
      var dialog = host.querySelector('.dialog'), original = App.MATERIALS[0].name;
      function footer(label) {
        return Array.prototype.filter.call(dialog.querySelectorAll('.dlg-foot .btn'),
          function (button) { return button.textContent.trim() === label; })[0];
      }
      App.MATERIALS[0].name = 'Edited soil';
      ctx.failure = new Error('Material library refused');
      footer('OK').click();
      T.ok(footer('OK').disabled);
      return settle().then(function () {
        T.eq(ctx.requests[0].path, '/api/project/materials');
        T.eq(App.MATERIALS[0].name, 'Edited soil', 'the user can correct the refused draft');
        T.ok(original !== App.MATERIALS[0].name);
        T.ok(dialog.isConnected);
        Array.prototype.forEach.call(dialog.querySelectorAll('.dlg-foot .btn'), function (button) {
          T.eq(button.disabled, false);
        });
        T.ok(ctx.lines.indexOf('err:Material library refused') >= 0);
        ctx.failure = null;
        footer('OK').click();
        return settle();
      }).then(function () {
        T.eq(ctx.requests.length, 2);
        T.eq(dialog.isConnected, false);
        T.eq(App.MATERIALS[0].name, 'Edited soil');
        T.ok(ctx.refreshed > 0);
      });
    });
  });

  test('material Cancel restores the library and sends no request', function () {
    return withShell(function (ctx, host) {
      var original = copy(App.MATERIALS);
      App.Dialogs.materials();
      App.MATERIALS[0].name = 'Unsaved material';
      var cancel = Array.prototype.filter.call(host.querySelectorAll('.dlg-foot .btn'),
        function (button) { return button.textContent.trim() === 'Cancel'; })[0];
      cancel.click();
      T.eq(App.MATERIALS, original);
      T.eq(ctx.requests, []);
      T.eq(host.querySelector('.dialog'), null);
    });
  });

  test('stage numerical controls reject invalid values and persist valid numbers and reset flags', function () {
    return withShell(function (ctx, host) {
      var id = App.PROJECT.stages[1].id;
      App.state.mode = 'staged'; App.state.phase = id;
      App.PROJECT.stages[1].time_step = 1;
      App.Explorer.mountPhases();
      function control(label) {
        var rows = Array.prototype.slice.call(host.querySelectorAll('#list-phases .pgrid-row'));
        var row = rows.filter(function (node) {
          return node.querySelector('.pgrid-key').textContent === label;
        })[0];
        T.ok(row, label);
        return row.querySelector('input');
      }
      function change(label, text) {
        var input = control(label);
        input.value = text;
        input.dispatchEvent(new Event('change', { bubbles: true }));
      }
      [
        ['Max iterations', 'abc', 'must be a number'],
        ['Max iterations', '1.5', 'must be a whole number'],
        ['Max iterations', '0', 'must be at least 1'],
        ['Time step', '-1', 'must be greater than 0'],
        ['Tolerated error', '0', 'must be greater than 0']
      ].forEach(function (entry) {
        var original = control(entry[0]).value;
        change(entry[0], entry[1]);
        T.eq(control(entry[0]).value, original, 'the invalid field is restored');
        T.ok(ctx.lines[ctx.lines.length - 1].indexOf(entry[2]) >= 0);
      });
      T.eq(ctx.requests, [], 'invalid numerical settings never reach the server');
      change('Max iterations', '30');
      return settle().then(function () {
        T.eq(App.PROJECT.stages[1].max_iterations, 30);
        change('Time step', '0,25');
        return settle();
      }).then(function () {
        T.eq(App.PROJECT.stages[1].time_step, 0.25);
        var reset = control('Reset displacements to zero');
        var desired = !reset.checked;
        reset.checked = desired; reset.dispatchEvent(new Event('change', { bubbles: true }));
        return settle().then(function () {
          T.eq(App.PROJECT.stages[1].reset_displacements, desired);
          T.eq(ctx.requests.length, 3);
          ctx.requests.forEach(function (request) {
            T.eq(request.path, '/api/project/stages');
            T.eq(request.body.stages[1].id, id);
          });
        });
      });
    });
  });

  test('stage insert and duplicate use the selected parent and refuse failed sequence writes', function () {
    return withShell(function (ctx, host) {
      App.state.mode = 'staged'; App.state.phase = App.PROJECT.stages[1].id;
      var selected = App.PROJECT.stages[1], selectedId = selected.id;
      selected.max_iterations = 37;
      selected.tolerated_error = 0.0007;
      selected.time_step = 2.5;
      selected.reset_displacements = true;
      ctx.server = copy(App.PROJECT);
      var original = copy(App.PROJECT.stages);
      App.Explorer.mountPhases();
      var before = App.PROJECT.stages.length;
      host.querySelectorAll('.stage-toolbar button')[1].click();
      return settle().then(function () {
        T.eq(App.PROJECT.stages.length, before + 1);
        T.eq(ctx.requests[0].path, '/api/project/stages');
        var inserted = App.PROJECT.stages[1];
        T.ok(!original.some(function (stage) { return stage.id === inserted.id; }), 'insertion has a fresh id');
        T.eq(inserted.parent, selected.parent);
        T.eq(App.PROJECT.stages[2].id, selectedId, 'insertion is immediately before the selected stage');
        T.eq(App.PROJECT.stages[2].parent, inserted.id);
        T.eq(App.PROJECT.stages.filter(function (stage) { return stage.id !== inserted.id; }),
          original.map(function (stage) {
            return stage.id === selectedId ? Object.assign({}, stage, { parent: inserted.id }) : stage;
          }), 'insertion preserves every other stage');
        T.eq(ctx.requests[0].body.stages, App.PROJECT.stages);
        T.eq(App.state.phase, selectedId);
        host.querySelectorAll('.stage-toolbar button')[2].click();
        return settle();
      }).then(function () {
        T.eq(App.PROJECT.stages.length, before + 2);
        var duplicate = App.PROJECT.stages[3];
        T.eq(App.PROJECT.stages[2].id, selectedId);
        T.eq(duplicate.parent, selectedId, 'the copy starts from the selected stage');
        T.ok(!ctx.requests[0].body.stages.some(function (stage) { return stage.id === duplicate.id; }));
        T.eq(duplicate.name, selected.name + ' (copy)');
        ['calculation', 'reset_displacements', 'max_iterations', 'tolerated_error', 'time_step'].forEach(function (key) {
          T.eq(duplicate[key], selected[key], 'copied ' + key);
        });
        T.eq(duplicate.activate, []);
        T.eq(duplicate.deactivate, []);
        T.eq(App.PROJECT.stages.filter(function (stage) { return stage.id !== duplicate.id; }),
          ctx.requests[0].body.stages.map(function (stage) {
            return stage.parent === selectedId ? Object.assign({}, stage, { parent: duplicate.id }) : stage;
          }), 'children follow the copy and unrelated stages are unchanged');
        T.eq(ctx.requests[1].path, '/api/project/stages');
        T.eq(ctx.requests[1].body.stages, App.PROJECT.stages);
        var stored = copy(App.PROJECT.stages);
        ctx.failure = new Error('Stage sequence refused');
        host.querySelectorAll('.stage-toolbar button')[0].click();
        return settle().then(function () {
          T.eq(App.PROJECT.stages, stored);
          T.eq(ctx.loaded, 1, 'a refusal reloads the stored sequence');
          T.ok(ctx.lines.indexOf('err:Stage sequence refused') >= 0);
        });
      });
    });
  });

  test('condition checkboxes report refused activation writes without changing the saved condition', function () {
    return withShell(function (ctx, host) {
      var record = App.BoundaryConditions.draftDisplacement(App.PROJECT, 'face', { face: 'bottom' });
      App.Model.apply(Object.assign({}, App.PROJECT, { boundary_conditions: [record] }));
      ctx.server = copy(App.PROJECT);
      App.Explorer.mountTree('soil');
      var check = host.querySelector('.condition-check');
      T.ok(check);
      ctx.failure = new Error('Condition activation refused');
      check.click();
      return settle().then(function () {
        T.eq(App.PROJECT.boundary_conditions[0].active, true);
        T.ok(ctx.lines.some(function (line) { return /err:.*Condition activation refused/.test(line); }));
      });
    });
  });

  test('successful clear-geometry command reloads and redraws only after the server accepts it', function () {
    return withShell(function (ctx) {
      var fetch = window.fetch, order = [];
      window.fetch = function (url, options) {
        T.eq(url, '/api/project/custom_parts');
        T.eq(options.method, 'DELETE');
        order.push('delete');
        return Promise.resolve({ ok: true, json: function () { return Promise.resolve({}); } });
      };
      function restore() { window.fetch = fetch; }
      return Promise.resolve().then(function () { return App.Command.run('cleargeometry'); }).then(function () {
        T.eq(order, ['delete']);
        T.eq(ctx.loaded, 1);
        T.eq(ctx.refreshed, 1);
        T.ok(ctx.lines.indexOf('ok:Custom geometry cleared.') >= 0);
      }).then(restore, function (error) { restore(); throw error; });
    });
  });

  test('running a deck case adopts and displays its own mesh without asking the mesher', function () {
    return withShell(function (ctx) {
      var mesh = window.VIEWPORT_PAYLOADS.imported, shown;
      App.Api.post = function (path, body) {
        ctx.requests.push({ path: path, body: body });
        return Promise.resolve({ project: ctx.server, mesh: mesh });
      };
      App.Viewport.showImportedMesh = function (value) { shown = value; };
      return App.Command.run('run deck-case.py').then(function () {
        T.eq(App.state.mode, 'mesh');
        T.eq(shown, mesh);
        T.eq(ctx.requests.length, 1);
        T.eq(ctx.requests[0].path, '/api/project/script');
        T.ok(ctx.lines.some(function (line) { return /opened with its own mesh/.test(line); }));
        T.ok(ctx.lines.some(function (line) { return /stages are the stages/.test(line); }));
      });
    });
  });
})();
