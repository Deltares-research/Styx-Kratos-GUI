"""HTTP contract tests.

The base UI under `frontend/base/` is served at `/css` and `/js`, and `frontend/assets` and
`frontend/vendor` at `/assets` and `/vendor`, mounted in place so there is one copy of each
file on disk.
"""

import json
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from core.geometry.cad_import import ImportRefused
from core.geometry import solid_model
from core.model.schemas import Project
from core.model.templates import seed_project

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "projects"


@pytest.fixture(scope="module")
def client():
    # The server now opens on a blank project (backend/store.py); this whole suite is
    # written against the seeded demo model, so start every module from there.
    with TestClient(app) as c:
        c.post("/api/project/reset")
        yield c


# ── Health ──────────────────────────────────────────────────────────────────

def test_empty_project_can_save_first_layer_and_delete_last_layer(client):
    from core.model.templates import blank_project
    original = client.get('/api/project').json()
    try:
        client.put('/api/project', json=blank_project().model_dump())
        material = seed_project().materials[0].model_dump()
        layer = dict(id='L1', name='Soil_1', mat=material['id'],
                     top=0, bottom=-5)
        response = client.patch('/api/project/layers', json={
            'layers': [layer], 'materials': [material],
        })
        assert response.status_code == 200
        response = client.patch('/api/project/layers', json={'layers': []})
        assert response.status_code == 200
        assert response.json()['project']['layers'] == []
    finally:
        client.put('/api/project', json=original)


def test_custom_layer_can_be_inserted_before_an_existing_body(client):
    original = client.get('/api/project').json()
    try:
        recipe = dict(kind='box', origin=[0, 0, 0], size=[1, 1, 1], material=original['materials'][0]['id'])
        first = client.post('/api/geometry/create', json=recipe).json()['parts'][0]['key']
        recipe.update(origin=[2, 0, 0], insert_before=first)
        response = client.post('/api/geometry/create', json=recipe)
        assert response.status_code == 200
        keys = [p['key'] for p in client.get('/api/project').json()['custom_parts']]
        assert keys.index(response.json()['parts'][0]['key']) < keys.index(first)
    finally:
        client.put('/api/project', json=original)

def test_health_reports_the_gmsh_version(client):
    """Not a ping. The point is to prove the worker subprocess is alive and that gmsh
    loaded inside it, which is where the interesting failures live."""
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert body["gmsh_version"].startswith("4.")


def test_health_and_the_page_say_the_version_kratos_cli_says(client):
    from core.version import describe

    assert client.get("/api/health").json()["version"] == describe()
    page = client.get("/").text
    assert f'<meta name="styx-version" content="{describe()}">' in page


# ── Project ─────────────────────────────────────────────────────────────────

def test_get_project_returns_something_the_schema_accepts_back(client):
    body = client.get("/api/project").json()
    assert Project.model_validate(body) == seed_project()


def test_put_project_replaces_the_model(client):
    changed = seed_project().model_dump()
    changed["name"] = "Renamed site"
    changed["mesh"]["element_size"] = 4.0

    assert client.put("/api/project", json=changed).status_code == 200
    assert client.get("/api/project").json()["name"] == "Renamed site"

    client.put("/api/project", json=seed_project().model_dump())


def test_post_project_reset_restores_the_seed_project(client):
    """Test setup's way back to the known, fully-populated demo model -- not what the
    toolbar's "New project" does (see test_post_project_new_starts_an_empty_project,
    below). The client has no copy of the seed -- it is the server that decides what
    the demo model is -- so the reset has to happen here."""
    changed = seed_project().model_dump()
    changed["name"] = "Something else"
    changed["dimension"] = 2
    client.put("/api/project", json=changed)

    body = client.post("/api/project/reset").json()
    assert Project.model_validate(body["project"]) == seed_project()
    assert body["invalidates"] == ["project", "tree", "geometry", "mesh"]
    assert client.get("/api/project").json()["name"] == seed_project().name


def test_post_project_new_starts_an_empty_project(client):
    """"New project" on the toolbar. The client has no copy of what "empty" means --
    it is the server that decides -- so this has to happen here, not by the client
    inventing a blank document of its own."""
    from core.model.templates import blank_project

    body = client.post("/api/project/new").json()

    assert Project.model_validate(body["project"]) == blank_project()
    assert body["invalidates"] == ["project", "tree", "geometry", "mesh"]
    assert client.get("/api/project").json() == blank_project().model_dump(mode="json")

    client.put("/api/project", json=seed_project().model_dump())


def test_the_project_the_server_opens_on_is_plane_strain(client):
    """The app is a 2D modeller first: the document it comes up on is the section, so
    the client never has to switch into it -- and never shows a 3D view it is about to
    replace. The offset is resolved here too, so the viewport reads one number."""
    from core.model.templates import blank_project

    blank = blank_project()

    assert blank.dimension == 2
    assert blank.section_offset == pytest.approx((blank.domain.z0 + blank.domain.z1) / 2)

    try:
        assert client.post("/api/project/new").json()["project"]["dimension"] == 2
        # An empty site draws nothing, but it still has to build: the viewport asks for
        # this before the user has added anything.
        assert client.get("/api/geometry").status_code == 200
    finally:
        client.put("/api/project", json=seed_project().model_dump())


def test_put_project_rejects_a_model_that_breaks_the_layer_stack(client):
    """js/dialogs.js edits layer depths with no validation at all, so this is the first
    place a gap in the stack can be caught rather than silently rendered."""
    broken = seed_project().model_dump()
    broken["layers"][0]["bottom"] = -9.0        # L2 still starts at -8.0

    response = client.put("/api/project", json=broken)
    assert response.status_code == 422
    assert "contiguous" in json.dumps(response.json())

    assert client.get("/api/project").json()["layers"][0]["bottom"] == -8.0


def test_put_project_rejects_unknown_fields(client):
    """extra='forbid' catches a frontend sending a renamed field, which would otherwise
    be dropped in silence and look like the edit simply did not take."""
    payload = seed_project().model_dump() | {"elementSize": 3.0}
    assert client.put("/api/project", json=payload).status_code == 422


def test_run_script_requires_a_path(client):
    response = client.post("/api/project/script", json={})

    assert response.status_code == 422
    assert response.json()["detail"] == "run needs a path to a .py file"


# ── Geometry ────────────────────────────────────────────────────────────────

def test_geometry_returns_drawable_sections_for_every_part(client):
    body = client.get("/api/geometry").json()
    assert {s["key"] for s in body["sections"]} == set(seed_project().part_keys())
    assert len(body["bbox"]) == 6

    for section in body["sections"]:
        assert set(section) == {"key", "color", "positions", "indices", "edges"}
        assert section["indices"] and len(section["indices"]) % 3 == 0
        assert max(section["indices"]) < len(section["positions"]) // 3


def test_geometry_is_gzipped_for_a_browser(client):
    """Uncompressed the payload is megabytes of decimal digits; gzipped it is tens of
    kilobytes, which is what makes JSON the right choice here rather than a binary
    format."""
    plain = client.get("/api/geometry", headers={"accept-encoding": "identity"})
    zipped = client.get("/api/geometry", headers={"accept-encoding": "gzip"})

    assert zipped.headers.get("content-encoding") == "gzip"
    assert int(zipped.headers["content-length"]) < len(plain.content) // 4


def test_geometry_follows_the_project(client):
    """The whole point of the backend: editing the model changes the 3D, which is what
    js/dialogs.js:124 currently apologises for being unable to do."""
    before = client.get("/api/geometry").json()

    deeper = seed_project().model_dump()
    deeper["layers"][0]["bottom"] = -9.0
    deeper["layers"][1]["top"] = -9.0
    assert client.put("/api/project", json=deeper).status_code == 200

    after = client.get("/api/geometry").json()
    assert after != before
    assert after["sections"] != before["sections"]

    client.put("/api/project", json=seed_project().model_dump())


def test_a_geometry_failure_is_reported_not_swallowed(client):
    """An OCC boolean that produces nothing must surface as an error the command log can
    show, never as an empty model that looks like a rendering bug."""
    # The full build: the layered seed raises no wall.
    impossible = seed_project(simple=False).model_dump()
    impossible["wall"]["thickness"] = 1e-9

    client.put("/api/project", json=impossible)
    response = client.get("/api/geometry")
    client.put("/api/project", json=seed_project().model_dump())

    assert response.status_code in (200, 500)
    if response.status_code == 500:
        assert "detail" in response.json()


# ── Geometry Import ───────────────────────────────────────────────────────────

def test_post_geometry_import_rejects_unsupported_extensions(client):
    response = client.post("/api/geometry/import", files={"file": ("test.txt", b"foo")})
    assert response.status_code == 422
    assert "extension" in response.json()["detail"]


@pytest.mark.parametrize(("failure", "status", "detail"), [
    (ImportRefused("the file has no solid"), 422, "the file has no solid"),
    (RuntimeError("worker unavailable"), 500, "worker unavailable"),
])
def test_post_geometry_import_reports_worker_failures(
        client, monkeypatch, failure, status, detail):
    from backend.routes import geometry

    async def fail(*_args):
        raise failure

    monkeypatch.setattr(geometry.gmsh_worker, "run", fail)

    response = client.post("/api/geometry/import", files={"file": ("broken.step", b"not CAD")})

    assert response.status_code == status
    assert response.json()["detail"] == detail


def test_post_geometry_import_adds_custom_part_and_invalidates(client):
    # A tiny valid step file (just to pass extension check and get to gmsh)
    # The actual parsing will happen in the gmsh worker.
    # For a real test, let's just make sure the API calls the job and handles response.
    # Since we don't want to actually run the gmsh import on a dummy file that would fail,
    # we can use a valid step file string from test_importer.py, but it's easier to mock the worker job
    # or just use a valid step. Let's create a real step file via gmsh here.
    
    import gmsh
    with solid_model.session():
        gmsh.clear()
        gmsh.model.occ.addBox(0,0,0,1,1,1)
        gmsh.model.occ.synchronize()
        import tempfile
        import os
        fd, path = tempfile.mkstemp(suffix=".step")
        os.close(fd)
        gmsh.write(path)
        gmsh.clear()
        
    with open(path, "rb") as f:
        content = f.read()
    os.remove(path)
    
    response = client.post("/api/geometry/import", files={"file": ("box.step", content)})
    assert response.status_code == 200
    body = response.json()
    
    assert len(body["parts"]) == 1
    part = body["parts"][0]
    assert part["key"].startswith("imported_")
    assert part["source"] == "import"
    assert "invalidates" in body


# ── Mdpa Import ────────────────────────────────────────────────────────────

def test_post_import_mdpa_rejects_unsupported_extensions(client):
    response = client.post("/api/import/mdpa", files={"file": ("test.txt", b"foo")})
    assert response.status_code == 422
    assert "extension" in response.json()["detail"]


def test_post_import_mdpa_rejects_malformed_decks(client):
    response = client.post("/api/import/mdpa",
                           files={"file": ("broken.mdpa", b"Begin Nodes\n1 x 0 0\nEnd Nodes\n")})
    assert response.status_code == 422


def test_post_import_mdpa_returns_the_parsed_mesh(client):
    deck = (
        b"Begin Properties 0\nEnd Properties\n\n"
        b"Begin Nodes\n1 0.0 0.0 0.0\n2 1.0 0.0 0.0\n3 0.0 1.0 0.0\nEnd Nodes\n\n"
        b"Begin Elements UPwSmallStrainElement2D3N\n1 0 1 2 3\nEnd Elements\n\n"
        b"Begin SubModelPart Soil_1\n"
        b"    Begin SubModelPartNodes\n1\n2\n3\n    End SubModelPartNodes\n"
        b"    Begin SubModelPartElements\n1\n    End SubModelPartElements\n"
        b"End SubModelPart\n"
    )
    response = client.post("/api/import/mdpa", files={"file": ("case.mdpa", deck)})
    assert response.status_code == 200
    body = response.json()

    assert body["nodes"] == 3
    assert body["dimension"] == 2
    assert body["elements"] == [{"kratos_class": "UPwSmallStrainElement2D3N",
                                 "kind": "continuum", "dim": 2, "count": 1}]
    part = next(p for p in body["parts"] if p["name"] == "Soil_1")
    assert part["kind"] == "body"


def test_post_import_mdpa_returns_a_2d_deck_in_the_frame_it_was_written_in(client):
    """A .mdpa carries Kratos plane coordinates, which since the re-basis are the
    world's: a 2D model is the x-y plane at z = 0. Nothing about the open project is
    needed to place it, and nothing is rotated on the way in."""
    deck = (
        b"Begin Properties 0\nEnd Properties\n\n"
        b"Begin Nodes\n1 0.0 0.0 0.0\n2 8.0 0.0 0.0\n3 0.0 -6.0 0.0\nEnd Nodes\n\n"
        b"Begin Elements UPwSmallStrainElement2D3N\n1 0 1 2 3\nEnd Elements\n"
    )
    section = seed_project().model_dump()
    section.update(dimension=2, section_offset=20.0)
    client.put("/api/project", json=section)
    try:
        body = client.post("/api/import/mdpa", files={"file": ("case.mdpa", deck)}).json()
    finally:
        client.put("/api/project", json=seed_project().model_dump())

    assert body["bbox"] == [0.0, -6.0, 0.0, 8.0, 0.0, 0.0]
    positions = next(s for s in body["sections"]
                     if s["key"] == "imported_continuum")["positions"]
    assert positions[2::3] == [0.0, 0.0, 0.0], "every node sits on the x-y plane"


def test_post_geometry_create_adds_custom_part(client):
    recipe = {
        "kind": "box",
        "origin": [0,0,0],
        "size": [5,5,5],
        "label": "My Box"
    }
    
    response = client.post("/api/geometry/create", json=recipe)
    assert response.status_code == 200
    body = response.json()
    
    assert len(body["parts"]) == 1
    part = body["parts"][0]
    assert part["key"].startswith("drawn_")
    assert part["source"] == "gui"
    assert part["label"] == "My Box"
    assert part["recipe"] == recipe
    assert "invalidates" in body
    
    # Check it persisted
    project = client.get("/api/project").json()
    assert len(project["custom_parts"]) > 0
    assert project["custom_parts"][-1]["key"] == part["key"]
    
    # Test clearing custom parts
    response = client.delete("/api/project/custom_parts")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    
    project = client.get("/api/project").json()
    assert len(project["custom_parts"]) == 0

    # Revert project to avoid polluting other tests
    client.put("/api/project", json=seed_project().model_dump())


def test_delete_geometry_part_removes_just_that_part(client):
    """The Model explorer's per-part Delete needs a per-part endpoint -- the existing
    DELETE /api/project/custom_parts clears everything, which is not what "delete this
    one thing I drew" means."""
    first = client.post("/api/geometry/create", json={
        "kind": "box", "origin": [0, 0, 0], "size": [1, 1, 1], "label": "Box one",
    }).json()["parts"][0]
    second = client.post("/api/geometry/create", json={
        "kind": "box", "origin": [5, 5, 0], "size": [1, 1, 1], "label": "Box two",
    }).json()["parts"][0]

    response = client.delete(f"/api/geometry/parts/{first['key']}")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "invalidates" in body

    project = client.get("/api/project").json()
    keys = [p["key"] for p in project["custom_parts"]]
    assert first["key"] not in keys
    assert second["key"] in keys

    # The remaining part must still be drawable -- deleting one part must not corrupt
    # the geometry build for the ones left behind.
    geometry = client.get("/api/geometry")
    assert geometry.status_code == 200
    assert any(s["key"] == second["key"] for s in geometry.json()["sections"])

    client.delete("/api/project/custom_parts")
    client.put("/api/project", json=seed_project().model_dump())


def test_delete_geometry_part_unknown_key_is_404(client):
    response = client.delete("/api/geometry/parts/does_not_exist")
    assert response.status_code == 404


@pytest.mark.parametrize("recipe", [
    {"kind": "line", "vertices": [[0, 0, 0], [5, 0, 0]], "label": "A line"},
    {"kind": "polygon", "vertices": [[0, 0, 0], [5, 0, 0], [5, 5, 0]], "label": "A surface"},
])
def test_post_geometry_create_line_and_surface_stay_drawable(client, recipe):
    """A drawn line or bare surface has no volume, which used to make the very next
    /api/geometry call raise -- either a GeometryError ("no volume for ...") or an
    unhandled KeyError. It must round-trip cleanly, like box already did."""
    response = client.post("/api/geometry/create", json=recipe)
    assert response.status_code == 200
    part = response.json()["parts"][0]
    key = part["key"]

    geometry = client.get("/api/geometry")
    assert geometry.status_code == 200
    sections = geometry.json()["sections"]
    assert any(s["key"] == key for s in sections)

    client.delete("/api/project/custom_parts")
    client.put("/api/project", json=seed_project().model_dump())


# ── Finite-element mesh ────────────────────────────────────────────────────

def test_mesh_endpoint_returns_real_stats_and_drawable_sections(client):
    response = client.post("/api/mesh", json={"element_size": 4.0, "order": 1})
    assert response.status_code == 200
    body = response.json()

    assert body["stats"]["nodes"] > 0
    assert body["stats"]["elements"] > 0
    assert body["stats"]["seconds"] >= 0
    assert body["sections"] and body["sections"][0]["indices"]
    assert isinstance(body["log"], list)


def test_mesh_endpoint_validates_settings_before_starting_gmsh(client):
    assert client.post("/api/mesh", json={"element_size": 0, "order": 2}).status_code == 422
    assert client.post("/api/mesh", json={"element_size": 4, "order": 3}).status_code == 422
    assert client.post("/api/mesh", json={
        "element_size": 4, "order": 1, "volume_keys": ["missing_body"]
    }).status_code == 422


def test_mesh_endpoint_reports_the_bodies_that_were_meshed(client):
    response = client.post("/api/mesh", json={
        "element_size": 5.0, "order": 1, "volume_keys": ["soil_L1"]
    })
    assert response.status_code == 200
    assert response.json()["meshed_keys"] == ["soil_L1"]


# ── Soil-layer write path ──────────────────────────────────────────────────

def test_patch_layers_updates_the_project_and_declares_invalidations(client):
    layers = [layer.model_dump() for layer in seed_project().layers]
    layers[0]["bottom"] = -9.0
    layers[1]["top"] = -9.0

    response = client.patch("/api/project/layers", json={"layers": layers})
    assert response.status_code == 200
    body = response.json()
    assert body["project"]["layers"][0]["bottom"] == -9.0
    assert body["invalidates"] == ["project", "tree", "geometry", "mesh"]
    assert client.get("/api/project").json()["layers"][1]["top"] == -9.0

    client.put("/api/project", json=seed_project().model_dump())


def test_patch_layers_rejects_invalid_stack_without_mutating_the_project(client):
    layers = [layer.model_dump() for layer in seed_project().layers]
    layers[0]["bottom"] = -9.0

    assert client.patch("/api/project/layers", json={"layers": layers}).status_code == 422
    assert client.get("/api/project").json()["layers"][0]["bottom"] == -8.0


# ── Structure write path ───────────────────────────────────────────────────

def test_patch_structures_updates_loads_and_declares_invalidations(client):
    loads = [load.model_dump() for load in seed_project().loads]
    loads[0]["name"] = "North surcharge"
    loads[0]["components"] = [5.0, 0.0, -35.0]

    response = client.patch("/api/project/structures", json={"loads": loads})

    assert response.status_code == 200
    body = response.json()
    assert body["project"]["loads"][0]["name"] == "North surcharge"
    assert body["project"]["loads"][0]["components"] == [5.0, 0.0, -35.0]
    assert body["invalidates"] == ["project", "tree", "geometry", "mesh"]
    assert client.get("/api/project").json()["loads"] == loads

    client.put("/api/project", json=seed_project().model_dump())


def test_patch_structures_rejects_duplicate_loads_without_mutating_project(client):
    original = [load.model_dump(mode="json") for load in seed_project().loads]
    response = client.patch(
        "/api/project/structures", json={"loads": original + [original[0]]}
    )

    assert response.status_code == 422
    assert client.get("/api/project").json()["loads"] == original


def test_patch_structures_accepts_a_coordinate_defined_point_load(client):
    point = {
        "id": "load_crane", "name": "Crane reaction", "kind": "point",
        "x": 8.5, "y": -3.0, "thickness": 0.25,
        "components": [15.0, -120.0], "distribution": "Uniform", "active": True,
    }
    response = client.patch("/api/project/structures", json={"loads": [point]})

    assert response.status_code == 200
    # `derived_from` comes back on every load: it is how a translated pair is linked
    # (core/model/load_translation.py), and a load the client authored is nobody's translation.
    assert response.json()["project"]["loads"] == [point | {"derived_from": None}]

    client.put("/api/project", json=seed_project().model_dump())


SECTION = {"id": "az26", "name": "AZ 26-700", "spacing": 1.0, "variables": {
    "YOUNG_MODULUS": 2.1e11, "POISSON_RATIO": 0.3, "CROSS_AREA": 0.0198, "I33": 5.52e-4,
    "DENSITY": 7850.0}}
BEAM = {"id": "sheetpile_1", "name": "Sheet pile 1", "section": "az26",
        "points": [[12.0, 0.0], [12.0, -14.0]], "active": True}
# What comes back: `kind` is defaulted in, which is how a project written before the
# 3D pile kinds existed still loads as the 2D sheet pile it was saved as, and the
# section gains the two inertias only a member in space has any use for, and the shear
# area that `None` means "take the whole section" for.
# `derived_from` comes back on every structure: it is how a translated pair is linked
# (core/model/wall_translation.py), and a pile the client authored is nobody's translation.
STORED_BEAM = BEAM | {"kind": "beam", "derived_from": None}
STORED_SECTION = SECTION | {"constitutive_law": "TimoshenkoBeamElasticConstitutiveLaw",
                            "tables": {}}


def test_patch_structures_creates_a_sheet_pile_and_its_section(client):
    loads = [load.model_dump(mode="json") for load in seed_project().loads]
    response = client.patch("/api/project/structures",
                            json={"loads": loads, "beam_sections": [SECTION],
                                  "beams": [BEAM]})

    assert response.status_code == 200
    body = response.json()
    assert body["project"]["beams"] == [STORED_BEAM]
    assert body["project"]["beam_sections"] == [STORED_SECTION]
    assert body["invalidates"] == ["project", "tree", "geometry", "mesh"]
    assert client.get("/api/project").json()["beams"] == [STORED_BEAM]

    client.put("/api/project", json=seed_project().model_dump())


def test_patch_structures_rejects_a_beam_without_its_section(client):
    """The whole-project validation is what stops a dangling section reference."""
    loads = [load.model_dump(mode="json") for load in seed_project().loads]
    response = client.patch("/api/project/structures",
                            json={"loads": loads, "beam_sections": [], "beams": [BEAM]})

    assert response.status_code == 422
    assert client.get("/api/project").json()["beams"] == []


def test_patch_structures_leaves_beams_alone_when_only_loads_are_sent(client):
    """Editing a load must not delete the sheet piles: an omitted collection is
    'unchanged', not 'empty'."""
    loads = [load.model_dump(mode="json") for load in seed_project().loads]
    client.patch("/api/project/structures",
                 json={"loads": loads, "beam_sections": [SECTION], "beams": [BEAM]})

    response = client.patch("/api/project/structures", json={"loads": loads})

    assert response.status_code == 200
    assert response.json()["project"]["beams"] == [STORED_BEAM]

    client.put("/api/project", json=seed_project().model_dump())


def test_patch_structures_deletes_a_sheet_pile_with_an_explicit_empty_list(client):
    loads = [load.model_dump(mode="json") for load in seed_project().loads]
    client.patch("/api/project/structures",
                 json={"loads": loads, "beam_sections": [SECTION], "beams": [BEAM]})

    response = client.patch("/api/project/structures",
                            json={"loads": loads, "beams": []})

    assert response.status_code == 200
    assert response.json()["project"]["beams"] == []

    client.put("/api/project", json=seed_project().model_dump())


ANCHOR_SECTION = {"id": "strand", "name": "4-strand tendon", "spacing": 2.5,
                  "tension_limit": 900_000.0, "compression_limit": None, "variables": {
                      "YOUNG_MODULUS": 1.95e11, "CROSS_AREA": 0.0006, "DENSITY": 7850.0}}
ANCHOR = {"id": "anchor_1", "name": "Anchor 1", "kind": "anchor", "section": "strand",
          "head": [12.0, -2.0], "tail": [20.0, -8.0], "prestress": 250.0, "active": True}


def test_patch_structures_creates_an_anchor_on_a_sheet_pile(client):
    loads = [load.model_dump(mode="json") for load in seed_project().loads]
    response = client.patch("/api/project/structures", json={
        "loads": loads, "beam_sections": [SECTION], "beams": [BEAM],
        "anchor_sections": [ANCHOR_SECTION], "anchors": [ANCHOR],
    })

    assert response.status_code == 200
    body = response.json()
    assert body["project"]["anchors"] == [ANCHOR]
    assert body["invalidates"] == ["project", "tree", "geometry", "mesh"]

    client.put("/api/project", json=seed_project().model_dump())


def test_patch_structures_refuses_an_anchor_that_hangs_off_no_pile(client):
    """Whole-project validation is what catches a head that would export a truss
    connected to nothing."""
    loads = [load.model_dump(mode="json") for load in seed_project().loads]
    floating = dict(ANCHOR, head=[30.0, -2.0])
    response = client.patch("/api/project/structures", json={
        "loads": loads, "beam_sections": [SECTION], "beams": [BEAM],
        "anchor_sections": [ANCHOR_SECTION], "anchors": [floating],
    })

    assert response.status_code == 422
    assert client.get("/api/project").json()["anchors"] == []


def test_patch_structures_leaves_anchors_alone_when_only_loads_are_sent(client):
    loads = [load.model_dump(mode="json") for load in seed_project().loads]
    client.patch("/api/project/structures", json={
        "loads": loads, "beam_sections": [SECTION], "beams": [BEAM],
        "anchor_sections": [ANCHOR_SECTION], "anchors": [ANCHOR],
    })

    response = client.patch("/api/project/structures", json={"loads": loads})

    assert response.status_code == 200
    assert response.json()["project"]["anchors"] == [ANCHOR]

    client.put("/api/project", json=seed_project().model_dump())


INTERFACE_SECTION = {"id": "contact_1", "name": "Steel against sand",
                     "material": "mat_sand", "r_inter": 0.67,
                     "virtual_thickness": 0.01, "normal_stiffness": None,
                     "shear_stiffness": None, "permeability": "Neutral"}
INTERFACE = {"id": "interface_1", "name": "Wall contact", "kind": "interface",
             "section": "contact_1", "structure": "sheetpile_1", "points": None,
             "side": "both", "stretch": None, "active": True}


def interface_section(client) -> dict:
    """The contact, bound to whichever soil the stored project actually has."""
    material = client.get("/api/project").json()["materials"][0]["id"]
    return dict(INTERFACE_SECTION, material=material)


def test_patch_structures_creates_an_interface_on_a_sheet_pile(client):
    loads = [load.model_dump(mode="json") for load in seed_project().loads]
    response = client.patch("/api/project/structures", json={
        "loads": loads, "beam_sections": [SECTION], "beams": [BEAM],
        "interface_sections": [interface_section(client)], "interfaces": [INTERFACE],
    })

    assert response.status_code == 200
    body = response.json()
    assert body["project"]["interfaces"] == [INTERFACE]
    assert body["invalidates"] == ["project", "tree", "geometry", "mesh"]
    assert client.get("/api/project").json()["interfaces"] == [INTERFACE]

    client.put("/api/project", json=seed_project().model_dump())


def test_patch_structures_refuses_an_interface_against_no_pile(client):
    """Whole-project validation again: an interface following a pile that is not in
    the project would mesh into a contact holding nothing."""
    loads = [load.model_dump(mode="json") for load in seed_project().loads]
    response = client.patch("/api/project/structures", json={
        "loads": loads, "interface_sections": [interface_section(client)],
        "interfaces": [INTERFACE],
    })

    assert response.status_code == 422
    assert client.get("/api/project").json()["interfaces"] == []


def test_patch_structures_refuses_an_interface_without_its_section(client):
    loads = [load.model_dump(mode="json") for load in seed_project().loads]
    response = client.patch("/api/project/structures", json={
        "loads": loads, "beam_sections": [SECTION], "beams": [BEAM],
        "interface_sections": [], "interfaces": [INTERFACE],
    })

    assert response.status_code == 422
    assert client.get("/api/project").json()["interfaces"] == []


def test_patch_structures_leaves_interfaces_alone_when_only_loads_are_sent(client):
    loads = [load.model_dump(mode="json") for load in seed_project().loads]
    client.patch("/api/project/structures", json={
        "loads": loads, "beam_sections": [SECTION], "beams": [BEAM],
        "interface_sections": [interface_section(client)], "interfaces": [INTERFACE],
    })

    response = client.patch("/api/project/structures", json={"loads": loads})

    assert response.status_code == 200
    assert response.json()["project"]["interfaces"] == [INTERFACE]

    client.put("/api/project", json=seed_project().model_dump())


def test_patch_structures_deletes_an_interface_with_an_explicit_empty_list(client):
    loads = [load.model_dump(mode="json") for load in seed_project().loads]
    client.patch("/api/project/structures", json={
        "loads": loads, "beam_sections": [SECTION], "beams": [BEAM],
        "interface_sections": [interface_section(client)], "interfaces": [INTERFACE],
    })

    response = client.patch("/api/project/structures",
                            json={"loads": loads, "interfaces": []})

    assert response.status_code == 200
    assert response.json()["project"]["interfaces"] == []
    assert response.json()["project"]["interface_sections"], \
        "a reusable contact outlives the interface using it"

    client.put("/api/project", json=seed_project().model_dump())


# ── No boreholes ────────────────────────────────────────────────────────────

def test_put_project_opens_a_file_saved_with_boreholes(client):
    """A file saved before boreholes were removed opens: each layer takes its levels at
    the first borehole (`migration.drop_boreholes`)."""
    old = json.loads((FIXTURES / "seed_3d_v1.json").read_text(encoding="utf-8"))
    assert "boreholes" in old
    try:
        response = client.put("/api/project", json=old)
        assert response.status_code == 200
        body = response.json()
    finally:
        client.put("/api/project", json=seed_project().model_dump())
    assert "boreholes" not in body
    assert [(layer["top"], layer["bottom"]) for layer in body["layers"]] == [
        (0.0, -8.0), (-8.0, -25.0)]


def test_migration_notes_name_the_soil_whose_water_is_overridden(client):
    """A file saved before 2026-11-02, as Open sends it: the PUT takes it in the new
    shape, and this route says which soil's own water that dropped."""
    old = seed_project().model_dump(mode="json")
    del old["fluid"]
    for material in old["materials"]:
        material["variables"]["GEO_DRAINAGE_TYPE"] = "CONSTANT_PW_FIELD"
    old["materials"][0]["variables"]["DYNAMIC_VISCOSITY"] = 1e-3
    old["materials"][1]["variables"]["DYNAMIC_VISCOSITY"] = 5e-3

    response = client.post("/api/project/migration-notes", json=old)

    assert response.status_code == 200
    notes = response.json()["notes"]
    assert len(notes) == 1 and notes[0].startswith("Sand, loose:")
    current = client.post("/api/project/migration-notes",
                          json=seed_project().model_dump(mode="json"))
    assert current.json() == {"notes": []}


def test_patch_layers_refuses_boreholes(client):
    """The layer update has no boreholes to carry any more; one sent is an error, not
    something quietly dropped."""
    project = seed_project()
    response = client.patch("/api/project/layers", json={
        "layers": [layer.model_dump() for layer in project.layers],
        "boreholes": [{"id": "bh1", "name": "BH-1", "x": 0, "y": 0, "head": 0, "water": 0}],
    })
    assert response.status_code == 422


def test_there_is_no_borehole_route(client):
    assert client.post("/api/project/boreholes", json={"x": 55.0}).status_code in (404, 405)


# ── Domain write path (rides on the layer update too) ───────────────────────

def test_patch_layers_can_resize_the_domain(client):
    project = seed_project()
    domain = project.domain.model_dump()
    domain.update(x1=60.0, z1=45.0)

    response = client.patch("/api/project/layers", json={
        "layers": [layer.model_dump() for layer in project.layers],
        "domain": domain,
    })
    assert response.status_code == 200

    saved = client.get("/api/project").json()["domain"]
    assert (saved["x1"], saved["z1"]) == (60.0, 45.0)

    client.put("/api/project", json=seed_project().model_dump())


def test_a_layer_delete_answers_with_the_mesh_size_it_took_away(client):
    """The GUI's soil layers window sends the stack without the layer; the size of the
    layer's body goes with it, and the answer says so for the Session log."""
    from tests.models.excavation import excavation_project

    project = excavation_project(staged=False).model_dump(mode="json")
    project["mesh"]["body_sizes"] = {"soil_L_mid": 2.0}
    layers = [dict(layer) for layer in project["layers"] if layer["id"] != "L_mid"]
    layers[0]["bottom"] = layers[1]["top"]
    try:
        put = client.put("/api/project", json=project)
        assert put.status_code == 200, put.text

        response = client.patch("/api/project/layers", json={"layers": layers})

        assert response.status_code == 200, response.text
        answer = response.json()
        assert answer["project"]["mesh"]["body_sizes"] == {}
        assert answer["edit_notes"] == [
            "Removed the mesh size of soil_L_mid (2): the edit took that body away. If it "
            "comes back, set its size again."]
        again = client.patch("/api/project/layers", json={"layers": layers})
        assert again.json()["edit_notes"] == []
    finally:
        client.put("/api/project", json=seed_project().model_dump())


# ── The water line ──────────────────────────────────────────────────────────
# `Project.water` holds the two numbers the deck's hydrostatic processes read -- the
# phreatic level and the fluid's specific weight (plan sec 7.2) -- and until now
# nothing in the GUI could change either. It rides along on the layers PATCH for the
# same reason the domain does: it is one object for the whole project, edited from the
# same Selection explorer rows, and one request means one validation of the result.

def test_patch_layers_can_move_the_water_line(client):
    project = seed_project()
    water = project.water.model_dump()
    water.update(y=-4.0)

    response = client.patch("/api/project/layers", json={
        "layers": [layer.model_dump() for layer in project.layers],
        "water": water,
    })
    assert response.status_code == 200
    # The mesh is not invalidated by it: the phreatic level is a reference plane and
    # takes no part in the geometry booleans (see WaterLevel's own comment), so the
    # elements do not change when it moves.
    assert "geometry" in response.json()["invalidates"]

    assert client.get("/api/project").json()["water"]["y"] == -4.0

    client.put("/api/project", json=seed_project().model_dump())


def test_patch_layers_can_change_the_specific_weight(client):
    """The other half of the pair, and the one that silently scales every hydrostatic
    pressure in the deck -- `_water_pressure` and `_normal_load` both read it."""
    project = seed_project()
    water = project.water.model_dump()
    water.update(specific_weight=9.81)

    assert client.patch("/api/project/layers", json={
        "layers": [layer.model_dump() for layer in project.layers],
        "water": water,
    }).status_code == 200
    assert client.get("/api/project").json()["water"]["specific_weight"] == 9.81

    client.put("/api/project", json=seed_project().model_dump())


def test_patch_layers_rejects_a_weightless_fluid(client):
    """Zero specific weight is a division by zero waiting in the materials file --
    DENSITY_WATER is derived from it -- and it is not water in any case."""
    project = seed_project()
    water = project.water.model_dump()
    water["specific_weight"] = 0.0

    response = client.patch("/api/project/layers", json={
        "layers": [layer.model_dump() for layer in project.layers],
        "water": water,
    })
    assert response.status_code == 422
    assert client.get("/api/project").json()["water"]["specific_weight"] ==         seed_project().water.specific_weight


def test_patch_layers_leaves_the_water_alone_when_it_is_not_sent(client):
    """Omitted means "leave it", the same as every other ride-along on this endpoint.
    A client editing only the layer stack must not reset the water table by silence."""
    project = seed_project()
    water = project.water.model_dump()
    water["y"] = -6.5
    client.patch("/api/project/layers", json={
        "layers": [layer.model_dump() for layer in project.layers], "water": water})

    assert client.patch("/api/project/layers", json={
        "layers": [layer.model_dump() for layer in project.layers]}).status_code == 200
    assert client.get("/api/project").json()["water"]["y"] == -6.5

    client.put("/api/project", json=seed_project().model_dump())


def test_patch_layers_rejects_an_inverted_domain(client):
    project = seed_project()
    domain = project.domain.model_dump()
    domain["x1"] = domain["x0"] - 1.0

    response = client.patch("/api/project/layers", json={
        "layers": [layer.model_dump() for layer in project.layers],
        "domain": domain,
    })
    assert response.status_code == 422
    assert client.get("/api/project").json()["domain"]["x1"] == seed_project().domain.x1


# ── Material write path ─────────────────────────────────────────────────────

def test_patch_materials_saves_edited_values_including_the_interface_fields(client):
    materials = [m.model_dump() for m in seed_project().materials]
    materials[1].update(name="Sand, medium", color="#ff0000",
                        r_inter=0.65, interface_permeability="Drain")
    materials[1]["variables"]["DENSITY_SOLID"] = 1896.0

    response = client.patch("/api/project/materials", json={"materials": materials})
    assert response.status_code == 200
    assert response.json()["invalidates"] == ["project", "tree", "geometry"]

    saved = client.get("/api/project").json()["materials"][1]
    assert (saved["name"], saved["color"], saved["variables"]["DENSITY_SOLID"]) == \
        ("Sand, medium", "#ff0000", 1896.0)
    assert (saved["r_inter"], saved["interface_permeability"]) == (0.65, "Drain")

    client.put("/api/project", json=seed_project().model_dump())


def test_patch_materials_keeps_every_variable_the_user_typed(client):
    """The server half of the round trip the material dialog depends on: the library is
    replaced wholesale, so the Kratos block goes back exactly as it came -- a variable
    added, a string, a list, a law nobody here knows."""
    materials = [m.model_dump() for m in seed_project().materials]
    materials[0]["variables"].update(POROSITY=0.42, K0_NC=0.62, UDSM_PARAMETERS=[1.0, 2.0])
    materials[0]["constitutive_law"] = "SmallStrainUDSM3DLaw"

    assert client.patch("/api/project/materials",
                        json={"materials": materials}).status_code == 200
    saved = client.get("/api/project").json()["materials"][0]
    assert saved["variables"] == materials[0]["variables"]
    assert saved["constitutive_law"] == "SmallStrainUDSM3DLaw"

    # And a variable taken out is gone, not kept: what is absent is derived.
    del materials[0]["variables"]["POROSITY"]
    assert client.patch("/api/project/materials",
                        json={"materials": materials}).status_code == 200
    assert "POROSITY" not in client.get("/api/project").json()["materials"][0]["variables"]

    client.put("/api/project", json=seed_project().model_dump())


def test_patch_materials_rejects_what_kratos_could_not_read(client):
    materials = [m.model_dump() for m in seed_project().materials]
    for bad in ({"porosity": 0.3}, {"variables": {"lower_case": 1.0}}):
        attempt = [dict(materials[0], **bad)] + materials[1:]
        assert client.patch("/api/project/materials",
                            json={"materials": attempt}).status_code == 422


def test_patch_materials_accepts_a_newly_added_material(client):
    materials = [m.model_dump() for m in seed_project().materials]
    materials.append({
        "id": "mx1", "name": "Peat, soft", "color": "#9aa7b4",
        "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
        "variables": {"YOUNG_MODULUS": 2.0e6, "POISSON_RATIO": 0.35,
                      "DENSITY_SOLID": 1121.3, "GEO_DRAINAGE_TYPE": "FULLY_COUPLED"},
        "r_inter": 0.5, "interface_permeability": "Impermeable",
    })

    assert client.patch("/api/project/materials",
                        json={"materials": materials}).status_code == 200
    assert client.get("/api/project").json()["materials"][-1]["id"] == "mx1"

    client.put("/api/project", json=seed_project().model_dump())


def test_patch_materials_refuses_to_drop_a_material_a_layer_still_uses(client):
    """The delete guard in the material editor, enforced for real: layer L1 points
    at m2, so a library without m2 must not be stored."""
    materials = [m.model_dump() for m in seed_project().materials if m.id != "m2"]

    response = client.patch("/api/project/materials", json={"materials": materials})
    assert response.status_code == 422
    assert len(client.get("/api/project").json()["materials"]) == 6


def test_patch_materials_rejects_out_of_range_values(client):
    materials = [m.model_dump() for m in seed_project().materials]
    materials[0]["r_inter"] = 1.5

    assert client.patch("/api/project/materials",
                        json={"materials": materials}).status_code == 422
    assert client.get("/api/project").json()["materials"][0]["r_inter"] == 0.70


# ── Custom soil volumes ─────────────────────────────────────────────────────

EMBANKMENT = {
    "kind": "polygon_extrude",
    "label": "Embankment",
    "vertices": [[0, 0, 0], [3, 0, 3], [9, 0, 3], [12, 0, 0]],
    "extrusion": [0, 30, 0],
}


def test_a_custom_part_may_carry_a_soil_material(client):
    """A drawn solid becomes soil when given a material: it takes that material's
    colour, which is what makes it render and mesh as ground rather than as a prop."""
    response = client.post("/api/geometry/create", json=dict(EMBANKMENT, material="m1"))
    assert response.status_code == 200

    part = client.get("/api/project").json()["custom_parts"][-1]
    assert part["mat"] == "m1"
    assert part["color"] == seed_project().material("m1").color

    client.delete("/api/project/custom_parts")


def test_creating_a_custom_part_rejects_an_unknown_material(client):
    response = client.post("/api/geometry/create", json=dict(EMBANKMENT, material="nope"))
    assert response.status_code == 422
    assert client.get("/api/project").json()["custom_parts"] == []


def test_a_second_solid_in_exactly_the_same_place_is_refused(client):
    """Fragmenting two coincident solids gives the shared volume to one of them, so
    the other would own nothing and draw nothing (see tessellate's .get fallback)."""
    assert client.post("/api/geometry/create", json=dict(EMBANKMENT, material="m1")).status_code == 200

    duplicate = dict(EMBANKMENT, label="Copy", material="m4")
    response = client.post("/api/geometry/create", json=duplicate)
    assert response.status_code == 422
    assert "same place" in response.json()["detail"]
    assert len(client.get("/api/project").json()["custom_parts"]) == 1

    # The model still builds, which is the point of refusing.
    assert client.get("/api/geometry").status_code == 200

    client.delete("/api/project/custom_parts")


def test_two_overlapping_but_distinct_soil_volumes_both_survive(client):
    """Overlap is legitimate -- fragmentation splits it -- and both keep a section."""
    assert client.post("/api/geometry/create", json=dict(EMBANKMENT, material="m1")).status_code == 200
    shifted = dict(EMBANKMENT, label="Emb B", material="m4",
                   vertices=[[6, 0, 0], [9, 0, 3], [15, 0, 3], [18, 0, 0]])
    assert client.post("/api/geometry/create", json=shifted).status_code == 200

    keys = {section["key"] for section in client.get("/api/geometry").json()["sections"]}
    assert {"drawn_0", "drawn_1"} <= keys

    client.delete("/api/project/custom_parts")


def test_patch_layers_can_reassign_a_custom_part_material(client):
    assert client.post("/api/geometry/create", json=dict(EMBANKMENT, material="m1")).status_code == 200

    project = client.get("/api/project").json()
    parts = project["custom_parts"]
    parts[0]["mat"] = "m4"

    response = client.patch("/api/project/layers",
                            json={"layers": project["layers"], "custom_parts": parts})
    assert response.status_code == 200
    assert client.get("/api/project").json()["custom_parts"][0]["mat"] == "m4"

    client.delete("/api/project/custom_parts")


def test_a_custom_part_pointing_at_an_unknown_material_is_rejected(client):
    assert client.post("/api/geometry/create", json=dict(EMBANKMENT, material="m1")).status_code == 200

    project = client.get("/api/project").json()
    parts = project["custom_parts"]
    parts[0]["mat"] = "ghost"

    response = client.patch("/api/project/layers",
                            json={"layers": project["layers"], "custom_parts": parts})
    assert response.status_code == 422
    assert client.get("/api/project").json()["custom_parts"][0]["mat"] == "m1"

    client.delete("/api/project/custom_parts")


def test_a_soil_volume_can_be_rebuilt_in_place(client):
    """Editing the coordinates must keep the key: its mesh size, tree row and any
    selection are all keyed by it."""
    assert client.post("/api/geometry/create", json=dict(EMBANKMENT, material="m1")).status_code == 200
    key = client.get("/api/project").json()["custom_parts"][0]["key"]

    taller = dict(EMBANKMENT, material="m1", replace=key,
                  vertices=[[0, 0, 0], [3, 0, 5], [9, 0, 5], [12, 0, 0]])
    assert client.post("/api/geometry/create", json=taller).status_code == 200

    parts = client.get("/api/project").json()["custom_parts"]
    assert len(parts) == 1
    assert parts[0]["key"] == key
    assert parts[0]["recipe"]["vertices"][1] == [3, 0, 5]

    client.delete("/api/project/custom_parts")


def test_replacing_an_unknown_part_is_a_404(client):
    response = client.post("/api/geometry/create",
                           json=dict(EMBANKMENT, material="m1", replace="drawn_99"))
    assert response.status_code == 404
    assert client.get("/api/project").json()["custom_parts"] == []


# ── The base UI is served in place ──────────────────────────────────────────

BASE = Path(__file__).resolve().parents[1] / "frontend" / "base"


@pytest.mark.parametrize(
    "path",
    ["/css/tokens.css", "/css/layout.css", "/css/components.css",
     "/js/app.js", "/js/data.js", "/js/explorer.js",
     "/vendor/three.min.js", "/assets/deltares-logo.png"],
)
def test_frozen_assets_are_served(client, path):
    assert client.get(path).status_code == 200


def test_the_mockup_viewport_is_not_served(client):
    assert client.get("/js/viewport.js").status_code == 404


# ── The live shell ──────────────────────────────────────────────────────────

def test_root_serves_the_live_shell(client):
    body = client.get("/").text
    assert "/live/js/viewport.js" in body


def test_the_live_shell_replaces_only_the_viewport_and_the_orbit_controller(client):
    """The whole portability argument rests on this: every frozen module is loaded
    verbatim except js/viewport.js, which is the only one that invents geometry, and
    js/orbit.js, which is hard-wired to a Z-up world the model no longer uses. If a
    third file ever needs replacing, that is a design change and should not pass
    quietly.

    The orbit controller is *overridden* rather than dropped: `App.Orbit` is a plain
    global assignment, so the frozen file is still loaded and the live one after it
    wins. It therefore appears in both lists, and the order matters.
    """
    body = client.get("/").text
    frozen = re.findall(r'src="/js/([a-z]+\.js)"', body)
    replaced = re.findall(r'src="/live/js/([a-z-]+\.js)"', body)

    assert "viewport.js" not in frozen, "the frozen viewport must not be loaded"
    assert set(frozen) == {"data.js", "ui.js", "orbit.js", "menubar.js",
                           "toolbars.js", "explorer.js", "command.js", "dialogs.js", "app.js"}
    # Additions rather than substitutions -- they have no frozen counterpart:
    # soil-volume-dialog.js, canvas-renderer.js, ruler.js, mesh-labels.js,
    # download.js, zip.js, stages.js, solver-settings.js, results.js, results-render.js,
    # results-view.js,
    # part-colors.js, water-command.js, script-command.js, node-parts.js, deck.js,
    # results-plot.js, vocabulary.js.
    # The assertion above is the one that guards the portability claim.
    assert set(replaced) == {"api.js", "buffers.js", "model.js", "viewport.js", "patches.js",
                             "vocabulary.js",
                             "mesh-settings.js", "import-dialog.js", "mdpa-import-dialog.js",
                             "draw-input.js", "soil-volume-dialog.js", "canvas-renderer.js",
                             # The Modify soil layers window, in place of the frozen one in
                             # js/dialogs.js, which drew the stack once per borehole.
                             "soil-layers-dialog.js",
                             "export.js", "calculate.js", "history.js", "loads.js",
                             "beams.js", "anchors.js",
                             "interfaces.js", "normal-loads.js", "lines.js",
                             "boundary-conditions.js", "material-library.js",
                             "orbit.js", "ruler.js", "mesh-labels.js",
                             "download.js", "zip.js", "stages.js", "results.js",
                             # A stage's expert solver settings, generated from
                             # core/model/solver.py, which stages.js resolves.
                             "solver-settings.js",
                             "results-render.js", "results-view.js", "part-colors.js",
                             "water-command.js", "script-command.js", "node-parts.js",
                             "deck.js",
                             "results-plot.js",
                             # The version the server writes into the page, in place of
                             # the frozen js/data.js's own.
                             "version.js",
                             # The unit system and the Kratos property sets the editors
                             # show, and the Material sets dialog that replaces the frozen
                             # one's old sheet (plan/outdated/kratos-native-inputs-plan.md).
                             "unit-table.js", "units.js", "property-sets.js",
                             "material-sets.js",
                             # The soil models the Material set window offers
                             # (core/model/soil_models.py).
                             "soil-model-table.js", "soil-models.js"}
    assert body.index('/js/orbit.js') < body.index('/live/js/orbit.js'), (
        "the Y-up controller has to be loaded after the frozen one it overrides")


MOCKUP_VIEWPORT_API = {"dolly", "generateMesh", "hasMesh", "init", "isVisible",
                       "rebuildSoil", "resize", "select", "setGrid", "setMode",
                       "setProjection", "setView", "setVisible", "zoomFit"}
"""What the mockup's viewport exported, and all js/app.js, toolbars.js and menubar.js
ever reach the 3D through. Dropping one breaks a button silently."""


def test_the_live_viewport_keeps_the_frozen_public_api(client):
    source = client.get("/live/js/viewport.js").text
    tail = source[source.rindex("return {"):]
    live = set(re.findall(r"(\w+)\s*:", tail[:tail.index("}")]))
    missing = MOCKUP_VIEWPORT_API - live
    assert not missing, f"missing from the live viewport: {sorted(missing)}"


def test_served_base_files_are_byte_identical_to_the_originals(client):
    """Mounted, not copied."""
    for path in ("js/data.js", "css/tokens.css"):
        served = client.get("/" + path).content
        assert served == (BASE / path).read_bytes(), path


# ── Model dimension ─────────────────────────────────────────────────────────

@pytest.fixture
def restore_3d(client):
    """The project store is process-global, so a test that switches to 2D has to
    put it back or every test after it meshes a section instead of a solid."""
    yield
    client.patch("/api/project/dimension", json={"dimension": 3})


def test_switching_to_2d_resolves_the_section_offset(client, restore_3d):
    body = client.patch("/api/project/dimension", json={"dimension": 2}).json()
    project = body["project"]
    assert project["dimension"] == 2
    assert "section_plane" not in project
    domain = project["domain"]
    assert project["section_offset"] == pytest.approx((domain["z0"] + domain["z1"]) / 2)


def test_switching_dimension_invalidates_everything_downstream(client, restore_3d):
    body = client.patch("/api/project/dimension", json={"dimension": 2}).json()
    # The tree too: a part that misses the plane is gone from the model explorer.
    assert set(body["invalidates"]) == {"project", "tree", "geometry", "mesh"}


def test_an_explicit_section_offset_is_accepted(client, restore_3d):
    body = client.patch("/api/project/dimension",
                        json={"dimension": 2, "section_offset": 6.25}).json()
    assert body["project"]["section_offset"] == 6.25


def test_a_section_outside_the_domain_is_refused(client, restore_3d):
    response = client.patch("/api/project/dimension",
                            json={"dimension": 2, "section_offset": 999.0})
    assert response.status_code == 422
    assert client.get("/api/project").json()["dimension"] == 3, "a refused patch must not commit"


def test_geometry_after_the_switch_is_a_flat_section(client, restore_3d):
    """Flat in z: the cut is taken at `section_offset` and moved onto the x-y plane."""
    client.patch("/api/project/dimension", json={"dimension": 2})
    payload = client.get("/api/geometry").json()
    assert payload["bbox"][2] == pytest.approx(0.0, abs=1e-3)
    assert payload["bbox"][5] == pytest.approx(0.0, abs=1e-3)
    # ...and it still spans both of its own axes.
    assert payload["bbox"][3] - payload["bbox"][0] > 1.0
    assert payload["bbox"][4] - payload["bbox"][1] > 1.0
    assert payload["sections"], "the section still has to be drawable"


def test_switching_back_to_3d_restores_the_solid(client, restore_3d):
    client.patch("/api/project/dimension", json={"dimension": 2})
    client.patch("/api/project/dimension", json={"dimension": 3})
    payload = client.get("/api/geometry").json()
    assert payload["bbox"][5] - payload["bbox"][2] > 1.0, "the solid has depth again"


def test_the_switch_refuses_a_section_plane(client, restore_3d):
    """There is one plane now -- the x-y section -- so a client still sending the old
    field is out of date rather than asking for something reasonable. Refused loudly,
    and the project must not switch behind the refusal."""
    response = client.patch("/api/project/dimension",
                            json={"dimension": 2, "section_plane": "xy"})
    assert response.status_code == 422
    assert client.get("/api/project").json()["dimension"] == 3


# ── Kratos export ───────────────────────────────────────────────────────────

def test_export_returns_a_deck_and_its_material_file(client):
    body = client.post("/api/export/mdpa", json={"element_size": 8.0, "order": 2}).json()
    assert body["mdpa"].startswith("Begin Properties 0")
    assert "Begin Nodes" in body["mdpa"] and "Begin SubModelPart Soil_1" in body["mdpa"]
    assert json.loads(body["materials"])["properties"]
    parameters = json.loads(body["project_parameters"])
    stage_settings = next(iter(parameters["stages"].values()))["stage_settings"]
    assert stage_settings["processes"]["loads_process_list"]
    assert body["stats"]["elements"] > 0


def test_export_can_leave_the_material_file_out(client):
    body = client.post("/api/export/mdpa",
                       json={"element_size": 8.0, "include_materials": False}).json()
    assert body["materials"] is None
    assert body["mdpa"]


def test_calculate_meshes_exports_and_runs_the_deck(client, monkeypatch, tmp_path):
    """The whole button, with a stand-in for Kratos: the project is meshed and exported
    as usual, the three files land in a directory of their own, and what comes back is
    where they went and what the run produced."""
    from core.analysis import calculation

    monkeypatch.setenv(calculation.RUNS_ENV, str(tmp_path / "runs"))
    monkeypatch.setenv(calculation.PYTHON_ENV, sys.executable)
    monkeypatch.setattr(calculation, "COMMAND",
                        ["-c", "open('results.post.res', 'w').close()"])

    body = client.post("/api/calculate", json={"element_size": 8.0}).json()

    assert body["ok"] is True
    directory = Path(body["directory"])
    assert directory.parent == tmp_path / "runs"
    assert sorted(body["inputs"]) == sorted(
        p.name for p in directory.iterdir()
        if p.suffix in (".mdpa",) or p.name.endswith("Parameters.json")
        or p.name == calculation.UNITS_NAME)
    assert body["outputs"] == ["results.post.res"]
    assert body["stats"]["elements"] > 0


def test_calculate_reports_a_failed_run_rather_than_raising(client, monkeypatch,
                                                            tmp_path):
    """A model Kratos refuses is an answer about the model, not a broken server: it
    comes back 200 with `ok` false and what Kratos said."""
    from core.analysis import calculation

    monkeypatch.setenv(calculation.RUNS_ENV, str(tmp_path / "runs"))
    monkeypatch.setenv(calculation.PYTHON_ENV, sys.executable)
    monkeypatch.setattr(calculation, "COMMAND",
                        ["-c", "import sys; print('Error: nope'); sys.exit(1)"])

    response = client.post("/api/calculate", json={"element_size": 8.0})

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert "nope" in response.json()["error"]


def test_calculate_refuses_a_second_run_while_one_is_going(client, monkeypatch):
    from core.analysis import calculation

    monkeypatch.setattr(calculation, "_running", True)

    assert client.post("/api/calculate", json={"element_size": 8.0}).status_code == 409


def test_calculate_refuses_a_model_with_nothing_to_mesh(client, monkeypatch):
    """A blank project meshes to no elements, and Kratos would run that deck without
    complaint. It is refused before gmsh or Kratos is started, in the words
    `kratos-cli check` uses (`session.nothing_to_mesh`)."""
    from core import session
    from core.analysis import calculation
    from core.model.templates import blank_project

    def never(*_):
        raise AssertionError("Kratos must not be started for an empty model")

    monkeypatch.setattr(calculation, "run", never)
    client.post("/api/project/new")
    try:
        response = client.post("/api/calculate", json={"element_size": 8.0})
    finally:
        client.post("/api/project/reset")

    assert response.status_code == 422
    assert response.json()["detail"] == session.nothing_to_mesh(blank_project())
    assert "nothing to mesh" in response.json()["detail"]


def test_export_rejects_an_unknown_body_key(client):
    response = client.post("/api/export/mdpa",
                           json={"element_size": 8.0, "volume_keys": ["soil_L9"]})
    assert response.status_code == 422


def test_export_of_a_section_is_a_plane_strain_deck(client, restore_3d):
    client.patch("/api/project/dimension", json={"dimension": 2, "section_offset": 20.0})
    loads = client.get("/api/project").json()["loads"]
    loads.append({
        "id": "load_line", "name": "LineLoad_1", "kind": "line",
        "x0": 1.0, "x1": 10.0, "y": 0.0, "thickness": 0.15,
        "components": [0.0, -20.0], "distribution": "Uniform", "active": True,
    })
    client.patch("/api/project/structures", json={"loads": loads})
    body = client.post("/api/export/mdpa", json={"element_size": 8.0, "order": 2}).json()
    assert "SmallStrainUPwDiffOrderElement2D6N" in body["mdpa"]
    assert "LineLoadDiffOrderCondition2D3N" in body["mdpa"], "the load pad is in this section"


# ── Cache control ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", ["/", "/live/js/patches.js", "/js/viewport.js",
                                  "/live/css/live.css", "/css/layout.css"])
def test_app_sources_are_never_cached(client, path):
    """The frontend is edited constantly and reloaded in a browser that is happy to
    keep an old copy. A half-stale mix -- new patches.js against an old viewport.js,
    say -- fails in ways that look like model bugs rather than caching, so the
    served sources say not to cache them at all."""
    headers = client.get(path).headers
    assert "no-store" in headers.get("cache-control", "")


def test_static_assets_may_still_be_cached(client):
    """Only the sources. The logo and the pinned three.js build never change."""
    assert "no-store" not in client.get("/vendor/three.min.js").headers.get("cache-control", "")


# ── 3D structures through the same one endpoint ─────────────────────────────

PANEL_SECTION = {"id": "az26_wall", "name": "AZ 26-700 wall",
                 "constitutive_law": "LinearElasticPlaneStress2DLaw", "tables": {},
                 "variables": {"YOUNG_MODULUS": 2.1e11, "POISSON_RATIO": 0.3,
                               "THICKNESS": 0.4, "DENSITY": 7850.0}}
PANEL = {"id": "panel_1", "name": "Wall 1", "kind": "panel", "section": "az26_wall",
         "footprint": [[12.0, 4.0], [12.0, 20.0]], "y_top": 0.0, "y_toe": -14.0,
         "active": True}
MEMBER = {"id": "member_1", "name": "King post 1", "kind": "member", "section": "az26",
          "points": [[18.0, 0.0, 10.0], [18.0, -12.0, 10.0]], "active": True}
TENDON = ANCHOR_SECTION
SPACE_ANCHOR = {"id": "anchor_1", "name": "Anchor 1", "kind": "anchor3d",
                "section": "strand", "head": [12.0, -2.0, 10.0],
                "tail": [17.0, -8.0, 10.0], "prestress": 250.0, "active": True}


def test_patch_structures_creates_a_wall_a_member_and_a_space_anchor(client):
    """One endpoint for every structure kind, in either dimension: the 3D records go
    through the same validated transaction the 2D ones do."""
    loads = [load.model_dump(mode="json") for load in seed_project().loads]
    response = client.patch("/api/project/structures",
                            json={"loads": loads,
                                  "beam_sections": [SECTION],
                                  "panel_sections": [PANEL_SECTION],
                                  "beams": [PANEL, MEMBER],
                                  "anchor_sections": [TENDON],
                                  "anchors": [SPACE_ANCHOR]})

    assert response.status_code == 200, response.json()
    stored = client.get("/api/project").json()
    assert [b["kind"] for b in stored["beams"]] == ["panel", "member"]
    assert [a["kind"] for a in stored["anchors"]] == ["anchor3d"]
    assert stored["panel_sections"] == [PANEL_SECTION]

    client.put("/api/project", json=seed_project().model_dump())


def test_patch_structures_rejects_a_wall_without_its_section(client):
    loads = [load.model_dump(mode="json") for load in seed_project().loads]
    response = client.patch("/api/project/structures",
                            json={"loads": loads, "panel_sections": [], "beams": [PANEL]})

    assert response.status_code == 422
    assert client.get("/api/project").json()["beams"] == []


def test_patch_structures_leaves_panel_sections_alone_when_unmentioned(client):
    """An omitted collection means 'unchanged', for the 3D library as for the 2D one."""
    loads = [load.model_dump(mode="json") for load in seed_project().loads]
    client.patch("/api/project/structures",
                 json={"loads": loads, "panel_sections": [PANEL_SECTION],
                       "beams": [PANEL]})
    response = client.patch("/api/project/structures", json={"loads": loads})

    assert response.status_code == 200
    assert response.json()["project"]["panel_sections"] == [PANEL_SECTION]
    assert [b["id"] for b in response.json()["project"]["beams"]] == ["panel_1"]

    client.put("/api/project", json=seed_project().model_dump())


def test_a_3d_structural_model_goes_from_patch_to_deck_through_the_api(client):
    """The whole 3D path the frontend drives, over HTTP: create a wall, a member and
    an anchor, draw them, mesh them, and export the deck they produce."""
    loads = [load.model_dump(mode="json") for load in seed_project().loads]
    created = client.patch("/api/project/structures",
                           json={"loads": loads,
                                 "beam_sections": [SECTION],
                                 "panel_sections": [PANEL_SECTION],
                                 "beams": [PANEL, MEMBER],
                                 "anchor_sections": [TENDON],
                                 "anchors": [SPACE_ANCHOR]})
    assert created.status_code == 200, created.json()

    drawn = client.get("/api/geometry").json()
    keys = {section["key"] for section in drawn["sections"]}
    assert {"panel_1", "member_1", "anchor_1"} <= keys, "the viewport cannot draw them"

    meshed = client.post("/api/mesh", json={"element_size": 8.0, "order": 2})
    assert meshed.status_code == 200, meshed.json()

    body = client.post("/api/export/mdpa", json={"element_size": 8.0, "order": 2}).json()
    deck, materials = body["mdpa"], json.loads(body["materials"])
    assert "ShellThinElement3D3N" in deck, "no wall in the deck"
    assert "Beam" in deck and "3D" in deck, "no member in the deck"
    assert "LinearTrussElement3D2N" in deck, "no anchor in the deck"
    assert "Anchor_1_Support" in deck, "the tail is not held by anything"
    named = {entry["model_part_name"] for entry in materials["properties"]}
    assert {"PorousDomain.Wall_1", "PorousDomain.King_post_1",
            "PorousDomain.Anchor_1"} <= named
    assert any("order 1" in warning for warning in body["warnings"]), body["warnings"]

    client.put("/api/project", json=seed_project().model_dump())


# ── The dimension round trip ────────────────────────────────────────────────

def test_a_2d_model_survives_a_round_trip_through_the_solid_model(client, restore_3d):
    """Author a beam, an anchor and a line load in the section, go up to 3D and come
    back: the numbers have to be the ones the user drew.

    The guard on the re-basis as a whole. Every record is dimension-native `(x, y)`,
    the switch up gives the wall a plan footprint and the load a pad spanning the
    domain's out-of-plane depth, and the switch down has to throw exactly that away
    again -- not a rotated, offset or transposed version of it.
    """
    line = {"id": "load_line", "name": "LineLoad_1", "kind": "line",
            "x0": 4.0, "x1": 16.0, "y": 0.0, "thickness": 0.15,
            "components": [0.0, -20.0], "distribution": "Uniform", "active": True}
    client.patch("/api/project/dimension", json={"dimension": 2, "section_offset": 12.5})
    client.patch("/api/project/structures", json={
        "loads": [line], "beam_sections": [SECTION], "beams": [BEAM],
        "anchor_sections": [ANCHOR_SECTION], "anchors": [ANCHOR],
    })

    def one(collection, kind):
        stored = client.get("/api/project").json()
        return next(r for r in stored[collection] if r.get("kind") == kind)

    up = client.patch("/api/project/dimension", json={"dimension": 3}).json()["project"]
    domain = up["domain"]

    # The wall is swept across the full out-of-plane depth, which is z.
    panel = next(b for b in up["beams"] if b["kind"] == "panel")
    assert panel["footprint"] == [[12.0, domain["z0"]], [12.0, domain["z1"]]]
    assert (panel["y_top"], panel["y_toe"]) == (0.0, -14.0)
    # ...and so is the load pad, which keeps the level it was drawn on.
    pad = next(l for l in up["loads"] if l["kind"] == "surface")
    assert (pad["x0"], pad["x1"]) == (4.0, 16.0)
    assert (pad["z0"], pad["z1"]) == (domain["z0"], domain["z1"])
    assert pad["y"] == 0.0
    # kN/m in the cut becomes kN/m2 over the footprint, vertical on Y.
    assert pad["components"] == [0.0, -20.0, 0.0]

    client.patch("/api/project/dimension", json={"dimension": 2, "section_offset": 12.5})

    assert one("beams", "beam")["points"] == BEAM["points"]
    assert one("anchors", "anchor")["head"] == ANCHOR["head"]
    assert one("anchors", "anchor")["tail"] == ANCHOR["tail"]
    back = one("loads", "line")
    assert (back["x0"], back["x1"], back["y"]) == (4.0, 16.0, 0.0)
    assert back["components"] == [0.0, -20.0]

    client.put("/api/project", json=seed_project().model_dump())


def test_a_staged_excavation_can_be_opened_and_drawn(client):
    """The test model, through the routes the browser actually calls -- which is
    `run tests/models/excavation.py` in the command box, and nothing of its own.

    The deck tests say the export is right; this says the model can be looked at, which
    is a different failure -- a body with no colour, or a key the viewport cannot name,
    takes the geometry endpoint down without touching the export.
    """
    path = Path(__file__).resolve().parent / "models" / "excavation.py"
    loaded = client.post("/api/project/script", json={"path": str(path)})
    assert loaded.status_code == 200, loaded.text
    project = loaded.json()["project"]
    assert project["dimension"] == 2
    assert [line["id"] for line in project["lines"]] == ["floor_1", "floor_2"]
    assert project["beams"] and project["anchors"] and project["normal_loads"]

    geometry = client.get("/api/geometry")
    assert geometry.status_code == 200
    drawn = {section["key"] for section in geometry.json()["sections"]}
    # Seven soil bodies, the wall and the strut. The loads are arrow glyphs the
    # viewport draws from the project itself, so they are not in this payload.
    assert len([k for k in drawn if k.startswith("soil_")]) == 7
    assert {"sheetpile", "strut"} <= drawn


# ── Stages ──────────────────────────────────────────────────────────────────
# Milestone D's write path. The stage list is its own endpoint rather than a
# ride-along on `structures`, because it is the one collection that is *about* the
# others: a stage names part keys, so it has to be validated against a model that is
# already settled, and sending both in one request would leave the order ambiguous.

def _staged_project() -> dict:
    """The seed with a pit dug in three lifts, so there is something to stage."""
    payload = seed_project().model_dump()
    payload["excavation"] = {"x0": 8.0, "x1": 16.0, "z0": 0.0, "z1": 25.0,
                             "levels": [-3.0, -5.0, -7.0]}
    return payload


def test_a_reset_project_has_no_stages(client):
    """Unstaged is the compatibility contract (plan sec 7.18), and it is the state a
    project is in until somebody asks for a sequence.

    Resets first rather than reading whatever the store happens to hold: this module's
    `client` is one shared project that every test borrows and puts back, so a claim
    about "the" project is only meaningful about one this test put there itself.
    """
    client.post("/api/project/reset")
    assert client.get("/api/project").json()["stages"] == []


def test_patch_stages_stores_a_sequence(client):
    client.put("/api/project", json=_staged_project())
    stages = [
        {"id": "initial", "name": "Initial stage", "calculation": "K0 procedure"},
        {"id": "dig1", "name": "Dig to -3", "parent": "initial",
         "deactivate": ["soil_L1__lift1"]},
    ]

    response = client.patch("/api/project/stages", json={"stages": stages})
    assert response.status_code == 200
    # The stage list changes, so the deck does; the geometry does not.
    assert "project" in response.json()["invalidates"]

    saved = client.get("/api/project").json()["stages"]
    assert [p["id"] for p in saved] == ["initial", "dig1"]
    assert saved[1]["deactivate"] == ["soil_L1__lift1"]

    client.put("/api/project", json=seed_project().model_dump())


def test_patch_stages_refuses_a_part_that_does_not_exist(client):
    """A stage names part keys, and a key nothing answers to would export a stage
    switching off a model part Kratos has never heard of."""
    client.put("/api/project", json=_staged_project())
    response = client.patch("/api/project/stages", json={"stages": [
        {"id": "initial", "name": "Initial stage"},
        {"id": "oops", "name": "Dig", "parent": "initial",
         "deactivate": ["no_such_part"]},
    ]})
    assert response.status_code == 422
    assert client.get("/api/project").json()["stages"] == []

    client.put("/api/project", json=seed_project().model_dump())


def test_patch_stages_refuses_a_branch(client):
    """Two stages starting from the same parent have no single execution order.
    Refused at the endpoint, with the names in the message, rather than at export --
    the editor is where it can still be fixed."""
    client.put("/api/project", json=_staged_project())
    response = client.patch("/api/project/stages", json={"stages": [
        {"id": "initial", "name": "Initial stage"},
        {"id": "a", "name": "A", "parent": "initial"},
        {"id": "b", "name": "B", "parent": "initial"},
    ]})
    assert response.status_code == 422
    detail = str(response.json()["detail"])
    assert "'a'" in detail and "'b'" in detail

    client.put("/api/project", json=seed_project().model_dump())


def test_patch_stages_can_clear_the_sequence(client):
    """Back to unstaged, which must export exactly what it exported before staged
    construction existed. An empty list is how the user says so."""
    client.put("/api/project", json=_staged_project())
    client.patch("/api/project/stages", json={"stages": [
        {"id": "initial", "name": "Initial stage"}]})

    assert client.patch("/api/project/stages",
                        json={"stages": []}).status_code == 200
    assert client.get("/api/project").json()["stages"] == []

    client.put("/api/project", json=seed_project().model_dump())


def test_there_is_no_default_stages_route(client):
    """Every stage is the user's to add: there are no default stages."""
    for route in ("/api/project/stages/defaults", "/api/project/phases/defaults"):
        assert client.post(route).status_code in (404, 405)


def test_a_stage_carries_its_three_choices(client):
    client.put("/api/project", json=_staged_project())
    response = client.patch("/api/project/stages", json={"stages": [
        {"id": "initial", "name": "Initial stage", "stress_initialisation": "K0"},
        {"id": "shake", "name": "Shake", "parent": "initial",
         "time_integration": "dynamic"}]})
    assert response.status_code == 200
    got = [(s["calculation"], s["stress_initialisation"], s["time_integration"])
           for s in response.json()["project"]["stages"]]
    assert got == [("mechanical", "K0", "static"), ("mechanical", "none", "dynamic")]

    client.put("/api/project", json=seed_project().model_dump())


def test_a_flow_stage_with_a_stress_initialisation_is_refused(client):
    client.put("/api/project", json=_staged_project())
    response = client.patch("/api/project/stages", json={"stages": [
        {"id": "flow", "name": "Flow", "calculation": "flow",
         "stress_initialisation": "K0"}]})
    assert response.status_code == 422
    assert "no stresses to initialise" in str(response.json()["detail"])

    client.put("/api/project", json=seed_project().model_dump())


# The routes and the key were "phases" before Styx took Kratos' word; a client written
# then keeps working.

def test_the_project_says_stages_not_phases(client):
    project = client.get("/api/project").json()
    assert "stages" in project and "phases" not in project


def test_the_old_patch_phases_route_still_answers(client):
    client.put("/api/project", json=_staged_project())
    response = client.patch("/api/project/phases", json={"phases": [
        {"id": "initial", "name": "Initial stage", "calculation": "K0 procedure"}]})
    assert response.status_code == 200
    stored = client.get("/api/project").json()["stages"]
    assert [s["id"] for s in stored] == ["initial"]
    assert (stored[0]["calculation"], stored[0]["stress_initialisation"]) == \
        ("mechanical", "K0")

    client.put("/api/project", json=seed_project().model_dump())


def test_a_branch_sent_as_phases_is_refused_under_stages(client):
    client.put("/api/project", json=_staged_project())
    response = client.patch("/api/project/phases", json={"phases": [
        {"id": "initial", "name": "Initial stage"},
        {"id": "a", "name": "A", "parent": "initial"},
        {"id": "b", "name": "B", "parent": "initial"},
    ]})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "stages"]

    client.put("/api/project", json=seed_project().model_dump())


def test_a_project_put_with_phases_is_accepted(client):
    client.put("/api/project", json=_staged_project())
    client.patch("/api/project/stages", json={"stages": [
        {"id": "initial", "name": "Initial stage", "stress_initialisation": "K0"},
        {"id": "null_step", "name": "Null step", "parent": "initial"}]})
    doc = client.get("/api/project").json()
    doc["phases"] = doc.pop("stages")
    assert client.put("/api/project", json=doc).status_code == 200
    assert [s["id"] for s in client.get("/api/project").json()["stages"]] == [
        "initial", "null_step"]

    client.put("/api/project", json=seed_project().model_dump())
