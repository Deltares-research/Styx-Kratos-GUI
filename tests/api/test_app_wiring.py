"""How the app is put together: which module declares each route, and the middleware order.

`backend/main.py` only assembles the app. Every route of the HTTP API lives in the router
of its group (`backend/routes/`), the groups `docs/ARCHITECTURE.md` lists, so a reader can
go from a URL to its file. The table below is that mapping; a route outside it fails here,
which is what keeps the next route from landing in `main.py` again.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import ValidationError

from backend.main import app
from core import gmsh_worker
from core.kratos import ExportError
from core.meshing import MeshingError
from core.schemas import MeshRequest
from core.seed import seed_project

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
]
"""Which module a path belongs to, first match wins."""


def owner(path: str) -> str | None:
    return next((module for matches, module in OWNERS if matches(path)), None)


API_ROUTES = [route for route in app.routes if isinstance(route, APIRoute)]


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

def test_validated_returns_the_project_a_payload_describes():
    from backend.routes.common import validated

    project = seed_project()

    assert validated(project.model_dump()) == project


def test_validated_refuses_as_a_request_error_field_by_field():
    """The 422 a bad request body gets, not the 500 a raw `ValidationError` would be."""
    from backend.routes.common import validated

    payload = seed_project().model_dump()
    payload["layers"] = "not a list"

    with pytest.raises(RequestValidationError) as refused:
        validated(payload)
    assert [e["loc"] for e in refused.value.errors()] == [("layers",)]
    assert isinstance(refused.value.__cause__, ValidationError)


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
