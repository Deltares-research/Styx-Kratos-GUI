"""`results`: the runs on this machine, and what one of them left behind
(`core.results.catalog`, which the GUI's Results mode reads too).

    runs               the runs under the runs root, newest first, numbered
    show RUN           its stages, files and whether it finished
    stages RUN         its stages, and which wrote results
    files RUN          its files, with their sizes
    fields RUN         what a stage can show: the field menu
    field RUN NAME     one field of a stage: its range, or every value with --csv
    at RUN NODE        every field of a stage at one node
    members RUN        the members the run wrote curves for, and their quantities
    profile RUN MEMBER [QUANTITY]
                       one quantity along a wall or interface, stage by stage
    get RUN FILE       a copy of one of its files
    archive RUN        the whole run as one zip

RUN is a run's id, its number in `results runs` -- nobody is going to retype
`Pit_A_2026-10-12_09-14` -- or the path of a run directory anywhere, copied off another
machine or not (plan D12). `--stage` takes a stage's number or words of its stage
("first excavation"); without it, the last stage that wrote results is read, which is
where the GUI opens a run too. Each answer is the one the `/api/results` routes give for
the same question, and `--csv` writes the file the GUI's `results csv` and
`results plot csv` save (`cli.terminal.tables`).
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from cli.terminal import tables
from cli.terminal.files import add_runs_dir, environment
from cli.terminal.output import STDOUT, Answer, CommandError
from core.analysis import calculation
from core.results import catalog, fields


def register(commands, common: argparse.ArgumentParser) -> None:
    results = commands.add_parser("results", parents=[common],
                                  help="the runs, and what one left behind")
    actions = results.add_subparsers(dest="action", metavar="<action>", required=True)

    def action(name: str, handler, help: str, *, stage: bool = False, csv: bool = False):
        parser = actions.add_parser(name, parents=[common], help=help)
        if name != "runs":
            parser.add_argument("run", help="the run's id, its number in `results runs`, "
                                            "or a run directory")
        if stage:
            parser.add_argument("--stage", metavar="STAGE",
                                help="its number, or words of its stage (default: the "
                                     "last stage that wrote results)")
        if csv:
            parser.add_argument("--csv", nargs="?", const=STDOUT, metavar="FILE",
                                help="the table as CSV, the file the GUI saves: on stdout, "
                                     "or into FILE")
        add_runs_dir(parser)
        parser.set_defaults(handler=handler)
        return parser

    action("runs", list_runs, "the runs, newest first")
    action("show", show_run, "a run's stages, files and whether it finished")
    action("stages", list_stages, "a run's stages, and which wrote results")
    action("files", list_files, "a run's files, with their sizes")
    action("fields", list_fields, "what a stage can show", stage=True)
    field = action("field", show_field, "one field of a stage", stage=True, csv=True)
    field.add_argument("name", help="as `results fields` lists it: uy, syy, pw, ...")
    field.add_argument("--location", choices=("nodes", "elements"),
                       help="per node, or per element as the solver computed it (default: "
                            "the first the field offers, as in the GUI)")
    at = action("at", show_at_node, "every field of a stage at one node", stage=True)
    at.add_argument("node", type=int)
    action("members", list_members, "the members the run wrote curves for")
    profile = action("profile", show_profile, "one quantity along a member, stage by "
                                              "stage", stage=True, csv=True)
    profile.add_argument("member", help="as `results members` lists it: wall, "
                                           "interface_right, ...")
    profile.add_argument("quantity", nargs="?",
                         help="M, Q, N, ux, uy, tn, ts, or a word of its label "
                              "(default: the bending moment)")
    get = action("get", get_file, "copy one file of a run")
    get.add_argument("file", help="as `results files` lists it")
    _out(get, "the file's own name, here")
    archive = action("archive", get_archive, "the whole run as one zip")
    _out(archive, "<run>.zip, here")


def _out(parser: argparse.ArgumentParser, default: str) -> None:
    # Taken as typed, not as a Path, which would drop the separator that says "a folder".
    parser.add_argument("--out", metavar="PATH",
                        help=f"a file, or a folder to put it in, made when it ends in / "
                             f"(default: {default})")
    parser.add_argument("--force", action="store_true", help="overwrite a file already there")


# ── The runs ────────────────────────────────────────────────────────────────

def list_runs(args: argparse.Namespace) -> Answer:
    with environment(args):
        runs = catalog.runs()
        root = calculation.runs_root()
    if not runs:
        return Answer(data=[], lines=[f"No runs yet in {root}. `kratos-cli calculate "
                                      "<project>` or `kratos-cli run <deck>` makes one."])
    lines = [f"{len(runs)} run{'s' if len(runs) != 1 else ''} in {root}:"]
    lines += [f"{number:>3}  {run['id']}  {run['results']} stage(s) with results, "
              f"{run['files']} files" for number, run in enumerate(runs, start=1)]
    return Answer(data=runs, lines=lines)


def show_run(args: argparse.Namespace) -> Answer:
    with environment(args):
        run = catalog.describe(_run(args.run))
    started = f"started {run['started']}" if run["started"] else "start unknown"
    lines = [f"{run['id']}  (deck {run['deck']}, {started})",
             f"  {'complete' if run['complete'] else 'not complete'}, "
             f"{run['unit_system']} units, {len(run['files'])} files, "
             f"{_size(sum(entry['bytes'] for entry in run['files']))}"]
    lines += _stage_lines(run["stages"])
    if run["failed_at"]:
        failed = run["failed_at"]
        lines.append(f"  stopped in stage {failed['index']} of {failed['of']} "
                     f"({_tidy(failed['name'])}); the stages before it can be read")
    elif not run["complete"]:
        lines.append("  not every stage wrote results, and the log does not say why"
                     + (f": see {run['log']} in the run directory" if run["log"] else ""))
    return Answer(data=run, lines=lines)


def list_stages(args: argparse.Namespace) -> Answer:
    with environment(args):
        run = catalog.describe(_run(args.run))
    return Answer(data=run["stages"],
                  lines=[f"{run['id']}: {len(run['stages'])} stages",
                         *_stage_lines(run["stages"])])


def list_files(args: argparse.Namespace) -> Answer:
    with environment(args):
        run = catalog.describe(_run(args.run))
    lines = [f"{len(run['files'])} files in {run['id']}:"]
    width = max((len(entry["name"]) for entry in run["files"]), default=0) + 2
    lines += [f"  {entry['name']:<{width}}{_size(entry['bytes'])}" for entry in run["files"]]
    lines.append("`kratos-cli results get <run> <file>` copies one, `results archive "
                 "<run>` all of them.")
    return Answer(data=run["files"], lines=lines)


# ── One stage ───────────────────────────────────────────────────────────────

def list_fields(args: argparse.Namespace) -> Answer:
    with environment(args):
        run = _run(args.run)
        stage = _stage(run, args.stage, args.run)
        menu = catalog.stage_fields(run, stage["index"])
    lines = [f"Stage {_named_stage(stage)} offers:"]
    for group in menu["groups"]:
        lines.append(f"  {group['name']}")
        lines += [f"    {entry['name']:<10}{entry['label']:<32}{entry['unit']:<8}"
                  + "/".join(entry["locations"]) for entry in group["fields"]]
    lines.append("`kratos-cli results field <run> <name>` reads one.")
    return Answer(data=menu, lines=lines)


def show_field(args: argparse.Namespace) -> Answer:
    with environment(args):
        run = _run(args.run)
        stage = _stage(run, args.stage, args.run)
        location = args.location or _first_location(run, stage["index"], args.name)
        try:
            field = catalog.stage_field(run, stage["index"], args.name, location)
        except fields.UnknownField as failure:
            raise CommandError(f"{failure} `kratos-cli results fields {args.run}` lists "
                               f"what stage {_named_stage(stage)} has.") from None
        label = _label(run)
    where = "element" if field["location"] == "elements" else "node"
    count = len(field["ids"])
    lines = [f"{field['label']} ({field['unit']}), stage {_named_stage(stage)}: "
             f"{tables.shown(field['min'])} to {tables.shown(field['max'])} over "
             f"{count} {where}{'s' if count != 1 else ''}"]
    if count:
        pairs = list(zip(field["values"], field["ids"]))
        low, high = min(pairs), max(pairs, key=lambda pair: (pair[0], -pair[1]))
        lines += [f"  min {tables.shown(low[0])} at {where} {low[1]}",
                  f"  max {tables.shown(high[0])} at {where} {high[1]}"]
        if "totals" in field:
            lines.append(_totals(field))
        lines.append("`--csv` writes every value.")
    return Answer(data=field, lines=lines,
                  csv=tables.field_csv(field, label, stage["stage"]))


def _totals(field: dict) -> str:
    """The sums of a field whose total means something (`fields.Definition.summed`). For
    the nodal water flow rate: the water let out, the water taken in, and the difference
    -- zero in a steady state, what the pores stored or gave up in a transient one."""
    totals, unit = field["totals"], field["unit"]
    if field["field"] == "flow_rate":
        return (f"  out {tables.shown(totals['positive'])}, in "
                f"{tables.shown(-totals['negative'])}, out - in "
                f"{tables.shown(totals['net'])} {unit}")
    return (f"  sum {tables.shown(totals['net'])} {unit} (positive "
            f"{tables.shown(totals['positive'])}, negative {tables.shown(totals['negative'])})")


def show_at_node(args: argparse.Namespace) -> Answer:
    with environment(args):
        run = _run(args.run)
        stage = _stage(run, args.stage, args.run)
        answer = catalog.stage_at_node(run, stage["index"], args.node)
    # Within half a millimetre of zero is zero, not "-0.000" (as `kratos-cli node`).
    at = ", ".join(f"{value if abs(value) >= 5e-4 else 0.0:.3f}" for value in answer["at"])
    lines, group = [f"Node {answer['node']} at ({at}) in stage {_named_stage(stage)}:"], None
    for row in answer["values"]:
        if row["group"] != group:
            group = row["group"]
            lines.append(f"  {group}")
        value = "—" if row["value"] is None else tables.shown(row["value"])
        lines.append(f"    {row['label']:<32}{value:<12}{row['unit']}")
    return Answer(data=answer, lines=lines)


# ── Members ─────────────────────────────────────────────────────────────────

def list_members(args: argparse.Namespace) -> Answer:
    with environment(args):
        listed = catalog.stage_members(_run(args.run))
    if not listed["members"]:
        return Answer(data=listed, lines=["This run wrote no member output: there is no "
                                          "wall in it, or no stage with one."])
    lines = ["This run wrote curves for:"]
    width = max(len(member["name"]) for member in listed["members"]) + 2
    for member in listed["members"]:
        stages = "stages " + ", ".join(map(str, member["stages"]))
        lines.append(f"  {member['name']:<{width}}{stages:<22}"
                     + ", ".join(entry["name"] for entry in member["quantities"]))
    lines.append("`kratos-cli results profile <run> wall M` reads one.")
    return Answer(data=listed, lines=lines)


def show_profile(args: argparse.Namespace) -> Answer:
    with environment(args):
        run = _run(args.run)
        listed = catalog.stage_members(run)["members"]
        member = _member(listed, args.member, run)
        quantity = _quantity(member, args.quantity)
        plot = catalog.member_profiles(run, member["name"], quantity)
        if args.stage is not None:
            stage = _stage(run, args.stage, args.run)
            plot["stages"] = [entry for entry in plot["stages"]
                              if entry["index"] == stage["index"]]
            if not plot["stages"]:
                raise CommandError(
                    f"The {member['name']} has no output in stage {_named_stage(stage)}; "
                    f"it has stages {', '.join(map(str, member['stages']))}.")
    lines = [f"{plot['label']} ({plot['unit']}) along the {plot['member']}, "
             f"{len(plot['stages'])} stage{'s' if len(plot['stages']) != 1 else ''}:"]
    for entry in plot["stages"]:
        low, high = entry["min"], entry["max"]
        extremes = (f"min {tables.shown(low['value'])} at y {tables.shown(low['y'])}, "
                    f"max {tables.shown(high['value'])} at y {tables.shown(high['y'])}"
                    if low else "no values")
        lines.append(f"  {entry['index']:>3}  {entry['stage']:<30}{extremes}")
    lines.append("`--csv` writes every point.")
    return Answer(data=plot, lines=lines, csv=tables.profile_csv(plot))


def _member(listed: list[dict], wanted: str, run) -> dict:
    """A member by its name, in any case (`ResultsPlot`'s `memberNamed`)."""
    for member in listed:
        if member["name"].lower() == wanted.lower():
            return member
    names = ", ".join(member["name"] for member in listed) or "none"
    raise CommandError(f"{_label(run)} wrote no output for a member called {wanted!r}; "
                       f"it has {names}.")


def _quantity(member: dict, wanted: str | None) -> str:
    """A quantity by its name (`M`, `tn`) or by a word of its label (`moment`,
    `normal`), the name first (`ResultsPlot`'s `quantityIn`); the bending moment, or the
    first there is, when none is asked for."""
    quantities = member["quantities"]
    if not wanted:
        chosen = next((entry for entry in quantities if entry["name"] == "M"),
                      quantities[0] if quantities else None)
    else:
        word = wanted.strip().lower()
        chosen = (next((entry for entry in quantities if entry["name"].lower() == word),
                       None)
                  or next((entry for entry in quantities
                           if word in entry["label"].lower()), None))
    if chosen is None:
        raise CommandError(f"The {member['name']} output has no {wanted!r}. It has "
                           + ", ".join(entry["name"] for entry in quantities) + ".")
    return chosen["name"]


# ── Files ───────────────────────────────────────────────────────────────────

def get_file(args: argparse.Namespace) -> Answer:
    with environment(args):
        source = catalog.file_path(_run(args.run), args.file)
    target = _target(args, source.name)
    shutil.copyfile(source, target)
    return Answer(data={"file": str(target), "bytes": target.stat().st_size},
                  lines=[f"wrote {target} ({_size(target.stat().st_size)})"])


def get_archive(args: argparse.Namespace) -> Answer:
    with environment(args):
        run = _run(args.run)
        name = f"{catalog.directory_of(run).name}.zip"
        buffer = catalog.archive(run)
    target = _target(args, name)
    target.write_bytes(buffer.getvalue())
    return Answer(data={"file": str(target), "bytes": target.stat().st_size},
                  lines=[f"wrote {target} ({_size(target.stat().st_size)})"])


def _target(args: argparse.Namespace, name: str) -> Path:
    """Where `--out` says: a file, or a folder to put `name` in -- one that is there, or
    one written with a separator at its end (`logs/`), which is made."""
    if args.out is None:
        target = Path(name)
    elif args.out.endswith(("/", "\\")):
        # Either separator, on every system: off Windows a trailing `\` is a legal
        # character of a name, and Path would make a folder called `logs\`.
        folder = Path(args.out.rstrip("/\\") or args.out)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / name
    else:
        target = Path(args.out)
    if target.is_dir():
        target = target / name
    if target.exists() and not args.force:
        raise CommandError(f"{target} is already there. Give --force to overwrite it, or "
                           "another --out.")
    return target


# ── Shared ──────────────────────────────────────────────────────────────────

def _run(given: str) -> catalog.Run:
    """A run: its position in the listing, a run directory anywhere, or a run id. A
    run's id always ends in its date and time, so a bare number is never one."""
    if given.isdigit():
        runs = catalog.runs()
        position = int(given)
        if not 1 <= position <= len(runs):
            raise CommandError(f"There is no run {position}: the listing has {len(runs)} "
                               f"run{'s' if len(runs) != 1 else ''}. `kratos-cli results "
                               "runs` lists them.")
        return runs[position - 1]["id"]
    if Path(given).is_dir():
        return Path(given)
    if not catalog.RUN_NAME.match(given):
        raise CommandError(f"{given!r} is not a run: give a run's id or its number in "
                           "`kratos-cli results runs`, or a run directory.")
    return given


def _label(run: catalog.Run) -> str:
    return str(run) if isinstance(run, Path) else run


def _stage(run: catalog.Run, wanted: str | None, given: str) -> dict:
    """The stage `--stage` names (`results.js`' `findStage`), or the last one that wrote
    results."""
    stages = catalog.stage_list(catalog.directory_of(run))
    if wanted is None:
        readable = [stage for stage in stages if stage["results"]]
        if not readable:
            raise CommandError(f"{_label(run)} wrote no results. `kratos-cli results show "
                               f"{given}` says how far it got.")
        return readable[-1]
    if wanted.strip().isdigit():
        found = next((stage for stage in stages if stage["index"] == int(wanted)), None)
    else:
        words = re.sub(r"[^a-z0-9]+", " ", wanted.lower()).strip()
        found = next((stage for stage in stages
                      if words in stage["stage"].lower()
                      or words in re.sub(r"[^a-z0-9]+", " ", stage["name"].lower())), None)
    if found is None:
        raise CommandError(f"In {_label(run)}, no stage matches {wanted!r}. Its stages: "
                           + ", ".join(f"{stage['index']} {stage['stage']}"
                                       for stage in stages) + ".")
    return found


def _first_location(run: catalog.Run, index: int, name: str) -> str:
    """Where the GUI draws a field it is not told where to: per element for a stress,
    as the solver computed it; per node for what only has nodes."""
    for group in catalog.stage_fields(run, index)["groups"]:
        for entry in group["fields"]:
            if entry["name"] == name:
                return entry["locations"][0]
    return "nodes"  # Not on the menu: `stage_field` says why.


def _stage_lines(stages: list[dict]) -> list[str]:
    lines = []
    for stage in stages:
        series = len(stage["json"])
        lines.append(f"  {stage['index']:>3}  {stage['stage']:<30}"
                     + ("results" if stage["results"] else "no results")
                     + (f"  +{series} series" if series else ""))
    return lines


def _named_stage(stage: dict) -> str:
    return f"{stage['index']} ({stage['stage']})"


def _tidy(name: str) -> str:
    """`1_First_excavation` back to `First excavation`, as a stage row says it."""
    return re.sub(r"^\d+_", "", name or "").replace("_", " ")


def _size(count: int) -> str:
    """`results.js`' `size`."""
    if count < 1024:
        return f"{count} B"
    if count < 1024 ** 2:
        return f"{count / 1024:.1f} KB"
    if count < 1024 ** 3:
        return f"{count / 1024 ** 2:.1f} MB"
    return f"{count / 1024 ** 3:.1f} GB"
