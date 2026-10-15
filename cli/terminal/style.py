"""Colour for a person at a terminal, and none for a pipe or a file.

Colour only adds escape codes around text that is already there: `plain` takes them out
again and gives, character for character, what a pipe gets. So a script reading the
output sees no difference, and neither does a test.

There is colour when the stream is a terminal (not `TERM=dumb`), `FORCE_COLOR` gives it
to a pipe as well, and `NO_COLOR` (https://no-color.org) takes it away everywhere. On
Windows the console is asked to read escape codes first; one that cannot gets none.

`answer` colours the lines a command answers with, by their shape, the same for every
command: a line with indented lines under it is a heading, the label of an indented
line and the id at the start of a row stand out, what is said in brackets at the end of
a line is quieter, `ok:` and `wrote` are green, and a command to type (in backticks) is
marked.
"""

from __future__ import annotations

import os
import re
import sys

CODES = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33",
         "blue": "34", "magenta": "35", "cyan": "36"}
RESET = "\033[0m"
ESCAPE = re.compile("\033\\[[0-9;]*m")


def enabled(stream) -> bool:
    """Whether what is written to `stream` is coloured."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    isatty = getattr(stream, "isatty", None)
    try:
        if isatty is None or not isatty():
            return False
    except ValueError:                              # a closed stream
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return _reads_escape_codes(stream)


def _reads_escape_codes(stream) -> bool:
    """Windows: switch the console to reading escape codes, and say whether it does."""
    if sys.platform != "win32":                     # what mypy, checking as Linux, reads
        return True
    try:
        import ctypes
        import msvcrt
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        handle = msvcrt.get_osfhandle(stream.fileno())
        mode = wintypes.DWORD()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        vt = 0x0004                                 # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return bool(mode.value & vt) or bool(kernel32.SetConsoleMode(handle, mode.value | vt))
    except (AttributeError, OSError, ValueError):
        return False


def paint(text: str, style: str, on: bool) -> str:
    """`text` in `style` -- words of CODES, `"bold red"` -- when `on`."""
    if not on or not text:
        return text
    return f"\033[{';'.join(CODES[word] for word in style.split())}m{text}{RESET}"


def plain(text: str) -> str:
    """`text` without its colour."""
    return ESCAPE.sub("", text)


# ── An answer's lines ───────────────────────────────────────────────────────

_TRAILING = re.compile(r"(?P<gap>\s{2,})(?P<aside>\([^()]*\))$")
_LABEL = re.compile(r"(?P<indent>\s+)(?P<label>\S+)(?=\s{2,}|$)|(?P<indent2>\s+)(?P<key>\S+:)(?=\s)")
_ID = re.compile(r"(?P<id>\S+)(?=\s{2,})")
_MARKED = re.compile(r"`[^`\n]+`|\bwrote\b")


def answer(lines: list[str], on: bool) -> list[str]:
    """The lines of an answer, coloured by their shape when `on`."""
    if not on:
        return list(lines)
    out = []
    for at, line in enumerate(lines):
        following = lines[at + 1] if at + 1 < len(lines) else ""
        heading = bool(line) and not line[0].isspace() and following[:1].isspace()
        out.append(_line(line, heading))
    return out


def _line(line: str, heading: bool) -> str:
    body, gap, aside = line, "", ""
    trailing = _TRAILING.search(line)
    if trailing and trailing.start() > 0:
        body, gap, aside = line[:trailing.start()], trailing["gap"], trailing["aside"]
    if heading:
        return paint(body, "bold", True) + gap + paint(aside, "dim", True)
    return _lead(body) + gap + paint(aside, "dim", True)


def _lead(body: str) -> str:
    """The start of a line that is not a heading -- `ok:`, a label, an id -- and the
    rest with its marks."""
    if body.startswith("ok:"):
        return paint("ok:", "bold green", True) + _marked(body[3:])
    if body[:1].isspace():
        label = _LABEL.match(body)
        if label:
            indent = label["indent"] or label["indent2"]
            word = label["label"] or label["key"]
            return indent + paint(word, "cyan", True) + _marked(body[label.end():])
        return _marked(body)
    row = _ID.match(body)
    if row:
        return paint(row["id"], "cyan", True) + _marked(body[row.end():])
    return _marked(body)


def _marked(text: str) -> str:
    def mark(found: re.Match) -> str:
        word = found.group()
        return paint(word, "green" if word == "wrote" else "cyan", True)
    return _MARKED.sub(mark, text)
