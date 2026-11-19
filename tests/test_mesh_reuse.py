"""A model meshed already is not meshed again: Generate mesh, then Calculate, meshes once.

`meshing.mesh_project` keeps its last mesh in its own gmsh model
(`solid_model.MESH_MODEL`), which the display tessellation of an edit leaves alone. The
same model and settings take that mesh as it is, and the deck written from it is the
deck a new mesh gives.
"""

import re
from pathlib import Path

import gmsh
import pytest

from core.geometry import meshing, solid_model, tessellation
from core.kratos import writer
from core.model.templates import seed_project

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project():
    return seed_project()


@pytest.fixture(autouse=True)
def fresh_cache():
    meshing._kept = None
    yield
    meshing._kept = None


def test_the_same_inputs_take_the_kept_mesh(project):
    with solid_model.session():
        first = meshing.mesh_project(project, element_size=6.0, order=1)
        second = meshing.mesh_project(project, element_size=6.0, order=1)
    assert not first.reused
    assert second.reused
    assert second.stats == first.stats


def test_the_mesh_survives_the_tessellation_of_an_edit(project):
    with solid_model.session():
        meshing.mesh_project(project, element_size=6.0, order=1)
        tessellation.tessellate(project)
        assert solid_model.MESH_MODEL in gmsh.model.list()
        again = meshing.mesh_project(project, element_size=6.0, order=1)
        assert again.reused
        assert gmsh.model.getCurrent() == solid_model.MESH_MODEL


def test_a_field_the_mesher_never_reads_keeps_the_mesh(project):
    renamed = project.model_copy(update={"name": "Another name", "stages": []})
    with solid_model.session():
        meshing.mesh_project(project, element_size=6.0, order=1)
        assert meshing.mesh_project(renamed, element_size=6.0, order=1).reused


def test_other_settings_or_geometry_mesh_again(project):
    moved = project.model_copy(update={"domain": project.domain.model_copy(
        update={"x1": project.domain.x1 + 2.0})})
    with solid_model.session():
        meshing.mesh_project(project, element_size=6.0, order=1)
        assert not meshing.mesh_project(project, element_size=5.0, order=1).reused
        assert not meshing.mesh_project(moved, element_size=5.0, order=1).reused


def test_a_cleared_gmsh_meshes_again(project):
    with solid_model.session():
        meshing.mesh_project(project, element_size=6.0, order=1)
        gmsh.clear()
        assert not meshing.mesh_project(project, element_size=6.0, order=1).reused


def test_a_deck_from_the_kept_mesh_is_the_deck_of_a_new_mesh(project):
    with solid_model.session():
        fresh = writer.export_project(project)
        tessellation.tessellate(project)
        kept = writer.export_project(project)
    assert not fresh["mesh_reused"]
    assert kept["mesh_reused"]
    for key in ("mdpa", "materials", "project_parameters", "nodes", "elements"):
        assert kept[key] == fresh[key], key


def test_the_fields_the_mesher_never_reads_match_the_gui():
    source = (ROOT / "frontend/js/mesh-settings.js").read_text(encoding="utf-8")
    listed = re.search(r"var NOT_MESHED = \[([^\]]*)\]", source)
    assert listed, "NOT_MESHED is no longer a list in mesh-settings.js"
    gui = tuple(re.findall(r"'([^']+)'", listed.group(1)))
    assert gui == meshing.NOT_MESHED
