/* ══════════════════════════════════════════════════════════════════
   test-documentation.js — Help > Documentation and Help > GUI tutorials: which
   page of the documentation site each opens, and what the log says. The Help
   menu rows and F1 are patches.js's.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var D = App.Documentation;

  /* Runs `body` with window.open and the log stood in; returns what each was given. */
  function withStandIns(body) {
    var savedOpen = window.open;
    var savedCommand = App.Command;
    var seen = { opened: [], notes: [] };
    window.open = function () { seen.opened.push(Array.prototype.slice.call(arguments)); };
    App.Command = { note: function (text) { seen.notes.push(text); } };
    try {
      seen.returned = body();
    } finally {
      window.open = savedOpen;
      App.Command = savedCommand;
    }
    return seen;
  }

  T.test('the home page and the GUI tutorials are pages of the published site', function () {
    T.eq(D.url('home'), 'https://deltares-research.github.io/Styx-Kratos-GUI/index.html');
    T.eq(D.url('tutorials'),
         'https://deltares-research.github.io/Styx-Kratos-GUI/docs/gui_tutorials/index.html');
  });

  T.test('a page it does not know opens the home page', function () {
    T.eq(D.url('nothing'), D.url('home'));
    T.eq(D.url(undefined), D.url('home'));
  });

  T.test('open opens a new tab, with no way back to Styx, and logs the address', function () {
    var seen = withStandIns(function () { return D.open('tutorials'); });
    T.eq(JSON.stringify(seen.opened),
         JSON.stringify([[D.url('tutorials'), '_blank', 'noopener']]));
    T.eq(JSON.stringify(seen.notes), JSON.stringify(['Documentation: ' + D.url('tutorials')]));
    T.eq(seen.returned, D.url('tutorials'));
  });

})();
