/* Kratos' word for the construction sequence is "stage", and Styx uses it. The frozen
   mockup data (js/data.js) still says "phase" in a menu, a rail tooltip and a mode
   hint. It is never edited, so its strings are rewritten here in memory, after it
   loads and before anything draws them. Icon keys are names, not words, and are left
   alone. */

var App = window.App || {};

App.Vocabulary = (function () {
  function word(text) {
    return String(text)
      .replace(/\bPhases\b/g, 'Stages').replace(/\bphases\b/g, 'stages')
      .replace(/\bPhase\b/g, 'Stage').replace(/\bphase\b/g, 'stage');
  }

  function relabelItems(items) {
    (items || []).forEach(function (item) {
      if (!item || typeof item !== 'object') return;
      ['label', 'tip', 'hint', 'title'].forEach(function (key) {
        if (typeof item[key] === 'string') item[key] = word(item[key]);
      });
      if (item.items) relabelItems(item.items);
      if (item.flyout) relabelItems(item.flyout);
    });
  }

  function relabel() {
    relabelItems(App.MENUS);
    relabelItems(App.MODES);
    Object.keys(App.RAILS || {}).forEach(function (mode) { relabelItems(App.RAILS[mode]); });
  }

  relabel();
  return { relabel: relabel, word: word };
})();
