/* ══════════════════════════════════════════════════════════════════
   test-phases.js — the phase model in the browser.

   Two halves, and the first matters more than it looks.

   `App.Phases.activeParts` is a second implementation of
   `server/app/phases.py:active_parts`. It exists because the viewport has to grey out
   what a phase switched off on every click, and cannot ask the server each time. Two
   implementations of one rule drift, so both are held to one generated document --
   `fixtures/phase-cases.js`, owned by `server/tests/test_phase_parity.py`, which
   rebuilds it from the real Python and fails if what is on disk is not what the
   server computes. The cases in it are the ones a careless chain walk gets wrong: a
   part switched off and later back on, an instruction that changes nothing, and a
   phase that says nothing at all.

   The second half is the editing: what the toolbar's four buttons do to a list, and
   what the panel shows for a phase. Those are pure list transforms here; the PATCH
   that follows them is `patches.js`' business.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var FIXTURE = window.PHASE_FIXTURE;

  function project() {
    return JSON.parse(JSON.stringify(FIXTURE.project));
  }

  /* ── Parity with the server ──────────────────────────────────────────── */

  test('the fixture is loaded at all', function () {
    T.ok(FIXTURE, 'fixtures/phase-cases.js did not load -- is it in index.html?');
    T.ok(FIXTURE.project.phases.length > 0);
  });

  test('activeParts agrees with the server for every phase in the fixture',
       function () {
    var p = project();
    Object.keys(FIXTURE.active_parts).forEach(function (id) {
      T.eq(App.Phases.activeParts(p, id).slice().sort(),
           FIXTURE.active_parts[id].slice().sort(),
           'phase ' + id + ' disagrees with server/app/phases.py');
    });
  });

  test('a part switched off and later back on is on', function () {
    /* The case that separates walking the chain from reading the last instruction:
       `soil_L1` is deactivated at dig_1 and activated again at dig_2. */
    var p = project();
    T.ok(App.Phases.activeParts(p, 'dig_1').indexOf('soil_L1') < 0);
    T.ok(App.Phases.activeParts(p, 'dig_2').indexOf('soil_L1') >= 0);
  });

  test('an instruction that changes nothing changes nothing', function () {
    var p = project();
    T.eq(App.Phases.activeParts(p, 'settle').slice().sort(),
         App.Phases.activeParts(p, 'dig_2').slice().sort());
  });

  test('everything is active before any phase switches something off', function () {
    /* The mesh carries every part; the first phase's job is to switch off what has
       not been built yet. Same starting point as the server's. */
    var p = project();
    p.phases = [{ id: 'only', name: 'Only', parent: null,
                  activate: [], deactivate: [] }];
    T.eq(App.Phases.activeParts(p, 'only').slice().sort(),
         FIXTURE.stageable_keys.slice().sort());
  });

  test('a phase nobody has heard of has no active set rather than throwing',
       function () {
    T.eq(App.Phases.activeParts(project(), 'no_such_phase'), null);
  });

  /* ── The execution order ─────────────────────────────────────────────── */

  test('the order is the chain, and matches the server', function () {
    T.eq(App.Phases.order(project()).map(function (ph) { return ph.id; }),
         FIXTURE.order);
  });

  test('a branch has no order, and says which phases branch', function () {
    var p = project();
    p.phases = [
      { id: 'root', name: 'Root', parent: null },
      { id: 'a', name: 'A', parent: 'root' },
      { id: 'b', name: 'B', parent: 'root' }
    ];
    T.eq(App.Phases.order(p), null);
    var problem = App.Phases.branchProblem(p);
    T.ok(problem, 'a branching tree reported no problem');
    T.ok(problem.indexOf('a') >= 0 && problem.indexOf('b') >= 0,
         'the message does not name the phases that branch: ' + problem);
  });

  test('a chain has no branch problem', function () {
    T.eq(App.Phases.branchProblem(project()), null);
  });

  /* ── The panel rows ──────────────────────────────────────────────────── */

  test('every phase becomes one row, in execution order', function () {
    var rows = App.Phases.rows(project());
    T.eq(rows.map(function (r) { return r.id; }), FIXTURE.order);
  });

  test('a row carries what the frozen panel draws', function () {
    var row = App.Phases.rows(project())[0];
    /* js/explorer.js:286-291 reads exactly these four off each row, and the dot's
       class is one of three the stylesheet defines (css/components.css:222-224). */
    T.eq(row.id, 'initial');
    T.eq(row.name, 'Initial stage');
    T.eq(row.kind, 'K0 procedure');
    T.ok(['initial', 'done', 'pending'].indexOf(row.state) >= 0, row.state);
    T.eq(typeof row.depth, 'number');
  });

  /* Plaxis indents each phase under the one it starts from. In a chain -- which is
     the only shape Kratos can run -- that is a staircase, which is what the frozen
     mockup's hardcoded rows show too. */
  test('depth follows the parent chain', function () {
    var depths = App.Phases.rows(project()).map(function (r) { return r.depth; });
    T.eq(depths, [0, 1, 2, 3, 4, 5, 6]);
  });

  test('the first phase is drawn as the initial one', function () {
    T.eq(App.Phases.rows(project())[0].state, 'initial');
  });

  test('phases that have not been run are pending', function () {
    App.Phases.rows(project()).slice(1).forEach(function (row) {
      T.eq(row.state, 'pending', row.id + ' is not pending before a run');
    });
  });

  /* The run log names the stage it reached (server/app/calculate.py's `failed_stage`),
     so the dots can say how far it got rather than all staying grey. */
  test('a finished run marks the stages that completed', function () {
    var rows = App.Phases.rows(project(), { completed: 3 });
    T.eq(rows[0].state, 'initial');
    T.eq(rows[1].state, 'done');
    T.eq(rows[2].state, 'done');
    T.eq(rows[3].state, 'pending');
  });

  /* ── Editing the list ────────────────────────────────────────────────── */

  test('add puts a new phase at the end of the chain', function () {
    var p = project();
    var list = App.Phases.added(p);
    T.eq(list.length, p.phases.length + 1);
    T.eq(list[list.length - 1].parent, 'settle',
         'the new phase does not start from the last one');
    T.eq(list[list.length - 1].calculation, 'Plastic');
  });

  test('add gives the new phase an id nothing else has', function () {
    var p = project();
    var list = App.Phases.added(p);
    var ids = list.map(function (ph) { return ph.id; });
    T.eq(ids.length, new Set(ids).size, 'duplicate phase id: ' + ids.join(', '));
  });

  test('add on an empty project makes a root', function () {
    var p = project();
    p.phases = [];
    var list = App.Phases.added(p);
    T.eq(list.length, 1);
    T.eq(list[0].parent, null);
  });

  /* Insert is the Plaxis button that puts a phase *between* the selected one and its
     parent, which means re-parenting the selected one onto the newcomer. Getting that
     wrong makes a branch, which the server then refuses. */
  test('insert splices a phase in above the selected one', function () {
    var p = project();
    var was = p.phases.map(function (ph) { return ph.id; });
    var list = App.Phases.inserted(p, 'dig_1');

    var fresh = list.filter(function (ph) { return was.indexOf(ph.id) < 0; });
    T.eq(fresh.length, 1, 'insert did not add exactly one phase');

    var byId = {};
    list.forEach(function (ph) { byId[ph.id] = ph; });
    T.eq(fresh[0].parent, 'build_wall', 'the new phase did not take dig_1s parent');
    T.eq(byId['dig_1'].parent, fresh[0].id, 'dig_1 was not re-parented onto it');
  });

  test('inserting never leaves a branch behind', function () {
    var p = project();
    p.phases = App.Phases.inserted(p, 'prop');
    T.eq(App.Phases.branchProblem(p), null);
    T.eq(App.Phases.order(p).length, 8);
  });

  test('delete removes the phase and heals the chain', function () {
    var p = project();
    var list = App.Phases.removed(p, 'prop');
    T.eq(list.length, p.phases.length - 1);
    var byId = {};
    list.forEach(function (ph) { byId[ph.id] = ph; });
    T.ok(!byId['prop'], 'prop survived the delete');
    /* Its child has to adopt its parent, or the chain is cut in two and every phase
       after it becomes unreachable. */
    T.eq(byId['dig_2'].parent, 'dig_1');
    p.phases = list;
    T.eq(App.Phases.branchProblem(p), null);
    T.eq(App.Phases.order(p).length, 6);
  });

  test('deleting the root promotes its child', function () {
    var p = project();
    var list = App.Phases.removed(p, 'initial');
    var byId = {};
    list.forEach(function (ph) { byId[ph.id] = ph; });
    T.eq(byId['null_step'].parent, null);
    p.phases = list;
    T.eq(App.Phases.order(p).length, 6);
  });

  test('deleting the only phase leaves an unphased project', function () {
    var p = project();
    p.phases = [{ id: 'only', name: 'Only', parent: null }];
    T.eq(App.Phases.removed(p, 'only'), []);
  });

  /* What a copy is *for* is repeating a dig: same solver settings, same shape, new
     parts. Copying the instructions too would switch the same bodies off twice, which
     Kratos tolerates and a reader does not. */
  test('copy repeats the settings but not the instructions', function () {
    var p = project();
    var was = p.phases.map(function (ph) { return ph.id; });
    var list = App.Phases.copied(p, 'build_wall');
    var made = list.filter(function (ph) { return was.indexOf(ph.id) < 0; })[0];
    T.ok(made, 'copy added no phase');
    T.eq(made.calculation, 'Plastic');
    T.eq(made.reset_displacements, true, 'the solver settings were not carried over');
    T.eq(made.activate, []);
    T.eq(made.deactivate, []);
    T.ok(made.id !== 'build_wall');
  });

  test('a copy is spliced in after its original, not appended', function () {
    var p = project();
    var was = p.phases.map(function (ph) { return ph.id; });
    var list = App.Phases.copied(p, 'build_wall');
    var byId = {};
    list.forEach(function (ph) { byId[ph.id] = ph; });
    var made = list.filter(function (ph) { return was.indexOf(ph.id) < 0; })[0];
    T.eq(made.parent, 'build_wall');
    T.eq(byId['dig_1'].parent, made.id, 'dig_1 was not re-parented onto the copy');
    p.phases = list;
    T.eq(App.Phases.branchProblem(p), null);
  });

  /* ── Toggling a part in a phase (the viewport's edit) ────────────────── */

  test('toggling an active part deactivates it in that phase', function () {
    var p = project();
    var list = App.Phases.toggled(p, 'prop', 'soil_L2');
    var phase = list.filter(function (ph) { return ph.id === 'prop'; })[0];
    T.ok(phase.deactivate.indexOf('soil_L2') >= 0);
    T.ok(phase.activate.indexOf('soil_L2') < 0, 'the part is in both lists');
  });

  test('toggling an inactive part activates it', function () {
    var p = project();
    // Off since `initial`, and untouched since -- so at `prop` it is genuinely off.
    T.ok(App.Phases.activeParts(p, 'prop').indexOf('soil_L1__lift2') < 0,
         'the fixture no longer has this part switched off at prop');

    var list = App.Phases.toggled(p, 'prop', 'soil_L1__lift2');
    var phase = list.filter(function (ph) { return ph.id === 'prop'; })[0];
    T.ok(phase.activate.indexOf('soil_L1__lift2') >= 0);
    T.ok(phase.deactivate.indexOf('soil_L1__lift2') < 0);
  });

  test('toggling twice returns the phase to where it started', function () {
    var p = project();
    var before = JSON.stringify(p.phases.filter(function (ph) {
      return ph.id === 'prop';
    })[0]);
    p.phases = App.Phases.toggled(p, 'prop', 'soil_L2');
    p.phases = App.Phases.toggled(p, 'prop', 'soil_L2');
    var after = JSON.stringify(p.phases.filter(function (ph) {
      return ph.id === 'prop';
    })[0]);
    T.eq(after, before, 'a part toggled twice left an instruction behind');
  });

  test('toggling never puts a part in both lists of one phase', function () {
    /* `Phase._one_instruction_per_part` refuses that outright, so a toggle that
       produced it would be rejected by the server with the edit already on screen. */
    var p = project();
    ['soil_L2', 'wall', 'anchors', 'soil_L1__lift3'].forEach(function (key) {
      p.phases = App.Phases.toggled(p, 'dig_2', key);
      var phase = p.phases.filter(function (ph) { return ph.id === 'dig_2'; })[0];
      T.eq((phase.activate || []).filter(function (k) {
        return (phase.deactivate || []).indexOf(k) >= 0;
      }), [], 'both lists name ' + key);
    });
  });

  /* ── Inherited vs owned, which is what the viewport greys differently ── */

  test('a part switched off by an ancestor is inherited, not owned', function () {
    var p = project();
    /* `soil_L1__lift3` is switched off in `initial` and never mentioned again. */
    T.eq(App.Phases.ownership(p, 'prop', 'soil_L1__lift3'), 'inherited');
    T.eq(App.Phases.ownership(p, 'initial', 'soil_L1__lift3'), 'own');
  });

  test('a part nothing has touched is neither', function () {
    T.eq(App.Phases.ownership(project(), 'prop', 'soil_L3'), null);
  });

  test('a part re-activated in this phase is owned by it', function () {
    T.eq(App.Phases.ownership(project(), 'dig_2', 'soil_L1'), 'own');
  });

  /* ── What the viewport hides ─────────────────────────────────────────── */

  test('outside staged mode a phase hides nothing', function () {
    /* Soil mode is for building the model, not for looking at one moment of it.
       Hiding the excavated lifts there would make a body the user is trying to draw
       against disappear for a reason nothing on screen explains. */
    ['soil', 'structures', 'mesh', 'flow'].forEach(function (mode) {
      T.eq(App.Phases.hiddenKeys(project(), 'dig_2', mode), []);
    });
  });

  test('in staged mode the parts a phase switched off are hidden', function () {
    var hidden = App.Phases.hiddenKeys(project(), 'prop', 'staged');
    T.ok(hidden.indexOf('soil_L1__lift2') >= 0, 'an inactive lift is still drawn');
    T.ok(hidden.indexOf('soil_L2') < 0, 'an active body was hidden');
  });

  test('the hidden set is exactly the complement of the active one', function () {
    var p = project();
    Object.keys(FIXTURE.active_parts).forEach(function (id) {
      var active = App.Phases.activeParts(p, id);
      var hidden = App.Phases.hiddenKeys(p, id, 'staged');
      T.eq(active.concat(hidden).sort(),
           App.Phases.stageableKeys(p).slice().sort(),
           'phase ' + id + ' neither shows nor hides every part');
      T.eq(active.filter(function (k) { return hidden.indexOf(k) >= 0; }), [],
           'phase ' + id + ' both shows and hides a part');
    });
  });

  test('a project with no phases hides nothing, in any mode', function () {
    /* The compatibility case: an unphased project is one model, all of it, and
       staged mode must not start hiding parts of it. */
    var p = project();
    p.phases = [];
    T.eq(App.Phases.hiddenKeys(p, null, 'staged'), []);
  });

  /* ── The Model explorer's checkbox, in Staged construction mode ─────────
     Ticked means "in the model in the selected phase". Each phase is free to switch
     any part on or off: a part an earlier phase took out is not stuck out, because the
     checkbox is there in every phase to put it back. The state is still inherited
     from the phase before -- that is how Kratos' stages run, one model carried from
     stage to stage -- so switching a part off in one phase leaves it off in the
     phases after it until one of them switches it back on. */

  function phaseOf(list, id) {
    return list.filter(function (ph) { return ph.id === id; })[0];
  }

  function activeAt(p, id, key) {
    return App.Phases.activeParts(p, id).indexOf(key) >= 0;
  }

  test('setActive switches a part off in the selected phase', function () {
    var p = project();
    p.phases = App.Phases.setActive(p, 'prop', ['soil_L2'], false);
    T.ok(!activeAt(p, 'prop', 'soil_L2'));
  });

  test('a part switched off earlier can be switched back on in a later phase', function () {
    var p = project();
    T.ok(!activeAt(p, 'prop', 'soil_L1__lift2'), 'the fixture has it on at prop');
    p.phases = App.Phases.setActive(p, 'prop', ['soil_L1__lift2'], true);
    T.ok(activeAt(p, 'prop', 'soil_L1__lift2'));
    // ...and only from there: the phases before it are untouched.
    var chain = App.Phases.chainTo(p, 'prop').map(function (ph) { return ph.id; });
    chain.slice(0, -1).forEach(function (id) {
      T.eq(activeAt(p, id, 'soil_L1__lift2'), activeAt(project(), id, 'soil_L1__lift2'),
           id + ' changed');
    });
  });

  test('switching a part in one phase changes no phase before it', function () {
    var before = project();
    var p = project();
    p.phases = App.Phases.setActive(p, 'dig_2', ['soil_L2'], false);
    App.Phases.chainTo(p, 'dig_2').slice(0, -1).forEach(function (ph) {
      T.eq(JSON.stringify(phaseOf(p.phases, ph.id)),
           JSON.stringify(phaseOf(before.phases, ph.id)), ph.id + ' was edited');
    });
  });

  test('setting a part to the state it already has adds no instruction', function () {
    var p = project();
    var before = JSON.stringify(phaseOf(p.phases, 'prop'));
    p.phases = App.Phases.setActive(p, 'prop', ['soil_L2'], true);
    T.eq(JSON.stringify(phaseOf(p.phases, 'prop')), before);
  });

  test('switching back what this phase changed drops its instruction', function () {
    var p = project();
    var before = JSON.stringify(phaseOf(p.phases, 'prop'));
    p.phases = App.Phases.setActive(p, 'prop', ['soil_L2'], false);
    p.phases = App.Phases.setActive(p, 'prop', ['soil_L2'], true);
    T.eq(JSON.stringify(phaseOf(p.phases, 'prop')), before);
  });

  test('a group row sets every part under it at once', function () {
    var p = project();
    var keys = ['soil_L2', 'soil_L1__lift2'];
    p.phases = App.Phases.setActive(p, 'prop', keys, true);
    keys.forEach(function (key) { T.ok(activeAt(p, 'prop', key), key); });
    p.phases = App.Phases.setActive(p, 'prop', keys, false);
    keys.forEach(function (key) { T.ok(!activeAt(p, 'prop', key), key); });
  });

  test('setActive never puts a part in both lists of one phase', function () {
    var p = project();
    ['soil_L2', 'wall', 'anchors', 'soil_L1__lift3'].forEach(function (key) {
      p.phases = App.Phases.setActive(p, 'dig_2', [key], false);
      p.phases = App.Phases.setActive(p, 'dig_2', [key], true);
      var phase = phaseOf(p.phases, 'dig_2');
      T.eq((phase.activate || []).filter(function (k) {
        return (phase.deactivate || []).indexOf(k) >= 0;
      }), [], 'both lists name ' + key);
    });
  });

  test('the checkbox state: on, off, or mixed for a group', function () {
    var p = project();
    T.eq(App.Phases.stateIn(p, 'prop', ['soil_L2']), 'on');
    T.eq(App.Phases.stateIn(p, 'prop', ['soil_L1__lift2']), 'off');
    T.eq(App.Phases.stateIn(p, 'prop', ['soil_L2', 'soil_L1__lift2']), 'mixed');
  });

  test('no selected phase hides nothing', function () {
    T.eq(App.Phases.hiddenKeys(project(), null, 'staged'), []);
    T.eq(App.Phases.hiddenKeys(project(), 'no_such_phase', 'staged'), []);
  });

  /* ── The Phases overview ───────────────────────────────────────────────
     The Plaxis "Phases" window: every phase on one line with how long it lasts and
     the time reached at its end, and -- beside it -- what the last calculation made
     of it. The window is DOM (patches.js `phasesDialog`); what it says is here. */

  function dike() {
    function phase(id, name, parent, calculation, days) {
      return { id: id, name: name, parent: parent, calculation: calculation,
               activate: [], deactivate: [], time_interval: days };
    }
    return { stageable_parts: [], phases: [
      phase('1_Initial_stage', 'Initial stage', null, 'K0 procedure', 0),
      phase('2_Null_step', 'Null step', '1_Initial_stage', 'Null step', 0),
      phase('3_Slag_1', 'Slag 1', '2_Null_step', 'Plastic', 17),
      phase('4_Slag_2', 'Slag 2', '3_Slag_1', 'Plastic', 22),
      phase('5_Kraan', 'Kraan load', '4_Slag_2', 'Plastic', 0.5)
    ] };
  }

  test('the overview lists every phase, numbered, in run order', function () {
    var rows = App.Phases.overview(dike(), null);
    T.eq(rows.map(function (r) { return r.number; }), [1, 2, 3, 4, 5]);
    T.eq(rows.map(function (r) { return r.id; }),
         ['1_Initial_stage', '2_Null_step', '3_Slag_1', '4_Slag_2', '5_Kraan']);
    T.eq(rows[0].kind, 'K0 procedure');
  });

  test('T is the time reached at the end of a phase, summed along its chain', function () {
    var rows = App.Phases.overview(dike(), null);
    T.eq(rows.map(function (r) { return r.total; }), [0, 0, 17, 39, 39.5]);
    T.eq(rows[3].interval, 22);
  });

  test('a row reads like the Plaxis list: name, duration, T, and its id', function () {
    var rows = App.Phases.overview(dike(), null);
    T.eq(rows[3].label, 'Slag 2 - 22 d, T = 39 d [4_Slag_2]');
    T.eq(rows[4].label, 'Kraan load - 0.5 d, T = 39.5 d [5_Kraan]');
    T.eq(rows[0].label, 'Initial stage [1_Initial_stage]', 'no time, no times');
  });

  test('before any calculation every phase says so', function () {
    App.Phases.overview(dike(), null).forEach(function (row) {
      T.eq(row.log, 'Not calculated');
    });
  });

  test('a finished run marks every phase OK', function () {
    App.Phases.overview(dike(), { completed: 5 }).forEach(function (row) {
      T.eq(row.log, 'OK');
      T.eq(row.state, row.number === 1 ? 'initial' : 'done');
    });
  });

  test('a failed run names the phase it stopped in, and nothing after it ran', function () {
    var rows = App.Phases.overview(dike(), { completed: 2, failed: true });
    T.eq(rows.map(function (r) { return r.log; }),
         ['OK', 'OK', 'Failed', 'Not calculated', 'Not calculated']);
    T.eq(rows[2].state, 'failed');
  });
})();
