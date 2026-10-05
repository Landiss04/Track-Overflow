"""Dispatcher actions by name, for the test links.

The test UI's links (``ctc.link.LocalLink`` and the socket link) send
dispatcher actions as ``(op, args)`` pairs. This module turns one pair
into the module call, checking every argument's type strictly: a
true/false argument must be a real boolean, never a string such as
``"false"`` (which Python would read as true).

``apply_batch`` applies a test UI's Send all or nothing: inputs and
actions are first tried on a copy of the module, and only if every one
succeeds are they applied to the module itself.
"""

from __future__ import annotations

import copy
from typing import Any, Callable, Mapping, Sequence

from ctc.interface import CtcInputs, CtcOffice
from ctc.model import InvalidInputError

Action = tuple[str, Mapping[str, Any]]


def _string(args: Mapping[str, Any], key: str) -> str:
    value = args[key]
    if not isinstance(value, str):
        raise InvalidInputError(f"{key} must be a string, got {value!r}")
    return value


def _bool(args: Mapping[str, Any], key: str) -> bool:
    value = args[key]
    if not isinstance(value, bool):
        raise InvalidInputError(
            f"{key} must be true or false, got {value!r}")
    return value


def _arrival(args: Mapping[str, Any]) -> float | None:
    value = args.get("arrival_s")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidInputError(
            f"arrival_s must be a number of seconds, got {value!r}")
    return float(value)


def apply_action(module: CtcOffice, op: str,
                 args: Mapping[str, Any]) -> None:
    """Run one dispatcher action on the module, or raise."""
    if not isinstance(args, Mapping):
        raise InvalidInputError(f"{op}: args must be an object")
    if op == "dispatch":
        module.dispatch(_string(args, "train_id"), _string(args, "line"),
                        _string(args, "destination_block_id"),
                        _arrival(args))
    elif op == "cancel_dispatch":
        module.cancel_dispatch(_string(args, "train_id"))
    elif op == "set_block_closed":
        module.set_block_closed(_string(args, "line"),
                                _string(args, "block_id"),
                                _bool(args, "closed"))
    elif op == "set_switch":
        module.set_switch(_string(args, "line"), _string(args, "switch_id"),
                          _string(args, "position"))  # type: ignore[arg-type]
    elif op == "release_switch":
        module.release_switch(_string(args, "line"),
                              _string(args, "switch_id"))
    elif op == "set_maintenance_mode":
        module.set_maintenance_mode(_bool(args, "active"))
    elif op == "set_clock_speedup":
        module.set_clock_speedup(_bool(args, "active"))
    else:
        raise InvalidInputError(f"unknown action {op!r}")


def apply_batch(module: CtcOffice, inputs: CtcInputs | None,
                actions: Sequence[Action],
                take_inputs: Callable[[CtcOffice, CtcInputs, bool], None],
                ) -> None:
    """Apply inputs, then actions, all or nothing.

    ``take_inputs(module, inputs, trial)`` hands inputs to a module; it
    is called with ``trial=True`` on the copy and ``trial=False`` on the
    real module (where it may also latch them for the clock). The
    inputs go first, so the actions' safety checks see them.
    """
    trial = copy.deepcopy(module)
    if inputs is not None:
        take_inputs(trial, inputs, True)
    for op, args in actions:
        apply_action(trial, op, args)
    if inputs is not None:
        take_inputs(module, inputs, False)
    for op, args in actions:
        apply_action(module, op, args)
