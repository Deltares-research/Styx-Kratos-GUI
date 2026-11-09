/* Every editor of every row of every property grid (frontend/js/model.js).

   `App.Model.apply` builds `App.OBJECT_PROPS`: per object, groups of rows, and on an
   editable row an editor -- `{kind, get, set[, options]}` -- or a button `{kind:
   'button', run}`. The explorer calls them; nothing else does. So rather than one test
   per row, three rules are swept over all of them, on the recorded test model in 2D and
   in 3D (fixtures/viewport-payloads.js):

   1. writing back what an editor reads is accepted -- a no-op edit is never refused;
   2. a number editor refuses something that is not a number, and changes nothing;
   3. every button runs, reaching the module it names.

   A row that breaks a rule is named in the failure, so a new grid is covered the day it
   is written. */

(function () {

  function each(fn) {
    Object.keys(App.OBJECT_PROPS || {}).forEach(function (key) {
      var props = App.OBJECT_PROPS[key];
      Object.keys((props && props.groups) || {}).forEach(function (group) {
        (props.groups[group] || []).forEach(function (row) {
          if (row && row[4]) fn(key + ' / ' + group + ' / ' + row[0], row[4], key, row[0]);
        });
      });
    });
  }

  function withProject(project, fn) {
    var saved = {
      LAYERS: App.LAYERS, MATERIALS: App.MATERIALS,
      LOADS: App.LOADS, PROJECT: App.PROJECT, props: App.OBJECT_PROPS, trees: {},
      BEAMS: App.BEAMS, BEAM_SECTIONS: App.BEAM_SECTIONS, PANEL_SECTIONS: App.PANEL_SECTIONS,
      ANCHORS: App.ANCHORS, ANCHOR_SECTIONS: App.ANCHOR_SECTIONS,
      INTERFACES: App.INTERFACES, INTERFACE_SECTIONS: App.INTERFACE_SECTIONS,
      NORMAL_LOADS: App.NORMAL_LOADS, BOUNDARY_CONDITIONS: App.BOUNDARY_CONDITIONS,
      PENDING_GRAVITY: App.PENDING_GRAVITY
    };
    Object.keys(App.TREES || {}).forEach(function (mode) { saved.trees[mode] = App.TREES[mode]; });
    App.OBJECT_PROPS = Object.assign({}, App.OBJECT_PROPS);
    try {
      App.Model.apply(JSON.parse(JSON.stringify(project)));
      return fn();
    } finally {
      Object.keys(saved).forEach(function (k) {
        if (k !== 'props' && k !== 'trees') App[k] = saved[k];
      });
      App.OBJECT_PROPS = saved.props;
      Object.keys(saved.trees).forEach(function (mode) { App.TREES[mode] = saved.trees[mode]; });
      App.Model.rebuildDerived();
    }
  }

  function conditionsAndBodies() {
    var project = JSON.parse(JSON.stringify(window.VIEWPORT_PAYLOADS.project));
    var conditions = App.BoundaryConditions;
    project.boundary_conditions = [
      conditions.draftDisplacement(project, 'line', { points: [[0, 0], [0, -10]] }),
      conditions.draftWaterPressure(project, 'domain', { fluid_pressure_type: 'Uniform', value: -100 }),
      conditions.draftWaterPressure(project, 'face', { fluid_pressure_type: 'Hydrostatic',
                                                      reference_coordinate: -1, face: 'left' }),
      conditions.draftSeepage(project, 'face', { face: 'right' })
    ];
    project.boundary_conditions.forEach(function (record, index) { record.id = 'grid_condition_' + index; });
    project.custom_parts = [{
      key: 'grid_fill', label: 'Grid fill', mat: project.materials[0].id,
      color: project.materials[0].color, source: 'drawn',
      recipe: { kind: 'polygon_extrude', vertices: [[0, 0, 0], [4, 0, 0], [0, -3, 0]],
                extrusion: [0, 0, 40] }
    }];
    return project;
  }

  function spatialStructures() {
    var project = JSON.parse(JSON.stringify(window.VIEWPORT_PAYLOADS.project3d));
    var d = project.domain;
    var x = (d.x0 + d.x1) / 2, z = (d.z0 + d.z1) / 2;
    var member = App.Beams.draftMember(project, [[x, d.y_top, z], [x, d.y_bottom, z]]);
    project.beams = [member];
    project.interfaces = [];
    project.beam_sections = App.Beams.sectionsFor(project, member);
    var anchor = App.Anchors.draft(project);
    project.anchors = [anchor];
    project.anchor_sections = App.Anchors.sectionsFor(project, anchor);
    return project;
  }

  function freeInterface() {
    var project = JSON.parse(JSON.stringify(window.VIEWPORT_PAYLOADS.project));
    project.beams = []; project.anchors = []; project.interfaces = [];
    var contact = App.Interfaces.draft(project);
    project.interfaces = [contact];
    project.interface_sections = App.Interfaces.sectionsFor(project, contact);
    return project;
  }

  var MODELS = [['2D', function () { return window.VIEWPORT_PAYLOADS.project; }],
                ['3D', function () { return window.VIEWPORT_PAYLOADS.project3d; }],
                ['conditions and custom soil', conditionsAndBodies],
                ['space member and anchor', spatialStructures],
                ['free soil interface', freeInterface]];

  test('member property edits change coordinates and roll back a zero-length member', function () {
    withProject(spatialStructures(), function () {
      var member = App.BEAMS[0];
      var geometry = App.OBJECT_PROPS[member.id].groups.Geometry;
      function coordinate(label) {
        return geometry.filter(function (row) { return row[0] === label; })[0][4];
      }
      var y2 = coordinate('y2'), old = y2.get();
      var changed = (member.points[0][1] + old) / 2;
      T.eq(y2.set(changed), null);
      T.eq(y2.get(), changed);
      T.eq(member.points[1][1], changed);
      T.ok(y2.set(member.points[0][1]), 'coincident endpoints are refused');
      T.eq(y2.get(), changed, 'the refused coordinate is rolled back');
    });
  });

  test("an anchor's force limits are typed in place, and taken away with a button", function () {
    var project = JSON.parse(JSON.stringify(window.VIEWPORT_PAYLOADS.project));
    var pile = project.beams[0];
    var anchor = App.Anchors.draftFromPoints(project, [pile.points[0], [pile.points[0][0] - 1,
                                                                        pile.points[0][1]]]);
    project.anchors = [anchor];
    project.anchor_sections = App.Anchors.sectionsFor(project, anchor);
    project.anchor_sections.forEach(function (section) {
      if (section.id === anchor.section) {
        section.tension_limit = 900;
        section.compression_limit = null;
      }
    });
    withProject(project, function () {
      var tendon = App.ANCHOR_SECTIONS.filter(function (s) { return s.id === anchor.section; })[0];
      function rows() { return App.OBJECT_PROPS[anchor.id].groups.Tendon; }
      function row(label) { return rows().filter(function (r) { return r[0] === label; }); }
      var tension = row('Tension limit')[0], compression = row('Compression limit')[0];
      T.ok(tension && compression, 'both limits have a row');
      T.eq(tension[4].get(), tendon.tension_limit);
      T.eq(compression[4].get(), null, 'a tendon takes no compression: no limit');
      T.ok(tension[4].set(-5), 'a limit must be above nought');
      T.eq(compression[4].set(250), null);
      T.eq(tendon.compression_limit, 250);
      var saved = App.commitSelectionEdit, committed = [];
      App.commitSelectionEdit = function (key) { committed.push(key); };
      try {
        var clear = row('Limit').filter(function (r) { return /tension/.test(r[4].text); })[0];
        T.ok(clear, 'a set tension limit can be taken away');
        clear[4].run();
        T.eq(tendon.tension_limit, null);
        T.eq(committed, [anchor.id]);
      } finally { App.commitSelectionEdit = saved; }
    });
  });

  test('free-interface property edits move its line and refuse coincident endpoints', function () {
    withProject(freeInterface(), function () {
      var contact = App.INTERFACES[0];
      var geometry = App.OBJECT_PROPS[contact.id].groups.Geometry;
      var row = geometry.filter(function (entry) { return entry[0] === 'y2'; })[0];
      T.ok(row, 'the endpoint elevation is editable');
      var editor = row[4], changed = (contact.points[0][1] + contact.points[1][1]) / 2;
      T.eq(editor.set(changed), null);
      T.eq(editor.get(), changed);
      T.ok(editor.set(contact.points[0][1]));
      T.eq(editor.get(), changed);
    });
  });

  test('the status-bar unit switch requests conversion once and follows the current project', function () {
    var item = document.createElement('span'), command = App.Command, commands = [];
    item.id = 'sb-units';
    document.body.appendChild(item);
    App.Command = { run: function (text) { commands.push(text); } };
    try {
      withProject(window.VIEWPORT_PAYLOADS.project, function () {
        App.Model.apply(App.PROJECT);
        var current = App.Units.current();
        var other = App.Units.systems().filter(function (system) { return system.name !== current; })[0];
        item.click();
        T.eq(commands, ['units ' + other.name], 'reapplying does not duplicate the listener');
        T.eq(item.textContent, App.Units.statusText(App.PROJECT));
        App.Model.apply(Object.assign({}, App.PROJECT, { unit_system: other.name }));
        item.click();
        T.eq(commands, ['units ' + other.name, 'units ' + current]);
        T.eq(item.textContent, App.Units.statusText(App.PROJECT));
      });
    } finally { item.remove(); App.Command = command; }
  });

  test('model exposes the edited domain separately from the stored project', function () {
    withProject(window.VIEWPORT_PAYLOADS.project3d, function () {
      T.eq(App.Model.domain(), App.Model.pendingDomain());
      T.eq(App.Model.domain().x0, App.PROJECT.domain.x0);
    });
  });

  test('computed volumes replace the property-grid placeholder without changing other rows', function () {
    withProject(window.VIEWPORT_PAYLOADS.project3d, function () {
      var key = 'soil_' + App.LAYERS[0].id;
      var rows = App.OBJECT_PROPS[key].groups.General;
      var volume = rows.filter(function (row) { return row[0] === 'Volume'; })[0];
      T.ok(volume, 'the solid layer has a volume row');
      var others = JSON.stringify(rows.filter(function (row) { return row !== volume; }));
      var mass = {}; mass[key] = 123.456; mass.missing_part = 5;
      App.Model.setVolumes(mass);
      T.eq(volume[1], '123.5');
      T.eq(volume[3], false);
      T.eq(JSON.stringify(rows.filter(function (row) { return row !== volume; })), others);
    });
  });

  test('accepted imported parts populate the explorer and its visibility group', function () {
    withProject(window.VIEWPORT_PAYLOADS.project3d, function () {
      var saved = { Viewport: App.Viewport, Explorer: App.Explorer, state: App.state }, keys, mounted;
      App.state = { mode: 'soil' };
      App.Viewport = { setImportedGroupKeys: function (value) { keys = value; } };
      App.Explorer = { mountTree: function (mode) { mounted = mode; } };
      try {
        App.Model.setImportedParts([{ key: 'deck:soil', label: 'Imported soil', color: '#123456' }]);
        T.eq(keys, ['deck:soil']);
        T.eq(mounted, App.state.mode);
        var found;
        (function walk(nodes) {
          (nodes || []).forEach(function (node) {
            if (node.label === 'Imported mesh') found = node;
            walk(node.children);
          });
        })(App.TREES[App.state.mode]);
        T.ok(found);
        T.eq(found.count, 1);
        T.eq(found.children[0].obj, 'deck:soil');
        App.Model.setImportedParts([]);
        T.eq(keys, []);
      } finally {
        App.Model.setImportedParts([]);
        Object.assign(App, saved);
      }
    });
  });

  MODELS.forEach(function (model) {
    var name = model[0], project = model[1];

    test('property grid (' + name + '): there are editors to check', function () {
      withProject(project(), function () {
        var count = 0;
        each(function () { count += 1; });
        T.ok(count > 20, 'only ' + count + ' editable rows found');
      });
    });

    test('property grid (' + name + '): writing back what an editor reads is accepted', function () {
      withProject(project(), function () {
        var refused = [];
        each(function (where, editor) {
          if (typeof editor.get !== 'function' || typeof editor.set !== 'function') return;
          var value = editor.get();
          var answer = editor.set(value);
          if (answer) refused.push(where + ': ' + answer);
          if (JSON.stringify(editor.get()) !== JSON.stringify(value)) {
            refused.push(where + ': the value changed on a no-op write');
          }
        });
        T.eq(refused, []);
      });
    });

    test('property grid (' + name + '): a select reads one of its own options', function () {
      withProject(project(), function () {
        var bad = [];
        each(function (where, editor) {
          if (editor.kind !== 'select' || typeof editor.options !== 'function') return;
          var values = editor.options().map(function (o) {
            return typeof o === 'object' ? o.value : o;
          });
          if (values.indexOf(editor.get()) < 0) {
            bad.push(where + ': ' + JSON.stringify(editor.get()) + ' not in ' + values.join(','));
          }
        });
        T.eq(bad, []);
      });
    });

    test('property grid (' + name + '): a number editor refuses what is not a number', function () {
      withProject(project(), function () {
        var accepted = [];
        each(function (where, editor) {
          if (editor.kind !== 'number' || typeof editor.set !== 'function') return;
          var before = JSON.stringify(editor.get());
          var answer = editor.set(NaN);
          if (!answer || typeof answer !== 'string') accepted.push(where);
          if (JSON.stringify(editor.get()) !== before) accepted.push(where + ' (changed)');
        });
        T.eq(accepted, []);
      });
    });

    test('property grid (' + name + '): every button runs and reaches its module', function () {
      var reached = [];
      // Stood in only after the grids are built: building them reads these modules
      // (App.NormalLoads.length, for one), and a recorder there would be read as data.
      withProject(project(), function () {
        var saved = { commitSelectionEdit: App.commitSelectionEdit };
        App.commitSelectionEdit = function (key) {
          reached.push({ method: 'commitSelectionEdit', args: [key] });
          return Promise.resolve();
        };
        ['Loads', 'NormalLoads', 'Beams', 'Anchors', 'Interfaces', 'SoilVolumeDialog',
         'BoundaryConditions'].forEach(function (module) {
          saved[module] = App[module];
          App[module] = Object.assign({}, App[module]);
          (module === 'SoilVolumeDialog' ? ['open'] : ['edit', 'remove']).forEach(function (verb) {
            App[module][verb] = function () {
              reached.push({ method: module + '.' + verb, args: Array.prototype.slice.call(arguments) });
              return Promise.resolve();
            };
          });
        });
        try {
          var broken = [];
          var buttons = 0;
          each(function (where, editor, key, label) {
            if (editor.kind !== 'button') return;
            buttons += 1;
            try {
              var part = (App.PROJECT.custom_parts || []).filter(function (item) { return item.key === key; })[0];
              var module = [
                ['Loads', App.LOADS], ['NormalLoads', App.NORMAL_LOADS],
                ['Beams', App.BEAMS], ['Anchors', App.ANCHORS],
                ['Interfaces', App.INTERFACES], ['BoundaryConditions', App.BOUNDARY_CONDITIONS]
              ].filter(function (entry) {
                return (entry[1] || []).some(function (record) { return record.id === key; });
              })[0];
              var expected;
              if (part) expected = { method: 'SoilVolumeDialog.open', args: [part] };
              else if (label === 'Stiffness' || label === 'Limit') {
                expected = { method: 'commitSelectionEdit', args: [key] };
              }
              else {
                T.ok(module, where + ': no expected object family');
                T.ok(label === 'Edit' || label === 'Delete', where + ': no expected button action');
                expected = { method: module[0] + (label === 'Edit' ? '.edit' : '.remove'), args: [key] };
              }
              reached.length = 0;
              editor.run();
              T.eq(reached, [expected], where);
              if (label === 'Stiffness') {
                var record = App.INTERFACES.filter(function (item) { return item.id === key; })[0];
                var section = App.INTERFACE_SECTIONS.filter(function (item) { return item.id === record.section; })[0];
                T.eq(section.variables.INTERFACE_NORMAL_STIFFNESS, undefined, where);
                T.eq(section.variables.INTERFACE_SHEAR_STIFFNESS, undefined, where);
              }
            } catch (error) { broken.push(where + ': ' + error.message); }
          });
          T.eq(broken, []);
          T.ok(buttons > 3, 'only ' + buttons + ' buttons');
        } finally {
          Object.keys(saved).forEach(function (module) { App[module] = saved[module]; });
        }
      });
    });
  });

})();
