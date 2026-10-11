/* ══════════════════════════════════════════════════════════════════
   material-sets.js — the Material sets dialog, for Kratos property sets.

   The frozen dialog (js/dialogs.js) edits an engineering-units sheet: unit weights in kN/m3,
   E in kN/m2, permeability in m/day, a material model and a drainage type -- numbers
   the exporter used to convert. A soil is now what Kratos reads (core/model/schemas.py
   `Material`): a constitutive law and its Variables under Kratos' own names, in the
   project's unit system, written into the deck as they stand. So this replaces that
   dialog with one that shows and edits exactly that, each number labelled in the
   project's units, and says which variables the export derives when they are left out.

   The contract with patches.js is unchanged: the dialog edits App.MATERIALS in place,
   its footer carries OK and Cancel, and patches.js turns OK into the PATCH that stores
   the library (and Cancel into putting it back). App.addMaterial and
   App.duplicateMaterial -- frozen helpers the toolbar and the soil dialog call -- make
   property sets too.
   ══════════════════════════════════════════════════════════════════ */

App.MaterialSets = (function () {
  'use strict';

  var P = App.PropertySets;

  function el() { return App.UI.el.apply(null, arguments); }
  function copy(value) { return JSON.parse(JSON.stringify(value)); }
  function dimension() { return App.PROJECT && App.PROJECT.dimension === 3 ? 3 : 2; }

  var sequence = 0;

  /* A brand new soil: a loose drained sand in the project's units, valid as it stands
     so it can be saved without touching a field first. */
  function newMaterial() {
    var id;
    do { sequence += 1; id = 'mx' + sequence; }
    while ((App.MATERIALS || []).some(function (m) { return m.id === id; }));
    var set = P.defaults('soil', App.Units.current(), dimension());
    return { id: id, name: 'Material_' + ((App.MATERIALS || []).length + 1), color: '#9aa7b4',
             constitutive_law: set.constitutive_law, variables: set.variables, tables: {},
             rInter: 0.70, interfacePerm: 'Neutral' };
  }

  function addMaterial() {
    var m = newMaterial();
    App.MATERIALS.push(m);
    return m;
  }

  function duplicateMaterial(source) {
    var m = copy(source);
    m.id = newMaterial().id;
    m.name = source.name + ' (copy)';
    App.MATERIALS.splice(App.MATERIALS.indexOf(source) + 1, 0, m);
    return m;
  }

  /* What a table cell shows for one variable: the number, or that the export derives
     it, or a dash. */
  function shown(m, name) {
    var value = (m.variables || {})[name];
    if (value === undefined) return P.derivable('soil', name) ? 'derived' : '—';
    return typeof value === 'number' ? String(+value.toPrecision(6)) : P.format(value);
  }

  var COLUMNS = ['GEO_DRAINAGE_TYPE', 'DENSITY_SOLID', 'YOUNG_MODULUS', 'GEO_FRICTION_ANGLE'];

  function heading(name) {
    var unit = App.Units.variableLabel(name);
    return name + (unit ? ' [' + unit + ']' : '');
  }

  /* ── The dialog ──────────────────────────────────────────────────── */

  function open(onClose) {
    var selected = App.MATERIALS.length ? App.MATERIALS[0].id : null;
    var toolbar = el('div.dlg-toolbar');
    var hint, table, body;

    function say(message, invalid) {
      if (!hint) return;
      hint.textContent = message ||
        'A soil is a Kratos property set: a constitutive law and its variables, in ' +
        App.Units.title() + '. Properties… edits them.';
      hint.classList.toggle('invalid', !!invalid);
    }

    function current() {
      return App.MATERIALS.filter(function (m) { return m.id === selected; })[0] || null;
    }

    function render() {
      App.UI.clear(body);
      App.MATERIALS.forEach(function (m) {
        var swatch = el('span.tree-swatch');
        swatch.style.background = m.color;
        var cells = [el('td', null, swatch), el('td', { text: m.name }),
                     el('td', { text: m.constitutive_law })];
        COLUMNS.forEach(function (name) {
          cells.push(el('td' + (name === 'GEO_DRAINAGE_TYPE' ? '' : '.num'), { text: shown(m, name) }));
        });
        cells.push(el('td', null, el('button.btn.btn-sm', {
          text: 'Properties…', type: 'button', 'data-action': 'material-properties',
          onclick: function (event) {
            event.stopPropagation();
            selected = m.id;
            editor(m, render);
            render();
          } })));
        var row = el('tr' + (m.id === selected ? '.sel' : ''), { 'data-material': m.id }, cells);
        row.addEventListener('click', function () { selected = m.id; say(null); render(); });
        body.appendChild(row);
      });
    }

    [['new', 'New material set'], ['copy', 'Duplicate material set'],
     ['delete', 'Delete material set'], null, ['materials', 'Properties…']].forEach(function (spec) {
      if (!spec) { toolbar.appendChild(el('span.tbsep')); return; }
      var button = el('button.tbtn', { type: 'button', 'data-action': spec[0] });
      button.appendChild(App.UI.icon(spec[0]));
      App.UI.attachTip(button, spec[1]);
      button.addEventListener('click', function () {
        App.UI.hideTip();
        var m = current();
        if (spec[0] === 'new') {
          selected = App.addMaterial().id;
          say('Added ' + current().name + '. Open Properties… to set its values.');
          render();
          return;
        }
        if (!m) { say('Select a material set first.', true); return; }
        if (spec[0] === 'copy') {
          selected = App.duplicateMaterial(m).id;
          say('Duplicated ' + m.name + '.');
        } else if (spec[0] === 'delete') {
          // The server refuses a layer pointing at a missing material; say so first.
          var used = App.layersUsingMaterial ? App.layersUsingMaterial(m.id) : [];
          if (used.length) {
            say('"' + m.name + '" is assigned to ' + used.join(', ') + '. Reassign those layers first.', true);
            return;
          }
          var at = App.MATERIALS.indexOf(m);
          App.MATERIALS.splice(at, 1);
          selected = App.MATERIALS.length ? App.MATERIALS[Math.min(at, App.MATERIALS.length - 1)].id : null;
          say('Deleted ' + m.name + '.');
        } else {
          editor(m, render);
        }
        render();
      });
      toolbar.appendChild(button);
    });

    return App.Dialogs.open({
      title: 'Material sets', width: 860, height: 480, toolbar: toolbar, onClose: onClose,
      buttons: [{ label: 'OK', primary: true }, { label: 'Cancel' }],
      build: function (root) {
        var wrap = el('div.dlg-simple');
        wrap.appendChild(library(function (id) { selected = id; render(); }, current, say));
        wrap.appendChild(el('h3', { text: 'Soil and interfaces — ' + App.Units.title() }));
        table = el('table.mat-table.selectable.material-sets');
        var head = el('tr');
        ['', 'Identification', 'Constitutive law'].concat(COLUMNS.map(heading), ['']).forEach(function (h) {
          head.appendChild(el('th', { text: h }));
        });
        table.appendChild(el('thead', null, head));
        body = el('tbody');
        table.appendChild(body);
        wrap.appendChild(table);
        hint = el('div.lay-hint', { style: 'border-top:0;background:none;padding:6px 0' });
        wrap.appendChild(hint);
        root.appendChild(wrap);
        render();
        say(null);
      }
    });
  }

  function library(onAdded, current, say) {
    var box = el('div.material-library');
    box.appendChild(el('h3', { text: 'Default library' }));
    box.appendChild(el('p', { text: 'Copy a soil preset into this project, or apply interface ' +
      'defaults to the selected material. Starting values in the project\'s units; review them.' }));
    var soils = el('select', { 'aria-label': 'Soil preset' });
    App.MaterialLibrary.soils().forEach(function (m) {
      soils.appendChild(el('option', { value: m.id, text: m.name }));
    });
    box.appendChild(el('div.lay-toolbar', null, [el('span', { text: 'Soil' }), soils,
      el('button.btn.btn-sm', { text: 'Add to project', type: 'button', 'data-action': 'add-soil-preset',
        onclick: function () {
          var m = App.MaterialLibrary.addSoil(soils.value);
          onAdded(m.id);
          say('Added ' + m.name + ' from the default library. Open Properties… to review it.');
        } })]));
    var contacts = el('select', { 'aria-label': 'Interface preset' });
    App.MaterialLibrary.interfaces().forEach(function (p) {
      contacts.appendChild(el('option', { value: p.id,
        text: p.name + ' — Rinter ' + p.rInter + ', ' + p.interfacePerm }));
    });
    box.appendChild(el('div.lay-toolbar', null, [el('span', { text: 'Interface' }), contacts,
      el('button.btn.btn-sm', { text: 'Apply to selected', type: 'button',
        'data-action': 'apply-interface-preset', onclick: function () {
          var m = current();
          if (!m) { say('Select a material set first.', true); return; }
          App.MaterialLibrary.applyInterface(m, contacts.value);
          say('Applied interface defaults to ' + m.name + ': Rinter ' + m.rInter + ', ' + m.interfacePerm + '.');
        } })]));
    return box;
  }

  /* ── One material's property set ─────────────────────────────────── */

  /* Every edit is checked as a whole set (App.PropertySets.validate) and undone when it
     would not save -- the same bounds the server holds, so OK cannot come back a 422. */
  function editor(m, changed) {
    var hint, grid, title;
    var DEFAULT = 'Kratos\' names, in ' + App.Units.title() + '. A blank variable the ' +
                  'export can derive is left to it; an invalid entry is refused and put back.';

    function say(message) {
      if (!hint) return;
      hint.textContent = message || DEFAULT;
      hint.classList.toggle('invalid', !!message);
    }

    function attempt(apply) {
      var before = copy(m);
      apply();
      var problem = (!m.name || !m.name.trim()) ? 'Identification cannot be empty.'
                                               : P.validate('soil', m);
      if (problem) {
        Object.keys(m).forEach(function (k) { delete m[k]; });
        Object.assign(m, before);
        say(problem);
        draw();
        return false;
      }
      say(null);
      if (changed) changed();
      return true;
    }

    function field(label, control, unit) {
      var value = el('div.pgrid-val.editable.field', null, [control]);
      if (unit) value.appendChild(el('span.unit', { text: unit }));
      return el('div.pgrid-row', null, [el('div.pgrid-key', { text: label }), value]);
    }

    function textInput(value, onCommit, attrs) {
      var input = el('input.cell-input', Object.assign({ value: value }, attrs || {}));
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
      });
      input.addEventListener('change', function () { onCommit(input.value); });
      return input;
    }

    function draw() {
      App.UI.clear(grid);
      grid.appendChild(el('h4', { text: 'General' }));
      grid.appendChild(field('Identification', textInput(m.name, function (v) {
        attempt(function () { m.name = v.trim(); });
        if (title) title.textContent = 'Material set — ' + m.name;
      }, { 'data-field': 'name' })));
      var colour = el('input', { type: 'color', value: m.color, 'data-field': 'color' });
      colour.addEventListener('input', function () { attempt(function () { m.color = colour.value; }); });
      grid.appendChild(field('Colour', colour));
      var laws = el('datalist', { id: 'material-laws' });
      [P.lawFor('soil', 2), P.lawFor('soil', 3)].forEach(function (law) {
        laws.appendChild(el('option', { value: law }));
      });
      grid.appendChild(laws);
      grid.appendChild(field('Constitutive law', textInput(m.constitutive_law, function (v) {
        attempt(function () { m.constitutive_law = v.trim(); });
      }, { list: 'material-laws', 'data-field': 'constitutive_law' })));

      grid.appendChild(el('h4', { text: 'Variables' }));
      P.names('soil', m, dimension()).forEach(function (name) {
        var value = (m.variables || {})[name];
        var input = textInput(P.format(value), function (text) {
          attempt(function () {
            var parsed = P.parse(text);
            if (parsed === undefined) delete m.variables[name]; else m.variables[name] = parsed;
          });
          draw();
        }, { 'data-variable': name,
             placeholder: P.derivable('soil', name) ? 'derived' : '' });
        var row = field(name, input, App.Units.variableLabel(name));
        if ((m.variables || {})[name] !== undefined) {
          row.appendChild(el('button.btn.btn-sm', { text: '×', type: 'button', title: 'Leave out',
            'data-remove': name, onclick: function () {
              attempt(function () { delete m.variables[name]; });
              draw();
            } }));
        }
        grid.appendChild(row);
      });

      // Any other variable Kratos reads -- a UDSM's parameters, OCR, a retention law.
      var names = el('datalist', { id: 'kratos-variables' });
      Object.keys(App.UNIT_TABLE.variables).forEach(function (n) {
        names.appendChild(el('option', { value: n }));
      });
      grid.appendChild(names);
      var newName = el('input.cell-input', { list: 'kratos-variables', placeholder: 'VARIABLE_NAME',
                                             'data-field': 'new-variable' });
      var newValue = el('input.cell-input', { placeholder: 'value', 'data-field': 'new-value' });
      var add = el('button.btn.btn-sm', { text: 'Add variable', type: 'button', 'data-action': 'add-variable',
        onclick: function () {
          var name = newName.value.trim().toUpperCase();
          var value = P.parse(newValue.value);
          if (!name || value === undefined) { say('Give the variable a name and a value.'); return; }
          if (attempt(function () { m.variables[name] = value; })) draw();
        } });
      grid.appendChild(el('div.pgrid-row', null, [el('div.pgrid-key', { text: 'Add' }),
        el('div.pgrid-val.field', null, [newName, newValue, add])]));

      grid.appendChild(el('h4', { text: 'Interfaces' }));
      grid.appendChild(field('Rinter', textInput(String(m.rInter), function (v) {
        var r = Number(v);
        if (!(r > 0 && r <= 1)) { say('Rinter must be above 0 and at most 1.'); draw(); return; }
        attempt(function () { m.rInter = r; });
      }, { 'data-field': 'rInter' })));
      var permeability = el('select', { 'data-field': 'interfacePerm' });
      ['Neutral', 'Drain', 'Impermeable'].forEach(function (p) {
        permeability.appendChild(el('option', { value: p, text: p }));
      });
      permeability.value = m.interfacePerm || 'Neutral';
      permeability.addEventListener('change', function () {
        attempt(function () { m.interfacePerm = permeability.value; });
      });
      grid.appendChild(field('Interface permeability', permeability));
    }

    m.variables = m.variables || {};
    return App.Dialogs.open({
      title: 'Material set — ' + m.name, width: 560, height: 560,
      buttons: [{ label: 'Close', primary: true }],
      build: function (root, ctx) {
        title = ctx && ctx.dialog ? ctx.dialog.querySelector('.dlg-title') : null;
        var wrap = el('div.dlg-simple', { style: 'display:flex;flex-direction:column;padding:0' });
        grid = el('div.pgrid.material-variables', { style: 'padding-top:10px;flex:1;overflow:auto' });
        hint = el('div.lay-hint', { text: DEFAULT });
        wrap.appendChild(grid);
        wrap.appendChild(hint);
        root.appendChild(wrap);
        draw();
      }
    });
  }

  return { open: open, editor: editor, newMaterial: newMaterial,
           addMaterial: addMaterial, duplicateMaterial: duplicateMaterial };
})();

/* Installed over the frozen helpers before patches.js wraps the dialog with its save. */
if (App.Dialogs) App.Dialogs.materials = App.MaterialSets.open;
App.addMaterial = App.MaterialSets.addMaterial;
App.duplicateMaterial = App.MaterialSets.duplicateMaterial;
App.newMaterialDefaults = App.MaterialSets.newMaterial;
