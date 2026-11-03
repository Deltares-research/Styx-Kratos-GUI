/* ══════════════════════════════════════════════════════════════════
   model.js — the server's project, in the shape the frozen UI expects.

   js/data.js is still loaded verbatim, but only its UI chrome (ICONS, MENUS,
   TOOLBAR, MODES, RAILS) is used as-is. The model halves -- MATERIALS and
   LAYERS -- are replaced from the server here, and the two derived
   structures are rebuilt.

   Those derived structures are the reason this file exists. App.TREES and
   App.OBJECT_PROPS are computed once inside an IIFE at js/data.js:460-579 and
   closed over, so nothing can recompute them. That is why a layer added in the
   soil dialog never appears in the model tree today.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Model = (function () {

  /* Falls back to the frozen demo extents until a project has been applied, so
     the module is usable before the first fetch resolves. */
  var domain = { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 };

  /* The water table, held beside the domain and for the same reason: it is one object
     for the whole project rather than a property of anything selected, and the
     Selection explorer edits it in place before a single PATCH sends it.

     `margin` and `thickness` are how the slab is *drawn* (WaterLevel's own comment
     calls it a reference plane overhanging the domain, not a solid). They are not
     editable and are carried untouched, because the layers PATCH replaces the whole
     object and dropping them would reset the drawing to its defaults.

     `null` for a model without one, which is what a new project is: there is no
     default level, so nothing about water is shown until `water <level>` sets one
     (frontend/js/water-command.js). */
  var water = null;

  /* ── Mapping ─────────────────────────────────────────────────── */

  /* Mirrors `Project.loads_for` in core/model/schemas.py, and has to stay in step
     with it: a surface load and a line load can be one load seen from two dimensions
     (core/model/load_translation.py translates between them on the mode switch), and both records
     are kept so the round trip does not widen the footprint. Exactly one of a pair
     belongs to the model, or the tree lists the load twice and the viewport draws it
     twice. A 2D load nothing was translated from -- a point load, or a line load below
     the ground surface -- has no surface form and shows in both. */
  function loadsFor(project) {
    var loads = project.loads || [];
    if (project.dimension === 2) {
      // A pad clear of the section plane does not load the section (loads_for(2)).
      var d = project.domain || domain;
      var cut = project.section_offset != null ? project.section_offset : (d.z0 + d.z1) / 2;
      var off = {};
      loads.forEach(function (load) {
        if (load.kind !== 'surface') return;
        if (load.z0 - 1e-9 <= cut && cut <= load.z1 + 1e-9) return;
        if (load.derived_from) off[load.derived_from] = true;
        loads.forEach(function (other) {
          if (other.derived_from === load.id) off[other.id] = true;
        });
      });
      return loads.filter(function (load) { return load.kind !== 'surface' && !off[load.id]; });
    }
    var paired = {};
    loads.forEach(function (load) {
      if (load.derived_from) { paired[load.id] = true; paired[load.derived_from] = true; }
    });
    return loads.filter(function (load) {
      return load.kind === 'surface' || !paired[load.id];
    });
  }

  /* Mirrors `Project.structures_for` in core/model/schemas.py, the way `loadsFor`
     mirrors `loads_for` and for the same reason: a sheet pile and a wall panel can be
     one wall seen from two dimensions (core/model/wall_translation.py translates between them on
     the mode switch), and exactly one half of a pair belongs to the model or the tree
     lists the wall twice and the viewport draws it twice. A pile nothing was
     translated from -- a raking or stepped one, which has no panel form -- shows in
     both. */
  /* Mirrors `Project.extent` in core/model/schemas.py: how far the model actually
     reaches, which is the domain grown to cover every drawn or imported part. A
     structure is placed against this, not against `project.domain` -- an embankment
     drawn above `y_top` is model geometry, and a load standing on it was being refused
     as "outside the domain" by both ends at once. Parts saved before their bounding
     box was recorded contribute nothing, exactly as on the server. */
  function extentOf(project) {
    var d = (project && project.domain) || domain;
    var boxes = (((project || {}).custom_parts) || [])
      .map(function (part) { return part.bbox; })
      .filter(function (box) { return box && box.length === 6; });
    if (!boxes.length) return d;
    function low(index, own) {
      return Math.min.apply(null, [own].concat(boxes.map(function (b) { return b[index]; })));
    }
    function high(index, own) {
      return Math.max.apply(null, [own].concat(boxes.map(function (b) { return b[index]; })));
    }
    return {
      x0: low(0, d.x0), y_bottom: low(1, d.y_bottom), z0: low(2, d.z0),
      x1: high(3, d.x1), y_top: high(4, d.y_top), z1: high(5, d.z1)
    };
  }

  function structuresFor(project) {
    var beams = project.beams || [];
    if (project.dimension === 2) {
      return beams.filter(function (b) { return (b.kind || 'beam') === 'beam'; });
    }
    var paired = {};
    beams.forEach(function (b) {
      if (b.derived_from) { paired[b.id] = true; paired[b.derived_from] = true; }
    });
    return beams.filter(function (b) {
      return b.kind === 'panel' || b.kind === 'member' || !paired[b.id];
    });
  }

  function fromProject(project) {
    return {
      domain: project.domain,
      water: project.water,
      // A soil is a Kratos property set (core/model/schemas.py Material): its law and
      // its Variables, under Kratos' names, in the project's units -- carried as they
      // are, because the library goes back in one PATCH that replaces it wholesale and
      // a variable this record dropped is a variable the next save deletes. Only the
      // two interface defaults are renamed, for the frozen library code that reads them.
      MATERIALS: project.materials.map(function (m) {
        return { id: m.id, name: m.name, color: m.color,
                 constitutive_law: m.constitutive_law,
                 variables: JSON.parse(JSON.stringify(m.variables || {})),
                 tables: JSON.parse(JSON.stringify(m.tables || {})),
                 rInter: m.r_inter, interfacePerm: m.interface_permeability };
      }),
      LAYERS: project.layers.map(function (l) {
        return { id: l.id, name: l.name, mat: l.mat, top: l.top, bottom: l.bottom };
      }),
      // Every 2D-native record is built into the solid model too, on the section
      // plane it was drawn on (core/geometry/solid_model.py's `_section_sweeps`), so 3D shows
      // it rather than hiding it: a sheet pile the viewport drops is the bug this
      // filter used to cause. The traffic is one way -- a wall panel is drawn in plan
      // and genuinely has no place in a plane-strain cut -- so 2D still shows only
      // its own kinds.
      LOADS: loadsFor(project).map(function (load) {
        return JSON.parse(JSON.stringify(load));
      }),
      BEAMS: structuresFor(project).map(function (beam) {
        return JSON.parse(JSON.stringify(beam));
      }),
      BEAM_SECTIONS: (project.beam_sections || [])
        .map(function (s) { return JSON.parse(JSON.stringify(s)); }),
      PANEL_SECTIONS: (project.panel_sections || [])
        .map(function (s) { return JSON.parse(JSON.stringify(s)); }),
      ANCHORS: (project.anchors || []).filter(function (anchor) {
        return project.dimension === 2 ? (anchor.kind || 'anchor') === 'anchor' : true;
      }).map(function (a) { return JSON.parse(JSON.stringify(a)); }),
      ANCHOR_SECTIONS: (project.anchor_sections || [])
        .map(function (s) { return JSON.parse(JSON.stringify(s)); }),
      // Shown in 3D as well: an interface is swept onto the section plane there and
      // splits the mesh along it. Its zero-thickness *elements* are still plane strain
      // only -- the export says so in a warning -- but the line is part of the solid
      // model and hiding it made the drawn interface look lost.
      INTERFACES: (project.interfaces || [])
        .map(function (i) { return JSON.parse(JSON.stringify(i)); }),
      INTERFACE_SECTIONS: (project.interface_sections || [])
        .map(function (s) { return JSON.parse(JSON.stringify(s)); }),
      // Shown in 3D too, for the same reason an interface is: the polyline is part of
      // the solid model even though the pressure it applies is plane strain only.
      NORMAL_LOADS: (project.normal_loads || [])
        .map(function (n) { return JSON.parse(JSON.stringify(n)); }),
      // Both kinds, in every dimension: a line kept from the section stays in the list
      // in 3D, as the export keeps it, and says there that it is left out.
      BOUNDARY_CONDITIONS: (project.boundary_conditions || [])
        .map(function (c) { return JSON.parse(JSON.stringify(c)); })
    };
  }

  /* The inverse of the MATERIALS mapping above, for the material-set write path.
     Everything the server's Material schema requires has to be present and
     named its way; an unknown or missing key is a 422. */
  function materialsToServer(materials) {
    return materials.map(function (m) {
      return { id: m.id, name: m.name, color: m.color,
               constitutive_law: m.constitutive_law,
               variables: JSON.parse(JSON.stringify(m.variables || {})),
               tables: JSON.parse(JSON.stringify(m.tables || {})),
               r_inter: m.rInter, interface_permeability: m.interfacePerm };
    });
  }

  /* ── The title bar ──────────────────────────────────────────────────────
     js/app.js:243-245 writes the title once at boot, out of the frozen
     App.PRODUCT constant, and nothing rewrites it -- so a project loaded from
     the server, opened from a file or reset to the seed still announced itself
     as "Untitled project". The name is one more global the frozen UI reads off
     the project, which is what this module is for. */
  function projectTitle(project) {
    var name = project && project.name ? String(project.name).trim() : '';
    return App.PRODUCT.name + '  ' + App.PRODUCT.version + '  —  '
      + (name || 'Untitled project') + '  [Model]';
  }

  /* App.PRODUCT.project moves with it: boot() reads that constant, and boot runs
     after the first project arrives, so leaving it stale would put the old name
     straight back into the bar. */
  function syncTitle(project) {
    var name = project && project.name ? String(project.name).trim() : '';
    App.PRODUCT.project = name || 'Untitled project';
    var bar = typeof document !== 'undefined' && document.getElementById('tb-title');
    if (bar) bar.textContent = projectTitle(project);
  }

  /* The status bar's units item said "m / kN / day" whatever the project held. It
     names the project's own system now, and choosing another one there types the
     `units` command (patches.js) -- the command line stays the way to do it. */
  function syncUnits(project) {
    var item = typeof document !== 'undefined' && document.getElementById('sb-units');
    if (!item || !App.Units) return;
    item.textContent = App.Units.statusText(project);
    item.title = 'The unit system every value is in. Click to convert the project to another.';
    if (item.dataset.wired) return;
    item.dataset.wired = '1';
    item.classList.add('sb-toggle');
    item.addEventListener('click', function () {
      var now = App.Units.current();
      var other = App.Units.systems().filter(function (s) { return s.name !== now; })[0];
      if (other && App.Command && App.Command.run) App.Command.run('units ' + other.name);
    });
  }

  /* Replaces the frozen js/data.js globals with the server's project. Until this
     runs the app is showing data.js's offline seed, which is still written in the
     mockup's Z-up frame -- deliberately, because that file is frozen. Nothing here
     reads its coordinates; the first project to arrive overwrites them wholesale. */
  function apply(project) {
    var mapped = fromProject(project);
    domain = mapped.domain;
    // Copied rather than aliased: the editors below mutate this object in place, and
    // aliasing App.PROJECT.water would make a rejected edit visible to everything
    // that reads the project before the PATCH that would have justified it.
    water = mapped.water ? Object.assign({ margin: 3.0, thickness: 0.06,
                                           specific_weight: null }, mapped.water) : null;
    App.MATERIALS = mapped.MATERIALS;
    // The water every soil holds, edited in the Material sets window in place: a copy,
    // for the same reason as `water`.
    App.FLUID = Object.assign({ bulk_modulus: null, dynamic_viscosity: null }, project.fluid || {});
    App.LAYERS = mapped.LAYERS;
    App.LOADS = mapped.LOADS;
    App.BEAMS = mapped.BEAMS;
    App.BEAM_SECTIONS = mapped.BEAM_SECTIONS;
    App.PANEL_SECTIONS = mapped.PANEL_SECTIONS;
    App.ANCHORS = mapped.ANCHORS;
    App.ANCHOR_SECTIONS = mapped.ANCHOR_SECTIONS;
    App.INTERFACES = mapped.INTERFACES;
    App.INTERFACE_SECTIONS = mapped.INTERFACE_SECTIONS;
    App.NORMAL_LOADS = mapped.NORMAL_LOADS;
    App.BOUNDARY_CONDITIONS = mapped.BOUNDARY_CONDITIONS;
    App.PROJECT = project;
    rebuildDerived();
    syncTitle(project);
    syncUnits(project);
    return project;
  }

  function load() {
    return App.Api.get('/api/project').then(apply);
  }

  /* ── Derived: the model tree ─────────────────────────────────── */

  /* js/data.js:573-577 puts one `soilVolumes` object into all five mode trees.
     Rebuilding it *in place* is what keeps them consistent -- replacing the node
     would only update whichever array we happened to reach. */
  function soilNodes() {
    var found = [], seen = [];
    Object.keys(App.TREES || {}).forEach(function (mode) {
      (function walk(nodes) {
        (nodes || []).forEach(function (n) {
          if (n.obj === 'soil' && seen.indexOf(n) < 0) { seen.push(n); found.push(n); }
          walk(n.children);
        });
      })(App.TREES[mode]);
    });
    return found;
  }

  /* One tree row per soil *body*, not per layer.

     A staged excavation splits the soil inside the pit into the lifts it is dug in, so
     one layer can be four bodies (core/model/schemas.py, `Project.soil_bodies`). Each
     is separately meshed, separately deactivated in a stage, and separately shown or
     hidden -- so each needs its own row with its own eye, or the excavated side has no
     representation in the tree at all.

     The project publishes both the keys and what to call them; deriving either here
     would be a second implementation of the split to keep in step. A project that
     publishes neither -- an older server, the frozen mockup -- still gets its one row
     per layer, which is what this always used to do. */
  function layerBodies(layer) {
    var published = (App.PROJECT && App.PROJECT.soil_body_keys) || [];
    var mine = published.filter(function (key) {
      return key.split('__')[0] === 'soil_' + layer.id;
    });
    return mine.length ? mine : ['soil_' + layer.id];
  }

  function layerChildren(layer) {
    var m = App.matById(layer.mat);
    var labels = (App.PROJECT && App.PROJECT.soil_body_labels) || {};
    return layerBodies(layer).map(function (key) {
      return { label: (labels[key] || layer.name) + '  ·  ' + m.name,
               swatch: m.color, leaf: true, eye: true, obj: key };
    });
  }

  /* Drawn/imported geometry has no place in App.TREES -- js/data.js:572-577 builds
     that structure once, before any of it exists. One shared node, which syncTrees()
     places in the single tree every mode reads, mirrors how soilVolumes above stays
     in sync across modes. */
  var customGeometryNode = {
    label: 'Custom geometry', icon: 'cube', count: 0,
    eye: true, obj: 'group:custom', children: []
  };

  /* A .mdpa import's accepted parts (mdpa-import-dialog.js's checklist "Accept"
     button): read-only, static geometry with no project counterpart -- there is no
     `App.PROJECT` field behind this node the way there is for every other one here --
     so `setImportedParts` below is the only thing that ever touches it, called
     straight from the dialog rather than from `rebuildDerived`'s project-driven pass. */
  var importedMeshNode = {
    label: 'Imported mesh', icon: 'cube', count: 0,
    eye: true, obj: 'group:imported', children: []
  };

  var loadConditionsNode = null;
  var previousLoadKeys = ['load']; // remove the frozen sample property on first rebuild
  var sheetPileNode = null;
  var previousBeamKeys = [];
  var anchorNode = null;
  var previousAnchorKeys = [];
  var interfaceNode = null;
  var previousInterfaceKeys = [];
  var normalLoadNode = null;
  var previousNormalLoadKeys = [];
  var modelConditionsNode = null;
  var boundaryNode = null;
  var previousConditionKeys = [];

  /* The frozen tree's "Water levels" node lists two mockup levels from js/data.js:677
     and a layered_soil project discards it along with the rest of that tree, so the
     water rows had nowhere to be clicked from. One node, one child, because the
     project has exactly one water level -- `Project.water` is a single object, not a
     collection, and a per-stage level is explicitly out of scope (plan sec 7.11).

     Top level, and deliberately not the frozen one: js/data.js:677 puts a "Water
     levels" node *inside* the Attributes library, and that one lists level
     definitions rather than the level this model is at. Exactly the distinction
     `findLoadConditionsNode` draws for "Loads", and settled the same way -- the
     library node is left alone rather than repurposed. */
  var waterLevelNode = null;

  function ensureWaterLevelNode() {
    if (!waterLevelNode) {
      waterLevelNode = { label: 'Water levels', icon: 'waterlevel', count: 1,
                         eye: true, obj: 'group:water', children: [] };
    }
    waterLevelNode.children = [{
      label: 'Global water level  ·  ' + water.y.toFixed(2) + ' m',
      icon: 'water', leaf: true, eye: true, obj: 'water'
    }];
    waterLevelNode.count = 1;
    return waterLevelNode;
  }

  /* Takes the "Water levels" row out of every mode's tree, for a model with no level.
     Top level only: the Attributes library's own "Water levels" node lists definitions,
     not this model's level, and stays. */
  function dropWaterLevelNode() {
    if (!waterLevelNode) return;
    var gone = waterLevelNode;
    waterLevelNode = null;
    Object.keys(App.TREES || {}).forEach(function (mode) {
      var nodes = App.TREES[mode] || [];
      var i = nodes.indexOf(gone);
      if (i >= 0) nodes.splice(i, 1);
    });
  }

  /* Top level only, deliberately: js/data.js:688 also has a "Loads" node *inside*
     the Attributes library, and that one lists load definitions, not the loads in
     the model. Reusing it made the live loads land in a different place depending
     on which project happened to load first. */
  function findLoadConditionsNode() {
    if (loadConditionsNode) return loadConditionsNode;
    Object.keys(App.TREES || {}).some(function (mode) {
      (App.TREES[mode] || []).some(function (node) {
        if (node && node.label === 'Loads' && node.icon === 'load') loadConditionsNode = node;
        return !!loadConditionsNode;
      });
      return !!loadConditionsNode;
    });
    if (!loadConditionsNode) {
      loadConditionsNode = { label: 'Loads', icon: 'load', count: 0, children: [] };
    }
    // Whether it was found or made: js/explorer.js:36 draws the visibility checkbox
    // only for a node carrying both, and a group row without one is the odd row out.
    loadConditionsNode.eye = true;
    loadConditionsNode.obj = 'group:loads';
    return loadConditionsNode;
  }

  /* The frozen data has no sheet-pile node and no per-member Anchors node -- its
     Anchors entry describes the seeded rows, not individual members -- so both are
     created here. Placing them is syncTrees()'s job, not theirs. */
  function ensureSheetPileNode() {
    if (!sheetPileNode) {
      sheetPileNode = { label: 'Sheet piles', icon: 'wall', count: 0,
                        eye: true, obj: 'group:sheetpiles', children: [] };
    }
    return sheetPileNode;
  }

  function ensureAnchorNode() {
    if (!anchorNode) {
      anchorNode = { label: 'Anchors', icon: 'anchor', count: 0,
                     eye: true, obj: 'group:anchors', children: [] };
    }
    return anchorNode;
  }

  /* The frozen tree already has an "Interfaces" row (js/data.js:729): a leaf inside
     Structures claiming eight of them, from the aggregate mockup. It selects nothing
     and cannot be edited, and leaving it beside the live node would put two rows with
     the identical label in one tree -- the dead-twin problem the rail solved for the
     frozen anchor tool. It is dropped, once, and the live node takes the name. */
  function dropFrozenInterfaceRow() {
    Object.keys(App.TREES || {}).forEach(function (mode) {
      (function walk(nodes) {
        if (!nodes) return;
        for (var i = nodes.length - 1; i >= 0; i -= 1) {
          var node = nodes[i];
          if (!node) continue;
          if (node !== interfaceNode && node.label === 'Interfaces' && node.leaf) {
            nodes.splice(i, 1);
            continue;
          }
          walk(node.children);
        }
      })(App.TREES[mode]);
    });
  }

  function ensureInterfaceNode() {
    if (!interfaceNode) {
      interfaceNode = { label: 'Interfaces', icon: 'interface', count: 0,
                        eye: true, obj: 'group:interfaces', children: [] };
    }
    dropFrozenInterfaceRow();
    return interfaceNode;
  }

  /* "Model conditions": the boundary conditions, one row each, and gravity. The frozen
     tree's own "Model conditions" (js/data.js) lists a demo's rows -- Domain, Water,
     Climate -- that select nothing, and two rows of one label would be the dead-twin
     problem `dropFrozenInterfaceRow` solves; it is dropped the same way. */
  function ensureModelConditionsNode() {
    if (!boundaryNode) {
      boundaryNode = { label: 'Boundary conditions', icon: 'prescribed', count: 0,
                       eye: true, obj: 'group:conditions', children: [] };
    }
    if (!modelConditionsNode) {
      modelConditionsNode = { label: 'Model conditions', icon: 'settings', children: [] };
    }
    Object.keys(App.TREES || {}).forEach(function (mode) {
      var nodes = App.TREES[mode] || [];
      for (var i = nodes.length - 1; i >= 0; i -= 1) {
        if (nodes[i] && nodes[i] !== modelConditionsNode
            && nodes[i].label === 'Model conditions') nodes.splice(i, 1);
      }
    });
    return modelConditionsNode;
  }

  /* A condition's own row: what it is, in the words `boundary list` uses. */
  /* A support in a groundwater flow project says it is left out, as an inactive
     condition says it is inactive (`App.BoundaryConditions.unusedInFlow`). */
  function conditionChild(record) {
    var conditions = App.BoundaryConditions;
    var label = conditions ? conditions.label(record) : record.name;
    var note = record.active === false ? '  (inactive)'
      : conditions && conditions.unusedInFlow(record, App.PROJECT)
        ? '  (unused in flow)' : '';
    return { label: label + note,
             icon: record.kind === 'displacement' ? 'prescribed' : 'water',
             leaf: true, eye: true, obj: record.id };
  }

  function yesNo(get, set) {
    return {
      kind: 'select',
      options: function () { return [{ value: 'yes', text: 'Yes' }, { value: 'no', text: 'No' }]; },
      get: function () { return get() ? 'yes' : 'no'; },
      set: function (value) { return set(value === 'yes'); }
    };
  }

  function conditionNumberEditor(record, field, unit, check) {
    return {
      kind: 'number', decimals: 3, unit: unit,
      get: function () { return record[field]; },
      set: function (value) {
        if (!Number.isFinite(value)) return 'The value must be a number.';
        if (check) { var problem = check(value); if (problem) return problem; }
        record[field] = value;
        return null;
      }
    };
  }

  /* The Selection explorer's rows for one condition. Each editor changes the copy in
     App.BOUNDARY_CONDITIONS, and `App.commitSelectionEdit` sends it
     (App.BoundaryConditions.save); the server refuses what does not validate, and the
     stored project comes back. */
  function conditionProps(record) {
    var support = record.kind === 'displacement';
    var seepage = record.kind === 'seepage';
    var where = record.on === 'domain' ? 'Whole soil'
      : record.on === 'face' ? 'Face: ' + record.face
      : record.on === 'part' ? 'Part: ' + record.part
      : (record.on === 'line' ? 'Line: ' : 'Point: ')
        + (record.points || []).map(function (p) { return fixed(p[0]) + ' ' + fixed(p[1]); })
          .join(', ');
    var general = [
      ['Condition', support ? 'Support' : seepage ? 'Seepage face' : 'Water pressure', '',
       true],
      ['Where', where, '', true],
      ['Active', record.active !== false ? 'Yes' : 'No', '', false,
       yesNo(function () { return record.active !== false; },
             function (on) { record.active = on; return null; })],
      ['Edit', '', '', false, { kind: 'button', text: 'Edit condition…',
        run: function () { if (App.BoundaryConditions) App.BoundaryConditions.edit(record.id); } }],
      ['Delete', '', '', false, { kind: 'button', text: 'Delete condition',
        run: function () { if (App.BoundaryConditions) App.BoundaryConditions.remove(record.id); } }]
    ];
    var what = [];
    if (support) {
      ['x', 'y', 'z'].forEach(function (axis, i) {
        what.push(['Fixed ' + axis, record.fixed[i] ? 'Yes' : 'No', '', false,
                   yesNo(function () { return record.fixed[i]; }, function (on) {
                     var next = record.fixed.slice();
                     next[i] = on;
                     if (!next.some(Boolean)) return 'A support holds x, y or z; delete it to '
                       + 'hold nothing.';
                     record.fixed = next;
                     return null;
                   })]);
      });
    } else if (seepage) {
      what.push(['', 'Water may leave the soil here, in a groundwater flow calculation.',
                 '', true]);
    } else {
      var stress = App.Units.label('stress');
      what.push(['Type', record.fluid_pressure_type.replace(/_/g, ' '), '', true]);
      if (record.fluid_pressure_type === 'Uniform') {
        what.push(['Value', String(record.value), stress, false,
                   conditionNumberEditor(record, 'value', stress)]);
      }
      if (record.fluid_pressure_type === 'Hydrostatic') {
        what.push(['Reference level', fixed(record.reference_coordinate), 'm', false,
                   conditionNumberEditor(record, 'reference_coordinate', 'm')]);
      }
      if (record.fluid_pressure_type !== 'Uniform') {
        what.push(['Tension cut-off', String(record.pressure_tension_cut_off), stress, false,
                   conditionNumberEditor(record, 'pressure_tension_cut_off', stress,
                     function (value) {
                       return value < 0 ? 'The cut-off is 0 or more.' : null;
                     })]);
      }
      what.push(['Fixed', record.is_fixed ? 'Yes' : 'No', '', false,
                 yesNo(function () { return record.is_fixed; },
                       function (on) { record.is_fixed = on; return null; })]);
    }
    return {
      title: record.name, icon: support ? 'prescribed' : 'water',
      groups: { 'General': general, 'Prescribed': what }
    };
  }

  function gravityProps() {
    return {
      title: 'Gravity', icon: 'settings',
      groups: { 'General': [
        ['Gravity acts', App.PROJECT && App.PROJECT.gravity === false ? 'No' : 'Yes', '', false,
         yesNo(function () { return !(App.PROJECT && App.PROJECT.gravity === false); },
               function (on) { App.PENDING_GRAVITY = on; return null; })],
        ['', 'The self weight of every body, in every stage.', '', true]
      ] }
    };
  }

  function ensureNormalLoadNode() {
    if (!normalLoadNode) {
      normalLoadNode = { label: 'Normal loads', icon: 'load', count: 0,
                         eye: true, obj: 'group:normal_loads', children: [] };
    }
    return normalLoadNode;
  }

  /* ── One tree, in one order ──────────────────────────────────────────────
     The Model explorer is remounted from App.TREES[mode] on every mode change,
     and the live nodes were pushed into the Structures tree alone: Loads, Sheet
     piles and Anchors vanished the moment the user clicked Soil. Every mode is
     handed the same array now, sorted into one order -- what the model is made
     of, then what is built on it, then what acts on it, then what is computed
     from it. A label this list does not name keeps its place at the end rather
     than being dropped. */
  var TREE_ORDER = [
    'Attributes library', 'Soil', 'Geometry', 'Custom geometry',
    'Imported mesh', 'Structures', 'Sheet piles', 'Anchors', 'Interfaces',
    'Normal loads', 'Loads', 'Water levels', 'Flow conditions', 'Mesh',
    'Model conditions'
  ];

  function containsNode(nodes, node) {
    return (nodes || []).some(function (item) {
      return item === node || containsNode(item.children, node);
    });
  }

  /* The frozen Soil tree's "Boreholes" node (js/data.js): a layer has one top and
     one bottom, so there are no boreholes to list. */
  var TREE_DROPPED = ['boreholes'];

  /* The frozen rows of the same kind, by label: the mockup's water level of a
     borehole, in its Attributes library and its Flow conditions node. */
  var TREE_ROWS_DROPPED = ['BoreholeWaterLevel_1'];

  /* Takes those rows out of `nodes` and their children, in place: the frozen nodes
     are shared between the mode trees. A count that counted them is kept right. */
  function dropFrozenRows(nodes) {
    (nodes || []).forEach(function (node) {
      if (!node || !node.children) return;
      var kept = node.children.filter(function (child) {
        return TREE_ROWS_DROPPED.indexOf(child && child.label) < 0;
      });
      if (kept.length !== node.children.length) {
        if (node.count === node.children.length) node.count = kept.length;
        node.children = kept;
      }
      dropFrozenRows(kept);
    });
    return nodes;
  }

  /* The union of every mode's top-level nodes. Deduped by identity first, then by
     label: the Soil and Structures trees carry *different* "Attributes library"
     objects (js/data.js:673,683), and once one tree serves both modes the richer
     of the two is the one worth keeping. */
  function topLevelUnion() {
    var out = [];
    Object.keys(App.TREES || {}).forEach(function (mode) {
      (App.TREES[mode] || []).forEach(function (node) {
        if (!node || out.indexOf(node) >= 0 || TREE_DROPPED.indexOf(node.obj) >= 0) return;
        var twin = -1;
        out.forEach(function (seen, i) { if (seen.label === node.label) twin = i; });
        if (twin < 0) out.push(node);
        else if ((node.children || []).length > (out[twin].children || []).length) {
          out[twin] = node;
        }
      });
    });
    return dropFrozenRows(out);
  }

  function orderTree(nodes) {
    function rank(node) {
      var i = TREE_ORDER.indexOf(node.label);
      return i < 0 ? TREE_ORDER.length : i;
    }
    return nodes.map(function (node, i) { return { node: node, i: i }; })
      .sort(function (a, b) { return rank(a.node) - rank(b.node) || a.i - b.i; })
      .map(function (entry) { return entry.node; });
  }

  /* One array object shared by all five modes, so a node expanded in Soil mode is
     still expanded in Structures mode -- and so a count rebuilt here shows up
     wherever the user happens to be standing.

     A layered_soil project has none of the frozen demo structure behind it, so
     its tree is the live nodes alone; a full project keeps its frozen nodes and
     gains the live ones. Either way a live node that is already in the tree stays
     where it is rather than being added a second time.

     A live group the model has nothing in is left out: an empty "Sheet piles [0]"
     row reads as if the model had sheet piles. It comes back with its first member. */
  function syncTrees(layeredSoil, soil) {
    var top = layeredSoil ? (soil ? [soil] : []) : topLevelUnion();
    var groups = [customGeometryNode, importedMeshNode, sheetPileNode, anchorNode,
                  interfaceNode, normalLoadNode, loadConditionsNode];
    function empty(node) { return groups.indexOf(node) >= 0 && !(node.children || []).length; }
    top = top.filter(function (node) { return !empty(node); });
    groups.concat([waterLevelNode, modelConditionsNode]).forEach(function (node) {
      if (node && !empty(node) && !containsNode(top, node)) top.push(node);
    });
    var tree = orderTree(top);
    Object.keys(App.TREES || {}).forEach(function (mode) { App.TREES[mode] = tree; });
    return tree;
  }

  function customPartChild(part) {
    return { label: part.label, swatch: part.color, leaf: true, eye: true, obj: part.key };
  }

  /* Labelled the way a stack layer is: name, then the material it is made of. */
  function soilBodyChild(part) {
    return { label: part.label + '  ·  ' + App.matById(part.mat).name,
             swatch: part.color, leaf: true, eye: true, obj: part.key };
  }

  /* A part with a material is a soil body, so it gets the same editable Material
     row a stack layer has; one without stays plain geometry. */
  function partMaterialEditor(part) {
    return {
      kind: 'select',
      options: function () {
        return App.MATERIALS.map(function (m) { return { value: m.id, text: m.name }; });
      },
      get: function () { return part.mat; },
      set: function (v) {
        part.mat = v;
        part.color = App.matById(v).color;
        return null;
      }
    };
  }

  /* The extent of a polygon_extrude body, from the corners and the sweep. Derived
     rather than free: the corners are the definition, so these are read-only and
     the corners themselves are edited in the Create/Edit soil volume dialog. */
  function recipeExtent(recipe) {
    if (!recipe || recipe.kind !== 'polygon_extrude') return null;
    var ext = recipe.extrusion || [0, 0, 0];
    var lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    (recipe.vertices || []).forEach(function (v) {
      [0, 1, 2].forEach(function (a) {
        lo[a] = Math.min(lo[a], v[a], v[a] + ext[a]);
        hi[a] = Math.max(hi[a], v[a], v[a] + ext[a]);
      });
    });
    return { lo: lo, hi: hi, corners: (recipe.vertices || []).length };
  }

  function customPartProps(part) {
    if (!part.mat) {
      return {
        title: part.label, icon: 'cube',
        groups: { 'General': [['Source', part.source === 'import' ? 'Imported' : 'Drawn'],
                              ['Color', part.color]] }
      };
    }

    /* A soil body gets the same shape of panel as a stack layer: what it is made
       of, how big it is, and where it sits. */
    // Area in a 2D model, volume in 3D: see App.SoilVolumeDialog.measure.
    var size = App.SoilVolumeDialog && part.recipe
      ? App.SoilVolumeDialog.measure(App.PROJECT, part.recipe) : null;

    var general = [
      ['Material', App.matById(part.mat).name, '', false, partMaterialEditor(part)],
      [size ? size.label : 'Volume', size ? size.value.toFixed(1) : '—',
       size ? size.unit : 'm³', true],
      ['Source', part.source === 'import' ? 'Imported' : 'Drawn', '', true]
    ];

    var groups = { 'General': general };
    var extent = recipeExtent(part.recipe);
    if (extent) {
      /* Same rule as the stack layers in geometryRows(): a plane-strain body runs
         forever out of plane, so the extents along the hidden axis stop describing
         it and are dropped. The axes themselves stay read-only either way -- the
         corners are the definition, and they are edited in the dialog. */
      var hidden = outOfPlaneAxis(App.PROJECT);
      var rows = [
        ['x min', fixed(extent.lo[0]), 'm', true], ['x max', fixed(extent.hi[0]), 'm', true],
        ['y min', fixed(extent.lo[1]), 'm', true], ['y max', fixed(extent.hi[1]), 'm', true]
      ];
      if (hidden !== 'z') {
        rows.push(['z min', fixed(extent.lo[2]), 'm', true]);
        rows.push(['z max', fixed(extent.hi[2]), 'm', true]);
      }
      rows.push(['Corners', String(extent.corners), '', false, {
        kind: 'button', text: 'Edit coordinates…',
        run: function () { App.SoilVolumeDialog.open(part); }
      }]);
      groups['Geometry'] = rows;
    }
    return { title: part.label, icon: 'cube', groups: groups };
  }

  /* ── Derived: the selection-explorer property grid ───────────── */

  function fixed(v) { return v.toFixed(3); }

  /* The domain is one object for the whole project, so these rows edit the model
     rather than the selected layer. Mirrors the server's ordering validator
     (`Domain._ordered` in core/model/schemas.py) so an impossible extent is refused
     here. */
  var LIMITS = { x0: ['x1', 'below'], x1: ['x0', 'above'],
                 z0: ['z1', 'below'], z1: ['z0', 'above'] };

  function domainEditor(field) {
    return {
      kind: 'number', decimals: 3, unit: 'm',
      get: function () { return domain[field]; },
      set: function (v) {
        // NaN fails both comparisons below, so without this it was stored as the
        // domain's edge -- and reached the server as null.
        if (!Number.isFinite(v)) return field + ' must be a number.';
        var other = LIMITS[field][0], side = LIMITS[field][1];
        if (side === 'below' && v >= domain[other]) return field + ' must stay below ' + other + '.';
        if (side === 'above' && v <= domain[other]) return field + ' must stay above ' + other + '.';
        domain[field] = v;
        return null;
      }
    };
  }

  function pendingDomain() { return domain; }

  function pendingWater() { return water; }

  /* ── The water line ──────────────────────────────────────────────────────
     Two numbers. `y` is the level a new hydrostatic water pressure condition or
     normal load is given, which the record then keeps as its own (`core.model.drafts`);
     only a normal load saved without a level still reads it at export
     (`core.kratos.parameters._normal_load`). The level fixes no pressure by itself.
     `specific_weight` scales the water pressures and DENSITY_WATER in the materials
     file. Nothing in the GUI could change either until
     now -- the frozen `water` entry in js/data.js:631 lists three water levels from
     a different project altogether.

     Bounds mirror the server's rather than inventing any: `gt=0` on the weight, and
     the model's reach on the level (`extentOf`, the server's `Project.extent`): the
     layers and any drawn soil above them. See plan sec 7.2. */

  function waterLevelEditor() {
    return {
      kind: 'number', decimals: 3, unit: 'm',
      get: function () { return water.y; },
      set: function (value) {
        if (!Number.isFinite(value)) return 'The water level must be a number.';
        // A phreatic level outside the model describes nothing: above it every
        // element is submerged whatever the number, below it none is.
        var reach = extentOf(App.PROJECT);
        if (value <= reach.y_bottom || value >= reach.y_top) {
          return 'The water level must lie between ' + fixed(reach.y_bottom) +
                 ' and ' + fixed(reach.y_top) + ' m.';
        }
        water.y = value;
        return null;
      }
    };
  }

  /* What the water weighs: the project's own, or water's 10 kN/m3 in its system when
     the project leaves it to the server (WaterLevel.specific_weight is optional). */
  function waterWeight() {
    return water.specific_weight !== null && water.specific_weight !== undefined
      ? water.specific_weight : App.Units.fromSI(10000, 'specific weight');
  }

  function waterWeightEditor() {
    return {
      kind: 'number', decimals: App.PropertySets.decimals(waterWeight()),
      unit: App.Units.label('specific weight'),
      get: function () { return waterWeight(); },
      set: function (value) {
        if (!Number.isFinite(value)) return 'The specific weight must be a number.';
        // Mirrors WaterLevel's gt=0. Zero is not merely wrong, it divides by zero
        // where core.kratos.materials derives DENSITY_WATER from it.
        if (value <= 0) return 'The specific weight must be greater than zero.';
        water.specific_weight = value;
        return null;
      }
    };
  }

  function waterProps() {
    return {
      title: 'Water level (global)', icon: 'waterlevel',
      groups: {
        'General': [
          ['Type', 'Global phreatic level', '', true],
          ['Specific weight', String(waterWeight()), App.Units.label('specific weight'),
           false, waterWeightEditor()]
        ],
        'Geometry': [
          ['Level', fixed(water.y), 'm', false, waterLevelEditor()],
          // Said here because it is the question the panel invites next, and the
          // answer is not obvious from a level alone.
          ['Depth below ground', fixed(extentOf(App.PROJECT).y_top - water.y), 'm', true]
        ],
        'Conditions': [
          ['Distribution', 'Hydrostatic', '', true],
          // The honest state of sec 7.11: a per-stage pore-pressure type is not offered,
          // the reference deck never varies it, and inventing one would be guessing.
          ['Per-stage level', 'Not supported', '', true]
        ]
      }
    };
  }

  function loadUnit(load) {
    return App.Units.label({ point: 'force', line: 'line force' }[load.kind] || 'stress');
  }

  function loadNumberEditor(load, field, component) {
    return {
      kind: 'number', decimals: 3, unit: component === undefined ? 'm' : loadUnit(load),
      get: function () { return component === undefined ? load[field] : load.components[component]; },
      set: function (value) {
        if (!Number.isFinite(value)) return field + ' must be a finite number.';
        if (component !== undefined) { load.components[component] = value; return null; }
        var other = { x0: 'x1', x1: 'x0', z0: 'z1', z1: 'z0' }[field];
        if ((field === 'x0' || field === 'z0') && value >= load[other]) {
          return field + ' must stay below ' + other + '.';
        }
        if ((field === 'x1' || field === 'z1') && value <= load[other]) {
          return field + ' must stay above ' + other + '.';
        }
        load[field] = value;
        return null;
      }
    };
  }

  function beamNumberEditor(beam, index, axis) {
    return {
      kind: 'number', decimals: 3, unit: 'm',
      get: function () { return beam.points[index][axis]; },
      set: function (value) {
        if (!Number.isFinite(value)) return 'Every pile coordinate must be a number.';
        var was = beam.points[index][axis];
        beam.points[index][axis] = value;
        var problem = App.Beams ? App.Beams.validate(beam) : null;
        if (problem) { beam.points[index][axis] = was; return problem; }
        return null;
      }
    };
  }

  /* Editing the section edits the shared profile, which is the point of it being
     reusable: every pile using it moves together, in one validated write. */
  function sectionNumberEditor(section, field, unit, decimals) {
    return {
      kind: 'number', decimals: decimals === undefined ? 4 : decimals, unit: unit,
      get: function () { return section[field]; },
      set: function (value) {
        var was = section[field];
        section[field] = value;
        var problem = App.Beams ? App.Beams.validateSection(section) : null;
        if (problem) { section[field] = was; return problem; }
        return null;
      }
    };
  }

  /* A profile's or wall's Kratos variables, edited in place through the same check the
     sheet-pile dialog uses. */
  function sectionRows(kind, section, dimension) {
    return [['Law', section.constitutive_law || '', '', true]].concat(
      App.PropertySets.rows(kind, section, dimension, function (s) {
        return App.Beams ? App.Beams.validateSection(s) : null;
      }));
  }

  function beamLength(beam) {
    var total = 0;
    for (var i = 1; i < beam.points.length; i += 1) {
      var dx = beam.points[i][0] - beam.points[i - 1][0];
      var dz = beam.points[i][1] - beam.points[i - 1][1];
      total += Math.sqrt(dx * dx + dz * dz);
    }
    return total;
  }

  /* One editor per coordinate of a member's polyline, which is the 3D sibling of
     `beamNumberEditor` and validates through the same door. */
  function memberNumberEditor(member, index, axis) {
    return {
      kind: 'number', decimals: 3, unit: 'm',
      get: function () { return member.points[index][axis]; },
      set: function (value) {
        if (!Number.isFinite(value)) return 'Every member coordinate must be a number.';
        var was = member.points[index][axis];
        member.points[index][axis] = value;
        var problem = App.Beams ? App.Beams.validate(member) : null;
        if (problem) { member.points[index][axis] = was; return problem; }
        return null;
      }
    };
  }

  function panelPointEditor(panel, index, axis) {
    return {
      kind: 'number', decimals: 3, unit: 'm',
      get: function () { return panel.footprint[index][axis]; },
      set: function (value) {
        if (!Number.isFinite(value)) return 'Every wall coordinate must be a number.';
        var was = panel.footprint[index][axis];
        panel.footprint[index][axis] = value;
        var problem = App.Beams ? App.Beams.validate(panel) : null;
        if (problem) { panel.footprint[index][axis] = was; return problem; }
        return null;
      }
    };
  }

  function panelLevelEditor(panel, field) {
    return {
      kind: 'number', decimals: 3, unit: 'm',
      get: function () { return panel[field]; },
      set: function (value) {
        var was = panel[field];
        panel[field] = value;
        var problem = App.Beams ? App.Beams.validate(panel) : null;
        if (problem) { panel[field] = was; return problem; }
        return null;
      }
    };
  }

  /* The plan length of a wall, which with its height is what an engineer checks. */
  function panelLength(panel) {
    var total = 0;
    for (var i = 1; i < panel.footprint.length; i += 1) {
      var dx = panel.footprint[i][0] - panel.footprint[i - 1][0];
      var dy = panel.footprint[i][1] - panel.footprint[i - 1][1];
      total += Math.sqrt(dx * dx + dy * dy);
    }
    return total;
  }

  function memberLength(member) {
    var total = 0;
    for (var i = 1; i < member.points.length; i += 1) {
      var d = [0, 1, 2].map(function (axis) {
        return member.points[i][axis] - member.points[i - 1][axis];
      });
      total += Math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]);
    }
    return total;
  }

  /* A wall: a footprint in plan, two levels, and a thickness where the 2D pile has an
     area and an inertia per metre run. */
  function panelProps(panel) {
    var section = App.Beams ? App.Beams.sectionOf(panel) : {};
    var geometry = [];
    panel.footprint.forEach(function (point, index) {
      geometry.push(['x' + (index + 1), fixed(point[0]), 'm', false,
                     panelPointEditor(panel, index, 0)]);
      geometry.push(['z' + (index + 1), fixed(point[1]), 'm', false,
                     panelPointEditor(panel, index, 1)]);
    });
    geometry.push(['Top level', fixed(panel.y_top), 'm', false,
                   panelLevelEditor(panel, 'y_top')]);
    geometry.push(['Toe level', fixed(panel.y_toe), 'm', false,
                   panelLevelEditor(panel, 'y_toe')]);
    geometry.push(['Length', fixed(panelLength(panel)), 'm', true]);
    geometry.push(['Height', fixed(panel.y_top - panel.y_toe), 'm', true]);
    geometry.push(['Delete', '', '', false, { kind: 'button', text: 'Delete wall',
      run: function () { if (App.Beams) App.Beams.remove(panel.id); } }]);
    return {
      title: panel.name, icon: 'wall',
      groups: {
        'General': [
          ['Section', section.name || panel.section, '', true],
          ['Vertices', String(panel.footprint.length), '', true],
          ['Active', panel.active !== false, '', true],
          ['Edit', '', '', false, { kind: 'button', text: 'Edit wall…',
            run: function () { if (App.Beams) App.Beams.edit(panel.id); } }]
        ],
        'Section': sectionRows('panel', section, 3),
        'Geometry': geometry
      }
    };
  }

  /* A member: the sheet pile's own profile library, standing in space. */
  function memberProps(member) {
    var section = App.Beams ? App.Beams.sectionOf(member) : {};
    var geometry = [];
    member.points.forEach(function (point, index) {
      ['x', 'y', 'z'].forEach(function (axis, a) {
        geometry.push([axis + (index + 1), fixed(point[a]), 'm', false,
                       memberNumberEditor(member, index, a)]);
      });
    });
    geometry.push(['Length', fixed(memberLength(member)), 'm', true]);
    geometry.push(['Delete', '', '', false, { kind: 'button', text: 'Delete member',
      run: function () { if (App.Beams) App.Beams.remove(member.id); } }]);
    return {
      title: member.name, icon: 'beam',
      groups: {
        'General': [
          ['Section', section.name || member.section, '', true],
          ['Vertices', String(member.points.length), '', true],
          ['Active', member.active !== false, '', true],
          ['Edit', '', '', false, { kind: 'button', text: 'Edit member…',
            run: function () { if (App.Beams) App.Beams.edit(member.id); } }]
        ],
        'Section': sectionRows('beam', section, 3),
        'Geometry': geometry
      }
    };
  }

  function beamProps(beam) {
    if (beam.kind === 'panel') return panelProps(beam);
    if (beam.kind === 'member') return memberProps(beam);
    var section = App.Beams ? App.Beams.sectionOf(beam) : {};
    var geometry = [];
    beam.points.forEach(function (point, index) {
      geometry.push(['x' + (index + 1), fixed(point[0]), 'm', false,
                     beamNumberEditor(beam, index, 0)]);
      geometry.push(['y' + (index + 1), fixed(point[1]), 'm', false,
                     beamNumberEditor(beam, index, 1)]);
    });
    geometry.push(['Length', fixed(beamLength(beam)), 'm', true]);
    geometry.push(['Delete', '', '', false, { kind: 'button', text: 'Delete sheet pile',
      run: function () { if (App.Beams) App.Beams.remove(beam.id); } }]);
    return {
      title: beam.name, icon: 'wall',
      groups: {
        'General': [
          ['Section', section.name || beam.section, '', true],
          ['Vertices', String(beam.points.length), '', true],
          ['Active', beam.active !== false, '', true],
          ['Edit', '', '', false, { kind: 'button', text: 'Edit sheet pile…',
            run: function () { if (App.Beams) App.Beams.edit(beam.id); } }]
        ],
        'Section': sectionRows('beam', section, 2).concat([
          ['Spacing', String(section.spacing), 'm', false,
           sectionNumberEditor(section, 'spacing', 'm', 3)]
        ]),
        'Geometry': geometry
      }
    };
  }

  function anchorEndEditor(anchor, end, axis) {
    return {
      kind: 'number', decimals: 3, unit: 'm',
      get: function () { return anchor[end][axis]; },
      set: function (value) {
        if (!Number.isFinite(value)) return 'Every anchor coordinate must be a number.';
        var was = anchor[end][axis];
        anchor[end][axis] = value;
        var problem = App.Anchors ? App.Anchors.validate(anchor, App.PROJECT) : null;
        if (problem) { anchor[end][axis] = was; return problem; }
        return null;
      }
    };
  }

  function anchorNumberEditor(anchor, field, unit, decimals) {
    return {
      kind: 'number', decimals: decimals === undefined ? 1 : decimals, unit: unit,
      get: function () { return anchor[field]; },
      set: function (value) {
        var was = anchor[field];
        anchor[field] = value;
        var problem = App.Anchors ? App.Anchors.validate(anchor, App.PROJECT) : null;
        if (problem) { anchor[field] = was; return problem; }
        return null;
      }
    };
  }

  function tendonNumberEditor(section, field, unit, decimals) {
    return {
      kind: 'number', decimals: decimals === undefined ? 4 : decimals, unit: unit,
      get: function () { return section[field]; },
      set: function (value) {
        var was = section[field];
        section[field] = value;
        var problem = App.Anchors ? App.Anchors.validateSection(section) : null;
        if (problem) { section[field] = was; return problem; }
        return null;
      }
    };
  }

  function tendonRows(tendon, dimension) {
    return [['Law', tendon.constitutive_law || '', '', true]].concat(
      App.PropertySets.rows('anchor', tendon, dimension, function (s) {
        return App.Anchors ? App.Anchors.validateSection(s) : null;
      }));
  }

  /* The 3D anchor: both ends in space, and no out-of-plane spacing to smear over --
     it is the discrete member the user drew, where it was drawn. */
  function spaceAnchorProps(anchor) {
    var tendon = App.Anchors ? App.Anchors.sectionOf(anchor) : {};
    var geometry = [];
    [['Head', 'head'], ['Tail', 'tail']].forEach(function (end) {
      ['x', 'y', 'z'].forEach(function (axis, a) {
        geometry.push([end[0] + ' ' + axis, fixed(anchor[end[1]][a]), 'm', false,
                       anchorEndEditor(anchor, end[1], a)]);
      });
    });
    geometry.push(['Length', fixed(App.Anchors ? App.Anchors.length(anchor) : 0),
                   'm', true]);
    geometry.push(['Inclination', fixed(App.Anchors ? App.Anchors.inclination(anchor) : 0),
                   '°', true]);
    geometry.push(['Delete', '', '', false, { kind: 'button', text: 'Delete anchor',
      run: function () { if (App.Anchors) App.Anchors.remove(anchor.id); } }]);
    return {
      title: anchor.name, icon: 'anchor',
      groups: {
        'General': [
          ['Tendon', tendon.name || anchor.section, '', true],
          ['TRUSS_PRESTRESS_PK2', String(anchor.prestress), App.Units.label('stress'), false,
           anchorNumberEditor(anchor, 'prestress', App.Units.label('stress'),
                              App.PropertySets.decimals(anchor.prestress))],
          ['Active', anchor.active !== false, '', true]
        ],
        'Tendon': tendonRows(tendon, 3),
        'Geometry': geometry
      }
    };
  }

  function anchorProps(anchor) {
    if (anchor.kind === 'anchor3d') return spaceAnchorProps(anchor);
    var tendon = App.Anchors ? App.Anchors.sectionOf(anchor) : {};
    var geometry = [
      ['Head x', fixed(anchor.head[0]), 'm', false, anchorEndEditor(anchor, 'head', 0)],
      ['Head y', fixed(anchor.head[1]), 'm', false, anchorEndEditor(anchor, 'head', 1)],
      ['Tail x', fixed(anchor.tail[0]), 'm', false, anchorEndEditor(anchor, 'tail', 0)],
      ['Tail y', fixed(anchor.tail[1]), 'm', false, anchorEndEditor(anchor, 'tail', 1)],
      ['Length', fixed(App.Anchors ? App.Anchors.length(anchor) : 0), 'm', true],
      ['Inclination', fixed(App.Anchors ? App.Anchors.inclination(anchor) : 0), '°', true],
      ['Delete', '', '', false, { kind: 'button', text: 'Delete anchor',
        run: function () { if (App.Anchors) App.Anchors.remove(anchor.id); } }]
    ];
    return {
      title: anchor.name, icon: 'anchor',
      groups: {
        'General': [
          ['Tendon', tendon.name || anchor.section, '', true],
          ['TRUSS_PRESTRESS_PK2', String(anchor.prestress), App.Units.label('stress'), false,
           anchorNumberEditor(anchor, 'prestress', App.Units.label('stress'),
                              App.PropertySets.decimals(anchor.prestress))],
          ['Active', anchor.active !== false, '', true]
        ],
        'Tendon': tendonRows(tendon, 2).concat([
          ['Spacing', String(tendon.spacing), 'm', false,
           tendonNumberEditor(tendon, 'spacing', 'm', 3)]
        ]),
        'Geometry': geometry
      }
    };
  }

  /* ── Interfaces ──────────────────────────────────────────────────────────
     The contact itself carries almost nothing: which line it runs along, which
     side of it is unglued, and which reusable property set it reads. The numbers
     live on that set, because r_inter reduces a particular soil's strength and
     several interfaces normally share one contact. */

  /* The faces as the screen shows them, in the words of the line: left and right on a
     steep one, below and above on a flat one (core/model/polylines.py). */
  var INTERFACE_SIDES = { both: 'Both sides', left: 'Left (toward -x)',
                          right: 'Right (toward +x)', below: 'Below', above: 'Above' };

  function interfaceSideEditor(record) {
    return {
      kind: 'select',
      options: function () {
        var words = App.Interfaces
          ? App.Interfaces.faces(App.Interfaces.pathOf(record, App.PROJECT))
          : ['left', 'right'];
        return (record.structure ? ['both'] : []).concat(words).map(function (side) {
          return { value: side, text: INTERFACE_SIDES[side] };
        });
      },
      get: function () { return record.side; },
      set: function (value) {
        var was = record.side;
        record.side = value;
        var problem = App.Interfaces
          ? App.Interfaces.validate(record, App.PROJECT) : null;
        if (problem) { record.side = was; return problem; }
        return null;
      }
    };
  }

  /* Along: a live sheet pile, or the interface's own coordinates, as in the window
     (App.Interfaces.open). A new pile is held whole; own coordinates start down the
     middle of the section. */
  function interfaceAlongEditor(record) {
    return {
      kind: 'select',
      options: function () {
        var piles = App.Interfaces ? App.Interfaces.livePiles(App.PROJECT) : [];
        return [{ value: '', text: 'Own coordinates' }].concat(piles.map(function (beam) {
          return { value: beam.id, text: beam.name };
        }));
      },
      get: function () { return record.structure || ''; },
      set: function (value) {
        var was = { structure: record.structure, points: record.points,
                    stretch: record.stretch, side: record.side };
        record.stretch = null;
        if (value) {
          record.structure = value;
          record.points = null;
        } else {
          record.structure = null;
          record.points = App.Interfaces.middleLine(App.PROJECT);
          if (record.side === 'both') record.side = 'left';
        }
        var problem = App.Interfaces
          ? App.Interfaces.validate(record, App.PROJECT) : null;
        if (problem) { Object.assign(record, was); return problem; }
        return null;
      }
    };
  }

  /* From and To of an interface on a pile: its stretch, or the pile's two ends. */
  function interfaceEnds(record) {
    var pile = App.Interfaces ? App.Interfaces.pileOf(record, App.PROJECT) : null;
    if (record.stretch) return record.stretch;
    return pile ? [pile.points[0], pile.points[pile.points.length - 1]] : [[0, 0], [0, 0]];
  }

  function interfaceStretchEditor(record, end, axis) {
    return {
      kind: 'number', decimals: 3, unit: 'm',
      get: function () { return interfaceEnds(record)[end][axis]; },
      set: function (value) {
        if (!Number.isFinite(value)) return 'Every interface coordinate must be a number.';
        var points = JSON.parse(JSON.stringify(interfaceEnds(record)));
        points[end][axis] = value;
        var was = record.stretch;
        try {
          record.stretch = App.Interfaces.stretchOn(
            App.Interfaces.pileOf(record, App.PROJECT), points[0], points[1]);
        } catch (error) {
          return error.message;
        }
        var problem = App.Interfaces.validate(record, App.PROJECT);
        if (problem) { record.stretch = was; return problem; }
        return null;
      }
    };
  }

  function interfacePointEditor(record, index, axis) {
    return {
      kind: 'number', decimals: 3, unit: 'm',
      get: function () { return record.points[index][axis]; },
      set: function (value) {
        if (!Number.isFinite(value)) return 'Every interface coordinate must be a number.';
        var was = record.points[index][axis];
        record.points[index][axis] = value;
        var problem = App.Interfaces
          ? App.Interfaces.validate(record, App.PROJECT) : null;
        if (problem) { record.points[index][axis] = was; return problem; }
        return null;
      }
    };
  }

  function contactNumberEditor(section, field, unit, decimals) {
    return {
      kind: 'number', decimals: decimals === undefined ? 3 : decimals, unit: unit,
      get: function () { return section[field]; },
      set: function (value) {
        var was = section[field];
        section[field] = value;
        var problem = App.Interfaces ? App.Interfaces.validateSection(section) : null;
        if (problem) { section[field] = was; return problem; }
        return null;
      }
    };
  }

  /* `null` is a choice, not a gap: a contact with no material of its own takes the
     stiffness of whichever soil each stretch runs against (core/model/schemas.py,
     InterfaceSection). A <select> carries strings, so it is offered as ''. */
  var ADJACENT_SOIL = { value: '', text: 'From the soil it runs against' };

  function contactMaterialEditor(section) {
    return {
      kind: 'select',
      options: function () {
        return [ADJACENT_SOIL].concat((App.MATERIALS || []).map(function (m) {
          return { value: m.id, text: m.name };
        }));
      },
      get: function () { return section.material || ''; },
      set: function (value) {
        var was = section.material;
        section.material = value || null;
        var problem = App.Interfaces ? App.Interfaces.validateSection(section) : null;
        if (problem) { section.material = was; return problem; }
        return null;
      }
    };
  }

  function contactPermeabilityEditor(section) {
    return {
      kind: 'select',
      options: function () {
        return ['Neutral', 'Drain', 'Impermeable'].map(function (name) {
          return { value: name, text: name };
        });
      },
      get: function () { return section.permeability; },
      set: function (value) { section.permeability = value; return null; }
    };
  }

  function interfaceProps(record) {
    var contact = App.Interfaces ? App.Interfaces.sectionOf(record) : {};
    var follows = !!record.structure;
    var pile = follows
      ? ((App.BEAMS || []).filter(function (b) { return b.id === record.structure; })[0])
      : null;
    var geometry = [];
    if (follows) {
      var ends = interfaceEnds(record);
      [['From', 0], ['To', 1]].forEach(function (end) {
        geometry.push([end[0] + ' x', fixed(ends[end[1]][0]), 'm', false,
                       interfaceStretchEditor(record, end[1], 0)]);
        geometry.push([end[0] + ' y', fixed(ends[end[1]][1]), 'm', false,
                       interfaceStretchEditor(record, end[1], 1)]);
      });
    } else {
      (record.points || []).forEach(function (point, index) {
        geometry.push(['x' + (index + 1), fixed(point[0]), 'm', false,
                       interfacePointEditor(record, index, 0)]);
        geometry.push(['y' + (index + 1), fixed(point[1]), 'm', false,
                       interfacePointEditor(record, index, 1)]);
      });
    }
    geometry.push(['Length',
                   fixed(App.Interfaces ? App.Interfaces.length(record) : 0), 'm', true]);
    geometry.push(['Edit', '', '', false, { kind: 'button', text: 'Edit interface…',
      run: function () { if (App.Interfaces) App.Interfaces.edit(record.id); } }]);
    geometry.push(['Delete', '', '', false, { kind: 'button', text: 'Delete interface',
      run: function () { if (App.Interfaces) App.Interfaces.remove(record.id); } }]);

    function check(s) { return App.Interfaces ? App.Interfaces.validateSection(s) : null; }
    // The two stiffnesses first, typed in place: what a user comes here to set. Left
    // out they read "derived" -- the soil's own shear modulus over the virtual thickness
    // supplies them at export -- and the button puts them back to that.
    var stiffnesses = ['INTERFACE_NORMAL_STIFFNESS', 'INTERFACE_SHEAR_STIFFNESS'];
    var properties = stiffnesses.map(function (name) {
      return App.PropertySets.typedRow('interface', contact, name, check);
    });
    var typed = stiffnesses.filter(function (name) {
      return (contact.variables || {})[name] !== undefined;
    });
    if (typed.length) {
      properties.push(['Stiffness', '', '', false, { kind: 'button',
        text: 'Derive from the soil', run: function () {
          typed.forEach(function (name) {
            App.PropertySets.assign(contact, name, undefined, check);
          });
          // The same write a typed value makes: the whole section library with it.
          if (App.commitSelectionEdit) App.commitSelectionEdit(record.id);
        } }]);
    }
    properties = properties.concat([
      ['Soil', (App.matById && contact.material
                && (App.matById(contact.material) || {}).name) || contact.material
               || ADJACENT_SOIL.text,
       '', false, contactMaterialEditor(contact)],
      // Only a Coulomb law reads the strength R_inter reduces; the default elastic one
      // reads the two stiffnesses alone (`kratos-cli section add --help` says the same).
      contact.r_inter === null || contact.r_inter === undefined
        ? ['R_inter (Coulomb law only)', 'each soil’s own', '', true]
        : ['R_inter (Coulomb law only)', String(contact.r_inter), '', false,
           contactNumberEditor(contact, 'r_inter', '', 2)],
      ['Virtual thickness', String(contact.virtual_thickness), 'm', false,
       contactNumberEditor(contact, 'virtual_thickness', 'm', 4)],
      ['Permeability', contact.permeability || 'Neutral', '', false,
       contactPermeabilityEditor(contact)]
    ]);
    // The rest of Kratos' own variables. One the contact leaves out reads "derived"
    // rather than zero: the soil's own strength supplies it at export.
    properties = properties.concat(App.PropertySets.rows('interface', contact,
      App.PROJECT && App.PROJECT.dimension, check).filter(function (row) {
        return stiffnesses.indexOf(row[0]) < 0;
      }));

    return {
      title: record.name, icon: 'interface',
      groups: {
        'General': [
          ['Contact', contact.name || record.section, '', true],
          ['Along', follows ? ((pile && pile.name) || record.structure) : 'Own coordinates',
           '', false, interfaceAlongEditor(record)],
          ['Side', INTERFACE_SIDES[record.side] || record.side, '', false,
           interfaceSideEditor(record)],
          ['Active', record.active !== false, '', true]
        ],
        'Contact': properties,
        'Geometry': geometry
      }
    };
  }

  /* ── Normal loads ────────────────────────────────────────────────────────
     A pressure normal to a free polyline, sized one of two ways: tracking the
     project's own water level ("Hydrostatic", the usual case for an exposed
     excavation face) or a fixed value along the whole line ("Uniform"). See
     core/model/schemas.py's NormalLoad and core/kratos/parameters.py's
     ApplyNormalLoadTableProcess. */

  function normalLoadPointEditor(record, index, axis) {
    return {
      kind: 'number', decimals: 3, unit: 'm',
      get: function () { return record.points[index][axis]; },
      set: function (value) {
        if (!Number.isFinite(value)) return 'Every coordinate must be a number.';
        var was = record.points[index][axis];
        record.points[index][axis] = value;
        var problem = App.NormalLoads
          ? App.NormalLoads.validate(record, App.PROJECT) : null;
        if (problem) { record.points[index][axis] = was; return problem; }
        return null;
      }
    };
  }

  function normalLoadFluidPressureTypeEditor(record) {
    return {
      kind: 'select',
      options: function () {
        return [{ value: 'Hydrostatic', text: 'Hydrostatic (tracks the water level)' },
                { value: 'Uniform', text: 'Uniform pressure' }];
      },
      get: function () { return record.fluid_pressure_type; },
      set: function (value) { record.fluid_pressure_type = value; return null; }
    };
  }

  function normalLoadPressureEditor(record) {
    return {
      kind: 'number', decimals: 1, unit: App.Units.label('stress'),
      get: function () { return record.pressure; },
      set: function (value) {
        if (!Number.isFinite(value)) return 'The pressure must be a number.';
        record.pressure = value;
        return null;
      }
    };
  }

  function normalLoadProps(record) {
    var hydrostatic = record.fluid_pressure_type === 'Hydrostatic';
    var geometry = [];
    (record.points || []).forEach(function (point, index) {
      geometry.push(['x' + (index + 1), fixed(point[0]), 'm', false,
                     normalLoadPointEditor(record, index, 0)]);
      geometry.push(['y' + (index + 1), fixed(point[1]), 'm', false,
                     normalLoadPointEditor(record, index, 1)]);
    });
    geometry.push(['Length',
                   fixed(App.NormalLoads ? App.NormalLoads.length(record) : 0), 'm', true]);
    geometry.push(['Delete', '', '', false, { kind: 'button', text: 'Delete normal load',
      run: function () { if (App.NormalLoads) App.NormalLoads.remove(record.id); } }]);

    /* The magnitude is always here and always editable, whichever mode the load is
       in: it is the field people come to this panel to change, and one that appears
       and vanishes with the type reads as a missing feature. It is written into the
       deck either way (see core.kratos.parameters' `_normal_load`). */
    var sizing = [
      ['Type', hydrostatic ? 'Hydrostatic' : 'Uniform', '', false,
       normalLoadFluidPressureTypeEditor(record)],
      ['Pressure', String(record.pressure), App.Units.label('stress'), false,
       normalLoadPressureEditor(record)]
    ];
    if (hydrostatic) {
      // Its own level, or -- a load saved before it had one -- the water level it
      // reads at export, which an edit here then makes its own.
      var water = App.PROJECT && App.PROJECT.water;
      var own = record.reference_coordinate !== null
        && record.reference_coordinate !== undefined;
      sizing.push([own ? 'Reference level' : 'Reference level (the water level)',
                   fixed(own ? record.reference_coordinate : (water ? water.y : 0)), 'm',
                   false, {
                     kind: 'number', decimals: 3, unit: 'm',
                     get: function () {
                       return own ? record.reference_coordinate : (water ? water.y : 0);
                     },
                     set: function (value) {
                       if (!Number.isFinite(value)) return 'The level must be a number.';
                       record.reference_coordinate = value;
                       return null;
                     }
                   }]);
    }

    return {
      title: record.name, icon: 'load',
      groups: {
        'General': [
          ['Active', record.active !== false, '', true],
          ['Edit', '', '', false, { kind: 'button', text: 'Edit normal load…',
            run: function () { if (App.NormalLoads) App.NormalLoads.edit(record.id); } }]
        ],
        'Sizing': sizing,
        'Geometry': geometry
      }
    };
  }

  function loadProps(load) {
    var point = load.kind === 'point';
    var line = load.kind === 'line';
    var unit = loadUnit(load);
    var geometry = point ? [
      ['x', fixed(load.x), 'm', false, loadNumberEditor(load, 'x')],
      ['y', fixed(load.y), 'm', false, loadNumberEditor(load, 'y')]
    ] : line ? [
      ['x min', fixed(load.x0), 'm', false, loadNumberEditor(load, 'x0')],
      ['x max', fixed(load.x1), 'm', false, loadNumberEditor(load, 'x1')],
      ['y', fixed(load.y), 'm', false, loadNumberEditor(load, 'y')],
      ['Length', fixed(load.x1 - load.x0), 'm', true]
    ] : [
      ['x min', fixed(load.x0), 'm', false, loadNumberEditor(load, 'x0')],
      ['x max', fixed(load.x1), 'm', false, loadNumberEditor(load, 'x1')],
      /* x/z place the pad in plan, y says which face it loads; it sits between them so
         the grid reads x, y, z. The server leaves y null to mean "the top of the
         model" (SurfaceLoad.y), resolved against ground_y at build time -- so say
         that rather than formatting the missing level as 0.000, which would read as
         a pad at datum. */
      Number.isFinite(load.y)
        ? ['y', fixed(load.y), 'm', false, loadNumberEditor(load, 'y')]
        : ['y', 'Top of model', '', true],
      ['z min', fixed(load.z0), 'm', false, loadNumberEditor(load, 'z0')],
      ['z max', fixed(load.z1), 'm', false, loadNumberEditor(load, 'z1')],
      ['Area', fixed((load.x1 - load.x0) * (load.z1 - load.z0)), 'm²', true]
    ];
    geometry.push(['Delete', '', '', false, { kind: 'button', text: 'Delete load',
      run: function () { if (App.Loads) App.Loads.remove(load.id); } }]);
    return {
      title: load.name, icon: 'load',
      groups: {
        'General': [
          ['Distribution', load.distribution, '', true],
          ['Active', load.active !== false, '', true],
          ['Edit', '', '', false, { kind: 'button', text: 'Edit load…',
            run: function () { if (App.Loads) App.Loads.edit(load.id); } }]
        ],
        'Components': (point || line) ? [
          ['qx', fixed(load.components[0]), unit, false, loadNumberEditor(load, 'qx', 0)],
          ['qy', fixed(load.components[1]), unit, false, loadNumberEditor(load, 'qy', 1)]
        ] : [
          ['qx', fixed(load.components[0]), unit, false, loadNumberEditor(load, 'qx', 0)],
          ['qy', fixed(load.components[1]), unit, false, loadNumberEditor(load, 'qy', 1)],
          ['qz', fixed(load.components[2]), unit, false, loadNumberEditor(load, 'qz', 2)]
        ],
        'Geometry': geometry
      }
    };
  }

  /* Which axis a plane-strain model has no extent along. Always z: a 2D model is
     the x-y plane, and the body runs forever out of plane, so its z extents stop
     describing the model. x and y still bound the section itself and stay. */
  function outOfPlaneAxis(project) {
    if (!project || project.dimension !== 2) return null;
    return 'z';
  }

  /* Where the cut sits along that axis. Mirrors App.Viewport.sectionOffset: an
     explicit offset, else the middle of the domain's out-of-plane depth. */
  function sectionAt(project) {
    if (project && typeof project.section_offset === 'number') return project.section_offset;
    return (domain.z0 + domain.z1) / 2;
  }

  function layerProps(layer, i) {
    var m = App.matById(layer.mat);

    return {
      title: 'SoilLayer_' + (i + 1) + ' (' + layer.name + ')', icon: 'cube',
      groups: {
        'General':  [['Material', m.name, '', false, App.LayerEditors.material(layer)],
                     // Filled in from the geometry response, which measures it.
                     ['Volume', '—', 'm³', true],
                     ['Active', true]],
        'Geometry': geometryRows(layer),
        'Mesh':     [['Coarseness factor', '1.000'], ['Element count', '—', '', true]]
      }
    };
  }

  /* x/y are the project domain -- the model's plan extents, shared by every layer --
     so editing one edits the whole model (see domainEditor). In 2D the pair normal
     to the section is dropped and the cut's position shown in its place: read-only,
     because moving the section is a mode switch (PATCH /api/project/dimension), not
     a property edit. z stays either way: for the elevation sections it bounds the
     cut, and it is the layer's own stratigraphy rather than the domain. */
  /* NaN fails every bound check of a level edit (js/soil-layers-dialog.js
     `setTop`, `setBottom`), so it would be written into the stack as a level. */
  function finiteOnly(editor) {
    var set = editor.set;
    editor.set = function (v) { return Number.isFinite(v) ? set(v) : 'The level must be a number.'; };
    return editor;
  }

  function geometryRows(layer) {
    var hidden = outOfPlaneAxis(App.PROJECT);
    var rows = [];
    if (hidden !== 'x') {
      rows.push(['x min', fixed(domain.x0), 'm', false, domainEditor('x0')]);
      rows.push(['x max', fixed(domain.x1), 'm', false, domainEditor('x1')]);
    }
    rows.push(['y min', fixed(layer.bottom), 'm', false,
               finiteOnly(App.SoilLayersDialog.levelEditor(layer, 'bottom'))]);
    rows.push(['y max', fixed(layer.top), 'm', false,
               finiteOnly(App.SoilLayersDialog.levelEditor(layer, 'top'))]);
    if (hidden !== 'z') {
      rows.push(['z min', fixed(domain.z0), 'm', false, domainEditor('z0')]);
      rows.push(['z max', fixed(domain.z1), 'm', false, domainEditor('z1')]);
    }
    if (hidden) {
      rows.push(['Section at ' + hidden, fixed(sectionAt(App.PROJECT)), 'm', true]);
    }
    return rows;
  }

  function rebuildDerived() {
    var layers = App.LAYERS || [];
    var loads = App.LOADS || [];
    var customParts = (App.PROJECT && App.PROJECT.custom_parts) || [];

    /* A custom part with a material is soil, so it sits under Soil beside the
       layers of the stack. Without one it is plain geometry and stays under
       Custom geometry. */
    var soilBodies = customParts.filter(function (p) { return !!p.mat; });
    var plainParts = customParts.filter(function (p) { return !p.mat; });

    var sharedSoilNodes = soilNodes();
    sharedSoilNodes.forEach(function (node) {
      // Flattened: a staged layer contributes one row per body, so the count is the
      // number of rows the user can actually see and toggle, not the number of layers.
      var layerRows = layers.reduce(function (rows, layer) {
        return rows.concat(layerChildren(layer));
      }, []);
      node.count = layerRows.length + soilBodies.length;
      node.children = layerRows.concat(soilBodies.map(soilBodyChild));
    });

    customGeometryNode.count = plainParts.length;
    customGeometryNode.children = plainParts.map(customPartChild);

    App.OBJECT_PROPS = App.OBJECT_PROPS || {};
    Object.keys(App.OBJECT_PROPS).forEach(function (key) {
      if (key.indexOf('soil_') === 0) delete App.OBJECT_PROPS[key];
    });
    // Replaces the frozen mockup's three water rows wholesale, the same way the
    // soil rows are replaced above: they describe a project nobody has open.
    // A model without a water level has no row and no property grid for one.
    if (water) {
      App.OBJECT_PROPS.water = waterProps();
      ensureWaterLevelNode();
    } else {
      delete App.OBJECT_PROPS.water;
      dropWaterLevelNode();
    }
    layers.forEach(function (layer, i) {
      // Every body of the layer, not just the layer's own key: clicking a lift in the
      // viewport or the tree selects `soil_<id>__lift2`, and a Selection explorer with
      // no entry for it shows nothing at all. A lift is the layer it was dug out of, so
      // it shows the layer's properties.
      layerBodies(layer).forEach(function (key) {
        App.OBJECT_PROPS[key] = layerProps(layer, i);
      });
    });

    var currentPartKeys = {};
    customParts.forEach(function (part) {
      App.OBJECT_PROPS[part.key] = customPartProps(part);
      currentPartKeys[part.key] = true;
    });
    Object.keys(App.OBJECT_PROPS).forEach(function (key) {
      if (/^(drawn|imported)_/.test(key) && !currentPartKeys[key]) delete App.OBJECT_PROPS[key];
    });

    var loadNode = findLoadConditionsNode();
    loadNode.count = loads.length;
    loadNode.children = loads.map(function (load) {
      return { label: load.name, icon: 'load', leaf: true, eye: true, obj: load.id };
    });
    previousLoadKeys.forEach(function (key) { delete App.OBJECT_PROPS[key]; });
    loads.forEach(function (load) { App.OBJECT_PROPS[load.id] = loadProps(load); });
    previousLoadKeys = loads.map(function (load) { return load.id; });

    var beams = App.BEAMS || [];
    var pileNode = ensureSheetPileNode();
    pileNode.count = beams.length;
    pileNode.children = beams.map(function (beam) {
      return { label: beam.name, icon: 'wall', leaf: true, eye: true, obj: beam.id };
    });
    previousBeamKeys.forEach(function (key) { delete App.OBJECT_PROPS[key]; });
    beams.forEach(function (beam) { App.OBJECT_PROPS[beam.id] = beamProps(beam); });
    previousBeamKeys = beams.map(function (beam) { return beam.id; });

    var anchors = App.ANCHORS || [];
    var tieNode = ensureAnchorNode();
    tieNode.count = anchors.length;
    tieNode.children = anchors.map(function (anchor) {
      return { label: anchor.name, icon: 'anchor', leaf: true, eye: true,
               obj: anchor.id };
    });
    previousAnchorKeys.forEach(function (key) { delete App.OBJECT_PROPS[key]; });
    anchors.forEach(function (a) { App.OBJECT_PROPS[a.id] = anchorProps(a); });
    previousAnchorKeys = anchors.map(function (anchor) { return anchor.id; });

    var contacts = App.INTERFACES || [];
    var contactNode = ensureInterfaceNode();
    contactNode.count = contacts.length;
    contactNode.children = contacts.map(function (record) {
      return { label: record.name, icon: 'interface', leaf: true, eye: true,
               obj: record.id };
    });
    previousInterfaceKeys.forEach(function (key) { delete App.OBJECT_PROPS[key]; });
    contacts.forEach(function (record) {
      App.OBJECT_PROPS[record.id] = interfaceProps(record);
    });
    previousInterfaceKeys = contacts.map(function (record) { return record.id; });

    var normalLoads = App.NORMAL_LOADS || [];
    var normalLoadTreeNode = ensureNormalLoadNode();
    normalLoadTreeNode.count = normalLoads.length;
    normalLoadTreeNode.children = normalLoads.map(function (record) {
      return { label: record.name, icon: 'load', leaf: true, eye: true,
               obj: record.id };
    });
    previousNormalLoadKeys.forEach(function (key) { delete App.OBJECT_PROPS[key]; });
    normalLoads.forEach(function (record) {
      App.OBJECT_PROPS[record.id] = normalLoadProps(record);
    });
    previousNormalLoadKeys = normalLoads.map(function (record) { return record.id; });

    var conditions = App.BOUNDARY_CONDITIONS || [];
    var conditionsNode = ensureModelConditionsNode();
    // A 2D model's front and back supports are kept for the solid model, not listed.
    var listed = conditions.filter(function (record) {
      return !(App.BoundaryConditions && App.BoundaryConditions.heldBySection(record, App.PROJECT));
    });
    boundaryNode.count = listed.length;
    boundaryNode.children = listed.map(conditionChild);
    var gravityOn = !(App.PROJECT && App.PROJECT.gravity === false);
    // No "Boundary conditions [0]" row for a model without any; gravity always acts or not.
    conditionsNode.children = (listed.length ? [boundaryNode] : []).concat([{
      label: 'Gravity  ·  ' + (gravityOn ? 'on' : 'off'), icon: 'settings', leaf: true,
      obj: 'gravity' }]);
    previousConditionKeys.forEach(function (key) { delete App.OBJECT_PROPS[key]; });
    conditions.forEach(function (record) {
      App.OBJECT_PROPS[record.id] = conditionProps(record);
    });
    App.OBJECT_PROPS.gravity = gravityProps();
    previousConditionKeys = conditions.map(function (record) { return record.id; });

    // Last, so every node it has to place already exists.
    syncTrees(!!(App.PROJECT && App.PROJECT.layered_soil), sharedSoilNodes[0]);
  }

  /* Volumes are measured by the geometry build, not the project, so they arrive
     separately. Called by the viewport once a payload has been drawn. */
  function setVolumes(mass) {
    Object.keys(mass || {}).forEach(function (key) {
      var props = App.OBJECT_PROPS[key];
      if (!props) return;
      props.groups.General.forEach(function (row) {
        if (row[0] === 'Volume') { row[1] = mass[key].toFixed(1); row[3] = false; }
      });
    });
  }

  function groupedInteger(value) {
    return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  function setMeshStats(stats) {
    if (!stats) return;
    var elements = groupedInteger(stats.elements);
    var nodes = groupedInteger(stats.nodes);
    var typeNames = Object.keys(stats.by_type || {});
    var props = App.OBJECT_PROPS && App.OBJECT_PROPS.mesh;

    if (props && props.groups && props.groups.Statistics) {
      props.groups.Statistics.forEach(function (row) {
        if (row[0] === 'Element type') row[1] = typeNames.join(', ') || '—';
        else if (row[0] === 'Elements') row[1] = elements;
        else if (row[0] === 'Nodes') row[1] = nodes;
        else if (row[0] === 'Average element size') row[1] = '—';
      });
    }

    Object.keys(App.TREES || {}).forEach(function (mode) {
      (function walk(items) {
        (items || []).forEach(function (item) {
          if (item.obj === 'mesh' && /^Elements:/.test(item.label)) item.label = 'Elements: ' + elements;
          if (item.obj === 'mesh' && /^Nodes:/.test(item.label)) item.label = 'Nodes: ' + nodes;
          walk(item.children);
        });
      })(App.TREES[mode]);
    });

    if (App.Explorer && App.state) {
      App.Explorer.mountTree(App.state.mode);
      if (App.state.selection === 'mesh') App.Explorer.mountSelection('mesh');
    }
  }

  /* mdpa-import-dialog.js's "Accept": `parts` is `[{key, label, color}]`, one per
     checklist row the user left checked. Replaces whatever was accepted before --
     this is one deck's worth of parts at a time, not an accumulating library, the same
     way `App.Viewport.showImportedMesh` replaces the previous preview outright. */
  function setImportedParts(parts) {
    parts = parts || [];
    importedMeshNode.count = parts.length;
    importedMeshNode.children = parts.map(function (part) {
      return { label: part.label, swatch: part.color, leaf: true, eye: true, obj: part.key };
    });
    if (App.Viewport && App.Viewport.setImportedGroupKeys) {
      App.Viewport.setImportedGroupKeys(parts.map(function (part) { return part.key; }));
    }
    syncTrees(!!(App.PROJECT && App.PROJECT.layered_soil), soilNodes()[0]);
    if (App.Explorer && App.state) App.Explorer.mountTree(App.state.mode);
  }

  return {
    fromProject: fromProject, materialsToServer: materialsToServer,
    extentOf: extentOf,
    pendingDomain: pendingDomain, pendingWater: pendingWater,
    outOfPlaneAxis: outOfPlaneAxis,
    apply: apply, load: load,
    projectTitle: projectTitle, syncTitle: syncTitle,
    rebuildDerived: rebuildDerived, setVolumes: setVolumes, setMeshStats: setMeshStats,
    setImportedParts: setImportedParts,
    domain: function () { return domain; }
  };
})();
