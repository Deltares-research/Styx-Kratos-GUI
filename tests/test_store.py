"""The one open project (`backend.store`).

`get` hands out the live object, not a copy. The routes rely on that, and it is also
what made finding F3 possible: a route that mutates what `get` returned and skips
validation leaves the store holding an invalid project. Every route now validates a new
project and `put`s it; these pin the store's own half of that contract.
"""

from backend import store
from core.schemas import Project
from core.seed import blank_project, seed_project


def test_get_returns_the_live_project_not_a_copy():
    assert store.get() is store.get()


def test_put_replaces_the_project_and_returns_it():
    saved = store.get()
    try:
        project = seed_project()
        assert store.put(project) is project
        assert store.get() is project
    finally:
        store.put(saved)


def test_reset_opens_the_seed_and_new_a_blank_project():
    saved = store.get()
    try:
        assert store.reset().model_dump() == seed_project().model_dump()
        assert store.new().model_dump() == blank_project().model_dump()
    finally:
        store.put(saved)


def test_both_starting_projects_validate_and_resave_as_a_fixed_point():
    for project in (seed_project(), seed_project(simple=True), blank_project()):
        dumped = project.model_dump(mode="json")
        assert Project.model_validate(dumped).model_dump(mode="json") == dumped
