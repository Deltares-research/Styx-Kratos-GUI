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

   Confidence note: every reference deck is plane strain, so the 2D
   pile's element classes are the only ones pinned by a fixture. The 3D classes
   follow Kratos' documented naming and are named in one place, core/kratos/writer.py.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Beams = (function () {

  /* How far the model reaches, which is not the same as the domain: a drawn
     or imported part may stand above `y_top`, and a structure placed on one is on
     model geometry. `App.Model.extentOf` mirrors the server's `Project.extent`; the
     fallback keeps this module usable in a page that has no App.Model. */
  function extent(project) {
    return (App.Model && App.Model.extentOf)
      ? App.Model.extentOf(project)
      : (project && project.domain);
  }


  /* S355 sheet piling, near an AZ 26-700 profile per metre run: a Kratos property set
     (App.PropertySets), in the project's units. A starting point the user edits, not a
     claim about their wall. */
  function defaultSection() {
    return Object.assign({ name: 'Sheet pile section', spacing: 1 },
                         App.PropertySets.defaults('beam'));
  }

  /* The same steel as a panel rather than as a metre run of one: a wall is defined
     by how thick it is. 0.4 m is a diaphragm wall, the usual 3D case. */
  function defaultPanelSection() {
    return Object.assign({ name: 'Wall section' }, App.PropertySets.defaults('panel'));
  }

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

  /* A sheet pile is authored in the 2D x-y section and nowhere else: that is the
     plane the confirmed beam elements describe. A wall or a member is authored in
     the solid model, for the mirror of that reason. */
  function available(project, kind) {
    if (!project) return false;
    if (project.dimension === 2) {
      return (kind || 'beam') === 'beam';
    }
    return kindsFor(project).indexOf(kind || 'panel') >= 0;
  }

  function unavailableMessage(project, kind) {
    if ((kind || 'beam') === 'beam') {
      return project && project.dimension === 2
        ? 'Sheet piles are created in the 2D x-y section.'
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
      if (p[0] < d.x0 || p[0] > d.x1 || p[1] < d.z0 || p[1] > d.z1) {
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
      y_top: d.y_top,
      y_toe: d.y_top - (d.y_top - d.y_bottom) * 0.5,
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
      if (p[0] < span.x0 || p[0] > span.x1
          || p[1] < span.y_bottom || p[1] > span.y_top
          || p[2] < span.z0 || p[2] > span.z1) {
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
      throw new Error('Sheet piles are created in the 2D x-y section.');
    }
    if (!points || points.length < 2) {
      throw new Error('A sheet pile needs at least two points.');
    }
    var d = project.domain;
    var span = extent(project);
    var flat = points.map(function (p) { return [p[0], p[1]]; });
    flat.forEach(function (p) {
      if (!p.every(Number.isFinite)) throw new Error('Every pile coordinate must be a number.');
      if (p[0] < span.x0 || p[0] > span.x1
          || p[1] < span.y_bottom || p[1] > span.y_top) {
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
      var z0 = d.z0 + (d.z1 - d.z0) * 0.25;
      var z1 = d.z1 - (d.z1 - d.z0) * 0.25;
      return draftPanel(project, [[x, z0], [x, z1]]);
    }
    if (wanted === 'member') {
      var z = d.z0 + (d.z1 - d.z0) * 0.5;
      return draftMember(project, [[x, d.y_top, z],
                                   [x, d.y_top - (d.y_top - d.y_bottom) * 0.5, z]]);
    }
    var toe = d.y_top - (d.y_top - d.y_bottom) * 0.5;
    return draftFromPoints(project, [[x, d.y_top], [x, toe]]);
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
                                 isPanel(beam) ? defaultPanelSection() : defaultSection()));
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
      if (!(Number.isFinite(beam.y_top) && Number.isFinite(beam.y_toe))) {
        return 'Every wall level must be a number.';
      }
      if (!(beam.y_top > beam.y_toe)) return 'A wall must have its top above its toe.';
      return null;
    }
    if (kind === 'member') return validatePolyline(beam.points, 3, 'member');
    return validatePolyline(beam.points, 2, 'sheet pile');
  }

  /* A wall's section is a shell's property set and carries no spacing; a pile's or a
     member's is a beam's. Which one a section is shows in what it carries. */
  function sectionKind(section) {
    return section.spacing === undefined ? 'panel' : 'beam';
  }

  function validateSection(section) {
    if (!section.name || !section.name.trim()) return 'Section name cannot be empty.';
    if (section.spacing !== undefined && !(section.spacing > 0)) {
      return 'Section spacing must be greater than zero.';
    }
    return App.PropertySets.validate(sectionKind(section), section);
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
                       isPanel(beam) ? defaultPanelSection() : defaultSection());
  }

  function input(value, step) {
    return App.UI.el('input.mesh-setting-control', {
      type: 'number', step: step || '0.1', value: String(value)
    });
  }

  /* A text box rather than a number box for a Kratos variable: it may be a flag, a
     list or a name as well as a number (App.PropertySets.parse), and a number box
     would round 2.1e11 into something unreadable. */
  function variableInput(value) {
    return App.UI.el('input.mesh-setting-control', {
      type: 'text', value: App.PropertySets.format(value)
    });
  }

  /* The dialog every kind this module authors shares: a name, its polyline (plus
     the two levels a wall hangs between), whether it is active, and the numbers of
     whichever section it points at -- mirroring loads.js's own `open()`, which is
     the pattern this was missing until now (`App.Dialogs.beam` was checked for but
     never implemented, so a pile used to be drafted and saved with no review at
     all). Editing the section here edits the shared profile, exactly as the
     Selection explorer's own fields already do. */
  function open(source, kind) {
    if (!App.Dialogs || !App.Dialogs.open) return;
    var beam = copy(source);
    kind = kind || kindOf(beam);
    var editing = collection().some(function (item) { return item.id === beam.id; });
    var library = sectionsFor(App.PROJECT, beam);
    var section = copy(library.filter(function (s) { return s.id === beam.section; })[0]
                       || library[0]);
    var field = kind === 'panel' ? 'footprint' : 'points';
    var axisLabels = kind === 'panel' ? ['x', 'z'] : (kind === 'member' ? ['x', 'y', 'z'] : ['x', 'y']);
    var el = App.UI.el, controls = {}, pointRows = [], sectionControls = {};
    var shell, message;

    function submit() {
      beam.name = controls.name.value.trim();
      beam[field] = pointRows.map(function (row) {
        return row.map(function (control) { return Number(control.value); });
      });
      if (kind === 'panel') {
        beam.y_top = Number(controls.y_top.value);
        beam.y_toe = Number(controls.y_toe.value);
      }
      beam.active = controls.active.checked;
      section.variables = section.variables || {};
      Object.keys(sectionControls).forEach(function (key) {
        var value = App.PropertySets.parse(sectionControls[key].value);
        if (key === 'spacing') { section.spacing = Number(sectionControls[key].value); return; }
        if (value === undefined) delete section.variables[key];
        else section.variables[key] = value;
      });
      var problem = validate(beam) || validateSection(section);
      if (problem) { message.textContent = problem; return; }
      var profiles = library.map(function (s) { return s.id === section.id ? section : s; });
      save(beam, profiles).then(function () { shell.close(); }, function (error) {
        message.textContent = error.message;
      });
    }

    shell = App.Dialogs.open({
      title: (editing ? 'Edit ' : 'Create ') + noun(beam),
      width: 520, height: kind === 'panel' ? 580 : 520,
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

        controls.name = el('input.mesh-setting-control', { type: 'text', value: beam.name });
        row('Name', controls.name, 'Shown in the Model explorer and Kratos submodel part.');

        beam[field].forEach(function (point, index) {
          var rowControls = point.map(function (value) { return input(value); });
          pointRows.push(rowControls);
          rowControls.forEach(function (control, axis) {
            row(axisLabels[axis] + (index + 1), control,
                'Vertex ' + (index + 1) + ', world ' + axisLabels[axis] + ' [m].');
          });
        });

        if (kind === 'panel') {
          controls.y_top = input(beam.y_top);
          controls.y_toe = input(beam.y_toe);
          row('Top level', controls.y_top, 'Elevation the wall hangs from [m].');
          row('Toe level', controls.y_toe, 'Elevation of the wall toe [m].');
        }

        controls.active = el('input.mesh-setting-control', { type: 'checkbox' });
        controls.active.checked = beam.active !== false;
        row('Active', controls.active, 'Inactive structures remain in the project but are not exported.');

        // The section's Kratos variables, by Kratos' names and in the project's
        // units; a blank one the server can derive is left to it.
        var sectionKindName = kind === 'panel' ? 'panel' : 'beam';
        App.PropertySets.names(sectionKindName, section,
                               App.PROJECT && App.PROJECT.dimension).forEach(function (key) {
          var control = variableInput((section.variables || {})[key]);
          sectionControls[key] = control;
          var unit = App.Units.variableLabel(key);
          var derived = App.PropertySets.derivable(sectionKindName, key);
          row(key, control, (unit ? '[' + unit + ']' : '')
                            + (derived ? (unit ? ' ' : '') + 'Blank: derived at export.' : ''));
        });
        if (kind !== 'panel') {
          var spacing = input(section.spacing, '0.1');
          sectionControls.spacing = spacing;
          row('Spacing', spacing, 'Out-of-plane centres [m]; a 2D section smears the pile over them.');
        }

        message = el('div.mesh-settings-message');
        row('', message, '');
      }
    });
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
    return open(draft(App.PROJECT, wanted), wanted);
  }

  function edit(id) {
    var beam = collection().filter(function (item) { return item.id === id; })[0];
    if (!beam) return;
    return open(beam, kindOf(beam));
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
    save: save, remove: remove, start: start, edit: edit, open: open,
    defaultSection: defaultSection, defaultPanelSection: defaultPanelSection
  };
})();
