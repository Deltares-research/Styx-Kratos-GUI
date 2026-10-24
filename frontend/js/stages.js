/* ══════════════════════════════════════════════════════════════════
   stages.js — the construction sequence, in the browser.

   The frozen panel (js/explorer.js:281) already draws a stage list, state dots and a
   property grid; it draws them from `App.PHASES`, seven hardcoded rows in
   js/data.js:559 that describe a project nobody has open. This module is what the
   panel reads instead, and what the toolbar above it acts on.

   ── Why the stage model exists twice ──────────────────────────────────────

   `activeParts` below is a second implementation of `core/model/stages.py`'s function
   of the same name. That is a deliberate duplication and worth being uneasy about.
   The reason is the viewport: staged mode has to grey out the parts a stage switched
   off, on every click, while the user is dragging a selection around -- and a round
   trip per click is not a thing anyone would keep. The server stays the authority
   (it is what exports the deck), and the two are held to one generated document,
   `frontend/tests/fixtures/stage-cases.js`, by `tests/test_stage_parity.py`. If
   the rule changes, that test fails before the drift can reach anybody.

   ── A stage stores a diff, not a state ────────────────────────────────────

   `activate` and `deactivate` say what a stage *changes* about the model it inherits
   from its parent. Resolving the diff to a state means walking the parent chain from
   the root -- which is why `activeParts` is not "read the last instruction", and why
   the fixture deliberately contains a part switched off and later switched back on.

   ── What is not here ──────────────────────────────────────────────────────

   Nothing in this file talks to the server. Every function returns a *new* stage
   list and mutates nothing, so a rejected PATCH leaves no half-edit on screen;
   sending them is `patches.js`' business. And the linearisation rule is mirrored
   rather than reimplemented: a branch is refused with the same reasoning and nearly
   the same words as `stages.StageError`, because the user reads one of them.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Stages = (function () {

  function stagesOf(project) {
    return (project && project.stages) || [];
  }

  function index(project) {
    var byId = {};
    stagesOf(project).forEach(function (stage) { byId[stage.id] = stage; });
    return byId;
  }

  function copy(value) { return JSON.parse(JSON.stringify(value)); }

  var GROUNDWATER_FLOW = 'Groundwater flow';

  /* Whether the project is a groundwater flow calculation: it has stages, and every one
     is a "Groundwater flow" stage (`core.model.stages.groundwater_flow`). A mix of flow
     and deformation stages is not one; the export refuses it. */
  function groundwaterFlow(project) {
    var list = stagesOf(project);
    return list.length > 0 && list.every(function (stage) {
      return stage.calculation === GROUNDWATER_FLOW;
    });
  }

  /* Both lists are optional on the wire -- pydantic defaults them and a stage that
     says nothing carries neither -- so every reader goes through here. */
  function listOf(stage, field) { return (stage && stage[field]) || []; }

  /* ── Resolving the tree ──────────────────────────────────────────────── */

  /* The stages from the root down to `id`, inclusive.

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

     Everything starts active: the mesh carries every part, and the first stage's job
     is to switch off what has not been built yet -- which is what Kratos'
     staged-excavation reference's stage 1 does. Mirrors core/model/stages.py:active_parts exactly,
     including that a part in both of one stage's lists is impossible (the schema
     refuses it), so the order within a stage does not matter.

     `null` for a stage that does not exist, rather than an empty set: "nothing is
     active" and "there is no such stage" are different answers, and a viewport
     handed the first would hide the whole model. */
  function activeParts(project, id) {
    if (!index(project)[id]) return null;
    var active = {};
    stageableKeys(project).forEach(function (key) { active[key] = true; });
    chainTo(project, id).forEach(function (stage) {
      listOf(stage, 'deactivate').forEach(function (key) { delete active[key]; });
      listOf(stage, 'activate').forEach(function (key) { active[key] = true; });
    });
    return Object.keys(active).sort();
  }

  /* What a stage may name.

     The server publishes it as `stageable_keys` and it is wider than what is drawn:
     a project that draws no load pads still has line loads, and the reference stages
     one. Falls back to the union of what the stages themselves mention, so the module
     still resolves a fixture or a project the server has not answered for yet. */
  function stageableKeys(project) {
    // `stageable_parts` is the project's own, published by the server for exactly
    // this (schemas.Project). The name differs from the server's method because a
    // pydantic computed field may not share a name with a method beside it.
    if (project && project.stageable_parts) return project.stageable_parts.slice();
    var seen = {};
    stagesOf(project).forEach(function (stage) {
      listOf(stage, 'activate').concat(listOf(stage, 'deactivate'))
        .forEach(function (key) { seen[key] = true; });
    });
    return Object.keys(seen).sort();
  }

  /* Depth first in creation order, or `null` if the tree branches.

     Kratos' SequentialOrchestrator takes one flat execution_list, so a tree with two
     children under one parent has no execution order at all. Same rule and same shape
     as `stages.linearise`; the difference is that this one returns null instead of
     raising, because the editor draws a branching tree rather than refusing to. */
  function order(project) {
    var all = stagesOf(project);
    if (!all.length) return [];
    if (branchProblem(project)) return null;

    // Roots kept apart rather than filed under a sentinel key: a stage id is any
    // string the user can type, so there is no key that is safe to reserve.
    var children = {};
    var roots = [];
    all.forEach(function (stage) {
      if (stage.parent == null) { roots.push(stage); return; }
      (children[stage.parent] = children[stage.parent] || []).push(stage);
    });

    var out = [];
    var stack = roots.slice().reverse();
    var seen = {};
    while (stack.length) {
      var stage = stack.pop();
      if (seen[stage.id]) continue;      // a cycle typed mid-edit
      seen[stage.id] = true;
      out.push(stage);
      stack = stack.concat((children[stage.id] || []).slice().reverse());
    }
    return out.length === all.length ? out : null;
  }

  /* The message for a tree that cannot be run, or null.

     Deliberately close to `stages.StageError`'s wording: the user may meet either,
     depending on whether they hit the toolbar or Calculate, and two different
     sentences about one problem read like two problems. */
  function branchProblem(project) {
    var all = stagesOf(project);
    var byParent = {};
    var roots = [];
    all.forEach(function (stage) {
      if (stage.parent == null) { roots.push(stage); return; }
      (byParent[stage.parent] = byParent[stage.parent] || []).push(stage);
    });

    if (all.length && roots.length !== 1) {
      return 'A construction sequence needs exactly one stage to start from, ' +
             'and this one has ' + roots.length + '.';
    }
    var branched = Object.keys(byParent).filter(function (parent) {
      return byParent[parent].length > 1;
    });
    if (!branched.length) return null;

    var names = byParent[branched[0]].map(function (stage) {
      return '"' + stage.name + '"';
    });
    return 'Stages ' + names.join(' and ') + ' both start from the same stage, so ' +
           'there is no single order to run them in. Kratos runs one sequence of ' +
           'stages: give each of them a different stage to start from, or delete ' +
           'all but one.';
  }

  /* ── The panel rows ──────────────────────────────────────────────────── */

  /* One row per stage, shaped for js/explorer.js:286-291 -- it reads `depth`, `state`,
     `name` and `kind` off each, and nothing else.

     `run` is what the last calculation reported, `{completed: n}`: the run log names
     the stage it reached (core/analysis/calculation.py's `failed_stage`), so the dots can
     say how far it got instead of all staying grey. Omitted, nothing has been run and
     every stage after the first is pending. */
  function rows(project, run) {
    var sequence = order(project) || stagesOf(project);
    var completed = (run && run.completed) || 0;
    return sequence.map(function (stage, position) {
      return {
        id: stage.id,
        name: stage.name,
        kind: stage.calculation || 'Plastic',
        // The three the stylesheet defines (css/components.css:222-224).
        state: position === 0 ? 'initial'
             : (position < completed ? 'done' : 'pending'),
        // Each stage is indented under the one it starts from. For a chain -- the
        // only shape that runs -- that is a staircase, which is what the frozen
        // mockup's own hardcoded rows show.
        depth: chainTo(project, stage.id).length - 1
      };
    });
  }

  /* The Stages overview (patches.js `stagesDialog`): `rows`, plus what the stage list
     puts on each line -- the stage's duration, the time T reached at its end (summed
     along its chain), its id -- and what the last calculation made of it.

     `run` is `{completed, failed}`: how many stages the last run got through, and
     whether it stopped short. A failed run failed in the stage after the last one it
     completed. */
  function days(value) {
    return String(Math.round(value * 1000) / 1000) + ' d';
  }

  function overview(project, run) {
    var byId = index(project);
    var completed = (run && run.completed) || 0;
    return rows(project, run).map(function (row, position) {
      var stage = byId[row.id] || {};
      var total = 0;
      chainTo(project, row.id).forEach(function (each) {
        total += Number(each.time_interval) || 0;
      });
      total = Math.round(total * 1000) / 1000;
      var interval = Number(stage.time_interval) || 0;
      var failedHere = !!(run && run.failed) && position === completed;
      return {
        number: position + 1, id: row.id, name: row.name, kind: row.kind,
        depth: row.depth, interval: interval, total: total,
        state: failedHere ? 'failed' : row.state,
        label: row.name + (interval || total
          ? ' - ' + days(interval) + ', T = ' + days(total) : '') + ' [' + row.id + ']',
        log: position < completed ? 'OK' : failedHere ? 'Failed' : 'Not calculated'
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
      // The server's own defaults, restated so that a stage made here and one made by
      // `Stage()` are the same stage. A mismatch would show up as a field changing by
      // itself the first time the project was reloaded.
      calculation: 'Plastic', loading: 'Staged construction',
      activate: [], deactivate: [],
      reset_displacements: false, max_iterations: 15,
      tolerated_error: 1e-4, time_interval: 0.0
    };
  }

  function lastOf(project) {
    var sequence = order(project) || stagesOf(project);
    return sequence.length ? sequence[sequence.length - 1] : null;
  }

  /* Add: a new stage at the end of the sequence. */
  function added(project) {
    var list = copy(stagesOf(project));
    var tail = lastOf(project);
    var id = freshId(project, 'stage');
    list.push(blank(project, id, 'Stage ' + (list.length + 1),
                    tail ? tail.id : null));
    return list;
  }

  /* Insert: a new stage *between* `id` and the stage it starts from.

     Re-parenting the selected stage onto the newcomer is the whole of the operation
     and the easy half to forget: without it the two are siblings, the tree branches,
     and the server refuses the save with a message about something the user did not
     knowingly do. */
  function inserted(project, id) {
    var byId = index(project);
    var target = byId[id];
    if (!target) return copy(stagesOf(project));

    var made = blank(project, freshId(project, 'stage'), 'New stage', target.parent);
    var list = copy(stagesOf(project));
    list.forEach(function (stage) {
      if (stage.id === id) stage.parent = made.id;
    });
    var at = list.map(function (stage) { return stage.id; }).indexOf(id);
    list.splice(at, 0, made);
    return list;
  }

  /* Delete: remove the stage and heal the chain.

     Its children adopt its parent. Without that the chain is cut in two and every
     stage after the deleted one is unreachable from the root -- which the server
     reports as "stages unreachable from the first one", naming stages the user never
     touched. Deleting the root promotes its child, which is the same rule with
     `parent` null. */
  function removed(project, id) {
    var byId = index(project);
    var target = byId[id];
    if (!target) return copy(stagesOf(project));

    var inherited = target.parent == null ? null : target.parent;
    return copy(stagesOf(project))
      .filter(function (stage) { return stage.id !== id; })
      .map(function (stage) {
        if (stage.parent === id) stage.parent = inherited;
        return stage;
      });
  }

  /* Copy: the same solver settings, spliced in after the original.

     Not the instructions. What a copy is *for* is repeating a step -- another dig,
     another prop -- with the same numerical treatment and different parts; carrying
     `activate`/`deactivate` across would switch the same bodies twice. Kratos
     tolerates that and a reader does not, which is the same reasoning
     `stages.transitions` uses when it drops no-ops from the deck. */
  function copied(project, id) {
    var byId = index(project);
    var original = byId[id];
    if (!original) return copy(stagesOf(project));

    var made = blank(project, freshId(project, 'stage'),
                     original.name + ' (copy)', original.id);
    made.calculation = original.calculation || 'Plastic';
    made.reset_displacements = !!original.reset_displacements;
    if (original.max_iterations != null) made.max_iterations = original.max_iterations;
    if (original.tolerated_error != null) made.tolerated_error = original.tolerated_error;
    if (original.time_interval != null) made.time_interval = original.time_interval;

    var list = copy(stagesOf(project));
    list.forEach(function (stage) {
      if (stage.parent === id) stage.parent = made.id;
    });
    var at = list.map(function (stage) { return stage.id; }).indexOf(id);
    list.splice(at + 1, 0, made);
    return list;
  }

  /* ── Toggling one part in one stage: the viewport's edit ─────────────── */

  /* Who decided a part's state in `id`: 'own' if this stage says so, 'inherited' if
     an ancestor did and this one has not overridden it, null if nothing has mentioned
     it at all.

     The viewport draws the three differently -- an inherited change is greyed --
     so the user can see what they own and what they merely received. */
  function ownership(project, id, key) {
    var chain = chainTo(project, id);
    if (!chain.length) return null;
    var here = chain[chain.length - 1];
    if (listOf(here, 'activate').indexOf(key) >= 0) return 'own';
    if (listOf(here, 'deactivate').indexOf(key) >= 0) return 'own';
    var inherited = chain.slice(0, -1).some(function (stage) {
      return listOf(stage, 'activate').indexOf(key) >= 0 ||
             listOf(stage, 'deactivate').indexOf(key) >= 0;
    });
    return inherited ? 'inherited' : null;
  }

  /* Switch `key` to the opposite of whatever it is in `id`.

     Written as "make this stage say the opposite of what it inherits", not as "append
     an instruction". The difference shows when the state already matches what the
     parent gives: the instruction is then redundant, and this drops it rather than
     leaving it behind -- so toggling twice returns the stage to exactly where it
     started instead of accumulating a no-op that the deck would have to filter out
     later.

     A part never ends up in both lists: `Stage._one_instruction_per_part` refuses
     that outright, so producing it here would mean the server rejecting an edit that
     is already on screen. */
  function toggled(project, id, key) {
    var current = (activeParts(project, id) || []).indexOf(key) >= 0;
    return setActive(project, id, [key], !current);
  }

  /* Make each of `keys` be `wanted` (in the model, or not) in stage `id` -- what the
     Model explorer's checkbox does in Staged construction mode, for one part or for a
     group row's every part.

     Only stage `id` is edited, so no stage before it changes; the ones after it inherit
     the new state until one of them says otherwise, which is how Kratos runs its
     stages -- one model, carried from stage to stage. Each key ends up with the
     smallest instruction that gives the wanted state: none at all when the parent
     already gives it (which is also how switching back drops an instruction rather
     than stacking a second one), and never both lists for one part, which the server
     refuses (`Stage._one_instruction_per_part`). */
  function setActive(project, id, keys, wanted) {
    var byId = index(project);
    if (!byId[id]) return copy(stagesOf(project));

    var before = chainTo(project, id).slice(0, -1);
    function inheritedActive(key) {
      var active = true;      // everything starts in the model
      before.forEach(function (stage) {
        if (listOf(stage, 'deactivate').indexOf(key) >= 0) active = false;
        if (listOf(stage, 'activate').indexOf(key) >= 0) active = true;
      });
      return active;
    }

    return copy(stagesOf(project)).map(function (stage) {
      if (stage.id !== id) return stage;
      var activate = listOf(stage, 'activate').slice();
      var deactivate = listOf(stage, 'deactivate').slice();
      keys.forEach(function (key) {
        activate = activate.filter(function (k) { return k !== key; });
        deactivate = deactivate.filter(function (k) { return k !== key; });
        // Only state an instruction the parent does not already give.
        if (wanted !== inheritedActive(key)) (wanted ? activate : deactivate).push(key);
      });
      stage.activate = activate;
      stage.deactivate = deactivate;
      return stage;
    });
  }

  /* 'on', 'off' or -- for a group row whose parts differ -- 'mixed', in stage `id`. */
  function stateIn(project, id, keys) {
    var active = activeParts(project, id) || [];
    var on = keys.filter(function (key) { return active.indexOf(key) >= 0; }).length;
    return !on ? 'off' : on === keys.length ? 'on' : 'mixed';
  }

  /* Which part keys the viewport should not draw, given the selected stage.

     Staged mode only. The other four modes are for building the model, and hiding
     the excavated lifts in Soil mode would make a body the user is trying to draw
     against vanish for a reason nothing on screen explains -- the stage list is not
     even visible there. The dock only shows the stages panel in staged mode
     (js/app.js:25-33), and this matches it.

     Empty for an unstaged project, which is the compatibility case: one model, all of
     it, exported exactly as it always was. Empty too when no stage is selected or the
     selected one has gone -- "hide nothing" is the safe answer to "I do not know",
     because the opposite hides the whole model. */
  function hiddenKeys(project, stageId, mode) {
    if (mode !== 'staged') return [];
    var active = activeParts(project, stageId);
    if (!active) return [];
    return stageableKeys(project).filter(function (key) {
      return active.indexOf(key) < 0;
    });
  }

  return {
    GROUNDWATER_FLOW: GROUNDWATER_FLOW, groundwaterFlow: groundwaterFlow,
    chainTo: chainTo, activeParts: activeParts, stageableKeys: stageableKeys,
    hiddenKeys: hiddenKeys,
    order: order, branchProblem: branchProblem, rows: rows, overview: overview,
    added: added, inserted: inserted, removed: removed, copied: copied,
    ownership: ownership, toggled: toggled, setActive: setActive, stateIn: stateIn
  };
})();

/* Deprecated: the name before Styx took Kratos' word. */
App.Phases = App.Stages;
