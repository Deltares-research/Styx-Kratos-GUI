"""Which version a copy of Styx says it is (`core/version.py`): a release, a clone some
commits after it, a clone with changes, and a download, which has no .git to ask."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from core import version
from core.version import VERSION, from_archive, from_git, label

ROOT = Path(__file__).resolve().parents[1]

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


# ── What git says, as a version ─────────────────────────────────────────────

def test_the_release_itself_is_the_bare_number():
    assert label(f"v{VERSION}-0-g2408259") == VERSION


def test_commits_after_the_tag_are_counted_and_named():
    assert label(f"v{VERSION}-12-g2408259") == f"{VERSION}+12.g2408259"


def test_changes_not_committed_are_said():
    assert label(f"v{VERSION}-0-g2408259-dirty") == f"{VERSION}+dirty"
    assert label(f"v{VERSION}-3-g2408259-dirty") == f"{VERSION}+3.g2408259.dirty"


def test_without_the_tag_the_commit_is_named():
    assert label("2408259") == f"{VERSION}+g2408259"
    assert label("2408259-dirty") == f"{VERSION}+g2408259.dirty"


def test_the_tag_of_another_version_does_not_count():
    """A tag the commits are counted from has to be this version's: after `VERSION` is
    raised for the next release, the old tag's count would say the wrong thing."""
    assert label("v0.0.1-5-g2408259") == f"{VERSION}+g2408259"


def test_a_pre_release_tag_is_read_whole():
    assert version._FROM_TAG.fullmatch("v1.2.0-rc.1-4-gabc1234")["tag"] == "1.2.0-rc.1"


def test_an_answer_git_would_not_give_is_the_bare_number():
    assert label("") == VERSION
    assert label("fatal: not a git repository") == VERSION


# ── A download ──────────────────────────────────────────────────────────────

def test_a_clone_has_nothing_written_in():
    assert from_archive() is None


def test_a_download_of_the_release_is_the_release():
    assert label(from_archive(f"v{VERSION}", "2408259")) == VERSION


def test_a_download_after_the_release_counts_from_it():
    assert label(from_archive(f"v{VERSION}-12-g2408259", "2408259")) == f"{VERSION}+12.g2408259"


def test_a_download_with_no_tag_names_its_commit():
    assert label(from_archive("", "2408259")) == f"{VERSION}+g2408259"


# ── Real git ────────────────────────────────────────────────────────────────

def git(folder: Path, *args: str) -> str:
    done = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.org",
                           *args],
                          cwd=folder, capture_output=True, text=True, check=True)
    return done.stdout.strip()


@pytest.fixture
def repository(tmp_path) -> Path:
    """A repository holding `core/version.py` and the `.gitattributes` line that has
    `git archive` write into it, with one commit."""
    folder = tmp_path / "styx"
    (folder / "core").mkdir(parents=True)
    shutil.copy(ROOT / "core" / "version.py", folder / "core" / "version.py")
    (folder / ".gitattributes").write_text("core/version.py export-subst\n", encoding="utf-8")
    git(folder, "init", "-q")
    git(folder, "add", ".")
    git(folder, "commit", "-q", "-m", "first")
    return folder


@needs_git
def test_a_clone_at_its_tag_and_after_it(repository):
    git(repository, "tag", "-a", f"v{VERSION}", "-m", "release")
    assert label(from_git(repository)) == VERSION

    (repository / "notes.txt").write_text("x", encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-q", "-m", "second")
    commit = git(repository, "rev-parse", "--short", "HEAD")
    assert label(from_git(repository)) == f"{VERSION}+1.g{commit}"

    (repository / "notes.txt").write_text("y", encoding="utf-8")
    assert label(from_git(repository)) == f"{VERSION}+1.g{commit}.dirty"


@needs_git
def test_a_clone_before_its_tag_is_made(repository):
    commit = git(repository, "rev-parse", "--short", "HEAD")
    assert label(from_git(repository)) == f"{VERSION}+g{commit}"


def test_a_folder_with_no_git_has_no_answer(tmp_path):
    assert from_git(tmp_path) is None


def archived_version(repository: Path, tmp_path: Path) -> str:
    """What `describe()` says in a download made by `git archive`, as the release
    workflow makes it."""
    archive = tmp_path / "styx.zip"
    git(repository, "archive", "--format=zip", "-o", str(archive), "HEAD")
    with zipfile.ZipFile(archive) as unpacked:
        unpacked.extract("core/version.py", tmp_path / "unpacked")
    spec = importlib.util.spec_from_file_location(
        "archived_version", tmp_path / "unpacked" / "core" / "version.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.describe()


@needs_git
def test_git_archive_writes_the_release_into_the_download(repository, tmp_path):
    git(repository, "tag", "-a", f"v{VERSION}", "-m", "release")
    assert archived_version(repository, tmp_path) == VERSION


@needs_git
def test_git_archive_of_a_branch_names_its_commit(repository, tmp_path):
    commit = git(repository, "rev-parse", "--short", "HEAD")
    assert archived_version(repository, tmp_path) == f"{VERSION}+g{commit}"


def test_this_checkout_says_a_version_of_its_own_number():
    assert version.describe().split("+")[0] == VERSION
