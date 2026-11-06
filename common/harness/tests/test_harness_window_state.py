"""Run the window focus and selection checks in a fresh GUI process."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


class HarnessWindowStateTest(unittest.TestCase):
    """Focus and selection survive status updates and rollover."""

    def test_focus_and_selection_probe(self) -> None:
        """Run ``window_state_probe`` apart from QCore tests."""
        result = subprocess.run(
            [sys.executable, "-m", "common.harness.tests.window_state_probe"],
            cwd=Path(__file__).resolve().parents[3],
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(result.returncode, 0,
                         result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
