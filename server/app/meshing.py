"""Generate a real tetrahedral FE mesh and a drawable boundary payload."""

from __future__ import annotations

from dataclasses import dataclass, field
import time

import gmsh

from app import build
from app.schemas import BoxRefinement, CylinderRefinement, Project
from app.tessellate import DECIMALS, Section


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

    def to_dict(self) -> dict:
        return {
            "bbox": list(self.bbox),
            "stats": self.stats.to_dict(),
            "sections": [section.to_dict() for section in self.sections],
            "log": self.log,
            "meshed_keys": self.meshed_keys,
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
                 body_sizes: dict[str, float] | None = None) -> MeshModel:
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
    built = build.build_geometry(project)
    meshed_keys = volume_keys or project.part_keys()
    unknown = sorted(set(meshed_keys) - set(project.part_keys()))
    if unknown:
        raise ValueError("unknown mesh body key(s): " + ", ".join(unknown))
    finite_element_tags = _finite_element_volumes(project, built, meshed_keys)
    requested_sizes = project.mesh.body_sizes if body_sizes is None else body_sizes
    unknown_sizes = sorted(set(requested_sizes) - set(project.part_keys()))
    if unknown_sizes:
        raise ValueError("unknown mesh body size key(s): " + ", ".join(unknown_sizes))
    volume_sizes = {
        tag: requested_sizes.get(key, size)
        for key in meshed_keys
        for tag in built.volumes.get(key, [])
    }

    gmsh.logger.start()
    try:
        _configure(size, finite_element_tags, refinements or [], volume_sizes=volume_sizes,
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
        log = built.log + gmsh.logger.get()
    except Exception as error:
        raise MeshingError(f"gmsh could not generate the volume mesh: {error}") from error
    finally:
        gmsh.logger.stop()

    return MeshModel(bbox=built.bbox, stats=stats, sections=sections, log=log,
                     meshed_keys=list(meshed_keys))


def _structural_entities(result: build.BuildResult) -> list[tuple[int, int]]:
    """The wall faces and member curves the mesher has to be told to mesh."""
    return ([(2, tag) for tags in result.faces.values() for tag in tags]
            + [(1, tag) for tags in result.curves.values() for tag in tags])


def _finite_element_volumes(project: Project, result: build.BuildResult,
                            volume_keys: list[str] | None = None) -> list[int]:
    """Physical solids only: omit display indicators and the excavation soil alias."""
    keys = volume_keys or ([f"soil_{layer.id}" for layer in project.layers]
                           + ["wall", "struts", "anchors", "piles", "wells"])
    return sorted({tag for key in keys for tag in result.volumes.get(key, [])})


def _configure(element_size: float, volume_tags: list[int],
               refinements: list[BoxRefinement | CylinderRefinement] | None = None,
               *, volume_sizes: dict[int, float] | None = None,
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
            + list((volume_sizes or {}).values())),
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
    _apply_refinements(element_size, refinements or [], volume_sizes or {}, dim)


def _apply_refinements(base_size: float,
                       refinements: list[BoxRefinement | CylinderRefinement],
                       volume_sizes: dict[int, float] | None = None,
                       dim: int = 3) -> int:
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

    if not field_tags:
        return 0
    background = fields.add("Min")
    fields.setNumbers(background, "FieldsList", field_tags)
    fields.setAsBackgroundMesh(background)
    return background


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
    node_tags, flat_coordinates, _ = gmsh.model.mesh.getNodes()
    coordinates = {
        int(tag): (
            float(flat_coordinates[3 * index]),
            float(flat_coordinates[3 * index + 1]),
            float(flat_coordinates[3 * index + 2]),
        )
        for index, tag in enumerate(node_tags)
    }
    section = Section(key="mesh", color=MESH_COLOR)
    local: dict[int, int] = {}
    unique_edges: set[tuple[int, int]] = set()

    def index_of(tag: int) -> int:
        if tag not in local:
            local[tag] = len(local)
            section.positions.extend(round(value, DECIMALS) for value in coordinates[tag])
        return local[tag]

    surfaces = _boundary_surfaces(volume_tags) if dim == 3 else sorted(volume_tags)
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
                unique_edges.update({
                    tuple(sorted((triangle[0], triangle[1]))),
                    tuple(sorted((triangle[1], triangle[2]))),
                    tuple(sorted((triangle[2], triangle[0]))),
                })

    for first, second in sorted(unique_edges):
        for tag in (first, second):
            section.edges.extend(round(value, DECIMALS) for value in coordinates[tag])
    return section


class MeshingError(RuntimeError):
    """A mesh-generation failure suitable for surfacing through the API."""
