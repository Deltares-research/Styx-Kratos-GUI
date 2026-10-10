"""Every key of the CROW deck against the validated deck's (plan sec 8.2).

`test_crow_reference.py` compares the *values* the two decks share, process modules and
material variables. A comparison of shared values cannot see a key one deck leaves out
-- which is how a missing GEO_DRAINAGE_TYPE once read as "2/2 agree". So here the key
*sets* are compared -- inside every process's Parameters, the solver settings and the
output settings, across all seven stages -- and the difference is pinned, each entry with
its reason. A key appearing on either side fails until it is added here, with one.

Needs the gitignored reference deck (`examples/crow/`); skips without it.
"""

from __future__ import annotations

import json

import pytest

from app import crow
from tests.crow_example import reference as example_file

REFERENCE = example_file("crow_validation_staged_construction.json")

ONLY_OURS = {
    "solver": {
        # The supports' sub-model parts, listed for the solver as well as named by their
        # processes; harmless, and what the GiD-authored decks Kratos ships also do.
        "processes_sub_model_part_list",
    },
    "output": {
        "gid_output.Parameters.postprocess_parameters.point_data_configuration",
        "gid_output.Parameters.postprocess_parameters.result_file_configuration.plane_output",
    },
}

ONLY_THEIRS = {
    "solver": {
        # UNVERIFIED (register row K1): Kratos' defaults are used for these. The
        # quasi-static U-Pw scheme reads newmark_theta for the pressure time integration;
        # CROW's results agree with the reference regardless (test_live_crow.py).
        "newmark_beta", "newmark_gamma", "newmark_theta",
        "time_stepping.max_delta_time_factor",
    },
    "output": {
        # UNVERIFIED (register row K2): with no interval GiD writes at every step, so a
        # stage cut into sub-steps writes several result blocks -- why app.gid_results
        # takes the last step (finding F6).
        "gid_output.Parameters.postprocess_parameters.result_file_configuration.output_interval",
    },
    "process apply_vector_constraint_table_process": {
        # The reference fixes several parts with one process; we write one per part.
        "model_part_name_list",
    },
}


def _keys(node, prefix=""):
    out = set()
    if isinstance(node, dict):
        for key, value in node.items():
            out.add(prefix + key)
            if not (isinstance(value, list) and value and not isinstance(value[0], dict)):
                out |= _keys(value, prefix + key + ".")
    elif isinstance(node, list):
        for value in node:
            out |= _keys(value, prefix)
    return out


def key_sets(document: dict) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {"stage": set(), "solver": set(), "output": set()}
    for stage in document["stages"].values():
        settings = stage["stage_settings"]
        out["stage"] |= set(settings)
        out["solver"] |= _keys(settings["solver_settings"])
        out["output"] |= _keys(settings.get("output_processes", {}))
        for processes in settings["processes"].values():
            for process in processes:
                out.setdefault(f"process {process['python_module']}", set()).update(
                    _keys(process["Parameters"]))
    return out


@pytest.fixture(scope="module")
def sets():
    if not REFERENCE.exists():
        pytest.skip(f"{REFERENCE.name} is not present; the reference decks are kept out "
                    "of the repository")
    ours = key_sets(json.loads(crow.export(crow.crow_project(staged=True))["project_parameters"]))
    theirs = key_sets(json.loads(REFERENCE.read_text(encoding="utf-8")))
    return ours, theirs


def test_the_keys_only_our_deck_has_are_the_recorded_ones(sets):
    ours, theirs = sets
    found = {group: ours.get(group, set()) - theirs.get(group, set())
             for group in set(ours) | set(theirs)}
    assert {g: k for g, k in found.items() if k} == ONLY_OURS


def test_the_keys_only_the_reference_has_are_the_recorded_ones(sets):
    ours, theirs = sets
    found = {group: theirs.get(group, set()) - ours.get(group, set())
             for group in set(ours) | set(theirs)}
    assert {g: k for g, k in found.items() if k} == ONLY_THEIRS
