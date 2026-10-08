"""Boundary types survive the JSON link unchanged."""

from __future__ import annotations

import json

from test_link.codec import (
    Json,
    decode_block_edit,
    decode_inputs,
    decode_outputs,
    encode_block_edit,
    encode_inputs,
    encode_outputs,
)
from track_model.interface import (
    BlockEdit,
    SignalAspect,
    SwitchPosition,
    TrackControllerCommands,
    TrackFailure,
)
from tests.helpers import DT_S, make_inputs, make_model, report


def through_json(data: Json) -> Json:
    """Return ``data`` after a real JSON text round trip."""
    result: Json = json.loads(json.dumps(data))
    return result


def test_inputs_round_trip() -> None:
    """Check every input field survives encoding."""
    inputs = make_inputs(
        {"T1": report("GREEN A-1", 3.5, speed_mps=-0.25, capacity=9)},
        TrackControllerCommands(
            commanded_speed_mps={"GREEN A-1": 8},
            commanded_authority={"GREEN A-1": "GREEN C-9"},
            switch_commands={"BLUE A-5": SwitchPosition.REVERSE},
            crossing_commands={"BLUE A-3": True},
            signal_commands={"BLUE A-4": SignalAspect.YELLOW},
            heater_commands={"GREEN A": False},
        ),
        ambient_temp_c=-7.5,
    )
    assert decode_inputs(through_json(encode_inputs(inputs))) == inputs


def test_outputs_round_trip() -> None:
    """Check real outputs, with a beacon and a failure, survive."""
    model = make_model(ticket_probability=1.0)
    model.set_block_failure("GREEN A-1", TrackFailure.TRACK_CIRCUIT)
    outputs = model.step(
        DT_S, make_inputs({"T1": report("GREEN A-3", 1.0)}))
    assert outputs.train_feeds["T1"].beacon is not None
    assert decode_outputs(through_json(encode_outputs(outputs))) == outputs


def test_block_edit_round_trip() -> None:
    """Check partial edits keep their None fields."""
    edit = BlockEdit(length_m=40.0, speed_limit_mps=None)
    assert decode_block_edit(through_json(encode_block_edit(edit))) == edit
