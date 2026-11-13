"""Start the Track Controller window and its test UI, each in its own
process.

    python TrackCtrlHw/launch.py
    python TrackCtrlHw/launch.py --no-test-ui

The two find each other over a local socket; either can be started on
its own, in either order. Closing one leaves the other running; this
launcher waits until both have closed. Ctrl+C closes both.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent
TRACK_CONTROLLER = MODULE_ROOT / "ui" / "main.py"
TEST_UI = MODULE_ROOT / "test_ui" / "main.py"


def main() -> int:
    """Spawn the windows and wait for them to close."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-test-ui",
        action="store_true",
        help="start only the Track Controller window",
    )
    args = parser.parse_args()

    scripts = [TRACK_CONTROLLER]
    if not args.no_test_ui:
        scripts.append(TEST_UI)
    # The same interpreter, so both run in the same environment. Each
    # script's own folder is its working directory for its imports.
    children = [
        subprocess.Popen([sys.executable, str(script)], cwd=script.parent)
        for script in scripts
    ]
    try:
        codes = [child.wait() for child in children]
    except KeyboardInterrupt:
        for child in children:
            child.terminate()
        for child in children:
            child.wait()
        return 130
    return max(codes)


if __name__ == "__main__":
    sys.exit(main())
