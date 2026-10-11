"""`kratos.export_project` with no mesh settings: the project meshes with its own.

A project carries the mesh it wants (`Project.mesh`), so a script or a test that exports
one should not have to restate it, and should not need to own a gmsh session to do so.
"""

from __future__ import annotations

import gmsh

from core.kratos import export as kratos
from core.model.schemas import MeshRequest
from tests.models import excavation


def small_model():
    project = excavation.excavation_project(staged=False)
    return project.model_copy(update={"mesh": project.mesh.model_copy(
        update={"element_size": 8.0, "body_sizes": {}, "refinements": [], "order": 1})})


def test_without_settings_the_project_meshes_with_its_own():
    project = small_model()
    assert not gmsh.isInitialized(), "the call has to stand on its own"
    own = kratos.export_project(project)
    assert not gmsh.isInitialized(), "and leave no gmsh session behind"
    stated = kratos.export_project(project, MeshRequest(**project.mesh.model_dump()))
    assert own["mdpa"] == stated["mdpa"]
    assert own["project_parameters"] == stated["project_parameters"]
