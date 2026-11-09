"""`core.geometry.cad_import` and `POST /api/geometry/import`: a CAD file in, one solid part out
(plan/active/alpha-test-plan.md Task 1.2).

The fixtures are made here rather than committed: STEP, IGES and BREP are written by gmsh
from a box, and the triangulated formats (STL, OBJ) are written as text from the eight
corners of a cube, so what each file contains is visible in this file."""

import io
from pathlib import Path

import pytest

from core.geometry import solid_model, cad_import

CORNERS = [(0, 0, 0), (2, 0, 0), (2, 1, 0), (0, 1, 0),
           (0, 0, 3), (2, 0, 3), (2, 1, 3), (0, 1, 3)]
# Counter-clockwise seen from outside, so every normal points out of the cube.
FACES = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
         (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
BOX = (0.0, 0.0, 0.0, 2.0, 1.0, 3.0)


def _normal(a, b, c):
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def stl_text(faces=FACES) -> str:
    lines = ["solid cube"]
    for face in faces:
        a, b, c = (CORNERS[i] for i in face)
        lines.append("  facet normal %g %g %g" % _normal(a, b, c))
        lines.append("    outer loop")
        lines += ["      vertex %g %g %g" % p for p in (a, b, c)]
        lines += ["    endloop", "  endfacet"]
    lines.append("endsolid cube")
    return "\n".join(lines) + "\n"


def obj_text() -> str:
    return "".join(["v %g %g %g\n" % p for p in CORNERS]
                   + ["f %d %d %d\n" % tuple(i + 1 for i in face) for face in FACES])


def binary_stl(faces=FACES) -> bytes:
    import struct
    body = b"".join(struct.pack("<12fH", *_normal(*(CORNERS[i] for i in face)),
                                 *(c for i in face for c in CORNERS[i]), 0) for face in faces)
    return b"binary cube".ljust(80, b" ") + struct.pack("<I", len(faces)) + body


@pytest.fixture(scope="module")
def gmsh_session():
    with solid_model.session():
        yield


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    # The importer writes its .brep into .data; a test writes into its own folder.
    target = tmp_path / "data"
    monkeypatch.setattr(cad_import, "DATA_DIR", target)
    return target


def written_by_gmsh(path: Path) -> Path:
    import gmsh
    gmsh.clear()
    gmsh.model.add("fixture")
    gmsh.model.occ.addBox(*BOX[:3], *(BOX[3 + i] - BOX[i] for i in range(3)))
    gmsh.model.occ.synchronize()
    gmsh.write(str(path))
    gmsh.clear()
    return path


def assert_one_box(result, data_dir):
    assert result["volumes"] == 1
    assert Path(result["brep_path"]).parent == data_dir
    assert Path(result["brep_path"]).exists()
    assert result["bbox"] == pytest.approx(BOX, abs=1e-4)


# ── Each format the dialog offers ───────────────────────────────────────────

@pytest.mark.parametrize("extension", [".step", ".stp", ".iges", ".igs", ".brep"])
def test_a_cad_solid_comes_through_as_one_volume_with_its_extent(gmsh_session, data_dir,
                                                                  tmp_path, extension):
    source = written_by_gmsh(tmp_path / f"box{extension}")
    assert_one_box(cad_import.process_import(str(source), extension), data_dir)


@pytest.mark.parametrize("extension, text", [(".stl", stl_text), (".obj", obj_text)])
def test_a_closed_triangulated_surface_is_rebuilt_into_a_solid(gmsh_session, data_dir,
                                                               tmp_path, extension, text):
    source = tmp_path / f"cube{extension}"
    source.write_text(text(), encoding="ascii")
    assert_one_box(cad_import.process_import(str(source), extension), data_dir)


def test_the_extension_is_matched_whatever_its_case(gmsh_session, data_dir, tmp_path):
    source = written_by_gmsh(tmp_path / "box.step").rename(tmp_path / "BOX.STEP")
    assert_one_box(cad_import.process_import(str(source), ".STEP"), data_dir)


def test_a_binary_stl_imports_like_an_ascii_one(gmsh_session, data_dir, tmp_path):
    source = tmp_path / "cube.stl"
    source.write_bytes(binary_stl())
    assert_one_box(cad_import.process_import(str(source), ".stl"), data_dir)


def test_an_obj_with_quads_texture_indices_and_comments_imports(gmsh_session, data_dir,
                                                               tmp_path):
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    text = ("# exported by a scanner\no cube\n"
            + "".join("v %g %g %g\n" % p for p in CORNERS) + "vt 0 0\nvn 0 0 1\n"
            + "".join("f " + " ".join(f"{i + 1}/1/1" for i in quad) + "\n" for quad in quads))
    source = tmp_path / "cube.obj"
    source.write_text(text, encoding="ascii")
    assert_one_box(cad_import.process_import(str(source), ".obj"), data_dir)


def test_two_separate_closed_bodies_are_two_volumes(gmsh_session, data_dir, tmp_path):
    shifted = [(x + 10, y, z) for x, y, z in CORNERS]
    text = ("".join("v %g %g %g\n" % p for p in CORNERS + shifted)
            + "".join("f %d %d %d\n" % tuple(i + 1 for i in face) for face in FACES)
            + "".join("f %d %d %d\n" % tuple(i + 9 for i in face) for face in FACES))
    source = tmp_path / "two.obj"
    source.write_text(text, encoding="ascii")
    result = cad_import.process_import(str(source), ".obj")
    assert result["volumes"] == 2
    assert result["bbox"] == pytest.approx((0, 0, 0, 12, 1, 3), abs=1e-4)


def test_a_mesh_too_large_to_rebuild_is_refused_with_its_size(gmsh_session, data_dir,
                                                               tmp_path, monkeypatch):
    monkeypatch.setattr(cad_import, "MAX_TRIANGLES", 10)
    source = tmp_path / "cube.stl"
    source.write_text(stl_text(), encoding="ascii")
    with pytest.raises(cad_import.ImportRefused, match="12 triangles"):
        cad_import.process_import(str(source), ".stl")


# ── What the user is told when the file is not a solid ──────────────────────

def test_an_open_surface_is_refused_with_a_reason_about_solids(gmsh_session, data_dir,
                                                                tmp_path):
    source = tmp_path / "lid_missing.stl"
    source.write_text(stl_text(FACES[:-2]), encoding="ascii")
    with pytest.raises(cad_import.ImportRefused, match="not closed"):
        cad_import.process_import(str(source), ".stl")


def test_a_cad_file_of_loose_faces_that_do_not_close_is_refused(gmsh_session, data_dir,
                                                                 tmp_path):
    import gmsh
    gmsh.clear()
    gmsh.model.occ.addRectangle(0, 0, 0, 2, 1)
    gmsh.model.occ.synchronize()
    gmsh.write(str(tmp_path / "sheet.step"))
    gmsh.clear()
    with pytest.raises(cad_import.ImportRefused, match="no 3D volumes"):
        cad_import.process_import(str(tmp_path / "sheet.step"), ".step")


@pytest.mark.parametrize("extension", [".step", ".stl", ".obj"])
def test_an_empty_file_is_refused_not_crashed_on(gmsh_session, data_dir, tmp_path, extension):
    source = tmp_path / f"empty{extension}"
    source.write_bytes(b"")
    with pytest.raises(cad_import.ImportRefused):
        cad_import.process_import(str(source), extension)


def test_a_file_that_is_not_what_its_extension_says_is_refused(gmsh_session, data_dir,
                                                               tmp_path):
    source = tmp_path / "notes.step"
    source.write_text("this is not a STEP file\n", encoding="ascii")
    with pytest.raises(cad_import.ImportRefused):
        cad_import.process_import(str(source), ".step")


def test_a_path_with_spaces_and_non_ascii_letters_imports(gmsh_session, data_dir, tmp_path):
    folder = tmp_path / "Rotterdam Zuid — bouwput ü"
    folder.mkdir()
    source = written_by_gmsh(folder / "wand é.step")
    assert_one_box(cad_import.process_import(str(source), ".step"), data_dir)


# ── Through the API ─────────────────────────────────────────────────────────

def test_a_part_rebuilt_from_triangles_takes_part_in_the_build_as_its_volume(gmsh_session,
                                                                             data_dir,
                                                                             tmp_path):
    from core.model.schemas import CustomPart
    from core.model.templates import seed_project

    source = tmp_path / "cube.stl"
    source.write_text(stl_text(), encoding="ascii")
    result = cad_import.process_import(str(source), ".stl")
    project = seed_project()
    project.custom_parts.append(CustomPart(key="imported_0", label="cube.stl", source="import",
                                           source_file=result["brep_path"],
                                           bbox=tuple(result["bbox"])))
    built = solid_model.build_geometry(project)
    assert built.mass["imported_0"] == pytest.approx(6.0, rel=1e-6), "2 x 1 x 3"


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app) as c:
        c.post("/api/project/new")
        made = []
        yield c, made
        for path in made:
            Path(path).unlink(missing_ok=True)
        c.post("/api/project/new")


def upload(client, name, text):
    c, made = client
    response = c.post("/api/geometry/import",
                      files={"file": (name, io.BytesIO(text.encode("utf-8")), "model/stl")})
    if response.status_code == 200:
        made.append(response.json()["parts"][0]["source_file"])
    return response


def test_an_upload_becomes_a_custom_part_labelled_with_its_file_name(client):
    response = upload(client, "Wand — Zuid ü.stl", stl_text())
    assert response.status_code == 200, response.text
    (part,) = response.json()["parts"]
    assert part["label"] == "Wand — Zuid ü.stl"
    assert part["source"] == "import"
    assert part["bbox"] == pytest.approx(list(BOX), abs=1e-4)
    project = client[0].get("/api/project").json()
    assert [p["key"] for p in project["custom_parts"]] == [part["key"]]


def test_an_unsupported_extension_is_refused_before_gmsh_sees_it(client):
    response = upload(client, "drawing.dwg", "AC1027")
    assert response.status_code == 422
    assert ".step" in response.json()["detail"]


def test_a_file_without_a_solid_is_a_422_that_says_why(client):
    response = upload(client, "lid_missing.stl", stl_text(FACES[:-2]))
    assert response.status_code == 422, "a bad file is the request's fault, not the server's"
    assert "not closed" in response.json()["detail"]


def test_the_temporary_upload_is_removed_whatever_happens(client, monkeypatch, tmp_path):
    import tempfile
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    upload(client, "cube.stl", stl_text())
    upload(client, "lid_missing.stl", stl_text(FACES[:-2]))
    assert list(tmp_path.iterdir()) == []


def test_a_key_is_never_reused_after_a_part_is_deleted(client):
    c, _ = client
    first = upload(client, "a.stl", stl_text()).json()["parts"][0]["key"]
    second = upload(client, "b.stl", stl_text()).json()["parts"][0]["key"]
    assert c.delete(f"/api/geometry/parts/{first}").status_code == 200
    third = upload(client, "c.stl", stl_text())
    assert third.status_code == 200, third.text
    keys = [p["key"] for p in c.get("/api/project").json()["custom_parts"]]
    assert len(keys) == len(set(keys)) == 2, keys
    assert third.json()["parts"][0]["key"] != second


def test_obj_negative_indices_are_relative_to_vertices_already_read(tmp_path):
    obj = tmp_path / "fan.obj"
    obj.write_text(
        "v 0 0 0\nv 2 0 0\nv 2 1 0\nv 0 1 0\nf -4 -3 -2 -1\n",
        encoding="ascii",
    )

    points, triangles = cad_import._read_obj(obj)

    assert points == [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0),
                      (2.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
    assert triangles == [(0, 1, 2), (0, 2, 3)]


def test_obj_face_with_an_unavailable_vertex_is_refused(tmp_path):
    obj = tmp_path / "bad.obj"
    obj.write_text("v 0 0 0\nv 1 0 0\nf 1 2 3\n", encoding="ascii")

    with pytest.raises(cad_import.ImportRefused, match="does not have"):
        cad_import._read_obj(obj)


def test_import_refuses_unsupported_formats(tmp_path, monkeypatch):
    import gmsh

    monkeypatch.setattr(cad_import, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(gmsh, "clear", lambda: None)
    monkeypatch.setattr(gmsh.model, "add", lambda *_args: None)

    with pytest.raises(cad_import.ImportRefused, match="\\.xyz is not a format"):
        cad_import.process_import(str(tmp_path / "model.xyz"), ".xyz")


def test_cad_healing_options_are_restored_even_when_gmsh_cannot_read_the_file(
    tmp_path, monkeypatch,
):
    import gmsh

    source = tmp_path / "broken.step"
    source.write_text("not a CAD model", encoding="ascii")
    monkeypatch.setattr(gmsh, "merge", lambda *_: (_ for _ in ()).throw(RuntimeError("bad CAD")))

    with solid_model.session():
        previous = {name: gmsh.option.getNumber(name) for name in cad_import.HEALING}
        with pytest.raises(cad_import.ImportRefused, match="bad CAD"):
            cad_import._merge_cad(source)

        assert {name: gmsh.option.getNumber(name) for name in cad_import.HEALING} == previous


def test_ascii_stl_reader_preserves_facet_vertices(tmp_path):
    stl = tmp_path / "triangle.stl"
    stl.write_text(
        "solid triangle\nfacet normal 0 0 1\nouter loop\n"
        "vertex 0 0 0\nvertex 2 0 0\nvertex 0 1 0\n"
        "endloop\nendfacet\nendsolid triangle\n",
        encoding="ascii",
    )

    assert cad_import._read_stl(stl) == (
        [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        [(0, 1, 2)],
    )


def test_obj_reader_accepts_texture_index_face_syntax(tmp_path):
    obj = tmp_path / "textured.obj"
    obj.write_text(
        "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1/1 2/2 3/3\n",
        encoding="ascii",
    )

    assert cad_import._read_obj(obj) == (
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        [(0, 1, 2)],
    )
