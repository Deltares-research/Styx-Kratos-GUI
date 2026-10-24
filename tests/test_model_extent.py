"""Where a structure is allowed to be: the model, not the layer block.

`Domain` is the block the soil layers fill. A drawn or imported part is not held
to it -- an embankment sits *above* `y_top`, and `solid_model.SECTION_PAD` already says so in
as many words: "the wall top and any drawn or imported part can legitimately stick out
of the declared domain".

The structure validators were checking against the domain all the same, so a load or a
sheet pile placed on a custom layer above ground was refused with "lies outside the
domain" even though it stood on model geometry. They check the *extent* now: the domain
grown to cover every custom part.

A part saved before its bounding box was recorded contributes nothing, so an old
project validates exactly as it used to.
"""

import pytest

from core.model.schemas import Project
from core.model.templates import seed_project


EMBANKMENT = {"key": "drawn_1", "label": "Embankment", "source": "gui",
              "source_file": "x.brep", "color": "#cccccc",
              "bbox": [0.0, 0.0, 0.0, 25.0, 4.0, 25.0]}


def project_with(**fields) -> dict:
    payload = seed_project(simple=True).model_dump()
    payload["custom_parts"] = [EMBANKMENT]
    payload.update(fields)
    return payload


def line_at(y: float) -> dict:
    return {"id": "load_1", "name": "LineLoad_1", "kind": "line",
            "x0": 4.0, "x1": 16.0, "y": y, "components": [0.0, -20.0]}


# ── The extent itself ───────────────────────────────────────────────────────

def test_the_extent_grows_to_cover_a_custom_part():
    project = Project.model_validate(project_with())

    assert project.extent().y_top == 4.0
    assert project.extent().y_bottom == project.domain.y_bottom


def test_the_extent_is_the_domain_when_nothing_sticks_out():
    project = Project.model_validate(seed_project(simple=True).model_dump())

    assert project.extent().model_dump() == project.domain.model_dump()


def test_a_part_with_no_recorded_box_leaves_the_extent_alone():
    """Projects saved before the box was stored still open and still validate."""
    older = dict(EMBANKMENT)
    older.pop("bbox")
    project = Project.model_validate(project_with(custom_parts=[older]))

    assert project.extent().model_dump() == project.domain.model_dump()


# ── What it lets the user build ─────────────────────────────────────────────

def test_a_load_on_a_custom_layer_above_ground_is_accepted():
    """The bug as reported: "Could not save load: line load lies outside the domain"."""
    Project.model_validate(project_with(loads=[line_at(2.0)]))


def test_a_load_above_everything_in_the_model_is_still_refused():
    """The check is relaxed, not removed: floating in the air is still an error."""
    with pytest.raises(Exception, match="outside the domain"):
        Project.model_validate(project_with(loads=[line_at(9.0)]))


def test_a_sheet_pile_reaching_up_into_a_custom_layer_is_accepted():
    Project.model_validate(project_with(
        beam_sections=[{"id": "az26", "name": "AZ 26", "E": 2.1e8, "nu": 0.3,
                        "area": 0.02, "inertia": 5e-4, "density": 7850.0}],
        beams=[{"id": "beam_1", "name": "Sheet pile 1", "kind": "beam",
                "section": "az26", "points": [[10.0, 3.0], [10.0, -8.0]]}],
    ))


def test_an_anchor_in_a_custom_layer_above_ground_is_accepted():
    Project.model_validate(project_with(
        beam_sections=[{"id": "az26", "name": "AZ 26", "E": 2.1e8, "nu": 0.3,
                        "area": 0.02, "inertia": 5e-4, "density": 7850.0}],
        beams=[{"id": "beam_1", "name": "Sheet pile 1", "kind": "beam",
                "section": "az26", "points": [[10.0, 3.0], [10.0, -8.0]]}],
        anchor_sections=[{"id": "strand", "name": "Strand", "E": 1.95e8,
                          "area": 0.0006, "density": 7850.0}],
        anchors=[{"id": "anchor_1", "name": "Anchor 1", "kind": "anchor",
                  "section": "strand", "head": [10.0, 2.0], "tail": [4.0, 1.0]}],
    ))


def test_a_point_load_on_a_custom_layer_above_ground_is_accepted():
    Project.model_validate(project_with(
        loads=[{"id": "load_1", "name": "PointLoad_1", "kind": "point",
                "x": 10.0, "y": 3.0, "components": [0.0, -30.0]}]))
