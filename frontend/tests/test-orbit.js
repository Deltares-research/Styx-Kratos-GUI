/* The Y-up orbit / pan / dolly controller (frontend/js/orbit.js).

   Driven with real DOM events on a detached element and a real THREE camera, so what
   is checked is what a drag does -- including the sign of the pan, which was wrong once
   (a rightward drag panned left) when the Z-up controller's vector was copied across. */

(function () {

  function rig(opts) {
    var el = document.createElement('div');
    var orbit = new App.Orbit(el, opts || {});
    return { el: el, orbit: orbit };
  }

  function mouse(target, type, init) {
    var event = new MouseEvent(type, Object.assign({ bubbles: true, cancelable: true }, init));
    target.dispatchEvent(event);
    return event;
  }

  function drag(r, dx, dy, init) {
    mouse(r.el, 'mousedown', Object.assign({ clientX: 100, clientY: 100, button: 0 }, init));
    mouse(window, 'mousemove', { clientX: 100 + dx, clientY: 100 + dy });
    mouse(window, 'mouseup', {});
  }

  function wheel(r, deltaY) {
    r.el.dispatchEvent(new WheelEvent('wheel', { deltaY: deltaY, bubbles: true, cancelable: true }));
  }

  test('orbit: the camera sits at the radius from the target, standing up along +Y', function () {
    var r = rig({ tx: 1, ty: 2, tz: 3, radius: 10, theta: 0, phi: Math.PI / 2 });
    var camera = new THREE.PerspectiveCamera();
    r.orbit.apply(camera);

    T.near(camera.position.x, 11, 1e-9);
    T.near(camera.position.y, 2, 1e-9);
    T.near(camera.position.z, 3, 1e-9);
    T.eq([camera.up.x, camera.up.y, camera.up.z], [0, 1, 0]);
    T.near(camera.position.distanceTo(new THREE.Vector3(1, 2, 3)), 10, 1e-9);
  });

  test('orbit: the polar angle is measured from +Y, so phi = 0 looks straight down', function () {
    var r = rig({ radius: 5, theta: 0.3, phi: 0 });
    var camera = new THREE.PerspectiveCamera();
    r.orbit.apply(camera);

    T.near(camera.position.y, 5, 1e-9);
    T.near(camera.position.x, 0, 1e-9);
  });

  test('orbit: an orthographic camera zooms with the radius', function () {
    var r = rig({ radius: 30, orthoBase: 60 });
    var camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 1000);
    r.orbit.apply(camera);

    T.near(camera.zoom, 2, 1e-12);
  });

  test('orbit: a left drag turns the view, and the polar angle never flips over', function () {
    var r = rig({ theta: 0, phi: 1 });
    drag(r, 40, 0);
    T.near(r.orbit.theta, -40 * 0.0075, 1e-12, 'horizontal drag turns the azimuth');

    drag(r, 0, -100000);
    T.near(r.orbit.phi, Math.PI - 0.03, 1e-12, 'clamped short of the pole');
    drag(r, 0, 100000);
    T.near(r.orbit.phi, 0.03, 1e-12, 'and short of the other pole');
  });

  test('orbit: a shift-drag pans, and a rightward drag moves the target left', function () {
    var r = rig({ radius: 100, theta: -0.7, phi: 1.1 });
    var before = r.orbit.target.clone();
    drag(r, 50, 0, { shiftKey: true });

    var moved = r.orbit.target.clone().sub(before);
    var right = new THREE.Vector3(Math.sin(r.orbit.theta), 0, -Math.cos(r.orbit.theta));
    T.ok(moved.length() > 0, 'the target moved');
    T.ok(moved.dot(right) < 0, 'the model follows the cursor: the target goes the other way');
    T.near(r.orbit.theta, -0.7, 1e-12, 'a pan does not turn the view');
  });

  test('orbit: a middle drag pans too', function () {
    var r = rig({ radius: 100 });
    var before = r.orbit.target.clone();
    drag(r, 0, 30, { button: 1 });

    T.ok(r.orbit.target.distanceTo(before) > 0);
  });

  test('orbit: a right-button press starts nothing (it opens the context menu)', function () {
    var r = rig({ theta: 0 });
    drag(r, 40, 0, { button: 2 });

    T.eq(r.orbit.theta, 0);
  });

  test('orbit: the wheel dollies in steps and stops at the limits', function () {
    var r = rig({ radius: 100, minRadius: 50, maxRadius: 120 });
    wheel(r, 1);
    T.near(r.orbit.radius, 112, 1e-9, 'out by one step');
    wheel(r, 1);
    T.eq(r.orbit.radius, 120, 'clamped at the far limit');
    for (var i = 0; i < 20; i++) wheel(r, -1);
    T.eq(r.orbit.radius, 50, 'clamped at the near limit');
  });

  test('orbit: dolly(+1) is a step in, dolly(-1) a step out', function () {
    var r = rig({ radius: 112 });
    r.orbit.dolly(1);
    T.near(r.orbit.radius, 100, 1e-9);
    r.orbit.dolly(-1);
    T.near(r.orbit.radius, 112, 1e-9);
  });

  test('orbit: a disabled controller ignores drags and the wheel', function () {
    var r = rig({ radius: 100, theta: 0 });
    r.orbit.enabled = false;
    drag(r, 40, 0);
    wheel(r, 1);

    T.eq(r.orbit.theta, 0);
    T.eq(r.orbit.radius, 100);
  });

  test('orbit: every change is announced', function () {
    var r = rig({ radius: 100 });
    var calls = 0;
    r.orbit.onChange = function () { calls += 1; };
    drag(r, 10, 0);
    wheel(r, 1);
    r.orbit.dolly(1);

    T.eq(calls, 3);
  });

  test('orbit: animateTo reaches the target view and takes the short way round', function () {
    var r = rig({ theta: 0.1, phi: 1, radius: 100 });
    r.orbit.animateTo({ theta: 2 * Math.PI - 0.1, phi: 0.5, radius: 40, tx: 5, ty: 6, tz: 7 }, 1);
    return new Promise(function (resolve) { setTimeout(resolve, 20); }).then(function () {
      T.eq(r.orbit.tick(), false, 'finished after its duration');
      T.near(r.orbit.theta, -0.1, 1e-9, '0.2 rad backwards, not 6.08 forwards');
      T.near(r.orbit.phi, 0.5, 1e-12);
      T.near(r.orbit.radius, 40, 1e-12);
      T.eq([r.orbit.target.x, r.orbit.target.y, r.orbit.target.z], [5, 6, 7]);
      T.eq(r.orbit.tick(), false, 'and stays finished');
    });
  });

  test('orbit: a drag cancels a running animation', function () {
    var r = rig({ theta: 0, radius: 100 });
    r.orbit.animateTo({ radius: 10 }, 100000);
    drag(r, 10, 0);

    T.eq(r.orbit.tick(), false);
    T.eq(r.orbit.radius, 100);
  });

  test('orbit: dispose stops listening', function () {
    var r = rig({ radius: 100, theta: 0 });
    r.orbit.dispose();
    drag(r, 40, 0);
    wheel(r, 1);

    T.eq(r.orbit.theta, 0);
    T.eq(r.orbit.radius, 100);
  });

})();
