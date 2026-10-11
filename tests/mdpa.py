"""A minimal .mdpa reader, used to assert on what the exporter writes.

Deliberately independent of `core.kratos.export`: it re-derives the file's meaning from the
text, so a test that passes says the *file* is right rather than that two copies of the
same helper agree. It also parses GiD's reference decks in the repo root, which is how
the format's invariants were established in the first place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re


@dataclass
class Block:
    name: str
    """The Kratos element or condition class, e.g. SmallStrainUPwDiffOrderElement2D6N."""
    entries: dict[int, list[int]] = field(default_factory=dict)
    """id -> connectivity, in file order."""
    properties: dict[int, int] = field(default_factory=dict)


@dataclass
class Part:
    name: str
    nodes: list[int] = field(default_factory=list)
    elements: list[int] = field(default_factory=list)
    conditions: list[int] = field(default_factory=list)
    data: dict[str, list[float]] = field(default_factory=dict)
    """Variable name -> value, from a SubModelPartData block. A scalar becomes a
    one-item list, so callers do not need two shapes to check."""


@dataclass
class Deck:
    nodes: dict[int, tuple[float, float, float]] = field(default_factory=dict)
    elements: list[Block] = field(default_factory=list)
    conditions: list[Block] = field(default_factory=list)
    parts: dict[str, Part] = field(default_factory=dict)
    properties: list[int] = field(default_factory=list)

    def element(self, element_id: int) -> list[int]:
        for block in self.elements:
            if element_id in block.entries:
                return block.entries[element_id]
        raise KeyError(element_id)

    def element_ids(self) -> list[int]:
        return [i for block in self.elements for i in block.entries]

    def condition_ids(self) -> list[int]:
        return [i for block in self.conditions for i in block.entries]


def parse(text: str) -> Deck:
    deck = Deck()
    lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not line.startswith("Begin "):
            continue
        head = line.split()
        if head[1] == "Properties":
            deck.properties.append(int(head[2]))
        elif head[1] == "Nodes":
            index = _nodes(lines, index, deck)
        elif head[1] == "Elements":
            index = _connectivity(lines, index, deck.elements, head[2])
        elif head[1] == "Conditions":
            index = _connectivity(lines, index, deck.conditions, head[2])
        elif head[1] == "SubModelPart":
            index = _part(lines, index, deck, head[2])
    return deck


def _nodes(lines: list[str], index: int, deck: Deck) -> int:
    while lines[index] != "End Nodes":
        parts = lines[index].split()
        deck.nodes[int(parts[0])] = tuple(float(v) for v in parts[1:4])
        index += 1
    return index + 1


def _connectivity(lines: list[str], index: int, into: list[Block], name: str) -> int:
    block = Block(name=name)
    while not lines[index].startswith("End "):
        values = [int(v) for v in lines[index].split()]
        block.entries[values[0]] = values[2:]
        block.properties[values[0]] = values[1]
        index += 1
    into.append(block)
    return index + 1


VECTOR_DATA = re.compile(r"(\w+)\s*\[\d+\]\s*\(([^)]*)\)")


def _part(lines: list[str], index: int, deck: Deck, name: str) -> int:
    part = Part(name=name)
    field_of = {"SubModelPartNodes": part.nodes, "SubModelPartElements": part.elements,
                "SubModelPartConditions": part.conditions}
    while lines[index] != "End SubModelPart":
        line = lines[index]
        index += 1
        match = re.fullmatch(r"Begin (SubModelPart\w+)", line)
        if not match:
            continue
        if match.group(1) == "SubModelPartData":
            index = _part_data(lines, index, part)
            continue
        target = field_of[match.group(1)]
        while not lines[index].startswith("End "):
            target.append(int(lines[index]))
            index += 1
        index += 1
    deck.parts[name] = part
    return index + 1


def _part_data(lines: list[str], index: int, part: Part) -> int:
    while not lines[index].startswith("End "):
        line = lines[index]
        index += 1
        vector = VECTOR_DATA.fullmatch(line)
        if vector:
            name, values = vector.groups()
            part.data[name] = [float(v) for v in values.split(",")]
        else:
            name, value = line.split(maxsplit=1)
            part.data[name] = [float(value)]
    return index + 1
