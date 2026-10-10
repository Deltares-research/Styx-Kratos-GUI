/* ══════════════════════════════════════════════════════════════════
   toolbars.js — main toolbar, mode tab strip and the left tool rail.
   ══════════════════════════════════════════════════════════════════ */

App.Toolbars = (function () {
  var el = App.UI.el, icon = App.UI.icon, tip = App.UI.attachTip;

  /* ── Main toolbar ────────────────────────────────────────────── */
  /** Renders App.TOOLBAR into #maintoolbar; '|' entries become separators. */
  function mountMain() {
    var bar = App.UI.clear(document.getElementById('maintoolbar'));

    App.TOOLBAR.forEach(function (t) {
      if (t === '|') { bar.appendChild(el('span.tbsep')); return; }

      var cls = '.tbtn' + (t.wide ? '.tbtn-wide' : '') + (t.cta ? '.tbtn-cta' : '') +
                (t.disabled ? '.disabled' : '') + (t.on ? '.active' : '');
      var btn = el('button' + cls, { type: 'button' });
      btn.appendChild(icon(t.icon));
      if (t.wide) btn.appendChild(el('span', { text: t.wide }));

      btn.addEventListener('click', function () {
        App.UI.hideTip();
        if (t.action) App.runAction(t);
        if (t.toggle) {
          bar.querySelectorAll('.tbtn').forEach(function (b) {
            if (b.dataset.toggle) b.classList.remove('active');
          });
          btn.classList.add('active');
        }
      });
      if (t.toggle) btn.dataset.toggle = t.toggle;
      if (t.action) btn.dataset.action = t.action;

      tip(btn, t.tip);
      bar.appendChild(btn);
    });
  }

  /**
   * Reflects a toggle state (grid, snapping, projection) in the toolbar.
   * @param {string} action The button's action name.
   * @param {boolean} on
   */
  function setToolbarState(action, on) {
    var b = document.querySelector('#maintoolbar .tbtn[data-action="' + action + '"]');
    if (b) b.classList.toggle('active', !!on);
  }

  /* ── Mode tabs ───────────────────────────────────────────────── */
  var MODE_GROUP_LABELS = { 1: 'Geometry', 2: 'Calculation' };

  /** Renders App.MODES into #modetabs, grouped under MODE_GROUP_LABELS. */
  function mountModes() {
    var bar = App.UI.clear(document.getElementById('modetabs'));

    // Cluster consecutive modes that share a group id, each under its own label.
    var groups = [];
    App.MODES.forEach(function (m) {
      var last = groups[groups.length - 1];
      if (!last || last.id !== m.group) {
        last = { id: m.group, label: MODE_GROUP_LABELS[m.group] || '', modes: [] };
        groups.push(last);
      }
      last.modes.push(m);
    });

    groups.forEach(function (g, i) {
      if (i > 0) bar.appendChild(el('span.mode-group-divider'));

      var group = el('div.mode-group');
      group.appendChild(el('span.mode-group-label', { text: g.label }));

      var tabs = el('div.mode-group-tabs');
      g.modes.forEach(function (m) {
        var tab = el('button.mode-tab', { text: m.label, type: 'button', data: { mode: m.id } });
        tab.addEventListener('click', function () { App.setMode(m.id); });
        tabs.appendChild(tab);
      });
      group.appendChild(tabs);
      bar.appendChild(group);
    });
  }

  /**
   * Marks the tab of the given mode as active.
   * @param {string} mode Mode id.
   */
  function highlightMode(mode) {
    document.querySelectorAll('.mode-tab').forEach(function (t) {
      t.classList.toggle('active', t.dataset.mode === mode);
    });
  }

  /* ── Left tool rail ──────────────────────────────────────────── */
  /**
   * Renders the tool rail for a mode from App.RAILS. Tools with a flyout open it
   * from the button's corner or on a long press.
   * @param {string} mode Mode id.
   */
  function mountRail(mode) {
    var rail = App.UI.clear(document.getElementById('toolrail'));
    var tools = App.RAILS[mode] || [];

    tools.forEach(function (t) {
      if (t === '-') { rail.appendChild(el('span.rail-sep')); return; }

      var btn = el('button.rail-btn' + (t.on ? '.active' : '') +
                   (t.flyout ? '.has-flyout' : ''), { type: 'button' });
      btn.appendChild(icon(t.icon));
      tip(btn, t.tip + (t.flyout ? '  (click the corner for more)' : ''));

      btn.addEventListener('click', function (e) {
        App.UI.hideTip();
        // Clicking the bottom-right corner opens the flyout instead.
        var r = btn.getBoundingClientRect();
        var corner = t.flyout && (e.clientX > r.right - 11) && (e.clientY > r.bottom - 11);
        if (corner) {
          App.Menu.openAt(t.flyout, r.right - 2, r.top + 4, function (item) {
            if (item.action) App.runAction(item);
            else App.Command.note('Tool selected: ' + item.label + ' (mockup — no drawing input).');
            setActive(btn);
          });
          return;
        }
        setActive(btn);
        if (t.action) App.runAction(t);
        else App.Command.note('Tool selected: ' + t.tip.replace(/…$/, '') +
                              ' — drawing input is not implemented in this mockup.');
      });

      // Long-press also opens the flyout, as in the reference UI.
      if (t.flyout) {
        var timer = null;
        btn.addEventListener('mousedown', function () {
          timer = setTimeout(function () {
            var r = btn.getBoundingClientRect();
            App.Menu.openAt(t.flyout, r.right - 2, r.top + 4, function (item) {
              if (item.action) App.runAction(item);
              else App.Command.note('Tool selected: ' + item.label + ' (mockup).');
            });
          }, 460);
        });
        ['mouseup', 'mouseleave'].forEach(function (ev) {
          btn.addEventListener(ev, function () { clearTimeout(timer); });
        });
      }

      rail.appendChild(btn);
    });

    /**
     * Marks one rail button as the active tool.
     * @param {!Element} btn
     */
    function setActive(btn) {
      rail.querySelectorAll('.rail-btn').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
    }
  }

  return {
    mountMain: mountMain, mountModes: mountModes, mountRail: mountRail,
    highlightMode: highlightMode, setToolbarState: setToolbarState
  };
})();
