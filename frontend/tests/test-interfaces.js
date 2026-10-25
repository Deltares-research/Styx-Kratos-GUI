/* Structure-mode interfaces.

   An interface is the zero-thickness contact between a structure and the ground: the
   band where the two slide and can open, instead of being welded together the way a
   bare sheet pile is. It follows either a pile -- the arrangement
   Kratos' reference decks contain -- or its own line through the soil, and `side` says
   which of the two soils is unglued from it. Plane strain only; see the INTERFACES
   table in core/kratos/writer.py. */

(function () {
  function pile(extra) {
    return Object.assign({ id: 'beam_1', name: 'Sheet pile 1', kind: 'beam',
                           section: 'az26', points: [[12, 0], [12, -14]],
                           active: true }, extra || {});
  }

  function section(extra) {
    return Object.assign({
      dimension: 2, section_offset: 20,
      domain: { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 },
      materials: [{ id: 'mat_sand', name: 'Sand' }],
      loads: [], beams: [pile()], beam_sections: [],
      interfaces: [], interface_sections: []
    }, extra || {});
  }

  function solid(extra) {
    return Object.assign(section(), { dimension: 3 }, extra || {});
  }

  // A Kratos property set like every other (core/model/schemas.py InterfaceSection):
  // no stiffness of its own, so the soil each stretch runs against supplies it.
  var CONTACT = { id: 'interfacesection_1', name: 'Interface', material: 'mat_sand',
                  r_inter: 0.7, virtual_thickness: 0.01, permeability: 'Neutral',
                  constitutive_law: 'GeoIncrementalLinearElasticInterfaceLaw',
                  variables: {}, tables: {} };

  /* ── Where an interface can be made ─────────────────────────────────── */

  test('interfaces are authored in the 2D section and nowhere else', function () {
    T.eq(App.Interfaces.available(section()), true);
    T.eq(App.Interfaces.available(solid()), false);
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
      Object.assign({}, CONTACT, { variables: { INTERFACE_NORMAL_STIFFNESS: -1 } })));
    T.ok(App.Interfaces.validateSection(Object.assign({}, CONTACT, { constitutive_law: '' })));
  });

  test('a contact with no Rinter of its own takes each soil’s', function () {
    /* core/model/schemas.py InterfaceSection.r_inter: None is the default rule -- each
       stretch of contact takes the Rinter of the soil it runs against. */
    T.eq(App.Interfaces.validateSection(Object.assign({}, CONTACT, { r_inter: null })), null);
  });

  test('a contact with no soil of its own derives from the soil it runs against', function () {
    /* The server's rule (InterfaceSection): no material and no stiffnesses is the
       ordinary case -- the test model's own contact is one -- not an error. It used to be refused
       here after the server had stopped refusing it, so any edit of such a contact
       in the property grid failed. */
    var loose = Object.assign({}, CONTACT, { material: null });
    T.eq(App.Interfaces.validateSection(loose), null);
    T.eq(App.Interfaces.validateSection(Object.assign({}, loose, { variables: {
      INTERFACE_NORMAL_STIFFNESS: 1e9, INTERFACE_SHEAR_STIFFNESS: 4e8 } })), null);
  });

  /* ── The line it runs along ─────────────────────────────────────────── */

  test('an interface on a pile reports the pile own polyline and length', function () {
    var project = section();
    var record = App.Interfaces.draft(project);
    T.eq(App.Interfaces.pathOf(record, project), [[12, 0], [12, -14]]);
    T.near(App.Interfaces.length(record, project), 14, 1e-9);
  });

  test('an interface on a part of a pile reports that part', function () {
    var project = section();
    var record = App.Interfaces.draft(project, 'beam_1', [[12, -9], [12.2, -3]]);
    T.eq(record.stretch, [[12, -9], [12, -3]], 'moved onto the pile');
    T.eq(App.Interfaces.pathOf(record, project), [[12, -3], [12, -9]],
         'in the pile\u2019s own order');
    T.near(App.Interfaces.length(record, project), 6, 1e-9);
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

/* The two entry points the menus and the Model explorer call: start and edit. */
(function () {
  function project(dimension) {
    return {
      dimension: dimension, section_offset: 20,
      domain: { x0: 0, x1: 50, z0: 0, z1: 40, y_top: 0, y_bottom: -25 },
      materials: [{ id: 'mat_sand', name: 'Sand' }],
      loads: [], beam_sections: [],
      beams: [{ id: 'beam_1', name: 'Sheet pile 1', kind: 'beam', section: 'az26',
                points: [[12, 0], [12, -14]], active: true }],
      interfaces: [{ id: 'interface_1', name: 'Wall contact', kind: 'interface',
                     section: 'interfacesection_1', structure: 'beam_1', points: null,
                     side: 'both', active: true }],
      interface_sections: [{ id: 'interfacesection_1', name: 'Interface',
                             material: 'mat_sand', r_inter: 0.7, virtual_thickness: 0.01,
                             permeability: 'Neutral',
                             constitutive_law: 'GeoIncrementalLinearElasticInterfaceLaw',
                             variables: {}, tables: {} }]
    };
  }

  function rig(dimension) {
    var saved = { Api: App.Api, PROJECT: App.PROJECT, INTERFACES: App.INTERFACES,
                  INTERFACE_SECTIONS: App.INTERFACE_SECTIONS, Model: App.Model,
                  Viewport: App.Viewport, Command: App.Command, Explorer: App.Explorer,
                  selectObject: App.selectObject, state: App.state };
    var ctx = { sent: [], notes: [], selected: null };
    App.PROJECT = project(dimension);
    App.INTERFACES = App.PROJECT.interfaces.slice();
    App.INTERFACE_SECTIONS = App.PROJECT.interface_sections.slice();
    App.Api = { patch: function (path, body) {
      ctx.sent.push({ path: path, body: body });
      return Promise.resolve({ project: App.PROJECT });
    } };
    App.Model = { apply: function () {}, load: function () { return Promise.resolve(); } };
    App.Viewport = { refresh: function () { return Promise.resolve(); } };
    App.Command = { ok: function () {}, err: function () {},
                    note: function (t) { ctx.notes.push(t); } };
    App.Explorer = null;
    App.state = { selection: null };
    App.selectObject = function (key) { ctx.selected = key; };
    ctx.done = function (promise) {
      return Promise.resolve(promise).then(function (v) { Object.assign(App, saved); return v; },
        function (e) { Object.assign(App, saved); throw e; });
    };
    return ctx;
  }

  /* The window, built against the real App.UI so its rows are the ones it renders. */
  function opened(ctx, open) {
    var saved = App.Dialogs;
    var spec = null, closed = false;
    App.Dialogs = { open: function (s) {
      spec = s; return { close: function () { closed = true; } };
    } };
    try { open(); } finally { App.Dialogs = saved; }
    var body = document.createElement('div');
    if (spec) spec.build(body);
    function control(label) {
      var labels = body.querySelectorAll('.mesh-setting-label');
      for (var i = 0; i < labels.length; i += 1) {
        if (labels[i].textContent === label) return labels[i].nextElementSibling;
      }
      return null;
    }
    function labels() {
      return Array.prototype.map.call(body.querySelectorAll('.mesh-setting-label'),
                                      function (node) { return node.textContent; });
    }
    function choices(label) {
      return Array.prototype.map.call(control(label).options, function (o) { return o.value; });
    }
    function set(label, value) {
      var input = control(label);
      input.value = String(value);
      input.dispatchEvent(new Event('change'));
    }
    function message() { return body.querySelector('.mesh-settings-message').textContent; }
    function save() {
      var button = spec.buttons.filter(function (b) { return b.label === 'Save'; })[0];
      return Promise.resolve(button.onClick());
    }
    return { spec: spec, body: body, control: control, labels: labels, choices: choices,
             set: set, message: message, save: save,
             closed: function () { return closed; } };
  }

  test('start: the tool opens the window and saves nothing yet', function () {
    var ctx = rig(2);
    return ctx.done(Promise.resolve().then(function () {
      var w = opened(ctx, function () { App.Interfaces.start('beam_1'); });
      T.ok(w.spec, 'the window opened');
      T.eq(w.spec.title, 'Create interface');
      T.eq(w.spec.buttons.map(function (b) { return b.label; }),
           ['Pick on model…', 'Save', 'Cancel']);
      T.eq(ctx.sent.length, 0, 'nothing is saved until Save');
      ['Name', 'Along', 'From x', 'From y', 'To x', 'To y', 'Side', 'Contact',
       'Active'].forEach(function (label) {
        T.ok(w.labels().indexOf(label) >= 0, label + ' is on the window');
      });
      T.eq(w.choices('Along'), ['', 'beam_1'], 'own coordinates, then each live pile');
      T.eq(w.control('Along').value, 'beam_1');
      T.eq([w.control('From y').value, w.control('To y').value], ['0', '-14'],
           'From and To start at the pile\u2019s two ends');
      T.eq(w.choices('Side'), ['both', 'left', 'right']);
      T.eq(w.choices('Contact'), ['interfacesection_1', '']);
    }));
  });

  test('a plain Save holds the whole pile', function () {
    var ctx = rig(2);
    return ctx.done(Promise.resolve().then(function () {
      App.PROJECT.interfaces[0].side = 'left';
      var w = opened(ctx, function () { App.Interfaces.start('beam_1'); });
      w.set('Side', 'right');
      return w.save().then(function () {
        T.eq(ctx.sent.length, 1);
        var added = ctx.sent[0].body.interfaces[1];
        T.eq(added.structure, 'beam_1');
        T.eq(added.stretch, null, 'the whole pile is saved as no stretch');
        T.eq(added.side, 'right');
        T.ok(w.closed(), 'and the window closes');
        T.eq(ctx.selected, added.id, 'and the new interface is selected');
      });
    }));
  });

  test('From and To are moved onto the pile, and a point far from it is refused', function () {
    var ctx = rig(2);
    return ctx.done(Promise.resolve().then(function () {
      App.PROJECT.interfaces[0].side = 'left';
      var w = opened(ctx, function () { App.Interfaces.start('beam_1'); });
      w.set('Side', 'right');
      w.set('From x', 12.3); w.set('From y', -2);
      w.set('To x', 12); w.set('To y', -6);
      return w.save().then(function () {
        T.eq(ctx.sent[0].body.interfaces[1].stretch, [[12, -2], [12, -6]]);
        T.eq(w.control('From x').value, '12', 'the window shows the moved point');
      }).then(function () {
        var far = opened(ctx, function () { App.Interfaces.start('beam_1'); });
        far.set('Side', 'right');
        far.set('To x', 13.2);
        return far.save().then(function () {
          T.eq(far.message(), 'To is 1.2 m from Sheet pile 1; From and To are points on the pile.');
          T.eq(ctx.sent.length, 1, 'nothing more was sent');
        });
      });
    }));
  });

  test('two interfaces on one face over the same length are refused, as by the project', function () {
    var ctx = rig(2);
    return ctx.done(Promise.resolve().then(function () {
      var w = opened(ctx, function () { App.Interfaces.start('beam_1'); });
      w.set('Side', 'left');
      w.set('From y', -2); w.set('To y', -6);
      return w.save().then(function () {
        T.eq(w.message(), 'Interface 2 and Wall contact both hold the left face of '
             + 'Sheet pile 1 between y -2 and y -6');
        T.eq(ctx.sent.length, 0);
      });
    }));
  });

  test('own coordinates along a pile are refused with what to do instead', function () {
    var ctx = rig(2);
    return ctx.done(Promise.resolve().then(function () {
      var w = opened(ctx, function () { App.Interfaces.start('beam_1'); });
      w.set('Along', '');
      T.eq(w.choices('Side'), ['left', 'right'], 'no both sides without a pile');
      T.ok(w.labels().indexOf('x2') >= 0 && w.labels().indexOf('From x') < 0);
      w.set('x1', 12); w.set('y1', -1); w.set('x2', 12); w.set('y2', -5);
      return w.save().then(function () {
        T.eq(w.message(), 'Interface 2 runs along Sheet pile 1. Put it on Sheet pile 1 '
             + 'instead (Along in the window, --structure on the command line) and set '
             + 'From and To');
        T.eq(ctx.sent.length, 0);
      });
    }));
  });

  test('own coordinates take more points, and save as a free line', function () {
    var ctx = rig(2);
    return ctx.done(Promise.resolve().then(function () {
      var w = opened(ctx, function () { App.Interfaces.start('beam_1'); });
      w.set('Along', '');
      var add = Array.prototype.filter.call(w.body.querySelectorAll('button'), function (b) {
        return b.textContent === 'Add point';
      })[0];
      add.click();
      T.ok(w.labels().indexOf('x3') >= 0, 'a third point');
      w.set('x1', 20); w.set('y1', 0); w.set('x2', 20); w.set('y2', -4);
      w.set('x3', 24); w.set('y3', -6);
      return w.save().then(function () {
        var added = ctx.sent[0].body.interfaces[1];
        T.eq(added.structure, null);
        T.eq(added.points, [[20, 0], [20, -4], [24, -6]]);
        T.eq(added.stretch, null);
        T.eq(added.side, 'left');
      });
    }));
  });

  test('a flat pile offers below and above', function () {
    var ctx = rig(2);
    return ctx.done(Promise.resolve().then(function () {
      App.PROJECT.beams[0].points = [[2, -3], [20, -5]];
      var w = opened(ctx, function () { App.Interfaces.edit('interface_1'); });
      T.eq(w.spec.title, 'Edit interface');
      T.eq(w.choices('Side'), ['both', 'below', 'above']);
    }));
  });

  test('start: in the solid model it says why and sends nothing', function () {
    var ctx = rig(3);
    return ctx.done(Promise.resolve(App.Interfaces.start()).then(function (result) {
      T.eq(result, undefined);
      T.eq(ctx.sent.length, 0);
      T.ok(/switch to 2D/.test(ctx.notes.join(' ')), ctx.notes.join(' | '));
    }));
  });

  test('start: on a pile that is not there it says why and sends nothing', function () {
    var ctx = rig(2);
    return ctx.done(Promise.resolve(App.Interfaces.start('beam_9')).then(function () {
      T.eq(ctx.sent.length, 0);
      T.ok(/live sheet pile/.test(ctx.notes.join(' ')));
    }));
  });

  test('edit: opens the window on the interface, and an unknown id does nothing', function () {
    var ctx = rig(2);
    T.eq(App.Interfaces.edit('interface_9'), undefined);
    return ctx.done(Promise.resolve().then(function () {
      var w = opened(ctx, function () { App.Interfaces.edit('interface_1'); });
      T.eq(w.control('Name').value, 'Wall contact');
      T.eq(ctx.sent.length, 0, 'opening saves nothing');
      w.set('To y', -7);
      return w.save().then(function () {
        T.eq(ctx.sent[0].body.interfaces.map(function (i) { return i.id; }), ['interface_1']);
        T.eq(ctx.sent[0].body.interfaces[0].stretch, [[12, 0], [12, -7]]);
      });
    }));
  });

  test('an interface key is recognised, anything else is not', function () {
    var ctx = rig(2);
    return ctx.done(Promise.resolve().then(function () {
      T.ok(App.Interfaces.isInterfaceKey('interface_1'));
      T.ok(!App.Interfaces.isInterfaceKey('beam_1'));
    }));
  });
})();
