"""`kratos-cli script P --out model.py`: the model written as one Python file
(plan/active/cli-plan.md, MS), and that file used every way a model script is used.

* it reads back as the project it was written from, here and in the GUI
  (`POST /api/project/script`, which is `run model.py` in the command box);
* `python model.py --out deck/` writes the deck `kratos-cli export` writes, byte for
  byte, because it is `kratos-cli export`;
* a model built in the terminal comes back whole.

`script <file.py>` in the GUI's command box writes it too (`POST /api/project/script/save`).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import store
from backend.main import app
from core import scripting, session

ROOT = Path(__file__).resolve().parents[2]
MODEL_SCRIPT = ROOT / "tests" / "models" / "excavation.py"


def test_script_writes_the_model_as_a_file_that_builds_it_again(cli, site, tmp_path):
    out = tmp_path / "model.py"

    ran = cli("script", site, "--out", out)

    assert ran.code == 0, ran.err
    assert f"wrote {out}" in ran.out and f"run {out.name}" in ran.out
    assert scripting.load_project(out) == session.load(site)
    assert ran.code == cli("--json", "script", site, "--out", out, "--force").code


def test_script_names_the_file_it_came_from_and_its_own_name(cli, site, tmp_path):
    out = tmp_path / "pit.py"
    cli("script", site, "--out", out)

    text = out.read_text(encoding="utf-8")
    assert "kratos-cli from site.json" in text
    assert "python pit.py --out deck/" in text


def test_script_does_not_replace_a_file_without_force(cli, site, tmp_path):
    out = tmp_path / "model.py"
    out.write_text("# mine\n", encoding="utf-8")

    ran = cli("script", site, "--out", out)

    assert ran.code == 1 and "--force" in ran.err
    assert out.read_text(encoding="utf-8") == "# mine\n"


def test_script_writes_only_a_python_file(cli, site, tmp_path):
    ran = cli("script", site, "--out", tmp_path / "model.txt")

    assert ran.code == 1 and ".py" in ran.err


def test_script_reads_a_script_too(cli, tmp_path):
    out = tmp_path / "again.py"

    assert cli("script", MODEL_SCRIPT, "--out", out).code == 0
    assert scripting.load_project(out) == session.load(MODEL_SCRIPT)


def test_a_model_built_in_the_terminal_comes_back_whole(cli, tmp_path):
    path, out = tmp_path / "pit.json", tmp_path / "pit.py"
    for argv in (
        ("new", path, "--name", "Pit C"),
        ("domain", path, "--x", "0", "40", "--y", "-30", "0", "--z", "0", "10"),
        ("material", path, "add", "clay", "--preset", "m3", "K0_NC=0.6"),
        ("material", path, "add", "sand", "--preset", "m5"),
        ("layer", path, "add", "top", "--material", "clay", "--bottom", "-6"),
        ("layer", path, "add", "bottom", "--material", "sand", "--bottom", "-30"),
        ("excavation", path, "--x", "0", "5", "--z", "0", "10", "--levels", "-2", "-4"),
        ("water", path, "-1"),
        ("beam", path, "add", "sheet", "--points", "5", "0", "5", "-10"),
        ("anchor", path, "add", "strut", "--head", "5", "-1", "--tail", "4", "-1"),
        ("interface", path, "add", "contact", "--structure", "sheet"),
        ("load", path, "add", "line", "surcharge", "--x", "5", "40", "--components", "0",
         "-10000"),
        ("normal-load", path, "add", "water_1", "--hydrostatic", "--points", "5", "-1", "5",
         "-2", "0", "-2"),
        ("set", path, "mesh.body_sizes.sheet", "0.5"),
        ("phases", path, "staged-excavation"),
    ):
        ran = cli(*argv)
        assert ran.code == 0, (argv, ran.err)

    assert cli("script", path, "--out", out).code == 0
    assert scripting.load_project(out) == session.load(path)


# ── The file, run as `python model.py` ──────────────────────────────────────

def python(*argv, cwd: Path) -> subprocess.CompletedProcess:
    """The file run by the environment's own Python, from a folder of the user's."""
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    return subprocess.run([sys.executable, *map(str, argv)], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", env=environment, timeout=600)


def test_the_file_writes_the_deck_kratos_cli_export_writes(cli, tmp_path):
    site, model = tmp_path / "pit.json", tmp_path / "pit.py"
    assert cli("build", MODEL_SCRIPT, "--out", site).code == 0
    assert cli("script", site, "--out", model).code == 0
    assert cli("export", site, "--out", tmp_path / "exported").code == 0

    ran = python(model, "--out", "deck", cwd=tmp_path)

    assert ran.returncode == 0, ran.stderr
    written, exported = tmp_path / "deck", tmp_path / "exported"
    names = sorted(path.name for path in exported.iterdir())
    assert sorted(path.name for path in written.iterdir()) == names
    for name in names:
        assert (written / name).read_bytes() == (exported / name).read_bytes(), name


def test_the_file_asks_what_to_do_when_told_nothing(cli, site, tmp_path):
    model = tmp_path / "model.py"
    cli("script", site, "--out", model)

    ran = python(model, cwd=tmp_path)

    assert ran.returncode == 2 and "--out DIR" in ran.stderr


# ── In the GUI ──────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    saved = store.get()
    with TestClient(app) as test_client:
        yield test_client
    store.put(saved)


def test_the_gui_opens_the_file(cli, site, tmp_path, client):
    model = tmp_path / "model.py"
    cli("script", site, "--out", model)

    answer = client.post("/api/project/script", json={"path": str(model)})

    assert answer.status_code == 200, answer.text
    assert store.get() == session.load(site)


def test_the_gui_writes_the_open_model_as_a_script(client, site, tmp_path):
    store.put(session.load(site))
    model = tmp_path / "model.py"

    answer = client.post("/api/project/script/save", json={"path": str(model)})

    assert answer.status_code == 200, answer.text
    assert answer.json()["path"] == str(model)
    assert scripting.load_project(model) == session.load(site)


def test_the_gui_does_not_replace_a_file_unless_told_to(client, site, tmp_path):
    store.put(session.load(site))
    model = tmp_path / "model.py"
    model.write_text("# mine\n", encoding="utf-8")

    refused = client.post("/api/project/script/save", json={"path": str(model)})
    assert refused.status_code == 422 and "--force" in refused.json()["detail"]
    assert model.read_text(encoding="utf-8") == "# mine\n"

    forced = client.post("/api/project/script/save", json={"path": str(model), "force": True})
    assert forced.status_code == 200
    assert scripting.load_project(model) == session.load(site)


def test_the_gui_needs_a_path(client):
    answer = client.post("/api/project/script/save", json={})

    assert answer.status_code == 422 and "script" in answer.json()["detail"]
