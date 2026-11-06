/* ══════════════════════════════════════════════════════════════════
   test-lines.js — the lines that split the soil (js/lines.js).

   What a new line starts as is held to the command line's in test-drafts.js. Which bodies
   the lines make is the server's (tests/test_soil_lines.py).
   ══════════════════════════════════════════════════════════════════ */

(function () {

  function section(lines) {
    return { dimension: 2, lines: lines || [],
             domain: { x0: 0, x1: 20, z0: 0, z1: 10, y_top: 0, y_bottom: -10 } };
  }

  T.test('lines are drawn in the 2D section only', function () {
    T.eq(App.Lines.available(section()), true);
    T.eq(App.Lines.available({ dimension: 3 }), false);
    var error = null;
    try { App.Lines.draft({ dimension: 3, lines: [] }); } catch (e) { error = e; }
    T.ok(error, 'a draft in 3D is refused');
  });

  T.test('a new line takes the first free number', function () {
    T.eq(App.Lines.draft(section()).id, 'line_1');
    T.eq(App.Lines.draft(section()).name, 'Line 1');
    T.eq(App.Lines.draft(section([{ id: 'line_1' }])).id, 'line_2');
  });

  T.test('a line is drawn along the points given', function () {
    T.eq(App.Lines.draft(section(), [[0, -2], [5, -2]]).points, [[0, -2], [5, -2]]);
  });

  T.test('a line with no points runs across the middle of the section', function () {
    T.eq(App.Lines.draft(section()).points, [[0, -5], [20, -5]]);
  });

  T.test('a line needs a name and two different points', function () {
    var line = { id: 'l', name: 'L', points: [[0, 0], [1, 0]] };
    T.eq(App.Lines.validate(line), null);
    T.ok(App.Lines.validate({ id: 'l', name: ' ', points: line.points }));
    T.ok(App.Lines.validate({ id: 'l', name: 'L', points: [[0, 0]] }));
    T.ok(App.Lines.validate({ id: 'l', name: 'L', points: [[0, 0], [0, 0]] }));
    T.ok(App.Lines.validate({ id: 'l', name: 'L', points: [[0, 0], [NaN, 1]] }));
  });

  T.test('a soil body is found by its key', function () {
    var was = App.PROJECT;
    App.PROJECT = { bodies: [{ id: 'part1', name: 'Part 1', layer: 'top' }] };
    try {
      T.eq(App.Lines.bodyOf('soil_top__part1').name, 'Part 1');
      T.eq(App.Lines.bodyOf('soil_top'), undefined);
    } finally {
      App.PROJECT = was;
    }
  });
})();
