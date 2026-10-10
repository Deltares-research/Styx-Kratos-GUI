/* ══════════════════════════════════════════════════════════════════
   orbit.js — minimal Z-up orbit / pan / dolly camera controller.
   Written by hand so the mockup carries no three.js example files
   (those are version-fragile and would break the file:// setup).

     left drag     orbit
     middle drag   pan          shift + left drag  pan
     wheel         dolly
   ══════════════════════════════════════════════════════════════════ */

/**
 * Spherical camera controller around a target point, Z up.
 * @param {!Element} domElement Element that receives mouse and wheel input.
 * @param {?Object=} opts Initial state: tx, ty, tz (target), radius, theta
 *     (azimuth), phi (polar angle from +Z), minRadius, maxRadius, and orthoBase
 *     (radius-to-zoom factor for orthographic cameras).
 * @constructor
 */
App.Orbit = function (domElement, opts) {
  opts = opts || {};

  var self = this;
  var TWO_PI = Math.PI * 2;

  this.target  = new THREE.Vector3(opts.tx || 0, opts.ty || 0, opts.tz || 0);
  this.radius  = opts.radius || 100;
  this.theta   = opts.theta !== undefined ? opts.theta : -Math.PI * 0.62;  // azimuth
  this.phi     = opts.phi   !== undefined ? opts.phi   :  Math.PI * 0.34;  // polar from +Z
  this.minRadius = opts.minRadius || 4;
  this.maxRadius = opts.maxRadius || 900;
  this.enabled = true;
  this.onChange = null;

  var rotSpeed = 0.0075, panSpeed = 0.0016, dollyStep = 1.12;
  var dragging = null, lastX = 0, lastY = 0;

  /* ── Apply the current spherical state to a camera ──────────── */
  /**
   * Positions and aims a camera from the current spherical state.
   * @param {!THREE.Camera} camera
   */
  this.apply = function (camera) {
    var sp = Math.sin(self.phi), cp = Math.cos(self.phi);
    camera.up.set(0, 0, 1);
    camera.position.set(
      self.target.x + self.radius * sp * Math.cos(self.theta),
      self.target.y + self.radius * sp * Math.sin(self.theta),
      self.target.z + self.radius * cp
    );
    camera.lookAt(self.target);
    if (camera.isOrthographicCamera) {
      camera.zoom = (opts.orthoBase || 60) / self.radius;
      camera.updateProjectionMatrix();
    }
  };

  /* ── Animated transition to a new view ──────────────────────── */
  var anim = null;
  /**
   * Starts an eased transition to a new view; tick() advances it.
   * @param {!Object} state Any of theta, phi, radius, tx, ty, tz; omitted ones keep
   *     their current value. Theta takes the shorter way round.
   * @param {number=} ms Duration; defaults to 420.
   */
  this.animateTo = function (state, ms) {
    var from = { theta: self.theta, phi: self.phi, radius: self.radius,
                 tx: self.target.x, ty: self.target.y, tz: self.target.z };
    var to = {
      theta: state.theta !== undefined ? nearestAngle(from.theta, state.theta) : from.theta,
      phi:    state.phi    !== undefined ? state.phi    : from.phi,
      radius: state.radius !== undefined ? state.radius : from.radius,
      tx: state.tx !== undefined ? state.tx : from.tx,
      ty: state.ty !== undefined ? state.ty : from.ty,
      tz: state.tz !== undefined ? state.tz : from.tz
    };
    var t0 = performance.now(), dur = ms || 420;
    anim = function (now) {
      var k = Math.min(1, (now - t0) / dur);
      var e = k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;   // easeInOutCubic
      self.theta  = from.theta  + (to.theta  - from.theta)  * e;
      self.phi    = from.phi    + (to.phi    - from.phi)    * e;
      self.radius = from.radius + (to.radius - from.radius) * e;
      self.target.set(from.tx + (to.tx - from.tx) * e,
                      from.ty + (to.ty - from.ty) * e,
                      from.tz + (to.tz - from.tz) * e);
      if (k >= 1) anim = null;
      fire();
    };
  };
  /**
   * Advances a running transition by one frame.
   * @return {boolean} Whether a transition is still running.
   */
  this.tick = function () { if (anim) anim(performance.now()); return !!anim; };

  /**
   * Returns the angle equal to `to` (mod 2π) that lies closest to `from`.
   * @param {number} from Radians.
   * @param {number} to Radians.
   * @return {number}
   */
  function nearestAngle(from, to) {
    var d = ((to - from) % TWO_PI + TWO_PI + Math.PI) % TWO_PI - Math.PI;
    return from + d;
  }

  /** Notifies the onChange listener, if any. */
  function fire() { if (self.onChange) self.onChange(); }

  /* ── Interaction ─────────────────────────────────────────────── */
  /**
   * Starts an orbit, or a pan for the middle button or Shift; ignores right clicks.
   * @param {!MouseEvent} e
   */
  function down(e) {
    if (!self.enabled || e.button === 2) return;
    dragging = (e.button === 1 || e.shiftKey) ? 'pan' : 'orbit';
    lastX = e.clientX; lastY = e.clientY;
    anim = null;
    domElement.style.cursor = dragging === 'pan' ? 'move' : 'grabbing';
    e.preventDefault();
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  }

  /**
   * Applies the drag delta as an orbit or a pan.
   * @param {!MouseEvent} e
   */
  function move(e) {
    if (!dragging) return;
    var dx = e.clientX - lastX, dy = e.clientY - lastY;
    lastX = e.clientX; lastY = e.clientY;

    if (dragging === 'orbit') {
      self.theta -= dx * rotSpeed;
      self.phi = Math.max(0.03, Math.min(Math.PI - 0.03, self.phi - dy * rotSpeed));
    } else {
      // Pan in the camera plane, scaled so it tracks the cursor at target depth.
      var s = self.radius * panSpeed;
      var right = new THREE.Vector3(-Math.sin(self.theta), Math.cos(self.theta), 0);
      var upv = new THREE.Vector3(
        -Math.cos(self.phi) * Math.cos(self.theta),
        -Math.cos(self.phi) * Math.sin(self.theta),
         Math.sin(self.phi)
      );
      self.target.addScaledVector(right, -dx * s);
      self.target.addScaledVector(upv,    dy * s);
    }
    fire();
  }

  /** Ends the drag. */
  function up() {
    dragging = null;
    domElement.style.cursor = '';
    window.removeEventListener('mousemove', move);
    window.removeEventListener('mouseup', up);
  }

  /**
   * Dollies in or out by one step per wheel event.
   * @param {!WheelEvent} e
   */
  function wheel(e) {
    if (!self.enabled) return;
    e.preventDefault();
    anim = null;
    var f = e.deltaY > 0 ? dollyStep : 1 / dollyStep;
    self.radius = Math.max(self.minRadius, Math.min(self.maxRadius, self.radius * f));
    fire();
  }

  /**
   * Dollies one step, as from the toolbar zoom buttons.
   * @param {number} dir Positive moves closer, otherwise further away.
   */
  this.dolly = function (dir) {
    anim = null;
    var f = dir > 0 ? 1 / dollyStep : dollyStep;
    self.radius = Math.max(self.minRadius, Math.min(self.maxRadius, self.radius * f));
    fire();
  };

  domElement.addEventListener('mousedown', down);
  domElement.addEventListener('wheel', wheel, { passive: false });

  /** Removes the listeners added to domElement. */
  this.dispose = function () {
    domElement.removeEventListener('mousedown', down);
    domElement.removeEventListener('wheel', wheel);
  };
};
