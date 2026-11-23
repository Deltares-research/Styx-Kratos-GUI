"""Read what a UDSM library says about itself: the models it holds and, per model, the
name and unit of each parameter.

A UDSM library is a soil law compiled into a .dll (Windows) or .so (Linux) that Kratos'
`SmallStrainUDSM*Law` loads at run time. It answers four questions through functions of
its own, written in Fortran: `getmodelcount`, `getmodelname`, `getparamcount`,
`getparamname` and `getparamunit`. Every argument goes by reference, and a string comes
with its buffer length as one more argument.

Loading a library runs its code, so this file is run as a script in a process of its own
(`core.model.udsm`): `python -I udsm_parser.py LIBRARY` prints one JSON object. A library
that crashes ends that process, not Styx. The strings are returned as the library wrote
them; `core.model.udsm` makes them readable.

Based on `kratos_element_test/model/io/udsm_parser.py` in KratosElementTestSuite.
"""

from __future__ import annotations

import ctypes
import json
import sys

BUFFER_SIZE = 256


def _function(library: ctypes.CDLL, name: str):
    """The library's function `name`, under the spellings Fortran compilers export it."""
    for spelling in (name, name.upper(), name + "_", name.upper() + "_"):
        try:
            return getattr(library, spelling)
        except AttributeError:
            continue
    raise LookupError(f"the library has no function {name}")


def _integer(value: int):
    return ctypes.byref(ctypes.c_int(value))


def _string(call, *numbers: int) -> bytes:
    buffer = ctypes.create_string_buffer(BUFFER_SIZE)
    call(*(_integer(n) for n in numbers), buffer, ctypes.c_long(BUFFER_SIZE))
    return buffer.raw


def _count(call, *numbers: int) -> int:
    result = ctypes.c_int()
    call(*(_integer(n) for n in numbers), ctypes.byref(result))
    return result.value


def text(raw: bytes) -> str:
    """A string the library wrote into a buffer.

    The libraries write a counted string: the first byte is the length of the text that
    follows, and blanks fill the rest of the buffer. A buffer that does not read as one
    is taken as plain text."""
    raw = raw.split(b"\0")[0]
    if raw and raw[0] <= len(raw) - 1 and not raw[1 + raw[0]:].strip():
        raw = raw[1:1 + raw[0]]
    return raw.decode("latin-1").strip()


def read(path: str) -> dict:
    """What the library at `path` says about itself:
    `{"models": [{"number", "name", "parameters": [{"name", "unit"}]}]}`, the strings as
    the library wrote them. `number` is the 1-based `UDSM_NUMBER` Kratos takes."""
    library = ctypes.CDLL(path, winmode=0) if sys.platform == "win32" else ctypes.CDLL(path)
    model_count = _function(library, "getmodelcount")
    model_name = _function(library, "getmodelname")
    parameter_count = _function(library, "getparamcount")
    parameter_name = _function(library, "getparamname")
    parameter_unit = _function(library, "getparamunit")
    for call in (model_count, model_name, parameter_count, parameter_name, parameter_unit):
        call.restype = None
    models = []
    for number in range(1, _count(model_count) + 1):
        parameters = [{"name": text(_string(parameter_name, number, index)),
                       "unit": text(_string(parameter_unit, number, index))}
                      for index in range(1, _count(parameter_count, number) + 1)]
        models.append({"number": number, "name": text(_string(model_name, number)),
                       "parameters": parameters})
    return {"models": models}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -I udsm_parser.py LIBRARY")
    print(json.dumps(read(sys.argv[1])))
