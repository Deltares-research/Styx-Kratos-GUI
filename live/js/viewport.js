/* ══════════════════════════════════════════════════════════════════
   viewport.js (live) — the three.js scene, drawing server geometry.

   Same public surface as the frozen js/viewport.js, so js/app.js,
   js/explorer.js, js/toolbars.js and js/menubar.js load unchanged and keep
   talking to it exactly as before. What changed is where the shapes come from:
   nothing here invents a box or a cylinder. The model is built by OpenCASCADE
   in the Python worker and arrives as buffers.

   Coordinates are X across, Y up and Z out of plane, metres, y = 0 at the
   ground datum. A 2D model is the x-y plane at z = 0; a 3D model extrudes it
   along Z. The frozen js/orbit.js is hard-wired to a Z-up world, so
   live/js/orbit.js overrides it -- see live/index.html.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Viewport = (function () {

  var renderer, scene, camPersp, camOrtho, cam, orbit, canvas, host;
  var triadGroup;
  var triadRenderer, triadScene, triadCam, triadCanvas;

  /* Which way is up, for every camera in this module -- the scene's and the triad
     widget's alike. The model is Y-up, and the 2D section looks along -z; a camera
     still standing on +z (the frozen mockup's convention) would have its up vector
     parallel to that view direction, which leaves lookAt() with a degenerate basis
     and renders nothing at all. See live/js/orbit.js, which stands the scene camera
     up on the same axis. */
  var WORLD_UP = [0, 1, 0];
  var raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2();
  var groups = {}, boxHelper = null;
  var importedMeshGroup = null;  // a foreign .mdpa's mesh: outside `groups`, so
                                  // rebuildGroups()/refresh() never touches it
  var importedSectionGroups = {};    // section.key -> its own THREE.Group, for the
  var importedSectionBBoxes = {};    // checklist's per-part toggle/frame buttons
  /* section.key -> {node_ids, positions}: the deck's own node numbers, kept so the
     node-ID overlay can label an imported mesh without re-reading the file. */
  var importedSectionNodes = {};
  /* The generated mesh's Kratos numbering, from POST /api/mesh/nodes. Null until the
     labels are asked for -- it costs a full export pass -- and back to null whenever a
     new mesh replaces the one it numbered. */
  var generatedNodeTable = null;
  var hovered = null, selected = null, selectedKeys = [];
  var visible = {};              // key -> bool, driven by the Model explorer
  var modeGroups = {};
  var showGrid = true, gridGroup, boundsGroup, referenceGrid;
  var activeView = 'iso';
  /* The section, not the solid model: the server opens on a plane-strain project
     (server/app/seed.py blank_project), so starting in 3D would only mean drawing a
     view the first /api/geometry answer immediately takes away. */
  var DEFAULT_VIEW_MODE = 'elevation';
  var DEFAULT_DIMENSION = 2;
  var dimension = DEFAULT_DIMENSION;   // 3 = the full solid model, 2 = a planar section

  var needsRender = true, meshBuilt = false;

  var frame = null;              // camera framing derived from the server bbox
  var soilKeys = [];
  var groupKeys = {};            // Model-explorer group row -> the part keys under it

  /* A group row stands for a family of parts: hiding it hides all of them, and
     selecting it highlights all of them. `soil` has always worked this way; the
     rest are named with a prefix no build-payload section key uses. */
  function keysFor(key) {
    if (groupKeys[key]) return groupKeys[key].slice();
    return key ? [key] : [];
  }

  /* Pure, for the same reason computeModeGroups is: this is the map the Model
     explorer's checkboxes are wired through. */
  function computeGroupKeys(soils, customs, loads, beams, anchors, contacts,
                            normalLoads) {
    return {
      soil: (soils || []).slice(),
      'group:custom': (customs || []).slice(),
      'group:loads': (loads || []).slice(),
      'group:sheetpiles': (beams || []).slice(),
      'group:anchors': (anchors || []).slice(),
      // A contact along a pile draws nothing of its own -- it is the pile's line --
      // so this is empty unless the interface was given a line of its own, which the
      // build tags under the interface's own key.
      'group:interfaces': (contacts || []).slice(),
      // Its own row rather than a share of 'group:loads': the Model explorer lists
      // normal loads separately, and an eye has to toggle what its own row names.
      'group:normal_loads': (normalLoads || []).slice()
    };
  }

  function note(text) { if (App.Command) App.Command.note(text); }
  function fail(err) {
    if (App.Command && App.Command.err) App.Command.err(err.message);
    else note('Error: ' + err.message);
  }

  /* ══════════════════════════════════════════════════════════════
     Materials

     One material per drawn section rather than one per colour. The frozen code
     shares a MeshLambertMaterial between parts (js/viewport.js:325-349) and
     setEmissive mutates it in place while traversing, which only works because
     the two demo layers happen to use different materials. With N server
     volumes, hovering one would tint every part that shares its colour.
     ══════════════════════════════════════════════════════════════ */

  var TRANSPARENT = { water: 0.34 };

  function materialFor(section) {
    var opacity = TRANSPARENT[section.key];
    var m = new THREE.MeshLambertMaterial({
      color: new THREE.Color(section.color),
      transparent: opacity !== undefined,
      opacity: opacity === undefined ? 1 : opacity,
      depthWrite: opacity === undefined
    });
    m.userData = { base: m.emissive.clone() };
    return m;
  }

  function edgeMaterial(section) {
    return new THREE.LineBasicMaterial({
      color: new THREE.Color(section.color).multiplyScalar(0.45),
      transparent: true, opacity: 0.5
    });
  }

  function setEmissive(key, hex) {
    var g = groups[key];
    if (!g) return;
    g.traverse(function (o) {
      if (o.material && o.material.emissive && o.material.userData) o.material.emissive.setHex(hex);
    });
    needsRender = true;
  }

  function restoreEmissive(key) {
    var g = groups[key];
    if (!g) return;
    g.traverse(function (o) {
      if (o.material && o.material.emissive && o.material.userData && o.material.userData.base) {
        o.material.emissive.copy(o.material.userData.base);
      }
    });
    needsRender = true;
  }

  /* ══════════════════════════════════════════════════════════════
     Building groups from a payload
     ══════════════════════════════════════════════════════════════ */

  function sectionMesh(section) {
    var mesh = new THREE.Mesh(App.Buffers.geometry(section), materialFor(section));
    mesh.userData.key = section.key;
    return mesh;
  }

  function sectionEdges(section) {
    if (!section.edges.length) return null;
    var lines = new THREE.LineSegments(App.Buffers.edges(section), edgeMaterial(section));
    lines.userData.noPick = true;
    return lines;
  }

  /* Frees GPU memory before a group is replaced. The frozen code never does
     this (js/viewport.js:611-614); with a real backend the model is rebuilt on
     every edit, so leaking a buffer per rebuild adds up quickly. */
  function disposeGroup(group) {
    if (!group) return;
    group.traverse(function (o) {
      if (o.geometry) o.geometry.dispose();
      if (o.material) o.material.dispose();
    });
    // The triad has its own scene, so remove from whichever one adopted the group.
    if (group.parent) group.parent.remove(group);
    else if (scene) scene.remove(group);
  }

  /* Conventional load symbols: the arrow tip is the application point and the shaft
     extends opposite to the force vector. Keeping this as a pure specification makes
     the 2D/3D placement rules testable without a renderer. */
  /* Where a load lies, whichever kind it is. Mirrors `Project.elevation_of` on the
     server: a point or line load carries its own y, and a surface load may leave it
     unset, which means the top of the model -- the reading every such load had before
     the field existed, and which a drawn embankment raises above `domain.y_top`. */
  function loadElevation(load, project) {
    if (load.kind !== 'surface') return load.y;
    if (load.y !== null && load.y !== undefined) return load.y;
    var span = (App.Model && App.Model.extentOf)
      ? App.Model.extentOf(project) : project.domain;
    return span.y_top;
  }

  /* The extent a symbol is sized against: what is drawn, not what is declared.
     `project.domain` is the block the boreholes describe and stays tens of metres
     wide around a 0.1 x 1 m column, so `size` -- the bounding box the viewport is
     framing -- is preferred whenever there is one. In 2D only the two axes on
     screen count: the third is edge-on to the camera. */
  function modelSpan(project, size) {
    var d = project.domain;
    var x = size ? size[0] : d.x1 - d.x0;
    var y = size ? size[1] : d.y_top - d.y_bottom;
    var z = size ? size[2] : d.z1 - d.z0;
    if (project.dimension !== 2) return Math.max(x, y, z);
    // In 2D only the section's own axes count; z is edge-on to the camera.
    return Math.max(x, y);
  }

  function loadGlyphSpec(load, project) {
    var vector = project.dimension === 2
      ? [load.components[0], load.components[1], 0]
      : (load.components || [0, 0, 0]);
    var magnitude = Math.sqrt(vector[0] * vector[0] + vector[1] * vector[1] +
                              vector[2] * vector[2]);
    var direction = magnitude > 0
      ? vector.map(function (component) { return component / magnitude; })
      : [0, -1, 0];
    var span = modelSpan(project, frame && frame.size);
    var spec = {
      kind: load.kind === 'point' ? 'point' : (project.dimension === 2 ? 'line' : 'surface'),
      direction: direction,
      // Purely proportional. A floor in metres made the arrow on a 0.1 x 1 m column
      // three quarters as tall as the column itself.
      length: span > 0 ? span * 0.08 : 1,
      anchors: [], active: load.active !== false, zero: magnitude === 0
    };
    if (load.kind === 'point') {
      spec.anchors.push([load.x, load.y, sectionOffset(project)]);
      return spec;
    }
    function samples(first, last, count) {
      var values = [];
      for (var i = 0; i < count; i++) values.push(first + (last - first) * i / (count - 1));
      return values;
    }
    if (project.dimension === 2) {
      var offset = sectionOffset(project);
      samples(load.x0, load.x1, 5).forEach(function (x) {
        spec.anchors.push([x, load.y, offset]);
      });
      return spec;
    }
    // The load's own elevation, not `d.y_top`: the domain is only the borehole block,
    // so a pad on a drawn embankment was being dragged down onto the borehole soil the
    // moment the model switched to 3D. Mirrors the server's `Project.elevation_of`,
    // including what an unset level means -- see `loadElevation`.
    var y = loadElevation(load, project);
    samples(load.x0, load.x1, 3).forEach(function (x) {
      samples(load.z0, load.z1, 3).forEach(function (z) {
        spec.anchors.push([x, y, z]);
      });
    });
    return spec;
  }

  /* A normal load pushes perpendicular to its own line, so unlike the three vector
     kinds there is no single direction for the whole symbol: each segment carries its
     own. Pure, for the same reason `loadGlyphSpec` is.

     Walking the line in the order its points are stored, a positive pressure pushes to
     the right of the walking direction -- so a line drawn left to right along the top
     of the ground pushes down into it, which is the reading anyone expects. A negative
     pressure flips the arrows. This is the symbol's convention; the sign Kratos itself
     applies comes from the condition's own node order (server/app/kratos.py). */
  function normalLoadGlyphSpec(load, project) {
    var points = load.points || [];
    var span = modelSpan(project, frame && frame.size);
    var length = span > 0 ? span * 0.08 : 1;
    var sign = load.pressure < 0 ? -1 : 1;
    var offset = sectionOffset(project);
    // The two modes are drawn identically: what a load is sized by is a property of
    // the load, not of how it looks, and a symbol that came and went with the mode
    // read as the load itself coming and going. A load in the model is a load on
    // screen, hydrostatic or uniform, whatever its magnitude.
    var spec = { arrows: [], length: length, active: load.active !== false };
    // Arrows and nothing else. A line along the loaded face -- the outline a line
    // load's glyph draws, or the strip the build used to make -- reads as a bar laid
    // on top of the model rather than as a load applied to it.
    for (var i = 1; i < points.length; i += 1) {
      var start = points[i - 1], end = points[i];
      var dx = end[0] - start[0], dy = end[1] - start[1];
      var len = Math.sqrt(dx * dx + dy * dy);
      if (!len) continue;
      var direction = [sign * dy / len, -sign * dx / len, 0];
      // Three to a segment, and the shared vertex is not given two arrows.
      for (var step = i === 1 ? 0 : 1; step <= 2; step += 1) {
        var t = step / 2;
        spec.arrows.push({
          tip: [start[0] + dx * t, start[1] + dy * t, offset],
          direction: direction
        });
      }
    }
    return spec;
  }

  function normalLoadGlyphGroup(load, project) {
    var spec = normalLoadGlyphSpec(load, project);
    var group = new THREE.Group();
    group.name = load.id + '-load-symbols';
    // A normal load's own blue, dark enough to hold its own against the section it is
    // drawn over, and not the red the three vector load kinds share -- this one is a
    // pressure on a face, usually water. Darker than the water slab's #2f8fd8 so the
    // two are still told apart where both are on screen.
    var color = spec.active ? 0x1f6fb0 : 0x777777;

    function mark(object) {
      object.traverse(function (child) {
        child.userData.key = load.id;
        child.userData.loadGlyph = true;
        if (child.material) {
          child.material.depthTest = false;
          child.material.transparent = true;
          child.material.opacity = spec.active ? 1 : 0.45;
        }
        child.renderOrder = 18;
      });
    }

    spec.arrows.forEach(function (entry) {
      var direction = new THREE.Vector3(
        entry.direction[0], entry.direction[1], entry.direction[2]);
      var tip = new THREE.Vector3(entry.tip[0], entry.tip[1], entry.tip[2]);
      var arrow = new THREE.ArrowHelper(
        direction, tip.clone().addScaledVector(direction, -spec.length),
        spec.length, color, spec.length * 0.16, spec.length * 0.09);
      mark(arrow);
      group.add(arrow);
    });

    return group;
  }

  function loadGlyphGroup(load, project) {
    var spec = loadGlyphSpec(load, project);
    var group = new THREE.Group();
    group.name = load.id + '-load-symbols';
    var color = spec.active ? 0xd4342d : 0x777777;

    spec.anchors.forEach(function (anchor) {
      var tip = new THREE.Vector3(anchor[0], anchor[1], anchor[2]);
      var direction = new THREE.Vector3(
        spec.direction[0], spec.direction[1], spec.direction[2]);
      var origin = tip.clone().addScaledVector(direction, -spec.length);
      if (!spec.zero) {
        var arrow = new THREE.ArrowHelper(
          direction, origin, spec.length, color,
          spec.length * 0.16, spec.length * 0.09);
        arrow.traverse(function (object) {
          object.userData.key = load.id;
          object.userData.loadGlyph = true;
          if (object.material) {
            object.material.depthTest = false;
            object.material.transparent = true;
            object.material.opacity = spec.active ? 1 : 0.45;
          }
          object.renderOrder = 18;
        });
        group.add(arrow);
      }
    });

    var markerRadius = spec.length * 0.045;
    if (spec.kind === 'point') {
      var marker = new THREE.Mesh(
        new THREE.SphereGeometry(markerRadius, 10, 6),
        new THREE.MeshBasicMaterial({ color: color, depthTest: false }));
      marker.position.set(spec.anchors[0][0], spec.anchors[0][1], spec.anchors[0][2]);
      marker.userData.key = load.id;
      marker.userData.loadGlyph = true;
      marker.renderOrder = 19;
      group.add(marker);
    } else {
      var outlinePoints;
      if (spec.kind === 'line') {
        outlinePoints = [spec.anchors[0], spec.anchors[spec.anchors.length - 1]];
      } else {
        // The same elevation the arrows use, or the outline stays behind on the
        // borehole soil while the arrows move up onto the embankment.
        var pad = loadElevation(load, project);
        outlinePoints = [
          [load.x0, pad, load.z0], [load.x1, pad, load.z0],
          [load.x1, pad, load.z1], [load.x0, pad, load.z1],
          [load.x0, pad, load.z0]
        ];
      }
      var outline = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(outlinePoints.map(function (point) {
          return new THREE.Vector3(point[0], point[1], point[2]);
        })),
        new THREE.LineBasicMaterial({ color: color, depthTest: false }));
      outline.userData.noPick = true;
      outline.userData.loadGlyph = true;
      outline.renderOrder = 18;
      group.add(outline);
    }
    return group;
  }

  function addLoadGlyphs() {
    function groupFor(id) {
      var group = groups[id];
      if (!group) {
        group = groups[id] = new THREE.Group();
        group.name = id;
        scene.add(group);
      }
      return group;
    }
    ((App.PROJECT && App.PROJECT.loads) || []).forEach(function (load) {
      if (App.Loads && !App.Loads.compatible(load, App.PROJECT)) return;
      groupFor(load.id).add(loadGlyphGroup(load, App.PROJECT));
    });
    // Plane strain only, like the record itself: in 3D there is no line on screen for
    // an arrow to stand on.
    if (!App.PROJECT || App.PROJECT.dimension !== 2) return;
    (App.PROJECT.normal_loads || []).forEach(function (load) {
      if (load.active === false) return;
      groupFor(load.id).add(normalLoadGlyphGroup(load, App.PROJECT));
    });
  }

  function buildGroups(payload) {
    Object.keys(groups).forEach(function (k) { disposeGroup(groups[k]); });
    groups = {};

    payload.sections.forEach(function (section) {
      var g = groups[section.key];
      if (!g) {
        g = groups[section.key] = new THREE.Group();
        g.name = section.key;
        scene.add(g);
      }
      g.add(sectionMesh(section));
      var edges = sectionEdges(section);
      if (edges) g.add(edges);
    });

    addLoadGlyphs();

    groups.mesh = groups.mesh || new THREE.Group();     // filled by generateMesh
    groups.mesh.name = 'mesh';
    if (!groups.mesh.parent) scene.add(groups.mesh);

    Object.keys(groups).forEach(function (k) {
      groups[k].visible = false;
      if (!(k in visible)) visible[k] = true;
    });
  }

  /* Pure so it is directly testable: setMode() only shows a key present in
     modeGroups[mode], so a custom part left out here is created (buildGroups gives
     every section its own THREE.Group) and then invisible forever, in every mode,
     no matter what the eye toggle says. */
  function computeModeGroups(soilKeys, customKeys, simpleExample, loadKeys, memberKeys,
                             normalLoadKeys) {
    customKeys = customKeys || [];
    loadKeys = loadKeys || [];
    // Sheet piles and anchors are sections of their own (server/app/tessellate.py
    // :112-126). Leaving them out of every mode is what kept them invisible.
    memberKeys = memberKeys || [];
    // And a normal load is a section of its own too -- the strip the build draws
    // along its line -- so it needs naming here for the same reason, in the modes a
    // load belongs to.
    loadKeys = loadKeys.concat(normalLoadKeys || []);
    if (simpleExample) {
      var visibleKeys = soilKeys.concat(customKeys);
      return { soil: visibleKeys, structures: visibleKeys.concat(loadKeys, memberKeys),
               mesh: visibleKeys.concat(['mesh'], memberKeys),
               flow: visibleKeys, staged: visibleKeys.concat(memberKeys) };
    }
    return {
      soil:       soilKeys.slice(),
      structures: soilKeys.concat(['wall', 'struts', 'anchors', 'piles'],
                                  loadKeys, memberKeys, customKeys),
      mesh:       ['mesh', 'wall'].concat(memberKeys, customKeys),
      flow:       soilKeys.concat(['water', 'wells', 'wall'], customKeys),
      staged:     ['excavation', 'wall', 'struts', 'anchors', 'water']
                    .concat(loadKeys, memberKeys, customKeys)
    };
  }

  function rebuildModeGroups() {
    soilKeys = (App.LAYERS || []).map(function (l) { return 'soil_' + l.id; });
    var customKeys = ((App.PROJECT && App.PROJECT.custom_parts) || [])
      .map(function (p) { return p.key; });
    var loadKeys = ((App.PROJECT && App.PROJECT.loads) || []).filter(function (load) {
      return !App.Loads || App.Loads.compatible(load, App.PROJECT);
    }).map(function (load) { return load.id; });
    // App.BEAMS/App.ANCHORS are already filtered to the project's dimension by
    // live/js/model.js -- a 3D project keeps its piles saved but draws none.
    var beamKeys = (App.BEAMS || []).map(function (beam) { return beam.id; });
    var anchorKeys = (App.ANCHORS || []).map(function (anchor) { return anchor.id; });
    // Plane strain only, like a free interface: in 3D the record is kept but the
    // build draws nothing for it, so naming it in a mode would name an empty group.
    var normalLoadKeys = (App.PROJECT && App.PROJECT.dimension === 2)
      ? (App.NORMAL_LOADS || []).map(function (item) { return item.id; })
      : [];
    modeGroups = computeModeGroups(
      soilKeys, customKeys, !!(App.PROJECT && App.PROJECT.simple_example), loadKeys,
      beamKeys.concat(anchorKeys), normalLoadKeys);
    var contactKeys = (App.INTERFACES || []).filter(function (item) {
      return !item.structure;
    }).map(function (item) { return item.id; });
    groupKeys = computeGroupKeys(soilKeys, customKeys, loadKeys, beamKeys, anchorKeys,
                                 contactKeys, normalLoadKeys);
  }

  /* ══════════════════════════════════════════════════════════════
     Grid and bounds, sized to the model rather than to constants
     ══════════════════════════════════════════════════════════════ */

  /* The 3D grid is a plane the model stands on, so it is sized to the model. Its cell
     is the unit both grids are drawn in: the 2D one coarsens by whole multiples of it
     so a coarse line is always a line the fine grid also had. */
  function modelGridSpan(frame) { return Math.max(frame.size[0], frame.size[1]) * 1.6; }

  function gridCell(frame) {
    var span = modelGridSpan(frame);
    return span / Math.max(8, Math.round(span / 2.5));
  }

  /* Beyond this the lines are closer than a pixel and cost more than they show. */
  var MAX_GRID_DIVISIONS = 240;
  var GRID_MARGIN = 1.3;                   // covered beyond the view, so a pan is free
  var gridSpec = null;                     // what the 2D grid currently covers

  /* The square of grid that covers the rectangle now on screen.

     Square because the camera can be looking down any of the three plane normals and
     the screen axes then map to different world axes; covering `max(halfW, halfH)`
     costs one extra row of lines and removes the mapping entirely. The centre snaps to
     the cell, so panning slides the view over a fixed lattice instead of dragging the
     lines along with it. */
  function sectionGridSpec(cell, center, halfW, halfH) {
    var c = cell > 0 ? cell : 1;
    var needed = Math.max(halfW, halfH) * GRID_MARGIN * 2;
    while (needed / c > MAX_GRID_DIVISIONS) c *= 2;
    var divisions = Math.ceil(needed / c);
    if (divisions % 2) divisions += 1;      // symmetric about the centre
    return {
      cell: c, divisions: divisions, span: divisions * c,
      u: Math.round(center[0] / c) * c, v: Math.round(center[1] / c) * c,
      center: [center[0], center[1]], halfW: halfW, halfH: halfH
    };
  }

  /* Rebuilt only when the view has actually left what is drawn, or needs a different
     cell: at GRID_MARGIN a drag crosses that boundary rarely, and the geometry is a
     few hundred vertices when it does. */
  function sectionGridNeedsRebuild(current, next) {
    if (!current || current.cell !== next.cell) return true;
    var reach = current.span / 2;
    return Math.abs(next.center[0] - current.u) + next.halfW > reach
        || Math.abs(next.center[1] - current.v) + next.halfH > reach;
  }

  function makeReferenceGrid(span, divisions) {
    if (referenceGrid) {
      gridGroup.remove(referenceGrid);
      referenceGrid.geometry.dispose();
      referenceGrid.material.dispose();
    }
    referenceGrid = new THREE.GridHelper(span, divisions, 0x8fa0b5, 0xb2bdcc);
    referenceGrid.material.transparent = true;
    referenceGrid.material.opacity = 0.55;
    referenceGrid.userData.noPick = true;
    gridGroup.add(referenceGrid);
  }

  /* The in-plane coordinates the camera is centred on: the section is the x-y
     plane, so those are its own two axes. */
  function sectionCenter() {
    return [orbit.target.x, orbit.target.y];
  }

  function visibleHalfExtent() {
    var zoom = cam.zoom || 1;
    return { halfW: (cam.right - cam.left) / 2 / zoom,
             halfH: (cam.top - cam.bottom) / 2 / zoom };
  }

  /* In 2D the grid is not a footprint under the model, it is the paper the section is
     drawn on: it has to reach the edges of the viewport at any pan or zoom, or it
     reads as the edge of the model. Called from the render tick, after the camera has
     been applied, because that is when the visible rectangle is known. */
  function syncSectionGrid() {
    if (dimension !== 2 || !showGrid || !frame || !gridGroup || !cam.isOrthographicCamera) return;
    var view = visibleHalfExtent();
    var next = sectionGridSpec(gridCell(frame), sectionCenter(), view.halfW, view.halfH);
    if (!sectionGridNeedsRebuild(gridSpec, next)) return;
    gridSpec = next;
    makeReferenceGrid(next.span, next.divisions);
    orientReferenceGrid(activeView, frameBBox(), [next.u, next.v]);
  }

  /* The rulers read the same visible rectangle the 2D grid does, so the numbers on
     the edges and the lines under the model can never disagree. Off in 3D: there is no
     one plane for a screen-edge coordinate to be measured in. */
  function syncRulers() {
    if (!App.Ruler) return;
    var on = dimension === 2 && !!cam && !!cam.isOrthographicCamera && !!frame;
    var view = on ? visibleHalfExtent() : { halfW: 0, halfH: 0 };
    App.Ruler.sync({
      active: on,
      center: on ? sectionCenter() : [0, 0],
      halfW: view.halfW, halfH: view.halfH
    });
  }

  /* The extents the frame was built from. gridReference() needs them to place the 3D
     grid under a front or side view, and passing null there is a crash, not a default. */
  function frameBBox() {
    return [frame.center[0] - frame.size[0] / 2, frame.center[1] - frame.size[1] / 2,
            frame.center[2] - frame.size[2] / 2, frame.center[0] + frame.size[0] / 2,
            frame.center[1] + frame.size[1] / 2, frame.center[2] + frame.size[2] / 2];
  }

  /* Back to the model-sized grid: what 3D wants, and what 2D starts from. */
  function resetReferenceGrid() {
    if (!frame || !gridGroup) return;
    var span = modelGridSpan(frame);
    gridSpec = null;
    makeReferenceGrid(span, Math.round(span / gridCell(frame)));
    orientReferenceGrid(activeView, frameBBox());
  }

  function rebuildFrame(bbox) {
    frame = App.Buffers.bounds(bbox);

    disposeGroup(gridGroup);
    disposeGroup(boundsGroup);

    var span = modelGridSpan(frame);

    gridGroup = new THREE.Group();
    gridSpec = null;                       // the 2D grid is re-derived from the camera
    makeReferenceGrid(span, Math.round(span / gridCell(frame)));
    orientReferenceGrid(activeView, bbox);

    boundsGroup = new THREE.Group();
    var box = new THREE.Box3(new THREE.Vector3(bbox[0], bbox[1], bbox[2]),
                             new THREE.Vector3(bbox[3], bbox[4], bbox[5]));
    var helper = new THREE.Box3Helper(box, 0x4a5568);
    helper.material.transparent = true;
    helper.material.opacity = 0.5;
    helper.userData.noPick = true;
    boundsGroup.add(helper);
    // No axis labels on the box: they sit in world space, so they drift away from the
    // model as it is orbited, and they name axes the triad already names in a corner
    // that does not move.

    gridGroup.visible = boundsGroup.visible = showGrid;
    scene.add(gridGroup);
    scene.add(boundsGroup);
    applyRadiusLimits();
  }

  /* Canvas-texture text label facing the camera. */
  function makeLabel(text, x, y, z, scale) {
    var c = document.createElement('canvas');
    c.width = 256; c.height = 64;
    var ctx = c.getContext('2d');
    ctx.font = 'bold 40px Segoe UI, Arial, sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.lineWidth = 7; ctx.strokeStyle = 'rgba(255,255,255,.92)';
    ctx.strokeText(text, 128, 34);
    ctx.fillStyle = '#1d2430';
    ctx.fillText(text, 128, 34);
    var tex = new THREE.CanvasTexture(c);
    tex.minFilter = THREE.LinearFilter;
    var sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true }));
    sp.scale.set(4 * (scale || 1), 1 * (scale || 1), 1);
    sp.position.set(x, y, z);
    sp.userData.noPick = true;
    sp.renderOrder = 10;
    return sp;
  }

  /* ══════════════════════════════════════════════════════════════
     Loading
     ══════════════════════════════════════════════════════════════ */

  function overlay(label) {
    var el = document.getElementById('vp-loading');
    var bar = el.querySelector('.vp-progress i');
    var text = el.querySelector('.vp-loading-label');
    return {
      show: function (msg, pct) {
        el.hidden = false;
        text.textContent = msg;
        bar.style.width = (pct || 0) + '%';
      },
      hide: function () { el.hidden = true; }
    };
  }

  var STALL_MS = 8000;             // how long to wait before saying so

  /* Fetch the project, then its geometry, and rebuild the scene.

     Both steps are logged, and a stall is announced. Before this, a request that
     never came back left a blank viewport, a command log that simply stopped after
     the boot banner, and no way to tell a hung fetch from a modelling bug. */
  function refresh() {
    // No renderer means no scene to build into, and every caller of refresh() is an
    // action that also has non-visual work to do -- the project, the model tree, the
    // property grid. Do that half rather than throwing out of the middle of it.
    if (!renderer) {
      return App.Model.load().then(function () {
        rebuildModeGroups();
        if (App.setMode) App.setMode(App.state.mode || 'soil');
      });
    }

    var ui = overlay();
    ui.show('Building model geometry…', 35);

    var stalled = setTimeout(function () {
      note('Still waiting for the model server after ' + (STALL_MS / 1000)
           + ' s. Is it still running? (Server status is in the bottom-left.)');
    }, STALL_MS);

    return App.Model.load()
      .then(function () {
        rebuildModeGroups();
        return App.Api.get('/api/geometry');
      })
      .then(function (payload) {
        clearTimeout(stalled);
        // Adopt the project's own dimension before anything is framed: a 2D project
        // reloaded from the server must not come up under a free 3D orbit.
        var mode = viewModeOf(App.PROJECT);
        dimension = mode === 'solid' ? 3 : 2;
        App.state.viewMode = mode;
        App.state.dimension = dimension;
        if (App.LivePatches && App.LivePatches.syncViewMode) {
          App.LivePatches.syncViewMode(mode);
        }

        fillTriad();
        // Framed before the groups are built: the load glyphs are sized against the
        // frame, and would otherwise carry the previous model's scale for a frame.
        rebuildFrame(payload.bbox);
        buildGroups(payload);
        meshBuilt = false;
        // The geometry moved, so the mesh that was numbered is gone with it.
        generatedNodeTable = null;
        refreshNodeLabels();

        var triangles = payload.sections.reduce(function (n, s) {
          return n + s.indices.length / 3;
        }, 0);
        note('Model geometry rebuilt: ' + payload.sections.length + ' volumes, '
             + triangles.toLocaleString('en-GB') + ' display triangles.');

        ui.hide();
        // Re-mounts the tree and the property grid against the new layer list.
        App.setMode(App.state.mode);
        setProjection(dimension === 2 ? false : App.state.projection !== false);
        setView('iso');
      })
      .catch(function (err) {
        clearTimeout(stalled);
        ui.hide();
        fail(err);
        throw err;
      });
  }

  /* ══════════════════════════════════════════════════════════════
     Scene assembly
     ══════════════════════════════════════════════════════════════ */

  var lastRendererError = null;

  var SOFTWARE_HELP =
    'No WebGL context — drawing the model on the CPU instead. It looks close but not '
    + 'identical (flat shading, no depth buffer, no axis labels) and it is slower, '
    + 'most noticeably with a fine mesh. Hardware acceleration is usually the fix: '
    + 'Settings → System → "Use graphics acceleration when available", and '
    + 'chrome://gpu says why it was refused.';

  var WEBGL_HELP =
    'The 3D viewport could not start: this browser gave no WebGL context. '
    + 'Chrome no longer falls back to software rendering, so this is usually hardware '
    + 'acceleration being off — turn it on under Settings → System → "Use graphics '
    + 'acceleration when available", then restart the browser. chrome://gpu shows why '
    + 'it was refused. Everything else in the app still works.';

  /* Attempted, not predicted. A support probe asks a throwaway canvas whether WebGL
     works and can disagree with the real construction in either direction -- and it
     leaves a third live context behind on a machine that may already be short of
     them. Constructing the renderer for real cannot be wrong about the renderer.

     A refusal falls back to the CPU renderer rather than to nothing. Both arguments
     are injectable so the fallback is testable without a broken browser. */
  function makeRenderer(build, fallback) {
    // The thrown Error says only "Error creating WebGL context". The *reason* --
    // blocklisted driver, GPU process gone, out of contexts -- arrives on this
    // event as a status message, and is the only thing that tells the two apart.
    var reason = null;
    function onCreationError(ev) { if (ev && ev.statusMessage) reason = ev.statusMessage; }
    if (canvas && canvas.addEventListener) {
      canvas.addEventListener('webglcontextcreationerror', onCreationError, false);
    }
    try {
      return (build || function () {
        return new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
      })();
    } catch (err) {
      lastRendererError = [err && err.message ? String(err.message) : String(err), reason]
        .filter(Boolean).join(' — ');
      return (fallback || function () {
        return App.CanvasRenderer && canvas ? new App.CanvasRenderer(canvas) : null;
      })();
    } finally {
      if (canvas && canvas.removeEventListener) {
        canvas.removeEventListener('webglcontextcreationerror', onCreationError, false);
      }
    }
  }

  /* Says so in the viewport itself as well as the command log: the viewport is where
     the user is looking when they notice nothing is there. */
  function reportNoViewport(message) {
    if (App.Command && App.Command.err) App.Command.err(message);
    var panel = document.getElementById('vp-no-webgl');
    if (!panel && host) {
      panel = document.createElement('div');
      panel.id = 'vp-no-webgl';
      panel.className = 'vp-no-webgl';
      host.appendChild(panel);
    }
    if (panel) panel.textContent = message;
  }

  function init() {
    canvas = document.getElementById('scene');
    host = document.getElementById('viewport');

    renderer = makeRenderer();
    if (renderer && renderer.isSoftware) {
      // A note, not the blocking panel: there is a model to look at now, and a panel
      // over the middle of the viewport would be the thing hiding it.
      if (App.Command && App.Command.note) {
        App.Command.note(SOFTWARE_HELP + (lastRendererError ? ' (' + lastRendererError + ')' : ''));
      }
    }
    if (!renderer) {
      // Return, do not throw. init() is called from the middle of js/app.js boot(),
      // so throwing here also loses the splitters, the mode setup and the model tree
      // -- an empty application window instead of one missing panel.
      reportNoViewport(WEBGL_HELP + (lastRendererError ? ' (' + lastRendererError + ')' : ''));
      // The explorer, the material and soil-layer dialogs and the mesh settings all
      // read App.PROJECT. Load it anyway: everything except the picture still works.
      refresh().catch(fail);
      return;
    }

    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    scene = new THREE.Scene();

    var hemi = new THREE.HemisphereLight(0xffffff, 0x94a1b2, 0.95);
    hemi.position.set(0, 0, 1);
    scene.add(hemi);
    var dir = new THREE.DirectionalLight(0xffffff, 0.72);
    dir.position.set(-40, -60, 90);
    scene.add(dir);
    var dir2 = new THREE.DirectionalLight(0xffffff, 0.24);
    dir2.position.set(70, 40, 30);
    scene.add(dir2);

    rebuildModeGroups();
    rebuildFrame([0, 0, -25, 50, 40, 0]);      // provisional, until the server answers

    camPersp = new THREE.PerspectiveCamera(App.Buffers.FOV_DEG, 1, 0.5, 3000);
    camOrtho = new THREE.OrthographicCamera(-1, 1, 1, -1, -2000, 4000);
    // A section is drawn in parallel projection from the first frame, not from the
    // frame after the project arrives.
    cam = dimension === 2 ? camOrtho : camPersp;

    // Before the controller exists: at the target, listeners run in the order they
    // were registered, and this one has to see the mousedown first to rewrite it.
    canvas.addEventListener('mousedown', function (event) {
      forcePanIfNeeded(event, effectiveNavMode());
    });

    var opening = cameraAngles(activeView, dimension);
    orbit = new App.Orbit(canvas, {
      tx: frame.center[0], ty: frame.center[1], tz: frame.center[2],
      radius: frame.homeRadius, theta: opening.theta, phi: opening.phi,
      minRadius: radiusLimits(frame).min, maxRadius: radiusLimits(frame).max,
      orthoBase: ORTHO_BASE
    });
    orbit.onChange = function () {
      var fixed = clampAngles(orbit, dimension);
      if (fixed.changed) { orbit.theta = fixed.theta; orbit.phi = fixed.phi; }
      needsRender = true;
    };

    // A second WebGL context, and only a decoration: a browser that refuses it can
    // still draw the model.
    try {
      buildTriad();
    } catch (err) {
      note('Axis triad unavailable (' + err.message + '); the viewport is unaffected.');
      triadRenderer = null;
    }
    bindPointer();

    // The edge rulers live in the viewport's DOM, not in the scene: they measure the
    // screen, so they are painted in screen pixels rather than projected like geometry.
    if (App.Ruler) App.Ruler.install(host);
    // Same arrangement, same reason: node numbers are screen furniture over the scene,
    // not objects in it.
    if (App.NodeLabels) App.NodeLabels.install(host);

    if (window.ResizeObserver) new ResizeObserver(resize).observe(host);
    window.addEventListener('resize', resize);
    resize();
    animate();

    refresh().catch(function () { /* already reported to the command log */ });
  }

  /* ── Axis triad (its own tiny renderer) ─────────────────────── */

  /* All three in 3D; in 2D only the two the section is drawn in, which are x and
     y. The camera cannot be turned towards z, so an arrow for it would point at
     nothing. */
  var AXES = [
    { name: 'x', dir: [1, 0, 0], color: 0xd23b3b },
    { name: 'y', dir: [0, 1, 0], color: 0x2f9e44 },
    { name: 'z', dir: [0, 0, 1], color: 0x2b6cd4 }
  ];

  function triadAxes(dim) {
    if (dim !== 2) return AXES.map(function (a) { return a.name; });
    return ['x', 'y'];
  }

  function buildTriad() {
    triadCanvas = document.getElementById('triad');
    triadRenderer = makeRenderer(
      function () {
        return new THREE.WebGLRenderer({ canvas: triadCanvas, antialias: true, alpha: true });
      },
      function () {
        return App.CanvasRenderer ? new App.CanvasRenderer(triadCanvas) : null;
      });
    if (!triadRenderer) return;
    triadRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    triadRenderer.setSize(86, 86, false);
    triadScene = new THREE.Scene();
    triadCam = new THREE.OrthographicCamera(-1.5, 1.5, 1.5, -1.5, -10, 10);

    fillTriad();
  }

  /* Rebuilt rather than hidden, so switching mode cannot leave a stale arrow behind. */
  function fillTriad() {
    if (!triadScene) return;
    disposeGroup(triadGroup);
    triadGroup = new THREE.Group();

    var shown = triadAxes(dimension);
    AXES.forEach(function (a) {
      if (shown.indexOf(a.name) < 0) return;
      var dir = new THREE.Vector3(a.dir[0], a.dir[1], a.dir[2]);
      triadGroup.add(new THREE.ArrowHelper(dir, new THREE.Vector3(0, 0, 0),
                                           1.05, a.color, 0.3, 0.18));
      triadGroup.add(makeLabel(a.name, dir.x * 1.34, dir.y * 1.34, dir.z * 1.34, 0.42));
    });
    triadScene.add(triadGroup);
    needsRender = true;
  }

  /* ── Pointer: hover, pick, context menu, coordinate readout ─── */
  function pickables() {
    var list = [];
    Object.keys(groups).forEach(function (k) {
      if (!groups[k].visible) return;
      groups[k].traverse(function (o) { if (o.isMesh && !o.userData.noPick) list.push(o); });
    });
    return list;
  }

  function pickAt(ev) {
    var r = canvas.getBoundingClientRect();
    pointer.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
    pointer.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
    raycaster.setFromCamera(pointer, cam);
    var hits = raycaster.intersectObjects(pickables(), false);
    return hits.length ? hits[0] : null;
  }

  var groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  var scratch = new THREE.Vector3();



  /* The plane the coordinate readout is taken off. In 2D it has to be the section
     itself: the camera looks straight down that plane's normal, so a ray cast at
     the z = 0 ground runs almost parallel to it and lands 1e14 m away. */
  /* The 2D section is the x-y plane, cut at `offset` along z but drawn at z = 0
     (build._section moves it there), so that is where a pointer lands. */
  function pickPlane(dim) {
    if (dim !== 2) return groundPlane;
    return new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  }

  function bindPointer() {
    canvas.addEventListener('mousemove', function (ev) {
      var hit = pickAt(ev);
      var key = hit ? hit.object.userData.key : null;

      if (key !== hovered) {
        if (hovered && selectedKeys.indexOf(hovered) < 0) restoreEmissive(hovered);
        hovered = key;
        if (hovered && selectedKeys.indexOf(hovered) < 0) setEmissive(hovered, 0x2a3550);
        canvas.style.cursor = hovered ? 'pointer' : '';
      }

      var p = hit ? hit.point : raycaster.ray.intersectPlane(
        pickPlane(dimension), scratch);
      if (p) App.setCoords(p.x, p.y, p.z);
    });

    canvas.addEventListener('mouseleave', function () {
      if (hovered && selectedKeys.indexOf(hovered) < 0) restoreEmissive(hovered);
      hovered = null;
    });

    canvas.addEventListener('click', function (ev) {
      if (ev.detail === 0) return;
      var hit = pickAt(ev);
      App.selectObject(hit ? hit.object.userData.key : null, 'viewport');
    });

    canvas.addEventListener('contextmenu', function (ev) {
      ev.preventDefault();
      var hit = pickAt(ev);
      App.viewportContextMenu(ev, hit ? hit.object.userData.key : null);
    });
  }

  /* ── Selection ──────────────────────────────────────────────── */
  function select(key) {
    if (!scene) return;
    selectedKeys.forEach(function (k) { restoreEmissive(k); });
    var keys = keysFor(key).filter(function (k) { return groups[k] && groups[k].visible; });
    selectedKeys = keys;
    selected = keys.length ? key : null;

    if (boxHelper) { scene.remove(boxHelper); boxHelper.geometry.dispose(); boxHelper = null; }
    if (!keys.length) { needsRender = true; return; }

    var box = new THREE.Box3();
    keys.forEach(function (k) {
      setEmissive(k, 0x1f3b70);
      box.union(new THREE.Box3().setFromObject(groups[k]));
    });
    if (!box.isEmpty()) {
      boxHelper = new THREE.Box3Helper(box, 0x2f7fe0);
      boxHelper.material.depthTest = false;
      boxHelper.renderOrder = 20;
      boxHelper.userData.noPick = true;
      scene.add(boxHelper);
    }
    needsRender = true;
  }

  /* ── Mode / visibility ──────────────────────────────────────── */
  function setMode(mode) {
    var wanted = modeGroups[mode] || [];
    Object.keys(groups).forEach(function (k) {
      groups[k].visible = wanted.indexOf(k) >= 0 && visible[k] !== false;
    });
    if (mode === 'mesh' && !meshBuilt && groups.mesh) groups.mesh.visible = false;
    if (selected && !selectedKeys.every(function (k) { return groups[k] && groups[k].visible; })) select(null);
    needsRender = true;
  }

  function setVisible(key, on) {
    if (groupKeys[key]) {
      groupKeys[key].forEach(function (k) { setVisible(k, on); });
      return;
    }
    // An accepted .mdpa part: no mode gates it (it belongs to no project mode, it is
    // outside `groups` entirely), so the group's own `.visible` is the whole state --
    // unlike a real part, there is no separate `wanted`/`modeGroups` gate to combine
    // it with.
    if (importedSectionGroups[key]) {
      importedSectionGroups[key].visible = on;
      if (!on && selectedKeys.indexOf(key) >= 0) select(null);
      refreshNodeLabels();
      needsRender = true;
      return;
    }
    if (!(key in groups)) return;
    visible[key] = on;
    var wanted = modeGroups[App.state.mode] || [];
    groups[key].visible = on && wanted.indexOf(key) >= 0;
    if (key === 'mesh' && !meshBuilt && groups.mesh) groups.mesh.visible = false;
    if (!on && selectedKeys.indexOf(key) >= 0) select(null);
    // A hidden mesh has no nodes to number: the labels follow the eye, or they float
    // over a part that is no longer there.
    if (key === 'mesh') refreshNodeLabels();
    needsRender = true;
  }

  /* An empty group reads as visible: an unchecked box on a row with nothing under
     it would only be a puzzle. */
  function isVisible(key) {
    if (groupKeys[key]) {
      return groupKeys[key].every(function (k) { return isVisible(k); });
    }
    if (importedSectionGroups[key]) return importedSectionGroups[key].visible;
    return visible[key] !== false;
  }

  /* ── Node-ID labels ─────────────────────────────────────────── */

  /* The overlay is painted in screen pixels (live/js/node-labels.js), so it needs the
     camera's own answer for where a world point lands. Kept here because the camera is
     here, and handed over as a function so that module stays free of three.js. */
  var labelPoint = new THREE.Vector3();
  function projectToScreen(x, y, z) {
    labelPoint.set(x, y, z).project(cam);
    // Past the far plane, or behind a perspective camera -- where project() mirrors the
    // point through the origin and would draw a number on the wrong side of the screen.
    if (labelPoint.z > 1) return null;
    return {
      x: (labelPoint.x * 0.5 + 0.5) * host.clientWidth,
      y: (-labelPoint.y * 0.5 + 0.5) * host.clientHeight,
      depth: labelPoint.z
    };
  }

  /* Every node currently on screen that has a number, from whichever meshes are drawn.
     An imported deck brings its own numbering with it; a generated mesh's has to be
     asked for, so it is only included once `generatedNodeTable` has arrived. */
  function labelledNodes() {
    var list = [];
    if (App.NodeLabels && importedMeshGroup) {
      var sections = Object.keys(importedSectionNodes)
        .filter(function (key) {
          var group = importedSectionGroups[key];
          return group && group.visible;
        })
        .map(function (key) { return importedSectionNodes[key]; });
      list = list.concat(App.NodeLabels.nodesFromSections(sections));
    }
    if (App.NodeLabels && generatedNodeTable && meshBuilt && visible.mesh !== false) {
      list = list.concat(App.NodeLabels.nodesFromTable(generatedNodeTable));
    }
    return list;
  }

  /* Re-gather without re-asking the server: called whenever what is drawn changes. A
     no-op while the labels are off, so nothing pays for a feature it is not using. */
  function refreshNodeLabels() {
    if (!App.NodeLabels || App.NodeLabels.mode() !== 'nodes') return;
    App.NodeLabels.setNodes(labelledNodes());
    needsRender = true;
  }

  /* Turn the node numbers on or off. `done` is called with the plan's own account of
     what fitted on screen (null when switched off or when the numbering failed), which
     is what the caller writes to the command log.

     A generated mesh's numbering is fetched once and cached: it costs a full export
     pass on the server, and nothing but a new mesh can change it. */
  function setNodeLabels(on, done) {
    if (!App.NodeLabels) { if (done) done(null); return; }
    if (!on) {
      App.NodeLabels.setMode(null);
      App.NodeLabels.hide();
      needsRender = true;
      if (done) done(null);
      return;
    }

    App.NodeLabels.setMode('nodes');
    var needsNumbering = meshBuilt && visible.mesh !== false && !generatedNodeTable;
    if (!needsNumbering) {
      App.NodeLabels.setNodes(labelledNodes());
      needsRender = true;
      if (done) done(App.NodeLabels.count());
      return;
    }

    var ui = overlay();
    ui.show('Numbering mesh nodes…', 40);
    App.Api.post('/api/mesh/nodes', meshSettings()).then(function (result) {
      generatedNodeTable = result.nodes || [];
      App.NodeLabels.setNodes(labelledNodes());
      ui.hide();
      needsRender = true;
      if (done) done(App.NodeLabels.count());
    }).catch(function (err) {
      ui.hide();
      // Off again rather than left on and empty: a label layer showing nothing looks
      // like a mesh with no nodes.
      App.NodeLabels.setMode(null);
      App.NodeLabels.hide();
      fail(err);
      if (done) done(null);
    });
  }

  function nodeLabelsOn() {
    return !!(App.NodeLabels && App.NodeLabels.mode() === 'nodes');
  }

  /* Painted from the render tick with the camera that drew the frame, the same way the
     rulers are: a label that lagged a frame behind would slide off its node on every
     orbit. */
  function syncNodeLabels() {
    if (!App.NodeLabels || !host) return;
    App.NodeLabels.sync({
      active: nodeLabelsOn(),
      width: host.clientWidth, height: host.clientHeight,
      project: projectToScreen
    });
  }

  /* ── Mesh generation ────────────────────────────────────────── */

  /* What the mesher is asked for. Its own function because two endpoints take it: the
     mesh itself, and the node numbering the ID labels are drawn from -- and a numbering
     taken from different settings than the mesh on screen would be numbers for a mesh
     nobody is looking at. */
  function meshSettings() {
    return Object.assign({}, App.PROJECT ? App.PROJECT.mesh : {
      element_size: 2.5, order: 2, algorithm_3d: 'delaunay', optimization: 'gmsh',
      smoothing: 10, curvature_points: 16, size_min_factor: 0.05,
      second_order_linear: true
    }, {
      refinements: App.MESH_REFINEMENTS || [],
      volume_keys: Array.isArray(App.MESH_BODY_SELECTION)
        ? App.MESH_BODY_SELECTION.slice()
        : App.MeshSettings.meshTargets(App.PROJECT, App.state.selection, isVisible)
    });
  }

  function generateMesh(done) {
    var ui = overlay();
    ui.show('Meshing with gmsh…', 20);

    var settings = meshSettings();
    App.Api.post('/api/mesh', settings).then(function (result) {
      ui.show('Uploading mesh…', 90);

      disposeGroup(groups.mesh);
      groups.mesh = new THREE.Group();
      groups.mesh.name = 'mesh';
      result.sections.forEach(function (section) {
        var mesh = new THREE.Mesh(App.Buffers.geometry(section), new THREE.MeshLambertMaterial({
          color: 0xd9dee6, transparent: true, opacity: 0.95, side: THREE.DoubleSide,
          polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1
        }));
        mesh.material.userData = { base: mesh.material.emissive.clone() };
        mesh.userData.key = 'mesh';
        groups.mesh.add(mesh);

        var wire = new THREE.LineSegments(
          new THREE.WireframeGeometry(mesh.geometry),
          new THREE.LineBasicMaterial({ color: 0x37474f, transparent: true, opacity: 0.75 })
        );
        wire.userData.noPick = true;
        groups.mesh.add(wire);
      });
      scene.add(groups.mesh);
      if (!(('mesh') in visible)) visible.mesh = true;

      meshBuilt = true;
      // Different mesh, different nodes: whatever was numbered before is now numbering
      // a mesh that no longer exists.
      generatedNodeTable = null;
      App.MESH_STATS = result.stats;
      if (App.Model && App.Model.setMeshStats) App.Model.setMeshStats(result.stats);
      (result.log || []).filter(function (line) { return /warning|error/i.test(line); })
        .slice(-5).forEach(function (line) {
          if (/error/i.test(line) && App.Command.err) App.Command.err(line);
          else note(line);
        });
      ui.hide();
      setMode(App.state.mode);
      needsRender = true;
      // Last, and only if the numbers are on screen: re-numbering means a second trip
      // to the server with its own progress overlay, which must not start under this
      // one's.
      if (nodeLabelsOn()) setNodeLabels(true);
      if (done) done(result.stats);
    }).catch(function (err) {
      ui.hide();
      fail(err);
      if (done) done();
    });
  }

  function hasMesh() { return meshBuilt; }

  /* A previewed .mdpa: drawn straight into the scene, not into `groups`, because it is
     not part of the project -- a project refresh() must not touch it. Its own parts
     are still reachable by key from the Model explorer's "Imported mesh" node
     (`setVisible`/`isVisible` above check `importedSectionGroups` too), which is what
     lets `App.Model.setImportedParts` build that node without this module knowing
     anything about trees. */
  function clearImportedMesh() {
    disposeGroup(importedMeshGroup);
    importedMeshGroup = null;
    importedSectionGroups = {};
    importedSectionBBoxes = {};
    importedSectionNodes = {};
    delete groupKeys['group:imported'];
    needsRender = true;
  }

  /* Double-sided, unlike a project part: a 2D deck is a single sheet of elements with
     whatever winding the file happens to carry, so a front-face-only material leaves
     half of it -- or all of it, seen from behind -- missing. The wireframe is the
     point of looking at an imported deck at all: it is a mesh, so its elements show. */
  function importedSectionMesh(section) {
    var mesh = new THREE.Mesh(App.Buffers.geometry(section), new THREE.MeshLambertMaterial({
      color: new THREE.Color(section.color), side: THREE.DoubleSide,
      polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1
    }));
    mesh.userData.noPick = true;
    return mesh;
  }

  function importedSectionWireframe(mesh) {
    var wire = new THREE.LineSegments(
      new THREE.WireframeGeometry(mesh.geometry),
      new THREE.LineBasicMaterial({ color: 0x37474f, transparent: true, opacity: 0.75 })
    );
    wire.userData.noPick = true;
    return wire;
  }

  /* A deck's beams and trusses are meshed along the soil's own element edges, so their
     line work is exactly coplanar with the wireframe drawn over it -- at equal depth the
     later line loses, and a sheet pile disappears into the mesh it is embedded in. Hence
     no depth test, and drawn last, the way the load glyphs already are.

     `transparent` at full opacity is not a contradiction: the wireframe over them is
     transparent, and three.js draws that whole pass after every opaque object whatever
     its renderOrder -- so an opaque pile is painted over by the mesh it sits in. Sharing
     the pass puts renderOrder back in charge. */
  function importedSectionLines(section) {
    var lines = new THREE.LineSegments(App.Buffers.edges(section),
      new THREE.LineBasicMaterial({ color: new THREE.Color(section.color),
                                    depthTest: false,
                                    transparent: true, opacity: 1 }));
    lines.userData.noPick = true;
    lines.renderOrder = 18;
    return lines;
  }

  function showImportedMesh(model) {
    if (!scene) return;
    clearImportedMesh();
    importedMeshGroup = new THREE.Group();
    importedMeshGroup.name = 'importedMesh';
    (model.sections || []).forEach(function (section) {
      var group = new THREE.Group();
      group.name = section.key;
      if (section.indices && section.indices.length) {
        var mesh = importedSectionMesh(section);
        group.add(mesh);
        group.add(importedSectionWireframe(mesh));
      }
      if (section.edges && section.edges.length) {
        group.add(importedSectionLines(section));
      }
      importedMeshGroup.add(group);
      importedSectionGroups[section.key] = group;
      if (section.bbox) importedSectionBBoxes[section.key] = section.bbox;
      if (section.node_ids) {
        importedSectionNodes[section.key] =
          { node_ids: section.node_ids, positions: section.positions };
      }
    });
    scene.add(importedMeshGroup);
    refreshNodeLabels();
    needsRender = true;

    if (orbit && model.bbox) {
      var bounds = App.Buffers.bounds(model.bbox);
      orbit.animateTo({ tx: bounds.center[0], ty: bounds.center[1], tz: bounds.center[2],
                        radius: bounds.homeRadius });
    }
  }

  function hasImportedMesh() { return !!importedMeshGroup; }

  /* Drops one section entirely -- what "Accept" does with a part the checklist left
     unchecked: not merely hidden, gone, the same as if it had never been drawn. */
  function removeImportedSection(key) {
    disposeGroup(importedSectionGroups[key]);
    delete importedSectionGroups[key];
    delete importedSectionBBoxes[key];
    delete importedSectionNodes[key];
    refreshNodeLabels();
  }

  /* "Imported mesh" in the Model explorer is one group row standing for whichever
     parts were accepted, the same way `computeGroupKeys`'s 'group:custom' etc. stand
     for a family of real project parts -- except there is no project-geometry payload
     to derive this family from, so the accepted list sets it directly. */
  function setImportedGroupKeys(keys) {
    groupKeys['group:imported'] = (keys || []).slice();
  }

  /* The checklist's per-row frame button: the bbox travels with the section (computed
     server-side, local to just that part's own nodes -- see mdpa_import._section_dict),
     so this needs no client-side geometry walk to find it. */
  function frameImportedSection(key) {
    var bbox = importedSectionBBoxes[key];
    if (!orbit || !bbox) return;
    var bounds = App.Buffers.bounds(bbox);
    orbit.animateTo({ tx: bounds.center[0], ty: bounds.center[1], tz: bounds.center[2],
                      radius: Math.max(bounds.homeRadius, 0.5) });
  }

  /* ── Camera presets ─────────────────────────────────────────── */
  /* Angles on the Y-up basis live/js/orbit.js uses: phi is polar from +Y, and
     position = target + r*(sin phi*cos theta, cos phi, sin phi*sin theta).

     `top` looks along the up vector, which is the one direction lookAt() cannot
     resolve -- a degenerate basis renders nothing at all, with no error. It keeps
     the frozen mockup's 0.035 rad tilt for exactly that reason. Nothing else needs
     one: the 2D section looks along -z, which is square to +y. */
  var VIEWS = {
    iso:   { theta: Math.PI * 0.25,  phi: Math.PI * 0.33 },
    front: { theta: Math.PI / 2,     phi: Math.PI / 2 },   // along -z, the section view
    side:  { theta: 0,               phi: Math.PI / 2 },   // along -x
    top:   { theta: Math.PI / 2,     phi: 0.035 }          // (nearly) down the up vector
  };

  /* The one camera a 2D model has: square on to the x-y plane, looking along -z
     with +y up. A true, untilted view -- there is no degenerate direction to dodge
     now that the controller stands the camera up on Y. */
  var SECTION_VIEW = { theta: VIEWS.front.theta, phi: VIEWS.front.phi };

  /* js/orbit.js:40 sets camera.zoom = ORTHO_BASE / radius on an orthographic camera,
     and the frozen resize() pairs that with a fixed half-height of 30. Both numbers
     were chosen for the 3D demo seen through the perspective camera; a flat section
     viewed through them sits at a fraction of the viewport. ORTHO_MARGIN is the
     breathing room around a fitted section. */
  var ORTHO_BASE = 46;
  var ORTHO_HALF_HEIGHT = 30;
  var ORTHO_MARGIN = 1.12;

  /* How far the wheel may dolly, as multiples of the fitted view rather than as
     metres. The frozen pair (8, and 6x the demo frame's 116) is a floor above the
     home radius of anything smaller than a few metres, which left the wheel dead
     and the zoom readout stuck. 0.08 is that same 8 on the demo domain. */
  var MIN_RADIUS_FRACTION = 0.08;
  var MAX_RADIUS_FACTOR = 6;

  function radiusLimits(frame) {
    var home = (frame && frame.homeRadius) || ORTHO_HALF_HEIGHT;
    return { min: home * MIN_RADIUS_FRACTION, max: home * MAX_RADIUS_FACTOR };
  }

  function applyRadiusLimits() {
    if (!orbit || !frame) return;
    var limits = radiusLimits(frame);
    orbit.minRadius = limits.min;
    orbit.maxRadius = limits.max;
    orbit.radius = Math.max(limits.min, Math.min(limits.max, orbit.radius));
  }

  /* The frustum half-height that fits a section at the home radius.

     Visible half-height is s / zoom, i.e. s * radius / ORTHO_BASE, so solving for a
     fit at frame.homeRadius gives a frustum that then dollies correctly with the
     wheel. Width is checked too: a tall, narrow viewport has to widen the frustum
     rather than clip the section's ends. */
  function orthoHalfHeight(frame, aspect) {
    if (!frame) return ORTHO_HALF_HEIGHT;
    // The section's own two axes: x across and y up.
    var span = [frame.size[0], frame.size[1]];
    var needed = Math.max(span[1] / 2, (span[0] / 2) / Math.max(aspect, 1e-4)) * ORTHO_MARGIN;
    return needed * ORTHO_BASE / frame.homeRadius;
  }

  /* Where the section sits along its normal, which is always z. Explicit when the
     project carries an offset; otherwise the middle of the domain's out-of-plane
     depth, which is where a section through a symmetric excavation belongs. */
  function sectionOffset(project) {
    if (project && typeof project.section_offset === 'number') return project.section_offset;
    var d = project && project.domain;
    if (!d) return 0;
    return (d.z0 + d.z1) / 2;
  }

  function cameraAngles(name, dim) {
    if (dim === 2) return { theta: SECTION_VIEW.theta, phi: SECTION_VIEW.phi };
    return VIEWS[name] || VIEWS.iso;
  }

  /* js/orbit.js mutates theta/phi directly on a left-drag (js/orbit.js:96-99) and
     has no locked mode. Rather than fork the frozen controller, the section angles
     are restored from its onChange, which fires after every drag step. Pan and
     dolly leave the angles alone, so both keep working in 2D. */
  function clampAngles(state, dim) {
    if (dim !== 2) return { theta: state.theta, phi: state.phi, changed: false };
    var v = cameraAngles(null, 2);
    return {
      theta: v.theta, phi: v.phi,
      changed: Math.abs(state.theta - v.theta) > 1e-9
            || Math.abs(state.phi - v.phi) > 1e-9
    };
  }

  /* Which plane the reference grid lies in, and where it sits along that plane's
     own normal. In 2D the grid *is* the section, so no view preset can move it: the
     x-y plane at z = 0, where `build._section` put the geometry.

     In 3D each preset backs the grid onto the far face of the model box: the front
     view gets the x-y plane at the near z, the side view the y-z plane at the far x,
     and the top view the x-z plane at the model's floor. */
  function gridReference(name, bbox, section) {
    if (section) return { plane: 'xy', offset: 0 };
    if (name === 'front') return { plane: 'xy', offset: bbox[2] };
    if (name === 'side') return { plane: 'yz', offset: bbox[3] };
    return { plane: 'xz', offset: bbox[1] };
  }

  /* `center` is the in-plane point the grid is drawn around -- the model in 3D, the
     camera's own centre in 2D, where the grid follows the view.

     THREE.GridHelper is built in the x-z plane, so the horizontal grid needs no
     rotation and the two vertical ones are stood up out of it. */
  function orientReferenceGrid(name, bbox, center) {
    if (!referenceGrid) return;
    var ref = gridReference(name, bbox, dimension === 2);
    var c = center || (ref.plane === 'xz' ? [frame.center[0], frame.center[2]]
                     : ref.plane === 'xy' ? [frame.center[0], frame.center[1]]
                                          : [frame.center[1], frame.center[2]]);
    referenceGrid.rotation.set(0, 0, 0);
    if (ref.plane === 'xz') {
      referenceGrid.position.set(c[0], ref.offset, c[1]);
    } else if (ref.plane === 'xy') {
      referenceGrid.rotation.x = Math.PI / 2;
      referenceGrid.position.set(c[0], c[1], ref.offset - 0.02);
    } else {
      referenceGrid.rotation.z = Math.PI / 2;
      referenceGrid.position.set(ref.offset, c[0], c[1]);
    }
  }

  function setView(name) {
    activeView = VIEWS[name] ? name : 'iso';
    if (!orbit || !frame) return;          // no WebGL: nothing to aim
    var v = cameraAngles(name, dimension);
    orientReferenceGrid(activeView, frameBBox());
    orbit.animateTo({ theta: v.theta, phi: v.phi, radius: frame.homeRadius,
                      tx: frame.center[0], ty: frame.center[1], tz: targetZ() });
    needsRender = true;
  }

  /* In 2D the orbit target sits on the section plane -- z = 0, where the geometry
     is -- so panning slides along it instead of drifting the camera off to one side
     of the model. */
  function targetZ() {
    return dimension === 2 ? 0 : frame.center[2];
  }

  function zoomFit() {
    if (!orbit || !frame) return;
    orbit.animateTo({ tx: frame.center[0], ty: frame.center[1], tz: targetZ(),
                      radius: frame.homeRadius });
    needsRender = true;
  }

  function dolly(dir) { if (orbit) orbit.dolly(dir); }

  /* ── Navigation mode: the toolbar's pan / rotate pair ───────────────────────

     js/orbit.js is frozen and has one rule for what a left-drag means
     (js/orbit.js:86): pan if the middle button or Shift is down, orbit otherwise.
     Rather than fork the controller, the toolbar's choice is expressed in that same
     vocabulary -- a mousedown listener registered *before* the controller's marks
     the event as shifted, and orbit.js then does the panning itself. One rule, one
     implementation, and middle-drag and Shift+drag keep working untouched. */
  var navMode = 'rotate';

  function setNavMode(mode) {
    navMode = mode === 'pan' ? 'pan' : 'rotate';
    return navMode;
  }

  function getNavMode() { return navMode; }

  /* There is nothing to orbit in a plane-strain section: js/orbit.js would move the
     angles and clampAngles() would put them straight back. Panning is the only
     navigation a locked camera has, so 2D uses it whatever the toolbar last said. */
  function effectiveNavMode(dim) {
    return (dim === undefined ? dimension : dim) === 2 ? 'pan' : navMode;
  }

  /* Returns whether this drag was converted. Event properties live on the prototype
     as getters, so an own property shadows them for the listeners that run next. */
  function forcePanIfNeeded(event, mode) {
    if (mode !== 'pan' || event.button !== 0 || event.shiftKey) return false;
    try {
      Object.defineProperty(event, 'shiftKey', { value: true, configurable: true });
    } catch (err) {
      return false;
    }
    return event.shiftKey === true;
  }

  function setProjection(persp) {
    if (!camPersp) return;
    cam = persp ? camPersp : camOrtho;
    resize();
    needsRender = true;
  }

  /* In 2D the camera is pinned square on to the x-y section plane and cannot be
     rotated off it, and the reference grid becomes that plane. */
  function setViewMode(mode) {
    dimension = mode === 'solid' ? 3 : 2;
    // A section drawn in perspective is not a section: parallel lines in the plane
    // have to stay parallel for anything measured off it to mean something.
    setProjection(dimension === 2 ? false : App.state.projection !== false);
    // 3D goes back to a grid the size of the model; 2D re-derives one from the camera
    // on the next tick.
    resetReferenceGrid();
    fillTriad();                   // the axes shown depend on the mode
    resize();                      // the frustum depends on the mode
    setView(activeView);
    needsRender = true;
  }

  function is2D() { return dimension === 2; }

  /* The view mode a loaded project is in, defaulting to the section the app opens on.
     There is one 2D view now -- the x-y section -- so the dimension decides it
     outright. */
  function viewModeOf(project) {
    return (project && project.dimension === 3) ? 'solid' : DEFAULT_VIEW_MODE;
  }

  function setGrid(on) {
    showGrid = on;
    if (!gridGroup) return;
    gridGroup.visible = on;
    boundsGroup.visible = on;
    needsRender = true;
  }

  /* ── Render loop ────────────────────────────────────────────── */
  function resize() {
    if (!host || !renderer) return;
    var w = host.clientWidth, h = host.clientHeight;
    if (w < 2 || h < 2) return;
    renderer.setSize(w, h, false);
    camPersp.aspect = w / h;
    camPersp.updateProjectionMatrix();
    var a = w / h;
    var s = dimension === 2 ? orthoHalfHeight(frame, a) : ORTHO_HALF_HEIGHT;
    camOrtho.left = -s * a; camOrtho.right = s * a;
    camOrtho.top = s; camOrtho.bottom = -s;
    camOrtho.updateProjectionMatrix();
    needsRender = true;
  }

  function animate() {
    if (!renderer) return;                 // no context: nothing to drive
    requestAnimationFrame(animate);
    if (orbit.tick()) needsRender = true;
    if (!needsRender) return;
    needsRender = false;

    orbit.apply(cam);
    syncSectionGrid();                     // needs the camera the frame is drawn with
    syncRulers();                          // same: the visible rectangle is known here
    renderer.render(scene, cam);
    syncNodeLabels();                      // over the frame just drawn, with its camera

    if (triadRenderer) {
      triadCam.position.copy(cam.position).sub(orbit.target).normalize().multiplyScalar(4);
      triadCam.up.set(WORLD_UP[0], WORLD_UP[1], WORLD_UP[2]);
      triadCam.lookAt(0, 0, 0);
      triadRenderer.render(triadScene, triadCam);
    }

    App.setZoom(Math.round(frame.homeRadius / orbit.radius * 100));
  }

  return {
    init: init, setMode: setMode, setVisible: setVisible, isVisible: isVisible,
    select: select, setView: setView, zoomFit: zoomFit, dolly: dolly,
    setProjection: setProjection, setGrid: setGrid, syncRulers: syncRulers,
    setViewMode: setViewMode, is2D: is2D,
    setNavMode: setNavMode, getNavMode: getNavMode,
    effectiveNavMode: effectiveNavMode, forcePanIfNeeded: forcePanIfNeeded,
    orthoHalfHeight: orthoHalfHeight, ORTHO_BASE: ORTHO_BASE,
    radiusLimits: radiusLimits, pickPlane: pickPlane, modelSpan: modelSpan,
    sectionGridSpec: sectionGridSpec, sectionGridNeedsRebuild: sectionGridNeedsRebuild,
    MAX_GRID_DIVISIONS: MAX_GRID_DIVISIONS,
    makeRenderer: makeRenderer, WEBGL_HELP: WEBGL_HELP,
    SOFTWARE_HELP: SOFTWARE_HELP,
    sectionOffset: sectionOffset, viewModeOf: viewModeOf,
    DEFAULT_VIEW_MODE: DEFAULT_VIEW_MODE, DEFAULT_DIMENSION: DEFAULT_DIMENSION,
    cameraAngles: cameraAngles, clampAngles: clampAngles, triadAxes: triadAxes,
    WORLD_UP: WORLD_UP,
    generateMesh: generateMesh, hasMesh: hasMesh, resize: resize,
    meshSettings: meshSettings,
    setNodeLabels: setNodeLabels, nodeLabelsOn: nodeLabelsOn,
    refreshNodeLabels: refreshNodeLabels, syncNodeLabels: syncNodeLabels,
    projectToScreen: projectToScreen,
    showImportedMesh: showImportedMesh, clearImportedMesh: clearImportedMesh,
    hasImportedMesh: hasImportedMesh, removeImportedSection: removeImportedSection,
    setImportedGroupKeys: setImportedGroupKeys,
    frameImportedSection: frameImportedSection,
    // js/viewport.js rebuilds its soil boxes from App.LAYERS client-side. Here the soil
    // geometry is the server's, tessellated by /api/geometry, so there is nothing to
    // rebuild locally: a committed change reaches the scene through refresh() instead.
    // Kept because the frozen callers (js/app.js createBorehole, js/command.js borehole)
    // call it unconditionally, and refresh() would re-fetch the project and discard the
    // client-side edit they just made.
    rebuildSoil: function () {},
    refresh: refresh, gridReference: gridReference, computeModeGroups: computeModeGroups,
    computeGroupKeys: computeGroupKeys,
    loadGlyphSpec: loadGlyphSpec, loadGlyphGroup: loadGlyphGroup,
    normalLoadGlyphSpec: normalLoadGlyphSpec,
    getScene: function() { return scene; },
    getCamera: function() { return cam; },
    getCanvas: function() { return canvas; }
  };
})();
