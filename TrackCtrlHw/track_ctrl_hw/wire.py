"""JSON forms of the module's boundary types, for the test UI link.

Every per-block mapping travels as a list of entries, each naming its
block as ``{"line", "section", "block_id"}``. Decoding is strict: a
message from another process is untrusted, so anything that is not
exactly the expected shape raises ``WireFormatError``.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Mapping, TypeVar

from track_ctrl_hw.errors import WireFormatError
from track_ctrl_hw.interface import (
    FAILURE_KINDS,
    SIGNAL_ASPECTS,
    SWITCH_POSITIONS,
    Block,
    BlockKey,
    BlockReport,
    CtcInputs,
    CtcReport,
    Suggestion,
    Switch,
    Territory,
    TrackCircuitCommand,
    TrackControllerInputs,
    TrackControllerOutputs,
    TrackModelInputs,
    TrackModelOutputs,
)

T = TypeVar("T")


# ------------------------------------------------------------------ #
# Blocks
# ------------------------------------------------------------------ #

def key_to_wire(key: BlockKey) -> dict[str, str]:
    """Encode a block key."""
    return {"line": key.line, "section": key.section, "block_id": key.block_id}


def key_from_wire(data: Any) -> BlockKey:
    """Decode a block key."""
    record = _object(data, "block")
    return BlockKey(
        line=_text(record, "line"),
        section=_text(record, "section"),
        block_id=_text(record, "block_id"),
    )


def _entries(
    mapping: Mapping[BlockKey, T], encode: Callable[[T], dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        {"block": key_to_wire(key), **encode(value)}
        for key, value in mapping.items()
    ]


def _from_entries(
    data: Any, name: str, decode: Callable[[Mapping[str, Any]], T]
) -> dict[BlockKey, T]:
    if not isinstance(data, list):
        raise WireFormatError(f"{name} must be a list")
    result: dict[BlockKey, T] = {}
    for entry in data:
        record = _object(entry, name)
        key = key_from_wire(record.get("block"))
        if key in result:
            raise WireFormatError(f"{name} lists {key.label} twice")
        result[key] = decode(record)
    return result


def _key_set(data: Any, name: str) -> frozenset[BlockKey]:
    if not isinstance(data, list):
        raise WireFormatError(f"{name} must be a list")
    return frozenset(key_from_wire(item) for item in data)


# ------------------------------------------------------------------ #
# Inputs and outputs
# ------------------------------------------------------------------ #

def inputs_to_wire(inputs: TrackControllerInputs) -> dict[str, Any]:
    """Encode one tick's inputs."""
    ctc = inputs.ctc
    model = inputs.track_model
    return {
        "time_s": inputs.time_s,
        "ctc": {
            "maintenance_mode": ctc.maintenance_mode,
            "closed_blocks": [key_to_wire(k) for k in ctc.closed_blocks],
            "switch_commands": _entries(
                ctc.switch_commands, lambda p: {"position": p}
            ),
            "suggestions": _entries(
                ctc.suggestions,
                lambda s: {
                    "speed_mps": s.speed_mps,
                    "authority_blocks": s.authority_blocks,
                },
            ),
        },
        "track_model": {
            "occupied_blocks": [
                key_to_wire(k) for k in model.occupied_blocks
            ],
            "failures": _entries(model.failures, lambda f: {"kind": f}),
            "switch_positions": _entries(
                model.switch_positions, lambda p: {"position": p}
            ),
            "crossings_active": _entries(
                model.crossings_active, lambda a: {"active": a}
            ),
            "signal_aspects": _entries(
                model.signal_aspects, lambda a: {"aspect": a}
            ),
        },
    }


def inputs_from_wire(data: Any) -> TrackControllerInputs:
    """Decode one tick's inputs."""
    record = _object(data, "inputs")
    ctc = _object(record.get("ctc"), "ctc")
    model = _object(record.get("track_model"), "track_model")
    return TrackControllerInputs(
        time_s=_number(record, "time_s"),
        ctc=CtcInputs(
            maintenance_mode=_flag(ctc, "maintenance_mode"),
            closed_blocks=_key_set(ctc.get("closed_blocks"), "closed_blocks"),
            switch_commands=_from_entries(
                ctc.get("switch_commands"), "switch_commands",
                lambda r: _choice(r, "position", SWITCH_POSITIONS),
            ),
            suggestions=_from_entries(
                ctc.get("suggestions"), "suggestions",
                lambda r: Suggestion(
                    speed_mps=_count(r, "speed_mps"),
                    authority_blocks=_count(r, "authority_blocks"),
                ),
            ),
        ),
        track_model=TrackModelInputs(
            occupied_blocks=_key_set(
                model.get("occupied_blocks"), "occupied_blocks"
            ),
            failures=_from_entries(
                model.get("failures"), "failures",
                lambda r: _choice(r, "kind", FAILURE_KINDS),
            ),
            switch_positions=_from_entries(
                model.get("switch_positions"), "switch_positions",
                lambda r: _choice(r, "position", SWITCH_POSITIONS),
            ),
            crossings_active=_from_entries(
                model.get("crossings_active"), "crossings_active",
                lambda r: _flag(r, "active"),
            ),
            signal_aspects=_from_entries(
                model.get("signal_aspects"), "signal_aspects",
                lambda r: _choice(r, "aspect", SIGNAL_ASPECTS),
            ),
        ),
    )


def outputs_to_wire(outputs: TrackControllerOutputs) -> dict[str, Any]:
    """Encode one tick's outputs."""
    model = outputs.track_model
    return {
        "track_model": {
            "track_circuits": _entries(
                model.track_circuits,
                lambda c: {
                    "speed_mps": c.speed_mps,
                    "authority_blocks": c.authority_blocks,
                },
            ),
            "switch_commands": _entries(
                model.switch_commands, lambda p: {"position": p}
            ),
            "crossing_commands": _entries(
                model.crossing_commands, lambda a: {"active": a}
            ),
            "signal_commands": _entries(
                model.signal_commands, lambda a: {"aspect": a}
            ),
        },
        "ctc_reports": [
            {
                "wayside_id": report.wayside_id,
                "sent_at_s": report.sent_at_s,
                "blocks": _entries(
                    report.blocks,
                    lambda b: {
                        "occupied": b.occupied,
                        "failure": b.failure,
                        "switch_position": b.switch_position,
                        "crossing_active": b.crossing_active,
                    },
                ),
            }
            for report in outputs.ctc_reports
        ],
    }


def outputs_from_wire(data: Any) -> TrackControllerOutputs:
    """Decode one tick's outputs."""
    record = _object(data, "outputs")
    model = _object(record.get("track_model"), "track_model")
    raw_reports = record.get("ctc_reports")
    if not isinstance(raw_reports, list):
        raise WireFormatError("ctc_reports must be a list")
    reports = []
    for raw in raw_reports:
        report = _object(raw, "ctc_report")
        reports.append(CtcReport(
            wayside_id=_text(report, "wayside_id"),
            sent_at_s=_number(report, "sent_at_s"),
            blocks=_from_entries(
                report.get("blocks"), "blocks",
                lambda r: BlockReport(
                    occupied=_flag(r, "occupied"),
                    failure=_optional_choice(r, "failure", FAILURE_KINDS),
                    switch_position=_optional_choice(
                        r, "switch_position", SWITCH_POSITIONS
                    ),
                    crossing_active=_optional_flag(r, "crossing_active"),
                ),
            ),
        ))
    return TrackControllerOutputs(
        track_model=TrackModelOutputs(
            track_circuits=_from_entries(
                model.get("track_circuits"), "track_circuits",
                lambda r: TrackCircuitCommand(
                    speed_mps=_count(r, "speed_mps"),
                    authority_blocks=_count(r, "authority_blocks"),
                ),
            ),
            switch_commands=_from_entries(
                model.get("switch_commands"), "switch_commands",
                lambda r: _choice(r, "position", SWITCH_POSITIONS),
            ),
            crossing_commands=_from_entries(
                model.get("crossing_commands"), "crossing_commands",
                lambda r: _flag(r, "active"),
            ),
            signal_commands=_from_entries(
                model.get("signal_commands"), "signal_commands",
                lambda r: _choice(r, "aspect", SIGNAL_ASPECTS),
            ),
        ),
        ctc_reports=tuple(reports),
    )


# ------------------------------------------------------------------ #
# Territories
# ------------------------------------------------------------------ #

def territory_to_wire(territory: Territory) -> dict[str, Any]:
    """Encode a territory, for the test UI's block lists."""
    return {
        "line": territory.line,
        "wayside_id": territory.wayside_id,
        "blocks": [
            {
                "block": key_to_wire(block.key),
                "length_m": block.length_m,
                "speed_limit_mps": block.speed_limit_mps,
            }
            for block in territory.blocks
        ],
        "switches": [
            {
                "block": key_to_wire(switch.key),
                "point": switch.point,
                "normal_end": switch.normal_end,
                "reverse_end": switch.reverse_end,
            }
            for switch in territory.switches
        ],
        "crossings": [key_to_wire(key) for key in territory.crossings],
    }


def territory_from_wire(data: Any) -> Territory:
    """Decode a territory."""
    record = _object(data, "territory")
    raw_blocks = record.get("blocks")
    raw_switches = record.get("switches")
    raw_crossings = record.get("crossings")
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise WireFormatError("a territory needs a list of blocks")
    if not isinstance(raw_switches, list) or not isinstance(
        raw_crossings, list
    ):
        raise WireFormatError("switches and crossings must be lists")
    blocks = []
    for raw in raw_blocks:
        block = _object(raw, "block")
        blocks.append(Block(
            key=key_from_wire(block.get("block")),
            length_m=_number(block, "length_m"),
            speed_limit_mps=_number(block, "speed_limit_mps"),
        ))
    switches = []
    for raw in raw_switches:
        switch = _object(raw, "switch")
        switches.append(Switch(
            key=key_from_wire(switch.get("block")),
            point=_text(switch, "point"),
            normal_end=_text(switch, "normal_end"),
            reverse_end=_text(switch, "reverse_end"),
        ))
    return Territory(
        line=_text(record, "line"),
        wayside_id=_text(record, "wayside_id"),
        blocks=tuple(blocks),
        switches=tuple(switches),
        crossings=tuple(key_from_wire(raw) for raw in raw_crossings),
    )


# ------------------------------------------------------------------ #
# Field checks
# ------------------------------------------------------------------ #

def _object(data: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(data, Mapping):
        raise WireFormatError(f"{name} must be an object")
    return data


def _text(record: Mapping[str, Any], name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value:
        raise WireFormatError(f"{name} must be non-empty text")
    return value


def _flag(record: Mapping[str, Any], name: str) -> bool:
    value = record.get(name)
    if not isinstance(value, bool):
        raise WireFormatError(f"{name} must be true or false")
    return value


def _optional_flag(record: Mapping[str, Any], name: str) -> bool | None:
    return None if record.get(name) is None else _flag(record, name)


def _number(record: Mapping[str, Any], name: str) -> float:
    value = record.get(name)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise WireFormatError(f"{name} must be a finite number")
    return float(value)


def _count(record: Mapping[str, Any], name: str) -> int:
    value = record.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise WireFormatError(f"{name} must be a whole number, 0 or more")
    return value


def _choice(
    record: Mapping[str, Any], name: str, allowed: tuple[str, ...]
) -> Any:
    value = record.get(name)
    if value not in allowed:
        raise WireFormatError(f"{name} must be one of {', '.join(allowed)}")
    return value


def _optional_choice(
    record: Mapping[str, Any], name: str, allowed: tuple[str, ...]
) -> Any:
    return None if record.get(name) is None else _choice(record, name, allowed)
