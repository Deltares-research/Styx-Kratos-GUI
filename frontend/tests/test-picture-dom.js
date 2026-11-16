/* picture.js — the canvas, the clipboard and where a file goes.

   Real canvases, and for a folder the browser's own private one
   (`navigator.storage.getDirectory()`), so a real folder handle is written to with no
   system window to press. The walk through stages and fields needs a whole app, and is in
   tests/e2e/test_pictures.py. */

(function () {
  var P = App.Picture;

  var PAGE = App.PictureDraw.page(2, 100, 50);

  function picture(list) { return { page: PAGE, list: list }; }

  var RED = { t: 'fill', tris: [0, 0, 20, 0, 20, 10, 0, 0, 20, 10, 0, 10], color: [1, 0, 0], alpha: 1 };

  function pixel(canvas, x, y) {
    return Array.prototype.slice.call(canvas.getContext('2d').getImageData(x, y, 1, 1).data);
  }

  function captureLog(body) {
    var lines = [];
    var saved = App.Command;
    App.Command = Object.assign({}, saved, {
      ok: function (line) { lines.push(['ok', line]); },
      note: function (line) { lines.push(['note', line]); },
      err: function (line) { lines.push(['err', line]); }
    });
    function back() { App.Command = saved; return lines; }
    return Promise.resolve().then(function () { return body(lines); }).then(back, function (error) {
      back();
      throw error;
    });
  }

  function privateFolder(name) {
    return navigator.storage.getDirectory().then(function (root) {
      return root.removeEntry(name, { recursive: true }).catch(function () {}).then(function () {
        return root.getDirectoryHandle(name, { create: true });
      });
    });
  }

  function textOf(folder, name) {
    return folder.getFileHandle(name).then(function (handle) {
      return handle.getFile();
    }).then(function (file) { return file.text(); });
  }

  test('paint fills the canvas at the page\'s pixel size', function () {
    var canvas = P.paint(picture([RED]));
    T.eq(canvas.width, PAGE.widthPx);
    T.eq(canvas.height, PAGE.heightPx);
    T.eq(pixel(canvas, 10, 10), [255, 0, 0, 255]);
  });

  test('a line is as wide as the list says, in millimetres', function () {
    var canvas = P.paint(picture([{ t: 'line', segs: [0, 5, 20, 5], color: [0, 0, 1], alpha: 1,
                                    width: 1, dash: null }]));
    var middle = Math.round(5 * PAGE.pxPerMm);
    T.eq(pixel(canvas, 100, middle)[2], 255, 'on the line');
    T.eq(pixel(canvas, 100, middle + Math.round(PAGE.pxPerMm))[3], 0, 'a millimetre off it, nothing');
    T.eq(pixel(canvas, 100, middle + Math.round(PAGE.pxPerMm * 0.3))[2], 255, 'wider than a hairline');
  });

  test('the image layer goes on pixel for pixel', function () {
    var rgba = new Uint8ClampedArray(PAGE.widthPx * PAGE.heightPx * 4);
    rgba[0] = 200; rgba[3] = 255;
    var canvas = P.paint(picture([{ t: 'image', width: PAGE.widthPx, height: PAGE.heightPx, rgba: rgba }]));
    T.eq(pixel(canvas, 0, 0), [200, 0, 0, 255]);
    T.eq(pixel(canvas, 1, 0)[3], 0);
  });

  test('the image layer goes where the list puts it', function () {
    var rgba = new Uint8ClampedArray(4);
    rgba[1] = 200; rgba[3] = 255;
    var shape = { t: 'image', width: 1, height: 1, x: 2, y: 3, w: 1, h: 1, rgba: rgba };
    var canvas = P.paint(picture([shape]));
    T.eq(pixel(canvas, Math.round(2 * PAGE.pxPerMm), Math.round(3 * PAGE.pxPerMm)), [0, 200, 0, 255]);
  });

  test('a PNG says 300 dpi', function () {
    return P.encode(picture([RED]), 'png').then(function (bytes) {
      T.eq(String.fromCharCode.apply(null, bytes.subarray(37, 41)), 'pHYs');
      T.eq(new DataView(bytes.buffer).getUint32(41), 11811);
    });
  });

  test('a real PNG with the chunk still decodes, at its size', function () {
    return P.encode(picture([RED]), 'png').then(function (bytes) {
      return createImageBitmap(new Blob([bytes], { type: 'image/png' }));
    }).then(function (bitmap) {
      T.eq(bitmap.width, PAGE.widthPx);
    });
  });

  test('a PDF compresses its streams when the browser can', function () {
    return P.encode(picture([RED]), 'pdf').then(function (bytes) {
      var text = String.fromCharCode.apply(null, bytes.subarray(0, Math.min(bytes.length, 4000)));
      T.ok(text.indexOf('%PDF-') === 0);
      T.ok(text.indexOf('/Filter /FlateDecode') > 0);
    });
  });

  test('an SVG image layer is a PNG in the file itself', function () {
    var rgba = new Uint8ClampedArray(PAGE.widthPx * PAGE.heightPx * 4);
    return P.encode(picture([{ t: 'image', width: PAGE.widthPx, height: PAGE.heightPx,
                               w: PAGE.widthMm, h: PAGE.heightMm, rgba: rgba }]),
                    'svg').then(function (text) {
      T.ok(text.indexOf('href="data:image/png;base64,') > 0);
    });
  });

  test('the SVG and the PNG of one picture draw alike', function () {
    var shapes = [RED, { t: 'fill', tris: [20, 0, 20, 10, 10, 10], color: [0, 0, 1], alpha: 0.5 },
                  { t: 'line', segs: [0, 5, 20, 5], color: [0, 1, 0], alpha: 1, width: 0.5, dash: null }];
    var one = picture(shapes);
    var png = P.paint(one);
    return P.encode(one, 'svg').then(function (text) {
      return new Promise(function (resolve, reject) {
        var image = new Image();
        image.onload = function () { resolve(image); };
        image.onerror = reject;
        image.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(text);
      });
    }).then(function (image) {
      var canvas = document.createElement('canvas');
      canvas.width = png.width; canvas.height = png.height;
      canvas.getContext('2d').drawImage(image, 0, 0, png.width, png.height);
      [[20, 20], [200, 20], [200, 59], [100, 59], [220, 100]].forEach(function (at) {
        var a = pixel(png, at[0], at[1]), b = pixel(canvas, at[0], at[1]);
        for (var k = 0; k < 4; k++) T.near(a[k], b[k], 6, 'at ' + at + ', channel ' + k);
      });
    });
  });

  /* ── A figure already an SVG ─────────────────────────────────────────── */

  test('a figure is drawn at 300 dpi, a unit being a CSS pixel', function () {
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="48">'
            + '<rect width="96" height="48" fill="#00f"/></svg>';
    return P.figure(svg).then(function (made) {
      T.eq(made.page.widthPx, 300, 'one inch');
      T.eq(made.page.heightPx, 150);
      T.eq(Array.prototype.slice.call(made.list[0].rgba, 0, 4), [0, 0, 255, 255]);
    });
  });

  /* ── The clipboard ───────────────────────────────────────────────────── */

  function withClipboard(clipboard, body) {
    var saved = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: clipboard });
    function back() {
      if (saved) Object.defineProperty(navigator, 'clipboard', saved);
      else delete navigator.clipboard;
    }
    return Promise.resolve().then(body).then(function (v) { back(); return v; },
                                             function (e) { back(); throw e; });
  }

  test('with no clipboard, Copy picture says why and offers Save', function () {
    return withClipboard(undefined, function () {
      T.eq(P.canCopy(), false);
      return captureLog(function () { return P.copy(); }).then(function (lines) {
        T.eq(lines[0][0], 'err');
        T.ok(/localhost or https/.test(lines[0][1]));
        T.ok(/Save picture/.test(lines[0][1]));
      });
    });
  });

  test('with no scene to draw, Copy picture says so', function () {
    var saved = App.Viewport.pictureView;
    App.Viewport.pictureView = function () { return null; };
    return withClipboard({ write: function () { throw new Error('nothing to write'); } }, function () {
      return captureLog(function () { return P.copy(); }).then(function (lines) {
        T.ok(/nothing to draw/.test(lines[0][1]));
      });
    }).then(function () { App.Viewport.pictureView = saved; },
            function (e) { App.Viewport.pictureView = saved; throw e; });
  });

  /* ── Where a file goes ───────────────────────────────────────────────── */

  test('a file goes in the folder', function () {
    return privateFolder('picture-test-a').then(function (folder) {
      return P.outlet(folder).add('one.txt', 'hello').then(function (done) {
        T.eq(done, true);
        return textOf(folder, 'one.txt');
      });
    }).then(function (text) { T.eq(text, 'hello'); });
  });

  test('a file already there is kept when the answer is no, and the save stops', function () {
    var saved = P.askOverwrite;
    P.askOverwrite = function () { return Promise.resolve(false); };
    return privateFolder('picture-test-b').then(function (folder) {
      return P.outlet(folder).add('one.txt', 'old').then(function () {
        return P.outlet(folder).add('one.txt', 'new');
      }).then(function (done) {
        T.eq(done, false);
        return textOf(folder, 'one.txt');
      });
    }).then(function (text) {
      P.askOverwrite = saved;
      T.eq(text, 'old');
    }, function (error) { P.askOverwrite = saved; throw error; });
  });

  test('the question is asked once for one save', function () {
    var saved = P.askOverwrite, asked = 0;
    P.askOverwrite = function () { asked += 1; return Promise.resolve(true); };
    return privateFolder('picture-test-c').then(function (folder) {
      var first = P.outlet(folder);
      return first.add('a.txt', '1').then(function () { return first.add('b.txt', '1'); })
        .then(function () {
          var second = P.outlet(folder);
          return second.add('a.txt', '2').then(function () { return second.add('b.txt', '2'); });
        }).then(function () { return textOf(folder, 'b.txt'); });
    }).then(function (text) {
      P.askOverwrite = saved;
      T.eq(asked, 1);
      T.eq(text, '2');
    }, function (error) { P.askOverwrite = saved; throw error; });
  });

  test('with no folder window, the files leave as one zip', function () {
    var saved = App.Download.anchor, sent = [];
    App.Download.anchor = function (name, content, mime) { sent.push([name, content, mime]); };
    var out = P.outlet(null);
    return out.add('a.png', new Uint8Array([1, 2])).then(function () {
      return out.add('b.png', new Uint8Array([3]));
    }).then(function () {
      out.finish();
      App.Download.anchor = saved;
      T.eq(sent.length, 1);
      T.ok(/\.zip$/.test(sent[0][0]));
      T.eq(sent[0][2], 'application/zip');
    }, function (error) { App.Download.anchor = saved; throw error; });
  });

  /* The server's answer to a request for its folder window. */
  function serverSays(answer, run) {
    var saved = App.Api.post;
    App.Api.post = function (path) {
      T.eq(path, '/api/files/folder');
      return answer instanceof Error ? Promise.reject(answer) : Promise.resolve(answer);
    };
    return run().then(function (result) {
      App.Api.post = saved;
      return result;
    }, function (error) { App.Api.post = saved; throw error; });
  }

  test('the folder window of the server goes first, and the one of the browser is not opened', function () {
    var saved = window.showDirectoryPicker, opened = false;
    window.showDirectoryPicker = function () { opened = true; return Promise.reject(new Error('no')); };
    return serverSays({ id: 'abc', name: 'C:\\Downloads' }, function () {
      return App.Download.pickFolder('x');
    }).then(function (folder) {
      window.showDirectoryPicker = saved;
      T.eq(folder, { server: 'abc', name: 'C:\\Downloads' });
      T.eq(opened, false);
    });
  });

  test('a dismissed server window is an answer', function () {
    return serverSays({ cancelled: true }, function () {
      return App.Download.pickFolder('x');
    }).then(function (folder) { T.eq(folder, App.Download.CANCELLED); });
  });

  test('a server window open already stops the save and says why', function () {
    var savedCommand = App.Command, said = [];
    App.Command = { err: function (text) { said.push(text); } };
    function back() { App.Command = savedCommand; }
    return serverSays({ busy: 'A folder window is open already.' }, function () {
      return App.Download.pickFolder('x');
    }).then(function (folder) {
      back();
      T.eq(folder, App.Download.CANCELLED);
      T.eq(said, ['A folder window is open already.']);
    }, function (error) { back(); throw error; });
  });

  test('a folder of the server is handed back, and one of the browser has nothing to hand back', function () {
    var savedFetch = window.fetch, sent = [];
    window.fetch = function (url, options) {
      sent.push([url, options.method]);
      return sent.length === 1 ? Promise.resolve({ ok: true }) : Promise.reject(new Error('gone'));
    };
    function back() { window.fetch = savedFetch; }
    return App.Download.releaseFolder({ server: 'a/b' }).then(function () {
      return App.Download.releaseFolder({ server: 'c' });
    }).then(function () {
      return App.Download.releaseFolder({ name: 'out' });
    }).then(function () {
      return App.Download.releaseFolder(null);
    }).then(function () {
      back();
      T.eq(sent, [[App.Api.base + '/api/files/folder/a%2Fb', 'DELETE'],
                  [App.Api.base + '/api/files/folder/c', 'DELETE']]);
    }, function (error) { back(); throw error; });
  });

  test('a file in a folder of the server is asked for and written by name', function () {
    var savedGet = App.Api.get, savedFetch = window.fetch, sent = null;
    var base = '/api/files/folder/abc/a%20b.png';
    App.Api.get = function (path) { T.eq(path, base); return Promise.resolve({ exists: true }); };
    window.fetch = function (url, options) {
      sent = [url, options];
      return Promise.resolve({ ok: true, json: function () { return Promise.resolve({}); } });
    };
    function back() { App.Api.get = savedGet; window.fetch = savedFetch; }
    var folder = { server: 'abc' };
    return App.Download.exists(folder, 'a b.png').then(function (there) {
      T.eq(there, true);
      return App.Download.writeInFolder(folder, 'a b.png', 'content');
    }).then(function () {
      back();
      T.eq(sent[0], App.Api.base + base);
      T.eq(sent[1].method, 'PUT');
      T.eq(sent[1].body, 'content');
    }, function (error) { back(); throw error; });
  });

  test('the reason the server gives for not writing a file reaches the user', function () {
    var savedFetch = window.fetch;
    window.fetch = function () {
      return Promise.resolve({ ok: false, json: function () {
        return Promise.resolve({ detail: 'the disk is full' });
      } });
    };
    return App.Download.writeInFolder({ server: 'abc' }, 'a.png', 'x').then(function () {
      window.fetch = savedFetch;
      T.ok(false, 'it should not have worked');
    }, function (error) {
      window.fetch = savedFetch;
      T.eq(error.message, 'the disk is full');
    });
  });

  test('where the server has no window, the browser is asked with an id, and a dismissed one is an answer', function () {
    var saved = window.showDirectoryPicker, options = null;
    window.showDirectoryPicker = function (given) {
      options = given;
      var error = new Error('no'); error.name = 'AbortError';
      return Promise.reject(error);
    };
    return serverSays({ no_window: 'no display' }, function () {
      return App.Download.pickFolder('styx-pictures');
    }).then(function (answer) {
      window.showDirectoryPicker = saved;
      T.eq(answer, App.Download.CANCELLED);
      T.eq(options.id, 'styx-pictures');
      T.eq(options.mode, 'readwrite');
    }, function (error) { window.showDirectoryPicker = saved; throw error; });
  });

  test('a browser with no folder window answers null', function () {
    var saved = window.showDirectoryPicker;
    window.showDirectoryPicker = undefined;
    return serverSays(new Error('cannot reach it'), function () {
      return App.Download.pickFolder('x');
    }).then(function (answer) {
      window.showDirectoryPicker = saved;
      T.eq(answer, null);
    });
  });

  test('the file window carries its id too', function () {
    var saved = window.showSaveFilePicker, options = null;
    window.showSaveFilePicker = function (given) {
      options = given;
      return Promise.resolve({ name: 'x' });
    };
    return App.Download.pickFile('a.png', 'image/png', 'styx-pictures').then(function () {
      window.showSaveFilePicker = saved;
      T.eq(options.id, 'styx-pictures');
      T.eq(options.types[0].accept['image/png'], ['.png']);
    }, function (error) { window.showSaveFilePicker = saved; throw error; });
  });

  /* ── The command ─────────────────────────────────────────────────────── */

  test('a line that is not this command is left for the others', function () {
    T.eq(P.command('mesh 2'), false);
  });

  test('a bad line says why, and saves nothing', function () {
    return captureLog(function () {
      T.eq(P.command('picture save tiff'), null);
    }).then(function (lines) {
      T.eq(lines[0][0], 'err');
      T.ok(/tiff/.test(lines[0][1]));
    });
  });

  /* ── The rows ────────────────────────────────────────────────────────── */

  test('more than one format, or a CSV, means a folder', function () {
    T.eq(P.isMany({ formats: ['png'] }), false);
    T.eq(P.isMany({ formats: ['png', 'pdf'] }), true);
    T.eq(P.isMany({ formats: ['png'], csv: true }), true);
  });
})();
