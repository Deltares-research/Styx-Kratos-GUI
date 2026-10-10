"""A stand-in for `app.calculate.run` in the GUI end-to-end tests (plan alpha 3.4).

It does what a Kratos run leaves behind, for exactly the deck it is given: a run
directory named the way `calculate.new_run_directory` names one, the deck written by
`calculate.write_deck`, synthetic GiD output per stage (`tests/fakes/gid_writer.py`),
member output for the wall, a `kratos.log` with the stage markers the real runner prints
-- and the same answer dict. The app has no fake mode: the end-to-end fixture swaps this
in with a monkeypatch, so Results mode can be driven on a machine with no Kratos.

The fields are analytic, so a test can say what the page should show:

    TOTAL_DISPLACEMENT = stage * (1e-3 x, -1e-3 y, 0)        DISPLACEMENT = (1e-3 x, -1e-3 y, 0)
    WATER_PRESSURE     = hydrostatic below y = -3            CAUCHY_STRESS = (0.6 s, s, 0.6 s), s = 18 kPa/m * y
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from app import calculate
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
            payload = {"TIME": [1.0]}
            for n in nodes:
                x, y, _ = deck.nodes[n]
                payload[f"NODE_{n}"] = {
                    "BENDING_MOMENT": [index * 1000.0 * y * (y + 13.0)],
                    "SHEAR_FORCE": [index * 1000.0 * (2 * y + 13.0)],
                    "AXIAL_FORCE": [-index * 100.0 * y],
                    "TOTAL_DISPLACEMENT_X": [-index * 1e-3 * (y + 13.0)],
                    "TOTAL_DISPLACEMENT_Y": [0.0],
                    "GEO_EFFECTIVE_TRACTION_VECTOR": [[index * 1000.0 * y, 100.0 * y]],
                }
            target = Path(name).name
            (directory / target).write_text(json.dumps(payload), encoding="utf-8")
            written.append(target)
    return written


def fake_run(export: dict) -> dict:
    started = time.monotonic()
    directory = calculate.new_run_directory(export["deck_name"])
    params = json.loads(export["project_parameters"])
    gid_writer.write_run(export, directory,
                         nodal={"TOTAL_DISPLACEMENT": _u, "DISPLACEMENT": _du,
                                "WATER_PRESSURE": _pw},
                         gauss={"CAUCHY_STRESS_TENSOR": _stress})
    _member_outputs(export, directory, params)
    order = params["orchestrator"]["settings"]["execution_list"]
    log = []
    for index, stage in enumerate(order, start=1):
        log.append(f"{calculate.STAGE_MARKER} begin {index}/{len(order)} {stage}")
        log.append(f"{calculate.STAGE_MARKER} end {index}/{len(order)} {stage}")
    (directory / calculate.LOG_NAME).write_text("\n".join(log) + "\n", encoding="utf-8")
    inputs = [f"{export['deck_name']}.mdpa", calculate.PARAMETERS_NAME]
    outputs = sorted(p.name for p in directory.iterdir()
                     if p.name not in inputs and p.name != calculate.LOG_NAME
                     and not p.name.endswith("aterials.json"))
    return {"ok": True, "returncode": 0, "stage": None,
            "seconds": round(time.monotonic() - started, 1), "directory": str(directory),
            "inputs": inputs, "outputs": outputs, "log": calculate.LOG_NAME, "error": None}
