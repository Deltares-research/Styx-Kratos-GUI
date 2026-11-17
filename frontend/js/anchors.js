/* ══════════════════════════════════════════════════════════════════
   anchors.js — Structure-mode anchors.

   An anchor is a two-node tie from a head to a tail, and needs no structure.
   A head within SNAP_DISTANCE of a sheet pile is snapped onto it and shares the
   beam's node; a head further away is a node of the soil mesh. What the tail is
   joined to is the anchor's `tail_end`: a free tail (a new anchor's) is a node
   of the soil mesh, so the tie pulls on the soil there; a fixed tail belongs to
   no element at all and is restrained by its own node group, the formulation
   Kratos' reference decks use, which idealises the grouted body as a fixed
   point.

   The Create anchor tool and the Edit anchor… button open one window (`open`),
   as the sheet pile's do.

   In the solid model the same tie may hang from a wall panel or a member, in
   three dimensions: `kind: "anchor3d"`, head snapped onto the swept surface of a
   wall or the polyline of a member. The formulation is identical -- only the
   dimension of the points, and what the head may sit on, differ.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Anchors = (function () {

  /* How far the model reaches, which is not the same as the domain: a drawn
     or imported part may stand above `y_top`, and a structure placed on one is on
     model geometry. `App.Model.extentOf` mirrors the server's `Project.extent`; the
     fallback keeps this module usable in a page that has no App.Model. */
  function extent(project) {
    return (App.Model && App.Model.extentOf)
      ? App.Model.extentOf(project)
      : (project && project.domain);
  }


  /* A four-strand tendon at 2.5 m centres, a Kratos property set in the project's
     units (App.PropertySets). Its 900 kN working limit is a design value the deck
     cannot carry, stated in the project's force unit. A starting point the user edits. */
  function defaultSection() {
    return Object.assign({ name: 'Anchor tendon', spacing: 2.5,
                           tension_limit: App.Units.fromSI(900000, 'force'),
                           compression_limit: null },
                         App.PropertySets.defaults('anchor'));
  }

  var SNAP_DISTANCE = 1.0;   // metres from a pile within which a head is snapped onto it

  function copy(value) { return JSON.parse(JSON.stringify(value)); }

  function collection() { return App.ANCHORS || []; }

  function sections() {
    return App.ANCHOR_SECTIONS || (App.PROJECT && App.PROJECT.anchor_sections) || [];
  }

  function storedAnchors() {
    return (App.PROJECT && App.PROJECT.anchors) || collection();
  }

  function storedLoads() {
    return (App.PROJECT && App.PROJECT.loads) || [];
  }

  /* Whether a project's anchors are drawn in a section or in space, which decides
     both the shape of their points and what they may hang from. */
  function spatial(project) { return !!project && project.dimension !== 2; }

  /* The structures of this project's own dimension that an anchor may hang from: a
     sheet pile in a section, a wall or a member in the solid model. */
  function livePiles(project) {
    var wanted = spatial(project) ? ['panel', 'member'] : ['beam'];
    return ((project && project.beams) || []).filter(function (beam) {
      return beam.active !== false && wanted.indexOf(beam.kind || 'beam') >= 0;
    });
  }

  /* An anchor needs no structure, so any open project may have one. */
  function available(project) {
    return !!project;
  }

  /* Whether the head of `anchor` is on a live structure of its own kind -- a sheet
     pile for a 2D anchor, a wall or a member for a 3D one -- whose node it then
     shares (core/model/schemas.py `Project.anchor_on_structure`). */
  function onStructure(project, anchor) {
    var wanted = anchor.kind === 'anchor3d' ? ['panel', 'member'] : ['beam'];
    return ((project && project.beams) || []).some(function (beam) {
      if (beam.active === false || wanted.indexOf(beam.kind || 'beam') < 0) return false;
      var found = beam.kind === 'panel' ? nearestOnPanel(beam, anchor.head)
                                        : nearestOnPolyline(beam.points || [], anchor.head);
      return !!found && found.distance <= 1e-6;
    });
  }

  /* The closest point on a polyline, in however many dimensions it is given. */
  function nearestOnPolyline(points, point) {
    var best = null;
    for (var i = 1; i < (points || []).length; i += 1) {
      var a = points[i - 1], b = points[i];
      var delta = a.map(function (value, axis) { return b[axis] - value; });
      var lengthSquared = delta.reduce(function (sum, d) { return sum + d * d; }, 0);
      if (!lengthSquared) continue;
      var t = a.reduce(function (sum, value, axis) {
        return sum + (point[axis] - value) * delta[axis];
      }, 0) / lengthSquared;
      t = Math.max(0, Math.min(1, t));
      var on = a.map(function (value, axis) { return value + t * delta[axis]; });
      var away = Math.sqrt(on.reduce(function (sum, value, axis) {
        return sum + (point[axis] - value) * (point[axis] - value);
      }, 0));
      if (!best || away < best.distance) best = { point: on, distance: away };
    }
    return best;
  }

  /* The closest point on a wall's swept surface. The sweep is vertical, so this
     splits: the plan position rides on the footprint, and the level is simply
     clamped between the wall's own two. */
  function nearestOnPanel(panel, point) {
    var plan = nearestOnPolyline(panel.footprint, [point[0], point[2]]);
    if (!plan) return null;
    var y = Math.max(panel.y_toe, Math.min(panel.y_top, point[1]));
    var on = [plan.point[0], y, plan.point[1]];
    return { point: on, distance: Math.hypot(plan.distance, point[1] - y) };
  }

  /* The closest point on any live structure, with how far away it was. Snapping is
     what turns a rough click into the shared node the export depends on. */
  function nearestOnPile(project, point) {
    var best = null;
    livePiles(project).forEach(function (beam) {
      var found = beam.kind === 'panel'
        ? nearestOnPanel(beam, point)
        : nearestOnPolyline(beam.points || [], point);
      if (found && (!best || found.distance < best.distance)) best = found;
    });
    return best;
  }

  function nextId(list, prefix) {
    var used = {};
    (list || []).forEach(function (item) { used[item.id] = true; });
    var number = 1;
    while (used[prefix + number]) number += 1;
    return prefix + number;
  }

  function unavailableMessage() {
    return 'Open or create a project first.';
  }

  /* A picked point in the dimension this project's anchors live in: `(x, z)` in a
     section, `(x, y, z)` in space. The drawing tools always hand over three
     numbers, so the section drops the one it has no room for. */
  function nativePoint(project, point) {
    return spatial(project)
      ? [point[0], point[1] === undefined ? 0 : point[1],
         point[2] === undefined ? 0 : point[2]]
      : [point[0], point[1]];
  }

  function insideDomain(project, point) {
    // The extent, not the domain: an anchor may be tied into a drawn embankment that
    // stands above `y_top`. Mirrors the server's `Project.extent`. In a section the top
    // is free: a strut from the part of a pile above the ground ends at a fixed point
    // in the air.
    // By the point's own width: a 2D anchor kept in a 3D project is still checked as
    // drawn, in its section, as the server does.
    var d = extent(project);
    if (point.length === 2) {
      return point[0] >= d.x0 && point[0] <= d.x1 && point[1] >= d.y_bottom;
    }
    return point[0] >= d.x0 && point[0] <= d.x1
      && point[1] >= d.y_bottom && point[1] <= d.y_top
      && point[2] >= d.z0 && point[2] <= d.z1;
  }

  /* `tailEnd` is what the tail is joined to (TAIL_ENDS); left out, the tail is free. */
  function draftFromPoints(project, points, tailEnd) {
    var end = tailEnd === undefined ? 'free' : tailEnd;
    if (!available(project)) throw new Error(unavailableMessage(project));
    if (!points || points.length !== 2) {
      throw new Error('An anchor needs a head and a tail.');
    }
    var ends = points.map(function (p) { return nativePoint(project, p); });
    if (!ends.every(function (p) { return p.every(Number.isFinite); })) {
      throw new Error('Every anchor coordinate must be a number.');
    }
    var head = snapHead(project, ends[0]).map(round);
    var tail = ends[1];
    if (!insideDomain(project, head) || !insideDomain(project, tail)) {
      throw new Error('The anchor must stay inside the model domain.');
    }
    var problem = headProblem(project, head);
    if (problem) throw new Error(problem);
    if (head.every(function (value, axis) { return value === tail[axis]; })) {
      throw new Error('An anchor must have a non-zero length.');
    }
    problem = tailEndProblem(project, end, tail);
    if (problem) throw new Error(problem);
    var id = nextId(project.anchors || [], 'anchor_');
    var existing = (project.anchor_sections || [])[0];
    return {
      id: id,
      name: 'Anchor ' + id.slice('anchor_'.length),
      kind: spatial(project) ? 'anchor3d' : 'anchor',
      section: existing ? existing.id : 'tendon_1',
      head: head, tail: tail.map(round),
      // TRUSS_PRESTRESS_PK2, a stress in the project's units: none until it is typed.
      prestress: 0,
      // A free tail is a node of the soil mesh; a fixed one is held in place.
      tail_end: end,
      active: true
    };
  }

  /* Millimetre precision: a snapped head that reads 11.999999999 in the property
     grid looks like a bug, and the server matches the pile to 1e-6 m. */
  function round(value) { return Math.round(value * 1e6) / 1e6; }

  /* The coordinate-first path: raking back and down from the pile at 35 degrees,
     the usual ground anchor, which the user then edits. With no structure the head
     is 2 m below the top of the soil in the middle of the domain. */
  function draft(project) {
    if (!available(project)) throw new Error(unavailableMessage(project));
    var d = project.domain;
    var length = 10, radians = 35 * Math.PI / 180;
    var pile = livePiles(project)[0];
    if (!pile) {
      var middle = [(d.x0 + d.x1) / 2, Math.max(d.y_bottom, d.y_top - 2)];
      if (spatial(project)) middle.push((d.z0 + d.z1) / 2);
      var toward = (d.x1 - middle[0]) >= (middle[0] - d.x0) ? 1 : -1;
      var far = middle.slice();
      far[0] = Math.max(d.x0, Math.min(d.x1, middle[0] + toward * length * Math.cos(radians)));
      far[1] = Math.max(d.y_bottom, Math.min(d.y_top, middle[1] - length * Math.sin(radians)));
      return draftFromPoints(project, [middle, far]);
    }
    if (!spatial(project)) {
      var top = pile.points[0], toe = pile.points[pile.points.length - 1];
      var head = [top[0], top[1] + (toe[1] - top[1]) * 0.25];
      // Rake into the retained side: away from the pit, which is the shorter side of
      // the domain about the wall.
      var into = (d.x1 - head[0]) >= (head[0] - d.x0) ? 1 : -1;
      var tail = [head[0] + into * length * Math.cos(radians),
                  head[1] - length * Math.sin(radians)];
      tail[0] = Math.max(d.x0, Math.min(d.x1, tail[0]));
      tail[1] = Math.max(d.y_bottom, Math.min(d.y_top, tail[1]));
      return draftFromPoints(project, [[head[0], head[1]], [tail[0], tail[1]]]);
    }

    // In space the head sits a quarter of the way down the structure, at the middle
    // of a wall's run or of a member's length, and the tie rakes back and down from
    // there -- the same ground anchor, one dimension up.
    var spot = pile.kind === 'panel'
      ? midOfPanel(pile)
      : midOfMember(pile);
    var away = (d.x1 - spot[0]) >= (spot[0] - d.x0) ? 1 : -1;
    var end = [spot[0] + away * length * Math.cos(radians),
               spot[1] - length * Math.sin(radians), spot[2]];
    end[0] = Math.max(d.x0, Math.min(d.x1, end[0]));
    end[1] = Math.max(d.y_bottom, Math.min(d.y_top, end[1]));
    return draftFromPoints(project, [spot, end]);
  }

  /* A quarter of the way down the wall, halfway along its footprint. */
  function midOfPanel(panel) {
    var first = panel.footprint[0];
    var last = panel.footprint[panel.footprint.length - 1];
    return [(first[0] + last[0]) / 2,
            panel.y_top + (panel.y_toe - panel.y_top) * 0.25,
            (first[1] + last[1]) / 2];
  }

  function midOfMember(member) {
    var top = member.points[0];
    var toe = member.points[member.points.length - 1];
    return [top[0], top[1] + (toe[1] - top[1]) * 0.25, top[2]];
  }

  function sectionsFor(project, anchor) {
    var list = copy((project && project.anchor_sections) || []);
    if (!list.some(function (s) { return s.id === anchor.section; })) {
      list.push(Object.assign({ id: anchor.section }, defaultSection()));
    }
    return list;
  }

  function validate(anchor, project) {
    if (!anchor.name || !anchor.name.trim()) return 'Name cannot be empty.';
    if (!anchor.section) return 'An anchor needs a tendon.';
    var width = anchor.kind === 'anchor3d' ? 3 : 2;
    var ends = [anchor.head, anchor.tail];
    if (!ends.every(function (p) {
      return p && p.length === width && p.every(Number.isFinite);
    })) {
      return 'Every anchor coordinate must be a number.';
    }
    if (anchor.head.every(function (v, axis) { return v === anchor.tail[axis]; })) {
      return 'An anchor must have a non-zero length.';
    }
    if (!Number.isFinite(anchor.prestress)) return 'Prestress must be a number.';
    var target = project || App.PROJECT;
    if (!target) return null;
    if (!insideDomain(target, anchor.head) || !insideDomain(target, anchor.tail)) {
      return 'The anchor must stay inside the model domain.';
    }
    // A head on no structure is a node of the soil mesh (headProblem).
    if (!onStructure(target, anchor) && anchor.head[1] > extent(target).y_top) {
      return 'An anchor head on no structure must be in the soil. Move the head '
        + 'down, or onto a structure.';
    }
    return tailEndProblem(target, anchor.tail_end, anchor.tail);
  }

  /* Why an anchor cannot start at `head`, or null (core/model/drafts.py
     `head_problem`). A head on no structure is a node of the soil mesh, so it has to
     be where soil can be, as a free tail does. */
  function headProblem(project, head) {
    if (!project) return null;
    var on = nearestOnPile(project, head);
    if (on && on.distance <= 1e-6) return null;
    if (head[1] > extent(project).y_top) {
      return 'An anchor head on no structure must be in the soil. Move the head '
        + 'down, or onto a structure.';
    }
    return null;
  }

  /* What an anchor's tail is joined to (core/model/schemas.py `TailEnd`). A new anchor
     is free; a record that does not say is fixed, as every anchor was before. */
  var TAIL_ENDS = ['free', 'fixed'];
  var TAIL_END_LABELS = { free: 'Free (joined to the soil)', fixed: 'Fixed (held in place)' };

  /* Why `tailEnd` cannot be used with this tail, or null (core/model/drafts.py
     `tail_end_problem`). A free tail is a node of the soil mesh, so it has to be where
     soil can be; in a section the top is otherwise open, for a fixed strut end in the
     air. Whether there really is soil there is only known once the model is built, and
     the export says so if there is not. */
  function tailEndProblem(project, tailEnd, tail) {
    if (tailEnd === undefined) return null;
    if (TAIL_ENDS.indexOf(tailEnd) < 0) return 'The tail end is free or fixed.';
    if (tailEnd === 'free' && project && tail[1] > extent(project).y_top) {
      return 'A free anchor tail must be in the soil. Move the tail down, '
        + 'or make the tail end fixed.';
    }
    return null;
  }

  function validateSection(section) {
    if (!section.name || !section.name.trim()) return 'Tendon name cannot be empty.';
    if (!(section.spacing > 0)) return 'Tendon spacing must be greater than zero.';
    // DENSITY may be zero, as on the server: a tendon is often modelled massless.
    var problem = App.PropertySets.validate('anchor', section);
    if (problem) return problem;
    // Null is the honest value for a tendon, which takes no compression at all.
    var limits = ['tension_limit', 'compression_limit'];
    for (var j = 0; j < limits.length; j += 1) {
      var limit = section[limits[j]];
      if (limit !== null && limit !== undefined && !(limit > 0)) {
        return 'A ' + limits[j].replace('_', ' ') + ' must be greater than zero.';
      }
    }
    return null;
  }

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
        return rollback
          .then(function () {
            return App.Viewport && App.Viewport.refresh ? App.Viewport.refresh() : null;
          })
          .then(function () {
            if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
            if (App.Command && App.Command.err) {
              App.Command.err('Could not save anchor: ' + error.message);
            }
            throw error;
          }, function () {
            if (App.Command && App.Command.err) {
              App.Command.err('Could not save anchor: ' + error.message);
            }
            throw error;
          });
      });
  }

  /* The piles are deliberately not resent: an omitted collection means "unchanged"
     to the structures endpoint, so an anchor edit cannot disturb the wall. */
  function save(anchor, tendons) {
    var problem = validate(anchor, App.PROJECT);
    if (problem) return Promise.reject(new Error(problem));
    var library = tendons || sectionsFor(App.PROJECT, anchor);
    for (var i = 0; i < library.length; i += 1) {
      var bad = validateSection(library[i]);
      if (bad) return Promise.reject(new Error(bad));
    }
    var anchors = copy(storedAnchors());
    var at = anchors.findIndex(function (item) { return item.id === anchor.id; });
    if (at < 0) anchors.push(copy(anchor)); else anchors[at] = copy(anchor);

    return patch({ loads: copy(storedLoads()), anchors: anchors,
                   anchor_sections: library },
                 'Saved anchor ' + anchor.name + '.')
      .then(function () {
        if (App.selectObject) App.selectObject(anchor.id, 'tree');
        return anchor;
      });
  }

  function remove(id) {
    var anchor = collection().filter(function (item) { return item.id === id; })[0];
    if (!anchor) return Promise.resolve(false);
    var anchors = copy(storedAnchors()).filter(function (item) { return item.id !== id; });
    if (App.state && App.state.selection === id && App.selectObject) App.selectObject(null);
    return patch({ loads: copy(storedLoads()), anchors: anchors,
                   anchor_sections: copy(sections()) },
                 'Deleted anchor ' + anchor.name + '.');
  }

  function sectionOf(anchor) {
    return sections().filter(function (s) { return s.id === anchor.section; })[0]
      || Object.assign({ id: anchor.section }, defaultSection());
  }

  function isAnchorKey(key) {
    return collection().some(function (anchor) { return anchor.id === key; });
  }

  /* Both work off the last coordinate being the level, which is true of a 2D
     `(x, z)` and of a 3D `(x, y, z)` alike: the rake of a tie is measured from the
     horizontal in either. */
  function length(anchor) {
    return Math.sqrt(anchor.head.reduce(function (sum, value, axis) {
      var d = anchor.tail[axis] - value;
      return sum + d * d;
    }, 0));
  }

  function inclination(anchor) {
    var last = anchor.head.length - 1;
    var drop = anchor.head[last] - anchor.tail[last];
    var run = Math.sqrt(anchor.head.slice(0, last).reduce(function (sum, value, axis) {
      var d = anchor.tail[axis] - value;
      return sum + d * d;
    }, 0));
    return Math.atan2(drop, run) * 180 / Math.PI;
  }

  function input(value) {
    return App.UI.el('input.mesh-setting-control', {
      type: 'number', step: '0.1', value: String(value)
    });
  }

  /* A text box for a Kratos variable, as in beams.js: it may be a flag, a list or a
     name as well as a number (App.PropertySets.parse). */
  function variableInput(value) {
    return App.UI.el('input.mesh-setting-control', {
      type: 'text', value: App.PropertySets.format(value)
    });
  }

  /* A typed head a little off the structure is moved onto it, as a picked one is
     (draftFromPoints); further away it is left where it is, for validate to refuse. */
  function snapHead(project, head) {
    var snapped = nearestOnPile(project, head);
    if (!snapped || snapped.distance > SNAP_DISTANCE) return head;
    return snapped.point.map(round);
  }

  /* The window the Create anchor tool and the Edit anchor… button open, as the sheet
     pile's does (beams.js `open`): a name, both ends, what the tail is joined to, the
     prestress, whether it is active, and the numbers of its tendon. Editing the tendon
     here edits the shared tendon, as the Selection explorer's own fields do. */
  function open(source) {
    if (!App.Dialogs || !App.Dialogs.open) return;
    var anchor = copy(source);
    if (TAIL_ENDS.indexOf(anchor.tail_end) < 0) anchor.tail_end = 'fixed';
    var editing = collection().some(function (item) { return item.id === anchor.id; });
    var library = sectionsFor(App.PROJECT, anchor);
    var section = copy(library.filter(function (s) { return s.id === anchor.section; })[0]
                       || library[0]);
    var axes = anchor.kind === 'anchor3d' ? ['x', 'y', 'z'] : ['x', 'y'];
    var el = App.UI.el, controls = {}, ends = { head: [], tail: [] }, sectionControls = {};
    var shell, message;

    function submit() {
      anchor.name = controls.name.value.trim();
      ['head', 'tail'].forEach(function (end) {
        anchor[end] = ends[end].map(function (control) { return Number(control.value); });
      });
      anchor.head = snapHead(App.PROJECT, anchor.head);
      anchor.tail_end = controls.tail_end.value;
      anchor.prestress = Number(controls.prestress.value);
      anchor.active = controls.active.checked;
      section.variables = section.variables || {};
      Object.keys(sectionControls).forEach(function (key) {
        if (key === 'spacing') { section.spacing = Number(sectionControls[key].value); return; }
        var value = App.PropertySets.parse(sectionControls[key].value);
        if (value === undefined) delete section.variables[key];
        else section.variables[key] = value;
      });
      var problem = validate(anchor, App.PROJECT) || validateSection(section);
      if (problem) { message.textContent = problem; return; }
      var tendons = library.map(function (s) { return s.id === section.id ? section : s; });
      save(anchor, tendons).then(function () { shell.close(); }, function (error) {
        message.textContent = error.message;
      });
    }

    shell = App.Dialogs.open({
      title: (editing ? 'Edit ' : 'Create ') + 'anchor',
      width: 520, height: anchor.kind === 'anchor3d' ? 620 : 580,
      buttons: [
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

        controls.name = el('input.mesh-setting-control', { type: 'text', value: anchor.name });
        row('Name', controls.name, 'Shown in the Model explorer and Kratos submodel part.');

        // The head is moved onto the nearest structure on Save (snapHead).
        [['head', 'Head'], ['tail', 'Tail']].forEach(function (end) {
          anchor[end[0]].forEach(function (value, axis) {
            var control = input(value);
            ends[end[0]].push(control);
            row(end[1] + ' ' + axes[axis], control, 'World ' + axes[axis] + ' [m].');
          });
        });

        controls.tail_end = el('select.mesh-setting-control');
        TAIL_ENDS.forEach(function (value) {
          controls.tail_end.appendChild(el('option', { value: value,
                                                       text: TAIL_END_LABELS[value] }));
        });
        controls.tail_end.value = anchor.tail_end;
        row('Tail end', controls.tail_end,
            'Free: joined to the soil mesh. Fixed: held in place.');

        controls.prestress = input(anchor.prestress);
        row('TRUSS_PRESTRESS_PK2', controls.prestress,
            '[' + App.Units.label('stress') + '] Positive in tension.');

        controls.active = el('input.mesh-setting-control', { type: 'checkbox' });
        controls.active.checked = anchor.active !== false;
        row('Active', controls.active,
            'Inactive anchors remain in the project but are not exported.');

        // The tendon's Kratos variables, by Kratos' names and in the project's units.
        App.PropertySets.names('anchor', section,
                               App.PROJECT && App.PROJECT.dimension).forEach(function (key) {
          var control = variableInput((section.variables || {})[key]);
          sectionControls[key] = control;
          var unit = App.Units.variableLabel(key);
          row(key, control, unit ? '[' + unit + ']' : '');
        });
        if (anchor.kind !== 'anchor3d') {
          var spacing = input(section.spacing);
          sectionControls.spacing = spacing;
          row('Spacing', spacing,
              'Out-of-plane centres [m]; a 2D section smears the anchor over them.');
        }

        message = el('div.mesh-settings-message');
        row('', message, '');
      }
    });
    return shell;
  }

  function start() {
    if (!App.PROJECT) return;
    if (!available(App.PROJECT)) {
      if (App.Command) App.Command.note(unavailableMessage(App.PROJECT));
      return;
    }
    return open(draft(App.PROJECT));
  }

  function edit(id) {
    var anchor = collection().filter(function (item) { return item.id === id; })[0];
    if (!anchor) return;
    return open(anchor);
  }

  return {
    available: available, draft: draft, draftFromPoints: draftFromPoints,
    nearestOnPile: nearestOnPile, nearestOnPanel: nearestOnPanel,
    nearestOnPolyline: nearestOnPolyline, spatial: spatial, livePiles: livePiles,
    unavailableMessage: unavailableMessage,
    sectionsFor: sectionsFor, sectionOf: sectionOf,
    validate: validate, validateSection: validateSection,
    save: save, remove: remove, start: start, edit: edit, open: open,
    isAnchorKey: isAnchorKey, length: length, inclination: inclination,
    defaultSection: defaultSection, TAIL_ENDS: TAIL_ENDS, TAIL_END_LABELS: TAIL_END_LABELS
  };
})();
