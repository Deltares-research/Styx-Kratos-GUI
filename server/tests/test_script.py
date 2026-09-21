"""Running a Python file to build the model -- the command line's `run <file.py>`.

Every failure here is read by whoever typed the command, with no stack trace on screen,
so the messages are asserted as carefully as the successes.
"""

import textwrap

import pytest

from app import script
from app.schemas import Project


def write(tmp_path, body: str, name: str = "model.py"):
    path = tmp_path / name
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


SEED = """
    from app.seed import seed_project
"""


def test_a_script_can_hand_back_a_project_variable(tmp_path):
    path = write(tmp_path, SEED + """
    PROJECT = seed_project()
    PROJECT.name = "from a variable"
    """)
    assert script.load_project(path).name == "from a variable"


def test_a_script_can_hand_back_a_builder_called_project(tmp_path):
    path = write(tmp_path, SEED + """
    def project():
        p = seed_project()
        p.name = "from project()"
        return p
    """)
    assert script.load_project(path).name == "from project()"


def test_a_builder_may_be_named_after_what_it_builds(tmp_path):
    """What lets `examples/crow/crow.py` be run as it stands, off its own `crow_project()`."""
    path = write(tmp_path, SEED + """
    def crow_project():
        p = seed_project()
        p.name = "from crow_project()"
        return p
    """)
    assert script.load_project(path).name == "from crow_project()"


def test_the_crow_example_runs(tmp_path):
    """The worked example has to be loadable by the thing that documents it -- and by
    the same path a user types, which is how the GUI opens it:

        run examples/crow/crow.py
    """
    from tests.crow_example import PATH
    loaded = script.load_project(PATH)
    assert isinstance(loaded, Project)
    assert len(loaded.excavation.levels) == 3
    assert loaded.beams and loaded.anchors


def test_main_is_not_called(tmp_path):
    """A script written for a shell writes files in `main()`. Looking at a model must
    not put anything on disk, so the entry point is never `main`."""
    path = write(tmp_path, SEED + """
    import pathlib
    PROJECT = seed_project()

    def main():
        pathlib.Path(__file__).with_name("side-effect.txt").write_text("ran")

    if __name__ == "__main__":
        main()
    """)
    script.load_project(path)
    assert not (tmp_path / "side-effect.txt").exists()


def test_a_missing_file_says_where_it_looked(tmp_path):
    with pytest.raises(script.ScriptError, match="no such file"):
        script.load_project(tmp_path / "nope.py")


def test_a_script_that_raises_reports_what_it_raised(tmp_path):
    path = write(tmp_path, """
    raise ValueError("the layers do not stack")
    """)
    with pytest.raises(script.ScriptError, match="the layers do not stack"):
        script.load_project(path)


def test_a_missing_package_is_named_rather_than_left_as_an_import_error(tmp_path):
    """The common way a script from elsewhere fails: written against a package this
    environment does not have. `demo_crow_excavation_wall.py` is exactly this -- it
    imports STEM's MiscellaneousTools, which this repo deliberately does not depend on
    (plan/stem-geometry-generator-feasibility.md)."""
    path = write(tmp_path, """
    from MiscellaneousTools.GeometryGenerator.build_mdpa import generate_mdpa
    """)
    with pytest.raises(script.ScriptError, match="MiscellaneousTools"):
        script.load_project(path)


def test_a_script_with_no_model_says_what_it_should_have_left_behind(tmp_path):
    path = write(tmp_path, """
    ANSWER = 42
    """)
    with pytest.raises(script.ScriptError, match="describes no model"):
        script.load_project(path)


def test_a_broken_builder_reports_its_own_failure(tmp_path):
    """Not "describes no model", which would send the reader looking for a naming
    mistake they did not make."""
    path = write(tmp_path, """
    def project():
        raise KeyError("bh1")
    """)
    with pytest.raises(script.ScriptError, match="project\\(\\) failed"):
        script.load_project(path)


def test_a_helper_that_takes_arguments_is_not_mistaken_for_the_entry_point(tmp_path):
    path = write(tmp_path, SEED + """
    def layered_project(depth):
        raise AssertionError("must not be called")

    PROJECT = seed_project()
    """)
    assert isinstance(script.load_project(path), Project)


_SCRIPT = textwrap.dedent("""
    from app.seed import seed_project
    PROJECT = seed_project()
    PROJECT.name = "From a script"
""")


def test_a_script_is_found_from_the_repository_root_too(tmp_path, monkeypatch):
    """`run examples/crow/crow.py`, typed the way the path reads in the project.

    The server runs from `server/`, so a path relative to that was once the only one
    that resolved -- which made the natural way to name a model script the wrong one,
    and `../examples/...` the right one. A model lives in the project, not in the
    server's own directory, so the root is searched as well.
    """
    root = tmp_path
    (root / "server").mkdir()
    (root / "examples").mkdir()
    (root / "examples" / "model.py").write_text(_SCRIPT, encoding="utf-8")
    monkeypatch.chdir(root / "server")

    project = script.load_project("examples/model.py")
    assert project.name == "From a script"


def test_the_server_s_own_directory_still_wins(tmp_path, monkeypatch):
    """Both roots are searched, nearest first: a file beside the server is the one a
    relative path names, as it always was."""
    root = tmp_path
    (root / "server").mkdir()
    (root / "server" / "model.py").write_text(_SCRIPT, encoding="utf-8")
    (root / "model.py").write_text(
        _SCRIPT.replace("From a script", "From the root"), encoding="utf-8")
    monkeypatch.chdir(root / "server")

    assert script.load_project("model.py").name == "From a script"
