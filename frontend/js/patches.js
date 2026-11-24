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

  function copy(value) { return JSON.parse(JSON.stringify(value)); }
  function snapshotLayers() { return copy(App.LAYERS || []); }
  function restoreLayers(snapshot) {
    App.LAYERS = copy(snapshot);
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

  /* Mesh > Clear mesh, the rail's Clear mesh and `clearmesh`. The mesh settings and the
     local sizes stay; Generate mesh (F9) makes the mesh again. */
  function clearMesh() {
    if (inFlight) {
      App.Command.note('Mesh generation is running; clear the mesh when it is done.');
      return;
    }
    if (!App.Viewport.clearMesh || !App.Viewport.clearMesh()) {
      App.Command.note('There is no mesh to clear.');
      return;
    }
    if (App.Model.clearMeshStats) App.Model.clearMeshStats();
    if (App.state.selection === 'mesh' && App.selectObject) App.selectObject(null);
    App.Command.ok('Mesh cleared. Generate mesh (F9) makes it again with the same settings.');
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
    var stages = (project.stages || []).length;
    if (stages) {
      App.Command.note('Its ' + stages + ' stages are the stages on the Staged '
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
     (core/model/templates.py blank_project). This is a 2D modeller first. */
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
        // between them (core/model/load_translation.py). It says what it did to each one, and a
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
     structures -- and an anchor may hang from whichever of them is there. The tool has
     to say which one it is about to make, for the same reason the soil-body tool
     renames itself below. */
  function nameStructureActions(is2d) {
    var labels = {
      createSheetPile: is2d ? 'Create sheet pile…' : 'Create wall panel…',
      createMember: 'Create member…',
      createAnchor: is2d ? 'Create anchor…' : 'Create anchor in space…',
      interface: 'Create interface…'
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
      if (!tool || tool.action !== 'createSoilVolume') return;
      tool.tip = 'Create soil ' + noun + '…';
      (tool.flyout || []).forEach(function (item) {
        if (item.action === 'createSoilBodyByCoordinates') {
          item.label = 'Soil ' + noun + ' by coordinates…';
        }
      });
    });
    (App.MENUS || []).forEach(function (menu) {
      (menu.items || []).forEach(function (item) {
        if (item && item.action === 'createSoilVolume') {
          item.label = 'Create soil ' + noun + '…';
        }
      });
    });
  }

  /* Create soil surface… in 2D: the outline is clicked corner by corner in the
     section, then the soil-surface window opens on those corners, so the name, the
     material and any corner the click did not land exactly can be set before it is
     built. Without the draw tool the window opens on its worked example. */
  function drawSoilSurface() {
    if (!App.SoilVolumeDialog) return;
    if (!App.DrawInput) { App.SoilVolumeDialog.open(); return; }
    App.DrawInput.start('polygon', {
      noun: 'a soil surface',
      onComplete: function (vertices) { App.SoilVolumeDialog.open(null, { vertices: vertices }); }
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
     sheet pile or wall, an anchor, a load -- needs the same two actions built here.
     A soil layer is here too: the frozen menu renames it with the browser's prompt,
     which a screenshot cannot show and a test cannot fill in. */
  function layerOf(key) {
    if (!key || key.indexOf('soil_') !== 0 || !App.layerById) return null;
    return App.layerById(key.slice(5)) || null;
  }

  function objectKind(key) {
    if (isDeletableCustomPart(key)) return 'part';
    if (App.Beams && App.Beams.isBeamKey(key)) return 'beam';
    if (App.Anchors && App.Anchors.isAnchorKey(key)) return 'anchor';
    if (App.Interfaces && App.Interfaces.isInterfaceKey(key)) return 'interface';
    if (App.NormalLoads && App.NormalLoads.isNormalLoadKey(key)) return 'normal_load';
    if (App.Lines && App.Lines.isLineKey(key)) return 'line';
    if (App.Lines && App.Lines.bodyOf(key)) return 'body';
    if (App.Loads && App.Loads.isLoadKey(key)) return 'load';
    if (App.BoundaryConditions && App.BoundaryConditions.isConditionKey(key)) {
      return 'condition';
    }
    if (layerOf(key)) return 'layer';
    return null;
  }

  function lineByKey(key) {
    return (App.LINES || []).filter(function (item) { return item.id === key; })[0];
  }

  function conditionByKey(key) {
    return (App.BOUNDARY_CONDITIONS || []).filter(function (item) { return item.id === key; })[0];
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
      : kind === 'line' ? lineByKey(key)
      : kind === 'body' ? App.Lines.bodyOf(key)
      : kind === 'load' ? loadByKey(key)
      : kind === 'condition' ? conditionByKey(key)
      : kind === 'layer' ? layerOf(key) : null;
    return obj ? (kind === 'part' ? obj.label : obj.name) : '';
  }

  function reportRenameError(error) {
    if (App.Command && App.Command.err) App.Command.err(error.message);
  }

  /* One rename path for every live kind: ask in the Rename window (js/name-dialog.js),
     write the field the frozen grid already treats as the display name, then save
     through each kind's own door -- a custom part goes back through the
     layers/domain/custom_parts PATCH (see commitSelectionEdit), a beam/anchor/load
     through its own module, which is what validates, persists and refreshes the tree
     for it already. */
  function renameObject(kind, key) {
    if (kind === 'body') return renameBodyPart(key);
    return App.NameDialog.ask({ title: 'Rename', value: objectName(kind, key),
                                help: 'Shown in the Model explorer.' })
      .then(function (name) {
        if (name !== null) return renamed(kind, key, name);
      });
  }

  function renamed(kind, key, name) {
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
    if (kind === 'line') {
      var line = lineByKey(key);
      if (!line) return;
      line.name = name;
      return App.Lines.save(line).catch(reportRenameError);
    }
    if (kind === 'load') {
      var load = loadByKey(key);
      if (!load) return;
      load.name = name;
      return App.Loads.save(load).catch(reportRenameError);
    }
    if (kind === 'condition') {
      var condition = conditionByKey(key);
      if (!condition) return;
      condition.name = name;
      return App.BoundaryConditions.save(condition).catch(reportRenameError);
    }
    if (kind === 'layer') {
      var layer = layerOf(key);
      if (!layer) return;
      layer.name = name;
      if (App.Command && App.Command.ok) App.Command.ok('Renamed soil layer to ' + name + '.');
      return App.commitSelectionEdit(key);
    }
  }

  function deleteObject(kind, key) {
    if (kind === 'part') return deleteCustomPart(key);
    if (kind === 'beam') return App.Beams.remove(key);
    if (kind === 'anchor') return App.Anchors.remove(key);
    if (kind === 'interface') return App.Interfaces.remove(key);
    if (kind === 'normal_load') return App.NormalLoads.remove(key);
    if (kind === 'line') return App.Lines.remove(key);
    if (kind === 'load') return App.Loads.remove(key);
    if (kind === 'condition') return App.BoundaryConditions.remove(key);
    if (kind === 'layer') return deleteLayer(key);
  }

  /* The frozen Delete of a layer, kept as it was: the stack closes the gap
     (App.deleteLayerById is the Soil layers window's), and the soil model goes to
     the server as one write. */
  function deleteLayer(key) {
    var layer = layerOf(key);
    if (!layer) return;
    var error = App.deleteLayerById(layer.id);
    if (error) {
      if (App.Command && App.Command.err) App.Command.err(error);
      return;
    }
    if (App.Command && App.Command.ok) App.Command.ok('Deleted soil layer ' + layer.name + '.');
    if (App.state && App.state.selection === key) App.selectObject(null);
    return App.commitSelectionEdit(null);
  }

  /* What the soil body `key` is a part of: its layer, or the soil surface (a custom
     part) a line cut. Once a line cuts a layer or a surface, the explorer shows only
     its parts, so a part's menu and panel are where the whole is deleted. */
  function bodyOwner(key) {
    var body = App.Lines && App.Lines.bodyOf(key);
    if (!body) return null;
    if (body.layer) {
      var layer = App.layerById ? App.layerById(body.layer) : null;
      return layer ? { kind: 'layer', noun: 'layer', key: 'soil_' + layer.id,
                       record: layer, name: layer.name } : null;
    }
    var part = partByKey(body.part);
    return part ? { kind: 'part', noun: in3D() ? 'soil volume' : 'soil surface',
                    key: part.key, record: part, name: part.label } : null;
  }

  /* What the Model explorer calls the soil body `key`. */
  function shownBodyName(key, body) {
    return ((App.PROJECT && App.PROJECT.soil_body_labels) || {})[key] || body.name;
  }

  /* Rename part, from the explorer menu and from the part's panel alike. The window starts
     with the name the Model explorer shows (`soil_body_labels`, such as `Sand · Part 2`),
     not the shorter name the part was given (`Part 2`), so what you see in the row is what
     you edit. OK on that name as it is changes nothing. A part is renamed on its own: its
     layer is renamed in the Soil layers window, and a cut soil surface needs no name of its
     own beside its parts'. */
  function renameBodyPart(key) {
    var body = App.Lines && App.Lines.bodyOf(key);
    if (!body) return;
    var shown = shownBodyName(key, body);
    return App.NameDialog.ask({ title: 'Rename part', value: shown,
                                help: 'Shown in the Model explorer.' })
      .then(function (name) {
        if (name === null || name === shown) return;
        // saveBody puts a refusal in the log itself.
        return App.Lines.saveBody(key, { name: name }).catch(function () {});
      });
  }

  /* The other parts of the layer or soil surface `key` is a part of, still in the model. */
  function otherParts(key) {
    var stem = key.split('__')[0];
    return ((App.PROJECT && App.PROJECT.soil_body_keys) || []).filter(function (other) {
      return other !== key && other.split('__')[0] === stem;
    });
  }

  /* One part alone goes (`session.remove_body`): the soil there becomes a void, and the
     rest of its layer or soil surface stays. The last part left is the whole of it. */
  function deleteBodyPart(key) {
    var owner = bodyOwner(key);
    var body = App.Lines && App.Lines.bodyOf(key);
    if (!owner || !body) return;
    return new Promise(function (resolve) {
      confirmDialog('Delete part',
        'This deletes ' + shownBodyName(key, body) + ', one part of ' + owner.noun + ' ' + owner.name +
        '. No soil is left there. The other parts of ' + owner.noun + ' ' + owner.name +
        ' stay.',
        function () { resolve(true); }, function () { resolve(false); });
    }).then(function (sure) { if (sure) return deleteBody(key); });
  }

  function deleteBody(key) {
    var label = ((App.PROJECT && App.PROJECT.soil_body_labels) || {})[key] || key;
    return deleteRequest('/api/project/bodies/' + encodeURIComponent(key), 'Delete failed')
      .then(function (reply) {
        if (reply && reply.project) App.Model.apply(reply.project);
        return App.Viewport.refresh();
      })
      .then(function () {
        if (App.state && App.state.selection === key && App.selectObject) {
          App.selectObject(null, 'tree');
        }
        if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
        if (App.Command && App.Command.ok) App.Command.ok('Deleted soil part ' + label + '.');
      })
      .catch(function (err) {
        if (App.Command && App.Command.err) {
          App.Command.err('Could not delete the soil part: ' + err.message);
        }
      });
  }

  /* The whole layer or soil surface goes, every part of it (Delete part takes one). */
  function deleteBodyOwner(key) {
    var owner = bodyOwner(key);
    if (!owner) return;
    var parts = ((App.PROJECT && App.PROJECT.soil_body_keys) || []).filter(function (other) {
      return other.split('__')[0] === owner.key;
    }).length;
    return new Promise(function (resolve) {
      confirmDialog('Delete ' + owner.noun,
        'This deletes ' + owner.noun + ' ' + owner.name + ' and all its ' + parts + ' parts.',
        function () { resolve(true); }, function () { resolve(false); });
    }).then(function (sure) {
      if (!sure) return;
      if (owner.kind === 'part') return deleteCustomPart(owner.key);
      var error = App.deleteLayerById(owner.record.id);
      if (error) { if (App.Command && App.Command.err) App.Command.err(error); return; }
      if (App.Command && App.Command.ok) App.Command.ok('Deleted soil layer ' + owner.name + '.');
      if (App.selectObject) App.selectObject(null, 'tree');
      return App.commitSelectionEdit(null);
    });
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
     stage". Ticking or unticking edits that stage alone
     (`App.Stages.setActive`): the other stages keep what they had, and a stage added
     afterwards starts with the state of the one before it. Every part keeps its row and
     its checkbox in every stage, so a part an earlier stage took out can be put back
     in any later one -- before this, a switched-off part was not drawn, so in the
     stages after it there was nothing left to click to bring it back.

     A group row (Sheet piles, Soil, Loads) sets every part under it, and shows a dash
     while they differ. A tick a stage inherited rather than set itself is drawn grey,
     so what this stage decided stands out from what it was handed. */
  function addStageChecks(mode) {
    var host = document.getElementById('tree-model');
    if (!host || mode !== 'staged' || !App.Stages || !App.PartColors) return;
    if (!selectedStageId()) return;
    var stageable = App.Stages.stageableKeys(App.PROJECT);
    var rows = host.querySelectorAll('.tree-row');
    var i = 0;
    (function walk(nodes) {
      (nodes || []).forEach(function (node) {
        var row = rows[i++];
        var keys = App.PartColors.keysUnder(node, stageable);
        if (row && keys.length) addStageCheck(row, keys, node);
        walk(node.children || []);
      });
    })((App.TREES && App.TREES[mode]) || []);
    paintStageChecks();
  }

  function addStageCheck(row, keys, node) {
    var check = document.createElement('span');
    check.className = 'tree-eye stage-check';
    check.dataset.keys = keys.join('\n');
    check.title = 'In the model in the selected stage';
    check.addEventListener('click', function (event) {
      event.stopPropagation();
      var stage = selectedStageId();
      if (!stage) return;
      var wanted = App.Stages.stateIn(App.PROJECT, stage, keys) !== 'on';
      var label = String(node.label || keys[0]).split('  ·  ')[0];
      saveStages(App.Stages.setActive(App.PROJECT, stage, keys, wanted),
                 label + (wanted ? ' switched on in ' : ' switched off in ')
                 + (stageById(stage) || {}).name + '.');
    });
    // In place of the eye, which in this mode would be a second, competing on/off.
    var eye = row.querySelector('.tree-eye');
    if (eye) row.replaceChild(check, eye);
    else row.insertBefore(check, row.firstChild);
  }

  /* ── The Model explorer's check box on a boundary condition ──────────────
     A condition row's check box says whether the condition is active (exported), as
     the Selection explorer's "Active" row and `kratos-cli boundary set --active` do,
     and a click switches it. It is not the eye: a condition is not drawn until the
     user selects its row or picks Show on it, so a box meaning "drawn" would be empty
     on every condition the model uses. The group row switches every condition under
     it and shows a dash while they differ. In Staged construction a condition row --
     support or water pressure -- keeps its stage check (addStageChecks), which says
     more: in the model in the selected stage. */
  function addConditionChecks(mode) {
    var host = document.getElementById('tree-model');
    if (!host || !App.BoundaryConditions) return;
    var rows = host.querySelectorAll('.tree-row');
    var i = 0;
    (function walk(nodes) {
      (nodes || []).forEach(function (node) {
        var row = rows[i++];
        var ids = conditionIdsUnder(node);
        if (row && ids.length && !row.querySelector('.stage-check')) {
          addConditionCheck(row, ids);
        }
        walk(node.children || []);
      });
    })((App.TREES && App.TREES[mode]) || []);
  }

  function conditionIdsUnder(node) {
    var isCondition = App.BoundaryConditions.isConditionKey;
    if (isCondition(node.obj)) return [node.obj];
    if (node.obj !== 'group:conditions') return [];
    return (node.children || []).map(function (child) { return child.obj; })
      .filter(isCondition);
  }

  function addConditionCheck(row, ids) {
    var state = App.BoundaryConditions.activeState(ids);
    var check = document.createElement('span');
    check.className = 'tree-eye condition-check' + (state === 'on' ? '' : ' ' + state);
    check.title = 'Active: exported to Kratos';
    check.addEventListener('click', function (event) {
      event.stopPropagation();
      App.BoundaryConditions.setActive(ids, state !== 'on').catch(function () {});
    });
    var eye = row.querySelector('.tree-eye');
    if (eye) row.replaceChild(check, eye);
    else row.insertBefore(check, row.firstChild);
  }

  /* After the stage or the sequence changed. The tree is mounted again only when the
     checkboxes have to appear (the first stages were just created) or go (the last
     stage was deleted, so the eyes come back); otherwise they are repainted in place.
     Never called from a mount, so it cannot loop. */
  function syncStageChecks() {
    if (typeof document === 'undefined') return;
    var host = document.getElementById('tree-model');
    if (!host || !App.state || App.state.mode !== 'staged') return;
    var stage = selectedStageId();
    var present = !!host.querySelector('.stage-check');
    if (!!stage !== present) {
      if (App.Explorer) App.Explorer.mountTree('staged');
      return;
    }
    paintStageChecks();
  }

  function paintStageChecks() {
    var host = document.getElementById('tree-model');
    if (!host) return;
    var stage = selectedStageId();
    Array.prototype.forEach.call(host.querySelectorAll('.stage-check'), function (check) {
      var keys = check.dataset.keys.split('\n');
      var state = stage ? App.Stages.stateIn(App.PROJECT, stage, keys) : 'on';
      check.classList.toggle('off', state === 'off');
      check.classList.toggle('mixed', state === 'mixed');
      check.classList.toggle('inherited', keys.length === 1 && !!stage
        && App.Stages.ownership(App.PROJECT, stage, keys[0]) === 'inherited');
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

  /* The boundary conditions come in two groups, each in its own mode: the
     mechanical ones (supports) in Structures, the flow ones (water pressure, seepage
     face) in Flow conditions. Each mode has a button that opens the window of one new
     condition of its group, and one that opens the window of all of its group.
     The rail button of the boundary conditions, in Structures mode. A new
     object each call: a rail item is one button, and the dimension gate below sets each
     flyout's items on their own. */
  function conditionTool() {
    return {
      icon: 'prescribed', action: 'createBoundaryCondition',
      tip: 'Create boundary condition',
      flyout: [
        { icon: 'prescribed', label: 'Create boundary condition…',
          action: 'createBoundaryCondition' },
        { icon: 'conditionlist', label: 'Mechanical boundary conditions…',
          action: 'mechanicalConditions' },
        { icon: 'prescribed', label: 'Line prescribed displacement',
          action: 'createSupportLine' },
        { icon: 'prescribed', label: 'Point prescribed displacement',
          action: 'createSupportPoint' }
      ]
    };
  }

  /* The Structures rail button of the window of all mechanical conditions. */
  function mechanicalConditionsTool() {
    return { icon: 'conditionlist', tip: 'Mechanical boundary conditions…',
             action: 'mechanicalConditions' };
  }

  /* The Flow conditions rail and menu: the water pressure conditions. The frozen
     "Create water level" draws nothing -- the water level is the `water` command and
     its explorer row -- so the rail's water tools are the conditions' instead: a new
     flow condition in its window, one drawn along a line or at a point, and the
     window of them all. */
  function installBoundaryConditionTools() {
    var flow = (App.RAILS || {}).flow;
    if (flow && !flow.some(function (tool) { return tool && tool.action === 'flowConditions'; })) {
      var drawTool = null;
      flow.forEach(function (tool) {
        if (tool && tool.icon === 'waterlevel' && !tool.action) {
          drawTool = tool;
          tool.action = 'createWaterPressureLine';
          tool.tip = 'Create water pressure line';
          tool.flyout = [
            { icon: 'waterlevel', label: 'Water pressure line',
              action: 'createWaterPressureLine' },
            { icon: 'waterlevel', label: 'Water pressure point',
              action: 'createWaterPressurePoint' },
            { icon: 'waterlevel', label: 'Seepage line',
              action: 'createSeepageLine' }
          ];
        }
      });
      // New in its window, then drawn, then the window of them all.
      var at = drawTool ? flow.indexOf(drawTool) : Math.min(2, flow.length);
      flow.splice(at, 0, { icon: 'watercondition', tip: 'Create flow boundary condition…',
                           action: 'createFlowCondition' });
      flow.splice(at + (drawTool ? 2 : 1), 0, { icon: 'conditionlist',
                                                tip: 'Flow boundary conditions…',
                                                action: 'flowConditions' });
    }
    var menus = App.MENUS || [];
    var flowMenu = menus.filter(function (m) { return m.label === 'Flow conditions'; })[0];
    if (flowMenu && !flowMenu.items.some(function (i) { return i && i.action === 'flowConditions'; })) {
      flowMenu.items.unshift(
        { label: 'Create flow boundary condition…', icon: 'watercondition',
          action: 'createFlowCondition' },
        { label: 'Flow boundary conditions…', icon: 'conditionlist',
          action: 'flowConditions' }, '-');
    }
    var structuresMenu = menus.filter(function (m) { return m.label === 'Structures'; })[0];
    var items = structuresMenu ? structuresMenu.items : [];
    items.slice().forEach(function (item) {
      if (item && item.label === 'Create prescribed displacement') {
        item.label = 'Mechanical boundary conditions…';
        item.icon = 'conditionlist';
        item.action = 'mechanicalConditions';
        item.sub = false;
        items.splice(items.indexOf(item), 0, { label: 'Create boundary condition…',
                                               icon: 'prescribed',
                                               action: 'createBoundaryCondition' });
      }
    });
  }

  /* `boundary ...`, typed. What to send is App.BoundaryConditions'
     (tested headless); this sends it and redraws. `false` when it is not this
     command. */
  function runBoundaryCommand(text) {
    if (!App.BoundaryConditions) return false;
    var answer = App.BoundaryConditions.command(text, App.PROJECT);
    if (answer === false) return false;
    if (App.Command.write) App.Command.write('echo', '> ' + String(text).trim());
    if (!answer.ok) { App.Command.err(answer.message); return true; }
    if (!answer.body) { App.Command.note(answer.message); return true; }
    App.Api.patch('/api/project/conditions', answer.body)
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

  function runPictureCommand(text) {
    if (!App.Picture) return false;
    return App.Picture.command(text) !== false;
  }

  function runFeedbackCommand(text) {
    if (!App.FeedbackDialog) return false;
    return App.FeedbackDialog.command(text) !== false;
  }

  /* `water ...`, typed: set, show or remove the project's water level. What to send is
     `App.WaterCommand`'s (tested headless); this sends it and redraws from the project
     the server stored. `false` when it is not this command. */
  function runWaterCommand(text) {
    if (!App.WaterCommand) return false;
    var answer = App.WaterCommand.command(text, {
      water: App.PROJECT ? App.PROJECT.water : null,
      // How far the model reaches, drawn soil above the layers included.
      domain: App.PROJECT ? App.Model.extentOf(App.PROJECT) : null,
      conditions: App.PROJECT ? App.PROJECT.boundary_conditions : null
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
  /* `script <file.py>`: the open model written as a model script
     (core/model/script_writer.py). What to send is App.ScriptCommand's; this sends it. */
  function runScriptCommand(text) {
    if (!App.ScriptCommand) return false;
    var answer = App.ScriptCommand.command(text);
    if (answer === false) return false;
    if (App.Command.write) App.Command.write('echo', '> ' + String(text).trim());
    if (!answer.ok) { App.Command.err(answer.message); return true; }
    App.Command.note(answer.message);
    App.Api.post('/api/project/script/save', answer.body)
      .then(function (result) {
        App.Command.ok(App.ScriptCommand.written(result.path || answer.body.path));
      })
      .catch(function (error) { App.Command.err(error.message); });
    return true;
  }

  /* `domain` / `domain --x FROM TO --y BOTTOM TOP --z FROM TO`, typed: show or set the
     size of the soil block, as File > Project properties… and `kratos-cli domain` do.
     What to send is App.DomainCommand's (tested headless); `setExtents` sends it.
     `false` when it is not this command. */
  function runDomainCommand(text) {
    if (!App.DomainCommand) return false;
    var answer = App.DomainCommand.command(text, App.PROJECT);
    if (answer === false) return false;
    if (App.Command.write) App.Command.write('echo', '> ' + String(text).trim());
    if (!answer.ok) { App.Command.err(answer.message); return true; }
    if (!answer.body) { App.Command.note(answer.message); return true; }
    setExtents(answer.body);
    return true;
  }

  function runUnitsCommand(text) {
    if (!App.Units) return false;
    var answer = App.Units.command(text, App.PROJECT);
    if (answer === false) return false;
    if (App.Command.write) App.Command.write('echo', '> ' + String(text).trim());
    if (!answer.ok) { App.Command.err(answer.message); return true; }
    if (!answer.body) { App.Command.note(answer.message); return true; }
    App.Command.note(answer.message);
    convertUnits(answer.body);
    return true;
  }

  /* PATCH /api/project/units with `body` ({ unit_system }): the server converts every
     value once (core/model/units.py `convert_project`). Then the model, the viewport
     and the explorer are redrawn, and the server's notes are shown. Shared by the
     `units` command and File > Project properties…. */
  function convertUnits(body) {
    return App.Api.patch('/api/project/units', body)
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
  }

  /* DELETE `path`, rejecting with the server's own `detail` when it refuses. A part a
     stage still uses is refused with a sentence naming the stage (backend/main.py
     `_without_custom_parts`), and that sentence is the whole of what the user needs. */
  function deleteRequest(path, fallback) {
    return fetch(App.Api.base + path, { method: 'DELETE' }).then(function (res) {
      if (res.ok) return res.json().then(App.Api.told);
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

  /* "Properties…" has been on this menu since the frozen mockup drew it, and did
     nothing for any kind: the callback below handled delete, rename and the eye, and
     let every other label fall off the end. A kind with a form of its own opens it --
     the same form the tool and the panel's Edit button open. The rest have no form;
     they keep their properties in the Selection explorer, so selecting the object is
     what "properties" means for them, and is at least what the label promises. */
  function openProperties(kind, key) {
    var owner = kind === 'load' ? App.Loads
      : kind === 'normal_load' ? App.NormalLoads
      : kind === 'line' ? App.Lines
      : kind === 'condition' ? App.BoundaryConditions
      : kind === 'beam' ? App.Beams
      : kind === 'anchor' ? App.Anchors
      : kind === 'interface' ? App.Interfaces : null;
    if (owner && owner.edit) return owner.edit(key);
    if (App.selectObject) App.selectObject(key, 'tree');
  }

  function onTreeContextMenu(event) {
    var row = event.target.closest && event.target.closest('.tree-row');
    var key = row && row.dataset.obj;
    var kind = objectKind(key);
    if (!kind) {
      // Not ours -- the frozen menu handles it (soil layers, groups, …), with its dead
      // rows taken out on the way. See dropFrozenTreeDeadRows.
      if (row) dropFrozenTreeDeadRows(key);
      return;
    }

    event.preventDefault();
    event.stopImmediatePropagation(); // the frozen row listener must not also open a menu

    // A soil body is a part of a layer or a soil surface: Rename part… and Delete part act
    // on the part, and Delete layer or Delete soil surface on the whole of it. The last
    // part left is the whole of it, so it goes with the second.
    var owner = kind === 'body' ? bodyOwner(key) : null;
    var edits = owner ? [
      { label: 'Rename part…', action: 'renameObject' },
      { label: 'Delete part', icon: 'delete', action: 'deletePart',
        disabled: !otherParts(key).length },
      { label: 'Delete ' + owner.noun, icon: 'delete', action: 'deleteOwner' }
    ] : [
      { label: 'Rename…', action: 'renameObject' },
      { label: 'Delete', icon: 'delete', action: 'deleteObject', disabled: kind === 'body' }
    ];
    App.Menu.openAt([
      { label: 'Zoom to object', icon: 'zoomfit', action: 'zoomFit' },
      { label: App.Viewport.isVisible(key) ? 'Hide' : 'Show', icon: 'eye' },
      '-'
    ].concat(edits, [
      '-',
      { label: 'Properties…', icon: 'settings' }
    ]), event.clientX, event.clientY, function (it) {
      if (it.action === 'deleteObject') return deleteObject(kind, key);
      if (it.action === 'renameObject') return renameObject(kind, key);
      if (it.action === 'deleteOwner') return deleteBodyOwner(key);
      if (it.action === 'deletePart') return deleteBodyPart(key);
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

  /* What a 2D section cannot serve. Mostly the camera -- a locked section view cannot
     orbit, take a preset angle or go perspective -- and a member, which exists in the
     solid model alone. `createSheetPile` is not here: it makes the wall of whichever
     dimension is open. */
  var THREE_D_ONLY = ['viewFront', 'viewTop', 'viewSide', 'viewIso',
                      'toggleProjection', 'navRotate', 'createMember'];

  /* And the mirror of it. An interface is a zero-thickness contact along a line in
     the section: every reference deck that has one is plane strain, and the 3D
     element is a surface with a different node layout and no fixture to pin it. */
  /* The rulers measure two named axes of one plane. In 3D the screen edges are three
     axes mixed by the orbit, so a number on an edge would be a number for nothing. */
  var TWO_D_ONLY = ['interface', 'createNormalLoad', 'drawLine', 'createLineByCoordinates',
                    'drawSoilSurface',
                    'toggleRuler', 'createSupportLine',
                    'createSupportPoint', 'createWaterPressureLine',
                    'createWaterPressurePoint', 'createSeepageLine'];

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

  /* Every menu row carrying `action`, submenus included: the Results menu keeps
     whole lists of its entries one level down, and a twin that hides in a submenu
     is still a twin the gating has to reach. */
  function menuItemsFor(action) {
    var found = [];
    function walk(items) {
      (items || []).forEach(function (item) {
        if (!item || typeof item !== 'object') return;
        if (item.action === action) found.push(item);
        if (Array.isArray(item.sub)) walk(item.sub);
      });
    }
    (App.MENUS || []).forEach(function (menu) { walk(menu.items); });
    return found;
  }

  /* ── What Styx does not do yet ───────────────────────────────────────────
     js/data.js draws the whole of the program the mockup imitates: wells and drains,
     plates and embedded beams, a tunnel designer, a Python interpreter, a macro
     library. Most of it has nothing behind it, and a button that looks ready and
     then answers "not available" in the log is a button the user learns to distrust
     -- along with every button beside it. A greyed one only clutters the menu. So a
     control with no live behaviour is taken out, in every place it appears, by one
     rule:

       a control works when it carries an action that is not on NOT_YET. A row with
       no action works only when it opens a real submenu -- an array the caller
       filled, not the mockup's placeholder `sub: true`.

     One predicate, asked by the menus, the rail, its flyouts and App.runAction alike,
     so a menu row and the button for the same tool cannot disagree about whether it
     exists. NOT_YET holds the actions that do run, but not what their label says:

       importSoilLayers   the mockup's import dialog, which imports nothing.
       drawPoint          draws a point, which the server then refuses: the creation
                          recipes (core/geometry/primitives.py) have no `point` kind.
       drawPolygon        "Create surface": a flat surface with no material. The mesh
                          leaves it out, with a note, so Kratos never sees it. Drawing
                          a surface is Soil > Create soil surface… now, which asks for
                          the material once the outline is drawn.
       drawBox,           a solid with no material, and the Selection explorer offers
       drawCylinder,      no way to give it one: the deck gets a body that no material
       importModel        is assigned to. Soil comes from Soil > Create soil surface…,
                          which asks for the material. */
  /* Help > Kratos documentation opens this. */
  var KRATOS_DOCS_URL =
    'https://deltares.github.io/Kratos-GeoMechanicsApplication-Documentation/user_documentation/';

  var NOT_YET = ['importSoilLayers', 'drawPoint', 'drawPolygon', 'drawBox', 'drawCylinder',
                 'importModel'];

  /* Separators ('-') and section captions are not controls, so they always pass. */
  function implemented(item) {
    if (!item || typeof item !== 'object' || item.title) return true;
    if (item.action) return NOT_YET.indexOf(item.action) < 0;
    return Array.isArray(item.sub);
  }

  /* The name a control goes by in the log. */
  function controlName(item) {
    return String(item.label || item.tip || item.action || '');
  }

  /* A separator with nothing on one side of it, or right after another, fences off
     nothing. Removing rows leaves such separators behind, so they go too. In place:
     js/menubar.js and js/toolbars.js read these very arrays. */
  function tidySeparators(items) {
    for (var i = items.length - 1; i >= 0; i--) {
      if (items[i] !== '-') continue;
      if (i === 0 || i === items.length - 1 || items[i + 1] === '-') items.splice(i, 1);
    }
    return items;
  }

  /* Takes every row of a menu or flyout that does nothing out of the list, in place,
     descending into real submenus. Rows that are greyed for another reason (2D or 3D,
     an empty undo history) are not touched: they work at other times. */
  function dropNotYet(items) {
    if (!Array.isArray(items)) return items;
    for (var i = items.length - 1; i >= 0; i--) {
      var item = items[i];
      if (!implemented(item)) { items.splice(i, 1); continue; }
      if (item && Array.isArray(item.sub)) dropNotYet(item.sub);
      if (item && Array.isArray(item.flyout)) dropNotYet(item.flyout);
    }
    return tidySeparators(items);
  }

  /* The rail's half of it, on the data js/toolbars.js mounts from, so a remount on a
     mode change draws the rail without them with no second pass.

     "Select" is the exception that is not one: the frozen rail gives it no action,
     but it is the pointer every mode starts with and picking works. Without an action
     it printed "drawing input is not implemented" on every click, so it is given
     `select`, which App.runAction answers by ending whatever draw or pick tool is
     running.

     It runs once, at the end of install(), when every live action has been hung on
     the frozen tools -- run earlier, it would take out Create line for still having
     none. */
  function dropRailTools() {
    Object.keys(App.RAILS || {}).forEach(function (mode) {
      (App.RAILS[mode] || []).forEach(function (tool) {
        if (tool && tool.icon === 'select' && !tool.action) tool.action = 'select';
      });
      dropNotYet(App.RAILS[mode]);
    });
  }

  /* A menu with nothing left in it would open an empty box, so it goes. In place, as
     js/menubar.js reads this very array. */
  function dropEverythingNotYet() {
    var menus = App.MENUS || [];
    menus.forEach(function (menu) { dropNotYet(menu.items); });
    var kept = menus.filter(function (menu) {
      return (menu.items || []).some(function (item) { return item !== '-'; });
    });
    menus.length = 0;
    Array.prototype.push.apply(menus, kept);
    dropRailTools();
  }

  /* The ticks in the menus, read from the state they describe rather than left at
     what js/data.js was written with. The frozen dispatcher flips the state and the
     toolbar button, never the menu row, so "Show axes triad" kept its ✓ over a
     hidden triad -- and in 2D "Perspective projection" was ticked over a section
     that is always drawn orthographic. */
  function syncCheckMarks() {
    var state = App.state || {};
    var marks = {
      toggleProjection: !in2D() && state.projection !== false,
      toggleGrid: state.grid !== false,
      toggleTriad: shownById('vp-triad'),
      toggleCmd: shownById('cmdpanel')
    };
    Object.keys(marks).forEach(function (action) {
      menuItemsFor(action).forEach(function (item) { item.checked = marks[action]; });
    });
    return marks;
  }

  /* The triad and the command panel are hidden by an inline `display: none`
     (js/app.js:180, :273) and by nothing else. Absent markup -- the test page --
     counts as shown, which is what js/data.js starts them as. */
  function shownById(id) {
    var node = typeof document !== 'undefined' && document.getElementById(id);
    return !node || node.style.display !== 'none';
  }

  /* The viewport's right-click menu is built fresh on every open (js/app.js:73), from
     a list that knows nothing of the dimension: it offered "Isometric view" and a
     ticked "Perspective projection" over a 2D section, both greyed on the toolbar. */
  function gateViewportItems(items) {
    (items || []).forEach(function (item) {
      if (!item || typeof item !== 'object' || !item.action) return;
      if (!availableNow(item.action)) item.disabled = true;
      if (item.action === 'toggleProjection') {
        item.checked = !in2D() && (App.state || {}).projection !== false;
      }
    });
    return items;
  }

  /* The frozen tree menu (js/explorer.js:102) ends in a "Properties…" that its
     callback lets fall off the end for every row, and greys "Rename…" and "Delete"
     with no action on every row that is not a soil layer. The live rows get a menu of
     their own with working ones (onTreeContextMenu); for the rest, the frozen row
     listener runs right after this, inside the same event, and calls App.Menu.openAt
     -- so a one-shot openAt is lent for that call and takes those dead rows out on
     the way through. "Hide"/"Show" has no action either, but the frozen callback
     answers it by its label, so it stays. A soil's row also gets the water it takes,
     as in the viewport. The timer puts the real openAt back should the frozen
     listener not run. */
  function dropFrozenTreeDeadRows(key) {
    if (!App.Menu || typeof App.Menu.openAt !== 'function' || App.Menu.openAt.__tree) return;
    var menu = App.Menu;
    var openAt = menu.openAt;
    var lent = function (items, x, y, onPick) {
      menu.openAt = openAt;
      var kept = tidySeparators((items || []).filter(function (item) {
        return !item || typeof item !== 'object' || item.title || item.action
          || /^(Hide|Show)$/.test(item.label || '');
      }));
      // A soil's row in Flow conditions: the water it takes, as in the viewport.
      return openAt(withSoilWaterRows(kept, key), x, y, function (item) {
        if (item && item.action === 'soilWater') {
          return App.BoundaryConditions.setSoilWater(item.soilKey, item.soilWater);
        }
        if (onPick) return onPick(item);
        return App.runAction(item);
      });
    };
    lent.__tree = true;
    menu.openAt = lent;
    setTimeout(function () { if (menu.openAt === lent) menu.openAt = openAt; }, 0);
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
    ['drawLine'],
    ['plate', 'beam', 'embedded', 'createSheetPile', 'createMember', 'createAnchor',
     'interface'],
    ['createLoad', 'createBoundaryCondition', 'mechanicalConditions'],
    ['tunnel']
  ];

  /* The frozen node-to-node anchor tool draws nothing -- frontend/js/anchors.js owns
     anchors now -- so it would only stand beside the real one as a dead twin. */
  var STRUCTURES_RAIL_DROPPED = ['anchor'];

  /* A tool is named by its action; the frozen mockup leaves most of them without
     one, and there the icon is the only name it has. */
  function railKey(tool) { return (tool && (tool.action || tool.icon)) || ''; }

  /* The Soil rail opens on what a soil is made of: the material sets, then the
     layers that use them. */
  var SOIL_RAIL_GROUPS = [
    ['select'],
    ['materials', 'soilLayers'],
    ['createSoilVolume']
  ];

  /* The frozen "Create borehole" (js/data.js): a layer has one top and one bottom,
     so there is no borehole to make. */
  var SOIL_DROPPED = ['createBorehole'];

  /* The status bar's words for Soil mode, in place of the frozen ones about boreholes. */
  var SOIL_HINT = 'Soil mode — define the soil materials and the soil layers.';

  function orderStructuresRail(tools) {
    return orderRail(tools, STRUCTURES_RAIL_GROUPS, STRUCTURES_RAIL_DROPPED);
  }

  function orderSoilRail(tools) { return orderRail(tools, SOIL_RAIL_GROUPS, SOIL_DROPPED); }

  /* The Soil menu reads as its rail does. */
  var SOIL_MENU_GROUPS = [
    ['materials', 'soilLayers'],
    ['createSoilVolume']
  ];

  function orderSoilMenu(items) { return orderRail(items, SOIL_MENU_GROUPS, SOIL_DROPPED); }

  /* Moves the entry whose key is `moving` to just before the one whose key is
     `anchor`, in place: the frozen tabs and menu bar read these very arrays. Leaves
     the list alone if either entry is missing or the order is already right. */
  function moveBefore(list, keyOf, moving, anchor) {
    var keys = (list || []).map(function (item) { return item && keyOf(item); });
    var from = keys.indexOf(moving);
    var to = keys.indexOf(anchor);
    if (from < 0 || to < 0 || from < to) return list;
    list.splice(to, 0, list.splice(from, 1)[0]);
    return list;
  }

  /* A water condition is meshed into the model Kratos reads, so the water is set
     before the mesh is made: Flow conditions comes before Mesh, on the mode tabs
     (and so on Ctrl+1..5, which follow App.MODES) and in the menu bar. Water
     conditions are model input, so the tab sits with Soil and Structures under
     Geometry rather than under Calculation. */
  function orderFlowBeforeMesh() {
    moveBefore(App.MODES, function (m) { return m.id; }, 'flow', 'mesh');
    var soil = App.MODES.filter(function (m) { return m.id === 'soil'; })[0];
    App.MODES.forEach(function (m) {
      if (m.id === 'flow' && soil) m.group = soil.group;
    });
    moveBefore(App.MENUS, function (m) { return m.label; }, 'Flow conditions', 'Mesh');
  }

  /* Pure, and tolerant of a rail this file has never seen: a tool that matches no
     group keeps its place in a trailing group rather than disappearing. */
  function orderRail(tools, groupKeys, dropped) {
    var rest = (tools || []).filter(function (tool) { return tool && tool !== '-'; });
    var groups = [];

    groupKeys.forEach(function (keys) {
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
      return dropped.indexOf(railKey(tool)) < 0;
    });
    if (unknown.length) groups.push(unknown);

    return groups.reduce(function (rail, group, i) {
      if (i) rail.push('-');
      return rail.concat(group);
    }, []);
  }

  /* The left rail is remounted whole on every mode change and its buttons carry no
     action attribute, so the tools are matched positionally against App.RAILS -- the
     same order js/toolbars.js:86-92 renders them in -- for the mode that was mounted,
     when the mount says which, since that is the list the buttons were drawn from. */
  function gateRail(mode) {
    var rail = document.getElementById('toolrail');
    var tools = (App.RAILS || {})[mode || (App.state || {}).mode] || [];
    if (!rail) return;
    var buttons = rail.querySelectorAll('.rail-btn');
    var i = 0;
    tools.forEach(function (tool) {
      if (tool === '-') return;
      var button = buttons[i++];
      if (!button) return;
      // The frozen rail draws an icon only. Named here, so a test, the tutorial script
      // and a screen reader can find a tool without counting buttons. `data-tool` is
      // set on every tool (by its icon when it has no action yet).
      if (tool.action) button.setAttribute('data-action', tool.action);
      else button.removeAttribute('data-action');
      button.setAttribute('data-tool', tool.action || tool.icon);
      if (tool.tip) button.setAttribute('aria-label', tool.tip);
      // A tool of the other dimension is left off the rail, not drawn greyed: in
      // 2D there is no box or member to make, and in 3D no line or interface. It
      // comes back when the model switches. Calculate still greys while it runs.
      var wrongDimension = !availableNow(tool.action);
      var off = wrongDimension || calculateOff(tool);
      if (tool.action === 'calculate') paintCalculating(button);
      button.hidden = wrongDimension;
      button.classList.toggle('disabled', off);
      button.disabled = off;
    });
    hideStraySeparators(rail);
  }

  /* A separator with nothing shown between it and the one before it (or the top of
     the rail), or nothing after it, would draw two lines in a row or a line at the
     end: hidden with the tools around it. */
  function hideStraySeparators(rail) {
    var last = null;
    var seen = false;
    Array.prototype.forEach.call(rail.children, function (child) {
      if (child.classList.contains('rail-sep')) {
        child.hidden = !seen;
        if (seen) last = child;
        seen = false;
      } else if (!child.hidden) {
        seen = true;
      }
    });
    if (!seen && last) last.hidden = true;
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
    // A support drawn along a line or at a point is plane strain; the windows are not.
    ['structures', 'mesh'].forEach(function (mode) {
      (((App.RAILS || {})[mode] || []).filter(function (tool) {
        return tool && tool.icon === 'prescribed';
      })[0] || { flyout: [] }).flyout.forEach(function (item) {
        item.disabled = TWO_D_ONLY.indexOf(item.action) >= 0 ? !is2d : false;
      });
    });
    // The sheet-pile flyout names a kind for each dimension. The one the open model
    // cannot hold is greyed like every other tool of the wrong dimension, rather than
    // offered and then refused by App.Beams.start.
    var sheetPile = (((App.RAILS || {}).structures || []).filter(function (tool) {
      return tool && tool.action === 'createSheetPile';
    })[0] || {}).flyout || [];
    sheetPile.forEach(function (item) {
      item.disabled = item.beamKind === 'beam' ? !is2d : !!is2d;
    });

    // An outline is drawn in the section; a 3D body has no plane to draw it on, so
    // there it is typed. Greyed rather than dropped: the flyout is mounted once.
    (((App.RAILS || {}).soil || []).filter(function (tool) {
      return tool && tool.action === 'createSoilVolume';
    })[0] || { flyout: [] }).flyout.forEach(function (item) {
      item.disabled = TWO_D_ONLY.indexOf(item.action) >= 0 ? !is2d : false;
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

    // A section is never perspective, so the menu's tick goes with the toolbar's.
    syncCheckMarks();
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

  /* ── Calculate: when it can run, and while it runs ─────────────────────────
     Five ways in -- the toolbar's green button, the Stages menu, the Staged
     construction rail, F9 and `calculate` in the command box -- and one answer for
     all of them, `App.Calculate.state` (js/calculate.js). A button that cannot do
     anything yet is greyed out with its reason as its tip, rather than pressed and
     then explained in the log; and one that is already doing it says so, spins, and
     cannot be pressed again for the hour the solver may take.

     Greying is not the guard. A menu opened before the project changed, F9 and the
     command box have no button to grey, so App.runAction and the command box ask the
     same question again and refuse with the same reason.

     The toolbar button is greyed with the class and `aria-disabled`, not the native
     `disabled`: a disabled button gets no mouse events, so it could not show the tip
     that says why it is grey, and css/live.css gives this one its pointer back. Its
     click still reaches App.runAction, which refuses it. Playwright and screen
     readers both read `aria-disabled` as disabled.

     The tip is live. js/ui.js attachTip reads its text when the tip is shown, through
     `textContent`, so an object whose toString asks the state now is the tip for
     every state the button will go through, without remounting the toolbar. The
     entry's own `tip` stays the string it was, for everything else that reads it.

     The rail button is mounted afresh on every mode change and its tip is joined into
     a string at mount, so it is greyed (gateRail) but keeps its plain tip.

     While a run goes on, the toolbar button and the Stages menu's item are Stop: a
     red square and "Stop", which asks and then stops Kratos (`App.Calculate.askStop`).
     Once asked, they say "Stopping…" until the run answers. F9 and the rail do not
     stop a run: a key pressed twice must not end an hour of work. */

  var CALCULATE_TIP = 'Calculate (F9): mesh the model and run it in Kratos.';

  /* When js/calculate.js is not there -- the tests replace it with a stub that only
     runs -- nothing is greyed: the refusal is not this file's to invent. */
  function calculateNow() {
    var calc = App.Calculate;
    if (!calc || typeof calc.state !== 'function') {
      return { ok: true, running: false, reason: '' };
    }
    return calc.state(App.PROJECT, typeof calc.running === 'function' && calc.running());
  }

  function calculateOff(tool) {
    return !!tool && tool.action === 'calculate' && !calculateNow().ok;
  }

  function stoppingNow() {
    var calc = App.Calculate;
    return !!(calc && typeof calc.stopping === 'function' && calc.stopping());
  }

  /* True while a run goes on and no stop has been asked: the button is Stop. */
  function stoppable(now) {
    return !!now.running && !stoppingNow()
      && !!(App.Calculate && typeof App.Calculate.askStop === 'function');
  }

  /* The toolbar button is Stop while a run goes on; the rail button only spins. */
  function paintCalculating(button) {
    var now = calculateNow();
    var busy = !!now.running;
    var stop = stoppable(now) && !button.classList.contains('rail-btn');
    button.classList.toggle('calculating', busy && !stop);
    button.classList.toggle('stop-calc', stop);
    if (busy) button.setAttribute('aria-busy', 'true');
    else button.removeAttribute('aria-busy');
  }

  var calculateTip = {
    toString: function () {
      var now = calculateNow();
      if (stoppable(now)) return App.Calculate.STOP_TIP || 'Stop the calculation.';
      return now.ok ? CALCULATE_TIP : now.reason;
    }
  };

  function calculateEntry() {
    return (App.TOOLBAR || []).filter(function (t) {
      return t && typeof t === 'object' && t.action === 'calculate';
    })[0] || null;
  }

  /* Said once, in the log, where a press was refused. */
  function refuseCalculate() {
    var now = calculateNow();
    if (now.ok) return false;
    if (App.Command && App.Command.note) App.Command.note(now.reason);
    return true;
  }

  function syncCalculate() {
    var now = calculateNow();
    var stop = stoppable(now);
    var off = !now.ok && !stop;
    var busyLabel = stop ? 'Stop' : stoppingNow() ? 'Stopping…' : 'Calculating…';
    var entry = calculateEntry();
    // On the data as well as the button, so a remount of the toolbar keeps it.
    if (entry) entry.disabled = off;

    var button = typeof document !== 'undefined'
      && document.querySelector('#maintoolbar .tbtn[data-action="calculate"]');
    if (button) {
      button.classList.toggle('disabled', off);
      button.setAttribute('aria-disabled', off ? 'true' : 'false');
      paintCalculating(button);
      var label = button.querySelector('span');
      if (label) {
        label.textContent = now.running ? busyLabel : ((entry && entry.wide) || 'Calculate');
      }
    }

    menuItemsFor('calculate').forEach(function (item) {
      if (item.calculateLabel === undefined) item.calculateLabel = item.label;
      item.disabled = off;
      item.label = now.running ? (stop ? 'Stop calculation' : busyLabel) : item.calculateLabel;
    });

    gateRail();
    return now;
  }

  /* Re-asked whenever the answer can change: a project arrives or changes (every
     change goes through App.Model.apply; the first load does not, js/model.js:266
     calls its own `apply`, so App.Model.load is hooked too), a run starts or ends,
     and the toolbar or the rail is mounted again. And once now, so the button is
     drawn greyed before the project has arrived rather than live for a moment.

     Each hook is marked where it is made, because install() runs more than once in
     the tests: the model hooks on the function, which the tests swap for stubs, and
     the toolbar's on App.Toolbars, so the tip is attached once whoever else wraps
     mountMain. */
  function installCalculateState() {
    var model = App.Model;
    if (model && typeof model.apply === 'function' && !model.apply.__calculate) {
      var appliedBefore = model.apply;
      model.apply = function () {
        var result = appliedBefore.apply(this, arguments);
        syncCalculate();
        return result;
      };
      model.apply.__calculate = true;
    }
    if (model && typeof model.load === 'function' && !model.load.__calculate) {
      var loadedBefore = model.load;
      model.load = function () {
        var out = loadedBefore.apply(this, arguments);
        if (out && typeof out.then === 'function') {
          out.then(function () { syncCalculate(); }, function () { syncCalculate(); });
        }
        return out;
      };
      model.load.__calculate = true;
    }

    var bars = App.Toolbars;
    if (bars && typeof bars.mountMain === 'function' && !bars.__calculateTip) {
      bars.__calculateTip = true;
      var mountedBefore = bars.mountMain;
      bars.mountMain = function () {
        // Mounted without its static tip, then given the live one.
        var entry = calculateEntry();
        var tip = entry ? entry.tip : null;
        if (entry) entry.tip = null;
        try { mountedBefore.apply(this, arguments); }
        finally { if (entry) entry.tip = tip; }
        var button = document.querySelector('#maintoolbar .tbtn[data-action="calculate"]');
        if (button && App.UI && App.UI.attachTip) App.UI.attachTip(button, calculateTip);
        syncCalculate();
      };
    }

    if (App.Calculate && typeof App.Calculate.onChange === 'function') {
      App.Calculate.onChange(syncCalculate);
    }
    if (App.Calculate && typeof App.Calculate.onStop === 'function') {
      App.Calculate.onStop(syncCalculate);
    }
    syncCalculate();
  }

  /* ── New, open, save ─────────────────────────────────────────────────────── */

  /* An app window with OK and Cancel. `onCancel` (optional) is called when it closes
     without OK: by Cancel, the close button or Escape. */
  function confirmDialog(title, text, onConfirm, onCancel) {
    if (!App.Dialogs || !App.Dialogs.open) return onConfirm();
    var confirmed = false;
    App.Dialogs.open({
      title: title, width: 440, height: 220,
      buttons: [{ label: 'OK', primary: true,
                  onClick: function () { confirmed = true; return onConfirm(); } },
                { label: 'Cancel' }],
      onClose: function () { if (!confirmed && onCancel) onCancel(); },
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
  function adoptProject(project, message, keepCommands) {
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
    // So were the boundary conditions shown: the next model's open hidden, as any does.
    if (App.Viewport.forgetConditionEyes) App.Viewport.forgetConditionEyes();

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
    wipeSession(keepCommands);

    return Promise.resolve(App.Viewport.refresh()).then(function () {
      if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
      if (App.Command) App.Command.ok(message);
    });
  }

  /* What the session still shows of the document that was open goes with it: the
     command log, the Model history tab, the commands the arrow keys bring back, the
     selection, the mesh, the node and element ID labels and the Convergence window of
     a finished run. A run still going keeps its window: Stop is in it. The next
     document starts as clean as a fresh start of the app, without the welcome text.
     `run <file.py>` keeps the commands: the user typed them in this session, and the
     arrow keys bring the run back to run the edited file again. */
  function wipeSession(keepCommands) {
    if (!keepCommands) {
      cmdHistory.length = 0;
      cmdIndex = 0;
    }
    if (!keepCommands && typeof document !== 'undefined') {
      ['cmd-log', 'cmd-history'].forEach(function (id) {
        var box = document.getElementById(id);
        if (box) box.textContent = '';
      });
      var entry = document.getElementById('cmd-entry');
      if (entry) entry.value = '';
    }
    var viewport = App.Viewport || {};
    if (App.MeshLabels && viewport.setLabels) {
      App.MeshLabels.KINDS.forEach(function (kind) { viewport.setLabels(kind, false); });
    }
    if (viewport.clearMesh) viewport.clearMesh();
    if (App.state && App.state.selection && App.selectObject) App.selectObject(null);
    var running = App.Calculate && App.Calculate.running && App.Calculate.running();
    if (App.ConvergenceWindow && App.ConvergenceWindow.close && !running) {
      App.ConvergenceWindow.close();
    }
  }

  /* An empty site, not the seeded demo -- the server owns what "empty" means, and a
     second definition here would be one to keep in step. `name`, from the New project
     window, is what `kratos-cli new --name` sets. */
  function newProject(name) {
    return App.Api.post('/api/project/new')
      .then(function (result) {
        var project = result.project;
        if (!name || name === project.name) return project;
        return App.Api.put('/api/project', Object.assign({}, project, { name: name }));
      })
      .then(function (project) {
        return adoptProject(project, 'New project started — empty site.');
      })
      .catch(function (error) {
        if (App.Command) App.Command.err('Could not start a new project: ' + error.message);
      });
  }

  /* The model's extents in Project properties: [field, label, domain key, help]. In 2D
     the out-of-plane z is left out, as the Selection explorer leaves it out. */
  var EXTENTS = [
    ['x0', 'x min', 'x0', null],
    ['x1', 'x max', 'x1', null],
    ['y0', 'y min', 'y_bottom', 'The bottom of the soil block.'],
    ['y1', 'y max', 'y_top', 'The ground level: the top of the first soil layer.'],
    ['z0', 'z min', 'z0', null],
    ['z1', 'z max', 'z1', null]
  ];

  function extentsShown(project) {
    return EXTENTS.filter(function (e) {
      return project.dimension !== 2 || e[0].charAt(0) !== 'z';
    });
  }

  function numberInMetres(text) {
    return isFinite(Number(text)) ? null : 'Type a number, in m. The decimal sign is a point.';
  }

  /* The axes whose extent the window changed, as PATCH /api/project/domain and
     `kratos-cli domain --x --y --z` take them: { x: [from, to], ... }. */
  function changedExtents(project, values) {
    var domain = project.domain || {};
    var update = {};
    ['x', 'y', 'z'].forEach(function (axis) {
      var lo = axis + '0', hi = axis + '1';
      if (values[lo] === undefined || values[hi] === undefined) return;
      var pair = [Number(values[lo]), Number(values[hi])];
      var keys = EXTENTS.filter(function (e) { return e[0] === lo || e[0] === hi; })
        .map(function (e) { return e[2]; });
      if (pair[0] !== domain[keys[0]] || pair[1] !== domain[keys[1]]) update[axis] = pair;
    });
    return update;
  }

  /* PATCH /api/project/domain with `update` ({ x: [from, to], ... }), then the model,
     the viewport and the explorer are redrawn. Shared by File > Project properties…
     and the `domain` command. */
  function setExtents(update) {
    return App.Api.patch('/api/project/domain', update)
      .then(function (result) {
        App.Model.apply(result.project);
        return App.Viewport.refresh().then(function () { return result; });
      })
      .then(function (result) {
        if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
        var d = result.project.domain;
        if (App.Command) {
          App.Command.ok('Size of the soil block: x ' + d.x0 + ' to ' + d.x1 + ' m, y '
                         + d.y_bottom + ' to ' + d.y_top + ' m.');
          (result.notes || []).forEach(function (note) { App.Command.note(note); });
        }
        return true;
      })
      .catch(function (error) {
        if (App.Command) App.Command.err('Could not change the size: ' + error.message);
        return false;
      });
  }

  /* File > Project properties…: the project's name, as `kratos-cli set FILE name ...`
     sets it, the size of the soil block, as `kratos-cli domain FILE --x --y --z` sets it,
     the gravitational acceleration g, as `kratos-cli gravity FILE G` sets it, and the
     unit system, as `kratos-cli units FILE SYSTEM` (or the `units` command) sets it.
     Name and g go through the whole-project PUT; a new size then goes through PATCH
     /api/project/domain, which moves the top of the first layer and the bottom of the
     last with it; a new unit system last through PATCH /api/project/units, which
     converts every value once. Undo takes back each one like any edit. */
  function projectProperties() {
    var project = App.PROJECT || {};
    var name = project.name || '';
    var g = typeof project.gravity_acceleration === 'number' ? project.gravity_acceleration
                                                             : App.Units.gravity('SI');
    var system = App.Units.system(project);
    var domain = project.domain || {};
    var shown = extentsShown(project);
    return App.NameDialog.form({
      title: 'Project properties',
      fields: [
        { name: 'name', label: 'Project name', value: name, empty: 'Type a name.',
          help: 'Shown in the title bar, and the name Save gives the file.' }
      ].concat(shown.map(function (e) {
        return { name: e[0], label: e[1], value: domain[e[2]], unit: 'm', help: e[3],
                 empty: 'Type the ' + e[1] + ' of the soil block, in m.',
                 check: numberInMetres };
      })).concat([
        { name: 'gravity_acceleration', label: 'Gravity', value: g, unit: 'm/s²',
          empty: 'Type the gravitational acceleration, in m/s².',
          check: function (text) {
            var value = Number(text);
            return isFinite(value) && value > 0 ? null : 'Gravity is a number above 0 m/s².';
          },
          help: 'The self weight of every body. The water keeps its specific weight.' },
        { name: 'unit_system', label: 'Unit system', value: system,
          choices: App.Units.systems().map(function (s) {
            return { value: s.name, label: s.title };
          }),
          help: 'A change converts every value: a cohesion of 5000 Pa becomes 5 kPa.' }
      ]),
      check: function (values) {
        var axes = shown.filter(function (e) { return e[0].charAt(1) === '0'; })
          .map(function (e) { return e[0].charAt(0); });
        var bad = axes.filter(function (axis) {
          return !(Number(values[axis + '1']) > Number(values[axis + '0']));
        })[0];
        return bad ? bad + ' max must be above ' + bad + ' min.' : null;
      }
    }).then(function (values) {
      if (values === null) return;
      var newG = Number(values.gravity_acceleration);
      var newSystem = values.unit_system || system;
      var extents = changedExtents(project, values);
      var resize = Object.keys(extents).length > 0;
      var said = [];
      if (values.name !== name) said.push('Project name: ' + values.name + '.');
      if (newG !== g) said.push('Gravity: g = ' + newG + ' m/s².');
      var convert = newSystem !== system;
      if (!said.length && !resize && !convert) return;
      var put = Promise.resolve(true);
      if (said.length) {
        // Only what changed: a rename leaves the project's gravity fields as they are.
        var edited = JSON.parse(JSON.stringify(App.PROJECT));
        edited.name = values.name;
        if (newG !== g) edited.gravity_acceleration = newG;
        put = App.Api.put('/api/project', edited).then(function (saved) {
          App.Model.apply(saved);
          if (App.Command) App.Command.ok(said.join(' '));
          return true;
        }).catch(function (error) {
          if (App.Command) {
            App.Command.err('Could not change the project properties: ' + error.message);
          }
          return false;
        });
      }
      return put.then(function (done) {
        if (!done || !resize) return done;
        // The line the command box takes for the same edit (`runDomainCommand`).
        if (App.Command && App.Command.write) {
          App.Command.write('echo', '> ' + App.DomainCommand.line(extents));
        }
        return setExtents(extents);
      }).then(function (done) {
        if (!done || !convert) return;
        if (App.Command) {
          if (App.Command.write) App.Command.write('echo', '> units ' + newSystem);
          App.Command.note('Converting every value from ' + App.Units.title(system)
                           + ' to ' + App.Units.title(newSystem) + '…');
        }
        return convertUnits({ unit_system: newSystem });
      });
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
        // one the app must not half-load, and the message says which field. It also
        // says what opening an old file changes about its calculation.
        return App.Api.post('/api/project/open', opened)
          .then(function (result) {
            return Promise.resolve(adoptProject(result.project,
                                                'Opened project: ' + file.name))
              .then(function () {
                (result.notes || []).forEach(function (note) {
                  if (App.Command.warn) App.Command.warn(note); else App.Command.note(note);
                });
              });
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

  /* The picture rows. Copying needs localhost or https, so on a LAN address the row is
     grey rather than a click that answers with an error. */
  function withPictureRows(items) {
    if (!App.Picture) return items;
    return items.concat(['-',
      { label: 'Copy picture', icon: 'copy', action: 'copyPicture', disabled: !App.Picture.canCopy() },
      { label: 'Save picture…', icon: 'camera', action: 'savePicture' }]);
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
      var mode = App.state && App.state.mode;
      // The numbers are drawn on a mesh that is on screen. A tab that does not draw the
      // mesh there is keeps them on for the tabs that do.
      if (!count && mode !== 'mesh' && mode !== 'results'
          && App.Viewport.hasMesh && App.Viewport.hasMesh()) {
        return App.Command.note(noun + ' IDs are on. They are drawn on the mesh: '
          + 'in the Mesh tab and in Results.');
      }
      if (!count && mode === 'results') {
        App.Viewport.setLabels(kind, false);
        return App.Command.note('Nothing to label — open a result first.');
      }
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
        openAt(gateViewportItems(withPictureRows(withSoilWaterRows(
          withStageRows(withIntersectRows(withLabelRows(items), key), key), key))),
               x, y, function (item) {
          if (item && item.action === 'intersectSurface') {
            return intersectSurfaces(item.surfaceKey, item.otherKey);
          }
          if (item && item.action === 'soilWater') {
            return App.BoundaryConditions.setSoilWater(item.soilKey, item.soilWater);
          }
          if (item && item.action === 'stageActivate') {
            return switchPartInStage(item.stageKey, true);
          }
          if (item && item.action === 'stageDeactivate') {
            return switchPartInStage(item.stageKey, false);
          }
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

  /* ── The stages panel ────────────────────────────────────────────────────
     `Explorer.mountPhases` (js/explorer.js:281) already draws everything the
     screenshots show: an indented list, a state dot per row, and a property grid for
     the selected stage. What it draws them from is `App.PHASES`, seven hardcoded rows
     in js/data.js:559 describing a project nobody has open -- so the panel was a
     picture of a stage list rather than a stage list.

     Replaced wholesale rather than patched around, because almost every line of it
     reads the frozen globals. What is kept is the markup and the class names, which
     is what the stylesheet is written against (css/components.css:214-226).

     `App.Stages` is the model; this is only the drawing and the buttons. Every edit
     goes the same way round: build a new list, PATCH it, take the stored project
     back. Nothing is mutated in place, so a rejected save leaves the panel showing
     what the server actually holds rather than what the user hoped for. */

  /* What the last calculation reported, for the state dots. `{completed: n}`, worked
     out from the stage the run died in: everything before it finished. A run that
     succeeded completed all of them; a run that never reached a stage completed
     none. Cleared when the stage list changes, because a dot describing a sequence
     that no longer exists is worse than a grey one. */
  var stageRun = null;

  function rememberRun(result) {
    var total = ((App.PROJECT && App.PROJECT.stages) || []).length;
    if (!result) { stageRun = null; }
    else if (result.ok) { stageRun = { completed: total }; }
    else if (result.stopped) {
      stageRun = { completed: result.stage ? result.stage.index - 1 : 0, stopped: true };
    }
    else if (result.stage) {
      stageRun = { completed: result.stage.index - 1, failed: true,
                   error: result.error || null };
    }
    else { stageRun = { completed: 0, failed: true, error: result.error || null }; }
    mountLiveStages();
  }

  function selectedStageId() {
    return App.Stages.selectedId(App.PROJECT, App.state && App.state.phase);
  }

  function stageById(id) {
    return ((App.PROJECT && App.PROJECT.stages) || []).filter(function (ph) {
      return ph.id === id;
    })[0] || null;
  }

  /* Send a stage list and adopt whatever comes back.

     The server is the authority on what a valid sequence is -- it refuses a branch, a
     part key nothing answers to, and a stage that both activates and deactivates the
     same thing -- so the reply replaces the list rather than the request confirming
     it. On a refusal the project is reloaded, which is what puts the panel back in
     step after an edit that could not be kept. */
  function saveStages(list, note) {
    return App.Api.patch('/api/project/stages', { stages: list })
      .then(function (response) {
        App.Model.apply(response.project);
        // The sequence has changed, so what the last run reached no longer maps onto
        // it. Better a row of grey dots than a green one against a stage that did
        // not exist when the run happened.
        stageRun = null;
        if (note) App.Command.ok(note);
        mountLiveStages();
        return App.Viewport.refresh();
      })
      .catch(function (error) {
        App.Command.err(error.message);
        return App.Model.load().then(mountLiveStages);
      });
  }

  /* The stage buttons: add, insert, duplicate and delete, on the selected stage.
     `new`/`copy`/`delete` are the mockup's own icon names (js/data.js:63-76); `phase`
     stands in for insert, which has no icon of its own in the frozen set. */
  var STAGE_ACTIONS = [
    ['new', 'Add stage', function () {
      return App.Stages.added(App.PROJECT);
    }, 'Stage added.', 'addStage'],
    ['phase', 'Insert stage above the selected one', function (selected) {
      return App.Stages.inserted(App.PROJECT, selected);
    }, 'Stage inserted.', 'insertStage', 'Nothing goes before the initial stage.'],
    ['copy', 'Duplicate the selected stage', function (selected) {
      return App.Stages.copied(App.PROJECT, selected);
    }, 'Stage duplicated.', 'duplicateStage'],
    ['delete', 'Delete the selected stage', function (selected) {
      return App.Stages.removed(App.PROJECT, selected);
    }, 'Stage deleted.', 'deleteStage', 'The initial stage is always there.']
  ];

  /* The stage buttons, added to `bar`: the same in the Stages panel and the Stages
     window. Each acts on the stage selected when it is clicked. `saved`, if given,
     runs once the new list has come back from the server. Answers a function that
     enables the buttons for the stage selected now. */
  function stageButtons(bar, saved) {
    var el = App.UI.el;
    var buttons = STAGE_ACTIONS.map(function (spec) {
      // Named, as the rail buttons are, so a script or a screen reader can find it.
      var button = el('button.tbtn', { type: 'button' });
      button.setAttribute('data-action', spec[4]);
      button.setAttribute('aria-label', spec[1]);
      button.appendChild(App.UI.icon(spec[0]));
      App.UI.attachTip(button, spec[1]);
      button.addEventListener('click', function () {
        App.UI.hideTip();
        var selected = selectedStageId();
        if (spec[0] !== 'new' && !selected) { App.Command.err('Select a stage first.'); return; }
        // Insert and Delete refuse the initial stage (App.Stages.inserted, .removed).
        if (spec[5] && App.Stages.isInitial(App.PROJECT, selected)) {
          App.Command.err(spec[5]);
          return;
        }
        var before = ((App.PROJECT && App.PROJECT.stages) || []).map(function (stage) {
          return stage.id;
        });
        var list = spec[2](selected);
        // A stage just made is the one to fill in next, so it is selected; after a
        // delete, selectedStageId falls back to the first.
        var made = list.filter(function (stage) { return before.indexOf(stage.id) < 0; })[0];
        if (made) App.state.phase = made.id;
        var done = saveStages(list, spec[3]);
        if (saved) done.then(saved);
      });
      bar.appendChild(button);
      return button;
    });
    function sync() {
      var selected = selectedStageId();
      buttons.forEach(function (button, i) {
        button.disabled = STAGE_ACTIONS[i][0] !== 'new' && !selected;
      });
    }
    sync();
    return sync;
  }

  function stageToolbar() {
    var el = App.UI.el;
    var bar = el('div.dlg-toolbar.stage-toolbar');
    stageButtons(bar);

    bar.appendChild(el('span.tbsep'));

    var dialog = el('button.btn.btn-sm', { text: 'Stages…', type: 'button' });
    dialog.addEventListener('click', function () { stagesDialog(); });
    bar.appendChild(dialog);

    return bar;
  }

  /* The empty state, which is the one every project starts in. Every stage is the
     user's to add, with the toolbar's Add above it. */
  function emptyStageState() {
    var el = App.UI.el;
    var wrap = el('div.lay-hint', { style: 'padding:10px' });
    wrap.appendChild(el('div', { text:
      'This project has no construction sequence: it exports as a single stage, ' +
      'the way it always has. Use "Add stage" above to add the initial stage.' }));
    return wrap;
  }

  /* In Staged construction a click on a part in the viewport selects it, and nothing
     more: switching a part in or out of a stage is asked for by name, with a right
     click (Activate / Deactivate in the viewport menu) or with the part's check box in
     the Model explorer. A click that also switched the part made every look at a part
     an edit, and one that could switch a part off but not reliably back on.

     The switch is the selected stage's alone (`App.Stages.setActive`): the other
     stages keep what they had. */
  function stagePartKey(key) {
    if (!key || !App.PROJECT || App.PROJECT.deck) return null;
    if (!App.state || App.state.mode !== 'staged') return null;
    if (!(App.PROJECT.stages || []).length || !App.Stages) return null;
    return App.Stages.stageableKeys(App.PROJECT).indexOf(key) >= 0 ? key : null;
  }

  function partLabel(key) {
    var project = App.PROJECT || {};
    var named = (project.soil_body_labels || {})[key];
    if (named) return named;
    var record = [].concat(project.custom_parts || [], project.beams || [],
                           project.anchors || [], project.interfaces || [],
                           project.normal_loads || [], project.loads || [],
                           project.boundary_conditions || [])
      .filter(function (each) { return each && (each.key === key || each.id === key); })[0];
    return (record && (record.label || record.name)) || key;
  }

  function switchPartInStage(key, wanted) {
    var stage = selectedStageId();
    if (!stage) { App.Command.err('Select a stage first.'); return null; }
    return saveStages(App.Stages.setActive(App.PROJECT, stage, [key], wanted),
                      partLabel(key) + (wanted ? ' activated in ' : ' deactivated in ')
                      + (stageById(stage) || {}).name + '.');
  }

  /* The viewport menu's two rows for a stageable part, in Staged construction: the
     state the part does not have in the selected stage is offered, the other greyed,
     so the menu also says which one it is in. */
  /* A soil right-clicked in Flow conditions: the water it takes, a submenu of the
     phreatic line, each head line and interpolated, the one it takes now ticked -- the
     same choice as its row of Soil water in the Boundary conditions window
     (`App.BoundaryConditions.soilWaterMenu`). */
  function soilWaterKey(key) {
    var BC = App.BoundaryConditions;
    if (!key || !App.PROJECT || App.PROJECT.deck || !BC || !BC.soilWaterMenu) return null;
    if (!App.state || App.state.mode !== 'flow') return null;
    return BC.soilPartKeys(App.PROJECT).indexOf(key) >= 0 ? key : null;
  }

  function withSoilWaterRows(items, key) {
    var soil = soilWaterKey(key);
    if (!soil) return items;
    var BC = App.BoundaryConditions;
    var choices = BC.soilWaterMenu(App.PROJECT, soil);
    var now = choices.filter(function (choice) { return choice.checked; })[0];
    var rows = [
      { label: 'Water: ' + (now ? now.label : 'phreatic line'), sub: choices },
      '-'
    ];
    var at = items.length && items[0] && items[0].title ? 1 : 0;
    return items.slice(0, at).concat(rows, items.slice(at));
  }

  /* Right-click on a drawn soil surface: Intersect with > each other soil surface it
     overlaps. The two become the part of each outside the other and the overlap, which
     takes the material of the one clicked (POST /api/geometry/intersect). A surface
     nothing overlaps says so rather than leaving the row out, so the action is found. */
  function withIntersectRows(items, key) {
    var D = App.SoilVolumeDialog;
    if (!key || !App.PROJECT || App.PROJECT.deck || !D || !D.overlappingSurfaces) return items;
    if (App.state && App.state.mode === 'results') return items;
    var others = D.overlappingSurfaces(App.PROJECT, key);
    if (!others) return items;
    var own = String(key).split('__')[0];
    var row = others.length
      ? { label: 'Intersect with', sub: others.map(function (other) {
          return { label: other.label, action: 'intersectSurface', surfaceKey: own,
                   otherKey: other.key };
        }) }
      : { label: 'Intersect with (no overlapping surface)', disabled: true };
    var at = items.length && items[0] && items[0].title ? 1 : 0;
    return items.slice(0, at).concat([row, '-'], items.slice(at));
  }

  function intersectSurfaces(key, other) {
    var named = '"' + partLabel(key) + '" with "' + partLabel(other) + '"';
    App.Command.note('Intersecting ' + named + '…');
    return App.Api.post('/api/geometry/intersect', { key: key, other: other })
      .then(function () { return App.Model.load(); })
      .then(function () { return App.Viewport.refresh(); })
      .then(function () {
        if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
        App.Command.ok('Intersected ' + named + ': the overlap is a soil surface of its '
                       + 'own, of the material of "' + partLabel(key) + '".');
      })
      .catch(function (error) { App.Command.err('Intersect failed: ' + error.message); });
  }

  function withStageRows(items, key) {
    var part = stagePartKey(key);
    var stage = part && selectedStageId();
    if (!stage) return items;
    var on = (App.Stages.activeParts(App.PROJECT, stage) || []).indexOf(part) >= 0;
    var name = (stageById(stage) || {}).name || stage;
    var rows = [
      { label: 'Activate in ' + name, action: 'stageActivate', disabled: on,
        stageKey: part },
      { label: 'Deactivate in ' + name, action: 'stageDeactivate', disabled: !on,
        stageKey: part },
      '-'
    ];
    var at = items.length && items[0] && items[0].title ? 1 : 0;
    return items.slice(0, at).concat(rows, items.slice(at));
  }

  /* Redrawn on every edit, so the panel keeps where it was scrolled to: emptying it
     clamps its scroll to the top, and an edit low on the grid would jump the panel
     away from the control just used. */
  function mountLiveStages() {
    if (typeof document === 'undefined') return;
    var host = document.getElementById('list-phases');
    if (!host) return;
    var scroll = host.scrollTop;
    drawLiveStages(host);
    host.scrollTop = scroll;
  }

  function drawLiveStages(host) {
    var el = App.UI.el;
    var icon = App.UI.icon;
    App.UI.clear(host);

    host.appendChild(stageToolbar());

    var stages = (App.PROJECT && App.PROJECT.stages) || [];
    // The Model explorer's checkboxes follow the selected stage. Every route that
    // changes the stage or the sequence comes through here.
    syncStageChecks();
    if (!stages.length) {
      host.appendChild(emptyStageState());
      return;
    }

    /* A branching tree has no execution order, so it has no stage list and cannot be
       run. Said here, where it can still be fixed, rather than at Calculate -- and
       said without hiding the rows, because the way out of it is to edit one of the
       stages that branch. */
    var problem = App.Stages.branchProblem(App.PROJECT);
    if (problem) {
      host.appendChild(el('div.lay-hint.invalid', { text: problem,
                                                    style: 'padding:6px 10px' }));
    }

    var selected = selectedStageId();
    var list = el('div.phase-list');
    App.Stages.rows(App.PROJECT, stageRun).forEach(function (row) {
      var node = el('div.phase-row' + (row.id === selected ? '.selected' : ''));
      node.style.paddingLeft = (8 + row.depth * 10) + 'px';
      node.appendChild(el('span.phase-dot.' + row.state));
      node.appendChild(el('span.phase-name', { text: row.name }));
      node.appendChild(el('span.phase-kind', { text: row.kind }));
      node.addEventListener('click', function () {
        App.state.phase = row.id;
        mountLiveStages();
        // Staged mode draws the model as of the selected stage, so moving the
        // selection moves the viewport with it.
        if (App.Viewport.applyStageVisibility) App.Viewport.applyStageVisibility();
        App.Command.note('Current stage: ' + row.name);
      });
      list.appendChild(node);
    });
    host.appendChild(list);

    var stage = stageById(selected);
    if (!stage) return;
    var grid = el('div.pgrid');
    var head = el('div.pgrid-header');
    head.appendChild(icon('phase'));
    head.appendChild(el('span', { text: stage.name }));
    grid.appendChild(head);
    appendStageGroups(grid, stage);
    host.appendChild(grid);
  }

  /* The property grid's groups for `stage`, then its expert settings, collapsed until
     opened. `after` runs once an edit is saved: the Stages dialog redraws with it,
     since which rows a stage has follows what it is set to. The dock redraws anyway
     (`saveStages`). */
  function appendStageGroups(grid, stage, after) {
    var el = App.UI.el;
    var groups = stageProps(stage);
    var rows = App.Stages.solverRows(App.PROJECT, stage);
    Object.keys(groups).forEach(function (name) {
      grid.appendChild(el('div.pgrid-group', { text: name }));
      groups[name].forEach(function (row) {
        grid.appendChild(stagePropRow(stage, row, after));
      });
      // The solver settings a stage of its kind is tuned by -- a dynamic stage's
      // Rayleigh damping -- follow its time integration, outside the expert ones.
      if (name === 'General') appendSolverGroups(grid, stage, rows, after, true);
    });
    grid.appendChild(expertSettings(stage, after, rows));
  }

  /* The solver settings among `rows` drawn on the stage's own grid (`onPanel`), or
     the expert ones, each group under its own header. */
  function appendSolverGroups(host, stage, rows, after, onPanel) {
    var el = App.UI.el;
    var group = null;
    rows.forEach(function (row) {
      var setting = App.Stages.solverSetting(row.key);
      if ((setting.panel === 'stage') !== onPanel) return;
      if (setting.group !== group) {
        group = setting.group;
        host.appendChild(el(onPanel ? 'div.pgrid-group' : 'div.pgrid-subgroup',
                            { text: group }));
      }
      host.appendChild(solverPropRow(stage, row, setting, after));
    });
  }

  /* The expert solver settings (`core.model.solver`): the strategy, the linear
     solver, the time step control, the time scheme of a dynamic stage, the assembly.
     Collapsed until opened, and kept open for the session once it is.

     Only the settings that apply are drawn (App.Stages.solverRows), at the stage's
     own value or the default its calculation type and time integration give it. A
     setting the stage changed says so, with a button that puts it back; a setting
     that is fixed -- the quasi-Newton strategy's Sparse LU, the seepage strategy of a
     seepage face -- is shown, not offered, with the reason as its tooltip. The rows
     are built when the section is first opened, so a closed one holds no controls. */
  function expertSettings(stage, after, rows) {
    var el = App.UI.el;
    rows = rows || App.Stages.solverRows(App.PROJECT, stage);
    var changed = rows.filter(function (row) {
      return row.overridden && App.Stages.solverSetting(row.key).panel !== 'stage';
    }).length;
    var open = !!(App.state && App.state.stageExpert);
    var wrap = el('div.pgrid-expert' + (open ? '.open' : ''));
    var head = el('div.pgrid-group.pgrid-toggle', {
      text: 'Expert settings' + (changed ? ' (' + changed + ' changed)' : ''),
      title: open ? 'Hide the expert settings' : 'Show the expert settings'
    });
    var body = null;

    function show() {
      if (!body) {
        body = el('div.pgrid-expert-body');
        appendSolverGroups(body, stage, rows, after, false);
        wrap.appendChild(body);
      }
      body.style.display = open ? '' : 'none';
      wrap.classList.toggle('open', open);
      head.title = open ? 'Hide the expert settings' : 'Show the expert settings';
    }

    head.addEventListener('click', function () {
      open = !open;
      App.state = App.state || {};
      App.state.stageExpert = open;
      show();
    });
    wrap.appendChild(head);
    if (open) show();
    return wrap;
  }

  /* One expert setting's row. Its edit stores the value on the stage
     (App.Stages.editedSolver), or takes it off again, back to the default. */
  function solverPropRow(stage, row, setting, after) {
    var el = App.UI.el;
    var key = el('div.pgrid-key' + (row.overridden ? '.changed' : ''), {
      text: setting.label, title: setting.help || setting.label
    });
    var shown = App.Stages.solverLabel(row.key, row.value);

    function commit(value) {
      var saved = saveStages(App.Stages.editedSolver(App.PROJECT, stage.id, row.key,
                                                     value));
      if (after) saved.then(after);
    }

    if (row.locked) {
      return el('div.pgrid-row', { title: row.locked }, [key, el('div.pgrid-val.readonly',
        { text: 'fixed: ' + shown, title: row.locked })]);
    }
    // A deck case's stages are its deck's, which the server refuses to change.
    if (App.PROJECT && App.PROJECT.deck) {
      return el('div.pgrid-row', null, [key, el('div.pgrid-val.readonly',
                                                 { text: shown })]);
    }

    var control;
    if (setting.kind === 'select') {
      control = el('select');
      setting.options.forEach(function (option) {
        var node = el('option', { value: option[0], text: option[1] });
        if (option[0] === row.value) node.selected = true;
        control.appendChild(node);
      });
      control.addEventListener('change', function () { commit(control.value); });
    } else if (setting.kind === 'check') {
      control = el('input.pgrid-check', { type: 'checkbox' });
      control.checked = !!row.value;
      control.addEventListener('change', function () { commit(control.checked); });
    } else {
      control = el('input.cell-input.cell-num', { value: String(row.value) });
      control.addEventListener('change', function () {
        var value = parseFloat(control.value.trim().replace(',', '.'));
        var problem = numberProblem(setting.label, value, {
          integer: setting.integer, min: setting.minimum,
          exclusiveMin: setting.above, max: setting.maximum
        });
        if (problem) {
          control.value = String(row.value);
          App.Command.err(problem);
          return;
        }
        commit(value);
      });
    }

    var cell = el('div.pgrid-val.editable.field', null, [control]);
    if (row.overridden) {
      var reset = el('button.pgrid-reset', {
        type: 'button', text: '↺',
        title: 'Back to the default: ' + App.Stages.solverLabel(row.key, row['default'])
      });
      reset.addEventListener('click', function () { commit(null); });
      cell.appendChild(reset);
    }
    return el('div.pgrid-row', null, [key, cell]);
  }

  /* What is wrong with `value` as `label`, given `bounds` -- `integer`, `min`,
     `exclusiveMin`, `max` -- or null. */
  function numberProblem(label, value, bounds) {
    if (!isFinite(value)) return label + ' must be a number.';
    if (bounds.integer && value !== Math.round(value)) {
      return label + ' must be a whole number.';
    }
    if (bounds.min != null && value < bounds.min) {
      return label + ' must be at least ' + bounds.min + '.';
    }
    if (bounds.exclusiveMin != null && value <= bounds.exclusiveMin) {
      return label + ' must be greater than ' + bounds.exclusiveMin + '.';
    }
    if (bounds.max != null && value > bounds.max) {
      return label + ' must be at most ' + bounds.max + '.';
    }
    return null;
  }

  /* The property grid for one stage.

     Field names follow the stage panel the frozen mockup already draws
     (js/data.js:569), because that is the UI this feeds. What it does *not* do is
     keep the mockup's rows this exporter has nothing behind -- "Max unloading steps",
     "Arc-length control", "Updated mesh", "Ignore undrained behaviour". A row that
     looks editable and is thrown away on save is worse than an absent one, and the
     three groups below are exactly what `schemas.Stage` carries.

     "Water conditions" is read-only: the water pressure conditions the stage has on,
     which the Model explorer's check boxes switch (App.BoundaryConditions.waterIn).

     The calculation type is mechanical or flow (App.Stages.CALCULATION_TYPES), chosen
     in the initial stage for the whole sequence: a later stage shows it, and cannot
     change it. The stresses are initialised in the initial stage of a mechanical
     sequence only, so only that stage has a "Stress initialisation" row -- and a later
     stage that has one anyway, as an old project's later K0 procedure does, until it is
     set to none; making the sequence a flow one sets it back to none, and making it a
     mechanical one again gives it gravity loading (App.Stages.edited). That row is also what
     switches gravity: none leaves the self weight out of every stage
     (`core.model.stages.gravity`), which the "Gravity" row under it says. A flow stage solves
     the water pressure alone, so its "Reset displacements to zero" box is greyed out,
     with the reason as its tooltip; the CLI refuses the option on such a stage.

     The stage duration and its time step are in the project's unit of time
     (App.Units); the server refuses a step longer than the duration. The initial
     stage also has the start time of the whole calculation, 0 by default; a later
     stage shows its own start time, where the stage before it ends, read-only.

     The convergence criterion is one of the calculation type's
     (App.Stages.CONVERGENCE_CRITERIA): residual or displacement for a mechanical
     stage, water pressure or residual for a flow stage. "Tolerated error" and
     "Absolute tolerance" are the criterion's relative and absolute tolerances. */
  function stageProps(stage) {
    var parent = stage.parent == null ? null : stageById(stage.parent);
    var flow = stage.calculation === App.Stages.FLOW;
    var first = stage.parent == null;
    var calculation = (App.Stages.CALCULATION_TYPES.filter(function (option) {
      return option[0] === (stage.calculation || 'mechanical');
    })[0] || [null, stage.calculation])[1];
    var second = App.Units ? App.Units.label('time') : 's';
    var criteria = App.Stages.criteriaOf(stage.calculation);
    var general = [
      ['Name', 'text', 'name'],
      ['Start from stage', 'static', parent ? parent.name : 'the model as built'],
      first ? ['Calculation type', 'select', 'calculation', App.Stages.CALCULATION_TYPES]
            : ['Calculation type', 'static', calculation + ' (from the initial stage)']
    ];
    var stresses = stage.stress_initialisation || 'none';
    if (first && (stage.calculation === 'mechanical' || stage.calculation == null)) {
      general.push(['Stress initialisation', 'select', 'stress_initialisation',
                    App.Stages.STRESS_INITIALISATIONS]);
      general.push(['Gravity', 'static', stresses === 'none'
        ? 'Off: no body has a self weight' : 'On: every body has its self weight']);
    } else if (!first && stresses !== 'none') {
      // An old project's later K0 procedure, which the server refuses every edit with:
      // the row is here so that it can go back to none, the one a later stage takes.
      general.push(['Stress initialisation', 'select', 'stress_initialisation',
                    App.Stages.STRESS_INITIALISATIONS.filter(function (option) {
                      return option[0] === stresses || option[0] === 'none';
                    })]);
    }
    general.push(['Time integration', 'select', 'time_integration',
                  App.Stages.TIME_INTEGRATIONS]);
    // The calculation's clock starts at the initial stage; every later stage picks up
    // where the one before it ended, so its start time is shown, not set.
    var timing = [first
      ? ['Start time', 'number', 'start_time', {}, second]
      : ['Start time', 'static',
         App.Stages.startOf(App.PROJECT, stage.id) + ' ' + second
         + ' (where the previous stage ends)']];
    var groups = {
      'General': general.concat([
        ['Loading type', 'static', stage.loading || 'Staged construction'],
        ['Water conditions', 'static', App.BoundaryConditions
          ? App.BoundaryConditions.waterIn(App.PROJECT, stage.id) : '']
      ], timing, [
        ['Stage duration', 'number', 'duration', { exclusiveMin: 0 }, second],
        ['Time step', 'number', 'time_step', { exclusiveMin: 0 }, second]
      ]),
      'Deformation control': [
        ['Reset displacements to zero', 'check', 'reset_displacements',
         flow ? { greyed: 'A groundwater flow stage has no displacements.' } : null]
      ],
      'Numerical control': [
        criteria.length > 1
          ? ['Convergence criterion', 'select', 'convergence_criterion', criteria]
          : ['Convergence criterion', 'static',
             criteria.length ? criteria[0][1] : stage.convergence_criterion],
        ['Max iterations', 'number', 'max_iterations', { min: 1, integer: true }],
        ['Tolerated error', 'number', 'tolerated_error', { exclusiveMin: 0 }],
        ['Absolute tolerance', 'number', 'absolute_tolerance', { exclusiveMin: 0 }]
      ]
    };
    // The linear strategy solves once: there is nothing to converge.
    if (!App.Stages.iterates(App.Stages.solverRows(App.PROJECT, stage))) {
      delete groups['Numerical control'];
    }
    return groups;
  }

  /* One row, and the edit behind it.

     Every committed edit PATCHes the whole stage list, because that is what the
     endpoint takes -- there is no per-field write, and inventing one would be a
     second way for the list to get out of step with the server. The reply replaces
     the list, so a value the server normalises shows the normalised one. */
  function stagePropRow(stage, spec, after) {
    var el = App.UI.el;
    var label = spec[0], kind = spec[1];
    var key = el('div.pgrid-key', { text: label });

    function commit(value) {
      var list = App.Stages.edited(App.PROJECT, stage.id, spec[2], value);
      var saved = saveStages(list);
      if (after) saved.then(after);
    }

    if (kind === 'static') {
      return el('div.pgrid-row', null,
                [key, el('div.pgrid-val.readonly', { text: String(spec[2]) })]);
    }
    /* A deck case's stages are its stages, read from the deck that Calculate runs
       (core/kratos/external_deck.py); the server refuses an edit, so none is offered. */
    if (App.PROJECT && App.PROJECT.deck) {
      var shown = stage[spec[2]];
      if (kind === 'check') shown = shown ? 'Yes' : 'No';
      if (kind === 'select') {
        spec[3].forEach(function (option) {
          if (Array.isArray(option) && option[0] === shown) shown = option[1];
        });
      }
      return el('div.pgrid-row', null, [key, el('div.pgrid-val.readonly', {
        text: (shown == null ? '' : String(shown)) + (spec[4] ? ' ' + spec[4] : '')
      })]);
    }

    var control;
    if (kind === 'text') {
      control = el('input.cell-input', { value: stage[spec[2]] || '' });
      control.addEventListener('change', function () {
        var text = control.value.trim();
        if (!text) {
          control.value = stage[spec[2]];
          App.Command.err('A stage name cannot be empty.');
          return;
        }
        commit(text);
      });
    } else if (kind === 'select') {
      control = el('select');
      // Each option is a value, or [value, label] where the two differ.
      spec[3].forEach(function (option) {
        var value = Array.isArray(option) ? option[0] : option;
        var node = el('option', { value: value,
                                  text: Array.isArray(option) ? option[1] : option });
        if (value === stage[spec[2]]) node.selected = true;
        control.appendChild(node);
      });
      control.addEventListener('change', function () { commit(control.value); });
    } else if (kind === 'check') {
      control = el('input.pgrid-check', { type: 'checkbox' });
      control.checked = !!stage[spec[2]];
      if (spec[3] && spec[3].greyed) {
        control.disabled = true;
        control.title = spec[3].greyed;
        return el('div.pgrid-row', { title: spec[3].greyed },
                  [key, el('div.pgrid-val.readonly', null, [control])]);
      }
      control.addEventListener('change', function () { commit(control.checked); });
    } else {
      var bounds = spec[3] || {};
      control = el('input.cell-input.cell-num', {
        value: String(stage[spec[2]] == null ? '' : stage[spec[2]])
      });
      control.addEventListener('change', function () {
        var value = parseFloat(control.value.trim().replace(',', '.'));
        var problem = numberProblem(label, value, bounds);
        if (problem) {
          control.value = String(stage[spec[2]]);
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

  /* ── The Stages dialog ───────────────────────────────────────────────────
     The second screenshot: the full-page stage editor, list on the left and the same
     three groups on the right, larger. Same rows and the same edit path as the panel
     -- it is the same grid given room -- so a stage field is described in one place
     and written one way.

     What the dialog adds is the parts list: what this stage switches on and off,
     which there is no room for beside a 220-pixel dock. */
  function stagesDialog() {
    var el = App.UI.el;
    if (!App.Dialogs || !App.Dialogs.open) {
      App.Command.err('The dialog layer is not available.');
      return;
    }

    var selected = selectedStageId();

    /* The panel's stage buttons, above the list: a stage is added, duplicated or
       deleted without closing the window. A deck's stages are the deck's, and it has
       none. The stage a button made is the one shown next. */
    var redraw = null, toolbar = null, syncButtons = function () {};
    if (!(App.PROJECT && App.PROJECT.deck)) {
      toolbar = el('div.dlg-toolbar.stage-toolbar');
      syncButtons = stageButtons(toolbar, function () {
        selected = selectedStageId();
        if (redraw) redraw();
      });
    }

    App.Dialogs.open({
      title: 'Stages', toolbar: toolbar,
      width: Math.min(1180, window.innerWidth - 40),
      height: Math.min(720, window.innerHeight - 40),
      buttons: [{ label: 'Close', primary: true }],
      build: function (body) {
        var wrap = el('div.dlg-simple.stages-overview', {
          style: 'display:flex;gap:12px;padding:0;height:100%'
        });
        var left = el('div.stages-overview-list', {
          style: 'flex:0 0 380px;overflow:auto;border-right:1px solid var(--c-line)'
        });
        var right = el('div', { style: 'flex:1;overflow:auto;padding-right:4px' });
        var log = el('div.stages-overview-log', {
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
          syncButtons();

          var stages = (App.PROJECT && App.PROJECT.stages) || [];
          if (!stages.length) {
            right.appendChild(el('p', { text:
              'This project has no stages yet. Use "Add stage" above to add the ' +
              'initial stage.' }));
            return;
          }

          /* One line per stage: status, name, duration,
             the time T reached, the id -- then the calculation type. What each line
             says is App.Stages.overview's (tested headlessly). */
          var overview = App.Stages.overview(App.PROJECT, stageRun);
          var list = el('div.phase-list');
          overview.forEach(function (row) {
            var node = el('div.phase-row' + (row.id === selected ? '.selected' : ''));
            node.style.paddingLeft = (8 + row.depth * 4) + 'px';
            node.title = row.label + ' · ' + row.kind;
            node.appendChild(el('span.phase-dot.' + row.state));
            var name = el('span.phase-name', { text: row.heading + ' ' });
            name.appendChild(el('span.phase-id', { text: '[' + row.id + ']' }));
            node.appendChild(name);
            node.appendChild(el('span.phase-kind', { text: row.kind }));
            node.addEventListener('click', function () {
              selected = row.id;
              App.state.phase = row.id;
              // The viewport follows, as it does from the dock's own list.
              if (App.Viewport.applyStageVisibility) App.Viewport.applyStageVisibility();
              mountLiveStages();
              draw();
            });
            list.appendChild(node);
          });
          left.appendChild(list);

          var stage = stageById(selected);
          if (!stage) { selected = stages[0].id; draw(); return; }
          var current = overview.filter(function (row) { return row.id === stage.id; })[0];
          stageLog(log, current);

          var grid = el('div.pgrid');
          appendStageGroups(grid, stage, draw);
          right.appendChild(grid);

          /* What this stage changes. Read-only here: the way to change it is to
             right-click the part in the viewport, or tick it in the Model explorer. */
          var on = stage.activate || [], off = stage.deactivate || [];
          var active = App.Stages.activeParts(App.PROJECT, stage.id) || [];
          var named = function (keys) {
            return keys.map(function (key) {
              return App.Stages.partLabel(App.PROJECT, key);
            }).join(', ');
          };
          var changes = el('div.pgrid');
          changes.appendChild(el('div.pgrid-group', { text: 'Staged construction' }));
          [['Activated here', on.length ? named(on) : '—'],
           ['Deactivated here', off.length ? named(off) : '—'],
           ['Active in this stage', active.length + ' of ' +
            App.Stages.stageableKeys(App.PROJECT).length + ' parts']
          ].forEach(function (row) {
            changes.appendChild(el('div.pgrid-row', null, [
              el('div.pgrid-key', { text: row[0] }),
              el('div.pgrid-val.readonly', { text: row[1] })
            ]));
          });
          right.appendChild(changes);

          /* The way back. A part this stage has switched off is not drawn in the
             viewport, so it cannot be clicked to bring it back -- which would make
             the toggle one-way, and the mistake unrecoverable without editing the
             stage before it. Listed here with a button each. */
          var hidden = App.PROJECT.deck ? []
            : App.Stages.hiddenKeys(App.PROJECT, stage.id, 'staged');
          if (hidden.length) {
            var back = el('div.pgrid');
            back.appendChild(el('div.pgrid-group', { text: 'Not in the model here' }));
            hidden.forEach(function (key) {
              var label = App.Stages.partLabel(App.PROJECT, key);
              var button = el('button.btn.btn-sm', { text: 'Switch on', type: 'button' });
              button.addEventListener('click', function () {
                saveStages(App.Stages.toggled(App.PROJECT, stage.id, key),
                           label + ' switched on in ' + stage.name + '.')
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
            ? 'These stages are the stages of the Kratos deck ' + App.PROJECT.deck.parameters
              + ', shown as they are. Edit the deck to change them, then run its '
              + 'script again.'
            : 'In Staged construction mode, tick or untick a part in the Model ' +
              'explorer, or right-click it in the viewport, to put it in or take it ' +
              'out of the selected stage. The other stages keep what they had; a ' +
              'stage added later starts from the stage before it.' }));
        }

        redraw = draw;
        draw();
      }
    });
  }

  /* The Stages window has three ways in, all the one action: a button on the Staged
     construction rail (beside Calculate), the Stages menu's "Edit stages…" -- which
     the frozen mockup draws and wires to nothing -- and `stages` on the command line. */
  function installStagesOverview() {
    var staged = App.RAILS && App.RAILS.staged;
    if (staged && !staged.some(function (tool) { return tool && tool.action === 'stages'; })) {
      var at = staged.length;
      staged.forEach(function (tool, i) { if (tool && tool.action === 'calculate') at = i; });
      staged.splice(at, 0, { icon: 'phase', tip: 'Stages overview…', action: 'stages' });
    }
    (App.MENUS || []).forEach(function (menu) {
      (menu.items || []).forEach(function (item) {
        if (item && item.label === 'Edit stages…') item.action = 'stages';
      });
    });
  }

  /* The right-hand column of the Stages window: what the last calculation made of
     the selected stage, and the time it reaches -- the "Log info for last
     calculation" and "Reached values". Only what this app knows: a Kratos run says
     whether each stage finished, not reached forces or safety factors. */
  function stageLog(host, row) {
    var el = App.UI.el;
    if (!row) return;
    host.appendChild(el('div.pgrid-group', { text: 'Log info for last calculation' }));
    var box = el('div.stages-overview-box.' + row.state, { text: row.log });
    host.appendChild(box);
    if (row.state === 'failed' && stageRun && stageRun.error) {
      host.appendChild(el('pre.stages-overview-error', { text: stageRun.error }));
    }
    var reached = el('div.pgrid');
    reached.appendChild(el('div.pgrid-group', { text: 'Reached values' }));
    [['Stage', row.number + ' of ' + ((App.PROJECT.stages || []).length)],
     ['Stage duration', row.duration + ' ' + row.unit],
     ['Reached total time', row.total + ' ' + row.unit]
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
     at the stages panel, so this one already sits in an implicit `auto` row that
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

  /* ── What the command panel says about itself ────────────────────────────
     The mockup's welcome, `help`, command reference, Model history and canned
     answers (js/data.js:914-956, js/dialogs.js:1240) describe a demo: a command line
     that "accepts a small set of demo commands", a model of 50 × 40 × 25 m whatever
     is open, `plate` answering "Plate_5" without building anything, and `calculate`
     saying no solver is attached. One list of the commands this build has feeds
     `help` and the command reference both, so the two cannot disagree again. */
  var COMMANDS = [
    ['run <file.py>', 'build the model from a Python file'],
    ['script <file.py>', 'write the model as a Python file that builds it'],
    ['mesh', 'generate the finite element mesh'],
    ['calculate', 'mesh the model and run it in Kratos (F9)'],
    ['calculate stop', 'stop the running calculation; what it wrote stays'],
    ['results', 'open what a calculation wrote (try "results runs")'],
    ['export', 'write the Kratos deck'],
    ['stages', 'the Stages overview: every stage, its time and result'],
    ['water <level>|off', 'set or remove the water level, e.g. water -1.5'],
    ['boundary [list|standard]', 'the boundary conditions, or put the standard supports back'],
    ['gravity [G]', 'show whether the self weight acts, or set g in m/s²'],
    ['units [SI|kN]', 'show the unit system, or convert the project to another'],
    ['soillayers', 'open the Modify soil layers window'],
    ['materials', 'open the Soil materials window'],
    ['cleargeometry', 'remove the drawn and imported solids'],
    ['clearmesh', 'clear the mesh; its settings stay'],
    ['colour <part>|all|off', 'draw a part of the mesh in its own colour'],
    ['node <id>', 'which SubModelParts a node is in'],
    ['gotosoil, gotostructures, gotomesh, gotoflow, gotostaged', 'open a mode'],
    ['view iso|top|front|side', 'a standard view'],
    ['zoomfit', 'zoom to fit the model'],
    ['clear', 'clear the session log'],
    ['feedback [text]', 'save a feedback report: what went wrong, or what you would like'],
    ['help', 'this list']
  ];

  /* The canned words of js/data.js that build nothing, and where the real tool is. */
  var PLACEHOLDERS = {
    soillayer: 'Soil > Modify soil layers…, or `kratos-cli layer add` in a terminal',
    plate: 'Structures > Create wall panel… (3D), or `kratos-cli wall add`',
    beam: 'Structures > Create sheet pile…, or `kratos-cli beam add`',
    anchor: 'Structures > Create anchor…, or `kratos-cli anchor add`',
    surface: 'Soil > Create soil surface…',
    line: 'the Create line tool of Structures mode',
    point: 'the Create line tool of Structures mode, which is drawn point by point'
  };

  /* Every first word js/command.js answers itself: its mode jumps, its `switch`, and
     the canned answers. Anything else it would call a demo command it does not know. */
  var SHELL_WORDS = ['gotosoil', 'gotostructures', 'gotomesh', 'gotoflow', 'gotostaged',
                     'gotoflowconditions', 'clear', 'view', 'zoomfit', 'soillayers',
                     'materials', 'mesh'];

  function helpLines() {
    return [['note', 'Commands:']].concat(COMMANDS.map(function (row) {
      var name = row[0].length < 22 ? (row[0] + '                      ').slice(0, 22)
                                    : row[0] + '  ';
      return ['note', '  ' + name + row[1]];
    }));
  }

  function shellAnswers(word) {
    return SHELL_WORDS.indexOf(word) >= 0
      || Object.prototype.hasOwnProperty.call(App.CMD_RESPONSES || {}, word);
  }

  function replaceMockupText() {
    var product = App.PRODUCT || {};
    App.CMD_WELCOME = [
      ['note', '# ' + (product.name || 'Styx') + ' — ' + (product.version || '')],
      ['note', '# Type a command and press Enter. "help" lists the commands.'],
      ['note', '# Try:  run tests/models/excavation.py  ·  help'],
      ['ok', 'Project "' + (product.project || 'Untitled project') + '" opened.']
    ];
    // Filled with what is typed, by the command box below; js/data.js's list was a
    // session nobody had.
    App.CMD_HISTORY = [];
    if (!App.CMD_RESPONSES) return;
    App.CMD_RESPONSES.help = helpLines();
    Object.keys(PLACEHOLDERS).forEach(function (word) {
      App.CMD_RESPONSES[word] = [['note', '"' + word + '" builds nothing in the command box '
                                          + 'yet. Use ' + PLACEHOLDERS[word] + '.']];
    });
  }

  function commandReference() {
    var el = App.UI.el;
    App.Dialogs.open({
      title: 'Command reference',
      width: 620, height: 520,
      buttons: [{ label: 'Close', primary: true }],
      build: function (body) {
        var list = el('ul');
        COMMANDS.forEach(function (row) {
          list.appendChild(el('li', null, [el('code', { text: row[0] }),
                                           el('span', { text: '  —  ' + row[1] })]));
        });
        body.appendChild(el('div.dlg-simple', null, [
          el('p', { text: 'Type a command in the box below the log and press Enter. '
                          + 'The arrow keys bring back earlier commands. `results` alone '
                          + 'lists all its forms.' }),
          list,
          el('p', { text: 'kratos-cli does the same work in a terminal: see docs/CLI.md.' })
        ]));
      }
    });
  }

  function recordHistory(text) {
    var history = typeof document !== 'undefined' && document.getElementById('cmd-history');
    if (!history || !App.UI) return;
    history.appendChild(App.UI.el('div.cmd-line.echo', { text: '> ' + text }));
  }

  function install() {
    if (installed || typeof App.runAction !== 'function' || !App.Command) return;
    installed = true;

    /* Results-mode state, declared here rather than beside the functions that use it.

       `var` hoists the name but not the initialiser, and the installers below run
       *during* this function -- so a `var resultsMenu = null` sitting further down
       would run after `installResultsMenu()` had filled it and quietly set it back to
       null, leaving the menu's Stage and Field submenus permanently empty. That is
       not hypothetical: it is what happened, along with the toolbar drawing the info
       glyph because `App.ICONS.viewresults` was assigned `undefined` the same way.
       Anything the installers touch is declared before the first of them is called. */
    var resultsMenu = null;      // the Results entry in App.MENUS, for refilling
    var resultsWindow = null;    // the floating chooser, while it is open
    var plotWindow = null;       // the wall/interface plot window, while it is open
    var plotColumns = 0;         // panels per row it was last drawn with
    var plotReloading = null;    // the run a reload of the plot is under way for
    var resultsLeft = null;      // what Results showed when it was left, to come back to
    var inResults = false;       // whether Results is the mode on screen

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
      // A menu item or tool from the mockup that nothing implements yet, or one on
      // NOT_YET. Both are taken out wherever they are drawn, so this is a stale menu or a
      // caller that did not ask `implemented` -- and it gets the same answer.
      if (item && (!item.action || NOT_YET.indexOf(item.action) >= 0)) {
        if (controlName(item) && App.Command) {
          App.Command.note('"' + controlName(item) + '" is not available in Styx yet.');
        }
        return;
      }
      // "Select": the pointer every mode starts with. Choosing it puts down whatever
      // draw or pick tool was running; with none running there is nothing to say.
      if (item && item.action === 'select') {
        if (App.DrawInput && App.DrawInput.cancel) App.DrawInput.cancel();
        return;
      }
      // Edit > Deselect all: what Esc already does (js/app.js:323).
      if (item && item.action === 'deselectAll') {
        if (App.selectObject) App.selectObject(null);
        return;
      }
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

      // A page on the web, in a tab of its own so the model stays open here.
      if (item && item.action === 'kratosDocs') {
        window.open(KRATOS_DOCS_URL, '_blank', 'noopener');
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
        openResultsWindow();
        return;
      }
      // The Results menu's and rail's "Convergence": `results convergence`, without
      // switching to Results mode -- it is read while a run goes on, and of a run that
      // wrote no results at all.
      if (item && item.action === 'showConvergence') {
        resultsCommand('results convergence');
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
        return App.NameDialog.ask({
          title: 'New project', label: 'Project name', value: 'Untitled project',
          text: 'This discards the current model and starts again from an empty project. '
            + 'Save first if you want to keep it.',
          help: 'Shown in the title bar, and the name Save gives the file.'
        }).then(function (name) { if (name !== null) return newProject(name); });
      }
      if (item && item.action === 'projectProperties') return projectProperties();
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
        'drawPolygon': 'polygon',
        'drawBox': 'box',
        'drawCylinder': 'cylinder'
      };
      
      if (item && drawModes[item.action]) {
        if (App.DrawInput) App.DrawInput.start(drawModes[item.action]);
        return;
      }
      
      if (item && item.action === 'drawLine') {
        if (App.Lines) App.Lines.start();
        return;
      }
      if (item && item.action === 'createLineByCoordinates') {
        if (App.Lines) App.Lines.typed();
        return;
      }
      if (item && item.action === 'clearMesh') {
        clearMesh();
        return;
      }
      if (item && item.action === 'generateMesh') {
        var size = App.PROJECT && App.PROJECT.mesh ? App.PROJECT.mesh.element_size : 2.5;
        // Refine/Coarsen/Reset remake the mesh and leave their object selected.
        requestMesh(!item.keepSelection, 'mesh ' + size);
        return;
      }
      // In 2D the soil surface is drawn first and its window opens on the corners;
      // a 3D volume has no plane to draw on, so its window opens straight away.
      if (item && (item.action === 'drawSoilSurface'
                   || (item.action === 'createSoilVolume' && in2D()))) {
        drawSoilSurface();
        return;
      }
      if (item && (item.action === 'createSoilVolume'
                   || item.action === 'createSoilBodyByCoordinates')) {
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
      // The window of all conditions, of the mechanical ones, or of the flow ones.
      var conditionWindows = { boundaryConditions: 'all', mechanicalConditions: 'mechanical',
                               flowConditions: 'flow' };
      if (item && conditionWindows.hasOwnProperty(item.action)) {
        if (App.BoundaryConditions) App.BoundaryConditions.open(conditionWindows[item.action]);
        return;
      }
      if (item && item.action === 'createBoundaryCondition') {
        if (App.BoundaryConditions) App.BoundaryConditions.openRecord(null, 'mechanical');
        return;
      }
      if (item && item.action === 'createFlowCondition') {
        if (App.BoundaryConditions) App.BoundaryConditions.openRecord(null, 'flow');
        return;
      }
      var drawnConditions = {
        createSupportLine: ['displacement', 'line'],
        createSupportPoint: ['displacement', 'point'],
        createWaterPressureLine: ['water_pressure', 'line'],
        createWaterPressurePoint: ['water_pressure', 'point'],
        createSeepageLine: ['seepage', 'line']
      };
      if (item && drawnConditions[item.action]) {
        if (App.BoundaryConditions) {
          App.BoundaryConditions.draw(drawnConditions[item.action][0],
                                      drawnConditions[item.action][1]);
        }
        return;
      }
      if (item && item.action === 'savePicture') {
        if (App.PictureDialog) App.PictureDialog.open();
        return;
      }
      if (item && item.action === 'feedback') {
        if (App.FeedbackDialog) App.FeedbackDialog.open();
        return;
      }
      if (item && item.action === 'copyPicture') {
        if (App.Picture) App.Picture.copy();
        return;
      }
      if (item && item.action === 'exportModel') {
        if (App.Export) App.Export.run();
        return;
      }
      if (item && item.action === 'openDocumentation') {
        if (App.Documentation) App.Documentation.open(item.page);
        return;
      }
      if (item && item.action === 'calculate') {
        // While a run goes on, the toolbar button (`cta`) and the menu item are Stop.
        // F9 (an action with no label) and the rail are refused below instead.
        if ((item.cta || item.label) && stoppable(calculateNow())) {
          App.Calculate.askStop();
          return;
        }
        // The button is greyed for the same reason; F9 and a menu left open are not.
        if (refuseCalculate()) return;
        if (App.Calculate) App.Calculate.run();
        return;
      }
      if (item && item.action === 'stages') {
        stagesDialog();
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
      // The selected object's local mesh size: halved, doubled, or taken away
      // (js/mesh-settings.js).
      var MESH_SIZE_FACTORS = { refineMesh: 0.5, coarsenMesh: 2, resetMeshRefinement: null };
      if (item && Object.prototype.hasOwnProperty.call(MESH_SIZE_FACTORS, item.action)) {
        return App.MeshSettings.changeSelected(MESH_SIZE_FACTORS[item.action]);
      }
      var result = frozenAction(item);
      // The frozen toggles flip the state and the toolbar button, never the menu tick.
      syncCheckMarks();
      return result;
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

    /* The menu twins of tools that work, given the tool's action -- a row that does
       nothing beside a button that does the same thing is the disagreement this
       file exists to stop. Refine, coarsen and reset get theirs so that the rows and
       the rail buttons are kept or taken out together. */
    var MENU_ACTIONS = {
      File: { 'New project…': 'newProject', 'Open project…': 'openProject',
              'Save': 'saveProject', 'Save as…': 'saveProject' },
      Edit: { 'Undo': 'undo', 'Redo': 'redo', 'Deselect all': 'deselectAll' },
      Structures: { 'Create point': 'drawPoint', 'Create line': 'drawLine',
                    'Create surface': 'drawPolygon', 'Create anchor': 'createAnchor' },
      Mesh: { 'Refine mesh': 'refineMesh', 'Coarsen mesh': 'coarsenMesh',
              'Reset local refinement': 'resetMeshRefinement', 'View mesh': 'viewMesh' },
      'Flow conditions': { 'Create water level': 'createWaterPressureLine' }
    };
    // Clear mesh, under Generate mesh: the two are a pair.
    var meshMenu = (App.MENUS || []).filter(function (m) { return m.label === 'Mesh'; })[0];
    if (meshMenu && !meshMenu.items.some(function (i) { return i && i.action === 'clearMesh'; })) {
      var generateItem = meshMenu.items.filter(function (i) {
        return i && i.action === 'generateMesh';
      })[0];
      meshMenu.items.splice(meshMenu.items.indexOf(generateItem) + 1, 0,
        { label: 'Clear mesh', icon: 'delete', action: 'clearMesh' });
    }
    // The Kratos GeoMechanics user documentation, under Command reference: what the
    // solver does with the model Styx writes.
    var helpMenu = (App.MENUS || []).filter(function (m) { return m.label === 'Help'; })[0];
    if (helpMenu && !helpMenu.items.some(function (i) { return i && i.action === 'kratosDocs'; })) {
      var reference = helpMenu.items.filter(function (i) { return i && i.action === 'cmdref'; })[0];
      helpMenu.items.splice(reference ? helpMenu.items.indexOf(reference) + 1 : 0, 0,
        { label: 'Kratos documentation', icon: 'help', action: 'kratosDocs' });
    }
    (App.MENUS || []).forEach(function (menu) {
      var wanted = MENU_ACTIONS[menu.label];
      if (!wanted) return;
      (menu.items || []).forEach(function (item) {
        if (item && !item.action && wanted[item.label]) item.action = wanted[item.label];
        // Named as the rail button is, since that is what it makes.
        if (item && item.action === 'createWaterPressureLine') {
          item.label = 'Create water pressure line';
        }
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
        gateRail(mode);
      };
    }

    installCalculateState();

    // js/data.js is frozen -- it is served as the same bytes from file:// and from
    // the server -- so the 2D switch is spliced into its arrays here instead.
    // A cross-section through a block: a rectangle with the cut face hatched.
    if (!App.ICONS.section2d) {
      App.ICONS.section2d = '<path d="M4 5h16v14H4z"/><path d="M4 12h16"/><path d="M8 5v14"/>';
    }

    /* The sheet pile and the anchor share one cross-section: the ground higher on
       the right than on the left, drawn faded, and the part the tool makes drawn
       in full over it -- the wall, or the anchor's plate, rod and grout body. The
       section is drawn close up, the ground reaching nearly to the icon's edges,
       so the part reads at 14 px; the wall is one straight line, drawn heavier
       than the icon's usual stroke. The sheet pile tool, the wall panel and their
       rows in the Model explorer ask for 'wall', which data.js never had, so they
       used to fall back to the info glyph. data.js's 'anchor' (a ship's anchor)
       is replaced so the two read as one family. */
    var iconGround = '<path d="M1 15.5h9.3M10.3 8H23" opacity=".32"/>';
    if (!App.ICONS.wall || App.ICONS.wall.indexOf('opacity') < 0) {
      App.ICONS.wall = '<path d="M10.3 2.5v19" stroke-width="2.1"/>' + iconGround;
    }
    if (!App.ICONS.anchor || App.ICONS.anchor.indexOf('opacity') < 0) {
      App.ICONS.anchor = '<path d="M11.3 9.2v3" stroke-width="2.5"/>'
                       + '<path d="M11.3 10.7l6 2.8"/>'
                       + '<path d="M17.3 13.5l4.8 2.2" stroke-width="3.4"/>' + iconGround;
    }

    /* A boundary condition is a support: a triangle on hatched ground, the symbol
       engineering drawings use and the one the viewport draws on the soil edges.
       data.js's 'prescribed' (an arrow onto a line) read as a load, so it is
       replaced in place and the tool, its flyout, the menu row and the explorer rows
       all change with it. */
    App.ICONS.prescribed = '<path d="M12 3.5l-6.5 11h13z"/><path d="M3 17.5h18"/>'
                         + '<path d="M6.5 17.5L4 21M11 17.5L8.5 21M15.5 17.5L13 21'
                         + 'M20 17.5L17.5 21"/>';

    /* A new flow condition: the water table symbol, a triangle point down on the
       water line, over the water. */
    App.ICONS.watercondition = '<path d="M8 3.5h8L12 9.5z"/><path d="M3 9.5h18"/>'
                             + '<path d="M3 14.5c3-3 6 3 9 0s6-3 9 0"/>'
                             + '<path d="M3 19.5c3-3 6 3 9 0s6-3 9 0"/>';
    // The window of all conditions of a group: a table of rows.
    App.ICONS.conditionlist = '<path d="M3 4h18v16H3z"/>'
                            + '<path d="M3 9h18M3 14.5h18M8.5 4v16"/>';

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
    /* The camera goes with the file group: it saves something too. */
    if (!App.ICONS.camera) {
      App.ICONS.camera = '<path d="M3 8h4l2-3h6l2 3h4v11H3z"/><circle cx="12" cy="13" r="3.5"/>';
    }
    if (!App.TOOLBAR.some(function (t) { return t && t.action === 'savePicture'; })) {
      App.TOOLBAR.splice(App.TOOLBAR.indexOf('|'), 0, {
        icon: 'camera', tip: 'Save picture — the view as PNG, PDF or SVG', action: 'savePicture'
      });
    }
    /* Feedback, last on the toolbar and in the Help menu: always in sight in a workshop,
       and out of the way of the modelling tools (js/feedback-dialog.js). */
    if (!App.ICONS.feedback) {
      App.ICONS.feedback = '<path d="M4 5h16v11H10l-4 4v-4H4z"/><path d="M8 9.5h8M8 12.5h5"/>';
    }
    if (!App.TOOLBAR.some(function (t) { return t && t.action === 'feedback'; })) {
      App.TOOLBAR.push('|', {
        icon: 'feedback', wide: 'Feedback', action: 'feedback',
        tip: 'Send feedback — say what went wrong or what you would like; saved as a file'
      });
    }
    var helpMenu = (App.MENUS || []).filter(function (m) { return m.label === 'Help'; })[0];
    if (helpMenu && !helpMenu.items.some(function (i) { return i && i.action === 'feedback'; })) {
      var aboutAt = helpMenu.items.findIndex(function (i) { return i && i.action === 'about'; });
      helpMenu.items.splice(aboutAt < 0 ? helpMenu.items.length : aboutAt, 0,
                            { label: 'Send feedback…', icon: 'feedback', action: 'feedback' });
    }
    var viewMenu = (App.MENUS || []).filter(function (m) { return m.label === 'View'; })[0];
    if (viewMenu && !viewMenu.items.some(function (i) { return i && i.action === 'toggleRuler'; })) {
      var gridItem = viewMenu.items.filter(function (i) { return i && i.action === 'toggleGrid'; })[0];
      viewMenu.items.splice(viewMenu.items.indexOf(gridItem) + 1, 0,
        { label: 'Show rulers', icon: 'ruler', checked: rulersOn(), action: 'toggleRuler' });
    }
    applyRulers();

    // Named so that they are kept, here and in the Mesh menu alike. By icon, not by
    // tip, since the tip is replaced just below.
    var MESH_TOOL_ACTIONS = { refine: 'refineMesh', coarsen: 'coarsenMesh',
                              resetmesh: 'resetMeshRefinement' };
    // The frozen tips do not say that the tool works on the selected object.
    var MESH_TOOL_TIPS = {
      refine: 'Refine mesh — halve the mesh size of the selected object',
      coarsen: 'Coarsen mesh — double the mesh size of the selected object',
      resetmesh: 'Reset local refinement — the selected object takes the global mesh size'
    };
    (App.RAILS.mesh || []).forEach(function (tool) {
      if (tool && MESH_TOOL_ACTIONS[tool.icon]) {
        tool.action = MESH_TOOL_ACTIONS[tool.icon];
        tool.tip = MESH_TOOL_TIPS[tool.icon];
      }
    });
    if (!(App.RAILS.mesh || []).some(function (tool) { return tool && tool.action === 'meshSettings'; })) {
      App.RAILS.mesh.splice(2, 0, { icon: 'settings', tip: 'Mesh properties…', action: 'meshSettings' }, '-');
    }
    if (!(App.RAILS.mesh || []).some(function (tool) { return tool && tool.action === 'clearMesh'; })) {
      var generateTool = (App.RAILS.mesh || []).filter(function (tool) {
        return tool && tool.action === 'generateMesh';
      })[0];
      App.RAILS.mesh.splice(App.RAILS.mesh.indexOf(generateTool) + 1, 0,
        { icon: 'delete', tip: 'Clear mesh — the settings and local sizes stay', action: 'clearMesh' });
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
      if (!fileMenu.items.some(function (item) { return item && item.action === 'savePicture'; })) {
        var printAt = fileMenu.items.findIndex(function (item) {
          return item && item.label === 'Print…';
        });
        fileMenu.items.splice(printAt < 0 ? fileMenu.items.length : printAt, 0,
                              { label: 'Save picture…', icon: 'camera', action: 'savePicture' });
      }
      /* There is deliberately no menu item for any one model. Models are opened by
         running the Python that builds them -- `run <file.py>` in the command box --
         which works for any model, not only the one somebody thought to add a
         button for. See `runScript`. */
      // The project's name, beside the other whole-project items (Save, Pack project).
      if (!fileMenu.items.some(function (item) { return item && item.action === 'projectProperties'; })) {
        var packAt = fileMenu.items.findIndex(function (item) {
          return item && item.label === 'Pack project…';
        });
        fileMenu.items.splice(packAt === -1 ? fileMenu.items.length : packAt + 1, 0,
          { label: 'Project properties…', action: 'projectProperties' });
      }
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

    /* Help > Reference manual and Tutorial manual had no action in the frozen mockup
       (js/data.js:188), so they were greyed. They open the documentation site now
       (js/documentation.js), under the names its pages go by, side by side: the
       mockup had Command reference between the two. */
    var helpMenu = App.MENUS.find(function (m) { return m.label === 'Help'; });
    if (helpMenu) {
      var tutorials = null;
      helpMenu.items.forEach(function (item) {
        if (!item || typeof item !== 'object' || item.action) return;
        if (item.label === 'Reference manual') {
          item.label = 'Documentation';
          item.action = 'openDocumentation';
          item.page = 'home';
        } else if (item.label === 'Tutorial manual') {
          item.label = 'GUI tutorials';
          item.action = 'openDocumentation';
          item.page = 'tutorials';
          tutorials = item;
        }
      });
      if (tutorials) {
        helpMenu.items.splice(helpMenu.items.indexOf(tutorials), 1);
        var docsAt = helpMenu.items.findIndex(function (item) {
          return item && item.action === 'openDocumentation';
        });
        helpMenu.items.splice(docsAt + 1, 0, tutorials);
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
      App.RAILS.soil.push({ icon: 'cube', tip: 'Create soil volume…', action: 'createSoilVolume',
        flyout: [
          { icon: 'polygon', label: 'Draw soil surface', action: 'drawSoilSurface' },
          { icon: 'cube', label: 'Soil volume by coordinates…',
            action: 'createSoilBodyByCoordinates' }
        ] });
    }
    if (App.RAILS.soil) App.RAILS.soil = orderSoilRail(App.RAILS.soil);
    var soilMenu = (App.MENUS || []).filter(function (m) { return m.label === 'Soil'; })[0];
    if (soilMenu && !soilMenu.items.some(function (i) { return i && i.action === 'createSoilVolume'; })) {
      soilMenu.items.push('-');
      soilMenu.items.push({ label: 'Create soil volume…', icon: 'cube', action: 'createSoilVolume' });
    }
    if (soilMenu) soilMenu.items = orderSoilMenu(soilMenu.items);
    // The frozen Soil-mode hint asks for boreholes, which a layer no longer has.
    (App.MODES || []).forEach(function (mode) {
      if (mode.id === 'soil') mode.hint = SOIL_HINT;
    });
    // The frozen "Show material sets…" (js/data.js) opens the Soil materials window.
    (App.RAILS.soil || []).forEach(function (tool) {
      if (tool && tool.action === 'materials') tool.tip = 'Soil materials…';
    });
    menuItemsFor('materials').forEach(function (item) { item.label = 'Soil materials…'; });

    // Add Import model to Structures rail
    if (App.RAILS.structures) {
      App.RAILS.structures.forEach(function(tool) {
        if (!tool || !tool.icon) return;
        if (tool.icon === 'point') tool.action = 'drawPoint';
        // A line that splits the soil: drawn, or typed in its window.
        if (tool.icon === 'line') {
          tool.action = 'drawLine';
          tool.flyout = [
            { icon: 'line', label: 'Draw line', action: 'drawLine' },
            { icon: 'line', label: 'Line by coordinates…', action: 'createLineByCoordinates' }
          ];
        }
        if (tool.icon === 'polygon') tool.action = 'drawPolygon';
        // The frozen rail drew an interface button but had nothing to hang on it.
        if (tool.icon === 'interface') tool.action = 'interface';
        // And a prescribed displacement tool, which is a boundary condition: the button
        // opens the window of one new condition, the flyout the window of them all, or
        // draws one along a line or at a point.
        if (tool.icon === 'prescribed') Object.assign(tool, conditionTool());
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
        // through to App.Beams.start. The kind the open model cannot hold is greyed
        // by syncDimensionAvailability, and refuses itself with a reason should it
        // still be asked for.
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

      // Beside the condition tool: the window of all mechanical conditions.
      if (!App.RAILS.structures.some(function (tool) {
        return tool && tool.action === 'mechanicalConditions';
      })) {
        App.RAILS.structures.push(mechanicalConditionsTool());
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

    installBoundaryConditionTools();
    orderFlowBeforeMesh();
    installResultsMode();
    installStagesOverview();
    // The tabs and the bar were drawn at boot, before the reorder above.
    if (App.Toolbars && App.Toolbars.mountModes && document.getElementById('modetabs')) {
      App.Toolbars.mountModes();
      if (App.state && App.Toolbars.highlightMode) App.Toolbars.highlightMode(App.state.mode);
    }
    if (App.Menu && App.Menu.mountBar && document.getElementById('menubar')) App.Menu.mountBar();

    /* Every live action is on its tool and its menu row by now, so whatever is still
       without one is what Styx does not do: take it out, of the menus and the rail.
       See NOT_YET. The rest is the menus starting out in step with the toolbar:
       Undo was enabled in the Edit menu and greyed on the toolbar until the first
       edit, and the ticks were js/data.js's, not the state's. */
    dropEverythingNotYet();
    syncHistoryButtons();
    syncCheckMarks();

    /* The stages panel, on the project's own stages. `App.setMode` calls
       `mountPhases` whenever staged mode is entered (js/app.js:33), and the frozen
       one reads `App.PHASES` -- so replacing the function is what makes every entry
       into the mode draw the real sequence. */
    if (App.Explorer && App.Explorer.mountPhases) {
      App.Explorer.mountPhases = mountLiveStages;
      if (App.state && App.state.mode === 'staged') mountLiveStages();
    }

    /* The stage dots follow the last run: `calculate.js` hands the result over and
       the panel colours the stages that completed.

       And then the app goes to Results. A calculation that produced something to look
       at and left you on the stage editor is a calculation you have to go and find the
       output of -- which is exactly what this whole milestone exists to stop. The
       switch waits for `ready()`, because until the run has been read there are no
       stages to show; and it is gated on there being a readable stage, so a run that
       died before writing anything leaves you where you were, next to the error. */
    if (App.Calculate && App.Calculate.run && !App.Calculate.run.__stages) {
      var frozenCalcRun = App.Calculate.run;
      App.Calculate.run = function (done) {
        return frozenCalcRun(function (result) {
          rememberRun(result);
          if (done) done(result);
          // A run the user stopped leaves them where they were, at the model.
          if (!result || result.stopped || !App.Results || !App.Results.ready) return;
          App.Results.ready().then(function () {
            if (App.Results.stage()) App.setMode('results');
          });
        });
      };
      App.Calculate.run.__stages = true;
    }

    // Model explorer: enable Delete for drawn/imported geometry (see onTreeContextMenu).
    if (App.Explorer && App.Explorer.mountTree) {
      var frozenMountTree = App.Explorer.mountTree;
      App.Explorer.mountTree = function (mode) {
        frozenMountTree(mode);
        tagTreeRowsWithObjKeys(mode);
        addPartColorToggles(mode);
        addStageChecks(mode);
        addConditionChecks(mode);
      };
      // The frozen Expand all and Collapse all mount the tree through their own closure,
      // which skips everything added above; mounted again here, they keep it.
      var frozenExpandAll = App.Explorer.expandAll;
      App.Explorer.expandAll = function (on) {
        frozenExpandAll(on);
        App.Explorer.mountTree(App.state.mode);
      };
    }
    if (typeof document !== 'undefined') {
      var treeHost = document.getElementById('tree-model');
      if (treeHost) treeHost.addEventListener('contextmenu', onTreeContextMenu, true);
    }

    replaceMockupText();
    if (App.Dialogs && App.Dialogs.commandReference && !App.Dialogs.commandReference.__live) {
      App.Dialogs.commandReference = commandReference;
      App.Dialogs.commandReference.__live = true;
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
        hint: 'Results mode — read back what a calculation wrote: choose a stage and a '
            + 'quantity, or type "results fields" to see what this stage offers.'
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

      if (App.ICONS && !App.ICONS.convergence) {
        App.ICONS.convergence = '<path d="M4 4v16h16"/>'
          + '<path d="M7 6l3 5 3-2 3 6 3 2"/><path d="M6 17.5h14" stroke-dasharray="2 2"/>';
      }

      App.RAILS = App.RAILS || {};
      App.RAILS.results = [
        { icon: 'select', tip: 'Select', toggle: true, on: true },
        '-',
        // The chooser never opens by itself; this is how the user opens it.
        { icon: 'results', tip: 'Choose results', action: 'chooseResults' },
        { icon: 'wallplot', tip: 'Plot along the wall — M, Q, N, ux and the earth '
            + 'pressure on it, every stage', action: 'plotResults' },
        { icon: 'convergence', tip: 'Convergence — how the solver converged, iteration '
            + 'by iteration', action: 'showConvergence' }
      ];

      /* `App.setMode` is frozen and knows only about the stages panel (js/app.js:25).
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
         show an empty stage list while the run was being read in the background. */
      if (App.Results.onChange) {
        App.Results.onChange(function () {
          mountResultsPanel();
          refreshResultsMenu();
          followRunInPlot();
          // The loads and the water over the contour follow the stage on screen.
          if (App.state && App.state.mode === 'results' && App.Viewport
              && App.Viewport.applyStageVisibility) {
            App.Viewport.applyStageVisibility();
          }
        });
      }

      // The Convergence window: its own file, which hears from App.Calculate and
      // App.ConvergencePlot itself.
      if (App.ConvergenceWindow) App.ConvergenceWindow.install();

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

      // The Stages menu carries the same action (js/data.js:177); one action, one
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
       Stages -- and Results arrived without its half of that pairing. Everything in
       it runs one of the `results ...` commands, so the menu, the panel and the
       command box are three ways into one tested implementation.

       `Stage` and `Field` are filled in from the open run. `App.Menu.build` reads
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
          { label: 'Stage', sub: [] },
          { label: 'Previous stage', action: 'resultsRun', cmd: 'results stage -' },
          { label: 'Next stage', action: 'resultsRun', cmd: 'results stage +' },
          '-',
          { label: 'Field', sub: [] },
          { label: 'Integration points', sub: [] },
          { label: 'Arrows', sub: [] },
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
          { label: 'Fit range to this stage', action: 'resultsRun',
            cmd: 'results range auto' },
          '-',
          { label: 'Value at a node…', action: 'resultsAtNode' },
          { label: 'Convergence…', icon: 'convergence', action: 'showConvergence' },
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

    /* The one menu entry that needs a value typed. It asks for one integer in the
       app's own small window (js/name-dialog.js), not the browser's prompt, and the
       answer is printed to the command log by the same `results at` the command box
       runs. */
    function askForNode() {
      if (App.state && App.state.mode !== 'results') App.setMode('results');
      return App.NameDialog.ask({
        title: 'Value at a node', label: 'Node number',
        help: 'Every field at this node is printed in the Session log.',
        empty: 'Type a node number.',
        check: function (text) {
          return /^\d+$/.test(text) ? null : '"' + text + '" is not a node number.';
        }
      }).then(function (node) {
        if (node !== null) resultsCommand('results at ' + node);
      });
    }

    function itemsOf(label) {
      if (!resultsMenu) return null;
      return resultsMenu.items.filter(function (it) {
        return it && it.label === label;
      })[0];
    }

    function refreshResultsMenu() {
      var stage = itemsOf('Stage');
      var field = itemsOf('Field');
      if (!stage || !field || !App.Results) return;
      var state = App.Results.state();

      stage.sub = (state.stages || []).map(function (s) {
        return {
          label: s.index + '  ' + s.stage, checked: s.index === state.stage,
          disabled: !s.results, action: 'resultsRun',
          cmd: 'results stage ' + s.index
        };
      });
      stage.disabled = !stage.sub.length;

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

      /* Where a stress or the hydraulic head -- computed at the integration points --
         is drawn. Set for all of them at once; offered while one is on screen. */
      var integration = itemsOf('Integration points');
      if (integration) {
        integration.sub = [
          { label: 'Per element (as computed)', action: 'resultsRun',
            checked: state.integration !== 'nodes', cmd: 'results location elements' },
          { label: 'Averaged to the nodes', action: 'resultsRun',
            checked: state.integration === 'nodes', cmd: 'results location nodes' }
        ];
        integration.disabled = !state.integrationField;
      }

      /* Arrows: off, or any vector the stage has, over whatever is shaded -- the
         flux over the head, say. */
      var arrows = itemsOf('Arrows');
      if (arrows) {
        arrows.sub = [
          { label: 'Off', action: 'resultsRun', checked: !state.arrows,
            cmd: 'results arrows off' }
        ];
        if ((state.vectors || []).length) arrows.sub.push('-');
        (state.vectors || []).forEach(function (vector) {
          arrows.sub.push({
            label: vector.group + ' · ' + vector.label + '  (' + vector.unit + ')',
            checked: state.arrows === vector.name, action: 'resultsRun',
            cmd: 'results arrows ' + vector.name
          });
        });
        arrows.disabled = !(state.vectors || []).length;
      }

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
        colours.sub.push({
          label: 'Show loads and water', checked: options.loads !== false,
          action: 'resultsRun',
          cmd: 'results loads ' + (options.loads === false ? 'on' : 'off')
        });
        // As the panel's box: a flow stage always draws the line, so it is offered
        // only over a coupled stage that wrote a water pressure.
        if (state.pressure && state.calculation !== 'flow') {
          colours.sub.push({
            label: 'Show zero pressure line', checked: !!options.zeroLine,
            action: 'resultsRun',
            cmd: 'results zeroline ' + (options.zeroLine ? 'off' : 'on')
          });
        }
      }
    }

    /* "View calculation results" -- the toolbar's chart button and the Stages menu
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
       choosing a stage and a quantity is the thing this mode is for.

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
       A member's results along it, a panel per stage -- the figure is
       `App.ResultsPlot.svg()`, a tested string, and this window only hosts it. Modeless
       like the chooser, for the same reason: it is read beside the model, not finished
       and dismissed. Its controls are the `results plot ...` commands, so the window,
       the menu and the command box cannot disagree. */

    function openPlotWindow() {
      if (plotWindow) return plotWindow;
      if (!App.Dialogs || !App.Dialogs.open) return null;

      var saveMenu = null;
      var handle = App.Dialogs.open({
        title: 'Plot along the wall',
        width: 1180, height: 560,
        buttons: [
          { label: 'Save ▾', keepOpen: true, onClick: function () { saveMenu.toggle(); } },
          { label: 'Close', primary: true }
        ],
        onClose: function () { saveMenu.close(); plotWindow = null; plotColumns = 0; }
      });
      handle.dialog.classList.add('dlg-plot');
      saveMenu = App.Picture.saveMenu(handle.dialog.querySelector('.dlg-foot .btn'),
                                      function (format) { resultsCommand('results plot ' + format); });

      var layer = document.getElementById('modal-layer');
      var scrims = layer ? layer.querySelectorAll('.scrim') : [];
      if (scrims.length) {
        var scrim = scrims[scrims.length - 1];
        if (scrim.parentNode) scrim.parentNode.removeChild(scrim);
      }

      plotWindow = handle;
      renderPlotWindow(true);

      // Panels per row follow the window's width, so widening it puts the stages side
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
       more than five (the reference figure's row) nor more than there are stages. */
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
      var resultsOn = inResults;
      inResults = on;
      if (on) {
        mountResultsPanel();
        // Already in Results: a redraw of the same tab (a part switched off in the
        // Model explorer, any edit that rebuilds the geometry). The contour and the
        // windows are still up as the user left them; leave them alone.
        if (resultsOn) return;
        var back = resultsLeft;
        resultsLeft = null;
        // Show the result that is open straight away: the same stage and field as
        // last time, or the first one a new run opens on. The Choose results window
        // never opens by itself -- asking again on every visit was in the way, and
        // the dock panel and the rail's "Choose results" are always there.
        if (App.Results.field()) App.Results.redraw();
        if (back && back.run === App.Results.current() && back.plot) openPlotWindow();
      } else {
        // Remember what was on screen, so coming back shows it again. Only on the
        // way out of Results: going from one other mode to the next must not
        // overwrite it.
        if (resultsOn && App.Results.current()) {
          resultsLeft = { run: App.Results.current(), plot: !!plotWindow };
        }
        // Leaving takes the contour off the model rather than leaving it behind under
        // the geometry, where it would be neither editable nor explicable -- and the
        // windows with it, since they belong to a mode that is no longer on.
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
      rows.push(row('Stage', select('stage', (state.stages || []).map(function (s) {
        return { value: s.index, label: s.index + '  ' + s.stage,
                 selected: s.index === state.stage, disabled: !s.results };
      }))));

      // One <optgroup> per group of the catalogue, as the Field menu has a title each.
      var fields = [];
      ((state.catalogue && state.catalogue.groups) || []).forEach(function (group) {
        group.fields.forEach(function (entry) {
          fields.push({ value: entry.name, group: group.name,
                        label: entry.label + '  (' + entry.unit + ')',
                        selected: state.field && state.field.field === entry.name });
        });
      });
      rows.push(row('Field', fields.length
        ? select('field', fields)
        : '<span class="dock-empty">this stage wrote nothing</span>'));
      if (state.integrationField) {
        rows.push(row('Location', select('location', [
          { value: 'elements', label: 'per element (as computed)',
            selected: state.integration !== 'nodes' },
          { value: 'nodes', label: 'averaged to the nodes',
            selected: state.integration === 'nodes' }
        ])));
      }
      if ((state.vectors || []).length) {
        rows.push(row('Arrows', select('arrows', [
          { value: 'off', label: 'off', selected: !state.arrows }
        ].concat(state.vectors.map(function (vector) {
          return { value: vector.name, label: vector.label + '  (' + vector.unit + ')',
                   selected: state.arrows === vector.name };
        })))));
      }

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
      /* The legend's limits. An empty box follows the stage -- its own value is the
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
                  'Legend minimum — leave empty to follow the stage')
          + '<span class="res-limits-to">…</span>'
          + limit('lim-max', options.max, state.field.max,
                  'Legend maximum — leave empty to follow the stage')
          + '<button type="button" data-res="lim-auto"'
          + " title=\"Back to this stage's own range\">Auto</button>"
          + '<span class="res-limits-unit">' + esc(state.field.unit) + '</span></span>'));
      }
      rows.push(row('Reverse', '<input type="checkbox" data-res="reverse"'
                               + (options.reversed ? ' checked' : '') + '>'));
      rows.push(row('Mesh', '<input type="checkbox" data-res="mesh"'
                            + (options.mesh ? ' checked' : '') + '>'));
      rows.push(row('Loads, water', '<input type="checkbox" data-res="loads"'
                                    + (options.loads !== false ? ' checked' : '')
                                    + ' title="The loads and the water level over the'
                                    + ' colours">'));
      /* The zero water pressure line. A flow stage always draws it, so the box is only
         offered for a coupled one -- and only when the stage wrote a water pressure. */
      if (state.pressure && state.calculation !== 'flow') {
        rows.push(row('Zero pressure', '<input type="checkbox" data-res="zeroline"'
                                  + (options.zeroLine ? ' checked' : '')
                                  + ' title="The line where the water pressure is zero'
                                  + ' (the phreatic surface)">'));
      }
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

      bind(body, 'stage', function (value) { return 'results stage ' + value; });
      bind(body, 'field', function (value) { return 'results field ' + value; });
      bind(body, 'location', function (value) { return 'results location ' + value; });
      bind(body, 'arrows', function (value) { return 'results arrows ' + value; });
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
      var loadsBox = body.querySelector('[data-res="loads"]');
      if (loadsBox) {
        loadsBox.addEventListener('change', function () {
          resultsCommand('results loads ' + (loadsBox.checked ? 'on' : 'off'));
        });
      }
      var zeroBox = body.querySelector('[data-res="zeroline"]');
      if (zeroBox) {
        zeroBox.addEventListener('change', function () {
          resultsCommand('results zeroline ' + (zeroBox.checked ? 'on' : 'off'));
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

    /* An entry with a `group` goes in an <optgroup> of that name, consecutive entries
       of one group in one. */
    function select(name, entries) {
      var html = '', open = null;
      entries.forEach(function (entry) {
        var group = entry.group || null;
        if (group !== open) {
          if (open !== null) html += '</optgroup>';
          if (group !== null) html += '<optgroup label="' + esc(group) + '">';
          open = group;
        }
        html += '<option value="' + esc(entry.value) + '"'
             + (entry.selected ? ' selected' : '')
             + (entry.disabled ? ' disabled' : '') + '>'
             + esc(entry.label) + '</option>';
      });
      if (open !== null) html += '</optgroup>';
      return '<select data-res="' + name + '">' + html + '</select>';
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

      // `picture`, `picture copy`, `picture save`: the Save picture window's words.
      if (runPictureCommand(text)) return;
      // `feedback [text]`: the Feedback window, with the text in it.
      if (runFeedbackCommand(text)) return;
      // `colour <part>`: the Model explorer's colour toggle, typed.
      if (runColourCommand(text)) return;
      // `water <level>` / `water off`: the project's water level.
      if (runWaterCommand(text)) return;
      // `boundary list|standard`: the boundary conditions.
      if (runBoundaryCommand(text)) return;
      // `units` / `units <system>`: the project's unit system.
      if (runUnitsCommand(text)) return;
      // `domain` / `domain --x FROM TO --y BOTTOM TOP`: the size of the soil block.
      if (runDomainCommand(text)) return;
      // `node <id>`: which SubModelParts a node is in.
      if (runNodeCommand(text)) return;
      // `script <file.py>`: the model written as a Python file that builds it again.
      if (runScriptCommand(text)) return;

      var cmd = (text || '').trim().split(/\s+/)[0].toLowerCase();
      if (cmd === 'calculate') {
        if (App.Command.write) App.Command.write('echo', '> ' + text.trim());
        // `calculate stop`: typed, so it does not ask first.
        if ((text.trim().split(/\s+/)[1] || '').toLowerCase() === 'stop') {
          if (App.Calculate && App.Calculate.stop) return App.Calculate.stop();
          return;
        }
        if (refuseCalculate()) return;
        if (App.Calculate) return App.Calculate.run();
        return;
      }
      if (cmd === 'stages' || cmd === 'phases') {
        if (App.Command.write) App.Command.write('echo', '> ' + text.trim());
        stagesDialog();
        return;
      }
      if (cmd === 'clearmesh') {
        if (App.Command.write) App.Command.write('echo', '> ' + text.trim());
        clearMesh();
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
         server's own message verbatim -- core/scripting.py writes them to be read here,
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
                + ' — a Kratos deck, opened with its own mesh.', true)
                .then(function () { showDeck(result.mesh, result.project); });
            }
            return adoptProject(result.project,
              'Ran ' + scriptPath + ' — model built. Meshing it now.', true)
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
      // js/command.js would call it "not in the demo command list".
      if (!shellAnswers(cmd.replace(/^_/, ''))) {
        if (App.Command.write) App.Command.write('echo', '> ' + text.trim());
        App.Command.err('Unknown command "' + text.trim().split(/\s+/)[0]
                        + '". Type help to see the commands.');
        return;
      }
      return frozenRun(text);
    };

    /* The frozen "Modify soil layers" drew the stack once per borehole; the live
       window (js/soil-layers-dialog.js) has one layer table. Opened by the Soil menu,
       the rail and `soillayers`, which all call App.Dialogs.soilLayers. */
    if (App.Dialogs && App.SoilLayersDialog) {
      App.Dialogs.soilLayers = App.SoilLayersDialog.open;
    }
    /* The Model explorer's Delete on a layer: the frozen one closed the gap once per
       borehole. */
    if (App.SoilLayersDialog) App.deleteLayerById = App.SoilLayersDialog.removeById;

    /* Edits made straight from the Model/Selection explorer — a layer deleted or
       renamed from the tree, a material reassigned, a level or a domain extent
       typed into the property grid. The frozen hook only refreshes the browser;
       here the soil model goes to the server as one request, because the layers
       and the domain are validated together. A rejected write is
       rolled back by re-reading the stored project, so the grid can never keep
       showing a value the model does not hold. */
    App.commitSelectionEdit = function (objKey) {
      var reselect = objKey === undefined ? App.state.selection : objKey;

      // A row of the Mesh group: the object's local mesh size, a mesh setting.
      if (App.PENDING_MESH_SIZE) {
        var pending = App.PENDING_MESH_SIZE;
        App.PENDING_MESH_SIZE = undefined;
        return App.MeshSettings.saveLocalSize(pending.key, pending.size, pending.band)
          .catch(function (error) { App.Command.err(error.message); });
      }

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

      if (App.BoundaryConditions && App.BoundaryConditions.isConditionKey(reselect)) {
        var condition = (App.BOUNDARY_CONDITIONS || []).filter(function (item) {
          return item.id === reselect;
        })[0];
        // The record is the whole write, as for a normal load.
        if (condition) return App.BoundaryConditions.save(condition);
      }

      if (App.Lines && App.Lines.isLineKey(reselect)) {
        var line = (App.LINES || []).filter(function (item) { return item.id === reselect; })[0];
        if (line) return App.Lines.save(line);
      }

      if (App.Lines && App.Lines.bodyOf(reselect)) {
        return App.Lines.saveBody(reselect, { mat: App.Lines.bodyOf(reselect).mat || null });
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
        var fluidSnapshot = copy(App.FLUID || {});
        frozenMaterials(onClose);
        var dialogs = document.querySelectorAll('#modal-layer .dialog');
        var dialog = dialogs[dialogs.length - 1];
        if (!dialog) return;

        var committed = false;
        function discard() {
          App.MATERIALS = copy(snapshot);
          App.FLUID = copy(fluidSnapshot);
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

            App.Api.patch('/api/project/materials',
                          { materials: App.Model.materialsToServer(App.MATERIALS),
                            fluid: App.FLUID || null })
              .then(function (response) {
                App.Model.apply(response.project);
                return App.Viewport.refresh();
              })
              .then(function () {
                App.Command.ok('Soil materials saved — ' + App.MATERIALS.length
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
      // F1, Help > Documentation, from anywhere: it types nothing, so the command box
      // has no use for it. Taken from the browser, whose own F1 opens its help pages.
      document.addEventListener('keydown', function (event) {
        if (event.key !== 'F1' || event.ctrlKey || event.altKey || event.shiftKey) return;
        event.preventDefault();
        App.runAction({ action: 'openDocumentation', page: 'home' });
      });
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
        var entry = document.getElementById('cmd-entry');
        if (entry && event.target === entry && event.key === 'Enter') {
          var text = entry.value.trim();
          if (!text) return;
          event.preventDefault(); event.stopImmediatePropagation();
          cmdHistory.push(text); cmdIndex = cmdHistory.length;
          recordHistory(text);
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
  }

  return {
    install: install, meshSummary: meshSummary,
    collapsibleResultsPanel: collapsibleResultsPanel,
    COMMANDS: COMMANDS, helpLines: helpLines, shellAnswers: shellAnswers,
    replaceMockupText: replaceMockupText,
    snapshotLayers: snapshotLayers, restoreLayers: restoreLayers,
    isDeletableCustomPart: isDeletableCustomPart, tagTreeRowsWithObjKeys: tagTreeRowsWithObjKeys,
    MODES: MODES, patchFor: patchFor, sectionLabel: sectionLabel,
    DEFAULT_MODEL_MODE: DEFAULT_MODEL_MODE,
    missingViewportApi: missingViewportApi, staleMessage: staleMessage,
    reportUncaught: reportUncaught,
    setModelMode: setModelMode, syncModelMode: syncModelMode, syncViewMode: syncViewMode,
    THREE_D_ONLY: THREE_D_ONLY, availableIn2D: availableIn2D,
    TWO_D_ONLY: TWO_D_ONLY, availableIn3D: availableIn3D,
    syncDimensionAvailability: syncDimensionAvailability, syncHistoryButtons: syncHistoryButtons,
    NOT_YET: NOT_YET, implemented: implemented, tidySeparators: tidySeparators,
    dropEverythingNotYet: dropEverythingNotYet, syncCheckMarks: syncCheckMarks,
    gateViewportItems: gateViewportItems,
    newProject: newProject, openProject: openProject, saveProject: saveProject,
    wipeSession: wipeSession,
    projectFileName: projectFileName, projectFromFileText: projectFromFileText,
    projectNameFromFile: projectNameFromFile,
    setNavigation: setNavigation, gateRail: gateRail,
    rulersOn: rulersOn, toggleRulers: toggleRulers, applyRulers: applyRulers,
    withLabelRows: withLabelRows, toggleLabels: toggleLabels,
    extendViewportMenu: extendViewportMenu,
    orderStructuresRail: orderStructuresRail,
    orderSoilRail: orderSoilRail,
    orderSoilMenu: orderSoilMenu,
    moveBefore: moveBefore,
    STRUCTURES_RAIL_GROUPS: STRUCTURES_RAIL_GROUPS,
    nameSoilBodyActions: nameSoilBodyActions,
    withIntersectRows: withIntersectRows, intersectSurfaces: intersectSurfaces,
    drawSoilSurface: drawSoilSurface,
    deleteRequest: deleteRequest, deleteCustomPart: deleteCustomPart, onTreeContextMenu: onTreeContextMenu,
    projectProperties: projectProperties,
    objectKind: objectKind, renameObject: renameObject, deleteObject: deleteObject,
    renameBodyPart: renameBodyPart, deleteBodyOwner: deleteBodyOwner,
    deleteBodyPart: deleteBodyPart, deleteBody: deleteBody,
    syncCalculate: syncCalculate, calculateTip: calculateTip, CALCULATE_TIP: CALCULATE_TIP,
    resetForTests: resetForTests
  };
})();

App.LivePatches.install();
