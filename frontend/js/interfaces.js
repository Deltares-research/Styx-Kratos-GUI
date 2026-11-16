/* ══════════════════════════════════════════════════════════════════
   interfaces.js — Structure-mode interfaces.

   An interface is the contact between a structure and the ground around it: the
   thin band where the two slide past one another and can pull apart, instead of
   being welded together the way a bare sheet pile is. Kratos writes it as a
   zero-thickness element -- two coincident faces with separate nodes -- and the
   server does the node splitting after meshing (core/kratos/interfaces.py).

   Two ways to place one, and a record carries exactly one of them:

     • along a sheet pile, which is the usual case and the one
       Kratos' reference decks contain. `side` says which of the two soils is
       unglued from the wall; "both" is the normal answer for a retaining wall.
     • along its own polyline through the soil -- an excavation face, a lining,
       a slip surface. There is no structure between the two soils then, so one
       of them has to keep the original nodes and `side` says which is detached.

   On a pile the interface runs the whole pile, or the part of it between From
   and To (`stretch`). A typed From or To is moved onto the pile (`snap`), and
   one more than STRETCH_SNAP away is refused.

   `side` names a face as the screen shows it, whichever way the line was drawn:
   on a line steeper than 45 degrees "left" is the face toward -x and "right" the
   face toward +x; on a flatter line the faces are "below" and "above"
   (core/model/polylines.py, which this mirrors).

   Plane strain only. Every reference deck is a section, and a 3D
   interface is a different element with a different node layout and no fixture
   to pin it -- see the INTERFACES table in core/kratos/writer.py.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Interfaces = (function () {

  /* Steel against a medium sand: the reduction factor an engineer starts from,
     and a virtual thickness the stiffness is derived over. The factor reduces the
     strength of the soil each stretch runs against (`sectionsFor`). */
  function defaultSection() {
    return Object.assign({ name: 'Interface', r_inter: 0.7, virtual_thickness: 0.01,
                           permeability: 'Neutral' }, App.PropertySets.defaults('interface'));
  }

  /* The laws a contact is offered (core/kratos/materials.py): the elastic one reads the
     two stiffnesses alone, a Coulomb one a strength too -- the soil's reduced by
     R_inter, or the contact's own. A linear elastic soil has no strength to give, so a
     Coulomb contact against one has to have its own; the export refuses it otherwise.
     The second Coulomb name is the one Kratos builds before 2026-10 register. */
  var ELASTIC_LAW = 'GeoIncrementalLinearElasticInterfaceLaw';
  var COULOMB_LAW = 'GeoInterfaceCoulombLawPlaneStrain';
  var COULOMB_LAWS = [COULOMB_LAW, 'GeoInterfaceCoulombWithTensionCutOff'];
  var LAWS = [{ value: ELASTIC_LAW, text: 'Elastic' }, { value: COULOMB_LAW, text: 'Coulomb' }];
  var STRENGTH = ['GEO_COHESION', 'GEO_FRICTION_ANGLE'];

  function coulomb(section) { return COULOMB_LAWS.indexOf(section.constitutive_law) >= 0; }

  function holds(section, name) {
    return Object.prototype.hasOwnProperty.call(section.variables || {}, name);
  }

  /* Whether the contact carries a strength of its own, rather than its soil's. */
  function ownStrength(section) {
    return STRENGTH.some(function (name) { return holds(section, name); });
  }

  function soilOf(section) {
    return (App.MATERIALS || []).filter(function (m) { return m.id === section.material; })[0]
      || null;
  }

  function elastic(soil) {
    return !!soil && App.SoilModels.modelOf(soil.constitutive_law) === 'linear_elastic';
  }

  /* Why a Coulomb contact cannot take its strength from the soil it names, in a few
     words, or null: the first part of `strengthProblem` and of the note that it has a
     strength of its own (core/kratos/materials.py `no_strength`). One that names none
     takes each adjacent soil's, which only the export knows. */
  function noStrength(section) {
    if (!coulomb(section)) return null;
    if (STRENGTH.every(function (name) { return holds(section, name); })) return null;
    var soil = soilOf(section);
    return elastic(soil) ? soil.name + ' is linear elastic and has no strength to give' : null;
  }

  /* `noStrength`, and what to do about it. */
  function strengthProblem(section) {
    var why = noStrength(section);
    return why === null ? null
      : why + ': set the contact\'s own GEO_COHESION and GEO_FRICTION_ANGLE.';
  }

  /* Give the contact a strength of its own, starting from what it took from its soil
     -- c R and atan(R tan phi) -- or, from a soil with none, the Mohr-Coulomb
     defaults. What it already holds is kept. */
  function setOwnStrength(section) {
    section.variables = section.variables || {};
    var soil = soilOf(section);
    var given = soil && !elastic(soil) ? soil.variables || {} : {};
    var r = section.r_inter !== null && section.r_inter !== undefined ? section.r_inter
      : (soil && soil.rInter) || 0.7;
    var from = {
      GEO_COHESION: typeof given.GEO_COHESION === 'number' ? given.GEO_COHESION * r : null,
      GEO_FRICTION_ANGLE: typeof given.GEO_FRICTION_ANGLE === 'number'
        ? Math.atan(Math.tan(given.GEO_FRICTION_ANGLE * Math.PI / 180) * r) * 180 / Math.PI
        : null
    };
    STRENGTH.forEach(function (name) {
      if (holds(section, name)) return;
      section.variables[name] = from[name] !== null ? Number(from[name].toPrecision(6))
        : App.SoilModels.defaultIn(App.SoilModels.find('mohr_coulomb', name),
                                   App.Units.current());
    });
  }

  /* Leave the strength out, for the export to take from the soil. */
  function soilStrength(section) {
    STRENGTH.forEach(function (name) { delete (section.variables || {})[name]; });
  }

  var SIDES = ['both', 'left', 'right', 'below', 'above'];

  var STRETCH_SNAP = 0.5;   // metres a typed From or To may be off the pile

  function copy(value) { return JSON.parse(JSON.stringify(value)); }

  function collection() { return App.INTERFACES || []; }

  function storedInterfaces() {
    return (App.PROJECT && App.PROJECT.interfaces) || collection();
  }

  function storedSections() {
    return App.INTERFACE_SECTIONS
      || (App.PROJECT && App.PROJECT.interface_sections) || [];
  }

  function storedLoads() {
    return (App.PROJECT && App.PROJECT.loads) || [];
  }

  /* Authored in the 2D x-y section and nowhere else, for the same reason a sheet
     pile is: that is the plane the confirmed interface element describes. */
  function available(project) {
    return !!project && project.dimension === 2;
  }

  function unavailableMessage(project) {
    return project && project.dimension === 2
      ? 'Interfaces are created in the 2D x-y section.'
      : 'An interface is a plane-strain object; switch to 2D to create one.';
  }

  /* The sheet piles an interface may be hung on. An interface against a switched
     off pile is a contact with nothing, so those are not offered. */
  function livePiles(project) {
    return ((project && project.beams) || []).filter(function (beam) {
      return beam.active !== false && (beam.kind || 'beam') === 'beam';
    });
  }

  function nextId(list, prefix) {
    var used = {};
    (list || []).forEach(function (item) { used[item.id] = true; });
    var number = 1;
    while (used[prefix + number]) number += 1;
    return prefix + number;
  }

  function nextSectionId(project) {
    return nextId(((project && project.interface_sections) || []), 'interfacesection_');
  }

  /* ── Points along a polyline (core/model/polylines.py) ── */

  /* The point on the polyline nearest `point`, its distance, and how far along the
     polyline it is. */
  function nearest(points, point) {
    var best = null;
    var walked = 0;
    for (var i = 1; i < points.length; i += 1) {
      var a = points[i - 1], b = points[i];
      var dx = b[0] - a[0], dy = b[1] - a[1];
      var size = Math.sqrt(dx * dx + dy * dy);
      if (!size) continue;
      var t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (size * size);
      t = Math.max(0, Math.min(1, t));
      var on = [a[0] + t * dx, a[1] + t * dy];
      var away = Math.sqrt((point[0] - on[0]) * (point[0] - on[0])
                           + (point[1] - on[1]) * (point[1] - on[1]));
      if (!best || away < best.distance) {
        best = { point: on, distance: away, along: walked + t * size };
      }
      walked += size;
    }
    return best;
  }

  /* The part of the polyline from `start` to `end` metres along it, in the
     polyline's own order, following every bend. */
  function between(points, start, end) {
    var low0 = Math.min(start, end), high0 = Math.max(start, end);
    var out = [];
    var walked = 0;
    for (var i = 1; i < points.length; i += 1) {
      var a = points[i - 1], b = points[i];
      var size = Math.sqrt((b[0] - a[0]) * (b[0] - a[0]) + (b[1] - a[1]) * (b[1] - a[1]));
      if (!size) continue;
      var low = Math.max(low0, walked), high = Math.min(high0, walked + size);
      if (low <= high) {
        [low, high].forEach(function (at) {
          var t = (at - walked) / size;
          var point = [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])];
          var last = out[out.length - 1];
          if (!last || last[0] !== point[0] || last[1] !== point[1]) out.push(point);
        });
      }
      walked += size;
    }
    return out;
  }

  /* The two faces of a line as the screen shows them: left and right for a line
     steeper than 45 degrees, below and above for a flatter one. */
  function faces(points) {
    if (!points || points.length < 2) return ['left', 'right'];
    var first = points[0], last = points[points.length - 1];
    return Math.abs(last[1] - first[1]) >= Math.abs(last[0] - first[0])
      ? ['left', 'right'] : ['below', 'above'];
  }

  /* Micrometre precision, as the anchors' snapped head: the server matches the pile
     to 1e-6 m. */
  function round(value) { return Math.round(value * 1e6) / 1e6; }

  /* `point` moved onto `pile`, or a refusal when it is more than STRETCH_SNAP away
     (core/model/drafts.py `stretch_point`, word for word). */
  function snap(pile, point, label) {
    if (!point || point.length !== 2 || !point.every(Number.isFinite)) {
      throw new Error(label + ' must be two numbers.');
    }
    var found = nearest(pile.points, point);
    if (!found || found.distance > STRETCH_SNAP) {
      throw new Error(label + ' is ' + (found ? found.distance.toFixed(1) : '?') + ' m from '
                      + pile.name + '; From and To are points on the pile.');
    }
    return found.point.map(round);
  }

  /* From and To on `pile`, snapped; null when they are the pile's two ends, which
     is the whole pile (drafts.py `stretch`). */
  function stretchOn(pile, start, end) {
    var points = [snap(pile, start, 'From'), snap(pile, end, 'To')];
    function same(a, b) { return a[0] === b[0] && a[1] === b[1]; }
    if (same(points[0], points[1])) {
      throw new Error('From and To are the same point on ' + pile.name
                      + '; the part of the pile needs length.');
    }
    var ends = [pile.points[0], pile.points[pile.points.length - 1]];
    var whole = (same(points[0], ends[0]) && same(points[1], ends[1]))
      || (same(points[0], ends[1]) && same(points[1], ends[0]));
    return whole ? null : points;
  }

  /* The coordinate-first path, like every other structure here: an interface on
     the first live sheet pile if there is one -- the whole pile, or the part
     between the two points of `stretch` -- and a free line down the middle of the
     section if there is not. The window opens on it. */
  function draft(project, structure, stretch) {
    if (!available(project)) throw new Error(unavailableMessage(project));
    var piles = livePiles(project);
    var pile = structure
      ? piles.filter(function (b) { return b.id === structure; })[0]
      : piles[0];
    if (structure && !pile) {
      throw new Error('An interface can only follow a live sheet pile.');
    }
    var id = nextId(project.interfaces || [], 'interface_');
    var existing = (project.interface_sections || [])[0];
    var record = {
      id: id,
      name: 'Interface ' + id.slice('interface_'.length),
      kind: 'interface',
      section: existing ? existing.id : nextSectionId(project),
      structure: null,
      points: null,
      side: 'both',
      stretch: null,
      active: true
    };
    if (stretch && !pile) {
      throw new Error('From and To are points on a sheet pile; an interface on its '
                      + 'own points runs its whole line.');
    }
    if (pile) {
      record.structure = pile.id;
      if (stretch) record.stretch = stretchOn(pile, stretch[0], stretch[1]);
      return record;
    }
    // No wall to wrap: a free line splits soil from soil, so one side has to keep
    // the original nodes and "both" would leave nothing holding them.
    var d = project.domain;
    var x = d.x0 + (d.x1 - d.x0) * 0.5;
    record.points = [[x, d.y_top], [x, d.y_top - (d.y_top - d.y_bottom) * 0.5]];
    record.side = 'left';
    return record;
  }

  /* The section list this interface needs saved alongside it: the project's own,
     plus a default the first time anyone draws one. The default has no material: each
     stretch takes the soil it runs against, reduced by r_inter (`drafts.section`). */
  function sectionsFor(project, record) {
    var library = copy((project && project.interface_sections) || []);
    var known = library.some(function (s) { return s.id === record.section; });
    if (!known) {
      library.push(Object.assign({ id: record.section }, defaultSection(),
                                 { material: null }));
    }
    return library;
  }

  function validate(record, project) {
    project = project || App.PROJECT;
    if (!record.name || !record.name.trim()) return 'Name cannot be empty.';
    if (!record.section) return 'An interface needs a section.';
    if (SIDES.indexOf(record.side) < 0) {
      return 'An interface side must be both, left, right, below or above.';
    }
    var free = !record.structure;
    if (free === !record.points) {
      return 'An interface follows either a sheet pile or its own points, not both.';
    }
    if (!free) {
      var piles = livePiles(project);
      if (!piles.some(function (b) { return b.id === record.structure; })) {
        return 'An interface can only follow a live sheet pile.';
      }
      return stretchProblem(record, project) || doubleContact(record, project);
    }
    if (record.side === 'both') {
      return 'A free interface has no structure between its sides; detach the left or the right.';
    }
    if (record.stretch) {
      return 'From and To are points on a sheet pile; an interface on its own points '
        + 'runs its whole line.';
    }
    var points = record.points || [];
    if (points.length < 2) return 'An interface needs at least two points.';
    for (var i = 0; i < points.length; i += 1) {
      if (points[i].length !== 2 || !points[i].every(Number.isFinite)) {
        return 'Every interface coordinate must be a number.';
      }
      if (i && points[i][0] === points[i - 1][0] && points[i][1] === points[i - 1][1]) {
        return 'An interface cannot repeat the same point twice.';
      }
    }
    return alongAPile(record, project);
  }

  /* ── The project's own checks (core/model/schemas.py `_check_interface_lines`),
     word for word, so the window refuses before the server does. ── */

  var STRETCH_TOLERANCE = 1e-6;
  var FACE_ORDER = ['left', 'right', 'below', 'above'];

  /* Python's `:g`, for the numbers a refusal names. */
  function g(value) { return String(Number(value.toPrecision(6))); }

  function xy(point) { return '(' + point.map(g).join(', ') + ')'; }

  function stretchProblem(record, project) {
    if (!record.stretch) return null;
    var pile = pileOf(record, project);
    var labels = ['From', 'To'];
    for (var i = 0; i < 2; i += 1) {
      var point = record.stretch[i];
      if (!point || point.length !== 2 || !point.every(Number.isFinite)) {
        return labels[i] + ' must be two numbers.';
      }
      var away = nearest(pile.points, point).distance;
      if (away > STRETCH_TOLERANCE) {
        return record.name + ': ' + labels[i] + ' ' + xy(point) + ' is '
          + g(Number(away.toPrecision(3))) + ' m from ' + pile.name
          + '; From and To are points on the pile';
      }
    }
    if (record.stretch[0][0] === record.stretch[1][0]
        && record.stretch[0][1] === record.stretch[1][1]) {
      return 'From and To are the same point on ' + pile.name
        + '; the part of the pile needs length.';
    }
    return null;
  }

  /* `side` in the words of the line it runs along, as the project stores it. */
  function sideOn(record, project) {
    if (record.side === 'both') return 'both';
    var words = faces(pathOf(record, project));
    return record.side === 'left' || record.side === 'below' ? words[0] : words[1];
  }

  function doubleContact(record, project) {
    var all = copy((project && project.interfaces) || []);
    var at = all.findIndex(function (item) { return item.id === record.id; });
    if (at < 0) all.push(copy(record)); else all[at] = copy(record);
    var held = [];
    for (var i = 0; i < all.length; i += 1) {
      var item = all[i];
      if (!item.structure || item.active === false) continue;
      var pile = pileOf(item, project);
      if (!pile) continue;
      var path = pathOf(item, project);
      var ends = [nearest(pile.points, path[0]).along,
                  nearest(pile.points, path[path.length - 1]).along].sort(function (a, b) {
        return a - b;
      });
      var mine = item.side === 'both' ? faces(path) : [sideOn(item, project)];
      for (var j = 0; j < held.length; j += 1) {
        var other = held[j];
        if (other.item.structure !== item.structure) continue;
        var common = mine.filter(function (face) { return other.faces.indexOf(face) >= 0; })
          .sort(function (a, b) { return FACE_ORDER.indexOf(a) - FACE_ORDER.indexOf(b); });
        var low = Math.max(ends[0], other.ends[0]), high = Math.min(ends[1], other.ends[1]);
        if (!common.length || high - low <= STRETCH_TOLERANCE) continue;
        var part = between(pile.points, low, high);
        var first = pile.points[0], last = pile.points[pile.points.length - 1];
        var steep = Math.abs(last[1] - first[1]) >= Math.abs(last[0] - first[0]);
        var axis = steep ? 'y' : 'x', index = steep ? 1 : 0;
        return item.name + ' and ' + other.item.name + ' both hold the ' + common[0]
          + ' face of ' + pile.name + ' between ' + axis + ' ' + g(part[0][index])
          + ' and ' + axis + ' ' + g(part[part.length - 1][index]);
      }
      held.push({ item: item, faces: mine, ends: ends });
    }
    return null;
  }

  /* A free line on a live pile (schemas.py `_runs_along`). */
  function runsAlong(line, pile) {
    for (var i = 1; i < line.length; i += 1) {
      for (var j = 1; j < pile.length; j += 1) {
        var c = pile[j - 1], d = pile[j];
        var dx = d[0] - c[0], dy = d[1] - c[1];
        var size = Math.sqrt(dx * dx + dy * dy);
        if (!size) continue;
        var ends = [line[i - 1], line[i]];
        var off = ends.map(function (p) {
          return Math.abs(dx * (p[1] - c[1]) - dy * (p[0] - c[0])) / size;
        });
        if (Math.max(off[0], off[1]) > STRETCH_TOLERANCE) continue;
        var along = ends.map(function (p) {
          return ((p[0] - c[0]) * dx + (p[1] - c[1]) * dy) / size;
        }).sort(function (a, b) { return a - b; });
        if (Math.min(along[1], size) - Math.max(along[0], 0) > STRETCH_TOLERANCE) return true;
      }
    }
    return false;
  }

  function alongAPile(record, project) {
    var piles = ((project && project.beams) || []).filter(function (beam) {
      return (beam.kind || 'beam') === 'beam' && beam.active !== false;
    });
    for (var i = 0; i < piles.length; i += 1) {
      if (runsAlong(record.points || [], piles[i].points || [])) {
        return record.name + ' runs along ' + piles[i].name + '. Put it on '
          + piles[i].name + ' instead (Along in the window, --structure on the command '
          + 'line) and set From and To';
      }
    }
    return null;
  }

  function validateSection(section) {
    if (!section.name || !section.name.trim()) return 'Section name cannot be empty.';
    // Null is a choice: each stretch of contact then takes its own soil's Rinter.
    if (section.r_inter !== null && section.r_inter !== undefined
        && !(section.r_inter > 0 && section.r_inter <= 1)) {
      return 'The strength reduction R_inter must be above 0 and at most 1.';
    }
    if (!(section.virtual_thickness > 0)) {
      return 'The virtual thickness must be greater than zero.';
    }
    var stiffnesses = ['INTERFACE_NORMAL_STIFFNESS', 'INTERFACE_SHEAR_STIFFNESS'];
    for (var i = 0; i < stiffnesses.length; i += 1) {
      var value = (section.variables || {})[stiffnesses[i]];
      if (value !== undefined && !(value > 0)) {
        return stiffnesses[i] + ' must be greater than zero.';
      }
    }
    var problem = App.PropertySets.validate('interface', section);
    if (problem) return problem;
    // What Kratos' Coulomb contact law checks (`InterfaceCoulombLaw::Check`).
    var phi = (section.variables || {}).GEO_FRICTION_ANGLE;
    var psi = (section.variables || {}).GEO_DILATANCY_ANGLE;
    if (coulomb(section) && typeof phi === 'number' && !(phi > 0 && phi < 90)) {
      return 'GEO_FRICTION_ANGLE of a Coulomb contact must be above 0 and below 90 degrees.';
    }
    if (typeof phi === 'number' && typeof psi === 'number' && psi > phi) {
      return 'GEO_DILATANCY_ANGLE cannot be larger than GEO_FRICTION_ANGLE.';
    }
    // No material and no stiffnesses is the ordinary case, not an error: the contact
    // then derives from whatever soil each stretch runs against. The server dropped
    // the old refusal for that reason (core/model/schemas.py, InterfaceSection), and
    // the one case with nothing to derive from -- no soil either side -- is caught at
    // export, where the adjacent bodies are known.
    return null;
  }

  /* Every write goes through the one structures endpoint, carrying the loads
     unchanged: the server validates the whole project, so an interface and the
     section it points at have to arrive together. */
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
            App.Command.err('Could not save interface: ' + error.message);
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

  function save(record, sections) {
    var problem = validate(record, App.PROJECT);
    if (problem) return Promise.reject(new Error(problem));
    var library = sections || sectionsFor(App.PROJECT, record);
    for (var i = 0; i < library.length; i += 1) {
      var bad = validateSection(library[i]);
      if (bad) return Promise.reject(new Error(bad));
    }
    var all = copy(storedInterfaces());
    var at = all.findIndex(function (item) { return item.id === record.id; });
    if (at < 0) all.push(copy(record)); else all[at] = copy(record);

    return patch({ loads: copy(storedLoads()), interfaces: all,
                   interface_sections: library },
                 'Saved interface ' + record.name + '.')
      .then(function () {
        if (App.selectObject) App.selectObject(record.id, 'tree');
        return record;
      });
  }

  function remove(id) {
    var record = collection().filter(function (item) { return item.id === id; })[0];
    if (!record) return Promise.resolve(false);
    var all = copy(storedInterfaces()).filter(function (item) { return item.id !== id; });
    if (App.state && App.state.selection === id && App.selectObject) App.selectObject(null);
    // The sections stay: a contact property set is a reusable library entry, not
    // something the last interface using it takes with it.
    return patch({ loads: copy(storedLoads()), interfaces: all,
                   interface_sections: copy(storedSections()) },
                 'Deleted interface ' + record.name + '.');
  }

  function sectionOf(record) {
    return storedSections().filter(function (s) { return s.id === record.section; })[0]
      || Object.assign({ id: record.section }, defaultSection());
  }

  function pileOf(record, project) {
    return ((project || App.PROJECT || {}).beams || [])
      .filter(function (beam) { return beam.id === record.structure; })[0];
  }

  /* What the interface runs along, for the explorer and the viewport: its own
     points, the pile's polyline, or the part of it between From and To, in the
     pile's own order (`Project.interface_path`). */
  function pathOf(record, project) {
    if (!record) return [];
    if (!record.structure) return record.points || [];
    var pile = pileOf(record, project);
    if (!pile || !pile.points) return [];
    if (!record.stretch) return pile.points;
    var start = nearest(pile.points, record.stretch[0]);
    var end = nearest(pile.points, record.stretch[1]);
    return start && end ? between(pile.points, start.along, end.along) : pile.points;
  }

  function length(record, project) {
    var points = pathOf(record, project);
    var total = 0;
    for (var i = 1; i < points.length; i += 1) {
      var dx = points[i][0] - points[i - 1][0];
      var dz = points[i][1] - points[i - 1][1];
      total += Math.sqrt(dx * dx + dz * dz);
    }
    return total;
  }

  /* ── The window: where the interface goes, which face, which contact ── */

  var OWN = '';             // the Along choice for a line of the interface's own
  var NEW_CONTACT = '';     // the Contact choice for a new property set

  var SIDE_LABELS = { both: 'Both sides', left: 'Left (toward -x)',
                      right: 'Right (toward +x)', below: 'Below', above: 'Above' };

  /* Two points down the middle of the section, where a free line is drafted. */
  function middleLine(project) {
    var d = project.domain;
    var x = d.x0 + (d.x1 - d.x0) * 0.5;
    return [[x, d.y_top], [x, d.y_top - (d.y_top - d.y_bottom) * 0.5]];
  }

  function numberInput(value) {
    return App.UI.el('input.mesh-setting-control', {
      type: 'number', step: '0.1', value: Number.isFinite(value) ? String(value) : ''
    });
  }

  function pick(record) {
    if (!App.DrawInput || !App.DrawInput.start) return;
    App.DrawInput.start('load', {
      count: 2,
      onComplete: function (points) {
        var picked = points.map(function (point) { return [point[0], point[1]]; });
        if (record.structure) record.stretch = picked;
        else record.points = picked;
        open(record);
      }
    });
  }

  /* Create and Edit open the same window. Along picks a sheet pile by name, or the
     interface's own coordinates; on a pile From and To start at its two ends, so a
     plain Save holds the whole pile. Nothing is saved until Save, and Save runs the
     project's own checks first (`validate`). */
  function open(source, note) {
    if (!App.Dialogs || !App.Dialogs.open) return;
    var project = App.PROJECT;
    var record = copy(source);
    var editing = collection().some(function (item) { return item.id === record.id; });
    var piles = livePiles(project);
    var sections = storedSections();
    var state = {
      name: record.name, along: record.structure || OWN,
      stretch: record.stretch, points: record.points || middleLine(project),
      side: record.side, active: record.active !== false,
      section: sections.some(function (s) { return s.id === record.section; })
        ? record.section : NEW_CONTACT
    };
    var el = App.UI.el, controls = {}, form, message, shell;

    function pileNamed(id) {
      return piles.filter(function (beam) { return beam.id === id; })[0];
    }

    function fromTo() {
      var pile = pileNamed(state.along);
      return state.stretch || [pile.points[0], pile.points[pile.points.length - 1]];
    }

    /* The window's values as a record, unchecked. */
    function current() {
      read();
      var out = copy(record);
      out.name = state.name.trim();
      out.side = state.side;
      out.active = state.active;
      out.section = state.section === NEW_CONTACT
        ? (sections.some(function (s) { return s.id === record.section; })
          ? nextSectionId(project) : record.section)
        : state.section;
      if (state.along === OWN) {
        out.structure = null;
        out.points = copy(state.points);
        out.stretch = null;
      } else {
        out.structure = state.along;
        out.points = null;
        out.stretch = copy(fromTo());
      }
      return out;
    }

    function read() {
      if (!controls.name) return;
      state.name = controls.name.value;
      state.side = controls.side.value;
      state.active = controls.active.checked;
      state.section = controls.section.value;
      if (state.along === OWN) {
        state.points = controls.points.map(function (pair) {
          return [Number(pair[0].value), Number(pair[1].value)];
        });
      } else {
        state.stretch = [[Number(controls.from[0].value), Number(controls.from[1].value)],
                         [Number(controls.to[0].value), Number(controls.to[1].value)]];
      }
    }

    function row(label, control, help) {
      form.appendChild(el('label.mesh-setting-label', { text: label }));
      form.appendChild(control);
      form.appendChild(el('div.mesh-setting-help', { text: help || '' }));
    }

    /* The form is rebuilt whole; where it was scrolled to is kept, so a choice does
       not throw the window back to the top. */
    function render() {
      var scrolled = form.scrollTop, outer = form.parentNode, outerScrolled = outer ? outer.scrollTop : 0;
      fill();
      form.scrollTop = scrolled;
      if (outer) outer.scrollTop = outerScrolled;
    }

    function fill() {
      form.textContent = '';
      controls = {};
      controls.name = el('input.mesh-setting-control', { type: 'text', value: state.name });
      row('Name', controls.name, 'Shown in the Model explorer and Kratos submodel part.');

      controls.along = el('select.mesh-setting-control');
      controls.along.appendChild(el('option', { value: OWN, text: 'Own coordinates' }));
      piles.forEach(function (beam) {
        controls.along.appendChild(el('option', { value: beam.id, text: beam.name }));
      });
      controls.along.value = state.along;
      controls.along.addEventListener('change', function () {
        read();
        state.along = controls.along.value;
        state.stretch = null;
        if (state.along === OWN) {
          state.points = middleLine(project);
          if (state.side === 'both') state.side = 'left';
        }
        render();
      });
      row('Along', controls.along,
          'A sheet pile the interface follows, or a line of its own through the soil.');

      var path;
      if (state.along === OWN) {
        controls.points = state.points.map(function (point, index) {
          var pair = [numberInput(point[0]), numberInput(point[1])];
          row('x' + (index + 1), pair[0], 'Point ' + (index + 1) + ' of the line [m].');
          row('y' + (index + 1), pair[1], 'Elevation of point ' + (index + 1) + ' [m].');
          return pair;
        });
        var buttons = el('div');
        var add = el('button.btn.btn-sm', { type: 'button', text: 'Add point' });
        var drop = el('button.btn.btn-sm', { type: 'button', text: 'Remove last point' });
        add.addEventListener('click', function () {
          read();
          var last = state.points[state.points.length - 1];
          state.points.push([last[0], last[1] - 1]);
          render();
        });
        drop.addEventListener('click', function () {
          read();
          if (state.points.length > 2) state.points.pop();
          render();
        });
        drop.disabled = state.points.length <= 2;
        buttons.appendChild(add);
        buttons.appendChild(drop);
        row('', buttons, 'A bent line has more than two points.');
        path = state.points;
      } else {
        var ends = fromTo();
        controls.from = [numberInput(ends[0][0]), numberInput(ends[0][1])];
        controls.to = [numberInput(ends[1][0]), numberInput(ends[1][1])];
        row('From x', controls.from[0], 'Where the interface starts on the pile [m]. '
            + 'A point off the pile is moved onto it, up to ' + STRETCH_SNAP + ' m away.');
        row('From y', controls.from[1], '[m]');
        row('To x', controls.to[0], 'Where it ends [m]. At the two ends of the pile it '
            + 'holds the whole pile.');
        row('To y', controls.to[1], '[m]');
        path = pileNamed(state.along).points;
      }

      var words = faces(path);
      var offered = (state.along === OWN ? [] : ['both']).concat(words);
      if (offered.indexOf(state.side) < 0) {
        state.side = state.side === 'right' || state.side === 'above' ? words[1] : words[0];
      }
      controls.side = el('select.mesh-setting-control');
      offered.forEach(function (side) {
        controls.side.appendChild(el('option', { value: side, text: SIDE_LABELS[side] }));
      });
      controls.side.value = state.side;
      row('Side', controls.side, words[0] === 'left'
        ? 'Which soil slides on it, as on the screen: left is the soil toward -x, '
          + 'whichever way the line was drawn.'
        : 'Which soil slides on it, as on the screen: below or above the line.');

      controls.section = el('select.mesh-setting-control');
      sections.forEach(function (s) {
        controls.section.appendChild(el('option', { value: s.id, text: s.name || s.id }));
      });
      controls.section.appendChild(el('option', { value: NEW_CONTACT, text: 'New contact' }));
      controls.section.value = state.section;
      row('Contact', controls.section,
          'The contact properties; change their numbers in the Selection explorer.');

      controls.active = el('input.mesh-setting-control', { type: 'checkbox' });
      controls.active.checked = state.active;
      row('Active', controls.active,
          'Inactive interfaces remain in the project but are not exported.');

      message = el('div.mesh-settings-message', { text: note || '' });
      row('', message, '');
    }

    function submit() {
      var out = current();
      if (out.structure) {
        var pile = pileNamed(out.structure);
        try {
          out.stretch = stretchOn(pile, out.stretch[0], out.stretch[1]);
        } catch (error) {
          message.textContent = error.message;
          return null;
        }
        // The moved points, as they are saved.
        state.stretch = out.stretch;
        var shown = fromTo();
        controls.from[0].value = String(shown[0][0]);
        controls.from[1].value = String(shown[0][1]);
        controls.to[0].value = String(shown[1][0]);
        controls.to[1].value = String(shown[1][1]);
      }
      var problem = validate(out, project);
      if (problem) { message.textContent = problem; return null; }
      return save(out, sectionsFor(project, out)).then(function () { shell.close(); },
        function (error) { message.textContent = error.message; });
    }

    shell = App.Dialogs.open({
      title: (editing ? 'Edit' : 'Create') + ' interface',
      width: 560, height: 660,
      buttons: [
        { label: 'Pick on model…', onClick: function () { pick(current()); } },
        { label: 'Save', primary: true, keepOpen: true, onClick: submit },
        { label: 'Cancel' }
      ],
      build: function (body) {
        body.classList.add('mesh-settings-body');
        form = el('div.mesh-settings-form');
        body.appendChild(form);
        render();
      }
    });
    return shell;
  }

  function start(structure) {
    if (!App.PROJECT) return;
    if (!available(App.PROJECT)) {
      if (App.Command) App.Command.note(unavailableMessage(App.PROJECT));
      return;
    }
    var record;
    try {
      record = draft(App.PROJECT, structure);
    } catch (error) {
      if (App.Command) App.Command.note(error.message);
      return;
    }
    return open(record);
  }

  function edit(id) {
    var record = collection().filter(function (item) { return item.id === id; })[0];
    if (!record) return;
    return open(record);
  }

  function isInterfaceKey(key) {
    return collection().some(function (record) { return record.id === key; });
  }

  return {
    SIDES: SIDES, STRETCH_SNAP: STRETCH_SNAP, defaultSection: defaultSection,
    ELASTIC_LAW: ELASTIC_LAW, COULOMB_LAW: COULOMB_LAW, LAWS: LAWS, STRENGTH: STRENGTH,
    coulomb: coulomb, ownStrength: ownStrength, noStrength: noStrength,
    strengthProblem: strengthProblem,
    setOwnStrength: setOwnStrength, soilStrength: soilStrength,
    nearest: nearest, between: between, faces: faces, snap: snap, stretchOn: stretchOn,
    pileOf: pileOf,
    available: available, unavailableMessage: unavailableMessage,
    livePiles: livePiles, draft: draft, sectionsFor: sectionsFor, sectionOf: sectionOf,
    pathOf: pathOf, length: length,
    validate: validate, validateSection: validateSection, sideOn: sideOn,
    middleLine: middleLine,
    save: save, remove: remove, start: start, edit: edit, open: open,
    isInterfaceKey: isInterfaceKey
  };
})();
