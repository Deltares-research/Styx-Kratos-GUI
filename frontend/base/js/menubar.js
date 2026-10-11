/* ══════════════════════════════════════════════════════════════════
   menubar.js — menu bar, drop-downs, flyouts and context menus.
   All three share one renderer.
   ══════════════════════════════════════════════════════════════════ */

App.Menu = (function () {
  var el = App.UI.el, icon = App.UI.icon;

  /**
   * Renders a list of item descriptors into a floating .menu element.
   * @param {!Array<(string|!Object)>} items Item descriptors; '-' is a separator
   *     and an object with `title` is a heading.
   * @param {?function(!Object)} onPick Called with the clicked item.
   * @return {!Element} The unattached menu element.
   */
  function build(items, onPick) {
    var menu = el('div.menu');

    items.forEach(function (it) {
      if (it === '-') { menu.appendChild(el('div.menu-sep')); return; }
      if (it.title) { menu.appendChild(el('div.menu-title', { text: it.title })); return; }

      var row = el('div.menu-item' + (it.disabled ? '.disabled' : ''));
      var ic = el('span.mi-icon');
      if (it.checked) ic.appendChild(el('span.mi-check', { text: '✓' }));
      else if (it.icon) ic.appendChild(icon(it.icon));
      row.appendChild(ic);
      row.appendChild(el('span', { text: it.label }));
      row.appendChild(el('span.mi-key', { text: it.key || '' }));
      row.appendChild(el('span.mi-sub', { text: it.sub ? '▶' : '' }));

      if (!it.disabled) {
        var depth = App.UI.popupDepth();
        if (it.sub) {
          row.addEventListener('mouseenter', function () {
            App.UI.closePopups(depth + 1);
            var r = row.getBoundingClientRect();
            // A real submenu when the caller supplied one (live/js/mesh-labels.js's
            // "Show labels" is the first); the mockup's placeholder otherwise.
            var sub = build(Array.isArray(it.sub) ? it.sub : demoSubmenu(it), onPick);
            App.UI.popup(sub, r.right - 2, r.top - 4, { flipX: r.left });
          });
        } else {
          row.addEventListener('mouseenter', function () { App.UI.closePopups(depth + 1); });
          row.addEventListener('click', function () {
            App.UI.closePopups(0);
            if (onPick) onPick(it);
          });
        }
      }
      menu.appendChild(row);
    });

    return menu;
  }

  /**
   * Returns placeholder content for the two menu entries that carry submenus.
   * @param {!Object} it The parent item; its label picks the placeholder.
   * @return {!Array<!Object>}
   */
  function demoSubmenu(it) {
    if (/Recent/.test(it.label)) return [
      { label: 'Deep excavation — Rotterdam Zuid.p3d' },
      { label: 'Quay wall — Vlissingen.p3d' },
      { label: 'Dike stability — Lek.p3d' },
      { label: 'Tunnel — Zuidasdok.p3d' }
    ];
    if (/load/i.test(it.label)) return [
      { label: 'Point load',   icon: 'load' },
      { label: 'Line load',    icon: 'line' },
      { label: 'Surface load', icon: 'surface' }
    ];
    return [
      { label: 'Point prescribed displacement',   icon: 'prescribed' },
      { label: 'Line prescribed displacement',    icon: 'prescribed' },
      { label: 'Surface prescribed displacement', icon: 'prescribed' }
    ];
  }

  /**
   * Opens a standalone menu (context menus, tool-rail flyouts), closing any other.
   * @param {!Array<(string|!Object)>} items Item descriptors, as for build().
   * @param {number} x Left edge in client pixels.
   * @param {number} y Top edge in client pixels.
   * @param {?function(!Object)=} onPick Defaults to App.runAction.
   */
  function openAt(items, x, y, onPick) {
    App.UI.closePopups(0);
    App.UI.popup(build(items, onPick || App.runAction), x, y);
  }

  /* ── The menu bar itself ───────────────────────────────────────── */
  /** Renders App.MENUS into #menubar and wires open, close and hover-switching. */
  function mountBar() {
    var bar = document.getElementById('menubar');
    App.UI.clear(bar);
    var openIdx = -1;

    App.MENUS.forEach(function (m, i) {
      var btn = el('button.mb-item', { text: m.label, type: 'button' });

      /** Opens this button's drop-down beneath it, closing any other. */
      function open() {
        App.UI.closePopups(0);
        var r = btn.getBoundingClientRect();
        btn.classList.add('open');
        openIdx = i;
        App.UI.whenClosed(function () {
          btn.classList.remove('open');
          openIdx = -1;
        });
        App.UI.popup(build(m.items, App.runAction), r.left, r.bottom);
      }

      btn.addEventListener('mousedown', function (e) {
        e.preventDefault();
        if (openIdx === i) App.UI.closePopups(0); else open();
      });
      // Once one menu is open, hovering the others switches to them.
      btn.addEventListener('mouseenter', function () {
        if (openIdx >= 0 && openIdx !== i) open();
      });

      bar.appendChild(btn);
    });
  }

  return { mountBar: mountBar, openAt: openAt, build: build };
})();
