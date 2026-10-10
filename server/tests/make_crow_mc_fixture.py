"""Builds the committed CROW Mohr-Coulomb fixture out of Kratos' own validation case.

    python tests/make_crow_mc_fixture.py --write [--kratos-tests <dir>]

Kratos' `crow_validation/mohr_coulomb_clay-sand/` is the Mohr-Coulomb counterpart of the
linear-elastic CROW case `make_crow_fixture.py` distils: the same mesh and stages, its
soils and contacts given Coulomb laws. Two things are taken from it, so that the tests
depend on neither the Kratos checkout nor anything gitignored:

* its `MaterialParameters.json`, which `test_crow_mc.py` holds our export to, set by set;
* its expected wall results, re-keyed from the reference mesh's node ids to y along the
  wall (the reference deck is `common/model.mdpa`, shared with the elastic case), so
  `tests/kratos/test_live_crow_mc.py` can interpolate them onto any mesh.

Regenerating is deliberate (`--write`), and `manifest.json` records where it came from.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from tests.make_crow_fixture import (CSV_FIELDS, KRATOS_TESTS, REFERENCE_WALL_PART,  # noqa: E402
                                     STAGES, expected_curves, wall_y_by_node)

FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "crow_mc"
EXPECTED_WALL = FIXTURE / "expected_wall"
MATERIALS = FIXTURE / "MaterialParameters.json"


def write(kratos_tests: pathlib.Path) -> dict:
    validation = kratos_tests / "crow_validation"
    case = validation / "mohr_coulomb_clay-sand"
    reference_deck = validation / "common" / "model.mdpa"
    if not case.exists():
        raise SystemExit(f"no Mohr-Coulomb case at {case}; pass --kratos-tests")
    FIXTURE.mkdir(parents=True, exist_ok=True)
    EXPECTED_WALL.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(case / "MaterialParameters.json", MATERIALS)

    y_by_node = wall_y_by_node(reference_deck.read_text(errors="replace"),
                              REFERENCE_WALL_PART)
    written = {}
    for reference_stage, our_stage in STAGES.items():
        source = case / "staged_construction" / f"{reference_stage}__expected_results_wall.csv"
        rows = expected_curves(source, y_by_node)
        with open(EXPECTED_WALL / f"{our_stage}.csv", "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["y", *CSV_FIELDS])
            writer.writeheader()
            for row in rows:
                writer.writerow({"y": f"{row['y']:.6f}"}
                                | {name: f"{row[name]:.6}" for name in CSV_FIELDS})
        written[our_stage] = source.name
        print(f"  expected_wall/{our_stage}.csv: {len(rows)} points")
    try:
        commit = subprocess.run(["git", "-C", str(kratos_tests), "rev-parse", "HEAD"],
                                capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    manifest = {"from": str(case), "reference_deck": str(reference_deck),
                "kratos_commit": commit, "materials": MATERIALS.name,
                "expected_wall": written}
    (FIXTURE / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n",
                                           encoding="utf-8")
    return manifest


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--kratos-tests", type=pathlib.Path, default=KRATOS_TESTS)
    args = parser.parse_args(argv[1:])
    if not args.write:
        print("dry run: pass --write to (re)write tests/fixtures/crow_mc/")
        return 0
    print(json.dumps(write(args.kratos_tests), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
