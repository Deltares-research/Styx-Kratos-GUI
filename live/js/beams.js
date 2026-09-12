/* ══════════════════════════════════════════════════════════════════
   beams.js — Structure-mode sheet piles.

   A pile is a dimension-native (x, z) polyline plus a reference to a reusable
   section, the same split the server keeps: several piles normally share one
   profile, and the numbers are edited in one place so two copies of "AZ 26"
   cannot drift apart.

   The solid model holds the other two kinds this module also authors. A wall in
   plan is a *panel* -- a footprint swept between two levels, carrying a thickness
   and meshed as shells -- and a bored pile or king post is a *member*, the same
   profile a sheet pile uses, standing in space. Which kinds a project can hold is
   its dimension's business; `available()` and `draft()` ask, rather than assume.

   Confidence note: every reference deck in examples/ is plane strain, so the 2D
   pile's element classes are the only ones pinned by a fixture. The 3D classes
   follow Kratos' documented naming and are named in one place, app/kratos.py.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Beams = (function () {

  /* How far the model reaches, which is not the same as the borehole domain: a drawn
     or imported part may stand above `z_top`, and a structure placed on one is on
     model geometry. `App.Model.extentOf` mirrors the server's `Project.extent`; the
     fallback keeps this module usable in a page that has no App.Model. */
  function extent(project) {
    return (App.Model && App.Model.extentOf)
      ? App.Model.extentOf(project)
      : (project && project.domain);
  }


  /* S355 sheet piling, near an AZ 26-700 profile per metre run. A starting point
     the user edits, not a claim about their wall. */
  var DEFAULT_SECTION = {
    name: 'Sheet pile section', E: 2.1e8, nu: 0.3,
    area: 0.0198, inertia: 5.52e-4, density: 7850, spacing: 1
  };

  /* The same steel as a panel rather than as a metre run of one: a wall is defined
     by how thick it is. 0.4 m is a diaphragm wall, the usual 3D case. */
  var DEFAULT_PANEL_SECTION = {
    name: 'Wall section', E: 2.1e8, nu: 0.3, thickness: 0.4, density: 7850
  };

  /* Which kind of structure a project of this dimension holds. A 2D section holds
     sheet piles; the solid model holds walls and the members standing in it. */
  function kindsFor(project) {
    if (!project) return [];
    return project.dimension === 2 ? ['beam'] : ['panel', 'member'];
  }

  function kindOf(beam) { return (beam && beam.kind) || 'beam'; }

  function isPanel(beam) { return kindOf(beam) === 'panel'; }

  function copy(value) { return JSON.parse(JSON.stringify(value)); }

  function collection() { return App.BEAMS || []; }

  function storedBeams() {
    return (App.PROJECT && App.PROJECT.beams) || collection();
  }

  /* The working copy the property grid edits in place, exactly as App.LAYERS and
     App.MATERIALS are edited; it falls back to the stored project before the first
     derive has run. */
  function sections(beam) {
    return isPanel(beam)
      ? (App.PANEL_SECTIONS || storedPanelSections())
      : (App.BEAM_SECTIONS || storedSections());
  }

  function storedSections() {
    return (App.PROJECT && App.PROJECT.beam_sections) || [];
  }

  function storedPanelSections() {
    return (App.PROJECT && App.PROJECT.panel_sections) || [];
  }

  function storedLoads() {
    return (App.PROJECT && App.PROJECT.loads) || [];
  }

  /* A sheet pile is authored in the x-z elevation and nowhere else: that is the
     plane the confirmed beam elements describe. A wall or a member is authored in
     the solid model, for the mirror of that reason. */
  function available(project, kind) {
    if (!project) return false;
    if (project.dimension === 2) {
      return (kind || 'beam') === 'beam' && (project.section_plane || 'xz') === 'xz';
    }
    return kindsFor(project).indexOf(kind || 'panel') >= 0;
  }

  function unavailableMessage(project, kind) {
    if ((kind || 'beam') === 'beam') {
      return project && project.dimension === 2
        ? 'Sheet piles are created in the x-z section.'
        : 'A sheet pile is a 2D section object; switch to 2D, or create a wall instead.';
    }
    return kind === 'panel'
      ? 'Wall panels are created in the 3D model; switch to 3D, or create a sheet pile.'
      : 'Members are created in the 3D model; switch to 3D, or create a sheet pile.';
  }

  function nextId(list, prefix) {
    var used = {};
    (list || []).forEach(function (item) { used[item.id] = true; });
    var number = 1;
    while (used[prefix + number]) number += 1;
    return prefix + number;
  }

  /* A wall, drawn as a footprint in plan and swept from the ground down. The levels
     are the domain's own until the user edits them, which is what a wall built from
     the surface is. */
  function draftPanel(project, footprint) {
    if (!available(project, 'panel')) throw new Error(unavailableMessage(project, 'panel'));
    var d = project.domain;
    var plan = (footprint || []).map(function (p) { return [p[0], p[1]]; });
    if (plan.length < 2) throw new Error('A wall needs at least two points.');
    plan.forEach(function (p) {
      if (!p.every(Number.isFinite)) throw new Error('Every wall coordinate must be a number.');
      if (p[0] < d.x0 || p[0] > d.x1 || p[1] < d.y0 || p[1] > d.y1) {
        throw new Error('The wall must stay inside the model domain.');
      }
    });
    var id = nextId(project.beams || [], 'panel_');
    var existing = (project.panel_sections || [])[0];
    return {
      id: id,
      name: 'Wall ' + id.slice('panel_'.length),
      kind: 'panel',
      section: existing ? existing.id : 'panelsection_1',
      footprint: plan,
      z_top: d.z_top,
      z_toe: d.z_top - (d.z_top - d.z_bottom) * 0.5,
      active: true
    };
  }

  /* A member: a polyline in space, vertical by default, which is the pile or king
     post the 3D model is usually given. */
  function draftMember(project, points) {
    if (!available(project, 'member')) throw new Error(unavailableMessage(project, 'member'));
    var d = project.domain;
    var span = extent(project);
    var space = (points || []).map(function (p) { return [p[0], p[1], p[2]]; });
    if (space.length < 2) throw new Error('A member needs at least two points.');
    space.forEach(function (p) {
      if (!p.every(Number.isFinite)) throw new Error('Every member coordinate must be a number.');
      if (p[0] < span.x0 || p[0] > span.x1 || p[1] < span.y0 || p[1] > span.y1
          || p[2] < span.z_bottom || p[2] > span.z_top) {
        throw new Error('The member must stay inside the model domain.');
      }
    });
    var id = nextId(project.beams || [], 'member_');
    var existing = (project.beam_sections || [])[0];
    return {
      id: id,
      name: 'Member ' + id.slice('member_'.length),
      kind: 'member',
      section: existing ? existing.id : 'beamsection_1',
      points: space,
      active: true
    };
  }

  function draftFromPoints(project, points) {
    if (!available(project, 'beam')) {
      throw new Error('Sheet piles are created in the 2D x-z section.');
    }
    if (!points || points.length < 2) {
      throw new Error('A sheet pile needs at least two points.');
    }
    var d = project.domain;
    var span = extent(project);
    var flat = points.map(function (p) { return [p[0], p[2] === undefined ? p[1] : p[2]]; });
    flat.forEach(function (p) {
      if (!p.every(Number.isFinite)) throw new Error('Every pile coordinate must be a number.');
      if (p[0] < span.x0 || p[0] > span.x1
          || p[1] < span.z_bottom || p[1] > span.z_top) {
        throw new Error('The sheet pile must stay inside the model domain.');
      }
    });
    for (var i = 1; i < flat.length; i += 1) {
      if (flat[i][0] === flat[i - 1][0] && flat[i][1] === flat[i - 1][1]) {
        throw new Error('A sheet pile cannot repeat the same point twice.');
      }
    }
    var beams = (project.beams || []);
    var id = nextId(beams, 'beam_');
    var existing = (project.beam_sections || [])[0];
    return {
      id: id,
      name: 'Sheet pile ' + id.slice('beam_'.length),
      kind: 'beam',
      section: existing ? existing.id : 'beamsection_1',
      points: flat,
      active: true
    };
  }

  /* The coordinate-first path: a pile down the middle of the section, which the
     user then edits. Picking in the viewport is the shortcut, not the contract. */
  function draft(project, kind) {
    var d = project && project.domain;
    var wanted = kind || (project && project.dimension === 2 ? 'beam' : 'panel');
    if (!available(project, wanted)) throw new Error(unavailableMessage(project, wanted));
    var x = d.x0 + (d.x1 - d.x0) * 0.5;
    if (wanted === 'panel') {
      // Across the middle of the site, a quarter in from either edge: a wall the
      // user drags to where their excavation actually is.
      var y0 = d.y0 + (d.y1 - d.y0) * 0.25;
      var y1 = d.y1 - (d.y1 - d.y0) * 0.25;
      return draftPanel(project, [[x, y0], [x, y1]]);
    }
    if (wanted === 'member') {
      var y = d.y0 + (d.y1 - d.y0) * 0.5;
      return draftMember(project, [[x, y, d.z_top],
                                   [x, y, d.z_top - (d.z_top - d.z_bottom) * 0.5]]);
    }
    var toe = d.z_top - (d.z_top - d.z_bottom) * 0.5;
    return draftFromPoints(project, [[x, 0, d.z_top], [x, 0, toe]]);
  }

  /* The section list this pile needs saved alongside it: the project's own, plus a
     default profile the first time anyone draws a pile. */
  function sectionsFor(project, beam) {
    var stored = isPanel(beam) ? (project && project.panel_sections)
                               : (project && project.beam_sections);
    var library = copy(stored || []);
    var known = library.some(function (s) { return s.id === beam.section; });
    if (!known) {
      library.push(Object.assign({ id: beam.section },
                                 isPanel(beam) ? DEFAULT_PANEL_SECTION : DEFAULT_SECTION));
    }
    return library;
  }

  /* A polyline of `width` coordinates per point, with no repeated point: the shape
     check every kind here shares, differing only in how many numbers a point has. */
  function validatePolyline(points, width, noun) {
    if (!points || points.length < 2) return 'A ' + noun + ' needs at least two points.';
    for (var i = 0; i < points.length; i += 1) {
      if (points[i].length !== width || !points[i].every(Number.isFinite)) {
        return 'Every ' + noun + ' coordinate must be a number.';
      }
      if (i && points[i].every(function (v, a) { return v === points[i - 1][a]; })) {
        return 'A ' + noun + ' cannot repeat the same point twice.';
      }
    }
    return null;
  }

  function validate(beam) {
    if (!beam.name || !beam.name.trim()) return 'Name cannot be empty.';
    var kind = kindOf(beam);
    if (!beam.section) {
      return 'A ' + (kind === 'panel' ? 'wall' : kind === 'member' ? 'member' : 'sheet pile')
        + ' needs a section.';
    }
    if (kind === 'panel') {
      var flat = validatePolyline(beam.footprint, 2, 'wall');
      if (flat) return flat;
      if (!(Number.isFinite(beam.z_top) && Number.isFinite(beam.z_toe))) {
        return 'Every wall level must be a number.';
      }
      if (!(beam.z_top > beam.z_toe)) return 'A wall must have its top above its toe.';
      return null;
    }
    if (kind === 'member') return validatePolyline(beam.points, 3, 'member');
    return validatePolyline(beam.points, 2, 'sheet pile');
  }

  function validateSection(section) {
    if (!section.name || !section.name.trim()) return 'Section name cannot be empty.';
    // A wall carries a thickness where a pile carries an area and an inertia per
    // metre run, so which numbers have to be positive is the section's own business.
    var positive = section.thickness !== undefined
      ? ['E', 'thickness', 'density']
      : ['E', 'area', 'inertia', 'density', 'spacing'];
    for (var i = 0; i < positive.length; i += 1) {
      if (!(section[positive[i]] > 0)) {
        return 'Section ' + positive[i] + ' must be greater than zero.';
      }
    }
    if (!(section.nu >= 0 && section.nu < 0.5)) {
      return "Poisson's ratio must be at least 0 and below 0.5.";
    }
    return null;
  }

  /* Every write goes through the one structures endpoint, carrying the loads
     unchanged: the server validates the whole project, so a pile and the section
     it points at have to arrive together. */
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
              App.Command.err('Could not save sheet pile: ' + error.message);
            }
            throw error;
          }, function () {
            if (App.Command && App.Command.err) {
              App.Command.err('Could not save sheet pile: ' + error.message);
            }
            throw error;
          });
      });
  }

  /* What this structure is called in a sentence to the user. */
  function noun(beam) {
    return { panel: 'wall', member: 'member' }[kindOf(beam)] || 'sheet pile';
  }

  /* The patch body for one structure: its own library under its own key, and the
     other one left out so the server keeps it as it is. */
  function libraries(beam, profiles) {
    return isPanel(beam) ? { panel_sections: profiles } : { beam_sections: profiles };
  }

  function save(beam, sections) {
    var problem = validate(beam);
    if (problem) return Promise.reject(new Error(problem));
    var profiles = sections || sectionsFor(App.PROJECT, beam);
    for (var i = 0; i < profiles.length; i += 1) {
      var bad = validateSection(profiles[i]);
      if (bad) return Promise.reject(new Error(bad));
    }
    var beams = copy(storedBeams());
    var at = beams.findIndex(function (item) { return item.id === beam.id; });
    if (at < 0) beams.push(copy(beam)); else beams[at] = copy(beam);

    var body = Object.assign({ loads: copy(storedLoads()), beams: beams },
                             libraries(beam, profiles));
    return patch(body, 'Saved ' + noun(beam) + ' ' + beam.name + '.')
      .then(function () {
        if (App.selectObject) App.selectObject(beam.id, 'tree');
        return beam;
      });
  }

  function remove(id) {
    var beam = collection().filter(function (item) { return item.id === id; })[0];
    if (!beam) return Promise.resolve(false);
    var beams = copy(storedBeams()).filter(function (item) { return item.id !== id; });
    if (App.state && App.state.selection === id && App.selectObject) App.selectObject(null);
    // The sections stay: a profile is a reusable library entry, not something the
    // last structure using it takes with it.
    var body = Object.assign({ loads: copy(storedLoads()), beams: beams },
                             libraries(beam, copy(sections(beam))));
    return patch(body, 'Deleted ' + noun(beam) + ' ' + beam.name + '.');
  }

  function sectionOf(beam) {
    return sections(beam).filter(function (s) { return s.id === beam.section; })[0]
      || Object.assign({ id: beam.section },
                       isPanel(beam) ? DEFAULT_PANEL_SECTION : DEFAULT_SECTION);
  }

  /* `kind` comes from the tool the user picked: the rail's flyout offers a wall and
     a member in 3D, and the plain sheet pile in 2D. Left out, each dimension gets
     the structure it is usually asked for. */
  function start(kind) {
    if (!App.PROJECT) return;
    var wanted = kind || (App.PROJECT.dimension === 2 ? 'beam' : 'panel');
    if (!available(App.PROJECT, wanted)) {
      if (App.Command) App.Command.note(unavailableMessage(App.PROJECT, wanted));
      return;
    }
    var beam = draft(App.PROJECT, wanted);
    var sections = sectionsFor(App.PROJECT, beam);
    if (App.Dialogs && App.Dialogs.beam) return App.Dialogs.beam(beam, sections);
    return save(beam, sections);
  }

  function edit(id) {
    var beam = collection().filter(function (item) { return item.id === id; })[0];
    if (!beam) return;
    // A wall's library is the panel sections, a pile's and a member's the beam
    // sections: sending the wrong one would ask the server to empty the other.
    var library = copy(isPanel(beam) ? storedPanelSections() : storedSections());
    if (App.Dialogs && App.Dialogs.beam) return App.Dialogs.beam(copy(beam), library);
    return save(copy(beam), library);
  }

  function isBeamKey(key) {
    return collection().some(function (beam) { return beam.id === key; });
  }

  return {
    isBeamKey: isBeamKey,
    available: available, draft: draft, draftFromPoints: draftFromPoints,
    draftPanel: draftPanel, draftMember: draftMember,
    kindsFor: kindsFor, kindOf: kindOf, unavailableMessage: unavailableMessage,
    sectionsFor: sectionsFor, sectionOf: sectionOf,
    validate: validate, validateSection: validateSection,
    save: save, remove: remove, start: start, edit: edit,
    DEFAULT_SECTION: DEFAULT_SECTION, DEFAULT_PANEL_SECTION: DEFAULT_PANEL_SECTION
  };
})();
