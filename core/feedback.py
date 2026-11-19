"""A feedback report: what a user says about Styx, with what is needed to see it again.

The GUI's Feedback window, its "Save a report" after an error (`backend/routes/feedback.py`)
and `kratos-cli feedback` all write the same thing, in the feedback folder: that is
`~/KratosGUI/feedback` (beside the runs), or `KRATOS_GUI_FEEDBACK`.

All the reports of one person on one day go in one ZIP file, `styx-feedback-<date>-<name>.zip`,
each in a folder of its own, `<time>-<kind>/`. At the end of a workshop each person has one
file to send, and the files of all of them can share one folder and still be told apart. The
ZIP file also holds `reports.txt`, the list of the reports in it.

A report's folder holds:

- `report.txt`: the message, who wrote it, when, the version of Styx, where in the app it was
  written, and the errors seen before it; written to be read first.
- `report.json`: the same, for a script to read.
- `project.json` (or the model script): the model at that moment, so the problem can be seen
  again by opening it.
- `view.png`: a picture of the model view, when the GUI sent one.
- `attachments/`: the files the user added: a screenshot they pasted, a document, a model of
  their own, any file.
- the logs it was given (the GUI's Session log and Model history, the server's own log), and
  the Kratos log and parameter files of the run that was open.

A report is added by writing the whole ZIP file again beside the old one, and then putting it
in the old one's place: a save that fails half-way leaves the reports saved before it as
they were.

Only the standard library, `core.analysis.calculation` (for the runs folder) and
`core.kratos.deck_files` (for the names of the run's files): the server and the command line
both import this.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import threading
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.analysis import calculation
from core.kratos.deck_files import MATERIALS_NAME, PARAMETERS_NAME

FOLDER_ENV = "KRATOS_GUI_FEEDBACK"
"""Where the reports are written. Defaults to `~/KratosGUI/feedback`."""

KINDS = {
    "bug": "Something is wrong",
    "confusing": "Something is confusing",
    "missing": "Something is missing",
    "good": "Something works well",
}
"""The kinds of feedback, by the word `kratos-cli feedback --kind` and the GUI send, with the
words the Feedback window shows."""

MAX_MESSAGE = 20_000
MAX_NAME = 100

RUN_FILES = (calculation.LOG_NAME, PARAMETERS_NAME, MATERIALS_NAME)
"""The files of the open run that go in a report: small, and they say what Kratos was given
and what it said. The mesh is left out: the model makes it again."""

INDEX = "reports.txt"
"""The list of the reports in a ZIP file, at its top."""

ATTACHMENTS = "attachments"
"""The folder of a report that holds the files its writer added."""
MAX_ATTACHMENTS = 10
MAX_ATTACHMENT_BYTES = 15_000_000
"""The largest file a writer may add: a screenshot, a document or a model, not a video."""

_RUN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

_ADDING = threading.Lock()
"""Held while a report is added to a ZIP file: the server saves two reports in two threads,
and each reads the old file before it puts the new one in its place."""


class FeedbackError(ValueError):
    """The report cannot be written as asked. The message says why, to be shown as it is."""


@dataclass
class Report:
    kind: str
    message: str = ""
    name: str = ""
    source: str = "GUI"
    """What wrote it: `GUI` or `kratos-cli`."""
    version: str = ""
    context: dict = field(default_factory=dict)
    """Where in the app it was written: the mode, the open window, the selection, ..."""
    errors: list[dict] = field(default_factory=list)
    """The errors seen before it, each `{"when", "what", "detail"}`. The first is the one
    the report is about when it came from "Save a report"."""
    logs: dict[str, str] = field(default_factory=dict)
    """Text files to put in the report, by file name."""
    project: str | None = None
    """The model, as the text of its file."""
    project_file: str = "project.json"
    view: bytes | None = None
    """A picture of the model view, as PNG: the GUI adds it by itself."""
    attachments: list[tuple[str, bytes]] = field(default_factory=list)
    """The files the writer added, of any kind, each as the name it had and its bytes.
    `attachment_names` makes the names safe for the ZIP file, and tells two alike apart."""
    run: str | Path | None = None
    """The run it is about: the name of a run under the runs folder (the GUI's open run),
    or a run directory anywhere (`kratos-cli feedback --run`)."""


@dataclass
class Saved:
    """Where a report went."""

    path: Path
    """The ZIP file it was added to."""
    report: str
    """Its folder in that file."""
    files: list[str]
    """Its files, as they are named in the ZIP file (with the folder in front)."""
    reports: int
    """How many reports the ZIP file holds now, this one included."""


def folder() -> Path:
    configured = os.environ.get(FOLDER_ENV, "").strip()
    return Path(configured) if configured else Path.home() / "KratosGUI" / "feedback"


def check(report: Report) -> None:
    """Raise `FeedbackError` for a report that cannot be written."""
    if report.kind not in KINDS:
        raise FeedbackError(f"{report.kind!r} is not a kind of feedback. The kinds are "
                            f"{', '.join(KINDS)}.")
    if not report.message.strip() and not report.errors:
        raise FeedbackError("Write what happened, or what you would like to see.")
    if len(report.message) > MAX_MESSAGE:
        raise FeedbackError(f"The message is longer than {MAX_MESSAGE} characters. Make it "
                            "shorter, or send it as two reports.")
    if len(report.name) > MAX_NAME:
        raise FeedbackError(f"The name is longer than {MAX_NAME} characters.")
    if isinstance(report.run, str) and not _RUN_NAME.fullmatch(report.run):
        raise FeedbackError(f"{report.run!r} is not the name of a run.")
    if report.view and not report.view.startswith(b"\x89PNG\r\n\x1a\n"):
        raise FeedbackError("The picture of the view is not a PNG.")
    if len(report.attachments) > MAX_ATTACHMENTS:
        raise FeedbackError(f"A report can hold {MAX_ATTACHMENTS} files at most. Put the "
                            "others in a second report.")
    for name, data in report.attachments:
        if len(data) > MAX_ATTACHMENT_BYTES:
            raise FeedbackError(f"{name} is larger than {MAX_ATTACHMENT_BYTES // 1_000_000} "
                                "MB. Add a smaller file.")


def attachment_names(names: list[str]) -> list[str]:
    """A safe name in the ZIP file for each of `names`, the names the writer's files had:
    the last part of the path only, with letters, digits, dots, dashes and underscores, and
    `-2`, `-3`, ... before the extension where two names are the same."""
    safe: list[str] = []
    taken: set[str] = set()
    for name in names:
        last = re.split(r"[\\/]", str(name))[-1]
        kept = re.sub(r"[^A-Za-z0-9._-]+", "-", last).strip("-.")[:80] or "file"
        stem, dot, suffix = kept.rpartition(".")
        if not dot or not stem:
            stem, suffix = kept, ""
        candidate, count = kept, 2
        while candidate.lower() in taken:
            candidate = f"{stem}-{count}" + (f".{suffix}" if suffix else "")
            count += 1
        taken.add(candidate.lower())
        safe.append(candidate)
    return safe


def slug(text: str, longest: int = 24) -> str:
    """`text` as a part of a file name: letters, digits and dashes only."""
    kept = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return kept[:longest].strip("-")


def file_name(report: Report, now: datetime) -> str:
    """The ZIP file of the reports of `report`'s writer on the day of `now`."""
    parts = ["styx-feedback", now.strftime("%Y-%m-%d")]
    who = slug(report.name)
    if who:
        parts.append(who)
    return "-".join(parts) + ".zip"


def report_folder(report: Report, now: datetime, taken: set[str]) -> str:
    """The folder of `report` in its ZIP file: the time and the kind, with `-2`, `-3`, ...
    after it where `taken` has that name already."""
    base = f"{now.strftime('%H-%M-%S')}-{report.kind}"
    name, count = base, 2
    while name in taken:
        name, count = f"{base}-{count}", count + 1
    return name


def write(report: Report, into: Path | None = None, now: datetime | None = None) -> Saved:
    """Add `report` to its writer's ZIP file of the day, in `into` (default: `folder()`)."""
    check(report)
    now = now or datetime.now()
    target_folder = into or folder()
    try:
        target_folder.mkdir(parents=True, exist_ok=True)
    except OSError as failure:
        raise FeedbackError(f"The folder {target_folder} could not be made: {failure}. Set "
                            f"{FOLDER_ENV} to a folder that can be written to.") from failure
    with _ADDING:
        return _add(report, now, target_folder)


def _add(report: Report, now: datetime, target_folder: Path) -> Saved:
    target = _day_file(target_folder / file_name(report, now))
    earlier = _reports_in(target)
    name = report_folder(report, now, set(earlier))
    files = {f"{name}/{file}": content for file, content in contents(report, now).items()}
    listed = {**earlier, name: _summary(report, now)}
    handle, temporary = tempfile.mkstemp(prefix=".styx-feedback-", suffix=".tmp",
                                         dir=target_folder)
    os.close(handle)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(INDEX, index(report, now, listed))
            if target.exists():
                _copy_into(archive, target)
            for file, content in files.items():
                archive.writestr(file, content)
        os.replace(temporary, target)
    except OSError as failure:
        Path(temporary).unlink(missing_ok=True)
        raise FeedbackError(f"The report could not be added to {target}: {failure}. If the "
                            "file is open in another program, close it and save again."
                            ) from failure
    return Saved(path=target, report=name, files=list(files), reports=len(listed))


def _day_file(path: Path) -> Path:
    """`path`, or the same name with `-2`, `-3`, ... where a file of that name is there but is
    not a ZIP file that can be read. That file is left as it is."""
    candidate, count = path, 2
    while candidate.exists() and not _readable(candidate):
        candidate = path.with_name(f"{path.stem}-{count}{path.suffix}")
        count += 1
    return candidate


def _readable(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            archive.namelist()
        return True
    except (OSError, zipfile.BadZipFile):
        return False


def _reports_in(path: Path) -> dict[str, dict]:
    """The reports in the ZIP file `path`, by folder, each with what its `report.json` says."""
    if not path.exists():
        return {}
    found: dict[str, dict] = {}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            folder_name, _, rest = name.partition("/")
            if not rest:
                continue
            found.setdefault(folder_name, {})
            if rest == "report.json":
                try:
                    found[folder_name] = json.loads(archive.read(name))
                except ValueError:
                    pass
    return found


def _copy_into(archive: zipfile.ZipFile, path: Path) -> None:
    """Copy the files of the ZIP file `path` into `archive`, but not its list of reports:
    `archive` has a new one."""
    with zipfile.ZipFile(path) as old:
        for info in old.infolist():
            if info.filename == INDEX:
                continue
            with old.open(info) as source, archive.open(info, "w") as copy:
                shutil.copyfileobj(source, copy)


def _summary(report: Report, now: datetime) -> dict:
    return {"kind": report.kind, "message": report.message, "name": report.name,
            "time": now.isoformat(timespec="seconds")}


def index(report: Report, now: datetime, listed: dict[str, dict]) -> str:
    """`reports.txt`: the reports in the ZIP file, one line each, by time."""
    who = report.name.strip() or "(no name given)"
    title = f"Styx feedback of {now.strftime('%Y-%m-%d')}, from {who}"
    lines = [title, "=" * len(title), "",
             "Each folder holds one report. Open its report.txt first.", ""]
    width = max(len(name) for name in listed)
    for name in sorted(listed):
        said = listed[name]
        kind = KINDS.get(said.get("kind", ""), "")
        first = (str(said.get("message") or "").strip().splitlines()
                 or ["(no message: saved after an error)"])[0]
        if len(first) > 70:
            first = first[:69] + "…"
        lines.append(f"{name.ljust(width)}  {kind.ljust(22)}  {first}".rstrip())
    return "\n".join(lines) + "\n"


def contents(report: Report, now: datetime) -> dict[str, str | bytes]:
    """The files of the report, by name, `report.txt` first."""
    files: dict[str, str | bytes] = {}
    if report.project is not None:
        files[report.project_file] = report.project
    if report.view:
        files["view.png"] = report.view
    safe = attachment_names([name for name, _data in report.attachments])
    for name, (_given, data) in zip(safe, report.attachments):
        files[f"{ATTACHMENTS}/{name}"] = data
    for name, log in report.logs.items():
        if log.strip():
            files[name] = log
    files.update(run_files(report.run))
    summary = {
        "kind": report.kind, "message": report.message, "name": report.name,
        "source": report.source, "version": report.version,
        "time": now.isoformat(timespec="seconds"), "context": report.context,
        "errors": report.errors, "run": None if report.run is None else str(report.run),
        "files": sorted(files),
    }
    return {"report.txt": readable(report, now, sorted(files)),
            "report.json": json.dumps(summary, indent=2, ensure_ascii=False) + "\n", **files}


def run_directory(run: str | Path | None) -> Path | None:
    """Where the run `run` is, or None for a run that is not there. A name is looked up
    under the runs folder only: it cannot lead out of it."""
    if isinstance(run, Path):
        return run if run.is_dir() else None
    if not run or not _RUN_NAME.fullmatch(run):
        return None
    root = calculation.runs_root()
    directory = root / run
    if not directory.is_dir() or directory.resolve().parent != root.resolve():
        return None
    return directory


def run_files(run: str | Path | None) -> dict[str, str]:
    """The `RUN_FILES` of the run `run`, as `run/<name>`; none for a run that is not there."""
    directory = run_directory(run)
    if directory is None:
        return {}
    found = {}
    for name in RUN_FILES:
        path = directory / name
        if path.is_file():
            found[f"run/{name}"] = path.read_text(encoding="utf-8", errors="replace")
    return found


FILE_NOTES = {
    "view.png": "the model view when the report was written",
    "session-log.txt": "the Session log of the GUI's command panel",
    "model-history.txt": "the Model history of the GUI's command panel",
    "server-log.txt": "the server's own log: its errors and the last requests",
    "report.json": "this report, for a script to read",
}


def _note(name: str, report: Report) -> str:
    if name == report.project_file:
        return "the model when the report was written: open it to see the problem again"
    if name.startswith("run/"):
        return f"from the open run, {report.run}"
    if name.startswith(ATTACHMENTS + "/"):
        return "added by the writer"
    return FILE_NOTES.get(name, "")


def readable(report: Report, now: datetime, names: list[str]) -> str:
    """`report.txt`: the report written to be read."""
    lines = ["Styx feedback", "=============", "",
             f"Kind:     {KINDS[report.kind]} ({report.kind})",
             f"From:     {report.name.strip() or '(no name given)'}",
             f"When:     {now.strftime('%Y-%m-%d %H:%M:%S')}",
             f"Version:  {report.version or '(unknown)'}",
             f"Sent by:  {report.source}", "",
             "What happened", "-------------",
             report.message.strip() or "(no message: the report was saved after an error)", ""]
    if report.context:
        lines += ["Where", "-----"]
        lines += [f"{key}: {_said(value)}" for key, value in report.context.items()
                  if value not in (None, "", [], {})]
        lines.append("")
    if report.errors:
        lines += ["Errors before this report", "-------------------------"]
        for error in report.errors:
            lines.append(f"{error.get('when', '')}  {error.get('what', '')}".strip())
            detail = str(error.get("detail") or "").strip()
            lines += ["    " + line for line in detail.splitlines()]
        lines.append("")
    lines += ["Files in this report", "--------------------"]
    width = max((len(name) for name in names + ["report.json"]), default=0)
    for name in ["report.json", *names]:
        note = _note(name, report)
        lines.append(f"{name.ljust(width)}  {note}".rstrip())
    return "\n".join(lines) + "\n"


def _said(value) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
