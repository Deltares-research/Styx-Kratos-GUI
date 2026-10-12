/* ══════════════════════════════════════════════════════════════════
   test-units.js — the project's unit system, in the browser.

   Kratos has no units: the project names a consistent set (core/model/units.py) and
   every value it holds -- property-set variables, loads, pressures -- is in that set.
   The browser needs to label each number for what it is, convert the library's presets
   into the project's system, and turn `units <system>` into the request that converts
   the whole project. `App.UNIT_TABLE` is generated from the server's own table
   (tests/test_unit_table.py), so the two cannot disagree.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var U = App.Units;

  function project(system) { return { unit_system: system }; }

  T.test('a project with no system is SI, the default', function () {
    T.eq(U.system(null), 'SI');
    T.eq(U.system({}), 'SI');
    T.eq(U.system(project('kN')), 'kN');
  });

  T.test('the systems on offer, with their titles', function () {
    T.eq(U.systems().map(function (s) { return s.name; }), ['SI', 'kN']);
    T.ok(/kN, m, t, s/.test(U.title('kN')), U.title('kN'));
  });

  T.test('a quantity is labelled in the system asked for', function () {
    T.eq(U.label('stress', 'SI'), 'Pa');
    T.eq(U.label('stress', 'kN'), 'kPa');
    T.eq(U.label('density', 'kN'), 't/m³');
    T.eq(U.label('line force', 'SI'), 'N/m');
    T.eq(U.label('dimensionless', 'SI'), '');
  });

  T.test('a Kratos variable is labelled by its quantity', function () {
    T.eq(U.quantityOf('YOUNG_MODULUS'), 'stress');
    T.eq(U.variableLabel('YOUNG_MODULUS', 'kN'), 'kPa');
    T.eq(U.variableLabel('DENSITY_SOLID', 'SI'), 'kg/m³');
    T.eq(U.variableLabel('GEO_FRICTION_ANGLE', 'SI'), '°');
    T.eq(U.variableLabel('INTERFACE_NORMAL_STIFFNESS', 'kN'), 'kN/m³');
  });

  T.test('a variable the table does not know has no label rather than a wrong one', function () {
    T.eq(U.quantityOf('UDSM_PARAMETERS'), null);
    T.eq(U.variableLabel('UDSM_PARAMETERS', 'SI'), '');
  });

  T.test('values convert between the systems the way the server converts them', function () {
    T.near(U.convert(150000, 'stress', 'SI', 'kN'), 150, 1e-9);
    T.near(U.convert(1834.86, 'density', 'SI', 'kN'), 1.83486, 1e-12);
    T.near(U.convert(1.0, 'force', 'kN', 'SI'), 1000, 1e-9);
    T.eq(U.convert(0.3, 'dimensionless', 'SI', 'kN'), 0.3);
    T.eq(U.convert(2.5, 'length', 'SI', 'kN'), 2.5);
  });

  T.test('a variables block converts by name, leaving strings and unknowns alone', function () {
    var out = U.convertVariables({ YOUNG_MODULUS: 3e7, POISSON_RATIO: 0.3,
                                   GEO_DRAINAGE_TYPE: 'CONSTANT_PW_FIELD',
                                   MY_OWN: 5 }, 'SI', 'kN');
    T.near(out.YOUNG_MODULUS, 3e4, 1e-9);
    T.eq(out.POISSON_RATIO, 0.3);
    T.eq(out.GEO_DRAINAGE_TYPE, 'CONSTANT_PW_FIELD');
    T.eq(out.MY_OWN, 5);
  });

  T.test('gravity is the same number in every system', function () {
    T.eq(U.gravity('SI'), 9.81);
    T.eq(U.gravity('kN'), 9.81);
  });

  T.test('the status bar names the system', function () {
    T.ok(/SI/.test(U.statusText(project('SI'))));
    T.ok(/kN/.test(U.statusText(project('kN'))));
  });

  /* ── `units` ─────────────────────────────────────────────────────── */

  T.test('anything that is not `units` is not this command', function () {
    T.eq(U.command('unit kN', project('SI')), false);
    T.eq(U.command('mesh', project('SI')), false);
  });

  T.test('a bare `units` says which system and what else there is, and sends nothing', function () {
    var answer = U.command('units', project('kN'));
    T.ok(answer.ok);
    T.eq(answer.body, null);
    T.ok(/kN/.test(answer.message) && /SI/.test(answer.message), answer.message);
  });

  T.test('`units <system>` asks the server to convert the project', function () {
    var answer = U.command('units kN', project('SI'));
    T.ok(answer.ok);
    T.eq(answer.body, { unit_system: 'kN' });
  });

  T.test('the system is matched without regard to case', function () {
    T.eq(U.command('units si', project('kN')).body, { unit_system: 'SI' });
    T.eq(U.command('UNITS KN', project('SI')).body, { unit_system: 'kN' });
  });

  T.test('the system the project is already in sends nothing', function () {
    var answer = U.command('units SI', project('SI'));
    T.ok(answer.ok);
    T.eq(answer.body, null);
    T.ok(/already/.test(answer.message), answer.message);
  });

  T.test('an unknown system is refused, naming the ones there are', function () {
    var answer = U.command('units imperial', project('SI'));
    T.eq(answer.ok, false);
    T.ok(/SI/.test(answer.message) && /kN/.test(answer.message), answer.message);
  });

})();
