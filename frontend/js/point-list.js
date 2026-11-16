/* ══════════════════════════════════════════════════════════════════
   point-list.js — the list of x, y points a window edits a polyline with.

   One row per point, each with a Remove button, and an Add point button under them that
   puts a new point after the last. A polyline keeps at least two points, so Remove is
   off while there are two. The Line window and the normal load window both use it.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.PointList = (function () {

  /* `points` is [[x, y], ...]. Returns the element to put in the window, and `read`,
     which gives the points as typed, as numbers. */
  function build(points) {
    var el = App.UI.el;
    var table = el('div.line-points');

    function read() {
      return Array.prototype.map.call(table.querySelectorAll('.line-point'), function (row) {
        var inputs = row.querySelectorAll('input');
        return [Number(inputs[0].value), Number(inputs[1].value)];
      });
    }

    function draw(list) {
      App.UI.clear(table);
      list.forEach(function (point, index) {
        var x = el('input.mesh-setting-control', {
          type: 'number', step: '0.1', value: String(point[0]) });
        var y = el('input.mesh-setting-control', {
          type: 'number', step: '0.1', value: String(point[1]) });
        var drop = el('button.btn.btn-sm', { type: 'button', text: 'Remove' });
        drop.disabled = list.length <= 2;
        drop.addEventListener('click', function () {
          var kept = read();
          kept.splice(index, 1);
          draw(kept);
        });
        table.appendChild(el('div.line-point', null, [
          el('span.line-point-number', { text: String(index + 1) }), x, y, drop]));
      });
    }

    var add = el('button.btn.btn-sm', { type: 'button', text: 'Add point' });
    add.addEventListener('click', function () {
      var list = read();
      var last = list[list.length - 1];
      list.push([last[0] + 1, last[1]]);
      draw(list);
    });
    draw(points);
    return { element: el('div', null, [table, add]), read: read };
  }

  return { build: build };
})();
