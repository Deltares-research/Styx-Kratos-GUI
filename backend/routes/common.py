"""What more than one router needs: reading an upload, validating an edited project, and
handing a mesh job to the gmsh worker.

Written once so the routes cannot drift apart in how they refuse a request.
"""

from __future__ import annotations

from fastapi import HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError

from core import gmsh_worker
from core.model.schemas import MeshRequest, Project

MAX_UPLOAD_BYTES = 256 * 2**20
"""The largest file an upload route reads. A real deck is a few megabytes (a dike section's mesh
is about 3 MB); this exists so a runaway file is a refusal, not an out-of-memory server."""


async def read_upload(file: UploadFile) -> bytes:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=(
            f"{file.filename} is larger than the {MAX_UPLOAD_BYTES / 2**20:g} MB this "
            "server reads in one upload."))
    return data


def validated(payload: dict) -> Project:
    """`payload` as a `Project`, refused the way a bad request body is: a 422 that names
    each field, not the 500 a `ValidationError` escaping a route would be."""
    try:
        return Project.model_validate(payload)
    except ValidationError as failure:
        raise RequestValidationError(failure.errors()) from failure


def not_for_a_deck(project: Project, what: str) -> None:
    """Refuse to mesh or export a project that is a deck already (`core.kratos.external_deck`).

    Everything but its deck is the empty site the schema requires, so going ahead would
    mesh nothing and answer as though that were the model.
    """
    if project.deck is not None:
        raise HTTPException(status_code=422, detail=(
            f"{project.name} is a Kratos deck ({project.deck.parameters} in "
            f"{project.deck.directory}), so it is not {what} here: its mesh is the "
            f"deck's own. Calculate runs it as it is."))


def check_mesh_keys(project: Project, settings: MeshRequest) -> None:
    """Refuse a mesh request that names a body this project does not have."""
    unknown = sorted((set(settings.volume_keys or []) | set(settings.body_sizes))
                     - set(project.part_keys()))
    if unknown:
        raise HTTPException(status_code=422, detail="unknown mesh body key(s): " + ", ".join(unknown))


async def run_mesh_job(job, project: Project, settings: BaseModel,
                       errors: tuple[type[Exception], ...]) -> dict:
    """Run `job` in the gmsh worker on this project and these settings.

    `errors` are the failures the route reports as a 500 with their reason, so the
    frontend can put it in the command log. Each route names its own: anything else -- a
    crashed worker, for one -- goes on to the app's handler.
    """
    try:
        return await gmsh_worker.run(job, project.model_dump_json(), settings.model_dump_json())
    except errors as failure:
        raise HTTPException(status_code=500, detail=str(failure)) from failure
