(function () {
  test('a selected soil layer keeps the work area within its assigned row', function () {
    var app = document.createElement('div');
    app.id = 'app';
    ['header', 'nav', 'div', 'div', 'main', 'div', 'section', 'footer'].forEach(function (tag, index) {
      var child = document.createElement(tag);
      if (index === 4) {
        child.id = 'workarea';
        ['aside', 'div', 'section', 'div', 'section'].forEach(function (workTag, workIndex) {
          var workChild = document.createElement(workTag);
          if (workIndex === 4) {
            workChild.id = 'dock';
            var model = document.createElement('section');
            model.className = 'dock-panel';
            var selection = document.createElement('section');
            selection.className = 'dock-panel';
            var selectionBody = document.createElement('div');
            selectionBody.className = 'dock-body';
            selectionBody.textContent = Array(80).fill('Soil layer geometry property').join('\n');
            selection.appendChild(selectionBody);
            workChild.appendChild(model);
            workChild.appendChild(document.createElement('div'));
            workChild.appendChild(selection);
          }
          child.appendChild(workChild);
        });
      }
      app.appendChild(child);
    });
    document.body.appendChild(app);

    try {
      var workarea = document.getElementById('workarea');
      var dock = document.getElementById('dock');
      T.ok(workarea.scrollHeight <= workarea.clientHeight,
           'selection content must scroll inside the dock rather than extend the work area');
      T.ok(dock.clientHeight <= workarea.clientHeight,
           'the dock must remain contained by the work area');
    } finally {
      app.remove();
    }
  });

  test('a tall command panel cannot push the work area outside the application frame', function () {
    var app = document.createElement('div');
    app.id = 'app';
    ['header', 'nav', 'div', 'div', 'main', 'div', 'section', 'footer'].forEach(function (tag, index) {
      var child = document.createElement(tag);
      if (index === 4) child.id = 'workarea';
      if (index === 5) child.id = 'split-cmd';
      if (index === 6) child.id = 'cmdpanel';
      app.appendChild(child);
    });
    var root = document.documentElement;
    var previousHeight = root.style.getPropertyValue('--cmd-height');
    root.style.setProperty('--cmd-height', '460px');
    document.body.appendChild(app);

    try {
      T.ok(app.scrollHeight <= app.clientHeight,
           'the grid must constrain its command row instead of overflowing');
      T.ok(document.getElementById('workarea').clientHeight >= 120,
           'the work area must retain its minimum usable height');
    } finally {
      app.remove();
      root.style.setProperty('--cmd-height', previousHeight);
    }
  });
})();
