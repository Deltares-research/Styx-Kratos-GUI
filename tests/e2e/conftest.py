"""The GUI end-to-end tier (plan alpha 3.1): the real server, the real page, a real browser.

The FastAPI app runs in this process under uvicorn, on a free port, with its runs written
to a temporary root. `calculate.run` is swapped for `tests/fakes/fake_kratos.py` so
Results mode can be driven on any machine -- unless `--run-kratos` is given, in which case
the real solver runs. Everything under tests/e2e is marked `e2e` by the root conftest and
needs `--run-e2e`.
"""

from __future__ import annotations

import os
import socket
import threading
import time

import pytest


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    channel = os.environ.get("KRATOS_GUI_TEST_BROWSER_CHANNEL", "chrome")
    args = dict(browser_type_launch_args)
    if channel != "bundled":
        args["channel"] = channel
    return args


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="package")
def live_server(request, tmp_path_factory):
    """Package-scoped, not session: its patches (the fake runner, the runs root) must be
    undone before the rest of the suite runs, or every later test that calls
    `calculate.run` gets the fake -- as 22 of them did when `--run-e2e` ran everything."""
    import uvicorn

    from core import calculate
    from backend.main import app
    from tests.fakes import fake_kratos

    root = tmp_path_factory.mktemp("e2e-runs")
    patch = pytest.MonkeyPatch()
    patch.setenv(calculate.RUNS_ENV, str(root))
    if not request.config.getoption("--run-kratos"):
        patch.setattr(calculate, "run", fake_kratos.fake_run)

    port = _free_port()
    # ws="none": the app has no websockets, and importing uvicorn's websocket protocol
    # pulls in a deprecated websockets module that pyproject.toml's pytest settings turn into an error.
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                           log_level="warning", ws="none"))
    failure: list[BaseException] = []

    def serve():
        try:
            server.run()
        except BaseException as error:          # reported below, not lost in the thread
            failure.append(error)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    deadline = time.monotonic() + 60
    while not server.started:
        if time.monotonic() > deadline or not thread.is_alive():
            raise RuntimeError(f"the server did not start: {failure!r}")
        time.sleep(0.05)
    try:
        yield {"url": f"http://127.0.0.1:{port}", "runs": root}
    finally:
        server.should_exit = True
        thread.join(30)
        patch.undo()


@pytest.fixture
def app_page(page, live_server):
    """The app, loaded on a freshly reset project, with console errors collected."""
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text)
            if message.type == "error" else None)
    page.request.post(live_server["url"] + "/api/project/reset")
    page.set_viewport_size({"width": 1600, "height": 1000})
    page.goto(live_server["url"] + "/")
    page.wait_for_function("window.App && App.LivePatches && App.PROJECT && App.Viewport"
                           " && App.Viewport.getScene && App.Viewport.getScene()",
                           timeout=60_000)
    page.errors = errors
    yield page


def command(page, text: str) -> None:
    """Type a line into the command box and press Enter, as a user would."""
    entry = page.locator("#cmd-entry")
    entry.click()
    entry.fill(text)
    entry.press("Enter")


def log_text(page) -> str:
    return page.locator("#cmd-log").inner_text()
