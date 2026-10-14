"""Remote stimulus protocol for the Track Controller.

The test UI is a separate process that plays the CTC, the Track Model
and the programmer. This module is the whole vocabulary it speaks, kept
free of any transport so it can be tested without a socket or a window.

Messages are single JSON objects. A client sends::

    {"id": 7, "type": "physical", "op": "set_occupancy",
     "controller": "GTC-03", "block": "62", "value": true}
    {"id": 8, "type": "user", "op": "select_controller", "name": "GTC-03"}

and the wayside answers every one with ``ack`` or ``error``, and pushes a
full ``snapshot`` whenever anything changes.

The two kinds of input are deliberately different in what they touch:

``physical``  the world the controller reacts to. They write onto a
              controller's input card, so they change what the PLC
              program sees and therefore what it drives. Maintenance
              mode and switch commands are here too: they come from the
              CTC Office, not from the programmer.
``user``      the programmer's hands. They do exactly what clicking the
              same control in the Track Controller UI does, so they
              exercise the UI's own features and nothing else.

Every speed on the wire is a whole number of m/s and every authority a
whole number of blocks, the system's backend units. Only the screen
shows mph.
"""

from __future__ import annotations

from typing import Any, Mapping

from track_ctrl.controller import TrackController
from track_ctrl.display import format_mph
from track_ctrl.system import TrackControllerSystem
from utils.system_clock import InvalidClockSettingError, SystemClock

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
    "set_suggestion",
    "set_all_suggestions",
    "clear_suggestion",
    "set_speed_limit",
    "set_maintenance",
    "set_switch_command",
)

USER_OPS = (
    "select_line",
    "select_controller",
    "set_tab",
    "set_switch",
    "release_switch",
    "run",
    "commit",
    "new_file",
    "open_file",
    "append_buffer",
    "load_program",
)

CLOCK_OPS = ("pause", "resume", "set_speed")


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


def _optional_number(message: Mapping[str, Any], key: str) -> float | None:
    if message.get(key) is None:
        return None
    return _number(message, key)


# --- physical inputs --------------------------------------------------

def apply_physical(
    system: TrackControllerSystem, message: Mapping[str, Any]
) -> str:
    """Apply one physical-input message and rescan what it touched.

    Returns a one-line description for the controller's terminal log.
    Raises :class:`StimulusError` for anything it cannot apply, leaving
    the controller untouched.
    """
    op = _text(message, "op")
    if op not in PHYSICAL_OPS:
        raise StimulusError(f"unknown physical op: {op}")

    # Maintenance mode is the CTC Office's and applies to the whole
    # system, so it names no controller.
    if op == "set_maintenance":
        active = _flag(message, "value")
        system.set_maintenance(active)
        return f"TEST CTC maintenance mode = {int(active)}"

    try:
        controller = system.controller(_text(message, "controller"))
        note = _apply_physical_op(system, controller, op, message)
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
    system: TrackControllerSystem, controller: TrackController,
    op: str, message: Mapping[str, Any]
) -> str:
    tag = f"TEST {controller.config.controller_id}"

    if op == "set_occupancy":
        block, value = _text(message, "block"), _flag(message, "value")
        system.set_occupancy(controller, block, value)
        return f"{tag} occupancy {block} = {int(value)}"
    if op == "clear_occupancy":
        for owned_block in controller.blocks:
            system.set_occupancy(controller, owned_block.block_id, False)
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
    if op == "set_suggestion":
        block = _text(message, "block")
        speed = _optional_number(message, "speed_mps")
        authority = _optional_number(message, "authority_blocks")
        if speed is None and authority is None:
            raise StimulusError(
                "give 'speed_mps' or 'authority_blocks', or both"
            )
        controller.set_suggestion(block, speed, authority)
        shown = controller.inputs.suggestions[block]
        return (
            f"{tag} CTC suggests block {block}: "
            f"{format_mph(shown.speed_mps)}, "
            f"{shown.authority_blocks} block(s)"
        )
    if op == "set_all_suggestions":
        speed = _optional_number(message, "speed_mps")
        authority = _optional_number(message, "authority_blocks")
        if speed is None and authority is None:
            raise StimulusError(
                "give 'speed_mps' or 'authority_blocks', or both"
            )
        controller.set_all_suggestions(speed, authority)
        return f"{tag} CTC suggestion set on all {len(controller.blocks)} blocks"
    if op == "clear_suggestion":
        block = _text(message, "block")
        controller.clear_suggestion(block)
        return f"{tag} CTC sends nothing for block {block}"
    if op == "set_switch_command":
        switch = _text(message, "switch")
        position = message.get("position")
        if position is None:
            controller.set_ctc_switch_command(switch, None)
            return f"{tag} CTC withdrew its command for switch {switch}"
        if position not in ("normal", "reverse"):
            raise StimulusError("'position' must be normal, reverse or null")
        controller.set_ctc_switch_command(switch, position == "reverse")
        return f"{tag} CTC commands switch {switch} {position}"

    # set_speed_limit: a missing or null value clears the override.
    if message.get("value") is None:
        controller.set_speed_limit_override(None)
        return f"{tag} speed limit back to the per-block limits"
    limit = _number(message, "value")
    controller.set_speed_limit_override(limit)
    return f"{tag} speed limit = {format_mph(limit)}"


# --- the shared clock ---------------------------------------------------

def apply_clock(clock: SystemClock, message: Mapping[str, Any]) -> str:
    """Pause, resume or re-speed the shared simulation clock.

    Neither a physical input nor a programmer action: the clock belongs
    to the central harness, and the CTC Office sets its speed and pause
    through it (D017). Standing alone, the test UI plays that part.
    """
    op = _text(message, "op")
    if op == "pause":
        clock.pause()
        return "TEST clock paused"
    if op == "resume":
        clock.resume()
        return "TEST clock running"
    if op == "set_speed":
        speed = message.get("speed")
        if isinstance(speed, bool) or not isinstance(speed, int):
            raise StimulusError("'speed' must be 1 or 10")
        try:
            clock.set_speed(speed)
        except InvalidClockSettingError as error:
            raise StimulusError(str(error)) from None
        return f"TEST clock speed {speed}x"
    raise StimulusError(f"unknown clock op: {op}")


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

def _circuit_text(speed_mps: int, authority_blocks: int) -> str:
    return f"{format_mph(speed_mps)} · {authority_blocks} BLK"


def output_rows(controller: TrackController) -> list[dict[str, Any]]:
    """The outputs as display rows, shared by every view.

    Speed is shown in mph here and only here: the values underneath are
    whole m/s.
    """
    outputs = controller.outputs
    rows: list[dict[str, Any]] = []
    for block in controller.blocks:
        circuit = outputs.track_circuits.get(block.block_id)
        if circuit is None:
            continue
        rows.append(
            {
                "name": f"TC_{block.block_id}",
                "label": f"Block {block.block_id} ({block.label})",
                "value": _circuit_text(
                    circuit.speed_mps, circuit.authority_blocks
                ),
                "kind": "circuit",
            }
        )
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
                "name": f"SIG_{name}",
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


def suggestion_rows(controller: TrackController) -> list[dict[str, Any]]:
    """What the CTC Office suggests for each block, as display rows."""
    rows: list[dict[str, Any]] = []
    for block in controller.blocks:
        suggestion = controller.inputs.suggestions.get(block.block_id)
        rows.append(
            {
                "name": f"SUG_{block.block_id}",
                "label": f"Block {block.block_id} ({block.label})",
                "value": (
                    "NONE SENT" if suggestion is None
                    else _circuit_text(
                        suggestion.speed_mps, suggestion.authority_blocks
                    )
                ),
                "kind": "suggestion",
            }
        )
    return rows


def _describe(controller: TrackController) -> dict[str, Any]:
    """Everything the test UI shows about one controller."""
    labels = {block.block_id: block.label for block in controller.blocks}
    inputs = controller.inputs
    outputs = controller.outputs
    first, last = controller.blocks[0], controller.blocks[-1]

    blocks = []
    for block in controller.blocks:
        suggestion = inputs.suggestions.get(block.block_id)
        circuit = outputs.track_circuits.get(block.block_id)
        blocks.append(
            {
                "id": block.block_id,
                "label": block.label,
                "occupied": inputs.occupancy.get(block.block_id, False),
                "closed": inputs.closed.get(block.block_id, False),
                "suggested_speed": (
                    None if suggestion is None else suggestion.speed_mps
                ),
                "suggested_authority": (
                    None if suggestion is None
                    else suggestion.authority_blocks
                ),
                "commanded_speed": (
                    None if circuit is None else circuit.speed_mps
                ),
                "commanded_authority": (
                    None if circuit is None else circuit.authority_blocks
                ),
            }
        )

    switches = []
    for switch in controller.config.switches:
        command = inputs.ctc_switch_commands.get(switch.switch_id)
        switches.append(
            {
                "id": switch.switch_id,
                "block_id": switch.block_id,
                "block": labels[switch.block_id],
                "reverse": outputs.switches.get(switch.switch_id, False),
                "fault": inputs.switch_fault.get(switch.switch_id, False),
                "moving": inputs.switch_moving.get(switch.switch_id, False),
                "manual": switch.switch_id in controller.manual_switches,
                "ctc_command": (
                    None if command is None
                    else "reverse" if command else "normal"
                ),
            }
        )

    return {
        "id": controller.config.controller_id,
        "line": controller.config.line_name,
        "span": f"{first.label} – {last.label}",
        "iteration": controller.iteration,
        "file": controller.file_name,
        "blocks": blocks,
        "switches": switches,
        "inputs": {"speed_limit": inputs.speed_limit_override_mps},
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
        "clock_paused": state.clockPaused,
        "clock_speed": state.clockSpeed,
        "standin": True,
        "maintenance": system.maintenance,
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
                1 for item in state.diagnostics["rows"]
                if item["severity"] == "error"
            ),
        },
    }
