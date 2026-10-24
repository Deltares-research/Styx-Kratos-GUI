/* ══════════════════════════════════════════════════════════════════
   results-plot.js — a structural member's results, plotted along it.

   The plot every retaining-wall calculation is read from: bending moment, shear
   force, normal force and displacement down the wall, and the earth pressure on it,
   one panel per construction stage. Modelled on Kratos' own staged-excavation
   comparison figure -- the quantity along the horizontal axis, the
   level y up the vertical one, a line with a dot at every node -- with the one
   addition of the largest value, written beside the point it occurs at.

   ── The command line is the feature ──────────────────────────────────────

       results plot                     the wall's bending moment, every stage
       results plot <quantity>          M, Q, N, ux, uy, tn, ts -- or a word of the
                                        label: moment, shear, normal, traction...
       results plot <member> [<q>]      wall, interface
       results plot members             what this run can plot
       results plot csv | svg           the numbers, or the figure, as a file

   The plot window and its buttons (patches.js) build these same strings.

   ── Why there is no DOM in here ──────────────────────────────────────────

   The same reason as results.js: this is the half `frontend/tests/run_headless.py` can
   execute. The figure is an SVG *string* -- built here, tested here, and handed to the
   window as markup -- so the only untested part is the window it is put in.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.ResultsPlot = (function () {

  var ROOT = '/api/results/runs';

  /* One panel, in SVG units. Roughly the proportions of a matplotlib subplot in the
     reference figure: taller than wide, because the wall is. */
  var PANEL = { width: 230, height: 330, left: 54, right: 14, top: 28, bottom: 46 };
  var COLUMNS = 5;          // per row before wrapping, as `make_sub_plots` does
  var DOTS_UP_TO = 150;     // nodes per panel; a sheet-pile wall is ~40-50, a long dike's ~750
  var LINE = '#1f77b4';     // matplotlib's first colour, the reference figure's Kratos line
  var PEAK = '#d62728';
  var GRID = '#dcdcdc';
  var FRAME = '#444';
  var INK = '#222';

  var view = { run: null, members: null, member: null, quantity: null, plot: null };
  var listeners = [];

  function log(kind, line) {
    if (App.Command && App.Command[kind]) App.Command[kind](line);
  }

  function fail(error) {
    log('err', (error && error.message) || String(error));
    return null;
  }

  /* ── State ────────────────────────────────────────────────────────────── */

  function state() {
    return { run: view.run, members: view.members, member: view.member,
             quantity: view.quantity, plot: view.plot };
  }

  /* Nothing plotted. Listeners are kept: the window subscribes once, at boot, and
     opening a different project must not quietly unplug it. */
  function forget() {
    view = { run: null, members: null, member: null, quantity: null, plot: null };
    changed({});
  }

  /* `event.open` is the command asking for the window: patches.js opens it if it is
     not already up. Every event also means "redraw from `state()`". */
  function onChange(listener) {
    if (typeof listener === 'function') listeners.push(listener);
  }

  function changed(event) {
    listeners.forEach(function (listener) {
      try { listener(event || {}); } catch (error) { /* a broken window must not stop this */ }
    });
  }

  /* ── Formatting ───────────────────────────────────────────────────────── */

  function format(value) {
    if (App.ResultsRender && App.ResultsRender.format) return App.ResultsRender.format(value);
    return String(value);
  }

  function pad(text, width) {
    var out = String(text);
    while (out.length < width) out += ' ';
    return out;
  }

  function plural(count, noun) {
    return count + ' ' + noun + (count === 1 ? '' : 's');
  }

  function esc(text) {
    return String(text === undefined || text === null ? '' : text)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function fixed(n) {
    return (Math.round(n * 10) / 10).toFixed(1);
  }

  /* ── Axes ─────────────────────────────────────────────────────────────── */

  /* The round step nearest -- in ratio, not difference -- to `span / target`. Nearest
     rather than next-up: next-up turns a 13 m wall into ticks every 5 m, and the
     reference figure (and anyone reading a wall) ticks it every 2. */
  function niceStep(span, target) {
    var raw = span / (target || 5);
    var magnitude = Math.pow(10, Math.floor(Math.log10(raw)));
    var best = null;
    [1, 2, 5, 10].forEach(function (n) {
      var distance = Math.abs(Math.log((n * magnitude) / raw));
      if (best === null || distance < best.distance) {
        best = { distance: distance, step: n * magnitude };
      }
    });
    return best.step;
  }

  function decimalsOf(step) {
    return Math.max(0, Math.ceil(-Math.log10(step) - 1e-9));
  }

  /* Every multiple of a round step inside [min, max]. Rounded to the step's decimals,
     so 3 * 0.005 is -0.015 and not -0.015000000000000001. */
  function ticks(min, max, target) {
    if (!(max > min)) return [min];
    var step = niceStep(max - min, target);
    var decimals = decimalsOf(step);
    var first = Math.ceil(min / step - 1e-9);
    var last = Math.floor(max / step + 1e-9);
    var out = [];
    for (var k = first; k <= last; k++) out.push(Number((k * step).toFixed(decimals)) || 0);
    return out;
  }

  function tickLabel(value, step) {
    var text = value.toFixed(decimalsOf(step));
    return /^-0(\.0*)?$/.test(text) ? text.slice(1) : text;
  }

  /* The data range and 5 % either side -- matplotlib's default margin, so a curve
     never sits on the frame. A flat curve (all zero, or a constant) still needs a
     range to be drawn in the middle of. */
  function padded(min, max) {
    if (max < min) { var swap = min; min = max; max = swap; }
    var span = max - min;
    if (span === 0) {
      var d = Math.abs(min) * 0.05 || 1;
      return { min: min - d, max: max + d };
    }
    return { min: min - 0.05 * span, max: max + 0.05 * span };
  }

  /* ── The figure ───────────────────────────────────────────────────────── */

  function title(stage) {
    return stage.index + ' ' + (stage.stage || stage.name || '');
  }

  function axisLabel(plot) {
    return plot.label + ' [' + plot.unit + ']';
  }

  /* The point of largest magnitude, which is the number a wall is designed for. */
  function peak(points) {
    var best = null;
    points.forEach(function (point) {
      if (!best || Math.abs(point[0]) > Math.abs(best[0])) best = point;
    });
    return best;
  }

  function panel(plot, stage, column, row) {
    var x0 = column * PANEL.width, y0 = row * PANEL.height;
    var left = PANEL.left, right = PANEL.width - PANEL.right;
    var top = PANEL.top, bottom = PANEL.height - PANEL.bottom;
    var middle = (left + right) / 2;
    var out = ['<g class="rp-panel" transform="translate(' + x0 + ',' + y0 + ')">'];

    out.push('<text class="rp-title" x="' + fixed(middle) + '" y="16" text-anchor="middle"'
             + ' font-size="11">' + esc(title(stage)) + '</text>');
    out.push('<text class="rp-xlabel" x="' + fixed(middle) + '" y="'
             + (PANEL.height - 8) + '" text-anchor="middle">' + esc(axisLabel(plot))
             + '</text>');
    if (column === 0) {
      out.push('<text class="rp-ylabel" transform="translate(13,' + fixed((top + bottom) / 2)
               + ') rotate(-90)" text-anchor="middle">y [m]</text>');
    }

    var points = stage.points || [];
    if (!points.length) {
      out.push('<rect x="' + left + '" y="' + top + '" width="' + (right - left)
               + '" height="' + (bottom - top) + '" fill="none" stroke="' + FRAME + '"/>');
      out.push('<text x="' + fixed(middle) + '" y="' + fixed((top + bottom) / 2)
               + '" text-anchor="middle" fill="#888">no values in this stage</text>');
      out.push('</g>');
      return out.join('');
    }

    var values = points.map(function (p) { return p[0]; });
    var levels = points.map(function (p) { return p[1]; });
    var xr = padded(Math.min.apply(null, values), Math.max.apply(null, values));
    var yr = padded(Math.min.apply(null, levels), Math.max.apply(null, levels));
    function sx(v) { return left + (v - xr.min) / (xr.max - xr.min) * (right - left); }
    // Upright: a higher level is further *up* the page, which is smaller screen y.
    function sy(y) { return bottom - (y - yr.min) / (yr.max - yr.min) * (bottom - top); }

    var xticks = ticks(xr.min, xr.max, 5);
    var yticks = ticks(yr.min, yr.max, 6);
    var xstep = xticks.length > 1 ? xticks[1] - xticks[0] : 1;
    var ystep = yticks.length > 1 ? yticks[1] - yticks[0] : 1;

    xticks.forEach(function (t) {
      var x = fixed(sx(t));
      out.push('<line class="rp-grid" x1="' + x + '" y1="' + top + '" x2="' + x + '" y2="'
               + bottom + '" stroke="' + GRID + '"/>');
      out.push('<text class="rp-tick" x="' + x + '" y="' + (bottom + 13)
               + '" text-anchor="middle">' + tickLabel(t, xstep) + '</text>');
    });
    yticks.forEach(function (t) {
      var y = fixed(sy(t));
      out.push('<line class="rp-grid" x1="' + left + '" y1="' + y + '" x2="' + right
               + '" y2="' + y + '" stroke="' + GRID + '"/>');
      out.push('<text class="rp-tick" x="' + (left - 4) + '" y="' + y
               + '" dy="0.35em" text-anchor="end">' + tickLabel(t, ystep) + '</text>');
    });
    out.push('<rect x="' + left + '" y="' + top + '" width="' + (right - left)
             + '" height="' + (bottom - top) + '" fill="none" stroke="' + FRAME + '"/>');

    out.push('<polyline class="rp-line" points="' + points.map(function (p) {
      return fixed(sx(p[0])) + ',' + fixed(sy(p[1]));
    }).join(' ') + '" fill="none" stroke="' + LINE + '" stroke-width="1.4"'
             + ' stroke-linejoin="round"/>');
    // A dot per node, as the reference figure has -- unless there are so many that the
    // dots merge into a bar and hide the line they mark.
    if (points.length <= DOTS_UP_TO) {
      points.forEach(function (p) {
        out.push('<circle class="rp-dot" cx="' + fixed(sx(p[0])) + '" cy="'
                 + fixed(sy(p[1])) + '" r="2" fill="' + LINE + '"/>');
      });
    }

    var most = peak(points);
    var px = sx(most[0]), py = sy(most[1]);
    var onRight = px > middle;
    out.push('<circle class="rp-peak" cx="' + fixed(px) + '" cy="' + fixed(py)
             + '" r="3.6" fill="none" stroke="' + PEAK + '" stroke-width="1.4"/>');
    out.push('<text class="rp-peak-label" x="' + fixed(px + (onRight ? -6 : 6)) + '" y="'
             + fixed(Math.max(top + 10, py - 6)) + '" text-anchor="'
             + (onRight ? 'end' : 'start') + '" fill="' + PEAK + '" font-weight="600">'
             + esc(format(most[0])) + '</text>');

    out.push('</g>');
    return out.join('');
  }

  /* The whole figure: a panel per stage, `columns` to a row. A string, so it can be
     tested here, shown by assigning it to a window's innerHTML, and saved as a file
     that opens anywhere. `options.columns` is the window's to choose by its width. */
  function svg(plot, options) {
    var stages = (plot && plot.stages) || [];
    var columns = Math.max(1, Math.min((options && options.columns) || COLUMNS,
                                       stages.length || 1));
    var rows = Math.max(1, Math.ceil(stages.length / columns));
    var width = columns * PANEL.width, height = rows * PANEL.height;
    var out = ['<svg xmlns="http://www.w3.org/2000/svg" class="rp-figure" viewBox="0 0 '
               + width + ' ' + height + '" width="' + width + '" height="' + height
               + '" font-family="Segoe UI, Arial, sans-serif" font-size="10" fill="' + INK
               + '">'];
    out.push('<rect width="' + width + '" height="' + height + '" fill="#fff"/>');
    stages.forEach(function (stage, i) {
      out.push(panel(plot, stage, i % columns, Math.floor(i / columns)));
    });
    out.push('</svg>');
    return out.join('');
  }

  /* ── Choosing what to plot ────────────────────────────────────────────── */

  function members(run) {
    if (view.run === run && view.members) return Promise.resolve(view.members);
    return App.Api.get(ROOT + '/' + encodeURIComponent(run) + '/members')
      .then(function (answer) {
        view = { run: run, members: answer.members || [], member: null, quantity: null,
                 plot: null };
        return view.members;
      }).catch(fail);
  }

  function names(list) {
    return list.map(function (entry) { return entry.name; }).join(', ');
  }

  function memberNamed(list, token) {
    var wanted = String(token || '').toLowerCase();
    return list.filter(function (m) { return m.name.toLowerCase() === wanted; })[0] || null;
  }

  /* A quantity of one member by its name (`M`, `tn`), or by a word of its label
     (`moment`, `normal`). The name first, so `n` is the normal force and not any label
     that happens to contain an n. */
  function quantityIn(member, token) {
    var wanted = String(token || '').toLowerCase().trim();
    var quantities = member.quantities || [];
    if (!wanted) {
      var keep = quantities.filter(function (q) { return q.name === view.quantity; })[0];
      var moment = quantities.filter(function (q) { return q.name === 'M'; })[0];
      return keep || moment || quantities[0] || null;
    }
    return quantities.filter(function (q) { return q.name.toLowerCase() === wanted; })[0]
      || quantities.filter(function (q) {
        return q.label.toLowerCase().indexOf(wanted) !== -1;
      })[0]
      || null;
  }

  /* The member on screen first, so `shear` stays on the interface while the interface
     is being looked at; then the rest in the order the run lists them. */
  function searchOrder(list) {
    var current = memberNamed(list, view.member);
    return current ? [current].concat(list.filter(function (m) { return m !== current; }))
                   : list;
  }

  function pick(list, tokens) {
    var named = tokens.length ? memberNamed(list, tokens[0]) : null;
    if (named) {
      var asked = tokens.slice(1).join(' ');
      var found = quantityIn(named, asked);
      if (!found) {
        log('err', 'The ' + named.name + ' output has no "' + asked + '". It has '
                   + names(named.quantities) + '.');
        return null;
      }
      return { member: named.name, quantity: found.name };
    }

    var token = tokens.join(' ');
    if (!token) {
      var wall = list.filter(function (m) {
        return (m.quantities || []).some(function (q) { return q.name === 'M'; });
      })[0];
      var member = memberNamed(list, view.member) || wall || list[0];
      var chosen = quantityIn(member, '');
      return chosen ? { member: member.name, quantity: chosen.name } : null;
    }

    var order = searchOrder(list);
    for (var i = 0; i < order.length; i++) {
      var hit = quantityIn(order[i], token);
      if (hit) return { member: order[i].name, quantity: hit.name };
    }
    if (tokens.length > 1) {
      log('err', 'There is no member called "' + tokens[0] + '" in this run — it has '
                 + names(list) + '.');
    } else {
      log('err', 'Nothing in this run can be plotted as "' + token + '". '
                 + list.map(function (m) {
                   return m.name + ': ' + names(m.quantities || []);
                 }).join('; ') + '.');
    }
    return null;
  }

  function fetchPlot(run, picked, open) {
    var path = ROOT + '/' + encodeURIComponent(run) + '/members/'
             + encodeURIComponent(picked.member) + '/' + encodeURIComponent(picked.quantity);
    return App.Api.get(path).then(function (plot) {
      view.member = picked.member;
      view.quantity = picked.quantity;
      view.plot = plot;
      report(plot);
      changed({ open: open });
      return plot;
    }).catch(fail);
  }

  function extreme(label, at) {
    return at ? label + ' ' + format(at.value) + ' at y = ' + at.y.toFixed(2) : '';
  }

  function report(plot) {
    log('ok', plot.label + ' (' + plot.unit + ') along the ' + plot.member + ', '
              + plural(plot.stages.length, 'stage') + ':');
    plot.stages.forEach(function (stage) {
      log('note', '  ' + pad(stage.index, 4) + pad(stage.stage || stage.name, 30)
                  + pad(extreme('max', stage.max), 28) + extreme('min', stage.min));
    });
    log('note', '`results plot csv` saves the numbers, `results plot svg` the figure.');
  }

  function listMembers(list) {
    if (!list.length) {
      log('note', 'This run wrote no member output.');
      return;
    }
    log('ok', 'This run can plot:');
    list.forEach(function (m) {
      log('note', '  ' + pad(m.name, 11) + pad('stages ' + m.stages.join(', '), 18)
                  + names(m.quantities || []));
    });
    log('note', 'e.g. `results plot wall M`, `results plot interface normal`.');
  }

  /* ── Saving ───────────────────────────────────────────────────────────── */

  function cell(text) {
    var value = String(text === undefined || text === null ? '' : text);
    return /[",\n]/.test(value) ? '"' + value.replace(/"/g, '""') + '"' : value;
  }

  function csv(plot) {
    var lines = ['stage,name,node,y [m],' + plot.quantity + ' [' + plot.unit + ']'];
    plot.stages.forEach(function (stage) {
      stage.points.forEach(function (point, i) {
        lines.push([stage.index, cell(stage.stage || stage.name),
                    (stage.nodes || [])[i], point[1], point[0]].join(','));
      });
    });
    return lines.join('\n') + '\n';
  }

  function save(kind) {
    var plot = view.plot;
    var name = [view.run, plot.member, plot.quantity].join('_') + '.' + kind;
    if (kind === 'csv') App.Download.anchor(name, csv(plot), 'text/csv');
    else App.Download.anchor(name, svg(plot), 'image/svg+xml');
    log('ok', 'Saved ' + name + '.');
  }

  /* ── The command ──────────────────────────────────────────────────────── */

  /* `results plot ...`, routed here by results.js. Always a promise. */
  function command(rest) {
    var tokens = String(rest || '').trim().split(/\s+/).filter(function (t) { return t; });
    var run = App.Results && App.Results.current ? App.Results.current() : null;
    if (!run) {
      log('err', 'No run is open. `results runs` lists them, `results open <n>` opens one.');
      return Promise.resolve();
    }
    var verb = (tokens[0] || '').toLowerCase();

    return members(run).then(function (list) {
      if (!list) return null;
      if (verb === 'members' || verb === 'list') return listMembers(list);
      if (!list.length) {
        log('note', run + ' wrote no member output — there is no wall in it, '
                    + 'or no stage with one.');
        return null;
      }
      if (verb === 'csv' || verb === 'svg') {
        var ready = view.plot ? Promise.resolve(view.plot)
                              : fetchPlot(run, pick(list, []), false);
        return ready.then(function (plot) { if (plot) save(verb); });
      }
      var picked = pick(list, tokens);
      return picked ? fetchPlot(run, picked, true) : null;
    });
  }

  return {
    command: command, state: state, forget: forget, onChange: onChange,
    svg: svg, ticks: ticks, tickLabel: tickLabel, padded: padded, csv: csv,
    PANEL: PANEL
  };
})();
