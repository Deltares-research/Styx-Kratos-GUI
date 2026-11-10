/* ══════════════════════════════════════════════════════════════════
   test-drafts.js — what a new soil or structure starts as, held to the
   command line's.

   The GUI starts a new soil from App.PropertySets and offers App.MaterialLibrary's
   presets, and a new structure from the Structure mode's draft functions; the
   command line (kratos-cli) starts each from core/model/drafts.py.
   fixtures/drafts.js is written from the Python by tests/test_draft_parity.py, and
   this suite holds the JavaScript to it, so neither side can change alone.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var F = window.DRAFTS_FIXTURE;

  T.test('a new soil takes the same law in each dimension as on the command line', function () {
    T.eq(App.PropertySets.lawFor('soil', 2), F.soil_laws['2']);
    T.eq(App.PropertySets.lawFor('soil', 3), F.soil_laws['3']);
  });

  T.test('a new soil starts from the same variables as on the command line', function () {
    T.eq(App.PropertySets.KINDS.soil.defaults, F.soil_defaults);
  });

  /* The soil models: the same table is generated for both sides (soil-model-table.js);
     these hold the functions that read it to the Python's answers. */
  var M = F.soil_models;

  T.test('each soil model starts a new soil from the same variables as on the command line', function () {
    Object.keys(M.defaults).forEach(function (model) {
      T.eq(App.SoilModels.defaultsSI(model), M.defaults[model], model);
      T.eq(Object.keys(App.SoilModels.defaultsSI(model)), Object.keys(M.defaults[model]),
           model + ': in the same order');
    });
  });

  M.fill.forEach(function (c) {
    T.test('a soil filled in as on the command line: ' + c.title, function () {
      var after = Object.assign(JSON.parse(JSON.stringify(c.before)), c.changes);
      var filled = App.SoilModels.fill(c.before_law, JSON.parse(JSON.stringify(c.before)),
                                       c.after_law, after, c.system, c.skip);
      T.eq(filled, c.filled);
      T.eq(after, c.after);
      T.eq(App.SoilModels.filledNote(App.SoilModels.modelOf(c.after_law), filled), c.note);
    });
  });

  T.test('a blank soil is the one the command line\'s material add starts from', function () {
    T.eq(App.SoilModels.blankSI(), M.blank);
    T.eq(Object.keys(App.SoilModels.blankSI()), Object.keys(M.blank), 'in the same order');
  });

  M.fill_choice.forEach(function (c) {
    T.test('a choice fills as on the command line: ' + c.title, function () {
      var after = Object.assign(JSON.parse(JSON.stringify(c.before)), c.changes);
      var filled = App.SoilModels.fillChoice(c.before_law, JSON.parse(JSON.stringify(c.before)),
                                             c.after_law, after, c.system);
      T.eq(filled, c.filled);
      T.eq(after, c.after);
    });
  });

  M.problem.forEach(function (c) {
    T.test('a soil refused as on the command line: ' + c.title, function () {
      T.eq(App.SoilModels.problem(c.law, c.variables), c.problem);
    });
  });

  /* The same number, but for the last bits of a sum taken in another order. */
  function close(a, b, name) { T.near(a, b, 1e-12 * Math.max(1, Math.abs(b)), name); }

  T.test('the project\'s water is written as on the command line', function () {
    M.water.forEach(function (c) {
      var water = App.SoilModels.water(c.system, c.specific_weight, c.bulk_modulus, c.viscosity);
      var what = JSON.stringify([c.system, c.specific_weight, c.bulk_modulus, c.viscosity]);
      T.eq(Object.keys(water), Object.keys(c.water), what + ', the same variables');
      Object.keys(c.water).forEach(function (name) { close(water[name], c.water[name], what + ' ' + name); });
    });
  });

  M.derived.forEach(function (c) {
    T.test('a soil derives and computes as on the command line: ' + c.title, function () {
      var water = App.SoilModels.water(c.system, c.water.DENSITY_WATER * App.Units.gravity(c.system),
                                       c.water.BULK_MODULUS_FLUID, c.water.DYNAMIC_VISCOSITY);
      close(water.DENSITY_WATER, c.water.DENSITY_WATER, 'the water');
      var derived = App.SoilModels.derived(c.law, c.variables, c.water, c.system, c.flow);
      T.eq(Object.keys(derived), Object.keys(c.derived), 'derived, in the same order');
      Object.keys(c.derived).forEach(function (name) {
        if (typeof c.derived[name] === 'number') close(derived[name], c.derived[name], name);
        else T.eq(derived[name], c.derived[name], name);
      });
      var computed = App.SoilModels.computed(c.law, c.variables, c.water, c.system, c.flow);
      T.eq(Object.keys(computed), Object.keys(c.computed), 'computed, in the same order');
      Object.keys(c.computed).forEach(function (name) {
        close(computed[name], c.computed[name], name);
      });
    });
  });

  T.test('a soil lists what it lists on the command line', function () {
    M.shown.forEach(function (c) {
      T.eq(App.SoilModels.shown(c.model, c.variables, c.flow).map(function (p) { return p.name; }),
           c.shown, c.model + ' ' + JSON.stringify(c.variables) + (c.flow ? ' in a flow project' : ''));
    });
  });

  T.test('a soil law needs what it needs on the command line', function () {
    M.required.forEach(function (c) {
      T.eq(App.SoilModels.required(c.law, c.variables), c.required, c.law);
    });
  });

  T.test('a new soil takes the colour it takes on the command line', function () {
    M.fresh_color.forEach(function (c) {
      T.eq(App.SoilModels.freshColor(c.used, c.preferred), c.color,
           JSON.stringify(c.used) + ', ' + c.preferred);
    });
  });

  T.test('a soil model chosen leaves out what it leaves out on the command line', function () {
    M.unread.forEach(function (c) {
      T.eq(App.SoilModels.unread(c.law, c.variables), c.unread, c.law);
    });
  });

  T.test('a soil law has the same name in each dimension as on the command line', function () {
    M.law_in.forEach(function (c) {
      T.eq(App.SoilModels.lawIn(c.law, c.dimension), c.result, c.law + ' in ' + c.dimension + 'D');
    });
  });

  T.test('the material library offers the same six presets as the command line', function () {
    var soils = App.MaterialLibrary.soils().map(function (s) {
      return { id: s.id, model: s.model, name: s.name, color: s.color, r_inter: s.rInter,
               interface_permeability: s.interfacePerm, variables: s.variables };
    });
    T.eq(soils, F.library);
  });

  /* Each structure tool's draft, called on the projects the fixture carries and held to
     what core/model/drafts.py made of the same call. App.PROJECT is the project too,
     because a default section is stated in App.Units.current(), which reads it. */
  F.calls.forEach(function (c) {
    T.test('a structure drafted as on the command line: ' + c.title, function () {
      var project = JSON.parse(JSON.stringify(F.projects[c.project]));
      App.PROJECT = project;
      var path = c.call.split('.');
      var fn = App[path[0]][path[1]];
      var args = [project].concat(JSON.parse(JSON.stringify(c.args)));
      if (c.error !== undefined) {
        var refusal = null;
        try { fn.apply(null, args); } catch (e) { refusal = e; }
        T.ok(refusal, c.call + ' should refuse: ' + c.error);
        T.eq(refusal.message, c.error);
        return;
      }
      T.eq(fn.apply(null, args), c.result);
    });
  });

})();
