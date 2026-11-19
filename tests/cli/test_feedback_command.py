"""`kratos-cli feedback`: the report the GUI's Feedback window saves, from the terminal, and
how `kratos-cli` says to report an error no command expected."""

from __future__ import annotations

import zipfile

import pytest

from cli.terminal import main as cli_main
from core import feedback
from core.analysis import calculation


@pytest.fixture(autouse=True)
def reports(tmp_path, monkeypatch):
    folder = tmp_path / "feedback"
    monkeypatch.setenv(feedback.FOLDER_ENV, str(folder))
    return folder


def files_of(said: dict) -> dict[str, bytes]:
    """The files of the report the answer `said` is about, by their names in its folder."""
    prefix = said["report"] + "/"
    with zipfile.ZipFile(said["path"]) as archive:
        return {name[len(prefix):]: archive.read(name) for name in archive.namelist()
                if name.startswith(prefix)}


def test_a_report_with_the_project_file_lands_in_the_feedback_folder(cli, site, reports):
    ran = cli("feedback", "Layer add was hard to find", "--kind", "confusing",
              "--name", "Ben", "--project", site, "--json")

    assert ran.code == 0, ran.err
    said = ran.json()
    files = files_of(said)
    assert said["folder"] == str(reports)
    assert said["name"].startswith("styx-feedback-") and said["name"].endswith("-ben.zip")
    assert said["report"].endswith("-confusing")
    assert files["site.json"] == site.read_bytes()
    text = files["report.txt"].decode()
    assert "Something is confusing (confusing)" in text
    assert "Sent by:  kratos-cli" in text


def test_the_run_gives_its_log(cli, tmp_path):
    run = tmp_path / "runs" / "site_2026-11-17_14-00"
    run.mkdir(parents=True)
    (run / calculation.LOG_NAME).write_text("Kratos stopped", encoding="utf-8")

    ran = cli("feedback", "The run stopped", "--run", run.name, "--json")

    assert ran.code == 0, ran.err
    assert files_of(ran.json())["run/kratos.log"] == b"Kratos stopped"


def test_the_gui_and_the_command_add_to_the_same_file_and_files_go_in(cli, tmp_path, reports):
    picture = tmp_path / "shot.png"
    picture.write_bytes(b"\x89PNG\r\n\x1a\nrest")
    notes = tmp_path / "notes.docx"
    notes.write_bytes(b"PK doc")
    feedback.write(feedback.Report(kind="bug", message="from the GUI", name="Ben"))

    ran = cli("feedback", "from the terminal", "--name", "Ben", "--attach", picture)

    assert ran.code == 0, ran.err
    assert "(2 reports in it now)" in ran.out
    assert len(list(reports.iterdir())) == 1
    ran = cli("feedback", "again", "--name", "Ben", "--attach", picture, "--attach", notes,
              "--json")
    files = files_of(ran.json())
    assert files["attachments/shot.png"] == picture.read_bytes()
    assert files["attachments/notes.docx"] == b"PK doc"


def test_out_puts_it_elsewhere(cli, tmp_path):
    ran = cli("feedback", "nice", "--kind", "good", "--out", tmp_path / "mine")

    assert ran.code == 0, ran.err
    assert ran.out.startswith("added ")
    assert f"-good to {tmp_path / 'mine'}" in ran.out
    assert len(list((tmp_path / "mine").glob("styx-feedback-*.zip"))) == 1


@pytest.mark.parametrize("argv, said", [
    (["feedback", "   "], "Write what happened"),
    (["feedback", "x", "--project", "no_such.json"], "no such project file"),
    (["feedback", "x", "--run", "nothing_2026-11-17_14-00"], "no such run"),
    (["feedback", "x", "--attach", "no_such.png"], "no such file to attach"),
])
def test_a_report_that_cannot_be_written_says_why(cli, argv, said):
    ran = cli(*argv)

    assert ran.code == 1
    assert said in ran.err


def test_the_kinds_are_the_gui_s(cli):
    ran = cli("feedback", "x", "--kind", "praise")

    assert ran.code == 2
    assert "bug" in ran.err and "confusing" in ran.err and "good" in ran.err


def test_an_error_no_command_expected_says_how_to_report_it(site, monkeypatch, capsys):
    def broken(_args):
        raise KeyError("missing")

    parser = cli_main.parser

    def with_a_broken_show():
        top = parser()
        top._subparsers._group_actions[0].choices["show"].set_defaults(handler=broken)
        return top

    monkeypatch.setattr(cli_main, "parser", with_a_broken_show)

    with pytest.raises(KeyError):
        cli_main.main(["show", str(site)])

    said = capsys.readouterr().err
    assert "This is a fault in Styx, not in the model." in said
    assert f'kratos-cli feedback "what you did" --project {site}' in said
