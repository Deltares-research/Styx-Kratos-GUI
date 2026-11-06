"""The folder a save of many files goes in, and the files written into it (backend/routes/files.py).

The browser's own folder window refuses Downloads, Desktop and Documents, so the server opens
the system's. That makes these the routes that write outside the runs folder: what they may
write, and for whom, is most of what is tested here.
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routes import files


@pytest.fixture
def client():
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000)) as c:
        yield c


@pytest.fixture
def chosen(monkeypatch, tmp_path):
    """The window answers with `tmp_path`, and records where it opened."""
    starts = []

    def choose(start):
        starts.append(start)
        return str(tmp_path)

    monkeypatch.setattr(files, "choose_folder", choose)
    monkeypatch.setattr(files, "_folders", {})
    return tmp_path, starts


def folder_id(client) -> str:
    return client.post("/api/files/folder").json()["id"]


def test_the_window_gives_a_folder_and_a_file_lands_in_it(client, chosen):
    folder, _ = chosen

    answer = client.post("/api/files/folder").json()
    written = client.put(f"/api/files/folder/{answer['id']}/stage1.png", content=b"\x89PNG")

    assert answer["name"] == str(folder)
    assert written.status_code == 200
    assert (folder / "stage1.png").read_bytes() == b"\x89PNG"


def test_the_window_can_be_dismissed(client, monkeypatch):
    monkeypatch.setattr(files, "choose_folder", lambda _start: "")

    assert client.post("/api/files/folder").json() == {"cancelled": True}


def test_the_window_opens_in_downloads_and_then_where_the_last_one_ended(client, chosen):
    folder, starts = chosen

    client.post("/api/files/folder")
    client.post("/api/files/folder")

    assert starts[0].name == "Downloads"
    assert starts[1] == folder


def test_a_computer_with_no_window_says_so_for_the_browser_to_take_over(client, monkeypatch):
    def no_window(_start):
        raise files.NoFolderWindow("no display")

    monkeypatch.setattr(files, "choose_folder", no_window)

    assert client.post("/api/files/folder").json() == {"no_window": "no display"}


def test_it_says_whether_a_file_is_there(client, chosen):
    folder, _ = chosen
    (folder / "there.png").write_bytes(b"x")
    made = folder_id(client)

    assert client.get(f"/api/files/folder/{made}/there.png").json() == {"exists": True}
    assert client.get(f"/api/files/folder/{made}/gone.png").json() == {"exists": False}


@pytest.mark.parametrize("name", ["run.bat", "a.py", "a.png.exe", "no_type", ".png", "..png",
                                  "a b.png", "a:b.png", "..%5Cup.png", "..%2Fup.png"])
def test_only_a_picture_or_a_csv_with_a_plain_name_can_be_written(client, chosen, name):
    folder, _ = chosen

    answer = client.put(f"/api/files/folder/{folder_id(client)}/{name}", content=b"x")

    assert answer.status_code in (404, 405, 422)
    assert list(folder.iterdir()) == []


@pytest.mark.parametrize("name", ["a.png", "A-b_c.1.PDF", "a.svg", "a.csv"])
def test_each_kind_of_file_a_save_makes_can_be_written(client, chosen, name):
    folder, _ = chosen

    assert client.put(f"/api/files/folder/{folder_id(client)}/{name}", content=b"x").status_code == 200
    assert (folder / name).exists()


def test_a_folder_nobody_chose_is_not_written_to(client, chosen):
    answer = client.put("/api/files/folder/invented/a.png", content=b"x")

    assert answer.status_code == 404


def test_a_folder_that_cannot_be_written_to_gives_the_reason(client, chosen, monkeypatch):
    def refuse(_self, _content):
        raise PermissionError("denied")

    monkeypatch.setattr("pathlib.Path.write_bytes", refuse)

    answer = client.put(f"/api/files/folder/{folder_id(client)}/a.png", content=b"x")

    assert answer.status_code == 500
    assert "denied" in answer.json()["detail"]


def test_another_site_cannot_open_the_window(client, chosen):
    _, starts = chosen

    answer = client.post("/api/files/folder", headers={"Origin": "https://evil.example"})

    assert answer.status_code == 403
    assert starts == []


def test_a_browser_on_another_computer_gets_no_window_and_no_file(chosen):
    folder, starts = chosen
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 1)) as here:
        made = folder_id(here)
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("192.168.1.5", 1)) as there:
        assert "no_window" in there.post("/api/files/folder").json()
        assert there.put(f"/api/files/folder/{made}/a.png", content=b"x").status_code == 403
    assert len(starts) == 1
    assert list(folder.iterdir()) == []


def test_a_server_reached_by_another_name_gets_no_window(chosen, monkeypatch):
    """Behind a proxy on the same computer the client is loopback, but the browser is not."""
    _, starts = chosen
    monkeypatch.setenv("KRATOS_GUI_ALLOWED_HOSTS", "modelling-pc")
    with TestClient(app, base_url="http://modelling-pc:8000", client=("127.0.0.1", 1)) as proxied:
        assert "no_window" in proxied.post("/api/files/folder").json()
    assert starts == []


# ── The job of `kratos-cli picture` ──────────────────────────────────────────

def test_a_server_started_for_a_picture_job_knows_its_token(client, monkeypatch):
    monkeypatch.setenv(files.PICTURE_JOB_ENV, "the-token")

    assert client.get("/api/files/picture-job/the-token").json() == {"ok": True}
    assert client.get("/api/files/picture-job/another").json() == {"ok": False}


def test_the_guis_own_server_runs_no_picture_job(client, monkeypatch):
    monkeypatch.delenv(files.PICTURE_JOB_ENV, raising=False)

    assert client.get("/api/files/picture-job/anything").json() == {"ok": False}


def test_the_cli_and_the_server_name_the_token_alike():
    from cli.terminal import pictures

    assert pictures.JOB_ENV == files.PICTURE_JOB_ENV


# ── The window itself ────────────────────────────────────────────────────────

def test_the_window_runs_apart_and_says_what_was_chosen(monkeypatch, tmp_path):
    asked = {}

    def run(command, **options):
        asked.update(command=command, options=options)
        return subprocess.CompletedProcess(command, 0, stdout="D:\\Mijn plots\n", stderr="")

    monkeypatch.setattr(subprocess, "run", run)

    assert files.choose_folder(tmp_path) == "D:\\Mijn plots"
    assert asked["command"][0] == sys.executable
    assert asked["command"][-1] == str(tmp_path)
    assert asked["options"]["encoding"] == "utf-8"


def test_a_window_that_could_not_open_says_why(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda command, **_options: subprocess.CompletedProcess(
        command, 1, stdout="", stderr="TclError: no display name\n"))

    with pytest.raises(files.NoFolderWindow, match="no display name"):
        files.choose_folder(tmp_path)


def test_a_python_that_cannot_start_counts_as_no_window(monkeypatch, tmp_path):
    def run(_command, **_options):
        raise OSError("not found")

    monkeypatch.setattr(subprocess, "run", run)

    with pytest.raises(files.NoFolderWindow, match="not found"):
        files.choose_folder(tmp_path)
