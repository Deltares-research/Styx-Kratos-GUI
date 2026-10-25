/* ══════════════════════════════════════════════════════════════════
   test-soil-models.js — the soil models a material can be.

   App.SoilModels reads the table generated from core/model/soil_models.py: the law of
   each model per dimension, the parameters the material window lists for it, and when
   each is listed. test-drafts.js holds its answers to the Python's; these are what the
   window builds on.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var S = App.SoilModels;

  function names(params) { return params.map(function (p) { return p.name; }); }

  T.test('the models are linear elastic and Mohr-Coulomb, each with a law per dimension', function () {
    T.eq(S.order(), ['linear_elastic', 'mohr_coulomb']);
    T.eq(S.label('mohr_coulomb'), 'Mohr-Coulomb');
    T.eq(S.law('mohr_coulomb', 2), 'GeoMohrCoulombLawPlaneStrain');
    T.eq(S.law('mohr_coulomb', 3), 'GeoMohrCoulombLaw3D');
    T.eq(S.label(S.OTHER), 'Other');
  });

  T.test('a law is the model it is a law of, under its old name too', function () {
    T.eq(S.modelOf('GeoIncrementalLinearElastic3DLaw'), 'linear_elastic');
    T.eq(S.modelOf('GeoMohrCoulombWithTensionCutOff2D'), 'mohr_coulomb');
    T.eq(S.modelOf('SmallStrainUDSM2DPlaneStrainLaw'), S.OTHER);
    T.eq(S.lawIn('GeoMohrCoulombWithTensionCutOff2D', 2), 'GeoMohrCoulombLawPlaneStrain');
  });

  T.test('the tensile strength is listed only with the tension cut-off on', function () {
    var off = names(S.shown('mohr_coulomb', { GEO_ENABLE_TENSION_CUT_OFF: false }));
    var on = names(S.shown('mohr_coulomb', { GEO_ENABLE_TENSION_CUT_OFF: true }));
    T.ok(off.indexOf('GEO_TENSILE_STRENGTH') < 0, off.join(' '));
    T.ok(on.indexOf('GEO_TENSILE_STRENGTH') >= 0, on.join(' '));
    T.ok(names(S.shown('mohr_coulomb', {})).indexOf('GEO_TENSILE_STRENGTH') < 0,
         'left out, the cut-off is off');
  });

  T.test('the saturations follow the retention law, and left out it is SaturatedLaw', function () {
    T.ok(names(S.shown('linear_elastic', {})).indexOf('SATURATED_SATURATION') < 0);
    var below = names(S.shown('mohr_coulomb', { RETENTION_LAW: 'SaturatedBelowPhreaticLevelLaw' }));
    T.ok(below.indexOf('RESIDUAL_SATURATION') >= 0);
    T.ok(below.indexOf('VAN_GENUCHTEN_GN') < 0);
    var vg = names(S.shown('mohr_coulomb', { RETENTION_LAW: 'VanGenuchtenLaw' }));
    T.ok(vg.indexOf('VAN_GENUCHTEN_GN') >= 0);
  });

  T.test('the undrained Poisson ratio is listed for an undrained soil only', function () {
    T.ok(names(S.shown('mohr_coulomb', {})).indexOf('GEO_POISSON_UNDRAINED') < 0);
    T.ok(names(S.shown('mohr_coulomb', { GEO_DRAINAGE_TYPE: 'UNDRAINED' }))
      .indexOf('GEO_POISSON_UNDRAINED') >= 0);
  });

  T.test('the window groups follow the model, and a law of no model has none', function () {
    var titles = S.groups('mohr_coulomb', {}).map(function (g) { return g.title; });
    T.eq(titles, ['Drainage', 'Stiffness', 'Weight', 'Flow', 'Strength', 'Pore fluid',
                  'Initial stresses']);
    T.eq(S.groups(S.OTHER, {}), []);
  });

  T.test('every text value Kratos accepts is a choice, and the cut-off is a flag', function () {
    T.eq(App.PropertySets.CHOICES.GEO_DRAINAGE_TYPE,
         ['CONSTANT_PW_FIELD', 'FULLY_COUPLED', 'DRAINED', 'UNDRAINED']);
    T.eq(App.PropertySets.CHOICES.RETENTION_LAW,
         ['SaturatedLaw', 'SaturatedBelowPhreaticLevelLaw', 'VanGenuchtenLaw']);
    T.eq(App.PropertySets.FLAGS, ['GEO_ENABLE_TENSION_CUT_OFF']);
  });

  T.test('a default Mohr-Coulomb soil is valid as it stands, in either unit system', function () {
    ['SI', 'kN'].forEach(function (system) {
      var set = { constitutive_law: S.law('mohr_coulomb', 2),
                  variables: App.Units.convertVariables(S.defaultsSI('mohr_coulomb'), 'SI', system) };
      T.eq(App.PropertySets.validate('soil', set), null, system);
    });
  });

  T.test('a Mohr-Coulomb soil without its strength is refused, naming what it lacks', function () {
    var variables = S.defaultsSI('mohr_coulomb');
    delete variables.GEO_DILATANCY_ANGLE;
    var problem = App.PropertySets.validate('soil', { constitutive_law: S.law('mohr_coulomb', 2),
                                                      variables: variables });
    T.ok(/GEO_DILATANCY_ANGLE/.test(problem), problem);
  });

  T.test('a choice Kratos would not read, or a flag that is not one, is refused', function () {
    var variables = S.defaultsSI('mohr_coulomb');
    variables.RETENTION_LAW = 'Saturated';
    T.ok(/RETENTION_LAW must be one of/.test(App.PropertySets.validate('soil',
      { constitutive_law: S.law('mohr_coulomb', 2), variables: variables })));
    variables = S.defaultsSI('mohr_coulomb');
    variables.GEO_ENABLE_TENSION_CUT_OFF = 'yes';
    T.ok(/true or false/.test(App.PropertySets.validate('soil',
      { constitutive_law: S.law('mohr_coulomb', 2), variables: variables })));
  });

})();
