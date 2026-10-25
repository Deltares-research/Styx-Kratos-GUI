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
   frontend/js/orbit.js overrides it -- see frontend/index.html.
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
     and renders nothing at all. See frontend/js/orbit.js, which stands the scene camera
     up on the same axis. */
  var WORLD_UP = [0, 1, 0];
  var raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2();
  var groups = {}, boxHelper = null;
  var importedMeshGroup = null;  // a foreign .mdpa's mesh: outside `groups`, so
                                  // rebuildGroups()/refresh() never touches it
  var importedEyes = {};             // section.key -> false when its eye is off
  var importedSectionParts = {};     // section.key -> the deck part it draws
  var importedSectionGroups = {};    // section.key -> its own THREE.Group, for the
  var importedSectionBBoxes = {};    // checklist's per-part toggle/frame buttons
  /* section.key -> the payload section itself, kept for its `node_ids` and `elements`:
     the deck's own numbering, so the ID overlay can label an imported mesh without
     re-reading the file. */
  var importedSectionLabels = {};
  /* The generated mesh's Kratos numbering, from POST /api/mesh/labels: {nodes, elements},
     each a table of [id, x, y, z]. Null until the labels are asked for -- it costs a full
     export pass -- and back to null whenever a new mesh replaces the one it numbered. */
  var generatedLabels = null;
  var hovered = null, selected = null, selectedKeys = [];
  var visible = {};              // key -> bool, driven by the Model explorer
  var modeGroups = {};
  var showGrid = true, gridGroup, boundsGroup, referenceGrid;
  var activeView = 'iso';
  /* The section, not the solid model: the server opens on a plane-strain project
     (core/model/templates.py blank_project), so starting in 3D would only mean drawing a
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
                            normalLoads, conditions) {
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
      'group:normal_loads': (normalLoads || []).slice(),
      'group:conditions': (conditions || []).slice()
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
      // A badge's letter is a texture of its own (labelInterfaceFaces).
      if (o.material && o.material.map) o.material.map.dispose();
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
     `project.domain` is the block the layers fill and stays tens of metres
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
    // The load's own elevation, not `d.y_top`: the domain is only the layer block,
    // so a pad on a drawn embankment was being dragged down onto the layer soil the
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
     pressure flips the arrows. The deck presses the same way: the exporter writes each
     segment against the drawn line, because Kratos presses to the left of a
     condition's own node order (core/kratos/writer.py, `_normal_load_conditions`), and
     warns where the arrows point out of the soil. */
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
        // layer soil while the arrows move up onto the embankment.
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

  /* ── The boundary conditions ─────────────────────────────────────────────
     Each condition drawn from its own record, client side, like the water line.

     2D: a support is a row of symbols along its face or line, or one at its point --
     the clamp of a fixed support (a stem on hatched ground) when it holds x and y, a
     triangle on rollers when it holds one of them, pointing along the one it holds --
     and a water pressure is its own level or phreatic line, dashed, with "h = ..."
     beside it (a uniform one: its target outlined, "p = ..."). 3D: the face outline in
     the condition's colour, and a level as the outline of its plane.

     Pure, for the same reason `loadGlyphSpec` is: the arithmetic is the half a test
     can reach. `lines` are polylines of [x, y, z]; `symbols` are where a support
     symbol stands, the outward direction it points from, and whether it is a roller. */
  var SUPPORT_COLOR = 0x2e7d32;
  var WATER_COLOR = 0x1f6fb0;
  var SYMBOL_SPACING = 4;          // between two symbols on a face, in symbol sizes

  /* Where the symbols stand on a line of [x, y] points: at each corner, and evenly
     between, about `spacing` apart. A line with no length (a face the soil only touches
     at a corner) has the one symbol. */
  function alongLine(points, spacing) {
    if (!points.length) return [];
    var out = [[points[0][0], points[0][1]]];
    for (var i = 1; i < points.length; i += 1) {
      var a = points[i - 1], b = points[i];
      var length = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (length < 1e-9) continue;
      var count = Math.max(1, Math.min(24, Math.round(length / spacing)));
      for (var step = 1; step <= count; step += 1) {
        var t = step / count;
        out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]);
      }
    }
    return out;
  }

  /* Where a roller points: out of the face when the face's normal is the component it
     holds, else along that component, toward -x or -y. */
  function rollerOutward(held, face) {
    var faceOut = face && OUTWARD[face];
    if (faceOut && faceOut[held] !== 0) return faceOut;
    return held === 0 ? [-1, 0] : [0, -1];
  }

  /* The faces of the soil as the build drew it. The export finds a face on the meshed
     soil (core/kratos/writer.py `_boundary_nodes`), not on `project.domain`: a layer
     stack shallower than the domain, or a drawn body beyond it, moves the face. This
     takes the same rule to the drawn sections -- the soil's lowest and highest plane
     on each axis, across the soil points that lie on it. Null with no soil drawn.

     Pure: `sections` are the build payload's, `keys` the soil bodies among them. */
  function soilFaceOutlines(sections, keys, project) {
    var wanted = {};
    (keys || []).forEach(function (key) { wanted[key] = true; });
    var points = [];
    (sections || []).forEach(function (section) {
      if (!wanted[section.key]) return;
      var p = section.positions || [];
      for (var i = 0; i + 2 < p.length; i += 3) points.push([p[i], p[i + 1], p[i + 2]]);
    });
    if (!points.length) return null;
    var lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    points.forEach(function (q) {
      for (var k = 0; k < 3; k += 1) {
        lo[k] = Math.min(lo[k], q[k]);
        hi[k] = Math.max(hi[k], q[k]);
      }
    });
    var tol = 1e-6 * Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2], 1);
    // The span along `other` of the soil points on the plane `axis` = `value`.
    function range(axis, value, other) {
      var a = Infinity, b = -Infinity;
      points.forEach(function (q) {
        if (Math.abs(q[axis] - value) > tol) return;
        a = Math.min(a, q[other]);
        b = Math.max(b, q[other]);
      });
      return [a, b];
    }
    if (project.dimension === 2) {
      var z = sectionOffset(project);
      var bottom = range(1, lo[1], 0), top = range(1, hi[1], 0);
      var left = range(0, lo[0], 1), right = range(0, hi[0], 1);
      return {
        bottom: [[bottom[0], lo[1], z], [bottom[1], lo[1], z]],
        top: [[top[0], hi[1], z], [top[1], hi[1], z]],
        left: [[lo[0], left[0], z], [lo[0], left[1], z]],
        right: [[hi[0], right[0], z], [hi[0], right[1], z]]
      };
    }
    function rectangle(axis, value) {
      var u = axis === 0 ? 1 : 0, v = axis === 2 ? 1 : 2;
      var ru = range(axis, value, u), rv = range(axis, value, v);
      return [[ru[0], rv[0]], [ru[1], rv[0]], [ru[1], rv[1]], [ru[0], rv[1]], [ru[0], rv[0]]]
        .map(function (c) {
          var q = [0, 0, 0];
          q[axis] = value; q[u] = c[0]; q[v] = c[1];
          return q;
        });
    }
    return {
      bottom: rectangle(1, lo[1]), top: rectangle(1, hi[1]),
      left: rectangle(0, lo[0]), right: rectangle(0, hi[0]),
      front: rectangle(2, lo[2]), back: rectangle(2, hi[2])
    };
  }

  /* A face of the model: the soil's own when it was measured (none when there is no
     soil, `outlines` empty), else the domain's. */
  function faceOutline(project, face, outlines) {
    if (outlines) return outlines[face] || null;
    var d = project.domain;
    if (project.dimension === 2) {
      var z = sectionOffset(project);
      return {
        bottom: [[d.x0, d.y_bottom, z], [d.x1, d.y_bottom, z]],
        top: [[d.x0, d.y_top, z], [d.x1, d.y_top, z]],
        left: [[d.x0, d.y_bottom, z], [d.x0, d.y_top, z]],
        right: [[d.x1, d.y_bottom, z], [d.x1, d.y_top, z]]
      }[face] || null;
    }
    var yb = d.y_bottom, yt = d.y_top;
    return {
      bottom: [[d.x0, yb, d.z0], [d.x1, yb, d.z0], [d.x1, yb, d.z1], [d.x0, yb, d.z1], [d.x0, yb, d.z0]],
      top: [[d.x0, yt, d.z0], [d.x1, yt, d.z0], [d.x1, yt, d.z1], [d.x0, yt, d.z1], [d.x0, yt, d.z0]],
      left: [[d.x0, yb, d.z0], [d.x0, yt, d.z0], [d.x0, yt, d.z1], [d.x0, yb, d.z1], [d.x0, yb, d.z0]],
      right: [[d.x1, yb, d.z0], [d.x1, yt, d.z0], [d.x1, yt, d.z1], [d.x1, yb, d.z1], [d.x1, yb, d.z0]],
      front: [[d.x0, yb, d.z0], [d.x1, yb, d.z0], [d.x1, yt, d.z0], [d.x0, yt, d.z0], [d.x0, yb, d.z0]],
      back: [[d.x0, yb, d.z1], [d.x1, yb, d.z1], [d.x1, yt, d.z1], [d.x0, yt, d.z1], [d.x0, yb, d.z1]]
    }[face] || null;
  }

  var OUTWARD = { bottom: [0, -1], top: [0, 1], left: [-1, 0], right: [1, 0] };

  function conditionGlyphSpec(record, project, outlines) {
    var spec = { kind: record.kind, lines: [], symbols: [], dashed: false, label: null,
                 active: record.active !== false };
    var d = project.domain;
    var two = project.dimension === 2;
    var z = two ? sectionOffset(project) : (d.z0 + d.z1) / 2;
    var span = modelSpan(project, frame && frame.size);
    spec.size = span > 0 ? span * 0.022 : 0.5;
    if (!two && (record.on === 'line' || record.on === 'point')) return spec;

    if (record.kind === 'displacement') {
      if (record.on === 'face' && !two) {
        var box = faceOutline(project, record.face, outlines);
        if (box) spec.lines.push(box);
        return spec;
      }
      // The section holds z by itself: a 2D symbol says what is held in x and y.
      var heldX = !!record.fixed[0], heldY = !!record.fixed[1];
      if (!heldX && !heldY) return spec;
      var roller = heldX !== heldY;
      var face = record.on === 'face' ? record.face : null;
      var outward = roller ? rollerOutward(heldX ? 0 : 1, face)
        : (face ? OUTWARD[face] : [0, -1]);
      if (record.on === 'face') {
        var outline = faceOutline(project, record.face, outlines);
        if (!outline) return spec;
        alongLine([outline[0], outline[1]], SYMBOL_SPACING * spec.size).forEach(function (at) {
          spec.symbols.push({ at: [at[0], at[1], z], outward: outward, roller: roller });
        });
      } else if (record.on === 'line') {
        var points = record.points || [];
        spec.lines.push(points.map(function (p) { return [p[0], p[1], z]; }));
        alongLine(points, SYMBOL_SPACING * spec.size).forEach(function (at) {
          spec.symbols.push({ at: [at[0], at[1], z], outward: outward, roller: roller });
        });
      } else if (record.on === 'point') {
        var p = (record.points || [[0, 0]])[0];
        spec.symbols.push({ at: [p[0], p[1], z], outward: outward, roller: roller });
      }
      return spec;
    }

    // A seepage face: its edge or line, with arrows out of the soil, and the word.
    if (record.kind === 'seepage') {
      var path = record.on === 'face'
        ? faceOutline(project, record.face, outlines)
        : (record.points || []).map(function (q) { return [q[0], q[1], z]; });
      if (!path || path.length < 2 || !two) {
        if (path) spec.lines.push(path);
        return spec;
      }
      spec.lines.push(path);
      var centre = [(d.x0 + d.x1) / 2, (d.y_bottom + d.y_top) / 2];
      for (var k = 0; k + 1 < path.length; k += 1) {
        var a = path[k], b = path[k + 1];
        var length = Math.hypot(b[0] - a[0], b[1] - a[1]);
        if (!(length > 0)) continue;
        var normalOut = [(b[1] - a[1]) / length, -(b[0] - a[0]) / length];
        var middle = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
        if ((middle[0] - centre[0]) * normalOut[0] + (middle[1] - centre[1]) * normalOut[1] < 0) {
          normalOut = [-normalOut[0], -normalOut[1]];
        }
        alongLine([a, b], SYMBOL_SPACING * spec.size).forEach(function (at) {
          spec.symbols.push({ at: [at[0], at[1], z], outward: normalOut, arrow: true });
        });
      }
      var mid = path[Math.floor(path.length / 2)];
      spec.label = { text: 'seepage', at: [mid[0], mid[1], z] };
      return spec;
    }

    // A water pressure: its level or line, dashed, and what it is.
    spec.dashed = true;
    var type = record.fluid_pressure_type;
    if (type === 'Hydrostatic' && typeof record.reference_coordinate === 'number') {
      var y = record.reference_coordinate;
      spec.lines.push(two ? [[d.x0, y, z], [d.x1, y, z]]
        : [[d.x0, y, d.z0], [d.x1, y, d.z0], [d.x1, y, d.z1], [d.x0, y, d.z1], [d.x0, y, d.z0]]);
      spec.label = { text: 'h = ' + y.toFixed(2) + ' m', at: [d.x1, y, z] };
    } else if (type === 'Phreatic_Multi_Line' && record.x_coordinates) {
      var zs = record.z_coordinates;
      spec.lines.push(record.x_coordinates.map(function (x, k) {
        return [x, record.y_coordinates[k], two ? z : (zs ? zs[k] : z)];
      }));
      var last = record.x_coordinates.length - 1;
      spec.label = { text: 'h = ' + record.y_coordinates[last].toFixed(2) + ' m',
                     at: [record.x_coordinates[last], record.y_coordinates[last], z] };
    } else if (type === 'Uniform') {
      var where = record.on === 'face' ? faceOutline(project, record.face, outlines)
        : (record.on === 'line' || record.on === 'point')
          ? (record.points || []).map(function (q) { return [q[0], q[1], z]; })
          : null;
      if (where) spec.lines.push(where);
      var at = where ? where[0] : [(d.x0 + d.x1) / 2, (d.y_bottom + d.y_top) / 2, z];
      spec.label = { text: 'p = ' + record.value, at: at };
    }
    return spec;
  }

  function conditionGlyphGroup(record, project, outlines) {
    var spec = conditionGlyphSpec(record, project, outlines);
    var group = new THREE.Group();
    group.name = record.id + '-condition';
    var color = !spec.active ? 0x777777
      : record.kind === 'displacement' ? SUPPORT_COLOR : WATER_COLOR;

    spec.lines.forEach(function (points) {
      if (points.length < 1) return;
      var vectors = points.map(function (p) { return new THREE.Vector3(p[0], p[1], p[2]); });
      if (vectors.length === 1) {
        var dot = new THREE.Mesh(new THREE.SphereGeometry(spec.size * 0.25, 10, 8),
                                 new THREE.MeshBasicMaterial({ color: color }));
        dot.position.copy(vectors[0]);
        group.add(dot);
        return;
      }
      var material = spec.dashed
        ? new THREE.LineDashedMaterial({ color: color, dashSize: spec.size,
                                         gapSize: spec.size * 0.6 })
        : new THREE.LineBasicMaterial({ color: color });
      var line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(vectors), material);
      if (spec.dashed) line.computeLineDistances();
      group.add(line);
    });

    spec.symbols.forEach(function (symbol) {
      var s = spec.size;
      var o = symbol.outward, side = [-o[1], o[0]];
      var at = symbol.at;
      function p(along, out) {
        return new THREE.Vector3(at[0] + side[0] * along + o[0] * out,
                                 at[1] + side[1] * along + o[1] * out, at[2]);
      }
      function stroke(points, segments) {
        var geometry = new THREE.BufferGeometry().setFromPoints(points);
        var material = new THREE.LineBasicMaterial({ color: color });
        group.add(segments ? new THREE.LineSegments(geometry, material)
                           : new THREE.Line(geometry, material));
      }
      if (symbol.arrow) {
        // Water leaving the soil: a short arrow pointing out of it.
        stroke([p(0, 0.15 * s), p(0, 1.0 * s), p(-0.25 * s, 0.7 * s), p(0, 1.0 * s),
                p(0.25 * s, 0.7 * s)]);
      } else if (symbol.roller) {
        // A triangle on three rollers.
        stroke([p(0, 0), p(-0.5 * s, 0.8 * s), p(0.5 * s, 0.8 * s), p(0, 0)]);
        [-0.34, 0, 0.34].forEach(function (along) {
          var ring = [];
          for (var k = 0; k <= 16; k += 1) {
            var angle = (k / 16) * Math.PI * 2;
            ring.push(p((along + Math.cos(angle) * 0.14) * s,
                        (0.94 + Math.sin(angle) * 0.14) * s));
          }
          stroke(ring);
        });
      } else {
        // The clamp: a stem out to hatched ground.
        var clamp = [p(0, 0), p(0, 0.7 * s), p(-0.6 * s, 0.7 * s), p(0.6 * s, 0.7 * s)];
        for (var h = -0.6; h <= 0.31; h += 0.3) {
          clamp.push(p(h * s, 0.7 * s), p((h + 0.3) * s, 1.05 * s));
        }
        stroke(clamp, true);
      }
    });

    if (spec.label) {
      group.add(makeLabel(spec.label.text, spec.label.at[0], spec.label.at[1],
                          spec.label.at[2], spec.size * 0.8));
    }
    group.traverse(function (child) {
      child.userData.key = record.id;
      if (child.material) {
        child.material.depthTest = false;
        child.material.transparent = true;
        child.material.opacity = spec.active ? 1 : 0.45;
      }
      child.renderOrder = 18;
    });
    return group;
  }

  function addConditionGlyphs(sections) {
    var soil = soilKeysOf(App.PROJECT, App.LAYERS).concat(
      ((App.PROJECT && App.PROJECT.custom_parts) || []).filter(function (part) {
        return part.mat;
      }).map(function (part) { return part.key; }));
    // No soil, no face: the export has none either, and a support drawn round an
    // empty site would hold nothing.
    var outlines = App.PROJECT ? soilFaceOutlines(sections, soil, App.PROJECT) || {} : null;
    ((App.PROJECT && App.PROJECT.boundary_conditions) || []).forEach(function (record) {
      var group = groups[record.id];
      if (!group) {
        group = groups[record.id] = new THREE.Group();
        group.name = record.id;
        scene.add(group);
      }
      group.add(conditionGlyphGroup(record, App.PROJECT, outlines));
    });
  }

  /* The keys of the conditions, supports and water pressures apart. Both are in every
     mode but Results, and hidden until the user shows them: by Show in the Model
     explorer's menu (off in a new view, `shownByDefault`), or by selecting it
     (`revealConditions`). Their check box there is "active", not the eye
     (addConditionChecks in frontend/js/patches.js). */
  function conditionKeysOf(project) {
    var supports = [], water = [];
    ((project && project.boundary_conditions) || []).forEach(function (record) {
      (record.kind === 'displacement' ? supports : water).push(record.id);
    });
    return { supports: supports, water: water };
  }

  /* ── The water line ──────────────────────────────────────────────────────
     The phreatic level, drawn by the client rather than tessellated by the server.

     A `layered_soil` project has no water geometry at all -- `Project.part_keys`
     omits "water" on that path, so the thin slab the full build raises is never
     meshed and the level cannot be seen. That is the path the blank project and
     a staged model script both take, so the level being invisible is the normal
     case rather than an edge one, and a deck whose every pore pressure is stated
     about a number nobody can see is the thing worth fixing (plan sec 7.2).

     Pure, and separated from the THREE objects below for the same reason
     `loadGlyphSpec` is: this is the half with the arithmetic, and it is the half a
     test can reach. */
  function waterLineSpec(project) {
    var d = project && project.domain;
    var w = project && project.water;
    if (!d || !w || typeof w.y !== 'number') return null;
    if (typeof d.x0 !== 'number' || typeof d.x1 !== 'number') return null;

    // The same overhang the slab has, and for the same reason WaterLevel's own
    // comment gives: the level has to read against the model's outside faces rather
    // than stopping flush with them.
    var m = typeof w.margin === 'number' ? w.margin : 0;
    var x0 = d.x0 - m, x1 = d.x1 + m, y = w.y;

    if (project.dimension === 2) {
      var z = sectionOffset(project);
      return { y: y, points: [[x0, y, z], [x1, y, z]] };
    }
    // A single line in 3D would be an arbitrary chord through the model. The level is
    // a plane there, so the outline of that plane is the honest drawing of it.
    var z0 = d.z0 - m, z1 = d.z1 + m;
    return { y: y, points: [[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1],
                            [x0, y, z0]] };
  }

  function addWaterLine() {
    var spec = waterLineSpec(App.PROJECT);
    if (!spec) return;
    var group = groups.water;
    if (!group) {
      group = groups.water = new THREE.Group();
      group.name = 'water';
      scene.add(group);
    }
    var line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(spec.points.map(function (point) {
        return new THREE.Vector3(point[0], point[1], point[2]);
      })),
      // The slab's own blue (#2f8fd8), so the drawn level and a tessellated one read
      // as the same object in a project that has both. depthTest off because the
      // level is a reference plane, not a solid: it is meant to be legible through
      // the ground it passes behind.
      new THREE.LineBasicMaterial({ color: 0x2f8fd8, depthTest: false }));
    // Never a pick target -- it is edited from the Selection explorer's rows, and a
    // line lying inside the soil would otherwise steal clicks meant for the soil.
    line.userData.noPick = true;
    line.renderOrder = 17;
    group.add(line);
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
    addConditionGlyphs(payload.sections);

    // Before the visibility sweep below, so the group it creates is given its
    // `visible` entry like every other one.
    addWaterLine();

    groups.mesh = groups.mesh || new THREE.Group();     // filled by generateMesh
    groups.mesh.name = 'mesh';
    if (!groups.mesh.parent) scene.add(groups.mesh);

    Object.keys(groups).forEach(function (k) {
      groups[k].visible = false;
      if (!(k in visible)) visible[k] = shownByDefault(k);
    });
  }

  /* Pure so it is directly testable: setMode() only shows a key present in
     modeGroups[mode], so a custom part left out here is created (buildGroups gives
     every section its own THREE.Group) and then invisible forever, in every mode,
     no matter what the eye toggle says. */
  function computeModeGroups(soilKeys, customKeys, layeredSoil, loadKeys, memberKeys,
                             normalLoadKeys, conditionKeys) {
    customKeys = customKeys || [];
    // The boundary conditions' symbols: in every mode, each one hidden until it is
    // shown (the explorer's Show) or selected.
    var conditions = ((conditionKeys && conditionKeys.supports) || [])
      .concat((conditionKeys && conditionKeys.water) || []);
    loadKeys = loadKeys || [];
    // Sheet piles and anchors are sections of their own (core/geometry/tessellation.py
    // :112-126). Leaving them out of every mode is what kept them invisible.
    memberKeys = memberKeys || [];
    // And a normal load is a section of its own too -- the strip the build draws
    // along its line -- so it needs naming here for the same reason, in the modes a
    // load belongs to.
    loadKeys = loadKeys.concat(normalLoadKeys || []);
    // Results draws its own contoured mesh (frontend/js/results-view.js); over it go
    // the loads and the water, so the user sees where the load is and where the water
    // stands. Not the supports: they would hide the edges of the contour.
    var results = loadKeys.concat(['water'], (conditionKeys && conditionKeys.water) || []);
    if (layeredSoil) {
      var visibleKeys = soilKeys.concat(customKeys);
      // "water" in the same two modes the full build shows it in -- the level is what
      // Flow conditions mode is for, and a staged excavation is read against it. Left
      // out of soil/structures/mesh so those keep reading as they did.
      return { soil: visibleKeys.concat(conditions),
               structures: visibleKeys.concat(loadKeys, memberKeys, conditions),
               mesh: visibleKeys.concat(['mesh'], memberKeys, conditions),
               flow: visibleKeys.concat(['water'], conditions),
               // Loads too: Staged construction is where a load is switched on and
               // off, so it has to be on screen there (`stageHidden` still hides one
               // the selected stage has switched off).
               staged: visibleKeys.concat(loadKeys, memberKeys, ['water'], conditions),
               results: results };
    }
    return {
      soil:       soilKeys.concat(conditions),
      structures: soilKeys.concat(['wall', 'struts', 'anchors', 'piles'],
                                  loadKeys, memberKeys, customKeys, conditions),
      mesh:       ['mesh', 'wall'].concat(memberKeys, customKeys, conditions),
      flow:       soilKeys.concat(['water', 'wells', 'wall'], customKeys, conditions),
      staged:     ['excavation', 'wall', 'struts', 'anchors', 'water']
                    .concat(loadKeys, memberKeys, customKeys, conditions),
      results:    results
    };
  }

  /* Which soil bodies there are to show.

     Not one per layer: a staged excavation splits the soil inside the pit into the
     lifts it is dug in, so three layers can be eight bodies (core/model/schemas.py,
     `Project.soil_bodies`). Deriving that split here would be a second implementation
     of it to keep in step, so the project publishes the answer and this reads it.

     Naming one key per layer is what used to leave every body inside the pit out of
     `modeGroups` -- built by buildGroups, then invisible in every mode, which is the
     whole excavated side of the model missing. The fallback is for a project that
     carries no such list: an older server, or the frozen mockup's own data. */
  function soilKeysOf(project, layers) {
    var published = project && project.soil_body_keys;
    if (Array.isArray(published) && published.length) return published.slice();
    return (layers || []).map(function (l) { return 'soil_' + l.id; });
  }

  function rebuildModeGroups() {
    soilKeys = soilKeysOf(App.PROJECT, App.LAYERS);
    var customKeys = ((App.PROJECT && App.PROJECT.custom_parts) || [])
      .map(function (p) { return p.key; });
    var loadKeys = ((App.PROJECT && App.PROJECT.loads) || []).filter(function (load) {
      return !App.Loads || App.Loads.compatible(load, App.PROJECT);
    }).map(function (load) { return load.id; });
    // App.BEAMS/App.ANCHORS are already filtered to the project's dimension by
    // frontend/js/model.js -- a 3D project keeps its piles saved but draws none.
    var beamKeys = (App.BEAMS || []).map(function (beam) { return beam.id; });
    var anchorKeys = (App.ANCHORS || []).map(function (anchor) { return anchor.id; });
    // Plane strain only, like a free interface: in 3D the record is kept but the
    // build draws nothing for it, so naming it in a mode would name an empty group.
    var normalLoadKeys = (App.PROJECT && App.PROJECT.dimension === 2)
      ? (App.NORMAL_LOADS || []).map(function (item) { return item.id; })
      : [];
    var conditionKeys = conditionKeysOf(App.PROJECT);
    conditionIds = conditionKeys.supports.concat(conditionKeys.water);
    waterIds = conditionKeys.water.slice();
    modeGroups = computeModeGroups(
      soilKeys, customKeys, !!(App.PROJECT && App.PROJECT.layered_soil), loadKeys,
      beamKeys.concat(anchorKeys), normalLoadKeys, conditionKeys);
    var contactKeys = (App.INTERFACES || []).filter(function (item) {
      return !item.structure;
    }).map(function (item) { return item.id; });
    groupKeys = computeGroupKeys(soilKeys, customKeys, loadKeys, beamKeys, anchorKeys,
                                 contactKeys, normalLoadKeys,
                                 conditionKeys.supports.concat(conditionKeys.water));
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
        generatedLabels = null;
        forgetNodeParts();
        refreshLabels();

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
      minRadius: radiusLimits(frame, dimension).min,
      maxRadius: radiusLimits(frame, dimension).max,
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
    if (App.MeshLabels) App.MeshLabels.install(host);

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
      hoverImportedNode(ev);
    });

    canvas.addEventListener('mouseleave', function () {
      if (hovered && selectedKeys.indexOf(hovered) < 0) restoreEmissive(hovered);
      hovered = null;
    });

    canvas.addEventListener('click', function (ev) {
      if (ev.detail === 0) return;
      if (pickImportedNode(ev)) return;
      var hit = pickAt(ev);
      App.selectObject(hit ? hit.object.userData.key : null, 'viewport');
    });

    canvas.addEventListener('contextmenu', function (ev) {
      ev.preventDefault();
      var hit = pickAt(ev);
      App.viewportContextMenu(ev, hit ? hit.object.userData.key : null);
    });
  }

  /* The box around what a group draws. Not `Box3.setFromObject`, which counts hidden
     children as well: the mesh group holds the coloured-part overlays, hidden until
     switched on, and the water level's line among them overhangs the model by its
     margin -- so selecting the mesh drew a box 3 m wider than the mesh on each side.
     Invisible subtrees are skipped, and so is anything marked `noBounds` (the overlay
     itself, which is a view of the mesh rather than part of it). */
  function boundsOf(object) {
    var box = new THREE.Box3();
    object.updateMatrixWorld(true);
    (function walk(o) {
      if (!o.visible || (o.userData && o.userData.noBounds)) return;
      if (o.geometry) {
        if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
        if (!o.geometry.boundingBox.isEmpty()) {
          box.union(o.geometry.boundingBox.clone().applyMatrix4(o.matrixWorld));
        }
      }
      o.children.forEach(walk);
    })(object);
    return box;
  }

  /* ── Selection ──────────────────────────────────────────────── */

  /* A boundary condition whose eye is off is drawn while it is selected, so picking
     "Roller left" in the explorer shows its rollers. The next selection or mode change
     takes it away again. */
  var conditionIds = [];
  var waterIds = [];
  var revealed = [];

  /* Whether the eye lets `key` be drawn in `mode`. In Staged construction a water
     pressure condition has the stage's checkbox in place of its eye, and the stage is
     what is read there: the conditions the selected stage has on are drawn, the others
     not (`stageHidden`). Results reads the stage on screen the same way. */
  function eyeOpen(key, mode) {
    if ((mode === 'staged' || mode === 'results') && waterIds.indexOf(key) >= 0) return true;
    return visible[key] !== false;
  }

  function shownByMode(key) {
    var mode = App.state && App.state.mode;
    return modeKeys(mode).indexOf(key) >= 0
           && eyeOpen(key, mode) && !stageHidden()[key];
  }

  function hideRevealed() {
    revealed.forEach(function (k) { if (groups[k]) groups[k].visible = shownByMode(k); });
    revealed = [];
  }

  function revealConditions(keys) {
    keys.forEach(function (k) {
      if (conditionIds.indexOf(k) < 0 || !groups[k] || groups[k].visible) return;
      if (stageHidden()[k]) return;
      if (App.state && App.state.mode === 'results') return;
      groups[k].visible = true;
      revealed.push(k);
    });
  }

  function select(key) {
    if (!scene) return;
    selectedKeys.forEach(function (k) { restoreEmissive(k); });
    hideRevealed();
    revealConditions(keysFor(key));
    var keys =keysFor(key).filter(function (k) { return groups[k] && groups[k].visible; });
    selectedKeys = keys;
    selected = keys.length ? key : null;

    if (boxHelper) { scene.remove(boxHelper); boxHelper.geometry.dispose(); boxHelper = null; }
    if (!keys.length) { needsRender = true; return; }

    var box = new THREE.Box3();
    keys.forEach(function (k) {
      setEmissive(k, 0x1f3b70);
      box.union(boundsOf(groups[k]));
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

  /* Parts the selected stage has switched off, as `{key: true}`.

     A third gate on top of the two that already exist -- the mode the user is in, and
     the eye toggle on the row -- rather than a new mechanism: a group is drawn when
     all three agree. Which is why this is a lookup rebuilt on demand rather than
     something written into `visible`: the eye is the user's own state and must
     survive stepping through the stages, so a stage may not overwrite it.

     `App.Stages` owns the rule (frontend/js/stages.js), and is held to the server's
     answers by `tests/test_stage_parity.py`. Empty whenever it cannot say. */
  function stageHidden() {
    if (!App.Stages || !App.Stages.hiddenKeys) return {};
    var hidden = {};
    var mode = App.state && App.state.mode;
    var stage = App.state && App.state.phase;
    if (mode === 'results') {
      // The project's stage the result on screen is of, read as Staged construction
      // reads its own; and what the export left out (the check box off) was never in
      // the run, so it is not drawn over its result either.
      var shown = resultsStage();
      stage = shown && shown.stage;
      mode = 'staged';
      var project = App.PROJECT || {};
      [].concat(project.loads || [], project.normal_loads || [],
                project.boundary_conditions || []).forEach(function (record) {
        if (record.active === false) hidden[record.id] = true;
      });
    }
    App.Stages.hiddenKeys(App.PROJECT, stage, mode)
      .forEach(function (key) { hidden[key] = true; });
    return hidden;
  }

  function resultsStage() {
    return App.Results && App.Results.projectStage
      ? App.Results.projectStage(App.PROJECT) : null;
  }

  /* The keys `mode` draws. In Results, none when `results loads off` took them away,
     and none when the run on screen is not of the open project: its loads and water
     would be drawn over a result they had no part in. */
  function modeKeys(mode) {
    if (mode === 'results') {
      var options = App.Results && App.Results.options && App.Results.options();
      if ((options && options.loads === false) || !resultsStage()) return [];
    }
    return modeGroups[mode] || [];
  }

  /* Redraw after the selected stage changes. The mode pass is the whole of it --
     nothing about the geometry changes when a stage is selected, only which of it
     is in the model at that moment. */
  function applyStageVisibility() {
    setMode(App.state && App.state.mode);
  }

  function setMode(mode) {
    var wanted = modeKeys(mode);
    var hidden = stageHidden();
    revealed = [];
    Object.keys(groups).forEach(function (k) {
      groups[k].visible = wanted.indexOf(k) >= 0 && eyeOpen(k, mode)
                          && !hidden[k];
    });
    if (mode === 'mesh' && !meshBuilt && groups.mesh) groups.mesh.visible = false;
    if (selected && conditionIds.indexOf(selected) >= 0) select(selected);
    else if (selected && !selectedKeys.every(function (k) { return groups[k] && groups[k].visible; })) select(null);
    // A stage may have switched a part off, and a coloured part follows that.
    syncPartColors();
    applyImportedVisibility(mode);
    needsRender = true;
  }

  /* An imported deck's sections, drawn or not. Outside `groups`, so the pass above
     never reaches them; this is their pass. Three things decide, and App.Deck (tested
     headlessly) is the one that combines them: the part's eye, the stage selected on
     the Staged construction tab -- a deck case's stages are its stages -- and Results,
     which draws its own contoured copy of the mesh, so the grey one steps aside. */
  function applyImportedVisibility(mode) {
    if (!importedMeshGroup) return;
    importedMeshGroup.visible = mode !== 'results';
    var active = App.Deck
      ? App.Deck.activeForView(App.PROJECT, App.state && App.state.phase, mode) : null;
    Object.keys(importedSectionGroups).forEach(function (key) {
      importedSectionGroups[key].visible = App.Deck
        ? App.Deck.sectionShown(importedSectionParts[key], importedEyes[key], active)
        : importedEyes[key] !== false;
    });
    importedPickable = null;
    refreshLabels();
    needsRender = true;
  }

  /* The eye of an imported part: true or false, or undefined for a key with no
     imported section -- which is how App.ResultsView tells a deck part from anything
     else. */
  function importedEye(key) {
    return importedSectionGroups[key] ? importedEyes[key] !== false : undefined;
  }

  function setVisible(key, on) {
    if (groupKeys[key]) {
      groupKeys[key].forEach(function (k) { setVisible(k, on); });
      return;
    }
    // An imported .mdpa part: outside `groups`, so its eye is kept on its own and
    // `applyImportedVisibility` combines it with the selected stage. In Results the
    // same eye shows and hides that part's contour.
    if (importedSectionGroups[key]) {
      importedEyes[key] = on;
      applyImportedVisibility(App.state && App.state.mode);
      if (!on && selectedKeys.indexOf(key) >= 0) select(null);
      if (App.ResultsView && App.ResultsView.syncVisibility) App.ResultsView.syncVisibility();
      return;
    }
    if (!(key in groups)) return;
    visible[key] = on;
    var wanted = modeKeys(App.state.mode);
    // The stage gate applies here too, or turning an eye back on would draw a part
    // the selected stage has not built yet.
    groups[key].visible = on && wanted.indexOf(key) >= 0 && !stageHidden()[key];
    if (key === 'mesh' && !meshBuilt && groups.mesh) groups.mesh.visible = false;
    if (!on && selectedKeys.indexOf(key) >= 0) select(null);
    // A hidden mesh has nothing to number: the labels follow the eye, or they float
    // over a part that is no longer there.
    if (key === 'mesh') refreshLabels();
    // A coloured part follows its own eye: hidden, it is not drawn coloured either.
    syncPartColors();
    needsRender = true;
  }

  /* An empty group reads as visible: an unchecked box on a row with nothing under
     it would only be a puzzle. */
  function isVisible(key) {
    if (groupKeys[key]) {
      return groupKeys[key].every(function (k) { return isVisible(k); });
    }
    if (importedSectionGroups[key]) return importedEyes[key] !== false;
    if (!(key in visible)) return shownByDefault(key);
    return visible[key] !== false;
  }

  /* Every part is drawn until its eye is turned off, but a boundary condition is not:
     a model opens on its soil, and the supports and water levels of each face would
     cover its edges. The user shows them one by one, from the Model explorer's menu. */
  function shownByDefault(key) {
    return !(App.BoundaryConditions && App.BoundaryConditions.isConditionKey(key));
  }

  /* When another project is opened. The standard conditions of every project have the
     same ids, so an eye turned on in the last one would otherwise show the new one's. */
  function forgetConditionEyes() {
    Object.keys(visible).forEach(function (key) {
      if (conditionIds.indexOf(key) >= 0 || !shownByDefault(key)) delete visible[key];
    });
    revealed = [];
  }

  /* ── ID labels (nodes, elements) ────────────────────────────── */

  /* The overlay is painted in screen pixels (frontend/js/mesh-labels.js), so it needs the
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

  /* Everything currently on screen that has a number, for one kind of label. An
     imported deck brings its own numbering with it, section by section, so a part the
     eye is closed on is not labelled; a generated mesh's has to be asked for, so it only
     joins in once `generatedLabels` has arrived. */
  function labelledPoints(kind) {
    var list = [];
    if (!App.MeshLabels) return list;
    if (importedMeshGroup) {
      var sections = Object.keys(importedSectionLabels)
        .filter(function (key) {
          var group = importedSectionGroups[key];
          return group && group.visible;
        })
        .map(function (key) { return importedSectionLabels[key]; });
      list = list.concat(kind === 'elements'
        ? App.MeshLabels.elementsFromSections(sections)
        : App.MeshLabels.nodesFromSections(sections));
    }
    if (generatedLabels && meshBuilt && visible.mesh !== false) {
      list = list.concat(App.MeshLabels.pointsFromTable(generatedLabels[kind]));
    }
    return list;
  }

  /* Re-gather without re-asking the server: called whenever what is drawn changes. Only
     the kinds that are on are gathered, so nothing pays for a label it is not showing. */
  function refreshLabels() {
    if (!App.MeshLabels) return;
    App.MeshLabels.KINDS.forEach(function (kind) {
      if (!App.MeshLabels.isActive(kind)) return;
      App.MeshLabels.setPoints(kind, labelledPoints(kind));
    });
    needsRender = true;
  }

  /* Whether the server has to be asked before a kind can be drawn. Only a generated mesh
     needs asking, and only once: the numbering costs a full export pass, and nothing but
     a new mesh can change it. */
  function needsNumbering() {
    return meshBuilt && visible.mesh !== false && !generatedLabels;
  }

  /* Fetch both tables at once. They come out of one export pass on the server, so asking
     for them separately would mean meshing the project twice to learn what it already
     said -- which is also why turning the second kind on afterwards is free. */
  function fetchLabels() {
    var ui = overlay();
    ui.show('Numbering mesh nodes and elements…', 40);
    return App.Api.post('/api/mesh/labels', meshSettings()).then(function (result) {
      generatedLabels = { nodes: result.nodes || [], elements: result.elements || [] };
      ui.hide();
      return generatedLabels;
    }).catch(function (err) {
      ui.hide();
      throw err;
    });
  }

  /* Turn one kind of label on or off. `done` is called with how many entities are
     labelled (null when switched off, or when the numbering failed and has already been
     reported), which is what the caller writes to the command log.

     The two kinds are independent: switching one off leaves the other drawn. */
  function setLabels(kind, on, done) {
    if (!App.MeshLabels) { if (done) done(null); return; }
    if (!on) {
      App.MeshLabels.setActive(kind, false);
      App.MeshLabels.setPoints(kind, []);
      if (!App.MeshLabels.anyActive()) App.MeshLabels.hide();
      needsRender = true;
      if (done) done(null);
      return;
    }

    App.MeshLabels.setActive(kind, true);
    if (!needsNumbering()) {
      refreshLabels();
      if (done) done(App.MeshLabels.count(kind));
      return;
    }

    fetchLabels().then(function () {
      refreshLabels();
      if (done) done(App.MeshLabels.count(kind));
    }).catch(function (err) {
      // Off again rather than left on and empty: a label layer showing nothing looks
      // like a mesh with no nodes in it.
      App.MeshLabels.setActive(kind, false);
      if (!App.MeshLabels.anyActive()) App.MeshLabels.hide();
      fail(err);
      if (done) done(null);
    });
  }

  /* A fresh mesh with the labels still on: re-ask for the numbering it invalidated. */
  function renumberLabels() {
    if (!App.MeshLabels || !App.MeshLabels.anyActive() || !needsNumbering()) {
      refreshLabels();
      return;
    }
    fetchLabels().then(refreshLabels).catch(function (err) {
      App.MeshLabels.KINDS.forEach(function (kind) { App.MeshLabels.setActive(kind, false); });
      App.MeshLabels.hide();
      fail(err);
    });
  }

  function labelsOn(kind) {
    return !!(App.MeshLabels && (kind ? App.MeshLabels.isActive(kind)
                                      : App.MeshLabels.anyActive()));
  }

  /* Painted from the render tick with the camera that drew the frame, the same way the
     rulers are: a label that lagged a frame behind would slide off its node on every
     orbit. */
  function syncLabels() {
    if (!App.MeshLabels || !host) return;
    App.MeshLabels.sync({
      active: labelsOn(),
      width: host.clientWidth, height: host.clientHeight,
      project: projectToScreen
    });
  }

  /* ── Mesh generation ────────────────────────────────────────── */

  /* What the mesher is asked for. Its own function because two endpoints take it: the
     mesh itself, and the node numbering the ID labels are drawn from -- and a numbering
     taken from different settings than the mesh on screen would be numbers for a mesh
     nobody is looking at. */
  /* The refinements a mesh is built with: the ones set from the toolbar this session
     if there are any, and otherwise the model's own (`MeshSettings.refinements`). A
     model can carry a graded mesh -- a model script can refine its excavation and
     grade out to the far field -- and it has to mesh that way from the Generate-mesh
     button and from Export alike, not only from a script.

     Length, not truthiness: "Reset local mesh refinement" leaves an empty array behind,
     and an empty array is truthy. Reset means "back to what the model asks for", not
     "no refinement at all". */
  function meshRefinements() {
    var local = App.MESH_REFINEMENTS;
    if (local && local.length) return local.slice();
    var mesh = App.PROJECT && App.PROJECT.mesh;
    return (mesh && mesh.refinements) ? mesh.refinements.slice() : [];
  }

  function meshSettings() {
    return Object.assign({}, App.PROJECT ? App.PROJECT.mesh : {
      element_size: 2.5, order: 2, algorithm_3d: 'delaunay', optimization: 'gmsh',
      smoothing: 10, curvature_points: 16, size_min_factor: 0.05,
      second_order_linear: true
    }, {
      refinements: meshRefinements(),
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
      buildPartColors(result.parts || []);
      scene.add(groups.mesh);
      if (!(('mesh') in visible)) visible.mesh = true;

      meshBuilt = true;
      // Different mesh, different nodes: whatever was numbered before is now numbering
      // a mesh that no longer exists.
      generatedLabels = null;
      forgetNodeParts();
      App.MESH_STATS = result.stats;
      if (App.Model && App.Model.setMeshStats) App.Model.setMeshStats(result.stats);
      (result.log || []).filter(function (line) { return /warning|error/i.test(line); })
        .slice(-5).forEach(function (line) {
          if (/error/i.test(line) && App.Command.err) App.Command.err(line);
          else note(line);
        });
      ui.hide();
      setMode(App.state.mode);
      // The Model explorer's colour toggles are only drawn for parts that have mesh
      // elements, so the tree is mounted again now that there are some.
      if (App.Explorer && App.Explorer.mountTree) App.Explorer.mountTree(App.state.mode);
      needsRender = true;
      // Last, and only if the numbers are on screen: re-numbering means a second trip
      // to the server with its own progress overlay, which must not start under this
      // one's.
      if (App.MeshLabels && App.MeshLabels.anyActive()) renumberLabels();
      if (done) done(result.stats);
    }).catch(function (err) {
      ui.hide();
      fail(err);
      if (done) done();
    });
  }

  function hasMesh() { return meshBuilt; }

  /* ── Which SubModelParts a node is in ──────────────────────────────────
     The node -> parts index of the deck this project exports (`/api/mesh/node-parts`,
     built by `App.NodeParts`), fetched the first time it is asked for and kept until
     the mesh changes -- it costs an export pass, like the labels. `nodePartsLoaded` is
     the no-fetch read the hover uses, so moving the pointer never starts one. */
  var nodePartsIndex = null;
  var nodeMarker = null;

  function nodeParts() {
    // An imported deck on screen is the deck being asked about.
    if (importedNodeIndex) return Promise.resolve(importedNodeIndex);
    if (nodePartsIndex) return Promise.resolve(nodePartsIndex);
    if (!meshBuilt) {
      return Promise.reject(new Error('There is no mesh yet. Generate one (mesh, or F9) '
        + 'first: node numbers come from the deck, and the deck is made from the mesh.'));
    }
    var ui = overlay();
    ui.show('Reading SubModelParts off the deck…', 40);
    return App.Api.post('/api/mesh/node-parts', meshSettings()).then(function (result) {
      nodePartsIndex = App.NodeParts.build(result);
      ui.hide();
      return nodePartsIndex;
    }).catch(function (err) {
      ui.hide();
      throw err;
    });
  }

  function nodePartsLoaded() { return nodePartsIndex; }

  function forgetNodeParts() {
    nodePartsIndex = null;
    clearNodeMark();
  }

  /* A dot on each of `points` ([x, y, z]): the node `node <id>` reported, and the
     nodes at its position. Drawn over everything, since a node inside the soil is the
     usual case. One marking at a time. */
  function markNodes(points) {
    clearNodeMark();
    if (!scene || !points.length) return;
    var geometry = new THREE.BufferGeometry().setFromPoints(points.map(function (p) {
      return new THREE.Vector3(p[0], p[1], p[2]);
    }));
    nodeMarker = new THREE.Points(geometry, new THREE.PointsMaterial({
      color: 0xe6194b, size: 11, sizeAttenuation: false, depthTest: false
    }));
    nodeMarker.renderOrder = 30;
    nodeMarker.userData.noPick = true;
    scene.add(nodeMarker);
    needsRender = true;
  }

  function clearNodeMark() {
    if (!nodeMarker) return;
    disposeGroup(nodeMarker);
    nodeMarker = null;
    needsRender = true;
  }

  /* ── Parts in a colour of their own ────────────────────────────────────
     The grey mesh is one sheet. `result.parts` is the same mesh cut along part keys
     (core/geometry/meshing.py `_part_sections`), and each part is built here once, hidden,
     inside the mesh group -- so it lives and dies with the mesh, and is only ever on
     screen where the mesh is (Mesh mode, mesh eye on). `App.PartColors` decides which
     are switched on; `syncPartColors` shows exactly those that are also shown by their
     own eye and built by the selected stage.

     A body is a tinted fill over the grey, with its own wireframe on top. A structure
     is its segments plus a dot on every node: a one-pixel line in a dense mesh is easy
     to lose, and the dots are the part's nodes, which is what it is being looked at
     for. */
  var meshPartKeys = [];
  var meshPartGroups = {};

  function buildPartColors(parts) {
    meshPartGroups = {};
    meshPartKeys = parts.map(function (section) { return section.key; });
    // The server sends them in `Project.part_keys` order, so a part keeps its colour
    // across a re-mesh that adds a structure after it.
    var palette = App.PartColors ? App.PartColors.colors(meshPartKeys) : {};
    var holder = new THREE.Group();
    holder.name = 'meshParts';
    // A view of the mesh, not part of it: never in a selection box (`boundsOf`).
    holder.userData.noBounds = true;
    parts.forEach(function (section) {
      var colour = new THREE.Color(palette[section.key] || '#e6194b');
      var group = new THREE.Group();
      group.name = 'meshPart:' + section.key;
      group.visible = false;
      if (section.indices.length) {
        var fill = new THREE.Mesh(App.Buffers.geometry(section), new THREE.MeshBasicMaterial({
          color: colour, transparent: true, opacity: 0.8, side: THREE.DoubleSide,
          // In front of the grey mesh (which sits at +1), behind the lines (at 0).
          polygonOffset: true, polygonOffsetFactor: 0.5, polygonOffsetUnits: 0.5
        }));
        fill.userData.noPick = true;
        group.add(fill);
        if (section.edges.length) {
          var wire = new THREE.LineSegments(App.Buffers.edges(section),
            new THREE.LineBasicMaterial({ color: 0x263238 }));
          wire.userData.noPick = true;
          group.add(wire);
        }
      } else if (section.edges.length) {
        var lines = new THREE.LineSegments(App.Buffers.edges(section),
          new THREE.LineBasicMaterial({ color: colour, depthTest: false }));
        lines.renderOrder = 10;
        lines.userData.noPick = true;
        group.add(lines);
        var dots = new THREE.Points(App.Buffers.edges(section), new THREE.PointsMaterial({
          color: colour, size: 6, sizeAttenuation: false, depthTest: false
        }));
        dots.renderOrder = 11;
        dots.userData.noPick = true;
        group.add(dots);
      }
      meshPartGroups[section.key] = group;
      holder.add(group);
    });
    labelInterfaceFaces(parts, palette);
    groups.mesh.add(holder);
    if (App.PartColors) App.PartColors.on.keep(meshPartKeys);
    syncPartColors();
  }

  /* An interface's two faces lie on one line, drawn a hair apart toward their own
     sides (meshing.py `_interface_sections`). A round L or R badge in the face's colour
     says which is which. With both faces present the badge goes a little further out
     than its line, away from the other face; a lone face is labelled where it is. */
  function labelInterfaceFaces(parts, palette) {
    if (!App.PartColors || typeof document === 'undefined') return;
    var middles = {};
    parts.forEach(function (section) {
      if (!App.PartColors.sideOf(section.key) || !section.edges.length) return;
      var segments = section.edges.length / 6;
      var at = Math.floor(segments / 2) * 6;
      var e = section.edges;
      middles[section.key] = new THREE.Vector3((e[at] + e[at + 3]) / 2,
                                               (e[at + 1] + e[at + 4]) / 2,
                                               (e[at + 2] + e[at + 5]) / 2);
    });
    Object.keys(middles).forEach(function (key) {
      var side = App.PartColors.sideOf(key);
      var other = App.PartColors.baseOf(key) + ':' + (side === 'L' ? 'R' : 'L');
      var at = middles[key].clone();
      if (middles[other]) at.add(middles[key].clone().sub(middles[other]).multiplyScalar(2));
      var badge = letterBadge(side, palette[key] || '#e6194b');
      badge.position.copy(at);
      meshPartGroups[key].add(badge);
    });
  }

  function letterBadge(letter, colour) {
    var canvas = document.createElement('canvas');
    canvas.width = canvas.height = 64;
    var ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(32, 32, 28, 0, 2 * Math.PI);
    ctx.fill();
    ctx.lineWidth = 6;
    ctx.strokeStyle = colour;
    ctx.stroke();
    ctx.fillStyle = colour;
    ctx.font = 'bold 34px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(letter, 32, 34);
    var sprite = new THREE.Sprite(new THREE.SpriteMaterial({
      map: new THREE.CanvasTexture(canvas), depthTest: false, sizeAttenuation: false
    }));
    // A fixed size on screen, whatever the zoom: about 3.5% of the viewport's height.
    sprite.scale.set(0.035, 0.035, 1);
    sprite.renderOrder = 12;
    sprite.userData.noPick = true;
    return sprite;
  }

  function syncPartColors() {
    if (!App.PartColors) return;
    var hidden = stageHidden();
    var drawn = App.PartColors.drawn(meshPartKeys, App.PartColors.on, function (key) {
      return isVisible(key) && !hidden[key];
    });
    Object.keys(meshPartGroups || {}).forEach(function (key) {
      meshPartGroups[key].visible = drawn.indexOf(key) >= 0;
    });
    needsRender = true;
  }

  function partColor(key) {
    return App.PartColors ? App.PartColors.colors(meshPartKeys)[key] : null;
  }

  function coloredPartKeys() { return meshBuilt ? meshPartKeys.slice() : []; }

  /* A previewed .mdpa: drawn straight into the scene, not into `groups`, because it is
     not part of the project -- a project refresh() must not touch it. Its own parts
     are still reachable by key from the Model explorer's "Imported mesh" node
     (`setVisible`/`isVisible` above check `importedSectionGroups` too), which is what
     lets `App.Model.setImportedParts` build that node without this module knowing
     anything about trees. */
  function clearImportedMesh() {
    disposeGroup(importedMeshGroup);
    importedMeshGroup = null;
    importedNodeIndex = null;
    importedPickable = null;
    forgetPickedNode();
    importedSectionGroups = {};
    importedEyes = {};
    importedSectionParts = {};
    importedSectionBBoxes = {};
    importedSectionLabels = {};
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
  var IMPORTED_LINE_ORDER = 18, INTERFACE_LINE_ORDER = 19;

  /* A zero-thickness contact is drawn along exactly the line of the structure it holds
     -- the same nodes, the same pixels -- so at equal render order the two fight and
     whichever was added last wins, at random from the reader's point of view. The
     contact goes on top, because it is the one with nothing else to be seen by: a sheet
     pile still reads as a sheet pile under it, and the interface is what the reader
     turned on to look for. Each still has its own eye in the Model explorer. */
  function importedLineOrder(section) {
    return section && section.kind === 'interface'
      ? INTERFACE_LINE_ORDER : IMPORTED_LINE_ORDER;
  }

  function importedSectionLines(section) {
    var lines = new THREE.LineSegments(App.Buffers.edges(section),
      new THREE.LineBasicMaterial({ color: new THREE.Color(section.color),
                                    depthTest: false,
                                    transparent: true, opacity: 1 }));
    lines.userData.noPick = true;
    lines.renderOrder = importedLineOrder(section);
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
      importedSectionParts[section.key] = section.part || null;
      if (section.bbox) importedSectionBBoxes[section.key] = section.bbox;
      if (section.node_ids || section.elements) importedSectionLabels[section.key] = section;
    });
    if (model.node_parts && App.NodeParts) {
      importedNodeIndex = App.NodeParts.build(model.node_parts);
      Object.keys(importedSectionGroups).forEach(function (key) {
        var dots = importedNodeDots(importedSectionLabels[key]);
        if (dots) importedSectionGroups[key].add(dots);
      });
    }
    scene.add(importedMeshGroup);
    applyImportedVisibility(App.state && App.state.mode);

    if (orbit && model.bbox) {
      var bounds = App.Buffers.bounds(model.bbox);
      orbit.animateTo({ tx: bounds.center[0], ty: bounds.center[1], tz: bounds.center[2],
                        radius: bounds.homeRadius });
    }
  }

  function hasImportedMesh() { return !!importedMeshGroup; }

  /* ── Picking a node of an imported deck ────────────────────────────────
     The first part of the Imported mesh feature, after Node_ViZ and Deltares'
     visualize_mdpa_project.py: the nodes are drawn, a click on one selects it, and the
     Selection explorer says which SubModelParts it is in -- and which parts hold every
     other node at its position, which is how the two sides of an interface are told
     apart. The hover says the same in one line in the status bar.

     Picked on screen (`App.NodeParts.pickOnScreen`): a node is "clicked" when it is
     within PICK_PX pixels of the pointer, at any zoom and in 2D and 3D alike. A click
     further from every node is an ordinary click. Only the nodes of the parts that are
     shown can be picked. */
  var PICK_PX = 8;
  /* Overlapping nodes -- an interface split leaves two or three at one point -- are
     fanned around it on screen, FAN_PX out, each on a leader line, so each can be
     clicked (Node_ViZ's way). The angles are the node labels' own (mesh-labels.js
     `fanOffsets`), so a dot sits under its own number; FAN_PX is shorter than the
     labels' 24 so the number stays clear of the dot. A point fans only when the next
     position is at least FAN_ROOM_PX away on screen: zoomed out it stays one dot. */
  var FAN_PX = 14;
  var FAN_ROOM_PX = 3 * FAN_PX;
  var nodeFanCanvas = null;
  var importedNodeIndex = null;
  var importedPickable = null;     // {id: true} for the shown parts, rebuilt on demand
  var pickedNode = null;

  /* Each part's own nodes as dots, inside that part's group, so hiding the part hides
     them and they are drawn only where the part is. */
  function importedNodeDots(section) {
    if (!section || !section.node_ids || !importedNodeIndex) return null;
    var points = [];
    section.node_ids.forEach(function (id) {
      var c = importedNodeIndex.coords[id];
      if (c) points.push(new THREE.Vector3(c[0], c[1], c[2]));
    });
    if (!points.length) return null;
    var dots = new THREE.Points(new THREE.BufferGeometry().setFromPoints(points),
      new THREE.PointsMaterial({ color: 0x263238, size: 4, sizeAttenuation: false }));
    dots.renderOrder = 5;
    dots.userData.noPick = true;
    return dots;
  }

  function pickableNodes() {
    if (importedPickable) return importedPickable;
    importedPickable = {};
    Object.keys(importedSectionGroups).forEach(function (key) {
      if (!importedSectionGroups[key].visible) return;
      var section = importedSectionLabels[key];
      ((section && section.node_ids) || []).forEach(function (id) {
        importedPickable[id] = true;
      });
    });
    return importedPickable;
  }

  function projectNode(xyz) { return projectToScreen(xyz[0], xyz[1], xyz[2]); }

  function fanOffsets(count) {
    return App.MeshLabels ? App.MeshLabels.fanOffsets(count, FAN_PX) : null;
  }

  function nodeUnderPointer(ev) {
    if (!importedNodeIndex || !importedMeshGroup || !importedMeshGroup.visible) return null;
    var r = canvas.getBoundingClientRect();
    var click = { x: ev.clientX - r.left, y: ev.clientY - r.top };
    return App.NodeParts.pickOnScreen(importedNodeIndex, projectNode, click, PICK_PX,
                                      pickableNodes(), fanOffsets, FAN_ROOM_PX);
  }

  /* The fans, painted over the frame just drawn with its camera -- the offsets are
     pixels, so they have to be worked out again whenever the view moves. The picked
     node is red, the rest dark, each on a leader line back to the shared point. */
  function paintNodeFans() {
    var shown = importedNodeIndex && importedMeshGroup && importedMeshGroup.visible
                && App.NodeParts && host;
    if (!shown) {
      if (nodeFanCanvas) nodeFanCanvas.hidden = true;
      return;
    }
    if (!nodeFanCanvas) {
      nodeFanCanvas = document.createElement('canvas');
      nodeFanCanvas.className = 'vp-node-fans';
      host.appendChild(nodeFanCanvas);
    }
    var ratio = window.devicePixelRatio || 1;
    var width = host.clientWidth, height = host.clientHeight;
    if (nodeFanCanvas.width !== Math.round(width * ratio)
        || nodeFanCanvas.height !== Math.round(height * ratio)) {
      nodeFanCanvas.width = Math.round(width * ratio);
      nodeFanCanvas.height = Math.round(height * ratio);
    }
    nodeFanCanvas.hidden = false;
    var ctx = nodeFanCanvas.getContext('2d');
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    var fanned = App.NodeParts.screenTargets(importedNodeIndex, projectNode, fanOffsets,
                                             pickableNodes(), FAN_ROOM_PX)
      .filter(function (target) {
        return target.fanned && target.ax > -FAN_PX && target.ax < width + FAN_PX
               && target.ay > -FAN_PX && target.ay < height + FAN_PX;
      });
    ctx.lineWidth = 1;
    ctx.strokeStyle = 'rgba(38, 50, 56, 0.7)';
    fanned.forEach(function (target) {
      ctx.beginPath();
      ctx.moveTo(target.ax, target.ay);
      ctx.lineTo(target.x, target.y);
      ctx.stroke();
    });
    fanned.forEach(function (target) {
      ctx.beginPath();
      ctx.arc(target.x, target.y, 4, 0, 2 * Math.PI);
      ctx.fillStyle = target.id === pickedNode ? '#e6194b' : '#263238';
      ctx.fill();
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = '#ffffff';
      ctx.stroke();
    });
  }

  function pickImportedNode(ev) {
    var id = nodeUnderPointer(ev);
    if (id === null) {
      forgetPickedNode();
      return false;
    }
    showNode(id);
    return true;
  }

  function hoverImportedNode(ev) {
    if (!importedNodeIndex) return;
    var id = nodeUnderPointer(ev);
    if (id === null) {
      canvas.style.cursor = hovered ? 'pointer' : '';
      return;
    }
    canvas.style.cursor = 'pointer';
    var hint = document.getElementById('sb-hint');
    if (hint) hint.textContent = App.NodeParts.hint(importedNodeIndex, id);
  }

  /* Select node `id` of the imported deck: mark it and the nodes at its position, and
     put what it is in into the Selection explorer. Also what `node <id>` does while an
     imported deck is shown. */
  function showNode(id) {
    if (!importedNodeIndex || !App.NodeParts.partsOf(importedNodeIndex, id)) return false;
    pickedNode = id;
    needsRender = true;
    select(null);
    markNodes(App.NodeParts.samePosition(importedNodeIndex, id).map(function (other) {
      return importedNodeIndex.coords[other];
    }));
    App.OBJECT_PROPS = App.OBJECT_PROPS || {};
    App.OBJECT_PROPS['node:' + id] = App.NodeParts.selectionProps(importedNodeIndex, id);
    if (App.Explorer && App.Explorer.mountSelection) App.Explorer.mountSelection('node:' + id);
    if (App.Command && App.Command.note) {
      App.Command.note(App.NodeParts.hint(importedNodeIndex, id));
    }
    return true;
  }

  function forgetPickedNode() {
    if (pickedNode === null) return;
    if (App.OBJECT_PROPS) delete App.OBJECT_PROPS['node:' + pickedNode];
    pickedNode = null;
    needsRender = true;
    clearNodeMark();
  }

  function importedNodes() { return importedNodeIndex; }

  /* Drops one section entirely -- what "Accept" does with a part the checklist left
     unchecked: not merely hidden, gone, the same as if it had never been drawn. */
  function removeImportedSection(key) {
    importedPickable = null;
    disposeGroup(importedSectionGroups[key]);
    delete importedSectionGroups[key];
    delete importedEyes[key];
    delete importedSectionParts[key];
    delete importedSectionBBoxes[key];
    delete importedSectionLabels[key];
    refreshLabels();
  }

  /* "Imported mesh" in the Model explorer is one group row standing for whichever
     parts were accepted, the same way `computeGroupKeys`'s 'group:custom' etc. stand
     for a family of real project parts -- except there is no project-geometry payload
     to derive this family from, so the accepted list sets it directly. */
  function setImportedGroupKeys(keys) {
    groupKeys['group:imported'] = (keys || []).slice();
  }

  /* The checklist's per-row frame button: the bbox travels with the section (computed
     server-side, local to just that part's own nodes -- see mdpa_reader._section_dict),
     so this needs no client-side geometry walk to find it. */
  function frameImportedSection(key) {
    var bbox = importedSectionBBoxes[key];
    if (!orbit || !bbox) return;
    var bounds = App.Buffers.bounds(bbox);
    orbit.animateTo({ tx: bounds.center[0], ty: bounds.center[1], tz: bounds.center[2],
                      radius: Math.max(bounds.homeRadius, 0.5) });
  }

  /* ── Camera presets ─────────────────────────────────────────── */
  /* Angles on the Y-up basis frontend/js/orbit.js uses: phi is polar from +Y, and
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
     breathing room around a fitted section: enough that the support symbols under the
     bottom face stay clear of the rulers drawn over the viewport's edges. */
  var ORTHO_BASE = 46;
  var ORTHO_HALF_HEIGHT = 30;
  var ORTHO_MARGIN = 1.2;

  /* How far the wheel may dolly, as multiples of the fitted view rather than as
     metres. The frozen pair (8, and 6x the demo frame's 116) is a floor above the
     home radius of anything smaller than a few metres, which left the wheel dead
     and the zoom readout stuck. 0.08 is that same 8 on the demo domain. */
  var MIN_RADIUS_FRACTION = 0.08;
  var MAX_RADIUS_FACTOR = 6;

  /* A 2D section is seen through the orthographic camera, whose near plane sits far
     behind the model, so nothing clips however close it gets -- and an imported deck
     crowds dozens of nodes into the last few centimetres beside a sheet pile, which
     12.5x of a 70 m section still showed as one smear. 0.0002 is 5000x: about a
     centimetre across the viewport on that section. 3D keeps the floor above, which
     keeps the perspective camera's near plane (0.5) out of the model. */
  var MIN_RADIUS_FRACTION_2D = 0.0002;

  function radiusLimits(frame, dim) {
    var home = (frame && frame.homeRadius) || ORTHO_HALF_HEIGHT;
    var fraction = (dim === undefined ? dimension : dim) === 2
      ? MIN_RADIUS_FRACTION_2D : MIN_RADIUS_FRACTION;
    return { min: home * fraction, max: home * MAX_RADIUS_FACTOR };
  }

  function applyRadiusLimits() {
    if (!orbit || !frame) return;
    var limits = radiusLimits(frame, dimension);
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
    applyRadiusLimits();           // so does how close the wheel may get
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
    syncLabels();                          // over the frame just drawn, with its camera
    paintNodeFans();                       // likewise: the fans are in pixels

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
    generateMesh: generateMesh, meshRefinements: meshRefinements,
    hasMesh: hasMesh, resize: resize,
    meshSettings: meshSettings,
    setLabels: setLabels, labelsOn: labelsOn,
    refreshLabels: refreshLabels, syncLabels: syncLabels,
    projectToScreen: projectToScreen,
    showImportedMesh: showImportedMesh, clearImportedMesh: clearImportedMesh,
    syncPartColors: syncPartColors, coloredPartKeys: coloredPartKeys, partColor: partColor,
    boundsOf: boundsOf,
    nodeParts: nodeParts, nodePartsLoaded: nodePartsLoaded, markNodes: markNodes,
    showNode: showNode, importedNodes: importedNodes,
    clearNodeMark: clearNodeMark,
    hasImportedMesh: hasImportedMesh, removeImportedSection: removeImportedSection,
    importedEye: importedEye,
    setImportedGroupKeys: setImportedGroupKeys, importedLineOrder: importedLineOrder,
    frameImportedSection: frameImportedSection,
    // js/viewport.js rebuilds its soil boxes from App.LAYERS client-side. Here the soil
    // geometry is the server's, tessellated by /api/geometry, so there is nothing to
    // rebuild locally: a committed change reaches the scene through refresh() instead.
    // Kept because the frozen callers (js/app.js, js/command.js) call it
    // unconditionally, and refresh() would re-fetch the project and discard the
    // client-side edit they just made.
    rebuildSoil: function () {},
    refresh: refresh, gridReference: gridReference, computeModeGroups: computeModeGroups,
    soilKeysOf: soilKeysOf,
    computeGroupKeys: computeGroupKeys,
    loadGlyphSpec: loadGlyphSpec, loadGlyphGroup: loadGlyphGroup,
    waterLineSpec: waterLineSpec,
    conditionGlyphSpec: conditionGlyphSpec, conditionKeysOf: conditionKeysOf,
    soilFaceOutlines: soilFaceOutlines, forgetConditionEyes: forgetConditionEyes,
    applyStageVisibility: applyStageVisibility,
    normalLoadGlyphSpec: normalLoadGlyphSpec,
    getScene: function() { return scene; },
    getCamera: function() { return cam; },
    getCanvas: function() { return canvas; },
    // Ask for one frame. The loop is gated on `needsRender`, so anything that adds to
    // the scene from outside this module -- `App.ResultsView` draws a whole contoured
    // mesh into it -- otherwise changes nothing until the camera happens to move.
    requestRender: function () { needsRender = true; },
    getOrbit: function () { return orbit; }
  };
})();
