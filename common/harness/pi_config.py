"""Explicit startup selection of physical or simulated hardware Pis."""

from __future__ import annotations

import json
from pathlib import Path

PI_MODULES = ("track-controller-hw", "train-controller-hw")
PI_MODES = ("physical", "process", "pty")


def _validated_config(value: object, source: str) -> dict[str, bool]:
    """Check the exact module names and Boolean simulation toggles."""
    if not isinstance(value, dict):
        raise ValueError(f"{source}: expected a JSON object of Pi toggles")
    unknown = set(value) - set(PI_MODULES)
    if unknown:
        raise ValueError(
            f"{source}: unknown Pi module(s): {', '.join(sorted(unknown))}; "
            f"expected only {', '.join(PI_MODULES)}"
        )
    for module, simulated in value.items():
        if not isinstance(simulated, bool):
            raise ValueError(
                f"{source}: {module} must be a JSON Boolean (true or false)"
            )
    return dict(value)


def load_pi_config(path: Path) -> dict[str, bool]:
    """Read an explicitly selected config, rejecting invalid input.

    Missing module keys mean physical hardware. File and format errors
    raise ValueError so the CLI can reject them before starting Qt.
    """
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read Pi config {path}: {error}") from error
    return _validated_config(value, f"Pi config {path}")


def resolve_pi_modes(
    config: dict[str, bool],
    test_pi: str | None = None,
    track_controller_pi: str | None = None,
    train_controller_pi: str | None = None,
) -> dict[str, str]:
    """Resolve defaults, file toggles, global CLI, then individual CLI.

    A true file toggle selects the existing process simulator. Without
    a file or CLI options, both modules use physical hardware.
    """
    toggles = _validated_config(config, "Pi config")
    modes = {
        module: "process" if toggles.get(module, False) else "physical"
        for module in PI_MODULES
    }
    if test_pi is not None:
        if test_pi not in ("process", "pty"):
            raise ValueError("--test-pi must be process or pty")
        modes = dict.fromkeys(PI_MODULES, test_pi)
    for module, mode in zip(
        PI_MODULES, (track_controller_pi, train_controller_pi)
    ):
        if mode is not None:
            if mode not in PI_MODES:
                raise ValueError(
                    f"{module}: expected one of {', '.join(PI_MODES)}"
                )
            modes[module] = mode
    return modes
