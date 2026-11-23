/* ══════════════════════════════════════════════════════════════════
   soil-models.js — the soil models a material can be.

   The material window offers a soil model first -- linear elastic or Mohr-Coulomb --
   and lists what that model's law reads: its parameters in groups, each with the value
   a new soil starts from, the text values Kratos accepts for a choice, and when it is
   listed at all (a tensile strength only with the tension cut-off on). A law no model
   is, is "Other": the user's own, written as typed.

   It lists what the choices make relevant and nothing else: no strength for a linear
   elastic soil, no flow parameters unless the soil is FULLY_COUPLED (or the project a
   groundwater flow calculation), and no water -- that is the project's, one for every
   soil. What the export derives where a soil leaves it out (`derived`) and what follows
   from its numbers (`computed`) are shown with their values.

   The table is the server's (core/model/soil_models.py), generated into
   soil-model-table.js. These are the server's functions over it, in the same words;
   tests/test_draft_parity.py holds the two to the same answers. No DOM: runs headless.
   ══════════════════════════════════════════════════════════════════ */

App.SoilModels = (function () {
  'use strict';

  function table() { return App.SOIL_MODEL_TABLE; }
  function models() { return table().models; }

  var OTHER = 'other';
  var UDSM = 'udsm';

  /* ── A UDSM soil: its library's model and parameters ─────────────────
     The models are the server's (core/model/udsm.py), loaded as App.UDSM_LIBRARY
     (GET /api/udsm/library.js); these are core/model/soil_models.py's `udsm_*`. */

  function udsmModels() {
    return (App.UDSM_LIBRARY && App.UDSM_LIBRARY.models) || [];
  }

  function basename(file) { return String(file).replace(/\\/g, '/').split('/').pop().toLowerCase(); }

  /* The library model a soil holding `variables` is, or null. */
  function udsmModel(variables) {
    variables = variables || {};
    var file = variables.UDSM_NAME, number = variables.UDSM_NUMBER;
    if (typeof file !== 'string' || typeof number !== 'number') return null;
    return udsmModels().filter(function (m) {
      return m.file.toLowerCase() === basename(file) && m.number === number;
    })[0] || null;
  }

  /* The model named `id` (`MohrCoulomb64:1`), or null. */
  function udsmById(id) {
    return udsmModels().filter(function (m) { return m.id === id; })[0] || null;
  }

  /* The start value of `model`'s parameter `index` (0-based) in `system`. */
  function udsmDefault(model, index, system) {
    var q = model.parameters[index].quantity;
    return q ? App.Units.fromSI(model.defaults[index], q, system) : model.defaults[index];
  }

  /* Make the soil holding `variables` the UDSM model `model`, with its start values in
     `system`. Returns the names set. */
  function udsmChoose(variables, model, system) {
    variables.UDSM_NAME = model.file;
    variables.UDSM_NUMBER = model.number;
    variables.IS_FORTRAN_UDSM = true;
    variables.UMAT_PARAMETERS = model.parameters.map(function (p, i) {
      return udsmDefault(model, i, system);
    });
    [['INDEX_OF_UMAT_C_PARAMETER', 'GEO_COHESION'],
     ['INDEX_OF_UMAT_PHI_PARAMETER', 'GEO_FRICTION_ANGLE']].forEach(function (pair) {
      if (Object.prototype.hasOwnProperty.call(model.roles, pair[1])) {
        variables[pair[0]] = model.roles[pair[1]];
      } else {
        delete variables[pair[0]];
      }
    });
    return table().udsm.variables.filter(function (name) {
      return Object.prototype.hasOwnProperty.call(variables, name);
    });
  }

  /* UMAT_PARAMETERS[index - 1], `index` 1-based; null when there is no such number. */
  function udsmParameter(variables, index) {
    var values = (variables || {}).UMAT_PARAMETERS;
    if (typeof index !== 'number' || index % 1 !== 0 || !Array.isArray(values) ||
        index < 1 || index > values.length) return null;
    var v = values[index - 1];
    return typeof v === 'number' && isFinite(v) ? v : null;
  }

  /* Why Kratos would refuse a UDSM soil: its parameters are not as many as its model
     reads. */
  function udsmProblem(variables) {
    var model = udsmModel(variables);
    var values = (variables || {}).UMAT_PARAMETERS;
    if (!model || !Array.isArray(values) || values.length === model.parameters.length) return null;
    return 'UMAT_PARAMETERS has ' + values.length + ' values, and ' + model.name + ' in ' +
           model.file + ' reads ' + model.parameters.length + ': ' +
           model.parameters.map(function (p) { return p.label; }).join(', ') + '.';
  }

  /* The unit of a library parameter in `system`, or the library's own. */
  function udsmUnit(parameter, system) {
    return parameter.quantity ? App.Units.label(parameter.quantity, system)
                              : String(parameter.unit).replace(/#/g, '');
  }

  /* The model `law` is, under any of its names, or 'other'. */
  function modelOf(law) {
    var found = OTHER;
    table().order.forEach(function (id) {
      var m = models()[id];
      if (found !== OTHER) return;
      if (Object.keys(m.laws).some(function (d) { return m.laws[d] === law; }) ||
          Object.prototype.hasOwnProperty.call(m.old_laws, law)) found = id;
    });
    return found;
  }

  function label(model) { return models()[model] ? models()[model].label : 'Other'; }

  /* The law of `model` in a model of dimension `dim`. */
  function law(model, dim) {
    if (!models()[model]) throw new Error('There is no soil model ' + model + '.');
    return models()[model].laws[dim === 3 ? '3' : '2'];
  }

  /* `name` as a model of dimension `dim` writes it. */
  function lawIn(name, dim) {
    var model = modelOf(name);
    return model === OTHER ? name : law(model, dim);
  }

  function parameters(model) {
    var m = models()[model];
    if (!m) return [];
    return m.groups.reduce(function (all, g) { return all.concat(g.parameters); }, []);
  }

  function hsl(h, s, l) {
    var a = s * Math.min(l, 1 - l);
    function channel(n) {
      var k = (n + h / 30) % 12;
      var v = l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
      return ('0' + Math.round(v * 255).toString(16)).slice(-2);
    }
    return '#' + channel(0) + channel(8) + channel(4);
  }

  /* A colour no soil has yet, `used` being the project's: `preferred` -- a preset's
     own -- while it is free, else the palette's first free one, then hues a golden
     angle apart once the palette is spent (core/model/soil_models.py `fresh_color`). */
  function freshColor(used, preferred) {
    var taken = {};
    (used || []).forEach(function (c) { taken[String(c).toLowerCase()] = true; });
    if (preferred !== undefined && preferred !== null && !taken[preferred.toLowerCase()]) {
      return preferred;
    }
    var free = table().palette.filter(function (c) { return !taken[c]; })[0];
    if (free) return free;
    for (var n = 0; ; n++) {
      var c = hsl((n * 137.508) % 360, 0.45, 0.6);
      if (!taken[c]) return c;
    }
  }

  /* What choosing `law` leaves out of a soil holding `variables`: what another model
     lists and the model of `law` does not (core/model/soil_models.py `unread`). */
  function unread(law, variables) {
    var model = modelOf(law);
    if (model === OTHER) return [];
    var names = function (id) { return parameters(id).map(function (p) { return p.name; }); };
    var own = reads(model);
    var listed = table().order.reduce(function (all, id) { return all.concat(names(id)); },
                                      table().udsm.variables.slice());
    return Object.keys(variables || {}).filter(function (name) {
      return listed.indexOf(name) >= 0 && own.indexOf(name) < 0;
    });
  }

  /* Every variable a soil of `model` reads: its parameters, and a UDSM soil's
     UDSM_VARIABLES (core/model/soil_models.py `reads`). */
  function reads(model) {
    var names = parameters(model).map(function (p) { return p.name; });
    return model === UDSM ? names.concat(table().udsm.variables) : names;
  }

  /* `name` as the deck reads it: the soil's, or what Kratos takes when it is left out. */
  function valueOf(name, variables, model) {
    if (Object.prototype.hasOwnProperty.call(variables, name)) return variables[name];
    var other = parameters(model).filter(function (q) { return q.name === name; })[0];
    return other && other.absent !== undefined ? other.absent : null;
  }

  function holds(p, variables, model, flow) {
    if (p.flow && !flow &&
        table().flowing.indexOf(valueOf('GEO_DRAINAGE_TYPE', variables, model)) < 0) return false;
    if (!p.when) return true;
    var value = valueOf(p.when.name, variables, model);
    return p.when.values.some(function (v) { return v === value; });
  }

  /* The parameters the window lists for a soil of `model` holding `variables`; `flow` in
     a groundwater flow project, which reads every soil's flow parameters. */
  function shown(model, variables, flow) {
    return parameters(model).filter(function (p) { return holds(p, variables || {}, model, flow); });
  }

  /* Its groups, each with the parameters shown in it; an empty group is left out. */
  function groups(model, variables, flow) {
    var m = models()[model];
    if (!m) return [];
    return m.groups.map(function (g) {
      return { title: g.title, parameters: g.parameters.filter(function (p) {
        return holds(p, variables || {}, model, flow);
      }) };
    }).filter(function (g) { return g.parameters.length; });
  }

  /* What the law `name` cannot run without, for a soil holding `variables`. */
  function required(name, variables) {
    var model = modelOf(name);
    var own = model === UDSM ? table().udsm.required.slice() : [];
    return own.concat(shown(model, variables).filter(function (p) { return p.required; })
      .map(function (p) { return p.name; }));
  }

  /* Whether `value` is something the law can run with (core/model/soil_models.py
     `_given`). */
  function given(name, value) {
    if (name === 'UDSM_NAME') return typeof value === 'string' && value.trim() !== '';
    if (name === 'UMAT_PARAMETERS') {
      return Array.isArray(value) && value.length > 0 && value.every(function (v) {
        return typeof v === 'number' && isFinite(v);
      });
    }
    if (name === 'UDSM_NUMBER') return typeof value === 'number' && value % 1 === 0 && value >= 1;
    return typeof value === 'number' && isFinite(value);
  }

  function find(model, name) {
    return parameters(model).filter(function (p) { return p.name === name; })[0] || null;
  }

  function defaultIn(p, system) {
    if (p.default === undefined) return undefined;
    if (typeof p.default !== 'number') return p.default;
    var one = {}; one[p.name] = p.default;
    return App.Units.convertVariables(one, 'SI', system)[p.name];
  }

  function has(variables, name) { return Object.prototype.hasOwnProperty.call(variables, name); }

  /* Fill into `after` the defaults of what a soil now lists and lacks: every one when the
     soil is new or changed model; when the model stayed, the ones not listed before (a
     retention law chosen brings its saturations) and the ones its law cannot run
     without. Nothing held is replaced; a name in `skip` is never filled. Returns the
     names filled, in the order filled. */
  function fill(beforeLaw, before, afterLaw, after, system, skip, flow) {
    var model = modelOf(afterLaw);
    var old = [];
    if (beforeLaw && modelOf(beforeLaw) === model) {
      old = shown(model, before, flow).map(function (p) { return p.name; });
    }
    skip = skip || [];
    var filled = [];
    if (model === UDSM && !has(after, 'UMAT_PARAMETERS') && skip.indexOf('UMAT_PARAMETERS') < 0) {
      // The soil's own model when it names one, else the first the libraries hold.
      var chosen = udsmModel(after) || udsmModels()[0];
      if (chosen) filled = filled.concat(udsmChoose(after, chosen, system));
    }
    for (;;) {
      var next = shown(model, after, flow).filter(function (p) {
        return !has(after, p.name) && skip.indexOf(p.name) < 0 && p.default !== undefined &&
               (old.indexOf(p.name) < 0 || p.required);
      })[0];
      if (!next) return filled;
      after[next.name] = defaultIn(next, system);
      filled.push(next.name);
    }
  }

  /* The variables a new soil of `model` starts with, in SI. */
  function defaultsSI(model) {
    var out = {};
    fill(null, {}, law(model, 2), out, 'SI');
    return out;
  }

  /* What the law `name` cannot run without and a soil holding `variables` leaves blank. */
  function missing(name, variables) {
    variables = variables || {};
    return required(name, variables).filter(function (n) { return !given(n, variables[n]); });
  }

  /* `fill`, as a choice in the material window fills -- a model, a drainage type, a
     flag. A soil still being filled in by hand, `missing` something before the choice,
     gets no number its new law must have, and nothing it was listing and left blank. */
  function fillChoice(beforeLaw, before, afterLaw, after, system, flow) {
    var skip = [];
    if (missing(beforeLaw, before).length) {
      skip = parameters(modelOf(afterLaw)).filter(function (p) { return p.required; })
        .concat(shown(modelOf(beforeLaw), before, flow).filter(function (p) {
          return !has(before, p.name);
        }))
        .map(function (p) { return p.name; });
    }
    return fill(beforeLaw, before, afterLaw, after, system, skip, flow);
  }

  /* A soil to fill in by hand, in SI: the catalogue's (core/model/soil_models.py
     `blank_si`), which `kratos-cli material add` starts from too. */
  function blankSI() { return JSON.parse(JSON.stringify(table().blank)); }

  function filledNote(model, names) {
    if (!names.length) return null;
    return 'Filled in from the ' + label(model) + ' defaults: ' + names.join(', ') + '.';
  }

  function number(variables, name) {
    variables = variables || {};
    var v = variables[name];
    return typeof v === 'number' && isFinite(v) ? v : null;
  }

  /* ── The water, and what follows from a soil's numbers ─────────────── */

  function constant(name) { return table().constants[name]; }

  /* The water every soil shares as Kratos reads it, in `system`: the project's values,
     water's where it gives none (null or undefined). `gravity` is the project's
     gravity_acceleration in m/s2: the density is the specific weight over it. */
  function water(system, specificWeight, bulkModulus, viscosity, gravity) {
    var given = function (v) { return v !== null && v !== undefined; };
    var weight = given(specificWeight) ? specificWeight
      : App.Units.fromSI(constant('WATER_SPECIFIC_WEIGHT'), 'specific weight', system);
    return {
      DENSITY_WATER: weight / App.Units.gravity(system, gravity),
      BULK_MODULUS_FLUID: given(bulkModulus) ? bulkModulus
        : App.Units.fromSI(constant('WATER_BULK_MODULUS'), 'stress', system),
      DYNAMIC_VISCOSITY: given(viscosity) ? viscosity
        : App.Units.fromSI(constant('WATER_VISCOSITY'), 'viscosity', system)
    };
  }

  /* The Biot coefficient 1 - K / K_s Kratos' coupled elements derive; 1 when the soil
     does not say enough. */
  function biot(variables) {
    var young = number(variables, 'YOUNG_MODULUS'), poisson = number(variables, 'POISSON_RATIO');
    var grains = number(variables, 'BULK_MODULUS_SOLID');
    if (young === null || poisson === null || !grains || poisson >= 0.5) return 1.0;
    return 1.0 - young / (3.0 * (1.0 - 2.0 * poisson)) / grains;
  }

  /* K0 of a normally consolidated soil: nu / (1 - nu) for a linear elastic soil, Jaky's
     1 - sin(phi) for another with a friction angle. */
  function k0(law, variables) {
    if (modelOf(law) === 'linear_elastic') {
      var poisson = number(variables, 'POISSON_RATIO');
      return poisson === null || poisson >= 1 ? null : poisson / (1.0 - poisson);
    }
    var phi = modelOf(law) === UDSM
      ? udsmParameter(variables, variables.INDEX_OF_UMAT_PHI_PARAMETER)
      : number(variables, 'GEO_FRICTION_ANGLE');
    return phi === null ? null : 1.0 - Math.sin(phi * Math.PI / 180);
  }

  /* What the export writes where a soil leaves it out, in `system`, in the order it
     derives them (core/model/soil_models.py `derived`). */
  function derived(law, variables, waterVariables, system, flow) {
    variables = variables || {};
    var out = {};
    function given(name) { return has(variables, name) ? variables[name] : out[name]; }
    function put(name, value) {
      if (!has(variables, name) && value !== null && value !== undefined) out[name] = value;
    }
    function both() { return Object.assign({}, variables, out); }
    put('GEO_DRAINAGE_TYPE', 'CONSTANT_PW_FIELD');
    put('BULK_MODULUS_SOLID', App.Units.fromSI(constant('BULK_MODULUS_SOLID'), 'stress', system));
    var drainage = given('GEO_DRAINAGE_TYPE');
    if (drainage === 'FULLY_COUPLED' || flow) {
      put('PERMEABILITY_XX', App.Units.fromSI(constant('PERMEABILITY'), 'permeability', system));
    }
    var kappa = given('PERMEABILITY_XX');
    put('PERMEABILITY_YY', typeof kappa === 'number' && isFinite(kappa) ? kappa : null);
    if (has(variables, 'RETENTION_LAW') &&
        table().unsaturated.indexOf(variables.RETENTION_LAW) >= 0) {
      put('MINIMUM_RELATIVE_PERMEABILITY', constant('MINIMUM_RELATIVE_PERMEABILITY'));
    }
    if (variables.RETENTION_LAW === 'VanGenuchtenLaw') {
      put('VAN_GENUCHTEN_GL', constant('VAN_GENUCHTEN_GL'));
    }
    if (drainage === 'FULLY_COUPLED' || flow) {
      put('BIOT_COEFFICIENT', biot(both()));
    }
    var hardening = has(variables, 'GEO_COULOMB_HARDENING_TYPE')
      ? String(variables.GEO_COULOMB_HARDENING_TYPE) : 'None';
    if (modelOf(law) === 'mohr_coulomb' && hardening.toLowerCase() === 'linear') {
      table().vectors.forEach(function (name) { put(name, 0.0); });
    }
    put('K0_NC', k0(law, variables));
    return out;
  }

  /* What follows from a soil's numbers, in `system`: its unit weight dry and saturated
     and, where its permeability is listed, the Darcy conductivity it makes
     (core/model/soil_models.py `computed`). Nothing of these is written. */
  function computed(law, variables, waterVariables, system, flow, gravity) {
    variables = variables || {};
    var every = Object.assign({}, derived(law, variables, waterVariables, system, flow), variables);
    var g = App.Units.gravity(system, gravity);
    var gammaW = waterVariables.DENSITY_WATER * g;
    var out = {};
    var density = number(every, 'DENSITY_SOLID'), porosity = number(every, 'POROSITY');
    if (density !== null && porosity !== null) {
      out.UNIT_WEIGHT_DRY = (1.0 - porosity) * density * g;
      out.UNIT_WEIGHT_SATURATED = out.UNIT_WEIGHT_DRY + porosity * gammaW;
    }
    var listed = shown(modelOf(law), variables, flow).map(function (p) { return p.name; });
    ['XX', 'YY'].forEach(function (axis) {
      var kappa = number(every, 'PERMEABILITY_' + axis);
      if (listed.indexOf('PERMEABILITY_' + axis) >= 0 && kappa !== null) {
        out['HYDRAULIC_CONDUCTIVITY_' + axis] = kappa * gammaW / waterVariables.DYNAMIC_VISCOSITY;
      }
    });
    return out;
  }

  /* name -> { label, quantity, group } of what `computed` gives. */
  function computedInfo() { return table().computed; }

  /* `value` as Python's `{:.6g}` writes it, so both sides refuse in the same words. */
  function significant(value) {
    if (value === 0) return '0';
    var exponent = Number(value.toExponential(5).split('e')[1]);
    if (exponent < -4 || exponent >= 6) {
      var parts = value.toExponential(5).split('e');
      var digits = trim(parts[0]);
      var power = Math.abs(exponent) < 10 ? '0' + Math.abs(exponent) : String(Math.abs(exponent));
      return digits + 'e' + (exponent < 0 ? '-' : '+') + power;
    }
    return trim(value.toFixed(5 - exponent));
  }

  function trim(text) { return text.indexOf('.') < 0 ? text : text.replace(/\.?0+$/, ''); }

  /* Why Kratos would refuse the soil, beyond a missing variable. */
  function problem(name, variables) {
    variables = variables || {};
    if (modelOf(name) === UDSM) return udsmProblem(variables);
    if (modelOf(name) !== 'mohr_coulomb') return null;
    var phi = number(variables, 'GEO_FRICTION_ANGLE'), psi = number(variables, 'GEO_DILATANCY_ANGLE');
    var cohesion = number(variables, 'GEO_COHESION'), tension = number(variables, 'GEO_TENSILE_STRENGTH');
    if (phi !== null && !(phi < 90)) return 'GEO_FRICTION_ANGLE must be below 90 degrees.';
    var hardening = variables.GEO_COULOMB_HARDENING_TYPE;
    if (String(hardening === undefined ? 'None' : hardening).toLowerCase() !== 'none') {
      var negative = table().vectors.filter(function (n) {
        var slope = number(variables, n);
        return slope !== null && slope < 0;
      })[0];
      if (negative) return negative + ' cannot be negative.';
    }
    if (phi !== null && psi !== null && psi > phi) {
      return 'GEO_DILATANCY_ANGLE cannot be larger than GEO_FRICTION_ANGLE.';
    }
    var cutOff = variables.GEO_ENABLE_TENSION_CUT_OFF;
    if ((cutOff === true || (cutOff === undefined && tension !== null)) &&
        tension !== null && cohesion !== null && phi !== null && phi > 0) {
      var limit = cohesion / Math.tan(phi * Math.PI / 180);
      if (tension > limit * (1 + 1e-12)) {
        return 'GEO_TENSILE_STRENGTH cannot be larger than GEO_COHESION / ' +
               'tan(GEO_FRICTION_ANGLE) = ' + significant(limit) + '.';
      }
    }
    return null;
  }

  return { OTHER: OTHER, UDSM: UDSM, order: function () { return table().order.slice(); },
           udsmModels: udsmModels, udsmModel: udsmModel, udsmById: udsmById,
           udsmDefault: udsmDefault, udsmChoose: udsmChoose, udsmParameter: udsmParameter,
           udsmProblem: udsmProblem, udsmUnit: udsmUnit, reads: reads,
           modelOf: modelOf, label: label, law: law, lawIn: lawIn, parameters: parameters,
           find: find, unread: unread, freshColor: freshColor, shown: shown, groups: groups, required: required, fill: fill,
           defaultIn: defaultIn, defaultsSI: defaultsSI, filledNote: filledNote,
           missing: missing, fillChoice: fillChoice, blankSI: blankSI,
           problem: problem, water: water, biot: biot,
           k0: k0, derived: derived, computed: computed, computedInfo: computedInfo,
           WATER: ['DENSITY_WATER', 'BULK_MODULUS_FLUID', 'DYNAMIC_VISCOSITY'] };
})();
