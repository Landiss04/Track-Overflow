"""HW Train Controller — driver / engineer console (ECE1140 Team 3).

Run, with the project virtual environment's interpreter
(truth conventions/toolchain.md):

    python main.py                         the driver's console
    python main.py --test                  the Train Model bench
    python main.py --both                  both windows, one backend
    python main.py --check [--shots DIR]   offscreen self-test

The console and the bench are separate windows. They share a
controller only when one process opens both, which is what --both
is for and how the bench drives the console.

Everything else lives in train_ctrl/: the control law, the fleet,
the Qt bridge, and train_ctrl/app.py, which opens the windows.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# The shared ui/ library sits at the repository root. After this
# folder, so this module's own check.py is never shadowed.
sys.path.insert(1, str(Path(__file__).resolve().parents[1]))

from train_ctrl.app import run  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--test", action="store_true",
                        help="open the Train Model bench instead")
    parser.add_argument("--both", action="store_true",
                        help="open the console and the bench together")
    parser.add_argument("--check", action="store_true",
                        help="run offscreen, exercise the console, report")
    parser.add_argument("--shots", metavar="DIR",
                        help="with --check, save screenshots to DIR")
    return parser.parse_args()


def main() -> int:
    """Open the console, the bench, or both."""
    args = _parse_args()
    return run(
        console=args.both or args.check or not args.test,
        bench=args.both or args.check or args.test,
        check=args.check,
        shots=Path(args.shots) if args.shots else None,
    )


if __name__ == "__main__":
    raise SystemExit(main())
