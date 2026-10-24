/* Tests for frontend/js/model.js — server project → the App globals the frozen UI reads.

   The interesting half is rebuildDerived(). App.TREES and App.OBJECT_PROPS are
   built once inside an IIFE at js/data.js:460-579 and closed over, which is why a
   layer added in the soil dialog never shows up in the tree today. */

(function () {

  function project(layers, customParts, layeredSoil) {
    return {
      name: 'Test site',
      layered_soil: !!layeredSoil,
      domain: { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 },
      boreholes: [
        { id: 'bh1', name: 'BH-1', x: 0, y: 0, head: 0, water: -1.5 },
        { id: 'bh2', name: 'BH-2', x: 28, y: 4, head: -0.4, water: -1.8 }
      ],
      materials: [
        { id: 'm2', name: 'Sand, loose', color: '#c4a86a',
          constitutive_law: 'GeoLinearElasticPlaneStrain2DLaw',
          variables: { YOUNG_MODULUS: 2.5e7, POISSON_RATIO: 0.28, DENSITY_SOLID: 1834.86,
                       GEO_COHESION: 500, GEO_FRICTION_ANGLE: 32 } },
        { id: 'm4', name: 'Clay, stiff', color: '#6f8fa8',
          constitutive_law: 'GeoLinearElasticPlaneStrain2DLaw',
          variables: { GEO_DRAINAGE_TYPE: 'FULLY_COUPLED', YOUNG_MODULUS: 1.2e7,
                       POISSON_RATIO: 0.33, DENSITY_SOLID: 1783.89 } }
      ],
      layers: layers,
      custom_parts: customParts || []
    };
  }

  var TWO = [
    { id: 'L1', name: 'Soil_1', mat: 'm2', tops: { bh1: 0, bh2: -0.4 }, bots: { bh1: -8, bh2: -9.2 } },
    { id: 'L2', name: 'Soil_2', mat: 'm4', tops: { bh1: -8, bh2: -9.2 }, bots: { bh1: -25, bh2: -25 } }
  ];

  var THREE_LAYERS = [
    { id: 'L1', name: 'Soil_1', mat: 'm2', tops: { bh1: 0, bh2: -0.4 }, bots: { bh1: -4, bh2: -5 } },
    { id: 'L3', name: 'Peat',   mat: 'm4', tops: { bh1: -4, bh2: -5 },  bots: { bh1: -8, bh2: -9.2 } },
    { id: 'L2', name: 'Soil_2', mat: 'm4', tops: { bh1: -8, bh2: -9.2 }, bots: { bh1: -25, bh2: -25 } }
  ];

  /* Every test restores the globals, so ordering cannot leak. */
  function withProject(p, fn) {
    var saved = {
      LAYERS: App.LAYERS, MATERIALS: App.MATERIALS, BOREHOLES: App.BOREHOLES,
      LOADS: App.LOADS, PROJECT: App.PROJECT, props: App.OBJECT_PROPS, trees: {},
      BEAMS: App.BEAMS, BEAM_SECTIONS: App.BEAM_SECTIONS,
      ANCHORS: App.ANCHORS, ANCHOR_SECTIONS: App.ANCHOR_SECTIONS,
      INTERFACES: App.INTERFACES, INTERFACE_SECTIONS: App.INTERFACE_SECTIONS
    };
    // A layered_soil project replaces App.TREES[mode] wholesale (js/model.js), which
    // would otherwise permanently discard the rich per-mode structure for every test
    // that runs after this one in the same page.
    Object.keys(App.TREES || {}).forEach(function (mode) { saved.trees[mode] = App.TREES[mode]; });
    App.OBJECT_PROPS = Object.assign({}, App.OBJECT_PROPS);
    try {
      App.Model.apply(p);
      return fn();
    } finally {
      App.LAYERS = saved.LAYERS;
      App.MATERIALS = saved.MATERIALS;
      App.BOREHOLES = saved.BOREHOLES;
      App.LOADS = saved.LOADS;
      App.BEAMS = saved.BEAMS;
      App.BEAM_SECTIONS = saved.BEAM_SECTIONS;
      App.ANCHORS = saved.ANCHORS;
      App.ANCHOR_SECTIONS = saved.ANCHOR_SECTIONS;
      App.INTERFACES = saved.INTERFACES;
      App.INTERFACE_SECTIONS = saved.INTERFACE_SECTIONS;
      App.PROJECT = saved.PROJECT;
      App.OBJECT_PROPS = saved.props;
      Object.keys(saved.trees).forEach(function (mode) { App.TREES[mode] = saved.trees[mode]; });
      App.Model.rebuildDerived();          // put the shared tree nodes back
    }
  }

  function soilNode(tree) {
    var found = null;
    (function walk(nodes) {
      (nodes || []).forEach(function (n) {
        if (n.obj === 'soil') found = n;
        walk(n.children);
      });
    })(tree);
    return found;
  }

  function customGeometryNode(tree) {
    var found = null;
    (function walk(nodes) {
      (nodes || []).forEach(function (n) {
        if (n.label === 'Custom geometry') found = n;
        walk(n.children);
      });
    })(tree);
    return found;
  }

  /* ── Mapping ─────────────────────────────────────────────────── */

  test('a material arrives as the Kratos property set the server holds', function () {
    var m = App.Model.fromProject(project(TWO)).MATERIALS[0];
    T.eq(m.constitutive_law, 'GeoLinearElasticPlaneStrain2DLaw');
    T.eq(m.variables.YOUNG_MODULUS, 2.5e7);
    T.eq(m.color, '#c4a86a');
    T.eq(m.id, 'm2');
  });

  test('layers keep their per-borehole tops and bottoms', function () {
    var l = App.Model.fromProject(project(TWO)).LAYERS[0];
    T.eq(l.tops, { bh1: 0, bh2: -0.4 });
    T.eq(l.bots, { bh1: -8, bh2: -9.2 });
    T.eq(l.mat, 'm2');
  });

  test('apply installs the globals the frozen scripts already close over', function () {
    withProject(project(TWO), function () {
      T.eq(App.LAYERS.length, 2);
      T.eq(App.BOREHOLES.length, 2);
      T.eq(App.matById('m4').name, 'Clay, stiff');
    });
  });

  function piledProject() {
    var p = project(TWO);
    p.dimension = 2; p.section_offset = 20;
    p.beam_sections = [{ id: 'az26', name: 'AZ 26-700', spacing: 1,
                         constitutive_law: 'TimoshenkoBeamElasticConstitutiveLaw', tables: {},
                         variables: { YOUNG_MODULUS: 2.1e11, POISSON_RATIO: 0.3,
                                      CROSS_AREA: 0.0198, I33: 5.52e-4, DENSITY: 7850 } }];
    p.beams = [{ id: 'beam_1', name: 'Sheet pile 1', section: 'az26',
                 points: [[12, 0], [12, -14]], active: true }];
    return p;
  }

  function nodeLabelled(tree, label) {
    var found = null;
    (function walk(nodes) {
      (nodes || []).forEach(function (node) {
        if (node.label === label) found = node;
        walk(node.children);
      });
    })(tree);
    return found;
  }

  test('a sheet pile gets its own tree entry and selection properties', function () {
    withProject(piledProject(), function () {
      var piles = nodeLabelled(App.TREES.structures, 'Sheet piles');
      T.ok(piles, 'Sheet piles node exists');
      T.eq(piles.count, 1);
      T.eq(piles.children[0].obj, 'beam_1');

      var props = App.OBJECT_PROPS.beam_1;
      T.eq(props.title, 'Sheet pile 1');
      T.eq(props.groups.Geometry.map(function (row) { return row[0]; }),
           ['x1', 'y1', 'x2', 'y2', 'Length', 'Delete']);
      T.eq(props.groups.Geometry[4][1], '14.000', 'length is derived from the polyline');
      T.eq(props.groups.General[0][1], 'AZ 26-700', 'the shared profile is named');
    });
  });

  test('the section rows edit the shared profile and reject a bad value', function () {
    withProject(piledProject(), function () {
      var rows = App.OBJECT_PROPS.beam_1.groups.Section;
      var area = rows.filter(function (row) { return row[0] === 'CROSS_AREA'; })[0];
      T.eq(area[2], 'm²', 'labelled in the project units');
      T.eq(area[4].set(0.03), null);
      T.eq(App.BEAM_SECTIONS[0].variables.CROSS_AREA, 0.03, 'the profile itself moved');
      T.ok(area[4].set(-1), 'a negative area is refused');
      T.eq(App.BEAM_SECTIONS[0].variables.CROSS_AREA, 0.03, 'and the profile is left as it was');
    });
  });

  test('a pile coordinate edit is refused when it collapses a segment', function () {
    withProject(piledProject(), function () {
      var rows = App.OBJECT_PROPS.beam_1.groups.Geometry;
      var y2 = rows.filter(function (row) { return row[0] === 'y2'; })[0];
      T.ok(y2[4].set(0), 'a pile of zero length cannot be meshed');
      T.eq(App.BEAMS[0].points[1][1], -14, 'the pile is unchanged');
      T.eq(y2[4].set(-10), null);
      T.eq(App.BEAMS[0].points[1][1], -10);
    });
  });

  test('sheet piles drawn in 2D are shown in a 3D view, not dropped', function () {
    /* The solid model builds them on the section plane (build._section_sweeps), so
       the explorer has to list them: a row that disappears on the mode switch reads
       as a lost structure. */
    var p = piledProject();
    p.dimension = 3;
    withProject(p, function () {
      T.eq(App.BEAMS.length, 1, 'the pile is built on the section plane in 3D');
      T.eq(nodeLabelled(App.TREES.structures, 'Sheet piles').count, 1);
      T.eq(p.beams.length, 1, 'the record survives in the project');
    });
  });

  function anchoredProject() {
    var p = piledProject();
    p.anchor_sections = [{ id: 'strand', name: '4-strand tendon', spacing: 2.5,
                           tension_limit: 900000, compression_limit: null,
                           constitutive_law: 'TrussConstitutiveLaw', tables: {},
                           variables: { YOUNG_MODULUS: 1.95e11, CROSS_AREA: 0.0006,
                                        DENSITY: 7850 } }];
    p.anchors = [{ id: 'anchor_1', name: 'Anchor 1', kind: 'anchor', section: 'strand',
                   head: [12, -2], tail: [20, -8], prestress: 250, active: true }];
    return p;
  }

  test('an anchor gets its own tree entry and selection properties', function () {
    withProject(anchoredProject(), function () {
      var anchors = nodeLabelled(App.TREES.structures, 'Anchors');
      T.ok(anchors, 'Anchors node exists');
      T.eq(anchors.count, 1);
      T.eq(anchors.children[0].obj, 'anchor_1');

      var props = App.OBJECT_PROPS.anchor_1;
      T.eq(props.title, 'Anchor 1');
      T.eq(props.groups.Geometry.map(function (row) { return row[0]; }),
           ['Head x', 'Head y', 'Tail x', 'Tail y', 'Length', 'Inclination', 'Delete']);
      T.eq(props.groups.Geometry[4][1], '10.000', 'length is derived from the ends');
      T.eq(props.groups.Geometry[5][1], '36.870', 'so is the rake');
      T.eq(props.groups.General[0][1], '4-strand tendon');
    });
  });

  test('an anchor head cannot be edited off the sheet pile it hangs from', function () {
    withProject(anchoredProject(), function () {
      var rows = App.OBJECT_PROPS.anchor_1.groups.Geometry;
      var headX = rows.filter(function (row) { return row[0] === 'Head x'; })[0];
      T.ok(headX[4].set(20), 'a head in mid-air is refused');
      T.eq(App.ANCHORS[0].head[0], 12, 'and the anchor is left where it was');
      var headZ = rows.filter(function (row) { return row[0] === 'Head y'; })[0];
      T.eq(headZ[4].set(-5), null, 'sliding along the pile is fine');
      T.eq(App.ANCHORS[0].head[1], -5);
    });
  });

  test('the tendon rows edit the shared library and reject a bad value', function () {
    withProject(anchoredProject(), function () {
      var rows = App.OBJECT_PROPS.anchor_1.groups.Tendon;
      var area = rows.filter(function (row) { return row[0] === 'CROSS_AREA'; })[0];
      T.eq(area[4].set(0.0009), null);
      T.eq(App.ANCHOR_SECTIONS[0].variables.CROSS_AREA, 0.0009);
      T.ok(area[4].set(0), 'a tendon with no steel is refused');
      T.eq(App.ANCHOR_SECTIONS[0].variables.CROSS_AREA, 0.0009);
    });
  });

  test('anchors drawn in 2D are shown in a 3D view, not dropped', function () {
    var p = anchoredProject();
    p.dimension = 3;
    withProject(p, function () {
      T.eq(App.ANCHORS.length, 1, 'the tie hangs off the pile in 3D too');
      T.eq(nodeLabelled(App.TREES.structures, 'Anchors').count, 1);
      T.eq(p.anchors.length, 1, 'the record survives in the project');
    });
  });

  function contactedProject() {
    var p = piledProject();
    p.interface_sections = [{ id: 'contact_1', name: 'Steel against sand',
                              material: 'm2', r_inter: 0.67, virtual_thickness: 0.01,
                              permeability: 'Neutral', variables: {}, tables: {},
                              constitutive_law: 'GeoIncrementalLinearElasticInterfaceLaw' }];
    p.interfaces = [{ id: 'interface_1', name: 'Wall contact', kind: 'interface',
                      section: 'contact_1', structure: 'beam_1', points: null,
                      side: 'both', active: true }];
    return p;
  }

  test('an interface gets its own tree entry and selection properties', function () {
    withProject(contactedProject(), function () {
      var contacts = nodeLabelled(App.TREES.structures, 'Interfaces');
      T.ok(contacts, 'Interfaces node exists');
      T.eq(contacts.count, 1);
      T.eq(contacts.children[0].obj, 'interface_1');

      var props = App.OBJECT_PROPS.interface_1;
      T.eq(props.title, 'Wall contact');
      T.eq(props.groups.General[1][1], 'Sheet pile');
      T.eq(props.groups.Geometry.map(function (row) { return row[0]; }),
           ['Follows', 'Length', 'Delete']);
      T.eq(props.groups.Geometry[1][1], '14.000',
           'the length is the pile the interface runs along');
    });
  });

  test('the side row edits the interface and refuses a side it cannot hold', function () {
    withProject(contactedProject(), function () {
      var side = App.OBJECT_PROPS.interface_1.groups.General
        .filter(function (row) { return row[0] === 'Side'; })[0];
      T.eq(side[4].set('left'), null);
      T.eq(App.INTERFACES[0].side, 'left');

      // A free line has no structure between its faces, so "both" leaves nothing
      // holding the original nodes -- the same rule the server enforces.
      App.INTERFACES[0].structure = null;
      App.INTERFACES[0].points = [[8, 0], [8, -10]];
      T.ok(side[4].set('both'));
      T.eq(App.INTERFACES[0].side, 'left', 'and the record is left as it was');
    });
  });

  test('the contact rows edit the shared library and reject a bad value', function () {
    withProject(contactedProject(), function () {
      var rows = App.OBJECT_PROPS.interface_1.groups.Contact;
      var reduction = rows.filter(function (row) {
        return row[0] === 'R_inter (Coulomb law only)'; })[0];
      T.eq(reduction[4].set(0.55), null);
      T.eq(App.INTERFACE_SECTIONS[0].r_inter, 0.55);
      T.ok(reduction[4].set(1.4), 'a contact stronger than the soil is refused');
      T.eq(App.INTERFACE_SECTIONS[0].r_inter, 0.55);
    });
  });

  test('a contact with no Rinter of its own says it takes each soil’s', function () {
    var p = contactedProject();
    p.interface_sections[0].r_inter = null;
    withProject(p, function () {
      var row = App.OBJECT_PROPS.interface_1.groups.Contact.filter(function (r) {
        return r[0] === 'R_inter (Coulomb law only)'; })[0];
      T.eq(row.slice(0, 4), ['R_inter (Coulomb law only)', 'each soil’s own', '', true]);
    });
  });

  test('the contact stiffnesses come first and are typed in place', function () {
    /* The two numbers a user comes to set. Left out they read "derived", and the export
       takes them from the soil; typed, a button puts them back to that. The CLI's way
       to the same is `section set ID INTERFACE_NORMAL_STIFFNESS=...`. */
    withProject(contactedProject(), function () {
      var rows = App.OBJECT_PROPS.interface_1.groups.Contact;
      T.eq(rows.slice(0, 2).map(function (row) { return row.slice(0, 2); }),
           [['INTERFACE_NORMAL_STIFFNESS', 'derived'], ['INTERFACE_SHEAR_STIFFNESS', 'derived']]);
      T.eq(rows[0][3], false, 'editable while derived');
      T.ok(!rows.some(function (row) { return row[0] === 'Stiffness'; }),
           'nothing to put back while both are derived');
      T.eq(rows[0][4].set(2e9), null);
      T.eq(App.INTERFACE_SECTIONS[0].variables.INTERFACE_NORMAL_STIFFNESS, 2e9);
      T.ok(rows[1][4].set(-1), 'a stiffness at or below zero is refused');
      T.eq(App.INTERFACE_SECTIONS[0].variables.INTERFACE_SHEAR_STIFFNESS, undefined);
    });
  });

  test('typed stiffnesses can be put back to the derived ones', function () {
    var p = contactedProject();
    p.interface_sections[0].variables = { INTERFACE_NORMAL_STIFFNESS: 2e9,
                                          INTERFACE_SHEAR_STIFFNESS: 2e8 };
    withProject(p, function () {
      var rows = App.OBJECT_PROPS.interface_1.groups.Contact;
      T.eq(rows[0].slice(0, 2), ['INTERFACE_NORMAL_STIFFNESS', '2000000000']);
      var reset = rows.filter(function (row) { return row[0] === 'Stiffness'; })[0];
      var committed = App.commitSelectionEdit;
      App.commitSelectionEdit = function () {};
      try { reset[4].run(); } finally { App.commitSelectionEdit = committed; }
      T.eq(App.INTERFACE_SECTIONS[0].variables, {});
    });
  });

  test('a free interface shows its own coordinates instead of a pile', function () {
    var p = contactedProject();
    p.interfaces[0].structure = null;
    p.interfaces[0].points = [[8, 0], [8, -10]];
    p.interfaces[0].side = 'left';
    withProject(p, function () {
      var props = App.OBJECT_PROPS.interface_1;
      T.eq(props.groups.General[1][1], 'Own line');
      T.eq(props.groups.Geometry.map(function (row) { return row[0]; }),
           ['x1', 'y1', 'x2', 'y2', 'Length', 'Delete']);
    });
  });

  test('interfaces drawn in 2D are listed in a 3D view', function () {
    /* Shown, though still authored in 2D only (App.Interfaces.available) and still
       exporting no elements in 3D: the line is swept into the solid model and splits
       its mesh, so the row has something behind it. */
    var p = contactedProject();
    p.dimension = 3;
    withProject(p, function () {
      T.eq(App.INTERFACES.length, 1);
      T.eq(nodeLabelled(App.TREES.structures, 'Interfaces').count, 1);
      T.eq(p.interfaces.length, 1, 'the record survives in the project');
    });
  });

  /* ── A translated load pair ──────────────────────────────────────
     core/model/load_translation.py turns a surface load into a line load on the switch to 2D and
     back, keeping both records so the footprint survives the round trip. Exactly one
     half of a pair belongs to the model: `App.Model`'s `loadsFor` mirrors the server's
     `Project.loads_for`, and these hold the two in step. */

  function pairedLoads() {
    return [
      { id: 'surfaceload_1', name: 'SurfaceLoad_1', kind: 'surface', x0: 4, x1: 16,
        z0: 15, z1: 25, thickness: 0.3, components: [0, 0, -25],
        distribution: 'Uniform', active: true, derived_from: null },
      { id: 'surfaceload_1_2d', name: 'SurfaceLoad_1', kind: 'line', x0: 4, x1: 16,
        y: 0, thickness: 0.3, components: [0, -25], distribution: 'Uniform',
        active: true, derived_from: 'surfaceload_1' }
    ];
  }

  /* A surface load is a horizontal pad, so x/z say where it sits in plan and y says
     how high it lies -- the elevation the server imprints it at (SurfaceLoad.y). The
     point and line loads have always shown their y; the pad's grid listed only the
     plan extents, so the one number that says which face it loads was invisible. */

  function surfaceRows(load) {
    var p = project(TWO);
    p.dimension = 3;
    p.loads = [load];
    return withProject(p, function () {
      return App.OBJECT_PROPS.surfaceload_1.groups.Geometry;
    });
  }

  function rowNamed(rows, label) {
    return rows.filter(function (r) { return r[0] === label; })[0];
  }

  test('a surface load shows the elevation it lies at', function () {
    var load = pairedLoads()[0];
    load.y = 4;
    var rows = surfaceRows(load);
    var row = rowNamed(rows, 'y');
    T.ok(row, 'the pad gives no clue which face it loads');
    T.eq(row[1], '4.000');
    T.eq(row[2], 'm');
    T.ok(row[4], 'it should be editable, like the line load it translates to');
  });

  test('a surface load with no elevation says so rather than showing a number', function () {
    /* y is optional: null means "the top of the model", resolved server-side against
       ground_y. Formatting that as 0.000 would claim a level the load does not have. */
    var rows = surfaceRows(pairedLoads()[0]);
    var row = rowNamed(rows, 'y');
    T.ok(row, 'the row should still be there');
    T.eq(row[1], 'Top of model');
    T.ok(row[3], 'with nothing to edit, it is read-only');
  });

  test('the pad keeps its plan extents alongside the elevation', function () {
    var rows = surfaceRows(pairedLoads()[0]).map(function (r) { return r[0]; });
    ['x min', 'x max', 'z min', 'z max', 'Area'].forEach(function (label) {
      T.ok(rows.indexOf(label) >= 0, label + ' should still be shown');
    });
  });

  test('the pad reads x, then y, then z -- the order the axes are named in', function () {
    /* Elevation between the two plan axes rather than after them, so the grid reads
       in the same order as the load components above it (qx, qy, qz) and as the
       Edit surface load dialog. */
    var rows = surfaceRows(pairedLoads()[0]).map(function (r) { return r[0]; });
    T.eq(rows.slice(0, 5), ['x min', 'x max', 'y', 'z min', 'z max']);
  });

  test('a translated load pair shows its 3D half in the solid model', function () {
    var p = project(TWO);
    p.dimension = 3;
    p.loads = pairedLoads();
    withProject(p, function () {
      T.eq(App.LOADS.map(function (l) { return l.id; }), ['surfaceload_1'],
           'the line half is the same load, not a second one');
      T.eq(nodeLabelled(App.TREES.structures, 'Loads').count, 1);
    });
  });

  test('a translated load pair shows its 2D half in the section', function () {
    var p = project(TWO);
    p.dimension = 2; p.section_offset = 20;
    p.loads = pairedLoads();
    withProject(p, function () {
      T.eq(App.LOADS.map(function (l) { return l.id; }), ['surfaceload_1_2d']);
      T.eq(nodeLabelled(App.TREES.structures, 'Loads').count, 1);
    });
  });

  test('a pair whose pad is clear of the section plane is not in the section', function () {
    /* Mirrors Project.loads_for(2): the pad at z 15..25 does not load a cut at z 5. */
    var p = project(TWO);
    p.dimension = 2; p.section_offset = 5;
    p.loads = pairedLoads();
    withProject(p, function () {
      T.eq(App.LOADS.map(function (l) { return l.id; }), []);
    });
  });

  test('a pair clear of the plane is still a load when the 2D half was authored', function () {
    /* The derived half is the surface one here; the rule follows the pad either way. */
    var p = project(TWO);
    p.dimension = 2; p.section_offset = 5;
    p.loads = [
      { id: 'lineload_1', name: 'LineLoad_1', kind: 'line', x0: 4, x1: 16, y: 0,
        thickness: 0.15, components: [0, -25], distribution: 'Uniform',
        active: true, derived_from: null },
      { id: 'lineload_1_3d', name: 'SurfaceLoad_1', kind: 'surface', x0: 4, x1: 16,
        z0: 15, z1: 25, thickness: 0.15, components: [0, -25, 0],
        distribution: 'Uniform', active: true, derived_from: 'lineload_1' }
    ];
    withProject(p, function () {
      T.eq(App.LOADS.map(function (l) { return l.id; }), []);
      p.section_offset = 20;
    });
    withProject(p, function () {
      T.eq(App.LOADS.map(function (l) { return l.id; }), ['lineload_1'],
           'moving the plane onto the pad brings it back');
    });
  });

  test('a 2D load with no surface counterpart is shown in 3D too', function () {
    /* A point load is kN, not kN/m2, and there is no 3D point-load kind: it is
       carried at the section plane rather than translated or dropped. */
    var p = project(TWO);
    p.dimension = 3;
    p.loads = [{ id: 'load_1', name: 'PointLoad_1', kind: 'point', x: 10, y: 0,
                 thickness: 0.25, components: [0, -30], distribution: 'Uniform',
                 active: true, derived_from: null }];
    withProject(p, function () {
      T.eq(App.LOADS.map(function (l) { return l.id; }), ['load_1']);
    });
  });

  test('named loads replace the frozen sample in the tree and selection properties', function () {
    var p = project(TWO);
    p.dimension = 2; p.section_offset = 20;
    p.loads = [{ id: 'load_1', name: 'LineLoad_1', kind: 'line', x0: 2, x1: 9, y: 0,
      thickness: 0.15, components: [3, -20], distribution: 'Uniform', active: true }];
    withProject(p, function () {
      var loads = null;
      (function walk(nodes) {
        (nodes || []).forEach(function (node) {
          if (node.label === 'Loads') loads = node;
          walk(node.children);
        });
      })(App.TREES.structures);
      T.ok(loads, 'Loads node exists');
      T.eq(loads.count, 1);
      T.eq(loads.children[0].obj, 'load_1');
      T.eq(App.OBJECT_PROPS.load_1.title, 'LineLoad_1');
      T.eq(App.OBJECT_PROPS.load_1.groups.Geometry.some(function (row) { return /^z/.test(row[0]); }), false);
      T.eq(App.OBJECT_PROPS.load_1.groups.Components.map(function (row) { return row[0]; }), ['qx', 'qy']);
      T.eq(App.OBJECT_PROPS.load_1.groups.Components[0][1], '3.000');
    });
  });

  /* ── rebuildDerived ──────────────────────────────────────────── */

  test('a third layer appears in the model tree', function () {
    withProject(project(THREE_LAYERS), function () {
      var node = soilNode(App.TREES.soil);
      T.eq(node.count, 3);
      T.eq(node.children.length, 3);
      T.eq(node.children.map(function (c) { return c.obj; }),
           ['soil_L1', 'soil_L3', 'soil_L2']);
    });
  });

  test('the soil node is shared, so every mode tree updates at once', function () {
    // js/data.js:573-577 puts one soilVolumes object into five trees. Rebuilding it
    // in place is what keeps all five consistent; replacing it would update one.
    T.ok(soilNode(App.TREES.soil) === soilNode(App.TREES.structures), 'soil/structures');
    T.ok(soilNode(App.TREES.soil) === soilNode(App.TREES.staged), 'soil/staged');
    withProject(project(THREE_LAYERS), function () {
      T.eq(soilNode(App.TREES.flow).children.length, 3);
      T.eq(soilNode(App.TREES.mesh).children.length, 3);
    });
  });

  test('a layer swatch follows its assigned material', function () {
    withProject(project(THREE_LAYERS), function () {
      var kids = soilNode(App.TREES.soil).children;
      T.eq(kids[0].swatch, '#c4a86a');
      T.eq(kids[1].swatch, '#6f8fa8');
      T.ok(/Peat/.test(kids[1].label), kids[1].label);
    });
  });

  test('selection properties exist for every layer and only for those layers', function () {
    withProject(project(THREE_LAYERS), function () {
      T.ok(App.OBJECT_PROPS.soil_L3, 'soil_L3 missing — selecting it would show nothing');
      var keys = Object.keys(App.OBJECT_PROPS).filter(function (k) { return /^soil_/.test(k); });
      T.eq(keys.sort(), ['soil_L1', 'soil_L2', 'soil_L3']);
    });
  });

  test('a removed layer stops being selectable', function () {
    withProject(project(THREE_LAYERS), function () {});
    withProject(project(TWO), function () {
      T.ok(!App.OBJECT_PROPS.soil_L3, 'stale soil_L3 survived the rebuild');
    });
  });

  test('layer depths in the property grid span the boreholes', function () {
    withProject(project(TWO), function () {
      var geom = App.OBJECT_PROPS.soil_L1.groups.Geometry;
      function value(label) {
        return geom.filter(function (r) { return r[0] === label; })[0][1];
      }
      T.eq(value('y max'), '0.000');       // highest top, at bh1
      T.eq(value('y min'), '-9.200');      // lowest bottom, at bh2
      T.eq(value('x max'), '50.000');      // from the project domain, not a literal
    });
  });

  test('the property grid follows the domain rather than assuming 50 × 40', function () {
    var p = project(TWO);
    p.domain = { x0: 0, x1: 120, z0: -10, z1: 30, y_top: 0, y_bottom: -25 };
    withProject(p, function () {
      var geom = App.OBJECT_PROPS.soil_L1.groups.Geometry;
      function value(label) {
        return geom.filter(function (r) { return r[0] === label; })[0][1];
      }
      T.eq(value('x max'), '120.000');
      T.eq(value('z min'), '-10.000');
    });
  });

  /* In a plane-strain model the axis normal to the section is not part of the
     geometry any more: the body runs forever that way. That axis is z -- x and y
     still bound the section itself. What replaces the pair is where the cut sits,
     which is the one thing about that axis that still matters and would otherwise
     vanish from the panel entirely. */
  (function () {
    function labels(p) {
      return withProject(p, function () {
        return App.OBJECT_PROPS.soil_L1.groups.Geometry.map(function (r) { return r[0]; });
      });
    }

    test('a 3D model shows all three extents', function () {
      var rows = labels(project(TWO));
      ['x min', 'x max', 'y min', 'y max', 'z min', 'z max'].forEach(function (label) {
        T.ok(rows.indexOf(label) >= 0, label + ' should be shown in 3D');
      });
      T.eq(rows.filter(function (r) { return /^Section/.test(r); }).length, 0);
    });

    test('the section drops the out-of-plane extents, not the in-plane ones', function () {
      var p = project(TWO);
      p.dimension = 2; p.section_offset = 12.5;
      var rows = labels(p);
      T.eq(rows.indexOf('z min'), -1, 'z min is not a property of a plane-strain model');
      T.eq(rows.indexOf('z max'), -1);
      T.ok(rows.indexOf('x min') >= 0, 'x still bounds the section');
      T.ok(rows.indexOf('x max') >= 0);
      T.ok(rows.indexOf('y min') >= 0, 'and y still bounds it top to bottom');
      T.ok(rows.indexOf('y max') >= 0);
    });

    test('the section position replaces the extents it hid', function () {
      var p = project(TWO);
      p.dimension = 2; p.section_offset = 12.5;
      withProject(p, function () {
        var geom = App.OBJECT_PROPS.soil_L1.groups.Geometry;
        var row = geom.filter(function (r) { return r[0] === 'Section at z'; })[0];
        T.ok(row, 'the panel says where the cut is');
        T.eq(row[1], '12.500');
        T.eq(row[2], 'm');
      });
    });
  })();

  /* ── Custom geometry (drawn/imported parts) ─────────────────────

     Before this, rebuildDerived() never looked at project.custom_parts at all: a
     drawn line, box or surface got no tree node and no OBJECT_PROPS entry, so there
     was nothing in the Model explorer to select or delete -- exactly the reported bug.
     Worse, the default project has layered_soil: true, which collapses every mode's
     tree down to just the Soil node, discarding anything else that isn't re-added. */

  var PART = { key: 'drawn_0', label: 'Box_1', color: '#4b6ea8', source: 'gui' };
  var PART2 = { key: 'imported_0', label: 'my_model.step', color: '#888888', source: 'import' };

  test('a drawn part appears in the model tree with the layered_soil project', function () {
    withProject(project(TWO, [PART], true), function () {
      var node = customGeometryNode(App.TREES.soil);
      T.ok(node, 'no "Custom geometry" node in the layered_soil tree');
      T.eq(node.count, 1);
      T.eq(node.children.map(function (c) { return c.obj; }), ['drawn_0']);
      T.eq(node.children[0].label, 'Box_1');
    });
  });

  test('the custom geometry node is shared across every mode tree', function () {
    withProject(project(TWO, [PART, PART2], true), function () {
      ['soil', 'structures', 'mesh', 'flow', 'staged'].forEach(function (mode) {
        var node = customGeometryNode(App.TREES[mode]);
        T.ok(node, mode + ' tree is missing the custom geometry node');
        T.eq(node.count, 2, mode);
      });
    });
  });

  test('a drawn part is selectable -- it has an OBJECT_PROPS entry', function () {
    withProject(project(TWO, [PART], true), function () {
      T.ok(App.OBJECT_PROPS.drawn_0, 'selecting drawn_0 would show nothing');
      T.eq(App.OBJECT_PROPS.drawn_0.title, 'Box_1');
    });
  });

  test('a deleted part stops being selectable and leaves the tree', function () {
    withProject(project(TWO, [PART, PART2], true), function () {});
    withProject(project(TWO, [PART2], true), function () {
      T.ok(!App.OBJECT_PROPS.drawn_0, 'stale drawn_0 survived the rebuild');
      var node = customGeometryNode(App.TREES.soil);
      T.eq(node.children.map(function (c) { return c.obj; }), ['imported_0']);
    });
  });

  /* A drawn soil body shows the same Geometry block a stack layer does, so it has to
     hide the same rows: in plane strain the model has no extent along z, and the
     body runs forever out of plane. This one kept its z min/z max after the stack
     layers stopped showing theirs -- the two grids are built by different functions
     (customPartProps vs geometryRows) and only the second one was re-based. */
  var DRAWN_SOIL = {
    key: 'drawn_2', label: 'Embankment', color: '#c4a86a', source: 'gui', mat: 'm2',
    recipe: { kind: 'polygon_extrude', extrusion: [0, 0, 20],
              vertices: [[0, 0, 0], [12, 0, 0], [9, 5, 0], [3, 5, 0]] }
  };

  function partRows(p) {
    return withProject(p, function () {
      return App.OBJECT_PROPS.drawn_2.groups.Geometry.map(function (r) { return r[0]; });
    });
  }

  test('a drawn soil body shows all three extents in 3D', function () {
    var rows = partRows(project(TWO, [DRAWN_SOIL]));
    ['x min', 'x max', 'y min', 'y max', 'z min', 'z max'].forEach(function (label) {
      T.ok(rows.indexOf(label) >= 0, label + ' should be shown in 3D');
    });
  });

  test('a drawn soil body drops its out-of-plane extents in the section', function () {
    var p = project(TWO, [DRAWN_SOIL]);
    p.dimension = 2; p.section_offset = 12.5;
    var rows = partRows(p);
    T.eq(rows.indexOf('z min'), -1, 'z min is not a property of a plane-strain model');
    T.eq(rows.indexOf('z max'), -1);
    T.ok(rows.indexOf('x min') >= 0, 'x still bounds the section');
    T.ok(rows.indexOf('y min') >= 0, 'and y still bounds it top to bottom');
    T.ok(rows.indexOf('Corners') >= 0, 'the corner editor stays either way');
  });

  test('with no custom parts, the tree has no Custom geometry row', function () {
    withProject(project(TWO, [], true), function () {
      T.ok(!customGeometryNode(App.TREES.soil),
           'an empty "Custom geometry [0]" row reads as if the model had some');
    });
  });

  /* Everything above asserts on App.TREES/App.OBJECT_PROPS directly. This one instead
     renders through the real js/explorer.js -- the same code the app uses -- so a
     mismatch between what model.js produces and what explorer.js expects to walk
     would show up here even if the data-level assertions above all still passed. */
  test('a drawn part appears in the actual rendered Model explorer DOM', function () {
    var savedState = App.state;
    App.state = { mode: 'soil', selection: null };

    var host = document.createElement('div');
    host.id = 'tree-model';
    document.body.appendChild(host);

    try {
      withProject(project(TWO, [PART], true), function () {
        App.Explorer.mountTree(App.state.mode);
        var labels = Array.prototype.map.call(
          host.querySelectorAll('.tree-label'), function (el) { return el.textContent; });
        T.ok(labels.indexOf('Custom geometry') >= 0,
          'no "Custom geometry" row rendered: [' + labels.join(', ') + ']');
        T.ok(labels.indexOf('Box_1') >= 0,
          'the drawn part itself is missing: [' + labels.join(', ') + ']');
      });
    } finally {
      document.body.removeChild(host);
      App.state = savedState;
    }
  });

  /* ── 3D structures ───────────────────────────────────────────────
     A wall panel and a member are what a sheet pile is in the solid model, and a
     space anchor is what an anchor is: the same collections, holding the kind that
     belongs to the project's own dimension. */

  function walledProject() {
    var p = project(TWO);
    p.dimension = 3;
    p.beam_sections = [{ id: 'az26', name: 'AZ 26-700', spacing: 1,
                         constitutive_law: 'TimoshenkoBeamElasticConstitutiveLaw', tables: {},
                         variables: { YOUNG_MODULUS: 2.1e11, POISSON_RATIO: 0.3,
                                      CROSS_AREA: 0.0198, I33: 5.52e-4, DENSITY: 7850 } }];
    p.panel_sections = [{ id: 'az26_wall', name: 'AZ 26-700 wall',
                          constitutive_law: 'LinearElasticPlaneStress2DLaw', tables: {},
                          variables: { YOUNG_MODULUS: 2.1e11, POISSON_RATIO: 0.3,
                                       THICKNESS: 0.4, DENSITY: 7850 } }];
    p.beams = [
      { id: 'panel_1', name: 'Wall 1', kind: 'panel', section: 'az26_wall',
        footprint: [[12, 4], [12, 20]], y_top: 0, y_toe: -14, active: true },
      { id: 'member_1', name: 'King post 1', kind: 'member', section: 'az26',
        points: [[18, 10, 0], [18, 10, -12]], active: true }
    ];
    p.anchor_sections = [{ id: 'strand', name: '4-strand tendon', spacing: 2.5,
                           tension_limit: 900000, compression_limit: null,
                           constitutive_law: 'TrussConstitutiveLaw', tables: {},
                           variables: { YOUNG_MODULUS: 1.95e11, CROSS_AREA: 0.0006,
                                        DENSITY: 7850 } }];
    p.anchors = [{ id: 'anchor_1', name: 'Anchor 1', kind: 'anchor3d', section: 'strand',
                   head: [12, 10, -2], tail: [17, 10, -8], prestress: 250, active: true }];
    return p;
  }

  test('a 3D project shows its walls and members where a 2D one shows sheet piles',
       function () {
    withProject(walledProject(), function () {
      T.eq(App.BEAMS.map(function (b) { return b.kind; }), ['panel', 'member']);
      T.eq(App.ANCHORS.map(function (a) { return a.kind; }), ['anchor3d']);
      T.eq(nodeLabelled(App.TREES.soil, 'Sheet piles').count, 2);
      // 3D-only kinds are unaffected: the traffic added here runs 2D -> 3D only.
      T.eq(nodeLabelled(App.TREES.soil, 'Anchors').count, 1);
    });
  });

  /* ── A translated wall pair ──────────────────────────────────────
     core/model/wall_translation.py turns a sheet pile into a wall panel on the switch to 3D and
     back, keeping both records so the plan footprint survives the round trip. The
     panel is what gives the wall y values to edit at all -- a pile has none. */

  function pairedWall() {
    var p = walledProject();
    p.beams = [
      { id: 'beam_1', name: 'Sheet pile 1', kind: 'beam', section: 'az26',
        points: [[10, 0], [10, -7.5]], active: true, derived_from: null },
      { id: 'beam_1_3d', name: 'Wall 1', kind: 'panel', section: 'az26_wall',
        footprint: [[10, 0], [10, 20]], y_top: 0, y_toe: -7.5, active: true,
        derived_from: 'beam_1' }
    ];
    p.anchors = [];
    return p;
  }

  test('a translated wall shows its panel in 3D, with z values to edit', function () {
    var p = pairedWall();
    p.dimension = 3;
    withProject(p, function () {
      T.eq(App.BEAMS.map(function (b) { return b.id; }), ['beam_1_3d'],
           'the pile half is the same wall, not a second one');
      var geometry = App.OBJECT_PROPS.beam_1_3d.groups.Geometry
        .map(function (row) { return row[0]; });
      T.ok(geometry.indexOf('z1') >= 0 && geometry.indexOf('z2') >= 0,
           'the wall has a plan footprint to edit: ' + geometry.join(', '));
    });
  });

  test('a translated wall shows its sheet pile in the section', function () {
    var p = pairedWall();
    p.dimension = 2; p.section_offset = 10;
    withProject(p, function () {
      T.eq(App.BEAMS.map(function (b) { return b.id; }), ['beam_1']);
    });
  });

  test('a 3D model shows its own kinds and the 2D ones drawn into it', function () {
    /* Both, now: a wall panel is drawn in plan and a sheet pile in the section, and
       the solid model builds each where it was drawn. The kinds keep their order in
       `beams[]` rather than being grouped. */
    var p = walledProject();
    p.beams = p.beams.concat([{ id: 'sheetpile_1', name: 'Sheet pile 1', kind: 'beam',
                                section: 'az26', points: [[12, 0], [12, -14]],
                                active: true }]);
    withProject(p, function () {
      T.eq(App.BEAMS.map(function (b) { return b.id; }),
           ['panel_1', 'member_1', 'sheetpile_1']);
      T.eq(p.beams.length, 3, 'the saved sheet pile is untouched');
    });
  });

  test('a wall is selectable and carries its thickness, levels and footprint',
       function () {
    withProject(walledProject(), function () {
      var props = App.OBJECT_PROPS.panel_1;
      T.eq(props.title, 'Wall 1');
      T.eq(props.groups.General[0][1], 'AZ 26-700 wall');
      var geometry = props.groups.Geometry.map(function (row) { return row[0]; });
      T.eq(geometry.slice(0, 4), ['x1', 'z1', 'x2', 'z2']);
      T.ok(geometry.indexOf('Top level') >= 0 && geometry.indexOf('Toe level') >= 0);
      var section = props.groups.Section.map(function (row) { return row[0]; });
      T.ok(section.indexOf('THICKNESS') >= 0, section.join(', '));
      T.eq(section.indexOf('CROSS_AREA'), -1, 'a wall has a thickness, not an area per metre');
    });
  });

  test('a member is selectable and carries its polyline in space', function () {
    withProject(walledProject(), function () {
      var props = App.OBJECT_PROPS.member_1;
      T.eq(props.title, 'King post 1');
      T.eq(props.groups.Geometry.map(function (row) { return row[0]; }).slice(0, 6),
           ['x1', 'y1', 'z1', 'x2', 'y2', 'z2']);
      var names = props.groups.Section.map(function (row) { return row[0]; });
      T.ok(names.indexOf('CROSS_AREA') >= 0 && names.indexOf('I22') >= 0, names.join(', '));
    });
  });

  test('a space anchor is selectable and carries both ends in space', function () {
    withProject(walledProject(), function () {
      var props = App.OBJECT_PROPS.anchor_1;
      T.eq(props.title, 'Anchor 1');
      T.eq(props.groups.Geometry.map(function (row) { return row[0]; }).slice(0, 6),
           ['Head x', 'Head y', 'Head z', 'Tail x', 'Tail y', 'Tail z']);
      T.eq(props.groups.Geometry[6][0], 'Length');
      T.eq(props.groups.Geometry[6][1], '7.810', 'the length is the 3D distance');
    });
  });

  test('a wall edit is refused when it would leave nothing to sweep', function () {
    withProject(walledProject(), function () {
      var rows = App.OBJECT_PROPS.panel_1.groups.Geometry;
      var toe = rows.filter(function (row) { return row[0] === 'Toe level'; })[0];
      T.ok(toe[4].set(0), 'a wall of zero height cannot be meshed');
      T.eq(App.BEAMS[0].y_toe, -14, 'the wall is left as it was');
      T.eq(toe[4].set(-10), null);
      T.eq(App.BEAMS[0].y_toe, -10);
    });
  });

  /* ── The title bar ───────────────────────────────────────────────
     js/app.js:244 writes the title once at boot out of the frozen App.PRODUCT
     constant, so every project loaded afterwards still read "Untitled project". */

  test('the title bar carries the loaded project name', function () {
    T.eq(App.Model.projectTitle({ name: 'Deep excavation — Rotterdam' }),
         App.PRODUCT.name + '  ' + App.PRODUCT.version
         + '  —  Deep excavation — Rotterdam  [Model]');
  });

  test('a project with no usable name falls back to Untitled project', function () {
    [{}, { name: '' }, { name: '   ' }, null].forEach(function (p) {
      T.ok(/—  Untitled project  \[Model\]$/.test(App.Model.projectTitle(p)),
           'got: ' + App.Model.projectTitle(p));
    });
  });

  test('applying a project rewrites the title bar and the constant boot() reads',
       function () {
    var savedName = App.PRODUCT.project;
    var bar = document.createElement('div');
    bar.id = 'tb-title';
    bar.textContent = 'stale';
    document.body.appendChild(bar);
    try {
      var p = project(TWO);
      p.name = 'Pit east';
      withProject(p, function () {
        T.eq(bar.textContent, App.Model.projectTitle(p));
        T.eq(App.PRODUCT.project, 'Pit east',
             'boot() re-reads this constant, so it has to move too');
      });
    } finally {
      bar.remove();
      App.PRODUCT.project = savedName;
    }
  });

  /* ── One tree, in one order ──────────────────────────────────────
     The explorer is remounted from App.TREES[mode] on every mode change, and the
     live nodes used to be pushed into the Structures tree alone -- so Loads, Sheet
     piles and Anchors disappeared the moment the user clicked Soil. */

  function topLabels(tree) {
    return (tree || []).map(function (node) { return node.label; });
  }

  test('every mode shows the same model tree, not a different one per mode', function () {
    withProject(project(TWO, [], true), function () {
      var soil = App.TREES.soil;
      ['structures', 'mesh', 'flow', 'staged'].forEach(function (mode) {
        T.ok(App.TREES[mode] === soil, mode + ' has a tree of its own: '
          + topLabels(App.TREES[mode]).join(', '));
      });
    });
  });

  test('the tree is ordered: what the model is made of, then what is built on it', function () {
    var p = anchoredProject();
    p.layered_soil = true;
    p.custom_parts = [PART];
    withProject(p, function () {
      T.eq(topLabels(App.TREES.soil),
           ['Soil', 'Custom geometry', 'Sheet piles', 'Anchors', 'Model conditions']);
    });
  });

  /* A group the model has nothing in has no row: an empty "Sheet piles [0]" row reads
     as if the model had sheet piles. Model conditions stays, for gravity. */
  test('a model with nothing but soil lists only Soil and Model conditions', function () {
    withProject(project(TWO, [], true), function () {
      T.eq(topLabels(App.TREES.soil), ['Soil', 'Model conditions']);
      T.ok(!nodeLabelled(App.TREES.soil, 'Boundary conditions'),
           'no "Boundary conditions [0]" row for a model without any');
    });
  });

  test('a full project keeps its frozen nodes, in the same one order', function () {
    withProject(anchoredProject(), function () {
      var labels = topLabels(App.TREES.soil);
      ['Sheet piles', 'Anchors'].forEach(function (label) {
        T.ok(labels.indexOf(label) >= 0, label + ' is missing from the Soil-mode tree: '
          + labels.join(', '));
      });
      var known = labels.filter(function (label) { return ORDER.indexOf(label) >= 0; });
      T.eq(known.slice().sort(function (a, b) { return ORDER.indexOf(a) - ORDER.indexOf(b); }),
           known, 'out of order: ' + known.join(', '));
      T.eq(labels.filter(function (l) { return l === 'Attributes library'; }).length, 1,
           'the two Attributes library nodes were merged into one');
    });
  });

  /* js/explorer.js:36 draws the visibility checkbox only for a node with both `eye`
     and `obj`, so a group row without them gets an empty slot -- which is why Loads,
     Sheet piles and Anchors had no box while Soil did. */
  test('every group row carries a visibility box, like Soil', function () {
    var p = anchoredProject();
    p.custom_parts = [PART];
    withProject(p, function () {
      ['Soil', 'Custom geometry', 'Sheet piles', 'Anchors'].forEach(function (label) {
        var node = nodeLabelled(App.TREES.soil, label);
        T.ok(node && node.eye === true, label + ' has no visibility checkbox');
        T.ok(node && node.obj, label + ' has no viewport key for the checkbox to toggle');
      });
    });
  });

  var ORDER = ['Attributes library', 'Soil', 'Boreholes', 'Geometry', 'Custom geometry',
               'Structures', 'Sheet piles', 'Anchors', 'Interfaces', 'Loads',
               'Flow conditions', 'Mesh', 'Model conditions'];

  test('real mesh statistics replace the frozen tree and property literals', function () {
    withProject(project(TWO), function () {
      App.Model.setMeshStats({
        nodes: 146321, elements: 82809, seconds: 5.125,
        by_type: { 'Tetrahedron 10': 82809 }, quality_histogram: {}
      });

      var rows = App.OBJECT_PROPS.mesh.groups.Statistics;
      function value(label) { return rows.filter(function (r) { return r[0] === label; })[0][1]; }
      T.eq(value('Elements'), '82 809');
      T.eq(value('Nodes'), '146 321');
      T.eq(value('Element type'), 'Tetrahedron 10');

      var labels = [];
      (function walk(nodes) {
        (nodes || []).forEach(function (n) { labels.push(n.label); walk(n.children); });
      })(App.TREES.mesh);
      T.ok(labels.indexOf('Elements: 82 809') >= 0);
      T.ok(labels.indexOf('Nodes: 146 321') >= 0);
    });
  });



  /* A staged excavation is more bodies than layers, and each one is separately
     meshed, deactivated and shown -- so each needs its own row in the Model explorer.
     Listing layers alone left the whole excavated side out of the tree. */

  var STAGED = {
    soil_body_keys: ['soil_L1', 'soil_L2', 'soil_L1__lift1', 'soil_L1__lift2'],
    soil_body_labels: {
      soil_L1: 'Soil_1', soil_L2: 'Soil_2',
      soil_L1__lift1: 'Soil_1 · lift 1', soil_L1__lift2: 'Soil_1 · lift 2'
    }
  };

  test('every staged soil body gets its own row in the Model explorer', function () {
    var p = Object.assign(project(TWO), STAGED);
    withProject(p, function () {
      var node = soilNode(App.TREES.soil);
      var objs = (node.children || []).map(function (c) { return c.obj; });
      // Grouped by layer (model.js layerBodies), not in the server's outside-first order.
      T.eq(objs, ['soil_L1', 'soil_L1__lift1', 'soil_L1__lift2', 'soil_L2'],
           'one row per body, each lift right after the layer it was dug out of');
      T.eq(node.count, 4, 'the count is rows, not layers');
      T.ok(/lift 1/.test(node.children[1].label), 'and says which part of the layer');
    });
  });

  test('a lift shows the properties of the layer it was dug out of', function () {
    var p = Object.assign(project(TWO), STAGED);
    withProject(p, function () {
      T.ok(App.OBJECT_PROPS['soil_L1__lift1'], 'a lift has a Selection explorer entry');
      T.eq(App.OBJECT_PROPS['soil_L1__lift1'].title,
           App.OBJECT_PROPS['soil_L1'].title, 'the same one the layer has');
    });
  });

  test('a project that publishes no bodies still lists one row per layer', function () {
    withProject(project(TWO), function () {
      var node = soilNode(App.TREES.soil);
      T.eq((node.children || []).map(function (c) { return c.obj; }),
           ['soil_L1', 'soil_L2']);
    });
  });
})();
