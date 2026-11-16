/* test-vocabulary.js — the frozen mockup's "phase" labels read "stage" once
   js/vocabulary.js has run over them (js/data.js itself is never edited). */

(function () {
  function labels(items) {
    return items.map(function (i) { return typeof i === 'string' ? i : (i.label || ''); });
  }

  test('the frozen menu reads Stages', function () {
    App.Vocabulary.relabel();
    var menu = App.MENUS.filter(function (m) { return m.label === 'Stages'; })[0];
    T.ok(menu, 'a Stages menu');
    T.eq(labels(menu.items)[0], 'Edit stages…');
  });

  test('no frozen label says phase', function () {
    App.Vocabulary.relabel();
    var text = JSON.stringify([App.MENUS, App.RAILS, App.MODES]);
    T.ok(!/phase/i.test(text.replace(/"icon":"phase"/g, '')), text);
  });

  test('relabel is idempotent', function () {
    App.Vocabulary.relabel();
    var once = JSON.stringify(App.MENUS);
    App.Vocabulary.relabel();
    T.eq(JSON.stringify(App.MENUS), once);
  });
})();
