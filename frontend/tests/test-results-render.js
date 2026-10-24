/* ══════════════════════════════════════════════════════════════════
   test-results-render.js — turning a field into what gets drawn.

   Everything `App.ResultsRender` does is arithmetic on arrays, which is exactly why it
   is a module of its own: there is no browser on this machine, so the only code that
   gets executed automatically is code with no DOM in it. The three.js calls that
   consume these arrays live in the viewport and are checked by eye; the arithmetic
   that decides what they draw is checked here.

   The cases worth reading first are the ones about holes. A node that no live element
   touches has no value — it is in an excavated body, or in a part this output does not
   write — and the difference between "no value" and "zero" is the difference between a
   grey patch and a blue one that reads as a real result.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var R = App.ResultsRender;

  /* A section as `/stages/{n}/mesh` sends one: four vertices, two triangles. */
  function section() {
    return {
      key: 'results:Soil_Top', part: 'Soil_Top', kind: 'continuum', color: '#b6ac97',
      node_ids: [1, 2, 3, 4],
      positions: [0, 0, 0,  1, 0, 0,  0, 1, 0,  1, 1, 0],
      indices: [0, 1, 2, 1, 3, 2],
      edges: []
    };
  }

  /* A field as `/stages/{n}/field/{name}` sends one. */
  function field(overrides) {
    var base = {
      field: 'uy', label: 'u_y', unit: 'm', location: 'nodes',
      ids: [1, 2, 3, 4], values: [0, -0.5, -1, -0.25], min: -1, max: 0
    };
    Object.keys(overrides || {}).forEach(function (k) { base[k] = overrides[k]; });
    return base;
  }

  /* ── Getting a value onto every vertex ────────────────────────────────── */

  test('a field lands on the vertices its node ids name', function () {
    var out = R.vertexValues(section(), field());
    T.eq(out.values, [0, -0.5, -1, -0.25]);
    T.eq(out.missing, 0);
  });

  test('vertex order follows the section, not the field', function () {
    /* The server sorts a field by node id; a section's vertices are in whatever order
       its elements needed. Zipping the two arrays positionally would look right on a
       section that happens to be sorted and be silently wrong on every other one. */
    var s = section();
    s.node_ids = [4, 3, 2, 1];
    s.positions = [1, 1, 0,  0, 1, 0,  1, 0, 0,  0, 0, 0];

    T.eq(R.vertexValues(s, field()).values, [-0.25, -1, -0.5, 0]);
  });

  test('a vertex the field has no value for is a hole, not a zero', function () {
    /* A node in a body this stage excavated. Zero is a real stress, and a floor of
       them through a pit reads as a result rather than as an absence. */
    var out = R.vertexValues(section(), field({ ids: [1, 2], values: [0, -0.5] }));

    T.eq(out.values[2], null);
    T.eq(out.values[3], null);
    T.eq(out.missing, 2);
  });

  test('an element field is spread to the vertices of its triangles', function () {
    /* Per-element values have no node ids. Triangle 0 is vertices 0,1,2 and triangle 1
       is 1,3,2, so vertex 1 and vertex 2 belong to both and average the two. */
    var s = section();
    s.triangle_elements = [7, 8];
    var out = R.vertexValues(s,
                             field({ location: 'elements', ids: [7, 8], values: [10, 20] }));

    T.eq(out.values, [10, 15, 15, 20]);
  });

  test('a quadratic element owns four triangles, and its value goes on all of them',
       function () {
    /* The case that a positional mapping gets wrong and that no 1:1 fixture can
       catch. One six-node triangle: corners 0,1,2 and mid-sides 3,4,5, split into
       (0,3,5) (3,1,4) (5,4,2) (3,4,5) — four triangles, one element. Read
       positionally, triangles 1..3 would take the values of elements that are
       somewhere else in the mesh entirely. */
    var s = {
      node_ids: [1, 2, 3, 4, 5, 6],
      positions: [0, 0, 0, 2, 0, 0, 0, 2, 0, 1, 0, 0, 1, 1, 0, 0, 1, 0],
      indices: [0, 3, 5, 3, 1, 4, 5, 4, 2, 3, 4, 5],
      triangle_elements: [11, 11, 11, 11],
      edges: [], edge_indices: []
    };

    var out = R.vertexValues(s, field({ location: 'elements',
                                        ids: [11, 12], values: [-100, 999] }));

    T.eq(out.values, [-100, -100, -100, -100, -100, -100]);
    T.eq(out.missing, 0);
  });

  test('two quadratic elements average only where they actually meet', function () {
    var s = {
      node_ids: [1, 2, 3],
      indices: [0, 1, 2,  0, 1, 2,  0, 1, 2,  0, 1, 2,  2, 2, 2],
      triangle_elements: [11, 11, 11, 11, 12],
      positions: [0, 0, 0, 1, 0, 0, 0, 1, 0], edges: [], edge_indices: []
    };

    var out = R.vertexValues(s, field({ location: 'elements',
                                        ids: [11, 12], values: [0, 10] }));

    T.eq(out.values[0], 0, 'vertex 0 is only in element 11');
    // Vertex 2 appears four times in element 11 and three times in element 12.
    T.near(out.values[2], (0 * 4 + 10 * 3) / 7, 1e-9);
  });

  test('without the element provenance nothing is drawn rather than something wrong',
       function () {
    /* An older server, or the 3D skin path, which builds faces from a whole part at
       once and cannot say which element each came from. A plausible-looking smear is
       worse than a visible absence. */
    var s = section();
    delete s.triangle_elements;

    var out = R.vertexValues(s, field({ location: 'elements', ids: [7, 8],
                                        values: [10, 20] }));

    T.eq(out.values, [null, null, null, null]);
    T.eq(out.missing, 4);
  });

  /* ── Colour ───────────────────────────────────────────────────────────── */

  test('a colour buffer is three floats per vertex', function () {
    var colors = R.colors(R.vertexValues(section(), field()), { min: -1, max: 0 });
    T.eq(colors.length, 4 * 3);
    colors.forEach(function (c) { T.ok(c >= 0 && c <= 1, 'channel out of range: ' + c); });
  });

  test('the ends of the range are the ends of the ramp', function () {
    var values = { values: [-1, 0], missing: 0 };
    var low = R.colors(values, { min: -1, max: 0 }).slice(0, 3);
    var high = R.colors(values, { min: -1, max: 0 }).slice(3, 6);

    T.ok(low.join() !== high.join(), 'the two ends must not be the same colour');
  });

  test('a flat field does not divide by zero', function () {
    /* Every value identical — an untouched stage, or a field that is zero everywhere.
       The normaliser is (v - min) / (max - min), and this is the case that makes it
       0/0 and paints the model with NaN. */
    var colors = R.colors({ values: [5, 5, 5], missing: 0 }, { min: 5, max: 5 });

    T.eq(colors.length, 9);
    colors.forEach(function (c) { T.ok(!Number.isNaN(c), 'NaN reached the colour buffer'); });
  });

  test('a value outside the range is clamped rather than wrapped', function () {
    /* What a typed range does: `results range -100 0` with values beyond it. Wrapping
       would paint the largest compression the same colour as the smallest. */
    var inside = R.colors({ values: [0], missing: 0 }, { min: 0, max: 10 });
    var below = R.colors({ values: [-999], missing: 0 }, { min: 0, max: 10 });

    T.eq(below, inside);
  });

  test('a hole takes the absent colour, not an end of the ramp', function () {
    var colors = R.colors({ values: [null], missing: 1 }, { min: 0, max: 1 });
    var grey = R.ABSENT;

    T.eq(Array.prototype.slice.call(colors, 0, 3).map(function (c) {
      return Math.round(c * 255);
    }), grey.map(function (c) { return Math.round(c * 255); }));
  });

  test('bands quantise the ramp without touching the data', function () {
    /* Two values inside one band must come out the same colour, and the values
       themselves must not be rounded — the probe still reports what was computed. */
    var options = { min: 0, max: 1, bands: 4 };
    var a = R.colors({ values: [0.30], missing: 0 }, options);
    var b = R.colors({ values: [0.49], missing: 0 }, options);
    var c = R.colors({ values: [0.60], missing: 0 }, options);

    T.eq(Array.prototype.slice.call(a), Array.prototype.slice.call(b));
    T.ok(a.join() !== c.join(), 'a different band must be a different colour');
  });

  test('smooth shading is the default', function () {
    var options = { min: 0, max: 1 };
    var a = R.colors({ values: [0.30], missing: 0 }, options);
    var b = R.colors({ values: [0.49], missing: 0 }, options);

    T.ok(a.join() !== b.join(), 'without bands, two different values differ');
  });

  test('every named colour map covers the range', function () {
    var names = Object.keys(R.MAPS);
    T.ok(names.length >= 8, 'only ' + names.length + ' maps on offer');

    names.forEach(function (name) {
      for (var i = 0; i <= 10; i++) {
        var rgb = R.sample(name, i / 10);
        T.eq(rgb.length, 3, name);
        rgb.forEach(function (c) {
          T.ok(c >= 0 && c <= 1, name + ' is out of range at '
                                            + (i / 10) + ': ' + c);
        });
      }
      T.ok(R.sample(name, 0).join() !== R.sample(name, 1).join(),
           name + ' has identical ends');
    });
  });

  test('every map is listed with a label a person can read', function () {
    Object.keys(R.MAPS).forEach(function (name) {
      T.ok(R.MAP_LABELS[name], name + ' has no label');
    });
  });

  /* ── Reversing ────────────────────────────────────────────────────────── */

  test('reversing swaps the ends of the ramp', function () {
    var values = { values: [-1, 0], missing: 0 };
    var plain = R.colors(values, { min: -1, max: 0 });
    var flipped = R.colors(values, { min: -1, max: 0, reversed: true });

    T.eq(Array.prototype.slice.call(flipped, 0, 3),
         Array.prototype.slice.call(plain, 3, 6), 'the low end takes the high colour');
    T.eq(Array.prototype.slice.call(flipped, 3, 6),
         Array.prototype.slice.call(plain, 0, 3));
  });

  test('reversing does not touch the values, only the colours', function () {
    /* The probe and the CSV still report what was computed; only the picture flips. */
    var out = R.vertexValues(section(), field());
    R.colors(out, { min: -1, max: 0, reversed: true });

    T.eq(out.values, [0, -0.5, -1, -0.25]);
  });

  test('reversing composes with banding', function () {
    var options = { min: 0, max: 1, bands: 4, reversed: true };
    var low = R.colors({ values: [0.05], missing: 0 }, options);
    var high = R.colors({ values: [0.95], missing: 0 }, options);
    var plainLow = R.colors({ values: [0.05], missing: 0 },
                            { min: 0, max: 1, bands: 4 });

    T.eq(Array.prototype.slice.call(low), Array.prototype.slice.call(
      R.colors({ values: [0.95], missing: 0 }, { min: 0, max: 1, bands: 4 })));
    T.ok(low.join() !== high.join());
    T.ok(low.join() !== plainLow.join(), 'reversed must differ from not reversed');
  });

  test('a hole stays absent however the ramp is arranged', function () {
    var colors = R.colors({ values: [null], missing: 1 },
                          { min: 0, max: 1, reversed: true, bands: 8 });

    T.eq(Array.prototype.slice.call(colors, 0, 3).map(function (c) {
      return Math.round(c * 255);
    }), R.ABSENT.map(function (c) { return Math.round(c * 255); }));
  });

  /* ── The ramp the legend is painted with ──────────────────────────────── */

  test('the ramp has a stop per step and runs low to high', function () {
    var stops = R.ramp({ map: 'viridis', min: 0, max: 1 }, 8);

    T.eq(stops.length, 9);
    T.eq(stops[0].t, 0);
    T.eq(stops[8].t, 1);
    T.eq(stops[0].rgb.join(), R.sample('viridis', 0).join());
    T.eq(stops[8].rgb.join(), R.sample('viridis', 1).join());
  });

  test('the ramp reverses with the colours, so the legend cannot disagree', function () {
    /* The legend is painted from this and the model from `colors`. Two separate
       implementations of the reverse would eventually disagree, and a legend that
       reads backwards against the model is worse than no legend. */
    var plain = R.ramp({ map: 'turbo', min: 0, max: 1 }, 4);
    var flipped = R.ramp({ map: 'turbo', min: 0, max: 1, reversed: true }, 4);

    T.eq(flipped[0].rgb.join(), plain[4].rgb.join());
    T.eq(flipped[4].rgb.join(), plain[0].rgb.join());
  });

  test('the ramp bands when the shading does', function () {
    var stops = R.ramp({ map: 'viridis', min: 0, max: 1, bands: 2 }, 8);
    var distinct = {};
    stops.forEach(function (stop) { distinct[stop.rgb.join()] = true; });

    T.eq(Object.keys(distinct).length, 2, 'two bands is two colours');
  });

  /* ── The legend ───────────────────────────────────────────────────────── */

  test('the legend reads from high at the top to low at the bottom', function () {
    var ticks = R.legend({ min: -100, max: 20, unit: 'kPa' }, 5);

    T.eq(ticks.length, 5);
    T.ok(ticks[0].value > ticks[4].value, 'the top of a legend is the maximum');
    T.eq(ticks[0].value, 20);
    T.eq(ticks[4].value, -100);
  });

  test('legend labels are readable rather than exact', function () {
    var ticks = R.legend({ min: -0.0123456, max: 0.0987654, unit: 'm' }, 3);
    ticks.forEach(function (tick) {
      T.ok(tick.label.length <= 10, 'too long to sit beside a ramp: ' + tick.label);
    });
  });

  test('a flat field still produces a legend', function () {
    var ticks = R.legend({ min: 7, max: 7, unit: 'kPa' }, 3);
    T.eq(ticks.length, 3);
    ticks.forEach(function (tick) { T.eq(tick.value, 7); });
  });

  /* ── Deformation ──────────────────────────────────────────────────────── */

  function displacement() {
    return { ids: [1, 2, 3, 4], location: 'nodes',
             values: [[0, 0, 0], [0, -0.01, 0], [0, -0.02, 0], [0, -0.01, 0]] };
  }

  test('a deformed position is the original plus the scaled displacement', function () {
    var moved = R.deform(section(), displacement(), 10);

    T.eq(Array.prototype.slice.call(moved, 0, 3), [0, 0, 0]);
    // Float32, because that is what a GPU position buffer is; ~7 significant digits
    // is all it carries and all the viewport ever had.
    T.near(moved[4], -0.1, 1e-6, 'vertex 1 starts at y=0 and moves down 10 x 0.01');
    T.near(moved[7], 0.8, 1e-6, 'vertex 2 starts at y=1 and moves down 10 x 0.02');
  });

  test('a factor of zero gives the original mesh back', function () {
    var s = section();
    var moved = R.deform(s, displacement(), 0);

    T.eq(Array.prototype.slice.call(moved), s.positions);
  });

  test('a vertex with no displacement stays where it is', function () {
    var d = displacement();
    d.ids = [1, 2];
    d.values = [[0, 0, 0], [0, -0.01, 0]];

    var moved = R.deform(section(), d, 10);

    T.eq(Array.prototype.slice.call(moved, 6, 12), [0, 1, 0, 1, 1, 0]);
  });

  test('the automatic factor makes the largest movement a readable fraction of the model',
       function () {
    /* A 3 mm settlement on an 80 m model is invisible at true scale, and a factor
       typed by hand is a number nobody knows in advance. "Auto" is what makes the
       first look at a result useful. */
    var factor = R.autoFactor(0.003, [0, -20, 0, 80, 0, 0]);

    T.ok(factor > 1, 'a millimetric settlement has to be exaggerated: ' + factor);
    T.near(0.003 * factor, R.AUTO_FRACTION * 80, 80 * 1e-6);
  });

  test('the automatic factor is 1 when the model has already moved that much',
       function () {
    /* A collapse. Exaggerating it would be misleading, and shrinking it would be
       worse: the rule is a ceiling, not a normalisation. */
    T.eq(R.autoFactor(40, [0, -20, 0, 80, 0, 0]), 1);
  });

  test('a model that has not moved at all gets a factor of 1, not infinity', function () {
    T.eq(R.autoFactor(0, [0, 0, 0, 10, 10, 0]), 1);
  });

  test('a model with no extent gets a factor of 1', function () {
    T.eq(R.autoFactor(0.01, [0, 0, 0, 0, 0, 0]), 1);
  });

  /* ── CSV ──────────────────────────────────────────────────────────────── */

  test('a field exports as csv with a header naming the unit', function () {
    var csv = R.csv(field(), { run: 'r_2026-09-22_00-49', stage: '4_First_excavation' });
    var lines = csv.trim().split('\n');

    T.ok(lines[0].indexOf('node') !== -1, 'the id column is named: ' + lines[0]);
    T.ok(lines[0].indexOf('m') !== -1, 'the unit is in the header: ' + lines[0]);
    T.eq(lines.length, 5, 'a header and one row per value');
    T.eq(lines[1].split(',')[0], '1');
  });

  test('an element field names its id column element', function () {
    var csv = R.csv(field({ location: 'elements' }), {});
    T.ok(csv.split('\n')[0].indexOf('element') !== -1);
  });

  test('csv does not lose precision the viewport never had', function () {
    var csv = R.csv(field({ ids: [1], values: [-0.012345678901], min: -1, max: 0 }), {});
    T.ok(csv.indexOf('-0.0123456789') !== -1, 'got: ' + csv);
  });

  test('a hole exports as an empty cell rather than as a zero', function () {
    var csv = R.csv(field({ ids: [1, 2], values: [1, null] }), {});
    var rows = csv.trim().split('\n');

    T.eq(rows[2], '2,');
  });

  /* ── One whole section, out of a run of the test model ────────────────────

     Everything above is four vertices wide, which is how an edge case should be
     written and is no way to notice that a whole mesh comes out grey.
     `results-field.js` is Soil_Middle_pit in the last stage of a run of the test model
     (tests/make_results_field_fixture.py): p' at the nodes, p' per element and
     the vertical displacement, all as the server sends them. The point of these cases
     is coverage of shape rather than of arithmetic -- that nothing is dropped, nothing
     is null, and nothing lands outside the range the legend is drawn for. */

  var FIELD = window.RESULTS_FIELD;

  test('a real section takes a value on every vertex it draws', function () {
    var vertex = R.vertexValues(FIELD.section, FIELD.fields.p_nodes);

    T.eq(vertex.values.length, FIELD.section.node_ids.length);
    T.eq(vertex.missing, 0, 'holes in a body that is whole in this stage');
  });

  test("a real section's values all lie inside the range the legend is drawn for",
    function () {
      var field = FIELD.fields.p_nodes;
      var vertex = R.vertexValues(FIELD.section, field);
      var outside = vertex.values.filter(function (v) {
        return v < field.min - 1e-9 || v > field.max + 1e-9;
      });

      T.eq(outside.length, 0, 'values outside [min, max]: ' + outside.slice(0, 3));
    });

  test('a per-element field reaches every vertex through triangle_elements',
    function () {
      /* The element ids are not the triangle ids -- a six-node triangle makes four --
         so this is the case that fails if `triangle_elements` is ever dropped from the
         payload or mis-ordered. */
      var vertex = R.vertexValues(FIELD.section, FIELD.fields.p_elements);

      T.eq(vertex.values.length, FIELD.section.node_ids.length);
      T.eq(vertex.missing, 0);
    });

  test('every vertex of a real section gets a colour in range', function () {
    var field = FIELD.fields.uy;
    var vertex = R.vertexValues(FIELD.section, field);
    var rgb = R.colors(vertex, { min: field.min, max: field.max });

    T.eq(rgb.length, vertex.values.length * 3);
    var bad = 0;
    for (var i = 0; i < rgb.length; i++) if (!(rgb[i] >= 0 && rgb[i] <= 1)) bad++;
    T.eq(bad, 0, 'components outside [0, 1]');
  });

  test('the legend of a compression-negative field runs from its top down', function () {
    var field = FIELD.fields.p_nodes;
    var ticks = R.legend({ min: field.min, max: field.max }, 6);

    T.eq(ticks.length, 6);
    T.near(ticks[0].value, field.max, 1e-9, 'the first tick is the top of the ramp');
    T.near(ticks[5].value, field.min, 1e-9);
    /* p is negative in compression, so "the top" is the smallest magnitude. Nothing
       here flips a sign, and this is where that would show up as an upside-down bar. */
    T.ok(ticks[0].value > ticks[5].value);
    T.ok(ticks[0].value < 0);
  });

  test('a real field exports one CSV row per value it carries', function () {
    var field = FIELD.fields.p_nodes;
    var rows = R.csv(field, {}).trim().split("\n");

    T.eq(rows.length, field.ids.length + 1, 'header plus one row per id');
  });

})();
