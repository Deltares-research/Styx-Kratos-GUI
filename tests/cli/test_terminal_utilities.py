"""Focused tests for the terminal's shared file, word and CSV helpers."""

from __future__ import annotations

import argparse
import os

import pytest

from cli.terminal import files, tables, words
from cli.terminal.output import CommandError
from core.analysis import calculation
from core.model.templates import blank_project


def test_an_edit_of_a_model_script_requires_an_output_or_a_dry_run(tmp_path):
    script = tmp_path / "model.py"
    args = argparse.Namespace(project=script, out=None, dry_run=False)

    with pytest.raises(CommandError, match="read but never written"):
        files.written(args, blank_project())

    args.dry_run = True
    assert files.written(args, blank_project()) == (None, "not written (--dry-run)")
    assert not script.exists()


def test_a_run_setting_applies_only_inside_its_context(tmp_path, monkeypatch):
    monkeypatch.setenv(calculation.RUNS_ENV, "before")
    monkeypatch.delenv(calculation.TIMEOUT_ENV, raising=False)
    args = argparse.Namespace(runs_dir=tmp_path / "runs", timeout=12)

    with files.environment(args):
        assert calculation.runs_root() == (tmp_path / "runs").resolve()
        assert os.environ[calculation.TIMEOUT_ENV] == "12"

    assert os.environ[calculation.RUNS_ENV] == "before"
    assert calculation.TIMEOUT_ENV not in os.environ


def test_values_and_coordinates_can_be_read_from_files(tmp_path):
    value_file = tmp_path / "value.json"
    value_file.write_text('{"active": false}', encoding="utf-8")
    points_file = tmp_path / "points.csv"
    points_file.write_text("x,y\n0; 1\n2, 3\n# ignored\n", encoding="utf-8")

    assert words.parsed([f"@{value_file}"]) == {"active": False}
    assert words.coordinates([f"@{points_file}"], 2) == [(0.0, 1.0), (2.0, 3.0)]


def test_plain_assignment_values_remain_text_and_empty_coordinates_are_refused():
    assert words.parsed(["FULLY_COUPLED"]) == "FULLY_COUPLED"
    with pytest.raises(CommandError, match="give the points with --line"):
        words.coordinates(None, 2, "--line")


@pytest.mark.parametrize("text, message", [
    ("@absent.json", "no such file"),
    ("@broken.json", "not valid JSON"),
])
def test_a_file_value_reports_missing_or_invalid_json(tmp_path, text, message):
    if text == "@broken.json":
        (tmp_path / "broken.json").write_text("{", encoding="utf-8")

    with pytest.raises(CommandError, match=message):
        words.parsed([f"@{tmp_path / text[1:]}"])


def test_coordinate_files_report_a_malformed_point_and_assignments_need_names(tmp_path):
    points = tmp_path / "bad.csv"
    points.write_text("x,y\n0,1\n2,3,4\n", encoding="utf-8")

    with pytest.raises(CommandError, match="is not a point of 2 numbers"):
        words.coordinates([f"@{points}"], 2)
    with pytest.raises(CommandError, match="NAME=VALUE"):
        words.assignments(["=1"])


def test_csv_distinguishes_element_values_and_empty_results():
    assert tables.field_csv({
        "location": "elements", "field": None, "unit": "Pa",
        "ids": [8, 9], "values": [1.5, None],
    }, "run", "stage") == (
        "element,value [Pa],# run / stage\n8,1.5\n9,\n")


def test_profile_csv_quotes_stage_names_that_contain_commas():
    plot = {
        "quantity": "M", "unit": "N·m",
        "stages": [{"index": 2, "stage": "Stage, two", "nodes": [7],
                    "points": [(4.5, -1.0)]}],
    }

    assert tables.profile_csv(plot) == (
        "stage,name,node,y [m],M [N·m]\n2,\"Stage, two\",7,-1,4.5\n")
