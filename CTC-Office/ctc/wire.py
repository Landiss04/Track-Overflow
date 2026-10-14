"""JSON form of the CTC Office boundary types, for the socket link.

Pure functions, no Qt: every boundary dataclass becomes a plain dict
(tuples become lists) and back. Only ``ctc.socket_link`` uses this; the
module itself never sees JSON.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Mapping

from ctc.interface import (
    BlockOccupancy,
    BlockRef,
    CancelledOrder,
    CrossingReport,
    CtcInputs,
    CtcOutputs,
    CtcSnapshot,
    DispatchOrder,
    QueuedTrain,
    SwitchCommand,
    SwitchReport,
    TrackControllerInputs,
    TrackControllerOutputs,
    TrackedTrain,
    TrackModelInputs,
    TrainAuthority,
    TrainSuggestion,
)


def to_wire(value: Any) -> Any:
    """A boundary dataclass as JSON-ready dicts and lists."""
    return dataclasses.asdict(value)


class WireFormatError(ValueError):
    """A message does not have the shape of a boundary type."""


def _mapping(value: Any, what: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise WireFormatError(f"{what} must be an object, got "
                              f"{type(value).__name__}")
    return value


def _items(data: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = data.get(key, ())
    if not isinstance(value, (list, tuple)):
        raise WireFormatError(f"{key} must be a list, got "
                              f"{type(value).__name__}")
    return [_mapping(item, f"an entry of {key}") for item in value]


def _sales(value: Any) -> dict[str, Any]:
    """``{station: tickets}``, as sent."""
    if not isinstance(value, Mapping):
        raise WireFormatError("ticket_sales must be an object of station "
                              f"names to tickets, got {type(value).__name__}")
    return dict(value)


def inputs_from_wire(data: Mapping[str, Any]) -> CtcInputs:
    data = _mapping(data, "inputs")
    track = _mapping(data.get("track_controller", {}), "track_controller")
    track_model = _mapping(data.get("track_model", {}), "track_model")
    return CtcInputs(
        track_controller=TrackControllerInputs(
            occupancy=tuple(BlockOccupancy(**b)
                            for b in _items(track, "occupancy")),
            switches=tuple(SwitchReport(**s)
                           for s in _items(track, "switches")),
            crossings=tuple(CrossingReport(**c)
                            for c in _items(track, "crossings")),
            # As sent: anything but a real boolean is rejected later.
            ready=track.get("ready", False),
        ),
        track_model=TrackModelInputs(
            ticket_sales=_sales(track_model.get("ticket_sales", {}))),
    )


def outputs_from_wire(data: Mapping[str, Any]) -> CtcOutputs:
    track = data.get("track_controller", {})
    return CtcOutputs(
        track_controller=TrackControllerOutputs(
            suggestions=tuple(TrainSuggestion(**s)
                              for s in track.get("suggestions", ())),
            closed_blocks=tuple(BlockRef(**b)
                                for b in track.get("closed_blocks", ())),
            switch_commands=tuple(
                SwitchCommand(**c)
                for c in track.get("switch_commands", ())),
        ),
        clock_speedup=bool(data.get("clock_speedup", False)),
    )


def snapshot_from_wire(data: Mapping[str, Any]) -> CtcSnapshot:
    inputs = data.get("inputs")
    return CtcSnapshot(
        outputs=outputs_from_wire(data.get("outputs", {})),
        inputs=None if inputs is None else inputs_from_wire(inputs),
        elapsed_s=float(data.get("elapsed_s", 0.0)),
        tickets_sold=dict(data.get("tickets_sold", {})),
        queued_trains=tuple(QueuedTrain(**q)
                            for q in data.get("queued_trains", ())),
        orders=tuple(DispatchOrder(**o) for o in data.get("orders", ())),
        pending_closures=tuple(BlockRef(**b) for b in
                               data.get("pending_closures", ())),
        closed_blocks=tuple(BlockRef(**b) for b in
                            data.get("closed_blocks", ())),
        switch_commands=tuple(SwitchCommand(**c) for c in
                              data.get("switch_commands", ())),
        cancelled_orders=tuple(CancelledOrder(**c) for c in
                               data.get("cancelled_orders", ())),
        authorities=tuple(
            TrainAuthority(**{**a, "route": tuple(a.get("route", ()))})
            for a in data.get("authorities", ())),
        inputs_staged=bool(data.get("inputs_staged", False)),
        maintenance_mode=bool(data.get("maintenance_mode", False)),
        trains=tuple(
            TrackedTrain(**{**t, "blocks": tuple(t.get("blocks", ()))})
            for t in data.get("trains", ())),
        lost_trains=tuple(data.get("lost_trains", ())),
    )
