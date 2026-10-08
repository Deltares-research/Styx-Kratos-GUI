/* ══════════════════════════════════════════════════════════════════
   phases.js — the construction sequence, in the browser.

   The frozen panel (js/explorer.js:281) already draws a phase list, state dots and a
   property grid; it draws them from `App.PHASES`, seven hardcoded rows in
   js/data.js:559 that describe a project nobody has open. This module is what the
   panel reads instead, and what the toolbar above it acts on.

   ── Why the phase model exists twice ──────────────────────────────────────

   `activeParts` below is a second implementation of `server/app/phases.py`'s function
   of the same name. That is a deliberate duplication and worth being uneasy about.
   The reason is the viewport: staged mode has to grey out the parts a phase switched
   off, on every click, while the user is dragging a selection around -- and a round
   trip per click is not a thing anyone would keep. The server stays the authority
   (it is what exports the deck), and the two are held to one generated document,
   `live/tests/fixtures/phase-cases.js`, by `server/tests/test_phase_parity.py`. If
   the rule changes, that test fails before the drift can reach anybody.

   ── A phase stores a diff, not a state ────────────────────────────────────

   `activate` and `deactivate` say what a phase *changes* about the model it inherits
   from its parent. Resolving the diff to a state means walking the parent chain from
   the root -- which is why `activeParts` is not "read the last instruction", and why
   the fixture deliberately contains a part switched off and later switched back on.

   ── What is not here ──────────────────────────────────────────────────────

   Nothing in this file talks to the server. Every function returns a *new* phase
   list and mutates nothing, so a rejected PATCH leaves no half-edit on screen;
   sending them is `patches.js`' business. And the linearisation rule is mirrored
   rather than reimplemented: a branch is refused with the same reasoning and nearly
   the same words as `phases.PhaseError`, because the user reads one of them.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Phases = (function () {

  function phasesOf(project) {
    return (project && project.phases) || [];
  }

  function index(project) {
    var byId = {};
    phasesOf(project).forEach(function (phase) { byId[phase.id] = phase; });
    return byId;
  }

  function copy(value) { return JSON.parse(JSON.stringify(value)); }

  /* Both lists are optional on the wire -- pydantic defaults them and a phase that
     says nothing carries neither -- so every reader goes through here. */
  function listOf(phase, field) { return (phase && phase[field]) || []; }

  /* ── Resolving the tree ──────────────────────────────────────────────── */

  /* The phases from the root down to `id`, inclusive.

     Follows parents rather than the execution order, so it resolves a half-built
     branch too -- the editor needs that, because a branch is a legitimate thing to
     have on screen even though it is not a thing Kratos can run. Guarded against a
     cycle: the server's schema forbids one, but this runs on whatever is in the
     browser, including a list mid-edit. */
  function chainTo(project, id) {
    var byId = index(project);
    var chain = [];
    var seen = {};
    var at = byId[id];
    while (at && !seen[at.id]) {
      seen[at.id] = true;
      chain.push(at);
      at = at.parent == null ? null : byId[at.parent];
    }
    return chain.reverse();
  }

  /* Which parts are in the model during `id`, as a sorted array.

     Everything starts active: the mesh carries every part, and the first phase's job
     is to switch off what has not been built yet -- which is what the CROW
     reference's stage 1 does. Mirrors server/app/phases.py:active_parts exactly,
     including that a part in both of one phase's lists is impossible (the schema
     refuses it), so the order within a phase does not matter.

     `null` for a phase that does not exist, rather than an empty set: "nothing is
     active" and "there is no such phase" are different answers, and a viewport
     handed the first would hide the whole model. */
  function activeParts(project, id) {
    if (!index(project)[id]) return null;
    var active = {};
    stageableKeys(project).forEach(function (key) { active[key] = true; });
    chainTo(project, id).forEach(function (phase) {
      listOf(phase, 'deactivate').forEach(function (key) { delete active[key]; });
      listOf(phase, 'activate').forEach(function (key) { active[key] = true; });
    });
    return Object.keys(active).sort();
  }

  /* What a phase may name.

     The server publishes it as `stageable_keys` and it is wider than what is drawn:
     a project that draws no load pads still has line loads, and the reference stages
     one. Falls back to the union of what the phases themselves mention, so the module
     still resolves a fixture or a project the server has not answered for yet. */
  function stageableKeys(project) {
    // `stageable_parts` is the project's own, published by the server for exactly
    // this (schemas.Project). The name differs from the server's method because a
    // pydantic computed field may not share a name with a method beside it.
    if (project && project.stageable_parts) return project.stageable_parts.slice();
    var seen = {};
    phasesOf(project).forEach(function (phase) {
      listOf(phase, 'activate').concat(listOf(phase, 'deactivate'))
        .forEach(function (key) { seen[key] = true; });
    });
    return Object.keys(seen).sort();
  }

  /* Depth first in creation order, or `null` if the tree branches.

     Kratos' SequentialOrchestrator takes one flat execution_list, so a tree with two
     children under one parent has no execution order at all. Same rule and same shape
     as `phases.linearise`; the difference is that this one returns null instead of
     raising, because the editor draws a branching tree rather than refusing to. */
  function order(project) {
    var all = phasesOf(project);
    if (!all.length) return [];
    if (branchProblem(project)) return null;

    // Roots kept apart rather than filed under a sentinel key: a phase id is any
    // string the user can type, so there is no key that is safe to reserve.
    var children = {};
    var roots = [];
    all.forEach(function (phase) {
      if (phase.parent == null) { roots.push(phase); return; }
      (children[phase.parent] = children[phase.parent] || []).push(phase);
    });

    var out = [];
    var stack = roots.slice().reverse();
    var seen = {};
    while (stack.length) {
      var phase = stack.pop();
      if (seen[phase.id]) continue;      // a cycle typed mid-edit
      seen[phase.id] = true;
      out.push(phase);
      stack = stack.concat((children[phase.id] || []).slice().reverse());
    }
    return out.length === all.length ? out : null;
  }

  /* The message for a tree that cannot be run, or null.

     Deliberately close to `phases.PhaseError`'s wording: the user may meet either,
     depending on whether they hit the toolbar or Calculate, and two different
     sentences about one problem read like two problems. */
  function branchProblem(project) {
    var all = phasesOf(project);
    var byParent = {};
    var roots = [];
    all.forEach(function (phase) {
      if (phase.parent == null) { roots.push(phase); return; }
      (byParent[phase.parent] = byParent[phase.parent] || []).push(phase);
    });

    if (all.length && roots.length !== 1) {
      return 'A construction sequence needs exactly one phase to start from, ' +
             'and this one has ' + roots.length + '.';
    }
    var branched = Object.keys(byParent).filter(function (parent) {
      return byParent[parent].length > 1;
    });
    if (!branched.length) return null;

    var names = byParent[branched[0]].map(function (phase) {
      return '"' + phase.name + '"';
    });
    return 'Phases ' + names.join(' and ') + ' both start from the same phase, so ' +
           'there is no single order to run them in. Kratos runs one sequence of ' +
           'stages: give each of them a different phase to start from, or delete ' +
           'all but one.';
  }

  /* ── The panel rows ──────────────────────────────────────────────────── */

  /* One row per phase, shaped for js/explorer.js:286-291 -- it reads `depth`, `state`,
     `name` and `kind` off each, and nothing else.

     `run` is what the last calculation reported, `{completed: n}`: the run log names
     the stage it reached (server/app/calculate.py's `failed_stage`), so the dots can
     say how far it got instead of all staying grey. Omitted, nothing has been run and
     every phase after the first is pending. */
  function rows(project, run) {
    var sequence = order(project) || phasesOf(project);
    var completed = (run && run.completed) || 0;
    return sequence.map(function (phase, position) {
      return {
        id: phase.id,
        name: phase.name,
        kind: phase.calculation || 'Plastic',
        // The three the stylesheet defines (css/components.css:222-224).
        state: position === 0 ? 'initial'
             : (position < completed ? 'done' : 'pending'),
        // Plaxis indents each phase under the one it starts from. For a chain -- the
        // only shape that runs -- that is a staircase, which is what the frozen
        // mockup's own hardcoded rows show.
        depth: chainTo(project, phase.id).length - 1
      };
    });
  }

  /* ── Editing: every one of these returns a new list ──────────────────── */

  function freshId(project, stem) {
    var taken = index(project);
    var n = 1;
    while (taken[stem + '_' + n]) n += 1;
    return stem + '_' + n;
  }

  function blank(project, id, name, parent) {
    return {
      id: id, name: name, parent: parent == null ? null : parent,
      // The server's own defaults, restated so that a phase made here and one made by
      // `Phase()` are the same phase. A mismatch would show up as a field changing by
      // itself the first time the project was reloaded.
      calculation: 'Plastic', loading: 'Staged construction',
      activate: [], deactivate: [],
      reset_displacements: false, max_iterations: 15,
      tolerated_error: 1e-4, time_interval: 0.0
    };
  }

  function lastOf(project) {
    var sequence = order(project) || phasesOf(project);
    return sequence.length ? sequence[sequence.length - 1] : null;
  }

  /* Add: a new phase at the end of the sequence. */
  function added(project) {
    var list = copy(phasesOf(project));
    var tail = lastOf(project);
    var id = freshId(project, 'phase');
    list.push(blank(project, id, 'Phase ' + (list.length + 1),
                    tail ? tail.id : null));
    return list;
  }

  /* Insert: a new phase *between* `id` and the phase it starts from.

     Re-parenting the selected phase onto the newcomer is the whole of the operation
     and the easy half to forget: without it the two are siblings, the tree branches,
     and the server refuses the save with a message about something the user did not
     knowingly do. */
  function inserted(project, id) {
    var byId = index(project);
    var target = byId[id];
    if (!target) return copy(phasesOf(project));

    var made = blank(project, freshId(project, 'phase'), 'New phase', target.parent);
    var list = copy(phasesOf(project));
    list.forEach(function (phase) {
      if (phase.id === id) phase.parent = made.id;
    });
    var at = list.map(function (phase) { return phase.id; }).indexOf(id);
    list.splice(at, 0, made);
    return list;
  }

  /* Delete: remove the phase and heal the chain.

     Its children adopt its parent. Without that the chain is cut in two and every
     phase after the deleted one is unreachable from the root -- which the server
     reports as "phases unreachable from the first one", naming phases the user never
     touched. Deleting the root promotes its child, which is the same rule with
     `parent` null. */
  function removed(project, id) {
    var byId = index(project);
    var target = byId[id];
    if (!target) return copy(phasesOf(project));

    var inherited = target.parent == null ? null : target.parent;
    return copy(phasesOf(project))
      .filter(function (phase) { return phase.id !== id; })
      .map(function (phase) {
        if (phase.parent === id) phase.parent = inherited;
        return phase;
      });
  }

  /* Copy: the same solver settings, spliced in after the original.

     Not the instructions. What a copy is *for* is repeating a step -- another dig,
     another prop -- with the same numerical treatment and different parts; carrying
     `activate`/`deactivate` across would switch the same bodies twice. Kratos
     tolerates that and a reader does not, which is the same reasoning
     `phases.transitions` uses when it drops no-ops from the deck. */
  function copied(project, id) {
    var byId = index(project);
    var original = byId[id];
    if (!original) return copy(phasesOf(project));

    var made = blank(project, freshId(project, 'phase'),
                     original.name + ' (copy)', original.id);
    made.calculation = original.calculation || 'Plastic';
    made.reset_displacements = !!original.reset_displacements;
    if (original.max_iterations != null) made.max_iterations = original.max_iterations;
    if (original.tolerated_error != null) made.tolerated_error = original.tolerated_error;
    if (original.time_interval != null) made.time_interval = original.time_interval;

    var list = copy(phasesOf(project));
    list.forEach(function (phase) {
      if (phase.parent === id) phase.parent = made.id;
    });
    var at = list.map(function (phase) { return phase.id; }).indexOf(id);
    list.splice(at + 1, 0, made);
    return list;
  }

  /* ── Toggling one part in one phase: the viewport's edit ─────────────── */

  /* Who decided a part's state in `id`: 'own' if this phase says so, 'inherited' if
     an ancestor did and this one has not overridden it, null if nothing has mentioned
     it at all.

     The viewport draws the three differently -- Plaxis greys an inherited change --
     so the user can see what they own and what they merely received. */
  function ownership(project, id, key) {
    var chain = chainTo(project, id);
    if (!chain.length) return null;
    var here = chain[chain.length - 1];
    if (listOf(here, 'activate').indexOf(key) >= 0) return 'own';
    if (listOf(here, 'deactivate').indexOf(key) >= 0) return 'own';
    var inherited = chain.slice(0, -1).some(function (phase) {
      return listOf(phase, 'activate').indexOf(key) >= 0 ||
             listOf(phase, 'deactivate').indexOf(key) >= 0;
    });
    return inherited ? 'inherited' : null;
  }

  /* Switch `key` to the opposite of whatever it is in `id`.

     Written as "make this phase say the opposite of what it inherits", not as "append
     an instruction". The difference shows when the state already matches what the
     parent gives: the instruction is then redundant, and this drops it rather than
     leaving it behind -- so toggling twice returns the phase to exactly where it
     started instead of accumulating a no-op that the deck would have to filter out
     later.

     A part never ends up in both lists: `Phase._one_instruction_per_part` refuses
     that outright, so producing it here would mean the server rejecting an edit that
     is already on screen. */
  function toggled(project, id, key) {
    var current = (activeParts(project, id) || []).indexOf(key) >= 0;
    return setActive(project, id, [key], !current);
  }

  /* Make each of `keys` be `wanted` (in the model, or not) in phase `id` -- what the
     Model explorer's checkbox does in Staged construction mode, for one part or for a
     group row's every part.

     Only phase `id` is edited, so no phase before it changes; the ones after it inherit
     the new state until one of them says otherwise, which is how Kratos runs its
     stages -- one model, carried from stage to stage. Each key ends up with the
     smallest instruction that gives the wanted state: none at all when the parent
     already gives it (which is also how switching back drops an instruction rather
     than stacking a second one), and never both lists for one part, which the server
     refuses (`Phase._one_instruction_per_part`). */
  function setActive(project, id, keys, wanted) {
    var byId = index(project);
    if (!byId[id]) return copy(phasesOf(project));

    var before = chainTo(project, id).slice(0, -1);
    function inheritedActive(key) {
      var active = true;      // everything starts in the model
      before.forEach(function (phase) {
        if (listOf(phase, 'deactivate').indexOf(key) >= 0) active = false;
        if (listOf(phase, 'activate').indexOf(key) >= 0) active = true;
      });
      return active;
    }

    return copy(phasesOf(project)).map(function (phase) {
      if (phase.id !== id) return phase;
      var activate = listOf(phase, 'activate').slice();
      var deactivate = listOf(phase, 'deactivate').slice();
      keys.forEach(function (key) {
        activate = activate.filter(function (k) { return k !== key; });
        deactivate = deactivate.filter(function (k) { return k !== key; });
        // Only state an instruction the parent does not already give.
        if (wanted !== inheritedActive(key)) (wanted ? activate : deactivate).push(key);
      });
      phase.activate = activate;
      phase.deactivate = deactivate;
      return phase;
    });
  }

  /* 'on', 'off' or -- for a group row whose parts differ -- 'mixed', in phase `id`. */
  function stateIn(project, id, keys) {
    var active = activeParts(project, id) || [];
    var on = keys.filter(function (key) { return active.indexOf(key) >= 0; }).length;
    return !on ? 'off' : on === keys.length ? 'on' : 'mixed';
  }

  /* Which part keys the viewport should not draw, given the selected phase.

     Staged mode only. The other four modes are for building the model, and hiding
     the excavated lifts in Soil mode would make a body the user is trying to draw
     against vanish for a reason nothing on screen explains -- the phase list is not
     even visible there. The dock only shows the phases panel in staged mode
     (js/app.js:25-33), and this matches it.

     Empty for an unphased project, which is the compatibility case: one model, all of
     it, exported exactly as it always was. Empty too when no phase is selected or the
     selected one has gone -- "hide nothing" is the safe answer to "I do not know",
     because the opposite hides the whole model. */
  function hiddenKeys(project, phaseId, mode) {
    if (mode !== 'staged') return [];
    var active = activeParts(project, phaseId);
    if (!active) return [];
    return stageableKeys(project).filter(function (key) {
      return active.indexOf(key) < 0;
    });
  }

  return {
    chainTo: chainTo, activeParts: activeParts, stageableKeys: stageableKeys,
    hiddenKeys: hiddenKeys,
    order: order, branchProblem: branchProblem, rows: rows,
    added: added, inserted: inserted, removed: removed, copied: copied,
    ownership: ownership, toggled: toggled, setActive: setActive, stateIn: stateIn
  };
})();
