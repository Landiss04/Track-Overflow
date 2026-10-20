"""The Train Model process the harness drives, without the harness.

The process's step is called directly, as the harness's ``STEP`` would
call it: which trains it adds and removes, how each steps, and how it
rejects one train's inputs without holding back the others. The JSON
form of the inputs and outputs is checked here too, and the
passenger-brake-release command.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
from PySide6.QtCore import QCoreApplication

from train_model.fleet import TrainModelFleet
from train_model.model import InvalidInputError
from train_model.module_process import TrainModelProcess
from train_model.wire import decode_inputs, encode_outputs
from tests.test_contract import DT_S, make_inputs
from utils.module_link import TickRejectedError

SIM_TIME_S = 18_000.1


@pytest.fixture(autouse=True)
def app() -> QCoreApplication:
    """A Qt application, for the process's link to live in."""
    return QCoreApplication.instance() or QCoreApplication([])


def wire_inputs(line: str = "Green", **controller: Any) -> dict[str, Any]:
    """One train's inputs as the harness sends them."""
    inputs = dataclasses.asdict(make_inputs())
    inputs["controller"].update(controller)
    return {"line": line, **inputs}


def make_process() -> tuple[TrainModelProcess, TrainModelFleet]:
    """A process around a fresh fleet, never connected."""
    fleet = TrainModelFleet()
    return TrainModelProcess(fleet, "unused", parent=fleet), fleet


def test_inputs_round_trip_through_json() -> None:
    """Check the JSON form decodes to the very inputs it came from."""
    inputs = make_inputs()
    assert decode_inputs(dataclasses.asdict(inputs)) == inputs


def test_outputs_encode_as_plain_json() -> None:
    """Check every output becomes plain values, nested by type."""
    fleet = TrainModelFleet()
    outputs = encode_outputs(fleet.add("G1").step(DT_S, make_inputs()))
    assert set(outputs) == {"controller", "track"}
    assert outputs["track"]["block_id"] == "A1"
    assert isinstance(outputs["controller"]["actual_speed_mps"], float)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda data: data.pop("controller"), "controller"),
        (lambda data: data["controller"].pop("power_cmd_w"), "missing"),
        (lambda data: data["controller"].update(power_kw=1.0), "unknown"),
        (lambda data: data["track"].pop("passengers_boarded"), "boarded"),
        (lambda data: data["track"].update(track_info=[]), "object"),
    ],
)
def test_malformed_inputs_are_refused(change: Any, message: str) -> None:
    """Check a wrong shape is refused, naming what is wrong."""
    data = dataclasses.asdict(make_inputs())
    change(data)
    with pytest.raises(InvalidInputError, match=message):
        decode_inputs(data)


def test_release_command_is_optional_in_json() -> None:
    """Check inputs with no release field do not release."""
    data = dataclasses.asdict(make_inputs())
    del data["controller"]["passenger_brake_release"]
    assert not decode_inputs(data).controller.passenger_brake_release


def test_roster_follows_the_inputs() -> None:
    """Check trains join when first named and leave when no longer."""
    process, fleet = make_process()
    process.step(1, DT_S, SIM_TIME_S, {"trains": {
        "G1": wire_inputs("Green"), "R1": wire_inputs("Red"),
    }})
    assert fleet.ids() == ["G1", "R1"]
    assert fleet.get("R1").line == "Red"
    reply = process.step(2, DT_S, SIM_TIME_S, {"trains": {
        "R1": wire_inputs("Red"),
    }})
    assert fleet.ids() == ["R1"]
    assert list(reply["trains"]) == ["R1"]


def test_each_train_steps_on_its_own_inputs() -> None:
    """Check every train in service steps and reports its outputs."""
    process, fleet = make_process()
    reply = process.step(1, DT_S, SIM_TIME_S, {"trains": {
        "G1": wire_inputs(), "G2": wire_inputs(),
    }})
    assert set(reply["trains"]) == {"G1", "G2"}
    assert "rejected" not in reply
    for train_id in ("G1", "G2"):
        speed = reply["trains"][train_id]["controller"]["actual_speed_mps"]
        state = fleet.get(train_id)
        assert speed > 0.0
        assert speed == state.outputs().controller.actual_speed_mps


def test_one_trains_bad_inputs_hold_back_only_that_train() -> None:
    """Check a rejected train is named and the others step."""
    process, fleet = make_process()
    process.step(1, DT_S, SIM_TIME_S, {"trains": {
        "G1": wire_inputs(), "G2": wire_inputs(),
    }})
    before = encode_outputs(fleet.get("G2").outputs())
    reply = process.step(2, DT_S, SIM_TIME_S, {"trains": {
        "G1": wire_inputs(), "G2": wire_inputs(power_cmd_w=-1.0),
    }})
    assert set(reply["rejected"]) == {"G2"}
    assert "power_cmd_w" in reply["rejected"]["G2"]
    assert reply["trains"]["G2"] == before
    assert reply["trains"]["G1"]["controller"]["actual_speed_mps"] > (
        reply["trains"]["G2"]["controller"]["actual_speed_mps"]
    )


def test_inputs_without_trains_reject_the_tick() -> None:
    """Check a STEP that names no roster is refused whole."""
    process, _ = make_process()
    with pytest.raises(TickRejectedError):
        process.step(1, DT_S, SIM_TIME_S, {})


def test_release_command_clears_a_passenger_pull() -> None:
    """Check the release clears a pull, not the controller's brake."""
    process, fleet = make_process()
    process.step(1, DT_S, SIM_TIME_S, {"trains": {"G1": wire_inputs()}})
    fleet.get("G1").applyEmergencyBrake()
    reply = process.step(2, DT_S, SIM_TIME_S, {"trains": {
        "G1": wire_inputs(),
    }})
    assert reply["trains"]["G1"]["controller"]["emergency_brake_active"]
    reply = process.step(3, DT_S, SIM_TIME_S, {"trains": {
        "G1": wire_inputs(passenger_brake_release=True),
    }})
    assert not reply["trains"]["G1"]["controller"]["emergency_brake_active"]
    reply = process.step(4, DT_S, SIM_TIME_S, {"trains": {
        "G1": wire_inputs(emergency_brake=True,
                          passenger_brake_release=True),
    }})
    assert reply["trains"]["G1"]["controller"]["emergency_brake_active"]


def test_overlength_beacon_rejects_only_its_train_before_mutation() -> None:
    process, fleet = make_process()
    process.step(1, DT_S, SIM_TIME_S, {"trains": {
        "G1": wire_inputs(), "G2": wire_inputs(),
    }})
    state = fleet.get("G1")
    state.applyEmergencyBrake()
    before = state.outputs()
    elapsed = state.elapsed_s
    invalid = wire_inputs(passenger_brake_release=True, door_left_open=True)
    invalid["track"]["beacon"] = {
        "station_name": "S" * 115, "platform_side": "L",
        "underground": False,
    }
    invalid["track"]["passengers_boarded"] = 100
    reply = process.step(2, DT_S, SIM_TIME_S + DT_S, {"trains": {
        "G1": invalid, "G2": wire_inputs(),
    }})
    assert set(reply["rejected"]) == {"G1"}
    assert "129" in reply["rejected"]["G1"]
    assert state.outputs() == before
    assert state.elapsed_s == elapsed
    assert state.snapshot["passenger_ebrake_pulled"]
    assert not state.snapshot["left_door"]
    assert state.snapshot["passengers"] == 0
    assert fleet.get("G2").elapsed_s == 2 * DT_S
