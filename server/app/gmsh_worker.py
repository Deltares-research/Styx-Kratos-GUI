"""Serialised access to gmsh, which is a process-global singleton.

gmsh keeps one current model (`GModel::current()`), one option table (`CTX::instance()`)
and one `isInitialized` flag for the whole process. Two requests meshing at once would
not race over a lock -- they would silently share and corrupt one model.

So every gmsh call runs in a `ProcessPoolExecutor(max_workers=1)`, awaited from the
event loop. That buys three things:

*   access is serialised by construction, with no locking discipline to get wrong;
*   the event loop stays responsive while a mesh runs for tens of seconds;
*   a hard crash is contained. OCC booleans on thin solids can abort the process
    outright, and that must not take the API down with them -- the pool simply starts a
    replacement worker on the next call.

gmsh is initialised once per worker, at startup, and the model is cleared per request:
repeated `initialize()`/`finalize()` cycles are a documented source of trouble.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Callable

_executor: ProcessPoolExecutor | None = None


def _init_worker() -> None:
    import gmsh

    if not gmsh.isInitialized():
        gmsh.initialize()
    # Diagnostics are captured per job and returned in the response, so nothing should
    # be written to a stdout no one is reading.
    gmsh.option.setNumber("General.Terminal", 0)


def executor() -> ProcessPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ProcessPoolExecutor(max_workers=1, initializer=_init_worker)
    return _executor


async def run(job: Callable[..., Any], *args: Any) -> Any:
    """Run `job` in the gmsh worker. `job` and its arguments must be picklable."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor(), job, *args)


def shutdown() -> None:
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=True)
        _executor = None


# ── Jobs ────────────────────────────────────────────────────────────────────
#
# Top-level functions, because the pool pickles them by qualified name. They take and
# return plain JSON-compatible values for the same reason.

def version_job() -> str:
    import gmsh

    return ".".join(str(int(v)) for v in (gmsh.GMSH_API_VERSION_MAJOR,
                                          gmsh.GMSH_API_VERSION_MINOR))


def geometry_job(project_json: str) -> dict:
    from app import tessellate
    from app.schemas import Project

    return tessellate.tessellate(Project.model_validate_json(project_json)).to_dict()


def mesh_job(project_json: str, settings_json: str) -> dict:
    from app import meshing
    from app.schemas import MeshRequest, Project

    project = Project.model_validate_json(project_json)
    settings = MeshRequest.model_validate_json(settings_json)
    return meshing.mesh_project(
        project, element_size=settings.element_size, order=settings.order,
        refinements=settings.refinements, algorithm_3d=settings.algorithm_3d,
        algorithm_2d=settings.algorithm_2d,
        optimization=settings.optimization, smoothing=settings.smoothing,
        curvature_points=settings.curvature_points,
        size_min_factor=settings.size_min_factor,
        second_order_linear=settings.second_order_linear,
        volume_keys=settings.volume_keys,
        body_sizes=settings.body_sizes,
    ).to_dict()


def mesh_labels_job(project_json: str, settings_json: str) -> dict:
    """Just the node and element tables of the deck this project would export.

    The whole export runs -- it is the only thing that knows a node's or an element's
    Kratos ID -- but only the numbering comes back, because that is all the viewport's
    ID labels need and an .mdpa's text is megabytes the overlay would only throw away.
    Both tables travel together: they come out of one pass, and fetching them separately
    would mean meshing the project twice to say what it already said.
    """
    from app import kratos
    from app.schemas import MeshRequest, Project

    project = Project.model_validate_json(project_json)
    settings = MeshRequest.model_validate_json(settings_json)
    result = kratos.export_project(project, settings, include_materials=False)
    return {"nodes": result["nodes"], "elements": result["elements"],
            "stats": result["stats"]}


def node_parts_job(project_json: str, settings_json: str) -> dict:
    """Which SubModelParts each node of the deck this project would export is in.

    The whole export runs, like `mesh_labels_job`, because the deck is the only thing
    that knows both a node's Kratos number and the parts that name it; the answer is
    read back off the `.mdpa` text so it is the deck's own (`app.node_parts`).
    """
    from app import kratos, node_parts
    from app.schemas import MeshRequest, Project

    project = Project.model_validate_json(project_json)
    settings = MeshRequest.model_validate_json(settings_json)
    result = kratos.export_project(project, settings, include_materials=False)
    return node_parts.node_parts(result["mdpa"])


def import_job(filepath: str, extension: str) -> dict:
    from app import importer
    return importer.process_import(filepath, extension)


def create_job(recipe_json: str) -> dict:
    import json
    from app import creator
    return creator.process_creation(json.loads(recipe_json))


def export_job(project_json: str, settings_json: str) -> dict:
    from app import kratos
    from app.schemas import ExportRequest, Project

    project = Project.model_validate_json(project_json)
    settings = ExportRequest.model_validate_json(settings_json)
    return kratos.export_project(project, settings,
                                 include_materials=settings.include_materials)
