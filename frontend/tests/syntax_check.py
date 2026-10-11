"""A syntax sanity check for the live JavaScript, for machines with no Node.

`frontend/tests/index.html` is the real test suite, and it can only be run by opening it in
a browser. That leaves a gap this closes: a *syntax* error takes the whole file out, so
`App.LivePatches` never installs and every live command silently falls through to the
frozen mockup -- which looks exactly like a feature that was never written rather than a
file that failed to parse.

It has happened. An apostrophe inside a single-quoted string --

    App.Command.note('... the model's own is used again.');

-- broke `patches.js` entirely, and the symptom was `Unknown command "run"`.

Two checks, both chosen because they catch that class and cannot be fooled by the false
positives a bracket counter suffers from (a regular expression literal looks like
division, and `/['"]/` looks like the start of a string):

*   **Unterminated string literal.** A JavaScript string may not contain a raw newline,
    so a quote that reaches the end of its line unclosed is always an error.
*   **Unbalanced brackets**, counted only after strings, comments and regular expression
    literals have been removed properly.

Run it from the repo root:

    python frontend/tests/syntax_check.py
"""

import pathlib
import re
import sys

# A `/` starts a regular expression when what comes before it cannot end an expression;
# after a name, a number or a closing bracket it is division instead. Two things decide
# it: the previous meaningful character, and -- because `return /x/.test(s)` is ordinary
# and `count / 2` is not -- the keyword it may follow.
BEFORE_REGEX = set("(,=:[!&|?{};+-*%~^<>") | {""}
BEFORE_REGEX_KEYWORDS = {
    "return", "typeof", "case", "in", "of", "new", "delete", "do", "else", "void",
    "instanceof", "yield", "await", "throw",
}
TRAILING_WORD = re.compile(r"([A-Za-z_$][\w$]*)\s*$")


def scan(text: str) -> tuple[list[str], str]:
    """Return (problems, code with strings, comments and regexes removed)."""
    problems: list[str] = []
    out: list[str] = []
    index, length, line = 0, len(text), 1
    previous = ""
    while index < length:
        char = text[index]
        if char == "\n":
            line += 1
            out.append(char)
            index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "/":
            index = text.find("\n", index)
            index = length if index < 0 else index
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "*":
            end = text.find("*/", index + 2)
            if end < 0:
                problems.append(f"line {line}: unterminated block comment")
                break
            line += text.count("\n", index, end)
            index = end + 2
            continue
        word = TRAILING_WORD.search("".join(out[-20:]))
        if char == "/" and (previous in BEFORE_REGEX
                            or (word and word.group(1) in BEFORE_REGEX_KEYWORDS)):
            index += 1
            closed = False
            while index < length and text[index] != "\n":
                if text[index] == "\\":
                    index += 2
                    continue
                if text[index] == "[":                 # a class may hold an unescaped /
                    while index < length and text[index] not in "]\n":
                        index += 2 if text[index] == "\\" else 1
                if text[index] == "/":
                    closed = True
                    index += 1
                    break
                index += 1
            if not closed:
                problems.append(f"line {line}: unterminated regular expression")
            previous = "/"
            continue
        if char in "'\"`":
            quote, start, index = char, line, index + 1
            closed = False
            while index < length:
                if text[index] == "\\":
                    index += 2
                    continue
                if text[index] == "\n":
                    line += 1
                    if quote != "`":
                        break                          # only a template may span lines
                if text[index] == quote:
                    closed = True
                    index += 1
                    break
                index += 1
            if not closed:
                problems.append(
                    f"line {start}: unterminated {quote} string -- an unescaped {quote} "
                    "inside it, most likely")
            previous = "x"
            continue
        out.append(char)
        if not char.isspace():
            previous = char
        index += 1
    return problems, "".join(out)


def brackets(code: str) -> list[str]:
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[tuple[str, int]] = []
    line = 1
    for char in code:
        if char == "\n":
            line += 1
        elif char in "([{":
            stack.append((char, line))
        elif char in ")]}":
            if not stack or stack[-1][0] != pairs[char]:
                return [f"line {line}: unbalanced {char!r}"]
            stack.pop()
    return [f"line {stack[-1][1]}: {stack[-1][0]!r} is never closed"] if stack else []


try:
    import esprima
except ImportError:                                  # pragma: no cover - optional
    esprima = None

PARSER_HINT = (
    "no real parser: `pip install esprima` turns this into a full syntax check "
    "instead of a bracket and string one"
)


def parsed(source: str) -> list[str]:
    """A real parse, when one is available.

    The two heuristics below catch the class of error that has actually happened here,
    but they are heuristics: `foo().[1]` balances its brackets and closes its strings,
    and takes the file out just the same. esprima is a JavaScript parser written in
    Python, so it runs on a machine with no Node -- which is the whole constraint this
    file exists under (plan sec 7.17).

    Optional rather than required, and the heuristics still run either way: this check
    has to keep working on a clean checkout with nothing installed, and a syntax check
    that cannot run is worth less than a partial one that can.
    """
    if esprima is None:
        return []
    try:
        esprima.parseScript(source)
    except Exception as failure:                     # esprima raises its own Error
        return [f"{failure}"]
    return []


def main(paths: list[str]) -> int:
    # `frontend/base/js` is in the default scan because the live layer patches its dialogs
    # and explorer in place, so a syntax error there takes out as much of the app.
    frontend = pathlib.Path(__file__).resolve().parents[1]
    files = [pathlib.Path(p) for p in paths] or sorted(
        (frontend / "base" / "js").glob("*.js")) + sorted(
        (frontend / "js").glob("*.js")) + sorted(
        (frontend / "tests").glob("*.js"))
    if esprima is None:
        print(f"note: {PARSER_HINT}")
        print()
    bad = 0
    for path in files:
        source = path.read_text(encoding="utf-8")
        problems, code = scan(source)
        problems += brackets(code)
        problems += parsed(source)
        if problems:
            bad += 1
            for problem in problems:
                print(f"{path}: {problem}")
        else:
            print(f"{path}: ok")
    print(f"\n{len(files) - bad}/{len(files)} files parse cleanly")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
