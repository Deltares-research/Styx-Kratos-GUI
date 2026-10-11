"""Running a Python file to build the model -- the command line's `run <file.py>`.

Every failure here is read by whoever typed the command, with no stack trace on screen,
so the messages are asserted as carefully as the successes.
"""

import pathlib
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
    """What lets a model script be run as it stands, off a builder named for what it
    builds -- `tests/models/excavation.py` has `excavation_project()`."""
    path = write(tmp_path, SEED + """
    def pit_project():
        p = seed_project()
        p.name = "from pit_project()"
        return p
    """)
    assert script.load_project(path).name == "from pit_project()"


def test_the_test_model_runs_as_a_script(tmp_path):
    """The model the tests build is a script the GUI can open, by the same path a user
    types:

        run tests/models/excavation.py
    """
    loaded = script.load_project(pathlib.Path(__file__).parent / "models" / "excavation.py")
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
    environment does not have -- a script written for STEM, say, imports its
    MiscellaneousTools, which this repo deliberately does not depend on
    (plan/outdated/stem-geometry-generator-feasibility.md)."""
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
    """`run models/pit.py`, typed the way the path reads in the project.

    The server runs from `server/`, so a path relative to that was once the only one
    that resolved -- which made the natural way to name a model script the wrong one,
    and `../models/...` the right one. A model lives in the project, not in the
    server's own directory, so the root is searched as well.
    """
    root = tmp_path
    (root / "server").mkdir()
    (root / "models").mkdir()
    (root / "models" / "pit.py").write_text(_SCRIPT, encoding="utf-8")
    monkeypatch.chdir(root / "server")

    project = script.load_project("models/pit.py")
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


# ── Errors a script author can act on (plan Task 1.3) ───────────────────────

def test_a_syntax_error_names_the_file_and_the_line(tmp_path):
    path = write(tmp_path, """
    from app.seed import seed_project
    PROJECT = seed_project(
    PROJECT.name = "never parsed"
    """)
    with pytest.raises(script.ScriptError) as error:
        script.load_project(path)
    assert "model.py" in str(error.value)
    assert "line 3" in str(error.value), str(error.value)


def test_a_runtime_error_names_the_line_of_the_script_it_came_from(tmp_path):
    path = write(tmp_path, SEED + """
    PROJECT = seed_project()
    depth = PROJECT.layers[99]
    """)
    with pytest.raises(script.ScriptError) as error:
        script.load_project(path)
    message = str(error.value)
    assert "IndexError" in message
    line = textwrap.dedent(path.read_text(encoding="utf-8")).splitlines().index(
        "depth = PROJECT.layers[99]") + 1
    assert f"line {line}" in message, message


def test_a_script_that_exits_is_an_error_not_the_end_of_the_server(tmp_path):
    """`sys.exit()` raises SystemExit, which no `except Exception` catches. A script that
    calls it at the top level -- or parses arguments with argparse outside a __main__
    guard -- must not take its exit out on the server."""
    path = write(tmp_path, """
    import sys
    sys.exit("usage: model.py --out DIR")
    """)
    with pytest.raises(script.ScriptError, match="exited.*usage: model.py"):
        script.load_project(path)


def test_argparse_outside_a_main_guard_is_reported_not_raised(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["uvicorn", "app.main:app"])
    path = write(tmp_path, """
    import argparse
    argparse.ArgumentParser().parse_args()
    """)
    with pytest.raises(script.ScriptError, match="exited"):
        script.load_project(path)


def test_a_builder_that_returns_something_else_says_what_it_returned(tmp_path):
    path = write(tmp_path, """
    def project():
        return {"name": "a dict, not a Project"}
    """)
    with pytest.raises(script.ScriptError, match=r"project\(\) returned a dict, not a Project"):
        script.load_project(path)


def test_a_project_variable_of_the_wrong_type_says_so(tmp_path):
    path = write(tmp_path, """
    PROJECT = "a pit"
    """)
    with pytest.raises(script.ScriptError, match="PROJECT is a str, not a Project"):
        script.load_project(path)


def test_project_variable_wins_over_project_function_wins_over_named_builder(tmp_path):
    common = SEED + """
    def named(label):
        p = seed_project()
        p.name = label
        return p
    """
    every = write(tmp_path, common + """
    PROJECT = named("variable")
    def project():
        raise AssertionError("not called when PROJECT is there")
    def site_project():
        raise AssertionError("not called when PROJECT is there")
    """, name="every.py")
    assert script.load_project(every).name == "variable"

    two = write(tmp_path, common + """
    def site_project():
        return named("named builder")
    def project():
        return named("project()")
    """, name="two.py")
    assert script.load_project(two).name == "project()"


def test_the_script_does_not_run_as_main(tmp_path):
    path = write(tmp_path, SEED + """
    PROJECT = seed_project()
    PROJECT.name = __name__
    """)
    assert script.load_project(path).name != "__main__"


# ── Scripts that come with helpers ──────────────────────────────────────────

def test_a_helper_module_beside_the_script_can_be_imported(tmp_path):
    """Not "needs the Python package 'site_layers', which is not installed" -- the
    package is right there, beside the script that imports it."""
    (tmp_path / "site_layers.py").write_text("DEPTH = -12.5\n", encoding="utf-8")
    path = write(tmp_path, SEED + """
    import site_layers
    PROJECT = seed_project()
    PROJECT.name = f"floor at {site_layers.DEPTH}"
    """)
    assert script.load_project(path).name == "floor at -12.5"


def test_an_edited_helper_is_read_again_on_the_next_run(tmp_path):
    """The point of `run` is to edit and look again; a helper cached from the first run
    would show the old model with no sign that it is old."""
    helper = tmp_path / "site_layers.py"
    helper.write_text("DEPTH = -12.5\n", encoding="utf-8")
    path = write(tmp_path, SEED + """
    import site_layers
    PROJECT = seed_project()
    PROJECT.name = f"floor at {site_layers.DEPTH}"
    """)
    script.load_project(path)
    helper.write_text("DEPTH = -20.0\n", encoding="utf-8")
    assert script.load_project(path).name == "floor at -20.0"


def test_running_a_script_writes_nothing_beside_it(tmp_path):
    (tmp_path / "site_layers.py").write_text("DEPTH = -12.5\n", encoding="utf-8")
    path = write(tmp_path, SEED + """
    import site_layers
    PROJECT = seed_project()
    """)
    script.load_project(path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["model.py", "site_layers.py"]


def test_installed_packages_stay_imported_when_the_venv_is_beside_the_script(
        tmp_path, monkeypatch):
    """server/.venv-* sits beside a script kept in server/: a package installed there and
    first imported by the script is not a helper, and re-importing a C extension breaks."""
    venv = tmp_path / ".venv"
    (venv / "pkgs").mkdir(parents=True)
    (venv / "pkgs" / "installed_thing.py").write_text("X = 1\n", encoding="utf-8")
    monkeypatch.setattr("sys.prefix", str(venv))
    monkeypatch.syspath_prepend(str(venv / "pkgs"))
    path = write(tmp_path, SEED + """
    import installed_thing
    PROJECT = seed_project()
    """)
    import sys
    try:
        script.load_project(path)
        assert "installed_thing" in sys.modules
    finally:
        sys.modules.pop("installed_thing", None)


def test_running_a_script_leaves_the_import_path_as_it_found_it(tmp_path):
    import sys
    before = list(sys.path)
    path = write(tmp_path, SEED + """
    PROJECT = seed_project()
    """)
    script.load_project(path)
    with pytest.raises(script.ScriptError):
        script.load_project(write(tmp_path, "raise RuntimeError('x')\n", name="bad.py"))
    assert sys.path == before


# ── Through the API ─────────────────────────────────────────────────────────

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
        c.post("/api/project/new")


def test_a_script_that_exits_is_a_400_and_the_server_keeps_serving(client, tmp_path):
    path = write(tmp_path, "import sys\nsys.exit(2)\n")
    response = client.post("/api/project/script", json={"path": str(path)})
    assert response.status_code == 400
    assert "exited" in response.json()["detail"]
    assert client.get("/api/health").status_code == 200


def test_a_syntax_error_reaches_the_command_log_with_its_line(client, tmp_path):
    path = write(tmp_path, "PROJECT = (\n")
    response = client.post("/api/project/script", json={"path": str(path)})
    assert response.status_code == 400
    assert "line 1" in response.json()["detail"]
