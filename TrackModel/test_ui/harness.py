"""Test UI state: stands in for the Track Controller, the Train Model and
the clock, and drives the Track Model only through the link.

Device IDs are learned from the outputs the Track Model pushes when the
link connects; nothing here reads the module's internals. Values are in
backend units (m, m/s, deg), because this page probes the interface,
except the ambient temperature, which is entered in degrees Fahrenheit
and converted before sending.

Acting as the Train Model, the page can move its fake trains: each tick
it adds speed x dt to every train's offset, and when the feed names a new
block it moves the train there with offset reset to 0, as the Train
Model would on a polarity change.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from test_link.link import LinkClient
from test_ui.block_filter import (
    filter_blocks,
    lines_of,
    parse_range,
    sections_of,
    short_name,
)
from track_model.interface import (
    BlockEdit,
    SignalAspect,
    SwitchPosition,
    TrackControllerCommands,
    TrackFailure,
    TrackModelInputs,
    TrackModelOutputs,
    TrainReport,
)

DT_S = 0.100
REAL_TIME_MS = 100
FAST_MS = 10                      # 10x: same dt, ten times the tick rate
#: The line shown first: the main line in use.
DEFAULT_LINE = "GREEN"
ALL_SECTIONS = "All"
SWITCH_OPTIONS = [p.name for p in SwitchPosition]
ASPECT_OPTIONS = [a.name for a in SignalAspect]
FAILURE_OPTIONS = [f.name for f in TrackFailure]


def f_to_c(temp_f: float) -> float:
    """Convert degrees Fahrenheit to Celsius."""
    return (temp_f - 32.0) * 5.0 / 9.0


def _row(name: str, kind: str, value: Any, unit: str = "",
         options: list[str] | None = None,
         row_id: str | None = None) -> dict[str, Any]:
    # One SignalRow model entry. "name" is the short label shown; "id"
    # is what an edit is sent back as, and what tests look rows up by.
    return {"id": row_id or name, "name": name, "kind": kind,
            "value": value, "unit": unit, "options": options or []}


@dataclass(slots=True)
class _FakeTrain:
    """One train, as the Train Model would report it."""

    block_id: str
    offset_m: float = 0.0
    speed_mps: float = 0.0
    block_changed: bool = False
    capacity: int = 222


class TrackModelTestHarness(QObject):
    """Inputs, read-back outputs and run control for the test UI."""

    inputsChanged = Signal()
    outputsChanged = Signal()
    linkChanged = Signal()
    runControlChanged = Signal()
    filterChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # Block filter: which line's blocks and devices the page shows.
        self._line = ""
        self._section = ""
        self._range_text = ""
        self._range: tuple[int, int] | None = None
        self._client = LinkClient(self)
        self._client.outputsReceived.connect(self._on_outputs)
        self._client.errorReceived.connect(self._on_error)
        self._client.connectionChanged.connect(
            lambda _c: self.linkChanged.emit()
        )
        self._timer = QTimer(self)
        self._timer.setInterval(REAL_TIME_MS)
        self._timer.timeout.connect(self.stepOnce)
        self._outputs: TrackModelOutputs | None = None
        self._error = ""
        self._tick = 0
        self._fast = False
        self._act_as_train_model = True
        self._awaiting_reply = False
        self._last_seen: dict[str, str] = {}
        self._sales_total: dict[str, int] = {}
        self._clear_inputs()
        self._client.connect_to_server()

    # ------------------------------------------------------------------ #
    # Link and run control
    # ------------------------------------------------------------------ #

    @Property(bool, notify=linkChanged)
    def connected(self) -> bool:
        """Whether the Track Model process answered."""
        return self._client.connected

    @Property(str, notify=outputsChanged)
    def lastError(self) -> str:
        """The last rejection from the Track Model, or empty."""
        return self._error

    @Property(bool, notify=runControlChanged)
    def running(self) -> bool:
        """Whether the clock is running."""
        return self._timer.isActive()

    @Property(bool, notify=runControlChanged)
    def fast(self) -> bool:
        """Whether the clock runs at 10x."""
        return self._fast

    @Property(str, notify=runControlChanged)
    def elapsed(self) -> str:
        """Simulated time sent so far, as hh:mm:ss."""
        total = int(self._tick * DT_S)
        hours, rest = divmod(total, 3600)
        minutes, seconds = divmod(rest, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @Property(int, notify=runControlChanged)
    def tick(self) -> int:
        """Ticks sent since start or reset."""
        return self._tick

    @Property(float, constant=True)
    def dt(self) -> float:
        """Seconds per tick. Fixed (D006)."""
        return DT_S

    @Property(bool, notify=runControlChanged)
    def actAsTrainModel(self) -> bool:
        """Whether this page moves its trains like the Train Model."""
        return self._act_as_train_model

    @Slot(bool)
    def setActAsTrainModel(self, on: bool) -> None:
        """Turn simulated train motion on or off."""
        self._act_as_train_model = on
        self.runControlChanged.emit()

    @Slot(bool)
    def setRunning(self, running: bool) -> None:
        """Run or hold the clock. Holding never changes dt."""
        if running:
            self._timer.start()
        else:
            self._timer.stop()
        self.runControlChanged.emit()

    @Slot(bool)
    def setFast(self, fast: bool) -> None:
        """Switch between 1x and 10x tick rate."""
        self._fast = fast
        self._timer.setInterval(FAST_MS if fast else REAL_TIME_MS)
        self.runControlChanged.emit()

    def close(self) -> None:
        """Stop the clock and drop the link. Call before deleting."""
        self._timer.stop()
        self._client.close()

    @Slot()
    def stepOnce(self) -> None:
        """Send one tick of inputs."""
        if self._awaiting_reply:
            return  # The last tick has not come back yet.
        if self._act_as_train_model:
            for train in self._trains.values():
                train.offset_m += train.speed_mps * DT_S
        if self._client.step(DT_S, self._inputs()):
            self._awaiting_reply = True
            self._tick += 1
            self.runControlChanged.emit()

    # ------------------------------------------------------------------ #
    # Test-only commands
    # ------------------------------------------------------------------ #

    @Slot()
    def resetModule(self) -> None:
        """Reset the Track Model and every input on this page."""
        self.setRunning(False)
        # Forget the pre-reset outputs, so device commands are relearned
        # from the reset reply rather than from stale positions.
        self._outputs = None
        self._clear_inputs()
        self._tick = 0
        self._last_seen.clear()
        self._sales_total.clear()
        self._client.reset()
        self.inputsChanged.emit()
        self.runControlChanged.emit()

    @Slot(str, str)
    def setBlockFailure(self, block_id: str, failure: str) -> None:
        """Test-only: inject or clear a failure on a block."""
        if block_id and failure in FAILURE_OPTIONS:
            self._client.set_block_failure(block_id, TrackFailure[failure])

    @Slot(str, "QVariant", "QVariant", "QVariant", "QVariant")
    def editBlock(self, block_id: str, length_m: Any, grade_deg: Any,
                  limit_mps: Any, elevation_m: Any) -> None:
        """Test-only: override a block's stats; blank fields unchanged."""
        def number(value: Any) -> float | None:
            text = str(value).strip() if value is not None else ""
            return float(text) if text else None

        try:
            edit = BlockEdit(number(length_m), number(grade_deg),
                             number(limit_mps), number(elevation_m))
        except ValueError:
            self._on_error("edit_block: not a number")
            return
        self._client.edit_block(block_id, edit)

    # ------------------------------------------------------------------ #
    # Known IDs (learned from the outputs)
    # ------------------------------------------------------------------ #

    @Property(list, notify=outputsChanged)
    def blocks(self) -> list[str]:
        """Every block ID the Track Model reports."""
        return self._block_ids()

    @Property(list, constant=True)
    def failureOptions(self) -> list[str]:
        """Failure modes for the test-only failure control."""
        return list(FAILURE_OPTIONS)

    # ------------------------------------------------------------------ #
    # Block filter
    # ------------------------------------------------------------------ #

    @Property(list, notify=filterChanged)
    def lines(self) -> list[str]:
        """Every line the Track Model reports."""
        return lines_of(self._block_ids())

    @Property(str, notify=filterChanged)
    def line(self) -> str:
        """The line whose blocks and devices are shown."""
        return self._line

    @Property(list, notify=filterChanged)
    def sections(self) -> list[str]:
        """"All", then the shown line's sections."""
        return [ALL_SECTIONS, *sections_of(self._block_ids(), self._line)]

    @Property(str, notify=filterChanged)
    def section(self) -> str:
        """The section filter, or "All"."""
        return self._section or ALL_SECTIONS

    @Property(str, notify=filterChanged)
    def rangeText(self) -> str:
        """The block-number range filter as typed, e.g. "5-20"."""
        return self._range_text

    @Property(list, notify=filterChanged)
    def filteredBlocks(self) -> list[str]:
        """Block IDs that pass the line, section and range filters."""
        return self._filtered()

    @Property(str, notify=filterChanged)
    def filterSummary(self) -> str:
        """How many blocks the filter lets through."""
        shown = len(self._filtered())
        total = len(filter_blocks(self._block_ids(), self._line))
        return f"{shown} of {total} {self._line} blocks"

    @Slot(str)
    def setLine(self, line: str) -> None:
        """Show another line; its section and range filters reset."""
        if line != self._line:
            self._line = line
            self._section = ""
            self._range_text, self._range = "", None
            self._filter_changed()

    @Slot(str)
    def setSection(self, section: str) -> None:
        """Show one section of the line, or "All"."""
        self._section = "" if section == ALL_SECTIONS else section
        self._filter_changed()

    @Slot(str)
    def setRange(self, text: str) -> None:
        """Show block numbers in a range: "12", "5-20", or blank."""
        try:
            self._range = parse_range(text)
        except ValueError as error:
            self._on_error(str(error))
            return
        self._range_text = text.strip()
        self._filter_changed()

    @Slot()
    def clearFilter(self) -> None:
        """Show the whole line again."""
        self._section = ""
        self._range_text, self._range = "", None
        self._filter_changed()

    # ------------------------------------------------------------------ #
    # Inputs
    # ------------------------------------------------------------------ #

    @Property(list, notify=inputsChanged)
    def trains(self) -> list[str]:
        """Fake train IDs, in creation order."""
        return list(self._trains)

    @Property(str, notify=inputsChanged)
    def selectedTrain(self) -> str:
        """The train the per-train rows apply to."""
        return self._selected_train

    @Property(str, notify=inputsChanged)
    def selectedBlock(self) -> str:
        """The block the per-block rows apply to."""
        return self._selected_block

    @Slot(str)
    def selectTrain(self, train_id: str) -> None:
        """Address the per-train rows to another train."""
        self._selected_train = train_id
        self.inputsChanged.emit()
        self.outputsChanged.emit()

    @Slot(str)
    def selectBlock(self, block_id: str) -> None:
        """Address the per-block rows to another block."""
        self._selected_block = block_id
        self.inputsChanged.emit()

    @Slot(str, str)
    def addTrain(self, train_id: str, block_id: str) -> None:
        """Put a new train on the track at the start of a block."""
        train_id = train_id.strip()
        if not train_id or train_id in self._trains or not block_id:
            self._on_error("add train: need a new ID and a block")
            return
        self._trains[train_id] = _FakeTrain(block_id)
        self._selected_train = train_id
        self.inputsChanged.emit()

    @Slot()
    def removeTrain(self) -> None:
        """Take the selected train off the track."""
        self._trains.pop(self._selected_train, None)
        self._selected_train = next(iter(self._trains), "")
        self.inputsChanged.emit()

    @Property(list, notify=inputsChanged)
    def trainRows(self) -> list[dict[str, Any]]:
        """Train Model report for the selected train."""
        train = self._trains.get(self._selected_train)
        if train is None:
            return []
        # Short labels; the ids are the TrainReport field names.
        return [
            _row("block", "string", train.block_id, row_id="block_id"),
            _row("offset", "float", round(train.offset_m, 2), "m",
                 row_id="offset_m"),
            _row("speed", "float", train.speed_mps, "m/s",
                 row_id="actual_speed_mps"),
            _row("changed", "bool", train.block_changed,
                 row_id="block_changed"),
            _row("capacity", "uint", train.capacity,
                 row_id="passenger_capacity"),
        ]

    @Property(list, notify=inputsChanged)
    def blockRows(self) -> list[dict[str, Any]]:
        """Track Controller commands for the selected block."""
        if not self._selected_block:
            return []
        return [
            _row("speed", "uint", self._speed.get(self._selected_block, 0),
                 "m/s", row_id="commanded_speed_mps"),
            _row("authority", "string",
                 self._authority.get(self._selected_block, ""),
                 row_id="authority_block_id"),
        ]

    @Property(list, notify=inputsChanged)
    def switchRows(self) -> list[dict[str, Any]]:
        """Switch commands on the line on show, one row per switch."""
        return [_row(short_name(k), "enum", v, options=SWITCH_OPTIONS,
                     row_id=k)
                for k, v in self._switches.items() if self._on_line(k)]

    @Property(list, notify=inputsChanged)
    def signalRows(self) -> list[dict[str, Any]]:
        """Signal commands on the line on show, one row per light."""
        return [_row(short_name(k), "enum", v, options=ASPECT_OPTIONS,
                     row_id=k)
                for k, v in self._signals.items() if self._on_line(k)]

    @Property(list, notify=inputsChanged)
    def crossingRows(self) -> list[dict[str, Any]]:
        """Gate commands on the line on show (true = gate closed)."""
        return [_row(short_name(k), "bool", v, row_id=k)
                for k, v in self._crossings.items() if self._on_line(k)]

    @Property(list, notify=inputsChanged)
    def heaterRows(self) -> list[dict[str, Any]]:
        """Heater commands, one row per zone."""
        # Heaters are per section: "heat B" is section B of the line.
        return [_row(f"heat {short_name(k)}", "bool", v, row_id=k)
                for k, v in self._heaters.items() if self._on_line(k)]

    @Property(list, notify=inputsChanged)
    def environmentRows(self) -> list[dict[str, Any]]:
        """Environment input; entered in Fahrenheit."""
        return [_row("ambient", "float", self._ambient_f, "°F")]

    @Slot(str, str, "QVariant")
    def setInput(self, group: str, name: str, value: Any) -> None:
        """Write one input row. Sent with the next tick."""
        try:
            self._set_input(group, name, value)
        except (KeyError, ValueError) as error:
            self._on_error(f"{group}.{name}: {error}")
            return
        self.inputsChanged.emit()

    # ------------------------------------------------------------------ #
    # Outputs
    # ------------------------------------------------------------------ #

    @Property(list, notify=outputsChanged)
    def controllerSummaryRows(self) -> list[dict[str, Any]]:
        """Track Controller read-back that is not per device.

        Occupancy and failures cover the line on show, with the line
        dropped from each block ID.
        """
        if self._outputs is None:
            return []
        out = self._outputs.controller
        occupied = [short_name(b) for b, o in out.block_occupancy.items()
                    if o and self._on_line(b)]
        failed = [f"{short_name(b)} {f.name}"
                  for b, f in out.failure_status.items()
                  if f is not TrackFailure.NONE and self._on_line(b)]
        sold = [f"{s}+{n}" for s, n in out.ticket_sales.items() if n]
        heaters_on = [short_name(s) for s, on in out.heater_states.items()
                      if on and self._on_line(s)]
        total = sum(self._sales_total.values())
        # Track temperature of the selected block's section.
        section = self._selected_block.split("-", 1)[0]
        temp = out.track_temp_c.get(section)
        return [
            _row("occupied", "string", ", ".join(occupied) or "none",
                 row_id="block_occupancy"),
            _row("failures", "string", ", ".join(failed) or "none",
                 row_id="failure_status"),
            _row("heaters on", "string", ", ".join(heaters_on) or "none",
                 row_id="heater_states"),
            _row("trk temp", "string", "none", row_id="track_temp_c")
            if temp is None else
            _row("trk temp", "float", round(temp, 2), "°C",
                 row_id="track_temp_c"),
            _row("sold now", "string", ", ".join(sold) or "none",
                 row_id="ticket_sales"),
            _row("sold total", "int", total, row_id="ticket_sales_total"),
        ]

    @Property(list, notify=outputsChanged)
    def deviceStateRows(self) -> list[dict[str, Any]]:
        """Switch, signal and gate read-back on the line on show."""
        if self._outputs is None:
            return []
        out = self._outputs.controller
        rows = [_row(f"sw {short_name(k)}", "string", v.name,
                     row_id=f"switch {k}")
                for k, v in out.switch_states.items() if self._on_line(k)]
        rows += [_row(f"sig {short_name(k)}", "string", v.name,
                      row_id=f"signal {k}")
                 for k, v in out.signal_states.items() if self._on_line(k)]
        rows += [_row(f"gate {short_name(k)}", "bool", v,
                      row_id=f"crossing {k}")
                 for k, v in out.crossing_states.items()
                 if self._on_line(k)]
        return rows

    @Property(list, notify=outputsChanged)
    def feedRows(self) -> list[dict[str, Any]]:
        """Train Model feed for the selected train."""
        if self._outputs is None:
            return []
        feed = self._outputs.train_feeds.get(self._selected_train)
        if feed is None:
            return []
        info, sig, beacon = feed.track_info, feed.track_signal, feed.beacon
        beacon_text = "none" if beacon is None else (
            f"{beacon.station_name} / {beacon.platform_side or '?'}"
            f"{' / underground' if beacon.underground else ''}"
        )
        # Short labels; the ids are the full field paths.
        return [
            _row("block", "string", info.block_id,
                 row_id="track_info.block_id"),
            _row("grade", "float", round(info.grade_deg, 4), "deg",
                 row_id="track_info.grade_deg"),
            _row("elevation", "float", info.elevation_m, "m",
                 row_id="track_info.elevation_m"),
            _row("limit", "float", round(info.speed_limit_mps, 3), "m/s",
                 row_id="track_info.speed_limit_mps"),
            _row("polarity", "bool", info.polarity,
                 row_id="track_info.polarity"),
            _row("station", "string", info.station_name or "none",
                 row_id="track_info.station_name"),
            _row("cmd speed", "int", sig.commanded_speed_mps, "m/s",
                 row_id="track_signal.commanded_speed_mps"),
            _row("authority", "string", sig.authority_block_id or "none",
                 row_id="track_signal.authority_block_id"),
            _row("beacon", "string", beacon_text),
            _row("boarded", "uint", feed.passengers_boarded,
                 row_id="passengers_boarded"),
        ]

    @Property(list, notify=outputsChanged)
    def trainControllerRows(self) -> list[dict[str, Any]]:
        """Signal seen by the selected train: this tick, and last seen."""
        if self._outputs is None or not self._selected_train:
            return []
        seen = self._outputs.signal_seen.get(self._selected_train)
        return [
            _row("seen now", "string",
                 "none" if seen is None else seen.name,
                 row_id="signal_seen"),
            _row("last seen", "string",
                 self._last_seen.get(self._selected_train, "none"),
                 row_id="last_seen"),
        ]

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _clear_inputs(self) -> None:
        # Every input back to its default; devices refill on next outputs.
        self._trains: dict[str, _FakeTrain] = {}
        # Trains the track has carried at least once.
        self._on_track: set[str] = set()
        self._selected_train = ""
        self._selected_block = ""
        self._speed: dict[str, int] = {}
        self._authority: dict[str, str] = {}
        self._switches: dict[str, str] = {}
        self._signals: dict[str, str] = {}
        self._crossings: dict[str, bool] = {}
        self._heaters: dict[str, bool] = {}       # by section
        self._ambient_f = 50.0
        if self._outputs is not None:
            self._learn_devices(self._outputs)

    def _learn_devices(self, outputs: TrackModelOutputs) -> None:
        # Fill device commands from the read-back, the first time only.
        out = outputs.controller
        if not self._switches:
            self._switches = {k: v.name for k, v in out.switch_states.items()}
        if not self._signals:
            self._signals = {k: v.name for k, v in out.signal_states.items()}
        if not self._crossings:
            self._crossings = dict(out.crossing_states)
        if not self._heaters:
            self._heaters = dict(out.heater_states)
        lines = lines_of(out.block_occupancy)
        if self._line not in lines and lines:
            self._line = DEFAULT_LINE if DEFAULT_LINE in lines else lines[0]
            self.filterChanged.emit()
        if self._selected_block not in self._filtered():
            self._selected_block = next(iter(self._filtered()), "")

    def _block_ids(self) -> list[str]:
        # Every block the Track Model reports, in layout order.
        if self._outputs is None:
            return []
        return list(self._outputs.controller.block_occupancy)

    def _filtered(self) -> list[str]:
        # The blocks passing the line, section and range filters.
        return filter_blocks(self._block_ids(), self._line, self._section,
                             self._range)

    def _on_line(self, device_id: str) -> bool:
        # Whether a device or block ID belongs to the line on show.
        return device_id.startswith(self._line + " ")

    def _filter_changed(self) -> None:
        # Keep the selected block inside the filter, then redraw.
        if self._selected_block not in self._filtered():
            self._selected_block = next(iter(self._filtered()), "")
        self.filterChanged.emit()
        self.inputsChanged.emit()
        self.outputsChanged.emit()

    def _set_input(self, group: str, name: str, value: Any) -> None:
        # Coerce and store one edited row.
        if group == "train":
            self._set_train_field(name, value)
        elif group == "block":
            self._set_block_field(name, value)
        elif group == "switch":
            self._switches[name] = SwitchPosition[str(value)].name
        elif group == "signal":
            self._signals[name] = SignalAspect[str(value)].name
        elif group == "crossing":
            self._crossings[name] = bool(value)
        elif group == "heater":
            self._heaters[name] = bool(value)
        elif group == "env":
            self._ambient_f = float(value)
        else:
            raise KeyError(group)

    def _set_train_field(self, name: str, value: Any) -> None:
        # One field of the selected train's report.
        train = self._trains[self._selected_train]
        if name == "block_id":
            train.block_id = str(value)
        elif name == "offset_m":
            train.offset_m = float(value)
        elif name == "actual_speed_mps":
            train.speed_mps = float(value)
        elif name == "block_changed":
            train.block_changed = bool(value)
        elif name == "passenger_capacity":
            train.capacity = max(0, int(float(value)))
        else:
            raise KeyError(name)

    def _set_block_field(self, name: str, value: Any) -> None:
        # One Track Controller command for the selected block.
        block_id = self._selected_block
        if name == "commanded_speed_mps":
            self._speed[block_id] = int(value)
        elif name == "authority_block_id":
            text = str(value).strip()
            if text:
                self._authority[block_id] = text
            else:
                self._authority.pop(block_id, None)
        else:
            raise KeyError(name)

    def _inputs(self) -> TrackModelInputs:
        # One tick of input from everything on this page.
        return TrackModelInputs(
            controller=TrackControllerCommands(
                commanded_speed_mps=dict(self._speed),
                commanded_authority=dict(self._authority),
                switch_commands={
                    k: SwitchPosition[v] for k, v in self._switches.items()
                },
                crossing_commands=dict(self._crossings),
                signal_commands={
                    k: SignalAspect[v] for k, v in self._signals.items()
                },
                heater_commands=dict(self._heaters),
            ),
            trains={
                train_id: TrainReport(
                    block_id=t.block_id,
                    offset_m=t.offset_m,
                    actual_speed_mps=t.speed_mps,
                    block_changed=t.block_changed,
                    passenger_capacity=t.capacity,
                )
                for train_id, t in self._trains.items()
            },
            ambient_temp_c=f_to_c(self._ambient_f),
        )

    def _on_outputs(self, outputs: TrackModelOutputs) -> None:
        # A reply or a pushed event: show it, and follow the feed.
        self._awaiting_reply = False
        self._outputs = outputs
        self._error = ""
        learned = not self._switches
        self._learn_devices(outputs)
        self._follow_feeds(outputs.train_feeds)
        for train_id, seen in outputs.signal_seen.items():
            if seen is not None:
                self._last_seen[train_id] = seen.name
        for station, sold in outputs.controller.ticket_sales.items():
            self._sales_total[station] = (
                self._sales_total.get(station, 0) + sold
            )
        if learned:
            self.filterChanged.emit()
        if learned or self._act_as_train_model:
            self.inputsChanged.emit()
        self.outputsChanged.emit()

    def _follow_feeds(self, feeds: Mapping[str, Any]) -> None:
        # Acting as the Train Model: take the block the track reports.
        for train_id in list(self._trains):
            train = self._trains[train_id]
            feed = feeds.get(train_id)
            train.block_changed = False
            if feed is None:
                if train_id in self._on_track and self._act_as_train_model:
                    # The track no longer carries it: it ran into the yard.
                    del self._trains[train_id]
                    self._on_track.discard(train_id)
                continue
            self._on_track.add(train_id)
            new_block = feed.track_info.block_id
            if self._act_as_train_model and new_block != train.block_id:
                train.block_id = new_block
                train.offset_m = 0.0
                train.block_changed = True
        if self._selected_train not in self._trains:
            self._selected_train = next(iter(self._trains), "")

    def _on_error(self, message: str) -> None:
        # Show a rejection; the clock keeps its state.
        self._awaiting_reply = False
        self._error = message
        self.outputsChanged.emit()
