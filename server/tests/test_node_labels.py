"""Node identity for the viewport's "Show labels -> Node IDs" overlay.

A label is only worth drawing if the number on it is the number the solver will see, so
both sources of a displayed mesh have to hand the viewer real Kratos node IDs:

*   a mesh the GUI generated -- gmsh tags are *not* those IDs, because
    `kratos.export_project` renumbers 1..N over the tags its blocks actually use and the
    interface split adds nodes along the way, so the numbering can only come from the
    exporter itself;
*   a `.mdpa` read back in -- the file's own node table, carried per drawn section.
"""

import pytest

from app import build, kratos, mdpa_import
from app.schemas import MeshRequest, Project
from app.seed import seed_project
from tests import mdpa


@pytest.fixture(scope="module")
def session():
    with build.session():
        yield


@pytest.fixture(scope="module")
def exported(session):
    project = seed_project()
    project.dimension = 2
    project.section_offset = 20.0
    return kratos.export_project(project, MeshRequest(element_size=6.0, order=2))


# ── A generated mesh: the exporter's own numbering ───────────────────────────

def test_export_carries_a_node_table_matching_the_deck(exported):
    deck = mdpa.parse(exported["mdpa"])
    table = exported["nodes"]

    assert len(table) == len(deck.nodes)
    assert [row[0] for row in table] == sorted(deck.nodes)
    for node_id, x, y, z in table:
        assert deck.nodes[node_id] == pytest.approx((x, y, z), abs=1e-6)


def test_node_ids_are_contiguous_from_one(exported):
    ids = [row[0] for row in exported["nodes"]]
    assert ids == list(range(1, len(ids) + 1))


# ── An imported deck: the file's own numbering ───────────────────────────────

def test_imported_sections_name_the_node_behind_every_position(exported):
    model = mdpa_import.import_mdpa(exported["mdpa"])
    sections = mdpa_import.to_sections(model)
    assert sections, "the seed section draws at least one body"

    nodes = model.world_nodes()
    for section in sections:
        ids = section["node_ids"]
        assert len(ids) * 3 == len(section["positions"])
        for index, node_id in enumerate(ids):
            assert node_id in nodes
            assert section["positions"][3 * index:3 * index + 3] == \
                pytest.approx(list(nodes[node_id]), abs=1e-9)


def test_imported_payload_reaches_the_client_with_its_node_ids(exported):
    model = mdpa_import.import_mdpa(exported["mdpa"])
    payload = model.to_dict()
    assert all(section["node_ids"] for section in payload["sections"])


# ── The route the overlay asks ───────────────────────────────────────────────

def test_mesh_nodes_route_returns_the_export_numbering():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        client.post("/api/project/reset")
        project = Project.model_validate(client.get("/api/project").json())
        project.dimension = 2
        project.section_offset = 20.0
        client.put("/api/project", json=project.model_dump())

        response = client.post("/api/mesh/nodes", json={"element_size": 6.0, "order": 2})
        assert response.status_code == 200
        table = response.json()["nodes"]
        assert table and [row[0] for row in table] == list(range(1, len(table) + 1))
        assert all(len(row) == 4 for row in table)
