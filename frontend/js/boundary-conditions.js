/* ══════════════════════════════════════════════════════════════════
   boundary-conditions.js — the boundary conditions.

   A boundary condition is a record of `Project.boundary_conditions`
   (core/model/schemas.py), and the deck holds these and no others: a project with
   no water pressure condition fixes no water pressure, and one with no support
   holds nothing still. Two kinds share one list, told apart by `kind`:

     • "displacement": the components `fixed` (x, y, z) held at zero, on a face, a
       soil part, a drawn line or a point;
     • "water_pressure": Kratos' `fluid_pressure_type` (Uniform, Hydrostatic,
       Phreatic_Multi_Line) on the whole soil, a face, a part, a line or a point.

   The target is two fields, the dialog's two questions: `on` (Whole soil / Face /
   Part / Line / Point), then the field it names (`face`, `part`, `points`).

   The drafts here are the twins of core/model/drafts.py's
   `displacement_condition`, `water_pressure_condition` and `standard_conditions`,
   held to them by tests/test_draft_parity.py. `command` answers `boundary` in the
   command box, with the words `kratos-cli boundary` takes. Every write is one
   `PATCH /api/project/conditions`. Gravity is not a condition: the initial stage's
   stress initialisation decides it (`core.model.stages.gravity`).
   The logic has no DOM in it; `open` and `openRecord` are the two windows.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.BoundaryConditions = (function () {
  'use strict';

  var FACES = ['bottom', 'left', 'right', 'front', 'back', 'top'];
  /* The faces a 2D section has: front and back bound the solid model along z only. */
  var SECTION_FACES = ['bottom', 'left', 'right', 'top'];
  /* The axis normal to each face (x 0, y 1, z 2): what a roller on it holds. */
  var FACE_NORMALS = { bottom: 1, top: 1, left: 0, right: 0, front: 2, back: 2 };
  var PRESSURE_TYPES = ['Uniform', 'Hydrostatic', 'Phreatic_Multi_Line'];
  var TARGETS = [['domain', 'Whole soil'], ['face', 'Face'], ['part', 'Part'],
                 ['line', 'Line'], ['point', 'Point']];
  var AXES = ['x', 'y', 'z'];
  /* The two groups of conditions, each with its own windows: the mechanical ones
     (supports) in Structures mode, the flow ones (water pressure, seepage face) in
     Flow conditions mode. */
  var GROUPS = {
    mechanical: { kinds: ['displacement'], title: 'Mechanical boundary conditions' },
    flow: { kinds: ['water_pressure', 'seepage'], title: 'Flow boundary conditions' }
  };
  var KIND_CHOICES = [['displacement', 'Support'], ['water_pressure', 'Water pressure'],
                      ['seepage', 'Seepage face']];

  /* The group a condition of `kind` belongs to. */
  function groupOf(kind) { return kind === 'displacement' ? 'mechanical' : 'flow'; }

  /* Whether a condition of `kind` is shown in the windows of `group` (all, with none). */
  function inGroup(kind, group) { return !GROUPS[group] || groupOf(kind) === group; }

  function copy(value) { return JSON.parse(JSON.stringify(value)); }

  function fixed2(value) { return Number(value).toFixed(2); }

  function records(project) {
    var p = project || App.PROJECT;
    return (p && p.boundary_conditions) || [];
  }

  function find(id, project) {
    return records(project).filter(function (record) { return record.id === id; })[0];
  }

  function isConditionKey(key) { return !!key && !!find(key); }

  /* ── Drafts: the twins of core/model/drafts.py ───────────────────────── */

  function freeId(taken, prefix) {
    var number = 1;
    while (taken.indexOf(prefix + number) >= 0) number += 1;
    return prefix + number;
  }

  /* An id and the name that goes with it: `Displacement 3` for the free
     `displacement_3`, and the id itself for one that was given. */
  function named(id, taken, prefix, noun) {
    if (id !== undefined && id !== null) return [id, id];
    var fresh = freeId(taken, prefix);
    return [fresh, noun + ' ' + fresh.slice(prefix.length)];
  }

  /* Down the middle of the section to half its depth, and the middle of the section:
     where a new line or point goes for the user to move (`_middle`, `_centre`). */
  function middle(project) {
    var d = project.domain;
    var x = d.x0 + (d.x1 - d.x0) * 0.5;
    return [[x, d.y_top], [x, d.y_top - (d.y_top - d.y_bottom) * 0.5]];
  }

  function centre(project) {
    var d = project.domain;
    return [d.x0 + (d.x1 - d.x0) * 0.5, d.y_bottom + (d.y_top - d.y_bottom) * 0.5];
  }

  function drawnPoints(project, on, points) {
    if (on === 'line') {
      return points ? points.map(function (p) { return [p[0], p[1]]; }) : middle(project);
    }
    if (on === 'point') {
      return points ? points.map(function (p) { return [p[0], p[1]]; }) : [centre(project)];
    }
    return null;
  }

  function takenIds(project) {
    return records(project).map(function (record) { return record.id; });
  }

  /* The axis a roller on this target holds. */
  function normal(on, face, points) {
    if (on === 'face' && FACE_NORMALS[face] !== undefined) return FACE_NORMALS[face];
    if (on === 'line' && points && points.length) {
      if (points.every(function (p) { return Math.abs(p[0] - points[0][0]) < 1e-9; })) {
        return 0;
      }
      if (points.every(function (p) { return Math.abs(p[1] - points[0][1]) < 1e-9; })) {
        return 1;
      }
      throw new Error('A roller holds the component normal to its line, and a sloping '
                      + 'line has no x or y normal; give the components it fixes.');
    }
    throw new Error('A roller on a ' + on + ' has no normal to hold; give the components '
                    + 'it fixes.');
  }

  /* `drafts.displacement_condition`: fixed in x, y and z unless `fixed` says which, or
     the target's normal only with `roller`. */
  function draftDisplacement(project, on, options) {
    options = options || {};
    if (on === 'domain') {
      throw new Error('A displacement condition on the whole soil would hold the whole '
                      + 'model still; put it on a face, a part, a line or a point.');
    }
    if ((on === 'line' || on === 'point') && project.dimension !== 2) {
      throw new Error('A displacement ' + on + ' is drawn in the 2D section; switch to 2D '
                      + 'to create one, or put the condition on a face or a part.');
    }
    var points = drawnPoints(project, on, options.points);
    var held;
    if (options.roller) {
      held = [false, false, false];
      held[normal(on, options.face, points)] = true;
    } else {
      held = options.fixed ? options.fixed.slice() : [true, true, true];
    }
    if (held.length !== 3) {
      throw new Error('A displacement condition holds x, y and z: give three values.');
    }
    var id = named(options.id, takenIds(project), 'displacement_', 'Displacement');
    return {
      id: id[0], name: options.name || id[1], kind: 'displacement', on: on,
      face: options.face || null, part: options.part || null, points: points,
      fixed: held.map(Boolean), active: true
    };
  }

  /* `drafts.water_pressure_condition`: hydrostatic and fixed unless told otherwise. A
     hydrostatic one with no level takes the project's water level, copied in. */
  function draftWaterPressure(project, on, options) {
    options = options || {};
    if ((on === 'line' || on === 'point') && project.dimension !== 2) {
      throw new Error('A water pressure ' + on + ' is drawn in the 2D section; switch to '
                      + '2D to create one, or put the condition on the whole soil, a face '
                      + 'or a part.');
    }
    var type = options.fluid_pressure_type || 'Hydrostatic';
    var level = options.reference_coordinate;
    if (level === undefined) level = null;
    if (type === 'Hydrostatic' && level === null) {
      if (!project.water) {
        throw new Error('A hydrostatic water pressure needs the level where its pressure '
                        + 'is zero: give its reference_coordinate. For a dry model, add no '
                        + 'water pressure condition, or a Uniform one with value 0.');
      }
      level = project.water.y;
    }
    var id = named(options.id, takenIds(project), 'waterpressure_', 'Water pressure');
    function list(values) { return values ? values.slice() : null; }
    return {
      id: id[0], name: options.name || id[1], kind: 'water_pressure', on: on,
      face: options.face || null, part: options.part || null,
      points: drawnPoints(project, on, options.points),
      fluid_pressure_type: type,
      is_fixed: options.is_fixed === undefined ? true : !!options.is_fixed,
      value: options.value === undefined ? 0.0 : options.value,
      reference_coordinate: level,
      x_coordinates: list(options.x_coordinates),
      y_coordinates: list(options.y_coordinates),
      z_coordinates: list(options.z_coordinates),
      pressure_tension_cut_off: options.pressure_tension_cut_off === undefined
        ? 0.0 : options.pressure_tension_cut_off,
      active: true
    };
  }

  /* Down the right side of the section to half its depth: where a new seepage line goes
     for the user to move (`drafts._right_side`). */
  function rightSide(project) {
    var d = project.domain;
    return [[d.x1, d.y_top], [d.x1, d.y_top - (d.y_top - d.y_bottom) * 0.5]];
  }

  /* `drafts.seepage_condition`: a seepage face on a face or along a line of the soil's
     outer boundary, where water may leave the soil in a groundwater flow calculation. */
  function draftSeepage(project, on, options) {
    options = options || {};
    if (on !== 'face' && on !== 'line') {
      throw new Error('A seepage face is on a face of the model, or on a line along the '
                      + "soil's outer boundary.");
    }
    if (on === 'line' && project.dimension !== 2) {
      throw new Error('A seepage line is drawn in the 2D section; switch to 2D to create '
                      + 'one, or put the seepage face on a face.');
    }
    var points = on === 'line'
      ? (options.points ? options.points.map(function (p) { return [p[0], p[1]]; })
                        : rightSide(project))
      : null;
    var id = named(options.id, takenIds(project), 'seepage_', 'Seepage face');
    return {
      id: id[0], name: options.name || id[1], kind: 'seepage', on: on,
      face: options.face || null, part: null, points: points, active: true
    };
  }

  /* `schemas.standard_conditions`: the bottom fixed, every side on rollers. */
  function standardSet() {
    var out = [{ id: 'fixed_bottom', name: 'Fixed bottom', kind: 'displacement',
                 on: 'face', face: 'bottom', part: null, points: null,
                 fixed: [true, true, true], active: true }];
    ['left', 'right', 'front', 'back'].forEach(function (face) {
      var held = [false, false, false];
      held[FACE_NORMALS[face]] = true;
      out.push({ id: 'roller_' + face, name: 'Roller ' + face, kind: 'displacement',
                 on: 'face', face: face, part: null, points: null, fixed: held,
                 active: true });
    });
    return out;
  }

  /* `drafts.standard_conditions`: the standard set, with ids no other condition of
     `project` has. */
  function standardConditions(project) {
    var taken = takenIds(project);
    return standardSet().map(function (record) {
      var id = record.id;
      if (taken.indexOf(id) >= 0) id = freeId(taken, record.id + '_');
      taken.push(id);
      record.id = id;
      return record;
    });
  }

  /* `session.standard_conditions`: the standard supports in place of every support on
     a face; the water pressures and the conditions on parts, lines and points stay. */
  function withStandard(project) {
    var kept = records(project).filter(function (record) {
      return !(record.kind === 'displacement' && record.on === 'face');
    }).map(copy);
    var standard = standardConditions(Object.assign({}, project,
                                                    { boundary_conditions: kept }));
    return standard.concat(kept);
  }

  /* What a part condition may name (`Project.soil_part_keys`): each layer, each body
     dug out of a staged one, and each custom part that has a material. */
  function soilPartKeys(project) {
    var keys = ((project && project.layers) || []).map(function (l) { return 'soil_' + l.id; });
    ((project && project.soil_body_keys) || []).forEach(function (key) {
      if (keys.indexOf(key) < 0) keys.push(key);
    });
    ((project && project.custom_parts) || []).forEach(function (part) {
      if (part.mat) keys.push(part.key);
    });
    return keys;
  }

  /* The faces this model has. */
  function facesOf(project) {
    return project && project.dimension === 2 ? SECTION_FACES.slice() : FACES.slice();
  }

  /* A support on the front or back face of a 2D model: the section holds z by itself,
     so the export leaves it out and the window and the explorer do not show it. It
     stays in the list for the solid model. */
  function heldBySection(record, project) {
    return !!project && project.dimension === 2 && record.kind === 'displacement'
      && record.on === 'face' && SECTION_FACES.indexOf(record.face) < 0;
  }

  /* The water pressure conditions `stageId` has on, by name, as the stage panel says
     them: a stage switches them as it does a part (App.Stages.activeParts). */
  function waterIn(project, stageId) {
    var water = records(project).filter(function (record) {
      return record.kind === 'water_pressure' && record.active !== false;
    });
    var on = App.Stages ? App.Stages.activeParts(project, stageId) : null;
    var names = water.filter(function (record) {
      return !on || on.indexOf(record.id) >= 0;
    }).map(function (record) { return record.name; });
    return names.length ? names.join(', ') : 'None';
  }

  /* ── Saying what a condition is ──────────────────────────────────────── */

  function xy(values) {
    return '(' + values.map(function (v) { return String(Number(v)); }).join(', ') + ')';
  }

  /* Where it acts, in words (`cli/commands/conditions.py` `target`). */
  function target(record) {
    if (record.on === 'domain') return 'the whole soil';
    if (record.on === 'face') return 'the ' + record.face + ' face';
    if (record.on === 'part') return 'part ' + record.part;
    return record.on + ' ' + (record.points || []).map(xy).join(' -> ');
  }

  /* What it prescribes, in words (`prescribed`). */
  function prescribed(record) {
    if (record.kind === 'displacement') {
      return 'fixed in ' + AXES.filter(function (axis, i) {
        return record.fixed[i];
      }).join(' ');
    }
    if (record.kind === 'seepage') return 'water may leave the soil here';
    var what;
    if (record.fluid_pressure_type === 'Uniform') what = String(record.value) + ' uniform';
    else if (record.fluid_pressure_type === 'Hydrostatic') {
      what = 'hydrostatic about ' + String(record.reference_coordinate) + ' m';
    } else {
      what = 'phreatic line ' + (record.x_coordinates || []).map(function (x, i) {
        return xy([x, record.y_coordinates[i]]);
      }).join(' -> ');
    }
    if (record.fluid_pressure_type !== 'Uniform' && record.pressure_tension_cut_off) {
      what += ', cut-off ' + record.pressure_tension_cut_off;
    }
    return what + (record.is_fixed ? ', fixed' : ', initial');
  }

  /* One condition in a line, as `kratos-cli boundary list` prints it. */
  function line(record) {
    return record.id + '  ' + record.name + '  ' + record.kind.replace('_', ' ') + ' on '
      + target(record) + '; ' + prescribed(record) + (record.active === false ? '  (inactive)' : '');
  }

  /* The explorer's label: the name, then what it does. */
  function label(record) {
    var what;
    if (record.kind === 'displacement') {
      what = AXES.filter(function (axis, i) { return record.fixed[i]; }).join(' ') + ' fixed';
    } else if (record.kind === 'seepage') {
      what = 'seepage';
    } else if (record.fluid_pressure_type === 'Hydrostatic') {
      what = 'h = ' + fixed2(record.reference_coordinate) + ' m';
    } else if (record.fluid_pressure_type === 'Uniform') {
      what = 'p = ' + record.value;
    } else {
      what = 'phreatic line';
    }
    return record.name + '  ·  ' + what;
  }

  /* Whether the self weight acts, as `core.model.stages.gravity` says it: a mechanical
     sequence has it when its initial stage initialises the stresses (K0 or gravity
     loading); a flow sequence and a project with no stages have it. */
  function selfWeight(project) {
    var first = ((project && project.stages) || []).filter(function (stage) {
      return stage.parent == null;
    })[0];
    if (!first || (first.calculation || 'mechanical') !== 'mechanical') return true;
    return (first.stress_initialisation || 'none') !== 'none';
  }

  /* As `kratos-cli gravity` says it (`cli/commands/conditions.py` `_gravity_line`). */
  function gravityLine(project) {
    var g = project && typeof project.gravity_acceleration === 'number'
      ? project.gravity_acceleration : App.Units.gravity('SI');
    var said = 'g = ' + g + ' m/s²';
    return selfWeight(project)
      ? 'The self weight acts on every body, with ' + said + '.'
      : 'The self weight is off: the initial stage initialises no stresses (' + said
        + ' when it acts).';
  }

  /* Said under a 2D list that leaves the front and back supports out
     (`condition_checks.SECTION_NOTE`). */
  var SECTION_NOTE = 'The front and back supports are kept for the solid model; the 2D '
    + 'section holds z by itself.';

  /* Said under the list of a groundwater flow project with supports
     (`condition_checks.FLOW_NOTE`). */
  var FLOW_NOTE = 'A groundwater flow calculation leaves the supports out: it solves the '
    + 'water pressure alone.';

  /* Whether the export of `project` leaves the support `record` out because the project
     is a groundwater flow calculation (`condition_checks.unused_in_flow`). */
  function unusedInFlow(record, project) {
    return record.kind === 'displacement' && App.Stages.groundwaterFlow(project);
  }

  /* The conditions a list shows, one line each, as `kratos-cli boundary list` prints
     them (`cli/commands/conditions.py` `listed_lines`). */
  function listedLines(project) {
    var all = records(project);
    var shown = all.filter(function (record) { return !heldBySection(record, project); });
    var lines = shown.length ? shown.map(line) : ['No boundary conditions yet.'];
    if (shown.length < all.length) lines.push(SECTION_NOTE);
    if (shown.some(function (record) { return unusedInFlow(record, project); })) {
      lines.push(FLOW_NOTE);
    }
    return lines;
  }

  /* ── The command box: `boundary` and `gravity` ───────────────────────── */

  /* `false` for a line that is not this command; otherwise `{ok, message, body}`,
     where `body` is what to PATCH, or null when there is nothing to send. */
  function command(text, project) {
    var words = String(text || '').trim().split(/\s+/);
    var word = (words[0] || '').toLowerCase();
    if (word !== 'boundary' && word !== 'gravity') return false;
    var arg = (words[1] || '').toLowerCase();

    if (word === 'gravity') {
      if (!arg) return { ok: true, body: null, message: gravityLine(project) };
      if (arg === 'on' || arg === 'off') {
        return { ok: false, body: null, message: 'Gravity has no switch: the initial '
                 + "stage's stress initialisation decides whether the self weight acts "
                 + '(Stages window). Give a number to set g, e.g. `gravity 9.81`.' };
      }
      var g = Number(arg);
      if (!isFinite(g) || words.length > 2) {
        return { ok: false, body: null, message: '"' + words.slice(1).join(' ')
                 + '" is not a number. Use `gravity 9.81` (g in m/s²).' };
      }
      if (!(g > 0)) {
        return { ok: false, body: null, message: 'g must be above 0 m/s², not ' + arg + '.' };
      }
      var after = Object.assign({}, project || {}, { gravity_acceleration: g });
      return { ok: true, body: { gravity_acceleration: g }, message: gravityLine(after) };
    }

    if (!arg || arg === 'list') {
      return { ok: true, body: null, message: listedLines(project).join('\n') };
    }
    if (arg === 'standard') {
      return { ok: true, body: { boundary_conditions: withStandard(project) },
               message: 'The standard supports: the bottom fixed, the sides on rollers.' };
    }
    return { ok: false, body: null,
             message: 'Use `boundary list` or `boundary standard`. Add and change '
                      + 'conditions in Model conditions > Boundary conditions.' };
  }

  /* ── Writing ─────────────────────────────────────────────────────────── */

  function send(body, message) {
    return App.Api.patch('/api/project/conditions', body)
      .then(function (response) {
        App.Model.apply(response.project);
        return App.Viewport.refresh();
      })
      .then(function () {
        if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
        if (App.Command && App.Command.ok) App.Command.ok(message);
        return true;
      })
      .catch(function (error) {
        var rollback = App.Model && App.Model.load ? App.Model.load() : Promise.resolve();
        function report() {
          if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
          if (App.Command && App.Command.err) {
            App.Command.err('Could not save the boundary conditions: ' + error.message);
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

  function saveAll(list, message) {
    return send({ boundary_conditions: copy(list) }, message);
  }

  function save(record) {
    var all = copy(records());
    var at = all.findIndex(function (item) { return item.id === record.id; });
    if (at < 0) all.push(copy(record)); else all[at] = copy(record);
    return saveAll(all, 'Saved ' + record.kind.replace('_', ' ') + ' condition '
                   + record.name + '.')
      .then(function () {
        if (App.selectObject) App.selectObject(record.id, 'tree');
        return record;
      });
  }

  function remove(id) {
    var record = find(id);
    if (!record) return Promise.resolve(false);
    if (App.state && App.state.selection === id && App.selectObject) App.selectObject(null);
    return saveAll(records().filter(function (item) { return item.id !== id; }),
                   'Deleted boundary condition ' + record.name + '.');
  }

  /* Whether the conditions `ids` are exported: 'on', 'off', or 'mixed' when they differ.
     What the Model explorer's check box on a condition row shows (addConditionChecks in
     frontend/js/patches.js). */
  function activeState(ids, project) {
    var on = ids.filter(function (id) {
      var record = find(id, project);
      return record && record.active !== false;
    }).length;
    return on === ids.length ? 'on' : on === 0 ? 'off' : 'mixed';
  }

  /* The check box's edit: the conditions `ids` in or out of the export, in one patch.
     For each, the same edit as `kratos-cli boundary set ID --active` or `--inactive`. */
  function setActive(ids, on) {
    var all = copy(records()).map(function (record) {
      if (ids.indexOf(record.id) >= 0) record.active = on;
      return record;
    });
    var names = ids.map(function (id) { return (find(id) || { name: id }).name; });
    return saveAll(all, (names.length === 1 ? 'Boundary condition ' + names[0] + ' is'
                         : 'Boundary conditions ' + names.join(', ') + ' are')
                   + (on ? ' active.' : ' inactive: kept in the project, but not exported.'));
  }

  function applyStandard() {
    return saveAll(withStandard(App.PROJECT),
                   'The standard supports: the bottom fixed, the sides on rollers.');
  }

  /* ── The face grid of the dialog: pure ───────────────────────────────── */

  /* The first condition of `kind` on a face (or on the whole soil, `face` null). */
  function onFace(list, kind, face) {
    return list.filter(function (record) {
      return record.kind === kind
        && (face ? record.on === 'face' && record.face === face : record.on === 'domain');
    })[0] || null;
  }

  /* What a support's `fixed` is called in the grid. */
  function supportChoice(record, face) {
    if (!record) return 'free';
    var held = record.fixed;
    if (held[0] && held[1] && held[2]) return 'fixed';
    var count = held.filter(Boolean).length;
    if (count === 1 && FACE_NORMALS[face] !== undefined && held[FACE_NORMALS[face]]) {
      return 'roller';
    }
    return 'custom';
  }

  /* One row of the grid as the window holds it, read off the conditions. A face's water
     column is its water pressure, or else its seepage face ('seepage'). */
  function gridRow(list, face) {
    var support = face ? onFace(list, 'displacement', face) : null;
    var water = onFace(list, 'water_pressure', face);
    var seepage = face && !water ? onFace(list, 'seepage', face) : null;
    return {
      face: face,
      support: supportChoice(support, face),
      fixed: support ? support.fixed.slice() : [false, false, false],
      supportId: support ? support.id : null,
      water: water ? water.fluid_pressure_type : seepage ? 'seepage' : 'none',
      number: water ? (water.fluid_pressure_type === 'Uniform'
                       ? water.value : water.reference_coordinate) : null,
      initial: water ? !water.is_fixed : false,
      waterId: water ? water.id : null,
      seepageId: seepage ? seepage.id : null
    };
  }

  function grid(project) {
    var list = records(project);
    return facesOf(project).map(function (face) { return gridRow(list, face); })
      .concat([gridRow(list, null)]);
  }

  /* The conditions the grid does not show: on parts, lines and points, and a second
     condition of a kind on one face. With `group`, only that group's. */
  function others(project, group) {
    var shown = {};
    grid(project).forEach(function (row) {
      if (row.supportId) shown[row.supportId] = true;
      if (row.waterId) shown[row.waterId] = true;
      if (row.seepageId) shown[row.seepageId] = true;
    });
    return records(project).filter(function (record) {
      return !shown[record.id] && !heldBySection(record, project)
        && inGroup(record.kind, group);
    });
  }

  /* The conditions after the grid's rows are applied to `project`'s: a row's records are
     changed in place, made, or taken out; every other condition stays as it is. A row
     with no `support` leaves the face's support alone, one with no `water` its water
     pressure and seepage face: the window of one group sends only its own columns. */
  function applyGrid(project, rows) {
    var list = copy(records(project));
    var work = Object.assign({}, project, { boundary_conditions: list });
    function drop(id) {
      var at = list.findIndex(function (item) { return item.id === id; });
      if (at >= 0) list.splice(at, 1);
    }
    function held(row) {
      if (row.support === 'fixed') return [true, true, true];
      if (row.support === 'roller') {
        var only = [false, false, false];
        only[FACE_NORMALS[row.face]] = true;
        return only;
      }
      return row.fixed.map(Boolean);
    }
    rows.forEach(function (row) {
      if (row.face && row.support !== undefined) {
        if (row.support === 'free') {
          if (row.supportId) drop(row.supportId);
        } else {
          var fixedNow = held(row);
          if (!fixedNow.some(Boolean)) {
            throw new Error('The support on the ' + row.face + ' face holds no component; '
                            + 'tick x, y or z, or set it free.');
          }
          var support = row.supportId && find(row.supportId, work);
          if (support) support.fixed = fixedNow;
          else {
            var name = (row.support === 'fixed' ? 'Fixed ' : row.support === 'roller'
              ? 'Roller ' : 'Support ') + row.face;
            list.push(draftDisplacement(work, 'face', { face: row.face, fixed: fixedNow,
                                                        name: name }));
          }
        }
      }
      if (row.water === undefined) return;
      var where = row.face ? 'the ' + row.face + ' face' : 'the whole soil';
      if (row.water !== 'seepage' && row.seepageId) drop(row.seepageId);
      if (row.water === 'seepage') {
        if (!row.face) throw new Error('A seepage face is on a face, not the whole soil.');
        if (row.waterId) drop(row.waterId);
        if (!row.seepageId) {
          list.push(draftSeepage(work, 'face', { face: row.face,
                                                 name: 'Seepage ' + row.face }));
        }
        return;
      }
      if (row.water === 'none') {
        if (row.waterId) drop(row.waterId);
        return;
      }
      var water = row.waterId && find(row.waterId, work);
      var number = row.number === '' || row.number === null || row.number === undefined
        ? null : Number(row.number);
      if (number !== null && !isFinite(number)) {
        throw new Error('The water pressure on ' + where + ' needs a number.');
      }
      if (row.water === 'Phreatic_Multi_Line'
          && !(water && water.fluid_pressure_type === 'Phreatic_Multi_Line')) {
        throw new Error('A Phreatic_Multi_Line on ' + where + ' needs the points of its '
                        + 'line: give them with More….');
      }
      if (row.water === 'Uniform' && number === null) number = 0.0;
      if (water) {
        water.fluid_pressure_type = row.water;
        water.is_fixed = !row.initial;
        if (row.water === 'Uniform') water.value = number;
        if (row.water === 'Hydrostatic') {
          water.reference_coordinate = number !== null ? number
            : (water.reference_coordinate !== null ? water.reference_coordinate
               : (project.water ? project.water.y : null));
          if (water.reference_coordinate === null) {
            throw new Error('A hydrostatic water pressure on ' + where + ' needs its '
                            + 'level.');
          }
        }
      } else {
        var options = { fluid_pressure_type: row.water, is_fixed: !row.initial };
        if (row.face) options.face = row.face;
        if (row.water === 'Uniform') options.value = number;
        if (row.water === 'Hydrostatic' && number !== null) {
          options.reference_coordinate = number;
        }
        list.push(draftWaterPressure(work, row.face ? 'face' : 'domain', options));
      }
    });
    return list;
  }

  /* ── The windows ─────────────────────────────────────────────────────── */

  function el(spec, attrs, child) { return App.UI.el(spec, attrs, child); }

  function options(select, choices, value) {
    choices.forEach(function (choice) {
      select.appendChild(el('option', { value: choice[0], text: choice[1] }));
    });
    select.value = value;
    return select;
  }

  /* "x y, x y" as points, or null for text that is not pairs of numbers. */
  function parsePoints(text) {
    var numbers = String(text || '').trim().split(/[\s,;]+/).filter(Boolean).map(Number);
    if (!numbers.length || numbers.length % 2 || !numbers.every(isFinite)) return null;
    var out = [];
    for (var i = 0; i < numbers.length; i += 2) out.push([numbers[i], numbers[i + 1]]);
    return out;
  }

  function pointsText(points) {
    return (points || []).map(function (p) { return p[0] + ' ' + p[1]; }).join(', ');
  }

  /* The Boundary conditions window: a row for each face of the model and one for the
     whole soil, the support and the water pressure on each; below them the conditions
     on parts, lines and points. Save writes them all in one request.
     `group` 'mechanical' shows the supports alone (no whole-soil row), and keeps the
     water conditions as they are; with none, both. 'flow' is the table of the flow
     conditions instead (`openFlowList`). */
  function open(group) {
    if (group === 'flow') return openFlowList();
    if (!App.Dialogs || !App.Dialogs.open || !App.PROJECT) return null;
    var project = App.PROJECT;
    var water = group !== 'mechanical';
    var rows = grid(project).filter(function (row) { return water || row.face; });
    var controls = [];
    var message, shell;

    function read() {
      return rows.map(function (row, i) {
        var c = controls[i];
        var out = Object.assign({}, row);
        if (c.support) {
          out.support = c.support.value;
          out.fixed = c.axes.map(function (box) { return box.checked; });
        } else delete out.support;
        if (c.water) {
          out.water = c.water.value;
          out.number = c.number.value.trim();
          out.initial = c.initial.checked;
        } else delete out.water;
        return out;
      });
    }

    function submit() {
      var list;
      try { list = applyGrid(App.PROJECT, read()); } catch (error) {
        message.textContent = error.message;
        return null;
      }
      return send({ boundary_conditions: list }, 'Saved the boundary conditions.').then(function () {
        shell.close();
      }, function (error) { message.textContent = error.message; });
    }

    function standard() {
      rows.forEach(function (row, i) {
        var c = controls[i];
        if (!c.support) return;
        c.support.value = row.face === 'bottom' ? 'fixed'
          : row.face === 'top' ? 'free' : 'roller';
        c.sync();
      });
    }

    function clear() {
      controls.forEach(function (c) {
        if (c.support) c.support.value = 'free';
        if (c.water) c.water.value = 'none';
        c.sync();
      });
    }

    /* The window of one condition of this row: its own, or a new one on the row. */
    function more(row) {
      var record = !water ? row.supportId && find(row.supportId)
        : (row.waterId && find(row.waterId)) || (row.seepageId && find(row.seepageId));
      shell.close();
      if (record) return openRecord(record, group);
      try {
        return openRecord(!water
          ? draftDisplacement(App.PROJECT, 'face', { face: row.face })
          : draftWaterPressure(App.PROJECT, row.face ? 'face' : 'domain', {
            face: row.face || undefined,
            fluid_pressure_type: App.PROJECT.water ? 'Hydrostatic' : 'Uniform' }), group);
      } catch (error) { if (App.Command) App.Command.err(error.message); }
      return null;
    }

    var heads = ['Where', 'Support', 'x', 'y', 'z'];
    if (water) heads = heads.concat(['Water pressure', 'Level / value', 'Initial']);
    heads.push('');

    var help = ['Support: Roller holds the component normal to the face, Fixed holds all; '
                + 'x, y, z: tick the components to hold.'];
    if (water) {
      help.push('Level / value: the level where a hydrostatic pressure is zero [m], or a '
                + 'uniform pressure [' + App.Units.label('stress') + '], compression '
                + 'negative. A new hydrostatic pressure with no level takes the water '
                + 'level. Initial: start values only, which the calculation then changes. '
                + 'Seepage face: water may leave the soil there, in a groundwater flow '
                + 'calculation.');
    }

    shell = App.Dialogs.open({
      title: (GROUPS[group] || { title: 'Boundary conditions' }).title,
      width: water ? 760 : 640, height: 560,
      buttons: [
        { label: 'Standard conditions', keepOpen: true, onClick: standard },
        { label: 'Clear', keepOpen: true, onClick: clear },
        { label: 'Add condition…', keepOpen: true, onClick: function () {
          shell.close();
          openRecord(null, group);
        } },
        { label: 'Save', primary: true, keepOpen: true, onClick: submit },
        { label: 'Cancel' }
      ],
      build: function (host) {
        // One column of its own: the dialog body lays its children out in a row.
        var body = el('div.mesh-settings-body.boundary-conditions');
        host.appendChild(body);
        var table = el('table.bc-grid');
        var head = el('tr');
        heads.forEach(function (text) { head.appendChild(el('th', { text: text })); });
        table.appendChild(head);

        rows.forEach(function (row) {
          var tr = el('tr');
          var c = {};
          tr.appendChild(el('td', { text: row.face ? row.face[0].toUpperCase()
                                    + row.face.slice(1) : 'Whole soil' }));
          if (row.face) {
            c.support = options(el('select.bc-support'), [['free', 'Free'],
              ['roller', 'Roller'], ['fixed', 'Fixed'], ['custom', 'x, y, z']], row.support);
            tr.appendChild(el('td', null, c.support));
            c.axes = AXES.map(function (axis, i) {
              var box = el('input.bc-axis', { type: 'checkbox' });
              box.checked = !!row.fixed[i];
              tr.appendChild(el('td', null, box));
              return box;
            });
          } else {
            tr.appendChild(el('td', { text: '—' }));
            ['', '', ''].forEach(function () { tr.appendChild(el('td')); });
          }
          if (water) {
            c.water = options(el('select.bc-water'), [['none', 'None'],
              ['Uniform', 'Uniform'], ['Hydrostatic', 'Hydrostatic'],
              ['Phreatic_Multi_Line', 'Phreatic line']].concat(
                row.face ? [['seepage', 'Seepage face']] : []), row.water);
            tr.appendChild(el('td', null, c.water));
            c.number = el('input.bc-number', { type: 'number', step: '0.1',
              value: row.number === null ? '' : String(row.number) });
            tr.appendChild(el('td', null, c.number));
            c.initial = el('input.bc-initial', { type: 'checkbox' });
            c.initial.checked = row.initial;
            tr.appendChild(el('td', null, c.initial));
          }
          var moreButton = el('button.btn.btn-sm', { type: 'button', text: 'More…' });
          moreButton.addEventListener('click', function () { more(row); });
          tr.appendChild(el('td', null, moreButton));
          c.sync = function () {
            if (c.support) {
              var choice = c.support.value;
              c.axes.forEach(function (box, i) {
                box.disabled = choice !== 'custom';
                if (choice === 'fixed') box.checked = true;
                if (choice === 'free') box.checked = false;
                if (choice === 'roller') box.checked = i === FACE_NORMALS[row.face];
              });
            }
            if (c.water) {
              var kind = c.water.value;
              c.number.disabled = kind === 'none' || kind === 'Phreatic_Multi_Line'
                || kind === 'seepage';
              c.initial.disabled = kind === 'none' || kind === 'seepage';
            }
          };
          if (c.support) c.support.addEventListener('change', c.sync);
          if (c.water) c.water.addEventListener('change', c.sync);
          c.sync();
          controls.push(c);
          table.appendChild(tr);
        });
        body.appendChild(table);
        body.appendChild(el('div.mesh-setting-help', { text: help.join(' ') }));

        var rest = others(project, group);
        body.appendChild(el('div.bc-heading', { text: 'On parts, lines and points' }));
        var list = el('div.bc-others');
        if (!rest.length) list.appendChild(el('div.mesh-setting-help', { text: 'None.' }));
        rest.forEach(function (record) {
          var item = el('div.bc-other');
          var solidOnly = project.dimension === 2 && record.on === 'face'
            && SECTION_FACES.indexOf(record.face) < 0;
          item.appendChild(el('span', { text: line(record)
                                        + (solidOnly ? '  (solid model only)' : '') }));
          var edit = el('button.btn.btn-sm', { type: 'button', text: 'Edit…' });
          edit.addEventListener('click', function () {
            shell.close();
            openRecord(record, group);
          });
          var del = el('button.btn.btn-sm', { type: 'button', text: 'Delete' });
          del.addEventListener('click', function () { shell.close(); remove(record.id); });
          item.appendChild(edit);
          item.appendChild(del);
          list.appendChild(item);
        });
        body.appendChild(list);

        message = el('div.mesh-settings-message');
        body.appendChild(message);
      }
    });
    return shell;
  }

  /* ── The table of the flow conditions ───────────────────────────────── */

  var NO_VALUE = '—';

  function plain(value) { return String(Number(value)); }

  /* Where a condition acts, as a table cell: "Whole soil", "Left face", "Part soil_L1",
     "Line (4, 6) → (22, 0)", "Point (8, -4)". */
  function whereCell(record, project) {
    if (record.on === 'domain') return 'Whole soil';
    if (record.on === 'face') {
      var face = record.face[0].toUpperCase() + record.face.slice(1) + ' face';
      return project && project.dimension === 2 && SECTION_FACES.indexOf(record.face) < 0
        ? face + ' (solid model only)' : face;
    }
    if (record.on === 'part') return 'Part ' + record.part;
    return (record.on === 'point' ? 'Point ' : 'Line ')
      + (record.points || []).map(xy).join(' → ');
  }

  /* One flow condition as the cells of its table row: the words a user reads, with
     units, and a dash where a column does not apply. */
  function flowRow(record, project) {
    var stress = ' ' + App.Units.label('stress');
    var row = { id: record.id, name: record.name, active: record.active !== false,
                where: whereCell(record, project) };
    if (record.kind === 'seepage') {
      return Object.assign(row, { condition: 'Seepage face', type: NO_VALUE,
                                  value: NO_VALUE, cutoff: NO_VALUE, initial: NO_VALUE });
    }
    var type = record.fluid_pressure_type;
    var level = record.reference_coordinate;
    row.condition = 'Water pressure';
    row.type = type === 'Phreatic_Multi_Line' ? 'Phreatic line' : type;
    if (type === 'Uniform') row.value = plain(record.value) + stress;
    else if (type === 'Hydrostatic') {
      row.value = level === null || level === undefined ? 'the water level'
        : 'y = ' + plain(level) + ' m';
    } else {
      row.value = (record.x_coordinates || []).map(function (x, i) {
        return xy([x, record.y_coordinates[i]]);
      }).join(' → ');
    }
    row.cutoff = type === 'Uniform' ? NO_VALUE
      : plain(record.pressure_tension_cut_off || 0) + stress;
    row.initial = record.is_fixed === false ? 'Yes' : 'No';
    return row;
  }

  /* The flow conditions of the model, in the order they were added, as table rows. */
  function flowRows(project) {
    return records(project).filter(function (record) {
      return groupOf(record.kind) === 'flow';
    }).map(function (record) { return flowRow(record, project); });
  }

  var FLOW_COLUMNS = [['name', 'Name'], ['condition', 'Condition'], ['where', 'Where'],
                      ['type', 'Type'], ['value', 'Level / value'],
                      ['cutoff', 'Tension cut-off'], ['initial', 'Initial only']];

  /* The Flow boundary conditions window: one row for each water pressure and seepage
     face of the model, with Edit… and Delete; Add condition… opens a new one. */
  function openFlowList() {
    if (!App.Dialogs || !App.Dialogs.open || !App.PROJECT) return null;
    var rows = flowRows(App.PROJECT);
    var shell = App.Dialogs.open({
      title: GROUPS.flow.title,
      width: 900, height: 480,
      buttons: [
        { label: 'Add condition…', keepOpen: true, onClick: function () {
          shell.close();
          openRecord(null, 'flow');
        } },
        { label: 'Close' }
      ],
      build: function (host) {
        var body = el('div.mesh-settings-body.boundary-conditions');
        host.appendChild(body);
        if (!rows.length) {
          body.appendChild(el('div.mesh-setting-help', { text: 'The model has no flow '
            + 'conditions yet. Click Add condition… to add a water pressure or a seepage '
            + 'face.' }));
          return;
        }
        var table = el('table.bc-grid.bc-flow');
        var head = el('tr');
        FLOW_COLUMNS.map(function (column) { return column[1]; }).concat(['Active', ''])
          .forEach(function (text) { head.appendChild(el('th', { text: text })); });
        table.appendChild(head);
        rows.forEach(function (row) {
          var tr = el('tr');
          FLOW_COLUMNS.forEach(function (column) {
            tr.appendChild(el('td', { text: row[column[0]] }));
          });
          var active = el('input.bc-active', { type: 'checkbox' });
          active.checked = row.active;
          active.addEventListener('change', function () {
            setActive([row.id], active.checked);
          });
          tr.appendChild(el('td', null, active));
          var actions = el('td.bc-actions');
          var edit = el('button.btn.btn-sm', { type: 'button', text: 'Edit…' });
          edit.addEventListener('click', function () {
            shell.close();
            openRecord(find(row.id), 'flow');
          });
          var del = el('button.btn.btn-sm', { type: 'button', text: 'Delete' });
          del.addEventListener('click', function () { shell.close(); remove(row.id); });
          actions.appendChild(edit);
          actions.appendChild(del);
          tr.appendChild(actions);
          table.appendChild(tr);
        });
        body.appendChild(table);
        body.appendChild(el('div.mesh-setting-help', { text: 'Level / value: where a '
          + 'hydrostatic pressure is zero, the points of a phreatic line, or a uniform '
          + 'pressure (compression negative). Initial only: start values, which the '
          + 'calculation then changes. Seepage face: water may leave the soil there, in a '
          + 'groundwater flow calculation.' }));
      }
    });
    return shell;
  }

  /* One condition, asked in the dialog's two steps: where (Whole soil / Face / Part /
     Line / Point, then which one) and what (a support, or a water pressure with the
     fields of its type). `null` makes a new one. `group` ('mechanical' or 'flow')
     offers only that group's kinds; a given condition keeps to its own group. */
  function openRecord(source, group) {
    if (!App.Dialogs || !App.Dialogs.open || !App.PROJECT) return null;
    var project = App.PROJECT;
    var record = source ? copy(source) : null;
    var known = !!(source && find(source.id));
    if (source) group = groupOf(source.kind);
    if (!GROUPS[group]) group = null;
    var kinds = KIND_CHOICES.filter(function (choice) { return inGroup(choice[0], group); });
    var c = {};
    var message, shell;

    function submit() {
      var kind = c.kind.value;
      var on = c.on.value;
      // A new condition opens as a support; switched to another kind, it takes that
      // kind's id and name (waterpressure_1, "Water pressure 1"), as the command line's.
      var draftName = record ? record.name : null;
      if (record && !known && record.kind !== kind) record = null;
      var where = { };
      if (on === 'face') where.face = c.face.value;
      if (on === 'part') where.part = c.part.value;
      if (on === 'line' || on === 'point') {
        var points = parsePoints(c.points.value);
        if (!points) { message.textContent = 'Give the points as x y, x y.'; return null; }
        where.points = points;
      }
      var made;
      try {
        if (kind === 'displacement') {
          made = draftDisplacement(project, on, Object.assign({
            fixed: c.axes.map(function (box) { return box.checked; }),
            id: record ? record.id : undefined }, where));
          if (!made.fixed.some(Boolean)) throw new Error('Tick x, y or z.');
        } else if (kind === 'seepage') {
          made = draftSeepage(project, on, Object.assign({
            id: record ? record.id : undefined }, where));
        } else {
          var type = c.type.value;
          var opts = Object.assign({ fluid_pressure_type: type, is_fixed: !c.initial.checked,
                                     id: record ? record.id : undefined }, where);
          var value = Number(c.value.value || 0);
          var level = c.level.value.trim();
          if (!isFinite(value)) throw new Error('The value must be a number.');
          opts.value = value;
          if (level !== '') opts.reference_coordinate = Number(level);
          var cut = Number(c.cutoff.value || 0);
          if (!isFinite(cut) || cut < 0) throw new Error('The cut-off is a stress of 0 or more.');
          opts.pressure_tension_cut_off = cut;
          if (type === 'Phreatic_Multi_Line') {
            var phreatic = parsePoints(c.phreatic.value);
            if (!phreatic || phreatic.length < 2) {
              throw new Error('A phreatic line needs two points or more, x y, x y.');
            }
            opts.x_coordinates = phreatic.map(function (p) { return p[0]; });
            opts.y_coordinates = phreatic.map(function (p) { return p[1]; });
            if (record && record.z_coordinates
                && record.z_coordinates.length === phreatic.length) {
              opts.z_coordinates = record.z_coordinates;
            }
          }
          made = draftWaterPressure(project, on, opts);
        }
      } catch (error) { message.textContent = error.message; return null; }
      var typed = c.name.value.trim();
      if (typed && !(record === null && typed === draftName)) made.name = typed;
      made.active = c.active.checked;
      return save(made).then(function () { shell.close(); }, function (error) {
        message.textContent = error.message;
      });
    }

    function pick() {
      if (!App.DrawInput || !App.DrawInput.start) return;
      var on = c.on.value;
      shell.close();
      App.DrawInput.start(on === 'point' ? 'load' : 'line', {
        count: 1, atPointer: true,
        onComplete: function (points) {
          var next = record ? copy(record) : { kind: c.kind.value };
          next.on = on;
          next.points = points.map(function (p) { return [p[0], p[1]]; });
          openRecord(Object.assign(blank(next.kind, on), next), group);
        }
      });
    }

    function blank(kind, on) {
      try {
        if (kind === 'seepage') {
          return draftSeepage(project, on === 'face' ? 'face' : 'line',
                              on === 'face' ? { face: 'right' } : {});
        }
        return kind === 'displacement'
          ? draftDisplacement(project, on === 'domain' ? 'face' : on,
                              on === 'domain' || on === 'face' ? { face: 'bottom' } : {})
          : draftWaterPressure(project, on, { fluid_pressure_type: project.water
                                              ? 'Hydrostatic' : 'Uniform' });
      } catch (error) {
        return draftWaterPressure(project, 'domain', { fluid_pressure_type: 'Uniform' });
      }
    }

    // A new flow condition opens as a water pressure on the whole soil.
    if (!record) {
      record = group === 'flow' ? blank('water_pressure', 'domain')
        : blank('displacement', 'face');
    }

    shell = App.Dialogs.open({
      title: (known ? 'Edit' : 'Create') + ' boundary condition',
      width: 600, height: 620,
      buttons: [
        { label: 'Pick on model…', onClick: pick },
        { label: 'Save', primary: true, keepOpen: true, onClick: submit },
        { label: 'Cancel' }
      ],
      build: function (body) {
        body.classList.add('mesh-settings-body');
        var form = el('div.mesh-settings-form');
        body.appendChild(form);
        var rows = {};
        function row(key, text, control, help) {
          var parts = [el('label.mesh-setting-label', { text: text }), control,
                       el('div.mesh-setting-help', { text: help || '' })];
          parts.forEach(function (part) { form.appendChild(part); });
          rows[key] = parts;
        }
        function show(key, on) {
          (rows[key] || []).forEach(function (part) { part.style.display = on ? '' : 'none'; });
        }
        function number(value) {
          return el('input.mesh-setting-control', { type: 'number', step: '0.1',
                                                    value: value === null || value === undefined
                                                      ? '' : String(value) });
        }

        c.name = el('input.mesh-setting-control', { type: 'text', value: record.name });
        row('name', 'Name', c.name, 'Shown in the Model explorer and the deck.');
        c.kind = options(el('select.mesh-setting-control'), kinds, record.kind);
        c.kind.disabled = known || kinds.length < 2;
        var supportHelp = 'A support holds displacements at zero.';
        var flowHelp = 'A water pressure sets the pore pressure. A seepage face, on a '
          + 'face or a line along the soil\'s outer boundary, lets water leave the soil '
          + 'in a groundwater flow calculation.';
        row('kind', 'Condition', c.kind, group === 'mechanical' ? supportHelp
            : group === 'flow' ? flowHelp
            : supportHelp + ' A seepage face, on a face or a line along the soil\'s outer '
              + 'boundary, lets water leave the soil in a groundwater flow calculation.');
        c.on = options(el('select.mesh-setting-control'), TARGETS, record.on);
        row('on', 'Where', c.on, 'Lines and points are drawn in the 2D section.');
        c.face = options(el('select.mesh-setting-control'), facesOf(project).map(function (f) {
          return [f, f];
        }), record.face || 'bottom');
        row('face', 'Face', c.face, '');
        var parts = soilPartKeys(project);
        c.part = options(el('select.mesh-setting-control'), parts.map(function (key) {
          return [key, key];
        }), record.part || parts[0] || '');
        row('part', 'Part', c.part, 'A soil part: a layer with all its lifts, one body, '
            + 'or a custom part with a material.');
        c.points = el('input.mesh-setting-control', { type: 'text',
                                                      value: pointsText(record.points) });
        row('points', 'Points', c.points, 'x y, x y … [m]; one point for a point.');

        c.axes = AXES.map(function (axis, i) {
          var box = el('input', { type: 'checkbox' });
          box.checked = record.kind === 'displacement' ? !!record.fixed[i] : i < 2;
          return box;
        });
        var axesBox = el('div.bc-axes');
        c.axes.forEach(function (box, i) {
          var lab = el('label');
          lab.appendChild(box);
          lab.appendChild(document.createTextNode(' ' + AXES[i] + '  '));
          axesBox.appendChild(lab);
        });
        var roller = el('button.btn.btn-sm', { type: 'button', text: 'Roller' });
        roller.addEventListener('click', function () {
          var points = parsePoints(c.points.value);
          try {
            var axis = normal(c.on.value, c.face.value, points);
            c.axes.forEach(function (box, i) { box.checked = i === axis; });
            message.textContent = '';
          } catch (error) { message.textContent = error.message; }
        });
        axesBox.appendChild(roller);
        row('axes', 'Fixed', axesBox, 'The components held at zero; a 2D deck never holds z.');

        var water = record.kind === 'water_pressure' ? record : {};
        c.type = options(el('select.mesh-setting-control'), PRESSURE_TYPES.map(function (t) {
          return [t, t.replace(/_/g, ' ')];
        }), water.fluid_pressure_type || 'Hydrostatic');
        row('type', 'Type', c.type, 'Uniform: one value. Hydrostatic: zero at its level, '
            + 'growing with depth. Phreatic line: hydrostatic below a line.');
        c.value = number(water.value);
        row('value', 'Value', c.value, '[' + App.Units.label('stress') + '], compression '
            + 'negative.');
        c.level = number(water.reference_coordinate !== undefined
                         ? water.reference_coordinate
                         : (project.water ? project.water.y : null));
        row('level', 'Reference level', c.level, 'Where the pressure is zero [m]. Empty '
            + 'takes the water level.');
        c.phreatic = el('input.mesh-setting-control', { type: 'text', value:
          (water.x_coordinates || []).map(function (x, i) {
            return x + ' ' + water.y_coordinates[i];
          }).join(', ') });
        row('phreatic', 'Phreatic line', c.phreatic, 'x y, x y … [m], x increasing.');
        c.cutoff = number(water.pressure_tension_cut_off || 0);
        row('cutoff', 'Tension cut-off', c.cutoff, 'The most suction above the level ['
            + App.Units.label('stress') + ']; 0 holds it at zero.');
        c.initial = el('input.mesh-setting-control', { type: 'checkbox' });
        c.initial.checked = water.is_fixed === false;
        row('initial', 'Initial only', c.initial, 'Start values, which the calculation '
            + 'then changes.');

        c.active = el('input.mesh-setting-control', { type: 'checkbox' });
        c.active.checked = record.active !== false;
        row('active', 'Active', c.active, 'Inactive conditions stay in the project but are '
            + 'not exported.');
        message = el('div.mesh-settings-message');
        row('message', '', message, '');

        function sync() {
          var support = c.kind.value === 'displacement';
          var seepage = c.kind.value === 'seepage';
          var water = !support && !seepage;
          var on = c.on.value;
          var type = c.type.value;
          show('face', on === 'face');
          show('part', on === 'part');
          show('points', on === 'line' || on === 'point');
          show('axes', support);
          ['type', 'cutoff', 'initial'].forEach(function (key) { show(key, water); });
          show('value', water && type === 'Uniform');
          show('level', water && type === 'Hydrostatic');
          show('phreatic', water && type === 'Phreatic_Multi_Line');
          show('cutoff', water && type !== 'Uniform');
        }
        [c.kind, c.on, c.type].forEach(function (control) {
          control.addEventListener('change', sync);
        });
        sync();
      }
    });
    return shell;
  }

  /* A support or a water pressure along a line drawn in the section, or at a point:
     the rail's tools. The drawn points open the condition's window. */
  function draw(kind, on) {
    var project = App.PROJECT;
    if (!project) return;
    if (project.dimension !== 2) {
      if (App.Command) App.Command.note('Lines and points are drawn in the 2D section; '
                                        + 'switch to 2D.');
      return;
    }
    if (!App.DrawInput || !App.DrawInput.start) return;
    App.DrawInput.start(on === 'point' ? 'load' : 'line', {
      // A point is where it was clicked, not on the ground surface as a load is.
      count: 1, atPointer: true,
      onComplete: function (points) {
        var drawn = points.map(function (p) { return [p[0], p[1]]; });
        var record;
        try {
          record = kind === 'displacement'
            ? draftDisplacement(App.PROJECT, on, { points: drawn })
            : kind === 'seepage' ? draftSeepage(App.PROJECT, on, { points: drawn })
            : draftWaterPressure(App.PROJECT, on, { points: drawn, fluid_pressure_type:
                                                    App.PROJECT.water ? 'Hydrostatic'
                                                                      : 'Uniform' });
        } catch (error) {
          if (App.Command) App.Command.err(error.message);
          return;
        }
        openRecord(record);
      }
    });
  }

  function edit(id) {
    var record = find(id);
    return record ? openRecord(record) : null;
  }

  return {
    FACES: FACES, SECTION_FACES: SECTION_FACES, FACE_NORMALS: FACE_NORMALS,
    PRESSURE_TYPES: PRESSURE_TYPES, TARGETS: TARGETS, GROUPS: GROUPS, groupOf: groupOf,
    draftDisplacement: draftDisplacement, draftWaterPressure: draftWaterPressure,
    draftSeepage: draftSeepage,
    standardConditions: standardConditions, withStandard: withStandard,
    soilPartKeys: soilPartKeys, facesOf: facesOf, heldBySection: heldBySection,
    unusedInFlow: unusedInFlow, waterIn: waterIn,
    line: line, listedLines: listedLines, label: label,
    command: command,
    grid: grid, others: others, applyGrid: applyGrid, parsePoints: parsePoints,
    flowRows: flowRows,
    isConditionKey: isConditionKey, find: find,
    save: save, remove: remove, applyStandard: applyStandard,
    activeState: activeState, setActive: setActive,
    open: open, openRecord: openRecord, draw: draw, edit: edit
  };
})();
