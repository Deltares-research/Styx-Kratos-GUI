"""The Feedback routes: a report written in the GUI, saved as a ZIP file (`core/feedback.py`).

The page sends what only it knows -- the message, where in the app it was written, its
Session log and Model history, a picture of the view, the files the user added (a pasted
screenshot, a document, ...), the errors it saw. The server adds what only it knows: the project as it holds it, its own log
(`backend/server_log.py`), the files of the open run, and the version. The report goes in
the writer's ZIP file of the day in the feedback folder, and the answer says where;
`POST /api/feedback/folder` opens that folder in the system's file browser, so the file can
be found and passed on.
"""

from __future__ import annotations

import base64
import binascii
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend import server_log, store
from backend.middleware import on_this_computer
from core import feedback, session, version

router = APIRouter()

MAX_LOG = 2_000_000
"""The longest log the page may send, in characters: far more than a day's Session log."""
MAX_PICTURE = 20_000_000
"""The longest picture of the view, in base64 characters (about 15 MB)."""
MAX_FILE = 4 * feedback.MAX_ATTACHMENT_BYTES // 3 + 1000
"""The longest file the user added, in base64 characters, with room for the data-URL head."""


class Attachment(BaseModel):
    """A file the user added: its name, and its bytes as base64 or as a data URL."""

    name: str = Field(max_length=255)
    data: str = Field(max_length=MAX_FILE)


class FeedbackRequest(BaseModel):
    kind: str
    message: str = Field("", max_length=feedback.MAX_MESSAGE)
    name: str = Field("", max_length=feedback.MAX_NAME)
    context: dict[str, Any] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    session_log: str = Field("", max_length=MAX_LOG)
    model_history: str = Field("", max_length=MAX_LOG)
    view: str | None = Field(None, max_length=MAX_PICTURE)
    """The picture of the model view: a PNG, base64-encoded, with or without the
    `data:image/png;base64,` in front."""
    attachments: list[Attachment] = Field(default_factory=list,
                                          max_length=feedback.MAX_ATTACHMENTS)
    include_project: bool = True
    run: str | None = None


def _decoded(encoded: str | None, what: str) -> bytes | None:
    """The bytes of a base64 text or data URL. Whether they are right, `feedback.check` says."""
    if not encoded:
        return None
    data = encoded.split(",", 1)[1] if encoded.startswith("data:") else encoded
    try:
        return base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as failure:
        raise HTTPException(status_code=422, detail=f"The {what} is not base64.") from failure


@router.post("/api/feedback")
def save_feedback(asked: FeedbackRequest) -> dict:
    """Add the report to the day's ZIP file, and say where: its `path`, `folder` and `name`,
    the `report`'s folder in it, that report's `files`, and how many `reports` it holds."""
    report = feedback.Report(
        kind=asked.kind, message=asked.message, name=asked.name, source="GUI",
        version=version.describe(), context=asked.context, errors=asked.errors,
        logs={"session-log.txt": asked.session_log, "model-history.txt": asked.model_history,
              "server-log.txt": server_log.text()},
        project=session.dumps(store.get()) if asked.include_project else None,
        view=_decoded(asked.view, "picture of the view"),
        attachments=[(file.name, _decoded(file.data, f"file {file.name}") or b"")
                     for file in asked.attachments], run=asked.run)
    try:
        saved = feedback.write(report)
    except feedback.FeedbackError as failure:
        raise HTTPException(status_code=422, detail=str(failure)) from failure
    server_log.LOGGER.info("feedback saved: %s in %s", saved.report, saved.path)
    return {"path": str(saved.path), "folder": str(saved.path.parent), "name": saved.path.name,
            "report": saved.report, "files": saved.files, "reports": saved.reports}


def open_in_file_browser(folder: Path) -> None:
    """Show `folder` in the system's file browser."""
    if sys.platform == "win32":
        os.startfile(folder)  # type: ignore[attr-defined]  # only on Windows
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@router.post("/api/feedback/folder")
def show_feedback_folder(request: Request) -> dict:
    """Open the feedback folder in the system's file browser. Only for a browser on this
    computer: on another one, the window would open out of the user's sight. `opened` is
    false then, and `folder` still says where the reports are."""
    where = feedback.folder()
    if not on_this_computer(request):
        return {"opened": False, "folder": str(where),
                "reason": "The browser is on another computer than the server."}
    try:
        where.mkdir(parents=True, exist_ok=True)
        open_in_file_browser(where)
    except OSError as failure:
        return {"opened": False, "folder": str(where), "reason": str(failure)}
    return {"opened": True, "folder": str(where)}
