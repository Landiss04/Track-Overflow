"""Track heaters, track temperature, and what failures actually do."""

from __future__ import annotations

import math

import pytest

from track_model.interface import (
    InvalidInputError,
    SignalAspect,
    SwitchPosition,
    TrackControllerCommands,
    TrackFailure,
)
from track_model.model import (
    HEATER_ON_AT_C,
    HEATER_RISE_C,
    TRACK_TIME_CONSTANT_S,
    TrackModel,
)
from tests.helpers import DT_S, make_inputs, make_model, report

FAR_M = 10_000.0
ALL_FAILURES = [TrackFailure.BROKEN_RAIL, TrackFailure.TRACK_CIRCUIT,
                TrackFailure.POWER]


def heat(model: TrackModel, ambient: float | None, ticks: int) -> None:
    """Hold the ambient for ``ticks`` steps. The Track Model switches the
    heaters itself from it (D026, TM-3)."""
    for _ in range(ticks):
        model.step(DT_S, make_inputs(ambient_temp_c=ambient))


def heaters(model: TrackModel) -> set[bool]:
    """Every section's heater state, as a set."""
    return set(model.snapshot().outputs.controller.heater_states.values())


def expected_rise(ticks: int) -> float:
    """Heater warming after ``ticks`` steps from ambient."""
    return HEATER_RISE_C * (1 - math.exp(-ticks * DT_S
                                         / TRACK_TIME_CONSTANT_S))


# --------------------------------------------------------------------------- #
# Heaters and track temperature
# --------------------------------------------------------------------------- #

def test_every_section_has_a_heater_and_a_temperature() -> None:
    """Check heaters and temperatures are keyed by section, off at start."""
    out = make_model().step(DT_S, make_inputs()).controller
    green = sorted(s for s in out.heater_states if s.startswith("GREEN"))
    assert len(green) == 26                 # sections A to Z
    assert green[0] == "GREEN A" and green[-1] == "GREEN Z"
    assert set(out.track_temp_c) == set(out.heater_states)
    assert not any(out.heater_states.values())


def test_unknown_heater_section_is_rejected() -> None:
    """Check heater commands must name a real section."""
    with pytest.raises(InvalidInputError):
        make_model().step(DT_S, make_inputs(controller=(
            TrackControllerCommands(heater_commands={"GREEN ZZ": True}))))


def test_track_starts_at_ambient() -> None:
    """Check the first step sets every section to the ambient temperature
    (above freezing, so no heater runs)."""
    out = make_model().step(DT_S, make_inputs(ambient_temp_c=5.0))
    assert set(out.controller.track_temp_c.values()) == {5.0}


def test_heater_warms_its_section_toward_ambient_plus_rise() -> None:
    """Check one time constant closes about 63% of the gap."""
    model = make_model()
    ticks = int(TRACK_TIME_CONSTANT_S / DT_S)
    heat(model, ambient=-5.0, ticks=ticks)
    temps = model.snapshot().outputs.controller.track_temp_c
    assert temps["GREEN B"] == pytest.approx(-5.0 + expected_rise(ticks))
    assert temps["GREEN B"] - (-5.0) == pytest.approx(
        HEATER_RISE_C * 0.632, abs=0.01)


def test_heater_does_not_change_ambient() -> None:
    """Check ambient stays the input while every section warms alike."""
    model = make_model()
    heat(model, ambient=-5.0, ticks=500)
    snap = model.snapshot()
    assert snap.ambient_temp_c == -5.0
    temps = snap.outputs.controller.track_temp_c
    assert temps["GREEN C"] == temps["GREEN B"] > -5.0


def test_heaters_switch_at_the_freezing_point() -> None:
    """Check on at or below 0 C, off above it, with no hysteresis."""
    model = make_model()
    for ambient, on in ((5.0, False), (HEATER_ON_AT_C, True),
                        (0.1, False), (-0.1, True), (0.01, False)):
        heat(model, ambient=ambient, ticks=1)
        assert heaters(model) == {on}, ambient


def test_no_ambient_keeps_the_heaters_as_they_were() -> None:
    """Check a tick with no ambient leaves the heaters in their last
    state."""
    model = make_model()
    heat(model, ambient=-2.0, ticks=1)
    heat(model, ambient=None, ticks=5)
    assert heaters(model) == {True}
    heat(model, ambient=3.0, ticks=1)
    heat(model, ambient=None, ticks=5)
    assert heaters(model) == {False}


def test_a_heater_command_is_not_applied() -> None:
    """Check the Track Model ignores Track Controller heater commands
    (D026): they are accepted on the boundary but switch nothing."""
    model = make_model()
    out = model.step(DT_S, make_inputs(
        controller=TrackControllerCommands(heater_commands={"GREEN B": True}),
        ambient_temp_c=5.0))
    assert out.controller.heater_states["GREEN B"] is False


def test_track_follows_a_change_in_ambient_gradually() -> None:
    """Check the track lags a sudden ambient change, then catches up."""
    model = make_model()
    # Both above freezing, so no heater runs.
    heat(model, ambient=10.0, ticks=1)
    heat(model, ambient=1.0, ticks=1)
    first = model.snapshot().outputs.controller.track_temp_c["GREEN A"]
    assert 9.9 < first < 10.0
    heat(model, ambient=1.0, ticks=30_000)
    assert model.snapshot().outputs.controller.track_temp_c[
        "GREEN A"] == pytest.approx(1.0, abs=1e-3)


def test_heater_off_lets_the_track_cool_back() -> None:
    """Check heaters going off returns the track toward ambient."""
    model = make_model()
    heat(model, ambient=0.0, ticks=3000)                 # on
    warm = model.snapshot().outputs.controller.track_temp_c["GREEN B"]
    heat(model, ambient=0.5, ticks=3000)                 # off
    cooled = model.snapshot().outputs.controller.track_temp_c["GREEN B"]
    assert warm > 6.0 and cooled - 0.5 < (warm - 0.0) / 2


# --------------------------------------------------------------------------- #
# Every failure: the circuit reads occupied and carries nothing
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("failure", ALL_FAILURES)
def test_failed_block_reads_occupied(failure: TrackFailure) -> None:
    """Check a failed block reports occupied with no train in it."""
    model = make_model()
    model.set_block_failure("GREEN C-9", failure)
    out = model.step(DT_S, make_inputs())
    assert out.controller.block_occupancy["GREEN C-9"]
    assert not out.controller.block_occupancy["GREEN C-8"]


@pytest.mark.parametrize("failure", ALL_FAILURES)
def test_failed_block_carries_no_track_signal(failure: TrackFailure) -> None:
    """Check a train in a failed block gets 0 m/s and no authority."""
    model = make_model()
    model.set_block_failure("GREEN C-9", failure)
    out = model.step(DT_S, make_inputs(
        {"T1": report("GREEN C-9", 1.0)},
        TrackControllerCommands(
            commanded_speed_mps={"GREEN C-9": 12},
            commanded_authority={"GREEN C-9": 4}),
    ))
    signal = out.train_feeds["T1"].track_signal
    assert (signal.commanded_speed_mps, signal.authority_blocks) == (
        0, 0)


def test_clearing_a_failure_restores_the_block() -> None:
    """Check NONE gives back a clear block and a live circuit."""
    model = make_model()
    commands = TrackControllerCommands(commanded_speed_mps={"GREEN C-9": 12})
    model.set_block_failure("GREEN C-9", TrackFailure.BROKEN_RAIL)
    model.step(DT_S, make_inputs(controller=commands))
    model.set_block_failure("GREEN C-9", TrackFailure.NONE)
    out = model.step(DT_S, make_inputs({"T1": report("GREEN C-9", 1.0)},
                                       commands))
    assert out.train_feeds["T1"].track_signal.commanded_speed_mps == 12
    assert model.snapshot().outputs.controller.block_occupancy["GREEN C-9"]
    model.step(DT_S, make_inputs())
    assert not model.snapshot().outputs.controller.block_occupancy[
        "GREEN C-9"]


def test_failure_shows_as_occupied_before_the_next_step() -> None:
    """Check the read-back changes as soon as Murphy injects it."""
    model = make_model()
    model.step(DT_S, make_inputs())
    model.set_block_failure("GREEN C-9", TrackFailure.TRACK_CIRCUIT)
    assert model.snapshot().outputs.controller.block_occupancy["GREEN C-9"]


# --------------------------------------------------------------------------- #
# Power failure: devices in the block lose power
# --------------------------------------------------------------------------- #

def test_power_failure_freezes_the_switch() -> None:
    """Check a powerless switch ignores commands until power returns."""
    model = make_model()
    model.set_block_failure("GREEN D-13", TrackFailure.POWER)
    reverse = TrackControllerCommands(
        switch_commands={"GREEN D-13": SwitchPosition.REVERSE})
    out = model.step(DT_S, make_inputs(controller=reverse))
    assert out.controller.switch_states["GREEN D-13"] is SwitchPosition.NORMAL
    model.set_block_failure("GREEN D-13", TrackFailure.NONE)
    out = model.step(DT_S, make_inputs())
    assert out.controller.switch_states["GREEN D-13"] is (
        SwitchPosition.REVERSE)


def test_power_failure_turns_the_light_red_for_trains_too() -> None:
    """Check a powerless light reads RED and a train entering sees RED."""
    model = make_model()
    green = TrackControllerCommands(
        signal_commands={"GREEN D-14": SignalAspect.GREEN})
    model.set_block_failure("GREEN D-14", TrackFailure.POWER)
    model.step(DT_S, make_inputs({"T1": report("GREEN D-15", 1.0)}, green))
    out = model.step(DT_S, make_inputs({"T1": report("GREEN D-15", -1.0)}))
    assert out.controller.signal_states["GREEN D-14"] is SignalAspect.RED
    assert out.signal_seen["T1"] is SignalAspect.RED


def test_power_failure_drops_the_crossing_gates() -> None:
    """Check powerless gates read closed even when commanded open."""
    model = make_model()
    model.set_block_failure("GREEN E-19", TrackFailure.POWER)
    out = model.step(DT_S, make_inputs(controller=TrackControllerCommands(
        crossing_commands={"GREEN E-19": False})))
    assert out.controller.crossing_states["GREEN E-19"] is True


def test_power_failure_stops_its_sections_heaters() -> None:
    """Check heaters in a section with a powerless block stay off."""
    model = make_model()
    model.set_block_failure("GREEN B-5", TrackFailure.POWER)
    heat(model, ambient=0.0, ticks=100)                  # heaters on
    out = model.snapshot().outputs.controller
    assert out.heater_states["GREEN B"] is False
    assert out.heater_states["GREEN C"] is True
    assert out.track_temp_c["GREEN B"] == 0.0
    assert out.track_temp_c["GREEN C"] > 0.0


@pytest.mark.parametrize("failure", [TrackFailure.BROKEN_RAIL,
                                     TrackFailure.TRACK_CIRCUIT])
def test_other_failures_leave_devices_powered(failure: TrackFailure) -> None:
    """Check rail and circuit failures do not touch lights or switches."""
    model = make_model()
    for block in ("GREEN D-13", "GREEN D-14"):
        model.set_block_failure(block, failure)
    out = model.step(DT_S, make_inputs(controller=TrackControllerCommands(
        switch_commands={"GREEN D-13": SwitchPosition.REVERSE},
        signal_commands={"GREEN D-14": SignalAspect.GREEN})))
    assert out.controller.switch_states["GREEN D-13"] is (
        SwitchPosition.REVERSE)
    assert out.controller.signal_states["GREEN D-14"] is SignalAspect.GREEN
