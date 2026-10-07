"""Render the Track Controller test UI to a PNG for visual review.

    python TrackCtrlHw/test_ui/capture.py out.png
    python TrackCtrlHw/test_ui/capture.py out.png --size 720 450

Start the Track Controller window first to capture the test UI
connected; otherwise it shows its waiting state.
"""

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QTimer

from app import TestWindow


def main() -> int:
    """Load the window, grab one frame, write it to disk and exit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", nargs="?", default="track-ctrl-test.png")
    parser.add_argument("--size", nargs=2, type=int, metavar=("W", "H"))
    parser.add_argument("--block", help="select this block, e.g. C-12")
    parser.add_argument("--send", type=int, default=0,
                        help="send the inputs this many times first")
    args = parser.parse_args()

    window = TestWindow(sys.argv[:1])
    if window.window is None:
        return 1
    if args.size:
        window.window.resize(*args.size)

    def prepare() -> None:
        if args.block:
            window.harness.selectBlock(args.block)
        for _ in range(args.send):
            window.harness.sendInputs()

    def grab() -> None:
        window.window.grabWindow().save(str(Path(args.out)))
        window.app.quit()

    # Give the link time to connect before preparing, and the layout
    # time to settle before the capture.
    QTimer.singleShot(1200, prepare)
    QTimer.singleShot(2200, grab)
    exit_code = window.app.exec()
    window.shutdown()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
