/* Structure-mode interfaces.

   An interface is the zero-thickness contact between a structure and the ground: the
   band where the two slide and can open, instead of being welded together the way a
   bare sheet pile is. It follows either a pile -- the arrangement
   examples/crow_case.mdpa contains -- or its own line through the soil, and `side` says
   which of the two soils is unglued from it. Plane strain only; see the INTERFACES
   table in server/app/kratos.py. */

(function () {
  function pile(extra) {
    return Object.assign({ id: 'beam_1', name: 'Sheet pile 1', kind: 'beam',
                           section: 'az26', points: [[12, 0], [12, -14]],
                           active: true }, extra || {});
  }

  function section(extra) {
    return Object.assign({
      dimension: 2, section_plane: 'xz', section_offset: 20,
      domain: { x0: 0, x1: 50, y0: 0, y1: 40, z_top: 0, z_bottom: -25 },
      materials: [{ id: 'mat_sand', name: 'Sand' }],
      loads: [], beams: [pile()], beam_sections: [],
      interfaces: [], interface_sections: []
    }, extra || {});
  }

  function solid(extra) {
    return Object.assign(section(), { dimension: 3 }, extra || {});
  }

  var CONTACT = { id: 'interfacesection_1', name: 'Interface', material: 'mat_sand',
                  r_inter: 0.7, virtual_thickness: 0.01, normal_stiffness: null,
                  shear_stiffness: null, permeability: 'Neutral' };

  /* ── Where an interface can be made ─────────────────────────────────── */

  test('interfaces are authored in the x-z section and nowhere else', function () {
    T.eq(App.Interfaces.available(section()), true);
    T.eq(App.Interfaces.available(solid()), false);
    T.eq(App.Interfaces.available(section({ section_plane: 'xy' })), false);
    T.ok(App.Interfaces.unavailableMessage(solid()));
  });

  test('drafting in the solid model refuses with a reason', function () {
    var error = null;
    try { App.Interfaces.draft(solid()); } catch (e) { error = e; }
    T.ok(error, 'a 3D interface is not a thing this exporter can write');
  });

  /* ── Drafting ───────────────────────────────────────────────────────── */

  test('an interface drafts onto the first live sheet pile, on both sides', function () {
    var record = App.Interfaces.draft(section());
    T.eq(record.structure, 'beam_1');
    T.eq(record.points, null);
    T.eq(record.side, 'both');
    T.eq(record.active, true);
    T.eq(record.id, 'interface_1');
    T.eq(record.kind, 'interface');
  });

  test('a switched-off pile is not offered to hang an interface on', function () {
    var project = section({ beams: [pile({ active: false })] });
    T.eq(App.Interfaces.livePiles(project).length, 0);
    var record = App.Interfaces.draft(project);
    T.eq(record.structure, null, 'a free line instead of a contact against nothing');
  });

  test('with no pile at all the draft is a free line detaching one side', function () {
    var record = App.Interfaces.draft(section({ beams: [] }));
    T.eq(record.structure, null);
    T.eq(record.points.length, 2);
    T.eq(record.side, 'left', 'something has to keep the original nodes');
  });

  test('drafting onto a named pile refuses a pile that is not live', function () {
    var error = null;
    try {
      App.Interfaces.draft(section({ beams: [pile({ active: false })] }), 'beam_1');
    } catch (e) { error = e; }
    T.ok(error);
  });

  test('the default contact is bound to a soil, because r_inter reduces one', function () {
    var project = section();
    var record = App.Interfaces.draft(project);
    var library = App.Interfaces.sectionsFor(project, record);
    T.eq(library.length, 1);
    T.eq(library[0].id, record.section);
    T.eq(library[0].material, 'mat_sand');
    T.ok(library[0].r_inter > 0 && library[0].r_inter <= 1);
  });

  /* ── Validation ─────────────────────────────────────────────────────── */

  test('an interface follows a pile or its own points, never both or neither', function () {
    var project = section();
    var ok = { id: 'interface_1', name: 'Wall contact', section: 'interfacesection_1',
               structure: 'beam_1', points: null, side: 'both', active: true };
    T.eq(App.Interfaces.validate(ok, project), null);
    T.ok(App.Interfaces.validate(
      Object.assign({}, ok, { points: [[8, 0], [8, -10]] }), project));
    T.ok(App.Interfaces.validate(
      Object.assign({}, ok, { structure: null }), project));
    T.ok(App.Interfaces.validate(Object.assign({}, ok, { name: '  ' }), project));
    T.ok(App.Interfaces.validate(Object.assign({}, ok, { structure: 'beam_9' }), project));
  });

  test('a free interface has to detach one side, not both', function () {
    var project = section({ beams: [] });
    var free = { id: 'interface_1', name: 'Cut', section: 'interfacesection_1',
                 structure: null, points: [[8, 0], [8, -10]], side: 'left',
                 active: true };
    T.eq(App.Interfaces.validate(free, project), null);
    T.ok(App.Interfaces.validate(Object.assign({}, free, { side: 'both' }), project),
         'with no structure in the middle there is nothing to detach from');
    T.ok(App.Interfaces.validate(
      Object.assign({}, free, { points: [[8, 0]] }), project));
    T.ok(App.Interfaces.validate(
      Object.assign({}, free, { points: [[8, 0], [8, 0]] }), project));
    T.ok(App.Interfaces.validate(
      Object.assign({}, free, { points: [[8, 0], [NaN, -1]] }), project));
  });

  test('contact validation refuses an unusable property set', function () {
    T.eq(App.Interfaces.validateSection(CONTACT), null);
    T.ok(App.Interfaces.validateSection(Object.assign({}, CONTACT, { r_inter: 0 })));
    T.ok(App.Interfaces.validateSection(Object.assign({}, CONTACT, { r_inter: 1.2 })));
    T.ok(App.Interfaces.validateSection(
      Object.assign({}, CONTACT, { virtual_thickness: 0 })));
    T.ok(App.Interfaces.validateSection(Object.assign({}, CONTACT, { name: '' })));
    T.ok(App.Interfaces.validateSection(
      Object.assign({}, CONTACT, { normal_stiffness: -1 })));
  });

  test('a contact with no soil needs both stiffnesses given outright', function () {
    var loose = Object.assign({}, CONTACT, { material: null });
    T.ok(App.Interfaces.validateSection(loose),
         'there would be nothing to derive the stiffness from');
    T.eq(App.Interfaces.validateSection(
      Object.assign({}, loose, { normal_stiffness: 1e6, shear_stiffness: 4e5 })), null);
  });

  /* ── The line it runs along ─────────────────────────────────────────── */

  test('an interface on a pile reports the pile own polyline and length', function () {
    var project = section();
    var record = App.Interfaces.draft(project);
    T.eq(App.Interfaces.pathOf(record, project), [[12, 0], [12, -14]]);
    T.near(App.Interfaces.length(record, project), 14, 1e-9);
  });

  test('a free interface reports its own polyline and length', function () {
    var record = { structure: null, points: [[8, 0], [8, -3], [12, -3]] };
    T.eq(App.Interfaces.pathOf(record, section()), record.points);
    T.near(App.Interfaces.length(record, section()), 7, 1e-9);
  });

  /* ── Persistence ────────────────────────────────────────────────────── */

  test('saving an interface writes both collections in one structures patch', function () {
    var sent = null;
    var saved = { Api: App.Api, PROJECT: App.PROJECT, INTERFACES: App.INTERFACES,
                  Model: App.Model, Viewport: App.Viewport, Command: App.Command,
                  Explorer: App.Explorer, selectObject: App.selectObject };
    App.PROJECT = section();
    App.INTERFACES = [];
    App.Api = { patch: function (path, body) {
      sent = { path: path, body: body };
      return Promise.resolve({ project: section() });
    } };
    App.Model = { apply: function () {}, load: function () { return Promise.resolve(); } };
    App.Viewport = { refresh: function () { return Promise.resolve(); } };
    App.Command = { ok: function () {}, err: function () {}, note: function () {} };
    App.Explorer = null;
    App.selectObject = null;

    var record = App.Interfaces.draft(App.PROJECT);
    return App.Interfaces.save(record, App.Interfaces.sectionsFor(App.PROJECT, record))
      .then(function () {
        T.eq(sent.path, '/api/project/structures');
        T.eq(sent.body.interfaces.length, 1);
        T.eq(sent.body.interface_sections.length, 1);
        T.ok('loads' in sent.body, 'the required loads collection travels with it');
        T.eq('beams' in sent.body, false,
             'a collection this write does not mention is left alone by the server');
      })
      .then(function () { Object.assign(App, saved); },
            function (e) { Object.assign(App, saved); throw e; });
  });

  test('deleting an interface leaves the contact library and the loads alone', function () {
    var sent = null;
    var saved = { Api: App.Api, PROJECT: App.PROJECT, INTERFACES: App.INTERFACES,
                  INTERFACE_SECTIONS: App.INTERFACE_SECTIONS,
                  Model: App.Model, Viewport: App.Viewport, Command: App.Command,
                  Explorer: App.Explorer, state: App.state };
    var project = section({
      interfaces: [{ id: 'interface_1', name: 'Wall contact',
                     section: 'interfacesection_1', structure: 'beam_1',
                     points: null, side: 'both', active: true }],
      interface_sections: [CONTACT]
    });
    App.PROJECT = project;
    App.INTERFACES = project.interfaces.slice();
    App.INTERFACE_SECTIONS = project.interface_sections.slice();
    App.Api = { patch: function (path, body) {
      sent = body;
      return Promise.resolve({ project: section() });
    } };
    App.Model = { apply: function () {}, load: function () { return Promise.resolve(); } };
    App.Viewport = { refresh: function () { return Promise.resolve(); } };
    App.Command = { ok: function () {}, err: function () {}, note: function () {} };
    App.Explorer = null;
    App.state = { selection: null };

    return App.Interfaces.remove('interface_1')
      .then(function (done) {
        T.eq(done, true);
        T.eq(sent.interfaces, []);
        T.eq(sent.interface_sections.length, 1,
             'a reusable contact outlives the interface using it');
      })
      .then(function () { Object.assign(App, saved); },
            function (e) { Object.assign(App, saved); throw e; });
  });

  test('an invalid interface is refused before any request is made', function () {
    var saved = { Api: App.Api, PROJECT: App.PROJECT, INTERFACES: App.INTERFACES };
    var called = false;
    App.PROJECT = section();
    App.INTERFACES = [];
    App.Api = { patch: function () { called = true; return Promise.resolve({}); } };
    var bad = { id: 'interface_1', name: '', section: 'interfacesection_1',
                structure: 'beam_1', points: null, side: 'both', active: true };
    return T.rejects(function () { return App.Interfaces.save(bad, [CONTACT]); })
      .then(function () {
        T.eq(called, false);
        Object.assign(App, saved);
      }, function (e) { Object.assign(App, saved); throw e; });
  });
})();
