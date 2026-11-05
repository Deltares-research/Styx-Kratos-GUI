"""A project file goes from one front end to the other and back unchanged.

The GUI opens a file by sending it to `PUT /api/project`, and saves what
`GET /api/project` answers, as `JSON.stringify(project, null, 2)`
(`frontend/js/patches.js` `openProject`, `saveProject`). The command line reads and
writes the same file through `core.session`. A field one side drops or rewrites is lost
on the way; these follow a file both ways. `tests/e2e/test_handover_flows.py` does the
same through the real page.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from core import session
from tests.models.excavation import excavation_project

MADE = {
    "a new demo project": lambda cli, path: cli("new", path, "--demo", "--dim", "2",
                                                "--name", "Pit A"),
    "a staged excavation": lambda cli, path: session.save(excavation_project(), path),
}
"""Projects as the command line writes them."""


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
        c.post("/api/project/reset")


@pytest.mark.parametrize("made", sorted(MADE))
def test_the_gui_opens_and_saves_a_command_line_file_unchanged(made, cli, client, tmp_path):
    path = tmp_path / "model.json"
    MADE[made](cli, path)
    written = json.loads(path.read_text(encoding="utf-8"))

    assert client.put("/api/project", json=written).status_code == 200
    saved = client.get("/api/project").json()

    assert saved == written


def test_a_project_the_gui_saves_is_checked_exported_and_scripted_on_the_command_line(
        cli, client, tmp_path):
    client.put("/api/project", json=excavation_project().model_dump(mode="json"))
    path = tmp_path / "saved.json"
    path.write_text(json.dumps(client.get("/api/project").json(), indent=2),
                    encoding="utf-8")

    assert cli("check", path).code == 0
    exported = cli("export", path, "--out", tmp_path / "deck")
    assert exported.code == 0, exported.err
    scripted = cli("script", path, "--out", tmp_path / "model.py")
    assert scripted.code == 0, scripted.err
