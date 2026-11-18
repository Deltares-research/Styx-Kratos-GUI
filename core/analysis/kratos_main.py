"""Run one exported deck through Kratos' orchestrator.

This module is not imported by the server. It is a script, handed to a *different*
interpreter -- the one Kratos was built for, which is not the one running FastAPI (see
`core.analysis.calculation`) -- with the deck's directory as its working directory:

    <kratos python> -m core.analysis.kratos_main ProjectParameters.json

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
"""How this script names the stage it is on, for `core.analysis.calculation` to read back.

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
    Deactivate operations run, so a stage naming a part the mdpa does not have throws
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


UNBUFFERED_NOTE = "[kratos-gui] note: Kratos output stays buffered and arrives in blocks"
"""Printed when `unbuffer_output` could not turn the C runtime's buffer off. The run goes
on: the log is still complete, only a live convergence plot updates in bursts."""

# The C runtime's "no buffer" mode for `setvbuf`. The value differs per runtime: the
# Microsoft one uses 0x4, glibc and the BSD libc use 2.
_IONBF = 0x4 if sys.platform == "win32" else 2


def unbuffer_output() -> bool:
    """Make the C runtime send Kratos' output to the pipe at once, not in blocks.

    Kratos prints from C++ through the C runtime's `stdout`. Into a pipe that stream is
    block-buffered, so the server gets Kratos' lines in bursts and out of order with
    the lines Python prints (the stage markers). Measured on Windows (2026-11-06): 20
    residual lines came in 2 bursts, and stage markers landed inside other lines. A live
    convergence plot would stay empty for minutes on a large model and then jump.
    Turning the buffer off before Kratos is imported fixes both, and a run is not
    slower. Python's own `sys.stdout` is set to line buffering for the same reason.

    True when the buffer is off. False when the call failed, for example with a Kratos
    build that has its own static C runtime; the run then works as before.
    """
    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass
    try:
        import ctypes

        if sys.platform == "win32":
            runtime = ctypes.CDLL("ucrtbase")
            runtime.__acrt_iob_func.restype = ctypes.c_void_p
            runtime.__acrt_iob_func.argtypes = [ctypes.c_uint]
            stream = runtime.__acrt_iob_func(1)
        else:
            runtime = ctypes.CDLL(None)
            symbol = "__stdoutp" if sys.platform == "darwin" else "stdout"
            stream = ctypes.c_void_p.in_dll(runtime, symbol).value
        runtime.setvbuf.restype = ctypes.c_int
        runtime.setvbuf.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int,
                                    ctypes.c_size_t]
        return bool(stream) and runtime.setvbuf(stream, None, _IONBF, 0) == 0
    except (OSError, AttributeError, ValueError):
        return False


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
        print("usage: python -m core.analysis.kratos_main <ProjectParameters.json>", file=sys.stderr)
        return 2
    # Before Kratos is imported: its C++ half takes the C runtime's stdout as it is then.
    if not unbuffer_output():
        print(UNBUFFERED_NOTE, flush=True)
    run(Path(argv[1]))
    return 0


if __name__ == "__main__":
    # No try/except around `run`: a Kratos failure is a traceback, and the traceback is
    # the most useful thing the log can carry back to whoever pressed Calculate.
    sys.exit(main(sys.argv))
