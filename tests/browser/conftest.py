import os

import pytest


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    # The installed Chrome by default; "bundled" uses `python -m playwright install chromium`.
    channel = os.environ.get("KRATOS_GUI_TEST_BROWSER_CHANNEL", "chrome")
    args = {**browser_type_launch_args, "args": ["--allow-file-access-from-files"]}
    if channel != "bundled":
        args["channel"] = channel
    return args
