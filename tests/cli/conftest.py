"""What the command-line tests share: a way to run `kratos-cli` in this process, a small
project file, and a machine with no Kratos and no runs of its own.

`cli.main.main(argv)` is called directly rather than through a subprocess, so a failure
shows where it happened and a test costs milliseconds. `tests/cli/test_wrappers.py` is
where the command is started the way a user starts it.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from cli.main import main
from core import session
from core.analysis import calculation
from core.model.schemas import DimensionUpdate
from core.model.templates import seed_project


@dataclass
class Ran:
    code: int
    out: str
    err: str

    def json(self) -> object:
        return json.loads(self.out)


@pytest.fixture
def cli(capsys):
    """`cli("show", path)`: run one command, and what it printed and returned."""
    def run(*argv) -> Ran:
        capsys.readouterr()
        code = main([str(arg) for arg in argv])
        printed = capsys.readouterr()
        return Ran(code, printed.out, printed.err)
    return run


@pytest.fixture
def site(tmp_path) -> Path:
    """The demo model as a plane-strain section with a coarse mesh: a project file that
    meshes in a few hundredths of a second."""
    project, _ = session.set_dimension(seed_project(), DimensionUpdate(dimension=2))
    project = session.with_value(project, "mesh.element_size", 5.0)
    return session.save(project, tmp_path / "site.json")


@pytest.fixture(autouse=True)
def this_machine_has_no_kratos(request, tmp_path, monkeypatch):
    """Runs land in this test's own folder, and no machine's settings reach in -- except
    into a `kratos` test, which is about this machine's Kratos."""
    monkeypatch.setenv(calculation.RUNS_ENV, str(tmp_path / "runs"))
    if request.node.get_closest_marker("kratos"):
        return
    monkeypatch.setattr(calculation, "SETTINGS_FILE", tmp_path / "no-settings.json")
    for name in (calculation.PYTHON_ENV, calculation.KRATOS_ENV, calculation.TIMEOUT_ENV):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def no_colour_from_this_machine(monkeypatch):
    """What is printed is compared as text: a terminal's colour settings stay out."""
    for name in ("NO_COLOR", "FORCE_COLOR", "TERM"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def stand_in_kratos(monkeypatch):
    """This interpreter in Kratos' place, running `script` in the run directory (the
    pattern of tests/test_calculate.py)."""
    def use(script: str = "open('stand_in.post.res', 'w').close()") -> None:
        monkeypatch.setattr(calculation, "COMMAND", ["-c", script])
        monkeypatch.setenv(calculation.PYTHON_ENV, sys.executable)
    return use
