/* ══════════════════════════════════════════════════════════════════
   version.js — which version of Styx the page is.

   The frozen js/data.js names a version of its own ('Prototype V1.0'), and
   the title bar, the command box's welcome and the About box all read it.
   The server writes the real one into the page (the `styx-version` meta tag,
   backend/main.py), from core/version.py: the same text `kratos-cli
   --version` prints. This runs before js/app.js boots, so the title bar is
   right the first time it is drawn.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Version = (function () {

  var UNKNOWN = 'version unknown';

  /* The version the server wrote into `doc`, or UNKNOWN on a page it did not
     serve (the test page, a file opened from disk). */
  function fromPage(doc) {
    var meta = doc && doc.querySelector('meta[name="styx-version"]');
    var said = meta ? String(meta.getAttribute('content') || '').trim() : '';
    return said || UNKNOWN;
  }

  if (typeof document !== 'undefined') App.PRODUCT.version = fromPage(document);

  return { fromPage: fromPage, UNKNOWN: UNKNOWN };
})();
