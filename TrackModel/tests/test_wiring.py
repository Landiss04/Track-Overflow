"""Every input reaches its output."""

from __future__ import annotations

import pytest

from track_model.interface import (
    BlockEdit,
    InvalidInputError,
    SignalAspect,
    SwitchPosition,
    TrackControllerCommands,
    TrackFailure,
    UnknownIdError,
)
from track_model.model import TrackModel
from tests.helpers import DT_S, make_inputs, make_model, report

FAR_M = 10_000.0     # past the end of any block


def cmd(**kwargs: object) -> TrackControllerCommands:
    """Return Track Controller commands with only the given fields."""
    return TrackControllerCommands(**kwargs)  # type: ignore[arg-type]


def drive(model: TrackModel, train_id: str, block_id: str,
          offset_m: float = FAR_M,
          controller: TrackControllerCommands | None = None) -> str:
    """Report ``offset_m`` in ``block_id``; return the train's new block."""
    out = model.step(
        DT_S, make_inputs({train_id: report(block_id, offset_m)}, controller)
    )
    return out.train_feeds[train_id].track_info.block_id


# --------------------------------------------------------------------------- #
# Commands become states
# --------------------------------------------------------------------------- #

def test_commands_become_states() -> None:
    """Check every Track Controller command against its read-back."""
    model = make_model()
    out = model.step(DT_S, make_inputs(controller=cmd(
        switch_commands={"BLUE A-5": SwitchPosition.REVERSE},
        crossing_commands={"BLUE A-3": True},
        signal_commands={"BLUE A-4": SignalAspect.GREEN},
        heater_commands={"BLUE A": True},
    ))).controller
    assert out.switch_states["BLUE A-5"] is SwitchPosition.REVERSE
    assert out.crossing_states["BLUE A-3"] is True
    assert out.signal_states["BLUE A-4"] is SignalAspect.GREEN
    assert out.heater_states["BLUE A"] is True


def test_absent_commands_keep_their_last_value() -> None:
    """Check that a command persists until the next one replaces it."""
    model = make_model()
    model.step(DT_S, make_inputs(controller=cmd(
        switch_commands={"BLUE A-5": SwitchPosition.REVERSE})))
    out = model.step(DT_S, make_inputs())
    assert out.controller.switch_states["BLUE A-5"] is SwitchPosition.REVERSE


def test_devices_start_at_safe_defaults() -> None:
    """Check switches NORMAL, gates up, signals RED, no failures."""
    out = make_model().step(DT_S, make_inputs()).controller
    assert set(out.switch_states.values()) == {SwitchPosition.NORMAL}
    assert not any(out.crossing_states.values())
    assert set(out.signal_states.values()) == {SignalAspect.RED}
    assert set(out.failure_status.values()) == {TrackFailure.NONE}


# --------------------------------------------------------------------------- #
# Per-train feed
# --------------------------------------------------------------------------- #

def test_feed_carries_the_block_and_track_circuit() -> None:
    """Check Track Info, commanded speed, authority and beacon."""
    model = make_model()
    out = model.step(DT_S, make_inputs(
        {"T1": report("GREEN A-3", offset_m=5.0)},
        cmd(commanded_speed_mps={"GREEN A-3": 12},
            commanded_authority={"GREEN A-3": "GREEN F-28"}),
    ))
    feed = out.train_feeds["T1"]
    assert feed.track_info.block_id == "GREEN A-3"
    assert feed.track_info.speed_limit_mps == pytest.approx(45 / 3.6)
    assert feed.track_signal.commanded_speed_mps == 12
    assert isinstance(feed.track_signal.commanded_speed_mps, int)
    assert feed.track_signal.authority_block_id == "GREEN F-28"
    assert feed.beacon is not None
    assert feed.beacon.station_name == "PIONEER"


def test_speed_and_authority_come_from_the_occupied_block() -> None:
    """Check both change as the train enters a block with other values."""
    model = make_model()
    commands = cmd(
        commanded_speed_mps={"BLUE A-3": 10, "BLUE A-4": 5},
        commanded_authority={"BLUE A-3": "BLUE A-5", "BLUE A-4": "BLUE B-8"},
    )
    drive(model, "T1", "BLUE A-3", 1.0, commands)
    out = model.step(DT_S, make_inputs({"T1": report("BLUE A-3", 1.0)}))
    signal = out.train_feeds["T1"].track_signal
    assert (signal.commanded_speed_mps, signal.authority_block_id) == (
        10, "BLUE A-5")
    out = model.step(DT_S, make_inputs({"T1": report("BLUE A-3", FAR_M)}))
    signal = out.train_feeds["T1"].track_signal
    assert (signal.commanded_speed_mps, signal.authority_block_id) == (
        5, "BLUE B-8")


def test_two_trains_in_one_block_get_the_same_signal() -> None:
    """Check the track circuit is the block's, not the train's."""
    out = make_model().step(DT_S, make_inputs(
        {"T1": report("GREEN A-3", 1.0), "T2": report("GREEN A-3", 20.0)},
        cmd(commanded_speed_mps={"GREEN A-3": 7},
            commanded_authority={"GREEN A-3": "GREEN C-9"}),
    ))
    assert (out.train_feeds["T1"].track_signal
            == out.train_feeds["T2"].track_signal)


def test_uncommanded_block_sends_zero_and_no_authority() -> None:
    """Check a block with no command yet carries 0 m/s and no authority."""
    out = make_model().step(DT_S, make_inputs({"T1": report("BLUE A-2")}))
    signal = out.train_feeds["T1"].track_signal
    assert signal.commanded_speed_mps == 0
    assert signal.authority_block_id is None


def test_no_beacon_away_from_stations() -> None:
    """Check that a block with no adjacent station has no beacon."""
    model = make_model()
    out = model.step(DT_S, make_inputs({"T1": report("BLUE A-4", 1.0)}))
    assert out.train_feeds["T1"].beacon is None


# --------------------------------------------------------------------------- #
# Occupancy and block movement
# --------------------------------------------------------------------------- #

def test_offset_inside_the_block_does_not_move_the_train() -> None:
    """Check occupancy and position for an offset short of the end."""
    model = make_model()
    out = model.step(DT_S, make_inputs({"T1": report("BLUE A-3", 1.0)}))
    assert out.train_feeds["T1"].track_info.block_id == "BLUE A-3"
    assert out.controller.block_occupancy["BLUE A-3"]
    assert sum(out.controller.block_occupancy.values()) == 1


def test_offset_past_the_end_advances_and_flips_polarity() -> None:
    """Check that occupancy moves and polarity reverses at a boundary."""
    model = make_model()
    first = model.step(DT_S, make_inputs({"T1": report("BLUE A-3", 1.0)}))
    out = model.step(DT_S, make_inputs({"T1": report("BLUE A-3", FAR_M)}))
    assert out.train_feeds["T1"].track_info.block_id == "BLUE A-4"
    assert out.controller.block_occupancy["BLUE A-4"]
    assert not out.controller.block_occupancy["BLUE A-3"]
    assert (out.train_feeds["T1"].track_info.polarity
            != first.train_feeds["T1"].track_info.polarity)


def test_stale_report_does_not_advance_twice() -> None:
    """Check that the old block's report, one tick late, is ignored."""
    model = make_model()
    drive(model, "T1", "BLUE A-3", 1.0)
    assert drive(model, "T1", "BLUE A-3") == "BLUE A-4"
    assert drive(model, "T1", "BLUE A-3") == "BLUE A-4"


def test_negative_offset_rolls_back_to_the_previous_block() -> None:
    """Check rollback returns the train to the block it came from."""
    model = make_model()
    drive(model, "T1", "BLUE A-3", 1.0)
    drive(model, "T1", "BLUE A-3")
    assert drive(model, "T1", "BLUE A-4", -1.0) == "BLUE A-3"


def test_continued_rollback_keeps_going_back() -> None:
    """Check two rollbacks in a row go back two blocks, not bounce."""
    model = make_model()
    drive(model, "T1", "BLUE A-2", 1.0)
    assert drive(model, "T1", "BLUE A-2") == "BLUE A-3"
    assert drive(model, "T1", "BLUE A-3") == "BLUE A-4"
    assert drive(model, "T1", "BLUE A-4", -1.0) == "BLUE A-3"
    assert drive(model, "T1", "BLUE A-3", -1.0) == "BLUE A-2"
    # Forward again: still the original direction of travel.
    assert drive(model, "T1", "BLUE A-2") == "BLUE A-3"


def test_stale_report_after_rollback_is_ignored() -> None:
    """Check the left block's late report does not reset the train."""
    model = make_model()
    drive(model, "T1", "BLUE A-3", 1.0)
    drive(model, "T1", "BLUE A-3")
    assert drive(model, "T1", "BLUE A-4", -1.0) == "BLUE A-3"
    # One tick late, the Train Model still reports A-4 with a negative
    # offset; that must not count as a second rollback or a placement.
    assert drive(model, "T1", "BLUE A-4", -1.0) == "BLUE A-3"
    assert model.snapshot().trains[0].previous_block_id == "BLUE A-2"


def test_rollback_through_a_switch_follows_its_position() -> None:
    """Check rolling back from 64 through 63 takes the switch's leg."""
    model = make_model()
    drive(model, "T1", "GREEN K-63", 1.0)
    assert drive(model, "T1", "GREEN K-63") == "GREEN K-64"
    assert drive(model, "T1", "GREEN K-64", -1.0) == "GREEN K-63"
    # Switch 63 is NORMAL (leg 62), so rolling on goes to 62.
    assert drive(model, "T1", "GREEN K-63", -1.0) == "GREEN J-62"


@pytest.mark.parametrize("position, expected", [
    (SwitchPosition.NORMAL, "BLUE B-6"),
    (SwitchPosition.REVERSE, "BLUE C-11"),
])
def test_train_takes_the_commanded_leg(
    position: SwitchPosition, expected: str
) -> None:
    """Check that a train follows the switch the Track Controller set."""
    model = make_model()
    switch = cmd(switch_commands={"BLUE A-5": position})
    drive(model, "T1", "BLUE A-4", 1.0, switch)
    drive(model, "T1", "BLUE A-4")
    assert drive(model, "T1", "BLUE A-5") == expected
    snap = model.snapshot().outputs.controller
    assert snap.switch_states["BLUE A-5"] is position


def test_two_trains_each_occupy_their_block() -> None:
    """Check occupancy with two trains on the track."""
    out = make_model().step(DT_S, make_inputs({
        "T1": report("GREEN A-1", 1.0), "T2": report("RED A-1", 1.0)}))
    occupied = {b for b, o in out.controller.block_occupancy.items() if o}
    assert occupied == {"GREEN A-1", "RED A-1"}


def test_train_leaving_the_inputs_leaves_the_track() -> None:
    """Check that a train no longer reported frees its block."""
    model = make_model()
    model.step(DT_S, make_inputs({"T1": report("GREEN A-1", 1.0)}))
    out = model.step(DT_S, make_inputs())
    assert not any(out.controller.block_occupancy.values())
    assert "T1" not in out.train_feeds


def test_train_runs_into_the_yard() -> None:
    """Check that a yard leg removes the train from the track."""
    model = make_model()
    to_yard = cmd(switch_commands={"GREEN I-57": SwitchPosition.REVERSE})
    drive(model, "T1", "GREEN I-56", 1.0, to_yard)
    drive(model, "T1", "GREEN I-56")
    out = model.step(DT_S, make_inputs({"T1": report("GREEN I-57", FAR_M)}))
    assert "T1" not in out.train_feeds
    assert not out.controller.block_occupancy["GREEN I-57"]


def test_block_changed_is_recorded_not_used() -> None:
    """Check that block_changed alone never moves a train."""
    model = make_model()
    flagged = report("BLUE A-3", 1.0)
    flagged = type(flagged)(flagged.block_id, flagged.offset_m,
                            flagged.actual_speed_mps, True,
                            flagged.passenger_capacity)
    out = model.step(DT_S, make_inputs({"T1": flagged}))
    assert out.train_feeds["T1"].track_info.block_id == "BLUE A-3"


# --------------------------------------------------------------------------- #
# Signal seen on entry
# --------------------------------------------------------------------------- #

def test_signal_seen_only_on_the_entry_tick() -> None:
    """Check the colour is sent once, and later changes do not reach it."""
    model = make_model()
    yellow = cmd(signal_commands={"BLUE A-4": SignalAspect.YELLOW})
    drive(model, "T1", "BLUE A-3", 1.0, yellow)
    out = model.step(DT_S, make_inputs({"T1": report("BLUE A-3", FAR_M)}))
    assert out.signal_seen["T1"] is SignalAspect.YELLOW

    green = cmd(signal_commands={"BLUE A-4": SignalAspect.GREEN})
    out = model.step(DT_S, make_inputs(
        {"T1": report("BLUE A-4", 5.0)}, green))
    assert out.signal_seen["T1"] is None
    assert out.controller.signal_states["BLUE A-4"] is SignalAspect.GREEN


def test_no_signal_seen_in_a_block_without_a_light() -> None:
    """Check entering an ordinary block sends no colour."""
    model = make_model()
    drive(model, "T1", "BLUE A-2", 1.0)
    out = model.step(DT_S, make_inputs({"T1": report("BLUE A-2", FAR_M)}))
    assert out.signal_seen["T1"] is None


# --------------------------------------------------------------------------- #
# Tickets and boarding
# --------------------------------------------------------------------------- #

def test_ticket_sales_go_to_the_track_controller() -> None:
    """Check one sale per station per tick at probability 1."""
    out = make_model(ticket_probability=1.0).step(DT_S, make_inputs())
    assert out.controller.ticket_sales["PIONEER"] == 1
    assert set(out.controller.ticket_sales.values()) == {1}


def test_ticket_sales_are_reproducible_with_a_seed() -> None:
    """Check that the same seed gives the same sales."""
    runs = []
    for _ in range(2):
        model = make_model(ticket_probability=0.5, seed=7)
        runs.append([
            dict(model.step(DT_S, make_inputs()).controller.ticket_sales)
            for _ in range(20)
        ])
    assert runs[0] == runs[1]


def test_stopped_train_boards_up_to_its_capacity() -> None:
    """Check boarding is bounded by waiting passengers and capacity."""
    model = make_model(ticket_probability=1.0)
    for _ in range(3):
        model.step(DT_S, make_inputs())
    out = model.step(DT_S, make_inputs(
        {"T1": report("BLUE B-10", 1.0, speed_mps=0.0, capacity=2)}))
    assert out.train_feeds["T1"].passengers_boarded == 2
    assert model.snapshot().waiting_passengers["B"] == 2


def test_moving_train_does_not_board() -> None:
    """Check that no one boards while the train is moving."""
    model = make_model(ticket_probability=1.0)
    out = model.step(DT_S, make_inputs(
        {"T1": report("BLUE B-10", 1.0, speed_mps=3.0)}))
    assert out.train_feeds["T1"].passengers_boarded == 0


# --------------------------------------------------------------------------- #
# Failures, environment and test-only commands
# --------------------------------------------------------------------------- #

def test_failure_reaches_the_outputs_between_steps() -> None:
    """Check that an injected failure is reported before the next step."""
    model = make_model()
    model.step(DT_S, make_inputs())
    model.set_block_failure("GREEN A-1", TrackFailure.BROKEN_RAIL)
    status = model.snapshot().outputs.controller.failure_status
    assert status["GREEN A-1"] is TrackFailure.BROKEN_RAIL
    out = model.step(DT_S, make_inputs())
    assert out.controller.failure_status["GREEN A-1"] is (
        TrackFailure.BROKEN_RAIL)


def test_ambient_temperature_is_stored() -> None:
    """Check the environment input reaches the snapshot."""
    model = make_model()
    model.step(DT_S, make_inputs(ambient_temp_c=-4.0))
    assert model.snapshot().ambient_temp_c == -4.0


def test_edit_block_changes_where_the_boundary_is() -> None:
    """Check a test-only length edit moves the block end."""
    model = make_model()
    model.edit_block("BLUE A-3", BlockEdit(length_m=10.0))
    drive(model, "T1", "BLUE A-3", 1.0)
    assert drive(model, "T1", "BLUE A-3", 11.0) == "BLUE A-4"


def test_reset_clears_trains_and_commands() -> None:
    """Check reset returns the freshly loaded state."""
    model = make_model()
    model.step(DT_S, make_inputs({"T1": report("GREEN A-1", 1.0)}, cmd(
        switch_commands={"BLUE A-5": SwitchPosition.REVERSE})))
    model.reset()
    snap = model.snapshot()
    assert snap.trains == ()
    assert snap.outputs.controller.switch_states["BLUE A-5"] is (
        SwitchPosition.NORMAL)


# --------------------------------------------------------------------------- #
# Rejected input
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("bad_inputs", [
    make_inputs({"T1": report("NOWHERE 1")}),
    make_inputs(controller=cmd(
        switch_commands={"BLUE A-4": SwitchPosition.REVERSE})),
    make_inputs(controller=cmd(
        signal_commands={"BLUE A-3": SignalAspect.GREEN})),
    make_inputs(controller=cmd(commanded_speed_mps={"BLUE A-3": -1})),
    make_inputs(controller=cmd(commanded_speed_mps={"BLUE A-3": 12.5})),
    make_inputs(controller=cmd(commanded_speed_mps={"BLUE A-3": True})),
    make_inputs(controller=cmd(commanded_speed_mps={"NOWHERE 1": 5})),
    make_inputs(controller=cmd(
        commanded_authority={"BLUE A-3": "NOWHERE 1"})),
    make_inputs(controller=cmd(
        commanded_authority={"NOWHERE 1": "BLUE A-3"})),
    make_inputs({"T1": report("BLUE A-3", float("nan"))}),
    make_inputs(ambient_temp_c=float("inf")),
], ids=[
    "unknown block in train report",
    "switch command on a block with no switch",
    "signal command on a block with no light",
    "negative commanded speed",
    "fractional commanded speed",
    "boolean commanded speed",
    "commanded speed for an unknown block",
    "authority naming an unknown block",
    "authority for an unknown block",
    "NaN train offset",
    "infinite ambient temperature",
])
def test_invalid_input_changes_nothing(bad_inputs: object) -> None:
    """Check rejection, and that the state is exactly as before."""
    model = make_model()
    model.step(DT_S, make_inputs({"T1": report("GREEN A-1", 1.0)}))
    before = model.snapshot()
    with pytest.raises(InvalidInputError):
        model.step(DT_S, bad_inputs)  # type: ignore[arg-type]
    assert model.snapshot() == before


@pytest.mark.parametrize("dt", [0.0, -0.1, float("nan")])
def test_bad_dt_is_rejected(dt: float) -> None:
    """Check that dt must be finite and positive."""
    with pytest.raises(InvalidInputError):
        make_model().step(dt, make_inputs())


def test_unknown_block_failure_is_rejected() -> None:
    """Check failure injection names a real block."""
    with pytest.raises(UnknownIdError):
        make_model().set_block_failure("NOWHERE 1", TrackFailure.POWER)
