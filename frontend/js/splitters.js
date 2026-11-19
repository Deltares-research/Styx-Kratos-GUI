/* ══════════════════════════════════════════════════════════════════
   splitters.js — the bars that resize the panels follow the mouse smoothly.

   Replaces App.UI.splitter (base/js/ui.js) before js/app.js wires the bars on
   DOMContentLoaded, with the same arguments. The frozen one made a drag jump:

   - It started from the size in the CSS custom property on :root. Until a bar has
     been dragged once that property is not set (the stylesheet's fallback gives the
     size), so it started from 0 and the panel snapped to its smallest size on the
     first move. It also started from the wrong size whenever the grid showed the
     panel smaller than the property asked for. This one starts from the size the
     panel has on screen: the panel next to the bar, on the side it resizes.
   - In the right dock, a panel grows into the Selection explorer, the row that takes
     the slack, and the Stages explorer then into the Model explorer (css/live.css caps
     the Model explorer so the Stages explorer fits). The frozen limit let a drag go
     past the point where nothing was left to give, so the panel stopped growing, the
     Stages explorer was pushed out of the dock, and dragging back did nothing until
     the mouse came back to that point. Here a dock panel grows only as far as the
     panels around it can give.
   - It resized on every mouse event, and the right and left bars and the command bar
     resize the 3D view each time. Here the size is applied once per frame.
   - It listened to mouse events on the window. A pointer capture keeps the drag going
     over the 3D view and outside the browser window, and a lost capture ends it.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Splitters = (function () {
  'use strict';

  /* The smallest the Selection explorer becomes when a dock panel grows into it, as
     css/layout.css sizes its row: 70 px beside the Stages explorer, else its header. */
  var SELECTION_MIN_STAGED = 70;

  function frame(run) {
    if (typeof window.requestAnimationFrame === 'function') return window.requestAnimationFrame(run);
    run();
    return 0;
  }

  /* The panel the bar resizes: before it, or after it for a bar that grows the panel
     when dragged towards -axis. */
  function target(node, invert) {
    return invert ? node.nextElementSibling : node.previousElementSibling;
  }

  /* The size to start a drag from: the panel's on screen, else the custom property. */
  function startSize(node, axis, prop, invert) {
    var panel = target(node, invert);
    var shown = panel ? (axis === 'x' ? panel.offsetWidth : panel.offsetHeight) : 0;
    if (shown > 0) return shown;
    return parseFloat(getComputedStyle(document.documentElement).getPropertyValue(prop)) || 0;
  }

  function open(panel) {
    return !!panel && !panel.hidden && !panel.classList.contains('collapsed');
  }

  function headHeight(panel) {
    var head = panel.querySelector('.dock-head');
    return head ? head.offsetHeight : 0;
  }

  /* How far `panel`, in the right dock, may grow: what the Selection explorer can give,
     and for the Stages explorer also what the Model explorer can give down to its
     header. Infinity for a bar outside the dock, or when the Selection explorer is not
     the row that takes the slack. */
  function room(node, panel) {
    var dock = node.closest ? node.closest('#dock') : null;
    var selection = dock && dock.querySelector('#panel-selection');
    if (!open(selection)) return Infinity;
    var smallest = dock.classList.contains('has-phases') ? SELECTION_MIN_STAGED : headHeight(selection);
    var give = Math.max(0, selection.offsetHeight - smallest);
    var model = dock.querySelector('#panel-model');
    if (panel && panel.id === 'panel-phases' && open(model)) {
      give += Math.max(0, model.offsetHeight - headHeight(model));
    }
    return give;
  }

  /* Same arguments as App.UI.splitter: a size in the custom property `prop` on :root,
     between `min` and `max` (a number, or a function read on every move); `invert`
     for a bar that grows the size when dragged towards -axis; `onMove` called with
     each new size and with no argument when the drag ends. */
  function splitter(node, axis, prop, min, max, invert, onMove) {
    if (!node) return;
    node.addEventListener('pointerdown', function (e) {
      if (e.button !== 0) return;
      e.preventDefault();
      var start = axis === 'x' ? e.clientX : e.clientY;
      var base = startSize(node, axis, prop, invert);
      var limit = base + room(node, target(node, invert));
      var pointer = start, pending = false, dragging = true;
      if (node.setPointerCapture) {
        try { node.setPointerCapture(e.pointerId); } catch (err) { /* a synthetic event has no pointer */ }
      }
      node.classList.add('dragging');
      document.body.classList.add('resizing');
      document.body.style.cursor = axis === 'x' ? 'col-resize' : 'row-resize';

      function apply() {
        pending = false;
        var d = (pointer - start) * (invert ? -1 : 1);
        var most = Math.min(typeof max === 'function' ? max() : max, limit);
        var v = Math.round(Math.max(min, Math.min(most, base + d)));
        document.documentElement.style.setProperty(prop, v + 'px');
        if (onMove) onMove(v);
      }
      function move(ev) {
        if (!dragging) return;
        pointer = axis === 'x' ? ev.clientX : ev.clientY;
        if (!pending) { pending = true; frame(function () { if (dragging) apply(); }); }
      }
      function up() {
        if (!dragging) return;
        dragging = false;
        if (pending) apply();
        node.classList.remove('dragging');
        document.body.classList.remove('resizing');
        document.body.style.cursor = '';
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', up);
        window.removeEventListener('pointercancel', up);
        node.removeEventListener('lostpointercapture', up);
        if (onMove) onMove();
      }
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
      window.addEventListener('pointercancel', up);
      node.addEventListener('lostpointercapture', up);
    });
  }

  if (App.UI) App.UI.splitter = splitter;

  return { splitter: splitter, startSize: startSize, room: room };
})();
