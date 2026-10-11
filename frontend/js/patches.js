/* Live-only overlays for behavior that is closed over inside the frozen scripts. */

var App = window.App || {};

App.LivePatches = (function () {
  var installed = false;
  var inFlight = false;

  /* The command box's own recall, and the guard that keeps a second install() from
     binding a second Enter handler onto the same box -- which would run every command
     twice. Module scope, because install() may be called more than once (the tests do)
     and neither may be reset when it is. */
  var cmdHistory = [], cmdIndex = 0, commandBoxBound = false;
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
      z_min: project.excavation.z0, z_max: project.excavation.z1,
      y_min: project.domain.y_bottom, y_max: project.domain.y_top
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

  /* A deck case's own mesh, on the Mesh tab, with every one of its parts listed in the
     Model explorer under "Imported mesh" -- what the .mdpa import's checklist leads to
     once accepted, without the checklist: a case is opened to be looked at whole.
     What is listed and said is App.Deck's (frontend/js/deck.js). */
  function showDeck(mesh, project) {
    if (App.state.mode !== 'mesh') App.setMode('mesh');
    App.Viewport.showImportedMesh(mesh);
    App.Model.setImportedParts(App.Deck.parts(mesh));
    App.Command.ok(App.Deck.summary(mesh, project.name));
    var stages = (project.phases || []).length;
    if (stages) {
      App.Command.note('Its ' + stages + ' stages are the phases on the Staged '
        + 'construction tab, read from the deck: select one to see the parts it has.');
    }
    App.Command.note('Calculate (F9) runs the deck as it is; `results` then reads back '
      + 'what it wrote.');
  }

  /* Model explorer: "Delete" for drawn/imported geometry.

     js/explorer.js:91 hard-codes { label: 'Delete', disabled: true } on every tree
     context menu -- the frozen mockup never had anything real to delete. A custom part
     does, so its row gets a second, capturing 'contextmenu' listener that runs before
     the frozen one (stopping it) and opens the same menu with Delete wired up instead. */

  /* Switch between the solid model and the plane-strain x-y section.

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
      viewport: 'elevation' },
    { id: '3d', label: '3D', icon: 'cube', action: 'viewMode3D',
      viewport: 'solid' }
  ];

  /* The mode the app opens in, matching the document the server opens on
     (core/model/seed.py blank_project). This is a 2D modeller first. */
  var DEFAULT_MODEL_MODE = '2d';

  var modeInFlight = false;

  function modeDef(id) {
    return MODES.filter(function (m) { return m.id === id; })[0] || MODES[1];
  }

  function patchFor(id) {
    return modeDef(id).id === '2d' ? { dimension: 2 } : { dimension: 3 };
  }

  /* "z = -12.5" -- the axis the cut travels along, which is always z now that a 2D
     model is the x-y plane, plus where it sits. */
  function sectionLabel(project) {
    var offset = project && project.section_offset;
    return 'z = ' + (typeof offset === 'number' ? offset : '?');
  }

  /* Ask the server for a mode. Explicit rather than a toggle, because each button
     names its own target: pressing the mode you are already in should cost nothing,
     and a rebuild of the whole model is not nothing. */
  function setModelMode(id) {
    var def = modeDef(id);
    var already = (App.state.modelMode || DEFAULT_MODEL_MODE) === def.id;
    if (modeInFlight || already) return Promise.resolve();
    modeInFlight = true;

    return App.Api.patch('/api/project/dimension', patchFor(def.id))
      .then(function (result) {
        // Through App.Model.apply, the funnel App.History records from: the switch
        // rewrites loads and walls, so it is an edit Undo has to be able to take back.
        // Assigned straight to App.PROJECT it left the history nothing to undo.
        App.Model.apply(result.project);
        App.state.modelMode = def.id;
        App.state.dimension = def.id === '2d' ? 2 : 3;
        syncModelMode(def.id);
        App.Viewport.setViewMode(def.viewport);
        App.Command.note(def.id === '2d'
          ? 'Switched to 2D — a plane-strain cross-section at ' + sectionLabel(result.project)
            + '. Geometry and mesh are rebuilt in the x-y plane.'
          : 'Switched to 3D — the full solid model.');
        // A load changes shape with the dimension: a pressure over a footprint in the
        // solid model is a pressure per metre run in the cut, and the server translates
        // between them (core/model/loads.py). It says what it did to each one, and a
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

  /* The opening mode, applied before anything has been fetched. Waiting for the first
     /api/geometry to gate the chrome would show the 3D toolbar, rail, menus and view
     cube for as long as that takes, and then take them away -- the app would appear to
     start in 3D and change its mind. Only ever fills a blank: a mode already chosen (a
     test's stub, or a switch that has happened) is left alone.

     The state is seeded now and the DOM gated after boot, because js/app.js mounts the
     toolbar and the rail from its own DOMContentLoaded handler, which is registered
     before this one and so runs before it. */
  function openOnDefaultMode() {
    App.state = App.state || {};
    if (App.state.modelMode) return;
    App.state.modelMode = DEFAULT_MODEL_MODE;
    App.state.dimension = DEFAULT_MODEL_MODE === '2d' ? 2 : 3;
    function gate() { syncModelMode(App.state.modelMode || DEFAULT_MODEL_MODE); }
    if (typeof document === 'undefined') return;
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', gate);
    } else {
      gate();
    }
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
    return 'Stale browser cache: frontend/js/viewport.js is older than frontend/js/patches.js '
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
    if (App.NormalLoads && App.NormalLoads.isNormalLoadKey(key)) return 'normal_load';
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

  function normalLoadByKey(key) {
    return (App.NORMAL_LOADS || []).filter(function (item) { return item.id === key; })[0];
  }

  function objectName(kind, key) {
    var obj = kind === 'part' ? partByKey(key)
      : kind === 'beam' ? beamByKey(key)
      : kind === 'anchor' ? anchorByKey(key)
      : kind === 'interface' ? interfaceByKey(key)
      : kind === 'normal_load' ? normalLoadByKey(key)
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
    if (kind === 'normal_load') {
      var normalLoad = normalLoadByKey(key);
      if (!normalLoad) return;
      normalLoad.name = name;
      return App.NormalLoads.save(normalLoad).catch(reportRenameError);
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
    if (kind === 'normal_load') return App.NormalLoads.remove(key);
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

  /* ── The colour toggle ──────────────────────────────────────────────────
     In Mesh mode every row with meshed parts under it gets a small square beside its
     eye. A click draws those parts in their own colour over the grey mesh (and again
     takes it off); the eye still only shows and hides. A group row (Sheet piles, Soil)
     toggles every part under it and shows half-filled while only some are on.

     The square only acts through `App.PartColors` and `App.Viewport.syncPartColors`,
     the same two things the `colour` command uses, so the tested half decides what
     each click means. Found by walking the rows in the same order as
     `tagTreeRowsWithObjKeys`, for the same reason: the frozen explorer keeps its own
     row-to-node map private. */
  function addPartColorToggles(mode) {
    var host = document.getElementById('tree-model');
    if (!host || !App.PartColors || mode !== 'mesh') return;
    var meshed = App.Viewport.coloredPartKeys ? App.Viewport.coloredPartKeys() : [];
    if (!meshed.length) return;
    var rows = host.querySelectorAll('.tree-row');
    var i = 0;
    (function walk(nodes) {
      (nodes || []).forEach(function (node) {
        var row = rows[i++];
        var keys = App.PartColors.keysUnder(node, meshed);
        if (row && keys.length) addPartColorToggle(row, keys, node);
        else if (row) addPartColorSlot(row);
        walk(node.children || []);
      });
    })((App.TREES && App.TREES[mode]) || []);
    syncPartColorToggles();
  }

  function addPartColorToggle(row, keys, node) {
    var square = document.createElement('span');
    square.className = 'tree-paint';
    square.dataset.keys = keys.join('\n');
    // A single part shows its own colour; a group, the colour of its first member.
    square.style.setProperty('--paint', App.Viewport.partColor(keys[0]) || '#e6194b');
    square.title = keys.length === 1 ? 'Draw this part of the mesh in its own colour'
                                     : 'Draw these ' + keys.length + ' parts in their own colours';
    square.addEventListener('click', function (event) {
      event.stopPropagation();
      var on = App.PartColors.on.toggle(keys);
      App.Viewport.syncPartColors();
      syncPartColorToggles();
      if (App.Command && App.Command.note) {
        App.Command.note((on ? 'Coloured: ' : 'No longer coloured: ')
                         + String(node.label || '').split('  ·  ')[0]);
      }
    });
    var eye = row.querySelector('.tree-eye');
    row.insertBefore(square, eye ? eye.nextSibling : row.firstChild);
  }

  /* An empty square's worth of space, so the labels stay in one column. */
  function addPartColorSlot(row) {
    var slot = document.createElement('span');
    slot.className = 'tree-paint empty-slot';
    var eye = row.querySelector('.tree-eye');
    row.insertBefore(slot, eye ? eye.nextSibling : row.firstChild);
  }

  function syncPartColorToggles() {
    var host = document.getElementById('tree-model');
    if (!host || !App.PartColors) return;
    Array.prototype.forEach.call(host.querySelectorAll('.tree-paint:not(.empty-slot)'), function (square) {
      var state = App.PartColors.on.stateOf(square.dataset.keys.split('\n'));
      square.classList.toggle('on', state === 'on');
      square.classList.toggle('mixed', state === 'mixed');
    });
  }

  /* ── The Model explorer in Staged construction mode ──────────────────────
     The row's checkbox stops being "shown" and becomes "in the model in the selected
     phase". Ticking or unticking edits that phase alone
     (`App.Phases.setActive`); the phases after it inherit the change until one of them
     says otherwise, which is how Kratos runs its stages. Every part keeps its row and
     its checkbox in every phase, so a part an earlier phase took out can be put back
     in any later one -- before this, a switched-off part was not drawn, so in the
     phases after it there was nothing left to click to bring it back.

     A group row (Sheet piles, Soil, Loads) sets every part under it, and shows a dash
     while they differ. A tick a phase inherited rather than set itself is drawn grey,
     so what this phase decided stands out from what it was handed. */
  function addPhaseChecks(mode) {
    var host = document.getElementById('tree-model');
    if (!host || mode !== 'staged' || !App.Phases || !App.PartColors) return;
    if (!selectedPhaseId()) return;
    var stageable = App.Phases.stageableKeys(App.PROJECT);
    var rows = host.querySelectorAll('.tree-row');
    var i = 0;
    (function walk(nodes) {
      (nodes || []).forEach(function (node) {
        var row = rows[i++];
        var keys = App.PartColors.keysUnder(node, stageable);
        if (row && keys.length) addPhaseCheck(row, keys, node);
        walk(node.children || []);
      });
    })((App.TREES && App.TREES[mode]) || []);
    paintPhaseChecks();
  }

  function addPhaseCheck(row, keys, node) {
    var check = document.createElement('span');
    check.className = 'tree-eye phase-check';
    check.dataset.keys = keys.join('\n');
    check.title = 'In the model in the selected phase';
    check.addEventListener('click', function (event) {
      event.stopPropagation();
      var phase = selectedPhaseId();
      if (!phase) return;
      var wanted = App.Phases.stateIn(App.PROJECT, phase, keys) !== 'on';
      var label = String(node.label || keys[0]).split('  ·  ')[0];
      savePhases(App.Phases.setActive(App.PROJECT, phase, keys, wanted),
                 label + (wanted ? ' switched on in ' : ' switched off in ')
                 + (phaseById(phase) || {}).name + '.');
    });
    // In place of the eye, which in this mode would be a second, competing on/off.
    var eye = row.querySelector('.tree-eye');
    if (eye) row.replaceChild(check, eye);
    else row.insertBefore(check, row.firstChild);
  }

  /* After the phase or the sequence changed. The tree is mounted again only when the
     checkboxes have to appear (the first phases were just created) or go (the last
     phase was deleted, so the eyes come back); otherwise they are repainted in place.
     Never called from a mount, so it cannot loop. */
  function syncPhaseChecks() {
    if (typeof document === 'undefined') return;
    var host = document.getElementById('tree-model');
    if (!host || !App.state || App.state.mode !== 'staged') return;
    var phase = selectedPhaseId();
    var present = !!host.querySelector('.phase-check');
    if (!!phase !== present) {
      if (App.Explorer) App.Explorer.mountTree('staged');
      return;
    }
    paintPhaseChecks();
  }

  function paintPhaseChecks() {
    var host = document.getElementById('tree-model');
    if (!host) return;
    var phase = selectedPhaseId();
    Array.prototype.forEach.call(host.querySelectorAll('.phase-check'), function (check) {
      var keys = check.dataset.keys.split('\n');
      var state = phase ? App.Phases.stateIn(App.PROJECT, phase, keys) : 'on';
      check.classList.toggle('off', state === 'off');
      check.classList.toggle('mixed', state === 'mixed');
      check.classList.toggle('inherited', keys.length === 1 && !!phase
        && App.Phases.ownership(App.PROJECT, phase, keys[0]) === 'inherited');
    });
  }

  /* ── Which SubModelParts a node is in ────────────────────────────────────
     `node <id>` writes the node's parts to the command log -- and those of every node
     at its position, which is how the two sides of an interface are told apart. With
     an imported deck on screen it also selects the node there, exactly as clicking it
     does (viewport.js `showNode`); otherwise it asks the open project's deck and marks
     the node on its mesh. Clicking a node is the viewport's own (`pickImportedNode`);
     the arithmetic is `App.NodeParts`'s, tested headless. */

  function runNodeCommand(text) {
    if (!App.NodeParts) return false;
    var parsed = App.NodeParts.parse(text);
    if (parsed === false) return false;
    if (App.Command.write) App.Command.write('echo', '> ' + String(text).trim());
    if (parsed.error) { App.Command.err(parsed.error); return true; }
    App.Viewport.nodeParts()
      .then(function (index) {
        var lines = App.NodeParts.report(index, parsed.id);
        if (App.NodeParts.partsOf(index, parsed.id) === null) {
          App.Command.err(lines[0]);
          return;
        }
        lines.forEach(function (line, i) {
          if (i === 0) App.Command.ok(line); else App.Command.note(line);
        });
        if (App.Viewport.importedNodes && App.Viewport.importedNodes() === index) {
          App.Viewport.showNode(parsed.id);
          return;
        }
        App.Viewport.markNodes(App.NodeParts.samePosition(index, parsed.id)
          .map(function (id) { return index.coords[id]; }));
      })
      .catch(function (error) { App.Command.err(error.message); });
    return true;
  }

  /* `colour ...`, typed. `false` when it is not this command. */
  function runColourCommand(text) {
    if (!App.PartColors) return false;
    var mode = App.state && App.state.mode;
    var answer = App.PartColors.command(text, {
      tree: (App.TREES && App.TREES[mode]) || [],
      meshed: App.Viewport.coloredPartKeys ? App.Viewport.coloredPartKeys() : [],
      on: App.PartColors.on
    });
    if (answer === false) return false;
    if (App.Command.write) App.Command.write('echo', '> ' + String(text).trim());
    if (answer.changed) {
      App.Viewport.syncPartColors();
      syncPartColorToggles();
    }
    var message = answer.message;
    if (answer.ok && answer.changed && mode !== 'mesh') {
      message += ' Coloured parts are drawn on the mesh, in Mesh mode.';
    }
    if (answer.ok) App.Command.ok(message);
    else App.Command.err(message);
    return true;
  }

  /* `water ...`, typed: set, show or remove the project's water level. What to send is
     `App.WaterCommand`'s (tested headless); this sends it and redraws from the project
     the server stored. `false` when it is not this command. */
  function runWaterCommand(text) {
    if (!App.WaterCommand) return false;
    var answer = App.WaterCommand.command(text, {
      water: App.PROJECT ? App.PROJECT.water : null,
      domain: App.PROJECT ? App.PROJECT.domain : null
    });
    if (answer === false) return false;
    if (App.Command.write) App.Command.write('echo', '> ' + String(text).trim());
    if (!answer.ok) { App.Command.err(answer.message); return true; }
    if (!answer.body) { App.Command.note(answer.message); return true; }
    App.Api.put('/api/project/water', answer.body)
      .then(function (result) {
        App.Model.apply(result.project);
        return App.Viewport.refresh();
      })
      .then(function () {
        if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
        App.Command.ok(answer.message);
      })
      .catch(function (error) { App.Command.err(error.message); });
    return true;
  }

  /* `units` / `units <system>`, typed: show the project's unit system, or convert the
     whole project to another one. What to send is `App.Units`'s (tested headless); this
     sends it, redraws from the project the server stored, and prints what the server
     could not convert. `false` when it is not this command. */
  function runUnitsCommand(text) {
    if (!App.Units) return false;
    var answer = App.Units.command(text, App.PROJECT);
    if (answer === false) return false;
    if (App.Command.write) App.Command.write('echo', '> ' + String(text).trim());
    if (!answer.ok) { App.Command.err(answer.message); return true; }
    if (!answer.body) { App.Command.note(answer.message); return true; }
    App.Command.note(answer.message);
    App.Api.patch('/api/project/units', answer.body)
      .then(function (result) {
        App.Model.apply(result.project);
        return App.Viewport.refresh().then(function () { return result; });
      })
      .then(function (result) {
        if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
        (result.notes || []).forEach(function (note) {
          if (App.Command.warn) App.Command.warn(note); else App.Command.note(note);
        });
        App.Command.ok('The project is now in ' + App.Units.title() + '.');
      })
      .catch(function (error) { App.Command.err(error.message); });
    return true;
  }

  /* DELETE `path`, rejecting with the server's own `detail` when it refuses. A part a
     phase still uses is refused with a sentence naming the phase (backend/main.py
     `_without_custom_parts`), and that sentence is the whole of what the user needs. */
  function deleteRequest(path, fallback) {
    return fetch(App.Api.base + path, { method: 'DELETE' }).then(function (res) {
      if (res.ok) return res.json();
      return res.json().catch(function () { return {}; }).then(function (body) {
        throw new Error(typeof body.detail === 'string' ? body.detail : fallback);
      });
    });
  }

  function deleteCustomPart(key) {
    if (App.Command && App.Command.note) App.Command.note('Deleting ' + key + '…');
    return deleteRequest('/api/geometry/parts/' + encodeURIComponent(key), 'Delete failed')
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
            return deleteRequest('/api/geometry/parts/' + encodeURIComponent(selected),
                                 'Could not delete the custom layer.')
              .then(function () { return App.Model.load(); })
              .then(function () { return App.Viewport.refresh(); }).then(refreshBodies);
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

  /* "Properties…" has been on this menu since the frozen mockup drew it, and did
     nothing for any kind: the callback below handled delete, rename and the eye, and
     let every other label fall off the end. A kind with a form of its own opens it --
     the same form the tool and the panel's Edit button open. The rest have no form;
     they keep their properties in the Selection explorer, so selecting the object is
     what "properties" means for them, and is at least what the label promises. */
  function openProperties(kind, key) {
    var owner = kind === 'load' ? App.Loads
      : kind === 'normal_load' ? App.NormalLoads
      : kind === 'beam' ? App.Beams : null;
    // Anchors and interfaces are deliberately not here: their `edit` saves the record
    // rather than opening anything, so calling it would write, not show.
    if (owner && owner.edit) return owner.edit(key);
    if (App.selectObject) App.selectObject(key, 'tree');
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
      if (/^Properties/.test(it.label)) return openProperties(kind, key);
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
  var TWO_D_ONLY = ['interface', 'createNormalLoad', 'toggleRuler'];

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

  /* The frozen node-to-node anchor tool draws nothing -- frontend/js/anchors.js owns
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
      // A normal load is plane strain like an interface, and carries no loadKind to
      // sort it by -- see TWO_D_ONLY, which gates its menu twin the same way.
      if (item.action === 'createNormalLoad') { item.disabled = !is2d; return; }
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
    // Coloured parts were parts of the document that is no longer open.
    if (App.PartColors) App.PartColors.on.clear();

    /* And a calculation's results, for exactly the same reason as the .mdpa above:
       they belong to the document that produced them. A different project is open
       now, so the contour on screen is of a model nobody has any more -- and because
       it lives in a group of its own, outside `groups`, `App.Viewport.refresh()` does
       not touch it. It would sit there over the new site looking like the new site's
       answer.

       The run itself is only forgotten, not deleted: the directories on disk outlive
       every project, and `results runs` still lists them. */
    if (App.ResultsView) App.ResultsView.clear();
    if (App.Results && App.Results.forget) App.Results.forget();
    // Results mode with nothing to show is a dead end, so leave it -- for the mode a
    // new project opens in anyway.
    if (App.state && App.state.mode === 'results') App.setMode('soil');

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
    // The window is asked for first, before anything is awaited: a browser only
    // offers the save picker while the click that opened the menu still counts as a
    // gesture. Without it Chrome on Windows drops the file into Downloads unasked.
    return App.Download.pickFile(projectFileName(App.PROJECT), 'application/json')
      .then(function (handle) {
        if (handle === App.Download.CANCELLED) return;
        // The server's copy, not the browser's: App.PROJECT is a snapshot from
        // whenever the last request answered, and a save has to be of what is
        // actually modelled.
        return App.Api.get('/api/project').then(function (project) {
          var name = (handle && handle.name) || projectFileName(project);
          return App.Download.write(handle, projectFileName(project),
                                    JSON.stringify(project, null, 2), 'application/json')
            .then(function () {
              if (App.Command) App.Command.ok('Saved ' + name + '.');
            });
        });
      })
      .catch(function (error) {
        if (App.Command) App.Command.err('Could not save the project: ' + error.message);
      });
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
     frontend/js/ruler.js owns the drawing; this owns the switch. The state lives on
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

  /* ══════════════════════════════════════════════════════════════════════════
     Viewport right-click: "Show labels ▸ Node IDs / Element IDs".

     A mesh is read by number -- a solver names node 4711 or element 902, and the only way
     to find it is to see the number on the mesh -- so the numbers belong on the thing
     itself, one right-click away from wherever the reader is already looking. The overlay
     and its arithmetic are frontend/js/mesh-labels.js; this is the way in.
     ══════════════════════════════════════════════════════════════════════════ */

  /* The frozen viewport menu (js/app.js:60) plus the labels row. Kept as a function of
     its own so the row's place in the menu is testable without opening one. */
  function withLabelRows(items) {
    if (!App.MeshLabels) return items;
    return items.concat(['-', App.MeshLabels.menuItem()]);
  }

  var LABEL_NOUNS = { nodes: 'Node', elements: 'Element' };

  /* One toggle per kind, each independent of the other: a node number and the number of
     the element around it are read together as often as apart. */
  function toggleLabels(kind) {
    var noun = LABEL_NOUNS[kind] || 'ID';
    var on = !App.Viewport.labelsOn(kind);
    App.Viewport.setLabels(kind, on, function (count) {
      if (!on) return App.Command.note(noun + ' ID labels hidden.');
      if (count === null) return;                            // already reported
      if (!count) {
        App.Viewport.setLabels(kind, false);
        return App.Command.note(
          'Nothing to label — generate a mesh (F9) or import a .mdpa first.');
      }
      App.Command.note(noun + ' IDs shown: ' + count + ' '
        + (kind === 'elements' ? 'elements' : 'nodes')
        + ', in the numbering the .mdpa is written with. '
        + 'Where they crowd, only the nearest is drawn — zoom in for the rest.');
    });
  }

  /* The frozen menu is *wrapped*, not rewritten: it builds its items in a closure and
     hands them straight to App.Menu.openAt, so lending it a one-shot openAt is what
     lets a row be added without copying the eleven it already has -- and without this
     module having to keep them in step. */
  function extendViewportMenu() {
    var frozen = App.viewportContextMenu;
    if (typeof frozen !== 'function') return;
    App.viewportContextMenu = function (event, key) {
      var openAt = App.Menu.openAt;
      App.Menu.openAt = function (items, x, y, onPick) {
        App.Menu.openAt = openAt;
        openAt(withLabelRows(items), x, y, function (item) {
          if (item && item.action === 'toggleNodeLabels') return toggleLabels('nodes');
          if (item && item.action === 'toggleElementLabels') return toggleLabels('elements');
          if (onPick) onPick(item);
        });
      };
      try {
        frozen(event, key);
      } finally {
        App.Menu.openAt = openAt;
      }
    };
  }

  /* ── The phases panel ────────────────────────────────────────────────────
     `Explorer.mountPhases` (js/explorer.js:281) already draws everything the
     screenshots show: an indented list, a state dot per row, and a property grid for
     the selected phase. What it draws them from is `App.PHASES`, seven hardcoded rows
     in js/data.js:559 describing a project nobody has open -- so the panel was a
     picture of a phase list rather than a phase list.

     Replaced wholesale rather than patched around, because almost every line of it
     reads the frozen globals. What is kept is the markup and the class names, which
     is what the stylesheet is written against (css/components.css:214-226).

     `App.Phases` is the model; this is only the drawing and the buttons. Every edit
     goes the same way round: build a new list, PATCH it, take the stored project
     back. Nothing is mutated in place, so a rejected save leaves the panel showing
     what the server actually holds rather than what the user hoped for. */

  /* What the last calculation reported, for the state dots. `{completed: n}`, worked
     out from the stage the run died in: everything before it finished. A run that
     succeeded completed all of them; a run that never reached a stage completed
     none. Cleared when the phase list changes, because a dot describing a sequence
     that no longer exists is worse than a grey one. */
  var phaseRun = null;

  function rememberRun(result) {
    var total = ((App.PROJECT && App.PROJECT.phases) || []).length;
    if (!result) { phaseRun = null; }
    else if (result.ok) { phaseRun = { completed: total }; }
    else if (result.stage) {
      phaseRun = { completed: result.stage.index - 1, failed: true,
                   error: result.error || null };
    }
    else { phaseRun = { completed: 0, failed: true, error: result.error || null }; }
    mountLivePhases();
  }

  function selectedPhaseId() {
    var list = (App.PROJECT && App.PROJECT.phases) || [];
    if (!list.length) return null;
    var wanted = App.state && App.state.phase;
    var found = list.filter(function (ph) { return ph.id === wanted; })[0];
    return found ? found.id : list[0].id;
  }

  function phaseById(id) {
    return ((App.PROJECT && App.PROJECT.phases) || []).filter(function (ph) {
      return ph.id === id;
    })[0] || null;
  }

  /* Send a phase list and adopt whatever comes back.

     The server is the authority on what a valid sequence is -- it refuses a branch, a
     part key nothing answers to, and a phase that both activates and deactivates the
     same thing -- so the reply replaces the list rather than the request confirming
     it. On a refusal the project is reloaded, which is what puts the panel back in
     step after an edit that could not be kept. */
  function savePhases(list, note) {
    return App.Api.patch('/api/project/phases', { phases: list })
      .then(function (response) {
        App.Model.apply(response.project);
        // The sequence has changed, so what the last run reached no longer maps onto
        // it. Better a row of grey dots than a green one against a phase that did
        // not exist when the run happened.
        phaseRun = null;
        if (note) App.Command.ok(note);
        mountLivePhases();
        return App.Viewport.refresh();
      })
      .catch(function (error) {
        App.Command.err(error.message);
        return App.Model.load().then(mountLivePhases);
      });
  }

  function phaseToolbar() {
    var el = App.UI.el;
    var icon = App.UI.icon;
    var bar = el('div.dlg-toolbar.phase-toolbar');
    var selected = selectedPhaseId();

    /* The icon row at the top left of the Phases window. `new`/`copy`/`delete`
       are the mockup's own icon names (js/data.js:63-76); `phase` stands in for
       insert, which has no icon of its own in the frozen set. */
    [['new', 'Add phase', function () {
        return App.Phases.added(App.PROJECT);
      }, 'Phase added.'],
     ['phase', 'Insert phase above the selected one', function () {
        return selected ? App.Phases.inserted(App.PROJECT, selected) : null;
      }, 'Phase inserted.'],
     ['copy', 'Duplicate the selected phase', function () {
        return selected ? App.Phases.copied(App.PROJECT, selected) : null;
      }, 'Phase duplicated.'],
     ['delete', 'Delete the selected phase', function () {
        return selected ? App.Phases.removed(App.PROJECT, selected) : null;
      }, 'Phase deleted.']
    ].forEach(function (spec) {
      var button = el('button.tbtn', { type: 'button' });
      button.appendChild(icon(spec[0]));
      App.UI.attachTip(button, spec[1]);
      button.disabled = spec[0] !== 'new' && !selected;
      button.addEventListener('click', function () {
        App.UI.hideTip();
        var list = spec[2]();
        if (!list) { App.Command.err('Select a phase first.'); return; }
        savePhases(list, spec[3]);
      });
      bar.appendChild(button);
    });

    bar.appendChild(el('span.tbsep'));

    var dialog = el('button.btn.btn-sm', { text: 'Phases…', type: 'button' });
    dialog.addEventListener('click', function () { phasesDialog(); });
    bar.appendChild(dialog);

    return bar;
  }

  /* The empty state, which is the one every project starts in.

     A panel with nothing in it and no way out of it would be the commonest thing
     anybody sees, so it carries the button that fills it. `default_phases` on the
     server builds the sequence -- settle, build, then alternate digging and propping
     -- from the model as it stands, which for a staged excavation is its seven
     stages exactly. */
  function emptyPhaseState() {
    var el = App.UI.el;
    var wrap = el('div.lay-hint', { style: 'padding:10px' });
    wrap.appendChild(el('div', { text:
      'This project has no construction sequence: it exports as a single stage, ' +
      'the way it always has.' }));
    var button = el('button.btn.btn-sm', {
      text: 'Create default phases', type: 'button',
      style: 'margin-top:8px'
    });
    button.addEventListener('click', function () {
      App.Api.post('/api/project/phases/defaults', {})
        .then(function (response) {
          App.Model.apply(response.project);
          App.Command.ok('Created ' + response.project.phases.length +
                         ' phases from the model. Edit them in the Phases panel.');
          mountLivePhases();
          return App.Viewport.refresh();
        })
        .catch(function (error) { App.Command.err(error.message); });
    });
    wrap.appendChild(button);
    return wrap;
  }

  /* Clicking a part in staged mode switches it on or off for the selected phase.

     Which is the behaviour the first screenshot shows, and the reason staged mode
     exists as a mode rather than a filter. Wrapped around `App.selectObject` rather
     than bound to the canvas, because that is the one funnel every pick already goes
     through -- viewport click, context menu and tree row alike -- so a part cannot be
     toggled by one route and merely selected by another.

     Selection still happens. Toggling instead of selecting would leave the property
     panel showing whatever was picked last, which is how you end up editing the wrong
     load; and the panel is the only place the part's name is written down. */
  function togglePartForPhase(key) {
    var phase = selectedPhaseId();
    if (!phase) { App.Command.err('Select a phase first.'); return false; }
    if (App.Phases.stageableKeys(App.PROJECT).indexOf(key) < 0) return false;

    var was = (App.Phases.activeParts(App.PROJECT, phase) || []).indexOf(key) >= 0;
    var owned = App.Phases.ownership(App.PROJECT, phase, key);
    var list = App.Phases.toggled(App.PROJECT, phase, key);
    var label = (App.PROJECT.soil_body_labels || {})[key] || key;
    savePhases(list, label + (was ? ' switched off in ' : ' switched on in ') +
                     (phaseById(phase) || {}).name +
                     (owned === 'inherited'
                        ? ' (it was inherited from an earlier phase until now).'
                        : '.'));
    return true;
  }

  function mountLivePhases() {
    if (typeof document === 'undefined') return;
    var host = document.getElementById('list-phases');
    if (!host) return;
    var el = App.UI.el;
    var icon = App.UI.icon;
    App.UI.clear(host);

    host.appendChild(phaseToolbar());

    var phases = (App.PROJECT && App.PROJECT.phases) || [];
    // The Model explorer's checkboxes follow the selected phase. Every route that
    // changes the phase or the sequence comes through here.
    syncPhaseChecks();
    if (!phases.length) {
      host.appendChild(emptyPhaseState());
      return;
    }

    /* A branching tree has no execution order, so it has no stage list and cannot be
       run. Said here, where it can still be fixed, rather than at Calculate -- and
       said without hiding the rows, because the way out of it is to edit one of the
       phases that branch. */
    var problem = App.Phases.branchProblem(App.PROJECT);
    if (problem) {
      host.appendChild(el('div.lay-hint.invalid', { text: problem,
                                                    style: 'padding:6px 10px' }));
    }

    var selected = selectedPhaseId();
    var list = el('div.phase-list');
    App.Phases.rows(App.PROJECT, phaseRun).forEach(function (row) {
      var node = el('div.phase-row' + (row.id === selected ? '.selected' : ''));
      node.style.paddingLeft = (8 + row.depth * 10) + 'px';
      node.appendChild(el('span.phase-dot.' + row.state));
      node.appendChild(el('span.phase-name', { text: row.name }));
      node.appendChild(el('span.phase-kind', { text: row.kind }));
      node.addEventListener('click', function () {
        App.state.phase = row.id;
        mountLivePhases();
        // Staged mode draws the model as of the selected phase, so moving the
        // selection moves the viewport with it.
        if (App.Viewport.applyPhaseVisibility) App.Viewport.applyPhaseVisibility();
        App.Command.note('Current phase: ' + row.name);
      });
      list.appendChild(node);
    });
    host.appendChild(list);

    var phase = phaseById(selected);
    if (!phase) return;
    var grid = el('div.pgrid');
    var head = el('div.pgrid-header');
    head.appendChild(icon('phase'));
    head.appendChild(el('span', { text: phase.name }));
    grid.appendChild(head);
    var groups = phaseProps(phase);
    Object.keys(groups).forEach(function (name) {
      grid.appendChild(el('div.pgrid-group', { text: name }));
      groups[name].forEach(function (row) {
        grid.appendChild(phasePropRow(phase, row));
      });
    });
    host.appendChild(grid);
  }

  /* The property grid for one phase.

     Field names follow the phase panel the frozen mockup already draws
     (js/data.js:569), because that is the UI this feeds. What it does *not* do is
     keep the mockup's rows this exporter has nothing behind -- "Max unloading steps",
     "Arc-length control", "Updated mesh", "Ignore undrained behaviour". A row that
     looks editable and is thrown away on save is worse than an absent one, and the
     three groups below are exactly what `schemas.Phase` carries.

     "Pore pressure calc." stays, read-only, saying what it actually is: the reference
     deck never varies it and a per-phase phreatic level is deliberately out of scope
     (plan sec 7.11). "Global water level" is the honest version of that row. */
  function phaseProps(phase) {
    var parent = phase.parent == null ? null : phaseById(phase.parent);
    return {
      'General': [
        ['Name', 'text', 'name'],
        ['Start from phase', 'static', parent ? parent.name : 'the model as built'],
        ['Calculation type', 'select', 'calculation',
         ['K0 procedure', 'Plastic', 'Null step']],
        ['Loading type', 'static', phase.loading || 'Staged construction'],
        ['Pore pressure calc.', 'static', 'Global water level'],
        ['Time interval', 'number', 'time_interval', { min: 0 }, 'day']
      ],
      'Deformation control': [
        ['Reset displacements to zero', 'check', 'reset_displacements']
      ],
      'Numerical control': [
        ['Max iterations', 'number', 'max_iterations', { min: 1, integer: true }],
        ['Tolerated error', 'number', 'tolerated_error', { exclusiveMin: 0 }]
      ]
    };
  }

  /* One row, and the edit behind it.

     Every committed edit PATCHes the whole phase list, because that is what the
     endpoint takes -- there is no per-field write, and inventing one would be a
     second way for the list to get out of step with the server. The reply replaces
     the list, so a value the server normalises shows the normalised one. */
  function phasePropRow(phase, spec) {
    var el = App.UI.el;
    var label = spec[0], kind = spec[1];
    var key = el('div.pgrid-key', { text: label });

    function commit(value) {
      var list = ((App.PROJECT && App.PROJECT.phases) || []).map(function (each) {
        var edited = copy(each);
        if (each.id === phase.id) edited[spec[2]] = value;
        return edited;
      });
      savePhases(list);
    }

    if (kind === 'static') {
      return el('div.pgrid-row', null,
                [key, el('div.pgrid-val.readonly', { text: String(spec[2]) })]);
    }
    /* A deck case's phases are its stages, read from the deck that Calculate runs
       (core/kratos/deck.py); the server refuses an edit, so none is offered. */
    if (App.PROJECT && App.PROJECT.deck) {
      var shown = phase[spec[2]];
      if (kind === 'check') shown = shown ? 'Yes' : 'No';
      return el('div.pgrid-row', null, [key, el('div.pgrid-val.readonly', {
        text: (shown == null ? '' : String(shown)) + (spec[4] ? ' ' + spec[4] : '')
      })]);
    }

    var control;
    if (kind === 'text') {
      control = el('input.cell-input', { value: phase[spec[2]] || '' });
      control.addEventListener('change', function () {
        var text = control.value.trim();
        if (!text) {
          control.value = phase[spec[2]];
          App.Command.err('A phase name cannot be empty.');
          return;
        }
        commit(text);
      });
    } else if (kind === 'select') {
      control = el('select');
      spec[3].forEach(function (option) {
        var node = el('option', { value: option, text: option });
        if (option === phase[spec[2]]) node.selected = true;
        control.appendChild(node);
      });
      control.addEventListener('change', function () { commit(control.value); });
    } else if (kind === 'check') {
      control = el('input.pgrid-check', { type: 'checkbox' });
      control.checked = !!phase[spec[2]];
      control.addEventListener('change', function () { commit(control.checked); });
    } else {
      var bounds = spec[3] || {};
      control = el('input.cell-input.cell-num', {
        value: String(phase[spec[2]] == null ? '' : phase[spec[2]])
      });
      control.addEventListener('change', function () {
        var value = parseFloat(control.value.trim().replace(',', '.'));
        var problem = null;
        if (!isFinite(value)) problem = label + ' must be a number.';
        else if (bounds.integer && value !== Math.round(value)) {
          problem = label + ' must be a whole number.';
        } else if (bounds.min !== undefined && value < bounds.min) {
          problem = label + ' must be at least ' + bounds.min + '.';
        } else if (bounds.exclusiveMin !== undefined && value <= bounds.exclusiveMin) {
          problem = label + ' must be greater than ' + bounds.exclusiveMin + '.';
        }
        if (problem) {
          control.value = String(phase[spec[2]]);
          App.Command.err(problem);
          return;
        }
        commit(value);
      });
    }

    var cell = el('div.pgrid-val.editable.field', null, [control]);
    if (spec[4]) cell.appendChild(el('span.unit', { text: spec[4] }));
    return el('div.pgrid-row', null, [key, cell]);
  }

  /* ── The Phases dialog ───────────────────────────────────────────────────
     The second screenshot: the full-page phase editor, list on the left and the same
     three groups on the right, larger. Same rows and the same edit path as the panel
     -- it is the same grid given room -- so a phase field is described in one place
     and written one way.

     What the dialog adds is the parts list: what this phase switches on and off,
     which there is no room for beside a 220-pixel dock. */
  function phasesDialog() {
    var el = App.UI.el;
    if (!App.Dialogs || !App.Dialogs.open) {
      App.Command.err('The dialog layer is not available.');
      return;
    }

    var selected = selectedPhaseId();

    App.Dialogs.open({
      title: 'Phases',
      width: Math.min(1180, window.innerWidth - 40),
      height: Math.min(720, window.innerHeight - 40),
      buttons: [{ label: 'Close', primary: true }],
      build: function (body) {
        var wrap = el('div.dlg-simple.phases-overview', {
          style: 'display:flex;gap:12px;padding:0;height:100%'
        });
        var left = el('div.phases-overview-list', {
          style: 'flex:0 0 380px;overflow:auto;border-right:1px solid var(--c-line)'
        });
        var right = el('div', { style: 'flex:1;overflow:auto;padding-right:4px' });
        var log = el('div.phases-overview-log', {
          style: 'flex:0 0 260px;overflow:auto;border-left:1px solid var(--c-line);'
               + 'padding:0 8px'
        });
        wrap.appendChild(left);
        wrap.appendChild(right);
        wrap.appendChild(log);
        body.appendChild(wrap);

        function draw() {
          App.UI.clear(left);
          App.UI.clear(right);
          App.UI.clear(log);

          var phases = (App.PROJECT && App.PROJECT.phases) || [];
          if (!phases.length) {
            right.appendChild(el('p', { text:
              'This project has no phases yet. Close this and use ' +
              '"Create default phases" in the Phases panel.' }));
            return;
          }

          /* One line per phase: status, name, duration,
             the time T reached, the id -- then the calculation type. What each line
             says is App.Phases.overview's (tested headlessly). */
          var overview = App.Phases.overview(App.PROJECT, phaseRun);
          var list = el('div.phase-list');
          overview.forEach(function (row) {
            var node = el('div.phase-row' + (row.id === selected ? '.selected' : ''));
            node.style.paddingLeft = (8 + row.depth * 4) + 'px';
            node.title = row.label + ' · ' + row.kind;
            node.appendChild(el('span.phase-dot.' + row.state));
            node.appendChild(el('span.phase-name', { text: row.label }));
            node.appendChild(el('span.phase-kind', { text: row.kind }));
            node.addEventListener('click', function () {
              selected = row.id;
              App.state.phase = row.id;
              // The viewport follows, as it does from the dock's own list.
              if (App.Viewport.applyPhaseVisibility) App.Viewport.applyPhaseVisibility();
              mountLivePhases();
              draw();
            });
            list.appendChild(node);
          });
          left.appendChild(list);

          var phase = phaseById(selected);
          if (!phase) { selected = phases[0].id; draw(); return; }
          var current = overview.filter(function (row) { return row.id === phase.id; })[0];
          phaseLog(log, current);

          var grid = el('div.pgrid');
          var groups = phaseProps(phase);
          Object.keys(groups).forEach(function (name) {
            grid.appendChild(el('div.pgrid-group', { text: name }));
            groups[name].forEach(function (row) {
              grid.appendChild(phasePropRow(phase, row));
            });
          });
          right.appendChild(grid);

          /* What this phase changes. Read-only here: the way to change it is to
             click the part in the viewport, which is the only place you can see
             which part you are naming. */
          var on = phase.activate || [], off = phase.deactivate || [];
          var active = App.Phases.activeParts(App.PROJECT, phase.id) || [];
          var changes = el('div.pgrid');
          changes.appendChild(el('div.pgrid-group', { text: 'Staged construction' }));
          [['Activated here', on.length ? on.join(', ') : '—'],
           ['Deactivated here', off.length ? off.join(', ') : '—'],
           ['Active in this phase', active.length + ' of ' +
            App.Phases.stageableKeys(App.PROJECT).length + ' parts']
          ].forEach(function (row) {
            changes.appendChild(el('div.pgrid-row', null, [
              el('div.pgrid-key', { text: row[0] }),
              el('div.pgrid-val.readonly', { text: row[1] })
            ]));
          });
          right.appendChild(changes);

          /* The way back. A part this phase has switched off is not drawn in the
             viewport, so it cannot be clicked to bring it back -- which would make
             the toggle one-way, and the mistake unrecoverable without editing the
             phase before it. Listed here with a button each. */
          var hidden = App.PROJECT.deck ? []
            : App.Phases.hiddenKeys(App.PROJECT, phase.id, 'staged');
          if (hidden.length) {
            var back = el('div.pgrid');
            back.appendChild(el('div.pgrid-group', { text: 'Not in the model here' }));
            hidden.forEach(function (key) {
              var label = (App.PROJECT.soil_body_labels || {})[key] || key;
              var button = el('button.btn.btn-sm', { text: 'Switch on', type: 'button' });
              button.addEventListener('click', function () {
                savePhases(App.Phases.toggled(App.PROJECT, phase.id, key),
                           label + ' switched on in ' + phase.name + '.')
                  .then(draw);
              });
              back.appendChild(el('div.pgrid-row', null, [
                el('div.pgrid-key', { text: label }),
                el('div.pgrid-val', null, [button])
              ]));
            });
            right.appendChild(back);
          }

          right.appendChild(el('div.lay-hint', { text: App.PROJECT.deck
            ? 'These phases are the stages of the Kratos deck ' + App.PROJECT.deck.parameters
              + ', shown as they are. Edit the deck to change them, then run its '
              + 'script again.'
            : 'In Staged construction mode, tick or untick a part in the Model ' +
              'explorer to put it in or take it out of the selected phase. The ' +
              'phases after it follow until one of them changes it again.' }));
        }

        draw();
      }
    });
  }

  /* The Phases window has three ways in, all the one action: a button on the Staged
     construction rail (beside Calculate), the Phases menu's "Edit phases…" -- which
     the frozen mockup draws and wires to nothing -- and `phases` on the command line. */
  function installPhasesOverview() {
    var staged = App.RAILS && App.RAILS.staged;
    if (staged && !staged.some(function (tool) { return tool && tool.action === 'phases'; })) {
      var at = staged.length;
      staged.forEach(function (tool, i) { if (tool && tool.action === 'calculate') at = i; });
      staged.splice(at, 0, { icon: 'phase', tip: 'Phases overview…', action: 'phases' });
    }
    (App.MENUS || []).forEach(function (menu) {
      (menu.items || []).forEach(function (item) {
        if (item && item.label === 'Edit phases…') item.action = 'phases';
      });
    });
  }

  /* The right-hand column of the Phases window: what the last calculation made of
     the selected phase, and the time it reaches -- the "Log info for last
     calculation" and "Reached values". Only what this app knows: a Kratos run says
     whether each stage finished, not reached forces or safety factors. */
  function phaseLog(host, row) {
    var el = App.UI.el;
    if (!row) return;
    host.appendChild(el('div.pgrid-group', { text: 'Log info for last calculation' }));
    var box = el('div.phases-overview-box.' + row.state, { text: row.log });
    host.appendChild(box);
    if (row.state === 'failed' && phaseRun && phaseRun.error) {
      host.appendChild(el('pre.phases-overview-error', { text: phaseRun.error }));
    }
    var reached = el('div.pgrid');
    reached.appendChild(el('div.pgrid-group', { text: 'Reached values' }));
    [['Phase', row.number + ' of ' + ((App.PROJECT.phases || []).length)],
     ['Time interval', row.interval + ' day'],
     ['Reached total time', row.total + ' day']
    ].forEach(function (pair) {
      reached.appendChild(el('div.pgrid-row', null, [
        el('div.pgrid-key', { text: pair[0] }),
        el('div.pgrid-val.readonly', { text: pair[1] })
      ]));
    });
    host.appendChild(reached);
  }

  /* ── The Results explorer's own collapse ────────────────────────────
     Every other dock panel collapses by its header, wired by `js/ui.js`. That one
     works off DOCK_ROWS, which lists the three panels the frozen page has -- and a
     panel missing from it gets no handler at all, so the Results explorer drew a
     caret that did nothing. It is live-only markup (frontend/index.html), so it is wired
     here rather than by widening a frozen table.

     It needs no grid row of its own on the way: `#dock`'s `grid-template-rows` stops
     at the phases panel, so this one already sits in an implicit `auto` row that
     shrinks to the header as soon as `.collapsed` hides the body. */
  function resultsCaret(panel) {
    var caret = panel.querySelector('.dock-caret');
    if (caret) caret.textContent = panel.classList.contains('collapsed') ? '▸' : '▾';
  }

  function collapsibleResultsPanel(dock) {
    var panel = dock && dock.querySelector('#panel-results');
    var head = panel && panel.querySelector('.dock-head');
    // install() may run more than once; a second handler would toggle it straight back.
    if (!head || head.__resultsCollapse) return;
    head.__resultsCollapse = true;
    head.addEventListener('click', function () {
      panel.classList.toggle('collapsed');
      resultsCaret(panel);
    });
    resultsCaret(panel);
  }

  function install() {
    if (installed || typeof App.runAction !== 'function' || !App.Command) return;
    installed = true;

    /* Results-mode state, declared here rather than beside the functions that use it.

       `var` hoists the name but not the initialiser, and the installers below run
       *during* this function -- so a `var resultsMenu = null` sitting further down
       would run after `installResultsMenu()` had filled it and quietly set it back to
       null, leaving the menu's Phase and Field submenus permanently empty. That is
       not hypothetical: it is what happened, along with the toolbar drawing the info
       glyph because `App.ICONS.viewresults` was assigned `undefined` the same way.
       Anything the installers touch is declared before the first of them is called. */
    var resultsMenu = null;      // the Results entry in App.MENUS, for refilling
    var resultsWindow = null;    // the floating chooser, while it is open
    var plotWindow = null;       // the wall/interface plot window, while it is open
    var plotColumns = 0;         // panels per row it was last drawn with
    var plotReloading = null;    // the run a reload of the plot is under way for

    extendViewportMenu();

    if (!App.Command.err) {
      App.Command.err = function (text) { App.Command.write('err', text); };
    }

    var stale = missingViewportApi(App.Viewport);
    if (stale.length) App.Command.err(staleMessage(stale));

    openOnDefaultMode();

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

      // "View calculation results": the mockup's dialog, replaced by the mode that
      // now exists. See `openResults`.
      if (item && item.action === 'results') {
        openResults();
        return;
      }

      /* Every Results menu entry. One action carrying the command it stands for,
         rather than one action name per entry: the menu is then a list of the same
         strings the command box takes, and adding an entry is adding a line of data. */
      if (item && item.action === 'resultsRun') {
        if (App.state && App.state.mode !== 'results') App.setMode('results');
        resultsCommand(item.cmd);
        return;
      }
      if (item && item.action === 'resultsAtNode') {
        askForNode();
        return;
      }
      // The rail's "Choose results": reopen the window, or bring it forward if it is
      // already up.
      if (item && item.action === 'chooseResults') {
        if (App.state && App.state.mode !== 'results') App.setMode('results');
        else openResultsWindow();
        return;
      }
      // The rail's "Plot along the wall": the same `results plot` the command box runs,
      // which opens the plot window when it has something to draw.
      if (item && item.action === 'plotResults') {
        if (App.state && App.state.mode !== 'results') App.setMode('results');
        resultsCommand('results plot');
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

      if (item && item.action === 'toggleNodeLabels') { toggleLabels('nodes'); return; }
      if (item && item.action === 'toggleElementLabels') { toggleLabels('elements'); return; }

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
      if (item && item.action === 'createNormalLoad') {
        if (App.NormalLoads) App.NormalLoads.start();
        return;
      }
      if (item && item.action === 'exportModel') {
        if (App.Export) App.Export.run();
        return;
      }
      if (item && item.action === 'calculate') {
        if (App.Calculate) App.Calculate.run();
        return;
      }
      if (item && item.action === 'phases') {
        phasesDialog();
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
          App.MESH_REFINEMENTS = null;
          App.Command.note(
            "Local mesh refinement reset; the model's own is used again.");
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
                 on: m.id === DEFAULT_MODEL_MODE };
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
      /* There is deliberately no menu item for any one model. Models are opened by
         running the Python that builds them -- `run <file.py>` in the command box --
         which works for any model, not only the one somebody thought to add a
         button for. See `runScript`. */
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
            // The normal load below is not one of the three vector kinds: it is
            // owned by App.NormalLoads and carries its own action, so the label
            // test that sorts the frozen three must not claim it.
            if (item.action === 'createNormalLoad') return;
            item.action = 'createLoad';
            item.loadKind = /point/i.test(item.label) ? 'point'
              : (/line/i.test(item.label) ? 'line' : 'surface');
          });
          // A pressure normal to a polyline rather than a vector on a flat run, so
          // App.Loads cannot make it -- but a user looking for a load looks here,
          // not in a tool of its own, so it joins the flyout the other three are in.
          if (!(tool.flyout || []).some(function (item) {
            return item && item.action === 'createNormalLoad';
          })) {
            tool.flyout = (tool.flyout || []).concat([
              { icon: 'load', label: 'Normal load', action: 'createNormalLoad' }
            ]);
          }
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
      if (!structuresMenu.items.some(function (item) {
        return item && item.action === 'createNormalLoad';
      })) {
        structuresMenu.items.push({ label: 'Create normal load',
                                    action: 'createNormalLoad', sub: false });
      }
    }

    installResultsMode();
    installPhasesOverview();

    /* The phases panel, on the project's own phases. `App.setMode` calls
       `mountPhases` whenever staged mode is entered (js/app.js:33), and the frozen
       one reads `App.PHASES` -- so replacing the function is what makes every entry
       into the mode draw the real sequence. */
    if (App.Explorer && App.Explorer.mountPhases) {
      App.Explorer.mountPhases = mountLivePhases;
      if (App.state && App.state.mode === 'staged') mountLivePhases();
    }

    /* The stage dots follow the last run: `calculate.js` hands the result over and
       the panel colours the phases that completed.

       And then the app goes to Results. A calculation that produced something to look
       at and left you on the phase editor is a calculation you have to go and find the
       output of -- which is exactly what this whole milestone exists to stop. The
       switch waits for `ready()`, because until the run has been read there are no
       phases to show; and it is gated on there being a readable phase, so a run that
       died before writing anything leaves you where you were, next to the error. */
    if (App.Calculate && App.Calculate.run && !App.Calculate.run.__phases) {
      var frozenCalcRun = App.Calculate.run;
      App.Calculate.run = function (done) {
        return frozenCalcRun(function (result) {
          rememberRun(result);
          if (done) done(result);
          if (!result || !App.Results || !App.Results.ready) return;
          App.Results.ready().then(function () {
            if (App.Results.stage()) App.setMode('results');
          });
        });
      };
      App.Calculate.run.__phases = true;
    }

    /* Staged construction editing: a pick in staged mode is also a toggle. */
    if (typeof App.selectObject === 'function' && !App.selectObject.__staged) {
      var frozenSelect = App.selectObject;
      App.selectObject = function (key, source) {
        frozenSelect(key, source);
        if (!key || source !== 'viewport') return;
        if (!App.state || App.state.mode !== 'staged') return;
        if (!App.PROJECT || !(App.PROJECT.phases || []).length) return;
        togglePartForPhase(key);
      };
      App.selectObject.__staged = true;
    }

    // Model explorer: enable Delete for drawn/imported geometry (see onTreeContextMenu).
    if (App.Explorer && App.Explorer.mountTree) {
      var frozenMountTree = App.Explorer.mountTree;
      App.Explorer.mountTree = function (mode) {
        frozenMountTree(mode);
        tagTreeRowsWithObjKeys(mode);
        addPartColorToggles(mode);
        addPhaseChecks(mode);
      };
    }
    if (typeof document !== 'undefined') {
      var treeHost = document.getElementById('tree-model');
      if (treeHost) treeHost.addEventListener('contextmenu', onTreeContextMenu, true);
    }

    /* `help` is a canned list in the frozen mockup (js/data.js:866). The commands this
       build really has belong in it, or the only way to find them is to read the
       source. Spliced above the mode-jump line so the scripting entry point is the
       first thing in the list rather than the last. */
    if (App.CMD_RESPONSES && App.CMD_RESPONSES.help &&
        !App.CMD_RESPONSES.help.some(function (line) { return /run </.test(line[1]); })) {
      App.CMD_RESPONSES.help.splice(1, 0,
        ['note', '  run <file.py>         build the model from a Python file'],
        ['note', '  export                write the Kratos deck'],
        ['note', '  cleargeometry         remove drawn/imported custom geometry'],
        ['note', '  results               open what a calculation wrote (try "results runs")'],
        ['note', '  colour <part>|all|off draw a part of the mesh in its own colour'],
        ['note', '  water <level>|off     set or remove the water level, e.g. water -1.5'],
        ['note', '  node <id>             which SubModelParts a node is in'],
        ['note', '  phases                the Phases overview: every phase, its time and result']);
    }

    /* ── Results mode ─────────────────────────────────────────────────────
       A sixth mode tab, its own dock panel, and the pointer readout over a contoured
       mesh. All of it is DOM, which on this machine means none of it is covered by an
       automated test -- so every control below does its work by calling the *same*
       `results ...` command the command box runs. There is one implementation of each
       action, it is the tested one, and the panel is a keyboard for it. */

    function installResultsMode() {
      if (!App.MODES || App.MODES.some(function (m) { return m.id === 'results'; })) {
        return;
      }
      /* Group 2, "Calculation", beside Mesh and Staged construction. Not a group of
         its own: `MODE_GROUP_LABELS` is private to the frozen toolbar (js/toolbars.js:46)
         and has no entry past 2, so a third group would draw with a blank label —
         and editing a frozen file for a caption is not worth it. Reading a result is
         the end of the calculation, so it sits there honestly enough. */
      /* The Model explorer beside the results. Every mode is handed the same tree
         (App.Model's syncTrees), but only for modes App.TREES already has a key for,
         and the frozen js/data.js knows five -- so Results had none and showed an
         empty dock. One key, and the next sync fills it like the rest. */
      if (App.TREES && !App.TREES.results) App.TREES.results = App.TREES.mesh || [];
      App.MODES.push({
        id: 'results', label: 'Results', group: 2,
        hint: 'Results mode — read back what a calculation wrote: choose a phase and a '
            + 'quantity, or type "results fields" to see what this phase offers.'
      });
      /* The plot button's glyph: a wall's axis down the left and a moment curve bellied
         out from it, on the 24x24 grid every App.ICONS entry uses. Assigned here, in the
         function that mounts the rail, for the hoisting reason `installResultsIcon`
         spells out. */
      if (App.ICONS && !App.ICONS.wallplot) {
        App.ICONS.wallplot = '<path d="M6 3v18"/><path d="M4 3h4M4 21h4"/>'
          + '<path d="M6 4.5C15 7 18 10.5 17.5 12.5S12 18 6 19.5"/>'
          + '<circle cx="17.5" cy="12.5" r="1.3"/>';
      }

      App.RAILS = App.RAILS || {};
      App.RAILS.results = [
        { icon: 'select', tip: 'Select', toggle: true, on: true },
        '-',
        // The chooser opens with the mode; this is how it comes back once closed.
        { icon: 'results', tip: 'Choose results', action: 'chooseResults' },
        { icon: 'wallplot', tip: 'Plot along the wall — M, Q, N, ux and the earth '
            + 'pressure on it, every phase', action: 'plotResults' }
      ];

      /* `App.setMode` is frozen and knows only about the phases panel (js/app.js:25).
         Wrapped rather than forked, the same way `App.selectObject` is. */
      if (typeof App.setMode === 'function' && !App.setMode.__results) {
        var frozenSetMode = App.setMode;
        App.setMode = function (mode) {
          frozenSetMode(mode);
          syncResultsPanel(mode === 'results');
        };
        App.setMode.__results = true;
      }

      // The tabs are built from App.MODES once, at boot, and this runs after that --
      // so they are built again, now that there is one more mode to draw.
      if (App.Toolbars && App.Toolbars.mountModes) {
        App.Toolbars.mountModes();
        if (App.state && App.Toolbars.highlightMode) {
          App.Toolbars.highlightMode(App.state.mode);
        }
      }

      installResultsIcon();
      installResultsMenu();
      collapsibleResultsPanel(document.getElementById('dock'));

      /* The panel and the menu both redraw themselves whenever the model behind them
         changes. Without this they are built once, from whatever was true when the
         mode was entered, and never again -- which is what made a finished calculation
         show an empty phase list while the run was being read in the background. */
      if (App.Results.onChange) {
        App.Results.onChange(function () {
          mountResultsPanel();
          refreshResultsMenu();
          followRunInPlot();
        });
      }

      /* The plot window is drawn from `App.ResultsPlot.state()` and nothing else, and
         opens when a `results plot` asks for it -- typed, or from any button. */
      if (App.ResultsPlot && App.ResultsPlot.onChange) {
        App.ResultsPlot.onChange(function (event) {
          if (event && event.open) openPlotWindow();
          renderPlotWindow(true);
        });
      }

      bindResultsProbe();
    }

    /* ── The "View calculation results" button ────────────────────────────
       The mockup gave it the bar chart it gives every chart-ish thing, and set it
       flush against Calculate with nothing between them -- so the one button that
       *starts* an hour of solving and the one that *reads* the answer sat as a pair,
       looking like two halves of the same control.

       Both are fixed here rather than in `js/data.js`: `App.UI.icon` looks the name up
       in `App.ICONS` when it draws, and `mountMain` reads `App.TOOLBAR` when it
       mounts, so adding to one and splicing the other is enough and the frozen file
       stays as it is. */

    function installResultsIcon() {
      if (!App.ICONS || !App.TOOLBAR) return;

      /* An eye over a chart: *view* the results.

         The lens is the set's own `eye` (js/data.js:38) squashed into the top half --
         same shape, so the two read as relatives rather than as two different eyes.
         The pupil is 1.4 rather than the 1.2 a straight scale would give: the lens is
         squashed vertically and not horizontally, so there is no ratio to preserve,
         and 1.2 comes out a 1.6px dot at the size the toolbar draws this. Under it, a
         baseline and three bars.

         Drawn on the same 24x24 grid as every other entry in `App.ICONS`, stroked and
         not filled, and everything sits inside 2.5..21.5 so it does not clip at the
         16px the main toolbar draws it at.

         Declared *in here*, not beside the other constants at the top of `install`.
         It lived there and this drew the info glyph instead: `var` hoists its name but
         not its value, `installResultsIcon` is called before that assignment runs, and
         `App.UI.icon` falls back to `App.ICONS.info` for anything it cannot find. The
         lookup is by name and silent, so the mistake showed up as the wrong picture
         rather than as an error. */
      var glyph =
        '<path d="M3 8.5Q12 2.5 21 8.5Q12 14.5 3 8.5Z"/>'
        + '<circle cx="12" cy="8.5" r="1.4"/>'
        + '<path d="M6 20h12"/>'
        + '<path d="M9 20v-3.5M12 20v-5.5M15 20v-2.5"/>';

      App.ICONS.viewresults = glyph;

      // The Phases menu carries the same action (js/data.js:177); one action, one
      // icon, or the two ways in stop looking like the same thing.
      (App.MENUS || []).forEach(function (menu) {
        (menu.items || []).forEach(function (item) {
          if (item && item.action === 'results') item.icon = 'viewresults';
        });
      });

      var at = -1;
      for (var i = 0; i < App.TOOLBAR.length; i++) {
        if (App.TOOLBAR[i] && App.TOOLBAR[i].action === 'results') { at = i; break; }
      }
      if (at < 0) return;
      App.TOOLBAR[at].icon = 'viewresults';
      if (App.TOOLBAR[at - 1] !== '|') App.TOOLBAR.splice(at, 0, '|');
      if (App.Toolbars && App.Toolbars.mountMain) App.Toolbars.mountMain();
    }

    /* ── The Results menu ─────────────────────────────────────────────────
       The menu bar mirrors the modes -- Soil, Structures, Mesh, Flow conditions,
       Phases -- and Results arrived without its half of that pairing. Everything in
       it runs one of the `results ...` commands, so the menu, the panel and the
       command box are three ways into one tested implementation.

       `Phase` and `Field` are filled in from the open run. `App.Menu.build` reads
       `it.sub` when the menu is opened rather than when it is mounted, so keeping the
       same item objects and refilling their arrays is enough to keep them current. */

    function installResultsMenu() {
      if (!App.MENUS || App.MENUS.some(function (m) { return m.label === 'Results'; })) {
        return;
      }
      resultsMenu = {
        label: 'Results',
        items: [
          { label: 'Open run…', icon: 'results', action: 'resultsRun', cmd: 'results runs' },
          '-',
          { label: 'Phase', sub: [] },
          { label: 'Previous phase', action: 'resultsRun', cmd: 'results phase -' },
          { label: 'Next phase', action: 'resultsRun', cmd: 'results phase +' },
          '-',
          { label: 'Field', sub: [] },
          { label: 'List fields', action: 'resultsRun', cmd: 'results fields' },
          '-',
          { label: 'Shading', sub: [
            { label: 'Smooth', action: 'resultsRun', cmd: 'results smooth' },
            { label: '8 bands', action: 'resultsRun', cmd: 'results bands 8' },
            { label: '16 bands', action: 'resultsRun', cmd: 'results bands 16' },
            { label: '32 bands', action: 'resultsRun', cmd: 'results bands 32' },
            { label: '48 bands', action: 'resultsRun', cmd: 'results bands 48' }
          ] },
          { label: 'Colours', sub: [] },
          { label: 'Deformed mesh', sub: [
            { label: 'Off', action: 'resultsRun', cmd: 'results deform off' },
            { label: 'Automatic', action: 'resultsRun', cmd: 'results deform auto' },
            { label: 'True scale (×1)', action: 'resultsRun', cmd: 'results deform 1' },
            { label: '×10', action: 'resultsRun', cmd: 'results deform 10' },
            { label: '×100', action: 'resultsRun', cmd: 'results deform 100' }
          ] },
          { label: 'Fit range to this phase', action: 'resultsRun',
            cmd: 'results range auto' },
          '-',
          { label: 'Value at a node…', action: 'resultsAtNode' },
          { label: 'Plot along the wall…', icon: 'wallplot', action: 'resultsRun',
            cmd: 'results plot' },
          { label: 'Save field as CSV', action: 'resultsRun', cmd: 'results csv' },
          { label: 'Download run', action: 'resultsRun', cmd: 'results zip' }
        ]
      };

      // Before Expert and Help, which are the two that trail every mode's own menu.
      var at = App.MENUS.map(function (m) { return m.label; }).indexOf('Expert');
      App.MENUS.splice(at < 0 ? App.MENUS.length : at, 0, resultsMenu);
      refreshResultsMenu();
      if (App.Menu && App.Menu.mountBar) App.Menu.mountBar();
    }

    /* The one menu entry that needs a value typed. A prompt rather than a dialog of
       its own: it asks for one integer, and the answer is printed to the command log
       by the same `results at` the command box runs. */
    function askForNode() {
      if (App.state && App.state.mode !== 'results') App.setMode('results');
      var node = window.prompt('Show every field at which node number?');
      if (node === null) return;
      node = String(node).trim();
      if (!/^\d+$/.test(node)) {
        if (App.Command) App.Command.err('"' + node + '" is not a node number.');
        return;
      }
      resultsCommand('results at ' + node);
    }

    function itemsOf(label) {
      if (!resultsMenu) return null;
      return resultsMenu.items.filter(function (it) {
        return it && it.label === label;
      })[0];
    }

    function refreshResultsMenu() {
      var phase = itemsOf('Phase');
      var field = itemsOf('Field');
      if (!phase || !field || !App.Results) return;
      var state = App.Results.state();

      phase.sub = (state.stages || []).map(function (s) {
        return {
          label: s.index + '  ' + s.phase, checked: s.index === state.stage,
          disabled: !s.results, action: 'resultsRun',
          cmd: 'results phase ' + s.index
        };
      });
      phase.disabled = !phase.sub.length;

      field.sub = [];
      ((state.catalogue && state.catalogue.groups) || []).forEach(function (group) {
        field.sub.push({ title: group.name });
        group.fields.forEach(function (entry) {
          field.sub.push({
            label: entry.label + '  (' + entry.unit + ')',
            checked: !!(state.field && state.field.field === entry.name),
            action: 'resultsRun', cmd: 'results field ' + entry.name
          });
        });
      });
      field.disabled = !field.sub.length;

      var colours = itemsOf('Colours');
      if (colours) {
        var options = App.Results.options();
        colours.sub = Object.keys(App.ResultsRender.MAPS).map(function (name) {
          return { label: App.ResultsRender.MAP_LABELS[name] || name,
                   checked: options.map === name,
                   action: 'resultsRun', cmd: 'results map ' + name };
        });
        colours.sub.push('-');
        colours.sub.push({
          label: 'Reversed', checked: !!options.reversed, action: 'resultsRun',
          cmd: 'results reverse ' + (options.reversed ? 'off' : 'on')
        });
        colours.sub.push({
          label: 'Show mesh', checked: !!options.mesh, action: 'resultsRun',
          cmd: 'results mesh ' + (options.mesh ? 'off' : 'on')
        });
      }
    }

    /* "View calculation results" -- the toolbar's chart button and the Phases menu
       item, both `action: 'results'` (js/data.js:177, :222). The frozen handler opens
       a "not implemented in this mockup" dialog (js/app.js:201), which is exactly what
       it should have done until this milestone. Now there is somewhere to go. */
    function openResults() {
      App.setMode('results');
      if (App.Results.current()) {
        // Already open -- `setMode` has just drawn the panel for it.
        return App.Results.ready();
      }
      // Nothing open: go to the newest run on the machine, which after a calculation
      // is the one that just finished.
      return App.Results.handleCommand('results runs').then(function (runs) {
        if (runs && runs.length) return App.Results.handleCommand('results open 1');
        if (App.Command) {
          App.Command.note('Nothing has been calculated on this machine yet — '
                           + 'press Calculate (F9) first.');
        }
      }).then(mountResultsPanel);
    }

    /* ── The Results window ───────────────────────────────────────────────
       The same controls as the dock panel, in a window of their own: the dock is
       narrow and shares its height with the Model and Selection explorers, and
       choosing a phase and a quantity is the thing this mode is for.

       Deliberately *modeless*. `App.Dialogs.open` lays a scrim over the page and every
       other dialog in this app wants that -- they are edits you finish before carrying
       on. This one is not: its whole purpose is to change what the model looks like
       while you watch it, so the scrim is taken back out and the viewport stays live
       underneath. Everything else the shell gives -- dragging, resizing, Esc -- is
       exactly right and is kept. */

    function openResultsWindow() {
      if (resultsWindow) {
        flashResultsWindow();
        return resultsWindow;
      }
      if (!App.Dialogs || !App.Dialogs.open) return null;

      /* The actions go in the footer beside Close, not in the body. `.dlg-body` is a
         flex *row* (css/components.css:313), so a second block inside it lands next
         to the controls rather than under them, and its buttons stretch to the full
         height of the window. The footer is where a dialog's buttons belong anyway.

         `keepOpen` on all three: fitting a range or saving a file is not finishing
         with the window. */
      var act = function (label, cmd) {
        return { label: label, keepOpen: true,
                 onClick: function () { resultsCommand(cmd); } };
      };

      var handle = App.Dialogs.open({
        title: 'Choose results',
        // Tall enough for every row without a scrollbar, and wide enough for the four
        // actions and Close on one line each. At 430 x 300 the last rows were cut off
        // and "Plot wall…" / "Download run" broke over two lines.
        width: 580, height: 440,
        buttons: [
          act('Plot wall…', 'results plot'),
          act('Fit range', 'results range auto'),
          act('Save CSV', 'results csv'),
          act('Download run', 'results zip'),
          { label: 'Close', primary: true }
        ],
        build: function (body) { renderResultsControls(body, false); },
        onClose: function () { resultsWindow = null; }
      });
      handle.dialog.classList.add('dlg-results');

      /* The scrim belongs to a modal dialog and this one is not modal. Removed rather
         than hidden by CSS so that nothing is left over the viewport swallowing
         pointer events -- which would take the orbit, the pick and the value readout
         with it. */
      var layer = document.getElementById('modal-layer');
      var scrims = layer ? layer.querySelectorAll('.scrim') : [];
      if (scrims.length) {
        var scrim = scrims[scrims.length - 1];
        if (scrim.parentNode) scrim.parentNode.removeChild(scrim);
      }

      resultsWindow = handle;
      return handle;
    }

    /* Already open: nudge it rather than silently doing nothing. The same shake
       `js/dialogs.js` uses when a modal's scrim is clicked -- reproduced rather than
       imported because it is private to that closure. */
    function flashResultsWindow() {
      if (!resultsWindow || !resultsWindow.dialog.animate) return;
      resultsWindow.dialog.animate(
        [{ transform: 'translateX(0)' }, { transform: 'translateX(-4px)' },
         { transform: 'translateX(4px)' }, { transform: 'translateX(0)' }],
        { duration: 160 });
    }

    function closeResultsWindow() {
      if (resultsWindow) resultsWindow.close();
      resultsWindow = null;
    }

    /* ── The plot window ──────────────────────────────────────────────────
       A member's results along it, a panel per phase -- the figure is
       `App.ResultsPlot.svg()`, a tested string, and this window only hosts it. Modeless
       like the chooser, for the same reason: it is read beside the model, not finished
       and dismissed. Its controls are the `results plot ...` commands, so the window,
       the menu and the command box cannot disagree. */

    function openPlotWindow() {
      if (plotWindow) return plotWindow;
      if (!App.Dialogs || !App.Dialogs.open) return null;

      var act = function (label, cmd) {
        return { label: label, keepOpen: true,
                 onClick: function () { resultsCommand(cmd); } };
      };
      var handle = App.Dialogs.open({
        title: 'Plot along the wall',
        width: 1180, height: 560,
        buttons: [
          act('Save SVG', 'results plot svg'),
          act('Save CSV', 'results plot csv'),
          { label: 'Close', primary: true }
        ],
        onClose: function () { plotWindow = null; plotColumns = 0; }
      });
      handle.dialog.classList.add('dlg-plot');

      var layer = document.getElementById('modal-layer');
      var scrims = layer ? layer.querySelectorAll('.scrim') : [];
      if (scrims.length) {
        var scrim = scrims[scrims.length - 1];
        if (scrim.parentNode) scrim.parentNode.removeChild(scrim);
      }

      plotWindow = handle;
      renderPlotWindow(true);

      // Panels per row follow the window's width, so widening it puts the phases side
      // by side and narrowing it wraps them -- redrawn only when that count changes.
      if (typeof ResizeObserver === 'function') {
        new ResizeObserver(function () { renderPlotWindow(false); }).observe(handle.body);
      }
      return handle;
    }

    function closePlotWindow() {
      if (plotWindow) plotWindow.close();
      plotWindow = null;
      plotColumns = 0;
    }

    /* Panels per row for the body's current width: as many 220 px panels as fit, never
       more than five (the reference figure's row) nor more than there are phases. */
    function plotColumnsFor(body, stages) {
      var width = body.clientWidth || 1100;
      return Math.max(1, Math.min(5, stages || 1, Math.floor(width / 220)));
    }

    function renderPlotWindow(force) {
      if (!plotWindow || !App.ResultsPlot) return;
      var body = plotWindow.body;
      var state = App.ResultsPlot.state();
      var plot = state.plot;
      var columns = plotColumnsFor(body, plot ? plot.stages.length : 1);
      if (!force && columns === plotColumns) return;
      plotColumns = columns;

      if (!plot) {
        body.innerHTML = '<p class="dock-empty">Nothing is plotted. Type '
          + '<code>results plot</code>, or <code>results plot members</code> to see what '
          + 'this run can show.</p>';
        return;
      }

      var members = state.members || [];
      var member = members.filter(function (m) { return m.name === plot.member; })[0];
      var controls = '<div class="rp-controls">'
        + '<label>Member ' + select('plot-member', members.map(function (m) {
          return { value: m.name, label: m.name, selected: m.name === plot.member };
        })) + '</label>'
        + '<label>Quantity ' + select('plot-quantity',
          ((member && member.quantities) || []).map(function (q) {
            return { value: q.name, label: q.label + '  (' + q.unit + ')',
                     selected: q.name === plot.quantity };
          })) + '</label>'
        + '<span class="rp-run" title="' + esc(state.run) + '">' + esc(state.run)
        + '</span></div>';

      body.innerHTML = '<div class="rp-window">' + controls
        + '<div class="rp-host">' + App.ResultsPlot.svg(plot, { columns: columns })
        + '</div></div>';

      bind(body, 'plot-member', function (value) { return 'results plot ' + value; });
      bind(body, 'plot-quantity', function (value) {
        return 'results plot ' + plot.member + ' ' + value;
      });
    }

    /* A different run opened while the window is up: plot that one instead, rather
       than go on showing the last run's wall under the new run's name. */
    function followRunInPlot() {
      if (!plotWindow || !App.ResultsPlot) return;
      var run = App.Results.current();
      var shown = App.ResultsPlot.state().run;
      if (!run || run === shown || run === plotReloading) return;
      plotReloading = run;
      resultsCommand('results plot').then(function () { plotReloading = null; },
                                          function () { plotReloading = null; });
    }

    function syncResultsPanel(on) {
      var panel = document.getElementById('panel-results');
      var dock = document.getElementById('dock');
      if (!panel || !dock) return;
      panel.hidden = !on;
      if (App.UI && App.UI.syncDock) App.UI.syncDock(dock);
      if (on) {
        mountResultsPanel();
        // Entering the mode opens the chooser, every time. It is what the mode is
        // for, and the dock panel alone is easy to miss down the side of the page.
        // The rail's "Choose results" reopens it after it has been closed. It fills
        // itself as it is built, so there is nothing to render afterwards.
        openResultsWindow();
      } else {
        // Leaving takes the contour off the model rather than leaving it behind under
        // the geometry, where it would be neither editable nor explicable -- and the
        // window with it, since it belongs to a mode that is no longer on.
        closeResultsWindow();
        closePlotWindow();
        if (App.ResultsView) App.ResultsView.clear();
      }
    }

    /* Run one of the tested commands, then redraw the panel from the state it left. */
    function resultsCommand(text) {
      var answer = App.Results.handleCommand(text);
      return Promise.resolve(answer === false ? null : answer)
        .then(function () { mountResultsPanel(); });
    }

    /* Both mounts, every time anything changes. The dock panel is always there; the
       window only while it is open. Neither keeps state of its own -- both are drawn
       from `App.Results.state()`, so they cannot disagree with each other or with the
       command box. */
    function mountResultsPanel() {
      // The dock panel has no footer, so it keeps the actions inline. The window puts
      // them beside Close instead -- see `openResultsWindow`.
      renderResultsControls(document.getElementById('panel-results-body'), true);
      renderResultsControls(resultsWindow && resultsWindow.body, false);
    }

    function renderResultsControls(body, withActions) {
      if (!body || !App.Results) return;
      var run = App.Results.current();
      if (!run) {
        body.innerHTML = '<p class="dock-empty">No run is open.<br>'
          + 'Press <b>Calculate</b> (F9), or type <code>results runs</code> '
          + 'in the command box to list what is already on this machine.</p>';
        return;
      }

      var state = App.Results.state ? App.Results.state() : {};
      var options = App.Results.options();
      var rows = [];

      rows.push(row('Run', '<span class="res-run" title="' + esc(run) + '">'
                           + esc(run) + '</span>'));
      rows.push(row('Phase', select('phase', (state.stages || []).map(function (s) {
        return { value: s.index, label: s.index + '  ' + s.phase,
                 selected: s.index === state.stage, disabled: !s.results };
      }))));

      var fields = [];
      ((state.catalogue && state.catalogue.groups) || []).forEach(function (group) {
        group.fields.forEach(function (entry) {
          fields.push({ value: entry.name,
                        label: group.name + ' · ' + entry.label + '  (' + entry.unit + ')',
                        selected: state.field && state.field.field === entry.name });
        });
      });
      rows.push(row('Field', fields.length
        ? select('field', fields)
        : '<span class="dock-empty">this phase wrote nothing</span>'));

      rows.push(row('Shading', select('bands', [0, 4, 8, 16, 24, 32, 48].map(function (n) {
        return { value: n, label: n ? n + ' bands' : 'smooth',
                 selected: options.bands === n };
      }))));
      rows.push(row('Colours', select('map',
        Object.keys(App.ResultsRender.MAPS).map(function (name) {
          return { value: name,
                   label: App.ResultsRender.MAP_LABELS[name] || name,
                   selected: options.map === name };
        }))));
      /* The legend's limits. An empty box follows the phase -- its own value is the
         placeholder -- so typing one limit leaves the other exact rather than the
         rounded number a filled-in box would hand back. What was typed goes through
         `App.Results.limitsCommand`, which is tested, to the `results range` that is. */
      if (state.field) {
        var limit = function (name, typed, auto, tip) {
          return '<input type="text" inputmode="decimal" data-res="' + name + '"'
            + ' value="' + esc(typed === null ? '' : typed) + '"'
            + ' placeholder="' + esc(App.ResultsRender.format(auto)) + '"'
            + ' title="' + esc(tip) + '">';
        };
        rows.push(row('Limits', '<span class="res-limits">'
          + limit('lim-min', options.min, state.field.min,
                  'Legend minimum — leave empty to follow the phase')
          + '<span class="res-limits-to">…</span>'
          + limit('lim-max', options.max, state.field.max,
                  'Legend maximum — leave empty to follow the phase')
          + '<button type="button" data-res="lim-auto"'
          + " title=\"Back to this phase's own range\">Auto</button>"
          + '<span class="res-limits-unit">' + esc(state.field.unit) + '</span></span>'));
      }
      rows.push(row('Reverse', '<input type="checkbox" data-res="reverse"'
                               + (options.reversed ? ' checked' : '') + '>'));
      rows.push(row('Mesh', '<input type="checkbox" data-res="mesh"'
                            + (options.mesh ? ' checked' : '') + '>'));
      rows.push(row('Deformed', select('deform', [
        { value: 'off', label: 'off', selected: !options.deform },
        { value: 'auto', label: 'auto', selected: options.deform === 'auto' },
        { value: '1', label: 'true scale (×1)', selected: options.deform === 1 },
        { value: '10', label: '×10', selected: options.deform === 10 },
        { value: '100', label: '×100', selected: options.deform === 100 }
      ])));

      body.innerHTML = '<div class="res-grid">' + rows.join('') + '</div>'
        + (withActions
           ? '<div class="res-actions">'
             + '<button data-cmd="results plot">Plot wall…</button>'
             + '<button data-cmd="results range auto">Fit range</button>'
             + '<button data-cmd="results csv">Save CSV</button>'
             + '<button data-cmd="results zip">Download run</button>'
             + '</div>'
           : '');

      bind(body, 'phase', function (value) { return 'results phase ' + value; });
      bind(body, 'field', function (value) { return 'results field ' + value; });
      bind(body, 'bands', function (value) {
        return value === '0' ? 'results smooth' : 'results bands ' + value;
      });
      bind(body, 'map', function (value) { return 'results map ' + value; });
      var reverse = body.querySelector('[data-res="reverse"]');
      if (reverse) {
        reverse.addEventListener('change', function () {
          // `on`/`off` rather than a bare toggle: the box already carries the state,
          // and toggling from it would invert whatever the module happened to think.
          resultsCommand('results reverse ' + (reverse.checked ? 'on' : 'off'));
        });
      }
      var meshBox = body.querySelector('[data-res="mesh"]');
      if (meshBox) {
        meshBox.addEventListener('change', function () {
          // on/off, like Reverse: the box already carries the state.
          resultsCommand('results mesh ' + (meshBox.checked ? 'on' : 'off'));
        });
      }
      bind(body, 'deform', function (value) { return 'results deform ' + value; });

      var minBox = body.querySelector('[data-res="lim-min"]');
      var maxBox = body.querySelector('[data-res="lim-max"]');
      var onLimits = function () {
        // `change` fires on Enter and on leaving the box, not on every keystroke, so a
        // half-typed "-0." is never sent.
        var cmd = App.Results.limitsCommand(minBox.value, maxBox.value);
        if (cmd) resultsCommand(cmd);
      };
      if (minBox && maxBox) {
        minBox.addEventListener('change', onLimits);
        maxBox.addEventListener('change', onLimits);
      }
      var autoButton = body.querySelector('[data-res="lim-auto"]');
      if (autoButton) {
        autoButton.addEventListener('click', function (event) {
          event.preventDefault();   // inside a <label>: do not also focus the first box
          resultsCommand('results range auto');
        });
      }

      Array.prototype.forEach.call(body.querySelectorAll('[data-cmd]'), function (button) {
        button.addEventListener('click', function () {
          resultsCommand(button.dataset.cmd);
        });
      });
    }

    /* Bound by data attribute, not by id: the controls are mounted twice at once --
       once in the dock and once in the floating window -- and two elements sharing an
       id is invalid, with `getElementById` silently answering for whichever came
       first. */
    function bind(body, name, toCommand) {
      var control = body.querySelector('[data-res="' + name + '"]');
      if (control) {
        control.addEventListener('change', function () {
          resultsCommand(toCommand(control.value));
        });
      }
    }

    function row(label, control) {
      return '<label class="res-row"><span>' + esc(label) + '</span>' + control + '</label>';
    }

    function select(name, entries) {
      return '<select data-res="' + name + '">' + entries.map(function (entry) {
        return '<option value="' + esc(entry.value) + '"'
             + (entry.selected ? ' selected' : '')
             + (entry.disabled ? ' disabled' : '') + '>'
             + esc(entry.label) + '</option>';
      }).join('') + '</select>';
    }

    function esc(text) {
      return String(text === undefined || text === null ? '' : text)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    /* The pointer readout: the value under the cursor, in the status bar, while a
       contour is on screen.

       Hung off `App.setCoords` rather than off a second raycast of our own. The
       viewport already turns every pointer move into a world point -- against the
       right plane for the dimension, with the camera the frame was drawn with -- and
       hands it here (frontend/js/viewport.js:1113). Casting again would be a second
       implementation of that, and would drift from it the first time the section
       plane moved. */
    function bindResultsProbe() {
      if (typeof App.setCoords !== 'function' || App.setCoords.__results) return;
      var frozenSetCoords = App.setCoords;
      App.setCoords = function (x, y, z) {
        frozenSetCoords(x, y, z);
        if (!App.state || App.state.mode !== 'results') return;
        if (!App.ResultsView || !App.ResultsView.isShowing()) return;
        var hint = document.getElementById('sb-hint');
        if (!hint) return;
        var text = App.ResultsView.describeAt({ x: x, y: y, z: z });
        if (text) hint.textContent = text;
      };
      App.setCoords.__results = true;
    }

    var frozenRun = App.Command.run;
    App.Command.run = function (text) {
      if (App.DrawInput && App.DrawInput.handleCommand(text)) return;

      /* The results commands, ahead of everything else and answering only their own:
         `handleCommand` returns false for anything that is not `results ...`, which
         is what keeps `mesh`, `run` and `export` with their owners below. It lives in
         its own module because it has to stay free of the DOM -- that is what lets
         `frontend/tests/run_headless.py` execute it here, where no browser can be. */
      if (App.Results) {
        var handledByResults = App.Results.handleCommand(text);
        if (handledByResults !== false) return handledByResults;
      }

      // `colour <part>`: the Model explorer's colour toggle, typed.
      if (runColourCommand(text)) return;
      // `water <level>` / `water off`: the project's water level.
      if (runWaterCommand(text)) return;
      // `units` / `units <system>`: the project's unit system.
      if (runUnitsCommand(text)) return;
      // `node <id>`: which SubModelParts a node is in.
      if (runNodeCommand(text)) return;

      var cmd = (text || '').trim().split(/\s+/)[0].toLowerCase();
      if (cmd === 'phases') {
        if (App.Command.write) App.Command.write('echo', '> ' + text.trim());
        phasesDialog();
        return;
      }
      if (cmd === 'cleargeometry') {
        if (App.Command.note) App.Command.note('Clearing custom geometry...');
        return deleteRequest('/api/project/custom_parts', 'Could not clear custom geometry.')
          .then(function() { return App.Model.load(); })
          .then(function() { return App.Viewport.refresh(); })
          .then(function() {
             if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
             if (App.Command.ok) App.Command.ok('Custom geometry cleared.');
          })
          .catch(function (error) { if (App.Command.err) App.Command.err(error.message); });
      }
      
      /* run <file.py> -- build the model from a Python file.

         The scripting interface every modeller of this kind has, and the reason the
         command line is here rather than being a log: the file says what the model is,
         the server runs it, and what comes back is adopted and meshed. Errors are the
         server's own message verbatim -- core/script.py writes them to be read here,
         with no stack trace on screen to fall back on. */
      if (cmd === 'run' || cmd === 'load') {
        var scriptPath = (text || '').trim().slice(cmd.length).trim();
        if (App.Command.write) App.Command.write('echo', '> ' + (text || '').trim());
        if (!scriptPath) {
          if (App.Command.err) App.Command.err('Usage: run <path to a .py file>');
          return;
        }
        return App.Api.post('/api/project/script', { path: scriptPath })
          .then(function (result) {
            // A deck case (a script naming a finished deck) brings its own mesh: show
            // that, rather than meshing the empty site its project carries.
            if (App.Deck && App.Deck.hasMesh(result)) {
              return adoptProject(result.project, 'Ran ' + scriptPath
                + ' — a Kratos deck, opened with its own mesh.')
                .then(function () { showDeck(result.mesh, result.project); });
            }
            return adoptProject(result.project,
              'Ran ' + scriptPath + ' — model built. Meshing it now.')
              .then(function () { requestMesh(true, null); });
          })
          .catch(function (error) {
            if (App.Command.err) App.Command.err(error.message);
          });
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

      if (App.NormalLoads && App.NormalLoads.isNormalLoadKey(reselect)) {
        var normalLoad = (App.NORMAL_LOADS || []).filter(function (item) {
          return item.id === reselect;
        })[0];
        // Nothing shared to carry: a normal load holds its own coordinates and its
        // own magnitude, so the record is the whole write.
        if (normalLoad) return App.NormalLoads.save(normalLoad);
      }

      function remount() {
        App.Explorer.mountTree(App.state.mode);
        App.Explorer.mountSelection(reselect);
      }

      return App.Api.patch('/api/project/layers', {
        layers: copy(App.LAYERS),
        boreholes: copy(App.BOREHOLES),
        domain: copy(App.Model.pendingDomain()),
        // Rides along with the domain because it is edited from the same panel and is
        // the same kind of thing: one object for the whole project. Sent on every
        // commit rather than only when the water rows were the ones touched -- the
        // endpoint takes the whole object or none of it, and working out which rows
        // the user visited would be a second source of truth about the same edit.
        water: copy(App.Model.pendingWater()),
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

      /* The command box, routed through the live interpreter.

         js/command.js binds its input to a *private* `run`, so replacing the exported
         `App.Command.run` does not change what typing into the box does: the frozen
         interpreter answers, and every live command reads as "Unknown command". This
         used to intercept `mesh` alone, which is why it was not noticed -- every other
         live command (`run`, `export`, `cleargeometry`, and anything `DrawInput`
         handles) was being answered by the frozen one.

         So the interception is now unconditional: Enter always goes to
         `App.Command.run`, whose wrapper falls back to the frozen interpreter for
         anything the live layer does not implement. Recall has to be reimplemented with
         it -- the frozen history is private to the same closure, and stopping its
         handler is what stops it being filled. */
      var alreadyBound = commandBoxBound;
      commandBoxBound = true;
      if (!alreadyBound) document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && activeLayerEdit && !activeLayerEdit.committed) {
          // activeLayerEdit.snapshot is a {layers, boreholes} pair, not a bare array.
          restoreSoil(activeLayerEdit.snapshot);
          activeLayerEdit = null;
        }
        var entry = document.getElementById('cmd-entry');
        if (entry && event.target === entry && event.key === 'Enter') {
          var text = entry.value.trim();
          if (!text) return;
          event.preventDefault(); event.stopImmediatePropagation();
          cmdHistory.push(text); cmdIndex = cmdHistory.length;
          entry.value = '';
          App.Command.run(text);
          return;
        }
        if (entry && event.target === entry
            && (event.key === 'ArrowUp' || event.key === 'ArrowDown')) {
          event.preventDefault(); event.stopImmediatePropagation();
          if (event.key === 'ArrowUp') {
            if (cmdIndex > 0) entry.value = cmdHistory[--cmdIndex];
          } else if (cmdIndex < cmdHistory.length - 1) {
            entry.value = cmdHistory[++cmdIndex];
          } else {
            cmdIndex = cmdHistory.length; entry.value = '';
          }
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
    collapsibleResultsPanel: collapsibleResultsPanel,
    snapshotLayers: snapshotLayers, restoreLayers: restoreLayers,
    snapshotSoil: snapshotSoil, restoreSoil: restoreSoil, pitRefinement: pitRefinement,
    isDeletableCustomPart: isDeletableCustomPart, tagTreeRowsWithObjKeys: tagTreeRowsWithObjKeys,
    MODES: MODES, patchFor: patchFor, sectionLabel: sectionLabel,
    DEFAULT_MODEL_MODE: DEFAULT_MODEL_MODE,
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
    withLabelRows: withLabelRows, toggleLabels: toggleLabels,
    extendViewportMenu: extendViewportMenu,
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
