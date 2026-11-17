/* ══════════════════════════════════════════════════════════════════
   name-dialog.js — a small window that asks for a few values: a name, or a number.

   Rename… and "Value at a node…" used the browser's own prompt. That box looks
   like no other window of the app, a screenshot cannot show it, and a test has to
   answer it from outside the page. This is the same question in an app window:
   one field or a few, OK and Cancel, Enter for OK and Escape for Cancel.

   `ask` asks for one value and answers the trimmed text, or null when the window
   is closed without one. `form` asks for several (File > Project properties…) and
   answers an object of trimmed texts by field name, or null.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.NameDialog = (function () {

  /* options: title (the window title), value (the text now), label (default
     "Name"), help (one line under the field), text (a paragraph above it),
     empty (the note for an empty field, default "Type a name."), check (a function
     of the trimmed text that answers a note when the text is refused, or null). */
  function ask(options) {
    var opts = options || {};
    return form({
      title: opts.title || 'Rename', text: opts.text,
      fields: [{ name: 'name', label: opts.label || 'Name', value: opts.value,
                 help: opts.help, empty: opts.empty || 'Type a name.', check: opts.check }]
    }).then(function (values) { return values === null ? null : values.name; });
  }

  /* options: title, text (a paragraph above the fields), fields: a list of
     { name (the input's name and the answer's key), label, value, help, unit (shown
     after the field), empty (the note for an empty field), check (as for `ask`) }. */
  function form(options) {
    var opts = options || {};
    var fields = opts.fields || [];
    var el = App.UI.el;
    return new Promise(function (resolve) {
      var answered = false, inputs = [], message = null, shell = null;

      function answer(value) {
        if (answered) return;
        answered = true;
        resolve(value);
      }
      function submit() {
        var values = {};
        for (var i = 0; i < fields.length; i += 1) {
          var field = fields[i], input = inputs[i];
          var text = String(input.value || '').trim();
          var note = !text ? (field.empty || 'Type a value.')
            : (field.check ? field.check(text) : null);
          if (note) {
            message.textContent = note;
            input.focus();
            return;
          }
          values[field.name] = text;
        }
        answer(values);
        shell.close();
      }

      shell = App.Dialogs.open({
        title: opts.title || 'Rename',
        width: 440, height: 135 + 55 * fields.length + (opts.text ? 60 : 0),
        buttons: [
          { label: 'OK', primary: true, keepOpen: true, onClick: submit },
          { label: 'Cancel' }
        ],
        onClose: function () { answer(null); },
        build: function (body) {
          body.classList.add('name-dialog-body');
          if (opts.text) body.appendChild(el('p.name-dialog-text', { text: opts.text }));
          var grid = el('div.name-dialog-form');
          body.appendChild(grid);
          fields.forEach(function (field) {
            var value = field.value === null || field.value === undefined ? ''
                                                                           : String(field.value);
            var input = el('input.mesh-setting-control.name-dialog-input', {
              type: 'text', name: field.name, value: value
            });
            input.value = value;
            input.addEventListener('keydown', function (event) {
              if (event.key === 'Enter') { event.preventDefault(); submit(); }
            });
            inputs.push(input);
            grid.appendChild(el('label.mesh-setting-label', { text: field.label || 'Name' }));
            grid.appendChild(field.unit
              ? el('span.name-dialog-with-unit', null, [input, el('span.unit', { text: field.unit })])
              : input);
            if (field.help) {
              grid.appendChild(el('span'));
              grid.appendChild(el('div.mesh-setting-help', { text: field.help }));
            }
          });
          message = el('div.mesh-settings-message');
          grid.appendChild(el('span'));
          grid.appendChild(message);
        }
      });
      shell.dialog.classList.add('name-dialog-window');
      if (inputs.length) {
        inputs[0].focus();
        inputs[0].select();
      }
    });
  }

  return { ask: ask, form: form };
})();
