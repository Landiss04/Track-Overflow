"""Edges into and out of the Track Controller (D005).

Pure functions on each module's JSON form, as in ``track_edges``. The
Track Controller SW runs the Green Line (R77); the HW variant is to run
the Red through the same functions (Phase 5).

The Track Controller's JSON form is ``track_ctrl.wire``'s: a block is
``{"line", "block_id"}``, a per-block value is a list of ``{"block",
"value"}`` entries, and enumerated values are in lower case
(``"normal"``, ``"super_green"``). The CTC Office's is its boundary
types as ``dataclasses.asdict`` makes them (``ctc.wire``). The Track
Model's is ``track_model.wire``'s, with its own block names
(``track_edges.BlockNames``) and enumerated values in capitals. Between
the Track Controller and the Track Model a switch and its light change
names too (``track_devices``): the Track Controller names both by the
block the switch is listed on, the Track Model the switch by its point
and the light by the block it stands on.

CTC Office -> Track Controller, ``ctc_to_track_controller``, one
line's::

    track_controller.suggestions[]: train_id, line, block_id,
        suggested_speed_mps, authority_blocks
                    -> suggestions[]: block, value {speed_mps,
                       authority_blocks}. The train ID stops here (R48);
                       of two for one block, the lower speed and the
                       lower authority win, each on its own
    track_controller.closed_blocks[]   -> closed_blocks[]
    track_controller.switch_commands[]: line, switch_id, position
                    -> switch_commands[]: block (the switch's ID), value

Track Model -> Track Controller, ``track_model_to_track_controller``,
one line's::

    controller.block_occupancy  -> occupied_blocks: the occupied ones.
                                   The Track Model reads a failed block
                                   as occupied (R33)
    controller.switch_states    -> switch_positions, by switch ID
    controller.crossing_states  -> crossings_active, by crossing block
    controller.signal_states    -> signal_aspects, by switch ID

Track Controller -> Track Model, ``track_controller_to_track_model``::

    track_circuits      -> commanded_speed_mps, a float (R24), and
                           commanded_authority, per block
    switch_commands     -> switch_commands, by point
    crossing_commands   -> crossing_commands
    signal_commands     -> signal_commands, by the light's block

It sends no heater commands: the Track Model switches its heaters
(D026).

Track Controller -> CTC Office, ``track_controller_to_ctc``, the CTC
Office's ``track_controller`` input, from every wayside's report::

    blocks[].occupied         -> occupancy[]: line, block_id, occupied
    blocks[].switch_position  -> switches[]: line, switch_id, position
    blocks[].crossing_active  -> crossings[]: line, crossing_id, state
                                 "active" or "inactive"
    wayside_id, line, ready, reason
                              -> waysides[] (R70)

A failed block reaches the CTC Office as occupied, with nothing else
said of it (R69). The signal aspects and the report's time stop here:
the CTC Office has no field for them.
"""

from __future__ import annotations

__all__ = [
    "ctc_to_track_controller",
    "line_ready",
    "track_controller_to_ctc",
    "track_controller_to_track_model",
    "track_model_to_track_controller",
]

from collections.abc import Iterable, Mapping
from typing import Any

from common.harness.track_devices import TrackDevices
from common.harness.track_edges import BlockNames

# Enumerated values, from the Track Model's spelling to the Track
# Controller's.
_POSITIONS: Mapping[str, str] = {"NORMAL": "normal", "REVERSE": "reverse"}
_ASPECTS: Mapping[str, str] = {
    "RED": "red",
    "YELLOW": "yellow",
    "GREEN": "green",
    "SUPER_GREEN": "super_green",
}
# And back.
_TRACK_MODEL_POSITIONS = {value: key for key, value in _POSITIONS.items()}
_TRACK_MODEL_ASPECTS = {value: key for key, value in _ASPECTS.items()}


def ctc_to_track_controller(
    outputs: Mapping[str, Any], line: str
) -> dict[str, Any]:
    """Map the CTC Office's outputs to a Track Controller's ``ctc``.

    Args:
        outputs: The CTC Office's outputs, with ``track_controller``.
        line: The line the Track Controller runs.

    Raises:
        KeyError: If an output is missing.
    """
    sent = outputs["track_controller"]
    suggestions: dict[str, tuple[Any, Any]] = {}
    for each in sent["suggestions"]:
        if each["line"] != line:
            continue
        wanted = (each["suggested_speed_mps"], each["authority_blocks"])
        held = suggestions.get(each["block_id"])
        # A vital controller never takes the more permissive of two.
        suggestions[each["block_id"]] = wanted if held is None else (
            min(held[0], wanted[0]),
            min(held[1], wanted[1]),
        )
    return {
        "closed_blocks": [
            _block(line, ref["block_id"])
            for ref in sent["closed_blocks"]
            if ref["line"] == line
        ],
        "switch_commands": [
            {"block": _block(line, command["switch_id"]),
             "value": command["position"]}
            for command in sent["switch_commands"]
            if command["line"] == line
        ],
        "suggestions": [
            {"block": _block(line, block_id),
             "value": {"speed_mps": speed, "authority_blocks": authority}}
            for block_id, (speed, authority) in suggestions.items()
        ],
    }


def track_model_to_track_controller(
    outputs: Mapping[str, Any],
    line: str,
    names: BlockNames,
    devices: TrackDevices,
) -> dict[str, Any]:
    """Map the Track Model's outputs to a Track Controller's.

    Args:
        outputs: The Track Model's outputs, with ``controller``.
        line: The line the Track Controller runs.
        names: The Track Model's block names.
        devices: Where each switch and light stands.

    Raises:
        KeyError: If an output is missing, a switch or light is
            unknown, or a value is not one the Track Model sends.
    """
    controller = outputs["controller"]
    occupied = [
        _block(line, number)
        for number, value in _on_line(
            controller["block_occupancy"], line, names
        )
        if value
    ]
    positions = [
        {"block": _block(line, devices.by_point(line, number).switch_id),
         "value": _POSITIONS[value]}
        for number, value in _on_line(
            controller["switch_states"], line, names
        )
    ]
    crossings = [
        {"block": _block(line, number), "value": value}
        for number, value in _on_line(
            controller["crossing_states"], line, names
        )
    ]
    aspects = [
        {"block": _block(line, devices.by_light(line, number).switch_id),
         "value": _ASPECTS[value]}
        for number, value in _on_line(
            controller["signal_states"], line, names
        )
    ]
    return {
        "occupied_blocks": occupied,
        "switch_positions": positions,
        "crossings_active": crossings,
        "signal_aspects": aspects,
    }


def track_controller_to_track_model(
    outputs: Mapping[str, Any], names: BlockNames, devices: TrackDevices
) -> dict[str, Any]:
    """Map a Track Controller's outputs to the Track Model's commands.

    Args:
        outputs: The Track Controller's outputs, with ``track_model``.
        names: The Track Model's block names.
        devices: Where each switch and light stands.

    Raises:
        KeyError: If an output is missing, a block, switch or light is
            unknown, or a value is not one the Track Controller sends.
    """
    commands = outputs["track_model"]
    speeds: dict[str, float] = {}
    authority: dict[str, Any] = {}
    for entry in commands["track_circuits"]:
        name = _name(names, entry["block"])
        speeds[name] = float(entry["value"]["speed_mps"])
        authority[name] = entry["value"]["authority_blocks"]
    switches = {}
    for entry in commands["switch_commands"]:
        line, number = _key(entry["block"])
        point = devices.by_switch(line, number).point
        switches[names.track_model_name(line, point)] = (
            _TRACK_MODEL_POSITIONS[entry["value"]]
        )
    signals = {}
    for entry in commands["signal_commands"]:
        line, number = _key(entry["block"])
        light = devices.by_switch(line, number).light
        signals[names.track_model_name(line, light)] = (
            _TRACK_MODEL_ASPECTS[entry["value"]]
        )
    return {
        "commanded_speed_mps": speeds,
        "commanded_authority": authority,
        "switch_commands": switches,
        "crossing_commands": {
            _name(names, entry["block"]): entry["value"]
            for entry in commands["crossing_commands"]
        },
        "signal_commands": signals,
    }


def track_controller_to_ctc(outputs: Mapping[str, Any]) -> dict[str, Any]:
    """Map a Track Controller's outputs to the CTC Office's input.

    Args:
        outputs: The Track Controller's outputs, with ``ctc_reports``.

    Returns:
        The CTC Office's ``track_controller`` input.

    Raises:
        KeyError: If an output is missing.
    """
    occupancy = []
    switches = []
    crossings = []
    waysides = []
    for report in outputs["ctc_reports"]:
        waysides.append({
            "wayside_id": report["wayside_id"],
            "line": report["line"],
            "ready": report["ready"],
            "reason": report["reason"],
        })
        for entry in report["blocks"]:
            line, number = _key(entry["block"])
            value = entry["value"]
            occupancy.append(
                {"line": line, "block_id": number,
                 "occupied": value["occupied"]}
            )
            if value["switch_position"] is not None:
                switches.append(
                    {"line": line, "switch_id": number,
                     "position": value["switch_position"]}
                )
            if value["crossing_active"] is not None:
                crossings.append(
                    {"line": line, "crossing_id": number,
                     "state": ("active" if value["crossing_active"]
                               else "inactive")}
                )
    return {
        "occupancy": occupancy,
        "switches": switches,
        "crossings": crossings,
        "waysides": waysides,
    }


def line_ready(waysides: Iterable[Mapping[str, Any]], line: str) -> bool:
    """Return whether a line's waysides are ready.

    A line is ready once a wayside on it has reported and every wayside
    on it is ready (``ctc.interface.TrackControllerInputs``; R70).

    Args:
        waysides: The ``waysides`` of the CTC Office's input.
        line: The line.
    """
    on_line = [each for each in waysides if each["line"] == line]
    return bool(on_line) and all(each["ready"] for each in on_line)


def _block(line: str, number: str) -> dict[str, str]:
    # One block in the Track Controller's form.
    return {"line": line, "block_id": number}


def _key(block: Mapping[str, Any]) -> tuple[str, str]:
    # A Track Controller block's line and number.
    return block["line"], block["block_id"]


def _name(names: BlockNames, block: Mapping[str, Any]) -> str:
    # The Track Model's name for a Track Controller block.
    return names.track_model_name(*_key(block))


def _on_line(
    values: Mapping[str, Any], line: str, names: BlockNames
) -> list[tuple[str, Any]]:
    # The values keyed by the Track Model's names that are on ``line``,
    # keyed by block number instead; names not yet known are left out.
    found = []
    for name, value in values.items():
        try:
            block_line, number = names.block(name)
        except KeyError:
            continue
        if block_line == line:
            found.append((number, value))
    return found
