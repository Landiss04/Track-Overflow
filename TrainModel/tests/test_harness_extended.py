"""Extended tests for the harness and state layer driving the real model.

Exercised from Python without loading QML.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from typing import Any

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from train_model import harness as harness_module  # noqa: E402
from train_model.interface import TrainConfig  # noqa: E402
from train_model.link import LocalLink  # noqa: E402
from train_model.state import TrainModelState  # noqa: E402

CFG = TrainConfig()


@pytest.fixture(scope="module", autouse=True)
def qt_app() -> Iterator[None]:
    """Provide the Qt application the harness timer needs."""
    app = QCoreApplication.instance() or QCoreApplication([])
    yield
    del app


def make() -> tuple[TrainModelState, Any]:
    """Return a fresh model state and a harness driving it."""
    state = TrainModelState()
    return state, harness_module.TestHarnessState(LocalLink(state))


def snap(state: TrainModelState) -> dict[str, Any]:
    """Read the state's snapshot property as QML would."""
    value: dict[str, Any] = state.property("snapshot")
    return value


def outputs(harness: Any) -> dict[str, Any]:
    """Index the visible output rows by signal name."""
    return {row["name"]: row["value"] for row in harness.property("outputs")}


@pytest.mark.parametrize(("power_w", "shown_w"), [
    (0.0, 0.0), (100_000.0, 100_000.0), (1_000_000.0, CFG.p_max_w)])
def test_power_consumption_display_is_clamped(
        power_w: float, shown_w: float) -> None:
    """Check displayed power is the command clamped to P_max."""
    state, harness = make()
    harness.setInput("power_command", power_w)
    assert harness.sendInputs()
    assert snap(state)["power_consumption"] == shown_w


def test_negative_power_send_is_rejected() -> None:
    """Check a negative power row is refused with a visible error."""
    state, harness = make()
    before = snap(state)
    harness.setInput("power_command", -1_000.0)
    assert not harness.sendInputs()
    assert harness.property("inputError")
    assert harness.property("tick") == 0
    assert snap(state) == before


def test_negative_authority_send_is_rejected() -> None:
    """Check a negative authority row is refused with a visible error."""
    state, harness = make()
    before = snap(state)
    harness.setInput("authority", -1)
    assert not harness.sendInputs()
    assert harness.property("inputError")
    assert harness.property("tick") == 0
    assert snap(state) == before


def test_power_consumption_zero_under_engine_failure() -> None:
    """Check no power is displayed while the engine has failed."""
    state, harness = make()
    state.setFailure("engine_failure", True)
    harness.setInput("power_command", 100_000.0)
    harness.sendInputs()
    assert snap(state)["power_consumption"] == 0.0


def test_grade_row_reaches_the_model_in_degrees() -> None:
    """Check the grade row is applied as degrees, unconverted."""
    state, harness = make()
    harness.setInput("grade", 2.0)
    harness.sendInputs()
    th = math.radians(2.0)
    g = CFG.g_mps2
    expected = -g * math.sin(th) + CFG.c_rr * g * math.cos(th)
    assert snap(state)["acceleration"] == pytest.approx(expected, rel=1e-12)


def test_direction_reverse_during_rollback() -> None:
    """Check the overview shows Reverse while the train rolls back."""
    state, harness = make()
    harness.setInput("grade", 3.0)
    harness.sendInputs()
    for _ in range(10):
        harness.advanceTick()
    assert snap(state)["direction"] == "Reverse"
    assert snap(state)["actual_speed"] < 0.0


def test_previous_block_tracks_block_changes() -> None:
    """Check the previous block is kept when the block changes."""
    state, harness = make()
    harness.setInput("block", "GREEN I")
    harness.sendInputs()
    harness.setInput("block", "GREEN J")
    harness.sendInputs()
    assert snap(state)["current_block"] == "GREEN J"
    assert snap(state)["previous_block"] == "GREEN I"


def test_next_station_shows_only_a_received_beacon() -> None:
    """Check the beacon station shows while received, then clears."""
    state, harness = make()
    harness.setInput("beacon_station", "Dormont")
    harness.sendInputs()
    assert snap(state)["next_station"] == "Dormont"
    harness.setInput("beacon_station", "")
    harness.sendInputs()
    assert snap(state)["next_station"] == "—"


@pytest.mark.parametrize(("ticks", "shown"), [
    (9, "00:00:00"), (10, "00:00:01"), (600, "00:01:00")])
def test_elapsed_clock_formatting(ticks: int, shown: str) -> None:
    """Check elapsed simulated time is shown as hh:mm:ss."""
    _, harness = make()
    harness.sendInputs()
    for _ in range(ticks - 1):
        harness.advanceTick()
    assert harness.property("tick") == ticks
    assert harness.property("elapsed") == shown


def test_int_rows_truncate_float_input() -> None:
    """Check an int row coerces a decimal string by truncation."""
    state, harness = make()
    harness.setInput("station", "GLENBURY")
    harness.setInput("left_door_command", True)
    harness.setInput("passengers_boarded", "12.9")
    harness.sendInputs()
    assert snap(state)["passengers"] == 12


def test_unknown_input_and_failure_names_raise() -> None:
    """Check unknown row and failure names are rejected."""
    state, harness = make()
    with pytest.raises(KeyError):
        harness.setInput("no_such_row", 1)
    with pytest.raises(KeyError):
        state.setFailure("no_such_failure", True)


def test_station_row_reaches_the_model_and_persists() -> None:
    """Check the station row is sent and kept on later ticks."""
    state, harness = make()
    harness.setInput("station", "GLENBURY")
    harness.sendInputs()
    harness.advanceTick()
    assert state.command_values()["station"] == "GLENBURY"
    assert harness.property("inputValues")["station"] == "GLENBURY"


@pytest.mark.parametrize(("station", "door", "boarded"), [
    ("", False, 0), ("", True, 0), ("GLENBURY", False, 0),
    ("GLENBURY", True, 30)])
def test_harness_boarding_needs_station_and_open_door(
        station: str, door: bool, boarded: int) -> None:
    """Check the test page boards only at a station with a door open."""
    state, harness = make()
    harness.setInput("station", station)
    harness.setInput("right_door_command", door)
    harness.setInput("passengers_boarded", 30)
    harness.sendInputs()
    assert snap(state)["passengers"] == boarded
    assert outputs(harness)["passenger_capacity"] == (
        snap(state)["capacity"] - boarded
    )


def test_door_interlock_is_visible_in_the_test_ui() -> None:
    """Check a door commanded open while moving shows closed until the stop.

    The output shows the interlock; the input row keeps the command.
    """
    state, harness = make()
    harness.setInput("power_command", CFG.p_max_w)
    harness.sendInputs()
    for _ in range(20):
        harness.advanceTick()
    harness.setInput("power_command", 0.0)
    harness.setInput("left_door_command", True)
    harness.sendInputs()
    assert snap(state)["actual_speed"] > 0.0
    assert outputs(harness)["left_door_state"] is False
    assert harness.property("inputValues")["left_door_command"] is True
    harness.setInput("service_brake_command", True)
    harness.sendInputs()
    for _ in range(100):
        harness.advanceTick()
        if snap(state)["left_door"]:
            break
    assert snap(state)["actual_speed"] == 0.0
    assert outputs(harness)["left_door_state"] is True


def test_reset_clears_the_station() -> None:
    """Check Reset module clears the station row."""
    state, harness = make()
    harness.setInput("station", "GLENBURY")
    harness.sendInputs()
    harness.resetModule()
    assert harness.property("inputValues")["station"] == ""
    assert state.command_values()["station"] == ""
