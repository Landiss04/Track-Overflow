"""Remote stimulus protocol for the Track Controller.

The test UI is a separate process that plays the CTC, the Track Model
and the programmer. This module is the whole vocabulary it speaks, kept
free of any transport so it can be tested without a socket or a window.

Messages are single JSON objects. A client sends::

    {"id": 7, "type": "physical", "op": "set_occupancy",
     "controller": "GTC-03", "block": "G051", "value": true}
    {"id": 8, "type": "user", "op": "select_controller", "id": ...}

and the wayside answers every one with ``ack`` or ``error``, and pushes a
full ``snapshot`` whenever anything changes.

The two kinds of input are deliberately different in what they touch:

``physical``  the world the controller reacts to. They write onto a
              controller's input card, so they change what the PLC
              program sees and therefore what it drives.
``user``      the programmer's hands. They do exactly what clicking the
              same control in the Track Controller UI does, so they
              exercise the UI's own features and nothing else.
"""

from __future__ import annotations

from typing import Any, Mapping

from track_ctrl.controller import TrackController
from track_ctrl.system import TrackControllerSystem

#: Name of the local (named-pipe) server the Track Controller listens on.
SERVER_NAME = "ece1140-track-controller-stimulus"

#: Longest text a user-input stimulus may append to the editor buffer.
MAX_APPEND_CHARS = 2000

PHYSICAL_OPS = (
    "set_occupancy",
    "clear_occupancy",
    "set_block_closed",
    "set_switch_fault",
    "set_switch_moving",
    "set_suggested_speed",
    "set_suggested_authority",
    "set_speed_limit",
)

USER_OPS = (
    "select_line",
    "select_controller",
    "set_tab",
    "set_maintenance",
    "set_switch",
    "release_switch",
    "run",
    "commit",
    "new_file",
    "open_file",
    "append_buffer",
    "load_program",
)


class StimulusError(ValueError):
    """A stimulus message was malformed or named something unknown."""


# --- field access -----------------------------------------------------

def _text(message: Mapping[str, Any], key: str) -> str:
    value = message.get(key)
    if not isinstance(value, str) or not value:
        raise StimulusError(f"'{key}' must be a non-empty string")
    return value


def _flag(message: Mapping[str, Any], key: str) -> bool:
    value = message.get(key)
    if not isinstance(value, bool):
        raise StimulusError(f"'{key}' must be true or false")
    return value


def _number(message: Mapping[str, Any], key: str) -> float:
    value = message.get(key)
    # bool is an int subclass; a flag is never a valid number here.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StimulusError(f"'{key}' must be a number")
    return float(value)


# --- physical inputs --------------------------------------------------

def apply_physical(
    system: TrackControllerSystem, message: Mapping[str, Any]
) -> str:
    """Apply one physical-input message and rescan the controller.

    Returns a one-line description for the controller's terminal log.
    Raises :class:`StimulusError` for anything it cannot apply, leaving
    the controller untouched.
    """
    op = _text(message, "op")
    if op not in PHYSICAL_OPS:
        raise StimulusError(f"unknown physical op: {op}")

    try:
        controller = system.controller(_text(message, "controller"))
        note = _apply_physical_op(controller, op, message)
    except KeyError as error:
        raise StimulusError(str(error.args[0])) from None
    except ValueError as error:
        if isinstance(error, StimulusError):
            raise
        raise StimulusError(str(error)) from None

    # Outputs recompute on every input change, with no wait for the
    # next tick, so the UI shows the effect of the stimulus immediately.
    controller.scan()
    return note


def _apply_physical_op(
    controller: TrackController, op: str, message: Mapping[str, Any]
) -> str:
    tag = f"TEST {controller.config.controller_id}"

    if op == "set_occupancy":
        block, value = _text(message, "block"), _flag(message, "value")
        controller.set_occupancy(block, value)
        return f"{tag} occupancy {block} = {int(value)}"
    if op == "clear_occupancy":
        controller.clear_occupancy()
        return f"{tag} occupancy cleared on every block"
    if op == "set_block_closed":
        block, value = _text(message, "block"), _flag(message, "value")
        controller.set_closed(block, value)
        return f"{tag} block {block} {'closed' if value else 'opened'}"
    if op == "set_switch_fault":
        switch, value = _text(message, "switch"), _flag(message, "value")
        controller.set_switch_fault(switch, value)
        return f"{tag} {switch} fault = {int(value)}"
    if op == "set_switch_moving":
        switch, value = _text(message, "switch"), _flag(message, "value")
        controller.set_switch_moving(switch, value)
        return f"{tag} {switch} moving = {int(value)}"
    if op == "set_suggested_speed":
        speed = _number(message, "value")
        controller.set_suggestion(speed_mph=speed)
        return f"{tag} CTC suggested speed = {speed:.0f} MPH"
    if op == "set_suggested_authority":
        authority = _number(message, "value")
        controller.set_suggestion(authority_blocks=authority)
        return f"{tag} CTC suggested authority = {int(authority)} block(s)"

    # set_speed_limit: a missing or null value clears the override.
    raw = message.get("value")
    if raw is None:
        controller.set_speed_limit_override(None)
        return f"{tag} speed limit back to the per-block limits"
    limit = _number(message, "value")
    controller.set_speed_limit_override(limit)
    return f"{tag} speed limit = {limit:.0f} MPH"


# --- user inputs ------------------------------------------------------

def apply_user(state: Any, message: Mapping[str, Any]) -> str:
    """Apply one user-input message by calling the same slots the UI does.

    ``state`` is the Track Controller UI's ``TrackControllerState``. A
    user input never reaches into the controller directly: if clicking
    the control would refuse, so does this.
    """
    op = _text(message, "op")
    if op not in USER_OPS:
        raise StimulusError(f"unknown user op: {op}")

    try:
        return _apply_user_op(state, op, message)
    except KeyError as error:
        raise StimulusError(str(error.args[0])) from None
    except (RuntimeError, ValueError) as error:
        if isinstance(error, StimulusError):
            raise
        raise StimulusError(str(error)) from None


def _apply_user_op(
    state: Any, op: str, message: Mapping[str, Any]
) -> str:
    if op == "select_line":
        name = _text(message, "name")
        state.selectLine(name)
        return f"user selected line {name}"
    if op == "select_controller":
        name = _text(message, "name")
        state.selectController(name)
        return f"user selected controller {name}"
    if op == "set_tab":
        index = int(_number(message, "index"))
        state.setActiveTab(index)
        return f"user opened the {'Program' if index == 0 else 'View'} tab"
    if op == "set_maintenance":
        state.setMaintenance(_flag(message, "value"))
        return "user toggled maintenance mode"
    if op == "set_switch":
        switch = _text(message, "switch")
        state.setSwitch(switch, _flag(message, "reverse"))
        return f"user set switch {switch} by hand"
    if op == "release_switch":
        switch = _text(message, "switch")
        state.releaseSwitch(switch)
        return f"user released switch {switch}"
    if op == "run":
        state.run()
        return "user pressed RUN"
    if op == "commit":
        state.commit()
        return "user pressed COMMIT"
    if op == "new_file":
        state.newFile()
        return "user pressed NEW"
    if op == "open_file":
        number = int(_number(message, "iteration"))
        state.openFile(number)
        return f"user opened iteration {number}"
    if op == "append_buffer":
        text = message.get("text")
        if not isinstance(text, str) or not text:
            raise StimulusError("'text' must be a non-empty string")
        if len(text) > MAX_APPEND_CHARS:
            raise StimulusError(
                f"'text' is longer than {MAX_APPEND_CHARS} characters"
            )
        if state.bufferReadOnly:
            raise StimulusError(
                "the open buffer is a committed iteration and is read-only"
            )
        state.setBuffer(state.buffer + text)
        return "user edited the buffer"

    # load_program
    path = _text(message, "path")
    state.loadProgramFromPath(path)
    return f"user loaded {path}"


# --- what the controller shows ------------------------------------------

def output_rows(controller: TrackController) -> list[dict[str, Any]]:
    """The commanded outputs as display rows, shared by every view."""
    outputs = controller.outputs
    rows: list[dict[str, Any]] = [
        {
            "name": "CMD_SPEED",
            "label": "Commanded speed",
            "value": f"{outputs.commanded_speed_mph:.0f} MPH",
            "kind": "scalar",
        },
        {
            "name": "CMD_AUTH",
            "label": "Commanded authority",
            "value": f"{outputs.commanded_authority_blocks} blocks",
            "kind": "scalar",
        },
    ]
    for name, state in outputs.switches.items():
        rows.append(
            {
                "name": f"SW_{name}",
                "label": f"Switch {name}",
                "value": "REVERSE" if state else "NORMAL",
                "kind": "switch",
            }
        )
    for name, aspect in outputs.aspects.items():
        rows.append(
            {
                "name": f"LT_{name}",
                "label": f"Signal {name}",
                "value": aspect,
                "kind": "aspect",
            }
        )
    for name, state in outputs.crossings.items():
        rows.append(
            {
                "name": f"XING_{name}",
                "label": f"Crossing {name}",
                "value": "ACTIVE" if state else "CLEAR",
                "kind": "crossing",
            }
        )
    return rows


def _describe(controller: TrackController) -> dict[str, Any]:
    """Everything the test UI shows about one controller."""
    labels = {block.block_id: block.label for block in controller.blocks}
    inputs = controller.inputs
    outputs = controller.outputs
    first, last = controller.blocks[0], controller.blocks[-1]

    return {
        "id": controller.config.controller_id,
        "line": controller.config.line_name,
        "span": f"{first.label} – {last.label}",
        "iteration": controller.iteration,
        "file": controller.file_name,
        "maintenance": controller.maintenance,
        "blocks": [
            {
                "id": block.block_id,
                "label": block.label,
                "occupied": inputs.occupancy.get(block.block_id, False),
                "closed": inputs.closed.get(block.block_id, False),
            }
            for block in controller.blocks
        ],
        "switches": [
            {
                "id": switch.switch_id,
                "block": labels[switch.block_id],
                "reverse": outputs.switches.get(switch.switch_id, False),
                "fault": inputs.switch_fault.get(switch.switch_id, False),
                "moving": inputs.switch_moving.get(switch.switch_id, False),
                "manual": switch.switch_id in controller.manual_switches,
            }
            for switch in controller.config.switches
        ],
        "inputs": {
            "suggested_speed": inputs.suggested_speed_mph,
            "suggested_authority": inputs.suggested_authority_blocks,
            "speed_limit": inputs.speed_limit_override_mph,
        },
        "commanded": {
            "speed": outputs.commanded_speed_mph,
            "authority": outputs.commanded_authority_blocks,
        },
        "outputs": output_rows(controller),
        "presence": [
            labels[block_id]
            for block_id, occupied in inputs.occupancy.items()
            if occupied
        ],
        "overrides": [
            {
                "rule": override.rule,
                "signal": override.signal,
                "message": override.message,
            }
            for override in outputs.overrides
        ],
    }


def build_snapshot(state: Any) -> dict[str, Any]:
    """Return the full picture the test UI redraws from.

    ``state`` is the Track Controller UI's ``TrackControllerState``; the
    ``ui`` block is read from it so the test UI mirrors what the
    programmer is looking at, including after they click something.
    """
    system: TrackControllerSystem = state.system
    selected = system.controller(state.selectedController)

    return {
        "type": "snapshot",
        "clock": state.clock,
        "standin": not system.external_control,
        "lines": [line.name for line in system.lines],
        "controllers": [
            _describe(controller)
            for controller in system.controllers.values()
        ],
        "ui": {
            "line": state.selectedLine,
            "controller": state.selectedController,
            "tab": state.activeTab,
            "maintenance": state.maintenance,
            "can_commit": state.canCommit,
            "buffer_dirty": state.bufferDirty,
            "buffer_read_only": state.bufferReadOnly,
            "buffer_file": state.bufferFile,
            "iteration": selected.iteration,
            "history": [
                {"number": entry.number, "file": entry.file_name}
                for entry in selected.history
            ],
            "errors": sum(
                1 for item in state.diagnostics
                if item["severity"] == "error"
            ),
        },
    }
