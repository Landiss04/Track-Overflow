"""Check module close/hide and SHOW restoration in a GUI process."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

_PROBE = """
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QWindow
from utils.harness_protocol import show_message
from utils.module_link import ModuleLink
from utils.module_window import keep_windows_open

app = QGuiApplication([])
keep_windows_open(app)
window = QWindow()
dialog = QWindow()
dialog.setFlags(Qt.WindowType.Dialog)
dialog.setTransientParent(window)
window.show()
dialog.show()
app.processEvents()
assert not dialog.close()
assert not window.close()
assert not window.isVisible() and not dialog.isVisible()
link = ModuleLink("train-model", "unused", lambda *args: {})
shown = []
link.showRequested.connect(lambda: shown.append(True))
link._handle(show_message(7))
app.processEvents()
assert window.isVisible()
assert not dialog.isVisible()
assert shown == [True] and link.tick == 0 and link.last_reply is None
link.close()
window.hide()
"""


class ModuleWindowTest(unittest.TestCase):
    """Restore a closed main window while keeping dialogs hidden."""

    def test_show_restores_only_main_windows(self) -> None:
        """Reopen through ModuleLink without changing stepping state."""
        result = subprocess.run(
            [sys.executable, "-c", _PROBE],
            cwd=Path(__file__).resolve().parents[2],
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
            capture_output=True, text=True, timeout=15, check=False,
        )
        self.assertEqual(result.returncode, 0,
                         result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
