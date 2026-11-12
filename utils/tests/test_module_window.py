"""Check module close/hide, SHOW and SNAPSHOT in a GUI process."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
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

# A hidden QML window still saves a tile-sized image of itself, and a
# maximized SHOW maximizes it.
_SNAPSHOT_PROBE = """
import os, sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQml import QQmlApplicationEngine
from utils.harness_protocol import show_message, snapshot_message
from utils.module_link import ModuleLink
from utils.module_window import SNAPSHOT_WIDTH_PX, keep_windows_open

app = QGuiApplication([])
keep_windows_open(app)
engine = QQmlApplicationEngine()
engine.loadData(b"import QtQuick\\nWindow { width: 1440; height: 900; "
                b"visible: true; color: 'red' }")
window = engine.rootObjects()[0]
app.processEvents()
assert not window.close() and not window.isVisible()
link = ModuleLink("train-model", "unused", lambda *args: {})
path = os.path.join(sys.argv[1], "train-model.png")
link._handle(snapshot_message(7, path))
image = QImage(path)
assert not image.isNull() and image.width() == SNAPSHOT_WIDTH_PX
assert image.pixelColor(10, 10).name() == "#ff0000"
assert os.listdir(sys.argv[1]) == ["train-model.png"]
link._handle(show_message(7, maximized=True))
app.processEvents()
assert window.isVisible()
assert window.windowState() == Qt.WindowState.WindowMaximized
assert link.tick == 0 and link.last_reply is None
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

    def test_snapshot_of_a_hidden_window_and_maximized(self) -> None:
        """Save a non-blank image while hidden; SHOW can maximize."""
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run(
                [sys.executable, "-c", _SNAPSHOT_PROBE, folder],
                cwd=Path(__file__).resolve().parents[2],
                env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
                capture_output=True, text=True, timeout=15, check=False,
            )
        self.assertEqual(result.returncode, 0,
                         result.stdout + result.stderr)
        # Only the offscreen platform cannot raise a window.
        self.assertEqual(result.stderr.replace(
            "This plugin does not support raise()\n", ""), "")


if __name__ == "__main__":
    unittest.main()
