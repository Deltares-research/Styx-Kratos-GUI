/* ══════════════════════════════════════════════════════════════════
   dialog-fit.js — windows with help text open wide enough to read it.

   A settings window lays out its rows in three columns (`.mesh-settings-form`,
   css/live.css): the label, the field, and a line of help. The window's own width
   comes from its caller, and most asked for 520 to 600 px. The label and the field
   take about 480 px of that, so the help was squeezed into a column a few words wide
   and ran down the window in a long thin strip, and the window had to scroll.

   `fit` widens such a window to WIDTH (no wider than the browser window allows),
   keeps it centred, and makes it taller when its rows still do not fit, up to the
   browser window's height. It only grows a window, and leaves one without help text
   alone. Every window App.Dialogs.open makes is fitted; a window that builds its own
   shell (Create soil volume) calls `fit` itself.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.DialogFit = (function () {
  'use strict';

  /* Room for a 165 px label, a 300 px field and about 235 px of help, plus the
     window's padding and the gaps between the columns. */
  var WIDTH = 760;
  var MARGIN_X = 40;  // as App.Dialogs.open keeps a window inside the browser window
  var MARGIN_Y = 60;

  function hasHelp(dialog) {
    var helps = dialog.querySelectorAll('.mesh-settings-form .mesh-setting-help');
    return Array.prototype.some.call(helps, function (h) { return h.textContent.trim() !== ''; });
  }

  function fit(dialog) {
    if (!dialog || !dialog.querySelector || !hasHelp(dialog)) return false;
    var width = Math.min(WIDTH, window.innerWidth - MARGIN_X);
    if ((parseFloat(dialog.style.width) || 0) < width) {
      dialog.style.width = width + 'px';
      dialog.style.left = Math.max(0, Math.round((window.innerWidth - width) / 2)) + 'px';
    }
    var body = dialog.querySelector('.dlg-body');
    var short = body ? body.scrollHeight - body.clientHeight : 0;
    if (short > 0) {
      var height = Math.min((parseFloat(dialog.style.height) || dialog.offsetHeight) + short,
                            window.innerHeight - MARGIN_Y);
      dialog.style.height = height + 'px';
      dialog.style.top = Math.max(0, Math.round((window.innerHeight - height) / 2 - 12)) + 'px';
    }
    return true;
  }

  /* Wraps App.Dialogs.open once: the window is built inside `open`, so its rows are
     there to look at when it returns. */
  function install() {
    if (!App.Dialogs || !App.Dialogs.open || App.Dialogs.open.fitted) return;
    var frozen = App.Dialogs.open;
    App.Dialogs.open = function () {
      var handle = frozen.apply(this, arguments);
      if (handle) fit(handle.dialog);
      return handle;
    };
    App.Dialogs.open.fitted = true;
  }

  install();

  return { WIDTH: WIDTH, fit: fit, install: install };
})();
