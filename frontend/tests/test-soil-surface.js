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
    dimension: 2, section_offset: 12.5,
    domain: { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 }
  };

  test('the section is the x-y plane, so those are the two axes the user types', function () {
    T.eq(D.sectionAxes().inPlane, [0, 1]);
    T.eq(D.sectionAxes().normal, 2);
    T.eq(D.sectionAxes().labels, ['x', 'y']);
  });

  test('an outline becomes a prism spanning the whole domain', function () {
    var prism = D.prismFor(project, [[0, 0], [12, 0], [12, 3]]);
    // Placed at the near face of the domain...
    T.eq(prism.vertices, [[0, 0, 0], [12, 0, 0], [12, 3, 0]]);
    // ...and swept the full 40 m out of plane, so any section plane cuts it.
    T.eq(prism.extrusion, [0, 0, 40]);
  });

  test('the prism crosses the section plane wherever the plane sits', function () {
    var prism = D.prismFor(project, [[0, 0], [10, 0], [10, 5]]);
    var z0 = prism.vertices[0][2], z1 = z0 + prism.extrusion[2];
    T.ok(z0 < project.section_offset && project.section_offset < z1,
         'the cut at z = ' + project.section_offset + ' falls inside [' + z0 + ', ' + z1 + ']');
  });

  test('a stored prism reads back as the outline that made it', function () {
    var points = [[0, 0], [3, 3], [9, 3], [12, 0]];
    var prism = D.prismFor(project, points);
    T.eq(D.outlineOf({ vertices: prism.vertices }), points);
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

    var prism = { recipe: { kind: 'polygon_extrude', extrusion: [0, 0, 40] } };
    T.eq(D.formFor(project, prism), 'surface', 'extruded across the plane');

    var alongPlane = { recipe: { kind: 'polygon_extrude', extrusion: [0, 5, 0] } };
    T.eq(D.formFor(project, alongPlane), 'volume', 'not a prism through this plane');

    var skew = { recipe: { kind: 'polygon_extrude', extrusion: [2, 0, 40] } };
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
    var along = { vertices: [[0, 0, 0], [3, 3, 0], [9, 3, 0]], extrusion: [0, 5, 0] };
    T.eq(D.measure(project, along).label, 'Volume');
  });

  /* The window opens on the corners clicked in the viewport, so they have to be
     fit to type over: no 12.3456789, and no corner given twice. */
  test('drawn corners are rounded, and a repeated click is kept once', function () {
    T.eq(D.drawnOutline([[0.00012, 1.23456], [12, 0], [12, 3]]),
         [[0, 1.235], [12, 0], [12, 3]]);
    T.eq(D.drawnOutline([[0, 0], [12, 0], [12, 0], [12, 3]]),
         [[0, 0], [12, 0], [12, 3]], 'a double click');
    T.eq(D.drawnOutline([[0, 0], [12, 0], [12, 3], [0, 0]]),
         [[0, 0], [12, 0], [12, 3]], 'closed on the first corner');
    T.eq(D.drawnOutline([]), []);
  });

  test('the title says which thing is being made', function () {
    T.eq(D.titleFor('surface', false), 'Create soil surface');
    T.eq(D.titleFor('surface', true), 'Edit soil surface');
    T.eq(D.titleFor('volume', false), 'Create soil volume');
    T.eq(D.titleFor('volume', true), 'Edit soil volume');
  });

  /* Right-click > Intersect with offers the other soil surfaces that share ground with
     the one clicked; the server is the one that splits them. */
  function surface(key, label, outline, extra) {
    return Object.assign({ key: key, label: label, mat: 'sand', recipe: {
      kind: 'polygon_extrude', extrusion: [0, 0, 40],
      vertices: outline.map(function (p) { return [p[0], p[1], 0]; }) } }, extra || {});
  }
  function square(x, y, size) {
    return [[x, y], [x + size, y], [x + size, y + size], [x, y + size]];
  }

  test('outlines overlap when they share ground, not when they only touch', function () {
    T.ok(D.outlinesOverlap(square(0, 0, 4), square(2, 2, 4)), 'corners overlap');
    T.ok(D.outlinesOverlap(square(0, 0, 4), square(2, 0, 4)), 'overlap along a shared edge line');
    T.ok(D.outlinesOverlap(square(0, 0, 10), square(4, 4, 2)), 'one wholly inside the other');
    T.ok(D.outlinesOverlap(square(4, 4, 2), square(0, 0, 10)), 'the other way round');
    T.ok(!D.outlinesOverlap(square(0, 0, 4), square(4, 0, 4)), 'side by side');
    T.ok(!D.outlinesOverlap(square(0, 0, 4), square(4, 4, 4)), 'corner to corner');
    T.ok(!D.outlinesOverlap(square(0, 0, 4), square(9, 9, 1)), 'apart');
  });

  test('a soil surface lists the other surfaces it overlaps, and nothing else', function () {
    var p = { custom_parts: [
      surface('drawn_0', 'Sand', square(0, 0, 4)),
      surface('drawn_1', 'Clay', square(2, 2, 4)),
      surface('drawn_2', 'Far', square(20, 20, 2)),
      surface('drawn_3', 'Plain', square(1, 1, 1), { mat: null }),
      { key: 'imported_0', label: 'Step', mat: 'sand', recipe: null }
    ] };
    T.eq(D.overlappingSurfaces(p, 'drawn_0'), [{ key: 'drawn_1', label: 'Clay' }]);
    T.eq(D.overlappingSurfaces(p, 'drawn_0__part2'), [{ key: 'drawn_1', label: 'Clay' }],
         'a piece a line cut off stands for its whole surface');
    T.eq(D.overlappingSurfaces(p, 'drawn_3'), null, 'a part with no material is not soil');
    T.eq(D.overlappingSurfaces(p, 'imported_0'), null);
    T.eq(D.overlappingSurfaces(p, 'drawn_2'), []);
  });
})();
