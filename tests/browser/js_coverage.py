"""Function coverage of the live modules, from Chrome's precise coverage
(`Profiler.takePreciseCoverage` with `detailed: false`, so one count per function).

Collected by the browser unit suite when pytest runs with `--js-coverage`; written to
`htmlcov-js/summary.json` and printed as a Markdown table.
"""

from __future__ import annotations

import posixpath
from urllib.parse import unquote, urlparse

LIVE_DIR = "/frontend/js/"
"""The suite page is opened from disk (`frontend/tests/index.html`), so the live modules
arrive as file URLs into `frontend/js/`, not as the server's `/live/js/`."""


def _module(url: str) -> str | None:
    path = unquote(urlparse(url).path)
    return posixpath.basename(path) if LIVE_DIR in path else None


def summarise(entries: list[dict]) -> dict[str, dict]:
    calls: dict[str, dict[int, tuple[str, int]]] = {}
    for entry in entries:
        module = _module(entry.get("url", ""))
        if module is None:
            continue
        functions = calls.setdefault(module, {})
        for function in entry.get("functions", []):
            start = function["ranges"][0]["startOffset"]
            name = function["functionName"]
            if start == 0 and not name:
                continue      # the script body, not a function anyone wrote
            seen = functions.get(start, (name, 0))[1]
            functions[start] = (name, seen + function["ranges"][0]["count"])

    summary = {}
    for module, functions in sorted(calls.items()):
        missed = [name or f"(anonymous @{start})"
                  for start, (name, count) in sorted(functions.items()) if count == 0]
        total = len(functions)
        covered = total - len(missed)
        summary[module] = {"functions": total, "covered": covered,
                           "percent": round(100.0 * covered / total, 1) if total else 100.0,
                           "missed": missed}
    return summary


def below(summary: dict[str, dict], target: float) -> list[str]:
    under = [(row["percent"], module) for module, row in summary.items()
             if row["percent"] < target]
    return [module for _, module in sorted(under)]


def table(summary: dict[str, dict]) -> str:
    lines = ["| Module | Functions | Covered | Coverage |", "|---|---|---|---|"]
    functions = covered = 0
    for module, row in summary.items():
        lines.append(f"| `{module}` | {row['functions']} | {row['covered']} | "
                     f"{row['percent']:.1f} % |")
        functions += row["functions"]
        covered += row["covered"]
    percent = 100.0 * covered / functions if functions else 100.0
    lines.append(f"| **total** | {functions} | {covered} | {percent:.1f} % |")
    return "\n".join(lines)
