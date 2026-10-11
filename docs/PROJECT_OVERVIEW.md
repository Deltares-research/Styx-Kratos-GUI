# Project overview — code size

Snapshot of the source tree on 2026-10-09 (after the wall-plot window, commit `93205af`):
lines of code, classes and functions per module, split into backend (Python server) and
frontend (browser app).

The rows of the example-case files, which left the repository on 2026-10-11, are
removed; the totals are still the snapshot's.

Styx is a Deltares/Kratos geotechnical modeller: build a soil and excavation model, mesh it
with Gmsh, export and run a Kratos GeoMechanics deck in construction phases, and read the
results back in a Plaxis-style Results mode. How the pieces fit is in
[ARCHITECTURE.md](ARCHITECTURE.md); what works and what does not is in
[FEATURES.md](FEATURES.md); how to install and run it is in
[INSTALLATION.md](INSTALLATION.md).

## How it is counted

- **Lines** = every physical line. **Code** = lines minus blank lines minus comment-only lines (Python docstrings count as comments).
- **Python**: parsed with `ast`. *Classes* include nested classes; *Functions* are module-level and nested functions; *Methods* are functions defined directly in a class body.
- **JavaScript**: counted from source text with comments, strings and regular-expression literals stripped. The frontend is plain ES5 (IIFE modules hung off a global `App` namespace) with no `class`, arrow functions or method shorthand, so it has 0 classes and every function is a `function` keyword. *Functions* counts every `function` keyword left after stripping: named declarations, anonymous `function (...)` expressions (callbacks, object-literal members) and `function(...)` written without the space. JS figures are close estimates, not parser-exact.
- Excluded: `vendor/` (three.js), `htmlcov*/`, virtual environments, `__pycache__`, and the local-only `plan/`, `tools/`, `graphify-out/` folders.
- **Comparing with the previous snapshot (2026-10-08):** lines, code and comments are counted the same way and compare directly. JS function counts are a few percent higher than that snapshot showed for the same files, because `function(` without a space is now included. Recounted this way, the previous snapshot had 1,750 live, 494 shell and 1,976 test functions, against the 1,743, 471 and 1,898 it printed.

## What changed since the previous snapshot

| Area | Change | Code lines |
|---|---|--:|
| `core/results/members.py` (new) | A structural member's results as curves along it — the data behind the wall-plot window | +83 |
| `core/results/runs.py`, `main.py` | `stage_members`, `member_profiles`, and the two `/members` routes | +66 |
| `frontend/js/results-plot.js` (new) | `results plot …` command and the SVG figure, DOM-free and tested headless | +356 |
| `frontend/js/patches.js`, `results.js`, `frontend/css/live.css` | The plot window and its buttons; legend Min/Max limits; legend moved clear of the ruler | +204 |
| `tests/test_result_members.py` (new) | The plot data against Kratos' own run (the orange benchmark line) | +184 |
| `frontend/tests/test-results-plot.js` (new), `test-results.js` | The figure, the command and the legend limits | +404 |

## Overview

| Area | Language | Files | Lines | Code | Classes | Functions | Methods | Functions + methods |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| Backend — Application (`core/`, `backend/`) | Python | 34 | 13,313 | 7,143 | 78 | 389 | 87 | 476 |
| Backend — Tests (`tests/`) | Python | 52 | 18,969 | 11,201 | 9 | 1468 | 16 | 1484 |
| Frontend — Live app JS (`frontend/js`) | JavaScript | 34 | 16,256 | 11,698 | 0 | 1839 | 0 | 1839 |
| Frontend — Shell JS (`frontend/base/js`) | JavaScript | 10 | 4,171 | 3,412 | 0 | 494 | 0 | 494 |
| Frontend — Tests (`frontend/tests`, JS) | JavaScript | 39 | 11,419 | 9,090 | 0 | 2087 | 0 | 2087 |
| Frontend — Test runners (`frontend/tests`, Python) | Python | 2 | 365 | 232 | 0 | 7 | 0 | 7 |
| Frontend — Stylesheets (`frontend/base/css`, `frontend/css`) | CSS | 4 | 1,167 | 971 | 0 | 0 | 0 | 0 |
| Frontend — HTML pages | HTML | 3 | 498 | 392 | 0 | 0 | 0 | 0 |
| **Backend total** | | **86** | **32,282** | **18,344** | **87** | **1857** | **103** | **1960** |
| **Frontend total** | | **92** | **33,876** | **25,795** | **0** | **4427** | **0** | **4427** |
| **Grand total** | | **178** | **66,158** | **44,139** | **87** | **6284** | **103** | **6387** |

### Production code vs tests

| Scope | Files | Lines | Code | Classes | Functions + methods |
|---|--:|--:|--:|--:|--:|
| Backend application | 34 | 13,313 | 7,143 | 78 | 476 |
| Frontend application (JS + CSS + HTML) | 51 | 22,092 | 16,473 | 0 | 2333 |
| **Production total** | 85 | 35,405 | 23,616 | 78 | 2809 |
| Backend tests | 52 | 18,969 | 11,201 | 9 | 1484 |
| Frontend tests | 41 | 11,784 | 9,322 | 0 | 2094 |
| **Test total** | 93 | 30,753 | 20,523 | 9 | 3578 |
| **Everything** | 178 | 66,158 | 44,139 | 87 | 6387 |

## Backend (Python: `core/`, `backend/`)

### Application modules — `core/`, `backend/`

| Module | Lines | Code | Comments/docs | Blank | Classes | Functions | Methods |
|---|--:|--:|--:|--:|--:|--:|--:|
| `model/schemas.py` | 1,949 | 1,036 | 636 | 277 | 41 | 4 | 63 |
| `kratos/export.py` | 1,670 | 946 | 517 | 207 | 2 | 49 | 0 |
| `geometry/build.py` | 1,253 | 683 | 378 | 192 | 2 | 37 | 0 |
| `main.py` | 918 | 529 | 231 | 158 | 0 | 43 | 0 |
| `geometry/meshing.py` | 594 | 412 | 110 | 72 | 3 | 18 | 2 |
| `kratos/processes.py` | 795 | 395 | 297 | 103 | 1 | 22 | 0 |
| `kratos/mdpa_import.py` | 483 | 282 | 133 | 68 | 4 | 15 | 5 |
| `results/runs.py` | 551 | 281 | 153 | 117 | 3 | 29 | 0 |
| `kratos/materials.py` | 479 | 224 | 192 | 63 | 1 | 8 | 0 |
| `geometry/tessellate.py` | 387 | 214 | 107 | 66 | 2 | 12 | 2 |
| `kratos/interfaces.py` | 364 | 204 | 92 | 68 | 3 | 16 | 0 |
| `kratos/deck.py` | 335 | 193 | 78 | 64 | 1 | 17 | 0 |
| `results/gid.py` | 326 | 184 | 83 | 59 | 5 | 3 | 9 |
| `results/fields.py` | 388 | 184 | 122 | 82 | 2 | 15 | 0 |
| `run/calculate.py` | 373 | 170 | 135 | 68 | 2 | 13 | 0 |
| `results/mesh.py` | 283 | 144 | 94 | 45 | 0 | 10 | 0 |
| `model/phases.py` | 248 | 105 | 94 | 49 | 1 | 8 | 0 |
| `model/seed.py` | 136 | 94 | 30 | 12 | 0 | 2 | 0 |
| `model/walls.py` | 173 | 93 | 45 | 35 | 0 | 9 | 0 |
| `launcher.py` | 128 | 91 | 8 | 29 | 0 | 9 | 0 |
| `model/loads.py` | 203 | 88 | 74 | 41 | 0 | 9 | 0 |
| `results/members.py` | 152 | 83 | 40 | 29 | 2 | 6 | 1 |
| `gmsh_worker.py` | 150 | 76 | 33 | 41 | 0 | 12 | 0 |
| `script.py` | 158 | 74 | 59 | 25 | 1 | 4 | 0 |
| `geometry/creator.py` | 104 | 68 | 11 | 25 | 0 | 2 | 0 |
| `results/parts.py` | 134 | 45 | 63 | 26 | 1 | 3 | 1 |
| `run/runner.py` | 112 | 40 | 44 | 28 | 1 | 3 | 4 |
| `geometry/importer.py` | 60 | 37 | 10 | 13 | 0 | 1 | 0 |
| `store.py` | 37 | 14 | 11 | 12 | 0 | 4 | 0 |
| `kratos/node_parts.py` | 31 | 10 | 13 | 8 | 0 | 2 | 0 |
| `__init__.py` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `routes/__init__.py` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **Total (34 files)** | **13,313** | **7,143** | **4,044** | **2,126** | **78** | **389** | **87** |

### Tests — `tests`

| Module | Lines | Code | Comments/docs | Blank | Classes | Functions | Methods |
|---|--:|--:|--:|--:|--:|--:|--:|
| `test_api.py` | 1,644 | 1,029 | 208 | 407 | 0 | 108 | 0 |
| `test_schemas.py` | 1,530 | 943 | 190 | 397 | 0 | 161 | 0 |
| `test_kratos.py` | 1,216 | 754 | 178 | 284 | 0 | 110 | 0 |
| `test_mdpa_import.py` | 680 | 430 | 80 | 170 | 0 | 44 | 0 |
| `test_deck.py` | 556 | 383 | 49 | 124 | 0 | 43 | 0 |
| `test_kratos_interfaces.py` | 639 | 367 | 123 | 149 | 0 | 52 | 0 |
| `test_build_2d.py` | 528 | 306 | 95 | 127 | 0 | 42 | 0 |
| `test_kratos_3d.py` | 500 | 285 | 72 | 143 | 0 | 45 | 0 |
| `test_result_mesh.py` | 442 | 281 | 55 | 106 | 0 | 30 | 0 |
| `test_results.py` | 480 | 281 | 54 | 145 | 0 | 40 | 0 |
| `test_calculate.py` | 485 | 261 | 89 | 135 | 3 | 35 | 7 |
| `test_result_fields.py` | 453 | 238 | 86 | 129 | 0 | 33 | 0 |
| `test_build.py` | 421 | 235 | 82 | 104 | 0 | 27 | 0 |
| `test_meshing_2d.py` | 377 | 232 | 56 | 89 | 0 | 33 | 0 |
| `test_load_translation.py` | 443 | 226 | 65 | 152 | 0 | 37 | 0 |
| `test_export_golden.py` | 367 | 223 | 61 | 83 | 0 | 30 | 0 |
| `test_build_3d.py` | 316 | 198 | 38 | 80 | 0 | 22 | 0 |
| `test_kratos_stage_processes.py` | 320 | 190 | 50 | 80 | 0 | 37 | 0 |
| `test_tessellate.py` | 306 | 187 | 46 | 73 | 0 | 23 | 0 |
| `test_result_members.py` | 342 | 184 | 51 | 107 | 0 | 32 | 0 |
| `test_gid_results.py` | 310 | 183 | 43 | 84 | 0 | 23 | 0 |
| `test_tessellate_2d.py` | 263 | 169 | 35 | 59 | 0 | 19 | 0 |
| `test_phases.py` | 274 | 151 | 62 | 61 | 0 | 26 | 0 |
| `test_creator.py` | 187 | 148 | 3 | 36 | 0 | 9 | 0 |
| `test_kratos_units.py` | 296 | 146 | 79 | 71 | 0 | 27 | 0 |
| `test_kratos_normal_loads.py` | 227 | 145 | 31 | 51 | 0 | 18 | 0 |
| `test_kratos_stages.py` | 237 | 128 | 49 | 60 | 0 | 24 | 0 |
| `test_result_parts.py` | 233 | 127 | 42 | 64 | 0 | 15 | 0 |
| `test_interfaces.py` | 234 | 123 | 49 | 62 | 0 | 18 | 0 |
| `test_mesh_parts.py` | 186 | 121 | 26 | 39 | 0 | 17 | 0 |
| `test_meshing.py` | 155 | 119 | 1 | 35 | 0 | 11 | 0 |
| `test_wall_translation.py` | 206 | 109 | 33 | 64 | 0 | 16 | 0 |
| `test_phase_parity.py` | 190 | 107 | 47 | 36 | 0 | 9 | 0 |
| `test_section_structures_3d.py` | 192 | 107 | 36 | 49 | 0 | 18 | 0 |
| `test_script.py` | 174 | 106 | 25 | 43 | 0 | 14 | 0 |
| `test_kratos_solver.py` | 187 | 104 | 31 | 52 | 0 | 16 | 0 |
| `test_node_parts.py` | 156 | 103 | 18 | 35 | 0 | 9 | 0 |
| `mdpa.py` | 134 | 100 | 10 | 24 | 3 | 5 | 3 |
| `frozen.py` | 131 | 96 | 14 | 21 | 0 | 8 | 0 |
| `test_water_level.py` | 159 | 91 | 26 | 42 | 0 | 15 | 0 |
| `test_mesh_labels.py` | 146 | 88 | 19 | 39 | 0 | 11 | 0 |
| `test_model_extent.py` | 102 | 53 | 17 | 32 | 0 | 10 | 0 |
| `test_parity.py` | 98 | 49 | 22 | 27 | 0 | 11 | 0 |
| `test_launcher.py` | 63 | 41 | 4 | 18 | 3 | 0 | 6 |
| `test_importer.py` | 31 | 24 | 4 | 3 | 0 | 1 | 0 |
| `__init__.py` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **Total (52 files)** | **18,969** | **11,201** | **3,092** | **4,676** | **9** | **1468** | **16** |

## Frontend (browser)

### Live application modules — `frontend/js`

| Module | Lines | Code | Comments | Blank | Functions |
|---|--:|--:|--:|--:|--:|
| `patches.js` | 3,604 | 2,617 | 648 | 339 | 400 |
| `viewport.js` | 2,400 | 1,669 | 493 | 238 | 229 |
| `model.js` | 1,633 | 1,259 | 251 | 123 | 242 |
| `results.js` | 914 | 642 | 170 | 102 | 91 |
| `beams.js` | 532 | 411 | 69 | 52 | 72 |
| `results-plot.js` | 476 | 356 | 55 | 65 | 67 |
| `soil-volume-dialog.js` | 453 | 340 | 59 | 54 | 50 |
| `anchors.js` | 428 | 332 | 52 | 44 | 63 |
| `loads.js` | 362 | 315 | 19 | 28 | 46 |
| `draw-input.js` | 328 | 280 | 10 | 38 | 22 |
| `phases.js` | 468 | 262 | 141 | 65 | 54 |
| `mesh-labels.js` | 397 | 259 | 84 | 54 | 42 |
| `interfaces.js` | 322 | 243 | 45 | 34 | 42 |
| `mdpa-import-dialog.js` | 310 | 240 | 31 | 39 | 28 |
| `normal-loads.js` | 322 | 240 | 46 | 36 | 44 |
| `mesh-settings.js` | 284 | 239 | 22 | 23 | 35 |
| `results-view.js` | 332 | 232 | 54 | 46 | 32 |
| `ruler.js` | 302 | 201 | 62 | 39 | 23 |
| `results-render.js` | 344 | 200 | 100 | 44 | 14 |
| `part-colors.js` | 267 | 182 | 53 | 32 | 43 |
| `node-parts.js` | 253 | 181 | 49 | 23 | 36 |
| `canvas-renderer.js` | 271 | 177 | 50 | 44 | 18 |
| `orbit.js` | 167 | 117 | 29 | 21 | 13 |
| `import-dialog.js` | 126 | 104 | 2 | 20 | 16 |
| `history.js` | 142 | 96 | 25 | 21 | 28 |
| `zip.js` | 112 | 82 | 15 | 15 | 10 |
| `export.js` | 132 | 80 | 36 | 16 | 13 |
| `calculate.js` | 112 | 60 | 35 | 17 | 10 |
| `api.js` | 90 | 59 | 16 | 15 | 15 |
| `material-library.js` | 58 | 56 | 2 | 0 | 10 |
| `deck.js` | 94 | 48 | 34 | 12 | 12 |
| `download.js` | 80 | 45 | 22 | 13 | 12 |
| `buffers.js` | 71 | 37 | 20 | 14 | 4 |
| `water-command.js` | 70 | 37 | 20 | 13 | 3 |
| **Total (34 files)** | **16,256** | **11,698** | **2,819** | **1,739** | **1839** |

### Shell modules — `frontend/base/js`

The frozen UI shell, served at `/js`; `frontend/js` swaps in its own viewport and patches the rest.

| Module | Lines | Code | Comments | Blank | Functions |
|---|--:|--:|--:|--:|--:|
| `dialogs.js` | 1,105 | 912 | 94 | 99 | 177 |
| `data.js` | 881 | 749 | 74 | 58 | 54 |
| `viewport.js` | 817 | 662 | 66 | 89 | 93 |
| `explorer.js` | 319 | 257 | 24 | 38 | 42 |
| `app.js` | 299 | 236 | 22 | 41 | 28 |
| `ui.js` | 225 | 177 | 24 | 24 | 34 |
| `orbit.js` | 146 | 117 | 12 | 17 | 13 |
| `toolbars.js` | 147 | 115 | 10 | 22 | 24 |
| `command.js` | 120 | 100 | 5 | 15 | 15 |
| `menubar.js` | 112 | 87 | 11 | 14 | 14 |
| **Total (10 files)** | **4,171** | **3,412** | **342** | **417** | **494** |

### Tests — `frontend/tests`

| Module | Lines | Code | Comments | Blank | Functions |
|---|--:|--:|--:|--:|--:|
| `test-results.js` | 1,079 | 872 | 91 | 116 | 236 |
| `test-model.js` | 1,002 | 813 | 83 | 106 | 205 |
| `test-patches.js` | 794 | 663 | 54 | 77 | 195 |
| `fixtures/phase-cases.js` | 591 | 579 | 10 | 2 | 0 |
| `test-loads.js` | 590 | 490 | 37 | 63 | 133 |
| `test-viewport.js` | 670 | 455 | 134 | 81 | 100 |
| `test-phases.js` | 511 | 376 | 63 | 72 | 97 |
| `test-results-plot.js` | 443 | 352 | 31 | 60 | 90 |
| `test-normal-loads.js` | 405 | 326 | 39 | 40 | 96 |
| `test-results-render.js` | 481 | 315 | 68 | 98 | 61 |
| `test-toolbar.js` | 373 | 304 | 28 | 41 | 87 |
| `test-mdpa-import.js` | 299 | 245 | 14 | 40 | 56 |
| `test-part-colors.js` | 292 | 225 | 20 | 47 | 40 |
| `test-mesh-labels.js` | 284 | 219 | 25 | 40 | 38 |
| `test-beams.js` | 241 | 210 | 7 | 24 | 45 |
| `test-water.js` | 294 | 208 | 48 | 38 | 53 |
| `test-interfaces.js` | 241 | 201 | 12 | 28 | 44 |
| `test-anchors.js` | 225 | 195 | 8 | 22 | 35 |
| `test-node-parts.js` | 263 | 178 | 34 | 51 | 48 |
| `test-ruler.js` | 215 | 167 | 11 | 37 | 43 |
| `test-dock.js` | 204 | 164 | 16 | 24 | 30 |
| `test-download.js` | 170 | 149 | 6 | 15 | 48 |
| `test-export.js` | 152 | 138 | 4 | 10 | 40 |
| `test-calculate.js` | 145 | 134 | 1 | 10 | 42 |
| `test-canvas-renderer.js` | 174 | 128 | 24 | 22 | 19 |
| `test-draw-input.js` | 128 | 102 | 6 | 20 | 28 |
| `test-mesh-settings.js` | 130 | 102 | 13 | 15 | 25 |
| `test-deck.js` | 131 | 98 | 11 | 22 | 18 |
| `test-material-library.js` | 127 | 98 | 18 | 11 | 18 |
| `test-api.js` | 120 | 91 | 10 | 19 | 29 |
| `test-buffers.js` | 102 | 70 | 15 | 17 | 13 |
| `test-soil-surface.js` | 108 | 69 | 22 | 17 | 11 |
| `test-layout.js` | 69 | 66 | 0 | 3 | 6 |
| `harness.js` | 81 | 59 | 10 | 12 | 17 |
| `test-empty-layers.js` | 58 | 58 | 0 | 0 | 15 |
| `test-water-command.js` | 80 | 58 | 8 | 14 | 12 |
| `test-zip.js` | 70 | 55 | 6 | 9 | 10 |
| `test-import.js` | 41 | 33 | 2 | 6 | 4 |
| **Total (39 files)** | **11,419** | **9,090** | **998** | **1,331** | **2087** |

Test runners:

| Module | Lines | Code | Comments/docs | Blank | Classes | Functions | Methods |
|---|--:|--:|--:|--:|--:|--:|--:|
| `syntax_check.py` | 198 | 135 | 38 | 25 | 0 | 4 | 0 |
| `run_headless.py` | 167 | 97 | 48 | 22 | 0 | 3 | 0 |
| **Total (2 files)** | **365** | **232** | **86** | **47** | **0** | **7** | **0** |

### Stylesheets

| File | Lines | Code | Comments | Blank |
|---|--:|--:|--:|--:|
| `css/components.css` | 442 | 398 | 25 | 19 |
| `frontend/css/live.css` | 405 | 308 | 65 | 32 |
| `css/layout.css` | 238 | 206 | 16 | 16 |
| `css/tokens.css` | 82 | 59 | 12 | 11 |
| **Total (4 files)** | **1,167** | **971** | **118** | **78** |

### HTML pages

| File | Lines | Code | Comments | Blank |
|---|--:|--:|--:|--:|
| `frontend/index.html` | 212 | 151 | 33 | 28 |
| `frontend/tests/index.html` | 140 | 126 | 6 | 8 |
| `index.html` | 146 | 115 | 8 | 23 |
| **Total (3 files)** | **498** | **392** | **47** | **59** |
