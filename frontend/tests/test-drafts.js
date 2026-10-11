/* ══════════════════════════════════════════════════════════════════
   test-drafts.js — what a new soil starts as, held to the command line's.

   The GUI starts a new soil from App.PropertySets and offers App.MaterialLibrary's
   presets; the command line (kratos-cli) starts one from core/model/drafts.py.
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

  T.test('the material library offers the same six presets as the command line', function () {
    var soils = App.MaterialLibrary.soils().map(function (s) {
      return { id: s.id, name: s.name, color: s.color, r_inter: s.rInter,
               interface_permeability: s.interfacePerm, variables: s.variables };
    });
    T.eq(soils, F.library);
  });

})();
