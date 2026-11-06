/* picture-draw.js — the list of shapes a saved picture is written from.

   Small scenes with known answers: a camera that looks straight at the x-y plane maps
   world x, y to the page in a way that can be worked out by hand. */

(function () {
  var D = App.PictureDraw;

  /* World -10..10 by -5..5 fills a 200 x 100 mm page, so 1 world unit is 10 mm. */
  function page() { return D.page(20, 200, 100); }

  function camera() {
    return {
      view: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, -100, 1],
      // Orthographic: x / 10, y / 5, z to -1..1 over view depths -1000 to -1.
      projection: [0.1, 0, 0, 0, 0, 0.2, 0, 0, 0, 0, -0.002, 0, 0, 0, -1.002, 1]
    };
  }

  var IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];

  function faces(positions, extra) {
    return Object.assign({
      kind: 'faces', matrix: IDENTITY, positions: positions, index: null, colors: null,
      color: [0.5, 0.5, 0.5], alpha: 1, transparent: false, depthTest: true, depthWrite: true,
      renderOrder: 0, lit: false, side: 2
    }, extra || {});
  }

  function lines(positions, extra) {
    return Object.assign({
      kind: 'lines', matrix: IDENTITY, positions: positions, index: null, colors: null,
      color: [0, 0, 0], alpha: 1, transparent: false, depthTest: true, renderOrder: 0,
      dash: null
    }, extra || {});
  }

  function view(objects, extra) {
    return Object.assign({ camera: camera(), section: true, objects: objects, lights: [] },
                         extra || {});
  }

  function ofType(list, type) {
    return list.filter(function (p) { return p.t === type; });
  }

  /* Two triangles covering world x -2..2, y -2..2. */
  var SQUARE = [-2, -2, 0, 2, -2, 0, 2, 2, 0, -2, -2, 0, 2, 2, 0, -2, 2, 0];

  /* ── Size and names ─────────────────────────────────────────────────── */

  test('a width in cm becomes pixels at 300 dpi, and the height follows the viewport', function () {
    var size = D.page(16, 1200, 600);
    T.eq(size.widthPx, 1890, '160 mm at 300 dpi');
    T.eq(size.heightPx, 945);
    T.eq(size.widthMm, 160);
    T.eq(size.heightMm, 80);
  });

  test('a file name is made of what the picture shows, safe on every filesystem', function () {
    T.eq(D.fileName(['My pit: A/B', 'stage2', 'First excavation'], 'pdf'),
         'My_pit_A_B_stage2_First_excavation.pdf');
    T.eq(D.fileName(['', 'mesh'], 'png'), 'mesh.png', 'an empty part leaves no stray underscore');
  });

  test('a picture is named after what it shows', function () {
    T.eq(D.pictureParts({ project: 'Pit', mode: 'mesh' }), ['Pit', 'mesh']);
    T.eq(D.pictureParts({ project: 'Pit', mode: 'staged', stage: { index: 2, name: 'Dig' } }),
         ['Pit', 'stage2', 'Dig']);
    T.eq(D.pictureParts({ run: 'Pit_2026', stage: { index: 2, name: 'Dig' }, field: 'uy' }),
         ['Pit_2026', 'stage2', 'uy'], 'as `results csv` names its file');
  });

  /* ── The command ────────────────────────────────────────────────────── */

  test('`picture` alone opens the window, and `picture copy` copies', function () {
    T.eq(D.parseCommand('picture').verb, 'open');
    T.eq(D.parseCommand('picture copy').verb, 'copy');
  });

  test('`picture save` reads formats, width, and what to walk', function () {
    var asked = D.parseCommand('picture save png SVG --width 12.5 --stage all --field all');
    T.eq(asked.verb, 'save');
    T.eq(asked.formats, ['png', 'svg']);
    T.eq(asked.width, 12.5);
    T.eq(asked.stage, 'all');
    T.eq(asked.field, 'all');
  });

  test('`picture save` reads what to leave out and what to add', function () {
    var asked = D.parseCommand('picture save --no-legend --no-rulers --no-axes --grid --csv');
    T.eq(asked.show, { legend: false, rulers: false, axes: false, grid: true });
    T.eq(asked.csv, true);
    T.ok(!asked.screenZoom, 'the whole model, unless asked');
    T.eq(D.parseCommand('picture save --screen-zoom').screenZoom, true);
  });

  test('`--stage` and `--field` take only `all`', function () {
    T.ok(/all/.test(D.parseCommand('picture save --stage 2').error));
    T.ok(/all/.test(D.parseCommand('picture save --field uy').error));
  });

  test('`picture save` with no format means PNG', function () {
    T.eq(D.parseCommand('picture save').formats, ['png']);
  });

  test('a command that cannot be done says why', function () {
    T.ok(/tiff/.test(D.parseCommand('picture save tiff').error));
    T.ok(/width/i.test(D.parseCommand('picture save --width lots').error));
    T.ok(/width/i.test(D.parseCommand('picture save --width 0').error));
    T.ok(/width/i.test(D.parseCommand('picture save --width 500').error));
    T.ok(/print/.test(D.parseCommand('picture print').error));
  });

  test('anything else is not this command', function () {
    T.eq(D.parseCommand('pictures'), null);
    T.eq(D.parseCommand('results csv'), null);
  });

  /* ── Light ──────────────────────────────────────────────────────────── */

  test('a lit face is the sum of the hemisphere and directional lights, clamped', function () {
    var lights = [{ kind: 'hemi', sky: [1, 1, 1], ground: [0, 0, 0], intensity: 0.5, dir: [0, 0, 1] },
                  { kind: 'dir', color: [1, 1, 1], intensity: 0.25, dir: [0, 0, 1] }];
    var rgb = D.shade([0.8, 0.4, 1], [0, 0, 1], lights);
    T.near(rgb[0], 0.6, 1e-9, '0.8 x (0.5 + 0.25)');
    T.near(rgb[1], 0.3, 1e-9);
    T.near(rgb[2], 0.75, 1e-9);
    var over = [{ kind: 'dir', color: [1, 1, 1], intensity: 3, dir: [0, 0, 1] }];
    T.eq(D.shade([0.8, 0.4, 1], [0, 0, 1], over), [1, 1, 1], 'never past white');
  });

  test('a light behind the face gives nothing', function () {
    var behind = [{ kind: 'dir', color: [1, 1, 1], intensity: 1, dir: [0, 0, -1] }];
    T.eq(D.shade([1, 1, 1], [0, 0, 1], behind), [0, 0, 0]);
  });

  /* ── Faces ──────────────────────────────────────────────────────────── */

  test('a flat face in a section is a vector fill, placed in millimetres', function () {
    var list = D.compose(view([faces(SQUARE)]), page());
    var fill = ofType(list, 'fill').slice(1);
    T.eq(fill.length, 1, 'one object of one colour is one fill');
    T.eq(fill[0].tris.length, 12, 'two triangles');
    T.near(fill[0].tris[0], 80, 1e-6, 'world x -2 is 80 mm from the left');
    T.near(fill[0].tris[1], 70, 1e-6, 'world y -2 is 70 mm from the top');
    T.eq(ofType(list, 'image').length, 0, 'no image is needed');
  });

  test('the background comes first, and is white', function () {
    var list = D.compose(view([faces(SQUARE)]), page());
    T.eq(list[0].color, [1, 1, 1]);
    T.eq(list[0].t, 'fill');
  });

  test('a front-only face is dropped when it faces away', function () {
    var back = [-2, -2, 0, -2, 2, 0, 2, 2, 0];
    T.eq(ofType(D.compose(view([faces(back, { side: 0 })]), page()), 'fill').length, 1,
         'only the background');
    T.eq(ofType(D.compose(view([faces(back, { side: 2 })]), page()), 'fill').length, 2,
         'a two-sided face is kept');
  });

  test('a section keeps three.js order: opaque first, then by renderOrder', function () {
    var a = faces(SQUARE, { color: [1, 0, 0], transparent: true, alpha: 0.5 });
    var b = faces(SQUARE, { color: [0, 1, 0], renderOrder: 5 });
    var c = faces(SQUARE, { color: [0, 0, 1] });
    var fills = ofType(D.compose(view([a, b, c]), page()), 'fill').slice(1);
    T.eq(fills.map(function (f) { return f.color; }), [[0, 0, 1], [0, 1, 0], [1, 0, 0]]);
    T.eq(fills[2].alpha, 0.5);
  });

  test('a face pushed back by polygon offset is hidden by another in its plane', function () {
    var soil = faces(SQUARE, { color: [1, 1, 0] });
    var grey = faces(SQUARE, { color: [0.8, 0.8, 0.8], transparent: true, alpha: 0.95, offset: 2 });
    var fills = ofType(D.compose(view([grey, soil]), page()), 'fill').slice(1);
    T.eq(fills.map(function (f) { return f.color; }), [[1, 1, 0]], 'as the mesh sits under the soil');
  });

  test('a pushed-back face still shows where nothing covers it', function () {
    var soil = faces([-2, -2, 0, 2, -2, 0, 2, 2, 0], { color: [1, 1, 0] });
    var grey = faces([-2, -2, 0, 2, 2, 0, -2, 2, 0], { color: [0.8, 0.8, 0.8], offset: 2 });
    T.eq(ofType(D.compose(view([soil, grey]), page()), 'fill').length, 3);
  });

  test('two faces in one plane both show, the later over the earlier', function () {
    var a = faces(SQUARE, { color: [1, 0, 0] });
    var b = faces(SQUARE, { color: [0, 0, 1], transparent: true, alpha: 0.5 });
    T.eq(ofType(D.compose(view([a, b]), page()), 'fill').length, 3);
  });

  test('a face with vertex colours goes in the image, with its colours interpolated', function () {
    var colours = [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0];
    var list = D.compose(view([faces(SQUARE, { colors: colours })]), page());
    T.eq(ofType(list, 'fill').length, 1, 'only the background');
    var image = ofType(list, 'image')[0];
    T.ok(image, 'an image layer');
    T.eq(list.indexOf(image), 1, 'straight above the background');
    T.eq(image.width, page().widthPx);
    var at = function (xMm, yMm) {
      var px = Math.round(xMm * page().pxPerMm), py = Math.round(yMm * page().pxPerMm);
      var i = (py * image.width + px) * 4;
      return [image.rgba[i], image.rgba[i + 1], image.rgba[i + 2], image.rgba[i + 3]];
    };
    T.eq(at(100, 50), [255, 0, 0, 255], 'inside the square');
    T.eq(at(10, 10)[3], 0, 'outside it, transparent');
  });

  test('colours are interpolated between vertices as WebGL does', function () {
    var positions = [-5, -5, 0, 5, -5, 0, 0, 5, 0];
    var colours = [0, 0, 0, 1, 1, 1, 0.5, 0.5, 0.5];
    var image = ofType(D.compose(view([faces(positions, { colors: colours })]), page()), 'image')[0];
    var size = page();
    var px = Math.round(100 * size.pxPerMm), py = Math.round(75 * size.pxPerMm);
    T.near(image.rgba[(py * image.width + px) * 4], 127, 3, 'halfway along the bottom edge');
  });

  test('in 3D the faces go in the image, and the nearer face wins', function () {
    var far = faces(SQUARE, { color: [1, 0, 0] });
    var near = faces(SQUARE.map(function (v, i) { return i % 3 === 2 ? 1 : v; }), { color: [0, 0, 1] });
    var list = D.compose(view([near, far], { section: false }), page());
    T.eq(ofType(list, 'fill').length, 1, 'only the background');
    var image = ofType(list, 'image')[0];
    var i = (Math.round(50 * page().pxPerMm) * image.width + Math.round(100 * page().pxPerMm)) * 4;
    T.eq([image.rgba[i], image.rgba[i + 2]], [0, 255], 'blue is nearer, whatever the order');
  });

  test('a section with too many triangles goes in the image', function () {
    var list = D.compose(view([faces(SQUARE)]), page(), { maxVectorFaces: 1 });
    T.eq(ofType(list, 'fill').length, 1, 'only the background');
    T.eq(ofType(list, 'image').length, 1);
  });

  /* ── Lines ──────────────────────────────────────────────────────────── */

  test('a line segment is placed in millimetres, with a thin line weight', function () {
    var line = ofType(D.compose(view([lines([-5, 0, 0, 5, 0, 0])]), page()), 'line')[0];
    T.near(line.segs[0], 50, 1e-6);
    T.near(line.segs[1], 50, 1e-6);
    T.near(line.segs[2], 150, 1e-6);
    T.eq(line.width, D.LINE_MM);
  });

  test('a line strip joins each point to the next; line segments go in pairs', function () {
    var points = [-5, 0, 0, 0, 0, 0, 5, 0, 0, 5, 3, 0];
    var strip = ofType(D.compose(view([lines(points, { kind: 'strip' })]), page()), 'line')[0];
    T.eq(strip.segs.length, 12, 'three segments');
    var pairs = ofType(D.compose(view([lines(points)]), page()), 'line')[0];
    T.eq(pairs.segs.length, 8, 'two segments');
  });

  test('a line behind a face is hidden where the face covers it, and only there', function () {
    var hiddenLine = lines([-8, 0, -1, 8, 0, -1]);
    var list = D.compose(view([faces(SQUARE), hiddenLine]), page());
    var segs = ofType(list, 'line')[0].segs;
    T.eq(segs.length, 8, 'split into the two pieces outside the square');
    T.near(segs[2], 80, 1, 'the first stops at the left edge of the square');
    T.near(segs[4], 120, 1, 'the second starts at its right edge');
  });

  test('a line in the plane of a face stays visible', function () {
    var list = D.compose(view([faces(SQUARE), lines([-2, 0, 0, 2, 0, 0])]), page());
    T.eq(ofType(list, 'line')[0].segs.length, 4);
  });

  test('a line that ignores depth is drawn over the face', function () {
    var over = lines([-1, 0, -1, 1, 0, -1], { depthTest: false });
    T.eq(ofType(D.compose(view([faces(SQUARE), over]), page()), 'line')[0].segs.length, 4);
  });

  test('a line is cut at the edge of the page', function () {
    var line = ofType(D.compose(view([lines([-50, 0, 0, 5, 0, 0])]), page()), 'line')[0];
    T.near(line.segs[0], 0, 1e-6);
    T.near(line.segs[2], 150, 1e-6);
    T.eq(ofType(D.compose(view([lines([-50, 0, 0, -40, 0, 0])]), page()), 'line').length, 0,
         'all outside: nothing');
  });

  test('a line with vertex colours splits by colour', function () {
    var colours = [1, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1];
    var list = D.compose(view([lines([-5, 0, 0, 0, 0, 0, 0, 1, 0, 5, 1, 0], { colors: colours })]), page());
    T.eq(ofType(list, 'line').map(function (l) { return l.color; }), [[1, 0, 0], [0, 0, 1]]);
  });

  test('a dashed line carries its dash in millimetres', function () {
    var dashed = lines([-5, 0, 0, 5, 0, 0], { kind: 'strip', dash: { size: 1, gap: 0.5 } });
    var line = ofType(D.compose(view([dashed]), page()), 'line')[0];
    T.near(line.dash[0], 10, 1e-6, '1 world unit is 10 mm');
    T.near(line.dash[1], 5, 1e-6);
  });

  test('points become dots, and a hidden point is left out', function () {
    var points = { kind: 'points', matrix: IDENTITY, positions: [0, 0, -1, 8, 0, -1], index: null,
                   colors: null, color: [1, 0, 0], alpha: 1, transparent: false, depthTest: true,
                   renderOrder: 0, size: 4 };
    var dots = ofType(D.compose(view([faces(SQUARE), points]), page()), 'dots')[0];
    T.eq(dots.xy.length, 2, 'the one over the square is hidden');
    T.near(dots.xy[0], 180, 1e-6);
  });

  /* ── Text in the scene ──────────────────────────────────────────────── */

  test('a label in the scene is text at its point, scaled with the world', function () {
    var label = { kind: 'text', matrix: IDENTITY, positions: [1, 2, 0], text: 'h = -1.50 m',
                  scale: 2, fraction: 0.5, fixed: false, color: [0.1, 0.1, 0.1], alpha: 1,
                  transparent: true, depthTest: false, renderOrder: 10, halo: true, bold: true };
    var text = ofType(D.compose(view([label]), page()), 'text')[0];
    T.eq(text.text, 'h = -1.50 m');
    T.near(text.x, 110, 1e-6);
    T.eq(text.anchor, 'middle');
    T.eq(text.halo, [1, 1, 1]);
    // 2 x 0.5 = 1 world unit of em is 10 mm, which is 28.35 pt.
    T.near(text.size, 10 * 72 / 25.4, 1e-6);
  });

  /* ── What goes over the scene ───────────────────────────────────────── */

  function legendPage() { return D.page(20, 200, 100, { legend: true }); }

  var LEGEND = { title: 'Total displacement', unit: 'm', stage: 3,
                 options: { min: 0, max: 2, map: 'rainbow', bands: 0 } };

  function allText(list) {
    return ofType(list, 'text').map(function (t) { return t.text; });
  }

  function xs(values) { return values.filter(function (v, i) { return i % 2 === 0; }); }
  function ys(values) { return values.filter(function (v, i) { return i % 2 === 1; }); }
  function least(values) { return Math.min.apply(null, values); }
  function most(values) { return Math.max.apply(null, values); }

  function legendBox(list) {
    return ofType(list, 'fill').filter(function (f) { return f.legendBox; })[0];
  }

  test('the legend has the unit and the ticks of the screen', function () {
    var words = allText(D.compose(view([], { legend: LEGEND }), legendPage()));
    T.ok(words.indexOf('[m]') >= 0, words.join(' | '));
    App.ResultsRender.legend(LEGEND.options, 7).forEach(function (tick) {
      T.ok(words.indexOf(tick.label) >= 0, 'tick ' + tick.label);
    });
  });

  test('the legend ramp runs from the top of the map to the bottom', function () {
    var steps = ofType(D.compose(view([], { legend: LEGEND }), legendPage()), 'fill')
      .filter(function (f) { return f.ramp; });
    T.ok(steps.length > 20);
    steps.sort(function (a, b) { return a.tris[1] - b.tris[1]; });
    T.eq(steps[0].color, App.ResultsRender.sample('rainbow', 1), 'the maximum is at the top');
  });

  test('the legend has its own column, right of the whole view', function () {
    var size = legendPage();
    T.eq(size.widthMm, 200, 'the page keeps the width asked for');
    var box = legendBox(D.compose(view([faces(SQUARE)], { legend: LEGEND }), size));
    T.ok(least(xs(box.tris)) >= size.scene.x + size.scene.widthMm, 'nothing of it over the view');
    T.ok(most(xs(box.tris)) <= size.widthMm, 'and all of it on the page');
  });

  test('the legend stands low, with its foot level with the foot of the view', function () {
    var size = legendPage();
    var list = D.compose(view([], { legend: LEGEND }), size);
    var steps = ofType(list, 'fill').filter(function (f) { return f.ramp; });
    var foot = size.scene.y + size.scene.heightMm;
    T.near(most(steps.map(function (s) { return most(ys(s.tris)); })), foot, 0.05);
    T.ok(least(ys(legendBox(list).tris)) > size.scene.y + size.scene.heightMm / 2,
         'and all of it in the lower half of a tall view');
  });

  test('the legend is smaller than the view of a report-width picture', function () {
    var size = D.page(16, 100, 50, { legend: true });
    T.ok(D.LEGEND_STRIP_MM <= 26);
    T.ok(size.scene.widthMm > 4 * D.LEGEND_STRIP_MM);
  });

  test('the image layer covers the view and not the column', function () {
    var size = legendPage();
    var colours = [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0];
    var image = ofType(D.compose(view([faces(SQUARE, { colors: colours })], { legend: LEGEND }), size),
                       'image')[0];
    T.eq(image.width, size.scene.widthPx);
    T.eq(image.w, size.scene.widthMm);
    T.ok(size.scene.widthPx < size.widthPx);
  });

  test('with no legend, rulers, title or footer the view has the whole page', function () {
    var size = D.page(20, 200, 100);
    T.eq(size.scene.widthMm, 200);
    T.eq(size.scene.x, 0);
    T.eq(size.heightMm, 100);
  });

  test('a legend on a page with no column for it is left out', function () {
    T.eq(legendBox(D.compose(view([], { legend: LEGEND }), page())), undefined);
  });

  /* ── The rulers ─────────────────────────────────────────────────────── */

  var RULERS = { center: [0, 0], halfW: 10, halfH: 5 };

  test('rulers are drawn for the paper, so their ticks do not crowd', function () {
    var list = D.compose(view([], { rulers: RULERS }), D.page(20, 200, 100, { rulers: true }));
    T.ok(allText(list).indexOf('0') >= 0, 'the origin is labelled');
    T.ok(ofType(list, 'text').filter(function (t) { return t.rotate === -90; }).length > 0,
         'the left ruler reads bottom to top');
  });

  test('there are two rulers, thin ones, outside the view', function () {
    var size = D.page(20, 200, 100, { rulers: true });
    var list = D.compose(view([], { rulers: RULERS }), size);
    var scene = size.scene;
    ofType(list, 'text').forEach(function (t) {
      var inView = t.x > scene.x && t.x < scene.x + scene.widthMm
                && t.y > scene.y && t.y < scene.y + scene.heightMm;
      T.ok(!inView, t.text + ' at ' + t.x + ', ' + t.y);
      T.ok(t.x < scene.x || t.y > scene.y + scene.heightMm, 'left or below: ' + t.text);
      T.ok(t.size <= 6, 'small type');
    });
    T.ok(scene.x <= 6, 'the left ruler takes ' + scene.x + ' mm');
    T.ok(size.heightMm - scene.y - scene.heightMm <= 6);
  });

  test('a fill reaching past the view is covered, so it cannot run under the rulers', function () {
    var size = D.page(20, 200, 100, { rulers: true });
    var big = [-50, -50, 0, 50, -50, 0, 50, 50, 0, -50, -50, 0, 50, 50, 0, -50, 50, 0];
    var list = D.compose(view([faces(big, { color: [1, 0, 0] })], { rulers: RULERS }), size);
    var model = list.findIndex(function (s) { return s.t === 'fill' && s.color[0] === 1 && s.color[1] === 0; });
    var mask = list.findIndex(function (s) { return s.mask; });
    T.ok(mask > model, 'the margins are painted after the scene');
  });

  /* ── The axes ───────────────────────────────────────────────────────── */

  var TRIAD = { axes: [{ name: 'x', dir: [1, 0, 0], color: [1, 0, 0] },
                       { name: 'y', dir: [0, 1, 0], color: [0, 1, 0] }] };

  test('the axis triad shows the axes it is given, in their colours', function () {
    var list = D.compose(view([], { triad: TRIAD }), D.page(20, 200, 100, { footer: true }));
    T.eq(allText(list), ['x', 'y']);
    var arrows = ofType(list, 'line');
    T.eq(arrows.length, 2);
    T.ok(arrows[0].segs[2] > arrows[0].segs[0], 'x points right');
    T.ok(arrows[1].segs[3] < arrows[1].segs[1], 'y points up the page');
  });

  test('the axes are small, and below the view: never on the model', function () {
    var size = D.page(20, 200, 100, { footer: true });
    var list = D.compose(view([], { triad: TRIAD }), size);
    var bottom = size.scene.y + size.scene.heightMm;
    var arrows = ofType(list, 'line');
    arrows.forEach(function (arrow) {
      T.ok(least(ys(arrow.segs)) >= bottom, 'below the view');
      T.ok(most(ys(arrow.segs)) <= size.heightMm, 'and on the page');
      T.ok(most(xs(arrow.segs)) - least(xs(arrow.segs)) <= 4, 'short');
    });
    ofType(list, 'text').forEach(function (t) { T.ok(t.y >= bottom, t.text); });
  });

  /* ── The title and the caption ──────────────────────────────────────── */

  var CAPTION = ['Total displacement', 'Maximum value = 1 m (node 3)', 'Minimum value = 0 m (node 4)'];

  test('the title is above the view, in the middle', function () {
    var size = D.page(20, 200, 100, { title: true });
    var title = ofType(D.compose(view([], { title: 'Stage 2: First excavation' }), size), 'text')[0];
    T.eq(title.text, 'Stage 2: First excavation');
    T.ok(title.y <= size.scene.y);
    T.ok(title.bold);
    T.eq(title.anchor, 'middle');
    T.near(title.x, size.scene.x + size.scene.widthMm / 2, 1e-6);
  });

  test('the caption is below the view, centred under it, one line each', function () {
    var size = D.page(20, 200, 100, { footer: true, caption: true });
    var list = D.compose(view([], { triad: TRIAD, caption: CAPTION }), size);
    var lines = ofType(list, 'text').filter(function (t) { return CAPTION.indexOf(t.text) >= 0; });
    T.eq(lines.map(function (t) { return t.text; }), CAPTION);
    T.eq(lines.map(function (t) { return t.bold; }), [true, false, false], 'the field stands out');
    lines.forEach(function (t, i) {
      T.eq(t.anchor, 'middle');
      T.near(t.x, size.scene.x + size.scene.widthMm / 2, 1e-6);
      T.ok(t.y >= size.scene.y + size.scene.heightMm, 'below the view');
      T.ok(t.y <= size.heightMm, 'and on the page');
      if (i) T.ok(t.y - lines[i - 1].y >= 7 / 72 * 25.4, 'the lines do not touch');
    });
  });

  test('on a narrow picture the caption keeps clear of the axes', function () {
    var size = D.page(6, 100, 100, { footer: true, caption: true });
    var list = D.compose(view([], { triad: TRIAD, caption: CAPTION }), size);
    var line = ofType(list, 'text').filter(function (t) { return t.text === CAPTION[1]; })[0];
    var arrows = ofType(list, 'line');
    T.ok(line.x - D.textWidth(line.text, line.size) / 2 > most(xs(arrows[0].segs)));
  });

  /* ── Cropping to the model ──────────────────────────────────────────── */

  var SCREEN = { width: 200, height: 100 };

  test('the picture is cropped to the model, with white space on each side', function () {
    // SQUARE is 4 by 4 in a view of 20 by 10.
    var picture = D.picture(view([faces(SQUARE, { color: [1, 0, 0] })]), 20, SCREEN);
    var scene = picture.page.scene;
    var fill = ofType(picture.list, 'fill').filter(function (f) { return f.color[1] === 0; })[0];
    var left = least(xs(fill.tris)) - scene.x;
    var right = scene.x + scene.widthMm - most(xs(fill.tris));
    T.near(left, right, 0.1, 'the same each side');
    T.ok(left > 0.05 * scene.widthMm && left < 0.15 * scene.widthMm, left + ' of ' + scene.widthMm);
  });

  test('a flat model has the same white space above and below as beside it', function () {
    var flat = [-5, -1, 0, 5, -1, 0, 5, 1, 0, -5, -1, 0, 5, 1, 0, -5, 1, 0];
    var picture = D.picture(view([faces(flat, { color: [1, 0, 0] })]), 20, SCREEN);
    var scene = picture.page.scene;
    var fill = ofType(picture.list, 'fill').filter(function (f) { return f.color[1] === 0; })[0];
    T.near(least(ys(fill.tris)) - scene.y, least(xs(fill.tris)) - scene.x, 0.1);
  });

  test('a side where the model runs off the screen has no white space', function () {
    var off = [-100, -2, 0, 5, -2, 0, 5, 2, 0, -100, -2, 0, 5, 2, 0, -100, 2, 0];
    var picture = D.picture(view([faces(off, { color: [1, 0, 0] })]), 20, SCREEN);
    var scene = picture.page.scene;
    var fill = ofType(picture.list, 'fill').filter(function (f) { return f.color[1] === 0; })[0];
    T.ok(least(xs(fill.tris)) <= scene.x, 'to the left edge of the view');
    T.ok(most(xs(fill.tris)) < scene.x + scene.widthMm - 1, 'and short of the right edge');
  });

  test('the view takes the shape of the model', function () {
    var picture = D.picture(view([faces(SQUARE)]), 20, SCREEN);
    T.near(picture.page.scene.heightMm / picture.page.scene.widthMm, 1, 0.01);
  });

  test('a tall model stays on a page a report can hold', function () {
    var wall = [-0.5, -5, 0, 0.5, -5, 0, 0.5, 5, 0, -0.5, -5, 0, 0.5, 5, 0, -0.5, 5, 0];
    var picture = D.picture(view([faces(wall)]), 20, SCREEN);
    T.ok(picture.page.scene.heightMm <= 1.3 * picture.page.scene.widthMm);
  });

  test('a flat model keeps room for the legend beside it', function () {
    var dike = [-10, -0.1, 0, 10, -0.1, 0, 10, 0.1, 0, -10, -0.1, 0, 10, 0.1, 0, -10, 0.1, 0];
    var picture = D.picture(view([faces(dike)], { legend: LEGEND }), 20, SCREEN);
    var words = ofType(picture.list, 'text');
    words.forEach(function (t) { T.ok(t.y <= picture.page.heightMm, t.text); });
    T.ok(picture.page.scene.heightMm >= 30);
  });

  test('a view zoomed into the model stays zoomed: what is off screen does not come back', function () {
    var big = [-100, -100, 0, 100, -100, 0, 100, 100, 0, -100, -100, 0, 100, 100, 0, -100, 100, 0];
    var picture = D.picture(view([faces(big)]), 20, SCREEN);
    T.near(picture.page.scene.heightMm / picture.page.scene.widthMm, 0.5, 0.02, 'the screen\'s shape');
  });

  test('a whole box goes past the screen and has white space on each side', function () {
    var off = [-100, -2, 0, 5, -2, 0, 5, 2, 0, -100, -2, 0, 5, 2, 0, -100, 2, 0];
    var seen = view([faces(off, { color: [1, 0, 0] })]);
    var frame = D.drawnBox(seen, SCREEN, true);
    T.near(frame.minX, -10, 1e-9);
    T.eq(frame.whole, true);
    var picture = D.picture(seen, 20, SCREEN, undefined, frame);
    var scene = picture.page.scene;
    var fill = ofType(picture.list, 'fill').filter(function (f) { return f.color[1] === 0; })[0];
    T.ok(least(xs(fill.tris)) > scene.x + 1, 'the far end of the model is in the picture');
    T.ok(most(xs(fill.tris)) < scene.x + scene.widthMm - 1);
  });

  test('zoom and pan do not change a picture with a whole box', function () {
    var model = faces(SQUARE, { color: [1, 0, 0] });
    function seenWith(scale, shift) {
      var eye = camera();
      eye.projection = eye.projection.slice();
      eye.projection[0] *= scale;
      eye.projection[5] *= scale;
      eye.projection[12] = shift;
      return view([model], { camera: eye });
    }
    function pictured(seen) {
      return D.picture(seen, 16, SCREEN, undefined, D.drawnBox(seen, SCREEN, true));
    }
    var first = pictured(seenWith(1, 0));
    [[8, 0], [0.25, 0], [1, 3], [8, -5]].forEach(function (move) {
      var other = pictured(seenWith(move[0], move[1]));
      T.eq(other.page.heightPx, first.page.heightPx, 'zoom ' + move[0] + ', pan ' + move[1]);
      T.eq(other.page.scene.widthPx, first.page.scene.widthPx);
    });
  });

  test('pictures with one frame have one size and the model in one place', function () {
    var soil = faces(SQUARE, { color: [1, 0, 0] });
    var load = lines([0, 2, 0, 0, 4, 0], { color: [0, 0, 1] });
    var bare = view([soil], { title: 'Stage 1: Start', caption: CAPTION });
    var loaded = view([soil, load], { title: 'Stage 2: Load', caption: CAPTION.slice(0, 1) });
    var frame = D.widerBox(D.drawnBox(bare, SCREEN), D.drawnBox(loaded, SCREEN));
    var one = D.picture(bare, 16, SCREEN, undefined, frame);
    var two = D.picture(loaded, 16, SCREEN, undefined, frame);
    T.eq(one.page.heightPx, two.page.heightPx, 'the same height, whatever the caption says');
    T.eq(one.page.scene, two.page.scene);
    function modelOf(picture) {
      return ofType(picture.list, 'fill').filter(function (f) { return f.color[1] === 0; })[0].tris;
    }
    T.eq(modelOf(one), modelOf(two));
    var apart = D.picture(bare, 16, SCREEN);
    T.ok(apart.page.heightPx !== one.page.heightPx, 'with no frame it would differ');
  });

  test('a picture with no title in a shared frame has the size of one with a title', function () {
    var frame = D.drawnBox(view([faces(SQUARE)]), SCREEN);
    var named = D.picture(view([faces(SQUARE)], { title: 'Stage 1: Start' }), 16, SCREEN, undefined, frame);
    var plain = D.picture(view([faces(SQUARE)]), 16, SCREEN, undefined, frame);
    T.eq(plain.page.heightPx, named.page.heightPx);
    T.eq(plain.page.scene, named.page.scene);
  });

  test('the box round two boxes is wider than either, and null is no box', function () {
    var a = { minX: -1, maxX: 0, minY: 0, maxY: 1 }, b = { minX: 0, maxX: 0.5, minY: -0.5, maxY: 0.5 };
    T.eq(D.widerBox(a, b), { minX: -1, maxX: 0.5, minY: -0.5, maxY: 1 });
    T.eq(D.widerBox(null, b), b);
    T.eq(D.widerBox(a, null), a);
    T.eq(D.widerBox(null, null), null);
    T.eq(D.widerBox(Object.assign({ whole: true }, a), Object.assign({ whole: true }, b)).whole, true);
  });

  test('the grid does not stretch the crop', function () {
    var grid = lines([-10, -5, 0, 10, 5, 0], { noFrame: true });
    var picture = D.picture(view([faces(SQUARE), grid]), 20, SCREEN);
    T.near(picture.page.scene.heightMm / picture.page.scene.widthMm, 1, 0.01);
  });

  test('an empty view keeps the framing of the screen', function () {
    var picture = D.picture(view([]), 20, SCREEN);
    T.near(picture.page.scene.heightMm / picture.page.scene.widthMm, 0.5, 1e-9);
  });

  test('the rulers read the cropped view', function () {
    var picture = D.picture(view([faces(SQUARE)], { rulers: RULERS }), 20, SCREEN);
    var words = allText(picture.list);
    T.ok(words.indexOf('2.0') >= 0, 'the edge of the model: ' + words.join(' | '));
    T.ok(words.indexOf('5.0') < 0 && words.indexOf('5') < 0, 'out of the crop: ' + words.join(' | '));
  });

  test('labels are planned for the cropped view', function () {
    var asked = null;
    var picture = D.picture(view([faces(SQUARE)], {
      labelPlanner: function (toView, across, down) {
        asked = { middle: toView(100, 50), across: across, down: down };
        return [];
      }
    }), 20, SCREEN);
    T.ok(asked, 'it was asked');
    T.near(asked.middle.x, asked.across / 2, 1e-6, 'the middle of the screen is the middle of the crop');
    T.near(asked.middle.y, asked.down / 2, 1e-6);
    T.ok(picture.list.length);
  });

  test('the title, the caption and the legend all come along', function () {
    var picture = D.picture(view([faces(SQUARE)], { legend: LEGEND, rulers: RULERS, triad: TRIAD,
                                                    title: 'Stage 1: Dig', caption: CAPTION }),
                            16, SCREEN);
    var words = allText(picture.list);
    T.ok(words.indexOf('Stage 1: Dig') >= 0);
    CAPTION.forEach(function (line) { T.ok(words.indexOf(line) >= 0, line); });
    T.ok(legendBox(picture.list));
    T.eq(picture.page.widthPx, 1890, 'the width asked for');
  });

  test('labels in the view are drawn with their halo and leader', function () {
    var labels = [{ result: { labels: [{ id: 7, x: 10, y: 20, leader: true, ax: 15, ay: 25 }] },
                    style: { text: '#f2f6ff', dot: 'rgba(255, 213, 79, 0.95)',
                             leader: 'rgba(210, 222, 240, 0.55)' },
                    halo: 'rgba(16, 22, 32, 0.85)' }];
    var list = D.compose(view([], { labels: labels }), page());
    T.ok(allText(list).indexOf('7') >= 0);
    T.eq(ofType(list, 'line').length, 1, 'the leader');
    T.eq(ofType(list, 'dots').length, 1, 'the dot on the shared point');
  });

  /* ── Text width ─────────────────────────────────────────────────────── */

  test('text width follows the letters, and the size', function () {
    T.ok(D.textWidth('WWW', 10) > D.textWidth('iii', 10));
    T.near(D.textWidth('A', 20), 2 * D.textWidth('A', 10), 1e-9);
  });

  test('bold letters have their own widths, for every letter of ASCII', function () {
    T.ok(D.textWidth('Stage 7', 10, true) > D.textWidth('Stage 7', 10));
    var ascii = '';
    for (var code = 32; code < 127; code++) ascii += String.fromCharCode(code);
    T.ok(D.textWidth(ascii, 10, true) > 0, 'a letter missing from the table would give NaN');
  });
})();
