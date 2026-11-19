/* test-dialog-fit.js — windows with help text open wide enough to read it.

   A settings window with a help column asked for 520 to 600 px, which left the help a
   few words wide. App.DialogFit widens it, keeps it centred, makes it taller when its
   rows still do not fit, and leaves a window without help text alone. */

(function () {
  var F = App.DialogFit;

  /* A window from App.Dialogs.open, with a settings form of the given help texts. */
  function withWindow(opts, run) {
    var host = document.createElement('div'); host.id = 'modal-layer'; document.body.appendChild(host);
    var handle = null;
    try {
      handle = App.Dialogs.open({
        title: 'Test', width: opts.width, height: opts.height, buttons: [{ label: 'Close' }],
        build: function (body) {
          body.classList.add('mesh-settings-body');
          var form = App.UI.el('div.mesh-settings-form');
          (opts.helps || []).forEach(function (help) {
            form.appendChild(App.UI.el('label.mesh-setting-label', { text: 'Field' }));
            form.appendChild(App.UI.el('input.mesh-setting-control', { type: 'text' }));
            form.appendChild(App.UI.el('div.mesh-setting-help', { text: help }));
          });
          if (opts.tall) form.appendChild(App.UI.el('div', { style: 'height:' + opts.tall + 'px' }));
          body.appendChild(form);
        }
      });
      return run(handle.dialog);
    } finally {
      if (handle) handle.close();
      host.remove();
    }
  }

  function px(value) { return parseFloat(value); }

  function wide() { return Math.min(F.WIDTH, window.innerWidth - 40); }

  T.test('a window with help text opens wide enough to read it, centred', function () {
    withWindow({ width: 600, height: 300, helps: ['Shown in the Model explorer and the deck.'] },
      function (dialog) {
        T.eq(px(dialog.style.width), wide());
        T.eq(px(dialog.style.left), Math.max(0, Math.round((window.innerWidth - wide()) / 2)));
      });
  });

  T.test('a window without help text keeps the width it asked for', function () {
    withWindow({ width: 500, height: 300, helps: ['', '  '] }, function (dialog) {
      T.eq(px(dialog.style.width), Math.min(500, window.innerWidth - 40));
    });
  });

  T.test('a window wider than that already is not made narrower', function () {
    var asked = Math.min(F.WIDTH + 100, window.innerWidth - 40);
    withWindow({ width: F.WIDTH + 100, height: 300, helps: ['Help.'] }, function (dialog) {
      T.eq(px(dialog.style.width), asked);
    });
  });

  T.test('a window whose rows do not fit grows taller, up to the browser window', function () {
    withWindow({ width: 600, height: 200, helps: ['Help.'], tall: 5000 }, function (dialog) {
      T.ok(px(dialog.style.height) > 200, 'taller than it asked for');
      T.ok(px(dialog.style.height) <= window.innerHeight - 60, 'inside the browser window');
    });
  });

  T.test('fit leaves anything that is not a window alone, and install wraps open once', function () {
    T.eq(F.fit(null), false);
    var open = App.Dialogs.open;
    F.install();
    T.ok(App.Dialogs.open === open, 'a second install does not wrap open again');
    T.ok(open.fitted, 'App.Dialogs.open is the fitted one');
  });
})();
