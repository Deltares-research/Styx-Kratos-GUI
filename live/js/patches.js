/* Live-only overlays for behavior that is closed over inside the frozen scripts. */

var App = window.App || {};

App.LivePatches = (function () {
  var installed = false;
  var inFlight = false;
  var activeLayerEdit = null;

  function copy(value) { return JSON.parse(JSON.stringify(value)); }
  function snapshotLayers() { return copy(App.LAYERS || []); }
  function restoreLayers(snapshot) {
    App.LAYERS = copy(snapshot);
    if (App.Model && App.Model.rebuildDerived) App.Model.rebuildDerived();
    if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
  }

  /* The soil dialog edits boreholes and layers together -- adding a borehole adds
     a tops/bots key to every layer -- so they have to be snapshotted, restored
     and saved as one unit. */
  function snapshotSoil() {
    return { layers: copy(App.LAYERS || []), boreholes: copy(App.BOREHOLES || []),
             materials: copy(App.MATERIALS || []) };
  }
  function restoreSoil(snapshot) {
    App.LAYERS = copy(snapshot.layers);
    App.BOREHOLES = copy(snapshot.boreholes);
    if (snapshot.materials) App.MATERIALS = copy(snapshot.materials);
    if (App.Model && App.Model.rebuildDerived) App.Model.rebuildDerived();
    if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
  }

  function integer(value) {
    return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  function meshSummary(stats) {
    return 'Mesh generated: ' + integer(stats.elements) + ' elements, '
      + integer(stats.nodes) + ' nodes (' + stats.seconds.toFixed(1) + ' s).';
  }

  function pitRefinement(project, factor) {
    return {
      kind: 'box', size: project.mesh.element_size * factor,
      x_min: project.excavation.x0, x_max: project.excavation.x1,
      y_min: project.excavation.y0, y_max: project.excavation.y1,
      z_min: project.domain.z_bottom, z_max: project.domain.z_top
    };
  }

  function requestMesh(selectAfter, echo) {
    if (inFlight) {
      if (App.Command && App.Command.note) App.Command.note('Mesh generation is already running.');
      return;
    }
    inFlight = true;
    if (App.state.mode !== 'mesh') App.setMode('mesh');
    if (echo) App.Command.write('echo', '> ' + echo);

    App.Viewport.generateMesh(function (stats) {
      inFlight = false;
      if (!stats) return; // viewport already reported the backend failure
      App.Command.ok(meshSummary(stats));
      if (selectAfter) App.selectObject('mesh', 'viewport');
    });
  }

  /* Model explorer: "Delete" for drawn/imported geometry.

     js/explorer.js:91 hard-codes { label: 'Delete', disabled: true } on every tree
     context menu -- the frozen mockup never had anything real to delete. A custom part
     does, so its row gets a second, capturing 'contextmenu' listener that runs before
     the frozen one (stopping it) and opens the same menu with Delete wired up instead. */

  /* Switch between the solid model and the plane-strain x-z section.

     The server owns the dimension, because it decides what the geometry *is*: the
     section is cut by OCC, not projected in the browser. So nothing local changes
     until the patch comes back -- a refused switch (a section plane outside an
     edited domain, say) must not leave a 2D camera pointed at a 3D model. */
  /* 2D and 3D are modes, not views. A view preset moves the camera over one model;
     switching mode changes what the model *is* -- the server cuts a planar section
     through the solids and meshes that instead. That is why this lives in the
     toolbar next to the mode-shaped controls rather than under View, and why it
     costs a full geometry rebuild.

     `viewport` is the camera vocabulary App.Viewport speaks (it needs the plane to
     place the camera); `plane` is what the server cuts. */
  var MODES = [
    { id: '2d', label: '2D', icon: 'section2d', action: 'viewMode2D',
      viewport: 'elevation', plane: 'xz' },
    { id: '3d', label: '3D', icon: 'cube', action: 'viewMode3D',
      viewport: 'solid' }
  ];

  var modeInFlight = false;

  function modeDef(id) {
    return MODES.filter(function (m) { return m.id === id; })[0] || MODES[1];
  }

  function patchFor(id) {
    var def = modeDef(id);
    return def.plane ? { dimension: 2, section_plane: def.plane } : { dimension: 3 };
  }

  /* "z = -12.5" -- the axis the cut travels along, which is the one *not* in the
     plane's name, plus where it sits. */
  function sectionLabel(project) {
    var normal = { xy: 'z', xz: 'y', yz: 'x' }[(project && project.section_plane) || 'xz'];
    var offset = project && project.section_offset;
    return normal + ' = ' + (typeof offset === 'number' ? offset : '?');
  }

  /* Ask the server for a mode. Explicit rather than a toggle, because each button
     names its own target: pressing the mode you are already in should cost nothing,
     and a rebuild of the whole model is not nothing. */
  function setModelMode(id) {
    var def = modeDef(id);
    // Same mode *and* same cut. A project can be 2D on a plane this UI no longer
    // offers (left from an earlier session, or set through the API); guarding on the
    // mode id alone would make the 2D button a no-op and strand it there, because
    // nothing else in the UI can name that plane.
    var already = (App.state.modelMode || '3d') === def.id
      && (!def.plane || !App.PROJECT || App.PROJECT.section_plane === def.plane);
    if (modeInFlight || already) return Promise.resolve();
    modeInFlight = true;

    return App.Api.patch('/api/project/dimension', patchFor(def.id))
      .then(function (result) {
        App.PROJECT = result.project;
        App.state.modelMode = def.id;
        App.state.dimension = def.plane ? 2 : 3;
        syncModelMode(def.id);
        App.Viewport.setViewMode(def.viewport);
        App.Command.note(def.plane
          ? 'Switched to 2D — a plane-strain cross-section at ' + sectionLabel(result.project)
            + '. Geometry and mesh are rebuilt in the x-z plane.'
          : 'Switched to 3D — the full solid model.');
        // A load changes shape with the dimension: a pressure over a footprint in the
        // solid model is a pressure per metre run in the cut, and the server translates
        // between them (server/app/loads.py). It says what it did to each one, and a
        // record the user did not author must not appear in the tree unannounced.
        (result.notes || []).forEach(function (note) { App.Command.note(note); });
        return App.Viewport.refresh();
      })
      .catch(function (error) {
        App.Command.err('Could not switch mode: ' + error.message);
      })
      .then(function () { modeInFlight = false; });
  }

  /* A sheet pile in a section is a wall panel in the solid model -- one tool, two
     structures -- and an anchor hangs from whichever of them is there. The tool has
     to say which one it is about to make, for the same reason the soil-body tool
     renames itself below. */
  function nameStructureActions(is2d) {
    var labels = {
      createSheetPile: is2d ? 'Create sheet pile…' : 'Create wall panel…',
      createMember: 'Create member…',
      createAnchor: is2d ? 'Create anchor…' : 'Create anchor in space…'
    };
    Object.keys(labels).forEach(function (action) {
      ((App.RAILS && App.RAILS.structures) || []).forEach(function (tool) {
        if (tool && tool.action === action) tool.tip = labels[action];
      });
      menuItemsFor(action).forEach(function (item) {
        item.label = labels[action].replace('…', '');
      });
    });
  }

  /* The rail button and the Soil menu open the same dialog, which builds a surface
     in 2D and a volume in 3D. Renaming them on the mode switch keeps the door and
     the room behind it agreeing. Both lists are read at render time, so mutating
     them in place is enough. */
  function nameSoilBodyActions(mode) {
    var noun = mode === '2d' ? 'surface' : 'volume';
    ((App.RAILS && App.RAILS.soil) || []).forEach(function (tool) {
      if (tool && tool.action === 'createSoilVolume') tool.tip = 'Create soil ' + noun + '…';
    });
    (App.MENUS || []).forEach(function (menu) {
      (menu.items || []).forEach(function (item) {
        if (item && item.action === 'createSoilVolume') {
          item.label = 'Create soil ' + noun + '…';
        }
      });
    });
  }

  /* Light the active button and nothing else. Tolerant of missing nodes: the
     unit-test page has no viewport markup. */
  function syncModelMode(id) {
    var active = modeDef(id).id;
    // The state setModelMode() guards on, so a project that *loads* in 2D leaves the
    // switch agreeing with the toolbar rather than believing it is still in 3D.
    App.state = App.state || {};
    App.state.modelMode = active;
    nameSoilBodyActions(active);
    MODES.forEach(function (m) {
      App.Toolbars.setToolbarState(m.action, m.id === active);
    });
    // Everything that is 3D-only goes with it: see syncDimensionAvailability.
    syncDimensionAvailability(active === '2d');
  }

  /* App.Viewport.refresh() speaks in section planes, because that is what places its
     camera. Translate at the boundary rather than teaching either side the other's
     vocabulary. */
  function syncViewMode(viewportMode) {
    syncModelMode(viewportMode === 'solid' ? '3d' : '2d');
  }

  /* ── Making failure visible ──────────────────────────────────────────────
     A blank viewport and a command log that simply stops is the worst thing this
     app can do: it looks like a modelling bug and the real reason is only in
     DevTools. These three put it where the user is already looking. */

  // What patches.js calls on App.Viewport. Their absence means the browser has an
  // older viewport.js than this file -- the two are edited together and renamed
  // together, so a mixed pair is always a cache artefact.
  var REQUIRED_VIEWPORT_API = ['setViewMode', 'refresh', 'viewModeOf', 'orthoHalfHeight',
                             'setNavMode', 'effectiveNavMode', 'syncRulers'];

  function missingViewportApi(viewport) {
    return REQUIRED_VIEWPORT_API.filter(function (name) {
      return typeof (viewport || {})[name] !== 'function';
    });
  }

  function staleMessage(missing) {
    return 'Stale browser cache: live/js/viewport.js is older than live/js/patches.js '
         + '(missing ' + missing.join(', ') + '). Hard-reload with Ctrl+Shift+R.';
  }

  function reportUncaught(event) {
    var reason = event && event.reason;
    var text = reason ? (reason.message || String(reason))
                      : ((event && event.message) || 'Unknown error');
    var where = event && event.filename
      ? ' (' + String(event.filename).split('/').pop() + ':' + event.lineno + ')' : '';
    if (App.Command && App.Command.err) App.Command.err('Script error: ' + text + where);
  }

  function isDeletableCustomPart(key) {
    return !!(key && App.PROJECT
      && (App.PROJECT.custom_parts || []).some(function (part) { return part.key === key; }));
  }

  /* Which of the live-owned collections a tree row's key belongs to, if any --
     the frozen menu (js/explorer.js:89-98) only ever wires up rename/delete for a
     soil layer, so every other kind of live object -- drawn/imported geometry, a
     sheet pile or wall, an anchor, a load -- needs the same two actions built here. */
  function objectKind(key) {
    if (isDeletableCustomPart(key)) return 'part';
    if (App.Beams && App.Beams.isBeamKey(key)) return 'beam';
    if (App.Anchors && App.Anchors.isAnchorKey(key)) return 'anchor';
    if (App.Interfaces && App.Interfaces.isInterfaceKey(key)) return 'interface';
    if (App.Loads && App.Loads.isLoadKey(key)) return 'load';
    return null;
  }

  function partByKey(key) {
    return ((App.PROJECT && App.PROJECT.custom_parts) || [])
      .filter(function (part) { return part.key === key; })[0];
  }

  function beamByKey(key) {
    return (App.BEAMS || []).filter(function (beam) { return beam.id === key; })[0];
  }

  function anchorByKey(key) {
    return (App.ANCHORS || []).filter(function (anchor) { return anchor.id === key; })[0];
  }

  function loadByKey(key) {
    return (App.LOADS || []).filter(function (load) { return load.id === key; })[0];
  }

  function interfaceByKey(key) {
    return (App.INTERFACES || []).filter(function (item) { return item.id === key; })[0];
  }

  function objectName(kind, key) {
    var obj = kind === 'part' ? partByKey(key)
      : kind === 'beam' ? beamByKey(key)
      : kind === 'anchor' ? anchorByKey(key)
      : kind === 'interface' ? interfaceByKey(key)
      : kind === 'load' ? loadByKey(key) : null;
    return obj ? (kind === 'part' ? obj.label : obj.name) : '';
  }

  function reportRenameError(error) {
    if (App.Command && App.Command.err) App.Command.err(error.message);
  }

  /* One rename path for every live kind: prompt, write the field the frozen grid
     already treats as the display name, then save through each kind's own door --
     a custom part goes back through the layers/domain/custom_parts PATCH (see
     commitSelectionEdit), a beam/anchor/load through its own module, which is what
     validates, persists and refreshes the tree for it already. */
  function renameObject(kind, key) {
    var name = window.prompt('New name', objectName(kind, key));
    if (name === null) return;
    name = name.trim();
    if (!name) { reportRenameError(new Error('Name cannot be empty.')); return; }

    if (kind === 'part') {
      var part = partByKey(key);
      if (!part) return;
      part.label = name;
      return App.commitSelectionEdit(key);
    }
    if (kind === 'beam') {
      var beam = beamByKey(key);
      if (!beam) return;
      beam.name = name;
      return App.Beams.save(beam, copy(App.BEAM_SECTIONS || [])).catch(reportRenameError);
    }
    if (kind === 'anchor') {
      var anchor = anchorByKey(key);
      if (!anchor) return;
      anchor.name = name;
      return App.Anchors.save(anchor, copy(App.ANCHOR_SECTIONS || [])).catch(reportRenameError);
    }
    if (kind === 'interface') {
      var contact = interfaceByKey(key);
      if (!contact) return;
      contact.name = name;
      return App.Interfaces.save(contact, copy(App.INTERFACE_SECTIONS || []))
        .catch(reportRenameError);
    }
    if (kind === 'load') {
      var load = loadByKey(key);
      if (!load) return;
      load.name = name;
      return App.Loads.save(load).catch(reportRenameError);
    }
  }

  function deleteObject(kind, key) {
    if (kind === 'part') return deleteCustomPart(key);
    if (kind === 'beam') return App.Beams.remove(key);
    if (kind === 'anchor') return App.Anchors.remove(key);
    if (kind === 'interface') return App.Interfaces.remove(key);
    if (kind === 'load') return App.Loads.remove(key);
  }

  /* explorer.js builds one tree DOM row per App.TREES[mode] node, in the same
     depth-first order -- there is no other way to recover which key a row is for, since
     rowsByObj lives in explorer.js's closure. */
  function tagTreeRowsWithObjKeys(mode) {
    var host = document.getElementById('tree-model');
    if (!host) return;
    var rows = host.querySelectorAll('.tree-row');
    var i = 0;
    (function walk(nodes) {
      (nodes || []).forEach(function (n) {
        var row = rows[i++];
        if (row) row.dataset.obj = n.obj || '';
        walk(n.children || []);
      });
    })((App.TREES && App.TREES[mode]) || []);
  }

  function deleteCustomPart(key) {
    if (App.Command && App.Command.note) App.Command.note('Deleting ' + key + '…');
    return fetch(App.Api.base + '/api/geometry/parts/' + encodeURIComponent(key), { method: 'DELETE' })
      .then(function (res) {
        if (!res.ok) return res.json().then(function (err) { throw new Error(err.detail || 'Delete failed'); });
        return res.json();
      })
      .then(function () { return App.Model.load(); })
      .then(function () { return App.Viewport.refresh(); })
      .then(function () {
        if (App.state && App.state.selection === key) App.selectObject(null, 'tree');
        if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
        if (App.Command && App.Command.ok) App.Command.ok('Deleted ' + key + '.');
      })
      .catch(function (err) {
        if (App.Command && App.Command.err) App.Command.err('Error deleting geometry: ' + err.message);
      });
  }

  /* Custom soil volumes, listed in the frozen "Modify soil layers" window.

     They are kept out of the layer table on purpose: that table is the borehole
     stack -- per-borehole tops and bottoms that must tile the domain gap-free --
     and a polygon prism has no place in it. What is editable here is what the
     two have in common: the name and the material. The shape is coordinates, so
     it is edited as coordinates. */
  function addSoilBodySection(dialog) {
    var bodies = ((App.PROJECT && App.PROJECT.custom_parts) || [])
      .filter(function (part) { return !!part.mat; });

    var el = App.UI.el;
    var pane = dialog.querySelector('.lay-pane');
    if (!pane) return;
    var previous = pane.querySelector('.soil-body-section');
    if (previous) previous.remove();

    var section = el('div.soil-body-section');
    section.appendChild(el('div.soil-body-section-head', { text: 'Custom soil volumes' }));
    var selected = bodies.length ? bodies[0].key : null;
    var actions = el('div.lay-toolbar');
    function persistStack() {
      if (!App.MATERIALS.length) App.addMaterial();
      return App.Api.patch('/api/project/layers', {
        layers: copy(App.LAYERS), boreholes: copy(App.BOREHOLES),
        materials: App.Model.materialsToServer(App.MATERIALS)
      }).then(function (response) {
        App.Model.apply(response.project);
        if (activeLayerEdit) activeLayerEdit.snapshot = snapshotSoil();
      });
    }
    function refreshBodies() {
      if (activeLayerEdit) activeLayerEdit.snapshot = snapshotSoil();
      addSoilBodySection(dialog);
    }
    ['Add', 'Insert', 'Delete'].forEach(function (label) {
      var button = el('button.btn.btn-sm', { text: label, type: 'button' });
      button.disabled = label === 'Delete' && !selected;
      button.addEventListener('click', function () {
        button.disabled = true;
        persistStack().then(function () {
          if (label === 'Delete') {
            return fetch(App.Api.base + '/api/geometry/parts/' + encodeURIComponent(selected), { method: 'DELETE' })
              .then(function (response) {
                if (!response.ok) throw new Error('Could not delete the custom layer.');
                return App.Model.load();
              }).then(function () { return App.Viewport.refresh(); }).then(refreshBodies);
          }
          App.SoilVolumeDialog.open(null, {
            insertBefore: label === 'Insert' ? selected : null, onSaved: refreshBodies
          });
        }).catch(function (error) { App.Command.err(error.message); })
          .then(function () { button.disabled = label === 'Delete' && !selected; });
      });
      actions.appendChild(button);
    });
    section.appendChild(actions);

    var table = el('table.lay-table');
    var headRow = el('tr');
    ['Volume', 'Material', 'Size', ''].forEach(function (h) {
      headRow.appendChild(el('th', { text: h }));
    });
    table.appendChild(el('thead', null, headRow));
    var tbody = el('tbody');
    table.appendChild(tbody);

    /* Saved straight away: this window's OK covers the layer stack, which these
       are not part of, so there is nothing for it to commit on their behalf. */
    function save() {
      return App.commitSelectionEdit(App.state.selection);
    }

    bodies.forEach(function (part) {
      var tr = el('tr');
      tr.classList.toggle('selected', part.key === selected);
      tr.addEventListener('mousedown', function () {
        selected = part.key;
        Array.prototype.forEach.call(tbody.children, function (row) {
          row.classList.toggle('selected', row === tr);
        });
      });

      var name = el('input.cell-input', { value: part.label });
      name.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); name.blur(); }
      });
      name.addEventListener('change', function () {
        var value = name.value.trim();
        if (!value) { name.value = part.label; return; }
        part.label = value;
        save();
      });
      tr.appendChild(el('td', null, name));

      var matCell = el('div.cell-mat');
      var swatch = el('span.tree-swatch');
      swatch.style.background = part.color;
      var select = el('select');
      (App.MATERIALS || []).forEach(function (m) {
        select.appendChild(el('option', { value: m.id, text: m.name }));
      });
      select.value = part.mat;
      select.addEventListener('change', function () {
        part.mat = select.value;
        part.color = App.matById(part.mat).color;
        swatch.style.background = part.color;
        save();
      });
      matCell.appendChild(swatch);
      matCell.appendChild(select);
      tr.appendChild(el('td', null, matCell));

      var size = App.SoilVolumeDialog && part.recipe
        ? App.SoilVolumeDialog.measure(App.PROJECT, part.recipe) : null;
      tr.appendChild(el('td', { text: size ? size.value.toFixed(1) + ' ' + size.unit : '—',
                                style: 'font-family:var(--font-mono);font-size:11.5px' }));

      var edit = el('button.btn.btn-sm', { type: 'button', text: 'Coordinates…' });
      edit.addEventListener('click', function () {
        dialog.querySelector('.dlg-x').click();   // the stack editor is modal
        App.SoilVolumeDialog.open(part);
      });
      tr.appendChild(el('td', null, edit));

      tbody.appendChild(tr);
    });

    section.appendChild(table);
    section.appendChild(el('div.lay-hint', { text:
      'These are solids defined by coordinates, not borehole layers, so they have no ' +
      'top/bottom in the stack above. Insert creates a body before the selected row. ' +
      'Custom actions save the current borehole edits; custom changes save immediately.' }));

    var hint = pane.querySelector('.lay-hint');
    if (hint) pane.insertBefore(section, hint); else pane.appendChild(section);
  }

  function onTreeContextMenu(event) {
    var row = event.target.closest && event.target.closest('.tree-row');
    var key = row && row.dataset.obj;
    var kind = objectKind(key);
    if (!kind) return; // not ours -- let the frozen menu handle it (soil layers, groups, …)

    event.preventDefault();
    event.stopImmediatePropagation(); // the frozen row listener must not also open a menu

    App.Menu.openAt([
      { label: 'Zoom to object', icon: 'zoomfit', action: 'zoomFit' },
      { label: App.Viewport.isVisible(key) ? 'Hide' : 'Show', icon: 'eye' },
      '-',
      { label: 'Rename…', action: 'renameObject' },
      { label: 'Delete', icon: 'delete', action: 'deleteObject' },
      '-',
      { label: 'Properties…', icon: 'settings' }
    ], event.clientX, event.clientY, function (it) {
      if (it.action === 'deleteObject') return deleteObject(kind, key);
      if (it.action === 'renameObject') return renameObject(kind, key);
      if (it.action) { App.runAction(it); return; }
      if (/Hide|Show/.test(it.label)) {
        var on = !App.Viewport.isVisible(key);
        App.Viewport.setVisible(key, on);
        if (App.Explorer && App.Explorer.syncEyes) App.Explorer.syncEyes(key, on);
      }
    });
  }


  /* ══════════════════════════════════════════════════════════════════════════
     The rest of the toolbar.

     js/data.js:197-223 draws fifteen buttons; six of them -- New, Open, Save, Undo,
     Redo and the pan/rotate pair -- were never given an action, because the frozen
     mockup had no document to make, load, save or step backwards through. The live
     build has one, and it is a single JSON object on the server, which is what makes
     all six a few lines each rather than a feature apiece.
     ══════════════════════════════════════════════════════════════════════════ */

  /* Actions a plane-strain section cannot serve. The four view presets and the
     isometric view all resolve to the same locked camera; perspective would stop the
     section being measurable; orbiting is undone by clampAngles as fast as it happens;
     and a box or a cylinder is a solid, which is not a thing a 2D model contains. */
  /* What a 2D section cannot serve. Mostly the camera -- a locked section view cannot
     orbit, take a preset angle or go perspective -- and, since the structures arrived,
     the objects a plane has no room for: a box, a cylinder and a member all exist in
     the solid model alone. `createSheetPile` is deliberately *not* here: it makes the
     wall of whichever dimension is open. */
  var THREE_D_ONLY = ['viewFront', 'viewTop', 'viewSide', 'viewIso',
                      'toggleProjection', 'navRotate', 'drawBox', 'drawCylinder',
                      'createMember'];

  /* And the mirror of it. An interface is a zero-thickness contact along a line in
     the section: every reference deck that has one is plane strain, and the 3D
     element is a surface with a different node layout and no fixture to pin it. */
  /* The rulers measure two named axes of one plane. In 3D the screen edges are three
     axes mixed by the orbit, so a number on an edge would be a number for nothing. */
  var TWO_D_ONLY = ['interface', 'toggleRuler'];

  function availableIn2D(action) { return THREE_D_ONLY.indexOf(action) < 0; }

  function availableIn3D(action) { return TWO_D_ONLY.indexOf(action) < 0; }

  /* Both directions ask a positive question. "Not 2D" is not the same as "3D" before
     the first mode is known, and answering it as 3D would close the interface tool on a
     model whose dimension nothing has said yet. */
  function availableNow(action) {
    if (in2D()) return availableIn2D(action);
    if (in3D()) return availableIn3D(action);
    return true;
  }

  function in2D() { return (App.state && App.state.modelMode) === '2d'; }

  function in3D() { return (App.state && App.state.modelMode) === '3d'; }

  function setToolbarDisabled(action, off) {
    var button = document.querySelector('#maintoolbar .tbtn[data-action="' + action + '"]');
    if (!button) return;
    button.classList.toggle('disabled', !!off);
    button.disabled = !!off;
  }

  function menuItemsFor(action) {
    var found = [];
    (App.MENUS || []).forEach(function (menu) {
      (menu.items || []).forEach(function (item) {
        if (item && item.action === action) found.push(item);
      });
    });
    return found;
  }

  /* ── Structures rail order ──────────────────────────────────────────────
     Every live tool was appended to the frozen rail, so sheet piles, anchors,
     import and the box all landed after "Tunnel designer" -- a separator away
     from the plates and beams they belong with. The rail is composed here
     instead, in the order a model is actually built: pick things, draw the
     geometry, hang structural members on it, load them, then the whole-model
     tools. Groups become the separators the rail draws between them. */
  var STRUCTURES_RAIL_GROUPS = [
    ['select', 'selectmulti'],
    ['drawPoint', 'drawLine', 'drawPolygon', 'drawBox'],
    ['plate', 'beam', 'embedded', 'createSheetPile', 'createMember', 'createAnchor',
     'interface'],
    ['createLoad', 'prescribed'],
    ['tunnel'],
    ['importModel']
  ];

  /* The frozen node-to-node anchor tool draws nothing -- live/js/anchors.js owns
     anchors now -- so it would only stand beside the real one as a dead twin. */
  var STRUCTURES_RAIL_DROPPED = ['anchor'];

  /* A tool is named by its action; the frozen mockup leaves most of them without
     one, and there the icon is the only name it has. */
  function railKey(tool) { return (tool && (tool.action || tool.icon)) || ''; }

  /* Pure, and tolerant of a rail this file has never seen: a tool that matches no
     group keeps its place in a trailing group rather than disappearing. */
  function orderStructuresRail(tools) {
    var rest = (tools || []).filter(function (tool) { return tool && tool !== '-'; });
    var groups = [];

    STRUCTURES_RAIL_GROUPS.forEach(function (keys) {
      var found = [];
      keys.forEach(function (key) {
        rest = rest.filter(function (tool) {
          if (railKey(tool) !== key) return true;
          found.push(tool);
          return false;
        });
      });
      if (found.length) groups.push(found);
    });

    var unknown = rest.filter(function (tool) {
      return STRUCTURES_RAIL_DROPPED.indexOf(railKey(tool)) < 0;
    });
    if (unknown.length) groups.push(unknown);

    return groups.reduce(function (rail, group, i) {
      if (i) rail.push('-');
      return rail.concat(group);
    }, []);
  }

  /* The left rail is remounted whole on every mode change and its buttons carry no
     action attribute, so the tools are matched positionally against App.RAILS -- the
     same order js/toolbars.js:86-92 renders them in. */
  function gateRail() {
    var rail = document.getElementById('toolrail');
    var tools = (App.RAILS || {})[(App.state || {}).mode] || [];
    if (!rail) return;
    var buttons = rail.querySelectorAll('.rail-btn');
    var i = 0;
    tools.forEach(function (tool) {
      if (tool === '-') return;
      var button = buttons[i++];
      if (!button) return;
      var off = !availableNow(tool.action);
      button.classList.toggle('disabled', off);
      button.disabled = off;
    });
  }

  /* One place decides what is available, so the toolbar, the menus, the rail and the
     view cube cannot disagree about it. */
  function syncDimensionAvailability(is2d) {
    THREE_D_ONLY.forEach(function (action) {
      setToolbarDisabled(action, is2d);
      menuItemsFor(action).forEach(function (item) { item.disabled = !!is2d; });
    });
    TWO_D_ONLY.forEach(function (action) {
      setToolbarDisabled(action, !is2d);
      menuItemsFor(action).forEach(function (item) { item.disabled = !is2d; });
    });

    (((App.RAILS || {}).structures || []).filter(function (tool) {
      return tool && tool.icon === 'load';
    })[0] || { flyout: [] }).flyout.forEach(function (item) {
      item.disabled = is2d ? item.loadKind === 'surface' : item.loadKind !== 'surface';
    });

    // Neither structure tool is gated by dimension any more: each dimension has its
    // own kind of them. What changes is which one the tool makes, so the tool says so.
    nameStructureActions(is2d);

    if (App.Toolbars && App.Toolbars.setToolbarState) {
      // 2D navigates by panning and draws in parallel projection; both buttons have to
      // say so, because neither state is the one the user last chose.
      var nav = is2d ? 'pan'
        : (App.Viewport && App.Viewport.getNavMode ? App.Viewport.getNavMode() : 'rotate');
      App.Toolbars.setToolbarState('navPan', nav === 'pan');
      App.Toolbars.setToolbarState('navRotate', nav === 'rotate');
      App.Toolbars.setToolbarState('toggleProjection',
        !is2d && (!App.state || App.state.projection !== false));
    }

    gateRail();

    if (typeof document === 'undefined') return;
    // Front/top/side/iso all resolve to the section once the camera is locked, so
    // showing them live would promise a rotation that cannot happen.
    var cube = document.getElementById('vp-viewcube');
    if (cube) {
      cube.classList.toggle('off', !!is2d);
      cube.querySelectorAll('button').forEach(function (b) { b.disabled = !!is2d; });
    }
  }

  /* ── Undo / redo ─────────────────────────────────────────────────────────── */

  function syncHistoryButtons() {
    var can = { undo: App.History.canUndo(), redo: App.History.canRedo() };
    ['undo', 'redo'].forEach(function (action) {
      setToolbarDisabled(action, !can[action]);
      menuItemsFor(action).forEach(function (item) { item.disabled = !can[action]; });
    });
  }

  /* ── New, open, save ─────────────────────────────────────────────────────── */

  function confirmDialog(title, text, onConfirm) {
    if (!App.Dialogs || !App.Dialogs.open) return onConfirm();
    App.Dialogs.open({
      title: title, width: 440, height: 220,
      buttons: [{ label: 'OK', primary: true, onClick: onConfirm }, { label: 'Cancel' }],
      build: function (body) {
        body.appendChild(App.UI.el('div.dlg-simple', null, [
          App.UI.el('h3', { text: title }),
          App.UI.el('p', { text: text })
        ]));
      }
    });
  }

  /* Applies a project the user chose -- the seed, or a file -- and starts its history
     over: the steps that came before belong to a document that is no longer open. */
  function adoptProject(project, message) {
    App.Model.apply(project);
    App.History.reset();
    syncHistoryButtons();
    // A previewed or accepted .mdpa belongs to the document that was open when it was
    // loaded -- swapping to a different one (new or opened) leaves all of it behind:
    // the preview, the floating checklist, and any parts already accepted into the
    // Model explorer's "Imported mesh" node.
    if (App.Viewport.clearImportedMesh) App.Viewport.clearImportedMesh();
    if (App.MdpaImportDialog && App.MdpaImportDialog.closeChecklist) {
      App.MdpaImportDialog.closeChecklist();
    }
    if (App.Model.setImportedParts) App.Model.setImportedParts([]);
    return Promise.resolve(App.Viewport.refresh()).then(function () {
      if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
      if (App.Command) App.Command.ok(message);
    });
  }

  /* An empty site, not the seeded demo -- the server owns what "empty" means, and a
     second definition here would be one to keep in step. */
  function newProject() {
    return App.Api.post('/api/project/new')
      .then(function (result) {
        return adoptProject(result.project, 'New project started — empty site.');
      })
      .catch(function (error) {
        if (App.Command) App.Command.err('Could not start a new project: ' + error.message);
      });
  }

  function projectFromFileText(text) {
    var parsed;
    try { parsed = JSON.parse(text); } catch (err) { parsed = null; }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('That is not a project file — expected the JSON written by Save.');
    }
    return parsed;
  }

  /* The name inside the document is whatever it was called when it was written --
     every project derived from the seed says "Deep excavation — Rotterdam Zuid" --
     so the title bar announced that whichever file was opened. The file the user
     picked is the name they know the project by, and adopting it also means Save
     writes back to the file it was opened from. A file with nothing but an
     extension leaves the document's own name standing. */
  function projectNameFromFile(fileName) {
    return String(fileName === null || fileName === undefined ? '' : fileName)
      .trim().replace(/\.json$/i, '').trim();
  }

  function openProject() {
    var input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json,application/json';
    input.style.display = 'none';
    document.body.appendChild(input);
    input.addEventListener('change', function () {
      var file = input.files && input.files[0];
      input.remove();
      if (!file) return;
      file.text().then(function (text) {
        var opened = projectFromFileText(text);
        var named = projectNameFromFile(file.name);
        if (named) opened.name = named;
        // Straight to the server: it is the validator. A project that fails there is
        // one the app must not half-load, and the message says which field.
        return App.Api.put('/api/project', opened)
          .then(function (project) {
            return adoptProject(project, 'Opened project: ' + file.name);
          });
      }).catch(function (error) {
        if (App.Command) App.Command.err('Could not open ' + file.name + ': ' + error.message);
      });
    });
    input.click();
  }

  function projectFileName(project) {
    var name = (project && project.name) || '';
    // Kept close to what the user typed, minus what a file system would refuse.
    var safe = name.replace(/[\\/:*?"<>|]+/g, '-').replace(/\s+/g, ' ').trim();
    return (safe || 'project') + '.json';
  }

  function saveProject() {
    // The server's copy, not the browser's: App.PROJECT is a snapshot from whenever
    // the last request answered, and a save has to be of what is actually modelled.
    return App.Api.get('/api/project')
      .then(function (project) {
        downloadFile(projectFileName(project), JSON.stringify(project, null, 2));
        if (App.Command) App.Command.ok('Saved ' + projectFileName(project) + '.');
      })
      .catch(function (error) {
        if (App.Command) App.Command.err('Could not save the project: ' + error.message);
      });
  }

  function downloadFile(name, text) {
    var url = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
    var link = document.createElement('a');
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 0);
  }

  /* ── Pan / rotate ────────────────────────────────────────────────────────── */

  function setNavigation(mode) {
    var chosen = App.Viewport.setNavMode(mode);
    if (!App.Command) return;
    if (in2D() && chosen === 'rotate') return;
    App.Command.note(chosen === 'pan'
      ? 'Navigation: left-drag pans. (Middle-drag pans in either mode.)'
      : 'Navigation: left-drag orbits.');
  }

  /* ── Rulers ─────────────────────────────────────────────────────────────
     live/js/ruler.js owns the drawing; this owns the switch. The state lives on
     App.state beside `grid` and `snap`, so it is one flag in one place whether the
     toolbar, the View menu or a mode change last touched it. On by default: a section
     is a measured drawing, and the point of the rulers is that nobody has to know
     they exist to read a coordinate off one. */

  function rulersOn() {
    App.state = App.state || {};
    if (App.state.ruler === undefined) App.state.ruler = true;
    return App.state.ruler;
  }

  /* Pushes the flag to the renderer and to both copies of the switch. Called on every
     change and once at install, so the two never drift apart. */
  function applyRulers() {
    var on = rulersOn();
    if (App.Ruler) {
      App.Ruler.setEnabled(on);
      // The rulers are painted from the render tick; a switch flipped while nothing is
      // moving has to ask for that tick itself.
      if (App.Viewport && App.Viewport.syncRulers) App.Viewport.syncRulers();
    }
    if (App.Toolbars && App.Toolbars.setToolbarState) {
      App.Toolbars.setToolbarState('toggleRuler', on);
    }
    menuItemsFor('toggleRuler').forEach(function (item) { item.checked = on; });
    return on;
  }

  function toggleRulers() {
    App.state.ruler = !rulersOn();
    applyRulers();
    App.Command.note('Rulers ' + (App.state.ruler ? 'shown' : 'hidden')
                     + ' along the viewport edges.');
  }

  function install() {
    if (installed || typeof App.runAction !== 'function' || !App.Command) return;
    installed = true;

    if (!App.Command.err) {
      App.Command.err = function (text) { App.Command.write('err', text); };
    }

    var stale = missingViewportApi(App.Viewport);
    if (stale.length) App.Command.err(staleMessage(stale));

    if (typeof window !== 'undefined' && !window.__liveErrorsWired) {
      window.__liveErrorsWired = true;
      window.addEventListener('error', reportUncaught);
      window.addEventListener('unhandledrejection', reportUncaught);
    }

    var frozenAction = App.runAction;
    App.runAction = function (item) {
      // Refused rather than quietly ignored: the button is greyed out, so anything
      // that still gets here came from a keyboard shortcut or a menu that was open
      // when the mode changed, and silence would read as a broken command.
      if (item && item.action && !availableIn2D(item.action) && in2D()) {
        if (App.Command) {
          App.Command.note('"' + (item.tip || item.label || item.action)
            + '" is a 3D feature. The model is a 2D section — switch to 3D first.');
        }
        return;
      }
      if (item && item.action && !availableIn3D(item.action) && in3D()) {
        if (App.Command) {
          App.Command.note('"' + (item.tip || item.label || item.action)
            + '" is a plane-strain feature. The model is the solid one — switch to 2D first.');
        }
        return;
      }

      if (item && item.action === 'newProject') {
        confirmDialog('New project',
          'This discards the current model and starts again from an empty project. '
          + 'Save first if you want to keep it.', newProject);
        return;
      }
      if (item && item.action === 'openProject') { openProject(); return; }
      if (item && item.action === 'saveProject') return saveProject();
      if (item && item.action === 'undo') return App.History.undo();
      if (item && item.action === 'redo') return App.History.redo();
      if (item && /^nav(Pan|Rotate)$/.test(item.action || '')) {
        return setNavigation(item.action === 'navPan' ? 'pan' : 'rotate');
      }

      if (item && item.action === 'importModel') {
        if (App.ImportDialog) App.ImportDialog.open();
        return;
      }
      if (item && item.action === 'importMdpa') {
        if (App.MdpaImportDialog) App.MdpaImportDialog.open();
        return;
      }
      
      var drawModes = {
        'drawPoint': 'point',
        'drawLine': 'line',
        'drawPolygon': 'polygon',
        'drawBox': 'box',
        'drawCylinder': 'cylinder'
      };
      
      if (item && drawModes[item.action]) {
        if (App.DrawInput) App.DrawInput.start(drawModes[item.action]);
        return;
      }
      
      if (item && item.action === 'generateMesh') {
        var size = App.PROJECT && App.PROJECT.mesh ? App.PROJECT.mesh.element_size : 2.5;
        requestMesh(true, 'mesh ' + size);
        return;
      }
      if (item && item.action === 'createSoilVolume') {
        if (App.SoilVolumeDialog) App.SoilVolumeDialog.open();
        return;
      }
      if (item && item.action === 'createLoad') {
        if (App.Loads) App.Loads.start(item.loadKind || (in2D() ? 'line' : 'surface'));
        return;
      }
      if (item && item.action === 'createSheetPile') {
        if (App.Beams) App.Beams.start(item.beamKind);
        return;
      }
      if (item && item.action === 'createMember') {
        if (App.Beams) App.Beams.start('member');
        return;
      }
      if (item && item.action === 'createAnchor') {
        if (App.Anchors) App.Anchors.start();
        return;
      }
      if (item && item.action === 'interface') {
        if (App.Interfaces) App.Interfaces.start();
        return;
      }
      if (item && item.action === 'exportModel') {
        if (App.Export) App.Export.run();
        return;
      }

      if (item && item.action === 'toggleRuler') return toggleRulers();

      if (item && /^viewMode(2D|3D)$/.test(item.action || '')) {
        return setModelMode(item.action === 'viewMode2D' ? '2d' : '3d');
      }

      if (item && item.action === 'meshSettings') {
        App.MeshSettings.open();
        return;
      }
      if (item && /^(refineMesh|coarsenMesh|resetMeshRefinement)$/.test(item.action)) {
        if (item.action === 'resetMeshRefinement') {
          App.MESH_REFINEMENTS = [];
          App.Command.note('Local mesh refinements reset.');
        } else {
          var factor = item.action === 'refineMesh' ? 0.5 : 2;
          App.MESH_REFINEMENTS = [pitRefinement(App.PROJECT, factor)];
          App.Command.note((factor < 1 ? 'Refinement' : 'Coarsening')
                           + ' region set inside the excavation. Generate the mesh to apply it.');
        }
        return;
      }
      return frozenAction(item);
    };

    /* The six frozen buttons that were drawn without an action, given one. Matched by
       icon and toggle name, which is all js/data.js:197-223 identifies them by. */
    var TOOLBAR_ACTIONS = { new: 'newProject', open: 'openProject', save: 'saveProject',
                            undo: 'undo', redo: 'redo' };
    App.TOOLBAR.forEach(function (t) {
      if (t === '|' || t.action) return;
      if (TOOLBAR_ACTIONS[t.icon]) t.action = TOOLBAR_ACTIONS[t.icon];
      else if (t.toggle === 'pan') t.action = 'navPan';
      else if (t.toggle === 'rotate') t.action = 'navRotate';
      // Undo and Redo start empty; syncHistoryButtons owns them from here.
      if (t.action === 'undo' || t.action === 'redo') t.disabled = true;
    });

    // The frozen tips describe the gestures, not the modes, because there were no
    // modes: both buttons only ever moved a highlight around.
    App.TOOLBAR.forEach(function (t) {
      if (t === '|') return;
      if (t.action === 'navPan') t.tip = 'Pan — left-drag pans (middle-drag always does)';
      if (t.action === 'navRotate') t.tip = 'Rotate — left-drag orbits the model (3D only)';
    });

    var MENU_ACTIONS = {
      File: { 'New project…': 'newProject', 'Open project…': 'openProject',
              'Save': 'saveProject', 'Save as…': 'saveProject' },
      Edit: { 'Undo': 'undo', 'Redo': 'redo' }
    };
    (App.MENUS || []).forEach(function (menu) {
      var wanted = MENU_ACTIONS[menu.label];
      if (!wanted) return;
      (menu.items || []).forEach(function (item) {
        if (item && !item.action && wanted[item.label]) item.action = wanted[item.label];
      });
    });

    App.History.install();
    App.History.onChange = syncHistoryButtons;

    // The rail is rebuilt on every mode change, so the gating has to be reapplied
    // after each mount rather than once at boot.
    if (App.Toolbars && App.Toolbars.mountRail) {
      var frozenMountRail = App.Toolbars.mountRail;
      App.Toolbars.mountRail = function (mode) {
        frozenMountRail(mode);
        gateRail();
      };
    }

    // js/data.js is frozen -- it is served as the same bytes from file:// and from
    // the server -- so the 2D switch is spliced into its arrays here instead.
    // A cross-section through a block: a rectangle with the cut face hatched.
    if (!App.ICONS.section2d) {
      App.ICONS.section2d = '<path d="M4 5h16v14H4z"/><path d="M4 12h16"/><path d="M8 5v14"/>';
    }

    // A rule with three ticks: the thing itself, not a metaphor for it.
    if (!App.ICONS.ruler) {
      App.ICONS.ruler = '<path d="M3 8h18v8H3z"/><path d="M7.5 8v4"/><path d="M12 8v5"/>'
                      + '<path d="M16.5 8v4"/>';
    }

    // Their own group in the toolbar, fenced by separators: they are not view tools
    // sitting beside zoom and pan, they choose which model is being edited. Both
    // carry a text label, so neither has to be decoded from an icon.
    if (!App.TOOLBAR.some(function (t) { return t && t.action === 'viewMode2D'; })) {
      // After the file group's separator, so the toolbar reads
      // "new open save | 2D 3D | undo redo | ...": fenced on both sides, and well
      // clear of the view tools they must not be mistaken for.
      var at = App.TOOLBAR.indexOf('|') + 1;
      var buttons = MODES.map(function (m) {
        return { icon: m.icon, wide: m.label, action: m.action,
                 tip: m.id === '2d'
                   ? '2D model — a plane-strain cross-section, meshed with triangles'
                   : '3D model — the full solid, meshed with tetrahedra',
                 on: m.id === '3d' };
      });
      App.TOOLBAR.splice.apply(App.TOOLBAR, [at, 0].concat(buttons).concat(['|']));
    }

    /* The ruler switch goes beside Show grid, in both places the grid switch lives:
       they are the same kind of thing -- reference marks over the section -- and a
       user looking to turn one off looks for the other in the same group. */
    if (!App.TOOLBAR.some(function (t) { return t && t.action === 'toggleRuler'; })) {
      var gridAt = App.TOOLBAR.findIndex(function (t) { return t && t.action === 'toggleGrid'; });
      App.TOOLBAR.splice(gridAt < 0 ? App.TOOLBAR.length : gridAt + 1, 0, {
        icon: 'ruler', tip: 'Show rulers — coordinates along all four viewport edges (2D)',
        action: 'toggleRuler', on: rulersOn()
      });
    }
    var viewMenu = (App.MENUS || []).filter(function (m) { return m.label === 'View'; })[0];
    if (viewMenu && !viewMenu.items.some(function (i) { return i && i.action === 'toggleRuler'; })) {
      var gridItem = viewMenu.items.filter(function (i) { return i && i.action === 'toggleGrid'; })[0];
      viewMenu.items.splice(viewMenu.items.indexOf(gridItem) + 1, 0,
        { label: 'Show rulers', icon: 'ruler', checked: rulersOn(), action: 'toggleRuler' });
    }
    applyRulers();

    (App.RAILS.mesh || []).forEach(function (tool) {
      if (!tool || !tool.tip) return;
      if (tool.tip === 'Refine mesh') tool.action = 'refineMesh';
      else if (tool.tip === 'Coarsen mesh') tool.action = 'coarsenMesh';
      else if (tool.tip === 'Reset local refinement') tool.action = 'resetMeshRefinement';
    });
    if (!(App.RAILS.mesh || []).some(function (tool) { return tool && tool.action === 'meshSettings'; })) {
      App.RAILS.mesh.splice(2, 0, { icon: 'settings', tip: 'Mesh properties…', action: 'meshSettings' }, '-');
    }
    
    /* File > Export model... is inert in the frozen mockup: js/data.js:99 gives the
       item no `action`, so App.runAction only logs that it is not implemented. It
       has one now, and the wrapper below picks it up. */
    var fileMenu = App.MENUS.find(function (m) { return m.label === 'File'; });
    if (fileMenu) {
      fileMenu.items.forEach(function (item) {
        if (item && item.label === 'Export model…' && !item.action) {
          item.action = 'exportModel';
        }
      });
      if (!fileMenu.items.some(function (item) { return item && item.action === 'importMdpa'; })) {
        // Belongs beside Export model -- the same File > Print/Export group -- not
        // tacked on after Exit, which is where a plain push would leave it.
        var exportAt = fileMenu.items.findIndex(function (item) {
          return item && item.action === 'exportModel';
        });
        var at = exportAt === -1 ? fileMenu.items.length : exportAt + 1;
        fileMenu.items.splice(at, 0,
          { label: 'Import mesh (.mdpa)…', icon: 'open', action: 'importMdpa' });
      }
    }

    // Add Import model to Structures menu
    var structuresMenu = App.MENUS.find(function(m) { return m.label === 'Structures'; });
    if (structuresMenu && !structuresMenu.items.some(function (item) { return item && item.action === 'importModel'; })) {
      structuresMenu.items.push('-');
      structuresMenu.items.push({ label: 'Import model…', icon: 'open', action: 'importModel' });
      structuresMenu.items.push({ label: 'Create box', icon: 'cube', action: 'drawBox' });
      structuresMenu.items.push({ label: 'Create cylinder', icon: 'cylinder', action: 'drawCylinder' });
    }
    
    // A custom soil volume belongs with the other soil tools.
    if (App.RAILS.soil && !App.RAILS.soil.some(function (tool) {
      return tool && tool.action === 'createSoilVolume';
    })) {
      App.RAILS.soil.push('-');
      App.RAILS.soil.push({ icon: 'cube', tip: 'Create soil volume…', action: 'createSoilVolume' });
    }
    var soilMenu = (App.MENUS || []).filter(function (m) { return m.label === 'Soil'; })[0];
    if (soilMenu && !soilMenu.items.some(function (i) { return i && i.action === 'createSoilVolume'; })) {
      soilMenu.items.push('-');
      soilMenu.items.push({ label: 'Create soil volume…', icon: 'cube', action: 'createSoilVolume' });
    }

    // Add Import model to Structures rail
    if (App.RAILS.structures) {
      App.RAILS.structures.forEach(function(tool) {
        if (!tool || !tool.icon) return;
        if (tool.icon === 'point') tool.action = 'drawPoint';
        if (tool.icon === 'line') tool.action = 'drawLine';
        if (tool.icon === 'polygon') tool.action = 'drawPolygon';
        // The frozen rail drew an interface button but had nothing to hang on it.
        if (tool.icon === 'interface') tool.action = 'interface';
        if (tool.icon === 'load') {
          tool.action = 'createLoad';
          (tool.flyout || []).forEach(function (item) {
            item.action = 'createLoad';
            item.loadKind = /point/i.test(item.label) ? 'point'
              : (/line/i.test(item.label) ? 'line' : 'surface');
          });
        }
      });
      
      // A sheet-pile tool of its own: the frozen rail has no structural-member
      // action, only the aggregate wall the mockup drew from constants.
      if (!App.RAILS.structures.some(function (tool) {
        return tool && tool.action === 'createSheetPile';
      })) {
        // One button for the wall of whichever dimension is open, with the corner
        // flyout naming both kinds outright: `beamKind` is what the click carries
        // through to App.Beams.start, and a kind the model cannot hold refuses
        // itself with a reason rather than being hidden.
        App.RAILS.structures.push({ icon: 'wall', tip: 'Create sheet pile…',
                                    action: 'createSheetPile', flyout: [
          { icon: 'wall', label: 'Sheet pile (2D section)',
            action: 'createSheetPile', beamKind: 'beam' },
          { icon: 'wall', label: 'Wall panel (3D)',
            action: 'createSheetPile', beamKind: 'panel' },
          { icon: 'beam', label: 'Member (3D)', action: 'createMember' } ] });
      }

      if (!App.RAILS.structures.some(function (tool) {
        return tool && tool.action === 'createMember';
      })) {
        App.RAILS.structures.push({ icon: 'beam', tip: 'Create member…',
                                    action: 'createMember' });
      }

      if (!App.RAILS.structures.some(function (tool) {
        return tool && tool.action === 'createAnchor';
      })) {
        App.RAILS.structures.push({ icon: 'anchor', tip: 'Create anchor…',
                                    action: 'createAnchor' });
      }

      if (!App.RAILS.structures.some(function (tool) { return tool && tool.action === 'importModel'; })) {
        App.RAILS.structures.push({ icon: 'open', tip: 'Import model…', action: 'importModel' });
        App.RAILS.structures.push({ icon: 'cube', tip: 'Create box', action: 'drawBox' });
      }

      // Everything above appends; this is what puts the rail back in order.
      App.RAILS.structures = orderStructuresRail(App.RAILS.structures);
    }

    if (structuresMenu) {
      structuresMenu.items.forEach(function (item) {
        if (item && item.label === 'Create load') {
          item.action = 'createLoad';
          item.sub = false;
        }
      });
      if (!structuresMenu.items.some(function (item) {
        return item && item.action === 'createSheetPile';
      })) {
        structuresMenu.items.push({ label: 'Create sheet pile',
                                    action: 'createSheetPile', sub: false });
      }
      if (!structuresMenu.items.some(function (item) {
        return item && item.action === 'createMember';
      })) {
        structuresMenu.items.push({ label: 'Create member',
                                    action: 'createMember', sub: false });
      }
      if (!structuresMenu.items.some(function (item) {
        return item && item.action === 'createAnchor';
      })) {
        structuresMenu.items.push({ label: 'Create anchor',
                                    action: 'createAnchor', sub: false });
      }
      // The frozen menu already names the interface; it just never did anything.
      structuresMenu.items.forEach(function (item) {
        if (item && item.label === 'Create interface') {
          item.action = 'interface';
          item.sub = false;
        }
      });
      if (!structuresMenu.items.some(function (item) {
        return item && item.action === 'interface';
      })) {
        structuresMenu.items.push({ label: 'Create interface',
                                    action: 'interface', sub: false });
      }
    }

    // Model explorer: enable Delete for drawn/imported geometry (see onTreeContextMenu).
    if (App.Explorer && App.Explorer.mountTree) {
      var frozenMountTree = App.Explorer.mountTree;
      App.Explorer.mountTree = function (mode) {
        frozenMountTree(mode);
        tagTreeRowsWithObjKeys(mode);
      };
    }
    if (typeof document !== 'undefined') {
      var treeHost = document.getElementById('tree-model');
      if (treeHost) treeHost.addEventListener('contextmenu', onTreeContextMenu, true);
    }

    var frozenRun = App.Command.run;
    App.Command.run = function (text) {
      if (App.DrawInput && App.DrawInput.handleCommand(text)) return;
      
      var cmd = (text || '').trim().split(/\s+/)[0].toLowerCase();
      if (cmd === 'cleargeometry') {
        if (App.Command.note) App.Command.note('Clearing custom geometry...');
        fetch(App.Api.base + '/api/project/custom_parts', { method: 'DELETE' })
          .then(function() { return App.Model.load(); })
          .then(function() { return App.Viewport.refresh(); })
          .then(function() {
             if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
             if (App.Command.ok) App.Command.ok('Custom geometry cleared.');
          });
        return;
      }
      
      if (cmd === 'export') {
        if (App.Command.write) App.Command.write('echo', '> ' + text.trim());
        if (App.Export) App.Export.run();
        return;
      }

      if (/^_?mesh(?:\s|$)/i.test((text || '').trim())) {
        requestMesh(false, text.trim());
        return;
      }
      return frozenRun(text);
    };

    if (App.Dialogs && App.Dialogs.soilLayers) {
      var frozenSoilLayers = App.Dialogs.soilLayers;
      App.Dialogs.soilLayers = function () {
        var snapshot = snapshotSoil();
        frozenSoilLayers();
        var dialogs = document.querySelectorAll('#modal-layer .dialog');
        var dialog = dialogs[dialogs.length - 1];
        if (!dialog) return;
        activeLayerEdit = { snapshot: snapshot, dialog: dialog, committed: false };
        addSoilBodySection(dialog);

        dialog.addEventListener('click', function (event) {
          if (event.target.closest('.dlg-x') && activeLayerEdit && !activeLayerEdit.committed) {
            restoreSoil(activeLayerEdit.snapshot);
            activeLayerEdit = null;
          }
        }, true);

        var buttons = dialog.querySelectorAll('.dlg-foot .btn');
        Array.prototype.forEach.call(buttons, function (oldButton) {
          var button = oldButton.cloneNode(true); // strips the frozen close/update listener
          oldButton.parentNode.replaceChild(button, oldButton);
          if (button.textContent.trim() === 'Cancel') {
            button.addEventListener('click', function () {
              restoreSoil(activeLayerEdit ? activeLayerEdit.snapshot : snapshot);
              var close = dialog.querySelector('.dlg-x');
              activeLayerEdit = null;
              close.click();
            });
          } else if (button.textContent.trim() === 'OK') {
            button.addEventListener('click', function () {
              Array.prototype.forEach.call(dialog.querySelectorAll('.dlg-foot .btn'), function (b) {
                b.disabled = true;
              });
              App.Api.patch('/api/project/layers', { layers: copy(App.LAYERS),
                                                     materials: App.Model.materialsToServer(App.MATERIALS),
                                                     boreholes: copy(App.BOREHOLES) })
                .then(function (response) {
                  App.Model.apply(response.project);
                  return App.Viewport.refresh();
                })
                .then(function () {
                  App.Command.ok('Soil layers updated — ' + App.LAYERS.length + ' layers, '
                                 + App.BOREHOLES.length + ' boreholes. Geometry regenerated.');
                  if (activeLayerEdit) activeLayerEdit.committed = true;
                  dialog.querySelector('.dlg-x').click();
                  activeLayerEdit = null;
                })
                .catch(function (error) {
                  Array.prototype.forEach.call(dialog.querySelectorAll('.dlg-foot .btn'), function (b) {
                    b.disabled = false;
                  });
                  if (App.Command.err) App.Command.err(error.message);
                  else App.Command.write('err', error.message);
                });
            });
          }
        });
      };
    }

    /* Edits made straight from the Model/Selection explorer — a layer deleted or
       renamed from the tree, a material reassigned, a level or a domain extent
       typed into the property grid. The frozen hook only refreshes the browser;
       here the soil model goes to the server as one request, because the layers,
       the boreholes and the domain are validated together. A rejected write is
       rolled back by re-reading the stored project, so the grid can never keep
       showing a value the model does not hold. */
    App.commitSelectionEdit = function (objKey) {
      var reselect = objKey === undefined ? App.state.selection : objKey;

      if (App.Loads && App.Loads.isLoadKey(reselect)) {
        var load = (App.LOADS || []).filter(function (item) { return item.id === reselect; })[0];
        if (load) return App.Loads.save(load);
      }

      if (App.Beams && App.Beams.isBeamKey(reselect)) {
        var beam = (App.BEAMS || []).filter(function (item) { return item.id === reselect; })[0];
        // The section rows edit the shared profile in place, so the whole library
        // travels with the pile: that is the write the server validates as one.
        if (beam) return App.Beams.save(beam, copy(App.BEAM_SECTIONS || []));
      }

      if (App.Anchors && App.Anchors.isAnchorKey(reselect)) {
        var anchor = (App.ANCHORS || []).filter(function (item) {
          return item.id === reselect;
        })[0];
        if (anchor) return App.Anchors.save(anchor, copy(App.ANCHOR_SECTIONS || []));
      }

      if (App.Interfaces && App.Interfaces.isInterfaceKey(reselect)) {
        var contact = (App.INTERFACES || []).filter(function (item) {
          return item.id === reselect;
        })[0];
        // Same as the pile: the Contact rows edit the shared property set in place,
        // so the whole library rides along in the one validated write.
        if (contact) return App.Interfaces.save(contact, copy(App.INTERFACE_SECTIONS || []));
      }

      function remount() {
        App.Explorer.mountTree(App.state.mode);
        App.Explorer.mountSelection(reselect);
      }

      return App.Api.patch('/api/project/layers', {
        layers: copy(App.LAYERS),
        boreholes: copy(App.BOREHOLES),
        domain: copy(App.Model.pendingDomain()),
        custom_parts: copy((App.PROJECT && App.PROJECT.custom_parts) || [])
      })
        .then(function (response) {
          App.Model.apply(response.project);
          return App.Viewport.refresh();
        })
        .then(remount)
        .catch(function (error) {
          if (App.Command.err) App.Command.err(error.message);
          else App.Command.write('err', error.message);
          return App.Model.load().then(function () {
            return App.Viewport.refresh();
          }).then(remount);
        });
    };

    /* Material sets: the frozen dialog edits App.MATERIALS in place and its OK
       only refreshes the browser's own copy. Send the library to the server
       instead, then take the stored project back. */
    if (App.Dialogs && App.Dialogs.materials) {
      var frozenMaterials = App.Dialogs.materials;
      App.Dialogs.materials = function (onClose) {
        var snapshot = copy(App.MATERIALS || []);
        frozenMaterials(onClose);
        var dialogs = document.querySelectorAll('#modal-layer .dialog');
        var dialog = dialogs[dialogs.length - 1];
        if (!dialog) return;

        var committed = false;
        function discard() {
          App.MATERIALS = copy(snapshot);
          if (App.Model && App.Model.rebuildDerived) App.Model.rebuildDerived();
          if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
        }

        dialog.addEventListener('click', function (event) {
          if (event.target.closest('.dlg-x') && !committed) discard();
        }, true);

        Array.prototype.forEach.call(dialog.querySelectorAll('.dlg-foot .btn'), function (oldButton) {
          var button = oldButton.cloneNode(true); // strips the frozen commit listener
          oldButton.parentNode.replaceChild(button, oldButton);
          var label = button.textContent.trim();

          if (label === 'Cancel') {
            button.addEventListener('click', function () {
              discard();
              dialog.querySelector('.dlg-x').click();
            });
            return;
          }
          if (label !== 'OK') return;

          button.addEventListener('click', function () {
            Array.prototype.forEach.call(dialog.querySelectorAll('.dlg-foot .btn'), function (b) {
              b.disabled = true;
            });

            /* This dialog can be opened from inside the soil-layer dialog. Both
               Model.apply and refresh() overwrite App.LAYERS/App.BOREHOLES from
               the server, which would silently throw away soil edits the user
               has not committed yet -- so hold them and put them back. */
            var pending = activeLayerEdit ? snapshotSoil() : null;

            App.Api.patch('/api/project/materials',
                          { materials: App.Model.materialsToServer(App.MATERIALS) })
              .then(function (response) {
                App.Model.apply(response.project);
                return App.Viewport.refresh();
              })
              .then(function () {
                if (pending) restoreSoil(pending);
                App.Command.ok('Material sets saved — ' + App.MATERIALS.length
                               + ' soil materials. Geometry regenerated.');
                committed = true;
                dialog.querySelector('.dlg-x').click();
              })
              .catch(function (error) {
                Array.prototype.forEach.call(dialog.querySelectorAll('.dlg-foot .btn'), function (b) {
                  b.disabled = false;
                });
                if (App.Command.err) App.Command.err(error.message);
                else App.Command.write('err', error.message);
              });
          });
        });
      };
    }

    if (typeof document !== 'undefined') {
      var status = document.getElementById('statusbar');
      if (status && !document.getElementById('sb-server')) {
        var connection = document.createElement('span');
        connection.id = 'sb-server'; connection.className = 'sb-item';
        connection.textContent = 'Server: checking…';
        status.insertBefore(connection, status.querySelector('.sb-spacer'));
        App.Api.get('/api/health').then(function (health) {
          connection.textContent = 'Server: online · gmsh ' + health.gmsh_version;
          connection.classList.add('active');
        }).catch(function () {
          connection.textContent = 'Server: offline';
          connection.classList.remove('active');
        });
      }
      /* The shortcuts js/data.js prints next to the menu items it never wired up.
         Ctrl+N and Ctrl+O are the browser's own in most builds and cannot always be
         taken; the menu and the toolbar are the reliable route to those two. */
      document.addEventListener('keydown', function (event) {
        if (!event.ctrlKey || event.altKey) return;
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'SELECT') return;
        var key = event.key.toLowerCase();
        var action = key === 'z' ? (event.shiftKey ? 'redo' : 'undo')
                   : key === 'y' ? 'redo'
                   : key === 's' ? 'saveProject'
                   : key === 'o' ? 'openProject'
                   : key === 'n' ? 'newProject' : null;
        if (!action) return;
        event.preventDefault();
        App.runAction({ action: action });
      });

      // The command module's input handler calls a private `run`, so intercept the one
      // live command whose frozen callback contains invented mesh counts.
      document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && activeLayerEdit && !activeLayerEdit.committed) {
          // activeLayerEdit.snapshot is a {layers, boreholes} pair, not a bare array.
          restoreSoil(activeLayerEdit.snapshot);
          activeLayerEdit = null;
        }
        var entry = document.getElementById('cmd-entry');
        if (event.key === 'Enter' && event.target === entry
            && /^_?mesh(?:\s|$)/i.test(entry.value.trim())) {
          event.preventDefault(); event.stopImmediatePropagation();
          var text = entry.value.trim(); entry.value = '';
          App.Command.run(text);
          return;
        }
        // The frozen shell double-books F9 as Calculate. In Mesh mode it means mesh.
        if (event.key === 'F9' && event.target.tagName !== 'INPUT'
            && event.target.tagName !== 'SELECT' && App.state.mode === 'mesh') {
          event.preventDefault(); event.stopImmediatePropagation();
          App.runAction({ action: 'generateMesh' });
        }
      }, true);
    }
  }

  function resetForTests() {
    installed = false;
    inFlight = false;
    modeInFlight = false;
    activeLayerEdit = null;
  }

  return {
    install: install, meshSummary: meshSummary,
    snapshotLayers: snapshotLayers, restoreLayers: restoreLayers,
    snapshotSoil: snapshotSoil, restoreSoil: restoreSoil, pitRefinement: pitRefinement,
    isDeletableCustomPart: isDeletableCustomPart, tagTreeRowsWithObjKeys: tagTreeRowsWithObjKeys,
    MODES: MODES, patchFor: patchFor, sectionLabel: sectionLabel,
    missingViewportApi: missingViewportApi, staleMessage: staleMessage,
    reportUncaught: reportUncaught,
    setModelMode: setModelMode, syncModelMode: syncModelMode, syncViewMode: syncViewMode,
    THREE_D_ONLY: THREE_D_ONLY, availableIn2D: availableIn2D,
    TWO_D_ONLY: TWO_D_ONLY, availableIn3D: availableIn3D,
    syncDimensionAvailability: syncDimensionAvailability, syncHistoryButtons: syncHistoryButtons,
    newProject: newProject, openProject: openProject, saveProject: saveProject,
    projectFileName: projectFileName, projectFromFileText: projectFromFileText,
    projectNameFromFile: projectNameFromFile,
    setNavigation: setNavigation, gateRail: gateRail,
    rulersOn: rulersOn, toggleRulers: toggleRulers, applyRulers: applyRulers,
    orderStructuresRail: orderStructuresRail,
    STRUCTURES_RAIL_GROUPS: STRUCTURES_RAIL_GROUPS,
    nameSoilBodyActions: nameSoilBodyActions,
    addSoilBodySection: addSoilBodySection,
    deleteCustomPart: deleteCustomPart, onTreeContextMenu: onTreeContextMenu,
    objectKind: objectKind, renameObject: renameObject, deleteObject: deleteObject,
    resetForTests: resetForTests
  };
})();

App.LivePatches.install();
