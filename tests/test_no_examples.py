"""The repository carries no example case: no model, test, fixture, comment or document
that belongs to one.

The example cases and their reference decks live outside the repository, on the machine
that has them. Nothing tracked may name them or reach for them, so a clone is complete
without them and nothing quietly skips because they are absent. This test reads every
tracked text file and every tracked path.

The words are assembled rather than written out, so this file does not trip itself.
"""

from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

_CASES = ["c" + "row", "eem" + "dijk", "simple" + "_embankment", "dike" + "_with_sheet_pile"]
FORBIDDEN = re.compile(
    r"(?<![a-z])(" + "|".join(_CASES) + r")(?![a-z])"   # the case names, not "crowd"
    + r"|(?<![a-z_])" + "exam" + r"ples[/\\]"           # a path into the examples folder
    + r"|[\"']" + "exam" + r"ples[\"']",                # ... or one joined from parts
    re.IGNORECASE)

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".gz", ".zip", ".woff", ".woff2",
                 ".ttf", ".brep", ".pdf"}


def tracked_files() -> list[str]:
    """What the next commit would hold: tracked files still on disk, and new files git
    does not ignore."""
    try:
        listed = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as failure:
        pytest.skip(f"not a git checkout: {failure}")
    names = dict.fromkeys(name for name in listed.decode("utf-8").split("\0") if name)
    return [name for name in names if (ROOT / name).is_file()]


def offending_lines(text: str) -> list[str]:
    return [f"{number}: {line.strip()[:120]}"
            for number, line in enumerate(text.splitlines(), start=1)
            if FORBIDDEN.search(line)]


def test_the_pattern_finds_the_cases_and_leaves_ordinary_words_alone():
    assert FORBIDDEN.search("from core import " + _CASES[0])
    assert FORBIDDEN.search(_CASES[0].upper() + " excavation wall")
    assert FORBIDDEN.search("tests/fixtures/" + _CASES[0] + "_run/manifest.json")
    assert FORBIDDEN.search("run app/" + _CASES[1] + ".py")
    assert FORBIDDEN.search("ROOT / \"exam" + "ples\" / \"deck.mdpa\"")
    assert FORBIDDEN.search("see exam" + "ples/model.py")
    assert not FORBIDDEN.search("Where they crowd, only the nearest is drawn")
    assert not FORBIDDEN.search("a worked example, as the examples in the README show")


def test_no_tracked_path_names_an_example_case():
    named = [name for name in tracked_files() if FORBIDDEN.search(name)]
    assert not named, "tracked paths that belong to an example case:\n  " + "\n  ".join(named)


def test_no_tracked_file_mentions_an_example_case():
    found = {}
    for name in tracked_files():
        path = ROOT / name
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lines = offending_lines(text)
        if lines:
            found[name] = lines
    report = "\n".join(f"{name}\n    " + "\n    ".join(lines[:5])
                       + (f"\n    ... {len(lines) - 5} more" if len(lines) > 5 else "")
                       for name, lines in sorted(found.items()))
    assert not found, f"{len(found)} tracked files mention an example case:\n{report}"
