"""The soil models a material can be, and what each one asks of its property set.

A soil is a Kratos property set: a law and its `Variables` (`schemas.Material`). The
material window offers a *soil model* first -- linear elastic or Mohr-Coulomb -- and
this table is what follows from that choice: the law per dimension, the variables the
window lists, in groups, with the value a new soil starts from, the text values Kratos
accepts for each choice, and when a variable is shown at all (a tensile strength only
with the tension cut-off on). A law this table does not know is the user's own ("Other")
and is written as typed.

The window lists what the choices make relevant and nothing else: a linear elastic soil
has no strength, a soil that is not `FULLY_COUPLED` no flow parameters (unless the whole
project is a groundwater flow calculation), and the water -- its weight, bulk modulus
and viscosity -- is the project's, one for every soil (`schemas.Fluid`), not a soil's.
What the export derives when a soil leaves it out (`derived`) and what follows from the
soil's numbers (`computed`: its unit weights, its Darcy conductivity) are shown beside
what is typed, with their values.

The browser reads the same table, generated into `frontend/js/soil-model-table.js`
(`python tests/test_soil_model_table.py --write`), and `frontend/js/soil-models.js`
repeats the functions below; `tests/test_draft_parity.py` holds the two to the same
answers.

Defaults are in SI and expressed in the project's system when used. A parameter without
a default is left out of a new soil: the export derives it (`derived`), or Kratos does.

What Kratos reads was checked in its GeoMechanicsApplication source: the laws registered
in `geo_mechanics_application.cpp`, `MohrCoulombLaw::Check`,
`CoulombYieldSurface::CheckMaterialProperties`, `ConstitutiveLawUtilities::
StringToDrainageType` and `RetentionLawFactory::Clone`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Iterable
from typing import Any

from core.model import units

LINEAR_ELASTIC = "linear_elastic"
MOHR_COULOMB = "mohr_coulomb"
OTHER = "other"
"""A law no model here is: the user's own, typed by name (a UDSM, say)."""

DRAINAGE_TYPES = ("DRAINED", "FULLY_COUPLED", "UNDRAINED")
"""The `GEO_DRAINAGE_TYPE`s a soil can have, as the project, the window and the command
line name them. The deck writes `DRAINED` as `CONSTANT_PW_FIELD` (`KRATOS_DRAINAGE`)."""

KRATOS_DRAINAGE = {"DRAINED": "CONSTANT_PW_FIELD"}
"""Drainage type -> the `GEO_DRAINAGE_TYPE` the deck writes for it, where they differ
(`kratos_drainage`).

Drained means the pore pressures do not follow the deformation: they are the ones the
water conditions set. Kratos' `CONSTANT_PW_FIELD` is exactly that -- its U-Pw elements
leave out the flow, storage and water-coupling terms and keep the pressure as it is
given. Kratos' own `DRAINED` is not: its elements assemble it as a `FULLY_COUPLED` soil
(`UPwSmallStrainElement`; nothing in `GeoMechanicsApplication` reads
`DrainageType::DRAINED`), drained only as far as its permeability lets the water go. So a
drained soil is written as `CONSTANT_PW_FIELD`, and Kratos' `DRAINED` is not offered."""

OLD_DRAINAGE = {"CONSTANT_PW_FIELD": "DRAINED"}
"""A `GEO_DRAINAGE_TYPE` the project held before 2026-11-04 -> its name now
(`project_drainage`). Read in a saved project, a script or a deck, it is renamed: the deck
it writes does not change."""

FLOWING = ("FULLY_COUPLED",)
"""The drainage types the window lists flow parameters for.

A drained soil is written as `CONSTANT_PW_FIELD`, for which Kratos' U-Pw elements leave
the flow terms out and check no permeability, viscosity or fluid bulk modulus. An
`UNDRAINED` soil is assembled, and checked, with them as a `FULLY_COUPLED` one is
(`UPwSmallStrainElement::Check`): for it the drainage type is the physics, not a
permeability, and the export gives it a fixed one (`FIXED_PERMEABILITY_SI`), which the
window does not list."""

FIXED_PERMEABILITY_SI = {"UNDRAINED": 1.0e-30}
"""m2: the intrinsic permeability the export writes for an `UNDRAINED` soil, whatever the
soil carries: so tight that no water flows. Neither shown nor typed: the drainage type is
the user's choice (`fixed_permeability`)."""

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

BULK_MODULUS_SOLID_SI = 1.0e10
"""Pa, the reference deck's own value: `BULK_MODULUS_SOLID` when a soil gives none."""
PERMEABILITY_SI = 1.0 / 86400 * WATER_VISCOSITY_SI / WATER_SPECIFIC_WEIGHT_SI
"""m2: the intrinsic permeability of a soil that conducts water at 1 m/day,
k mu / gamma_w. `PERMEABILITY_XX` is intrinsic -- Kratos divides it by the viscosity
(`GeoTransportEquationUtilities::CalculatePermeabilityMatrix`) -- not a Darcy
conductivity."""
MINIMUM_RELATIVE_PERMEABILITY = 1.0e-4
"""`MINIMUM_RELATIVE_PERMEABILITY` when a soil gives none. Only a soil whose water flows
reads it, but Kratos' U-Pw elements check it for every soil whose retention law is one of
`UNSATURATED`, whatever its drainage type: the export derives it for those."""
VAN_GENUCHTEN_GL = 1.25
"""`VAN_GENUCHTEN_GL` when a soil gives none. As `MINIMUM_RELATIVE_PERMEABILITY`: only a
soil whose water flows reads it, but `VanGenuchtenLaw::Check` asks for it whatever the
drainage type, so the export derives it for every soil with that law."""
HARDENING_TYPES = ("None", "Linear")
"""Every `GEO_COULOMB_HARDENING_TYPE` Kratos builds (`CoulombYieldSurface`, which reads
it in any case). Left out, it is "None"."""
VECTORS = ("GEO_COHESION_FUNCTION_COEFFICIENTS", "GEO_FRICTION_ANGLE_FUNCTION_COEFFICIENTS",
           "GEO_DILATANCY_ANGLE_FUNCTION_COEFFICIENTS")
"""Variables Kratos reads as a `Vector` and the project holds as their one entry, the
slope of a linear hardening: the export writes a number given as `[number]`."""
UNDRAINED_POISSON_LIMIT = 0.495
"""Kratos clamps an undrained Poisson ratio to this
(`ConstitutiveLawUtilities::GetOrCalculateUndrainedPoissonsRatio`)."""


PALETTE = ("#d8c48a", "#8fa86b", "#6f8fa8", "#c4785a", "#9a80b0", "#5fa89f",
           "#b08a6a", "#b0606f", "#7f9f3f", "#4f6f9f", "#d89a4a", "#8d8d99")
"""Earthy colours a new soil takes, far enough apart that soils side by side in a
section can be told from each other, and none the grey of the mesh (`fresh_color`)."""


def fresh_color(used: Iterable[str], preferred: str | None = None) -> str:
    """A colour no soil has yet, `used` being the project's: `preferred` -- a preset's
    own -- while it is free, else the palette's first free one, then hues a golden angle
    apart once the palette is spent, so every soil added looks different. What the
    material window and `kratos-cli material add` give a new, duplicated or preset soil
    (`App.SoilModels.freshColor`)."""
    taken = {str(color).lower() for color in used}
    if preferred is not None and preferred.lower() not in taken:
        return preferred
    for color in PALETTE:
        if color not in taken:
            return color
    n = 0
    while True:
        color = _hsl((n * 137.508) % 360, 0.45, 0.6)
        if color not in taken:
            return color
        n += 1


def _hsl(h: float, s: float, light: float) -> str:
    """`#rrggbb` of a hue in degrees, a saturation and a lightness, as the browser's
    twin rounds it (half up)."""
    a = s * min(light, 1 - light)

    def channel(n: int) -> str:
        k = (n + h / 30) % 12
        v = light - a * max(-1, min(k - 3, 9 - k, 1))
        return f"{math.floor(v * 255 + 0.5):02x}"
    return "#" + channel(0) + channel(8) + channel(4)


@dataclass(frozen=True)
class Parameter:
    """One variable the material window lists for a model."""
    name: str
    label: str
    """What the window calls it. The Kratos name is its tooltip, and what is written."""
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
    flow: bool = False
    """Read for the water flowing through the soil: listed only for a soil whose
    drainage is one of `FLOWING`, or in a groundwater flow project."""


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
    return (Parameter("GEO_DRAINAGE_TYPE", "Drainage type", "DRAINED",
                      choices=DRAINAGE_TYPES, absent="DRAINED"),
            Parameter("GEO_POISSON_UNDRAINED", "Undrained Poisson's ratio",
                      when=("GEO_DRAINAGE_TYPE", ("UNDRAINED",))))


def _stiffness() -> tuple[Parameter, ...]:
    return (Parameter("YOUNG_MODULUS", "Young's modulus", 1.0e7, required=True),
            Parameter("POISSON_RATIO", "Poisson's ratio", 0.3, required=True))


def _weight() -> tuple[Parameter, ...]:
    # Porosity 0, as in Kratos' reference: Kratos weighs a point at
    # (1 - n) DENSITY_SOLID g + n S gamma_w, so the soil weighs DENSITY_SOLID g --
    # 17 kN/m3 here -- above and below the water alike. Nothing derives a porosity: it
    # is the soil's, and Kratos' U-Pw elements check it.
    return (Parameter("DENSITY_SOLID", "Density of the solid", 17000 / 9.81,
                      required=True),
            Parameter("POROSITY", "Porosity", 0.0, required=True))


def _saturation() -> tuple[Parameter, ...]:
    """The retention law: how full of water the pores are, which weighs the soil whatever
    its drainage. Saturated below the phreatic level and residual above it, unless the
    user says otherwise."""
    unsaturated = ("RETENTION_LAW", UNSATURATED)
    van_genuchten = ("RETENTION_LAW", ("VanGenuchtenLaw",))
    return (Parameter("RETENTION_LAW", "Retention law", "SaturatedBelowPhreaticLevelLaw",
                      choices=RETENTION_LAWS, absent="SaturatedLaw"),
            Parameter("SATURATED_SATURATION", "Saturated saturation", 1.0,
                      when=unsaturated),
            Parameter("RESIDUAL_SATURATION", "Residual saturation", 1.0e-10,
                      when=unsaturated),
            # Kratos' tests/Muskat/van_genuchten_hydrostatic.
            Parameter("VAN_GENUCHTEN_AIR_ENTRY_PRESSURE", "Air entry pressure", 2611.0,
                      when=van_genuchten),
            Parameter("VAN_GENUCHTEN_GN", "Pore size distribution index g_n", 1.377,
                      when=van_genuchten))


def _flow() -> tuple[Parameter, ...]:
    unsaturated = ("RETENTION_LAW", UNSATURATED)
    van_genuchten = ("RETENTION_LAW", ("VanGenuchtenLaw",))
    return (Parameter("PERMEABILITY_XX", "Intrinsic permeability xx", PERMEABILITY_SI,
                      flow=True),
            Parameter("PERMEABILITY_YY", "Intrinsic permeability yy", flow=True),
            Parameter("MINIMUM_RELATIVE_PERMEABILITY", "Minimum relative permeability",
                      MINIMUM_RELATIVE_PERMEABILITY, when=unsaturated, flow=True),
            Parameter("VAN_GENUCHTEN_GL", "Relative permeability exponent g_l", VAN_GENUCHTEN_GL,
                      when=van_genuchten, flow=True))


def _grain_water() -> tuple[Parameter, ...]:
    """Read where the pore water carries load: a coupled soil's storage and an undrained
    one's Skempton B (`ConstitutiveLawUtilities::GetOrCalculateSkemptonB`)."""
    loaded = ("GEO_DRAINAGE_TYPE", ("FULLY_COUPLED", "UNDRAINED"))
    return (Parameter("BULK_MODULUS_SOLID", "Bulk modulus of the grains", when=loaded),
            Parameter("BIOT_COEFFICIENT", "Biot coefficient", when=loaded))


def _hardening() -> tuple[Parameter, ...]:
    """Kratos' linear Coulomb hardening (`CoulombYieldSurface`): each strength grows with
    the equivalent plastic strain kappa, as c + a_c kappa, phi + a_phi kappa and
    psi + a_psi kappa, the angles' slopes in radians. Once it is on, Kratos wants all
    three slopes, none negative: each starts at 0, a strength that does not grow, and
    one left out is written as 0 (`derived`). Off -- left out -- unless the user asks."""
    linear = ("GEO_COULOMB_HARDENING_TYPE", ("Linear",))
    return (Parameter("GEO_COULOMB_HARDENING_TYPE", "Hardening", choices=HARDENING_TYPES,
                      absent="None"),
            Parameter("GEO_COHESION_FUNCTION_COEFFICIENTS", "Cohesion slope", 0.0,
                      when=linear),
            Parameter("GEO_FRICTION_ANGLE_FUNCTION_COEFFICIENTS", "Friction angle slope",
                      0.0, when=linear),
            Parameter("GEO_DILATANCY_ANGLE_FUNCTION_COEFFICIENTS", "Dilatancy angle slope",
                      0.0, when=linear))


def _initial_stresses() -> tuple[Parameter, ...]:
    return (Parameter("K0_NC", "K0, normally consolidated"),)


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
            ("Saturation", _saturation()),
            ("Flow", _flow()),
            ("Grain-water interaction", _grain_water()),
            # No strength: the elastic law reads none, and its K0 follows from the
            # Poisson ratio (`derived`).
            ("Initial stresses", _initial_stresses()),
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
            ("Saturation", _saturation()),
            ("Flow", _flow()),
            ("Grain-water interaction", _grain_water()),
            # A cohesion of 1 kPa, not 0: with none the yield surface has its apex at
            # zero stress, and the ground surface, where the stress is near zero, keeps
            # a Newton-Raphson run from converging.
            ("Strength", (
                Parameter("GEO_COHESION", "Cohesion", 1000.0, required=True),
                Parameter("GEO_FRICTION_ANGLE", "Friction angle", 30.0, required=True),
                Parameter("GEO_DILATANCY_ANGLE", "Dilatancy angle", 0.0, required=True),
                Parameter("GEO_ENABLE_TENSION_CUT_OFF", "Tension cut-off", False,
                          flag=True, absent=False),
                Parameter("GEO_TENSILE_STRENGTH", "Tensile strength", 0.0, required=True,
                          when=("GEO_ENABLE_TENSION_CUT_OFF", (True,))),
            )),
            ("Hardening", _hardening()),
            ("Initial stresses", _initial_stresses()),
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


def unread(law: str, variables: dict) -> list[str]:
    """What choosing `law` leaves out of a soil holding `variables`: what another model
    lists and the model of `law` does not -- a linear elastic soil's strength and
    hardening. The material window and `kratos-cli material set --model` both leave it
    out; the window keeps it aside while it is open. Nothing for a law of no model,
    which is written as typed, and nothing the catalogue does not know."""
    model = model_of(law)
    if model == OTHER:
        return []
    reads = {p.name for p in parameters(model)}
    listed = {p.name for other in MODELS for p in parameters(other)}
    return [name for name in variables if name in listed and name not in reads]


def _value(name: str, variables: dict, model: str) -> Any:
    """`name` as the deck reads it: the soil's, or what Kratos takes when it is left
    out."""
    if name in variables:
        return variables[name]
    other = next((p for p in parameters(model) if p.name == name), None)
    return other.absent if other is not None else None


def _holds(parameter: Parameter, variables: dict, model: str, flow: bool) -> bool:
    if parameter.flow and not flow and \
            _value("GEO_DRAINAGE_TYPE", variables, model) not in FLOWING:
        return False
    if parameter.when is None:
        return True
    name, values = parameter.when
    value = _value(name, variables, model)
    return value in values and isinstance(value, bool) == isinstance(values[0], bool)


def shown(model: str, variables: dict, flow: bool = False) -> list[Parameter]:
    """The parameters the window lists for a soil of `model` holding `variables`; `flow`
    in a groundwater flow project, which reads every soil's flow parameters."""
    return [p for p in parameters(model) if _holds(p, variables, model, flow)]


def required(name: str, variables: dict) -> list[str]:
    """What the law `name` cannot run without, for a soil holding `variables`."""
    return [p.name for p in shown(model_of(name), variables) if p.required]


def fill(before_law: str | None, before: dict, after_law: str, after: dict,
         system: str, skip: tuple[str, ...] = (), flow: bool = False) -> list[str]:
    """Fill into `after` the defaults of what a soil now lists and lacks.

    The soil was `before_law` holding `before` (None and {}: a new soil) and is now
    `after_law` holding `after`. A parameter its model lists for `after` that `after`
    lacks gets its default in `system` when

    *   the soil is new or changed model: every one, so a soil switched to Mohr-Coulomb
        is ready to run;
    *   the model stayed and the parameter was not listed before: a retention law chosen
        brings its saturations, a cut-off switched on its tensile strength, a soil made
        `FULLY_COUPLED` its permeability. One that was listed and is left out stays
        out, for the export to derive;
    *   the law cannot run without it.

    Nothing the soil holds is replaced, nor is a name in `skip` filled. `flow` is
    `shown`'s. Returns the names filled, in the order filled."""
    model = model_of(after_law)
    old: set[str] = set()
    if before_law is not None and model_of(before_law) == model:
        old = {p.name for p in shown(model, before, flow)}
    filled: list[str] = []
    while True:
        # Listed anew after each fill: a retention law filled lists its saturations.
        for p in shown(model, after, flow):
            if (p.name not in after and p.name not in skip and p.default is not None
                    and (p.name not in old or p.required)):
                after[p.name] = default_in(p, system)
                filled.append(p.name)
                break
        else:
            return filled


def missing(name: str, variables: dict) -> list[str]:
    """What the law `name` cannot run without and a soil holding `variables` leaves
    blank: what the window says is still to fill in."""
    return [n for n in required(name, variables) if _number(variables.get(n)) is None]


def fill_choice(before_law: str, before: dict, after_law: str, after: dict, system: str,
                flow: bool = False, skip: tuple[str, ...] = ()) -> list[str]:
    """`fill`, as a choice in the material window fills -- a model, a drainage type, a
    flag (`App.MaterialSets` `choose`). A soil still being filled in by hand, `missing`
    something before the choice, gets no number its new law must have, and nothing it
    was listing and left blank: those stay the user's to type. Nor is a name in `skip`
    filled."""
    if missing(before_law, before):
        skip += tuple(p.name for p in parameters(model_of(after_law)) if p.required) + \
            tuple(p.name for p in shown(model_of(before_law), before, flow)
                  if p.name not in before)
    return fill(before_law, before, after_law, after, system, skip, flow)


def blank_si() -> dict:
    """A soil to fill in by hand, in SI: what the material window's **Create soil** and
    `kratos-cli material add` both start from. Linear elastic, `DRAINED`, saturated below
    the phreatic level -- with the saturations that retention law cannot run without --
    and nothing else: its stiffness and weight are the user's to type (`missing`)."""
    soil: dict = {"GEO_DRAINAGE_TYPE": "DRAINED"}
    for name in ("RETENTION_LAW", "SATURATED_SATURATION", "RESIDUAL_SATURATION"):
        soil[name] = next(p.default for p in parameters(LINEAR_ELASTIC) if p.name == name)
    return soil


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


def _number(value: Any) -> float | None:
    return None if isinstance(value, bool) or not isinstance(value, (int, float)) \
        else float(value)


def biot(variables: dict) -> float:
    """The Biot coefficient 1 - K / K_s, as Kratos' coupled elements derive it when it
    is not given (`GeoTransportEquationUtilities::CalculateBiotCoefficient`): K the
    drained bulk modulus of the elastic soil, E / (3 (1 - 2 nu)), and K_s the grains'.
    1, incompressible grains, when the soil does not say enough to derive it."""
    young = _number(variables.get("YOUNG_MODULUS"))
    poisson = _number(variables.get("POISSON_RATIO"))
    grains = _number(variables.get("BULK_MODULUS_SOLID"))
    if young is None or poisson is None or not grains or poisson >= 0.5:
        return 1.0
    return 1.0 - young / (3.0 * (1.0 - 2.0 * poisson)) / grains


def undrained_poisson(variables: dict, fluid_bulk_modulus: float) -> float | None:
    """The undrained Poisson ratio Kratos derives when it is not given, from Skempton's
    B (`ConstitutiveLawUtilities::CalculateUndrainedPoissonsRatio`), clamped as Kratos
    clamps it. None when the soil does not say enough, or Kratos would refuse the
    numbers (a Skempton B outside [0, 1])."""
    poisson = _number(variables.get("POISSON_RATIO"))
    alpha = _number(variables.get("BIOT_COEFFICIENT"))
    porosity = _number(variables.get("POROSITY"))
    grains = _number(variables.get("BULK_MODULUS_SOLID"))
    if poisson is None or alpha is None or porosity is None or grains is None \
            or not fluid_bulk_modulus:
        return None
    denominator = alpha + porosity * (grains / fluid_bulk_modulus + alpha - 1.0)
    if denominator <= 0:
        return None
    b = alpha / denominator
    if not 0.0 <= b <= 1.0 + 1e-12:     # Kratos refuses it: "out of range [0,1]"
        return None
    b = min(b, 1.0)
    denominator = 3.0 - alpha * b * (1.0 - 2.0 * poisson)
    if denominator <= 0:
        return None
    result = (3.0 * poisson + alpha * b * (1.0 - 2.0 * poisson)) / denominator
    return min(result, UNDRAINED_POISSON_LIMIT)


def k0(law: str, variables: dict) -> float | None:
    """K0 of a normally consolidated soil: Jaky's 1 - sin(phi) for a soil with a friction
    angle that is not elastic -- the correlation Kratos' staged-excavation reference
    follows -- and the elastic nu / (1 - nu) for a linear elastic one, which has none.
    None when the soil says neither."""
    if model_of(law) == LINEAR_ELASTIC:
        poisson = _number(variables.get("POISSON_RATIO"))
        return None if poisson is None or poisson >= 1 else poisson / (1.0 - poisson)
    phi = _number(variables.get("GEO_FRICTION_ANGLE"))
    return None if phi is None else 1.0 - math.sin(math.radians(phi))


def derived(law: str, variables: dict, water_variables: dict, system: str,
            flow: bool = False) -> dict:
    """What the export writes for a soil of `law` holding `variables` where the soil
    leaves it out, in `system`, in the order it derives them. The window shows each in
    place of the value it lacks.

    `water_variables` is `water`'s, for the undrained Poisson ratio; `flow` is a
    groundwater flow deck's, whose water pressure elements read the permeability and
    the Biot coefficient of every soil. The water itself, the permeabilities a
    dimension adds (`PERMEABILITY_XY`, the 3D ones) and an undrained soil's fixed
    permeability (`fixed_permeability`), the export writes on top. The drainage type is
    the project's name for it; the deck's is `kratos_drainage`'s."""
    out: dict = {}

    def given(name: str) -> Any:
        return variables[name] if name in variables else out.get(name)

    def put(name: str, value: Any) -> None:
        if name not in variables and value is not None:
            out[name] = value

    put("GEO_DRAINAGE_TYPE", "DRAINED")
    put("BULK_MODULUS_SOLID", units.from_si(BULK_MODULUS_SOLID_SI, units.STRESS, system))
    drainage = given("GEO_DRAINAGE_TYPE")
    # An undrained soil's permeability is not derived but fixed.
    if fixed_permeability(variables, system, flow) is None:
        if drainage == "FULLY_COUPLED" or flow:
            put("PERMEABILITY_XX", units.from_si(PERMEABILITY_SI, units.PERMEABILITY, system))
        put("PERMEABILITY_YY", _number(given("PERMEABILITY_XX")))
    if variables.get("RETENTION_LAW") in UNSATURATED:
        put("MINIMUM_RELATIVE_PERMEABILITY", MINIMUM_RELATIVE_PERMEABILITY)
    if variables.get("RETENTION_LAW") == "VanGenuchtenLaw":
        put("VAN_GENUCHTEN_GL", VAN_GENUCHTEN_GL)
    if drainage in ("FULLY_COUPLED", "UNDRAINED") or flow:
        put("BIOT_COEFFICIENT", biot({**variables, **out}))
    if drainage == "UNDRAINED":
        put("GEO_POISSON_UNDRAINED", undrained_poisson(
            {**variables, **out}, water_variables["BULK_MODULUS_FLUID"]))
    if model_of(law) == MOHR_COULOMB and \
            str(variables.get("GEO_COULOMB_HARDENING_TYPE", "None")).lower() == "linear":
        for name in VECTORS:
            put(name, 0.0)
    put("K0_NC", k0(law, variables))
    return out


def fixed_permeability(variables: dict, system: str, flow: bool = False) -> float | None:
    """The intrinsic permeability, in every direction, the export writes for a soil
    holding `variables` in place of any it carries, in `system`: `FIXED_PERMEABILITY_SI`
    for an `UNDRAINED` soil. None for any other, and in a groundwater flow project
    (`flow`), which lists every soil's permeability for the user to set."""
    fixed = FIXED_PERMEABILITY_SI.get(str(variables.get("GEO_DRAINAGE_TYPE")))
    if fixed is None or flow:
        return None
    return units.from_si(fixed, units.PERMEABILITY, system)


def kratos_drainage(value: Any) -> Any:
    """The `GEO_DRAINAGE_TYPE` the deck writes for the drainage type `value`: a drained
    soil's is `CONSTANT_PW_FIELD` (`KRATOS_DRAINAGE`); any other as it is."""
    return KRATOS_DRAINAGE.get(value, value) if isinstance(value, str) else value


def project_drainage(variables: dict) -> dict:
    """`variables` with a `GEO_DRAINAGE_TYPE` from before 2026-11-04 under its name now
    (`OLD_DRAINAGE`), in any case Kratos reads it in; as they are when there is none."""
    value = variables.get("GEO_DRAINAGE_TYPE")
    if not isinstance(value, str) or value.upper() not in OLD_DRAINAGE:
        return variables
    return {**variables, "GEO_DRAINAGE_TYPE": OLD_DRAINAGE[value.upper()]}


AXIS_PERMEABILITIES = ("PERMEABILITY_XX", "PERMEABILITY_YY", "PERMEABILITY_ZZ")
"""A soil's permeabilities along the axes; the fixed one is 0 across them."""


def unused_permeability(variables: dict, system: str, flow: bool = False) -> str | None:
    """What the export and `kratos-cli material set` say about a soil holding
    `variables` that carries a permeability the export does not write: one other than
    its drainage type's fixed one (`fixed_permeability`). None when there is none."""
    fixed = fixed_permeability(variables, system, flow)
    if fixed is None:
        return None
    own = [f"{name} {number:g}" for name in AXIS_PERMEABILITIES
           if (number := _number(variables.get(name))) is not None
           and not math.isclose(number, fixed, rel_tol=1e-3)]
    if not own:
        return None
    return (f"{', '.join(own)} not used: an {variables['GEO_DRAINAGE_TYPE']} soil is "
            f"written with the fixed intrinsic permeability {fixed:g} "
            f"{units.label(units.PERMEABILITY, system)}. Remove it, or make the soil "
            "FULLY_COUPLED to have it written.")


COMPUTED = {
    "UNIT_WEIGHT_DRY": ("Unit weight, dry", units.SPECIFIC_WEIGHT, "Weight"),
    "UNIT_WEIGHT_SATURATED": ("Unit weight, saturated", units.SPECIFIC_WEIGHT, "Weight"),
    "HYDRAULIC_CONDUCTIVITY_XX": ("Darcy permeability xx", units.VELOCITY, "Flow"),
    "HYDRAULIC_CONDUCTIVITY_YY": ("Darcy permeability yy", units.VELOCITY, "Flow"),
}
"""What `computed` gives: name -> (label, quantity, the window's group it is shown in).
Not Kratos variables: nothing of these is written."""


def computed(law: str, variables: dict, water_variables: dict, system: str,
             flow: bool = False) -> dict:
    """What follows from a soil's numbers, for the window to show beside them, in
    `system`: its unit weight dry, (1 - n) rho_s g, and saturated, with n gamma_w on
    top -- what Kratos weighs it at above and below the phreatic level -- and, where its
    permeability is listed, the Darcy conductivity that is: k = kappa gamma_w / mu."""
    every = {**derived(law, variables, water_variables, system, flow), **variables}
    g = units.gravity(system)
    gamma_w = water_variables["DENSITY_WATER"] * g
    out: dict = {}
    density, porosity = _number(every.get("DENSITY_SOLID")), _number(every.get("POROSITY"))
    if density is not None and porosity is not None:
        out["UNIT_WEIGHT_DRY"] = (1.0 - porosity) * density * g
        out["UNIT_WEIGHT_SATURATED"] = out["UNIT_WEIGHT_DRY"] + porosity * gamma_w
    listed = {p.name for p in shown(model_of(law), variables, flow)}
    for axis in ("XX", "YY"):
        kappa = _number(every.get(f"PERMEABILITY_{axis}"))
        if f"PERMEABILITY_{axis}" in listed and kappa is not None:
            out[f"HYDRAULIC_CONDUCTIVITY_{axis}"] = \
                kappa * gamma_w / water_variables["DYNAMIC_VISCOSITY"]
    return out


def problem(name: str, variables: dict) -> str | None:
    """Why Kratos would refuse the soil, beyond a missing variable: the bounds
    `MohrCoulombLaw::Check` and `CoulombYieldSurface` hold between its variables, and
    on a hardening's slopes."""
    if model_of(name) != MOHR_COULOMB:
        return None

    phi, psi = _number(variables.get("GEO_FRICTION_ANGLE")), \
        _number(variables.get("GEO_DILATANCY_ANGLE"))
    cohesion, tension = _number(variables.get("GEO_COHESION")), \
        _number(variables.get("GEO_TENSILE_STRENGTH"))
    if phi is not None and not phi < 90:
        return "GEO_FRICTION_ANGLE must be below 90 degrees."
    if str(variables.get("GEO_COULOMB_HARDENING_TYPE", "None")).lower() != "none":
        for slope_name in VECTORS:
            slope = _number(variables.get(slope_name))
            if slope is not None and slope < 0:
                return f"{slope_name} cannot be negative."
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
        out: dict = {"name": p.name, "label": p.label}
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
        if p.flow:
            out["flow"] = True
        return out

    return {"order": list(MODELS), "other": OTHER, "flowing": list(FLOWING),
            "unsaturated": list(UNSATURATED),
            "blank": blank_si(), "fixed_permeability": dict(FIXED_PERMEABILITY_SI),
            "palette": list(PALETTE),
            "vectors": list(VECTORS),
            "constants": {"WATER_SPECIFIC_WEIGHT": WATER_SPECIFIC_WEIGHT_SI,
                          "WATER_BULK_MODULUS": WATER_BULK_MODULUS_SI,
                          "WATER_VISCOSITY": WATER_VISCOSITY_SI,
                          "BULK_MODULUS_SOLID": BULK_MODULUS_SOLID_SI,
                          "PERMEABILITY": PERMEABILITY_SI,
                          "MINIMUM_RELATIVE_PERMEABILITY": MINIMUM_RELATIVE_PERMEABILITY,
                          "VAN_GENUCHTEN_GL": VAN_GENUCHTEN_GL,
                          "UNDRAINED_POISSON_LIMIT": UNDRAINED_POISSON_LIMIT},
            "computed": {name: {"label": label, "quantity": quantity.name, "group": group}
                         for name, (label, quantity, group) in COMPUTED.items()},
            "models": {
                model.id: {"label": model.label,
                           "laws": {str(dim): name for dim, name in model.laws.items()},
                           "old_laws": dict(model.old_laws),
                           "groups": [{"title": title,
                                       "parameters": [parameter(p) for p in group]}
                                      for title, group in model.groups]}
                for model in MODELS.values()}}
