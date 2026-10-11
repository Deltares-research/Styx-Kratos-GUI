/* ══════════════════════════════════════════════════════════════════
   property-sets.js — what Kratos reads, as the editors show it.

   Every soil, sheet-pile profile, wall, tendon and contact in a project is a Kratos
   property set: a constitutive law and a `Variables` block under Kratos' own names, in
   the project's unit system (core/schemas.py `KratosPropertySet`). The deck
   carries it verbatim; the server fills in only what is missing and derivable, and says
   which. So the editors show Kratos' names and Kratos' numbers, labelled with the
   project's units -- nothing is converted between what is typed and what Kratos reads.

   This module is the knowledge the editors share: which law a new set starts with,
   which variables its law cannot do without, which ones the server derives when they
   are left out, the defaults a new set gets (stated in SI and expressed in the
   project's system), and how a typed value becomes a Kratos value. No DOM: runs
   headless (frontend/tests/test-property-sets.js). The property-grid rows it builds are
   plain arrays the frozen explorer already knows how to draw.
   ══════════════════════════════════════════════════════════════════ */

App.PropertySets = (function () {
  'use strict';

  var NAME = /^[A-Z][A-Z0-9_]*$/;

  var KINDS = {
    soil: {
      laws: { 2: 'GeoLinearElasticPlaneStrain2DLaw', 3: 'GeoIncrementalLinearElastic3DLaw' },
      required: ['YOUNG_MODULUS', 'POISSON_RATIO', 'DENSITY_SOLID'],
      shown: ['GEO_DRAINAGE_TYPE', 'YOUNG_MODULUS', 'POISSON_RATIO', 'DENSITY_SOLID',
              'DENSITY_WATER', 'POROSITY', 'PERMEABILITY_XX', 'PERMEABILITY_YY',
              'GEO_COHESION', 'GEO_FRICTION_ANGLE', 'K0_NC'],
      derived: ['GEO_DRAINAGE_TYPE', 'DENSITY_WATER', 'POROSITY', 'BULK_MODULUS_SOLID',
                'BULK_MODULUS_FLUID', 'DYNAMIC_VISCOSITY', 'PERMEABILITY_YY',
                'PERMEABILITY_XY', 'PERMEABILITY_ZZ', 'PERMEABILITY_YZ',
                'PERMEABILITY_ZX', 'K0_NC'],
      // A new soil: a loose drained sand, in SI. Porosity 0, as in Kratos' reference:
      // Kratos weighs a point at (1 - n) DENSITY_SOLID g + n S gamma_w, so at n = 0 the
      // soil weighs DENSITY_SOLID g -- 17 kN/m3 here -- whatever its saturation. A soil
      // that should weigh more below the water than above it needs a porosity and a
      // RETENTION_LAW (SaturatedBelowPhreaticLevelLaw), which the editor lets you add.
      defaults: { GEO_DRAINAGE_TYPE: 'CONSTANT_PW_FIELD', YOUNG_MODULUS: 1.0e7,
                  POISSON_RATIO: 0.3, DENSITY_SOLID: 17000 / 9.81, POROSITY: 0.0,
                  PERMEABILITY_XX: 1 / 86400, GEO_COHESION: 0.0, GEO_FRICTION_ANGLE: 30.0 }
    },
    beam: {
      law: 'TimoshenkoBeamElasticConstitutiveLaw',
      required: ['YOUNG_MODULUS', 'POISSON_RATIO', 'DENSITY', 'CROSS_AREA', 'I33'],
      shown: ['YOUNG_MODULUS', 'POISSON_RATIO', 'DENSITY', 'CROSS_AREA', 'I33',
              'AREA_EFFECTIVE_Y'],
      shown3d: ['I22', 'TORSIONAL_INERTIA', 'AREA_EFFECTIVE_Z'],
      derived: ['AREA_EFFECTIVE_Y', 'I22', 'TORSIONAL_INERTIA', 'AREA_EFFECTIVE_Z'],
      // An AZ 26-700 sheet pile, per metre run.
      defaults: { YOUNG_MODULUS: 2.1e11, POISSON_RATIO: 0.3, DENSITY: 7850.0,
                  CROSS_AREA: 0.0198, I33: 5.52e-4 }
    },
    panel: {
      law: 'LinearElasticPlaneStress2DLaw',
      required: ['YOUNG_MODULUS', 'POISSON_RATIO', 'DENSITY', 'THICKNESS'],
      shown: ['YOUNG_MODULUS', 'POISSON_RATIO', 'DENSITY', 'THICKNESS'],
      derived: [],
      defaults: { YOUNG_MODULUS: 2.1e11, POISSON_RATIO: 0.3, DENSITY: 7850.0, THICKNESS: 0.4 }
    },
    anchor: {
      law: 'TrussConstitutiveLaw',
      required: ['YOUNG_MODULUS', 'CROSS_AREA', 'DENSITY'],
      shown: ['YOUNG_MODULUS', 'CROSS_AREA', 'DENSITY'],
      derived: ['TRUSS_PRESTRESS_PK2'],
      // A four-strand tendon, per anchor.
      defaults: { YOUNG_MODULUS: 1.95e11, CROSS_AREA: 0.0006, DENSITY: 7850.0 }
    },
    interface: {
      law: 'GeoIncrementalLinearElasticInterfaceLaw',
      required: [],
      shown: ['INTERFACE_NORMAL_STIFFNESS', 'INTERFACE_SHEAR_STIFFNESS', 'GEO_COHESION',
              'GEO_FRICTION_ANGLE'],
      derived: ['GEO_DRAINAGE_TYPE', 'INTERFACE_NORMAL_STIFFNESS',
                'INTERFACE_SHEAR_STIFFNESS', 'GEO_COHESION', 'GEO_FRICTION_ANGLE',
                'GEO_DILATANCY_ANGLE'],
      defaults: {}
    }
  };

  var CHOICES = { GEO_DRAINAGE_TYPE: ['CONSTANT_PW_FIELD', 'FULLY_COUPLED'] };

  /* What the export cannot write without, beyond being a number. */
  var POSITIVE = ['YOUNG_MODULUS', 'CROSS_AREA', 'I33', 'I22', 'TORSIONAL_INERTIA',
                  'THICKNESS', 'AREA_EFFECTIVE_Y', 'AREA_EFFECTIVE_Z'];
  var NOT_NEGATIVE = ['DENSITY_SOLID', 'DENSITY_WATER', 'DENSITY', 'POROSITY',
                      'GEO_COHESION', 'GEO_FRICTION_ANGLE', 'K0_NC'];

  function kind(name) {
    var found = KINDS[name];
    if (!found) throw new Error('No property-set kind called ' + name + '.');
    return found;
  }

  function lawFor(kindName, dimension) {
    var k = kind(kindName);
    return k.laws ? k.laws[dimension === 3 ? 3 : 2] : k.law;
  }

  /* A new set's law and variables, in `system`. */
  function defaults(kindName, system, dimension) {
    var k = kind(kindName);
    return { constitutive_law: lawFor(kindName, dimension),
             variables: App.Units.convertVariables(k.defaults, 'SI', system || App.Units.current()),
             tables: {} };
  }

  function isNumber(value) { return typeof value === 'number' && isFinite(value); }

  function finite(value) {
    if (typeof value === 'number') return isFinite(value);
    if (Array.isArray(value)) return value.every(finite);
    return true;
  }

  /* An error sentence, or null. Mirrors what the server and the export refuse, so a set
     accepted here does not come back as a 422 or an export error. */
  function validate(kindName, set) {
    var k = kind(kindName);
    if (!set.constitutive_law || !String(set.constitutive_law).trim()) {
      return 'A property set needs a constitutive law.';
    }
    var variables = set.variables || {};
    var names = Object.keys(variables);
    for (var i = 0; i < names.length; i += 1) {
      var name = names[i], value = variables[name];
      if (!NAME.test(name)) return '"' + name + '" is not a Kratos variable name (CAPITALS_AND_UNDERSCORES).';
      if (!finite(value)) return name + ' must be a finite number.';
      if (POSITIVE.indexOf(name) >= 0 && isNumber(value) && !(value > 0)) {
        return name + ' must be greater than zero.';
      }
      if (NOT_NEGATIVE.indexOf(name) >= 0 && isNumber(value) && value < 0) {
        return name + ' cannot be negative.';
      }
    }
    if (isNumber(variables.POISSON_RATIO) && !(variables.POISSON_RATIO >= 0 && variables.POISSON_RATIO < 0.5)) {
      return 'POISSON_RATIO must be at least 0 and below 0.5.';
    }
    if (isNumber(variables.POROSITY) && !(variables.POROSITY < 1)) return 'POROSITY must be below 1.';
    var known = set.constitutive_law === lawFor(kindName, 2) || set.constitutive_law === lawFor(kindName, 3);
    if (known) {
      var missing = k.required.filter(function (n) { return !isNumber(variables[n]); });
      if (missing.length) {
        return set.constitutive_law + ' needs ' + missing.join(', ') + '.';
      }
    }
    return null;
  }

  /* A typed value as Kratos takes it: a number (a comma is a decimal point), a flag, a
     list in brackets, or text. Blank is `undefined` -- leave the variable out, and let
     the server derive it if it can. */
  function parse(text) {
    var raw = String(text === undefined || text === null ? '' : text).trim();
    if (raw === '') return undefined;
    if (raw === 'true' || raw === 'false') return raw === 'true';
    if (raw.charAt(0) === '[') {
      try { return JSON.parse(raw); } catch (e) { return raw; }
    }
    var number = Number(raw.replace(',', '.'));
    if (raw !== '' && isFinite(number) && /^[-+]?[0-9.,]+(e[-+]?[0-9]+)?$/i.test(raw)) return number;
    return raw;
  }

  function format(value) {
    if (value === undefined || value === null) return '';
    if (Array.isArray(value) || typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }

  /* Six significant figures' worth of decimals for the explorer's fixed-point display:
     2.1e11 Pa shows whole, 1.83486 t/m3 keeps its digits. */
  function decimals(value) {
    if (!isNumber(value) || value === 0) return 3;
    return Math.max(0, Math.min(10, 5 - Math.floor(Math.log(Math.abs(value)) / Math.LN10)));
  }

  function derivable(kindName, name) { return kind(kindName).derived.indexOf(name) >= 0; }

  /* The names an editor lists for a set: its kind's usual ones, the 3D extras in a 3D
     model, then whatever else the set carries, in its own order. */
  function names(kindName, set, dimension) {
    var k = kind(kindName);
    var out = k.shown.concat(dimension === 3 && k.shown3d ? k.shown3d : []);
    Object.keys((set && set.variables) || {}).forEach(function (n) {
      if (out.indexOf(n) < 0) out.push(n);
    });
    return out;
  }

  /* Rows for the Selection explorer's property grid: [label, shown, unit, read-only,
     editor]. A number is edited in place; a choice is a select; a variable the set
     leaves out is shown as derived, read-only -- set it in the editor dialog. Every
     edit goes through `check(set)`, which returns an error to refuse it. */
  function rows(kindName, set, dimension, check) {
    set.variables = set.variables || {};
    return names(kindName, set, dimension).map(function (name) {
      var value = set.variables[name];
      var unit = App.Units.variableLabel(name);
      if (value === undefined) {
        return [name, derivable(kindName, name) ? 'derived' : '—', unit, true];
      }
      if (CHOICES[name]) {
        return [name, String(value), '', false, {
          kind: 'select',
          options: function () { return CHOICES[name].map(function (c) { return { value: c, text: c }; }); },
          get: function () { return set.variables[name]; },
          set: function (chosen) { return assign(set, name, chosen, check); }
        }];
      }
      if (!isNumber(value)) return [name, format(value), unit, true];
      return [name, String(value), unit, false, {
        kind: 'number', decimals: decimals(value), unit: unit,
        get: function () { return set.variables[name]; },
        set: function (number) { return assign(set, name, number, check); }
      }];
    });
  }

  function assign(set, name, value, check) {
    var had = Object.prototype.hasOwnProperty.call(set.variables, name);
    var was = set.variables[name];
    if (value === undefined) delete set.variables[name]; else set.variables[name] = value;
    var problem = check ? check(set) : null;
    if (problem) {
      if (had) set.variables[name] = was; else delete set.variables[name];
      return problem;
    }
    return null;
  }

  return { KINDS: KINDS, CHOICES: CHOICES, lawFor: lawFor, defaults: defaults,
           validate: validate, parse: parse, format: format, decimals: decimals,
           derivable: derivable, names: names, rows: rows, assign: assign };
})();
