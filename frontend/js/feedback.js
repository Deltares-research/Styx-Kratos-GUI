/* ══════════════════════════════════════════════════════════════════
   feedback.js — what a feedback report says, and the errors it can be about.

   The half with no DOM, like results-render.js: frontend/tests/run_headless.py runs it.
   feedback-dialog.js is the window, the buttons and the "Save a report" offer.

   ── The errors ───────────────────────────────────────────────────────────

   Three kinds of error are kept as they happen, so a report can say what went wrong
   before it was written, and so the app can offer a report at once:

   *   an answer of 500 or more from the server (api.js): a mesh gmsh could not make,
       a Kratos that would not start, or a fault in Styx itself;
   *   a calculation that failed (calculate.js); a run the user stopped is not one;
   *   an error in the page's own scripts.

   `notice` keeps each one and tells the listeners about it, unless the same error was
   seen less than a minute before: a failure that repeats on every click is offered once.

   ── The report ───────────────────────────────────────────────────────────

   `payload` is the body of POST /api/feedback (backend/routes/feedback.py). The server
   adds what only it has -- the model, its own log, the open run's files -- and adds the
   report to the writer's ZIP file of the day (core/feedback.py). The kinds are the same
   words as `kratos-cli feedback --kind`.

   ── The files ────────────────────────────────────────────────────────────

   Besides the pictures of the whole window and of the view, the writer may add files of their own: paste a
   screenshot (taken with Win+Shift+S, say) into the window, drop files on it, or choose
   them. Any kind of file goes: a picture, a document, a model. `filesIn` finds the files
   among what was pasted or dropped; `fileRefusal` says why one cannot go.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Feedback = (function () {

  /* Same ids, same words as core/feedback.py KINDS. */
  var KINDS = [
    { id: 'bug', label: 'Something is wrong',
      hint: 'What did you do, what did you expect, and what happened instead?' },
    { id: 'confusing', label: 'Something is confusing',
      hint: 'What was hard to understand or to find?' },
    { id: 'missing', label: 'Something is missing',
      hint: 'What do you need that Styx cannot do yet?' },
    { id: 'good', label: 'Something works well',
      hint: 'What did you like? It tells us what to keep.' }
  ];

  var MAX_ERRORS = 20;          // kept, newest last; a report sends them all
  var REPEAT_MS = 60 * 1000;    // the same error within this is not offered again
  var MAX_LOG_LINES = 2000;     // of the Session log and the Model history

  var errors = [];
  var listeners = [];

  function kind(id) {
    return KINDS.filter(function (k) { return k.id === id; })[0] || null;
  }

  function two(n) { return (n < 10 ? '0' : '') + n; }

  function clock(date) {
    return two(date.getHours()) + ':' + two(date.getMinutes()) + ':' + two(date.getSeconds());
  }

  /* Told of each new error: `fn(entry)`. Adding the same function twice adds it once. */
  function onNotice(fn) {
    if (typeof fn === 'function' && listeners.indexOf(fn) < 0) listeners.push(fn);
  }

  function offNotice(fn) {
    listeners = listeners.filter(function (known) { return known !== fn; });
  }

  /* Keep an error: `what` in a few words, `detail` the reason as it was said. Answers the
     entry `{when, what, detail}`, and whether it was told to the listeners. */
  function notice(what, detail, now) {
    var at = typeof now === 'number' ? now : Date.now();
    var said = String(detail || '');
    var repeat = errors.some(function (e) {
      return e.what === what && e.detail === said && at - e.at < REPEAT_MS;
    });
    var entry = { when: clock(new Date(at)), what: String(what), detail: said, at: at };
    errors.push(entry);
    if (errors.length > MAX_ERRORS) errors.splice(0, errors.length - MAX_ERRORS);
    if (!repeat) {
      listeners.slice().forEach(function (fn) {
        try { fn(entry); } catch (err) { setTimeout(function () { throw err; }, 0); }
      });
    }
    return { entry: entry, told: !repeat };
  }

  /* api.js: an answer of 500 or more. The feedback routes are left out: an offer to save
     a report because saving a report failed would only fail again. */
  function serverError(status, message, method, path) {
    if (String(path || '').indexOf('/api/feedback') === 0) return null;
    return notice('Server error ' + status + ' on ' + method + ' ' + path, message);
  }

  /* calculate.js: a run that failed (`ok` false in the answer of /api/calculate). A run
     the user stopped (`stopped` true) never comes here. */
  function calculationFailed(result) {
    var stage = result && result.stage;
    var what = 'Calculation failed' + (stage ? ' in stage ' + stage.index + ' of ' + stage.of
                                               + ' ("' + stage.name + '")' : '')
             + (result && result.returncode === null ? ' (timed out)' : '');
    return notice(what, (result && result.error) || 'Kratos exited without saying why.');
  }

  /* An `error` or `unhandledrejection` event of the page. A server answer that no caller
     caught is not one: it has a `status` (api.js), a refusal is the server's own words,
     and an answer of 500 or more was offered already by `serverError`. */
  function uncaught(event) {
    var reason = event && event.reason;
    if (reason && reason.status) return null;
    var text = reason ? (reason.message || String(reason))
                      : ((event && event.message) || 'Unknown error');
    var where = event && event.filename
      ? ' (' + String(event.filename).split('/').pop() + ':' + event.lineno + ')' : '';
    var stack = reason && reason.stack ? '\n' + reason.stack
      : (event && event.error && event.error.stack ? '\n' + event.error.stack : '');
    return notice('Script error in the page', text + where + stack);
  }

  /* The errors kept, oldest first, as a report sends them. */
  function seen() {
    return errors.map(function (e) { return { when: e.when, what: e.what, detail: e.detail }; });
  }

  /* The last `max` lines of `lines` (an array of strings), as one text. */
  function lastLines(lines, max) {
    var list = lines || [];
    var keep = max || MAX_LOG_LINES;
    var cut = list.length > keep ? ['(' + (list.length - keep) + ' earlier lines left out)']
                                     .concat(list.slice(list.length - keep)) : list;
    return cut.join('\n');
  }

  /* Where in the app the report was written, from a plain snapshot of it (feedback-dialog.js
     `snapshot`), as the lines "Where" of report.txt. Empty values are left out. */
  function context(s) {
    var said = {};
    function put(key, value) {
      if (value !== null && value !== undefined && value !== '') said[key] = value;
    }
    s = s || {};
    put('mode', s.mode);
    put('window', s.window);
    put('open windows', s.windows && s.windows.length ? s.windows.join(', ') : null);
    put('selected', s.selection);
    put('stage', s.stage);
    put('results', s.results);
    put('project', s.project);
    put('dimension', s.dimension);
    put('units', s.units);
    put('screen', s.screen);
    put('browser', s.browser);
    put('address', s.address);
    return said;
  }

  /* The body of POST /api/feedback. `fields`: kind, message, name, context (from `context`),
     sessionLog and modelHistory (arrays of lines), view (the picture of the view, base64
     PNG, or null), windowPicture (the picture of the whole Styx window, the same),
     attachments (the writer's files, each {name, data}: data a data URL),
     includeProject, run
     (the open run's id or null), error (the entry the report is about, or null: it goes
     first). */
  function payload(fields) {
    var f = fields || {};
    var list = seen();
    if (f.error) {
      list = list.filter(function (e) {
        return !(e.when === f.error.when && e.what === f.error.what && e.detail === f.error.detail);
      });
      list.unshift({ when: f.error.when, what: f.error.what, detail: f.error.detail });
    }
    return {
      kind: f.kind || 'bug',
      message: String(f.message || '').trim(),
      name: String(f.name || '').trim(),
      context: f.context || {},
      errors: list,
      session_log: lastLines(f.sessionLog),
      model_history: lastLines(f.modelHistory),
      view: f.view || null,
      window_picture: f.windowPicture || null,
      attachments: (f.attachments || []).map(function (a) { return { name: a.name, data: a.data }; }),
      include_project: f.includeProject !== false,
      run: f.run || null
    };
  }

  /* Why the report cannot be sent yet, or null. A report after an error may have no words:
     the error says what happened. */
  function refusal(fields) {
    var f = fields || {};
    if (!kind(f.kind)) return 'Choose what kind of feedback this is.';
    if (!String(f.message || '').trim() && !f.error) {
      return 'Write what happened, or what you would like to see.';
    }
    return null;
  }

  /* ── The files ───────────────────────────────────────────────────────── */

  var MAX_FILES = 10;                       // core/feedback.py MAX_ATTACHMENTS
  var MAX_FILE_BYTES = 15 * 1000 * 1000;    // core/feedback.py MAX_ATTACHMENT_BYTES

  /* The files among `items`: a paste's clipboardData.items (each with `kind` and
     `getAsFile`) or a drop's dataTransfer.files (each a File). Each comes as {file,
     pasted}: a pasted picture has no name of its own. Empty when there is none, so that a
     paste of text is left to the text box. */
  function filesIn(items) {
    var found = [];
    Array.prototype.forEach.call(items || [], function (item) {
      if (!item) return;
      if (typeof item.getAsFile === 'function') {
        if (item.kind && item.kind !== 'file') return;
        var file = item.getAsFile();
        if (file) found.push({ file: file, pasted: true });
      } else {
        found.push({ file: item, pasted: false });
      }
    });
    return found;
  }

  /* The name a file goes by in the report: its own, or `screenshot.<type>` for a picture
     pasted from the clipboard, which the browser calls `image.png`. */
  function fileName(file, pasted) {
    var type = String(file.type || '');
    if (pasted && /^image\//.test(type)) {
      return 'screenshot.' + (type === 'image/jpeg' ? 'jpg' : type.slice(6).split('+')[0]);
    }
    return file.name || 'file';
  }

  /* Why `file` cannot be added to the `count` files there are, or null. */
  function fileRefusal(file, count) {
    if ((count || 0) >= MAX_FILES) {
      return 'A report can hold ' + MAX_FILES + ' files at most. Put the others in a second report.';
    }
    if (file.size > MAX_FILE_BYTES) {
      return (file.name || 'The file') + ' is larger than ' + MAX_FILE_BYTES / 1e6
           + ' MB. Add a smaller file.';
    }
    return null;
  }

  /* A file's size in words: "830 bytes", "12 kB", "1.4 MB". */
  function sizeSaid(bytes) {
    if (bytes < 1000) return bytes + ' bytes';
    if (bytes < 1e6) return Math.round(bytes / 1000) + ' kB';
    return (Math.round(bytes / 1e5) / 10) + ' MB';
  }

  /* The keys to take a screenshot and paste it, on the computer `platform` (navigator's). */
  function screenshotKeys(platform) {
    if (/Mac|iPhone|iPad/.test(platform || '')) {
      return { take: 'Cmd+Ctrl+Shift+4', paste: 'Cmd+V' };
    }
    if (/Win/.test(platform || '')) return { take: 'Win+Shift+S', paste: 'Ctrl+V' };
    return { take: 'your screenshot tool', paste: 'Ctrl+V' };
  }

  /* What the note after a save says: the file, and how many reports it holds. */
  function savedSaid(answer) {
    var count = answer.reports || 1;
    return {
      text: 'Report added to ' + answer.name,
      detail: 'In ' + answer.folder + '. The file holds ' + count
            + (count === 1 ? ' report' : ' reports') + ' now. At the end of the day, send '
            + 'this one file to the Styx team, or put it in the shared folder.'
    };
  }

  /* Bytes (a Uint8Array) as base64, in pieces: one call with every byte overflows the
     stack on a large picture. */
  function base64(bytes) {
    var parts = [];
    for (var i = 0; i < bytes.length; i += 0x8000) {
      parts.push(String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000)));
    }
    return btoa(parts.join(''));
  }

  /* The errors kept are forgotten; the listeners stay. */
  function forgetForTests() {
    errors = [];
  }

  return {
    KINDS: KINDS, REPEAT_MS: REPEAT_MS, MAX_ERRORS: MAX_ERRORS, kind: kind, clock: clock,
    onNotice: onNotice, offNotice: offNotice, notice: notice, serverError: serverError,
    calculationFailed: calculationFailed, uncaught: uncaught, seen: seen,
    lastLines: lastLines, context: context, payload: payload, refusal: refusal,
    filesIn: filesIn, fileName: fileName, fileRefusal: fileRefusal, sizeSaid: sizeSaid,
    screenshotKeys: screenshotKeys, savedSaid: savedSaid,
    MAX_FILES: MAX_FILES, MAX_FILE_BYTES: MAX_FILE_BYTES,
    base64: base64, forgetForTests: forgetForTests
  };
})();
