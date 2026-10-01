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
    return state, harness_module.TestHarnessState(state)


def snap(state: TrainModelState) -> dict[str, Any]:
    """Read the state's snapshot property as QML would."""
    value: dict[str, Any] = state.property("snapshot")
    return value


@pytest.mark.parametrize(("power_w", "shown_w"), [
    (-1_000.0, 0.0), (100_000.0, 100_000.0), (1_000_000.0, CFG.p_max_w)])
def test_power_consumption_display_is_clamped(
        power_w: float, shown_w: float) -> None:
    """Check displayed power is the command clamped to 0..P_max."""
    state, harness = make()
    harness.setInput("power_command", power_w)
    harness.sendInputs()
    assert snap(state)["power_consumption"] == shown_w


def test_power_consumption_zero_under_engine_failure() -> None:
    """Check no power is displayed while the engine has failed."""
    state, harness = make()
    state.setFailure("engine_failure", True)
    harness.sendInputs()
    assert snap(state)["power_consumption"] == 0.0


def test_grade_row_reaches_the_model_in_degrees() -> None:
    """Check the grade row is applied as degrees, unconverted."""
    state, harness = make()
    harness.setInput("power_command", 0.0)
    harness.setInput("grade", 2.0)
    harness.sendInputs()
    th = math.radians(2.0)
    g = CFG.g_mps2
    expected = -g * math.sin(th) + CFG.c_rr * g * math.cos(th)
    assert snap(state)["acceleration"] == pytest.approx(expected, rel=1e-12)


def test_direction_reverse_during_rollback() -> None:
    """Check the overview shows Reverse while the train rolls back."""
    state, harness = make()
    harness.setInput("power_command", 0.0)
    harness.setInput("grade", 3.0)
    harness.sendInputs()
    for _ in range(10):
        harness.advanceTick()
    assert snap(state)["direction"] == "Reverse"
    assert snap(state)["actual_speed"] < 0.0


def test_previous_block_tracks_block_changes() -> None:
    """Check the previous block is kept when the block changes."""
    state, harness = make()
    harness.sendInputs()
    harness.setInput("block", "GREEN J")
    harness.sendInputs()
    assert snap(state)["current_block"] == "GREEN J"
    assert snap(state)["previous_block"] == "GREEN I"


def test_last_beacon_is_kept_between_beacons() -> None:
    """Check the last station stays shown once the beacon is passed."""
    state, harness = make()
    harness.sendInputs()
    harness.setInput("beacon_station", "")
    harness.sendInputs()
    assert snap(state)["next_station"] == "Dormont"


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
