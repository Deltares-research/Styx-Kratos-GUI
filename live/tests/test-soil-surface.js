/* ══════════════════════════════════════════════════════════════════
   test-soil-surface.js — the 2D face of the soil-body dialog.

   In a plane-strain model there is no third dimension to extrude into: the
   body is an outline in the section plane, and out of plane it is understood
   to run forever. So in 2D the dialog asks for a surface, not a volume.

   What it *sends* is still a polygon_extrude prism, because that is what the
   backend sections. Extruding across the whole domain is the honest encoding
   of "infinite out of plane": every section cuts it, and switching back to 3D
   shows a body that spans the model rather than a mystery slab.
   ══════════════════════════════════════════════════════════════════ */

(function () {
  var D = App.SoilVolumeDialog;
  var project = {
    dimension: 2, section_plane: 'xz', section_offset: 12.5,
    domain: { x0: 0, x1: 50, y0: 0, y1: 40, z_top: 0, z_bottom: -25 }
  };

  test('the section plane decides which two axes the user types', function () {
    T.eq(D.sectionAxes('xz').inPlane, [0, 2]);
    T.eq(D.sectionAxes('xz').normal, 1);
    T.eq(D.sectionAxes('xz').labels, ['x', 'z']);
    T.eq(D.sectionAxes('xy').inPlane, [0, 1]);
    T.eq(D.sectionAxes('xy').normal, 2);
    T.eq(D.sectionAxes('yz').inPlane, [1, 2]);
    T.eq(D.sectionAxes('yz').normal, 0);
  });

  test('an outline becomes a prism spanning the whole domain', function () {
    var prism = D.prismFor(project, [[0, 0], [12, 0], [12, 3]]);
    // Placed at the near face of the domain...
    T.eq(prism.vertices, [[0, 0, 0], [12, 0, 0], [12, 0, 3]]);
    // ...and swept the full 40 m across it, so any section plane cuts it.
    T.eq(prism.extrusion, [0, 40, 0]);
  });

  test('the prism crosses the section plane wherever the plane sits', function () {
    var prism = D.prismFor(project, [[0, 0], [10, 0], [10, 5]]);
    var y0 = prism.vertices[0][1], y1 = y0 + prism.extrusion[1];
    T.ok(y0 < project.section_offset && project.section_offset < y1,
         'the cut at y = ' + project.section_offset + ' falls inside [' + y0 + ', ' + y1 + ']');
  });

  test('a plan section builds its prism along z instead', function () {
    var plan = Object.assign({}, project, { section_plane: 'xy', section_offset: -6 });
    var prism = D.prismFor(plan, [[0, 0], [10, 0], [10, 10]]);
    T.eq(prism.vertices[0], [0, 0, -25]);
    T.eq(prism.extrusion, [0, 0, 25]);
  });

  test('a stored prism reads back as the outline that made it', function () {
    var points = [[0, 0], [3, 3], [9, 3], [12, 0]];
    var prism = D.prismFor(project, points);
    T.eq(D.outlineOf({ vertices: prism.vertices }, 'xz'), points);
  });

  test('area is the shoelace of the outline, not a volume', function () {
    // A 12 x 3 rectangle.
    T.eq(D.areaOf([[0, 0], [12, 0], [12, 3], [0, 3]]), 36);
    // The embankment trapezoid: (12 + 6) / 2 * 3.
    T.eq(D.areaOf([[0, 0], [3, 3], [9, 3], [12, 0]]), 27);
  });

  test('an outline is rejected for the reasons a 2D outline can be wrong', function () {
    T.ok(/three corners/.test(D.validateOutline([[0, 0], [1, 1]])));
    T.ok(/not a number/.test(D.validateOutline([[0, 0], [NaN, 1], [2, 2]])));
    T.ok(/no area/.test(D.validateOutline([[0, 0], [1, 1], [2, 2]])), 'collinear');
    T.eq(D.validateOutline([[0, 0], [12, 0], [12, 3]]), null);
  });

  /* Which form to show is not simply "are we in 2D". A body drawn in 3D whose
     extrusion runs *along* the section plane is not a prism through it; showing
     it as an outline would silently flatten a shape the user did not ask to
     change. Those keep the volume form even in 2D. */
  test('the form follows the body, not only the mode', function () {
    T.eq(D.formFor({ dimension: 3 }, null), 'volume');
    T.eq(D.formFor(project, null), 'surface', 'a new body in 2D is a surface');

    var prism = { recipe: { kind: 'polygon_extrude', extrusion: [0, 40, 0] } };
    T.eq(D.formFor(project, prism), 'surface', 'extruded across the plane');

    var alongPlane = { recipe: { kind: 'polygon_extrude', extrusion: [0, 0, 5] } };
    T.eq(D.formFor(project, alongPlane), 'volume', 'not a prism through this plane');

    var skew = { recipe: { kind: 'polygon_extrude', extrusion: [2, 40, 0] } };
    T.eq(D.formFor(project, skew), 'volume', 'skew to the plane normal');
  });

  /* The explorer and the soil-bodies table both printed m³ off the stored prism.
     For a body the user drew as a surface that is a number they never typed --
     the full-domain sweep -- so it has to report the area it was drawn as. */
  test('a surface is measured as area, a volume as volume', function () {
    var prism = D.prismFor(project, [[0, 0], [3, 3], [9, 3], [12, 0]]);
    var asSurface = D.measure(project, prism);
    T.eq(asSurface.label, 'Area');
    T.eq(asSurface.unit, 'm²');
    T.near(asSurface.value, 27, 1e-9);

    // The same body in a 3D project is a volume again: 27 m² swept 40 m.
    var asVolume = D.measure({ dimension: 3 }, prism);
    T.eq(asVolume.label, 'Volume');
    T.eq(asVolume.unit, 'm³');
    T.near(asVolume.value, 1080, 1e-6);
  });

  test('a body that is not a prism through the plane keeps its volume', function () {
    var along = { vertices: [[0, 0, 0], [3, 0, 3], [9, 0, 3]], extrusion: [0, 0, 5] };
    T.eq(D.measure(project, along).label, 'Volume');
  });

  test('the title says which thing is being made', function () {
    T.eq(D.titleFor('surface', false), 'Create soil surface');
    T.eq(D.titleFor('surface', true), 'Edit soil surface');
    T.eq(D.titleFor('volume', false), 'Create soil volume');
    T.eq(D.titleFor('volume', true), 'Edit soil volume');
  });
})();
