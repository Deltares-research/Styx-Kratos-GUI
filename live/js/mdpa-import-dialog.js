/* Import a Kratos .mdpa deck's mesh: nodes, typed elements/conditions, and named
   sub-model-part groupings, read back by `POST /api/import/mdpa` (app/mdpa_import.py).

   This recovers the mesh a deck contains, not the parametric project that produced it
   -- that information is discarded on export, so nothing here ever becomes a real,
   editable project part. What it does become, after a successful import: a drawn
   preview in the viewport (App.Viewport.showImportedMesh) plus a small floating
   checklist -- one row per body sub-model part the deck itself named, so each part can
   be shown/hidden and framed on its own -- and, once "Accept" is clicked, a permanent
   (for this session) "Imported mesh" node in the Model explorer for whichever rows
   were left checked (app/live/js/model.js's setImportedParts). Unchecked rows are
   dropped outright, not merely hidden. This is a session-only bookmark, not a save:
   it lives in the browser alone, is never written into the project JSON, and a New or
   Open project clears it exactly like the preview it came from. */

var App = window.App || {};

App.MdpaImportDialog = (function () {
  /* A child of #modal-layer with no `.scrim` sibling: layout.css gives that layer
     `pointer-events: none` and only opts direct children back in, so this floats over
     the viewport without blocking clicks/drags to the 3D view around it -- unlike the
     import dialog itself, this is meant to be used *while* looking at the model. */
  function openChecklist(model, filename) {
    var layer = document.getElementById('modal-layer');
    if (!layer) return;
    closeChecklist();

    var el = App.UI.el;
    // Not `.dialog`: that class sets `min-width: 420px` for a real dialog's toolbar
    // and canvas, which would force this narrow checklist wide open. Built from
    // scratch instead, keeping only `.dlg-head`/`.dlg-title`/`.dlg-x` for the header,
    // which style just the head bar, not the panel's own size.
    var panel = el('div', { id: 'mdpa-checklist' });
    panel.style.position = 'fixed';
    panel.style.left = '12px';
    panel.style.top = '96px';
    panel.style.width = '260px';
    panel.style.maxHeight = '70vh';
    panel.style.display = 'flex';
    panel.style.flexDirection = 'column';
    panel.style.background = 'var(--c-panel, #fff)';
    panel.style.border = '1px solid #7d879a';
    panel.style.boxShadow = '0 4px 16px rgba(0,0,0,.25)';
    panel.style.fontSize = '13px';

    var closeButton = el('button.dlg-x', { text: '✕', type: 'button' });
    var head = el('div.dlg-head', null,
      [el('span.dlg-title', { text: filename }), closeButton]);
    panel.appendChild(head);
    App.Dialogs.draggable(head, panel);

    // Not `.dlg-body` either: it is `display: flex` with no direction set (a row,
    // meant for one big child like a canvas) and `overflow: hidden` -- exactly what
    // laid every checklist row out sideways in a strip that ran off-screen and clipped.
    var list = el('div');
    list.style.overflowY = 'auto';
    list.style.padding = '8px 10px';
    list.style.display = 'flex';
    list.style.flexDirection = 'column';

    var entries = [];    // {section, checkbox}, for Accept to read back the checked rows
    (model.sections || []).forEach(function (section) {
      var row = checklistRow(section);
      entries.push({ section: section, checkbox: row.checkbox });
      list.appendChild(row.el);
    });
    if (!(model.sections || []).length) {
      list.appendChild(el('div', { text: 'Nothing in this deck could be drawn.' }));
    }
    panel.appendChild(list);

    if (entries.length) panel.appendChild(footer(entries));

    layer.appendChild(panel);

    closeButton.addEventListener('click', function () {
      closeChecklist();
      if (App.Viewport && App.Viewport.clearImportedMesh) App.Viewport.clearImportedMesh();
    });
  }

  /* Accept: the checked rows become the Model explorer's "Imported mesh" node
     (App.Model.setImportedParts); the unchecked ones are dropped from the viewport
     outright, not merely left hidden -- "unchecked" means "not wanted", not "wanted
     later". Then the checklist itself closes, but -- unlike the ✕ button -- without
     clearing the preview, since what is left of it is now the accepted set. */
  function footer(entries) {
    var el = App.UI.el;
    var bar = el('div.dlg-foot');
    var accept = el('button.btn.btn-primary', { text: 'Accept', type: 'button' });
    accept.addEventListener('click', function () {
      var parts = [];
      entries.forEach(function (entry) {
        if (entry.checkbox.checked) {
          parts.push({ key: entry.section.key,
                      label: entry.section.part || (entry.section.kind + ' (ungrouped)'),
                      color: entry.section.color });
        } else if (App.Viewport && App.Viewport.removeImportedSection) {
          App.Viewport.removeImportedSection(entry.section.key);
        }
      });
      closeChecklist();
      if (App.Model && App.Model.setImportedParts) App.Model.setImportedParts(parts);
      if (App.Command) {
        App.Command.ok(parts.length
          ? 'Added ' + parts.length + ' part' + (parts.length === 1 ? '' : 's')
            + ' to the Model explorer, under "Imported mesh".'
          : 'No parts were checked -- nothing added to the Model explorer.');
      }
    });
    bar.appendChild(accept);
    return bar;
  }

  function checklistRow(section) {
    var el = App.UI.el;
    var row = el('label');
    row.style.display = 'flex';
    row.style.alignItems = 'center';
    row.style.gap = '6px';
    row.style.padding = '3px 0';
    row.style.cursor = 'pointer';

    var checkbox = el('input', { type: 'checkbox' });
    checkbox.checked = true;
    checkbox.addEventListener('change', function () {
      if (App.Viewport && App.Viewport.setVisible) {
        App.Viewport.setVisible(section.key, checkbox.checked);
      }
    });

    var swatch = el('span');
    swatch.style.width = '10px';
    swatch.style.height = '10px';
    swatch.style.flex = '0 0 auto';
    swatch.style.borderRadius = '2px';
    swatch.style.background = section.color;

    var label = el('span', { text: section.part || (section.kind + ' (ungrouped)') });
    label.style.flex = '1';
    label.style.overflow = 'hidden';
    label.style.textOverflow = 'ellipsis';
    label.style.whiteSpace = 'nowrap';
    label.title = section.part || section.kind;

    var frame = el('button', { text: '⌖', type: 'button' });
    frame.title = 'Frame this part';
    frame.addEventListener('click', function (event) {
      event.preventDefault();      // do not toggle the row's own checkbox
      if (App.Viewport && App.Viewport.frameImportedSection) {
        App.Viewport.frameImportedSection(section.key);
      }
    });

    row.appendChild(checkbox);
    row.appendChild(swatch);
    row.appendChild(label);
    row.appendChild(frame);
    return { el: row, checkbox: checkbox };
  }

  function closeChecklist() {
    var panel = document.getElementById('mdpa-checklist');
    if (panel && panel.parentNode) panel.parentNode.removeChild(panel);
  }

  function open() {
    var layer = document.getElementById('modal-layer');
    if (!layer || document.getElementById('mdpa-import-dialog')) return;

    var el = App.UI.el;
    var scrim = el('div.scrim');
    var dialog = el('div.dialog.import-dialog', { id: 'mdpa-import-dialog' });

    dialog.style.width = '500px';
    dialog.style.height = '360px';
    dialog.style.left = Math.max(20, (window.innerWidth - 500) / 2) + 'px';
    dialog.style.top = Math.max(20, (window.innerHeight - 360) / 2) + 'px';

    var closeButton = el('button.dlg-x', { text: '✕', type: 'button' });
    var head = el('div.dlg-head', null,
      [el('span.dlg-title', { text: 'Import mesh (.mdpa)' }), closeButton]);
    dialog.appendChild(head);
    App.Dialogs.draggable(head, dialog);

    var body = el('div.dlg-body');
    body.style.display = 'flex';
    body.style.flexDirection = 'column';
    body.style.padding = '20px';

    var dropZone = el('div.drop-zone',
      { text: 'Drag and drop a .mdpa file here, or click to browse.' });
    dropZone.style.flex = '1';
    dropZone.style.border = '2px dashed #999';
    dropZone.style.borderRadius = '8px';
    dropZone.style.display = 'flex';
    dropZone.style.alignItems = 'center';
    dropZone.style.justifyContent = 'center';
    dropZone.style.textAlign = 'center';
    dropZone.style.cursor = 'pointer';
    dropZone.style.padding = '20px';
    dropZone.style.marginBottom = '20px';
    dropZone.style.color = '#666';

    var fileInput = el('input', { type: 'file', accept: '.mdpa' });
    fileInput.style.display = 'none';

    body.appendChild(dropZone);
    body.appendChild(fileInput);

    var message = el('div', { text: '' });
    message.style.color = 'red';
    body.appendChild(message);

    dialog.appendChild(body);
    layer.appendChild(scrim);
    layer.appendChild(dialog);

    function close() {
      if (scrim.parentNode) scrim.remove();
      if (dialog.parentNode) dialog.remove();
      document.removeEventListener('keydown', escape);
    }

    function escape(event) { if (event.key === 'Escape') close(); }

    function summarize(model, filename) {
      var byKind = {};
      (model.elements || []).concat(model.conditions || []).forEach(function (entity) {
        byKind[entity.kind] = (byKind[entity.kind] || 0) + entity.count;
      });
      var kinds = Object.keys(byKind).map(function (kind) {
        return byKind[kind] + ' ' + kind;
      }).join(', ') || 'no elements';
      var bodies = (model.parts || []).filter(function (p) { return p.kind === 'body'; }).length;

      return filename + ': ' + model.dimension + 'D mesh, ' + model.nodes + ' nodes, '
        + kinds + ', ' + (model.parts || []).length + ' sub-model parts ('
        + bodies + ' bodies).';
    }

    function handleFile(file) {
      if (!file) return;
      message.textContent = 'Uploading and parsing...';
      message.style.color = '#333';

      var formData = new FormData();
      formData.append('file', file);

      fetch(App.Api.base + '/api/import/mdpa', { method: 'POST', body: formData })
        .then(function (res) {
          if (!res.ok) {
            return res.json().then(function (err) {
              throw new Error(err.detail || 'Import failed');
            });
          }
          return res.json();
        })
        .then(function (model) {
          close();
          if (App.Viewport && App.Viewport.showImportedMesh) {
            App.Viewport.showImportedMesh(model);
          }
          openChecklist(model, file.name);
          if (App.Command) {
            App.Command.ok(summarize(model, file.name));
            App.Command.note('Shown as a read-only preview in the viewport -- not '
              + 'added to the project. Only the mesh is recoverable from a .mdpa '
              + 'deck, not the parametric project that produced it.');
            // A plane-strain deck is stood up on the open project's section plane, so
            // it is edge-on until the view is looking along that plane's normal.
            if (model.dimension === 2 && App.Viewport && App.Viewport.is2D
                && !App.Viewport.is2D()) {
              App.Command.note('This is a plane-strain section, placed on the '
                + "project's own section plane. Switch to 2D to see it face-on.");
            }
          }
        })
        .catch(function (err) {
          message.textContent = err.message;
          message.style.color = 'red';
        });
    }

    dropZone.addEventListener('click', function () { fileInput.click(); });
    fileInput.addEventListener('change', function (e) { handleFile(e.target.files[0]); });

    dropZone.addEventListener('dragover', function (e) {
      e.preventDefault();
      dropZone.style.backgroundColor = '#eee';
    });
    dropZone.addEventListener('dragleave', function (e) {
      e.preventDefault();
      dropZone.style.backgroundColor = '';
    });
    dropZone.addEventListener('drop', function (e) {
      e.preventDefault();
      dropZone.style.backgroundColor = '';
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleFile(e.dataTransfer.files[0]);
      }
    });

    closeButton.addEventListener('click', close);
    scrim.addEventListener('click', close);
    document.addEventListener('keydown', escape);
  }

  return { open: open, openChecklist: openChecklist, closeChecklist: closeChecklist };
})();
