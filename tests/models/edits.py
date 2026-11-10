"""The test pit with a mesh size on each body an edit takes away, and the bodies the
GUI sends for its edits.

Shared by `tests/test_session.py` (the size rule, edit by edit) and
`tests/cli/test_edit_parity.py` (the command line against the GUI): both hold an edit
to what the GUI sends, so both read that from here.
"""

from __future__ import annotations

import copy

from core.model.schemas import Project

SIZED = {"sheetpile": 0.5, "strut": 0.5, "wall_contact": 0.5, "water_1": 0.5,
         "soil_L_mid__pit": 1.0, "soil_L_top__lift3": 1.0,
         "drawn_0": 0.5}
"""An element size on each body an edit takes away: the two front ends once disagreed
on what becomes of it."""


def sized(project: Project, **extra: float) -> Project:
    """`project` with the sizes of `SIZED` its bodies have, and `extra` as they are."""
    sizes = {key: size for key, size in SIZED.items() if key in project.part_keys()}
    mesh = project.mesh.model_copy(update={"body_sizes": {**sizes, **extra}})
    return project.model_copy(update={"mesh": mesh})


def without(records: list[dict], id: str) -> list[dict]:
    return [record for record in records if record["id"] != id]


def structures_sent(payload: dict, **lists: list[dict]) -> dict:
    """What a Structure-mode edit sends (`beams.js`, `anchors.js`, `interfaces.js`,
    `normal-loads.js` `save`/`remove`): the loads as they are, and the lists it
    changed."""
    return {"loads": payload["loads"], **lists}


def stack_without(layers: list[dict], id: str) -> list[dict]:
    """The layers after `SoilLayersDialog.remove`: the layer above takes the bottom of
    the one removed; for the top layer, the layer below takes its top."""
    layers = copy.deepcopy(layers)
    index = [layer["id"] for layer in layers].index(id)
    gone = layers.pop(index)
    if index > 0:
        layers[index - 1]["bottom"] = gone["bottom"]
    elif layers:
        layers[0]["top"] = gone["top"]
    return layers


def layers_window_sent(payload: dict, id: str) -> dict:
    """What the soil layers window's OK sends after its Delete
    (`soil-layers-dialog.js` `commit`): the stack and the material library."""
    return {"layers": stack_without(payload["layers"], id),
            "materials": payload["materials"]}
