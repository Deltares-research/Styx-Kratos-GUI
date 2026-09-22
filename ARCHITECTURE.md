# Architecture at a glance

A Deltares/Kratos-branded geotechnical modeller: build soil/excavation models,
mesh them with Gmsh, export Kratos MultiPhysics `.mdpa` decks.

## Backend

| Layer | What |
|---|---|
| Framework | FastAPI 0.115.6 + Uvicorn 0.34.0 |
| Validation | Pydantic 2.10.4 — `Project` is the single source of truth |
| Geometry/mesh | Gmsh 4.13.1 (OpenCASCADE kernel) |
| Numerics | NumPy 2.2.1 |
| State | In-memory single project (`server/app/store.py`) — no DB, no auth |
| Concurrency | `ProcessPoolExecutor(max_workers=1)` (`server/app/gmsh_worker.py`) |
| Tests | pytest 8.3.4 + httpx TestClient, ~17k lines, 1158 cases. `python -m pytest -q` from `server/` |

## Frontend

| Layer | What |
|---|---|
| 3D | three.js (vendored, r150-ish) — only dependency |
| Build | **None** — no npm, no bundler, no transpiler |
| Style | ES5 IIFE modules on a global `App` namespace, ~25 `<script>` tags |
| Fallback renderer | Hand-written CPU painter (`live/js/canvas-renderer.js`) |
| HTTP | `fetch` wrapper (`live/js/api.js`) |
| Tests | ~90-line browser harness (`live/tests/`), 32 files. The DOM-free suites also run headless: `python live/tests/run_headless.py` (quickjs), 142 cases |

## Core pipeline

| Step | Module | Note |
|---|---|---|
| 1. Edit | `server/app/schemas.py` | Every PATCH re-validates the *whole* project |
| 2. Build | `server/app/build.py` | Boxes → boolean fragment → cut pit → embed structures |
| 3. Draw | `server/app/tessellate.py` | OCC `importStl()`, ~0.1 s — not an FE mesh |
| 4. Mesh | `server/app/meshing.py` | Real tet/tri mesh, re-derived from geometry |
| 5. Split | `server/app/interfaces.py` | Duplicate nodes, zero-thickness contacts |
| 6. Export | `server/app/kratos.py` | `.mdpa` + `MaterialParameters.json` + `ProjectParameters.json` |
| 7. Solve | `server/app/calculate.py` | Kratos in a subprocess, in a run directory of its own |

## Three ideas that carry the design

| Idea | Why |
|---|---|
| Gmsh in a 1-worker subprocess | It's a process-global singleton; also contains OCC hard crashes |
| Frozen `js/` + live `live/js/` | Server mounts frozen files in place; only `viewport.js` is swapped, rest is monkey-patched |
| Part keys | One string = gmsh physical group + `userData.key` + tree `obj:` + `OBJECT_PROPS` key |
