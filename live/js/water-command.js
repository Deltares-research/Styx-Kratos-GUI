/* ══════════════════════════════════════════════════════════════════
   water-command.js — `water`: set, show or remove the project's water level.

       water              the level, or that there is none
       water <level>      set it (metres, inside the model), e.g. `water -1.5`
       water off          remove it (also `none`, `remove`)

   A model is not born with a water level (server/app/seed.py `blank_project`): it has
   one when its author sets one, and this is where that is done. Once set, the level and
   its specific weight are also editable in the Selection explorer, as before.

   This module only decides what was asked and what to send to
   `PUT /api/project/water`. It has no DOM in it, so the headless runner executes it
   (live/tests/test-water-command.js). Sending, and redrawing what comes back, is
   patches.js's `runWaterCommand`.
   ══════════════════════════════════════════════════════════════════ */

(function (App) {
  'use strict';

  var USAGE = 'Use `water <level>` to set it, e.g. water -1.5, or `water off` to remove it.';
  var REMOVE = ['off', 'none', 'remove'];

  function fixed(value) { return Number(value).toFixed(2); }

  /* `ctx` is `{water, domain}`: the project's current level (or null) and its extents.
     Returns `false` for anything that is not this command; otherwise `{ok, message,
     body}`, where `body` is what to PUT, or null when there is nothing to send. */
  function command(text, ctx) {
    var words = String(text || '').trim().split(/\s+/);
    if ((words[0] || '').toLowerCase() !== 'water') return false;

    var water = ctx.water || null;
    var domain = ctx.domain || {};
    var arg = (words[1] || '').toLowerCase();

    if (!arg) {
      return { ok: true, body: null, message: water
        ? 'Water level: ' + fixed(water.y) + ' m (specific weight '
          + (water.specific_weight === null || water.specific_weight === undefined
             ? App.Units.fromSI(10000, 'specific weight') : water.specific_weight)
          + ' ' + App.Units.label('specific weight') + ').'
        : 'This model has no water level. ' + USAGE };
    }

    if (REMOVE.indexOf(arg) >= 0) {
      if (!water) return { ok: true, body: null, message: 'There is no water level to remove.' };
      return { ok: true, body: { water: null }, message: 'Water level removed.' };
    }

    var level = Number(words[1]);
    if (words.length > 2 || words[1] === '' || !isFinite(level)) {
      return { ok: false, body: null, message: '"' + words.slice(1).join(' ')
               + '" is not a water level. ' + USAGE };
    }
    // The property editor's own bounds (live/js/model.js `waterLevelEditor`): a level
    // outside the model describes nothing.
    if (typeof domain.y_bottom === 'number' && typeof domain.y_top === 'number'
        && (level <= domain.y_bottom || level >= domain.y_top)) {
      return { ok: false, body: null, message: 'The water level must lie between '
               + fixed(domain.y_bottom) + ' and ' + fixed(domain.y_top) + ' m.' };
    }
    // Everything else about an existing level -- its specific weight above all -- is
    // the user's and is kept. A new level takes the server's defaults.
    var next = water ? Object.assign({}, water, { y: level }) : { y: level };
    return { ok: true, body: { water: next },
             message: 'Water level set to ' + fixed(level) + ' m.' };
  }

  App.WaterCommand = { command: command };

})(window.App = window.App || {});
