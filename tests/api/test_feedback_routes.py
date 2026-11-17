"""The Feedback routes (backend/routes/feedback.py), and what the server keeps for them: its
log and the last requests (backend/server_log.py), with the errors no route answers
(backend/main.py).

The report itself -- its name and its files -- is tests/test_feedback.py's. Here: what the
page sends and what the server adds, what is refused, who may open the folder, and that an
error the server did not expect comes back as a sentence and lands in its log.
"""

from __future__ import annotations

import base64
import zipfile

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from backend import server_log
from backend.main import app
from backend.routes import feedback as feedback_routes
from core import feedback

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nrest").decode()
JPEG = base64.b64encode(b"\xff\xd8\xffrest").decode()


@pytest.fixture
def reports(tmp_path, monkeypatch):
    folder = tmp_path / "feedback"
    monkeypatch.setenv(feedback.FOLDER_ENV, str(folder))
    return folder


@pytest.fixture
def opened(monkeypatch):
    """The folders the file browser was asked to show, with none really opened."""
    shown = []
    monkeypatch.setattr(feedback_routes, "open_in_file_browser", shown.append)
    return shown


@pytest.fixture
def client():
    server_log.clear()
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000),
                    raise_server_exceptions=False) as c:
        c.post("/api/project/reset")
        yield c
        c.post("/api/project/reset")


def files_of(said: dict) -> dict[str, bytes]:
    """The files of the report the answer `said` is about, by their names in its folder."""
    prefix = said["report"] + "/"
    with zipfile.ZipFile(said["path"]) as archive:
        return {name[len(prefix):]: archive.read(name) for name in archive.namelist()
                if name.startswith(prefix)}


def test_a_report_holds_what_the_page_sent_and_what_the_server_knows(client, reports):
    answer = client.post("/api/feedback", json={
        "kind": "bug", "message": "The mesh did not show.", "name": "Ben",
        "context": {"mode": "Mesh"}, "session_log": "> mesh",
        "model_history": "> water -1", "view": "data:image/png;base64," + PNG,
        "attachments": [{"name": "shot.jpg", "data": "data:image/jpeg;base64," + JPEG},
                        {"name": "notes.docx", "data": base64.b64encode(b"PK doc").decode()},
                        {"name": "notes.docx", "data": base64.b64encode(b"again").decode()}]})

    assert answer.status_code == 200, answer.text
    said = answer.json()
    files = files_of(said)
    assert said["folder"] == str(reports)
    assert said["name"].endswith("-ben.zip")
    assert said["reports"] == 1
    assert said["files"] == [said["report"] + "/" + name for name in files]
    assert files["view.png"].startswith(b"\x89PNG")
    assert files["attachments/shot.jpg"].startswith(b"\xff\xd8")
    assert files["attachments/notes.docx"] == b"PK doc"
    assert files["attachments/notes-2.docx"] == b"again", "the same name twice keeps both"
    assert files["session-log.txt"] == b"> mesh"
    assert files["model-history.txt"] == b"> water -1"
    assert b'"name"' in files["project.json"], "the project the server holds"
    assert b"POST /api/project/reset -> 200" in files["server-log.txt"]
    assert b"Sent by:  GUI" in files["report.txt"]


def test_the_model_can_be_left_out(client, reports):
    said = client.post("/api/feedback", json={"kind": "good", "message": "nice",
                                              "include_project": False}).json()

    assert said["report"] + "/project.json" not in said["files"]


def test_the_next_report_goes_in_the_same_file(client, reports):
    first = client.post("/api/feedback", json={"kind": "bug", "message": "a", "name": "Ben"}).json()
    second = client.post("/api/feedback", json={"kind": "good", "message": "b",
                                                "name": "Ben"}).json()

    assert second["path"] == first["path"]
    assert second["reports"] == 2
    assert second["report"] != first["report"]


@pytest.mark.parametrize("body, said", [
    ({"kind": "praise", "message": "x"}, "not a kind of feedback"),
    ({"kind": "bug", "message": " "}, "Write what happened"),
    ({"kind": "bug", "message": "x", "view": "not base64!"}, "picture of the view is not base64"),
    ({"kind": "bug", "message": "x", "view": JPEG}, "view is not a PNG"),
    ({"kind": "bug", "message": "x", "attachments": [{"name": "a", "data": "not base64!"}]},
     "file a is not base64"),
])
def test_a_report_that_cannot_be_saved_says_why(client, reports, body, said):
    answer = client.post("/api/feedback", json=body)

    assert answer.status_code == 422
    assert said in answer.json()["detail"]
    assert not reports.exists() or not list(reports.iterdir())


def test_the_folder_opens_for_a_browser_on_this_computer(client, reports, opened):
    said = client.post("/api/feedback/folder").json()

    assert said == {"opened": True, "folder": str(reports)}
    assert opened == [reports]
    assert reports.is_dir()


def test_the_folder_does_not_open_for_a_browser_elsewhere(reports, opened):
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("192.168.1.20", 50000)) as c:
        said = c.post("/api/feedback/folder").json()

    assert said["opened"] is False
    assert said["folder"] == str(reports)
    assert opened == []


# ── Errors, kept for a report ───────────────────────────────────────────────

broken = APIRouter()


@broken.get("/api/test-only/broken")
def broken_route():
    return {}["missing"]


@pytest.fixture
def with_a_broken_route():
    app.include_router(broken)
    yield
    app.router.routes[:] = [route for route in app.router.routes
                            if getattr(route, "path", "") != "/api/test-only/broken"
                            and getattr(route, "original_router", None) is not broken]


def test_an_error_no_route_expected_is_a_sentence_and_lands_in_the_log(
        client, with_a_broken_route):
    answer = client.get("/api/test-only/broken")

    assert answer.status_code == 500
    detail = answer.json()["detail"]
    assert "did not expect (KeyError: 'missing')" in detail
    assert "save a report" in detail
    log = server_log.text()
    assert "GET /api/test-only/broken stopped on an error" in log
    assert "Traceback" in log
    assert "GET /api/test-only/broken -> 500" in log


def test_a_failure_a_route_reports_lands_in_the_log(client, monkeypatch):
    from backend.routes import decks
    from core.analysis import calculation

    async def export(*_args):
        return {"stats": {}, "warnings": []}

    def refuse(_export):
        raise calculation.CalculationError("Kratos could not be started.")

    monkeypatch.setattr(decks, "run_mesh_job", export)
    monkeypatch.setattr(calculation, "run", refuse)

    answer = client.post("/api/calculate", json={"element_size": 6.0, "order": 1})

    assert answer.json() == {"detail": "Kratos could not be started."}
    assert "POST /api/calculate -> 500: Kratos could not be started." in server_log.text()


def test_the_page_files_are_not_kept_as_requests(client):
    client.get("/")

    assert "GET / " not in server_log.text()
