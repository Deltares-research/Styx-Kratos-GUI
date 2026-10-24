/* Collapsible right-dock panels (js/ui.js), and the live-only one
   (frontend/js/patches.js) that js/ui.js has never heard of. */

function dockFixture(options) {
  options = options || {};

  function panel(id, withTools) {
    var section = document.createElement('section');
    section.className = 'dock-panel';
    section.id = id;

    var head = document.createElement('header');
    head.className = 'dock-head';
    var caret = document.createElement('span');
    caret.className = 'dock-caret';
    caret.textContent = '▾';
    head.appendChild(caret);
    if (withTools) {
      var tools = document.createElement('span');
      tools.className = 'dock-head-tools';
      tools.appendChild(document.createElement('button'));
      head.appendChild(tools);
    }

    var body = document.createElement('div');
    body.className = 'dock-body';
    section.appendChild(head);
    section.appendChild(body);
    return section;
  }

  function splitter(id) {
    var bar = document.createElement('div');
    bar.className = 'splitter splitter-h dock-split';
    bar.id = id;
    return bar;
  }

  var dock = document.createElement('aside');
  dock.id = 'dock';
  dock.appendChild(panel('panel-model', true));
  dock.appendChild(splitter('split-dock1'));
  dock.appendChild(panel('panel-selection'));
  dock.appendChild(splitter('split-dock2'));
  var stages = panel('panel-phases');
  stages.hidden = !options.stages;
  dock.appendChild(stages);
  var results = panel('panel-results');
  results.hidden = !options.results;
  dock.appendChild(results);
  document.body.appendChild(dock);
  return dock;
}

function withDock(options, body) {
  var dock = dockFixture(options);
  App.UI.collapsibleDock(dock);
  try {
    return body(dock);
  } finally {
    document.body.removeChild(dock);
  }
}

function head(dock, id) { return dock.querySelector('#' + id + ' .dock-head'); }
function caretOf(dock, id) { return dock.querySelector('#' + id + ' .dock-caret').textContent; }

test('clicking a dock header collapses its panel and turns the caret', function () {
  withDock({}, function (dock) {
    var panel = dock.querySelector('#panel-model');
    T.eq(caretOf(dock, 'panel-model'), '▾', 'starts open');

    head(dock, 'panel-model').click();
    T.ok(panel.classList.contains('collapsed'), 'the panel is marked collapsed');
    T.eq(caretOf(dock, 'panel-model'), '▸', 'the caret points at the closed panel');
    T.eq(dock.style.getPropertyValue('--r-model'), 'auto',
         'its grid row shrinks to the header it holds');

    head(dock, 'panel-model').click();
    T.ok(!panel.classList.contains('collapsed'));
    T.eq(caretOf(dock, 'panel-model'), '▾');
    T.eq(dock.style.getPropertyValue('--r-model'), '',
         'reopening hands the row back to the stylesheet, dragged height and all');
  });
});

test('every dock section collapses, not just the first', function () {
  withDock({ stages: true }, function (dock) {
    [['panel-model', '--r-model'],
     ['panel-selection', '--r-selection'],
     ['panel-phases', '--r-phases']].forEach(function (pair) {
      head(dock, pair[0]).click();
      T.ok(dock.querySelector('#' + pair[0]).classList.contains('collapsed'), pair[0]);
      T.eq(dock.style.getPropertyValue(pair[1]), 'auto', pair[1]);
    });
  });
});

test('the expand-all and collapse-all buttons do not collapse the panel', function () {
  withDock({}, function (dock) {
    /* They live inside the Model explorer's own header, so the header's click
       handler has to let them through. */
    dock.querySelector('#panel-model .dock-head-tools button').click();
    T.ok(!dock.querySelector('#panel-model').classList.contains('collapsed'));
  });
});

test('collapsing the selection panel hands the slack to the last open panel', function () {
  withDock({}, function (dock) {
    head(dock, 'panel-selection').click();
    T.eq(dock.style.getPropertyValue('--r-model'), '1fr',
         'without it the dock would end in dead space');
  });
  withDock({ stages: true }, function (dock) {
    head(dock, 'panel-selection').click();
    T.eq(dock.style.getPropertyValue('--r-phases'), '1fr');
    T.eq(dock.style.getPropertyValue('--r-model'), '', 'the model panel keeps its height');
  });
});

test('a hidden stages panel takes no part in the layout', function () {
  withDock({}, function (dock) {
    head(dock, 'panel-selection').click();
    T.eq(dock.style.getPropertyValue('--r-phases'), '',
         'a hidden panel must not be handed the slack');
  });
});

test('a splitter that would resize a collapsed panel is disabled', function () {
  withDock({ stages: true }, function (dock) {
    head(dock, 'panel-model').click();
    T.ok(dock.querySelector('#split-dock1').classList.contains('disabled'));
    head(dock, 'panel-model').click();
    T.ok(!dock.querySelector('#split-dock1').classList.contains('disabled'));

    head(dock, 'panel-phases').click();
    T.ok(dock.querySelector('#split-dock2').classList.contains('disabled'));
  });
});

/* The Results explorer is markup only the live page has, so `js/ui.js` cannot wire it:
   DOCK_ROWS names the three frozen panels and a panel missing from it gets no click
   handler at all. The live layer wires this one. */
function withResultsDock(body) {
  var dock = dockFixture({ stages: true, results: true });
  App.UI.collapsibleDock(dock);
  App.LivePatches.collapsibleResultsPanel(dock);
  try {
    return body(dock);
  } finally {
    document.body.removeChild(dock);
  }
}

test('clicking the Results explorer header collapses it', function () {
  withResultsDock(function (dock) {
    var panel = dock.querySelector('#panel-results');
    T.eq(caretOf(dock, 'panel-results'), '▾', 'starts open');

    head(dock, 'panel-results').click();
    T.ok(panel.classList.contains('collapsed'), 'the panel is marked collapsed');
    T.eq(caretOf(dock, 'panel-results'), '▸', 'the caret points at the closed panel');

    head(dock, 'panel-results').click();
    T.ok(!panel.classList.contains('collapsed'), 'and it opens again');
    T.eq(caretOf(dock, 'panel-results'), '▾');
  });
});

test('collapsing the Results explorer touches none of the grid rows', function () {
  withResultsDock(function (dock) {
    head(dock, 'panel-results').click();
    /* It sits in an implicit `auto` row -- #dock's grid-template-rows stops at the
       stages panel -- so hiding its body is the whole of the collapse. */
    T.eq(dock.style.getPropertyValue('--r-model'), '');
    T.eq(dock.style.getPropertyValue('--r-selection'), '');
    T.eq(dock.style.getPropertyValue('--r-phases'), '');
  });
});

test('wiring the Results explorer twice still collapses on one click', function () {
  withResultsDock(function (dock) {
    /* install() runs more than once (the tests alone do it), and a second handler on
       the same header would toggle the panel straight back open. */
    App.LivePatches.collapsibleResultsPanel(dock);
    head(dock, 'panel-results').click();
    T.ok(dock.querySelector('#panel-results').classList.contains('collapsed'));
  });
});

/* `.dock-panel { display: flex }` (css/layout.css) is an author rule, and it beats the
   browser's own `[hidden] { display: none }`. So `panel.hidden = true`, which is how
   leaving Staged construction or Results puts their explorers away, hid nothing: both
   stayed on screen in every tab after. Computed style, because the attribute alone was
   always set correctly. */
test('a hidden dock panel is not drawn', function () {
  withDock({ stages: false, results: false }, function (dock) {
    ['panel-phases', 'panel-results'].forEach(function (id) {
      T.eq(getComputedStyle(dock.querySelector('#' + id)).display, 'none', id);
    });
    T.eq(getComputedStyle(dock.querySelector('#panel-model')).display, 'flex',
         'the panels that are shown keep their layout');
  });
});
