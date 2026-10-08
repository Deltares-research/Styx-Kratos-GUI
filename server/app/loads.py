"""Translating a load between the section and the solid model.

A surface load and a line load are one load seen from two dimensions. Plane strain
reduces a pressure over a footprint (kN/m2) to a pressure per metre run in the cut
(kN/m) -- numerically the same number, because a metre run of the section is exactly
what the reduction integrates over -- and the out-of-plane extent is what it throws
away. Switching mode translates one into the other so a load drawn in 3D is still
there in 2D, and back.

Both records are kept, paired by `derived_from`. A line load carries no `z` at all --
dimension-native by design, and there is a test that says so -- so replacing the
surface record outright would widen a footprint of z = 5..10 to the whole model on the
way back. Keeping it costs one extra record and makes the round trip lossless.

The translation runs in the direction of travel: leaving 2D pushes the section's line
loads up, leaving 3D pushes the solid model's surface loads down. Whichever dimension
the user was working in is the one they edited, so that is the one that wins.

Not everything has a counterpart. A point load is kN, not kN/m2, and there is no 3D
point-load kind to put it in. A line load below `y_top` has nowhere to go either: a
`SurfaceLoad` has no level of its own and always sits on the ground surface, so translating
one would relocate it. Both are left alone and built at the section plane instead --
see `Project.loads_for`, which is what keeps a translated pair from being applied twice.
"""

from __future__ import annotations

from app.schemas import LineLoad, PointLoad, Project, SurfaceLoad

Load = PointLoad | LineLoad | SurfaceLoad


DEFAULT_NAMES = {"point": "PointLoad_", "line": "LineLoad_", "surface": "SurfaceLoad_"}
"""The auto-generated name per kind, matching `nextNumber` in live/js/loads.js.

These names carry the kind, and the model explorer lists a load by name alone -- so a
surface load still called "LineLoad_1" reads as one that never converted. A name off
this pattern is the user's own and is never rewritten.
"""


def _translated_name(source: Load, existing: Load | None, kind: str) -> str:
    """What to call the half of a pair that lives in `kind`.

    A default name is renumbered into the target kind's own prefix, keeping the number
    so the two halves stay recognisably one load. Anything else -- "Crane pad" -- is a
    word the user chose for the load itself, not for its dimension, and carries across
    untouched.
    """
    if existing is not None and not _is_default(existing.name):
        return existing.name        # the user named this half in its own dimension
    number = _number_of(source.name)
    return DEFAULT_NAMES[kind] + number if number else source.name


def _is_default(name: str) -> bool:
    return _number_of(name) is not None


def _number_of(name: str) -> str | None:
    """The trailing number of a default name, or None if this name is not one."""
    for prefix in DEFAULT_NAMES.values():
        if name.startswith(prefix) and name[len(prefix):].isdigit():
            return name[len(prefix):]
    return None


def _line_from(surface: SurfaceLoad, project: Project, existing: LineLoad | None
               ) -> LineLoad:
    """The section's view of a surface load: its x extent, on the ground surface.

    `existing` is the counterpart a previous switch already made. Its id and name are
    reused so the tree row, the selection and anything holding the key stay put.
    """
    qx, qy, _ = surface.components
    return LineLoad(
        id=existing.id if existing else f"{surface.id}_2d",
        name=_translated_name(surface, existing, "line"),
        x0=surface.x0, x1=surface.x1, y=project.elevation_of(surface),
        thickness=surface.thickness,
        components=(qx, qy),
        distribution=surface.distribution,
        active=surface.active,
        derived_from=existing.derived_from if existing else surface.id,
    )


def _surface_from(line: LineLoad, project: Project, existing: SurfaceLoad | None
                  ) -> SurfaceLoad:
    """The solid model's view of a line load.

    The footprint is the whole out-of-plane width the first time, which is what plane
    strain means and all the line record can say. On a later switch the counterpart's
    own `z0`/`z1` are kept: the user may have narrowed the footprint in 3D, and the
    trip through the section is not a reason to undo that.
    """
    qx, qy = line.components
    return SurfaceLoad(
        id=existing.id if existing else f"{line.id}_3d",
        name=_translated_name(line, existing, "surface"),
        x0=line.x0, x1=line.x1, y=line.y,
        z0=existing.z0 if existing else project.domain.z0,
        z1=existing.z1 if existing else project.domain.z1,
        thickness=line.thickness,
        components=(qx, qy, 0.0),
        distribution=line.distribution,
        active=line.active,
        derived_from=existing.derived_from if existing else line.id,
    )


GROUND_TOLERANCE = 1e-6
"""How far off the ground a line load may be and still count as lying on it.

Not a nicety: gmsh pads every bounding box it reports by 1e-7, so an embankment drawn
0..4 makes `ground_y` 4.0000001 while the load the user places on its visible top is at
4.0. Exact equality made those two different numbers and the load stopped translating.
Comfortably above that pad and below anything an engineer would mean by a level.
"""


def _translatable(load: Load, project: Project) -> bool:
    """Whether this 2D load has a surface form at all. See the module docstring.

    `ground_y` rather than `domain.y_top`: a load drawn on top of an embankment is on
    the ground surface even though it is well above the borehole block. Compared within
    `GROUND_TOLERANCE`, because neither number is exact.
    """
    return (load.kind == "line"
            and abs(load.y - project.ground_y()) <= GROUND_TOLERANCE)


def _partner_of(load: Load, by_id: dict[str, Load], derived: dict[str, Load]
                ) -> Load | None:
    """The other half of a translated pair, whichever half `load` is.

    The link is stored once, on the derived record, so it is followed forwards from
    there and backwards from the original.
    """
    if load.derived_from is not None:
        return by_id.get(load.derived_from)
    return derived.get(load.id)


def translate(project: Project, dimension: int,
              log: list[str] | None = None,
              section_offset: float | None = None) -> list[Load]:
    """`project.loads`, with each load's counterpart in `dimension` made or refreshed.

    Runs in the direction of travel: entering 3D pushes every line load into its
    surface partner, entering 2D pushes every surface load into its line partner. The
    dimension being left is the one the user was editing, so it is the one that wins --
    and because the *partner* is rewritten rather than the record itself, the half they
    edited is never overwritten by its own translation.

    `section_offset` is where the section plane will be (None: the mid-plane, as the
    Project validator resolves it); only the notes read it.

    Returns a new list in the original's order, with any newly derived record appended
    after the one it came from, so the tree does not reshuffle on a mode switch.
    """
    if dimension == project.dimension:
        return list(project.loads)
    noun = "line load" if dimension == 2 else "surface load"
    low, high = project.section_bounds()
    cut = section_offset if section_offset is not None else (low + high) / 2

    def note(message: str) -> None:
        """A translated record appearing on its own is a surprise; say what happened."""
        if log is not None:
            log.append(message)

    by_id = {load.id: load for load in project.loads}
    derived = {load.derived_from: load for load in project.loads
               if load.derived_from is not None}

    # Positional, not `list.index`: a partner may sit either side of the load it is
    # paired with, and two loads that happen to hold equal values compare equal.
    out: list[Load] = list(project.loads)
    position = {load.id: index for index, load in enumerate(out)}
    added: list[tuple[int, Load]] = []

    for load in project.loads:
        partner = _partner_of(load, by_id, derived)
        if dimension == 3 and load.kind == "line":
            if partner is not None and partner.kind == "surface":
                out[position[partner.id]] = _surface_from(load, project, partner)
                note(f"{load.name}'s {noun} is updated from the section.")
            elif partner is None and _translatable(load, project):
                added.append((position[load.id], _surface_from(load, project, None)))
                note(f"{load.name} is now also a {noun}, spanning the model width.")
        elif dimension == 2 and load.kind == "surface":
            if not load.z0 - 1e-9 <= cut <= load.z1 + 1e-9:
                note(f"{load.name} lies at z = {load.z0:g}..{load.z1:g}, clear of the "
                     f"section plane at z = {cut:g}, so it is not in the section.")
            if partner is not None and partner.kind == "line":
                out[position[partner.id]] = _line_from(load, project, partner)
                note(f"{load.name}'s {noun} is updated from the solid model.")
            elif partner is None:
                added.append((position[load.id], _line_from(load, project, None)))
                note(f"{load.name} is now also a {noun} in the section.")
        elif dimension == 3 and partner is None and load.kind != "surface":
            # A point load, or a line load below the ground surface. Neither has a
            # surface form to be translated into -- see the module docstring -- so it
            # is built at the section plane as it stands. Worth saying: the alternative
            # readings are that it was translated, or that it was dropped.
            note(f"{load.name} has no {noun} form and is carried at the section plane.")

    # Back to front, so an insertion does not shift the positions still to be used.
    for index, made in sorted(added, key=lambda pair: pair[0], reverse=True):
        out.insert(index + 1, made)
    return out
