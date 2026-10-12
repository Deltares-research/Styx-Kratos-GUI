"""CAD import: a file in, OpenCASCADE solids out, saved as a .brep the build reloads.

Two kinds of file, two routes to the same place:

*   **CAD** (STEP, IGES, BREP) is read by OpenCASCADE, with face sewing and solid making on:
    IGES describes faces rather than solids, so a box written as IGES arrives as six loose
    faces, and without these options it could never be imported.
*   **Triangulated surfaces** (STL, OBJ) are read here, checked for being closed, split into
    connected bodies, and each body is rebuilt as one OCC face per triangle, sewn into a shell
    and closed into a volume. gmsh's own STL route gives a *discrete* surface that cannot be
    written as a .brep, and gmsh 4.13 cannot read OBJ at all, so neither can be used.

Everything that is wrong with the *file* raises `ImportRefused`, which the API reports as a
422 with its message: the user can fix the file, the server has nothing to fix.
"""

import struct
import uuid
from collections.abc import Sequence
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / ".data"

CAD_EXTENSIONS = {".step", ".stp", ".iges", ".igs", ".brep"}
MESH_EXTENSIONS = {".stl", ".obj"}

MAX_TRIANGLES = 50_000
"""Above this a triangulated surface is refused rather than rebuilt. Each triangle becomes
an OCC face, so the cost grows with the count: ~8 000 take about five seconds, and the
worker serves nothing else meanwhile."""


class ImportRefused(ValueError):
    """The file cannot become a solid. The message says why, for the person who chose it."""


def process_import(filepath: str, extension: str) -> dict:
    """Run inside the gmsh worker. Reads the file, makes sure it is solid, saves a .brep.

    Returns `{"brep_path": str, "volumes": int, "bbox": [xmin, ymin, zmin, xmax, ymax, zmax]}`.
    """
    import gmsh

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    gmsh.clear()
    gmsh.model.add("import_temp")

    path, ext = Path(filepath), extension.lower()
    if ext in MESH_EXTENSIONS:
        points, triangles = (_read_stl if ext == ".stl" else _read_obj)(path)
        triangles = _checked(points, triangles, path.name)
        for body in _bodies(triangles):
            _solid_from_triangles(points, body)
    elif ext in CAD_EXTENSIONS:
        _merge_cad(path)
    else:
        raise ImportRefused(f"{ext} is not a format this importer reads.")
    gmsh.model.occ.synchronize()

    volumes = gmsh.model.getEntities(3)
    if not volumes:
        raise ImportRefused(
            "Imported model contains no 3D volumes. Ensure the file contains solid "
            "geometry, not just surfaces.")

    boxes = [gmsh.model.getBoundingBox(3, tag) for _, tag in volumes]
    bbox = (
        min(b[0] for b in boxes), min(b[1] for b in boxes), min(b[2] for b in boxes),
        max(b[3] for b in boxes), max(b[4] for b in boxes), max(b[5] for b in boxes),
    )
    brep_path = DATA_DIR / f"{uuid.uuid4().hex}.brep"
    # The OCC shapes as a .brep, so solid_model.py can re-import them cheaply on every rebuild.
    gmsh.write(str(brep_path))
    return {"brep_path": str(brep_path), "volumes": len(volumes), "bbox": bbox}


# ── CAD ─────────────────────────────────────────────────────────────────────

HEALING = {"Geometry.OCCSewFaces": 1, "Geometry.OCCMakeSolids": 1}


def _merge_cad(path: Path) -> None:
    import gmsh

    if path.stat().st_size == 0:
        raise ImportRefused(f"{path.name} is empty.")
    # Set for this read only: the worker is shared, and the build's own imports must not change.
    previous = {name: gmsh.option.getNumber(name) for name in HEALING}
    try:
        for name, value in HEALING.items():
            gmsh.option.setNumber(name, value)
        gmsh.merge(str(path))
    except Exception as failure:
        raise ImportRefused(f"{path.name} could not be read as CAD: {failure}") from failure
    finally:
        for name, value in previous.items():
            gmsh.option.setNumber(name, value)


# ── Triangulated surfaces ───────────────────────────────────────────────────

Point = tuple[float, float, float]
Triangle = tuple[int, int, int]


class _Points:
    """Vertices by position, so a corner repeated in every triangle (STL) is one point."""

    def __init__(self) -> None:
        self.points: list[Point] = []
        self._index: dict[Point, int] = {}

    def add(self, point: Sequence[float]) -> int:
        x, y, z = point
        key = (round(x, 9), round(y, 9), round(z, 9))
        if key not in self._index:
            self._index[key] = len(self.points)
            self.points.append((x, y, z))
        return self._index[key]


def _read_stl(path: Path) -> tuple[list[Point], list[Triangle]]:
    data = path.read_bytes()
    if not data.strip():
        raise ImportRefused(f"{path.name} is empty.")
    points = _Points()
    triangles: list[Triangle] = []
    count = struct.unpack_from("<I", data, 80)[0] if len(data) >= 84 else -1
    if len(data) == 84 + 50 * count:
        for n in range(count):
            values = struct.unpack_from("<12f", data, 84 + 50 * n)
            a, b, c = (points.add(values[3 + 3 * k: 6 + 3 * k]) for k in range(3))
            triangles.append((a, b, c))
    else:
        corners = []
        for line in data.decode("latin-1").splitlines():
            words = line.split()
            if words[:1] == ["vertex"]:
                corners.append(points.add([float(w) for w in words[1:4]]))
        if len(corners) % 3:
            raise ImportRefused(f"{path.name} is not a readable STL: a facet is incomplete.")
        triangles = [(corners[i], corners[i + 1], corners[i + 2])
                     for i in range(0, len(corners), 3)]
    if not triangles:
        raise ImportRefused(f"{path.name} contains no triangles.")
    return points.points, triangles


def _read_obj(path: Path) -> tuple[list[Point], list[Triangle]]:
    text = path.read_text(encoding="latin-1")
    if not text.strip():
        raise ImportRefused(f"{path.name} is empty.")
    vertices: list[Point] = []
    faces: list[list[int]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        words = line.split()
        if not words:
            continue
        try:
            if words[0] == "v":
                x, y, z = (float(w) for w in words[1:4])
                vertices.append((x, y, z))
            elif words[0] == "f":
                # "f 1 2 3", "f 1/1 2/2 3/3" or "f 1//1 ..."; negative indices count from the end.
                indices = [int(w.split("/")[0]) for w in words[1:]]
                faces.append([i - 1 if i > 0 else len(vertices) + i for i in indices])
        except ValueError as failure:
            raise ImportRefused(f"{path.name}, line {number}: {failure}") from failure
    if not faces:
        raise ImportRefused(f"{path.name} contains no faces.")
    points = _Points()
    triangles: list[Triangle] = []
    for face in faces:
        if len(face) < 3 or not all(0 <= i < len(vertices) for i in face):
            raise ImportRefused(f"{path.name} has a face that names a vertex it does not have.")
        corners = [points.add(vertices[i]) for i in face]
        # A polygon is split into a fan; OBJ faces are planar and convex by convention.
        triangles += [(corners[0], corners[k], corners[k + 1]) for k in range(1, len(corners) - 1)]
    return points.points, triangles


def _checked(points: list[Point], triangles: list[Triangle], name: str) -> list[Triangle]:
    triangles = [t for t in triangles if len(set(t)) == 3]
    if len(triangles) > MAX_TRIANGLES:
        raise ImportRefused(
            f"{name} has {len(triangles)} triangles; more than {MAX_TRIANGLES} cannot be "
            "rebuilt into a solid here. Reduce the mesh, or export the model as STEP.")
    edges: dict[tuple[int, int], int] = {}
    for a, b, c in triangles:
        for edge in ((a, b), (b, c), (c, a)):
            key = (min(edge), max(edge))
            edges[key] = edges.get(key, 0) + 1
    open_edges = sum(1 for count in edges.values() if count != 2)
    if open_edges:
        raise ImportRefused(
            f"{name} is not closed: {open_edges} edge(s) are not shared by exactly two "
            "triangles. Only a watertight surface encloses a solid; close the holes and "
            "export it again.")
    return triangles


def _bodies(triangles: list[Triangle]) -> list[list[Triangle]]:
    """Triangles grouped into connected pieces, one future volume each."""
    parent: dict[int, int] = {}

    def root(i: int) -> int:
        parent.setdefault(i, i)
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b, c in triangles:
        parent[root(b)] = root(a)
        parent[root(c)] = root(a)
    groups: dict[int, list[Triangle]] = {}
    for triangle in triangles:
        groups.setdefault(root(triangle[0]), []).append(triangle)
    return list(groups.values())


def _solid_from_triangles(points: list[Point], triangles: list[Triangle]) -> int:
    import gmsh

    occ = gmsh.model.occ
    tags: dict[int, int] = {}
    lines: dict[tuple[int, int], int] = {}

    def point(i: int) -> int:
        if i not in tags:
            tags[i] = occ.addPoint(*points[i])
        return tags[i]

    def line(a: int, b: int) -> int:
        key = (min(a, b), max(a, b))
        if key not in lines:
            lines[key] = occ.addLine(point(key[0]), point(key[1]))
        return lines[key] if key[0] == a else -lines[key]

    faces = [occ.addPlaneSurface([occ.addCurveLoop([line(a, b), line(b, c), line(c, a)])])
             for a, b, c in triangles]
    return occ.addVolume([occ.addSurfaceLoop(faces, sewing=True)])
