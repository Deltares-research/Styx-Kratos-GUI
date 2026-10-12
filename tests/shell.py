"""The bash a test runs a shell script with: `kratos-cli.sh`, or a script of commands.

On Windows that is Git's bash. `C:\\Windows\\System32\\bash.exe` is WSL's, which runs the
script in Linux, where this checkout's Windows environment is not, so it is never the
one: Git's is found beside `git`, then on PATH outside the Windows folders.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def bash() -> Path | None:
    """The bash to run a shell script with, or None when this machine has none."""
    if sys.platform != "win32":
        found = shutil.which("bash")
        return Path(found) if found else None
    git = shutil.which("git")
    if git:
        for folder in Path(git).resolve().parents:
            for candidate in (folder / "bin" / "bash.exe", folder / "usr" / "bin" / "bash.exe"):
                if candidate.is_file():
                    return candidate
    found = shutil.which("bash")
    if found and "\\windows\\" not in found.lower() and "windowsapps" not in found.lower():
        return Path(found)
    return None
