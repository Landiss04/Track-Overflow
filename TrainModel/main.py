"""Application entry point for the Train Model window.

The window shows one train of a :class:`TrainModelFleet`. Standalone,
the fleet holds a single train, which the test UI (a separate process,
``test_ui.py``) drives through its interface over the link served
here. Once the system is integrated, the central harness owns the
fleet and adds a train for each one in service.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QObject

from train_model.app import run_window
from train_model.fleet import TrainModelFleet
from train_model.link import TestLinkServer

# The one train the test UI drives. Its line is left unknown: the test
# UI picks the line in its own process.
TEST_TRAIN_ID = "T-1"


def main() -> int:
    """Run the Train Model window and serve it to the test UI."""

    def build_context() -> dict[str, QObject]:
        fleet = TrainModelFleet()
        train_model = fleet.add(TEST_TRAIN_ID)
        server = TestLinkServer(train_model, parent=train_model)
        if not server.listen():
            print(
                "Test UI link unavailable: another Train Model is "
                "running, or the link could not be opened.",
                file=sys.stderr,
            )
        return {"fleet": fleet}

    return run_window("Train Model", "Main.qml", build_context)


if __name__ == "__main__":
    raise SystemExit(main())
