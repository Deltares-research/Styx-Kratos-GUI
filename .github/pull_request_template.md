## What and why

<!-- What this pull request changes, and why. Link the issue that it closes: "Closes #123". -->

## How it was tested

<!-- The tests that you added or changed. Anything that you checked by hand, and why it has no automated test. -->

## Checklist

- [ ] `python tools/test.py quick` passes (`browser` if the browser code changed)
- [ ] `ruff check .` passes
- [ ] If `core/kratos/`, `core/analysis/` or `core/results/` changed: `python tools/test.py kratos` and `python tools/test.py bench` pass on a computer with Kratos
- [ ] If the GUI got a new edit of the model: `kratos-cli` has the same command
- [ ] The documents match the change (see "Documents to update" in CONTRIBUTING.md)
- [ ] The pull request has one label: `bug`, `enhancement`, `documentation`, `breaking-change` or `dependencies`
