"""The CTC Office module as hosted by the CTC Office window.

The window owns the one live CTC module. It also serves that module to
the CTC test UI over ``ctc.socket_link``, so both windows act on the
same state:

- Until the central harness exists, the window's simulation clock steps
  the module every tick with the latest Track Controller and Track Model
  inputs. The test UI replaces those inputs on Send.
- Dispatcher actions taken in the window (dispatch, block closures,
  switch positions, the operating mode and the clock speed) go straight
  to the module and are pushed to any connected test UI.
- Actions the test UI sends reach the window through the link server's
  ``changed`` signal, and every panel re-reads the module.

Values cross into QML in display units (mph); the module stays in SI.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from ctc.interface import (
    CtcInputs,
    CtcOffice,
    CtcSnapshot,
    DispatchOrder,
    TrackModelInputs,
    TrainSuggestion,
)
from ctc.model import CtcError, StubCtcOffice
from ctc.schedule import ScheduleError, load_schedule
from ctc.socket_link import CtcLinkServer
from ctc.track_layout import Line, load_layout
from ctc_ui.display import (
    MPS_TO_MPH,
    TimeOfDayError,
    block_key,
    format_time_of_day,
    parse_time_of_day,
)

if TYPE_CHECKING:
    from ctc_ui.sim_clock import SimulationClockBridge

#: The shared clock's fast-forward speed; clock_speedup means this.
SPEEDUP_FACTOR = 10

#: Shown for a value that is not known yet.
NO_VALUE = "—"

_FAILURE_LABELS = {
    "broken_rail": "Broken rail",
    "track_circuit": "Circuit failure",
    "power": "Power failure",
}

_SWITCH_POSITIONS = ("normal", "reverse")


#: Hours of ticket sales the throughput history shows.
HISTORY_HOURS = 12


def _hour(sim_time_s: float) -> int:
    """The simulated clock hour a time falls in, counted from midnight
    of the first simulated day."""
    return int(sim_time_s // 3600)


def _offset(seconds: int) -> str:
    """``+m:ss`` after the schedule start."""
    return f"+{seconds // 60}:{seconds % 60:02d}"


def _mph(speed_mps: float) -> str:
    return f"{speed_mps * MPS_TO_MPH:.1f}"


def _block_number(block_id: str) -> tuple[int, str]:
    # Sort blocks by number where the ID is a number, for display only.
    return (int(block_id) if block_id.isdigit() else -1, block_id)


class CtcHost(QObject):
    """Bindable CTC module for ``Main.qml``, served to the test UI."""

    #: Anything the panels show changed: re-read the bound properties.
    stateChanged = Signal()
    #: Simulated time moved on (once per simulated second), or the
    #: module changed: throughput needs re-reading.
    clockChanged = Signal()
    maintenanceModeChanged = Signal()
    clockSpeedupChanged = Signal()
    scheduleChanged = Signal()

    def __init__(self, module: CtcOffice | None = None,
                 layout: Mapping[str, Line] | None = None,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._layout = dict(load_layout() if layout is None else layout)
        self._module = (module if module is not None
                        else StubCtcOffice(layout=self._layout))
        self._server = CtcLinkServer(self._module, parent=self,
                                     set_inputs=self._receive_inputs)
        self._server.changed.connect(self._refresh)
        # The latest Track Controller and Track Model inputs, stepped
        # with on every tick.
        self._inputs = CtcInputs()
        self._schedule_file = ""
        self._schedule_error = ""
        self._last_state: object = None
        self._revision = 0
        self._last_second = -1
        # Tickets sold per (simulated clock hour, line), for the history
        # chart. Hours count from midnight of the first simulated day.
        self._hourly_sales: dict[tuple[int, str], int] = {}
        self._first_hour = 0
        self._current_hour = 0

    def start(self) -> None:
        """Start serving the test UI. The window works either way."""
        if not self._server.listen():
            print("CTC test UI link unavailable: could not listen.",
                  file=sys.stderr)

    def stop(self) -> None:
        """Stop serving the test UI; call before the app shuts down."""
        self._server.close()

    # -- Clock --------------------------------------------------------

    def follow_clock(self, clock: SimulationClockBridge) -> None:
        """Step the module on the window's clock, and keep
        clock_speedup in step with its speed."""
        def apply_speed() -> None:
            # speedChanged also fires on pause; repeats are ignored.
            self.setClockSpeedup(clock.speed == SPEEDUP_FACTOR)
        clock.speedChanged.connect(apply_speed)
        apply_speed()
        self._first_hour = self._current_hour = _hour(clock.clock.sim_time_s)
        clock.clock.add_tick_listener(self._on_tick)

    def _on_tick(self, sim_time_s: float, tick_s: float) -> None:
        try:
            self._module.step(tick_s, self._inputs)
        except CtcError as error:
            # Inputs are validated on arrival, so this is a module bug.
            print(f"CTC step failed: {error}", file=sys.stderr)
            return
        self._current_hour = _hour(sim_time_s)
        for sale in self._inputs.track_model.ticket_sales:
            key = (self._current_hour, sale.line)
            self._hourly_sales[key] = (
                self._hourly_sales.get(key, 0) + sale.tickets)
        # Ticket sales count tickets sold since the previous tick, so a
        # sale is stepped with once.
        if self._inputs.track_model.ticket_sales:
            self._inputs = dataclasses.replace(
                self._inputs, track_model=TrackModelInputs())
        self._refresh()

    def _receive_inputs(self, inputs: CtcInputs) -> None:
        """New inputs from the test UI, already validated."""
        self._inputs = inputs

    def _refresh(self) -> None:
        """Tell the panels and the test UI about any change."""
        snap = self._module.snapshot()
        state = (dataclasses.replace(snap, elapsed_s=0.0), self._inputs)
        second = int(snap.elapsed_s)
        changed = state != self._last_state
        new_second = second != self._last_second
        if changed:
            self._last_state = state
            self._revision += 1
            self.stateChanged.emit()
            self.maintenanceModeChanged.emit()
            self.clockSpeedupChanged.emit()
            self.scheduleChanged.emit()
        if new_second:
            self._last_second = second
        if changed or new_second:
            # Throughput moves with time and with every sale.
            self.clockChanged.emit()
        if changed or new_second:
            self._server.push()

    def _act(self, action: Any, *args: Any) -> str:
        """Run a dispatcher action; return its error text, or ""."""
        try:
            action(*args)
        except CtcError as error:
            return str(error)
        self._refresh()
        return ""

    @Property(int, notify=stateChanged)
    def revision(self) -> int:
        """Bumped on every change. QML bindings that call a slot read
        it, so they re-evaluate when the module changes."""
        return self._revision

    # -- Layout options -----------------------------------------------

    @Property(list, constant=True)
    def lineNames(self) -> list[str]:  # noqa: N802
        return list(self._layout)

    @Slot(str, result=list)
    def blockOptions(self, line: str) -> list[str]:  # noqa: N802
        layout_line = self._layout.get(line)
        if layout_line is None:
            return []
        return [block.block_id for block in layout_line.blocks]

    @Slot(str, result=list)
    def switchOptions(self, line: str) -> list[dict[str, str]]:  # noqa
        layout_line = self._layout.get(line)
        if layout_line is None:
            return []
        return [{"value": block.block_id,
                 "text": f"{block.block_id}  ({block.switch})"}
                for block in layout_line.blocks if block.switch]

    @Slot(str, result=list)
    def stationOptions(self, line: str) -> list[dict[str, str]]:  # noqa
        layout_line = self._layout.get(line)
        if layout_line is None:
            return []
        return [{"value": block_id,
                 "text": f"{name.title()} · block {block_id}"}
                for name, block_ids in layout_line.stations().items()
                for block_id in block_ids]

    # -- Trains -------------------------------------------------------

    def _orders(self, snap: CtcSnapshot) -> dict[str, DispatchOrder]:
        return {order.train_id: order for order in snap.orders}

    def _suggestions(self, snap: CtcSnapshot) -> dict[str, TrainSuggestion]:
        return {s.train_id: s
                for s in snap.outputs.track_controller.suggestions}

    def _train_lines(self, snap: CtcSnapshot) -> dict[str, str]:
        """Every known train and its line: reported first, then ordered."""
        lines = {o.train_id: o.line for o in snap.orders}
        for report in self._inputs.track_controller.trains:
            lines[report.train_id] = report.line
        return dict(sorted(lines.items()))

    def _destination(self, line: str, block_id: str) -> str:
        layout_line = self._layout.get(line)
        block = layout_line.block(block_id) if layout_line else None
        if block is not None and block.station:
            return f"{block.station.title()} ({block_id})"
        return f"Block {block_id}"

    def _train_row(self, train_id: str, line: str,
                   snap: CtcSnapshot) -> dict[str, Any]:
        reports = {r.train_id: r
                   for r in self._inputs.track_controller.trains}
        report = reports.get(train_id)
        order = self._orders(snap).get(train_id)
        suggestion = self._suggestions(snap).get(train_id)
        return {
            "train": train_id,
            "line": line,
            "block": report.block_id if report else NO_VALUE,
            "speed": _mph(report.speed_mps) if report else NO_VALUE,
            "speedLimit": (_mph(suggestion.suggested_speed_mps)
                           if suggestion else NO_VALUE),
            "authority": (suggestion.authority_block_id
                          if suggestion else NO_VALUE),
            "destination": (self._destination(
                order.line, order.destination_block_id)
                if order else NO_VALUE),
            "destinationBlock": (order.destination_block_id
                                 if order else ""),
            "eta": (format_time_of_day(order.arrival_s)
                    if order and order.arrival_s is not None
                    else NO_VALUE),
            "status": ("En route" if order
                       else "Reported" if report else NO_VALUE),
            "reported": report is not None,
        }

    @Property(list, notify=stateChanged)
    def trains(self) -> list[dict[str, Any]]:
        """Rows for the Train occupancy window."""
        snap = self._module.snapshot()
        return [self._train_row(train_id, line, snap)
                for train_id, line in self._train_lines(snap).items()]

    @Slot(str, result="QVariantMap")
    def trainDetail(self, train_id: str) -> dict[str, Any]:  # noqa: N802
        """One train's row, or an empty map if it is not known."""
        snap = self._module.snapshot()
        line = self._train_lines(snap).get(train_id)
        if line is None:
            return {}
        return self._train_row(train_id, line, snap)

    @Slot(str, result=list)
    def trainOptions(self, line: str) -> list[dict[str, str]]:  # noqa
        """Trains on a line, then a new train with the next free ID."""
        snap = self._module.snapshot()
        known = self._train_lines(snap)
        options = [{"value": train_id, "text": train_id}
                   for train_id, train_line in known.items()
                   if train_line == line]
        number = 1
        while f"T{number}" in known:
            number += 1
        options.append({"value": f"T{number}",
                        "text": f"New train (T{number})"})
        return options

    # -- Track state ----------------------------------------------------

    @Property(dict, notify=stateChanged)
    def blockStates(self) -> dict[str, str]:  # noqa: N802
        """``Line:block`` -> closed | failure, for the map.

        Failure outranks closed, so the most urgent state shows (style
        guide 6.4). Occupancy is drawn as trains instead; see
        ``mapTrains``.
        """
        snap = self._module.snapshot()
        states: dict[str, str] = {}
        for block in snap.outputs.track_controller.closed_blocks:
            states[block_key(block.line, block.block_id)] = "closed"
        for failure in self._inputs.track_controller.failures:
            states[block_key(failure.line, failure.block_id)] = "failure"
        return states

    @Property(list, notify=stateChanged)
    def mapTrains(self) -> list[dict[str, Any]]:  # noqa: N802
        """Trains to draw on the map: ``{train, line, block, fraction}``.

        A reported train sits at its offset into its block. A block
        reported occupied with no train reported on it gets an
        unnamed train at its middle, so occupancy always shows.
        """
        track = self._inputs.track_controller
        trains = []
        placed: set[tuple[str, str]] = set()
        for report in track.trains:
            layout_line = self._layout.get(report.line)
            block = (layout_line.block(report.block_id)
                     if layout_line else None)
            length = block.length_m if block else 0.0
            trains.append({
                "train": report.train_id, "line": report.line,
                "block": report.block_id,
                "fraction": report.offset_m / length if length else 0.5})
            placed.add((report.line, report.block_id))
        for occupancy in track.occupancy:
            key = (occupancy.line, occupancy.block_id)
            if occupancy.occupied and key not in placed:
                trains.append({"train": "", "line": occupancy.line,
                               "block": occupancy.block_id,
                               "fraction": 0.5})
                placed.add(key)
        return trains

    @Property(dict, notify=stateChanged)
    def crossingStates(self) -> dict[str, str]:  # noqa: N802
        """``Line:crossing`` -> inactive | active, as last reported."""
        return {block_key(c.line, c.crossing_id): c.state
                for c in self._inputs.track_controller.crossings}

    @Property(list, notify=stateChanged)
    def closures(self) -> list[dict[str, Any]]:
        """Closed and failed blocks, for Active closures."""
        snap = self._module.snapshot()
        rows: list[dict[str, Any]] = []
        for block in snap.outputs.track_controller.closed_blocks:
            rows.append({"block": f"{block.line} {block.block_id}",
                         "state": "Closed", "line": block.line,
                         "blockId": block.block_id, "reopenable": True})
        for failure in self._inputs.track_controller.failures:
            rows.append({
                "block": f"{failure.line} {failure.block_id}",
                "state": _FAILURE_LABELS.get(failure.kind, failure.kind),
                "line": failure.line, "blockId": failure.block_id,
                "reopenable": False})
        rows.sort(key=lambda r: (r["line"], _block_number(r["blockId"])))
        return rows

    @Slot(str, str, result="QVariantMap")
    def switchDetail(self, line: str,  # noqa: N802
                     switch_id: str) -> dict[str, str]:
        """A switch's connections, reported and commanded positions."""
        layout_line = self._layout.get(line)
        block = layout_line.block(switch_id) if layout_line else None
        if block is None or not block.switch:
            return {}
        connections = [part.strip() for part in block.switch.split(";")]
        reported = {(s.line, s.switch_id): s.position
                    for s in self._inputs.track_controller.switches}
        commanded = {
            (c.line, c.switch_id): c.position
            for c in self._module.snapshot()
            .outputs.track_controller.switch_commands}
        return {
            "normal": connections[0],
            "reverse": connections[1] if len(connections) > 1 else NO_VALUE,
            "reported": reported.get((line, switch_id), NO_VALUE),
            "commanded": commanded.get((line, switch_id), NO_VALUE),
        }

    @Property(int, notify=stateChanged)
    def switchCommandCount(self) -> int:  # noqa: N802
        return len(self._module.snapshot()
                   .outputs.track_controller.switch_commands)

    # -- Throughput ---------------------------------------------------

    def _tickets_per_hour(self) -> dict[str, str]:
        """Tickets per hour on each line since the simulation started,
        keyed by line name; a dash until a simulated minute has passed."""
        snap = self._module.snapshot()
        hours = snap.elapsed_s / 3600
        return {
            sale.line: (f"{sale.tickets / hours:.0f}"
                        if snap.elapsed_s >= 60 else NO_VALUE)
            for sale in snap.tickets_sold
        }

    @Property(dict, notify=clockChanged)
    def throughput(self) -> dict[str, str]:
        return self._tickets_per_hour()

    @Property(list, notify=clockChanged)
    def throughputRows(self) -> list[dict[str, str]]:  # noqa: N802
        """One row per line for the throughput table."""
        return [{"line": line, "tickets": per_hour, "trains": NO_VALUE,
                 "dwell": NO_VALUE}
                for line, per_hour in self._tickets_per_hour().items()]

    @Property(dict, notify=clockChanged)
    def throughputHistory(self) -> dict[str, Any]:  # noqa: N802
        """Tickets sold per line in each of 12 simulated clock hours.

        The window starts at the hour the simulation started and, once
        12 hours have passed, follows the current hour. ``hours`` labels
        each hour (``HH:00``); each series has one count per hour;
        ``peak`` is the largest count, the shared scale; ``current`` is
        the index of the hour in progress.
        """
        last = max(self._current_hour,
                   self._first_hour + HISTORY_HOURS - 1)
        hours = range(last - HISTORY_HOURS + 1, last + 1)
        counts = {line: [self._hourly_sales.get((hour, line), 0)
                         for hour in hours]
                  for line in self._layout}
        return {
            "hours": [f"{hour % 24:02d}:00" for hour in hours],
            "series": [{"line": line, "counts": line_counts}
                       for line, line_counts in counts.items()],
            "peak": max((count for line_counts in counts.values()
                         for count in line_counts), default=0),
            "current": self._current_hour - hours[0],
        }

    # -- Dispatcher actions -------------------------------------------

    @Slot(str, str, str, str, result=str)
    def dispatchTrain(self, train_id: str, line: str,  # noqa: N802
                      block_id: str, arrival_text: str) -> str:
        """Dispatch or reroute a train; arrival is optional HH:MM."""
        arrival: float | None = None
        if arrival_text.strip():
            try:
                arrival = parse_time_of_day(arrival_text)
            except TimeOfDayError as error:
                return str(error)
        return self._act(self._module.dispatch, train_id, line, block_id,
                         arrival)

    @Slot(str, str, str, result=str)
    def setAuthority(self, train_id: str, line: str,  # noqa: N802
                     block_id: str) -> str:
        """Send a train directly to a block, with no arrival time."""
        return self._act(self._module.dispatch, train_id, line, block_id,
                         None)

    @Slot(str, result=str)
    def cancelDispatch(self, train_id: str) -> str:  # noqa: N802
        return self._act(self._module.cancel_dispatch, train_id)

    @Slot(str, str, result=str)
    def closeBlock(self, line: str, block_id: str) -> str:  # noqa: N802
        return self._act(self._module.set_block_closed, line, block_id,
                         True)

    @Slot(str, str, result=str)
    def reopenBlock(self, line: str, block_id: str) -> str:  # noqa: N802
        return self._act(self._module.set_block_closed, line, block_id,
                         False)

    @Slot(str, str, int, result=str)
    def setSwitch(self, line: str, switch_id: str,  # noqa: N802
                  position: int) -> str:
        """Command a switch: position 0 is normal, 1 reverse."""
        if position not in (0, 1):
            return "Choose Normal or Reverse."
        return self._act(self._module.set_switch, line, switch_id,
                         _SWITCH_POSITIONS[position])

    @Slot(str, str, result=str)
    def releaseSwitch(self, line: str, switch_id: str) -> str:  # noqa
        return self._act(self._module.release_switch, line, switch_id)

    # -- Operating mode and clock speed -------------------------------

    @Property(bool, notify=maintenanceModeChanged)
    def maintenanceMode(self) -> bool:  # noqa: N802
        outputs = self._module.snapshot().outputs
        return outputs.track_controller.maintenance_mode

    @Slot(bool)
    def setMaintenanceMode(self, active: bool) -> None:  # noqa: N802
        """Apply the window's operating mode to the module."""
        if active != self.maintenanceMode:
            self._act(self._module.set_maintenance_mode, active)

    @Property(bool, notify=clockSpeedupChanged)
    def clockSpeedup(self) -> bool:  # noqa: N802
        return self._module.snapshot().outputs.clock_speedup

    @Slot(bool)
    def setClockSpeedup(self, active: bool) -> None:  # noqa: N802
        """Apply the window's clock speed (10x is True) to the module."""
        if active != self.clockSpeedup:
            self._act(self._module.set_clock_speedup, active)

    # -- Schedule -----------------------------------------------------

    @Property(str, notify=scheduleChanged)
    def scheduleFile(self) -> str:  # noqa: N802
        return self._schedule_file

    @Property(str, notify=scheduleChanged)
    def scheduleError(self) -> str:  # noqa: N802
        return self._schedule_error

    @Property(list, notify=scheduleChanged)
    def departures(self) -> list[dict[str, Any]]:
        """Queued runs as rows for the Next departures table."""
        return [
            {"time": _offset(q.departure_s),
             "train": f"{q.line} {q.train_id}",
             "status": "Queued"}
            for q in self._module.snapshot().queued_trains
        ]

    @Slot(QUrl)
    def loadSchedule(self, url: QUrl) -> None:  # noqa: N802
        """Load a schedule file; on failure keep the current one."""
        path = Path(url.toLocalFile())
        try:
            schedule = load_schedule(path)
        except ScheduleError as error:
            self._schedule_error = str(error)
        else:
            self._module.load_schedule(schedule)
            self._schedule_file = path.name
            self._schedule_error = ""
            self._refresh()
        self.scheduleChanged.emit()
