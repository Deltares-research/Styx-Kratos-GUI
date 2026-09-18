/* Rulers along the four edges of a 2D section: the arithmetic that turns the
   camera's visible rectangle into labelled ticks, and the switch that shows them. */

(function () {

  var R = App.Ruler;

  /* ── Step selection ────────────────────────────────────────────── */

  test('a nice step is 1, 2 or 5 times a power of ten', function () {
    T.eq(R.niceStep(1), 1);
    T.eq(R.niceStep(1.1), 2);
    T.eq(R.niceStep(2.5), 5);
    T.eq(R.niceStep(6), 10);
    T.eq(R.niceStep(0.03), 0.05);
    T.eq(R.niceStep(300), 500);
  });

  test('a degenerate step never divides by zero', function () {
    T.ok(R.niceStep(0) > 0, 'zero must still yield a usable step');
    T.ok(R.niceStep(-4) > 0, 'a negative span must still yield a usable step');
  });

  /* ── Ticks ─────────────────────────────────────────────────────── */

  test('ticks land on multiples of the step, inside the range', function () {
    var out = R.ticks(-3, 7, 500, 100);
    T.eq(out.step, 2, '10 m over 500 px, no two ticks closer than 100 px');
    T.eq(out.ticks.map(function (t) { return t.value; }), [-2, 0, 2, 4, 6]);
    T.near(out.ticks[1].pos, 150, 1e-9, '0 m sits 3 m from the left of a 10 m span');
  });

  test('the step coarsens until ticks are at least the minimum spacing apart', function () {
    var out = R.ticks(0, 1000, 400, 80);
    T.ok(out.step / 1000 * 400 >= 80, 'ticks closer than 80 px are unreadable');
    out.ticks.forEach(function (t) {
      T.ok(t.value % out.step === 0, t.value + ' is not a multiple of ' + out.step);
    });
  });

  test('an empty or inverted range yields no ticks rather than an infinite loop', function () {
    T.eq(R.ticks(5, 5, 400, 50).ticks, []);
    T.eq(R.ticks(5, 1, 400, 50).ticks, []);
    T.eq(R.ticks(0, 10, 0, 50).ticks, []);
  });

  /* ── Minor ticks ──────────────────────────────────────────────── */

  test('a major step is subdivided into equal, round minor steps', function () {
    T.eq(R.minorDivisions(1), 5, '1 m in fifths: 0.2 m marks');
    T.eq(R.minorDivisions(2), 4, '2 m in quarters: 0.5 m marks');
    T.eq(R.minorDivisions(5), 5, '5 m in fifths: 1 m marks');
    T.eq(R.minorDivisions(20), 4);
    T.eq(R.minorDivisions(0.5), 5);
  });

  test('minor ticks fall between the major ones and never on top of them', function () {
    var out = R.ticks(0, 10, 1000, 200);
    T.eq(out.step, 2);
    T.eq(out.minorStep, 0.5, '2 m in quarters');
    T.eq(out.minor.map(function (t) { return t.value; }),
         [0.5, 1, 1.5, 2.5, 3, 3.5, 4.5, 5, 5.5, 6.5, 7, 7.5, 8.5, 9, 9.5]);
    var majors = out.ticks.map(function (t) { return t.value; });
    out.minor.forEach(function (t) {
      T.ok(majors.indexOf(t.value) < 0, t.value + ' is already a labelled tick');
    });
  });

  test('a minor tick sits where its world value projects', function () {
    var out = R.ticks(0, 10, 1000, 200);
    T.near(out.minor[0].pos, 50, 1e-9, '0.5 m of a 10 m span across 1000 px');
  });

  test('minor ticks are dropped when they would be closer than the eye resolves', function () {
    var wide = R.ticks(0, 100, 1000, 60);      // 10 m majors, 2 m minors, 20 px apart
    T.ok(wide.minor.length > 0, 'there is room for them here');
    var cramped = R.ticks(0, 100, 400, 20);    // 5 m majors, 1 m minors, 4 px apart
    T.eq(cramped.minor, [], 'a ruler of hairlines says less than a bare one');
  });

  test('an empty range has no minor ticks either', function () {
    T.eq(R.ticks(5, 5, 400, 50).minor, []);
  });

  /* ── Labels ────────────────────────────────────────────────────── */

  test('a label carries just enough decimals for its step', function () {
    T.eq(R.format(12, 5), '12');
    T.eq(R.format(0.5, 0.5), '0.5');
    T.eq(R.format(-0.25, 0.05), '-0.25');
    T.eq(R.format(0, 0.05), '0.00', 'every label on one ruler carries the same decimals');
    T.eq(R.format(-0.0001, 0.05), '0.00', 'a value that rounds to zero is never "-0.00"');
  });

  /* ── Which world axes the screen axes are ──────────────────────── */

  test('the section names the axes its screen edges measure', function () {
    T.eq(R.axesOf(), ['x', 'y'], 'the 2D section: x across, y up');
  });

  /* ── The plan drawn from a camera ──────────────────────────────── */

  function state(over) {
    var s = { center: [10, 4], halfW: 20, halfH: 10,
              width: 800, height: 400, minSpacing: 60 };
    Object.keys(over || {}).forEach(function (k) { s[k] = over[k]; });
    return s;
  }

  test('the visible rectangle becomes the two rulers\' ranges', function () {
    var p = R.plan(state());
    T.eq([p.h.axis, p.v.axis], ['x', 'y']);
    T.eq([p.h.min, p.h.max], [-10, 30], 'centre 10 ± halfW 20');
    T.eq([p.v.min, p.v.max], [-6, 14], 'centre 4 ± halfH 10');
    T.ok(p.h.minor.length && p.v.minor.length, 'both rulers carry their minor ticks');
  });

  test('minor ticks are flipped with the major ones on the vertical ruler', function () {
    var p = R.plan(state({ center: [0, 0], halfW: 10, halfH: 5, width: 400, height: 200 }));
    p.v.minor.forEach(function (t) {
      T.near(t.pos, 100 - t.value / 10 * 200, 1e-9,
             'z ' + t.value + ' must be measured down from the top like the labels');
    });
  });

  test('the horizontal ruler runs left to right and the vertical one top to bottom', function () {
    var p = R.plan(state());
    var first = p.h.ticks[0], last = p.h.ticks[p.h.ticks.length - 1];
    T.ok(first.pos < last.pos && first.value < last.value,
         'x grows to the right, and so does its pixel position');

    var top = p.v.ticks[0], bottom = p.v.ticks[p.v.ticks.length - 1];
    T.ok(top.pos < bottom.pos, 'ticks are listed down the screen');
    T.ok(top.value > bottom.value, 'z grows upward, so the topmost tick is the largest');
  });

  test('a tick sits where its world value projects', function () {
    var p = R.plan(state({ center: [0, 0], halfW: 10, halfH: 5, width: 400, height: 200 }));
    var zero = p.h.ticks.filter(function (t) { return t.value === 0; })[0];
    T.near(zero.pos, 200, 1e-9, 'x = 0 is the middle of a symmetric view');
    var vzero = p.v.ticks.filter(function (t) { return t.value === 0; })[0];
    T.near(vzero.pos, 100, 1e-9, 'z = 0 is the middle of a symmetric view');
  });

  test('both rulers of a square-pixel view share one step', function () {
    var p = R.plan(state({ center: [0, 0], halfW: 20, halfH: 10, width: 800, height: 400 }));
    T.eq(p.h.step, p.v.step, 'equal metres per pixel must not read as two different scales');
  });

  /* ── The switch ────────────────────────────────────────────────── */

  test('the rulers are off in 3D whatever the switch says', function () {
    R.setEnabled(true);
    T.eq(R.visible({ active: false }), false, 'a solid model has no section to measure');
    T.eq(R.visible({ active: true }), true);
    R.setEnabled(false);
    T.eq(R.visible({ active: true }), false, 'switched off is off in 2D too');
    R.setEnabled(true);
  });

  /* ── The DOM it paints into ────────────────────────────────────── */

  test('install builds one canvas per edge and sync leaves them hidden in 3D', function () {
    var host = document.createElement('div');
    host.style.cssText = 'position:absolute;left:-9999px;width:800px;height:400px';
    document.body.appendChild(host);
    try {
      R.install(host);
      var edges = host.querySelectorAll('canvas.vp-ruler');
      T.eq(edges.length, 4, 'top, bottom, left and right');
      T.eq(Array.prototype.map.call(edges, function (c) { return c.dataset.edge; }).sort(),
           ['bottom', 'left', 'right', 'top']);

      R.setEnabled(true);
      var drawn = R.sync({ active: true, center: [0, 0], halfW: 10, halfH: 5,
                           width: 800, height: 400 });
      T.eq(edges[0].hidden, false, 'a 2D section with the switch on shows them');
      T.eq(drawn.h.axis, 'x', 'sync reports the scale it painted');

      R.sync({ active: false });
      T.ok(Array.prototype.every.call(edges, function (c) { return c.hidden; }),
           '3D hides every edge');
    } finally {
      R.uninstall();
      host.remove();
    }
  });

  /* ── Wiring ────────────────────────────────────────────────────── */

  test('the toolbar and the View menu both carry the ruler switch', function () {
    var saved = { action: App.runAction, command: App.Command };
    App.runAction = function () {};
    App.Command = { note: function () {}, ok: function () {}, err: function () {},
                    write: function () {}, run: function () {} };
    try {
      App.LivePatches.install();
      T.ok(App.TOOLBAR.some(function (t) { return t && t.action === 'toggleRuler'; }),
           'no toolbar button for the rulers');
      var view = App.MENUS.filter(function (m) { return m.label === 'View'; })[0];
      T.ok(view.items.some(function (i) { return i && i.action === 'toggleRuler'; }),
           'no View menu item for the rulers');
    } finally {
      App.runAction = saved.action; App.Command = saved.command;
      App.LivePatches.resetForTests();
    }
  });

  test('the ruler switch is a 2D-only action', function () {
    T.eq(App.LivePatches.availableIn3D('toggleRuler'), false,
         'there is nothing to measure on a solid model');
    T.eq(App.LivePatches.availableIn2D('toggleRuler'), true);
  });

})();
