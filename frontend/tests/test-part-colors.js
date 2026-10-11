/* ══════════════════════════════════════════════════════════════════
   test-part-colors.js — which parts of the mesh are drawn in a colour of their own.

   `App.PartColors` is the bookkeeping behind the Model explorer's colour toggle and the
   `colour` command: which part gets which colour, which parts are switched on, what a
   group row stands for, and what a typed name means. None of it touches the DOM or
   three.js, which is why it is a module of its own and why it runs headless.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var P = App.PartColors;

  /* A staged model's tree, cut down to its shapes: a soil body row, a group row whose children
     are parts, and a row bound to nothing that has a meshable part under it. */
  function tree() {
    return [
      { label: 'Soil', children: [
        { label: 'Top  ·  Sand', obj: 'soil_L_top' },
        { label: 'Lift 1  ·  Sand', obj: 'soil_L_top__lift1' }
      ] },
      { label: 'Sheet piles', obj: 'group:sheetpiles', children: [
        { label: 'Sheet pile', obj: 'sheetpile' }
      ] },
      { label: 'Anchors', obj: 'group:anchors', children: [
        { label: 'Strut', obj: 'strut' }
      ] },
      { label: 'Interfaces', obj: 'group:interfaces', children: [
        { label: 'Wall contact', obj: 'wall_contact' }
      ] },
      { label: 'Loads', obj: 'group:loads', children: [
        { label: 'Load', obj: 'surcharge' }
      ] },
      { label: 'Water levels', obj: 'group:water', children: [
        { label: 'Global water level  ·  -1.50 m', obj: 'water' }
      ] }
    ];
  }

  /* As the server sends them: an interface is one key per face it unglues. */
  var MESHED = ['soil_L_top', 'soil_L_top__lift1', 'sheetpile', 'strut',
                'wall_contact:L', 'wall_contact:R', 'surcharge'];

  /* ── Colours ─────────────────────────────────────────────────────────── */

  T.test('every part gets a colour, and no two of the first twelve share one', function () {
    var keys = [];
    for (var i = 0; i < 12; i++) keys.push('part' + i);
    var colours = P.colors(keys);
    var seen = {};
    keys.forEach(function (key) {
      T.ok(/^#[0-9a-f]{6}$/i.test(colours[key]), key + ' has ' + colours[key]);
      T.ok(!seen[colours[key]], key + ' repeats ' + colours[key]);
      seen[colours[key]] = true;
    });
  });

  T.test('a part keeps its colour when the parts after it change', function () {
    /* Re-meshing a model with one more structure must not repaint the soil. */
    var before = P.colors(['soil_a', 'sheetpile']);
    var after = P.colors(['soil_a', 'sheetpile', 'strut']);
    T.eq(after.soil_a, before.soil_a);
    T.eq(after.sheetpile, before.sheetpile);
  });

  T.test('no part is painted the grey the mesh is drawn in', function () {
    var colours = P.colors(MESHED);
    MESHED.forEach(function (key) {
      T.ok(colours[key].toLowerCase() !== '#d9dee6', key);
    });
  });

  /* ── What a row stands for ───────────────────────────────────────────── */

  T.test('a part row stands for its own key', function () {
    T.eq(P.keysUnder(tree()[1].children[0], MESHED), ['sheetpile']);
  });

  T.test('a group row stands for every meshed part under it', function () {
    T.eq(P.keysUnder(tree()[0], MESHED), ['soil_L_top', 'soil_L_top__lift1']);
    T.eq(P.keysUnder(tree()[1], MESHED), ['sheetpile']);
  });

  T.test('a row with nothing meshed under it stands for nothing', function () {
    /* The water level is drawn as a plane, not meshed: no toggle for it. */
    T.eq(P.keysUnder(tree()[5], MESHED), []);
  });

  /* ── Switching on and off ────────────────────────────────────────────── */

  T.test('everything starts off', function () {
    var on = P.create();
    T.eq(on.stateOf(['sheetpile']), 'off');
    T.eq(on.keys(), []);
  });

  T.test('toggling a part turns it on, and again turns it off', function () {
    var on = P.create();
    T.eq(on.toggle(['sheetpile']), true);
    T.ok(on.isOn('sheetpile'));
    T.eq(on.toggle(['sheetpile']), false);
    T.ok(!on.isOn('sheetpile'));
  });

  T.test('a group with some parts on reads as mixed, and toggling it turns all on', function () {
    var on = P.create();
    on.set(['soil_L_top'], true);
    var soil = ['soil_L_top', 'soil_L_top__lift1'];
    T.eq(on.stateOf(soil), 'mixed');
    on.toggle(soil);
    T.eq(on.stateOf(soil), 'on');
    on.toggle(soil);
    T.eq(on.stateOf(soil), 'off');
  });

  T.test('a part that is no longer meshed is forgotten', function () {
    var on = P.create();
    on.set(['sheetpile', 'strut'], true);
    on.keep(['sheetpile']);
    T.eq(on.keys(), ['sheetpile']);
  });

  /* ── What is drawn ───────────────────────────────────────────────────── */

  T.test('a part is drawn when it is on, meshed and shown', function () {
    var on = P.create();
    on.set(['sheetpile', 'strut', 'soil_L_top'], true);
    var hidden = { strut: true };
    var drawn = P.drawn(MESHED, on, function (key) { return !hidden[key]; });
    T.eq(drawn, ['soil_L_top', 'sheetpile']);
  });

  /* ── Interfaces: one part, two faces ─────────────────────────────────── */

  T.test('an interface row stands for both of its faces', function () {
    T.eq(P.keysUnder(tree()[3].children[0], MESHED), ['wall_contact:L', 'wall_contact:R']);
  });

  T.test('a key that only begins like a row is not that row', function () {
    /* `wall_contact_2` is another interface, not a face of `wall_contact`. */
    T.eq(P.keysUnder({ obj: 'wall_contact' }, ['wall_contact_2']), []);
  });

  T.test('the two faces get two different colours', function () {
    var colours = P.colors(MESHED);
    T.ok(colours['wall_contact:L'] !== colours['wall_contact:R']);
  });

  T.test('a face is shown and hidden by its interface', function () {
    var on = P.create();
    on.set(['wall_contact:L', 'wall_contact:R'], true);
    var hidden = { wall_contact: true };
    T.eq(P.drawn(MESHED, on, function (key) { return !hidden[key]; }), []);
  });

  T.test('the interface by name colours both faces', function () {
    var on = P.create();
    T.ok(run('colour wall contact', on).ok);
    T.eq(on.keys(), ['wall_contact:L', 'wall_contact:R']);
  });

  T.test('a face is named by its interface and L or R', function () {
    var on = P.create();
    var answer = run('colour wall contact R', on);
    T.ok(answer.ok, answer.message);
    T.eq(on.keys(), ['wall_contact:R']);
    T.ok(/Wall contact R/.test(answer.message), answer.message);
    T.ok(run('colour wall contact r off', on).ok);
    T.eq(on.keys(), []);
  });

  T.test('the faces are listed as their own parts', function () {
    var answer = run('colour');
    T.ok(/Wall contact L/.test(answer.message) && /Wall contact R/.test(answer.message),
         answer.message);
  });

  T.test('a face is labelled by the letter after its key', function () {
    T.eq(P.sideOf('wall_contact:L'), 'L');
    T.eq(P.sideOf('wall_contact:R'), 'R');
    T.eq(P.sideOf('sheetpile'), null);
  });

  /* ── Loads ───────────────────────────────────────────────────────────── */

  T.test('a load row colours the edges it acts on', function () {
    var on = P.create();
    T.ok(run('colour load', on).ok);
    T.eq(on.keys(), ['surcharge']);
    T.eq(P.keysUnder(tree()[4], MESHED), ['surcharge']);
  });

  /* ── The `colour` command ─────────────────────────────────────────────── */

  function run(text, on) {
    return P.command(text, { tree: tree(), meshed: MESHED, on: on || P.create() });
  }

  T.test('anything that is not `colour` is not this command', function () {
    T.eq(run('mesh'), false);
    T.eq(run('colours'), false);
  });

  T.test('`color` is accepted as well as `colour`', function () {
    var on = P.create();
    T.ok(run('color sheetpile', on).ok);
    T.ok(on.isOn('sheetpile'));
  });

  T.test('a part is found by its key', function () {
    var on = P.create();
    var answer = run('colour sheetpile', on);
    T.ok(answer.ok, answer.message);
    T.ok(answer.changed);
    T.eq(on.keys(), ['sheetpile']);
  });

  T.test('a part is found by its row label, case and material ignored', function () {
    var on = P.create();
    T.ok(run('colour sheet pile', on).ok);
    T.ok(run('colour lift 1', on).ok);
    T.eq(on.keys(), ['sheetpile', 'soil_L_top__lift1'], 'in the order switched on');
  });

  T.test('a group label colours everything under it', function () {
    var on = P.create();
    T.ok(run('colour Soil', on).ok);
    T.eq(on.keys(), ['soil_L_top', 'soil_L_top__lift1']);
  });

  T.test('a unique beginning of a name is enough', function () {
    var on = P.create();
    T.ok(run('colour str', on).ok);
    T.eq(on.keys(), ['strut']);
  });

  T.test('an ambiguous beginning names the candidates and changes nothing', function () {
    var on = P.create();
    var answer = run('colour s', on);
    T.ok(!answer.ok);
    T.ok(/Sheet pile/.test(answer.message) && /Strut/.test(answer.message), answer.message);
    T.eq(on.keys(), []);
  });

  T.test('an unknown name says what can be coloured', function () {
    var answer = run('colour quay wall');
    T.ok(!answer.ok);
    T.ok(/quay wall/.test(answer.message) && /Sheet pile/.test(answer.message),
         answer.message);
  });

  T.test('a part that is not meshed cannot be coloured, and says why', function () {
    var answer = run('colour water');
    T.ok(!answer.ok);
    T.ok(/mesh/i.test(answer.message), answer.message);
  });

  T.test('`off` after a name switches that part off only', function () {
    var on = P.create();
    on.set(['sheetpile', 'strut'], true);
    T.ok(run('colour sheetpile off', on).ok);
    T.eq(on.keys(), ['strut']);
  });

  T.test('`colour all` and `colour off` switch everything', function () {
    var on = P.create();
    T.ok(run('colour all', on).ok);
    T.eq(on.keys(), MESHED);
    T.ok(run('colour off', on).ok);
    T.eq(on.keys(), []);
    run('colour all', on);
    T.ok(run('colour none', on).ok);
    T.eq(on.keys(), []);
  });

  T.test('a bare `colour` lists what is coloured and what could be', function () {
    var on = P.create();
    on.set(['strut'], true);
    var answer = run('colour', on);
    T.ok(answer.ok);
    T.ok(!answer.changed);
    T.ok(/Strut/.test(answer.message) && /Sheet pile/.test(answer.message),
         answer.message);
  });

  T.test('with no mesh there is nothing to colour, and it says to mesh first', function () {
    var answer = P.command('colour sheetpile', { tree: tree(), meshed: [], on: P.create() });
    T.ok(!answer.ok);
    T.ok(/mesh/i.test(answer.message), answer.message);
  });

})();
