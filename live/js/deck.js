/* ══════════════════════════════════════════════════════════════════
   deck.js — a model that is a Kratos deck already, opened with `run <case.py>`.

   A deck case script builds nothing: it names a finished deck
   (server/app/deck.py), and `POST /api/project/script` sends that deck's mesh back
   with the project, in the shape `POST /api/import/mdpa` answers. There is nothing to
   generate, so instead of meshing, the command line goes straight to the Mesh tab
   with the deck's mesh drawn and its parts listed in the Model explorer.

   This module decides what is there and what to say about it. It has no DOM in it, so
   the headless runner executes it (live/tests/test-deck.js); drawing the mesh and
   switching tabs is patches.js's `showDeck`.
   ══════════════════════════════════════════════════════════════════ */

(function (App) {
  'use strict';

  function integer(value) {
    return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  /* Whether the answer to `run` carries a mesh to show. A parametric model
     carries none, and is meshed by the client as it always was. */
  function hasMesh(result) {
    return !!(result && result.mesh && (result.mesh.sections || []).length);
  }

  /* A section's row label: the deck's own SubModelPart name, or -- for elements no
     part claims -- their kind. The .mdpa import checklist names them the same way. */
  function label(section) {
    return section.part || (section.kind + ' (ungrouped)');
  }

  /* The Model explorer's "Imported mesh" rows, one per drawn part, in deck order --
     the shape `App.Model.setImportedParts` takes. */
  function parts(mesh) {
    return ((mesh && mesh.sections) || []).map(function (section) {
      return { key: section.key, label: label(section), color: section.color };
    });
  }

  /* "Dike section: 2D mesh, 16 885 nodes, 5 155 continuum, 374 beam elements;
     78 parts in the Model explorer." Elements only: a load condition is part of the
     deck, but not of what is drawn. */
  function summary(mesh, name) {
    var byKind = {}, order = [];
    (mesh.elements || []).forEach(function (entity) {
      if (!(entity.kind in byKind)) { byKind[entity.kind] = 0; order.push(entity.kind); }
      byKind[entity.kind] += entity.count;
    });
    var kinds = order.map(function (kind) {
      return integer(byKind[kind]) + ' ' + kind;
    }).join(', ') || 'no';
    var count = (mesh.sections || []).length;
    return name + ': ' + mesh.dimension + 'D mesh, ' + integer(mesh.nodes) + ' nodes, '
      + kinds + ' elements; ' + count + ' part' + (count === 1 ? '' : 's')
      + ' in the Model explorer, under "Imported mesh".';
  }

  /* ── Staged construction: a stage's own parts ─────────────────────────────
     A deck's phases are its stages (server/app/deck.py `phases`), keyed by the deck's
     own part names. The viewport draws a deck as imported sections, outside the
     project parts the frozen phase pass hides, so it asks this which parts the
     selected stage has. `null` means "draw by the eye alone": any tab but Staged
     construction, no stage selected, or a model that is not a deck. */
  function activeForView(project, phaseId, mode) {
    if (mode !== 'staged' || !project || !project.deck || !phaseId) return null;
    if (!App.Phases || !App.Phases.activeParts) return null;
    return App.Phases.activeParts(project, phaseId);
  }

  /* Whether a deck part is drawn: its eye is on and -- with a stage selected -- that
     stage has it. A part no stage names (an aggregate repeating elements other parts
     own, or elements no part claims) is in no stage, so it is not drawn in one. */
  function sectionShown(part, eyeOn, active) {
    if (eyeOn === false) return false;
    if (!active) return true;
    return !!part && active.indexOf(part) >= 0;
  }

  /* ── Results: the Model explorer beside the contour ───────────────────────
     A result section is named by the deck part it comes from, so the explorer row of
     that part -- its "Imported mesh" eye -- shows and hides it. `eyeOf(key)` is the
     viewport's own eye state, undefined for a key it has no row for; such a section
     (e.g. "Other elements") is always drawn. */
  function resultShown(part, eyeOf) {
    if (!part) return true;
    return eyeOf('imported:' + part) !== false;
  }

  App.Deck = { hasMesh: hasMesh, label: label, parts: parts, summary: summary,
               activeForView: activeForView, sectionShown: sectionShown,
               resultShown: resultShown };
})(window.App = window.App || {});
