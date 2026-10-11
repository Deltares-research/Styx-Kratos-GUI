"""GiD's ASCII post files, read back.

A Kratos deck written by `core.kratos_processes` carries one `GiDOutputProcess` per
stage, which leaves two files beside the deck: `<problem>.post.msh`, the mesh as that
stage saw it, and `<problem>.post.res`, the results on it. This module turns both into
tables and stops there. It has no opinion about what a number means -- which quantities
a user may ask for, in what unit, with which sign -- because that is a question about
geotechnics rather than about a file format, and it lives in `core.result_fields`.

Reading these rather than adding a VTK writer is a decision, not an accident: the
deck's output block is part of what is compared against a validated reference stage
for stage, and a second writer would change a deck that is
currently known-good (`plan/active/postprocessing-plan.md`, decision 1.1).

── The two things about this format that are easy to get wrong ──────────────

**An element row ends in its Properties id.** `11 1 2 3 4 5 6 3` is a six-node triangle
in property set 3, not a seven-node element. Read the last number as a node and you get
a connectivity that still refers to real coordinates somewhere else in the mesh, so
nothing downstream fails -- it just draws the wrong shape.

**A Gauss row spans several lines.** The first carries the element id and the first
integration point; every remaining point of that element follows on a bare line with no
id:

    11 -44314.5 -85354.7 -45373.9 -702.893 0 0
     -44110.3 -84816.3 -45029.7 -587.065 0 0
     -40413.7 -78864.8 -41333.5 -473.357 0 0

A reader that takes the first token as an id sees three elements, two of them numbered
-44110 and -40413. The discriminator used here is the token count -- a starting row has
one more number than a continuation row -- cross-checked against the point count the
file's own `GaussPoints` block declares.

── Empty is a real answer ───────────────────────────────────────────────────

A stage writes an element block with nothing in it for a body that phase deactivated,
and a `Values` block with nothing in it for a variable the element does not implement
(the beam does not compute `CAUCHY_STRESS_TENSOR` on its integration points, and the
runs on this machine all carry an empty `lin2_element_gp` block saying so). Neither is
corruption, and the difference between "empty" and "absent" is what lets the field
catalogue offer only what is really there.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dataclass_field

COMPONENTS = {"scalar": 1, "vector": 3, "matrix": 6}
"""How many numbers a result type puts on a row. A `Matrix` is the six independent
components of a symmetric tensor, in GiD's order: xx yy zz xy yz xz."""

MESH_HEADER = re.compile(
    r'^MESH\s+"(?P<name>[^"]*)"\s+dimension\s+(?P<dimension>\d+)\s+'
    r'ElemType\s+(?P<type>\w+)\s+Nnode\s+(?P<nnode>\d+)', re.IGNORECASE)

GAUSS_HEADER = re.compile(
    r'^GaussPoints\s+"(?P<name>[^"]*)"\s+ElemType\s+(?P<type>\w+)', re.IGNORECASE)

GAUSS_COUNT = re.compile(r"^Number\s+Of\s+Gauss\s+Points:\s*(\d+)", re.IGNORECASE)

RESULT_HEADER = re.compile(
    r'^Result\s+"(?P<variable>[^"]*)"\s+"(?P<analysis>[^"]*)"\s+(?P<time>\S+)\s+'
    r'(?P<kind>\w+)\s+On(?P<location>Nodes|GaussPoints)'
    r'(?:\s+"(?P<gauss>[^"]*)")?', re.IGNORECASE)


# ── The mesh ────────────────────────────────────────────────────────────────

@dataclass
class Block:
    """One `MESH` block: the elements of one Kratos sub-model part, all of one type.

    `name` is GiD's own (`Kratos_Triangle2D6_Mesh_2`) and says nothing about which part
    of the project it is. That join is made through the `.mdpa` in the same directory --
    see `core.result_fields.parts_of`.
    """
    name: str
    element_type: str
    nnode: int
    dimension: int
    elements: dict[int, list[int]] = dataclass_field(default_factory=dict)
    properties: dict[int, int] = dataclass_field(default_factory=dict)


@dataclass
class GidMesh:
    nodes: dict[int, tuple[float, float, float]] = dataclass_field(default_factory=dict)
    blocks: list[Block] = dataclass_field(default_factory=list)

    @property
    def dimension(self) -> int:
        """2 for a plane-strain section, 3 otherwise -- as the blocks declare it.

        Taken from the file rather than inferred from the coordinates: a 3D model that
        happens to be flat at this moment would otherwise be read as a section.
        """
        return max((block.dimension for block in self.blocks), default=3)

    def connectivity(self, element: int) -> list[int] | None:
        """One element's nodes, without the caller having to know its block. `None`
        for an id the mesh does not have, which is the normal answer while a result
        file and a mesh file are being checked against each other."""
        for block in self.blocks:
            found = block.elements.get(element)
            if found is not None:
                return found
        return None

    def block_of(self, element: int) -> Block | None:
        for block in self.blocks:
            if element in block.elements:
                return block
        return None

    def elements(self) -> dict[int, list[int]]:
        """Every element in the mesh, flattened. Built on demand rather than kept: the
        blocks are the truth, and a second copy would have to be kept in step."""
        out: dict[int, list[int]] = {}
        for block in self.blocks:
            out.update(block.elements)
        return out


def read_mesh(text: str) -> GidMesh:
    """Parse a `.post.msh`.

    One pass, line by line. `Coordinates` appears in the first block only and fills a
    single global node table that every later block refers to.
    """
    mesh = GidMesh()
    block: Block | None = None
    section = None  # None | "coordinates" | "elements"

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        header = MESH_HEADER.match(stripped)
        if header:
            block = Block(name=header["name"], element_type=header["type"],
                          nnode=int(header["nnode"]),
                          dimension=int(header["dimension"]))
            mesh.blocks.append(block)
            section = None
            continue

        lowered = stripped.lower()
        if lowered.startswith("end "):
            section = None
            continue
        if lowered == "coordinates":
            section = "coordinates"
            continue
        if lowered == "elements":
            section = "elements"
            continue

        if section == "coordinates":
            parts = stripped.split()
            if len(parts) >= 4:
                mesh.nodes[int(parts[0])] = (float(parts[1]), float(parts[2]),
                                             float(parts[3]))
        elif section == "elements" and block is not None:
            parts = stripped.split()
            # id, then `nnode` nodes, then the Properties id. Anything shorter is not
            # an element row and is skipped rather than guessed at.
            if len(parts) >= block.nnode + 1:
                element = int(parts[0])
                block.elements[element] = [int(p) for p in parts[1:1 + block.nnode]]
                if len(parts) > block.nnode + 1:
                    block.properties[element] = int(parts[1 + block.nnode])
    return mesh


# ── The results ─────────────────────────────────────────────────────────────

@dataclass
class GaussSet:
    """One `GaussPoints` declaration. `count` is the only part anything here uses, and
    it is what makes the continuation lines readable -- see the module docstring."""
    name: str
    element_type: str
    count: int = 1


@dataclass
class Field:
    """One `Result` block.

    `values` is keyed by node id for a nodal field and by element id for a Gauss field,
    and the two shapes differ deliberately: a nodal entry is one list of components, a
    Gauss entry is a list of those, one per integration point. Nothing collapses the
    second into the first here, because averaging a tensor and then deriving q from it
    is not the same number as deriving q at each point and averaging that -- and the
    second is the right one. `core.result_fields` does it in that order.
    """
    variable: str
    kind: str          # "scalar" | "vector" | "matrix"
    location: str      # "nodes" | "gauss"
    time: float
    gauss_set: str | None = None
    values: dict = dataclass_field(default_factory=dict)

    @property
    def components(self) -> int:
        return COMPONENTS.get(self.kind, 1)


@dataclass
class Results:
    gauss_sets: dict[str, GaussSet] = dataclass_field(default_factory=dict)
    blocks: list[Field] = dataclass_field(default_factory=list)

    def all_fields(self) -> list[Field]:
        return list(self.blocks)

    def fields_named(self, variable: str) -> list[Field]:
        """Every block for one variable. There can be more than one: a variable written
        on Gauss points is written once per element type, so `CAUCHY_STRESS_TENSOR`
        appears for the triangles and again for the beam."""
        return [f for f in self.blocks if f.variable == variable]

    def field(self, variable: str, gauss_set: str | None = None) -> Field | None:
        """The variable as the stage left it, or `None` -- which is the normal answer,
        not an exception.

        Two things make that more than "the block called `variable`":

        * **Steps.** A stage cut into sub-steps on non-convergence writes one block per
          step. The stage's result is its *last* step with values -- the latest time,
          and for equal times the later block in the file. An empty last step is a
          write that was cut off (a killed run), and the step before it is what there
          is to see; a set that is empty at every step stays empty.
        * **Gauss sets.** A Gauss variable is written once per element type, so with no
          `gauss_set` the last step of every set is merged into one table keyed by
          element id. An empty set -- the beam's `lin2_element_gp` declaring it has no
          stresses -- adds nothing and hides nothing.
        """
        latest: dict[str | None, tuple[tuple[bool, float, int], int, Field]] = {}
        for index, block in enumerate(self.blocks):
            if block.variable != variable:
                continue
            if gauss_set is not None and block.gauss_set != gauss_set:
                continue
            key = (bool(block.values), block.time, index)
            if block.gauss_set not in latest or key > latest[block.gauss_set][0]:
                latest[block.gauss_set] = (key, index, block)
        if not latest:
            return None
        last = [block for _, _, block in sorted(latest.values(), key=lambda t: t[1])]
        filled = [block for block in last if block.values]
        if len(filled) <= 1:
            return filled[0] if filled else last[-1]
        first = filled[0]
        merged = Field(variable=variable, kind=first.kind, location=first.location,
                       time=max(block.time for block in filled), gauss_set=None)
        for block in filled:
            merged.values.update(block.values)
        return merged

    def variables(self) -> set[str]:
        return {f.variable for f in self.blocks}


def read_results(text: str) -> Results:
    """Parse a `.post.res`."""
    out = Results()
    gauss: GaussSet | None = None
    current: Field | None = None
    in_values = False
    last_element: int | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        header = GAUSS_HEADER.match(stripped)
        if header:
            gauss = GaussSet(name=header["name"], element_type=header["type"])
            out.gauss_sets[gauss.name] = gauss
            continue
        if gauss is not None:
            count = GAUSS_COUNT.match(stripped)
            if count:
                gauss.count = int(count[1])
                continue
        if stripped.lower().startswith("end gausspoints"):
            gauss = None
            continue
        if gauss is not None:
            # Inside a GaussPoints block: "Natural Coordinates: Given" and the
            # coordinates after it. Nothing here needs them -- the values are read
            # per point in file order, and where the points sit inside the element
            # only matters to a true shape-function extrapolation, which this is not.
            continue

        header = RESULT_HEADER.match(stripped)
        if header:
            current = Field(
                variable=header["variable"],
                kind=header["kind"].lower(),
                location="nodes" if header["location"].lower() == "nodes" else "gauss",
                time=_number(header["time"]),
                gauss_set=header["gauss"],
            )
            out.blocks.append(current)
            in_values = False
            last_element = None
            continue

        lowered = stripped.lower()
        if lowered == "values":
            in_values = True
            last_element = None
            continue
        if lowered.startswith("end values"):
            in_values = False
            current = None
            continue

        if not in_values or current is None:
            continue

        parts = stripped.split()
        if current.location == "nodes":
            if len(parts) >= current.components + 1:
                current.values[int(parts[0])] = [float(p) for p in
                                                 parts[1:1 + current.components]]
            continue

        # Gauss: a row with one more number than there are components starts a new
        # element; one with exactly as many continues the element before it.
        if len(parts) == current.components:
            if last_element is not None:
                current.values[last_element].append([float(p) for p in parts])
        elif len(parts) >= current.components + 1:
            last_element = int(parts[0])
            current.values[last_element] = [[float(p) for p in
                                             parts[1:1 + current.components]]]
    return out


def _number(token: str) -> float:
    try:
        return float(token)
    except ValueError:
        return 0.0
