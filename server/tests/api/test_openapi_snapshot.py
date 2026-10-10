"""The API's shape, frozen (plan sec 5 (e)).

The front end discovers an API change only at run time, in somebody's browser. This
compares `app.openapi()` -- every route, parameter, request and response schema -- with
a committed snapshot, minus the prose (descriptions, summaries, titles), so a docstring
edit does not fail it and a renamed field does.

The schema FastAPI emits depends on the FastAPI and pydantic versions as well as on the
code, so the snapshot records the versions it was made with -- the ones
`requirements.txt` pins, i.e. the server venv's. Under any other versions the comparison
would only measure the libraries, so it is skipped with the reason.

A deliberate change: `pytest tests/api/test_openapi_snapshot.py --update-snapshots`
(in the server venv), then review the diff of `openapi.snapshot.json`.
"""

from __future__ import annotations

import json
from pathlib import Path

import fastapi
import pydantic
import pytest

from app.main import app

SNAPSHOT = Path(__file__).with_name("openapi.snapshot.json")
PROSE = {"description", "summary", "title"}


def _without_prose(node):
    if isinstance(node, dict):
        return {k: _without_prose(v) for k, v in node.items()
                if not (k in PROSE and isinstance(v, str))}
    if isinstance(node, list):
        return [_without_prose(v) for v in node]
    return node


def _versions() -> dict:
    return {"fastapi": fastapi.__version__, "pydantic": pydantic.VERSION}


def _render(document: dict) -> str:
    return json.dumps(document, indent=1, sort_keys=True) + "\n"


def test_the_api_matches_its_snapshot(request):
    current = {"versions": _versions(), "openapi": _without_prose(app.openapi())}
    if request.config.getoption("--update-snapshots") or not SNAPSHOT.exists():
        SNAPSHOT.write_text(_render(current), encoding="utf-8")
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    if committed["versions"] != current["versions"]:
        pytest.skip(f"the snapshot was made with {committed['versions']}, this interpreter "
                    f"has {current['versions']}; run it in the server venv")
    assert _render(current) == _render(committed), (
        "The API changed. If that is deliberate, rerun with --update-snapshots and "
        "review the diff of tests/api/openapi.snapshot.json.")


def test_prose_is_not_part_of_the_snapshot():
    stripped = _without_prose({"description": "x", "properties": {"title": {"type": "string"}}})

    assert stripped == {"properties": {"title": {"type": "string"}}}


def test_the_snapshot_was_made_with_the_pinned_versions():
    """Regenerated under the wrong interpreter, the snapshot would silently stop being
    checked by the one that matters."""
    pins = dict(line.strip().split("==") for line in
                (Path(__file__).resolve().parents[2] / "requirements.txt")
                .read_text(encoding="utf-8").splitlines() if "==" in line)
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["versions"]

    assert committed == {"fastapi": pins["fastapi"], "pydantic": pins["pydantic"]}
