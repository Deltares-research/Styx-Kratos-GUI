/* ══════════════════════════════════════════════════════════════════
   convergence-plot.js — how the solver converged, drawn from the run's log.

   Kratos prints the relative and the absolute residual of every nonlinear iteration.
   The server reads them back (`core/results/convergence.py`, route
   `/api/results/runs/<run>/convergence`) for a finished run or one that is still
   running; this module turns that data into the figure, the status words and the CSV.
   The window that shows it, live during Calculate, is `convergence-window.js`.

   The look is that of the ConvergencePlotter in Deltares' FEA-Tools: two panels that
   share the iteration axis, the relative residual above the absolute one, on a log
   scale, a dashed line for the target, a green X where the criterion was met, grey
   bands for the stages and thin lines where a step starts. When Kratos printed the
   fraction of unbalance (only its load stepping scheme does), a red line shows it on a
   second axis, 0 to 1, on the right of both panels. It adds a red mark where a step
   reached the iteration limit or was cut back, and a tooltip on every dot. A dot is
   drawn for every iteration, because many stages have only one.

   A stage chooses its own convergence criterion, and Kratos prints which one it checks:
   the residual, the displacement change or the water pressure change. Each has its own
   colour and legend entry, and the axes name it when the whole run has one. The
   iteration axis counts over the whole run, as the original's does, and says so.

   The figure shows every stage, or one stage alone (the window's slider): with many
   stages, the early ones are too narrow to read. Its numbers stay those of the run.

   ── The command line is the feature ──────────────────────────────────────

       results convergence                    in the Convergence window: the run Kratos
                                              is working on, else the open run, else
                                              the newest run
       results convergence stage N | WORDS | all
                                              the same, showing one stage alone (its
                                              number or words of its name), or all
       results convergence csv | svg | png | pdf
                                              the numbers, or the figure, as a file: of
                                              the run in the Convergence window while
                                              it is open (its Save button runs these),
                                              else of the run chosen as above; of the
                                              stage shown alone, if one is

   `kratos-cli results convergence RUN` prints the same data as a table, its `--stage`
   is `stage` here, and its `--csv` writes the same file as `csv` here
   (`tests/test_convergence_parity.py`).

   ── Why there is no DOM in here ──────────────────────────────────────────

   The same reason as results-plot.js: `frontend/tests/run_headless.py` can execute it.
   The figure is an SVG string, built and tested here, and only shown by the window.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.ConvergencePlot = (function () {

  var ROOT = '/api/results/runs';

  /* The figure, in SVG units: two panels of the same height, one above the other.
     `right` is the margin on the right; `fraction` is that margin when the second axis,
     the fraction of unbalance, needs room for its numbers and its name. `panel` is the
     height of a panel in a saved figure, and the least one the window draws. */
  var FIG = { width: 560, left: 64, right: 18, fraction: 44, top: 30, panel: 170, gap: 14,
              bottom: 38, legend: 18 };
  var LINE = '#1f77b4';      // matplotlib's first colour, the original's residual line
  /* What each criterion measures, in words, and the colour of its line: matplotlib's
     first colours, the residual's the original's. */
  var CRITERIA = {
    residual: { words: 'residual', colour: LINE },
    displacement: { words: 'displacement change', colour: '#ff7f0e' },
    water_pressure: { words: 'water pressure change', colour: '#17becf' }
  };
  var TARGET = '#222';
  var MET = '#2ca02c';
  var EVENT = '#d62728';
  var STEP = '#9a9a9a';
  var BANDS = ['#ececec', '#dcdcdc'];
  var GRID = '#e4e4e4';
  var FRAME = '#444';
  var INK = '#222';
  var CHAR = 5.6;            // the width of one character of the 10-unit font, roughly

  var view = { run: null, data: null, stage: null };
  var listeners = [];

  function log(kind, line) {
    if (App.Command && App.Command[kind]) App.Command[kind](line);
  }

  function fail(error) {
    log('err', (error && error.message) || String(error));
    return null;
  }

  /* ── State ────────────────────────────────────────────────────────────── */

  /* `stage` is the index of the stage shown alone, or null for all of them. */
  function state() { return { run: view.run, data: view.data, stage: view.stage }; }

  function forget() {
    view = { run: null, data: null, stage: null };
    changed({});
  }

  /* The stage shown alone stays while the same run is shown and still has it. */
  function keep(run, data) {
    var stage = run === view.run && stageNamed(data, view.stage) ? view.stage : null;
    view = { run: run, data: data, stage: stage };
  }

  /* Show stage `index` alone, or every stage with null. */
  function setStage(index) {
    view.stage = index !== null && index !== undefined && stageNamed(view.data, index)
      ? index : null;
    changed({});
  }

  /* `event.open` asks for the window to open (the command); every event also means
     "redraw from `state()`". */
  function onChange(listener) {
    if (typeof listener === 'function') listeners.push(listener);
  }

  function changed(event) {
    listeners.forEach(function (listener) {
      try { listener(event || {}); } catch (error) { /* a broken window must not stop this */ }
    });
  }

  /* ── Numbers and words ────────────────────────────────────────────────── */

  /* A value of the data: a number, or "nan", "inf" or "-inf" (JSON has none of them). */
  function finite(value) {
    return typeof value === 'number' && isFinite(value);
  }

  function format(value) {
    if (value === null || value === undefined) return '—';
    if (!finite(value)) return String(value);
    if (App.ResultsRender && App.ResultsRender.format) return App.ResultsRender.format(value);
    return String(value);
  }

  function esc(text) {
    return String(text === undefined || text === null ? '' : text)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function fixed(n) {
    return (Math.round(n * 10) / 10).toFixed(1);
  }

  function plural(count, noun) {
    return count + ' ' + noun + (count === 1 ? '' : 's');
  }

  /* `3_SheetPileWall_installation` as a stage row says it: `SheetPileWall installation`. */
  function tidy(name) {
    return String(name || '').replace(/^\d+_/, '').replace(/_/g, ' ');
  }

  /* `core.results.convergence.event_text`, word for word. */
  function eventText(event) {
    if (event.kind === 'cut_back') return 'step cut back, factor ' + event.factor;
    if (event.kind === 'max_iterations') {
      return 'step reached the iteration limit of ' + event.limit;
    }
    return String(event.kind);
  }

  function stageNamed(data, index) {
    if (index === null || index === undefined) return null;
    return ((data && data.stages) || []).filter(function (stage) {
      return stage.index === index;
    })[0] || null;
  }

  /* The criterion of an iteration, as `CRITERIA` has it. An iteration whose line did
     not name one is the residual's, as the original took every line to be. */
  function criterionKey(it) {
    return (it && it.criterion) || 'residual';
  }

  function criterion(key) {
    return CRITERIA[key] || { words: String(key).replace(/_/g, ' ').toLowerCase() + ' change',
                              colour: '#7f7f7f' };
  }

  /* The criteria these iterations were checked on, in the order they came. */
  function criteriaIn(iterations) {
    var seen = [];
    (iterations || []).forEach(function (it) {
      var key = criterionKey(it);
      if (seen.indexOf(key) === -1) seen.push(key);
    });
    return seen;
  }

  /* What the axes measure: the criterion's words when the run has one, else "value". */
  function measured(data) {
    var keys = criteriaIn(data && data.iterations);
    return keys.length > 1 ? 'value' : criterion(keys[0] || 'residual').words;
  }

  /* "stage 3 of 7, SheetPileWall installation": the stage Kratos is in, or was last in. */
  function stageText(data) {
    var stage = data && data.stage;
    if (!stage) {
      var stages = (data && data.stages) || [];
      stage = stages.length ? stages[stages.length - 1] : null;
    }
    if (!stage || stage.index === null || stage.index === undefined) return '';
    return 'stage ' + stage.index + (stage.of ? ' of ' + stage.of : '')
           + (stage.name ? ', ' + tidy(stage.name) : '');
  }

  /* The last iteration in words and numbers, so the plot is not the only way to read it.
     Its number is the run's, as on the iteration axis; its place in the step follows:
     "Iteration 57 (stage 3, step 2, iteration 5 of the step). Relative residual 3.20e-3
     (target 1.00e-4). Absolute residual ...". */
  function lastText(data) {
    var iterations = (data && data.iterations) || [];
    if (!iterations.length) return '';
    var last = iterations[iterations.length - 1];
    var inStep = iterations.filter(function (it) {
      return it.stage === last.stage && it.step === last.step;
    }).length;
    var place = [];
    if (last.stage !== null && last.stage !== undefined) place.push('stage ' + last.stage);
    if (last.step) place.push('step ' + last.step + ', iteration ' + inStep + ' of the step');
    var words = criterion(criterionKey(last)).words;
    return 'Iteration ' + iterations.length + (place.length ? ' (' + place.join(', ') + ')' : '')
           + '. Relative ' + words + ' ' + format(last.relative) + ' (target '
           + format(last.relative_target) + '). Absolute ' + words + ' '
           + format(last.absolute) + ' (target ' + format(last.absolute_target) + ').'
           + (last.met ? ' Criterion met.' : '');
  }

  var NO_RESIDUALS = 'Kratos printed no residuals. Is the solver\'s echo_level 0 in this deck?';

  /* ── Axes ─────────────────────────────────────────────────────────────── */

  /* The decades a log axis spans: every finite, positive residual and target in it.
     A value that is a whole decade (a target of 1e-3) gets one more decade beyond it,
     so it is not drawn on the frame; and a decade either side when all are one value. */
  function decades(values) {
    var lo = Infinity, hi = -Infinity;
    values.forEach(function (v) {
      if (finite(v) && v > 0) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
    });
    if (lo === Infinity) return { lo: -12, hi: 0 };
    var a = Math.floor(Math.log10(lo) - 0.05), b = Math.ceil(Math.log10(hi) + 0.05);
    if (b <= a) { a -= 1; b += 1; }
    return { lo: a, hi: b };
  }

  function decadeLabel(power) {
    if (power === 0) return '1';
    if (power === 1) return '10';
    return '1e' + power;
  }

  /* Whole iterations, about `target` of them, on round numbers, from iteration `first`
     (1 when left out) to `first + count - 1`. `first` gets a tick too, unless a round
     one is so close the numbers would touch. */
  function iterationTicks(count, target, first) {
    first = first || 1;
    if (count <= 1) return [first];
    var raw = count / (target || 8);
    var magnitude = Math.pow(10, Math.floor(Math.log10(raw)));
    var step = [1, 2, 5, 10].map(function (n) { return n * magnitude; })
      .filter(function (s) { return s >= raw; })[0] || 10 * magnitude;
    step = Math.max(1, Math.round(step));
    var out = [];
    for (var k = Math.ceil(first / step) * step; k < first + count; k += step) out.push(k);
    if (!out.length || (out[0] !== first && out[0] - first >= step / 2)) out.unshift(first);
    return out;
  }

  /* ── The figure ───────────────────────────────────────────────────────── */

  /* The fractions of unbalance worth drawing: those that are a number. */
  function fractionsOf(data) {
    return ((data && data.fractions) || []).filter(function (f) { return finite(f.value); });
  }

  /* The right edge of the panels: further in when the second axis is drawn. */
  function rightEdge(data) {
    return FIG.width - (fractionsOf(data).length ? FIG.fraction : FIG.right);
  }

  /* An X, the original's 'x' marker, centred on (x, y), `half` wide either way. */
  function cross(x, y, half) {
    return 'M' + fixed(x - half) + ',' + fixed(y - half) + 'l' + fixed(2 * half) + ','
           + fixed(2 * half) + 'm0,' + fixed(-2 * half) + 'l' + fixed(-2 * half) + ','
           + fixed(2 * half);
  }

  /* The part of `data` that is stage `index`, with every `at` counted from the stage's
     first iteration, and `offset`, the number of iterations before it: what the figure
     draws when it shows that stage alone. All of `data` when there is no such stage.
     The same split as `stage_rows` in `core/results/convergence.py`: a step at the next
     stage's start is that stage's, and an event belongs to the iteration before it. */
  function windowed(data, index) {
    var stages = data.stages || [];
    var order = -1;
    stages.forEach(function (stage, i) { if (order < 0 && stage.index === index) order = i; });
    if (index === null || index === undefined || order < 0) return { data: data, offset: 0 };
    var iterations = data.iterations || [];
    var from = stages[order].at;
    var last = order + 1 === stages.length;
    var to = last ? iterations.length : stages[order + 1].at;
    function moved(list, keep) {
      return (list || []).filter(keep).map(function (item) {
        return Object.assign({}, item, { at: item.at - from });
      });
    }
    function after(item) { return item.at > from && item.at <= to; }
    return { offset: from, data: Object.assign({}, data, {
      iterations: iterations.slice(from, to),
      stages: [Object.assign({}, stages[order], { at: 0 })],
      steps: moved(data.steps, function (step) {
        return step.at >= from && (step.at < to || last);
      }),
      events: moved(data.events, after),
      fractions: moved(data.fractions, after)
    }) };
  }

  /* Where each stage's band runs, in iterations: from just before its first iteration
     to just after its last. A stage still running reaches the end of the axis. */
  function bands(data, count) {
    var stages = data.stages || [];
    return stages.map(function (stage, i) {
      var end = i + 1 < stages.length ? stages[i + 1].at : count;
      return { stage: stage, from: stage.at + 0.5, to: end + 0.5,
               iterations: (data.iterations || []).slice(stage.at, end) };
    });
  }

  function tooltip(data, it, n) {
    var stage = it.stage !== null && it.stage !== undefined ? stageNamed(data, it.stage) : null;
    var words = criterion(criterionKey(it)).words;
    var place = 'Iteration ' + n
              + (stage ? ' — stage ' + stage.index + (stage.name ? ' ' + tidy(stage.name) : '')
                 : '')
              + (it.step ? ', step ' + it.step : '');
    var lines = [place,
                 'Relative ' + words + ' ' + format(it.relative) + ' (target '
                 + format(it.relative_target) + ')',
                 'Absolute ' + words + ' ' + format(it.absolute) + ' (target '
                 + format(it.absolute_target) + ')'];
    if (it.met) lines.push('Criterion met');
    (data.events || []).forEach(function (event) {
      if (event.at === n) lines.push(eventText(event));
    });
    return lines.join('\n');
  }

  /* One panel: `key` is 'relative' or 'absolute'. `fig` is the figure's layout (`svg`):
     the data it draws, `sx`, `count`, `offset`, the panel height and the right edge. */
  function panel(fig, key, top, lastPanel) {
    var data = fig.data, sx = fig.sx, count = fig.count, offset = fig.offset;
    var left = FIG.left, right = fig.right, height = fig.panel, bottom = top + height;
    var iterations = data.iterations || [];
    var out = ['<g class="cp-panel cp-' + key + '">'];
    var range = decades(iterations.map(function (it) { return it[key]; })
      .concat(iterations.map(function (it) { return it[key + '_target']; })));
    function sy(v) {
      if (!finite(v)) return top;                      // nan and inf: on the top edge
      if (v <= 0) return bottom;                       // zero: on the bottom edge
      var t = (Math.log10(v) - range.lo) / (range.hi - range.lo);
      return bottom - Math.max(0, Math.min(1, t)) * (bottom - top);
    }

    // The stage bands and the step lines, under everything else.
    bands(data, count).forEach(function (band, i) {
      var x0 = Math.max(left, sx(band.from)), x1 = Math.min(right, sx(band.to));
      if (x1 > x0) {
        out.push('<rect class="cp-band" x="' + fixed(x0) + '" y="' + top + '" width="'
                 + fixed(x1 - x0) + '" height="' + height + '" fill="'
                 + BANDS[((band.stage.index || i + 1) - 1) % BANDS.length] + '"/>');
      }
    });
    var starts = {};
    (data.stages || []).forEach(function (stage) { starts[stage.at] = true; });
    var steps = (data.steps || []).filter(function (step) {
      return step.at > 0 && step.at < count && !starts[step.at];
    });
    if (steps.length <= (right - left) / 3) {
      steps.forEach(function (step) {
        var x = fixed(sx(step.at + 0.5));
        out.push('<line class="cp-step" x1="' + x + '" y1="' + top + '" x2="' + x + '" y2="'
                 + bottom + '" stroke="' + STEP + '" stroke-dasharray="3,3"'
                 + ' stroke-width="0.7"/>');
      });
    }

    // The decades.
    // At most about six labelled decades, on round powers: every 1, 2, 3, 5, 10, ...
    var span = range.hi - range.lo;
    var every = [1, 2, 3, 5, 10, 20, 25, 50, 100, 200].filter(function (n) {
      return span / n <= 6;
    })[0] || 500;
    for (var p = range.lo; p <= range.hi; p++) {
      var y = fixed(sy(Math.pow(10, p)));
      if (p % every === 0) {
        out.push('<line class="cp-grid" x1="' + left + '" y1="' + y + '" x2="' + right
                 + '" y2="' + y + '" stroke="' + GRID + '"/>');
        out.push('<text class="cp-tick" x="' + (left - 4) + '" y="' + y
                 + '" dy="0.35em" text-anchor="end">' + decadeLabel(p) + '</text>');
      }
    }
    out.push('<text class="cp-ylabel" transform="translate(14,' + fixed((top + bottom) / 2)
             + ') rotate(-90)" text-anchor="middle">'
             + (key === 'relative' ? 'Relative ' : 'Absolute ') + measured(data) + '</text>');

    // The target, a dashed step line: each iteration's own target across its width.
    if (iterations.length) {
      var target = [];
      iterations.forEach(function (it, i) {
        if (!finite(it[key + '_target'])) return;
        var ty = fixed(sy(it[key + '_target']));
        target.push(fixed(sx(i + 0.5)) + ',' + ty, fixed(sx(i + 1.5)) + ',' + ty);
      });
      if (target.length) {
        out.push('<polyline class="cp-target" points="' + target.join(' ')
                 + '" fill="none" stroke="' + TARGET + '" stroke-dasharray="5,3"'
                 + ' stroke-width="1"/>');
      }
    }

    // The residuals: one line through the whole run, across steps and stages, as the
    // FEA-Tools plotter draws it. It breaks at a value that is not finite, and where the
    // criterion changes: a residual and a displacement change are not one quantity.
    var segment = [], lines = [], was = null;
    function flush() {
      if (segment.length > 1) lines.push({ points: segment, key: was });
      segment = [];
    }
    iterations.forEach(function (it, i) {
      var now = criterionKey(it);
      if (!finite(it[key]) || now !== was) flush();
      was = now;
      if (finite(it[key])) segment.push(fixed(sx(i + 1)) + ',' + fixed(sy(it[key])));
    });
    flush();
    lines.forEach(function (line) {
      out.push('<polyline class="cp-line" points="' + line.points.join(' ') + '" fill="none"'
               + ' stroke="' + criterion(line.key).colour + '" stroke-width="1.3"'
               + ' stroke-linejoin="round"/>');
    });

    // A dot for every iteration, with its tooltip; a green X over it where the criterion
    // was met; a red cross on the top edge for a value that is not a number.
    var r = iterations.length > 400 ? 1.4 : iterations.length > 100 ? 2 : 2.6;
    iterations.forEach(function (it, i) {
      var x = fixed(sx(i + 1)), cy = fixed(sy(it[key]));
      var tip = '<title>' + esc(tooltip(data, it, i + 1 + offset)) + '</title>';
      if (!finite(it[key])) {
        out.push('<path class="cp-nan" d="M' + fixed(sx(i + 1) - 3) + ',' + fixed(top + 1)
                 + 'l6,6m0,-6l-6,6" stroke="' + EVENT + '" stroke-width="1.6" fill="none">'
                 + tip + '</path>');
        return;
      }
      out.push('<circle class="cp-dot" cx="' + x + '" cy="' + cy + '" r="' + r + '" fill="'
               + criterion(criterionKey(it)).colour + '">' + tip + '</circle>');
      if (it.met) {
        // Over the dot, so it shows; the dot under it keeps the tooltip.
        out.push('<path class="cp-met" d="' + cross(sx(i + 1), sy(it[key]), r + 1.8)
                 + '" stroke="' + MET + '" stroke-width="1.6" fill="none"'
                 + ' pointer-events="none"/>');
      }
    });

    // A red mark on the top edge where a step reached the limit or was cut back.
    var marked = {};
    (data.events || []).forEach(function (event) {
      var n = Math.max(1, Math.min(count, event.at));
      (marked[n] = marked[n] || []).push(eventText(event));
    });
    Object.keys(marked).forEach(function (n) {
      var x = sx(Number(n));
      out.push('<path class="cp-event" d="M' + fixed(x - 4) + ',' + top + 'h8l-4,7z" fill="'
               + EVENT + '"><title>' + esc('After iteration ' + (Number(n) + offset) + ': '
               + marked[n].join('; ')) + '</title></path>');
    });

    // The fraction of unbalance, when Kratos printed one: a red line with an x at each
    // value, on a second axis from 0 to 1 on the right, as the original draws it. Kratos
    // prints it once a step, after the step's last iteration, so that is where it sits.
    var fractions = fractionsOf(data);
    if (fractions.length) {
      var fy = function (v) { return bottom - Math.max(0, Math.min(1, v)) * (bottom - top); };
      var at = function (f) { return Math.max(1, Math.min(count, f.at)); };
      out.push('<g class="cp-fraction">');
      if (fractions.length > 1) {
        out.push('<polyline class="cp-fraction-line" points="' + fractions.map(function (f) {
          return fixed(sx(at(f))) + ',' + fixed(fy(f.value));
        }).join(' ') + '" fill="none" stroke="' + EVENT + '" stroke-width="1.1"/>');
      }
      var half = fractions.length > 200 ? 1.8 : 2.6;
      fractions.forEach(function (f) {
        out.push('<path class="cp-fraction-mark" d="' + cross(sx(at(f)), fy(f.value), half)
                 + '" stroke="' + EVENT + '" stroke-width="1.2" fill="none"><title>'
                 + esc('Fraction of unbalance ' + format(f.value) + ', after iteration '
                       + (at(f) + offset)) + '</title></path>');
      });
      [0, 0.2, 0.4, 0.6, 0.8, 1].forEach(function (v) {
        var ty = fixed(fy(v));
        out.push('<line x1="' + right + '" y1="' + ty + '" x2="' + (right + 3) + '" y2="' + ty
                 + '" stroke="' + EVENT + '"/>');
        out.push('<text class="cp-tick cp-fraction-tick" x="' + (right + 5) + '" y="' + ty
                 + '" dy="0.35em" fill="' + EVENT + '">' + v + '</text>');
      });
      out.push('<text class="cp-ylabel cp-fraction-label" transform="translate('
               + (FIG.width - 7) + ',' + fixed((top + bottom) / 2) + ') rotate(90)"'
               + ' text-anchor="middle" fill="' + EVENT + '">Fraction of unbalance</text>');
      out.push('</g>');
    }

    out.push('<rect x="' + left + '" y="' + top + '" width="' + (right - left) + '" height="'
             + height + '" fill="none" stroke="' + FRAME + '"/>');
    if (fractions.length) {
      out.push('<line class="cp-fraction-spine" x1="' + right + '" y1="' + top + '" x2="'
               + right + '" y2="' + bottom + '" stroke="' + EVENT + '"/>');
    }

    // The iteration axis: tick marks on both panels, numbers under the lower one. The
    // numbers are the run's, also when one stage is shown alone.
    iterationTicks(count, 8, offset + 1).forEach(function (n) {
      var x = fixed(sx(n - offset));
      out.push('<line x1="' + x + '" y1="' + bottom + '" x2="' + x + '" y2="' + (bottom + 3)
               + '" stroke="' + FRAME + '"/>');
      if (lastPanel) {
        out.push('<text class="cp-tick" x="' + x + '" y="' + (bottom + 13)
                 + '" text-anchor="middle">' + n + '</text>');
      }
    });
    out.push('</g>');
    return out.join('');
  }

  /* The stage labels above the upper panel: "3 SheetPileWall installation" where it
     fits in its band, "3" where only that fits, nothing where not even that does. The
     tooltip also names the stage's criterion. */
  function stageLabels(fig) {
    var out = [];
    bands(fig.data, fig.count).forEach(function (band) {
      var x0 = Math.max(FIG.left, fig.sx(band.from)), x1 = Math.min(fig.right, fig.sx(band.to));
      var room = x1 - x0 - 4;
      var stage = band.stage;
      var number = stage.index === null || stage.index === undefined ? '' : String(stage.index);
      var full = (number + ' ' + tidy(stage.name)).trim();
      var text = full.length * CHAR <= room ? full : number.length * CHAR <= room ? number : '';
      if (!text) return;
      var keys = criteriaIn(band.iterations);
      var tip = full + (keys.length ? ' — ' + keys.map(function (key) {
        return criterion(key).words;
      }).join(' and ') + ' criterion' : '');
      out.push('<text class="cp-stage" x="' + fixed((x0 + x1) / 2) + '" y="' + (FIG.top - 6)
               + '" text-anchor="middle"><title>' + esc(tip) + '</title>' + esc(text)
               + '</text>');
    });
    return out.join('');
  }

  /* The legend's entries, each `width` wide with its `draw(x)`: a line per criterion the
     figure shows, then the target, the met criterion, the events, the stages and, when
     Kratos printed it, the fraction of unbalance. */
  function legendItems(data) {
    function entry(text, icon, colour) {
      return { width: 20 + text.length * CHAR + 12, draw: function (x) {
        return icon(x) + '<text x="' + fixed(x + 20) + '" y="0" dy="0.35em"'
               + (colour ? ' fill="' + colour + '"' : '') + '>' + esc(text) + '</text>';
      } };
    }
    var keys = criteriaIn(data.iterations);
    var items = (keys.length ? keys : ['residual']).map(function (key) {
      var colour = criterion(key).colour;
      return entry(criterion(key).words, function (x) {
        return '<line x1="' + fixed(x) + '" y1="0" x2="' + fixed(x + 16) + '" y2="0" stroke="'
               + colour + '" stroke-width="1.3"/><circle cx="' + fixed(x + 8)
               + '" cy="0" r="2.4" fill="' + colour + '"/>';
      });
    });
    items.push(entry('target', function (x) {
      return '<line x1="' + fixed(x) + '" y1="0" x2="' + fixed(x + 16) + '" y2="0" stroke="'
             + TARGET + '" stroke-dasharray="5,3"/>';
    }));
    items.push(entry('criterion met', function (x) {
      return '<circle cx="' + fixed(x + 8) + '" cy="0" r="2.4" fill="' + LINE + '"/><path d="'
             + cross(x + 8, 0, 4.2) + '" stroke="' + MET + '" stroke-width="1.6" fill="none"/>';
    }));
    items.push(entry('iteration limit or cut-back', function (x) {
      return '<path d="M' + fixed(x + 4) + ',-4h8l-4,7z" fill="' + EVENT + '"/>';
    }));
    items.push(entry('stage', function (x) {
      return '<rect x="' + fixed(x + 1) + '" y="-5" width="14" height="10" fill="' + BANDS[1]
             + '"/>';
    }));
    if (fractionsOf(data).length) {
      items.push(entry('fraction of unbalance (right axis)', function (x) {
        return '<line x1="' + fixed(x) + '" y1="0" x2="' + fixed(x + 16) + '" y2="0" stroke="'
               + EVENT + '" stroke-width="1.1"/><path d="' + cross(x + 8, 0, 2.6)
               + '" stroke="' + EVENT + '" stroke-width="1.2" fill="none"/>';
      }, EVENT));
    }
    return items;
  }

  /* The legend's entries in rows that fit the figure's width, each entry with its `x`. */
  function legendRows(data) {
    var room = FIG.width - FIG.left - 8, rows = [[]], x = 0;
    legendItems(data).forEach(function (item) {
      if (x > 0 && x + item.width - 12 > room) { rows.push([]); x = 0; }
      rows[rows.length - 1].push({ item: item, x: x });
      x += item.width;
    });
    return rows;
  }

  function legend(rows, y) {
    var out = ['<g class="cp-legend" transform="translate(' + FIG.left + ',' + y + ')">'];
    rows.forEach(function (row, i) {
      out.push('<g class="cp-legend-row" transform="translate(0,' + i * FIG.legend + ')">');
      row.forEach(function (placed) { out.push(placed.item.draw(placed.x)); });
      out.push('</g>');
    });
    out.push('</g>');
    return out.join('');
  }

  /* The whole figure, as a string: shown by the window, saved as a file. `options`:
     `stage`, the index of the stage to show alone (all when left out); `height`, the
     height to fill, in the figure's units (the window's shape: 560 wide), which makes
     the panels taller, never shorter than a saved figure's. */
  function svg(data, options) {
    data = data || {};
    options = options || {};
    var part = windowed(data, options.stage);
    var shown = part.data;
    var iterations = shown.iterations || [];
    var count = Math.max(1, iterations.length);
    var left = FIG.left, right = rightEdge(shown);
    function sx(n) { return left + (n - 0.5) / count * (right - left); }
    var rows = legendRows(shown);
    var fixedPart = FIG.top + FIG.gap + FIG.bottom + FIG.legend * rows.length;
    var panelHeight = options.height
      ? Math.max(FIG.panel, Math.floor((options.height - fixedPart) / 2)) : FIG.panel;
    var h = fixedPart + 2 * panelHeight;
    var fig = { data: shown, sx: sx, count: count, offset: part.offset, panel: panelHeight,
                right: right };
    var out = ['<svg xmlns="http://www.w3.org/2000/svg" class="cp-figure" viewBox="0 0 '
               + FIG.width + ' ' + h + '" width="' + FIG.width + '" height="' + h
               + '" font-family="Segoe UI, Arial, sans-serif" font-size="10" fill="' + INK
               + '">'];
    out.push('<rect width="' + FIG.width + '" height="' + h + '" fill="#fff"/>');
    var upper = FIG.top, lower = FIG.top + panelHeight + FIG.gap;
    out.push(stageLabels(fig));
    out.push(panel(fig, 'relative', upper, false));
    out.push(panel(fig, 'absolute', lower, true));
    out.push('<text class="cp-xlabel" x="' + fixed((left + right) / 2) + '" y="'
             + (lower + panelHeight + 28) + '" text-anchor="middle">'
             + 'Iteration, counted over all stages</text>');
    if (!iterations.length) {
      out.push('<text class="cp-empty" x="' + fixed((left + right) / 2) + '" y="'
               + fixed(upper + panelHeight / 2) + '" text-anchor="middle" fill="#888">'
               + 'no iterations yet</text>');
    }
    out.push(legend(rows, h - FIG.legend * (rows.length - 0.5) - 2));
    out.push('</svg>');
    return out.join('');
  }

  /* ── The file ─────────────────────────────────────────────────────────── */

  var COLUMNS = ['iteration', 'stage', 'stage_name', 'step', 'time', 'cycle', 'criterion',
                 'relative', 'relative_target', 'absolute', 'absolute_target', 'met',
                 'events'];

  function cell(text) {
    var value = String(text === undefined || text === null ? '' : text);
    return /[",\n]/.test(value) ? '"' + value.replace(/"/g, '""') + '"' : value;
  }

  function value(v) {
    return v === null || v === undefined ? '' : String(v);
  }

  /* A row per iteration: `cli.terminal.tables.convergence_csv`, byte for byte. With
     `stage`, the rows of that stage only, as `--stage` gives them. */
  function csv(data, stage) {
    var names = {};
    (data.stages || []).forEach(function (entry) { names[entry.index] = entry.name; });
    var lines = [COLUMNS.join(',')];
    (data.iterations || []).forEach(function (it, i) {
      var n = i + 1;
      if (stage !== null && stage !== undefined && it.stage !== stage) return;
      var events = (data.events || []).filter(function (event) { return event.at === n; })
        .map(function (event) {
          return event.kind + ' ' + value(event.factor !== undefined ? event.factor
                                                                     : event.limit);
        }).join('; ');
      lines.push([n, value(it.stage), cell(names[it.stage]), value(it.step), value(it.time),
                  value(it.cycle), value(it.criterion), value(it.relative),
                  value(it.relative_target),
                  value(it.absolute), value(it.absolute_target), it.met ? 'yes' : 'no',
                  cell(events)].join(','));
    });
    return lines.join('\n') + '\n';
  }

  /* ── Loading ──────────────────────────────────────────────────────────── */

  /* The data of `run`, kept as the one on screen. Always a promise; null on a failure,
     which is said in the log. `quiet` leaves the log alone: the live window asks
     every second. */
  function load(run, quiet) {
    return App.Api.get(ROOT + '/' + encodeURIComponent(run) + '/convergence')
      .then(function (data) {
        keep(run, data);
        return data;
      }, function (error) { return quiet ? null : fail(error); });
  }

  /* Put `data` on screen as the run's, without asking: the window has it already. */
  function show(run, data, event) {
    keep(run, data);
    changed(event || {});
  }

  /* The run the command means: the one Kratos is working on, so the window follows a
     run in progress; else the open one; else the newest on this machine. */
  function whichRun() {
    var open = App.Results && App.Results.current ? App.Results.current() : null;
    return App.Api.get('/api/calculate/status').then(function (status) {
      return status && status.run ? status.run : null;
    }, function () { return null; }).then(function (running) {
      if (running || open) return running || open;
      return App.Api.get(ROOT).then(function (answer) {
        var runs = (answer && answer.runs) || [];
        return runs.length ? runs[0].id : null;
      });
    });
  }

  function report(data) {
    var iterations = data.iterations || [];
    if (!iterations.length) {
      log('note', data.run + ': no iterations. '
                  + ((data.stages || []).length ? NO_RESIDUALS
                     : data.log ? 'Kratos did not start solving.' : 'The run has no log.'));
      return;
    }
    var stages = (data.stages || []).length;
    log('ok', data.run + ': ' + plural(iterations.length, 'iteration') + ' in '
              + plural(stages || 1, 'stage')
              + (data.running ? ' (still running)'
                 : data.failed_at ? '; stopped in stage ' + data.failed_at.index + ' of '
                                    + data.failed_at.of : '') + '.');
    log('note', '`results convergence csv` saves the numbers, `results convergence svg`, '
                + '`png` or `pdf` the figure; `results convergence stage N` shows one stage.');
  }

  /* The stage `wanted` names in `data`: its number, or words of its name, as
     `kratos-cli results convergence --stage` matches it. */
  function stageMatching(data, wanted) {
    var stages = (data && data.stages) || [];
    if (/^\d+$/.test(wanted)) return stageNamed(data, Number(wanted));
    var plain = function (text) {
      return String(text || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
    };
    var words = plain(wanted);
    return stages.filter(function (stage) {
      return stage.name && plain(stage.name).indexOf(words) !== -1;
    })[0] || null;
  }

  /* ── Saving ───────────────────────────────────────────────────────────── */

  function windowOpen() {
    var W = App.ConvergenceWindow;
    return !!(W && W.state && W.state().open);
  }

  /* What is shown is what is saved: the stage shown alone, when there is one. */
  function save(kind) {
    var data = view.data, stage = view.stage;
    var name = view.run + '_convergence' + (stage === null ? '' : '_stage_' + stage) + '.'
               + kind;
    var figure = svg(data, { stage: stage });
    if (kind === 'png' || kind === 'pdf') return App.Picture.saveFigure(figure, name, kind);
    var text = kind === 'csv' ? csv(data, stage) : figure;
    var mime = kind === 'csv' ? 'text/csv' : 'image/svg+xml';
    return App.Download.pickFile(name, mime).then(function (target) {
      if (target === App.Download.CANCELLED) {
        log('note', name + ' not saved.');
        return null;
      }
      return App.Download.write(target, name, text, mime).then(function () {
        log('ok', 'Saved ' + name + '.');
      });
    }).catch(fail);
  }

  /* ── The command ──────────────────────────────────────────────────────── */

  /* `results convergence ...`, routed here by results.js. Always a promise. */
  function command(rest) {
    var verb = String(rest || '').trim().toLowerCase();
    if (/^stage(\s|$)/.test(verb)) return chooseStage(verb.slice(5).trim());
    if (verb && verb !== 'csv' && verb !== 'svg' && verb !== 'png' && verb !== 'pdf') {
      log('err', 'No such convergence command: "' + verb + '". `results convergence` '
                 + 'shows it; `stage N` or `stage all` after it picks the stages shown; '
                 + '`csv`, `svg`, `png` or `pdf` after it saves it.');
      return Promise.resolve();
    }
    // With the Convergence window open, a file is of what it shows: its Save button and
    // the command box save the same run. Saved at once, with nothing asked first, so
    // the browser still takes it as the click's and opens its save window.
    if (verb && windowOpen()) {
      if (!view.run || !view.data) {
        log('note', 'Nothing to save yet: the Convergence window shows no run.');
        return Promise.resolve(null);
      }
      return Promise.resolve(save(verb));
    }
    return whichRun().then(function (run) {
      if (!run) {
        log('err', 'No runs yet — press Calculate (F9) and one will appear.');
        return null;
      }
      return load(run).then(function (data) {
        if (!data) return null;
        if (verb) return save(verb);
        report(data);
        changed({ open: true });
        return data;
      });
    }).catch(fail);
  }

  /* `results convergence stage N | WORDS | all`: of the run the window shows, else of
     the run `results convergence` takes, which it then shows. */
  function chooseStage(wanted) {
    var ready = windowOpen() && view.data ? Promise.resolve(view.data)
      : whichRun().then(function (run) {
        if (run) return load(run);
        log('err', 'No runs yet — press Calculate (F9) and one will appear.');
        return null;
      });
    return ready.then(function (data) {
      if (!data) return null;
      var found = null;
      if (wanted && wanted !== 'all') {
        found = stageMatching(data, wanted);
        if (!found) {
          log('err', 'In ' + view.run + ', no stage with iterations matches "' + wanted
                     + '". Its stages: ' + ((data.stages || []).map(function (stage) {
                       return (stage.index + ' ' + tidy(stage.name)).trim();
                     }).join(', ') || 'none') + '.');
          return null;
        }
      }
      view.stage = found ? found.index : null;
      log('ok', found ? 'Showing stage ' + found.index
                        + (found.name ? ', ' + tidy(found.name) : '') + ', alone.'
                      : 'Showing every stage.');
      changed(windowOpen() ? {} : { open: true });
      return data;
    }).catch(fail);
  }

  return {
    command: command, state: state, forget: forget, onChange: onChange, load: load,
    show: show, setStage: setStage, svg: svg, csv: csv, stageText: stageText,
    lastText: lastText, criterion: criterion,
    eventText: eventText, decades: decades, iterationTicks: iterationTicks,
    tidy: tidy, NO_RESIDUALS: NO_RESIDUALS, FIG: FIG
  };
})();
