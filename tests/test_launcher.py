"""Cross-platform launcher tests.

These tests use only the standard library so setup can be checked before pytest and
the application's runtime dependencies have been installed.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend import launcher as _launcher

ROOT = Path(__file__).resolve().parents[1]

platform_venv_name = _launcher.platform_venv_name
requirements_changed = _launcher.requirements_changed
venv_python = _launcher.venv_python


class PlatformEnvironmentTests(unittest.TestCase):
    def test_windows_and_linux_never_share_a_virtual_environment(self):
        self.assertEqual(platform_venv_name("win32"), ".venv-windows")
        self.assertEqual(platform_venv_name("linux"), ".venv-linux")
        self.assertEqual(platform_venv_name("darwin"), ".venv-macos")
        self.assertEqual(platform_venv_name("custom/os"), ".venv-custom-os")

    def test_virtual_environment_python_uses_the_platform_layout(self):
        root = Path("environment")
        self.assertEqual(venv_python(root, "win32"), root / "Scripts" / "python.exe")
        self.assertEqual(venv_python(root, "linux"), root / "bin" / "python")


class RequirementStampTests(unittest.TestCase):
    def test_missing_stamp_requires_installation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            requirements = root / "requirements.txt"
            requirements.write_text("fastapi==1\n", encoding="utf-8")

            self.assertTrue(requirements_changed(requirements, root / ".requirements.sha256"))

    def test_matching_stamp_skips_installation_and_edits_require_it(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            requirements = root / "requirements.txt"
            stamp = root / ".requirements.sha256"
            requirements.write_text("fastapi==1\n", encoding="utf-8")

            self.assertFalse(requirements_changed(requirements, stamp, update=True))
            self.assertFalse(requirements_changed(requirements, stamp))

            requirements.write_text("fastapi==2\n", encoding="utf-8")
            self.assertTrue(requirements_changed(requirements, stamp))


class WrapperTests(unittest.TestCase):
    def test_linux_wrapper_forwards_arguments_to_the_python_launcher(self):
        source = (ROOT / "run.sh").read_text(encoding="utf-8")
        self.assertIn('-m backend.launcher "$@"', source)
        self.assertNotIn(".venv/bin/python", source)

    def test_windows_wrapper_forwards_arguments_to_the_python_launcher(self):
        source = (ROOT / "run.bat").read_text(encoding="utf-8")
        self.assertIn("-m backend.launcher --open-browser %*", source)
        self.assertNotIn(r".venv\Scripts\python.exe", source)


if __name__ == "__main__":
    unittest.main()


# ── main(), with the environment and the server stood in ────────────────────

import pytest as _pytest

@_pytest.fixture
def stood_in(monkeypatch, tmp_path):
    calls = {"check": 0, "exec": None, "call": None}
    monkeypatch.setattr(_launcher, "ensure_environment", lambda: tmp_path / "python")
    monkeypatch.setattr(_launcher, "check_environment",
                        lambda python: calls.__setitem__("check", calls["check"] + 1))
    monkeypatch.setattr(_launcher.os, "execv", lambda exe, argv: calls.__setitem__("exec", argv))
    monkeypatch.setattr(_launcher.os, "chdir", lambda path: None)
    monkeypatch.delenv(_launcher.ALLOWED_HOSTS_ENV, raising=False)
    # Whatever this machine happens to be serving on 8000 is not these tests' business.
    monkeypatch.setattr(_launcher, "port_in_use", lambda host, port: False)
    return calls


def test_check_validates_and_starts_nothing(stood_in):
    assert _launcher.main(["--check"]) == 0
    assert stood_in["check"] == 1 and stood_in["exec"] is None


def test_the_server_is_started_on_loopback_by_default(stood_in):
    _launcher.main([])

    argv = stood_in["exec"]
    assert argv[argv.index("--host") + 1] == "127.0.0.1"
    assert _launcher.ALLOWED_HOSTS_ENV not in _launcher.os.environ


def test_a_named_host_is_allowed_through_to_the_server(stood_in, monkeypatch):
    _launcher.main(["--host", "modelling-pc", "--port", "9000"])

    argv = stood_in["exec"]
    assert argv[argv.index("--port") + 1] == "9000"
    assert _launcher.os.environ[_launcher.ALLOWED_HOSTS_ENV] == "modelling-pc"
    monkeypatch.delenv(_launcher.ALLOWED_HOSTS_ENV)


def test_a_failed_setup_is_one_line_and_exit_code_one(monkeypatch, capsys):
    def broken():
        raise RuntimeError("Python 3.10 or newer is required; found 3.9")
    monkeypatch.setattr(_launcher, "ensure_environment", broken)

    assert _launcher.main([]) == 1
    assert "Launcher failed: Python 3.10" in capsys.readouterr().err


class WindowsInterpreterTests(unittest.TestCase):
    def test_regular_python_selects_the_same_minor_version(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        result = SimpleNamespace(returncode=0, stdout="C:\\Python313\\python.exe\n0\n")
        version = SimpleNamespace(major=3, minor=13)
        with patch.object(_launcher.sys, "version_info", version), \
                patch.object(_launcher.subprocess, "run", return_value=result):
            self.assertEqual(_launcher._regular_windows_python(),
                             Path(r"C:\Python313\python.exe"))

    def test_free_threaded_fallback_is_rejected(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        result = SimpleNamespace(returncode=0, stdout="C:\\Python313t\\python.exe\n1\n")
        version = SimpleNamespace(major=3, minor=13)
        with patch.object(_launcher.sys, "version_info", version), \
                patch.object(_launcher.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "install regular Python 3.13"):
                _launcher._regular_windows_python()


@_pytest.mark.parametrize("output, returncode, expected", [
    ("0\n", 0, False),
    ("1\n", 0, True),
    ("", 1, None),
    ("", 0, None),
    ("unexpected\n", 0, None),
])
def test_launcher_probes_the_environment_abi(
        monkeypatch, output, returncode, expected):
    from types import SimpleNamespace
    from unittest.mock import Mock

    run = Mock(return_value=SimpleNamespace(stdout=output, returncode=returncode))
    monkeypatch.setattr(_launcher.subprocess, "run", run)
    python = Path("environment-python.exe")

    assert _launcher._python_is_free_threaded(python) is expected
    assert run.call_args.args[0][0] == str(python)


def test_launcher_handles_an_interpreter_that_cannot_start(monkeypatch):
    from unittest.mock import Mock

    monkeypatch.setattr(_launcher.subprocess, "run",
                        Mock(side_effect=OSError("cannot execute")))

    assert _launcher._python_is_free_threaded(Path("broken-python.exe")) is None


def test_launcher_explains_a_missing_windows_python_launcher(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock

    monkeypatch.setattr(_launcher, "sys", SimpleNamespace(
        version_info=SimpleNamespace(major=3, minor=13)))
    monkeypatch.setattr(_launcher.subprocess, "run",
                        Mock(side_effect=FileNotFoundError("py not found")))

    with _pytest.raises(RuntimeError, match="install regular Python 3.13"):
        _launcher._regular_windows_python()


def test_windows_python_probe_preserves_unicode_paths_and_tolerates_launcher_diagnostics(
        monkeypatch):
    import os
    import subprocess
    import sys

    executable = "C:\\Users\\" + chr(0x0416) + "\\Python313\\python.exe"
    run = subprocess.run

    def launch_probe(command, **kwargs):
        assert command[:2] == [
            "py", f"-{sys.version_info.major}.{sys.version_info.minor}"]
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["errors"] == "replace"
        environment = dict(os.environ, PYTHONIOENCODING="ascii:strict")
        prefix = (
            f"import sys, os, sysconfig; sys.executable = {ascii(executable)}; "
            "sysconfig.get_config_var = lambda name: 0; "
            "os.write(2, bytes([255])); "
        )
        return run([sys.executable, "-c", prefix + command[-1]],
                   env=environment, **kwargs)

    monkeypatch.setattr(_launcher.subprocess, "run", launch_probe)

    assert _launcher._regular_windows_python() == Path(executable)


def test_launcher_refuses_an_unsupported_python_before_setup(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock

    monkeypatch.setattr(_launcher, "sys", SimpleNamespace(
        version_info=(3, 9), version="3.9.9"))
    create = Mock()
    monkeypatch.setattr(_launcher.venv, "EnvBuilder", create)

    with _pytest.raises(RuntimeError, match="Python 3.10 or newer.*found 3.9.9"):
        _launcher.ensure_environment()
    create.assert_not_called()


@_pytest.mark.parametrize("output, returncode", [
    ("", 0),
    ("python.exe\n", 0),
    ("\n0\n", 0),
    ("python.exe\n0\n", 1),
])
def test_regular_windows_python_rejects_an_invalid_probe(monkeypatch, output, returncode):
    from types import SimpleNamespace
    from unittest.mock import Mock

    monkeypatch.setattr(_launcher, "sys", SimpleNamespace(
        version_info=SimpleNamespace(major=3, minor=13)))
    monkeypatch.setattr(_launcher.subprocess, "run", Mock(return_value=SimpleNamespace(
        stdout=output, returncode=returncode)))

    with _pytest.raises(RuntimeError, match="install regular Python 3.13"):
        _launcher._regular_windows_python()


@_pytest.mark.parametrize("platform, version, free_threaded", [
    ("win32", (3, 13), False),
    ("win32", (3, 14), True),
    ("linux", (3, 13), True),
    ("darwin", (3, 13), True),
])
def test_launcher_leaves_other_interpreters_on_the_normal_startup_path(
        stood_in, monkeypatch, platform, version, free_threaded):
    from types import SimpleNamespace
    from unittest.mock import Mock

    monkeypatch.setattr(_launcher, "sys", SimpleNamespace(
        platform=platform, version_info=version))
    monkeypatch.setattr(_launcher, "sysconfig", SimpleNamespace(
        get_config_var=lambda _: int(free_threaded)))
    fallback = Mock()
    monkeypatch.setattr(_launcher, "_regular_windows_python", fallback)

    assert _launcher.main(["--check"]) == 0
    fallback.assert_not_called()
    assert stood_in["check"] == 1
    assert stood_in["exec"] is None


@_pytest.mark.parametrize("explicit_arguments", [True, False])
def test_launcher_reexecutes_older_free_threaded_windows_python(
        monkeypatch, tmp_path, explicit_arguments):
    from types import SimpleNamespace
    from unittest.mock import Mock

    class Reexecuted(BaseException):
        pass

    forwarded = ["--check"]
    regular = Path("regular-python.exe")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(_launcher, "sys", SimpleNamespace(
        platform="win32", version_info=(3, 13),
        argv=[str(ROOT / "backend" / "launcher.py"), *forwarded]))
    monkeypatch.setattr(_launcher, "sysconfig", SimpleNamespace(get_config_var=lambda _: 1))
    monkeypatch.setattr(_launcher, "_regular_windows_python", lambda: regular)
    monkeypatch.setattr(_launcher, "parse_args", lambda _: SimpleNamespace(check=True))
    setup = Mock()

    def reexecute(*_args):
        assert Path.cwd() == ROOT
        raise Reexecuted

    execute = Mock(side_effect=reexecute)
    monkeypatch.setattr(_launcher, "ensure_environment", setup)
    monkeypatch.setattr(_launcher.os, "execv", execute)

    with _pytest.raises(Reexecuted):
        _launcher.main(forwarded if explicit_arguments else None)

    execute.assert_called_once_with(
        str(regular), [str(regular), "-m", "backend.launcher", *forwarded])
    setup.assert_not_called()


@_pytest.mark.parametrize("exists, abi, host_abi, recreate", [
    (False, False, False, True),
    (True, False, False, False),
    (True, True, False, True),
    (True, None, False, True),
    (True, True, True, False),
    (True, False, True, True),
])
def test_launcher_rebuilds_only_a_missing_or_incompatible_environment(
        tmp_path, monkeypatch, exists, abi, host_abi, recreate):
    from types import SimpleNamespace
    from unittest.mock import Mock

    environment = tmp_path / ".venv-windows"
    python = environment / "python.exe"
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("example==1\n", encoding="ascii")
    if exists:
        environment.mkdir()
        python.touch()
    monkeypatch.setattr(_launcher, "ROOT", tmp_path)
    monkeypatch.setattr(_launcher, "REQUIREMENTS", requirements)
    monkeypatch.setattr(_launcher, "sys", SimpleNamespace(
        platform="win32", version_info=(3, 13), version="3.13"))
    monkeypatch.setattr(_launcher, "sysconfig", SimpleNamespace(
        get_config_var=lambda _: int(host_abi)))
    monkeypatch.setattr(_launcher, "platform_venv_name", lambda: ".venv-windows")
    monkeypatch.setattr(_launcher, "venv_python", lambda _: python)
    monkeypatch.setattr(_launcher, "_python_is_free_threaded", lambda _: abi)

    def create(folder):
        assert folder == environment
        environment.mkdir(exist_ok=True)
        python.touch()

    builder = Mock()
    builder.create.side_effect = create
    factory = Mock(return_value=builder)
    install = Mock()
    monkeypatch.setattr(_launcher.venv, "EnvBuilder", factory)
    monkeypatch.setattr(_launcher.subprocess, "check_call", install)

    assert _launcher.ensure_environment() == python
    if recreate:
        factory.assert_called_once_with(with_pip=True, clear=exists)
        builder.create.assert_called_once_with(environment)
    else:
        factory.assert_not_called()
    install.assert_called_once_with(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check",
         "-r", str(requirements)], cwd=tmp_path)
    assert not _launcher.requirements_changed(
        requirements, environment / ".requirements.sha256")
    monkeypatch.setattr(_launcher, "_python_is_free_threaded", lambda _: host_abi)
    factory.reset_mock()
    install.reset_mock()

    assert _launcher.ensure_environment() == python
    factory.assert_not_called()
    install.assert_not_called()


def test_launcher_does_not_stamp_a_failed_dependency_install(tmp_path, monkeypatch):
    from unittest.mock import Mock

    environment = tmp_path / "environment"
    environment.mkdir()
    python = environment / "python.exe"
    python.touch()
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("example==1\n", encoding="ascii")
    monkeypatch.setattr(_launcher, "_ensure_supported_python", lambda: None)
    monkeypatch.setattr(_launcher, "ROOT", tmp_path)
    monkeypatch.setattr(_launcher, "REQUIREMENTS", requirements)
    monkeypatch.setattr(_launcher, "platform_venv_name", lambda: "environment")
    monkeypatch.setattr(_launcher, "venv_python", lambda _: python)
    monkeypatch.setattr(_launcher, "_python_is_free_threaded", lambda _: False)
    from types import SimpleNamespace
    monkeypatch.setattr(_launcher, "sysconfig", SimpleNamespace(get_config_var=lambda _: 0))
    failure = _launcher.subprocess.CalledProcessError(1, ["pip"])
    monkeypatch.setattr(_launcher.subprocess, "check_call", Mock(side_effect=failure))

    with _pytest.raises(_launcher.subprocess.CalledProcessError):
        _launcher.ensure_environment()

    assert not (environment / ".requirements.sha256").exists()


# ── A port that is already taken ────────────────────────────────────────────

import socket as _socket


@_pytest.fixture
def listening():
    """A socket listening on a free loopback port, like a server left running."""
    server = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen()
    yield server.getsockname()[1]
    server.close()


def test_a_port_with_a_server_on_it_is_in_use(listening):
    assert _launcher.port_in_use("127.0.0.1", listening)
    assert _launcher.port_in_use("localhost", listening)


def test_an_all_interfaces_bind_is_probed_on_loopback(listening):
    assert _launcher.port_in_use("0.0.0.0", listening)


def test_a_free_port_is_not_in_use(listening):
    port = listening
    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        free = probe.getsockname()[1]

    assert not _launcher.port_in_use("127.0.0.1", free)
    assert port != free


def test_a_server_already_on_the_port_is_refused_not_opened(stood_in, monkeypatch, capsys):
    """A server left running from before still holds its own project in memory, and
    its own code. The browser must not be pointed at it as if it were this one: a new
    server cannot bind the port, so it would exit, and the page would show the old
    model."""
    monkeypatch.setattr(_launcher, "port_in_use", lambda host, port: True)
    opened = []
    monkeypatch.setattr(_launcher.webbrowser, "open", opened.append)
    monkeypatch.setattr(_launcher.subprocess, "call",
                        lambda argv: stood_in.__setitem__("call", argv))

    assert _launcher.main(["--open-browser"]) == 1

    assert stood_in["exec"] is None and stood_in["call"] is None and opened == []
    err = capsys.readouterr().err
    assert "8000" in err and "already" in err


def test_opening_the_browser_preserves_the_server_exit_status(stood_in, monkeypatch):
    from unittest.mock import Mock

    timer = Mock()
    factory = Mock(return_value=timer)
    server = Mock(return_value=7)
    monkeypatch.setattr(_launcher.threading, "Timer", factory)
    monkeypatch.setattr(_launcher.subprocess, "call", server)

    assert _launcher.main(["--open-browser", "--port", "9000"]) == 7
    factory.assert_called_once_with(
        1.0, _launcher.webbrowser.open, args=("http://127.0.0.1:9000/",))
    timer.start.assert_called_once_with()
    assert server.call_args.args[0][-2:] == ["--port", "9000"]
    assert stood_in["exec"] is None


def test_a_failed_server_exec_is_reported_as_a_launcher_error(
        stood_in, monkeypatch, capsys):
    from unittest.mock import Mock

    monkeypatch.setattr(_launcher.os, "execv",
                        Mock(side_effect=OSError("cannot start server")))

    assert _launcher.main([]) == 1
    assert "Launcher failed: cannot start server" in capsys.readouterr().err
