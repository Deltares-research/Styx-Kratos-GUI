"""Which part of the model an element belongs to, and what a phase did to it.

GiD names a mesh block `Kratos_Triangle2D6_Mesh_2`. That is a block index and an element
type, and it says nothing about whether the block is the top soil layer, the third
excavation lift or the sheet pile. The names live in the `.mdpa` in the same run
directory, and the join between the two is exact rather than approximate: both files
carry Kratos' own element ids, so this module is a lookup and never a guess.

Parsing the `.mdpa` is `core.mdpa_import`'s job, not repeated here. (That parser could
not read a deck this project had written until P1 -- see
`tests/test_mdpa_import.test_blank_lines_inside_a_block_are_skipped` and
`tests/test_calculate.test_the_deck_lands_on_disk_as_the_bytes_it_was_rendered_as` for
the two defects that combined to cause it.)

── Absent is two different things ───────────────────────────────────────────

A part with no elements in a stage's mesh is one of:

*   **deactivated by that phase.** Kratos writes the block and leaves it empty. This is
    how a staged result recovers the construction sequence -- no phase record is
    consulted and none is needed. Verified against a real seven-stage excavation run, where
    the three excavation lifts drop out at stages 4, 6 and 7 exactly as the phase names
    say they should.
*   **never written by this output at all.** The GiD writer emits only the element types
    it has a geometry for, and it has none for
    `Geo_UPwLineInterfacePlaneStrainDiffOrderElement3Plus3N`. The interfaces are in the
    deck, they are solved, and they appear in none of the seven stages.

Calling the second "removed in this phase" would be a false statement about the model,
so the two are kept apart. Telling them apart needs the whole run rather than one stage
-- hence `written_parts`, and hence `StagePart.written` being `None` when nobody asked.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field

from core.gid_results import GidMesh
from core.mdpa_import import MdpaModel


@dataclass
class StagePart:
    """One named part of the deck, as one stage of the run saw it."""

    name: str
    kind: str
    """From `mdpa_import.Part`: "body", "load", "boundary", "support" or "group"."""
    declared: int
    """How many elements the deck gives this part, in every stage."""
    nodes: int
    elements: list[int] = dataclass_field(default_factory=list)
    """Of those, the ones this stage's mesh actually contains."""

    @property
    def alive(self) -> bool | None:
        """Whether this part is in the model during this stage.

        `None` for a part that owns no elements -- a support, a boundary, a node group.
        Aliveness is not a question about those, and answering `False` would put them
        in the explorer greyed out as though a phase had removed them.
        """
        if not self.declared:
            return None
        return bool(self.elements)

    written: bool | None = None
    """Whether the GiD output writes this part's elements anywhere in the run.

    `None` covers the two ways the question does not apply: nobody asked (`stage_parts`
    was given one stage, and one stage cannot answer it), and the part owns no elements
    to write -- a support, a boundary, a node group. `False` is a real answer, and it
    means this output format has no geometry for the part's element type, not that a
    phase removed it. See the module docstring.
    """


def element_owner(model: MdpaModel) -> dict[int, str]:
    """Element id -> the name of the part that owns it.

    Only parts that own elements are considered, so a node set does not lay claim to
    the elements its nodes happen to belong to.

    Checked against a real staged deck, where no element is claimed by two parts: the
    staged split gives every lift its own body. Should a deck ever overlap them, the
    first part in file order wins, which is the deck's own outermost grouping.
    """
    owner: dict[int, str] = {}
    for part in model.parts.values():
        for element in part.elements:
            owner.setdefault(element, part.name)
    return owner


def written_parts(model: MdpaModel, meshes: list[GidMesh]) -> set[str]:
    """The parts the GiD output writes at least one element of, anywhere in the run.

    A fact about the whole run, which is why it takes every stage's mesh. What it is
    for is the one distinction a single stage cannot make: a part missing from this
    stage because the phase removed it, against a part missing from every stage because
    this output format has no geometry for its element type.
    """
    present: set[int] = set()
    for mesh in meshes:
        for block in mesh.blocks:
            present.update(block.elements)
    return {part.name for part in model.parts.values()
            if any(element in present for element in part.elements)}


def stage_parts(model: MdpaModel, mesh: GidMesh,
                written: set[str] | None = None) -> list[StagePart]:
    """Every named part of the deck, with the elements this stage's mesh has for it.

    In the deck's own declaration order, which is the order the model was built in and
    so the order a reader expects to find things in.
    """
    present = {element for block in mesh.blocks for element in block.elements}
    return [
        StagePart(
            name=part.name,
            kind=part.kind,
            declared=len(part.elements),
            nodes=len(part.nodes),
            elements=[element for element in part.elements if element in present],
            # A part with no elements has nothing for GiD to write or not write, so the
            # question does not apply to it -- the same reasoning as `alive`. Reported
            # as False, every support and boundary in the deck would read as something
            # this output cannot show.
            written=None if written is None or not part.elements
            else part.name in written,
        )
        for part in model.parts.values()
    ]
