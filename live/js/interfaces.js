/* ══════════════════════════════════════════════════════════════════
   interfaces.js — Structure-mode interfaces.

   An interface is the contact between a structure and the ground around it: the
   thin band where the two slide past one another and can pull apart, instead of
   being welded together the way a bare sheet pile is. Kratos writes it as a
   zero-thickness element -- two coincident faces with separate nodes -- and the
   server does the node splitting after meshing (server/app/interfaces.py).

   Two ways to place one, and a record carries exactly one of them:

     • along a sheet pile, which is the usual case and the one
       examples/crow_case.mdpa contains. `side` says which of the two soils is
       unglued from the wall; "both" is the normal answer for a retaining wall.
     • along its own polyline through the soil -- an excavation face, a lining,
       a slip surface. There is no structure between the two soils then, so one
       of them has to keep the original nodes and `side` says which is detached.

   Left and right are relative to walking the line in the order its points are
   stored, the same convention the exported element's node order carries.

   Plane strain only. Every reference deck in examples/ is a section, and a 3D
   interface is a different element with a different node layout and no fixture
   to pin it -- see the INTERFACES table in server/app/kratos.py.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Interfaces = (function () {

  /* Steel against a medium sand: the reduction factor an engineer starts from,
     and a virtual thickness the stiffness is derived over. The material is filled
     in from the project when the interface is drafted, because the factor reduces
     a particular soil's strength rather than a number in the abstract. */
  function defaultSection() {
    return Object.assign({ name: 'Interface', r_inter: 0.7, virtual_thickness: 0.01,
                           permeability: 'Neutral' }, App.PropertySets.defaults('interface'));
  }

  var SIDES = ['both', 'left', 'right'];

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

  /* The coordinate-first path, like every other structure here: an interface on
     the first live sheet pile if there is one, and a free line down the middle of
     the section if there is not. The user then edits it in the explorer. */
  function draft(project, structure) {
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
      active: true
    };
    if (pile) {
      record.structure = pile.id;
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
     plus a default the first time anyone draws one. The default is bound to a soil
     material, because r_inter reduces that soil's strength. */
  function sectionsFor(project, record) {
    var library = copy((project && project.interface_sections) || []);
    var known = library.some(function (s) { return s.id === record.section; });
    if (!known) {
      var soil = ((project && project.materials) || [])[0];
      library.push(Object.assign({ id: record.section }, defaultSection(),
                                 { material: soil ? soil.id : null }));
    }
    return library;
  }

  function validate(record, project) {
    if (!record.name || !record.name.trim()) return 'Name cannot be empty.';
    if (!record.section) return 'An interface needs a section.';
    if (SIDES.indexOf(record.side) < 0) return 'An interface side must be both, left or right.';
    var free = !record.structure;
    if (free === !record.points) {
      return 'An interface follows either a sheet pile or its own points, not both.';
    }
    if (!free) {
      var piles = livePiles(project || App.PROJECT);
      if (!piles.some(function (b) { return b.id === record.structure; })) {
        return 'An interface can only follow a live sheet pile.';
      }
      return null;
    }
    if (record.side === 'both') {
      return 'A free interface has no structure between its sides; detach the left or the right.';
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
    // No material and no stiffnesses is the ordinary case, not an error: the contact
    // then derives from whatever soil each stretch runs against. The server dropped
    // the old refusal for that reason (server/app/schemas.py, InterfaceSection), and
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

  /* What the interface runs along, for the explorer and the viewport: the pile's
     own polyline when it follows one, its own points when it does not. */
  function pathOf(record, project) {
    if (!record) return [];
    if (!record.structure) return record.points || [];
    var pile = ((project || App.PROJECT || {}).beams || [])
      .filter(function (beam) { return beam.id === record.structure; })[0];
    return (pile && pile.points) || [];
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
    return save(record, sectionsFor(App.PROJECT, record));
  }

  function edit(id) {
    var record = collection().filter(function (item) { return item.id === id; })[0];
    if (!record) return;
    return save(copy(record), copy(storedSections()));
  }

  function isInterfaceKey(key) {
    return collection().some(function (record) { return record.id === key; });
  }

  return {
    SIDES: SIDES, defaultSection: defaultSection,
    available: available, unavailableMessage: unavailableMessage,
    livePiles: livePiles, draft: draft, sectionsFor: sectionsFor, sectionOf: sectionOf,
    pathOf: pathOf, length: length,
    validate: validate, validateSection: validateSection,
    save: save, remove: remove, start: start, edit: edit,
    isInterfaceKey: isInterfaceKey
  };
})();
