/* ══════════════════════════════════════════════════════════════════
   ui.js — small DOM helpers shared by every other module.
   ══════════════════════════════════════════════════════════════════ */

App.UI = (function () {

  /* Create an element: el('div.cls#id', {attrs}, [children|string]) */
  function el(spec, attrs, kids) {
    var m = /^([a-zA-Z0-9]+)?((?:[.#][\w-]+)*)$/.exec(spec) || [];
    var node = document.createElement(m[1] || 'div');
    (m[2] || '').split(/(?=[.#])/).forEach(function (t) {
      if (!t) return;
      if (t[0] === '.') node.classList.add(t.slice(1));
      else node.id = t.slice(1);
    });
    if (attrs) Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v === null || v === undefined || v === false) return;
      if (k === 'html') node.innerHTML = v;
      else if (k === 'text') node.textContent = v;
      else if (k.slice(0, 2) === 'on') node.addEventListener(k.slice(2).toLowerCase(), v);
      else if (k === 'data') Object.keys(v).forEach(function (d) { node.dataset[d] = v[d]; });
      else node.setAttribute(k, v === true ? '' : v);
    });
    if (kids != null) (Array.isArray(kids) ? kids : [kids]).forEach(function (c) {
      if (c == null) return;
      node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return node;
  }

  /* Inline SVG icon from App.ICONS */
  function icon(name, cls) {
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    if (cls) svg.setAttribute('class', cls);
    svg.innerHTML = App.ICONS[name] || App.ICONS.info;
    return svg;
  }

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); return node; }

  function $(sel, root) { return (root || document).querySelector(sel); }

  /* ── Floating layer (menus, flyouts, context menus) ──────────── */
  var layer = null;
  function menuLayer() { return layer || (layer = document.getElementById('menu-layer')); }

  var openStack = [];       // currently open floating elements
  var onCloseAll = [];      // callbacks fired when everything closes

  function popup(node, x, y, opts) {
    opts = opts || {};
    menuLayer().appendChild(node);
    // Flip into view if it would overflow the window.
    var r = node.getBoundingClientRect();
    if (x + r.width > window.innerWidth - 4) x = Math.max(4, (opts.flipX || x) - r.width);
    if (y + r.height > window.innerHeight - 4) y = Math.max(4, window.innerHeight - r.height - 4);
    node.style.left = Math.round(x) + 'px';
    node.style.top = Math.round(y) + 'px';
    openStack.push(node);
    return node;
  }

  function closePopups(depth) {
    depth = depth || 0;
    while (openStack.length > depth) {
      var n = openStack.pop();
      if (n.parentNode) n.parentNode.removeChild(n);
    }
    if (openStack.length === 0) { onCloseAll.forEach(function (f) { f(); }); onCloseAll = []; }
  }

  function whenClosed(fn) { onCloseAll.push(fn); }
  function popupDepth() { return openStack.length; }

  document.addEventListener('mousedown', function (e) {
    if (openStack.length && !openStack.some(function (n) { return n.contains(e.target); })
        && !(e.target.closest && e.target.closest('.mb-item, .rail-btn'))) closePopups(0);
  }, true);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && openStack.length) { closePopups(0); e.stopPropagation(); }
  }, true);

  /* ── Tooltips ────────────────────────────────────────────────── */
  var tipNode = null, tipTimer = null;
  function attachTip(node, text) {
    if (!text) return node;
    node.addEventListener('mouseenter', function () {
      clearTimeout(tipTimer);
      tipTimer = setTimeout(function () {
        var r = node.getBoundingClientRect();
        tipNode = el('div.vp-tooltip', { text: text });
        tipNode.style.position = 'fixed';
        tipNode.style.zIndex = 900;
        document.body.appendChild(tipNode);
        var tr = tipNode.getBoundingClientRect();
        var x = Math.min(r.left, window.innerWidth - tr.width - 6);
        var y = r.bottom + 6;
        if (y + tr.height > window.innerHeight - 4) y = r.top - tr.height - 6;
        tipNode.style.left = Math.max(4, x) + 'px';
        tipNode.style.top = y + 'px';
      }, 520);
    });
    node.addEventListener('mouseleave', hideTip);
    node.addEventListener('mousedown', hideTip);
    return node;
  }
  function hideTip() {
    clearTimeout(tipTimer);
    if (tipNode && tipNode.parentNode) tipNode.parentNode.removeChild(tipNode);
    tipNode = null;
  }

  /* ── Draggable splitters ─────────────────────────────────────── */
  /* axis: 'x' | 'y'.  Writes `prop` (a CSS custom property on :root). */
  function splitter(node, axis, prop, min, max, invert, onMove) {
    if (!node) return;
    node.addEventListener('mousedown', function (e) {
      e.preventDefault();
      var start = axis === 'x' ? e.clientX : e.clientY;
      var css = getComputedStyle(document.documentElement).getPropertyValue(prop);
      var base = parseFloat(css) || 0;
      node.classList.add('dragging');
      document.body.classList.add('resizing');
      document.body.style.cursor = axis === 'x' ? 'col-resize' : 'row-resize';

      function move(ev) {
        var now = axis === 'x' ? ev.clientX : ev.clientY;
        var d = (now - start) * (invert ? -1 : 1);
        var v = Math.max(min, Math.min(typeof max === 'function' ? max() : max, base + d));
        document.documentElement.style.setProperty(prop, v + 'px');
        if (onMove) onMove(v);
      }
      function up() {
        node.classList.remove('dragging');
        document.body.classList.remove('resizing');
        document.body.style.cursor = '';
        window.removeEventListener('mousemove', move);
        window.removeEventListener('mouseup', up);
        if (onMove) onMove();
      }
      window.addEventListener('mousemove', move);
      window.addEventListener('mouseup', up);
    });
  }

  /* ── Collapsible dock panels ─────────────────────────────────── */
  /* Every section of the right dock collapses to its own header. #dock is a grid
     whose row sizes come from --r-model / --r-selection / --r-phases, so collapsing
     is one custom property set to `auto`: the row then shrinks to the header it
     holds. Clearing the property hands the row back to the stylesheet, including
     whatever height its splitter was dragged to -- reopening a panel restores the
     size it had rather than a default. */
  var DOCK_ROWS = {
    'panel-model':     { row: '--r-model',     splitter: 'split-dock1' },
    'panel-selection': { row: '--r-selection', splitter: null },
    'panel-phases':    { row: '--r-phases',    splitter: 'split-dock2' }
  };

  function dockSections(dock) {
    return Array.prototype.filter.call(dock.querySelectorAll('.dock-panel'),
                                       function (panel) { return DOCK_ROWS[panel.id]; });
  }

  function syncDock(dock) {
    if (!dock) return;
    var open = [];
    dockSections(dock).forEach(function (panel) {
      var spec = DOCK_ROWS[panel.id];
      var collapsed = panel.classList.contains('collapsed');

      var caret = panel.querySelector('.dock-caret');
      if (caret) caret.textContent = collapsed ? '▸' : '▾';

      // Dragging a splitter that resizes a collapsed panel would move a row that
      // cannot move, so it stops responding until the panel is open again.
      var bar = spec.splitter && dock.querySelector('#' + spec.splitter);
      if (bar) bar.classList.toggle('disabled', collapsed);

      if (panel.hidden) return;
      if (collapsed) dock.style.setProperty(spec.row, 'auto');
      else { dock.style.removeProperty(spec.row); open.push(spec); }
    });

    // The Selection explorer normally absorbs the dock's slack. Collapsed, it hands
    // that job to the last panel still open, so the dock never ends in dead space.
    var selection = dock.querySelector('#panel-selection');
    if (open.length && selection && selection.classList.contains('collapsed')) {
      dock.style.setProperty(open[open.length - 1].row, '1fr');
    }
  }

  function collapsibleDock(dock) {
    if (!dock) return;
    dockSections(dock).forEach(function (panel) {
      var head = panel.querySelector('.dock-head');
      if (!head) return;
      head.addEventListener('click', function (e) {
        // The Model explorer's expand-all / collapse-all buttons sit in this same
        // header and mean something else entirely.
        if (e.target.closest && e.target.closest('.dock-head-tools')) return;
        panel.classList.toggle('collapsed');
        syncDock(dock);
      });
    });
    syncDock(dock);
  }

  /* ── Number formatting ───────────────────────────────────────── */
  function fixed(v, n) {
    if (v === null || v === undefined || v === '') return '';
    var x = typeof v === 'number' ? v : parseFloat(v);
    return isNaN(x) ? String(v) : x.toFixed(n === undefined ? 3 : n);
  }

  return {
    el: el, icon: icon, clear: clear, $: $,
    popup: popup, closePopups: closePopups, popupDepth: popupDepth,
    whenClosed: whenClosed, menuLayer: menuLayer,
    attachTip: attachTip, hideTip: hideTip,
    splitter: splitter, collapsibleDock: collapsibleDock, syncDock: syncDock,
    fixed: fixed
  };
})();
