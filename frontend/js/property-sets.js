/* ══════════════════════════════════════════════════════════════════
   property-sets.js — what Kratos reads, as the editors show it.

   Every soil, sheet-pile profile, wall, tendon and contact in a project is a Kratos
   property set: a constitutive law and a `Variables` block under Kratos' own names, in
   the project's unit system (core/model/schemas.py `KratosPropertySet`). The deck
   carries it verbatim; the server fills in only what is missing and derivable, and says
   which. So the editors show Kratos' names and Kratos' numbers, labelled with the
   project's units -- nothing is converted between what is typed and what Kratos reads.

   This module is the knowledge the editors share: which law a new set starts with,
   which variables its law cannot do without, which ones the server derives when they
   are left out, the defaults a new set gets (stated in SI and expressed in the
   project's system), and how a typed value becomes a Kratos value. A soil's law is a
   soil model's (App.SoilModels, soil-models.js), which says what a soil lists and needs. No DOM: runs
   headless (frontend/tests/test-property-sets.js). The property-grid rows it builds are
   plain arrays the frozen explorer already knows how to draw.
   ══════════════════════════════════════════════════════════════════ */

App.PropertySets = (function () {
  'use strict';

  var NAME = /^[A-Z][A-Z0-9_]*$/;

  var S = App.SoilModels;
  var ELASTIC = 'linear_elastic';

  var KINDS = {
    soil: {
      laws: { 2: S.law(ELASTIC, 2), 3: S.law(ELASTIC, 3) },
      // The linear elastic model's; a soil of another model needs what that model says
      // (App.SoilModels.required).
      required: S.required(S.law(ELASTIC, 2), {}),
      shown: S.shown(ELASTIC, {}).map(function (p) { return p.name; }),
      // Left out, the export derives these (App.SoilModels.derived), or Kratos does. The
      // water is not a soil's at all: it is the project's (App.SoilModels.WATER).
      derived: ['GEO_DRAINAGE_TYPE', 'BULK_MODULUS_SOLID', 'PERMEABILITY_XX',
                'PERMEABILITY_YY', 'PERMEABILITY_XY', 'PERMEABILITY_ZZ', 'PERMEABILITY_YZ',
                'PERMEABILITY_ZX', 'MINIMUM_RELATIVE_PERMEABILITY', 'K0_NC',
                'BIOT_COEFFICIENT', 'GEO_POISSON_UNDRAINED'],
      // A new soil: a loose drained sand, in SI (core/model/soil_models.py), saturated
      // below the phreatic level. Porosity 0, as in Kratos' reference: Kratos weighs a
      // point at (1 - n) DENSITY_SOLID g + n S gamma_w, so at n = 0 the soil weighs
      // DENSITY_SOLID g -- 17 kN/m3 here -- whatever its saturation. A soil that should
      // weigh more below the water than above it needs a porosity.
      defaults: S.defaultsSI(ELASTIC)
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

  /* Every text value Kratos accepts, per variable that takes one, and the variables
     that are true or false: from the soil models' parameters. */
  var CHOICES = {};
  var FLAGS = [];
  S.order().forEach(function (model) {
    S.parameters(model).forEach(function (p) {
      if (p.choices) CHOICES[p.name] = p.choices.slice();
      if (p.flag && FLAGS.indexOf(p.name) < 0) FLAGS.push(p.name);
    });
  });

  /* What the export cannot write without, beyond being a number. */
  var POSITIVE = ['YOUNG_MODULUS', 'CROSS_AREA', 'I33', 'I22', 'TORSIONAL_INERTIA',
                  'THICKNESS', 'AREA_EFFECTIVE_Y', 'AREA_EFFECTIVE_Z'];
  var NOT_NEGATIVE = ['DENSITY_SOLID', 'DENSITY_WATER', 'DENSITY', 'POROSITY',
                      'GEO_COHESION', 'GEO_FRICTION_ANGLE', 'GEO_DILATANCY_ANGLE',
                      'GEO_TENSILE_STRENGTH', 'K0_NC', 'SATURATED_SATURATION',
                      'RESIDUAL_SATURATION', 'MINIMUM_RELATIVE_PERMEABILITY'];

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
     accepted here does not come back as a 422 or an export error. `partial`: a value
     the law needs may still be blank -- the server stores such a set and the export
     names what it lacks -- so a soil can be filled in one value at a time. */
  function validate(kindName, set, partial) {
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
    var needed = null;
    if (kindName === 'soil') {
      // The server's Material refuses them too (core/model/schemas.py).
      var own = S.WATER.filter(function (n) { return names.indexOf(n) >= 0; });
      if (own.length) {
        return own.join(', ') + (own.length === 1 ? ' belongs' : ' belong') +
               ' to the project\'s water, not to a soil: set it under Water.';
      }
      // A choice Kratos reads by name has to be one of its names, a flag a flag.
      for (var c = 0; c < names.length; c += 1) {
        var choice = CHOICES[names[c]];
        if (choice && choice.indexOf(variables[names[c]]) < 0) {
          return names[c] + ' must be one of ' + choice.join(', ') + '.';
        }
        if (FLAGS.indexOf(names[c]) >= 0 && typeof variables[names[c]] !== 'boolean') {
          return names[c] + ' must be true or false.';
        }
      }
      if (S.modelOf(set.constitutive_law) !== S.OTHER) {
        needed = S.required(set.constitutive_law, variables);
      }
    } else if (set.constitutive_law === lawFor(kindName, 2) ||
               set.constitutive_law === lawFor(kindName, 3)) {
      needed = k.required;
    }
    if (needed && !partial) {
      var missing = needed.filter(function (n) { return !isNumber(variables[n]); });
      if (missing.length) {
        return set.constitutive_law + ' needs ' + missing.join(', ') + '.';
      }
    }
    return kindName === 'soil' ? S.problem(set.constitutive_law, variables) : null;
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

  /* The names an editor lists for a set: its kind's usual ones (a soil: its model's, as
     its values show them), the 3D extras in a 3D model, then whatever else the set
     carries, in its own order. */
  function names(kindName, set, dimension) {
    var k = kind(kindName);
    var out = kindName === 'soil'
      ? S.shown(S.modelOf(set && set.constitutive_law), (set && set.variables) || {})
          .map(function (p) { return p.name; })
      : k.shown.concat(dimension === 3 && k.shown3d ? k.shown3d : []);
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

  /* A row for a variable the set may leave out, typed in place: "derived" until a
     number is typed, the number after. What an interface section's stiffnesses need,
     which have no editor dialog of their own; `section set ID NAME=VALUE` is the CLI's
     way to the same. */
  function typedRow(kindName, set, name, check) {
    set.variables = set.variables || {};
    var unit = App.Units.variableLabel(name);
    var value = set.variables[name];
    return [name, value === undefined ? 'derived' : String(value), unit, false, {
      kind: 'number', decimals: 0, unit: unit,
      get: function () {
        return set.variables[name] === undefined ? 'derived' : set.variables[name];
      },
      set: function (number) {
        // Writing back what `get` read leaves a derived value derived.
        if (number === 'derived') return null;
        return assign(set, name, number, check);
      }
    }];
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

  return { KINDS: KINDS, CHOICES: CHOICES, FLAGS: FLAGS, lawFor: lawFor, defaults: defaults,
           validate: validate, parse: parse, format: format, decimals: decimals,
           derivable: derivable, names: names, rows: rows, typedRow: typedRow,
           assign: assign };
})();
