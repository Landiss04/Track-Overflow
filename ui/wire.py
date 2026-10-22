"""The Train Model's boundary types as JSON, for the harness protocol.

The central harness sends each train's inputs, and takes its outputs,
as JSON objects whose keys are the field names of the types in
``train_model.interface``. Each module defines only its own boundary
types; the harness maps the other modules' outputs onto them (D005).
Nested types are nested objects, and ``None`` is ``null``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

from train_model.interface import (
    Beacon,
    ControllerCommands,
    TrackInfo,
    TrackInputs,
    TrackSignal,
    TrainModelInputs,
    TrainModelOutputs,
)
from train_model.model import InvalidInputError


def decode_inputs(data: Any) -> TrainModelInputs:
    """Return one train's inputs from their JSON form.

    Values are checked by the model when it steps; this checks only
    the shape.

    Raises:
        InvalidInputError: If an object is missing, a field is missing
            or unknown, or a value is not an object where one belongs.
    """
    entry = _object(data, "train")
    track = _object(entry.get("track"), "track")
    beacon = track.get("beacon")
    if "passengers_boarded" not in track:
        raise InvalidInputError("track is missing passengers_boarded")
    return TrainModelInputs(
        controller=_build(ControllerCommands, entry.get("controller"),
                          "controller"),
        track=TrackInputs(
            track_info=_build(TrackInfo, track.get("track_info"),
                              "track_info"),
            track_signal=_build(TrackSignal, track.get("track_signal"),
                                "track_signal"),
            beacon=None if beacon is None else _build(
                Beacon, beacon, "beacon"),
            passengers_boarded=track["passengers_boarded"],
        ),
    )


def encode_outputs(outputs: TrainModelOutputs) -> dict[str, Any]:
    """Return one train's outputs in their JSON form."""
    return dataclasses.asdict(outputs)


def _object(value: Any, name: str) -> Mapping[str, Any]:
    # A JSON object, or a refusal naming it.
    if not isinstance(value, Mapping):
        raise InvalidInputError(f"{name} must be an object, got {value!r}")
    return value


def _build(cls: type[Any], value: Any, name: str) -> Any:
    # One boundary type from an object with exactly its fields; a
    # field with a default may be left out.
    data = _object(value, name)
    fields = {field.name: field for field in dataclasses.fields(cls)}
    unknown = sorted(set(data) - set(fields))
    if unknown:
        raise InvalidInputError(f"{name} has unknown fields {unknown}")
    missing = sorted(
        field_name
        for field_name, field in fields.items()
        if field_name not in data
        and field.default is dataclasses.MISSING
        and field.default_factory is dataclasses.MISSING
    )
    if missing:
        raise InvalidInputError(f"{name} is missing {missing}")
    return cls(**data)
