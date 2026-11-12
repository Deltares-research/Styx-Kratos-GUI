/* Mesh properties: shown when the Mesh mode tab is clicked before there is a mesh,
   and from the toolbar's mesh-settings button at any time. */

var App = window.App || {};

App.MeshSettings = (function () {
  var defaults = {
    element_size: 2.5, order: 2, algorithm_3d: 'delaunay', algorithm_2d: 'frontal',
    optimization: 'gmsh', smoothing: 10, curvature_points: 16, size_min_factor: 0.05,
    second_order_linear: true, body_sizes: {}
  };

  var TITLE = 'Mesh properties';

  /* The values are what the server's mesher takes; only the labels are the user's.
     'gmsh' is the mesher's own optimizer, so it is shown as the standard one. */
  function optimizationChoices() {
    return [['none', 'None'], ['gmsh', 'Standard'], ['netgen', 'Netgen']];
  }

  function optimizationHelp(planar) {
    return planar
      ? 'Improves triangle quality after initial generation. Netgen is 3D-only and falls back to Standard.'
      : 'Improves tetrahedron quality after initial generation.';
  }

  /* The Mesh tab is also how you go back to look at a mesh, so once there is one the
     dialog stays shut: switching tabs must not put a regenerate button in front of it. */
  function opensOnModeTab(hasMesh) {
    return !hasMesh;
  }

  function fromProject(project) {
    return Object.assign({}, defaults, (project && project.mesh) || {});
  }

  /* gmsh reads Mesh.Algorithm in 2D and Mesh.Algorithm3D in 3D, so the dialog must
     offer whichever will actually be used -- the other one is not a worse choice,
     it is an ignored one. Both are kept on the project either way, so switching
     dimension does not discard the setting for the dimension you left. */
  var ALGORITHMS = {
    algorithm_3d: [['delaunay', 'Delaunay'], ['frontal', 'Frontal'], ['hxt', 'HXT parallel']],
    algorithm_2d: [['frontal', 'Frontal-Delaunay'], ['delaunay', 'Delaunay'],
                   ['meshadapt', 'MeshAdapt'], ['auto', 'Automatic']]
  };

  function algorithmRow(project) {
    var two = project && project.dimension === 2;
    var name = two ? 'algorithm_2d' : 'algorithm_3d';
    return {
      name: name,
      label: two ? '2D algorithm' : '3D algorithm',
      choices: ALGORITHMS[name],
      help: two
        ? 'Frontal-Delaunay favours triangle quality; MeshAdapt is the most forgiving on thin faces.'
        : 'Delaunay is robust; Frontal favors quality; HXT is faster on larger models.'
    };
  }

  /* The dialog shows one algorithm select, not two (see algorithmRow), so the key for
     the dimension you are not in is absent from the form. Laying the form over the
     stored settings is what preserves it -- reading the form alone leaves that key
     undefined and validate() then rejects a value the user was never shown. */
  function merge(project, formValue) {
    return Object.assign(fromProject(project), formValue);
  }

  function validate(value) {
    var out = Object.assign({}, value);
    out.element_size = Number(out.element_size);
    out.order = Number(out.order);
    out.smoothing = Number(out.smoothing);
    out.curvature_points = Number(out.curvature_points);
    out.size_min_factor = Number(out.size_min_factor);
    if (!(out.element_size > 0)) throw new Error('Element size must be greater than zero.');
    if ([1, 2].indexOf(out.order) < 0) throw new Error('Element order must be 1 or 2.');
    if (['delaunay', 'frontal', 'hxt'].indexOf(out.algorithm_3d) < 0) throw new Error('Unknown 3D algorithm.');
    if (['meshadapt', 'auto', 'delaunay', 'frontal'].indexOf(out.algorithm_2d) < 0)
      throw new Error('Unknown 2D algorithm.');
    if (['none', 'gmsh', 'netgen'].indexOf(out.optimization) < 0) throw new Error('Unknown optimizer.');
    if (!Number.isInteger(out.smoothing) || out.smoothing < 0 || out.smoothing > 100)
      throw new Error('Smoothing must be an integer from 0 to 100.');
    if (!Number.isInteger(out.curvature_points) || out.curvature_points < 0 || out.curvature_points > 100)
      throw new Error('Curvature points must be an integer from 0 to 100.');
    if (!(out.size_min_factor > 0 && out.size_min_factor <= 1))
      throw new Error('Minimum-size factor must be greater than 0 and at most 1.');
    out.second_order_linear = !!out.second_order_linear;
    return out;
  }

  /* Every body that can be meshed: the layer stack, plus any custom part that
     has been given a material (those are soil too). A layer or a soil surface that a
     line cut is its pieces, one row each, as in the Model explorer: the project
     publishes their keys and names (`soil_body_keys`, `soil_body_labels`), so the split
     is not worked out a second time here. `owner` is the key of the layer or surface. */
  function meshBodies(project) {
    var published = (project && project.soil_body_keys) || [];
    var labels = (project && project.soil_body_labels) || {};
    function pieces(owner, name) {
      var mine = published.filter(function (key) { return key.split('__')[0] === owner; });
      if (!mine.length) mine = [owner];
      return mine.map(function (key) {
        return { key: key, owner: owner, label: labels[key] || name };
      });
    }
    var bodies = [];
    ((project && project.layers) || []).forEach(function (layer) {
      bodies = bodies.concat(pieces('soil_' + layer.id, layer.name || layer.id));
    });
    ((project && project.custom_parts) || []).forEach(function (part) {
      if (part.mat) bodies = bodies.concat(pieces(part.key, part.label));
    });
    return bodies;
  }

  function meshTargets(project, selection, isVisible) {
    var keys = meshBodies(project).map(function (b) { return b.key; });
    if (keys.indexOf(selection) >= 0) return [selection];
    return keys.filter(function (key) { return isVisible(key); });
  }

  function bodyControls(project, selectedKeys) {
    var mesh = (project && project.mesh) || {};
    var fallback = Number(mesh.element_size || defaults.element_size);
    var sizes = mesh.body_sizes || {};
    function has(key) { return Object.prototype.hasOwnProperty.call(sizes, key); }
    return meshBodies(project).map(function (body) {
      // A size set on the whole layer or surface, before a line cut it, is each piece's.
      var from = has(body.key) ? body.key : has(body.owner) ? body.owner : null;
      return {
        key: body.key,
        owner: body.owner,
        label: body.label,
        enabled: selectedKeys.indexOf(body.key) >= 0,
        size: from ? Number(sizes[from]) : fallback,
        follows: !from
      };
    });
  }

  /* The sizes the window saves. It has rows for the layers only, so a size it has no row
     for -- a structure's, a lift's, set in `kratos-cli` or a script -- stays as it is. A
     row that `follows` the global size has had no size typed, and asks for none.
     A size on a whole layer or surface that a line cut shows on each of its pieces'
     rows. While every one of those rows still shows it, it stays as it is. Once one
     shows another size, each piece's row saves its own size and the whole one goes:
     two sizes for one body would leave the mesher to choose. */
  function savedBodySizes(project, rows) {
    var sizes = Object.assign({}, ((project && project.mesh) || {}).body_sizes);
    function has(key) { return Object.prototype.hasOwnProperty.call(sizes, key); }
    var whole = {};
    rows.forEach(function (row) {
      if (row.owner && row.owner !== row.key && has(row.owner)) {
        var same = row.size === Number(sizes[row.owner]) && !has(row.key);
        whole[row.owner] = (whole[row.owner] !== false) && same;
      }
    });
    Object.keys(whole).forEach(function (owner) { if (!whole[owner]) delete sizes[owner]; });
    rows = rows.filter(function (row) { return !whole[row.owner] || row.owner === row.key; });
    rows.forEach(function (row) {
      if (!(row.size > 0)) delete sizes[row.key];
      else if (!row.follows) sizes[row.key] = row.size;
    });
    return sizes;
  }

  /* The bodies of `project` that this window's check boxes leave out. */
  function leftOutBodies(project, selectedKeys) {
    return meshBodies(project).map(function (body) { return body.key; })
      .filter(function (key) { return selectedKeys.indexOf(key) < 0; });
  }

  /* The bodies to mesh after a choice in this window, or null when it made none or left
     nothing. It is kept as what was left out (`App.MESH_BODIES_LEFT_OUT`) because the
     model changes under it: a body added later is meshed, as `kratos-cli` meshes it, and
     a deleted body is not asked for, which the server would refuse. A layer left out
     before a line cut it leaves out each of its pieces. */
  function chosenBodies(project, leftOut) {
    if (!Array.isArray(leftOut)) return null;
    var kept = meshBodies(project)
      .filter(function (body) {
        return leftOut.indexOf(body.key) < 0 && leftOut.indexOf(body.owner) < 0;
      })
      .map(function (body) { return body.key; });
    return kept.length ? kept : null;
  }

  function open() {
    if (!App.PROJECT || document.getElementById('mesh-settings-dialog')) return;
    var el = App.UI.el, settings = fromProject(App.PROJECT);
    var layer = document.getElementById('modal-layer');
    var scrim = el('div.scrim');
    var dialog = el('div.dialog.mesh-settings-dialog', { id: 'mesh-settings-dialog' });
    dialog.style.width = '720px'; dialog.style.height = '570px';
    dialog.style.left = Math.max(20, (window.innerWidth - 720) / 2) + 'px';
    dialog.style.top = Math.max(20, (window.innerHeight - 570) / 2) + 'px';

    var closeButton = el('button.dlg-x', { text: '✕', type: 'button' });
    var head = el('div.dlg-head', null, [el('span.dlg-title', { text: TITLE }), closeButton]);
    dialog.appendChild(head);
    App.Dialogs.draggable(head, dialog);
    var body = el('div.dlg-body.mesh-settings-body');
    var form = el('div.mesh-settings-form');
    body.appendChild(form); dialog.appendChild(body);

    function row(label, control, help) {
      form.appendChild(el('label.mesh-setting-label', { text: label }));
      form.appendChild(control);
      form.appendChild(el('div.mesh-setting-help', { text: help }));
      return control;
    }
    function input(name, type, attrs) {
      var node = el('input.mesh-setting-control', Object.assign({ name: name, type: type }, attrs || {}));
      if (type === 'checkbox') node.checked = !!settings[name]; else node.value = settings[name];
      return node;
    }
    function select(name, choices) {
      var node = el('select.mesh-setting-control', { name: name });
      choices.forEach(function (choice) { node.appendChild(el('option', { value: choice[0], text: choice[1] })); });
      node.value = settings[name]; return node;
    }

    var targets = chosenBodies(App.PROJECT, App.MESH_BODIES_LEFT_OUT)
      || meshTargets(App.PROJECT, App.state.selection, App.Viewport.isVisible);
    var bodyTable = el('div.mesh-body-table');
    // The checkbox column carries no caption: "Mesh" does not fit a 16px box, and
    // the help text beside the table already explains what ticking one does.
    bodyTable.appendChild(el('div.mesh-body-head', null, [
      el('span'), el('span', { text: 'Layer' }), el('span', { text: 'Target size' })
    ]));
    bodyControls(App.PROJECT, targets).forEach(function (bodyRow) {
      var enabled = el('input.mesh-body-enabled', {
        type: 'checkbox', checked: bodyRow.enabled, 'data-body-key': bodyRow.key
      });
      enabled.checked = bodyRow.enabled;
      var size = el('input.mesh-setting-control.mesh-body-size', {
        type: 'number', min: '0.01', step: '0.1', value: bodyRow.size,
        'data-body-size-key': bodyRow.key, 'data-body-owner': bodyRow.owner
      });
      size.value = bodyRow.size;
      if (bodyRow.follows) size.setAttribute('data-follows-global', '');
      size.addEventListener('input', function () { size.removeAttribute('data-follows-global'); });

      /* The target size only applies to a layer that is being meshed, so follow
         the checkbox: greyed out when unchecked, and skipped by read(). */
      var bodyRowNode = el('label.mesh-body-row', null, [
        enabled, el('span', { text: bodyRow.label, title: bodyRow.label }), size
      ]);
      function syncEnabled() {
        size.disabled = !enabled.checked;
        bodyRowNode.classList.toggle('off', !enabled.checked);
      }
      enabled.addEventListener('change', syncEnabled);
      syncEnabled();
      bodyTable.appendChild(bodyRowNode);
    });
    row('Layer mesh sizes', bodyTable,
        'Check every layer to mesh. A layer or soil surface that a line splits has a row for each part. Each checked row can use an independent target size; shared faces remain conformal.');

    var globalSize = row('Global element size', input('element_size', 'number', { min: '0.01', step: '0.1' }),
        'Maximum target edge length in model units. Smaller values create more tetrahedra.');
    globalSize.addEventListener('input', function () {
      if (!(Number(globalSize.value) > 0)) return;
      form.querySelectorAll('.mesh-body-size[data-follows-global]').forEach(function (control) {
        control.value = globalSize.value;
      });
    });
    var planar = App.PROJECT && App.PROJECT.dimension === 2;
    row('Element order', select('order', planar
          ? [[1, 'Linear · 3-node triangle'], [2, 'Quadratic · 6-node triangle']]
          : [[1, 'Linear · 4-node tetrahedron'], [2, 'Quadratic · 10-node tetrahedron']]),
        'Quadratic elements add midside nodes after the mesh is generated.');
    var algorithm = algorithmRow(App.PROJECT);
    row(algorithm.label, select(algorithm.name, algorithm.choices), algorithm.help);
    row('Optimization', select('optimization', optimizationChoices()), optimizationHelp(planar));
    row('Smoothing steps', input('smoothing', 'number', { min: '0', max: '100', step: '1' }),
        'Surface-mesh smoothing iterations. Ten is a balanced default.');
    row('Curvature points', input('curvature_points', 'number', { min: '0', max: '100', step: '1' }),
        'Minimum sampling around curved features; zero disables curvature sizing.');
    row('Minimum-size factor', input('size_min_factor', 'number', { min: '0.001', max: '1', step: '0.01' }),
        'Smallest permitted size as a fraction of the global size.');
    row('Straight quadratic edges', input('second_order_linear', 'checkbox'),
        'Keeps quadratic midside nodes linear, preventing inversion on fragmented CAD faces.');

    var message = el('span.mesh-settings-message');
    var apply = el('button.btn', { text: 'Apply', type: 'button' });
    var generate = el('button.btn.btn-primary', { text: 'Apply and generate', type: 'button' });
    var cancel = el('button.btn', { text: 'Cancel', type: 'button' });
    dialog.appendChild(el('div.dlg-foot', null, [message, el('span.spacer'), apply, generate, cancel]));
    layer.appendChild(scrim); layer.appendChild(dialog);

    function close() { if (scrim.parentNode) scrim.remove(); if (dialog.parentNode) dialog.remove(); document.removeEventListener('keydown', escape); }
    function escape(event) { if (event.key === 'Escape') close(); }
    function read() {
      var value = {};
      form.querySelectorAll('[name]').forEach(function (control) {
        value[control.name] = control.type === 'checkbox' ? control.checked : control.value;
      });
      var selectedKeys = [], rows = [];
      form.querySelectorAll('.mesh-body-enabled').forEach(function (control) {
        var key = control.getAttribute('data-body-key');
        if (control.checked) selectedKeys.push(key);
      });
      if (!selectedKeys.length) throw new Error('Select at least one layer to mesh.');
      form.querySelectorAll('.mesh-body-size').forEach(function (control) {
        var key = control.getAttribute('data-body-size-key');
        var size = Number(control.value);
        var meshed = selectedKeys.indexOf(key) >= 0;
        if (meshed && !(size > 0)) {
          throw new Error('Mesh size for ' + key + ' must be greater than zero.');
        }
        // Keep a size typed for a layer that is currently unchecked, so ticking it
        // again does not silently fall back to the global size.
        rows.push({ key: key, owner: control.getAttribute('data-body-owner'), size: size,
                    follows: control.hasAttribute('data-follows-global') });
      });
      value.body_sizes = savedBodySizes(App.PROJECT, rows);
      value.volume_keys = selectedKeys;
      return validate(merge(App.PROJECT, value));
    }
    function save(andGenerate) {
      try { settings = read(); message.textContent = ''; }
      catch (error) { message.textContent = error.message; return; }
      apply.disabled = generate.disabled = true;
      var selectedKeys = settings.volume_keys.slice();
      var savedSettings = Object.assign({}, settings); delete savedSettings.volume_keys;
      var project = JSON.parse(JSON.stringify(App.PROJECT)); project.mesh = savedSettings;
      App.Api.put('/api/project', project).then(function (saved) {
        App.MESH_BODIES_LEFT_OUT = leftOutBodies(App.PROJECT, selectedKeys);
        App.Model.apply(saved); close();
        App.Command.ok('Mesh properties updated.');
        if (andGenerate) App.runAction({ action: 'generateMesh' });
      }).catch(function (error) {
        apply.disabled = generate.disabled = false; message.textContent = error.message;
      });
    }
    apply.addEventListener('click', function () { save(false); });
    generate.addEventListener('click', function () { save(true); });
    cancel.addEventListener('click', close); closeButton.addEventListener('click', close);
    document.addEventListener('keydown', escape);
  }

  if (typeof document !== 'undefined') {
    document.addEventListener('click', function (event) {
      if (!(event.target.closest && event.target.closest('.mode-tab[data-mode="mesh"]'))) return;
      var hasMesh = !!(App.Viewport && App.Viewport.hasMesh && App.Viewport.hasMesh());
      if (opensOnModeTab(hasMesh)) open();
    });
  }
  return {
    fromProject: fromProject, validate: validate, meshTargets: meshTargets,
    bodyControls: bodyControls, savedBodySizes: savedBodySizes, leftOutBodies: leftOutBodies,
    chosenBodies: chosenBodies, algorithmRow: algorithmRow, merge: merge, open: open,
    TITLE: TITLE, optimizationChoices: optimizationChoices, optimizationHelp: optimizationHelp,
    opensOnModeTab: opensOnModeTab
  };
})();
