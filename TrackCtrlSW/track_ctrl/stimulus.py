"""Remote protocol between the Track Controller and its test UI.

The test UI is a separate process. It plays the CTC Office, the Track
Model, the shared clock and the programmer. This module is the part of
the vocabulary that touches the Track Controller UI itself, kept free of
any transport so it can be tested without a socket or a window.

Messages are single JSON objects, one per line. A client sends::

    {"id": 7, "type": "step", "dt": 0.1, "inputs": {...}}
    {"id": 8, "type": "user", "op": "select_controller", "name": "GTC-03"}
    {"id": 9, "type": "clock", "paused": false, "speed": 10}

and the wayside answers each with ``outputs`` (to a ``step``), ``ack`` or
``error``, and pushes a full ``snapshot`` whenever anything the UI shows
changes.

``step``  one tick of the module boundary: exactly what the central
          harness will do. The inputs and outputs are the boundary
          types in :mod:`track_ctrl.interface`, in :mod:`track_ctrl.wire`.
          The world the controller reacts to is the sender's, not this
          module's.
``user``  the programmer's hands. They do exactly what clicking the same
          control in the Track Controller UI does, so they exercise the
          UI's own features and nothing else.
``clock`` a note of whether the sender's clock is paused and how fast it
          runs, so the header can show it. The clock is not this
          module's: it only displays it (D017).

Every speed on the wire is a whole number of m/s and every authority a
whole number of blocks, the system's backend units. Only the screen
shows mph.
"""

from __future__ import annotations

from typing import Any, Mapping

from track_ctrl.controller import TrackController
from track_ctrl.display import format_mph

#: Name of the local (named-pipe) server the Track Controller listens on.
SERVER_NAME = "ece1140-track-controller-stimulus"

#: Longest text a user-input stimulus may append to the editor buffer.
MAX_APPEND_CHARS = 2000

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
    "load_starter_programs",
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

    if op == "load_starter_programs":
        before = state.system.not_ready_reasons()
        state.loadStarterPrograms()
        return f"user loaded starter programs ({len(before)} were missing)"

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


def _describe(
    controller: TrackController, line_key: str
) -> dict[str, Any]:
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
        "line_key": line_key,
        "span": f"{first.label} – {last.label}",
        "iteration": controller.iteration,
        "file": controller.file_name,
        "blocks": blocks,
        "switches": switches,
        "crossings": [
            crossing.block_id for crossing in controller.config.crossings
        ],
        "signals": [
            signal.block_id for signal in controller.config.signals
        ],
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
    module = state.system
    selected = module.controller(state.selectedController)

    return {
        "type": "snapshot",
        "clock": state.clock,
        "maintenance": module.maintenance,
        "ready": module.ready,
        "not_ready": list(module.not_ready_reasons()),
        "lines": [line.name for line in module.lines],
        "controllers": [
            _describe(controller, module.line_key(controller_id))
            for controller_id, controller in module.controllers.items()
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
