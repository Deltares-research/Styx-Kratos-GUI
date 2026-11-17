/* test-feedback-dom.js — the Feedback window, the button in every window's title bar, the
   `feedback` command and the note after an error (js/feedback-dialog.js). Browser only. */

(function () {
  var D = App.FeedbackDialog;

  /* A modal layer, a recorded API and command log, and nothing open at the end. */
  function rig(answer) {
    var saved = { api: App.Api, command: App.Command, viewport: App.Viewport };
    var ctx = { posts: [], lines: [] };
    var layer = document.getElementById('modal-layer');
    var owned = !layer;
    if (owned) {
      layer = document.createElement('div');
      layer.id = 'modal-layer';
      document.body.appendChild(layer);
    }
    App.Api = Object.assign({}, saved.api, {
      post: function (path, body) {
        ctx.posts.push({ path: path, body: body });
        return answer instanceof Error ? Promise.reject(answer) : Promise.resolve(answer);
      }
    });
    App.Command = {
      write: function (kind, t) { ctx.lines.push(kind + ':' + t); },
      ok: function (t) { ctx.lines.push('ok:' + t); },
      note: function (t) { ctx.lines.push('note:' + t); },
      err: function (t) { ctx.lines.push('err:' + t); }
    };
    App.Viewport = {};          // no picture: the report goes without one
    ctx.layer = layer;
    ctx.restore = function () {
      var open = layer.querySelectorAll('.dialog .dlg-x');
      Array.prototype.forEach.call(open, function (x) { x.click(); });
      D.hideNote();
      if (owned) layer.remove();
      App.Api = saved.api; App.Command = saved.command; App.Viewport = saved.viewport;
      App.Feedback.forgetForTests();
    };
    return ctx;
  }

  function feedbackWindow() {
    return document.querySelector('.feedback-window');
  }

  function press(label) {
    var buttons = feedbackWindow().querySelectorAll('.dlg-foot .btn');
    Array.prototype.filter.call(buttons, function (b) { return b.textContent === label; })[0].click();
  }

  function settle() { return new Promise(function (done) { setTimeout(done, 0); }); }

  test('feedback dom: every window gets the speech bubble, and it names the window', function () {
    var ctx = rig({});
    try {
      var shell = App.Dialogs.open({ title: 'Mesh properties', buttons: [] });
      D.addWindowButton(shell.dialog);
      D.addWindowButton(shell.dialog);
      var bubbles = shell.dialog.querySelectorAll('.dlg-head .dlg-feedback');
      T.eq(bubbles.length, 1, 'once');
      T.eq(bubbles[0].nextElementSibling.className, 'dlg-x', 'before the close cross');

      bubbles[0].click();
      T.ok(D.isOpen());
      T.ok(/the window "Mesh properties"/.test(feedbackWindow().textContent));
      D.addWindowButton(feedbackWindow());
      T.eq(feedbackWindow().querySelectorAll('.dlg-feedback').length, 0,
           'not on the Feedback window itself');
    } finally { ctx.restore(); }
  });

  test('feedback dom: Escape over another window closes the Feedback window only', function () {
    var ctx = rig({});
    try {
      App.Dialogs.open({ title: 'Soil materials', buttons: [] });
      D.open({ window: 'Soil materials' });
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      T.ok(!D.isOpen());
      T.eq(ctx.layer.querySelectorAll('.dialog').length, 1, 'the window under it stays');
    } finally { ctx.restore(); }
  });

  test('feedback dom: an empty report is refused in the window, and nothing is sent', function () {
    var ctx = rig({});
    try {
      D.open();
      press('Save report');
      T.ok(/Write what happened/.test(feedbackWindow().querySelector('.feedback-message-line').textContent));
      T.eq(ctx.posts.length, 0);
    } finally { ctx.restore(); }
  });

  test('feedback dom: Save report sends the words, the kind and the logs, and says where the file is', function () {
    var ctx = rig({ path: 'C:/fb/styx-feedback-2026-11-17.zip', folder: 'C:/fb',
                    name: 'styx-feedback-2026-11-17.zip', report: '14-05-12-confusing',
                    reports: 2 });
    D.open({ message: 'Hard to find', kind: 'confusing' });
    var win = feedbackWindow();
    win.querySelector('input[name="feedback-model"]').checked = false;
    press('Save report');
    return settle().then(settle).then(function () {
      T.eq(ctx.posts.length, 1);
      var sent = ctx.posts[0];
      T.eq(sent.path, '/api/feedback');
      T.eq(sent.body.kind, 'confusing');
      T.eq(sent.body.message, 'Hard to find');
      T.eq(sent.body.include_project, false);
      T.eq(sent.body.view, null);
      T.eq(sent.body.attachments, []);
      T.ok(sent.body.context.mode, 'where in the app');
      T.ok(!D.isOpen(), 'closed after the save');
      T.ok(ctx.lines.indexOf('ok:Feedback saved: 14-05-12-confusing in C:/fb/styx-feedback-2026-11-17.zip') >= 0);
      var note = document.getElementById('feedback-note');
      T.ok(note && /Report added to styx-feedback-2026-11-17.zip/.test(note.textContent));
      T.ok(/holds 2 reports now/.test(note.textContent));
      T.ok(/Show folder/.test(note.textContent));
    }).then(ctx.restore, function (error) { ctx.restore(); throw error; });
  });

  /* A paste event with `items` on its clipboard, as a browser makes one for Ctrl+V. */
  function paste(types, items) {
    var event = new Event('paste', { bubbles: true, cancelable: true });
    event.clipboardData = { types: types, items: items };
    document.activeElement.dispatchEvent(event);
    return event;
  }

  function onePixelPng() {
    var bytes = atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==');
    var array = new Uint8Array(bytes.length);
    for (var i = 0; i < bytes.length; i += 1) array[i] = bytes.charCodeAt(i);
    return new File([array], 'shot.png', { type: 'image/png' });
  }

  function until(check) {
    return new Promise(function (done, fail) {
      var tries = 0;
      (function look() {
        if (check()) return done();
        if ((tries += 1) > 100) return fail(new Error('timed out'));
        setTimeout(look, 10);
      })();
    });
  }

  test('feedback dom: a pasted screenshot and a dropped file are shown, sent, and can be removed', function () {
    var ctx = rig({ path: 'p', folder: 'f', name: 'n', report: 'r', reports: 1 });
    D.open({ message: 'Look' });
    var win = feedbackWindow();
    T.ok(/Ctrl\+V here/.test(win.querySelector('.feedback-files').textContent));
    var text = paste(['text/plain'], [{ kind: 'string', type: 'text/plain' }]);
    T.ok(!text.defaultPrevented, 'a paste of text is left to the text box');
    var file = onePixelPng();
    var picture = paste(['Files'], [{ kind: 'file', type: 'image/png',
                                      getAsFile: function () { return file; } }]);
    T.ok(picture.defaultPrevented);
    var drop = new Event('drop', { bubbles: true, cancelable: true });
    drop.dataTransfer = { types: ['Files'],
                          files: [new File(['words'], 'notes.docx', { type: 'application/msword' })] };
    win.dispatchEvent(drop);
    T.ok(drop.defaultPrevented);
    return until(function () { return win.querySelectorAll('.feedback-file').length === 2
                                      && win.querySelector('.feedback-file-thumb'); }).then(function () {
      var names = Array.prototype.map.call(win.querySelectorAll('.feedback-file-name'),
                                           function (n) { return n.textContent; });
      T.eq(names, ['screenshot.png', 'notes.docx']);
      T.eq(win.querySelector('.feedback-file-icon').textContent, 'docx');
      press('Save report');
      return settle().then(settle);
    }).then(function () {
      var sent = ctx.posts[0].body.attachments;
      T.eq(sent.map(function (a) { return a.name; }), ['screenshot.png', 'notes.docx']);
      T.ok(/^data:image\/png;base64,/.test(sent[0].data));
      D.open({ message: 'again' });
      var again = feedbackWindow();
      T.eq(again.querySelectorAll('.feedback-file').length, 0, 'a new report starts with none');
      paste(['Files'], [{ kind: 'file', type: 'image/png', getAsFile: function () { return file; } }]);
      return until(function () { return again.querySelector('.feedback-file-remove'); }).then(function () {
        again.querySelector('.feedback-file-remove').click();
        T.eq(again.querySelectorAll('.feedback-file').length, 0);
      });
    }).then(ctx.restore, function (error) { ctx.restore(); throw error; });
  });

  test('feedback dom: a save the server refuses stays open and says why', function () {
    var ctx = rig(new Error('The folder could not be made.'));
    D.open({ message: 'x' });
    press('Save report');
    return settle().then(settle).then(function () {
      T.ok(D.isOpen());
      T.ok(/could not be saved: The folder could not be made./.test(
        feedbackWindow().querySelector('.feedback-message-line').textContent));
    }).then(ctx.restore, function (error) { ctx.restore(); throw error; });
  });

  test('feedback dom: after an error a note offers a report about it', function () {
    var ctx = rig({});
    try {
      var entry = App.Feedback.notice('Server error 500 on POST /api/mesh', 'gmsh failed\nmore').entry;
      var note = document.getElementById('feedback-note');
      T.ok(note, 'the note is shown');
      T.ok(/Something went wrong: Server error 500 on POST \/api\/mesh/.test(note.textContent));
      T.ok(note.textContent.indexOf('more') < 0, 'the first line of the reason only');
      Array.prototype.filter.call(note.querySelectorAll('button'), function (b) {
        return b.textContent === 'Save a report';
      })[0].click();
      T.ok(D.isOpen());
      T.ok(!document.getElementById('feedback-note'), 'the note goes');
      T.ok(/gmsh failed/.test(feedbackWindow().querySelector('.feedback-error').textContent));
      T.eq(entry.what, 'Server error 500 on POST /api/mesh');
    } finally { ctx.restore(); }
  });

  test('feedback dom: `feedback <text>` opens the window with the text in it', function () {
    var ctx = rig({});
    try {
      T.eq(D.command('mesh'), false);
      T.eq(D.command('feedback   The ruler is too small'), true);
      T.eq(feedbackWindow().querySelector('textarea').value, 'The ruler is too small');
      T.ok(ctx.lines.indexOf('echo:> feedback   The ruler is too small') >= 0);
    } finally { ctx.restore(); }
  });

  test('feedback dom: the toolbar and the Help menu have Feedback', function () {
    T.ok(App.TOOLBAR.some(function (t) { return t && t.action === 'feedback' && t.wide === 'Feedback'; }));
    var help = App.MENUS.filter(function (m) { return m.label === 'Help'; })[0];
    T.ok(help.items.some(function (i) { return i && i.action === 'feedback'; }));
    T.ok(App.LivePatches.COMMANDS.some(function (row) { return row[0] === 'feedback [text]'; }));
  });
})();
