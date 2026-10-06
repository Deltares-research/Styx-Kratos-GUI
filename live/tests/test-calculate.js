/* Calculate — handing the deck to Kratos and reporting what came back. */

function withCalculateStubs(body) {
  var saved = { Api: App.Api, Command: App.Command, PROJECT: App.PROJECT,
                REFINEMENTS: App.MESH_REFINEMENTS, SELECTION: App.MESH_BODY_SELECTION };
  var logged = [];
  App.Command = {
    ok: function (line) { logged.push(['ok', line]); },
    note: function (line) { logged.push(['note', line]); },
    err: function (line) { logged.push(['err', line]); },
    write: function (kind, line) { logged.push([kind, line]); }
  };
  App.PROJECT = { name: 'Deep excavation — Rotterdam Zuid',
                  mesh: { element_size: 2.5, order: 2 } };
  App.MESH_REFINEMENTS = [];
  App.MESH_BODY_SELECTION = null;

  function restore() {
    App.Api = saved.Api; App.Command = saved.Command; App.PROJECT = saved.PROJECT;
    App.MESH_REFINEMENTS = saved.REFINEMENTS;
    App.MESH_BODY_SELECTION = saved.SELECTION;
  }

  var outcome;
  try {
    outcome = body(logged);
  } catch (error) {
    restore();
    throw error;
  }
  if (outcome && typeof outcome.then === 'function') {
    return outcome.then(function (value) { restore(); return value; },
                        function (error) { restore(); throw error; });
  }
  restore();
  return outcome;
}

function calculationResult(overrides) {
  var result = {
    ok: true, returncode: 0, seconds: 12.5,
    directory: 'C:\\Users\\someone\\KratosGUI\\runs\\Model_2026-09-20_10-15',
    inputs: ['Model.mdpa', 'MaterialParameters.json', 'ProjectParameters.json'],
    outputs: ['Model_1_Stage.post.msh', 'Model_1_Stage.post.res'],
    log: 'kratos.log', error: null,
    stats: { nodes: 38942, elements: 24118 }, warnings: []
  };
  Object.keys(overrides || {}).forEach(function (key) { result[key] = overrides[key]; });
  return result;
}

test('calculate sends the project mesh settings to the solver endpoint', function () {
  return withCalculateStubs(function () {
    var sent = null;
    App.Api = { post: function (path, body) {
      sent = { path: path, body: body };
      return Promise.resolve(calculationResult());
    } };
    return App.Calculate.run().then(function () {
      T.eq(sent.path, '/api/calculate');
      T.eq(sent.body.order, 2, "the project's own mesh settings, as the export uses");
    });
  });
});

test('a successful calculation says where the results were written', function () {
  return withCalculateStubs(function (logged) {
    App.Api = { post: function () { return Promise.resolve(calculationResult()); } };
    return App.Calculate.run().then(function () {
      var done = logged.filter(function (line) { return line[0] === 'ok'; });
      T.eq(done.length, 1, 'one line saying it worked');
      T.ok(done[0][1].indexOf('Model_2026-09-20_10-15') !== -1,
           'and it names the directory the user has to open: ' + done[0][1]);
      T.ok(logged.some(function (line) {
        return line[1].indexOf('Model_1_Stage.post.res') !== -1;
      }), 'the result files are named, not just counted');
    });
  });
});

test('a calculation Kratos refused reports its reason', function () {
  return withCalculateStubs(function (logged) {
    App.Api = { post: function () {
      return Promise.resolve(calculationResult({
        ok: false, returncode: 1, outputs: [],
        error: 'Error: There is no sub model part with name "Sheet_pile_1"'
      }));
    } };
    return App.Calculate.run().then(function () {
      T.ok(logged.some(function (line) {
        return line[0] === 'err' && line[1].indexOf('Sheet_pile_1') !== -1;
      }), 'what Kratos said reaches the log rather than "calculation failed"');
      T.ok(logged.some(function (line) {
        return line[1].indexOf('kratos.log') !== -1;
      }), 'and the full log is pointed at, since only its tail was sent');
    });
  });
});

test('an export warning is repeated before the run is reported', function () {
  return withCalculateStubs(function (logged) {
    App.Api = { post: function () {
      return Promise.resolve(calculationResult({
        warnings: ['Mohr-Coulomb is written as linear elastic']
      }));
    } };
    return App.Calculate.run().then(function () {
      var warned = logged.findIndex(function (line) {
        return line[1].indexOf('linear elastic') !== -1;
      });
      var done = logged.findIndex(function (line) { return line[0] === 'ok'; });
      T.ok(warned !== -1 && warned < done,
           'a caveat about the model is worth more before the result than after it');
    });
  });
});

test('a server that refused the request is reported, not swallowed', function () {
  return withCalculateStubs(function (logged) {
    App.Api = { post: function () {
      return Promise.reject(new Error('A calculation is already running.'));
    } };
    return App.Calculate.run().then(function () {
      T.ok(logged.some(function (line) {
        return line[0] === 'err' && line[1].indexOf('already running') !== -1;
      }), 'the failure names its cause');
    });
  });
});

test('a second press while one is in flight is refused rather than queued', function () {
  return withCalculateStubs(function (logged) {
    var release;
    App.Api = { post: function () {
      return new Promise(function (resolve) { release = resolve; });
    } };
    var first = App.Calculate.run();
    App.Calculate.run();
    T.ok(logged.some(function (line) {
      return line[1].indexOf('already running') !== -1;
    }), 'the second press says so');
    release(calculationResult());
    return first;
  });
});
