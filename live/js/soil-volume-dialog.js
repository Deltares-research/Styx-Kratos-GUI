/* Create a custom soil volume from typed coordinates.

   The shape is a planar polygon plus an extrusion vector, which is the
   `polygon_extrude` recipe app/creator.py already runs. One form covers both
   ways of describing a body:

     * an embankment or cutting — the cross-section drawn in a vertical plane
       (x and z vary, y constant), extruded along the alignment;
     * a fill pad or lens — the plan footprint (x and y vary, z constant),
       extruded downward or upward.

   Giving it a material is what makes it soil rather than display geometry: it
   then takes that material's colour and is meshed as a soil body. */

var App = window.App || {};

App.SoilVolumeDialog = (function () {

  /* An embankment, as a worked example: a trapezoid in the x-y plane extruded
     30 m along y. Base 12 m, crest 6 m, height 3 m, 1:1 side slopes. */
  var EXAMPLE = {
    label: 'Embankment',
    vertices: [[0, 0, 0], [3, 0, 3], [9, 0, 3], [12, 0, 0]],
    extrusion: [0, 30, 0]
  };

  function num(value) {
    return Number(String(value).trim().replace(',', '.'));
  }

  /* The polygon has to be planar for gmsh to build a plane surface from it, and
     the extrusion has to leave that plane, or there is no volume. Both are
     checked here so the failure names the problem instead of surfacing as a
     gmsh error from the worker. */
  function planeNormal(vertices) {
    var a = vertices[0], b = vertices[1];
    var u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
    for (var i = 2; i < vertices.length; i++) {
      var c = vertices[i];
      var v = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
      var n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
      var len = Math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]);
      if (len > 1e-9) return [n[0] / len, n[1] / len, n[2] / len];
    }
    return null; // every point collinear
  }

  function validate(vertices, extrusion) {
    if (vertices.length < 3) return 'A soil volume needs at least three corners.';

    var bad = null;
    vertices.forEach(function (v, i) {
      if (v.some(function (c) { return !isFinite(c); })) {
        bad = 'Corner ' + (i + 1) + ' has a coordinate that is not a number.';
      }
    });
    if (bad) return bad;

    if (extrusion.some(function (c) { return !isFinite(c); })) {
      return 'The extrusion needs three numbers.';
    }

    var normal = planeNormal(vertices);
    if (!normal) return 'The corners are all in a straight line, so they enclose no area.';

    // Every corner must lie in the plane of the first three.
    var a = vertices[0];
    for (var i = 3; i < vertices.length; i++) {
      var d = (vertices[i][0] - a[0]) * normal[0]
            + (vertices[i][1] - a[1]) * normal[1]
            + (vertices[i][2] - a[2]) * normal[2];
      if (Math.abs(d) > 1e-6) {
        return 'Corner ' + (i + 1) + ' is ' + Math.abs(d).toFixed(3) +
               ' m out of the plane of the others. All corners must be coplanar.';
      }
    }

    var along = extrusion[0] * normal[0] + extrusion[1] * normal[1] + extrusion[2] * normal[2];
    if (Math.abs(along) < 1e-9) {
      return 'The extrusion runs along the polygon, so it would sweep no volume. ' +
             'Extrude across it instead.';
    }
    return null;
  }

  /* Signed area of the polygon in its own plane, times the extrusion component
     across it: the volume gmsh will produce, shown before committing. */
  function volumeOf(vertices, extrusion) {
    var normal = planeNormal(vertices);
    if (!normal) return 0;
    var cross = [0, 0, 0];
    for (var i = 0; i < vertices.length; i++) {
      var p = vertices[i], q = vertices[(i + 1) % vertices.length];
      cross[0] += p[1] * q[2] - p[2] * q[1];
      cross[1] += p[2] * q[0] - p[0] * q[2];
      cross[2] += p[0] * q[1] - p[1] * q[0];
    }
    var area = Math.abs(cross[0] * normal[0] + cross[1] * normal[1] + cross[2] * normal[2]) / 2;
    var height = Math.abs(extrusion[0] * normal[0] + extrusion[1] * normal[1] + extrusion[2] * normal[2]);
    return area * height;
  }


  /* ══════════════════════════════════════════════════════════════
     2D: a surface in the section plane, not a volume

     A plane-strain model has no third dimension to extrude into. The body is an
     outline in the section plane and out of plane it runs forever, so the dialog
     asks for corners in two axes and nothing else.

     What is *sent* is still a polygon_extrude prism: that is what the backend
     sections (app/build.py `_section` intersects a plane with a solid, and a
     surface has nothing to intersect). Sweeping it across the whole domain is the
     honest encoding of "infinite out of plane" -- every section plane cuts it, and
     switching back to 3D shows a body spanning the model rather than a slab of
     arbitrary thickness sitting at a remembered offset.
     ══════════════════════════════════════════════════════════════ */

  /* There is one section plane: the x-y plane, normal to z. The outline is drawn
     in the section's own two axes and swept out of plane along Z. */
  var SECTION_AXES = { inPlane: [0, 1], normal: 2, labels: ['x', 'y'] };

  function sectionAxes() {
    return SECTION_AXES;
  }

  /* How far the model extends along the section normal: the prism spans all of it. */
  function domainSpan(project) {
    var d = (project && project.domain) || {};
    return [d.z0, d.z1];
  }

  function prismFor(project, points) {
    var span = domainSpan(project);
    var vertices = points.map(function (p) { return [p[0], p[1], span[0]]; });
    return { vertices: vertices, extrusion: [0, 0, span[1] - span[0]] };
  }

  function outlineOf(recipe) {
    return (recipe.vertices || []).map(function (v) { return [v[0], v[1]]; });
  }

  /* Shoelace. The outline is already in one plane, so this is the whole story. */
  function areaOf(points) {
    var sum = 0;
    for (var i = 0; i < points.length; i++) {
      var p = points[i], q = points[(i + 1) % points.length];
      sum += p[0] * q[1] - q[0] * p[1];
    }
    return Math.abs(sum) / 2;
  }

  function validateOutline(points) {
    if (points.length < 3) return 'A soil surface needs at least three corners.';
    var bad = null;
    points.forEach(function (p, i) {
      if (!isFinite(p[0]) || !isFinite(p[1])) {
        bad = 'Corner ' + (i + 1) + ' has a coordinate that is not a number.';
      }
    });
    if (bad) return bad;
    if (areaOf(points) < 1e-9) {
      return 'The corners are all in a straight line, so they enclose no area.';
    }
    return null;
  }

  /* Which form to show is not simply "are we in 2D". A body drawn in 3D whose
     extrusion runs along the section plane rather than through it is not a prism at
     all; offering it as an outline would silently flatten a shape the user never
     asked to change. Those keep the volume form. */
  function formFor(project, part) {
    if (!project || project.dimension !== 2) return 'volume';
    var recipe = part && part.recipe;
    if (!recipe || recipe.kind !== 'polygon_extrude') return 'surface';

    var axes = sectionAxes();
    var e = recipe.extrusion || [0, 0, 0];
    var acrossOnly = e.every(function (c, a) {
      return a === axes.normal ? Math.abs(c) > 1e-9 : Math.abs(c) < 1e-9;
    });
    return acrossOnly ? 'surface' : 'volume';
  }

  /* What to print for a body in the model explorer and the soil-bodies table. A
     surface is reported as the area it was drawn as, not as the volume of the
     full-domain prism it is stored as -- that sweep is an encoding detail, and a
     number the user never typed. */
  function measure(project, recipe) {
    if (!recipe || !recipe.vertices) return null;
    if (formFor(project, { recipe: Object.assign({ kind: 'polygon_extrude' }, recipe) })
        === 'surface') {
      return { label: 'Area', unit: 'm²',
               value: areaOf(outlineOf(recipe)) };
    }
    return { label: 'Volume', unit: 'm³',
             value: volumeOf(recipe.vertices, recipe.extrusion) };
  }

  function titleFor(form, editing) {
    return (editing ? 'Edit soil ' : 'Create soil ') + form;
  }

  /* `part` edits an existing body: the form opens on its coordinates and the
     create call rebuilds it in place, keeping its key (and so its mesh size,
     its tree row and the current selection). */
  function open(part, options) {
    options = options || {};
    if (!App.PROJECT || document.getElementById('soil-volume-dialog')) return;
    var editing = part && part.recipe && part.recipe.kind === 'polygon_extrude' ? part : null;
    var form = formFor(App.PROJECT, editing);
    var surface = form === 'surface';
    var axes = sectionAxes();
    var el = App.UI.el;
    var layer = document.getElementById('modal-layer');
    var scrim = el('div.scrim');
    var dialog = el('div.dialog.soil-volume-dialog', { id: 'soil-volume-dialog' });
    dialog.style.width = '560px';
    dialog.style.height = '560px';
    dialog.style.left = Math.max(20, (window.innerWidth - 560) / 2) + 'px';
    dialog.style.top = Math.max(20, (window.innerHeight - 560) / 2) + 'px';

    var closeButton = el('button.dlg-x', { text: '✕', type: 'button' });
    var head = el('div.dlg-head', null,
      [el('span.dlg-title', { text: titleFor(form, !!editing) }), closeButton]);
    dialog.appendChild(head);
    App.Dialogs.draggable(head, dialog);

    var body = el('div.dlg-body.soil-volume-body');
    var fields = el('div.mesh-settings-form');
    body.appendChild(fields);
    dialog.appendChild(body);

    function row(label, control, help) {
      fields.appendChild(el('label.mesh-setting-label', { text: label }));
      fields.appendChild(control);
      fields.appendChild(el('div.mesh-setting-help', { text: help }));
      return control;
    }

    /* ── Name ─────────────────────────────────────────────────── */
    var nameInput = el('input.mesh-setting-control',
                       { type: 'text', value: editing ? editing.label : EXAMPLE.label });
    row('Name', nameInput, 'Shown in the Model explorer.');

    /* ── Material ─────────────────────────────────────────────── */
    var matSelect = el('select.mesh-setting-control');
    (App.MATERIALS || []).forEach(function (m) {
      matSelect.appendChild(el('option', { value: m.id, text: m.name }));
    });
    if (editing && editing.mat) matSelect.value = editing.mat;
    else if (App.MATERIALS && App.MATERIALS.length) matSelect.value = App.MATERIALS[0].id;
    row('Material', matSelect,
        'The ' + form + ' is meshed as soil with this material’s properties, and takes its colour.');

    /* ── Corner table ─────────────────────────────────────────── */
    var vertexRows = [];
    var table = el('div.soil-volume-table' + (surface ? '.planar' : ''));
    var columns = surface ? axes.labels : ['x', 'y', 'z'];
    var head = el('div.soil-volume-head', null,
      [el('span', { text: '#' })]
        .concat(columns.map(function (a) { return el('span', { text: a + ' [m]' }); }))
        .concat([el('span')]));
    var rowsHost = el('div.soil-volume-rows');
    table.appendChild(head);
    table.appendChild(rowsHost);

    function renderVertices() {
      App.UI.clear(rowsHost);
      vertexRows.forEach(function (v, i) {
        var line = el('div.soil-volume-row');
        line.appendChild(el('span.soil-volume-index', { text: String(i + 1) }));
        columns.forEach(function (axis, a) {
          var input = el('input.mesh-setting-control.soil-volume-coord',
                         { type: 'number', step: '0.1', value: v[a] });
          input.addEventListener('change', function () {
            v[a] = num(input.value);
            refresh();
          });
          input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
          });
          line.appendChild(input);
        });
        var remove = el('button.btn.btn-sm', { type: 'button', text: '✕' });
        remove.addEventListener('click', function () {
          vertexRows.splice(i, 1);
          renderVertices();
          refresh();
        });
        line.appendChild(remove);
        rowsHost.appendChild(line);
      });
    }

    var addRow = el('button.btn.btn-sm', { type: 'button', text: 'Add corner' });
    addRow.addEventListener('click', function () {
      var last = vertexRows[vertexRows.length - 1] || columns.map(function () { return 0; });
      vertexRows.push(last.slice());
      renderVertices();
      refresh();
    });

    var tableWrap = el('div', null, [table, el('div.soil-volume-actions', null, [addRow])]);
    row('Corners', tableWrap, surface
        ? 'The outline of the surface, in order, in the ' + axes.labels.join('–') + ' section '
          + 'plane. There is no third coordinate: in plane strain the body runs the full '
          + 'thickness of the model out of plane.'
        : 'The outline of the volume, in order. All corners must lie in one plane — for an '
          + 'embankment, draw the cross-section with x and z varying and y the same on every corner.');

    /* ── Extrusion ────────────────────────────────────────────── */
    // In 2D there is nothing to ask: the outline is swept across the whole domain,
    // which is what "infinite out of plane" means for a body you can section.
    var extInputs = [];
    var extRow = el('div.soil-volume-extrusion');
    if (!surface) ['dx', 'dy', 'dz'].forEach(function (axis, a) {
      extRow.appendChild(el('span.soil-volume-axis', { text: axis }));
      var input = el('input.mesh-setting-control.soil-volume-coord',
                     { type: 'number', step: '0.1', value: EXAMPLE.extrusion[a] });
      input.addEventListener('change', refresh);
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
      });
      extInputs.push(input);
      extRow.appendChild(input);
    });
    if (!surface) {
      row('Extrusion', extRow,
          'How far to sweep the outline, and in which direction. It must point across the ' +
          'outline’s plane — 30 m along y sweeps a cross-section into a 30 m long embankment.');
    }

    /* ── Live readout ─────────────────────────────────────────── */
    var summary = el('div.soil-volume-summary');
    row('', summary, '');

    function readVertices() {
      return vertexRows.map(function (v) { return v.map(num); });
    }
    function readExtrusion() {
      return extInputs.map(function (input) { return num(input.value); });
    }

    /* One shape check for both forms, so the footer and the live readout cannot
       disagree about whether the body is buildable. */
    function check() {
      var points = readVertices();
      if (surface) {
        return { problem: validateOutline(points),
                 summary: points.length + ' corners · area ' + areaOf(points).toFixed(1) + ' m²' };
      }
      var extrusion = readExtrusion();
      return { problem: validate(points, extrusion),
               summary: points.length + ' corners · volume '
                        + volumeOf(points, extrusion).toFixed(1) + ' m³' };
    }

    function refresh() {
      var state = check();
      var problem = state.problem;
      if (problem) {
        summary.textContent = problem;
        summary.classList.add('invalid');
        create.disabled = true;
        return;
      }
      summary.textContent = state.summary;
      summary.classList.remove('invalid');
      create.disabled = false;
    }

    /* ── Footer ───────────────────────────────────────────────── */
    var message = el('span.mesh-settings-message');
    var create = el('button.btn.btn-primary',
                    { text: editing ? 'Save' : 'Create', type: 'button' });
    var cancel = el('button.btn', { text: 'Cancel', type: 'button' });
    dialog.appendChild(el('div.dlg-foot', null, [message, el('span.spacer'), create, cancel]));

    layer.appendChild(scrim);
    layer.appendChild(dialog);

    function close() {
      if (scrim.parentNode) scrim.remove();
      if (dialog.parentNode) dialog.remove();
      document.removeEventListener('keydown', escape);
    }
    function escape(event) { if (event.key === 'Escape') close(); }
    document.addEventListener('keydown', escape);
    closeButton.addEventListener('click', close);
    cancel.addEventListener('click', close);

    create.addEventListener('click', function () {
      var state = check();
      if (state.problem) { message.textContent = state.problem; return; }

      create.disabled = cancel.disabled = true;
      message.textContent = 'Building geometry…';

      // A surface is still sent as a prism: it is a solid the backend can section.
      var shape = surface ? prismFor(App.PROJECT, readVertices())
                          : { vertices: readVertices(), extrusion: readExtrusion() };
      var payload = {
        kind: 'polygon_extrude',
        label: nameInput.value.trim() || ('Soil ' + form),
        material: matSelect.value,
        vertices: shape.vertices,
        extrusion: shape.extrusion
      };
      if (editing) payload.replace = editing.key;
      if (options.insertBefore) payload.insert_before = options.insertBefore;

      App.Api.post('/api/geometry/create', payload)
        .then(function () { return App.Model.load(); })
        .then(function () { return App.Viewport.refresh(); })
        .then(function () {
          App.Explorer.mountTree(App.state.mode);
          if (App.state.selection) App.Explorer.mountSelection(App.state.selection);
          App.Command.ok((editing ? 'Updated' : 'Created') + ' soil ' + form + ' "' +
                         payload.label + '" — ' + state.summary.split('· ')[1] + ' of ' +
                         App.matById(matSelect.value).name + '.');
          close();
          if (options.onSaved) options.onSaved();
        })
        .catch(function (error) {
          create.disabled = cancel.disabled = false;
          message.textContent = error.message;
        });
    });

    // Open on the body being edited, or on the worked example so the shape of the
    // input is obvious.
    var seed;
    if (surface) {
      seed = outlineOf(editing ? editing.recipe : { vertices: EXAMPLE.vertices });
    } else {
      seed = editing ? editing.recipe.vertices : EXAMPLE.vertices;
    }
    vertexRows = seed.map(function (v) { return v.slice(); });
    if (editing && !surface) {
      editing.recipe.extrusion.forEach(function (v, a) { extInputs[a].value = v; });
    }
    renderVertices();
    refresh();
  }

  return {
    open: open, validate: validate, volumeOf: volumeOf, planeNormal: planeNormal,
    sectionAxes: sectionAxes, prismFor: prismFor, outlineOf: outlineOf, areaOf: areaOf,
    validateOutline: validateOutline, formFor: formFor, titleFor: titleFor,
    measure: measure
  };
})();
