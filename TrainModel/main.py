"""Application entry point for the Train Model window.

The test UI is a separate process (``test_ui.py``). It drives this
module through its interface over the link served here; once the
system is integrated, the central harness drives it instead.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QObject

from train_model.app import run_window
from train_model.link import TestLinkServer
from train_model.state import TrainModelState


def main() -> int:
    """Run the Train Model window and serve it to the test UI."""

    def build_context() -> dict[str, QObject]:
        train_model = TrainModelState()
        server = TestLinkServer(train_model, parent=train_model)
        if not server.listen():
            print(
                "Test UI link unavailable: another Train Model is "
                "running, or the link could not be opened.",
                file=sys.stderr,
            )
        return {"trainModel": train_model}

    return run_window("Train Model", "Main.qml", build_context)


if __name__ == "__main__":
    raise SystemExit(main())
