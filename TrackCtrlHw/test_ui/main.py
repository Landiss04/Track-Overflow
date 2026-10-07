"""Launcher for the Track Controller test UI.

The test UI runs in its own process and window, separate from the Track
Controller window, and connects to it by itself. Run from the
repository root:

    python TrackCtrlHw/test_ui/main.py

or start both windows at once with ``python TrackCtrlHw/launch.py``.
"""

import sys

from app import TestWindow


def main() -> int:
    """Run the test UI until it is closed."""
    window = TestWindow(sys.argv)
    if window.window is None:
        print("Failed to load the test UI.", file=sys.stderr)
        return 1
    exit_code = window.app.exec()
    window.shutdown()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
