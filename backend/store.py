"""The one project this server is editing.

Single session, held in memory: the app it serves is a desktop-style modeller with one
document open, and the frozen UI has no concept of a project list or a user. Persistence
would be a real feature with real questions attached (where, what format, what happens to
a mesh when the geometry changes underneath it), not a line of code -- so it is left out
rather than half-done.
"""

from __future__ import annotations

from core.model.schemas import Project
from core.model.templates import blank_project, seed_project

# The server opens on an empty site. `reset()` restores the demo model -- it is what
# test setup uses to get back to a known, fully-populated project -- while `new()` is
# the toolbar's "New project": an actually empty site, the same one the server opens on.
_project: Project = blank_project()


def get() -> Project:
    return _project


def put(project: Project) -> Project:
    """Replace the model. Validation has already happened in the schema."""
    global _project
    _project = project
    return _project


def reset() -> Project:
    return put(seed_project())


def new() -> Project:
    return put(blank_project())
