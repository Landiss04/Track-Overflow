"""Edge mappings for the Track Model.

Each function is pure: it translates one producer's types into one
consumer's types and touches no module state. This is the one place that
imports both the Track Model's boundary types and the catalog. Units do
not change across an edge; everything stays in backend units.

Edges:

- Track Controller -> Track Model    ``track_controller_to_track_model``
- Train Model      -> Track Model    ``train_model_to_track_model``
- Track Model      -> Track Controller ``track_model_to_track_controller``
- Track Model      -> Train Model    ``track_model_to_train_model``
- Track Model      -> Train Controller ``track_model_to_train_controller``

There is no edge to the CTC Office: it reads Track Model data through
the Track Controller.
"""

from __future__ import annotations

from collections.abc import Mapping

from common.interfaces import (
    Beacon as CatalogBeacon,
    FailureMode,
    SignalAspect as CatalogAspect,
    SwitchPosition as CatalogSwitch,
    TrackInfo as CatalogTrackInfo,
    TrackReadback,
    TrainTrackFeed,
    TrainTrackReport,
    WaysideCommands,
)
from track_model.interface import (
    Beacon,
    SignalAspect,
    SwitchPosition,
    TrackControllerCommands,
    TrackFailure,
    TrackModelInputs,
    TrackModelOutputs,
    TrainReport,
)

_FAILURES: dict[TrackFailure, FailureMode] = {
    TrackFailure.NONE: FailureMode.NONE,
    TrackFailure.BROKEN_RAIL: FailureMode.BROKEN_RAIL,
    TrackFailure.TRACK_CIRCUIT: FailureMode.TRACK_CIRCUIT,
    TrackFailure.POWER: FailureMode.POWER_FAILURE,
}


# --------------------------------------------------------------------------- #
# Into the Track Model
# --------------------------------------------------------------------------- #

def track_controller_to_track_model(
    commands: WaysideCommands,
) -> TrackControllerCommands:
    """Map the Track Controller's commands to Track Model input."""
    return TrackControllerCommands(
        commanded_speed_mps=dict(commands.commanded_speed_mps),
        commanded_authority=dict(commands.authority_block_id),
        switch_commands={
            k: SwitchPosition[v.name]
            for k, v in commands.switch_positions.items()
        },
        crossing_commands=dict(commands.crossing_gates_closed),
        signal_commands={
            k: SignalAspect[v.name]
            for k, v in commands.signal_aspects.items()
        },
        heater_commands=dict(commands.heaters_on),
    )


def train_model_to_track_model(
    reports: Mapping[str, TrainTrackReport],
) -> dict[str, TrainReport]:
    """Map every train's Train Model report to Track Model input."""
    return {
        train_id: TrainReport(
            block_id=r.position.block_id,
            offset_m=r.position.offset_m,
            actual_speed_mps=r.actual_speed_mps,
            block_changed=r.block_changed,
            passenger_capacity=r.passenger_capacity,
        )
        for train_id, r in reports.items()
    }


def build_track_model_inputs(
    commands: WaysideCommands,
    reports: Mapping[str, TrainTrackReport],
    ambient_temp_c: float,
) -> TrackModelInputs:
    """Assemble one tick of Track Model input from both edges."""
    return TrackModelInputs(
        controller=track_controller_to_track_model(commands),
        trains=train_model_to_track_model(reports),
        ambient_temp_c=ambient_temp_c,
    )


# --------------------------------------------------------------------------- #
# Out of the Track Model
# --------------------------------------------------------------------------- #

def track_model_to_track_controller(
    outputs: TrackModelOutputs,
) -> TrackReadback:
    """Map the Track Model's read-back for the Track Controller."""
    out = outputs.controller
    return TrackReadback(
        block_occupancy=dict(out.block_occupancy),
        switch_positions={
            k: CatalogSwitch[v.name] for k, v in out.switch_states.items()
        },
        crossing_gates_closed=dict(out.crossing_states),
        signal_aspects={
            k: CatalogAspect[v.name] for k, v in out.signal_states.items()
        },
        failures={k: _FAILURES[v] for k, v in out.failure_status.items()},
        heaters_on=dict(out.heater_states),
        ticket_sales=dict(out.ticket_sales),
        track_temp_c=dict(out.track_temp_c),
    )


def track_model_to_train_model(
    outputs: TrackModelOutputs, train_id: str
) -> TrainTrackFeed | None:
    """Map one train's feed; None if the train is not on the track."""
    feed = outputs.train_feeds.get(train_id)
    if feed is None:
        return None
    info = feed.track_info
    return TrainTrackFeed(
        track_info=CatalogTrackInfo(
            block_id=info.block_id,
            grade_deg=info.grade_deg,
            elevation_m=info.elevation_m,
            speed_limit_mps=info.speed_limit_mps,
            polarity=info.polarity,
        ),
        commanded_speed_mps=feed.track_signal.commanded_speed_mps,
        authority_block_id=feed.track_signal.authority_block_id,
        beacon=_beacon(feed.beacon),
        passengers_boarded=feed.passengers_boarded,
    )


def track_model_to_train_controller(
    outputs: TrackModelOutputs, train_id: str
) -> CatalogAspect | None:
    """Return the signal colour one train saw on entering its block.

    Not None only on the entry tick into a block with a light; the Train
    Controller keeps it. PROVISIONAL: not yet agreed with the Train
    Controller owner.
    """
    seen = outputs.signal_seen.get(train_id)
    return None if seen is None else CatalogAspect[seen.name]


def _beacon(beacon: Beacon | None) -> CatalogBeacon | None:
    # Station fields carry over unchanged; "LR" is a two-sided platform.
    if beacon is None:
        return None
    return CatalogBeacon(
        next_station=beacon.station_name,
        platform_side=beacon.platform_side or "",
        underground=beacon.underground,
    )
