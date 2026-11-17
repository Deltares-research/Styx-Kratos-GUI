"""Every model a user can open, meshed and exported, in both element orders (alpha 2.2).

The models: the test model staged and unstaged, both seed projects, the test model
translated into the solid model, and the saved project files committed under
`tests/fixtures/projects/`. Each goes through the same export the Calculate button runs,
coarse, and must

* pass every structural rule (`check_deck`), and
* warn about nothing but what is expected of that model.

A warning outside the allow-list fails: a new one is either a defect or a deliberate
change that belongs in the list with its reason.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core.geometry import solid_model
from core.kratos import writer
from core.model.schemas import MeshRequest, Project
from core.model.templates import seed_project
from tests.models import excavation
from tests.pipeline.deck_invariants import check_deck

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "projects"

ALLOWED_WARNINGS = [
    # Whatever a property set left out and the export filled in, named.
    r"^Derived where a property set left them out",
    # A design limit Kratos has no property for (every_field_2d_v1 carries one).
    r"^tendon .* carries a tension or compression limit",
]

ALLOWED_3D_WARNINGS = [
    # What the solid model cannot carry yet, each named in the export (core/kratos/writer.py).
    r"^interfaces are plane-strain only and none was written into this 3D deck",
    r"^a normal load is plane-strain only and none was written into this 3D deck",
    r"^the wall panels are written as linear shells inside a quadratic soil mesh",
    # Kratos cannot carry a shell's or a 3D beam's forces into the next stage.
    r"^wall panel\(s\) .* stay in the model from one stage to the next",
    r"^member\(s\) .* stay in the model from one stage to the next",
]

ALLOWED_SAVED_WARNINGS = [
    # A project saved before water pressure conditions existed opens with none
    # (`Project.boundary_conditions`), so the water level it carries fixes nothing.
    r"^the water level \(.*\) fixes no pressure by itself",
    # ... and a coupled soil in it is said to need one.
    r"^no water pressure condition is set, so nothing fixes the water pressure, and .* "
    r"couples it",
    # A water load saved when the deck pressed to the left of the drawn line, as the
    # staged excavation's loads were drawn then; it presses to the right now, as its
    # arrows always showed, and the export says the line is the wrong way round.
    r"^normal load 'WaterLoad_Stage\d' pulls on the soil instead of pressing on it",
]


def _solid_excavation() -> Project:
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as client:
        try:
            client.put("/api/project",
                       json=excavation.excavation_project(staged=True).model_dump(mode="json"))
            assert client.patch("/api/project/dimension", json={"dimension": 3}).status_code == 200
            return Project.model_validate(client.get("/api/project").json())
        finally:
            client.post("/api/project/reset")


def _saved(path: Path):
    return lambda: Project.model_validate(json.loads(path.read_text(encoding="utf-8")))


MODELS = {
    "excavation-staged": lambda: excavation.excavation_project(staged=True),
    "excavation-unstaged": lambda: excavation.excavation_project(staged=False),
    "seed": lambda: seed_project(),
    "seed-simple": lambda: seed_project(simple=True),
    "excavation-solid": _solid_excavation,
    **{f"saved:{p.stem}": _saved(p) for p in sorted(FIXTURES.glob("*.json"))},
}
SIZES = {2: 8.0, 3: 12.0}


@pytest.mark.parametrize("order", [1, 2])
@pytest.mark.parametrize("name", sorted(MODELS))
def test_every_model_exports_a_sound_deck(name, order):
    project = MODELS[name]()
    settings = MeshRequest(element_size=SIZES[project.dimension], order=order)
    with solid_model.session():
        export = writer.export_project(project, settings)

    assert check_deck(export) == []
    allowed = (ALLOWED_WARNINGS + (ALLOWED_3D_WARNINGS if project.dimension == 3 else [])
               + (ALLOWED_SAVED_WARNINGS if name.startswith("saved:") else []))
    unexpected = [w for w in export["warnings"]
                  if not any(re.search(pattern, w) for pattern in allowed)]
    assert unexpected == []
    assert len(export["nodes"]) > 0 and len(export["elements"]) > 0


def test_the_sweep_covers_both_dimensions():
    dimensions = {MODELS[name]().dimension for name in MODELS}
    assert dimensions == {2, 3}
