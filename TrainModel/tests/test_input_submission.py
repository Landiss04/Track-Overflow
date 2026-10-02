"""Regression coverage for rejected submissions and display-unit boundaries."""

import math

import pytest
from PySide6.QtCore import QCoreApplication

from train_model.harness import TestHarnessState as Harness
from train_model.link import LocalLink
from train_model.state import TrainModelState
from tests.test_physics import make_inputs


@pytest.fixture
def pair():
    app = QCoreApplication.instance() or QCoreApplication([])
    state = TrainModelState()
    yield state, Harness(LocalLink(state))
    assert app is not None


@pytest.mark.parametrize("failure", [False, True])
@pytest.mark.parametrize("bad_field,bad_value", [
    ("power_command", -1),
    ("power_command", math.inf),
    ("power_command", math.nan),
    ("grade", math.inf),
    ("elevation", math.nan),
    ("speed_limit", math.inf),
    ("commanded_speed", math.nan),
    ("temperature_setpoint", math.inf),
    ("beacon_platform_side", "X"),
])
def test_rejected_send_preserves_state_and_can_retry(pair, failure,
                                                     bad_field, bad_value):
    state, harness = pair
    harness.setInput("station", "Station")
    harness.setInput("left_door_command", True)
    harness.setInput("passengers_boarded", 40)
    assert harness.sendInputs()
    harness.setInput("left_door_command", False)
    assert harness.sendInputs()
    state.applyEmergencyBrake()
    state.setFailure("brake_failure", failure)
    before = state.snapshot
    previous_tick = harness.tick
    notifications = []
    state.snapshotChanged.connect(lambda: notifications.append(True))
    harness.setInput("emergency_brake_command", False)
    harness.setInput("beacon_station", "Station")
    harness.setInput("left_door_command", True)
    harness.setInput("passengers_boarded", 10)
    harness.setInput(bad_field, bad_value)
    harness.setRunning(True)
    assert not harness.sendInputs()
    assert state.snapshot == before
    assert not notifications
    assert harness.tick == previous_tick
    assert not harness.running
    assert harness.inputError
    assert "emergency_brake_command" in harness.pendingInputs
    harness.setInput(bad_field, "L" if bad_field == "beacon_platform_side" else 0)
    assert harness.sendInputs()
    assert not harness.inputError
    assert not harness.pendingInputs
    assert harness.tick == previous_tick + 1
    assert not state.snapshot["passenger_ebrake_pulled"]
    assert not state.snapshot["emergency_brake"]
    assert state.isFailed("brake_failure") == failure
    # Rejection did not consume the seeded disembark draw or board anyone.
    control = TrainModelState()
    control.step(.1, make_inputs(boarded=40, door_left=True, station="S"))
    control.step(.1, make_inputs(station="S"))
    control.step(.1, make_inputs(door_left=True, boarded=10, station="S"))
    assert state.snapshot["passengers"] == control.snapshot["passengers"]


@pytest.mark.parametrize("dt", [0, -1, math.inf, math.nan])
def test_invalid_time_cannot_clear_test_latch(pair, dt):
    state, harness = pair
    state.applyEmergencyBrake()
    before = state.snapshot
    harness.setInput("emergency_brake_command", False)
    # dt is the shared clock's tick length, which the clock itself
    # keeps positive; force it to reach the module's own check.
    harness._clock._tick_s = dt
    assert not harness.sendInputs()
    assert state.snapshot == before
    assert harness.tick == 0
    assert harness.inputError
    harness._clock._tick_s = .1
    assert harness.sendInputs()
    assert not state.snapshot["passenger_ebrake_pulled"]


def test_initial_advance_rejection_and_reset(pair):
    state, harness = pair
    state.applyEmergencyBrake()
    harness.setInput("emergency_brake_command", False)
    harness.setDisplayInput("power_command", -1)
    harness.advanceTick()
    assert state.snapshot["passenger_ebrake_pulled"]
    assert harness.tick == 0
    assert harness.inputError
    harness.resetModule()
    assert not harness.inputError
    assert not harness.pendingInputs
    assert not state.snapshot["passenger_ebrake_pulled"]


# Literal expectations are independent of the conversion implementation.
DISPLAY_CASES = [
    ("power_command", 100.0, 100000.0, "kW"),
    ("commanded_speed", 22.36936, 10.0, "mph"),
    ("speed_limit", 44.73872, 20.0, "mph"),
    ("elevation", 328.084, 100.0, "ft"),
    ("elevation", -32.8084, -10.0, "ft"),
    ("temperature_setpoint", 77.0, 25.0, "°F"),
    ("temperature_setpoint", -40.0, -40.0, "°F"),
    ("grade", 3.5, 3.5, "deg"),
    ("announcement", "Next station", "Next station", ""),
    ("authority_block", "B3", "B3", ""),
    ("interior_light_command", True, True, ""),
]


@pytest.mark.parametrize("name,display,backend,unit", DISPLAY_CASES)
def test_display_input_round_trip_keeps_backend_metric(pair, name, display,
                                                       backend, unit):
    state, harness = pair
    harness.setDisplayInput(name, display)
    if isinstance(backend, (float, int)):
        assert harness.inputValues[name] == pytest.approx(backend)
    else:
        assert harness.inputValues[name] == backend
    assert harness.displayInputValues[name] == display
    definition = next(r for r in harness.inputDefinitions if r["name"] == name)
    assert definition["unit"] == unit
    assert harness.sendInputs()
    for _ in range(10):
        harness.advanceTick()
        assert harness.sendInputs()  # unchanged displayed values aren't resent
    actual = state.command_values()[name]
    if isinstance(backend, (float, int)):
        assert actual == pytest.approx(backend, rel=1e-12, abs=1e-12)
    else:
        assert actual == backend
    assert harness.displayInputValues[name] == display


def test_live_inputs_and_outputs_convert_after_a_send(pair):
    state, harness = pair
    for name, value in {
        "power_command": 100000, "commanded_speed": 10.0,
        "authority_block": "A9", "block": "A1", "speed_limit": 19.0,
        "polarity": True, "elevation": 100, "temperature_setpoint": 25,
    }.items():
        harness.setInput(name, value)
    assert harness.sendInputs()
    assert harness.displayInputValues["power_command"] == 100
    assert harness.displayInputValues["commanded_speed"] == 22.36936
    assert harness.displayInputValues["elevation"] == 328.084
    assert harness.displayInputValues["temperature_setpoint"] == 77
    out = {r["name"]: r for r in harness.outputs}
    assert out["commanded_speed"]["value"] == 22.369
    assert out["commanded_speed"]["unit"] == "mph"
    assert out["speed_limit"]["value"] == 42.502
    assert out["cabin_temp"]["value"] == 68.003
    assert out["cabin_temp"]["unit"] == "°F"
    assert out["position_offset"]["value"] == round(
        state.snapshot["position_offset"] * 3.280840, 3
    )
    assert out["position_offset"]["unit"] == "ft"
    assert out["actual_speed"]["value"] == round(
        state.snapshot["actual_speed"] * 2.236936, 3
    )
    # No power output exists, so the control keeps the accepted command
    # while the engine has failed.
    state.setFailure("engine_failure", True)
    assert harness.displayInputValues["power_command"] == 100
    harness.setDisplayInput("power_command", 99)
    assert harness.sendInputs()
    assert harness.displayInputValues["power_command"] == 99
    state.setFailure("engine_failure", False)
    assert harness.displayInputValues["power_command"] == 99
    assert state.command_values()["power_command"] == 99000
    harness.resetModule()
    assert harness.displayInputValues["temperature_setpoint"] == 68
    assert harness.displayInputValues["power_command"] == 0
