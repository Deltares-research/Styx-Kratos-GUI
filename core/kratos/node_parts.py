"""Which SubModelParts each node of a deck is in.

Read off the `.mdpa` text itself -- the one `core.kratos.writer` writes for the open project, or
any other -- with `core.kratos.mdpa_reader`, so a part's name and a node's number are exactly
what Kratos is given. Nothing is derived from the project: an interface split, a staged
lift, a load's own sub-model part are all whatever the deck says they are.

The payload is the node table and, per part, the nodes it names. The browser inverts that
into node -> parts (frontend/js/node-parts.js); sending it the other way round would repeat
every part name once per node.
"""

from __future__ import annotations

from core.kratos import mdpa_reader


def node_parts(mdpa_text: str) -> dict:
    """`{"nodes": [[id, x, y, z], ...], "parts": [{"name", "kind", "nodes"}, ...]}`,
    nodes in id order and parts in deck order, each part's nodes as the deck lists them.
    """
    return of_model(mdpa_reader.import_mdpa(mdpa_text))


def of_model(model: mdpa_reader.MdpaModel) -> dict:
    """`node_parts` for a deck already parsed -- what the `.mdpa` import route has."""
    return {
        "nodes": [[node, *model.nodes[node]] for node in sorted(model.nodes)],
        "parts": [{"name": part.name, "kind": part.kind, "nodes": list(part.nodes)}
                  for part in model.parts.values()],
    }
