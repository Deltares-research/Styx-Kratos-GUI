/* test-feedback.js — what a feedback report says, and the errors it can be about
   (js/feedback.js). No DOM: frontend/tests/run_headless.py runs it too. */

(function () {
  var F = App.Feedback;

  function told() {
    var heard = [];
    var fn = function (entry) { heard.push(entry); };
    F.onNotice(fn);
    return { heard: heard, stop: function () { F.offNotice(fn); } };
  }

  test('feedback: the kinds are the words of kratos-cli feedback --kind', function () {
    T.eq(F.KINDS.map(function (k) { return k.id; }), ['bug', 'confusing', 'missing', 'good']);
    T.eq(F.kind('missing').label, 'Something is missing');
    T.eq(F.kind('praise'), null);
  });

  test('feedback: an error is kept and told, and not told again while it repeats within a minute', function () {
    F.forgetForTests();
    var ear = told();
    try {
      var start = 1000000;
      T.ok(F.notice('Server error 500 on POST /api/mesh', 'gmsh failed', start).told);
      T.ok(!F.notice('Server error 500 on POST /api/mesh', 'gmsh failed', start + 5000).told);
      T.ok(F.notice('Server error 500 on POST /api/mesh', 'another reason', start + 6000).told);
      T.ok(F.notice('Server error 500 on POST /api/mesh', 'gmsh failed', start + 5000 + F.REPEAT_MS + 1).told,
         'a minute after it was last seen');
      T.eq(ear.heard.length, 3);
      T.eq(F.seen().length, 4, 'a repeat is still kept for the report');
      T.eq(Object.keys(F.seen()[0]).sort(), ['detail', 'what', 'when']);
    } finally { ear.stop(); F.forgetForTests(); }
  });

  test('feedback: only the newest errors are kept', function () {
    F.forgetForTests();
    for (var i = 0; i < F.MAX_ERRORS + 5; i += 1) F.notice('error ' + i, '', i * 1000);
    T.eq(F.seen().length, F.MAX_ERRORS);
    T.eq(F.seen()[0].what, 'error 5');
    F.forgetForTests();
  });

  test('feedback: a server error names the request; a failing feedback route is not offered', function () {
    F.forgetForTests();
    var kept = F.serverError(500, 'Kratos could not be started.', 'POST', '/api/calculate');
    T.eq(kept.entry.what, 'Server error 500 on POST /api/calculate');
    T.eq(kept.entry.detail, 'Kratos could not be started.');
    T.eq(F.serverError(500, 'disk full', 'POST', '/api/feedback'), null);
    T.eq(F.seen().length, 1);
    F.forgetForTests();
  });

  test('feedback: a calculation Kratos stopped says the stage', function () {
    F.forgetForTests();
    var kept = F.calculationFailed({ ok: false, returncode: 1, error: 'Diverged.',
                                     stage: { index: 3, of: 5, name: 'Excavation' } });
    T.eq(kept.entry.what, 'Calculation failed in stage 3 of 5 ("Excavation")');
    T.eq(kept.entry.detail, 'Diverged.');
    T.eq(F.calculationFailed({ ok: false, returncode: null, stage: null }).entry.what,
         'Calculation failed (timed out)');
    F.forgetForTests();
  });

  test('feedback: a script error says where it happened', function () {
    F.forgetForTests();
    var kept = F.uncaught({ message: 'x is undefined', filename: 'http://127.0.0.1:8000/js/lines.js',
                            lineno: 12 });
    T.eq(kept.entry.detail, 'x is undefined (lines.js:12)');
    T.eq(F.uncaught({ reason: new Error('nope') }).entry.detail.split('\n')[0], 'nope');
    F.forgetForTests();
  });

  test('feedback: the payload puts the error it is about first, once', function () {
    F.forgetForTests();
    var first = F.notice('first', 'a', 1000).entry;
    var about = F.notice('second', 'b', 2000).entry;
    var body = F.payload({
      kind: 'bug', message: '  It broke.  ', name: ' Ben ', error: about,
      context: { mode: 'Mesh' }, sessionLog: ['> mesh', 'Mesh failed'], modelHistory: [],
      view: 'AAAA', attachments: [{ name: 'a.txt', data: 'data:,x', size: 1, type: 'text/plain' }],
      includeProject: false, run: 'dike_2026-11-17_14-00'
    });
    T.eq(body.message, 'It broke.');
    T.eq(body.name, 'Ben');
    T.eq(body.errors.map(function (e) { return e.what; }), ['second', 'first']);
    T.eq(body.session_log, '> mesh\nMesh failed');
    T.eq(body.model_history, '');
    T.eq(body.view, 'AAAA');
    T.eq(body.attachments, [{ name: 'a.txt', data: 'data:,x' }], 'the name and the data only');
    T.eq(body.include_project, false);
    T.eq(body.run, 'dike_2026-11-17_14-00');
    T.eq(first.what, 'first');
    F.forgetForTests();
  });

  test('feedback: a report needs a kind, and words unless it is about an error', function () {
    T.eq(F.refusal({ kind: 'bug', message: '  ' }),
         'Write what happened, or what you would like to see.');
    T.eq(F.refusal({ kind: 'bug', message: '', error: { what: 'x' } }), null);
    T.eq(F.refusal({ kind: 'praise', message: 'x' }), 'Choose what kind of feedback this is.');
    T.eq(F.refusal({ kind: 'good', message: 'nice' }), null);
  });

  test('feedback: a long log keeps its last lines and says how many it left out', function () {
    var lines = ['1', '2', '3', '4', '5'];
    T.eq(F.lastLines(lines, 2), '(3 earlier lines left out)\n4\n5');
    T.eq(F.lastLines(lines, 10), '1\n2\n3\n4\n5');
  });

  test('feedback: pasted or dropped files are found; text is left alone', function () {
    var png = { type: 'image/png', size: 10, name: 'image.png' };
    var doc = { type: 'application/pdf', size: 10, name: 'notes.pdf' };
    var pasted = [{ kind: 'string', type: 'text/html', getAsFile: function () { return null; } },
                  { kind: 'file', type: 'image/png', getAsFile: function () { return png; } }];
    T.eq(F.filesIn(pasted), [{ file: png, pasted: true }]);
    T.eq(F.filesIn([{ kind: 'string', type: 'text/plain', getAsFile: function () { return null; } }]), []);
    T.eq(F.filesIn([png, doc]), [{ file: png, pasted: false }, { file: doc, pasted: false }],
         'a drop gives the files themselves, of any kind');
    T.eq(F.filesIn(null), []);
  });

  test('feedback: a pasted picture is a screenshot; a file keeps its name', function () {
    T.eq(F.fileName({ type: 'image/png', name: 'image.png' }, true), 'screenshot.png');
    T.eq(F.fileName({ type: 'image/jpeg', name: 'image.jpg' }, true), 'screenshot.jpg');
    T.eq(F.fileName({ type: 'image/png', name: 'wall.png' }, false), 'wall.png');
    T.eq(F.fileName({ type: '', name: '' }, false), 'file');
  });

  test('feedback: at most 10 files of at most 15 MB each', function () {
    T.eq(F.fileRefusal({ name: 'a.docx', size: 1000 }, 0), null);
    T.ok(/10 files at most/.test(F.fileRefusal({ name: 'a', size: 1 }, F.MAX_FILES)));
    T.eq(F.fileRefusal({ name: 'film.mp4', size: F.MAX_FILE_BYTES + 1 }, 0),
         'film.mp4 is larger than 15 MB. Add a smaller file.');
    T.eq([F.sizeSaid(830), F.sizeSaid(12400), F.sizeSaid(1440000)], ['830 bytes', '12 kB', '1.4 MB']);
  });

  test('feedback: the keys for a screenshot are the computer\'s', function () {
    T.eq(F.screenshotKeys('Win32'), { take: 'Win+Shift+S', paste: 'Ctrl+V' });
    T.eq(F.screenshotKeys('MacIntel').paste, 'Cmd+V');
    T.eq(F.screenshotKeys('Linux x86_64').take, 'your screenshot tool');
  });

  test('feedback: after a save the note names the file and how many reports it holds', function () {
    var said = F.savedSaid({ name: 'styx-feedback-2026-11-17-ben.zip', folder: 'C:/fb', reports: 3 });
    T.eq(said.text, 'Report added to styx-feedback-2026-11-17-ben.zip');
    T.ok(/^In C:\/fb\. The file holds 3 reports now\./.test(said.detail));
    T.ok(/holds 1 report now/.test(F.savedSaid({ name: 'a.zip', folder: 'f', reports: 1 }).detail));
  });

  test('feedback: the context leaves out what is empty', function () {
    var said = F.context({ mode: 'Mesh', window: null, windows: ['Mesh properties'],
                           selection: '', project: 'Dike', dimension: '2D' });
    T.eq(said, { mode: 'Mesh', 'open windows': 'Mesh properties', project: 'Dike',
                 dimension: '2D' });
  });
})();
