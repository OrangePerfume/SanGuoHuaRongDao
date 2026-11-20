"""Prevent regressions that turn a passing unittest summary into a false CI pass."""
from pathlib import Path
import unittest
from unittest.mock import Mock

from tools.run_tests import gate_failure

ROOT = Path(__file__).resolve().parents[1]


class CIGateTests(unittest.TestCase):
    def test_strict_gate_rejects_gui_skips(self):
        result = Mock()
        result.wasSuccessful.return_value = True
        result.skipped = [("gui", "missing Qt")]
        self.assertIsNotNone(gate_failure(result, True, []))
        self.assertIsNone(gate_failure(result, False, []))

    def test_strict_gate_rejects_unit_failures_and_qt_callback_errors(self):
        result = Mock()
        result.wasSuccessful.return_value = False
        result.skipped = []
        self.assertIsNotNone(gate_failure(result, True, []))
        result.wasSuccessful.return_value = True
        self.assertIsNotNone(gate_failure(result, True, ["Qt callback traceback"]))
        self.assertIsNotNone(gate_failure(None, True, []))

    def test_strict_gate_accepts_only_success_with_no_skips(self):
        result = Mock()
        result.wasSuccessful.return_value = True
        result.skipped = []
        self.assertIsNone(gate_failure(result, True, []))

    def test_windows_workflows_and_local_build_share_strict_runner(self):
        files = (
            ROOT / ".github/workflows/ci.yml",
            ROOT / ".github/workflows/release.yml",
            ROOT / "build.cmd",
        )
        for file in files:
            with self.subTest(file=file.name):
                source = file.read_text(encoding="utf-8")
                self.assertIn("tools/run_tests.py --require-qt", source)
                self.assertNotIn("continue-on-error: true", source)
                self.assertNotIn("python -m unittest discover", source)


if __name__ == "__main__":
    unittest.main()
