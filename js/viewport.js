/* ══════════════════════════════════════════════════════════════════
   viewport.js — the three.js scene.

   Coordinate system matches geotechnical convention: X east, Y north,
   Z up (metres). The model is a 50 × 40 × 25 m two-layer soil block
   with a braced excavation in the middle.
   ══════════════════════════════════════════════════════════════════ */

App.Viewport = (function () {

  /* ── Model dimensions ───────────────────────────────────────── */
  var X0 = 0, X1 = 50, Y0 = 0, Y1 = 40, ZTOP = 0, ZBOT = -25;
  var PX0 = 12, PX1 = 38, PY0 = 10, PY1 = 30;      // excavation pit
  var Z_PIT = -7.0, Z_WALL_TOE = -14.0, Z_WALL_TOP = 0.6;
  var Z_WATER = -1.5, Z_STRUT = -3.0;
  var CENTER = { x: (X0 + X1) / 2, y: (Y0 + Y1) / 2, z: -8 };

  var renderer, scene, camPersp, camOrtho, cam, orbit, canvas, host;
  var triadRenderer, triadScene, triadCam, triadCanvas;
  var raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2();
  var groups = {}, mats = {}, boxHelper = null;
  var hovered = null, selected = null, selectedKeys = [];
  var visible = {};              // key -> bool, driven by the Model explorer
  var modeGroups = {};           // mode -> [group keys]
  var showGrid = true, gridGroup, boundsGroup;
  var needsRender = true, meshBuilt = false;

  // 'soil' and 'boreholes' are virtual keys meaning "every soil layer" /
  // "every borehole" at once — the Model explorer's parent rows toggle and
  // select the whole group together, while each layer/borehole keeps its
  // own real key ('soil_L1', 'bh_bh1', …) so it can be picked and selected
  // independently in the viewport and the tree.
  var SOIL_LAYER_KEYS = App.LAYERS.map(function (l) { return 'soil_' + l.id; });
  var BOREHOLE_KEYS = App.BOREHOLES.map(function (b) { return 'bh_' + b.id; });

  /**
   * Expands a group key into the real group keys it stands for.
   * @param {?string} key Real key, or virtual 'soil' / 'boreholes'.
   * @return {!Array<string>} Matching keys; empty for a null key.
   */
  function keysFor(key) {
    if (key === 'soil') return SOIL_LAYER_KEYS.slice();
    if (key === 'boreholes') return BOREHOLE_KEYS.slice();
    return key ? [key] : [];
  }

  /* ══════════════════════════════════════════════════════════════
     Geometry helpers
     ══════════════════════════════════════════════════════════════ */

  /**
   * Builds an axis-aligned box mesh spanning the given extents (metres).
   * @param {number} x0
   * @param {number} x1
   * @param {number} y0
   * @param {number} y1
   * @param {number} z0
   * @param {number} z1
   * @param {!THREE.Material} material
   * @param {string} key Pick/selection key stored in userData.
   * @return {!THREE.Mesh}
   */
  function boxBetween(x0, x1, y0, y1, z0, z1, material, key) {
    var g = new THREE.BoxGeometry(x1 - x0, y1 - y0, z1 - z0);
    var m = new THREE.Mesh(g, material);
    m.position.set((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
    m.userData.key = key;
    return m;
  }

  /**
   * Builds a non-pickable outline of a mesh's feature edges.
   * @param {!THREE.Mesh} mesh
   * @param {number=} color Hex colour; defaults to 0x2a3140.
   * @param {number=} opacity Defaults to 0.35.
   * @return {!THREE.LineSegments}
   */
  function edgesOf(mesh, color, opacity) {
    var e = new THREE.LineSegments(
      new THREE.EdgesGeometry(mesh.geometry, 15),
      new THREE.LineBasicMaterial({ color: color || 0x2a3140, transparent: true,
                                    opacity: opacity === undefined ? 0.35 : opacity })
    );
    e.position.copy(mesh.position);
    e.rotation.copy(mesh.rotation);
    e.userData.noPick = true;
    return e;
  }

  /**
   * Adds an outlined box spanning the given extents (metres) to a group.
   * @param {!THREE.Group} group
   * @param {number} x0
   * @param {number} x1
   * @param {number} y0
   * @param {number} y1
   * @param {number} z0
   * @param {number} z1
   * @param {!THREE.Material} material
   * @param {string} key Pick/selection key.
   * @param {number=} edgeColor Hex colour of the outline.
   * @return {!THREE.Mesh} The box mesh.
   */
  function addBox(group, x0, x1, y0, y1, z0, z1, material, key, edgeColor) {
    var m = boxBetween(x0, x1, y0, y1, z0, z1, material, key);
    group.add(m);
    group.add(edgesOf(m, edgeColor, 0.28));
    return m;
  }

  /**
   * Returns the three.js material for a soil layer, resolved through its material id.
   * @param {!Object} layer Entry of App.LAYERS.
   * @return {!THREE.Material}
   */
  function soilMat(layer) {
    return mats['mat_' + App.matById(layer.mat).id];
  }

  /**
   * Returns the id of the borehole whose depths define the 3D soil block.
   * One representative borehole is used (not a sloping stratigraphy) — the
   * first one, whichever that is.
   * @return {string}
   */
  function refBoreholeId() { return App.BOREHOLES[0].id; }

  /**
   * Builds the soil block, optionally with the excavation pit removed.
   * Used with excavate=true for 'staged construction'.
   * @param {boolean} excavate Whether to cut the pit down to Z_PIT.
   * @param {string} key Pick/selection key for every box.
   * @return {!THREE.Group}
   */
  function buildSoil(excavate, key) {
    var g = new THREE.Group();
    var refBh = refBoreholeId();
    App.LAYERS.forEach(function (layer) {
      var zt = layer.tops[refBh], zb = layer.bots[refBh];
      var mat = soilMat(layer);

      if (!excavate || zt <= Z_PIT) {
        addBox(g, X0, X1, Y0, Y1, zb, zt, mat, key);
        return;
      }
      // Part of this layer sits below the pit floor → keep it whole.
      if (zb < Z_PIT) addBox(g, X0, X1, Y0, Y1, zb, Z_PIT, mat, key);
      var za = Math.max(zb, Z_PIT);                       // above the pit floor
      addBox(g, X0,  PX0, Y0,  Y1,  za, zt, mat, key);    // west
      addBox(g, PX1, X1,  Y0,  Y1,  za, zt, mat, key);    // east
      addBox(g, PX0, PX1, Y0,  PY0, za, zt, mat, key);    // south
      addBox(g, PX0, PX1, PY1, Y1,  za, zt, mat, key);    // north
    });
    return g;
  }

  /**
   * Builds the soil block as one THREE.Group per layer, so each layer can be
   * picked and selected independently in the viewport and Model explorer.
   * @return {!Object<string, !THREE.Group>} Groups keyed 'soil_<layerId>'.
   */
  function buildSoilLayers() {
    var byKey = {};
    var refBh = refBoreholeId();
    App.LAYERS.forEach(function (layer) {
      var key = 'soil_' + layer.id;
      var g = new THREE.Group();
      var zt = layer.tops[refBh], zb = layer.bots[refBh];
      addBox(g, X0, X1, Y0, Y1, zb, zt, soilMat(layer), key);
      byKey[key] = g;
    });
    return byKey;
  }

  /**
   * Builds borehole markers: a thin post from the borehole head down to the
   * deepest layer bottom there, with a small flag on top.
   * @return {!Object<string, !THREE.Group>} One group per borehole, keyed
   *     'bh_<id>', so each is independently pickable.
   */
  function buildBoreholes() {
    var byKey = {};
    var postMat = new THREE.MeshStandardMaterial({ color: 0x2a3140, roughness: 0.6 });
    var flagMat = new THREE.MeshStandardMaterial({ color: 0xd23b3b, roughness: 0.5 });
    App.BOREHOLES.forEach(function (b) {
      var key = 'bh_' + b.id;
      var zBot = Math.min.apply(null, App.LAYERS.map(function (l) { return l.bots[b.id]; }));
      var g = new THREE.Group();

      var h = b.head - zBot;
      var post = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.18, h, 12), postMat);
      post.rotation.x = Math.PI / 2;
      post.position.set(b.x, b.y, (b.head + zBot) / 2);
      post.userData.key = key;
      g.add(post);

      var flag = new THREE.Mesh(new THREE.ConeGeometry(0.5, 1.1, 12), flagMat);
      flag.position.set(b.x, b.y, b.head + 0.55);
      flag.userData.key = key;
      g.add(flag);

      byKey[key] = g;
    });
    return byKey;
  }

  /**
   * Builds the retaining walls: four thin vertical slabs around the pit.
   * @return {!THREE.Group}
   */
  function buildWalls() {
    var g = new THREE.Group(), t = 0.8, m = mats.wall;
    addBox(g, PX0 - t, PX0, PY0 - t, PY1 + t, Z_WALL_TOE, Z_WALL_TOP, m, 'wall', 0x1b2433);
    addBox(g, PX1, PX1 + t, PY0 - t, PY1 + t, Z_WALL_TOE, Z_WALL_TOP, m, 'wall', 0x1b2433);
    addBox(g, PX0, PX1, PY0 - t, PY0, Z_WALL_TOE, Z_WALL_TOP, m, 'wall', 0x1b2433);
    addBox(g, PX0, PX1, PY1, PY1 + t, Z_WALL_TOE, Z_WALL_TOP, m, 'wall', 0x1b2433);
    return g;
  }

  /**
   * Builds horizontal struts spanning the pit at Z_STRUT, plus two walers.
   * @return {!THREE.Group}
   */
  function buildStruts() {
    var g = new THREE.Group();
    [14, 20, 26, 32].forEach(function (x) {
      var geo = new THREE.CylinderGeometry(0.28, 0.28, PY1 - PY0 + 1.6, 10);
      var m = new THREE.Mesh(geo, mats.beam);
      m.rotation.x = Math.PI / 2;                        // align along +Y
      m.position.set(x, (PY0 + PY1) / 2, Z_STRUT);
      m.userData.key = 'struts';
      g.add(m);
    });
    // Two walers running along the long walls.
    [PY0 - 0.5, PY1 + 0.5].forEach(function (y) {
      var geo = new THREE.BoxGeometry(PX1 - PX0, 0.5, 0.6);
      var m = new THREE.Mesh(geo, mats.beam);
      m.position.set((PX0 + PX1) / 2, y, Z_STRUT);
      m.userData.key = 'struts';
      g.add(m);
    });
    return g;
  }

  /**
   * Builds inclined ground anchors (35° down) on the two long walls.
   * @return {!THREE.Group}
   */
  function buildAnchors() {
    var g = new THREE.Group(), len = 11, inc = 35 * Math.PI / 180;
    [[PY0 - 0.4, -1], [PY1 + 0.4, 1]].forEach(function (side) {
      var y0 = side[0], dir = side[1];
      [15, 21, 27, 33].forEach(function (x) {
        var geo = new THREE.CylinderGeometry(0.11, 0.11, len, 8);
        var m = new THREE.Mesh(geo, mats.anchor);
        // Direction: outward in Y and downward in Z.
        var dy = dir * Math.cos(inc), dz = -Math.sin(inc);
        m.position.set(x, y0 + dy * len / 2, -4.5 + dz * len / 2);
        m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0),
                                        new THREE.Vector3(0, dy, dz).normalize());
        m.userData.key = 'anchors';
        g.add(m);
        var head = new THREE.Mesh(new THREE.SphereGeometry(0.32, 10, 8), mats.anchor);
        head.position.set(x, y0, -4.5);
        head.userData.key = 'anchors';
        g.add(head);
      });
    });
    return g;
  }

  /**
   * Builds the embedded beam rows (bored piles) under the pit floor.
   * @return {!THREE.Group}
   */
  function buildPiles() {
    var g = new THREE.Group();
    for (var i = 0; i < 4; i++) for (var j = 0; j < 3; j++) {
      var geo = new THREE.CylinderGeometry(0.3, 0.3, 9, 10);
      var m = new THREE.Mesh(geo, mats.pile);
      m.rotation.x = Math.PI / 2;
      m.position.set(16 + i * 6, 14 + j * 6, Z_PIT - 4.5);
      m.userData.key = 'piles';
      g.add(m);
    }
    return g;
  }

  /**
   * Builds the surface load patch beside the excavation, with arrows.
   * @return {!THREE.Group}
   */
  function buildLoad() {
    var g = new THREE.Group();
    var pad = new THREE.Mesh(new THREE.BoxGeometry(9, 12, 0.25), mats.load);
    pad.position.set(5.5, 20, ZTOP + 0.15);
    pad.userData.key = 'load';
    g.add(pad);
    for (var i = 0; i < 3; i++) for (var j = 0; j < 4; j++) {
      var x = 2.5 + i * 3, y = 15.5 + j * 3;
      var shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 2.4, 6), mats.load);
      shaft.rotation.x = Math.PI / 2;
      shaft.position.set(x, y, ZTOP + 1.5);
      shaft.userData.key = 'load';
      var tip = new THREE.Mesh(new THREE.ConeGeometry(0.24, 0.6, 8), mats.load);
      tip.rotation.x = Math.PI;
      tip.position.set(x, y, ZTOP + 0.45);
      tip.userData.key = 'load';
      g.add(shaft); g.add(tip);
    }
    return g;
  }

  /**
   * Builds the phreatic-level plane at Z_WATER, slightly wider than the model.
   * @return {!THREE.Group}
   */
  function buildWater() {
    var g = new THREE.Group();
    var plane = new THREE.Mesh(new THREE.BoxGeometry(X1 - X0 + 6, Y1 - Y0 + 6, 0.06), mats.water);
    plane.position.set(CENTER.x, CENTER.y, Z_WATER);
    plane.userData.key = 'water';
    g.add(plane);
    g.add(edgesOf(plane, 0x1a5f96, 0.6));
    // Phreatic-level tick marks on the outside faces.
    var lineMat = new THREE.LineBasicMaterial({ color: 0x1a5f96 });
    var pts = [new THREE.Vector3(X0 - 3, Y0 - 3, Z_WATER), new THREE.Vector3(X1 + 3, Y0 - 3, Z_WATER)];
    g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), lineMat));
    return g;
  }

  /**
   * Builds the dewatering wells inside the pit.
   * @return {!THREE.Group}
   */
  function buildWells() {
    var g = new THREE.Group();
    [[18, 15], [32, 25]].forEach(function (p) {
      var pipe = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.35, 15, 12), mats.well);
      pipe.rotation.x = Math.PI / 2;
      pipe.position.set(p[0], p[1], -7.5);
      pipe.userData.key = 'wells';
      g.add(pipe);
      var cap = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.7, 0.8, 12), mats.well);
      cap.rotation.x = Math.PI / 2;
      cap.position.set(p[0], p[1], 0.6);
      cap.userData.key = 'wells';
      g.add(cap);
    });
    return g;
  }

  /**
   * Builds the finite element mesh display: triangulated surfaces of the soil block.
   * @return {!THREE.Group}
   */
  function buildMesh() {
    var g = new THREE.Group();
    var faces = [
      // [w, h, position, rotation(euler)]
      [X1 - X0, Y1 - Y0, [CENTER.x, CENTER.y, ZTOP], [0, 0, 0]],
      [X1 - X0, Y1 - Y0, [CENTER.x, CENTER.y, ZBOT], [Math.PI, 0, 0]],
      [X1 - X0, ZTOP - ZBOT, [CENTER.x, Y0, (ZTOP + ZBOT) / 2], [Math.PI / 2, 0, 0]],
      [X1 - X0, ZTOP - ZBOT, [CENTER.x, Y1, (ZTOP + ZBOT) / 2], [-Math.PI / 2, 0, 0]],
      [Y1 - Y0, ZTOP - ZBOT, [X0, CENTER.y, (ZTOP + ZBOT) / 2], [Math.PI / 2, 0, -Math.PI / 2]],
      [Y1 - Y0, ZTOP - ZBOT, [X1, CENTER.y, (ZTOP + ZBOT) / 2], [Math.PI / 2, 0, Math.PI / 2]]
    ];
    faces.forEach(function (f) {
      var segA = Math.max(4, Math.round(f[0] / 2.6));
      var segB = Math.max(4, Math.round(f[1] / 2.6));
      var geo = new THREE.PlaneGeometry(f[0], f[1], segA, segB);
      // Jitter the interior vertices so the triangulation looks unstructured.
      var pos = geo.attributes.position;
      for (var i = 0; i < pos.count; i++) {
        var px = pos.getX(i), py = pos.getY(i);
        var edgeX = Math.abs(Math.abs(px) - f[0] / 2) < 1e-6;
        var edgeY = Math.abs(Math.abs(py) - f[1] / 2) < 1e-6;
        if (!edgeX) pos.setX(i, px + (pseudo(i * 3.1) - 0.5) * 1.5);
        if (!edgeY) pos.setY(i, py + (pseudo(i * 7.7) - 0.5) * 1.5);
      }
      geo.computeVertexNormals();

      var face = new THREE.Mesh(geo, mats.meshFace);
      face.position.fromArray(f[2]);
      face.rotation.fromArray(f[3]);
      face.userData.key = 'mesh';
      g.add(face);

      var wire = new THREE.LineSegments(new THREE.WireframeGeometry(geo), mats.meshWire);
      wire.position.copy(face.position);
      wire.rotation.copy(face.rotation);
      wire.userData.noPick = true;
      g.add(wire);
    });
    return g;
  }

  /**
   * Returns a deterministic pseudo-random number in [0, 1) — no Math.random needed.
   * @param {number} n Seed.
   * @return {number}
   */
  function pseudo(n) { var s = Math.sin(n * 12.9898) * 43758.5453; return s - Math.floor(s); }

  /**
   * Builds a non-pickable canvas-texture text label facing the camera.
   * @param {string} text
   * @param {number} x
   * @param {number} y
   * @param {number} z
   * @param {number=} scale Size multiplier; defaults to 1.
   * @return {!THREE.Sprite}
   */
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

  /**
   * Builds the ground grid, laid in the XY plane just below the model base.
   * @return {!THREE.Group}
   */
  function buildGrid() {
    var g = new THREE.Group();
    var grid = new THREE.GridHelper(80, 32, 0x8fa0b5, 0xb2bdcc);
    grid.rotation.x = Math.PI / 2;                    // GridHelper is XZ by default
    grid.position.set(CENTER.x, CENTER.y, ZBOT - 0.4);
    grid.material.transparent = true;
    grid.material.opacity = 0.55;
    grid.userData.noPick = true;
    g.add(grid);
    return g;
  }

  /**
   * Builds the model bounding box with x/y axis labels.
   * @return {!THREE.Group}
   */
  function buildBounds() {
    var g = new THREE.Group();
    var box = new THREE.Box3(new THREE.Vector3(X0, Y0, ZBOT), new THREE.Vector3(X1, Y1, ZTOP));
    var helper = new THREE.Box3Helper(box, 0x4a5568);
    helper.material.transparent = true;
    helper.material.opacity = 0.5;
    helper.userData.noPick = true;
    g.add(helper);
    g.add(makeLabel('x', X1 + 3, Y0, ZBOT, 0.8));
    g.add(makeLabel('y', X0, Y1 + 3, ZBOT, 0.8));
    return g;
  }

  /* ══════════════════════════════════════════════════════════════
     Materials
     ══════════════════════════════════════════════════════════════ */
  /**
   * Creates the shared materials into `mats`, one per App.MATERIALS entry
   * plus fixed ones for structures, water and the mesh.
   */
  function buildMaterials() {
    // Keyed by material id, so a layer's colour follows its assigned material.
    App.MATERIALS.forEach(function (m) {
      mats['mat_' + m.id] = new THREE.MeshLambertMaterial({ color: new THREE.Color(m.color) });
    });
    mats.wall   = new THREE.MeshLambertMaterial({ color: 0x4b6ea8 });
    mats.beam   = new THREE.MeshLambertMaterial({ color: 0xb5573a });
    mats.anchor = new THREE.MeshLambertMaterial({ color: 0x2f6f4f });
    mats.pile   = new THREE.MeshLambertMaterial({ color: 0x7a6a55 });
    mats.load   = new THREE.MeshLambertMaterial({ color: 0xd4342d });
    mats.marker = new THREE.MeshLambertMaterial({ color: 0xf0a830 });
    mats.well   = new THREE.MeshLambertMaterial({ color: 0x2f8fd8 });
    mats.water  = new THREE.MeshLambertMaterial({ color: 0x2f8fd8, transparent: true,
                                                  opacity: 0.34, depthWrite: false });
    mats.meshFace = new THREE.MeshLambertMaterial({ color: 0xd9dee6, transparent: true,
                                                    opacity: 0.95, side: THREE.DoubleSide,
                                                    polygonOffset: true, polygonOffsetFactor: 1,
                                                    polygonOffsetUnits: 1 });
    mats.meshWire = new THREE.LineBasicMaterial({ color: 0x37474f, transparent: true, opacity: 0.75 });

    // Remember base emissive colours so hover/selection can be undone.
    Object.keys(mats).forEach(function (k) {
      if (mats[k].emissive) mats[k].userData = { base: mats[k].emissive.clone() };
    });
  }

  /**
   * Sets the emissive colour of every material in a group (hover/selection tint).
   * Materials are shared, so this also tints other groups using them.
   * @param {string} key Group key.
   * @param {number} hex
   */
  function setEmissive(key, hex) {
    var g = groups[key];
    if (!g) return;
    g.traverse(function (o) {
      if (o.material && o.material.emissive && o.material.userData) {
        o.material.emissive.setHex(hex);
      }
    });
    needsRender = true;
  }

  /**
   * Restores the base emissive colour of every material in a group.
   * @param {string} key Group key.
   */
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
     Scene assembly
     ══════════════════════════════════════════════════════════════ */
  /**
   * Creates the renderer, scene, cameras and all model groups, wires up
   * pointer and resize handling, and starts the render loop.
   * Expects #scene, #viewport and #triad in the DOM.
   */
  function init() {
    canvas = document.getElementById('scene');
    host = document.getElementById('viewport');

    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
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

    buildMaterials();

    gridGroup = buildGrid();
    boundsGroup = buildBounds();
    scene.add(gridGroup);
    scene.add(boundsGroup);

    var soilLayers = buildSoilLayers();
    Object.keys(soilLayers).forEach(function (k) { groups[k] = soilLayers[k]; });
    var boreholes = buildBoreholes();
    Object.keys(boreholes).forEach(function (k) { groups[k] = boreholes[k]; });
    groups.excavation = buildSoil(true, 'excavation');
    groups.wall       = buildWalls();
    groups.struts     = buildStruts();
    groups.anchors    = buildAnchors();
    groups.piles      = buildPiles();
    groups.load       = buildLoad();
    groups.water      = buildWater();
    groups.wells      = buildWells();
    groups.mesh       = new THREE.Group();          // built lazily on "Generate mesh"

    Object.keys(groups).forEach(function (k) {
      groups[k].name = k;
      groups[k].visible = false;
      visible[k] = true;                            // explorer default = shown
      scene.add(groups[k]);
    });

    modeGroups = buildModeGroups();

    camPersp = new THREE.PerspectiveCamera(42, 1, 0.5, 3000);
    camOrtho = new THREE.OrthographicCamera(-1, 1, 1, -1, -2000, 4000);
    cam = camPersp;

    orbit = new App.Orbit(canvas, {
      tx: CENTER.x, ty: CENTER.y, tz: CENTER.z,
      radius: 118, theta: -Math.PI * 0.68, phi: Math.PI * 0.33,
      minRadius: 8, maxRadius: 700, orthoBase: 46
    });
    orbit.onChange = function () { needsRender = true; };

    buildTriad();
    bindPointer();

    if (window.ResizeObserver) new ResizeObserver(resize).observe(host);
    window.addEventListener('resize', resize);
    resize();
    animate();
  }

  /* ── Axis triad (its own tiny renderer) ─────────────────────── */
  /** Sets up the axis triad's renderer, scene and camera on #triad. */
  function buildTriad() {
    triadCanvas = document.getElementById('triad');
    triadRenderer = new THREE.WebGLRenderer({ canvas: triadCanvas, antialias: true, alpha: true });
    triadRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    triadRenderer.setSize(86, 86, false);
    triadScene = new THREE.Scene();
    triadCam = new THREE.OrthographicCamera(-1.5, 1.5, 1.5, -1.5, -10, 10);

    var axes = [
      [new THREE.Vector3(1, 0, 0), 0xd23b3b, 'x'],
      [new THREE.Vector3(0, 1, 0), 0x2f9e44, 'y'],
      [new THREE.Vector3(0, 0, 1), 0x2b6cd4, 'z']
    ];
    axes.forEach(function (a) {
      var arrow = new THREE.ArrowHelper(a[0], new THREE.Vector3(0, 0, 0), 1.05, a[1], 0.3, 0.18);
      triadScene.add(arrow);
      var lbl = makeLabel(a[2], a[0].x * 1.34, a[0].y * 1.34, a[0].z * 1.34, 0.42);
      triadScene.add(lbl);
    });
  }

  /* ── Pointer: hover, pick, context menu, coordinate readout ─── */
  /**
   * Returns the pickable meshes of all visible groups.
   * @return {!Array<!THREE.Mesh>}
   */
  function pickables() {
    var list = [];
    Object.keys(groups).forEach(function (k) {
      if (!groups[k].visible) return;
      groups[k].traverse(function (o) { if (o.isMesh && !o.userData.noPick) list.push(o); });
    });
    return list;
  }

  /**
   * Raycasts from the pointer position into the visible scene.
   * Leaves `raycaster` aimed along the pointer ray for later use.
   * @param {!MouseEvent} ev
   * @return {?THREE.Intersection} Nearest hit, or null.
   */
  function pickAt(ev) {
    var r = canvas.getBoundingClientRect();
    pointer.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
    pointer.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
    raycaster.setFromCamera(pointer, cam);
    var hits = raycaster.intersectObjects(pickables(), false);
    return hits.length ? hits[0] : null;
  }

  var groundPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  var scratch = new THREE.Vector3();

  /** Binds hover, click-select, context-menu and coordinate-readout handlers to the canvas. */
  function bindPointer() {
    var moved = false;

    canvas.addEventListener('mousedown', function () { moved = false; });
    canvas.addEventListener('mousemove', function (ev) {
      moved = true;
      var hit = pickAt(ev);
      var key = hit ? hit.object.userData.key : null;

      if (key !== hovered) {
        if (hovered && selectedKeys.indexOf(hovered) < 0) restoreEmissive(hovered);
        hovered = key;
        if (hovered && selectedKeys.indexOf(hovered) < 0) setEmissive(hovered, 0x2a3550);
        canvas.style.cursor = hovered ? 'pointer' : '';
      }

      // Status-bar coordinates: use the hit point, else the z = 0 plane.
      var p = hit ? hit.point : raycaster.ray.intersectPlane(groundPlane, scratch);
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
  /**
   * Selects a group (or virtual 'soil' / 'boreholes'), tinting it and
   * drawing a bounding box. Hidden groups are ignored.
   * @param {?string} key Group key, or null to clear the selection.
   */
  function select(key) {
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
  /**
   * Returns which group keys each workflow mode shows.
   * @return {!Object<string, !Array<string>>} Group keys keyed by mode.
   */
  function buildModeGroups() {
    return {
      soil:       SOIL_LAYER_KEYS.concat(BOREHOLE_KEYS),
      structures: SOIL_LAYER_KEYS.concat(BOREHOLE_KEYS, ['wall', 'struts', 'anchors', 'piles', 'load']),
      mesh:       ['mesh', 'wall'],
      flow:       SOIL_LAYER_KEYS.concat(BOREHOLE_KEYS, ['water', 'wells', 'wall']),
      staged:     ['excavation', 'wall', 'struts', 'anchors', 'water']
    };
  }

  /**
   * Syncs the cached soil materials with App.MATERIALS.
   * buildMaterials() caches them at init, but the material editor can recolour
   * or add entries later; without this a colour edit never reaches the scene
   * and a layer assigned a new material would get an undefined material.
   */
  function syncSoilMaterials() {
    App.MATERIALS.forEach(function (m) {
      var key = 'mat_' + m.id;
      if (mats[key]) {
        mats[key].color.set(m.color);
      } else {
        mats[key] = new THREE.MeshLambertMaterial({ color: new THREE.Color(m.color) });
        if (mats[key].emissive) mats[key].userData = { base: mats[key].emissive.clone() };
      }
    });
  }

  /**
   * Rebuilds the soil-layer, borehole and excavation groups from the current
   * App.LAYERS / App.BOREHOLES and reapplies the active mode's visibility.
   * The "Modify soil layers" dialog and borehole tools mutate those arrays in
   * place; call App.refreshSoilData() first to keep the tree and Selection
   * explorer in sync too.
   */
  function rebuildSoil() {
    syncSoilMaterials();
    SOIL_LAYER_KEYS.concat(BOREHOLE_KEYS, ['excavation']).forEach(function (k) {
      var g = groups[k];
      if (!g) return;
      scene.remove(g);
      g.traverse(function (o) { if (o.isMesh || o.isLineSegments) o.geometry.dispose(); });
      delete groups[k];
      delete visible[k];
    });

    SOIL_LAYER_KEYS = App.LAYERS.map(function (l) { return 'soil_' + l.id; });
    BOREHOLE_KEYS = App.BOREHOLES.map(function (b) { return 'bh_' + b.id; });

    var soilLayers = buildSoilLayers();
    Object.keys(soilLayers).forEach(function (k) { groups[k] = soilLayers[k]; });
    var boreholes = buildBoreholes();
    Object.keys(boreholes).forEach(function (k) { groups[k] = boreholes[k]; });
    groups.excavation = buildSoil(true, 'excavation');

    SOIL_LAYER_KEYS.concat(BOREHOLE_KEYS, ['excavation']).forEach(function (k) {
      groups[k].name = k;
      groups[k].visible = false;
      visible[k] = true;
      scene.add(groups[k]);
    });

    modeGroups = buildModeGroups();
    if (selected && !selectedKeys.every(function (k) { return groups[k]; })) select(null);
    setMode(App.state.mode);
    needsRender = true;
  }

  /**
   * Shows the groups belonging to a workflow mode, respecting explorer visibility.
   * Clears the selection if any selected group becomes hidden.
   * @param {string} mode One of 'soil', 'structures', 'mesh', 'flow', 'staged'.
   */
  function setMode(mode) {
    var wanted = modeGroups[mode] || [];
    Object.keys(groups).forEach(function (k) {
      groups[k].visible = wanted.indexOf(k) >= 0 && visible[k] !== false;
    });
    if (mode === 'mesh' && !meshBuilt) groups.mesh.visible = false;
    if (selected && !selectedKeys.every(function (k) { return groups[k] && groups[k].visible; })) select(null);
    needsRender = true;
  }

  /**
   * Sets a group's Model-explorer visibility; it only shows if the active mode includes it.
   * @param {string} key Group key, or virtual 'soil' / 'boreholes'.
   * @param {boolean} on
   */
  function setVisible(key, on) {
    if (key === 'soil' || key === 'boreholes') {
      keysFor(key).forEach(function (k) { setVisible(k, on); });
      return;
    }
    if (!(key in groups)) return;
    visible[key] = on;
    var mode = App.state.mode;
    var wanted = modeGroups[mode] || [];
    groups[key].visible = on && wanted.indexOf(key) >= 0;
    if (key === 'mesh' && !meshBuilt) groups.mesh.visible = false;
    if (!on && selectedKeys.indexOf(key) >= 0) select(null);
    needsRender = true;
  }

  /**
   * Returns whether a group is toggled visible in the Model explorer.
   * @param {string} key Group key, or virtual 'soil' / 'boreholes' (true only if all are).
   * @return {boolean}
   */
  function isVisible(key) {
    if (key === 'soil' || key === 'boreholes') {
      return keysFor(key).every(function (k) { return visible[k] !== false; });
    }
    return visible[key] !== false;
  }

  /* ── Mesh generation (fake progress, real geometry) ─────────── */
  /**
   * Runs a simulated meshing progress overlay, then builds the mesh group once.
   * @param {function()=} done Called after the mesh is shown.
   */
  function generateMesh(done) {
    var overlay = document.getElementById('vp-loading');
    var bar = overlay.querySelector('.vp-progress i');
    var label = overlay.querySelector('.vp-loading-label');
    overlay.hidden = false;
    bar.style.width = '0%';

    var steps = [
      [12,  'Checking geometry consistency…'],
      [30,  'Generating surface mesh…'],
      [58,  'Generating volume mesh…'],
      [80,  'Applying local refinements…'],
      [94,  'Optimising element quality…'],
      [100, 'Mesh generated: 24 118 elements, 38 942 nodes']
    ];
    var i = 0;
    (function next() {
      if (i >= steps.length) {
        setTimeout(function () {
          overlay.hidden = true;
          if (!meshBuilt) {
            scene.remove(groups.mesh);
            groups.mesh = buildMesh();
            groups.mesh.name = 'mesh';
            scene.add(groups.mesh);
            meshBuilt = true;
          }
          setMode(App.state.mode);
          needsRender = true;
          if (done) done();
        }, 320);
        return;
      }
      bar.style.width = steps[i][0] + '%';
      label.textContent = steps[i][1];
      i++;
      setTimeout(next, 230 + (i === 3 ? 400 : 0));
    })();
  }

  /**
   * Returns whether the mesh has been generated.
   * @return {boolean}
   */
  function hasMesh() { return meshBuilt; }

  /* ── Camera presets ─────────────────────────────────────────── */
  var VIEWS = {
    iso:   { theta: -Math.PI * 0.68, phi: Math.PI * 0.33 },
    front: { theta: -Math.PI / 2,    phi: Math.PI / 2 },
    side:  { theta: 0,               phi: Math.PI / 2 },
    top:   { theta: -Math.PI / 2,    phi: 0.035 }
  };

  /**
   * Animates the camera to a preset view centred on the model.
   * @param {string} name 'iso', 'front', 'side' or 'top'; unknown names fall back to 'iso'.
   */
  function setView(name) {
    var v = VIEWS[name] || VIEWS.iso;
    orbit.animateTo({ theta: v.theta, phi: v.phi, radius: 118,
                      tx: CENTER.x, ty: CENTER.y, tz: CENTER.z });
    needsRender = true;
  }

  /** Animates the camera to frame all visible groups, or the model box if none are visible. */
  function zoomFit() {
    var box = new THREE.Box3();
    Object.keys(groups).forEach(function (k) {
      if (groups[k].visible) box.expandByObject(groups[k]);
    });
    if (box.isEmpty()) box.set(new THREE.Vector3(X0, Y0, ZBOT), new THREE.Vector3(X1, Y1, ZTOP));
    var c = box.getCenter(new THREE.Vector3());
    var sphere = box.getBoundingSphere(new THREE.Sphere());
    var r = sphere.radius / Math.sin(THREE.MathUtils.degToRad(camPersp.fov) / 2) * 1.06;
    orbit.animateTo({ tx: c.x, ty: c.y, tz: c.z, radius: Math.max(orbit.minRadius, r) });
    needsRender = true;
  }

  /**
   * Moves the camera towards or away from the orbit target.
   * @param {number} dir Dolly direction, passed to App.Orbit#dolly.
   */
  function dolly(dir) { orbit.dolly(dir); }

  /**
   * Switches between perspective and orthographic projection.
   * @param {boolean} persp True for perspective.
   */
  function setProjection(persp) {
    cam = persp ? camPersp : camOrtho;
    resize();
    needsRender = true;
  }

  /**
   * Shows or hides the ground grid and model bounding box.
   * @param {boolean} on
   */
  function setGrid(on) {
    showGrid = on;
    gridGroup.visible = on;
    boundsGroup.visible = on;
    needsRender = true;
  }

  /* ── Render loop ────────────────────────────────────────────── */
  /** Resizes the renderer and both cameras to the #viewport host element. */
  function resize() {
    if (!host) return;
    var w = host.clientWidth, h = host.clientHeight;
    if (w < 2 || h < 2) return;
    renderer.setSize(w, h, false);
    camPersp.aspect = w / h;
    camPersp.updateProjectionMatrix();
    var a = w / h, s = 30;
    camOrtho.left = -s * a; camOrtho.right = s * a;
    camOrtho.top = s; camOrtho.bottom = -s;
    camOrtho.updateProjectionMatrix();
    needsRender = true;
  }

  /**
   * Runs the render loop; redraws the scene and triad only when needed.
   * Also pushes the zoom percentage to the status bar.
   */
  function animate() {
    requestAnimationFrame(animate);
    if (orbit.tick()) needsRender = true;
    if (!needsRender) return;
    needsRender = false;

    orbit.apply(cam);
    renderer.render(scene, cam);

    // Triad mirrors the main camera orientation.
    triadCam.position.copy(cam.position).sub(orbit.target).normalize().multiplyScalar(4);
    triadCam.up.set(0, 0, 1);
    triadCam.lookAt(0, 0, 0);
    triadRenderer.render(triadScene, triadCam);

    App.setZoom(Math.round(118 / orbit.radius * 100));
  }

  return {
    init: init, setMode: setMode, setVisible: setVisible, isVisible: isVisible,
    select: select, setView: setView, zoomFit: zoomFit, dolly: dolly,
    setProjection: setProjection, setGrid: setGrid, rebuildSoil: rebuildSoil,
    generateMesh: generateMesh, hasMesh: hasMesh, resize: resize
  };
})();
