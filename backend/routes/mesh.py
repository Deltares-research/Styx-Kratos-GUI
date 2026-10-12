"""The Mesh routes: the mesh of the open project, and the deck numbering laid over it.

Each is a job for the gmsh worker (`core.gmsh_worker`), so meshing never runs on the
event loop.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend import store
from backend.routes.common import check_mesh_keys, not_for_a_deck, run_mesh_job
from core import gmsh_worker
from core.geometry.solid_model import GeometryError
from core.kratos.writer import ExportError
from core.geometry.meshing import MeshingError
from core.model.schemas import MeshRequest

router = APIRouter()


@router.post("/api/mesh")
async def generate_mesh(settings: MeshRequest) -> dict:
    project = store.get()
    not_for_a_deck(project, "meshed")
    check_mesh_keys(project, settings)
    return await run_mesh_job(gmsh_worker.mesh_job, project, settings,
                              (GeometryError, MeshingError))


@router.post("/api/mesh/labels")
async def mesh_labels(settings: MeshRequest) -> dict:
    """The node and element tables -- Kratos ID and where to draw it -- of the deck this
    project exports. A node's point is itself; an element's is its centroid.

    What the viewport's "Show labels" overlay draws from. Deliberately a route of its own
    rather than a field on `POST /api/mesh`: the numbering costs a full export pass
    (interface splitting included), and a mesh is generated far more often than its
    numbers are looked at.
    """
    project = store.get()
    not_for_a_deck(project, "meshed")
    check_mesh_keys(project, settings)
    return await run_mesh_job(gmsh_worker.mesh_labels_job, project, settings,
                              (GeometryError, MeshingError, ExportError))


@router.post("/api/mesh/node-parts")
async def mesh_node_parts(settings: MeshRequest) -> dict:
    """Which SubModelParts each node of this project's deck is in: the node table and,
    per part, the nodes it names -- in the same Kratos numbering `/api/mesh/labels`
    puts on the mesh. What `node <id>` and the viewport's node inspection read
    (frontend/js/node-parts.js). A route of its own for the reason the labels have one: it
    costs a full export pass, and is asked for far less often than a mesh.
    """
    project = store.get()
    not_for_a_deck(project, "meshed")
    check_mesh_keys(project, settings)
    return await run_mesh_job(gmsh_worker.node_parts_job, project, settings,
                              (GeometryError, MeshingError, ExportError))
