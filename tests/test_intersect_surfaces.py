"""Two drawn soil surfaces intersected into their own parts and the overlap
(`session.intersection_plan`, `session.with_intersection`): what right-click > Intersect
with in the viewport does."""

from __future__ import annotations

import pytest

from core import session
from core.model import drafts, regions
from core.model.schemas import CustomPart, Domain, Project, Stage
from tests.test_soil_lines import edited, material

DOMAIN = Domain(x0=0.0, x1=10.0, z0=0.0, z1=1.0, y_top=10.0, y_bottom=0.0)


def square(x0: float, y0: float, size: float) -> list[tuple[float, float]]:
    return [(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)]


def surface(project: Project, key: str, outline, mat: str, label: str) -> dict:
    recipe = drafts.section_prism(project, outline)
    recipe.update(label=label, material=mat)
    return CustomPart(key=key, label=label, source="gui", recipe=recipe, mat=mat,
                      source_file=f"{key}.brep").model_dump()


def two_surfaces(a=square(0.0, 0.0, 4.0), b=square(2.0, 2.0, 4.0), **fields) -> Project:
    empty = Project(name="Intersect", dimension=2, domain=DOMAIN,
                    materials=[material("sand"), material("clay")], layers=[])
    return edited(empty, custom_parts=[surface(empty, "drawn_0", a, "sand", "Sand"),
                                       surface(empty, "drawn_1", b, "clay", "Clay")],
                  **fields)


def fake_build(recipe: dict) -> dict:
    """What `gmsh_worker.create_job` answers, without gmsh: the box of the outline."""
    xs = [v[0] for v in recipe["vertices"]]
    ys = [v[1] for v in recipe["vertices"]]
    return {"brep_path": "piece.brep", "bbox": [min(xs), min(ys), 0.0, max(xs), max(ys), 1.0]}


def intersected(project: Project, key="drawn_0", other="drawn_1") -> Project:
    plan = session.intersection_plan(project, key, other)
    return session.with_intersection(project, plan, [fake_build(recipe) for recipe, _ in plan])


def area(part: CustomPart) -> float:
    section = part.section_outline()
    assert section is not None
    return abs(regions._area(section[0]))


def parts(project: Project) -> dict[str, tuple[str, str | None, float]]:
    return {part.key: (part.label, part.mat, pytest.approx(area(part)))
            for part in project.custom_parts}


def test_two_overlapping_surfaces_become_their_own_parts_and_the_overlap():
    after = intersected(two_surfaces())
    assert parts(after) == {
        "drawn_0": ("Sand", "sand", 12.0),
        "drawn_1": ("Clay", "clay", 12.0),
        "drawn_2": ("Sand & Clay", "sand", 4.0),
    }


def test_the_overlap_takes_the_material_of_the_surface_that_was_clicked():
    after = intersected(two_surfaces(), key="drawn_1", other="drawn_0")
    assert parts(after)["drawn_2"] == ("Clay & Sand", "clay", 4.0)


def test_a_lens_inside_a_surface_keeps_its_key_and_takes_the_outer_material():
    after = intersected(two_surfaces(a=square(0.0, 0.0, 6.0), b=square(2.0, 2.0, 2.0)))
    lens = next(part for part in after.custom_parts if part.key == "drawn_1")
    assert (lens.label, lens.mat, area(lens)) == ("Sand & Clay", "sand", pytest.approx(4.0))
    rest = [part for part in after.custom_parts if part.mat == "sand" and part.key != "drawn_1"]
    assert "drawn_0" in [part.key for part in rest]
    assert sum(area(part) for part in rest) == pytest.approx(32.0)
    assert len(rest) >= 2           # the ring around the lens, in pieces with no hole


def test_a_surface_inside_the_one_clicked_on_keeps_its_shape():
    after = intersected(two_surfaces(a=square(2.0, 2.0, 2.0), b=square(0.0, 0.0, 6.0)))
    inner = next(part for part in after.custom_parts if part.key == "drawn_0")
    assert (inner.label, inner.mat, area(inner)) == ("Sand", "sand", pytest.approx(4.0))
    outer = [part for part in after.custom_parts if part.mat == "clay"]
    assert sum(area(part) for part in outer) == pytest.approx(32.0)


def test_a_new_piece_is_in_the_stages_the_surface_it_came_from_is_in():
    project = two_surfaces(stages=[
        Stage(id="first", name="First", activate=["drawn_0"]).model_dump(),
        Stage(id="second", name="Second", parent="first", deactivate=["drawn_1"]).model_dump()])
    first, second = intersected(project).stages
    assert first.activate == ["drawn_0", "drawn_2"]
    assert second.deactivate == ["drawn_1"]


def test_a_new_piece_takes_the_water_and_the_mesh_size_of_its_surface():
    project = two_surfaces(soil_water={"drawn_0": "interpolate"})
    project = project.model_copy(update={"mesh": project.mesh.model_copy(
        update={"body_sizes": {"drawn_0": 0.25}})})
    after = intersected(project)
    assert after.soil_water.get("drawn_2") == project.soil_water["drawn_0"]
    assert after.mesh.body_sizes.get("drawn_2") == 0.25


@pytest.mark.parametrize("a, b, refused", [
    (square(0.0, 0.0, 4.0), square(4.0, 0.0, 4.0), "do not overlap"),
    (square(0.0, 0.0, 4.0), square(5.0, 5.0, 2.0), "do not overlap"),
])
def test_surfaces_that_do_not_overlap_are_refused(a, b, refused):
    with pytest.raises(session.EditRefused, match=refused):
        session.intersection_plan(two_surfaces(a=a, b=b), "drawn_0", "drawn_1")


def test_a_surface_cannot_be_intersected_with_itself_or_a_part_that_is_not_soil():
    project = two_surfaces()
    with pytest.raises(session.EditRefused, match="itself"):
        session.intersection_plan(project, "drawn_0", "drawn_0")
    with pytest.raises(session.UnknownPart):
        session.intersection_plan(project, "drawn_0", "nothing")
