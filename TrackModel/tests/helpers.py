"""Shared builders for the Track Model tests."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from track_model.interface import (
    TrackConfig,
    TrackControllerCommands,
    TrackModelInputs,
    TrainReport,
)
from track_model.model import TrackModel

DT_S = 0.1
MODULE_DIR = Path(__file__).resolve().parents[1]
LAYOUT_PATHS = tuple(str(p) for p in sorted(MODULE_DIR.glob("*_line.json")))


def make_model(ticket_probability: float = 0.0, seed: int = 0) -> TrackModel:
    """Return a Track Model over every course line."""
    return TrackModel(TrackConfig(LAYOUT_PATHS, ticket_probability, seed))


def report(
    block_id: str,
    offset_m: float = 0.0,
    speed_mps: float = 10.0,
    capacity: int = 222,
    doors_open: bool = False,
) -> TrainReport:
    """Return one train's Train Model report.

    ``offset_m`` is the distance since the train entered ``block_id``,
    as the Train Model reports it (it restarts at 0 in each block).
    """
    return TrainReport(
        block_id=block_id,
        offset_m=offset_m,
        actual_speed_mps=speed_mps,
        block_changed=False,
        passenger_capacity=capacity,
        doors_open=doors_open,
    )


#: How far past a block's end a test pushes a train, like one tick of
#: motion would. Small, so the carried overshoot stays realistic.
OVERSHOOT_M = 0.5


def past_end(model: TrackModel, block_id: str) -> float:
    """Return an offset that just crosses the end of ``block_id``."""
    length = next(b.length_m for b in model.snapshot().blocks
                  if b.block_id == block_id)
    return length + OVERSHOOT_M


def make_inputs(
    trains: Mapping[str, TrainReport] | None = None,
    controller: TrackControllerCommands | None = None,
    ambient_temp_c: float = 10.0,
    sim_time_s: float | None = None,
) -> TrackModelInputs:
    """Return a full input set; empty commands keep the last values."""
    return TrackModelInputs(
        controller=controller or TrackControllerCommands(),
        trains=dict(trains or {}),
        ambient_temp_c=ambient_temp_c,
        sim_time_s=sim_time_s,
    )
