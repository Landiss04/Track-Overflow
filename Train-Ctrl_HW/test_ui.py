"""Application entry point for the Train Model test UI window.

Runs as its own process, standing in for the Track Model, the Train
Controller and the clock. It drives the Train Model started by
``main.py`` through the module's interface, connecting whenever that
process is up.

The stand-in Track Model loads the Blue Line unless told otherwise:

    python test_ui.py                         # Blue Line, to Station B
    python test_ui.py --line green            # Green Line loop from the yard
    python test_ui.py --line red --route 9-1,16-66
"""

from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QObject

from train_model.app import run_window
from train_model.harness import TestHarnessState
from train_model.link import SocketLink
from train_model.track_stub import (
    DEFAULT_ROUTES,
    LINE_FILES,
    TrackStub,
    load_line,
)


def parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    """Read the test UI's own flags; return the rest for Qt.

    Args:
        argv: The command-line arguments after the program name.

    Returns:
        The parsed flags, and every argument left for Qt.
    """
    parser = argparse.ArgumentParser(
        prog="test_ui.py",
        description="Train Model test UI.",
    )
    parser.add_argument(
        "--line", choices=sorted(LINE_FILES), default="blue",
        help="the line the stand-in Track Model loads (default: blue)",
    )
    parser.add_argument(
        "--route", metavar="RANGES",
        help="blocks to travel, in order, as ranges such as 63-100,85-77;"
        " a range that counts down runs against the block numbering."
        " Defaults: " + "; ".join(
            f"{line} {route}" for line, route in DEFAULT_ROUTES.items()),
    )
    return parser.parse_known_args(argv)


def load_track(args: argparse.Namespace) -> TrackStub:
    """Load the line and route the flags name, or exit with the reason."""
    try:
        return load_line(args.line, args.route)
    except (OSError, ValueError, KeyError) as exc:
        sys.exit(f"test_ui.py: cannot load the {args.line} line: {exc}")


def main(argv: list[str] | None = None) -> int:
    """Run the test UI window against the Train Model process."""
    args, qt_args = parse_args(sys.argv[1:] if argv is None else argv)
    track = load_track(args)
    # Qt reads its own options from sys.argv; hand it only those.
    sys.argv = [sys.argv[0], *qt_args]

    def build_context() -> dict[str, QObject]:
        link = SocketLink()
        harness = TestHarnessState(link, parent=link, track=track)
        return {"harness": harness}

    return run_window("Train Model Test UI", "TestMain.qml", build_context)


if __name__ == "__main__":
    raise SystemExit(main())
