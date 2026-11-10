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
    T.eq(row.kind, 'K0 procedure');
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
    T.eq(list[list.length - 1].calculation, 'Plastic');
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

  test('deleting the root promotes its child', function () {
    var p = project();
    var list = App.Stages.removed(p, 'initial');
    var byId = {};
    list.forEach(function (ph) { byId[ph.id] = ph; });
    T.eq(byId['null_step'].parent, null);
    p.stages = list;
    T.eq(App.Stages.order(p).length, 6);
  });

  test('deleting the only stage leaves an unstaged project', function () {
    var p = project();
    p.stages = [{ id: 'only', name: 'Only', parent: null }];
    T.eq(App.Stages.removed(p, 'only'), []);
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
    T.eq(made.calculation, 'Plastic');
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
     checkbox is there in every stage to put it back. The state is still inherited
     from the stage before -- that is how Kratos' stages run, one model carried from
     stage to stage -- so switching a part off in one stage leaves it off in the
     stages after it until one of them switches it back on. */

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
    function stage(id, name, parent, calculation, days) {
      return { id: id, name: name, parent: parent, calculation: calculation,
               activate: [], deactivate: [], time_interval: days };
    }
    return { stageable_parts: [], stages: [
      stage('1_Initial_stage', 'Initial stage', null, 'K0 procedure', 0),
      stage('2_Null_step', 'Null step', '1_Initial_stage', 'Null step', 0),
      stage('3_Slag_1', 'Slag 1', '2_Null_step', 'Plastic', 17),
      stage('4_Slag_2', 'Slag 2', '3_Slag_1', 'Plastic', 22),
      stage('5_Kraan', 'Kraan load', '4_Slag_2', 'Plastic', 0.5)
    ] };
  }

  test('the overview lists every stage, numbered, in run order', function () {
    var rows = App.Stages.overview(dike(), null);
    T.eq(rows.map(function (r) { return r.number; }), [1, 2, 3, 4, 5]);
    T.eq(rows.map(function (r) { return r.id; }),
         ['1_Initial_stage', '2_Null_step', '3_Slag_1', '4_Slag_2', '5_Kraan']);
    T.eq(rows[0].kind, 'K0 procedure');
  });

  test('T is the time reached at the end of a stage, summed along its chain', function () {
    var rows = App.Stages.overview(dike(), null);
    T.eq(rows.map(function (r) { return r.total; }), [0, 0, 17, 39, 39.5]);
    T.eq(rows[3].interval, 22);
  });

  test('a row lists its name, duration, T, and its id', function () {
    var rows = App.Stages.overview(dike(), null);
    T.eq(rows[3].label, 'Slag 2 - 22 d, T = 39 d [4_Slag_2]');
    T.eq(rows[4].label, 'Kraan load - 0.5 d, T = 39.5 d [5_Kraan]');
    T.eq(rows[0].label, 'Initial stage [1_Initial_stage]', 'no time, no times');
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
