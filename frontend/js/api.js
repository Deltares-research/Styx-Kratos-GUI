/* ══════════════════════════════════════════════════════════════════
   api.js — the HTTP client.

   Small on purpose. The only real work is turning a failed response into a
   message a person can act on: FastAPI returns `{detail: "..."}` for our own
   errors and `{detail: [{loc, msg}, ...]}` for schema rejections, and both need
   to end up as one line in the command log rather than "[object Object]".

   An edit's answer can carry `edit_notes`: what the edit took away besides what was
   asked, such as the mesh size of a body it removed (backend/routes/common.py
   `stored`). Every answer comes through here, so each note is shown whichever part
   of the GUI made the edit.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.Api = (function () {

  /* Where the server is, given a page location.

     Served over http the app talks to its own origin, so nothing is hardcoded
     and the port can change. Opened off disk -- which is how the frozen demo is
     meant to be used -- a relative fetch would resolve to a file: URL and fail
     with an opaque TypeError, so fall back to the local server explicitly. */
  function baseFor(location) {
    return location.protocol === 'file:' ? 'http://127.0.0.1:8000' : '';
  }

  function messageFrom(status, body) {
    var detail = body && body.detail;

    if (typeof detail === 'string') return detail;

    if (Array.isArray(detail)) {
      // pydantic: one entry per rejected field. `loc` starts with "body".
      return detail.map(function (d) {
        var where = (d.loc || []).slice(1).join('.');
        return where ? where + ': ' + d.msg : d.msg;
      }).join('; ');
    }
    return 'HTTP ' + status;
  }

  /* Give each of `answer`'s `edit_notes` to `note`, and give back the answer. */
  function told(answer, note) {
    if (note && answer && Array.isArray(answer.edit_notes)) answer.edit_notes.forEach(note);
    return answer;
  }

  function create(options) {
    var base = options.base || '';
    var fetcher = options.fetch;
    var note = options.note;

    function request(method, path, body) {
      var opts = { method: method, headers: {} };
      if (body !== undefined) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
      }

      return fetcher(base + path, opts).then(function (response) {
        if (response.ok) {
          return response.json().then(function (answer) { return told(answer, note); });
        }

        // Read the body for a reason, but never let a malformed one mask the status.
        return response.json().catch(function () { return null; })
          .then(function (parsed) {
            var err = new Error(messageFrom(response.status, parsed));
            err.status = response.status;
            throw err;
          });
      }, function (cause) {
        // fetch only rejects when the request never completed.
        var err = new Error('Cannot reach the model server at ' + (base || 'this origin')
                            + ' — is it running? (' + cause.message + ')');
        err.offline = true;
        throw err;
      });
    }

    return {
      base: base,
      fetch: fetcher,
      get:   function (path)       { return request('GET', path); },
      put:   function (path, body) { return request('PUT', path, body); },
      post:  function (path, body) { return request('POST', path, body); },
      patch: function (path, body) { return request('PATCH', path, body); }
    };
  }

  /* The instance the app uses. Tests build their own with create(). */
  function noteInTheLog(line) {
    if (App.Command && App.Command.note) App.Command.note(line);
  }

  var live = create({
    base: baseFor(window.location),
    fetch: function (url, opts) { return window.fetch(url, opts); },
    note: noteInTheLog
  });

  return {
    create: create, baseFor: baseFor,
    base: live.base,
    get: live.get, put: live.put, post: live.post, patch: live.patch,
    /* For an answer fetched outside this client: a DELETE (js/patches.js). */
    told: function (answer) { return told(answer, noteInTheLog); }
  };
})();
