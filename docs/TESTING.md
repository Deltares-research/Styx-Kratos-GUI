# Running the tests

Run these commands from the repository root, with any Python 3.10+. The runner always runs
pytest in the app's own venv. First install the test-only tools into that venv:

```bash
# Windows
.venv-windows\Scripts\python.exe -m pip install -r requirements-dev.txt
# Linux (use .venv-macos on macOS)
.venv-linux/bin/python -m pip install -r requirements-dev.txt
```

| Command | What it runs |
|---|---|
| `python tools/test.py quick` | The JS syntax check, the headless JS suites, and pytest without the browser |
| `python tools/test.py browser` | Everything in `quick`, plus the browser unit suite (`frontend/tests/index.html`) through Playwright |
| `python tools/test.py e2e` | Everything in `browser`, plus the GUI end-to-end tests |
| `python tools/test.py kratos` | The tests that run Kratos (needs [Kratos to be set up](KRATOS_SETUP.md)) |
| `python tools/test.py bench` | The Kratos benchmark runner |
| `python tools/test.py perf` | The performance tests |
| `python tools/test.py all` | Everything this machine can run, with a list of what was skipped and why |

- Any arguments after the tier are passed to pytest, for example
  `python tools/test.py quick -k phases -x`.
- If a step's prerequisite is missing (quickjs, Kratos, or a browser), the step is reported as
  skipped, not as failed.
- The headless JS suites need `quickjs`. If it does not install in the venv, set
  `KRATOS_GUI_QUICKJS_PYTHON` to a Python that has it.
- The browser tests use your installed Chrome. If you do not have Chrome, run
  `python -m playwright install chromium` and set `KRATOS_GUI_TEST_BROWSER_CHANNEL=bundled`.
- For coverage, add `--cov=core --cov=backend --cov-report=html --js-coverage` to a tier that
  runs the browser suite. The Python report is written to `htmlcov/`, and the JS function
  coverage to `htmlcov-js/summary.json`.

CI runs the `e2e` tier on Windows and Ubuntu for every pull request and every push to `main`
(see [.github/workflows/tests.yml](../.github/workflows/tests.yml)). Line coverage below 95 %
fails the run. [CONTRIBUTING.md](../CONTRIBUTING.md) lists the other checks CI runs.
