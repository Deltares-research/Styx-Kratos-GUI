# Code size of Styx

This page gives the size of the code: the lines, classes and functions of each module. Use
it to see where the code is and how large each part is. The numbers are a snapshot of
the code on 2026-11-19. For how the parts work together, see
[ARCHITECTURE.md](ARCHITECTURE.md).

## How the code is counted

- **Lines:** all physical lines of the file.
- **Code:** the lines that contain code. Blank lines and comment lines are not code. A
  Python docstring counts as a comment.
- **Python:** the files are parsed with `ast`. *Classes* includes nested classes.
  *Methods* are the functions directly in a class body. *Functions* are all other
  functions, also nested ones.
- **JavaScript:** the browser code is plain ES5 modules on a global `App` object, with no
  `class` and no arrow functions. *Functions* is the number of `function` keywords after
  comments, strings and regular expressions are removed. These counts are close estimates,
  not exact.
- **Not counted:** `frontend/vendor/` (three.js), test fixtures, virtual environments,
  `__pycache__`, coverage output, and the local folders `plan/` and `graphify-out/`.

## Overview

| Area | Language | Files | Lines | Code | Classes | Functions | Methods |
|---|---|--:|--:|--:|--:|--:|--:|
| Engine and server (`core/`, `backend/`) | Python | 61 | 25,748 | 14,799 | 111 | 916 | 159 |
| Command line (`cli/`) | Python | 26 | 5,827 | 4,302 | 8 | 317 | 35 |
| Server tests (`tests/`) | Python | 195 | 52,521 | 34,020 | 33 | 4,201 | 72 |
| Benchmarks and test runner (`benchmarks/`, `tools/`) | Python | 8 | 1,321 | 926 | 5 | 71 | 0 |
| Browser app (`frontend/js`) | JavaScript | 61 | 35,233 | 26,530 | 0 | 3,981 | 0 |
| Frozen shell (`frontend/base/js`) | JavaScript | 9 | 3,971 | 2,794 | 0 | 406 | 0 |
| Browser tests (`frontend/tests`, JS) | JavaScript | 81 | 29,523 | 24,923 | 0 | 6,141 | 0 |
| Browser test runners (`frontend/tests`, Python) | Python | 2 | 480 | 318 | 0 | 7 | 0 |
| Stylesheets | CSS | 4 | 1,472 | 1,182 | 0 | 0 | 0 |
| HTML pages | HTML | 2 | 465 | 381 | 0 | 0 | 0 |
| **Total** | | **449** | **156,561** | **110,175** | **157** | **16,040** | **266** |

| Scope | Files | Lines | Code |
|---|--:|--:|--:|
| Application code | 163 | 72,716 | 49,988 |
| Tests, benchmarks and test runners | 286 | 83,845 | 60,187 |

## Modules

Each table lists the files of one area, the largest first. A long list shows the 25
largest files and one row for the rest.

### Engine and server (`core/`, `backend/`)

| Module | Lines | Code | Classes | Functions | Methods |
|---|--:|--:|--:|--:|--:|
| `core/model/schemas.py` | 3,400 | 1,858 | 53 | 20 | 124 |
| `core/kratos/writer.py` | 2,876 | 1,746 | 3 | 78 | 0 |
| `core/session.py` | 1,677 | 1,032 | 6 | 95 | 0 |
| `core/geometry/solid_model.py` | 1,386 | 772 | 2 | 41 | 0 |
| `core/geometry/meshing.py` | 1,044 | 709 | 4 | 34 | 2 |
| `core/model/drafts.py` | 1,004 | 648 | 1 | 48 | 0 |
| `core/model/migration.py` | 936 | 616 | 0 | 50 | 0 |
| `core/kratos/parameters.py` | 1,161 | 566 | 2 | 26 | 0 |
| `core/model/soil_models.py` | 770 | 427 | 2 | 45 | 0 |
| `core/kratos/materials.py` | 635 | 377 | 1 | 19 | 0 |
| `core/results/catalog.py` | 705 | 367 | 3 | 36 | 0 |
| `core/model/solver.py` | 546 | 350 | 0 | 14 | 0 |
| `core/analysis/calculation.py` | 604 | 319 | 2 | 24 | 0 |
| `core/kratos/interfaces.py` | 538 | 313 | 3 | 22 | 0 |
| `core/kratos/mdpa_reader.py` | 517 | 306 | 4 | 15 | 5 |
| `core/model/stages.py` | 511 | 261 | 1 | 28 | 0 |
| `core/results/fields.py` | 522 | 260 | 2 | 20 | 1 |
| `core/kratos/condition_checks.py` | 412 | 249 | 0 | 27 | 0 |
| `core/kratos/external_deck.py` | 394 | 236 | 1 | 17 | 0 |
| `core/model/script_writer.py` | 309 | 224 | 0 | 12 | 0 |
| `core/model/regions.py` | 314 | 216 | 1 | 19 | 4 |
| `core/geometry/tessellation.py` | 386 | 212 | 2 | 12 | 2 |
| `core/results/convergence.py` | 321 | 205 | 0 | 10 | 0 |
| `core/results/gid_reader.py` | 351 | 200 | 5 | 3 | 9 |
| `core/scripting.py` | 303 | 171 | 1 | 10 | 0 |
| 36 smaller files | 4,126 | 2,159 | 12 | 191 | 12 |

### Command line (`cli/`)

| Module | Lines | Code | Classes | Functions | Methods |
|---|--:|--:|--:|--:|--:|
| `cli/commands/structures.py` | 674 | 550 | 0 | 35 | 0 |
| `cli/commands/results.py` | 539 | 405 | 0 | 32 | 0 |
| `cli/commands/conditions.py` | 492 | 383 | 0 | 27 | 0 |
| `cli/terminal/shell.py` | 502 | 374 | 2 | 13 | 22 |
| `cli/commands/ground.py` | 433 | 330 | 0 | 28 | 0 |
| `cli/commands/stages.py` | 426 | 305 | 0 | 25 | 0 |
| `cli/commands/project.py` | 345 | 272 | 0 | 21 | 0 |
| `cli/commands/picture.py` | 262 | 208 | 0 | 15 | 0 |
| `cli/terminal/pictures.py` | 229 | 170 | 2 | 8 | 7 |
| `cli/commands/analysis.py` | 213 | 154 | 1 | 8 | 4 |
| `cli/commands/inspection.py` | 205 | 152 | 0 | 11 | 0 |
| `cli/commands/meshing.py` | 194 | 144 | 0 | 12 | 0 |
| `cli/commands/volumes.py` | 179 | 135 | 0 | 10 | 0 |
| `cli/terminal/words.py` | 183 | 119 | 0 | 15 | 0 |
| `cli/commands/surfaces.py` | 157 | 114 | 0 | 11 | 0 |
| `cli/terminal/main.py` | 151 | 94 | 1 | 4 | 2 |
| `cli/terminal/tables.py` | 141 | 90 | 0 | 7 | 0 |
| `cli/terminal/style.py` | 131 | 84 | 0 | 9 | 0 |
| `cli/terminal/output.py` | 131 | 72 | 2 | 10 | 0 |
| `cli/commands/edit.py` | 85 | 55 | 0 | 7 | 0 |
| `cli/terminal/files.py` | 89 | 54 | 0 | 6 | 0 |
| `cli/commands/interactive.py` | 35 | 26 | 0 | 2 | 0 |
| `cli/__main__.py` | 29 | 12 | 0 | 1 | 0 |
| `cli/terminal/__init__.py` | 2 | 0 | 0 | 0 | 0 |
| `cli/__init__.py` | 0 | 0 | 0 | 0 | 0 |
| `cli/commands/__init__.py` | 0 | 0 | 0 | 0 | 0 |

### Server tests (`tests/`)

| Module | Lines | Code | Classes | Functions | Methods |
|---|--:|--:|--:|--:|--:|
| `tests/test_schemas.py` | 1,904 | 1,209 | 0 | 192 | 0 |
| `tests/test_api.py` | 1,866 | 1,178 | 0 | 123 | 0 |
| `tests/test_kratos.py` | 1,487 | 948 | 0 | 131 | 0 |
| `tests/test_session.py` | 1,222 | 741 | 0 | 138 | 0 |
| `tests/test_kratos_interfaces.py` | 1,124 | 696 | 0 | 94 | 0 |
| `tests/test_layout.py` | 935 | 625 | 0 | 53 | 0 |
| `tests/test_soil_models.py` | 895 | 604 | 0 | 73 | 0 |
| `tests/test_soil_lines.py` | 837 | 577 | 0 | 98 | 0 |
| `tests/e2e/test_pictures.py` | 719 | 577 | 0 | 43 | 0 |
| `tests/test_calculate.py` | 861 | 513 | 3 | 62 | 7 |
| `tests/test_results.py` | 786 | 489 | 0 | 66 | 0 |
| `tests/test_deck.py` | 652 | 463 | 0 | 51 | 0 |
| `tests/test_mdpa_import.py` | 714 | 457 | 0 | 47 | 0 |
| `tests/test_draft_parity.py` | 528 | 450 | 0 | 19 | 0 |
| `tests/test_result_fields.py` | 743 | 447 | 0 | 52 | 0 |
| `tests/test_stages.py` | 697 | 447 | 0 | 68 | 0 |
| `tests/api/test_route_contract.py` | 533 | 431 | 1 | 19 | 0 |
| The steps of the GUI tutorial in `tests/e2e/tutorials/` | 580 | 428 | 0 | 32 | 0 |
| `tests/test_kratos_flow.py` | 607 | 412 | 0 | 53 | 0 |
| `tests/test_drafts.py` | 623 | 399 | 0 | 61 | 0 |
| `tests/cli/test_structure_commands.py` | 607 | 397 | 0 | 54 | 0 |
| `tests/e2e/test_flows.py` | 544 | 395 | 0 | 33 | 0 |
| `tests/test_result_mesh.py` | 546 | 372 | 0 | 35 | 0 |
| `tests/kratos/test_live_interfaces.py` | 576 | 361 | 0 | 34 | 0 |
| `tests/test_kratos_stage_processes.py` | 577 | 352 | 0 | 63 | 0 |
| 170 smaller files | 31,358 | 20,052 | 29 | 2,507 | 65 |

### Benchmarks and test runner (`benchmarks/`, `tools/`)

| Module | Lines | Code | Classes | Functions | Methods |
|---|--:|--:|--:|--:|--:|
| `benchmarks/cases.py` | 490 | 358 | 0 | 41 | 0 |
| `benchmarks/runner.py` | 181 | 134 | 4 | 6 | 0 |
| `tools/docs_site.py` | 179 | 121 | 0 | 7 | 0 |
| `benchmarks/models.py` | 164 | 110 | 0 | 6 | 0 |
| `tools/test.py` | 145 | 99 | 1 | 6 | 0 |
| `tools/gui_tutorial.py` | 110 | 68 | 0 | 4 | 0 |
| `benchmarks/__main__.py` | 52 | 36 | 0 | 1 | 0 |
| `benchmarks/__init__.py` | 0 | 0 | 0 | 0 | 0 |

### Browser app (`frontend/js`)

| Module | Lines | Code | Functions |
|---|--:|--:|--:|
| `frontend/js/patches.js` | 5,454 | 3,963 | 593 |
| `frontend/js/viewport.js` | 4,198 | 3,022 | 417 |
| `frontend/js/model.js` | 2,389 | 1,862 | 372 |
| `frontend/js/boundary-conditions.js` | 1,880 | 1,535 | 244 |
| `frontend/js/solver-settings.js` | 1,022 | 1,012 | 0 |
| `frontend/js/results.js` | 1,289 | 912 | 132 |
| `frontend/js/picture.js` | 1,066 | 894 | 190 |
| `frontend/js/picture-draw.js` | 1,068 | 850 | 100 |
| `frontend/js/interfaces.js` | 975 | 771 | 121 |
| `frontend/js/convergence-plot.js` | 899 | 674 | 121 |
| `frontend/js/soil-model-table.js` | 586 | 578 | 0 |
| `frontend/js/material-sets.js` | 722 | 564 | 111 |
| `frontend/js/mesh-settings.js` | 651 | 525 | 91 |
| `frontend/js/stages.js` | 810 | 491 | 97 |
| `frontend/js/anchors.js` | 632 | 471 | 88 |
| `frontend/js/soil-layers-dialog.js` | 582 | 463 | 88 |
| `frontend/js/beams.js` | 541 | 417 | 76 |
| `frontend/js/results-render.js` | 631 | 400 | 39 |
| `frontend/js/results-view.js` | 541 | 381 | 46 |
| `frontend/js/results-plot.js` | 504 | 379 | 71 |
| `frontend/js/soil-volume-dialog.js` | 464 | 350 | 50 |
| `frontend/js/picture-writers.js` | 415 | 337 | 44 |
| `frontend/js/surface-water.js` | 452 | 322 | 59 |
| `frontend/js/loads.js` | 372 | 321 | 47 |
| `frontend/js/convergence-window.js` | 396 | 300 | 36 |
| 36 smaller files | 6,694 | 4,736 | 748 |

### Frozen shell (`frontend/base/js`)

| Module | Lines | Code | Functions |
|---|--:|--:|--:|
| `frontend/base/js/dialogs.js` | 1,293 | 916 | 177 |
| `frontend/base/js/data.js` | 956 | 749 | 54 |
| `frontend/base/js/explorer.js` | 385 | 257 | 42 |
| `frontend/base/js/app.js` | 335 | 236 | 28 |
| `frontend/base/js/ui.js` | 374 | 217 | 39 |
| `frontend/base/js/orbit.js` | 193 | 117 | 13 |
| `frontend/base/js/toolbars.js` | 166 | 115 | 24 |
| `frontend/base/js/command.js` | 139 | 100 | 15 |
| `frontend/base/js/menubar.js` | 130 | 87 | 14 |

### Browser tests (`frontend/tests`, JS)

| Module | Lines | Code | Functions |
|---|--:|--:|--:|
| `frontend/tests/test-results.js` | 1,705 | 1,425 | 386 |
| `frontend/tests/test-authoring-dom.js` | 1,349 | 1,281 | 240 |
| `frontend/tests/test-model.js` | 1,361 | 1,131 | 274 |
| `frontend/tests/test-patches.js` | 1,250 | 1,070 | 340 |
| `frontend/tests/test-viewport-live.js` | 1,018 | 933 | 243 |
| `frontend/tests/test-patches-editing.js` | 839 | 808 | 236 |
| `frontend/tests/test-picture-live.js` | 789 | 698 | 224 |
| `frontend/tests/test-viewport.js` | 916 | 658 | 140 |
| `frontend/tests/test-boundary-conditions.js` | 744 | 657 | 113 |
| `frontend/tests/test-picture-draw.js` | 739 | 610 | 131 |
| `frontend/tests/test-stages.js` | 788 | 609 | 144 |
| `frontend/tests/test-patches-results.js` | 670 | 609 | 164 |
| `frontend/tests/test-toolbar.js` | 673 | 581 | 179 |
| `frontend/tests/test-patches-stages.js` | 617 | 551 | 123 |
| `frontend/tests/test-material-sets.js` | 600 | 536 | 103 |
| `frontend/tests/test-loads.js` | 624 | 519 | 146 |
| `frontend/tests/test-results-render.js` | 725 | 502 | 98 |
| `frontend/tests/test-normal-loads.js` | 595 | 496 | 125 |
| `frontend/tests/test-convergence-plot.js` | 561 | 480 | 98 |
| `frontend/tests/test-not-yet.js` | 525 | 457 | 114 |
| `frontend/tests/test-results-plot.js` | 536 | 431 | 110 |
| `frontend/tests/test-model-props.js` | 452 | 407 | 93 |
| `frontend/tests/test-calculate-button.js` | 464 | 403 | 103 |
| `frontend/tests/test-soil-layers-dialog.js` | 445 | 398 | 108 |
| `frontend/tests/test-frozen-ui.js` | 443 | 390 | 80 |
| 56 smaller files | 10,095 | 8,283 | 2,026 |

### Browser test runners (`frontend/tests`, Python)

| Module | Lines | Code | Classes | Functions | Methods |
|---|--:|--:|--:|--:|--:|
| `frontend/tests/run_headless.py` | 283 | 182 | 0 | 3 | 0 |
| `frontend/tests/syntax_check.py` | 197 | 136 | 0 | 4 | 0 |
