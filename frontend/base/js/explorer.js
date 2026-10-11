/* ══════════════════════════════════════════════════════════════════
   explorer.js — Model explorer tree, Selection explorer property grid
   and the Phases explorer.
   ══════════════════════════════════════════════════════════════════ */

App.Explorer = (function () {
  var el = App.UI.el, icon = App.UI.icon;
  var rowsByObj = {};      // viewport key -> [tree row elements]
  var eyesByObj = {};      // viewport key -> [checkbox elements]

  /* ══════════════════════════════════════════════════════════════
     Model explorer
     ══════════════════════════════════════════════════════════════ */
  /**
   * Rebuilds the Model explorer tree for a workbench mode.
   * Resets the row/checkbox lookups and re-applies the current selection.
   * @param {string} mode One of 'soil', 'structures', 'mesh', 'flow', 'staged'.
   */
  function mountTree(mode) {
    var host = App.UI.clear(document.getElementById('tree-model'));
    var tree = el('div.tree');
    rowsByObj = {}; eyesByObj = {};
    (App.TREES[mode] || []).forEach(function (n) { tree.appendChild(node(n, 0)); });
    host.appendChild(tree);
    syncSelection(App.state.selection);
  }

  /**
   * Builds a tree node (row plus collapsible children) from a tree descriptor.
   * Registers bound rows and checkboxes in rowsByObj / eyesByObj.
   * @param {!Object} data Tree descriptor; its `expanded` flag is set in place.
   * @param {number} depth Nesting level, 0 for root nodes.
   * @return {!Element} The node wrapper element.
   */
  function node(data, depth) {
    if (data.expanded === undefined) data.expanded = depth === 0;

    var wrap = el('div.tree-node');
    var row = el('div.tree-row');
    row.style.paddingLeft = (4 + depth * 13) + 'px';

    var hasKids = data.children && data.children.length;
    var twisty = el('span.tree-twisty' + (hasKids ? '' : '.leaf'),
                    { text: data.expanded ? '▼' : '▶' });
    row.appendChild(twisty);

    // Visibility checkbox (only on nodes bound to a viewport object).
    if (data.eye && data.obj) {
      var eye = el('span.tree-eye' + (App.Viewport.isVisible(data.obj) ? '' : '.off'));
      eye.addEventListener('click', function (e) {
        e.stopPropagation();
        var on = eye.classList.contains('off');
        App.Viewport.setVisible(data.obj, on);
        syncEyes(data.obj, on);
        App.Command.note((on ? 'Shown: ' : 'Hidden: ') + data.label.split('  ')[0]);
      });
      row.appendChild(eye);
      (eyesByObj[data.obj] = eyesByObj[data.obj] || []).push(eye);
    } else {
      row.appendChild(el('span.tree-eye.hidden-slot'));
    }

    if (data.swatch) {
      var sw = el('span.tree-swatch');
      sw.style.background = data.swatch;
      row.appendChild(sw);
    } else if (data.icon) {
      var ic = el('span.tree-icon');
      ic.appendChild(icon(data.icon));
      row.appendChild(ic);
    } else {
      row.appendChild(el('span.tree-icon'));
    }

    row.appendChild(el('span.tree-label', { text: data.label }));
    if (data.count !== undefined) row.appendChild(el('span.tree-count', { text: '[' + data.count + ']' }));

    var kids = null;
    if (hasKids) {
      kids = el('div.tree-children' + (data.expanded ? '' : '.collapsed'));
      data.children.forEach(function (c) { kids.appendChild(node(c, depth + 1)); });
      twisty.addEventListener('click', function (e) { e.stopPropagation(); toggle(); });
      row.addEventListener('dblclick', toggle);
    }

    /** Toggles the node between expanded and collapsed. */
    function toggle() {
      data.expanded = !data.expanded;
      twisty.textContent = data.expanded ? '▼' : '▶';
      kids.classList.toggle('collapsed', !data.expanded);
    }

    row.addEventListener('click', function () {
      App.selectObject(data.obj || null, 'tree');
      if (!data.obj) { clearRowHighlight(); row.classList.add('selected'); }
    });
    row.addEventListener('contextmenu', function (e) {
      e.preventDefault();
      // Soil layers are the tree's one genuinely removable node: App.LAYERS owns
      // them, and deleting one has a defined meaning for the stack.
      var layerId = layerIdOf(data.obj);
      App.Menu.openAt([
        { label: 'Zoom to object', icon: 'zoomfit', action: 'zoomFit' },
        { label: data.eye && data.obj && App.Viewport.isVisible(data.obj) ? 'Hide' : 'Show', icon: 'eye' },
        '-',
        { label: 'Rename…', disabled: !layerId, action: layerId ? 'renameLayer' : null },
        { label: 'Delete', icon: 'delete', disabled: !layerId,
          action: layerId ? 'deleteLayer' : null },
        '-',
        { label: 'Properties…', icon: 'settings' }
      ], e.clientX, e.clientY, function (it) {
        if (it.action === 'deleteLayer') return deleteLayerNode(layerId);
        if (it.action === 'renameLayer') return renameLayerNode(layerId);
        if (it.action) App.runAction(it);
        else if (/Hide|Show/.test(it.label) && data.obj) {
          var on = !App.Viewport.isVisible(data.obj);
          App.Viewport.setVisible(data.obj, on);
          syncEyes(data.obj, on);
        }
      });
    });

    if (data.obj) (rowsByObj[data.obj] = rowsByObj[data.obj] || []).push(row);

    wrap.appendChild(row);
    if (kids) wrap.appendChild(kids);
    return wrap;
  }

  /** Removes the selected highlight from every Model explorer row. */
  function clearRowHighlight() {
    document.querySelectorAll('#tree-model .tree-row.selected')
      .forEach(function (r) { r.classList.remove('selected'); });
  }

  /**
   * Updates every visibility checkbox bound to a viewport object.
   * @param {string} obj Viewport object key.
   * @param {boolean} on Whether the object is visible.
   */
  function syncEyes(obj, on) {
    (eyesByObj[obj] || []).forEach(function (e) { e.classList.toggle('off', !on); });
  }

  /**
   * Highlights (and scrolls to) the rows bound to a viewport object.
   * @param {?string} obj Viewport object key, or null to clear the highlight.
   */
  function syncSelection(obj) {
    clearRowHighlight();
    if (!obj) return;
    var rows = rowsByObj[obj] || [];
    rows.forEach(function (r) { r.classList.add('selected'); });
    if (rows.length) {
      var r = rows[0], host = document.getElementById('tree-model');
      var top = r.offsetTop, h = host.clientHeight;
      if (top < host.scrollTop || top > host.scrollTop + h - 24) host.scrollTop = Math.max(0, top - h / 3);
    }
  }

  /**
   * Expands or collapses every node of the current mode's tree and remounts it.
   * @param {boolean} on True to expand, false to collapse.
   */
  function expandAll(on) {
    (function walk(list) {
      list.forEach(function (n) {
        if (n.children) { n.expanded = on; walk(n.children); }
      });
    })(App.TREES[App.state.mode] || []);
    mountTree(App.state.mode);
  }

  /* ══════════════════════════════════════════════════════════════
     Selection explorer (property grid)
     ══════════════════════════════════════════════════════════════ */
  /**
   * Renders the Selection explorer property grid for an object.
   * @param {?string} objKey Selection key, or null to show the empty state.
   */
  function mountSelection(objKey) {
    var host = App.UI.clear(document.getElementById('grid-selection'));
    var def = objKey && App.OBJECT_PROPS[objKey];

    if (!def) {
      host.appendChild(el('div.pgrid-empty',
        { text: 'No object selected. Click an object in the viewport or the Model explorer.' }));
      return;
    }

    var grid = el('div.pgrid');
    var head = el('div.pgrid-header');
    head.appendChild(icon(def.icon || 'cube'));
    head.appendChild(el('span', { text: def.title }));
    grid.appendChild(head);

    Object.keys(def.groups).forEach(function (g) {
      grid.appendChild(el('div.pgrid-group', { text: g }));
      def.groups[g].forEach(function (r) { grid.appendChild(propRow(r, objKey)); });
    });

    host.appendChild(grid);
  }

  /**
   * Builds a property row from [key, value, unit, readonly, editor].
   * With an editor descriptor (see App.LayerEditors in js/data.js) the row
   * renders a live control that commits through App.commitSelectionEdit,
   * which each build defines for itself.
   * @param {!Array<*>} r Row descriptor.
   * @param {?string=} objKey Selection key the row belongs to.
   * @return {!Element} The row element.
   */
  function propRow(r, objKey) {
    var key = r[0], val = r[1], unit = r[2] || '', ro = r[3], editor = r[4];
    var row = el('div.pgrid-row');
    row.appendChild(el('div.pgrid-key', { text: key }));

    var v = el('div.pgrid-val' + (ro ? '.readonly' : '.editable'));

    if (editor && !ro) {
      v.classList.add('field');
      v.appendChild(editorControl(editor, key, objKey));
      if (unit) v.appendChild(el('span.unit', { text: unit }));
    } else if (typeof val === 'boolean') {
      var cb = el('input.pgrid-check', { type: 'checkbox' });
      cb.checked = val;
      cb.disabled = !!ro;
      v.classList.remove('editable');
      v.appendChild(cb);
    } else {
      v.appendChild(el('span', { text: String(val) }));
      if (unit) v.appendChild(el('span.unit', { text: unit }));
    }
    row.appendChild(v);
    return row;
  }

  /**
   * Returns the soil layer id for a selection key ('soil_L1' -> 'L1').
   * @param {?string} objKey Selection key.
   * @return {?string} The layer id, or null when it is not an existing layer.
   */
  function layerIdOf(objKey) {
    if (!objKey || objKey.indexOf('soil_') !== 0) return null;
    var id = objKey.slice(5);
    return App.layerById && App.layerById(id) ? id : null;
  }

  /**
   * Deletes a soil layer, clearing the selection if it pointed at that layer.
   * @param {string} layerId
   */
  function deleteLayerNode(layerId) {
    var layer = App.layerById(layerId);
    if (!layer) return;
    var err = App.deleteLayerById(layerId);
    if (err) { App.Command.write('err', err); return; }
    App.Command.ok('Deleted soil layer ' + layer.name + '.');
    if (App.state.selection === 'soil_' + layerId) App.selectObject(null);
    commit(null);
  }

  /**
   * Prompts for a new soil layer name and applies it.
   * @param {string} layerId
   */
  function renameLayerNode(layerId) {
    var layer = App.layerById(layerId);
    if (!layer) return;
    var name = window.prompt('Layer name', layer.name);
    if (name === null) return;
    name = name.trim();
    if (!name) { App.Command.write('err', 'Layer name cannot be empty.'); return; }
    layer.name = name;
    App.Command.ok('Renamed soil layer to ' + name + '.');
    commit(App.state.selection);
  }

  /**
   * Commits a model edit through App.commitSelectionEdit, when the build defines it.
   * @param {?string=} objKey Selection key that was edited.
   */
  function commit(objKey) {
    if (App.commitSelectionEdit) App.commitSelectionEdit(objKey);
  }

  /**
   * Writes an edit error to the command line.
   * @param {string} message
   */
  function reportEditError(message) {
    App.Command.write('err', message);
  }

  /**
   * Builds the input control (button, select or numeric field) for an editor descriptor.
   * @param {!Object} editor Editor descriptor with a `kind` and get/set callbacks.
   * @param {string} label Property name, used in error messages.
   * @param {?string=} objKey Selection key committed after a successful edit.
   * @return {!Element} The control element.
   */
  function editorControl(editor, label, objKey) {
    if (editor.kind === 'button') {
      var btn = el('button.btn.btn-sm', { type: 'button', text: editor.text });
      btn.addEventListener('click', function () { editor.run(); });
      return el('div.cell-mat', null, btn);
    }

    if (editor.kind === 'select') {
      var sel = el('select');
      editor.options().forEach(function (o) {
        sel.appendChild(el('option', { value: o.value, text: o.text }));
      });
      sel.value = editor.get();
      sel.addEventListener('change', function () {
        var err = editor.set(sel.value);
        if (err) { sel.value = editor.get(); reportEditError(err); return; }
        commit(objKey);
      });
      return el('div.cell-mat', null, sel);
    }

    // Numeric.
    var show = function () { return App.UI.fixed(editor.get(), editor.decimals || 3); };
    var inp = el('input.cell-input.cell-num', { value: show() });
    inp.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); inp.blur(); }
    });
    inp.addEventListener('change', function () {
      var n = parseFloat(inp.value.trim().replace(',', '.'));
      if (isNaN(n)) { inp.value = show(); reportEditError(label + ': "' + inp.value + '" is not a number.'); return; }
      var err = editor.set(n);
      if (err) { inp.value = show(); reportEditError(err); return; }
      commit(objKey);
    });
    return inp;
  }

  /* ══════════════════════════════════════════════════════════════
     Phases explorer
     ══════════════════════════════════════════════════════════════ */
  /**
   * Renders the Phases list and the property grid of the current phase.
   * Clicking a row sets App.state.phase and remounts the list.
   */
  function mountPhases() {
    var host = App.UI.clear(document.getElementById('list-phases'));
    var list = el('div.phase-list');

    App.PHASES.forEach(function (p) {
      var row = el('div.phase-row' + (p.id === App.state.phase ? '.selected' : ''));
      row.style.paddingLeft = (8 + p.depth * 10) + 'px';
      row.appendChild(el('span.phase-dot.' + p.state));
      row.appendChild(el('span.phase-name', { text: p.name }));
      row.appendChild(el('span.phase-kind', { text: p.kind }));
      row.addEventListener('click', function () {
        App.state.phase = p.id;
        mountPhases();
        App.Command.note('Current phase: ' + p.name);
      });
      list.appendChild(row);
    });

    host.appendChild(list);

    // Properties of the selected phase, underneath the list.
    var grid = el('div.pgrid');
    var sel = App.PHASES.filter(function (p) { return p.id === App.state.phase; })[0] || App.PHASES[0];
    var head = el('div.pgrid-header');
    head.appendChild(icon('phase'));
    head.appendChild(el('span', { text: sel.name }));
    grid.appendChild(head);
    Object.keys(App.PHASE_PROPS).forEach(function (g) {
      grid.appendChild(el('div.pgrid-group', { text: g }));
      App.PHASE_PROPS[g].forEach(function (r) { grid.appendChild(propRow(r)); });
    });
    host.appendChild(grid);
  }

  return {
    mountTree: mountTree, mountSelection: mountSelection, mountPhases: mountPhases,
    syncSelection: syncSelection, syncEyes: syncEyes, expandAll: expandAll
  };
})();
