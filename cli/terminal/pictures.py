"""A picture for `kratos-cli picture`, drawn by the same page the GUI draws it with.

What a picture shows is decided in the browser (`frontend/js/picture-draw.js`), from a scene
only the browser builds. A second renderer in Python would have to draw every support, load
and water level again, and would drift from the screen. So this starts the server and the
installed browser with no window, and hands the page a job in its address. The page does
what a user would do and posts each file here.

Both are separate processes: the command line stays a front end of `core`
(`tests/test_layout.py`), and only this one command needs them. The files come to a small
receiver of our own, on an address only this process knows, so the server gains no route
that takes files. The server is told the job's token (`JOB_ENV`), and the page runs a job
only when its server knows the token: a link to the GUI with a job in it does nothing.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cli.terminal.output import CommandError

ROOT = Path(__file__).resolve().parents[2]
BROWSER_ENV = "KRATOS_GUI_BROWSER"
"""The browser to use, for one that is not where `find_browser` looks."""
BROWSER_NAMES = ("chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                 "msedge", "microsoft-edge", "microsoft-edge-stable")
BROWSER_PATHS = (
    r"Google\Chrome\Application\chrome.exe",
    r"Microsoft\Edge\Application\msedge.exe",
)
MAC_BROWSERS = ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
WINDOW = "1600,1000"
"""The shape the page is laid out in, and so the shape of the picture."""
SERVER_START_SECONDS = 60.0
WAIT_SECONDS = 600.0
"""A mesh and every field of every stage of a large run can take minutes."""
JOB_ENV = "KRATOS_GUI_PICTURE_JOB"
"""The token of the job, for the server this starts (`backend/routes/files.py`)."""


def find_browser() -> str | None:
    """Chrome or Edge: `KRATOS_GUI_BROWSER`, then the PATH, then where they install."""
    configured = os.environ.get(BROWSER_ENV)
    if configured:
        return configured
    for name in BROWSER_NAMES:
        found = shutil.which(name)
        if found:
            return found
    bases = [os.environ.get(name) for name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
    candidates = [Path(base) / path for base in bases if base for path in BROWSER_PATHS]
    candidates += [Path(path) for path in MAC_BROWSERS]
    return next((str(path) for path in candidates if path.is_file()), None)


class Receiver:
    """Takes the files the page posts. The token in the path keeps out anything else on
    this machine that finds the port."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.answer: dict | None = None
        self.done = threading.Event()
        self.token = secrets.token_urlsafe(16)
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                parts = urllib.parse.urlsplit(self.path)
                prefix = f"/{receiver.token}/"
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                if not parts.path.startswith(prefix):
                    self.send_error(404)
                    return
                receiver.take(parts.path[len(prefix):], urllib.parse.parse_qs(parts.query), body)
                self.send_response(204)
                self.end_headers()

            def log_message(self, format, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}/{self.token}"

    def take(self, what: str, query: dict, body: bytes) -> None:
        if what == "file":
            # A name, not a path: nothing the page sends can choose where a file lands.
            self.files[Path(query["name"][0]).name] = body
        elif what == "done":
            self.answer = json.loads(body)
            self.done.set()

    def __enter__(self) -> "Receiver":
        self.thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self.server.shutdown()
        self.server.server_close()


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def start_server(job_token: str) -> tuple[subprocess.Popen, str]:
    """The GUI's server in a process of its own, answering, and its address. It runs the
    job with `job_token` and no other."""
    port = _free_port()
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1",
         "--port", str(port), "--log-level", "error", "--ws", "none"],
        cwd=ROOT, env={**os.environ, JOB_ENV: job_token},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=sys.platform != "win32")
    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + SERVER_START_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=30):
                return process, url
        except (urllib.error.URLError, OSError):
            time.sleep(0.1)
    stop(process)
    raise CommandError("The Styx server did not start, so no picture could be drawn. "
                       "`run.bat --check` or `./run.sh --check` tests the installation.")


def put_project(url: str, project_json: str) -> None:
    request = urllib.request.Request(url + "/api/project", data=project_json.encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="PUT")
    try:
        with urllib.request.urlopen(request, timeout=120):
            pass
    except urllib.error.HTTPError as failure:
        raise CommandError(f"The server refused the model: {failure.read().decode()}") from None


def open_page(browser: str, url: str, profile: str) -> subprocess.Popen:
    command = [browser, "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
               "--no-default-browser-check", "--disable-gpu", f"--window-size={WINDOW}"]
    # A browser refuses its sandbox to root, which is what a container runs as.
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        command.append("--no-sandbox")
    return subprocess.Popen(command + [url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=sys.platform != "win32")


def stop(process: subprocess.Popen) -> None:
    """The process and what it started: a server left behind keeps its gmsh worker, and
    on Windows a virtual environment's python.exe is itself a parent of the real one."""
    if process.poll() is None:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                process.kill()
    process.wait()


def draw(job: dict, project_json: str | None = None) -> dict[str, bytes]:
    """The files of `job` (see `prepareJob` in `frontend/js/picture.js`), by name."""
    browser = find_browser()
    if browser is None:
        raise CommandError(
            "`kratos-cli picture` draws with Chrome or Edge, and neither was found. Install "
            f"one, or set {BROWSER_ENV} to the program. The GUI's camera button saves the "
            "same pictures.")
    token = secrets.token_urlsafe(16)
    server, url = start_server(token)
    page = None
    try:
        if project_json is not None:
            put_project(url, project_json)
        with Receiver() as receiver, tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
            address = url + "/?" + urllib.parse.urlencode(
                {"picture": json.dumps({**job, "token": token, "receiver": receiver.url})})
            page = open_page(browser, address, profile)
            try:
                _wait(receiver, page)
            finally:
                stop(page)
    finally:
        stop(server)
    answer = receiver.answer or {}
    if not answer.get("ok"):
        raise CommandError(answer.get("error") or "The picture could not be drawn.")
    if answer.get("count") != len(receiver.files):
        raise CommandError(f"The page saved {answer.get('count')} files, and "
                           f"{len(receiver.files)} arrived.")
    return receiver.files


def _wait(receiver: Receiver, page: subprocess.Popen) -> None:
    deadline = time.monotonic() + WAIT_SECONDS
    while not receiver.done.wait(0.2):
        if time.monotonic() > deadline:
            raise CommandError(f"No answer from the browser after {WAIT_SECONDS:.0f} s.")
        # Its last post may still be on the way when it stops.
        if page.poll() is not None and not receiver.done.wait(2):
            raise CommandError(f"The browser stopped (code {page.returncode}) before the "
                               "pictures were done.")
