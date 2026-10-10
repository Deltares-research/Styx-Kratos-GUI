/* The 2D/3D switch and the undo history (live/js/patches.js setModelMode).

   The switch rewrites the project -- loads and walls change shape with the dimension --
   so it is an edit like any other and Undo has to take it back. It used to assign the
   server's answer to App.PROJECT directly, past App.Model.apply, which is the one funnel
   App.History records from; the refresh after it then fetched the same project back,
   and the switch left nothing to undo (found by the GUI end-to-end tier). */

(function () {

  var GLOBALS = ['Api', 'Command', 'Viewport', 'PROJECT', 'state', 'runAction',
                 'selectObject', 'setMode', 'LAYERS', 'MATERIALS', 'BOREHOLES', 'LOADS',
                 'BEAMS', 'BEAM_SECTIONS', 'PANEL_SECTIONS', 'ANCHORS', 'ANCHOR_SECTIONS',
                 'INTERFACES', 'INTERFACE_SECTIONS', 'NORMAL_LOADS'];

  function rig() {
    var saved = { props: App.OBJECT_PROPS, trees: {} };
    GLOBALS.forEach(function (k) { saved[k] = App[k]; });
    Object.keys(App.TREES || {}).forEach(function (m) { saved.trees[m] = App.TREES[m]; });
    var two = JSON.parse(JSON.stringify(window.VIEWPORT_PAYLOADS.project));
    var three = JSON.parse(JSON.stringify(window.VIEWPORT_PAYLOADS.project3d));
    var ctx = { puts: [], server: two };
    App.OBJECT_PROPS = Object.assign({}, App.OBJECT_PROPS);
    App.state = { mode: 'soil', modelMode: '2d' };
    App.Model.apply(JSON.parse(JSON.stringify(two)));
    App.Api = {
      patch: function (path) {
        ctx.server = three;
        return Promise.resolve({ project: JSON.parse(JSON.stringify(three)), notes: [] });
      },
      put: function (path, body) {
        ctx.puts.push(body);
        ctx.server = body;
        return Promise.resolve(JSON.parse(JSON.stringify(body)));
      },
      get: function () { return Promise.resolve(JSON.parse(JSON.stringify(ctx.server))); }
    };
    App.Command = { ok: function () {}, err: function () {}, note: function () {},
                    write: function () {}, run: function () {} };
    App.Viewport = Object.assign({}, App.Viewport, {
      refresh: function () { return App.Model.load(); },
      setViewMode: function () {}
    });
    App.runAction = function () {};
    App.selectObject = function () {};
    App.setMode = function (m) { App.state.mode = m; };
    App.LivePatches.resetForTests();
    App.LivePatches.install();
    App.History.reset();
    ctx.restore = function () {
      App.LivePatches.resetForTests();
      App.History.reset();
      GLOBALS.forEach(function (k) { App[k] = saved[k]; });
      App.OBJECT_PROPS = saved.props;
      Object.keys(saved.trees).forEach(function (m) { App.TREES[m] = saved.trees[m]; });
      App.Model.rebuildDerived();
    };
    return ctx;
  }

  test('switching to 3D can be undone, back to the 2D project as it was', function () {
    var ctx = rig();
    return App.LivePatches.setModelMode('3d').then(function () {
      T.eq(App.PROJECT.dimension, 3);
      T.ok(App.History.canUndo(), 'the switch is a step in the history');
      return App.History.undo();
    }).then(function () {
      T.eq(App.PROJECT.dimension, 2, 'undone');
      T.eq(ctx.puts[ctx.puts.length - 1].dimension, 2, 'and the server was told');
    }).then(function () { ctx.restore(); }, function (e) { ctx.restore(); throw e; });
  });

})();
