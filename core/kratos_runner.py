"""Run one exported deck through Kratos' orchestrator.

This module is not imported by the server. It is a script, handed to a *different*
interpreter -- the one Kratos was built for, which is not the one running FastAPI (see
`core.calculate`) -- with the deck's directory as its working directory:

    <kratos python> -m core.kratos_runner ProjectParameters.json

so `import core` must not pull the server in: nothing here imports FastAPI, pydantic or
gmsh, and nothing in `core/__init__.py` may either. It talks to its caller the way any
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


STAGE_MARKER = "[kratos-gui] stage"
"""How this script names the stage it is on, for `core.calculate` to read back.

Ours rather than Kratos': `SequentialOrchestrator.Run` loops over the execution list
calling `CheckStageSettings`, `CreateStage`, `RunCurrentStagePreprocess`, the stage's
own `Run`, then `RunCurrentStagePostprocess`, and prints nothing naming the stage
through any of it. Confirmed by reading the orchestrator and by a real seven-stage run
log, both of which say the same thing: there is no banner to parse.

So a deck that dies in the middle used to come back as "it failed", with the reason but
not the place. On seven stages that is most of the message missing.
"""


def announcing(orchestrator_class):
    """`orchestrator_class`, wrapped so that it says which stage it is starting.

    A subclass of whatever the registry named, overriding the two per-stage hooks the
    base `Orchestrator` publishes. Deliberately *not* a reimplementation of `Run`: that
    loop also does checkpointing, output settings and the final-data dictionary, and a
    copy of it here would go stale silently the first time Kratos changed it. The
    hooks are called once per stage and in a defined place, which is all this needs.

    `begin` is printed *before* the preprocess rather than after, because the
    preprocess is itself a place a deck fails -- it is where the Activate and
    Deactivate operations run, so a phase naming a part the mdpa does not have throws
    here. `end` is printed after the postprocess, so a stage is only finished once
    everything belonging to it is.

    Flushed on every line: stdout is a pipe, and a run that dies takes an unflushed
    buffer with it -- which would lose exactly the marker that says where it died.
    """
    class Announcing(orchestrator_class):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._stage_index = 0

        def _announce(self, event: str, stage_name: str) -> None:
            print(f"{STAGE_MARKER} {event} {self._stage_index}/"
                  f"{self.GetNumberOfStages()} {stage_name}", flush=True)

        def RunCurrentStagePreprocess(self, stage_name, data=None):
            self._stage_index += 1
            self._announce("begin", stage_name)
            super().RunCurrentStagePreprocess(stage_name, data)

        def RunCurrentStagePostprocess(self, stage_name, data=None):
            super().RunCurrentStagePostprocess(stage_name, data)
            self._announce("end", stage_name)

    Announcing.__name__ = f"Announcing{orchestrator_class.__name__}"
    return Announcing


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
    announcing(orchestrator)(project).Run()


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
