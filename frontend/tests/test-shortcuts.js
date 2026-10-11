/* ══════════════════════════════════════════════════════════════════
   test-shortcuts.js — the keyboard shortcuts FEATURES.md B1 lists.

   js/data.js prints Ctrl+Z / Y / S / O / N beside menu items it never wired up;
   patches.js binds them to the actions the menus run, and turns F9 into Generate mesh
   in Mesh mode. Each is pressed here as a user would, and the action it asks for is
   recorded instead of run.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  function press(target, init) {
    target.dispatchEvent(new KeyboardEvent('keydown', Object.assign(
      { bubbles: true, cancelable: true }, init)));
  }

  /* The actions one key press asked for. install() can run more than once on this page,
     so a key may reach several identical handlers: the set of actions is what counts. */
  function actionsFor(init, target, mode) {
    var saved = { runAction: App.runAction, mode: App.state && App.state.mode };
    var asked = [];
    App.runAction = function (spec) { asked.push(spec.action); };
    if (mode) App.state.mode = mode;
    try {
      press(target || document.body, init);
    } finally {
      App.runAction = saved.runAction;
      if (mode) App.state.mode = saved.mode;
    }
    return asked.filter(function (a, i) { return asked.indexOf(a) === i; });
  }

  T.test('Ctrl+Z undoes, Ctrl+Y and Ctrl+Shift+Z redo', function () {
    T.eq(actionsFor({ key: 'z', ctrlKey: true }), ['undo']);
    T.eq(actionsFor({ key: 'y', ctrlKey: true }), ['redo']);
    T.eq(actionsFor({ key: 'Z', ctrlKey: true, shiftKey: true }), ['redo']);
  });

  T.test('Ctrl+S saves, Ctrl+O opens and Ctrl+N starts a new project', function () {
    T.eq(actionsFor({ key: 's', ctrlKey: true }), ['saveProject']);
    T.eq(actionsFor({ key: 'o', ctrlKey: true }), ['openProject']);
    T.eq(actionsFor({ key: 'n', ctrlKey: true }), ['newProject']);
  });

  T.test('a shortcut typed into a field is the field’s, not the application’s', function () {
    var input = document.createElement('input');
    document.body.appendChild(input);
    try {
      T.eq(actionsFor({ key: 'z', ctrlKey: true }, input), []);
    } finally { input.remove(); }
  });

  T.test('Ctrl+Alt is left alone, and a plain letter does nothing', function () {
    T.eq(actionsFor({ key: 'z', ctrlKey: true, altKey: true }), []);
    T.eq(actionsFor({ key: 'z' }), []);
  });

  T.test('F9 in Mesh mode generates the mesh', function () {
    T.ok(actionsFor({ key: 'F9' }, document.body, 'mesh').indexOf('generateMesh') >= 0);
  });

})();
