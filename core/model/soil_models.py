"""The soil models a material can be, and what each one asks of its property set.

A soil is a Kratos property set: a law and its `Variables` (`schemas.Material`). The
material window offers a *soil model* first -- linear elastic or Mohr-Coulomb -- and
this table is what follows from that choice: the law per dimension, the variables the
window lists, in groups, with the value a new soil starts from, the text values Kratos
accepts for each choice, and when a variable is shown at all (a tensile strength only
with the tension cut-off on). A law this table does not know is the user's own ("Other")
and is written as typed.

The browser reads the same table, generated into `frontend/js/soil-model-table.js`
(`python tests/test_soil_model_table.py --write`), and `frontend/js/soil-models.js`
repeats the few functions below; `tests/test_draft_parity.py` holds the two to the same
answers.

Defaults are in SI and expressed in the project's system when used. A parameter without
a default is left out of a new soil: the export derives it (`core/kratos/materials.py`),
or Kratos does.

What Kratos reads was checked in its GeoMechanicsApplication source: the laws registered
in `geo_mechanics_application.cpp`, `MohrCoulombLaw::Check`,
`CoulombYieldSurface::CheckMaterialProperties`, `ConstitutiveLawUtilities::
StringToDrainageType` and `RetentionLawFactory::Clone`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from core.model import units

LINEAR_ELASTIC = "linear_elastic"
MOHR_COULOMB = "mohr_coulomb"
OTHER = "other"
"""A law no model here is: the user's own, typed by name (a UDSM, say)."""

DRAINAGE_TYPES = ("CONSTANT_PW_FIELD", "FULLY_COUPLED", "DRAINED", "UNDRAINED")
"""Every `GEO_DRAINAGE_TYPE` Kratos accepts (`StringToDrainageType`)."""

RETENTION_LAWS = ("SaturatedLaw", "SaturatedBelowPhreaticLevelLaw", "VanGenuchtenLaw")
"""Every `RETENTION_LAW` Kratos builds (`RetentionLawFactory`). Its fourth name,
`PressureFilterLaw`, builds a `SaturatedLaw` and is left out."""

UNSATURATED = ("SaturatedBelowPhreaticLevelLaw", "VanGenuchtenLaw")

WATER_SPECIFIC_WEIGHT_SI = 10_000.0
"""N/m3: the water's specific weight when the project gives none
(`schemas.WATER_SPECIFIC_WEIGHT_SI`)."""
WATER_BULK_MODULUS_SI = 2.2e9
"""Pa, water at 20 C: `BULK_MODULUS_FLUID` when the project gives none."""
WATER_VISCOSITY_SI = 1.0e-3
"""Pa s, water at 20 C: `DYNAMIC_VISCOSITY` when the project gives none."""
WATER = ("DENSITY_WATER", "BULK_MODULUS_FLUID", "DYNAMIC_VISCOSITY")
"""The water's variables. They are the project's (`schemas.Fluid`), one for every soil,
written into each soil by the export and refused on a soil of its own."""


@dataclass(frozen=True)
class Parameter:
    """One variable the material window lists for a model."""
    name: str
    default: Any = None
    """The value a new soil starts with, in SI. None: left out, for the export or Kratos
    to derive."""
    required: bool = False
    """The law cannot run without it, and nothing derives it."""
    choices: tuple[str, ...] = ()
    """The text values Kratos accepts: a drop-down list."""
    flag: bool = False
    """True or false: a check box."""
    absent: Any = None
    """What the deck holds when the variable is left out, for the `when` of another
    parameter: `SaturatedLaw` for a retention law, say."""
    when: tuple[str, tuple] | None = None
    """(variable, values): listed only while that variable is one of these values."""


@dataclass(frozen=True)
class SoilModel:
    id: str
    label: str
    laws: dict[int, str]
    """The law per dimension."""
    old_laws: dict[str, int]
    """Older names of the same law -> their dimension. Recognised as this model and
    replaced by `laws` when a project loads."""
    groups: tuple[tuple[str, tuple[Parameter, ...]], ...]


def _drainage() -> tuple[Parameter, ...]:
    return (Parameter("GEO_DRAINAGE_TYPE", "CONSTANT_PW_FIELD", choices=DRAINAGE_TYPES,
                      absent="CONSTANT_PW_FIELD"),
            Parameter("GEO_POISSON_UNDRAINED", when=("GEO_DRAINAGE_TYPE", ("UNDRAINED",))))


def _stiffness() -> tuple[Parameter, ...]:
    return (Parameter("YOUNG_MODULUS", 1.0e7, required=True),
            Parameter("POISSON_RATIO", 0.3, required=True))


def _weight() -> tuple[Parameter, ...]:
    # Porosity 0, as in Kratos' reference: Kratos weighs a point at
    # (1 - n) DENSITY_SOLID g + n S gamma_w, so the soil weighs DENSITY_SOLID g --
    # 17 kN/m3 here -- above and below the water alike.
    return (Parameter("DENSITY_SOLID", 17000 / 9.81, required=True),
            Parameter("DENSITY_WATER"),
            Parameter("POROSITY", 0.0))


def _flow(retention: str | None) -> tuple[Parameter, ...]:
    saturated = ("RETENTION_LAW", UNSATURATED)
    van_genuchten = ("RETENTION_LAW", ("VanGenuchtenLaw",))
    return (Parameter("PERMEABILITY_XX", 1 / 86400),
            Parameter("PERMEABILITY_YY"),
            Parameter("RETENTION_LAW", retention, choices=RETENTION_LAWS,
                      absent="SaturatedLaw"),
            Parameter("SATURATED_SATURATION", 1.0, when=saturated),
            Parameter("RESIDUAL_SATURATION", 1.0e-10, when=saturated),
            Parameter("MINIMUM_RELATIVE_PERMEABILITY", 1.0e-4, when=saturated),
            # Kratos' tests/Muskat/van_genuchten_hydrostatic.
            Parameter("VAN_GENUCHTEN_AIR_ENTRY_PRESSURE", 2611.0, when=van_genuchten),
            Parameter("VAN_GENUCHTEN_GN", 1.377, when=van_genuchten),
            Parameter("VAN_GENUCHTEN_GL", 1.25, when=van_genuchten))


def _pore_fluid() -> tuple[Parameter, ...]:
    return (Parameter("BULK_MODULUS_SOLID"), Parameter("BULK_MODULUS_FLUID"),
            Parameter("BIOT_COEFFICIENT"))


MODELS: dict[str, SoilModel] = {
    LINEAR_ELASTIC: SoilModel(
        id=LINEAR_ELASTIC, label="Linear elastic",
        # GeoMechanics registers no `GeoLinearElastic3DLaw`; its one 3D linear elastic
        # soil law is the incremental one.
        laws={2: "GeoLinearElasticPlaneStrain2DLaw", 3: "GeoIncrementalLinearElastic3DLaw"},
        old_laws={},
        groups=(
            ("Drainage", _drainage()),
            ("Stiffness", _stiffness()),
            ("Weight", _weight()),
            ("Flow", _flow(None)),
            # Not read by the elastic law: an interface along the soil takes them, and
            # K0 follows from the friction angle.
            ("Strength", (Parameter("GEO_COHESION", 0.0),
                          Parameter("GEO_FRICTION_ANGLE", 30.0))),
            ("Pore fluid", _pore_fluid()),
            ("Initial stresses", (Parameter("K0_NC"),)),
        )),
    MOHR_COULOMB: SoilModel(
        id=MOHR_COULOMB, label="Mohr-Coulomb",
        laws={2: "GeoMohrCoulombLawPlaneStrain", 3: "GeoMohrCoulombLaw3D"},
        # Registered still, and "Deprecated! ... will be removed".
        old_laws={"GeoMohrCoulombWithTensionCutOff2D": 2,
                  "GeoMohrCoulombWithTensionCutOff3D": 3},
        groups=(
            ("Drainage", _drainage()),
            ("Stiffness", _stiffness()),
            ("Weight", _weight()),
            ("Flow", _flow("SaturatedBelowPhreaticLevelLaw")),
            # A cohesion of 1 kPa, not 0: with none the yield surface has its apex at
            # zero stress, and the ground surface, where the stress is near zero, keeps
            # a Newton-Raphson run from converging.
            ("Strength", (
                Parameter("GEO_COHESION", 1000.0, required=True),
                Parameter("GEO_FRICTION_ANGLE", 30.0, required=True),
                Parameter("GEO_DILATANCY_ANGLE", 0.0, required=True),
                Parameter("GEO_ENABLE_TENSION_CUT_OFF", False, flag=True, absent=False),
                Parameter("GEO_TENSILE_STRENGTH", 0.0, required=True,
                          when=("GEO_ENABLE_TENSION_CUT_OFF", (True,))),
            )),
            ("Pore fluid", _pore_fluid()),
            ("Initial stresses", (Parameter("K0_NC"),)),
        )),
}

_BY_LAW = {law: model.id for model in MODELS.values()
           for law in [*model.laws.values(), *model.old_laws]}


def model_of(law: str) -> str:
    """The model `law` is, under any of its names, or `OTHER`."""
    return _BY_LAW.get(law, OTHER)


def label(model: str) -> str:
    return MODELS[model].label if model in MODELS else "Other"


def law(model: str, dim: int) -> str:
    """The law of `model` in a model of dimension `dim`."""
    try:
        return MODELS[model].laws[3 if dim == 3 else 2]
    except KeyError:
        raise ValueError(f"there is no soil model {model!r}; there are: "
                         + ", ".join(MODELS)) from None


def law_in(name: str, dim: int) -> str:
    """`name` as a model of dimension `dim` writes it: the current law of its model in
    that dimension, or `name` itself when no model here is that law."""
    model = model_of(name)
    return name if model == OTHER else law(model, dim)


def law_dimension(name: str) -> int | None:
    """The dimension `name` is a law of, when it is a model's law; None otherwise."""
    model = MODELS.get(model_of(name))
    if model is None:
        return None
    for dim, current in model.laws.items():
        if current == name:
            return dim
    return model.old_laws[name]


def parameters(model: str) -> list[Parameter]:
    """Every parameter of `model`, in the window's order."""
    found = MODELS.get(model)
    return [] if found is None else [p for _, group in found.groups for p in group]


def _holds(parameter: Parameter, variables: dict, model: str) -> bool:
    if parameter.when is None:
        return True
    name, values = parameter.when
    other = next((p for p in parameters(model) if p.name == name), None)
    value = variables.get(name, other.absent if other is not None else None)
    return value in values and isinstance(value, bool) == isinstance(values[0], bool)


def shown(model: str, variables: dict) -> list[Parameter]:
    """The parameters the window lists for a soil of `model` holding `variables`."""
    return [p for p in parameters(model) if _holds(p, variables, model)]


def required(name: str, variables: dict) -> list[str]:
    """What the law `name` cannot run without, for a soil holding `variables`."""
    return [p.name for p in shown(model_of(name), variables) if p.required]


def fill(before_law: str | None, before: dict, after_law: str, after: dict,
         system: str, skip: tuple[str, ...] = ()) -> list[str]:
    """Fill into `after` the defaults of what a soil now lists and lacks.

    The soil was `before_law` holding `before` (None and {}: a new soil) and is now
    `after_law` holding `after`. A parameter its model lists for `after` that `after`
    lacks gets its default in `system` when

    *   the soil is new or changed model: every one, so a soil switched to Mohr-Coulomb
        is ready to run;
    *   the model stayed and the parameter was not listed before: a retention law chosen
        brings its saturations, a cut-off switched on its tensile strength. One that was
        listed and is left out stays out, for the export to derive;
    *   the law cannot run without it.

    Nothing the soil holds is replaced, nor is a name in `skip` filled. Returns the names
    filled, in the order filled."""
    model = model_of(after_law)
    old: set[str] = set()
    if before_law is not None and model_of(before_law) == model:
        old = {p.name for p in shown(model, before)}
    filled: list[str] = []
    while True:
        # Listed anew after each fill: a retention law filled lists its saturations.
        for p in shown(model, after):
            if (p.name not in after and p.name not in skip and p.default is not None
                    and (p.name not in old or p.required)):
                after[p.name] = default_in(p, system)
                filled.append(p.name)
                break
        else:
            return filled


def default_in(parameter: Parameter, system: str) -> Any:
    """`parameter`'s default in the unit system `system`; None when it has none."""
    value = parameter.default
    quantity = units.VARIABLES.get(parameter.name)
    if quantity is None or value is None or isinstance(value, (bool, str)):
        return value
    return units.convert(float(value), quantity, "SI", system)


def defaults_si(model: str) -> dict:
    """The variables a new soil of `model` starts with, in SI."""
    out: dict = {}
    fill(None, {}, law(model, 2), out, "SI")
    return out


def filled_note(model: str, names: list[str]) -> str | None:
    """What `fill` did, as the window and the command line both say it."""
    if not names:
        return None
    return f"Filled in from the {label(model)} defaults: {', '.join(names)}."


# ── The water, and what follows from a soil's numbers ───────────────────────

def water(system: str, specific_weight: float | None = None,
          bulk_modulus: float | None = None, viscosity: float | None = None) -> dict:
    """The water every soil shares as Kratos reads it, in `system`: the project's
    values (`schemas.Fluid`, `WaterLevel.specific_weight`), water's where it gives
    none."""
    weight = (specific_weight if specific_weight is not None else
              units.from_si(WATER_SPECIFIC_WEIGHT_SI, units.SPECIFIC_WEIGHT, system))
    return {
        "DENSITY_WATER": weight / units.gravity(system),
        "BULK_MODULUS_FLUID": (bulk_modulus if bulk_modulus is not None else
                               units.from_si(WATER_BULK_MODULUS_SI, units.STRESS, system)),
        "DYNAMIC_VISCOSITY": (viscosity if viscosity is not None else
                              units.from_si(WATER_VISCOSITY_SI, units.VISCOSITY, system)),
    }


def problem(name: str, variables: dict) -> str | None:
    """Why Kratos would refuse the soil, beyond a missing variable: the bounds
    `MohrCoulombLaw::Check` and `CoulombYieldSurface` hold between its variables."""
    if model_of(name) != MOHR_COULOMB:
        return None

    def number(key: str) -> float | None:
        value = variables.get(key)
        return None if isinstance(value, bool) or not isinstance(value, (int, float)) \
            else float(value)

    phi, psi = number("GEO_FRICTION_ANGLE"), number("GEO_DILATANCY_ANGLE")
    cohesion, tension = number("GEO_COHESION"), number("GEO_TENSILE_STRENGTH")
    if phi is not None and not phi < 90:
        return "GEO_FRICTION_ANGLE must be below 90 degrees."
    if phi is not None and psi is not None and psi > phi:
        return "GEO_DILATANCY_ANGLE cannot be larger than GEO_FRICTION_ANGLE."
    cut_off = variables.get("GEO_ENABLE_TENSION_CUT_OFF")
    if (cut_off is True or (cut_off is None and tension is not None)) \
            and tension is not None and cohesion is not None and phi is not None and phi > 0:
        limit = cohesion / math.tan(math.radians(phi))
        if tension > limit * (1 + 1e-12):
            return (f"GEO_TENSILE_STRENGTH cannot be larger than GEO_COHESION / "
                    f"tan(GEO_FRICTION_ANGLE) = {limit:.6g}.")
    return None


def table() -> dict:
    """The catalogue as the browser reads it (`App.SOIL_MODEL_TABLE`)."""
    def parameter(p: Parameter) -> dict:
        out: dict = {"name": p.name}
        if p.default is not None:
            out["default"] = p.default
        if p.required:
            out["required"] = True
        if p.choices:
            out["choices"] = list(p.choices)
        if p.flag:
            out["flag"] = True
        if p.absent is not None:
            out["absent"] = p.absent
        if p.when is not None:
            out["when"] = {"name": p.when[0], "values": list(p.when[1])}
        return out

    return {"order": list(MODELS), "other": OTHER, "models": {
        model.id: {"label": model.label,
                   "laws": {str(dim): name for dim, name in model.laws.items()},
                   "old_laws": dict(model.old_laws),
                   "groups": [{"title": title, "parameters": [parameter(p) for p in group]}
                              for title, group in model.groups]}
        for model in MODELS.values()}}
