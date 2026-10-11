"""Running a benchmark the way the GUI runs a model (plan alpha 4.1, decision D5).

The project goes to the server with PUT /api/project and is calculated with POST
/api/calculate -- the same routes, the same export, the same runner the Calculate button
uses -- and the run is then read back through `core.results.catalog`. Nothing about a benchmark
takes a shortcut the user's model would not take.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from core.model.schemas import Project

STATUSES = ("PASS", "PASS-DEV", "FAIL", "ERROR", "BLOCKED", "KNOWN")
"""PASS-DEV: passes, on a deliberately documented deviation from the reference model.
KNOWN: fails the way a recorded, not yet fixed defect says it will. Not a failure of the
suite -- but the day it passes, it is one: the defect is gone and the mark must go too."""


@dataclass
class Outcome:
    name: str
    passed: bool
    measured: str
    expected: str


@dataclass
class Context:
    """What a check reads: the run, the project it was made from, and the server's answer."""
    run_id: str
    project: Project
    response: dict
    directory: Path


@dataclass
class Case:
    id: str
    title: str
    reference: str
    build: Callable[[], Project] | None = None
    checks: list[Callable[[Context], Outcome]] = field(default_factory=list)
    settings: dict | None = None
    deviation: str | None = None
    blocked: str | None = None
    known_defect: str | None = None
    """A defect this case exposes and nobody has fixed yet, named. The case still runs."""
    needs: tuple[str, ...] = ()
    """Cases whose run this one's checks read (a 2D profile its 3D extrusion is held to),
    run first when this one is asked for alone."""
    dimension_after_put: int | None = None
    """Switch the stored project to this dimension through the API before calculating --
    how a user turns a section into its solid model."""


@dataclass
class Result:
    case: Case
    status: str
    outcomes: list[Outcome] = field(default_factory=list)
    seconds: float = 0.0
    detail: str = ""


def run_case(case: Case, runs_root: Path) -> Result:
    if case.blocked:
        return Result(case, "BLOCKED", detail=case.blocked)
    os.environ.setdefault("KRATOS_GUI_ALLOWED_HOSTS", "testserver")
    from fastapi.testclient import TestClient

    from core.analysis import calculation
    from core.results import catalog
    from backend.main import app

    previous = os.environ.get(calculation.RUNS_ENV)
    os.environ[calculation.RUNS_ENV] = str(runs_root)
    catalog.forget_cache()
    started = time.monotonic()
    try:
        project = case.build()
        with TestClient(app) as client:
            put = client.put("/api/project", json=project.model_dump(mode="json"))
            if put.status_code != 200:
                return Result(case, "ERROR", detail=f"PUT project: {put.text[:400]}")
            if case.dimension_after_put:
                switched = client.patch("/api/project/dimension",
                                        json={"dimension": case.dimension_after_put})
                if switched.status_code != 200:
                    return Result(case, "ERROR", detail=f"dimension: {switched.text[:400]}")
                project = Project.model_validate(client.get("/api/project").json())
            settings = case.settings or project.mesh.model_dump()
            response = client.post("/api/calculate", json=settings)
            client.post("/api/project/reset")
        if response.status_code != 200:
            return Result(case, "ERROR", detail=f"calculate: {response.text[:400]}")
        answer = response.json()
        if not answer["ok"]:
            return Result(case, "FAIL", detail=f"Kratos: {(answer.get('error') or '')[-400:]}",
                          seconds=time.monotonic() - started)
        context = Context(answer["run"], project, answer, Path(answer["directory"]))
        outcomes = [check(context) for check in case.checks]
        passed = all(o.passed for o in outcomes)
        status = ("PASS-DEV" if case.deviation else "PASS") if passed else "FAIL"
        detail = case.deviation or ""
        if case.known_defect:
            status, detail = (("FAIL", "passes although marked as a known defect -- the "
                               "defect is gone: remove `known_defect`") if passed
                              else ("KNOWN", case.known_defect))
        return Result(case, status, outcomes, time.monotonic() - started, detail=detail)
    except Exception as error:  # a benchmark's crash is its own result, not the report's
        return Result(case, "ERROR", detail=f"{type(error).__name__}: {error}",
                      seconds=time.monotonic() - started)
    finally:
        if previous is None:
            os.environ.pop(calculation.RUNS_ENV, None)
        else:
            os.environ[calculation.RUNS_ENV] = previous
        catalog.forget_cache()


def with_needs(chosen: list[Case], by_id: dict[str, Case]) -> list[Case]:
    """`chosen` in catalogue order, each preceded by the cases it needs, none twice."""
    out: list[Case] = []

    def add(case: Case) -> None:
        for name in case.needs:
            add(by_id[name])
        if case not in out:
            out.append(case)

    for case in chosen:
        add(case)
    return out


def kratos_commit() -> str | None:
    """The commit and date of the Kratos build a calculation uses, for the report: the
    checkout two levels above the configured build (`<checkout>/bin/Release`)."""
    import subprocess

    from core.analysis import calculation

    build = os.environ.get(calculation.KRATOS_ENV) or calculation._settings().get("kratos")
    if not build:
        return None
    checkout = Path(build).parents[1]
    try:
        return subprocess.run(["git", "-C", str(checkout), "log", "-1", "--format=%H %cI"],
                              capture_output=True, text=True, timeout=30).stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def report(results: list[Result], kratos_commit: str | None) -> tuple[str, dict]:
    lines = ["# Benchmark report", "",
             f"Kratos: `{kratos_commit or 'unknown'}`", "",
             "| Case | Status | Reference | Checks | Time |", "|---|---|---|---|---|"]
    for r in results:
        checks = "<br>".join(f"{'✔' if o.passed else '✘'} {o.name}: {o.measured} "
                             f"(expected {o.expected})" for o in r.outcomes) or r.detail
        lines.append(f"| **{r.case.id}** {r.case.title} | {r.status} | {r.case.reference} | "
                     f"{checks} | {r.seconds:.1f} s |")
    document = {"kratos": kratos_commit, "cases": [
        {"id": r.case.id, "status": r.status, "detail": r.detail, "seconds": round(r.seconds, 2),
         "checks": [o.__dict__ for o in r.outcomes]} for r in results]}
    return "\n".join(lines) + "\n", document


def write_report(results: list[Result], directory: Path, kratos_commit: str | None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    text, document = report(results, kratos_commit)
    (directory / "report.md").write_text(text, encoding="utf-8")
    (directory / "report.json").write_text(json.dumps(document, indent=1), encoding="utf-8")
    return directory / "report.md"
