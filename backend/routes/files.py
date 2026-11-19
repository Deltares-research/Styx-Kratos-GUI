"""The Files routes: a folder the user chooses, and the files of one save written into it.

A browser's own folder window refuses some folders outright, Downloads, Desktop and Documents
among them, and no page can talk it out of that. The server runs on the user's computer, so
it opens the system's window instead and writes the files itself.

A request never names a place on disk. It can only write a picture or a CSV file directly
into a folder the user chose in that window, by an id that only this answer gave out. An id
is for one save: the page hands it back when the save ends, and one left unused for a while
is forgotten all the same, so a tab closed during a save leaves no way into the folder. All of
it is for a browser on the same computer: from another one, the system's window would open on
the server, out of the user's sight, and the frontend falls back to the browser's own window.

One folder window is open at a time, and it closes after a while: each one holds a thread of
the server until it closes.

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
import time
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from backend.middleware import on_this_computer

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
FOLDER_WINDOW_SECONDS = 10 * 60
"""How long the folder window waits for a choice; then it closes, as if it was dismissed."""
FOLDER_IDLE_SECONDS = 15 * 60
"""How long a folder id lasts with no file asked for or written."""

PICTURE_JOB_ENV = "KRATOS_GUI_PICTURE_JOB"
"""The token of the one picture job this server was started for; unset in the GUI's own."""

SAVED_TYPES = (".png", ".pdf", ".svg", ".csv")
FILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


@dataclass
class Folder:
    path: Path
    used: float
    """`time.monotonic()` when it was last chosen, asked about or written to."""


_folders: dict[str, Folder] = {}
"""The folders of the saves under way, by their id."""
_last_chosen: Path | None = None
"""Where the folder window opens next: where the last one ended."""
_window_open = False


class NoFolderWindow(Exception):
    """The system's window could not be opened here."""


def choose_folder(start: Path) -> str:
    """The folder chosen in the system's window, opened at `start`. `""` if it was dismissed,
    or if nobody chose in time."""
    flags = 0
    if sys.platform == "win32":         # no console window comes up with it
        flags = subprocess.CREATE_NO_WINDOW
    try:
        done = subprocess.run([sys.executable, "-c", FOLDER_WINDOW, FOLDER_TITLE, str(start)],
                              capture_output=True, encoding="utf-8", creationflags=flags,
                              timeout=FOLDER_WINDOW_SECONDS)
    except subprocess.TimeoutExpired:   # `run` has closed the window already
        return ""
    except OSError as failure:
        raise NoFolderWindow(str(failure)) from failure
    if done.returncode:
        raise NoFolderWindow(done.stderr.strip())
    return done.stdout.strip()


def _only_this_computer(request: Request) -> None:
    if not on_this_computer(request):
        raise HTTPException(status_code=403, detail="Only a browser on this computer can do this.")


def _forget_idle() -> None:
    now = time.monotonic()
    for folder in [key for key, known in _folders.items()
                   if now - known.used > FOLDER_IDLE_SECONDS]:
        del _folders[folder]


def _target(request: Request, folder: str, name: str) -> Path:
    _only_this_computer(request)
    _forget_idle()
    if folder not in _folders:
        raise HTTPException(status_code=404, detail="That folder is not known. Save again.")
    if not FILE_NAME.fullmatch(name) or not name.lower().endswith(SAVED_TYPES):
        raise HTTPException(status_code=422, detail=f"{name!r} is not the name of a picture or a CSV file.")
    known = _folders[folder]
    known.used = time.monotonic()
    return known.path / name


@router.post("/api/files/folder")
async def open_folder_window(request: Request) -> dict:
    """Opens the system's folder window. Where it cannot, `no_window` says why, and the browser's
    own takes over: that is a normal answer, not a failure of this request. While a window is
    open, `busy` says so and no other opens."""
    global _last_chosen, _window_open
    if not on_this_computer(request):
        return {"no_window": "The browser is on another computer."}
    if _window_open:
        return {"busy": "A folder window is open already: choose the folder in it, or close it."}
    _forget_idle()
    start = _last_chosen or Path.home() / "Downloads"
    _window_open = True
    try:
        chosen = await asyncio.to_thread(choose_folder, start)
    except NoFolderWindow as failure:
        return {"no_window": str(failure)}
    finally:
        _window_open = False
    if not chosen:
        return {"cancelled": True}
    folder = secrets.token_urlsafe(16)
    _last_chosen = Path(chosen)
    _folders[folder] = Folder(_last_chosen, time.monotonic())
    return {"id": folder, "name": chosen}


@router.delete("/api/files/folder/{folder}")
def release_folder(folder: str, request: Request) -> dict:
    """The save that had this folder has ended: its id writes nothing more."""
    _only_this_computer(request)
    return {"released": _folders.pop(folder, None) is not None}


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
