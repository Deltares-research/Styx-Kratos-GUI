import math
import uuid
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / ".data"

DIM_NAME = {0: "point", 1: "curve", 2: "surface", 3: "volume"}


def process_creation(recipe: dict) -> dict:
    """Run inside the gmsh worker. Executes a geometry creation recipe and saves a .brep.

    Each recipe kind produces entities of one dimension -- 3 for a solid, 2 for a bare
    surface, 1 for a bare line. That dimension decides which entities to validate and
    measure, so a flat surface or a line does not get held to the "must enclose a volume"
    bar that only means something for solids.

    Returns:
        dict: {"brep_path": str, "dim": int, "volumes": int, "bbox": [xmin, ymin, zmin, xmax, ymax, zmax]}
    """
    import gmsh

    DATA_DIR.mkdir(exist_ok=True)

    gmsh.clear()
    gmsh.model.add("create_temp")

    kind = recipe.get("kind")
    if not kind:
        raise ValueError("Recipe missing 'kind' field")

    _check(recipe, kind)

    if kind == "box":
        o = recipe["origin"]
        s = recipe["size"]
        gmsh.model.occ.addBox(o[0], o[1], o[2], s[0], s[1], s[2])
        dim = 3

    elif kind == "cylinder":
        c = recipe["center"]
        a = recipe["axis"]
        r = recipe["radius"]
        gmsh.model.occ.addCylinder(c[0], c[1], c[2], a[0], a[1], a[2], r)
        dim = 3

    elif kind == "line":
        verts = recipe["vertices"]
        if len(verts) < 2:
            raise ValueError("line requires at least 2 vertices")

        p_tags = [gmsh.model.occ.addPoint(v[0], v[1], v[2]) for v in verts]
        for i in range(len(p_tags) - 1):
            gmsh.model.occ.addLine(p_tags[i], p_tags[i + 1])
        dim = 1

    elif kind == "polygon":
        # A flat surface, no extrusion -- distinct from polygon_extrude below. This is
        # what the GUI's "Create surface" tool sends.
        loop_tag = _closed_loop(gmsh, recipe["vertices"])
        gmsh.model.occ.addPlaneSurface([loop_tag])
        dim = 2

    elif kind == "polygon_extrude":
        ext = recipe["extrusion"]
        loop_tag = _closed_loop(gmsh, recipe["vertices"])
        surf_tag = gmsh.model.occ.addPlaneSurface([loop_tag])
        gmsh.model.occ.extrude([(2, surf_tag)], ext[0], ext[1], ext[2])
        dim = 3

    else:
        raise ValueError(f"Unknown creation recipe kind: {kind}")

    gmsh.model.occ.synchronize()

    entities = gmsh.model.getEntities(dim)
    if not entities:
        raise ValueError(f"Geometry creation produced no {DIM_NAME[dim]} entities.")

    boxes = [gmsh.model.getBoundingBox(dim, tag) for _, tag in entities]
    bbox = (
        min(b[0] for b in boxes), min(b[1] for b in boxes), min(b[2] for b in boxes),
        max(b[3] for b in boxes), max(b[4] for b in boxes), max(b[5] for b in boxes),
    )

    brep_filename = f"{uuid.uuid4().hex}.brep"
    brep_path = DATA_DIR / brep_filename

    gmsh.write(str(brep_path))

    return {
        "brep_path": str(brep_path),
        "dim": dim,
        "volumes": len(entities) if dim == 3 else 0,
        "bbox": bbox,
    }


def _closed_loop(gmsh, verts: list) -> int:
    """Points -> closed line loop -> curve loop tag, shared by polygon and polygon_extrude."""
    if len(verts) < 3:
        raise ValueError("polygon requires at least 3 vertices")

    p_tags = [gmsh.model.occ.addPoint(v[0], v[1], v[2]) for v in verts]
    l_tags = [gmsh.model.occ.addLine(p_tags[i], p_tags[(i + 1) % len(p_tags)])
              for i in range(len(p_tags))]
    return gmsh.model.occ.addCurveLoop(l_tags)


def _vector(recipe: dict, kind: str, key: str) -> list[float]:
    value = recipe.get(key)
    if (not isinstance(value, (list, tuple)) or len(value) != 3
            or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in value)):
        raise ValueError(f"a {kind} needs '{key}' as three finite numbers")
    return [float(v) for v in value]


def _check(recipe: dict, kind: str) -> None:
    """Refuse a recipe that cannot be built, naming the field, before gmsh sees it.

    Left to gmsh, a zero-size box or a missing key surfaces as an OpenCASCADE exception
    or a KeyError -- a 500 that says nothing the user can act on. These are the caller's
    to fix, and the route turns a ValueError into a 422 with this message.
    """
    if kind == "box":
        _vector(recipe, kind, "origin")
        if any(v == 0 for v in _vector(recipe, kind, "size")):
            raise ValueError("a box needs a non-zero 'size' along all three axes")
    elif kind == "cylinder":
        _vector(recipe, kind, "center")
        if not any(_vector(recipe, kind, "axis")):
            raise ValueError("a cylinder needs a non-zero 'axis'")
        radius = recipe.get("radius")
        if not isinstance(radius, (int, float)) or not radius > 0:
            raise ValueError("a cylinder needs a 'radius' greater than zero")
    elif kind in ("polygon", "polygon_extrude"):
        vertices = recipe.get("vertices") or []
        if len(vertices) >= 3 and _area(vertices) <= 1e-12:
            raise ValueError(f"the {kind} has no area: its vertices lie on one line")
        if kind == "polygon_extrude" and not any(_vector(recipe, kind, "extrusion")):
            raise ValueError("a polygon_extrude needs a non-zero 'extrusion'")


def _area(vertices: list) -> float:
    """The polygon's area by Newell's method -- exact for a planar polygon in 3D."""
    nx = ny = nz = 0.0
    for (x0, y0, z0), (x1, y1, z1) in zip(vertices, vertices[1:] + vertices[:1]):
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    return 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)
