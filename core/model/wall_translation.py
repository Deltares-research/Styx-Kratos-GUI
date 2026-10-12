"""Translating a wall between the section and the solid model.

A sheet pile and a wall panel are one wall seen from two dimensions. In the section it
is an `(x, z)` polyline with a profile per metre run; in the solid model it is a plan
footprint swept between two levels, meshed as shells. Switching mode translates one
into the other, which is what gives the wall a `y` to edit in 3D at all -- a pile has
none, so before this it could only be swept a nominal strip wide with nothing in the
Selection explorer to change.

The pairing is the one `core/model/load_translation.py` uses for a surface load and a line load, and for
the same reason: both records are kept, linked by `derived_from`, so the footprint the
user draws in plan survives a trip through a section that has no y to remember it by.
The translation runs in the direction of travel, so whichever dimension was just left
-- the one the user was editing -- is the one that wins.

Only a *vertical* pile has a panel form, because a panel is a vertical sweep. A raking
or stepped pile is left alone and swept onto the section plane as before; straightening
it into a footprint would silently redraw the wall.

A panel the user authored directly in 3D is not translated down. It is a wall in plan,
which a plane-strain cut has no way to represent in general, and it has never appeared
in the section; only the half of a *pair* is refreshed.
"""

from __future__ import annotations


from core.model.schemas import Beam, Member, Panel, PanelSection, Project

Structure = Beam | Panel | Member

TOLERANCE = 1e-9
"""How far apart two x values may be and still be one vertical wall."""

DEFAULT_NAMES = {"beam": "Sheet pile ", "panel": "Wall "}
"""The auto-generated name per kind, matching `draftPanel`/`draftFromPoints` in
frontend/js/beams.js. These carry the kind, and the model explorer lists a structure by
name alone, so a panel still called "Sheet pile 1" reads as one that never converted.
A name off this pattern is the user's own and is never rewritten."""


def _number_of(name: str) -> str | None:
    for prefix in DEFAULT_NAMES.values():
        if name.startswith(prefix) and name[len(prefix):].isdigit():
            return name[len(prefix):]
    return None


def _translated_name(source: Structure, existing: Structure | None, kind: str) -> str:
    if existing is not None and _number_of(existing.name) is None:
        return existing.name        # the user named this half in its own dimension
    number = _number_of(source.name)
    return DEFAULT_NAMES[kind] + number if number else source.name


def _is_vertical(beam: Beam) -> bool:
    xs = [x for x, _ in beam.points]
    return max(xs) - min(xs) <= TOLERANCE


def wall_section_for(section, existing: dict[str, PanelSection]) -> PanelSection:
    """The shell property set a pile's profile becomes, made once per profile.

    `CROSS_AREA` per metre run is exactly a thickness in metres
    (`PanelSection.from_beam_section`), the same reduction `core.kratos.writer._shell_section_of`
    writes into the deck. Shared by every wall built
    from that profile, so editing the profile moves all of them together.
    """
    key = f"{section.id}_wall"
    if key in existing:
        return existing[key]
    return PanelSection.from_beam_section(section, key, f"{section.name} wall")


def _panel_from(beam: Beam, project: Project, existing: Panel | None,
                section: PanelSection) -> Panel:
    """The solid model's view of a sheet pile.

    The footprint runs the whole out-of-plane width the first time, which is all the
    pile can say. On a later switch the counterpart's own `z` values are kept: the user
    may have narrowed the wall in plan, and a trip through the section is not a reason
    to undo that.
    """
    x = beam.points[0][0]
    ys = [y for _, y in beam.points]
    zs = ([point[1] for point in existing.footprint] if existing
          else [project.domain.z0, project.domain.z1])
    return Panel(
        id=existing.id if existing else f"{beam.id}_3d",
        name=_translated_name(beam, existing, "panel"),
        section=existing.section if existing else section.id,
        footprint=[(x, z) for z in zs],
        y_top=max(ys), y_toe=min(ys),
        active=beam.active,
        derived_from=existing.derived_from if existing else beam.id,
    )


def _beam_from(panel: Panel, project: Project, existing: Beam) -> Beam:
    """The section's view of a wall panel: where it crosses the cut, top to toe.

    Only ever used to refresh an existing pile, so the profile and the id it already
    has are kept; a panel with no pile behind it is not translated down at all.
    """
    x = panel.footprint[0][0]
    return Beam(
        id=existing.id, name=_translated_name(panel, existing, "beam"),
        section=existing.section,
        points=[(x, panel.y_top), (x, panel.y_toe)],
        active=panel.active,
        derived_from=existing.derived_from,
    )


def _partner_of(structure: Structure, by_id: dict[str, Structure],
                derived: dict[str, Structure]) -> Structure | None:
    """The other half of a translated pair, whichever half `structure` is."""
    if structure.derived_from is not None:
        return by_id.get(structure.derived_from)
    return derived.get(structure.id)


def translate(project: Project, dimension: int, log: list[str] | None = None
              ) -> tuple[list[Structure], list[PanelSection]]:
    """`project.beams` and `panel_sections`, with each wall's counterpart made or refreshed.

    Returns both because a translated panel needs a shell property set to reference,
    and the project validator rejects one that is not there.
    """
    sections = list(project.panel_sections)
    if dimension == project.dimension:
        return list(project.beams), sections

    def note(message: str) -> None:
        if log is not None:
            log.append(message)

    by_id = {b.id: b for b in project.beams}
    derived = {b.derived_from: b for b in project.beams if b.derived_from is not None}
    known = {s.id: s for s in sections}

    out: list[Structure] = list(project.beams)
    position = {b.id: i for i, b in enumerate(out)}
    added: list[tuple[int, Structure]] = []

    for beam in project.beams:
        partner = _partner_of(beam, by_id, derived)
        if dimension == 3 and isinstance(beam, Beam):
            if partner is not None and isinstance(partner, Panel):
                out[position[partner.id]] = _panel_from(
                    beam, project, partner, known[partner.section])
                note(f"{beam.name}'s wall panel is updated from the section.")
            elif partner is None and _is_vertical(beam):
                section = wall_section_for(project.beam_section(beam.section), known)
                if section.id not in known:
                    known[section.id] = section
                    sections.append(section)
                added.append((position[beam.id],
                              _panel_from(beam, project, None, section)))
                note(f"{beam.name} is now also a wall panel, spanning the model width.")
            elif partner is None:
                note(f"{beam.name} is not vertical, so it has no wall-panel form; it is "
                     "swept onto the section plane instead.")
        elif dimension == 2 and isinstance(beam, Panel):
            if partner is not None and isinstance(partner, Beam):
                out[position[partner.id]] = _beam_from(beam, project, partner)
                note(f"{beam.name}'s sheet pile is updated from the solid model.")

    for index, made in sorted(added, key=lambda pair: pair[0], reverse=True):
        out.insert(index + 1, made)
    return out, sections
