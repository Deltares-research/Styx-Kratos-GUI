"""`get`, `set`, `add`, `remove`: any field of the project, by path (`core.session`).

A value is read as JSON when it is JSON -- `1.5`, `true`, `null`, `{"y": -2}` -- and as
text otherwise, so `set site.json name Pit A` needs no quoting. `@file.json` reads the
value from a file, which is how a whole record is given.
"""

from __future__ import annotations

import json

from core import session


def test_get_prints_a_value_as_json(cli, site):
    ran = cli("get", site, "layers[L1].tops")

    assert ran.code == 0
    assert json.loads(ran.out) == session.value_at(session.load(site), "layers[L1].tops")


def test_get_without_a_path_prints_the_whole_project(cli, site):
    assert json.loads(cli("get", site).out) == session.load(site).model_dump(mode="json")


def test_set_writes_a_number(cli, site):
    assert cli("set", site, "mesh.element_size", "1.5").code == 0

    assert session.load(site).mesh.element_size == 1.5


def test_set_takes_text_that_is_not_json_as_text(cli, site):
    assert cli("set", site, "name", "Pit A").code == 0

    assert session.load(site).name == "Pit A"


def test_add_takes_a_record_from_a_file_and_remove_takes_it_away(cli, site, tmp_path):
    clay = session.load(site).materials[0].model_dump(mode="json") | {"id": "clay2",
                                                                      "name": "Clay 2"}
    record = tmp_path / "clay2.json"
    record.write_text(json.dumps(clay), encoding="utf-8")

    assert cli("add", site, "materials", f"@{record}").code == 0
    assert session.load(site).materials[-1].id == "clay2"

    assert cli("remove", site, "materials[clay2]").code == 0
    assert "clay2" not in [m.id for m in session.load(site).materials]


def test_a_path_that_names_nothing_says_what_is_there(cli, site):
    ran = cli("get", site, "layers[nope]")

    assert ran.code == 1
    assert "L1, L2" in ran.err


def test_a_field_with_a_command_of_its_own_points_at_it(cli, site):
    ran = cli("set", site, "dimension", "3")

    assert ran.code == 1
    assert "`dimension` command" in ran.err
    assert session.load(site).dimension == 2


def test_a_value_file_that_is_not_there_is_refused(cli, site, tmp_path):
    ran = cli("add", site, "materials", f"@{tmp_path / 'nope.json'}")

    assert ran.code == 1
    assert "nope.json" in ran.err
