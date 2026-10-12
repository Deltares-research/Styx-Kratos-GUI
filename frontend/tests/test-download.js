/* download.js — the save window, and what it writes to.

   Chrome on Windows does not ask where a download goes, so a save that only
   ever made an <a download> gave the user no window and no choice of folder.
   These pin the picker path down without opening a real dialog. */

function withPickers(pickers, body) {
  var saved = window.showSaveFilePicker;
  if ('file' in pickers) window.showSaveFilePicker = pickers.file;
  else delete window.showSaveFilePicker;

  function restore() {
    if (saved) window.showSaveFilePicker = saved;
    else delete window.showSaveFilePicker;
  }

  var outcome;
  try {
    outcome = body();
  } catch (error) {
    restore();
    throw error;
  }
  if (outcome && typeof outcome.then === 'function') {
    return outcome.then(function (v) { restore(); return v; },
                        function (e) { restore(); throw e; });
  }
  restore();
  return outcome;
}

/* A stand-in for a FileSystemFileHandle: records what was written to it. */
function fakeFileHandle(name) {
  var handle = { name: name, written: null, closed: false };
  handle.createWritable = function () {
    return Promise.resolve({
      write: function (text) { handle.written = text; return Promise.resolve(); },
      close: function () { handle.closed = true; return Promise.resolve(); }
    });
  };
  return handle;
}

test('a save asks the user where the file goes when the browser can', function () {
  var asked = null;
  return withPickers({ file: function (options) {
    asked = options;
    return Promise.resolve(fakeFileHandle('project.json'));
  } }, function () {
    return App.Download.pickFile('Deep excavation.json', 'application/json')
      .then(function (handle) {
        T.ok(handle && handle.createWritable, 'the picked handle comes back to be written to');
        T.eq(asked.suggestedName, 'Deep excavation.json',
             "the dialog opens on the project's own name");
        T.eq(asked.types[0].accept['application/json'], ['.json'],
             'the extension is offered so the name survives the round trip');
      });
  });
});

test('a dismissed save window stops the save instead of downloading anyway', function () {
  return withPickers({ file: function () {
    var error = new Error('The user aborted a request.');
    error.name = 'AbortError';
    return Promise.reject(error);
  } }, function () {
    return App.Download.pickFile('project.json', 'application/json')
      .then(function (handle) { T.eq(handle, App.Download.CANCELLED); });
  });
});

test('a browser with no picker falls back to the plain download', function () {
  return withPickers({}, function () {
    return App.Download.pickFile('project.json').then(function (handle) {
      T.eq(handle, null, 'no handle, and no rejection either — the download still runs');
    });
  });
});

test('a picker refused for any other reason also falls back', function () {
  return withPickers({ file: function () {
    var error = new Error('Must be handling a user gesture to show a file picker.');
    error.name = 'SecurityError';
    return Promise.reject(error);
  } }, function () {
    return App.Download.pickFile('project.json').then(function (handle) { T.eq(handle, null); });
  });
});

test('a picked file is written and closed', function () {
  var handle = fakeFileHandle('project.json');
  return App.Download.write(handle, 'ignored.json', '{"a":1}', 'application/json')
    .then(function () {
      T.eq(handle.written, '{"a":1}');
      T.ok(handle.closed, 'an unclosed writable leaves the file empty on disk');
    });
});

test('no handle still downloads, so nothing is lost where there is no picker', function () {
  var saved = App.Download.anchor, downloaded = [];
  App.Download.anchor = function (name, text, mime) { downloaded.push([name, text, mime]); };
  return App.Download.write(null, 'project.json', '{}', 'application/json')
    .then(function () {
      App.Download.anchor = saved;
      T.eq(downloaded, [['project.json', '{}', 'application/json']]);
    }, function (error) {
      App.Download.anchor = saved;
      throw error;
    });
});

/* ── File ▸ Save / Save as… ─────────────────────────────────────────────── */

function withSaveStubs(pick, body) {
  var saved = { Api: App.Api, Command: App.Command, PROJECT: App.PROJECT,
                pickFile: App.Download.pickFile, write: App.Download.write };
  var logged = [], wrote = [];
  App.Command = {
    ok: function (line) { logged.push(['ok', line]); },
    note: function (line) { logged.push(['note', line]); },
    err: function (line) { logged.push(['err', line]); }
  };
  App.PROJECT = { name: 'Deep excavation — Rotterdam Zuid' };
  App.Api = { get: function (path) {
    T.eq(path, '/api/project', 'a save is of what the server holds, not the local snapshot');
    return Promise.resolve({ name: 'Deep excavation — Rotterdam Zuid', layers: [] });
  } };
  App.Download.pickFile = pick;
  App.Download.write = function (target, name, text, mime) {
    wrote.push([target, name, text, mime]);
    return Promise.resolve();
  };
  function restore() {
    App.Api = saved.Api; App.Command = saved.Command; App.PROJECT = saved.PROJECT;
    App.Download.pickFile = saved.pickFile; App.Download.write = saved.write;
  }
  return Promise.resolve().then(function () { return body(wrote, logged); })
    .then(function (v) { restore(); return v; },
          function (e) { restore(); throw e; });
}

test('File ▸ Save asks where the project goes before it fetches it', function () {
  var asked = null, handle = fakeFileHandle('mine.json');
  return withSaveStubs(function (name, mime) {
    asked = [name, mime];
    return Promise.resolve(handle);
  }, function (wrote, logged) {
    return App.LivePatches.saveProject().then(function () {
      T.eq(asked, ['Deep excavation — Rotterdam Zuid.json', 'application/json'],
           "the window opens on the project's name, minus what a file system refuses");
      T.eq(wrote.length, 1);
      T.eq(wrote[0][0], handle, 'the file the user named is what gets written');
      T.eq(JSON.parse(wrote[0][2]).name, 'Deep excavation — Rotterdam Zuid');
      T.ok(logged.some(function (line) {
        return line[0] === 'ok' && line[1] === 'Saved mine.json.';
      }), 'the log names the file the user actually chose');
    });
  });
});

test('a dismissed save window writes nothing at all', function () {
  return withSaveStubs(function () {
    return Promise.resolve(App.Download.CANCELLED);
  }, function (wrote, logged) {
    return App.LivePatches.saveProject().then(function () {
      T.eq(wrote.length, 0);
      T.eq(logged.length, 0, 'a cancelled save is not a failure to report');
    });
  });
});
