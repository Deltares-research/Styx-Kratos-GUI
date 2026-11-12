"""The examples stay in the examples folder: no model, test, fixture, comment or document
outside it belongs to an example case.

The examples folder holds models for people to read and run: project files, model scripts
and command files for `kratos-cli` and its tutorial, one folder per model. Nothing else may
name them or reach for them, so no code or test depends on an example, and an example can
be changed or dropped without breaking the build. This test reads every tracked text file
and every tracked path.

The exceptions are the folder itself, `EXAMPLES` below, and the pages in `ALLOWED` that
point people at it.

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

EXAMPLES = "exam" + "ples/"
ALLOWED = ("README.md", "docs/CLI.md", "docs/developer/README.md",
           "docs/cli_tutorials/README.md",
           "docs/cli_tutorials/1_build_from_scratch.md",
           "docs/cli_tutorials/2_open_in_the_shell.md",
           "docs/cli_tutorials/3_run_the_python_script.md",
           "docs/cli_tutorials/" + _CASES[0].upper() + "_case.md",
           "docs/cli_tutorials/Muskat_case.md",
           "docs/superpowers/specs/2026-11-03-" + _CASES[0] + "-gui-tutorial-design.md",
           "docs/developer/code-map/GRAPH_REPORT.md",
           "docs/developer/code-map/GRAPH_TREE.html")
"""Besides the files under `EXAMPLES`, what may name them: the pages that point at them,
the design of the GUI tutorial built on the same case, and the generated code map, which
lists every tracked file and so names them too."""

KRATOS_REFERENCE = ("benchmarks/cases.py",
                    *(f"benchmarks/reference/{_CASES[0]}/{name}" for name in
                      ("README.md", "linear_elastic.csv", "mohr_coulomb.csv")),
                    "tests/models/" + _CASES[0] + ".py",
                    "tests/kratos/test_live_interfaces.py",
                    "tests/e2e/tutorials/" + _CASES[0] + ".py",
                    "tests/e2e/test_gui_tutorials.py")
"""What names Kratos' own validation case of the same name (its
`tests/` + _CASES[0] + `_validation`), not the example: the benchmark built after it, its
reference values, the tests that read Kratos' files, and the GUI tutorial that builds the
model of `tests/models/` from its numbers. None of them reads the example."""


def allowed(name: str) -> bool:
    return name.startswith(EXAMPLES) or name in ALLOWED or name in KRATOS_REFERENCE


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
    named = [name for name in tracked_files()
             if FORBIDDEN.search(name) and not allowed(name)]
    assert not named, "tracked paths that belong to an example case:\n  " + "\n  ".join(named)


def test_no_tracked_file_mentions_an_example_case():
    found = {}
    for name in tracked_files():
        path = ROOT / name
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file() or allowed(name):
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
