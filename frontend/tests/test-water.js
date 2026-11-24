/* ══════════════════════════════════════════════════════════════════
   test-water.js — the water line.

   `Project.water` is the water level: the level a new hydrostatic condition or normal
   load takes, and the one a normal load saved without its own reads. What the water
   weighs is not the level's but the water's (`Project.fluid.specific_weight`), edited
   under Water properties; the panel shows it read-only. The Selection explorer's
   `water` entry used to be the mockup's three water rows from js/data.js:631, which
   describe a different project.

   See plan/outdated/staged-construction-plan.md sec 7.2, "the GUI follow-on Marjan asked for".
   A *per-stage* phreatic level is a further step and deliberately not here.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  function project(water) {
    return {
      name: 'Water site',
      layered_soil: true,
      dimension: 2,
      domain: { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 },
      materials: [
{ id: 'm2', name: 'Sand', color: '#c4a86a',
          constitutive_law: 'GeoLinearElasticPlaneStrain2DLaw',
          variables: { YOUNG_MODULUS: 2.5e7, POISSON_RATIO: 0.28, DENSITY_SOLID: 1834.86,
                       GEO_COHESION: 500, GEO_FRICTION_ANGLE: 32 } }
      ],
      layers: [{ id: 'L1', name: 'Soil_1', mat: 'm2', top: 0, bottom: -25 }],
      custom_parts: [],
      water: water || { y: -1.5, margin: 3.0, thickness: 0.06 }
    };
  }

  function withProject(p, fn) {
    var saved = { LAYERS: App.LAYERS, MATERIALS: App.MATERIALS, PROJECT: App.PROJECT,
                  props: App.OBJECT_PROPS, trees: {} };
    Object.keys(App.TREES || {}).forEach(function (m) { saved.trees[m] = App.TREES[m]; });
    App.OBJECT_PROPS = Object.assign({}, App.OBJECT_PROPS);
    try {
      App.Model.apply(p);
      return fn();
    } finally {
      App.LAYERS = saved.LAYERS; App.MATERIALS = saved.MATERIALS;
      App.PROJECT = saved.PROJECT;
      App.OBJECT_PROPS = saved.props;
      Object.keys(saved.trees).forEach(function (m) { App.TREES[m] = saved.trees[m]; });
    }
  }

  function rows(group) {
    return App.OBJECT_PROPS.water.groups[group];
  }

  function row(group, label) {
    return rows(group).filter(function (r) { return r[0] === label; })[0];
  }

  /* ── The panel describes this project ─────────────────────────────────── */

  test('the water panel shows the project level, not the mockup rows', function () {
    withProject(project({ y: -4.25, margin: 3, thickness: 0.06 }),
                function () {
      T.eq(row('Geometry', 'Level')[1], '-4.250');
    });
  });

  /* What the water weighs is the water's (`Fluid.specific_weight`), which a project
     without a level has too: shown with the level, edited under Water properties. */
  test('the water panel shows the water\'s specific weight, which the deck will use',
       function () {
    var p = project();
    p.fluid = { specific_weight: 9.81 };
    withProject(p, function () {
      var weight = row('General', 'Specific weight (Water properties)');
      T.eq(weight[1], '9.81');
      T.eq(weight[3], true, 'read only here: it is the water\'s, not the level\'s');
      T.ok(!weight[4], 'no editor on the level');
    });
  });

  /* ── The level is editable, and validated the way the server validates it ── */

  test('the level is editable and the edit is what gets sent', function () {
    withProject(project(), function () {
      var editor = row('Geometry', 'Level')[4];
      T.ok(editor, 'the Level row carries no editor');
      T.eq(editor.set(-6.0), null, 'a level inside the domain was refused');
      T.eq(App.Model.pendingWater().y, -6.0);
    });
  });

  test('a project that leaves the weight to the water shows water\'s own', function () {
    withProject(project(), function () {
      T.eq(row('General', 'Specific weight (Water properties)')[1], '10000');
    });
  });

  test('a level outside the domain is refused', function () {
    withProject(project(), function () {
      var editor = row('Geometry', 'Level')[4];
      T.ok(editor.set(-99) !== null, 'a level below the model was accepted');
      T.ok(editor.set(50) !== null, 'a level above the model was accepted');
      T.eq(App.Model.pendingWater().y, -1.5, 'a rejected level stuck');
    });
  });

  test('a non-numeric level is refused', function () {
    withProject(project(), function () {
      T.ok(row('Geometry', 'Level')[4].set(NaN) !== null);
    });
  });

  /* ── The level survives a reload ──────────────────────────────────────── */

  test('applying a project replaces the pending water wholesale', function () {
    withProject(project({ y: -2, margin: 3, thickness: 0.06 }),
                function () {
      T.eq(App.Model.pendingWater().y, -2);
    });
    withProject(project({ y: -7, margin: 3.5, thickness: 0.06 }), function () {
      T.eq(App.Model.pendingWater().y, -7);
      T.eq(App.Model.pendingWater().margin, 3.5);
    });
  });

  /* ── It has to be reachable ───────────────────────────────────────────
     The rows can exist in App.OBJECT_PROPS and still be unusable: a layered_soil
     project throws away the frozen tree, "Water levels" with it, so there is no row
     to click and the panel never opens. The node is what makes the editor real. */

  /* Top level only, for the reason ensureWaterLevelNode gives: js/data.js:677 has a
     second "Water levels" node inside the Attributes library, listing definitions
     rather than this model's level, and a recursive search would find whichever came
     first and assert against the wrong one. */
  function topNode(nodes, label) {
    return (nodes || []).filter(function (node) {
      return node && node.label === label;
    })[0] || null;
  }

  test('a layered project still has a water level to select', function () {
    withProject(project(), function () {
      var node = topNode(App.TREES.flow, 'Water levels');
      T.ok(node, 'no "Water levels" node in the tree');
      T.eq(node.children.length, 1);
      T.eq(node.children[0].obj, 'water',
           'the row does not point at the water property grid');
    });
  });

  test('the water node is in every mode, like the rest of the live tree', function () {
    withProject(project(), function () {
      ['soil', 'structures', 'mesh', 'flow', 'staged'].forEach(function (mode) {
        T.ok(topNode(App.TREES[mode], 'Water levels'), mode + ' has no water node');
      });
    });
  });

  test('the water row is labelled with the level it is at', function () {
    withProject(project({ y: -3.25, margin: 3, thickness: 0.06 }),
                function () {
      var node = topNode(App.TREES.flow, 'Water levels');
      T.ok(node.children[0].label.indexOf('-3.25') >= 0,
           'the row does not name its level: ' + node.children[0].label);
    });
  });

  /* margin and thickness are how the slab is *drawn* -- a reference plane overhanging
     the domain so the level reads against the model's outside faces -- and are not the
     user's business. They still have to survive the round trip, because the layers
     PATCH replaces the whole water object. */
  test('the drawing fields ride along untouched', function () {
    withProject(project({ y: -3, margin: 4.5, thickness: 0.2 }),
                function () {
      App.Model.pendingWater().y = -3.5;
      T.eq(App.Model.pendingWater().margin, 4.5);
      T.eq(App.Model.pendingWater().thickness, 0.2);
    });
  });

  /* ── A model without one ──────────────────────────────────────────────
     A new project has no water level (core/model/templates.py `blank_project`), and the
     GUI must not invent one: no -1.5 m row, no property grid for a level that is not
     there. `water <level>` is how one is added. */

  function dryProject() {
    var p = project();
    p.water = null;
    return p;
  }

  test('a model with no water level has no water row in any mode', function () {
    withProject(dryProject(), function () {
      ['soil', 'structures', 'mesh', 'flow', 'staged'].forEach(function (mode) {
        T.ok(!topNode(App.TREES[mode], 'Water levels'), mode + ' still shows a water row');
      });
    });
  });

  test('a model with no water level has no water level pending or to edit', function () {
    withProject(dryProject(), function () {
      T.eq(App.Model.pendingWater(), null);
      T.ok(!App.OBJECT_PROPS.water, 'a property grid for a level that does not exist');
    });
  });
})();

/* ══════════════════════════════════════════════════════════════════
   The line in the viewport.

   A `layered_soil` project has no water geometry at all: `Project.part_keys` omits
   "water" on that path, so the thin slab the full build raises is never tessellated
   and the level is invisible. That is the case the blank project opens in and the one
   a staged model script uses, so "invisible" is the normal state rather than the
   exception -- hence a line drawn by the client from the project's own number.

   `waterLineSpec` is pure, and tested here rather than through the scene for the same
   reason `loadGlyphSpec` is: it is the part with the arithmetic in it.
   ══════════════════════════════════════════════════════════════════ */

(function () {
  function project(dimension, y, extra) {
    return Object.assign({
      dimension: dimension,
      domain: { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 },
      water: { y: y, margin: 3.0, thickness: 0.06 }
    }, extra || {});
  }

  test('in plane strain the water line spans the domain at its level', function () {
    var spec = App.Viewport.waterLineSpec(project(2, -4));
    T.eq(spec.points.length, 2);
    T.eq(spec.points[0][1], -4, 'the line is not at the water level');
    T.eq(spec.points[1][1], -4);
    // Both ends overhang by `margin`, which is what the field is for: the level has
    // to read against the model's outside faces rather than stopping at them.
    T.eq(spec.points[0][0], -3);
    T.eq(spec.points[1][0], 53);
  });

  test('the plane-strain line sits on the section plane', function () {
    T.eq(App.Viewport.waterLineSpec(project(2, -4)).points[0][2], 20,
         'the line is not on the middle of the domain');
    T.eq(App.Viewport.waterLineSpec(project(2, -4, { section_offset: 5 })).points[0][2], 5,
         'the line ignores an explicit section offset');
  });

  /* In 3D a single line would be an arbitrary chord through the model. The level is a
     plane there, so its outline is the honest drawing of it. */
  test('in 3D the water level is drawn as a closed outline in plan', function () {
    var spec = App.Viewport.waterLineSpec(project(3, -6));
    T.eq(spec.points.length, 5, 'the outline is not closed');
    T.eq(spec.points[0], spec.points[4], 'the outline does not return to its start');
    spec.points.forEach(function (point) {
      T.eq(point[1], -6, 'a corner is off the water level');
    });
    var xs = spec.points.map(function (p) { return p[0]; });
    var zs = spec.points.map(function (p) { return p[2]; });
    T.eq(Math.min.apply(null, xs), -3);
    T.eq(Math.max.apply(null, xs), 53);
    T.eq(Math.min.apply(null, zs), -3);
    T.eq(Math.max.apply(null, zs), 43);
  });

  test('a project with no water level draws nothing', function () {
    T.eq(App.Viewport.waterLineSpec({ dimension: 2, domain: {} }), null);
    T.eq(App.Viewport.waterLineSpec(null), null);
  });

  /* The group has to be named in a mode or it is built and then never shown --
     the same trap computeModeGroups was written to document for custom parts. */
  test('the water group is shown in the flow and staged modes of a layered project',
       function () {
    var groups = App.Viewport.computeModeGroups(['soil_L1'], [], true);
    T.ok(groups.flow.indexOf('water') >= 0, 'flow mode hides the water line');
    T.ok(groups.staged.indexOf('water') >= 0, 'staged mode hides the water line');
  });

  test('adding the water line did not change the other modes', function () {
    var groups = App.Viewport.computeModeGroups(['soil_L1', 'soil_L2'], [], true);
    T.eq(groups.structures, ['soil_L1', 'soil_L2']);
    T.eq(groups.mesh, ['soil_L1', 'soil_L2', 'mesh']);
    T.eq(groups.soil, ['soil_L1', 'soil_L2', 'water'], 'Soil draws it too, faded');
  });
})();
