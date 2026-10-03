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
    CrossingReport,
    CtcInputs,
    CtcOutputs,
    CtcSnapshot,
    QueuedTrain,
    SwitchReport,
    TrackControllerInputs,
    TrackControllerOutputs,
    TrackFailureReport,
    TrackModelInputs,
    TrainReport,
    TrainSuggestion,
)


def to_wire(value: Any) -> Any:
    """A boundary dataclass as JSON-ready dicts and lists."""
    return dataclasses.asdict(value)


def inputs_from_wire(data: Mapping[str, Any]) -> CtcInputs:
    track = data.get("track_controller", {})
    return CtcInputs(
        track_controller=TrackControllerInputs(
            occupancy=tuple(BlockOccupancy(**b)
                            for b in track.get("occupancy", ())),
            trains=tuple(TrainReport(**t) for t in track.get("trains", ())),
            switches=tuple(SwitchReport(**s)
                           for s in track.get("switches", ())),
            crossings=tuple(CrossingReport(**c)
                            for c in track.get("crossings", ())),
            failures=tuple(TrackFailureReport(**f)
                           for f in track.get("failures", ())),
        ),
        track_model=TrackModelInputs(**data.get("track_model", {})),
    )


def outputs_from_wire(data: Mapping[str, Any]) -> CtcOutputs:
    track = data.get("track_controller", {})
    return CtcOutputs(
        track_controller=TrackControllerOutputs(
            suggestions=tuple(TrainSuggestion(**s)
                              for s in track.get("suggestions", ())),
            closed_block_ids=tuple(track.get("closed_block_ids", ())),
            maintenance_mode=bool(track.get("maintenance_mode", False)),
        ),
        clock_speedup=bool(data.get("clock_speedup", False)),
    )


def snapshot_from_wire(data: Mapping[str, Any]) -> CtcSnapshot:
    inputs = data.get("inputs")
    return CtcSnapshot(
        outputs=outputs_from_wire(data.get("outputs", {})),
        inputs=None if inputs is None else inputs_from_wire(inputs),
        elapsed_s=float(data.get("elapsed_s", 0.0)),
        tickets_sold_total=int(data.get("tickets_sold_total", 0)),
        queued_trains=tuple(QueuedTrain(**q)
                            for q in data.get("queued_trains", ())),
    )
