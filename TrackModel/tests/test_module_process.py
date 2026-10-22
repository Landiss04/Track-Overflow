"""The Track Model process the harness drives, without the harness.

The process's step is called directly, as the harness's ``STEP`` would
call it: the JSON form of the inputs and outputs, how a bad input
refuses the tick and changes nothing, the clock's time reaching the
window, and the lines the system loads.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from track_model.interface import (
    Beacon,
    CtcOutputs,
    InvalidInputError,
    SignalAspect,
    SwitchPosition,
    TrackConfig,
    TrackControllerOutputs,
    TrackInfo,
    TrackModelOutputs,
    TrackSignal,
    TrainFeed,
    TrainReport,
)
from track_model.model import TrackModel
from track_model.module_process import TrackModelProcess, layout_paths
from track_model.state import TrackModelState
from track_model.wire import decode_inputs, encode_outputs
from tests.helpers import DT_S, make_model
from tests.qt_helpers import dispose, qt_app, wait_for
from utils.module_link import TickRejectedError

FIVE_AM_S = 18_000.0


@pytest.fixture
def process() -> Iterator[tuple[TrackModelProcess, TrackModel]]:
    """A process around a fresh model, never connected."""
    qt_app()
    model = make_model()
    state = TrackModelState(model)
    yield TrackModelProcess(model, state, "unused", parent=state), model
    dispose(state)


def report(block_id: str = "GREEN K-63", **changes: Any) -> dict[str, Any]:
    """One train's report as the harness sends it."""
    return {
        "block_id": block_id,
        "offset_m": 0.0,
        "actual_speed_mps": 0.0,
        "block_changed": False,
        "passenger_capacity": 222,
        "doors_open": False,
        **changes,
    }


def wire_inputs(**changes: Any) -> dict[str, Any]:
    """The Track Model's inputs as the harness sends them."""
    inputs: dict[str, Any] = {
        "controller": {
            "commanded_speed_mps": {"GREEN K-63": 12.5},
            "commanded_authority": {"GREEN K-63": 2},
            "switch_commands": {"GREEN K-63": "REVERSE"},
            "crossing_commands": {},
            "signal_commands": {"GREEN K-64": "GREEN"},
            "heater_commands": {"GREEN K": True},
        },
        "trains": {"G1": report()},
    }
    inputs.update(changes)
    return inputs


def test_inputs_decode_from_json() -> None:
    """Check each field and enumerated value arrives as itself."""
    inputs = decode_inputs(wire_inputs(), FIVE_AM_S)
    cmd = inputs.controller
    assert cmd.commanded_speed_mps == {"GREEN K-63": 12.5}
    assert cmd.commanded_authority == {"GREEN K-63": 2}
    assert cmd.switch_commands == {"GREEN K-63": SwitchPosition.REVERSE}
    assert cmd.signal_commands == {"GREEN K-64": SignalAspect.GREEN}
    assert cmd.heater_commands == {"GREEN K": True}
    assert inputs.trains == {"G1": TrainReport(**report())}
    assert inputs.ambient_temp_c is None
    assert inputs.sim_time_s == FIVE_AM_S


def test_command_maps_and_ambient_may_be_left_out() -> None:
    """Check a step with only trains commands nothing."""
    inputs = decode_inputs({"trains": {}, "ambient_temp_c": 15.0})
    assert inputs.controller.commanded_speed_mps == {}
    assert inputs.controller.switch_commands == {}
    assert inputs.ambient_temp_c == 15.0


Change = Callable[[dict[str, Any]], object]


@pytest.mark.parametrize(("change", "message"), [
    (lambda data: data.pop("trains"), "trains"),
    (lambda data: data.update(clock=1), "unknown"),
    (lambda data: data["controller"].update(speeds={}), "unknown"),
    (lambda data: data["controller"].update(commanded_speed_mps=[]),
     "object"),
    (lambda data: data["controller"]["commanded_speed_mps"].update(
        {"GREEN K-63": "12"}), "number"),
    (lambda data: data["controller"]["commanded_speed_mps"].update(
        {"GREEN K-63": True}), "number"),
    (lambda data: data["controller"]["switch_commands"].update(
        {"GREEN K-63": "normal"}), "NORMAL"),
    (lambda data: data["controller"]["signal_commands"].update(
        {"GREEN K-64": "SUPER GREEN"}), "SUPER_GREEN"),
    (lambda data: data["controller"]["heater_commands"].update(
        {"GREEN K": 1}), "bool"),
    (lambda data: data["trains"]["G1"].pop("doors_open"), "missing"),
    (lambda data: data["trains"]["G1"].update(position=0), "unknown"),
    (lambda data: data["trains"]["G1"].update(passenger_capacity=True),
     "passenger_capacity"),
    (lambda data: data["trains"]["G1"].update(offset_m="0"), "offset_m"),
    (lambda data: data["trains"].update(G2=[]), "object"),
    (lambda data: data.update(ambient_temp_c="cold"), "ambient"),
])
def test_malformed_inputs_are_refused(change: Change, message: str) -> None:
    """Check a wrong shape or type is refused, naming what is wrong."""
    data = wire_inputs()
    change(data)
    with pytest.raises(InvalidInputError, match=message):
        decode_inputs(data)


def _fields(cls: type[Any]) -> set[str]:
    # A boundary type's field names.
    return {field.name for field in dataclasses.fields(cls)}


def test_outputs_encode_every_field_as_plain_json() -> None:
    """Check the JSON form has every field, with enums by name."""
    model = make_model()
    model.step(DT_S, decode_inputs(wire_inputs()))
    outputs = model.step(DT_S, decode_inputs(wire_inputs()))
    data = json.loads(json.dumps(encode_outputs(outputs)))
    assert set(data) == _fields(TrackModelOutputs)
    assert set(data["controller"]) == _fields(TrackControllerOutputs)
    assert set(data["ctc"]) == _fields(CtcOutputs)
    feed = data["train_feeds"]["G1"]
    assert set(feed) == _fields(TrainFeed)
    assert set(feed["track_info"]) == _fields(TrackInfo)
    assert set(feed["track_signal"]) == _fields(TrackSignal)
    assert feed["track_signal"] == {
        "commanded_speed_mps": 12.5, "authority_blocks": 2,
    }
    assert data["controller"]["switch_states"]["GREEN K-63"] == "REVERSE"
    assert data["controller"]["signal_states"]["GREEN K-64"] == "GREEN"
    assert data["controller"]["failure_status"]["GREEN K-63"] == "NONE"


def test_a_beacon_encodes_as_an_object() -> None:
    """Check a beacon's fields, next to GLENBURY."""
    outputs = make_model().step(DT_S, decode_inputs(
        wire_inputs(trains={"G1": report("GREEN K-64")})))
    beacon = encode_outputs(outputs)["train_feeds"]["G1"]["beacon"]
    assert set(beacon) == _fields(Beacon)
    assert beacon == {
        "station_name": "GLENBURY", "platform_side": "R",
        "underground": False,
    }


def test_process_steps_the_model(
    process: tuple[TrackModelProcess, TrackModel],
) -> None:
    """Check a step places the train and feeds it its block."""
    step, model = process
    reply = step.step(1, DT_S, FIVE_AM_S, wire_inputs())
    feed = reply["train_feeds"]["G1"]
    assert feed["track_info"]["block_id"] == "GREEN K-63"
    assert feed["track_signal"]["commanded_speed_mps"] == 12.5
    assert reply["controller"]["block_occupancy"]["GREEN K-63"]
    assert [train.train_id for train in model.snapshot().trains] == ["G1"]


def test_process_gives_the_window_the_clocks_time(
    process: tuple[TrackModelProcess, TrackModel],
) -> None:
    """Check the step's simulation time is the window's time of day."""
    step, model = process
    step.step(1, DT_S, FIVE_AM_S + 61.0, wire_inputs())
    assert model.snapshot().sim_time_s == FIVE_AM_S + 61.0
    state = step.parent()
    assert isinstance(state, TrackModelState)
    assert state.property("running")
    # The window redraws after the reply, within a tenth of a second.
    assert wait_for(lambda: state.property("elapsed") == "05:01:01",
                    timeout_ms=1000)


def test_a_bad_input_refuses_the_tick_and_changes_nothing(
    process: tuple[TrackModelProcess, TrackModel],
) -> None:
    """Check a refused tick leaves the model as it was."""
    step, model = process
    step.step(1, DT_S, FIVE_AM_S, wire_inputs())
    before = model.snapshot()
    with pytest.raises(TickRejectedError, match="NOWHERE"):
        step.step(2, DT_S, FIVE_AM_S + DT_S, wire_inputs(
            trains={"G1": report("NOWHERE 1")}))
    assert model.snapshot() == before
    with pytest.raises(TickRejectedError, match="unknown"):
        step.step(2, DT_S, FIVE_AM_S + DT_S, {"trains": {}, "x": 1})
    assert model.snapshot() == before


def test_the_system_loads_green_and_red_only() -> None:
    """Check the Blue Line is left out (D023)."""
    model = TrackModel(TrackConfig(layout_paths()))
    assert {block.line for block in model.snapshot().blocks} == {
        "GREEN", "RED",
    }
