"""A model that is a Kratos deck already: shown as its own mesh, run as its own files.

A model script usually builds its case out of the parametric `Project`, which is then
exported. That is the right way round for a model the schema can say, and the wrong
one for a case like a long-running dike analysis: twenty stages, three material sets swapped between them, phreatic multi-lines,
a crane load that comes and goes, and a constitutive-law switch -- written, run and
validated as a deck, and nothing the layers-and-boreholes schema can express. Rebuilding
it would be a second model of the same dike, checked against nothing.

So a deck case script hands back a project that *points at* the deck::

    from core.kratos.external_deck import deck_project

    def dike_project():
        return deck_project(HERE, "dike.json", name="Dike section")

and `run <file.py>` opens it like any other model. What differs is downstream:

*   there is nothing to mesh -- the deck's own mesh comes back with the project
    (`preview`), and the command line shows it, parts and all;
*   Calculate copies the deck into a run directory (`stage`) and runs it as it is,
    instead of exporting one.

The deck is read where it is, never copied into the project: a case directory is the
deck's home, and its author keeps editing it there. Only the files its parameters name
are taken into a run -- a case directory also carries READMEs, pictures and the results
of runs made elsewhere, and none of that belongs beside a new one.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path, PurePath

from core.kratos import deck_files, mdpa_reader, node_parts
from core.model.schemas import Deck, Domain, Phase, Project
from core.model.templates import blank_project


class DeckError(ValueError):
    """The deck cannot be opened. Read by whoever typed `run`, so it names the file."""


MDPA_MODELER = "ImportMDPAModeler"
"""The modeler a multi-stage deck reads its mesh with (`stage_preprocess.modelers`).
Matched by suffix, because the registry path in front of it is spelled more than one
way across Kratos versions."""


# ── Opening one ─────────────────────────────────────────────────────────────

def deck_project(directory: str | Path, parameters: str = deck_files.PARAMETERS_NAME,
                 name: str | None = None) -> Project:
    """The project a deck case opens as.

    The empty site `templates.blank_project` is, carrying the deck -- with the dimension
    and the extent taken from the mesh, so that a plane-strain deck opens in 2D and
    the view frames the dike rather than a default 20 m site. Every file the deck
    names is checked here, so a broken case fails when it is opened, by name, rather
    than three minutes into a run.
    """
    source = Deck(directory=str(Path(directory).expanduser().resolve()),
                  parameters=parameters)
    missing = [file for file in input_files(source) if not _path(source, file).is_file()]
    if missing:
        raise DeckError(f"the deck in {source.directory} names "
                        f"{', '.join(missing)}, which "
                        f"{'is' if len(missing) == 1 else 'are'} not there")

    model = _mesh(source)
    x0, y0, _z0, x1, y1, _z1 = model.bbox
    settings = _parameters(source)
    source = source.model_copy(update={"parts": stageable_parts(settings)})
    blank = blank_project()
    return Project.model_validate(blank.model_dump() | {
        "name": name or deck_name(source),
        "dimension": model.dimension,
        "section_offset": None,
        "domain": Domain(x0=x0, x1=max(x1, x0 + 1e-3), z0=blank.domain.z0,
                         z1=blank.domain.z1, y_top=max(y1, y0 + 1e-3),
                         y_bottom=y0).model_dump(),
        "deck": source.model_dump(),
        "phases": [phase.model_dump() for phase in phases(settings)],
    })


# ── What it is made of ──────────────────────────────────────────────────────

def input_files(deck: Deck) -> list[str]:
    """Every file the deck reads, by name: the parameters, the mesh, then each
    materials file in the order the stages first ask for it."""
    parameters = _parameters(deck)
    names = [deck.parameters]
    meshes: list[str] = []
    materials: list[str] = []
    for stage in _stages(parameters):
        for modeler in (stage.get("stage_preprocess") or {}).get("modelers") or []:
            if str(modeler.get("name", "")).endswith(MDPA_MODELER):
                meshes.append(modeler.get("Parameters", {}).get("input_filename", ""))
        solver = (stage.get("stage_settings") or {}).get("solver_settings") or {}
        imported = solver.get("model_import_settings") or {}
        if imported.get("input_type") == "mdpa":
            meshes.append(imported.get("input_filename", ""))
        materials.append((solver.get("material_import_settings") or {})
                         .get("materials_filename", ""))
    for mesh in meshes:
        if mesh and f"{mesh}.mdpa" not in names:
            names.append(f"{mesh}.mdpa")
    for material in materials:
        if material and material not in names:
            names.append(material)
    return names


def deck_name(deck: Deck) -> str:
    """The mesh file's stem: what a run directory is named after."""
    return Path(_mdpa_file(deck)).stem


def preview(deck: Deck) -> dict:
    """The mesh, drawable, with which parts every node is in -- exactly what
    `POST /api/import/mdpa` answers for the same file, so the client shows it the
    same way."""
    model = _mesh(deck)
    return {**model.to_dict(), "node_parts": node_parts.of_model(model)}


def stats(deck: Deck) -> dict:
    """What the command log says about the mesh a run was made from."""
    model = _mesh(deck)
    return {"nodes": len(model.nodes),
            "elements": sum(len(entity.entries) for entity in model.elements)}


# ── Its stages, as phases ───────────────────────────────────────────────────
#
# What lets the Phase explorer list a deck's own sequence. A stage says which parts it
# computes on (`problem_domain_sub_model_part_list`) and which it loads
# (`loads_process_list`); the difference between one stage and the next is exactly the
# diff a `Phase` stores. Read-only: the deck is what runs, so these are never exported
# (`core.session.DeckReadOnly`).

MODEL_PART_PREFIX = "PorousDomain."
COMPUTATIONAL = "porous_computational_model_part"
"""The whole active model, which every stage loads with gravity. Not a part a stage
builds or removes."""

K0_PROCESS = "apply_k0_procedure_process"
STAGE_NUMBER = re.compile(r"^\d+_")
SECONDS_PER_DAY = 86400.0


def stage_parts(stage: dict) -> list[str]:
    """The parts one stage has in it: those it computes on, then those it loads."""
    settings = stage.get("stage_settings") or {}
    names = list((settings.get("solver_settings") or {})
                 .get("problem_domain_sub_model_part_list") or [])
    for process in ((settings.get("processes") or {}).get("loads_process_list") or []):
        name = (process.get("Parameters") or {}).get("model_part_name")
        if isinstance(name, str):
            names.append(name)
    out: list[str] = []
    for name in names:
        name = name[len(MODEL_PART_PREFIX):] if name.startswith(MODEL_PART_PREFIX) else name
        if name and name != COMPUTATIONAL and name not in out:
            out.append(name)
    return out


def stageable_parts(parameters: dict) -> list[str]:
    """Every part some stage has in it, in the order the stages first name them."""
    out: list[str] = []
    for stage in _stages(parameters):
        out += [name for name in stage_parts(stage) if name not in out]
    return out


def phases(parameters: dict) -> list[Phase]:
    """One phase per stage, in run order, each starting from the one before.

    Phases resolve from "everything is there" (`core.model.phases.active_parts`), so the first
    one deactivates what its stage does not have; every later one stores only what
    changed. The calculation type is read where the deck says it: a K0 stage runs the
    K0 procedure process, and a null step is named as one -- the deck has no other
    marker for it.
    """
    order = ((parameters.get("orchestrator") or {}).get("settings") or {})         .get("execution_list") or list(parameters.get("stages") or {})
    stages = parameters.get("stages") or {}
    everything = stageable_parts(parameters)
    out: list[Phase] = []
    before = set(everything)
    for name in order:
        stage = stages.get(name)
        if not isinstance(stage, dict):
            continue
        now = stage_parts(stage)
        out.append(_phase(name, stage, out[-1].id if out else None,
                          activate=[key for key in everything
                                    if key in now and key not in before],
                          deactivate=[key for key in everything
                                      if key in before and key not in now]))
        before = set(now)
    return out


def _phase(name: str, stage: dict, parent: str | None, *, activate: list[str],
           deactivate: list[str]) -> Phase:
    settings = stage.get("stage_settings") or {}
    solver = settings.get("solver_settings") or {}
    problem = settings.get("problem_data") or {}
    title = STAGE_NUMBER.sub("", name).replace("_", " ") or name
    fields: dict = {"id": name, "name": title, "parent": parent,
                    "activate": activate, "deactivate": deactivate,
                    "calculation": _calculation(stage, title),
                    "reset_displacements": bool(solver.get("reset_displacements", False))}
    if isinstance(solver.get("max_iterations"), int) and solver["max_iterations"] > 0:
        fields["max_iterations"] = solver["max_iterations"]
    tolerance = solver.get("residual_relative_tolerance")
    if isinstance(tolerance, (int, float)) and tolerance > 0:
        fields["tolerated_error"] = float(tolerance)
    start, end = problem.get("start_time"), problem.get("end_time")
    if isinstance(start, (int, float)) and isinstance(end, (int, float)) and end > start:
        # Seconds in the deck, days in a phase. The K0 and null steps span one
        # second of pseudo-time, which is no time at all to anyone reading days.
        fields["time_interval"] = round((end - start) / SECONDS_PER_DAY, 3)
    return Phase(**fields)


def _calculation(stage: dict, title: str) -> str:
    processes = (stage.get("stage_settings") or {}).get("processes") or {}
    for group in processes.values():
        for process in group if isinstance(group, list) else []:
            if K0_PROCESS in str(process.get("python_module", "")):
                return "K0 procedure"
    return "Null step" if "null step" in title.lower() else "Plastic"


# ── Running it ──────────────────────────────────────────────────────────────

def stage(deck: Deck, directory: Path) -> list[str]:
    """Copy the deck into the run directory `directory`, ready for the runner.

    Two changes, both to the parameters and both about where things land rather than
    what is computed:

    *   it is written as `deck_files.PARAMETERS_NAME`, which is the name the runner is
        started with and the one `core.results.catalog` reads a run's stages from;
    *   each output process' `output_name` loses any directory in front of it. Kratos
        would write `gid_output/1_Initial_stage.post.res` into a subdirectory, and a
        run directory is flat -- `core.results.catalog.file_path` serves nothing else, on
        purpose.

    The original is never touched.
    """
    parameters = _flattened(_parameters(deck))
    written = []
    deck_files.write_text(directory / deck_files.PARAMETERS_NAME,
                     json.dumps(parameters, indent=4))
    written.append(deck_files.PARAMETERS_NAME)
    for name in input_files(deck)[1:]:
        shutil.copyfile(_path(deck, name), directory / name)
        written.append(name)
    # A deck this application exported says which unit system its numbers are in;
    # the run keeps the record, so its results are labelled in it. Kratos never reads it.
    units = _path(deck, deck_files.UNITS_NAME)
    if units.is_file():
        shutil.copyfile(units, directory / deck_files.UNITS_NAME)
        written.append(deck_files.UNITS_NAME)
    return written


def _flattened(parameters: dict) -> dict:
    out = copy.deepcopy(parameters)
    for stage_ in _stages(out):
        outputs = (stage_.get("stage_settings") or {}).get("output_processes") or {}
        for processes in outputs.values():
            for process in processes if isinstance(processes, list) else []:
                settings = process.get("Parameters") or {}
                if isinstance(settings.get("output_name"), str):
                    settings["output_name"] = PurePath(
                        settings["output_name"].replace("\\", "/")).name
    return out


# ── Reading it ──────────────────────────────────────────────────────────────

def _path(deck: Deck, name: str) -> Path:
    return Path(deck.directory) / name


def _parameters(deck: Deck) -> dict:
    path = _path(deck, deck.parameters)
    try:
        parameters = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as failure:
        raise DeckError(f"no deck parameters at {path}: {deck.parameters} is not "
                        f"in {deck.directory}") from failure
    except (OSError, ValueError) as failure:
        raise DeckError(f"{deck.parameters} could not be read: {failure}") from failure
    if not isinstance(parameters, dict) or not isinstance(parameters.get("stages"), dict):
        raise DeckError(f"{deck.parameters} is not a multi-stage Kratos deck: it has no "
                        f"\"stages\" to run")
    return parameters


def _stages(parameters: dict) -> list[dict]:
    """The stages in run order, falling back to file order when the orchestrator
    does not list them."""
    stages = parameters.get("stages") or {}
    order = ((parameters.get("orchestrator") or {}).get("settings") or {}) \
        .get("execution_list") or list(stages)
    return [stages[name] for name in order if isinstance(stages.get(name), dict)]


def _mdpa_file(deck: Deck) -> str:
    meshes = [name for name in input_files(deck) if name.endswith(".mdpa")]
    if not meshes:
        raise DeckError(f"{deck.parameters} reads no .mdpa: no stage imports a mesh")
    return meshes[0]


_meshes: dict[tuple, mdpa_reader.MdpaModel] = {}
"""Parsed meshes, by path and what the filesystem says about it -- a case's .mdpa is
megabytes, and opening, previewing and calculating it would otherwise parse it three
times over."""


def _mesh(deck: Deck) -> mdpa_reader.MdpaModel:
    path = _path(deck, _mdpa_file(deck))
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if key not in _meshes:
        _meshes.clear()
        try:
            _meshes[key] = mdpa_reader.import_mdpa(path.read_text(encoding="utf-8",
                                                                  errors="replace"))
        except mdpa_reader.ImportError_ as failure:
            raise DeckError(f"{path.name}: {failure}") from failure
    return _meshes[key]
