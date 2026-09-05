/* ══════════════════════════════════════════════════════════════════
   command.js — the Session / Model history panel and its small
   set of demo commands.
   ══════════════════════════════════════════════════════════════════ */

App.Command = (function () {
  var el = App.UI.el;
  var log, hist, entry;
  var history = [], histIdx = -1;

  function mount() {
    log = document.getElementById('cmd-log');
    hist = document.getElementById('cmd-history');
    entry = document.getElementById('cmd-entry');

    App.CMD_WELCOME.forEach(function (l) { write(l[0], l[1]); });
    App.CMD_HISTORY.forEach(function (l) {
      hist.appendChild(el('div.cmd-line.' + l[0], { text: l[1] }));
    });

    document.querySelectorAll('.cmd-tab').forEach(function (t) {
      t.addEventListener('click', function () {
        document.querySelectorAll('.cmd-tab').forEach(function (x) { x.classList.remove('active'); });
        t.classList.add('active');
        var session = t.dataset.tab === 'session';
        log.hidden = !session;
        hist.hidden = session;
      });
    });

    document.getElementById('cmd-ref').addEventListener('click', function (e) {
      e.preventDefault();
      App.runAction({ action: 'cmdref' });
    });

    entry.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        var text = entry.value.trim();
        if (!text) return;
        history.push(text); histIdx = history.length;
        entry.value = '';
        run(text);
      } else if (e.key === 'ArrowUp') {
        if (histIdx > 0) { histIdx--; entry.value = history[histIdx]; }
        e.preventDefault();
      } else if (e.key === 'ArrowDown') {
        if (histIdx < history.length - 1) { histIdx++; entry.value = history[histIdx]; }
        else { histIdx = history.length; entry.value = ''; }
        e.preventDefault();
      }
    });
  }

  function write(kind, text) {
    if (!log) return;
    log.appendChild(el('div.cmd-line.' + kind, { text: text }));
    log.scrollTop = log.scrollHeight;
  }

  function note(text) { write('note', text); }
  function ok(text)   { write('ok', text); }

  /* ── Demo command interpreter ────────────────────────────────── */
  function run(text) {
    write('echo', '> ' + text);
    var parts = text.split(/\s+/);
    var cmd = parts[0].toLowerCase().replace(/^_/, '');
    var arg = (parts[1] || '').toLowerCase();

    var modeJump = {
      gotosoil: 'soil', gotostructures: 'structures', gotomesh: 'mesh',
      gotoflow: 'flow', gotostaged: 'staged', gotoflowconditions: 'flow'
    };

    if (modeJump[cmd]) {
      App.setMode(modeJump[cmd]);
      ok('Mode: ' + modeJump[cmd]);
      return;
    }

    switch (cmd) {
      case 'clear':
        App.UI.clear(log);
        return;
      case 'view':
        if (['iso', 'top', 'front', 'side'].indexOf(arg) >= 0) {
          App.Viewport.setView(arg); ok(arg + ' view');
        } else write('err', 'Usage: view iso|top|front|side');
        return;
      case 'zoomfit':
        App.Viewport.zoomFit(); ok('Zoomed to fit'); return;
      case 'soillayers':
        App.Dialogs.soilLayers(); ok('OK'); return;
      case 'materials':
        App.Dialogs.materials(); ok('OK'); return;
      case 'mesh':
        App.setMode('mesh');
        App.Viewport.generateMesh(function () {
          ok('Mesh generated: 24118 elements, 38942 nodes');
        });
        return;
      case 'borehole': {
        var bx = parseFloat(parts[1]), by = parseFloat(parts[2]);
        var nb = App.addBorehole(isNaN(bx) ? undefined : bx, isNaN(by) ? undefined : by);
        App.refreshSoilData();
        App.Viewport.rebuildSoil();
        App.Explorer.mountTree(App.state.mode);
        ok(nb.name);
        return;
      }
    }

    var canned = App.CMD_RESPONSES[cmd];
    if (canned) { canned.forEach(function (l) { write(l[0], l[1]); }); return; }

    write('err', 'Unknown command "' + parts[0] + '". Type  help  for the demo command list.');
  }

  return { mount: mount, write: write, note: note, ok: ok, run: run };
})();
