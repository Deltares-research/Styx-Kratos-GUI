"""`picture`: the pictures the GUI's camera button saves, from the terminal.

    geometry PROJECT   the model, as the Structures tab shows it
    mesh PROJECT       its mesh
    stage PROJECT      a stage as the Staged construction tab shows it, or every stage
    result RUN [FIELD] a result as the Results tab shows it, or every field and stage

The options have the words of `picture save` in the GUI's command box, and the same page
draws both (`cli.terminal.pictures`), so the pictures are the same. RUN and `--stage` read
as in `kratos-cli results`.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from cli.commands import results as run_commands
from cli.terminal import pictures
from cli.terminal.files import add_project, add_runs_dir, environment, read
from cli.terminal.output import Answer, CommandError
from core import session
from core.results import catalog, fields

FORMATS = ("png", "pdf", "svg")
VIEWS = ("front", "top", "side", "iso")
DEFAULT_WIDTH_CM = 16.0
MAX_WIDTH_CM = 60.0


def _formats(text: str) -> list[str]:
    names = [name.strip().lower() for name in text.split(",") if name.strip()]
    wrong = [name for name in names if name not in FORMATS]
    if wrong or not names:
        raise argparse.ArgumentTypeError(f"{text!r}: the formats are {', '.join(FORMATS)}, "
                                         "with a comma between them")
    return list(dict.fromkeys(names))


def _width(text: str) -> float:
    try:
        width = float(text)
    except ValueError:
        width = 0.0
    if not 0 < width <= MAX_WIDTH_CM:
        raise argparse.ArgumentTypeError(f"{text!r}: the width is in cm, more than 0 and at "
                                         f"most {MAX_WIDTH_CM:g}")
    return width


def register(commands, common: argparse.ArgumentParser) -> None:
    picture = commands.add_parser(
        "picture", parents=[common], help="save pictures of the model, its stages or its results",
        description="Save what the GUI's viewport shows as PNG, PDF or SVG, at 300 dpi. Draws "
                    "with Chrome or Edge, with no window, so the pictures are the GUI's own.")
    whats = picture.add_subparsers(dest="what", metavar="<what>", required=True)

    def what(name: str, handler, help: str) -> argparse.ArgumentParser:
        parser = whats.add_parser(name, parents=[common], help=help)
        parser.add_argument("--format", type=_formats, default=["png"], metavar="LIST",
                            help="png, pdf and svg, with a comma between them (default: png)")
        parser.add_argument("--width", type=_width, default=DEFAULT_WIDTH_CM, metavar="CM",
                            help=f"the picture's width (default: {DEFAULT_WIDTH_CM:g}); 300 dpi")
        parser.add_argument("--view", choices=VIEWS,
                            help="the camera, in a 3D model (default: as a new project opens)")
        parser.add_argument("--no-rulers", action="store_true", help="leave out the rulers (2D)")
        parser.add_argument("--no-axes", action="store_true", help="leave out the axes")
        parser.add_argument("--grid", action="store_true", help="draw the grid too")
        # Taken as typed, not as a Path, which would drop the separator that says "a folder".
        parser.add_argument("--out", metavar="PATH",
                            help="a file, or a folder to put them in, made when it ends in / "
                                 "(default: here)")
        parser.add_argument("--force", action="store_true", help="overwrite files already there")
        parser.set_defaults(handler=handler)
        return parser

    add_project(what("geometry", draw_geometry, "the model, as the Structures tab shows it"))
    add_project(what("mesh", draw_mesh, "the mesh, made first with the model's own settings"))
    stage = what("stage", draw_stage, "a stage as Staged construction shows it, or every stage")
    add_project(stage)
    stage.add_argument("--stage", metavar="STAGE", default="all",
                       help="its number, words of its name, or all (default: all)")

    result = what("result", draw_result, "a result as the Results tab shows it")
    result.add_argument("run", help="the run's id, its number in `results runs`, or a run directory")
    result.add_argument("field", nargs="?",
                        help="as `results fields` lists it, or all (default: what the Results "
                             "tab opens on)")
    result.add_argument("--stage", metavar="STAGE",
                        help="its number, words of its stage, or all (default: the last stage "
                             "that wrote results)")
    result.add_argument("--project", type=Path,
                        help="the model the run is of, to draw its loads and water over the result")
    result.add_argument("--no-legend", action="store_true", help="leave out the legend")
    result.add_argument("--csv", action="store_true", help="save the field values as CSV too")
    result.add_argument("--map", help="the colour map, as `results map` in the GUI")
    result.add_argument("--bands", type=int, help="the colour bands, as `results bands`")
    result.add_argument("--range", nargs=2, type=float, metavar=("MIN", "MAX"),
                        help="the legend's limits, as `results range`")
    result.add_argument("--deform", help="the deformation factor, or auto, as `results deform`")
    result.add_argument("--mesh", action="store_true", help="the element outlines, as `results mesh`")
    add_runs_dir(result)


def _asked(args: argparse.Namespace, **extra) -> dict:
    # Drawn in a section unless left out; a 3D view has none to draw.
    show: dict[str, bool] = {"rulers": not args.no_rulers}
    if args.no_axes:
        show["axes"] = False
    if args.grid:
        show["grid"] = True
    if getattr(args, "no_legend", False):
        show["legend"] = False
    return {"formats": args.format, "width": args.width, "show": show,
            "csv": getattr(args, "csv", False), "stage": None, "field": None, **extra}


def _save(args: argparse.Namespace, files: dict[str, bytes]) -> Answer:
    if not files:
        raise CommandError("There was nothing to draw: no stage or field matched.")
    folder = args.out is None or args.out.endswith(("/", "\\")) or Path(args.out).is_dir()
    if len(files) > 1 and not folder:
        raise CommandError(f"This makes {len(files)} files, and {args.out} is not a folder. "
                           "End --out with / to make one.")
    targets = {name: run_commands._target(args, name) for name in files}
    for name, target in targets.items():
        target.write_bytes(files[name])
    sizes = {target: target.stat().st_size for target in targets.values()}
    return Answer(data={"files": [{"file": str(target), "bytes": size}
                                  for target, size in sizes.items()]},
                  lines=[f"wrote {target} ({run_commands._size(size)})"
                         for target, size in sizes.items()])


def _project_json(args: argparse.Namespace) -> str:
    project = read(args)
    session.require_parametric(project, "drawn")
    return project.model_dump_json()


def draw_geometry(args: argparse.Namespace) -> Answer:
    job = {"mode": "structures", "view": args.view, "asked": _asked(args)}
    return _save(args, pictures.draw(job, _project_json(args)))


def draw_mesh(args: argparse.Namespace) -> Answer:
    job = {"mode": "mesh", "view": args.view, "asked": _asked(args)}
    return _save(args, pictures.draw(job, _project_json(args)))


def _project_stage(project, wanted: str) -> int:
    """A stage of the model by its number or words of its name, as `results` reads a run's."""
    stages = project.stages
    if not stages:
        raise CommandError("This model has no stages. `kratos-cli stages` makes them.")
    if wanted.strip().isdigit():
        number = int(wanted)
        if 1 <= number <= len(stages):
            return number
    else:
        words = re.sub(r"[^a-z0-9]+", " ", wanted.lower()).strip()
        for number, stage in enumerate(stages, start=1):
            if words and words in re.sub(r"[^a-z0-9]+", " ", stage.name.lower()):
                return number
    raise CommandError(f"No stage matches {wanted!r}. Its stages: "
                       + ", ".join(f"{i} {stage.name}" for i, stage in enumerate(stages, start=1))
                       + ".")


def draw_stage(args: argparse.Namespace) -> Answer:
    project_json = _project_json(args)
    every = args.stage.strip().lower() == "all"
    job = {"mode": "staged", "view": args.view,
           "stage": None if every else _project_stage(args.as_read, args.stage),
           "asked": _asked(args, stage="all" if every else None)}
    return _save(args, pictures.draw(job, project_json))


def _options(args: argparse.Namespace) -> list[str]:
    """The display options, in the words of the GUI's command box, which also checks them."""
    lines = []
    if args.map:
        lines.append(f"results map {args.map}")
    if args.bands is not None:
        lines.append(f"results bands {args.bands}")
    if args.range:
        lines.append(f"results range {args.range[0]} {args.range[1]}")
    if args.deform:
        lines.append(f"results deform {args.deform}")
    if args.mesh:
        lines.append("results mesh on")
    return lines


def _run_id(run: catalog.Run, given: str) -> str:
    """The id the server knows a run by. A directory elsewhere has to be named as a run is,
    and its folder becomes the runs root for this command."""
    if not isinstance(run, Path):
        return run
    if not catalog.RUN_NAME.match(run.name):
        raise CommandError(f"{given} is not named as a run is (<deck>_<date>_<time>), and the "
                           "server finds a run by that name. Rename the folder to draw it.")
    return run.name


def draw_result(args: argparse.Namespace) -> Answer:
    with environment(args):
        run = run_commands._run(args.run)
        every_stage = (args.stage or "").strip().lower() == "all"
        stage = None if every_stage else run_commands._stage(run, args.stage, args.run)
        every_field = (args.field or "").lower() == "all"
        if args.field and not every_field and stage is not None:
            _check_field(run, stage, args.field, args.run)
        if isinstance(run, Path):
            args.runs_dir = run.resolve().parent
        project_json = None
        if args.project is not None:
            args.project = Path(args.project)
            project_json = _project_json(args)

    lines = [f"results open {_run_id(run, args.run)}"]
    if stage is not None:
        lines.append(f"results stage {stage['index']}")
    if args.field and not every_field:
        lines.append(f"results field {args.field}")
    job = {"mode": "results", "view": args.view, "commands": lines + _options(args),
           "asked": _asked(args, stage="all" if every_stage else None,
                           field="all" if every_field else None)}
    with environment(args):
        return _save(args, pictures.draw(job, project_json))


def _check_field(run: catalog.Run, stage: dict, name: str, given: str) -> None:
    """Refused here, in the words of `results field`, before a browser is started for it."""
    try:
        catalog.stage_field(run, stage["index"], name, run_commands._first_location(
            run, stage["index"], name))
    except fields.UnknownField as failure:
        raise CommandError(f"{failure} `kratos-cli results fields {given}` lists what stage "
                           f"{stage['index']} ({stage['stage']}) has.") from None
