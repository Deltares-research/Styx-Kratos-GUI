/* The viewport, booted (frontend/js/viewport.js).

   test-viewport.js covers the pure helpers the module exports. This boots the module
   itself -- renderer, scene, camera, orbit, pointer -- once, against recorded server
   answers for the test model (fixtures/viewport-payloads.js, written by
   tests/make_viewport_fixture.py), and then drives its public API, checking the
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
    App.setMode = function (mode) { App.state.mode = mode; App.Viewport.setMode(mode); };
    App.viewportContextMenu = function (event, key) { App.__contextKey = key; };
    App.Explorer = { mountTree: function () {}, mountSelection: function () {} };
  }

  function boot() {
    standIns();
    if (!booted) {
      var host = document.createElement('div');
      host.id = 'viewport';
      host.style.cssText = 'position:fixed;left:0;top:0;width:640px;height:480px;';
      // The viewport's own furniture, as frontend/index.html has it.
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

  /* The ID labels number the generated mesh where it is drawn: the Mesh tab. */
  function meshTab() {
    App.state.mode = 'mesh';
    App.Viewport.setMode('mesh');
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

  test('viewport: the numbers show where the mesh is drawn, and not elsewhere', function () {
    var savedMode = App.state.mode;
    return boot().then(function () {
      meshTab();
      return new Promise(function (resolve) { App.Viewport.setLabels('nodes', true, resolve); });
    }).then(function (count) {
      T.ok(count > 0, 'numbered in the Mesh tab');
      App.state.mode = 'structures';
      App.Viewport.setMode('structures');
      T.eq(App.MeshLabels.count('nodes'), 0, 'Structures draws no mesh, so no numbers');
      T.ok(App.Viewport.labelsOn('nodes'), 'but they stay on');
      meshTab();
      return until(function () { return App.MeshLabels.count('nodes') > 0; });
    }).then(function () {
      T.ok(App.MeshLabels.count('nodes') > 0, 'back in the Mesh tab, back on screen');
    }).then(function () {
      App.Viewport.setLabels('nodes', false);
      App.state.mode = savedMode;
      App.Viewport.setMode(savedMode);
    }, function (error) {
      App.Viewport.setLabels('nodes', false);
      App.state.mode = savedMode;
      App.Viewport.setMode(savedMode);
      throw error;
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

  test('viewport: a stage hides what it has not built yet', function () {
    return boot().then(function () {
      var stages = App.PROJECT.stages || [];
      T.ok(stages.length > 1, 'the test model is staged');
      App.state.mode = 'staged';
      App.state.phase = stages[0].id;
      App.Viewport.applyStageVisibility();
      var hidden = App.Stages.hiddenKeys(App.PROJECT, stages[0].id, 'staged');
      var groups = sceneGroups();
      hidden.filter(function (key) { return groups[key]; }).forEach(function (key) {
        T.eq(groups[key].visible, false, key + ' is not built in the first stage');
      });
      App.state.phase = null;
      App.state.mode = 'soil';
      App.Viewport.setMode('soil');
    });
  });

  test('viewport: selected boundary symbols are revealed temporarily and their eyes reset for a new project', function () {
    function restore() {
      App.Viewport.select(null);
      App.Viewport.forgetConditionEyes();
      standIns();
      App.state.mode = 'soil'; App.state.phase = null;
      return App.Viewport.refresh();
    }
    return boot().then(function () {
      var project = JSON.parse(JSON.stringify(P.project));
      var conditions = App.BoundaryConditions;
      project.boundary_conditions = [
        conditions.draftDisplacement(project, 'face', { face: 'bottom' }),
        conditions.draftDisplacement(project, 'face', { face: 'left', roller: true }),
        conditions.draftWaterPressure(project, 'point', {
          points: [[10, -5]], fluid_pressure_type: 'Uniform', value: -100
        }),
        conditions.draftSeepage(project, 'face', { face: 'right' })
      ];
      project.boundary_conditions.forEach(function (record, i) { record.id = 'viewport_condition_' + i; });
      var get = App.Api.get;
      App.Api.get = function (path) {
        return path === '/api/project' ? Promise.resolve(project) : get(path);
      };
      App.state.mode = 'soil'; App.state.phase = null;
      return App.Viewport.refresh();
    }).then(function () {
      var groups = sceneGroups();
      App.PROJECT.boundary_conditions.forEach(function (record) {
        var group = groups[record.id];
        T.ok(group, record.name + ' has a glyph group');
        T.ok(group.children.length > 0);
        T.eq(group.visible, false, 'conditions start hidden');
        App.Viewport.select(record.id);
        T.eq(group.visible, true, 'selecting the condition reveals it');
        App.Viewport.select(null);
        T.eq(group.visible, false, 'deselecting restores the eye');
        App.Viewport.setVisible(record.id, true);
        T.eq(App.Viewport.isVisible(record.id), true);
      });
      App.Viewport.forgetConditionEyes();
      return App.Viewport.refresh();
    }).then(function () {
      var groups = sceneGroups();
      App.PROJECT.boundary_conditions.forEach(function (record) {
        T.eq(App.Viewport.isVisible(record.id), false);
        T.eq(groups[record.id].visible, false);
      });
    }).then(restore, function (error) {
      return restore().then(function () { throw error; });
    });
  });

  ['project', 'geometry'].forEach(function (endpoint) {
    test('viewport: a failed ' + endpoint + ' refresh rejects, reports its cause and removes the progress overlay', function () {
      var timeout = window.setTimeout, clear = window.clearTimeout;
      var stalled, rejectRequest, refresh, rejected, originalGroups, cleared = 0;
      function restore() {
        window.setTimeout = timeout;
        window.clearTimeout = clear;
        standIns();
      }
      return boot().then(function () {
        originalGroups = sceneGroups();
        var get = App.Api.get;
        App.Api.get = function (path) {
          if (path === '/api/' + endpoint) {
            return new Promise(function (resolve, reject) { rejectRequest = reject; });
          }
          return get(path);
        };
        window.setTimeout = function (callback, delay) {
          if (delay === 8000) { stalled = callback; return -1; }
          return timeout.apply(window, arguments);
        };
        window.clearTimeout = function (id) {
          if (id === -1) cleared += 1;
          else clear(id);
        };
        try { refresh = App.Viewport.refresh(); }
        finally { window.setTimeout = timeout; }
        rejected = T.rejects(function () { return refresh; });
        return until(function () { return rejectRequest; }).then(function () {
          T.ok(rejectRequest);
          T.eq(document.getElementById('vp-loading').hidden, false);
          T.ok(stalled);
          stalled();
          T.ok(notes.some(function (line) { return /Still waiting for the model server after 8 s/.test(line); }));
          rejectRequest(new Error('Cannot build ' + endpoint));
          return rejected;
        });
      }).then(function (error) {
        T.eq(error.message, 'Cannot build ' + endpoint);
        T.eq(cleared, 1, 'the stalled-request timer is cleared');
        T.eq(document.getElementById('vp-loading').hidden, true);
        T.ok(notes.some(function (line) { return line === 'err:Cannot build ' + endpoint; }));
        Object.keys(originalGroups).forEach(function (key) {
          T.ok(sceneGroups()[key] === originalGroups[key], key + ' retains its last valid geometry');
        });
      }).then(restore, function (error) {
        if (rejectRequest) rejectRequest(error);
        restore(); throw error;
      });
    });
  });

  test('viewport: custom soil and free contacts join the mode groups and hidden selections lose their box', function () {
    function restore() {
      App.Viewport.select(null);
      standIns();
      App.state.mode = 'soil';
      return App.Viewport.refresh();
    }
    return boot().then(function () {
      var project = JSON.parse(JSON.stringify(P.project));
      var key = 'viewport_fill';
      project.custom_parts = [{ key: key, label: 'Fill', mat: project.materials[0].id,
        recipe: { kind: 'polygon_extrude', vertices: [[0, 0, 0], [4, 0, 0], [0, -3, 0]],
                  extrusion: [0, 0, 1] } }];
      var freeProject = Object.assign({}, project, { beams: [], interfaces: [] });
      var contact = App.Interfaces.draft(freeProject);
      project.interfaces = [contact];
      project.interface_sections = App.Interfaces.sectionsFor(project, contact);
      var geometry = Object.assign({}, P.geometry, {
        sections: P.geometry.sections.concat([
          Object.assign({}, P.geometry.sections[0], { key: key }),
          { key: contact.id, positions: [0, 0, 0, 0, -3, 0],
            indices: [], edges: [0, 0, 0, 0, -3, 0], color: '#123456' }
        ])
      });
      App.Api.get = function (path) {
        return Promise.resolve(path === '/api/project' ? project : geometry);
      };
      return App.Viewport.refresh().then(function () {
        App.state.mode = 'soil'; App.Viewport.setMode('soil');
        T.ok(sceneGroups()[key].visible, 'material-bearing drawn soil is visible with the stack');
        App.Viewport.select(key);
        T.ok(App.Viewport.getScene().children.some(function (child) { return child.type === 'Box3Helper'; }));
        App.Viewport.select(null);
        App.state.mode = 'structures'; App.Viewport.setMode('structures');
        T.ok(sceneGroups()[contact.id], 'the free contact has its own drawable group');
        T.eq(sceneGroups()[contact.id].visible, true, 'the free contact is drawn in structures mode');
        App.Viewport.setVisible('group:interfaces', false);
        T.eq(App.Viewport.isVisible(contact.id), false, 'the contact group controls its free lines');
        T.eq(sceneGroups()[contact.id].visible, false);
        App.Viewport.setVisible('group:interfaces', true);
        T.eq(sceneGroups()[contact.id].visible, true, 'showing contacts restores the drawable group');
        App.Viewport.select(App.BEAMS[0].id);
        T.ok(App.Viewport.getScene().children.some(function (child) { return child.type === 'Box3Helper'; }));
        App.state.mode = 'soil'; App.Viewport.setMode('soil');
        T.eq(sceneGroups()[contact.id].visible, false, 'soil mode excludes contacts');
        T.eq(sceneGroups()[App.BEAMS[0].id].visible, false);
        T.eq(App.Viewport.getScene().children.some(function (child) { return child.type === 'Box3Helper'; }), false);
      });
    }).then(restore, function (error) {
      return restore().then(function () { throw error; });
    });
  });

  test('viewport: a 3D free-interface face is visible with structures and follows its eye', function () {
    function restore() {
      App.Viewport.select(null);
      standIns();
      App.state.mode = 'soil';
      return App.Viewport.refresh();
    }
    return boot().then(function () {
      var project = JSON.parse(JSON.stringify(P.project3d));
      var contact = {
        id: 'free_contact_3d', name: 'Free 3D contact', kind: 'interface',
        section: 'contact', structure: null, points: [[0, -2], [0, -10]],
        side: 'left', active: true
      };
      project.interfaces = [contact];
      var face = {
        key: contact.id, color: '#123456',
        positions: [0, -2, -1, 0, -10, -1, 0, -10, 1],
        indices: [0, 1, 2],
        edges: [0, -2, -1, 0, -10, -1, 0, -10, -1, 0, -10, 1,
                0, -10, 1, 0, -2, -1]
      };
      var geometry = {
        bbox: [-5, -15, -5, 5, 0, 5],
        sections: [face]
      };
      App.Api.get = function (path) {
        return Promise.resolve(path === '/api/project' ? project : geometry);
      };
      return App.Viewport.refresh().then(function () {
        var group = sceneGroups()[contact.id];
        T.ok(group, 'the face section has a scene group');
        T.eq(group.children.some(function (child) { return child.isMesh; }), true,
             'the supplied face, not just its edge, is rendered');
        App.state.mode = 'structures'; App.Viewport.setMode('structures');
        T.eq(group.visible, true, 'free interfaces remain visible in a 3D project');
        App.Viewport.setVisible('group:interfaces', false);
        T.eq(group.visible, false, 'the interface eye hides its face');
        App.Viewport.setVisible('group:interfaces', true);
        T.eq(group.visible, true, 'the interface eye restores its face');
      });
    }).then(restore, function (error) {
      return restore().then(function () { throw error; });
    });
  });

  test('viewport: a 2D drag rewrites rotate into pan before the orbit controller sees it', function () {
    return boot().then(function () {
      var canvas = App.Viewport.getCanvas(), rect = canvas.getBoundingClientRect();
      var event = new MouseEvent('mousedown', { button: 0, buttons: 1,
        clientX: rect.left + 100, clientY: rect.top + 100, bubbles: true });
      App.Viewport.setNavMode('rotate');
      canvas.dispatchEvent(event);
      T.ok(event.shiftKey, 'a section always pans rather than attempting an orbit');
      document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
      App.Viewport.setNavMode('select');
    });
  });

  test('viewport: mesh and label request failures report their cause and hide the progress overlay', function () {
    return boot().then(function () {
      meshTab();
      return new Promise(function (resolve) { App.Viewport.generateMesh(resolve); });
    }).then(function () {
      App.Api.post = function () { return Promise.reject(new Error('Numbering refused')); };
      // Regenerating above discards the old label table.
      return new Promise(function (resolve) { App.Viewport.setLabels('nodes', true, resolve); });
    }).then(function (count) {
      T.eq(count, null);
      T.eq(App.Viewport.labelsOn('nodes'), false);
      T.ok(notes.some(function (line) { return /err:.*Numbering refused/.test(line); }));
      T.eq(document.getElementById('vp-loading').hidden, true);
      App.Api.post = function () { return Promise.reject(new Error('Meshing refused')); };
      return new Promise(function (resolve) { App.Viewport.generateMesh(resolve); });
    }).then(function (stats) {
      T.eq(stats, undefined);
      T.ok(notes.some(function (line) { return /err:.*Meshing refused/.test(line); }));
      T.eq(document.getElementById('vp-loading').hidden, true);
    });
  });

  test('viewport: overlapping imported nodes can be hovered and picked at their fanned screen positions', function () {
    var hint, owned, previousHint;
    function restore() {
      App.Viewport.clearImportedMesh();
      App.Viewport.setLabels('nodes', false);
      if (hint) {
        if (owned) hint.remove(); else hint.textContent = previousHint;
      }
    }
    return boot().then(function () {
      hint = document.getElementById('sb-hint'); owned = !hint;
      if (!hint) {
        hint = document.createElement('span'); hint.id = 'sb-hint';
        document.body.appendChild(hint);
      }
      previousHint = hint.textContent;
      App.state.mode = 'soil'; App.Viewport.setMode('soil');
      App.Viewport.showImportedMesh({
        dimension: 2, bbox: [-5, -5, 0, 15, 5, 0],
        sections: [{ key: 'fan_test', color: '#123456', indices: [],
          edges: [0, 0, 0, 10, 0, 0], node_ids: [1, 2, 3] }],
        node_parts: { nodes: [[1, 0, 0, 0], [2, 0, 0, 0], [3, 10, 0, 0]],
                      parts: [{ name: 'Fan test', kind: 'body', nodes: [1, 2, 3] }] }
      });
      App.Viewport.setView('front');
      return new Promise(function (resolve) { App.Viewport.setLabels('nodes', true, resolve); })
        .then(function () { return new Promise(function (resolve) { setTimeout(resolve, 600); }); });
    }).then(function () {
      var targets = App.NodeParts.screenTargets(App.Viewport.importedNodes(), function (point) {
        return App.Viewport.projectToScreen(point[0], point[1], point[2]);
      }, function (count) { return App.MeshLabels.fanOffsets(count, 14); },
      { 1: true, 2: true, 3: true }, 42);
      var target = targets.filter(function (entry) { return entry.id === 1; })[0];
      T.ok(target && target.fanned, 'coincident nodes are individually pickable');
      var canvas = App.Viewport.getCanvas(), rect = canvas.getBoundingClientRect();
      var event = { clientX: rect.left + target.x, clientY: rect.top + target.y,
                    detail: 1, bubbles: true };
      canvas.dispatchEvent(new MouseEvent('mousemove', event));
      T.ok(/Fan test/.test(hint.textContent), hint.textContent);
      canvas.dispatchEvent(new MouseEvent('click', event));
      T.ok(App.OBJECT_PROPS['node:1'], 'clicking the fanned dot selects that node');
      T.ok(App.Viewport.getOrbit(), 'the viewport retains its controller');
      App.Viewport.rebuildSoil();
      T.ok(App.Viewport.hasImportedMesh(), 'the legacy rebuild hook does not discard the preview');
      App.Viewport.clearImportedMesh();
      T.eq(App.OBJECT_PROPS['node:1'], undefined);
    }).then(restore, function (error) { restore(); throw error; });
  });

  test('viewport: solid soil outlines follow all six measured faces rather than the domain', function () {
    var positions = [];
    [2, 8].forEach(function (x) {
      [-9, -1].forEach(function (y) {
        [3, 7].forEach(function (z) { positions.push(x, y, z); });
      });
    });
    var outlines = App.Viewport.soilFaceOutlines([{ key: 'soil', positions: positions }],
                                                ['soil'], { dimension: 3 });
    T.eq(Object.keys(outlines).sort(), ['back', 'bottom', 'front', 'left', 'right', 'top']);
    T.eq(outlines.bottom, [[2, -9, 3], [8, -9, 3], [8, -9, 7], [2, -9, 7], [2, -9, 3]]);
    T.eq(outlines.left, [[2, -9, 3], [2, -1, 3], [2, -1, 7], [2, -9, 7], [2, -9, 3]]);
    T.eq(outlines.back, [[2, -9, 7], [8, -9, 7], [8, -1, 7], [2, -1, 7], [2, -9, 7]]);
  });

  test('viewport: remeshing refreshes enabled labels and reports numbering and node-index refusals', function () {
    function mesh() { return new Promise(function (resolve) { App.Viewport.generateMesh(resolve); }); }
    function restore() {
      App.Viewport.setLabels('nodes', false);
      App.Viewport.setLabels('elements', false);
      App.PartColors.on.clear();
      standIns();
    }
    return boot().then(function () {
      meshTab();
      var post = App.Api.post;
      App.Api.post = function (path, body) {
        if (path === '/api/mesh') {
          return Promise.resolve(Object.assign({}, P.mesh, {
            log: ['warning: poor element quality', 'error: rejected display element']
          }));
        }
        return post(path, body);
      };
      return mesh();
    }).then(function () {
      T.ok(notes.some(function (line) { return /warning: poor element quality/.test(line); }));
      T.ok(notes.some(function (line) { return /err:error: rejected display element/.test(line); }));
      var key = App.Viewport.coloredPartKeys()[0];
      App.PartColors.on.set([key], true);
      App.Viewport.syncPartColors();
      return new Promise(function (resolve) { App.Viewport.setLabels('nodes', true, resolve); });
    }).then(function () {
      var before = calls.filter(function (call) { return call === 'POST /api/mesh/labels'; }).length;
      return mesh().then(function () {
        return until(function () {
          return calls.filter(function (call) { return call === 'POST /api/mesh/labels'; }).length > before
            && App.MeshLabels.count('nodes') > 0;
        });
      });
    }).then(function () {
      T.ok(App.Viewport.labelsOn('nodes'));
      var post = App.Api.post;
      App.Api.post = function (path, body) {
        if (path === '/api/mesh/labels' || path === '/api/mesh/node-parts') {
          return Promise.reject(new Error('Deck numbering refused'));
        }
        return post(path, body);
      };
      return mesh();
    }).then(function () {
      return until(function () { return !App.Viewport.labelsOn(); });
    }).then(function () {
      T.ok(notes.some(function (line) { return /err:.*Deck numbering refused/.test(line); }));
      return T.rejects(function () { return App.Viewport.nodeParts(); });
    }).then(function (error) {
      T.eq(error.message, 'Deck numbering refused');
      T.eq(App.Viewport.nodePartsLoaded(), null);
      T.eq(document.getElementById('vp-loading').hidden, true);
    }).then(restore, function (error) { restore(); throw error; });
  });

})();
