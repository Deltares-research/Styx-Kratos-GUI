/* Viewport interaction state machine for geometry creation */

var App = window.App || {};

App.DrawInput = (function () {
  var activeMode = null; // 'point', 'line', 'polygon', 'box', 'cylinder', 'load'
  var activeOptions = null;
  var state = 'IDLE'; // 'IDLE', 'PLACING'
  var vertices = [];
  
  var previewGroup = new THREE.Group();
  previewGroup.name = 'draw-preview';
  previewGroup.userData.noPick = true;
  
  var raycaster = new THREE.Raycaster();
  var pointer = new THREE.Vector2();
  var groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  
  var canvas, scene, cam;
  var boundClick, boundMove, boundKey;
  
  function init() {
    canvas = App.Viewport.getCanvas();
    scene = App.Viewport.getScene();
    cam = App.Viewport.getCamera();
    if (previewGroup.parent !== scene) scene.add(previewGroup);
    if (!boundClick) {
      boundClick = onClick;
      boundMove = onMove;
      boundKey = onKey;
    }
  }
  
  function start(mode, options) {
    init();
    if (activeMode) cancel();
    activeMode = mode;
    activeOptions = options || null;
    state = 'PLACING';
    vertices = [];
    updatePreview();
    
    canvas.addEventListener('click', boundClick, true);
    canvas.addEventListener('contextmenu', onContextMenu, true);
    canvas.addEventListener('mousemove', boundMove, true);
    document.addEventListener('keydown', boundKey, true);
    
    canvas.style.cursor = 'crosshair';
    if (App.Command) App.Command.note('Started drawing ' + mode + '. Click to place, right-click/Enter to finish, Esc to cancel.');
  }
  
  function cancel() {
    if (!activeMode) return;
    activeMode = null;
    activeOptions = null;
    state = 'IDLE';
    vertices = [];
    updatePreview();
    
    canvas.removeEventListener('click', boundClick, true);
    canvas.removeEventListener('contextmenu', onContextMenu, true);
    canvas.removeEventListener('mousemove', boundMove, true);
    document.removeEventListener('keydown', boundKey, true);
    
    canvas.style.cursor = '';
    if (App.Command) App.Command.note('Drawing cancelled.');
  }
  
  function commit() {
    var recipe = null;
    
    // A line a tool asked for (a boundary condition's) goes to that tool, not into a
    // drawn solid: the points are what it wants.
    if (activeMode === 'line' && activeOptions && activeOptions.onComplete
        && vertices.length >= 2) {
      var drawn = vertices.slice();
      var done = activeOptions.onComplete;
      finish();
      done(drawn);
      return;
    }
    if (activeMode === 'load' && vertices.length >= ((activeOptions && activeOptions.count) || 2)) {
      var completed = vertices.slice();
      var callback = activeOptions && activeOptions.onComplete;
      finish();
      if (callback) callback(completed);
      return;
    } else if (activeMode === 'point' && vertices.length === 1) {
      recipe = { kind: 'point', position: vertices[0] };
    } else if (activeMode === 'line' && vertices.length >= 2) {
      recipe = { kind: 'line', vertices: vertices };
    } else if (activeMode === 'polygon' && vertices.length >= 3) {
      recipe = { kind: 'polygon', vertices: vertices };
    } else if (activeMode === 'box' && vertices.length >= 2) {
      var v0 = vertices[0], v1 = vertices[1];
      recipe = { kind: 'box', origin: v0, size: [v1[0]-v0[0], v1[1]-v0[1], -5] }; // Height default -5
    } else if (activeMode === 'cylinder' && vertices.length >= 2) {
      var v0 = vertices[0], v1 = vertices[1];
      var r = Math.sqrt(Math.pow(v1[0]-v0[0],2) + Math.pow(v1[1]-v0[1],2));
      recipe = { kind: 'cylinder', center: v0, axis: [0,0,-5], radius: r };
    } else {
      if (App.Command) App.Command.err('Not enough vertices for ' + activeMode);
      return;
    }
    
    if (App.Command) App.Command.note('Committing ' + activeMode + '...');
    
    // Clear state before waiting for response
    var modeName = activeMode;
    finish();
    postRecipe(recipe, modeName);
  }

  function finish() {
    activeMode = null;
    activeOptions = null;
    state = 'IDLE';
    vertices = [];
    updatePreview();
    canvas.removeEventListener('click', boundClick, true);
    canvas.removeEventListener('contextmenu', onContextMenu, true);
    canvas.removeEventListener('mousemove', boundMove, true);
    document.removeEventListener('keydown', boundKey, true);
    canvas.style.cursor = '';
  }
    
  function postRecipe(recipe, modeName) {
    return fetch(App.Api.base + '/api/geometry/create', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(recipe)
    }).then(function(res) {
      if (!res.ok) {
        return res.json().then(function(err) { throw new Error(err.detail || 'Create failed'); });
      }
      return res.json();
    })
    .then(function(data) {
      if (App.Command) App.Command.ok('Created ' + modeName + ' successfully.');
      return App.Model.load().then(function () {
        return App.Viewport.refresh();
      }).then(function () {
        if (App.Explorer && App.state) {
          App.Explorer.mountTree(App.state.mode);
          App.selectObject(data.parts[0].key, 'tree');
        }
      });
    })
    .catch(function(err) {
      if (App.Command) App.Command.err('Error creating geometry: ' + err.message);
    });
  }
  
  function getIntersection(ev) {
    var r = canvas.getBoundingClientRect();
    pointer.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
    pointer.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
    raycaster.setFromCamera(pointer, cam);
    var p = new THREE.Vector3();
    var plane = groundPlane;
    var project = App.PROJECT;
    if (activeMode === 'load' && project) {
      var top = project.domain.y_top;
      if (project.dimension === 2) {
        // The section is the x-y plane at z = 0, so that is what a pick lands on.
        plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
      } else {
        // The ground surface, which with Y up is a plane of constant y.
        plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -top);
      }
    }
    if (raycaster.ray.intersectPlane(plane, p)) {
      if (App.state && App.state.snap) {
        // Snap to grid (1m resolution)
        p.x = Math.round(p.x);
        p.y = Math.round(p.y);
        p.z = Math.round(p.z);
      }
      if (activeMode === 'load' && project && !(activeOptions && activeOptions.pointLoad)) {
        // Loads authored in a section belong to its ground boundary. The pointer's
        // vertical position chooses no extra degree of freedom.
        p.y = project.domain.y_top;
      }
      return [p.x, p.y, p.z];
    }
    return null;
  }
  
  function onClick(ev) {
    if (ev.detail === 0) return;
    ev.preventDefault();
    ev.stopPropagation();
    
    var pt = getIntersection(ev);
    if (!pt) return;
    
    vertices.push(pt);
    
    if (activeMode === 'point' && vertices.length === 1) commit();
    else if (activeMode === 'box' && vertices.length === 2) commit();
    else if (activeMode === 'cylinder' && vertices.length === 2) commit();
    else if (activeMode === 'load' && vertices.length === ((activeOptions && activeOptions.count) || 2)) commit();
    else updatePreview(pt);
  }
  
  /* Right-click finishes an open shape -- a line or a polygon has no fixed vertex count.
     Everything else completes itself on its last click, so there is nothing to finish. */
  function onContextMenu(ev) {
    if (state !== 'PLACING') return;
    ev.preventDefault();
    ev.stopPropagation();
    if (activeMode === 'line' || activeMode === 'polygon') commit();
  }
  
  function handleCommand(text) {
    if (state !== 'PLACING') return false;
    text = (text || '').trim();
    if (!text) return false;
    
    // Check if user is typing a coordinate, e.g. "10 20" or "10 20 5"
    var parts = text.split(/[\s,]+/);
    if (parts.length >= 2) {
      var x = parseFloat(parts[0]);
      var y = parseFloat(parts[1]);
      var z = parts.length > 2 ? parseFloat(parts[2]) : 0;
      if (!isNaN(x) && !isNaN(y) && !isNaN(z)) {
        vertices.push([x, y, z]);
        if (App.Command) App.Command.note('Placed vertex at ' + x + ', ' + y + ', ' + z);
        
        if (activeMode === 'point' && vertices.length === 1) commit();
        else if (activeMode === 'box' && vertices.length === 2) commit();
        else if (activeMode === 'cylinder' && vertices.length === 2) commit();
        else if (activeMode === 'load' && vertices.length === ((activeOptions && activeOptions.count) || 2)) commit();
        else updatePreview();
        return true;
      }
    }
    return false;
  }
  
  function onMove(ev) {
    if (state !== 'PLACING') return;
    ev.preventDefault();
    ev.stopPropagation();
    
    var pt = getIntersection(ev);
    if (pt) updatePreview(pt);
  }
  
  function onKey(ev) {
    if (ev.key === 'Escape') {
      cancel();
    } else if (ev.key === 'Enter') {
      if (activeMode === 'line' || activeMode === 'polygon') {
        ev.preventDefault();
        commit();
      }
    }
  }
  
  function updatePreview(cursorPt) {
    while (previewGroup.children.length > 0) {
      var child = previewGroup.children[0];
      previewGroup.remove(child);
      if (child.geometry) child.geometry.dispose();
      if (child.material) child.material.dispose();
    }
    
    if (!activeMode || vertices.length === 0) {
      App.Viewport.resize(); // trigger render
      return;
    }
    
    var pts = vertices.slice();
    if (cursorPt) pts.push(cursorPt);
    
    var material = new THREE.LineBasicMaterial({ color: 0xffaa00, linewidth: 2 });
    var pMaterial = new THREE.MeshBasicMaterial({ color: 0xffaa00, transparent: true, opacity: 0.3, side: THREE.DoubleSide });
    
    if (activeMode === 'line' || activeMode === 'polygon') {
      var points = pts.map(function(p) { return new THREE.Vector3(p[0], p[1], p[2]); });
      if (activeMode === 'polygon' && pts.length > 2) {
        points.push(points[0]);
        var shape = new THREE.Shape();
        shape.moveTo(points[0].x, points[0].y);
        for(var i=1; i<points.length; i++) shape.lineTo(points[i].x, points[i].y);
        var geometry = new THREE.ShapeGeometry(shape);
        previewGroup.add(new THREE.Mesh(geometry, pMaterial));
      }
      var lineGeo = new THREE.BufferGeometry().setFromPoints(points);
      previewGroup.add(new THREE.Line(lineGeo, material));
      
      // Draw points
      pts.forEach(function(p) {
        var sphere = new THREE.Mesh(new THREE.SphereGeometry(0.2), new THREE.MeshBasicMaterial({color: 0xff0000}));
        sphere.position.set(p[0], p[1], p[2]);
        previewGroup.add(sphere);
      });
    } else if (activeMode === 'box' && pts.length === 2) {
      var v0 = pts[0], v1 = pts[1];
      var w = v1[0] - v0[0];
      var h = v1[1] - v0[1];
      var d = -5;
      var boxGeo = new THREE.BoxGeometry(Math.abs(w), Math.abs(h), Math.abs(d));
      var boxMesh = new THREE.Mesh(boxGeo, pMaterial);
      boxMesh.position.set(v0[0] + w/2, v0[1] + h/2, v0[2] + d/2);
      previewGroup.add(boxMesh);
    } else if (activeMode === 'load' && pts.length === 2) {
      // The load from the first click to the pointer: a line along the section's
      // ground, or the footprint rectangle in plan for a surface load in 3D.
      var a = pts[0], b = pts[1];
      var loadPoints;
      if (App.PROJECT && App.PROJECT.dimension === 2) {
        loadPoints = [new THREE.Vector3(a[0], a[1], a[2]),
                      new THREE.Vector3(b[0], b[1], b[2])];
      } else {
        loadPoints = [
          new THREE.Vector3(a[0], a[1], a[2]), new THREE.Vector3(b[0], a[1], a[2]),
          new THREE.Vector3(b[0], a[1], b[2]), new THREE.Vector3(a[0], a[1], b[2]),
          new THREE.Vector3(a[0], a[1], a[2])
        ];
      }
      previewGroup.add(new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(loadPoints), material));
    } else if (activeMode === 'cylinder' && pts.length === 2) {
      var v0 = pts[0], v1 = pts[1];
      var r = Math.sqrt(Math.pow(v1[0]-v0[0],2) + Math.pow(v1[1]-v0[1],2));
      var h = -5;
      var cylGeo = new THREE.CylinderGeometry(r, r, Math.abs(h), 32);
      var cylMesh = new THREE.Mesh(cylGeo, pMaterial);
      cylMesh.rotation.x = Math.PI/2;
      cylMesh.position.set(v0[0], v0[1], v0[2] + h/2);
      previewGroup.add(cylMesh);
    }
    
    // Force a render
    App.Viewport.resize();
  }
  
  return { start: start, cancel: cancel, handleCommand: handleCommand };
})();
