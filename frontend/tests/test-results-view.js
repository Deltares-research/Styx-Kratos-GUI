/* The contoured mesh on screen (frontend/js/results-view.js).

   The half of Results mode that touches three.js and the DOM. It needs no WebGL to be
   tested: a THREE.Scene is a plain object tree, so `App.Viewport` is replaced with one
   that hands out a real scene, and what `draw` puts in it -- and what the legend, the
   probe and the extremes say -- is read straight back. */

(function () {

  var V = App.ResultsView;

  function section(over) {
    return Object.assign({
      key: 'results:Soil', part: 'Soil', kind: 'continuum',
      node_ids: [1, 2, 3],
      positions: [0, 0, 0, 2, 0, 0, 0, 2, 0],
      indices: [0, 1, 2],
      edge_indices: [],
      wire_indices: [0, 1, 1, 2, 2, 0]
    }, over || {});
  }

  function payload(over) {
    return Object.assign({
      run: 'R', stage: 3,
      mesh: { dimension: 2, bbox: [0, 0, 0, 2, 2, 0], sections: [section()] },
      field: { field: 'uy', label: 'u_y', unit: 'm', location: 'nodes',
               ids: [1, 2, 3], values: [0, -0.5, -1], min: -1, max: 0 },
      displacement: null,
      options: { map: 'rainbow', bands: 32, deform: 0, reversed: false, mesh: false,
                 min: -1, max: 0 }
    }, over || {});
  }

  function stage(fn) {
    var saved = { viewport: App.Viewport, deck: App.Deck };
    var scene = new THREE.Scene();
    var renders = 0;
    var host = document.createElement('div');
    host.id = 'viewport';
    document.body.appendChild(host);
    App.Viewport = {
      getScene: function () { return scene; },
      requestRender: function () { renders += 1; }
    };
    function restore() {
      V.clear();
      host.remove();
      App.Viewport = saved.viewport;
      App.Deck = saved.deck;
    }
    try {
      var out = fn({ scene: scene, host: host, renders: function () { return renders; } });
      restore();
      return out;
    } catch (error) {
      restore();
      throw error;
    }
  }

  function group(scene) {
    return scene.children.filter(function (c) { return c.name === 'results'; })[0];
  }

  test('results view: drawing puts one group in the scene, with the contoured surface', function () {
    stage(function (ctx) {
      V.draw(payload());
      var g = group(ctx.scene);
      T.ok(g, 'a results group was added');
      T.ok(V.isShowing());
      var mesh = g.children.filter(function (c) { return c.isMesh; })[0];
      T.eq(mesh.userData.key, 'results:Soil');
      T.eq(mesh.geometry.getAttribute('color').count, 3, 'one colour per vertex');
      T.ok(ctx.renders() > 0, 'a render was asked for');
    });
  });

  test('results view: element outlines are drawn only when asked for', function () {
    stage(function (ctx) {
      V.draw(payload());
      T.eq(group(ctx.scene).children.length, 1, 'surface only');
      V.draw(payload({ options: Object.assign({}, payload().options, { mesh: true }) }));
      var outline = group(ctx.scene).children.filter(function (c) { return /:mesh$/.test(c.name); })[0];
      T.ok(outline, 'the outline is drawn');
      T.eq(outline.renderOrder, 15, 'below the structural line work');
    });
  });

  test('results view: the zero line goes on along the phreatic line outside the soil',
       function () {
    stage(function (ctx) {
      var pressure = { field: 'pw', label: 'Pore pressure', unit: 'kPa', location: 'nodes',
                       ids: [1, 2, 3], values: [-10, -10, 10], min: -10, max: 10 };
      function beyond() {
        return group(ctx.scene).children.filter(function (c) {
          return c.name === 'results:phreatic-outside';
        })[0];
      }
      // The triangle (0,0) (2,0) (0,2); the line at y = 1 leaves it at x = 1.
      V.draw(payload({ pressure: pressure, phreatic: [[[-3, 1], [5, 1]]] }));
      var line = beyond();
      T.ok(line && line.isLineSegments, 'drawn');
      var at = line.geometry.getAttribute('position');
      T.eq(at.count, 4, 'a piece either side of the soil');
      T.near(at.getX(0), -3, 1e-6);
      T.near(at.getX(1), 0, 1e-6, 'meets the soil where the traced line ends');
      // Out through the hypotenuse, at 45 degrees: within a millimetre or so of it.
      T.near(at.getX(2), 1, 2e-3);
      T.near(at.getX(3), 5, 1e-6);

      V.draw(payload({ phreatic: [[[-3, 1], [5, 1]]] }));
      T.ok(!beyond(), 'not without the zero line it carries on');
    });
  });

  test('results view: the zero pressure line is drawn where the pressure sent crosses zero',
       function () {
    stage(function (ctx) {
      var pressure = { field: 'pw', label: 'Pore pressure', unit: 'kPa', location: 'nodes',
                       ids: [1, 2, 3], values: [-10, -10, 10], min: -10, max: 10 };
      V.draw(payload({ pressure: pressure }));
      var line = group(ctx.scene).children.filter(function (c) {
        return c.name === 'results:Soil:zero-pressure';
      })[0];
      T.ok(line && line.isLineSegments, 'a line was drawn');
      var at = line.geometry.getAttribute('position');
      T.eq(at.count, 2, 'one segment across the one triangle');
      T.near(at.getY(0), 1, 1e-6, 'halfway up, where -10 turns into 10');
      T.near(at.getY(1), 1, 1e-6);
      T.ok(ctx.host.querySelector('.vp-legend-zero'), 'the legend names the line');
      var wide = line.children.filter(function (c) { return c.userData.screenOnly; })[0];
      T.ok(wide && wide.isMesh, 'drawn wide on screen');
      T.eq(wide.geometry.getAttribute('position').count, 4, 'two triangles to a segment');

      V.draw(payload());
      T.ok(!group(ctx.scene).children.some(function (c) { return /zero-pressure/.test(c.name); }),
           'no pressure sent, no line');
      T.ok(!ctx.host.querySelector('.vp-legend-zero'));
    });
  });

  test('results view: the wide zero line reads the canvas size each time it is drawn',
       function () {
    stage(function (ctx) {
      var pressure = { field: 'pw', label: 'Pore pressure', unit: 'kPa', location: 'nodes',
                       ids: [1, 2, 3], values: [-10, -10, 10], min: -10, max: 10 };
      V.draw(payload({ pressure: pressure }));
      var line = group(ctx.scene).children.filter(function (c) {
        return c.name === 'results:Soil:zero-pressure';
      })[0];
      var wide = line.children.filter(function (c) { return c.userData.screenOnly; })[0];
      var resolution = wide.material.uniforms.resolution.value;
      wide.onBeforeRender({ getSize: function (target) { return target.set(800, 600); } });
      T.eq([resolution.x, resolution.y], [800, 600]);
      T.ok(wide.material.uniformsNeedUpdate);
      wide.onBeforeRender({});
      T.eq([resolution.x, resolution.y], [800, 600], 'a renderer with no size changes nothing');
    });
  });

  test('results view: a vector field is drawn as arrows over the shading', function () {
    stage(function (ctx) {
      function arrows() {
        return group(ctx.scene).children.filter(function (c) {
          return c.name === 'results:arrows';
        })[0];
      }
      var vectors = { field: 'flux', label: '|q|', unit: 'm/s',
                      ids: [1, 2, 3], values: [[1, 0, 0], [0, 1, 0], [0, 0, 0]], max: 1 };
      V.draw(payload({ vectors: vectors }));
      var drawnArrows = arrows();
      T.ok(drawnArrows && drawnArrows.isLineSegments, 'drawn');
      T.eq(drawnArrows.renderOrder, 19, 'over the shading');
      var at = drawnArrows.geometry.getAttribute('position');
      T.ok(at.count > 0 && at.count % 2 === 0, 'whole segments');
      T.near(at.getX(0), 0, 1e-6, 'the first arrow starts at node 1');
      T.near(at.getY(0), 0, 1e-6);
      T.ok(/\|q\| up to/.test(document.getElementById('vp-legend').textContent),
           'the legend names it');

      V.draw(payload({ vectors: Object.assign({}, vectors, {
        values: [[0, 0, 0], [0, 0, 0], [0, 0, 0]] }) }));
      T.ok(!arrows(), 'a field that is zero everywhere has no arrows');
    });
  });

  test('results view: the legend data says what the legend on screen says', function () {
    stage(function () {
      T.eq(V.legendData(), null, 'nothing drawn, nothing to say');
      V.draw(payload());
      var data = V.legendData();
      T.eq(data.title, 'u_y');
      T.eq(data.unit, 'm');
      T.eq(data.stage, 3);
      T.eq(data.options.map, 'rainbow');
      T.ok(data.range, 'with the lines the range is given in');
    });
  });

  test('results view: a structure is drawn as lines above the surface', function () {
    stage(function (ctx) {
      V.draw(payload({ mesh: { bbox: [0, 0, 0, 2, 2, 0], sections: [
        section({ key: 'results:Wall', part: 'Wall', indices: [], edge_indices: [0, 1] })] } }));
      var lines = group(ctx.scene).children[0];
      T.ok(lines.isLineSegments);
      T.eq(lines.renderOrder, 20);
    });
  });

  test('results view: the surface, outline and lines share one position buffer', function () {
    stage(function (ctx) {
      V.draw(payload({
        options: Object.assign({}, payload().options, { mesh: true }),
        mesh: { bbox: [0, 0, 0, 2, 2, 0], sections: [section({ edge_indices: [0, 1] })] }
      }));
      var attrs = group(ctx.scene).children.map(function (c) {
        return c.geometry.getAttribute('position');
      });
      T.eq(attrs.length, 3);
      T.ok(attrs[0] === attrs[1] && attrs[1] === attrs[2],
           'one buffer, so a deformation moves all three together');
    });
  });

  test('results view: a deformation factor moves the vertices by that many displacements', function () {
    stage(function (ctx) {
      V.draw(payload({
        displacement: { ids: [1, 2, 3], values: [[0, -0.1, 0], [0, -0.1, 0], [0, -0.1, 0]] },
        options: Object.assign({}, payload().options, { deform: 10 })
      }));
      var y = group(ctx.scene).children[0].geometry.getAttribute('position').array;
      T.near(y[1], -1, 1e-6, 'node 1 down by 10 x 0.1');
      T.near(y[4], -1, 1e-6);
      T.near(y[7], 1, 1e-6, 'node 3 from 2 down to 1');
    });
  });

  test('results view: with no displacement to deform by, the factor is ignored', function () {
    stage(function (ctx) {
      V.draw(payload({ options: Object.assign({}, payload().options, { deform: 50 }) }));
      var y = group(ctx.scene).children[0].geometry.getAttribute('position').array;
      T.eq(Array.prototype.slice.call(y), [0, 0, 0, 2, 0, 0, 0, 2, 0]);
    });
  });

  test("results view: 'auto' scales the largest displacement to a readable size", function () {
    stage(function (ctx) {
      var displacement = { ids: [1, 2, 3], values: [[0, -0.001, 0], [0, 0, 0], [0, 0, 0]] };
      V.draw(payload({ displacement: displacement,
                       options: Object.assign({}, payload().options, { deform: 'auto' }) }));
      var y = group(ctx.scene).children[0].geometry.getAttribute('position').array;
      var factor = App.ResultsRender.autoFactor(0.001, [0, 0, 0, 2, 2, 0]);
      T.ok(factor > 1, 'a millimetre on a 2 m model is magnified');
      T.near(y[1], -0.001 * factor, 1e-6);
    });
  });

  test('results view: clearing removes and disposes everything', function () {
    stage(function (ctx) {
      V.draw(payload());
      var disposed = 0;
      group(ctx.scene).traverse(function (c) {
        if (c.geometry) c.geometry.addEventListener('dispose', function () { disposed += 1; });
      });
      V.clear();
      T.eq(group(ctx.scene), undefined);
      T.ok(!V.isShowing());
      T.eq(disposed, 1);
    });
  });

  test('results view: the legend names the field, its unit and the stage, escaped', function () {
    stage(function (ctx) {
      var p = payload();
      p.field = Object.assign({}, p.field, { label: '<b>u</b>', unit: 'm' });
      V.draw(p);
      var legend = document.getElementById('vp-legend');
      T.ok(legend && !legend.hidden, 'the legend is shown');
      T.eq(legend.querySelector('.vp-legend-title').textContent, '<b>u</b>',
           'markup in a label is text, not HTML');
      T.eq(legend.querySelector('.vp-legend-unit').textContent, 'm');
      T.ok(/stage 3/.test(legend.querySelector('.vp-legend-foot').textContent));
      T.eq(legend.querySelectorAll('li').length, 7, 'seven ticks');
      V.clear();
      T.ok(legend.hidden, 'cleared with the drawing');
    });
  });

  test('results view: the probe reports the nearest node, its part and value', function () {
    stage(function () {
      V.draw(payload());
      var found = V.nearest({ x: 1.9, y: 0.1, z: 0 });
      T.eq(found.node, 2);
      T.eq(found.part, 'Soil');
      T.eq(found.value, -0.5);
      T.ok(/node 2 · Soil · u_y .*-0\.5.* m/.test(V.describeAt({ x: 1.9, y: 0.1, z: 0 })),
           V.describeAt({ x: 1.9, y: 0.1, z: 0 }));
    });
  });

  test('results view: with nothing drawn the probe says nothing', function () {
    stage(function () {
      T.eq(V.describeAt({ x: 0, y: 0, z: 0 }), '');
      T.eq(V.nearest({ x: 0, y: 0, z: 0 }), null);
    });
  });

  test('results view: the extremes are where the smallest and largest values are', function () {
    stage(function () {
      V.draw(payload());
      var e = V.extremes();
      T.eq(e.min.node, 3);
      T.eq(e.min.value, -1);
      T.eq(e.min.point, [0, 2, 0]);
      T.eq(e.max.node, 1);
    });
  });

  test("results view: each part follows its row's eye in the Model explorer", function () {
    stage(function (ctx) {
      App.Viewport.importedEye = function () { return true; };
      App.Deck = { resultShown: function (part) { return part !== 'Soil'; } };
      V.draw(payload());
      T.eq(group(ctx.scene).children[0].visible, false, 'Soil is switched off');
      App.Deck.resultShown = function () { return true; };
      V.syncVisibility();
      T.eq(group(ctx.scene).children[0].visible, true);
    });
  });

  test('results view: a payload missing its mesh or field draws nothing', function () {
    stage(function (ctx) {
      V.draw(payload({ mesh: null }));
      V.draw(payload({ field: null }));
      T.eq(group(ctx.scene), undefined);
    });
  });

})();
