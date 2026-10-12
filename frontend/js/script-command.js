/* ══════════════════════════════════════════════════════════════════
   script-command.js — `script <file.py>`: the open model, written as a model script.

       script models/pit.py           write it; refused when the file is there
       script models/pit.py --force   replace the file that is there

   The file is the Python that builds the model again, every value typed out
   (core/model/script_writer.py): `run <file.py>` opens it, `kratos-cli` takes it,
   and `python <file.py> --out deck/` writes its Kratos deck. The same file
   `kratos-cli script` writes.

   This module only decides what was asked and what to send to
   `POST /api/project/script/save`. It has no DOM in it, so the headless runner
   executes it (frontend/tests/test-script-command.js). Sending it, and saying what
   came back, is patches.js's `runScriptCommand`.
   ══════════════════════════════════════════════════════════════════ */

(function (App) {
  'use strict';

  var USAGE = 'Use `script <file.py>` to write the model as a Python file that builds it '
            + 'again, e.g. script models/pit.py; add --force to replace a file that is there.';
  var FORCE = /(^|\s)--force(?=\s|$)/;

  /* Returns `false` for anything that is not this command; otherwise `{ok, message,
     body}`, where `body` is what to POST, or null when there is nothing to send. */
  function command(text) {
    var trimmed = String(text || '').trim();
    var words = trimmed.split(/\s+/);
    if ((words[0] || '').toLowerCase() !== 'script') return false;

    // The path is the rest of the line, as `run` takes it: a folder may have a space.
    var rest = trimmed.slice(words[0].length).trim();
    var force = FORCE.test(rest);
    var path = rest.replace(FORCE, ' ').trim();
    if (!path) return { ok: false, body: null, message: USAGE };
    if (!/\.py$/i.test(path)) {
      return { ok: false, body: null,
               message: 'A model script is a .py file, not ' + path + '. ' + USAGE };
    }
    return { ok: true, body: force ? { path: path, force: true } : { path: path },
             message: 'Writing the model to ' + path + '...' };
  }

  /* What to say once it is written: where, and the two ways back. */
  function written(path) {
    return 'Wrote ' + path + '. `run ' + path + '` opens it again; `python ' + path
         + ' --out deck/` writes its Kratos deck.';
  }

  App.ScriptCommand = { command: command, written: written };

})(window.App = window.App || {});
