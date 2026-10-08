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
) -> TrainReport:
    """Return one train's Train Model report."""
    return TrainReport(
        block_id=block_id,
        offset_m=offset_m,
        actual_speed_mps=speed_mps,
        block_changed=False,
        passenger_capacity=capacity,
    )


def make_inputs(
    trains: Mapping[str, TrainReport] | None = None,
    controller: TrackControllerCommands | None = None,
    ambient_temp_c: float = 10.0,
) -> TrackModelInputs:
    """Return a full input set; empty commands keep the last values."""
    return TrackModelInputs(
        controller=controller or TrackControllerCommands(),
        trains=dict(trains or {}),
        ambient_temp_c=ambient_temp_c,
    )
