"""What the export says about a model's boundary conditions before it meshes anything.

The warnings of plan/done/boundary-conditions-plan.md sec 2.3 that the project alone
answers: a model nothing holds still, a water level nothing reads, a coupled soil with
nothing to fix its water pressure, a condition on a face or a drawn line this dimension
does not have, a K0 procedure with gravity off. The export (`core.kratos.writer`) adds them to its own, and
`kratos-cli check` prints them without meshing, so both say the same thing in the same
words.

A seepage face (`SeepageCondition`) belongs to a groundwater flow calculation; a
deformation deck leaves it out and says so.

A groundwater flow project (`core.model.stages.groundwater_flow`) has warnings of its own
instead of the ones about deformation -- the structures and loads it leaves out (the
supports it leaves out silently), a soil fixed everywhere,
gravity off -- and the refusals of `flow_refusal`, which both say before meshing too.

The ones that need the mesh -- two conditions sharing nodes, a part with no soil in this
dimension, a line with no mesh at it -- stay with the export.

No gmsh here: `check` loads this module, and a command that never meshes should not pay
for loading the mesher.
"""

from __future__ import annotations

from core.model import stages
from core.model.schemas import (SECTION_FACES, DisplacementCondition, Material, Stage,
                                Project, SeepageCondition, WaterPressureCondition)


def warnings(project: Project) -> list[str]:
    """The project's boundary condition warnings, in the order the export says them."""
    out: list[str] = []
    for condition in project.boundary_conditions:
        if condition.active and not held_by_section(project, condition):
            left_out = _left_out(project, condition)
            if left_out:
                out.append(left_out)
    if _flow(project):
        out += _left_out_of_flow(project)
        out += _water_fixed_everywhere(project)
        out += _weightless_flow(project)
        out += _unused_water_level(project)
        return out
    out += _seepage_outside_flow(project)
    out += _rigid_body(project)
    out += _unpinned_water(project)
    out += _free_water_in_stages(project)
    out += _unused_water_level(project)
    out += _weightless_k0(project)
    return out


SECTION_NOTE = ("The front and back supports are kept for the solid model; the 2D "
                "section holds z by itself.")
"""Said under a 2D list that leaves them out, in the CLI and in the GUI's command box
alike."""

FLOW_NOTE = ("A groundwater flow calculation leaves the supports out: it solves the "
             "water pressure alone.")
"""Said under the list of a groundwater flow project with supports, in the CLI and in the
GUI's command box alike; the Model explorer marks each support "(unused in flow)"."""


def listed(project: Project) -> list:
    """The conditions a list shows the user: all but the ones `held_by_section`."""
    return [c for c in project.boundary_conditions if not held_by_section(project, c)]


def unused_in_flow(project: Project, condition) -> bool:
    """Whether the export leaves the support `condition` out because the project is a
    groundwater flow calculation (`App.BoundaryConditions.unusedInFlow`)."""
    return isinstance(condition, DisplacementCondition) and _flow(project)


def written(project: Project, condition) -> bool:
    """Whether the export writes `condition` in this dimension at all."""
    return condition.active and _left_out(project, condition) is None


def noun(condition) -> str:
    """`condition`, as a warning names it."""
    kind = {"water_pressure": "water pressure", "seepage": "seepage"}.get(
        condition.kind, "displacement")
    return f"{kind} condition {condition.name!r}"


def _left_out(project: Project, condition) -> str | None:
    """Why the export leaves `condition` out in this dimension, or None."""
    if condition.on in ("line", "point") and project.dimension != 2:
        return (f"{noun(condition)} is on a {condition.on}, which is drawn in the 2D "
                "section; this 3D deck leaves it out.")
    if condition.on == "face" and project.dimension == 2 \
            and condition.face not in SECTION_FACES:
        return (f"{noun(condition)} is on the {condition.face} face, which this 2D model "
                "does not have; it is left out.")
    return None


def held_by_section(project: Project, condition) -> bool:
    """A displacement support on the front or back face of a 2D model: left out, and
    nothing to say about it, because the plane-strain section holds z everywhere. Every
    project starts with rollers there (`schemas.standard_conditions`), for the solid
    model. Not listed either, by the CLI or the GUI (`listed`; its twin is
    `App.BoundaryConditions.heldBySection`)."""
    return (isinstance(condition, DisplacementCondition) and project.dimension == 2
            and condition.on == "face" and condition.face not in SECTION_FACES)


def _seepage_outside_flow(project: Project) -> list[str]:
    """A seepage face in a deformation project: the deck has no seepage strategy to open
    and close it, so it is left out."""
    faces = [c for c in project.boundary_conditions
             if isinstance(c, SeepageCondition) and written(project, c)]
    return [f"{noun(c)} is left out: a seepage face belongs to a groundwater flow "
            "calculation, and this project's stages are not \"Groundwater flow\"."
            for c in faces]


def _rigid_body(project: Project) -> list[str]:
    """Nothing holds the model: no displacement condition and no anchor, whose fixed
    tail is a support of its own. Kratos cannot solve a body that is free to move."""
    held = any(isinstance(c, DisplacementCondition) and written(project, c)
               for c in project.boundary_conditions)
    anchors = (project.plane_anchors if project.dimension == 2
               else project.plane_anchors + project.space_anchors)
    if held or any(anchor.active for anchor in anchors):
        return []
    return [
        "no displacement condition holds the model, so it can move as a rigid body and "
        "Kratos will not solve it. Add one: the standard conditions are the bottom "
        "fixed and the sides on rollers."]


def _water_pressures(project: Project) -> list[WaterPressureCondition]:
    return [c for c in project.boundary_conditions
            if isinstance(c, WaterPressureCondition) and written(project, c)]


def _unpinned_water(project: Project) -> list[str]:
    """A mechanical-only soil's water pressure stays as it starts (`CONSTANT_PW_FIELD`,
    what `core.kratos.materials` fills in): it needs nothing
    to fix it, and a dry model of such soil runs, giving the results it gave when the
    export still fixed zero everywhere. One
    that couples it is the one to say something about: Kratos solves it, but with the
    pressure free the self weight raises one of its own -- about 1.5 MPa and 8 m of
    settlement in a 40 m block that settles 0.65 m dry
    (tests/kratos/test_live_conditions.py)."""
    if _water_pressures(project):
        return []
    coupled = _coupled_soils(project)
    if not coupled:
        return []
    return [
        "no water pressure condition is set, so nothing fixes the water pressure, and "
        f"{', '.join(repr(name) for name in coupled)} couples it to the deformation "
        "(GEO_DRAINAGE_TYPE): the self weight then builds up water pressures the model "
        "does not have, and the displacements with them. Add a water pressure condition "
        "(for a dry model: Uniform, value 0, on the whole soil)."]


def _soil_materials(project: Project) -> list[Material]:
    """The materials the soil uses: each soil body's and the custom parts'."""
    used = ({*project.soil_body_materials.values()}
            | {part.mat for part in project.custom_parts if part.mat is not None})
    return [m for m in project.materials if m.id in used]


def _coupled_soils(project: Project) -> list[str]:
    """The names of the soil materials in use that couple the water pressure to the
    deformation (`GEO_DRAINAGE_TYPE` other than `CONSTANT_PW_FIELD`)."""
    return [m.name for m in _soil_materials(project)
            if m.variables.get("GEO_DRAINAGE_TYPE", "CONSTANT_PW_FIELD") != "CONSTANT_PW_FIELD"]


def _free_water_in_stages(project: Project) -> list[str]:
    """A stage in which nothing holds the water pressure of a coupled soil.

    What a stage that switches its conditions off leaves depends on the Kratos process
    (tests/kratos/test_live_conditions.py): a fixed Hydrostatic or Phreatic condition
    keeps its nodes fixed at their last values after its stage, so the later stages
    carry them; a fixed Uniform one frees its nodes when its stage ends. So a stage is
    unheld when no fixed condition is on in it and no fixed Hydrostatic or Phreatic one
    was on before it. Unstaged projects are `_unpinned_water`'s."""
    pressures = _water_pressures(project)
    if not project.stages or not pressures:
        return []
    coupled = _coupled_soils(project)
    if not coupled:
        return []
    try:
        order = stages.linearise(project)
    except stages.StageError:
        return []
    fixed = [c for c in pressures if c.is_fixed]
    kept = False
    out: list[str] = []
    for stage in order:
        on = stages.active_parts(project, stage)
        now = [c for c in fixed if c.id in on]
        if not now and not kept:
            out.append(
                f"in stage {stage.name!r} no fixed water pressure condition is on and "
                "none that keeps its values (Hydrostatic or Phreatic) was on before, so "
                f"the water pressure of {', '.join(repr(name) for name in coupled)} is "
                "free there, and the self weight builds up pressures the model does not "
                "have. Switch a water pressure condition on in that stage.")
        kept = kept or any(c.fluid_pressure_type != "Uniform" for c in now)
    return out


def _unused_water_level(project: Project) -> list[str]:
    """The project has a water level and nothing in the deck reads it: since the level
    fixes no pressure by itself, a model with no water pressure condition is a model
    whose author may expect pore pressures it will not get."""
    if project.water is None:
        return []
    loads = any(load.fluid_pressure_type == "Hydrostatic"
                and load.reference_coordinate is None
                for load in project.active_normal_loads)
    if _water_pressures(project) or loads:
        return []
    return [
        f"the water level ({project.water.y:g} m) fixes no pressure by itself, and no "
        "water pressure condition or normal load uses it. Add a water pressure condition "
        "if the soil should be under water."]


def _weightless_k0(project: Project) -> list[str]:
    """A K0 procedure derives its stresses from the self weight, which gravity off
    leaves out: the stresses it starts the next stage with are zero."""
    if project.gravity:
        return []
    return [f"stage {stage.name!r} is a K0 procedure, whose stresses come from the self "
            "weight; with gravity off they are zero."
            for stage in project.stages if stage.calculation == "K0 procedure"]


# ── Groundwater flow ────────────────────────────────────────────────────────

def _flow(project: Project) -> bool:
    """Whether the project is a groundwater flow calculation. A mix of flow and
    deformation stages is not one: `flow_refusal` says why it cannot be exported."""
    try:
        return stages.groundwater_flow(project)
    except stages.StageError:
        return False


def flow_refusal(project: Project) -> str | None:
    """Why the export refuses this groundwater flow project, or None. None too for a
    project that is not one, except a mix of flow and deformation stages."""
    try:
        if not stages.groundwater_flow(project):
            return None
    except stages.StageError as failure:
        return str(failure)
    if project.dimension != 2:
        return ("a groundwater flow calculation is 2D only for now: switch the model to "
                "the 2D section.")
    missing = [m.name for m in _soil_materials(project)
               if m.number("PERMEABILITY_XX") is None]
    if missing:
        return (f"{', '.join(repr(name) for name in missing)} has no PERMEABILITY_XX, "
                "and a groundwater flow calculation cannot run without it: give the "
                "soil its intrinsic permeability (m²).")
    unheld = _unheld_flow_stage(project)
    if unheld is not None:
        return (f"in stage {unheld.name!r} no fixed water pressure condition is on, and "
                "none that keeps its values (Hydrostatic or Phreatic) was on before, so "
                "the water pressure has no single solution. Switch on a fixed water "
                "pressure condition where the head is known, on a face or a line.")
    return None


def _unheld_flow_stage(project: Project) -> Stage | None:
    """The first stage in which nothing fixes the water pressure, or None. The same
    rule as `_free_water_in_stages`: a fixed Hydrostatic or Phreatic condition keeps its
    nodes fixed after its stage, a fixed Uniform one does not."""
    try:
        order = stages.linearise(project)
    except stages.StageError:
        return None
    fixed = [c for c in _water_pressures(project) if c.is_fixed]
    kept = False
    for stage in order:
        on = stages.active_parts(project, stage)
        now = [c for c in fixed if c.id in on]
        if not now and not kept:
            return stage
        kept = kept or any(c.fluid_pressure_type != "Uniform" for c in now)
    return None


def _left_out_of_flow(project: Project) -> list[str]:
    """What a groundwater flow deck does not write: its elements carry the water
    pressure alone, so nothing that acts on a displacement has anything to act on.

    The displacement conditions are left out without a word: every new project has the
    standard supports, nobody expects a support to change the flow, and a boundary with
    no water pressure condition lets no water through, as a fixed one would suggest."""
    dim = project.dimension
    anchors: list = (project.plane_anchors if dim == 2
                     else [*project.plane_anchors, *project.space_anchors])
    kinds: tuple[tuple[str, list], ...] = (
        ("structures", [b for b in project.structures_for(dim) if b.active]),
        ("anchors", [a for a in anchors if a.active]),
        ("interfaces", project.active_interfaces),
        ("loads", [load for load in project.loads_for(dim) if load.active]),
        ("normal loads", project.active_normal_loads),
    )
    return [f"a groundwater flow calculation writes the soil alone: the {kind} "
            f"{_names(records)} are left out."
            for kind, records in kinds if records]


def _water_fixed_everywhere(project: Project) -> list[str]:
    """A fixed condition on the whole soil leaves no node free, so no water flows."""
    return [f"{noun(c)} fixes the water pressure at every node of the soil, so no water "
            "can flow. Fix it on the faces or lines where the head is known instead, and "
            "give the soil a start value (not fixed) if it needs one."
            for c in _water_pressures(project) if c.is_fixed and c.on == "domain"]


def _weightless_flow(project: Project) -> list[str]:
    """Without gravity the water has no weight: the flow follows the pressure alone, and
    the hydraulic head is not written (`parameters._gid_output`)."""
    if project.gravity:
        return []
    return ["gravity is off, so the water has no weight: it flows from the pressure "
            "differences alone, and the hydraulic head is not written. Turn gravity on, "
            "unless the section is a horizontal one."]


def _names(records: list) -> str:
    return ", ".join(repr(record.name) for record in records)
