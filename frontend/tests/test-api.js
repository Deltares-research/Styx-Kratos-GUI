/* Tests for frontend/js/api.js — the HTTP client.

   Everything here runs against an injected fetch, so no server is needed and the
   error paths (which are the interesting ones) are reachable. */

(function () {

  function stub(responses) {
    var calls = [];
    function fetchStub(url, opts) {
      calls.push({ url: url, opts: opts || {} });
      var next = responses.shift();
      if (typeof next === 'function') return next();
      return Promise.resolve(next);
    }
    fetchStub.calls = calls;
    return fetchStub;
  }

  function json(status, body) {
    return {
      ok: status >= 200 && status < 300,
      status: status,
      json: function () { return Promise.resolve(body); }
    };
  }

  function notJson(status) {
    return {
      ok: false, status: status,
      json: function () { return Promise.reject(new SyntaxError('not json')); }
    };
  }

  function api(responses) {
    return App.Api.create({ base: '', fetch: stub(responses) });
  }

  /* ── Base URL ────────────────────────────────────────────────── */

  test('a page served over http talks to its own origin', function () {
    T.eq(App.Api.baseFor({ protocol: 'http:' }), '');
    T.eq(App.Api.baseFor({ protocol: 'https:' }), '');
  });

  test('a page opened from disk falls back to the local server', function () {
    // The frozen demo is meant to run off file://. If someone opens frontend/ that
    // way, a relative fetch would resolve to a file: URL and fail opaquely.
    T.eq(App.Api.baseFor({ protocol: 'file:' }), 'http://127.0.0.1:8000');
  });

  /* ── Requests ────────────────────────────────────────────────── */

  test('the live client forwards requests to the current window fetch', function () {
    var original = window.fetch;
    var transport = stub([json(200, { status: 'ready' })]);
    window.fetch = transport;
    function restore() { window.fetch = original; }
    return App.Api.get('/api/health').then(function (body) {
      T.eq(body, { status: 'ready' });
      T.eq(transport.calls.length, 1);
      T.eq(transport.calls[0].url, App.Api.base + '/api/health');
      T.eq(transport.calls[0].opts.method, 'GET');
    }).then(restore, function (error) { restore(); throw error; });
  });

  test('get parses the body and sends no payload', function () {
    var client = api([json(200, { name: 'Site' })]);
    return client.get('/api/project').then(function (body) {
      T.eq(body, { name: 'Site' });
      var call = client.fetch.calls[0];
      T.eq(call.url, '/api/project');
      T.eq(call.opts.method, 'GET');
      T.eq(call.opts.body, undefined);
    });
  });

  test('put sends JSON with the right content type', function () {
    var client = api([json(200, { ok: true })]);
    return client.put('/api/project', { name: 'Site' }).then(function () {
      var call = client.fetch.calls[0];
      T.eq(call.opts.method, 'PUT');
      T.eq(call.opts.headers['Content-Type'], 'application/json');
      T.eq(JSON.parse(call.opts.body), { name: 'Site' });
    });
  });

  test('post and patch send JSON and return the server response', function () {
    var client = api([json(201, { id: 'load_1' }), json(200, { name: 'Updated' })]);
    return client.post('/api/loads', { value: 12 }).then(function (body) {
      T.eq(body, { id: 'load_1' });
      return client.patch('/api/project', { name: 'Updated' });
    }).then(function (body) {
      T.eq(body, { name: 'Updated' });
      T.eq(client.fetch.calls.map(function (call) {
        return [call.url, call.opts.method, call.opts.headers['Content-Type'],
                JSON.parse(call.opts.body)];
      }), [
        ['/api/loads', 'POST', 'application/json', { value: 12 }],
        ['/api/project', 'PATCH', 'application/json', { name: 'Updated' }]
      ]);
    });
  });

  test('the base url is prefixed to every path', function () {
    var client = App.Api.create({ base: 'http://127.0.0.1:8000', fetch: stub([json(200, {})]) });
    return client.get('/api/health').then(function () {
      T.eq(client.fetch.calls[0].url, 'http://127.0.0.1:8000/api/health');
    });
  });

  /* ── What an edit took away ──────────────────────────────────── */

  test("each of an edit's notes is said, and the answer comes back whole", function () {
    var said = [];
    var answer = { project: { name: 'Site' }, edit_notes: ['Removed the mesh size of a (1)'] };
    var client = App.Api.create({ base: '', fetch: stub([json(200, answer)]),
                                  note: function (line) { said.push(line); } });
    return client.patch('/api/project/layers', {}).then(function (body) {
      T.eq(said, ['Removed the mesh size of a (1)']);
      T.eq(body, answer);
    });
  });

  test('an answer with no notes says nothing', function () {
    var said = [];
    var client = App.Api.create({ base: '', fetch: stub([json(200, { edit_notes: [] }),
                                                         json(200, { name: 'Site' })]),
                                  note: function (line) { said.push(line); } });
    return client.patch('/api/project/layers', {})
      .then(function () { return client.get('/api/project'); })
      .then(function () { T.eq(said, []); });
  });

  test('the live client reports edit notes in the command log', function () {
    var originalFetch = window.fetch, originalCommand = App.Command;
    var said = [];
    var answer = { project: { name: 'Site' }, edit_notes: ['Removed an unused mesh size'] };
    window.fetch = stub([json(200, answer)]);
    App.Command = { note: function (line) { said.push(line); } };
    function restore() { window.fetch = originalFetch; App.Command = originalCommand; }
    return App.Api.patch('/api/project/layers', {}).then(function (body) {
      T.eq(body, answer);
      T.eq(said, answer.edit_notes);
    }).then(restore, function (error) { restore(); throw error; });
  });

  test('answers fetched outside the client report their notes and remain unchanged', function () {
    var original = App.Command, said = [];
    var answer = { project: { name: 'Site' }, edit_notes: ['Removed the deleted part'] };
    try {
      App.Command = { note: function (line) { said.push(line); } };
      T.eq(App.Api.told(answer), answer);
      T.eq(said, answer.edit_notes);
      App.Command = null;
      T.eq(App.Api.told(answer), answer);
    } finally { App.Command = original; }
  });

  /* ── Failures ────────────────────────────────────────────────── */

  test("a FastAPI error surfaces its detail, not just a status code", function () {
    var client = api([json(500, { detail: 'Boolean produced no volume for wall' })]);
    return T.rejects(function () { return client.get('/api/geometry'); }).then(function (err) {
      T.ok(/Boolean produced no volume for wall/.test(err.message), err.message);
      T.eq(err.status, 500);
    });
  });

  test('a 422 reports which field the schema rejected', function () {
    // pydantic's detail is a list of objects; flattening it is the difference
    // between a usable command-log line and "[object Object]".
    var client = api([json(422, { detail: [
      { loc: ['body', 'layers', 0, 'bottom'], msg: 'layer stack must be contiguous' }
    ] })]);
    return T.rejects(function () { return client.put('/api/project', {}); }).then(function (err) {
      T.ok(/contiguous/.test(err.message), err.message);
      T.ok(/layers/.test(err.message), err.message);
      T.ok(!/\[object Object\]/.test(err.message), err.message);
    });
  });

  test('a non-JSON error body still produces a readable message', function () {
    var client = api([notJson(502)]);
    return T.rejects(function () { return client.get('/api/geometry'); }).then(function (err) {
      T.ok(/502/.test(err.message), err.message);
    });
  });

  test('an unreachable server says so rather than leaking TypeError', function () {
    var client = api([function () { return Promise.reject(new TypeError('Failed to fetch')); }]);
    return T.rejects(function () { return client.get('/api/health'); }).then(function (err) {
      T.ok(/server/i.test(err.message), err.message);
      T.eq(err.offline, true);
    });
  });

})();
