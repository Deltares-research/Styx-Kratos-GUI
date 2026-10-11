/* ══════════════════════════════════════════════════════════════════
   test-deck.js — `run <case.py>` for a case that is a Kratos deck already.

   The server sends such a case's mesh back with the project (core/kratos/deck.py);
   `App.Deck` decides what to do with it -- whether there is one, which parts go into
   the Model explorer, and what the command log says. Showing it, and switching to
   the Mesh tab, are patches.js's.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var D = App.Deck;

  var MESH = {
    dimension: 2, nodes: 16885,
    elements: [
      { kratos_class: 'SmallStrainUPwDiffOrderElement2D8N', kind: 'continuum', count: 4873 },
      { kratos_class: 'SmallStrainUPwDiffOrderElement2D6N', kind: 'continuum', count: 282 },
      { kratos_class: 'LinearTimoshenkoCurvedBeamElement2D3N', kind: 'beam', count: 374 }
    ],
    conditions: [{ kratos_class: 'LineLoadDiffOrderCondition2D3N', kind: 'condition', count: 11 }],
    sections: [
      { key: 'imported:soil_1_toplaag_left', part: 'soil_1_toplaag_left',
        kind: 'continuum', color: '#c9a35c' },
      { key: 'imported:sheetpile_upper', part: 'sheetpile_upper',
        kind: 'beam', color: '#5b8dbd' },
      { key: 'imported_interface', part: null, kind: 'interface', color: '#d4a017' }
    ]
  };

  T.test('a parametric model comes back without a mesh, and is meshed as before', function () {
    T.eq(D.hasMesh({ project: {}, mesh: null }), false);
    T.eq(D.hasMesh({ project: {} }), false);
    T.eq(D.hasMesh(null), false);
  });

  T.test('a deck comes back with its mesh', function () {
    T.eq(D.hasMesh({ project: {}, mesh: MESH }), true);
  });

  T.test('a mesh with nothing drawable in it is not shown as one', function () {
    T.eq(D.hasMesh({ mesh: { sections: [] } }), false);
  });

  T.test('every drawn part becomes a row of the Model explorer, in deck order', function () {
    T.eq(D.parts(MESH), [
      { key: 'imported:soil_1_toplaag_left', label: 'soil_1_toplaag_left', color: '#c9a35c' },
      { key: 'imported:sheetpile_upper', label: 'sheetpile_upper', color: '#5b8dbd' },
      { key: 'imported_interface', label: 'interface (ungrouped)', color: '#d4a017' }
    ]);
  });

  T.test('the label is the deck\'s own part name, or the kind when no part claims it', function () {
    T.eq(D.label({ part: 'Slag_1_aanbrengen_left', kind: 'continuum' }), 'Slag_1_aanbrengen_left');
    T.eq(D.label({ part: null, kind: 'beam' }), 'beam (ungrouped)');
  });

  T.test('the summary names the model, its size and where the parts are', function () {
    var text = D.summary(MESH, 'Dike section');
    T.ok(/^Dike section/.test(text), text);
    T.ok(/2D/.test(text), text);
    T.ok(/16 885 nodes/.test(text), text);
    T.ok(/5 155 continuum/.test(text), 'both soil classes are counted together: ' + text);
    T.ok(/374 beam/.test(text), text);
    T.ok(!/condition/.test(text), 'conditions are not elements: ' + text);
    T.ok(/3 parts/.test(text) && /Model explorer/.test(text), text);
  });

  /* ── Phases: the Staged construction tab shows a stage's own parts ───────────── */

  var STAGED = {
    deck: { directory: 'C:/cases/dike', parameters: 'dike.json',
            parts: ['soil', 'fill', 'crane'] },
    stageable_parts: ['soil', 'fill', 'crane'],
    phases: [
      { id: '1_Initial_stage', name: 'Initial stage', parent: null,
        activate: [], deactivate: ['fill', 'crane'] },
      { id: '3_Fill', name: 'Fill', parent: '1_Initial_stage',
        activate: ['fill'], deactivate: [] }
    ]
  };

  T.test('outside the Staged construction tab every part is drawn', function () {
    T.eq(D.activeForView(STAGED, '3_Fill', 'mesh'), null);
    T.eq(D.activeForView(STAGED, '3_Fill', 'results'), null);
  });

  T.test('on the Staged construction tab, the selected stage decides', function () {
    T.eq(D.activeForView(STAGED, '1_Initial_stage', 'staged'), ['soil']);
    T.eq(D.activeForView(STAGED, '3_Fill', 'staged'), ['fill', 'soil']);
  });

  T.test('no stage selected hides nothing, rather than everything', function () {
    T.eq(D.activeForView(STAGED, null, 'staged'), null);
    T.eq(D.activeForView(STAGED, 'gone', 'staged'), null);
  });

  T.test('a model that is not a deck is left to the viewport as before', function () {
    var parametric = { stageable_parts: ['soil'], phases: STAGED.phases };
    T.eq(D.activeForView(parametric, '3_Fill', 'staged'), null);
  });

  T.test('a part is drawn when its eye is on and its stage has it', function () {
    T.eq(D.sectionShown('soil', true, ['soil']), true);
    T.eq(D.sectionShown('fill', true, ['soil']), false, 'not built yet');
    T.eq(D.sectionShown('soil', false, ['soil']), false, 'eye off');
    T.eq(D.sectionShown('fill', undefined, null), true, 'no stage: eye alone');
  });

  T.test('a part no stage names is not drawn in any stage', function () {
    // An aggregate like `sheetpile_aggregate` repeats elements other parts own; a
    // stage never computes on it, so it would draw a wall before the wall exists.
    T.eq(D.sectionShown('sheetpile_aggregate', true, ['soil']), false);
    T.eq(D.sectionShown(null, true, ['soil']), false, 'elements no part claims');
  });

  /* ── Results: the Model explorer's eyes act on the contour ────────────────────── */

  T.test('a result part follows the eye of the deck part of the same name', function () {
    var eyes = { 'imported:soil': true, 'imported:fill': false };
    function eyeOf(key) { return eyes[key]; }
    T.eq(D.resultShown('soil', eyeOf), true);
    T.eq(D.resultShown('fill', eyeOf), false);
  });

  T.test('a result part with no row of its own is always drawn', function () {
    T.eq(D.resultShown('Other elements', function () { return undefined; }), true);
    T.eq(D.resultShown(null, function () { return false; }), true);
  });

}());
