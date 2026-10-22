"""Wire protocol between the central harness and the module processes.

The harness runs each module in a process of its own and drives it
over a Qt local socket: a named pipe on Windows and a socket file
elsewhere, never a network connection (decision D005). The same
messages travel over USB serial to a Raspberry Pi (D027).

Every message is one JSON object on one line, ended by ``\\n``. Each
carries:

- ``op``: what the message is, in capitals, like every enumerated
  value that crosses a module boundary (``conventions/naming.md``);
- ``id``: an integer request ID. A reply carries the ID of the request
  it answers. A message nobody asked for carries 0;
- ``tick``: the tick it belongs to, 0 before the first tick.

Numbers are finite and within the range of a double, and text is valid
Unicode, sent as UTF-8. A line that breaks either is refused, at either
end: ``1e999`` is valid JSON text, but would come out as infinity.

Harness to module:

- ``STEP``: step once. ``{"op": "STEP", "id": 41, "tick": 12, "dt": 0.1,
  "sim_time_s": 18001.2, "inputs": {...}}``. ``sim_time_s`` is the
  unwrapped simulation time at the end of the step (D017).
- ``QUIT``: end the process.
- ``SHOW``: reopen the module window; no reply (additive in v1).
- ``CLOCK_STATE``: actual harness pause/speed state for HW hosts, initially
  and on transitions, including between steps (additive in v1). Carries
  id 0 and state with boolean clock_paused and clock_speedup.

Module to harness:

- ``READY``: the module is loaded and can step. ``{"op": "READY",
  "id": 0, "tick": 0, "module": "ctc-office", "protocol": 1}``.
- ``OUTPUTS``: the reply to a ``STEP``, with ``outputs``.
- ``REJECTED``: the reply to a ``STEP`` the module refused, with a
  ``reason``. The module's state did not change.
- ``STATE``: a change made between ticks, with ``state``. The harness
  reads the CTC Office's ``clock_paused`` this way while the clock is
  paused, since no step runs then.

This module is free of Qt so both sides, and tests, can share it.
"""

from __future__ import annotations

__all__ = [
    "MAX_LINE_BYTES",
    "MODULE_TO_HARNESS",
    "HARNESS_TO_MODULE",
    "OUTPUTS",
    "PROTOCOL_VERSION",
    "ProtocolError",
    "QUIT",
    "READY",
    "REJECTED",
    "STATE",
    "SHOW",
    "STEP",
    "CLOCK_STATE",
    "LineBuffer",
    "decode",
    "encode",
    "outputs_message",
    "quit_message",
    "ready_message",
    "rejected_message",
    "state_message",
    "show_message",
    "step_message",
    "validate",
]

import json
import math
import re
import sys
from collections.abc import Mapping
from typing import Any, TypeGuard

#: Bumped for incompatible changes; additive SHOW remains in version 1.
PROTOCOL_VERSION = 1

#: Longest line accepted. A module's outputs for one tick stay far
#: below this; a longer line means a broken sender.
MAX_LINE_BYTES = 8 * 1024 * 1024

# An escaped UTF-16 surrogate. Only these let JSON text carry a string
# that is not valid Unicode, so only a line holding one is checked.
_SURROGATE_ESCAPE = re.compile(r"\\u[dD][89a-fA-F]")

# Digits in the largest double; a shorter integer always fits one.
_MAX_FLOAT_DIGITS = len(str(int(sys.float_info.max)))

STEP = "STEP"
QUIT = "QUIT"
READY = "READY"
OUTPUTS = "OUTPUTS"
REJECTED = "REJECTED"
STATE = "STATE"
SHOW = "SHOW"
CLOCK_STATE = "CLOCK_STATE"

HARNESS_TO_MODULE = frozenset({STEP, QUIT, SHOW, CLOCK_STATE})
MODULE_TO_HARNESS = frozenset({READY, OUTPUTS, REJECTED, STATE})

# Fields each message must carry beyond op, id and tick, with a check
# for each value.
_OBJECT = "object"
_STRING = "string"
_INTEGER = "integer"
_POSITIVE_NUMBER = "positive number"
_NUMBER = "number"

_REQUIRED_FIELDS: dict[str, dict[str, str]] = {
    STEP: {
        "dt": _POSITIVE_NUMBER,
        "sim_time_s": _NUMBER,
        "inputs": _OBJECT,
    },
    QUIT: {},
    SHOW: {},
    READY: {"module": _STRING, "protocol": _INTEGER},
    OUTPUTS: {"outputs": _OBJECT},
    REJECTED: {"reason": _STRING},
    STATE: {"state": _OBJECT},
    CLOCK_STATE: {"state": _OBJECT},
}


class ProtocolError(ValueError):
    """A line or message that does not follow the protocol."""


def encode(message: Mapping[str, Any]) -> bytes:
    """Return ``message`` as one wire line, ending in a newline.

    Args:
        message: A message built by one of the ``*_message`` helpers,
            or any mapping that passes ``validate``.

    Returns:
        UTF-8 JSON on a single line.

    Raises:
        ProtocolError: If the message is not valid, or holds a value
            JSON cannot carry, such as NaN or text that is not valid
            Unicode.
    """
    validate(message)
    try:
        text = json.dumps(
            message,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        # Raw UTF-8, so text that is not valid Unicode, such as a lone
        # surrogate from undecodable bytes, fails here, not at the
        # receiver.
        return (text + "\n").encode("utf-8")
    except UnicodeEncodeError as error:
        raise ProtocolError(
            "cannot encode message: text is not valid Unicode"
        ) from error
    except (TypeError, ValueError) as error:
        raise ProtocolError(f"cannot encode message: {error}") from error


def decode(line: bytes) -> dict[str, Any]:
    """Return the message one wire line carries.

    Args:
        line: One line, with or without its newline.

    Returns:
        The message, checked by ``validate``.

    Raises:
        ProtocolError: If the line is not UTF-8 JSON, not an object, or
            not a valid message; if it holds a number past the range of
            a double, which other ends would read as infinite; or if it
            holds text that is not valid Unicode.
    """
    try:
        text = line.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProtocolError("line is not UTF-8") from error
    try:
        message = json.loads(
            text,
            parse_constant=_reject_constant,
            parse_float=_parse_float,
            parse_int=_parse_int,
        )
    except ProtocolError:
        raise
    except RecursionError as error:
        raise ProtocolError("line is nested too deeply") from error
    except ValueError as error:
        raise ProtocolError(f"line is not JSON: {error}") from error
    if not isinstance(message, dict):
        raise ProtocolError("line is not a JSON object")
    if _SURROGATE_ESCAPE.search(text):
        _check_unicode(message)
    validate(message)
    return message


def validate(message: Mapping[str, Any]) -> None:
    """Check that ``message`` has an op, an ID, a tick and its fields.

    Raises:
        ProtocolError: Naming the first thing wrong.
    """
    op = message.get("op")
    if op not in _REQUIRED_FIELDS:
        raise ProtocolError(f"unknown op {op!r}")
    for field in ("id", "tick"):
        value = message.get(field)
        if not _is_integer(value) or value < 0:
            raise ProtocolError(
                f"{op} needs a non-negative integer {field}, got {value!r}"
            )
    for field, kind in _REQUIRED_FIELDS[op].items():
        if field not in message:
            raise ProtocolError(f"{op} is missing {field}")
        if not _has_kind(message[field], kind):
            raise ProtocolError(
                f"{op} {field} must be a {kind}, got {message[field]!r}"
            )
    if op == CLOCK_STATE:
        state = message["state"]
        if message["id"] != 0 or set(state) != {
            "clock_paused", "clock_speedup"
        } or not all(isinstance(value, bool) for value in state.values()):
            raise ProtocolError(
                "CLOCK_STATE needs id 0 and boolean clock_paused/clock_speedup"
            )


def step_message(
    request_id: int,
    tick: int,
    dt: float,
    sim_time_s: float,
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a ``STEP`` for one module."""
    return {
        "op": STEP,
        "id": request_id,
        "tick": tick,
        "dt": dt,
        "sim_time_s": sim_time_s,
        "inputs": dict(inputs),
    }


def quit_message(tick: int) -> dict[str, Any]:
    """Return a ``QUIT``."""
    return {"op": QUIT, "id": 0, "tick": tick}


def show_message(tick: int) -> dict[str, Any]:
    """Return a ``SHOW`` without requesting a reply."""
    return {"op": SHOW, "id": 0, "tick": tick}


def ready_message(module: str) -> dict[str, Any]:
    """Return the ``READY`` a module sends once it can step."""
    return {
        "op": READY,
        "id": 0,
        "tick": 0,
        "module": module,
        "protocol": PROTOCOL_VERSION,
    }


def outputs_message(
    request_id: int, tick: int, outputs: Mapping[str, Any]
) -> dict[str, Any]:
    """Return the ``OUTPUTS`` reply to a ``STEP``."""
    return {
        "op": OUTPUTS,
        "id": request_id,
        "tick": tick,
        "outputs": dict(outputs),
    }


def rejected_message(
    request_id: int, tick: int, reason: str
) -> dict[str, Any]:
    """Return the ``REJECTED`` reply to a ``STEP`` a module refused."""
    return {"op": REJECTED, "id": request_id, "tick": tick, "reason": reason}


def state_message(tick: int, state: Mapping[str, Any]) -> dict[str, Any]:
    """Return a ``STATE`` push for a change made between ticks."""
    return {"op": STATE, "id": 0, "tick": tick, "state": dict(state)}


class LineBuffer:
    """Split a byte stream into wire lines.

    Bytes arrive in arbitrary pieces; ``feed`` returns every line that
    is complete so far and keeps the rest for the next call. A line
    past the size limit is dropped up to its newline and reported in
    its place, so the lines around it still arrive.
    """

    def __init__(self, max_line_bytes: int = MAX_LINE_BYTES) -> None:
        """Create an empty buffer.

        Args:
            max_line_bytes: Longest line accepted, newline excluded.
        """
        self._max_line_bytes = max_line_bytes
        self._pending = bytearray()
        # Dropping the rest of a line already reported as too long.
        self._discarding = False

    def feed(self, data: bytes) -> list[bytes | ProtocolError]:
        """Add ``data`` and return the complete, non-blank lines.

        Returns:
            The lines in order. A line past the size limit is a
            ``ProtocolError`` in its place, once, however many pieces
            it came in; reading goes on from its newline.
        """
        self._pending.extend(data)
        lines: list[bytes | ProtocolError] = []
        while True:
            end = self._pending.find(b"\n")
            if end < 0:
                break
            line = bytes(self._pending[:end]).strip()
            del self._pending[: end + 1]
            if self._discarding:
                # The end of a line already reported.
                self._discarding = False
            elif len(line) > self._max_line_bytes:
                lines.append(_line_too_long())
            elif line:
                lines.append(line)
        if len(self._pending) > self._max_line_bytes:
            # No newline yet, and already too long: report it now and
            # drop the rest of it as it comes.
            self._pending.clear()
            if not self._discarding:
                self._discarding = True
                lines.append(_line_too_long())
        return lines


def _line_too_long() -> ProtocolError:
    # One wording wherever a line is too long.
    return ProtocolError("line is longer than the limit")


def _is_integer(value: Any) -> TypeGuard[int]:
    # bool is an int in Python but never a valid ID or tick.
    return isinstance(value, int) and not isinstance(value, bool)


def _has_kind(value: Any, kind: str) -> bool:
    # One field check; numbers must be finite.
    if kind == _OBJECT:
        return isinstance(value, dict)
    if kind == _STRING:
        return isinstance(value, str) and bool(value)
    if kind == _INTEGER:
        return _is_integer(value)
    is_number = (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )
    if kind == _POSITIVE_NUMBER:
        return is_number and value > 0
    return is_number


def _reject_constant(name: str) -> Any:
    # json accepts NaN and Infinity by default; the protocol does not.
    raise ValueError(f"{name} is not allowed")


def _parse_float(text: str) -> float:
    # 1e999 is valid JSON text, but Python reads it as infinity, which
    # the harness could not send on.
    value = float(text)
    if not math.isfinite(value):
        raise ProtocolError(f"number {text[:40]} is out of range")
    return value


def _parse_int(text: str) -> int:
    # Python reads any integer, but past the largest double no other
    # end can use it as a number. Over 4300 digits ``int`` refuses.
    value = int(text)
    if len(text) > _MAX_FLOAT_DIGITS and abs(value) > sys.float_info.max:
        raise ProtocolError(f"number {text[:40]}... is out of range")
    return value


def _check_unicode(message: Mapping[str, Any]) -> None:
    # An escaped lone surrogate decodes to a str that cannot be written
    # out again, to the event log or anywhere else.
    try:
        json.dumps(message, ensure_ascii=False).encode("utf-8")
    except UnicodeEncodeError as error:
        raise ProtocolError(
            "line holds text that is not valid Unicode"
        ) from error
