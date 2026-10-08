"""The harness edge functions carry values across unchanged.

These live with the Track Model tests because the edges import the
Track Model's boundary types; ``pytest.ini`` puts the repository root on
the path for ``common``.
"""

from __future__ import annotations

from common.harness.track_model_edges import (
    build_track_model_inputs,
    track_model_to_track_controller,
    track_model_to_train_controller,
    track_model_to_train_model,
)
from common.interfaces import (
    FailureMode,
    SignalAspect,
    SwitchPosition,
    TrainPosition,
    TrainTrackReport,
    WaysideCommands,
)
from track_model.interface import TrackFailure
from tests.helpers import DT_S, make_model

FAR_M = 10_000.0


def wayside(**kwargs: object) -> WaysideCommands:
    """Return catalog Track Controller commands."""
    return WaysideCommands(**kwargs)  # type: ignore[arg-type]


def at(block_id: str, offset_m: float, speed: float = 5.0) -> (
    dict[str, TrainTrackReport]
):
    """Return a catalog report for train T1."""
    return {"T1": TrainTrackReport(
        TrainPosition(block_id, offset_m), speed, False, 222)}


def test_round_trip_through_every_edge() -> None:
    """Drive the model only through edges and read every edge back."""
    model = make_model()
    commands = wayside(
        commanded_speed_mps={"BLUE A-4": 11},
        authority_block_id={"BLUE A-4": "BLUE B-10"},
        switch_positions={"BLUE A-5": SwitchPosition.REVERSE},
        crossing_gates_closed={"BLUE A-3": True},
        signal_aspects={"BLUE A-4": SignalAspect.SUPER_GREEN},
        heaters_on={"BLUE B": True},
    )
    model.step(DT_S, build_track_model_inputs(commands, at("BLUE A-3", 1.0),
                                              ambient_temp_c=-2.0))
    model.set_block_failure("BLUE A-2", TrackFailure.POWER)
    out = model.step(DT_S, build_track_model_inputs(
        WaysideCommands(), at("BLUE A-3", FAR_M), ambient_temp_c=-2.0))

    readback = track_model_to_track_controller(out)
    assert readback.block_occupancy["BLUE A-4"]
    assert readback.switch_positions["BLUE A-5"] is SwitchPosition.REVERSE
    assert readback.crossing_gates_closed["BLUE A-3"] is True
    assert readback.signal_aspects["BLUE A-4"] is SignalAspect.SUPER_GREEN
    assert readback.failures["BLUE A-2"] is FailureMode.POWER_FAILURE
    assert readback.heaters_on["BLUE B"] is True
    # BLUE A-2 has lost power, so section A's heaters are off.
    assert readback.heaters_on["BLUE A"] is False
    assert set(readback.track_temp_c) == set(readback.heaters_on)

    feed = track_model_to_train_model(out, "T1")
    assert feed is not None
    assert feed.track_info.block_id == "BLUE A-4"
    assert feed.commanded_speed_mps == 11
    assert feed.authority_block_id == "BLUE B-10"

    assert track_model_to_train_controller(out, "T1") is (
        SignalAspect.SUPER_GREEN)


def test_absent_train_maps_to_none() -> None:
    """Check edges for a train that is not on the track."""
    out = make_model().step(DT_S, build_track_model_inputs(
        WaysideCommands(), {}, ambient_temp_c=0.0))
    assert track_model_to_train_model(out, "T9") is None
    assert track_model_to_train_controller(out, "T9") is None


def test_beacon_maps_to_the_catalog_beacon() -> None:
    """Check station fields carry across the Train Model edge."""
    out = make_model().step(DT_S, build_track_model_inputs(
        WaysideCommands(), at("GREEN A-3", 1.0), ambient_temp_c=0.0))
    feed = track_model_to_train_model(out, "T1")
    assert feed is not None and feed.beacon is not None
    assert (feed.beacon.next_station, feed.beacon.platform_side) == (
        "PIONEER", "L")
