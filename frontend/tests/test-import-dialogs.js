/* The two upload dialogs, driven the way a user does: a real File set on the hidden
   input (or dropped on the zone), `fetch` answered by a stand-in. `handleFile` is not
   exported and does not return its promise, so the tests wait for its visible effect. */

(function () {

  function until(check, ms) {
    var deadline = Date.now() + (ms || 2000);
    return new Promise(function (resolve, reject) {
      (function poll() {
        var value = check();
        if (value) return resolve(value);
        if (Date.now() > deadline) return reject(new Error('timed out waiting'));
        setTimeout(poll, 5);
      })();
    });
  }

  function files(file) {
    var transfer = new DataTransfer();
    transfer.items.add(file);
    return transfer.files;
  }

  function choose(dialog, file) {
    var input = dialog.querySelector('input[type=file]');
    input.files = files(file);
    input.dispatchEvent(new Event('change'));
  }

  function drop(dialog, file) {
    var zone = dialog.querySelector('.drop-zone');
    var event = new Event('drop', { bubbles: true, cancelable: true });
    event.dataTransfer = { files: files(file) };
    zone.dispatchEvent(event);
  }

  /* Everything the dialogs reach for, recorded. `answer` is what fetch resolves to. */
  function rig(answer) {
    var saved = { fetch: window.fetch, api: App.Api, command: App.Command, model: App.Model,
                  viewport: App.Viewport, explorer: App.Explorer, state: App.state,
                  select: App.selectObject };
    var ctx = { posts: [], lines: [], loaded: 0, refreshed: 0, mounted: null, selected: null,
                shown: null };
    var layer = document.createElement('div');
    layer.id = 'modal-layer';
    document.body.appendChild(layer);
    window.fetch = function (url, options) {
      ctx.posts.push({ url: url, file: options.body.get('file') });
      return Promise.resolve(answer);
    };
    App.Api = { base: '' };
    App.Command = {
      ok: function (t) { ctx.lines.push('ok:' + t); },
      note: function (t) { ctx.lines.push('note:' + t); },
      err: function (t) { ctx.lines.push('err:' + t); }
    };
    App.Model = { load: function () { ctx.loaded += 1; return Promise.resolve(); } };
    App.Viewport = {
      refresh: function () { ctx.refreshed += 1; return Promise.resolve(); },
      showImportedMesh: function (model) { ctx.shown = model; },
      is2D: function () { return false; },
      clearImportedMesh: function () {}
    };
    App.Explorer = { mountTree: function (mode) { ctx.mounted = mode; } };
    App.state = { mode: 'soil' };
    App.selectObject = function (key) { ctx.selected = key; };
    ctx.restore = function () {
      if (App.MdpaImportDialog.closeChecklist) App.MdpaImportDialog.closeChecklist();
      layer.remove();
      window.fetch = saved.fetch; App.Api = saved.api; App.Command = saved.command;
      App.Model = saved.model; App.Viewport = saved.viewport; App.Explorer = saved.explorer;
      App.state = saved.state; App.selectObject = saved.select;
    };
    return ctx;
  }

  function ok(body) {
    return { ok: true, json: function () { return Promise.resolve(body); } };
  }

  function refused(detail) {
    return { ok: false, status: 422, json: function () { return Promise.resolve({ detail: detail }); } };
  }

  function wrap(ctx, promise) {
    return promise.then(function () { ctx.restore(); },
                        function (e) { ctx.restore(); throw e; });
  }

  /* ── Import 3D model ──────────────────────────────────────────────────── */

  test('import: a chosen file is uploaded, then the part is loaded, drawn and selected', function () {
    var ctx = rig(ok({ parts: [{ key: 'imported_0' }] }));
    App.ImportDialog.open();
    var dialog = document.getElementById('import-dialog');
    choose(dialog, new File(['solid'], 'cube.stl'));
    return wrap(ctx, until(function () { return ctx.selected; }).then(function () {
      T.eq(ctx.posts[0].url, '/api/geometry/import');
      T.eq(ctx.posts[0].file.name, 'cube.stl');
      T.ok(ctx.lines.some(function (l) { return l === 'ok:Successfully imported model: cube.stl'; }));
      T.ok(!document.getElementById('import-dialog'), 'the dialog closes');
      T.eq([ctx.loaded, ctx.refreshed], [1, 1]);
      T.eq(ctx.mounted, 'soil');
      T.eq(ctx.selected, 'imported_0');
    }));
  });

  test("import: a refused file shows the server's reason and keeps the dialog open", function () {
    var ctx = rig(refused('the surfaces do not close into a solid'));
    App.ImportDialog.open();
    var dialog = document.getElementById('import-dialog');
    choose(dialog, new File(['x'], 'open.stl'));
    var message = function () {
      return Array.prototype.filter.call(dialog.querySelectorAll('.dlg-body div'), function (d) {
        return /close into a solid/.test(d.textContent);
      })[0];
    };
    return wrap(ctx, until(message).then(function (shown) {
      T.ok(document.getElementById('import-dialog'), 'still open, to try another file');
      T.eq(shown.style.color, 'red');
      T.eq(ctx.loaded, 0, 'nothing is reloaded for a refusal');
    }));
  });

  test('import: a dropped file is uploaded like a chosen one', function () {
    var ctx = rig(ok({ parts: [{ key: 'imported_3' }] }));
    App.ImportDialog.open();
    drop(document.getElementById('import-dialog'), new File(['x'], 'part.step'));
    return wrap(ctx, until(function () { return ctx.selected; }).then(function () {
      T.eq(ctx.posts[0].file.name, 'part.step');
    }));
  });

  test('import: dragging over the zone highlights it, leaving clears it', function () {
    var ctx = rig(ok({}));
    App.ImportDialog.open();
    var zone = document.querySelector('#import-dialog .drop-zone');
    zone.dispatchEvent(new Event('dragover', { cancelable: true }));
    var during = zone.style.backgroundColor;
    zone.dispatchEvent(new Event('dragleave', { cancelable: true }));
    var after = zone.style.backgroundColor;
    document.querySelector('#import-dialog .dlg-x').click();
    ctx.restore();
    T.ok(during !== '', 'highlighted while a file is over it');
    T.eq(after, '');
  });

  test('import: Escape and the backdrop both close it, and it opens once', function () {
    var ctx = rig(ok({}));
    try {
      App.ImportDialog.open();
      App.ImportDialog.open();
      T.eq(document.querySelectorAll('#import-dialog').length, 1, 'a second open is ignored');
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      T.ok(!document.getElementById('import-dialog'), 'Escape closes');
      App.ImportDialog.open();
      document.querySelector('#modal-layer .scrim').click();
      T.ok(!document.getElementById('import-dialog'), 'the backdrop closes');
    } finally {
      ctx.restore();
    }
  });

  test('import: choosing no file does nothing', function () {
    var ctx = rig(ok({}));
    App.ImportDialog.open();
    var input = document.querySelector('#import-dialog input[type=file]');
    input.dispatchEvent(new Event('change'));
    document.querySelector('#import-dialog .dlg-x').click();
    ctx.restore();
    T.eq(ctx.posts.length, 0);
  });

  test('import: clicking the drop zone opens the file input without uploading', function () {
    var ctx = rig(ok({}));
    try {
      App.ImportDialog.open();
      var dialog = document.getElementById('import-dialog'), clicks = 0;
      dialog.querySelector('input[type=file]').click = function () { clicks += 1; };
      dialog.querySelector('.drop-zone').click();
      T.eq(clicks, 1);
      T.eq(ctx.posts, []);
      dialog.querySelector('.dlg-x').click();
    } finally { ctx.restore(); }
  });

  /* ── Import mesh (.mdpa) ──────────────────────────────────────────────── */

  var MODEL = {
    dimension: 2, bbox: [0, 0, 0, 1, 1, 0], nodes: 4,
    elements: [{ kratos_class: 'UPwSmallStrainElement2D3N', kind: 'continuum', dim: 2, count: 2 }],
    conditions: [{ kratos_class: 'UPwFaceLoadCondition2D2N', kind: 'load', dim: 1, count: 1 }],
    parts: [{ name: 'Soil', kind: 'body' }, { name: 'Top', kind: 'load' }],
    sections: [], node_parts: { nodes: [], parts: [] }
  };

  test('mdpa: a chosen deck is previewed, summarised and its checklist opened', function () {
    var ctx = rig(ok(MODEL));
    App.MdpaImportDialog.open();
    choose(document.getElementById('mdpa-import-dialog'), new File(['x'], 'site.mdpa'));
    return wrap(ctx, until(function () { return ctx.shown; }).then(function () {
      T.eq(ctx.posts[0].url, '/api/import/mdpa');
      T.ok(!document.getElementById('mdpa-import-dialog'), 'the upload dialog closes');
      T.ok(document.getElementById('mdpa-checklist'), 'the checklist opens');
      var summary = ctx.lines.filter(function (l) { return /^ok:/.test(l); })[0];
      T.eq(summary, 'ok:site.mdpa: 2D mesh, 4 nodes, 2 continuum, 1 load, 2 sub-model parts (1 bodies).');
      T.ok(ctx.lines.some(function (l) { return /Switch to 2D/.test(l); }),
           'a section deck seen in 3D says how to see it face-on');
    }));
  });

  test("mdpa: a malformed deck shows the server's reason", function () {
    var ctx = rig(refused('malformed .mdpa deck: line 3'));
    App.MdpaImportDialog.open();
    var dialog = document.getElementById('mdpa-import-dialog');
    choose(dialog, new File(['x'], 'bad.mdpa'));
    return wrap(ctx, until(function () {
      return /line 3/.test(dialog.textContent);
    }).then(function () {
      T.ok(document.getElementById('mdpa-import-dialog'));
      T.eq(ctx.shown, null);
      document.querySelector('#mdpa-import-dialog .dlg-x').click();
    }));
  });

  test('mdpa: a deck with no elements says so in its summary', function () {
    var empty = Object.assign({}, MODEL, { elements: [], conditions: [], parts: [], dimension: 3 });
    var ctx = rig(ok(empty));
    App.MdpaImportDialog.open();
    drop(document.getElementById('mdpa-import-dialog'), new File(['x'], 'nodes.mdpa'));
    return wrap(ctx, until(function () { return ctx.shown; }).then(function () {
      T.ok(ctx.lines.some(function (l) { return /3D mesh, 4 nodes, no elements, 0 sub-model parts/.test(l); }),
           ctx.lines.join(' | '));
      T.ok(!ctx.lines.some(function (l) { return /Switch to 2D/.test(l); }));
    }));
  });

  test('mdpa: Escape closes the upload dialog', function () {
    var ctx = rig(ok(MODEL));
    try {
      App.MdpaImportDialog.open();
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      T.ok(!document.getElementById('mdpa-import-dialog'));
    } finally {
      ctx.restore();
    }
  });

  test('mdpa: browsing and drag feedback do not upload until a file is chosen', function () {
    var ctx = rig(ok(MODEL));
    try {
      App.MdpaImportDialog.open();
      var dialog = document.getElementById('mdpa-import-dialog'), clicks = 0;
      dialog.querySelector('input[type=file]').click = function () { clicks += 1; };
      var zone = dialog.querySelector('.drop-zone');
      zone.click();
      T.eq(clicks, 1);
      var over = new Event('dragover', { cancelable: true });
      zone.dispatchEvent(over);
      T.ok(over.defaultPrevented);
      T.ok(zone.style.backgroundColor !== '');
      var leave = new Event('dragleave', { cancelable: true });
      zone.dispatchEvent(leave);
      T.ok(leave.defaultPrevented);
      T.eq(zone.style.backgroundColor, '');
      T.eq(ctx.posts, []);
      dialog.querySelector('.dlg-x').click();
    } finally { ctx.restore(); }
  });

})();
