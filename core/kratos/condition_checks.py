"""What the export says about a model's boundary conditions before it meshes anything.

The warnings of plan/active/boundary-conditions-plan.md sec 2.3 that the project alone
answers: a model nothing holds still, a water level nothing reads, a coupled soil with
nothing to fix its water pressure, a condition on a face or a drawn line this dimension
does not have, a K0 procedure with gravity off. The export (`core.kratos.writer`) adds them to its own, and
`kratos-cli check` prints them without meshing, so both say the same thing in the same
words.

The ones that need the mesh -- two conditions sharing nodes, a part with no soil in this
dimension, a line with no mesh at it -- stay with the export.

No gmsh here: `check` loads this module, and a command that never meshes should not pay
for loading the mesher.
"""

from __future__ import annotations

from core.model.schemas import DisplacementCondition, Project, WaterPressureCondition

SECTION_FACES = ("bottom", "left", "right", "top")
"""The faces a 2D section has. Front and back bound the solid model along z only."""


def warnings(project: Project) -> list[str]:
    """The project's boundary condition warnings, in the order the export says them."""
    out: list[str] = []
    for condition in project.boundary_conditions:
        if condition.active and not _plane_strain_holds(project, condition):
            left_out = _left_out(project, condition)
            if left_out:
                out.append(left_out)
    out += _rigid_body(project)
    out += _unpinned_water(project)
    out += _unused_water_level(project)
    out += _weightless_k0(project)
    return out


def written(project: Project, condition) -> bool:
    """Whether the export writes `condition` in this dimension at all."""
    return condition.active and _left_out(project, condition) is None


def noun(condition) -> str:
    """`condition`, as a warning names it."""
    kind = "water pressure" if condition.kind == "water_pressure" else "displacement"
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


def _plane_strain_holds(project: Project, condition) -> bool:
    """A displacement support on the front or back face of a 2D model: left out, and
    nothing to say about it, because the plane-strain section holds z everywhere. Every
    project starts with rollers there (`schemas.standard_conditions`), for the solid
    model."""
    return (isinstance(condition, DisplacementCondition) and project.dimension == 2
            and condition.on == "face" and condition.face not in SECTION_FACES)


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
    """A soil whose water pressure stays as it starts (`CONSTANT_PW_FIELD`, what
    `core.kratos.materials` fills in) needs nothing to fix it: a dry model of such soil
    runs, and gives the results it gave when the export still fixed zero everywhere. One
    that couples it is the one to say something about: Kratos solves it, but with the
    pressure free the self weight raises one of its own -- about 1.5 MPa and 8 m of
    settlement in a 40 m block that settles 0.65 m dry
    (tests/kratos/test_live_conditions.py)."""
    if _water_pressures(project):
        return []
    used = ({layer.mat for layer in project.layers}
            | {part.mat for part in project.custom_parts if part.mat is not None})
    coupled = [m.name for m in project.materials if m.id in used
               and m.variables.get("GEO_DRAINAGE_TYPE", "CONSTANT_PW_FIELD")
               != "CONSTANT_PW_FIELD"]
    if not coupled:
        return []
    return [
        "no water pressure condition is set, so nothing fixes the water pressure, and "
        f"{', '.join(repr(name) for name in coupled)} couples it to the deformation "
        "(GEO_DRAINAGE_TYPE): the self weight then builds up water pressures the model "
        "does not have, and the displacements with them. Add a water pressure condition "
        "(for a dry model: Uniform, value 0, on the whole soil)."]


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
    leaves out: the stresses it starts the next phase with are zero."""
    if project.gravity:
        return []
    return [f"phase {phase.name!r} is a K0 procedure, whose stresses come from the self "
            "weight; with gravity off they are zero."
            for phase in project.phases if phase.calculation == "K0 procedure"]
