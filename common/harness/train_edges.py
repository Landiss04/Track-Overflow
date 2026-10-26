"""Edges between the Train Model and the Train Controller (D005).

Pure functions, one per edge, from one module's outputs for a train to
the other module's inputs for it, both in their JSON form. Each module
names its own fields: the Train Model as in ``train_model.interface``,
the Train Controller as its ``read_inputs`` keys and
``TrainModelCommands`` fields. Units do not change across either edge:
both sides are in SI (``conventions/units.md``).

Train Controller -> Train Model, ``train_controller_to_train_model``::

    power_w                 -> power_cmd_w
    service_brake           -> service_brake
    emergency_brake         -> emergency_brake
    door_command [l, r]     -> door_left_open, door_right_open
    light_command [i, e]    -> interior_lights, exterior_lights
    temperature_setpoint_c  -> temp_setpoint_c
    announcement            -> announcement
    (not sent)              -> passenger_brake_release, always false

The Train Controller does not send a passenger brake release, by its
owner's decision (``Train-Ctrl_HW/HARNESS_INTEGRATION.md``, Outputs;
``OPEN_ISSUES.md`` #25): clearing the Train Model's passenger latch is
left to the Train Model. Its ``power_verified`` (M21) is its own and
does not cross this edge.

Train Model -> Train Controller, ``train_model_to_train_controller``,
from the Train Model's ``controller`` outputs::

    actual_speed_mps            -> actual_speed
    commanded_speed_mps         -> commanded_speed
    authority_blocks            -> authority_blocks
    emergency_brake_active      -> emergency_brake_state
    service_brake_active        -> service_brake_state
    door_left_open,
    door_right_open             -> door_state [left, right]
    interior_lights_on,
    exterior_lights_on          -> light_state [interior, exterior]
    cabin_temp_c                -> cabin_temperature
    beacon, when over one       -> beacon_station, beacon_side,
                                   beacon_underground

The Train Model also passes the block's speed limit through; the
Train Controller takes commanded speed as its limit and has no input
for it (``Train-Ctrl_HW/REQUIREMENTS.md`` M1), so this edge drops it.

The light ahead goes from the Track Model to the Train Controller
directly (``signals/signal-aspect-ahead``), through
``aspect_to_train_controller``.
"""

from __future__ import annotations

__all__ = [
    "INERT_COMMANDS",
    "aspect_to_train_controller",
    "train_controller_to_train_model",
    "train_model_to_train_controller",
]

from collections.abc import Mapping
from typing import Any

#: What a train's Train Model gets before its Train Controller has
#: sent anything: no power, the service brake on, doors shut, lights
#: on, and a comfortable 21 °C asked of the cabin. A new
#: train waits in its yard exit block; the Train Controller joins one
#: tick after the Train Model, once the Train Model has reported the
#: train, and its first commands arrive the tick after that.
INERT_COMMANDS: Mapping[str, Any] = {
    "power_cmd_w": 0.0,
    "service_brake": True,
    "emergency_brake": False,
    "interior_lights": True,
    "exterior_lights": True,
    "door_left_open": False,
    "door_right_open": False,
    "temp_setpoint_c": 21.0,
    "announcement": "",
    "passenger_brake_release": False,
}

# The light ahead as the Track Model spells it (signal-aspect-ahead,
# all caps), and as the Train Controller reads it. The Train
# Controller still spells the fourth aspect with a space.
_ASPECTS = {
    "RED": "RED",
    "YELLOW": "YELLOW",
    "GREEN": "GREEN",
    "SUPER_GREEN": "SUPER GREEN",
}


def train_controller_to_train_model(
    commands: Mapping[str, Any],
) -> dict[str, Any]:
    """Map a train's Train Controller commands to its Train Model.

    Returns:
        The Train Model's ``controller`` input for the train.

    Raises:
        KeyError: If a command is missing.
    """
    left, right = commands["door_command"]
    interior, exterior = commands["light_command"]
    return {
        "power_cmd_w": commands["power_w"],
        "service_brake": commands["service_brake"],
        "emergency_brake": commands["emergency_brake"],
        "interior_lights": interior,
        "exterior_lights": exterior,
        "door_left_open": left,
        "door_right_open": right,
        "temp_setpoint_c": commands["temperature_setpoint_c"],
        "announcement": commands["announcement"],
        "passenger_brake_release": False,
    }


def train_model_to_train_controller(
    outputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Map a train's Train Model outputs to its Train Controller.

    Takes the Train Model's ``controller`` outputs. A beacon is passed
    on only while the Train Model reports one; the Train Controller
    keeps the last one it heard.

    Raises:
        KeyError: If an output is missing.
    """
    inputs = {
        "actual_speed": outputs["actual_speed_mps"],
        "commanded_speed": outputs["commanded_speed_mps"],
        "authority_blocks": outputs["authority_blocks"],
        "emergency_brake_state": outputs["emergency_brake_active"],
        "service_brake_state": outputs["service_brake_active"],
        "door_state": [
            outputs["door_left_open"],
            outputs["door_right_open"],
        ],
        "light_state": [
            outputs["interior_lights_on"],
            outputs["exterior_lights_on"],
        ],
        "cabin_temperature": outputs["cabin_temp_c"],
    }
    beacon = outputs["beacon"]
    if beacon is not None:
        inputs["beacon_station"] = beacon["station_name"]
        inputs["beacon_side"] = beacon["platform_side"]
        inputs["beacon_underground"] = beacon["underground"]
    return inputs


def aspect_to_train_controller(aspect: str) -> str:
    """Map the light ahead to the Train Controller's spelling.

    Raises:
        KeyError: If ``aspect`` is not one of the four aspects.
    """
    return _ASPECTS[aspect]
