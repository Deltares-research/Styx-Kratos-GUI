/* The Line window's browser half: the ways into the window and what its buttons do, built
   against the real App.UI. What a new line starts as, and saving a soil body, are
   test-lines.js, which runs headless as well (frontend/tests/run_headless.py). */

(function () {
  var STUBBED = ['PROJECT', 'Dialogs', 'DrawInput', 'Api', 'Model', 'Viewport', 'Command',
                 'Explorer', 'selectObject'];

  function project(dimension) {
    return {
      dimension: dimension,
      domain: { x0: 0, x1: 20, z0: 0, z1: 10, y_top: 0, y_bottom: -10 },
      lines: [{ id: 'floor', name: 'Floor', points: [[0, -2], [5, -2]] }]
    };
  }

  /* `server` answers the PATCH. Returns what each stub was given, and `restore`. */
  function rig(dimension, server) {
    var saved = {};
    STUBBED.forEach(function (name) { saved[name] = App[name]; });
    var ctx = { opened: [], drawing: null, closed: 0, patches: [], selected: [], notes: [],
                errors: [], loads: 0 };
    App.PROJECT = project(dimension);
    App.Dialogs = { open: function (config) {
      var body = document.createElement('div');
      config.build(body);
      ctx.opened.push({ config: config, body: body });
      return { close: function () { ctx.closed += 1; } };
    } };
    App.DrawInput = { start: function (mode, options) {
      ctx.drawing = { mode: mode, options: options };
    } };
    App.Api = { patch: function (path, fields) {
      ctx.patches.push({ path: path, fields: fields });
      return server ? server() : Promise.resolve({ project: App.PROJECT });
    } };
    App.Model = { apply: function () {},
                  load: function () { ctx.loads += 1; return Promise.resolve(); } };
    App.Viewport = { refresh: function () { return Promise.resolve(); } };
    App.Command = { note: function (text) { ctx.notes.push(text); }, ok: function () {},
                    err: function (text) { ctx.errors.push(text); } };
    App.Explorer = { mountTree: function () {}, mountSelection: function () {} };
    App.selectObject = function (id) { ctx.selected.push(id); };
    ctx.restore = function () {
      STUBBED.forEach(function (name) { App[name] = saved[name]; });
    };
    return ctx;
  }

  function button(opened, label) {
    return opened.config.buttons.filter(function (each) {
      return each.label.indexOf(label) === 0;
    })[0];
  }

  function points(opened) {
    return Array.prototype.map.call(opened.body.querySelectorAll('.line-point'), function (row) {
      return Array.prototype.map.call(row.querySelectorAll('input'), function (input) {
        return input.value;
      });
    });
  }

  function typeX(opened, row, value) {
    opened.body.querySelectorAll('.line-point')[row].querySelector('input').value = value;
  }

  function finished(ctx, promise) {
    return promise.then(function () { ctx.restore(); },
                        function (error) { ctx.restore(); throw error; });
  }

  ['start', 'typed'].forEach(function (entry) {
    T.test(entry + ': in the solid model it says why and opens nothing', function () {
      var ctx = rig(3);
      try {
        T.eq(App.Lines[entry](), undefined);
        T.eq(ctx.opened.length, 0);
        T.eq(ctx.drawing, null);
        T.eq(ctx.notes, ['A line is drawn in the 2D section; switch to 2D to create one.']);
      } finally { ctx.restore(); }
    });
  });

  T.test('start: the points drawn open the window, in the plane of the section', function () {
    var ctx = rig(2);
    try {
      App.Lines.start();
      T.eq(ctx.drawing.mode, 'line');
      ctx.drawing.options.onComplete([[5, 0, 0], [5, -4, 0]]);
      T.ok(/Create line/.test(ctx.opened[0].config.title));
      T.eq(points(ctx.opened[0]), [['5', '0'], ['5', '-4']]);
      T.eq(ctx.opened[0].body.querySelector('input[type="text"]').value, 'Line 1');
    } finally { ctx.restore(); }
  });

  T.test('typed: the window opens on a line across the section, with no drawing', function () {
    var ctx = rig(2);
    try {
      App.Lines.typed();
      T.eq(ctx.drawing, null);
      T.eq(points(ctx.opened[0]), [['0', '-5'], ['20', '-5']]);
    } finally { ctx.restore(); }
  });

  T.test('edit: a line opens as Edit with its own points, an unknown id does nothing', function () {
    var ctx = rig(2);
    try {
      T.eq(App.Lines.edit('nothing'), undefined);
      T.eq(ctx.opened.length, 0);
      App.Lines.edit('floor');
      T.ok(/Edit line/.test(ctx.opened[0].config.title));
      T.eq(points(ctx.opened[0]), [['0', '-2'], ['5', '-2']]);
    } finally { ctx.restore(); }
  });

  T.test('the window adds a point after the last, and keeps at least two', function () {
    var ctx = rig(2);
    try {
      App.Lines.edit('floor');
      var opened = ctx.opened[0];
      function removes() {
        return opened.body.querySelectorAll('.line-point button');
      }
      T.ok(removes()[0].disabled && removes()[1].disabled, 'two points: nothing to remove');
      Array.prototype.filter.call(opened.body.querySelectorAll('button'), function (each) {
        return each.textContent === 'Add point';
      })[0].click();
      T.eq(points(opened), [['0', '-2'], ['5', '-2'], ['6', '-2']]);
      T.ok(!removes()[0].disabled);
      removes()[1].click();
      T.eq(points(opened), [['0', '-2'], ['6', '-2']]);
    } finally { ctx.restore(); }
  });

  T.test("the window's Pick on model draws the same line again", function () {
    var ctx = rig(2);
    try {
      App.Lines.edit('floor');
      button(ctx.opened[0], 'Pick on model').onClick();
      ctx.drawing.options.onComplete([[1, -3, 0], [5, -3, 0]]);
      T.ok(/Edit line/.test(ctx.opened[1].config.title), 'still the line it was');
      T.eq(points(ctx.opened[1]), [['1', '-3'], ['5', '-3']]);
    } finally { ctx.restore(); }
  });

  T.test('Save sends every line, with what was typed, closes and selects the line', function () {
    var ctx = rig(2);
    App.Lines.edit('floor');
    typeX(ctx.opened[0], 1, '7');
    return finished(ctx, button(ctx.opened[0], 'Save').onClick().then(function () {
      T.eq(ctx.patches, [{ path: '/api/project/lines', fields: { lines: [
        { id: 'floor', name: 'Floor', points: [[0, -2], [7, -2]] }] } }]);
      T.eq(ctx.closed, 1);
      T.eq(ctx.selected, ['floor']);
    }));
  });

  T.test('Save adds a new line after the others', function () {
    var ctx = rig(2);
    App.Lines.typed();
    return finished(ctx, button(ctx.opened[0], 'Save').onClick().then(function () {
      T.eq(ctx.patches[0].fields.lines.map(function (line) { return line.id; }),
           ['floor', 'line_1']);
    }));
  });

  T.test('Save with a repeated point says why in the window and sends nothing', function () {
    var ctx = rig(2);
    try {
      App.Lines.edit('floor');
      typeX(ctx.opened[0], 1, '0');
      T.eq(button(ctx.opened[0], 'Save').onClick(), null);
      T.eq(ctx.opened[0].body.querySelector('.mesh-settings-message').textContent,
           'A line cannot repeat the same point twice.');
      T.eq(ctx.patches, []);
      T.eq(ctx.closed, 0);
    } finally { ctx.restore(); }
  });

  T.test('a refused Save stays open, says why and reads the project back', function () {
    var reason = "stage 'dig' names no such part: soil_top__part1";
    var ctx = rig(2, function () { return Promise.reject(new Error(reason)); });
    App.Lines.edit('floor');
    return finished(ctx, button(ctx.opened[0], 'Save').onClick().then(function () {
      T.eq(ctx.closed, 0);
      T.eq(ctx.opened[0].body.querySelector('.mesh-settings-message').textContent, reason);
      T.eq(ctx.errors, ['Could not save the line: ' + reason]);
      T.eq(ctx.loads, 1);
      T.eq(ctx.selected, []);
    }));
  });
})();
