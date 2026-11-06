/* ══════════════════════════════════════════════════════════════════
   picture-draw.js — what a saved picture shows, as a list of shapes.

   A picture is not a capture of the canvas. WebGL draws a line one pixel wide at any
   resolution, so at 300 dpi a mesh would print as a faint grey; the legend, the rulers
   and the labels are not in that canvas at all; and a capture cannot become a vector
   file. So the scene is turned into one list of shapes in millimetres, and PNG, SVG and
   PDF are all written from that list (picture-writers.js and picture.js).

   No DOM and no three.js here: `picture.js` hands over plain arrays, and everything that
   decides what is drawn can run under `frontend/tests/run_headless.py`.

   ── The shapes ───────────────────────────────────────────────────────────

     fill    tris [x1, y1, x2, y2, x3, y3, ...], color [r, g, b], alpha
     line    segs [x1, y1, x2, y2, ...], color, alpha, width, dash [on, off] or null
     dots    xy [x, y, ...], r, color, alpha, ring (color) or null
     text    x, y (the baseline), text, size (pt), anchor, color, alpha, bold, rotate,
             halo (color) or null
     image   width, height (pixels), rgba, and x, y, w, h (mm)

   Lengths are millimetres from the top left of the page, colours are 0..1.

   ── Depth ────────────────────────────────────────────────────────────────

   The screen's depth buffer is what keeps the grid behind the soil and a far edge behind
   a near face, so a picture needs one too. Faces are rasterised into `depth`; a line is
   then walked along its length and only the pieces in front are kept.

   Faces with vertex colours (a contour) have no vector form in SVG, so they are drawn
   into the image layer. In 3D all faces go there, where the depth buffer hides them
   exactly as the screen does. Everything else stays vector.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.PictureDraw = (function () {

  var DPI = 300;
  var DEFAULT_WIDTH_CM = 16;     // the text width of an A4 report
  var MAX_WIDTH_CM = 60;         // about A1, and about what a browser's canvas can hold
  var LINE_MM = 0.15;            // a thin drawing line, and sharp at 300 dpi
  /* A report's picture is about the model, so what explains it stays small, and outside
     the view, where it cannot land on the model. */
  var LEGEND_STRIP_MM = 24;
  var RULER_BAND_MM = 4.2;
  var TITLE_BAND_MM = 5;
  var FOOTER_BAND_MM = 7;
  var CAPTION_LINES = 3;         // the field, its maximum and its minimum
  var CAPTION_LINE_MM = 3.4;
  var CAPTION_PAD_MM = 1.5;
  var EDGE_MM = 1.5;
  var RULER_PT = 5.5;
  /* The shapes a view may crop to: as tall as a report's page, and flat enough only where
     no legend needs the room. */
  var TALLEST = 1.25;
  var LOWEST_MM = 12;
  var LOWEST_WITH_LEGEND_MM = 34;
  /* The white space on each side of the model, as a share of half its longest side. */
  var CROP_MARGIN = 0.25;
  var MM_PER_CSS = 25.4 / 96;    // the screen's own sizes, read as a 96 dpi page
  var PT_PER_MM = 72 / 25.4;
  /* A vector file of many thousand triangles opens slowly and gains nothing. */
  var MAX_VECTOR_FACES = 120000;
  /* How far in front of a face a line may be judged "on" it, in the depth buffer's own
     units. In a section the grid is 0.02 m behind the model, which is 7e-6 of these. */
  var DEPTH_BIAS_SECTION = 2e-6;
  var DEPTH_BIAS_3D = 1e-5;
  /* A material's polygonOffset in those units: enough to settle two faces in one plane,
     as it does on screen, and far less than the grid's distance behind the model. */
  var OFFSET_UNIT = 5e-7;
  /* Rounding in the depth buffer's 32-bit floats. Two faces in one plane both pass, and
     the later one wins, as WebGL's LEQUAL has it. */
  var DEPTH_ROUNDING = 1e-7;
  var NEAREST_W = 1e-6;
  var WHITE = [1, 1, 1];
  var FONT_MIDDLE = 0.35;        // from a text's baseline up to its middle, in em

  /* Helvetica's widths for ASCII, in 1/1000 em: all a layout needs to know about a font.
     Arial has the same widths, and that is the font a PNG and an SVG are drawn in. */
  var WIDTHS = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278,
    278, 556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667,
    778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556,
    556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333,
    500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584];
  var WIDTHS_BOLD = [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278,
    278, 556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611,
    975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778, 667,
    778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556, 333, 556,
    611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389,
    556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584];
  var WIDTH_OTHER = 600;

  /* ── Size and names ───────────────────────────────────────────────────── */

  /* The paper the picture is drawn for: the width asked for, with the view in `scene` and,
     around it, a band for each of `parts` {legend, rulers, title, footer, caption}. The height
     follows the view's shape, `shapeWidth` by `shapeHeight`. With no `parts` the view is the
     page. */
  function page(widthCm, shapeWidth, shapeHeight, parts) {
    var widthMm = widthCm * 10;
    var part = parts || {};
    var edge = parts ? EDGE_MM : 0;
    var strip = part.legend ? Math.min(LEGEND_STRIP_MM, widthMm / 3) : 0;
    var left = (part.rulers ? RULER_BAND_MM : 0) + edge;
    var top = part.title ? TITLE_BAND_MM : edge;
    var band = Math.max(part.footer ? FOOTER_BAND_MM : edge,
                        part.caption ? CAPTION_LINES * CAPTION_LINE_MM + CAPTION_PAD_MM : 0);
    var ruled = part.rulers ? RULER_BAND_MM : 0;
    var sceneMm = widthMm - left - edge - strip;
    var sceneHeight = sceneMm * shapeHeight / shapeWidth;
    var widthPx = Math.round(widthMm / 25.4 * DPI);
    var pxPerMm = widthPx / widthMm;
    var heightMm = top + sceneHeight + ruled + band;
    return {
      widthMm: widthMm, heightMm: heightMm, widthPx: widthPx,
      heightPx: Math.round(heightMm * pxPerMm), pxPerMm: pxPerMm, strip: strip, band: band,
      // On whole pixels, so the image layer of a PNG lines up with what is drawn over it.
      scene: { x: Math.round(left * pxPerMm) / pxPerMm, y: Math.round(top * pxPerMm) / pxPerMm,
               widthMm: sceneMm, heightMm: sceneHeight, widthPx: Math.round(sceneMm * pxPerMm),
               heightPx: Math.round(sceneHeight * pxPerMm), pxPerMm: pxPerMm }
    };
  }

  function fileName(parts, extension) {
    var name = parts.map(function (part) {
      return String(part === undefined || part === null ? '' : part)
        .replace(/[^A-Za-z0-9.-]+/g, '_').replace(/^_+|_+$/g, '');
    }).filter(function (part) { return part; }).join('_');
    return (name || 'picture') + '.' + extension;
  }

  /* What a picture is called, from what it shows. A result is named as `results csv`
     names its file, so the two lie side by side in a folder. */
  function pictureParts(shown) {
    if (shown.run) return [shown.run, 'stage' + shown.stage.index, shown.field];
    if (shown.stage) return [shown.project, 'stage' + shown.stage.index, shown.stage.name];
    return [shown.project, shown.mode];
  }

  function textWidth(text, size, bold) {
    var widths = bold ? WIDTHS_BOLD : WIDTHS;
    var total = 0;
    var value = String(text);
    for (var i = 0; i < value.length; i++) {
      var code = value.charCodeAt(i);
      total += code >= 32 && code < 127 ? widths[code - 32] : WIDTH_OTHER;
    }
    return total / 1000 * size / PT_PER_MM;
  }

  /* ── The command ──────────────────────────────────────────────────────── */

  var FORMATS = ['png', 'pdf', 'svg'];

  /* `picture`, `picture copy`, `picture save [png] [pdf] [svg] [--width CM] [--stage all]
     [--field all] [--no-legend] [--no-rulers] [--no-axes] [--grid] [--csv]`. `null` for a
     line that is not this command. */
  function parseCommand(text) {
    var tokens = String(text || '').trim().split(/\s+/);
    if (tokens[0].toLowerCase() !== 'picture') return null;
    var verb = (tokens[1] || '').toLowerCase();
    if (!verb) return { verb: 'open' };
    if (verb === 'copy') return { verb: 'copy', width: DEFAULT_WIDTH_CM, show: {} };
    if (verb !== 'save') {
      return { error: '"picture ' + verb + '" is not a picture command. '
                      + 'Use `picture`, `picture copy` or `picture save`.' };
    }
    var asked = { verb: 'save', formats: [], width: DEFAULT_WIDTH_CM, stage: null, field: null,
                  csv: false, show: {} };
    for (var i = 2; i < tokens.length; i++) {
      var token = tokens[i].toLowerCase();
      if (token === '--width') {
        asked.width = Number(tokens[++i]);
        if (!(asked.width > 0 && asked.width <= MAX_WIDTH_CM)) {
          return { error: 'The width is in cm, more than 0 and at most ' + MAX_WIDTH_CM + '.' };
        }
      } else if (token === '--stage' || token === '--field') {
        if ((tokens[++i] || '').toLowerCase() !== 'all') {
          return { error: token + ' takes `all`. For one ' + token.slice(2)
                          + ', show it on screen first.' };
        }
        asked[token.slice(2)] = 'all';
      } else if (token === '--no-legend' || token === '--no-rulers' || token === '--no-axes') {
        asked.show[token.slice(5)] = false;
      } else if (token === '--grid') {
        asked.show.grid = true;
      } else if (token === '--csv') {
        asked.csv = true;
      } else if (FORMATS.indexOf(token) >= 0) {
        if (asked.formats.indexOf(token) < 0) asked.formats.push(token);
      } else {
        return { error: '"' + tokens[i] + '" is not something a picture can be saved as. '
                        + 'The formats are png, pdf and svg.' };
      }
    }
    if (!asked.formats.length) asked.formats.push('png');
    return asked;
  }

  /* ── Light ────────────────────────────────────────────────────────────── */

  /* three.js r149's Lambert with its default settings: the colour times the hemisphere
     term plus each directional term, in the same space as the hex it was given. */
  function shade(color, normal, lights) {
    var r = 0, g = 0, b = 0;
    lights.forEach(function (light) {
      var dot = normal[0] * light.dir[0] + normal[1] * light.dir[1] + normal[2] * light.dir[2];
      if (light.kind === 'hemi') {
        var w = 0.5 * dot + 0.5;
        r += light.intensity * (light.ground[0] + (light.sky[0] - light.ground[0]) * w);
        g += light.intensity * (light.ground[1] + (light.sky[1] - light.ground[1]) * w);
        b += light.intensity * (light.ground[2] + (light.sky[2] - light.ground[2]) * w);
      } else if (dot > 0) {
        r += light.intensity * light.color[0] * dot;
        g += light.intensity * light.color[1] * dot;
        b += light.intensity * light.color[2] * dot;
      }
    });
    return [Math.min(color[0] * r, 1), Math.min(color[1] * g, 1), Math.min(color[2] * b, 1)];
  }

  /* ── Matrices (column-major, as three.js keeps them) ──────────────────── */

  function multiply(a, b) {
    var out = new Array(16);
    for (var c = 0; c < 4; c++) {
      for (var r = 0; r < 4; r++) {
        out[c * 4 + r] = a[r] * b[c * 4] + a[r + 4] * b[c * 4 + 1]
                       + a[r + 8] * b[c * 4 + 2] + a[r + 12] * b[c * 4 + 3];
      }
    }
    return out;
  }

  /* Every vertex of an object in clip space, for the page. */
  function toClip(object, viewProjection) {
    var m = multiply(viewProjection, object.matrix);
    var p = object.positions;
    var count = p.length / 3;
    var clip = new Float64Array(count * 4);
    for (var i = 0; i < count; i++) {
      var x = p[i * 3], y = p[i * 3 + 1], z = p[i * 3 + 2];
      clip[i * 4] = m[0] * x + m[4] * y + m[8] * z + m[12];
      clip[i * 4 + 1] = m[1] * x + m[5] * y + m[9] * z + m[13];
      clip[i * 4 + 2] = m[2] * x + m[6] * y + m[10] * z + m[14];
      clip[i * 4 + 3] = m[3] * x + m[7] * y + m[11] * z + m[15];
    }
    return clip;
  }

  function colorKey(color) {
    return Math.round(color[0] * 255) + ',' + Math.round(color[1] * 255) + ','
         + Math.round(color[2] * 255);
  }

  /* ── The depth buffer and the image layer ─────────────────────────────── */

  function newBuffer(size) {
    var depth = new Float32Array(size.widthPx * size.heightPx);
    for (var i = 0; i < depth.length; i++) depth[i] = Infinity;
    return { w: size.widthPx, h: size.heightPx, depth: depth, rgba: null, used: false };
  }

  /* One triangle. `paint` is null for depth only, or {a, b, c, alpha} with the colour at
     each corner, 0..1. Colours are linear across the screen, which is what WebGL does in
     a section; in perspective it is a small difference nobody reads a contour by. */
  function rasterise(buffer, ax, ay, az, bx, by, bz, cx, cy, cz, paint, write) {
    var area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax);
    if (area === 0) return;
    var minX = Math.max(0, Math.floor(Math.min(ax, bx, cx)));
    var maxX = Math.min(buffer.w - 1, Math.ceil(Math.max(ax, bx, cx)));
    var minY = Math.max(0, Math.floor(Math.min(ay, by, cy)));
    var maxY = Math.min(buffer.h - 1, Math.ceil(Math.max(ay, by, cy)));
    if (paint && !buffer.rgba) buffer.rgba = new Uint8ClampedArray(buffer.w * buffer.h * 4);

    for (var y = minY; y <= maxY; y++) {
      for (var x = minX; x <= maxX; x++) {
        var px = x + 0.5, py = y + 0.5;
        var u = ((bx - px) * (cy - py) - (by - py) * (cx - px)) / area;
        var v = ((cx - px) * (ay - py) - (cy - py) * (ax - px)) / area;
        var w = 1 - u - v;
        if (u < 0 || v < 0 || w < 0) continue;
        var z = u * az + v * bz + w * cz;
        var at = y * buffer.w + x;
        if (z > buffer.depth[at] + DEPTH_ROUNDING) continue;
        if (write) { buffer.depth[at] = z; buffer.used = true; }
        if (!paint) continue;
        var i = at * 4;
        var alpha = paint.alpha;
        for (var k = 0; k < 3; k++) {
          var value = (u * paint.a[k] + v * paint.b[k] + w * paint.c[k]) * 255;
          buffer.rgba[i + k] = alpha >= 1 || !buffer.rgba[i + 3]
            ? value : value * alpha + buffer.rgba[i + k] * (1 - alpha);
        }
        buffer.rgba[i + 3] = Math.max(buffer.rgba[i + 3], alpha * 255);
      }
    }
  }

  function vertexColor(colors, vertex) {
    return [colors[vertex * 3], colors[vertex * 3 + 1], colors[vertex * 3 + 2]];
  }

  /* The normal of a face, turned to the side the viewer sees. */
  function faceNormal(object, a, b, c, flip) {
    var p = object.positions, m = object.matrix;
    function world(i) {
      var x = p[i * 3], y = p[i * 3 + 1], z = p[i * 3 + 2];
      return [m[0] * x + m[4] * y + m[8] * z, m[1] * x + m[5] * y + m[9] * z,
              m[2] * x + m[6] * y + m[10] * z];
    }
    var pa = world(a), pb = world(b), pc = world(c);
    var ux = pb[0] - pa[0], uy = pb[1] - pa[1], uz = pb[2] - pa[2];
    var vx = pc[0] - pa[0], vy = pc[1] - pa[1], vz = pc[2] - pa[2];
    var nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    var size = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1;
    var sign = flip ? -1 : 1;
    return [sign * nx / size, sign * ny / size, sign * nz / size];
  }

  /* ── Walking the objects ──────────────────────────────────────────────── */

  function vertexCount(object) {
    return object.index ? object.index.length : object.positions.length / 3;
  }

  function vertexAt(object, i) {
    return object.index ? object.index[i] : i;
  }

  /* Calls `visit(a, b, c, back, screen)` for each face the camera can see: the corners,
     whether it faces away, and every vertex in pixels. */
  function eachFace(object, clip, size, visit) {
    var total = vertexCount(object);
    var w = size.widthPx, h = size.heightPx;
    var screen = new Float64Array(clip.length / 4 * 3);
    for (var v = 0; v < clip.length / 4; v++) {
      var cw = clip[v * 4 + 3];
      screen[v * 3] = (clip[v * 4] / cw * 0.5 + 0.5) * w;
      screen[v * 3 + 1] = (-clip[v * 4 + 1] / cw * 0.5 + 0.5) * h;
      screen[v * 3 + 2] = clip[v * 4 + 2] / cw;
    }
    for (var i = 0; i + 2 < total; i += 3) {
      var a = vertexAt(object, i), b = vertexAt(object, i + 1), c = vertexAt(object, i + 2);
      // Behind the eye, where the divide above mirrors a point through the origin.
      if (clip[a * 4 + 3] <= NEAREST_W || clip[b * 4 + 3] <= NEAREST_W
          || clip[c * 4 + 3] <= NEAREST_W) continue;
      var area = (screen[b * 3] - screen[a * 3]) * (screen[c * 3 + 1] - screen[a * 3 + 1])
               - (screen[b * 3 + 1] - screen[a * 3 + 1]) * (screen[c * 3] - screen[a * 3]);
      if (area === 0) continue;
      // The screen's y runs down, so a face towards the viewer has a negative area here.
      var back = area > 0;
      if ((object.side === 0 && back) || (object.side === 1 && !back)) continue;
      visit(a, b, c, back, screen);
    }
  }

  function averageDepth(object, clip) {
    var total = 0, count = clip.length / 4;
    for (var i = 0; i < count; i++) total += clip[i * 4 + 2] / (clip[i * 4 + 3] || 1);
    return count ? total / count : 0;
  }

  /* Far to near within a layer, as three.js sorts its transparent objects. Opaque objects
     come first, whatever their renderOrder. */
  function orderKey(a, b) {
    if (a.transparent !== b.transparent) return a.transparent ? 1 : -1;
    if (a.renderOrder !== b.renderOrder) return a.renderOrder - b.renderOrder;
    if (a.transparent && a.depth !== b.depth) return b.depth - a.depth;
    return a.index - b.index;
  }

  function faceColor(object, a, b, c, back, lights) {
    if (!object.lit) return object.color;
    return shade(object.color, faceNormal(object, a, b, c, back), lights);
  }

  function depthOffset(object) {
    return (object.offset || 0) * OFFSET_UNIT;
  }

  /* Into the image and the depth buffer. */
  function rasteriseObject(buffer, object, clip, size, lights, toImage) {
    var colors = object.colors;
    var write = object.depthWrite !== false && object.depthTest !== false;
    var push = depthOffset(object);
    eachFace(object, clip, size, function (a, b, c, back, s) {
      var paint = null;
      if (toImage) {
        var flat = colors ? null : faceColor(object, a, b, c, back, lights);
        paint = { alpha: object.alpha,
                  a: colors ? vertexColor(colors, a) : flat,
                  b: colors ? vertexColor(colors, b) : flat,
                  c: colors ? vertexColor(colors, c) : flat };
      }
      rasterise(buffer, s[a * 3], s[a * 3 + 1], s[a * 3 + 2] + push, s[b * 3], s[b * 3 + 1],
                s[b * 3 + 2] + push, s[c * 3], s[c * 3 + 1], s[c * 3 + 2] + push, paint, write);
    });
  }

  /* Whether a face shows, judged at its middle against what was drawn before it. */
  function faceShows(buffer, s, a, b, c, push) {
    var x = Math.floor((s[a * 3] + s[b * 3] + s[c * 3]) / 3);
    var y = Math.floor((s[a * 3 + 1] + s[b * 3 + 1] + s[c * 3 + 1]) / 3);
    if (x < 0 || y < 0 || x >= buffer.w || y >= buffer.h) return true;
    var z = (s[a * 3 + 2] + s[b * 3 + 2] + s[c * 3 + 2]) / 3 + push;
    return z <= buffer.depth[y * buffer.w + x] + DEPTH_ROUNDING;
  }

  /* One object's faces as vector fills, one fill per colour: within one path a viewer
     leaves no seam between two triangles. Called before the object writes its own depth,
     so a face behind another in the same plane drops out as it does on screen. */
  function fillsOf(object, clip, buffer, size, lights) {
    var byColor = {};
    var scale = 1 / size.pxPerMm;
    var test = object.depthTest !== false;
    var push = depthOffset(object);
    eachFace(object, clip, size, function (a, b, c, back, s) {
      if (test && !faceShows(buffer, s, a, b, c, push)) return;
      var color = faceColor(object, a, b, c, back, lights);
      var key = colorKey(color);
      if (!byColor[key]) {
        byColor[key] = { t: 'fill', tris: [], color: color, alpha: object.alpha };
      }
      byColor[key].tris.push(s[a * 3] * scale, s[a * 3 + 1] * scale, s[b * 3] * scale,
                             s[b * 3 + 1] * scale, s[c * 3] * scale, s[c * 3 + 1] * scale);
    });
    return Object.keys(byColor).map(function (key) { return byColor[key]; });
  }

  /* The pairs of vertices an object draws as lines. */
  function linePairs(object) {
    var total = vertexCount(object);
    var step = object.kind === 'strip' ? 1 : 2;
    var pairs = [];
    for (var i = 0; i + 1 < total; i += step) {
      pairs.push(vertexAt(object, i), vertexAt(object, i + 1));
    }
    return pairs;
  }

  /* Cut to where w > 0, then to the page (Liang-Barsky). `null` for nothing left. */
  function clipSegment(clip, a, b, size) {
    var ax = clip[a * 4], ay = clip[a * 4 + 1], az = clip[a * 4 + 2], aw = clip[a * 4 + 3];
    var bx = clip[b * 4], by = clip[b * 4 + 1], bz = clip[b * 4 + 2], bw = clip[b * 4 + 3];
    if (aw <= NEAREST_W && bw <= NEAREST_W) return null;
    if (aw <= NEAREST_W || bw <= NEAREST_W) {
      var t = (NEAREST_W - aw) / (bw - aw);
      var x = ax + (bx - ax) * t, y = ay + (by - ay) * t, z = az + (bz - az) * t;
      if (aw <= NEAREST_W) { ax = x; ay = y; az = z; aw = NEAREST_W; }
      else { bx = x; by = y; bz = z; bw = NEAREST_W; }
    }
    var x0 = (ax / aw * 0.5 + 0.5) * size.widthPx, y0 = (-ay / aw * 0.5 + 0.5) * size.heightPx;
    var x1 = (bx / bw * 0.5 + 0.5) * size.widthPx, y1 = (-by / bw * 0.5 + 0.5) * size.heightPx;
    var z0 = az / aw, z1 = bz / bw;
    var dx = x1 - x0, dy = y1 - y0;
    var low = 0, high = 1;
    var checks = [[-dx, x0], [dx, size.widthPx - x0], [-dy, y0], [dy, size.heightPx - y0]];
    for (var i = 0; i < 4; i++) {
      var p = checks[i][0], q = checks[i][1];
      if (p === 0) { if (q < 0) return null; continue; }
      var r = q / p;
      if (p < 0) { if (r > high) return null; if (r > low) low = r; }
      else { if (r < low) return null; if (r < high) high = r; }
    }
    return { x0: x0 + dx * low, y0: y0 + dy * low, z0: z0 + (z1 - z0) * low,
             x1: x0 + dx * high, y1: y0 + dy * high, z1: z0 + (z1 - z0) * high };
  }

  /* The pieces of a segment in front of the depth buffer, in pixels. */
  function visiblePieces(buffer, segment, bias) {
    var dx = segment.x1 - segment.x0, dy = segment.y1 - segment.y0;
    var steps = Math.max(1, Math.ceil(Math.max(Math.abs(dx), Math.abs(dy))));
    var pieces = [];
    var start = null, last = 0;
    for (var i = 0; i <= steps; i++) {
      var t = i / steps;
      var x = Math.min(buffer.w - 1, Math.max(0, Math.floor(segment.x0 + dx * t)));
      var y = Math.min(buffer.h - 1, Math.max(0, Math.floor(segment.y0 + dy * t)));
      var z = segment.z0 + (segment.z1 - segment.z0) * t;
      if (z <= buffer.depth[y * buffer.w + x] + bias) {
        if (start === null) start = t;
        last = t;
      } else if (start !== null) {
        pieces.push(start, last);
        start = null;
      }
    }
    if (start !== null) pieces.push(start, last);
    return pieces;
  }

  function linesOf(object, clip, buffer, size, bias) {
    var pairs = linePairs(object);
    var byColor = {};
    var scale = 1 / size.pxPerMm;
    var hide = object.depthTest !== false && buffer.used;
    var dash = object.dash ? dashOf(object, clip, size) : null;

    for (var i = 0; i < pairs.length; i += 2) {
      var a = pairs[i], b = pairs[i + 1];
      var segment = clipSegment(clip, a, b, size);
      if (!segment) continue;
      var color = object.colors
        ? vertexColor(object.colors, a).map(function (c, k) {
            return (c + object.colors[b * 3 + k]) / 2;
          })
        : object.color;
      var key = colorKey(color);
      if (!byColor[key]) {
        byColor[key] = { t: 'line', segs: [], color: color, alpha: object.alpha,
                         width: LINE_MM, dash: dash };
      }
      var pieces = hide ? visiblePieces(buffer, segment, bias) : [0, 1];
      for (var p = 0; p < pieces.length; p += 2) {
        var dx = segment.x1 - segment.x0, dy = segment.y1 - segment.y0;
        byColor[key].segs.push((segment.x0 + dx * pieces[p]) * scale,
                               (segment.y0 + dy * pieces[p]) * scale,
                               (segment.x0 + dx * pieces[p + 1]) * scale,
                               (segment.y0 + dy * pieces[p + 1]) * scale);
      }
    }
    return Object.keys(byColor).map(function (key) { return byColor[key]; })
      .filter(function (line) { return line.segs.length; });
  }

  /* A dash is set in world units: read how long one world unit is on the page off the
     object's first segment. */
  function dashOf(object, clip, size) {
    var pairs = linePairs(object);
    var a = pairs[0], b = pairs[1];
    var p = object.positions;
    var world = Math.sqrt(Math.pow(p[a * 3] - p[b * 3], 2) + Math.pow(p[a * 3 + 1] - p[b * 3 + 1], 2)
                        + Math.pow(p[a * 3 + 2] - p[b * 3 + 2], 2));
    var segment = world > 0 ? screenLength(clip, a, b, size) : 0;
    var mmPerWorld = world > 0 ? segment / size.pxPerMm / world : 1;
    return [object.dash.size * mmPerWorld, object.dash.gap * mmPerWorld];
  }

  function screenLength(clip, a, b, size) {
    var aw = clip[a * 4 + 3] || 1, bw = clip[b * 4 + 3] || 1;
    var dx = (clip[a * 4] / aw - clip[b * 4] / bw) * 0.5 * size.widthPx;
    var dy = (clip[a * 4 + 1] / aw - clip[b * 4 + 1] / bw) * 0.5 * size.heightPx;
    return Math.sqrt(dx * dx + dy * dy);
  }

  function dotsOf(object, clip, buffer, size, bias) {
    var xy = [];
    var scale = 1 / size.pxPerMm;
    var hide = object.depthTest !== false && buffer.used;
    for (var i = 0; i < clip.length / 4; i++) {
      var w = clip[i * 4 + 3];
      if (w <= NEAREST_W) continue;
      var x = (clip[i * 4] / w * 0.5 + 0.5) * size.widthPx;
      var y = (-clip[i * 4 + 1] / w * 0.5 + 0.5) * size.heightPx;
      if (x < 0 || y < 0 || x >= size.widthPx || y >= size.heightPx) continue;
      if (hide && clip[i * 4 + 2] / w > buffer.depth[Math.floor(y) * buffer.w + Math.floor(x)] + bias) {
        continue;
      }
      xy.push(x * scale, y * scale);
    }
    if (!xy.length) return [];
    return [{ t: 'dots', xy: xy, r: (object.size || 2) / 2 * MM_PER_CSS, color: object.color,
              alpha: object.alpha, ring: null }];
  }

  /* A label in the scene. A sprite keeps its height in world units, or with `fixed` a
     share of the view, and three.js works both out through the projection's y scale. */
  function textOf(object, clip, projection, size) {
    var w = clip[3];
    if (w <= NEAREST_W) return [];
    var x = (clip[0] / w * 0.5 + 0.5) * size.widthMm;
    var y = (-clip[1] / w * 0.5 + 0.5) * size.heightMm;
    var clipHeight = object.scale * object.fraction * projection[5] / (object.fixed ? 1 : w);
    var em = clipHeight * 0.5 * size.heightMm;
    var shapes = [];
    if (object.ring) {
      shapes.push({ t: 'dots', xy: [x, y], r: object.scale * 0.44 * projection[5] * 0.5 * size.heightMm,
                    color: WHITE, alpha: 1, ring: object.ring });
    }
    shapes.push({ t: 'text', x: x, y: y + em * FONT_MIDDLE, text: object.text,
                  size: em * PT_PER_MM, anchor: 'middle', color: object.color,
                  alpha: object.alpha, bold: !!object.bold, rotate: 0,
                  halo: object.halo ? WHITE : null });
    return shapes;
  }

  /* ── The scene ────────────────────────────────────────────────────────── */

  function sceneShapes(view, size, options) {
    var viewProjection = multiply(view.camera.projection, view.camera.view);
    var buffer = newBuffer(size);
    var bias = view.section ? DEPTH_BIAS_SECTION : DEPTH_BIAS_3D;
    var limit = options.maxVectorFaces === undefined ? MAX_VECTOR_FACES : options.maxVectorFaces;
    var lights = view.lights || [];

    var entries = view.objects.map(function (object, index) {
      var clip = toClip(object, viewProjection);
      return { object: object, clip: clip, index: index, renderOrder: object.renderOrder || 0,
               transparent: !!object.transparent, depth: averageDepth(object, clip) };
    });
    var faces = entries.filter(function (entry) { return entry.object.kind === 'faces'; });

    var vectorFaces = 0;
    faces.forEach(function (entry) {
      if (entry.object.depthTest !== false) vectorFaces += vertexCount(entry.object) / 3;
    });
    /* A face that ignores depth is a symbol drawn over everything, and stays vector. */
    function inImage(object) {
      if (object.depthTest === false) return false;
      return !!object.colors || !view.section || vectorFaces > limit;
    }

    // The order three.js draws in: what is opaque writes the depth the rest is tested by.
    faces.slice().sort(orderKey).forEach(function (entry) {
      var toImage = inImage(entry.object);
      if (!toImage) entry.fills = fillsOf(entry.object, entry.clip, buffer, size, lights);
      if (entry.object.depthTest === false) return;
      rasteriseObject(buffer, entry.object, entry.clip, size, lights, toImage);
    });

    var shapes = [];
    entries.slice().sort(orderKey).forEach(function (entry) {
      var object = entry.object;
      var made = [];
      if (object.kind === 'faces') {
        made = entry.fills || [];
      } else if (object.kind === 'lines' || object.kind === 'strip') {
        made = linesOf(object, entry.clip, buffer, size, bias);
      } else if (object.kind === 'points') {
        made = dotsOf(object, entry.clip, buffer, size, bias);
      } else if (object.kind === 'text') {
        made = textOf(object, entry.clip, view.camera.projection, size);
      }
      shapes.push.apply(shapes, made);
    });

    var image = buffer.rgba
      ? [{ t: 'image', width: buffer.w, height: buffer.h, x: 0, y: 0, w: size.widthMm,
           h: size.heightMm, rgba: buffer.rgba }] : [];
    return image.concat(shapes);
  }

  /* ── What goes over the scene ─────────────────────────────────────────── */

  function rect(x, y, w, h, color, alpha) {
    return { t: 'fill', tris: [x, y, x + w, y, x + w, y + h, x, y, x + w, y + h, x, y + h],
             color: color, alpha: alpha === undefined ? 1 : alpha };
  }

  function hex(value) {
    return [parseInt(value.slice(1, 3), 16) / 255, parseInt(value.slice(3, 5), 16) / 255,
            parseInt(value.slice(5, 7), 16) / 255];
  }

  /* `rgba(r, g, b, a)` as the mesh labels write their colours, or `#rrggbb`. */
  function cssColor(value) {
    var parts = /rgba\(([^,]+),([^,]+),([^,]+),([^)]+)\)/.exec(value);
    if (!parts) return { color: hex(value), alpha: 1 };
    return { color: [Number(parts[1]) / 255, Number(parts[2]) / 255, Number(parts[3]) / 255],
             alpha: Number(parts[4]) };
  }

  function label(text, x, middleY, size, color, extra) {
    return Object.assign({ t: 'text', x: x, y: middleY + size / PT_PER_MM * FONT_MIDDLE,
                           text: text, size: size, anchor: 'start', color: color, alpha: 1,
                           bold: false, rotate: 0, halo: null }, extra || {});
  }

  /* The legend, in its own column, with its foot level with the foot of the view. Only the
     unit stands over it: the caption says which field this is. */
  function legendShapes(legend, size) {
    var smallPt = 6;
    var ink = hex('#222222'), soft = hex('#5b6673');
    var pad = 1.2;
    var left = size.scene.x + size.scene.widthMm + pad + 0.8;
    var head = smallPt / PT_PER_MM * 1.5;
    var rampHeight = Math.max(10, Math.min(30, size.scene.heightMm - head - pad));
    var rampTop = size.scene.y + size.scene.heightMm - rampHeight;
    var top = rampTop - pad - head;
    var box = rect(left - pad, top, size.widthMm - left + pad, head + pad + rampHeight, WHITE);
    box.legendBox = true;
    var shapes = [box];

    if (legend.unit) {
      shapes.push(label('[' + legend.unit + ']', left, top + head / 2, smallPt, soft));
    }

    var rampWidth = 3;
    var steps = App.ResultsRender.ramp(legend.options, 64);
    for (var i = 0; i + 1 < steps.length; i++) {
      // The stops run low to high, and the maximum is at the top. A hair of overlap, so a
      // viewer leaves no white line between two steps.
      var y = rampTop + (1 - steps[i + 1].t) * rampHeight;
      var step = rect(left, y, rampWidth, (steps[i + 1].t - steps[i].t) * rampHeight + 0.02,
                      steps[i + 1].rgb);
      step.ramp = true;
      shapes.push(step);
    }
    App.ResultsRender.legend(legend.options, 7).forEach(function (tick) {
      shapes.push(label(tick.label, left + rampWidth + 1, rampTop + (1 - tick.t) * rampHeight,
                        smallPt, ink));
    });
    return shapes;
  }

  /* The ruler's own plan, run for the size of the view: a tick spacing chosen for a wide
     screen would crowd on a report's text width. A thin frame round the view, with a scale
     on its left and bottom, as a plot has: in the view's own millimetres. */
  function rulerShapes(rulers, size) {
    var css = MM_PER_CSS;
    var w = size.widthMm, h = size.heightMm;
    var layout = App.Ruler.plan({ center: rulers.center, halfW: rulers.halfW, halfH: rulers.halfH,
                                  width: w / css, height: h / css, minSpacing: 48 });
    var shapes = [];
    var ink = hex('#41505f'), tickInk = hex('#7b8794'), minorInk = hex('#aab4c0'), edge = hex('#b8c2ce');
    var em = RULER_PT / PT_PER_MM;
    var longTick = 0.8, shortTick = 0.4, gap = 0.3;
    var room = 1;

    function segments(list, color) {
      if (!list.length) return;
      shapes.push({ t: 'line', segs: list, color: color, alpha: 1, width: LINE_MM, dash: null });
    }

    segments([0, 0, w, 0, w, 0, w, h, w, h, 0, h, 0, h, 0, 0], edge);

    var minor = [], major = [];
    (layout.h.minor || []).forEach(function (tick) {
      minor.push(tick.pos * css, h, tick.pos * css, h + shortTick);
    });
    (layout.v.minor || []).forEach(function (tick) {
      minor.push(0, tick.pos * css, -shortTick, tick.pos * css);
    });
    layout.h.ticks.forEach(function (tick) {
      var x = tick.pos * css;
      if (x < room || x > w - room) return;
      major.push(x, h, x, h + longTick);
      shapes.push(label(App.Ruler.format(tick.value, layout.h.step), x, h + longTick + gap + em / 2,
                        RULER_PT, ink, { anchor: 'middle' }));
    });
    layout.v.ticks.forEach(function (tick) {
      var y = tick.pos * css;
      if (y < room || y > h - room) return;
      major.push(0, y, -longTick, y);
      // Read bottom to top; the baseline is off the column's middle, to the right.
      shapes.push(label(App.Ruler.format(tick.value, layout.v.step),
                        -longTick - gap - em / 2 + em * FONT_MIDDLE, y - em * FONT_MIDDLE,
                        RULER_PT, ink, { anchor: 'middle', rotate: -90 }));
    });
    segments(minor, minorInk);
    segments(major, tickInk);
    return shapes;
  }

  /* The axes, small, in the band below the view, with their left end at `left`. As `buildTriad`
     draws them, turned as the camera is turned. `right` is where they end. */
  function triadShapes(triad, camera, left, middle) {
    var length = 2.6, head = 0.75, side = 0.3, past = 0.8;
    var v = camera.view;
    var arrows = triad.axes.map(function (axis) {
      var d = axis.dir;
      var dx = v[0] * d[0] + v[4] * d[1] + v[8] * d[2];
      var dy = -(v[1] * d[0] + v[5] * d[1] + v[9] * d[2]);
      return { name: axis.name, color: axis.color, dx: dx, dy: dy,
               size: Math.sqrt(dx * dx + dy * dy) };
    });
    // Where the ends land, so the whole triad can be placed in the band.
    var minX = 0, maxX = 0, minY = 0, maxY = 0;
    arrows.forEach(function (arrow) {
      var x = arrow.dx * (length + past), y = arrow.dy * (length + past);
      minX = Math.min(minX, x); maxX = Math.max(maxX, x);
      minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    });
    var ox = left - minX + 0.6;
    var oy = middle - (minY + maxY) / 2;

    var shapes = [];
    arrows.forEach(function (arrow) {
      var tipX = ox + arrow.dx * length, tipY = oy + arrow.dy * length;
      if (arrow.size > 0.05) {
        var ux = arrow.dx / arrow.size, uy = arrow.dy / arrow.size;
        var baseX = tipX - ux * head, baseY = tipY - uy * head;
        shapes.push({ t: 'line', segs: [ox, oy, baseX, baseY], color: arrow.color, alpha: 1,
                      width: LINE_MM * 1.5, dash: null });
        shapes.push({ t: 'fill', color: arrow.color, alpha: 1,
                      tris: [tipX, tipY, baseX - uy * side, baseY + ux * side,
                             baseX + uy * side, baseY - ux * side] });
      }
      shapes.push(label(arrow.name, ox + arrow.dx * (length + past), oy + arrow.dy * (length + past),
                        4.5, hex('#1d2430'), { anchor: 'middle', bold: true }));
    });
    return { shapes: shapes, right: ox + maxX + 0.6 };
  }

  /* `labels` are `App.MeshLabels` plans for the paper, in CSS pixels. */
  function labelShapes(labels) {
    var css = MM_PER_CSS;
    var shapes = [];
    labels.forEach(function (layer) {
      var leader = cssColor(layer.style.leader), dot = cssColor(layer.style.dot);
      var text = cssColor(layer.style.text), halo = cssColor(layer.halo);
      var segs = [], dots = [];
      layer.result.labels.forEach(function (item) {
        if (!item.leader) return;
        segs.push(item.ax * css, item.ay * css, item.x * css, item.y * css);
        dots.push(item.ax * css, item.ay * css);
      });
      if (segs.length) {
        shapes.push({ t: 'line', segs: segs, color: leader.color, alpha: leader.alpha,
                      width: LINE_MM, dash: null });
        shapes.push({ t: 'dots', xy: dots, r: 1.8 * css, color: dot.color, alpha: dot.alpha, ring: null });
      }
      layer.result.labels.forEach(function (item) {
        shapes.push(label(String(item.id), item.x * css, item.y * css, 11 * 0.75, text.color,
                          { anchor: 'middle', halo: halo.color }));
      });
    });
    return shapes;
  }

  /* ── The whole picture ────────────────────────────────────────────────── */

  /* Moves shapes drawn in the view's millimetres to their place on the page. */
  function shifted(shapes, dx, dy) {
    function move(values) {
      return values.map(function (value, i) { return value + (i % 2 ? dy : dx); });
    }
    return shapes.map(function (shape) {
      if (shape.t === 'fill') return Object.assign({}, shape, { tris: move(shape.tris) });
      if (shape.t === 'line') return Object.assign({}, shape, { segs: move(shape.segs) });
      if (shape.t === 'dots') return Object.assign({}, shape, { xy: move(shape.xy) });
      return Object.assign({}, shape, { x: shape.x + dx, y: shape.y + dy });
    });
  }

  /* White over everything round the view: a fill of a model zoomed in on reaches past it. */
  function margins(size) {
    var s = size.scene;
    var rows = [[0, 0, size.widthMm, s.y], [0, s.y + s.heightMm, size.widthMm, size.heightMm - s.y - s.heightMm],
                [0, 0, s.x, size.heightMm], [s.x + s.widthMm, 0, size.widthMm - s.x - s.widthMm, size.heightMm]];
    return rows.filter(function (r) { return r[2] > 0 && r[3] > 0; }).map(function (r) {
      var mask = rect(r[0], r[1], r[2], r[3], WHITE);
      mask.mask = true;
      return mask;
    });
  }

  /* The lines below the view, centred under it, the first one bold: as far right as the axes
     need, on a picture so narrow that they would meet. */
  function captionShapes(caption, size, clearOf) {
    var middle = size.scene.x + size.scene.widthMm / 2;
    var widest = Math.max.apply(null, caption.map(function (line) { return textWidth(line, 7.5, true); }));
    middle = Math.max(middle, clearOf + widest / 2);
    var top = size.heightMm - size.band + CAPTION_PAD_MM / 2;
    return caption.map(function (line, i) {
      return label(line, middle, top + CAPTION_LINE_MM * (i + 0.5), i ? 7 : 7.5, hex('#222222'),
                   { anchor: 'middle', bold: !i });
    });
  }

  /* `view`: {camera: {view, projection}, section, objects, lights}, and optionally rulers,
     triad, legend, labels, title and caption. Only what is there is drawn, so what the window
     leaves out is left out of `view`. */
  function compose(view, size, options) {
    var settings = options || {};
    var scene = size.scene;
    var list = [rect(0, 0, size.widthMm, size.heightMm, view.background || WHITE)];

    var inView = sceneShapes(view, scene, settings);
    if (view.labels && view.labels.length) inView = inView.concat(labelShapes(view.labels));
    list = list.concat(shifted(inView, scene.x, scene.y));
    list = list.concat(margins(size));
    if (view.rulers) list = list.concat(shifted(rulerShapes(view.rulers, scene), scene.x, scene.y));

    if (view.title) {
      list.push(label(view.title, scene.x + scene.widthMm / 2, scene.y / 2 + 0.2, 7.5,
                      hex('#222222'), { anchor: 'middle', bold: true }));
    }
    var clearOf = 0;
    if (view.triad) {
      var triad = triadShapes(view.triad, view.camera, EDGE_MM, size.heightMm - size.band / 2);
      list = list.concat(triad.shapes);
      clearOf = triad.right + 2;
    }
    if (view.caption) list = list.concat(captionShapes(view.caption, size, clearOf));
    if (view.legend && size.strip) list = list.concat(legendShapes(view.legend, size));
    return list;
  }

  /* The part of the view that holds something to draw, in clip space: a box round what is
     drawn, cut to the screen. `null` for nothing. */
  function drawnBox(view, screen) {
    var viewProjection = multiply(view.camera.projection, view.camera.view);
    var box = null;
    function take(x, y) {
      var cx = Math.max(-1, Math.min(1, x)), cy = Math.max(-1, Math.min(1, y));
      if (!box) box = { minX: cx, maxX: cx, minY: cy, maxY: cy };
      box.minX = Math.min(box.minX, cx); box.maxX = Math.max(box.maxX, cx);
      box.minY = Math.min(box.minY, cy); box.maxY = Math.max(box.maxY, cy);
    }
    view.objects.forEach(function (object) {
      if (object.noFrame) return;
      var clip = toClip(object, viewProjection);
      for (var i = 0; i < clip.length / 4; i++) {
        var w = clip[i * 4 + 3];
        if (w <= NEAREST_W) continue;
        var x = clip[i * 4] / w, y = clip[i * 4 + 1] / w;
        if (object.kind !== 'text') { take(x, y); continue; }
        // A label reaches half its length to each side of its point.
        var em = object.scale * object.fraction * view.camera.projection[5] / (object.fixed ? 1 : w);
        var half = textWidth(object.text, PT_PER_MM) * em / 2 * screen.height / screen.width;
        take(x - half, y - em / 2);
        take(x + half, y + em / 2);
      }
    });
    return box;
  }

  /* The box round two boxes, either of which can be `null`. */
  function widerBox(a, b) {
    if (!a || !b) return a || b;
    return { minX: Math.min(a.minX, b.minX), maxX: Math.max(a.maxX, b.maxX),
             minY: Math.min(a.minY, b.minY), maxY: Math.max(a.maxY, b.maxY) };
  }

  /* The view cropped to `frame`, or to what it draws, with white space round it, on a page with
     room for what goes round the view. A `frame` is a `drawnBox` that pictures share, so they
     come out the same size with the model in the same place. A side where the model runs off
     the screen has no space: a view zoomed in on stays zoomed in on. The camera is left alone:
     the crop is one more matrix after its projection. */
  function framed(view, widthCm, screen, frame) {
    var parts = { legend: !!view.legend, rulers: !!view.rulers, title: !!view.title,
                  footer: !!view.triad, caption: !!view.caption };
    var sceneMm = page(widthCm, 1, 1, parts).scene.widthMm;
    var lowest = (view.legend ? LOWEST_WITH_LEGEND_MM : LOWEST_MM) / sceneMm;
    var box = frame || drawnBox(view, screen);
    var cx = 0, cy = 0, hx = 1, hy = 1;
    if (box && box.maxX >= box.minX && box.maxY >= box.minY
        && (box.maxX > box.minX || box.maxY > box.minY)) {
      // Half the box, in screen pixels: the units in which the two sides can be compared.
      var space = CROP_MARGIN * Math.max((box.maxX - box.minX) / 2 * screen.width,
                                         (box.maxY - box.minY) / 2 * screen.height);
      var spaceX = space / screen.width, spaceY = space / screen.height;
      var minX = box.minX > -1 ? box.minX - spaceX : box.minX;
      var maxX = box.maxX < 1 ? box.maxX + spaceX : box.maxX;
      var minY = box.minY > -1 ? box.minY - spaceY : box.minY;
      var maxY = box.maxY < 1 ? box.maxY + spaceY : box.maxY;
      cx = (minX + maxX) / 2;
      cy = (minY + maxY) / 2;
      var a = (maxX - minX) / 2 * screen.width;
      var b = (maxY - minY) / 2 * screen.height;
      if (b / a > TALLEST) a = b / TALLEST;
      if (b / a < lowest) b = a * lowest;
      hx = a / screen.width;
      hy = b / screen.height;
    }
    var crop = [1 / hx, 0, 0, 0, 0, 1 / hy, 0, 0, 0, 0, 1, 0, -cx / hx, -cy / hy, 0, 1];
    var result = Object.assign({}, view, {
      camera: Object.assign({}, view.camera, { projection: multiply(crop, view.camera.projection) })
    });
    if (view.rulers) {
      result.rulers = { center: [view.rulers.center[0] + cx * view.rulers.halfW,
                                 view.rulers.center[1] + cy * view.rulers.halfH],
                        halfW: view.rulers.halfW * hx, halfH: view.rulers.halfH * hy };
    }
    var size = page(widthCm, hx * screen.width, hy * screen.height, parts);
    if (view.labelPlanner) {
      var across = size.scene.widthMm / MM_PER_CSS, down = size.scene.heightMm / MM_PER_CSS;
      result.labels = view.labelPlanner(function (x, y) {
        var nx = (x / screen.width * 2 - 1 - cx) / hx, ny = (y / screen.height * 2 - 1 + cy) / hy;
        return { x: (nx * 0.5 + 0.5) * across, y: (ny * 0.5 + 0.5) * down };
      }, across, down);
    }
    return { view: result, page: size };
  }

  /* The whole picture: {page, list}. `screen` is the viewport's size in pixels. */
  function picture(view, widthCm, screen, options, frame) {
    var made = framed(view, widthCm, screen, frame);
    return { page: made.page, list: compose(made.view, made.page, options) };
  }

  return {
    DPI: DPI, DEFAULT_WIDTH_CM: DEFAULT_WIDTH_CM, MAX_WIDTH_CM: MAX_WIDTH_CM, LINE_MM: LINE_MM,
    FORMATS: FORMATS, MM_PER_CSS: MM_PER_CSS, LEGEND_STRIP_MM: LEGEND_STRIP_MM,
    page: page, fileName: fileName, pictureParts: pictureParts, textWidth: textWidth,
    parseCommand: parseCommand,
    shade: shade, compose: compose, drawnBox: drawnBox, widerBox: widerBox, framed: framed,
    picture: picture
  };
})();
