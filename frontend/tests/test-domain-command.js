/* ══════════════════════════════════════════════════════════════════
   test-domain-command.js — `domain`: the size of the soil block, shown or set.

   The command box takes the words of `kratos-cli domain P --x --y --z`, and File >
   Project properties… writes the same line in the log for the same edit.
   `App.DomainCommand` decides what was asked and what to send -- the request itself,
   and redrawing what comes back, are patches.js's.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var D = App.DomainCommand;
  var SECTION = { dimension: 2, section_offset: 5,
                  domain: { x0: 0, x1: 20, y_bottom: -15, y_top: 0, z0: 0, z1: 10 } };
  var SOLID = { dimension: 3, section_offset: null,
                domain: { x0: 0, x1: 20, y_bottom: -15, y_top: 0.5, z0: -4, z1: 4 } };

  T.test('anything that is not `domain` is not this command', function () {
    T.eq(D.command('domains', SECTION), false);
    T.eq(D.command('mesh', SECTION), false);
    T.eq(D.command('', SECTION), false);
  });

  T.test('a bare `domain` says the extents as kratos-cli domain does, and sends nothing', function () {
    T.eq(D.command('domain', SECTION),
         { ok: true, body: null,
           message: 'domain x 0 .. 20, y -15 .. 0 (2D section at z = 5)' });
    T.eq(D.command('  DOMAIN ', SOLID).message, 'domain x 0 .. 20, y -15 .. 0.5, z -4 .. 4');
  });

  T.test('a 2D section with no offset yet is cut through the middle of z', function () {
    var project = { dimension: 2, section_offset: null, domain: SECTION.domain };
    T.eq(D.describe(project), 'domain x 0 .. 20, y -15 .. 0 (2D section at z = 5)');
  });

  T.test('the flags give the axes to send, in metres', function () {
    T.eq(D.command('domain --x 0 30 --y -20 0', SECTION),
         { ok: true, body: { x: [0, 30], y: [-20, 0] }, message: null });
    T.eq(D.command('domain --z -2.5 2.5', SOLID).body, { z: [-2.5, 2.5] });
    T.eq(D.command('domain --Y -20 1', SECTION).body, { y: [-20, 1] }, 'a flag in capitals');
  });

  T.test('a word that is not an axis is refused with the usage', function () {
    var answer = D.command('domain --w 0 1', SECTION);
    T.eq(answer.ok, false);
    T.eq(answer.body, null);
    T.ok(/"--w" is not an axis\. Use `domain --x FROM TO/.test(answer.message), answer.message);
    T.eq(D.command('domain 0 30', SECTION).ok, false);
  });

  T.test('an axis needs two numbers', function () {
    T.ok(/--x takes two numbers, in m\./.test(D.command('domain --x 0', SECTION).message));
    T.ok(/--y takes two numbers/.test(D.command('domain --y -20 top', SECTION).message));
  });

  T.test('a max that is not above its min is refused, as Project properties refuses it', function () {
    T.eq(D.command('domain --x 30 0', SECTION),
         { ok: false, body: null, message: 'x max must be above x min.' });
    T.eq(D.command('domain --y 0 0', SECTION).message, 'y max must be above y min.');
  });

  T.test('the line of an update is the command that makes it', function () {
    T.eq(D.line({ y: [-60, 0], x: [0, 80] }), 'domain --x 0 80 --y -60 0');
    T.eq(D.line({ z: [0, 20] }), 'domain --z 0 20');
    var update = { x: [0, 80.5], y: [-60, 0] };
    T.eq(D.command(D.line(update), SECTION).body, update, 'and the command reads it back');
  });

})();
