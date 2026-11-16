"""Serialised access to gmsh, which is a process-global singleton.

gmsh keeps one current model (`GModel::current()`), one option table (`CTX::instance()`)
and one `isInitialized` flag for the whole process. Two requests meshing at once would
not race over a lock -- they would silently share and corrupt one model.

So every gmsh call runs in a `ProcessPoolExecutor(max_workers=1)`, awaited from the
event loop. That buys three things:

*   access is serialised by construction, with no locking discipline to get wrong;
*   the event loop stays responsive while a mesh runs for tens of seconds;
*   a hard crash is contained. OCC booleans on thin solids can abort the process
    outright, and that must not take the API down with them -- `run` discards the
    broken pool and raises `WorkerCrashed`, and the next call starts a replacement
    worker.

gmsh is initialised once per worker, at startup, and the model is cleared per request:
repeated `initialize()`/`finalize()` cycles are a documented source of trouble.
"""

from __future__ import annotations

import asyncio
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from typing import Any, Callable

_executor: ProcessPoolExecutor | None = None


class WorkerCrashed(RuntimeError):
    """The gmsh worker died during a job -- an OCC abort, or the process being killed.

    Only the request that was running fails: the dead pool is discarded here, so the next
    call starts a fresh worker. `ProcessPoolExecutor` itself never recovers; left alone,
    one crash would fail every gmsh request until the server restarted.
    """


def _init_worker() -> None:
    import gmsh

    from core.geometry import solid_model

    if not gmsh.isInitialized():
        solid_model.initialize()
    # Diagnostics are captured per job and returned in the response, so nothing should
    # be written to a stdout no one is reading.
    gmsh.option.setNumber("General.Terminal", 0)


def executor() -> ProcessPoolExecutor:
    global _executor
    if _executor is None:
        # Spawned on every platform, as Windows always does: Linux would fork, and a
        # fork of a process with other threads (a server, a browser driver) can
        # inherit a lock one of them held, and wait on it forever.
        _executor = ProcessPoolExecutor(max_workers=1, initializer=_init_worker,
                                        mp_context=multiprocessing.get_context("spawn"))
    return _executor


async def run(job: Callable[..., Any], *args: Any) -> Any:
    """Run `job` in the gmsh worker. `job` and its arguments must be picklable."""
    loop = asyncio.get_running_loop()
    pool = executor()
    try:
        return await loop.run_in_executor(pool, job, *args)
    except BrokenProcessPool as broken:
        _discard(pool)
        raise WorkerCrashed(
            "The geometry engine (gmsh) stopped unexpectedly while working on this "
            "request -- typically an OpenCASCADE failure on a degenerate shape. It has been "
            "restarted; the request can be retried, and a change to the geometry that "
            "triggered it may be needed.") from broken


def _discard(pool: ProcessPoolExecutor) -> None:
    """Drop a broken pool, unless a concurrent request has already replaced it."""
    global _executor
    if _executor is pool:
        _executor = None
    pool.shutdown(wait=False, cancel_futures=True)


def shutdown() -> None:
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=True)
        _executor = None


def run_here(job: Callable[..., Any], *args: Any) -> Any:
    """Run `job` in this process instead of the worker, with gmsh owned for it.

    What the command line does (`cli/`): it runs one job and exits, so a pool would cost
    a second interpreter for nothing, and a crash ends only that command. gmsh is
    initialized for the job and finalized after, unless it was running already -- the
    same re-entrant rule `solid_model.session` keeps.
    """
    from core.geometry import solid_model

    with solid_model.session():
        return job(*args)


def run_blocking(job: Callable[..., Any], *args: Any) -> Any:
    """Run `job` and wait for it, from code that is not on the event loop.

    In a process's main thread that is `run_here`. Anywhere else -- a route's worker
    thread running a model script -- gmsh cannot be initialized (it installs a signal
    handler, which only the main thread may), so the job goes to the worker and this
    waits for it.
    """
    import threading

    if threading.current_thread() is threading.main_thread():
        return run_here(job, *args)
    return executor().submit(job, *args).result()


# ── Jobs ────────────────────────────────────────────────────────────────────
#
# Top-level functions, because the pool pickles them by qualified name. They take and
# return plain JSON-compatible values for the same reason.

def version_job() -> str:
    import gmsh

    return ".".join(str(int(v)) for v in (gmsh.GMSH_API_VERSION_MAJOR,
                                          gmsh.GMSH_API_VERSION_MINOR))


def geometry_job(project_json: str) -> dict:
    from core.geometry import tessellation
    from core.model.schemas import Project

    return tessellation.tessellate(Project.model_validate_json(project_json)).to_dict()


def mesh_job(project_json: str, settings_json: str) -> dict:
    from core.geometry import meshing
    from core.model.schemas import MeshRequest, Project

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
        body_sizes=settings.body_sizes, size_bands=settings.size_bands,
    ).to_dict()


def mesh_labels_job(project_json: str, settings_json: str) -> dict:
    """Just the node and element tables of the deck this project would export.

    The whole export runs -- it is the only thing that knows a node's or an element's
    Kratos ID -- but only the numbering comes back, because that is all the viewport's
    ID labels need and an .mdpa's text is megabytes the overlay would only throw away.
    Both tables travel together: they come out of one pass, and fetching them separately
    would mean meshing the project twice to say what it already said.
    """
    from core.kratos import writer
    from core.model.schemas import MeshRequest, Project

    project = Project.model_validate_json(project_json)
    settings = MeshRequest.model_validate_json(settings_json)
    result = writer.export_project(project, settings, include_materials=False)
    return {"nodes": result["nodes"], "elements": result["elements"],
            "stats": result["stats"]}


def node_parts_job(project_json: str, settings_json: str) -> dict:
    """Which SubModelParts each node of the deck this project would export is in.

    The whole export runs, like `mesh_labels_job`, because the deck is the only thing
    that knows both a node's Kratos number and the parts that name it; the answer is
    read back off the `.mdpa` text so it is the deck's own (`core.kratos.node_parts`).
    """
    from core.kratos import writer, node_parts
    from core.model.schemas import MeshRequest, Project

    project = Project.model_validate_json(project_json)
    settings = MeshRequest.model_validate_json(settings_json)
    result = writer.export_project(project, settings, include_materials=False)
    return node_parts.node_parts(result["mdpa"])


def import_job(filepath: str, extension: str) -> dict:
    from core.geometry import cad_import
    return cad_import.process_import(filepath, extension)


def create_job(recipe_json: str) -> dict:
    import json
    from core.geometry import primitives
    return primitives.process_creation(json.loads(recipe_json))


def export_job(project_json: str, settings_json: str) -> dict:
    from core.kratos import writer
    from core.model.schemas import ExportRequest, Project

    project = Project.model_validate_json(project_json)
    settings = ExportRequest.model_validate_json(settings_json)
    return writer.export_project(project, settings,
                                 include_materials=settings.include_materials)
