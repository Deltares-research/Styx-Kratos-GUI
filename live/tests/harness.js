/* ══════════════════════════════════════════════════════════════════
   harness.js — a ~90 line test runner.

   There is no Node on this machine and no build step in this project, so the
   tests run where the code actually runs: in the browser, against the real
   three.js from vendor/. Open live/tests/ to see them; `window.__TEST_RESULTS__`
   holds the same outcome as data so a driver can assert on it without anyone
   having to look at a screen.
   ══════════════════════════════════════════════════════════════════ */

(function (global) {

  var cases = [];

  function fmt(v) {
    if (typeof v === 'string') return JSON.stringify(v);
    if (v && v.length !== undefined && typeof v !== 'function' && v.length > 8) {
      return '[' + Array.prototype.slice.call(v, 0, 8).join(', ') + ', …(' + v.length + ')]';
    }
    try { return JSON.stringify(v); } catch (e) { return String(v); }
  }

  /* Structural equality, deep enough for arrays and plain objects. */
  function same(a, b) {
    if (a === b) return true;
    if (typeof a !== typeof b || a === null || b === null) return false;
    if (typeof a !== 'object') return false;
    var ka = Object.keys(a), kb = Object.keys(b);
    if (ka.length !== kb.length) return false;
    return ka.every(function (k) { return same(a[k], b[k]); });
  }

  var T = {
    test: function (name, fn) { cases.push({ name: name, fn: fn }); },

    ok: function (v, msg) {
      if (!v) throw new Error(msg || 'expected truthy, got ' + fmt(v));
    },

    eq: function (a, b, msg) {
      if (!same(a, b)) throw new Error((msg ? msg + ': ' : '') + fmt(a) + ' !== ' + fmt(b));
    },

    near: function (a, b, tol, msg) {
      if (!(Math.abs(a - b) <= tol)) {
        throw new Error((msg ? msg + ': ' : '') + a + ' is not within ' + tol + ' of ' + b);
      }
    },

    /* Asserts fn rejects/throws, and returns the error for further checks. */
    rejects: function (fn, msg) {
      return Promise.resolve().then(fn).then(
        function () { throw new Error(msg || 'expected a rejection, got none'); },
        function (err) { return err; }
      );
    },

    run: function () {
      var results = { passed: 0, failed: 0, failures: [], names: [] };
      return cases.reduce(function (chain, c) {
        return chain.then(function () {
          return Promise.resolve().then(c.fn).then(function () {
            results.passed++;
            results.names.push('PASS ' + c.name);
          }, function (err) {
            results.failed++;
            results.names.push('FAIL ' + c.name);
            results.failures.push(c.name + '\n    ' + (err && err.message || err));
          });
        });
      }, Promise.resolve()).then(function () {
        results.total = cases.length;
        results.ok = results.failed === 0;
        return results;
      });
    }
  };

  global.T = T;
  global.test = T.test;
})(window);
