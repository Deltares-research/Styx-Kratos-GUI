/* ══════════════════════════════════════════════════════════════════
   test-property-sets.js — what Kratos reads, as the editors show it.

   A soil, profile, wall, tendon or contact is a Kratos property set: a law and a
   Variables block under Kratos' names, in the project's units, carried into the deck
   verbatim (core/model/schemas.py). `App.PropertySets` is what the editors share about
   them: the law a new set starts with, what its law cannot do without, what the server
   derives when it is left out, and how a typed value becomes a Kratos value.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var P = App.PropertySets;

  function soil(variables) {
    return { constitutive_law: 'GeoLinearElasticPlaneStrain2DLaw',
             variables: Object.assign({ YOUNG_MODULUS: 1e7, POISSON_RATIO: 0.3,
                                        DENSITY_SOLID: 1800 }, variables || {}) };
  }

  T.test('a soil starts with the linear elastic law of its dimension', function () {
    T.eq(P.lawFor('soil', 2), 'GeoLinearElasticPlaneStrain2DLaw');
    T.eq(P.lawFor('soil', 3), 'GeoIncrementalLinearElastic3DLaw');
    T.eq(P.lawFor('beam', 2), 'TimoshenkoBeamElasticConstitutiveLaw');
  });

  T.test('defaults are stated in SI and arrive in the project\'s system', function () {
    var si = P.defaults('beam', 'SI', 2);
    var kn = P.defaults('beam', 'kN', 2);
    T.eq(si.variables.YOUNG_MODULUS, 2.1e11);
    T.near(kn.variables.YOUNG_MODULUS, 2.1e8, 1e-3);
    T.near(kn.variables.DENSITY, 7.85, 1e-12);
    T.eq(kn.variables.CROSS_AREA, si.variables.CROSS_AREA);
    T.eq(P.defaults('soil', 'SI', 3).constitutive_law, 'GeoIncrementalLinearElastic3DLaw');
  });

  T.test('a default set passes its own validation', function () {
    ['soil', 'beam', 'panel', 'anchor', 'interface'].forEach(function (k) {
      T.eq(P.validate(k, P.defaults(k, 'kN', 2)), null, k);
    });
  });

  T.test('a known law without what it needs is refused, naming it', function () {
    var set = soil();
    delete set.variables.DENSITY_SOLID;
    T.ok(/DENSITY_SOLID/.test(P.validate('soil', set)), P.validate('soil', set));
  });

  T.test('a law nobody here knows is the user\'s business', function () {
    T.eq(P.validate('soil', { constitutive_law: 'SmallStrainUDSM2DPlaneStrainLaw',
                              variables: { UDSM_NAME: 'mc.dll', UDSM_PARAMETERS: [1, 2] } }), null);
  });

  T.test('what Kratos could not read is refused', function () {
    T.ok(P.validate('soil', soil({ youngs: 1 })));
    T.ok(P.validate('soil', soil({ YOUNG_MODULUS: Infinity })));
    T.ok(P.validate('soil', soil({ YOUNG_MODULUS: 0 })));
    T.ok(P.validate('soil', soil({ POISSON_RATIO: 0.5 })));
    T.ok(P.validate('soil', soil({ POROSITY: 1 })));
    T.ok(P.validate('soil', soil({ GEO_COHESION: -1 })));
    T.ok(P.validate('soil', { constitutive_law: '', variables: {} }));
  });

  T.test('a typed value becomes what Kratos takes', function () {
    T.eq(P.parse('2.1e11'), 2.1e11);
    T.eq(P.parse(' 0,3 '), 0.3);
    T.eq(P.parse('-20000'), -20000);
    T.eq(P.parse('CONSTANT_PW_FIELD'), 'CONSTANT_PW_FIELD');
    T.eq(P.parse('true'), true);
    T.eq(P.parse('[1, 2.5]'), [1, 2.5]);
    T.eq(P.parse(''), undefined);
    T.eq(P.format([1, 2.5]), '[1,2.5]');
    T.eq(P.format(undefined), '');
  });

  T.test('the explorer shows six significant figures whatever the magnitude', function () {
    T.eq(P.decimals(2.1e11), 0);
    T.eq(P.decimals(1.83486), 5);
    T.eq(P.decimals(0.0198), 7);
  });

  T.test('the rows list the usual names, then whatever else the set carries', function () {
    var names = P.names('soil', soil({ OCR: 1.2 }), 2);
    T.eq(names[0], 'GEO_DRAINAGE_TYPE');
    T.eq(names[names.length - 1], 'OCR');
    T.ok(P.names('beam', { variables: {} }, 3).indexOf('I22') >= 0);
    T.ok(P.names('beam', { variables: {} }, 2).indexOf('I22') < 0);
  });

  T.test('a left-out derivable variable shows as derived, labelled in the project units', function () {
    var rows = P.rows('soil', soil(), 2);
    var k0 = rows.filter(function (r) { return r[0] === 'K0_NC'; })[0];
    T.eq(k0.slice(0, 4), ['K0_NC', 'derived', '', true]);
    var porosity = rows.filter(function (r) { return r[0] === 'POROSITY'; })[0];
    T.eq(porosity.slice(0, 4), ['POROSITY', '—', '', true], 'the soil\'s own: nothing derives it');
    var modulus = rows.filter(function (r) { return r[0] === 'YOUNG_MODULUS'; })[0];
    T.eq(modulus[2], App.Units.variableLabel('YOUNG_MODULUS'));
    T.eq(modulus[4].kind, 'number');
  });

  T.test('an edit through a row is refused, and undone, when the check says no', function () {
    var set = soil();
    var modulus = P.rows('soil', set, 2).filter(function (r) { return r[0] === 'YOUNG_MODULUS'; })[0];
    var refused = modulus[4].set(-1, null);
    T.eq(refused, null, 'no check given: written');
    T.eq(set.variables.YOUNG_MODULUS, -1);
    set.variables.YOUNG_MODULUS = 1e7;
    var check = function (s) { return P.validate('soil', s); };
    modulus = P.rows('soil', set, 2, check).filter(function (r) { return r[0] === 'YOUNG_MODULUS'; })[0];
    T.ok(modulus[4].set(-1));
    T.eq(set.variables.YOUNG_MODULUS, 1e7);
  });

  T.test('the drainage type is a choice between the two a soil can have', function () {
    var set = soil({ GEO_DRAINAGE_TYPE: 'DRAINED' });
    var row = P.rows('soil', set, 2).filter(function (r) { return r[0] === 'GEO_DRAINAGE_TYPE'; })[0];
    T.eq(row[4].kind, 'select');
    T.eq(row[4].options().map(function (o) { return o.value; }),
         ['DRAINED', 'FULLY_COUPLED']);
    T.eq(row[4].set('FULLY_COUPLED'), null);
    T.eq(set.variables.GEO_DRAINAGE_TYPE, 'FULLY_COUPLED');
  });

})();
