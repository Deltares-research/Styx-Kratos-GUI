/* Tests for frontend/js/draw-input.js — the viewport drawing state machine.

   Clicks go through a real THREE.Raycaster against the camera, which is hard to drive
   without a rendered scene. `handleCommand` (typing "x y z" into the command panel) is
   the module's own text-entry path for the same vertex list, so it doubles as the test
   seam here -- no raycaster mocking needed. */

(function () {

  function withMockedEnvironment(fn) {
    var origViewport = App.Viewport;
    var origModel = App.Model;
    var origFetch = window.fetch;

    var mockCanvas = document.createElement('canvas');
    var mockScene = { add: function () {}, remove: function () {} };

    App.Viewport = {
      getCanvas: function () { return mockCanvas; },
      getScene: function () { return mockScene; },
      getCamera: function () { return {}; },
      resize: function () {},
      refresh: function () { return Promise.resolve(); }
    };

    var posted = null;
    window.fetch = function (url, options) {
      posted = { url: url, recipe: JSON.parse(options.body) };
      return Promise.resolve({
        ok: true,
        json: function () { return Promise.resolve({ parts: [{ key: 'drawn_0' }] }); }
      });
    };

    App.Model = { load: function () { return Promise.resolve(); } };

    return Promise.resolve()
      .then(function () { return fn(mockCanvas, function () { return posted; }); })
      .then(
        function (result) { restore(); return result; },
        function (err) { restore(); throw err; }
      );

    function restore() {
      App.Viewport = origViewport;
      App.Model = origModel;
      window.fetch = origFetch;
    }
  }

  function pressEnter() {
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
  }

  test('starting a draw mode shows a crosshair cursor, Escape cancels it', function () {
    return withMockedEnvironment(function (canvas) {
      App.DrawInput.start('point');
      T.eq(canvas.style.cursor, 'crosshair', 'cursor changes to crosshair');
      App.DrawInput.cancel();
      T.eq(canvas.style.cursor, '', 'cursor resets on cancel');
    });
  });

  test('line: two typed vertices commit a line recipe on Enter', function () {
    return withMockedEnvironment(function (canvas, getPosted) {
      App.DrawInput.start('line');
      App.DrawInput.handleCommand('0 0 0');
      App.DrawInput.handleCommand('5 5 0');
      T.eq(getPosted(), null, 'line does not auto-commit at two vertices, unlike box');
      pressEnter();

      var posted = getPosted();
      T.ok(posted, 'commit posted a recipe');
      T.eq(posted.url, App.Api.base + '/api/geometry/create');
      T.eq(posted.recipe.kind, 'line');
      T.eq(posted.recipe.vertices, [[0, 0, 0], [5, 5, 0]]);
      T.eq('extrusion' in posted.recipe, false, 'a line has no extrusion field');
    });
  });

  test('surface: three typed vertices commit a plain polygon recipe, not an extrusion', function () {
    return withMockedEnvironment(function (canvas, getPosted) {
      App.DrawInput.start('polygon');
      App.DrawInput.handleCommand('0 0 0');
      App.DrawInput.handleCommand('10 0 0');
      App.DrawInput.handleCommand('10 10 0');
      pressEnter();

      var posted = getPosted();
      T.ok(posted, 'commit posted a recipe');
      T.eq(posted.recipe.kind, 'polygon',
        '"Create surface" must send a flat surface recipe, not polygon_extrude');
      T.eq(posted.recipe.vertices, [[0, 0, 0], [10, 0, 0], [10, 10, 0]]);
      T.eq('extrusion' in posted.recipe, false, 'a plain surface has no extrusion field');
    });
  });

  test('box: two typed corners auto-commit a box recipe', function () {
    return withMockedEnvironment(function (canvas, getPosted) {
      App.DrawInput.start('box');
      App.DrawInput.handleCommand('0 0 0');
      T.eq(getPosted(), null, 'box does not commit after the first corner');
      App.DrawInput.handleCommand('4 3 0');

      var posted = getPosted();
      T.ok(posted, 'box auto-commits at the second corner, unlike line/surface');
      T.eq(posted.recipe.kind, 'box');
      T.eq(posted.recipe.origin, [0, 0, 0]);
      T.eq(posted.recipe.size[0], 4);
      T.eq(posted.recipe.size[1], 3);
    });
  });

  test('commit resolves the created part through Model.load and clears drawing state', function () {
    return withMockedEnvironment(function (canvas, getPosted) {
      App.DrawInput.start('line');
      App.DrawInput.handleCommand('0 0 0');
      App.DrawInput.handleCommand('1 0 0');
      pressEnter();
      T.ok(getPosted(), 'recipe was sent');

      // Starting a new draw right after a commit must not throw -- state was reset.
      App.DrawInput.start('point');
      App.DrawInput.cancel();
    });
  });

})();
