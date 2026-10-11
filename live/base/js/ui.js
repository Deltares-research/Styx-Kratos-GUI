/* ══════════════════════════════════════════════════════════════════
   ui.js — small DOM helpers shared by every other module.
   ══════════════════════════════════════════════════════════════════ */

App.UI = (function () {

  /**
   * Creates an element: el('div.cls#id', {attrs}, [children|string]).
   * @param {string} spec Tag name followed by any .class and #id parts; tag defaults to div.
   * @param {?Object=} attrs Attributes. `text`, `html`, `data` and `on*` listeners are
   *     handled specially; null, undefined and false values are skipped.
   * @param {?(Node|string|!Array<?(Node|string)>)=} kids Children to append.
   * @return {!Element}
   */
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

  /**
   * Creates an inline SVG icon from App.ICONS, falling back to the info icon.
   * @param {string} name Key in App.ICONS.
   * @param {string=} cls Class attribute for the svg.
   * @return {!SVGElement}
   */
  function icon(name, cls) {
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    if (cls) svg.setAttribute('class', cls);
    svg.innerHTML = App.ICONS[name] || App.ICONS.info;
    return svg;
  }

  /**
   * Removes all children of a node.
   * @param {!Node} node
   * @return {!Node} The same node.
   */
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); return node; }

  /**
   * Returns the first element matching a selector.
   * @param {string} sel CSS selector.
   * @param {?ParentNode=} root Defaults to document.
   * @return {?Element}
   */
  function $(sel, root) { return (root || document).querySelector(sel); }

  /* ── Floating layer (menus, flyouts, context menus) ──────────── */
  var layer = null;
  /**
   * Returns the #menu-layer element, looked up once.
   * @return {!Element}
   */
  function menuLayer() { return layer || (layer = document.getElementById('menu-layer')); }

  var openStack = [];       // currently open floating elements
  var onCloseAll = [];      // callbacks fired when everything closes

  /**
   * Shows a floating element at a position, kept inside the window, and pushes it
   * on the open-popup stack.
   * @param {!Element} node
   * @param {number} x Left edge in client pixels.
   * @param {number} y Top edge in client pixels.
   * @param {?{flipX: (number|undefined)}=} opts `flipX` is the right edge to place
   *     against when the popup would overflow on the right (submenus).
   * @return {!Element} The same node.
   */
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

  /**
   * Closes popups above a stack depth; closing the last runs the whenClosed callbacks.
   * @param {number=} depth Number of popups to keep open; defaults to 0.
   */
  function closePopups(depth) {
    depth = depth || 0;
    while (openStack.length > depth) {
      var n = openStack.pop();
      if (n.parentNode) n.parentNode.removeChild(n);
    }
    if (openStack.length === 0) { onCloseAll.forEach(function (f) { f(); }); onCloseAll = []; }
  }

  /**
   * Registers a one-shot callback for when every popup has closed.
   * @param {function()} fn
   */
  function whenClosed(fn) { onCloseAll.push(fn); }
  /**
   * Returns the number of popups currently open.
   * @return {number}
   */
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
  /**
   * Shows a delayed tooltip below a node while it is hovered.
   * @param {!Element} node
   * @param {?string=} text Tooltip text; nothing is attached when empty.
   * @return {!Element} The same node.
   */
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
  /** Hides the current tooltip and cancels a pending one. */
  function hideTip() {
    clearTimeout(tipTimer);
    if (tipNode && tipNode.parentNode) tipNode.parentNode.removeChild(tipNode);
    tipNode = null;
  }

  /* ── Draggable splitters ─────────────────────────────────────── */
  /**
   * Makes a splitter drag-resize a size stored in a CSS custom property on :root.
   * @param {?Element} node The splitter; nothing happens when null.
   * @param {string} axis 'x' or 'y'.
   * @param {string} prop Custom property to write, e.g. '--dock-width'.
   * @param {number} min Smallest size in pixels.
   * @param {(number|function(): number)} max Largest size in pixels, or a function
   *     returning it, re-read on every move.
   * @param {boolean=} invert True when dragging towards -axis grows the size.
   * @param {function(number=)=} onMove Called with each new size, and with no
   *     argument when the drag ends.
   */
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

      /**
       * Applies the clamped size for the current pointer position.
       * @param {!MouseEvent} ev
       */
      function move(ev) {
        var now = axis === 'x' ? ev.clientX : ev.clientY;
        var d = (now - start) * (invert ? -1 : 1);
        var v = Math.max(min, Math.min(typeof max === 'function' ? max() : max, base + d));
        document.documentElement.style.setProperty(prop, v + 'px');
        if (onMove) onMove(v);
      }
      /** Ends the drag and removes the window listeners. */
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

  /**
   * Returns the dock panels that have a row in DOCK_ROWS.
   * @param {!Element} dock
   * @return {!Array<!Element>}
   */
  function dockSections(dock) {
    return Array.prototype.filter.call(dock.querySelectorAll('.dock-panel'),
                                       function (panel) { return DOCK_ROWS[panel.id]; });
  }

  /**
   * Recomputes the dock's row sizes, carets and splitter states from which panels
   * are collapsed or hidden.
   * @param {?Element} dock
   */
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

  /**
   * Makes each dock panel collapse to its header when the header is clicked.
   * @param {?Element} dock
   */
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

  /* ── Number formatting ─────────────────────────────────────────── */
  /**
   * Formats a value with a fixed number of decimals.
   * @param {*} v A number or numeric string; empty values give ''.
   * @param {number=} n Decimals; defaults to 3.
   * @return {string} The formatted number, or String(v) when it is not numeric.
   */
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
