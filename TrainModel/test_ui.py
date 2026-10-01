"""Application entry point for the Train Model test UI window.

Runs as its own process, standing in for the Track Model, the Train
Controller and the clock. It drives the Train Model started by
``main.py`` through the module's interface, connecting whenever that
process is up.
"""

from __future__ import annotations

from PySide6.QtCore import QObject

from train_model.app import run_window
from train_model.harness import TestHarnessState
from train_model.link import SocketLink


def main() -> int:
    """Run the test UI window against the Train Model process."""

    def build_context() -> dict[str, QObject]:
        link = SocketLink()
        harness = TestHarnessState(link, parent=link)
        return {"harness": harness}

    return run_window("Train Model Test UI", "TestMain.qml", build_context)


if __name__ == "__main__":
    raise SystemExit(main())
