"""The files a Kratos deck is made of, by name, and the one way to write them.

Here, in the deck's layer, rather than in `core.run.calculate`: calculate writes a deck
and runs it, but `core.kratos.deck` stages an existing deck under the same names,
`core.kratos.processes` writes the materials names into the parameters, and a module of
the deck may not reach up into the run. `calculate` imports these, so
`calculate.PARAMETERS_NAME` is the same object.
"""

from __future__ import annotations

from pathlib import Path

PARAMETERS_NAME = "ProjectParameters.json"
"""The parameters file: the name the runner is started with
(`core.run.calculate.COMMAND`), and the one `core.results.runs` reads a run's stages from."""

MATERIALS_NAME = "MaterialParameters.json"
"""The materials file every stage reads, named in the parameters'
`material_import_settings` (`core.kratos.processes`)."""

INITIAL_MATERIALS_NAME = "initial_materials.json"
"""What `1_Initial_stage` reads instead: the same file plus the two K0 variables
`apply_k0_procedure_process` needs, which only that stage runs. Written only when the
deck has a stage that reads it. The reference deck pairs its own two files exactly this
way (plan sec C4)."""

UNITS_NAME = "kratos_gui_units.json"
"""Beside the deck: the unit system its numbers are in, so its results are labelled in it
(`core.results.runs.run_unit_system`). Kratos never reads it."""


def write_text(path: Path, text: str) -> None:
    r"""Write `text` to `path` exactly as it is.

    `newline=""` is the whole of it, and it is not a style choice. `core.kratos.export` renders
    the deck with CRLF endings on purpose -- `export.LINE_END` -- so that what the
    exporter produces stays byte-comparable with the GiD-authored reference decks it is
    checked against. Writing that in Python's default text mode on Windows translates
    the "\n" of every one of those pairs a second time, and each line goes to disk as
    "\r\r\n".

    Kratos never complained, so seven real runs went green over a deck in that state.
    What did complain was this project: `core.kratos.mdpa_import` reads a file like that as
    blank-line-separated and used to fail outright on the first one, which meant the
    postprocessor could not open the .mdpa sitting beside the results it was reading.
    """
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
