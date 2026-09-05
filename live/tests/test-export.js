/* File ▸ Export model… — the Kratos deck download. */

function withExportStubs(body) {
  var saved = { Api: App.Api, Command: App.Command, PROJECT: App.PROJECT,
                REFINEMENTS: App.MESH_REFINEMENTS, SELECTION: App.MESH_BODY_SELECTION,
                save: App.Export.save };
  var written = [], logged = [];
  App.Command = {
    ok: function (line) { logged.push(['ok', line]); },
    note: function (line) { logged.push(['note', line]); },
    err: function (line) { logged.push(['err', line]); }
  };
  App.Export.save = function (name, text) { written.push([name, text]); };
  App.PROJECT = { name: 'Deep excavation — Rotterdam Zuid',
                  mesh: { element_size: 2.5, order: 2 } };
  App.MESH_REFINEMENTS = [];
  App.MESH_BODY_SELECTION = null;
  function restore() {
    App.Api = saved.Api; App.Command = saved.Command; App.PROJECT = saved.PROJECT;
    App.MESH_REFINEMENTS = saved.REFINEMENTS;
    App.MESH_BODY_SELECTION = saved.SELECTION;
    App.Export.save = saved.save;
  }

  var outcome;
  try {
    outcome = body(written, logged);
  } catch (error) {
    restore();
    throw error;
  }
  // An async case must keep its stubs until it settles, not until it returns.
  if (outcome && typeof outcome.then === 'function') {
    return outcome.then(function (value) { restore(); return value; },
                        function (error) { restore(); throw error; });
  }
  restore();
  return outcome;
}

test('the export meshes every body unless bodies were explicitly chosen', function () {
  withExportStubs(function () {
    T.eq(App.Export.meshRequest().volume_keys, undefined,
         'hiding a layer must not drop it from the analysis');
    App.MESH_BODY_SELECTION = ['soil_L1'];
    T.eq(App.Export.meshRequest().volume_keys, ['soil_L1'],
         'an explicit choice in the mesh dialog is still honoured');
    T.eq(App.Export.meshRequest().element_size, 2.5, "the project's own mesh settings");
  });
});

test('the file is named after the project', function () {
  T.eq(App.Export.baseName({ name: 'Deep excavation — Rotterdam Zuid' }),
       'Deep_excavation_Rotterdam_Zuid');
  T.eq(App.Export.baseName({}), 'model');
});

test('a successful export writes the deck, its materials, and its process file', function () {
  return withExportStubs(function (written, logged) {
    App.Api = { post: function (path, body) {
      T.eq(path, '/api/export/mdpa');
      T.eq(body.order, 2);
      return Promise.resolve({
        mdpa: 'Begin Properties 0\r\nEnd Properties\r\n',
        materials: '{"properties": []}',
        project_parameters: '{"solver_settings": {}}',
        stats: { nodes: 38942, elements: 24118 },
        warnings: ['check the constitutive law']
      });
    } };
    return App.Export.run().then(function () {
      T.eq(written.length, 3, 'the deck, MaterialParameters.json and ProjectParameters.json');
      T.eq(written[0][0], 'Deep_excavation_Rotterdam_Zuid.mdpa');
      T.eq(written[1][0], 'MaterialParameters.json');
      T.eq(written[2][0], 'ProjectParameters.json');
      T.ok(logged.some(function (line) {
        return line[0] === 'note' && line[1] === 'check the constitutive law';
      }), 'a material warning reaches the command log rather than being swallowed');
      T.ok(logged.some(function (line) {
        return line[0] === 'ok' && line[1].indexOf('24 118 elements') !== -1;
      }), 'the summary counts what was written');
    });
  });
});

test('an export without materials or process metadata writes only the deck', function () {
  return withExportStubs(function (written) {
    App.Api = { post: function () {
      return Promise.resolve({ mdpa: 'Begin Properties 0\r\n', materials: null,
                               project_parameters: null,
                               stats: { nodes: 1, elements: 1 }, warnings: [] });
    } };
    return App.Export.run().then(function () {
      T.eq(written.length, 1);
    });
  });
});

test('a failed export is reported, not swallowed', function () {
  return withExportStubs(function (written, logged) {
    App.Api = { post: function () { return Promise.reject(new Error('gmsh said no')); } };
    return App.Export.run().then(function () {
      T.eq(written.length, 0);
      T.ok(logged.some(function (line) {
        return line[0] === 'err' && line[1].indexOf('gmsh said no') !== -1;
      }), 'the failure names its cause');
    });
  });
});
