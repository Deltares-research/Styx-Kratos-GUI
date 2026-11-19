/* ══════════════════════════════════════════════════════════════════
   domain-command.js — `domain`: show or set the size of the soil block.

       domain                                  the extents, as `kratos-cli domain P`
       domain --x FROM TO --y BOTTOM TOP       set them; any of --x, --y and --z
       domain --z FROM TO                      out of plane

   The same edit as File > Project properties… and `kratos-cli domain P --x --y --z`
   (core/session.py `set_domain`): `--y` is the bottom and the ground level, and with
   layers it moves the top of the first layer and the bottom of the last with it.

   This module only decides what was asked and what to send to
   `PATCH /api/project/domain`, and spells the command line that Project properties
   writes in the log. It has no DOM in it, so the headless runner executes it
   (frontend/tests/test-domain-command.js). Sending, and redrawing what comes back, is
   patches.js's `setExtents`.
   ══════════════════════════════════════════════════════════════════ */

(function (App) {
  'use strict';

  var AXES = ['x', 'y', 'z'];
  var USAGE = 'Use `domain --x FROM TO --y BOTTOM TOP`, and `--z FROM TO` for the out of '
    + 'plane extent.';

  function plain(value) { return String(Number(value)); }

  /* The extents as `kratos-cli domain P` prints them (cli/commands/ground.py
     `_domain_line`). A 2D model is the section at one z. */
  function describe(project) {
    var d = (project && project.domain) || {};
    var extent = 'domain x ' + plain(d.x0) + ' .. ' + plain(d.x1) + ', y '
      + plain(d.y_bottom) + ' .. ' + plain(d.y_top);
    if (project && project.dimension === 2) {
      var z = typeof project.section_offset === 'number' ? project.section_offset
                                                         : (d.z0 + d.z1) / 2;
      return extent + ' (2D section at z = ' + plain(z) + ')';
    }
    return extent + ', z ' + plain(d.z0) + ' .. ' + plain(d.z1);
  }

  /* The command line of an update ({ x: [from, to], ... }), the axes in x, y, z order. */
  function line(update) {
    return ['domain'].concat(AXES.filter(function (axis) { return update[axis]; })
      .map(function (axis) {
        return '--' + axis + ' ' + plain(update[axis][0]) + ' ' + plain(update[axis][1]);
      })).join(' ');
  }

  /* Returns `false` for anything that is not this command; otherwise `{ok, message,
     body}`, where `body` is what PATCH /api/project/domain takes ({ x: [from, to],
     y: [bottom, top], z: [from, to] }), or null when there is nothing to send. */
  function command(text, project) {
    var words = String(text || '').trim().split(/\s+/);
    if ((words[0] || '').toLowerCase() !== 'domain') return false;
    if (words.length === 1) return { ok: true, body: null, message: describe(project) };

    var body = {};
    for (var i = 1; i < words.length; i += 3) {
      var axis = /^--([xyz])$/i.exec(words[i]);
      var pair = [Number(words[i + 1]), Number(words[i + 2])];
      if (!axis) {
        return { ok: false, body: null, message: '"' + words[i] + '" is not an axis. ' + USAGE };
      }
      var name = axis[1].toLowerCase();
      if (words[i + 1] === undefined || words[i + 2] === undefined
          || !isFinite(pair[0]) || !isFinite(pair[1])) {
        return { ok: false, body: null, message: '--' + name + ' takes two numbers, in m. '
                 + USAGE };
      }
      // The words of the Project properties window, which refuses the same.
      if (!(pair[1] > pair[0])) {
        return { ok: false, body: null, message: name + ' max must be above ' + name + ' min.' };
      }
      body[name] = pair;
    }
    return { ok: true, body: body, message: null };
  }

  App.DomainCommand = { command: command, describe: describe, line: line };

})(window.App = window.App || {});
