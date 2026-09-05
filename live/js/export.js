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
      refinements: App.MESH_REFINEMENTS || []
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
    var url = URL.createObjectURL(new Blob([text], { type: mime || 'text/plain' }));
    var anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    // Revoked a tick later: a browser still reading the blob when the URL goes
    // away saves an empty file.
    setTimeout(function () { URL.revokeObjectURL(url); }, 0);
  }

  function run(done) {
    if (inFlight) {
      log('note', 'An export is already running.');
      return;
    }
    inFlight = true;
    log('note', 'Meshing and writing the Kratos deck…');

    return App.Api.post('/api/export/mdpa', meshRequest()).then(function (result) {
      inFlight = false;
      var name = baseName(App.PROJECT) + '.mdpa';
      // Through the module object, so a test can record what would be written
      // instead of making the browser save three files.
      App.Export.save(name, result.mdpa, 'text/plain');
      if (result.materials) App.Export.save('MaterialParameters.json', result.materials,
                                            'application/json');
      if (result.project_parameters) App.Export.save('ProjectParameters.json',
                                                      result.project_parameters,
                                                      'application/json');
      (result.warnings || []).forEach(function (warning) { log('note', warning); });
      log('ok', 'Exported ' + name + ': ' + integer(result.stats.elements)
                + ' elements, ' + integer(result.stats.nodes) + ' nodes.');
      if (done) done(result);
      return result;
    }).catch(function (err) {
      inFlight = false;
      log('err', 'Export failed: ' + err.message);
      if (done) done();
    });
  }

  return { run: run, meshRequest: meshRequest, baseName: baseName, save: save };
})();
