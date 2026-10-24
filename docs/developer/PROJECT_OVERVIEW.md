# Code size of Styx

This page gives the size of the code: the lines, classes and functions of each module. Use
it to see where the code is and how large each part is. The numbers are a snapshot of the
`docs/developer-guide` branch on 2026-10-21. For how the parts work together, see
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
| Engine and server (`core/`, `backend/`) | Python | 51 | 16,538 | 9,291 | 92 | 580 | 100 |
| Command line (`cli/`) | Python | 22 | 3,695 | 2,681 | 5 | 213 | 23 |
| Server tests (`tests/`) | Python | 139 | 31,198 | 19,411 | 20 | 2,533 | 49 |
| Benchmarks and test runner (`benchmarks/`, `tools/`) | Python | 6 | 822 | 583 | 5 | 47 | 0 |
| Browser app (`frontend/js`) | JavaScript | 39 | 17,541 | 12,654 | 0 | 1,977 | 0 |
| Frozen shell (`frontend/base/js`) | JavaScript | 9 | 3,914 | 2,754 | 0 | 401 | 0 |
| Browser tests (`frontend/tests`, JS) | JavaScript | 55 | 14,387 | 11,550 | 0 | 2,851 | 0 |
| Browser test runners (`frontend/tests`, Python) | Python | 2 | 408 | 264 | 0 | 7 | 0 |
| Stylesheets | CSS | 4 | 1,189 | 974 | 0 | 0 | 0 |
| HTML pages | HTML | 2 | 389 | 311 | 0 | 0 | 0 |
| **Total** | | **329** | **90,081** | **60,473** | **122** | **8,609** | **172** |

| Scope | Files | Lines | Code |
|---|--:|--:|--:|
| Application code | 127 | 43,266 | 28,665 |
| Tests, benchmarks and test runners | 202 | 46,815 | 31,808 |

## Modules

Each table lists the files of one area, the largest first. A long list shows the 25
largest files and one row for the rest.

### Engine and server (`core/`, `backend/`)

| Module | Lines | Code | Classes | Functions | Methods |
|---|--:|--:|--:|--:|--:|
| `core/model/schemas.py` | 2,034 | 1,102 | 43 | 6 | 72 |
| `core/kratos/writer.py` | 1,699 | 949 | 2 | 49 | 0 |
| `core/session.py` | 1,146 | 698 | 6 | 66 | 0 |
| `core/geometry/solid_model.py` | 1,258 | 689 | 2 | 37 | 0 |
| `core/geometry/meshing.py` | 668 | 456 | 3 | 22 | 2 |
| `core/model/drafts.py` | 664 | 456 | 1 | 35 | 0 |
| `core/kratos/parameters.py` | 783 | 394 | 1 | 22 | 0 |
| `core/results/catalog.py` | 637 | 329 | 3 | 32 | 0 |
| `core/kratos/mdpa_reader.py` | 518 | 306 | 4 | 15 | 5 |
| `core/kratos/materials.py` | 437 | 255 | 1 | 13 | 0 |
| `core/geometry/tessellation.py` | 388 | 214 | 2 | 12 | 2 |
| `core/analysis/calculation.py` | 411 | 210 | 2 | 15 | 0 |
| `core/kratos/interfaces.py` | 365 | 204 | 3 | 16 | 0 |
| `core/model/script_writer.py` | 276 | 201 | 0 | 11 | 0 |
| `core/results/gid_reader.py` | 351 | 200 | 5 | 3 | 9 |
| `core/kratos/external_deck.py` | 342 | 197 | 1 | 17 | 0 |
| `core/results/fields.py` | 385 | 187 | 2 | 15 | 1 |
| `core/model/stages.py` | 365 | 182 | 1 | 17 | 0 |
| `core/model/migration.py` | 243 | 173 | 0 | 13 | 0 |
| `core/geometry/cad_import.py` | 242 | 170 | 2 | 10 | 2 |
| `core/scripting.py` | 271 | 151 | 1 | 9 | 0 |
| `core/model/units.py` | 222 | 143 | 2 | 11 | 0 |
| `core/results/mesh.py` | 280 | 141 | 0 | 10 | 0 |
| `backend/launcher.py` | 176 | 115 | 0 | 11 | 0 |
| `core/gmsh_worker.py` | 212 | 103 | 1 | 15 | 0 |
| 26 smaller files | 2,165 | 1,066 | 4 | 98 | 7 |

### Command line (`cli/`)

| Module | Lines | Code | Classes | Functions | Methods |
|---|--:|--:|--:|--:|--:|
| `cli/commands/structures.py` | 548 | 440 | 0 | 33 | 0 |
| `cli/terminal/shell.py` | 502 | 374 | 2 | 13 | 22 |
| `cli/commands/results.py` | 411 | 306 | 0 | 25 | 0 |
| `cli/commands/ground.py` | 304 | 223 | 0 | 22 | 0 |
| `cli/commands/project.py` | 272 | 216 | 0 | 16 | 0 |
| `cli/commands/stages.py` | 257 | 180 | 0 | 19 | 0 |
| `cli/commands/inspection.py` | 203 | 150 | 0 | 11 | 0 |
| `cli/commands/volumes.py` | 179 | 135 | 0 | 10 | 0 |
| `cli/commands/meshing.py` | 127 | 90 | 0 | 9 | 0 |
| `cli/terminal/words.py` | 134 | 89 | 0 | 10 | 0 |
| `cli/terminal/style.py` | 131 | 84 | 0 | 9 | 0 |
| `cli/terminal/tables.py` | 100 | 66 | 0 | 5 | 0 |
| `cli/terminal/output.py` | 119 | 65 | 2 | 9 | 0 |
| `cli/terminal/main.py` | 104 | 63 | 1 | 3 | 1 |
| `cli/commands/analysis.py` | 84 | 62 | 0 | 5 | 0 |
| `cli/commands/edit.py` | 85 | 55 | 0 | 7 | 0 |
| `cli/terminal/files.py` | 75 | 48 | 0 | 5 | 0 |
| `cli/commands/interactive.py` | 35 | 26 | 0 | 2 | 0 |
| `cli/__main__.py` | 23 | 9 | 0 | 0 | 0 |
| `cli/__init__.py` | 0 | 0 | 0 | 0 | 0 |
| `cli/commands/__init__.py` | 0 | 0 | 0 | 0 | 0 |
| `cli/terminal/__init__.py` | 2 | 0 | 0 | 0 | 0 |

### Server tests (`tests/`)

| Module | Lines | Code | Classes | Functions | Methods |
|---|--:|--:|--:|--:|--:|
| `tests/test_api.py` | 1,651 | 1,040 | 0 | 107 | 0 |
| `tests/test_schemas.py` | 1,571 | 969 | 0 | 162 | 0 |
| `tests/test_kratos.py` | 1,215 | 755 | 0 | 110 | 0 |
| `tests/test_layout.py` | 932 | 623 | 0 | 53 | 0 |
| `tests/test_session.py` | 861 | 508 | 0 | 101 | 0 |
| `tests/test_mdpa_import.py` | 714 | 457 | 0 | 47 | 0 |
| `tests/test_deck.py` | 560 | 396 | 0 | 44 | 0 |
| `tests/test_calculate.py` | 668 | 376 | 3 | 51 | 7 |
| `tests/test_kratos_interfaces.py` | 643 | 370 | 0 | 52 | 0 |
| `tests/test_results.py` | 619 | 367 | 0 | 54 | 0 |
| `tests/test_result_mesh.py` | 511 | 343 | 0 | 33 | 0 |
| `tests/test_github_automation.py` | 511 | 318 | 0 | 60 | 0 |
| `tests/test_build_2d.py` | 528 | 306 | 0 | 42 | 0 |
| `tests/api/test_route_contract.py` | 375 | 303 | 1 | 14 | 0 |
| `tests/test_load_translation.py` | 552 | 290 | 0 | 47 | 0 |
| `tests/test_kratos_3d.py` | 501 | 286 | 0 | 45 | 0 |
| `tests/test_result_fields.py` | 525 | 284 | 0 | 39 | 0 |
| `tests/test_script.py` | 394 | 276 | 0 | 31 | 0 |
| `tests/test_gid_results.py` | 432 | 271 | 0 | 28 | 0 |
| `tests/test_build.py` | 420 | 234 | 0 | 27 | 0 |
| `tests/test_meshing_2d.py` | 377 | 232 | 0 | 33 | 0 |
| `tests/test_export_golden.py` | 375 | 228 | 0 | 30 | 0 |
| `tests/test_stages.py` | 400 | 228 | 0 | 40 | 0 |
| `tests/pipeline/deck_invariants.py` | 315 | 227 | 0 | 16 | 0 |
| `tests/test_kratos_stage_processes.py` | 355 | 211 | 0 | 40 | 0 |
| 114 smaller files | 15,193 | 9,513 | 16 | 1227 | 42 |

### Benchmarks and test runner (`benchmarks/`, `tools/`)

| Module | Lines | Code | Classes | Functions | Methods |
|---|--:|--:|--:|--:|--:|
| `benchmarks/cases.py` | 328 | 239 | 0 | 29 | 0 |
| `benchmarks/runner.py` | 181 | 134 | 4 | 6 | 0 |
| `tools/test.py` | 145 | 99 | 1 | 6 | 0 |
| `benchmarks/models.py` | 116 | 75 | 0 | 5 | 0 |
| `benchmarks/__main__.py` | 52 | 36 | 0 | 1 | 0 |
| `benchmarks/__init__.py` | 0 | 0 | 0 | 0 | 0 |

### Browser app (`frontend/js`)

| Module | Lines | Code | Functions |
|---|--:|--:|--:|
| `frontend/js/patches.js` | 3,781 | 2,760 | 420 |
| `frontend/js/viewport.js` | 2,400 | 1,669 | 229 |
| `frontend/js/model.js` | 1,664 | 1,271 | 255 |
| `frontend/js/results.js` | 936 | 656 | 92 |
| `frontend/js/beams.js` | 538 | 415 | 75 |
| `frontend/js/soil-volume-dialog.js` | 453 | 340 | 50 |
| `frontend/js/anchors.js` | 431 | 331 | 64 |
| `frontend/js/loads.js` | 365 | 317 | 46 |
| `frontend/js/results-plot.js` | 476 | 307 | 59 |
| `frontend/js/material-sets.js` | 358 | 299 | 59 |
| `frontend/js/draw-input.js` | 330 | 278 | 22 |
| `frontend/js/stages.js` | 468 | 262 | 54 |
| `frontend/js/mesh-labels.js` | 397 | 259 | 42 |
| `frontend/js/interfaces.js` | 325 | 242 | 43 |
| `frontend/js/normal-loads.js` | 323 | 241 | 44 |
| `frontend/js/mdpa-import-dialog.js` | 310 | 240 | 28 |
| `frontend/js/mesh-settings.js` | 284 | 239 | 35 |
| `frontend/js/unit-table.js` | 242 | 235 | 0 |
| `frontend/js/results-view.js` | 334 | 232 | 32 |
| `frontend/js/ruler.js` | 302 | 201 | 23 |
| `frontend/js/results-render.js` | 344 | 200 | 14 |
| `frontend/js/part-colors.js` | 267 | 182 | 43 |
| `frontend/js/node-parts.js` | 253 | 181 | 36 |
| `frontend/js/property-sets.js` | 236 | 178 | 23 |
| `frontend/js/canvas-renderer.js` | 271 | 177 | 18 |
| `frontend/js/orbit.js` | 167 | 117 | 13 |
| `frontend/js/import-dialog.js` | 126 | 104 | 16 |
| `frontend/js/history.js` | 142 | 96 | 28 |
| `frontend/js/export.js` | 138 | 84 | 13 |
| `frontend/js/zip.js` | 112 | 82 | 10 |
| `frontend/js/units.js` | 113 | 77 | 20 |
| `frontend/js/material-library.js` | 83 | 68 | 12 |
| `frontend/js/calculate.js` | 112 | 60 | 10 |
| `frontend/js/api.js` | 90 | 59 | 15 |
| `frontend/js/deck.js` | 94 | 48 | 12 |
| `frontend/js/download.js` | 80 | 45 | 12 |
| `frontend/js/water-command.js` | 72 | 39 | 3 |
| `frontend/js/buffers.js` | 71 | 37 | 4 |
| `frontend/js/script-command.js` | 53 | 26 | 3 |

### Frozen shell (`frontend/base/js`)

| Module | Lines | Code | Functions |
|---|--:|--:|--:|
| `frontend/base/js/dialogs.js` | 1,293 | 916 | 177 |
| `frontend/base/js/data.js` | 956 | 749 | 54 |
| `frontend/base/js/explorer.js` | 385 | 257 | 42 |
| `frontend/base/js/app.js` | 335 | 236 | 28 |
| `frontend/base/js/ui.js` | 317 | 177 | 34 |
| `frontend/base/js/orbit.js` | 193 | 117 | 13 |
| `frontend/base/js/toolbars.js` | 166 | 115 | 24 |
| `frontend/base/js/command.js` | 139 | 100 | 15 |
| `frontend/base/js/menubar.js` | 130 | 87 | 14 |

### Browser tests (`frontend/tests`, JS)

| Module | Lines | Code | Functions |
|---|--:|--:|--:|
| `frontend/tests/test-results.js` | 1,207 | 983 | 271 |
| `frontend/tests/test-model.js` | 1,059 | 866 | 216 |
| `frontend/tests/test-patches.js` | 979 | 825 | 253 |
| `frontend/tests/test-loads.js` | 596 | 495 | 134 |
| `frontend/tests/test-viewport.js` | 670 | 455 | 100 |
| `frontend/tests/test-normal-loads.js` | 492 | 405 | 113 |
| `frontend/tests/test-frozen-ui.js` | 443 | 390 | 80 |
| `frontend/tests/test-stages.js` | 521 | 383 | 99 |
| `frontend/tests/test-results-plot.js` | 443 | 352 | 90 |
| `frontend/tests/test-results-render.js` | 481 | 315 | 61 |
| `frontend/tests/test-viewport-live.js` | 357 | 315 | 82 |
| `frontend/tests/test-toolbar.js` | 385 | 314 | 88 |
| `frontend/tests/test-interfaces.js` | 348 | 291 | 70 |
| `frontend/tests/test-mdpa-import.js` | 299 | 245 | 56 |
| `frontend/tests/test-patches-results.js` | 270 | 238 | 68 |
| `frontend/tests/test-part-colors.js` | 292 | 225 | 40 |
| `frontend/tests/test-beams.js` | 255 | 224 | 46 |
| `frontend/tests/test-anchors.js` | 242 | 211 | 37 |
| `frontend/tests/test-water.js` | 295 | 209 | 53 |
| `frontend/tests/test-import-dialogs.js` | 237 | 208 | 55 |
| `frontend/tests/test-results-view.js` | 229 | 202 | 46 |
| `frontend/tests/test-patches-stages.js` | 229 | 200 | 54 |
| `frontend/tests/test-mesh-labels.js` | 239 | 182 | 31 |
| `frontend/tests/test-node-parts.js` | 263 | 178 | 48 |
| `frontend/tests/test-draw-pointer.js` | 197 | 173 | 40 |
| 30 smaller files | 3,359 | 2,666 | 620 |

### Browser test runners (`frontend/tests`, Python)

| Module | Lines | Code | Classes | Functions | Methods |
|---|--:|--:|--:|--:|--:|
| `frontend/tests/syntax_check.py` | 197 | 136 | 0 | 4 | 0 |
| `frontend/tests/run_headless.py` | 211 | 128 | 0 | 3 | 0 |
