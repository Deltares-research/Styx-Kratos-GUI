/* ══════════════════════════════════════════════════════════════════
   test-script-command.js — `script <file.py>`: the open model, written as a model
   script. `App.ScriptCommand` decides what was asked and what to send; the request,
   and saying what came back, are patches.js's.
   ══════════════════════════════════════════════════════════════════ */

(function () {

  var S = App.ScriptCommand;

  T.test('anything that is not `script` is not this command', function () {
    T.eq(S.command('scripts pit.py'), false);
    T.eq(S.command('run pit.py'), false);
    T.eq(S.command(''), false);
  });

  T.test('a path sends the path', function () {
    var answer = S.command('script models/pit.py');
    T.ok(answer.ok);
    T.eq(JSON.stringify(answer.body), JSON.stringify({ path: 'models/pit.py' }));
  });

  T.test('the path is the rest of the line, spaces and all', function () {
    var answer = S.command('script  D:/My models/pit A.py ');
    T.eq(answer.body.path, 'D:/My models/pit A.py');
  });

  T.test('--force asks for the file there to be replaced, wherever it is typed', function () {
    T.eq(JSON.stringify(S.command('script pit.py --force').body),
         JSON.stringify({ path: 'pit.py', force: true }));
    T.eq(S.command('script --force pit.py').body.path, 'pit.py');
  });

  T.test('no path says how, and sends nothing', function () {
    var answer = S.command('script');
    T.ok(!answer.ok);
    T.eq(answer.body, null);
    T.ok(/script <file\.py>/.test(answer.message), answer.message);
  });

  T.test('a file that is not .py is refused before anything is sent', function () {
    var answer = S.command('script pit.json');
    T.ok(!answer.ok);
    T.eq(answer.body, null);
    T.ok(/\.py file/.test(answer.message), answer.message);
  });

  T.test('what is said once it is written names both ways back', function () {
    var said = S.written('pit.py');
    T.ok(/run pit\.py/.test(said) && /--out deck\//.test(said), said);
  });

})();
