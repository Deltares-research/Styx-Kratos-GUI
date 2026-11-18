/* Mesh properties: shown when the Mesh mode tab is clicked before there is a mesh,
   and from the toolbar's mesh-settings button at any time. */

var App = window.App || {};

App.MeshSettings = (function () {
  var defaults = {
    element_size: 2.5, order: 2, algorithm_3d: 'delaunay', algorithm_2d: 'frontal',
    optimization: 'gmsh', smoothing: 10, curvature_points: 16, size_min_factor: 0.05,
    second_order_linear: true, body_sizes: {}, size_bands: {}
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

  /* Every body that is meshed: the layer stack, plus any custom part that has been
     given a material (those are soil too). The whole model is always meshed, as
     `kratos-cli mesh` meshes it: a part that should have no mesh is removed. A layer or
     a soil surface that a line cut is its pieces, one row each, as in the Model
     explorer: the project publishes their keys and names (`soil_body_keys`,
     `soil_body_labels`), so the split is not worked out a second time here. `owner` is
     the key of the layer or surface. */
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

  function bodyControls(project) {
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
        size: from ? Number(sizes[from]) : fallback,
        follows: !from
      };
    });
  }

  /* The sizes the layer rows save. A size they have no row for -- a lift's, set in
     `kratos-cli` or a script -- stays as it is. A row that `follows` the global size
     has had no size typed, and asks for none, unless a band was typed on it: a band
     grows a size back out, so the size shown becomes the layer's own.
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
      else if (!row.follows || row.band > 0) sizes[row.key] = row.size;
    });
    return sizes;
  }

  /* ── Local mesh sizes ──────────────────────────────────────────────────
     The size at one object and the band over which it grows back to the global
     size (`body_sizes` and `size_bands`, core/geometry/meshing.py). */

  function owns(map, key) {
    return !!map && Object.prototype.hasOwnProperty.call(map, key);
  }

  function localSize(project, key) {
    var mesh = (project && project.mesh) || {};
    return { size: owns(mesh.body_sizes, key) ? Number(mesh.body_sizes[key]) : null,
             band: owns(mesh.size_bands, key) ? Number(mesh.size_bands[key]) : null };
  }

  /* `mesh` with `key` at `size` and `band`. A null size takes the size and its band
     away; a null or zero band takes the band only. */
  function withLocalSize(mesh, key, size, band) {
    var sizes = Object.assign({}, (mesh && mesh.body_sizes) || {});
    var bands = Object.assign({}, (mesh && mesh.size_bands) || {});
    if (size === null) {
      delete sizes[key]; delete bands[key];
    } else {
      sizes[key] = size;
      if (band > 0) bands[key] = band; else delete bands[key];
    }
    return Object.assign({}, mesh, { body_sizes: sizes, size_bands: bands });
  }

  /* Why a size and a band cannot be saved together, or null. */
  function localProblem(size, band) {
    if (size !== null && !(size > 0)) return 'The mesh size must be greater than zero.';
    if (band !== null && !(band >= 0)) return 'The band cannot be negative.';
    if (size === null && band > 0) return 'Give a mesh size before a band.';
    return null;
  }

  /* The faces of the model, as `Project.listed_mesh_size_keys` lists them: a 2D
     section has no front and back. */
  var FACES = ['bottom', 'left', 'right', 'front', 'back', 'top'];
  var SECTION_FACES = ['bottom', 'left', 'right', 'top'];
  function modelFaces(project) {
    return project && project.dimension === 2 ? SECTION_FACES : FACES;
  }

  /* The key a size on the face `face` is kept under (`schemas.face_size_key`). One per
     face, whatever conditions are on it: the deck writes one node part per face. */
  function faceKey(face) { return 'face_' + face; }

  /* "Bottom face  ·  Fixed bottom": the face, and the conditions on it. */
  function faceLabel(project, face) {
    var on = ((project && project.boundary_conditions) || []).filter(function (c) {
      return c.on === 'face' && c.face === face;
    }).map(function (c) { return c.name || c.id; });
    var name = face.charAt(0).toUpperCase() + face.slice(1) + ' face';
    return on.length ? name + '  ·  ' + on.join(', ') : name;
  }

  /* The loads this dimension builds (`Project.loads_for`), as the Model explorer lists
     them. */
  function builtLoads(project) {
    if (App.Model && App.Model.loadsFor) return App.Model.loadsFor(project || {});
    return (project && project.loads) || [];
  }

  /* Everything but the soil that a size can be given to, as
     `Project.listed_mesh_size_keys` lists it: the structures, the anchors (sized at
     their head), the interfaces, the normal loads, the soil lines, the conditions on a
     line or at a point, the loads, and the faces of the model. Together with the soil
     these are every node part the deck writes. A condition on a face is on that face's
     part, and takes its size (`sizeKeyOf`). */
  function localObjects(project) {
    var p = project || {};
    var out = [];
    function add(records, kind) {
      (records || []).forEach(function (record) {
        out.push({ key: record.id, label: record.name || record.id, kind: kind });
      });
    }
    add(p.beams, 'structure');
    add(p.anchors, 'anchor');
    add(p.interfaces, 'interface');
    add(p.normal_loads, 'normal load');
    add(p.lines, 'line');
    add((p.boundary_conditions || []).filter(function (c) {
      return c.on === 'line' || c.on === 'point';
    }), 'condition');
    add(builtLoads(p), 'load');
    modelFaces(p).forEach(function (face) {
      out.push({ key: faceKey(face), label: faceLabel(p, face), kind: 'face' });
    });
    return out;
  }

  /* The key whose size the object `id` has, or null for one that takes the global size
     (`Project.mesh_size_key_of`). A condition on a face has the face's, one on a soil
     part the part's, and one on the whole soil none: the whole soil is meshed at the
     global element size. Anything else has its own. */
  function sizeKeyOf(project, id) {
    var condition = ((project && project.boundary_conditions) || []).filter(function (c) {
      return c.id === id;
    })[0];
    if (!condition) return id;
    if (condition.on === 'face' && condition.face) return faceKey(condition.face);
    if (condition.on === 'part') return condition.part || null;
    if (condition.on === 'domain') return null;
    return id;
  }

  /* Every key a size can name: the layers and soil surfaces, their bodies, and
     `localObjects`. */
  function sizableKeys(project) {
    var keys = [];
    function add(key) { if (keys.indexOf(key) < 0) keys.push(key); }
    meshBodies(project).forEach(function (body) { add(body.owner); add(body.key); });
    ((project && project.soil_body_keys) || []).forEach(add);
    return keys.concat(localObjects(project).map(function (o) { return o.key; }));
  }

  /* One row per line and point object, with its own size and band or null. */
  function localControls(project) {
    return localObjects(project).map(function (object) {
      var now = localSize(project, object.key);
      return { key: object.key, label: object.label, kind: object.kind,
               size: now.size, band: now.band };
    });
  }

  /* `mesh` with the rows' sizes and bands: a size where one was typed, none where the
     row was left empty. */
  function savedLocalSizes(mesh, rows) {
    var out = mesh;
    rows.forEach(function (row) { out = withLocalSize(out, row.key, row.size, row.band); });
    return out;
  }

  function reportError(error) {
    if (App.Command && App.Command.err) App.Command.err(error.message);
  }

  /* What the user calls the object `key`. */
  function nameOf(project, key) {
    var found = meshBodies(project).concat(localObjects(project)).filter(function (o) {
      return o.key === key;
    })[0];
    var labels = (project && project.soil_body_labels) || {};
    return found ? found.label : (labels[key] || key);
  }

  /* Save one object's size and band, as the Mesh properties window saves its own. */
  function saveLocalSize(key, size, band) {
    var problem = localProblem(size, band);
    if (problem) return Promise.reject(new Error(problem));
    var project = JSON.parse(JSON.stringify(App.PROJECT));
    project.mesh = withLocalSize(fromProject(project), key, size, band);
    var name = nameOf(App.PROJECT, key);
    return App.Api.put('/api/project', project).then(function (saved) {
      App.Model.apply(saved);
      // Drawn again, or its Mesh size row keeps the old size until the next click. A
      // condition on a face shows the face's size, so it is drawn again too.
      var selected = App.state && App.state.selection;
      if (App.selectObject && selected && sizeKeyOf(App.PROJECT, selected) === key) {
        App.selectObject(selected, 'tree');
      }
      if (App.Command && App.Command.ok) {
        App.Command.ok(size === null ? name + ' takes the global mesh size again.'
                       : 'Mesh size of ' + name + ': ' + size + ' m'
                         + (band > 0 ? ', growing back over ' + band + ' m.' : '.'));
      }
      return saved;
    });
  }

  /* The Selection explorer's Mesh group for `key`. The explorer calls
     App.commitSelectionEdit after an edit, which sends what is kept in
     App.PENDING_MESH_SIZE (js/patches.js). With no size of its own the object reads
     "global"; writing that back, or the band it shows, changes nothing. `id` is the
     selected object when its size is another's: a condition on a face shows the
     face's size, and says so. */
  var GLOBAL = 'global';
  function selectionRows(key, id) {
    var now = localSize(App.PROJECT, key);
    function keep(size, band) {
      if ((size !== null && !Number.isFinite(size)) || (band !== null && !Number.isFinite(band))) {
        return 'The mesh size and the band must be numbers.';
      }
      if (size === now.size && (band || 0) === (now.band || 0)) return null;
      var problem = localProblem(size, band);
      if (problem) return problem;
      App.PENDING_MESH_SIZE = { key: key, size: size, band: band };
      return null;
    }
    var rows = [
      ['Mesh size', now.size === null ? GLOBAL : String(now.size), 'm', false, {
        // Three, as Refine rounds: two would show a halved 0.25 m as 0.13.
        kind: 'number', decimals: 3,
        get: function () { return now.size === null ? GLOBAL : now.size; },
        set: function (size) { return keep(size === GLOBAL ? now.size : size, now.band); } }],
      ['Band', String(now.band || 0), 'm', false, {
        kind: 'number', decimals: 2,
        get: function () { return now.band || 0; },
        set: function (band) { return keep(now.size, band); } }]
    ];
    if (id !== undefined && id !== key) {
      rows.unshift(['Size of', nameOf(App.PROJECT, key), '', true]);
    }
    if (now.size !== null) {
      rows.push(['Size', '', '', false, { kind: 'button', text: 'Use the global size',
        run: function () {
          return App.MeshSettings.saveLocalSize(key, null, null).catch(reportError);
        } }]);
    }
    return rows;
  }

  /* The size an object is meshed at now: its own, its layer's, or the global size. */
  function sizeNow(project, key) {
    var own = localSize(project, key).size;
    if (own !== null) return own;
    var layer = localSize(project, String(key).split('__')[0]).size;
    if (layer !== null) return layer;
    return Number(fromProject(project).element_size);
  }

  /* Refine mesh (factor 0.5), Coarsen mesh (2) and Reset local refinement (null) on the
     selected object. On the Mesh tab with a mesh on screen the mesh is made again, so
     the user sees what the tool did; the object stays selected for the next press. */
  function changeSelected(factor) {
    var selected = App.state && App.state.selection;
    var key = selected ? sizeKeyOf(App.PROJECT, selected) : null;
    if (!key || sizableKeys(App.PROJECT).indexOf(key) < 0) {
      if (App.Command && App.Command.note) {
        var whole = selected && key === null
          ? ((App.PROJECT && App.PROJECT.boundary_conditions) || []).filter(function (c) {
            return c.id === selected;
          })[0] : null;
        App.Command.note(whole
          ? (whole.name || whole.id) + ' acts on the whole soil, which is meshed at the '
            + 'global element size. Change it in Mesh properties.'
          : 'Select a layer, a soil body, a structure, a load, a condition or a line first.');
      }
      return Promise.resolve(null);
    }
    var band = localSize(App.PROJECT, key).band;
    var size = factor === null ? null
      : Math.round(sizeNow(App.PROJECT, key) * factor * 1000) / 1000;
    return saveLocalSize(key, size, size === null ? null : band).then(function (saved) {
      if (App.state.mode === 'mesh' && App.Viewport && App.Viewport.hasMesh
          && App.Viewport.hasMesh()) {
        App.runAction({ action: 'generateMesh', keepSelection: true });
      }
      return saved;
    }).catch(reportError);
  }

  function open() {
    if (!App.PROJECT || document.getElementById('mesh-settings-dialog')) return;
    var el = App.UI.el, settings = fromProject(App.PROJECT);
    var layer = document.getElementById('modal-layer');
    var scrim = el('div.scrim');
    var dialog = el('div.dialog.mesh-settings-dialog', { id: 'mesh-settings-dialog' });
    dialog.style.width = '780px'; dialog.style.height = '570px';
    dialog.style.left = Math.max(20, (window.innerWidth - 780) / 2) + 'px';
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

    var bodyTable = el('div.mesh-body-table');
    bodyTable.appendChild(el('div.mesh-body-head', null, [
      el('span', { text: 'Layer' }), el('span', { text: 'Target size' }),
      el('span', { text: 'Band' })
    ]));
    bodyControls(App.PROJECT).forEach(function (bodyRow) {
      var size = el('input.mesh-setting-control.mesh-body-size', {
        type: 'number', min: '0.01', step: '0.1', value: bodyRow.size,
        'data-body-size-key': bodyRow.key, 'data-body-owner': bodyRow.owner
      });
      size.value = bodyRow.size;
      if (bodyRow.follows) size.setAttribute('data-follows-global', '');
      size.addEventListener('input', function () { size.removeAttribute('data-follows-global'); });
      var band = el('input.mesh-setting-control.mesh-body-band', {
        type: 'number', min: '0', step: '1', placeholder: 'none',
        'data-body-band-key': bodyRow.key
      });
      var bandNow = localSize(App.PROJECT, bodyRow.key).band;
      band.value = bandNow === null ? '' : bandNow;
      bodyTable.appendChild(el('label.mesh-body-row', null, [
        el('span', { text: bodyRow.label, title: bodyRow.label }), size, band
      ]));
    });
    row('Layer mesh sizes', bodyTable,
        'Every layer is meshed, and shared faces keep common nodes. A layer or soil surface that a line splits has a row for each part. Each layer can have its own target size. Band: the distance outside the layer over which its size grows back to the global size [m]. To leave a part out of the mesh, remove it from the model.');

    var locals = localControls(App.PROJECT);
    if (locals.length) {
      var localTable = el('div.mesh-body-table');
      localTable.appendChild(el('div.mesh-body-head', null, [
        el('span', { text: 'Object' }), el('span', { text: 'Size' }),
        el('span', { text: 'Band' })
      ]));
      locals.forEach(function (localRow) {
        var size = el('input.mesh-setting-control.mesh-structure-size', {
          type: 'number', min: '0.01', step: '0.1', placeholder: 'global',
          'data-structure-key': localRow.key
        });
        size.value = localRow.size === null ? '' : localRow.size;
        var band = el('input.mesh-setting-control.mesh-structure-band', {
          type: 'number', min: '0', step: '1', placeholder: 'none',
          'data-structure-key': localRow.key
        });
        band.value = localRow.band === null ? '' : localRow.band;
        localTable.appendChild(el('label.mesh-body-row', {
          title: localRow.kind
        }, [el('span', { text: localRow.label }), size, band]));
      });
      row('Object mesh sizes', localTable,
          'The element size at each structure, anchor (at its head), interface, normal load, soil line, load, condition on a line or at a point, and face of the model, and the band over which it grows back to the global size [m]. A condition on a face takes the size of the face. Empty: it takes the size of the mesh around it. Also in the Selection explorer of each object.');
    }

    var globalSize = row('Global element size', input('element_size', 'number', { min: '0.01', step: '0.1' }),
        'The largest edge length of an element [m]. A smaller value makes more, smaller elements.');
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
      var rows = [];
      form.querySelectorAll('.mesh-body-size').forEach(function (control) {
        var key = control.getAttribute('data-body-size-key');
        var size = Number(control.value);
        if (!(size > 0)) {
          throw new Error('Mesh size for ' + key + ' must be greater than zero.');
        }
        var bandControl = form.querySelector('.mesh-body-band[data-body-band-key="' + key + '"]');
        var band = typedNumber(bandControl, key);
        if (band !== null && !(band >= 0)) throw new Error('The band of ' + key + ' cannot be negative.');
        rows.push({ key: key, owner: control.getAttribute('data-body-owner'), size: size,
                    band: band,
                    follows: control.hasAttribute('data-follows-global') });
      });
      var sizes = savedBodySizes(App.PROJECT, rows);
      var bands = Object.assign({}, fromProject(App.PROJECT).size_bands);
      rows.forEach(function (row) {
        if (row.band > 0 && owns(sizes, row.key)) bands[row.key] = row.band;
        else delete bands[row.key];
      });
      var localRows = [];
      form.querySelectorAll('.mesh-structure-size').forEach(function (control) {
        var key = control.getAttribute('data-structure-key');
        var size = typedNumber(control, key);
        var band = typedNumber(form.querySelector(
          '.mesh-structure-band[data-structure-key="' + key + '"]'), key);
        var problem = localProblem(size, band);
        if (problem) throw new Error(key + ': ' + problem);
        localRows.push({ key: key, size: size, band: band });
      });
      var local = savedLocalSizes({ body_sizes: sizes, size_bands: bands }, localRows);
      value.body_sizes = local.body_sizes;
      value.size_bands = local.size_bands;
      return validate(merge(App.PROJECT, value));
    }
    function typedNumber(control, key) {
      var typed = control ? control.value.trim() : '';
      if (typed === '') return null;
      var number = Number(typed);
      if (!Number.isFinite(number)) throw new Error(key + ': "' + typed + '" is not a number.');
      return number;
    }
    function save(andGenerate) {
      try { settings = read(); message.textContent = ''; }
      catch (error) { message.textContent = error.message; return; }
      apply.disabled = generate.disabled = true;
      var project = JSON.parse(JSON.stringify(App.PROJECT)); project.mesh = settings;
      App.Api.put('/api/project', project).then(function (saved) {
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
    fromProject: fromProject, validate: validate, meshBodies: meshBodies,
    bodyControls: bodyControls, savedBodySizes: savedBodySizes,
    localSize: localSize, withLocalSize: withLocalSize, localProblem: localProblem,
    localObjects: localObjects, localControls: localControls, savedLocalSizes: savedLocalSizes,
    sizableKeys: sizableKeys, sizeKeyOf: sizeKeyOf, faceKey: faceKey,
    saveLocalSize: saveLocalSize, selectionRows: selectionRows,
    sizeNow: sizeNow, changeSelected: changeSelected,
    algorithmRow: algorithmRow, merge: merge, open: open,
    TITLE: TITLE, optimizationChoices: optimizationChoices, optimizationHelp: optimizationHelp,
    opensOnModeTab: opensOnModeTab
  };
})();
