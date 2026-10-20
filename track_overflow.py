"""Track Overflow: the one executable for the whole system.

Run with no arguments, it starts the central harness. The harness
starts every module by running this same program again with
``--module <name>`` (``conventions/files-and-paths``; G-RUN-2 in
``documents/system-integration-design.md``).

``stub`` stands in for any of the seven modules. The real modules are
wired in one phase at a time: Phase 1 adds the Train Model and the
Train Controller SW, Phase 2 the Track Model, and Phase 3 the Track
Controller SW.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

EXIT_USAGE = 2

# The repository root, or a built executable's bundle root, where the
# module folders sit as they do in the source.
_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def main(argv: Sequence[str] | None = None) -> int:
    """Start the harness, or one module with ``--module <name>``.

    Args:
        argv: The command line after the program name; defaults to
            ``sys.argv[1:]``.

    Returns:
        The exit code.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--module")
    known, rest = parser.parse_known_args(args)
    if known.module is None:
        # Imported here, so a module process loads only its own code.
        from common.harness import app

        return app.main(rest)
    run_module = _MODULES.get(known.module)
    if run_module is None:
        print(
            f"track_overflow: no module {known.module!r} yet; "
            f"modules: {', '.join(sorted(_MODULES))}",
            file=sys.stderr,
        )
        return EXIT_USAGE
    return run_module(rest)


def _run_stub(args: list[str]) -> int:
    # Imported on use, which also lets a frozen build find it.
    from common.harness import stub_module

    return stub_module.main(args)


def _run_track_controller_sw(args: list[str]) -> int:
    # The Track Controller's package sits in its own folder, beside its
    # window's QML; its layouts are the Track Model's files.
    _import_from("TrackCtrlSW")
    from track_ctrl import module_process

    return module_process.main(args)


def _run_track_model(args: list[str]) -> int:
    # The Track Model's package sits in its own folder, beside its
    # layout files and its window's QML.
    _import_from("TrackModel")
    from track_model import module_process

    return module_process.main(args)


def _run_train_model(args: list[str]) -> int:
    # The Train Model's package sits in its own folder.
    _import_from("TrainModel")
    from train_model import module_process

    return module_process.main(args)


def _run_train_controller_sw(args: list[str]) -> int:
    # The Train Controller's package and its check.py sit in its own
    # folder; the hyphen keeps that folder from being a package.
    _import_from("Train-Ctrl_HW")
    from train_ctrl import module_process

    return module_process.main(["--as", "train-controller-sw", *args])


def _import_from(folder: str) -> None:
    # Put one module's folder first on the import path.
    sys.path.insert(0, str(_ROOT / folder))


# Every module this executable can run, by its --module name.
_MODULES: dict[str, Callable[[list[str]], int]] = {
    "stub": _run_stub,
    "track-controller-sw": _run_track_controller_sw,
    "track-model": _run_track_model,
    "train-model": _run_train_model,
    "train-controller-sw": _run_train_controller_sw,
}


if __name__ == "__main__":
    sys.exit(main())
