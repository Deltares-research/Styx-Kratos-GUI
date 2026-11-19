/* test-splitters.js — the bars that resize the panels (js/splitters.js).

   A drag starts from the size the panel has on screen, a panel in the right dock grows
   only as far as the Selection explorer can give, and the drag ends with onMove(). */

(function () {
  var S = App.Splitters;
  var PROP = '--test-splitter-size';

  function box(height, id) {
    var node = document.createElement('div');
    if (id) node.id = id;
    node.style.height = height + 'px';
    return node;
  }

  /* A panel, a bar and another panel, in a column of fixed heights. */
  function withColumn(run) {
    var column = document.createElement('div');
    var before = box(200), bar = box(5), after = box(150);
    column.appendChild(before); column.appendChild(bar); column.appendChild(after);
    document.body.appendChild(column);
    try {
      return run(bar);
    } finally {
      column.remove();
      document.documentElement.style.removeProperty(PROP);
    }
  }

  function pointer(type, node, y, button) {
    node.dispatchEvent(new PointerEvent(type, { bubbles: true, clientX: 0, clientY: y,
                                                button: button || 0, pointerId: 1 }));
  }

  /* Presses at y = 100, moves to each y in `path` and lets go. */
  function drag(bar, path) {
    pointer('pointerdown', bar, 100);
    path.forEach(function (y) { pointer('pointermove', window.document, y); });
    pointer('pointerup', window.document, path[path.length - 1]);
  }

  function size() {
    return document.documentElement.style.getPropertyValue(PROP);
  }

  T.test('App.UI.splitter is the smooth one', function () {
    T.ok(App.UI.splitter === S.splitter);
  });

  T.test('the first drag starts from the panel on screen, not from zero', function () {
    withColumn(function (bar) {
      S.splitter(bar, 'y', PROP, 50, 600, false);
      drag(bar, [105, 110]);
      T.eq(size(), '210px', 'the 200 px panel grew by 10 px');
    });
  });

  T.test('a bar that grows the panel after it starts from that panel', function () {
    withColumn(function (bar) {
      S.splitter(bar, 'y', PROP, 50, 600, true);
      drag(bar, [70]);
      T.eq(size(), '180px', 'the 150 px panel grew by 30 px');
    });
  });

  T.test('a drag stays between the smallest and the largest size', function () {
    withColumn(function (bar) {
      S.splitter(bar, 'y', PROP, 50, function () { return 260; }, false);
      drag(bar, [400]);
      T.eq(size(), '260px');
      drag(bar, [-400]);
      T.eq(size(), '50px');
    });
  });

  T.test('onMove has each size, then nothing when the drag ends; a right click does nothing', function () {
    withColumn(function (bar) {
      var calls = [];
      S.splitter(bar, 'y', PROP, 50, 600, false, function (v) { calls.push(v); });
      pointer('pointerdown', bar, 100, 2);
      T.eq(calls.length, 0, 'the right button starts no drag');
      drag(bar, [120]);
      T.eq(calls, [220, undefined]);
      T.ok(!document.body.classList.contains('resizing'), 'the page is left as it was');
    });
  });

  T.test('a bar with no panel beside it starts from the custom property', function () {
    var bar = box(5);
    document.body.appendChild(bar);
    document.documentElement.style.setProperty(PROP, '120px');
    try {
      S.splitter(bar, 'y', PROP, 50, 600, false);
      drag(bar, [110]);
      T.eq(size(), '130px');
    } finally {
      bar.remove();
      document.documentElement.style.removeProperty(PROP);
    }
  });

  /* The right dock beside the Stages explorer, in fixed heights. */
  function withDockColumn(run) {
    var dock = document.createElement('aside');
    dock.id = 'dock';
    dock.className = 'has-phases';
    var model = box(100, 'panel-model'), bar = box(5, 'split-dock1');
    var selection = box(150, 'panel-selection');
    var head = box(23); head.className = 'dock-head'; selection.appendChild(head);
    [model, bar, selection, box(5, 'split-dock2'), box(200, 'panel-phases')].forEach(function (n) {
      dock.appendChild(n);
    });
    document.body.appendChild(dock);
    try {
      return run(bar, selection, dock);
    } finally {
      dock.remove();
      document.documentElement.style.removeProperty(PROP);
    }
  }

  T.test('a dock panel grows only as far as the Selection explorer can give', function () {
    withDockColumn(function (bar) {
      T.eq(S.room(bar), 80, '150 px down to its 70 px beside the Stages explorer');
      S.splitter(bar, 'y', PROP, 80, 2000, false);
      drag(bar, [600]);
      T.eq(size(), '180px');
    });
  });

  T.test('the Stages explorer also grows into the Model explorer, down to its header', function () {
    withDockColumn(function (bar, selection, dock) {
      var head = box(23); head.className = 'dock-head';
      dock.querySelector('#panel-model').appendChild(head);
      var stagesBar = dock.querySelector('#split-dock2');
      T.eq(S.room(stagesBar, dock.querySelector('#panel-phases')), 80 + 77);
      dock.querySelector('#panel-model').classList.add('collapsed');
      T.eq(S.room(stagesBar, dock.querySelector('#panel-phases')), 80, 'a collapsed one gives nothing');
    });
  });

  T.test('without the Stages explorer the Selection explorer gives all but its header', function () {
    withDockColumn(function (bar, selection, dock) {
      dock.className = '';
      T.eq(S.room(bar), 127);
    });
  });

  T.test('a collapsed Selection explorer or a bar outside the dock sets no limit', function () {
    withDockColumn(function (bar, selection) {
      selection.classList.add('collapsed');
      T.eq(S.room(bar), Infinity);
    });
    withColumn(function (bar) { T.eq(S.room(bar), Infinity); });
  });

  T.test('a moved bar is drawn on the next frame', function () {
    withColumn(function (bar) {
      var calls = [];
      S.splitter(bar, 'y', PROP, 50, 600, false, function (v) { calls.push(v); });
      pointer('pointerdown', bar, 100);
      pointer('pointermove', window.document, 130);
      pointer('pointermove', window.document, 140);
      T.eq(calls.length, 0, 'nothing yet: the size waits for the frame');
      pointer('pointerup', window.document, 140);
      T.eq(calls, [240, undefined], 'the last place only, once');
    });
  });
})();
