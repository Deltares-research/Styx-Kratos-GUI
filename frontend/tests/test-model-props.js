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
          if (row && row[4]) fn(key + ' / ' + group + ' / ' + row[0], row[4], key);
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
      NORMAL_LOADS: App.NORMAL_LOADS
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

  var MODELS = [['2D', function () { return window.VIEWPORT_PAYLOADS.project; }],
                ['3D', function () { return window.VIEWPORT_PAYLOADS.project3d; }]];

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
      function recorder(module) {
        return new Proxy({}, { get: function (target, verb) {
          return function () { reached.push(module + '.' + String(verb)); return Promise.resolve(); };
        } });
      }
      // Stood in only after the grids are built: building them reads these modules
      // (App.NormalLoads.length, for one), and a recorder there would be read as data.
      withProject(project(), function () {
        var saved = {};
        ['Loads', 'NormalLoads', 'Beams', 'Anchors', 'Interfaces', 'SoilVolumeDialog',
         'LivePatches', 'Water', 'WaterCommand'].forEach(function (module) {
          saved[module] = App[module];
          App[module] = recorder(module);
        });
        try {
          var broken = [];
          var buttons = 0;
          each(function (where, editor) {
            if (editor.kind !== 'button') return;
            buttons += 1;
            try { editor.run(); } catch (error) { broken.push(where + ': ' + error.message); }
          });
          T.eq(broken, []);
          T.ok(buttons > 3, 'only ' + buttons + ' buttons');
          T.ok(reached.length > 0, 'the buttons reached their modules');
        } finally {
          Object.keys(saved).forEach(function (module) { App[module] = saved[module]; });
        }
      });
    });
  });

})();
