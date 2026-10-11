"""Entity identity for the viewport's "Show labels" overlay: node and element IDs.

A label is only worth drawing if the number on it is the number the solver will see, so
both sources of a displayed mesh have to hand the viewer real Kratos IDs:

*   a mesh the GUI generated -- gmsh tags are *not* those IDs, because
    `kratos.export_project` renumbers 1..N over the tags its blocks actually use, numbers
    elements in emission order, and the interface split adds nodes along the way, so the
    numbering can only come from the exporter itself;
*   a `.mdpa` read back in -- the file's own tables, carried per drawn section.

An element is labelled at its centroid, which for the simplices this exporter writes is
the mean of its nodes in either order: the midside nodes of a quadratic element are edge
midpoints, and their mean is the same point as the corners'.
"""

import pytest

from core.geometry import build
from core.kratos import export as kratos, mdpa_import
from core.model.schemas import MeshRequest, Project
from core.model.seed import seed_project
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


def test_export_carries_an_element_table_matching_the_deck(exported):
    deck = mdpa.parse(exported["mdpa"])
    table = exported["elements"]

    assert len(table) == len(deck.element_ids())
    assert [row[0] for row in table] == sorted(deck.element_ids())


def test_an_element_is_labelled_at_the_centre_of_its_own_nodes(exported):
    deck = mdpa.parse(exported["mdpa"])
    for element_id, x, y, z in exported["elements"][:50]:
        corners = [deck.nodes[node] for node in deck.element(element_id)]
        centre = [sum(c[axis] for c in corners) / len(corners) for axis in range(3)]
        assert (x, y, z) == pytest.approx(tuple(centre), abs=1e-6)


def test_every_labelled_element_lies_inside_the_model(exported):
    xs = [row[1] for row in exported["nodes"]]
    ys = [row[2] for row in exported["nodes"]]
    for _, x, y, _z in exported["elements"]:
        assert min(xs) - 1e-6 <= x <= max(xs) + 1e-6
        assert min(ys) - 1e-6 <= y <= max(ys) + 1e-6


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


def test_imported_sections_carry_their_elements_and_where_to_label_them(exported):
    model = mdpa_import.import_mdpa(exported["mdpa"])
    sections = mdpa_import.to_sections(model)
    nodes = model.world_nodes()
    by_id = {element_id: conn
             for entity in model.elements for element_id, conn in entity.entries.items()}

    labelled = [row for section in sections for row in section["elements"]]
    assert labelled, "a drawn body has drawn elements"
    # No element is labelled twice: a body part claims its own, and the per-kind
    # fallback only picks up what no part claimed.
    assert len({row[0] for row in labelled}) == len(labelled)

    for element_id, x, y, z in labelled[:50]:
        corners = [nodes[node] for node in by_id[element_id]]
        centre = [sum(c[axis] for c in corners) / len(corners) for axis in range(3)]
        assert (x, y, z) == pytest.approx(tuple(centre), abs=1e-9)


def test_imported_payload_reaches_the_client_with_both_tables(exported):
    model = mdpa_import.import_mdpa(exported["mdpa"])
    payload = model.to_dict()
    assert all(section["node_ids"] for section in payload["sections"])
    assert any(section["elements"] for section in payload["sections"])


# ── The route the overlay asks ───────────────────────────────────────────────

def test_mesh_labels_route_returns_the_export_numbering():
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as client:
        client.post("/api/project/reset")
        project = Project.model_validate(client.get("/api/project").json())
        project.dimension = 2
        project.section_offset = 20.0
        client.put("/api/project", json=project.model_dump())

        response = client.post("/api/mesh/labels", json={"element_size": 6.0, "order": 2})
        assert response.status_code == 200
        payload = response.json()

        # Both tables from one export pass: a second trip would mean meshing the whole
        # project again to say what it already said.
        nodes, elements = payload["nodes"], payload["elements"]
        assert nodes and [row[0] for row in nodes] == list(range(1, len(nodes) + 1))
        assert elements and [row[0] for row in elements] == list(range(1, len(elements) + 1))
        assert all(len(row) == 4 for row in nodes + elements)
