## What and why

<!-- What this changes, and why. Link the issue it closes: "Closes #123". -->

## How it was tested

<!-- The tests you added or changed. Anything checked by hand, and why it could not be automated. -->

## Checklist

- [ ] A failing test came first, and it passes now
- [ ] `python tools/test.py quick` passes (`browser` if the frontend changed)
- [ ] `python frontend/tests/syntax_check.py` passes, if any JavaScript changed
- [ ] `ruff check .` passes
- [ ] If the deck writer or the results reader changed: `python tools/test.py kratos` passes on a machine with Kratos
- [ ] The documentation (README.md, ARCHITECTURE.md, FEATURES.md) matches the change
- [ ] A label is set: `bug`, `enhancement`, `documentation`, `breaking-change` or `dependencies`
