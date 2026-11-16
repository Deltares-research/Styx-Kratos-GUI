/* File ▸ Export model… — the Kratos deck, saved as one archive. */

function withExportStubs(body) {
  var saved = { Api: App.Api, Command: App.Command, PROJECT: App.PROJECT,
                save: App.Export.save, pickFile: App.Download.pickFile };
  var written = [], logged = [];
  App.Command = {
    ok: function (line) { logged.push(['ok', line]); },
    note: function (line) { logged.push(['note', line]); },
    err: function (line) { logged.push(['err', line]); }
  };
  App.Export.save = function (name, text) { written.push([name, text]); };
  // Never the real one: it would put a save dialog in front of the test run.
  App.Download.pickFile = function () { return Promise.resolve(null); };
  App.PROJECT = { name: 'Deep excavation — Rotterdam Zuid', layers: [{ id: 'L1' }, { id: 'L2' }],
                  mesh: { element_size: 2.5, order: 2 } };
  function restore() {
    App.Api = saved.Api; App.Command = saved.Command; App.PROJECT = saved.PROJECT;
    App.Export.save = saved.save;
    App.Download.pickFile = saved.pickFile;
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

test('the export meshes every body', function () {
  withExportStubs(function () {
    T.eq(App.Export.meshRequest().volume_keys, undefined,
         'hiding a layer must not drop it from the analysis');
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
      T.eq(written.length, 1, 'one save window bought one file: the archive');
      T.eq(written[0][0], 'Deep_excavation_Rotterdam_Zuid.zip');
      T.eq(written[0][1].type, 'application/zip', 'and it is the archive that was written');
      T.ok(logged.some(function (line) {
        return line[0] === 'note' && line[1] === 'check the constitutive law';
      }), 'a material warning reaches the command log rather than being swallowed');
      T.ok(logged.some(function (line) {
        return line[0] === 'ok' && line[1].indexOf('24 118 elements') !== -1;
      }), 'the summary counts what was written');
    });
  });
});

test('the archive holds the deck, its materials and its process file', function () {
  var result = { mdpa: 'Begin Properties 0\r\n', materials: '{"properties": []}',
                 project_parameters: '{"solver_settings": {}}' };
  T.eq(App.Export.files(result, 'model.mdpa').map(function (f) { return f.name; }),
       ['model.mdpa', 'MaterialParameters.json', 'ProjectParameters.json']);
  T.eq(App.Export.files(result, 'model.mdpa')[0].text, 'Begin Properties 0\r\n');
});

test('the real export save writes its archive to the picked file', function () {
  var save = App.Export.save;
  return withExportStubs(function () {
    var handle = fakeFileHandle('deck.zip');
    App.Export.save = save;
    App.Download.pickFile = function () { return Promise.resolve(handle); };
    App.Api = { post: function () {
      return Promise.resolve({ mdpa: 'Begin Nodes\nEnd Nodes\n',
                               stats: { nodes: 0, elements: 0 } });
    } };
    return App.Export.run().then(function () {
      T.ok(handle.written instanceof Blob, 'the file receives the archive, not its name');
      T.eq(handle.written.type, 'application/zip');
      T.ok(handle.written.size > 0);
      T.ok(handle.closed, 'the archive is committed to disk');
    });
  });
});

test('an export without materials or process metadata carries only the deck', function () {
  var bare = { mdpa: 'Begin Properties 0\r\n', materials: null, project_parameters: null };
  T.eq(App.Export.files(bare, 'model.mdpa').length, 1);
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

test('the export asks where to save before it meshes, not after', function () {
  return withExportStubs(function (written, logged) {
    var asked = null;
    App.Download.pickFile = function (name, mime) {
      asked = { name: name, mime: mime, beforeMeshing: !logged.length };
      return Promise.resolve(fakeFileHandle(name));
    };
    App.Api = { post: function () {
      return Promise.resolve({ mdpa: 'Begin Properties 0\r\n',
                               stats: { nodes: 1, elements: 1 } });
    } };
    return App.Export.run().then(function () {
      T.ok(asked.beforeMeshing,
           'a picker opened after the mesh request is refused: the gesture is spent');
      T.eq(asked.name, 'Deep_excavation_Rotterdam_Zuid.zip');
      T.eq(asked.mime, 'application/zip');
      T.eq(written.length, 1);
    });
  });
});

test('a dismissed save window cancels the export instead of meshing anyway', function () {
  return withExportStubs(function (written, logged) {
    App.Download.pickFile = function () {
      return Promise.resolve(App.Download.CANCELLED);
    };
    App.Api = { post: function () { throw new Error('the export should not have meshed'); } };
    return App.Export.run().then(function () {
      T.eq(written.length, 0);
      T.ok(logged.some(function (line) { return line[1] === 'Export cancelled.'; }),
           'the log says why nothing was written');
      // The guard has to be cleared, or every later export reports one in flight.
      App.Api = { post: function () {
        return Promise.resolve({ mdpa: 'x', stats: { nodes: 1, elements: 1 } });
      } };
      App.Download.pickFile = function () { return Promise.resolve(null); };
      return App.Export.run().then(function () { T.eq(written.length, 1); });
    });
  });
});
