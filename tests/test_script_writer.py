"""`core.model.script_writer`: a project written as one Python file, which builds the
same project again (plan/active/cli-plan.md, MS).

The round trip is the contract: `scripting.load_project` of the written file equals the
project it was written from, for the seed, the empty site, the tracked test model, a
model in kN, a section and a deck case. The rest pins its shape -- grouped as a model
script is, one constructor per record, Kratos' own names as keys, literal values -- and
the drawn and imported solids, which point at .brep files outside the project and are
built again when those are gone (`session.with_solids`).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core import scripting, session
from core.geometry import cad_import, primitives
from core.model import script_writer, templates
from core.model.schemas import DimensionUpdate, Project, UnitsUpdate
from tests.models import excavation
from tests.test_deck import deck_dir  # noqa: F401  (the fixture)
from tests.test_importer import obj_text


def round_trip(project: Project, tmp_path: Path, name: str = "model.py") -> Project:
    path = tmp_path / name
    path.write_text(script_writer.script(project), encoding="utf-8")
    return scripting.load_project(path)


# ── The round trip ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("make", [
    templates.blank_project,
    lambda: templates.seed_project(simple=True),
    lambda: templates.seed_project(simple=False),
    excavation.excavation_project,
], ids=["blank", "seed", "seed-full", "test-model"])
def test_the_script_builds_the_project_it_was_written_from(make, tmp_path):
    project = make()

    assert round_trip(project, tmp_path) == project


def test_a_project_in_kn_comes_back_in_kn(tmp_path):
    project, _ = session.set_units(excavation.excavation_project(),
                                   UnitsUpdate(unit_system="kN"))

    assert round_trip(project, tmp_path) == project


def test_a_section_of_the_seed_comes_back_as_the_section(tmp_path):
    project, _ = session.set_dimension(templates.seed_project(),
                                       DimensionUpdate(dimension=2))

    assert round_trip(project, tmp_path) == project


def test_a_deck_case_is_written_as_the_deck_it_opens(deck_dir, tmp_path):  # noqa: F811
    from core.kratos import external_deck

    project = external_deck.deck_project(deck_dir, "dike.json", name="Dike")
    text = script_writer.script(project)

    assert "deck_project(" in text
    assert round_trip(project, tmp_path) == project


# ── Its shape ───────────────────────────────────────────────────────────────

@pytest.fixture
def text() -> str:
    return script_writer.script(excavation.excavation_project())


def test_it_is_python_and_grouped_as_a_model_script_is(text):
    ast.parse(text)
    headings = [line for line in text.splitlines() if line.startswith("# ── ")]
    order = [heading.split("── ", 1)[1].split(" ─")[0] for heading in headings]
    assert order[:4] == ["The site", "The soil", "The structures", "The loads"]
    assert "The mesh" in order and order[-1] == "The construction stages"


def test_one_constructor_per_record_with_kratos_names_as_keys(text):
    project = excavation.excavation_project()

    assert text.count("Material(") == len(project.materials)
    assert text.count("SoilLayer(") == len(project.layers)
    assert text.count("Stage(") == len(project.stages)
    assert '"YOUNG_MODULUS":' in text and '"POISSON_RATIO":' in text


def test_the_values_are_literal_and_defaults_are_left_out(text):
    project = excavation.excavation_project()

    assert repr(project.materials[0].variables["YOUNG_MODULUS"]) in text
    assert "active=True" not in text            # every record's default


def test_it_names_how_it_is_used(text):
    docstring = ast.get_docstring(ast.parse(text))

    assert "run " in docstring and "--out" in docstring and "kratos-cli" in docstring
    assert "def project() -> Project:" in text
    assert 'if __name__ == "__main__":' in text


# ── Where the file finds the checkout ───────────────────────────────────────

def run_as(text: str, file: Path) -> dict:
    """The file's module-level code, run as if it were saved at `file`."""
    namespace = {"__file__": str(file), "__name__": "model"}
    exec(compile(text, str(file), "exec"), namespace)
    return namespace


def test_a_file_in_the_checkout_finds_it_from_the_folders_above():
    """A model script kept in the repository works in every clone of it, so it holds no
    path of the computer it was written on."""
    root = script_writer.ROOT
    text = script_writer.script(templates.blank_project(), folder=root / "models")

    assert root.as_posix() not in text
    assert run_as(text, root / "models" / "pit" / "model.py")["ROOT"] == root


def test_a_file_outside_the_checkout_also_keeps_the_one_it_was_written_from(tmp_path):
    """Run by a Python outside the checkout, from a folder outside it, the folders above
    and the environment find nothing: the checkout it was written from is the last
    place to look."""
    text = script_writer.script(templates.blank_project(), folder=tmp_path)

    assert f'Path("{script_writer.ROOT.as_posix()}")' in text
    assert run_as(text, tmp_path / "model.py")["ROOT"] == script_writer.ROOT


def test_writing_a_file_into_the_checkout_leaves_its_path_out(monkeypatch, tmp_path):
    monkeypatch.setattr(script_writer, "ROOT", tmp_path)

    written = session.write_script(templates.blank_project(), tmp_path / "pit.py")

    text = written.read_text(encoding="utf-8")
    assert tmp_path.as_posix() not in text
    assert "Path(sys.prefix).resolve().parent]:" in text


def test_a_field_the_writer_has_no_heading_for_is_still_written(monkeypatch, tmp_path):
    """The writer walks the schema: a field it was never told about lands under
    "Other", and the round trip still holds."""
    monkeypatch.setattr(script_writer, "GROUPS", {"The site": ("domain",)})
    project = excavation.excavation_project()

    text = script_writer.script(project)
    assert "# ── Other" in text
    assert round_trip(project, tmp_path) == project


# ── Drawn and imported solids ───────────────────────────────────────────────

@pytest.fixture
def solids_here(tmp_path, monkeypatch):
    monkeypatch.setattr(primitives, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(cad_import, "DATA_DIR", tmp_path / "data")


def drawn(project: Project, recipe: dict) -> Project:
    from core import gmsh_worker

    built = gmsh_worker.run_here(gmsh_worker.create_job, json.dumps(recipe))
    return session.with_created_part(project, recipe, built)[0]


BOX = {"kind": "box", "origin": [2.0, -4.0, 0.0], "size": [3.0, 2.0, 20.0], "label": "Fill"}


def test_a_drawn_solid_round_trips_while_its_brep_is_there(solids_here, tmp_path):
    project = drawn(templates.blank_project(), BOX)

    assert round_trip(project, tmp_path) == project


def test_a_drawn_solid_whose_brep_is_gone_is_built_again_from_its_recipe(solids_here,
                                                                          tmp_path):
    project = drawn(templates.blank_project(), BOX)
    Path(project.custom_parts[0].source_file).unlink()

    again = round_trip(project, tmp_path)

    part, before = again.custom_parts[0], project.custom_parts[0]
    assert Path(part.source_file).is_file()
    assert part.model_dump(exclude={"source_file"}) == before.model_dump(exclude={"source_file"})


def test_an_imported_solid_whose_brep_is_gone_is_read_again_from_its_file(solids_here,
                                                                          tmp_path):
    from core import gmsh_worker

    source = tmp_path / "cube.obj"
    source.write_text(obj_text(), encoding="utf-8")
    built = gmsh_worker.run_here(gmsh_worker.import_job, str(source), ".obj")
    project, _ = session.with_imported_part(templates.blank_project(), source.name, built,
                                            source=source)
    assert project.custom_parts[0].imported_from == str(source.resolve())
    Path(project.custom_parts[0].source_file).unlink()

    part = round_trip(project, tmp_path).custom_parts[0]

    assert Path(part.source_file).is_file()
    assert part.bbox == pytest.approx(project.custom_parts[0].bbox)


def test_an_imported_solid_with_nothing_to_read_again_is_refused_by_name(solids_here,
                                                                         tmp_path):
    from core import gmsh_worker

    source = tmp_path / "cube.obj"
    source.write_text(obj_text(), encoding="utf-8")
    built = gmsh_worker.run_here(gmsh_worker.import_job, str(source), ".obj")
    project, part = session.with_imported_part(templates.blank_project(), "cube.obj", built)
    Path(part.source_file).unlink()

    with pytest.raises(scripting.ScriptError, match="cube.obj"):
        round_trip(project, tmp_path)
