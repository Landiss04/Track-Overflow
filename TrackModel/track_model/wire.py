"""The Track Model's boundary types as JSON, for the harness protocol.

The central harness sends the Track Model's inputs, and takes its
outputs, as JSON objects whose keys are the field names of the types in
``track_model.interface``. Each module defines only its own boundary
types; the harness maps the other modules' outputs onto them (D005).
Nested types are nested objects, an enumerated value travels by its
name, in capitals (``conventions/naming``), and ``None`` is ``null``.
Blocks keep the Track Model's own names, such as ``"GREEN K-63"``.

The inputs, with every field shown::

    {"controller": {"commanded_speed_mps": {"GREEN K-63": 12.5},
                    "commanded_authority": {"GREEN K-63": 2},
                    "switch_commands": {"GREEN K-63": "NORMAL"},
                    "crossing_commands": {}, "signal_commands": {},
                    "heater_commands": {}},
     "trains": {"G1": {"block_id": "GREEN K-63", "offset_m": 0.0,
                       "actual_speed_mps": 0.0, "block_changed": false,
                       "passenger_capacity": 222, "doors_open": false}},
     "ambient_temp_c": null}

A command map left out is empty, as is a ``controller`` left out. The
ambient temperature may be left out: the Track Model window sets it.
The simulation time is not an input field: the harness sends it with
every step, and the process passes it on (``decode_inputs``).

The outputs are ``TrackModelOutputs`` field for field, built by hand
rather than by ``dataclasses.asdict``, which copies every value and
would cost much of a tick at 10x.
"""

from __future__ import annotations

__all__ = ["decode_inputs", "encode_outputs"]

from collections.abc import Mapping
from enum import Enum
from typing import Any, TypeVar

from track_model.interface import (
    InvalidInputError,
    SignalAspect,
    SwitchPosition,
    TrackControllerCommands,
    TrackModelInputs,
    TrackModelOutputs,
    TrainFeed,
    TrainReport,
)

_E = TypeVar("_E", bound=Enum)

#: The command maps, by field name, and the kind of value each holds.
_COMMANDS = {
    "commanded_speed_mps": "number",
    "commanded_authority": "number",
    "switch_commands": SwitchPosition,
    "crossing_commands": "bool",
    "signal_commands": SignalAspect,
    "heater_commands": "bool",
}

#: A train report's fields and the JSON type each must have. Numbers
#: are checked further by the model when it steps.
_REPORT_FIELDS: dict[str, type | tuple[type, ...]] = {
    "block_id": str,
    "offset_m": (int, float),
    "actual_speed_mps": (int, float),
    "block_changed": bool,
    "passenger_capacity": int,
    "doors_open": bool,
}


def decode_inputs(
    data: Any, sim_time_s: float | None = None
) -> TrackModelInputs:
    """Return the Track Model's inputs from their JSON form.

    Values are checked by the model when it steps; this checks the
    shape, the names of enumerated values, and the JSON type of each
    value, so the model's checks never meet a value of the wrong type.

    Args:
        data: The inputs, as the harness sent them.
        sim_time_s: The central clock's time for this step, for the
            window's time of day.

    Raises:
        InvalidInputError: If an object is missing, a field is missing
            or unknown, or a value is of the wrong type.
    """
    inputs = _object(data, "inputs")
    _only(inputs, {"controller", "trains", "ambient_temp_c"}, "inputs")
    ambient = inputs.get("ambient_temp_c")
    if ambient is not None and not _is_number(ambient):
        raise InvalidInputError(
            f"ambient_temp_c must be a number or null, got {ambient!r}"
        )
    return TrackModelInputs(
        controller=_commands(inputs.get("controller", {})),
        trains={
            str(train_id): _report(train_id, report)
            for train_id, report in _object(
                inputs.get("trains"), "trains"
            ).items()
        },
        ambient_temp_c=ambient,
        sim_time_s=sim_time_s,
    )


def encode_outputs(outputs: TrackModelOutputs) -> dict[str, Any]:
    """Return the Track Model's outputs in their JSON form."""
    out = outputs.controller
    return {
        "controller": {
            "block_occupancy": dict(out.block_occupancy),
            "switch_states": _names(out.switch_states),
            "crossing_states": dict(out.crossing_states),
            "signal_states": _names(out.signal_states),
            "failure_status": _names(out.failure_status),
            "heater_states": dict(out.heater_states),
            "track_temp_c": dict(out.track_temp_c),
        },
        "ctc": {"tickets_sold_now": dict(outputs.ctc.tickets_sold_now)},
        "train_feeds": {
            train_id: _feed(feed)
            for train_id, feed in outputs.train_feeds.items()
        },
        "signal_seen": {
            train_id: None if seen is None else seen.name
            for train_id, seen in outputs.signal_seen.items()
        },
    }


def _commands(value: Any) -> TrackControllerCommands:
    # The Track Controller's commands, each map checked by its kind.
    data = _object(value, "controller")
    _only(data, set(_COMMANDS), "controller")
    maps: dict[str, dict[str, Any]] = {}
    for name, kind in _COMMANDS.items():
        given = _object(data.get(name, {}), name)
        if isinstance(kind, type) and issubclass(kind, Enum):
            maps[name] = {
                key: _member(kind, item, f"{name}[{key!r}]")
                for key, item in given.items()
            }
            continue
        for key, item in given.items():
            fits = isinstance(item, bool) if kind == "bool" else (
                _is_number(item))
            if not fits:
                raise InvalidInputError(
                    f"{name}[{key!r}] must be a {kind}, got {item!r}"
                )
        maps[name] = dict(given)
    return TrackControllerCommands(**maps)


def _report(train_id: str, value: Any) -> TrainReport:
    # One train's report, with exactly its fields, each of its type.
    data = _object(value, f"train {train_id}")
    _only(data, set(_REPORT_FIELDS), f"train {train_id}")
    missing = sorted(set(_REPORT_FIELDS) - set(data))
    if missing:
        raise InvalidInputError(f"train {train_id} is missing {missing}")
    for name, kind in _REPORT_FIELDS.items():
        item = data[name]
        # A bool is an int to Python; only the flags may be bools.
        if not isinstance(item, kind) or (
            isinstance(item, bool) and kind is not bool
        ):
            raise InvalidInputError(
                f"train {train_id} {name} has the wrong type: {item!r}"
            )
    return TrainReport(**data)


def _object(value: Any, name: str) -> Mapping[str, Any]:
    # A JSON object, or a refusal naming it.
    if not isinstance(value, Mapping):
        raise InvalidInputError(f"{name} must be an object, got {value!r}")
    return value


def _only(data: Mapping[str, Any], allowed: set[str], name: str) -> None:
    # Refuse a field this form does not have.
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise InvalidInputError(f"{name} has unknown fields {unknown}")


def _member(kind: type[_E], value: Any, name: str) -> _E:
    # An enumerated value from its name.
    if not isinstance(value, str) or value not in kind.__members__:
        raise InvalidInputError(
            f"{name} must be one of {list(kind.__members__)}, "
            f"got {value!r}"
        )
    return kind[value]


def _is_number(value: Any) -> bool:
    # A JSON number: an int or a float, never a bool.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _names(values: Mapping[str, Enum]) -> dict[str, str]:
    # Enumerated values by name.
    return {key: value.name for key, value in values.items()}


def _feed(feed: TrainFeed) -> dict[str, Any]:
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
            "authority_blocks": signal.authority_blocks,
        },
        "beacon": None if beacon is None else {
            "station_name": beacon.station_name,
            "platform_side": beacon.platform_side,
            "underground": beacon.underground,
        },
        "passengers_boarded": feed.passengers_boarded,
    }
