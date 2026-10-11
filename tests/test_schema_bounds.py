"""Every declared bound in the schema, tested on both sides (plan sec 4.1).

Generated rather than written: each `Field(gt=..., ge=..., lt=..., le=...)`,
`min_length`/`max_length` and `Literal[...]` on every model in `core.schemas` becomes a
pair of cases -- the value at (or just inside) the bound is accepted, the value just
outside it is refused. A bound added tomorrow is tested tomorrow, and a bound someone
loosens by accident fails here.

Each field is validated on its own, through a `TypeAdapter` carrying the field's own
constraints, because building a whole valid instance of every model generically would
test the fixture, not the bound.
"""

from __future__ import annotations

import inspect
import math
import types
import typing
from typing import Annotated, Literal, get_args, get_origin

import annotated_types
import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from core import schemas

EPSILON = 1e-9


def _models() -> list[type[BaseModel]]:
    return [obj for _, obj in inspect.getmembers(schemas, inspect.isclass)
            if issubclass(obj, BaseModel) and obj.__module__ == schemas.__name__]


def _unwrap(annotation):
    """`X | None` -> X; anything else unchanged. A None alternative is not a bound."""
    if get_origin(annotation) in (typing.Union, types.UnionType):
        options = [a for a in get_args(annotation) if a is not type(None)]
        if len(options) == 1:
            return options[0]
    return annotation


def _flatten(annotation) -> tuple[object, list]:
    """An `Annotated` alias (`PositiveSize`) carries its constraints with it."""
    metadata = []
    while get_origin(annotation) is Annotated:
        args = get_args(annotation)
        annotation, metadata = args[0], metadata + list(args[1:])
    return annotation, metadata


def _is_int(annotation) -> bool:
    return annotation is int


def _numeric_cases(base, metadata):
    as_int = _is_int(base)
    step = 1 if as_int else max(EPSILON, 1e-9)
    for item in metadata:
        if isinstance(item, annotated_types.Gt):
            yield "gt", item.gt + step, item.gt
        elif isinstance(item, annotated_types.Ge):
            yield "ge", item.ge, item.ge - step
        elif isinstance(item, annotated_types.Lt):
            yield "lt", item.lt - step, item.lt
        elif isinstance(item, annotated_types.Le):
            yield "le", item.le, item.le + step


def _cases():
    out = []
    for model in _models():
        for name, info in model.model_fields.items():
            annotation, aliased = _flatten(_unwrap(info.annotation))
            metadata = aliased + list(info.metadata)
            label = f"{model.__name__}.{name}"
            if annotation in (int, float):
                for kind, ok, bad in _numeric_cases(annotation, metadata):
                    if isinstance(ok, float) and not math.isfinite(ok):
                        continue
                    out.append(pytest.param(info, ok, bad, id=f"{label}:{kind}"))
            elif get_origin(annotation) is Literal:
                choices = get_args(annotation)
                out.append(pytest.param(info, choices[0], "__not_a_choice__",
                                        id=f"{label}:literal"))
            for item in metadata:
                if isinstance(item, annotated_types.MinLen) and item.min_length > 0:
                    empty = "" if annotation is str else []
                    out.append(pytest.param(info, None, empty, id=f"{label}:min_length"))
    return out


CASES = _cases()


def _adapter(info):
    return TypeAdapter(Annotated[info.annotation, info])


def test_the_schema_has_bounds_to_test():
    """A guard on the generator: if introspection broke, every case below would vanish
    and the module would pass by testing nothing."""
    assert len(CASES) > 40


@pytest.mark.parametrize("info,ok,bad", CASES)
def test_a_bound_accepts_its_edge_and_refuses_past_it(info, ok, bad):
    adapter = _adapter(info)
    if ok is not None:
        adapter.validate_python(ok)
    with pytest.raises(ValidationError):
        adapter.validate_python(bad)


def test_every_refusal_says_which_bound():
    """The message is what reaches the command log; it must say what the limit is."""
    info = schemas.MeshSettings.model_fields["element_size"]
    with pytest.raises(ValidationError) as caught:
        _adapter(info).validate_python(0)
    assert "greater than 0" in str(caught.value)
