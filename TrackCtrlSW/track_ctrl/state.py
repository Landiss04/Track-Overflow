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

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot

from track_ctrl.controller import TrackController, default_program_source
from track_ctrl.plc import SEVERITY_ERROR, compile_program, has_errors
from track_ctrl.display import mps_to_mph
from track_ctrl.models import BlockListModel, list_property
from track_ctrl.interface import (
    TrackControllerInputs,
    TrackControllerOutputs,
)
from track_ctrl.layout import (
    LayoutError,
    LineLayout,
    build_default_system,
    build_line,
    default_layout_dir,
    load_layout_file,
)
from track_ctrl.module import SwTrackController, clock_text
from track_ctrl.stimulus import output_rows, suggestion_rows

#: How often the views are refreshed while the clock runs, in ms.
UI_REFRESH_MS = 200

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
    tabChanged = Signal()
    externalChanged = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        lines: Sequence[LineLayout] | None = None,
    ) -> None:
        """Build the module's UI state.

        The module has no clock and no world of its own. Whatever drives
        it, the central harness or the test UI, calls :meth:`step` once
        per tick of the shared clock (D017), with the tick's inputs.
        Until the first tick every wayside idles at its starter program.

        Args:
            parent: Optional Qt parent.
            lines: The lines to start with, each divided among its
                waysides; the default Green and Red when None. Under the
                central harness this variant runs the Green Line only
                (R77, ``track_ctrl.module_process``).
        """
        super().__init__(parent)
        self._system = SwTrackController()
        for line in build_default_system() if lines is None else lines:
            self._system.load_track(line)

        #: Only for the header badges: whether the sender's clock is held
        #: and how fast it runs. The clock is not this module's.
        self._clock_paused = True
        self._clock_speed = 1
        #: Whether a test UI or harness is connected to drive the module.
        self._driven = False

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
        #: Set by a tick, cleared when the views are told; see _flush.
        self._dirty = False
        #: 0 is the Program tab, 1 is the View tab. Held here rather than
        #: in QML so a remote stimulus can drive it like a click does.
        self._active_tab = 0

        self._block_model = BlockListModel(self)
        # Kept in step with the selected controller on every change, so
        # the tile grids update the rows that changed and nothing else.
        self.controllerChanged.connect(self._sync_blocks)
        self.selectionChanged.connect(self._sync_blocks)
        self._sync_blocks()

        self._load_buffer_from_controller()

        # The clock ticks every 0.1 simulated seconds, 100 times a real
        # second at 10x. Telling QML on every tick would rebuild every
        # list that often, so ticks only mark the state dirty and the
        # views are refreshed at a steady, readable rate.
        self._refresh = QTimer(self)
        self._refresh.setInterval(UI_REFRESH_MS)
        self._refresh.timeout.connect(self._flush)
        self._refresh.start()

    # --- helpers -----------------------------------------------------

    @property
    def _controller(self) -> TrackController:
        return self._system.controllers[self._controller_id]

    def _log(self, line: str) -> None:
        self._terminal.append(line)
        del self._terminal[:-TERMINAL_DEPTH]

    def _stamp(self) -> str:
        # Simulated time, so the terminal agrees with the header clock.
        # Before the first tick there is none, so wall time stands in.
        time_s = self._system.time_s
        if time_s is None:
            return datetime.now().strftime("%H:%M:%S")
        return clock_text(time_s)

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

    def step(
        self, dt: float, inputs: TrackControllerInputs
    ) -> TrackControllerOutputs:
        """Run one tick of the module, and mark the views for a refresh.

        This is the call the central harness makes. The views are
        refreshed at a steady rate rather than on every tick; see
        ``_flush``.
        """
        outputs = self._system.step(dt, inputs)
        self._dirty = True
        return outputs

    # --- startup ------------------------------------------------------

    @Property(bool, notify=controllerChanged)
    def ready(self) -> bool:
        """Whether startup is done: a line is loaded, every wayside programmed.

        Until it is, the whole module drives its fail-safe outputs and
        tells the CTC Office it is not ready.
        """
        return self._system.ready

    @Property(str, notify=controllerChanged)
    def notReadyReason(self) -> str:
        """What startup still needs, for the header; empty when ready."""
        reasons = self._system.not_ready_reasons()
        if not reasons:
            return ""
        more = len(reasons) - 1
        return reasons[0] + (f" (and {more} more)" if more else "")

    @Slot()
    def loadStarterPrograms(self) -> None:
        """Commit a generated starter program to every wayside without one."""
        loaded = self._system.load_starter_programs()
        if not loaded:
            return
        self._log(
            f"[{self._stamp()}] starter programs loaded on "
            f"{len(loaded)} wayside(s)"
        )
        if self._controller_id in loaded:
            self._load_buffer_from_controller()
            self.bufferChanged.emit()
        self.terminalChanged.emit()
        self.selectionChanged.emit()
        self.controllerChanged.emit()

    def set_clock_status(self, paused: bool, speed: int) -> None:
        """Note the sender's clock state, for the header badges."""
        self._clock_paused = paused
        self._clock_speed = speed
        self.clockChanged.emit()

    def _flush(self) -> None:
        if not self._dirty:
            return
        self._dirty = False
        self.clockChanged.emit()
        self.controllerChanged.emit()

    # --- clock and selection -----------------------------------------

    @Property(str, notify=clockChanged)
    def clock(self) -> str:
        """Simulated time of day of the last tick, ``HH:MM:SS`` (D017)."""
        time_s = self._system.time_s
        return "--:--:--" if time_s is None else clock_text(time_s)

    @Property(bool, notify=clockChanged)
    def clockPaused(self) -> bool:
        """Whether the shared clock is held."""
        return self._clock_paused

    @Property(int, notify=clockChanged)
    def clockSpeed(self) -> int:
        """The shared clock's speed: 1 or 10."""
        return self._clock_speed

    @list_property(selectionChanged)
    def lines(self) -> list[dict[str, Any]]:
        """Every line, with the totals the View tab's first column shows."""
        summary: list[dict[str, Any]] = []
        for line in self._system.lines:
            occupied = sum(
                1
                for controller in self._system.controllers_for(line.name)
                for flag in controller.inputs.occupancy.values()
                if flag
            )
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
                    "occupied": occupied,
                    "closed": closed,
                    "trains": occupied,
                    "selected": line.name == self._line_name,
                }
            )
        return summary

    @list_property(selectionChanged)
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

    @Property(QUrl, constant=True)
    def layoutFolder(self) -> QUrl:
        """Where the track layout files live, to open the file dialog in."""
        return QUrl.fromLocalFile(str(default_layout_dir()))

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
        carrying = sum(
            1 for circuit in outputs.track_circuits.values()
            if circuit.speed_mps > 0
        )
        return {
            "id": controller.config.controller_id,
            "line": controller.config.line_name,
            "file": controller.file_name,
            "iteration": controller.iteration,
            "maintenance": controller.maintenance,
            "mode": (
                "Maintenance (CTC)" if controller.maintenance
                else "Automatic"
            ),
            "block_count": len(controller.blocks),
            "span": (
                f"{controller.blocks[0].label} – "
                f"{controller.blocks[-1].label}"
            ),
            "circuits": len(outputs.track_circuits),
            "carrying": carrying,
            "suggested_blocks": len(controller.inputs.suggestions),
            "committed_at": (
                controller.history[0].committed_at if controller.history else ""
            ),
            "override_count": len(outputs.overrides),
        }

    def _block_rows(self) -> list[dict[str, Any]]:
        """One row per block the selected controller owns."""
        controller = self._controller
        rows: list[dict[str, Any]] = []
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

            rows.append(
                {
                    "blockId": block.block_id,
                    "label": block.label,
                    "section": block.section,
                    "number": block.index,
                    "occupied": occupied,
                    "closed": closed,
                    "train": controller.inputs.trains.get(block.block_id, ""),
                    "feature": feature,
                    "speedLimit": round(mps_to_mph(block.speed_limit_mps)),
                    "station": block.station or "",
                }
            )
        return rows

    def _sync_blocks(self) -> None:
        self._block_model.update(self._block_rows())

    @Property(QObject, constant=True)
    def blockModel(self) -> QObject:
        """The selected controller's blocks, updated in place."""
        return self._block_model

    @Property("QVariantMap", notify=controllerChanged)
    def blockCounts(self) -> dict[str, Any]:
        """How many blocks the selected controller owns, and their state."""
        controller = self._controller
        return {
            "total": len(controller.blocks),
            "occupied": sum(
                1 for flag in controller.inputs.occupancy.values() if flag
            ),
            "closed": sum(
                1 for flag in controller.inputs.closed.values() if flag
            ),
        }

    @list_property(controllerChanged)
    def outputs(self) -> list[dict[str, Any]]:
        """Commanded outputs, as the View tab and watch pane list them."""
        return output_rows(self._controller)

    @list_property(controllerChanged)
    def suggestionRows(self) -> list[dict[str, Any]]:
        """The CTC Office's suggestion for each block, as display rows."""
        return suggestion_rows(self._controller)

    @list_property(controllerChanged)
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

    @list_property(bufferChanged)
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

    @list_property(bufferChanged)
    def diagnostics(self) -> list[dict[str, Any]]:
        """Compiler messages from the last RUN, for the parser pane."""
        return list(self._diagnostics)

    @Property("QVariantMap", notify=bufferChanged)
    def sandbox(self) -> dict[str, Any]:
        """Outputs the last RUN produced on the duplicate state."""
        return dict(self._sandbox)

    @list_property(terminalChanged)
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
        """Read a .plc file chosen in the file dialog into the buffer."""
        self.loadProgramFromPath(url.toLocalFile())

    @Slot(str)
    def loadProgramFromPath(self, file_path: str) -> None:
        """Read a .plc file from disk into the buffer.

        File I/O stays on the Python side: QML owns visuals and this
        class owns state, so a read failure is reported into the same
        terminal as everything else rather than raising inside a view.
        """
        path = Path(file_path)
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
        # The compiler's own diagnostics, plus how the program fits this
        # controller: names it does not have, outputs it leaves undriven.
        found = controller.diagnose(program)

        self._diagnostics = [
            {
                "severity": item.severity,
                "line": item.line,
                "message": item.message,
            }
            for item in found
        ]

        if has_errors(found):
            errors = sum(
                1
                for item in found
                if item.severity == SEVERITY_ERROR
            )
            self._verified_source = None
            self._sandbox = {}
            self._log(
                f"[{stamp}] compile failed — {errors} error(s); "
                "nothing was sent to the wayside"
            )
            for item in found:
                self._log(f"[{stamp}] {item.format()}")
            self.bufferChanged.emit()
            self.terminalChanged.emit()
            return

        report = controller.run_program(program, controller.inputs.copy())

        # Warnings found while scanning are added to the compiler's, so
        # the parser pane and the commit gate see one list. The static
        # check already catches most of them; only new ones are added.
        # A line the compiler already flagged is not reported twice: the
        # scan's undefined-read warning is the same problem seen later.
        seen = {item.line for item in found if item.line > 0}
        for warning in report.warnings:
            if warning.line not in seen:
                seen.add(warning.line)
                self._diagnostics.append(
                    {
                        "severity": warning.severity,
                        "line": warning.line,
                        "message": warning.message,
                    }
                )

        # Only a buffer that ran with no diagnostic at all is verified.
        # A warning on a vital program is not cosmetic: each one means
        # an output or input does something other than the code says.
        clean = not self._diagnostics
        self._verified_source = self._buffer if clean else None
        circuits = report.outputs.track_circuits
        self._sandbox = {
            "circuits": len(circuits),
            "carrying": sum(1 for c in circuits.values() if c.speed_mps > 0),
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
        for entry in self._diagnostics:
            self._log(
                f"[{stamp}] {entry['severity'].upper():<7} line "
                f"{entry['line']:>3}  {entry['message']}"
            )
        if clean:
            self._log(
                f"[{stamp}] run complete — COMMIT will put this on "
                f"{controller.config.controller_id}"
            )
        else:
            self._log(
                f"[{stamp}] run complete with {len(self._diagnostics)} "
                "warning(s) — COMMIT is blocked until they are resolved"
            )

        self.bufferChanged.emit()
        self.terminalChanged.emit()

    @Slot()
    def commit(self) -> None:
        """Promote the verified buffer to the live controller."""
        if not self.canCommit:
            if self._diagnostics and self._verified_source is None:
                reason = (
                    f"resolve the {len(self._diagnostics)} "
                    "warning(s) or error(s) first"
                )
            else:
                reason = "run this exact buffer first"
            self._log(f"[{self._stamp()}] commit refused — {reason}")
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

    # --- maintenance mode (the CTC Office's) ------------------------------

    @Property(bool, notify=maintenanceChanged)
    def maintenance(self) -> bool:
        """Whether the CTC Office has the system in maintenance mode.

        Shown, never set, from this UI: the CTC Office owns maintenance
        mode and this module obeys it.
        """
        return self._controller.maintenance

    @list_property(maintenanceChanged)
    def switches(self) -> list[dict[str, Any]]:
        """Switches the manual-switch dialog can set."""
        controller = self._controller
        rows: list[dict[str, Any]] = []
        for switch in controller.config.switches:
            block = next(
                block
                for block in controller.blocks
                if block.block_id == switch.block_id
            )
            command = controller.inputs.ctc_switch_commands.get(
                switch.switch_id
            )
            rows.append(
                {
                    "id": switch.switch_id,
                    "block": block.label,
                    "reverse": controller.outputs.switches.get(
                        switch.switch_id, False
                    ),
                    "manual": switch.switch_id in controller.manual_switches,
                    "ctc_command": (
                        "" if command is None
                        else "REVERSE" if command else "NORMAL"
                    ),
                    "normal_to": switch.normal_end,
                    "reverse_to": switch.reverse_end,
                }
            )
        return rows

    @Slot(str, bool)
    def setSwitch(self, switch_id: str, reverse: bool) -> None:
        """Hand-set one switch. Only while the CTC has maintenance on."""
        controller = self._controller
        if not controller.maintenance:
            raise RuntimeError(
                "switches can only be set by hand while the CTC Office has "
                "the system in maintenance mode"
            )
        known = {switch.switch_id for switch in controller.config.switches}
        if switch_id not in known:
            raise KeyError(f"unknown switch: {switch_id}")

        controller.manual_switches[switch_id] = reverse
        controller.scan()
        note = ""
        if switch_id in controller.inputs.ctc_switch_commands:
            note = "; the CTC Office's command for it takes precedence"
        self._log(
            f"[{self._stamp()}] {switch_id} set to "
            f"{'REVERSE' if reverse else 'NORMAL'} by hand{note}"
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

    # --- tabs, test link and remote stimulus ---------------------------

    @property
    def system(self) -> SwTrackController:
        """The wayside network, for the stimulus layer (not QML)."""
        return self._system

    @Property(int, notify=tabChanged)
    def activeTab(self) -> int:
        """Which tab is showing: 0 Program, 1 View."""
        return self._active_tab

    @Slot(int)
    def setActiveTab(self, index: int) -> None:
        """Show the Program (0) or View (1) tab."""
        if index not in (0, 1):
            raise ValueError(f"no such tab: {index}")
        if index == self._active_tab:
            return
        self._active_tab = index
        self.tabChanged.emit()

    @Property(bool, notify=externalChanged)
    def externalControl(self) -> bool:
        """Whether a test UI or harness is connected and driving ticks."""
        return self._driven

    def set_external_control(self, active: bool) -> None:
        """Note that a test UI has connected or left."""
        if self._driven == active:
            return
        self._driven = active
        note = (
            "test UI connected: it supplies the clock and the world"
            if active else "test UI disconnected: the controller idles"
        )
        self._log(f"[{self._stamp()}] {note}")
        self.externalChanged.emit()
        self.terminalChanged.emit()

    def notify_external_change(self, log_line: str | None = None) -> None:
        """Tell the views that inputs changed from outside the UI."""
        if log_line is not None:
            self._log(f"[{self._stamp()}] {log_line}")
            self.terminalChanged.emit()
        self.controllerChanged.emit()
        self.selectionChanged.emit()
        self.maintenanceChanged.emit()

    # --- track configuration -------------------------------------------

    def inspect_track_config(self, file_path: str) -> dict[str, Any]:
        """Read a layout file and report what loading it would do.

        Nothing is changed. The dialog uses this to show the user which
        line the file is, how big it is and what it would replace
        before they commit to it.
        """
        try:
            parsed = load_layout_file(file_path)
        except LayoutError as error:
            return {"ok": False, "error": str(error)}
        existing = self._system.controllers_for(parsed.name)
        return {
            "ok": True,
            "error": "",
            "file": Path(file_path).name,
            "line": parsed.name,
            "blocks": len(parsed.blocks),
            "switches": len(parsed.switches),
            "crossings": len(parsed.crossing_blocks),
            "min": parsed.min_controllers,
            "max": parsed.max_controllers,
            "default": (
                len(existing) if existing else parsed.default_controllers
            ),
            "replaces": len(existing),
        }

    def load_track_config(self, file_path: str, controllers: int) -> str:
        """Load a track layout and divide it among ``controllers`` waysides.

        Replaces the line of the same name if there is one, and with it
        every controller on that line and the programs they hold: the
        territories they governed no longer exist. Returns an empty
        string on success, otherwise a message saying why nothing was
        changed.
        """
        try:
            parsed = load_layout_file(file_path)
            line = build_line(parsed, controllers)
        except LayoutError as error:
            self._log(f"[{self._stamp()}] track configuration refused: {error}")
            self.terminalChanged.emit()
            return str(error)

        replacing = self._system.controllers_for(line.name)
        removed = self._system.load_track(line)
        # The programmer is looking at what they just loaded.
        self._line_name = line.name
        self._controller_id = line.controllers[0].controller_id
        self._load_buffer_from_controller()

        self._log(
            f"[{self._stamp()}] loaded {Path(file_path).name}: {line.name}, "
            f"{len(line.blocks)} blocks, {line.switch_count} switches, "
            f"{line.crossing_count} crossings, divided among "
            f"{len(line.controllers)} controllers"
            + (
                f"; replaced {len(replacing)} controller(s) and their "
                "programs" if removed else ""
            )
        )
        self.selectionChanged.emit()
        self.bufferChanged.emit()
        self.terminalChanged.emit()
        self.controllerChanged.emit()
        self.maintenanceChanged.emit()
        return ""

    @Slot(QUrl, result="QVariantMap")
    def inspectTrackConfig(self, url: QUrl) -> dict[str, Any]:
        """Preview a layout file chosen in the file dialog."""
        return self.inspect_track_config(url.toLocalFile())

    @Slot(QUrl, int, result=str)
    def loadTrackConfig(self, url: QUrl, controllers: int) -> str:
        """Load a layout file chosen in the file dialog."""
        return self.load_track_config(url.toLocalFile(), controllers)
