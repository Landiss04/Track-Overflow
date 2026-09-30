"""Tests for the test harness driving the real Train Model.

These exercise ``TestHarnessState`` and ``TrainModelState`` from Python,
without loading any QML.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from train_model import harness as harness_module  # noqa: E402
from train_model.interface import TrainConfig  # noqa: E402
from train_model.state import TrainModelState  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def qt_app() -> Iterator[None]:
    """Provide the Qt application the harness timer needs."""
    app = QCoreApplication.instance() or QCoreApplication([])
    yield
    del app


def make_harness() -> tuple[TrainModelState, Any]:
    """Return a fresh model state and a harness driving it."""
    state = TrainModelState()
    return state, harness_module.TestHarnessState(state)


def snap(state: TrainModelState) -> dict[str, Any]:
    """Read the state's snapshot property as QML would."""
    value: dict[str, Any] = state.property("snapshot")
    return value


def test_every_input_row_is_mapped() -> None:
    """Check that sending the seeded rows builds valid model inputs."""
    state, harness = make_harness()
    harness.sendInputs()
    assert harness.property("tick") == 1
    assert snap(state)["current_block"] == "GREEN I"


def test_send_boards_passengers_once() -> None:
    """Check that a sent boarding count updates the passenger count once."""
    state, harness = make_harness()
    harness.setInput("passengers_boarded", 30)
    harness.sendInputs()
    assert snap(state)["passengers"] == 30
    harness.advanceTick()
    harness.advanceTick()
    assert snap(state)["passengers"] == 30
    harness.sendInputs()
    assert snap(state)["passengers"] == 60
    outputs = {row["name"]: row["value"] for row in harness.property("outputs")}
    assert outputs["passengers"] == 60


def test_boarding_raises_mass() -> None:
    """Check that boarding passengers raises the displayed mass."""
    cfg = TrainConfig()
    state, harness = make_harness()
    harness.setInput("passengers_boarded", 10)
    harness.sendInputs()
    expected = cfg.m_empty_kg + (cfg.n_crew + 10) * cfg.passenger_mass_kg
    assert snap(state)["loaded_mass"] == pytest.approx(expected)


def test_power_command_moves_the_train() -> None:
    """Check that the model, not a placeholder, produces the speed."""
    state, harness = make_harness()
    harness.setInput("power_command", 100_000.0)
    harness.sendInputs()
    for _ in range(20):
        harness.advanceTick()
    assert snap(state)["actual_speed"] > 0.0
    assert snap(state)["position_offset"] > 0.0


def test_brake_state_comes_from_the_model() -> None:
    """Check Brake State in the snapshot is the model's engaged state."""
    state, harness = make_harness()
    harness.setInput("service_brake_command", True)
    harness.sendInputs()
    assert snap(state)["service_brake"] is True
    state.setFailure("brake_failure", True)
    harness.advanceTick()
    assert snap(state)["service_brake"] is False
    assert snap(state)["emergency_brake"] is False


def test_passenger_pull_reported_next_tick() -> None:
    """Check a passenger pull latches and engages the emergency brake."""
    state, harness = make_harness()
    harness.sendInputs()
    state.applyEmergencyBrake()
    assert snap(state)["passenger_ebrake_pulled"] is True
    harness.advanceTick()
    assert snap(state)["emergency_brake"] is True
    state.releaseEmergencyBrake()
    assert snap(state)["passenger_ebrake_pulled"] is True


def test_reset_restores_a_fresh_model() -> None:
    """Check Reset module clears passengers, failures and the tick count."""
    state, harness = make_harness()
    harness.sendInputs()
    state.setFailure("engine_failure", True)
    harness.resetModule()
    assert harness.property("tick") == 0
    assert snap(state)["passengers"] == 0
    assert state.property("activeFailureCount") == 0


def test_invalid_platform_side_is_rejected() -> None:
    """Check a beacon platform side other than L or R raises."""
    _, harness = make_harness()
    harness.setInput("beacon_platform_side", "X")
    with pytest.raises(ValueError, match="platform_side"):
        harness.sendInputs()
