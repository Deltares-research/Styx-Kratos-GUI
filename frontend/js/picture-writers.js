/* ══════════════════════════════════════════════════════════════════
   picture-writers.js — the shapes of picture-draw.js as a file.

   No DOM here either. The two things only a browser can do are done by `picture.js` and
   handed in: encoding an image as a PNG for the SVG, and compressing the PDF's streams.

   ── The PDF ──────────────────────────────────────────────────────────────

   Written by hand, because what a picture needs of PDF is small: filled and stroked
   paths, transparency, an image with a soft mask, and text. A library would add a few
   hundred kilobytes to a page that has no build step.

   The text uses two of the fonts every PDF reader has: Helvetica, for Latin, and Symbol,
   for the Greek in the field labels (σ, τ, Δ). No font file is embedded, so a character
   neither has is written as `?`, and `pdfStreams` counts them for the log.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.PictureWriters = (function () {

  var PT_PER_MM = 72 / 25.4;
  var FONT_FAMILY = 'Arial, Helvetica, sans-serif';
  var CIRCLE = 0.5523;             // a quarter circle as a Bézier curve

  function number(value) {
    var text = value.toFixed(3);
    if (text.indexOf('.') >= 0) text = text.replace(/0+$/, '').replace(/\.$/, '');
    return text === '-0' ? '0' : text;
  }

  function fine(value) {
    return String(parseFloat(value.toFixed(5)));
  }

  /* ── SVG ──────────────────────────────────────────────────────────────── */

  function hexColor(color) {
    return '#' + color.map(function (c) {
      var part = Math.round(Math.max(0, Math.min(1, c)) * 255).toString(16);
      return part.length < 2 ? '0' + part : part;
    }).join('');
  }

  function escapeXml(text) {
    return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function opacity(name, alpha) {
    return alpha < 1 ? ' ' + name + '="' + number(alpha) + '"' : '';
  }

  function svgFill(shape) {
    var d = '';
    for (var i = 0; i + 5 < shape.tris.length; i += 6) {
      d += 'M' + number(shape.tris[i]) + ' ' + number(shape.tris[i + 1])
         + 'L' + number(shape.tris[i + 2]) + ' ' + number(shape.tris[i + 3])
         + 'L' + number(shape.tris[i + 4]) + ' ' + number(shape.tris[i + 5]) + 'Z';
    }
    return '<path d="' + d + '" fill="' + hexColor(shape.color) + '"'
         + opacity('fill-opacity', shape.alpha) + '/>';
  }

  function svgLine(shape) {
    var d = '';
    for (var i = 0; i + 3 < shape.segs.length; i += 4) {
      d += 'M' + number(shape.segs[i]) + ' ' + number(shape.segs[i + 1])
         + 'L' + number(shape.segs[i + 2]) + ' ' + number(shape.segs[i + 3]);
    }
    return '<path d="' + d + '" fill="none" stroke="' + hexColor(shape.color) + '"'
         + opacity('stroke-opacity', shape.alpha)
         + ' stroke-width="' + number(shape.width) + '" stroke-linecap="round"'
         + (shape.dash ? ' stroke-dasharray="' + number(shape.dash[0]) + ' '
                         + number(shape.dash[1]) + '"' : '') + '/>';
  }

  function svgDots(shape) {
    var rest = ' r="' + number(shape.r) + '" fill="' + hexColor(shape.color) + '"'
             + opacity('fill-opacity', shape.alpha)
             + (shape.ring ? ' stroke="' + hexColor(shape.ring) + '" stroke-width="'
                             + number(shape.r * 0.2) + '"' : '') + '/>';
    var out = '';
    for (var i = 0; i + 1 < shape.xy.length; i += 2) {
      out += '<circle cx="' + number(shape.xy[i]) + '" cy="' + number(shape.xy[i + 1]) + '"' + rest;
    }
    return out;
  }

  function svgText(shape) {
    var size = shape.size / PT_PER_MM;
    return '<text x="' + number(shape.x) + '" y="' + number(shape.y) + '" font-size="'
         + number(size) + '" fill="' + hexColor(shape.color) + '"'
         + opacity('fill-opacity', shape.alpha)
         + (shape.bold ? ' font-weight="bold"' : '')
         + (shape.anchor !== 'start' ? ' text-anchor="' + shape.anchor + '"' : '')
         + (shape.rotate ? ' transform="rotate(' + number(shape.rotate) + ' ' + number(shape.x)
                           + ' ' + number(shape.y) + ')"' : '')
         + (shape.halo ? ' stroke="' + hexColor(shape.halo) + '" stroke-width="' + number(size * 0.2)
                         + '" paint-order="stroke" stroke-linejoin="round"' : '')
         + '>' + escapeXml(shape.text) + '</text>';
  }

  /* `imageHref(shape)` gives the URL of an image layer, encoded by the caller. As
     `xlink:href`: drawing programs read that one, and browsers read it too. */
  function svg(list, page, imageHref) {
    var parts = ['<svg xmlns="http://www.w3.org/2000/svg" '
                 + 'xmlns:xlink="http://www.w3.org/1999/xlink" width="' + number(page.widthMm)
                 + 'mm" height="' + number(page.heightMm) + 'mm" viewBox="0 0 '
                 + number(page.widthMm) + ' ' + number(page.heightMm) + '" font-family="'
                 + FONT_FAMILY + '">'];
    list.forEach(function (shape) {
      if (shape.t === 'fill') parts.push(svgFill(shape));
      else if (shape.t === 'line') parts.push(svgLine(shape));
      else if (shape.t === 'dots') parts.push(svgDots(shape));
      else if (shape.t === 'text') parts.push(svgText(shape));
      else if (shape.t === 'image') {
        parts.push('<image x="' + number(shape.x || 0) + '" y="' + number(shape.y || 0)
                   + '" width="' + number(shape.w) + '" height="'
                   + number(shape.h) + '" preserveAspectRatio="none" xlink:href="'
                   + imageHref(shape) + '"/>');
      }
    });
    parts.push('</svg>');
    return parts.join('\n');
  }

  /* ── PDF text ─────────────────────────────────────────────────────────── */

  var GREEK = 'ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩαβγδεζηθικλμνξοπρστυφχψω';
  var SYMBOL = 'ABGDEZHQIKLMNXOPRSTUFCYWabgdezhqiklmnxoprstufcyw';
  /* The few that are not at their Unicode number in the WinAnsi code page. */
  var WIN_ANSI = { 0x2013: 0x96, 0x2014: 0x97, 0x2018: 0x91, 0x2019: 0x92, 0x201C: 0x93,
                   0x201D: 0x94, 0x2022: 0x95, 0x2026: 0x85, 0x2212: 0x2D };

  /* A text as runs of one font each, with the code of each character in that font. */
  function textRuns(text) {
    var runs = [];
    var value = String(text);
    for (var i = 0; i < value.length; i++) {
      var unit = value.charCodeAt(i);
      var greek = GREEK.indexOf(value.charAt(i));
      var font = greek >= 0 ? 'symbol' : 'text';
      var code, missing = 0;
      if (greek >= 0) code = SYMBOL.charCodeAt(greek);
      else if (WIN_ANSI[unit]) code = WIN_ANSI[unit];
      else if ((unit >= 32 && unit < 127) || (unit >= 0xA0 && unit <= 0xFF)) code = unit;
      else { code = 0x3F; missing = 1; }
      var last = runs[runs.length - 1];
      if (!last || last.font !== font) {
        last = { font: font, codes: [], missing: 0 };
        runs.push(last);
      }
      last.codes.push(code);
      last.missing += missing;
    }
    return runs;
  }

  function hexCodes(codes) {
    return codes.map(function (code) {
      var part = code.toString(16).toUpperCase();
      return part.length < 2 ? '0' + part : part;
    }).join('');
  }

  /* ── PDF content ──────────────────────────────────────────────────────── */

  function rgb(color, operator) {
    return color.map(number).join(' ') + ' ' + operator;
  }

  /* The page's transform makes the content's units millimetres from the top left, the
     same space the shapes are in. */
  function pdfStreams(list, page) {
    var out = [];
    var alphas = [];
    var images = [];
    var missing = 0;
    var scale = fine(PT_PER_MM);

    function state(alpha) {
      var at = alphas.indexOf(alpha);
      if (at < 0) {
        alphas.push(alpha);
        alphas.sort();
        at = alphas.indexOf(alpha);
      }
      return alpha;
    }

    out.push('q');
    out.push(scale + ' 0 0 -' + scale + ' 0 ' + number(page.heightMm * PT_PER_MM) + ' cm');

    list.forEach(function (shape) {
      if (shape.t === 'image') {
        var name = 'Im' + images.length;
        images.push(splitImage(shape));
        out.push('q ' + number(shape.w) + ' 0 0 -' + number(shape.h) + ' ' + number(shape.x || 0)
                 + ' ' + number((shape.y || 0) + shape.h) + ' cm /' + name + ' Do Q');
        return;
      }
      out.push('@GS' + state(shape.alpha));
      if (shape.t === 'fill') out.push(pdfFill(shape));
      else if (shape.t === 'line') out.push(pdfLine(shape));
      else if (shape.t === 'dots') out.push(pdfDots(shape));
      else if (shape.t === 'text') {
        var written = pdfText(shape);
        missing += written.missing;
        out.push(written.content);
      }
    });
    out.push('Q');

    // Named last, once every alpha is known and the list is in its final order.
    var content = out.map(function (line) {
      if (line.indexOf('@GS') !== 0) return line;
      return '/GS' + alphas.indexOf(Number(line.slice(3))) + ' gs';
    }).join('\n') + '\n';
    return { content: content, alphas: alphas, images: images, missing: missing };
  }

  function pdfFill(shape) {
    var path = [rgb(shape.color, 'rg')];
    for (var i = 0; i + 5 < shape.tris.length; i += 6) {
      path.push(number(shape.tris[i]) + ' ' + number(shape.tris[i + 1]) + ' m '
                + number(shape.tris[i + 2]) + ' ' + number(shape.tris[i + 3]) + ' l '
                + number(shape.tris[i + 4]) + ' ' + number(shape.tris[i + 5]) + ' l h');
    }
    path.push('f');
    return path.join('\n');
  }

  function pdfLine(shape) {
    var path = [rgb(shape.color, 'RG'), number(shape.width) + ' w', '1 J',
                shape.dash ? '[' + number(shape.dash[0]) + ' ' + number(shape.dash[1]) + '] 0 d'
                           : '[] 0 d'];
    for (var i = 0; i + 3 < shape.segs.length; i += 4) {
      path.push(number(shape.segs[i]) + ' ' + number(shape.segs[i + 1]) + ' m '
                + number(shape.segs[i + 2]) + ' ' + number(shape.segs[i + 3]) + ' l');
    }
    path.push('S');
    return path.join('\n');
  }

  function pdfCircle(x, y, r) {
    var k = r * CIRCLE;
    function p(a, b) { return number(x + a) + ' ' + number(y + b); }
    return p(r, 0) + ' m '
         + p(r, k) + ' ' + p(k, r) + ' ' + p(0, r) + ' c '
         + p(-k, r) + ' ' + p(-r, k) + ' ' + p(-r, 0) + ' c '
         + p(-r, -k) + ' ' + p(-k, -r) + ' ' + p(0, -r) + ' c '
         + p(k, -r) + ' ' + p(r, -k) + ' ' + p(r, 0) + ' c h';
  }

  function pdfDots(shape) {
    var path = [rgb(shape.color, 'rg')];
    if (shape.ring) {
      path.push(rgb(shape.ring, 'RG'), number(shape.r * 0.2) + ' w', '[] 0 d');
    }
    for (var i = 0; i + 1 < shape.xy.length; i += 2) {
      path.push(pdfCircle(shape.xy[i], shape.xy[i + 1], shape.r));
    }
    path.push(shape.ring ? 'B' : 'f');
    return path.join('\n');
  }

  function pdfText(shape) {
    var size = shape.size / PT_PER_MM;
    var width = App.PictureDraw.textWidth(shape.text, shape.size, shape.bold);
    var shift = shape.anchor === 'middle' ? width / 2 : shape.anchor === 'end' ? width : 0;
    var angle = (shape.rotate || 0) * Math.PI / 180;
    var cos = Math.cos(angle), sin = Math.sin(angle);
    /* The page is flipped, so the text's up has to point back up the page. */
    var matrix = [size * cos, size * sin, size * sin, -size * cos,
                  shape.x - shift * cos, shape.y - shift * sin].map(number).join(' ');
    var runs = textRuns(shape.text);
    var letters = runs.map(function (run) {
      var font = run.font === 'symbol' ? 'F3' : shape.bold ? 'F2' : 'F1';
      return '/' + font + ' 1 Tf <' + hexCodes(run.codes) + '> Tj';
    }).join(' ');
    var missing = runs.reduce(function (sum, run) { return sum + run.missing; }, 0);

    var parts = [];
    if (shape.halo) {
      parts.push('BT 1 Tr ' + rgb(shape.halo, 'RG') + ' ' + number(size * 0.2) + ' w [] 0 d 1 j '
                 + matrix + ' Tm ' + letters + ' ET');
    }
    parts.push('BT 0 Tr ' + rgb(shape.color, 'rg') + ' ' + matrix + ' Tm ' + letters + ' ET');
    return { content: parts.join('\n'), missing: missing };
  }

  function splitImage(shape) {
    var count = shape.width * shape.height;
    var colour = new Uint8Array(count * 3), alpha = new Uint8Array(count);
    for (var i = 0; i < count; i++) {
      colour[i * 3] = shape.rgba[i * 4];
      colour[i * 3 + 1] = shape.rgba[i * 4 + 1];
      colour[i * 3 + 2] = shape.rgba[i * 4 + 2];
      alpha[i] = shape.rgba[i * 4 + 3];
    }
    return { width: shape.width, height: shape.height, rgb: colour, alpha: alpha };
  }

  /* ── The PDF file ─────────────────────────────────────────────────────── */

  function latin1(text) {
    var bytes = new Uint8Array(text.length);
    for (var i = 0; i < text.length; i++) bytes[i] = text.charCodeAt(i) & 0xFF;
    return bytes;
  }

  /* `parts`: the streams of `pdfStreams` as {bytes, filter}, where `filter` names how the
     caller compressed them, or is null. */
  function pdfAssemble(page, parts) {
    var chunks = [], size = 0, offsets = [];

    function add(bytes) { chunks.push(bytes); size += bytes.length; }
    function text(value) { add(latin1(value)); }
    function object(number, dictionary, stream) {
      offsets[number] = size;
      if (!stream) { text(number + ' 0 obj\n' + dictionary + '\nendobj\n'); return; }
      var filter = stream.filter ? ' /Filter /' + stream.filter : '';
      text(number + ' 0 obj\n<< ' + dictionary + ' /Length ' + stream.bytes.length + filter
           + ' >>\nstream\n');
      add(stream.bytes);
      text('\nendstream\nendobj\n');
    }

    var images = parts.images || [];
    var CONTENT = 4, FONT_TEXT = 5, FONT_BOLD = 6, FONT_SYMBOL = 7, FIRST_IMAGE = 8;
    var xObjects = images.map(function (image, i) {
      return '/Im' + i + ' ' + (FIRST_IMAGE + i * 2) + ' 0 R';
    }).join(' ');
    var states = parts.alphas.map(function (alpha, i) {
      return '/GS' + i + ' << /ca ' + number(alpha) + ' /CA ' + number(alpha) + ' >>';
    }).join(' ');

    text('%PDF-1.5\n%\xE2\xE3\xCF\xD3\n');
    object(1, '<< /Type /Catalog /Pages 2 0 R >>');
    object(2, '<< /Type /Pages /Kids [3 0 R] /Count 1 >>');
    object(3, '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ' + number(page.widthMm * PT_PER_MM)
              + ' ' + number(page.heightMm * PT_PER_MM) + '] /Contents ' + CONTENT + ' 0 R'
              + ' /Resources << /Font << /F1 ' + FONT_TEXT + ' 0 R /F2 ' + FONT_BOLD
              + ' 0 R /F3 ' + FONT_SYMBOL + ' 0 R >> /ExtGState << ' + states + ' >>'
              + (xObjects ? ' /XObject << ' + xObjects + ' >>' : '') + ' >> >>');
    object(CONTENT, '', parts.content);
    object(FONT_TEXT, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica '
                      + '/Encoding /WinAnsiEncoding >>');
    object(FONT_BOLD, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold '
                      + '/Encoding /WinAnsiEncoding >>');
    object(FONT_SYMBOL, '<< /Type /Font /Subtype /Type1 /BaseFont /Symbol >>');
    images.forEach(function (image, i) {
      var at = FIRST_IMAGE + i * 2;
      var common = '/Type /XObject /Subtype /Image /Width ' + image.width + ' /Height '
                 + image.height + ' /BitsPerComponent 8';
      object(at, common + ' /ColorSpace /DeviceRGB /SMask ' + (at + 1) + ' 0 R', image.rgb);
      object(at + 1, common + ' /ColorSpace /DeviceGray', image.alpha);
    });

    var count = FIRST_IMAGE + images.length * 2;
    var table = size;
    var lines = ['xref', '0 ' + count, '0000000000 65535 f '];
    for (var n = 1; n < count; n++) {
      lines.push(('0000000000' + offsets[n]).slice(-10) + ' 00000 n ');
    }
    text(lines.join('\n') + '\ntrailer\n<< /Size ' + count + ' /Root 1 0 R >>\nstartxref\n'
         + table + '\n%%EOF\n');

    var file = new Uint8Array(size), at = 0;
    chunks.forEach(function (chunk) { file.set(chunk, at); at += chunk.length; });
    return file;
  }

  /* ── PNG ──────────────────────────────────────────────────────────────── */

  /* `canvas.toBlob` writes no resolution, and Word then places the image at 96 dpi, three
     times too wide. The chunk goes right after the header, where the format wants it. */
  function pngWithDpi(png, dpi) {
    var chunk = new Uint8Array(21);
    var view = new DataView(chunk.buffer);
    var perMetre = Math.round(dpi / 0.0254);
    view.setUint32(0, 9);
    chunk.set([0x70, 0x48, 0x59, 0x73], 4);
    view.setUint32(8, perMetre);
    view.setUint32(12, perMetre);
    chunk[16] = 1;
    view.setUint32(17, App.Zip.crc32(chunk.subarray(4, 17)) >>> 0);
    var out = new Uint8Array(png.length + 21);
    out.set(png.subarray(0, 33));
    out.set(chunk, 33);
    out.set(png.subarray(33), 54);
    return out;
  }

  return {
    svg: svg, textRuns: textRuns, number: number, latin1: latin1,
    pdfStreams: pdfStreams, pdfAssemble: pdfAssemble, pngWithDpi: pngWithDpi
  };
})();
