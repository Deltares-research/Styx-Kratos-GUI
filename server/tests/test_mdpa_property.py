"""`app.mdpa_import`, against decks generated at random (plan sec 4.4, sec 9).

Hand-written fixtures pin the cases somebody thought of. This writes random small decks
-- any node count, triangles over those nodes, sub-model parts (some nested) over both,
optional blank lines and comments in the places a hand-edited file has them -- and
reads each one back: what comes out must be exactly what went in.
"""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from app import mdpa_import

ELEMENT = "UPwSmallStrainElement2D3N"
COORD = st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False)
NAME = st.from_regex(r"[A-Z][A-Za-z0-9_]{0,10}", fullmatch=True)


@st.composite
def decks(draw):
    n_nodes = draw(st.integers(min_value=3, max_value=25))
    nodes = {i: (draw(COORD), draw(COORD), 0.0) for i in range(1, n_nodes + 1)}
    node_ids = list(nodes)
    n_elements = draw(st.integers(min_value=1, max_value=15))
    elements = {e: draw(st.lists(st.sampled_from(node_ids), min_size=3, max_size=3))
                for e in range(1, n_elements + 1)}
    names = draw(st.lists(NAME, min_size=0, max_size=4, unique=True))
    parts = {}
    for name in names:
        parts[name] = {
            "nodes": draw(st.lists(st.sampled_from(node_ids), unique=True, max_size=8)),
            "elements": draw(st.lists(st.sampled_from(list(elements)), unique=True,
                                      max_size=5)),
            "child": draw(st.one_of(st.none(), NAME.filter(lambda n: n not in names))),
        }
    noise = draw(st.booleans())
    return nodes, elements, parts, noise


def write(nodes, elements, parts, noise) -> str:
    blank = [""] if noise else []
    lines = ["// generated" if noise else "", "Begin Properties 1", "End Properties"]
    lines += ["Begin Nodes"] + blank
    lines += [f"{i} {x!r} {y!r} {z!r}" for i, (x, y, z) in nodes.items()]
    lines += ["End Nodes", f"Begin Elements {ELEMENT}"]
    lines += [f"{e} 1 {a} {b} {c}" + ("  // tri" if noise else "")
              for e, (a, b, c) in elements.items()]
    lines += ["End Elements"]
    for name, part in parts.items():
        lines += [f"Begin SubModelPart {name}", "  Begin SubModelPartNodes"] + blank
        lines += [f"  {n}" for n in part["nodes"]]
        lines += ["  End SubModelPartNodes", "  Begin SubModelPartElements"]
        lines += [f"  {e}" for e in part["elements"]]
        lines += ["  End SubModelPartElements"]
        if part["child"]:
            lines += [f"  Begin SubModelPart {part['child']}", "    Begin SubModelPartNodes"]
            lines += [f"    {n}" for n in part["nodes"][:2]]
            lines += ["    End SubModelPartNodes", "  End SubModelPart"]
        lines += ["End SubModelPart"] + blank
    return "\n".join(lines) + "\n"


@settings(max_examples=150, deadline=None)
@given(decks())
def test_a_random_deck_reads_back_as_written(deck):
    nodes, elements, parts, noise = deck

    model = mdpa_import.import_mdpa(write(nodes, elements, parts, noise))

    assert model.nodes == nodes
    (entity,) = model.elements
    assert entity.kratos_class == ELEMENT
    assert entity.entries == {e: list(conn) for e, conn in elements.items()}
    expected_names = set(parts) | {f"{n}.{p['child']}" for n, p in parts.items() if p["child"]}
    assert set(model.parts) == expected_names
    for name, part in parts.items():
        assert model.parts[name].nodes == part["nodes"]
        assert model.parts[name].elements == part["elements"]
        if part["child"]:
            assert model.parts[f"{name}.{part['child']}"].nodes == part["nodes"][:2]


@settings(max_examples=100, deadline=None)
@given(decks())
def test_crlf_and_lf_decks_read_the_same(deck):
    text = write(*deck)

    assert (mdpa_import.import_mdpa(text.replace("\n", "\r\n")).to_dict()
            == mdpa_import.import_mdpa(text).to_dict())
