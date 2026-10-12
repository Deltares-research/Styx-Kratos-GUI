/* ══════════════════════════════════════════════════════════════════
   part-colors.js — a part of the mesh, drawn in a colour of its own.

   The mesh is normally one grey sheet, which says nothing about which elements are
   the sheet pile's and which are the soil's. The Model explorer's colour toggle (the
   small square beside each row's eye, in Mesh mode) and the `colour` command switch a
   part's own colour on over it, so a user can inspect, part by part, what each of
   them is made of.

   The eye keeps its meaning -- shown or hidden -- and is not touched by this: a part is
   drawn coloured only while it is both coloured *and* shown.

   This module is the bookkeeping only: which colour belongs to which part, which parts
   are switched on, what a group row stands for, and what a typed name means. It has no
   DOM and no three.js in it, so it is the half the headless runner can execute
   (frontend/tests/test-part-colors.js). The drawing is in viewport.js and the toggles are
   in patches.js, and both act through what is here.
   ══════════════════════════════════════════════════════════════════ */

(function (App) {
  'use strict';

  /* Twelve colours that stay distinguishable from each other and from the grey mesh
     (#d9dee6) and its dark wireframe. Beyond twelve parts they repeat; by then a user
     inspects a few at a time anyway. */
  var PALETTE = [
    '#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4', '#42d4f4',
    '#f032e6', '#bfef45', '#469990', '#9a6324', '#800000', '#000075'
  ];

  /* `keys` in the project's own part order. A part's colour is its place in that
     order, so it survives a re-mesh: parts are added after the ones already there. */
  function colors(keys) {
    var out = {};
    (keys || []).forEach(function (key, i) { out[key] = PALETTE[i % PALETTE.length]; });
    return out;
  }

  /* An interface reaches the mesh as one key per face it unglues -- `wall_contact:L`
     and `wall_contact:R` (core/geometry/meshing.py `_interface_sections`) -- because the
     two faces are what a user has to tell apart. Left is a +90 degree turn from walking
     the line in its stored order, the project's own convention. */
  var SIDE = /:(L|R)$/;

  function sideOf(key) {
    var match = SIDE.exec(key || '');
    return match ? match[1] : null;
  }

  /* The part a key belongs to: the interface for a face, the key itself otherwise. */
  function baseOf(key) {
    return String(key || '').replace(SIDE, '');
  }

  /* The meshed parts a tree row stands for: its own key (or its faces) if meshed,
     otherwise every meshed key under it -- which is what makes a group row (Sheet
     piles, Soil) colour its members. */
  function keysUnder(node, meshed) {
    var out = [];
    (function walk(n) {
      if (!n) return;
      var own = n.obj ? meshed.filter(function (key) { return baseOf(key) === n.obj; }) : [];
      if (own.length) {
        own.forEach(function (key) { if (out.indexOf(key) < 0) out.push(key); });
        return;
      }
      (n.children || []).forEach(walk);
    })(node);
    return out;
  }

  /* Which parts are switched on. One per page in use (`App.PartColors.on`); `create`
     is there so a test can start from nothing. */
  function create() {
    var on = [];
    function isOn(key) { return on.indexOf(key) >= 0; }
    function set(keys, wanted) {
      keys.forEach(function (key) {
        var i = on.indexOf(key);
        if (wanted && i < 0) on.push(key);
        if (!wanted && i >= 0) on.splice(i, 1);
      });
    }
    function stateOf(keys) {
      var count = keys.filter(isOn).length;
      return !count ? 'off' : count === keys.length ? 'on' : 'mixed';
    }
    return {
      isOn: isOn,
      set: set,
      stateOf: stateOf,
      /* All on goes off; anything less goes all on. A mixed group goes on, which is
         what a click on a half-filled box is asking for. */
      toggle: function (keys) {
        var wanted = stateOf(keys) !== 'on';
        set(keys, wanted);
        return wanted;
      },
      keys: function () { return on.slice(); },
      clear: function () { on.length = 0; },
      /* Forget what the current mesh no longer has. */
      keep: function (meshed) {
        on = on.filter(function (key) { return meshed.indexOf(key) >= 0; });
      }
    };
  }

  /* What the viewport draws: on, meshed and shown, in mesh order. A face is shown by
     its interface's eye -- there is no eye per face. */
  function drawn(meshed, on, isVisible) {
    return meshed.filter(function (key) { return on.isOn(key) && isVisible(baseOf(key)); });
  }

  /* ── Names ─────────────────────────────────────────────────────────────
     A row's label is what the user sees and so what they type. Only the part before
     the "  ·  " counts -- "Top  ·  Sand" is the body called Top, made of Sand. */

  function shortLabel(label) {
    return String(label || '').split('  ·  ')[0].trim();
  }

  function walkTree(tree, visit) {
    (function walk(nodes) {
      (nodes || []).forEach(function (n) { visit(n); walk(n.children); });
    })(tree);
  }

  /* Everything a name can mean: each row with something meshed under it, by its
     label, and each meshed part by its key. */
  function candidates(tree, meshed) {
    var out = [];
    walkTree(tree, function (n) {
      var keys = keysUnder(n, meshed);
      if (keys.length && shortLabel(n.label)) out.push({ name: shortLabel(n.label), keys: keys });
    });
    var names = partNames(tree, meshed);
    meshed.forEach(function (key, i) {
      out.push({ name: key, keys: [key] });
      // A face has no row of its own, so "Wall contact R" is its only name.
      if (sideOf(key)) out.push({ name: names[i], keys: [key] });
    });
    return out;
  }

  /* The name of each meshed part, as its row says it; a face is its interface's name
     and its letter, "Wall contact L". */
  function partNames(tree, meshed) {
    var names = {};
    walkTree(tree, function (n) {
      if (n.obj && !names[n.obj]) names[n.obj] = shortLabel(n.label) || n.obj;
    });
    return meshed.map(function (key) {
      var base = names[baseOf(key)];
      if (!base) return key;
      return sideOf(key) ? base + ' ' + sideOf(key) : base;
    });
  }

  function nameOf(key, tree, meshed) {
    var i = meshed.indexOf(key);
    return i >= 0 ? partNames(tree, meshed)[i] : key;
  }

  function sameKeys(a, b) { return a.join('\n') === b.join('\n'); }

  /* `{keys}` for a name the user typed, or `{error}` saying why there are none. An
     exact name wins; failing that, a beginning that only one thing has. */
  function resolve(name, tree, meshed) {
    var wanted = name.toLowerCase();
    var all = candidates(tree, meshed);
    var exact = all.filter(function (c) { return c.name.toLowerCase() === wanted; });
    if (exact.length) return { keys: exact[0].keys };

    var begins = [];
    all.forEach(function (c) {
      if (c.name.toLowerCase().indexOf(wanted) !== 0) return;
      if (!begins.some(function (b) { return sameKeys(b.keys, c.keys); })) begins.push(c);
    });
    if (begins.length === 1) return { keys: begins[0].keys };
    if (begins.length > 1) {
      return { error: '"' + name + '" could be ' + begins.map(function (c) {
        return c.name;
      }).join(', ') + '. Type more of the name.' };
    }

    var unmeshed = false;
    walkTree(tree, function (n) {
      var label = shortLabel(n.label).toLowerCase();
      if ((n.obj || '').toLowerCase() === wanted || label === wanted
          || (label && label.indexOf(wanted) === 0)) {
        unmeshed = true;
      }
    });
    var choices = ' Parts with mesh elements: ' + partNames(tree, meshed).join(', ') + '.';
    if (unmeshed) {
      return { error: '"' + name + '" has no mesh elements, so there is nothing to '
                      + 'colour.' + choices };
    }
    return { error: 'No part called "' + name + '".' + choices };
  }

  /* ── The command ───────────────────────────────────────────────────────

       colour                 what is coloured, and what could be
       colour <part> [off]    colour one part (a row label, or a key), or stop
       colour all | off       every meshed part, or none

     `ctx` is `{tree, meshed, on}`: the Model explorer's nodes, the meshed part keys in
     project order, and the tracker. Returns `false` for anything that is not this
     command, before anything else happens; otherwise `{ok, message, changed}`, which
     the caller prints and, if `changed`, redraws from. */
  function command(text, ctx) {
    var words = String(text || '').trim().split(/\s+/);
    var verb = (words[0] || '').toLowerCase();
    if (verb !== 'colour' && verb !== 'color') return false;

    var tree = ctx.tree || [], meshed = ctx.meshed || [], on = ctx.on;
    if (!meshed.length) {
      return { ok: false, changed: false,
               message: 'There is no mesh to colour yet. Mesh the model first.' };
    }

    var rest = words.slice(1);
    var choices = 'Parts with mesh elements: ' + partNames(tree, meshed).join(', ') + '.';
    if (!rest.length) {
      var coloured = on.keys().filter(function (key) { return meshed.indexOf(key) >= 0; });
      return { ok: true, changed: false, message: (coloured.length
        ? 'Coloured: ' + coloured.map(function (key) {
            return nameOf(key, tree, meshed);
          }).join(', ') + '. '
        : 'Nothing is coloured. ') + choices };
    }

    var single = rest.length === 1 ? rest[0].toLowerCase() : null;
    if (single === 'all') {
      on.set(meshed, true);
      return { ok: true, changed: true, message: 'Every meshed part is coloured.' };
    }
    if (single === 'off' || single === 'none') {
      on.clear();
      return { ok: true, changed: true, message: 'No part is coloured.' };
    }

    var last = rest[rest.length - 1].toLowerCase();
    var wanted = true;
    if (rest.length > 1 && (last === 'off' || last === 'on')) {
      wanted = last === 'on';
      rest = rest.slice(0, -1);
    }
    var found = resolve(rest.join(' '), tree, meshed);
    if (found.error) return { ok: false, changed: false, message: found.error };

    on.set(found.keys, wanted);
    var names = found.keys.map(function (key) { return nameOf(key, tree, meshed); });
    return { ok: true, changed: true,
             message: (wanted ? 'Coloured: ' : 'No longer coloured: ') + names.join(', ') + '.' };
  }

  App.PartColors = {
    PALETTE: PALETTE,
    colors: colors, keysUnder: keysUnder, create: create, drawn: drawn,
    sideOf: sideOf, baseOf: baseOf,
    resolve: resolve, command: command,
    on: create()
  };

})(window.App = window.App || {});
