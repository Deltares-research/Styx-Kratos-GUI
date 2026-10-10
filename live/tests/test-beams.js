/* Structure-mode piles and walls.

   A sheet pile is a dimension-native (x, y) polyline in a section. The solid model
   holds the other two kinds: a *panel*, which is a wall in plan swept between two
   levels and meshed as shells, and a *member*, which is the same profile a sheet pile
   uses standing in space. Each kind belongs to one dimension and refuses the other
   with a reason -- see plan/structure-mode-implementation-plan.md. */

(function () {
  function section(extra) {
    return Object.assign({
      dimension: 2, section_offset: 20,
      domain: { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 },
      loads: [], beams: [], beam_sections: []
    }, extra || {});
  }
  function solid() {
    return {
      dimension: 3,
      domain: { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 },
      loads: [], beams: [], beam_sections: []
    };
  }

  test('a sheet pile drafts as a dimension-native x-y polyline', function () {
    var beam = App.Beams.draftFromPoints(section(), [[12, 0, 20], [12, -14, 20]]);
    T.eq(beam.points, [[12, 0], [12, -14]]);
    T.eq(beam.active, true);
    T.eq('z' in beam || 'z0' in beam, false);
    T.eq(beam.id, 'beam_1');
  });

  test('a drafted pile keeps every vertex of a multi-segment polyline', function () {
    var beam = App.Beams.draftFromPoints(section(),
      [[12, 0, 20], [12, -7, 20], [15, -12, 20]]);
    T.eq(beam.points, [[12, 0], [12, -7], [15, -12]]);
  });

  test('a coordinate draft starts inside the domain when nothing is picked', function () {
    var beam = App.Beams.draft(section());
    var d = section().domain;
    T.ok(beam.points.length === 2);
    T.ok(beam.points.every(function (p) {
      return p[0] >= d.x0 && p[0] <= d.x1 && p[1] >= d.y_bottom && p[1] <= d.y_top;
    }), 'the default pile has to be inside the model');
  });

  test('each kind of structure is available in the dimension it belongs to', function () {
    T.eq(App.Beams.available(section(), 'beam'), true);
    T.eq(App.Beams.available(section(), 'panel'), false);
    T.eq(App.Beams.available(solid(), 'panel'), true);
    T.eq(App.Beams.available(solid(), 'member'), true);
    T.eq(App.Beams.available(solid(), 'beam'), false);
    T.eq(App.Beams.kindsFor(section()), ['beam']);
    T.eq(App.Beams.kindsFor(solid()), ['panel', 'member']);
  });

  test('a sheet pile in 3D is refused rather than silently reinterpreted', function () {
    var message = '';
    try { App.Beams.draft(solid(), 'beam'); } catch (e) { message = e.message; }
    T.ok(/wall/i.test(message), 'the message says what to make instead: ' + message);
  });

  test('a wall in a 2D section is refused the same way', function () {
    var message = '';
    try { App.Beams.draft(section(), 'panel'); } catch (e) { message = e.message; }
    T.ok(/sheet pile|3D/i.test(message), message);
  });

  /* ── The 3D kinds ───────────────────────────────────────────────── */

  test('a wall drafts as a plan footprint swept between two levels', function () {
    var panel = App.Beams.draft(solid(), 'panel');
    var d = solid().domain;
    T.eq(panel.kind, 'panel');
    T.eq(panel.id, 'panel_1');
    T.ok(panel.footprint.length === 2);
    T.ok(panel.footprint.every(function (p) {
      return p.length === 2 && p[0] >= d.x0 && p[0] <= d.x1 && p[1] >= d.z0 && p[1] <= d.z1;
    }), 'the footprint is (x, y) inside the site');
    T.ok(panel.y_top > panel.y_toe, 'a wall hangs down from its top');
    T.eq('points' in panel, false, 'a wall has no in-section polyline');
  });

  test('a member drafts as a polyline in space', function () {
    var member = App.Beams.draft(solid(), 'member');
    T.eq(member.kind, 'member');
    T.eq(member.id, 'member_1');
    T.ok(member.points.every(function (p) { return p.length === 3; }));
    T.ok(member.points[0][1] > member.points[1][1], 'it stands downward');
  });

  test('a wall brings a section with a thickness rather than an area', function () {
    var project = solid();
    var panel = App.Beams.draft(project, 'panel');
    var sections = App.Beams.sectionsFor(project, panel);
    T.eq(sections.length, 1);
    T.ok(sections[0].variables.THICKNESS > 0);
    T.eq('CROSS_AREA' in sections[0].variables, false);
    T.eq('spacing' in sections[0], false);
    T.eq(App.Beams.validateSection(sections[0]), null);
  });

  test('a wall is validated on its own terms', function () {
    var panel = App.Beams.draft(solid(), 'panel');
    T.eq(App.Beams.validate(panel), null);
    T.ok(App.Beams.validate(Object.assign({}, panel, { y_toe: panel.y_top })),
         'a wall of no height is refused');
    T.ok(App.Beams.validate(Object.assign({}, panel, { footprint: [[1, 1]] })),
         'a wall needs a run to sweep');
  });

  test('a member is validated as a polyline in three dimensions', function () {
    var member = App.Beams.draft(solid(), 'member');
    T.eq(App.Beams.validate(member), null);
    T.ok(App.Beams.validate(Object.assign({}, member, { points: [[1, 2], [3, 4]] })),
         'a 2D polyline is not a member');
  });

  test('a structure drawn outside the site is refused', function () {
    var failed = false;
    try { App.Beams.draftPanel(solid(), [[999, 4], [999, 20]]); } catch (e) { failed = true; }
    T.ok(failed);
    failed = false;
    try {
      App.Beams.draftMember(solid(), [[5, 5, 0], [5, 5, -999]]);
    } catch (e) { failed = true; }
    T.ok(failed);
  });

  test('a pile draft brings a default section when the project has none', function () {
    var project = section();
    var sections = App.Beams.sectionsFor(project, App.Beams.draft(project));
    T.eq(sections.length, 1);
    var v = sections[0].variables;
    T.ok(v.YOUNG_MODULUS > 0 && v.CROSS_AREA > 0 && v.I33 > 0);
    T.eq(sections[0].constitutive_law, 'TimoshenkoBeamElasticConstitutiveLaw');
    T.eq(sections[0].spacing, 1);
  });

  test('a second pile reuses the section already in the project', function () {
    var project = section({
      beam_sections: [{ id: 'az26', name: 'AZ 26-700', spacing: 1,
                        constitutive_law: 'TimoshenkoBeamElasticConstitutiveLaw', tables: {},
                         variables: { YOUNG_MODULUS: 2.1e11, POISSON_RATIO: 0.3,
                                      CROSS_AREA: 0.0198, I33: 5.52e-4, DENSITY: 7850 } }]
    });
    var beam = App.Beams.draft(project);
    T.eq(beam.section, 'az26');
    T.eq(App.Beams.sectionsFor(project, beam).length, 1);
  });

  test('ids do not collide with the piles already in the project', function () {
    var project = section({
      beams: [{ id: 'beam_1', name: 'Sheet pile 1', section: 'az26',
                points: [[12, 0], [12, -14]], active: true }],
      beam_sections: [{ id: 'az26', name: 'AZ 26-700', spacing: 1,
                        constitutive_law: 'TimoshenkoBeamElasticConstitutiveLaw', tables: {},
                         variables: { YOUNG_MODULUS: 2.1e11, POISSON_RATIO: 0.3,
                                      CROSS_AREA: 0.0198, I33: 5.52e-4, DENSITY: 7850 } }]
    });
    T.eq(App.Beams.draft(project).id, 'beam_2');
  });

  test('validation refuses a polyline that cannot be meshed', function () {
    var ok = { id: 'beam_1', name: 'Sheet pile 1', section: 'az26',
               points: [[12, 0], [12, -14]], active: true };
    T.eq(App.Beams.validate(ok), null);
    T.ok(App.Beams.validate(Object.assign({}, ok, { name: '  ' })));
    T.ok(App.Beams.validate(Object.assign({}, ok, { points: [[12, 0]] })));
    T.ok(App.Beams.validate(Object.assign({}, ok, { points: [[12, 0], [12, 0]] })));
    T.ok(App.Beams.validate(Object.assign({}, ok, { points: [[12, 0], [NaN, -1]] })));
  });

  test('section validation refuses unusable structural properties', function () {
    var steel = { YOUNG_MODULUS: 2.1e11, POISSON_RATIO: 0.3, CROSS_AREA: 0.0198,
                  I33: 5.52e-4, DENSITY: 7850 };
    var ok = { id: 'az26', name: 'AZ 26-700', spacing: 1,
               constitutive_law: 'TimoshenkoBeamElasticConstitutiveLaw', variables: steel };
    function with_(variables) {
      return Object.assign({}, ok, { variables: Object.assign({}, steel, variables) });
    }
    T.eq(App.Beams.validateSection(ok), null);
    T.ok(App.Beams.validateSection(with_({ YOUNG_MODULUS: 0 })));
    T.ok(App.Beams.validateSection(with_({ CROSS_AREA: -1 })));
    T.ok(App.Beams.validateSection(with_({ I33: 0 })));
    T.ok(App.Beams.validateSection(with_({ POISSON_RATIO: 0.5 })));
    T.ok(App.Beams.validateSection(Object.assign({}, ok, { spacing: 0 })));
    T.ok(App.Beams.validateSection(Object.assign({}, ok, { name: '' })));
  });

  test('saving a pile writes both collections in one structures patch', function () {
    var sent = null;
    var saved = { Api: App.Api, PROJECT: App.PROJECT, BEAMS: App.BEAMS,
                  Model: App.Model, Viewport: App.Viewport, Command: App.Command,
                  Explorer: App.Explorer, selectObject: App.selectObject };
    App.PROJECT = section();
    App.BEAMS = [];
    App.Api = { patch: function (path, body) {
      sent = { path: path, body: body };
      return Promise.resolve({ project: section() });
    } };
    App.Model = { apply: function () {}, load: function () { return Promise.resolve(); } };
    App.Viewport = { refresh: function () { return Promise.resolve(); } };
    App.Command = { ok: function () {}, err: function () {}, note: function () {} };
    App.Explorer = null;
    App.selectObject = null;

    var beam = App.Beams.draft(App.PROJECT);
    return App.Beams.save(beam, App.Beams.sectionsFor(App.PROJECT, beam))
      .then(function () {
        T.eq(sent.path, '/api/project/structures');
        T.eq(sent.body.beams.length, 1);
        T.eq(sent.body.beam_sections.length, 1);
        T.ok('loads' in sent.body, 'the required loads collection travels with it');
      })
      .then(function () { Object.assign(App, saved); },
            function (e) { Object.assign(App, saved); throw e; });
  });

  test('deleting a pile leaves the sections and loads alone', function () {
    var sent = null;
    var saved = { Api: App.Api, PROJECT: App.PROJECT, BEAMS: App.BEAMS,
                  Model: App.Model, Viewport: App.Viewport, Command: App.Command,
                  Explorer: App.Explorer, state: App.state };
    var project = section({
      beams: [{ id: 'beam_1', name: 'Sheet pile 1', section: 'az26',
                points: [[12, 0], [12, -14]], active: true }],
      beam_sections: [{ id: 'az26', name: 'AZ 26-700', spacing: 1,
                        constitutive_law: 'TimoshenkoBeamElasticConstitutiveLaw', tables: {},
                         variables: { YOUNG_MODULUS: 2.1e11, POISSON_RATIO: 0.3,
                                      CROSS_AREA: 0.0198, I33: 5.52e-4, DENSITY: 7850 } }]
    });
    App.PROJECT = project;
    App.BEAMS = project.beams.slice();
    App.Api = { patch: function (path, body) {
      sent = body;
      return Promise.resolve({ project: section() });
    } };
    App.Model = { apply: function () {}, load: function () { return Promise.resolve(); } };
    App.Viewport = { refresh: function () { return Promise.resolve(); } };
    App.Command = { ok: function () {}, err: function () {}, note: function () {} };
    App.Explorer = null;
    App.state = { selection: null };

    return App.Beams.remove('beam_1')
      .then(function (done) {
        T.eq(done, true);
        T.eq(sent.beams, []);
        T.eq(sent.beam_sections.length, 1, 'a reusable profile outlives the pile using it');
      })
      .then(function () { Object.assign(App, saved); },
            function (e) { Object.assign(App, saved); throw e; });
  });
})();
