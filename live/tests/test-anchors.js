/* Structure-mode anchors: a two-node tie from a structure to a restrained point.

   The head has to land on that structure -- that is what makes it one shared node in
   the mesh rather than a truss attached to nothing. In a section it hangs from a sheet
   pile in (x, z); in the solid model it hangs from a wall panel or a member, in
   (x, y, z), as `kind: "anchor3d"`. Same formulation, one dimension up. */

(function () {
  var PILE = { id: 'beam_1', name: 'Sheet pile 1', section: 'az26',
               points: [[12, 0], [12, -14]], active: true };
  var PROFILE = { id: 'az26', name: 'AZ 26-700', E: 2.1e8, nu: 0.3, area: 0.0198,
                  inertia: 5.52e-4, density: 7850, spacing: 1 };

  function section(extra) {
    return Object.assign({
      dimension: 2, section_plane: 'xz', section_offset: 20,
      domain: { x0: 0, x1: 50, y0: 0, y1: 40, z_top: 0, z_bottom: -25 },
      loads: [], beams: [PILE], beam_sections: [PROFILE],
      anchors: [], anchor_sections: []
    }, extra || {});
  }
  var WALL = { id: 'panel_1', name: 'Wall 1', kind: 'panel', section: 'w1',
               footprint: [[12, 4], [12, 20]], z_top: 0, z_toe: -14, active: true };
  var MEMBER = { id: 'member_1', name: 'King post 1', kind: 'member', section: 'az26',
                 points: [[18, 10, 0], [18, 10, -12]], active: true };

  function solid(extra) {
    return Object.assign({
      dimension: 3,
      domain: { x0: 0, x1: 50, y0: 0, y1: 40, z_top: 0, z_bottom: -25 },
      loads: [], beams: [WALL], beam_sections: [PROFILE],
      panel_sections: [], anchors: [], anchor_sections: []
    }, extra || {});
  }

  test('an anchor is available wherever there is a structure to hang it from',
    function () {
      T.eq(App.Anchors.available(section()), true);
      T.eq(App.Anchors.available(solid()), true, 'a wall carries an anchor in 3D');
      T.eq(App.Anchors.available(solid({ beams: [MEMBER] })), true);
      T.eq(App.Anchors.available(solid({ beams: [] })), false);
      T.eq(App.Anchors.available(section({ beams: [] })), false);
      T.eq(App.Anchors.available(section({ section_plane: 'xy' })), false);
      // Each dimension sees only its own kinds: a saved sheet pile is nothing to hang
      // a space anchor from, and a wall is nothing to hang a plane anchor from.
      T.eq(App.Anchors.available(solid({ beams: [PILE] })), false);
      T.eq(App.Anchors.available(section({ beams: [WALL] })), false);
    });

  /* ── Anchors in space ───────────────────────────────────────────── */

  test('a space anchor drafts from the wall it hangs on, raking back and down',
    function () {
      var anchor = App.Anchors.draft(solid());
      T.eq(anchor.kind, 'anchor3d');
      T.eq(anchor.head.length, 3);
      T.eq(anchor.head[0], 12, 'the head is on the wall');
      T.ok(anchor.tail[0] > anchor.head[0], 'the tail rakes away from the wall');
      T.ok(anchor.tail[2] < anchor.head[2], 'and downward');
      T.eq(App.Anchors.validate(anchor, solid()), null);
    });

  test('a space anchor head is snapped onto the wall it was dropped near', function () {
    var anchor = App.Anchors.draftFromPoints(solid(), [[12.4, 10, -3], [20, 10, -9]]);
    T.eq(anchor.head, [12, 10, -3], 'the head lands on the wall surface');
  });

  test('a head placed in mid-air is refused rather than snapped from far away',
    function () {
      var message = '';
      try {
        App.Anchors.draftFromPoints(solid(), [[30, 10, -3], [35, 10, -9]]);
      } catch (e) { message = e.message; }
      T.ok(/wall or a member/i.test(message), message);
    });

  test('a space anchor may hang from a member instead', function () {
    var anchor = App.Anchors.draftFromPoints(solid({ beams: [MEMBER] }),
                                             [[18, 10, -4], [23, 10, -9]]);
    T.eq(anchor.head, [18, 10, -4]);
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

  test('an anchor without a pile to hang from is refused with a reason', function () {
    var message = '';
    try { App.Anchors.draft(section({ beams: [] })); } catch (e) { message = e.message; }
    T.ok(/sheet pile/i.test(message), 'the message names what is missing: ' + message);
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
        [[12.4, 20, -3], [20, 20, -8]]);
      T.eq(anchor.head, [12, -3], 'snapped 0.4 m across onto the pile');
      T.eq(anchor.tail, [20, -8]);
    });

  test('a head too far from any pile is refused, not silently dragged', function () {
    var failed = false;
    try {
      App.Anchors.draftFromPoints(section(), [[30, 20, -3], [40, 20, -8]]);
    } catch (e) { failed = true; }
    T.ok(failed, 'a head metres away from the wall is a mistake, not a snap');
  });

  test('ids do not collide with the anchors already in the project', function () {
    var project = section({
      anchors: [{ id: 'anchor_1', name: 'Anchor 1', kind: 'anchor', section: 'strand',
                  head: [12, -2], tail: [20, -8], prestress: 250, active: true }],
      anchor_sections: [{ id: 'strand', name: 'tendon', E: 1.95e8, area: 0.0006,
                          density: 7850, spacing: 2.5, tension_limit: 900,
                          compression_limit: null }]
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
    T.ok(App.Anchors.validate(Object.assign({}, ok, { head: [30, -2] }), section()),
         'a head off the pile');
    T.ok(App.Anchors.validate(Object.assign({}, ok, { prestress: NaN }), section()));
  });

  test('tendon validation refuses unusable structural properties', function () {
    var ok = { id: 'strand', name: 'tendon', E: 1.95e8, area: 0.0006, density: 7850,
               spacing: 2.5, tension_limit: 900, compression_limit: null };
    T.eq(App.Anchors.validateSection(ok), null);
    T.eq(App.Anchors.validateSection(Object.assign({}, ok, { compression_limit: 500 })), null);
    T.ok(App.Anchors.validateSection(Object.assign({}, ok, { E: 0 })));
    T.ok(App.Anchors.validateSection(Object.assign({}, ok, { area: -1 })));
    T.ok(App.Anchors.validateSection(Object.assign({}, ok, { spacing: 0 })));
    T.ok(App.Anchors.validateSection(Object.assign({}, ok, { tension_limit: 0 })));
    T.ok(App.Anchors.validateSection(Object.assign({}, ok, { name: '' })));
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
      anchor_sections: [{ id: 'strand', name: 'tendon', E: 1.95e8, area: 0.0006,
                          density: 7850, spacing: 2.5, tension_limit: 900,
                          compression_limit: null }]
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
