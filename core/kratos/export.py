"""Export the meshed model as a Kratos MultiPhysics `.mdpa` input deck.

The target is the file GiD writes for a Kratos GeoMechanics analysis: an empty
`Properties 0` block, one global node table, one `Elements` block per material body,
optional `Conditions` for the surface load, and one `SubModelPart` per body whose node
list is exactly the union of its elements' nodes.

One thing the deck does that the mesh does not: an interface. Where the project asks for
one, `core.kratos.interfaces` splits the meshed soil off the structure it was built conformal to
and this writes the zero-thickness elements that hold the two together again -- see the
`INTERFACES` table below.

Two conventions are load-bearing and both are checked by tests rather than assumed:

*   **Node ordering.** gmsh's TRI6 (`c1 c2 c3 m12 m23 m31`) is already Kratos'. Its
    TET10 is not: gmsh's last two midside nodes are m34, m24 where Kratos' are m24, m34,
    so the table below carries a permutation per element type.
*   **The plane.** A 2D project is a section at a constant coordinate along its normal
    axis -- an `xz` elevation lives at a constant *y*. Kratos plane strain reads X and Y
    only, so the section's own two axes are remapped onto X/Y with Z zeroed. Passing the
    world coordinates through would produce a model with no extent in Y.

The mesh is not re-generated here. `meshing.mesh_project` leaves the mesh in the gmsh
worker's model and this harvests it in the same job; rebuilding the geometry afterwards
would clear it.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import gmsh

from core.model import phases
from core.geometry import build, meshing
from core.kratos import files, interfaces
from core.kratos import materials as kratos_materials, processes as kratos_processes
from core.kratos.materials import material_parameters
from core.model.schemas import (Beam, LineLoad, MeshRequest, PanelSection, PointLoad,
                         Project, SurfaceLoad)

# (dim, gmsh element type) -> (Kratos class, gmsh index order in Kratos' order)
ELEMENTS: dict[tuple[int, int], tuple[str, tuple[int, ...]]] = {
    (2, 2): ("UPwSmallStrainElement2D3N", (0, 1, 2)),
    (2, 9): ("SmallStrainUPwDiffOrderElement2D6N", (0, 1, 2, 3, 4, 5)),
    (3, 4): ("UPwSmallStrainElement3D4N", (0, 1, 2, 3)),
    (3, 11): ("SmallStrainUPwDiffOrderElement3D10N", (0, 1, 2, 3, 4, 5, 6, 7, 9, 8)),
}

# Sheet piles: 1D structural elements living inside the 2D section, sharing its nodes.
# Both 2D classes and their (end, end, midside) connectivity are read off reference
# GeoMechanics decks, one of each order, so the gmsh order maps straight through.
#
# The 3D entries are the members: bored piles, king posts and struts. NOT CONFIRMED by
# any reference deck -- every one of them is plane strain -- so these follow Kratos
# StructuralMechanicsApplication's naming rather than a fixture here, exactly as the
# constitutive laws in core/kratos/materials.py already do. Check them against the first
# real 3D run; they are named here, in one place, so that is a one-line change.
#
# Every name here is checked against the registrations of the Kratos build that runs the
# deck (tests/kratos/test_kratos_registry.py). That is how two of them were found not to
# exist: Kratos has no 2-node *curved* beam (an older reference deck writes one anyway,
# so a first-order section with a pile never loaded) and no 3-node *straight* one
# in 3D. The 2-node beams are straight, the 3-node ones curved, in both dimensions.
BEAMS: dict[tuple[int, int], tuple[str, tuple[int, ...]]] = {
    (2, 1): ("LinearTimoshenkoBeamElement2D2N", (0, 1)),
    (2, 8): ("LinearTimoshenkoCurvedBeamElement2D3N", (0, 1, 2)),
    (3, 1): ("LinearTimoshenkoBeamElement3D2N", (0, 1)),
    (3, 8): ("LinearTimoshenkoCurvedBeamElement3D3N", (0, 1, 2)),
}

# Wall panels: 2D structural elements living inside the 3D solid, sharing its nodes.
# Kratos' shells are 3- and 4-node only -- there is no quadratic shell -- so a 6-node
# triangle is written from its three corners and the export says so. Same confidence
# note as the 3D beams above.
SHELLS: dict[tuple[int, int], tuple[str, tuple[int, ...]]] = {
    (3, 2): ("ShellThinElement3D3N", (0, 1, 2)),
    (3, 9): ("ShellThinElement3D3N", (0, 1, 2)),
}

# Zero-thickness contact between a structure and the soil, or between two soils. Only
# the quadratic class is pinned by a reference deck, which writes
# `Geo_UPwLineInterfacePlaneStrainDiffOrderElement3Plus3N` with six nodes -- three from
# the sheet pile, then their three coincident copies on one face of the soil -- and one
# element per pile segment per face, the two faces carrying opposite node orders.
#
# The linear name below follows the same convention with the DiffOrder infix dropped, as
# the beam and soil classes do between orders, but no reference deck contains it.
# Check it against the first real first-order run; it is named here alone.
#
# 2D only. Every reference deck is plane strain, and a 3D interface is a surface element
# with a different class, a different node layout and no fixture at all -- so a 3D
# project exports no interface and says so, rather than inventing one.
INTERFACES: dict[tuple[int, int], str] = {
    (2, 2): "Geo_UPwLineInterfacePlaneStrainElement2Plus2N",
    (2, 3): "Geo_UPwLineInterfacePlaneStrainDiffOrderElement3Plus3N",
}

TRUSSES: dict[int, str] = {
    2: "LinearTrussElement2D2N",
    3: "LinearTrussElement3D2N",
}
"""The anchor tie, per model dimension. The 2D name is read off a reference deck;
the 3D one is its documented counterpart and carries the same caveat as `SHELLS`."""

# The boundary of a 2D body is a line, of a 3D body a surface.
CONDITIONS: dict[tuple[int, int], tuple[str, tuple[int, ...]]] = {
    (2, 1): ("LineLoadCondition2D2N", (0, 1)),
    (2, 8): ("LineLoadDiffOrderCondition2D3N", (0, 1, 2)),
    (3, 2): ("UPwFaceLoadCondition3D3N", (0, 1, 2)),
    (3, 9): ("SurfaceLoadDiffOrderCondition3D6N", (0, 1, 2, 3, 4, 5)),
}

# A `NormalLoad`'s condition, keyed by node count rather than gmsh element type --
# `_normal_load_conditions` reads its rows off `_segments`, which already discards the
# type and hands back gmsh's own line order (already Kratos'), the same way `INTERFACES`
# is keyed. 2D only, like a free interface. Both names are confirmed against a working
# reference (Deltares/FEA-Tools' MiscellaneousTools/InterfaceInserter,
# test_create_interfaces.py for the linear class, a reference deck's ProjectParameters
# for the quadratic one).
#
# The linear name was `LineNormalLoadCondition2D2N` until the registry check above found
# no such condition in the Kratos that runs these decks; GeoMechanics' linear normal load
# is `UPwNormalFaceLoadCondition2D2N`, reading the same NORMAL_CONTACT_STRESS the
# normal-load process sets (tests/kratos/test_live_constructs.py runs it).
NORMAL_LOAD_CONDITIONS: dict[tuple[int, int], str] = {
    (2, 2): "UPwNormalFaceLoadCondition2D2N",
    (2, 3): "LineNormalLoadDiffOrderCondition2D3N",
}

# The edges of a 2D continuum element, in the order its own geometry generates them.
# Kratos matches a condition to its element by exact node-id sequence -- its
# NeighbouringElementFinder rotates faces only, never a line, and reverse search is off
# -- so a line condition carrying the right nodes in any other order is reported as
# having no neighbour element and the run stops before its first step. Keyed by node
# count, indices into connectivity already in Kratos order.
EDGES: dict[int, tuple[tuple[int, ...], ...]] = {
    3: ((0, 1), (1, 2), (2, 0)),
    6: ((0, 1, 3), (1, 2, 4), (2, 0, 5)),
}

# The faces of a 3D continuum element, as Kratos' own Tetrahedra3D4 / Tetrahedra3D10
# GenerateFaces lists them -- each pointing out of the element, corners then the
# matching mid-side nodes. Kratos matches a face condition to its element by node
# sequence up to *rotation* but never reversal, so a load face written the other way
# round is "found without any corresponding element" and the run stops. Keyed by node
# count, indices into connectivity already in Kratos order.
FACES: dict[int, tuple[tuple[int, ...], ...]] = {
    4: ((2, 3, 1), (0, 3, 2), (0, 1, 3), (0, 2, 1)),
    10: ((0, 2, 1, 6, 5, 4), (0, 3, 2, 7, 9, 6), (0, 1, 3, 4, 8, 7), (2, 3, 1, 9, 8, 5)),
}

# Reversing the first two corners flips an element; the midside nodes move with the
# edges they sit on. Keyed by node count, applied to connectivity already in Kratos
# order.
FLIP: dict[int, tuple[int, ...]] = {
    3: (0, 2, 1),
    6: (0, 2, 1, 5, 4, 3),
    4: (1, 0, 2, 3),
    10: (1, 0, 2, 3, 4, 6, 5, 8, 7, 9),
}

# Domain faces that become named node groups: (part name, world axis, Domain attribute).
BOUNDARIES = (
    ("Bottom_Fixed", 1, "y_bottom"),
    ("Left_Edge", 0, "x0"),
    ("Right_Edge", 0, "x1"),
    ("Front_Edge", 2, "z0"),
    ("Back_Edge", 2, "z1"),
    ("Top_Surface", 1, "y_top"),
)
RESERVED = {name for name, _, _ in BOUNDARIES}

LOWER_FACES = {"x0", "z0", "y_bottom"}
"""The `BOUNDARIES` attributes naming the low side of their axis; the rest are the high
side. Used to read each face off the meshed body rather than off the declared box."""

TOLERANCE = 1e-6
"""Metres. A node counts as lying on a domain face within this."""

# Indicators, not finite-element material: the load pad and the phreatic slab are never
# meshed, and `excavation` is an alias for soil that has been dug away.
NOT_MATERIAL = set(build.DISPLAY_ONLY) | {"excavation"}


class ExportError(RuntimeError):
    """The mesh cannot be expressed as a Kratos deck. Surfaced to the command log."""


def export_project(project: Project, settings: MeshRequest | None = None,
                   include_materials: bool = True) -> dict:
    """Mesh the project and render it as a Kratos deck.

    Returns `{"mdpa", "nodes", "elements", "materials", "initial_materials", "stats",
    "meshed_keys", "warnings", "log"}`, all JSON-safe, so it can cross the gmsh
    worker's process boundary unchanged. `materials` is None when the companion
    MaterialParameters.json is not wanted, and `initial_materials` is None unless some
    stage reads one -- only a deck with a K0 stage does (plan sec C4).

    Without `settings` the project meshes with the settings it carries (`Project.mesh`),
    the ones the GUI's Generate mesh uses. The call runs in a gmsh session of its own when
    there is none (`build.session` is re-entrant, so the worker's long-lived one is used
    as it is), which lets a script or a test export a model in one line.
    """
    if settings is None:
        settings = MeshRequest(**project.mesh.model_dump())
    with build.session():
        return _export(project, settings, include_materials)


def _export(project: Project, settings: MeshRequest, include_materials: bool) -> dict:
    mesh = meshing.mesh_project(
        project, element_size=settings.element_size, order=settings.order,
        refinements=settings.refinements, algorithm_3d=settings.algorithm_3d,
        algorithm_2d=settings.algorithm_2d, optimization=settings.optimization,
        smoothing=settings.smoothing, curvature_points=settings.curvature_points,
        size_min_factor=settings.size_min_factor,
        second_order_linear=settings.second_order_linear,
        volume_keys=settings.volume_keys, body_sizes=settings.body_sizes,
    )
    dim = 2 if project.dimension == 2 else 3
    names = _part_names(project)
    # Collected from here down rather than only out of the materials file: the deck
    # itself has things to say -- an interface a 3D model cannot carry, a wall written
    # one order below the soil around it.
    #
    # Seeded from `mesh.log`'s own curated notes -- every `core.geometry.build` line meant for a
    # person rather than gmsh's own chatter carries this exact "Info    : " padding
    # (gmsh's raw logger writes "Info: ..." instead, one space, so the two never
    # collide). A pile that never touches the soil, a wall drawn in the wrong mode --
    # these already explain themselves at build time; only `export.js` never asked to
    # see them before, so a structure could vanish from the deck with nothing in the
    # UI to say why.
    warnings: list[str] = [note[len("Info    : "):] for note in mesh.log
                           if note.startswith("Info    : ")]

    world = _world_coordinates()
    coordinates = _kratos_coordinates(world, dim)
    bodies = _bodies(project, dim)
    soil_blocks = [(key, name, _oriented(rows, coordinates, dim))
                   for key, name, rows in _harvest(bodies, dim)]
    blocks = list(soil_blocks)
    # Not passed through `_oriented`: a line has no signed area to be inside out, and
    # its 3-node form would collide with the triangle entry in `FLIP`. The mesher
    # already emits each segment in the order the beam was drawn.
    beam_blocks = _harvest(_beam_bodies(project, dim), 1, BEAMS, model_dim=dim)
    # A beam's node order is its local axis, and the sign of every force it reports
    # follows it, so it runs the way the user drew it rather than the way gmsh built
    # the curve. Done here, before the interface split reads these rows: which face of
    # the wall is which is settled by the drawn path too (`core/kratos/interfaces.py`), so both
    # answer to the same statement of intent.
    beam_blocks = [(key, name, _drawn_order(rows, _beam_of(project, key).points, world))
                   for key, name, rows in beam_blocks]
    blocks.extend(beam_blocks)
    # Nor are the wall shells: a sheet of steel has two faces and no "inside out", so
    # there is no signed area to correct -- only a normal, which is the wall's own.
    panel_blocks = _harvest(_panel_bodies(project, dim), 2, SHELLS, model_dim=dim)
    blocks.extend(panel_blocks)
    anchor_blocks, anchor_supports = _anchor_ties(project, dim, _world_coordinates())
    blocks.extend(anchor_blocks)
    conditions = (_load_conditions(project, dim, world, warnings) +
                 _normal_load_conditions(project, dim, warnings, world))
    # Last, because it rewrites what everything above produced: the interface unglues
    # the soil from the structures already harvested, so it needs their connectivity in
    # hand -- and the nodes it adds have to be in `world` before the boundary groups and
    # the node table are read off it.
    interface_blocks, interface_ties = _interface_elements(
        project, dim, soil_blocks, beam_blocks, conditions, world, coordinates, warnings)
    blocks.extend(interface_blocks)
    # Named here rather than in `_part_names`: which bodies a contact actually runs
    # against is a fact about the mesh, not about the project, and is not known until
    # the split above has run. `Interface_Soil_Top_lift1` -- the contact's own name,
    # then the body it holds -- which is how the reference deck names them too.
    for key, _, _ in interface_blocks:
        stem, _, body = key.partition("__")
        names.setdefault(key, f"{names[stem]}_{names[body]}" if body else names[stem])
    # After the interface split, so each condition is aligned to the copy of the soil it
    # ended up on rather than to the element it left behind.
    _align_conditions(conditions, soil_blocks)

    used = sorted({tag for _, _, rows in blocks for row in rows for tag in row}
                  | {tag for _, _, rows in conditions for row in rows for tag in row})
    node_id = {tag: index for index, tag in enumerate(used, start=1)}

    part_materials = _part_materials(project, names, blocks)
    numbered, parts = _number_elements(blocks, names, node_id)
    # Read here rather than off `parts` below: everything appended to it from this point
    # is a node- or condition-only group (a boundary, a load, an anchor support, a tie),
    # and the solver's domain lists may name only parts that carry elements.
    body_parts = [name for name, _, elements, _ in parts if elements]
    condition_blocks, load_parts = _number_conditions(conditions, names, node_id)
    # Soil only, which is what `_boundary_nodes` documents it measures the domain faces
    # from. `soil_blocks` is every continuum body, structures included: in 3D the wall
    # ring, the struts and the piles are solids too, and the ring is built *outboard* of
    # the pit face (`build._build_solids`), so a pit against the domain edge puts wall
    # outside the soil. Measured with it, the left face follows the wall and the soil's
    # own edge -- the one the excavation is dug against -- is not a boundary at all.
    body_tags = {tag for key, _, rows in soil_blocks if key.startswith("soil_")
                 for row in rows for tag in row}
    boundaries = _boundary_nodes(project, dim, world, node_id, body_tags)
    # Read off the harvested blocks rather than the geometry: after the interface split
    # a body's nodes are the copies it actually ended up with, and those are the ones a
    # constraint has to name.
    boundaries, boundary_owners = _segment_boundaries(
        project, boundaries,
        {key: {node_id[tag] for row in rows for tag in row if tag in node_id}
         for key, _, rows in soil_blocks if key.startswith("soil_")},
        names)
    parts.extend(_boundary_parts(boundaries))
    parts.extend(load_parts)
    supports = [(f"{names[key]}_Support", [node_id[tag]], [], [])
                for key, tag in anchor_supports.items() if tag in node_id]
    parts.extend(supports)
    # A node-only part per side of every tie `_split_ties` found, so the process below
    # can name them; see `_interface_elements`.
    ties = {}
    for key, master, slave in interface_ties:
        master_name, slave_name = f"{names[key]}_Master", f"{names[key]}_Slave"
        parts.append((master_name, sorted({node_id[tag] for tag in master}), [], []))
        parts.append((slave_name, sorted({node_id[tag] for tag in slave}), [], []))
        ties[key] = (master_name, slave_name)

    # The retained-side copies of the retained-side interfaces' nodes, as one node-only
    # part. An interface element's second half is its soil-side copy of the split nodes
    # (`_interface_by_body`), so the group is those halves, for the contacts that run
    # against soil outside the pit. Written only for a staged deck, which is the only
    # thing that reads it (plan sec C7).
    outside = {key for key, _, _, inside in project.soil_bodies() if not inside}
    retained_blocks = [(key, rows) for key, _, rows in interface_blocks
                       if key.partition("__")[2] in outside]
    right_side_part = None
    if project.phases and retained_blocks:
        retained_nodes = sorted({node_id[tag] for _, rows in retained_blocks
                                 for row in rows for tag in row[len(row) // 2:]
                                 if tag in node_id})
        if retained_nodes:
            right_side_part = RIGHT_SIDE_PART
            parts.append((right_side_part, retained_nodes, [], []))

    condition_keys = {key for key, _, rows in conditions if rows}
    active_loads = [(names[load.id], *_load_variable(load, dim))
                    for load in project.loads if load.id in condition_keys]
    # A hydrostatic load cannot exist without a water level (`Project` rejects it), so
    # the level read here is only ever missing for a uniform load, which ignores it.
    normal_load_processes = [
        (names[load.id], load.fluid_pressure_type, load.pressure,
         project.water.y if project.water is not None else project.domain.y_bottom,
         project.water_specific_weight)
        for load in project.active_normal_loads if load.id in condition_keys
    ]
    beam_properties = [(names[key], project.beam_section(_beam_of(project, key).section),
                        dim)
                       for key, _, _ in beam_blocks]
    panel_properties = [(names[key], _shell_section_of(project, key))
                        for key, _, _ in panel_blocks]
    anchor_properties = [(names[key], project.anchor_section(_anchor_of(project, key).section),
                          _anchor_of(project, key).prestress, dim)
                         for key, _, _ in anchor_blocks]
    # Third entry: the material of the soil body this stretch of contact runs against,
    # which is what its stiffness and strength are derived from unless the section names
    # one of its own. The body is in the block's own key -- `<interface>__<body>` -- and
    # `part_materials` has already worked out what every body is made of, so this is a
    # lookup rather than a second copy of that rule.
    material_by_part = dict(part_materials)
    interface_properties = [
        (names[key], project.interface_section(_interface_of(project, key).section),
         _adjacent_material(project, key, names, material_by_part))
        for key, _, _ in interface_blocks]
    try:
        materials, material_warnings = (
            material_parameters(project, part_materials, dim, beam_properties,
                                anchor_properties, panel_properties, interface_properties)
            if include_materials else (None, [])
        )
    except kratos_materials.MaterialError as failure:
        # A property set that cannot be written is the user's to fix, and says what;
        # surfaced like every other refusal of the export rather than as a crash.
        raise ExportError(str(failure)) from None
    warnings.extend(material_warnings)
    # Kratos has no quadratic shell, so a wall in a quadratic mesh is written from the
    # corner nodes of each 6-node face: compatible along the soil's linear edges, one
    # order below it along the curved ones. Said out loud rather than left to be found
    # in the deck.
    if panel_blocks and settings.order == 2:
        warnings.append(
            "the wall panels are written as linear shells inside a quadratic soil mesh "
            "-- Kratos has no 6-node shell. Mesh with order 1 for a fully compatible "
            "wall, or accept the linear approximation along its faces."
        )

    load_mask = [True, True, dim == 3]
    # The far end of every anchor is pinned: in this formulation the grouted body is a
    # fixed point, so the tie reacts against a restraint rather than against the soil.
    anchor_fixities = [(name, list(load_mask)) for name, _, _, _ in supports]
    # A sheet pile does not exist before it is installed: it and whichever interface(s)
    # tie it to the soil are staged together, deactivated in the deck's initial state and
    # activated in a wall-installation stage -- see `staged_construction.json`. Members
    # (3D) have no interface of their own kind and are not staged; nothing here invents a
    # construction sequence for them.
    wall_parts = ([names[key] for key, _, _ in beam_blocks] +
                  [names[key] for key, _, _ in interface_blocks
                   if _interface_of(project, key).structure is not None]) if dim == 2 else []
    staged_ties = list(ties.values()) if dim == 2 else []
    # Said out loud rather than left to be noticed in the deck (plan sec 7.13). The
    # restriction above stays -- nothing here invents a construction sequence for a 3D
    # structure -- but the phases panel is visible in 3D projects, so a user can build a
    # sequence in one and would otherwise get a deck quietly missing a part of it.
    #
    # Scoped to the case where the guards actually withhold something. A 3D project with
    # no structures loses nothing to them, and a warning on every 3D export is one people
    # stop reading. Deliberately *not* a claim that staging is plane-strain only: an
    # explicit phase list activates and deactivates its parts in 3D exactly as in 2D, and
    # `test_kratos_3d.py` holds both halves of that.
    if dim == 3 and (beam_blocks or interface_blocks):
        warnings.append(
            "staged construction is plane strain only where structures are concerned: "
            "this 3D model's walls, members and contacts are not staged, so they are "
            "present in every stage and get no installation stage of their own. A phase "
            "list still switches soil bodies, panels and anchors on and off as usual."
        )

    # Which model keys each deck part needs alive. Parts not named here own nothing and
    # are in every stage: the domain's own faces, and the node groups a tie holds.
    stageable = set(project.stageable_keys())
    owners: dict[str, tuple[str, ...]] = {name: () for name, *_ in parts}
    for key, _, _ in blocks:
        if key in stageable:
            owners[names[key]] = (key,)
        else:
            # An interface block is `<interface>__<body>`: it needs both, which is what
            # makes digging a lift out take the contact against it too.
            stem, _, body = key.partition("__")
            owners[names[key]] = tuple(k for k in (stem, body) if k in stageable)
    owners.update({name: (key,) for name, key in boundary_owners.items()})
    owners.update({names[key]: (key,) for key in condition_keys if key in stageable})
    owners.update({f"{names[key]}_Support": (key,) for key in anchor_supports
                   if key in stageable})

    interface_parts = tuple(names[key] for key, _, _ in interface_blocks)
    deck = _Deck(
        name=deck_name(project),
        owners=owners,
        bodies=tuple(body_parts),
        soils=tuple(names[key] for key, _, _ in soil_blocks
                    if key.startswith("soil_")),
        interfaces=interface_parts,
        retained=tuple(names[key] for key, _ in retained_blocks),
        beams=tuple(names[key] for key, _, _ in beam_blocks),
        structures=tuple(names[key] for key, _, _ in beam_blocks + anchor_blocks),
        ties=tuple((master, slave, key) for key, (master, slave) in ties.items())
             if dim == 2 else (),
        right_side=right_side_part,
    )
    stages = _stages(project, deck, wall_parts, staged_ties)
    # The initial stage reads a materials file of its own. Rendered only when a stage
    # actually names it, so an unphased deck is not shipped a file nothing opens.
    initial_materials = None
    if include_materials and any(
            stage.materials_filename == files.INITIAL_MATERIALS_NAME
            for stage in stages):
        initial_materials, _ = material_parameters(
            project, part_materials, dim, beam_properties, anchor_properties,
            panel_properties, interface_properties, k0=True)
    processes = kratos_processes.project_parameters(
        _boundary_constraints(project, dim, boundaries) + anchor_fixities,
        [(name, variable, load_mask, value) for name, variable, value in active_loads],
        stages,
        normal_load_processes,
        water=_phreatic(project),
        deck_name=deck_name(project),
        domain_size=dim,
        body_parts=body_parts,
        # A Timoshenko beam and a shell carry rotations; soil, a truss tendon and an
        # interface do not, and dofs no element uses cost memory for nothing.
        rotation_dofs=bool(beam_blocks or panel_blocks),
    )
    return {
        "mdpa": _render(coordinates, node_id, numbered, condition_blocks, parts),
        # What the deck's files are named after -- the .mdpa itself, the results, and
        # `model_import_settings.input_filename` inside the parameters above, which is
        # how Kratos finds the .mdpa again. Returned rather than re-derived by whoever
        # writes the files, so the name in the deck and the name on disk cannot drift.
        "deck_name": deck_name(project),
        # The system every number in the deck is in, recorded with the run so its results
        # are read in it (`calculate.write_deck`, `core.results.fields`).
        "unit_system": project.unit_system,
        # The node table on its own, in the deck's own numbering. The viewport's node-ID
        # labels can only be drawn from here: a gmsh tag is not a Kratos ID -- `node_id`
        # above renumbers 1..N over the tags the blocks actually use, and the interface
        # split has already added nodes of its own -- so nothing short of this pass knows
        # what number a node will carry in the file.
        "nodes": [[index, *coordinates[tag]]
                  for tag, index in sorted(node_id.items(), key=lambda item: item[1])],
        # Where each element's number goes when the viewport draws it: its own centre.
        # Same pass, same reason as the node table -- an element id is assigned here, in
        # emission order, and exists nowhere before this function runs.
        "elements": _element_labels(coordinates, node_id, numbered),
        "materials": materials,
        "initial_materials": initial_materials,
        "project_parameters": processes,
        "stats": mesh.stats.to_dict(),
        "meshed_keys": mesh.meshed_keys,
        "warnings": warnings,
        "log": mesh.log,
    }




def _adjacent_material(project: Project, key: str, names: dict[str, str],
                       material_by_part: dict[str, str]):
    """The material of the soil body an interface block runs against, or None.

    None for a contact with no soil behind it -- a free interface in air, or a body with
    no material -- in which case the section has to carry the answer itself.
    """
    body = key.partition("__")[2]
    material_id = material_by_part.get(names.get(body, ""))
    return project.material(material_id) if material_id else None


# ── Stages ──────────────────────────────────────────────────────────────────
# Turning `Project.phases` into the deck's stages. The phase model speaks the user's
# vocabulary -- one drawn `Interface`, one soil body per lift -- and the deck speaks its
# own, in which that interface is eight parts and each of them is tied to the body it
# runs against. Translating between the two is this section's whole job, and it is why
# `core.model.phases` knows nothing about Kratos: the model has no business knowing that
# digging out a lift also removes a contact.

WALL_OUTPUT_VARIABLES = ("BENDING_MOMENT", "SHEAR_FORCE", "AXIAL_FORCE",
                         "TOTAL_DISPLACEMENT")
WALL_EXTRAPOLATED = ("AXIAL_FORCE", "BENDING_MOMENT", "SHEAR_FORCE")
INTERFACE_VARIABLES = ("GEO_EFFECTIVE_TRACTION_VECTOR",)
RIGHT_SIDE_PART = "Right_Side_Of_Right_Interfaces"
"""The retained-side nodes of the retained-side interfaces, as a node-only sub-model
part. Written only when something reads it -- the `JsonOutputProcess` a staged deck
carries -- so an unphased project does not grow a part it never names (plan sec C7)."""


@dataclass(frozen=True)
class _Deck:
    """What the stage builder needs to know about the deck it is staging.

    Everything here is in *deck* part names except `owners`, which is the bridge: for
    each deck part, the model keys it needs alive. A part with no owners -- the domain's
    own `Bottom_Fixed`, a tie's node groups -- is in every stage.
    """
    name: str
    owners: dict[str, tuple[str, ...]]
    bodies: tuple[str, ...]
    soils: tuple[str, ...]
    interfaces: tuple[str, ...]
    retained: tuple[str, ...]
    beams: tuple[str, ...]
    structures: tuple[str, ...]
    ties: tuple[tuple[str, str, str], ...] = ()
    right_side: str | None = None


def _deck_active(deck: _Deck, keys: set[str]) -> frozenset[str]:
    """The deck parts alive when `keys` are the model's active parts.

    One rule, applied to everything: a deck part is alive while every model key it was
    built from is. That is what pairs an interface with the soil body it holds (it is
    owned by both, so digging the body away takes it too) and what makes a lift's
    stretch of the left edge vanish with the lift -- without either being written down
    as a special case anywhere.
    """
    return frozenset(name for name, owned in deck.owners.items()
                     if all(key in keys for key in owned))


def _stages(project: Project, deck: _Deck, staged_parts: list[str],
            staged_ties: list[tuple[str, str]]) -> list[kratos_processes.Stage]:
    """The deck's stages, in execution order.

    A project with no phases exports exactly the deck it exported before staged
    construction existed -- one stage, or the implicit two a sheet pile has always
    produced. That is the compatibility contract, and it is a gate rather than a
    special case of the staged path so that nothing in the staged path can reach a
    project that never asked for it.
    """
    if not project.phases:
        if not staged_parts:
            return [kratos_processes.Stage(name=kratos_processes.STAGE_NAME)]
        return [
            kratos_processes.Stage(
                name=kratos_processes.INITIAL_STAGE_NAME, modeler=True,
                deactivate=tuple(staged_parts), ties=tuple(staged_ties)),
            kratos_processes.Stage(
                name=kratos_processes.WALL_INSTALLATION_STAGE_NAME,
                activate=tuple(staged_parts), start_time=1.0),
        ]
    return _phased_stages(project, deck)


def _phased_stages(project: Project, deck: _Deck) -> list[kratos_processes.Stage]:
    """One stage per phase. Raises `phases.PhaseError` if the tree does not linearise."""
    steps = phases.transitions(project)

    # The reference deck starts at -2.0: its K0 stage and its null step sit at negative
    # time so that real construction starts at 0 and two runs' result files line up
    # stage for stage. Cosmetic to Kratos, and free to reproduce -- the leading run of
    # phases that are not ordinary plastic steps is exactly what "before construction"
    # means.
    settling = 0
    for phase, _, _ in steps:
        if phase.calculation == "Plastic":
            break
        settling += 1

    out: list[kratos_processes.Stage] = []
    keys = set(project.stageable_keys())
    live = _deck_active(deck, keys)
    for index, (phase, switched_on, switched_off) in enumerate(steps):
        was = live
        keys = (set(keys) - switched_off) | switched_on
        live = _deck_active(deck, keys)

        # The operations name element-carrying parts only, which is what Activate and
        # Deactivate act on; a node group vanishes from the process lists instead, by
        # way of the filter `Stage.active` drives. Derived from the two states rather
        # than from the phase's own lists, so the interface that goes with a body needs
        # no rule of its own here.
        activate = tuple(name for name in deck.bodies if name in live and name not in was)
        deactivate = tuple(name for name in deck.bodies
                           if name in was and name not in live)

        k0 = phase.calculation == "K0 procedure"
        arriving = [name for name in deck.interfaces if name in activate]
        # Stresses carry over for what was already there *and* still is. A part being
        # installed in this stage has no previous stress to carry, which is why the
        # reference leaves the anchor out of stage 5 and puts it back in stage 6.
        carried = tuple(name for name in deck.interfaces + deck.structures
                        if name in live and name in was)
        beams = tuple(name for name in deck.beams if name in live)
        retained = tuple(name for name in deck.retained if name in live)

        extrapolate = ()
        if beams:
            extrapolate += ((beams, WALL_EXTRAPOLATED),)
        if retained:
            extrapolate += ((retained, INTERFACE_VARIABLES),)

        output = ()
        if beams:
            output += ((beams[0], "output_wall", WALL_OUTPUT_VARIABLES),)
        if retained and deck.right_side:
            output += ((deck.right_side, "output_interface", INTERFACE_VARIABLES),)

        out.append(kratos_processes.Stage(
            name=kratos_processes.stage_name(index, phase.name),
            activate=activate,
            deactivate=deactivate,
            active=live,
            bodies=tuple(name for name in deck.bodies if name in live),
            start_time=float(index - settling),
            modeler=index == 0,
            # The tie holds the two copies of a split node together for as long as the
            # structure that split them is not installed. Derived from the interface's
            # own activation rather than counted: in the reference that is stages 1 and
            # 2, and in a project whose wall goes in later it is however many stages
            # come first.
            ties=tuple((master, slave) for master, slave, key in deck.ties
                       if key not in keys),
            k0_parts=tuple(name for name in deck.soils if name in live) if k0 else (),
            find_neighbours=tuple(arriving),
            final_stresses=carried,
            extrapolate=extrapolate,
            json_output=output,
            reset_displacements=phase.reset_displacements,
            max_iterations=phase.max_iterations,
            tolerated_error=phase.tolerated_error,
            materials_filename=(files.INITIAL_MATERIALS_NAME if k0
                                else files.MATERIALS_NAME),
        ))
    return out


# ── Interfaces ──────────────────────────────────────────────────────────────

def _interface_elements(project: Project, dim: int,
                        soil_blocks: list[tuple[str, str, list[list[int]]]],
                        beam_blocks: list[tuple[str, str, list[list[int]]]],
                        conditions: list[tuple[str, str, list[list[int]]]],
                        world: dict[int, tuple[float, float, float]],
                        coordinates: dict[int, tuple[float, float, float]],
                        warnings: list[str]
                        ) -> tuple[list[tuple[str, str, list[list[int]]]],
                                   list[tuple[str, list[int], list[int]]]]:
    """Unglue the soil along every active interface and write the contact elements.

    The topology is `core.kratos.interfaces`' job and is done on connectivity alone; what
    happens here is the bookkeeping around it. The soil rows are rewritten onto the
    copies, the copies inherit their originals' coordinates -- which is what makes the
    element zero-thickness -- and any load condition standing on a split node follows
    the element it belongs to, so a surface load beside a wall stays on the soil rather
    than being left on the wall's own node.

    A 3D project exports no interface: see the `INTERFACES` table for why.

    Also returns, per interface that follows a staged structure, the raw node tags to
    tie together with a master/slave constraint while that structure is not installed
    yet -- see `_split_ties`.
    """
    active = project.active_interfaces
    if not active:
        if project.dimension != 2 and any(i.active for i in project.interfaces):
            warnings.append(
                "interfaces are plane-strain only and none was written into this 3D "
                "deck; the structures are meshed bonded to the soil."
            )
        return [], []

    beam_rows = {key: rows for key, _, rows in beam_blocks}
    specs = []
    for interface in active:
        if interface.structure is None:
            segments = _segments(_tagged(1).get(interface.id, []))
            path = [tuple(point) for point in interface.points]
        else:
            segments = beam_rows.get(interface.structure, [])
            path = [tuple(point) for point in
                    _beam_of(project, interface.structure).points]
        if not segments:
            raise ExportError(
                f"interface {interface.name!r} has no mesh along its line -- the line "
                "it follows lies outside the soil in this section, so there is nothing "
                "for the contact to hold."
            )
        specs.append(interfaces.Spec(key=interface.id, path=path, segments=segments,
                                     structural=interface.structure is not None,
                                     sides=interface.side))

    flat: list[list[int]] = []
    spans = []
    for _, _, rows in soil_blocks:
        spans.append((len(flat), len(rows)))
        flat.extend(rows)
    before = [list(row) for row in flat]

    try:
        split = interfaces.split_mesh(specs, flat, coordinates)
    except interfaces.InterfaceError as failure:
        raise ExportError(str(failure)) from None

    for (start, count), (_, _, rows) in zip(spans, soil_blocks):
        rows[:] = flat[start:start + count]
    for new_tag, source in split.duplicates.items():
        coordinates[new_tag] = coordinates[source]
        world[new_tag] = world[source]
    # The nodes the structures own, so a load standing on one is not dragged onto the
    # soil beside it. Beams only: a panel is a 3D wall and interfaces are plane strain.
    _follow_the_soil(conditions, before, split,
                     frozenset(node for _, _, rows in beam_blocks
                               for row in rows for node in row))

    out = []
    ties = []
    for interface in active:
        rows = split.elements.get(interface.id) or []
        if not rows:
            continue
        per_side = len(rows[0]) // 2
        name = INTERFACES.get((dim, per_side))
        if name is None:
            raise ExportError(
                f"no Kratos interface element is mapped for {per_side} nodes a side in "
                f"{dim}D. Mesh the section with linear or quadratic triangles."
            )
        # One block per soil body the contact runs against, not one per interface. A
        # lift is deactivated in its own phase and the contact along it has to go at the
        # same moment: an interface still holding a face whose soil has been dug away
        # would carry shear against nothing. The reference deck splits the same way --
        # `Interface_Excavated_Soil_1` beside `Interface_Soil_Top_Right` -- and a
        # `side="both"` contact contributes to two bodies at once, one per face.
        for body_key, body_rows in _interface_by_body(rows, per_side, soil_blocks):
            out.append((f"{interface.id}__{body_key}", name, body_rows))
        # Ties stay per interface. They hold the two copies of a split node together
        # while the structure is not installed, which is one question about the whole
        # line, not one per body it happens to pass.
        if interface.structure is not None:
            master, slave = _split_ties(rows, per_side, split.duplicates)
            if master and slave:
                ties.append((interface.id, master, slave))
    return out, ties


def _interface_by_body(rows: list[list[int]], per_side: int,
                       soil_blocks: list[tuple[str, str, list[list[int]]]]
                       ) -> list[tuple[str, list[list[int]]]]:
    """Group contact elements by the soil body each one runs against.

    An interface element's second half is its soil-side copy of the split nodes (see
    `_split_ties`), and those nodes came out of exactly one soil element, so they answer
    which body this stretch of contact belongs to. A node on the seam between two bodies
    belongs to both, so the body is the one *all* of the element's soil-side nodes
    agree on; where they cannot agree -- which happens only if a contact element spans a
    seam -- the first in block order is taken, so the grouping is deterministic rather
    than dependent on set iteration.
    """
    bodies: dict[int, list[str]] = {}
    for key, _, body_rows in soil_blocks:
        if not key.startswith("soil_"):
            continue
        for row in body_rows:
            for node in row:
                if key not in bodies.setdefault(node, []):
                    bodies[node].append(key)

    grouped: dict[str, list[list[int]]] = {}
    for row in rows:
        shared: list[str] | None = None
        for node in row[per_side:]:
            owners = bodies.get(node, [])
            shared = owners if shared is None else [k for k in shared if k in owners]
        if not shared:
            # No soil on this side at all: the contact runs against the structure only,
            # which nothing in the deck can name a body for.
            continue
        grouped.setdefault(shared[0], []).append(row)
    return list(grouped.items())


def _split_ties(rows: list[list[int]], per_side: int, duplicates: dict[int, int]
                ) -> tuple[list[int], list[int]]:
    """Pair up the soil-side copies of every node the interface split into two.

    A node in the middle of the line gets exactly two copies, one per face (see
    `core.kratos.interfaces`'s module docstring) -- while the structure that owns the line is
    staged (deactivated, then activated on installation -- see `kratos_processes`),
    nothing else holds those two copies together, so they need a master/slave tie for
    the stage(s) before installation. A node with only one copy is the toe, where the
    ground closes under the structure and is already continuous; it needs no tie.

    The pairing is exact, not discovered by search: each node in one list has exactly one
    true partner, at zero distance, in the other. That made
    `minimum_number_of_neighbouring_nodes` 1 here for a while, and running the deck
    showed why it cannot be -- see `kratos_processes.MASTER_SLAVE_NEIGHBOURS`. The
    geometry below is unchanged by that; only what Kratos is asked to do with it.
    """
    by_original: dict[int, set[int]] = {}
    for row in rows:
        for node in row[per_side:]:
            original = duplicates.get(node)
            if original is not None:
                by_original.setdefault(original, set()).add(node)

    master, slave = [], []
    for copies in by_original.values():
        if len(copies) != 2:
            continue
        first, second = sorted(copies)
        master.append(first)
        slave.append(second)
    return master, slave


def _segments(entities: list[int]) -> list[list[int]]:
    """The mesh's own line elements on a set of curves, `(end, end)` or
    `(end, end, midside)` -- gmsh's line order, which is already Kratos'."""
    rows = []
    for entity in entities:
        types, _, connectivity = gmsh.model.mesh.getElements(1, entity)
        for element_type, flat in zip(types, connectivity):
            stride = gmsh.model.mesh.getElementProperties(int(element_type))[3]
            for offset in range(0, len(flat), stride):
                rows.append([int(flat[offset + i]) for i in range(stride)])
    return rows


def _follow_the_soil(conditions: list[tuple[str, str, list[list[int]]]],
                     before: list[list[int]], split: interfaces.Split,
                     structural: frozenset[int] = frozenset()) -> None:
    """Move every condition standing on a split node onto the copy its own soil got.

    A condition is usually a face of one continuum element, so the element that
    contained all of its nodes before the split is the body it belongs to, and it is
    renamed exactly as that element was.

    **Unless it stands on a structure.** A load running down a wall is on the wall, not
    on either copy of the ground beside it, and the wall keeps the original nodes while
    both soil sides take copies. Left to the rule above, such a condition finds whichever
    soil element happens to hold all its nodes first -- the retained side -- and moves
    there. The excavation's own water load then pressed the retained ground *away* from
    the wall instead of pressing on the exposed face, and the retained interface's
    traction fell to zero and went into tension as the pit was dug. Found by running the
    deck and comparing tractions stage by stage; nothing in the file looks wrong.

    So a row whose nodes all belong to a structure is left where it is, which is on the
    structure.
    """
    sources = set(split.duplicates.values())
    for _, _, rows in conditions:
        for index, row in enumerate(rows):
            if not sources.intersection(row):
                continue
            if structural and set(row) <= structural:
                continue
            owner = next((i for i, element in enumerate(before)
                          if set(row) <= set(element)), None)
            if owner is None:
                continue
            rows[index] = [split.renamed[owner].get(node, node) for node in row]


def _interface_of(project: Project, key: str):
    """The interface a block key names. Blocks are emitted one per soil body the
    contact runs against (`_interface_by_body`), so the key carries the body after a
    `__` and the interface's own id is what comes before it."""
    stem = key.partition("__")[0]
    return next(interface for interface in project.interfaces if interface.id == stem)

def _anchor_ties(project: Project, dim: int,
                 world: dict[int, tuple[float, float, float]]
                 ) -> tuple[list[tuple[str, str, list[list[int]]]], dict[str, int]]:
    """One two-node truss per active anchor, plus the tail node each one is held by.

    Built from located nodes rather than harvested from a meshed curve, the same way a
    point load's condition is. That is what makes the result match the reference deck
    exactly: one linear element whatever the mesh order, with the head node the beam
    already owns and a tail node bonded to nothing.

    The head is resolved to a *beam* node specifically. `build._attach_anchors` draws
    the anchor as display geometry whose own head vertex sits at the same place, so a
    plain nearest-node search could pick that stray instead of the pile's node.
    """
    # In 3D both kinds are live: a space anchor is drawn in the model, and a plane
    # anchor hangs off the sheet pile that `build._section_sweeps` put on the cut.
    anchors = (project.plane_anchors if dim == 2
               else project.plane_anchors + project.space_anchors)
    # The structures an anchor may hang from: a 2D head is on a sheet pile, a 3D head on
    # a wall or a member. Resolved to *structural* nodes specifically, because
    # `build._attach_anchors` draws the tie's own head vertex at the same place and a
    # plain nearest-node search could pick that stray instead.
    structural = {tag for _, _, rows in _harvest(_beam_bodies(project, dim), 1, BEAMS,
                                                 model_dim=dim)
                  for row in rows for tag in row}
    structural |= {tag for _, _, rows in _harvest(_panel_bodies(project, dim), 2, SHELLS,
                                                  model_dim=dim)
                   for row in rows for tag in row}
    blocks, supports = [], {}
    for anchor in anchors:
        if not anchor.active:
            continue
        head = _node_at(anchor.head, project, world, structural)
        tail = _node_at(anchor.tail, project, world, None)
        if head is None or tail is None:
            raise ExportError(
                f"anchor {anchor.name!r} has no mesh node at its "
                f"{'head' if head is None else 'tail'}; re-mesh the model."
            )
        blocks.append((anchor.id, TRUSSES[dim], [[head, tail]]))
        supports[anchor.id] = tail
    return blocks, supports


def _node_at(point: tuple[float, ...], project: Project,
             world: dict[int, tuple[float, float, float]],
             among: set[int] | None) -> int | None:
    """The mesh node on an anchor end, in world coordinates, or None.

    A 2D anchor is dimension-native `(x, y)`, which is exactly the first two world
    axes now that the section is the x-y plane; a 3D one is in world coordinates
    already. Either way the comparison is direct.
    """
    axes = (0, 1, 2) if len(point) == 3 else (0, 1)
    for tag, xyz in world.items():
        if among is not None and tag not in among:
            continue
        if all(abs(xyz[axis] - value) <= TOLERANCE
               for axis, value in zip(axes, point)):
            return tag
    return None


def _anchor_of(project: Project, key: str):
    return next(anchor for anchor in project.anchors if anchor.id == key)


def _beam_of(project: Project, key: str) -> Beam:
    return next(beam for beam in project.beams if beam.id == key)


def _panel_of(project: Project, key: str):
    return next(panel for panel in project.panels if panel.id == key)


def _shell_section_of(project: Project, key: str) -> PanelSection:
    """The shell property set behind a surface structure, whichever kind drew it.

    A panel carries a thickness already. A sheet pile carries `area` in m2 per metre
    run -- which *is* a thickness in metres, the plane-strain reduction `PanelSection`
    documents read backwards -- so the swept wall is written with exactly the steel the
    section was drawn with. The sweep width never enters it: widening the strip
    (`BeamSection.spacing`) spreads the same wall over more of the model, it does not
    add material to it.
    """
    panel = next((p for p in project.panels if p.id == key), None)
    if panel is not None:
        return project.panel_section(panel.section)
    beam = project.beam_section(_beam_of(project, key).section)
    return PanelSection.from_beam_section(beam, beam.id, beam.name)


def _load_variable(load: PointLoad | LineLoad | SurfaceLoad,
                   dim: int) -> tuple[str, list[float]]:
    """The Kratos variable name and world-shaped value a load's condition carries.

    It reaches the solver through a ProjectParameters.json process against the load's
    sub-model part; the .mdpa itself names the part and its conditions and nothing more.
    """
    components = [load.components[0], load.components[1], 0.0] if dim == 2 \
        else list(load.components)
    variable = {"point": "POINT_LOAD", "line": "LINE_LOAD",
               "surface": "SURFACE_LOAD"}[load.kind]
    return variable, components


# ── Reading the mesh back out of gmsh ───────────────────────────────────────

def _phreatic(project: Project) -> tuple[float, float]:
    """(level, specific weight) the pore pressure is fixed about.

    A dry model has no level, and its pressure degrees of freedom still need fixing. The
    level is then the bottom of the model: Kratos writes
    `min(-gamma * (level - y), pressure_tension_cut_off)` at each node and the cut-off
    defaults to 0 (GeoMechanicsApplication, apply_constant_hydrostatic_pressure_process.cpp),
    so every node at or above it -- which is every node -- gets exactly zero, fixed. The
    same process the validated decks use, so nothing new is asked of Kratos.
    """
    if project.water is None:
        return (project.domain.y_bottom, project.water_specific_weight)
    return (project.water.y, project.water_specific_weight)


def _world_coordinates() -> dict[int, tuple[float, float, float]]:
    tags, flat, _ = gmsh.model.mesh.getNodes()
    return {int(tag): (float(flat[3 * i]), float(flat[3 * i + 1]), float(flat[3 * i + 2]))
            for i, tag in enumerate(tags)}


def _kratos_coordinates(world: dict[int, tuple[float, float, float]], dim: int
                        ) -> dict[int, tuple[float, float, float]]:
    """World coordinates are Kratos coordinates, in both dimensions.

    There is nothing to remap since the re-basis: a 2D model is the x-y plane, which is
    the plane Kratos writes a plane-strain deck in, and `build._section` has already
    moved it onto z = 0. Asserted rather than assumed -- a 2D node off the plane would
    otherwise reach the deck as a silently wrong third coordinate.
    """
    if dim == 2:
        off_plane = [tag for tag, xyz in world.items() if abs(xyz[2]) > TOLERANCE]
        if off_plane:
            raise ValueError(
                f"{len(off_plane)} node(s) of the 2D mesh lie off the z = 0 plane; "
                "the section was not flattened"
            )
    return world


def _bodies(project: Project, dim: int) -> dict[str, list[int]]:
    """Part key -> entity tags, from the physical groups `build` tagged, in tree order.

    Physical groups are the identity contract the rest of the app already uses, so the
    deck's bodies are the same bodies the model tree and the viewport name.
    """
    tagged: dict[str, list[int]] = {}
    for group_dim, tag in gmsh.model.getPhysicalGroups(dim):
        name = gmsh.model.getPhysicalName(group_dim, tag)
        tagged[name] = [int(t) for t in gmsh.model.getEntitiesForPhysicalGroup(group_dim, tag)]
    # A normal load's key names a display ribbon at this dimension (build's
    # `_build_display_only`) and the line its condition sits on one dimension down, so
    # it is excluded here for the same reason a load id is: the symbol is not a body.
    load_keys = ({load.id for load in project.loads}
                 | {load.id for load in project.normal_loads})
    return {key: tagged[key] for key in project.part_keys()
            if key in tagged and key not in NOT_MATERIAL and key not in load_keys}


def _tagged(dim: int) -> dict[str, list[int]]:
    """Physical group name -> entity tags, for one dimension."""
    return {
        gmsh.model.getPhysicalName(dim, tag):
            [int(t) for t in gmsh.model.getEntitiesForPhysicalGroup(dim, tag)]
        for _, tag in gmsh.model.getPhysicalGroups(dim)
    }


def _beam_bodies(project: Project, dim: int) -> dict[str, list[int]]:
    """Beam key -> 1D entity tags: the sheet piles in a 2D section, the members in 3D.

    Both are curves inside the continuum they stand in, so they are harvested the same
    way and differ only in which Kratos class the model's dimension picks.
    """
    structures = project.sheet_piles if dim == 2 else project.members
    tagged = _tagged(1)
    return {beam.id: tagged[beam.id] for beam in structures
            if beam.active and tagged.get(beam.id)}


def _panel_bodies(project: Project, dim: int) -> dict[str, list[int]]:
    """Panel key -> 2D entity tags, for the walls embedded in the 3D solid.

    Empty in 2D: a wall is drawn in plan and has no place in a plane-strain cut, which
    `build._embed_beams` has already logged.
    """
    if dim != 3:
        return {}
    tagged = _tagged(2)
    # A sheet pile swept onto the section plane is a surface like a panel is, so it is
    # harvested as one. Which property set it binds is the only thing that differs, and
    # `_shell_section_of` is where that is decided.
    walls = list(project.panels) + list(project.sheet_piles)
    return {wall.id: tagged[wall.id] for wall in walls
            if wall.active and tagged.get(wall.id)}


def _harvest(bodies: dict[str, list[int]], dim: int, table: dict | None = None,
             model_dim: int | None = None) -> list[tuple[str, str, list[list[int]]]]:
    """One (part key, Kratos class, connectivity rows) per body and element type.

    `dim` is the dimension of the *entities* read from gmsh; `model_dim` is the one the
    element table is keyed by. They differ for the sheet piles alone: a beam is a curve
    (`dim` 1) but its Kratos class is named for the plane-strain model it lives in
    (`model_dim` 2), which is also what tells a 2D beam from a 3D one.
    """
    out = []
    for key, entities in bodies.items():
        rows_by_class: dict[str, list[list[int]]] = {}
        for entity in entities:
            types, _, connectivity = gmsh.model.mesh.getElements(dim, entity)
            for element_type, flat in zip(types, connectivity):
                name, order = _lookup(table or ELEMENTS,
                                      dim if model_dim is None else model_dim,
                                      int(element_type))
                # The stride is what gmsh wrote, which is not always what Kratos reads:
                # a 6-node triangle becomes a 3-node shell, because Kratos has no
                # quadratic shell to pair with a quadratic soil mesh.
                stride = gmsh.model.mesh.getElementProperties(int(element_type))[3]
                rows = rows_by_class.setdefault(name, [])
                for offset in range(0, len(flat), stride):
                    rows.append([int(flat[offset + i]) for i in order])
        for name, rows in rows_by_class.items():
            if rows:
                out.append((key, name, rows))
    return out


def _lookup(table: dict, dim: int, element_type: int) -> tuple[str, tuple[int, ...]]:
    try:
        return table[(dim, element_type)]
    except KeyError:
        shape = gmsh.model.mesh.getElementProperties(element_type)[0]
        raise ExportError(
            f"no Kratos element is mapped for a {shape} in {dim}D. Mesh with linear or "
            "quadratic simplices, or add the type to core/kratos/export.py."
        ) from None


def _oriented(rows: list[list[int]], coordinates: dict[int, tuple[float, float, float]],
              dim: int) -> list[list[int]]:
    """Flip any element whose corners run the wrong way.

    gmsh is consistent, but a negative Jacobian is silent in the deck and fatal in the
    solver, so it is cheaper to check every element than to trust the mesher.
    """
    fixed = []
    for row in rows:
        corners = [coordinates[tag] for tag in row[:dim + 1]]
        if _signed_measure(corners, dim) < 0:
            row = [row[i] for i in FLIP[len(row)]]
        fixed.append(row)
    return fixed


def _signed_measure(corners: list[tuple[float, float, float]], dim: int) -> float:
    if dim == 2:
        (x1, y1, _), (x2, y2, _), (x3, y3, _) = corners
        return (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
    a, b, c, d = corners
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    w = [d[i] - a[i] for i in range(3)]
    cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    return sum(cross[i] * w[i] for i in range(3))


def _load_conditions(project: Project, dim: int,
                     world: dict[int, tuple[float, float, float]],
                     warnings: list[str] | None = None
                     ) -> list[tuple[str, str, list[list[int]]]]:
    """Each load's conditions: the elements `meshing.loaded_elements` finds under it,
    under the class `CONDITIONS` names for their gmsh type, or for a point load its one
    node as a `PointLoadCondition`."""
    for load in project.loads_for(dim):
        if dim == 3 and load.active and load.kind == "line" and warnings is not None:
            # A line load imprints a *curve* on the solid's boundary, and the boundary
            # elements `loaded_elements` harvests are faces. CONDITIONS has no 3D line
            # class to write it with, and inventing one with no reference deck behind it
            # would be a guess in the deck rather than in a comment. Said out loud
            # instead: the load is drawn and meshed, but it is not applied.
            warnings.append(
                f"{load.name!r} is a line load, which has no Kratos condition in a "
                "3D deck; it is drawn at the section plane but applies no force. "
                "Move it to the ground surface so it translates to a surface load, "
                "or apply it in the 2D section."
            )
    out: list[tuple[str, str, list[list[int]]]] = []
    for key, element_type, rows in meshing.loaded_elements(project, dim, world):
        if element_type == meshing.POINT:
            out.append((key, f"PointLoadCondition{dim}D1N", rows))
            continue
        name, order = _lookup(CONDITIONS, dim, element_type)
        out.append((key, name, [[row[i] for i in order] for row in rows]))
    return out


def _normal_load_conditions(project: Project, dim: int, warnings: list[str],
                            world: dict[int, tuple[float, float, float]] | None = None
                            ) -> list[tuple[str, str, list[list[int]]]]:
    """One condition per active `NormalLoad`, off the line `build._embed_beams` already
    gave its own physical group -- the same way a free interface's line is found.

    Unlike `meshing.loaded_elements`, this does not scan the boundary at a fixed
    elevation: a normal load can run down a vertical face, which has no single elevation
    to scan for, so it is read straight off the mesh instead.
    """
    if project.dimension != 2 and any(n.active for n in project.normal_loads):
        warnings.append(
            "a normal load is plane-strain only and none was written into this 3D "
            "deck; it is drawn at the section plane but applies no pressure."
        )
    out = []
    for load in project.active_normal_loads:
        rows = _segments(_tagged(1).get(load.id, []))
        if not rows:
            raise ExportError(
                f"normal load {load.name!r} has no mesh along its line -- the line it "
                "follows lies outside the soil in this section, so there is nothing "
                "for the condition to hold."
            )
        per_row = len(rows[0])
        name = NORMAL_LOAD_CONDITIONS.get((dim, per_row))
        if name is None:
            raise ExportError(
                f"no Kratos condition is mapped for a normal load with {per_row} "
                f"nodes a segment in {dim}D. Mesh the section with linear or "
                "quadratic elements."
            )
        # Along the drawn line, so the whole loaded surface carries one outward
        # normal; `_align_conditions` then keeps that direction when it puts each
        # segment onto an element edge.
        if world is not None:
            rows = _drawn_order(rows, [tuple(point) for point in load.points], world)
        out.append((load.id, name, rows))
    return out


def _drawn_order(rows: list[list[int]], path: list[tuple[float, float]],
                 world: dict[int, tuple[float, float, float]]) -> list[list[int]]:
    """Turn each harvested segment to run the way its line was drawn.

    gmsh hands a curve's elements out in the direction it happened to build the curve,
    which is not always the direction the user drew it, and for a line the node order is
    not bookkeeping:

    *   a beam's order is its local axis, so reversing it flips the sign of the axial
        force, bending moment and shear that come back out of the run;
    *   a normal load's order is its normal -- the pressure acts along the 90-degree
        rotation of the tangent -- so a reversed segment pushes the wrong way.

    The drawn polyline is the one statement of intent there is, so each segment is
    ordered by how far along it its two ends lie. Measuring along the whole polyline
    rather than per leg is what makes a corner work: the segments either side of it are
    ordered by the same rule, without either needing to know which leg it sits on.
    """
    # Two components for a drawn 2D line, three for a member in space: the path says
    # which, and `world` is always (x, y, z), so the comparison is simply truncated to
    # however many the path carries.
    if len(path) < 2:
        return rows
    span = len(path[0])

    def along(tag: int) -> float:
        point = world[tag][:span]
        best, travelled = None, 0.0
        for start, end in zip(path, path[1:]):
            step = [b - a for a, b in zip(start, end)]
            length = math.sqrt(sum(d * d for d in step))
            if not length:
                continue
            offset = [p - a for p, a in zip(point, start)]
            reach = min(1.0, max(0.0, sum(o * d for o, d in zip(offset, step))
                                 / length ** 2))
            away = math.sqrt(sum((o - d * reach) ** 2 for o, d in zip(offset, step)))
            if best is None or away < best[0]:
                best = (away, travelled + reach * length)
            travelled += length
        return 0.0 if best is None else best[1]
    return [[row[1], row[0], *row[2:]] if along(row[1]) < along(row[0]) else row
            for row in rows]


def _align_conditions(conditions: list[tuple[str, str, list[list[int]]]],
                      soil_blocks: list[tuple[str, str, list[list[int]]]]) -> None:
    """Rewrite each boundary condition onto the element edge it stands on.

    gmsh hands a boundary line out in the direction of the curve it meshed, which is not
    the direction the neighbouring element traverses that same edge; `_oriented` then
    flips elements the mesher gave inside out, moving the edge again. Kratos wants the
    element's order exactly -- see `EDGES` for what it does with anything else.

    A boundary edge on the outside of the model belongs to one element, and there is
    one ordering to take. An edge *inside* it belongs to two, which face each other and
    traverse it in opposite directions -- the floor of an excavation is the case that
    matters, shared between the lift being dug out and the ground that stays. Taking
    whichever was seen first put the water load on the pit floor the wrong way up, so
    where both exist the one already agreeing with the condition is kept. That is the
    direction the line was drawn in (`_drawn_order`), which is the only statement of
    which side of an internal face the load acts on.

    A 3D face is aligned the same way, to the face as its element generates it
    (`FACES`). Kratos *rotates* a face to match, which once read as reason enough to
    leave faces alone -- but it never *reverses* one, and gmsh's boundary triangles came
    out reversed against the tetrahedra often enough that no 3D load had ever loaded.
    """
    edges: dict[frozenset[int], list[tuple[int, ...]]] = {}
    faces: dict[frozenset[int], list[tuple[int, ...]]] = {}
    for _, _, rows in soil_blocks:
        for row in rows:
            for table, into in ((EDGES, edges), (FACES, faces)):
                for order in table.get(len(row), ()):
                    entity = tuple(row[index] for index in order)
                    found = into.setdefault(frozenset(entity), [])
                    if entity not in found:
                        found.append(entity)
    for _, _, rows in conditions:
        for index, row in enumerate(rows):
            key = frozenset(row)
            found = [face for face in faces.get(key, ()) if len(face) == len(row)]
            if found:
                rows[index] = list(next((face for face in found if _rotated(face, row)),
                                        found[0]))
                continue
            found = [edge for edge in edges.get(key, ()) if len(edge) == len(row)]
            if found:
                rows[index] = list(next((edge for edge in found if list(edge) == row),
                                        found[0]))


def _rotated(face: tuple[int, ...], row: list[int]) -> bool:
    """Whether `row` is the triangular `face` rotated: corners and mid-sides turn
    together, the way Kratos compares them."""
    for k in range(3):
        turned = list(face[k:3] + face[:k])
        if len(face) == 6:
            turned += list(face[3 + k:] + face[3:3 + k])
        if turned == row:
            return True
    return False


# ── Naming and numbering ────────────────────────────────────────────────────

def _part_names(project: Project) -> dict[str, str]:
    """Part key -> sub-model part name, unique and safe for a Kratos deck."""
    used = set(RESERVED)
    names: dict[str, str] = {}
    # In body order, not layer order, so a lift is named after the layer it was dug out
    # of: `Upper_Sand`, then `Upper_Sand_lift1`. A staged body has no name of its own in
    # the project -- the user named the layer, not the lift -- so it takes the layer's
    # and says which part of it this is.
    layers = {f"soil_{layer.id}": layer for layer in project.layers}
    for key, *_ in project.soil_bodies():
        stem, _, suffix = key.partition("__")
        layer = layers[stem]
        base = _sanitise(layer.name) or layer.id
        names[key] = _unique(f"{base}_{suffix}" if suffix else base, used)
    for part in project.custom_parts:
        names[part.key] = _unique(_sanitise(part.label) or part.key, used)
    for load in project.loads:
        names[load.id] = _unique(_sanitise(load.name) or load.id, used)
    for beam in project.beams:
        names[beam.id] = _unique(_sanitise(beam.name) or beam.id, used)
    for anchor in project.anchors:
        names[anchor.id] = _unique(_sanitise(anchor.name) or anchor.id, used)
    for interface in project.interfaces:
        names[interface.id] = _unique(_sanitise(interface.name) or interface.id, used)
    for load in project.normal_loads:
        names[load.id] = _unique(_sanitise(load.name) or load.id, used)
    for key in project.part_keys():
        names.setdefault(key, _unique(key, used))
    return names


def deck_name(project: Project) -> str:
    """The stem the deck's files share: `<name>.mdpa`, `<name>_<stage>.post.res`, and
    `model_import_settings.input_filename` inside ProjectParameters.json.

    The project's own name, reduced to what every filesystem accepts -- the same rule
    `frontend/js/export.js` applies when it names the archive, so the file a download writes
    and the file a calculation runs are named alike. Public because two callers need the
    same answer: the export that puts it in the parameters, and `core.run.calculate`, which
    has to write the .mdpa under exactly the name those parameters ask Kratos for.
    """
    return re.sub(r"[^A-Za-z0-9]+", "_", project.name).strip("_") or "model"


def _sanitise(name: str) -> str:
    cleaned = "".join(c if c.isalnum() or c == "_" else "_" for c in name).strip("_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return "" if cleaned[:1].isdigit() else cleaned


def _unique(name: str, used: set[str]) -> str:
    candidate, suffix = name, 2
    while candidate in used:
        candidate, suffix = f"{name}_{suffix}", suffix + 1
    used.add(candidate)
    return candidate


def _number_elements(blocks: list[tuple[str, str, list[list[int]]]],
                     names: dict[str, str], node_id: dict[int, int]
                     ) -> tuple[list[tuple[str, list[tuple[int, int, list[int]]]]],
                                list[tuple[str, list[int], list[int], list[int]]]]:
    """Assign element ids in emission order and collect one sub-model part per body."""
    numbered = []
    parts: dict[str, tuple[list[int], list[int]]] = {}
    next_id = 1
    for key, class_name, rows in blocks:
        entries = []
        for row in rows:
            entries.append((next_id, 0, [node_id[tag] for tag in row]))
            next_id += 1
        numbered.append((class_name, entries))
        nodes, elements = parts.setdefault(names[key], ([], []))
        elements.extend(element_id for element_id, _, _ in entries)
        nodes.extend(n for _, _, connectivity in entries for n in connectivity)
    ordered = [(name, sorted(set(nodes)), sorted(elements), [])
               for name, (nodes, elements) in parts.items()]
    return numbered, ordered


def _number_conditions(
    conditions: list[tuple[str, str, list[list[int]]]],
    names: dict[str, str],
    node_id: dict[int, int],
) -> tuple[list[tuple[str, list[tuple[int, int, list[int]]]]],
           list[tuple[str, list[int], list[int], list[int]]]]:
    """Assign condition ids in emission order, in their own id space starting at 1.

    Property 0, always: a load's magnitude is not read off a Properties block (see
    `_load_variable`), and every reference GeoMechanics deck writes 0 here
    for exactly this condition class.
    """
    numbered = []
    parts = []
    next_id = 1
    for key, class_name, rows in conditions:
        entries = []
        nodes: set[int] = set()
        ids: list[int] = []
        for row in rows:
            connectivity = [node_id[tag] for tag in row]
            entries.append((next_id, 0, connectivity))
            nodes.update(connectivity)
            ids.append(next_id)
            next_id += 1
        numbered.append((class_name, entries))
        if ids:
            parts.append((names[key], sorted(nodes), [], ids))
    return numbered, parts


def _boundary_nodes(project: Project, dim: int,
                    world: dict[int, tuple[float, float, float]],
                    node_id: dict[int, int],
                    body_tags: set[int] | None = None,
                    ) -> list[tuple[str, int, list[int]]]:
    """(name, world axis, node ids) for every domain-face boundary present in this
    dimension. Shared by the .mdpa sub-model parts and the derived boundary
    constraints below, so both agree on exactly which boundaries exist.

    The faces are measured from the meshed soil, not from `project.domain`: a drawn or
    imported soil body is not held to the borehole box, so a domain plane it does not
    reach yields an empty group and the deck silently loses `Right_Edge` or
    `Bottom_Fixed`. Where the soil does fill the domain the two agree exactly.
    Structures are excluded from the measurement -- a sheet pile standing proud of the
    ground must not become the whole `Top_Surface` -- but any node lying on a face,
    structural or not, joins the group.

    A 2D section has no boundary along its normal axis, which is always z, so
    `Front_Edge` and `Back_Edge` are simply not written -- an empty one would read as
    a modelling mistake.
    """
    skipped = 2 if dim == 2 else None
    measured = [xyz for tag, xyz in world.items()
                if tag in node_id and (body_tags is None or tag in body_tags)]
    if not measured:
        measured = [xyz for tag, xyz in world.items() if tag in node_id]
    out = []
    for name, axis, attribute in BOUNDARIES:
        if axis == skipped or not measured:
            continue
        values = [xyz[axis] for xyz in measured]
        plane = min(values) if attribute in LOWER_FACES else max(values)
        nodes = sorted(node_id[tag] for tag, xyz in world.items()
                       if tag in node_id and abs(xyz[axis] - plane) <= TOLERANCE)
        if nodes:
            out.append((name, axis, nodes))
    return out


def _boundary_parts(boundaries: list[tuple[str, int, list[int]]]
                    ) -> list[tuple[str, list[int], list[int], list[int]]]:
    """Named node groups on the domain faces, as `.mdpa` sub-model parts."""
    return [(name, nodes, [], []) for name, _, nodes in boundaries]


def _segment_boundaries(project: Project, boundaries: list[tuple[str, int, list[int]]],
                        body_nodes: dict[str, set[int]], names: dict[str, str],
                        ) -> tuple[list[tuple[str, int, list[int]]], dict[str, str]]:
    """Split a domain face wherever an excavation lift meets it.

    A lift is deactivated in its own phase, and its stretch of the domain edge has to
    go with it: a roller still holding the ground that was just dug away would restrain
    soil that is no longer there. So the face the pit reaches becomes one part per lift
    -- the reference deck's `Excavated_Soil_N_Left_Edge` -- plus what is left, which
    keeps the face's own name and holds the ground that is never dug.

    Only where it is needed. A face no lift touches (the far side, the bottom) never
    loses a body, so splitting it would buy nothing and add parts to every process list
    that names it. `Top_Surface` is skipped even where a lift does reach it: it is the
    free surface and is never constrained (`_boundary_constraints`), so segmenting it
    would produce parts nothing reads.

    Segments overlap by one node at each seam, and deliberately: the node between two
    lifts belongs to both, and the node at the final floor belongs to the last lift
    *and* to the ground below it. Whichever of the two is deactivated, the other still
    names that node and still holds it.

    Returns the boundaries and, beside them, which soil body each new segment belongs
    to. A constraint on a segment has to vanish in the stage its lift is dug out in
    (plan sec C3), and reading that back off the part's name afterwards would be a
    second, weaker copy of the naming rule below.
    """
    lifts = [key for key, _, _, inside in project.soil_bodies()
             if inside and "__lift" in key]
    if not lifts:
        return boundaries, {}

    # Nodes that exist only in lifts. Subtracting these rather than all lift nodes is
    # what leaves the seams in the remainder -- and it leaves structural nodes lying on
    # the face alone, which belong to no soil body at all.
    permanent = set().union(*(nodes for key, nodes in body_nodes.items()
                              if key not in lifts)) if body_nodes else set()
    exclusive = set().union(*(body_nodes.get(key, set()) for key in lifts)) - permanent

    out: list[tuple[str, int, list[int]]] = []
    owners: dict[str, str] = {}
    for name, axis, nodes in boundaries:
        touching = [key for key in lifts
                    if body_nodes.get(key, set()) & set(nodes)] if name != "Top_Surface" \
            else []
        if not touching:
            out.append((name, axis, nodes))
            continue
        for key in touching:
            segment = sorted(set(nodes) & body_nodes[key])
            out.append((f"{names[key]}_{name}", axis, segment))
            owners[f"{names[key]}_{name}"] = key
        out.append((name, axis, [n for n in nodes if n not in exclusive]))
    return out, owners





def _boundary_constraints(project: Project, dim: int,
                          boundaries: list[tuple[str, int, list[int]]]
                          ) -> list[tuple[str, list[bool]]]:
    """DISPLACEMENT fixities for a box domain: pinned at the bottom, rollers on the
    sides. `Top_Surface` is deliberately excluded -- it is the free or loaded surface,
    never a fixed one.
    """
    ndof = [True, True, dim == 3]
    out = []
    for name, axis, _ in boundaries:
        if name == "Top_Surface":
            continue
        if name == "Bottom_Fixed":
            out.append((name, list(ndof)))
            continue
        # Kratos coordinates are world coordinates in both dimensions, so the world
        # axis is the vector index. In 2D the only axis this never sees is z, which
        # `_boundary_nodes` has already dropped.
        is_fixed = [False, False, False]
        is_fixed[axis] = True
        out.append((name, is_fixed))
    return out


def _part_materials(project: Project, names: dict[str, str],
                    blocks: list[tuple[str, str, list[list[int]]]]) -> list[tuple[str, str]]:
    """(sub-model part name, material id) for every exported body that has a material."""
    # Keyed by body, not by layer: a lift is still the layer it was dug out of, so
    # `soil_L1__lift1` has to find `soil_L1`'s material or the deck exports a body with
    # no material at all.
    material_of = {f"soil_{layer.id}": layer.mat for layer in project.layers}
    material_of.update({key: material_of[key.partition("__")[0]]
                        for key, *_ in project.soil_bodies()})
    material_of.update({p.key: p.mat for p in project.custom_parts if p.mat})
    seen: list[tuple[str, str]] = []
    for key, _, _ in blocks:
        entry = (names[key], material_of.get(key))
        if entry[1] and entry not in seen:
            seen.append(entry)
    return seen


def _element_labels(coordinates: dict[int, tuple[float, float, float]],
                    node_id: dict[int, int],
                    elements: list[tuple[str, list[tuple[int, int, list[int]]]]]
                    ) -> list[list[float]]:
    """`[element id, x, y, z]` per element, the point being its centroid.

    The mean of *all* the element's nodes, not just its corners: for the simplices this
    exporter writes the two agree exactly, because a quadratic element's extra nodes are
    edge midpoints and the mean of the midpoints of a simplex's edges is its centroid.
    So an element's label needs no knowledge of its order to be placed in the middle of
    it.
    """
    placed = {index: coordinates[tag] for tag, index in node_id.items()}
    labels: list[list[float]] = []
    for _class_name, entries in elements:
        for entry_id, _property_id, connectivity in entries:
            corners = [placed[node] for node in connectivity]
            count = len(corners)
            labels.append([entry_id] + [sum(corner[axis] for corner in corners) / count
                                        for axis in range(3)])
    labels.sort(key=lambda row: row[0])
    return labels


# ── Rendering ───────────────────────────────────────────────────────────────

LINE_END = "\r\n"


def _render(coordinates: dict[int, tuple[float, float, float]], node_id: dict[int, int],
            elements: list[tuple[str, list[tuple[int, int, list[int]]]]],
            conditions: list[tuple[str, list[tuple[int, int, list[int]]]]],
            parts: list[tuple[str, list[int], list[int], list[int]]]) -> str:
    """Lay the deck out the way GiD does, so the two diff against each other."""
    lines = ["Begin Properties 0", "End Properties", ""]

    lines.append("Begin Nodes")
    for tag, index in sorted(node_id.items(), key=lambda item: item[1]):
        x, y, z = coordinates[tag]
        lines.append(f"{index:5d}{x:15.10f}{y:15.10f}{z:15.10f}")
    lines += ["End Nodes", ""]

    for keyword, blocks in (("Elements", elements), ("Conditions", conditions)):
        for class_name, entries in blocks:
            lines.append(f"Begin {keyword} {class_name}")
            for entry_id, property_id, connectivity in entries:
                nodes = "".join(f"{n:6d}" for n in connectivity)
                lines.append(f"{entry_id:9d}{property_id:11d}{nodes} ")
            lines += [f"End {keyword}", ""]

    for name, nodes, part_elements, part_conditions in parts:
        lines.append(f"Begin SubModelPart {name}")
        for keyword, values in (("Nodes", nodes), ("Elements", part_elements),
                                ("Conditions", part_conditions)):
            if not values:
                continue
            lines.append(f"    Begin SubModelPart{keyword}")
            lines += [f"{value:13d}" for value in values]
            lines.append(f"    End SubModelPart{keyword}")
        lines += ["End SubModelPart", ""]

    return LINE_END.join(lines)
