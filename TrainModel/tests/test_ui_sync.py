"""Both views observe one model; staged test inputs are explicitly separate."""

import os
from pathlib import Path
import subprocess
import sys

import pytest
from PySide6.QtCore import QCoreApplication

from train_model.harness import TestHarnessState as Harness
from train_model.link import LocalLink
from train_model.state import TrainModelState


@pytest.fixture
def pair():
    """Keep a Qt application alive for the harness timer."""
    app = QCoreApplication.instance() or QCoreApplication([])
    state = TrainModelState()
    yield state, Harness(LocalLink(state))
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
    "commanded_speed": 12.5, "authority": 9,
    "beacon_station": "Station", "beacon_platform_side": "R",
    "beacon_underground": True, "block": "B2", "grade": 2.0,
    "elevation": 17.0, "speed_limit": 18.0, "polarity": True,
    "station": "Station", "passengers_boarded": 0,
    "temperature_setpoint": 22.5,
    "announcement": "Arriving",
}


def send(harness, values):
    """Stage every value and send them as one tick."""
    for name, value in values.items():
        harness.setInput(name, value)
    assert harness.sendInputs()


@pytest.mark.parametrize("name", list(LIVE_VALUES))
def test_every_input_shows_the_accepted_value_after_a_send(pair, name):
    state, harness = pair
    send(harness, dict(LIVE_VALUES, passengers_boarded=7))
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
    send(harness, LIVE_VALUES)
    state.setFailure(failure, True)
    assert failure not in outputs(harness)  # not sent to the controller
    assert state.activeFailureCount == 1
    assert next(r for r in state.failures if r["name"] == failure)["active"]
    # There is no power output, so engine failure changes no control.
    fields = {
        "engine_failure": {},
        "signal_pickup_failure": {"commanded_speed": 0, "authority": 0},
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
    send(harness, {
        "beacon_station": "Station", "beacon_platform_side": "L",
        "beacon_underground": True,
    })
    # The beacon is not in the test UI's output table; the Train Model
    # window shows it, and the module still outputs it.
    assert "beacon_station" not in outputs(harness)
    assert state.snapshot["next_station"] == "Station"
    assert state.outputs().controller.beacon is not None
    send(harness, {"beacon_station": "", "beacon_underground": False})
    for _ in range(8):
        harness.advanceTick()
    assert state.snapshot["next_station"] == "—"
    assert state.outputs().controller.beacon is None
    assert state.snapshot["clock"] == harness.elapsed == "00:00:01"


def run_gui_check(name, timeout):
    """Run a GUI check script in its own offscreen application."""
    script = Path(__file__).with_name(name)
    result = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True,
        timeout=timeout, env={
            **os.environ, "QT_QPA_PLATFORM": "offscreen",
            "QT_QUICK_BACKEND": "software", "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # A QML binding error is a failure even when the checks pass.
    assert ".qml:" not in result.stderr, result.stderr


def test_qml_live_bindings_and_edit_focus():
    """Exercise actual Qt Quick bindings in a separate GUI application."""
    run_gui_check("qml_sync_check.py", timeout=20)


def test_input_list_scrolls_in_place_and_outputs_are_trimmed():
    """The looping input list and the trimmed output table, in Qt Quick."""
    run_gui_check("input_list_check.py", timeout=30)


def test_readouts_never_show_a_negative_zero():
    """A value that rounds to zero reads 0.00, never -0.00."""
    run_gui_check("readout_sign_check.py", timeout=20)


def test_emergency_brake_button_with_the_real_test_ui():
    """The overview button, driven from the test UI in its own process."""
    run_gui_check("ebrake_button_check.py", timeout=120)
