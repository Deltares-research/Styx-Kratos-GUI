/* ══════════════════════════════════════════════════════════════════
   history.js — undo / redo, in whole-project snapshots.

   The frozen toolbar has had Undo and Redo since the mockup was drawn
   (js/data.js:202-203) and neither has ever done anything: the mockup had no
   model to step backwards through. The live build does, and it lives on the
   server, so "the state of the document" is exactly one thing -- the Project
   JSON -- and a step backwards is a PUT of an older copy.

   Snapshots rather than inverse operations, because every edit already goes
   through App.Model.apply(): one funnel to hook, no per-command undo to write
   and forget for the next feature. A project is a few kilobytes of JSON, so a
   stack of them costs nothing worth optimising.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.History = (function () {

  var LIMIT = 40;                 // deep enough for a session, bounded for memory
  var undoStack = [], redoStack = [];
  var applying = false;           // set while *we* are the ones changing the project
  var installed = false;
  var env = null;                 // overridden by withEnv() in the tests

  function clone(project) { return JSON.parse(JSON.stringify(project)); }
  function same(a, b) { return JSON.stringify(a) === JSON.stringify(b); }

  /* The real world: write the project back, then rebuild everything from it.
     Resolved late so a test that swaps App.Api or App.Model is not fighting a
     reference captured at load time. */
  function defaultEnv() {
    return {
      put: function (path, body) { return App.Api.put(path, body); },
      apply: function (project) {
        App.Model.apply(project);
        return App.Viewport.refresh();
      }
    };
  }

  function current() { return env || defaultEnv(); }

  function changed() { if (App.History.onChange) App.History.onChange(); }

  /* ── Recording ───────────────────────────────────────────────── */

  /* Called for every project the app applies. `previous` is what was on screen
     before it. Returns whether this counted as a step -- a refresh that fetches
     the same project back is not one, and neither is our own undo. */
  function record(previous, next) {
    if (applying || !previous || same(previous, next)) return false;
    undoStack.push(clone(previous));
    if (undoStack.length > LIMIT) undoStack.shift();
    // Redoing after a fresh edit would replay a branch the model has left.
    redoStack.length = 0;
    changed();
    return true;
  }

  function reset() {
    undoStack.length = 0;
    redoStack.length = 0;
    changed();
  }

  function canUndo() { return undoStack.length > 0; }
  function canRedo() { return redoStack.length > 0; }
  function depth() { return { undo: undoStack.length, redo: redoStack.length }; }
  function peekUndo() { return undoStack[undoStack.length - 1]; }

  /* ── Stepping ────────────────────────────────────────────────── */

  function step(from, to, label) {
    if (!from.length) {
      if (App.Command) App.Command.note('Nothing to ' + label + '.');
      return Promise.resolve(false);
    }
    var target = from.pop();
    var here = App.PROJECT ? clone(App.PROJECT) : null;
    var api = current();

    applying = true;
    return Promise.resolve(api.put('/api/project', target))
      .then(function (saved) {
        if (here) to.push(here);
        return api.apply(saved || target);
      })
      .then(function () {
        if (App.Command) App.Command.ok(label === 'undo' ? 'Undone.' : 'Redone.');
        return true;
      })
      .catch(function (error) {
        // The step never happened, so put it back where it came from rather than
        // leaving the stacks describing a model the server does not have.
        from.push(target);
        if (App.Command) App.Command.err('Could not ' + label + ': ' + error.message);
        return false;
      })
      .then(function (ok) {
        applying = false;
        changed();
        return ok;
      });
  }

  function undo() { return step(undoStack, redoStack, 'undo'); }
  function redo() { return step(redoStack, undoStack, 'redo'); }

  /* ── Hooking the one funnel every project change goes through ── */

  function install() {
    if (installed || !App.Model || typeof App.Model.apply !== 'function') return;
    installed = true;
    var frozenApply = App.Model.apply;
    App.Model.apply = function (project) {
      var previous = App.PROJECT;
      var result = frozenApply(project);
      record(previous, project);
      return result;
    };
  }

  /* Tests drive the stacks without a server or a scene behind them. */
  function withEnv(stub, body) {
    var saved = env;
    env = { put: stub.put || defaultEnv().put, apply: stub.apply || function () {} };
    function restore() { env = saved; }
    var out;
    try { out = body(); } catch (err) { restore(); throw err; }
    return Promise.resolve(out).then(
      function (v) { restore(); return v; },
      function (e) { restore(); throw e; });
  }

  return {
    install: install, record: record, reset: reset,
    canUndo: canUndo, canRedo: canRedo, depth: depth, peekUndo: peekUndo,
    undo: undo, redo: redo, withEnv: withEnv,
    onChange: null
  };
})();
