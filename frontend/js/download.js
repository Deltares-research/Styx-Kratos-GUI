/* ══════════════════════════════════════════════════════════════════
   download.js — where a saved file goes.

   Chrome on Linux is usually set to ask where each download goes; Chrome on
   Windows is not, so File ▸ Save, Save as… and Export model… all landed
   silently in the Downloads folder with no window and no choice of name. The
   File System Access API asks on both, and this is the one place that knows
   about it.

   The picker only works on a fresh gesture: the browser refuses it once an
   await has intervened. So `pickFile` has to be called straight out of the
   click — before the project is fetched, before the mesh is asked for — and the
   handle it returns is written to afterwards. One gesture buys one window, and
   so one file: that is why an export is a single archive.

   Where there is no picker (Firefox, Safari, a file:// page) `write` falls
   back to the anchor download that was here before, so nothing is lost.

   A save of many files takes a folder, and the browser's folder window refuses Downloads,
   Desktop and Documents. So `pickFolder` asks the server first, which on the user's own
   computer opens the system's window and writes the files (backend/routes/files.py).
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Download = (function () {

  var CANCELLED = 'cancelled';

  function extensionOf(name) {
    var dot = String(name || '').lastIndexOf('.');
    return dot > 0 ? String(name).slice(dot) : '';
  }

  /* A dismissed dialog is an answer and must stop the save. Any other refusal —
     no permission, an insecure origin — is not, and drops back to a download. */
  function settle(promise) {
    return promise.then(function (handle) { return handle; }, function (error) {
      return error && error.name === 'AbortError' ? CANCELLED : null;
    });
  }

  /* `id` names a kind of save: the browser opens that window in the folder last used for
     it. */
  function pickFile(suggestedName, mime, id) {
    if (typeof window.showSaveFilePicker !== 'function') return Promise.resolve(null);
    var accept = {};
    accept[mime || 'text/plain'] = [extensionOf(suggestedName) || '.txt'];
    var options = {
      suggestedName: suggestedName,
      types: [{ description: suggestedName, accept: accept }]
    };
    if (id) options.id = id;
    return settle(window.showSaveFilePicker(options));
  }

  /* `null` where the server cannot open the window: it is on another computer, or has no
     display. The answer comes at once then, so the click still counts for the browser's.
     A window open already is the user's to answer: this save stops, and says why. */
  function serverFolder() {
    return App.Api.post('/api/files/folder', {}).then(function (answer) {
      if (answer.no_window) return null;
      if (answer.busy) {
        if (App.Command && App.Command.err) App.Command.err(answer.busy);
        return CANCELLED;
      }
      return answer.cancelled ? CANCELLED : { server: answer.id, name: answer.name };
    }, function () { return null; });
  }

  function browserFolder(id) {
    if (typeof window.showDirectoryPicker !== 'function') return Promise.resolve(null);
    return settle(window.showDirectoryPicker({ id: id, mode: 'readwrite' }));
  }

  function pickFolder(id) {
    return serverFolder().then(function (folder) { return folder || browserFolder(id); });
  }

  function onServer(folder, name) {
    return '/api/files/folder/' + encodeURIComponent(folder.server) + '/' + encodeURIComponent(name);
  }

  /* The save is over: the server's id for the folder writes nothing more. A folder of the
     browser has nothing to hand back, and a failure here costs nothing -- the server forgets
     an unused id by itself. */
  function releaseFolder(folder) {
    if (!folder || !folder.server) return Promise.resolve();
    var path = '/api/files/folder/' + encodeURIComponent(folder.server);
    return window.fetch(App.Api.base + path, { method: 'DELETE' })
      .then(function () {}, function () {});
  }

  function writeOnServer(folder, name, content) {
    return window.fetch(App.Api.base + onServer(folder, name), { method: 'PUT', body: content })
      .then(function (response) {
        if (response.ok) return null;
        return response.json().catch(function () { return {}; }).then(function (answer) {
          throw new Error(answer.detail || name + ' could not be written.');
        });
      });
  }

  function exists(folder, name) {
    if (folder.server) {
      return App.Api.get(onServer(folder, name)).then(function (answer) { return answer.exists; });
    }
    return folder.getFileHandle(name).then(function () { return true; }, function (error) {
      if (error && error.name === 'NotFoundError') return false;
      throw error;
    });
  }

  function writeInFolder(folder, name, content) {
    if (folder.server) return writeOnServer(folder, name, content);
    return folder.getFileHandle(name, { create: true }).then(function (handle) {
      return writeHandle(handle, content);
    });
  }

  function writeHandle(handle, text) {
    return handle.createWritable().then(function (stream) {
      return Promise.resolve(stream.write(text)).then(function () { return stream.close(); });
    });
  }

  /* Either destination: the file the user named, or — with no picker — the
     download bar. */
  function write(target, name, text, mime) {
    if (target && typeof target.createWritable === 'function') {
      return writeHandle(target, text);
    }
    // Through the module object, so a test can record what would be written.
    App.Download.anchor(name, text, mime);
    return Promise.resolve();
  }

  function anchor(name, text, mime) {
    var url = URL.createObjectURL(new Blob([text], { type: mime || 'text/plain' }));
    var link = document.createElement('a');
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    // Revoked a tick later: a browser still reading the blob when the URL goes
    // away saves an empty file.
    setTimeout(function () { URL.revokeObjectURL(url); }, 0);
  }

  return { CANCELLED: CANCELLED, pickFile: pickFile, pickFolder: pickFolder, exists: exists,
           writeInFolder: writeInFolder, releaseFolder: releaseFolder, write: write,
           anchor: anchor };
})();
