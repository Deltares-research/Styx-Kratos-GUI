"""Jobs for `test_gmsh_worker.py`. A separate module because the pool pickles a job by its
qualified name, so the worker process has to be able to import it."""

import os
import time


def crash() -> None:
    """What an OCC abort does to the worker: the process ends, nothing unwinds."""
    os._exit(1)


def crash_with_args(*_args) -> None:
    """`crash`, in the place of a real job that is passed the project."""
    os._exit(1)


def fail(message: str) -> None:
    raise ValueError(message)


def pid() -> int:
    return os.getpid()


def hold(seconds: float) -> tuple[int, float, float]:
    started = time.monotonic()
    time.sleep(seconds)
    return os.getpid(), started, time.monotonic()
