/* picture-dialog.js — what the window asks, as the line it runs.

   The window writes a `picture save ...` line, so a choice in it means what the same words
   mean in the command box and in `kratos-cli picture`. */

(function () {
  var W = App.PictureDialog;
  var D = App.PictureDraw;

  function choice(extra) {
    return Object.assign({ formats: ['png'], width: D.DEFAULT_WIDTH_CM, scope: 'view', csv: false,
                           legend: true, rulers: true, axes: true, grid: false }, extra || {});
  }

  var SCREEN = { legend: true, rulers: true };

  test('the plain choice is the plain line', function () {
    T.eq(W.commandFor(choice(), SCREEN), 'picture save png');
  });

  test('the zoom of the screen is asked for in the words of the box', function () {
    T.eq(W.commandFor(choice({ screenZoom: true }), SCREEN), 'picture save png --screen-zoom');
  });

  test('every choice in the window is a word of the command', function () {
    var line = W.commandFor(choice({ formats: ['png', 'svg'], width: 12, scope: 'both', csv: true,
                                     legend: false, rulers: false, axes: false, grid: true }), SCREEN);
    T.eq(line, 'picture save png svg --width 12 --stage all --field all --no-legend --no-rulers '
               + '--no-axes --grid --csv');
  });

  test('the line the window writes is one the command reads', function () {
    var line = W.commandFor(choice({ formats: ['pdf'], width: 20, scope: 'fields', grid: true }), SCREEN);
    var asked = D.parseCommand(line);
    T.eq(asked.formats, ['pdf']);
    T.eq(asked.width, 20);
    T.eq(asked.field, 'all');
    T.eq(asked.stage, null);
    T.eq(asked.show.grid, true);
  });

  test('a thing the screen does not have is not left out in words', function () {
    var line = W.commandFor(choice({ legend: false, rulers: false }), { legend: false, rulers: false });
    T.eq(line, 'picture save png');
  });

  test('stages are offered in Staged construction, and fields in Results', function () {
    T.eq(W.scopesFor(false, false), ['view']);
    T.eq(W.scopesFor(false, true), ['view', 'stages']);
    T.eq(W.scopesFor(true, false), ['view', 'stages', 'fields', 'both']);
  });

  var COUNTS = { stages: 7, fields: 20 };

  test('one file in one format asks for a file', function () {
    T.ok(/^1 file\. You choose its name/.test(W.hint(choice(), COUNTS)));
  });

  test('more than one file asks for a folder, and says how many', function () {
    var hint = W.hint(choice({ formats: ['png', 'pdf'], scope: 'stages' }), COUNTS);
    T.ok(/^14 files\. You choose a folder/.test(hint), hint);
  });

  test('every stage and every field is an estimate, and the CSV counts', function () {
    var hint = W.hint(choice({ scope: 'both', csv: true }), COUNTS);
    T.ok(/^About 280 files/.test(hint), hint);
  });

  test('no format and no CSV asks for a format', function () {
    T.eq(W.hint(choice({ formats: [] }), COUNTS), 'Choose a format.');
  });
})();
