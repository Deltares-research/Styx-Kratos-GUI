"""Cross-platform launcher tests.

These tests use only the standard library so setup can be checked before pytest and
the application's runtime dependencies have been installed.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.launcher import platform_venv_name, requirements_changed, venv_python

SERVER_ROOT = Path(__file__).resolve().parents[1]


class PlatformEnvironmentTests(unittest.TestCase):
    def test_windows_and_linux_never_share_a_virtual_environment(self):
        self.assertEqual(platform_venv_name("win32"), ".venv-windows")
        self.assertEqual(platform_venv_name("linux"), ".venv-linux")

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
        source = (SERVER_ROOT / "run.sh").read_text(encoding="utf-8")
        self.assertIn('-m app.launcher "$@"', source)
        self.assertNotIn(".venv/bin/python", source)

    def test_windows_wrapper_forwards_arguments_to_the_python_launcher(self):
        source = (SERVER_ROOT / "run.bat").read_text(encoding="utf-8")
        self.assertIn("-m app.launcher --open-browser %*", source)
        self.assertNotIn(r".venv\Scripts\python.exe", source)


if __name__ == "__main__":
    unittest.main()
