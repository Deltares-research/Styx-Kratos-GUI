/* ══════════════════════════════════════════════════════════════════
   feedback-dialog.js — the Feedback window, and the offer to save a report after an error.

   Ways in:

   *   the Feedback button at the end of the main toolbar, Help > Send feedback…, and
       `feedback [text]` in the command box (js/patches.js routes all three here);
   *   the small speech-bubble button in the title bar of every window: the report then
       says which window it is about;
   *   "Save a report" in the note that comes up after an error (feedback.js `notice`).

   The window asks for little: the kind, a few sentences, and a name if the user wants to
   give one (kept in this browser for the next report). Files of their own may be added: a
   screenshot pasted in (Ctrl+V), or any file dropped on the window or chosen. The rest is
   added without asking: where in the app it was written, a picture of the view, the
   Session log, the Model history and the errors seen. The server adds the model, its own log and the open
   run's files, and adds the report to the writer's ZIP file of the day, in the feedback
   folder on this computer. Nothing is sent over the internet.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.FeedbackDialog = (function () {

  var TITLE = 'Send feedback';
  var NAME_KEY = 'styx-feedback-name';
  var NOTE_ID = 'feedback-note';
  var OFFER_SECONDS = 45;        // an offer after an error goes away by itself after this

  var installed = false;
  var openShell = null;
  var noteTimer = null;

  function log(kind, line) {
    if (App.Command && App.Command[kind]) App.Command[kind](line);
  }

  /* ── Where the user is ─────────────────────────────────────────────────── */

  function modeLabel(mode) {
    if (mode === 'results') return 'Results';
    var found = (App.MODES || []).filter(function (m) { return m.id === mode; })[0];
    return found ? found.label : mode;
  }

  /* The titles of the windows open now, bottom first, the Feedback window left out. */
  function openWindows() {
    var layer = document.getElementById('modal-layer');
    if (!layer) return [];
    return Array.prototype.map.call(layer.querySelectorAll('.dialog .dlg-title'), function (t) {
      return t.textContent.trim();
    }).filter(function (title) { return title && title !== TITLE; });
  }

  function stageName() {
    var stages = (App.PROJECT && App.PROJECT.stages) || [];
    var id = App.state && App.state.phase;
    var found = stages.filter(function (s) { return s.id === id; })[0];
    return found ? found.name : null;
  }

  function resultsSaid() {
    if (!App.Results || !App.Results.current || !App.Results.current()) return null;
    var field = App.Results.field && App.Results.field();
    var stage = App.Results.stage && App.Results.stage();
    return 'run ' + App.Results.current()
      + (stage ? ', stage ' + stage : '')
      + (field && field.field ? ', ' + field.field : '');
  }

  /* A plain snapshot of the app, for feedback.js `context`. `window` is the one the report
     is about, when it came from a window's own button. */
  function snapshot(aboutWindow) {
    var mode = App.state && App.state.mode;
    var project = App.PROJECT || {};
    return {
      mode: modeLabel(mode),
      window: aboutWindow || null,
      windows: openWindows(),
      selection: App.state && App.state.selection,
      stage: mode === 'staged' ? stageName() : null,
      results: resultsSaid(),
      project: project.name || null,
      dimension: project.dimension ? project.dimension + 'D' : null,
      units: project.unit_system || null,
      screen: window.innerWidth + ' x ' + window.innerHeight + ' px',
      browser: navigator.userAgent,
      address: window.location.href
    };
  }

  function linesOf(id) {
    var box = document.getElementById(id);
    if (!box) return [];
    return Array.prototype.map.call(box.querySelectorAll('.cmd-line'), function (line) {
      return line.textContent;
    });
  }

  /* A picture of the view as base64 PNG, or null when there is none: the same drawing as
     Save picture, of the view as it is on screen. */
  function screenshot() {
    var P = App.Picture;
    if (!P || !App.Viewport || !App.Viewport.pictureView) return Promise.resolve(null);
    var asked = { screenZoom: true };
    return Promise.resolve().then(function () {
      return P.commonFrame(asked);
    }).then(function (frame) {
      var picture = P.compose(asked, frame);
      return picture ? P.encode(picture, 'png') : null;
    }).then(function (bytes) {
      return bytes ? App.Feedback.base64(bytes) : null;
    }).catch(function () { return null; });
  }

  function rememberedName() {
    try { return window.localStorage.getItem(NAME_KEY) || ''; } catch (e) { return ''; }
  }

  function rememberName(name) {
    try { window.localStorage.setItem(NAME_KEY, name); } catch (e) { /* private window */ }
  }

  /* ── The window ────────────────────────────────────────────────────────── */

  /* The line under the switches: what goes in the report without being asked. */
  function alsoInTheReport(where) {
    var errors = App.Feedback.seen().length;
    var parts = ['that it is about ' + (where.window ? 'the window "' + where.window + '"'
                                                     : 'the ' + where.mode + ' mode'),
                 'the Session log', 'the log of the server', 'the version of Styx'];
    if (errors) parts.push(errors === 1 ? 'the error seen so far' : 'the ' + errors + ' errors seen so far');
    if (where.results) parts.push('the log of the open calculation');
    return 'Also in the report: ' + parts.slice(0, -1).join(', ') + ' and '
         + parts[parts.length - 1] + '.';
  }

  /* options: kind ('bug', ...), message (text to start with), error (the entry of
     feedback.js the report is about), window (the title of the window it is about). */
  function open(options) {
    var opts = options || {};
    if (openShell) {
      openShell.dialog.querySelector('textarea').focus();
      return openShell;
    }
    var el = App.UI.el;
    var picture = screenshot();      // started now: the view as it is, before typing
    var where = snapshot(opts.window);
    var chosen = App.Feedback.kind(opts.kind) ? opts.kind : 'bug';
    var text, name, withPicture, withModel, message, saveButton, saving = false;
    var added = [], filesBox = null, chooser = null;   // the writer's own files

    function chooseButton(label) {
      return el('button.btn.btn-sm.feedback-files-choose', {
        type: 'button', text: label, onclick: function () { chooser.click(); }
      });
    }

    /* The files box: how to add files, and the files added, each with a way to remove it. */
    function drawFiles() {
      filesBox.textContent = '';
      filesBox.classList.toggle('has-files', added.length > 0);
      var keys = App.Feedback.screenshotKeys(navigator.platform);
      if (!added.length) {
        filesBox.appendChild(el('div.feedback-files-text', null, [
          'Add a screenshot or other files: press ' + keys.take + ', select a part of the '
          + 'screen, then press ' + keys.paste + ' here. Or drop files here, or ',
          chooseButton('Choose files…')
        ]));
        return;
      }
      added.forEach(function (a, i) {
        var picture = /^image\//.test(a.type);
        filesBox.appendChild(el('div.feedback-file', null, [
          picture ? el('img.feedback-file-thumb', { src: a.data, alt: a.name })
                  : el('span.feedback-file-icon', { text: (a.name.split('.').pop() || 'file').slice(0, 4) }),
          el('span.feedback-file-name', { text: a.name, title: a.name }),
          el('span.feedback-file-size', { text: App.Feedback.sizeSaid(a.size) }),
          el('button.btn.btn-sm.feedback-file-remove', {
            type: 'button', text: 'Remove',
            onclick: function () { added.splice(i, 1); drawFiles(); }
          })
        ]));
      });
      if (added.length < App.Feedback.MAX_FILES) {
        filesBox.appendChild(el('div.feedback-files-text', null, [
          'Paste or drop more, or ', chooseButton('Choose files…')
        ]));
      }
    }

    function addFile(file, pasted) {
      var refused = App.Feedback.fileRefusal(file, added.length);
      if (refused) { message.textContent = refused; return; }
      var entry = { name: App.Feedback.fileName(file, pasted), type: String(file.type || ''),
                    size: file.size, data: null };
      added.push(entry);      // now, so that the count holds for files read at the same time
      var reader = new FileReader();
      reader.onload = function () {
        if (!openShell) return;
        entry.data = String(reader.result);
        message.textContent = '';
        drawFiles();
      };
      reader.onerror = function () {
        added.splice(added.indexOf(entry), 1);
        message.textContent = entry.name + ' could not be read.';
        drawFiles();
      };
      reader.readAsDataURL(file);
    }

    function addFiles(found) {
      found.forEach(function (f) { addFile(f.file, f.pasted); });
    }

    /* A paste anywhere while the window is open: files are taken, text is left alone.
       A copy from an office program can hold both: it is text, then. */
    function onPaste(event) {
      var data = event.clipboardData;
      if (!data || Array.prototype.indexOf.call(data.types || [], 'text/plain') >= 0) return;
      var found = App.Feedback.filesIn(data.items);
      if (!found.length) return;
      event.preventDefault();
      addFiles(found);
    }

    function onDragOver(event) {
      if (!event.dataTransfer || Array.prototype.indexOf.call(event.dataTransfer.types || [], 'Files') < 0) return;
      event.preventDefault();
      filesBox.classList.add('drop-here');
    }

    function onDrop(event) {
      filesBox.classList.remove('drop-here');
      var found = App.Feedback.filesIn(event.dataTransfer && event.dataTransfer.files);
      if (!found.length) return;
      event.preventDefault();
      addFiles(found);
    }

    function hintFor(id) { return App.Feedback.kind(id).hint; }

    function submit() {
      if (saving) return;
      var fields = { kind: chosen, message: text.value, error: opts.error || null };
      var refused = App.Feedback.refusal(fields);
      if (refused) {
        message.textContent = refused;
        text.focus();
        return;
      }
      if (added.some(function (a) { return a.data === null; })) {
        message.textContent = 'A file is still being read. Click Save report again in a moment.';
        return;
      }
      saving = true;
      message.textContent = 'Saving the report…';
      if (saveButton) saveButton.disabled = true;
      rememberName(name.value.trim());
      (withPicture.checked ? picture : Promise.resolve(null)).then(function (png) {
        return App.Api.post('/api/feedback', App.Feedback.payload({
          kind: chosen, message: text.value, name: name.value, error: opts.error || null,
          context: App.Feedback.context(where),
          sessionLog: linesOf('cmd-log'), modelHistory: linesOf('cmd-history'),
          view: png, attachments: added, includeProject: withModel.checked,
          run: App.Results && App.Results.current ? App.Results.current() : null
        }));
      }).then(function (answer) {
        saving = false;
        log('ok', 'Feedback saved: ' + answer.report + ' in ' + answer.path);
        if (openShell) openShell.close();
        saved(answer);
      }, function (error) {
        saving = false;
        if (saveButton) saveButton.disabled = false;
        message.textContent = 'The report could not be saved: ' + error.message;
      });
    }

    function onKey(event) {
      // Over another window, Escape closes this one only: both listen on the document.
      if (event.key !== 'Escape' || !openShell) return;
      event.stopImmediatePropagation();
      event.preventDefault();
      openShell.close();
    }

    var shell = App.Dialogs.open({
      title: TITLE, width: 580, height: opts.error ? 600 : 540,
      buttons: [{ label: 'Save report', primary: true, keepOpen: true, onClick: submit },
                { label: 'Cancel' }],
      onClose: function () {
        window.removeEventListener('keydown', onKey, true);
        document.removeEventListener('paste', onPaste);
        openShell = null;
      },
      build: function (body) {
        body.classList.add('feedback-body');
        body.appendChild(el('p.feedback-text', {
          text: 'Tell us what happened, or what you would like to see. The report is saved '
              + 'in a file on this computer. Nothing is sent over the internet.'
        }));
        if (opts.error) {
          body.appendChild(el('div.feedback-error', null, [
            el('strong', { text: opts.error.what }),
            el('div.feedback-error-detail', { text: String(opts.error.detail || '').split('\n')[0] })
          ]));
        }
        var kinds = el('div.feedback-kinds', { role: 'radiogroup' });
        App.Feedback.KINDS.forEach(function (k) {
          var input = el('input', { type: 'radio', name: 'feedback-kind', value: k.id });
          input.checked = k.id === chosen;
          input.addEventListener('change', function () {
            chosen = k.id;
            text.placeholder = hintFor(chosen);
          });
          kinds.appendChild(el('label.feedback-kind', null, [input, el('span', { text: k.label })]));
        });
        body.appendChild(kinds);

        text = el('textarea.mesh-setting-control.feedback-message', {
          rows: 6, name: 'feedback-message', placeholder: hintFor(chosen)
        });
        text.value = opts.message || '';
        body.appendChild(text);

        name = el('input.mesh-setting-control.feedback-name', {
          type: 'text', name: 'feedback-name', placeholder: 'Your name (optional)'
        });
        name.value = rememberedName();
        body.appendChild(name);

        withPicture = el('input', { type: 'checkbox', name: 'feedback-picture' });
        withPicture.checked = true;
        withModel = el('input', { type: 'checkbox', name: 'feedback-model' });
        withModel.checked = true;
        body.appendChild(el('div.feedback-options', null, [
          el('label', null, [withPicture, el('span', { text: 'Add a picture of the view' })]),
          el('label', null, [withModel, el('span', { text: 'Add the model' })])
        ]));

        filesBox = el('div.feedback-files');
        chooser = el('input', { type: 'file', multiple: true, name: 'feedback-files' });
        chooser.style.display = 'none';
        chooser.addEventListener('change', function () {
          addFiles(App.Feedback.filesIn(chooser.files));
          chooser.value = '';
        });
        body.appendChild(filesBox);
        body.appendChild(chooser);

        body.appendChild(el('p.feedback-also', { text: alsoInTheReport(where) }));
        message = el('div.mesh-settings-message.feedback-message-line');
        body.appendChild(message);
      }
    });
    shell.dialog.classList.add('feedback-window');
    saveButton = shell.dialog.querySelector('.dlg-foot .btn-primary');
    drawFiles();
    shell.dialog.addEventListener('dragover', onDragOver);
    shell.dialog.addEventListener('dragleave', function () { filesBox.classList.remove('drop-here'); });
    shell.dialog.addEventListener('drop', onDrop);
    window.addEventListener('keydown', onKey, true);
    document.addEventListener('paste', onPaste);
    openShell = shell;
    text.focus();
    return shell;
  }

  /* ── The note in the corner ────────────────────────────────────────────── */

  function hideNote() {
    if (noteTimer) { clearTimeout(noteTimer); noteTimer = null; }
    var note = document.getElementById(NOTE_ID);
    if (note) note.remove();
  }

  /* A small note above the status bar: `text`, its `buttons` ({label, onClick, primary}),
     and a close cross. One at a time: a new one takes the place of the last. */
  function showNote(kind, text, detail, buttons) {
    hideNote();
    var el = App.UI.el;
    var row = el('div.feedback-note-buttons');
    (buttons || []).forEach(function (b) {
      row.appendChild(el('button.btn.btn-sm' + (b.primary ? '.btn-primary' : ''), {
        type: 'button', text: b.label,
        onclick: function () { hideNote(); b.onClick(); }
      }));
    });
    var note = el('div#' + NOTE_ID + '.feedback-note.feedback-note-' + kind, { role: 'status' }, [
      el('button.feedback-note-x', { type: 'button', text: '✕', title: 'Close',
                                     onclick: hideNote }),
      el('div.feedback-note-text', { text: text }),
      detail ? el('div.feedback-note-detail', { text: detail }) : null,
      row
    ]);
    document.body.appendChild(note);
    noteTimer = setTimeout(hideNote, OFFER_SECONDS * 1000);
    return note;
  }

  /* After an error: offer a report about it. */
  function offer(entry) {
    if (openShell) return null;
    var first = String(entry.detail || '').split('\n')[0];
    return showNote('error', 'Something went wrong: ' + entry.what + '.',
                    first.length > 200 ? first.slice(0, 200) + '…' : first, [
      { label: 'Save a report', primary: true,
        onClick: function () { open({ kind: 'bug', error: entry }); } }
    ]);
  }

  /* After a save: where the file is, and a way to see it. */
  function saved(answer) {
    var said = App.Feedback.savedSaid(answer);
    return showNote('ok', said.text, said.detail, [
      { label: 'Show folder', primary: true, onClick: showFolder }
    ]);
  }

  function showFolder() {
    return App.Api.post('/api/feedback/folder', {}).then(function (answer) {
      if (!answer.opened) {
        log('note', 'The feedback reports are in ' + answer.folder
                    + (answer.reason ? ' (' + answer.reason + ')' : '') + '.');
      }
      return answer;
    }, function (error) {
      log('err', 'The feedback folder could not be opened: ' + error.message);
    });
  }

  /* ── A button in every window ──────────────────────────────────────────── */

  var BUBBLE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H10l-4 4v-4H4z"/>'
             + '<path d="M8 9.5h8M8 12.5h5"/></svg>';

  /* The speech bubble before the close cross of `dialog`, unless it has one, or is the
     Feedback window itself. */
  function addWindowButton(dialog) {
    var head = dialog && dialog.querySelector && dialog.querySelector('.dlg-head');
    if (!head || head.querySelector('.dlg-feedback')) return;
    var title = head.querySelector('.dlg-title');
    var said = title ? title.textContent.trim() : '';
    if (said === TITLE) return;
    var button = App.UI.el('button.dlg-feedback', {
      type: 'button', title: 'Send feedback about this window', html: BUBBLE
    });
    button.addEventListener('mousedown', function (event) { event.stopPropagation(); });
    button.addEventListener('click', function () {
      var now = head.querySelector('.dlg-title');
      open({ window: now ? now.textContent.trim() : said });
    });
    var close = head.querySelector('.dlg-x');
    head.insertBefore(button, close || null);
  }

  /* Every window opens in #modal-layer, from js/dialogs.js or from the live code alike:
     watching the layer gives each one the button, with no window having to ask. */
  function watchWindows() {
    var layer = document.getElementById('modal-layer');
    if (!layer || typeof MutationObserver !== 'function') return;
    Array.prototype.forEach.call(layer.querySelectorAll('.dialog'), addWindowButton);
    new MutationObserver(function (changes) {
      changes.forEach(function (change) {
        Array.prototype.forEach.call(change.addedNodes, function (node) {
          if (node.classList && node.classList.contains('dialog')) addWindowButton(node);
        });
      });
    }).observe(layer, { childList: true });
  }

  /* `feedback [text]` in the command box: the window, with the text in it. `false` when
     it is not this command. */
  function command(text) {
    var said = String(text || '').trim();
    var words = said.split(/\s+/);
    if (words[0].toLowerCase() !== 'feedback') return false;
    if (App.Command && App.Command.write) App.Command.write('echo', '> ' + said);
    open({ message: said.slice(words[0].length).trim() });
    return true;
  }

  function install() {
    if (installed || typeof document === 'undefined') return;
    installed = true;
    App.Feedback.onNotice(offer);
    window.addEventListener('error', function (event) { App.Feedback.uncaught(event); });
    window.addEventListener('unhandledrejection', function (event) { App.Feedback.uncaught(event); });
    watchWindows();
  }

  return {
    TITLE: TITLE, open: open, command: command, offer: offer, saved: saved, showFolder: showFolder,
    hideNote: hideNote, snapshot: snapshot, screenshot: screenshot,
    addWindowButton: addWindowButton, install: install,
    isOpen: function () { return !!openShell; }
  };
})();

App.FeedbackDialog.install();
