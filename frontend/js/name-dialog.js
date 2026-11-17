/* ══════════════════════════════════════════════════════════════════
   name-dialog.js — a small window that asks for one value: a name, or a number.

   Rename… and "Value at a node…" used the browser's own prompt. That box looks
   like no other window of the app, a screenshot cannot show it, and a test has to
   answer it from outside the page. This is the same question in an app window: one
   field, OK and Cancel, Enter for OK and Escape for Cancel.

   `ask` answers the trimmed text, or null when the window is closed without one.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.NameDialog = (function () {

  /* options: title (the window title), value (the text now), label (default
     "Name"), help (one line under the field), text (a paragraph above it),
     empty (the note for an empty field, default "Type a name."), check (a function
     of the trimmed text that answers a note when the text is refused, or null). */
  function ask(options) {
    var opts = options || {};
    var el = App.UI.el;
    return new Promise(function (resolve) {
      var answered = false, input = null, message = null, shell = null;

      function answer(value) {
        if (answered) return;
        answered = true;
        resolve(value);
      }
      function submit() {
        var name = String(input.value || '').trim();
        var note = !name ? (opts.empty || 'Type a name.')
          : (opts.check ? opts.check(name) : null);
        if (note) {
          message.textContent = note;
          input.focus();
          return;
        }
        answer(name);
        shell.close();
      }

      shell = App.Dialogs.open({
        title: opts.title || 'Rename',
        width: 440, height: opts.text ? 250 : 190,
        buttons: [
          { label: 'OK', primary: true, keepOpen: true, onClick: submit },
          { label: 'Cancel' }
        ],
        onClose: function () { answer(null); },
        build: function (body) {
          body.classList.add('name-dialog-body');
          if (opts.text) body.appendChild(el('p.name-dialog-text', { text: opts.text }));
          var form = el('div.name-dialog-form');
          body.appendChild(form);
          input = el('input.mesh-setting-control.name-dialog-input', {
            type: 'text', name: 'name', value: opts.value || ''
          });
          input.value = opts.value || '';
          input.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') { event.preventDefault(); submit(); }
          });
          message = el('div.mesh-settings-message');
          form.appendChild(el('label.mesh-setting-label', { text: opts.label || 'Name' }));
          form.appendChild(input);
          form.appendChild(el('span'));
          form.appendChild(el('div.mesh-setting-help', { text: opts.help || '' }));
          form.appendChild(el('span'));
          form.appendChild(message);
        }
      });
      shell.dialog.classList.add('name-dialog-window');
      if (input) {
        input.focus();
        input.select();
      }
    });
  }

  return { ask: ask };
})();
