"""How the app is put together: which module declares each route, and the middleware order.

`backend/main.py` only assembles the app. Every route of the HTTP API lives in the router
of its group (`backend/routes/`), the groups `docs/developer/ARCHITECTURE.md` lists, so a
reader can go from a URL to its file. The table below is that mapping; a route outside it
fails here, which is what keeps the next route from landing in `main.py` again.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from backend.main import app
from core import gmsh_worker, session
from core.kratos.writer import ExportError
from core.geometry.meshing import MeshingError
from core.model.schemas import MeshRequest
from core.model.templates import seed_project
from tests.api.served import api_routes

ROUTES = Path(__file__).resolve().parents[2] / "backend" / "routes"

OWNERS = [
    # The exact paths first: they would otherwise fall under a prefix below.
    (lambda path: path in ("/", "/api/health"), "backend.main"),
    (lambda path: path == "/api/project/custom_parts", "backend.routes.geometry"),
    (lambda path: path.startswith("/api/project"), "backend.routes.project"),
    (lambda path: path.startswith("/api/geometry"), "backend.routes.geometry"),
    (lambda path: path.startswith("/api/mesh"), "backend.routes.mesh"),
    (lambda path: path.startswith(("/api/export/", "/api/import/")), "backend.routes.decks"),
    (lambda path: path == "/api/calculate", "backend.routes.decks"),
    (lambda path: path.startswith("/api/results/"), "backend.routes.results"),
    (lambda path: path.startswith("/api/files/"), "backend.routes.files"),
]
"""Which module a path belongs to, first match wins."""


def owner(path: str) -> str | None:
    return next((module for matches, module in OWNERS if matches(path)), None)


API_ROUTES = api_routes(app)


@pytest.mark.parametrize("route", API_ROUTES,
                         ids=[f"{','.join(sorted(r.methods))} {r.path}" for r in API_ROUTES])
def test_each_route_lives_in_the_module_of_its_group(route):
    expected = owner(route.path)

    assert expected is not None, f"{route.path} is in no group of the HTTP API table"
    assert route.endpoint.__module__ == expected


def test_every_router_module_is_included():
    """A router that is written but never included serves nothing, and no route test
    would notice its routes are gone from the table they are checked against."""
    serving = {route.endpoint.__module__ for route in API_ROUTES}
    modules = {f"backend.routes.{path.stem}" for path in ROUTES.glob("*.py")
               if path.stem not in ("__init__", "common")}

    assert modules <= serving, sorted(modules - serving)


def test_the_middleware_runs_host_check_then_no_cache_then_gzip():
    """Starlette makes the middleware added last the outermost, and `user_middleware`
    lists them outermost first. The Host/Origin check has to run before anything else
    sees the request (`test_security.py`)."""
    names = [m.kwargs["dispatch"].__name__ if "dispatch" in m.kwargs else m.cls.__name__
             for m in app.user_middleware]

    assert names == ["only_this_browser_tab", "do_not_cache_sources", "GZipMiddleware"]


# ── The helpers the routes share (backend/routes/common.py) ─────────────────

def test_refusals_lets_an_edit_that_succeeds_through():
    from backend.routes.common import refusals

    with refusals():
        project = seed_project()

    assert project == seed_project()


def test_refusals_turns_a_validation_error_into_a_request_error_field_by_field():
    """The 422 a bad request body gets, not the 500 a raw `ValidationError` would be."""
    from backend.routes.common import refusals
    from core.model.schemas import Project

    payload = seed_project().model_dump()
    payload["layers"] = "not a list"

    with pytest.raises(RequestValidationError) as refused, refusals():
        Project.model_validate(payload)
    assert [e["loc"] for e in refused.value.errors()] == [("layers",)]
    assert isinstance(refused.value.__cause__, ValidationError)


@pytest.mark.parametrize(("failure", "status"), [
    (session.EditRefused("a stage still uses it"), 422),
    (session.DeckReadOnly("Edit the deck"), 422),
    (session.UnknownPart("no custom part with key 'x'"), 404),
], ids=["refused", "deck", "unknown"])
def test_refusals_answers_a_refused_edit_with_its_reason(failure, status):
    from backend.routes.common import refusals

    with pytest.raises(HTTPException) as answered, refusals():
        raise failure
    assert (answered.value.status_code, answered.value.detail) == (status, str(failure))


# ── Every edit is core.session's (plan/active/cli-plan.md M0) ───────────────

EDITS = {
    "patch_layers": "replace_layers",
    "put_water": "set_water",
    "patch_materials": "replace_materials",
    "patch_structures": "replace_structures",
    "patch_stages": "replace_stages",
    "seed_default_stages": "default_stages",
    "patch_dimension": "set_dimension",
    "patch_units": "set_units",
    "clear_custom_parts": "without_custom_parts",
    "delete_geometry_part": "without_custom_part",
    "create_geometry": "with_created_part",
    "import_geometry": "with_imported_part",
}
"""Each route that edits the project, and the `core.session` function that makes the edit.
The command line makes the same edits through the same functions, so the GUI and the
terminal cannot come to different answers for one change."""


def _route_functions() -> dict[str, ast.AST]:
    return {node.name: node for path in sorted(ROUTES.glob("*.py"))
            for node in ast.parse(path.read_text(encoding="utf-8")).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _session_calls(function: ast.AST) -> set[str]:
    return {node.func.attr for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "session"}


@pytest.mark.parametrize(("route", "edit"), sorted(EDITS.items()))
def test_each_edit_route_makes_its_edit_through_core_session(route, edit):
    functions = _route_functions()

    assert route in functions, f"no route function {route} in backend/routes/"
    assert edit in _session_calls(functions[route])
    assert hasattr(session, edit)


def test_no_route_puts_a_project_together_itself():
    """A route that writes into a project payload is making an edit `core.session` does
    not know about -- one the command line would then make differently, or not at all."""
    builders = sorted(
        f"{name}: line {node.lineno}" for name, function in _route_functions().items()
        for node in ast.walk(function)
        if (isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Subscript) for target in node.targets))
        or (isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "append"))

    assert builders == []


def test_check_mesh_keys_lets_the_model_own_keys_through():
    from backend.routes.common import check_mesh_keys

    project = seed_project()
    keys = project.part_keys()

    check_mesh_keys(project, MeshRequest(volume_keys=keys[:1], body_sizes={keys[-1]: 2.0}))


def test_check_mesh_keys_names_every_unknown_key_sorted():
    from backend.routes.common import check_mesh_keys

    settings = MeshRequest(volume_keys=["zeta"], body_sizes={"alpha": 2.0})

    with pytest.raises(HTTPException) as refused:
        check_mesh_keys(seed_project(), settings)
    assert refused.value.status_code == 422
    assert refused.value.detail == "unknown mesh body key(s): alpha, zeta"


@pytest.fixture
def worker(monkeypatch):
    """`gmsh_worker.run` replaced: records what it was asked, answers or raises `outcome`."""
    calls = []
    state = {"outcome": {"ok": True}}

    async def run(*args):
        calls.append(args)
        if isinstance(state["outcome"], BaseException):
            raise state["outcome"]
        return state["outcome"]

    monkeypatch.setattr(gmsh_worker, "run", run)
    return calls, state


def test_run_mesh_job_hands_the_worker_the_job_and_both_documents(worker):
    from backend.routes.common import run_mesh_job

    calls, _ = worker
    project, settings = seed_project(), MeshRequest()

    answer = asyncio.run(run_mesh_job(gmsh_worker.mesh_job, project, settings, (ValueError,)))

    assert answer == {"ok": True}
    assert calls == [(gmsh_worker.mesh_job, project.model_dump_json(),
                      settings.model_dump_json())]


def test_run_mesh_job_turns_the_errors_it_is_given_into_a_500_with_the_reason(worker):
    from backend.routes.common import run_mesh_job

    _, state = worker
    state["outcome"] = MeshingError("the box has no volume")

    with pytest.raises(HTTPException) as refused:
        asyncio.run(run_mesh_job(gmsh_worker.mesh_job, seed_project(), MeshRequest(),
                                 (MeshingError,)))
    assert refused.value.status_code == 500
    assert refused.value.detail == "the box has no volume"
    assert isinstance(refused.value.__cause__, MeshingError)


def test_run_mesh_job_lets_any_other_error_through(worker):
    """Each route names what it turns into a 500; the rest -- a crashed worker, for one --
    goes on to the app's own handler."""
    from backend.routes.common import run_mesh_job

    _, state = worker
    state["outcome"] = ExportError("no materials")

    with pytest.raises(ExportError):
        asyncio.run(run_mesh_job(gmsh_worker.mesh_job, seed_project(), MeshRequest(),
                                 (MeshingError,)))
