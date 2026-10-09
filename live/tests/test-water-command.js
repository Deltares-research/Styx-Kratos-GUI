/* ══════════════════════════════════════════════════════════════════
   test-water-command.js — `water`: the project's water level, set or removed.

   A model is not born with a water level any more (server/tests/test_water_level.py);
   it gets one when its author types `water <level>`, and loses it with `water off`.
   `App.WaterCommand` decides what was asked and what to send -- the request itself,
   and redrawing what comes back, are patches.js's.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var W = App.WaterCommand;
  var DOMAIN = { y_top: 0, y_bottom: -20 };
  var WET = { y: -1.5, margin: 3, thickness: 0.06, specific_weight: 10 };

  function run(text, water) {
    return W.command(text, { water: water === undefined ? null : water, domain: DOMAIN });
  }

  T.test('anything that is not `water` is not this command', function () {
    T.eq(run('waterlevel -2'), false);
    T.eq(run('mesh'), false);
  });

  T.test('a bare `water` says the level, and sends nothing', function () {
    var answer = run('water', WET);
    T.ok(answer.ok);
    T.eq(answer.body, null);
    T.ok(/-1\.50 m/.test(answer.message), answer.message);
  });

  T.test('a bare `water` on a dry model says there is none and how to set one', function () {
    var answer = run('water');
    T.ok(answer.ok);
    T.eq(answer.body, null);
    T.ok(/no water level/i.test(answer.message) && /water <level>/.test(answer.message),
         answer.message);
  });

  T.test('a number sets the level', function () {
    var answer = run('water -2.5');
    T.ok(answer.ok, answer.message);
    T.eq(answer.body, { water: { y: -2.5 } });
  });

  T.test('a new level keeps the rest of the existing one', function () {
    /* The specific weight is the user's; changing the level must not reset it. */
    var answer = run('water -3', { y: -1.5, margin: 3, thickness: 0.06, specific_weight: 9.81 });
    T.eq(answer.body, { water: { y: -3, margin: 3, thickness: 0.06, specific_weight: 9.81 } });
  });

  T.test('a level outside the model is refused, as the property editor refuses it', function () {
    var above = run('water 1');
    var below = run('water -25');
    T.ok(!above.ok && !below.ok);
    T.eq(above.body, null);
    T.ok(/between -20\.00 and 0\.00/.test(above.message), above.message);
  });

  T.test('something that is not a level says how to use the command', function () {
    var answer = run('water deep');
    T.ok(!answer.ok);
    T.ok(/water <level>/.test(answer.message), answer.message);
  });

  T.test('`off`, `none` and `remove` take the level away', function () {
    ['off', 'none', 'remove'].forEach(function (word) {
      var answer = run('water ' + word, WET);
      T.ok(answer.ok, word);
      T.eq(answer.body, { water: null }, word);
    });
  });

  T.test('taking away a level that is not there sends nothing', function () {
    var answer = run('water off');
    T.ok(answer.ok);
    T.eq(answer.body, null);
  });

})();
