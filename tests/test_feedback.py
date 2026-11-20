"""A feedback report in its writer's ZIP file of the day (core/feedback.py): the file's name,
the report's folder in it, what is in that folder, and what is refused. The GUI's route and `kratos-cli feedback` both write it; their own tests are in
tests/api/test_feedback_routes.py and tests/cli/test_feedback_command.py."""

from __future__ import annotations

import json
import math
import re
import threading
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from core import feedback
from core.analysis import calculation

NOW = datetime(2026, 11, 17, 14, 5, 12)


PNG = b"\x89PNG\r\n\x1a\nrest"
JPEG = b"\xff\xd8\xffrest"


def files_of(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def report_files(saved: feedback.Saved) -> dict[str, bytes]:
    """The files of the report `saved`, by their names in its folder."""
    prefix = saved.report + "/"
    return {name[len(prefix):]: data for name, data in files_of(saved.path).items()
            if name.startswith(prefix)}


def test_a_report_goes_in_a_folder_of_its_own_in_the_day_s_zip_of_its_writer(tmp_path):
    report = feedback.Report(kind="confusing", message="Where is the water level?",
                             name="Anna de Vries")

    saved = feedback.write(report, tmp_path, NOW)

    assert saved.path == tmp_path / "styx-feedback-2026-11-17-anna-de-vries.zip"
    assert saved.report == "14-05-12-confusing"
    assert saved.reports == 1
    assert list(files_of(saved.path))[:3] == [
        "reports.txt", "14-05-12-confusing/report.txt", "14-05-12-confusing/report.json"]
    assert saved.files == [name for name in files_of(saved.path) if name != "reports.txt"]


def test_the_reports_of_one_day_go_in_one_file_and_are_all_kept(tmp_path):
    first = feedback.write(feedback.Report(kind="bug", message="It broke.", name="Ben",
                                           view=PNG), tmp_path, NOW)
    second = feedback.write(feedback.Report(kind="good", message="Nice ruler.", name="Ben"),
                            tmp_path, NOW.replace(hour=15))

    assert second.path == first.path
    assert second.reports == 2
    files = files_of(second.path)
    assert files["14-05-12-bug/view.png"] == PNG, "the first report is kept as it was"
    assert b"Nice ruler." in files["15-05-12-good/report.txt"]
    assert list(files).count("reports.txt") == 1
    index = files["reports.txt"].decode()
    assert "Styx feedback of 2026-11-17, from Ben" in index
    assert index.index("14-05-12-bug") < index.index("15-05-12-good")
    assert "Something works well    Nice ruler." in index
    assert [p.name for p in tmp_path.iterdir()] == [second.path.name], "no file left over"


def test_another_day_or_another_name_is_another_file(tmp_path):
    ben = feedback.write(feedback.Report(kind="bug", message="m", name="Ben"), tmp_path, NOW)
    tomorrow = feedback.write(feedback.Report(kind="bug", message="m", name="Ben"), tmp_path,
                              NOW.replace(day=18))
    nobody = feedback.write(feedback.Report(kind="bug", message="m"), tmp_path, NOW)

    assert ben.path.name == "styx-feedback-2026-11-17-ben.zip"
    assert tomorrow.path.name == "styx-feedback-2026-11-18-ben.zip"
    assert nobody.path.name == "styx-feedback-2026-11-17.zip"


def test_a_second_report_in_the_same_second_gets_a_folder_of_its_own(tmp_path):
    report = feedback.Report(kind="bug", message="again")

    first = feedback.write(report, tmp_path, NOW)
    second = feedback.write(report, tmp_path, NOW)

    assert (first.report, second.report) == ("14-05-12-bug", "14-05-12-bug-2")
    assert second.path == first.path


def test_a_damaged_file_of_the_day_is_left_as_it_is(tmp_path):
    damaged = tmp_path / "styx-feedback-2026-11-17.zip"
    damaged.write_bytes(b"not a zip")

    saved = feedback.write(feedback.Report(kind="bug", message="m"), tmp_path, NOW)

    assert saved.path.name == "styx-feedback-2026-11-17-2.zip"
    assert damaged.read_bytes() == b"not a zip"


def test_a_save_that_fails_leaves_the_earlier_reports_as_they_were(tmp_path, monkeypatch):
    first = feedback.write(feedback.Report(kind="bug", message="first"), tmp_path, NOW)
    before = first.path.read_bytes()

    def locked(*_args):
        raise PermissionError("the file is in use")

    monkeypatch.setattr(feedback.os, "replace", locked)
    with pytest.raises(feedback.FeedbackError, match="close it and save again"):
        feedback.write(feedback.Report(kind="bug", message="second"), tmp_path, NOW)

    assert first.path.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == [first.path.name], "no file left over"


def test_the_writer_s_files_of_any_kind_go_in_attachments(tmp_path):
    report = feedback.Report(kind="bug", message="m", attachments=[
        ("screenshot.png", PNG), ("C:/Users/ben/notes on the wall.docx", b"PK doc"),
        ("../../evil.txt", b"x"), ("screenshot.png", b"other")])

    files = report_files(feedback.write(report, tmp_path, NOW))

    assert files["attachments/screenshot.png"] == PNG
    assert files["attachments/notes-on-the-wall.docx"] == b"PK doc", "the name only, made safe"
    assert files["attachments/evil.txt"] == b"x", "a path cannot lead out of the folder"
    assert files["attachments/screenshot-2.png"] == b"other", "two names alike are told apart"
    assert "attachments/notes-on-the-wall.docx  added by the writer" in files[
        "report.txt"].decode()


def test_a_name_with_nothing_safe_in_it_becomes_file():
    assert feedback.attachment_names(["???", "..."]) == ["file", "file-2"]


def test_too_many_or_too_large_files_are_refused(tmp_path):
    many = [(f"{i}.txt", b"x") for i in range(feedback.MAX_ATTACHMENTS + 1)]
    with pytest.raises(feedback.FeedbackError, match="files at most"):
        feedback.write(feedback.Report(kind="bug", message="m", attachments=many), tmp_path, NOW)
    large = [("film.mp4", b"x" * (feedback.MAX_ATTACHMENT_BYTES + 1))]
    with pytest.raises(feedback.FeedbackError, match="film.mp4 is larger than 15 MB"):
        feedback.write(feedback.Report(kind="bug", message="m", attachments=large), tmp_path, NOW)


def test_the_report_holds_the_model_the_picture_the_logs_and_says_what_each_is(tmp_path):
    report = feedback.Report(
        kind="bug", message="The mesh did not show.", name="Ben", version="0.1.0",
        context={"mode": "Mesh", "window": "Mesh properties", "selected": None},
        errors=[{"when": "14:04:00", "what": "Server error 500 on POST /api/mesh",
                 "detail": "gmsh failed\nat line 2"}],
        logs={"session-log.txt": "> mesh\nMesh failed", "model-history.txt": "  "},
        project='{"name": "dike"}', view=PNG, window=PNG + b"window")

    files = report_files(feedback.write(report, tmp_path, NOW))
    text = files["report.txt"].decode()

    assert files["project.json"] == b'{"name": "dike"}'
    assert files["view.png"] == PNG
    assert files["window.png"] == PNG + b"window"
    assert files["session-log.txt"] == b"> mesh\nMesh failed"
    assert "model-history.txt" not in files, "an empty log is left out"
    assert "Kind:     Something is wrong (bug)" in text
    assert "From:     Ben" in text
    assert "Version:  0.1.0" in text
    assert "The mesh did not show." in text
    assert "window: Mesh properties" in text
    assert "selected" not in text, "an empty value is left out"
    assert "14:04:00  Server error 500 on POST /api/mesh\n    gmsh failed\n    at line 2" in text
    assert "project.json     the model when the report was written" in text
    assert "window.png       the whole Styx window when the report was written" in text
    summary = json.loads(files["report.json"])
    assert summary["kind"] == "bug"
    assert summary["time"] == "2026-11-17T14:05:12"
    assert summary["files"] == ["project.json", "session-log.txt", "view.png", "window.png"]


def test_the_open_run_gives_its_log_and_parameters(tmp_path, monkeypatch):
    monkeypatch.setenv(calculation.RUNS_ENV, str(tmp_path / "runs"))
    run = tmp_path / "runs" / "dike_2026-11-17_14-00"
    run.mkdir(parents=True)
    (run / calculation.LOG_NAME).write_text("Kratos stopped", encoding="utf-8")
    (run / "ProjectParameters.json").write_text("{}", encoding="utf-8")
    (run / "dike.mdpa").write_text("a large mesh", encoding="utf-8")

    files = report_files(feedback.write(feedback.Report(kind="bug", message="m",
                                                        run=run.name), tmp_path, NOW))

    assert files["run/kratos.log"] == b"Kratos stopped"
    assert files["run/ProjectParameters.json"] == b"{}"
    assert not any(name.endswith(".mdpa") for name in files), "the mesh is left out"


@pytest.mark.parametrize("run", ["..", "../runs", "no_such_run"])
def test_a_run_name_cannot_lead_out_of_the_runs_folder(tmp_path, monkeypatch, run):
    monkeypatch.setenv(calculation.RUNS_ENV, str(tmp_path / "runs"))
    (tmp_path / "runs").mkdir()

    assert feedback.run_files(run) == {}


def test_a_run_directory_anywhere_can_be_named_by_its_path(tmp_path):
    run = tmp_path / "elsewhere"
    run.mkdir()
    (run / calculation.LOG_NAME).write_text("done", encoding="utf-8")

    assert feedback.run_files(run) == {"run/kratos.log": "done"}


def test_the_folder_is_beside_the_runs_or_where_the_environment_says(tmp_path, monkeypatch):
    monkeypatch.delenv(feedback.FOLDER_ENV, raising=False)
    assert feedback.folder() == Path.home() / "KratosGUI" / "feedback"

    monkeypatch.setenv(feedback.FOLDER_ENV, str(tmp_path / "reports"))
    saved = feedback.write(feedback.Report(kind="good", message="nice"), now=NOW)

    assert saved.path.parent == tmp_path / "reports"


@pytest.mark.parametrize("report, said", [
    (feedback.Report(kind="praise", message="x"), "not a kind of feedback"),
    (feedback.Report(kind="bug", message="   "), "Write what happened"),
    (feedback.Report(kind="bug", message="x" * (feedback.MAX_MESSAGE + 1)), "longer than"),
    (feedback.Report(kind="bug", message="x", run="../up"), "not the name of a run"),
    (feedback.Report(kind="bug", message="x", view=JPEG), "view is not a PNG"),
])
def test_a_report_that_cannot_be_written_says_why(tmp_path, report, said):
    with pytest.raises(feedback.FeedbackError, match=said):
        feedback.write(report, tmp_path, NOW)
    assert list(tmp_path.iterdir()) == []


def test_a_report_after_an_error_needs_no_words(tmp_path):
    report = feedback.Report(kind="bug", errors=[{"when": "1", "what": "Script error"}])

    saved = feedback.write(report, tmp_path, NOW)

    assert "(no message: the report was saved after an error)" in report_files(saved)[
        "report.txt"].decode()
    assert "(no message: saved after an error)" in files_of(saved.path)["reports.txt"].decode()


def test_a_name_in_a_file_name_keeps_letters_and_digits_only():
    assert feedback.slug("  Jo O'Brien / Team 2 ") == "jo-o-brien-team-2"
    assert feedback.slug("***") == ""


# ── The browser's copy ──────────────────────────────────────────────────────

FEEDBACK_JS = Path(__file__).resolve().parents[1] / "frontend" / "js" / "feedback.js"


def test_the_window_offers_the_kinds_and_limits_the_server_takes():
    """frontend/js/feedback.js keeps its own copy of the kinds and the file limits, so the
    window can refuse a file before it is sent. The copy must match core/feedback.py."""
    source = FEEDBACK_JS.read_text(encoding="utf-8")
    kinds = dict(re.findall(r"\{ id: '(\w+)', label: '([^']+)'", source))
    assert kinds == feedback.KINDS
    assert re.search(r"var MAX_FILES = (\d+);", source).group(1) == str(feedback.MAX_ATTACHMENTS)
    factors = re.search(r"var MAX_FILE_BYTES = ([\d *]+);", source).group(1).split("*")
    assert math.prod(int(factor) for factor in factors) == feedback.MAX_ATTACHMENT_BYTES


def test_reports_saved_at_the_same_time_are_all_kept(tmp_path):
    """The server saves in parallel threads: each report must reach the day's file."""
    count = 8
    start = threading.Barrier(count)

    def save(i: int) -> None:
        start.wait()
        feedback.write(feedback.Report(kind="bug", message=f"report {i}", name="Anna"),
                       tmp_path, NOW)

    threads = [threading.Thread(target=save, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    (day,) = tmp_path.glob("*.zip")
    messages = sorted(json.loads(data)["message"] for name, data in files_of(day).items()
                      if name.endswith("/report.json"))
    assert messages == sorted(f"report {i}" for i in range(count))

