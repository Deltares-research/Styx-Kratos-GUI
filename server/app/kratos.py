"""Export the meshed model as a Kratos MultiPhysics `.mdpa` input deck.

The target is the file GiD writes for a Kratos GeoMechanics analysis: an empty
`Properties 0` block, one global node table, one `Elements` block per material body,
optional `Conditions` for the surface load, and one `SubModelPart` per body whose node
list is exactly the union of its elements' nodes.

One thing the deck does that the mesh does not: an interface. Where the project asks for
one, `app.interfaces` splits the meshed soil off the structure it was built conformal to
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

import gmsh

from app import build, interfaces, meshing
from app import kratos_processes
from app.kratos_materials import material_parameters
from app.schemas import (Beam, LineLoad, MeshRequest, PanelSection, PointLoad,
                         Project, SurfaceLoad)

# (dim, gmsh element type) -> (Kratos class, gmsh index order in Kratos' order)
ELEMENTS: dict[tuple[int, int], tuple[str, tuple[int, ...]]] = {
    (2, 2): ("UPwSmallStrainElement2D3N", (0, 1, 2)),
    (2, 9): ("SmallStrainUPwDiffOrderElement2D6N", (0, 1, 2, 3, 4, 5)),
    (3, 4): ("UPwSmallStrainElement3D4N", (0, 1, 2, 3)),
    (3, 11): ("SmallStrainUPwDiffOrderElement3D10N", (0, 1, 2, 3, 4, 5, 6, 7, 9, 8)),
}

# Sheet piles: 1D structural elements living inside the 2D section, sharing its nodes.
# Both 2D classes and their (end, end, midside) connectivity are read off the reference
# decks -- examples/dike_with_sheet_pile.mdpa writes the linear one,
# examples/crow_case.mdpa the quadratic one -- so the gmsh order maps straight through.
#
# The 3D entries are the members: bored piles, king posts and struts. NOT CONFIRMED by
# any deck in examples/ -- every one of them is plane strain -- so these follow Kratos
# StructuralMechanicsApplication's naming rather than a fixture here, exactly as the
# constitutive laws in app/kratos_materials.py already do. Check them against the first
# real 3D run; they are named here, in one place, so that is a one-line change.
BEAMS: dict[tuple[int, int], tuple[str, tuple[int, ...]]] = {
    (2, 1): ("LinearTimoshenkoCurvedBeamElement2D2N", (0, 1)),
    (2, 8): ("LinearTimoshenkoCurvedBeamElement2D3N", (0, 1, 2)),
    (3, 1): ("LinearTimoshenkoBeamElement3D2N", (0, 1)),
    (3, 8): ("LinearTimoshenkoBeamElement3D3N", (0, 1, 2)),
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
# the quadratic class is pinned by a fixture: examples/crow_case.mdpa writes
# `Geo_UPwLineInterfacePlaneStrainDiffOrderElement3Plus3N` with six nodes -- three from
# the sheet pile, then their three coincident copies on one face of the soil -- and one
# element per pile segment per face, the two faces carrying opposite node orders.
#
# The linear name below follows the same convention with the DiffOrder infix dropped, as
# the beam and soil classes do between orders, but no deck in examples/ contains it.
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
"""The anchor tie, per model dimension. The 2D name is read off examples/crow_case.mdpa;
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
# test_create_interfaces.py for the linear class, examples/crow_config.json for the
# quadratic one).
NORMAL_LOAD_CONDITIONS: dict[tuple[int, int], str] = {
    (2, 2): "LineNormalLoadCondition2D2N",
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


def export_project(project: Project, settings: MeshRequest,
                   include_materials: bool = True) -> dict:
    """Mesh the project and render it as a Kratos deck.

    Returns `{"mdpa", "nodes", "materials", "stats", "meshed_keys", "warnings", "log"}`, all
    JSON-safe, so it can cross the gmsh worker's process boundary unchanged.
    `materials` is None when the companion MaterialParameters.json is not wanted.
    """
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
    # Seeded from `mesh.log`'s own curated notes -- every `app.build` line meant for a
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
    blocks.extend(beam_blocks)
    # Nor are the wall shells: a sheet of steel has two faces and no "inside out", so
    # there is no signed area to correct -- only a normal, which is the wall's own.
    panel_blocks = _harvest(_panel_bodies(project, dim), 2, SHELLS, model_dim=dim)
    blocks.extend(panel_blocks)
    anchor_blocks, anchor_supports = _anchor_ties(project, dim, _world_coordinates())
    blocks.extend(anchor_blocks)
    conditions = (_load_conditions(project, dim, world, warnings) +
                 _normal_load_conditions(project, dim, warnings))
    # Last, because it rewrites what everything above produced: the interface unglues
    # the soil from the structures already harvested, so it needs their connectivity in
    # hand -- and the nodes it adds have to be in `world` before the boundary groups and
    # the node table are read off it.
    interface_blocks, interface_ties = _interface_elements(
        project, dim, soil_blocks, beam_blocks, conditions, world, coordinates, warnings)
    blocks.extend(interface_blocks)
    # After the interface split, so each condition is aligned to the copy of the soil it
    # ended up on rather than to the element it left behind.
    _align_conditions(conditions, soil_blocks)

    used = sorted({tag for _, _, rows in blocks for row in rows for tag in row}
                  | {tag for _, _, rows in conditions for row in rows for tag in row})
    node_id = {tag: index for index, tag in enumerate(used, start=1)}

    part_materials = _part_materials(project, names, blocks)
    numbered, parts = _number_elements(blocks, names, node_id)
    condition_blocks, load_parts = _number_conditions(conditions, names, node_id)
    body_tags = {tag for _, _, rows in soil_blocks for row in rows for tag in row}
    boundaries = _boundary_nodes(project, dim, world, node_id, body_tags)
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

    condition_keys = {key for key, _, rows in conditions if rows}
    active_loads = [(names[load.id], *_load_variable(load, dim))
                    for load in project.loads if load.id in condition_keys]
    normal_load_processes = [
        (names[load.id], load.fluid_pressure_type, load.pressure,
         project.water.y, project.water.specific_weight)
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
    interface_properties = [(names[key], project.interface_section(
                                 _interface_of(project, key).section))
                            for key, _, _ in interface_blocks]
    materials, material_warnings = (
        material_parameters(project, part_materials, dim, beam_properties,
                            anchor_properties, panel_properties, interface_properties)
        if include_materials else (None, [])
    )
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
    processes = kratos_processes.project_parameters(
        _boundary_constraints(project, dim, boundaries) + anchor_fixities,
        [(name, variable, load_mask, value) for name, variable, value in active_loads],
        wall_parts,
        staged_ties,
        normal_load_processes,
    )
    return {
        "mdpa": _render(coordinates, node_id, numbered, condition_blocks, parts),
        # The node table on its own, in the deck's own numbering. The viewport's node-ID
        # labels can only be drawn from here: a gmsh tag is not a Kratos ID -- `node_id`
        # above renumbers 1..N over the tags the blocks actually use, and the interface
        # split has already added nodes of its own -- so nothing short of this pass knows
        # what number a node will carry in the file.
        "nodes": [[index, *coordinates[tag]]
                  for tag, index in sorted(node_id.items(), key=lambda item: item[1])],
        "materials": materials,
        "project_parameters": processes,
        "stats": mesh.stats.to_dict(),
        "meshed_keys": mesh.meshed_keys,
        "warnings": warnings,
        "log": mesh.log,
    }




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

    The topology is `app.interfaces`' job and is done on connectivity alone; what
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
    _follow_the_soil(conditions, before, split)

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
        out.append((interface.id, name, rows))
        if interface.structure is not None:
            master, slave = _split_ties(rows, per_side, split.duplicates)
            if master and slave:
                ties.append((interface.id, master, slave))
    return out, ties


def _split_ties(rows: list[list[int]], per_side: int, duplicates: dict[int, int]
                ) -> tuple[list[int], list[int]]:
    """Pair up the soil-side copies of every node the interface split into two.

    A node in the middle of the line gets exactly two copies, one per face (see
    `app.interfaces`'s module docstring) -- while the structure that owns the line is
    staged (deactivated, then activated on installation -- see `kratos_processes`),
    nothing else holds those two copies together, so they need a master/slave tie for
    the stage(s) before installation. A node with only one copy is the toe, where the
    ground closes under the structure and is already continuous; it needs no tie.

    `minimum_number_of_neighbouring_nodes` in `kratos_processes._master_slave_constraint`
    is deliberately 1, not the 2 a generic nearest-neighbour tie would ask for: the
    pairing here is exact, not discovered by search, so each node in one list has
    exactly one true partner, at zero distance, in the other.
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
                     before: list[list[int]], split: interfaces.Split) -> None:
    """Move every condition standing on a split node onto the copy its own soil got.

    A condition is a face of one continuum element, so the element that contained all of
    its nodes before the split is the body it belongs to, and it is renamed exactly as
    that element was.
    """
    sources = set(split.duplicates.values())
    for _, _, rows in conditions:
        for index, row in enumerate(rows):
            if not sources.intersection(row):
                continue
            owner = next((i for i, element in enumerate(before)
                          if set(row) <= set(element)), None)
            if owner is None:
                continue
            rows[index] = [split.renamed[owner].get(node, node) for node in row]


def _interface_of(project: Project, key: str):
    return next(interface for interface in project.interfaces if interface.id == key)

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
    return PanelSection(id=beam.id, name=beam.name, E=beam.E, nu=beam.nu,
                        thickness=beam.area, density=beam.density)


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
            "quadratic simplices, or add the type to app/kratos.py."
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
    """Boundary elements on the ground surface that lie under the load pad.

    Selected element by element rather than entity by entity: the pad is a display
    indicator that never cuts the soil, so the loaded region is not a separate part.

    `build._imprint_load_footprints` has split the boundary exactly at the footprint
    edges, so every element is wholly inside or wholly outside it and the test below is
    an exact containment test. Without that imprint the only available rule would be
    whether an element's centre lies under the pad, which moves a loaded edge by as
    much as one element.
    """
    out: list[tuple[str, str, list[list[int]]]] = []
    # `loads_for` rather than a kind test: a translated pair holds a surface record and
    # a line record for one load, and writing both would apply it twice. What it hands
    # back for a 3D model is the surface loads plus the 2D ones nothing was translated
    # from -- see the CONDITIONS table for which of those can actually be written.
    for load in project.loads_for(dim):
        if not load.active:
            continue
        if dim == 3 and load.kind == "line":
            # A line load imprints a *curve* on the solid's boundary, and the boundary
            # elements harvested below are faces. CONDITIONS has no 3D line class to
            # write it with, and inventing one with no reference deck behind it would
            # be a guess in the deck rather than in a comment. Said out loud instead:
            # the load is drawn and meshed, but it is not applied.
            if warnings is not None:
                warnings.append(
                    f"{load.name!r} is a line load, which has no Kratos condition in a "
                    "3D deck; it is drawn at the section plane but applies no force. "
                    "Move it to the ground surface so it translates to a surface load, "
                    "or apply it in the 2D section."
                )
            continue
        if load.kind == "point":
            target = ((load.x, load.y, 0.0) if dim == 2
                      else (load.x, load.y, project.cut_at()))
            nearest = min(
                world,
                key=lambda tag: sum((world[tag][axis] - target[axis]) ** 2 for axis in range(3)),
            )
            out.append((load.id, f"PointLoadCondition{dim}D1N", [[nearest]]))
            continue
        elevation = project.elevation_of(load)
        rows_by_class: dict[str, list[list[int]]] = {}
        for _, entity in gmsh.model.getEntities(dim - 1):
            box = gmsh.model.getBoundingBox(dim - 1, entity)
            if abs(box[1] - elevation) > TOLERANCE or abs(box[4] - elevation) > TOLERANCE:
                continue
            types, _, connectivity = gmsh.model.mesh.getElements(dim - 1, entity)
            for element_type, flat in zip(types, connectivity):
                name, order = _lookup(CONDITIONS, dim, int(element_type))
                for offset in range(0, len(flat), len(order)):
                    row = [int(flat[offset + i]) for i in order]
                    if _under_load(row[:dim], world, load):
                        rows_by_class.setdefault(name, []).append(row)
        out.extend((load.id, name, rows) for name, rows in rows_by_class.items() if rows)
    return out


def _normal_load_conditions(project: Project, dim: int, warnings: list[str]
                            ) -> list[tuple[str, str, list[list[int]]]]:
    """One condition per active `NormalLoad`, off the line `build._embed_beams` already
    gave its own physical group -- the same way a free interface's line is found.

    Unlike `_load_conditions`, this does not scan the boundary at a fixed elevation: a
    normal load can run down a vertical face, which has no single elevation to scan
    for, so it is read straight off the mesh instead.
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
        out.append((load.id, name, rows))
    return out


def _align_conditions(conditions: list[tuple[str, str, list[list[int]]]],
                      soil_blocks: list[tuple[str, str, list[list[int]]]]) -> None:
    """Rewrite each boundary condition onto the element edge it stands on.

    gmsh hands a boundary line out in the direction of the curve it meshed, which is not
    the direction the neighbouring element traverses that same edge; `_oriented` then
    flips elements the mesher gave inside out, moving the edge again. Kratos wants the
    element's order exactly -- see `EDGES` for what it does with anything else.

    A boundary edge belongs to one element, so the first ordering found for a set of
    nodes is the only one a condition can sit on. 3D faces are left alone: Kratos rotates
    those itself, and only the continuum blocks are offered here in any case.
    """
    edges: dict[frozenset[int], tuple[int, ...]] = {}
    for _, _, rows in soil_blocks:
        for row in rows:
            for order in EDGES.get(len(row), ()):
                edge = tuple(row[index] for index in order)
                edges.setdefault(frozenset(edge), edge)
    for _, _, rows in conditions:
        for index, row in enumerate(rows):
            edge = edges.get(frozenset(row))
            if edge is not None and len(edge) == len(row):
                rows[index] = list(edge)


def _under_load(corners: list[int], world: dict[int, tuple[float, float, float]],
                load) -> bool:
    """Every corner inside the footprint, within the tolerance the imprint holds to."""
    def inside(value: float, low: float, high: float) -> bool:
        return low - TOLERANCE <= value <= high + TOLERANCE

    if load.kind == "line":
        return all(inside(world[tag][0], load.x0, load.x1) for tag in corners)
    return all(inside(world[tag][0], load.x0, load.x1)
               and inside(world[tag][2], load.z0, load.z1) for tag in corners)


# ── Naming and numbering ────────────────────────────────────────────────────

def _part_names(project: Project) -> dict[str, str]:
    """Part key -> sub-model part name, unique and safe for a Kratos deck."""
    used = set(RESERVED)
    names: dict[str, str] = {}
    for layer in project.layers:
        names[f"soil_{layer.id}"] = _unique(_sanitise(layer.name) or layer.id, used)
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
    `_load_variable`), and every reference GeoMechanics deck in examples/ writes 0 here
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
    material_of = {f"soil_{layer.id}": layer.mat for layer in project.layers}
    material_of.update({p.key: p.mat for p in project.custom_parts if p.mat})
    seen: list[tuple[str, str]] = []
    for key, _, _ in blocks:
        entry = (names[key], material_of.get(key))
        if entry[1] and entry not in seen:
            seen.append(entry)
    return seen


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
