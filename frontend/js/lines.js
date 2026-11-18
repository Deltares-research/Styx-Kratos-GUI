/* ══════════════════════════════════════════════════════════════════
   lines.js — the lines that split the soil.

   A line is a polyline in the 2D section. Where it crosses a soil layer from one edge to
   another, the layer becomes separate soil bodies, each its own part of the model: a
   stage can switch one off, and one can have a material of its own. A sheet pile cuts the
   soil the same way. Which bodies there are is the server's to say
   (core/model/regions.py, `Project.soil_bodies`): the project publishes them, and this
   file only edits the lines.

   Drawn or typed: the Create line tool draws, its flyout's "Line by coordinates…" opens
   the same window with no drawing first, and the points stay editable in both places.
   `kratos-cli line` is the same edit.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Lines = (function () {

  function copy(value) { return JSON.parse(JSON.stringify(value)); }

  function stored() { return (App.PROJECT && App.PROJECT.lines) || []; }

  /* Authored in the 2D section; a solid model has the same lines, swept across z. */
  function available(project) { return !!project && project.dimension === 2; }

  var UNAVAILABLE = 'A line is drawn in the 2D section; switch to 2D to create one.';

  function nextNumber(lines) {
    var used = {};
    (lines || []).forEach(function (line) { used[line.id] = true; });
    var number = 1;
    while (used['line_' + number]) number += 1;
    return number;
  }

  /* A new line along `points`, or across the middle of the section (`drafts.line`). */
  function draft(project, points) {
    if (!available(project)) throw new Error(UNAVAILABLE);
    var number = nextNumber(project.lines);
    var d = project.domain;
    return {
      id: 'line_' + number,
      name: 'Line ' + number,
      points: points ? copy(points) : [[d.x0, (d.y_top + d.y_bottom) / 2],
                                       [d.x1, (d.y_top + d.y_bottom) / 2]]
    };
  }

  function validate(record) {
    if (!record.name || !record.name.trim()) return 'Name cannot be empty.';
    var points = record.points || [];
    if (points.length < 2) return 'A line needs at least two points.';
    for (var i = 0; i < points.length; i += 1) {
      if (points[i].length !== 2 || !points[i].every(Number.isFinite)) {
        return 'Every coordinate must be a number.';
      }
      if (i && points[i][0] === points[i - 1][0] && points[i][1] === points[i - 1][1]) {
        return 'A line cannot repeat the same point twice.';
      }
    }
    return null;
  }

  /* The whole list, as the structures and conditions routes take theirs: the server
     validates the project as one transaction and works out the bodies. `edit_notes`
     (a line that splits no soil) reaches the log through App.Api. */
  function patch(lines, describe) {
    return App.Api.patch('/api/project/lines', { lines: lines })
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
            App.Command.err('Could not save the line: ' + error.message);
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
    var all = copy(stored());
    var at = all.findIndex(function (item) { return item.id === record.id; });
    if (at < 0) all.push(copy(record)); else all[at] = copy(record);
    return patch(all, 'Saved line ' + record.name + '.').then(function () {
      if (App.selectObject) App.selectObject(record.id, 'tree');
      return record;
    });
  }

  function remove(id) {
    var record = stored().filter(function (item) { return item.id === id; })[0];
    if (!record) return Promise.resolve(false);
    if (App.state && App.state.selection === id && App.selectObject) App.selectObject(null);
    return patch(copy(stored()).filter(function (item) { return item.id !== id; }),
                 'Deleted line ' + record.name + '.');
  }

  /* Click the points, then right-click or Enter; "x y" in the command box places one too
     (App.DrawInput). The window opens on what was drawn, to read and correct. */
  function pick(source) {
    if (!App.DrawInput || !App.DrawInput.start) return;
    App.DrawInput.start('line', {
      onComplete: function (points) {
        var drawn = points.map(function (point) { return [point[0], point[1]]; });
        var record = source ? copy(source) : draft(App.PROJECT);
        record.points = drawn;
        open(record);
      }
    });
  }

  function open(source) {
    if (!App.Dialogs || !App.Dialogs.open) return;
    var record = copy(source);
    var el = App.UI.el;
    var shell, message, name, points;

    function submit() {
      record.name = name.value.trim();
      record.points = points.read();
      var problem = validate(record);
      if (problem) { message.textContent = problem; return null; }
      return save(record).then(function () { shell.close(); }, function (error) {
        message.textContent = error.message;
      });
    }

    var known = stored().some(function (item) { return item.id === source.id; });
    shell = App.Dialogs.open({
      title: (known ? 'Edit' : 'Create') + ' line',
      width: 590, height: 440,
      buttons: [
        { label: 'Pick on model…', onClick: function () { pick(record); } },
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
        name = el('input.mesh-setting-control', { type: 'text', value: record.name });
        row('Name', name, 'Shown in the Model explorer.');

        points = App.PointList.build(record.points);
        row('Points', points.element,
            'x and y [m], in order. Where the line crosses a soil layer from one edge to '
            + 'another, the layer becomes separate soil parts. A part of the line that ends '
            + 'inside the soil splits nothing.');

        message = el('div.mesh-settings-message');
        row('', message, '');
      }
    });
  }

  /* The rail button: draw. In 3D, say why not. */
  function start() {
    if (!available(App.PROJECT)) {
      if (App.Command) App.Command.note(UNAVAILABLE);
      return;
    }
    return pick();
  }

  /* The flyout's "Line by coordinates…": the same window, on a line across the section. */
  function typed() {
    if (!available(App.PROJECT)) {
      if (App.Command) App.Command.note(UNAVAILABLE);
      return;
    }
    return open(draft(App.PROJECT));
  }

  function edit(id) {
    var record = stored().filter(function (item) { return item.id === id; })[0];
    if (record) return open(record);
  }

  function isLineKey(key) {
    return stored().some(function (record) { return record.id === key; });
  }

  /* ── Soil bodies ───────────────────────────────────────────────────────────────── */

  /* A body's key: `soil_<layer>__<id>`, or `<part>__<id>` for a piece of a drawn soil
     surface (core/model/schemas.py `SoilBody.key`). */
  function bodyKey(body) {
    return (body.part ? body.part : 'soil_' + body.layer) + '__' + body.id;
  }

  function bodyOf(key) {
    var published = (App.PROJECT && App.PROJECT.bodies) || [];
    return published.filter(function (body) { return bodyKey(body) === key; })[0];
  }

  /* A body's name and its material; `mat: null` goes back to the layer's or the
     surface's. */
  function saveBody(key, fields) {
    return App.Api.patch('/api/project/bodies/' + encodeURIComponent(key), fields)
      .then(function (response) {
        App.Model.apply(response.project);
        return App.Viewport.refresh();
      })
      .then(function () {
        if (App.Explorer && App.state) {
          App.Explorer.mountTree(App.state.mode);
          App.Explorer.mountSelection(key);
        }
        return true;
      })
      .catch(function (error) {
        if (App.Command && App.Command.err) {
          App.Command.err('Could not save the soil part: ' + error.message);
        }
        throw error;
      });
  }

  return {
    available: available, draft: draft, validate: validate,
    save: save, remove: remove, start: start, typed: typed, pick: pick, open: open,
    edit: edit, isLineKey: isLineKey,
    bodyKey: bodyKey, bodyOf: bodyOf, saveBody: saveBody
  };
})();
