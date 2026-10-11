"""The register of constructs only a Kratos run can prove (tests/kratos/register.py) is
held to the code: a new comment deferring to "the first real run" fails here until the
register has a row for its file, and no row may claim a status it does not have."""

from __future__ import annotations

import re
from pathlib import Path

from tests.kratos.register import COVERED_FILES, REGISTER

APP = Path(__file__).resolve().parents[1] / "app"
DEFERRAL = re.compile(r"first real|check (?:it|them|this) against the first", re.IGNORECASE)


def test_every_row_says_what_proves_it():
    for row in REGISTER:
        assert row["status"] in {"closed", "fixed", "open", "blocked"}, row["id"]
        assert row["evidence"].strip(), row["id"]
    assert len({row["id"] for row in REGISTER}) == len(REGISTER)


def test_every_deferral_in_the_exporter_is_in_a_file_the_register_covers():
    deferring = {path.name for path in APP.glob("*.py")
                 if DEFERRAL.search(path.read_text(encoding="utf-8"))}
    assert deferring <= COVERED_FILES, sorted(deferring - COVERED_FILES)
    registered = {row["where"].split()[0].split(".")[0] + ".py" for row in REGISTER}
    assert deferring <= registered | {"kratos_materials.py", "kratos_processes.py"}


def test_the_open_and_blocked_rows_are_the_known_gaps():
    """Shrinking this set is progress; growing it should be a decision."""
    assert {row["id"] for row in REGISTER if row["status"] in {"open", "blocked"}} == \
        {"R3", "R6"}
