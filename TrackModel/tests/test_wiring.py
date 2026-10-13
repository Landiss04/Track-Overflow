"""Every input reaches its output."""

from __future__ import annotations

import dataclasses

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
from tests.helpers import (
    DT_S,
    OVERSHOOT_M,
    make_inputs,
    make_model,
    past_end,
    report,
)


def cmd(**kwargs: object) -> TrackControllerCommands:
    """Return Track Controller commands with only the given fields."""
    return TrackControllerCommands(**kwargs)  # type: ignore[arg-type]


def drive(model: TrackModel, train_id: str, block_id: str,
          offset_m: float | None = None,
          controller: TrackControllerCommands | None = None) -> str:
    """Report ``offset_m`` in ``block_id``; return the train's new block.

    With no offset, report one that just crosses the block's end.
    """
    if offset_m is None:
        offset_m = past_end(model, block_id)
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
            commanded_authority={"GREEN A-3": 5}),
    ))
    feed = out.train_feeds["T1"]
    assert feed.track_info.block_id == "GREEN A-3"
    assert feed.track_info.speed_limit_mps == pytest.approx(45 / 3.6)
    assert feed.track_signal.commanded_speed_mps == 12
    assert isinstance(feed.track_signal.commanded_speed_mps, int)
    assert feed.track_signal.authority_blocks == 5
    assert feed.beacon is not None
    assert feed.beacon.station_name == "PIONEER"


def test_speed_and_authority_come_from_the_occupied_block() -> None:
    """Check both change as the train enters a block with other values."""
    model = make_model()
    commands = cmd(
        commanded_speed_mps={"BLUE A-3": 10, "BLUE A-4": 5},
        commanded_authority={"BLUE A-3": 2, "BLUE A-4": 6},
    )
    drive(model, "T1", "BLUE A-3", 1.0, commands)
    out = model.step(DT_S, make_inputs({"T1": report("BLUE A-3", 1.0)}))
    signal = out.train_feeds["T1"].track_signal
    assert (signal.commanded_speed_mps, signal.authority_blocks) == (
        10, 2)
    end = past_end(model, "BLUE A-3")
    out = model.step(DT_S, make_inputs({"T1": report("BLUE A-3", end)}))
    signal = out.train_feeds["T1"].track_signal
    assert (signal.commanded_speed_mps, signal.authority_blocks) == (
        5, 6)


def test_two_trains_in_one_block_get_the_same_signal() -> None:
    """Check the track circuit is the block's, not the train's."""
    out = make_model().step(DT_S, make_inputs(
        {"T1": report("GREEN A-3", 1.0), "T2": report("GREEN A-3", 20.0)},
        cmd(commanded_speed_mps={"GREEN A-3": 7},
            commanded_authority={"GREEN A-3": 3}),
    ))
    assert (out.train_feeds["T1"].track_signal
            == out.train_feeds["T2"].track_signal)


def test_uncommanded_block_sends_zero_and_no_authority() -> None:
    """Check a block with no command yet carries 0 m/s and no authority."""
    out = make_model().step(DT_S, make_inputs({"T1": report("BLUE A-2")}))
    signal = out.train_feeds["T1"].track_signal
    assert signal.commanded_speed_mps == 0
    assert signal.authority_blocks == 0


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
    end = past_end(model, "BLUE A-3")
    out = model.step(DT_S, make_inputs({"T1": report("BLUE A-3", end)}))
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
    # 1.0 m was carried into A-4 (0.5 m overshoot twice), so -2 m is
    # 1 m back past its start.
    assert drive(model, "T1", "BLUE A-4", -2.0) == "BLUE A-3"
    # Back at A-3's far end: rolling its whole 50 m reaches A-2.
    assert drive(model, "T1", "BLUE A-3", -50.0) == "BLUE A-2"
    # Forward again: still the original direction of travel.
    assert drive(model, "T1", "BLUE A-2") == "BLUE A-3"


def test_slow_rollback_stays_in_the_block_it_rolled_into() -> None:
    """Check a train that rolls back into a block is at its far end.

    The Train Model restarts its offset at 0 in the new block, so its
    next reports are small negatives. They must move the train back
    within the block, not one more block every tick.
    """
    model = make_model()
    drive(model, "T1", "BLUE A-3", 1.0)
    drive(model, "T1", "BLUE A-3")
    assert drive(model, "T1", "BLUE A-4", -1.0) == "BLUE A-3"
    for offset in (-1.0, -2.0, -3.0, -10.0):
        assert drive(model, "T1", "BLUE A-3", offset) == "BLUE A-3"
    assert model.snapshot().trains[0].offset_m == pytest.approx(
        50.0 - (1.0 - OVERSHOOT_M) - 10.0)


def test_forward_overshoot_is_carried_into_the_next_block() -> None:
    """Check the distance past a block's end counts in the next block."""
    model = make_model()
    drive(model, "T1", "BLUE A-3", 1.0)
    assert drive(model, "T1", "BLUE A-3", 52.0) == "BLUE A-4"
    # The Train Model now reports 0 + 47 m: 2 m carried, so 49 m in.
    assert drive(model, "T1", "BLUE A-4", 47.0) == "BLUE A-4"
    assert drive(model, "T1", "BLUE A-4", 48.0) == "BLUE A-5"


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
    # Switch 63 is NORMAL (leg 62), so rolling on through 63's 100 m
    # goes to 62.
    assert drive(model, "T1", "GREEN K-63", -100.0) == "GREEN J-62"


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
    end = past_end(model, "GREEN I-57")
    out = model.step(DT_S, make_inputs({"T1": report("GREEN I-57", end)}))
    assert "T1" not in out.train_feeds
    assert not out.controller.block_occupancy["GREEN I-57"]


def test_block_changed_is_recorded_not_used() -> None:
    """Check that block_changed alone never moves a train."""
    model = make_model()
    flagged = dataclasses.replace(report("BLUE A-3", 1.0), block_changed=True)
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
    end = past_end(model, "BLUE A-3")
    out = model.step(DT_S, make_inputs({"T1": report("BLUE A-3", end)}))
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
    end = past_end(model, "BLUE A-2")
    out = model.step(DT_S, make_inputs({"T1": report("BLUE A-2", end)}))
    assert out.signal_seen["T1"] is None


# --------------------------------------------------------------------------- #
# Tickets and boarding
# --------------------------------------------------------------------------- #

def _stations_by_line(model: TrackModel) -> dict[str, int]:
    # How many stations (pooled by name) each line has.
    stations: dict[str, set[str]] = {}
    for block in model.snapshot().blocks:
        stations.setdefault(block.line, set())
        if block.station_name is not None:
            stations[block.line].add(block.station_name)
    return {line: len(names) for line, names in stations.items()}


def test_ticket_sales_go_to_the_ctc_office() -> None:
    """Check one sale per station per tick, by line, at probability 1."""
    model = make_model(ticket_probability=1.0)
    out = model.step(DT_S, make_inputs())
    assert dict(out.ctc.tickets_sold_now) == _stations_by_line(model)
    assert not hasattr(out.controller, "ticket_sales")


def test_ticket_sales_are_events_with_no_running_total() -> None:
    """Check each tick reports only its own sales and no total."""
    model = make_model(ticket_probability=1.0)
    per_tick = _stations_by_line(model)
    for _ in range(3):
        out = model.step(DT_S, make_inputs())
        assert dict(out.ctc.tickets_sold_now) == per_tick
        assert not hasattr(out.ctc, "tickets_sold_total")


def test_reset_clears_this_ticks_sales() -> None:
    """Check that a reset leaves every line at zero sold now."""
    model = make_model(ticket_probability=1.0)
    model.step(DT_S, make_inputs())
    model.reset()
    assert set(model.snapshot().outputs.ctc.tickets_sold_now.values()) == {0}


def test_ticket_sales_are_reproducible_with_a_seed() -> None:
    """Check that the same seed gives the same sales."""
    runs = []
    for _ in range(2):
        model = make_model(ticket_probability=0.5, seed=7)
        runs.append([
            dict(model.step(DT_S, make_inputs()).ctc.tickets_sold_now)
            for _ in range(20)
        ])
    assert runs[0] == runs[1]


def test_stopped_train_boards_up_to_its_capacity() -> None:
    """Check boarding is bounded by waiting passengers and capacity."""
    model = make_model(ticket_probability=1.0)
    for _ in range(3):
        model.step(DT_S, make_inputs())
    out = model.step(DT_S, make_inputs(
        {"T1": report("BLUE B-10", 1.0, speed_mps=0.0, capacity=2,
                      doors_open=True)}))
    assert out.train_feeds["T1"].passengers_boarded == 2
    assert model.snapshot().waiting_passengers["B"] == 2


def test_moving_train_does_not_board() -> None:
    """Check that no one boards while the train is moving."""
    model = make_model(ticket_probability=1.0)
    out = model.step(DT_S, make_inputs(
        {"T1": report("BLUE B-10", 1.0, speed_mps=3.0, doors_open=True)}))
    assert out.train_feeds["T1"].passengers_boarded == 0


def test_closed_doors_board_nobody_and_keep_the_queue() -> None:
    """Check a stopped train with doors shut takes no one off the queue."""
    model = make_model(ticket_probability=1.0)
    out = model.step(DT_S, make_inputs(
        {"T1": report("BLUE B-10", 1.0, speed_mps=0.0)}))
    assert out.train_feeds["T1"].passengers_boarded == 0
    assert model.snapshot().waiting_passengers["B"] == 1


# --------------------------------------------------------------------------- #
# Integration with the Train Model
# --------------------------------------------------------------------------- #

def test_report_with_no_block_yet_is_ignored() -> None:
    """Check a train reporting block "" is skipped, not a rejected tick.

    The Train Model reports no block before its first step.
    """
    model = make_model()
    out = model.step(DT_S, make_inputs({
        "T1": report("", 0.0), "T2": report("GREEN A-1", 1.0)}))
    assert "T1" not in out.train_feeds
    assert out.train_feeds["T2"].track_info.block_id == "GREEN A-1"


def test_train_reporting_no_block_leaves_the_track() -> None:
    """Check a placed train that reports "" is taken off the track."""
    model = make_model()
    model.step(DT_S, make_inputs({"T1": report("GREEN A-1", 1.0)}))
    out = model.step(DT_S, make_inputs({"T1": report("", 0.0)}))
    assert not out.controller.block_occupancy["GREEN A-1"]


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
        commanded_authority={"BLUE A-3": -1})),
    make_inputs(controller=cmd(
        commanded_authority={"NOWHERE 1": 3})),
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
    "negative authority",
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
