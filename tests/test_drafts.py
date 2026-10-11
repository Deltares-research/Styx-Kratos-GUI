"""`core.model.drafts`: what a new record starts as, the way the GUI starts it.

The command line adds boreholes, layers, materials and soil volumes without the GUI's
dialogs, so what those dialogs fill in for a new one has to exist in Python as well. The
numbers are the GUI's own -- `frontend/js/property-sets.js` and `material-library.js` --
and `tests/test_draft_parity.py` holds the two to one document.
"""

from __future__ import annotations

import pytest

from core.model import drafts, units
from core.model.schemas import SOIL_LAW_PAIRS, Material
from core.model.templates import blank_project, seed_project


def test_a_new_soil_takes_the_linear_elastic_law_of_the_dimension():
    for dimension in (2, 3):
        law = drafts.SOIL_LAWS[dimension]
        assert SOIL_LAW_PAIRS[law][0] == dimension


def test_a_new_soil_is_a_loose_drained_sand_in_the_project_s_units():
    project = blank_project()

    material, notes = drafts.soil(project, "sand")

    assert isinstance(material, Material)
    assert material.constitutive_law == drafts.SOIL_LAWS[2]
    assert material.variables == drafts.SOIL_DEFAULTS_SI
    assert (material.id, material.name, material.color) == ("sand", "sand", drafts.SOIL_COLOR)
    assert notes == []


def test_a_new_soil_in_a_kn_project_is_stated_in_kn():
    project = blank_project().model_copy(update={"unit_system": "kN"})

    material, _ = drafts.soil(project, "sand")

    expected, _ = units.convert_variables(drafts.SOIL_DEFAULTS_SI, "SI", "kN")
    assert material.variables == expected
    assert material.variables["YOUNG_MODULUS"] == pytest.approx(1.0e4)


def test_a_soil_can_start_from_a_library_preset():
    material, _ = drafts.soil(blank_project(), "clay", preset="m3")

    preset = drafts.preset("m3")
    assert material.name == preset["name"]
    assert material.color == preset["color"]
    assert material.variables == preset["variables"]
    assert (material.r_inter, material.interface_permeability) == (0.5, "Impermeable")


def test_an_unknown_preset_says_which_there_are():
    with pytest.raises(drafts.DraftError, match="m1, m2, m3, m4, m5, m6"):
        drafts.soil(blank_project(), "clay", preset="m9")


def test_the_library_is_the_gui_s_six_soils_in_si():
    assert [p["id"] for p in drafts.LIBRARY] == ["m1", "m2", "m3", "m4", "m5", "m6"]
    assert drafts.preset("m6")["variables"]["YOUNG_MODULUS"] == 2.0e9


def test_a_new_borehole_copies_its_neighbour_as_the_gui_does():
    """`App.addBorehole`: 10 m past the last one, at its plan y, its ground and water
    levels -- and every layer's levels there -- copied from it, so the stack stays whole."""
    project = seed_project()
    last = project.boreholes[-1]

    borehole = drafts.borehole(project)

    assert (borehole.x, borehole.y) == (last.x + 10, last.y)
    assert (borehole.head, borehole.water) == (last.head, last.water)
    assert borehole.id == "bh4" and borehole.name == "BH-4"


def test_a_new_borehole_takes_what_it_is_given():
    borehole = drafts.borehole(seed_project(), id="north", x=5.0, y=7.0, head=1.0)

    assert (borehole.id, borehole.x, borehole.y, borehole.head) == ("north", 5.0, 7.0, 1.0)


def test_a_new_layer_goes_below_the_last_one():
    project = seed_project()

    layer = drafts.layer(project, "L3", "m1", thickness=5.0)

    assert layer.tops == project.layers[-1].bots
    assert layer.bots == {bh: top - 5.0 for bh, top in layer.tops.items()}
    assert layer.name == "L3"


def test_the_first_layer_starts_at_the_ground():
    project = blank_project()

    layer = drafts.layer(project, "L1", "m1", bottom=-6.0)

    assert layer.tops == {"bh1": project.boreholes[0].head}
    assert layer.bots == {"bh1": -6.0}


def test_a_section_outline_is_swept_across_the_whole_model():
    """`soil-volume-dialog.js` `prismFor`: a 2D body is an outline in the x-y plane,
    swept along z across the domain, so every section plane cuts it."""
    project = blank_project()
    domain = project.domain

    recipe = drafts.section_prism(project, [(0, 0), (3, 2), (6, 0)])

    assert recipe["kind"] == "polygon_extrude"
    assert recipe["vertices"] == [[0, 0, domain.z0], [3, 2, domain.z0], [6, 0, domain.z0]]
    assert recipe["extrusion"] == [0, 0, domain.z1 - domain.z0]


def test_a_free_id_is_the_first_number_not_taken():
    assert drafts.free_id(["bh1", "bh2", "bh4"], "bh") == "bh3"
    assert drafts.free_id([], "L") == "L1"
