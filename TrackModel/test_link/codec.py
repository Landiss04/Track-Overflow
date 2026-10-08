"""JSON encoding of the Track Model's boundary types.

Values stay in backend units and field names are unchanged; enums travel
by name. Only the types that cross the link are covered.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any, TypeVar

from track_model.interface import (
    Beacon,
    BlockEdit,
    SignalAspect,
    SwitchPosition,
    TrackControllerCommands,
    TrackControllerOutputs,
    TrackFailure,
    TrackInfo,
    TrackModelInputs,
    TrackModelOutputs,
    TrackSignal,
    TrainFeed,
    TrainReport,
)

Json = dict[str, Any]
E = TypeVar("E", bound=Enum)


def _names(values: Mapping[str, Enum]) -> dict[str, str]:
    # Enum values travel by member name.
    return {k: v.name for k, v in values.items()}


def _enums(kind: type[E], values: Mapping[str, str]) -> dict[str, E]:
    # Inverse of _names; an unknown name raises KeyError.
    return {k: kind[v] for k, v in values.items()}


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #

def encode_inputs(inputs: TrackModelInputs) -> Json:
    """Return ``inputs`` as a JSON-ready dict."""
    cmd = inputs.controller
    return {
        "controller": {
            "commanded_speed_mps": dict(cmd.commanded_speed_mps),
            "commanded_authority": dict(cmd.commanded_authority),
            "switch_commands": _names(cmd.switch_commands),
            "crossing_commands": dict(cmd.crossing_commands),
            "signal_commands": _names(cmd.signal_commands),
            "heater_commands": dict(cmd.heater_commands),
        },
        "trains": {
            train_id: {
                "block_id": r.block_id,
                "offset_m": r.offset_m,
                "actual_speed_mps": r.actual_speed_mps,
                "block_changed": r.block_changed,
                "passenger_capacity": r.passenger_capacity,
            }
            for train_id, r in inputs.trains.items()
        },
        "ambient_temp_c": inputs.ambient_temp_c,
    }


def decode_inputs(data: Json) -> TrackModelInputs:
    """Rebuild ``TrackModelInputs`` from ``encode_inputs`` output."""
    cmd = data["controller"]
    return TrackModelInputs(
        controller=TrackControllerCommands(
            commanded_speed_mps={
                k: int(v) for k, v in cmd["commanded_speed_mps"].items()
            },
            commanded_authority=dict(cmd["commanded_authority"]),
            switch_commands=_enums(SwitchPosition, cmd["switch_commands"]),
            crossing_commands={
                k: bool(v) for k, v in cmd["crossing_commands"].items()
            },
            signal_commands=_enums(SignalAspect, cmd["signal_commands"]),
            heater_commands={
                k: bool(v) for k, v in cmd["heater_commands"].items()
            },
        ),
        trains={
            train_id: TrainReport(
                block_id=str(r["block_id"]),
                offset_m=float(r["offset_m"]),
                actual_speed_mps=float(r["actual_speed_mps"]),
                block_changed=bool(r["block_changed"]),
                passenger_capacity=int(r["passenger_capacity"]),
            )
            for train_id, r in data["trains"].items()
        },
        ambient_temp_c=float(data["ambient_temp_c"]),
    )


# --------------------------------------------------------------------------- #
# Outputs
# --------------------------------------------------------------------------- #

def encode_outputs(outputs: TrackModelOutputs) -> Json:
    """Return ``outputs`` as a JSON-ready dict."""
    out = outputs.controller
    return {
        "controller": {
            "block_occupancy": dict(out.block_occupancy),
            "switch_states": _names(out.switch_states),
            "crossing_states": dict(out.crossing_states),
            "signal_states": _names(out.signal_states),
            "failure_status": _names(out.failure_status),
            "heater_states": dict(out.heater_states),
            "ticket_sales": dict(out.ticket_sales),
            "track_temp_c": dict(out.track_temp_c),
        },
        "train_feeds": {
            train_id: _encode_feed(feed)
            for train_id, feed in outputs.train_feeds.items()
        },
        "signal_seen": {
            train_id: None if seen is None else seen.name
            for train_id, seen in outputs.signal_seen.items()
        },
    }


def decode_outputs(data: Json) -> TrackModelOutputs:
    """Rebuild ``TrackModelOutputs`` from ``encode_outputs`` output."""
    out = data["controller"]
    return TrackModelOutputs(
        controller=TrackControllerOutputs(
            block_occupancy=dict(out["block_occupancy"]),
            switch_states=_enums(SwitchPosition, out["switch_states"]),
            crossing_states=dict(out["crossing_states"]),
            signal_states=_enums(SignalAspect, out["signal_states"]),
            failure_status=_enums(TrackFailure, out["failure_status"]),
            heater_states=dict(out["heater_states"]),
            ticket_sales={k: int(v) for k, v in out["ticket_sales"].items()},
            track_temp_c={
                k: float(v) for k, v in out["track_temp_c"].items()
            },
        ),
        train_feeds={
            train_id: _decode_feed(feed)
            for train_id, feed in data["train_feeds"].items()
        },
        signal_seen={
            train_id: None if seen is None else SignalAspect[seen]
            for train_id, seen in data["signal_seen"].items()
        },
    )


def _encode_feed(feed: TrainFeed) -> Json:
    # One train's feed, nested as in TrainFeed.
    info, signal, beacon = feed.track_info, feed.track_signal, feed.beacon
    return {
        "track_info": {
            "block_id": info.block_id,
            "grade_deg": info.grade_deg,
            "elevation_m": info.elevation_m,
            "speed_limit_mps": info.speed_limit_mps,
            "polarity": info.polarity,
            "station_name": info.station_name,
        },
        "track_signal": {
            "commanded_speed_mps": signal.commanded_speed_mps,
            "authority_block_id": signal.authority_block_id,
        },
        "beacon": None if beacon is None else {
            "station_name": beacon.station_name,
            "platform_side": beacon.platform_side,
            "underground": beacon.underground,
        },
        "passengers_boarded": feed.passengers_boarded,
    }


def _decode_feed(data: Json) -> TrainFeed:
    # Inverse of _encode_feed.
    info, signal, beacon = (
        data["track_info"], data["track_signal"], data["beacon"]
    )
    return TrainFeed(
        track_info=TrackInfo(
            block_id=info["block_id"],
            grade_deg=float(info["grade_deg"]),
            elevation_m=float(info["elevation_m"]),
            speed_limit_mps=float(info["speed_limit_mps"]),
            polarity=bool(info["polarity"]),
            station_name=info["station_name"],
        ),
        track_signal=TrackSignal(
            commanded_speed_mps=int(signal["commanded_speed_mps"]),
            authority_block_id=signal["authority_block_id"],
        ),
        beacon=None if beacon is None else Beacon(
            station_name=beacon["station_name"],
            platform_side=beacon["platform_side"],
            underground=bool(beacon["underground"]),
        ),
        passengers_boarded=int(data["passengers_boarded"]),
    )


# --------------------------------------------------------------------------- #
# Test-only commands
# --------------------------------------------------------------------------- #

def encode_block_edit(edit: BlockEdit) -> Json:
    """Return a block edit as a JSON-ready dict."""
    return {
        "length_m": edit.length_m,
        "grade_deg": edit.grade_deg,
        "speed_limit_mps": edit.speed_limit_mps,
        "elevation_m": edit.elevation_m,
    }


def decode_block_edit(data: Json) -> BlockEdit:
    """Rebuild a ``BlockEdit``; missing or null fields stay unchanged."""
    def number(key: str) -> float | None:
        value = data.get(key)
        return None if value is None else float(value)

    return BlockEdit(
        length_m=number("length_m"),
        grade_deg=number("grade_deg"),
        speed_limit_mps=number("speed_limit_mps"),
        elevation_m=number("elevation_m"),
    )
