"""The convergence CSV, written twice and held to one answer.

The GUI's `results convergence csv` builds the file in the browser
(`App.ConvergencePlot.csv`), and `kratos-cli results convergence --csv` builds it in
Python (`cli.terminal.tables.convergence_csv`), from the same data the route sends
(`core.results.convergence`). Two writers of one file drift unless something holds them
together.

`frontend/tests/fixtures/convergence-cases.js` is that something. This module owns it:
it parses the log fixtures with the real parser, writes the CSV with the real Python
writer, and compares both to what is on disk. `frontend/tests/test-convergence-plot.js`
reads the same file and compares the JavaScript CSV to the same text. The same cases
also feed the figure's tests, so the plot is drawn from real parsed logs.

    python tests/test_convergence_parity.py --write

rewrites it after a deliberate change. A `.js` file assigning a global, as
`tests/test_stage_parity.py` explains: the browser suite runs from `file://`.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from cli.terminal import tables  # noqa: E402
from core.analysis import calculation  # noqa: E402
from core.results import convergence  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOGS = ROOT / "tests" / "fixtures" / "convergence"
FIXTURE = ROOT / "frontend" / "tests" / "fixtures" / "convergence-cases.js"
MARKER = calculation.STAGE_MARKER

HEADER = '''/* Generated fixture -- the convergence data of real and made-up Kratos logs, as the
   route sends it, and the CSV `kratos-cli results convergence --csv` writes for each.
   `App.ConvergencePlot.csv` must write the same text, and the figure's tests draw
   these cases. See `tests/test_convergence_parity.py`, which regenerates and
   compares it.

   Not hand-edited. `python tests/test_convergence_parity.py --write` rebuilds it.
*/
window.CONVERGENCE_FIXTURE =
'''

MADE_UP = {
    # What a run that blows up prints, a zero, a stage name with a comma in it, and the
    # fraction of unbalance Kratos' load stepping scheme prints after a step.
    "nan_and_zero": "\n".join([
        f"{MARKER} begin 1/1 1_Dig, then wait",
        "GeoMechanics Analysis: Analysis -START-",
        "GeoMechanics Analysis: cycle:  1", "GeoMechanics Analysis: TIME      :  0.5",
        "RESIDUAL CRITERION:  :: [ Obtained ratio = 0; Expected ratio = 0.0001; "
        "Absolute norm = 0; Expected norm =  1e-09]",
        "RESIDUAL CRITERION: Convergence is achieved",
        "Load stepping: Fraction of unbalance: 0.5",
        "GeoMechanics Analysis: cycle:  1", "GeoMechanics Analysis: TIME      :  1.0",
        "RESIDUAL CRITERION:  :: [ Obtained ratio = nan; Expected ratio = 0.0001; "
        "Absolute norm = -nan(ind); Expected norm =  1e-09]",
        "RESIDUAL CRITERION:  :: [ Obtained ratio = inf; Expected ratio = 0.0001; "
        "Absolute norm = 1e+300; Expected norm =  1e-09]",
        "ResidualBasedNewtonRaphsonStrategy: ATTENTION: max iterations ( 2 ) exceeded!",
        "GeoMechanics Analysis: Down-scaling with factor:  0.5 ",
        "", ]),
    "empty": "",
}


def build() -> dict:
    cases = {}
    for path in sorted(LOGS.glob("*.log")):
        cases[path.stem] = convergence.read_log(path)
    for name, text in MADE_UP.items():
        cases[name] = convergence.parse(text)
    return {name: {"data": data, "csv": tables.convergence_csv(data)}
            for name, data in cases.items()}


def render(document: dict) -> str:
    return HEADER + json.dumps(document, indent=1) + ";\n"


def stored() -> dict:
    text = FIXTURE.read_text(encoding="utf-8")
    marker = "window.CONVERGENCE_FIXTURE ="
    body = text[text.index(marker) + len(marker):].strip()
    return json.loads(body.rstrip(";"))


def test_the_fixture_on_disk_is_what_the_server_and_the_cli_compute():
    assert stored() == build(), (
        "frontend/tests/fixtures/convergence-cases.js is out of date. Rerun\n"
        "    python tests/test_convergence_parity.py --write\n"
        "and check what changed before committing it."
    )


def test_the_fixture_has_the_cases_worth_having():
    document = stored()
    assert {"staged_cut_lines", "iteration_limit", "seepage", "nan_and_zero",
            "empty"} <= set(document)
    made_up = document["nan_and_zero"]["data"]["iterations"]
    assert [i["relative"] for i in made_up] == [0.0, "nan", "inf"]
    assert document["nan_and_zero"]["data"]["fractions"] == [{"at": 1, "value": 0.5}]
    assert '"1_Dig, then wait"' in document["nan_and_zero"]["csv"], "a comma is quoted"


if __name__ == "__main__":
    if "--write" in sys.argv:
        FIXTURE.write_text(render(build()), encoding="utf-8", newline="\n")
        print(f"wrote {FIXTURE}")
