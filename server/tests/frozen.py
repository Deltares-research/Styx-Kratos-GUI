"""Read values back out of the base UI's sample data so tests can assert against them.

`live/base/js/data.js` is never edited. These helpers parse it so test_parity.py can prove
the Python seed project still agrees.
"""

import re
from pathlib import Path

DATA_JS = Path(__file__).resolve().parents[2] / "live" / "base" / "js" / "data.js"

_NUMBER = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"


def _object_literals(src: str, array_name: str) -> list[str]:
    """Return the raw text of each `{...}` entry in `App.<array_name> = [ ... ];`."""
    # Anchor on the assignment, not the bare name: helper functions in js/data.js
    # also mention App.LAYERS / App.MATERIALS, and matching one of those reads the
    # wrong bracket and silently parses nothing.
    start = src.index(f"App.{array_name} = [")
    depth, begin = 0, src.index("[", start)
    for i in range(begin, len(src)):
        if src[i] == "[":
            depth += 1
        elif src[i] == "]":
            depth -= 1
            if depth == 0:
                body = src[begin + 1 : i]
                break
    else:  # pragma: no cover - malformed source
        raise AssertionError(f"unterminated App.{array_name}")

    entries, depth, begin = [], 0, None
    for i, ch in enumerate(body):
        if ch == "{":
            if depth == 0:
                begin = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                entries.append(body[begin : i + 1])
    return entries


def _fields(literal: str) -> dict[str, str]:
    return {k: v.strip() for k, v in re.findall(r"(\w+)\s*:\s*('[^']*'|[^,{}]+)", literal)}


def boreholes() -> list[dict]:
    src = DATA_JS.read_text(encoding="utf-8")
    out = []
    for lit in _object_literals(src, "BOREHOLES"):
        f = _fields(lit)
        out.append(
            dict(
                id=f["id"].strip("'"),
                name=f["name"].strip("'"),
                x=float(f["x"]), y=float(f["y"]),
                head=float(f["head"]), water=float(f["water"]),
            )
        )
    return out


def layers() -> list[dict]:
    src = DATA_JS.read_text(encoding="utf-8")
    out = []
    for lit in _object_literals(src, "LAYERS"):
        def levels(kind: str) -> dict[str, float]:
            block = re.search(rf"{kind}\s*:\s*\{{([^}}]*)\}}", lit).group(1)
            return {
                bh: float(z)
                for bh, z in re.findall(rf"(\w+)\s*:\s*({_NUMBER})", block)
            }

        head = lit[: lit.index("tops")]
        f = _fields(head)
        out.append(
            dict(
                id=f["id"].strip("'"),
                name=f["name"].strip("'"),
                mat=f["mat"].strip("'"),
                tops=levels("tops"),
                bots=levels("bots"),
            )
        )
    return out


def materials() -> list[dict]:
    src = DATA_JS.read_text(encoding="utf-8")
    out = []
    for lit in _object_literals(src, "MATERIALS"):
        f = _fields(lit)

        def num(key: str):
            raw = f[key].strip()
            return None if raw == "null" else float(raw)

        out.append(
            dict(
                id=f["id"].strip("'"), name=f["name"].strip("'"),
                model=f["model"].strip("'"), type=f["type"].strip("'"),
                color=f["color"].strip("'"),
                g_unsat=num("gUnsat"), g_sat=num("gSat"),
                E=num("E"), nu=num("nu"), c=num("c"), phi=num("phi"), k=num("k"),
                r_inter=num("rInter"),
                interface_permeability=f["interfacePerm"].strip("'"),
            )
        )
    return out
