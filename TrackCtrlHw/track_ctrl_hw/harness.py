"""Test harness for the Track Controller test UI.

The test UI stands in for every neighbour of the Track Controller: the
CTC Office, the Track Model and the clock. It drives the module through
``TestLinkClient`` with ``step(dt, inputs)`` once per clock tick, and
reads back only the module's outputs (decision D010 sets the pattern).

Every input and output is per block. One wayside and one block are
selected at a time, and all four tables show that block. Maintenance
mode is the only input that is not per block: the CTC Office sets it
for the whole system.

Values are shown in backend units (m/s, blocks), because this page
probes the module boundary rather than presenting it to an operator.

Time comes from the shared simulation clock (``utils/system_clock.py``)
at the fixed time step of decision D006. ``ClockDriver`` ticks it in
real time while it runs, at 1x or 10x; Send and Advance tick it by
hand. Every tick sends the inputs as they stand.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from track_ctrl_hw import display
from track_ctrl_hw.errors import TrackControllerError
from track_ctrl_hw.interface import (
    BlockKey,
    CtcInputs,
    Suggestion,
    Territory,
    TrackControllerInputs,
    TrackControllerOutputs,
    TrackModelInputs,
)
from track_ctrl_hw.link import TestLinkClient
from track_ctrl_hw.rows_model import RowsModel
from track_ctrl_hw.wayside import speed_limit_whole_mps

# The shared clock lives in the repository-level utils/ package.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from utils.clock_driver import ClockDriver  # noqa: E402
from utils.system_clock import ALLOWED_SPEEDS, SystemClock  # noqa: E402

CTC_GROUP = "ctc"
TRACK_MODEL_GROUP = "track_model"

POSITIONS = {"NORMAL": "normal", "REVERSE": "reverse"}
GATES = {"GATES UP": False, "GATES DOWN": True}
ASPECTS = {
    "RED": "red",
    "YELLOW": "yellow",
    "GREEN": "green",
    "SUPER GREEN": "super_green",
}
FAILURES = {
    "NONE": None,
    "BROKEN_RAIL": "broken_rail",
    "TRACK_CIRCUIT": "track_circuit",
    "POWER": "power",
}

#: Most ticks one Advance runs: ten simulated minutes.
MAX_TICK_STEP = 6000
_DEFAULT_TICK_STEP = 10
_REFRESH_MS = 100


def _label(table: dict[str, Any], value: Any) -> str:
    for label, wire_value in table.items():
        if wire_value == value:
            return label
    return ""


@dataclass(frozen=True)
class BlockInputs:
    """What the stand-ins send for one block."""

    suggestion: bool = False
    suggested_speed: int = 0
    suggested_authority: int = 1
    block_closed: bool = False
    switch_command: str = "NORMAL"
    block_occupancy: bool = False
    track_failure: str = "NONE"
    switch_state: str = "NORMAL"
    crossing_state: str = "GATES UP"
    signal_aspect: str = "RED"


_FIELD_KINDS = {
    "suggestion": "bool",
    "suggested_speed": "uint",
    "suggested_authority": "uint",
    "block_closed": "bool",
    "switch_command": "enum",
    "block_occupancy": "bool",
    "track_failure": "enum",
    "switch_state": "enum",
    "crossing_state": "enum",
    "signal_aspect": "enum",
}
_FIELD_OPTIONS = {
    "switch_command": list(POSITIONS),
    "track_failure": list(FAILURES),
    "switch_state": list(POSITIONS),
    "crossing_state": list(GATES),
    "signal_aspect": list(ASPECTS),
}
_GROUP_FIELDS = {
    CTC_GROUP: (
        "suggestion", "suggested_speed", "suggested_authority",
        "block_closed", "switch_command",
    ),
    TRACK_MODEL_GROUP: (
        "block_occupancy", "track_failure", "switch_state",
        "crossing_state", "signal_aspect",
    ),
}
_UNITS = {"suggested_speed": "m/s", "suggested_authority": "blocks"}


class TestHarness(QObject):
    """Stand-in producers and clock for the Track Controller."""

    __test__ = False  # not a pytest test class

    selectionChanged = Signal()
    connectionChanged = Signal()
    runControlChanged = Signal()
    statusChanged = Signal()

    def __init__(
        self,
        link: TestLinkClient | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._link = link or TestLinkClient(parent=self)
        self._territories: dict[str, Territory] = {}
        self._inputs: dict[BlockKey, BlockInputs] = {}
        self._maintenance = False
        self._selected_wayside = ""
        self._selected_block = ""
        self._error = ""
        self._edits = 0
        self._tick_step = _DEFAULT_TICK_STEP
        self._last_sent = ""
        self._report_text = ""
        self._dirty = False

        self._ctc_inputs = RowsModel(self)
        self._model_inputs = RowsModel(self)
        self._ctc_outputs = RowsModel(self)
        self._model_outputs = RowsModel(self)

        self._clock = SystemClock()
        self._clock.add_tick_listener(self._on_tick)
        self._clock.add_state_listener(self.runControlChanged.emit)
        self._driver = ClockDriver(self._clock, parent=self)
        self._driver.start()

        self._link.connectedChanged.connect(self._on_connected_changed)
        self._link.territoriesChanged.connect(self._on_territories)
        self._link.outputsChanged.connect(self._mark_dirty)
        self._timer = QTimer(self)
        self._timer.setInterval(_REFRESH_MS)
        self._timer.timeout.connect(self._refresh_if_dirty)
        self._timer.start()
        self._on_territories()

    def close(self) -> None:
        """Stop the clock and the link, before shutdown."""
        self._timer.stop()
        self._driver.stop()
        self._clock.pause()
        self._link.close()

    # -- connection and territories ----------------------------------

    @Slot()
    def _on_connected_changed(self) -> None:
        # Hold a running clock as soon as the Track Controller goes,
        # rather than spend ticks on steps that cannot reach it.
        if not self._link.connected:
            self._clock.pause()
        self.connectionChanged.emit()

    @Slot()
    def _on_territories(self) -> None:
        territories = {t.wayside_id: t for t in self._link.territories}
        known = {key for t in territories.values() for key in t.keys}
        for territory in territories.values():
            for block in territory.blocks:
                if block.key not in self._inputs:
                    self._inputs[block.key] = BlockInputs(
                        suggested_speed=speed_limit_whole_mps(
                            block.speed_limit_mps
                        )
                    )
        for key in list(self._inputs):
            if key not in known:
                del self._inputs[key]
        self._territories = territories
        if self._selected_wayside not in territories:
            self._selected_wayside = next(iter(territories), "")
            self._selected_block = ""
        self._fix_block()
        self._refresh()
        self.connectionChanged.emit()

    def _fix_block(self) -> None:
        labels = self._block_labels()
        if self._selected_block not in labels:
            self._selected_block = labels[0] if labels else ""
        self.selectionChanged.emit()

    def _territory(self) -> Territory | None:
        return self._territories.get(self._selected_wayside)

    def _block_labels(self) -> list[str]:
        territory = self._territory()
        return [] if territory is None else [k.label for k in territory.keys]

    def _key(self) -> BlockKey | None:
        territory = self._territory()
        if territory is None:
            return None
        for key in territory.keys:
            if key.label == self._selected_block:
                return key
        return None

    # -- edits ---------------------------------------------------------

    @Slot(str)
    def selectWayside(self, wayside_id: str) -> None:  # noqa: N802
        """Show another wayside's blocks."""
        if wayside_id in self._territories:
            self._selected_wayside = wayside_id
            self._selected_block = ""
            self._fix_block()
            self._refresh()

    @Slot(str)
    def selectBlock(self, label: str) -> None:  # noqa: N802
        """Show another block of the selected wayside."""
        if label in self._block_labels():
            self._selected_block = label
            self.selectionChanged.emit()
            self._refresh()

    @Slot(str, str, "QVariant")
    def setInput(  # noqa: N802
        self, group: str, name: str, value: Any
    ) -> None:
        """Change one input of the selected block; sent at next tick."""
        key = self._key()
        if key is None or name not in _GROUP_FIELDS.get(group, ()):
            return
        kind = _FIELD_KINDS[name]
        if kind == "bool":
            coerced: Any = bool(value)
        elif kind == "uint":
            try:
                coerced = int(float(value))
            except (TypeError, ValueError):
                return
            if coerced < 0:
                return
        else:
            coerced = str(value)
            if coerced not in _FIELD_OPTIONS[name]:
                return
        current = self._inputs[key]
        if getattr(current, name) == coerced:
            return
        self._inputs[key] = replace(current, **{name: coerced})
        self._edits += 1
        self._refresh()
        self.statusChanged.emit()

    @Slot(bool)
    def setMaintenance(self, active: bool) -> None:  # noqa: N802
        """Turn the CTC Office's maintenance mode on or off."""
        if active != self._maintenance:
            self._maintenance = bool(active)
            self._edits += 1
            self.selectionChanged.emit()
            self._refresh()
            self.statusChanged.emit()

    # -- run control -----------------------------------------------------

    @Slot()
    def sendInputs(self) -> None:  # noqa: N802
        """Send the inputs now: advance the clock one tick."""
        if self._require_connection():
            self._clock.tick()

    def _require_connection(self) -> bool:
        # A tick with no Track Controller would advance time that the
        # module never sees.
        if self._link.connected:
            return True
        self._set_error(
            self._link.refusal
            or "The Track Controller is not running. Start it first."
        )
        return False

    @Slot(bool)
    def setRunning(self, running: bool) -> None:  # noqa: N802
        """Run the clock in real time, or hold it."""
        if running and not self._require_connection():
            return
        if running:
            self._clock.resume()
        else:
            self._clock.pause()

    @Slot(int)
    def setSpeed(self, speed: int) -> None:  # noqa: N802
        """Run the clock at 1x or 10x."""
        if speed in ALLOWED_SPEEDS:
            self._clock.set_speed(speed)

    @Slot("QVariant")
    def setTickStep(self, ticks: Any) -> None:  # noqa: N802
        """Set how many ticks one Advance runs."""
        try:
            step = int(float(ticks))
        except (TypeError, ValueError):
            step = self._tick_step
        step = max(1, min(MAX_TICK_STEP, step))
        self._tick_step = step
        self.runControlChanged.emit()

    @Slot()
    def advanceTicks(self) -> None:  # noqa: N802
        """Tick the clock ``tickStep`` times, held or running."""
        if not self._require_connection():
            return
        for _ in range(self._tick_step):
            self._clock.tick()
            # A rejected step holds the clock and stops the run.
            if self._error or not self._link.connected:
                break

    @Slot()
    def resetModule(self) -> None:  # noqa: N802
        """Return the module, the clock and every input to the start."""
        try:
            self._link.reset()
        except TrackControllerError as error:
            self._set_error(str(error))
            return
        self._clock.reset()
        self._inputs = {}
        self._maintenance = False
        self._edits = 0
        self._last_sent = ""
        self._on_territories()
        self._set_error("")
        self.runControlChanged.emit()

    def _on_tick(self, sim_time_s: float, tick_s: float) -> None:
        # One clock tick: one step of the module with today's inputs.
        if not self._link.connected:
            self._clock.pause()
            return
        try:
            self._link.step(tick_s, self.build_inputs(sim_time_s))
        except TrackControllerError as error:
            self._clock.pause()
            self._set_error(str(error))
            return
        self._edits = 0
        self._last_sent = display.clock(sim_time_s)
        if self._error:
            self._set_error("")
        self._dirty = True

    def build_inputs(self, time_s: float) -> TrackControllerInputs:
        """Everything the stand-ins send this tick."""
        switch_keys = {
            switch.key
            for territory in self._territories.values()
            for switch in territory.switches
        }
        crossing_keys = {
            key
            for territory in self._territories.values()
            for key in territory.crossings
        }
        items = self._inputs.items()
        return TrackControllerInputs(
            time_s=time_s,
            ctc=CtcInputs(
                maintenance_mode=self._maintenance,
                closed_blocks=frozenset(k for k, v in items if v.block_closed),
                # The CTC Office sends switch commands only in maintenance.
                switch_commands=(
                    {
                        k: POSITIONS[v.switch_command]
                        for k, v in items
                        if k in switch_keys
                    }
                    if self._maintenance
                    else {}
                ),
                suggestions={
                    k: Suggestion(v.suggested_speed, v.suggested_authority)
                    for k, v in items
                    if v.suggestion
                },
            ),
            track_model=TrackModelInputs(
                occupied_blocks=frozenset(
                    k for k, v in items if v.block_occupancy
                ),
                failures={
                    k: FAILURES[v.track_failure]
                    for k, v in items
                    if FAILURES[v.track_failure] is not None
                },
                switch_positions={
                    k: POSITIONS[v.switch_state]
                    for k, v in items
                    if k in switch_keys
                },
                crossings_active={
                    k: GATES[v.crossing_state]
                    for k, v in items
                    if k in crossing_keys
                },
                signal_aspects={
                    k: ASPECTS[v.signal_aspect]
                    for k, v in items
                    if k in switch_keys
                },
            ),
        )

    def _set_error(self, message: str) -> None:
        self._error = message
        self.statusChanged.emit()

    # -- tables ----------------------------------------------------------

    @Slot()
    def _mark_dirty(self) -> None:
        self._dirty = True

    @Slot()
    def _refresh_if_dirty(self) -> None:
        if self._dirty:
            self._refresh()
            self.runControlChanged.emit()
            self.statusChanged.emit()

    def _refresh(self) -> None:
        self._dirty = False
        key = self._key()
        territory = self._territory()
        if key is None or territory is None:
            for model in (
                self._ctc_inputs, self._model_inputs, self._ctc_outputs,
                self._model_outputs,
            ):
                model.set_rows([])
            return
        has_switch = any(s.key == key for s in territory.switches)
        has_crossing = key in territory.crossings
        inputs = self._inputs[key]
        applies = {
            "suggested_speed": inputs.suggestion,
            "suggested_authority": inputs.suggestion,
            "switch_command": has_switch,
            "switch_state": has_switch,
            "crossing_state": has_crossing,
            "signal_aspect": has_switch,
        }
        for group, model in (
            (CTC_GROUP, self._ctc_inputs),
            (TRACK_MODEL_GROUP, self._model_inputs),
        ):
            model.set_rows([
                {
                    "group": group,
                    "name": name,
                    "kind": _FIELD_KINDS[name],
                    "unit": _UNITS.get(name, ""),
                    "value": getattr(inputs, name),
                    "options": _FIELD_OPTIONS.get(name, []),
                    "applies": applies.get(name, True),
                }
                for name in _GROUP_FIELDS[group]
            ])
        self._fill_outputs(key, territory, has_switch, has_crossing)

    def _fill_outputs(
        self,
        key: BlockKey,
        territory: Territory,
        has_switch: bool,
        has_crossing: bool,
    ) -> None:
        outputs: TrackControllerOutputs | None = self._link.outputs
        report = None
        if outputs is not None:
            report = next(
                (
                    r for r in outputs.ctc_reports
                    if r.wayside_id == territory.wayside_id
                ),
                None,
            )
        entry = None if report is None else report.blocks.get(key)
        model = None if outputs is None else outputs.track_model
        circuit = None if model is None else model.track_circuits.get(key)

        def row(name: str, kind: str, value: Any, applies: bool = True,
                unit: str = "") -> dict[str, Any]:
            return {
                "name": name, "kind": kind, "unit": unit,
                "value": value if applies else None, "options": [],
                "applies": applies,
            }

        self._ctc_outputs.set_rows([
            row("block_occupancy", "bool",
                None if entry is None else entry.occupied),
            row("switch_state", "enum",
                None if entry is None
                else _label(POSITIONS, entry.switch_position) or None,
                has_switch),
            row("crossing_state", "enum",
                None if entry is None
                else _label(GATES, entry.crossing_active) or None,
                has_crossing),
            row("signal_state", "enum",
                None if entry is None
                else _label(ASPECTS, entry.signal_aspect) or None,
                has_switch),
            row("track_failure", "enum",
                None if entry is None else _label(FAILURES, entry.failure)),
        ])
        self._model_outputs.set_rows([
            row("commanded_speed", "uint",
                None if circuit is None else circuit.speed_mps, unit="m/s"),
            row("commanded_authority", "uint",
                None if circuit is None else circuit.authority_blocks,
                unit="blocks"),
            row("switch_position_command", "enum",
                None if model is None
                else _label(POSITIONS, model.switch_commands.get(key)) or None,
                has_switch),
            row("crossing_command", "enum",
                None if model is None
                else _label(GATES, model.crossing_commands.get(key)) or None,
                has_crossing),
            row("signal_light_command", "enum",
                None if model is None
                else _label(ASPECTS, model.signal_commands.get(key)) or None,
                has_switch),
        ])
        self._report_text = (
            "" if report is None
            else f"Report sent {display.clock(report.sent_at_s)}"
        )

    # -- properties --------------------------------------------------------

    @Property(bool, notify=connectionChanged)
    def connected(self) -> bool:
        """Whether a Track Controller is serving this test UI."""
        return self._link.connected

    @Property(str, notify=connectionChanged)
    def refusal(self) -> str:
        """Why the Track Controller refused this test UI, or ""."""
        return self._link.refusal

    @Property(str, notify=connectionChanged)
    def line(self) -> str:
        """The line the Track Controller runs, or ""."""
        return self._link.line or ""

    @Property("QVariantList", notify=connectionChanged)
    def waysides(self) -> list[str]:
        """Loaded wayside IDs."""
        return list(self._territories)

    @Property(str, notify=selectionChanged)
    def selectedWayside(self) -> str:  # noqa: N802
        """The wayside whose blocks are shown."""
        return self._selected_wayside

    @Property("QVariantList", notify=selectionChanged)
    def blocks(self) -> list[str]:
        """Block labels of the selected wayside."""
        return self._block_labels()

    @Property(str, notify=selectionChanged)
    def selectedBlock(self) -> str:  # noqa: N802
        """The block all four tables show."""
        return self._selected_block

    @Property(bool, notify=selectionChanged)
    def maintenance(self) -> bool:
        """The CTC Office's maintenance mode, as sent."""
        return self._maintenance

    @Property(QObject, constant=True)
    def ctcInputs(self) -> RowsModel:  # noqa: N802
        """What the CTC Office sends for the selected block."""
        return self._ctc_inputs

    @Property(QObject, constant=True)
    def trackModelInputs(self) -> RowsModel:  # noqa: N802
        """What the Track Model sends for the selected block."""
        return self._model_inputs

    @Property(QObject, constant=True)
    def ctcOutputs(self) -> RowsModel:  # noqa: N802
        """What the wayside reports to the CTC Office for the block."""
        return self._ctc_outputs

    @Property(QObject, constant=True)
    def trackModelOutputs(self) -> RowsModel:  # noqa: N802
        """What the wayside drives onto the Track Model for the block."""
        return self._model_outputs

    @Property(str, notify=statusChanged)
    def reportText(self) -> str:  # noqa: N802
        """When the selected wayside last reported to the CTC Office."""
        return getattr(self, "_report_text", "")

    @Property(str, notify=statusChanged)
    def errorText(self) -> str:  # noqa: N802
        """The last rejected step or link failure, or ""."""
        return self._error

    @Property(int, notify=statusChanged)
    def pendingEdits(self) -> int:  # noqa: N802
        """Edits made since the last tick sent the inputs."""
        return self._edits

    @Property(bool, notify=runControlChanged)
    def running(self) -> bool:
        """Whether the clock runs in real time."""
        return not self._clock.is_paused

    @Property(int, notify=runControlChanged)
    def speed(self) -> int:
        """Clock speed multiplier: 1 or 10."""
        return self._clock.speed

    @Property(int, notify=runControlChanged)
    def tick(self) -> int:
        """Ticks since the last reset."""
        return self._clock.tick_count

    @Property(float, notify=runControlChanged)
    def dt(self) -> float:
        """Seconds per tick."""
        return self._clock.tick_s

    @Property(str, notify=runControlChanged)
    def clockText(self) -> str:  # noqa: N802
        """Simulated time of day."""
        return self._clock.format_time_of_day()

    @Property(str, notify=runControlChanged)
    def lastSent(self) -> str:  # noqa: N802
        """Simulated time the inputs were last sent, or ""."""
        return self._last_sent

    @Property(int, notify=runControlChanged)
    def tickStep(self) -> int:  # noqa: N802
        """Ticks one Advance runs."""
        return self._tick_step
