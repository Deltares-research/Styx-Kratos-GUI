"""What the server keeps of its own log, for a feedback report (`core/feedback.py`).

The console the server runs in is often closed, or out of sight, when someone reports a
problem. So the server keeps the last lines of its log in memory -- its errors with their
tracebacks, and uvicorn's own messages -- and the last API requests, one line each. A report
takes both as `server-log.txt`. Nothing is written to disk here, and nothing outlives the
server.
"""

from __future__ import annotations

import logging
import time
import traceback
from collections import deque

LOGGER = logging.getLogger("styx")
"""The server's own logger. An error that reaches no route's answer is logged here."""

MAX_LINES = 400
MAX_REQUESTS = 200

_lines: deque[str] = deque(maxlen=MAX_LINES)
_requests: deque[str] = deque(maxlen=MAX_REQUESTS)


ALREADY_KEPT = "Exception in ASGI application"
"""How uvicorn says an error reached it. The app's own handler (`backend/main.py`) has kept
that error with its traceback already, so uvicorn's copy is left out."""


class _Keep(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith("uvicorn") and record.getMessage().startswith(ALREADY_KEPT):
            return
        try:
            _lines.append(self.format(record))
        except Exception:  # a log line that cannot be formatted must not stop the server
            self.handleError(record)


_handler = _Keep()
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s",
                                        "%H:%M:%S"))
WATCHED = ("styx", "uvicorn", "uvicorn.error")
"""The loggers kept. `uvicorn.access` is not: `request` keeps the API requests in a shorter
form, and leaves out the page's own files."""


def install() -> None:
    """Keep the lines of `WATCHED`. Called when the server starts: uvicorn sets up its
    loggers before that, and would drop a handler added earlier. Twice is the same as once."""
    for name in WATCHED:
        logger = logging.getLogger(name)
        if _handler not in logger.handlers:
            logger.addHandler(_handler)
    if LOGGER.level == logging.NOTSET:
        LOGGER.setLevel(logging.INFO)


def error(what: str, failure: BaseException) -> None:
    """Log `failure` with its traceback."""
    LOGGER.error("%s\n%s", what, "".join(
        traceback.format_exception(type(failure), failure, failure.__traceback__)).rstrip())


def request(method: str, path: str, status: int, seconds: float) -> None:
    _requests.append(f"{time.strftime('%H:%M:%S')} {method} {path} -> {status} "
                     f"({seconds * 1000:.0f} ms)")


def text() -> str:
    """The log and the requests, as the text of `server-log.txt`."""
    parts = ["Server log (last lines)", "=======================", *(_lines or ["(empty)"]), "",
             "API requests (last ones)", "========================",
             *(_requests or ["(none)"])]
    return "\n".join(parts) + "\n"


def clear() -> None:
    """Forget everything kept; for the tests."""
    _lines.clear()
    _requests.clear()
