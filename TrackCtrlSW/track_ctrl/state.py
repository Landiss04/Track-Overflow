"""The QObject bridge between the wayside runtime and the QML views.

QML owns every visual; this class owns every value. The views read
plain dicts and lists through ``Property`` and change state only
through ``Slot`` calls, so the whole module can be driven from Python
in a test without a window.

The run / commit rule lives here because it is a workflow rule rather
than a safety rule: RUN compiles the editor buffer and scans it against
a copy of the live inputs, and COMMIT is refused until the buffer that
was run is the buffer on screen. The programmer therefore cannot put
anything on the track that they have not just watched execute.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot

from track_ctrl.controller import TrackController, default_program_source
from track_ctrl.plc import SEVERITY_ERROR, compile_program, has_errors
from track_ctrl.system import TrackControllerSystem

#: Simulation tick, in milliseconds.
TICK_INTERVAL_MS = 1000

#: Lines kept in the terminal scrollback.
TERMINAL_DEPTH = 200


class TrackControllerState(QObject):
    """Everything the Program and View tabs display."""

    clockChanged = Signal()
    selectionChanged = Signal()
    bufferChanged = Signal()
    terminalChanged = Signal()
    controllerChanged = Signal()
    maintenanceChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._system = TrackControllerSystem()

        first_line = self._system.lines[0]
        self._line_name = first_line.name
        self._controller_id = first_line.controllers[0].controller_id

        self._buffer: str = ""
        self._buffer_file = ""
        self._terminal: list[str] = []
        self._diagnostics: list[dict[str, Any]] = []
        self._sandbox: dict[str, Any] = {}
        #: The buffer text of the last successful RUN. COMMIT is only
        #: offered while this still matches what is on screen.
        self._verified_source: str | None = None
        #: Which explorer entry is open: 0 is the live buffer, any
        #: other number is that committed iteration, shown read-only.
        self._open_iteration = 0
        self._clock = datetime.now().strftime("%H:%M:%S")

        self._load_buffer_from_controller()

        self._timer = QTimer(self)
        self._timer.setInterval(TICK_INTERVAL_MS)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    # --- helpers -----------------------------------------------------

    @property
    def _controller(self) -> TrackController:
        return self._system.controllers[self._controller_id]

    def _log(self, line: str) -> None:
        self._terminal.append(line)
        del self._terminal[:-TERMINAL_DEPTH]

    def _stamp(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _load_buffer_from_controller(self) -> None:
        """Open the committed program of the selected controller."""
        controller = self._controller
        program = controller.program
        self._buffer = (
            program.source if program is not None
            else default_program_source(controller)
        )
        self._buffer_file = controller.file_name
        self._verified_source = None
        self._open_iteration = 0
        self._sandbox = {}
        self._diagnostics = []
        self._terminal = []
        self._log(
            f"[{self._stamp()}] opened {controller.file_name} from "
            f"{controller.config.controller_id} "
            f"(iteration #{controller.iteration})"
        )

    def _on_tick(self) -> None:
        self._clock = datetime.now().strftime("%H:%M:%S")
        self._system.tick()
        self.clockChanged.emit()
        self.controllerChanged.emit()

    # --- clock and selection -----------------------------------------

    @Property(str, notify=clockChanged)
    def clock(self) -> str:
        """Simulation wall clock, shown in the header."""
        return self._clock

    @Property("QVariantList", notify=selectionChanged)
    def lines(self) -> list[dict[str, Any]]:
        """Every line, with the totals the View tab's first column shows."""
        summary: list[dict[str, Any]] = []
        for line in self._system.lines:
            placed = self._system.occupancy_for(line)
            closed = sum(
                1
                for controller in self._system.controllers_for(line.name)
                for state in controller.inputs.closed.values()
                if state
            )
            summary.append(
                {
                    "name": line.name,
                    "color": line.color,
                    "controllers": len(line.controllers),
                    "blocks": len(line.blocks),
                    "occupied": len(placed),
                    "closed": closed,
                    "trains": len(placed),
                    "selected": line.name == self._line_name,
                }
            )
        return summary

    @Property("QVariantList", notify=selectionChanged)
    def controllers(self) -> list[dict[str, Any]]:
        """The controllers on the selected line."""
        rows: list[dict[str, Any]] = []
        for controller in self._system.controllers_for(self._line_name):
            blocks = controller.blocks
            occupied = sum(
                1
                for block in blocks
                if controller.inputs.occupancy.get(block.block_id, False)
            )
            rows.append(
                {
                    "id": controller.config.controller_id,
                    "span": f"{blocks[0].label} – {blocks[-1].label}",
                    "block_count": len(blocks),
                    "occupied": occupied,
                    "iteration": controller.iteration,
                    "maintenance": controller.maintenance,
                    "selected": (
                        controller.config.controller_id == self._controller_id
                    ),
                }
            )
        return rows

    @Property(str, notify=selectionChanged)
    def selectedLine(self) -> str:
        """Name of the line currently selected."""
        return self._line_name

    @Property(str, notify=selectionChanged)
    def selectedController(self) -> str:
        """Id of the controller currently selected."""
        return self._controller_id

    @Property(str, notify=selectionChanged)
    def selectedLineColor(self) -> str:
        """Identity colour of the selected line."""
        return self._system.line(self._line_name).color

    @Slot(str)
    def selectLine(self, name: str) -> None:
        """Select a line and its first controller."""
        if name == self._line_name:
            return
        self._line_name = name
        self._controller_id = (
            self._system.line(name).controllers[0].controller_id
        )
        self._load_buffer_from_controller()
        self.selectionChanged.emit()
        self.bufferChanged.emit()
        self.terminalChanged.emit()
        self.controllerChanged.emit()
        self.maintenanceChanged.emit()

    @Slot(str)
    def selectController(self, controller_id: str) -> None:
        """Select a controller and open its committed program."""
        if controller_id == self._controller_id:
            return
        if controller_id not in self._system.controllers:
            raise KeyError(f"unknown controller: {controller_id}")
        self._controller_id = controller_id
        self._load_buffer_from_controller()
        self.selectionChanged.emit()
        self.bufferChanged.emit()
        self.terminalChanged.emit()
        self.controllerChanged.emit()
        self.maintenanceChanged.emit()

    # --- the selected controller -------------------------------------

    @Property("QVariantMap", notify=controllerChanged)
    def controller(self) -> dict[str, Any]:
        """Header and summary values for the selected controller."""
        controller = self._controller
        outputs = controller.outputs
        return {
            "id": controller.config.controller_id,
            "line": controller.config.line_name,
            "file": controller.file_name,
            "iteration": controller.iteration,
            "maintenance": controller.maintenance,
            "mode": "Maintenance" if controller.maintenance else "Automatic",
            "block_count": len(controller.blocks),
            "span": (
                f"{controller.blocks[0].label} – "
                f"{controller.blocks[-1].label}"
            ),
            "commanded_speed": outputs.commanded_speed_mph,
            "commanded_authority": outputs.commanded_authority_blocks,
            "suggested_speed": controller.inputs.suggested_speed_mph,
            "suggested_authority": controller.inputs.suggested_authority_blocks,
            "committed_at": (
                controller.history[0].committed_at if controller.history else ""
            ),
            "override_count": len(outputs.overrides),
        }

    @Property("QVariantList", notify=controllerChanged)
    def blocks(self) -> list[dict[str, Any]]:
        """Every block the selected controller owns, for the tile grid."""
        controller = self._controller
        tiles: list[dict[str, Any]] = []
        for block in controller.blocks:
            occupied = controller.inputs.occupancy.get(block.block_id, False)
            closed = controller.inputs.closed.get(block.block_id, False)
            feature = ""
            for switch in controller.config.switches:
                if switch.block_id == block.block_id:
                    feature = "SWITCH"
            for crossing in controller.config.crossings:
                if crossing.block_id == block.block_id:
                    feature = "XING"
            for signal in controller.config.signals:
                if signal.block_id == block.block_id:
                    feature = "SIGNAL"
            if block.station is not None:
                feature = "STATION"

            tiles.append(
                {
                    "id": block.block_id,
                    "label": block.label,
                    "section": block.section,
                    "number": block.index,
                    "occupied": occupied,
                    "closed": closed,
                    "train": controller.inputs.trains.get(block.block_id, ""),
                    "feature": feature,
                    "speed_limit": block.speed_limit_mph,
                    "station": block.station or "",
                }
            )
        return tiles

    @Property("QVariantList", notify=controllerChanged)
    def outputs(self) -> list[dict[str, Any]]:
        """Commanded outputs, as the View tab and watch pane list them."""
        controller = self._controller
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

    @Property("QVariantList", notify=controllerChanged)
    def inputSignals(self) -> list[dict[str, Any]]:
        """The scalar inputs the watch pane shows beside the block grid."""
        controller = self._controller
        return [
            {
                "name": "SUG_SPEED",
                "label": "Suggested speed",
                "value": f"{controller.inputs.suggested_speed_mph:.0f} MPH",
            },
            {
                "name": "SUG_AUTH",
                "label": "Suggested authority",
                "value": (
                    f"{controller.inputs.suggested_authority_blocks} blocks"
                ),
            },
        ]

    @Property("QVariantList", notify=controllerChanged)
    def overrides(self) -> list[dict[str, Any]]:
        """Vital restrictions currently applied to the program's output."""
        return [
            {
                "rule": override.rule,
                "signal": override.signal,
                "message": override.message,
            }
            for override in self._controller.outputs.overrides
        ]

    # --- the editor --------------------------------------------------

    @Property(str, notify=bufferChanged)
    def buffer(self) -> str:
        """The editor buffer: what RUN compiles and COMMIT promotes."""
        return self._buffer

    @Property(str, notify=bufferChanged)
    def bufferFile(self) -> str:
        """Name of the file open in the editor."""
        return self._buffer_file

    @Property(bool, notify=bufferChanged)
    def bufferDirty(self) -> bool:
        """Whether the live buffer differs from the committed program.

        A history entry on screen is never "dirty": it is a record, not
        a draft.
        """
        if self._open_iteration != 0:
            return False
        program = self._controller.program
        return program is None or program.source != self._buffer

    @Property(bool, notify=bufferChanged)
    def canCommit(self) -> bool:
        """Whether COMMIT is allowed right now.

        Only after a clean RUN of exactly this text: committing
        something that has not been executed in the sandbox is the one
        thing the workflow exists to prevent.
        """
        return (
            self._verified_source is not None
            and self._verified_source == self._buffer
        )

    @Property("QVariantList", notify=bufferChanged)
    def files(self) -> list[dict[str, Any]]:
        """Explorer entries: the live file plus the committed history."""
        controller = self._controller
        entries: list[dict[str, Any]] = [
            {
                "name": controller.file_name,
                "detail": (
                    "COMMITTED" if self._open_iteration != 0
                    else "EDITED" if self.bufferDirty else "COMMITTED"
                ),
                "iteration": 0,
                "current": self._open_iteration == 0,
                "readonly": False,
            }
        ]
        for entry in controller.history:
            entries.append(
                {
                    "name": entry.file_name,
                    "detail": f"#{entry.number} · {entry.committed_at}",
                    "iteration": entry.number,
                    "current": entry.number == self._open_iteration,
                    "readonly": True,
                }
            )
        return entries

    @Property(bool, notify=bufferChanged)
    def bufferReadOnly(self) -> bool:
        """Whether the open buffer is a committed iteration.

        History is a record of what ran, so it is shown rather than
        edited. Editing resumes on returning to the live buffer.
        """
        return self._open_iteration != 0

    @Property("QVariantList", notify=bufferChanged)
    def diagnostics(self) -> list[dict[str, Any]]:
        """Compiler messages from the last RUN, for the parser pane."""
        return list(self._diagnostics)

    @Property("QVariantMap", notify=bufferChanged)
    def sandbox(self) -> dict[str, Any]:
        """Outputs the last RUN produced on the duplicate state."""
        return dict(self._sandbox)

    @Property("QVariantList", notify=terminalChanged)
    def terminal(self) -> list[str]:
        """Terminal scrollback for the docked output pane."""
        return list(self._terminal)

    @Slot(str)
    def setBuffer(self, text: str) -> None:
        """Replace the editor buffer from the text area."""
        if text == self._buffer:
            return
        self._buffer = text
        # Any edit invalidates the previous run: what was verified is
        # no longer what is on screen.
        self.bufferChanged.emit()

    @Slot(int)
    def openFile(self, iteration: int) -> None:
        """Open a history entry, or return to the live buffer."""
        controller = self._controller
        if iteration == 0:
            self._load_buffer_from_controller()
        else:
            entry = next(
                (item for item in controller.history
                 if item.number == iteration),
                None,
            )
            if entry is None:
                raise KeyError(f"unknown iteration: {iteration}")
            self._buffer = entry.source
            self._buffer_file = entry.file_name
            self._verified_source = None
            self._open_iteration = entry.number
            self._log(
                f"[{self._stamp()}] opened iteration #{entry.number} "
                f"({entry.file_name}) read-only"
            )
        self.bufferChanged.emit()
        self.terminalChanged.emit()

    @Slot(QUrl)
    def loadProgramFromUrl(self, url: QUrl) -> None:
        """Read a .plc file chosen in the file dialog into the buffer.

        File I/O stays on the Python side: QML owns visuals and this
        class owns state, so a read failure is reported into the same
        terminal as everything else rather than raising inside a view.
        """
        path = Path(url.toLocalFile())
        try:
            with path.open(encoding="utf-8") as handle:
                source = handle.read()
        except OSError as error:
            self._log(f"[{self._stamp()}] could not read {path.name}: {error}")
            self.terminalChanged.emit()
            return
        self.loadProgramFile(path.name, source)

    @Slot(str, str)
    def loadProgramFile(self, file_name: str, source: str) -> None:
        """Load an external .plc file into the buffer.

        A loaded file takes the same RUN then COMMIT path as anything
        typed by hand; nothing reaches the track on load alone.
        """
        self._buffer = source
        self._buffer_file = file_name
        self._verified_source = None
        self._open_iteration = 0
        self._sandbox = {}
        self._diagnostics = []
        self._log(
            f"[{self._stamp()}] loaded {file_name} into the buffer "
            "— run it before committing"
        )
        self.bufferChanged.emit()
        self.terminalChanged.emit()

    @Slot()
    def newFile(self) -> None:
        """Start a fresh program from the controller's own layout."""
        controller = self._controller
        self._buffer = default_program_source(controller)
        self._buffer_file = f"{controller.config.controller_id.lower()}_new.plc"
        self._verified_source = None
        self._open_iteration = 0
        self._sandbox = {}
        self._diagnostics = []
        self._log(f"[{self._stamp()}] new buffer from the controller layout")
        self.bufferChanged.emit()
        self.terminalChanged.emit()

    # --- run and commit ----------------------------------------------

    @Slot()
    def run(self) -> None:
        """Compile the buffer and scan it against duplicate state.

        Nothing here touches the committed program or the live outputs.
        The controller's inputs are copied first, so the candidate
        program sees exactly the world the live one does without being
        able to change it.
        """
        controller = self._controller
        stamp = self._stamp()
        program = compile_program(self._buffer)

        self._diagnostics = [
            {
                "severity": item.severity,
                "line": item.line,
                "message": item.message,
            }
            for item in program.diagnostics
        ]

        if has_errors(program.diagnostics):
            errors = sum(
                1
                for item in program.diagnostics
                if item.severity == SEVERITY_ERROR
            )
            self._verified_source = None
            self._sandbox = {}
            self._log(
                f"[{stamp}] compile failed — {errors} error(s); "
                "nothing was sent to the wayside"
            )
            for item in program.diagnostics:
                self._log(f"[{stamp}] {item.format()}")
            self.bufferChanged.emit()
            self.terminalChanged.emit()
            return

        report = controller.run_program(program, controller.inputs.copy())

        self._verified_source = self._buffer
        self._sandbox = {
            "speed": report.outputs.commanded_speed_mph,
            "authority": report.outputs.commanded_authority_blocks,
            "raw_speed": report.raw_speed_mph,
            "raw_authority": report.raw_authority_blocks,
            "booleans": program.boolean_count,
            "lines": program.line_count,
            "overrides": len(report.outputs.overrides),
        }

        self._log(
            f"[{stamp}] compiled {self._buffer_file} — "
            f"{program.line_count} lines, {program.boolean_count} booleans, "
            "0 errors"
        )
        self._log(f"[{stamp}] sandbox scan on duplicate state — live "
                  "outputs untouched")
        for line in report.log:
            self._log(line)
        for warning in report.warnings:
            self._log(f"[{stamp}] {warning.format()}")
        self._log(
            f"[{stamp}] run complete — COMMIT will put this on "
            f"{controller.config.controller_id}"
        )

        self.bufferChanged.emit()
        self.terminalChanged.emit()

    @Slot()
    def commit(self) -> None:
        """Promote the verified buffer to the live controller."""
        if not self.canCommit:
            self._log(
                f"[{self._stamp()}] commit refused — run this exact "
                "buffer first"
            )
            self.terminalChanged.emit()
            return

        controller = self._controller
        stamp = self._stamp()
        entry = controller.commit(self._buffer, self._buffer_file)
        controller.scan()

        self._log(
            f"[{stamp}] committed iteration #{entry.number} to "
            f"{controller.config.controller_id} — {entry.file_name} is "
            "now executing"
        )
        self._verified_source = None

        self.bufferChanged.emit()
        self.terminalChanged.emit()
        self.controllerChanged.emit()
        self.selectionChanged.emit()

    # --- maintenance mode --------------------------------------------

    @Property(bool, notify=maintenanceChanged)
    def maintenance(self) -> bool:
        """Whether the selected controller is in maintenance mode."""
        return self._controller.maintenance

    @Property("QVariantList", notify=maintenanceChanged)
    def switches(self) -> list[dict[str, Any]]:
        """Switches the maintenance dialog can set."""
        controller = self._controller
        rows: list[dict[str, Any]] = []
        for switch in controller.config.switches:
            block = next(
                block
                for block in controller.blocks
                if block.block_id == switch.block_id
            )
            rows.append(
                {
                    "id": switch.switch_id,
                    "block": block.label,
                    "reverse": controller.outputs.switches.get(
                        switch.switch_id, False
                    ),
                    "manual": switch.switch_id in controller.manual_switches,
                    "normal_to": switch.normal_to,
                    "reverse_to": switch.reverse_to,
                }
            )
        return rows

    @Slot(bool)
    def setMaintenance(self, active: bool) -> None:
        """Enter or leave maintenance mode on the selected controller.

        Leaving clears every manual override, so the program takes the
        switches back rather than inheriting a hand-set position.
        """
        controller = self._controller
        if controller.maintenance == active:
            return
        controller.maintenance = active
        if not active:
            controller.manual_switches.clear()
        controller.scan()
        self._log(
            f"[{self._stamp()}] {controller.config.controller_id} "
            f"{'entered' if active else 'left'} maintenance mode"
        )
        self.maintenanceChanged.emit()
        self.controllerChanged.emit()
        self.selectionChanged.emit()
        self.terminalChanged.emit()

    @Slot(str, bool)
    def setSwitch(self, switch_id: str, reverse: bool) -> None:
        """Hand-set one switch. Maintenance mode only."""
        controller = self._controller
        if not controller.maintenance:
            raise RuntimeError(
                "switches can only be set by hand in maintenance mode"
            )
        known = {switch.switch_id for switch in controller.config.switches}
        if switch_id not in known:
            raise KeyError(f"unknown switch: {switch_id}")

        controller.manual_switches[switch_id] = reverse
        controller.scan()
        self._log(
            f"[{self._stamp()}] {switch_id} set to "
            f"{'REVERSE' if reverse else 'NORMAL'} by hand; authority on "
            f"{controller.config.controller_id} held at 0"
        )
        self.maintenanceChanged.emit()
        self.controllerChanged.emit()
        self.terminalChanged.emit()

    @Slot(str)
    def releaseSwitch(self, switch_id: str) -> None:
        """Give one switch back to the program."""
        controller = self._controller
        if controller.manual_switches.pop(switch_id, None) is None:
            return
        controller.scan()
        self._log(
            f"[{self._stamp()}] {switch_id} released back to the program"
        )
        self.maintenanceChanged.emit()
        self.controllerChanged.emit()
        self.terminalChanged.emit()

    # --- block closure (stands in for the CTC) ------------------------

    @Slot(str, bool)
    def setBlockClosed(self, block_id: str, closed: bool) -> None:
        """Close or reopen a block, as the CTC would."""
        self._system.set_block_closed(block_id, closed)
        self._controller.scan()
        self._log(
            f"[{self._stamp()}] block {block_id} "
            f"{'closed for maintenance' if closed else 'reopened'}"
        )
        self.controllerChanged.emit()
        self.selectionChanged.emit()
        self.terminalChanged.emit()
