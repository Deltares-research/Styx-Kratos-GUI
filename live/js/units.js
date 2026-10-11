/* ══════════════════════════════════════════════════════════════════
   units.js — the project's unit system, in the browser.

   Kratos has no units. A project names one consistent set -- SI (N, m, kg, s) or
   kN (kN, m, t, s) -- and every value it holds is in it: what the editors show, what
   the deck carries, what the results come back in (server/app/units.py). So nothing
   here converts a value on its way to the server. It labels numbers for what they
   are, converts the library's presets into the project's system, and turns
   `units <system>` into the request that converts the whole project once.

   App.UNIT_TABLE (live/js/unit-table.js) is generated from the server's own table.
   No DOM: runs headless (live/tests/test-units.js).
   ══════════════════════════════════════════════════════════════════ */

App.Units = (function () {
  'use strict';

  function table() { return App.UNIT_TABLE; }

  function system(project) {
    var name = project && project.unit_system;
    return name && table().systems[name] ? name : table().default;
  }

  function current() { return system(App.PROJECT); }

  function systems() {
    return Object.keys(table().systems).map(function (name) {
      return { name: name, title: table().systems[name].title };
    });
  }

  function title(name) { return table().systems[name || current()].title; }

  function label(quantity, name) {
    var q = table().quantities[quantity];
    return q ? q.labels[name || current()] : '';
  }

  function quantityOf(variable) { return table().variables[variable] || null; }

  function variableLabel(variable, name) {
    var quantity = quantityOf(variable);
    return quantity ? label(quantity, name) : '';
  }

  function unit(quantity, name) {
    var s = table().systems[name];
    var d = table().quantities[quantity].dimension;
    return Math.pow(s.mass, d[0]) * Math.pow(s.length, d[1]) * Math.pow(s.time, d[2]);
  }

  /* `value`, a `quantity` in system `from`, in system `to`. */
  function convert(value, quantity, from, to) {
    if (from === to) return value;
    return value * unit(quantity, from) / unit(quantity, to);
  }

  function fromSI(value, quantity, name) { return convert(value, quantity, 'SI', name || current()); }

  /* A Kratos `Variables` block in system `to`. Strings, flags, lists and names the
     table does not know are kept as they are -- the server says which in its notes. */
  function convertVariables(variables, from, to) {
    var out = {};
    Object.keys(variables).forEach(function (name) {
      var value = variables[name];
      var quantity = quantityOf(name);
      out[name] = quantity && typeof value === 'number' ? convert(value, quantity, from, to)
                                                        : value;
    });
    return out;
  }

  function gravity(name) {
    var s = table().systems[name || current()];
    return table().gravity * s.time * s.time / s.length;
  }

  function statusText(project) { return 'Units: ' + title(system(project)); }

  /* `units` / `units <system>`: false when the text is not this command, otherwise
     { ok, body, message } -- `body` is what PATCH /api/project/units takes, or null
     when there is nothing to send. Sending it and redrawing are patches.js's. */
  function command(text, project) {
    var words = String(text || '').trim().split(/\s+/);
    if (words[0].toLowerCase() !== 'units') return false;
    var now = system(project);
    var names = Object.keys(table().systems);
    var others = names.filter(function (n) { return n !== now; });
    if (words.length === 1 || words[1] === '') {
      return { ok: true, body: null,
               message: 'The project is in ' + title(now) + '. `units '
                        + others.join('` or `units ') + '` converts every value to '
                        + others.map(title).join(' or ') + '.' };
    }
    var asked = names.filter(function (n) { return n.toLowerCase() === words[1].toLowerCase(); })[0];
    if (!asked) {
      return { ok: false, body: null,
               message: 'There is no unit system "' + words[1] + '". Choose one of: '
                        + names.join(', ') + '.' };
    }
    if (asked === now) {
      return { ok: true, body: null, message: 'The project is already in ' + title(now) + '.' };
    }
    return { ok: true, body: { unit_system: asked },
             message: 'Converting every value from ' + title(now) + ' to ' + title(asked) + '…' };
  }

  return { system: system, current: current, systems: systems, title: title, label: label,
           quantityOf: quantityOf, variableLabel: variableLabel, convert: convert,
           fromSI: fromSI, convertVariables: convertVariables, gravity: gravity,
           statusText: statusText, command: command };
})();
