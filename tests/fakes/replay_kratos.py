"""A stand-in for `core.analysis.calculation.run` that gives back one real Kratos run.

GitHub's runners have no Kratos, but the GUI tutorials show real results. So one real run
of each tutorial's model is recorded on a computer with Kratos
(`python tools/gui_tutorial.py NAME --record`) into `tests/fixtures/tutorial_runs/NAME/`,
and this replays it: it makes a run directory as `calculation.run` does, writes the deck
the GUI gives it, and copies the recorded output beside it. Results mode then reads a real
run.

The replay also compares the deck it is given with the recorded deck (`tests/deck_compare.py`).
If they differ, the recorded run belongs to another model. The replay still copies it, so a
pull request can go on, and it notes the problem in `problems`: the tutorial test warns
about it, or with `--strict-deck` fails on it.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from core.analysis import calculation
from tests import deck_compare

ANSWER = "answer.json"
"""What `calculation.run` answered for the recorded run, saved beside its files."""


class Replay:
    """`calculation.run` for the run recorded in `folder`."""

    def __init__(self, folder: Path, record_command: str):
        self.folder = folder
        self.record_command = record_command
        self.problems: list[str] = []

    def __call__(self, export: dict) -> dict:
        started = time.monotonic()
        directory = calculation.new_run_directory(export["deck_name"])
        inputs = calculation.write_deck(export, directory)
        found = deck_compare.differences(
            deck_compare.deck_view(export),
            deck_compare.deck_view(deck_compare.read_deck(self.folder)))
        if found:
            self.problems.append(
                f"The deck differs from the recorded run in {self.folder} ("
                + "; ".join(found) + "), so the results shown are of another model. On a "
                f"computer with Kratos, run `{self.record_command}` and commit the new run.")
        for path in sorted(self.folder.iterdir()):
            if path.name in inputs or path.name == ANSWER or path.suffix == ".mdpa":
                continue
            shutil.copy2(path, directory / path.name)
        answer = json.loads((self.folder / ANSWER).read_text(encoding="utf-8"))
        answer.update(directory=str(directory), inputs=inputs,
                      seconds=round(time.monotonic() - started, 1))
        return answer


def record(answer: dict, folder: Path) -> list[str]:
    """Keep the run `calculation.run` just answered with, in `folder` (emptied first):
    its deck, what Kratos wrote, and the answer. Returns the names kept."""
    directory = Path(answer["directory"])
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    kept = []
    for path in sorted(directory.iterdir()):
        if path.is_file():
            shutil.copy2(path, folder / path.name)
            kept.append(path.name)
    # Kratos' log names the run directory, a temporary folder of this computer's user.
    log = folder / calculation.LOG_NAME
    if log.exists():
        text = log.read_text(encoding="utf-8")
        for spelling in (str(directory), str(directory).replace("\\", "\\\\")):
            text = text.replace(spelling, "<run directory>")
        log.write_text(text, encoding="utf-8")
    saved = {key: value for key, value in answer.items() if key != "directory"}
    (folder / ANSWER).write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
    return kept


WARNINGS_ENV = "STYX_TUTORIAL_WARNINGS"
"""A file to add each deck warning to, one per line: `tools/gui_tutorial.py` reads it after
pytest, which captures what the test prints, and shows the warnings in the CI log."""


def note(message: str) -> None:
    """Add `message` to the file `WARNINGS_ENV` names, if it names one."""
    path = os.environ.get(WARNINGS_ENV)
    if path:
        with open(path, "a", encoding="utf-8") as warnings_file:
            warnings_file.write(" ".join(message.split()) + "\n")
