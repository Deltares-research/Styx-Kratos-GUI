"""Every route's contract, in one table (plan/active/full-test-and-validation-plan.md sec 5).

For each route the app serves:

(a) a happy path, asserting the response *shape* -- its keys and, where it has one, the
    `invalidates` list the front end refreshes from;
(b) a refused request, with a `detail` a person can read: a sentence, or pydantic's list
    of `{loc, msg}` that `frontend/js/api.js` turns into one;
(d) for a project that *is* a Kratos deck, the routes that would mesh, export or restage
    it refuse with 422, and every other edit leaves the deck attached.

The table is checked against the application's own route list, so a new route without a
contract fails here rather than going untested. Domain errors beyond one per route live
next to the code they are about (`test_api.py`, `test_results.py`, ...).
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pytest
from fastapi.testclient import TestClient

from core.kratos import external_deck
from backend.main import app
from tests.api.served import api_routes
from core.model.templates import seed_project
from tests import results_run
from tests.test_importer import stl_text

RUN = None
"""The fake run of the test model the results routes read, set by the `client` fixture."""
COARSE = {"element_size": 6.0, "order": 1}


@dataclass
class Contract:
    method: str
    path: str
    happy: Callable
    keys: set[str] = field(default_factory=set)
    invalidates: set[str] | None = None
    bad: Callable | None = None
    bad_status: int | None = None
    content_type: str = "application/json"


def _project(c):
    return c.get("/api/project").json()


def _structures(c):
    p = _project(c)
    keys = ["loads", "beam_sections", "panel_sections", "beams", "anchor_sections",
            "anchors", "interface_sections", "interfaces", "normal_loads"]
    return {k: p[k] for k in keys}


def _fresh(name: str) -> str:
    """A path in a folder of its own, for a route that writes a file."""
    import tempfile

    return str(Path(tempfile.mkdtemp(prefix="contract-")) / name)


def _first_node(c):
    mesh = c.get(f"/api/results/runs/{RUN}/stages/7/mesh").json()
    return mesh["sections"][0]["node_ids"][0]


def _box(c):
    return c.post("/api/geometry/create", json={
        "kind": "box", "origin": [0, 0, 0], "size": [1, 1, 1], "label": "B"}).json()["parts"][0]["key"]


PROJECT_KEYS = {"project", "invalidates"}
EDITED = PROJECT_KEYS | {"edit_notes"}
"""An edit's answer: with the mesh sizes it took away with their bodies
(`backend.routes.common.stored`), which `frontend/js/api.js` shows."""
EVERYTHING = {"project", "tree", "geometry", "mesh"}

CONTRACTS = [
    Contract("GET", "/api/health", lambda c: c.get("/api/health"),
             {"ok", "version", "gmsh_version"}),
    Contract("GET", "/api/project", lambda c: c.get("/api/project"),
             {"name", "layers", "materials", "stages", "deck", "mesh"}),
    Contract("PUT", "/api/project", lambda c: c.put("/api/project", json=_project(c)),
             {"name", "layers", "materials"},
             bad=lambda c: c.put("/api/project", json={**_project(c), "no_such_key": 1}),
             bad_status=422),
    Contract("POST", "/api/project/open",
             lambda c: c.post("/api/project/open", json={**_project(c), "gravity": False}),
             {"project", "notes", "invalidates"}, EVERYTHING,
             bad=lambda c: c.post("/api/project/open", json={**_project(c), "no_such_key": 1}),
             bad_status=422),
    Contract("POST", "/api/project/migration-notes",
             lambda c: c.post("/api/project/migration-notes", json=_project(c)), {"notes"},
             bad=lambda c: c.post("/api/project/migration-notes", json=[]), bad_status=422),
    Contract("POST", "/api/project/reset", lambda c: c.post("/api/project/reset"),
             PROJECT_KEYS, EVERYTHING),
    Contract("POST", "/api/project/new", lambda c: c.post("/api/project/new"),
             PROJECT_KEYS, EVERYTHING),
    Contract("POST", "/api/project/script",
             lambda c: c.post("/api/project/script", json={"path": "tests/models/excavation.py"}),
             {"project", "path", "mesh", "invalidates"}, EVERYTHING,
             bad=lambda c: c.post("/api/project/script", json={"path": "no/such/file.py"}),
             bad_status=400),
    Contract("POST", "/api/project/script/save",
             lambda c: c.post("/api/project/script/save", json={"path": _fresh("model.py")}),
             {"path"},
             bad=lambda c: c.post("/api/project/script/save", json={"path": "model.txt"}),
             bad_status=422),
    Contract("PATCH", "/api/project/layers",
             lambda c: c.patch("/api/project/layers", json={"layers": _project(c)["layers"]}),
             EDITED,
             bad=lambda c: c.patch("/api/project/layers", json={"layers": [
                 {**_project(c)["layers"][0], "mat": "no_such_material"}]}),
             bad_status=422),
    Contract("PUT", "/api/project/water",
             lambda c: c.put("/api/project/water", json={"water": None}), EDITED,
             bad=lambda c: c.put("/api/project/water", json={}), bad_status=422),
    Contract("PATCH", "/api/project/materials",
             lambda c: c.patch("/api/project/materials",
                               json={"materials": _project(c)["materials"]}),
             EDITED,
             bad=lambda c: c.patch("/api/project/materials", json={"materials": []}),
             bad_status=422),
    Contract("PATCH", "/api/project/structures",
             lambda c: c.patch("/api/project/structures", json=_structures(c)),
             EDITED,
             bad=lambda c: c.patch("/api/project/structures", json={}), bad_status=422),
    Contract("PATCH", "/api/project/lines",
             lambda c: c.patch("/api/project/lines", json={"lines": [
                 {"id": "l", "name": "L", "points": [[1.0, 0.0], [1.0, -2.0]]}]}),
             EDITED,
             bad=lambda c: c.patch("/api/project/lines", json={"lines": [
                 {"id": "l", "name": "L", "points": [[1.0, 0.0]]}]}), bad_status=422),
    Contract("PATCH", "/api/project/bodies/{key}",
             lambda c: (c.patch("/api/project/lines", json={"lines": [
                 {"id": "l", "name": "L", "points": [[1.0, 0.0], [1.0, -8.0]]}]}),
                        c.patch(f"/api/project/bodies/{c.get('/api/project').json()['soil_body_keys'][0]}",
                                json={"name": "A"}))[1],
             EDITED,
             bad=lambda c: c.patch("/api/project/bodies/no_such_body", json={"name": "A"}),
             bad_status=404),
    Contract("PATCH", "/api/project/conditions",
             lambda c: c.patch("/api/project/conditions", json={
                 "boundary_conditions": _project(c)["boundary_conditions"]}),
             EDITED,
             bad=lambda c: c.patch("/api/project/conditions", json={"boundary_conditions": [
                 {"id": "d", "name": "d", "kind": "displacement", "on": "domain"}]}),
             bad_status=422),
    Contract("PATCH", "/api/project/stages",
             lambda c: c.patch("/api/project/stages", json={"stages": []}), EDITED,
             bad=lambda c: c.patch("/api/project/stages", json={"stages": [
                 {"id": "a", "name": "A"}, {"id": "b", "name": "B", "parent": "a",
                                            "deactivate": ["no_such_part"]}]}),
             bad_status=422),
    # The pre-rename routes, kept so old clients keep working.
    Contract("PATCH", "/api/project/phases",
             lambda c: c.patch("/api/project/phases", json={"phases": []}), EDITED),
    Contract("PATCH", "/api/project/dimension",
             lambda c: c.patch("/api/project/dimension",
                               json={"dimension": _project(c)["dimension"]}),
             {"project", "notes", "edit_notes", "invalidates"},
             bad=lambda c: c.patch("/api/project/dimension", json={"dimension": 4}),
             bad_status=422),
    Contract("PATCH", "/api/project/units",
             lambda c: c.patch("/api/project/units",
                               json={"unit_system": _project(c)["unit_system"]}),
             {"project", "notes", "edit_notes", "invalidates"},
             bad=lambda c: c.patch("/api/project/units", json={"unit_system": "imperial"}),
             bad_status=422),
    Contract("DELETE", "/api/project/custom_parts",
             lambda c: c.delete("/api/project/custom_parts"), {"ok"} | EDITED,
             EVERYTHING),
    Contract("DELETE", "/api/geometry/parts/{key}",
             lambda c: c.delete(f"/api/geometry/parts/{_box(c)}"), {"ok"} | EDITED,
             EVERYTHING,
             bad=lambda c: c.delete("/api/geometry/parts/no_such_part"), bad_status=404),
    Contract("GET", "/api/geometry", lambda c: c.get("/api/geometry"), {"bbox", "sections"}),
    Contract("POST", "/api/geometry/import",
             lambda c: c.post("/api/geometry/import", files={
                 "file": ("cube.stl", io.BytesIO(stl_text().encode()))}),
             {"parts", "invalidates"},
             bad=lambda c: c.post("/api/geometry/import", files={
                 "file": ("cube.txt", io.BytesIO(b"x"))}),
             bad_status=422),
    Contract("POST", "/api/geometry/create",
             lambda c: c.post("/api/geometry/create", json={
                 "kind": "box", "origin": [0, 0, 0], "size": [1, 1, 1], "label": "B"}),
             {"parts", "invalidates"},
             bad=lambda c: c.post("/api/geometry/create", json={"kind": "teapot"}),
             bad_status=422),
    Contract("POST", "/api/mesh", lambda c: c.post("/api/mesh", json=COARSE),
             {"bbox", "log", "meshed_keys", "parts", "sections", "stats"},
             bad=lambda c: c.post("/api/mesh", json={**COARSE, "element_size": 0}),
             bad_status=422),
    Contract("POST", "/api/mesh/labels", lambda c: c.post("/api/mesh/labels", json=COARSE),
             {"elements", "nodes", "stats"},
             bad=lambda c: c.post("/api/mesh/labels", json={**COARSE, "order": 3}),
             bad_status=422),
    Contract("POST", "/api/mesh/node-parts",
             lambda c: c.post("/api/mesh/node-parts", json=COARSE), {"nodes", "parts"},
             bad=lambda c: c.post("/api/mesh/node-parts", json={
                 **COARSE, "body_sizes": {"no_such_part": 1.0}}),
             bad_status=422),
    Contract("POST", "/api/export/mdpa", lambda c: c.post("/api/export/mdpa", json=COARSE),
             {"deck_name", "mdpa", "materials", "project_parameters", "warnings", "stats"},
             bad=lambda c: c.post("/api/export/mdpa", json={**COARSE, "element_size": -1}),
             bad_status=422),
    Contract("POST", "/api/calculate", lambda c: c.post("/api/calculate", json=COARSE),
             {"ok", "run", "directory", "stage", "error"},
             bad=lambda c: c.post("/api/calculate", json={**COARSE, "order": 7}),
             bad_status=422),
    Contract("GET", "/api/results/runs", lambda c: c.get("/api/results/runs"),
             {"runs", "root"}),
    Contract("GET", "/api/results/runs/{run_id}", lambda c: c.get(f"/api/results/runs/{RUN}"),
             {"id", "deck", "stages", "files", "complete", "failed_at", "log"},
             bad=lambda c: c.get("/api/results/runs/Nope_2001-01-01_00-00"), bad_status=404),
    Contract("GET", "/api/results/runs/{run_id}/stages/{index}/fields",
             lambda c: c.get(f"/api/results/runs/{RUN}/stages/7/fields"), {"stage", "groups"},
             bad=lambda c: c.get(f"/api/results/runs/{RUN}/stages/99/fields"),
             bad_status=404),
    Contract("GET", "/api/results/runs/{run_id}/stages/{index}/mesh",
             lambda c: c.get(f"/api/results/runs/{RUN}/stages/7/mesh"),
             {"bbox", "dimension", "sections"},
             bad=lambda c: c.get(f"/api/results/runs/{RUN}/stages/99/mesh"), bad_status=404),
    Contract("GET", "/api/results/runs/{run_id}/stages/{index}/displacement",
             lambda c: c.get(f"/api/results/runs/{RUN}/stages/7/displacement"),
             {"ids", "source", "values"},
             bad=lambda c: c.get(f"/api/results/runs/{RUN}/stages/0/displacement"),
             bad_status=404),
    Contract("GET", "/api/results/runs/{run_id}/stages/{index}/at/{node}",
             lambda c: c.get(f"/api/results/runs/{RUN}/stages/7/at/{_first_node(c)}"),
             {"at", "node", "values"},
             bad=lambda c: c.get(f"/api/results/runs/{RUN}/stages/7/at/999999999"),
             bad_status=422),
    Contract("GET", "/api/results/runs/{run_id}/stages/{index}/parts",
             lambda c: c.get(f"/api/results/runs/{RUN}/stages/7/parts"), {"parts"},
             bad=lambda c: c.get(f"/api/results/runs/{RUN}/stages/99/parts"), bad_status=404),
    Contract("GET", "/api/results/runs/{run_id}/stages/{index}/field/{name}",
             lambda c: c.get(f"/api/results/runs/{RUN}/stages/7/field/p"),
             {"field", "ids", "label", "location", "max", "min", "unit", "values"},
             bad=lambda c: c.get(f"/api/results/runs/{RUN}/stages/7/field/no_such_field"),
             bad_status=422),
    Contract("GET", "/api/results/runs/{run_id}/members",
             lambda c: c.get(f"/api/results/runs/{RUN}/members"), {"members"},
             bad=lambda c: c.get("/api/results/runs/Nope_2001-01-01_00-00/members"),
             bad_status=404),
    Contract("GET", "/api/results/runs/{run_id}/members/{member}/{quantity}",
             lambda c: c.get(f"/api/results/runs/{RUN}/members/wall/M"),
             set(),
             bad=lambda c: c.get(f"/api/results/runs/{RUN}/members/wall/no_such_quantity"),
             bad_status=422),
    Contract("GET", "/api/results/runs/{run_id}/files/{name}",
             lambda c: c.get(f"/api/results/runs/{RUN}/files/ProjectParameters.json"),
             set(), content_type="application/octet-stream",
             bad=lambda c: c.get(f"/api/results/runs/{RUN}/files/no_such_file.txt"),
             bad_status=404),
    Contract("GET", "/api/results/runs/{run_id}/archive",
             lambda c: c.get(f"/api/results/runs/{RUN}/archive"), set(),
             content_type="application/zip",
             bad=lambda c: c.get("/api/results/runs/Nope_2001-01-01_00-00/archive"),
             bad_status=404),
    Contract("POST", "/api/import/mdpa",
             lambda c: c.post("/api/import/mdpa", files={"file": ("d.mdpa", io.BytesIO(
                 b"Begin Nodes\n1 0 0 0\n2 1 0 0\n3 0 1 0\nEnd Nodes\n"
                 b"Begin Elements UPwSmallStrainElement2D3N\n1 1 1 2 3\nEnd Elements\n"))}),
             {"dimension", "bbox", "nodes", "elements", "parts", "sections", "node_parts"},
             bad=lambda c: c.post("/api/import/mdpa", files={"file": ("d.mdpa", io.BytesIO(
                 b"Begin Nodes\n1 zero 0 0\nEnd Nodes\n"))}),
             bad_status=422),
    Contract("GET", "/", lambda c: c.get("/"), set(), content_type="text/html"),
]


def _id(contract: Contract) -> str:
    return f"{contract.method} {contract.path}"


@pytest.fixture
def client(monkeypatch, tmp_path):
    global RUN
    RUN = results_run.use(monkeypatch, results_run.fake_run())
    # Calculate runs this interpreter in Kratos' place: the route's own shape is the
    # point here, not the analysis (`test_calculate.py` covers the runner).
    from core.analysis import calculation
    monkeypatch.setattr(calculation, "SETTINGS_FILE", tmp_path / "none.json")
    monkeypatch.delenv(calculation.KRATOS_ENV, raising=False)
    monkeypatch.setenv(calculation.PYTHON_ENV, __import__("sys").executable)
    monkeypatch.setattr(calculation, "COMMAND", ["-c", "print('stand-in')"])
    with TestClient(app) as c:
        c.post("/api/project/reset")
        yield c
        c.post("/api/project/reset")


def test_every_route_has_a_contract():
    routes = {f"{m} {r.path}" for r in api_routes(app) for m in r.methods}
    listed = {_id(c) for c in CONTRACTS}

    assert routes - listed == set(), "routes with no contract"
    assert listed - routes == set(), "contracts for routes that do not exist"


@pytest.mark.parametrize("contract", CONTRACTS, ids=_id)
def test_the_happy_path_has_its_shape(client, contract, monkeypatch, tmp_path):
    if contract.path == "/api/calculate":
        from core.analysis import calculation
        monkeypatch.setenv(calculation.RUNS_ENV, str(tmp_path / "calc_runs"))
    response = contract.happy(client)

    assert response.status_code == 200, response.text[:500]
    assert response.headers["content-type"].startswith(contract.content_type)
    if contract.content_type == "application/json" and contract.keys:
        body = response.json()
        assert contract.keys <= set(body), sorted(contract.keys - set(body))
        if contract.invalidates is not None:
            assert contract.invalidates <= set(body["invalidates"])


def _readable(detail) -> bool:
    if isinstance(detail, str):
        return bool(detail.strip()) and not detail.startswith(("{", "[", "<"))
    if isinstance(detail, list):
        return bool(detail) and all(isinstance(d, dict) and d.get("msg") for d in detail)
    return False


BAD = [c for c in CONTRACTS if c.bad is not None]


@pytest.mark.parametrize("contract", BAD, ids=_id)
def test_a_refused_request_says_why(client, contract):
    response = contract.bad(client)

    assert response.status_code == contract.bad_status, response.text[:500]
    assert _readable(response.json().get("detail")), response.text[:500]


def test_geometry_import_reports_an_unreadable_obj_as_a_client_error(client):
    response = client.post("/api/geometry/import", files={
        "file": ("bad.obj", io.BytesIO(b"f 1 2 3\n")),
    })

    assert response.status_code == 422, response.text
    assert _readable(response.json().get("detail"))


RUNNER_ERRORS = [
    ("Busy", 409, "A calculation is already running."),
    ("CalculationError", 500, "Cannot start solver."),
]


@pytest.mark.parametrize("error_name, status, message", RUNNER_ERRORS)
def test_calculate_project_reports_runner_errors(
        client, monkeypatch, error_name, status, message):
    from unittest.mock import AsyncMock, Mock

    from backend.routes import decks
    from core.analysis import calculation

    export = {"stats": {}, "warnings": []}
    mesh = AsyncMock(return_value=export)
    monkeypatch.setattr(decks, "run_mesh_job", mesh)
    run = Mock(side_effect=getattr(calculation, error_name)(message))
    monkeypatch.setattr(calculation, "run", run)

    response = client.post("/api/calculate", json=COARSE)

    assert response.status_code == status, response.text
    assert response.json() == {"detail": message}
    mesh.assert_awaited_once()
    run.assert_called_once_with(export)


# ── (d) a project that is a Kratos deck ──────────────────────────────────────

DECK_MDPA = ("Begin Properties 1\nEnd Properties\nBegin Nodes\n1 0 0 0\n2 1 0 0\n3 0 1 0\n"
             "End Nodes\nBegin Elements UPwSmallStrainElement2D3N\n1 1 1 2 3\nEnd Elements\n"
             "Begin SubModelPart Soil\n Begin SubModelPartNodes\n 1\n 2\n 3\n"
             " End SubModelPartNodes\n Begin SubModelPartElements\n 1\n"
             " End SubModelPartElements\nEnd SubModelPart\n")


@pytest.fixture
def deck_client(client, tmp_path):
    directory = tmp_path / "deck"
    directory.mkdir()
    (directory / "site.mdpa").write_text(DECK_MDPA, encoding="utf-8")
    (directory / "materials.json").write_text('{"properties": []}', encoding="utf-8")
    stage = {"stage_preprocess": {"modelers": [{
                 "name": "Modelers.KratosMultiphysics.ImportMDPAModeler",
                 "Parameters": {"input_filename": "site", "model_part_name": "PorousDomain"}}]},
             "stage_settings": {
                 "problem_data": {"problem_name": "1_Initial"},
                 "solver_settings": {
                     "model_import_settings": {"input_type": "use_input_model_part"},
                     "material_import_settings": {"materials_filename": "materials.json"},
                     "problem_domain_sub_model_part_list": ["Soil"]},
                 "processes": {}, "output_processes": {}}}
    (directory / "site.json").write_text(json.dumps({
        "orchestrator": {"name": "Orchestrators.KratosMultiphysics.SequentialOrchestrator",
                         "settings": {"execution_list": ["1_Initial"]}},
        "stages": {"1_Initial": stage}}), encoding="utf-8")
    project = external_deck.deck_project(directory, "site.json", name="Site")
    assert client.put("/api/project", json=project.model_dump()).status_code == 200
    return client


@pytest.mark.parametrize("error_name, status, message", RUNNER_ERRORS)
def test_calculate_deck_reports_runner_errors(
        deck_client, monkeypatch, error_name, status, message):
    from unittest.mock import Mock

    from backend import store
    from core.analysis import calculation

    deck = store.get().deck
    run = Mock(side_effect=getattr(calculation, error_name)(message))
    monkeypatch.setattr(calculation, "run_deck", run)

    response = deck_client.post("/api/calculate", json=COARSE)

    assert response.status_code == status, response.text
    assert response.json() == {"detail": message}
    run.assert_called_once_with(deck)


def test_calculate_reports_a_missing_external_deck_file_as_a_client_error(
        deck_client, tmp_path, monkeypatch):
    from core.analysis import calculation
    from unittest.mock import Mock

    run = Mock()
    monkeypatch.setattr(calculation, "run_deck", run)
    (tmp_path / "deck" / "site.mdpa").unlink()

    response = deck_client.post("/api/calculate", json=COARSE)

    assert response.status_code == 400, response.text
    assert _readable(response.json().get("detail"))
    assert "site.mdpa could not be read" in response.json()["detail"]
    run.assert_not_called()


REFUSED_FOR_A_DECK = [
    ("POST", "/api/mesh", COARSE), ("POST", "/api/mesh/labels", COARSE),
    ("POST", "/api/mesh/node-parts", COARSE), ("POST", "/api/export/mdpa", COARSE),
    ("PATCH", "/api/project/stages", {"stages": []}),
]


@pytest.mark.parametrize("method,path,body", REFUSED_FOR_A_DECK,
                         ids=[f"{m} {p}" for m, p, _ in REFUSED_FOR_A_DECK])
def test_a_deck_is_not_meshed_exported_or_restaged(deck_client, method, path, body):
    response = deck_client.request(method, path, json=body)

    assert response.status_code == 422
    assert "deck" in response.json()["detail"].lower()


@pytest.mark.parametrize("edit", [
    lambda c: c.patch("/api/project/layers", json={"layers": _project(c)["layers"]}),
    # A deck project carries no materials of its own, and the library may not be empty.
    lambda c: c.patch("/api/project/materials",
                      json={"materials": [seed_project().materials[0].model_dump()]}),
    lambda c: c.put("/api/project/water", json={"water": None}),
    lambda c: c.delete("/api/project/custom_parts"),
], ids=["layers", "materials", "water", "clear custom parts"])
def test_any_other_edit_leaves_the_deck_attached(deck_client, edit):
    before = _project(deck_client)["deck"]

    assert edit(deck_client).status_code == 200
    assert _project(deck_client)["deck"] == before
