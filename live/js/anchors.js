/* ══════════════════════════════════════════════════════════════════
   anchors.js — Structure-mode anchors.

   An anchor is a two-node tie: a head on a sheet pile and a tail at a point
   the analysis holds still. That is the formulation the reference deck uses
   (examples/crow_case.mdpa) -- the head node is shared with the beam, and the
   tail belongs to no element at all, restrained by its own node group. The
   grouted body is idealised as a fixed point rather than bonded to the soil.

   So the head is snapped onto a pile here rather than left where it was
   clicked: an anchor floating beside its wall would export a truss attached to
   nothing, and the server refuses it anyway.

   In the solid model the same tie hangs from a wall panel or a member instead, in
   three dimensions: `kind: "anchor3d"`, head snapped onto the swept surface of a
   wall or the polyline of a member, tail free. The formulation is identical --
   only the dimension of the points, and what the head may sit on, differ.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Anchors = (function () {

  /* How far the model reaches, which is not the same as the borehole domain: a drawn
     or imported part may stand above `z_top`, and a structure placed on one is on
     model geometry. `App.Model.extentOf` mirrors the server's `Project.extent`; the
     fallback keeps this module usable in a page that has no App.Model. */
  function extent(project) {
    return (App.Model && App.Model.extentOf)
      ? App.Model.extentOf(project)
      : (project && project.domain);
  }


  /* A four-strand tendon at 2.5 m centres. A starting point the user edits. */
  var DEFAULT_SECTION = {
    name: 'Anchor tendon', E: 1.95e8, area: 0.0006, density: 7850,
    spacing: 2.5, tension_limit: 900, compression_limit: null
  };

  var SNAP_DISTANCE = 1.0;   // metres a picked head may be off the pile

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

  /* An anchor needs something to hang from, in the dimension it is drawn in. */
  function available(project) {
    if (!project || livePiles(project).length === 0) return false;
    return spatial(project) || (project.section_plane || 'xz') === 'xz';
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
    var plan = nearestOnPolyline(panel.footprint, [point[0], point[1]]);
    if (!plan) return null;
    var z = Math.max(panel.z_toe, Math.min(panel.z_top, point[2]));
    var on = [plan.point[0], plan.point[1], z];
    return { point: on, distance: Math.hypot(plan.distance, point[2] - z) };
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

  function unavailableMessage(project) {
    if (livePiles(project).length) {
      return spatial(project)
        ? 'Anchors are created in the 3D model.'
        : 'Anchors are created in the 2D x-z section.';
    }
    return spatial(project)
      ? 'An anchor hangs from a wall or a member; create one first.'
      : 'An anchor hangs from a sheet pile; create one first.';
  }

  /* A picked point in the dimension this project's anchors live in: `(x, z)` in a
     section, `(x, y, z)` in space. The drawing tools always hand over three
     numbers, so the section drops the one it has no room for. */
  function nativePoint(project, point) {
    return spatial(project)
      ? [point[0], point[1] === undefined ? 0 : point[1],
         point[2] === undefined ? point[1] : point[2]]
      : [point[0], point[2] === undefined ? point[1] : point[2]];
  }

  function insideDomain(project, point) {
    // The extent, not the domain: an anchor may be tied into a drawn embankment that
    // stands above `z_top`. Mirrors the server's `Project.extent`.
    var d = extent(project);
    if (!spatial(project)) {
      return point[0] >= d.x0 && point[0] <= d.x1
        && point[1] >= d.z_bottom && point[1] <= d.z_top;
    }
    return point[0] >= d.x0 && point[0] <= d.x1
      && point[1] >= d.y0 && point[1] <= d.y1
      && point[2] >= d.z_bottom && point[2] <= d.z_top;
  }

  function draftFromPoints(project, points) {
    if (!available(project)) throw new Error(unavailableMessage(project));
    if (!points || points.length !== 2) {
      throw new Error('An anchor needs a head and a tail.');
    }
    var ends = points.map(function (p) { return nativePoint(project, p); });
    if (!ends.every(function (p) { return p.every(Number.isFinite); })) {
      throw new Error('Every anchor coordinate must be a number.');
    }
    var snapped = nearestOnPile(project, ends[0]);
    if (!snapped || snapped.distance > SNAP_DISTANCE) {
      throw new Error(spatial(project)
        ? 'The anchor head must be placed on a wall or a member.'
        : 'The anchor head must be placed on a sheet pile.');
    }
    var tail = ends[1];
    if (!insideDomain(project, tail)) {
      throw new Error('The anchor must stay inside the model domain.');
    }
    var head = snapped.point.map(round);
    if (head.every(function (value, axis) { return value === tail[axis]; })) {
      throw new Error('An anchor must have a non-zero length.');
    }
    var id = nextId(project.anchors || [], 'anchor_');
    var existing = (project.anchor_sections || [])[0];
    return {
      id: id,
      name: 'Anchor ' + id.slice('anchor_'.length),
      kind: spatial(project) ? 'anchor3d' : 'anchor',
      section: existing ? existing.id : 'tendon_1',
      head: head, tail: tail.map(round),
      prestress: 250,
      active: true
    };
  }

  /* Millimetre precision: a snapped head that reads 11.999999999 in the property
     grid looks like a bug, and the server matches the pile to 1e-6 m. */
  function round(value) { return Math.round(value * 1e6) / 1e6; }

  /* The coordinate-first path: raking back and down from the pile at 35 degrees,
     the usual ground anchor, which the user then edits. */
  function draft(project) {
    if (!available(project)) throw new Error(unavailableMessage(project));
    var d = project.domain;
    var length = 10, radians = 35 * Math.PI / 180;
    var pile = livePiles(project)[0];
    if (!spatial(project)) {
      var top = pile.points[0], toe = pile.points[pile.points.length - 1];
      var head = [top[0], top[1] + (toe[1] - top[1]) * 0.25];
      // Rake into the retained side: away from the pit, which is the shorter side of
      // the domain about the wall.
      var into = (d.x1 - head[0]) >= (head[0] - d.x0) ? 1 : -1;
      var tail = [head[0] + into * length * Math.cos(radians),
                  head[1] - length * Math.sin(radians)];
      tail[0] = Math.max(d.x0, Math.min(d.x1, tail[0]));
      tail[1] = Math.max(d.z_bottom, Math.min(d.z_top, tail[1]));
      return draftFromPoints(project, [[head[0], 0, head[1]], [tail[0], 0, tail[1]]]);
    }

    // In space the head sits a quarter of the way down the structure, at the middle
    // of a wall's run or of a member's length, and the tie rakes back and down from
    // there -- the same ground anchor, one dimension up.
    var spot = pile.kind === 'panel'
      ? midOfPanel(pile)
      : midOfMember(pile);
    var away = (d.x1 - spot[0]) >= (spot[0] - d.x0) ? 1 : -1;
    var end = [spot[0] + away * length * Math.cos(radians), spot[1],
               spot[2] - length * Math.sin(radians)];
    end[0] = Math.max(d.x0, Math.min(d.x1, end[0]));
    end[2] = Math.max(d.z_bottom, Math.min(d.z_top, end[2]));
    return draftFromPoints(project, [spot, end]);
  }

  /* A quarter of the way down the wall, halfway along its footprint. */
  function midOfPanel(panel) {
    var first = panel.footprint[0];
    var last = panel.footprint[panel.footprint.length - 1];
    return [(first[0] + last[0]) / 2, (first[1] + last[1]) / 2,
            panel.z_top + (panel.z_toe - panel.z_top) * 0.25];
  }

  function midOfMember(member) {
    var top = member.points[0];
    var toe = member.points[member.points.length - 1];
    return [top[0], top[1], top[2] + (toe[2] - top[2]) * 0.25];
  }

  function sectionsFor(project, anchor) {
    var list = copy((project && project.anchor_sections) || []);
    if (!list.some(function (s) { return s.id === anchor.section; })) {
      list.push(Object.assign({ id: anchor.section }, DEFAULT_SECTION));
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
    var snapped = target ? nearestOnPile(target, anchor.head) : null;
    if (!snapped || snapped.distance > 1e-6) {
      return width === 3
        ? 'The anchor head must sit on a wall or a member.'
        : 'The anchor head must sit on a sheet pile.';
    }
    return null;
  }

  function validateSection(section) {
    if (!section.name || !section.name.trim()) return 'Tendon name cannot be empty.';
    var positive = ['E', 'area', 'density', 'spacing'];
    for (var i = 0; i < positive.length; i += 1) {
      if (!(section[positive[i]] > 0)) {
        return 'Tendon ' + positive[i] + ' must be greater than zero.';
      }
    }
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
      || Object.assign({ id: anchor.section }, DEFAULT_SECTION);
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

  function start() {
    if (!App.PROJECT) return;
    if (!available(App.PROJECT)) {
      if (App.Command) App.Command.note(unavailableMessage(App.PROJECT));
      return;
    }
    var anchor = draft(App.PROJECT);
    var tendons = sectionsFor(App.PROJECT, anchor);
    if (App.Dialogs && App.Dialogs.anchor) return App.Dialogs.anchor(anchor, tendons);
    return save(anchor, tendons);
  }

  function edit(id) {
    var anchor = collection().filter(function (item) { return item.id === id; })[0];
    if (!anchor) return;
    return save(copy(anchor), copy(sections()));
  }

  return {
    available: available, draft: draft, draftFromPoints: draftFromPoints,
    nearestOnPile: nearestOnPile, nearestOnPanel: nearestOnPanel,
    nearestOnPolyline: nearestOnPolyline, spatial: spatial, livePiles: livePiles,
    unavailableMessage: unavailableMessage,
    sectionsFor: sectionsFor, sectionOf: sectionOf,
    validate: validate, validateSection: validateSection,
    save: save, remove: remove, start: start, edit: edit,
    isAnchorKey: isAnchorKey, length: length, inclination: inclination,
    DEFAULT_SECTION: DEFAULT_SECTION
  };
})();
