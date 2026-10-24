"""The Muskat tutorial, `docs/cli_tutorials/Muskat_case.md`, run command by command
through `kratos-cli`.

Every command succeeds and prints what the tutorial shows it print, and the three
models it builds are the ones `tests/models/muskat.py` builds: their decks, as
`kratos-cli export` writes them, are the model script's, less the names
(`tests/muskat_reference.deck_view`). The model script's decks are held to Kratos' own
`tests/Muskat` by `tests/test_kratos_flow.py` and `tests/kratos/test_kratos_muskat.py`.

With `--run-kratos` the tutorial's calculations run too. They print what the tutorial
shows, and give the right answer:

- Case A gives Kratos' own values (`test_Muskat.py`) at its nodes, which are the exact
  answer.
- Case B gives Kratos' values to within what its 0.1 m mesh differs from a finer one
  (`CASE_B_TOLERANCE`).
- Case C lets out the water it takes in, at the discharge of Dupuit and Charny, through
  a seepage face open from the tail water up to an exit point.
"""

from __future__ import annotations

import io
import math
import re
import shlex
import shutil
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path

import pytest

from cli.terminal.main import main
from core.analysis import calculation
from core.geometry import solid_model
from core.kratos import writer
from core.results import catalog
from tests import muskat_reference as reference
from tests.models import muskat

TUTORIAL = Path(__file__).resolve().parents[2] / "docs" / "cli_tutorials" / "Muskat_case.md"

RUN_COMMANDS = ("calculate", "results")
"""What needs Kratos, or a run it made."""

FINISHED = re.compile(r"run (\S+) finished in [\d.]+ s: (\d+) files in .+")
"""What `calculate` prints first. The run's name, its time and its folder change from run
to run, so `same_print` compares the rest."""

MODELS = {"muskat.json": lambda: muskat.muskat(order=2),
          "muskat_vg.json": lambda: muskat.van_genuchten(size=0.1),
          "muskat_seepage.json": muskat.seepage}
"""The tutorial's project files, and the model script's model of each."""


@dataclass
class Step:
    command: str
    shown: list[str] | None
    """What the tutorial shows the command print; None for a command it shows alone."""


def steps() -> list[Step]:
    """The tutorial's commands, in order: every line of a `powershell` block, and every
    `PS>` line of a `text` block with the lines it shows printed after it."""
    found: list[Step] = []
    block = None
    for line in TUTORIAL.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            block = None if block is not None else line[3:].strip()
        elif block == "powershell" and line.strip():
            found.append(Step(line.strip(), None))
        elif block == "text" and line.startswith("PS> "):
            found.append(Step(line[4:].strip(), []))
        elif block == "text" and line.strip() and found and found[-1].shown is not None:
            found[-1].shown.append(line)
    return found


def follow(folder: Path, *, calculations: bool) -> list[tuple[Step, int, list[str]]]:
    """Each step run in `folder`, as the tutorial runs it: the step, its exit code and
    what it printed. The calculations and their results only when `calculations`."""
    done = []
    with pytest.MonkeyPatch.context() as patch:
        patch.chdir(folder)
        for name in ("NO_COLOR", "FORCE_COLOR", "TERM"):
            patch.delenv(name, raising=False)
        for step in steps():
            words = shlex.split(step.command)
            if words[0] == "Copy-Item":
                shutil.copyfile(words[1], words[2])
                continue
            assert words[0] == "kratos-cli", step.command
            if words[1] in RUN_COMMANDS and not calculations:
                continue
            printed = io.StringIO()
            with redirect_stdout(printed), redirect_stderr(io.StringIO()):
                code = main(words[1:])
            done.append((step, code, printed.getvalue().splitlines()))
    return done


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> tuple[Path, list]:
    folder = tmp_path_factory.mktemp("muskat-tutorial")
    return folder, follow(folder, calculations=False)


def test_the_tutorial_shows_its_commands():
    """Or every test below would pass on nothing."""
    words = [shlex.split(step.command)[1] for step in steps() if "kratos-cli" in step.command]
    assert words.count("calculate") == 3
    assert sum(step.shown is not None for step in steps()) >= 15


def test_every_command_succeeds_and_prints_what_the_tutorial_shows(built):
    _, done = built
    wrong = [(step.command, code, printed) for step, code, printed in done
             if code != 0 or (step.shown is not None and printed != step.shown)]
    assert not wrong


@pytest.mark.parametrize("name", MODELS)
def test_the_model_is_the_model_script_s(built, cli, name):
    folder, _ = built
    assert cli("export", folder / name, "--out", folder / f"deck_{name}").code == 0
    with solid_model.session():
        script = writer.export_project(MODELS[name]())

    ours = reference.deck_view(reference.read_deck(folder / f"deck_{name}"))
    assert ours == reference.deck_view(script)


# ── The calculations, in Kratos ─────────────────────────────────────────────

CASE_B_TOLERANCE = {"WATER_PRESSURE": 15.0, "EFFECTIVE_SATURATION": 0.02}
"""Pa, and a fraction of full saturation: what the tutorial's 0.1 m mesh is from Kratos'
values, as the tutorial says. The flux is held where it changes slowly, below the
phreatic line and away from the face (node 273): to 2 % of its length."""


@pytest.fixture(scope="module")
def calculated(tmp_path_factory) -> dict:
    """The steps, the calculations among them; and of the three runs, what is checked:
    A's and B's values at Kratos' nodes, and C's faces."""
    from tests.results_run import require_kratos

    require_kratos()
    folder = tmp_path_factory.mktemp("muskat-tutorial-runs")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(calculation.RUNS_ENV, str(folder / "runs"))
        catalog.forget_cache()
        done = follow(folder, calculations=True)
        runs = [FINISHED.fullmatch(printed[0]).group(1) for step, code, printed in done
                if " calculate " in step.command and code == 0]
        assert len(runs) == 3, [(step.command, printed) for step, _, printed in done]
        a, b, c = ((catalog.stage_mesh(run, 1), catalog.stage_results(run, 1)) for run in runs)
        answer = {"done": done,
                  "a": muskat.at_kratos_nodes(*a, muskat.KRATOS_A),
                  "b": muskat.at_kratos_nodes(*b, muskat.KRATOS_B),
                  "c": muskat.seepage_outcome(*c)}
    catalog.forget_cache()
    return answer


def same_print(step: Step, printed: list[str]) -> bool:
    """`printed` is what the tutorial shows, but for the name, the time and the folder of
    the run `calculate` made."""
    def general(lines: list[str]) -> list[str]:
        ran = FINISHED.fullmatch(lines[0]) if lines else None
        if not ran:
            return lines
        return [f"run finished: {ran.group(2)} files",
                *(line.replace(ran.group(1), "<run>") for line in lines[1:])]
    return general(printed) == general(step.shown or [])


@pytest.mark.kratos
def test_the_calculations_print_what_the_tutorial_shows(calculated):
    wrong = [(step.command, code, printed) for step, code, printed in calculated["done"]
             if code != 0 or (step.shown is not None and not same_print(step, printed))]
    assert not wrong


@pytest.mark.kratos
@pytest.mark.parametrize("node", muskat.KRATOS_A)
def test_case_a_is_kratos_own_answer(calculated, node):
    _, expected = muskat.KRATOS_A[node]
    got = calculated["a"][node]
    for variable, value in expected.items():
        if variable == "FLUID_FLUX_VECTOR":
            assert got[variable][0] == pytest.approx(value[0], rel=1e-4)
            assert abs(got[variable][1]) <= 1e-9
        else:
            assert got[variable][0] == pytest.approx(value, abs=1.0), variable


@pytest.mark.kratos
@pytest.mark.parametrize("node", muskat.KRATOS_B)
def test_case_b_is_kratos_own_answer(calculated, node):
    _, expected = muskat.KRATOS_B[node]
    got = calculated["b"][node]
    for variable, tolerance in CASE_B_TOLERANCE.items():
        if variable in expected:
            assert got[variable][0] == pytest.approx(expected[variable], abs=tolerance)
    if node == 273:
        (qx, qy), (kx, ky) = got["FLUID_FLUX_VECTOR"][:2], expected["FLUID_FLUX_VECTOR"]
        assert math.hypot(qx - kx, qy - ky) <= 0.02 * math.hypot(kx, ky)


@pytest.mark.kratos
def test_case_c_lets_the_water_out_through_its_seepage_face(calculated):
    face, inflow, outflow = calculated["c"]
    assert outflow == pytest.approx(-inflow, rel=1e-3)
    assert muskat.CHARNY_DISCHARGE <= outflow <= 1.02 * muskat.CHARNY_DISCHARGE
    assert 1.7 <= muskat.exit_point(face) <= 2.0
