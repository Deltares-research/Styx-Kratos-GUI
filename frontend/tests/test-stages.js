/* ══════════════════════════════════════════════════════════════════
   test-stages.js — the stage model in the browser.

   Two halves, and the first matters more than it looks.

   `App.Stages.activeParts` is a second implementation of
   `core/model/stages.py:active_parts`. It exists because the viewport has to grey out
   what a stage switched off on every click, and cannot ask the server each time. Two
   implementations of one rule drift, so both are held to one generated document --
   `fixtures/stage-cases.js`, owned by `tests/test_stage_parity.py`, which
   rebuilds it from the real Python and fails if what is on disk is not what the
   server computes. The cases in it are the ones a careless chain walk gets wrong: a
   part switched off and later back on, an instruction that changes nothing, and a
   stage that says nothing at all.

   The second half is the editing: what the toolbar's four buttons do to a list, and
   what the panel shows for a stage. Those are pure list transforms here; the PATCH
   that follows them is `patches.js`' business.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var FIXTURE = window.STAGE_FIXTURE;

  function project() {
    return JSON.parse(JSON.stringify(FIXTURE.project));
  }

  /* ── Parity with the server ──────────────────────────────────────────── */

  test('the fixture is loaded at all', function () {
    T.ok(FIXTURE, 'fixtures/stage-cases.js did not load -- is it in index.html?');
    T.ok(FIXTURE.project.stages.length > 0);
  });

  test('App.Phases is the same module as App.Stages', function () {
    T.ok(App.Phases === App.Stages, 'the old name is an alias');
  });

  test('reads project.stages', function () {
    var p = { stages: [{ id: 's1', name: 'Initial', parent: null, deactivate: ['wall'] }],
              stageable_parts: ['wall', 'soil_1'] };
    T.eq(App.Stages.activeParts(p, 's1'), ['soil_1']);
  });

  test('older projects derive unique stageable keys from both activation lists', function () {
    var p = { stages: [
      { id: 'initial', parent: null, activate: ['wall', 'soil'], deactivate: ['load'] },
      { id: 'dig', parent: 'initial', activate: ['load'], deactivate: ['soil', 'soil'] }
    ] };
    T.eq(App.Stages.stageableKeys(p), ['load', 'soil', 'wall']);
    T.eq(App.Stages.activeParts(p, 'initial'), ['soil', 'wall']);
    T.eq(App.Stages.activeParts(p, 'dig'), ['load', 'wall']);
    T.eq(p.stages[1].deactivate, ['soil', 'soil'], 'reading does not rewrite the saved stages');
  });

  test('activeParts agrees with the server for every stage in the fixture',
       function () {
    var p = project();
    Object.keys(FIXTURE.active_parts).forEach(function (id) {
      T.eq(App.Stages.activeParts(p, id).slice().sort(),
           FIXTURE.active_parts[id].slice().sort(),
           'stage ' + id + ' disagrees with core/model/stages.py');
    });
  });

  /* The editing, held to core/model/stages.py's twins: the command line adds, inserts,
     deletes, copies and switches parts the way the toolbar and the explorer do. */
  (FIXTURE.edits || []).forEach(function (edit) {
    test('App.Stages.' + edit.call + '(' + JSON.stringify(edit.args).slice(1, -1)
         + ') agrees with the command line', function () {
      var args = [project()].concat(JSON.parse(JSON.stringify(edit.args)));
      T.eq(App.Stages[edit.call].apply(null, args), edit.result);
    });
  });

  /* The expert solver settings, held to core/model/solver.py's `resolve` by the
     fixture tests/test_solver_parity.py writes. */
  var SOLVER = window.SOLVER_FIXTURE;

  test('the expert settings catalogue and its fixture are loaded', function () {
    T.ok((App.SOLVER_SETTINGS || []).length > 0,
         'js/solver-settings.js did not load -- is it in index.html?');
    T.ok(SOLVER && SOLVER.cases.length > 0,
         'fixtures/solver-cases.js did not load -- is it in index.html?');
  });

  ((SOLVER && SOLVER.cases) || []).forEach(function (each) {
    test('resolveSolver(' + each.calculation + ', ' + each.time_integration + ', ' +
         JSON.stringify(each.overrides) + ', ' + each.model_strategy +
         ') agrees with the server', function () {
      T.eq(App.Stages.resolveSolver(each.calculation, each.time_integration,
                                    each.overrides, each.model_strategy), each.rows);
    });
  });

  function solverValue(rows, key) {
    var row = rows.filter(function (each) { return each.key === key; })[0];
    return row ? row.value : undefined;
  }

  test('a mechanical stage is solved by Newton-Raphson with a scaled Sparse LU',
       function () {
    var rows = App.Stages.solverRows({}, { calculation: 'mechanical',
                                           time_integration: 'static' });
    T.eq(solverValue(rows, 'strategy_type'), 'newton_raphson');
    T.eq(solverValue(rows, 'number_cycles'), 1);
    T.eq(solverValue(rows, 'linear_solver_scaling'), true);
    var linear = rows.filter(function (row) { return row.key === 'linear_solver_type'; })[0];
    T.eq(linear.value, 'LinearSolversApplication.sparse_lu');
    T.eq(linear.locked, null);
  });

  test('the quasi-Newton strategy fixes its Sparse LU', function () {
    var rows = App.Stages.solverRows({}, {
      calculation: 'mechanical', time_integration: 'static',
      solver_settings: { strategy_type: 'quasi_newton' } });
    var linear = rows.filter(function (row) { return row.key === 'linear_solver_type'; })[0];
    T.eq(linear.value, 'LinearSolversApplication.sparse_lu');
    T.ok(linear.locked, 'the quasi-Newton strategy fixes its linear solver');
  });

  test('another strategy lets the linear solver be chosen', function () {
    var rows = App.Stages.solverRows({}, {
      calculation: 'mechanical', time_integration: 'static',
      solver_settings: { strategy_type: 'newton_raphson', linear_solver_type: 'amgcl' } });
    var linear = rows.filter(function (row) { return row.key === 'linear_solver_type'; })[0];
    T.eq(linear.locked, null);
    T.eq(linear.value, 'amgcl');
    T.eq(solverValue(rows, 'linear_solver_smoother_type'), 'ilu0',
         'an AMGCL solver has its own settings');
    T.eq(solverValue(rows, 'quasi_newton_type'), undefined,
         'and the quasi-Newton ones are gone');
  });

  test('a flow stage takes its default strategy from the server', function () {
    var p = { model_strategies: { only: 'newton_raphson_with_seepage' } };
    var rows = App.Stages.solverRows(p, { id: 'only', calculation: 'flow',
                                          time_integration: 'static' });
    var strategy = rows[0];
    T.eq(strategy.value, 'newton_raphson_with_seepage');
    T.ok(strategy.locked, 'a seepage face fixes it');
    T.eq(App.Stages.solverLabel('strategy_type', strategy.value),
         'Newton-Raphson with seepage');
  });

  test('only a dynamic stage has a time scheme', function () {
    var still = App.Stages.solverRows({}, { calculation: 'mechanical',
                                            time_integration: 'static' });
    var moving = App.Stages.solverRows({}, { calculation: 'mechanical',
                                             time_integration: 'dynamic' });
    T.eq(solverValue(still, 'newmark_beta'), undefined);
    T.eq(solverValue(moving, 'newmark_beta'), 0.25);
  });

  test('the linear strategy has nothing to converge', function () {
    T.ok(App.Stages.iterates(App.Stages.solverRows({}, { calculation: 'mechanical' })));
    T.ok(!App.Stages.iterates(App.Stages.solverRows({}, {
      calculation: 'mechanical', solver_settings: { strategy_type: 'linear' } })));
  });

  test('a part switched off and later back on is on', function () {
    /* The case that separates walking the chain from reading the last instruction:
       `soil_L1__outside` is deactivated at dig_1 and activated again at dig_2. */
    var p = project();
    T.ok(App.Stages.activeParts(p, 'dig_1').indexOf('soil_L1__outside') < 0);
    T.ok(App.Stages.activeParts(p, 'dig_2').indexOf('soil_L1__outside') >= 0);
  });

  test('an instruction that changes nothing changes nothing', function () {
    var p = project();
    T.eq(App.Stages.activeParts(p, 'settle').slice().sort(),
         App.Stages.activeParts(p, 'dig_2').slice().sort());
  });

  test('everything is active before any stage switches something off', function () {
    /* The mesh carries every part; the first stage's job is to switch off what has
       not been built yet. Same starting point as the server's. */
    var p = project();
    p.stages = [{ id: 'only', name: 'Only', parent: null,
                  activate: [], deactivate: [] }];
    T.eq(App.Stages.activeParts(p, 'only').slice().sort(),
         FIXTURE.stageable_keys.slice().sort());
  });

  test('a stage nobody has heard of has no active set rather than throwing',
       function () {
    T.eq(App.Stages.activeParts(project(), 'no_such_stage'), null);
  });

  /* ── The execution order ─────────────────────────────────────────────── */

  test('the order is the chain, and matches the server', function () {
    T.eq(App.Stages.order(project()).map(function (ph) { return ph.id; }),
         FIXTURE.order);
  });

  test('a branch has no order, and says which stages branch', function () {
    var p = project();
    p.stages = [
      { id: 'root', name: 'Root', parent: null },
      { id: 'a', name: 'A', parent: 'root' },
      { id: 'b', name: 'B', parent: 'root' }
    ];
    T.eq(App.Stages.order(p), null);
    var problem = App.Stages.branchProblem(p);
    T.ok(problem, 'a branching tree reported no problem');
    T.ok(problem.indexOf('a') >= 0 && problem.indexOf('b') >= 0,
         'the message does not name the stages that branch: ' + problem);
  });

  test('a chain has no branch problem', function () {
    T.eq(App.Stages.branchProblem(project()), null);
  });

  /* ── The panel rows ──────────────────────────────────────────────────── */

  test('every stage becomes one row, in execution order', function () {
    var rows = App.Stages.rows(project());
    T.eq(rows.map(function (r) { return r.id; }), FIXTURE.order);
  });

  test('a row carries what the frozen panel draws', function () {
    var row = App.Stages.rows(project())[0];
    /* js/explorer.js:286-291 reads exactly these four off each row, and the dot's
       class is one of three the stylesheet defines (css/components.css:222-224). */
    T.eq(row.id, 'initial');
    T.eq(row.name, 'Initial stage');
    T.eq(row.kind, 'Mechanical, K0');
    T.ok(['initial', 'done', 'pending'].indexOf(row.state) >= 0, row.state);
    T.eq(typeof row.depth, 'number');
  });

  /* Each stage is indented under the one it starts from. In a chain -- which is
     the only shape Kratos can run -- that is a staircase, which is what the frozen
     mockup's hardcoded rows show too. */
  test('depth follows the parent chain', function () {
    var depths = App.Stages.rows(project()).map(function (r) { return r.depth; });
    T.eq(depths, [0, 1, 2, 3, 4, 5, 6]);
  });

  test('the first stage is drawn as the initial one', function () {
    T.eq(App.Stages.rows(project())[0].state, 'initial');
  });

  test('stages that have not been run are pending', function () {
    App.Stages.rows(project()).slice(1).forEach(function (row) {
      T.eq(row.state, 'pending', row.id + ' is not pending before a run');
    });
  });

  /* The run log names the stage it reached (core/analysis/calculation.py's `failed_stage`),
     so the dots can say how far it got rather than all staying grey. */
  test('a finished run marks the stages that completed', function () {
    var rows = App.Stages.rows(project(), { completed: 3 });
    T.eq(rows[0].state, 'initial');
    T.eq(rows[1].state, 'done');
    T.eq(rows[2].state, 'done');
    T.eq(rows[3].state, 'pending');
  });

  /* ── Editing the list ────────────────────────────────────────────────── */

  test('add puts a new stage at the end of the chain', function () {
    var p = project();
    var list = App.Stages.added(p);
    T.eq(list.length, p.stages.length + 1);
    T.eq(list[list.length - 1].parent, 'settle',
         'the new stage does not start from the last one');
    T.eq(list[list.length - 1].calculation, 'mechanical');
    T.eq(list[list.length - 1].stress_initialisation, 'none');
    T.eq(list[list.length - 1].time_integration, 'static');
  });

  /* ── The three choices of a stage ────────────────────────────────────── */

  test('a row says what a stage solves for, and how', function () {
    var kind = App.Stages.kindOf;
    T.eq(kind({ calculation: 'mechanical', stress_initialisation: 'none' }), 'Mechanical');
    T.eq(kind({ calculation: 'mechanical', stress_initialisation: 'gravity' }),
         'Mechanical, gravity');
    T.eq(kind({ calculation: 'flow', time_integration: 'dynamic' }), 'Flow, dynamic');
  });

  test('the calculation types are mechanical and flow', function () {
    T.eq(App.Stages.CALCULATION_TYPES.map(function (o) { return o[0]; }),
         ['mechanical', 'flow']);
    T.eq(App.Stages.STRESS_INITIALISATIONS.map(function (o) { return o[0]; }),
         ['K0', 'gravity', 'none']);
    T.eq(App.Stages.TIME_INTEGRATIONS.map(function (o) { return o[0]; }),
         ['static', 'dynamic']);
  });

  /* The calculation type and the stress initialisation are the initial stage's
     (`core.model.stages.edited`); the parity fixture holds the rest of it. */
  test('a flow sequence is chosen in the initial stage, and has no stresses', function () {
    var list = App.Stages.edited(project(), 'initial', 'calculation', 'flow');
    T.ok(list.every(function (stage) { return stage.calculation === 'flow'; }),
         'not every stage became a flow stage');
    T.ok(list.every(function (stage) { return stage.stress_initialisation === 'none'; }));
    T.eq(App.Stages.edited(project(), 'dig_1', 'calculation', 'flow'), project().stages,
         'a later stage changed the calculation type');
    T.eq(App.Stages.edited(project(), 'dig_1', 'stress_initialisation', 'K0'),
         project().stages, 'a later stage got a stress initialisation');
  });

  test('trying flow and going back to mechanical keeps the self weight', function () {
    var p = project();
    p.stages = App.Stages.edited(p, 'initial', 'calculation', 'flow');
    var back = App.Stages.edited(p, 'initial', 'calculation', 'mechanical');
    T.eq(back.map(function (stage) { return stage.stress_initialisation; }),
         back.map(function (stage) {
           return stage.id === 'initial' ? 'gravity' : 'none';
         }));
  });

  test('a later stage with a stress initialisation can go back to none', function () {
    var p = project();
    p.stages[1].stress_initialisation = 'K0';
    var list = App.Stages.edited(p, p.stages[1].id, 'stress_initialisation', 'none');
    T.eq(list[1].stress_initialisation, 'none');
  });

  test('a project with no stages gets the initial stage first', function () {
    var list = App.Stages.added({ stageable_parts: [], stages: [] });
    T.eq(list.length, 1);
    T.eq([list[0].id, list[0].name, list[0].parent, list[0].stress_initialisation],
         ['initial', 'Initial stage', null, 'gravity']);
  });

  test('the initial stage is neither deleted nor preceded', function () {
    T.eq(App.Stages.removed(project(), 'initial'), project().stages);
    T.eq(App.Stages.inserted(project(), 'initial'), project().stages);
    T.ok(App.Stages.isInitial(project(), 'initial'));
    T.ok(!App.Stages.isInitial(project(), 'dig_1'));
  });

  test('add gives the new stage an id nothing else has', function () {
    var p = project();
    var list = App.Stages.added(p);
    var ids = list.map(function (ph) { return ph.id; });
    T.eq(ids.length, new Set(ids).size, 'duplicate stage id: ' + ids.join(', '));
  });

  test('add on an empty project makes a root', function () {
    var p = project();
    p.stages = [];
    var list = App.Stages.added(p);
    T.eq(list.length, 1);
    T.eq(list[0].parent, null);
  });

  /* Insert is the button that puts a stage *between* the selected one and its
     parent, which means re-parenting the selected one onto the newcomer. Getting that
     wrong makes a branch, which the server then refuses. */
  test('insert splices a stage in above the selected one', function () {
    var p = project();
    var was = p.stages.map(function (ph) { return ph.id; });
    var list = App.Stages.inserted(p, 'dig_1');

    var fresh = list.filter(function (ph) { return was.indexOf(ph.id) < 0; });
    T.eq(fresh.length, 1, 'insert did not add exactly one stage');

    var byId = {};
    list.forEach(function (ph) { byId[ph.id] = ph; });
    T.eq(fresh[0].parent, 'build_wall', 'the new stage did not take dig_1s parent');
    T.eq(byId['dig_1'].parent, fresh[0].id, 'dig_1 was not re-parented onto it');
  });

  test('inserting never leaves a branch behind', function () {
    var p = project();
    p.stages = App.Stages.inserted(p, 'prop');
    T.eq(App.Stages.branchProblem(p), null);
    T.eq(App.Stages.order(p).length, 8);
  });

  test('delete removes the stage and heals the chain', function () {
    var p = project();
    var list = App.Stages.removed(p, 'prop');
    T.eq(list.length, p.stages.length - 1);
    var byId = {};
    list.forEach(function (ph) { byId[ph.id] = ph; });
    T.ok(!byId['prop'], 'prop survived the delete');
    /* Its child has to adopt its parent, or the chain is cut in two and every stage
       after it becomes unreachable. */
    T.eq(byId['dig_2'].parent, 'dig_1');
    p.stages = list;
    T.eq(App.Stages.branchProblem(p), null);
    T.eq(App.Stages.order(p).length, 6);
  });

  test('the only stage is the initial stage, and is not deleted either', function () {
    var p = project();
    p.stages = [{ id: 'only', name: 'Only', parent: null }];
    T.eq(App.Stages.removed(p, 'only'), p.stages);
  });

  /* What a copy is *for* is repeating a dig: same solver settings, same shape, new
     parts. Copying the instructions too would switch the same bodies off twice, which
     Kratos tolerates and a reader does not. */
  test('copy repeats the settings but not the instructions', function () {
    var p = project();
    var was = p.stages.map(function (ph) { return ph.id; });
    var list = App.Stages.copied(p, 'build_wall');
    var made = list.filter(function (ph) { return was.indexOf(ph.id) < 0; })[0];
    T.ok(made, 'copy added no stage');
    T.eq(made.calculation, 'mechanical');
    T.eq(made.stress_initialisation, 'none');
    T.eq(made.reset_displacements, true, 'the solver settings were not carried over');
    T.eq(made.activate, []);
    T.eq(made.deactivate, []);
    T.ok(made.id !== 'build_wall');
  });

  test('a copy is spliced in after its original, not appended', function () {
    var p = project();
    var was = p.stages.map(function (ph) { return ph.id; });
    var list = App.Stages.copied(p, 'build_wall');
    var byId = {};
    list.forEach(function (ph) { byId[ph.id] = ph; });
    var made = list.filter(function (ph) { return was.indexOf(ph.id) < 0; })[0];
    T.eq(made.parent, 'build_wall');
    T.eq(byId['dig_1'].parent, made.id, 'dig_1 was not re-parented onto the copy');
    p.stages = list;
    T.eq(App.Stages.branchProblem(p), null);
  });

  /* ── Toggling a part in a stage (the viewport's edit) ────────────────── */

  test('toggling an active part deactivates it in that stage', function () {
    var p = project();
    var list = App.Stages.toggled(p, 'prop', 'soil_L2__pit');
    var stage = list.filter(function (ph) { return ph.id === 'prop'; })[0];
    T.ok(stage.deactivate.indexOf('soil_L2__pit') >= 0);
    T.ok(stage.activate.indexOf('soil_L2__pit') < 0, 'the part is in both lists');
  });

  test('toggling an inactive part activates it', function () {
    var p = project();
    // Off since `initial`, and untouched since -- so at `prop` it is genuinely off.
    T.ok(App.Stages.activeParts(p, 'prop').indexOf('soil_L1__lift2') < 0,
         'the fixture no longer has this part switched off at prop');

    var list = App.Stages.toggled(p, 'prop', 'soil_L1__lift2');
    var stage = list.filter(function (ph) { return ph.id === 'prop'; })[0];
    T.ok(stage.activate.indexOf('soil_L1__lift2') >= 0);
    T.ok(stage.deactivate.indexOf('soil_L1__lift2') < 0);
  });

  test('toggling twice returns the stage to where it started', function () {
    var p = project();
    var before = JSON.stringify(p.stages.filter(function (ph) {
      return ph.id === 'prop';
    })[0]);
    p.stages = App.Stages.toggled(p, 'prop', 'soil_L2__pit');
    p.stages = App.Stages.toggled(p, 'prop', 'soil_L2__pit');
    var after = JSON.stringify(p.stages.filter(function (ph) {
      return ph.id === 'prop';
    })[0]);
    T.eq(after, before, 'a part toggled twice left an instruction behind');
  });

  test('toggling never puts a part in both lists of one stage', function () {
    /* `Stage._one_instruction_per_part` refuses that outright, so a toggle that
       produced it would be rejected by the server with the edit already on screen. */
    var p = project();
    ['soil_L2__pit', 'pile', 'tie', 'soil_L1__lift3'].forEach(function (key) {
      p.stages = App.Stages.toggled(p, 'dig_2', key);
      var stage = p.stages.filter(function (ph) { return ph.id === 'dig_2'; })[0];
      T.eq((stage.activate || []).filter(function (k) {
        return (stage.deactivate || []).indexOf(k) >= 0;
      }), [], 'both lists name ' + key);
    });
  });

  /* ── Inherited vs owned, which is what the viewport greys differently ── */

  test('a part switched off by an ancestor is inherited, not owned', function () {
    var p = project();
    /* `soil_L1__lift3` is switched off in `initial` and never mentioned again. */
    T.eq(App.Stages.ownership(p, 'prop', 'soil_L1__lift3'), 'inherited');
    T.eq(App.Stages.ownership(p, 'initial', 'soil_L1__lift3'), 'own');
  });

  test('a part nothing has touched is neither', function () {
    T.eq(App.Stages.ownership(project(), 'prop', 'soil_L3'), null);
  });

  test('a part re-activated in this stage is owned by it', function () {
    T.eq(App.Stages.ownership(project(), 'dig_2', 'soil_L1__outside'), 'own');
  });

  /* ── What the viewport hides ─────────────────────────────────────────── */

  test('outside staged mode a stage hides nothing', function () {
    /* Soil mode is for building the model, not for looking at one moment of it.
       Hiding the excavated lifts there would make a body the user is trying to draw
       against disappear for a reason nothing on screen explains. */
    ['soil', 'structures', 'mesh', 'flow'].forEach(function (mode) {
      T.eq(App.Stages.hiddenKeys(project(), 'dig_2', mode), []);
    });
  });

  test('in staged mode the parts a stage switched off are hidden', function () {
    var hidden = App.Stages.hiddenKeys(project(), 'prop', 'staged');
    T.ok(hidden.indexOf('soil_L1__lift2') >= 0, 'an inactive lift is still drawn');
    T.ok(hidden.indexOf('soil_L2__pit') < 0, 'an active body was hidden');
  });

  test('the hidden set is exactly the complement of the active one', function () {
    var p = project();
    Object.keys(FIXTURE.active_parts).forEach(function (id) {
      var active = App.Stages.activeParts(p, id);
      var hidden = App.Stages.hiddenKeys(p, id, 'staged');
      T.eq(active.concat(hidden).sort(),
           App.Stages.stageableKeys(p).slice().sort(),
           'stage ' + id + ' neither shows nor hides every part');
      T.eq(active.filter(function (k) { return hidden.indexOf(k) >= 0; }), [],
           'stage ' + id + ' both shows and hides a part');
    });
  });

  test('a project with no stages hides nothing, in any mode', function () {
    /* The compatibility case: an unstaged project is one model, all of it, and
       staged mode must not start hiding parts of it. */
    var p = project();
    p.stages = [];
    T.eq(App.Stages.hiddenKeys(p, null, 'staged'), []);
  });

  /* ── The Model explorer's checkbox, in Staged construction mode ─────────
     Ticked means "in the model in the selected stage". Each stage is free to switch
     any part on or off: a part an earlier stage took out is not stuck out, because the
     checkbox is there in every stage to put it back. And a switch is per stage: the
     stages are stored as diffs, but switching a part in one stage gives the stage
     after it whatever instruction keeps it as it was, so no other stage changes. */

  function stageOf(list, id) {
    return list.filter(function (ph) { return ph.id === id; })[0];
  }

  function activeAt(p, id, key) {
    return App.Stages.activeParts(p, id).indexOf(key) >= 0;
  }

  test('setActive switches a part off in the selected stage', function () {
    var p = project();
    p.stages = App.Stages.setActive(p, 'prop', ['soil_L2__pit'], false);
    T.ok(!activeAt(p, 'prop', 'soil_L2__pit'));
  });

  test('a part switched off earlier can be switched back on in a later stage', function () {
    var p = project();
    T.ok(!activeAt(p, 'prop', 'soil_L1__lift2'), 'the fixture has it on at prop');
    p.stages = App.Stages.setActive(p, 'prop', ['soil_L1__lift2'], true);
    T.ok(activeAt(p, 'prop', 'soil_L1__lift2'));
    // ...and only from there: the stages before it are untouched.
    var chain = App.Stages.chainTo(p, 'prop').map(function (ph) { return ph.id; });
    chain.slice(0, -1).forEach(function (id) {
      T.eq(activeAt(p, id, 'soil_L1__lift2'), activeAt(project(), id, 'soil_L1__lift2'),
           id + ' changed');
    });
  });

  test('switching a part in one stage changes no stage before it', function () {
    var before = project();
    var p = project();
    p.stages = App.Stages.setActive(p, 'dig_2', ['soil_L2__pit'], false);
    App.Stages.chainTo(p, 'dig_2').slice(0, -1).forEach(function (ph) {
      T.eq(JSON.stringify(stageOf(p.stages, ph.id)),
           JSON.stringify(stageOf(before.stages, ph.id)), ph.id + ' was edited');
    });
  });

  test('setting a part to the state it already has adds no instruction', function () {
    var p = project();
    var before = JSON.stringify(stageOf(p.stages, 'prop'));
    p.stages = App.Stages.setActive(p, 'prop', ['soil_L2__pit'], true);
    T.eq(JSON.stringify(stageOf(p.stages, 'prop')), before);
  });

  test('switching back what this stage changed drops its instruction', function () {
    var p = project();
    var before = JSON.stringify(stageOf(p.stages, 'prop'));
    p.stages = App.Stages.setActive(p, 'prop', ['soil_L2__pit'], false);
    p.stages = App.Stages.setActive(p, 'prop', ['soil_L2__pit'], true);
    T.eq(JSON.stringify(stageOf(p.stages, 'prop')), before);
  });

  test('a group row sets every part under it at once', function () {
    var p = project();
    var keys = ['soil_L2__pit', 'soil_L1__lift2'];
    p.stages = App.Stages.setActive(p, 'prop', keys, true);
    keys.forEach(function (key) { T.ok(activeAt(p, 'prop', key), key); });
    p.stages = App.Stages.setActive(p, 'prop', keys, false);
    keys.forEach(function (key) { T.ok(!activeAt(p, 'prop', key), key); });
  });

  test('switching a part in one stage leaves the stages after it as they were', function () {
    var before = project();
    var p = project();
    var ids = p.stages.map(function (ph) { return ph.id; });
    ['soil_L2__pit', 'pile', 'tie', 'soil_L1__lift2'].forEach(function (key) {
      [true, false].forEach(function (wanted) {
        p = project();
        p.stages = App.Stages.setActive(p, 'build_wall', [key], wanted);
        T.eq(activeAt(p, 'build_wall', key), wanted, key + ' in build_wall');
        ids.filter(function (id) { return id !== 'build_wall'; }).forEach(function (id) {
          T.eq(activeAt(p, id, key), activeAt(before, id, key),
               key + ' changed in ' + id + ' when build_wall was switched');
        });
      });
    });
  });

  test('switching a part off in the first stage does not switch it off in the second',
       function () {
    var p = { stageable_parts: ['soil_1', 'soil_2'], stages: [
      { id: 's1', name: 'Stage 1', parent: null, activate: [], deactivate: [] },
      { id: 's2', name: 'Stage 2', parent: 's1', activate: [], deactivate: [] }
    ] };
    p.stages = App.Stages.setActive(p, 's1', ['soil_1'], false);
    T.eq(App.Stages.activeParts(p, 's1'), ['soil_2']);
    T.eq(App.Stages.activeParts(p, 's2'), ['soil_1', 'soil_2']);
    T.eq(stageOf(p.stages, 's2').activate, ['soil_1'], 'stage 2 keeps it with an instruction');
    // ...and switching it back on in stage 1 leaves stage 2 with nothing to say.
    p.stages = App.Stages.setActive(p, 's1', ['soil_1'], true);
    T.eq(stageOf(p.stages, 's1').deactivate, []);
    T.eq(stageOf(p.stages, 's2').activate, []);
  });

  test('setActive never puts a part in both lists of one stage', function () {
    var p = project();
    ['soil_L2__pit', 'pile', 'tie', 'soil_L1__lift3'].forEach(function (key) {
      p.stages = App.Stages.setActive(p, 'dig_2', [key], false);
      p.stages = App.Stages.setActive(p, 'dig_2', [key], true);
      var stage = stageOf(p.stages, 'dig_2');
      T.eq((stage.activate || []).filter(function (k) {
        return (stage.deactivate || []).indexOf(k) >= 0;
      }), [], 'both lists name ' + key);
    });
  });

  test('the checkbox state: on, off, or mixed for a group', function () {
    var p = project();
    T.eq(App.Stages.stateIn(p, 'prop', ['soil_L2__pit']), 'on');
    T.eq(App.Stages.stateIn(p, 'prop', ['soil_L1__lift2']), 'off');
    T.eq(App.Stages.stateIn(p, 'prop', ['soil_L2__pit', 'soil_L1__lift2']), 'mixed');
  });

  test('no selected stage hides nothing', function () {
    T.eq(App.Stages.hiddenKeys(project(), null, 'staged'), []);
    T.eq(App.Stages.hiddenKeys(project(), 'no_such_stage', 'staged'), []);
  });

  /* ── The Stages overview ───────────────────────────────────────────────
     The "Stages" window: every stage on one line with how long it lasts and
     the time reached at its end, and -- beside it -- what the last calculation made
     of it. The window is DOM (patches.js `stagesDialog`); what it says is here. */

  function dike() {
    function stage(id, name, parent, stresses, seconds) {
      return { id: id, name: name, parent: parent, calculation: 'mechanical',
               stress_initialisation: stresses, time_integration: 'static',
               activate: [], deactivate: [], duration: seconds, time_step: seconds };
    }
    return { stageable_parts: [], stages: [
      stage('1_Initial_stage', 'Initial stage', null, 'K0', 1),
      stage('2_Null_step', 'Null step', '1_Initial_stage', 'none', 1),
      stage('3_Slag_1', 'Slag 1', '2_Null_step', 'none', 17),
      stage('4_Slag_2', 'Slag 2', '3_Slag_1', 'none', 22),
      stage('5_Kraan', 'Kraan load', '4_Slag_2', 'none', 0.5)
    ] };
  }

  test('the overview lists every stage, numbered, in run order', function () {
    var rows = App.Stages.overview(dike(), null);
    T.eq(rows.map(function (r) { return r.number; }), [1, 2, 3, 4, 5]);
    T.eq(rows.map(function (r) { return r.id; }),
         ['1_Initial_stage', '2_Null_step', '3_Slag_1', '4_Slag_2', '5_Kraan']);
    T.eq(rows[0].kind, 'Mechanical, K0');
  });

  test('T is the time reached at the end of a stage, summed along its chain', function () {
    var rows = App.Stages.overview(dike(), null);
    T.eq(rows.map(function (r) { return r.total; }), [1, 2, 19, 41, 41.5]);
    T.eq(rows[3].duration, 22);
  });

  test('a row lists its name, duration, T, and its id', function () {
    var rows = App.Stages.overview(dike(), null);
    T.eq(rows[3].label, 'Slag 2 - 22 s, T = 41 s [4_Slag_2]');
    T.eq(rows[4].label, 'Kraan load - 0.5 s, T = 41.5 s [5_Kraan]');
    T.eq(rows[0].label, 'Initial stage - 1 s, T = 1 s [1_Initial_stage]');
  });

  test('a stage that names no duration lasts the default second', function () {
    var p = dike();
    delete p.stages[0].duration;
    var rows = App.Stages.overview(p, null);
    T.eq(rows[0].duration, 1);
    T.eq(rows[4].total, 41.5);
  });

  test('a stage made here has the duration and time step the server gives one', function () {
    var list = App.Stages.added(dike());
    var made = list[list.length - 1];
    T.eq([made.duration, made.time_step], [1, 1]);
  });

  test('a copy keeps the duration and time step of the original', function () {
    var list = App.Stages.copied(dike(), '4_Slag_2');
    var made = list.filter(function (stage) { return stage.name === 'Slag 2 (copy)'; })[0];
    T.eq([made.duration, made.time_step], [22, 22]);
  });

  test('before any calculation every stage says so', function () {
    App.Stages.overview(dike(), null).forEach(function (row) {
      T.eq(row.log, 'Not calculated');
    });
  });

  test('a finished run marks every stage OK', function () {
    App.Stages.overview(dike(), { completed: 5 }).forEach(function (row) {
      T.eq(row.log, 'OK');
      T.eq(row.state, row.number === 1 ? 'initial' : 'done');
    });
  });

  test('a failed run names the stage it stopped in, and nothing after it ran', function () {
    var rows = App.Stages.overview(dike(), { completed: 2, failed: true });
    T.eq(rows.map(function (r) { return r.log; }),
         ['OK', 'OK', 'Failed', 'Not calculated', 'Not calculated']);
    T.eq(rows[2].state, 'failed');
  });
})();
