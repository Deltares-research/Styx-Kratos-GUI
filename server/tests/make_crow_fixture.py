"""Builds the committed CROW run fixture out of a real run directory.

    python tests/make_crow_fixture.py --write

A calculation writes 5.7 MB into `~/KratosGUI/runs/<deck>_<stamp>/`, and that directory
is on one machine and in nobody's clone. The tests in `test_crow_results.py` and
`test_crow_wall_forces.py` need a *real* run -- seven stages, eight bodies, a beam,
interfaces, bodies that vanish mid-sequence -- so this distils one down to ~700 KB that
can be committed: the deck, two of the seven stages, the per-member output of the four
stages the validation checks, and the deck's own parameter files. Everything textual is
gzipped; `tests/crow_run.py` expands it into a temporary directory that is a run
directory in every respect, which is how the registry can be pointed at it.

It also writes the *expected* results, which come from somewhere else entirely:
Kratos' own CROW validation case. `<stage>__expected_results_wall.csv` in the
GeoMechanicsApplication's test suite holds bending moment, shear force, normal force and
horizontal displacement per node of the *reference* mesh. Our mesh has neither the same
node numbering nor the same node positions, so the join is by **y along the wall**, the
way `test_CROW_case_generated_mesh.py` does it: node ids are turned into y through the
reference deck, and the result is a curve that any mesh can be interpolated onto. Doing
that here rather than in the test means the committed fixture depends on neither the
Kratos checkout nor the gitignored reference deck.

Regenerating is deliberate, never a side effect of running the suite: `--write` is
required, and the diff is meant to be read. Everything it writes is reproducible from a
run directory plus a Kratos checkout, and `manifest.json` records which ones.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from tests import mdpa                                    # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "crow_run"
RUN_FILES = FIXTURE / "run"
EXPECTED_WALL = FIXTURE / "expected_wall"

KRATOS_TESTS = pathlib.Path(
    r"C:\Checkouts\KratosProjects\yek\applications\GeoMechanicsApplication\tests")
"""Where the validation case lives on the machine this fixture was made on. Only this
script needs it; the tests read what it wrote."""

REFERENCE_WALL_PART = "Sheet_Pile_Wall"
"""The wall in the reference deck. Ours is `SheetPileWall` -- the same wall, named by a
different hand (see `test_crow_reference.py` on why names are not compared)."""

OUR_WALL_PART = "SheetPileWall"

STAGES = {
    # reference stage -> ours. The two excavations and the wall installation are the
    # stages the Kratos test checks; 5 (the strut) is plotted there but not checked,
    # and 1 and 2 have no wall to check.
    "3_Wall_installation": "3_SheetPileWall_installation",
    "4_First_excavation": "4_First_excavation",
    "6_Second_excavation": "6_Second_excavation",
    "7_Third_excavation": "7_Third_excavation",
}

CSV_FIELDS = {
    # ours <- Kratos' column name. All SI: N*m/m, N/m, m.
    "bending_moment": "bending_moment_in_Nm_per_m",
    "shear_force": "shear_force_in_N_per_m",
    "normal_force": "normal_force_in_N_per_m",
    "horizontal_total_displacement": "horizontal_total_displacement_in_m",
}

KEPT_STAGES = ["1_Initial_stage", "7_Third_excavation"]
"""The two stages whose GiD output is committed: the k0 state, where everything the deck
has is present, and the last excavation, where three bodies have been dug away. The
middle five are ~2.5 MB and are exercised by the opt-in tests against a whole run."""

VERSION = re.compile(r"Multi-Physics\s+(\S+)")


def newest_run(root: pathlib.Path, deck: str) -> pathlib.Path:
    candidates = sorted(path for path in root.glob(f"{deck}_*") if path.is_dir())
    if not candidates:
        raise SystemExit(f"no run of {deck} in {root}")
    return candidates[-1]


def wall_y_by_node(deck_text: str, part: str) -> dict[int, float]:
    """{node id: y} for one sub-model part of a deck."""
    deck = mdpa.parse(deck_text)
    if part not in deck.parts:
        raise SystemExit(f"no sub-model part {part!r} in the deck "
                         f"(it has {sorted(deck.parts)[:8]}...)")
    return {node: deck.nodes[node][1] for node in deck.parts[part].nodes}


def expected_curves(csv_path: pathlib.Path,
                    y_by_node: dict[int, float]) -> list[dict[str, float]]:
    """Kratos' expected results, re-keyed from reference node id to y.

    Sorted by y, so the test can walk it as a curve. The node id is dropped: it is the
    reference mesh's numbering and means nothing to any other mesh, and keeping it would
    invite exactly the join this whole exercise exists to avoid.
    """
    rows = []
    with open(csv_path, newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append({"y": y_by_node[int(row["node"])]}
                        | {ours: float(row[theirs])
                           for ours, theirs in CSV_FIELDS.items()})
    return sorted(rows, key=lambda row: row["y"])


def write_expected(kratos_tests: pathlib.Path) -> dict:
    validation = kratos_tests / "crow_validation"
    reference_deck = validation / "common" / "model.mdpa"
    expected_dir = validation / "linear_elastic" / "staged_construction"
    if not reference_deck.exists():
        raise SystemExit(f"no reference deck at {reference_deck}; pass --kratos-tests")

    y_by_node = wall_y_by_node(reference_deck.read_text(errors="replace"),
                              REFERENCE_WALL_PART)
    EXPECTED_WALL.mkdir(parents=True, exist_ok=True)
    written = {}
    for reference_stage, our_stage in STAGES.items():
        source = expected_dir / f"{reference_stage}__expected_results_wall.csv"
        rows = expected_curves(source, y_by_node)
        target = EXPECTED_WALL / f"{our_stage}.csv"
        with open(target, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["y", *CSV_FIELDS])
            writer.writeheader()
            for row in rows:
                writer.writerow({"y": f"{row['y']:.6f}"}
                                | {name: f"{row[name]:.6}" for name in CSV_FIELDS})
        written[our_stage] = source.name
        print(f"  expected_wall/{target.name}: {len(rows)} points, "
              f"y {rows[0]['y']:.3f} .. {rows[-1]['y']:.3f}")

    return {
        "from": str(expected_dir),
        "reference_deck": str(reference_deck),
        "reference_wall_part": REFERENCE_WALL_PART,
        "files": written,
    }


def copy_run(run: pathlib.Path) -> dict:
    """The run itself: deck, parameters, two stages of GiD output, member output."""
    if RUN_FILES.exists():
        shutil.rmtree(RUN_FILES)
    RUN_FILES.mkdir(parents=True)

    deck_name = next(run.glob("*.mdpa")).stem
    compressed = [f"{deck_name}.mdpa", "ProjectParameters.json"]
    compressed += [f"{deck_name}_{stage}.post.{kind}"
                   for stage in KEPT_STAGES for kind in ("msh", "res")]
    plain = ["MaterialParameters.json", "initial_materials.json"]
    plain += sorted(path.name for path in run.glob("*__output_wall.json")
                    if path.name.split("__")[0] in STAGES.values())
    plain += [f"{max(STAGES.values())}__output_interface.json"]

    total = 0
    for name in compressed:
        source = run / name
        target = RUN_FILES / f"{name}.gz"
        target.write_bytes(gzip.compress(source.read_bytes(), 9))
        total += target.stat().st_size
    for name in plain:
        source = run / name
        if not source.exists():
            print(f"  (no {name} in this run)")
            continue
        shutil.copyfile(source, RUN_FILES / name)
        total += (RUN_FILES / name).stat().st_size

    log = (run / "kratos.log")
    version = None
    if log.exists():
        found = VERSION.search(log.read_text(errors="replace")[:4000])
        version = found.group(1) if found else None

    print(f"  run/: {len(list(RUN_FILES.iterdir()))} files, {total / 1024:.0f} KB")
    return {
        "run": run.name,
        "from": str(run),
        "deck_name": deck_name,
        "kratos": version,
        "stages_with_gid_output": KEPT_STAGES,
        "our_wall_part": OUR_WALL_PART,
    }


PROBES = [
    # (label, x, y). Chosen by where they are in the model rather than by node id, so
    # that regenerating the fixture from a differently meshed run still probes the same
    # places: the far field at three depths, the ground the excavation is taking, and
    # both ends of the wall.
    ("far field, upper ground", 40.0, -3.0),
    ("far field, middle ground", 40.0, -10.0),
    ("far field, deep sand", 40.0, -30.0),
    ("behind the wall, above the first lift", 3.0, -1.0),
    ("under the pit floor", 2.5, -9.0),
    ("the wall's top", 5.0, 0.0),
    ("the wall's toe", 5.0, -13.0),
]
"""Where `expected.json` records every field this reader produces."""

JS_FIXTURE = (HERE.parents[1] / "live" / "tests" / "fixtures" / "crow-field.js")
JS_SECTION = "results:Soil_Middle_pit"
JS_STAGE = 7

JS_HEADER = """/* Generated fixture -- one real section of one real stage, for the arithmetic that
   decides what gets drawn. Written by server/tests/make_crow_fixture.py --write.

   `test-results-render.js` is otherwise made of four-vertex squares, which is the right
   way to pin an edge case and the wrong way to notice that a whole mesh comes out
   inside-out. This is %(part)s in stage %(stage)d of the CROW run: %(vertices)d
   vertices, %(triangles)d triangles, and the values that go on them.

   A .js file assigning a global rather than a .json one, because the browser suite is
   opened from file://, where a fetch is blocked. Same convention as phase-cases.js.
*/
window.CROW_FIXTURE =
"""


def round_all(value, digits: int = 6):
    """Floats to a fixed number of decimals, recursively. Keeps the fixture readable and
    its diff meaningful: a field written at full double precision changes in its last
    digit for reasons nobody can see."""
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, list):
        return [round_all(item, digits) for item in value]
    if isinstance(value, dict):
        return {key: round_all(item, digits) for key, item in value.items()}
    return value


def write_expected_values(run: pathlib.Path) -> dict:
    """Every field this reader produces, at seven points, in both committed stages.

    A pin against ourselves, and deliberately a tight one: the physical checks in
    `test_crow_results.py` say the numbers are *plausible* -- hydrostatic, compression
    negative, in kPa -- and a plausible number can still be a changed one. This is what
    notices when the Gauss-to-node averaging, an invariant or a unit quietly moves.

    Recorded through `results.stage_at_node`, which is also what `results at <id>`
    prints, so the file is readable as what a user would have seen.
    """
    import os

    from app import calculate, results

    os.environ[calculate.RUNS_ENV] = str(run.parent)
    results.forget_cache()
    run_id = run.name

    mesh = results.stage_mesh(run_id, 7)
    probes = []
    for label, x, y in PROBES:
        node = min(mesh.nodes,
                   key=lambda id: (mesh.nodes[id][0] - x) ** 2
                   + (mesh.nodes[id][1] - y) ** 2)
        probes.append({
            "label": label,
            "target": [x, y],
            "node": node,
            "at": list(mesh.nodes[node]),
            # Full precision, not rounded: the point of this file is to notice a change
            # in the last digits, and rounding it would be rounding away its purpose.
            "stages": {str(index): results.stage_at_node(run_id, index, node)
                       for index in (1, 7)},
        })

    target = FIXTURE / "expected.json"
    target.write_text(json.dumps({"probes": probes}, indent=1) + "\n",
                      encoding="utf-8")
    print(f"  expected.json: {len(probes)} probes x 2 stages, "
          f"{target.stat().st_size / 1024:.0f} KB")
    return {"probes": [probe["label"] for probe in probes], "stages": [1, 7]}


def compact_json(payload: dict, depth: int = 2, indent: int = 1) -> str:
    """JSON with structure on the outside and no whitespace inside the arrays.

    `indent=2` all the way down puts each of 1 300 triangle indices on a line of its
    own, which is a 235 KB fixture nobody can read and a diff nobody can follow. Two
    levels of keys are expanded and everything below them is compact, so the file opens
    on a shape rather than on a column of integers.
    """
    if depth == 0 or not isinstance(payload, dict):
        return json.dumps(payload, separators=(",", ":"))
    pad = " " * indent
    lines = [f'{pad}{json.dumps(key)}: '
             f'{compact_json(value, depth - 1, indent + 1)}'
             for key, value in payload.items()]
    return "{\n" + ",\n".join(lines) + "\n" + " " * (indent - 1) + "}"


def write_js_fixture(run: pathlib.Path) -> dict:
    """One section and its fields, for `live/tests/test-results-render.js`."""
    import os

    from app import calculate, results

    os.environ[calculate.RUNS_ENV] = str(run.parent)
    results.forget_cache()
    run_id = run.name

    sections = results.stage_geometry(run_id, JS_STAGE)["sections"]
    section = next(one for one in sections if one["key"] == JS_SECTION)
    wanted = {"nodes": set(section["node_ids"]),
              # `elements` is the part's own list and is empty for a section the mesh
              # gave us per triangle; the ids that matter here are the ones the
              # triangles were built from.
              "elements": set(section["triangle_elements"])}

    def field(name: str, location: str) -> dict:
        """One field, cut down to the ids this section draws.

        `min` and `max` are left as the whole stage's, because that is what they are:
        the legend is drawn for the stage and the colours for one section at a time, and
        a fixture that narrowed the range would be a different picture from the one on
        screen.
        """
        found = results.stage_field(run_id, JS_STAGE, name, location)
        kept = [(id, value) for id, value in zip(found["ids"], found["values"])
                if id in wanted[location]]
        return found | {"ids": [id for id, _ in kept],
                        "values": [value for _, value in kept]}

    payload = {
        "run": run_id,
        "stage": JS_STAGE,
        "section": section,
        "fields": {"p_nodes": field("p", "nodes"),
                   "p_elements": field("p", "elements"),
                   "uy": field("uy", "nodes")},
    }
    header = JS_HEADER % {"part": section["part"], "stage": JS_STAGE,
                          "vertices": len(section["node_ids"]),
                          "triangles": len(section["indices"]) // 3}
    JS_FIXTURE.write_text(header + compact_json(round_all(payload)) + ";\n",
                          encoding="utf-8")
    print(f"  {JS_FIXTURE.relative_to(HERE.parents[1])}: "
          f"{JS_FIXTURE.stat().st_size / 1024:.0f} KB")
    return {"section": JS_SECTION, "stage": JS_STAGE,
            "fields": sorted(payload["fields"])}


def git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE,
                              capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):       # pragma: no cover
        return None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true",
                        help="actually write the fixture (required)")
    parser.add_argument("--run", type=pathlib.Path,
                        help="the run directory to distil; default is the newest CROW "
                             "run under the runs root")
    parser.add_argument("--kratos-tests", type=pathlib.Path, default=KRATOS_TESTS,
                        help="the GeoMechanicsApplication's tests directory, which "
                             "holds crow_validation/")
    arguments = parser.parse_args(argv[1:])

    if not arguments.write:
        parser.error("this rewrites a committed fixture; pass --write to mean it")

    from app import calculate                             # here: needs gmsh on the path
    run = arguments.run or newest_run(calculate.runs_root(), "CROW_excavation_wall")
    print(f"run:      {run}")
    print(f"expected: {arguments.kratos_tests}")

    manifest = {
        "written_by": "tests/make_crow_fixture.py",
        "git_sha": git_sha(),
        "run": copy_run(run),
        "expected": write_expected(arguments.kratos_tests),
        "values": write_expected_values(run),
        "javascript": write_js_fixture(run),
    }
    (FIXTURE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                           encoding="utf-8")
    print(f"wrote {FIXTURE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
