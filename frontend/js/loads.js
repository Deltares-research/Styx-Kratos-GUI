/* Dimension-native Structure-mode loads. 2D records contain x/z only; the active
   section supplies the display plane. 3D surface records contain x/y extents. */

var App = window.App || {};

App.Loads = (function () {

  /* How far the model reaches, which is not the same as the domain: a drawn
     or imported part may stand above `y_top`, and a structure placed on one is on
     model geometry. `App.Model.extentOf` mirrors the server's `Project.extent`; the
     fallback keeps this module usable in a page that has no App.Model. */
  function extent(project) {
    return (App.Model && App.Model.extentOf)
      ? App.Model.extentOf(project)
      : (project && project.domain);
  }

  function copy(value) { return JSON.parse(JSON.stringify(value)); }

  function collection() { return App.LOADS || []; }

  function compatible(load, project) {
    return !!load && !!project && (project.dimension === 2
      ? load.kind === 'point' || load.kind === 'line'
      : load.kind === 'surface');
  }

  function storedCollection() {
    return (App.PROJECT && App.PROJECT.loads) || collection();
  }

  function nextNumber(project) {
    var used = {};
    ((project && project.loads) || collection()).forEach(function (load) { used[load.id] = true; });
    var number = 1;
    while (used['load_' + number]) number += 1;
    return number;
  }

  function draftFromPoints(project, points) {
    if (!project || !project.domain || !points || points.length !== 2) {
      throw new Error('A load needs exactly two picked corners.');
    }
    var a = points[0], b = points[1], d = project.domain;
    var x0, x1, z0, z1;
    if (project.dimension === 2) {
      x0 = Math.min(a[0], b[0]); x1 = Math.max(a[0], b[0]);
      if (!(x1 > x0)) throw new Error('The load must have a non-zero width.');
      var span = extent(project);
      if (x0 < span.x0 || x1 > span.x1) {
        throw new Error('The load interval must stay inside the model domain.');
      }
      var lineNumber = nextNumber(project);
      return {
        id: 'load_' + lineNumber, name: 'LineLoad_' + lineNumber, kind: 'line',
        // The top of the model, not of the layer block: a load drawn on a raised
        // embankment belongs on it, and one left at `domain.y_top` would sit buried
        // inside the fill and would not translate to a surface load (core/
        // loads.py compares against `Project.ground_y`).
        x0: x0, x1: x1, y: span.y_top, thickness: 0.15,
        components: [0, -App.Units.fromSI(20000, 'line force', App.Units.system(project))],
        distribution: 'Uniform', active: true
      };
    } else {
      x0 = Math.min(a[0], b[0]); x1 = Math.max(a[0], b[0]);
      z0 = Math.min(a[1], b[1]); z1 = Math.max(a[1], b[1]);
    }
    if (!(x1 > x0) || !(z1 > z0)) throw new Error('The load must have a non-zero width.');
    if (x0 < d.x0 || x1 > d.x1 || z0 < d.z0 || z1 > d.z1) {
      throw new Error('The load footprint must stay inside the model domain.');
    }
    var number = nextNumber(project);
    return {
      id: 'load_' + number,
      name: (project.dimension === 2 ? 'LineLoad_' : 'SurfaceLoad_') + number,
      kind: 'surface',
      // The elevation is carried, not rederived: the server places the pad from it
      // (`Project.elevation_of`), and rederiving from a gmsh bounding box is padded
      // by 1e-7 and lands just above the face it should imprint.
      x0: x0, x1: x1, z0: z0, z1: z1, y: extent(project).y_top,
      thickness: 0.15,
      // 20 kN/m2 down, in the project's units.
      components: [0, -App.Units.fromSI(20000, 'stress', App.Units.system(project)), 0],
      distribution: 'Uniform', active: true
    };
  }

  function draftPoint(project, coordinate) {
    if (!project || project.dimension !== 2 || !project.domain || !coordinate ||
        coordinate.length !== 2 || !coordinate.every(Number.isFinite)) {
      throw new Error('A 2D point load needs one finite x-y coordinate.');
    }
    var d = project.domain;
    var span = extent(project);
    if (coordinate[0] < span.x0 || coordinate[0] > span.x1 ||
        coordinate[1] < span.y_bottom || coordinate[1] > span.y_top) {
      throw new Error('The point-load coordinate must stay inside the model domain.');
    }
    var number = nextNumber(project);
    return {
      id: 'load_' + number, name: 'PointLoad_' + number, kind: 'point',
      x: coordinate[0], y: coordinate[1], thickness: 0.25,
      components: [0, -App.Units.fromSI(20000, 'force', App.Units.system(project))],
      distribution: 'Uniform', active: true
    };
  }

  function draftSurface(project) {
    if (!project || project.dimension !== 3 || !project.domain) {
      throw new Error('A surface load needs a 3D model domain.');
    }
    var d = project.domain;
    var dx = d.x1 - d.x0, dz = d.z1 - d.z0;
    return draftFromPoints(project, [
      [d.x0 + dx * 0.4, d.z0 + dz * 0.4],
      [d.x0 + dx * 0.6, d.z0 + dz * 0.6]
    ]);
  }

  function validate(load) {
    if (!load.name || !load.name.trim()) return 'Name cannot be empty.';
    if (load.kind === 'point') {
      if (![load.x, load.y].every(Number.isFinite)) {
        return 'Every point-load coordinate must be a number.';
      }
    } else if (load.kind === 'line') {
      if (!(load.x1 > load.x0) || !Number.isFinite(load.y)) {
        return 'The line load must have a non-zero width and finite y coordinate.';
      }
    } else if (!(load.x1 > load.x0) || !(load.z1 > load.z0)) {
      return 'The load must have a non-zero width.';
    }
    if (!(load.thickness > 0)) return 'Indicator thickness must be greater than zero.';
    if (!load.components.every(function (value) { return Number.isFinite(value); })) {
      return 'Every load component must be a number.';
    }
    return null;
  }

  function available(kind, project) {
    if (!project) return false;
    return project.dimension === 2
      ? kind === 'point' || kind === 'line'
      : kind === 'surface';
  }

  function save(load) {
    var problem = validate(load);
    if (problem) return Promise.reject(new Error(problem));
    var loads = copy(storedCollection());
    var at = loads.findIndex(function (item) { return item.id === load.id; });
    if (at < 0) loads.push(copy(load)); else loads[at] = copy(load);

    return App.Api.patch('/api/project/structures', { loads: loads })
      .then(function (response) {
        App.Model.apply(response.project);
        return App.Viewport.refresh();
      })
      .then(function () {
        if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
        if (App.selectObject) App.selectObject(load.id, 'tree');
        if (App.Command && App.Command.ok) App.Command.ok('Saved load ' + load.name + '.');
        return load;
      })
      .catch(function (error) {
        var rollback = App.Model && App.Model.load ? App.Model.load() : Promise.resolve();
        return rollback
          .then(function () {
            return App.Viewport && App.Viewport.refresh ? App.Viewport.refresh() : null;
          })
          .then(function () {
            if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
            if (App.Command && App.Command.err) {
              App.Command.err('Could not save load: ' + error.message);
            }
            throw error;
          }, function () {
            if (App.Command && App.Command.err) {
              App.Command.err('Could not save load: ' + error.message);
            }
            throw error;
          });
      });
  }

  function remove(id) {
    var load = collection().filter(function (item) { return item.id === id; })[0];
    if (!load) return Promise.resolve(false);
    var loads = copy(storedCollection()).filter(function (item) { return item.id !== id; });
    return App.Api.patch('/api/project/structures', { loads: loads })
      .then(function (response) {
        App.Model.apply(response.project);
        if (App.state && App.state.selection === id && App.selectObject) App.selectObject(null);
        return App.Viewport.refresh();
      })
      .then(function () {
        if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
        if (App.Command && App.Command.ok) App.Command.ok('Deleted load ' + load.name + '.');
        return true;
      });
  }

  function start(kind) {
    if (!App.PROJECT) return;
    kind = kind || (App.PROJECT.dimension === 2 ? 'line' : 'surface');
    if (!available(kind, App.PROJECT)) {
      if (App.Command) App.Command.note(
        kind === 'surface'
          ? 'Surface loads are available only in 3D mode.'
          : 'Point and line loads are available only in 2D mode.'
      );
      return;
    }
    var d = App.PROJECT.domain;
    try {
      // A 2D record is dimension-native `(x, y)`: the section's own two axes, which
      // are the world's X and Y.
      open(kind === 'point' ? draftPoint(App.PROJECT, [
        (d.x0 + d.x1) / 2, d.y_top
      ]) : (kind === 'line' ? draftFromPoints(App.PROJECT, [
        [d.x0 + (d.x1 - d.x0) * 0.4, d.y_top],
        [d.x0 + (d.x1 - d.x0) * 0.6, d.y_top]
      ]) : draftSurface(App.PROJECT)), kind);
    } catch (error) {
      if (App.Command && App.Command.err) App.Command.err(error.message);
    }
  }

  function pick(kind) {
    App.DrawInput.start('load', {
      count: kind === 'point' ? 1 : 2,
      pointLoad: kind === 'point',
      onComplete: function (points) {
        try {
          open(kind === 'point' ? draftPoint(App.PROJECT, [points[0][0], points[0][1]])
                                : draftFromPoints(App.PROJECT, points), kind);
        } catch (error) {
          if (App.Command && App.Command.err) App.Command.err(error.message);
        }
      }
    });
  }

  function input(value, step) {
    return App.UI.el('input.mesh-setting-control', {
      type: 'number', step: step || '0.1', value: String(value)
    });
  }

  function open(source, authoringKind) {
    if (!App.Dialogs || !App.Dialogs.open) return;
    var load = copy(source);
    var displayKind = authoringKind || (load.kind === 'point' ? 'point'
      : (App.PROJECT.dimension === 2 ? 'line' : 'surface'));
    var el = App.UI.el, controls = {};
    var shell;

    function submit() {
      load.name = controls.name.value.trim();
      ['x0', 'x1', 'z0', 'z1', 'thickness'].forEach(function (key) {
        if (controls[key]) load[key] = Number(controls[key].value);
      });
      ['x', 'y'].forEach(function (key) {
        if (!controls[key]) return;
        /* A surface load's y is optional: blank means "the top of the model", which
           the server resolves against ground_y (SurfaceLoad.y). Number('') is 0, so
           reading it like the others would quietly drop the pad to datum. A point or
           line load left blank becomes null too, and validate() refuses it there. */
        var raw = controls[key].value.trim();
        load[key] = raw === '' ? null : Number(raw);
      });
      load.components.forEach(function (_, axis) {
        load.components[axis] = Number(controls['q' + axis].value);
      });
      load.active = controls.active.checked;
      var problem = validate(load);
      if (problem) {
        message.textContent = problem;
        return;
      }
      save(load).then(function () { shell.close(); }, function (error) {
        message.textContent = error.message;
      });
    }

    shell = App.Dialogs.open({
      title: (source.id && collection().some(function (item) { return item.id === source.id; }))
        ? 'Edit ' + displayKind + ' load'
        : 'Create ' + displayKind + ' load',
      width: 590, height: App.PROJECT.dimension === 2 ? 430 : 540,
      buttons: [
        { label: 'Pick on model…', onClick: function () { pick(load.kind); } },
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
        controls.name = el('input.mesh-setting-control', { type: 'text', value: load.name });
        row('Name', controls.name, 'Shown in the Model explorer and Kratos submodel part.');

        if (load.kind === 'point') {
          controls.x = input(load.x); controls.y = input(load.y);
          row('x', controls.x, 'World x coordinate [m].');
          row('y', controls.y, 'World y coordinate, the elevation [m].');
        } else if (load.kind === 'line') {
          controls.x0 = input(load.x0); controls.x1 = input(load.x1); controls.y = input(load.y);
          row('x min', controls.x0, 'Start of the loaded interval [m].');
          row('x max', controls.x1, 'End of the loaded interval [m].');
          row('y', controls.y, 'Elevation of the loaded interval [m].');
        } else {
          controls.x0 = input(load.x0); controls.x1 = input(load.x1);
          controls.z0 = input(load.z0); controls.z1 = input(load.z1);
          row('x min', controls.x0, 'Start of the loaded footprint.');
          row('x max', controls.x1, 'End of the loaded footprint.');
          controls.y = input(Number.isFinite(load.y) ? load.y : '');
          row('y', controls.y, 'Elevation of the pad [m]. Blank puts it on top of the model.');
          row('z min', controls.z0, 'Front edge of the surface load.');
          row('z max', controls.z1, 'Back edge of the surface load.');
        }
        controls.thickness = input(load.thickness, '0.01');
        row('Indicator thickness', controls.thickness, 'Display only; it does not enter the FE mesh.');

        controls.q0 = input(load.components[0]);
        controls.q1 = input(load.components[1]);
        if (load.kind === 'surface') controls.q2 = input(load.components[2]);
        var unit = App.Units.label({ point: 'force', line: 'line force' }[load.kind] || 'stress');
        row('qx', controls.q0, 'World x component [' + unit + '].');
        row('qy', controls.q1, 'World y component [' + unit + ']; downward is negative.');
        if (load.kind === 'surface') {
          row('qz', controls.q2, 'World z component [' + unit + '].');
        }

        controls.active = el('input.mesh-setting-control', { type: 'checkbox' });
        controls.active.checked = load.active !== false;
        row('Active', controls.active, 'Inactive loads remain in the project but are not exported.');
        message = el('div.mesh-settings-message');
        row('', message, '');
      }
    });
    var message;
  }

  function edit(id) {
    var load = collection().filter(function (item) { return item.id === id; })[0];
    if (load) open(load);
  }

  function isLoadKey(key) {
    return collection().some(function (load) { return load.id === key; });
  }

  return {
    draftFromPoints: draftFromPoints, draftPoint: draftPoint, draftSurface: draftSurface,
    validate: validate, available: available, compatible: compatible,
    start: start, pick: pick, open: open, edit: edit, save: save, remove: remove,
    isLoadKey: isLoadKey
  };
})();
