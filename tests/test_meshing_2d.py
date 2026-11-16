"""Plane-strain meshing: triangles on the section face, not tetrahedra in a solid.

Everything gmsh needs told differently in 2D is asserted here, because each one fails
quietly rather than loudly: `generate(2)` instead of `generate(3)`, `Mesh.Algorithm`
instead of `Mesh.Algorithm3D`, and a `Restrict` field driven by `SurfacesList` rather
than `VolumesList` -- that last one simply has no effect if left as it was, so a
per-layer size would be silently ignored and every element would come out the same size.
"""

from types import SimpleNamespace

import pytest

from core.geometry import solid_model, meshing
from core.model.schemas import BoxRefinement, Project
from core.model.templates import seed_project


def section_project(simple: bool = True, **extra) -> Project:
    return Project.model_validate(
        seed_project(simple=simple).model_dump() | {"dimension": 2} | extra
    )


@pytest.fixture(scope="module")
def quadratic():
    project = section_project()
    with solid_model.session():
        yield project, meshing.mesh_project(project, element_size=2.0, order=2)


def test_real_surface_elements_are_generated(quadratic):
    _, mesh = quadratic
    assert mesh.stats.elements > 0
    assert mesh.stats.nodes > 0


def test_the_mesh_is_triangles_and_nothing_solid(quadratic):
    import gmsh

    triangle = gmsh.model.mesh.getElementType("Triangle", 2)
    types, elements, nodes = gmsh.model.mesh.getElements(2)
    by_type = {int(t): (e, n) for t, e, n in zip(types, elements, nodes)}
    assert set(by_type) == {triangle}

    # Order 2 in 2D is the six-node triangle, not the ten-node tetrahedron.
    element_tags, node_tags = by_type[triangle]
    assert len(node_tags) == len(element_tags) * 6

    solid_elements = sum(len(tags) for tags in gmsh.model.mesh.getElements(3)[1])
    assert solid_elements == 0, "a plane-strain model has no volume elements"


def test_stats_are_internally_consistent(quadratic):
    stats = quadratic[1].stats
    assert sum(stats.by_type.values()) == stats.elements
    assert sum(stats.quality_histogram.values()) == stats.elements
    assert stats.quality_histogram["<0.0"] == 0, "inverted triangles are not a usable mesh"


def test_the_average_element_size_is_near_the_size_asked_for(quadratic):
    """The Selection explorer of the mesh shows it: the mean edge length of the
    elements, which gmsh aims at the element size (2 m here) where nothing refines."""
    stats = quadratic[1].stats
    assert 0.5 < stats.average_size < 2.5
    assert stats.to_dict()["average_size"] == stats.average_size


def test_every_node_lies_on_the_section_plane(quadratic):
    """Which is z = 0: the cut is taken at `section_offset` and moved onto the x-y
    plane, so the mesh has no third coordinate to speak of."""
    import gmsh

    _, mesh = quadratic
    _, coordinates, _ = gmsh.model.mesh.getNodes()
    for z in coordinates[2::3]:
        assert z == pytest.approx(0.0, abs=1e-6)


def test_the_payload_is_drawable_and_finite(quadratic):
    _, mesh = quadratic
    assert mesh.sections
    for section in mesh.sections:
        assert section.key == "mesh"
        assert section.indices and len(section.indices) % 3 == 0
        assert max(section.indices) < len(section.positions) // 3
        assert len(section.edges) % 6 == 0


def test_a_finer_body_size_actually_refines_that_body():
    """The Restrict field must be given SurfacesList in 2D. Left as VolumesList it
    matches nothing, gmsh reports no error, and the size is silently ignored."""
    project = section_project()
    coarse_key = f"soil_{project.layers[0].id}"
    with solid_model.session():
        coarse = meshing.mesh_project(project, element_size=4.0, order=1)
        fine = meshing.mesh_project(project, element_size=4.0, order=1,
                                    body_sizes={coarse_key: 1.0})
    assert fine.stats.elements > coarse.stats.elements * 1.5


def test_a_local_refinement_box_still_applies():
    project = section_project()
    d = project.domain
    box = BoxRefinement(kind="box", size=0.8,
                        x_min=d.x0, x_max=d.x1 / 2,
                        z_min=d.z0 - 1, z_max=d.z1 + 1,
                        y_min=d.y_bottom, y_max=d.y_top)
    with solid_model.session():
        plain = meshing.mesh_project(project, element_size=4.0, order=1)
        refined = meshing.mesh_project(project, element_size=4.0, order=1, refinements=[box])
    assert refined.stats.elements > plain.stats.elements


def test_meshing_reports_which_keys_it_meshed():
    project = section_project()
    with solid_model.session():
        mesh = meshing.mesh_project(project, element_size=4.0, order=1)
    assert set(mesh.meshed_keys) <= set(project.part_keys())
    assert mesh.meshed_keys


# ── Mixed-dimensional meshing: 2D soil with 1D sheet piles ──────────────────

def piled_section(points=((12.0, 0.0), (12.0, -14.0))) -> Project:
    payload = section_project().model_dump()
    payload["beam_sections"] = [{"id": "az26", "name": "AZ 26-700", "E": 2.1e8,
                                 "nu": 0.3, "area": 0.0198, "inertia": 5.52e-4,
                                 "density": 7850.0, "spacing": 1.0}]
    payload["beams"] = [{"id": "sheetpile_1", "name": "Sheet pile 1", "section": "az26",
                         "points": [list(p) for p in points], "active": True}]
    return Project.model_validate(payload)


def beam_mesh(project: Project, order: int = 2) -> tuple[list[int], set[int], set[int]]:
    """(line element types, beam node ids, soil node ids) after a real mesh run."""
    import gmsh
    meshing.mesh_project(project, element_size=3.0, order=order)
    types, beam_nodes, soil_nodes = [], set(), set()
    for dim, group in gmsh.model.getPhysicalGroups():
        name = gmsh.model.getPhysicalName(dim, group)
        for entity in gmsh.model.getEntitiesForPhysicalGroup(dim, group):
            kinds, _, connectivity = gmsh.model.mesh.getElements(dim, entity)
            for kind, nodes in zip(kinds, connectivity):
                if name.startswith("soil_"):
                    soil_nodes.update(int(n) for n in nodes)
                elif name == "sheetpile_1":
                    types.append(int(kind))
                    beam_nodes.update(int(n) for n in nodes)
    return types, beam_nodes, soil_nodes


def test_a_sheet_pile_is_meshed_as_line_elements_beside_the_soil_triangles():
    with solid_model.session():
        types, beam_nodes, _ = beam_mesh(piled_section())

    assert beam_nodes, "the pile has to reach the mesh, not just the geometry"
    assert set(types) == {8}, "gmsh type 8 is the 3-node line, the quadratic beam"


def test_a_first_order_run_meshes_the_pile_as_two_node_lines():
    with solid_model.session():
        types, _, _ = beam_mesh(piled_section(), order=1)

    assert set(types) == {1}, "gmsh type 1 is the 2-node line"


def test_every_sheet_pile_node_is_also_a_soil_node():
    """Conformity is the whole point of embedding the curve, and it is what the
    Kratos decks show: in a sheet-pile deck every one of the sheet pile's nodes
    belongs to the soil mesh too."""
    with solid_model.session():
        _, beam_nodes, soil_nodes = beam_mesh(piled_section())

    assert beam_nodes - soil_nodes == set()


def test_a_pile_crossing_a_layer_boundary_still_shares_its_nodes():
    with solid_model.session():
        _, beam_nodes, soil_nodes = beam_mesh(
            piled_section(points=((12.0, 0.0), (12.0, -7.0), (15.0, -12.0)))
        )

    assert len(beam_nodes) > 2
    assert beam_nodes - soil_nodes == set()


# ── Anchors: a tie hanging off a pile, detached from the soil ───────────────

TENDON = {"id": "strand", "name": "4-strand tendon", "E": 1.95e8, "area": 0.0006,
          "density": 7850.0, "spacing": 2.5, "tension_limit": 900.0,
          "compression_limit": None}


def anchored_section(head=(12.0, -2.0), tail=(20.0, -8.0)) -> Project:
    payload = piled_section().model_dump()
    payload["anchor_sections"] = [TENDON]
    payload["anchors"] = [{"id": "anchor_1", "name": "Anchor 1", "kind": "anchor",
                           "section": "strand", "head": list(head), "tail": list(tail),
                           "prestress": 250.0, "active": True}]
    return Project.model_validate(payload)


def mesh_nodes_at(x: float, y: float, tol: float = 1e-6) -> list[int]:
    import gmsh
    tags, coords, _ = gmsh.model.mesh.getNodes()
    return [int(t) for i, t in enumerate(tags)
            if abs(coords[3 * i] - x) < tol and abs(coords[3 * i + 1] - y) < tol]


def test_the_anchor_head_is_a_node_the_sheet_pile_owns():
    """Splitting the pile at the head is what makes the tie land on a real beam node."""
    with solid_model.session():
        _, beam_nodes, soil_nodes = beam_mesh(anchored_section())
        at_head = mesh_nodes_at(12.0, -2.0)

    assert [n for n in at_head if n in beam_nodes], "no beam node sits at the head"
    assert beam_nodes - soil_nodes == set(), "the pile stays bonded to the soil"


def test_an_anchor_does_not_cost_the_pile_its_conformity():
    """The pile must keep every node it had before an anchor was hung off it."""
    with solid_model.session():
        _, plain_nodes, _ = beam_mesh(piled_section())
        _, anchored_nodes, _ = beam_mesh(anchored_section())

    assert len(anchored_nodes) >= len(plain_nodes)


def test_the_anchor_tail_gets_exactly_one_node_belonging_to_nothing_else():
    """The reference deck's tail node is in no element at all: the grouted body is
    idealised as a fixed point, not bonded to the soil."""
    import gmsh
    with solid_model.session():
        meshing.mesh_project(anchored_section(), element_size=3.0, order=2)
        at_tail = mesh_nodes_at(20.0, -8.0)
        used = set()
        for dim, group in gmsh.model.getPhysicalGroups():
            if gmsh.model.getPhysicalName(dim, group).endswith("_Support"):
                continue
            for entity in gmsh.model.getEntitiesForPhysicalGroup(dim, group):
                for connectivity in gmsh.model.mesh.getElements(dim, entity)[2]:
                    used.update(int(n) for n in connectivity)

    assert len(at_tail) == 1
    assert at_tail[0] not in used, "the tail must not be bonded to soil, pile or anything"


# ── Per-structure element size ──────────────────────────────────────────────
# `MeshSettings.body_sizes` is keyed by part key, and a beam, an anchor and an interface
# all have one -- so a size could always be *asked* for a structure. It was read out of
# `BuildResult.volumes`, which holds nothing for a structure (they are curves, and live
# in `.curves`), so the request was accepted by the schema and then silently dropped:
# the wall came out at whatever size the soil around it happened to be.
#
# The reference deck meshes its wall at 1 m inside soil at 2 m, which is the ordinary
# thing to want: the wall is where the bending moments are read.


def excavation_like():
    from tests.models import excavation
    return excavation.excavation_project(staged=False)


def excavation_deck(**sizes):
    """The test model exported with the given per-part sizes, parsed back."""
    from core.kratos import writer
    from tests.models import excavation
    from core.model.schemas import MeshRequest
    from tests import mdpa
    project = excavation.excavation_project(staged=False)
    base = {f"soil_{layer.id}": 2.0 for layer in project.layers}
    with solid_model.session():
        exported = writer.export_project(
            project, MeshRequest(element_size=8.0, order=2,
                                 body_sizes=base | sizes))
    return mdpa.parse(exported["mdpa"])


def wall_elements(deck) -> int:
    return sum(len(b.entries) for b in deck.elements
               if b.name == "LinearTimoshenkoCurvedBeamElement2D3N")


def test_a_size_asked_for_a_structure_reaches_the_mesh():
    """Coarse wall, fine wall, same soil: the wall's own size is what changes it."""
    coarse = wall_elements(excavation_deck())
    fine = wall_elements(excavation_deck(sheetpile=0.5))
    assert fine > coarse * 2, (coarse, fine)


def test_a_structure_s_size_holds_when_the_layers_to_mesh_are_named():
    """A request may name the layers it meshes (`volume_keys`). The wall is in none of
    them, and its size was once dropped with it: the sheet-pile size did nothing when
    the layers were named, though a request that named none honoured it."""
    project = excavation_like()
    layers = [f"soil_{layer.id}" for layer in project.layers]

    def elements(sizes):
        with solid_model.session():
            mesh = meshing.mesh_project(project, element_size=8.0, order=1,
                                        volume_keys=layers, body_sizes=sizes)
        return mesh.stats.elements

    assert elements({"sheetpile": 0.5}) > elements({})


def test_the_contact_follows_the_wall_it_holds():
    """The interface is split off the same curve, so refining the wall refines it too --
    one element a side, which is what keeps the two conformal."""
    deck = excavation_deck(sheetpile=0.5)
    contacts = sum(len(b.entries) for b in deck.elements
                   if b.name.startswith("Geo_UPwLineInterface"))
    assert contacts == 2 * wall_elements(deck)


def test_a_finer_wall_does_not_refine_the_far_field():
    """A `Restrict` field applies to the entities it names. Asking for a fine wall must
    not drag the whole model finer -- the bottom boundary is 60 m down and has no reason
    to notice."""
    plain = len(excavation_deck().parts["Bottom_Fixed"].nodes)
    refined = len(excavation_deck(sheetpile=0.5).parts["Bottom_Fixed"].nodes)
    assert refined == plain


def test_the_structure_size_is_the_same_field_the_soil_uses():
    """One mechanism, not two: `body_sizes` is keyed by part key and a structure has
    one, so nothing new is asked of the user or of the Mesh properties dialog."""
    assert "sheetpile" in excavation_like().part_keys()


# ── A graded mesh ───────────────────────────────────────────────────────────
# Fine where the answer is read, coarse where it is not. Until `BoxRefinement.thickness`
# existed, a refinement could only step: `size` inside the box and the model's own size
# immediately outside it, which puts a jump in element size wherever the box edge falls.
# A band is what turns that step into a grade.


def edge_lengths_by_band(project, **kw):
    """Mean longest triangle edge, in 10 m bands of x."""
    import math
    import gmsh
    with solid_model.session():
        meshing.mesh_project(project, order=2, **kw)
        types, _, connectivity = gmsh.model.mesh.getElements(2)
        tags, coords, _ = gmsh.model.mesh.getNodes()
        at = {int(t): (coords[3 * i], coords[3 * i + 1]) for i, t in enumerate(tags)}
        bands = {}
        for element_type, flat in zip(types, connectivity):
            stride = gmsh.model.mesh.getElementProperties(int(element_type))[3]
            for start in range(0, len(flat), stride):
                corners = [at[int(t)] for t in flat[start:start + stride][:3]]
                longest = max(math.dist(corners[a], corners[b])
                              for a, b in ((0, 1), (1, 2), (2, 0)))
                band = int(sum(p[0] for p in corners) / 3 // 10) * 10
                bands.setdefault(band, []).append(longest)
    return {band: sum(v) / len(v) for band, v in sorted(bands.items())}


def a_box(**kw):
    from core.model.schemas import BoxRefinement
    return BoxRefinement(kind="box", size=0.75, x_min=-1.0, x_max=8.0,
                         y_min=-16.0, y_max=1.0, z_min=-1e6, z_max=1e6, **kw)


def test_a_box_without_a_band_steps_straight_back_to_the_model_size():
    """The behaviour every refinement had before `thickness`, and still the default."""
    bands = edge_lengths_by_band(excavation_like(), element_size=8.0, refinements=[a_box()])
    assert bands[0] < 1.5
    assert bands[20] > 4.0, "without a band the size jumps at the edge of the box"


def test_a_band_grades_the_size_back_out_instead_of_stepping():
    """Growing outwards, and gradually.

    Not strictly monotone: out where the band has run out and every element is the model
    size, the means wobble by a few percent from one 10 m strip to the next, which is
    the mesher and not the grading. The two things that matter are that no strip is
    *smaller* than the one inside it by more than that noise, and that no strip is more
    than twice the one inside it -- a step of four or more is the jump a bare box makes.
    """
    bands = edge_lengths_by_band(excavation_like(), element_size=8.0,
                                 refinements=[a_box(thickness=45.0)])
    sizes = [bands[b] for b in sorted(bands)]
    assert sizes[0] < 1.5 and sizes[-1] > 6.0
    assert all(b > 0.9 * a for a, b in zip(sizes, sizes[1:])), sizes
    assert all(b < 2.5 * a for a, b in zip(sizes, sizes[1:])), sizes


def test_the_test_model_carries_its_own_graded_mesh():
    """A model script is what a user opens, so the grading has to travel with the
    project rather than being typed into a mesh dialog afterwards."""
    project = excavation_like()
    assert project.mesh.refinements, "the project carries its refinement"
    bands = edge_lengths_by_band(
        project, element_size=project.mesh.element_size,
        body_sizes=project.mesh.body_sizes,
        refinements=[r.model_copy() for r in project.mesh.refinements])
    sizes = [bands[b] for b in sorted(bands)]
    coarse = project.mesh.element_size
    assert sizes[0] < 0.25 * coarse, "fine at the excavation"
    assert sizes[-1] > 0.7 * coarse, "back to the model's own size at the far boundary"
    assert sizes[-1] > 4 * sizes[0], "and genuinely graded between them"


# ── A local mesh size: any object, with a band ──────────────────────────────
# The size at an object, and the band over which it grows back to the element size.


def elements_of(project, body_sizes=None, **kw):
    """The element count, with `body_sizes` added to the project's own sizes."""
    sizes = {**project.mesh.body_sizes, **(body_sizes or {})}
    with solid_model.session():
        return meshing.mesh_project(project, order=1, refinements=[], body_sizes=sizes,
                                    **kw).stats.elements


def test_a_band_on_the_wall_grades_the_mesh_out_from_it():
    """The wall at x = 6: fine beside it, the element size far away, and no jump."""
    bands = edge_lengths_by_band(excavation_like(), element_size=8.0, refinements=[],
                                 body_sizes={"sheetpile": 0.75},
                                 size_bands={"sheetpile": 45.0})
    sizes = [bands[b] for b in sorted(bands)]
    assert sizes[0] < 1.5 and sizes[-1] > 6.0
    assert all(b > 0.9 * a for a, b in zip(sizes, sizes[1:])), sizes
    assert all(b < 2.5 * a for a, b in zip(sizes, sizes[1:])), sizes


def test_without_a_band_a_size_meshes_as_it_always_did():
    project = excavation_like()
    sizes = {"sheetpile": 0.5, "soil_L_top": 3.0}
    plain = elements_of(project, element_size=8.0, body_sizes=sizes)
    assert elements_of(project, element_size=8.0, body_sizes=sizes,
                       size_bands={"sheetpile": 0.0, "soil_L_top": 0.0}) == plain


def test_a_band_on_a_layer_grows_its_size_out_into_the_next_one():
    project = excavation_like()
    sizes = {"soil_L_top": 1.0}
    assert (elements_of(project, element_size=8.0, body_sizes=sizes,
                        size_bands={"soil_L_top": 10.0})
            > elements_of(project, element_size=8.0, body_sizes=sizes))


def test_a_band_on_a_size_coarser_than_the_mesh_does_nothing():
    project = excavation_like()
    sizes = {"soil_L_bot": 12.0}
    assert (elements_of(project, element_size=8.0, body_sizes=sizes,
                        size_bands={"soil_L_bot": 20.0})
            == elements_of(project, element_size=8.0, body_sizes=sizes))


def test_a_soil_line_takes_a_size():
    """A soil line has no curves of its own: they are the edges between the bodies it
    split, found on its polyline."""
    project = excavation_like()
    plain = elements_of(project, element_size=8.0)
    sized = elements_of(project, element_size=8.0, body_sizes={"floor_2": 0.5})
    graded = elements_of(project, element_size=8.0, body_sizes={"floor_2": 0.5},
                         size_bands={"floor_2": 10.0})
    assert plain < sized < graded


def test_an_interface_on_a_pile_sizes_the_pile_it_runs_along():
    project = excavation_like()
    assert (elements_of(project, element_size=8.0, body_sizes={"wall_contact": 0.5})
            == elements_of(project, element_size=8.0, body_sizes={"sheetpile": 0.5}))


def test_a_point_load_and_a_point_condition_take_a_size():
    from core.model.schemas import DisplacementCondition, PointLoad
    project = excavation_like()
    payload = project.model_dump()
    payload["loads"] = [PointLoad(id="push", name="Push", x=30.0, y=0.0,
                                  components=(0.0, -1.0)).model_dump()]
    payload["boundary_conditions"] = payload["boundary_conditions"] + [
        DisplacementCondition(id="pin", name="Pin", on="point", points=[(40.0, -30.0)],
                              fixed=(True, True, True)).model_dump()]
    project = Project.model_validate(payload)
    plain = elements_of(project, element_size=8.0)
    for key in ("push", "pin"):
        sized = elements_of(project, element_size=8.0, body_sizes={key: 0.5})
        graded = elements_of(project, element_size=8.0, body_sizes={key: 0.5},
                             size_bands={key: 10.0})
        assert plain < sized < graded, key


def test_a_line_load_an_anchor_and_every_face_take_a_size():
    """Every node part the deck writes can be sized: the edges under a line load, the
    soil round an anchor's head, and the soil's edges on each face of the section."""
    project = excavation_like()
    plain = elements_of(project, element_size=8.0)
    for key in ("surcharge", "strut", "face_bottom", "face_left", "face_right", "face_top"):
        sized = elements_of(project, element_size=8.0, body_sizes={key: 0.5})
        graded = elements_of(project, element_size=8.0, body_sizes={key: 0.5},
                             size_bands={key: 10.0})
        assert plain < sized < graded, key


def test_a_line_load_and_a_face_size_the_edges_the_deck_puts_them_on():
    """The edges under the surcharge, and the soil's edges on the left of the section:
    on the line of the load or the face, and nowhere else."""
    import gmsh
    project = excavation_like()
    load = next(load for load in project.loads if load.id == "surcharge")
    sizes = {"surcharge": 0.5, "face_left": 0.5}
    with solid_model.session():
        built = solid_model.build_geometry(project)
        soil = meshing._finite_element_volumes(project, built, project.part_keys())
        curves = meshing._curves_of(project, built, sizes, 2, soil)
        under = [gmsh.model.getBoundingBox(1, tag) for tag in curves["surcharge"]]
        left = [gmsh.model.getBoundingBox(1, tag) for tag in curves["face_left"]]
    assert under and left
    assert all(abs(box[1] - load.y) < 1e-6 and abs(box[4] - load.y) < 1e-6
               and box[0] >= load.x0 - 1e-6 and box[3] <= load.x1 + 1e-6 for box in under)
    assert sum(box[3] - box[0] for box in under) == pytest.approx(load.x1 - load.x0)
    x0 = project.domain.x0
    assert all(abs(box[0] - x0) < 1e-6 and abs(box[3] - x0) < 1e-6 for box in left)
    assert sum(box[4] - box[1] for box in left) == pytest.approx(
        project.domain.y_top - project.domain.y_bottom)


def test_a_size_names_an_object_the_model_has():
    with pytest.raises(ValueError, match="unknown mesh body size key"):
        elements_of(excavation_like(), element_size=8.0, body_sizes={"nowhere": 1.0})


def test_load_footprint_containment_distinguishes_line_and_surface_loads():
    coordinates = {
        1: (1.0, 0.0, -2.0), 2: (2.0, 0.0, -2.0), 3: (1.5, 0.0, -1.0),
        4: (1.0, 0.0, 1.0),
    }
    line = SimpleNamespace(kind="line", x0=1.0, x1=2.0)
    surface = SimpleNamespace(kind="surface", x0=1.0, x1=2.0, z0=-2.0, z1=0.0)

    assert meshing._under_load([1, 2], coordinates, line)
    assert meshing._under_load([1, 2], coordinates, surface)
    assert not meshing._under_load([1, 4], coordinates, surface)
