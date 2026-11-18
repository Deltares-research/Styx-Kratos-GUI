/* ══════════════════════════════════════════════════════════════════
   ruler.js — measured edges for the 2D section.

   A plane-strain section is a drawing, and a drawing without a scale is a
   picture. The grid already says "these lines are 0.5 m apart", but it never
   says *where* a line is, and reading a coordinate off it means counting cells
   from a corner nobody marked. Four rulers say it directly: the world value at
   every screen edge, in the same two axes the section is drawn in.

   All four are painted, not just two, because the section is panned as often as
   it is zoomed and the model is rarely in the middle of the viewport: a point
   near the bottom-right is measured against the bottom and right edges without
   the eye travelling the width of the screen to reach a ruler.

   The arithmetic here (`niceStep`, `ticks`, `plan`) is deliberately separate from
   the painting: it takes the camera's visible rectangle and returns where every
   tick goes, which is the part that can be wrong and therefore the part that is
   tested. 3D never shows them -- there is no single plane for the numbers to
   mean anything in.
   ══════════════════════════════════════════════════════════════════ */

(function (App) {
  'use strict';

  var SIZE = 22;                 // ruler thickness in CSS pixels
  var MIN_SPACING = 64;          // no two labelled ticks closer than this
  var MIN_MINOR_SPACING = 7;     // below this the minor ticks are a grey smudge
  var EDGES = ['top', 'bottom', 'left', 'right'];

  /* The two world axes the screen's horizontal and vertical edges measure. Fixed,
     not derived from the camera, because the 2D camera is fixed too: there is one
     section -- the x-y plane -- and it is viewed along -z with +y up. */
  var AXES = ['x', 'y'];

  function axesOf() { return AXES.slice(); }

  /* 1, 2 or 5 times a power of ten: the only steps a reader can add up in their head,
     and the same family the grid coarsens by, so a ruler tick is always on a grid line
     when the two happen to agree. */
  function niceStep(raw) {
    if (!(raw > 0) || !isFinite(raw)) return 1;
    var mag = Math.pow(10, Math.floor(Math.log10(raw)));
    var f = raw / mag;
    var step = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
    return step * mag;
  }

  /* How many unlabelled marks a labelled interval is cut into. Chosen so the minor
     step is itself round -- 1 m in fifths is 0.2, 2 m in quarters is 0.5, 5 m in
     fifths is 1 -- because the reader counts minor ticks to interpolate, and counting
     is only easier than reading if each one is worth a number they can say. */
  function minorDivisions(step) {
    var mag = Math.pow(10, Math.floor(Math.log10(step > 0 ? step : 1) + 1e-9));
    var f = Math.round(step / mag);
    return f === 2 ? 4 : 5;
  }

  /* Every multiple of the step inside [min, max], with its pixel offset from the min
     end, and the minor marks between them. The caller decides which screen direction
     that end is. */
  function ticks(min, max, lengthPx, minSpacingPx) {
    var span = max - min;
    if (!(span > 0) || !(lengthPx > 0)) {
      return { step: niceStep(0), minorStep: 0, ticks: [], minor: [] };
    }
    var perPx = span / lengthPx;
    var step = niceStep(perPx * (minSpacingPx > 0 ? minSpacingPx : MIN_SPACING));

    /* One lattice for both: the minor step walks it and every nth mark is a major one,
       so a major tick is exactly a minor tick that got a label. Deriving the two
       independently would let rounding put a label half a pixel off its own mark. */
    var divisions = minorDivisions(step);
    var minorStep = step / divisions;
    // Enough room for the marks is a question about pixels, not about metres.
    var withMinor = minorStep / perPx >= MIN_MINOR_SPACING;

    var major = [], minor = [];
    // Guarding the count as well as the bound: a pathological span/step (a camera
    // mid-animation, a zero-size viewport) must drop the ruler, never hang the frame.
    var first = Math.ceil(min / minorStep - 1e-9);
    var last = Math.floor(max / minorStep + 1e-9);
    for (var i = first; i <= last && major.length + minor.length < 8192; i++) {
      var value = i * minorStep;
      var mark = { value: value, pos: (value - min) / span * lengthPx };
      // Modulo on the index, not on the value: i is an exact integer where
      // 0.30000000000000004 % 0.1 is not.
      if (((i % divisions) + divisions) % divisions === 0) {
        mark.value = (i / divisions) * step;    // the major value, free of minorStep's error
        mark.pos = (mark.value - min) / span * lengthPx;
        major.push(mark);
      } else if (withMinor) {
        minor.push(mark);
      }
    }
    return { step: step, minorStep: withMinor ? minorStep : 0,
             ticks: major, minor: minor };
  }

  /* Decimals come from the step, not from the value: a ruler whose labels change
     length as they pass zero reads as noise. */
  function format(value, step) {
    var decimals = Math.min(4, Math.max(0, -Math.floor(Math.log10(step > 0 ? step : 1) + 1e-9)));
    var text = value.toFixed(decimals);
    if (parseFloat(text) === 0) text = (0).toFixed(decimals);   // never "-0.00"
    return decimals ? text : String(parseInt(text, 10));
  }

  /* The camera's visible rectangle turned into two labelled scales.

     `center` is the in-plane point the camera is on and `halfW`/`halfH` its visible
     half-extents -- exactly what viewport.js already computes for the 2D grid. The
     horizontal scale is listed left to right; the vertical one is listed *down* the
     screen, so its values descend: both are then in the order they are painted. */
  function plan(state) {
    var axes = axesOf();
    var w = state.width, h = state.height;
    var spacing = state.minSpacing || MIN_SPACING;
    var hMin = state.center[0] - state.halfW, hMax = state.center[0] + state.halfW;
    var vMin = state.center[1] - state.halfH, vMax = state.center[1] + state.halfH;

    var horizontal = ticks(hMin, hMax, w, spacing);
    var vertical = ticks(vMin, vMax, h, spacing);

    // Screen y grows downward while the world axis grows upward, so the pixel offset
    // is measured from the far end and the list reverses with it.
    function flip(list) {
      return list.map(function (t) {
        return { value: t.value, pos: h - t.pos };
      }).reverse();
    }

    return {
      h: { axis: axes[0], min: hMin, max: hMax, step: horizontal.step,
           minorStep: horizontal.minorStep,
           ticks: horizontal.ticks, minor: horizontal.minor },
      v: { axis: axes[1], min: vMin, max: vMax, step: vertical.step,
           minorStep: vertical.minorStep,
           ticks: flip(vertical.ticks), minor: flip(vertical.minor) }
    };
  }

  /* ── The switch ───────────────────────────────────────────────── */

  var enabled = false;

  function setEnabled(on) {
    enabled = !!on;
    return enabled;
  }

  function isEnabled() { return enabled; }

  /* Two conditions, one answer: the user asked for them and there is a section to
     measure. 3D is not a "no" the switch can override. */
  function visible(state) { return enabled && !!(state && state.active); }

  /* ── The DOM ──────────────────────────────────────────────────── */

  var canvases = null, host = null;

  function install(container) {
    host = container || document.getElementById('viewport');
    if (!host) return null;
    if (canvases) uninstall();
    canvases = {};
    EDGES.forEach(function (edge) {
      var c = document.createElement('canvas');
      c.className = 'vp-ruler vp-ruler-' + edge;
      c.dataset.edge = edge;
      c.hidden = true;
      host.appendChild(c);
      canvases[edge] = c;
    });
    return canvases;
  }

  function uninstall() {
    if (!canvases) return;
    if (host && host.classList) host.classList.remove('rulers-on');
    EDGES.forEach(function (edge) {
      var c = canvases[edge];
      if (c && c.parentNode) c.parentNode.removeChild(c);
    });
    canvases = null;
  }

  function hideAll() {
    if (!canvases) return;
    EDGES.forEach(function (edge) { canvases[edge].hidden = true; });
    // The HUD corners only step inward while there is a ruler under them.
    if (host && host.classList) host.classList.remove('rulers-on');
  }

  /* Painted, not laid out in DOM: a tick every 64 px over a 2000 px edge is a hundred
     absolutely-positioned elements per frame, and this runs inside the render tick. */
  function paint(canvas, scale, orientation, ratio) {
    var horizontal = orientation === 'top' || orientation === 'bottom';
    var length = horizontal ? canvas.clientWidth : canvas.clientHeight;
    if (!(length > 0)) return;
    canvas.width = Math.floor((horizontal ? length : SIZE) * ratio);
    canvas.height = Math.floor((horizontal ? SIZE : length) * ratio);

    var ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = 'rgba(255,255,255,.86)';
    ctx.fillRect(0, 0, horizontal ? length : SIZE, horizontal ? SIZE : length);

    ctx.strokeStyle = '#b8c2ce';
    ctx.lineWidth = 1;
    ctx.beginPath();
    // The hairline separating the ruler from the scene, on the side facing it.
    if (orientation === 'top')    { ctx.moveTo(0, SIZE - 0.5); ctx.lineTo(length, SIZE - 0.5); }
    if (orientation === 'bottom') { ctx.moveTo(0, 0.5);        ctx.lineTo(length, 0.5); }
    if (orientation === 'left')   { ctx.moveTo(SIZE - 0.5, 0); ctx.lineTo(SIZE - 0.5, length); }
    if (orientation === 'right')  { ctx.moveTo(0.5, 0);        ctx.lineTo(0.5, length); }
    ctx.stroke();

    /* Minor marks first, and shorter and paler: they are the interpolation aid, and a
       tick the same weight as a labelled one turns the ruler into a comb. Drawn as one
       path -- there can be a couple of hundred of them per edge, per frame. */
    var minorLength = 4;
    ctx.strokeStyle = '#aab4c0';
    ctx.beginPath();
    (scale.minor || []).forEach(function (t) {
      var m = Math.round(t.pos) + 0.5;
      if (m < 1 || m > length - 1) return;
      if (horizontal) {
        var my = orientation === 'top' ? SIZE - minorLength : 0;
        ctx.moveTo(m, my); ctx.lineTo(m, my + minorLength);
      } else {
        var mx = orientation === 'left' ? SIZE - minorLength : 0;
        ctx.moveTo(mx, m); ctx.lineTo(mx + minorLength, m);
      }
    });
    ctx.stroke();

    ctx.font = '10px Segoe UI, Arial, sans-serif';
    ctx.fillStyle = '#41505f';
    ctx.strokeStyle = '#7b8794';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    scale.ticks.forEach(function (t) {
      var p = Math.round(t.pos) + 0.5;
      if (p < 6 || p > length - 6) return;         // a label with no room to sit in
      var label = format(t.value, scale.step);
      ctx.beginPath();
      if (horizontal) {
        var y0 = orientation === 'top' ? SIZE - 6 : 0;
        ctx.moveTo(p, y0); ctx.lineTo(p, y0 + 6);
        ctx.stroke();
        ctx.fillText(label, p, orientation === 'top' ? SIZE - 13 : 13);
      } else {
        var x0 = orientation === 'left' ? SIZE - 6 : 0;
        ctx.moveTo(x0, p); ctx.lineTo(x0 + 6, p);
        ctx.stroke();
        // Read bottom-to-top, the way a vertical scale is read on a drawing.
        ctx.save();
        ctx.translate(orientation === 'left' ? SIZE - 13 : 13, p);
        ctx.rotate(-Math.PI / 2);
        ctx.fillText(label, 0, 0);
        ctx.restore();
      }
    });
  }

  /* Called from the render tick with the camera's own numbers, so the rulers cannot
     disagree with what is on screen. `width`/`height` default to the host, which is
     what the scene canvas fills. */
  function sync(state) {
    if (!canvases) return null;
    if (!visible(state)) { hideAll(); return null; }

    var width = state.width || host.clientWidth;
    var height = state.height || host.clientHeight;
    if (!(width > 2 && height > 2)) { hideAll(); return null; }

    var layout = plan({ center: state.center,
                        halfW: state.halfW, halfH: state.halfH,
                        width: width, height: height,
                        minSpacing: state.minSpacing });
    var ratio = Math.min(window.devicePixelRatio || 1, 2);
    EDGES.forEach(function (edge) { canvases[edge].hidden = false; });
    if (host && host.classList) host.classList.add('rulers-on');
    paint(canvases.top, layout.h, 'top', ratio);
    paint(canvases.bottom, layout.h, 'bottom', ratio);
    paint(canvases.left, layout.v, 'left', ratio);
    paint(canvases.right, layout.v, 'right', ratio);
    return layout;
  }

  App.Ruler = {
    SIZE: SIZE, MIN_SPACING: MIN_SPACING,
    niceStep: niceStep, minorDivisions: minorDivisions, ticks: ticks,
    format: format, axesOf: axesOf, plan: plan,
    setEnabled: setEnabled, isEnabled: isEnabled, visible: visible,
    install: install, uninstall: uninstall, sync: sync
  };

})(window.App = window.App || {});
