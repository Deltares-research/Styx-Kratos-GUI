/* ══════════════════════════════════════════════════════════════════
   picture.js — a saved picture, from the scene on screen to a file or the clipboard.

   The half with a DOM: it reads three.js into the plain arrays `picture-draw.js` works on,
   paints on a canvas, asks for the save window, and walks the stages and fields. What is
   drawn is decided over there.

   ── One gesture, one window ──────────────────────────────────────────────

   As in download.js, the browser only offers a save window straight out of the click. So
   `save` asks first and draws afterwards, and the choice between a file window and a
   folder window has to be made from what was asked, before any field list is known.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Picture = (function () {

  var D = App.PictureDraw;
  var W = App.PictureWriters;
  var WINDOW_ID = 'styx-pictures';

  var MIME = { png: 'image/png', pdf: 'application/pdf', svg: 'image/svg+xml', csv: 'text/csv' };

  var walking = false;
  var stopAsked = false;

  function log(kind, line) {
    if (App.Command && App.Command[kind]) App.Command[kind](line);
  }

  /* ── The scene as plain arrays ────────────────────────────────────────── */

  function rgb(color) { return [color.r, color.g, color.b]; }

  function unit(vector) {
    var size = Math.sqrt(vector.x * vector.x + vector.y * vector.y + vector.z * vector.z) || 1;
    return [vector.x / size, vector.y / size, vector.z / size];
  }

  function attribute(geometry, name) {
    var found = geometry && geometry.attributes && geometry.attributes[name];
    return found ? found.array : null;
  }

  function common(object, kind) {
    var material = object.material;
    return {
      kind: kind, matrix: object.matrixWorld.elements,
      positions: attribute(object.geometry, 'position'),
      index: object.geometry && object.geometry.index ? object.geometry.index.array : null,
      colors: material.vertexColors ? attribute(object.geometry, 'color') : null,
      color: material.color ? rgb(material.color) : [0, 0, 0],
      alpha: material.transparent ? material.opacity : 1,
      transparent: !!material.transparent,
      depthTest: material.depthTest !== false,
      depthWrite: material.depthWrite !== false,
      offset: material.polygonOffset ? material.polygonOffsetFactor + material.polygonOffsetUnits : 0,
      renderOrder: object.renderOrder || 0
    };
  }

  /* `null` for what a picture cannot show: a sprite that says nothing about its text. */
  function describe(object) {
    if (!object.material || Array.isArray(object.material)) return null;
    // Drawn by a shader on screen only (a wide line's band, results-view.js); the line
    // it sits on is in the picture instead.
    if (object.userData.screenOnly) return null;
    if (object.isSprite) {
      var text = object.userData.pictureText;
      if (!text) return null;
      var label = common(object, 'text');
      return Object.assign(label, {
        positions: [0, 0, 0], index: null, colors: null, text: text.text,
        scale: object.scale.y, fraction: text.fraction, fixed: !!text.fixed,
        color: rgb(new THREE.Color(text.color)), halo: !!text.halo, bold: !!text.bold,
        ring: text.ring === undefined ? null : rgb(new THREE.Color(text.ring))
      });
    }
    if (!attribute(object.geometry, 'position')) return null;
    if (object.isMesh) {
      return Object.assign(common(object, 'faces'), {
        lit: !!object.material.isMeshLambertMaterial, side: object.material.side
      });
    }
    if (object.isLineSegments || object.isLine) {
      var dashed = object.material.isLineDashedMaterial;
      return Object.assign(common(object, object.isLineSegments ? 'lines' : 'strip'), {
        dash: dashed ? { size: object.material.dashSize, gap: object.material.gapSize } : null,
        weight: object.userData.lineWeight || 1
      });
    }
    if (object.isPoints) {
      return Object.assign(common(object, 'points'), { size: object.material.size });
    }
    return null;
  }

  function lightsOf(scene) {
    var lights = [];
    scene.traverseVisible(function (object) {
      if (object.isHemisphereLight) {
        lights.push({ kind: 'hemi', sky: rgb(object.color), ground: rgb(object.groundColor),
                      intensity: object.intensity, dir: unit(object.position) });
      } else if (object.isDirectionalLight) {
        lights.push({ kind: 'dir', color: rgb(object.color), intensity: object.intensity,
                      dir: unit(object.position.clone().sub(object.target.position)) });
      }
    });
    return lights;
  }

  function objectsOf(screen, show) {
    var skip = screen.leaveOut.slice();
    if (!show.grid) skip = skip.concat(screen.grid);
    var objects = [];
    (function walk(object, inGrid) {
      if (!object.visible || skip.indexOf(object) >= 0) return;
      var grid = inGrid || screen.grid.indexOf(object) >= 0;
      var described = describe(object);
      if (described) {
        // A picture crops to the model, and the grid runs on past it.
        if (grid) described.noFrame = true;
        objects.push(described);
      }
      object.children.forEach(function (child) { walk(child, grid); });
    })(screen.scene, false);
    return objects;
  }

  /* The stage on screen, as a picture's title says it. */
  function stageTitle() {
    if (inResults()) {
      var index = App.Results.stage();
      var found = resultStages().filter(function (stage) { return stage.index === index; })[0];
      return 'Stage ' + index + (found && found.stage ? ': ' + found.stage : '');
    }
    if (!inStaged()) return null;
    var stage = currentStage();
    return 'Stage ' + stage.index + ': ' + stage.name;
  }

  /* What the screen shows now, or what a stage or field shows after `walk` has put it
     there. `show` is what the window ticked; anything it does not name follows the
     screen. */
  function readView(screen, show) {
    var view = {
      camera: { view: screen.camera.matrixWorldInverse.elements,
                projection: screen.camera.projectionMatrix.elements },
      section: screen.section,
      objects: objectsOf(screen, show),
      lights: lightsOf(screen.scene),
      title: stageTitle()
    };
    if (show.rulers && screen.rulers) view.rulers = screen.rulers;
    if (show.axes) {
      view.triad = { axes: screen.axes.map(function (axis) {
        return { name: axis.name, dir: axis.dir, color: rgb(new THREE.Color(axis.color)) };
      }) };
    }
    var legend = App.ResultsView && App.state && App.state.mode === 'results'
      ? App.ResultsView.legendData() : null;
    if (legend) {
      view.caption = [legend.title].concat(legend.range || []);
      if (show.legend) view.legend = legend;
    }
    if (App.MeshLabels && App.Viewport.labelsOn && App.Viewport.labelsOn()) {
      view.labelPlanner = function (toView, across, down) {
        return App.MeshLabels.forPicture(function (x, y, z) {
          var at = App.Viewport.projectToScreen(x, y, z);
          if (!at) return null;
          var there = toView(at.x, at.y);
          return { x: there.x, y: there.y, depth: at.depth };
        }, across, down);
      };
    }
    return view;
  }

  function defaults() {
    return { legend: true, axes: true, grid: false,
             rulers: !!(App.Ruler && App.Ruler.isEnabled && App.Ruler.isEnabled()) };
  }

  function viewNow(asked, screen) {
    return readView(screen, Object.assign(defaults(), asked.show || {}));
  }

  /* The picture as shapes, or `null` with no scene to read. `frame` is from `commonFrame`. */
  function compose(asked, frame) {
    var screen = App.Viewport.pictureView && App.Viewport.pictureView();
    if (!screen) return null;
    return D.picture(viewNow(asked, screen), asked.width || D.DEFAULT_WIDTH_CM, screen, undefined, frame);
  }

  /* ── A canvas, for the PNG ────────────────────────────────────────────── */

  function imageCanvas(shape) {
    var canvas = document.createElement('canvas');
    canvas.width = shape.width;
    canvas.height = shape.height;
    canvas.getContext('2d').putImageData(new ImageData(shape.rgba, shape.width, shape.height), 0, 0);
    return canvas;
  }

  function css(color) {
    return 'rgb(' + color.map(function (c) { return Math.round(c * 255); }).join(',') + ')';
  }

  function paintText(ctx, shape) {
    var size = shape.size * 25.4 / 72;
    ctx.save();
    ctx.translate(shape.x, shape.y);
    if (shape.rotate) ctx.rotate(shape.rotate * Math.PI / 180);
    ctx.font = (shape.bold ? 'bold ' : '') + size + 'px Arial, Helvetica, sans-serif';
    ctx.textAlign = shape.anchor === 'middle' ? 'center' : shape.anchor === 'end' ? 'right' : 'left';
    ctx.textBaseline = 'alphabetic';
    if (shape.halo) {
      ctx.lineJoin = 'round';
      ctx.lineWidth = size * 0.2;
      ctx.strokeStyle = css(shape.halo);
      ctx.strokeText(shape.text, 0, 0);
    }
    ctx.fillStyle = css(shape.color);
    ctx.fillText(shape.text, 0, 0);
    ctx.restore();
  }

  function paint(picture) {
    var size = picture.page;
    var canvas = document.createElement('canvas');
    canvas.width = size.widthPx;
    canvas.height = size.heightPx;
    var ctx = canvas.getContext('2d');
    var scale = size.pxPerMm;
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    ctx.lineCap = 'round';

    picture.list.forEach(function (shape) {
      ctx.globalAlpha = shape.alpha === undefined ? 1 : shape.alpha;
      if (shape.t === 'image') {
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.drawImage(imageCanvas(shape), Math.round((shape.x || 0) * scale),
                      Math.round((shape.y || 0) * scale));
        ctx.setTransform(scale, 0, 0, scale, 0, 0);
      } else if (shape.t === 'fill') {
        ctx.fillStyle = css(shape.color);
        ctx.beginPath();
        for (var i = 0; i + 5 < shape.tris.length; i += 6) {
          ctx.moveTo(shape.tris[i], shape.tris[i + 1]);
          ctx.lineTo(shape.tris[i + 2], shape.tris[i + 3]);
          ctx.lineTo(shape.tris[i + 4], shape.tris[i + 5]);
          ctx.closePath();
        }
        ctx.fill();
      } else if (shape.t === 'line') {
        ctx.strokeStyle = css(shape.color);
        ctx.lineWidth = shape.width;
        ctx.setLineDash(shape.dash || []);
        ctx.beginPath();
        for (var s = 0; s + 3 < shape.segs.length; s += 4) {
          ctx.moveTo(shape.segs[s], shape.segs[s + 1]);
          ctx.lineTo(shape.segs[s + 2], shape.segs[s + 3]);
        }
        ctx.stroke();
        ctx.setLineDash([]);
      } else if (shape.t === 'dots') {
        ctx.fillStyle = css(shape.color);
        for (var d = 0; d + 1 < shape.xy.length; d += 2) {
          ctx.beginPath();
          ctx.arc(shape.xy[d], shape.xy[d + 1], shape.r, 0, 2 * Math.PI);
          ctx.fill();
          if (shape.ring) {
            ctx.lineWidth = shape.r * 0.2;
            ctx.strokeStyle = css(shape.ring);
            ctx.stroke();
          }
        }
      } else if (shape.t === 'text') {
        paintText(ctx, shape);
      }
    });
    return canvas;
  }

  function pngBlob(picture) {
    return new Promise(function (resolve, reject) {
      paint(picture).toBlob(function (blob) {
        if (blob) resolve(blob);
        else reject(new Error('The browser could not make a PNG of this size.'));
      }, 'image/png');
    });
  }

  /* ── The three formats ────────────────────────────────────────────────── */

  function deflate(bytes) {
    if (typeof CompressionStream !== 'function') {
      return Promise.resolve({ bytes: bytes, filter: null });
    }
    var stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream('deflate'));
    return new Response(stream).arrayBuffer().then(function (buffer) {
      return { bytes: new Uint8Array(buffer), filter: 'FlateDecode' };
    });
  }

  /* A page of a PDF, as `App.PictureWriters.pdfDocument` takes it. */
  function pdfPage(picture) {
    var streams = W.pdfStreams(picture.list, picture.page);
    if (streams.missing) {
      log('note', streams.missing + ' character(s) in this picture are not in the PDF fonts '
                  + 'and are written as "?". PNG and SVG keep them.');
    }
    return Promise.all([deflate(W.latin1(streams.content))].concat(streams.images.map(function (image) {
      return Promise.all([deflate(image.rgb), deflate(image.alpha)]);
    }))).then(function (parts) {
      return { page: picture.page, parts: {
        content: parts[0], alphas: streams.alphas,
        images: parts.slice(1).map(function (pair, i) {
          return { width: streams.images[i].width, height: streams.images[i].height,
                   rgb: pair[0], alpha: pair[1] };
        })
      } };
    });
  }

  function pdfBytes(picture) {
    return pdfPage(picture).then(function (page) { return W.pdfDocument([page]); });
  }

  function svgText(picture) {
    return W.svg(picture.list, picture.page, function (shape) {
      return imageCanvas(shape).toDataURL('image/png');
    });
  }

  /* One picture in one format, as what a file is written from. */
  function encode(picture, format) {
    if (format === 'svg') return Promise.resolve(svgText(picture));
    if (format === 'pdf') return pdfBytes(picture);
    return pngBlob(picture).then(function (blob) {
      return blob.arrayBuffer();
    }).then(function (buffer) {
      return W.pngWithDpi(new Uint8Array(buffer), D.DPI);
    });
  }

  /* ── The clipboard ────────────────────────────────────────────────────── */

  function canCopy() {
    return !!(typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.write
              && typeof ClipboardItem === 'function');
  }

  /* The blob goes in as a promise: the clipboard write has to start inside the click. */
  function copy(asked) {
    if (!canCopy()) {
      log('err', 'This browser cannot copy a picture here: copying needs localhost or https. '
                 + 'Use Save picture instead.');
      return Promise.resolve(false);
    }
    if (walking) {
      log('note', 'Pictures are being saved. Copy this one when that is done.');
      return Promise.resolve(false);
    }
    if (!compose(asked || {})) {
      log('err', 'There is no picture to copy: the viewport has nothing to draw.');
      return Promise.resolve(false);
    }
    var picture = null;
    var blob = commonFrame(asked || {}).then(function (frame) {
      picture = compose(asked || {}, frame);
      return pngBlob(picture);
    });
    var item = new ClipboardItem({ 'image/png': blob });
    return navigator.clipboard.write([item]).then(function () {
      log('ok', 'Picture copied to the clipboard (' + picture.page.widthPx + ' x '
                + picture.page.heightPx + ' px).');
      return true;
    }, function (error) {
      log('err', 'The picture could not be copied: ' + error.message);
      return false;
    });
  }

  /* ── What to save ─────────────────────────────────────────────────────── */

  function projectName() {
    return (App.PROJECT && App.PROJECT.name) || 'model';
  }

  function currentStage() {
    var list = (App.PROJECT && App.PROJECT.stages) || [];
    var position = -1;
    list.forEach(function (stage, i) {
      if (stage.id === (App.state && App.state.phase)) position = i;
    });
    if (position < 0) position = 0;
    return list.length ? { index: position + 1, id: list[position].id, name: list[position].name }
                       : null;
  }

  function resultStages() {
    var state = App.Results.state();
    return (state.stages || []).filter(function (stage) { return stage.results; });
  }

  function inResults() {
    return !!(App.state && App.state.mode === 'results' && App.Results && App.Results.current()
              && App.Results.field());
  }

  function inStaged() {
    return !!(App.state && App.state.mode === 'staged' && currentStage());
  }

  /* Whether a request means more than one file. Known before anything is walked, because
     it decides which window to open. */
  function isMany(asked) {
    return asked.formats.length > 1 || !!asked.csv
        || (asked.stage === 'all' && (inResults() || inStaged()))
        || (asked.field === 'all' && inResults());
  }

  /* Whether the PDF of this request has more than one picture in it. */
  function isOnePdf(asked) {
    return !!asked.onePdf && asked.formats.indexOf('pdf') >= 0
        && ((asked.stage === 'all' && (inResults() || inStaged()))
            || (asked.field === 'all' && inResults()));
  }

  /* What the pictures in one PDF have in common, named as `pictureParts` names one of them. */
  function onePdfName(asked) {
    if (!inResults()) return D.fileName([projectName(), 'stages'], 'pdf');
    return D.fileName([App.Results.current(),
                       asked.stage === 'all' ? 'stages' : 'stage' + App.Results.stage(),
                       asked.field === 'all' ? 'fields' : App.Results.field().field], 'pdf');
  }

  /* Calls `visit(shown)` once per picture, with the screen showing it, and puts the screen
     back. `stopped()` is asked before each. */
  function walk(asked, visit, stopped) {
    var mode = App.state && App.state.mode;
    if (inResults()) return walkResults(asked, visit, stopped);
    if (inStaged()) return walkStaged(asked, visit, stopped);
    return visit({ project: projectName(), mode: mode });
  }

  function walkStaged(asked, visit, stopped) {
    var keep = App.state.phase;
    var list = App.PROJECT.stages;
    function shown(stage, index) {
      return { project: projectName(), mode: 'staged',
               stage: { index: index, name: stage.name } };
    }
    if (asked.stage !== 'all') {
      var one = currentStage();
      return visit({ project: projectName(), mode: 'staged',
                     stage: { index: one.index, name: one.name } });
    }
    var chain = Promise.resolve();
    list.forEach(function (stage, i) {
      chain = chain.then(function () {
        if (stopped()) return null;
        App.state.phase = stage.id;
        App.Viewport.applyStageVisibility();
        return visit(shown(stage, i + 1));
      });
    });
    function back() {
      App.state.phase = keep;
      App.Viewport.applyStageVisibility();
    }
    return chain.then(back, function (error) { back(); throw error; });
  }

  function walkResults(asked, visit, stopped) {
    var keepStage = App.Results.stage();
    var keepField = App.Results.field().field;
    var stages = asked.stage === 'all' ? resultStages()
      : resultStages().filter(function (stage) { return stage.index === keepStage; });
    var run = App.Results.current();
    var chain = Promise.resolve();

    function onePicture(stage, name) {
      return function () {
        if (stopped()) return null;
        return App.Results.show(stage.index, name).then(function () {
          var field = App.Results.field();
          // A stage that does not offer this field draws something else: not this picture.
          if (name && (!field || field.field !== name)) return null;
          return visit({ run: run, stage: { index: stage.index, name: stage.stage },
                         field: field.field, values: field });
        });
      };
    }

    stages.forEach(function (stage) {
      chain = chain.then(function () {
        if (stopped()) return null;
        return App.Results.show(stage.index, keepField).then(function () {
          var names = asked.field === 'all' ? App.Results.fieldNames() : [keepField];
          var inner = Promise.resolve();
          names.forEach(function (name) { inner = inner.then(onePicture(stage, name)); });
          return inner;
        });
      });
    });
    function back() { return App.Results.show(keepStage, keepField); }
    return chain.then(back, function (error) {
      return back().then(function () { throw error; });
    });
  }

  /* Going through the stages can hide what is selected, and the user's selection stays. */
  function keepingSelection(run) {
    var key = App.Viewport.selectedKey();
    function back() {
      if (key && App.Viewport.selectedKey() !== key) App.Viewport.select(key);
    }
    return Promise.resolve().then(run).then(function (answer) {
      back();
      return answer;
    }, function (error) {
      back();
      throw error;
    });
  }

  /* `visit` once for what the screen draws, once for each tab that draws the model, and once
     for each stage as Staged construction draws it. Only which groups are visible changes, and
     all of it is put back before the screen is next drawn. */
  function throughTabsAndStages(visit) {
    var mode = App.state.mode, phase = App.state.phase;
    function show(tab) {
      App.state.mode = tab;
      App.Viewport.applyStageVisibility();
      visit();
    }
    visit();
    try {
      App.Viewport.modelTabs().forEach(show);
      ((App.PROJECT && App.PROJECT.stages) || []).forEach(function (stage) {
        App.state.phase = stage.id;
        show('staged');
      });
    } finally {
      App.state.mode = mode;
      App.state.phase = phase;
      App.Viewport.applyStageVisibility();
    }
  }

  /* The frame every picture of this model shares: what any tab or stage draws, so that a stage
     with a load has the same frame, with the model in the same place, as a stage with none, a
     picture of the mesh or a result, whichever of them are saved and when. It takes in the whole
     model, wherever the camera is, unless the user asks for the zoom of the screen: then it is
     the screen. Results come from the server, so there the screen also goes through the stages,
     as a save of every stage does: a deformed shape that goes past the frame makes it wider
     there. */
  function commonFrame(asked) {
    if (asked.screenZoom) return Promise.resolve(D.screenBox());
    var screen = App.Viewport.pictureView();
    var box = null;
    function take() {
      box = D.widerBox(box, D.drawnBox(viewNow(asked, screen), screen, true));
      return null;
    }
    walking = true;
    stopAsked = false;
    if (inResults()) progress('Getting the stages…');
    function done() {
      walking = false;
      progress(null);
    }
    return keepingSelection(function () {
      throughTabsAndStages(take);
      if (inResults()) return walk({ stage: 'all' }, take, function () { return stopAsked; });
      return null;
    }).then(function () {
      done();
      return box;
    }, function (error) {
      done();
      throw error;
    });
  }

  /* ── Where it goes ────────────────────────────────────────────────────── */

  function askOverwrite(name) {
    return new Promise(function (resolve) {
      var answer = false;
      App.Dialogs.open({
        title: 'Save picture',
        width: 420, height: 170,
        buttons: [{ label: 'Overwrite', primary: true, onClick: function () { answer = true; } },
                  { label: 'Stop' }],
        onClose: function () { resolve(answer); },
        build: function (body) {
          body.appendChild(App.UI.el('div.dlg-simple', {
            text: name + ' is already in this folder, and maybe other files of this save too. '
                  + 'Overwrite them?'
          }));
        }
      });
    });
  }

  /* Writes the files one by one into a folder, or collects them for one zip when the
     browser has no folder window. */
  function outlet(folder) {
    var collected = [];
    var allowed = false;
    return {
      add: function (name, content) {
        if (!folder) {
          collected.push({ name: name, text: content });
          return Promise.resolve(true);
        }
        var ready = allowed ? Promise.resolve(false) : App.Download.exists(folder, name);
        return ready.then(function (there) {
          if (!there) return true;
          return App.Picture.askOverwrite(name).then(function (yes) {
            allowed = yes;
            return yes;
          });
        }).then(function (go) {
          if (!go) return false;
          return App.Download.writeInFolder(folder, name, content).then(function () { return true; });
        });
      },
      finish: function () {
        if (folder || !collected.length) return;
        App.Download.anchor(D.fileName([projectName(), 'pictures'], 'zip'),
                            App.Zip.create(collected), 'application/zip');
      }
    };
  }

  function progress(text) {
    var box = document.getElementById('vp-loading');
    if (!box) return;
    box.hidden = !text;
    var stop = box.querySelector('.picture-stop');
    if (!text) {
      if (stop) stop.remove();
      return;
    }
    var label = box.querySelector('.vp-loading-label');
    if (label) label.textContent = text;
    if (!stop) {
      box.querySelector('.vp-loading-box').appendChild(App.UI.el('button.btn.picture-stop', {
        text: 'Stop', type: 'button', onclick: function () { stopAsked = true; }
      }));
    }
  }

  /* ── Saving ───────────────────────────────────────────────────────────── */

  function saveOne(asked) {
    var format = asked.formats[0];
    var first = (inResults() ? { run: App.Results.current(),
                                 stage: { index: App.Results.stage() },
                                 field: App.Results.field().field }
      : inStaged() ? { project: projectName(), mode: 'staged', stage: currentStage() }
      : { project: projectName(), mode: App.state && App.state.mode });
    var name = D.fileName(D.pictureParts(first), format);
    return App.Download.pickFile(name, MIME[format], WINDOW_ID).then(function (target) {
      if (target === App.Download.CANCELLED) { log('note', 'Picture not saved.'); return null; }
      return commonFrame(asked).then(function (frame) {
        if (stopAsked) { log('note', 'Picture not saved.'); return null; }
        var picture = compose(asked, frame);
        if (!picture) {
          log('err', 'There is no picture to save: the viewport has nothing to draw.');
          return null;
        }
        return encode(picture, format).then(function (content) {
          return App.Download.write(target, name, content, MIME[format]);
        }).then(function () {
          log('ok', 'Saved ' + (target && target.name ? target.name : name) + ' ('
                    + picture.page.widthPx + ' x ' + picture.page.heightPx + ' px at '
                    + D.DPI + ' dpi).');
          return 1;
        });
      });
    });
  }

  /* Every picture of the request into `out`. `{count, stopped}`. */
  function saveAll(asked, out) {
    var count = 0, refused = false, frame = null;
    var together = isOnePdf(asked), pages = [];
    function stopped() { return refused || stopAsked; }

    function write(name, content) {
      return out.add(name, content).then(function (done) {
        if (done) count += 1;
        else refused = true;
        progress('Saving pictures… ' + count + ' file' + (count === 1 ? '' : 's'));
        return done;
      });
    }

    function visit(shown) {
      var picture = compose(asked, frame);
      if (!picture) return null;
      var parts = D.pictureParts(shown);
      var chain = Promise.resolve(true);
      asked.formats.forEach(function (format) {
        chain = chain.then(function (go) {
          if (!go || stopped()) return false;
          if (format === 'pdf' && together) {
            return pdfPage(picture).then(function (page) {
              pages.push(page);
              progress('Saving pictures… ' + pages.length + ' page' + (pages.length === 1 ? '' : 's'));
              return true;
            });
          }
          return encode(picture, format).then(function (content) {
            return write(D.fileName(parts, format), content);
          });
        });
      });
      if (asked.csv && shown.values) {
        chain = chain.then(function (go) {
          if (!go || stopped()) return false;
          return write(D.fileName(parts, 'csv'), App.ResultsRender.csv(shown.values, {
            run: shown.run, stage: shown.stage.name
          }));
        });
      }
      return chain;
    }

    function finish() {
      walking = false;
      progress(null);
    }
    return commonFrame(asked).then(function (shared) {
      frame = shared;
      if (stopAsked) return null;
      walking = true;
      progress('Saving pictures…');
      return keepingSelection(function () { return walk(asked, visit, stopped); });
    }).then(function () {
      // What a stop leaves of the pages is still a file, as the files before a stop are.
      if (!pages.length || refused) return null;
      return write(onePdfName(asked), W.pdfDocument(pages));
    }).then(function () {
      finish();
      return { count: count, pages: pages.length, stopped: stopped() };
    }, function (error) {
      finish();
      throw error;
    });
  }

  function saveMany(asked) {
    log('note', 'Choose the folder in the window that opens.');
    return App.Download.pickFolder(WINDOW_ID).then(function (folder) {
      if (folder === App.Download.CANCELLED) { log('note', 'Pictures not saved.'); return null; }
      var out = outlet(folder);
      var release = function () { return App.Download.releaseFolder(folder); };
      return saveAll(asked, out).then(function (result) {
        out.finish();
        log(result.stopped ? 'note' : 'ok', (result.stopped ? 'Stopped after ' : 'Saved ')
            + result.count + ' file' + (result.count === 1 ? '' : 's')
            + (folder && folder.name ? ' in ' + folder.name : '') + '.');
        return release().then(function () { return result.count; });
      }, function (error) {
        return release().then(function () { throw error; });
      });
    });
  }

  /* Every picture in one PDF and nothing else: one file, so it asks for a file. */
  function saveOnePdf(asked) {
    var name = onePdfName(asked);
    return App.Download.pickFile(name, MIME.pdf, WINDOW_ID).then(function (target) {
      if (target === App.Download.CANCELLED) { log('note', 'Pictures not saved.'); return null; }
      return saveAll(asked, {
        add: function (file, content) {
          return App.Download.write(target, file, content, MIME.pdf).then(function () { return true; });
        }
      }).then(function (result) {
        if (!result.count) { log('note', 'Pictures not saved.'); return null; }
        var called = target && target.name ? target.name : name;
        var size = result.pages + ' page' + (result.pages === 1 ? '' : 's');
        log(result.stopped ? 'note' : 'ok', result.stopped ? 'Stopped: ' + called + ' has ' + size + '.'
                                                           : 'Saved ' + called + ' with ' + size + '.');
        return 1;
      });
    });
  }

  /* Must be called straight out of a click or a key press: the first thing it does is open
     a save window. */
  function save(asked) {
    if (walking) {
      log('note', 'Pictures are being saved already.');
      return Promise.resolve(null);
    }
    if (!App.Viewport.pictureView || !App.Viewport.pictureView()) {
      log('err', 'There is no picture to save: the viewport has nothing to draw.');
      return Promise.resolve(null);
    }
    if ((asked.stage === 'all' && !inResults() && !inStaged())
        || (asked.field === 'all' && !inResults())) {
      log('note', 'This tab shows one picture. Every stage is for Staged construction and '
                  + 'Results, every field for Results.');
    }
    // From here, as the window to choose a folder can stay open for as long as the user likes.
    walking = true;
    var onlyOnePdf = isOnePdf(asked) && asked.formats.length === 1 && !asked.csv;
    return (onlyOnePdf ? saveOnePdf(asked) : isMany(asked) ? saveMany(asked) : saveOne(asked)).catch(function (error) {
      log('err', 'The picture could not be saved: ' + error.message);
      return null;
    }).then(function (answer) {
      walking = false;
      return answer;
    });
  }

  /* ── A figure that is already an SVG ──────────────────────────────────── */

  /* The plot along a wall is an SVG string from `results-plot.js`. For a PNG or a PDF it
     is drawn once at 300 dpi; one unit of it is one CSS pixel. */
  function figure(svgString) {
    var across = Number(/ width="(\d+(?:\.\d+)?)"/.exec(svgString)[1]);
    var down = Number(/ height="(\d+(?:\.\d+)?)"/.exec(svgString)[1]);
    var size = D.page(across * D.MM_PER_CSS / 10, across, down);
    return new Promise(function (resolve, reject) {
      var image = new Image();
      image.onload = function () {
        var canvas = document.createElement('canvas');
        canvas.width = size.widthPx;
        canvas.height = size.heightPx;
        var ctx = canvas.getContext('2d');
        ctx.drawImage(image, 0, 0, size.widthPx, size.heightPx);
        var pixels = ctx.getImageData(0, 0, size.widthPx, size.heightPx);
        resolve({ page: size, list: [{ t: 'image', width: size.widthPx, height: size.heightPx,
                                       w: size.widthMm, h: size.heightMm,
                                       rgba: pixels.data }] });
      };
      image.onerror = function () { reject(new Error('The browser could not draw the figure.')); };
      image.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgString);
    });
  }

  function saveFigure(svgString, name, format) {
    return App.Download.pickFile(name, MIME[format], WINDOW_ID).then(function (target) {
      if (target === App.Download.CANCELLED) { log('note', 'Not saved.'); return null; }
      return figure(svgString).then(function (picture) {
        return encode(picture, format);
      }).then(function (content) {
        return App.Download.write(target, name, content, MIME[format]);
      }).then(function () {
        log('ok', 'Saved ' + name + '.');
        return 1;
      });
    }).catch(function (error) {
      log('err', 'The figure could not be saved: ' + error.message);
      return null;
    });
  }

  /* ── For `kratos-cli picture` ─────────────────────────────────────────── */

  /* The CLI has no browser of its own, so it opens this page with no window and a job in
     the address (cli/terminal/pictures.py). The page does what a user would, and posts
     each file to the receiver the CLI holds open. Another address, so `no-cors`: nothing
     is read back, and the last post says how many files there should be.

     Anyone can make a link with a job in it. So the files go only to a receiver on this
     computer, and a job runs only on the server the CLI started for it, which alone knows
     its token: in the GUI a user started, such a link draws nothing. */
  var NOT_A_JOB = 'This page was opened with a picture job that kratos-cli did not give it. '
                + 'Nothing was drawn or sent.';

  /* The job in `search`, `null` with none, or an Error for one that is not the CLI's. */
  function jobFromAddress(search) {
    var text = search ? new URLSearchParams(search).get('picture') : null;
    if (!text) return null;
    try {
      var job = JSON.parse(text);
      var to = new URL(job.receiver);
      if (to.protocol === 'http:' && to.hostname === '127.0.0.1' && typeof job.token === 'string'
          && job.token) return job;
    } catch (error) { /* not a job: refused below */ }
    return new Error(NOT_A_JOB);
  }

  function isOurJob(job) {
    return App.Api.get('/api/files/picture-job/' + encodeURIComponent(job.token)).then(function (answer) {
      return !!(answer && answer.ok);
    }, function () { return false; });
  }

  /* `true` when the job in `search` ran. */
  function startJob(search) {
    var job = jobFromAddress(search);
    if (!job) return Promise.resolve(false);
    var ours = job instanceof Error ? Promise.resolve(false) : isOurJob(job);
    return ours.then(function (yes) {
      if (!yes) { log('err', NOT_A_JOB); return false; }
      return runJob(job).then(function () { return true; });
    });
  }

  function untilBooted() {
    return new Promise(function (resolve) {
      (function check() {
        if (App.PROJECT && App.LivePatches && App.Viewport.pictureView()) resolve();
        else setTimeout(check, 50);
      })();
    });
  }

  function meshed() {
    return new Promise(function (resolve) { App.Viewport.generateMesh(resolve); });
  }

  /* The camera eases to the model for a moment after the page opens, and to a preset view. */
  function cameraStill() {
    return new Promise(function (resolve) {
      (function check() {
        if (App.Viewport.cameraMoving()) setTimeout(check, 50);
        else resolve();
      })();
    });
  }

  /* Puts the screen where the job wants it, in the words a user would type. */
  function prepareJob(job) {
    var ready = App.Viewport.refresh();
    if (job.mode === 'mesh') ready = ready.then(meshed);
    (job.commands || []).forEach(function (line) {
      ready = ready.then(function () { return App.Results.handleCommand(line); });
    });
    return ready.then(function () {
      App.setMode(job.mode);
      if (job.stage) {
        App.state.phase = App.PROJECT.stages[job.stage - 1].id;
        App.Viewport.applyStageVisibility();
      }
      if (job.view) App.Viewport.setView(job.view);
      return cameraStill();
    });
  }

  function runJob(job) {
    var errors = [];
    var said = App.Command.err;
    App.Command.err = function (line) {
      errors.push(line);
      return said.apply(App.Command, arguments);
    };
    function post(path, body) {
      return fetch(job.receiver + path, { method: 'POST', mode: 'no-cors', body: body });
    }
    function refuse() {
      if (errors.length) throw new Error(errors[0]);
    }
    return untilBooted().then(function () {
      return prepareJob(job);
    }).then(function () {
      refuse();
      return saveAll(job.asked, {
        add: function (name, content) {
          return post('/file?name=' + encodeURIComponent(name), content).then(function () {
            return true;
          });
        }
      });
    }).then(function (result) {
      refuse();
      return post('/done', JSON.stringify({ ok: true, count: result.count }));
    }).catch(function (error) {
      return post('/done', JSON.stringify({ ok: false, error: error.message || String(error) }));
    });
  }

  if (typeof window !== 'undefined' && window.addEventListener && typeof location !== 'undefined') {
    window.addEventListener('load', function () { startJob(location.search); });
  }

  /* ── The command ──────────────────────────────────────────────────────── */

  /* `false` for a line that is not this command, as the other commands in the box answer. */
  function command(text) {
    if (String(text || '').trim().split(/\s+/)[0].toLowerCase() !== 'picture') return false;
    var asked = D.parseCommand(text);
    if (App.Command.write) App.Command.write('echo', '> ' + String(text).trim());
    if (asked.error) { log('err', asked.error); return null; }
    if (asked.verb === 'open') return App.PictureDialog.open();
    if (asked.verb === 'copy') return copy(asked);
    return save(asked);
  }

  return {
    compose: compose, commonFrame: commonFrame, paint: paint, encode: encode, readView: readView,
    defaults: defaults,
    canCopy: canCopy, copy: copy, save: save, command: command, isMany: isMany,
    inResults: inResults, inStaged: inStaged, resultStages: resultStages,
    askOverwrite: askOverwrite, outlet: outlet, saveFigure: saveFigure, figure: figure,
    runJob: runJob, jobFromAddress: jobFromAddress, startJob: startJob
  };
})();
