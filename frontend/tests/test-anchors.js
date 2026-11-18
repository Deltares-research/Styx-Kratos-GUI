/* Structure-mode anchors: a two-node tie from a head to a tail.

   An anchor needs no structure. A head near one is snapped onto it, which makes it one
   shared node in the mesh; a head further away is a node of the soil mesh. In a
   section it may hang from a sheet pile in (x, y); in the solid model from a wall
   panel or a member, in (x, y, z), as `kind: "anchor3d"`. Same formulation, one
   dimension up. */

(function () {
  var PILE = { id: 'beam_1', name: 'Sheet pile 1', section: 'az26',
               points: [[12, 0], [12, -14]], active: true };
  var PROFILE = { id: 'az26', name: 'AZ 26-700', spacing: 1,
                  constitutive_law: 'TimoshenkoBeamElasticConstitutiveLaw', tables: {},
                         variables: { YOUNG_MODULUS: 2.1e11, POISSON_RATIO: 0.3,
                                      CROSS_AREA: 0.0198, I33: 5.52e-4, DENSITY: 7850 } };

  function section(extra) {
    return Object.assign({
      dimension: 2, section_offset: 20,
      domain: { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 },
      loads: [], beams: [PILE], beam_sections: [PROFILE],
      anchors: [], anchor_sections: []
    }, extra || {});
  }
  var WALL = { id: 'panel_1', name: 'Wall 1', kind: 'panel', section: 'w1',
               footprint: [[12, 4], [12, 20]], y_top: 0, y_toe: -14, active: true };
  var MEMBER = { id: 'member_1', name: 'King post 1', kind: 'member', section: 'az26',
                 points: [[18, 0, 10], [18, -12, 10]], active: true };

  function solid(extra) {
    return Object.assign({
      dimension: 3,
      domain: { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 },
      loads: [], beams: [WALL], beam_sections: [PROFILE],
      panel_sections: [], anchors: [], anchor_sections: []
    }, extra || {});
  }

  test('an anchor is available in any project, with or without a structure',
    function () {
      T.eq(App.Anchors.available(section()), true);
      T.eq(App.Anchors.available(solid()), true);
      T.eq(App.Anchors.available(solid({ beams: [] })), true);
      T.eq(App.Anchors.available(section({ beams: [] })), true);
      T.eq(App.Anchors.available(null), false);
    });

  /* ── Anchors in space ───────────────────────────────────────────── */

  test('a space anchor drafts from the wall it hangs on, raking back and down',
    function () {
      var anchor = App.Anchors.draft(solid());
      T.eq(anchor.kind, 'anchor3d');
      T.eq(anchor.head.length, 3);
      T.eq(anchor.head[0], 12, 'the head is on the wall');
      T.ok(anchor.tail[0] > anchor.head[0], 'the tail rakes away from the wall');
      T.ok(anchor.tail[1] < anchor.head[1], 'and downward');
      T.eq(App.Anchors.validate(anchor, solid()), null);
    });

  test('a space anchor head is snapped onto the wall it was dropped near', function () {
    var anchor = App.Anchors.draftFromPoints(solid(), [[12.4, -3, 10], [20, -9, 10]]);
    T.eq(anchor.head, [12, -3, 10], 'the head lands on the wall surface');
  });

  test('a head far from any wall stays in the soil rather than being snapped',
    function () {
      var anchor = App.Anchors.draftFromPoints(solid(), [[30, -3, 10], [35, -9, 10]]);
      T.eq(anchor.head, [30, -3, 10]);
      T.eq(App.Anchors.validate(anchor, solid()), null);
    });

  test('a space anchor may hang from a member instead', function () {
    var anchor = App.Anchors.draftFromPoints(solid({ beams: [MEMBER] }),
                                             [[18, -4, 10], [23, -9, 10]]);
    T.eq(anchor.head, [18, -4, 10]);
    T.eq(anchor.kind, 'anchor3d');
  });

  test('length and inclination are measured in whichever dimension the tie lives in',
    function () {
      var flat = { head: [0, 0], tail: [3, -4] };
      T.eq(App.Anchors.length(flat), 5);
      T.eq(Math.round(App.Anchors.inclination(flat)), 53);
      var spatial = { head: [0, 0, 0], tail: [3, 4, -5] };
      T.eq(Math.round(App.Anchors.length(spatial) * 1000) / 1000, 7.071);
      T.eq(Math.round(App.Anchors.inclination(spatial)), 45);
    });

  test('a tie of zero length is refused in space as in a section', function () {
    var anchor = App.Anchors.draft(solid());
    T.ok(App.Anchors.validate(Object.assign({}, anchor, { tail: anchor.head.slice() }),
                              solid()));
  });

  test('an anchor with no pile starts 2 m down in the middle of the soil', function () {
    var anchor = App.Anchors.draft(section({ beams: [] }));
    T.eq(anchor.head, [25, -2]);
    T.ok(anchor.tail[1] < anchor.head[1], 'and rakes down');
    T.eq(anchor.tail_end, 'free');
    T.eq(App.Anchors.validate(anchor, section({ beams: [] })), null);
  });

  test('a head on no structure must be in the soil', function () {
    var message = '';
    try {
      App.Anchors.draftFromPoints(section({ beams: [] }), [[25, 2], [30, -8]], 'fixed');
    } catch (e) { message = e.message; }
    T.ok(/head on no structure must be in the soil/.test(message), message);
  });

  test('a drafted anchor puts its head on the pile and its tail in the retained soil',
    function () {
      var anchor = App.Anchors.draft(section());
      T.eq(anchor.head[0], 12, 'the head is on the pile');
      T.ok(anchor.tail[0] > anchor.head[0], 'the tail rakes back into the soil');
      T.ok(anchor.tail[1] < anchor.head[1], 'and downward');
      T.eq(anchor.kind, 'anchor');
      T.eq(anchor.id, 'anchor_1');
    });

  test('a picked head is snapped onto the nearest pile rather than left floating',
    function () {
      var anchor = App.Anchors.draftFromPoints(section(),
        [[12.4, -3, 20], [20, -8, 20]]);
      T.eq(anchor.head, [12, -3], 'snapped 0.4 m across onto the pile');
      T.eq(anchor.tail, [20, -8]);
    });

  test('a fixed head is held where it was typed, and may be in the air', function () {
    var near = App.Anchors.draftFromPoints(section(), [[12.4, -3, 20], [20, -8, 20]],
                                           'free', 'fixed');
    T.eq(near.head, [12.4, -3], 'a fixed head is not snapped onto the pile');
    T.eq(near.head_end, 'fixed');
    var high = App.Anchors.draftFromPoints(section({ beams: [] }), [[25, 2], [30, -8]],
                                           'free', 'fixed');
    T.eq(high.head, [25, 2]);
    T.eq(App.Anchors.validate(high, section({ beams: [] })), null);
    high.head_end = 'loose';
    T.ok(/head end is free or fixed/.test(App.Anchors.validate(high, section({ beams: [] }))));
  });

  test('a drafted tail is on whole metres, 8 m back and 6 m down', function () {
    var anchor = App.Anchors.draft(section({ beams: [] }));
    T.eq(anchor.tail, [33, -8]);
  });

  test('a head too far from any pile is left where it was, not dragged', function () {

    var anchor = App.Anchors.draftFromPoints(section(), [[30, -3, 20], [40, -8, 20]]);
    T.eq(anchor.head, [30, -3], 'a head metres away from the wall is in the soil');
  });

  test('ids do not collide with the anchors already in the project', function () {
    var project = section({
      anchors: [{ id: 'anchor_1', name: 'Anchor 1', kind: 'anchor', section: 'strand',
                  head: [12, -2], tail: [20, -8], prestress: 250, active: true }],
      anchor_sections: [{ id: 'strand', name: 'tendon', spacing: 2.5, tension_limit: 900000,
                          compression_limit: null, constitutive_law: 'TrussConstitutiveLaw', tables: {},
                           variables: { YOUNG_MODULUS: 1.95e11, CROSS_AREA: 0.0006,
                                        DENSITY: 7850 } }]
    });
    T.eq(App.Anchors.draft(project).id, 'anchor_2');
    T.eq(App.Anchors.draft(project).section, 'strand', 'the tendon is reused');
  });

  test('validation refuses a tie that cannot be built', function () {
    var ok = { id: 'anchor_1', name: 'Anchor 1', kind: 'anchor', section: 'strand',
               head: [12, -2], tail: [20, -8], prestress: 250, active: true };
    T.eq(App.Anchors.validate(ok, section()), null);
    T.ok(App.Anchors.validate(Object.assign({}, ok, { name: ' ' }), section()));
    T.ok(App.Anchors.validate(Object.assign({}, ok, { tail: [12, -2] }), section()),
         'a zero-length anchor');
    T.eq(App.Anchors.validate(Object.assign({}, ok, { head: [30, -2] }), section()), null,
         'a head off the pile is a node of the soil');
    T.ok(App.Anchors.validate(Object.assign({}, ok, { head: [30, 2] }), section()),
         'a head off the pile and above the ground');
    T.ok(App.Anchors.validate(Object.assign({}, ok, { prestress: NaN }), section()));
  });

  test('tendon validation refuses unusable structural properties', function () {
    var steel = { YOUNG_MODULUS: 1.95e11, CROSS_AREA: 0.0006, DENSITY: 7850 };
    var ok = { id: 'strand', name: 'tendon', spacing: 2.5, tension_limit: 900000,
               compression_limit: null, constitutive_law: 'TrussConstitutiveLaw', variables: steel };
    function with_(variables) { return Object.assign({}, steel, variables); }
    T.eq(App.Anchors.validateSection(ok), null);
    T.eq(App.Anchors.validateSection(Object.assign({}, ok, { compression_limit: 500000 })), null);
    T.ok(App.Anchors.validateSection(Object.assign({}, ok, { variables: with_({ YOUNG_MODULUS: 0 }) })));
    T.ok(App.Anchors.validateSection(Object.assign({}, ok, { variables: with_({ CROSS_AREA: -1 }) })));
    T.ok(App.Anchors.validateSection(Object.assign({}, ok, { spacing: 0 })));
    T.ok(App.Anchors.validateSection(Object.assign({}, ok, { tension_limit: 0 })));
    T.ok(App.Anchors.validateSection(Object.assign({}, ok, { name: '' })));
  });

  test('a massless tendon is allowed, as on the server; a negative density is not', function () {
    var steel = { YOUNG_MODULUS: 1.95e11, CROSS_AREA: 0.0006, DENSITY: 0 };
    var ok = { id: 'strand', name: 'tendon', spacing: 1, tension_limit: null,
               compression_limit: null, constitutive_law: 'TrussConstitutiveLaw', variables: steel };
    T.eq(App.Anchors.validateSection(ok), null);
    T.ok(App.Anchors.validateSection(Object.assign({}, ok, {
      variables: Object.assign({}, steel, { DENSITY: -1 }) })));
    T.ok(App.Anchors.validateSection(Object.assign({}, ok, {
      variables: Object.assign({}, steel, { DENSITY: NaN }) })));
  });

  function withStubs(project, body) {
    var saved = { Api: App.Api, PROJECT: App.PROJECT, ANCHORS: App.ANCHORS,
                  ANCHOR_SECTIONS: App.ANCHOR_SECTIONS, Model: App.Model,
                  Viewport: App.Viewport, Command: App.Command,
                  Explorer: App.Explorer, state: App.state,
                  selectObject: App.selectObject };
    var sent = null;
    App.PROJECT = project;
    App.ANCHORS = (project.anchors || []).slice();
    App.ANCHOR_SECTIONS = (project.anchor_sections || []).slice();
    App.Api = { patch: function (path, payload) {
      sent = { path: path, body: payload };
      return Promise.resolve({ project: project });
    } };
    App.Model = { apply: function () {}, load: function () { return Promise.resolve(); } };
    App.Viewport = { refresh: function () { return Promise.resolve(); } };
    App.Command = { ok: function () {}, err: function () {}, note: function () {} };
    App.Explorer = null;
    App.state = { selection: null };
    App.selectObject = null;
    return Promise.resolve()
      .then(function () { return body(function () { return sent; }); })
      .then(function (v) { Object.assign(App, saved); return v; },
            function (e) { Object.assign(App, saved); throw e; });
  }

  test('saving an anchor writes it with its tendon in one structures patch', function () {
    var project = section();
    return withStubs(project, function (sent) {
      var anchor = App.Anchors.draft(project);
      return App.Anchors.save(anchor, App.Anchors.sectionsFor(project, anchor))
        .then(function () {
          T.eq(sent().path, '/api/project/structures');
          T.eq(sent().body.anchors.length, 1);
          T.eq(sent().body.anchor_sections.length, 1);
          T.ok('loads' in sent().body, 'the required loads collection travels with it');
          T.eq('beams' in sent().body, false,
               'the piles are untouched, so they are left out rather than resent');
        });
    });
  });

  test('deleting an anchor keeps the tendon library and the piles', function () {
    var project = section({
      anchors: [{ id: 'anchor_1', name: 'Anchor 1', kind: 'anchor', section: 'strand',
                  head: [12, -2], tail: [20, -8], prestress: 250, active: true }],
      anchor_sections: [{ id: 'strand', name: 'tendon', spacing: 2.5, tension_limit: 900000,
                          compression_limit: null, constitutive_law: 'TrussConstitutiveLaw', tables: {},
                           variables: { YOUNG_MODULUS: 1.95e11, CROSS_AREA: 0.0006,
                                        DENSITY: 7850 } }]
    });
    return withStubs(project, function (sent) {
      return App.Anchors.remove('anchor_1').then(function (done) {
        T.eq(done, true);
        T.eq(sent().body.anchors, []);
        T.eq(sent().body.anchor_sections.length, 1);
      });
    });
  });
})();
