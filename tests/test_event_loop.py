"""No route does slow work on the event loop (plan sec 9, finding F10).

An `async def` route runs on the one event loop every request shares, so anything slow in
it -- parsing a deck, running a script, zipping a run -- stalls every other request until
it is done, `/api/health` included. Such a route has to hand the work to a thread
(`asyncio.to_thread`) or to the gmsh worker (`gmsh_worker.run`); a plain `def` route is run
on FastAPI's thread pool already.

The cheap ones -- a validation and a store write, nothing that grows with the model --
are listed by name, so adding a slow `async def` route fails here rather than in a user's
frozen browser tab.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
SOURCES = [BACKEND / "main.py", *sorted((BACKEND / "routes").glob("*.py"))]
"""Where routes are declared: the app's own two in `main.py`, the rest in a router each."""

CHEAP = {
    "health", "get_project", "put_project", "reset_project", "new_project",
    "patch_layers", "put_water", "patch_materials", "patch_structures", "patch_conditions",
    "patch_stages", "patch_lines", "patch_body", "delete_body",
    "patch_dimension", "clear_custom_parts", "delete_geometry_part",
    "index",
}
"""Validation and a store write. `patch_dimension` translates loads and walls, which is
proportional to how many there are -- tens, not the mesh."""

OFFLOADS = ("to_thread", "run", "run_mesh_job")
"""`asyncio.to_thread(...)`, `gmsh_worker.run(...)`, and `run_mesh_job(...)`
(`backend/routes/common.py`), which is `gmsh_worker.run` for a mesh job."""


def _routes() -> list[ast.AsyncFunctionDef | ast.FunctionDef]:
    nodes = [node for source in SOURCES
             for node in ast.parse(source.read_text(encoding="utf-8")).body]
    out = []
    for node in nodes:
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for decorator in node.decorator_list:
            if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                    and isinstance(decorator.func.value, ast.Name)
                    and decorator.func.value.id in {"app", "router"}
                    and decorator.func.attr in {"get", "post", "put", "patch", "delete"}):
                out.append(node)
    return out


def _offloads(function: ast.AsyncFunctionDef) -> bool:
    for node in ast.walk(function):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            called = node.value.func
            name = (called.attr if isinstance(called, ast.Attribute)
                    else called.id if isinstance(called, ast.Name) else None)
            if name in OFFLOADS:
                return True
    return False


def test_the_route_table_was_found():
    assert len(_routes()) > 30


def test_every_async_route_is_cheap_or_hands_its_work_off():
    slow = [route.name for route in _routes()
            if isinstance(route, ast.AsyncFunctionDef)
            and route.name not in CHEAP and not _offloads(route)]

    assert slow == [], (
        "async routes doing their work on the event loop: " + ", ".join(slow)
        + ". Make them plain `def`, or await asyncio.to_thread / gmsh_worker.run.")


def test_the_cheap_list_names_only_routes_that_exist():
    names = {route.name for route in _routes()}

    assert CHEAP <= names, sorted(CHEAP - names)
