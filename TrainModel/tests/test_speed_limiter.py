"""Tests for the test UI's stand-in speed limiter.

The control law alone, then the harness sending its limited commands to
the real Train Model. No QML is loaded.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from train_model import harness as harness_module  # noqa: E402
from train_model.interface import TrainConfig  # noqa: E402
from train_model.link import LocalLink  # noqa: E402
from train_model.speed_limiter import (  # noqa: E402
    BRAKE_MARGIN_MPS,
    RELEASE_MARGIN_MPS,
    SpeedLimiter,
)
from train_model.state import TrainModelState  # noqa: E402

DT = 0.1
CAP = 50 / 3.6                       # the Blue Line's speed limit
V_MAX = TrainConfig().v_max_mps
MPH = 2.236936


@pytest.fixture(scope="module", autouse=True)
def qt_app() -> Iterator[None]:
    """Provide the Qt application the harness timer needs."""
    app = QCoreApplication.instance() or QCoreApplication([])
    yield
    del app


def make_harness(**kwargs: Any) -> tuple[TrainModelState, Any]:
    """Return a fresh model state and a harness driving it."""
    state = TrainModelState()
    return state, harness_module.TestHarnessState(LocalLink(state), **kwargs)


def run(harness: Any, ticks: int) -> None:
    """Advance the harness clock by hand."""
    for _ in range(ticks):
        harness.advanceTick()


def test_well_below_the_cap_the_entered_power_passes_through() -> None:
    """Check that the limiter leaves the power alone far from the cap."""
    limited = SpeedLimiter().apply(DT, CAP, 0.0, 120_000.0, False)
    assert limited.power_w == 120_000.0
    assert not limited.service_brake
    assert not limited.limiting


@pytest.mark.parametrize("speed", [0.0, CAP - 1.0, CAP, CAP + 0.4, -2.0])
@pytest.mark.parametrize("power", [0.0, 50_000.0, 480_000.0])
def test_the_limiter_never_raises_the_power(
        speed: float, power: float) -> None:
    """Check that the output is between zero and the entered power."""
    limited = SpeedLimiter().apply(DT, CAP, speed, power, False)
    assert 0.0 <= limited.power_w <= power


def test_well_over_the_cap_power_is_cut_and_the_brake_applied() -> None:
    """Check the brake engages past the margin and holds under the cap."""
    limiter = SpeedLimiter()
    over = limiter.apply(DT, CAP, CAP + BRAKE_MARGIN_MPS + 0.1, 480e3, False)
    assert over.service_brake and over.limiting
    assert over.power_w == 0.0
    # Back under the cap, inside the release margin: still braking.
    held = limiter.apply(DT, CAP, CAP - 0.1, 480e3, False)
    assert held.service_brake and held.power_w == 0.0
    # Past the release margin: released.
    released = limiter.apply(
        DT, CAP, CAP - RELEASE_MARGIN_MPS - 0.1, 480e3, False)
    assert not released.service_brake


def test_an_entered_service_brake_is_kept() -> None:
    """Check that the limiter never releases the operator's brake."""
    limited = SpeedLimiter().apply(DT, CAP, 0.0, 0.0, True)
    assert limited.service_brake


def test_the_integral_does_not_wind_up_while_saturated() -> None:
    """Check that far below the cap the integral stays put."""
    limiter = SpeedLimiter()
    for _ in range(1000):
        limiter.apply(DT, CAP, 0.0, 480_000.0, False)
    assert limiter.state.integral_m == 0.0


def test_braking_discards_the_wound_up_integral() -> None:
    """Check that the integral is dropped once the limiter has to brake.

    An integral built up while the train could not respond, such as
    during an engine failure, would otherwise come back as power every
    time the brake released.
    """
    limiter = SpeedLimiter()
    for _ in range(300):
        limiter.apply(DT, CAP, CAP - 0.3, 480e3, False)
    assert limiter.state.integral_m > 1.0
    over = limiter.apply(DT, CAP, CAP + BRAKE_MARGIN_MPS + 0.1, 480e3, False)
    assert over.service_brake
    assert limiter.state.integral_m == 0.0


def test_reset_forgets_the_state() -> None:
    """Check that reset clears the integral and the brake."""
    limiter = SpeedLimiter()
    limiter.apply(DT, CAP, CAP + 5.0, 480e3, False)
    limiter.reset()
    assert limiter.state.integral_m == 0.0
    assert not limiter.state.braking


@pytest.mark.parametrize("passengers", [0, 222])
def test_full_power_settles_at_the_blue_line_speed_limit(
        passengers: int) -> None:
    """Check full power on the Blue Line settles at 50 km/h, empty or full."""
    state, harness = make_harness()
    if passengers:
        # Board at a station with a door open, then close it.
        for name, value in {"station": "Station B", "left_door_command": True,
                            "passengers_boarded": passengers}.items():
            harness.setInput(name, value)
        assert harness.sendInputs()
        harness.setInput("left_door_command", False)
        harness.setInput("station", "")
    harness.setInput("power_command", 480_000.0)
    assert harness.sendInputs()
    speeds = []
    for _ in range(900):
        harness.advanceTick()
        speeds.append(state.outputs().controller.actual_speed_mps)
    assert max(speeds) < CAP + BRAKE_MARGIN_MPS
    assert speeds[-1] == pytest.approx(CAP, abs=0.05)
    assert harness.limiting
    # The row keeps the entered power; the model receives less.
    assert harness.inputValues["power_command"] == 480_000.0
    assert state.snapshot["power_command"] < 480_000.0


def test_without_a_speed_limit_the_cap_is_the_maximum_speed() -> None:
    """Check that the vehicle's maximum speed caps a manual track."""
    state, harness = make_harness(track=None)
    assert harness.speedCap == pytest.approx(V_MAX * MPH)
    harness.setInput("power_command", 480_000.0)
    assert harness.sendInputs()
    run(harness, 1500)
    speed = state.outputs().controller.actual_speed_mps
    assert speed == pytest.approx(V_MAX, abs=0.05)


def test_lowering_the_speed_limit_brakes_down_to_it() -> None:
    """Check that a lower limit mid-run brings the train down to it."""
    state, harness = make_harness(track=None)
    harness.setInput("power_command", 480_000.0)
    harness.setInput("speed_limit", CAP)
    assert harness.sendInputs()
    run(harness, 600)
    harness.setInput("speed_limit", 8.0)
    assert harness.sendInputs()
    assert state.outputs().controller.service_brake_active
    run(harness, 600)
    assert harness.speedCap == pytest.approx(8.0 * MPH)
    speed = state.outputs().controller.actual_speed_mps
    assert speed == pytest.approx(8.0, abs=0.05)


def test_after_an_engine_failure_the_speed_settles_without_hunting() -> None:
    """Check one brake application, not a cycle, after the failure.

    The limiter cannot see the failure, so its integral grows while the
    train coasts. Clearing the failure brings that power back at once.
    """
    state, harness = make_harness()
    harness.setInput("power_command", 480_000.0)
    assert harness.sendInputs()
    run(harness, 600)
    state.setFailure("engine_failure", True)
    run(harness, 600)
    state.setFailure("engine_failure", False)
    braking, speeds = [], []
    for _ in range(600):
        harness.advanceTick()
        braking.append(state.outputs().controller.service_brake_active)
        speeds.append(state.outputs().controller.actual_speed_mps)
    applications = sum(1 for was, now in zip(braking, braking[1:])
                       if now and not was) + braking[0]
    assert applications <= 1
    # Settled for the last 20 s.
    assert all(abs(v - CAP) < 0.05 for v in speeds[-200:])


def test_level_track_never_needs_the_brake() -> None:
    """Check full power to the cap on level track never brakes."""
    state, harness = make_harness(track=None)
    harness.setInput("power_command", 480_000.0)
    harness.setInput("speed_limit", CAP)
    assert harness.sendInputs()
    for _ in range(900):
        harness.advanceTick()
        assert not state.outputs().controller.service_brake_active


@pytest.mark.parametrize("grade_deg", [-3.0, -5.0, -8.0])
def test_a_downhill_holds_the_cap_without_chattering(
        grade_deg: float) -> None:
    """Check a downhill cycles the brake slowly and stays at the cap.

    The service brake is on or off, so holding a downhill speed takes
    some cycling; braking as soon as gravity takes the train over the
    cap, and releasing well under it, keeps that slow (Kevin).
    """
    state, harness = make_harness(track=None)
    for name, value in {"power_command": 480_000.0, "speed_limit": CAP,
                        "grade": grade_deg}.items():
        harness.setInput(name, value)
    assert harness.sendInputs()
    run(harness, 1200)
    braking, speeds = [], []
    for _ in range(600):
        harness.advanceTick()
        braking.append(state.outputs().controller.service_brake_active)
        speeds.append(state.outputs().controller.actual_speed_mps)
    applications = sum(1 for was, now in zip(braking, braking[1:])
                       if now and not was)
    assert applications <= 16  # a minute; it was 38 at -5 degrees
    assert max(speeds) < CAP + 0.3
    assert min(speeds) > CAP - RELEASE_MARGIN_MPS - 0.25


def test_reset_clears_the_limiter() -> None:
    """Check that resetting the module also resets the limiter."""
    _, harness = make_harness()
    harness.setInput("power_command", 480_000.0)
    assert harness.sendInputs()
    run(harness, 400)
    assert harness.limiting
    harness.resetModule()
    assert not harness.limiting
