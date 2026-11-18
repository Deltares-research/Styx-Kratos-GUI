"""The Results routes: reading back what a calculation left behind.

Which runs exist, which stages each got through, which files are in it, and what a stage
can show -- its mesh, its fields, the curves along a wall. All of it is `core.results.catalog`;
these routes only turn its refusals into status codes.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from core.analysis import calculation
from core.results import catalog

router = APIRouter()


def _results_error(failure: catalog.ResultsError) -> HTTPException:
    """404 for something that is not there, 400 for something that may not be asked.

    The distinction matters for exactly one case: a filename that tries to climb out
    of the run directory is refused as a bad request whether or not it names something
    real, so the answer cannot be used to find out what is on the machine.
    """
    status = 400 if isinstance(failure, catalog.UnsafeName) else 404
    return HTTPException(status_code=status, detail=str(failure))


@router.get("/api/results/runs")
def results_runs() -> dict:
    """Every run on this machine, newest first. Cheap: names and sizes, no parsing."""
    return {"runs": catalog.runs(), "root": str(calculation.runs_root())}


@router.get("/api/results/runs/{run_id}")
def results_run(run_id: str) -> dict:
    try:
        return catalog.describe(run_id)
    except catalog.ResultsError as failure:
        raise _results_error(failure) from failure


@router.get("/api/results/runs/{run_id}/stages/{index}/fields")
def results_stage_fields(run_id: str, index: int) -> dict:
    """What this stage can be asked to show.

    Derived from the file, never from a list in the source: a variable Kratos declined
    to write -- or wrote an empty block for, because the element does not implement it
    -- costs one missing menu entry and breaks nothing. See `core.results.fields`.
    """
    try:
        return catalog.stage_fields(run_id, index)
    except catalog.ResultsError as failure:
        raise _results_error(failure) from failure


@router.get("/api/results/runs/{run_id}/stages/{index}/mesh")
def results_stage_mesh(run_id: str, index: int) -> dict:
    """The stage's mesh as drawable buffers, one section per named part.

    Vertex *i* of a section is the deck's node `node_ids[i]`, at
    `positions[3i..3i+2]`. That correspondence is what lets a field -- which comes back
    keyed by node id -- become a vertex-colour buffer without a second request.
    """
    try:
        return catalog.stage_geometry(run_id, index)
    except catalog.ResultsError as failure:
        raise _results_error(failure) from failure


@router.get("/api/results/runs/{run_id}/stages/{index}/displacement")
def results_stage_displacement(run_id: str, index: int) -> dict:
    """The displacement vectors this stage's mesh is deformed by.

    Its own route because it is the one quantity the viewer needs all three components
    of; everything in the field catalogue derives a single number.
    """
    try:
        return catalog.stage_displacement(run_id, index)
    except catalog.ResultsError as failure:
        raise _results_error(failure) from failure


@router.get("/api/results/runs/{run_id}/stages/{index}/vectors/{name}")
def results_stage_vectors(run_id: str, index: int, name: str) -> dict:
    """The whole vector behind a field (`flux`, `ux`, ...) at every node: what its
    arrows are drawn with. 422 for a field that is not part of a vector."""
    from core.results import fields

    try:
        return catalog.stage_vectors(run_id, index, name)
    except fields.UnknownField as failure:
        raise HTTPException(status_code=422, detail=str(failure)) from failure
    except catalog.ResultsError as failure:
        raise _results_error(failure) from failure


@router.get("/api/results/runs/{run_id}/stages/{index}/at/{node}")
def results_stage_at(run_id: str, index: int, node: int) -> dict:
    """Every field of this stage at one node, in one request.

    `results at <id>` is how a number gets checked against a hand calculation without
    leaving the app, and doing it a field at a time would be twenty-odd round trips.
    """
    from core.results import fields

    try:
        return catalog.stage_at_node(run_id, index, node)
    except fields.UnknownField as failure:
        raise HTTPException(status_code=422, detail=str(failure)) from failure
    except catalog.ResultsError as failure:
        raise _results_error(failure) from failure


@router.get("/api/results/runs/{run_id}/stages/{index}/parts")
def results_stage_parts(run_id: str, index: int) -> dict:
    """The deck's named parts as this stage saw them, and which were live in it."""
    try:
        return catalog.stage_parts(run_id, index)
    except catalog.ResultsError as failure:
        raise _results_error(failure) from failure


@router.get("/api/results/runs/{run_id}/stages/{index}/field/{name}")
def results_stage_field(run_id: str, index: int, name: str,
                              location: str = "nodes") -> dict:
    """One field: the ids it is defined on, the numbers on them, and their range.

    The range travels with the values so that a colour legend and the colours it
    explains can never be computed from two different things.
    """
    from core.results import fields

    try:
        return catalog.stage_field(run_id, index, name, location)
    except fields.UnknownField as failure:
        # 422 rather than 404: the run and the stage are both there, and what is wrong
        # is the question -- a field this stage does not carry, or a location it
        # cannot be drawn at.
        raise HTTPException(status_code=422, detail=str(failure)) from failure
    except catalog.ResultsError as failure:
        raise _results_error(failure) from failure


@router.get("/api/results/runs/{run_id}/members")
def results_members(run_id: str) -> dict:
    """The structural members this run wrote curves for -- the wall, its interface --
    with the stages each has and the quantities each can be plotted for."""
    try:
        return catalog.stage_members(run_id)
    except catalog.ResultsError as failure:
        raise _results_error(failure) from failure


@router.get("/api/results/runs/{run_id}/members/{member}/{quantity}")
def results_member_plot(run_id: str, member: str, quantity: str) -> dict:
    """One quantity along one member, a curve per stage: what the plot window draws.

    422 for a quantity this member does not carry, like an unknown field: the run and
    the member are there, and what is wrong is the question.
    """
    from core.results import members

    try:
        return catalog.member_profiles(run_id, member, quantity)
    except members.UnknownQuantity as failure:
        raise HTTPException(status_code=422, detail=str(failure)) from failure
    except catalog.ResultsError as failure:
        raise _results_error(failure) from failure


@router.get("/api/results/runs/{run_id}/files/{name}")
def results_file(run_id: str, name: str) -> FileResponse:
    """One file of one run, as a download.

    The first route in this project that opens a file the caller named. Every check
    is in `catalog.file_path`, which refuses anything that is not a plain filename in
    that one flat directory -- see its docstring for why the check is spelled out
    rather than left to `Path`.
    """
    try:
        path = catalog.file_path(run_id, name)
    except catalog.ResultsError as failure:
        raise _results_error(failure) from failure
    # `media_type` is not sniffed: a .post.res is text and a .mdpa is text, but both
    # are megabytes nobody wants rendered in a tab. Everything here is a download.
    return FileResponse(path, filename=path.name,
                        media_type="application/octet-stream")


@router.get("/api/results/runs/{run_id}/archive")
def results_archive(run_id: str) -> Response:
    """The whole run directory as one zip -- the deck, the results and the log.

    Server-side rather than zipped in the browser from `frontend/js/zip.js`: the client
    would have to fetch every file first, which is the same megabytes twice over and
    one request per file, to produce an archive of what the server already has laid
    out in a directory.
    """
    try:
        buffer = catalog.archive(run_id)
    except catalog.ResultsError as failure:
        raise _results_error(failure) from failure
    return Response(
        content=buffer.getvalue(), media_type="application/zip",
        headers={"content-disposition": f'attachment; filename="{run_id}.zip"'})
