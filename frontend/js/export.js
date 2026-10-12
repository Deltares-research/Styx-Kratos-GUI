/* ══════════════════════════════════════════════════════════════════
   export.js — File ▸ Export model…, writing a Kratos MultiPhysics deck.

   The server meshes and renders; this asks for it, then hands the browser the deck,
   its materials, and the partial ProjectParameters.json (solver_settings still empty
   until the project carries a solver choice). That is the whole module, and it is the
   app's first download path — nothing here ever fetched a file before, only uploaded
   one.

   Two deliberate differences from generating a mesh in the viewport:

   *   the export covers every meshable body, not the visible ones. Hiding a
       layer to see behind it must not quietly leave it out of the analysis;
       the mesh-settings dialog's body selection, being an explicit choice, is
       still honoured.
   *   it never reuses the mesh on screen. The gmsh worker keeps one model and
       clears it per request, so the only mesh an export can trust is the one
       the export itself made — which is also why it can take a while.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Export = (function () {

  var inFlight = false;
  // The file the user named for this export, if the browser offered to ask.
  var target = null;

  function log(kind, line) {
    if (App.Command && App.Command[kind]) App.Command[kind](line);
  }

  function integer(value) {
    return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  /* The mesh settings the deck is built with: the project's own, plus any local
     refinement and any explicit body selection. `volume_keys` is left off unless
     the user picked bodies, and the server then meshes everything. */
  function meshRequest() {
    var project = App.PROJECT || {};
    var settings = Object.assign({}, project.mesh || {}, {
      /* The same rule the viewport meshes by (`App.Viewport.meshRefinements`), so the
         deck is built from the mesh the user is looking at rather than a flatter one. */
      refinements: App.Viewport.meshRefinements()
    });
    if (Array.isArray(App.MESH_BODY_SELECTION) && App.MESH_BODY_SELECTION.length) {
      settings.volume_keys = App.MESH_BODY_SELECTION.slice();
    }
    return settings;
  }

  /* A file name a person recognises: the project's, reduced to something every
     filesystem accepts. */
  function baseName(project) {
    var name = ((project && project.name) || 'model')
      .replace(/[^A-Za-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    return name || 'model';
  }

  function save(filename, text, mime) {
    return App.Download.write(target, filename, text, mime || 'text/plain');
  }

  /* The deck's files, named as they are inside the archive. One more for a staged
     deck: its K0 stage reads a materials file of its own. */
  function files(result, deckName) {
    var written = [{ name: deckName, text: result.mdpa }];
    if (result.materials) {
      written.push({ name: 'MaterialParameters.json', text: result.materials });
    }
    if (result.initial_materials) {
      written.push({ name: 'initial_materials.json', text: result.initial_materials });
    }
    if (result.project_parameters) {
      written.push({ name: 'ProjectParameters.json', text: result.project_parameters });
    }
    // Which unit system every number above is in. Kratos never reads it; opened again
    // as a deck case, it is what labels the results (core/results/catalog.py).
    if (result.unit_system) {
      written.push({ name: 'kratos_gui_units.json',
                     text: JSON.stringify({ unit_system: result.unit_system }) });
    }
    return written;
  }

  function run(done) {
    if (inFlight) {
      log('note', 'An export is already running.');
      return;
    }
    inFlight = true;

    var archive = baseName(App.PROJECT) + '.zip';
    // Asked for first, before anything is awaited: a browser only offers the save
    // window while the click that opened the menu still counts as a gesture, and the
    // mesh takes far too long for the answer to still be one. One window, so one
    // file -- which is why the deck is zipped rather than written loose.
    return App.Download.pickFile(archive, 'application/zip').then(function (handle) {
      if (handle === App.Download.CANCELLED) {
        inFlight = false;
        log('note', 'Export cancelled.');
        if (done) done();
        return;
      }
      target = handle;
      log('note', 'Meshing and writing the Kratos deck…');

      return App.Api.post('/api/export/mdpa', meshRequest()).then(function (result) {
        // The server's name for the deck, not this module's: ProjectParameters.json
        // already names the .mdpa in `model_import_settings.input_filename`, and a file
        // named anything else is an archive Kratos cannot run once it is unpacked.
        // Both rules agree today; only one of them is in the file.
        var deck = (result.deck_name || baseName(App.PROJECT)) + '.mdpa';
        // Through the module object, so a test can record what would be written
        // instead of making the browser save a file.
        return Promise.resolve(App.Export.save(archive, App.Zip.create(files(result, deck)),
                                               'application/zip')).then(function () {
          inFlight = false;
          target = null;
          (result.warnings || []).forEach(function (warning) { log('note', warning); });
          log('ok', 'Exported ' + archive + ': ' + integer(result.stats.elements)
                    + ' elements, ' + integer(result.stats.nodes) + ' nodes.');
          if (done) done(result);
          return result;
        });
      });
    }).catch(function (err) {
      inFlight = false;
      target = null;
      log('err', 'Export failed: ' + err.message);
      if (done) done();
    });
  }

  return { run: run, meshRequest: meshRequest, baseName: baseName, save: save,
           files: files };
})();
