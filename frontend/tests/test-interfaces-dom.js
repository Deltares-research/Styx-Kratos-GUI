/* The interface window's browser half: the window that `start` and `edit` open,
   built against the real App.UI. The drafts, the checks and the patches are
   test-interfaces.js, which runs headless as well (frontend/tests/run_headless.py). */

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
                  selectObject: App.selectObject, state: App.state, DrawInput: App.DrawInput };
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

  test('the own-coordinate editor removes only the last added point', function () {
    var ctx = rig(2);
    return ctx.done(Promise.resolve().then(function () {
      var w = opened(ctx, function () { App.Interfaces.start(); });
      w.set('Along', '');
      function click(text) {
        Array.prototype.filter.call(w.body.querySelectorAll('button'), function (b) {
          return b.textContent === text;
        })[0].click();
      }
      click('Add point');
      T.ok(w.control('x3'));
      click('Remove last point');
      T.eq(w.control('x3'), null);
      T.ok(Array.prototype.filter.call(w.body.querySelectorAll('button'), function (b) {
        return b.textContent === 'Remove last point';
      })[0].disabled, 'the line always keeps its first two points');
    }));
  });

  test('picking a free interface reopens the form with the picked section coordinates', function () {
    var ctx = rig(2), picked;
    return ctx.done(Promise.resolve().then(function () {
      App.DrawInput = { start: function (mode, options) { picked = { mode: mode, options: options }; } };
      var first = opened(ctx, function () { App.Interfaces.start(); });
      first.set('Along', '');
      first.spec.buttons[0].onClick();
      T.eq(picked.mode, 'load');
      T.eq(picked.options.count, 2);
      var second = opened(ctx, function () {
        picked.options.onComplete([[20, -2, 0], [22, -9, 0]]);
      });
      T.eq(second.control('x1').value, '20');
      T.eq(second.control('y2').value, '-9');
      return second.save().then(function () {
        T.eq(ctx.sent[0].body.interfaces[1].points, [[20, -2], [22, -9]]);
        T.ok(second.closed());
      });
    }));
  });

  test('a rejected interface patch leaves the form open with the server reason', function () {
    var ctx = rig(2);
    return ctx.done(Promise.resolve().then(function () {
      App.Api = { patch: function () { return Promise.reject(new Error('Contact refused')); } };
      var w = opened(ctx, function () { App.Interfaces.edit('interface_1'); });
      return w.save().then(function () {
        T.ok(!w.closed());
        T.eq(w.message(), 'Contact refused');
      });
    }));
  });

  test('an off-pile stored stretch reports the coordinates that are invalid', function () {
    var ctx = rig(2);
    return ctx.done(Promise.resolve().then(function () {
      var record = Object.assign({}, App.PROJECT.interfaces[0], { stretch: [[14, -2], [12, -6]] });
      var problem = App.Interfaces.validate(record, App.PROJECT);
      T.ok(/From \(14, -2\)/.test(problem), problem);
      T.ok(/Sheet pile 1/.test(problem), problem);
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
