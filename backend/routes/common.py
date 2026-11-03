"""What more than one router needs: reading an upload, storing an edit and answering a
refused one, and handing a mesh job to the gmsh worker.

Written once so the routes cannot drift apart in how they answer a request.
"""

from __future__ import annotations

from contextlib import contextmanager

from fastapi import HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError

from backend import store
from core import gmsh_worker, session
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


@contextmanager
def refusals():
    """Answer an edit `core.session` refuses the way a bad request is answered.

    A field that does not validate is a 422 naming each field, the same as a bad request
    body, not the 500 a `ValidationError` escaping a route would be. A part that is not
    there is a 404; any other refused edit is a 422 with its reason, which the command
    log shows as it stands.
    """
    try:
        yield
    except ValidationError as failure:
        raise RequestValidationError(failure.errors()) from failure
    except session.UnknownPart as failure:
        raise HTTPException(status_code=404, detail=str(failure)) from failure
    except session.EditRefused as failure:
        raise HTTPException(status_code=422, detail=str(failure)) from failure


def stored(project: Project) -> dict:
    """Store the edited `project`, and start the answer to the edit: the project, and in
    `edit_notes` the mesh sizes the edit took away with their bodies
    (`session.removed_sizes`). The GUI shows `edit_notes` in its command box whatever
    edit it made (frontend/js/api.js); kratos-cli prints the same note."""
    notes = session.removed_sizes(store.get(), project)
    store.put(project)
    return {"project": project, "edit_notes": notes}


def not_for_a_deck(project: Project, what: str) -> None:
    """Refuse, as a 422, to mesh or export a project that is a deck already
    (`session.require_parametric`)."""
    with refusals():
        session.require_parametric(project, what)


def check_mesh_keys(project: Project, settings: MeshRequest) -> None:
    """Refuse a mesh request that names a body this project does not have."""
    unknown = session.unknown_mesh_keys(project, settings)
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
