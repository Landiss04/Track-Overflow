"""Launcher for the Track Controller window.

The window hosts the module and serves it to the test UI, which runs in
its own process (``TrackCtrlHw/test_ui/main.py``). Run from the
repository root:

    python TrackCtrlHw/ui/main.py

or start both windows at once with ``python TrackCtrlHw/launch.py``.
"""

import sys

from app import Window


def main() -> int:
    """Run the Track Controller window until it is closed."""
    window = Window(sys.argv)
    if window.window is None:
        print("Failed to load the Track Controller window.", file=sys.stderr)
        return 1
    if not window.state.listen():
        print(
            "Another Track Controller is already serving a test UI; this "
            "window runs without one.",
            file=sys.stderr,
        )
    exit_code = window.app.exec()
    window.shutdown()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
