/* ══════════════════════════════════════════════════════════════════
   boundary-conditions.js — the boundary conditions.

   A boundary condition is a record of `Project.boundary_conditions`
   (core/model/schemas.py), and the deck holds these and no others: a project with
   no water pressure condition fixes no water pressure, and one with no support
   holds nothing still. Two kinds share one list, told apart by `kind`:

     • "displacement": the components `fixed` (x, y, z) held at zero, on a face, a
       soil part, a drawn line or a point;
     • "water_pressure": Kratos' `fluid_pressure_type` (Uniform, Hydrostatic,
       Phreatic_Multi_Line, and Head_Line: a phreatic multi-line to Kratos) on the whole
       soil, a face, a part, a line or a point;
     • "seepage": where water may leave the soil, on a face or a line of its boundary;
     • "flux": water flowing into the soil at a rate, on a face or a line of its boundary.

   The Flow conditions rail draws them directly: a water line (`drawWaterLine`: the
   phreatic line first, head lines after it), a flow boundary condition along the soil's
   boundary (`drawFlowBoundary`), and a uniform pressure on a soil (`pickSoilPressure`).
   In Staged construction a stage gives its own phreatic line, soil water and values
   (`setStagePhreatic`, `setStageSoilWater`, `openRecord` with a stage).

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
  var PRESSURE_TYPES = ['Uniform', 'Hydrostatic', 'Phreatic_Multi_Line', 'Head_Line'];
  /* What the type lists call them. */
  var TYPE_LABELS = { Uniform: 'Uniform', Hydrostatic: 'Hydrostatic',
                      Phreatic_Multi_Line: 'Phreatic line', Head_Line: 'Head line' };
  /* `schemas.LINE_TYPES` on `schemas.LINE_TARGETS`: a water line, the phreatic line or a
     head line, on the whole soil or drawn on a line. `schemas.INTERPOLATE`: a soil whose
     water is interpolated between the soils above and below it (Kratos'
     Interpolate_Line). */
  var LINE_TYPES = ['Phreatic_Multi_Line', 'Head_Line'];
  var LINE_TARGETS = ['domain', 'line'];
  var INTERPOLATE = 'interpolate';
  /* `schemas.DRY`: a soil with no water, its pressure held at zero. */
  var DRY = 'dry';
  /* `schemas.STAGE_VALUES`: the fields a stage may give a value of its own. */
  var STAGE_VALUES = {
    water_pressure: ['value', 'reference_coordinate', 'x_coordinates', 'y_coordinates',
                     'z_coordinates', 'pressure_tension_cut_off'],
    flux: ['value']
  };
  var TARGETS = [['domain', 'Whole soil'], ['face', 'Face'], ['part', 'Part'],
                 ['line', 'Line'], ['point', 'Point']];
  var AXES = ['x', 'y', 'z'];
  /* The two groups of conditions, each with its own windows: the mechanical ones
     (supports) in Structures mode, the flow ones (water pressure, seepage face) in
     Flow conditions mode. */
  var GROUPS = {
    mechanical: { kinds: ['displacement'], title: 'Mechanical boundary conditions' },
    flow: { kinds: ['water_pressure', 'seepage', 'flux'], title: 'Flow boundary conditions' }
  };
  var KIND_CHOICES = [['displacement', 'Support'], ['water_pressure', 'Water pressure'],
                      ['seepage', 'Seepage face'], ['flux', 'Flux']];

  /* The unit of a flux: the project's length over its time. */
  function fluxUnit() {
    var time = App.Units && App.Units.label ? App.Units.label('time') : '';
    return 'm/' + (time || 's');
  }

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

  /* `drafts.flux_condition`: water flowing into the soil at `value` (the project's length
     over its time; negative flows out), on a face or along a line of the soil's outer
     boundary. */
  function draftFlux(project, on, options) {
    options = options || {};
    if (on !== 'face' && on !== 'line') {
      throw new Error('A prescribed flux is on a face of the model, or on a line along '
                      + "the soil's outer boundary.");
    }
    if (on === 'line' && project.dimension !== 2) {
      throw new Error('A flux line is drawn in the 2D section; switch to 2D to create '
                      + 'one, or put the flux on a face.');
    }
    var points = on === 'line'
      ? (options.points ? options.points.map(function (p) { return [p[0], p[1]]; })
                        : rightSide(project))
      : null;
    var id = named(options.id, takenIds(project), 'flux_', 'Flux');
    return {
      id: id[0], name: options.name || id[1], kind: 'flux', on: on,
      face: options.face || null, part: null, points: points,
      value: options.value === undefined ? 0.0 : options.value, active: true
    };
  }

  /* `drafts.water_line`: a water line through `points` on the whole soil -- the
     phreatic line if the project has none yet, else a head line -- its points sorted by
     x. Start values in a groundwater flow project, fixed otherwise. */
  function draftWaterLine(project, points, options) {
    options = options || {};
    var drawn = (points || []).map(function (p) { return [Number(p[0]), Number(p[1])]; })
      .sort(function (a, b) { return a[0] - b[0]; });
    if (drawn.length < 2) throw new Error('A water line needs two points or more.');
    for (var i = 1; i < drawn.length; i += 1) {
      if (drawn[i][0] <= drawn[i - 1][0]) {
        throw new Error('A water line has one level at each x: give its points different '
                        + 'x coordinates.');
      }
    }
    var phreatic = !waterLines(records(project)).length;
    var id = named(options.id, takenIds(project), 'waterline_',
                   phreatic ? 'Phreatic line' : 'Head line');
    var flow = !!(App.Stages && App.Stages.groundwaterFlow
                  && App.Stages.groundwaterFlow(project));
    return {
      id: id[0], name: options.name || id[1], kind: 'water_pressure', on: 'domain',
      fluid_pressure_type: phreatic ? 'Phreatic_Multi_Line' : 'Head_Line',
      is_fixed: !flow,
      x_coordinates: drawn.map(function (p) { return p[0]; }),
      y_coordinates: drawn.map(function (p) { return p[1]; }),
      active: true
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
    if (record.kind === 'flux') {
      return record.value >= 0 ? String(record.value) + ' into the soil'
        : String(-record.value) + ' out of the soil';
    }
    var what;
    if (record.fluid_pressure_type === 'Uniform') what = String(record.value) + ' uniform';
    else if (record.fluid_pressure_type === 'Hydrostatic') {
      what = 'hydrostatic about ' + String(record.reference_coordinate) + ' m';
    } else {
      what = (record.fluid_pressure_type === 'Head_Line' ? 'head line ' : 'phreatic line ')
        + (record.x_coordinates || []).map(function (x, i) {
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
    } else if (record.kind === 'flux') {
      what = 'q = ' + record.value + ' ' + fluxUnit();
    } else if (record.fluid_pressure_type === 'Hydrostatic') {
      what = 'h = ' + fixed2(record.reference_coordinate) + ' m';
    } else if (record.fluid_pressure_type === 'Uniform') {
      what = 'p = ' + record.value;
    } else {
      what = record.fluid_pressure_type === 'Head_Line' ? 'head line' : 'phreatic line';
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

  /* `record` saved, in place of the one of its id or added. `staged`, from
     `stagedPhreatic`, sends the stages along, so both are checked as one edit. */
  function save(record, staged) {
    var all = copy(records());
    var at = all.findIndex(function (item) { return item.id === record.id; });
    if (at < 0) all.push(copy(record)); else all[at] = copy(record);
    var message = 'Saved ' + record.kind.replace('_', ' ') + ' condition ' + record.name + '.';
    var body = { boundary_conditions: all };
    if (staged) {
      body.stages = staged.stages;
      message += ' It is the phreatic line from stage ' + staged.stageName + ' on'
        + (staged.replaced.length ? ', in place of ' + staged.replaced.join(', ') : '')
        + '.';
    }
    return send(body, message)
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

  /* ── The water of each soil: pure ────────────────────────────────────── */

  /* `Project.water_lines`: the phreatic line and the head lines, on the whole soil or
     drawn on a line. */
  function waterLines(list) {
    return list.filter(function (record) {
      return record.kind === 'water_pressure' && LINE_TARGETS.indexOf(record.on) >= 0
        && LINE_TYPES.indexOf(record.fluid_pressure_type) >= 0;
    });
  }

  /* `Project.phreatic_lines`: every soil's water by default, one a stage. */
  function phreaticLines(list) {
    return waterLines(list).filter(function (record) {
      return record.fluid_pressure_type === 'Phreatic_Multi_Line';
    });
  }

  /* The first phreatic line, or null: the one the whole soil's row of the grid shows. */
  function phreaticLine(list) {
    return phreaticLines(list)[0] || null;
  }

  /* The phreatic lines' names, as a soil that takes them is labelled. */
  function phreaticNames(list) {
    return phreaticLines(list).map(function (record) { return record.name; }).join(', ');
  }

  /* `Project.head_lines`: the lines a soil can take instead. */
  function headLines(list) {
    return waterLines(list).filter(function (record) {
      return record.fluid_pressure_type === 'Head_Line';
    });
  }

  /* A stage has one phreatic line on (`Project.phreatic_lines_together`): said before
     the server says it, with what to do instead. Only a phreatic line on the whole soil
     or drawn on a line counts, and only one that is on. A staged `project` may switch
     from one to another, a lower one for a pit pumped dry, which the server checks
     stage by stage. */
  function checkOnePhreatic(list, project) {
    if (project && (project.stages || []).length) return;
    var phreatic = phreaticLines(list).filter(function (record) {
      return record.active !== false;
    });
    if (phreatic.length > 1) {
      throw new Error('A stage has one phreatic line, ' + phreatic[0].name + '. Switch '
                      + phreatic[1].name + ' off, or make it a head line and give it to '
                      + 'its soils under Soil water.');
    }
  }

  /* A new phreatic line `made`, saved while the stage `stageId` is selected, in a staged
     `project`: the phreatic line from that stage on. Everything starts in the model, so
     saved as it is it would be on in the initial stage beside the one already there,
     which the server refuses. So the initial stage switches it off and the stage
     switches it on, and each phreatic line on in the stage before is switched off there
     -- one a stage. `{stages, replaced}`, the whole sequence and the names of the lines
     it switched off, or null when there is nothing to do: an unstaged project, a line
     already in the project, a line that is no phreatic line or is off, or the initial
     stage selected (two lines on there is the error `checkOnePhreatic` says). */
  function stagedPhreatic(project, made, stageId) {
    var S = App.Stages;
    var list = (project && project.stages) || [];
    if (!S || !list.length || !made || made.active === false) return null;
    if (made.kind !== 'water_pressure' || made.fluid_pressure_type !== 'Phreatic_Multi_Line'
        || LINE_TARGETS.indexOf(made.on) < 0) return null;
    if (find(made.id, project)) return null;
    var chain = S.chainTo(project, stageId);
    if (chain.length < 2) return null;
    var parent = chain[chain.length - 2];
    var before = S.activeParts(project, parent.id) || [];
    var here = S.activeParts(project, stageId) || [];
    var others = phreaticLines(project.boundary_conditions || []).filter(function (record) {
      return record.active !== false && here.indexOf(record.id) >= 0;
    });
    function without(items, key) {
      return (items || []).filter(function (k) { return k !== key; });
    }
    var stages = copy(list).map(function (stage) {
      stage.activate = (stage.activate || []).slice();
      stage.deactivate = (stage.deactivate || []).slice();
      if (stage.id === chain[0].id) stage.deactivate.push(made.id);
      if (stage.id === stageId) {
        stage.activate.push(made.id);
        others.forEach(function (record) {
          stage.activate = without(stage.activate, record.id);
          stage.deactivate = without(stage.deactivate, record.id);
          // Only an instruction the stage before does not already give.
          if (before.indexOf(record.id) >= 0) stage.deactivate.push(record.id);
        });
      }
      return stage;
    });
    return { stages: stages, replaced: others.map(function (record) { return record.name; }) };
  }

  /* A new phreatic line made with the initial stage selected, in a staged `project`
     whose initial stage has one on already: said before the server says it, with how
     to make it a later stage's. */
  function checkInitialPhreatic(project, made, stageId) {
    var S = App.Stages;
    if (!S || !project || !(project.stages || []).length || !made || made.active === false
        || made.kind !== 'water_pressure' || made.fluid_pressure_type !== 'Phreatic_Multi_Line'
        || LINE_TARGETS.indexOf(made.on) < 0 || find(made.id, project)) return;
    var initial = S.initialOf(project);
    if (!initial || (stageId && stageId !== initial.id)) return;
    var on = S.activeParts(project, initial.id) || [];
    var there = phreaticLines(project.boundary_conditions || []).filter(function (record) {
      return record.active !== false && on.indexOf(record.id) >= 0;
    })[0];
    if (there) {
      throw new Error('A stage has one phreatic line, and ' + initial.name + ' has '
                      + there.name + '. To make this the phreatic line of a later stage, '
                      + 'select that stage in Staged construction and save it again; or '
                      + 'make it a head line.');
    }
  }

  /* What the user calls the soil `key`: its layer, its piece of one, or its part. */
  function soilName(project, key) {
    var layer = (project.layers || []).filter(function (l) {
      return 'soil_' + l.id === key;
    })[0];
    if (layer) return layer.name;
    var part = (project.custom_parts || []).filter(function (p) { return p.key === key; })[0];
    if (part) return part.label;
    return (project.soil_body_labels || {})[key] || key;
  }

  /* The water a soil can take, as [value, label]: the phreatic line (''), a head line,
     interpolated, or dry. With `state` (`waterState`), the phreatic and head lines are
     that stage's. */
  function soilWaterChoices(list, state) {
    var phreatic = state ? (state.phreatic ? state.phreatic.name : '') : phreaticNames(list);
    var heads = state ? state.heads : headLines(list);
    var out = [['', 'Phreatic line' + (phreatic ? ' (' + phreatic + ')' : ' (none yet)')]];
    heads.forEach(function (record) {
      out.push([record.id, 'Head line (' + record.name + ')']);
    });
    out.push([INTERPOLATE, 'Interpolated between the soils above and below']);
    out.push([DRY, 'Dry: no water, its pressure held at zero']);
    return out;
  }

  /* The water of stage `stageId`, or of the model as built for null, as the Flow
     conditions and Staged construction tabs draw it (`App.Stages.waterIn`): `phreatic`
     its phreatic line or null, `heads` the head lines in the order of the list, and
     `soil_water` the soils that take a water of their own. */
  function waterState(project, stageId) {
    var list = records(project);
    if (!App.Stages || !App.Stages.waterIn) {
      return { phreatic: phreaticLine(list), heads: headLines(list),
               soil_water: (project && project.soil_water) || {}, conditions: {} };
    }
    var water = App.Stages.waterIn(project || {}, stageId == null ? null : stageId);
    var heads = waterLines(list).filter(function (record) {
      return !!water.conditions[record.id]
        && !(water.phreatic && water.phreatic.id === record.id);
    });
    return { phreatic: water.phreatic, heads: heads, soil_water: water.soil_water,
             conditions: water.conditions };
  }

  /* Each soil and the water it takes, '' for the phreatic line: the rows of Soil water. */
  function soilWaterRows(project) {
    var chosen = (project && project.soil_water) || {};
    return soilPartKeys(project).map(function (key) {
      return { key: key, label: soilName(project, key), water: chosen[key] || '' };
    });
  }

  /* `Project.soil_water` after the rows, with the conditions `list`: a soil whose head
     line is no longer one takes the phreatic line. */
  function applySoilWater(list, rows) {
    var lines = waterLines(list).map(function (record) { return record.id; });
    var out = {};
    rows.forEach(function (row) {
      if (row.water === INTERPOLATE || row.water === DRY || lines.indexOf(row.water) >= 0) {
        out[row.key] = row.water;
      }
    });
    return out;
  }

  /* ── The colours of the water: pure ──────────────────────────────────── */

  /* The phreatic line and an interpolated soil are always drawn in the same colour,
     whatever order the lines were drawn or listed in, so a user learns them once. The
     head lines take the colours of `HEAD_COLORS` in their order in the list, none of
     them the phreatic blue or the interpolated amber. A soil is filled with a light
     tint of its line's colour (`SOIL_TINT`), so the line itself still shows over it. */
  var PHREATIC_COLOR = '#1565c0';
  var INTERPOLATE_COLOR = '#e09b00';
  /* A dry soil, sand-coloured. A soil with a uniform pressure of its own is no water
     line's: green, away from every water blue and the head lines' teal, and hatched
     (`pattern: 'hatch'`), so it never reads as a soil on the phreatic line. */
  var DRY_COLOR = '#a1887f';
  var UNIFORM_COLOR = '#388e3c';
  var NO_WATER_COLOR = '#9aa3ad';
  var HEAD_COLORS = ['#c62828', '#7b1fa2', '#00897b', '#d81b60', '#6d4c41', '#5d7a00'];
  var SOIL_TINT = 0.45;

  /* `hex` mixed toward white by `amount` (0 keeps it, 1 is white). */
  function tint(hex, amount) {
    var n = parseInt(String(hex).slice(1), 16);
    return '#' + [16, 8, 0].map(function (shift) {
      var c = (n >> shift) & 255;
      var mixed = Math.round(c + (255 - c) * amount);
      return (mixed < 16 ? '0' : '') + mixed.toString(16);
    }).join('');
  }

  /* The colour of the water line `record` among the conditions `list`: the phreatic
     blue, a head line's own colour, or null for any other condition. */
  function waterLineColor(record, list, phreaticId) {
    if (!record || record.kind !== 'water_pressure') return null;
    var phreatic = phreaticId !== undefined
      ? record.id === phreaticId
      : phreaticLines(list).some(function (r) { return r.id === record.id; });
    if (phreatic) return PHREATIC_COLOR;
    // A head line keeps its colour whatever a stage makes of the lines: the typed head
    // lines first, in their order, then the lines typed phreatic that a stage makes
    // head lines.
    var order = headLines(list).concat(phreaticLines(list)).map(function (r) { return r.id; });
    var at = order.indexOf(record.id);
    return at < 0 ? null : HEAD_COLORS[at % HEAD_COLORS.length];
  }

  /* The water the soil `key` takes, as `Project.water_of_bodies` reads it: its own
     entry, else its layer's (a body `soil_L__a` is a piece of `soil_L`), else '' for
     the phreatic line. An entry naming a line that is no head line is no entry. */
  function soilWaterOf(project, key, stageId) {
    var chosen = waterState(project, stageId).soil_water;
    if (chosen[key] !== undefined) return chosen[key];
    var layer = String(key).split('__')[0];
    if (layer !== key && chosen[layer] !== undefined) return chosen[layer];
    return '';
  }

  /* The fixed uniform pressure the user put on the soil `key` (on it, or on its layer)
     that the stage `stageId` has on, or null: it is the one the soil gets
     (`writer._water_pressures`). */
  function soilPressureOf(project, key, stageId) {
    var conditions = waterState(project, stageId).conditions;
    var layer = String(key).split('__')[0];
    var found = null;
    Object.keys(conditions).forEach(function (id) {
      var record = conditions[id];
      if (record.kind === 'water_pressure' && record.on === 'part'
          && record.fluid_pressure_type === 'Uniform' && record.is_fixed !== false
          && (record.part === key || record.part === layer)) found = record;
    });
    return found;
  }

  /* What the water `water` ('' for the phreatic line, a head line's id, or
     INTERPOLATE) is called and drawn in. A soil on the phreatic line of a project that
     has none takes no water line. */
  function waterLook(list, water, state) {
    if (water === INTERPOLATE) {
      return { color: INTERPOLATE_COLOR, label: 'Interpolated' };
    }
    if (water === DRY) return { color: DRY_COLOR, label: 'Dry' };
    var phreaticId = state ? (state.phreatic ? state.phreatic.id : null) : undefined;
    if (water) {
      var heads = state ? state.heads : headLines(list);
      var line = heads.filter(function (r) { return r.id === water; })[0];
      if (line) {
        return { color: waterLineColor(line, list, phreaticId), label: 'Head line: ' + line.name };
      }
    }
    var phreatic = state ? (state.phreatic ? state.phreatic.name : '') : phreaticNames(list);
    return phreatic
      ? { color: PHREATIC_COLOR, label: 'Phreatic line: ' + phreatic }
      : { color: NO_WATER_COLOR, label: 'No water line' };
  }

  /* Whether the Flow conditions tab colours the soils by their water: once there is a
     water line, or a soil takes a water of its own. A project with neither keeps the
     soils in their own colours. */
  function soilWaterShown(project) {
    return waterLines(records(project)).length > 0
      || Object.keys((project && project.soil_water) || {}).length > 0
      || ((project && project.stages) || []).some(function (stage) {
        return Object.keys(stage.soil_water || {}).length > 0;
      })
      || records(project).some(function (record) {
        return record.kind === 'water_pressure' && record.on === 'part'
          && record.fluid_pressure_type === 'Uniform';
      });
  }

  /* Each soil of `keys` and how the Flow conditions tab draws it, as
     `{key: {water, color, fill, label, pattern}}`: `color` its line's, `fill` the
     lighter tint the soil is filled with, `pattern` 'hatch' for a uniform pressure of
     its own (stripes of `color` over `fill`), else null. Null when the soils keep
     their own colours (`soilWaterShown`). */
  function soilWaterColors(project, keys, stageId) {
    if (!soilWaterShown(project)) return null;
    var list = records(project);
    var state = stageId == null ? null : waterState(project, stageId);
    var out = {};
    (keys || []).forEach(function (key) {
      var pressure = soilPressureOf(project, key, stageId);
      var water = soilWaterOf(project, key, stageId);
      var look = pressure
        ? { color: UNIFORM_COLOR, label: 'Uniform pressure: ' + pressure.name }
        : waterLook(list, water, state);
      out[key] = { water: pressure ? 'uniform:' + pressure.id : water, color: look.color,
                   fill: tint(look.color, SOIL_TINT), label: look.label,
                   pattern: pressure ? 'hatch' : null };
    });
    return out;
  }

  /* The legend of the Flow conditions tab: one row for each water line, and one for
     interpolated and for no water line when a soil of `keys` takes it, as
     `[{color, fill, label, line, pattern}]` -- `line` 'solid' for the phreatic line,
     'dashed' for a head line, null for a soil-only entry; `pattern` as
     `soilWaterColors` gives it. Empty when the soils keep their own colours. */
  function waterLegend(project, keys, stageId) {
    var colors = soilWaterColors(project, keys, stageId);
    if (!colors) return [];
    var list = records(project);
    var state = stageId == null ? null : waterState(project, stageId);
    var taken = Object.keys(colors).map(function (key) { return colors[key].water; });
    var out = [];
    function add(water, line) {
      var look = waterLook(list, water, state);
      out.push({ color: look.color, fill: tint(look.color, SOIL_TINT), label: look.label,
                 line: line, pattern: null });
    }
    var phreatic = state ? state.phreatic : phreaticLine(list);
    if (phreatic) add('', 'solid');
    else if (taken.indexOf('') >= 0) add('', null);
    (state ? state.heads : headLines(list)).forEach(function (record) {
      add(record.id, 'dashed');
    });
    if (taken.indexOf(INTERPOLATE) >= 0) add(INTERPOLATE, null);
    if (taken.indexOf(DRY) >= 0) add(DRY, null);
    var seen = {};
    Object.keys(colors).forEach(function (key) {
      var entry = colors[key];
      if (String(entry.water).indexOf('uniform:') !== 0 || seen[entry.water]) return;
      seen[entry.water] = true;
      out.push({ color: entry.color, fill: entry.fill, label: entry.label, line: null,
                 pattern: entry.pattern });
    });
    return out;
  }

  /* The right-click menu's choices for the soil `key`: each water it can take, the
     one it takes now ticked, as menu rows carrying `soilKey` and `soilWater`.
     Interpolated is 2D only. */
  function soilWaterMenu(project, key, stageId) {
    var staged = stageId != null;
    var now = soilWaterOf(project, key, stageId);
    var two = !project || project.dimension === 2;
    var state = staged ? waterState(project, stageId) : null;
    var rows = soilWaterChoices(records(project), state).map(function (choice) {
      var interpolate = choice[0] === INTERPOLATE;
      return {
        label: interpolate ? 'Interpolated (above and below)' + (two ? '' : ' — 2D only')
          : choice[0] === DRY ? 'Dry' : choice[1],
        action: staged ? 'stageSoilWater' : 'soilWater', soilKey: key, soilWater: choice[0],
        stageId: staged ? stageId : undefined,
        checked: choice[0] === now, disabled: interpolate && !two
      };
    });
    if (staged) {
      var own = ((App.Stages.chainTo(project, stageId).slice(-1)[0] || {}).soil_water || {});
      rows.push('-');
      rows.push({ label: 'As the stage before', action: 'stageSoilWater', soilKey: key,
                  soilWater: null, stageId: stageId,
                  disabled: !Object.prototype.hasOwnProperty.call(own, key) });
    } else {
      rows.push('-');
      rows.push({ label: 'Uniform pressure…', action: 'soilPressure', soilKey: key });
    }
    return rows;
  }

  /* `Project.soil_water` with the soil `key` taking `water` ('' for the phreatic line).
     A piece of a layer takes its layer's entry unless it has its own, and an entry
     cannot say "the phreatic line": a piece put back on the phreatic line while its
     layer takes another water leaves the layer's entry to its other pieces, by name,
     and the layer none. */
  function withSoilWater(project, key, water) {
    var out = Object.assign({}, (project && project.soil_water) || {});
    var layer = String(key).split('__')[0];
    if (water) {
      out[key] = water;
      return out;
    }
    delete out[key];
    if (layer !== key && out[layer] !== undefined) {
      var inherited = out[layer];
      delete out[layer];
      ((project && project.soil_body_keys) || []).forEach(function (body) {
        if (body !== key && body.split('__')[0] === layer && out[body] === undefined) {
          out[body] = inherited;
        }
      });
    }
    return out;
  }

  /* The right-click's edit: the soil `key` takes `water`, in one PATCH, as
     `kratos-cli boundary soil-water` does. */
  function setSoilWater(key, water) {
    var project = App.PROJECT;
    var name = soilName(project, key);
    var said = water === INTERPOLATE
      ? name + ': water interpolated between the soils above and below.'
      : water === DRY ? name + ' is dry: its water pressure is held at zero.'
      : name + ' takes its water from: ' + waterLook(records(project), water).label + '.';
    return send({ soil_water: withSoilWater(project, key, water) }, said);
  }

  /* ── The water of a stage ────────────────────────────────────────────── */

  function stageName(project, stageId) {
    return ((project.stages || []).filter(function (stage) {
      return stage.id === stageId;
    })[0] || {}).name || stageId;
  }

  /* The stages `list` sent, as every stage edit is (`App.saveStages`, patches.js). */
  function sendStages(list, message) {
    if (App.saveStages) return App.saveStages(list, message);
    return App.Api.patch('/api/project/stages', { stages: list }).then(function (response) {
      App.Model.apply(response.project);
      if (App.Command && App.Command.ok) App.Command.ok(message);
      return App.Viewport.refresh();
    });
  }

  /* The water line `lineId` the phreatic line from stage `stageId` on (null: the stage
     before's), as `kratos-cli stages water ID --phreatic-line` sets it. */
  function setStagePhreatic(stageId, lineId) {
    var project = App.PROJECT;
    var line = find(lineId, project);
    var said = lineId == null
      ? stageName(project, stageId) + ' has the phreatic line of the stage before.'
      : (line ? line.name : lineId) + ' is the phreatic line from ' + stageName(project, stageId)
        + '; every other water line is a head line there.';
    return sendStages(App.Stages.setPhreaticLine(project, stageId, lineId), said);
  }

  /* The soil `key` takes `water` from stage `stageId` on -- '' the phreatic line, null
     the stage before's water -- as `kratos-cli stages soil-water` sets it. */
  function setStageSoilWater(stageId, key, water) {
    var project = App.PROJECT;
    var name = soilName(project, key);
    var where = ' from ' + stageName(project, stageId) + '.';
    var said = water == null ? name + ' takes the water of the stage before' + where
      : water === DRY ? name + ' is dry' + where
      : water === INTERPOLATE ? name + ': water interpolated' + where
      : water === '' ? name + ' takes the phreatic line' + where
      : name + ' takes head line ' + ((find(water, project) || {}).name || water) + where;
    return sendStages(App.Stages.setSoilWater(project, stageId, key, water), said);
  }

  /* The water line `id` the phreatic line of the model as built, every other one a head
     line, as `kratos-cli boundary phreatic` makes it. */
  function makePhreatic(id) {
    var lines = waterLines(records()).map(function (record) { return record.id; });
    var record = find(id);
    if (!record || lines.indexOf(id) < 0) return Promise.resolve(false);
    var all = copy(records()).map(function (item) {
      if (lines.indexOf(item.id) >= 0) {
        item.fluid_pressure_type = item.id === id ? 'Phreatic_Multi_Line' : 'Head_Line';
      }
      return item;
    });
    return saveAll(all, record.name + ' is the phreatic line; every other water line is a '
                   + 'head line, for the soils that take it.');
  }

  /* What a stage gives a condition, in `fields` -- only the values a stage may change --
     over what the stage before gives it: replacing what the stage gave it before. No
     field that differs from the stage before's leaves the stage nothing of its own. */
  function stageValueEdit(project, stageId, record, fields) {
    var parent = (App.Stages.chainTo(project, stageId).slice(-2, -1)[0] || null);
    var inherited = Object.assign({}, record,
                                  parent ? App.Stages.stageValues(project, parent.id)[record.id] || {}
                                         : {});
    var changed = {};
    (STAGE_VALUES[record.kind] || []).forEach(function (field) {
      if (fields[field] === undefined) return;
      if (JSON.stringify(fields[field]) !== JSON.stringify(inherited[field] === undefined
                                                            ? null : inherited[field])) {
        changed[field] = fields[field];
      }
    });
    var cleared = Object.assign({}, project, {
      stages: App.Stages.setValues(project, stageId, record.id, null) });
    return Object.keys(changed).length
      ? App.Stages.setValues(cleared, stageId, record.id, changed) : cleared.stages;
  }

  /* ── The face grid of the dialog: pure ───────────────────────────────── */

  /* The first condition of `kind` on a face (or on the whole soil, `face` null). A head
     line on the whole soil is no row's: it is for the soils that take it. */
  function onFace(list, kind, face) {
    return list.filter(function (record) {
      return record.kind === kind && record.fluid_pressure_type !== 'Head_Line'
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
    // The whole soil's row is the phreatic line on it, when there is one: every soil's
    // water unless it takes another. The head lines are listed with the rest.
    var phreatic = phreaticLine(list);
    var water = (!face && phreatic && phreatic.on === 'domain' && phreatic)
      || onFace(list, 'water_pressure', face);
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
     condition of a kind on one face. */
  function others(project) {
    var shown = {};
    grid(project).forEach(function (row) {
      if (row.supportId) shown[row.supportId] = true;
      if (row.waterId) shown[row.waterId] = true;
      if (row.seepageId) shown[row.seepageId] = true;
    });
    return records(project).filter(function (record) {
      return !shown[record.id] && !heldBySection(record, project);
    });
  }

  /* The conditions after the grid's rows are applied to `project`'s: a row's records are
     changed in place, made, or taken out; every other condition stays as it is. */
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
      if (row.face) {
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
    checkOnePhreatic(list, work);
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

  /* A drawn line's points as a phreatic line, which Kratos reads with x increasing: a
     line drawn from right to left is turned round. */
  function phreaticPoints(points) {
    var out = (points || []).map(function (p) { return [p[0], p[1]]; });
    if (out.length > 1 && out[out.length - 1][0] < out[0][0]) out.reverse();
    return out;
  }

  /* The Boundary conditions window: a row for each face of the model and one for the
     whole soil, the support and the water pressure on each; below them the conditions
     on parts, lines and points, and the water each soil takes. Save writes them all in
     one request. `group` 'mechanical' or 'flow' opens the table of that group's
     conditions instead (`openList`). */
  function open(group) {
    if (GROUPS[group]) return openList(group);
    if (!App.Dialogs || !App.Dialogs.open || !App.PROJECT) return null;
    var project = App.PROJECT;
    var rows = grid(project);
    var controls = [];
    var soils = soilWaterRows(project);
    var soilControls = [];
    var message, shell;

    function read() {
      return rows.map(function (row, i) {
        var c = controls[i];
        var out = Object.assign({}, row);
        if (c.support) {
          out.support = c.support.value;
          out.fixed = c.axes.map(function (box) { return box.checked; });
        }
        out.water = c.water.value;
        out.number = c.number.value.trim();
        out.initial = c.initial.checked;
        return out;
      });
    }

    function submit() {
      var list;
      try { list = applyGrid(App.PROJECT, read()); } catch (error) {
        message.textContent = error.message;
        return null;
      }
      var chosen = applySoilWater(list, soils.map(function (row, i) {
        return Object.assign({}, row, { water: soilControls[i].value });
      }));
      return send({ boundary_conditions: list, soil_water: chosen },
                  'Saved the boundary conditions.').then(function () {
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
        c.water.value = 'none';
        c.sync();
      });
    }

    shell = App.Dialogs.open({
      title: 'Boundary conditions',
      width: 760, height: 560,
      buttons: [
        { label: 'Standard conditions', keepOpen: true, onClick: standard },
        { label: 'Clear', keepOpen: true, onClick: clear },
        { label: 'Add condition…', keepOpen: true, onClick: function () {
          shell.close();
          openRecord(null);
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
        ['Where', 'Support', 'x', 'y', 'z', 'Water pressure', 'Level / value',
         'Initial', ''].forEach(function (text) { head.appendChild(el('th', { text: text })); });
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
          var more = el('button.btn.btn-sm', { type: 'button', text: 'More…' });
          more.addEventListener('click', function () {
            var record = (row.waterId && find(row.waterId))
              || (row.seepageId && find(row.seepageId));
            shell.close();
            if (record) openRecord(record);
            else {
              try {
                openRecord(draftWaterPressure(App.PROJECT, row.face ? 'face' : 'domain', {
                  face: row.face || undefined,
                  fluid_pressure_type: App.PROJECT.water ? 'Hydrostatic' : 'Uniform' }));
              } catch (error) { if (App.Command) App.Command.err(error.message); }
            }
          });
          tr.appendChild(el('td', null, more));
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
            var water = c.water.value;
            c.number.disabled = water === 'none' || water === 'Phreatic_Multi_Line'
              || water === 'seepage';
            c.initial.disabled = water === 'none' || water === 'seepage';
          };
          if (c.support) c.support.addEventListener('change', c.sync);
          c.water.addEventListener('change', c.sync);
          c.sync();
          controls.push(c);
          table.appendChild(tr);
        });
        body.appendChild(table);
        body.appendChild(el('div.mesh-setting-help', { text:
          'Level / value: the level where a hydrostatic pressure is zero [m], or a uniform '
          + 'pressure [' + App.Units.label('stress') + '], compression negative. A new '
          + 'hydrostatic pressure with no level takes the water level. Initial: start '
          + 'values only, which the calculation then changes. Seepage face: water may '
          + 'leave the soil there, in a groundwater flow calculation.' }));

        var rest = others(project);
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
          edit.addEventListener('click', function () { shell.close(); openRecord(record); });
          var del = el('button.btn.btn-sm', { type: 'button', text: 'Delete' });
          del.addEventListener('click', function () { shell.close(); remove(record.id); });
          item.appendChild(edit);
          item.appendChild(del);
          list.appendChild(item);
        });
        body.appendChild(list);

        body.appendChild(el('div.bc-heading', { text: 'Soil water' }));
        var choices = soilWaterChoices(records(project));
        var waters = el('table.bc-grid.bc-soil-water');
        soils.forEach(function (row) {
          var tr = el('tr');
          // The colour the Flow conditions tab fills this soil with.
          var swatch = el('span.bc-water-swatch');
          var name = el('td');
          name.appendChild(swatch);
          name.appendChild(document.createTextNode(row.label));
          tr.appendChild(name);
          var select = options(el('select.bc-soil-water-choice'), choices, '');
          select.value = choices.some(function (choice) { return choice[0] === row.water; })
            ? row.water : '';
          select.setAttribute('aria-label', 'Water of ' + row.label);
          function paint() {
            var look = waterLook(records(project), select.value);
            swatch.style.background = tint(look.color, SOIL_TINT);
            swatch.style.borderColor = look.color;
            swatch.title = look.label;
          }
          select.addEventListener('change', paint);
          paint();
          tr.appendChild(el('td', null, select));
          soilControls.push(select);
          waters.appendChild(tr);
        });
        if (!soils.length) {
          body.appendChild(el('div.mesh-setting-help', { text: 'No soil yet.' }));
        } else {
          body.appendChild(waters);
        }
        body.appendChild(el('div.mesh-setting-help', { text:
          'The water each soil takes: the phreatic line, by default; a head line, for an '
          + 'aquifer, which acts only on the soils that take it; or interpolated between '
          + 'the soils above and below, for an aquitard (2D only). A project has one '
          + 'phreatic line; draw the other lines as water pressures of the type Head line. '
          + 'Only the phreatic line puts water on the ground.' }));

        message = el('div.mesh-settings-message');
        body.appendChild(message);
      }
    });
    return shell;
  }

  /* ── The tables of the mechanical and the flow conditions ─────────────── */

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
    if (record.kind === 'flux') {
      return Object.assign(row, { condition: 'Flux', type: NO_VALUE,
                                  value: plain(record.value) + ' ' + fluxUnit() + ' in',
                                  cutoff: NO_VALUE, initial: NO_VALUE });
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

  /* What a support holds, as table cells: its kind (Fixed: every component the model
     has; Roller: the one normal to its face or line; else Custom) and the components.
     A 2D section never holds z, so z is left out there. */
  function supportRow(record, project) {
    var axes = project && project.dimension === 2 ? [0, 1] : [0, 1, 2];
    var held = axes.filter(function (i) { return record.fixed[i]; });
    var roller = null;
    try { roller = normal(record.on, record.face, record.points); } catch (error) {
      roller = null;
    }
    var kind = held.length === axes.length ? 'Fixed'
      : held.length === 1 && held[0] === roller ? 'Roller'
      : held.length ? 'Custom' : 'Free';
    return { id: record.id, name: record.name, active: record.active !== false,
             where: whereCell(record, project), support: kind,
             fixed: held.length ? held.map(function (i) { return AXES[i]; }).join(', ')
                                : NO_VALUE };
  }

  /* The conditions of `group` the model has, in the order they were added, as table
     rows. The front and back supports of a 2D section are left out, as
     `kratos-cli boundary list` leaves them out. */
  function groupRows(project, group) {
    return records(project).filter(function (record) {
      return groupOf(record.kind) === group && !heldBySection(record, project);
    }).map(function (record) {
      return group === 'mechanical' ? supportRow(record, project) : flowRow(record, project);
    });
  }

  function flowRows(project) { return groupRows(project, 'flow'); }

  function mechanicalRows(project) { return groupRows(project, 'mechanical'); }

  var LIST_COLUMNS = {
    mechanical: [['name', 'Name'], ['where', 'Where'], ['support', 'Support'],
                 ['fixed', 'Fixed in']],
    flow: [['name', 'Name'], ['condition', 'Condition'], ['where', 'Where'],
           ['type', 'Type'], ['value', 'Level / value'], ['cutoff', 'Tension cut-off'],
           ['initial', 'Initial only']]
  };

  var LIST_HELP = {
    mechanical: 'A support holds the displacement at zero in the components of Fixed in. '
      + 'Fixed: all components. Roller: the component normal to its face or line. '
      + 'Standard conditions puts back the bottom fixed and the sides on rollers.',
    flow: 'Level / value: where a hydrostatic pressure is zero, the points of a phreatic '
      + 'line, or a uniform pressure (compression negative). Initial only: start values, '
      + 'which the calculation then changes. Seepage face: water may leave the soil there, '
      + 'in a groundwater flow calculation. Flux: water flows into the soil at the value '
      + '(negative: out of it).'
  };

  var LIST_EMPTY = {
    mechanical: 'The model has no supports yet. Click Add condition… to add one, or '
      + 'Standard conditions for the bottom fixed and the sides on rollers.',
    flow: 'The model has no flow conditions yet. Click Add condition… to add a water '
      + 'pressure, a seepage face or a flux.'
  };

  /* The window of one group's conditions: a table with one row for each condition of
     the model, an Active check box, Edit… and Delete; Add condition… opens a new one.
     The supports' window also puts back the standard supports. */
  function openList(group) {
    if (!App.Dialogs || !App.Dialogs.open || !App.PROJECT) return null;
    var project = App.PROJECT;
    var rows = groupRows(project, group);
    var columns = LIST_COLUMNS[group];
    var shell;
    var buttons = [
      { label: 'Add condition…', keepOpen: true, onClick: function () {
        shell.close();
        openRecord(null, group);
      } },
      { label: 'Close' }
    ];
    if (group === 'mechanical') {
      buttons.unshift({ label: 'Standard conditions', keepOpen: true, onClick: function () {
        shell.close();
        return applyStandard().then(function () { return openList(group); });
      } });
    }
    shell = App.Dialogs.open({
      title: GROUPS[group].title,
      width: group === 'flow' ? 900 : 700, height: 480,
      buttons: buttons,
      build: function (host) {
        var body = el('div.mesh-settings-body.boundary-conditions');
        host.appendChild(body);
        if (!rows.length) {
          body.appendChild(el('div.mesh-setting-help', { text: LIST_EMPTY[group] }));
          return;
        }
        var table = el('table.bc-grid.bc-list');
        var head = el('tr');
        columns.map(function (column) { return column[1]; }).concat(['Active', ''])
          .forEach(function (text) { head.appendChild(el('th', { text: text })); });
        table.appendChild(head);
        rows.forEach(function (row) {
          var tr = el('tr');
          columns.forEach(function (column) {
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
            openRecord(find(row.id), group);
          });
          var del = el('button.btn.btn-sm', { type: 'button', text: 'Delete' });
          del.addEventListener('click', function () { shell.close(); remove(row.id); });
          actions.appendChild(edit);
          actions.appendChild(del);
          tr.appendChild(actions);
          table.appendChild(tr);
        });
        body.appendChild(table);
        var notes = [LIST_HELP[group]];
        if (group === 'mechanical') {
          if (records(project).some(function (record) { return heldBySection(record, project); })) {
            notes.push(SECTION_NOTE);
          }
          if (records(project).some(function (record) { return unusedInFlow(record, project); })) {
            notes.push(FLOW_NOTE);
          }
        }
        body.appendChild(el('div.mesh-setting-help', { text: notes.join(' ') }));
      }
    });
    return shell;
  }

  /* One condition, asked in the dialog's two steps: where (Whole soil / Face / Part /
     Line / Point, then which one) and what (a support, a water pressure with the
     fields of its type, a seepage face, or a flux). `null` makes a new one. `group`
     ('mechanical' or 'flow') offers only that group's kinds; a given condition keeps to
     its own group.

     With `stageId`, the condition's values in that stage (`Stage.condition_values`):
     only what a stage may change (`STAGE_VALUES`) can be edited, and Save gives the
     stage those values over what the stage before gives it, as
     `kratos-cli stages value` does; "As the stage before" takes them back.

     `soil` (`{ title }`): a uniform pressure on one soil, already picked; the window
     asks only its name, value, Initial only and Active (`openSoilPressure`). */
  function openRecord(source, group, stageId, soil) {
    if (!App.Dialogs || !App.Dialogs.open || !App.PROJECT) return null;
    var project = App.PROJECT;
    var SOIL_ROWS = ['name', 'value', 'initial', 'active', 'message'];
    var staged = stageId != null && !!source && !!STAGE_VALUES[source.kind]
      && !!App.Stages && !!find(source.id);
    var record = source ? copy(source) : null;
    if (staged) {
      record = Object.assign(record, App.Stages.stageValues(project, stageId)[source.id] || {});
    }
    var known = !!(source && find(source.id));
    if (source) group = groupOf(source.kind);
    if (!GROUPS[group]) group = null;
    var kinds = KIND_CHOICES.filter(function (choice) { return inGroup(choice[0], group); });
    var c = {};
    var message, shell;
    // The phreatic line last filled in from the points: while the field still holds it
    // (or nothing), it follows the points; a line typed by hand is left alone.
    var autoPhreatic = null;

    function phreaticFollows() {
      var typed = c.phreatic.value.trim();
      return typed === '' || typed === autoPhreatic;
    }

    /* A water pressure on a line with a phreatic line: the phreatic line is the drawn
       line's points, x increasing, unless one of its own was typed. */
    function followPoints() {
      if (!c.phreatic || c.kind.value !== 'water_pressure' || c.on.value !== 'line'
          || LINE_TYPES.indexOf(c.type.value) < 0 || !phreaticFollows()) return;
      var points = parsePoints(c.points.value);
      if (!points || points.length < 2) return;
      autoPhreatic = c.phreatic.value = pointsText(phreaticPoints(points));
    }

    function submit() {
      followPoints();
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
        } else if (kind === 'flux') {
          var rate = Number(c.flux.value || 0);
          if (!isFinite(rate)) throw new Error('The flux must be a number.');
          made = draftFlux(project, on, Object.assign({
            id: record ? record.id : undefined, value: rate }, where));
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
          if (LINE_TYPES.indexOf(type) >= 0) {
            var phreatic = parsePoints(c.phreatic.value);
            if (!phreatic || phreatic.length < 2) {
              throw new Error('A ' + TYPE_LABELS[type].toLowerCase() + ' needs two points '
                              + 'or more, x y, x y.');
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
      if (staged) {
        var fields = {};
        STAGE_VALUES[source.kind].forEach(function (field) {
          if (made[field] !== undefined) fields[field] = made[field];
        });
        return sendStages(stageValueEdit(project, stageId, source, fields),
                          source.name + ' has its values in ' + stageName(project, stageId)
                          + '.').then(function () { shell.close(); }, function (error) {
          message.textContent = error.message;
        });
      }
      var selected = App.Stages && App.Stages.selectedId
        ? App.Stages.selectedId(project, App.state && App.state.phase) : null;
      var phreaticEdit = stagedPhreatic(project, made, selected);
      if (phreaticEdit) {
        phreaticEdit.stageName = (project.stages.filter(function (stage) {
          return stage.id === selected;
        })[0] || {}).name || selected;
      }
      try {
        checkOnePhreatic(records().filter(function (item) {
          return item.id !== made.id;
        }).concat([made]), project);
        if (!phreaticEdit) checkInitialPhreatic(project, made, selected);
      } catch (error) { message.textContent = error.message; return null; }
      return save(made, phreaticEdit).then(function () { shell.close(); }, function (error) {
        message.textContent = error.message;
      });
    }

    function pick() {
      if (!App.DrawInput || !App.DrawInput.start) return;
      var on = c.on.value;
      var kind = c.kind.value;
      // The kind and the pressure type chosen in the form come back with the drawn
      // points; a phreatic line that followed the old points follows the new ones.
      var type = c.type.value;
      var follows = phreaticFollows();
      shell.close();
      App.DrawInput.start(on === 'point' ? 'load' : 'line', {
        count: 1, atPointer: true,
        onComplete: function (points) {
          var next = record && record.kind === kind ? copy(record) : { kind: kind };
          next.on = on;
          next.points = points.map(function (p) { return [p[0], p[1]]; });
          if (kind === 'water_pressure') {
            next.fluid_pressure_type = type;
            if (follows) {
              next.x_coordinates = null;
              next.y_coordinates = null;
              next.z_coordinates = null;
            }
          }
          openRecord(Object.assign(blank(kind, on), next), group);
        }
      });
    }

    function blank(kind, on) {
      try {
        if (kind === 'seepage') {
          return draftSeepage(project, on === 'face' ? 'face' : 'line',
                              on === 'face' ? { face: 'right' } : {});
        }
        if (kind === 'flux') {
          return draftFlux(project, on === 'line' ? 'line' : 'face',
                           on === 'line' ? {} : { face: 'left' });
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

    var buttons = staged
      ? [{ label: 'As the stage before', onClick: function () {
            return sendStages(App.Stages.setValues(project, stageId, source.id, null),
                              source.name + ' has the values of the stage before in '
                              + stageName(project, stageId) + '.');
          } },
         { label: 'Save', primary: true, keepOpen: true, onClick: submit },
         { label: 'Cancel' }]
      : [{ label: 'Pick on model…', onClick: pick },
         { label: 'Save', primary: true, keepOpen: true, onClick: submit },
         { label: 'Cancel' }];
    if (soil && !staged) buttons = buttons.slice(1);
    shell = App.Dialogs.open({
      title: staged ? source.name + ' in ' + stageName(project, stageId)
        : soil ? soil.title
        : (known ? 'Edit' : 'Create') + ' boundary condition',
      width: 600, height: soil ? 340 : 620,
      buttons: buttons,
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
          + 'in a groundwater flow calculation. A flux, there too, lets water in at a rate.';
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
          return [t, TYPE_LABELS[t]];
        }), water.fluid_pressure_type || 'Hydrostatic');
        row('type', 'Type', c.type, 'Uniform: one value. Hydrostatic: zero at its level, '
            + 'growing with depth. Phreatic line: hydrostatic below a line, the water of '
            + 'every soil; one a stage. Head line: the same, for the soils that take '
            + 'it under Soil water.');
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
        row('phreatic', 'Phreatic line', c.phreatic, 'x y, x y … [m], x increasing. On a '
            + 'line, filled in from its points until you type one of your own.');
        autoPhreatic = record.points ? pointsText(phreaticPoints(record.points)) : null;
        c.flux = number(record.kind === 'flux' ? record.value : 0);
        row('flux', 'Flux', c.flux, 'Water flowing into the soil per unit area of its '
            + 'boundary [' + fluxUnit() + ']; negative flows out.');
        c.cutoff = number(water.pressure_tension_cut_off || 0);
        row('cutoff', 'Tension cut-off', c.cutoff, 'The most suction above the level ['
            + App.Units.label('stress') + ']; 0 holds it at zero.');
        c.initial = el('input.mesh-setting-control', { type: 'checkbox' });
        c.initial.checked = water.is_fixed === false;
        // A new phreatic line is the soil's initial pressure: start values, until the
        // user says otherwise.
        var initialChosen = known;
        c.initial.addEventListener('change', function () { initialChosen = true; });
        row('initial', 'Initial only', c.initial, 'Start values, which the calculation '
            + 'then changes. A phreatic line is written so in the stage it comes on, and '
            + 'the ground under its water is fixed to it.');

        c.active = el('input.mesh-setting-control', { type: 'checkbox' });
        c.active.checked = record.active !== false;
        row('active', 'Active', c.active, 'Inactive conditions stay in the project but are '
            + 'not exported.');
        message = el('div.mesh-settings-message');
        row('message', '', message, '');

        function sync() {
          var support = c.kind.value === 'displacement';
          var seepage = c.kind.value === 'seepage';
          var flux = c.kind.value === 'flux';
          var water = !support && !seepage && !flux;
          show('flux', flux);
          var on = c.on.value;
          var type = c.type.value;
          show('face', on === 'face');
          show('part', on === 'part');
          show('points', on === 'line' || on === 'point');
          show('axes', support);
          ['type', 'cutoff', 'initial'].forEach(function (key) { show(key, water); });
          show('value', water && type === 'Uniform');
          show('level', water && type === 'Hydrostatic');
          show('phreatic', water && LINE_TYPES.indexOf(type) >= 0);
          rows.phreatic[0].textContent = type === 'Head_Line' ? 'Head line' : 'Phreatic line';
          show('cutoff', water && type !== 'Uniform');
          if (water && !initialChosen) {
            c.initial.checked = type === 'Phreatic_Multi_Line'
              && LINE_TARGETS.indexOf(on) >= 0;
          }
          if (soil) {
            // The soil and the uniform type are known: the rest stays out of sight.
            Object.keys(rows).forEach(function (key) {
              show(key, SOIL_ROWS.indexOf(key) >= 0);
            });
          }
          followPoints();
        }
        [c.kind, c.on, c.type].forEach(function (control) {
          control.addEventListener('change', sync);
        });
        ['input', 'change'].forEach(function (event) {
          c.points.addEventListener(event, followPoints);
        });
        sync();
        if (staged) {
          // A stage changes values, never what a condition is or where it acts.
          [c.name, c.kind, c.on, c.face, c.part, c.points, c.type, c.initial, c.active]
            .concat(c.axes).forEach(function (control) { control.disabled = true; });
          message.textContent = 'The values from ' + stageName(project, stageId)
            + ' on; the stages after it keep theirs.';
        }
      }
    });
    return shell;
  }

  /* ── The Flow conditions rail's tools ────────────────────────────────── */

  function inSection(project, what) {
    if (!project) return false;
    if (project.dimension !== 2) {
      if (App.Command) App.Command.note(what + ' drawn in the 2D section; switch to 2D.');
      return false;
    }
    return !!(App.DrawInput && App.DrawInput.start);
  }

  /* Draw water line: a line through the clicked points on the whole soil, saved as it
     is drawn -- the phreatic line if the model has no water line yet, else a head line
     for the soils that take it (`draftWaterLine`), as `kratos-cli boundary water-line`. */
  function drawWaterLine() {
    var project = App.PROJECT;
    if (!inSection(project, 'Water lines are')) return;
    App.DrawInput.start('line', {
      noun: 'water line',
      onComplete: function (points) {
        var record;
        try { record = draftWaterLine(App.PROJECT, points); } catch (error) {
          if (App.Command) App.Command.err(error.message);
          return null;
        }
        var phreatic = record.fluid_pressure_type === 'Phreatic_Multi_Line';
        return save(record).then(function () {
          if (App.Command && App.Command.ok) {
            App.Command.ok(record.name + (phreatic
              ? ' is the phreatic line: the water of every soil that takes no other.'
              : ' is a head line: right-click a soil > Water to give it to that soil, or '
                + 'right-click the line > Make phreatic line.'));
          }
          return record;
        });
      }
    });
  }

  /* The lines of the soil's geometry as built (`App.SurfaceWater.geometryLines`): its
     outer boundary and the lines between its bodies. Empty before a build. */
  function soilLines(project) {
    var sections = App.Viewport && App.Viewport.builtSections
      ? App.Viewport.builtSections() : null;
    if (!sections || !project || !App.SurfaceWater || !App.SurfaceWater.geometryLines) {
      return [];
    }
    return App.SurfaceWater.geometryLines(sections, App.SurfaceWater.soilKeys(project));
  }

  /* What DrawInput moves each point of a flow boundary condition with (its `snapPoint`):
     onto the nearest point of a line of the soil's geometry -- its outer boundary, or a
     line between two of its bodies -- however far off it was clicked, since the
     condition is nowhere else; then, with snapping on (`step`, the status bar's snapping
     distance), along the line to a corner or a grid line of `step` within `step`
     (`App.SurfaceWater.snapOnto`). Null when the model has no soil to draw on. */
  function boundarySnapper(project) {
    var edges = soilLines(project);
    if (!edges.length) return null;
    var corners = App.SurfaceWater.corners(edges);
    return function (point, step) {
      var near = App.SurfaceWater.snapOnto(edges, corners, point[0], point[1], step);
      return near ? near.point : null;
    };
  }

  var FLOW_TYPES = {
    line: [['seepage', 'Seepage face'], ['flux', 'Flux'], ['Hydrostatic', 'Hydrostatic'],
           ['Uniform', 'Uniform']],
    point: [['Hydrostatic', 'Hydrostatic'], ['Uniform', 'Uniform']]
  };

  /* Whether the line `points` is off the soil's outer boundary -- along a line between
     two bodies, or across the soil -- where a seepage face and a flux cannot be (writer
     `_edge_conditions`). False when it is on the boundary, or the model is not built and
     it cannot be told. */
  function insideSoil(project, points) {
    var outer = soilLines(project).filter(function (edge) { return edge.outer; });
    return outer.length > 0 && !App.SurfaceWater.runsAlong(outer, points);
  }

  /* The level a new hydrostatic condition at `points` is given: the project's water
     level, else the phreatic line's above their middle, else the ground's. */
  function levelAt(project, points) {
    if (project.water) return project.water.y;
    var line = phreaticLine(records(project));
    var x = points.reduce(function (sum, p) { return sum + p[0]; }, 0) / points.length;
    if (line && App.SurfaceWater) return App.SurfaceWater.level(line, x);
    return project.domain.y_top;
  }

  /* `{record}` -- a seepage face, a flux, or a fixed water pressure -- on the drawn
     line or point, from what the flow boundary dialog chose (`draftSeepage`,
     `draftFlux`, `draftWaterPressure`). */
  function flowBoundary(project, on, points, type, number) {
    var where = { points: points };
    if (type === 'seepage') return draftSeepage(project, 'line', where);
    if (type === 'flux') return draftFlux(project, 'line', Object.assign({ value: number }, where));
    return draftWaterPressure(project, on, Object.assign(
      type === 'Hydrostatic' ? { reference_coordinate: number } : { value: number },
      { fluid_pressure_type: type }, where));
  }

  /* The drawn `points` ([x, y]) with a point that repeats the one before it dropped: two
     clicks on one spot (a double click) land on the same point of the boundary. */
  function distinctPoints(points) {
    return points.filter(function (p, i) {
      return i === 0 || p[0] !== points[i - 1][0] || p[1] !== points[i - 1][1];
    });
  }

  /* Create flow boundary condition: click points on the soil's boundary, each moved onto
     it (`boundarySnapper`), and finish (right-click or Enter). One point is a condition
     at that point, more a line through them; then what it is. */
  function drawFlowBoundary() {
    var project = App.PROJECT;
    if (!inSection(project, 'Flow boundary conditions are')) return;
    var snapper = boundarySnapper(project);
    if (!snapper) {
      if (App.Command) {
        App.Command.err('There is no soil to draw a flow boundary condition on: the model '
                        + 'has no soil, or it is not built yet.');
      }
      return;
    }
    App.DrawInput.start('line', {
      minPoints: 1, snapPoint: snapper,
      noun: 'flow boundary condition (one point for a point, more for a line)',
      onComplete: function (points) {
        var drawn = distinctPoints(points.map(function (p) { return [p[0], p[1]]; }));
        openFlowBoundary(drawn.length === 1 ? 'point' : 'line', drawn);
      }
    });
  }

  /* What the drawn line or point is: a seepage face, a flux, a hydrostatic or a
     uniform water pressure, with the one number it needs. */
  function openFlowBoundary(on, points) {
    if (!App.Dialogs || !App.Dialogs.open || !App.PROJECT) return null;
    var project = App.PROJECT;
    var c = {};
    var message, shell;
    function needs(type) {
      return type === 'flux' ? ['Flux', fluxUnit() + ', into the soil; negative flows out', 0]
        : type === 'Hydrostatic' ? ['Level', 'm: where the pressure is zero',
                                    levelAt(project, points)]
        : type === 'Uniform' ? ['Pressure', App.Units.label('stress')
                                + ', compression negative', 0]
        : null;
    }
    function submit() {
      var type = c.type.value;
      var number = Number(c.number.value || 0);
      var made;
      try {
        if (needs(type) && !isFinite(number)) throw new Error('Give a number.');
        made = flowBoundary(project, on, points, type, number);
      } catch (error) { message.textContent = error.message; return null; }
      var typed = c.name.value.trim();
      if (typed) made.name = typed;
      return save(made).then(function () { shell.close(); }, function (error) {
        message.textContent = error.message;
      });
    }
    shell = App.Dialogs.open({
      title: 'Flow boundary condition',
      width: 460, height: 340,
      buttons: [{ label: 'Save', primary: true, keepOpen: true, onClick: submit },
                { label: 'Cancel' }],
      build: function (body) {
        body.classList.add('mesh-settings-body');
        var form = el('div.mesh-settings-form');
        body.appendChild(form);
        function row(text, control, help) {
          var parts = [el('label.mesh-setting-label', { text: text }), control,
                       el('div.mesh-setting-help', { text: help || '' })];
          parts.forEach(function (part) { form.appendChild(part); });
          return parts;
        }
        form.appendChild(el('div.mesh-setting-help', {
          text: (on === 'point' ? 'At ' : 'Along ') + points.map(xy).join(' → ') }));
        // A line inside the soil takes a water pressure only.
        var inner = on === 'line' && insideSoil(project, points);
        var types = inner ? FLOW_TYPES.point : FLOW_TYPES[on];
        c.type = options(el('select.mesh-setting-control'), types, types[0][0]);
        row('Condition', c.type, on === 'point'
          ? 'A seepage face and a flux are on a line of the boundary.'
          : inner
            ? 'This line is inside the soil: a seepage face and a flux are on its outer '
              + 'boundary only. Hydrostatic and Uniform fix the water pressure.'
            : 'Seepage: water may leave the soil here. Flux: water flows in at a rate. '
              + 'Hydrostatic and Uniform fix the water pressure.');
        c.number = el('input.mesh-setting-control', { type: 'number', step: 'any' });
        var numberRow = row('', c.number, '');
        c.name = el('input.mesh-setting-control', { type: 'text', value: '' });
        row('Name', c.name, 'Empty: a name of its own.');
        message = el('div.mesh-settings-message');
        form.appendChild(message);
        function sync() {
          var need = needs(c.type.value);
          numberRow.forEach(function (part) { part.style.display = need ? '' : 'none'; });
          if (!need) return;
          numberRow[0].textContent = need[0];
          numberRow[2].textContent = need[1];
          c.number.value = String(need[2]);
        }
        c.type.addEventListener('change', sync);
        sync();
      }
    });
    return shell;
  }

  /* Uniform soil pressure: click a soil, give its pressure. A fixed uniform water
     pressure on that soil part, which a stage switches and may give another value. */
  function pickSoilPressure() {
    var project = App.PROJECT;
    if (!inSection(project, 'A soil is picked')) return;
    App.DrawInput.start('load', {
      count: 1, atPointer: true, noun: 'soil to set a uniform pressure on',
      onComplete: function (points) {
        var sections = App.Viewport && App.Viewport.builtSections
          ? App.Viewport.builtSections() : null;
        var key = App.SurfaceWater && sections
          ? App.SurfaceWater.soilAt(sections, App.SurfaceWater.soilKeys(App.PROJECT),
                                    points[0][0], points[0][1])
          : null;
        if (!key) {
          if (App.Command) App.Command.err('There is no soil there: click inside a soil.');
          return;
        }
        openSoilPressure(key);
      }
    });
  }

  /* The uniform water pressure of the soil `key`: the one it has, or a new one. The
     soil and the type are known, so the window asks only the name, the value, Initial
     only and Active. */
  function openSoilPressure(key) {
    var project = App.PROJECT;
    var own = records(project).filter(function (record) {
      return record.kind === 'water_pressure' && record.on === 'part' && record.part === key
        && record.fluid_pressure_type === 'Uniform';
    })[0];
    var record = own ? copy(own) : draftWaterPressure(project, 'part', {
      part: key, fluid_pressure_type: 'Uniform', value: 0,
      name: soilName(project, key) + ' pressure' });
    if (!own && soilPartKeys(project).indexOf(key) < 0) {
      // A body of a layer the part list names by its layer.
      record.part = String(key).split('__')[0];
    }
    return openRecord(record, 'flow', null, {
      title: 'Uniform pressure on ' + soilName(project, key) });
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
    flowRows: flowRows, mechanicalRows: mechanicalRows,
    phreaticPoints: phreaticPoints,
    INTERPOLATE: INTERPOLATE, waterLines: waterLines, phreaticLine: phreaticLine,
    headLines: headLines,
    checkOnePhreatic: checkOnePhreatic, phreaticLines: phreaticLines, soilWaterChoices: soilWaterChoices,
    stagedPhreatic: stagedPhreatic, checkInitialPhreatic: checkInitialPhreatic,
    soilWaterRows: soilWaterRows, applySoilWater: applySoilWater,
    DRY: DRY, STAGE_VALUES: STAGE_VALUES, DRY_COLOR: DRY_COLOR, UNIFORM_COLOR: UNIFORM_COLOR,
    draftFlux: draftFlux, draftWaterLine: draftWaterLine, waterState: waterState,
    soilPressureOf: soilPressureOf, makePhreatic: makePhreatic,
    setStagePhreatic: setStagePhreatic, setStageSoilWater: setStageSoilWater,
    stageValueEdit: stageValueEdit, flowBoundary: flowBoundary, levelAt: levelAt,
    drawWaterLine: drawWaterLine, drawFlowBoundary: drawFlowBoundary,
    openFlowBoundary: openFlowBoundary, pickSoilPressure: pickSoilPressure,
    openSoilPressure: openSoilPressure, boundarySnapper: boundarySnapper,
    PHREATIC_COLOR: PHREATIC_COLOR, INTERPOLATE_COLOR: INTERPOLATE_COLOR,
    NO_WATER_COLOR: NO_WATER_COLOR, HEAD_COLORS: HEAD_COLORS, tint: tint,
    waterLineColor: waterLineColor, soilWaterOf: soilWaterOf,
    soilWaterShown: soilWaterShown, soilWaterColors: soilWaterColors,
    waterLegend: waterLegend, soilWaterMenu: soilWaterMenu, withSoilWater: withSoilWater,
    setSoilWater: setSoilWater, soilName: soilName,
    isConditionKey: isConditionKey, find: find,
    save: save, remove: remove, applyStandard: applyStandard,
    activeState: activeState, setActive: setActive,
    open: open, openRecord: openRecord, draw: draw, edit: edit
  };
})();
