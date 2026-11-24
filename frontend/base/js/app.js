/* ══════════════════════════════════════════════════════════════════
   app.js — application state, mode switching, action dispatch, boot.
   ══════════════════════════════════════════════════════════════════ */

/** @type {!Object} UI state shared by every module. */
App.state = {
  mode: 'soil',
  selection: null,
  phase: 'ph4',
  projection: true,     // true = perspective
  grid: true,
  snap: true
};

/* ── Mode switching ───────────────────────────────────────────── */
/**
 * Switches the application to another mode and remounts every mode-specific view.
 * @param {string} mode Id of an entry in App.MODES; unknown ids are ignored.
 */
App.setMode = function (mode) {
  var def = App.MODES.filter(function (m) { return m.id === mode; })[0];
  if (!def) return;
  App.state.mode = mode;

  App.Toolbars.highlightMode(mode);
  App.Toolbars.mountRail(mode);
  App.Explorer.mountTree(mode);
  App.Viewport.setMode(mode);

  var dock = document.getElementById('dock');
  var staged = mode === 'staged';
  dock.classList.toggle('has-phases', staged);
  document.getElementById('panel-phases').hidden = !staged;
  document.getElementById('split-dock2').hidden = !staged;
  // The phases panel joins and leaves the dock with the mode, so the row sizes have
  // to be recomputed -- collapsed or not, it must not be handed space it cannot use.
  App.UI.syncDock(dock);
  if (staged) App.Explorer.mountPhases();

  document.getElementById('sb-hint').textContent = def.hint;
  document.getElementById('vp-mode-label').textContent = def.label + ' mode';

  // A selection may not exist in the new mode.
  if (App.state.selection && !App.Viewport.isVisible(App.state.selection)) App.selectObject(null);
  else App.selectObject(App.state.selection, 'mode');

  if (mode === 'mesh' && !App.Viewport.hasMesh()) {
    App.Command.note('Mesh mode — no mesh generated yet. Use the "Generate mesh" tool (F9).');
  }
};

/* ── Selection ────────────────────────────────────────────────── */
/**
 * Selects an object in the viewport, Model explorer and Selection explorer.
 * @param {?string} key Object key, or null to clear the selection.
 * @param {string=} source Origin of the selection; 'viewport' also logs it.
 */
App.selectObject = function (key, source) {
  App.state.selection = key || null;
  App.Viewport.select(App.state.selection);
  App.Explorer.syncSelection(App.state.selection);
  App.Explorer.mountSelection(App.state.selection);
  if (key && source === 'viewport') {
    var def = App.OBJECT_PROPS[key];
    App.Command.note('Selected: ' + (def ? def.title : key));
  }
};

/* ── Viewport context menu ────────────────────────────────────── *//**
 * Opens the viewport context menu at the cursor, selecting the clicked object first.
 * @param {!MouseEvent} ev The contextmenu event.
 * @param {?string} key Key of the object under the cursor, or null for empty space.
 */App.viewportContextMenu = function (ev, key) {
  if (key) App.selectObject(key, 'viewport');
  var def = key && App.OBJECT_PROPS[key];
  var items = [];
  if (def) items.push({ title: def.title });
  items.push(
    { label: 'Zoom to fit', icon: 'zoomfit', key: 'F5', action: 'zoomFit' },
    { label: 'Isometric view', icon: 'cube', action: 'viewIso' },
    '-',
    { label: 'Hide selected', icon: 'eye', disabled: !key },
    { label: 'Hide all but selected', disabled: !key },
    { label: 'Show all', action: 'showAll' },
    '-',
    { label: 'Visibility settings…', icon: 'eye', action: 'visibility' },
    { label: 'Perspective projection', icon: 'persp',
      checked: App.state.projection, action: 'toggleProjection' },
    { label: 'Show grid', icon: 'grid', checked: App.state.grid, action: 'toggleGrid' }
  );

  App.Menu.openAt(items, ev.clientX, ev.clientY, function (it) {
    if (it.action) return App.runAction(it);
    if (/^Hide selected/.test(it.label) && key) {
      App.Viewport.setVisible(key, false);
      App.Explorer.syncEyes(key, false);
      App.Command.note('Hidden: ' + key);
    } else if (/^Hide all but/.test(it.label)) {
      ['soil', 'excavation', 'wall', 'struts', 'anchors', 'piles',
       'water', 'wells', 'mesh'].concat((App.LOADS || []).map(function (load) {
        return load.id;
      })).forEach(function (k) {
        var on = k === key;
        App.Viewport.setVisible(k, on);
        App.Explorer.syncEyes(k, on);
      });
    }
  });
};

/** Makes every object group and load visible again. */
App.showAll = function () {
  ['soil', 'excavation', 'wall', 'struts', 'anchors', 'piles',
   'water', 'wells', 'mesh'].concat((App.LOADS || []).map(function (load) {
    return load.id;
  })).forEach(function (k) {
    App.Viewport.setVisible(k, true);
    App.Explorer.syncEyes(k, true);
  });
  App.Command.note('All object groups shown.');
};

/**
 * Applies an edit made in the Model or Selection explorer to everything downstream.
 * The live build replaces this in live/js/patches.js, where the change goes to the
 * server first.
 * @param {?string=} objKey Row to re-select, or null; omitted keeps the selection.
 */
App.commitSelectionEdit = function (objKey) {
  App.refreshSoilData();
  App.Viewport.rebuildSoil();
  App.Explorer.mountTree(App.state.mode);
  App.Explorer.mountSelection(objKey === undefined ? App.state.selection : objKey);
};

/* ── Action dispatch (menus, toolbar, context menus) ──────────── */
/**
 * Runs the action named by a menu, toolbar or context-menu item.
 * Items without an action, or with an unknown one, only log a note.
 * @param {?Object} item Item descriptor; its `action` and `label` are read.
 */
App.runAction = function (item) {
  var a = item && item.action;

  if (!a) {
    if (item && item.label) App.Command.note('"' + item.label + '" is not implemented in this UI mockup.');
    return;
  }

  switch (a) {
    case 'zoomIn':   App.Viewport.dolly(1); break;
    case 'zoomOut':  App.Viewport.dolly(-1); break;
    case 'zoomFit':  App.Viewport.zoomFit(); break;
    case 'viewFront': setView('front'); break;
    case 'viewTop':   setView('top'); break;
    case 'viewSide':  setView('side'); break;
    case 'viewIso':   setView('iso'); break;

    case 'toggleProjection':
      App.state.projection = !App.state.projection;
      App.Viewport.setProjection(App.state.projection);
      App.Toolbars.setToolbarState('toggleProjection', App.state.projection);
      App.Command.note('Projection: ' + (App.state.projection ? 'perspective' : 'orthographic'));
      break;

    case 'toggleGrid':
      App.state.grid = !App.state.grid;
      App.Viewport.setGrid(App.state.grid);
      App.Toolbars.setToolbarState('toggleGrid', App.state.grid);
      break;

    case 'toggleSnap':
      App.state.snap = !App.state.snap;
      App.Toolbars.setToolbarState('toggleSnap', App.state.snap);
      document.getElementById('sb-snap').classList.toggle('active', App.state.snap);
      break;

    case 'toggleTriad':
      var tri = document.getElementById('vp-triad');
      tri.style.display = tri.style.display === 'none' ? '' : 'none';
      break;

    case 'toggleCmd':
      toggleCommandPanel();
      break;

    case 'visibility': App.Dialogs.visibility(); break;
    case 'soilLayers': App.Dialogs.soilLayers(); break;
    case 'materials':  App.Dialogs.materials(); break;
    case 'importSoilLayers': App.Dialogs.importSoilLayers(); break;
    case 'about':      App.Dialogs.about(); break;
    case 'cmdref':     App.Dialogs.commandReference(); break;
    case 'showAll':    App.showAll(); break;

    case 'createBorehole':
      var nb = App.addBorehole();
      App.refreshSoilData();
      App.Viewport.rebuildSoil();
      App.Explorer.mountTree(App.state.mode);
      App.Command.ok('Borehole added: ' + nb.name);
      break;

    case 'generateMesh':
      if (App.state.mode !== 'mesh') App.setMode('mesh');
      App.Command.write('echo', '> mesh 0.06');
      App.Viewport.generateMesh(function () {
        App.Command.ok('Mesh generated: 24118 elements, 38942 nodes');
        App.selectObject('mesh', 'viewport');
      });
      break;

    case 'viewMesh':
      if (!App.Viewport.hasMesh()) App.runAction({ action: 'generateMesh' });
      else App.selectObject('mesh', 'viewport');
      break;

    case 'calculate':
      App.Dialogs.notImplemented('Calculate',
        'In the full application this starts the calculation kernel for the phases marked ' +
        'for calculation in the Phases explorer.');
      break;

    case 'results':
      App.Dialogs.notImplemented('View calculation results',
        'In the full application this opens the Output program with deformation, stress and ' +
        'structural force result plots for the selected phase.');
      break;

    default:
      App.Command.note('Action "' + a + '" is not implemented in this UI mockup.');
  }
};

/**
 * Moves the camera to a preset view and highlights its view-cube button.
 * @param {string} name One of 'front', 'top', 'side' or 'iso'.
 */
function setView(name) {
  App.Viewport.setView(name);
  document.querySelectorAll('#vp-viewcube button').forEach(function (b) {
    b.classList.toggle('active', b.dataset.view === name);
  });
}

/* ── Status bar helpers (called from the viewport) ────────────── */
/**
 * Shows the cursor position in the status bar.
 * @param {number} x Metres.
 * @param {number} y Metres.
 * @param {number} z Metres.
 */
App.setCoords = function (x, y, z) {
  document.getElementById('sb-coords').textContent =
    'x ' + App.UI.fixed(x, 3) + ' m   y ' + App.UI.fixed(y, 3) +
    ' m   z ' + App.UI.fixed(z, 3) + ' m';
};

/**
 * Shows the zoom level in the status bar.
 * @param {number} pct Zoom as a percentage.
 */
App.setZoom = function (pct) {
  var n = document.getElementById('sb-zoom');
  var t = 'Zoom ' + pct + '%';
  if (n.textContent !== t) n.textContent = t;
};

/* ── Command panel show / hide ────────────────────────────────── */
var cmdHidden = false;
/** Shows or hides the command panel and its splitter, then resizes the viewport. */
function toggleCommandPanel() {
  cmdHidden = !cmdHidden;
  document.getElementById('cmdpanel').style.display = cmdHidden ? 'none' : '';
  document.getElementById('split-cmd').style.display = cmdHidden ? 'none' : '';
  document.documentElement.style.setProperty('--cmd-height', cmdHidden ? '0px' : '150px');
  App.Viewport.resize();
}

/* ── Boot ─────────────────────────────────────────────────────── *//** Mounts the UI, wires splitters and keyboard shortcuts, and enters Soil mode. */function boot() {
  document.getElementById('tb-title').textContent =
    App.PRODUCT.name + '  ' + App.PRODUCT.version + '  —  ' + App.PRODUCT.project + '  [Model]';

  App.Menu.mountBar();
  App.Toolbars.mountMain();
  App.Toolbars.mountModes();
  App.Command.mount();
  App.Viewport.init();

  /* Splitters */
  var vp = function () { App.Viewport.resize(); };
  App.UI.splitter(document.getElementById('split-left'), 'x', '--rail-width', 34, 132, false, vp);
  App.UI.splitter(document.getElementById('split-right'), 'x', '--dock-width', 210, 620, true, vp);
  App.UI.splitter(document.getElementById('split-cmd'), 'y', '--cmd-height', 0, 460, true, vp);
  App.UI.splitter(document.getElementById('split-dock1'), 'y', '--model-panel-height', 80,
                  function () { return Math.max(120, document.getElementById('dock').clientHeight - 160); });
  App.UI.splitter(document.getElementById('split-dock2'), 'y', '--phases-height', 90,
                  function () { return Math.max(120, document.getElementById('dock').clientHeight - 260); },
                  true);

  /* View cube */
  document.querySelectorAll('#vp-viewcube button').forEach(function (b) {
    b.addEventListener('click', function () { setView(b.dataset.view); });
  });

  /* Every dock section collapses to its header, by its caret or anywhere else on it */
  App.UI.collapsibleDock(document.getElementById('dock'));

  /* Dock header expand / collapse buttons */
  var tools = document.querySelectorAll('#panel-model .dock-head-tools button');
  if (tools[0]) tools[0].addEventListener('click', function () { App.Explorer.expandAll(true); });
  if (tools[1]) tools[1].addEventListener('click', function () { App.Explorer.expandAll(false); });

  /* Status-bar snapping toggle */
  document.getElementById('sb-snap').addEventListener('click', function () {
    App.runAction({ action: 'toggleSnap' });
  });

  /* Keyboard shortcuts */
  document.addEventListener('keydown', function (e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
    if (e.key === 'F5') { e.preventDefault(); App.Viewport.zoomFit(); }
    else if (e.key === 'F9') { e.preventDefault(); App.runAction({ action: 'calculate' }); }
    else if (e.key === 'Escape') App.selectObject(null);
    else if (e.ctrlKey && e.key >= '1' && e.key <= '5') {
      e.preventDefault();
      App.setMode(App.MODES[parseInt(e.key, 10) - 1].id);
    }
  });

  App.setMode('soil');
  App.Command.note('Tip: left-drag to orbit, middle-drag (or Shift+drag) to pan, wheel to zoom.');
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
else boot();
