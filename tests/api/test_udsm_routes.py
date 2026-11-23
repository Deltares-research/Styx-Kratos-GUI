"""The UDSM routes: the models of the libraries that come with Styx, for the material
window (GET /api/udsm/library, /api/udsm/library.js), and a library's bytes, for a deck
the browser downloads (GET /api/udsm/files/<name>)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from core.model import udsm
from tests.fakes import udsm as fakes


@pytest.fixture
def client():
    with udsm.using([fakes.mohr_coulomb()]), TestClient(app) as c:
        yield c


def test_the_library_lists_each_model_with_its_parameters(client):
    answer = client.get("/api/udsm/library")

    assert answer.status_code == 200
    model = answer.json()["models"][0]
    assert model["id"] == "MohrCoulomb64:1" and model["name"] == "Mohr-Coulomb"
    assert model["parameters"][1] == {"name": "@n#_ur", "label": "ν_ur", "key": "nu_ur",
                                      "unit": "-", "quantity": "dimensionless"}
    assert answer.json()["problems"] == []


def test_the_page_loads_the_library_as_a_script(client):
    answer = client.get("/api/udsm/library.js")

    assert answer.status_code == 200
    assert answer.headers["content-type"].startswith("text/javascript")
    head, _, body = answer.text.partition(" = ")
    assert head == "App.UDSM_LIBRARY"
    assert json.loads(body.rstrip().rstrip(";")) == udsm.table()


def test_the_page_loads_the_library_before_the_soil_models(client):
    page = client.get("/").text
    assert page.index("/api/udsm/library.js") < page.index("/live/js/soil-models.js")


def test_a_library_file_is_served_by_its_name(client):
    answer = client.get("/api/udsm/files/MohrCoulomb64.dll")

    assert answer.status_code == 200
    assert answer.content == (udsm.FOLDER / "MohrCoulomb64.dll").read_bytes()


@pytest.mark.parametrize("name", ["Other.dll", "parser.py", "..%2Flibrary.py"])
def test_nothing_else_is_served(client, name):
    assert client.get(f"/api/udsm/files/{name}").status_code == 404
