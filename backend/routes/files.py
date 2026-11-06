"""The Files routes: a folder the user chooses, and the files of one save written into it.

A browser's own folder window refuses some folders outright, Downloads, Desktop and Documents
among them, and no page can talk it out of that. The server runs on the user's computer, so
it opens the system's window instead and writes the files itself.

A request never names a place on disk. It can only write a picture or a CSV file directly
into a folder the user chose in that window, by an id that only this answer gave out. All of
it is for a browser on the same computer: from another one, the system's window would open on
the server, out of the user's sight, and the frontend falls back to the browser's own window.

`kratos-cli picture` starts a server of its own and opens the page with a job in its address
(`cli/terminal/pictures.py`). Only that server knows the job's token, so a link to a user's
own GUI with a job in it draws nothing and sends nothing.
"""

from __future__ import annotations

import asyncio
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from backend.middleware import LOOPBACK_HOSTS, host_name

router = APIRouter()

# In a process of its own: Tk wants its own main thread, and a window that fails to open
# (no display, a Python with no Tk) must not take the server with it. On top, or it can open
# behind the browser, where nobody sees it.
FOLDER_WINDOW = """
import sys, tkinter, tkinter.filedialog
sys.stdout.reconfigure(encoding="utf-8")
root = tkinter.Tk()
root.withdraw()
root.attributes("-topmost", True)
root.update()
print(tkinter.filedialog.askdirectory(parent=root, title=sys.argv[1], initialdir=sys.argv[2]))
"""
FOLDER_TITLE = "Choose a folder for the pictures"

PICTURE_JOB_ENV = "KRATOS_GUI_PICTURE_JOB"
"""The token of the one picture job this server was started for; unset in the GUI's own."""

SAVED_TYPES = (".png", ".pdf", ".svg", ".csv")
FILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

_folders: dict[str, Path] = {}
"""The folders chosen since the server started, the last one last."""


class NoFolderWindow(Exception):
    """The system's window could not be opened here."""


def choose_folder(start: Path) -> str:
    """The folder chosen in the system's window, opened at `start`. `""` if it was dismissed."""
    flags = 0
    if sys.platform == "win32":         # no console window comes up with it
        flags = subprocess.CREATE_NO_WINDOW
    try:
        done = subprocess.run([sys.executable, "-c", FOLDER_WINDOW, FOLDER_TITLE, str(start)],
                              capture_output=True, encoding="utf-8", creationflags=flags)
    except OSError as failure:
        raise NoFolderWindow(str(failure)) from failure
    if done.returncode:
        raise NoFolderWindow(done.stderr.strip())
    return done.stdout.strip()


def _on_this_computer(request: Request) -> bool:
    return (request.client is not None and request.client.host in LOOPBACK_HOSTS
            and host_name(request.headers.get("host", "")) in LOOPBACK_HOSTS)


def _target(request: Request, folder: str, name: str) -> Path:
    if not _on_this_computer(request):
        raise HTTPException(status_code=403, detail="Only a browser on this computer can do this.")
    if folder not in _folders:
        raise HTTPException(status_code=404, detail="That folder is not known. Save again.")
    if not FILE_NAME.fullmatch(name) or not name.lower().endswith(SAVED_TYPES):
        raise HTTPException(status_code=422, detail=f"{name!r} is not the name of a picture or a CSV file.")
    return _folders[folder] / name


@router.post("/api/files/folder")
async def open_folder_window(request: Request) -> dict:
    """Opens the system's folder window. Where it cannot, `no_window` says why, and the browser's
    own takes over: that is a normal answer, not a failure of this request."""
    if not _on_this_computer(request):
        return {"no_window": "The browser is on another computer."}
    start = next(reversed(_folders.values()), Path.home() / "Downloads")
    try:
        chosen = await asyncio.to_thread(choose_folder, start)
    except NoFolderWindow as failure:
        return {"no_window": str(failure)}
    if not chosen:
        return {"cancelled": True}
    folder = secrets.token_urlsafe(16)
    _folders.update({folder: Path(chosen)})
    return {"id": folder, "name": chosen}


@router.get("/api/files/folder/{folder}/{name}")
def file_exists(folder: str, name: str, request: Request) -> dict:
    return {"exists": _target(request, folder, name).exists()}


@router.put("/api/files/folder/{folder}/{name}")
async def write_file(folder: str, name: str, request: Request) -> dict:
    target = _target(request, folder, name)
    content = await request.body()
    try:
        await asyncio.to_thread(target.write_bytes, content)
    except OSError as failure:
        raise HTTPException(status_code=500, detail=f"{target} could not be written: {failure}") from failure
    return {"path": str(target)}


@router.get("/api/files/picture-job/{token}")
def picture_job(token: str) -> dict:
    """Whether the page may run the job in its address: only with the token of this server."""
    expected = os.environ.get(PICTURE_JOB_ENV, "")
    return {"ok": bool(expected) and secrets.compare_digest(token.encode(), expected.encode())}
