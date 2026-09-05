/* ══════════════════════════════════════════════════════════════════
   dialogs.js — modal shell plus the dialogs the mockup ships with.
   The "Modify soil layers" window is the showcase piece: its table
   and borehole graphic are genuinely wired to each other.
   ══════════════════════════════════════════════════════════════════ */

App.Dialogs = (function () {
  var el = App.UI.el, icon = App.UI.icon, fixed = App.UI.fixed;

  /* ══════════════════════════════════════════════════════════════
     Generic modal shell — draggable, resizable, Esc to close
     ══════════════════════════════════════════════════════════════ */
  function open(opts) {
    var layer = document.getElementById('modal-layer');
    var scrim = el('div.scrim');
    var dlg = el('div.dialog');

    var w = opts.width || 560, h = opts.height || 380;
    w = Math.min(w, window.innerWidth - 40);
    h = Math.min(h, window.innerHeight - 60);
    dlg.style.width = w + 'px';
    dlg.style.height = h + 'px';
    dlg.style.left = Math.round((window.innerWidth - w) / 2) + 'px';
    dlg.style.top = Math.round((window.innerHeight - h) / 2 - 12) + 'px';

    var head = el('div.dlg-head', null, [
      el('span.dlg-title', { text: opts.title }),
      el('button.dlg-x', { text: '✕', type: 'button', onclick: close })
    ]);
    dlg.appendChild(head);

    if (opts.toolbar) dlg.appendChild(opts.toolbar);

    var body = el('div.dlg-body');
    dlg.appendChild(body);

    var foot = el('div.dlg-foot');
    foot.appendChild(el('span.spacer'));
    (opts.buttons || [{ label: 'OK', primary: true }, { label: 'Cancel' }]).forEach(function (b) {
      foot.appendChild(el('button.btn' + (b.primary ? '.btn-primary' : ''), {
        text: b.label, type: 'button',
        onclick: function () { if (b.onClick) b.onClick(); if (b.keepOpen !== true) close(); }
      }));
    });
    dlg.appendChild(foot);

    var grip = el('div.dlg-resize');
    dlg.appendChild(grip);

    layer.appendChild(scrim);
    layer.appendChild(dlg);
    drag(head, dlg);
    resize(grip, dlg);

    function onKey(e) { if (e.key === 'Escape') close(); }
    document.addEventListener('keydown', onKey);

    function close() {
      document.removeEventListener('keydown', onKey);
      if (scrim.parentNode) scrim.parentNode.removeChild(scrim);
      if (dlg.parentNode) dlg.parentNode.removeChild(dlg);
      if (opts.onClose) opts.onClose();
    }

    scrim.addEventListener('mousedown', function () { flash(dlg); });

    if (opts.build) opts.build(body, { close: close, dialog: dlg });
    return { close: close, body: body, dialog: dlg };
  }

  function flash(dlg) {
    dlg.animate([{ transform: 'translateX(0)' }, { transform: 'translateX(-4px)' },
                 { transform: 'translateX(4px)' }, { transform: 'translateX(0)' }],
                { duration: 160 });
  }

  function drag(handle, dlg) {
    handle.addEventListener('mousedown', function (e) {
      if (e.target.closest('.dlg-x')) return;
      var sx = e.clientX, sy = e.clientY;
      var x0 = parseFloat(dlg.style.left), y0 = parseFloat(dlg.style.top);
      function mv(ev) {
        dlg.style.left = Math.max(-40, Math.min(window.innerWidth - 80, x0 + ev.clientX - sx)) + 'px';
        dlg.style.top = Math.max(0, Math.min(window.innerHeight - 40, y0 + ev.clientY - sy)) + 'px';
      }
      function up() { window.removeEventListener('mousemove', mv); window.removeEventListener('mouseup', up); }
      window.addEventListener('mousemove', mv); window.addEventListener('mouseup', up);
      e.preventDefault();
    });
  }

  function resize(grip, dlg) {
    grip.addEventListener('mousedown', function (e) {
      var sx = e.clientX, sy = e.clientY;
      var w0 = dlg.offsetWidth, h0 = dlg.offsetHeight;
      function mv(ev) {
        dlg.style.width = Math.max(420, w0 + ev.clientX - sx) + 'px';
        dlg.style.height = Math.max(240, h0 + ev.clientY - sy) + 'px';
      }
      function up() { window.removeEventListener('mousemove', mv); window.removeEventListener('mouseup', up); }
      window.addEventListener('mousemove', mv); window.addEventListener('mouseup', up);
      e.preventDefault();
    });
  }

  /* ══════════════════════════════════════════════════════════════
     Modify soil layers
     ══════════════════════════════════════════════════════════════ */
  function soilLayers() {
    var state = { bh: App.BOREHOLES[0].id, layer: 0 };
    var refreshAll;

    // Snapshot so Cancel can discard every edit made while the dialog was open.
    var layersSnapshot = JSON.parse(JSON.stringify(App.LAYERS));
    var boreholesSnapshot = JSON.parse(JSON.stringify(App.BOREHOLES));
    var materialsSnapshot = JSON.parse(JSON.stringify(App.MATERIALS));
    function restoreSnapshot() {
      App.LAYERS.length = 0;
      Array.prototype.push.apply(App.LAYERS, layersSnapshot);
      App.BOREHOLES.length = 0;
      Array.prototype.push.apply(App.BOREHOLES, boreholesSnapshot);
      App.MATERIALS = materialsSnapshot;
    }

    var toolbar = el('div.dlg-toolbar');

    open({
      title: 'Modify soil layers',
      width: 900, height: 560,
      toolbar: toolbar,
      buttons: [
        { label: 'OK', primary: true, onClick: function () {
            App.Command.ok('Soil layers updated — ' + App.LAYERS.length + ' layers, ' +
                           App.BOREHOLES.length + ' boreholes.');
            App.refreshSoilData();
            App.Viewport.rebuildSoil();
            App.Explorer.mountTree(App.state.mode);
          } },
        { label: 'Cancel', onClick: restoreSnapshot }
      ],
      build: function (body) {
        /* ── Left: borehole columns ───────────────────────────── */
        var bhPane = el('div.bh-pane');
        var bhHead = el('div.bh-pane-head', null, ['Boreholes']);
        var canvasWrap = el('div.bh-canvas-wrap');
        var bhProps = el('div.bh-props');
        bhPane.appendChild(bhHead);
        bhPane.appendChild(canvasWrap);
        bhPane.appendChild(bhProps);

        /* ── Right: layer table ───────────────────────────────── */
        var layPane = el('div.lay-pane');
        var layTB = el('div.lay-toolbar');
        var tableWrap = el('div.lay-table-wrap');
        var hint = el('div.lay-hint');
        var DEFAULT_HINT = 'Edit any level, thickness, material or borehole field — the columns ' +
                           'update immediately. Changing a bottom (or a thickness) moves the top ' +
                           'of the layer below it, keeping the stack gap-free.';
        function say(message) {
          hint.textContent = message || DEFAULT_HINT;
          hint.classList.toggle('invalid', !!message);
        }
        say(null);
        layPane.appendChild(layTB);
        layPane.appendChild(tableWrap);
        layPane.appendChild(hint);

        body.appendChild(bhPane);
        body.appendChild(layPane);

        /* ── Dialog toolbar ───────────────────────────────────── */
        [['borehole', 'Add borehole'], ['delete', 'Delete borehole'], null,
         ['soillayers', 'Add layer'], ['materials', 'Material sets…'], null,
         ['waterlevel', 'Water levels'], ['flowfn', 'Field data']].forEach(function (t) {
          if (!t) { toolbar.appendChild(el('span.tbsep')); return; }
          var b = el('button.tbtn', { type: 'button' });
          b.appendChild(icon(t[0]));
          App.UI.attachTip(b, t[1]);
          b.addEventListener('click', function () {
            if (t[1] === 'Add borehole') addBorehole();
            else if (t[1] === 'Delete borehole') deleteBorehole();
            else if (t[1] === 'Add layer') addLayer();
            else if (t[1] === 'Material sets…') materials(function () { refreshAll(); });
            else App.Command.note(t[1] + ' — not implemented in this mockup.');
          });
          toolbar.appendChild(b);
        });

        /* ── Layer table toolbar ──────────────────────────────── */
        var sel = el('select');
        sel.addEventListener('change', function () { state.bh = sel.value; refreshAll(); });

        function renderBhSelect() {
          App.UI.clear(sel);
          App.BOREHOLES.forEach(function (b) {
            sel.appendChild(el('option', { value: b.id, text: b.name +
              '   (x = ' + fixed(b.x, 1) + ', y = ' + fixed(b.y, 1) + ')' }));
          });
          sel.value = state.bh;
        }

        layTB.appendChild(el('span', { text: 'Layers of' }));
        layTB.appendChild(sel);
        layTB.appendChild(el('span.spacer', { style: 'flex:1' }));
        layTB.appendChild(el('button.btn.btn-sm', { text: 'Add',    type: 'button', onclick: addLayer }));
        layTB.appendChild(el('button.btn.btn-sm', { text: 'Insert', type: 'button', onclick: insertLayer }));
        layTB.appendChild(el('button.btn.btn-sm', { text: 'Delete', type: 'button', onclick: deleteLayer }));

        /* ── Renderers ────────────────────────────────────────── */
        /* Live cell references, so an edit can update the other columns without
           rebuilding the table. Rebuilding mid-interaction is what made the
           levels and the material picker unusable by hand: the row's mousedown,
           and the `change` fired when a dirty field loses focus, both used to
           re-render — destroying the very element the click was travelling to. */
        var rowRefs = [];

        function writeUnlessFocused(input, text) {
          if (document.activeElement !== input) input.value = text;
        }

        /* Push the current App.LAYERS values back into the existing cells. */
        function syncValues() {
          App.LAYERS.forEach(function (L, i) {
            var ref = rowRefs[i];
            if (!ref) return;
            var top = L.tops[state.bh], bot = L.bots[state.bh];
            writeUnlessFocused(ref.name, L.name);
            writeUnlessFocused(ref.top, fixed(top, 3));
            writeUnlessFocused(ref.bot, fixed(bot, 3));
            writeUnlessFocused(ref.thick, fixed(top - bot, 3));
            if (ref.mat.value !== L.mat) ref.mat.value = L.mat;
            ref.swatch.style.background = matOf(L).color;
          });
          renderColumns();
        }

        /* A numeric cell that reads its value through `get`, so it never shows a
           figure captured at render time. `accept` mirrors a server constraint. */
        function levelInput(get, set, accept, invalidMessage) {
          var inp = commitOnEnter(el('input.cell-input.cell-num', { value: fixed(get(), 3) }));
          inp.addEventListener('change', function () {
            var n = parseFloat(inp.value.trim().replace(',', '.'));
            if (isNaN(n)) {
              say('"' + inp.value + '" is not a number.');
              inp.value = fixed(get(), 3);
              return;
            }
            if (accept && !accept(n)) { say(invalidMessage); inp.value = fixed(get(), 3); return; }
            say(null);
            set(n);
            inp.value = fixed(get(), 3);
          });
          return inp;
        }

        function renderTable() {
          App.UI.clear(tableWrap);
          rowRefs = [];
          var t = el('table.lay-table');
          var thead = el('thead');
          var hr = el('tr');
          ['Layer', 'Top [m]', 'Bottom [m]', 'Thickness [m]', 'Material'].forEach(function (h) {
            hr.appendChild(el('th', { text: h }));
          });
          thead.appendChild(hr);
          t.appendChild(thead);

          var tb = el('tbody');
          var rows = [];

          /* Move the highlight only — see the note on rowRefs above. */
          function selectRow(i) {
            if (state.layer === i) return;
            state.layer = i;
            rows.forEach(function (r, ri) { r.classList.toggle('sel', ri === i); });
            renderColumns();
          }

          App.LAYERS.forEach(function (L, i) {
            var tr = el('tr' + (i === state.layer ? '.sel' : ''));
            rows.push(tr);
            tr.addEventListener('mousedown', function () { selectRow(i); });

            var nameInp = commitOnEnter(el('input.cell-input', { value: L.name }));
            nameInp.addEventListener('change', function () {
              var v = nameInp.value.trim();
              if (!v) { say('Layer name cannot be empty.'); nameInp.value = L.name; return; }
              L.name = v;
              say(null);
              syncValues();
            });
            tr.appendChild(el('td', null, nameInp));

            var topInp = levelInput(function () { return L.tops[state.bh]; },
                                    function (v) { setTop(i, v); });
            var botInp = levelInput(function () { return L.bots[state.bh]; },
                                    function (v) { setBottom(i, v); });
            var thickInp = levelInput(function () { return L.tops[state.bh] - L.bots[state.bh]; },
                                      function (v) { setThickness(i, v); },
                                      function (v) { return v >= 0; },
                                      'Thickness must be 0 or greater.');
            tr.appendChild(el('td', null, topInp));
            tr.appendChild(el('td', null, botInp));
            tr.appendChild(el('td', null, thickInp));

            var matCell = el('div.cell-mat');
            var sw = el('span.tree-swatch');
            sw.style.background = matOf(L).color;
            var ms = el('select');
            App.MATERIALS.forEach(function (m) {
              ms.appendChild(el('option', { value: m.id, text: m.name }));
            });
            ms.value = L.mat;
            ms.addEventListener('change', function () {
              L.mat = ms.value;
              say(null);
              syncValues();
            });
            matCell.appendChild(sw);
            matCell.appendChild(ms);
            tr.appendChild(el('td', null, matCell));

            rowRefs.push({ name: nameInp, top: topInp, bot: botInp,
                           thick: thickInp, mat: ms, swatch: sw });
            tb.appendChild(tr);
          });
          t.appendChild(tb);
          tableWrap.appendChild(t);
        }

        function renderColumns() {
          App.UI.clear(canvasWrap);

          var zTop = 4, zBot = -28, H = 420, PAD_T = 16, AXIS_W = 44;
          var colW = 56, gap = 16;
          var W = AXIS_W + App.BOREHOLES.length * (colW + gap);
          var scale = H / (zTop - zBot);
          var y = function (z) { return PAD_T + (zTop - z) * scale; };

          var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
          svg.setAttribute('class', 'bh-svg');
          svg.setAttribute('width', W);
          svg.setAttribute('height', H + PAD_T + 26);
          svg.setAttribute('viewBox', '0 0 ' + W + ' ' + (H + PAD_T + 26));

          function n(tag, attrs, text) {
            var e = document.createElementNS('http://www.w3.org/2000/svg', tag);
            Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); });
            if (text !== undefined) e.textContent = text;
            return e;
          }

          // Depth axis
          svg.appendChild(n('line', { x1: AXIS_W - 6, y1: y(zTop), x2: AXIS_W - 6, y2: y(zBot),
                                      stroke: '#8b94a5', 'stroke-width': 1 }));
          for (var z = 0; z >= -25; z -= 5) {
            svg.appendChild(n('line', { x1: AXIS_W - 10, y1: y(z), x2: AXIS_W - 6, y2: y(z),
                                        stroke: '#8b94a5', 'stroke-width': 1 }));
            svg.appendChild(n('text', { x: AXIS_W - 13, y: y(z) + 3.5, 'text-anchor': 'end',
                                        'font-size': 9.5, fill: '#5b6577',
                                        'font-family': 'Segoe UI, Arial' }, fixed(z, 1)));
          }

          App.BOREHOLES.forEach(function (b, bi) {
            var x = AXIS_W + bi * (colW + gap);
            var isSel = b.id === state.bh;

            svg.appendChild(n('text', { x: x + colW / 2, y: 11, 'text-anchor': 'middle',
                                        'font-size': 10.5, 'font-weight': isSel ? 700 : 500,
                                        fill: isSel ? '#080c80' : '#5b6577',
                                        'font-family': 'Segoe UI, Arial' }, b.name));

            App.LAYERS.forEach(function (L, li) {
              var t = L.tops[b.id], bt = L.bots[b.id];
              if (t <= bt) return;
              var r = n('rect', {
                x: x, y: y(t), width: colW, height: Math.max(1, y(bt) - y(t)),
                fill: matOf(L).color, stroke: '#3a4250', 'stroke-width': 0.8,
                class: 'bh-layer-rect' + (isSel && li === state.layer ? ' sel' : '')
              });
              r.addEventListener('mousedown', function () {
                state.bh = b.id; state.layer = li; sel.value = b.id; refreshAll();
              });
              r.appendChild(n('title', {}, L.name + ' — ' + matOf(L).name +
                                          '  (' + fixed(t, 2) + ' … ' + fixed(bt, 2) + ' m)'));
              svg.appendChild(r);
            });

            // Ground surface and phreatic level
            svg.appendChild(n('line', { x1: x - 4, y1: y(b.head), x2: x + colW + 4, y2: y(b.head),
                                        stroke: '#2a3140', 'stroke-width': 1.4 }));
            svg.appendChild(n('line', { x1: x - 6, y1: y(b.water), x2: x + colW + 6, y2: y(b.water),
                                        stroke: '#2f8fd8', 'stroke-width': 1.4,
                                        'stroke-dasharray': '5 3' }));
            svg.appendChild(n('path', {
              d: 'M' + (x + colW + 7) + ',' + y(b.water) + ' l4,-3 l0,6 z',
              fill: '#2f8fd8'
            }));

            svg.appendChild(n('text', { x: x + colW / 2, y: H + PAD_T + 14, 'text-anchor': 'middle',
                                        'font-size': 9, fill: '#8b94a5',
                                        'font-family': 'Segoe UI, Arial' },
                              '(' + fixed(b.x, 0) + ', ' + fixed(b.y, 0) + ')'));
          });

          canvasWrap.appendChild(svg);
        }

        /* ── Borehole properties (of the selected borehole) ───── */
        function renderBhProps() {
          App.UI.clear(bhProps);
          var b = App.BOREHOLES.filter(function (x) { return x.id === state.bh; })[0];
          if (!b) return;

          // Redraw the graphic and the picker, but never this grid: re-rendering it
          // mid-edit would tear out the input being typed into. The header instead
          // follows a rename in place.
          var F = fieldBuilders(say, function () { renderBhSelect(); renderColumns(); });
          var headNode = el('div.bh-props-head', { text: b.name });
          var grid = el('div.pgrid');
          [
            F.textRow('Name', function () { return b.name; }, function (v) {
              if (!v) return 'Borehole name cannot be empty.';
              b.name = v;
              headNode.textContent = v;
              return null;
            }),
            F.numRow('x', 'm', { decimals: 2 }, function () { return b.x; }, function (v) { b.x = v; }),
            F.numRow('y', 'm', { decimals: 2 }, function () { return b.y; }, function (v) { b.y = v; }),
            F.numRow('Ground level', 'm', { decimals: 2 },
                     function () { return b.head; }, function (v) { b.head = v; }),
            F.numRow('Water level', 'm', { decimals: 2 },
                     function () { return b.water; }, function (v) { b.water = v; })
          ].forEach(function (r) { grid.appendChild(r); });

          bhProps.appendChild(headNode);
          bhProps.appendChild(grid);
        }

        /* ── Edits ────────────────────────────────────────────── */
        /* The stack must stay gap-free and never invert: the server rejects
           bottom-above-top per layer, and a non-contiguous stack outright
           (server/app/schemas.py:110-135). Each setter cascades to its
           neighbour and refuses an edit that would cross it. */
        function setTop(i, v) {
          var L = App.LAYERS[i];
          if (v < L.bots[state.bh]) { say('Top must be at or above this layer\'s bottom.'); return; }
          if (i > 0 && v > App.LAYERS[i - 1].tops[state.bh]) {
            say('Top cannot rise above the top of the layer above.'); return;
          }
          L.tops[state.bh] = v;
          if (i > 0) App.LAYERS[i - 1].bots[state.bh] = v;
          syncValues();
        }
        function setBottom(i, v) {
          var L = App.LAYERS[i];
          if (v > L.tops[state.bh]) { say('Bottom must be at or below this layer\'s top.'); return; }
          if (i < App.LAYERS.length - 1 && v < App.LAYERS[i + 1].bots[state.bh]) {
            say('Bottom cannot drop below the bottom of the layer below.'); return;
          }
          L.bots[state.bh] = v;
          if (i < App.LAYERS.length - 1) App.LAYERS[i + 1].tops[state.bh] = v;
          syncValues();
        }
        /* Thickness is the derived column: keep the top and move the bottom. */
        function setThickness(i, v) {
          setBottom(i, App.LAYERS[i].tops[state.bh] - v);
        }
        function addLayer() {
          var last = App.LAYERS[App.LAYERS.length - 1];
          if (!App.MATERIALS.length) App.addMaterial();
          var nu = newLayer(last ? last.mat : App.MATERIALS[0].id);
          App.BOREHOLES.forEach(function (b) {
            nu.tops[b.id] = last ? last.bots[b.id] : b.head;
            nu.bots[b.id] = nu.tops[b.id] - 5;
          });
          App.LAYERS.push(nu);
          state.layer = App.LAYERS.length - 1;
          refreshAll();
        }
        function newLayer(material) {
          var number = 1;
          while (App.LAYERS.some(function (layer) { return layer.id === 'L' + number; })) number++;
          return { id: 'L' + number, name: 'Soil_' + number, mat: material, tops: {}, bots: {} };
        }
        function insertLayer() {
          if (!App.LAYERS.length) { addLayer(); return; }
          var i = state.layer, L = App.LAYERS[i];
          var nu = newLayer(L.mat);
          App.BOREHOLES.forEach(function (b) {
            var mid = (L.tops[b.id] + L.bots[b.id]) / 2;
            nu.tops[b.id] = mid;
            nu.bots[b.id] = L.bots[b.id];
            L.bots[b.id] = mid;
          });
          App.LAYERS.splice(i + 1, 0, nu);
          refreshAll();
        }
        function deleteLayer() {
          if (!App.LAYERS.length) return;
          var i = state.layer, L = App.LAYERS[i];
          App.BOREHOLES.forEach(function (b) {
            if (i > 0) App.LAYERS[i - 1].bots[b.id] = L.bots[b.id];
            else if (App.LAYERS[1]) App.LAYERS[1].tops[b.id] = L.tops[b.id];
          });
          App.LAYERS.splice(i, 1);
          state.layer = Math.max(0, Math.min(i, App.LAYERS.length - 1));
          refreshAll();
        }

        function addBorehole() {
          var nb = App.addBorehole();
          state.bh = nb.id;
          refreshAll();
        }
        function deleteBorehole() {
          if (App.BOREHOLES.length <= 1) return;
          var idx = App.BOREHOLES.findIndex(function (b) { return b.id === state.bh; });
          if (idx < 0) idx = App.BOREHOLES.length - 1;
          var removed = App.BOREHOLES[idx];
          App.BOREHOLES.splice(idx, 1);
          App.LAYERS.forEach(function (L) {
            delete L.tops[removed.id];
            delete L.bots[removed.id];
          });
          state.bh = App.BOREHOLES[Math.min(idx, App.BOREHOLES.length - 1)].id;
          refreshAll();
        }

        refreshAll = function () { renderBhSelect(); renderTable(); renderColumns(); renderBhProps(); };
        refreshAll();
      }
    });
  }

  function matOf(layer) {
    return App.matById(layer.mat);
  }

  /* ══════════════════════════════════════════════════════════════
     Material sets
     ══════════════════════════════════════════════════════════════ */
  /* Applies material edits to everything downstream: tree labels and swatches,
     the per-layer property sets, and the 3D soil colours. The live app replaces
     this step in live/js/patches.js, where the edits go to the server first. */
  function commitMaterials() {
    App.refreshSoilData();
    App.Viewport.rebuildSoil();
    App.Explorer.mountTree(App.state.mode);
    App.Command.ok('Material sets updated — ' + App.MATERIALS.length + ' soil materials.');
  }

  /* `onClose` lets the caller re-read App.MATERIALS afterwards — the soil layers
     dialog uses it so a material added in here appears in its Material column. */
  function materials(onClose) {
    // Property edits mutate App.MATERIALS live so the table and swatches react as
    // you type; Cancel puts the whole list back the way it was found.
    var snapshot = JSON.parse(JSON.stringify(App.MATERIALS));
    function restoreSnapshot() {
      App.MATERIALS.length = 0;
      Array.prototype.push.apply(App.MATERIALS, snapshot);
    }

    var selected = App.MATERIALS.length ? App.MATERIALS[0].id : null;
    var toolbar = el('div.dlg-toolbar');
    var hint;

    function say(message, invalid) {
      if (!hint) return;
      hint.textContent = message ||
        'Select a material set, then use the toolbar to add, duplicate or delete it. ' +
        'Properties… opens its General / Parameters / Groundwater / Interfaces tabs.';
      hint.classList.toggle('invalid', !!invalid);
    }

    open({
      title: 'Material sets',
      width: 760, height: 460,
      toolbar: toolbar,
      onClose: onClose,
      buttons: [
        { label: 'OK', primary: true, onClick: commitMaterials },
        { label: 'Cancel', onClick: restoreSnapshot }
      ],
      build: function (body) {
        var wrap = el('div.dlg-simple');
        wrap.appendChild(el('h3', { text: 'Soil and interfaces' }));

        var t = el('table.mat-table.selectable');
        var hr = el('tr');
        ['', 'Identification', 'Material model', 'Drainage type',
         'γunsat [kN/m³]', 'γsat [kN/m³]', "E' [kN/m²]", "φ' [°]", ''].forEach(function (h) {
          hr.appendChild(el('th', { text: h }));
        });
        t.appendChild(el('thead', null, hr));

        var tb = el('tbody');
        t.appendChild(tb);

        function selectedMaterial() {
          return App.MATERIALS.filter(function (m) { return m.id === selected; })[0] || null;
        }

        function renderSoilTable() {
          App.UI.clear(tb);
          if (applyInterfaceButton) applyInterfaceButton.disabled = !selectedMaterial();
          App.MATERIALS.forEach(function (m) {
            var sw = el('span.tree-swatch');
            sw.style.background = m.color;
            var tr = el('tr' + (m.id === selected ? '.sel' : ''), null, [
              el('td', null, sw),
              el('td', { text: m.name }),
              el('td', { text: m.model }),
              el('td', { text: m.type }),
              el('td.num', { text: fixed(m.gUnsat, 1) }),
              el('td.num', { text: fixed(m.gSat, 1) }),
              el('td.num', { text: m.E >= 1e6 ? m.E.toExponential(2) : fixed(m.E, 0) }),
              el('td.num', { text: m.phi === null ? '—' : fixed(m.phi, 1) }),
              el('td', null, el('button.btn.btn-sm', { text: 'Properties…', type: 'button',
                onclick: function (e) {
                  e.stopPropagation();
                  selected = m.id;
                  materialEditor(m, renderSoilTable);
                  renderSoilTable();
                } }))
            ]);
            tr.addEventListener('click', function () {
              selected = m.id;
              say(null);
              renderSoilTable();
            });
            tb.appendChild(tr);
          });
        }

        /* ── Dialog toolbar ───────────────────────────────────── */
        [['new', 'New material set'], ['copy', 'Duplicate material set'],
         ['delete', 'Delete material set'], null,
         ['materials', 'Properties…']].forEach(function (spec) {
          if (!spec) { toolbar.appendChild(el('span.tbsep')); return; }
          var b = el('button.tbtn', { type: 'button' });
          b.appendChild(icon(spec[0]));
          App.UI.attachTip(b, spec[1]);
          b.addEventListener('click', function () {
            App.UI.hideTip();
            var m = selectedMaterial();

            if (spec[1] === 'New material set') {
              selected = App.addMaterial().id;
              say('Added ' + selectedMaterial().name + '. Open Properties… to set its values.');
              renderSoilTable();
              return;
            }
            if (!m) { say('Select a material set first.', true); return; }

            if (spec[1] === 'Duplicate material set') {
              selected = App.duplicateMaterial(m).id;
              say('Duplicated ' + m.name + '.');
              renderSoilTable();
            } else if (spec[1] === 'Delete material set') {
              // The server's Project validator rejects a layer pointing at a
              // missing material, so refuse rather than save something invalid.
              var used = App.layersUsingMaterial(m.id);
              if (used.length) {
                say('"' + m.name + '" is assigned to ' + used.join(', ') +
                    '. Reassign those layers first.', true);
                return;
              }
              var i = App.MATERIALS.indexOf(m);
              App.MATERIALS.splice(i, 1);
              selected = App.MATERIALS.length
                ? App.MATERIALS[Math.min(i, App.MATERIALS.length - 1)].id : null;
              say('Deleted ' + m.name + '.');
              renderSoilTable();
            } else if (spec[1] === 'Properties…') {
              materialEditor(m, renderSoilTable);
            }
          });
          toolbar.appendChild(b);
        });

        var library = el('div.material-library');
        library.appendChild(el('h3', { text: 'Default library' }));
        library.appendChild(el('p', { text: 'Copy a soil preset into this project, or apply interface defaults to the selected material. These are starting values; review them for your project.' }));
        var soilSelect = el('select', { 'aria-label': 'Soil preset' });
        App.MaterialLibrary.soils().forEach(function (m) {
          soilSelect.appendChild(el('option', { value: m.id, text: m.name + ' — ' + m.model }));
        });
        var soilRow = el('div.lay-toolbar', null, [el('span', { text: 'Soil' }), soilSelect,
          el('button.btn.btn-sm', { text: 'Add to project', type: 'button', 'data-action': 'add-soil-preset',
            onclick: function () {
              var m = App.MaterialLibrary.addSoil(soilSelect.value);
              selected = m.id;
              renderSoilTable();
              say('Added ' + m.name + ' from the default library. Open Properties… to review or edit its values.');
            } })]);
        var interfaceSelect = el('select', { 'aria-label': 'Interface preset' });
        App.MaterialLibrary.interfaces().forEach(function (p) {
          interfaceSelect.appendChild(el('option', { value: p.id,
            text: p.name + ' — Rinter ' + p.rInter + ', ' + p.interfacePerm }));
        });
        var applyInterfaceButton = el('button.btn.btn-sm', { text: 'Apply to selected', type: 'button',
          'data-action': 'apply-interface-preset', onclick: function () {
            var m = selectedMaterial();
            if (!m) return;
            App.MaterialLibrary.applyInterface(m, interfaceSelect.value);
            say('Applied interface defaults to ' + m.name + ': Rinter ' + m.rInter + ', ' + m.interfacePerm + '.');
          } });
        library.appendChild(soilRow);
        library.appendChild(el('div.lay-toolbar', null, [el('span', { text: 'Interface' }),
          interfaceSelect, applyInterfaceButton]));
        wrap.insertBefore(library, wrap.firstChild);

        renderSoilTable();
        wrap.appendChild(t);

        hint = el('div.lay-hint', { style: 'border-top:0;background:none;padding:6px 0' });
        say(null);
        wrap.appendChild(hint);

        wrap.appendChild(el('h3', { text: 'Structural materials', style: 'margin-top:14px' }));
        var t2 = el('table.mat-table');
        var hr2 = el('tr');
        ['Identification', 'Type', 'Properties'].forEach(function (h) { hr2.appendChild(el('th', { text: h })); });
        t2.appendChild(el('thead', null, hr2));
        var tb2 = el('tbody');
        App.STRUCT_MATERIALS.forEach(function (s) {
          tb2.appendChild(el('tr', null, [
            el('td', { text: s.name }), el('td', { text: s.kind }), el('td', { text: s.detail })
          ]));
        });
        t2.appendChild(tb2);
        wrap.appendChild(t2);

        body.appendChild(wrap);
      }
    });
  }

  /* `change` fires on blur, not on Enter, so a value typed and confirmed with
     Enter would sit uncommitted until the field happened to lose focus. Blurring
     on Enter runs the field's own change handler, validation and all. */
  function commitOnEnter(input) {
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
    });
    return input;
  }

  /* ══════════════════════════════════════════════════════════════
     Shared property-grid field builders

     Used by the material editor and the borehole editor. `say(msg)` reports a
     rejected edit, `changed()` runs after an accepted one. Bounds mirror the
     server's Field(...) constraints so a value accepted here cannot come back
     from a save as a 422.
     ══════════════════════════════════════════════════════════════ */
  function fieldBuilders(say, changed) {
    function row(label, valueNode, unit) {
      var v = el('div.pgrid-val.editable.field', null, [valueNode]);
      if (unit) v.appendChild(el('span.unit', { text: unit }));
      return el('div.pgrid-row', null, [el('div.pgrid-key', { text: label }), v]);
    }

    /* Text field. `apply` returns an error string to reject the edit. */
    function textRow(label, get, apply) {
      var inp = commitOnEnter(el('input.cell-input', { value: get() }));
      inp.addEventListener('change', function () {
        var err = apply(inp.value.trim());
        if (err) { inp.value = get(); say(err); return; }
        inp.value = get();
        say(null);
        changed();
      });
      return row(label, inp);
    }

    /* Numeric field. `bounds` = { min, max, exclusiveMin, exclusiveMax,
       nullable, decimals }; decimals null shows the raw value. */
    function numRow(label, unit, bounds, get, set) {
      function show() {
        var v = get();
        if (v === null || v === undefined) return '';
        return bounds.decimals === null ? String(v) : fixed(v, bounds.decimals);
      }
      var inp = commitOnEnter(el('input.cell-input.cell-num', { value: show() }));
      if (bounds.nullable) inp.placeholder = '—';

      inp.addEventListener('change', function () {
        var raw = inp.value.trim().replace(',', '.');

        if (raw === '' || raw === '—') {
          if (!bounds.nullable) { inp.value = show(); say(label + ' is required.'); return; }
          set(null); inp.value = ''; say(null); changed(); return;
        }

        var n = parseFloat(raw);
        if (isNaN(n)) { inp.value = show(); say(label + ': "' + inp.value + '" is not a number.'); return; }

        var err = null;
        if (bounds.exclusiveMin !== undefined && n <= bounds.exclusiveMin) {
          err = label + ' must be greater than ' + bounds.exclusiveMin + '.';
        } else if (bounds.min !== undefined && n < bounds.min) {
          err = label + ' must be at least ' + bounds.min + '.';
        } else if (bounds.exclusiveMax !== undefined && n >= bounds.exclusiveMax) {
          err = label + ' must be less than ' + bounds.exclusiveMax + '.';
        } else if (bounds.max !== undefined && n > bounds.max) {
          err = label + ' must be at most ' + bounds.max + '.';
        }
        if (err) { inp.value = show(); say(err); return; }

        set(n);
        inp.value = show();
        say(null);
        changed();
      });
      return row(label, inp, unit);
    }

    /* Dropdown over a fixed value set. */
    function selectRow(label, options, get, set) {
      var sel = el('select');
      options.forEach(function (o) {
        sel.appendChild(el('option', { value: o.value || o, text: o.text || o }));
      });
      sel.value = get();
      sel.addEventListener('change', function () {
        set(sel.value);
        say(null);
        changed();
      });
      return row(label, el('div.cell-mat', null, sel));
    }

    /* Colour. <input type="color"> can only ever yield #rrggbb, which is exactly
       what the server's Hex pattern wants, so this field cannot be invalid. */
    function colorRow(label, get, set) {
      var pick = el('input', { type: 'color', value: get(),
                               style: 'width:34px;height:17px;border:0;background:none;padding:0' });
      var text = el('span', { text: get(), style: 'font-family:var(--font-mono)' });
      pick.addEventListener('input', function () {
        set(pick.value);
        text.textContent = get();
        say(null);
        changed();
      });
      return row(label, el('div.cell-mat', null, [pick, text]));
    }

    return { row: row, textRow: textRow, numRow: numRow,
             selectRow: selectRow, colorRow: colorRow };
  }

  /* Per-material property editor: General / Parameters / Groundwater /
     Interfaces tabs over one App.MATERIALS entry. Every field is editable and
     validated against the same bounds the server's Material schema enforces
     (server/app/schemas.py:82-100). Edits are written straight to the material
     object; the Material sets dialog's Cancel restores its snapshot. */
  function materialEditor(m, onChange) {
    var hint, titleNode;
    var DEFAULT_HINT = 'Values are validated as you type. An out-of-range entry is rejected ' +
                       'and the previous value restored.';

    function say(message) {
      if (!hint) return;
      hint.textContent = message || DEFAULT_HINT;
      hint.classList.toggle('invalid', !!message);
    }

    var F = fieldBuilders(say, function () { if (onChange) onChange(); });
    var textRow = F.textRow, numRow = F.numRow, selectRow = F.selectRow, colorRow = F.colorRow;

    var TABS = {
      'General': function () {
        return [
          textRow('Identification', function () { return m.name; }, function (v) {
            if (!v) return 'Identification cannot be empty.';
            m.name = v;
            if (titleNode) titleNode.textContent = 'Material set — ' + m.name;
            return null;
          }),
          colorRow('Colour', function () { return m.color; },
                   function (v) { m.color = v; }),
          selectRow('Material model', App.MATERIAL_MODELS,
                    function () { return m.model; }, function (v) { m.model = v; }),
          selectRow('Drainage type', App.MATERIAL_TYPES,
                    function () { return m.type; }, function (v) { m.type = v; }),
          numRow('γunsat', 'kN/m³', { exclusiveMin: 0, decimals: 1 },
                 function () { return m.gUnsat; }, function (v) { m.gUnsat = v; }),
          numRow('γsat', 'kN/m³', { exclusiveMin: 0, decimals: 1 },
                 function () { return m.gSat; }, function (v) { m.gSat = v; })
        ];
      },
      'Parameters': function () {
        return [
          numRow("E' (Young's modulus)", 'kN/m²', { exclusiveMin: 0, decimals: null },
                 function () { return m.E; }, function (v) { m.E = v; }),
          numRow("ν' (Poisson's ratio)", '', { min: 0, exclusiveMax: 0.5, decimals: 3 },
                 function () { return m.nu; }, function (v) { m.nu = v; }),
          numRow("c' (cohesion)", 'kN/m²', { min: 0, nullable: true, decimals: 1 },
                 function () { return m.c; }, function (v) { m.c = v; }),
          numRow("φ' (friction angle)", '°', { min: 0, exclusiveMax: 90, nullable: true, decimals: 1 },
                 function () { return m.phi; }, function (v) { m.phi = v; })
        ];
      },
      'Groundwater': function () {
        return [
          numRow('k (permeability)', 'm/day', { min: 0, decimals: 4 },
                 function () { return m.k; }, function (v) { m.k = v; })
        ];
      },
      'Interfaces': function () {
        return [
          numRow('Rinter (strength reduction)', '', { exclusiveMin: 0, max: 1, decimals: 2 },
                 function () { return m.rInter; }, function (v) { m.rInter = v; }),
          selectRow('Interface permeability', App.INTERFACE_PERM,
                    function () { return m.interfacePerm; }, function (v) { m.interfacePerm = v; })
        ];
      }
    };
    var names = Object.keys(TABS);

    open({
      title: 'Material set — ' + m.name,
      width: 460, height: 400,
      buttons: [{ label: 'Close', primary: true }],
      build: function (body, ctx) {
        titleNode = ctx.dialog.querySelector('.dlg-title');
        var wrap = el('div.dlg-simple', { style: 'display:flex;flex-direction:column;padding:0' });
        var tabs = el('div.mat-tabs');
        var grid = el('div.pgrid', { style: 'padding-top:10px;flex:1;overflow:auto' });
        hint = el('div.lay-hint', { text: DEFAULT_HINT });
        wrap.appendChild(tabs);
        wrap.appendChild(grid);
        wrap.appendChild(hint);
        body.appendChild(wrap);

        function show(name) {
          tabs.querySelectorAll('.mat-tab').forEach(function (b) {
            b.classList.toggle('active', b.dataset.tab === name);
          });
          App.UI.clear(grid);
          TABS[name]().forEach(function (r) { grid.appendChild(r); });
          say(null);
        }

        names.forEach(function (name) {
          var b = el('button.mat-tab', { text: name, type: 'button', data: { tab: name } });
          b.addEventListener('click', function () { show(name); });
          tabs.appendChild(b);
        });
        show(names[0]);
      }
    });
  }

  /* ══════════════════════════════════════════════════════════════
     Import soil layers
     ══════════════════════════════════════════════════════════════ */
  function importSoilLayers() {
    open({
      title: 'Import soil layers',
      width: 460, height: 260,
      buttons: [{ label: 'Import', primary: true }, { label: 'Cancel' }],
      build: function (body) {
        var wrap = el('div.dlg-simple');
        wrap.appendChild(el('p', { text:
          'Import a borehole/stratigraphy file (e.g. GEF, XML) to populate the soil model.' }));
        wrap.appendChild(el('div.pgrid', null, el('div.pgrid-row', null, [
          el('div.pgrid-key', { text: 'File' }),
          el('div.pgrid-val.readonly', { text: 'No file selected' })
        ])));
        wrap.appendChild(el('div.mock-banner', { text:
          'UI mockup — file import is not wired up; use "Modify soil layers…" to edit the demo data by hand.' }));
        body.appendChild(wrap);
      }
    });
  }

  /* ══════════════════════════════════════════════════════════════
     Visibility settings
     ══════════════════════════════════════════════════════════════ */
  function visibility() {
    var ITEMS = [
      ['soil', 'Soil volumes'], ['excavation', 'Soil volumes (staged)'],
      ['wall', 'Plates'], ['struts', 'Beams'], ['anchors', 'Anchors'],
      ['piles', 'Embedded beam rows'], ['load', 'Loads'],
      ['water', 'Water levels'], ['wells', 'Wells'], ['mesh', 'Mesh']
    ];
    open({
      title: 'Visibility settings',
      width: 380, height: 400,
      buttons: [{ label: 'Close', primary: true }],
      build: function (body) {
        var wrap = el('div.dlg-simple');
        wrap.appendChild(el('p', { text: 'Show or hide object groups in the active view.' }));
        ITEMS.forEach(function (it) {
          var cb = el('input.pgrid-check', { type: 'checkbox' });
          cb.checked = App.Viewport.isVisible(it[0]);
          cb.addEventListener('change', function () {
            App.Viewport.setVisible(it[0], cb.checked);
            App.Explorer.syncEyes(it[0], cb.checked);
          });
          var row = el('label', { style: 'display:flex;gap:8px;align-items:center;padding:3px 0;cursor:pointer' },
                       [cb, el('span', { text: it[1] })]);
          wrap.appendChild(row);
        });
        body.appendChild(wrap);
      }
    });
  }

  /* ══════════════════════════════════════════════════════════════
     Small informational dialogs
     ══════════════════════════════════════════════════════════════ */
  function about() {
    open({
      title: 'About ' + App.PRODUCT.name,
      width: 480, height: 300,
      buttons: [{ label: 'OK', primary: true }],
      build: function (body) {
        body.appendChild(el('div.dlg-simple', null, [
          el('h3', { text: App.PRODUCT.name }),
          el('p', { text: App.PRODUCT.version }),
          el('p', { text: 'A user-interface concept for a 3D finite element geotechnical ' +
                          'modelling application.' }),
          el('div.mock-banner', { text:
            'This is a front-end mockup only. There is no computational kernel, no file I/O and ' +
            'no persistence — every value shown is sample data.' })
        ]));
      }
    });
  }

  function commandReference() {
    open({
      title: 'Command reference',
      width: 560, height: 400,
      buttons: [{ label: 'Close', primary: true }],
      build: function (body) {
        var ul = el('ul');
        [['borehole <x> <y>', 'add a borehole'],
         ['soillayers', 'open the Modify soil layers window'],
         ['materials', 'open the material sets window'],
         ['mesh', 'switch to Mesh mode and generate the mesh'],
         ['gotosoil / gotostructures / gotomesh / gotoflow / gotostaged', 'switch mode'],
         ['view iso | top | front | side', 'standard views'],
         ['zoomfit', 'zoom to fit the visible model'],
         ['clear', 'clear the session log'],
         ['help', 'list the demo commands']].forEach(function (r) {
          ul.appendChild(el('li', null, [el('code', { text: r[0] }), el('span', { text: '  —  ' + r[1] })]));
        });
        body.appendChild(el('div.dlg-simple', null, [
          el('h3', { text: 'Demo commands' }),
          el('p', { text: 'The command line recognises this small set so the panel behaves like the real one.' }),
          ul,
          el('div.mock-banner', { text: 'The real command reference would list the full scripting API.' })
        ]));
      }
    });
  }

  function notImplemented(title, text) {
    open({
      title: title, width: 460, height: 250,
      buttons: [{ label: 'OK', primary: true }],
      build: function (body) {
        body.appendChild(el('div.dlg-simple', null, [
          el('h3', { text: title }),
          el('p', { text: text }),
          el('div.mock-banner', { text: 'No solver or output viewer is attached to this mockup.' })
        ]));
      }
    });
  }

  return {
    open: open, draggable: drag, resizable: resize,
    soilLayers: soilLayers, materials: materials,
    importSoilLayers: importSoilLayers, visibility: visibility,
    about: about, commandReference: commandReference, notImplemented: notImplemented
  };
})();
