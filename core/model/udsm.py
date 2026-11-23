"""The UDSM libraries that come with Styx, and the soil models they hold.

The libraries are the .dll files in `udsm_libraries/`. Each is read by `udsm_parser.py`,
in a process of its own, the first time it is asked for: its models, and per model the name
and unit of each parameter, in the order Kratos takes them in `UMAT_PARAMETERS`. On Linux
a library is read, and run by Kratos, from the .so of the same name beside it (Kratos'
`SmallStrainUDSMLaw` swaps the extension); a .dll without one is not listed there.

A library says nothing of start values, nor which parameter is the stiffness or the
strength. What is known of a model beyond what it says is in `KNOWN`: its start values,
with their source, and which parameters are Young's modulus, Poisson's ratio, the
cohesion, the friction angle and the dilatancy angle. The K0 stage runs a UDSM soil on
the linear elastic law with that Young's modulus and Poisson's ratio
(`core/kratos/materials.py`); a contact takes the strength from those parameters. A
model not in `KNOWN` starts at zeros, and its soil is typed in full by the user.

The names come in the libraries' own markup: `@n#` is the Greek letter the Symbol font
draws for `n` (nu), `_` starts a subscript, `#` ends a group and `|...|` marks an
absolute value. `label` makes them readable, `key` a word to type on the command line.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from core.model import units

FOLDER = Path(__file__).resolve().parent / "udsm_libraries"
PARSER = Path(__file__).resolve().parent / "udsm_parser.py"
DECK_FOLDER = "udsm"
"""Where the export puts the libraries a deck uses, beside its other files: `UDSM_NAME`
is written as `udsm/<file>`, which Kratos opens from the folder it runs in."""

VARIABLES = ("UDSM_NAME", "UDSM_NUMBER", "IS_FORTRAN_UDSM", "UMAT_PARAMETERS",
             "INDEX_OF_UMAT_C_PARAMETER", "INDEX_OF_UMAT_PHI_PARAMETER")
"""What a UDSM soil holds of its law, under Kratos' names: the library, the model in it,
that it is written in Fortran, the parameters in the library's order, and which of them
are the cohesion and the friction angle, 1-based, which Kratos' K0 procedure and c-phi
reduction read."""

UNITS = {
    "F/L2": units.STRESS, "F/L": units.LINE_FORCE, "F": units.FORCE,
    "F/L3": units.SPECIFIC_WEIGHT, "L": units.LENGTH, "T": units.TIME,
    "L/T": units.VELOCITY, "L2": units.AREA, "deg": units.ANGLE, "-": units.DIMENSIONLESS,
    "": units.DIMENSIONLESS,
}
"""A library's unit (F force, L length, T time) -> the quantity, in the project's units.
A unit not here is shown as the library writes it, and a change of unit system keeps
that parameter as typed."""

GREEK = dict(zip("abcdefghijklmnopqrstuvwxyzABDFGLPQSWXY",
                 "αβχδεφγηιϕκλμνοπθρστυϖωξψζΑΒΔΦΓΛΠΘΣΩΞΨ"))
"""The Symbol font's letters: what `@n#` in a library's name is drawn as."""

LATIN = {"α": "alpha", "β": "beta", "χ": "chi", "δ": "delta", "ε": "epsilon", "φ": "phi",
         "γ": "gamma", "η": "eta", "ι": "iota", "ϕ": "phi", "κ": "kappa", "λ": "lambda",
         "μ": "mu", "ν": "nu", "ο": "omicron", "π": "pi", "θ": "theta", "ρ": "rho",
         "σ": "sigma", "τ": "tau", "υ": "upsilon", "ϖ": "pi", "ω": "omega", "ξ": "xi",
         "ψ": "psi", "ζ": "zeta", "Α": "Alpha", "Β": "Beta", "Δ": "Delta", "Φ": "Phi",
         "Γ": "Gamma", "Λ": "Lambda", "Π": "Pi", "Θ": "Theta", "Σ": "Sigma",
         "Ω": "Omega", "Ξ": "Xi", "Ψ": "Psi"}


@dataclass(frozen=True)
class Known:
    """What Styx knows of a model beyond what its library says."""
    defaults: tuple[float, ...]
    """The start values, in SI, in the library's order."""
    source: str
    roles: dict[str, int] = field(default_factory=dict)
    """Kratos variable -> the 1-based parameter that is it: `YOUNG_MODULUS`,
    `POISSON_RATIO`, `GEO_COHESION`, `GEO_FRICTION_ANGLE`, `GEO_DILATANCY_ANGLE`."""


KNOWN: dict[tuple[str, int], Known] = {
    # E and nu are the built-in Mohr-Coulomb model's defaults (soil_models.MODELS), so a
    # soil switched between the two keeps its stiffness; the rest are the Kratos deck's.
    ("MohrCoulomb64.dll", 1): Known(
        defaults=(1.0e7, 0.3, 1000.0, 30.0, 0.0, 1000.0, 1.0, 0.0),
        source="Kratos GeoMechanicsApplication, tests/C-Phi_reduction_process/"
               "Mohr_Coulomb_model64/MaterialParameters_stage2.json",
        roles={"YOUNG_MODULUS": 1, "POISSON_RATIO": 2, "GEO_COHESION": 3,
               "GEO_FRICTION_ANGLE": 4, "GEO_DILATANCY_ANGLE": 5}),
}


class LibraryError(RuntimeError):
    """A library cannot be read."""


@dataclass(frozen=True)
class Parameter:
    name: str
    """As the library writes it, without its number."""
    label: str
    key: str
    unit: str
    """As the library writes it."""
    quantity: units.Quantity | None


@dataclass(frozen=True)
class Model:
    file: str
    number: int
    name: str
    parameters: tuple[Parameter, ...]
    defaults: tuple[float, ...]
    """In SI: `KNOWN`'s, or zeros."""
    known: bool
    roles: dict[str, int]
    source: str = ""

    @property
    def id(self) -> str:
        """The word that names it: the library's file name without `.dll`, and its
        number: `MohrCoulomb64:1`."""
        return f"{Path(self.file).stem}:{self.number}"

    def index(self, key: str) -> int | None:
        """The 0-based position of the parameter `key`, or None."""
        return next((i for i, p in enumerate(self.parameters) if p.key == key), None)


# ── The libraries' names, made readable ─────────────────────────────────────

def _bare(raw: str) -> str:
    """`raw` without its leading number (`1. E` -> `E`)."""
    return re.sub(r"^\s*\d+\s*[.)]\s*", "", raw).strip()


def label(raw: str) -> str:
    """A parameter's name as the window shows it: `@n#_ur` -> `ν_ur`,
    `|@s#_t, cut-off#|` -> `σ_t, cut-off`."""
    text = re.sub(r"@(\w)#?", lambda m: GREEK.get(m.group(1), m.group(1)), _bare(raw))
    return re.sub(r"\s+", " ", text.replace("#", "").replace("|", "")).strip()


def key(readable: str) -> str:
    """A label as a word to type: `ν_ur` -> `nu_ur`, `c'` -> `c`, `σ_t, cut-off` ->
    `sigma_t_cut_off`, `yield function (MC=1; ...)` -> `yield_function`."""
    text = readable.split("(")[0]
    text = "".join(LATIN.get(ch, ch) for ch in text)
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_") or "parameter"


def quantity(unit: str) -> units.Quantity | None:
    return UNITS.get(unit.replace("#", "").replace("^", "").strip())


def unit_label(parameter: Parameter, system: str) -> str:
    """The parameter's unit in the project's system, or the library's own."""
    if parameter.quantity is None:
        return parameter.unit.replace("#", "")
    return units.label(parameter.quantity, system)


def model(file: str, read: dict) -> Model:
    """One model of the library `file`, from what `udsm_parser.read` gives of it."""
    parameters: list[Parameter] = []
    for raw in read["parameters"]:
        readable = label(raw["name"])
        word, n = key(readable), 2
        while any(p.key == word for p in parameters):
            word, n = f"{key(readable)}_{n}", n + 1
        parameters.append(Parameter(_bare(raw["name"]), readable, word, raw["unit"],
                                    quantity(raw["unit"])))
    known = KNOWN.get((file, read["number"]))
    if known is not None and len(known.defaults) != len(parameters):
        known = None
    return Model(file=file, number=read["number"], name=label(read["name"]) or file,
                 parameters=tuple(parameters),
                 defaults=known.defaults if known else (0.0,) * len(parameters),
                 known=known is not None, roles=dict(known.roles) if known else {},
                 source=known.source if known else "")


# ── Reading the libraries ───────────────────────────────────────────────────

def files() -> list[Path]:
    return sorted(FOLDER.glob("*.dll"), key=lambda path: path.name.lower())


def loadable(path: Path) -> Path | None:
    """What this system loads for the library `path`: the .dll on Windows, the .so of
    the same name elsewhere, when there is one."""
    if sys.platform == "win32":
        return path
    so = path.with_suffix(".so")
    return so if so.exists() else None


@lru_cache(maxsize=None)
def _read(path: str, stamp: tuple[int, int]) -> dict:
    """`udsm_parser.read` of `path`, in a process of its own; `stamp` (size, mtime) reads it
    again when the file changes."""
    try:
        done = subprocess.run([sys.executable, "-I", str(PARSER), path],
                              capture_output=True, text=True, timeout=60, check=False)
    except subprocess.TimeoutExpired:
        raise LibraryError(f"{Path(path).name} did not answer within 60 s") from None
    if done.returncode != 0:
        why = (done.stderr.strip().splitlines() or [f"exit code {done.returncode}"])[-1]
        raise LibraryError(f"{Path(path).name} cannot be read: {why}")
    return json.loads(done.stdout)


def read(path: Path) -> dict:
    stat = path.stat()
    return _read(str(path), (stat.st_size, stat.st_mtime_ns))


def scan() -> tuple[list[Model], list[str]]:
    """Every model of every library this system can load, and why a library is left
    out."""
    found: list[Model] = []
    problems: list[str] = []
    for path in files():
        target = loadable(path)
        if target is None:
            problems.append(f"{path.name} has no {path.stem}.so beside it, so it cannot "
                            "run on this system")
            continue
        try:
            answer = read(target)
        except (LibraryError, OSError, ValueError) as failure:
            problems.append(str(failure))
            continue
        found.extend(model(path.name, entry) for entry in answer["models"])
    return found, problems


_override: list[list[Model]] = []


def models() -> list[Model]:
    """The models the soil window and `kratos-cli material udsm` offer."""
    return _override[-1] if _override else scan()[0]


def problems() -> list[str]:
    return [] if _override else scan()[1]


class using:
    """`with using([...]):` -- these models in place of the libraries' (tests)."""

    def __init__(self, replacement: list[Model]) -> None:
        self.replacement = replacement

    def __enter__(self) -> list[Model]:
        _override.append(self.replacement)
        return self.replacement

    def __exit__(self, *_exc: object) -> None:
        _override.pop()


def find(file: object, number: object) -> Model | None:
    """The model `number` of the library `file` (its name only, or a deck's
    `udsm/<file>`), or None."""
    if not isinstance(file, str) or isinstance(number, bool) or not isinstance(number, int):
        return None
    name = Path(file.replace("\\", "/")).name.lower()
    return next((m for m in models() if m.file.lower() == name and m.number == number), None)


def by_id(word: str) -> Model:
    """The model named `word` (`Model.id`, or its library's name when it holds one)."""
    available = models()
    for m in available:
        if word.lower() in (m.id.lower(), f"{m.file.lower()}:{m.number}"):
            return m
    single = [m for m in available if Path(m.file).stem.lower() == word.lower()]
    if len(single) == 1:
        return single[0]
    names = ", ".join(m.id for m in available) or "none on this system"
    raise LookupError(f"there is no UDSM model {word!r}; there are: {names}")


def path(model: Model) -> Path:
    return FOLDER / model.file


def deck_files(model: Model) -> dict[str, str]:
    """What a deck that uses `model` needs beside it: published path -> the file here.
    The .so goes too when there is one, so the deck runs on Linux as well."""
    out = {f"{DECK_FOLDER}/{model.file}": str(path(model))}
    so = path(model).with_suffix(".so")
    if so.exists():
        out[f"{DECK_FOLDER}/{so.name}"] = str(so)
    return out


def table(models_: list[Model] | None = None, problems_: list[str] | None = None) -> dict:
    """The models as the browser reads them (`App.UDSM_LIBRARY`)."""
    listed = models() if models_ is None else models_
    return {
        "models": [{
            "id": m.id, "file": m.file, "number": m.number, "name": m.name,
            "known": m.known, "source": m.source, "defaults": list(m.defaults),
            "roles": dict(m.roles),
            "parameters": [{"name": p.name, "label": p.label, "key": p.key, "unit": p.unit,
                            "quantity": p.quantity.name if p.quantity else None}
                           for p in m.parameters]}
            for m in listed],
        "problems": problems() if problems_ is None else problems_,
    }
