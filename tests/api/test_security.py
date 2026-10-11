"""The local server is only for the browser tab it serves (plan sec 10, S2-S6).

It listens on the loopback interface, but any web page the user has open can still try
to reach it: by DNS rebinding (an attacker's name resolving to 127.0.0.1, so the request
carries the attacker's `Host`), or by a plain cross-site POST from the page itself (which
carries the attacker's `Origin`). Either would reach `/api/project/script`, which runs
Python. Both are refused before any route runs.
"""

from __future__ import annotations

import io
import os
import tempfile
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import launcher
from backend.main import app
from backend.routes import common
from core import calculate


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ── S2: Host and Origin ──────────────────────────────────────────────────────

@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost:8000", "localhost",
                                  "[::1]:8000", "127.0.0.1"])
def test_the_loopback_names_are_served(client, host):
    assert client.get("/api/health", headers={"Host": host}).status_code == 200


@pytest.mark.parametrize("host", ["evil.example", "evil.example:8000",
                                  "127.0.0.1.evil.example", "192.168.1.20:8000"])
def test_a_foreign_host_is_refused_before_any_route_runs(client, host):
    """DNS rebinding: the page's own name now points at 127.0.0.1."""
    response = client.post("/api/project/script", headers={"Host": host},
                           json={"path": "tests/models/excavation.py"})

    assert response.status_code == 400
    assert "host" in response.json()["detail"].lower()


@pytest.mark.parametrize("origin", ["http://evil.example", "https://127.0.0.1.evil.example",
                                    "null"])
def test_a_cross_site_request_is_refused(client, origin):
    """A form or a fetch from another site carries that site's Origin."""
    response = client.post("/api/project/script", headers={"Origin": origin},
                           content=b'{"path": "tests/models/excavation.py"}')

    assert response.status_code == 403
    assert "origin" in response.json()["detail"].lower()


@pytest.mark.parametrize("origin", ["http://127.0.0.1:8000", "http://localhost:8000"])
def test_the_app_own_origin_is_served(client, origin):
    assert client.get("/api/health", headers={"Origin": origin}).status_code == 200


def test_more_hosts_can_be_allowed_deliberately(client, monkeypatch):
    """Serving on a LAN is a choice someone makes on purpose (`--host`), so it is an
    environment variable away -- never the default."""
    monkeypatch.setenv(launcher.ALLOWED_HOSTS_ENV, "modelling-pc, 10.0.0.5")

    assert client.get("/api/health", headers={"Host": "modelling-pc:8000"}).status_code == 200
    assert client.get("/api/health", headers={"Host": "10.0.0.5"}).status_code == 200
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400


# ── S4: upload limits ────────────────────────────────────────────────────────

def _temp_files(suffix: str) -> set[str]:
    return {name for name in os.listdir(tempfile.gettempdir()) if name.endswith(suffix)}


@pytest.mark.parametrize("route,name", [("/api/geometry/import", "big.step"),
                                        ("/api/import/mdpa", "big.mdpa")])
def test_an_upload_over_the_limit_is_refused_and_leaves_nothing_behind(
        client, monkeypatch, route, name):
    # `read_upload` reads the limit from the module it lives in.
    monkeypatch.setattr(common, "MAX_UPLOAD_BYTES", 16)
    before = _temp_files(Path(name).suffix)

    response = client.post(route, files={"file": (name, io.BytesIO(b"x" * 17))})

    assert response.status_code == 413
    assert "16" in response.json()["detail"] or "MB" in response.json()["detail"]
    assert _temp_files(Path(name).suffix) == before


def test_the_upload_limit_is_generous_by_default():
    """A real deck is megabytes (a dike section's mesh: ~3 MB); the limit is for
    runaway files."""
    assert common.MAX_UPLOAD_BYTES >= 100 * 2**20


# ── S5: the archive ──────────────────────────────────────────────────────────

def test_archive_entries_are_plain_names_only(client, tmp_path, monkeypatch):
    root = tmp_path / "runs"
    run = root / "Deck_2026-01-01_00-00"
    (run / "sub").mkdir(parents=True)
    (run / "Deck.mdpa").write_text("Begin Properties 0\nEnd Properties\n", encoding="utf-8")
    (run / "sub" / "hidden.txt").write_text("nested", encoding="utf-8")
    monkeypatch.setenv(calculate.RUNS_ENV, str(root))

    response = client.get("/api/results/runs/Deck_2026-01-01_00-00/archive")

    assert response.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert names == ["Deck.mdpa"]
    assert all("/" not in n and "\\" not in n and ".." not in n for n in names)


# ── S6: where it listens ─────────────────────────────────────────────────────

def test_the_launcher_listens_on_loopback_by_default():
    assert launcher.parse_args([]).host == "127.0.0.1"


def test_the_launcher_allows_the_host_it_was_told_to_listen_on(monkeypatch):
    """`--host modelling-pc` has to be reachable as modelling-pc, or the Host check
    would refuse the very address the user chose."""
    environment = launcher.server_environment(launcher.parse_args(["--host", "0.0.0.0"]),
                                              {})
    assert environment == {}
    environment = launcher.server_environment(
        launcher.parse_args(["--host", "modelling-pc"]), {})
    assert environment[launcher.ALLOWED_HOSTS_ENV] == "modelling-pc"
