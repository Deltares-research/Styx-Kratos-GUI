/* ══════════════════════════════════════════════════════════════════
   soil-models.js — the soil models a material can be.

   The material window offers a soil model first -- linear elastic or Mohr-Coulomb --
   and lists what that model's law reads: its parameters in groups, each with the value
   a new soil starts from, the text values Kratos accepts for a choice, and when it is
   listed at all (a tensile strength only with the tension cut-off on). A law no model
   is, is "Other": the user's own, written as typed.

   The table is the server's (core/model/soil_models.py), generated into
   soil-model-table.js. These are the server's functions over it, in the same words;
   tests/test_draft_parity.py holds the two to the same answers. No DOM: runs headless.
   ══════════════════════════════════════════════════════════════════ */

App.SoilModels = (function () {
  'use strict';

  function table() { return App.SOIL_MODEL_TABLE; }
  function models() { return table().models; }

  var OTHER = 'other';

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

  function holds(p, variables, model) {
    if (!p.when) return true;
    var other = parameters(model).filter(function (q) { return q.name === p.when.name; })[0];
    var value = Object.prototype.hasOwnProperty.call(variables, p.when.name)
      ? variables[p.when.name] : (other && other.absent !== undefined ? other.absent : null);
    return p.when.values.some(function (v) { return v === value; });
  }

  /* The parameters the window lists for a soil of `model` holding `variables`. */
  function shown(model, variables) {
    return parameters(model).filter(function (p) { return holds(p, variables || {}, model); });
  }

  /* Its groups, each with the parameters shown in it; an empty group is left out. */
  function groups(model, variables) {
    var m = models()[model];
    if (!m) return [];
    return m.groups.map(function (g) {
      return { title: g.title, parameters: g.parameters.filter(function (p) {
        return holds(p, variables || {}, model);
      }) };
    }).filter(function (g) { return g.parameters.length; });
  }

  /* What the law `name` cannot run without, for a soil holding `variables`. */
  function required(name, variables) {
    return shown(modelOf(name), variables).filter(function (p) { return p.required; })
      .map(function (p) { return p.name; });
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
  function fill(beforeLaw, before, afterLaw, after, system, skip) {
    var model = modelOf(afterLaw);
    var old = [];
    if (beforeLaw && modelOf(beforeLaw) === model) {
      old = shown(model, before).map(function (p) { return p.name; });
    }
    skip = skip || [];
    var filled = [];
    for (;;) {
      var next = shown(model, after).filter(function (p) {
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

  function filledNote(model, names) {
    if (!names.length) return null;
    return 'Filled in from the ' + label(model) + ' defaults: ' + names.join(', ') + '.';
  }

  function number(variables, name) {
    var v = variables[name];
    return typeof v === 'number' && isFinite(v) ? v : null;
  }

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
    if (modelOf(name) !== 'mohr_coulomb') return null;
    variables = variables || {};
    var phi = number(variables, 'GEO_FRICTION_ANGLE'), psi = number(variables, 'GEO_DILATANCY_ANGLE');
    var cohesion = number(variables, 'GEO_COHESION'), tension = number(variables, 'GEO_TENSILE_STRENGTH');
    if (phi !== null && !(phi < 90)) return 'GEO_FRICTION_ANGLE must be below 90 degrees.';
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

  return { OTHER: OTHER, order: function () { return table().order.slice(); },
           modelOf: modelOf, label: label, law: law, lawIn: lawIn, parameters: parameters,
           find: find, shown: shown, groups: groups, required: required, fill: fill,
           defaultIn: defaultIn, defaultsSI: defaultsSI, filledNote: filledNote,
           problem: problem };
})();
