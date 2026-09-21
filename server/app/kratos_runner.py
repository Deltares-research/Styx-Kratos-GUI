"""Run one exported deck through Kratos' orchestrator.

This module is not imported by the server. It is a script, handed to a *different*
interpreter -- the one Kratos was built for, which is not the one running FastAPI (see
`app.calculate`) -- with the deck's directory as its working directory:

    <kratos python> -m app.kratos_runner ProjectParameters.json

so `import app` must not pull the server in: nothing here imports FastAPI, pydantic or
gmsh, and nothing in `app/__init__.py` may either. It talks to its caller the way any
other command-line tool does, through the exit code and what it writes to stdout.

The orchestrator dance below -- look the orchestrator up in Kratos' registry, import the
module it names, instantiate it around a `Project` and call `Run()` -- is Kratos' own
published way to run a multistage deck, and is lifted from
`applications/GeoMechanicsApplication/tests/helper_utilities.py:run_orchestrator` in the
Kratos source tree.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


def run(parameters_path: Path) -> None:
    """Run the deck `parameters_path` names, in whatever directory it sits in.

    Every path inside a Kratos deck -- the .mdpa, the materials file, the results -- is
    relative to the process' working directory, so the caller sets that to the deck's
    own directory and this reads the file by name from there.
    """
    import KratosMultiphysics as Kratos
    from KratosMultiphysics.project import Project

    with open(parameters_path, encoding="utf-8") as handle:
        settings = Kratos.Parameters(handle.read())

    project = Project(settings)
    entry = Kratos.Registry[project.GetSettings()["orchestrator"]["name"].GetString()]
    orchestrator = getattr(importlib.import_module(entry["ModuleName"]),
                           entry["ClassName"])
    orchestrator(project).Run()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: kratos_runner.py <ProjectParameters.json>", file=sys.stderr)
        return 2
    run(Path(argv[1]))
    return 0


if __name__ == "__main__":
    # No try/except around `run`: a Kratos failure is a traceback, and the traceback is
    # the most useful thing the log can carry back to whoever pressed Calculate.
    sys.exit(main(sys.argv))
