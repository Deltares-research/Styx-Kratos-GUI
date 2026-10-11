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

  function pickFile(suggestedName, mime) {
    if (typeof window.showSaveFilePicker !== 'function') return Promise.resolve(null);
    var accept = {};
    accept[mime || 'text/plain'] = [extensionOf(suggestedName) || '.txt'];
    return settle(window.showSaveFilePicker({
      suggestedName: suggestedName,
      types: [{ description: suggestedName, accept: accept }]
    }));
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

  return { CANCELLED: CANCELLED, pickFile: pickFile, write: write, anchor: anchor };
})();
