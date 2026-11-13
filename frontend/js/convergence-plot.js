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

   ── The command line is the feature ──────────────────────────────────────

       results convergence                    in the Convergence window: the run Kratos
                                              is working on, else the open run, else
                                              the newest run
       results convergence csv | svg | png | pdf
                                              the numbers, or the figure, as a file

   `kratos-cli results convergence RUN` prints the same data as a table, and its
   `--csv` writes the same file as `csv` here (`tests/test_convergence_parity.py`).

   ── Why there is no DOM in here ──────────────────────────────────────────

   The same reason as results-plot.js: `frontend/tests/run_headless.py` can execute it.
   The figure is an SVG string, built and tested here, and only shown by the window.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.ConvergencePlot = (function () {

  var ROOT = '/api/results/runs';

  /* The figure, in SVG units: two panels of the same height, one above the other.
     `right` is the margin on the right; `fraction` is that margin when the second axis,
     the fraction of unbalance, needs room for its numbers and its name. */
  var FIG = { width: 560, left: 64, right: 18, fraction: 44, top: 30, panel: 150, gap: 14,
              bottom: 38, legend: 18 };
  var LINE = '#1f77b4';      // matplotlib's first colour, the original's residual line
  var TARGET = '#222';
  var MET = '#2ca02c';
  var EVENT = '#d62728';
  var STEP = '#9a9a9a';
  var BANDS = ['#ececec', '#dcdcdc'];
  var GRID = '#e4e4e4';
  var FRAME = '#444';
  var INK = '#222';
  var CHAR = 5.6;            // the width of one character of the 10-unit font, roughly

  var view = { run: null, data: null };
  var listeners = [];

  function log(kind, line) {
    if (App.Command && App.Command[kind]) App.Command[kind](line);
  }

  function fail(error) {
    log('err', (error && error.message) || String(error));
    return null;
  }

  /* ── State ────────────────────────────────────────────────────────────── */

  function state() { return { run: view.run, data: view.data }; }

  function forget() {
    view = { run: null, data: null };
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
    return (data.stages || []).filter(function (stage) { return stage.index === index; })[0]
           || null;
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

  /* The last iteration in words and numbers, so the plot is not the only way to read it:
     "Step 2, iteration 5. Relative 3.20e-3 (target 1.00e-4). Absolute ...". */
  function lastText(data) {
    var iterations = (data && data.iterations) || [];
    if (!iterations.length) return '';
    var last = iterations[iterations.length - 1];
    var inStage = iterations.filter(function (it) {
      return it.stage === last.stage && it.step === last.step;
    }).length;
    return (last.step ? 'Step ' + last.step + ', iteration ' + inStage + '. '
                      : 'Iteration ' + iterations.length + '. ')
           + 'Relative ' + format(last.relative) + ' (target ' + format(last.relative_target)
           + '). Absolute ' + format(last.absolute) + ' (target '
           + format(last.absolute_target) + ').' + (last.met ? ' Criterion met.' : '');
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

  /* Whole iterations, about `target` of them, on round numbers. */
  function iterationTicks(count, target) {
    if (count <= 1) return [1];
    var raw = count / (target || 8);
    var magnitude = Math.pow(10, Math.floor(Math.log10(raw)));
    var step = [1, 2, 5, 10].map(function (n) { return n * magnitude; })
      .filter(function (s) { return s >= raw; })[0] || 10 * magnitude;
    step = Math.max(1, Math.round(step));
    var out = [];
    for (var k = step; k <= count; k += step) out.push(k);
    if (out[0] !== 1) out.unshift(1);
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

  /* A second legend row holds the fraction of unbalance, when there is one. */
  function height(data) {
    return FIG.top + 2 * FIG.panel + FIG.gap + FIG.bottom
           + FIG.legend * (fractionsOf(data).length ? 2 : 1);
  }

  /* An X, the original's 'x' marker, centred on (x, y), `half` wide either way. */
  function cross(x, y, half) {
    return 'M' + fixed(x - half) + ',' + fixed(y - half) + 'l' + fixed(2 * half) + ','
           + fixed(2 * half) + 'm0,' + fixed(-2 * half) + 'l' + fixed(-2 * half) + ','
           + fixed(2 * half);
  }

  /* Where each stage's band runs, in iterations: from just before its first iteration
     to just after its last. A stage still running reaches the end of the axis. */
  function bands(data, count) {
    var stages = data.stages || [];
    return stages.map(function (stage, i) {
      var end = i + 1 < stages.length ? stages[i + 1].at : count;
      return { stage: stage, from: stage.at + 0.5, to: end + 0.5 };
    });
  }

  function tooltip(data, it, n) {
    var stage = it.stage !== null && it.stage !== undefined ? stageNamed(data, it.stage) : null;
    var place = 'Iteration ' + n
              + (stage ? ' — stage ' + stage.index + (stage.name ? ' ' + tidy(stage.name) : '')
                 : '')
              + (it.step ? ', step ' + it.step : '');
    var lines = [place,
                 'Relative ' + format(it.relative) + ' (target ' + format(it.relative_target) + ')',
                 'Absolute ' + format(it.absolute) + ' (target ' + format(it.absolute_target) + ')'];
    if (it.met) lines.push('Criterion met');
    (data.events || []).forEach(function (event) {
      if (event.at === n) lines.push(eventText(event));
    });
    return lines.join('\n');
  }

  /* One panel: `key` is 'relative' or 'absolute'. */
  function panel(data, key, top, sx, count, lastPanel) {
    var left = FIG.left, right = rightEdge(data), bottom = top + FIG.panel;
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
                 + fixed(x1 - x0) + '" height="' + FIG.panel + '" fill="'
                 + BANDS[i % BANDS.length] + '"/>');
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
             + (key === 'relative' ? 'Relative residual' : 'Absolute residual') + '</text>');

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
    // FEA-Tools plotter draws it. It breaks only at a value that is not finite.
    var segment = [], lines = [];
    iterations.forEach(function (it, i) {
      if (!finite(it[key])) {
        if (segment.length > 1) lines.push(segment);
        segment = [];
      }
      if (finite(it[key])) segment.push(fixed(sx(i + 1)) + ',' + fixed(sy(it[key])));
    });
    if (segment.length > 1) lines.push(segment);
    lines.forEach(function (points) {
      out.push('<polyline class="cp-line" points="' + points.join(' ') + '" fill="none"'
               + ' stroke="' + LINE + '" stroke-width="1.3" stroke-linejoin="round"/>');
    });

    // A dot for every iteration, with its tooltip; a green X over it where the criterion
    // was met; a red cross on the top edge for a value that is not a number.
    var r = iterations.length > 400 ? 1.4 : iterations.length > 100 ? 2 : 2.6;
    iterations.forEach(function (it, i) {
      var x = fixed(sx(i + 1)), cy = fixed(sy(it[key]));
      var tip = '<title>' + esc(tooltip(data, it, i + 1)) + '</title>';
      if (!finite(it[key])) {
        out.push('<path class="cp-nan" d="M' + fixed(sx(i + 1) - 3) + ',' + fixed(top + 1)
                 + 'l6,6m0,-6l-6,6" stroke="' + EVENT + '" stroke-width="1.6" fill="none">'
                 + tip + '</path>');
        return;
      }
      out.push('<circle class="cp-dot" cx="' + x + '" cy="' + cy + '" r="' + r + '" fill="'
               + LINE + '">' + tip + '</circle>');
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
               + EVENT + '"><title>' + esc('After iteration ' + n + ': '
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
                       + at(f)) + '</title></path>');
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
             + FIG.panel + '" fill="none" stroke="' + FRAME + '"/>');
    if (fractions.length) {
      out.push('<line class="cp-fraction-spine" x1="' + right + '" y1="' + top + '" x2="'
               + right + '" y2="' + bottom + '" stroke="' + EVENT + '"/>');
    }

    // The iteration axis: tick marks on both panels, numbers under the lower one.
    iterationTicks(count, 8).forEach(function (n) {
      var x = fixed(sx(n));
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
     fits in its band, "3" where only that fits, nothing where not even that does. */
  function stageLabels(data, sx, count) {
    var out = [];
    bands(data, count).forEach(function (band) {
      var x0 = Math.max(FIG.left, sx(band.from)), x1 = Math.min(rightEdge(data), sx(band.to));
      var room = x1 - x0 - 4;
      var stage = band.stage;
      var number = stage.index === null || stage.index === undefined ? '' : String(stage.index);
      var full = (number + ' ' + tidy(stage.name)).trim();
      var text = full.length * CHAR <= room ? full : number.length * CHAR <= room ? number : '';
      if (!text) return;
      out.push('<text class="cp-stage" x="' + fixed((x0 + x1) / 2) + '" y="' + (FIG.top - 6)
               + '" text-anchor="middle"><title>' + esc(full) + '</title>' + esc(text)
               + '</text>');
    });
    return out.join('');
  }

  function legend(data, y) {
    var x = FIG.left;
    var out = ['<g class="cp-legend" transform="translate(' + x + ',' + y + ')">'];
    out.push('<line x1="0" y1="0" x2="16" y2="0" stroke="' + LINE + '" stroke-width="1.3"/>'
             + '<circle cx="8" cy="0" r="2.4" fill="' + LINE + '"/>'
             + '<text x="20" y="0" dy="0.35em">residual</text>');
    out.push('<line x1="78" y1="0" x2="96" y2="0" stroke="' + TARGET
             + '" stroke-dasharray="5,3"/><text x="100" y="0" dy="0.35em">target</text>');
    out.push('<circle cx="146" cy="0" r="2.4" fill="' + LINE + '"/><path d="'
             + cross(146, 0, 4.2) + '" stroke="' + MET + '" stroke-width="1.6" fill="none"/>'
             + '<text x="155" y="0" dy="0.35em">criterion met</text>');
    out.push('<path d="M232,-4h8l-4,7z" fill="' + EVENT + '"/>'
             + '<text x="245" y="0" dy="0.35em">iteration limit or cut-back</text>');
    out.push('<rect x="380" y="-5" width="14" height="10" fill="' + BANDS[1] + '"/>'
             + '<text x="398" y="0" dy="0.35em">stage</text>');
    if (fractionsOf(data).length) {
      out.push('<g class="cp-legend-fraction" transform="translate(0,' + FIG.legend + ')">'
               + '<line x1="0" y1="0" x2="16" y2="0" stroke="' + EVENT + '" stroke-width="1.1"/>'
               + '<path d="' + cross(8, 0, 2.6) + '" stroke="' + EVENT + '" stroke-width="1.2"'
               + ' fill="none"/><text x="20" y="0" dy="0.35em" fill="' + EVENT + '">'
               + 'fraction of unbalance (right axis)</text></g>');
    }
    out.push('</g>');
    return out.join('');
  }

  /* The whole figure, as a string: shown by the window, saved as a file. */
  function svg(data) {
    data = data || {};
    var iterations = data.iterations || [];
    var count = Math.max(1, iterations.length);
    var left = FIG.left, right = rightEdge(data);
    function sx(n) { return left + (n - 0.5) / count * (right - left); }
    var h = height(data);
    var out = ['<svg xmlns="http://www.w3.org/2000/svg" class="cp-figure" viewBox="0 0 '
               + FIG.width + ' ' + h + '" width="' + FIG.width + '" height="' + h
               + '" font-family="Segoe UI, Arial, sans-serif" font-size="10" fill="' + INK
               + '">'];
    out.push('<rect width="' + FIG.width + '" height="' + h + '" fill="#fff"/>');
    var upper = FIG.top, lower = FIG.top + FIG.panel + FIG.gap;
    out.push(stageLabels(data, sx, count));
    out.push(panel(data, 'relative', upper, sx, count, false));
    out.push(panel(data, 'absolute', lower, sx, count, true));
    out.push('<text class="cp-xlabel" x="' + fixed((left + right) / 2) + '" y="'
             + (lower + FIG.panel + 28) + '" text-anchor="middle">Iteration</text>');
    if (!iterations.length) {
      out.push('<text class="cp-empty" x="' + fixed((left + right) / 2) + '" y="'
               + fixed(upper + FIG.panel / 2) + '" text-anchor="middle" fill="#888">'
               + 'no iterations yet</text>');
    }
    var rows = fractionsOf(data).length ? 2 : 1;
    out.push(legend(data, h - FIG.legend * (rows - 0.5) - 2));
    out.push('</svg>');
    return out.join('');
  }

  /* ── The file ─────────────────────────────────────────────────────────── */

  var COLUMNS = ['iteration', 'stage', 'stage_name', 'step', 'time', 'cycle', 'relative',
                 'relative_target', 'absolute', 'absolute_target', 'met', 'events'];

  function cell(text) {
    var value = String(text === undefined || text === null ? '' : text);
    return /[",\n]/.test(value) ? '"' + value.replace(/"/g, '""') + '"' : value;
  }

  function value(v) {
    return v === null || v === undefined ? '' : String(v);
  }

  /* A row per iteration: `cli.terminal.tables.convergence_csv`, byte for byte. */
  function csv(data) {
    var names = {};
    (data.stages || []).forEach(function (stage) { names[stage.index] = stage.name; });
    var lines = [COLUMNS.join(',')];
    (data.iterations || []).forEach(function (it, i) {
      var n = i + 1;
      var events = (data.events || []).filter(function (event) { return event.at === n; })
        .map(function (event) {
          return event.kind + ' ' + value(event.factor !== undefined ? event.factor
                                                                     : event.limit);
        }).join('; ');
      lines.push([n, value(it.stage), cell(names[it.stage]), value(it.step), value(it.time),
                  value(it.cycle), value(it.relative), value(it.relative_target),
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
        view = { run: run, data: data };
        return data;
      }, function (error) { return quiet ? null : fail(error); });
  }

  /* Put `data` on screen as the run's, without asking: the window has it already. */
  function show(run, data, event) {
    view = { run: run, data: data };
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
                + '`png` or `pdf` the figure.');
  }

  /* ── Saving ───────────────────────────────────────────────────────────── */

  function save(kind) {
    var data = view.data;
    var name = view.run + '_convergence.' + kind;
    if (kind === 'png' || kind === 'pdf') return App.Picture.saveFigure(svg(data), name, kind);
    var text = kind === 'csv' ? csv(data) : svg(data);
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
    if (verb && verb !== 'csv' && verb !== 'svg' && verb !== 'png' && verb !== 'pdf') {
      log('err', 'No such convergence command: "' + verb + '". `results convergence` '
                 + 'shows it; `csv`, `svg`, `png` or `pdf` after it saves it.');
      return Promise.resolve();
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

  return {
    command: command, state: state, forget: forget, onChange: onChange, load: load,
    show: show, svg: svg, csv: csv, stageText: stageText, lastText: lastText,
    eventText: eventText, decades: decades, iterationTicks: iterationTicks,
    tidy: tidy, NO_RESIDUALS: NO_RESIDUALS, FIG: FIG
  };
})();
