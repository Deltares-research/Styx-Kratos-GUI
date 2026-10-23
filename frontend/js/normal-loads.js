/* ══════════════════════════════════════════════════════════════════
   normal-loads.js — Structure-mode normal loads.

   A normal load is a pressure applied perpendicular to a free polyline -- an
   exposed excavation face, a sloped boundary -- rather than the fixed x/y
   vector a LineLoad carries on a flat horizontal run. The server embeds the
   polyline the same way it embeds a free interface's (core/geometry/solid_model.py's
   `_embed_beams`) and writes Kratos' ApplyNormalLoadTableProcess for it
   (core/kratos/parameters.py).

   Two ways to size one, picked by `fluid_pressure_type`:

     • "Hydrostatic" derives the pressure from a water level, zero at that
       level and increasing with depth -- the usual case for an exposed
       excavation face (a staged excavation's WaterLoad_StageN arrangement).
       The level is the load's own `reference_coordinate`, which a new load is
       given from the project's water level; one saved before it had one reads
       the project's at export.
     • "Uniform" applies a fixed `pressure` everywhere along the line instead,
       for a load that is not water.

   Plane strain only, like a free interface -- see NORMAL_LOAD_CONDITIONS in
   core/kratos/writer.py.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.NormalLoads = (function () {

  var FLUID_PRESSURE_TYPES = ['Uniform', 'Hydrostatic'];

  function copy(value) { return JSON.parse(JSON.stringify(value)); }

  function collection() { return App.NORMAL_LOADS || []; }

  function storedNormalLoads() {
    return (App.PROJECT && App.PROJECT.normal_loads) || collection();
  }

  function storedLoads() {
    return (App.PROJECT && App.PROJECT.loads) || [];
  }

  /* Authored in the 2D x-y section and nowhere else, for the same reason a
     free interface is: that is the plane the condition it writes describes. */
  function available(project) {
    return !!project && project.dimension === 2;
  }

  function unavailableMessage(project) {
    return project && project.dimension === 2
      ? 'Normal loads are created in the 2D x-y section.'
      : 'A normal load is a plane-strain object; switch to 2D to create one.';
  }

  function nextId(list, prefix) {
    var used = {};
    (list || []).forEach(function (item) { used[item.id] = true; });
    var number = 1;
    while (used[prefix + number]) number += 1;
    return prefix + number;
  }

  /* A free line down the middle of the section, the same default a free
     interface gets when there is no pile to follow -- the user then edits
     each point's x/y in the explorer. `options.hydrostatic` makes it hydrostatic,
     with the project's water level copied in as its own (`drafts.normal_load`). */
  function draft(project, options) {
    options = options || {};
    if (!available(project)) throw new Error(unavailableMessage(project));
    var id = nextId(project.normal_loads || [], 'normalload_');
    var d = project.domain;
    var x = d.x0 + (d.x1 - d.x0) * 0.5;
    var record = {
      id: id,
      name: 'Normal load ' + id.slice('normalload_'.length),
      kind: 'normal',
      points: [[x, d.y_top], [x, d.y_top - (d.y_top - d.y_bottom) * 0.5]],
      // Uniform unless asked, so the magnitude asked for on the form is the magnitude
      // applied. Hydrostatic derives its pressure from a water level and ignores that
      // number, which is not something to default anyone into.
      fluid_pressure_type: options.hydrostatic ? 'Hydrostatic' : 'Uniform',
      pressure: 0.0,
      active: true
    };
    // Set only when there is one, as the Python twin leaves the field unset.
    if (options.hydrostatic && project.water) record.reference_coordinate = project.water.y;
    return record;
  }

  function validate(record) {
    if (!record.name || !record.name.trim()) return 'Name cannot be empty.';
    if (FLUID_PRESSURE_TYPES.indexOf(record.fluid_pressure_type) < 0) {
      return 'A normal load must be Uniform or Hydrostatic.';
    }
    if (!Number.isFinite(record.pressure)) return 'The pressure must be a number.';
    var points = record.points || [];
    if (points.length < 2) return 'A normal load needs at least two points.';
    for (var i = 0; i < points.length; i += 1) {
      if (points[i].length !== 2 || !points[i].every(Number.isFinite)) {
        return 'Every coordinate must be a number.';
      }
      if (i && points[i][0] === points[i - 1][0] && points[i][1] === points[i - 1][1]) {
        return 'A normal load cannot repeat the same point twice.';
      }
    }
    return null;
  }

  /* Every write goes through the one structures endpoint, carrying the loads
     unchanged: the server validates the whole project as one transaction, the
     same path a free interface's save takes. */
  function patch(body, describe) {
    return App.Api.patch('/api/project/structures', body)
      .then(function (response) {
        App.Model.apply(response.project);
        return App.Viewport.refresh();
      })
      .then(function () {
        if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
        if (App.Command && App.Command.ok) App.Command.ok(describe);
        return true;
      })
      .catch(function (error) {
        var rollback = App.Model && App.Model.load ? App.Model.load() : Promise.resolve();
        function report() {
          if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
          if (App.Command && App.Command.err) {
            App.Command.err('Could not save normal load: ' + error.message);
          }
          throw error;
        }
        return rollback
          .then(function () {
            return App.Viewport && App.Viewport.refresh ? App.Viewport.refresh() : null;
          })
          .then(report, report);
      });
  }

  function save(record) {
    var problem = validate(record);
    if (problem) return Promise.reject(new Error(problem));
    var all = copy(storedNormalLoads());
    var at = all.findIndex(function (item) { return item.id === record.id; });
    if (at < 0) all.push(copy(record)); else all[at] = copy(record);

    return patch({ loads: copy(storedLoads()), normal_loads: all },
                 'Saved normal load ' + record.name + '.')
      .then(function () {
        if (App.selectObject) App.selectObject(record.id, 'tree');
        return record;
      });
  }

  function remove(id) {
    var record = collection().filter(function (item) { return item.id === id; })[0];
    if (!record) return Promise.resolve(false);
    var all = copy(storedNormalLoads()).filter(function (item) { return item.id !== id; });
    if (App.state && App.state.selection === id && App.selectObject) App.selectObject(null);
    return patch({ loads: copy(storedLoads()), normal_loads: all },
                 'Deleted normal load ' + record.name + '.');
  }

  function input(value, step) {
    return App.UI.el('input.mesh-setting-control', {
      type: 'number', step: step || '0.1', value: String(value)
    });
  }

  /* Two clicks in the section, the same way a line load is picked. A polyline of
     more than two points is edited point by point in the explorer afterwards --
     there is no multi-point sketch tool here, and a free interface has none either. */
  function pick() {
    if (!App.DrawInput || !App.DrawInput.start) return;
    App.DrawInput.start('load', {
      count: 2,
      onComplete: function (points) {
        var record = draft(App.PROJECT);
        record.points = points.map(function (point) { return [point[0], point[1]]; });
        open(record);
      }
    });
  }

  /* The same form a line load gets (frontend/js/loads.js): where it is, how big it is,
     and whether it counts -- asked once when the load is made, and reachable again
     from the explorer. Everything on it is editable in the properties panel too, so
     nothing here is the only way to set a field. */
  function open(source) {
    if (!App.Dialogs || !App.Dialogs.open) return;
    var record = copy(source);
    var el = App.UI.el, controls = { xs: [], ys: [] };
    var shell, message;

    function submit() {
      record.name = controls.name.value.trim();
      record.points = controls.xs.map(function (control, index) {
        return [Number(control.value), Number(controls.ys[index].value)];
      });
      record.fluid_pressure_type = controls.type.value;
      var level = controls.level.value.trim();
      if (record.fluid_pressure_type === 'Hydrostatic') {
        if (level !== '') record.reference_coordinate = Number(level);
        else if (App.PROJECT && App.PROJECT.water) {
          record.reference_coordinate = App.PROJECT.water.y;
        } else {
          message.textContent = 'Give the level where the pressure is zero: the model has '
            + 'no water level to take it from.';
          return null;
        }
        if (!Number.isFinite(record.reference_coordinate)) {
          message.textContent = 'The reference level must be a number.';
          return null;
        }
      }
      // Asked for every time, in either mode: a load whose magnitude was never given
      // is one nobody has finished describing, and Number('') would quietly read a
      // blank box as a load of zero.
      var pressure = controls.pressure.value.trim();
      if (pressure === '') {
        message.textContent = 'Give the load a pressure in ' + App.Units.label('stress') + '.';
        return null;
      }
      record.pressure = Number(pressure);
      record.active = controls.active.checked;
      var problem = validate(record);
      if (problem) { message.textContent = problem; return null; }
      // Returned, not just started: the caller -- a test, or a button that wants to
      // know -- can wait for the write instead of guessing when it landed.
      return save(record).then(function () { shell.close(); }, function (error) {
        message.textContent = error.message;
      });
    }

    var known = collection().some(function (item) { return item.id === source.id; });
    shell = App.Dialogs.open({
      title: (known ? 'Edit' : 'Create') + ' normal load',
      width: 590, height: 470,
      buttons: [
        { label: 'Pick on model…', onClick: function () { pick(); } },
        { label: 'Save', primary: true, keepOpen: true, onClick: submit },
        { label: 'Cancel' }
      ],
      build: function (body) {
        body.classList.add('mesh-settings-body');
        var form = el('div.mesh-settings-form');
        body.appendChild(form);
        function row(label, control, help) {
          form.appendChild(el('label.mesh-setting-label', { text: label }));
          form.appendChild(control);
          form.appendChild(el('div.mesh-setting-help', { text: help || '' }));
        }

        controls.name = el('input.mesh-setting-control', { type: 'text', value: record.name });
        row('Name', controls.name, 'Shown in the Model explorer and Kratos submodel part.');

        (record.points || []).forEach(function (point, index) {
          var n = index + 1;
          var x = input(point[0]), y = input(point[1]);
          controls.xs.push(x);
          controls.ys.push(y);
          row('x' + n, x, n === 1 ? 'Start of the loaded line [m].'
                                  : 'Point ' + n + ' of the loaded line [m].');
          row('y' + n, y, 'Elevation of point ' + n + ' [m].');
        });

        controls.type = el('select.mesh-setting-control');
        [['Uniform', 'Uniform pressure'],
         ['Hydrostatic', 'Hydrostatic (from a water level)']].forEach(function (choice) {
          controls.type.appendChild(el('option', { value: choice[0], text: choice[1] }));
        });
        controls.type.value = record.fluid_pressure_type;
        row('Type', controls.type,
            'Uniform applies the pressure below. Hydrostatic ignores it and derives '
            + 'the pressure from the reference level instead, growing with depth.');


        // Blank on a new load rather than pre-filled with nought, so the magnitude is
        // something the user states rather than something they can walk past.
        controls.pressure = input(known ? record.pressure : (record.pressure || ''));
        row('Pressure', controls.pressure,
            'Required. Magnitude [' + App.Units.label('stress')
            + '], normal to the line, compression positive.');

        var water = App.PROJECT && App.PROJECT.water;
        controls.level = input(record.reference_coordinate !== undefined
                               && record.reference_coordinate !== null
                               ? record.reference_coordinate : (water ? water.y : ''));
        row('Reference level', controls.level,
            'Hydrostatic: the level where the pressure is zero [m]. Empty takes the '
            + 'water level, which the load then keeps as its own.');

        controls.active = el('input.mesh-setting-control', { type: 'checkbox' });
        controls.active.checked = record.active !== false;
        row('Active', controls.active,
            'Inactive loads remain in the project but are not exported.');

        message = el('div.mesh-settings-message');
        row('', message, '');
      }
    });
  }

  function length(record) {
    var points = (record && record.points) || [];
    var total = 0;
    for (var i = 1; i < points.length; i += 1) {
      var dx = points[i][0] - points[i - 1][0];
      var dz = points[i][1] - points[i - 1][1];
      total += Math.sqrt(dx * dx + dz * dz);
    }
    return total;
  }

  function start() {
    if (!App.PROJECT) return;
    if (!available(App.PROJECT)) {
      if (App.Command) App.Command.note(unavailableMessage(App.PROJECT));
      return;
    }
    var record;
    try {
      record = draft(App.PROJECT);
    } catch (error) {
      if (App.Command) App.Command.note(error.message);
      return;
    }
    // Asked for, not assumed: a load nobody has given a magnitude or a position is
    // not a load anyone meant, so the form opens before anything is written -- the
    // same order a line load is created in.
    return open(record);
  }

  function edit(id) {
    var record = collection().filter(function (item) { return item.id === id; })[0];
    if (!record) return;
    return open(record);
  }

  function isNormalLoadKey(key) {
    return collection().some(function (record) { return record.id === key; });
  }

  return {
    FLUID_PRESSURE_TYPES: FLUID_PRESSURE_TYPES,
    available: available, unavailableMessage: unavailableMessage,
    draft: draft, length: length,
    validate: validate,
    save: save, remove: remove, start: start, edit: edit,
    pick: pick, open: open,
    isNormalLoadKey: isNormalLoadKey
  };
})();
