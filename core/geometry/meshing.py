"""Generate a real tetrahedral FE mesh and a drawable boundary payload."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import time

import gmsh

from core.geometry import solid_model
from core.model import polylines
from core.model.schemas import BoxRefinement, CylinderRefinement, Project, WaterLevel
from core.geometry.tessellation import DECIMALS, Section


MESH_COLOR = "#d9dee6"
QUALITY_BINS = (0.0, 0.2, 0.4, 0.6, 0.8)
QUALITY_LABELS = ("<0.0", "0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0")
ALGORITHM_3D = {"delaunay": 1, "frontal": 4, "hxt": 10}
# gmsh's Mesh.Algorithm, the 2D counterpart. Frontal-Delaunay is gmsh's own
# recommendation for quality on plane surfaces.
ALGORITHM_2D = {"meshadapt": 1, "auto": 2, "delaunay": 5, "frontal": 6}


@dataclass
class MeshStats:
    nodes: int
    elements: int
    by_type: dict[str, int]
    quality_histogram: dict[str, int]
    seconds: float

    def to_dict(self) -> dict:
        return {
            "nodes": self.nodes,
            "elements": self.elements,
            "by_type": self.by_type,
            "quality_histogram": self.quality_histogram,
            "seconds": self.seconds,
        }


@dataclass
class MeshModel:
    bbox: tuple[float, float, float, float, float, float]
    stats: MeshStats
    sections: list[Section]
    log: list[str] = field(default_factory=list)
    meshed_keys: list[str] = field(default_factory=list)
    parts: list[Section] = field(default_factory=list)
    """The same mesh cut along part keys, one section per part that owns elements: a
    soil body's triangles (in 3D, its own skin), or a structure's line segments. What
    the Model explorer's colour toggle draws, so a user can see which elements are the
    sheet pile's. `sections` stays the one grey buffer the mesh is normally drawn as."""

    def to_dict(self) -> dict:
        return {
            "bbox": list(self.bbox),
            "stats": self.stats.to_dict(),
            "sections": [section.to_dict() for section in self.sections],
            "log": self.log,
            "meshed_keys": self.meshed_keys,
            "parts": [section.to_dict() for section in self.parts],
        }


def mesh_project(project: Project, element_size: float | None = None,
                 order: int | None = None,
                 refinements: list[BoxRefinement | CylinderRefinement] | None = None,
                 algorithm_3d: str | None = None, algorithm_2d: str | None = None,
                 optimization: str | None = None,
                 smoothing: int | None = None, curvature_points: int | None = None,
                 size_min_factor: float | None = None,
                 second_order_linear: bool | None = None,
                 volume_keys: list[str] | None = None,
                 body_sizes: dict[str, float] | None = None,
                 size_bands: dict[str, float] | None = None) -> MeshModel:
    """Rebuild the OCC model, generate tetrahedra, and expose its outer skin."""
    size = project.mesh.element_size if element_size is None else element_size
    requested_order = project.mesh.order if order is None else order
    algorithm = project.mesh.algorithm_3d if algorithm_3d is None else algorithm_3d
    algorithm_planar = project.mesh.algorithm_2d if algorithm_2d is None else algorithm_2d
    dim = 3 if project.dimension != 2 else 2
    optimizer = project.mesh.optimization if optimization is None else optimization
    smooth = project.mesh.smoothing if smoothing is None else smoothing
    curvature = project.mesh.curvature_points if curvature_points is None else curvature_points
    minimum_factor = project.mesh.size_min_factor if size_min_factor is None else size_min_factor
    linear_order_two = (project.mesh.second_order_linear if second_order_linear is None
                        else second_order_linear)
    if size <= 0:
        raise ValueError("element_size must be greater than zero")
    if requested_order not in (1, 2):
        raise ValueError("order must be 1 or 2")

    started = time.perf_counter()
    built = solid_model.build_geometry(project)
    # Expanded, because what picks these picks *layers*: the Mesh properties dialog
    # lists `project.layers`, and a staged layer is several bodies. Naming the layer has
    # to bring the lifts dug out of it, or a project whose pit is staged meshes only the
    # ground outside it -- see `Project.expand_body_keys`. A no-op when nothing is
    # staged, and on a list that already names bodies.
    meshed_keys = project.expand_body_keys(volume_keys) if volume_keys \
        else project.part_keys()
    unknown = sorted(set(meshed_keys) - set(project.part_keys()))
    if unknown:
        raise ValueError("unknown mesh body key(s): " + ", ".join(unknown))
    finite_element_tags = _finite_element_volumes(project, built, meshed_keys)
    requested_sizes = project.mesh.body_sizes if body_sizes is None else body_sizes
    requested_bands = project.mesh.size_bands if size_bands is None else size_bands
    # A size asked for a layer applies to every body dug out of it, for the same reason.
    requested_sizes = {key: size for layer_key, size in requested_sizes.items()
                       for key in project.expand_body_keys([layer_key])}
    requested_bands = {key: band for layer_key, band in requested_bands.items()
                       for key in project.expand_body_keys([layer_key])}
    unknown_sizes = sorted(set(requested_sizes) - set(project.mesh_size_keys()))
    if unknown_sizes:
        raise ValueError("unknown mesh body size key(s): " + ", ".join(unknown_sizes))
    volume_sizes = {
        tag: requested_sizes.get(key, size)
        for key in meshed_keys
        for tag in built.volumes.get(key, [])
    }
    # The same sizes, for the parts that are curves rather than bodies: a sheet pile, a
    # member, an anchor, the line an interface or a normal load follows. They have part
    # keys like everything else, so a size could always be *asked* for one -- it was
    # looked up in `built.volumes`, which holds nothing for them, and silently dropped.
    # A wall meshed finer than the ground it stands in is the ordinary thing to want:
    # the wall is where the bending moments are read, and the reference deck meshes its
    # own at 1 m inside soil at 2 m.
    #
    # Only the sizes actually asked for, unlike the bodies above. Pinning every curve to
    # the base size would stop the mesh grading along it, and a curve that nobody sized
    # should take whatever the surface around it is doing.
    # Every curve asked for, not only those among `meshed_keys`: that list names the
    # soil bodies to mesh (the Mesh properties window sends its ticked layers), and a
    # wall standing in them is meshed with them whether it is named or not.
    curves_of = _curves_of(project, built, requested_sizes, dim)
    curve_sizes = {
        tag: size
        for key, size in requested_sizes.items()
        for tag in curves_of.get(key, [])
    }
    # A 3D wall panel is faces, and a soil line in a solid model is the faces it was
    # swept into: one dimension below the model, as a curve is in a section.
    faces_of = _faces_of(project, built, requested_sizes, dim)
    face_sizes = {
        tag: size
        for key, size in requested_sizes.items()
        for tag in faces_of.get(key, [])
    }
    graded = _graded_sizes(project, built, size, requested_sizes, requested_bands,
                           meshed_keys, curves_of, faces_of, dim)

    gmsh.logger.start()
    try:
        _configure(size, finite_element_tags, refinements or [], volume_sizes=volume_sizes,
                   curve_sizes=curve_sizes, face_sizes=face_sizes, graded=graded,
                   algorithm_3d=algorithm, algorithm_2d=algorithm_planar, dim=dim,
                   smoothing=smooth, curvature_points=curvature,
                   size_min_factor=minimum_factor, second_order_linear=linear_order_two,
                   structural=_structural_entities(built))
        gmsh.model.mesh.generate(dim)
        if optimizer != "none":
            # Netgen only optimizes tetrahedra. Asking for it on a plane mesh is not an
            # error, it simply does nothing, so 2D falls back to gmsh's own optimizer.
            gmsh.model.mesh.optimize("Netgen" if optimizer == "netgen" and dim == 3 else "")
        if requested_order == 2:
            # setOrder operates on an existing mesh; calling it before generate is a no-op.
            gmsh.model.mesh.setOrder(2)

        stats = _stats(time.perf_counter() - started, dim)
        sections = [_boundary_section(finite_element_tags, dim)]
        parts = _part_sections(project, built, meshed_keys, dim)
        log = built.log + gmsh.logger.get()
    except Exception as error:
        raise MeshingError(f"gmsh could not generate the volume mesh: {error}") from error
    finally:
        gmsh.logger.stop()

    return MeshModel(bbox=built.bbox, stats=stats, sections=sections, log=log,
                     meshed_keys=list(meshed_keys), parts=parts)


@dataclass(frozen=True)
class GradedSize:
    """A local size that grows back to the element size over a band.

    `dim` and `tags` are the entities the size is measured from: the model's own
    dimension for a soil body (the size holds inside it and grows outside it), one
    below for a wall, a line or a panel. A point has no entity: `at` is where it is.
    """
    size: float
    band: float
    dim: int = 0
    tags: tuple[int, ...] = ()
    at: tuple[float, float, float] | None = None


# How near a curve or face has to lie to a drawn line to be part of it, in metres. Looser
# than `solid_model.TOLERANCE`: a centre of mass carries more rounding than a vertex.
ON_LINE = 1e-5


def _entities_on(points: list[tuple[float, float]], dim: int,
                 among: list[int] | None = None) -> list[int]:
    """The entities of dimension `dim` that lie on the polyline `points` in the (x, y)
    plane: every vertex of the entity and its centre of mass. In a section that is the
    curves along a line; in a solid model, the faces the line was swept into."""
    out: list[int] = []
    tags = among if among is not None else [tag for _, tag in gmsh.model.getEntities(dim)]
    for tag in tags:
        corners = [gmsh.model.getValue(0, vertex, [])
                   for _, vertex in gmsh.model.getBoundary([(dim, tag)], combined=False,
                                                           oriented=False, recursive=True)]
        middle = gmsh.model.occ.getCenterOfMass(dim, tag)
        if corners and all(polylines.nearest(points, (p[0], p[1]))[1] < ON_LINE
                           for p in [*corners, middle]):
            out.append(tag)
    return sorted(out)


def _curves_of(project: Project, built: solid_model.BuildResult,
               sizes: dict[str, float], dim: int) -> dict[str, list[int]]:
    """Part key -> the curves a size on it applies to. The structures the build embeds
    have their own (`built.curves`). A soil line and an interface on a pile have none:
    their curves are found on their polylines, the soil line's only in a section."""
    curves = dict(built.curves)
    lines = {line.id: line for line in project.lines} if dim == 2 else {}
    for key in sizes:
        if key in curves:
            continue
        if key in lines:
            curves[key] = _entities_on([(p[0], p[1]) for p in lines[key].points], 1)
            continue
        interface = next((i for i in project.interfaces
                          if i.id == key and i.structure is not None), None)
        if interface is not None and interface.structure in built.curves:
            curves[key] = _entities_on(project.interface_path(interface), 1,
                                       built.curves[interface.structure])
    return curves


def _faces_of(project: Project, built: solid_model.BuildResult,
              sizes: dict[str, float], dim: int) -> dict[str, list[int]]:
    """Part key -> the faces a size on it applies to, in a solid model only: a wall
    panel's own faces, and the faces a soil line was swept into."""
    if dim != 3:
        return {}
    faces = dict(built.faces)
    for line in project.lines:
        if line.id in sizes and line.id not in faces:
            faces[line.id] = _entities_on([(p[0], p[1]) for p in line.points], 2)
    return faces


def _point_of(project: Project, key: str, dim: int) -> tuple[float, float, float] | None:
    """Where the point condition or the point load `key` is, or None."""
    for condition in project.boundary_conditions:
        if condition.id == key and condition.on == "point" and condition.points:
            x, y = condition.points[0]
            return (x, y, 0.0)
    for load in project.loads:
        if load.id == key and load.kind == "point":
            return (load.x, load.y, 0.0) if dim == 2 else (load.x, load.y, project.cut_at())
    return None


def _graded_sizes(project: Project, built: solid_model.BuildResult, base: float,
                  sizes: dict[str, float], bands: dict[str, float],
                  meshed_keys: list[str], curves_of: dict[str, list[int]],
                  faces_of: dict[str, list[int]], dim: int) -> list[GradedSize]:
    """The sizes that grow back to `base` over a band, and every point size.

    A size with no band keeps the field it always had, so a project that sets no band
    meshes as it did. A band on a size coarser than `base` has nothing to grow back to
    and is not used. A point has no field of its own to fall back on: with no band, its
    size holds within one element of it."""
    out: list[GradedSize] = []
    for key, size in sizes.items():
        band = bands.get(key, 0.0)
        at = _point_of(project, key, dim)
        if at is not None:
            out.append(GradedSize(size=size, band=band, at=at))
            continue
        if band <= 0.0 or size >= base:
            continue
        if key in meshed_keys and built.volumes.get(key):
            out.append(GradedSize(size, band, dim, tuple(built.volumes[key])))
        elif curves_of.get(key):
            out.append(GradedSize(size, band, 1, tuple(curves_of[key])))
        elif faces_of.get(key):
            out.append(GradedSize(size, band, 2, tuple(faces_of[key])))
    return out


def _structural_entities(result: solid_model.BuildResult) -> list[tuple[int, int]]:
    """The wall faces and member curves the mesher has to be told to mesh."""
    return ([(2, tag) for tags in result.faces.values() for tag in tags]
            + [(1, tag) for tags in result.curves.values() for tag in tags])


def _finite_element_volumes(project: Project, result: solid_model.BuildResult,
                            volume_keys: list[str] | None = None) -> list[int]:
    """Physical solids only: omit display indicators and the excavation soil alias."""
    keys = volume_keys or ([f"soil_{layer.id}" for layer in project.layers]
                           + ["wall", "struts", "anchors", "piles", "wells"])
    return sorted({tag for key in keys for tag in result.volumes.get(key, [])})


def _configure(element_size: float, volume_tags: list[int],
               refinements: list[BoxRefinement | CylinderRefinement] | None = None,
               *, volume_sizes: dict[int, float] | None = None,
               curve_sizes: dict[int, float] | None = None,
               face_sizes: dict[int, float] | None = None,
               graded: list[GradedSize] | None = None,
               algorithm_3d: str = "delaunay", algorithm_2d: str = "frontal",
               dim: int = 3, smoothing: int = 10,
               curvature_points: int = 16, size_min_factor: float = 0.05,
               second_order_linear: bool = True,
               structural: list[tuple[int, int]] | None = None) -> None:
    if dim == 3:
        gmsh.option.setNumber("Mesh.Algorithm3D", ALGORITHM_3D[algorithm_3d])
    else:
        gmsh.option.setNumber("Mesh.Algorithm", ALGORITHM_2D[algorithm_2d])
    gmsh.option.setNumber("Mesh.Smoothing", smoothing)
    gmsh.option.setNumber("Mesh.MeshSizeMin", element_size * size_min_factor)
    gmsh.option.setNumber(
        "Mesh.MeshSizeMax",
        max([element_size]
            + [r.size for r in refinements or []]
            + list((volume_sizes or {}).values())
            + list((curve_sizes or {}).values())
            + list((face_sizes or {}).values())),
    )
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
    # Thin cylinders need enough points around their circumference. Without this,
    # coarse global sizes make cap and side facets overlap at anchor/wall interfaces.
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", curvature_points)
    # Keep quadratic midside nodes on their linear edges. Curving them back onto the
    # numerous tiny OCC fragments can invert otherwise valid tetrahedra.
    gmsh.option.setNumber("Mesh.SecondOrderLinear", int(second_order_linear))

    # load and water are thin display indicators, not FE material. Mesh only the real
    # solids without deleting anything from the B-rep or invalidating physical groups.
    gmsh.model.setVisibility(gmsh.model.getEntities(), 0, recursive=False)
    gmsh.model.setVisibility([(dim, tag) for tag in volume_tags], 1, recursive=True)
    # A structure embedded in a 3D volume is not part of that volume's B-rep -- an
    # internal face bounds nothing and an internal curve bounds no face -- so the
    # recursion above never reaches a member's curves, and it would go unmeshed while
    # the tetrahedra around it conform to it perfectly. Naming them here is what turns
    # that geometry into elements. Anchor ties are deliberately left out: their truss is
    # built from located nodes, and meshing the tie would only add nodes no element uses.
    if structural:
        gmsh.model.setVisibility(structural, 1, recursive=True)
    gmsh.option.setNumber("Mesh.MeshOnlyVisible", 1)
    _apply_refinements(element_size, refinements or [], volume_sizes or {}, dim,
                       curve_sizes or {}, face_sizes=face_sizes, graded=graded)


def _apply_refinements(base_size: float,
                       refinements: list[BoxRefinement | CylinderRefinement],
                       volume_sizes: dict[int, float] | None = None,
                       dim: int = 3,
                       curve_sizes: dict[int, float] | None = None,
                       *, face_sizes: dict[int, float] | None = None,
                       graded: list[GradedSize] | None = None) -> int:
    """Create local size fields and return the background Min field tag, or zero.

    A size is restricted to each OCC volume instead of meshing the volumes in
    separate passes.  Consequently a fragmented interface remains one surface;
    Gmsh applies the finer adjacent constraint there and both volumes reuse the
    same surface nodes.
    """
    fields = gmsh.model.mesh.field
    field_tags: list[int] = []
    for refinement in refinements:
        tag = fields.add("Box" if refinement.kind == "box" else "Cylinder")
        fields.setNumber(tag, "VIn", refinement.size)
        fields.setNumber(tag, "VOut", base_size)
        if isinstance(refinement, BoxRefinement):
            for option, value in (
                ("XMin", refinement.x_min), ("XMax", refinement.x_max),
                ("YMin", refinement.y_min), ("YMax", refinement.y_max),
                ("ZMin", refinement.z_min), ("ZMax", refinement.z_max),
                # gmsh grows the size from VIn back to VOut across this band outside
                # the box. Zero is a step, which is what a box with no band means.
                ("Thickness", refinement.thickness),
            ):
                fields.setNumber(tag, option, value)
        else:
            for option, value in (
                ("XCenter", refinement.x), ("YCenter", refinement.y), ("ZCenter", refinement.z),
                ("XAxis", refinement.axis_x), ("YAxis", refinement.axis_y),
                ("ZAxis", refinement.axis_z), ("Radius", refinement.radius),
            ):
                fields.setNumber(tag, option, value)
        field_tags.append(tag)

    for volume_tag, size in (volume_sizes or {}).items():
        constant = fields.add("MathEval")
        fields.setString(constant, "F", repr(size))
        restricted = fields.add("Restrict")
        fields.setNumber(restricted, "InField", constant)
        # A Restrict field matches by entity dimension. Left as VolumesList on a plane
        # model it matches nothing, gmsh reports no error, and the per-body size is
        # silently ignored -- every element comes out the base size instead.
        fields.setNumbers(restricted, "SurfacesList" if dim == 2 else "VolumesList",
                          [volume_tag])
        field_tags.append(restricted)

    for curve_tag, curve_size in (curve_sizes or {}).items():
        constant = fields.add("MathEval")
        fields.setString(constant, "F", repr(curve_size))
        restricted = fields.add("Restrict")
        fields.setNumber(restricted, "InField", constant)
        # `CurvesList` whatever the model's dimension: a structure is a curve in a plane
        # section and a curve in a solid alike. Restricted to the curve, so a finely
        # meshed wall pulls the elements that touch it finer -- they have to share its
        # nodes -- and leaves the far field alone.
        fields.setNumbers(restricted, "CurvesList", [curve_tag])
        field_tags.append(restricted)

    # A 3D wall panel, the same way: a constant on its faces.
    for face_tag, face_size in (face_sizes or {}).items():
        constant = fields.add("MathEval")
        fields.setString(constant, "F", repr(face_size))
        restricted = fields.add("Restrict")
        fields.setNumber(restricted, "InField", constant)
        fields.setNumbers(restricted, "SurfacesList", [face_tag])
        field_tags.append(restricted)

    for local in graded or []:
        field_tags.append(_graded_field(local, base_size, dim))

    if not field_tags:
        return 0
    background = fields.add("Min")
    fields.setNumbers(background, "FieldsList", field_tags)
    fields.setAsBackgroundMesh(background)
    return background


def _graded_field(local: GradedSize, base_size: float, dim: int) -> int:
    """A Threshold field: `local.size` at the object, growing linearly to `base_size`
    over `local.band`, and no limit beyond it -- a coarser size outside the band (a layer
    of its own size) is not cut back to `base_size`.

    The distance is measured from the object's entities: a body's edges in a section or
    its faces in a solid (the size inside the body is its own Restrict field), a curve
    or a face itself, sampled finely enough that the distance is true to about a tenth
    of the size. A point is measured from where it is."""
    fields = gmsh.model.mesh.field
    distance = fields.add("Distance" if local.at is None else "MathEval")
    near = 0.0
    if local.at is not None:
        x, y, z = local.at
        fields.setString(distance, "F", f"Sqrt((x-({x!r}))^2+(y-({y!r}))^2+(z-({z!r}))^2)")
        near = local.size
    else:
        entity_dim = local.dim - 1 if local.dim == dim else local.dim
        tags = list(local.tags)
        if local.dim == dim:
            tags = sorted({tag for _, tag in gmsh.model.getBoundary(
                [(dim, tag) for tag in tags], combined=False, oriented=False)})
        extent = max(gmsh.model.occ.getMass(entity_dim, tag) for tag in tags)
        if entity_dim == 2:
            extent = math.sqrt(extent)
        fields.setNumbers(distance, "CurvesList" if entity_dim == 1 else "SurfacesList", tags)
        fields.setNumber(distance, "Sampling",
                         min(400 if entity_dim == 1 else 100,
                             max(20, math.ceil(10 * extent / local.size))))
    threshold = fields.add("Threshold")
    fields.setNumber(threshold, "InField", distance)
    fields.setNumber(threshold, "SizeMin", local.size)
    fields.setNumber(threshold, "SizeMax", max(base_size, local.size))
    fields.setNumber(threshold, "DistMin", near)
    fields.setNumber(threshold, "DistMax", near + local.band)
    fields.setNumber(threshold, "StopAtDistMax", 1)
    return threshold


def _stats(seconds: float, dim: int = 3) -> MeshStats:
    node_tags, _, _ = gmsh.model.mesh.getNodes()
    types, element_tags, _ = gmsh.model.mesh.getElements(dim)

    by_type: dict[str, int] = {}
    all_elements: list[int] = []
    for element_type, tags in zip(types, element_tags):
        name = gmsh.model.mesh.getElementProperties(int(element_type))[0]
        by_type[name] = by_type.get(name, 0) + len(tags)
        all_elements.extend(int(tag) for tag in tags)

    histogram = {label: 0 for label in QUALITY_LABELS}
    if all_elements:
        qualities = gmsh.model.mesh.getElementQualities(all_elements, "minSICN")
        for quality in qualities:
            value = min(1.0, float(quality))
            index = sum(value >= boundary for boundary in QUALITY_BINS)
            histogram[QUALITY_LABELS[index]] += 1

    return MeshStats(
        nodes=len(node_tags),
        elements=len(all_elements),
        by_type=by_type,
        quality_histogram=histogram,
        seconds=round(seconds, 3),
    )


def _boundary_surfaces(volume_tags: list[int]) -> list[int]:
    owners: dict[int, int] = {}
    for volume in volume_tags:
        for _, surface in gmsh.model.getBoundary([(3, volume)], oriented=False):
            tag = abs(int(surface))
            owners[tag] = owners.get(tag, 0) + 1
    return sorted(surface for surface, count in owners.items() if count == 1)


def _boundary_section(volume_tags: list[int], dim: int = 3) -> Section:
    """Convert high- or low-order surface elements to linear browser triangles.

    In 3D the drawable payload is the outer skin, so the surfaces are those owned by
    exactly one meshed volume. In 2D the meshed faces *are* the payload -- a plane mesh
    has no skin to walk -- so they are emitted directly.
    """
    surfaces = _boundary_surfaces(volume_tags) if dim == 3 else sorted(volume_tags)
    return _surface_section("mesh", surfaces, _node_coordinates())


def _node_coordinates() -> dict[int, tuple[float, float, float]]:
    node_tags, flat_coordinates, _ = gmsh.model.mesh.getNodes()
    return {
        int(tag): (
            float(flat_coordinates[3 * index]),
            float(flat_coordinates[3 * index + 1]),
            float(flat_coordinates[3 * index + 2]),
        )
        for index, tag in enumerate(node_tags)
    }


def _part_sections(project: Project, built: solid_model.BuildResult, meshed_keys: list[str],
                   dim: int) -> list[Section]:
    """One section per part key that owns elements, in `Project.part_keys` order, then
    the loads that order leaves out.

    A body is its triangles: the faces it owns in 2D, its own skin in 3D (the skin of
    that body alone, so a body buried inside the model still has something to draw), and
    a 3D wall's panels. A structure is its line elements' segments. An interface is one
    section per face it unglues (`_interface_sections`), and a load is the boundary
    edges the deck applies it on (`_load_sections`).

    `excavation` is left out: it is an alias for the soil bodies, not a part, and
    drawing it would paint every soil triangle a second time.
    """
    coordinates = _node_coordinates()
    meshed = set(meshed_keys)
    interfaces = {interface.id: interface for interface in project.active_interfaces}
    loads = _load_sections(project, dim, coordinates)
    keys = project.part_keys()
    # A layered-soil project draws no load pads, so its loads are not part keys -- but
    # they are rows in the Model explorer and conditions in the deck all the same.
    keys = keys + [key for key in loads if key not in keys]
    # The water level likewise: a row in the Model explorer whenever the project has one,
    # whether or not the build raises a slab for it.
    if project.water is not None and "water" not in keys:
        keys.append("water")
    sections = []
    for key in keys:
        if key == "excavation":
            continue
        if key == "water":
            if project.water is not None:
                sections.append(_water_section(project, project.water, dim))
            continue
        if key in loads:
            sections.append(loads[key])
            continue
        if key in interfaces:
            sections.extend(_interface_sections(interfaces[key], project, built,
                                                coordinates))
            continue
        bodies = built.volumes.get(key, []) if key in meshed else []
        surfaces = (_boundary_surfaces(bodies) if dim == 3 else sorted(bodies)) \
            + built.faces.get(key, [])
        section = _surface_section(key, surfaces, coordinates)
        for start, end in _line_segments(built.curves.get(key, []), coordinates):
            section.edges.extend(start + end)
        _add_tie_segments(section, built.ties.get(key, []))
        if section.indices or section.edges:
            sections.append(section)
    return sections


def _water_section(project: Project, water: WaterLevel, dim: int) -> Section:
    """The phreatic level as lines: across the section in 2D, the outline of the level's
    plane in 3D. With the slab's own overhang, as the viewport's water line has it
    (frontend/js/viewport.js `waterLineSpec`), so the level reads past the model's edges."""
    d = project.domain
    x0, x1 = d.x0 - water.margin, d.x1 + water.margin
    if dim == 2:
        corners = [(x0, water.y, 0.0), (x1, water.y, 0.0)]
        pairs = [(corners[0], corners[1])]
    else:
        z0, z1 = d.z0 - water.margin, d.z1 + water.margin
        corners = [(x0, water.y, z0), (x1, water.y, z0), (x1, water.y, z1),
                   (x0, water.y, z1)]
        pairs = list(zip(corners, corners[1:] + corners[:1]))
    section = Section(key="water", color=MESH_COLOR)
    for start, end in pairs:
        section.edges.extend(round(value, DECIMALS) for value in start + end)
    return section


INTERFACE_SIDES = {"both": ("L", "R"), "left": ("L",), "right": ("R",), "below": ("L",),
                   "above": ("R",)}
"""The faces an interface unglues, by `Interface.side`, as the suffix of their key: L for
the face on the left of the screen (below, on a flat line), R for the other."""

PIECE_TOLERANCE = 1e-6
"""Metres. How near the line between From and To a piece of the pile's curve has to be
to be drawn as part of the interface."""

SIDE_OFFSET = 0.15
"""How far each face of an interface is drawn off its line, as a fraction of the
shortest segment along it. Both faces lie exactly on the line, so drawn there one would
hide the other; this much is enough to see two and little enough to still read as the
line."""


def _interface_sections(interface, project: Project, built: solid_model.BuildResult,
                        coordinates: dict[int, tuple[float, float, float]]
                        ) -> list[Section]:
    """`<key>:L` and/or `<key>:R`: one section per face the interface unglues.

    The deck has a contact element per face (`core.kratos.interfaces`), and which face a user is
    looking at matters -- one holds the retained soil, the other the excavated side. An
    interface on a structure owns no curve of its own, so its segments are the
    structure's, between From and To when it holds only a part of it. Each face is
    pushed toward its own side of the screen (`schemas.Interface`) using the direction
    of the leg of the line it lies along, not the direction gmsh happened to build the
    curve in. The drawn segments are therefore *not* node positions: they are
    `SIDE_OFFSET` of a segment away from them.
    """
    path = project.interface_path(interface)
    curves = built.curves.get(interface.structure or interface.id, [])
    pieces = [(start, end) for start, end in _line_segments(curves, coordinates)
              if polylines.nearest(path, ((start[0] + end[0]) / 2,
                                          (start[1] + end[1]) / 2))[1] <= PIECE_TOLERANCE]
    if not pieces:
        return []
    lengths = [math.dist(start, end) for start, end in pieces]
    offset = SIDE_OFFSET * min(length for length in lengths if length > 0)
    faces = polylines.faces(path)
    sections = []
    for side in INTERFACE_SIDES[interface.side]:
        # `_left_of` is the left walking the line, and L is the screen's left.
        walking = polylines.walking_side(path, faces[0] if side == "L" else faces[1])
        sign = 1.0 if walking == "left" else -1.0
        section = Section(key=f"{interface.id}:{side}", color=MESH_COLOR)
        for start, end in pieces:
            nx, ny = _left_of(path, start, end)
            dx, dy = sign * offset * nx, sign * offset * ny
            section.edges.extend(round(value, DECIMALS) for value in (
                start[0] + dx, start[1] + dy, start[2], end[0] + dx, end[1] + dy, end[2]))
        sections.append(section)
    return sections


def _left_of(path: list[tuple[float, float]], start: tuple[float, float, float],
             end: tuple[float, float, float]) -> tuple[float, float]:
    """The unit left normal of the leg of `path` a segment lies along: the leg nearest
    the segment's midpoint."""
    mx, my = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
    best = None
    for (ax, ay), (bx, by) in zip(path, path[1:]):
        lx, ly = bx - ax, by - ay
        length_sq = lx * lx + ly * ly
        if length_sq == 0:
            continue
        along = max(0.0, min(1.0, ((mx - ax) * lx + (my - ay) * ly) / length_sq))
        distance = math.hypot(ax + along * lx - mx, ay + along * ly - my)
        if best is None or distance < best[0]:
            best = (distance, lx, ly)
    if best is None:
        return (0.0, 0.0)
    _, lx, ly = best
    length = math.hypot(lx, ly)
    return (-ly / length, lx / length)


POINT = 15
"""gmsh's element type for a single node: what `loaded_elements` calls a point load's
row, which is one node rather than boundary elements."""


def loaded_elements(project: Project, dim: int,
                    world: dict[int, tuple[float, float, float]]
                    ) -> list[tuple[str, int, list[list[int]]]]:
    """`(load id, gmsh element type, node rows)` for each active load: the boundary
    elements on the ground surface that lie under it, or for a point load the one node
    nearest it, typed `POINT`. Rows are in gmsh's node order.

    Two things ask, and both ask here, so they cannot disagree: `core.kratos.writer`
    writes a condition on each row, and the mesh preview colours the same edges
    (`_load_sections`), so the line a user sees is exactly the one Kratos is told to load.

    Selected element by element rather than entity by entity: the pad is a display
    indicator that never cuts the soil, so the loaded region is not a separate part.
    `solid_model._imprint_load_footprints` has split the boundary exactly at the footprint
    edges, so every element is wholly inside or wholly outside it and the test below is
    an exact containment test. Without that imprint the only available rule would be
    whether an element's centre lies under the pad, which moves a loaded edge by as
    much as one element.
    """
    out: list[tuple[str, int, list[list[int]]]] = []
    carried: set[int] | None = None
    # `loads_for` rather than a kind test: a translated pair holds a surface record and
    # a line record for one load, and taking both would apply it twice. What it hands
    # back for a 3D model is the surface loads plus the 2D ones nothing was translated
    # from.
    for load in project.loads_for(dim):
        # A 3D line load imprints a *curve* on the solid's boundary, and the boundary
        # elements read below are faces; the exporter says so in its warnings.
        if not load.active or (dim == 3 and load.kind == "line"):
            continue
        if load.kind == "point":
            target = ((load.x, load.y, 0.0) if dim == 2
                      else (load.x, load.y, project.cut_at()))
            # Only a node an element of the model holds: the fragment keeps each pile's
            # own drawn line beside the pieces it cut, and the line's end vertex is a
            # node of its own at the pile head, in no element. A load put there loaded
            # nothing, and Kratos stopped at the stage it arrived in.
            if carried is None:
                carried = _carried_nodes(dim)
            nearest = min(
                (tag for tag in world if tag in carried),
                key=lambda tag: sum((world[tag][axis] - target[axis]) ** 2 for axis in range(3)),
            )
            out.append((load.id, POINT, [[nearest]]))
            continue
        elevation = project.elevation_of(load)
        rows_by_type: dict[int, list[list[int]]] = {}
        for _, entity in gmsh.model.getEntities(dim - 1):
            box = gmsh.model.getBoundingBox(dim - 1, entity)
            if (abs(box[1] - elevation) > solid_model.TOLERANCE
                    or abs(box[4] - elevation) > solid_model.TOLERANCE):
                continue
            types, _, connectivity = gmsh.model.mesh.getElements(dim - 1, entity)
            for element_type, flat in zip(types, connectivity):
                size = gmsh.model.mesh.getElementProperties(int(element_type))[3]
                for offset in range(0, len(flat), size):
                    row = [int(flat[offset + i]) for i in range(size)]
                    if _under_load(row[:dim], world, load):
                        rows_by_type.setdefault(int(element_type), []).append(row)
        out.extend((load.id, element_type, rows)
                   for element_type, rows in rows_by_type.items() if rows)
    return out


def _carried_nodes(dim: int) -> set[int]:
    """The nodes of the model's own elements: its soil and every line in a physical
    group (the structures). A curve the fragment left behind and no group names is meshed
    too, and its nodes are in no element of the deck."""
    nodes: set[int] = set()
    entities = [(dim, tag) for _, tag in gmsh.model.getEntities(dim)]
    for group_dim, group in gmsh.model.getPhysicalGroups():
        if group_dim < dim:
            entities.extend((group_dim, int(tag)) for tag in
                            gmsh.model.getEntitiesForPhysicalGroup(group_dim, group))
    for entity_dim, tag in entities:
        for flat in gmsh.model.mesh.getElements(entity_dim, tag)[2]:
            nodes.update(int(node) for node in flat)
    return nodes


def _under_load(corners: list[int], world: dict[int, tuple[float, float, float]],
                load) -> bool:
    """Every corner inside the footprint, within the tolerance the imprint holds to."""
    def inside(value: float, low: float, high: float) -> bool:
        return low - solid_model.TOLERANCE <= value <= high + solid_model.TOLERANCE

    if load.kind == "line":
        return all(inside(world[tag][0], load.x0, load.x1) for tag in corners)
    return all(inside(world[tag][0], load.x0, load.x1)
               and inside(world[tag][2], load.z0, load.z1) for tag in corners)


def _load_sections(project: Project, dim: int,
                   coordinates: dict[int, tuple[float, float, float]]
                   ) -> dict[str, Section]:
    """Each load, as the edges the deck applies it on (`loaded_elements`). A point load
    is one node, drawn as a segment of no length so it still gets its dot. A 3D surface
    load is drawn by the edges of its faces.
    """
    out: dict[str, Section] = {}
    for key, _, rows in loaded_elements(project, dim, coordinates):
        section = out.setdefault(key, Section(key=key, color=MESH_COLOR))
        for row in rows:
            corners = row[:dim]
            pairs = ([(corners[0], corners[0])] if len(corners) == 1 else
                     [(corners[0], corners[1])] if len(corners) == 2 else
                     list(zip(corners, corners[1:] + corners[:1])))
            for first, second in pairs:
                for tag in (first, second):
                    section.edges.extend(round(value, DECIMALS)
                                         for value in coordinates[tag])
    return out


def _line_segments(curves: list[int], coordinates: dict[int, tuple[float, float, float]]
                   ) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """Each line element on `curves`, corner to corner, rounded for the payload. A
    quadratic line's mid node is skipped, the same way a six-node triangle is drawn by
    its three corners."""
    out: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    for curve in curves:
        types, _, connectivities = gmsh.model.mesh.getElements(1, curve)
        for element_type, connectivity in zip(types, connectivities):
            node_count = gmsh.model.mesh.getElementProperties(int(element_type))[3]
            for offset in range(0, len(connectivity), node_count):
                out.append((_rounded(coordinates[int(connectivity[offset])]),
                            _rounded(coordinates[int(connectivity[offset + 1])])))
    return out


def _rounded(point: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = point
    return (round(x, DECIMALS), round(y, DECIMALS), round(z, DECIMALS))


def _add_tie_segments(section: Section, curves: list[int]) -> None:
    """An anchor is one two-node truss from head to tail whatever the mesh does along
    its curve (`core.kratos.writer._anchor_ties`), so it is drawn as that one segment:
    the curve's two end points."""
    for curve in curves:
        ends = gmsh.model.getBoundary([(1, curve)], oriented=False)
        for _, point in ends[:2]:
            section.edges.extend(round(float(value), DECIMALS)
                                 for value in gmsh.model.getValue(0, abs(point), []))


def _surface_section(key: str, surfaces: list[int],
                     coordinates: dict[int, tuple[float, float, float]]) -> Section:
    """The triangles on `surfaces`, with their unique edges as a wireframe."""
    section = Section(key=key, color=MESH_COLOR)
    local: dict[int, int] = {}
    unique_edges: set[tuple[int, int]] = set()

    def index_of(tag: int) -> int:
        if tag not in local:
            local[tag] = len(local)
            section.positions.extend(round(value, DECIMALS) for value in coordinates[tag])
        return local[tag]

    for surface in surfaces:
        types, _, connectivities = gmsh.model.mesh.getElements(2, surface)
        for element_type, connectivity in zip(types, connectivities):
            _, dimension, _, node_count, _, primary_count = gmsh.model.mesh.getElementProperties(
                int(element_type)
            )
            if dimension != 2 or primary_count != 3:
                continue
            for offset in range(0, len(connectivity), node_count):
                triangle = [int(tag) for tag in connectivity[offset:offset + 3]]
                indices = [index_of(tag) for tag in triangle]
                section.indices.extend(indices)
                a, b, c = triangle
                unique_edges.update({
                    (min(a, b), max(a, b)),
                    (min(b, c), max(b, c)),
                    (min(c, a), max(c, a)),
                })

    for first, second in sorted(unique_edges):
        for tag in (first, second):
            section.edges.extend(round(value, DECIMALS) for value in coordinates[tag])
    return section


class MeshingError(RuntimeError):
    """A mesh-generation failure suitable for surfacing through the API."""
