"""The benchmark models, as ordinary projects (plan alpha 4, decision D6).

Each builder returns a `Project`, so every model here also opens in the GUI the way any
model does -- `run benchmarks/models.py` builds the K0 column, the default -- and the
benchmark runner sends exactly that project through the REST API, the path the GUI uses.
"""

from __future__ import annotations

from core.model import migration, stages
from tests.models import excavation
from core.model.schemas import Project, standard_conditions
from core.model.templates import blank_project


def material(id_: str, name: str, gamma: float, k0: float | None = None,
             E: float = 3.0e4, nu: float = 0.3, porosity: float | None = 0.0,
             gamma_sat: float | None = None) -> dict:
    """A drained linear-elastic soil, described as an engineer would (kN/m3, kN/m2,
    m/day): the form the analytical checks in `cases.py` read. Porosity 0 by default, so
    the unsaturated weight is the weight; `porosity=None` takes the default porosity, 0.3."""
    return {"id": id_, "name": name, "model": "Linear Elastic", "type": "Drained",
            "color": "#b6ac97", "g_unsat": gamma, "g_sat": gamma_sat or gamma, "E": E,
            "nu": nu, "c": 1.0, "phi": 30.0, "k": 1.0, "porosity": porosity, "k0_nc": k0}


def weighing(spec: dict) -> dict:
    """`spec` as the Kratos property set that weighs what it says: `g_unsat` above the
    phreatic level and `g_sat` below it.

    Kratos weighs a point at (1 - n) DENSITY_SOLID g + n S gamma_w, S its saturation. With
    `SaturatedBelowPhreaticLevelLaw` S is 1 below the water and `RESIDUAL_SATURATION`
    (nearly 0) above it, so DENSITY_SOLID = g_unsat / ((1 - n) g) and n = (g_sat -
    g_unsat) / gamma_w give both weights. The project holds exactly these numbers; this
    is the engineer's arithmetic, done once, in the benchmark."""
    gamma_w = 10.0
    n = spec["porosity"] if spec["g_sat"] == spec["g_unsat"] else \
        (spec["g_sat"] - spec["g_unsat"]) / gamma_w
    out = dict(spec)
    out["kratos"] = {
        "id": spec["id"], "name": spec["name"], "color": spec["color"],
        "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
        "variables": {
            "GEO_DRAINAGE_TYPE": "DRAINED",
            "YOUNG_MODULUS": spec["E"] * 1000.0, "POISSON_RATIO": spec["nu"],
            "DENSITY_SOLID": spec["g_unsat"] * 1000.0 / ((1.0 - n) * 9.81),
            "POROSITY": n, "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
            # Kratos' saturated-below-the-phreatic-level retention block.
            "SATURATED_SATURATION": 1.0, "RESIDUAL_SATURATION": 1.0e-10,
            "MINIMUM_RELATIVE_PERMEABILITY": 1.0e-4,
            "PERMEABILITY_XX": spec["k"] / 86_400,
            "K0_NC": spec["k0_nc"],
        },
    }
    return out


def column(layers: list[tuple[float, float, dict]], width: float = 1.0,
           water_y: float | None = None, k0_stage: bool = True,
           name: str = "Soil column") -> Project:
    """A soil column `width` wide, its layers as (top, bottom, material) from the top.

    Rollers on the sides and a fixed base are the exporter's own boundaries, and the pore
    pressure is fixed hydrostatically on the whole column; a single K0 stage when
    `k0_stage`, otherwise the one stage of a project without a sequence."""
    p = blank_project().model_dump(mode="json")
    top, bottom = layers[0][0], layers[-1][1]
    p["name"] = name
    p["domain"] = {"x0": 0.0, "x1": width, "z0": 0.0, "z1": 1.0,
                   "y_top": top, "y_bottom": bottom}
    seen, materials = set(), []
    for _, _, mat in layers:
        if mat["id"] not in seen:
            seen.add(mat["id"])
            materials.append(mat)
    # The benchmark's own description of a soil is the engineer's (kN/m3, kN/m2, m/day),
    # which is what its analytical checks are written in; the project holds what Kratos
    # reads, converted the way every project in that shape is (`core/model/migration.py`).
    # Its water is the project's (`Project.fluid`), which is water's here.
    p["materials"] = [mat["kratos"] if "kratos" in mat
                      else migration.without_water(migration.material(mat, 2))
                      for mat in materials]
    p["layers"] = [{"id": f"L{i}", "name": f"Layer_{i}", "mat": mat["id"],
                    "top": t, "bottom": b}
                   for i, (t, b, mat) in enumerate(layers, start=1)]
    p["excavation"] = {"x0": 0.0, "x1": width / 2, "z0": 0.0, "z1": 0.5,
                       "floor_y": bottom + 0.5 * (top - bottom)}
    p["section_offset"] = 0.5
    p["water"] = {"y": water_y} if water_y is not None else None
    # Hydrostatic about the water level, or about the base -- zero everywhere -- in a
    # dry column.
    p["boundary_conditions"] = [
        *(c.model_dump() for c in standard_conditions()),
        {"id": "pore_pressure", "name": "Pore pressure", "kind": "water_pressure",
         "on": "domain", "reference_coordinate": water_y if water_y is not None else bottom}]
    p["mesh"] = {"element_size": min(width, (top - bottom) / 10), "order": 2}
    if k0_stage:
        p["stages"] = [{"id": "initial", "name": "Initial stage", "calculation": "K0 procedure"}]
    return Project.model_validate(p)


def column_under_drawn_fill(fill: tuple[float, float, dict],
                            layer: tuple[float, float, dict], width: float = 1.0,
                            name: str = "Soil column under drawn fill") -> Project:
    """`column` with its top part drawn rather than made as a layer: `layer` is the
    soil layer, `fill` a polygon over the full width with a material of its own,
    both as (top, bottom, material). The fill is built from its recipe, as a model
    script builds it, so the runner sends a project whose .brep exists."""
    from core import scripting

    fill_top, fill_bottom, fill_material = fill
    p = column([layer], width=width, name=name).model_dump(mode="json")
    p["domain"]["y_top"] = fill_top
    p["materials"].append(fill_material["kratos"] if "kratos" in fill_material
                          else migration.without_water(migration.material(fill_material, 2)))
    corners = [(0.0, fill_top), (0.0, fill_bottom), (width, fill_bottom), (width, fill_top)]
    p["custom_parts"] = [{
        "key": "drawn_0", "label": "Fill", "source": "gui", "mat": fill_material["id"],
        "recipe": {"kind": "polygon_extrude", "material": fill_material["id"],
                   "vertices": [[x, y, 0.0] for x, y in corners],
                   "extrusion": [0.0, 0.0, 1.0]}}]
    p["mesh"]["element_size"] = min(width, (fill_top - layer[1]) / 10)
    return scripting.with_solids(Project.model_validate(p))


def symmetric_pit(width: float = 80.0, pit: tuple[float, float] = (35.0, 45.0),
                  levels: tuple[float, ...] = (-2.0, -5.0), dimension: int = 2) -> Project:
    """The test model's ground with no structures, dug symmetrically in the middle of a
    full model: two lifts, the default staged sequence. Plane strain, or its 3D
    extrusion."""
    p = excavation.excavation_project(staged=False).model_dump(mode="json")
    p.update(beams=[], anchors=[], interfaces=[], loads=[], normal_loads=[], stages=[],
             water=None, name="Symmetric pit")
    p["domain"] = dict(p["domain"], x0=0.0, x1=width)
    p["excavation"] = {k: v for k, v in p["excavation"].items() if k != "floor_y"}
    p["excavation"].update(x0=pit[0], x1=pit[1], levels=list(levels))
    p["mesh"] = dict(p["mesh"], body_sizes={}, refinements=[], element_size=2.0)
    project = Project.model_validate(p)
    project = Project.model_validate(
        project.model_dump() | {"stages": [ph.model_dump()
                                           for ph in stages.staged_excavation_stages(project)]})
    return project


def project() -> Project:
    """`run benchmarks/models.py` opens the K0 column."""
    return column([(0.0, -10.0, material("sand", "Sand", 18.0, k0=0.6))])
