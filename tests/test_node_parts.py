"""Which SubModelParts each node is in -- read off the deck itself.

The answer is taken from the `.mdpa` the export writes, parsed back with
`core.kratos.mdpa_import`, so a part's name and a node's number are exactly what Kratos is given.
That matters most at an interface: the split leaves two or three nodes at one point, and
which of them the wall holds and which each soil side holds is the whole question.
"""

from __future__ import annotations

from collections import defaultdict

import pytest

from core.geometry import build
from core.kratos import export as kratos, node_parts
from tests.models.excavation import excavation_project
from core.model.schemas import MeshRequest

DECK = """Begin Properties 0
End Properties

Begin Nodes
  1  0.0  0.0  0.0
  2  1.0  0.0  0.0
  3  1.0  0.0  0.0
  4  2.0  0.0  0.0
End Nodes

Begin SubModelPart Wall
  Begin SubModelPartNodes
    1
    2
  End SubModelPartNodes
End SubModelPart

Begin SubModelPart Soil
  Begin SubModelPartNodes
    3
    4
  End SubModelPartNodes
End SubModelPart

Begin SubModelPart Load
  Begin SubModelPartNodes
    2
    3
  End SubModelPartNodes
End SubModelPart
"""


def membership(payload: dict) -> dict[int, set[str]]:
    out: dict[int, set[str]] = defaultdict(set)
    for part in payload["parts"]:
        for node in part["nodes"]:
            out[node].add(part["name"])
    return out


def test_every_node_and_its_coordinates_come_back():
    payload = node_parts.node_parts(DECK)
    assert payload["nodes"] == [[1, 0.0, 0.0, 0.0], [2, 1.0, 0.0, 0.0],
                                [3, 1.0, 0.0, 0.0], [4, 2.0, 0.0, 0.0]]


def test_each_part_lists_its_own_nodes_in_deck_order():
    payload = node_parts.node_parts(DECK)
    assert [(part["name"], part["kind"], part["nodes"]) for part in payload["parts"]] == [
        ("Wall", "group", [1, 2]),
        ("Soil", "group", [3, 4]),
        ("Load", "group", [2, 3]),
    ]


def test_a_node_is_in_every_part_that_names_it():
    by_node = membership(node_parts.node_parts(DECK))
    assert by_node[2] == {"Wall", "Load"}
    assert by_node[3] == {"Soil", "Load"}


# ── The test model's wall ────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def wall_deck():
    with build.session():
        exported = kratos.export_project(excavation_project(), MeshRequest(),
                                         include_materials=False)
    return node_parts.node_parts(exported["mdpa"])


def test_the_wall_and_each_soil_side_hold_their_own_node(wall_deck):
    """Every wall position the interface split is three nodes: the pile's own, and one
    for the soil on each side. Each side's copy is in that side's soil only -- one body,
    or two where the node sits on the seam between layers -- and never in the other
    side's."""
    by_node = membership(wall_deck)
    at = defaultdict(list)
    for node, x, y, _ in wall_deck["nodes"]:
        at[(round(x, 6), round(y, 6))].append(node)
    triples = [ids for ids in at.values()
               if len(ids) == 3 and any("SheetPileWall" in by_node[n] for n in ids)]
    assert triples, "no split wall node at all"
    for ids in triples:
        walls = [n for n in ids if "SheetPileWall" in by_node[n]]
        assert len(walls) == 1, ids
        soils = [n for n in ids if n not in walls]
        bodies = [{p for p in by_node[n] if p.startswith("Soil_")} for n in soils]
        assert all(bodies), ("a soil copy in no soil body", bodies)
        assert not bodies[0] & bodies[1], ("both sides in one body", bodies)


def test_the_numbering_is_the_deck_s(wall_deck):
    ids = [row[0] for row in wall_deck["nodes"]]
    assert ids == list(range(1, len(ids) + 1))


# ── The route ───────────────────────────────────────────────────────────────

def test_the_route_answers_in_the_labels_numbering():
    """The viewport puts numbers on the mesh from `/api/mesh/labels` and asks this route
    what a number belongs to, so the two must count the same nodes the same way."""
    from fastapi.testclient import TestClient

    from backend import store
    from backend.main import app

    with TestClient(app) as client:
        store.put(excavation_project())
        settings = {"element_size": 1.0, "order": 2}
        response = client.post("/api/mesh/node-parts", json=settings)
        assert response.status_code == 200, response.text
        payload = response.json()
        labels = client.post("/api/mesh/labels", json=settings).json()
        assert [row[0] for row in payload["nodes"]] == [row[0] for row in labels["nodes"]]
        assert {part["name"] for part in payload["parts"]} >= {"SheetPileWall", "Load"}
        assert client.post("/api/mesh/node-parts", json={
            "element_size": 1.0, "order": 2, "volume_keys": ["missing_body"]
        }).status_code == 422
        store.reset()


# ── An imported deck ────────────────────────────────────────────────────────

def test_an_imported_deck_says_which_parts_each_of_its_nodes_is_in():
    """The first part of the Imported mesh feature: a user previews a `.mdpa`, clicks a
    node on it, and is told its SubModelParts. The preview needs the same node -> parts
    payload the project's own deck gets, read off the file it was given."""
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as client:
        response = client.post("/api/import/mdpa",
                               files={"file": ("case.mdpa", DECK.encode("utf-8"))})
    assert response.status_code == 200, response.text
    assert response.json()["node_parts"] == node_parts.node_parts(DECK)
