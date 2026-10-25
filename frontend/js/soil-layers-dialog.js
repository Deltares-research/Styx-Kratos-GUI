/* ══════════════════════════════════════════════════════════════════
   soil-layers-dialog.js — the Modify soil layers window.

   Replaces the frozen one (js/dialogs.js:148), which drew the stack once per
   borehole. A layer has one top and one bottom now (core/model/schemas.py
   SoilLayer), so the window is one layer table, one column picture of the stack
   with the water level, and the custom soil volumes under the table.

   It edits a copy of the stack. OK sends that copy, with the material library, in
   one PATCH /api/project/layers; Cancel, the close button and Esc drop it. The
   stack edits below are the browser's twin of core/session.py `update_layer`,
   `split_layer` and `remove_layer`: a moved level moves the neighbour's level with
   it, and a level that would cross the neighbour's other face is refused. The
   Selection explorer's level rows (js/model.js `layerProps`) use the same rules.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.SoilLayersDialog = (function () {

  /* How thick Add makes a new layer, in metres: core/model/drafts.py LAYER_THICKNESS. */
  var THICKNESS = 5.0;

  var HINT = 'Type a name, a material, a level or a thickness: the column follows. ' +
             'A moved top or bottom moves the level of the next layer with it, so the ' +
             'stack has no gaps. The top of the first layer is the ground level.';

  function copy(value) { return JSON.parse(JSON.stringify(value)); }

  /* A level as the messages print it: 3 decimals at most, no trailing zeros. */
  function level(value) { return String(Number(Number(value).toFixed(3))); }

  /* ── The stack ─────────────────────────────────────────────────────────
     Each edit changes `layers` in place. A level edit gives back a sentence that
     says why it was refused, or null. */

  function newLayer(layers, material, top, bottom) {
    var number = 1;
    while (layers.some(function (layer) { return layer.id === 'L' + number; })) number++;
    return { id: 'L' + number, name: 'Soil_' + number, mat: material, top: top,
             bottom: bottom };
  }

  /* A layer under the stack, from the last layer's bottom -- `groundTop`, the top of
     the domain, for the first -- 5 m down (core/model/drafts.py `layer`). Gives back
     its index. */
  function add(layers, material, groundTop) {
    var last = layers[layers.length - 1];
    var top = last ? last.bottom : groundTop;
    layers.push(newLayer(layers, material, top, top - THICKNESS));
    return layers.length - 1;
  }

  /* Insert: the layer `i` halved, the lower half a new layer of the same material.
     Gives back the new layer's index. */
  function split(layers, i) {
    var upper = layers[i];
    var middle = (upper.top + upper.bottom) / 2;
    var lower = newLayer(layers, upper.mat, middle, upper.bottom);
    upper.bottom = middle;
    layers.splice(i + 1, 0, lower);
    return i + 1;
  }

  /* The layer `i` taken out; the layer above takes its bottom, or, for the top
     layer, the layer below takes its top. */
  function remove(layers, i) {
    var gone = layers.splice(i, 1)[0];
    if (i > 0) layers[i - 1].bottom = gone.bottom;
    else if (layers.length) layers[0].top = gone.top;
  }

  function setTop(layers, i, value) {
    var layer = layers[i], above = layers[i - 1];
    if (value < layer.bottom) {
      return 'The top must be at or above the bottom of the layer (' + level(layer.bottom) +
             ' m).';
    }
    if (above && value > above.top) {
      return 'The top cannot rise above the top of the layer above (' + level(above.top) +
             ' m).';
    }
    layer.top = value;
    if (above) above.bottom = value;
    return null;
  }

  function setBottom(layers, i, value) {
    var layer = layers[i], below = layers[i + 1];
    if (value > layer.top) {
      return 'The bottom must be at or below the top of the layer (' + level(layer.top) +
             ' m).';
    }
    if (below && value < below.bottom) {
      return 'The bottom cannot drop below the bottom of the layer below (' +
             level(below.bottom) + ' m).';
    }
    layer.bottom = value;
    if (below) below.top = value;
    return null;
  }

  /* The top stays; the bottom moves. */
  function setThickness(layers, i, value) {
    if (!(value >= 0)) return 'The thickness must be 0 or more.';
    return setBottom(layers, i, layers[i].top - value);
  }

  /* The Model explorer's Delete on a layer row (js/explorer.js `deleteLayerNode`):
     the frozen `App.deleteLayerById` closed the gap once per borehole. */
  function removeById(id) {
    var layers = App.LAYERS || [];
    if (layers.length <= 1) return 'A model needs at least one soil layer.';
    var i = layers.map(function (layer) { return layer.id; }).indexOf(id);
    if (i < 0) return 'That layer no longer exists.';
    remove(layers, i);
    return null;
  }

  /* The Selection explorer's editor of a layer's top or bottom (`edge`). */
  function levelEditor(layer, edge) {
    return {
      kind: 'number', decimals: 3, unit: 'm',
      get: function () { return layer[edge]; },
      set: function (value) {
        var i = (App.LAYERS || []).indexOf(layer);
        if (i < 0) return 'That layer no longer exists.';
        return (edge === 'top' ? setTop : setBottom)(App.LAYERS, i, value);
      }
    };
  }

  /* ── The column picture ────────────────────────────────────────────── */

  /* A tick spacing of 1, 2 or 5 times a power of ten, near `raw`. */
  function tickStep(raw) {
    var power = Math.pow(10, Math.floor(Math.log10(raw)));
    var n = raw / power;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * power;
  }

  /* The levels the picture spans, from the stack and the water level, widened to
     whole ticks. Null with nothing to draw. */
  function columnRange(layers, water) {
    var levels = [];
    layers.forEach(function (layer) { levels.push(layer.top, layer.bottom); });
    if (!levels.length) return null;
    if (water && Number.isFinite(water.y)) levels.push(water.y);
    var hi = Math.max.apply(null, levels), lo = Math.min.apply(null, levels);
    if (hi - lo < 1) { hi += 0.5; lo -= 0.5; }
    var step = tickStep((hi - lo) / 6);
    return { top: Math.ceil(hi / step) * step, bottom: Math.floor(lo / step) * step,
             step: step };
  }

  function svgNode(tag, attrs, text) {
    var node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.keys(attrs).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    if (text !== undefined) node.textContent = text;
    return node;
  }

  /* The stack as one column: a band per layer in its material's colour, the ground
     line at the top of the stack and the water level as a dashed line. A band click
     calls `onPick(i)`. */
  function drawColumn(layers, water, selected, onPick) {
    var range = columnRange(layers, water);
    if (!range) return null;
    var H = 400, PAD = 14, AXIS = 50, COL = 110, W = AXIS + COL + 44;
    var scale = H / (range.top - range.bottom);
    function y(z) { return PAD + (range.top - z) * scale; }
    var font = 'Segoe UI, Arial';
    var decimals = range.step < 1 ? 1 : 0;

    var svg = svgNode('svg', { 'class': 'soil-column-svg', width: W, height: H + 2 * PAD,
                               viewBox: '0 0 ' + W + ' ' + (H + 2 * PAD) });
    svg.appendChild(svgNode('line', { x1: AXIS - 6, y1: y(range.top), x2: AXIS - 6,
                                      y2: y(range.bottom), stroke: '#8b94a5' }));
    var ticks = Math.round((range.top - range.bottom) / range.step);
    for (var k = 0; k <= ticks; k++) {
      var z = range.top - k * range.step;
      svg.appendChild(svgNode('line', { x1: AXIS - 10, y1: y(z), x2: AXIS - 6, y2: y(z),
                                        stroke: '#8b94a5' }));
      svg.appendChild(svgNode('text', { x: AXIS - 13, y: y(z) + 3.5, 'text-anchor': 'end',
                                        'font-size': 9.5, fill: '#5b6577',
                                        'font-family': font }, App.UI.fixed(z, decimals)));
    }

    layers.forEach(function (layer, i) {
      if (!(layer.top > layer.bottom)) return;
      var material = App.matById(layer.mat) || {};
      var band = svgNode('rect', {
        x: AXIS, y: y(layer.top), width: COL, height: Math.max(1, y(layer.bottom) - y(layer.top)),
        fill: material.color || '#cccccc', stroke: '#3a4250', 'stroke-width': 0.8,
        'class': 'soil-column-band' + (i === selected ? ' sel' : '')
      });
      band.addEventListener('mousedown', function () { onPick(i); });
      band.appendChild(svgNode('title', {}, layer.name + ' — ' + (material.name || layer.mat) +
                                            '  (' + level(layer.top) + ' … ' +
                                            level(layer.bottom) + ' m)'));
      svg.appendChild(band);
    });

    var ground = y(layers[0].top);
    svg.appendChild(svgNode('line', { x1: AXIS - 4, y1: ground, x2: AXIS + COL + 4, y2: ground,
                                      stroke: '#2a3140', 'stroke-width': 1.4 }));
    if (water && Number.isFinite(water.y)) {
      var wy = y(water.y);
      svg.appendChild(svgNode('line', { 'class': 'soil-column-water', x1: AXIS - 6, y1: wy,
                                        x2: AXIS + COL + 6, y2: wy, stroke: '#2f8fd8',
                                        'stroke-width': 1.4, 'stroke-dasharray': '5 3' }));
      svg.appendChild(svgNode('path', { d: 'M' + (AXIS + COL + 7) + ',' + wy + ' l4,-3 l0,6 z',
                                        fill: '#2f8fd8' }));
      svg.appendChild(svgNode('text', { x: AXIS + COL + 14, y: wy + 3.5, 'font-size': 9.5,
                                        fill: '#2f8fd8', 'font-family': font }, 'water'));
    }
    return svg;
  }

  /* ── The window ────────────────────────────────────────────────────── */

  function open() {
    var el = App.UI.el, fixed = App.UI.fixed;
    var work = copy(App.LAYERS || []);
    var materialsAtOpen = copy(App.MATERIALS || []);
    var projectAtOpen = App.PROJECT;
    var addedMaterial = false, committed = false;
    var selected = 0;
    var rows = [];   // per layer: its row and the cells an edit elsewhere rewrites
    var tableWrap, columnWrap, bodyHost, hint;

    function say(message) {
      hint.textContent = message || HINT;
      hint.classList.toggle('invalid', !!message);
    }

    /* Esc and the close button close without OK too, so the library is put back
       here rather than on Cancel alone. A library the server took on the way (Material
       sets…, or a custom volume saved) stays. */
    function discard() {
      if (!addedMaterial || App.PROJECT !== projectAtOpen) return;
      App.MATERIALS = materialsAtOpen;
      if (App.Model && App.Model.rebuildDerived) App.Model.rebuildDerived();
    }

    function material() {
      if (!App.MATERIALS.length) { App.addMaterial(); addedMaterial = true; }
      var last = work[work.length - 1];
      return last ? last.mat : App.MATERIALS[0].id;
    }

    function groundTop() {
      var domain = App.Model && App.Model.domain ? App.Model.domain() : null;
      return domain && Number.isFinite(domain.y_top) ? domain.y_top : 0;
    }

    function addLayer() { selected = add(work, material(), groundTop()); renderAll(); }
    function insertLayer() {
      if (!work.length) { addLayer(); return; }
      selected = split(work, selected);
      renderAll();
    }
    function deleteLayer() {
      if (!work.length) return;
      remove(work, selected);
      selected = Math.max(0, Math.min(selected, work.length - 1));
      renderAll();
    }

    function pick(i) {
      selected = i;
      rows.forEach(function (row, n) { row.tr.classList.toggle('sel', n === i); });
      renderColumn();
    }

    function writeUnlessFocused(input, text) {
      if (document.activeElement !== input) input.value = text;
    }

    /* After a level edit: the cells of every row, without rebuilding the table, so
       the input being typed into is not torn out. */
    function syncValues() {
      work.forEach(function (layer, i) {
        var row = rows[i];
        if (!row) return;
        writeUnlessFocused(row.top, fixed(layer.top, 3));
        writeUnlessFocused(row.bottom, fixed(layer.bottom, 3));
        writeUnlessFocused(row.thickness, fixed(layer.top - layer.bottom, 3));
        row.swatch.style.background = (App.matById(layer.mat) || {}).color || '';
      });
      renderColumn();
    }

    function commitOnEnter(input) {
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
      });
      return input;
    }

    function numberCell(get, set) {
      var input = commitOnEnter(el('input.cell-input.cell-num', { value: fixed(get(), 3) }));
      input.addEventListener('change', function () {
        var value = Number(input.value.trim().replace(',', '.'));
        var refused = input.value.trim() === '' || !Number.isFinite(value)
          ? '"' + input.value + '" is not a number.' : set(value);
        say(refused);
        input.value = fixed(get(), 3);
        if (!refused) syncValues();
      });
      return input;
    }

    function renderTable() {
      App.UI.clear(tableWrap);
      rows = [];
      var table = el('table.lay-table');
      var headRow = el('tr');
      ['Layer', 'Material', 'Top [m]', 'Bottom [m]', 'Thickness [m]'].forEach(function (h) {
        headRow.appendChild(el('th', { text: h }));
      });
      table.appendChild(el('thead', null, headRow));
      var tbody = el('tbody');

      work.forEach(function (layer, i) {
        var tr = el('tr' + (i === selected ? '.sel' : ''));
        tr.addEventListener('mousedown', function () { if (selected !== i) pick(i); });

        var name = commitOnEnter(el('input.cell-input', { value: layer.name }));
        name.addEventListener('change', function () {
          var value = name.value.trim();
          if (!value) { say('A layer needs a name.'); name.value = layer.name; return; }
          layer.name = value;
          say(null);
          renderColumn();
        });
        tr.appendChild(el('td', null, name));

        var matCell = el('div.cell-mat');
        var swatch = el('span.tree-swatch');
        swatch.style.background = (App.matById(layer.mat) || {}).color || '';
        var select = el('select');
        App.MATERIALS.forEach(function (m) {
          select.appendChild(el('option', { value: m.id, text: m.name }));
        });
        select.value = layer.mat;
        select.addEventListener('change', function () {
          layer.mat = select.value;
          say(null);
          syncValues();
        });
        matCell.appendChild(swatch);
        matCell.appendChild(select);
        tr.appendChild(el('td', null, matCell));

        var top = numberCell(function () { return layer.top; },
                             function (v) { return setTop(work, i, v); });
        var bottom = numberCell(function () { return layer.bottom; },
                                function (v) { return setBottom(work, i, v); });
        var thickness = numberCell(function () { return layer.top - layer.bottom; },
                                   function (v) { return setThickness(work, i, v); });
        tr.appendChild(el('td', null, top));
        tr.appendChild(el('td', null, bottom));
        tr.appendChild(el('td', null, thickness));

        rows.push({ tr: tr, top: top, bottom: bottom, thickness: thickness, swatch: swatch });
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      tableWrap.appendChild(table);
    }

    function renderColumn() {
      App.UI.clear(columnWrap);
      var svg = drawColumn(work, App.PROJECT && App.PROJECT.water, selected, pick);
      columnWrap.appendChild(svg || el('div.soil-column-empty', {
        text: 'No layers yet. Add puts the first one at the top of the domain.' }));
    }

    function renderAll() { say(null); renderTable(); renderColumn(); }

    function build(body) {
      var columnPane = el('div.soil-column-pane');
      columnPane.appendChild(el('div.soil-column-head', { text: 'Layer stack' }));
      columnWrap = el('div.soil-column-wrap');
      columnPane.appendChild(columnWrap);

      var pane = el('div.lay-pane');
      var tools = el('div.lay-toolbar');
      tools.appendChild(el('span', { text: 'Layers' }));
      tools.appendChild(el('span.spacer', { style: 'flex:1' }));
      [['Add', addLayer], ['Insert', insertLayer], ['Delete', deleteLayer]].forEach(function (t) {
        tools.appendChild(el('button.btn.btn-sm', { text: t[0], type: 'button', onclick: t[1] }));
      });
      tools.appendChild(el('button.btn.btn-sm', {
        text: 'Material sets…', type: 'button',
        onclick: function () { App.Dialogs.materials(function () { renderAll(); renderBodies(); }); }
      }));
      tableWrap = el('div.lay-table-wrap');
      bodyHost = el('div');
      hint = el('div.lay-hint');
      pane.appendChild(tools);
      pane.appendChild(tableWrap);
      pane.appendChild(bodyHost);
      pane.appendChild(hint);

      body.appendChild(columnPane);
      body.appendChild(pane);
      renderAll();
      renderBodies();
    }

    var handle = App.Dialogs.open({
      title: 'Modify soil layers', width: 900, height: 560,
      buttons: [{ label: 'OK', primary: true, keepOpen: true, onClick: commit },
                { label: 'Cancel' }],
      onClose: function () { if (!committed) discard(); },
      build: build
    });

    function footButtons(disabled) {
      Array.prototype.forEach.call(handle.dialog.querySelectorAll('.dlg-foot .btn'),
                                   function (b) { b.disabled = disabled; });
    }

    function failed(error) {
      if (App.Command.err) App.Command.err(error.message);
      else App.Command.write('err', error.message);
    }

    function commit() {
      footButtons(true);
      return App.Api.patch('/api/project/layers', {
        layers: copy(work), materials: App.Model.materialsToServer(App.MATERIALS)
      }).then(function (response) {
        App.Model.apply(response.project);
        return App.Viewport.refresh();
      }).then(function () {
        committed = true;
        if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
        App.Command.ok('Soil layers updated — ' + App.LAYERS.length + ' layers.');
        handle.close();
      }).catch(function (error) {
        footButtons(false);
        failed(error);
      });
    }

    /* ── Custom soil volumes ─────────────────────────────────────────────
       Kept out of the layer table on purpose: a layer is a band from one level to
       another across the whole domain, and a polygon prism has no place in that. What
       is editable here is what the two have in common: the name and the material.
       The shape is coordinates, so it is edited as coordinates. */

    /* Add, Insert and Delete go through the server, which answers with the whole
       project, so the stack is saved first or those answers would undo its edits. */
    function saveStack() {
      if (!App.MATERIALS.length) App.addMaterial();
      return App.Api.patch('/api/project/layers', {
        layers: copy(work), materials: App.Model.materialsToServer(App.MATERIALS)
      }).then(function (response) { App.Model.apply(response.project); });
    }

    function renderBodies() {
      App.UI.clear(bodyHost);
      var bodies = ((App.PROJECT && App.PROJECT.custom_parts) || [])
        .filter(function (part) { return !!part.mat; });
      var chosen = bodies.length ? bodies[0].key : null;

      var section = el('div.soil-body-section');
      section.appendChild(el('div.soil-body-section-head', { text: 'Custom soil volumes' }));
      var actions = el('div.lay-toolbar');
      ['Add', 'Insert', 'Delete'].forEach(function (label) {
        var button = el('button.btn.btn-sm', { text: label, type: 'button' });
        button.disabled = label === 'Delete' && !chosen;
        button.addEventListener('click', function () {
          button.disabled = true;
          saveStack().then(function () {
            if (label === 'Delete') {
              return App.LivePatches.deleteRequest(
                '/api/geometry/parts/' + encodeURIComponent(chosen),
                'Could not delete the custom soil volume.')
                .then(function () { return App.Model.load(); })
                .then(function () { return App.Viewport.refresh(); })
                .then(renderBodies);
            }
            App.SoilVolumeDialog.open(null, {
              insertBefore: label === 'Insert' ? chosen : null, onSaved: renderBodies
            });
          }).catch(failed)
            .then(function () { button.disabled = label === 'Delete' && !chosen; });
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

      /* Saved straight away: OK covers the layer stack, which these are not part
         of, so there is nothing for it to save on their behalf. */
      function save() { return App.commitSelectionEdit(App.state.selection); }

      bodies.forEach(function (part) {
        var tr = el('tr');
        tr.classList.toggle('selected', part.key === chosen);
        tr.addEventListener('mousedown', function () {
          chosen = part.key;
          Array.prototype.forEach.call(tbody.children, function (row) {
            row.classList.toggle('selected', row === tr);
          });
        });

        var name = commitOnEnter(el('input.cell-input', { value: part.label }));
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
          handle.close();   // this window is modal
          App.SoilVolumeDialog.open(part);
        });
        tr.appendChild(el('td', null, edit));

        tbody.appendChild(tr);
      });

      section.appendChild(table);
      section.appendChild(el('div.lay-hint', { text:
        'These are solids made from coordinates, not layers, so they have no top or ' +
        'bottom in the stack above. Insert makes a volume before the selected row. ' +
        'Add, Insert and Delete save the layer edits first; a name or a material ' +
        'changed here is saved at once.' }));
      bodyHost.appendChild(section);
    }

    return handle;
  }

  return {
    THICKNESS: THICKNESS,
    add: add, split: split, remove: remove,
    setTop: setTop, setBottom: setBottom, setThickness: setThickness,
    removeById: removeById, levelEditor: levelEditor,
    columnRange: columnRange, drawColumn: drawColumn,
    open: open
  };
})();
