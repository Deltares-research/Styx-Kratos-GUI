"""Portable setup and launcher for the backend.

Windows and POSIX virtual environments have incompatible directory layouts and native
packages. Keep one generated environment per platform so a shared or copied checkout
cannot accidentally try to execute the other platform's Python binary.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import venv
import webbrowser


ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements.txt"
MINIMUM_PYTHON = (3, 10)

# A development checkout has requirements.txt next to the package; an installed wheel does not.
_is_installed = not REQUIREMENTS.is_file()

EXEC_REPLACES_THE_PROCESS = sys.platform != "win32"
"""Whether `os.execv` can start the server in place of this process. On Windows it
cannot: it starts a second process and ends this one, so `uv run` gives the prompt back
while the server still runs, and it does not quote its arguments, so a Python in a
folder with a space in its name (`OneDrive - Deltares`) is cut at the space. There the
server is a child process instead."""


def platform_venv_name(platform: str = sys.platform) -> str:
    if platform == "win32":
        return ".venv-windows"
    if platform.startswith("linux"):
        return ".venv-linux"
    if platform == "darwin":
        return ".venv-macos"
    return f".venv-{platform.replace('/', '-')}"


def venv_python(environment: Path, platform: str = sys.platform) -> Path:
    if platform == "win32":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def _requirements_digest(requirements: Path) -> str:
    return hashlib.sha256(requirements.read_bytes()).hexdigest()


def requirements_changed(requirements: Path, stamp: Path, *, update: bool = False) -> bool:
    """Compare requirements by content, avoiding unreliable cross-filesystem mtimes."""
    digest = _requirements_digest(requirements)
    changed = not stamp.is_file() or stamp.read_text(encoding="ascii").strip() != digest
    if update:
        stamp.write_text(digest + "\n", encoding="ascii")
        return False
    return changed


def _ensure_supported_python() -> None:
    if sys.version_info < MINIMUM_PYTHON:
        required = ".".join(map(str, MINIMUM_PYTHON))
        raise RuntimeError(f"Python {required} or newer is required; found {sys.version.split()[0]}")


def ensure_environment() -> Path:
    _ensure_supported_python()
    
    # If installed as a wheel, dependencies are already available
    if _is_installed:
        return Path(sys.executable)
    
    # Otherwise, use the development venv approach
    environment = ROOT / platform_venv_name()
    python = venv_python(environment)

    if not python.is_file():
        print(f"Creating {platform_venv_name()} virtual environment...", flush=True)
        # A directory without its platform's interpreter is an interrupted/generated
        # environment. EnvBuilder(clear=True) safely reconstructs that exact cache.
        venv.EnvBuilder(with_pip=True, clear=environment.exists()).create(environment)

    stamp = environment / ".requirements.sha256"
    if requirements_changed(REQUIREMENTS, stamp):
        print("Installing dependencies...", flush=True)
        subprocess.check_call(
            [str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(REQUIREMENTS)],
            cwd=ROOT,
        )
        requirements_changed(REQUIREMENTS, stamp, update=True)

    return python


def check_environment(python: Path) -> None:
    probe = (
        "import fastapi, gmsh, numpy, uvicorn; "
        "from backend.main import app; "
        "from core.version import describe; "
        "print('Environment OK: Styx ' + describe() + ', gmsh ' + gmsh.__version__)"
    )
    subprocess.check_call([str(python), "-c", probe], cwd=ROOT)


ALLOWED_HOSTS_ENV = "KRATOS_GUI_ALLOWED_HOSTS"
"""Host names the server answers to besides the loopback ones, comma-separated. Read by
`backend.middleware`'s Host check; defined here because the launcher runs before the
server's dependencies are installed, so it cannot import the backend."""

LOOPBACK = ("127.0.0.1", "localhost", "::1", "[::1]")
ALL_INTERFACES = ("0.0.0.0", "::", "[::]")


def server_environment(args: argparse.Namespace, base: dict[str, str]) -> dict[str, str]:
    """What the server process needs in its environment beyond `base`.

    `--host modelling-pc` has to be reachable *as* modelling-pc, or the Host check would
    refuse the very address the user chose. An all-interfaces bind names no host, so it
    adds none: which name the LAN uses is for `KRATOS_GUI_ALLOWED_HOSTS` to say.
    """
    if args.host in LOOPBACK or args.host in ALL_INTERFACES:
        return {}
    extra = [h for h in (base.get(ALLOWED_HOSTS_ENV, ""), args.host) if h]
    return {ALLOWED_HOSTS_ENV: ",".join(extra)}


def port_in_use(host: str, port: int) -> bool:
    """Whether something already answers on `port` -- most likely a server left running.

    Probed by connecting, not by binding: on Windows a test bind can succeed on a port
    another process is listening on. An all-interfaces address is reached on loopback.
    """
    if host in ALL_INTERFACES:
        host = "::1" if ":" in host else "127.0.0.1"
    try:
        with socket.create_connection((host.strip("[]"), port), timeout=0.5):
            return True
    except OSError:
        return False


def open_when_ready(url: str, host: str, port: int, server: subprocess.Popen,
                    *, timeout: float = 120.0, interval: float = 0.25) -> bool:
    """Open `url` in the browser once the server answers on `port`.

    Uvicorn only binds the port after the app is imported and started, so the first
    successful connection means the page can load. Opening the browser earlier shows a
    "site can't be reached" page until the server is up. Gives up, without opening
    anything, if the server exits or `timeout` seconds pass first.
    """
    deadline = time.monotonic() + timeout
    while server.poll() is None and time.monotonic() < deadline:
        if port_in_use(host, port):
            webbrowser.open(url)
            return True
        time.sleep(interval)
    return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set up and run the kratos-GUI backend")
    parser.add_argument("--check", action="store_true", help="install and validate dependencies, then exit")
    parser.add_argument("--open-browser", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        python = ensure_environment()
        if args.check:
            check_environment(python)
            return 0

        # A new server could not bind the port and would exit, while the browser opened
        # on the old one -- with the project, and the code, it had when it was started.
        if port_in_use(args.host, args.port):
            print(f"Port {args.port} is already in use, most likely by a server that is "
                  "still running from before. Close that window (or end its python.exe), "
                  f"or start this one on another port (--port {args.port + 1}).",
                  file=sys.stderr)
            return 1

        command = [
            str(python), "-m", "uvicorn", "backend.main:app",
            "--host", args.host, "--port", str(args.port),
        ]
        
        # When installed, use current directory; in development, change to ROOT
        if not _is_installed:
            os.chdir(ROOT)
        
        os.environ.update(server_environment(args, dict(os.environ)))
        if args.open_browser:
            url = f"http://{args.host}:{args.port}/"
            with subprocess.Popen(command) as server:
                threading.Thread(target=open_when_ready,
                                 args=(url, args.host, args.port, server),
                                 daemon=True).start()
                try:
                    return server.wait()
                except BaseException:
                    server.kill()
                    raise
        if not EXEC_REPLACES_THE_PROCESS:
            return subprocess.call(command)
        os.execv(str(python), command)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Launcher failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
