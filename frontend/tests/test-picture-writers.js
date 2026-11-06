/* picture-writers.js — the list of shapes as SVG, as PDF, and the resolution in a PNG.

   Read back with no library: the PDF's cross-reference table has to point at each of its
   objects, or a strict reader refuses the file. */

(function () {
  var W = App.PictureWriters;
  var PAGE = { widthMm: 100, heightMm: 50, widthPx: 1181, heightPx: 591, pxPerMm: 11.81 };

  var TRIANGLE = { t: 'fill', tris: [10, 10, 20, 10, 20, 20], color: [1, 0, 0], alpha: 1 };
  var LINE = { t: 'line', segs: [0, 0, 10, 10], color: [0, 0, 1], alpha: 0.5, width: 0.15, dash: null };

  function text(extra) {
    return Object.assign({ t: 'text', x: 5, y: 6, text: 'stage 1', size: 8, anchor: 'start',
                           color: [0, 0, 0], alpha: 1, bold: false, rotate: 0, halo: null },
                         extra || {});
  }

  /* ── SVG ────────────────────────────────────────────────────────────── */

  test('an SVG states its size in millimetres, so a reader places it at its true size', function () {
    var svg = W.svg([], PAGE);
    T.ok(/^<svg /.test(svg));
    T.ok(svg.indexOf('width="100mm"') > 0);
    T.ok(svg.indexOf('height="50mm"') > 0);
    T.ok(svg.indexOf('viewBox="0 0 100 50"') > 0);
  });

  test('an SVG fill and line are paths with their colours', function () {
    var svg = W.svg([TRIANGLE, LINE], PAGE);
    T.ok(svg.indexOf('d="M10 10L20 10L20 20Z"') > 0, svg);
    T.ok(svg.indexOf('fill="#ff0000"') > 0);
    T.ok(svg.indexOf('stroke="#0000ff"') > 0);
    T.ok(svg.indexOf('stroke-opacity="0.5"') > 0);
    T.ok(svg.indexOf('stroke-width="0.15"') > 0);
  });

  test('an SVG dash is a dash array', function () {
    var svg = W.svg([Object.assign({}, LINE, { dash: [2, 1] })], PAGE);
    T.ok(svg.indexOf('stroke-dasharray="2 1"') > 0);
  });

  test('SVG text stays text, and is escaped', function () {
    var svg = W.svg([text({ text: 'a < b & "c"', anchor: 'middle' })], PAGE);
    T.ok(svg.indexOf('a &lt; b &amp; &quot;c&quot;') > 0, svg);
    T.ok(svg.indexOf('text-anchor="middle"') > 0);
    T.ok(svg.indexOf('font-size="2.822"') > 0, '8 pt is 2.822 mm');
  });

  test('rotated SVG text turns about its own point, and a halo goes behind the letters', function () {
    var svg = W.svg([text({ rotate: -90, halo: [1, 1, 1] })], PAGE);
    T.ok(svg.indexOf('transform="rotate(-90 5 6)"') > 0, svg);
    T.ok(svg.indexOf('paint-order="stroke"') > 0);
  });

  test('an SVG image comes from what the caller encoded, at its own size', function () {
    var image = { t: 'image', width: 2, height: 2, w: 60, h: 30, rgba: new Uint8ClampedArray(16) };
    var svg = W.svg([image], PAGE, function (shape) {
      T.eq(shape, image);
      return 'data:image/png;base64,AAAA';
    });
    T.ok(svg.indexOf('href="data:image/png;base64,AAAA"') > 0);
    T.ok(svg.indexOf('width="60" height="30"') > 0, svg);
  });

  test('SVG dots are circles, with a ring when they have one', function () {
    var svg = W.svg([{ t: 'dots', xy: [1, 2, 3, 4], r: 0.5, color: [0, 1, 0], alpha: 1,
                       ring: [1, 0, 0] }], PAGE);
    T.ok(svg.indexOf('<circle cx="1" cy="2" r="0.5"') > 0, svg);
    T.ok(svg.indexOf('<circle cx="3" cy="4"') > 0);
    T.ok(svg.indexOf('stroke="#ff0000"') > 0);
  });

  /* ── PDF text ───────────────────────────────────────────────────────── */

  test('Latin text is Helvetica; Greek is the Symbol font', function () {
    var runs = W.textRuns('σ\'yy');
    T.eq(runs.map(function (r) { return r.font; }), ['symbol', 'text']);
    T.eq(runs[0].codes, [0x73], 'σ is s in Symbol');
    T.eq(runs[1].codes, [0x27, 0x79, 0x79]);
  });

  test('accented letters and units keep their codes', function () {
    T.eq(W.textRuns('m²')[0].codes, [0x6D, 0xB2]);
    T.eq(W.textRuns('−1')[0].codes, [0x2D, 0x31], 'a minus sign is a hyphen');
    T.eq(W.textRuns('a·b')[0].codes, [0x61, 0xB7, 0x62]);
  });

  test('a character neither font has becomes a question mark, and is counted', function () {
    var runs = W.textRuns('土x');
    T.eq(runs[0].codes, [0x3F, 0x78]);
    T.eq(runs[0].missing, 1);
  });

  /* ── PDF ────────────────────────────────────────────────────────────── */

  function pdfText(bytes) {
    var out = '';
    for (var i = 0; i < bytes.length; i++) out += String.fromCharCode(bytes[i]);
    return out;
  }

  function assemble(list) {
    var streams = W.pdfStreams(list, PAGE);
    return { streams: streams,
             bytes: W.pdfAssemble(PAGE, { content: { bytes: W.latin1(streams.content), filter: null },
                                          alphas: streams.alphas,
                                          images: streams.images.map(function (image) {
                                            return { width: image.width, height: image.height,
                                                     rgb: { bytes: image.rgb, filter: null },
                                                     alpha: { bytes: image.alpha, filter: null } };
                                          }) }) };
  }

  test('the PDF page is the picture\'s size in points', function () {
    var file = pdfText(assemble([TRIANGLE]).bytes);
    T.ok(file.indexOf('%PDF-1.5') === 0);
    T.ok(/\/MediaBox \[0 0 283\.465 141\.732\]/.test(file), file.slice(0, 400));
  });

  test('every object in the cross-reference table is where the table says', function () {
    var file = pdfText(assemble([TRIANGLE, LINE, text()]).bytes);
    var xref = file.lastIndexOf('\nxref\n') + 1;
    var start = Number(/startxref\n(\d+)/.exec(file)[1]);
    T.eq(start, xref, 'startxref points at the table');
    var head = file.slice(xref).split('\n');
    var count = Number(head[1].split(' ')[1]);
    T.ok(count > 4);
    for (var i = 1; i < count; i++) {
      var offset = Number(head[2 + i].slice(0, 10));
      T.eq(file.slice(offset, offset + String(i).length + 6), i + ' 0 obj', 'object ' + i);
    }
  });

  test('a stream says its true length', function () {
    var file = pdfText(assemble([TRIANGLE]).bytes);
    var match = /\/Length (\d+)[^>]*>>\nstream\n/.exec(file);
    var length = Number(match[1]);
    var begin = match.index + match[0].length;
    T.eq(file.slice(begin + length, begin + length + 10), '\nendstream');
  });

  test('the content flips to millimetres from the top left, and fills and strokes', function () {
    var content = W.pdfStreams([TRIANGLE, LINE], PAGE).content;
    T.ok(content.indexOf('2.83465 0 0 -2.83465 0 141.732 cm') >= 0, content);
    T.ok(content.indexOf('1 0 0 rg') > 0);
    T.ok(content.indexOf('10 10 m 20 10 l 20 20 l h') > 0);
    T.ok(content.indexOf('0.15 w') > 0);
    T.ok(content.indexOf('0 0 m 10 10 l') > 0);
  });

  test('transparency is a graphics state, named once per value', function () {
    var streams = W.pdfStreams([LINE, Object.assign({}, LINE), TRIANGLE], PAGE);
    T.eq(streams.alphas, [1, 0.5].sort());
    T.ok(streams.content.indexOf('/GS1 gs') > 0 || streams.content.indexOf('/GS0 gs') > 0);
  });

  test('PDF text is upright in the flipped page', function () {
    var content = W.pdfStreams([text()], PAGE).content;
    T.ok(content.indexOf('2.822 0 0 -2.822 5 6 Tm') > 0, content);
    T.ok(/<[0-9A-F]+> Tj/.test(content));
  });

  test('centred bold PDF text is measured in the bold letters', function () {
    var content = W.pdfStreams([text({ anchor: 'middle', bold: true })], PAGE).content;
    var width = App.PictureDraw.textWidth('stage 1', 8, true);
    T.ok(content.indexOf('-2.822 ' + W.number(5 - width / 2) + ' 6 Tm') > 0, content);
  });

  test('centred PDF text starts half its width to the left', function () {
    var content = W.pdfStreams([text({ anchor: 'middle' })], PAGE).content;
    var width = App.PictureDraw.textWidth('stage 1', 8);
    var expected = W.number(5 - width / 2);
    T.ok(content.indexOf('-2.822 ' + expected + ' 6 Tm') > 0, content);
  });

  test('a halo is stroked first, the letters filled over it', function () {
    var content = W.pdfStreams([text({ halo: [1, 1, 1] })], PAGE).content;
    T.ok(content.indexOf('1 Tr') > 0);
    T.ok(content.indexOf('1 Tr') < content.indexOf('0 Tr'));
  });

  test('an image splits into colour and alpha, and sits at the top left', function () {
    var rgba = new Uint8ClampedArray([10, 20, 30, 255, 40, 50, 60, 128]);
    var streams = W.pdfStreams([{ t: 'image', width: 2, height: 1, w: 60, h: 30, rgba: rgba }], PAGE);
    T.eq(Array.prototype.slice.call(streams.images[0].rgb), [10, 20, 30, 40, 50, 60]);
    T.eq(Array.prototype.slice.call(streams.images[0].alpha), [255, 128]);
    T.ok(streams.content.indexOf('60 0 0 -30 0 30 cm /Im0 Do') > 0, streams.content);
  });

  test('an image sits where the list puts it', function () {
    var rgba = new Uint8ClampedArray([10, 20, 30, 255]);
    var shape = { t: 'image', width: 1, height: 1, x: 5, y: 7, w: 60, h: 30, rgba: rgba };
    T.ok(W.pdfStreams([shape], PAGE).content.indexOf('60 0 0 -30 5 37 cm /Im0 Do') > 0);
    var svg = W.svg([shape], PAGE, function () { return 'data:x'; });
    T.ok(svg.indexOf('<image x="5" y="7" width="60" height="30"') > 0, svg);
  });

  test('an image object has its soft mask', function () {
    var rgba = new Uint8ClampedArray([10, 20, 30, 255]);
    var file = pdfText(assemble([{ t: 'image', width: 1, height: 1, w: 10, h: 10, rgba: rgba }]).bytes);
    T.ok(/\/SMask \d+ 0 R/.test(file));
    T.ok(file.indexOf('/ColorSpace /DeviceGray') > 0);
    T.ok(file.indexOf('/ColorSpace /DeviceRGB') > 0);
  });

  test('dots become closed curves', function () {
    var content = W.pdfStreams([{ t: 'dots', xy: [5, 5], r: 1, color: [0, 0, 0], alpha: 1, ring: null }],
                               PAGE).content;
    T.ok(content.indexOf(' c') > 0);
    T.ok(/\nf\n/.test(content));
  });

  /* ── PNG ────────────────────────────────────────────────────────────── */

  /* The smallest PNG header: signature, then an IHDR of length 13. */
  function tinyPng() {
    var bytes = new Uint8Array(33 + 12);
    bytes.set([137, 80, 78, 71, 13, 10, 26, 10], 0);
    bytes.set([0, 0, 0, 13, 73, 72, 68, 82], 8);
    bytes.set([0, 0, 0, 0, 73, 69, 78, 68, 0xAE, 0x42, 0x60, 0x82], 33);
    return bytes;
  }

  test('a PNG says its resolution right after its header', function () {
    var out = W.pngWithDpi(tinyPng(), 300);
    T.eq(out.length, tinyPng().length + 21);
    T.eq(pdfText(out.subarray(37, 41)), 'pHYs');
    var view = new DataView(out.buffer);
    T.eq(view.getUint32(41), 11811, 'pixels per metre across');
    T.eq(view.getUint32(45), 11811, 'and down');
    T.eq(out[49], 1, 'the unit is the metre');
    T.eq(view.getUint32(50), App.Zip.crc32(out.subarray(37, 50)) >>> 0);
    T.eq(pdfText(out.subarray(58, 62)), 'IEND');
  });
})();
