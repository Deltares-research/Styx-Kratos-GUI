"""A stand-in for `core.analysis.calculation.run` in the GUI end-to-end tests (plan alpha 3.4).

It does what a Kratos run leaves behind, for exactly the deck it is given: a run
directory named the way `calculation.new_run_directory` names one, the deck written by
`calculation.write_deck`, synthetic GiD output per stage (`tests/fakes/gid_writer.py`),
member output for the wall, a `kratos.log` with the stage markers the real runner prints
and the residual lines Kratos prints (`log_lines`) -- and the same answer dict. The app has no fake mode: the end-to-end fixture swaps this
in with a monkeypatch, so Results mode can be driven on a machine with no Kratos.

The fields are analytic, so a test can say what the page should show:

    TOTAL_DISPLACEMENT = stage * (1e-3 x, -1e-3 y, 0)        DISPLACEMENT = (1e-3 x, -1e-3 y, 0)
    WATER_PRESSURE     = hydrostatic below y = -3            CAUCHY_STRESS = (0.6 s, s, 0.6 s), s = 18 kPa/m * y
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from core.analysis import calculation
from tests import mdpa
from tests.fakes import gid_writer

WATER_Y = -3.0


def _u(x, y, z, stage):
    return (stage * 1e-3 * x, -stage * 1e-3 * y, 0.0)


def _du(x, y, z, stage):
    return (1e-3 * x, -1e-3 * y, 0.0)


def _pw(x, y, z, stage):
    return (-9810.0 * max(0.0, WATER_Y - y),)


def _stress(x, y, z, stage):
    s = 18000.0 * y
    return (0.6 * s, s, 0.6 * s, 0.0, 0.0, 0.0)


def _member_outputs(export: dict, directory: Path, params: dict) -> list[str]:
    """`<stage>__output_wall.json` for every stage the deck asks for one."""
    deck = mdpa.parse(export["mdpa"])
    written = []
    for index, stage in enumerate(params["orchestrator"]["settings"]["execution_list"],
                                  start=1):
        processes = params["stages"][stage]["stage_settings"].get("processes", {})
        for process in processes.get("json_output", []):
            name = process["Parameters"]["output_file_name"]
            part = process["Parameters"]["model_part_name"].split(".", 1)[1]
            nodes = deck.parts[part].nodes if part in deck.parts else []
            # What each member's process asks for, as a real run writes it: forces and
            # displacements on a beam, tractions on an interface.
            traction = "interface" in name.rsplit("__output_", 1)[-1]
            payload = {"TIME": [1.0]}
            for n in nodes:
                x, y, _ = deck.nodes[n]
                payload[f"NODE_{n}"] = (
                    {"GEO_EFFECTIVE_TRACTION_VECTOR": [[index * 1000.0 * y, 100.0 * y]]}
                    if traction else {
                        "BENDING_MOMENT": [index * 1000.0 * y * (y + 13.0)],
                        "SHEAR_FORCE": [index * 1000.0 * (2 * y + 13.0)],
                        "AXIAL_FORCE": [-index * 100.0 * y],
                        "TOTAL_DISPLACEMENT_X": [-index * 1e-3 * (y + 13.0)],
                        "TOTAL_DISPLACEMENT_Y": [0.0],
                    })
            target = Path(name).name
            (directory / target).write_text(json.dumps(payload), encoding="utf-8")
            written.append(target)
    return written


ITERATIONS = 3
"""Residual lines per stage in the fake log; the last one meets the target."""


def log_lines(stage: str, index: int, total: int) -> list[list[str]]:
    """One stage of the log, as groups of lines: the stage's start, then one group per
    iteration, then the stage's end. Groups, so `slow_run` can write them one by one.

    The residuals fall tenfold per iteration from `10 ** -index`, so each stage's numbers
    say which stage they are."""
    marker = calculation.STAGE_MARKER
    start = [f"{marker} begin {index}/{total} {stage}",
             "GeoMechanics Analysis: Analysis -START-",
             "GeoMechanics Analysis: cycle:  1",
             f"GeoMechanics Analysis: TIME      :  {float(index)}"]
    iterations = []
    for n in range(ITERATIONS):
        relative = 10.0 ** -(index + n)
        lines = [f"RESIDUAL CRITERION:  :: [ Obtained ratio = {relative:g}; Expected ratio "
                 f"= {10.0 ** -(index + ITERATIONS - 1):g}; Absolute norm = "
                 f"{relative * 1e-6:g}; Expected norm =  1e-09]"]
        if n == ITERATIONS - 1:
            lines.append("RESIDUAL CRITERION: Convergence is achieved")
        iterations.append(lines)
    return [start, *iterations, [f"{marker} end {index}/{total} {stage}"]]


def fake_run(export: dict, seconds_per_iteration: float = 0.0) -> dict:
    started = time.monotonic()
    directory = calculation.new_run_directory(export["deck_name"])
    params = json.loads(export["project_parameters"])
    gid_writer.write_run(export, directory,
                         nodal={"TOTAL_DISPLACEMENT": _u, "DISPLACEMENT": _du,
                                "WATER_PRESSURE": _pw},
                         gauss={"CAUCHY_STRESS_TENSOR": _stress})
    _member_outputs(export, directory, params)
    order = params["orchestrator"]["settings"]["execution_list"]
    with calculation.in_progress(directory), \
            open(directory / calculation.LOG_NAME, "w", encoding="utf-8") as log:
        for index, stage in enumerate(order, start=1):
            for group in log_lines(stage, index, len(order)):
                log.write("\n".join(group) + "\n")
                log.flush()
                if seconds_per_iteration and group[0].startswith("RESIDUAL"):
                    time.sleep(seconds_per_iteration)
    inputs = [f"{export['deck_name']}.mdpa", calculation.PARAMETERS_NAME]
    outputs = sorted(p.name for p in directory.iterdir()
                     if p.name not in inputs and p.name != calculation.LOG_NAME
                     and not p.name.endswith("aterials.json"))
    return {"ok": True, "returncode": 0, "stopped": False, "stage": None,
            "seconds": round(time.monotonic() - started, 1), "directory": str(directory),
            "inputs": inputs, "outputs": outputs, "log": calculation.LOG_NAME, "error": None}


def slow_run(seconds_per_iteration: float):
    """`fake_run` that writes its log the way a real run does: an iteration at a time,
    `seconds_per_iteration` apart, while `calculation.current_run` names the run. For
    the end-to-end test of the live convergence window."""
    def run(export: dict) -> dict:
        return fake_run(export, seconds_per_iteration)
    return run
