"""HW Train Controller — driver / engineer console (ECE1140 Team 3).

Run, with the project virtual environment's interpreter
(truth conventions/toolchain.md):

    python main.py                         the driver's console
    python main.py --test                  the test bench
    python main.py --check [--shots DIR]   offscreen self-test

The bench opens only when asked for. It stands in for the central
harness: spawning a train on the Red Line opens the HW Train
Controller's console, on the Green Line the SW one, each with its own
controller, as the harness has them (REQUIREMENTS.md M13).

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

from train_ctrl.app import run, run_bench  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--test", action="store_true",
                        help="open the test bench, which opens the "
                             "consoles")
    parser.add_argument("--check", action="store_true",
                        help="run offscreen, exercise the console, report")
    parser.add_argument("--shots", metavar="DIR",
                        help="with --check, save screenshots to DIR")
    return parser.parse_args()


def main() -> int:
    """Open the console, or the bench and the consoles it spawns."""
    args = _parse_args()
    if args.test and not args.check:
        return run_bench()
    return run(
        console=True,
        bench=args.check,
        check=args.check,
        shots=Path(args.shots) if args.shots else None,
    )


if __name__ == "__main__":
    raise SystemExit(main())
