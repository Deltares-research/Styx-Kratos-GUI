/* Browser authoring paths: real form controls, with only server and viewport effects recorded. */
(function () {
  function project(dimension) {
    return {
      name: 'Authoring test', dimension: dimension || 2, unit_system: 'SI',
      domain: { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 },
      layers: [{ id: 'L1', name: 'Upper', top: 0, bottom: -10, mat: 'soil' },
               { id: 'L2', name: 'Lower', top: -10, bottom: -25, mat: 'soil' }],
      custom_parts: [], loads: [], beams: [], beam_sections: [], panel_sections: [],
      anchors: [], anchor_sections: [], normal_loads: [], boundary_conditions: [],
      mesh: { element_size: 2.5, algorithm_2d: 'meshadapt', algorithm_3d: 'hxt' }
    };
  }

  function drain() {
    return new Promise(function (resolve) { setTimeout(resolve, 0); });
  }

  function withEnvironment(initial, body) {
    var keys = ['PROJECT', 'LOADS', 'BEAMS', 'BEAM_SECTIONS', 'PANEL_SECTIONS', 'ANCHORS',
                'ANCHOR_SECTIONS', 'NORMAL_LOADS', 'MATERIALS', 'MESH_BODY_SELECTION',
                'Api', 'Model', 'Viewport', 'Explorer', 'Command', 'Dialogs', 'DrawInput',
                'state', 'selectObject', 'runAction', 'matById'];
    var saved = {};
    keys.forEach(function (key) { saved[key] = App[key]; });
    var layer = document.getElementById('modal-layer'), owned = !layer;
    if (!layer) {
      layer = document.createElement('div'); layer.id = 'modal-layer';
      document.body.appendChild(layer);
    }
    var originalChildren = Array.prototype.slice.call(layer.children);
    var ctx = { dialogs: [], requests: [], selected: [], logs: [], actions: [],
                applied: [], refreshed: 0, loaded: 0, drawn: null, failure: null };
    function apply(value) {
      App.PROJECT = value;
      App.LOADS = value.loads; App.BEAMS = value.beams;
      App.BEAM_SECTIONS = value.beam_sections; App.PANEL_SECTIONS = value.panel_sections;
      App.ANCHORS = value.anchors; App.ANCHOR_SECTIONS = value.anchor_sections;
      App.NORMAL_LOADS = value.normal_loads;
    }
    apply(initial);
    App.MATERIALS = [{ id: 'soil', name: 'Test soil' }];
    App.matById = function (id) {
      T.eq(id, 'soil'); return App.MATERIALS[0];
    };
    App.MESH_BODY_SELECTION = null;
    App.state = { mode: 'structures', selection: null };
    App.selectObject = function (id) { ctx.selected.push(id); App.state.selection = id; };
    App.runAction = function (spec) { ctx.actions.push(spec.action); };
    App.Command = {
      ok: function (text) { ctx.logs.push(['ok', text]); },
      note: function (text) { ctx.logs.push(['note', text]); },
      err: function (text) { ctx.logs.push(['err', text]); }
    };
    App.Model = {
      apply: function (value) { ctx.applied.push(value); apply(value); },
      load: function () { ctx.loaded += 1; return Promise.resolve(); }
    };
    App.Viewport = {
      refresh: function () { ctx.refreshed += 1; return Promise.resolve(); },
      isVisible: function () { return true; }, hasMesh: function () { return false; }
    };
    App.Explorer = { mountTree: function () {}, mountSelection: function () {} };
    function request(method, path, value) {
      ctx.requests.push({ method: method, path: path,
                          body: JSON.parse(JSON.stringify(value)) });
      if (ctx.failure) return Promise.reject(ctx.failure);
      var next = method === 'PUT' ? value : Object.assign({}, App.PROJECT, value);
      return Promise.resolve(method === 'PATCH' ? { project: next } : next);
    }
    App.Api = {
      patch: function (path, value) { return request('PATCH', path, value); },
      put: function (path, value) { return request('PUT', path, value); },
      post: function (path, value) { return request('POST', path, value); }
    };
    App.Dialogs = {
      draggable: saved.Dialogs.draggable,
      open: function (options) {
        var dialog = { options: options, form: document.createElement('div'), closed: false };
        ctx.dialogs.push(dialog);
        options.build(dialog.form);
        return { close: function () { dialog.closed = true; } };
      }
    };
    App.DrawInput = { start: function (mode, options) { ctx.drawn = { mode: mode, options: options }; } };
    function restore() {
      ['mesh-settings-dialog', 'soil-volume-dialog'].forEach(function (id) {
        var dialog = document.getElementById(id);
        if (dialog) dialog.querySelector('.dlg-x').click();
      });
      Array.prototype.slice.call(layer.children).forEach(function (node) {
        if (originalChildren.indexOf(node) < 0) node.remove();
      });
      if (owned) layer.remove();
      keys.forEach(function (key) { App[key] = saved[key]; });
    }
    return Promise.resolve().then(function () { return body(ctx); })
      .then(function () { restore(); }, function (error) { restore(); throw error; });
  }

  function latest(ctx) { return ctx.dialogs[ctx.dialogs.length - 1]; }
  function field(dialog, label) {
    var labels = dialog.form.querySelectorAll('label.mesh-setting-label');
    for (var i = 0; i < labels.length; i++) {
      if (labels[i].textContent === label) return labels[i].nextElementSibling;
    }
    throw new Error('No field named ' + label);
  }
  function button(dialog, label) {
    var spec = dialog.options.buttons.filter(function (item) { return item.label === label; })[0];
    T.ok(spec, 'No button named ' + label);
    return spec.onClick();
  }
  function change(control, value) {
    control.value = value; control.dispatchEvent(new Event('change', { bubbles: true }));
  }
  function realButton(dialog, text) {
    var found = Array.prototype.filter.call(dialog.querySelectorAll('button'), function (node) {
      return node.textContent === text;
    })[0];
    T.ok(found, 'No button named ' + text); return found;
  }

  test('mesh dialog validates selection and sizes before saving and generating', function () {
    return withEnvironment(project(), function (ctx) {
      App.MeshSettings.open();
      App.MeshSettings.open();
      T.eq(document.querySelectorAll('#mesh-settings-dialog').length, 1);
      var dialog = document.getElementById('mesh-settings-dialog');
      var boxes = dialog.querySelectorAll('.mesh-body-enabled');
      boxes.forEach(function (box) { box.checked = false; box.dispatchEvent(new Event('change')); });
      T.ok(dialog.querySelector('.mesh-body-size').disabled);
      realButton(dialog, 'Apply').click();
      T.ok(/at least one layer/.test(dialog.querySelector('.mesh-settings-message').textContent));
      T.eq(ctx.requests.length, 0);
      boxes[0].checked = true; boxes[0].dispatchEvent(new Event('change'));
      var size = dialog.querySelector('.mesh-body-size');
      T.ok(!size.disabled);
      size.value = '0';
      realButton(dialog, 'Apply').click();
      T.ok(/greater than zero/.test(dialog.querySelector('.mesh-settings-message').textContent));
      T.eq(ctx.requests.length, 0);
      size.value = '1.25';
      dialog.querySelector('[name=algorithm_2d]').value = 'delaunay';
      realButton(dialog, 'Apply and generate').click();
      return drain().then(function () {
        T.eq(ctx.requests.length, 1);
        T.eq(ctx.requests[0].path, '/api/project');
        T.eq(ctx.requests[0].body.mesh.algorithm_3d, 'hxt', 'the hidden algorithm is preserved');
        T.eq(ctx.requests[0].body.mesh.algorithm_2d, 'delaunay');
        T.eq(ctx.requests[0].body.mesh.body_sizes.soil_L1, 1.25);
        T.eq(ctx.requests[0].body.mesh.volume_keys, undefined, 'selection is not a stored mesh setting');
        T.eq(App.MESH_BODY_SELECTION, ['soil_L1']);
        T.eq(ctx.actions, ['generateMesh']);
        T.eq(ctx.applied.length, 1);
        T.ok(!document.getElementById('mesh-settings-dialog'));
      });
    });
  });

  test('mesh dialog keeps failed saves editable and allows a retry without generation', function () {
    return withEnvironment(project(3), function (ctx) {
      ctx.failure = new Error('Mesh settings refused');
      App.MeshSettings.open();
      var dialog = document.getElementById('mesh-settings-dialog');
      realButton(dialog, 'Apply').click();
      return drain().then(function () {
        T.eq(dialog.querySelector('.mesh-settings-message').textContent, 'Mesh settings refused');
        T.ok(!realButton(dialog, 'Apply').disabled);
        T.ok(!realButton(dialog, 'Apply and generate').disabled);
        T.eq(ctx.applied.length, 0);
        ctx.failure = null;
        realButton(dialog, 'Apply').click();
        return drain();
      }).then(function () {
        T.eq(ctx.applied.length, 1);
        T.eq(ctx.actions, []);
        T.ok(!document.getElementById('mesh-settings-dialog'));
      });
    });
  });

  test('mesh dialog opens from the mode tab and closes with Cancel or Escape', function () {
    return withEnvironment(project(), function () {
      var tab = document.createElement('button');
      tab.className = 'mode-tab'; tab.dataset.mode = 'mesh';
      document.body.appendChild(tab);
      try {
        tab.click();
        var dialog = document.getElementById('mesh-settings-dialog');
        T.ok(dialog);
        realButton(dialog, 'Cancel').click();
        T.ok(!document.getElementById('mesh-settings-dialog'));
        App.MeshSettings.open();
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        T.ok(!document.getElementById('mesh-settings-dialog'));
      } finally { tab.remove(); }
    });
  });

  test('soil volume validation distinguishes malformed, flat and non-planar geometry', function () {
    var validate = App.SoilVolumeDialog.validate;
    var triangle = [[0, 0, 0], [4, 0, 0], [0, 3, 0]];
    T.eq(validate(triangle, [0, 0, 2]), null);
    T.ok(/three corners/.test(validate(triangle.slice(0, 2), [0, 0, 2])));
    T.ok(/Corner 2.*not a number/.test(validate([[0, 0, 0], [NaN, 0, 0], [0, 3, 0]], [0, 0, 2])));
    T.ok(/three numbers/.test(validate(triangle, [0, 0, NaN])));
    T.ok(/straight line/.test(validate([[0, 0, 0], [1, 0, 0], [2, 0, 0]], [0, 0, 2])));
    T.ok(/coplanar/.test(validate(triangle.concat([[1, 1, 1]]), [0, 0, 2])));
    T.ok(/no volume/.test(validate(triangle, [2, 0, 0])));
    T.near(App.SoilVolumeDialog.volumeOf(triangle, [0, 0, 2]), 12, 1e-9);
  });

  test('soil volume form edits corners and extrusion and saves the requested replacement', function () {
    return withEnvironment(project(3), function (ctx) {
      var part = { key: 'fill', label: 'Fill', mat: 'soil', recipe: {
        kind: 'polygon_extrude', vertices: [[0, 0, 0], [4, 0, 0], [0, 3, 0]], extrusion: [0, 0, 2]
      } };
      var saved = 0;
      App.SoilVolumeDialog.open(part, { insertBefore: 'soil_L2', onSaved: function () { saved += 1; } });
      var dialog = document.getElementById('soil-volume-dialog');
      T.ok(/volume 12.0/.test(dialog.querySelector('.soil-volume-summary').textContent));
      realButton(dialog, 'Add corner').click();
      T.eq(dialog.querySelectorAll('.soil-volume-row').length, 4);
      dialog.querySelector('.soil-volume-row:last-child button').click();
      T.eq(dialog.querySelectorAll('.soil-volume-row').length, 3);
      var coord = dialog.querySelector('.soil-volume-row:nth-child(2) input');
      change(coord, '6');
      var enter = new KeyboardEvent('keydown', { key: 'Enter', cancelable: true });
      coord.dispatchEvent(enter);
      T.ok(enter.defaultPrevented);
      var ext = dialog.querySelectorAll('.soil-volume-extrusion input');
      change(ext[2], '3');
      ext[2].dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', cancelable: true }));
      T.ok(/volume 27.0/.test(dialog.querySelector('.soil-volume-summary').textContent));
      realButton(dialog, 'Save').click();
      return drain().then(function () {
        T.eq(ctx.requests[0].path, '/api/geometry/create');
        T.eq(ctx.requests[0].body, { kind: 'polygon_extrude', label: 'Fill', material: 'soil',
          vertices: [[0, 0, 0], [6, 0, 0], [0, 3, 0]], extrusion: [0, 0, 3],
          replace: 'fill', insert_before: 'soil_L2' });
        T.eq([ctx.loaded, ctx.refreshed, saved], [1, 1, 1]);
        T.ok(!document.getElementById('soil-volume-dialog'));
      });
    });
  });

  test('soil volume form shows a failed save and can retry the same shape', function () {
    return withEnvironment(project(3), function (ctx) {
      ctx.failure = new Error('Geometry could not be built');
      App.SoilVolumeDialog.open();
      var dialog = document.getElementById('soil-volume-dialog');
      realButton(dialog, 'Create').click();
      return drain().then(function () {
        T.eq(dialog.querySelector('.mesh-settings-message').textContent, ctx.failure.message);
        T.ok(!realButton(dialog, 'Create').disabled);
        T.ok(!realButton(dialog, 'Cancel').disabled);
        T.eq(ctx.loaded, 0);
        ctx.failure = null;
        realButton(dialog, 'Create').click();
        return drain();
      }).then(function () {
        T.eq(ctx.requests.length, 2);
        T.eq(ctx.loaded, 1);
        T.ok(!document.getElementById('soil-volume-dialog'));
      });
    });
  });

  ['beam', 'panel', 'member'].forEach(function (kind) {
    test('structure editor saves edited coordinates and section properties for ' + kind, function () {
      return withEnvironment(project(kind === 'beam' ? 2 : 3), function (ctx) {
        App.Beams.start(kind);
        var dialog = latest(ctx);
        T.ok(/^Create /.test(dialog.options.title));
        field(dialog, 'Name').value = 'Edited structure';
        field(dialog, 'YOUNG_MODULUS').value = '200000000000';
        field(dialog, 'x1').value = '10';
        if (kind !== 'panel') field(dialog, 'Spacing').value = '2';
        button(dialog, 'Save');
        return drain().then(function () {
          T.ok(dialog.closed);
          var body = ctx.requests[0].body;
          T.eq(body.beams[0].name, 'Edited structure');
          T.eq((kind === 'panel' ? body.beams[0].footprint : body.beams[0].points)[0][0], 10);
          var library = kind === 'panel' ? body.panel_sections : body.beam_sections;
          T.eq(library[0].variables.YOUNG_MODULUS, 200000000000);
          if (kind !== 'panel') T.eq(library[0].spacing, 2);
          App.Beams.edit(body.beams[0].id);
          T.ok(/^Edit /.test(latest(ctx).options.title));
          if (kind === 'panel') {
            App.PANEL_SECTIONS = null;
            T.eq(App.Beams.sectionOf(body.beams[0]).id, library[0].id);
          }
        });
      });
    });
  });

  test('structure editor validates before saving and leaves a rejected save open', function () {
    return withEnvironment(project(), function (ctx) {
      App.Beams.start();
      var dialog = latest(ctx);
      field(dialog, 'Name').value = '';
      button(dialog, 'Save');
      T.ok(/Name cannot be empty/.test(dialog.form.textContent));
      T.eq(ctx.requests, []);
      field(dialog, 'Name').value = 'Pile';
      ctx.failure = new Error('Structure refused');
      button(dialog, 'Save');
      return drain().then(function () {
        T.ok(!dialog.closed);
        T.ok(/Structure refused/.test(dialog.form.textContent));
        T.eq(ctx.loaded, 1, 'a failed patch reloads the server model');
      });
    });
  });

  test('anchor start uses the tendon editor and edit saves the existing anchor', function () {
    var initial = project();
    initial.beams = [{ id: 'pile', kind: 'beam', points: [[12, 0], [12, -20]], active: true }];
    return withEnvironment(initial, function (ctx) {
      var proposed, tendons;
      App.Dialogs.anchor = function (anchor, sections) { proposed = anchor; tendons = sections; };
      App.Anchors.start();
      T.eq(proposed.head[0], 12);
      T.eq(ctx.requests, [], 'opening the editor must not save the draft');
      initial.anchors = [proposed]; initial.anchor_sections = tendons;
      App.ANCHORS = initial.anchors; App.ANCHOR_SECTIONS = tendons;
      return App.Anchors.edit(proposed.id).then(function () {
        T.eq(ctx.requests[0].body.anchors, [proposed]);
        T.eq(ctx.requests[0].body.anchor_sections, tendons);
        T.eq(ctx.requests[0].body.beams, undefined, 'an anchor edit does not replace the piles');
        T.eq(ctx.selected, [proposed.id]);
        T.eq(App.Anchors.edit('missing'), undefined);
      });
    });
  });

  test('load editor picks a new point and deletion preserves the other loads', function () {
    return withEnvironment(project(), function (ctx) {
      App.Loads.start('point');
      button(latest(ctx), 'Pick on model\u2026');
      T.eq(ctx.drawn.mode, 'load');
      T.eq(ctx.drawn.options.count, 1);
      T.ok(ctx.drawn.options.pointLoad);
      ctx.drawn.options.onComplete([[8, -3, 0]]);
      var dialog = latest(ctx);
      T.eq(field(dialog, 'x').value, '8');
      T.eq(field(dialog, 'y').value, '-3');
      button(dialog, 'Save');
      return drain().then(function () {
        T.ok(dialog.closed);
        var point = ctx.requests[0].body.loads[0];
        var other = Object.assign({}, point, { id: 'other', name: 'Other load' });
        App.PROJECT.loads.push(other);
        App.LOADS = App.PROJECT.loads;
        App.Loads.edit(point.id);
        T.eq(latest(ctx).options.title, 'Edit point load');
        App.state.selection = point.id;
        return App.Loads.remove(point.id);
      }).then(function (removed) {
        T.eq(removed, true);
        T.eq(ctx.requests[1].body.loads.map(function (load) { return load.id; }), ['other']);
        T.eq(App.state.selection, null);
        return App.Loads.remove('missing');
      }).then(function (removed) {
        T.eq(removed, false);
        T.eq(ctx.requests.length, 2);
      });
    });
  });

  test('normal-load picker converts section coordinates and reopens the editor', function () {
    return withEnvironment(project(), function (ctx) {
      App.NormalLoads.start();
      button(latest(ctx), 'Pick on model\u2026');
      T.eq(ctx.drawn.mode, 'load');
      T.eq(ctx.drawn.options.count, 2);
      ctx.drawn.options.onComplete([[5, -2, 0], [15, -4, 0]]);
      var dialog = latest(ctx);
      T.eq(field(dialog, 'x1').value, '5');
      T.eq(field(dialog, 'y2').value, '-4');
      field(dialog, 'Pressure').value = '120';
      return button(dialog, 'Save').then(function () {
        T.ok(dialog.closed);
        T.eq(ctx.requests[0].body.normal_loads[0].points, [[5, -2], [15, -4]]);
      });
    });
  });

  test('boundary editor saves supports, picks section lines and deletes only the selected condition', function () {
    return withEnvironment(project(), function (ctx) {
      App.BoundaryConditions.openRecord();
      var dialog = latest(ctx);
      field(dialog, 'Name').value = 'Bottom support';
      return button(dialog, 'Save').then(function () {
        T.ok(dialog.closed);
        var support = ctx.requests[0].body.boundary_conditions[0];
        App.BoundaryConditions.edit(support.id);
        dialog = latest(ctx);
        T.eq(dialog.options.title, 'Edit boundary condition');
        change(field(dialog, 'Where'), 'line');
        button(dialog, 'Pick on model\u2026');
        T.ok(dialog.closed);
        T.eq(ctx.drawn.mode, 'line');
        T.ok(ctx.drawn.options.atPointer);
        ctx.drawn.options.onComplete([[0, -3, 0], [0, -15, 0]]);
        dialog = latest(ctx);
        T.eq(field(dialog, 'Points').value, '0 -3, 0 -15');
        return button(dialog, 'Save');
      }).then(function () {
        T.eq(ctx.requests[1].body.boundary_conditions[0].points, [[0, -3], [0, -15]]);
        var id = App.PROJECT.boundary_conditions[0].id;
        App.state.selection = id;
        return App.BoundaryConditions.remove(id);
      }).then(function () {
        T.eq(ctx.requests[2].body.boundary_conditions, []);
        T.eq(App.state.selection, null);
        return App.BoundaryConditions.applyStandard();
      }).then(function () {
        T.ok(ctx.requests[3].body.boundary_conditions.length > 0);
      });
    });
  });

  test('boundary drawing opens a water condition at the picked point', function () {
    return withEnvironment(project(), function (ctx) {
      App.BoundaryConditions.draw('water_pressure', 'point');
      T.eq(ctx.drawn.mode, 'load');
      T.ok(ctx.drawn.options.atPointer);
      ctx.drawn.options.onComplete([[8, -4, 0]]);
      var dialog = latest(ctx);
      T.eq(field(dialog, 'Points').value, '8 -4');
      T.eq(field(dialog, 'Type').value, 'Uniform');
      return button(dialog, 'Save').then(function () {
        T.eq(ctx.requests[0].body.boundary_conditions[0].points, [[8, -4]]);
      });
    });
  });

  test('normal-load save refusal reloads the model and leaves the form open for retry', function () {
    return withEnvironment(project(), function (ctx) {
      App.NormalLoads.start();
      var dialog = latest(ctx);
      field(dialog, 'Pressure').value = '120';
      ctx.failure = new Error('Normal load refused');
      return button(dialog, 'Save').then(function () {
        T.eq(ctx.loaded, 1);
        T.eq(ctx.refreshed, 1);
        T.eq(dialog.closed, false);
        T.ok(/Normal load refused/.test(dialog.form.textContent));
        T.ok(ctx.logs.some(function (line) {
          return line[0] === 'err' && /Normal load refused/.test(line[1]);
        }));
        ctx.failure = null;
        return button(dialog, 'Save');
      }).then(function () {
        var saved = App.PROJECT.normal_loads[0];
        T.ok(dialog.closed);
        App.NormalLoads.edit(saved.id);
        T.eq(latest(ctx).options.title, 'Edit normal load');
        return App.NormalLoads.remove(saved.id);
      }).then(function () {
        T.eq(App.PROJECT.normal_loads, []);
      });
    });
  });

  test('boundary grid applies standard supports, clears them, and saves changed water and gravity', function () {
    return withEnvironment(project(), function (ctx) {
      App.BoundaryConditions.open();
      var dialog = latest(ctx);
      button(dialog, 'Standard conditions');
      var supports = dialog.form.querySelectorAll('.bc-support');
      T.ok(Array.prototype.some.call(supports, function (control) { return control.value === 'fixed'; }));
      button(dialog, 'Clear');
      supports.forEach(function (control) { T.eq(control.value, 'free'); });
      var water = dialog.form.querySelector('.bc-water');
      change(water, 'Uniform');
      var number = dialog.form.querySelector('.bc-number');
      T.eq(number.disabled, false);
      number.value = '-125';
      dialog.form.querySelector('.bc-gravity input').checked = false;
      ctx.failure = new Error('Boundary grid refused');
      return button(dialog, 'Save').then(function () {
        T.eq(dialog.closed, false);
        T.ok(/Boundary grid refused/.test(dialog.form.textContent));
        ctx.failure = null;
        return button(dialog, 'Save');
      }).then(function () {
        T.ok(dialog.closed);
        var sent = ctx.requests[1].body;
        T.eq(sent.gravity, false);
        T.ok(sent.boundary_conditions.some(function (record) { return record.value === -125; }));
        App.BoundaryConditions.open();
        dialog = latest(ctx);
        dialog.form.querySelector('.bc-grid button').click();
        T.ok(dialog.closed);
        T.eq(latest(ctx).options.title, 'Edit boundary condition');
        App.BoundaryConditions.open();
        dialog = latest(ctx);
        button(dialog, 'Add condition\u2026');
        T.ok(dialog.closed);
        T.eq(latest(ctx).options.title, 'Create boundary condition');
      });
    });
  });
})();
