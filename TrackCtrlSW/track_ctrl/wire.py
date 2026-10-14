"""JSON forms of the module's boundary types, for a test link.

Pure functions, no Qt. Every per-block mapping travels as a list of
entries, each naming its block as ``{"line", "block_id"}``. Decoding is
strict: a message from another process is untrusted, so anything that is
not exactly the expected shape raises ``WireFormatError``. Unknown keys
are an error too, so a sender and a receiver that disagree about the
contract find out at once.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Mapping, TypeVar

from track_ctrl.errors import WireFormatError
from track_ctrl.interface import (
    SIGNAL_ASPECTS,
    SWITCH_POSITIONS,
    BlockKey,
    BlockReport,
    CtcInputs,
    CtcReport,
    Suggestion,
    TrackCircuitCommand,
    TrackControllerInputs,
    TrackControllerOutputs,
    TrackControllerSnapshot,
    TrackModelInputs,
    TrackModelOutputs,
)

T = TypeVar("T")


# ------------------------------------------------------------------ #
# Strict readers
# ------------------------------------------------------------------ #

def _object(value: Any, where: str, keys: set[str]) -> Mapping[str, Any]:
    """Return ``value`` if it is a dict with exactly ``keys``."""
    if not isinstance(value, dict):
        raise WireFormatError(f"{where} must be an object")
    found = set(value)
    if found != keys:
        missing = sorted(keys - found)
        extra = sorted(found - keys)
        detail = (f"missing {missing}" if missing else "") + (
            f" unexpected {extra}" if extra else ""
        )
        raise WireFormatError(f"{where} has the wrong keys:{detail}")
    return value


def _list(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise WireFormatError(f"{where} must be a list")
    return value


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str):
        raise WireFormatError(f"{where} must be a string")
    return value


def _flag(value: Any, where: str) -> bool:
    if not isinstance(value, bool):
        raise WireFormatError(f"{where} must be true or false")
    return value


def _whole(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise WireFormatError(f"{where} must be a whole number, 0 or more")
    return value


def _seconds(value: Any, where: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise WireFormatError(f"{where} must be finite and 0 or more")
    return float(value)


def _choice(value: Any, where: str, allowed: tuple[str, ...]) -> Any:
    if value not in allowed:
        raise WireFormatError(f"{where} must be one of {list(allowed)}")
    return value


# ------------------------------------------------------------------ #
# Blocks and per-block mappings
# ------------------------------------------------------------------ #

def block_to_wire(key: BlockKey) -> dict[str, str]:
    """One block as ``{"line", "block_id"}``."""
    return {"line": key.line, "block_id": key.block_id}


def block_from_wire(value: Any, where: str = "block") -> BlockKey:
    """Read one block."""
    entry = _object(value, where, {"line", "block_id"})
    return BlockKey(
        _text(entry["line"], f"{where}.line"),
        _text(entry["block_id"], f"{where}.block_id"),
    )


def _map_to_wire(
    values: Mapping[BlockKey, T], encode: Callable[[T], Any]
) -> list[dict[str, Any]]:
    return [
        {"block": block_to_wire(key), "value": encode(value)}
        for key, value in values.items()
    ]


def _map_from_wire(
    value: Any, where: str, decode: Callable[[Any, str], T]
) -> dict[BlockKey, T]:
    found: dict[BlockKey, T] = {}
    for position, item in enumerate(_list(value, where)):
        spot = f"{where}[{position}]"
        entry = _object(item, spot, {"block", "value"})
        key = block_from_wire(entry["block"], f"{spot}.block")
        if key in found:
            raise WireFormatError(f"{spot}: {key.label} appears twice")
        found[key] = decode(entry["value"], f"{spot}.value")
    return found


def _set_to_wire(keys: Any) -> list[dict[str, str]]:
    return [block_to_wire(key) for key in keys]


def _set_from_wire(value: Any, where: str) -> frozenset[BlockKey]:
    keys = [
        block_from_wire(item, f"{where}[{position}]")
        for position, item in enumerate(_list(value, where))
    ]
    return frozenset(keys)


def _position(value: Any, where: str) -> Any:
    return _choice(value, where, SWITCH_POSITIONS)


def _aspect(value: Any, where: str) -> Any:
    return _choice(value, where, SIGNAL_ASPECTS)


def _suggestion_to_wire(value: Suggestion) -> dict[str, int]:
    return {
        "speed_mps": value.speed_mps,
        "authority_blocks": value.authority_blocks,
    }


def _suggestion_from_wire(value: Any, where: str) -> Suggestion:
    entry = _object(value, where, {"speed_mps", "authority_blocks"})
    return Suggestion(
        _whole(entry["speed_mps"], f"{where}.speed_mps"),
        _whole(entry["authority_blocks"], f"{where}.authority_blocks"),
    )


def _circuit_to_wire(value: TrackCircuitCommand) -> dict[str, int]:
    return {
        "speed_mps": value.speed_mps,
        "authority_blocks": value.authority_blocks,
    }


def _circuit_from_wire(value: Any, where: str) -> TrackCircuitCommand:
    entry = _object(value, where, {"speed_mps", "authority_blocks"})
    return TrackCircuitCommand(
        _whole(entry["speed_mps"], f"{where}.speed_mps"),
        _whole(entry["authority_blocks"], f"{where}.authority_blocks"),
    )


# ------------------------------------------------------------------ #
# Inputs
# ------------------------------------------------------------------ #

def inputs_to_wire(inputs: TrackControllerInputs) -> dict[str, Any]:
    """One tick of inputs as JSON-ready data."""
    ctc = inputs.ctc
    model = inputs.track_model
    return {
        "time_s": inputs.time_s,
        "ctc": {
            "maintenance_mode": ctc.maintenance_mode,
            "closed_blocks": _set_to_wire(ctc.closed_blocks),
            "switch_commands": _map_to_wire(ctc.switch_commands, str),
            "suggestions": _map_to_wire(
                ctc.suggestions, _suggestion_to_wire
            ),
        },
        "track_model": {
            "occupied_blocks": _set_to_wire(model.occupied_blocks),
            "switch_positions": _map_to_wire(model.switch_positions, str),
            "crossings_active": _map_to_wire(model.crossings_active, bool),
            "signal_aspects": _map_to_wire(model.signal_aspects, str),
        },
    }


def inputs_from_wire(value: Any) -> TrackControllerInputs:
    """Read one tick of inputs, rejecting anything not exactly right."""
    top = _object(value, "inputs", {"time_s", "ctc", "track_model"})
    ctc = _object(
        top["ctc"], "inputs.ctc",
        {"maintenance_mode", "closed_blocks", "switch_commands",
         "suggestions"},
    )
    model = _object(
        top["track_model"], "inputs.track_model",
        {"occupied_blocks", "switch_positions", "crossings_active",
         "signal_aspects"},
    )
    return TrackControllerInputs(
        time_s=_seconds(top["time_s"], "inputs.time_s"),
        ctc=CtcInputs(
            maintenance_mode=_flag(
                ctc["maintenance_mode"], "inputs.ctc.maintenance_mode"
            ),
            closed_blocks=_set_from_wire(
                ctc["closed_blocks"], "inputs.ctc.closed_blocks"
            ),
            switch_commands=_map_from_wire(
                ctc["switch_commands"], "inputs.ctc.switch_commands",
                _position,
            ),
            suggestions=_map_from_wire(
                ctc["suggestions"], "inputs.ctc.suggestions",
                _suggestion_from_wire,
            ),
        ),
        track_model=TrackModelInputs(
            occupied_blocks=_set_from_wire(
                model["occupied_blocks"], "inputs.track_model.occupied_blocks"
            ),
            switch_positions=_map_from_wire(
                model["switch_positions"],
                "inputs.track_model.switch_positions", _position,
            ),
            crossings_active=_map_from_wire(
                model["crossings_active"],
                "inputs.track_model.crossings_active", _flag,
            ),
            signal_aspects=_map_from_wire(
                model["signal_aspects"],
                "inputs.track_model.signal_aspects", _aspect,
            ),
        ),
    )


# ------------------------------------------------------------------ #
# Outputs
# ------------------------------------------------------------------ #

def _optional(value: Any, where: str, read: Callable[[Any, str], T]) -> Any:
    return None if value is None else read(value, where)


def _report_to_wire(report: CtcReport) -> dict[str, Any]:
    return {
        "wayside_id": report.wayside_id,
        "sent_at_s": report.sent_at_s,
        "blocks": _map_to_wire(
            report.blocks,
            lambda each: {
                "occupied": each.occupied,
                "switch_position": each.switch_position,
                "crossing_active": each.crossing_active,
                "signal_aspect": each.signal_aspect,
            },
        ),
    }


def _block_report_from_wire(value: Any, where: str) -> BlockReport:
    entry = _object(
        value, where,
        {"occupied", "switch_position", "crossing_active", "signal_aspect"},
    )
    return BlockReport(
        occupied=_flag(entry["occupied"], f"{where}.occupied"),
        switch_position=_optional(
            entry["switch_position"], f"{where}.switch_position", _position
        ),
        crossing_active=_optional(
            entry["crossing_active"], f"{where}.crossing_active",
            lambda item, spot: _flag(item, spot),
        ),
        signal_aspect=_optional(
            entry["signal_aspect"], f"{where}.signal_aspect", _aspect
        ),
    )


def _report_from_wire(value: Any, where: str) -> CtcReport:
    entry = _object(value, where, {"wayside_id", "sent_at_s", "blocks"})
    return CtcReport(
        wayside_id=_text(entry["wayside_id"], f"{where}.wayside_id"),
        sent_at_s=_seconds(entry["sent_at_s"], f"{where}.sent_at_s"),
        blocks=_map_from_wire(
            entry["blocks"], f"{where}.blocks", _block_report_from_wire
        ),
    )


def outputs_to_wire(outputs: TrackControllerOutputs) -> dict[str, Any]:
    """One tick of outputs as JSON-ready data."""
    model = outputs.track_model
    return {
        "track_model": {
            "track_circuits": _map_to_wire(
                model.track_circuits, _circuit_to_wire
            ),
            "switch_commands": _map_to_wire(model.switch_commands, str),
            "crossing_commands": _map_to_wire(model.crossing_commands, bool),
            "signal_commands": _map_to_wire(model.signal_commands, str),
        },
        "ctc_reports": [_report_to_wire(each) for each in outputs.ctc_reports],
    }


def outputs_from_wire(value: Any) -> TrackControllerOutputs:
    """Read one tick of outputs, rejecting anything not exactly right."""
    top = _object(value, "outputs", {"track_model", "ctc_reports"})
    model = _object(
        top["track_model"], "outputs.track_model",
        {"track_circuits", "switch_commands", "crossing_commands",
         "signal_commands"},
    )
    return TrackControllerOutputs(
        track_model=TrackModelOutputs(
            track_circuits=_map_from_wire(
                model["track_circuits"],
                "outputs.track_model.track_circuits", _circuit_from_wire,
            ),
            switch_commands=_map_from_wire(
                model["switch_commands"],
                "outputs.track_model.switch_commands", _position,
            ),
            crossing_commands=_map_from_wire(
                model["crossing_commands"],
                "outputs.track_model.crossing_commands", _flag,
            ),
            signal_commands=_map_from_wire(
                model["signal_commands"],
                "outputs.track_model.signal_commands", _aspect,
            ),
        ),
        ctc_reports=tuple(
            _report_from_wire(item, f"outputs.ctc_reports[{position}]")
            for position, item in enumerate(
                _list(top["ctc_reports"], "outputs.ctc_reports")
            )
        ),
    )


# ------------------------------------------------------------------ #
# Snapshot (encode only: the UI reads it, nothing sends one back)
# ------------------------------------------------------------------ #

def snapshot_to_wire(snapshot: TrackControllerSnapshot) -> dict[str, Any]:
    """The module's observable state as JSON-ready data."""
    return {
        "maintenance_mode": snapshot.maintenance_mode,
        "time_s": snapshot.time_s,
        "ticks": snapshot.ticks,
        "waysides": [
            {
                "wayside_id": each.wayside_id,
                "line": each.line,
                "blocks": _set_to_wire(each.blocks),
                "program": None if each.program is None else {
                    "file_name": each.program.file_name,
                    "iteration": each.program.iteration,
                    "checksum": each.program.checksum,
                    "boolean_count": each.program.boolean_count,
                    "statement_count": each.program.statement_count,
                },
                "switches": [
                    {
                        "switch": block_to_wire(state.switch),
                        "commanded": state.commanded,
                        "reported": state.reported,
                    }
                    for state in each.switches
                ],
                "signal_commands": _map_to_wire(each.signal_commands, str),
                "signal_reports": _map_to_wire(each.signal_reports, str),
                "crossing_commands": _map_to_wire(
                    each.crossing_commands, bool
                ),
                "crossing_reports": _map_to_wire(each.crossing_reports, bool),
                "track_circuits": _map_to_wire(
                    each.track_circuits, _circuit_to_wire
                ),
                "occupied_blocks": _set_to_wire(each.occupied_blocks),
                "closed_blocks": _set_to_wire(each.closed_blocks),
                "suggestions": _map_to_wire(
                    each.suggestions, _suggestion_to_wire
                ),
                "overrides": [
                    {
                        "rule": item.rule,
                        "target": item.target,
                        "message": item.message,
                    }
                    for item in each.overrides
                ],
                "report": None if each.report is None
                else _report_to_wire(each.report),
            }
            for each in snapshot.waysides
        ],
    }
