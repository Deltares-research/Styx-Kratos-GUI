/* The viewport, booted (live/js/viewport.js).

   test-viewport.js covers the pure helpers the module exports. This boots the module
   itself -- renderer, scene, camera, orbit, pointer -- once, against recorded server
   answers for the test model (fixtures/viewport-payloads.js, written by
   server/tests/make_viewport_fixture.py), and then drives its public API, checking the
   scene graph it leaves behind. WebGL where the browser offers it, App.CanvasRenderer
   where it does not; both are a real renderer as far as this module is concerned.

   The module keeps its state between tests (it is one viewport), so the tests run in
   the order written and each says what it starts from. The harness restores swapped
   `App` modules after every test, so `boot()` reinstalls the stand-ins each time. */

(function () {

  var P = window.VIEWPORT_PAYLOADS;
  var booted = null;
  var calls = [];
  var notes = [];

  function standIns() {
    App.Api = {
      base: '',
      get: function (path) {
        calls.push('GET ' + path);
        if (path === '/api/project') return Promise.resolve(JSON.parse(JSON.stringify(P.project)));
        if (path === '/api/geometry') return Promise.resolve(P.geometry);
        return Promise.reject(new Error('unexpected GET ' + path));
      },
      post: function (path) {
        calls.push('POST ' + path);
        if (path === '/api/mesh') return Promise.resolve(P.mesh);
        if (path === '/api/mesh/labels') return Promise.resolve(P.labels);
        if (path === '/api/mesh/node-parts') return Promise.resolve(P.nodeParts);
        return Promise.reject(new Error('unexpected POST ' + path));
      }
    };
    App.Command = {
      note: function (t) { notes.push('note:' + t); },
      ok: function (t) { notes.push('ok:' + t); },
      err: function (t) { notes.push('err:' + t); },
      write: function () {}
    };
    App.state = App.state || {};
    App.state.mode = App.state.mode || 'soil';
    App.setCoords = function () {};
    App.setZoom = function () {};
    App.selectObject = function (key) { App.state.selection = key; };
    App.viewportContextMenu = function (event, key) { App.__contextKey = key; };
    App.Explorer = { mountTree: function () {}, mountSelection: function () {} };
  }

  function boot() {
    standIns();
    if (!booted) {
      var host = document.createElement('div');
      host.id = 'viewport';
      host.style.cssText = 'position:fixed;left:0;top:0;width:640px;height:480px;';
      // The viewport's own furniture, as live/index.html has it.
      host.innerHTML =
        '<canvas id="scene" style="width:100%;height:100%;display:block"></canvas>'
        + '<span class="vp-mode-label" id="vp-mode-label"></span>'
        + '<div id="vp-triad"><canvas id="triad"></canvas></div>'
        + '<div id="vp-tooltip" class="vp-tooltip" hidden></div>'
        + '<div id="vp-loading" class="vp-loading" hidden><div class="vp-loading-box">'
        + '<div class="vp-loading-label"></div><div class="vp-progress"><i></i></div>'
        + '</div></div>';
      document.body.appendChild(host);
      App.state = { mode: 'soil' };
      try {
        App.Viewport.init();
        booted = until(function () { return App.PROJECT && App.Viewport.getScene()
          && Object.keys(sceneGroups()).length > 2; });
      } catch (error) {
        // Once, not per test: a viewport that cannot boot fails every case below with
        // the same reason rather than booting again in each.
        booted = Promise.reject(error);
      }
    }
    return booted;
  }

  function until(check, ms) {
    var deadline = Date.now() + (ms || 5000);
    return new Promise(function (resolve, reject) {
      (function poll() {
        var value;
        try { value = check(); } catch (e) { value = null; }
        if (value) return resolve(value);
        if (Date.now() > deadline) return reject(new Error('timed out waiting'));
        setTimeout(poll, 10);
      })();
    });
  }

  function sceneGroups() {
    var out = {};
    App.Viewport.getScene().children.forEach(function (child) {
      if (child.isGroup && child.name) out[child.name] = child;
    });
    return out;
  }

  function soilKey() {
    return (App.PROJECT.soil_body_keys || [])[0];
  }

  test('viewport: it boots against the server and builds one group per part', function () {
    return boot().then(function () {
      T.ok(calls.indexOf('GET /api/project') >= 0 && calls.indexOf('GET /api/geometry') >= 0);
      var groups = sceneGroups();
      P.geometry.sections.forEach(function (section) {
        T.ok(groups[section.key], 'a group for ' + section.key);
      });
      T.ok(App.Viewport.getCamera(), 'a camera');
      T.ok(App.Viewport.getCanvas() === document.getElementById('scene'));
      T.eq(App.Viewport.is2D(), App.PROJECT.dimension === 2);
    });
  });

  test('viewport: a mode shows its own parts and hides the rest', function () {
    return boot().then(function () {
      App.state.mode = 'soil';
      App.Viewport.setMode('soil');
      T.ok(sceneGroups()[soilKey()].visible, 'soil is drawn in Soil mode');
      App.Viewport.setMode('mesh');
      T.eq(sceneGroups().mesh ? sceneGroups().mesh.visible : false, false,
           'no mesh drawn before one is generated');
      App.Viewport.setMode('soil');
    });
  });

  test("viewport: a part's eye hides and shows it, and survives a mode change", function () {
    return boot().then(function () {
      var key = soilKey();
      App.state.mode = 'soil';
      App.Viewport.setVisible(key, false);
      T.eq(App.Viewport.isVisible(key), false);
      T.eq(sceneGroups()[key].visible, false);
      App.Viewport.setMode('soil');
      T.eq(sceneGroups()[key].visible, false, 'the eye wins over the mode');
      App.Viewport.setVisible(key, true);
      T.eq(sceneGroups()[key].visible, true);
    });
  });

  test('viewport: selecting a part outlines it, and selecting nothing removes the outline', function () {
    return boot().then(function () {
      function boxes() {
        return App.Viewport.getScene().children.filter(function (c) { return c.type === 'Box3Helper'; });
      }
      App.Viewport.select(soilKey());
      T.eq(boxes().length, 1);
      App.Viewport.select(null);
      T.eq(boxes().length, 0);
    });
  });

  test('viewport: hiding the selected part drops the selection', function () {
    return boot().then(function () {
      var key = soilKey();
      App.Viewport.select(key);
      App.Viewport.setVisible(key, false);
      T.eq(App.Viewport.getScene().children.filter(function (c) {
        return c.type === 'Box3Helper'; }).length, 0);
      App.Viewport.setVisible(key, true);
    });
  });

  test('viewport: the camera presets, zoom-to-fit and dolly move the camera', function () {
    return boot().then(function () {
      var camera = App.Viewport.getCamera();
      var before = camera.position.clone();
      App.Viewport.dolly(1);
      App.Viewport.zoomFit();
      App.Viewport.setView(App.Viewport.is2D() ? 'front' : 'top');
      return until(function () { return !camera.position.equals(before); }, 3000);
    });
  });

  test('viewport: generating a mesh draws it and colours its parts', function () {
    return boot().then(function () {
      App.state.mode = 'mesh';
      return new Promise(function (resolve) { App.Viewport.generateMesh(resolve); });
    }).then(function (stats) {
      T.ok(stats, 'the stats are handed back: ' + notes.filter(function (n) {
        return /^err:/.test(n); }).join(' | '));
      T.ok(App.Viewport.hasMesh());
      T.ok(calls.indexOf('POST /api/mesh') >= 0);
      App.Viewport.setMode('mesh');
      T.ok(sceneGroups().mesh.visible, 'the mesh is drawn in Mesh mode');
      T.ok(App.Viewport.coloredPartKeys().length > 0, 'its parts can be coloured');
      var key = App.Viewport.coloredPartKeys()[0];
      T.ok(/^#|rgb|^0x/.test(String(App.Viewport.partColor(key))) || App.Viewport.partColor(key),
           'a part has a colour');
      App.Viewport.syncPartColors();
    });
  });

  test('viewport: node and element numbers are fetched once per mesh', function () {
    return boot().then(function () {
      var before = calls.filter(function (c) { return c === 'POST /api/mesh/labels'; }).length;
      return new Promise(function (resolve) { App.Viewport.setLabels('nodes', true, resolve); })
        .then(function (count) {
          T.ok(count > 0, 'nodes are numbered');
          T.ok(App.Viewport.labelsOn('nodes'));
          return new Promise(function (resolve) { App.Viewport.setLabels('elements', true, resolve); });
        }).then(function (count) {
          T.ok(count > 0, 'elements are numbered');
          var after = calls.filter(function (c) { return c === 'POST /api/mesh/labels'; }).length;
          T.eq(after - before, 1, 'the second kind reuses the first numbering');
          App.Viewport.syncLabels();
          App.Viewport.setLabels('nodes', false);
          App.Viewport.setLabels('elements', false);
          T.ok(!App.Viewport.labelsOn());
        });
    });
  });

  test('viewport: a world point projects into the canvas', function () {
    return boot().then(function () {
      var bbox = P.geometry.bbox;
      var centre = [(bbox[0] + bbox[3]) / 2, (bbox[1] + bbox[4]) / 2, (bbox[2] + bbox[5]) / 2];
      App.Viewport.zoomFit();
      return until(function () {
        var at = App.Viewport.projectToScreen(centre[0], centre[1], centre[2]);
        return at && at.x > 0 && at.x < 640 && at.y > 0 && at.y < 480 ? at : null;
      }, 3000);
    });
  });

  test("viewport: which parts a node is in comes from the deck, once", function () {
    return boot().then(function () {
      return App.Viewport.nodeParts();
    }).then(function (index) {
      T.ok(index && App.Viewport.nodePartsLoaded() === index);
      return App.Viewport.nodeParts().then(function (again) {
        T.ok(again === index, 'cached until the mesh changes');
        T.eq(calls.filter(function (c) { return c === 'POST /api/mesh/node-parts'; }).length, 1);
      });
    });
  });

  test('viewport: a node mark is drawn and cleared', function () {
    return boot().then(function () {
      function marks() {
        return App.Viewport.getScene().children.filter(function (c) { return c.isPoints; });
      }
      App.Viewport.markNodes([[0, 0, 0], [1, 1, 0]]);
      T.eq(marks().length, 1);
      App.Viewport.markNodes([[2, 2, 0]]);
      T.eq(marks().length, 1, 'one marking at a time');
      App.Viewport.clearNodeMark();
      T.eq(marks().length, 0);
    });
  });

  test('viewport: an imported deck is drawn outside the project, part by part', function () {
    return boot().then(function () {
      App.Viewport.showImportedMesh(P.imported);
      T.ok(App.Viewport.hasImportedMesh());
      var imported = sceneGroups().importedMesh;
      T.ok(imported, 'drawn in its own group');
      var keys = P.imported.sections.map(function (s) { return s.key; });
      T.eq(imported.children.length, keys.length);
      T.eq(App.Viewport.importedEye(keys[0]), true);
      T.eq(App.Viewport.importedEye('not_imported'), undefined);
      T.ok(App.Viewport.importedNodes(), 'its node index is built');

      App.Viewport.setVisible(keys[0], false);
      T.eq(App.Viewport.isVisible(keys[0]), false);
      App.Viewport.setVisible(keys[0], true);

      App.Viewport.setImportedGroupKeys([keys[0]]);
      App.Viewport.setVisible('group:imported', false);
      T.eq(App.Viewport.isVisible('group:imported'), false, 'the group row hides its parts');
      App.Viewport.setVisible('group:imported', true);
      App.Viewport.frameImportedSection(keys[0]);
    });
  });

  test('viewport: a node of the imported deck can be shown by number', function () {
    return boot().then(function () {
      var index = App.Viewport.importedNodes();
      var node = Object.keys(index.coords)[0];
      T.ok(App.Viewport.showNode(Number(node)), 'a known node is shown');
      T.ok(App.OBJECT_PROPS['node:' + node], 'its properties reach the Selection explorer');
      T.eq(App.Viewport.showNode(-1), false, 'an unknown node is refused');
    });
  });

  test('viewport: an unchecked imported part is dropped, and clearing removes the deck', function () {
    return boot().then(function () {
      var keys = P.imported.sections.map(function (s) { return s.key; });
      App.Viewport.removeImportedSection(keys[keys.length - 1]);
      T.eq(App.Viewport.importedEye(keys[keys.length - 1]), undefined);
      App.Viewport.clearImportedMesh();
      T.ok(!App.Viewport.hasImportedMesh());
      T.ok(!sceneGroups().importedMesh);
      T.eq(App.Viewport.importedNodes(), null);
    });
  });

  test('viewport: projection, grid, navigation and resize can all be switched', function () {
    return boot().then(function () {
      App.Viewport.setProjection(true);
      App.Viewport.setProjection(false);
      App.Viewport.setGrid(false);
      App.Viewport.setGrid(true);
      App.Viewport.setNavMode('pan');
      T.eq(App.Viewport.getNavMode(), 'pan');
      App.Viewport.setNavMode('orbit');
      App.Viewport.resize();
      T.ok(App.Viewport.getCamera());
    });
  });

  test('viewport: the pointer picks the part under it', function () {
    return boot().then(function () {
      App.state.mode = 'soil';
      App.Viewport.setMode('soil');
      App.Viewport.setView(App.Viewport.is2D() ? 'front' : 'top');
      App.Viewport.zoomFit();
      return new Promise(function (resolve) { setTimeout(resolve, 600); });
    }).then(function () {
      var canvas = App.Viewport.getCanvas();
      var r = canvas.getBoundingClientRect();
      var at = { clientX: r.left + r.width / 2, clientY: r.top + r.height / 2,
                 bubbles: true, detail: 1 };
      canvas.dispatchEvent(new MouseEvent('mousemove', at));
      canvas.dispatchEvent(new MouseEvent('click', at));
      T.ok(App.state.selection, 'a click on the model selects what is under it');
      canvas.dispatchEvent(new MouseEvent('contextmenu', at));
      T.eq(App.__contextKey, App.state.selection, 'and the context menu names the same part');
      canvas.dispatchEvent(new MouseEvent('mouseleave', at));
    });
  });

  test('viewport: a phase hides what it has not built yet', function () {
    return boot().then(function () {
      var phases = App.PROJECT.phases || [];
      T.ok(phases.length > 1, 'the test model is staged');
      App.state.mode = 'staged';
      App.state.phase = phases[0].id;
      App.Viewport.applyPhaseVisibility();
      var hidden = App.Phases.hiddenKeys(App.PROJECT, phases[0].id, 'staged');
      var groups = sceneGroups();
      hidden.filter(function (key) { return groups[key]; }).forEach(function (key) {
        T.eq(groups[key].visible, false, key + ' is not built in the first phase');
      });
      App.state.phase = null;
      App.state.mode = 'soil';
      App.Viewport.setMode('soil');
    });
  });

})();
