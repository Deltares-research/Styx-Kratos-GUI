"""`picture`: the job a command gives the stand, and what it does with the files.

The stand is stood in for by a thread that posts what the real one would, to the real
receiver. No server and no browser, so this runs anywhere; tests/e2e/test_pictures.py runs
the whole thing for real.
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

import pytest

from cli.terminal import pictures
from cli.terminal.main import main
from cli.terminal.output import CommandError
from core import session
from tests import results_run
from tests.models.excavation import excavation_project


class FakePage:
    """What `open_page` returns, standing in for a browser that has stopped."""

    pid = 0
    returncode = 0

    def __init__(self, running=True):
        self.running = running

    def poll(self):
        return None if self.running else 0

    def wait(self, *_):
        return 0


@pytest.fixture
def stand(monkeypatch):
    """A stand-in page. `stand.files` is what it posts; `stand.job` is what it was asked."""

    class Stand:
        files = {"Pit_stage1.png": b"PNG"}
        error = None
        job = None
        projects: list[str] = []
        count = None
        server_token = None

    def open_page(_browser, url, _profile):
        job = json.loads(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["picture"][0])
        Stand.job = job

        def post():
            def send(path, body):
                urllib.request.urlopen(urllib.request.Request(job["receiver"] + path, data=body,
                                                              method="POST"))
            for name, content in Stand.files.items():
                send("/file?" + urllib.parse.urlencode({"name": name}), content)
            answer = ({"ok": False, "error": Stand.error} if Stand.error
                      else {"ok": True, "count": len(Stand.files) if Stand.count is None
                            else Stand.count})
            send("/done", json.dumps(answer).encode())

        threading.Thread(target=post, daemon=True).start()
        return FakePage()

    monkeypatch.setattr(pictures, "find_browser", lambda: "a browser")
    def start_server(token):
        Stand.server_token = token
        return FakePage(), "http://server"

    monkeypatch.setattr(pictures, "start_server", start_server)
    monkeypatch.setattr(pictures, "stop", lambda _process: None)
    monkeypatch.setattr(pictures, "put_project",
                        lambda _url, text: Stand.projects.append(text))
    monkeypatch.setattr(pictures, "open_page", open_page)
    Stand.projects = []
    return Stand


@pytest.fixture
def project(tmp_path):
    path = tmp_path / "pit.json"
    session.save(excavation_project(), path)
    return path


@pytest.fixture
def run(monkeypatch):
    return results_run.use(monkeypatch, results_run.fake_run())


# ── The job ─────────────────────────────────────────────────────────────────

def test_geometry_is_what_the_structures_tab_shows(stand, project, tmp_path, capsys):
    code = main(["picture", "geometry", str(project), "--out", str(tmp_path) + "/"])
    assert code == 0
    assert stand.job["mode"] == "structures"
    assert stand.job["asked"]["formats"] == ["png"]
    assert stand.job["asked"]["width"] == 16.0
    assert json.loads(stand.projects[0])["name"] == excavation_project().name
    assert (tmp_path / "Pit_stage1.png").read_bytes() == b"PNG"
    assert "wrote" in capsys.readouterr().out


def test_the_job_carries_the_token_only_its_server_knows(stand, project, tmp_path):
    assert main(["picture", "geometry", str(project), "--out", str(tmp_path) + "/"]) == 0
    assert len(stand.job["token"]) > 16
    assert stand.job["token"] == stand.server_token
    assert stand.job["receiver"].startswith("http://127.0.0.1:")


def test_mesh_asks_for_the_mesh_tab(stand, project, tmp_path):
    assert main(["picture", "mesh", str(project), "--out", str(tmp_path) + "/"]) == 0
    assert stand.job["mode"] == "mesh"


def test_the_options_are_the_words_of_the_window(stand, project, tmp_path):
    assert main(["picture", "geometry", str(project), "--out", str(tmp_path) + "/",
                 "--format", "PNG, svg,png", "--width", "12.5", "--no-rulers", "--no-axes",
                 "--grid", "--view", "top"]) == 0
    asked = stand.job["asked"]
    assert asked["formats"] == ["png", "svg"], "as given, once each"
    assert asked["width"] == 12.5
    assert asked["show"] == {"rulers": False, "axes": False, "grid": True}
    assert stand.job["view"] == "top"


@pytest.mark.parametrize("option", (["--format", "tiff"], ["--width", "0"], ["--width", "lots"],
                                    ["--width", "500"], ["--view", "under"]))
def test_a_bad_option_is_refused_before_anything_starts(stand, project, option, capsys):
    assert main(["picture", "geometry", str(project), *option]) != 0
    assert stand.job is None


def test_every_stage_is_the_default(stand, project, tmp_path):
    assert main(["picture", "stage", str(project), "--out", str(tmp_path) + "/"]) == 0
    assert stand.job["mode"] == "staged"
    assert stand.job["stage"] is None
    assert stand.job["asked"]["stage"] == "all"


def test_one_pdf_is_asked_of_the_page(stand, project, tmp_path):
    assert main(["picture", "stage", str(project), "--format", "pdf", "--one-pdf",
                 "--out", str(tmp_path) + "/"]) == 0
    assert stand.job["asked"]["onePdf"] is True
    assert stand.job["asked"]["stage"] == "all"


def test_one_pdf_goes_to_a_file_with_the_name_asked_for(stand, project, tmp_path):
    stand.files = {"Pit_stages.pdf": b"%PDF-"}
    out = tmp_path / "report.pdf"
    assert main(["picture", "stage", str(project), "--format", "pdf", "--one-pdf",
                 "--out", str(out)]) == 0
    assert out.read_bytes() == b"%PDF-"


def test_one_pdf_needs_a_pdf(stand, project, capsys):
    assert main(["picture", "stage", str(project), "--one-pdf"]) != 0
    assert stand.job is None
    assert "--one-pdf needs pdf" in capsys.readouterr().err


def test_a_pdf_for_each_picture_is_the_default(stand, project, tmp_path):
    assert main(["picture", "stage", str(project), "--format", "pdf",
                 "--out", str(tmp_path) + "/"]) == 0
    assert "onePdf" not in stand.job["asked"]


@pytest.mark.parametrize("wanted", ("2", "SECOND"))
def test_a_stage_by_its_number_or_words_of_its_name(stand, tmp_path, wanted):
    model = excavation_project()
    model.stages[1].name = "The second one"
    path = tmp_path / "pit.json"
    session.save(model, path)
    assert main(["picture", "stage", str(path), "--stage", wanted, "--out", str(tmp_path) + "/"]) == 0
    assert stand.job["stage"] == 2
    assert stand.job["asked"]["stage"] is None


@pytest.mark.parametrize("wanted", ("99", "no such stage"))
def test_a_stage_that_is_not_there_lists_those_that_are(stand, project, wanted, capsys):
    assert main(["picture", "stage", str(project), "--stage", wanted]) != 0
    error = capsys.readouterr().err
    assert "No stage matches" in error
    assert excavation_project().stages[0].name in error
    assert stand.job is None


# ── Results ─────────────────────────────────────────────────────────────────

def test_a_result_opens_the_run_in_the_words_of_the_box(stand, run, tmp_path):
    assert main(["picture", "result", run, "--out", str(tmp_path) + "/"]) == 0
    assert stand.job["mode"] == "results"
    assert stand.job["commands"][0] == f"results open {run}"
    assert stand.job["commands"][1].startswith("results stage ")
    assert stand.projects == [], "a run needs no model"


def test_display_options_are_the_box_commands(stand, run, tmp_path):
    assert main(["picture", "result", run, "uy", "--stage", "2", "--map", "viridis",
                 "--bands", "12", "--range", "-1", "1", "--deform", "auto", "--mesh",
                 "--no-legend", "--csv", "--out", str(tmp_path) + "/"]) == 0
    assert stand.job["commands"] == [f"results open {run}", "results stage 2", "results field uy",
                                    "results map viridis", "results bands 12",
                                    "results range -1.0 1.0", "results deform auto",
                                    "results mesh on"]
    assert stand.job["asked"]["show"]["legend"] is False
    assert stand.job["asked"]["csv"] is True


def test_every_field_of_every_stage(stand, run, tmp_path):
    assert main(["picture", "result", run, "all", "--stage", "all",
                 "--out", str(tmp_path) + "/"]) == 0
    assert stand.job["asked"]["stage"] == "all"
    assert stand.job["asked"]["field"] == "all"
    assert stand.job["commands"] == [f"results open {run}"]


def test_the_field_can_be_given_as_the_box_gives_it(stand, run, tmp_path):
    assert main(["picture", "result", run, "--field", "all", "--stage", "all",
                 "--format", "png,pdf", "--out", str(tmp_path) + "/"]) == 0
    assert stand.job["asked"]["field"] == "all"
    assert stand.job["asked"]["formats"] == ["png", "pdf"]
    assert main(["picture", "result", run, "--field", "uy", "--stage", "2",
                 "--out", str(tmp_path) + "/", "--force"]) == 0
    assert "results field uy" in stand.job["commands"]


def test_two_different_fields_are_refused(stand, run, capsys):
    assert main(["picture", "result", run, "ux", "--field", "uy"]) != 0
    assert "Two fields" in capsys.readouterr().err
    assert stand.job is None


def test_an_unknown_field_is_refused_in_the_words_of_results(stand, run, capsys):
    assert main(["picture", "result", run, "nonsense", "--stage", "2"]) != 0
    assert "results fields" in capsys.readouterr().err
    assert stand.job is None


def test_a_result_can_draw_its_model_too(stand, run, project, tmp_path):
    assert main(["picture", "result", run, "--project", str(project),
                 "--out", str(tmp_path) + "/"]) == 0
    assert len(stand.projects) == 1


def test_a_run_folder_elsewhere_keeps_a_run_name(stand, run, tmp_path, capsys):
    root, _ = results_run.fake_run()
    named = shutil.copytree(root / run, tmp_path / "copied" / run)
    assert main(["picture", "result", str(named), "--out", str(tmp_path) + "/"]) == 0
    assert stand.job["commands"][0] == f"results open {run}"

    other = shutil.copytree(root / run, tmp_path / "from the cluster")
    stand.job = None
    assert main(["picture", "result", str(other)]) != 0
    assert "named as a run is" in capsys.readouterr().err
    assert stand.job is None


# ── The files ───────────────────────────────────────────────────────────────

def test_one_file_can_be_named(stand, project, tmp_path):
    target = tmp_path / "wall.png"
    assert main(["picture", "geometry", str(project), "--out", str(target)]) == 0
    assert target.read_bytes() == b"PNG"


def test_a_file_named_for_another_format_is_refused(stand, project, tmp_path, capsys):
    stand.files = {"Pit_stage1.pdf": b"%PDF-"}
    target = tmp_path / "wall.png"
    assert main(["picture", "geometry", str(project), "--format", "pdf", "--out", str(target)]) != 0
    assert "does not end in .pdf" in capsys.readouterr().err
    assert not target.exists()
    assert main(["picture", "geometry", str(project), "--format", "pdf",
                 "--out", str(tmp_path / "wall.PDF")]) == 0


def test_many_files_need_a_folder(stand, project, tmp_path, capsys):
    stand.files = {"a.png": b"1", "b.png": b"2"}
    assert main(["picture", "stage", str(project), "--out", str(tmp_path / "x.png")]) != 0
    assert "End --out with /" in capsys.readouterr().err


def test_a_folder_is_made_for_them(stand, project, tmp_path):
    stand.files = {"a.png": b"1", "b.pdf": b"2"}
    folder = tmp_path / "new" / "folder"
    assert main(["picture", "stage", str(project), "--out", str(folder) + "/"]) == 0
    assert sorted(path.name for path in folder.iterdir()) == ["a.png", "b.pdf"]


def test_a_file_already_there_needs_force(stand, project, tmp_path, capsys):
    stand.files = {"a.png": b"new"}
    (tmp_path / "a.png").write_bytes(b"old")
    assert main(["picture", "geometry", str(project), "--out", str(tmp_path) + "/"]) != 0
    assert "--force" in capsys.readouterr().err
    assert (tmp_path / "a.png").read_bytes() == b"old"
    assert main(["picture", "geometry", str(project), "--out", str(tmp_path) + "/", "--force"]) == 0
    assert (tmp_path / "a.png").read_bytes() == b"new"


def test_json_lists_the_files(stand, project, tmp_path, capsys):
    assert main(["--json", "picture", "geometry", str(project), "--out", str(tmp_path) + "/"]) == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer["files"][0]["bytes"] == 3


def test_a_name_from_the_page_cannot_choose_where_a_file_lands(stand, project, tmp_path):
    stand.files = {"../../evil.png": b"x"}
    assert main(["picture", "geometry", str(project), "--out", str(tmp_path) + "/"]) == 0
    assert (tmp_path / "evil.png").is_file()
    assert not (tmp_path.parent.parent / "evil.png").exists()


# ── When it goes wrong ──────────────────────────────────────────────────────

def test_the_pages_error_is_the_commands_error(stand, project, capsys):
    stand.error = 'No colour map called "x".'
    assert main(["picture", "geometry", str(project)]) != 0
    assert 'No colour map called "x".' in capsys.readouterr().err


def test_nothing_drawn_says_so(stand, project, capsys):
    stand.files = {}
    assert main(["picture", "geometry", str(project)]) != 0
    assert "nothing to draw" in capsys.readouterr().err


def test_a_file_lost_on_the_way_is_noticed(stand, project, capsys):
    stand.count = 5
    assert main(["picture", "geometry", str(project)]) != 0
    assert "5 files" in capsys.readouterr().err


def test_no_browser_says_what_to_do(monkeypatch, project, capsys):
    monkeypatch.setattr(pictures, "find_browser", lambda: None)
    assert main(["picture", "geometry", str(project)]) != 0
    error = capsys.readouterr().err
    assert "Chrome or Edge" in error
    assert pictures.BROWSER_ENV in error


def test_a_browser_that_stops_early_is_reported(stand, project, monkeypatch, capsys):
    monkeypatch.setattr(pictures, "open_page", lambda *_: FakePage(running=False))
    monkeypatch.setattr(threading.Event, "wait", lambda self, timeout=None: False)
    assert main(["picture", "geometry", str(project)]) != 0
    assert "browser stopped" in capsys.readouterr().err


def test_no_answer_is_a_timeout(stand, project, monkeypatch, capsys):
    monkeypatch.setattr(pictures, "open_page", lambda *_: FakePage())
    monkeypatch.setattr(pictures, "WAIT_SECONDS", 0.05)
    assert main(["picture", "geometry", str(project)]) != 0
    assert "No answer" in capsys.readouterr().err


# ── Finding the browser ─────────────────────────────────────────────────────

def test_the_setting_comes_first(monkeypatch):
    monkeypatch.setenv(pictures.BROWSER_ENV, "/my/browser")
    assert pictures.find_browser() == "/my/browser"


def test_then_the_path(monkeypatch):
    monkeypatch.delenv(pictures.BROWSER_ENV, raising=False)
    monkeypatch.setattr(pictures.shutil, "which",
                        lambda name: "/usr/bin/msedge" if name == "msedge" else None)
    assert pictures.find_browser() == "/usr/bin/msedge"


def test_then_where_it_installs(monkeypatch, tmp_path):
    monkeypatch.delenv(pictures.BROWSER_ENV, raising=False)
    monkeypatch.setattr(pictures.shutil, "which", lambda name: None)
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path))
    monkeypatch.setattr(pictures, "BROWSER_PATHS", ("Edge/msedge.exe",))
    monkeypatch.setattr(pictures, "MAC_BROWSERS", ())
    assert pictures.find_browser() is None
    (tmp_path / "Edge").mkdir()
    (tmp_path / "Edge" / "msedge.exe").write_text("")
    assert pictures.find_browser() == str(tmp_path / "Edge" / "msedge.exe")


# ── The receiver and the processes ──────────────────────────────────────────

def test_the_receiver_answers_only_its_own_address():
    with pictures.Receiver() as receiver:
        base = receiver.url.rsplit("/", 1)[0]
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(urllib.request.Request(base + "/wrong/file?name=x", data=b"1",
                                                          method="POST"))
        assert receiver.files == {}
        urllib.request.urlopen(urllib.request.Request(receiver.url + "/file?name=x", data=b"1",
                                                      method="POST"))
        assert receiver.files == {"x": b"1"}


def test_stop_ends_a_process_and_what_it_started():
    child = "import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); time.sleep(60)"
    process = subprocess.Popen([sys.executable, "-c", child],
                               start_new_session=sys.platform != "win32")
    pictures.stop(process)
    assert process.poll() is not None


def test_a_server_that_does_not_start_is_reported(monkeypatch):
    class Dead(FakePage):
        def poll(self):
            return 1

    monkeypatch.setattr(pictures.subprocess, "Popen", lambda *a, **k: Dead())
    monkeypatch.setattr(pictures, "stop", lambda _process: None)
    with pytest.raises(CommandError, match="did not start"):
        pictures.start_server("token")


def test_the_server_is_waited_for(monkeypatch):
    class Answer:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    tries = []

    def urlopen(url, timeout=None):
        tries.append(url)
        if len(tries) < 2:
            raise urllib.error.URLError("not yet")
        return Answer()

    started = {}

    def popen(command, **options):
        started.update(options)
        return FakePage()

    monkeypatch.setattr(pictures.subprocess, "Popen", popen)
    monkeypatch.setattr(pictures.urllib.request, "urlopen", urlopen)
    _, url = pictures.start_server("the-token")
    assert tries == [url + "/api/health"] * 2
    assert started["env"][pictures.JOB_ENV] == "the-token"


def test_a_refused_model_says_why(monkeypatch):
    def urlopen(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 422, "no", {}, io.BytesIO(b"bad depth"))

    monkeypatch.setattr(pictures.urllib.request, "urlopen", urlopen)
    with pytest.raises(CommandError, match="bad depth"):
        pictures.put_project("http://server", "{}")


def test_the_browser_gets_no_window_and_its_own_profile(monkeypatch):
    seen = {}

    def popen(command, **_):
        seen["command"] = command
        return FakePage()

    monkeypatch.setattr(pictures.subprocess, "Popen", popen)
    pictures.open_page("browser", "http://page", "profile")
    assert seen["command"][0] == "browser"
    assert "--headless=new" in seen["command"]
    assert "--user-data-dir=profile" in seen["command"]
    assert seen["command"][-1] == "http://page"
