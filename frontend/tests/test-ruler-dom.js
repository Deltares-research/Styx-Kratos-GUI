/* The rulers' browser half: the canvases they paint and the switch's wiring into
   the toolbar and View menu (patches.js). The arithmetic is test-ruler.js, which
   runs headless as well (frontend/tests/run_headless.py). */

(function () {

  var R = App.Ruler;

  /* ── The DOM it paints into ────────────────────────────────────── */

  test('install builds one canvas per edge and sync leaves them hidden in 3D', function () {
    var enabled = R.isEnabled();
    var host = document.createElement('div');
    host.style.cssText = 'position:absolute;left:-9999px;width:800px;height:400px';
    document.body.appendChild(host);
    try {
      R.install(host);
      var edges = host.querySelectorAll('canvas.vp-ruler');
      T.eq(edges.length, 4, 'top, bottom, left and right');
      T.eq(Array.prototype.map.call(edges, function (c) { return c.dataset.edge; }).sort(),
           ['bottom', 'left', 'right', 'top']);

      R.setEnabled(true);
      T.eq(R.isEnabled(), true);
      var drawn = R.sync({ active: true, center: [0, 0], halfW: 10, halfH: 5,
                           width: 800, height: 400 });
      T.eq(edges[0].hidden, false, 'a 2D section with the switch on shows them');
      T.eq(drawn.h.axis, 'x', 'sync reports the scale it painted');

      R.sync({ active: false });
      T.ok(Array.prototype.every.call(edges, function (c) { return c.hidden; }),
           '3D hides every edge');
      R.setEnabled(false);
      T.eq(R.isEnabled(), false);
      R.sync({ active: true, center: [0, 0], halfW: 10, halfH: 5, width: 800, height: 400 });
      T.ok(Array.prototype.every.call(edges, function (c) { return c.hidden; }),
           'the user switch also hides rulers in a 2D view');
    } finally {
      R.setEnabled(enabled);
      R.uninstall();
      host.remove();
    }
  });

  /* ── Wiring ────────────────────────────────────────────────────── */

  test('the toolbar and the View menu both carry the ruler switch', function () {
    var saved = { action: App.runAction, command: App.Command };
    App.runAction = function () {};
    App.Command = { note: function () {}, ok: function () {}, err: function () {},
                    write: function () {}, run: function () {} };
    try {
      App.LivePatches.install();
      T.ok(App.TOOLBAR.some(function (t) { return t && t.action === 'toggleRuler'; }),
           'no toolbar button for the rulers');
      var view = App.MENUS.filter(function (m) { return m.label === 'View'; })[0];
      T.ok(view.items.some(function (i) { return i && i.action === 'toggleRuler'; }),
           'no View menu item for the rulers');
    } finally {
      App.runAction = saved.action; App.Command = saved.command;
      App.LivePatches.resetForTests();
    }
  });

  test('the ruler switch is a 2D-only action', function () {
    T.eq(App.LivePatches.availableIn3D('toggleRuler'), false,
         'there is nothing to measure on a solid model');
    T.eq(App.LivePatches.availableIn2D('toggleRuler'), true);
  });

})();
