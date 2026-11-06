/* ══════════════════════════════════════════════════════════════════
   picture-dialog.js — the Save picture window.

   A form that writes a `picture save ...` line and runs it, so the window, the command
   box and `kratos-cli picture` have one set of words and one code path. `commandFor` has
   no DOM and is tested as such; the window around it is in the browser suite.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.PictureDialog = (function () {

  /* Which walk each choice of the window means. Offered only where it means something. */
  var SCOPES = {
    view: { label: 'This view' },
    stages: { label: 'Every stage', stage: 'all' },
    fields: { label: 'This stage, every field', field: 'all' },
    both: { label: 'Every stage, every field', stage: 'all', field: 'all' }
  };

  /* The choices kept between two openings of the window. */
  var last = { formats: ['png'], width: App.PictureDraw.DEFAULT_WIDTH_CM, scope: 'view',
               csv: false };

  function scopesFor(results, staged) {
    if (results) return ['view', 'stages', 'fields', 'both'];
    if (staged) return ['view', 'stages'];
    return ['view'];
  }

  /* What the screen does unless told otherwise goes unsaid, so the line stays short. */
  function commandFor(choice, screen) {
    var words = ['picture', 'save'].concat(choice.formats);
    var size = App.PictureDraw;
    if (choice.width !== size.DEFAULT_WIDTH_CM) words.push('--width', String(choice.width));
    var scope = SCOPES[choice.scope] || SCOPES.view;
    if (scope.stage) words.push('--stage', 'all');
    if (scope.field) words.push('--field', 'all');
    if (!choice.legend && screen.legend) words.push('--no-legend');
    if (!choice.rulers && screen.rulers) words.push('--no-rulers');
    if (!choice.axes) words.push('--no-axes');
    if (choice.grid) words.push('--grid');
    if (choice.csv) words.push('--csv');
    return words.join(' ');
  }

  /* What the window tells the user will happen next. The number of fields is the open
     stage's, and is only an estimate for "every stage". */
  function hint(choice, counts) {
    var scope = SCOPES[choice.scope] || SCOPES.view;
    var pictures = (scope.stage ? counts.stages : 1) * (scope.field ? counts.fields : 1);
    var files = pictures * choice.formats.length + (choice.csv ? pictures : 0);
    if (!choice.formats.length && !choice.csv) return 'Choose a format.';
    var many = files > 1 || scope.stage || scope.field;
    var number = (scope.stage && scope.field ? 'About ' : '') + files + ' file' + (files === 1 ? '' : 's');
    return many ? number + '. You choose a folder next.'
                : number + '. You choose its name and place next.';
  }

  /* Only the width: the height follows the model in all its stages, and in Results those
     have to come from the server. */
  function sizeLine(choice) {
    return App.PictureDraw.page(choice.width, 1, 1).widthPx + ' px wide at ' + App.PictureDraw.DPI
         + ' dpi';
  }

  function open() {
    var view = App.Viewport.pictureView && App.Viewport.pictureView();
    if (!view) {
      App.Command.err('There is no picture to save: the viewport has nothing to draw.');
      return null;
    }
    if (document.getElementById('picture-form')) return null;

    var el = App.UI.el;
    var results = App.Picture.inResults(), staged = App.Picture.inStaged();
    var scopes = scopesFor(results, staged);
    var screen = { legend: results, rulers: !!view.rulers };
    var counts = {
      stages: results ? App.Picture.resultStages().length
            : ((App.PROJECT && App.PROJECT.stages) || []).length || 1,
      fields: results ? App.Results.fieldNames().length : 1
    };
    var form = el('div.picture-form', { id: 'picture-form' });
    var dpiNote = el('div.mesh-setting-help');
    var note = el('div.picture-note');
    var choice = {
      formats: last.formats.slice(), width: last.width,
      scope: scopes.indexOf(last.scope) >= 0 ? last.scope : 'view',
      csv: results && last.csv, legend: true,
      rulers: !!(App.Picture.defaults().rulers && view.rulers), axes: true, grid: false
    };

    function refresh() {
      dpiNote.textContent = choice.width > 0 && choice.width <= App.PictureDraw.MAX_WIDTH_CM
        ? sizeLine(choice)
        : 'The width is in cm, more than 0 and at most ' + App.PictureDraw.MAX_WIDTH_CM + '.';
      note.textContent = hint(choice, counts);
    }

    function row(label, control) {
      form.appendChild(el('label.mesh-setting-label', { text: label }));
      form.appendChild(control);
    }

    function tick(text, checked, onChange, extra) {
      var box = el('input', { type: 'checkbox' });
      box.checked = checked;
      if (extra && extra.disabled) box.disabled = true;
      if (extra && extra.name) box.name = extra.name;
      box.addEventListener('change', function () { onChange(box.checked); refresh(); });
      var holder = el('label.picture-tick', { title: (extra && extra.title) || '' });
      holder.appendChild(box);
      holder.appendChild(document.createTextNode(' ' + text));
      return holder;
    }

    var formats = el('div.picture-row');
    App.PictureDraw.FORMATS.forEach(function (format) {
      formats.appendChild(tick(format.toUpperCase(), choice.formats.indexOf(format) >= 0, function (on) {
        choice.formats = App.PictureDraw.FORMATS.filter(function (name) {
          return name === format ? on : choice.formats.indexOf(name) >= 0;
        });
      }, { name: 'picture-format-' + format }));
    });
    row('Format', formats);

    var width = el('input.mesh-setting-control', { type: 'number', name: 'picture-width', step: '0.5',
                                                   min: '1', max: String(App.PictureDraw.MAX_WIDTH_CM) });
    width.value = choice.width;
    width.addEventListener('input', function () { choice.width = Number(width.value); refresh(); });
    var widthRow = el('div.picture-row');
    widthRow.appendChild(width);
    widthRow.appendChild(document.createTextNode(' cm'));
    widthRow.appendChild(dpiNote);
    row('Width', widthRow);

    if (scopes.length > 1) {
      var list = el('div.picture-column');
      scopes.forEach(function (scope) {
        var radio = el('input', { type: 'radio', name: 'picture-scope', value: scope });
        radio.checked = choice.scope === scope;
        radio.addEventListener('change', function () { choice.scope = scope; refresh(); });
        var holder = el('label.picture-tick');
        holder.appendChild(radio);
        holder.appendChild(document.createTextNode(' ' + SCOPES[scope].label));
        list.appendChild(holder);
      });
      row('Pictures', list);
    }

    var showing = el('div.picture-row');
    if (screen.legend) {
      showing.appendChild(tick('Legend', true, function (on) { choice.legend = on; },
                               { name: 'picture-legend' }));
    }
    if (screen.rulers) {
      showing.appendChild(tick('Rulers', choice.rulers, function (on) { choice.rulers = on; },
                               { name: 'picture-rulers' }));
    }
    showing.appendChild(tick('Axes', true, function (on) { choice.axes = on; },
                             { name: 'picture-axes' }));
    showing.appendChild(tick('Grid', false, function (on) { choice.grid = on; }, {
      name: 'picture-grid', disabled: !view.gridOn,
      title: view.gridOn ? '' : 'The grid is off on screen. Show grid turns it on.'
    }));
    row('Show', showing);

    if (results) {
      row('Also save', tick('The field values as CSV', choice.csv, function (on) { choice.csv = on; },
                            { name: 'picture-csv' }));
    }
    refresh();

    function valid() {
      if (!(choice.width > 0 && choice.width <= App.PictureDraw.MAX_WIDTH_CM)) return false;
      return choice.formats.length > 0 || choice.csv;
    }

    var handle = App.Dialogs.open({
      title: 'Save picture',
      width: 500, height: 370,
      buttons: [
        { label: 'Copy picture', keepOpen: true, onClick: function () {
          App.Picture.copy({ width: valid() ? choice.width : undefined, show: {
            legend: choice.legend, rulers: choice.rulers, axes: choice.axes, grid: choice.grid
          } });
        } },
        { label: 'Save…', primary: true, keepOpen: true, onClick: function () {
          if (!valid()) { refresh(); return; }
          last = { formats: choice.formats.slice(), width: choice.width, scope: choice.scope,
                   csv: choice.csv };
          handle.close();
          // Straight out of the click, so the browser still offers its save window.
          App.Command.run(commandFor(choice, screen));
        } },
        { label: 'Cancel' }
      ],
      build: function (body) {
        var wrap = el('div.picture-body');
        wrap.appendChild(form);
        wrap.appendChild(note);
        body.appendChild(wrap);
      }
    });
    return handle;
  }

  return { open: open, commandFor: commandFor, hint: hint, scopesFor: scopesFor };
})();
