"""Without Kratos, the tests that need a real run skip; they do not fail."""

from __future__ import annotations

import sys

import pytest

from core.analysis import calculation
from tests import results_run


@pytest.fixture
def no_settings(monkeypatch, tmp_path):
    """Nothing configured but what the test sets, and a fresh answer to the probe."""
    monkeypatch.setattr(calculation, "SETTINGS_FILE", tmp_path / "absent.json")
    monkeypatch.delenv(calculation.KRATOS_ENV, raising=False)
    results_run.kratos_missing.cache_clear()
    yield
    results_run.kratos_missing.cache_clear()


def test_the_servers_own_python_is_not_taken_for_kratos(no_settings, monkeypatch):
    """The fallback `calculation.interpreter()` takes with nothing configured exists and
    runs, and has no Kratos in it."""
    monkeypatch.setenv(calculation.PYTHON_ENV, sys.executable)
    reason = results_run.kratos_missing()
    assert reason and "not installed" in reason
    with pytest.raises(pytest.skip.Exception, match="not installed"):
        results_run.require_kratos()


def test_a_python_that_does_not_exist_is_a_skip_with_the_reason(no_settings, monkeypatch,
                                                                tmp_path):
    monkeypatch.setenv(calculation.PYTHON_ENV, str(tmp_path / "no-such-python.exe"))
    with pytest.raises(pytest.skip.Exception, match="no Kratos configured"):
        results_run.real_run()
