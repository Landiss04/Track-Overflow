"""Both views observe one model; staged test inputs are explicitly separate."""

from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys

import pytest
from PySide6.QtCore import QCoreApplication

from train_model.harness import TestHarnessState as Harness
from train_model.interface import Beacon
from train_model.state import TrainModelState
from tests.test_physics import make_inputs


@pytest.fixture
def pair():
    """Keep a Qt application alive for the harness timer."""
    app = QCoreApplication.instance() or QCoreApplication([])
    state = TrainModelState()
    yield state, Harness(state)
    assert app is not None


def outputs(harness):
    """Index the visible output rows by signal name."""
    return {row["name"]: row["value"] for row in harness.outputs}


def test_passenger_pull_updates_both_views_without_a_tick(pair):
    state, harness = pair
    before = state.snapshot
    state.applyEmergencyBrake()
    assert state.snapshot["emergency_brake"]
    assert harness.inputValues["emergency_brake_command"]
    assert outputs(harness)["emergency_brake_state"]
    assert harness.tick == 0
    assert state.snapshot["position_offset"] == before["position_offset"]
    assert state.snapshot["clock"] == before["clock"]
    state.releaseEmergencyBrake()
    assert harness.inputValues["emergency_brake_command"]


LIVE_VALUES = {
    "power_command": 125000.0,
    "service_brake_command": True, "emergency_brake_command": False,
    "interior_light_command": True, "exterior_light_command": True,
    "left_door_command": True, "right_door_command": True,
    "commanded_speed": 12.5, "authority_block": "B9",
    "beacon_station": "Station", "beacon_platform_side": "R",
    "beacon_underground": True, "block": "B2", "grade": 2.0,
    "elevation": 17.0, "speed_limit": 18.0, "polarity": True,
    "passengers_boarded": 0, "temperature_setpoint": 22.5,
    "announcement": "Arriving",
}


@pytest.mark.parametrize("name", list(LIVE_VALUES))
def test_every_input_refreshes_from_external_model_step(pair, name):
    state, harness = pair
    command = dict(LIVE_VALUES, passengers_boarded=7)
    state.step(0.1, Harness._build_inputs(command))
    assert harness.inputValues[name] == LIVE_VALUES[name]
    assert not harness.pendingInputs
    assert state.snapshot["grade"] == 2.0
    assert state.snapshot["elevation"] == 17.0
    assert state.snapshot["passengers"] == 7


@pytest.mark.parametrize("failure", [
    "engine_failure", "signal_pickup_failure", "brake_failure",
])
def test_failure_state_and_affected_values_change_while_paused(pair, failure):
    state, harness = pair
    state.step(0.1, Harness._build_inputs(LIVE_VALUES))
    state.setFailure(failure, True)
    assert outputs(harness)[failure]
    assert state.activeFailureCount == 1
    assert next(r for r in state.failures if r["name"] == failure)["active"]
    fields = {
        "engine_failure": {"power_command": 0},
        "signal_pickup_failure": {"commanded_speed": 0, "authority_block": ""},
        "brake_failure": {"service_brake_command": False},
    }[failure]
    for name, value in fields.items():
        assert harness.inputValues[name] == value
    # Sending an unrelated field must not feed failed readbacks into the
    # stored producer commands. Clearing the fault restores them.
    harness.setInput("announcement", "Updated")
    harness.sendInputs()
    state.setFailure(failure, False)
    for name in fields:
        assert harness.inputValues[name] == LIVE_VALUES[name]


def test_pending_edits_survive_ticks_and_are_not_automatically_sent(pair):
    state, harness = pair
    harness.sendInputs()
    harness.setInput("power_command", 12345)
    harness.setInput("temperature_setpoint", 24.5)
    harness.advanceTick()
    state.applyEmergencyBrake()
    assert harness.inputValues["power_command"] == 12345
    assert harness.inputValues["temperature_setpoint"] == 24.5
    assert harness.inputValues["emergency_brake_command"]
    assert set(harness.pendingInputs) == {
        "power_command", "temperature_setpoint"
    }
    assert state.command_values()["power_command"] == 0
    harness.sendInputs()
    assert not harness.pendingInputs
    assert state.command_values()["power_command"] == 12345


def test_reset_clears_drafts_faults_beacons_and_terrain(pair):
    state, harness = pair
    initial = dict(harness.inputValues)
    state.step(1.0, Harness._build_inputs(LIVE_VALUES))
    state.applyEmergencyBrake()
    state.setFailure("engine_failure", True)
    harness.setInput("grade", 3)
    harness.resetModule()
    assert harness.inputValues == initial
    assert not harness.pendingInputs
    assert state.activeFailureCount == 0
    assert state.snapshot["grade"] == state.snapshot["elevation"] == 0
    assert state.snapshot["next_station"] == "—"
    assert state.snapshot["clock"] == harness.elapsed == "00:00:00"


def test_beacon_disappearance_and_clock_refresh(pair):
    state, harness = pair
    inp = make_inputs()
    inp = replace(inp, track=replace(
        inp.track, beacon=Beacon("Station", "L", True)
    ))
    state.step(0.1, inp)
    assert outputs(harness)["beacon_station"] == "Station"
    for _ in range(9):
        state.step(0.1, make_inputs())
    assert state.snapshot["next_station"] == "—"
    assert outputs(harness)["beacon_station"] == ""
    assert not outputs(harness)["beacon_underground"]
    assert state.snapshot["clock"] == harness.elapsed == "00:00:01"


def test_qml_live_bindings_and_edit_focus():
    """Exercise actual Qt Quick bindings in a separate GUI application."""
    script = Path(__file__).with_name("qml_sync_check.py")
    result = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True,
        timeout=20, env={
            **os.environ, "QT_QPA_PLATFORM": "offscreen",
            "QT_QUICK_BACKEND": "software", "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
