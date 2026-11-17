"""Which version of Styx this copy is: the GUI's title bar and About box, `kratos-cli
--version` and `run.sh --check` all say `describe()`, so a bug report names the same
thing whichever of them it was read from.

`VERSION` is set by hand before a release (CONTRIBUTING.md, "Releasing"), and the
release workflow refuses a tag that is not `v` + `VERSION`. A copy that is not exactly
that release says which commit it is too, after a `+`:

- `0.1.0`: the release, from its download or from a clone at its tag;
- `0.1.0+12.g2408259`: twelve commits after the tag `v0.1.0`, at commit 2408259;
- `0.1.0+g2408259`: commit 2408259 where the tag is not there to count from -- it has not
  been made yet, or the copy is a ZIP of a branch;
- `.dirty` at the end: a clone with changes that are not committed.

Only the standard library: the launcher reads this before the app's dependencies are
installed.
"""

from __future__ import annotations

import re
import subprocess
from functools import lru_cache
from pathlib import Path

VERSION = "0.1.1"
"""The number of the release this code is, or is on its way from."""

ROOT = Path(__file__).resolve().parents[1]

# A download has no .git to ask, so `git archive` writes the answers in instead
# (export-subst, .gitattributes): the release workflow's archives and GitHub's
# "Download ZIP" alike. In a clone they stay the placeholders written here.
ARCHIVE_DESCRIBE = "$Format:%(describe:tags=true,match=v[0-9]*)$"
ARCHIVE_COMMIT = "$Format:%h$"

_FROM_TAG = re.compile(r"v(?P<tag>.+)-(?P<ahead>\d+)-g(?P<commit>[0-9a-f]+)")
_COMMIT = re.compile(r"[0-9a-f]{4,40}")


def label(described: str) -> str:
    """`VERSION`, with what `git describe --tags --long --dirty --always` says about a
    copy added where the copy is not exactly that release. Git answers
    `v<tag>-<ahead>-g<commit>`, or only `<commit>` where it found no tag, and `-dirty`
    after either. A tag other than `v` + `VERSION` counts as none."""
    dirty = described.endswith("-dirty")
    described = described.removesuffix("-dirty")
    found = _FROM_TAG.fullmatch(described)
    if found and found["tag"] == VERSION:
        build = [] if found["ahead"] == "0" else [found["ahead"], "g" + found["commit"]]
    elif found:
        build = ["g" + found["commit"]]
    elif _COMMIT.fullmatch(described):
        build = ["g" + described]
    else:
        return VERSION
    if dirty:
        build.append("dirty")
    return VERSION + "+" + ".".join(build) if build else VERSION


def from_archive(described: str = ARCHIVE_DESCRIBE, commit: str = ARCHIVE_COMMIT) -> str | None:
    """`git describe`'s answer for a download, from what `git archive` wrote into it, or
    None in a clone, where nothing was written. The archive's describe is not `--long`:
    it says a bare `v0.1.0` at the tag itself, and nothing where there is no tag."""
    if commit.startswith("$"):
        return None
    if not described or described.startswith("$"):
        return commit
    return described if _FROM_TAG.fullmatch(described) else f"{described}-0-g{commit}"


def from_git(root: Path = ROOT) -> str | None:
    """`git describe`'s answer for a clone, or None where there is no git to ask: no
    .git folder, no git installed, or git refusing the folder."""
    if not (root / ".git").exists():
        return None
    try:
        done = subprocess.run(
            ["git", "describe", "--tags", "--long", "--dirty", "--always",
             "--match", f"v{VERSION}"],
            cwd=root, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


@lru_cache(maxsize=1)
def describe() -> str:
    """The version this copy says it is. Asked once per process: git takes a moment, and
    the copy does not change under a running server."""
    described = from_git() or from_archive()
    return label(described) if described else VERSION
