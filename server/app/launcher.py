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
import subprocess
import sys
import threading
import venv
import webbrowser


SERVER_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = SERVER_ROOT / "requirements.txt"
MINIMUM_PYTHON = (3, 10)


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
    environment = SERVER_ROOT / platform_venv_name()
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
            cwd=SERVER_ROOT,
        )
        requirements_changed(REQUIREMENTS, stamp, update=True)

    return python


def check_environment(python: Path) -> None:
    probe = (
        "import fastapi, gmsh, numpy, uvicorn; "
        "from app.main import app; "
        "print('Environment OK: gmsh ' + gmsh.__version__)"
    )
    subprocess.check_call([str(python), "-c", probe], cwd=SERVER_ROOT)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set up and run the Mockup backend")
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

        command = [
            str(python), "-m", "uvicorn", "app.main:app",
            "--host", args.host, "--port", str(args.port),
        ]
        os.chdir(SERVER_ROOT)
        if args.open_browser:
            url = f"http://{args.host}:{args.port}/"
            threading.Timer(1.0, webbrowser.open, args=(url,)).start()
            return subprocess.call(command)
        os.execv(str(python), command)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Launcher failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
