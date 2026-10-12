"""`python -m benchmarks run --all | <id> ...`, `python -m benchmarks list` (from the repository root).

Writes `benchmarks/reports/report.md` and `report.json` (gitignored) and exits non-zero
when any case FAILs or ERRORs. BLOCKED cases are reported, not failed: they name the
feature they wait for; nor are KNOWN ones, which name the defect they show.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.path.insert(0, str(HERE.parent))
    from benchmarks.cases import BY_ID, CASES
    from benchmarks.runner import kratos_commit, run_case, with_needs, write_report

    parser = argparse.ArgumentParser(prog="python -m benchmarks")
    sub = parser.add_subparsers(dest="verb", required=True)
    sub.add_parser("list")
    run = sub.add_parser("run")
    run.add_argument("ids", nargs="*")
    run.add_argument("--all", action="store_true")
    args, _ = parser.parse_known_args(argv[1:])

    if args.verb == "list":
        for case in CASES:
            print(f"{case.id:12s} {'BLOCKED ' if case.blocked else ''}{case.title}")
        return 0

    chosen = CASES if args.all or not args.ids else with_needs([BY_ID[i] for i in args.ids], BY_ID)
    reports = HERE / "reports"
    results = []
    for case in chosen:
        result = run_case(case, reports / "runs")
        results.append(result)
        print(f"{case.id:12s} {result.status:9s} {result.seconds:6.1f} s  {result.detail}")
        for outcome in result.outcomes:
            print(f"{'':14s}{'ok ' if outcome.passed else 'BAD'} {outcome.name}: "
                  f"{outcome.measured} (expected {outcome.expected})")
    path = write_report(results, reports, kratos_commit())
    print(f"report: {path}")
    return 1 if any(r.status in ("FAIL", "ERROR") for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
