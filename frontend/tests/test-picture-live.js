/* picture.js and picture-dialog.js on a booted viewport.

   test-viewport-live.js boots the viewport against the recorded test model
   (fixtures/viewport-payloads.js); this file runs after it and draws that scene: one
   picture, every stage, one PDF, the results walk, the clipboard, the window, and the job
   kratos-cli gives the page. The save windows, the clipboard and the receiver are
   stand-ins; the scene, the shapes and the encoders are the real ones.

   The harness puts back an `App` module a test swaps, not a property inside one, so a
   test that patches `App.Viewport` or `App.Picture` itself puts it back. */

(function () {

  var P = window.VIEWPORT_PAYLOADS;
  var Pic = App.Picture;
  var lines, files, asked;

  function standIns() {
    lines = [];
    App.Api = {
      base: '',
      get: function (path) {
        if (path === '/api/project') return Promise.resolve(JSON.parse(JSON.stringify(P.project)));
        if (path === '/api/geometry') return Promise.resolve(P.geometry);
        return Promise.reject(new Error('unexpected GET ' + path));
      },
      post: function (path) {
        if (path === '/api/mesh') return Promise.resolve(P.mesh);
        if (path === '/api/mesh/labels') return Promise.resolve(P.labels);
        if (path === '/api/mesh/node-parts') return Promise.resolve(P.nodeParts);
        return Promise.reject(new Error('unexpected POST ' + path));
      }
    };
    App.Command = {
      note: function (t) { lines.push(['note', t]); },
      ok: function (t) { lines.push(['ok', t]); },
      err: function (t) { lines.push(['err', t]); },
      write: function () {},
      run: function (t) { lines.push(['run', t]); }
    };
    App.setMode = function (mode) { App.state.mode = mode; App.Viewport.setMode(mode); };
    // As test-viewport-live.js has them: this page has no tree or status bar to fill.
    App.setCoords = function () {};
    App.setZoom = function () {};
    App.selectObject = function (key) { App.state.selection = key; };
    App.Explorer = { mountTree: function () {}, mountSelection: function () {} };
  }

  /* The save windows answer at once: `file` and `folder` are what they give, `there` the
     names already in the folder, `onWrite(name)` runs as each file is written. */
  function windows(options) {
    options = options || {};
    files = [];
    asked = [];
    var cancelled = App.Download.CANCELLED;
    function answer(given, otherwise) {
      return given instanceof Error ? Promise.reject(given)
        : given && given.then ? given : Promise.resolve(given === undefined ? otherwise : given);
    }
    App.Download = {
      CANCELLED: cancelled,
      pickFile: function (name, mime, id) {
        asked.push(['file', name, mime, id]);
        return answer(options.file, { name: name });
      },
      pickFolder: function (id) {
        asked.push(['folder', id]);
        return answer(options.folder, { name: 'out' });
      },
      exists: function (folder, name) {
        return Promise.resolve(!!(options.there && options.there.indexOf(name) >= 0));
      },
      writeInFolder: function (folder, name, content) {
        files.push({ name: name, content: content });
        if (options.onWrite) options.onWrite(name);
        return Promise.resolve();
      },
      write: function (target, name, content, mime) {
        files.push({ name: name, content: content, mime: mime });
        return Promise.resolve();
      },
      anchor: function () {}
    };
  }

  function until(check, ms) {
    var deadline = Date.now() + (ms || 5000);
    return new Promise(function (resolve, reject) {
      (function poll() {
        var value;
        try { value = check(); } catch (e) { value = null; }
        if (value) return resolve(value);
        if (Date.now() > deadline) return reject(new Error('timed out waiting'));
        setTimeout(poll, 10);
      })();
    });
  }

  function staged(position) {
    App.state.mode = 'staged';
    App.Viewport.setMode('staged');
    App.state.phase = App.PROJECT.stages[position].id;
    App.Viewport.applyStageVisibility();
  }

  /* The booted viewport in Staged construction, on its third stage. */
  function ready() {
    standIns();
    return until(function () { return App.PROJECT && App.Viewport.pictureView(); }).then(function () {
      staged(2);
    });
  }

  function said(kind, pattern) {
    return lines.some(function (line) { return line[0] === kind && pattern.test(line[1]); });
  }

  function isPng(content) {
    return content[1] === 0x50 && content[2] === 0x4e && content[3] === 0x47;
  }

  function startsPdf(content) {
    return String.fromCharCode.apply(null, Array.prototype.slice.call(content, 0, 5)) === '%PDF-';
  }

  function button(label) {
    return Array.prototype.filter.call(document.querySelectorAll('button'), function (b) {
      return b.textContent === label;
    }).pop();
  }

  /* `run` with the layer dialogs open in, as frontend/index.html has it. */
  function layered(run) {
    var layer = document.getElementById('modal-layer'), owned = !layer;
    if (owned) {
      layer = document.createElement('div');
      layer.id = 'modal-layer';
      document.body.appendChild(layer);
    }
    function back() { if (owned) layer.remove(); }
    return Promise.resolve().then(run).then(function (v) { back(); return v; },
                                            function (e) { back(); throw e; });
  }

  /* ── The screen as shapes ────────────────────────────────────────────── */

  test('picture live: the stage on screen is drawn with its title, its rulers and its labels', function () {
    return ready().then(function () {
      return new Promise(function (resolve) { App.Viewport.setLabels('nodes', true, resolve); });
    }).then(function () {
      var stage = App.PROJECT.stages[2];
      var view = Pic.readView(App.Viewport.pictureView(), { rulers: true, axes: true, grid: true });
      T.eq(view.title, 'Stage 3: ' + stage.name);
      T.ok(view.objects.length > 0, 'the parts of the stage');
      T.ok(view.lights.length > 0, 'the lights');
      T.ok(view.triad.axes.length >= 2, 'the axes');
      var made = Pic.compose({ width: 5, show: { rulers: true } });
      T.ok(made.list.some(function (shape) { return shape.t === 'text'; }), 'ruler numbers');
      var canvas = Pic.paint(made);
      T.eq(canvas.width, made.page.widthPx);
    }).then(function () {
      App.Viewport.setLabels('nodes', false);
    }, function (error) { App.Viewport.setLabels('nodes', false); throw error; });
  });

  test('picture live: the defaults follow the rulers on screen', function () {
    return ready().then(function () {
      T.eq(Pic.defaults().rulers, !!(App.Ruler && App.Ruler.isEnabled && App.Ruler.isEnabled()));
      T.eq(Pic.defaults().axes, true);
    });
  });

  /* ── One picture ─────────────────────────────────────────────────────── */

  test('picture live: one picture asks for a file and writes a PNG of the stage', function () {
    return ready().then(function () {
      windows();
      return Pic.save({ formats: ['png'], width: 5, show: {} });
    }).then(function (count) {
      T.eq(count, 1);
      T.eq(asked[0][0], 'file');
      T.ok(/stage3/.test(asked[0][1]), asked[0][1]);
      T.eq(asked[0][3], 'styx-pictures');
      T.ok(isPng(files[0].content), 'a PNG');
      T.ok(said('ok', /Saved .*\.png \(\d+ x \d+ px at 300 dpi\)/), JSON.stringify(lines));
      T.eq(document.getElementById('vp-loading').hidden, true);
    });
  });

  test('picture live: a closed file window saves nothing', function () {
    return ready().then(function () {
      windows({ file: App.Download.CANCELLED });
      return Pic.save({ formats: ['svg'], width: 5 });
    }).then(function (count) {
      T.eq(count, null);
      T.eq(files.length, 0);
      T.ok(said('note', /Picture not saved/));
    });
  });

  test('picture live: an error on the way is said, and the next save can start', function () {
    return ready().then(function () {
      windows({ file: new Error('disk full') });
      return Pic.save({ formats: ['png'], width: 5 });
    }).then(function (count) {
      T.eq(count, null);
      T.ok(said('err', /could not be saved: disk full/));
      windows({ file: App.Download.CANCELLED });
      return Pic.save({ formats: ['png'], width: 5 });
    }).then(function () {
      T.ok(said('note', /Picture not saved/), 'not refused as busy');
    });
  });

  test('picture live: with nothing to draw, save says so', function () {
    var saved = App.Viewport.pictureView;
    return ready().then(function () {
      App.Viewport.pictureView = function () { return null; };
      return Pic.save({ formats: ['png'], width: 5 });
    }).then(function (count) {
      App.Viewport.pictureView = saved;
      T.eq(count, null);
      T.ok(said('err', /nothing to draw/));
    }, function (error) { App.Viewport.pictureView = saved; throw error; });
  });

  test('picture live: every stage asked for in a tab of one picture is one picture, said so', function () {
    return ready().then(function () {
      App.state.mode = 'soil';
      App.Viewport.setMode('soil');
      windows({ file: App.Download.CANCELLED });
      return Pic.save({ formats: ['png'], width: 5, stage: 'all' });
    }).then(function () {
      T.ok(said('note', /This tab shows one picture/));
      T.eq(asked[0][0], 'file');
    });
  });

  /* ── Every stage ─────────────────────────────────────────────────────── */

  test('picture live: every stage goes in a folder, and the screen and the selection come back', function () {
    var stages, phase, key;
    return ready().then(function () {
      stages = App.PROJECT.stages;
      phase = App.state.phase;
      key = (App.PROJECT.soil_body_keys || [])[0];
      App.Viewport.select(key);
      key = App.Viewport.selectedKey();
      windows();
      return Pic.save({ formats: ['png', 'svg'], width: 5, stage: 'all' });
    }).then(function (count) {
      T.eq(count, stages.length * 2);
      T.eq(asked[0][0], 'folder');
      T.eq(files.filter(function (file) { return /\.png$/.test(file.name); }).length, stages.length);
      T.ok(/<svg/.test(files.filter(function (file) { return /\.svg$/.test(file.name); })[0].content));
      T.eq(App.state.phase, phase, 'the stage on screen is back');
      T.eq(App.Viewport.selectedKey(), key, 'the selection is back');
      T.ok(said('ok', /Saved \d+ files in out\./), JSON.stringify(lines));
    });
  });

  test('picture live: a closed folder window saves nothing', function () {
    return ready().then(function () {
      windows({ folder: App.Download.CANCELLED });
      return Pic.save({ formats: ['png', 'svg'], width: 5 });
    }).then(function () {
      T.eq(files.length, 0);
      T.ok(said('note', /Pictures not saved/));
    });
  });

  test('picture live: Stop ends a save after the file being written', function () {
    return ready().then(function () {
      windows({ onWrite: function () {
        var stop = document.querySelector('#vp-loading .picture-stop');
        if (stop) stop.click();
      } });
      return Pic.save({ formats: ['png'], width: 5, stage: 'all' });
    }).then(function (count) {
      T.eq(count, 1);
      T.ok(said('note', /Stopped after 1 file/), JSON.stringify(lines));
      T.eq(document.querySelector('#vp-loading .picture-stop'), null, 'the button goes');
    });
  });

  test('picture live: a file already there is asked about, and a no stops the save', function () {
    var saved = Pic.askOverwrite;
    return ready().then(function () {
      windows({ there: [] });
      return Pic.save({ formats: ['png', 'svg'], width: 5 });
    }).then(function () {
      var names = files.map(function (file) { return file.name; });
      Pic.askOverwrite = function () { return Promise.resolve(false); };
      windows({ there: names });
      return Pic.save({ formats: ['png', 'svg'], width: 5 });
    }).then(function (count) {
      Pic.askOverwrite = saved;
      T.eq(count, 0);
      T.eq(files.length, 0);
    }, function (error) { Pic.askOverwrite = saved; throw error; });
  });

  test('picture live: the overwrite question answers with the button pressed', function () {
    return layered(function () {
      var first = Pic.askOverwrite('a.png');
      T.ok(/a\.png is already in this folder/.test(document.getElementById('modal-layer').textContent));
      button('Overwrite').click();
      return first.then(function (yes) {
        T.eq(yes, true);
        var second = Pic.askOverwrite('a.png');
        button('Stop').click();
        return second;
      }).then(function (yes) { T.eq(yes, false); });
    });
  });

  test('picture live: every stage in one PDF asks for one file with a page for each', function () {
    var stages;
    return ready().then(function () {
      stages = App.PROJECT.stages;
      windows();
      return Pic.save({ formats: ['pdf'], width: 5, stage: 'all', onePdf: true });
    }).then(function (count) {
      T.eq(count, 1);
      T.eq(asked[0][0], 'file');
      T.ok(/_stages\.pdf$/.test(asked[0][1]), asked[0][1]);
      T.eq(files.length, 1);
      T.ok(startsPdf(files[0].content));
      T.ok(said('ok', new RegExp('with ' + stages.length + ' pages')), JSON.stringify(lines));
    });
  });

  test('picture live: one PDF beside other files goes in the folder', function () {
    return ready().then(function () {
      windows();
      return Pic.save({ formats: ['png', 'pdf'], width: 5, stage: 'all', onePdf: true });
    }).then(function () {
      var pdfs = files.filter(function (file) { return /\.pdf$/.test(file.name); });
      T.eq(asked[0][0], 'folder');
      T.eq(pdfs.length, 1);
      T.ok(startsPdf(pdfs[0].content));
    });
  });

  test('picture live: a one-PDF save whose window is closed saves nothing', function () {
    return ready().then(function () {
      windows({ file: App.Download.CANCELLED });
      return Pic.save({ formats: ['pdf'], width: 5, stage: 'all', onePdf: true });
    }).then(function () {
      T.ok(said('note', /Pictures not saved/));
    });
  });

  test('picture live: a one-PDF save stopped after its first page keeps that page', function () {
    var watch;
    return ready().then(function () {
      windows();
      var box = document.getElementById('vp-loading');
      // Pressed the moment the first page is ready, before the next stage is drawn.
      watch = new MutationObserver(function () {
        var stop = box.querySelector('.picture-stop');
        if (stop && /1 page$/.test(box.querySelector('.vp-loading-label').textContent)) stop.click();
      });
      watch.observe(box, { subtree: true, childList: true, characterData: true });
      return Pic.save({ formats: ['pdf'], width: 5, stage: 'all', onePdf: true });
    }).then(function (count) {
      watch.disconnect();
      T.eq(count, 1);
      T.eq(files.length, 1);
      T.ok(said('note', /^Stopped: .*_stages\.pdf has 1 page\.$/), JSON.stringify(lines));
    }, function (error) { watch.disconnect(); throw error; });
  });

  test('picture live: an error while the stages are walked puts the stage on screen back', function () {
    var phase;
    return ready().then(function () {
      phase = App.state.phase;
      windows();
      App.Download.writeInFolder = function () { return Promise.reject(new Error('folder gone')); };
      return Pic.save({ formats: ['png'], width: 5, stage: 'all' });
    }).then(function (count) {
      T.eq(count, null);
      T.ok(said('err', /could not be saved: folder gone/), JSON.stringify(lines));
      T.eq(App.state.phase, phase);
    });
  });

  test('picture live: an error while the frame is measured is said, and the screen is free again', function () {
    var tabs = App.Viewport.modelTabs;
    return ready().then(function () {
      App.Viewport.modelTabs = function () { throw new Error('no tabs'); };
      windows();
      return Pic.save({ formats: ['png'], width: 5 });
    }).then(function (count) {
      App.Viewport.modelTabs = tabs;
      T.eq(count, null);
      T.ok(said('err', /could not be saved: no tabs/), JSON.stringify(lines));
      T.eq(document.getElementById('vp-loading').hidden, true);
      T.eq(App.state.mode, 'staged', 'the tab is back');
    }, function (error) { App.Viewport.modelTabs = tabs; throw error; });
  });

  test('picture live: an image layer goes into a PDF as an image with its own transparency', function () {
    var page = App.PictureDraw.page(2, 100, 50);
    var rgba = new Uint8ClampedArray(4 * 4);
    for (var i = 0; i < rgba.length; i += 4) { rgba[i] = 255; rgba[i + 3] = 128; }
    return Pic.encode({ page: page, list: [{ t: 'image', width: 2, height: 2, w: 10, h: 10,
                                             rgba: rgba }] }, 'pdf').then(function (bytes) {
      var text = String.fromCharCode.apply(null, Array.prototype.slice.call(bytes));
      T.ok(/^%PDF-/.test(text));
      T.ok(/\/Subtype\s*\/Image/.test(text), 'an image');
      T.ok(/\/SMask/.test(text), 'with its alpha');
    });
  });

  /* ── Results ─────────────────────────────────────────────────────────── */

  /* A run of two stages with results, the first without the field `s`. */
  function results() {
    var at = { stage: 2, field: 'u' };
    App.Results = Object.assign({}, App.Results, {
      state: function () {
        return { stages: [{ index: 1, stage: 'Initial', results: true },
                          { index: 2, stage: 'Dig', results: true },
                          { index: 3, stage: 'Later', results: false }] };
      },
      current: function () { return 'run-1'; },
      stage: function () { return at.stage; },
      field: function () { return { field: at.field, values: [1, 2] }; },
      fieldNames: function () { return ['u', 's']; },
      show: function (index, name) {
        at.stage = index;
        at.field = index === 1 && name === 's' ? 'u' : name || at.field;
        return Promise.resolve();
      }
    });
    App.ResultsView = Object.assign({}, App.ResultsView, { legendData: function () { return null; } });
    App.ResultsRender = Object.assign({}, App.ResultsRender, {
      csv: function (values, about) { return 'run,' + about.run + '\n'; }
    });
    App.state.mode = 'results';
    return at;
  }

  test('picture live: every field of every stage of a run, with its values, and the screen comes back', function () {
    var at;
    return ready().then(function () {
      at = results();
      T.eq(Pic.inResults(), true);
      T.eq(Pic.resultStages().length, 2);
      windows();
      return Pic.save({ formats: ['png'], width: 5, stage: 'all', field: 'all', csv: true });
    }).then(function (count) {
      var names = files.map(function (file) { return file.name; });
      T.eq(count, 6, names.join(' '));
      T.eq(names.filter(function (name) { return /\.csv$/.test(name); }).length, 3);
      T.ok(names.every(function (name) { return /^run-1_stage\d_\w\./.test(name); }), names.join(' '));
      T.eq([at.stage, at.field], [2, 'u'], 'the stage and field on screen are back');
      App.state.mode = 'staged';
    }, function (error) { App.state.mode = 'staged'; throw error; });
  });

  test('picture live: one result picture is named for its run, stage and field', function () {
    return ready().then(function () {
      results();
      windows();
      T.eq(Pic.readView(App.Viewport.pictureView(), {}).title, 'Stage 2: Dig');
      return Pic.save({ formats: ['png'], width: 5 });
    }).then(function () {
      T.ok(/^run-1_stage2_u\.png$/.test(asked[0][1]), asked[0][1]);
      App.state.mode = 'staged';
    }, function (error) { App.state.mode = 'staged'; throw error; });
  });

  test('picture live: every field of one stage in one PDF is named for both', function () {
    return ready().then(function () {
      results();
      windows();
      return Pic.save({ formats: ['pdf'], width: 5, field: 'all', onePdf: true });
    }).then(function () {
      T.ok(/^run-1_stage2_fields\.pdf$/.test(asked[0][1]), asked[0][1]);
      T.ok(said('ok', /with 2 pages/), JSON.stringify(lines));
      App.state.mode = 'staged';
    }, function (error) { App.state.mode = 'staged'; throw error; });
  });

  test('picture live: an error in the walk puts the result on screen back', function () {
    var at;
    return ready().then(function () {
      at = results();
      var show = App.Results.show;
      App.Results.show = function (index, name) {
        if (index === 1 && name === 's') return Promise.reject(new Error('no such field'));
        return show(index, name);
      };
      windows();
      return Pic.save({ formats: ['png'], width: 5, stage: 'all', field: 'all' });
    }).then(function () {
      T.ok(said('err', /no such field/), JSON.stringify(lines));
      T.eq([at.stage, at.field], [2, 'u']);
      App.state.mode = 'staged';
    }, function (error) { App.state.mode = 'staged'; throw error; });
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

  test('picture live: Copy picture puts a PNG on the clipboard', function () {
    var copied = null;
    return ready().then(function () {
      return withClipboard({ write: function (items) {
        return items[0].getType('image/png').then(function (blob) { copied = blob; });
      } }, function () { return Pic.copy({ width: 5 }); });
    }).then(function (done) {
      T.eq(done, true);
      T.eq(copied.type, 'image/png');
      T.ok(said('ok', /copied to the clipboard \(\d+ x \d+ px\)/), JSON.stringify(lines));
    });
  });

  test('picture live: a clipboard that refuses is said', function () {
    return ready().then(function () {
      return withClipboard({ write: function () { return Promise.reject(new Error('denied')); } },
                           function () { return Pic.copy(); });
    }).then(function (done) {
      T.eq(done, false);
      T.ok(said('err', /could not be copied: denied/));
    });
  });

  test('picture live: while pictures are saved, a copy or a second save waits', function () {
    var open;
    return ready().then(function () {
      windows({ folder: new Promise(function (resolve) { open = resolve; }) });
      var first = Pic.save({ formats: ['png', 'svg'], width: 5 });
      return withClipboard({ write: function () { return Promise.resolve(); } }, function () {
        return Pic.copy();
      }).then(function (copied) {
        T.eq(copied, false);
        T.ok(said('note', /Copy this one when that is done/));
        return Pic.save({ formats: ['png'], width: 5 });
      }).then(function (second) {
        T.eq(second, null);
        T.ok(said('note', /being saved already/));
        open(App.Download.CANCELLED);
        return first;
      });
    });
  });

  /* ── A figure ────────────────────────────────────────────────────────── */

  var FIGURE = '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="48">'
             + '<rect width="96" height="48" fill="#00f"/></svg>';

  test('picture live: a figure is saved as the PNG asked for', function () {
    return ready().then(function () {
      windows();
      return Pic.saveFigure(FIGURE, 'plot.png', 'png');
    }).then(function (count) {
      T.eq(count, 1);
      T.eq(asked[0], ['file', 'plot.png', 'image/png', 'styx-pictures']);
      T.ok(isPng(files[0].content));
      T.ok(said('ok', /Saved plot\.png/));
    });
  });

  test('picture live: a figure whose window is closed, or that cannot be drawn, is not saved', function () {
    return ready().then(function () {
      windows({ file: App.Download.CANCELLED });
      return Pic.saveFigure(FIGURE, 'plot.pdf', 'pdf');
    }).then(function (count) {
      T.eq(count, null);
      T.ok(said('note', /Not saved/));
      windows();
      return Pic.saveFigure('<svg width="10" height="10"><broken', 'plot.png', 'png');
    }).then(function (count) {
      T.eq(count, null);
      T.ok(said('err', /could not be saved: The browser could not draw the figure/));
    });
  });

  /* ── The window ──────────────────────────────────────────────────────── */

  function closeDialog() {
    var cancel = button('Cancel');
    if (cancel) cancel.click();
  }

  test('picture live: the window says the size, checks the width, and saves in the words of the box', function () {
    return layered(function () {
      var saved = App.Picture;
      var copies = [];
      return ready().then(function () {
        App.Picture = Object.assign({}, saved, { copy: function (a) { copies.push(a); } });
        var handle = App.PictureDialog.open();
        T.ok(handle, 'opened');
        T.eq(App.PictureDialog.open(), null, 'once');
        var form = document.getElementById('picture-form');
        T.ok(/\d+ px wide at 300 dpi/.test(form.textContent), form.textContent);
        var width = form.querySelector('[name=picture-width]');
        width.value = '0';
        width.dispatchEvent(new Event('input'));
        T.ok(/more than 0/.test(form.textContent));
        button('Save…').click();
        T.ok(document.getElementById('picture-form'), 'a bad width keeps the window open');
        button('Copy picture').click();
        T.eq(copies[0].width, undefined, 'a bad width copies at the default');
        width.value = '8';
        width.dispatchEvent(new Event('input'));
        var svg = form.querySelector('[name=picture-format-svg]');
        svg.checked = true;
        svg.dispatchEvent(new Event('change'));
        var all = form.querySelector('[name=picture-scope][value=stages]')
               || form.querySelectorAll('[name=picture-scope]')[1];
        all.checked = true;
        all.dispatchEvent(new Event('change'));
        var onePdf = form.querySelectorAll('[name=picture-pdf]')[1];
        onePdf.checked = true;
        onePdf.dispatchEvent(new Event('change'));
        ['picture-axes', 'picture-rulers', 'picture-grid', 'picture-screen-zoom'].forEach(function (name) {
          var box = form.querySelector('[name=' + name + ']');
          box.checked = !box.checked;
          box.dispatchEvent(new Event('change'));
        });
        button('Save…').click();
        T.eq(document.getElementById('picture-form'), null, 'closed');
        var run = lines.filter(function (line) { return line[0] === 'run'; })[0];
        T.ok(run && /^picture save --format \S*svg/.test(run[1]), JSON.stringify(lines));
        T.ok(/--width 8/.test(run[1]), run[1]);
        App.Picture = saved;
      }, function (error) { App.Picture = saved; closeDialog(); throw error; });
    });
  });

  test('picture live: in Results the window offers the legend and the values', function () {
    return layered(function () {
      return ready().then(function () {
        results();
        App.PictureDialog.open();
        var form = document.getElementById('picture-form');
        ['picture-legend', 'picture-csv'].forEach(function (name) {
          var box = form.querySelector('[name=' + name + ']');
          T.ok(box, name);
          box.checked = !box.checked;
          box.dispatchEvent(new Event('change'));
        });
        closeDialog();
        T.eq(document.getElementById('picture-form'), null);
        App.state.mode = 'staged';
      }, function (error) { closeDialog(); App.state.mode = 'staged'; throw error; });
    });
  });

  test('picture live: with nothing to draw the window does not open', function () {
    var saved = App.Viewport.pictureView;
    return ready().then(function () {
      App.Viewport.pictureView = function () { return null; };
      T.eq(App.PictureDialog.open(), null);
      App.Viewport.pictureView = saved;
      T.ok(said('err', /nothing to draw/));
    }, function (error) { App.Viewport.pictureView = saved; throw error; });
  });

  /* ── The job of kratos-cli ───────────────────────────────────────────── */

  var RECEIVER = 'http://127.0.0.1:9';

  function job(extra) {
    return Object.assign({
      receiver: RECEIVER, token: 'the-token', mode: 'staged', stage: 2, view: 'front',
      asked: { formats: ['svg'], width: 5, show: { rulers: false }, stage: null, field: null }
    }, extra || {});
  }

  function address(given) { return '?picture=' + encodeURIComponent(JSON.stringify(given)); }

  /* `server` answers the token; the posts to the receiver are kept in `posts`. */
  function receiving(server, run) {
    var posts = [], checked = [];
    var savedFetch = window.fetch;
    window.fetch = function (url, options) {
      posts.push({ url: url, options: options });
      return Promise.resolve({});
    };
    var get = App.Api.get;
    App.Api.get = function (path) {
      if (/^\/api\/files\/picture-job\//.test(path)) {
        checked.push(path);
        return server instanceof Error ? Promise.reject(server) : Promise.resolve(server);
      }
      return get(path);
    };
    function back() { window.fetch = savedFetch; }
    return Promise.resolve().then(function () { return run(); }).then(function (answer) {
      back();
      return { answer: answer, posts: posts, checked: checked };
    }, function (error) { back(); throw error; });
  }

  test('picture live: an address with no job is no job', function () {
    T.eq(Pic.jobFromAddress(''), null);
    T.eq(Pic.jobFromAddress('?x=1'), null);
    return Pic.startJob('').then(function (ran) { T.eq(ran, false); });
  });

  test('picture live: a job for a receiver elsewhere, with no token or not JSON, is refused unasked', function () {
    [address(job({ receiver: 'http://evil.example' })),
     address(job({ receiver: 'https://127.0.0.1:9' })),
     address(job({ token: '' })),
     address(job({ token: 7 })),
     '?picture=%7Bnot%20json'].forEach(function (search) {
      T.ok(Pic.jobFromAddress(search) instanceof Error, search);
    });
    return ready().then(function () {
      return receiving({ ok: true }, function () {
        return Pic.startJob(address(job({ receiver: 'http://evil.example' })));
      });
    }).then(function (seen) {
      T.eq(seen.answer, false);
      T.eq(seen.checked.length, 0, 'the server is not even asked');
      T.eq(seen.posts.length, 0, 'nothing is sent');
      T.ok(said('err', /kratos-cli did not give it/));
    });
  });

  test('picture live: a job its server does not know draws nothing and sends nothing', function () {
    return ready().then(function () {
      return receiving({ ok: false }, function () { return Pic.startJob(address(job())); });
    }).then(function (seen) {
      T.eq(seen.answer, false);
      T.eq(seen.checked, ['/api/files/picture-job/the-token']);
      T.eq(seen.posts.length, 0);
      T.ok(said('err', /kratos-cli did not give it/));
      return receiving(new Error('offline'), function () { return Pic.startJob(address(job())); });
    }).then(function (seen) {
      T.eq(seen.answer, false, 'no answer is a no');
      T.eq(seen.posts.length, 0);
    });
  });

  test('picture live: the job of kratos-cli draws its stage and posts each file, then the count', function () {
    return ready().then(function () {
      return receiving({ ok: true }, function () { return Pic.startJob(address(job())); });
    }).then(function (seen) {
      T.eq(seen.answer, true);
      T.eq(seen.posts.length, 2, JSON.stringify(seen.posts.map(function (p) { return p.url; })));
      T.ok(/^http:\/\/127\.0\.0\.1:9\/file\?name=.*stage2.*\.svg$/.test(seen.posts[0].url), seen.posts[0].url);
      T.eq(seen.posts[0].options.mode, 'no-cors');
      T.eq(seen.posts[1].url, RECEIVER + '/done');
      T.eq(JSON.parse(seen.posts[1].options.body), { ok: true, count: 1 });
      T.eq(App.state.phase, App.PROJECT.stages[1].id);
    });
  });

  test('picture live: a mesh job meshes first, and an error the page says ends the job', function () {
    return ready().then(function () {
      App.Results = Object.assign({}, App.Results, {
        handleCommand: function (line) { App.Command.err('Not a results command: ' + line); }
      });
      return receiving({ ok: true }, function () {
        return Pic.runJob(job({ mode: 'mesh', stage: null, view: null, commands: ['results nonsense'] }));
      });
    }).then(function (seen) {
      T.eq(seen.posts.length, 1, 'no file, only the end');
      var done = JSON.parse(seen.posts[0].options.body);
      T.eq(done.ok, false);
      T.ok(/Not a results command: results nonsense/.test(done.error), done.error);
      T.eq(App.state.mode, 'mesh');
    });
  });

})();