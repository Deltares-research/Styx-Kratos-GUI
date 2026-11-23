/* ══════════════════════════════════════════════════════════════════
   material-sets.js — the Soil materials dialog, for Kratos property sets.

   The frozen dialog (js/dialogs.js) edits an engineering-units sheet: unit weights in kN/m3,
   E in kN/m2, permeability in m/day, a material model and a drainage type -- numbers
   the exporter used to convert. A soil is now what Kratos reads (core/model/schemas.py
   `Material`): a constitutive law and its Variables under Kratos' own names, in the
   project's unit system, written into the deck as they stand. So this replaces that
   dialog with one that shows and edits exactly that, each number labelled in the
   project's units, and shows what the export derives when a value is left out. The
   water is not a soil's: it is the project's, one for every soil, edited under Water.

   The contract with patches.js is unchanged: the dialog edits App.MATERIALS in place,
   its footer carries OK and Cancel, and patches.js turns OK into the PATCH that stores
   the library (and Cancel into putting it back). App.addMaterial and
   App.duplicateMaterial -- frozen helpers the toolbar and the soil dialog call -- make
   property sets too.
   ══════════════════════════════════════════════════════════════════ */

App.MaterialSets = (function () {
  'use strict';

  var P = App.PropertySets;
  var S = App.SoilModels;

  function el() { return App.UI.el.apply(null, arguments); }
  function copy(value) { return JSON.parse(JSON.stringify(value)); }
  function dimension() { return App.PROJECT && App.PROJECT.dimension === 3 ? 3 : 2; }

  /* A groundwater flow project reads every soil's flow parameters, whatever its
     drainage type. */
  function flowProject() {
    return !!(App.Stages && App.PROJECT && App.Stages.groundwaterFlow(App.PROJECT));
  }

  /* The water every soil holds, as Kratos reads it: the water level's specific weight,
     and the bulk modulus and viscosity edited under Water in this window (App.FLUID). */
  function waterWeight() {
    var level = App.PROJECT && App.PROJECT.water;
    return level && level.specific_weight !== null && level.specific_weight !== undefined
      ? level.specific_weight : null;
  }

  function waterVariables() {
    var fluid = App.FLUID || {};
    return S.water(App.Units.current(), waterWeight(), fluid.bulk_modulus, fluid.dynamic_viscosity,
                   projectGravity());
  }

  /* Project.gravity_acceleration, in m/s2: what the unit weights and the water's density
     are worked out with. */
  function projectGravity() {
    return App.PROJECT ? App.PROJECT.gravity_acceleration : undefined;
  }

  /* A number as the window shows it: six significant figures, and a power of ten when it
     is very large or very small, so 1.157e-12 m² reads as what it is. */
  function number(value) {
    if (typeof value !== 'number' || !isFinite(value)) return P.format(value);
    if (value === 0) return '0';
    var size = Math.abs(value);
    if (size >= 1e6 || size < 1e-3) {
      var parts = value.toExponential(5).split('e');
      return parts[0].replace(/\.?0+$/, '') + 'e' + parts[1].replace('+', '');
    }
    return String(+value.toPrecision(6));
  }

  var sequence = 0;

  /* A colour no soil has yet (App.SoilModels.freshColor, as `kratos-cli material add`
     gives one). */
  function freshColor() {
    return S.freshColor((App.MATERIALS || []).map(function (m) { return m.color; }));
  }

  /* A brand new soil: a loose drained sand in the project's units, valid as it stands
     so it can be saved without touching a field first. */
  function newMaterial() {
    var id;
    do { sequence += 1; id = 'mx' + sequence; }
    while ((App.MATERIALS || []).some(function (m) { return m.id === id; }));
    var set = P.defaults('soil', App.Units.current(), dimension());
    return { id: id, name: 'Material_' + ((App.MATERIALS || []).length + 1), color: freshColor(),
             constitutive_law: set.constitutive_law, variables: set.variables, tables: {},
             rInter: 0.70, interfacePerm: 'Neutral' };
  }

  function addMaterial() {
    var m = newMaterial();
    App.MATERIALS.push(m);
    return m;
  }

  /* A soil to fill in by hand: linear elastic, drained, saturated below the phreatic
     level, and nothing else -- the catalogue's (App.SoilModels.blankSI), which
     `kratos-cli material add` starts from too. Its stiffness and weight are the user's
     to type, so it is not ready for a calculation until they are (`missing`); what is
     left blank and derivable -- K0 from the Poisson ratio or the friction angle -- is
     shown as derived. */
  function blankSoil() {
    var m = newMaterial();
    m.constitutive_law = S.law('linear_elastic', dimension());
    m.variables = App.Units.convertVariables(S.blankSI(), 'SI', App.Units.current());
    return m;
  }

  function createSoil() {
    var m = blankSoil();
    App.MATERIALS.push(m);
    return m;
  }

  /* What the soil's model needs and the soil leaves blank: the Kratos names. */
  function missing(m) {
    return S.missing(m.constitutive_law, m.variables || {});
  }

  function labels(m, names) {
    var model = S.modelOf(m.constitutive_law);
    return names.map(function (name) {
      var p = S.find(model, name);
      return p ? p.label : name;
    });
  }

  function duplicateMaterial(source) {
    var m = copy(source);
    var fresh = newMaterial();
    m.id = fresh.id;
    m.color = fresh.color;
    m.name = source.name + ' (copy)';
    App.MATERIALS.splice(App.MATERIALS.indexOf(source) + 1, 0, m);
    return m;
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
        var swatch = el('span.tree-swatch.material-swatch');
        swatch.style.background = m.color;
        // The soil model, as the editor's drop-down names it; a law of no model by its
        // own name. The law itself on hover, as `kratos-cli material list` gives both.
        var model = S.modelOf(m.constitutive_law);
        var cells = [el('td', null, swatch), el('td', { text: m.name }),
                     el('td', { text: model === S.OTHER ? m.constitutive_law : S.label(model),
                                title: m.constitutive_law, 'data-column': 'soil-model' })];
        cells.push(el('td', null, el('button.btn.btn-sm', {
          text: 'Properties…', type: 'button', 'data-action': 'material-properties',
          onclick: function (event) {
            event.stopPropagation();
            selected = m.id;
            editor(m, render);
            render();
          } })));
        var row = el('tr' + (m.id === selected ? '.sel' : ''), { 'data-material': m.id }, cells);
        var lacks = labels(m, missing(m));
        if (lacks.length) row.title = 'Still to fill in: ' + lacks.join(', ') + '.';
        row.addEventListener('click', function () { selected = m.id; say(null); render(); });
        body.appendChild(row);
      });
    }

    /* A new soil is a blank one, opened to be filled in. */
    function create() {
      var m = createSoil();
      selected = m.id;
      say('Created ' + m.name + '. Fill in its values.');
      render();
      editor(m, render);
    }

    [['new', 'Create soil'], ['copy', 'Duplicate soil material'],
     ['delete', 'Delete soil material'], null, ['materials', 'Properties…']].forEach(function (spec) {
      if (!spec) { toolbar.appendChild(el('span.tbsep')); return; }
      var button = el('button.tbtn', { type: 'button', 'data-action': spec[0] });
      button.appendChild(App.UI.icon(spec[0]));
      App.UI.attachTip(button, spec[1]);
      button.addEventListener('click', function () {
        App.UI.hideTip();
        var m = current();
        if (spec[0] === 'new') { create(); return; }
        if (!m) { say('Select a soil material first.', true); return; }
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
      title: 'Soil materials', width: 860, height: 620, toolbar: toolbar, onClose: onClose,
      buttons: [{ label: 'OK', primary: true }, { label: 'Cancel' }],
      build: function (root) {
        var wrap = el('div.dlg-simple');
        wrap.appendChild(el('h3', { text: 'Soils — ' + App.Units.title() }));
        wrap.appendChild(el('div.lay-toolbar', null, [el('button.btn.btn-sm.btn-primary', {
          text: 'Create soil', type: 'button', 'data-action': 'create-soil', onclick: create })]));
        table = el('table.mat-table.selectable.material-sets');
        var head = el('tr');
        ['Colour', 'Name', 'Soil model', 'Properties'].forEach(function (h) {
          head.appendChild(el('th', { text: h }));
        });
        table.appendChild(el('thead', null, head));
        body = el('tbody');
        table.appendChild(body);
        wrap.appendChild(table);
        wrap.appendChild(water(function (message, invalid) { say(message, invalid); }));
        wrap.appendChild(library(function (id) { selected = id; render(); }, say));
        hint = el('div.lay-hint', { style: 'border-top:0;background:none;padding:6px 0' });
        wrap.appendChild(hint);
        root.appendChild(wrap);
        render();
        say(null);
      }
    });
  }

  /* The water in every soil's pores: one for the project, as every soil holds the same
     water (core/model/schemas.py `Fluid`). Its weight is the water level's, shown here;
     its bulk modulus and viscosity are edited here, on App.FLUID, and saved with the
     soils. Left blank, each is water's at 20 C. */
  function water(say) {
    var box = el('div.pgrid.material-water');
    box.appendChild(el('h3', { text: 'Water' }));
    var weight = waterWeight();
    var shownWeight = weight !== null ? weight
      : App.Units.fromSI(App.SOIL_MODEL_TABLE.constants.WATER_SPECIFIC_WEIGHT, 'specific weight');
    box.appendChild(el('div.pgrid-row', { title: 'DENSITY_WATER is this over g' }, [
      el('div.pgrid-key', { text: 'Unit weight' }),
      el('div.pgrid-val.readonly.field', { 'data-water': 'specific_weight' }, [
        el('span.computed-value', { text: number(shownWeight) }),
        el('span.unit', { text: App.Units.label('specific weight') })])]));
    [['bulk_modulus', 'Bulk modulus', 'BULK_MODULUS_FLUID', 'stress',
      App.SOIL_MODEL_TABLE.constants.WATER_BULK_MODULUS],
     ['dynamic_viscosity', 'Dynamic viscosity', 'DYNAMIC_VISCOSITY', 'viscosity',
      App.SOIL_MODEL_TABLE.constants.WATER_VISCOSITY]].forEach(function (spec) {
      App.FLUID = App.FLUID || {};
      var value = App.FLUID[spec[0]];
      var input = el('input.cell-input', {
        value: value === null || value === undefined ? '' : number(value), 'data-water': spec[0],
        placeholder: number(App.Units.fromSI(spec[4], spec[3])) + ' (water)' });
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
      });
      input.addEventListener('change', function () {
        var parsed = P.parse(input.value);
        if (parsed === undefined) {
          App.FLUID[spec[0]] = null;
          say(spec[1] + ' of the water left blank: water\'s own.');
        } else if (typeof parsed !== 'number' || !(parsed > 0)) {
          input.value = value === null || value === undefined ? '' : number(value);
          say('The water\'s ' + spec[1].toLowerCase() + ' must be a number greater than zero.', true);
          return;
        } else {
          App.FLUID[spec[0]] = parsed;
          say(null);
        }
        value = App.FLUID[spec[0]];
      });
      box.appendChild(el('div.pgrid-row', { title: spec[2] + ', written into every soil' }, [
        el('div.pgrid-key', { text: spec[1] }),
        el('div.pgrid-val.editable.field', null, [
          input, el('span.unit', { text: App.Units.label(spec[3]) })])]));
    });
    return box;
  }

  /* The presets, below the soils: a soil, and the soil model to add it as -- its own
     until another is chosen (`kratos-cli material add --preset ID --model M`). */
  function library(onAdded, say) {
    var box = el('div.material-library');
    box.appendChild(el('h3', { text: 'Default soil material library' }));
    box.appendChild(el('p', { text: 'Copy a soil preset into this project. Starting values in ' +
      'the project\'s units; review them.' }));
    var presets = App.MaterialLibrary.soils();
    var soils = el('select', { 'aria-label': 'Soil preset', 'data-field': 'preset' });
    presets.forEach(function (m) {
      soils.appendChild(el('option', { value: m.id, text: m.name }));
    });
    var model = el('select', { 'aria-label': 'Soil model of the preset', 'data-field': 'preset-model' });
    S.order().forEach(function (id) {
      model.appendChild(el('option', { value: id, text: S.label(id) }));
    });
    function ownModel() {
      model.value = presets.filter(function (m) { return m.id === soils.value; })[0].model;
    }
    soils.addEventListener('change', ownModel);
    ownModel();
    function added(m, notes) {
      onAdded(m.id);
      say(['Added ' + m.name + ' (' + S.label(S.modelOf(m.constitutive_law)) + ') from the ' +
           'default soil material library. Open Properties… to review it.'].concat(notes).join(' '));
    }
    box.appendChild(el('div.lay-toolbar', null, [el('span', { text: 'Soil' }), soils,
      el('span', { text: 'Model' }), model,
      // The preset in the soil's own window, before it is in the project: looked at, or
      // changed and then added as it stands.
      el('button.btn.btn-sm', { text: 'Properties…', type: 'button', 'data-action': 'preview-soil-preset',
        onclick: function () {
          var notes = [];
          var m = App.MaterialLibrary.preview(soils.value, model.value, notes);
          editor(m, null, { notes: notes, onAdd: function () {
            added(App.MaterialLibrary.add(m), []);
          } });
        } }),
      el('button.btn.btn-sm', { text: 'Add to project', type: 'button', 'data-action': 'add-soil-preset',
        onclick: function () {
          var notes = [];
          added(App.MaterialLibrary.addSoil(soils.value, model.value, notes), notes);
        } })]));
    return box;
  }

  /* ── One material's property set ─────────────────────────────────── */

  /* Every edit is checked as a whole set (App.PropertySets.validate) and undone when it
     would not save -- the same bounds the server holds, so OK cannot come back a 422.

     The soil model comes first (App.SoilModels): it sets the law for the project's
     dimension and the parameters listed, in groups. A choice is a drop-down of the
     values Kratos accepts, a flag a check box, a number a text box in the project's
     units. A model chosen, a choice changed or a flag switched fills in the defaults of
     what the soil now lists and lacks, and the hint says which. Only what the model,
     the drainage type and the retention law make relevant is listed. A value left
     blank shows what the export derives in its place; the unit weights and the Darcy
     permeability that follow from the soil's numbers are shown, not typed. "Other" is
     any law, typed by name, with the variables the soil carries and any it is given.

     A model chosen leaves out what it does not read -- no cohesion for a linear elastic
     soil -- and keeps it aside while the window is open, so choosing the model back
     brings back the values typed, not its defaults.

     With `library.onAdd`, `m` is a library soil that is not in the project
     (App.MaterialLibrary.preview): the window says so, and its Add to project calls
     `library.onAdd` with the soil as it stands; Close leaves the project as it was. */
  function editor(m, changed, library) {
    var hint, grid, title;
    var other = S.modelOf(m.constitutive_law) === S.OTHER;
    var aside = {};
    var DEFAULT = (library ? 'Not in the project: Add to project copies this soil in, with ' +
                             'any change made here. ' : '') +
                  'In ' + App.Units.title() + '; hover a name for its Kratos variable. A ' +
                  'blank value shows what the export derives in its place; an invalid ' +
                  'entry is refused and put back.';

    /* No message: what the soil still lacks for a calculation, or the usual line. */
    function say(message, notice) {
      if (!hint) return;
      var lacks = labels(m, missing(m));
      hint.textContent = message || (lacks.length
        ? 'Still to fill in before a calculation: ' + lacks.join(', ') + '.' : DEFAULT);
      hint.classList.toggle('invalid', !!message && !notice);
    }

    /* A value the law needs may stay blank -- a soil is filled in one value at a time --
       but one the soil holds is not blanked, and none may be invalid. */
    function attempt(apply) {
      var before = copy(m);
      apply();
      var blanked = missing(m).filter(function (name) {
        return typeof (before.variables || {})[name] === 'number';
      });
      var problem = (!m.name || !m.name.trim()) ? 'Identification cannot be empty.'
                  : blanked.length ? m.constitutive_law + ' needs ' + blanked.join(', ') + '.'
                  : P.validate('soil', m, true);
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

    /* An edit that can list more -- a model, a choice, a flag -- with the defaults of
       what it lists anew filled in (App.SoilModels.fillChoice, which `kratos-cli
       material add --model` fills with too). A soil still being filled in by hand gets
       no number it must have, and nothing it was listing and left blank: those stay the
       user's to type, a model chosen or not. */
    function choose(apply) {
      var beforeLaw = m.constitutive_law, before = copy(m.variables);
      var flow = flowProject();
      var filled = [];
      var ok = attempt(function () {
        apply();
        filled = S.fillChoice(beforeLaw, before, m.constitutive_law, m.variables,
                              App.Units.current(), flow);
      });
      if (ok && filled.length) say(S.filledNote(S.modelOf(m.constitutive_law), filled), true);
      draw();
      return ok;
    }

    /* A row: the label, the control, and the unit right beside it -- a slot every row
       has, empty for a pure number, so the units line up -- then a slot for the button
       that leaves a value out, so they stay lined up whether it is there or not. `name`
       is the Kratos variable the row writes, shown when the label is hovered. */
    function field(label, control, unit, name) {
      var value = el('div.pgrid-val.editable.field', null,
                     [control, el('span.unit', { text: unit || '' }), el('span.remove-slot')]);
      var key = el('div.pgrid-key', { text: label });
      if (name) key.title = name;
      return el('div.pgrid-row', null, [key, value]);
    }

    /* A value that follows from the soil's numbers (App.SoilModels.computed): shown,
       never typed, never written. */
    function computedRow(name, value) {
      var info = S.computedInfo()[name];
      var cell = el('div.pgrid-val.readonly.field', null, [
        el('span.computed-value', { text: number(value) }),
        el('span.unit', { text: App.Units.label(info.quantity) })]);
      // A conductivity also in the unit people quote it in.
      if (info.quantity === 'velocity') {
        cell.appendChild(el('span.unit-also', { text: '= ' + number(value * 86400) + ' m/day' }));
      }
      cell.appendChild(el('span.remove-slot'));
      return el('div.pgrid-row', { 'data-computed': name }, [
        el('div.pgrid-key', { text: info.label }), cell]);
    }

    function textInput(value, onCommit, attrs) {
      var input = el('input.cell-input', Object.assign({ value: value }, attrs || {}));
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
      });
      input.addEventListener('change', function () { onCommit(input.value); });
      return input;
    }

    function select(options, value, attrs, onChange) {
      var box = el('select', attrs);
      options.forEach(function (o) { box.appendChild(el('option', { value: o.value, text: o.text })); });
      box.value = value;
      box.addEventListener('change', function () { onChange(box.value); });
      return box;
    }

    function held(name) { return Object.prototype.hasOwnProperty.call(m.variables, name); }

    /* The soil's law set to `law`: when it is a model's, what that model does not read
       (App.SoilModels.unread, as `kratos-cli material set --model` leaves it out) is put
       aside and what was put aside that it reads is put back. A law of no model keeps
       all the soil carries. */
    function setLaw(law) {
      m.constitutive_law = law;
      var model = S.modelOf(law);
      if (model === S.OTHER) return;
      var reads = S.parameters(model).map(function (p) { return p.name; });
      Object.keys(aside).forEach(function (name) {
        if (reads.indexOf(name) >= 0 && !held(name)) m.variables[name] = aside[name];
      });
      S.unread(law, m.variables).forEach(function (name) {
        aside[name] = m.variables[name];
        delete m.variables[name];
      });
    }

    /* A number, list or text variable, typed; blank leaves it out. Left out, it shows
       what the export derives in its place (`derived`), or that it derives one. */
    function typedRow(name, label, derived) {
      var placeholder = derived !== undefined ? number(derived) + ' (derived)'
                      : P.derivable('soil', name) ? 'derived' : '';
      var input = textInput(number(m.variables[name]), function (text) {
        attempt(function () {
          var parsed = P.parse(text);
          if (parsed === undefined) delete m.variables[name]; else m.variables[name] = parsed;
        });
        draw();
      }, { 'data-variable': name, placeholder: placeholder });
      var row = field(label || name, input, App.Units.variableLabel(name), label ? name : null);
      if (held(name)) {
        // In the value's cell, in its slot: a third child of the two-column row would
        // wrap below it.
        var slot = row.querySelector('.remove-slot');
        slot.appendChild(el('button.btn.btn-sm', { text: '×', type: 'button',
          title: derived !== undefined || P.derivable('soil', name) ? 'Leave out, and derive it'
                                                                    : 'Leave out',
          'data-remove': name, onclick: function () {
            attempt(function () { delete m.variables[name]; });
            draw();
          } }));
      }
      return row;
    }

    function parameterRow(p, derived) {
      var name = p.name;
      if (p.choices) {
        var value = held(name) ? m.variables[name] : p.absent;
        var options = p.choices.slice();
        if (value !== undefined && options.indexOf(value) < 0) options.unshift(value);
        var text = p.choice_text || {};
        var row = field(p.label, select(options.map(function (c) {
          return { value: c, text: text[c] ? text[c].label : c };
        }), value, { 'data-variable': name }, function (chosen) {
            choose(function () { m.variables[name] = chosen; });
          }), '', name);
        if (!text[value] || !text[value].note) return row;
        // Below the row, the width of the grid: a third child of the two-column row
        // would squeeze into a column.
        return el('div.pgrid-choice', null, [row,
          el('div.pgrid-note', { text: text[value].note, 'data-note': name })]);
      }
      if (p.flag) {
        var box = el('input', { type: 'checkbox', 'data-variable': name });
        box.checked = (held(name) ? m.variables[name] : p.absent) === true;
        box.addEventListener('change', function () {
          var on = box.checked;
          choose(function () { m.variables[name] = on; });
        });
        return field(p.label, box, '', name);
      }
      return typedRow(name, p.label, derived[name]);
    }

    /* A UDSM soil's own rows: the UDSM model, from the libraries that come with Styx
       (App.UDSM_LIBRARY), and its parameters as the library names them, each one entry
       of UMAT_PARAMETERS, in the project's units. A soil naming a library Styx does not
       have keeps its parameters as one typed list. */
    function udsmRows() {
      var system = App.Units.current();
      var current = S.udsmModel(m.variables);
      var options = S.udsmModels().map(function (u) {
        return { value: u.id, text: u.name + ' (' + u.file + ')' };
      });
      if (!current) {
        var named = m.variables.UDSM_NAME;
        options.unshift({ value: '', text: named ? named + ', model ' + m.variables.UDSM_NUMBER +
                          ' (not a library of Styx)' : 'None on this system' });
      }
      var row = field('UDSM model', select(options, current ? current.id : '',
        { 'data-field': 'udsm-model' }, function (chosen) {
          var u = S.udsmById(chosen);
          if (u) choose(function () { S.udsmChoose(m.variables, u, system); });
        }), '', 'UDSM_NAME, UDSM_NUMBER');
      grid.appendChild(row);
      var problems = (App.UDSM_LIBRARY && App.UDSM_LIBRARY.problems) || [];
      if (!S.udsmModels().length && problems.length) {
        grid.appendChild(el('div.pgrid-note', { text: problems.join(' '), 'data-note': 'udsm' }));
      }
      grid.appendChild(el('h4', { text: 'UDSM parameters' }));
      if (!current) {
        grid.appendChild(typedRow('UMAT_PARAMETERS', 'Parameters'));
        return;
      }
      if (!current.known) {
        grid.appendChild(el('div.pgrid-note', { 'data-note': 'udsm-defaults',
          text: 'No start values are known for this model: type every value.' }));
      }
      current.parameters.forEach(function (p, i) {
        var values = m.variables.UMAT_PARAMETERS || [];
        var input = textInput(number(values[i]), function (text) {
          var parsed = P.parse(text);
          if (typeof parsed !== 'number') {
            say(p.label + ' must be a number.');
            draw();
            return;
          }
          attempt(function () {
            var list = (m.variables.UMAT_PARAMETERS || []).slice();
            list[i] = parsed;
            m.variables.UMAT_PARAMETERS = list;
          });
          draw();
        }, { 'data-udsm-parameter': p.key });
        grid.appendChild(field(p.label, input, S.udsmUnit(p, system),
                               p.name + ' (UMAT_PARAMETERS, entry ' + (i + 1) + ')'));
      });
    }

    /* The grid is rebuilt whole; where it was scrolled to is kept, so a choice that
       lists more or less does not throw the window back to the top. */
    function draw() {
      var scrolled = grid.scrollTop, outer = grid.parentNode, outerScrolled = outer ? outer.scrollTop : 0;
      fill();
      grid.scrollTop = scrolled;
      if (outer) outer.scrollTop = outerScrolled;
    }

    function fill() {
      App.UI.clear(grid);
      grid.appendChild(el('h4', { text: 'General' }));
      grid.appendChild(field('Identification', textInput(m.name, function (v) {
        attempt(function () { m.name = v.trim(); });
        if (title) title.textContent = 'Soil material — ' + m.name;
      }, { 'data-field': 'name' })));
      var colour = el('input', { type: 'color', value: m.color, 'data-field': 'color' });
      colour.addEventListener('input', function () { attempt(function () { m.color = colour.value; }); });
      grid.appendChild(field('Colour', colour));

      var model = other ? S.OTHER : S.modelOf(m.constitutive_law);
      var models = S.order().map(function (id) { return { value: id, text: S.label(id) }; })
        .concat([{ value: S.OTHER, text: 'Other (type a law name)' }]);
      var modelRow = field('Soil model', select(models, model, { 'data-field': 'soil-model' },
        function (chosen) {
          other = chosen === S.OTHER;
          if (other) { say('Type the name of the Kratos law below.', true); draw(); return; }
          choose(function () { setLaw(S.law(chosen, dimension())); });
        }));
      // A model's law follows from the model and the dimension: named on hover, not shown.
      if (!other) modelRow.title = m.constitutive_law;
      grid.appendChild(modelRow);
      if (model === S.UDSM) udsmRows();
      if (other) {
        var laws = el('datalist', { id: 'material-laws' });
        S.order().forEach(function (id) {
          [S.law(id, 2), S.law(id, 3)].forEach(function (law) {
            laws.appendChild(el('option', { value: law }));
          });
        });
        grid.appendChild(laws);
        grid.appendChild(field('Constitutive law', textInput(m.constitutive_law, function (v) {
          var law = v.trim();
          if (choose(function () { setLaw(law); })) {
            other = S.modelOf(m.constitutive_law) === S.OTHER;
            draw();
          }
        }, { list: 'material-laws', 'data-field': 'constitutive_law' })));
      }

      // What the export derives where the soil is silent, and what follows from its
      // numbers: shown with the parameters they belong to.
      var system = App.Units.current(), flow = flowProject(), water = waterVariables();
      var derived = S.derived(m.constitutive_law, m.variables, water, system, flow);
      var computed = S.computed(m.constitutive_law, m.variables, water, system, flow,
                                projectGravity());
      function after(names) {
        names.forEach(function (name) {
          if (computed[name] !== undefined) grid.appendChild(computedRow(name, computed[name]));
        });
      }
      S.groups(model, m.variables, flow).forEach(function (group) {
        grid.appendChild(el('h4', { text: group.title }));
        group.parameters.forEach(function (p) {
          grid.appendChild(parameterRow(p, derived));
          if (/^PERMEABILITY_(XX|YY)$/.test(p.name)) after(['HYDRAULIC_CONDUCTIVITY_' + p.name.slice(-2)]);
        });
        if (group.title === 'Weight') after(['UNIT_WEIGHT_DRY', 'UNIT_WEIGHT_SATURATED']);
      });

      // A model lists all it reads. What else the soil carries -- from an older project,
      // or the command line -- is named in one line, given no fields, and can be left
      // out; nothing is added to it here. A law of no model is the user's own: its
      // variables are typed and added freely.
      var parameters = S.reads(model);
      var rest = Object.keys(m.variables).filter(function (n) { return parameters.indexOf(n) < 0; });
      if (!other && rest.length) {
        grid.appendChild(el('div.pgrid-row', { 'data-unread': rest.join(' '),
          title: 'Written into the deck as they stand; ' + S.label(model) + ' does not read them.' }, [
          el('div.pgrid-key', { text: 'Not read by ' + S.label(model) }),
          el('div.pgrid-val.readonly.field', null, [
            el('span.computed-value', { text: rest.join(', ') }),
            el('button.btn.btn-sm', { text: 'Leave out', type: 'button', 'data-action': 'leave-out-unread',
              onclick: function () {
                attempt(function () { rest.forEach(function (name) { delete m.variables[name]; }); });
                draw();
              } })])]));
      }
      if (other) {
        grid.appendChild(el('h4', { text: 'Variables' }));
        rest.forEach(function (name) { grid.appendChild(typedRow(name)); });
        var names = el('datalist', { id: 'kratos-variables' });
        Object.keys(App.UNIT_TABLE.variables).forEach(function (n) {
          if (S.WATER.indexOf(n) < 0) names.appendChild(el('option', { value: n }));
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
      }

      // Rinter reduces the strength a Coulomb contact takes from the soil. A linear
      // elastic soil has none to give: a Coulomb contact against it sets its own, in the
      // interface's properties (core/kratos/materials.py), so there is nothing to reduce.
      grid.appendChild(el('h4', { text: 'Interfaces' }));
      if (model === 'linear_elastic') {
        var why = 'A linear elastic soil has no strength to give a contact. A Coulomb ' +
                  'contact against it sets its own cohesion and friction angle: select ' +
                  'the interface, and under Contact set Strength to Set on the interface.';
        grid.appendChild(el('div.pgrid-row', { 'data-field': 'no-strength', title: why }, [
          el('div.pgrid-key', { text: 'Strength' }),
          el('div.pgrid-val.readonly.field', null, [
            el('span.computed-value', { text: 'None to give — a Coulomb contact sets its own' }),
            el('span.remove-slot')])]));
      } else {
        grid.appendChild(field('Rinter', textInput(String(m.rInter), function (v) {
          var r = Number(v);
          if (!(r > 0 && r <= 1)) { say('Rinter must be above 0 and at most 1.'); draw(); return; }
          attempt(function () { m.rInter = r; });
        }, { 'data-field': 'rInter' })));
      }
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
      title: 'Soil material — ' + m.name + (library ? ' (library)' : ''), width: 600, height: 620,
      buttons: library ? [{ label: 'Add to project', primary: true, onClick: library.onAdd },
                          { label: 'Close' }]
                       : [{ label: 'Close', primary: true }],
      build: function (root, ctx) {
        title = ctx && ctx.dialog ? ctx.dialog.querySelector('.dlg-title') : null;
        var wrap = el('div.dlg-simple', { style: 'display:flex;flex-direction:column;padding:0' });
        grid = el('div.pgrid.material-variables', { style: 'flex:1;overflow:auto' });
        hint = el('div.lay-hint', { text: DEFAULT });
        wrap.appendChild(grid);
        wrap.appendChild(hint);
        root.appendChild(wrap);
        draw();
        say(library && library.notes && library.notes.length ? library.notes.join(' ') : null,
            true);
      }
    });
  }

  return { open: open, editor: editor, newMaterial: newMaterial, blankSoil: blankSoil,
           createSoil: createSoil, missing: missing,
           addMaterial: addMaterial, duplicateMaterial: duplicateMaterial };
})();

/* Installed over the frozen helpers before patches.js wraps the dialog with its save. */
if (App.Dialogs) App.Dialogs.materials = App.MaterialSets.open;
App.addMaterial = App.MaterialSets.addMaterial;
App.duplicateMaterial = App.MaterialSets.duplicateMaterial;
App.newMaterialDefaults = App.MaterialSets.newMaterial;
