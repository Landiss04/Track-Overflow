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
    BlockRef,
    CtcInputs,
    CtcOffice,
    CtcSnapshot,
    DispatchOrder,
    TrackModelInputs,
    TrainAuthority,
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

_BLOCKED_LABELS = {
    "occupied": "occupied",
    "closed": "closed",
    "closing": "closing",
    "failed": "failed",
}


def _closed_only(snap: CtcSnapshot) -> list[BlockRef]:
    """Closed blocks, without the ones still closing: ``closed_blocks``
    lists both, since the Track Controller is locked out of either."""
    pending = set(snap.pending_closures)
    return [b for b in snap.outputs.track_controller.closed_blocks
            if b not in pending]


def _authority_limit(limit: TrainAuthority) -> str:
    """Why a train's authority ends where it does, short enough for a
    key-value row: "Block 24 occupied", "Switch 12 not set"."""
    if limit.reason == "destination":
        return "At destination" if limit.blocks == 0 else "Destination"
    if limit.reason == "switch":
        return f"Switch {limit.at} not set"
    if limit.reason in _BLOCKED_LABELS:
        return f"Block {limit.at} {_BLOCKED_LABELS[limit.reason]}"
    if limit.reason == "reserved":
        return f"Block {limit.at} held by {limit.held_by}"
    return "No route"


#: Blocks within authority shown as chips in the Selected train panel.
ROUTE_CHIPS = 8

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
    noticesChanged = Signal()

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
        self._clock: SimulationClockBridge | None = None
        # Self-cancelled orders already dismissed from the notices.
        self._cancelled_seen = 0
        # Reversal alerts the dispatcher dismissed: (train, line, block
        # it would reverse in). Forgotten once the situation clears, so
        # it alerts again if it comes back.
        self._reversals_seen: set[tuple[str, str, str]] = set()

    def start(self) -> None:
        """Start serving the test UI. The window works either way."""
        if not self._server.listen():
            print("CTC test UI link unavailable: could not listen.",
                  file=sys.stderr)

    @staticmethod
    def already_running() -> bool:
        """True if another CTC Office window is already running."""
        return CtcLinkServer.is_running()

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
        self._clock = clock
        clock.pausedChanged.connect(self.noticesChanged)
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
        """New inputs from the test UI.

        They are staged in the module, so the dispatcher's safety checks
        use them at once, and applied at the next tick: while the clock
        is paused they change nothing, and the window keeps showing the
        last applied reports. Raises if the module rejects them.
        """
        self._module.stage_inputs(inputs)
        self._inputs = inputs

    def _applied(self) -> CtcInputs:
        """The reports the module last stepped with: what to show."""
        applied = self._module.snapshot().inputs
        return applied if applied is not None else CtcInputs()

    def _refresh(self) -> None:
        """Tell the panels and the test UI about any change."""
        snap = self._module.snapshot()
        state = (dataclasses.replace(snap, elapsed_s=0.0), self._inputs)
        second = int(snap.elapsed_s)
        changed = state != self._last_state
        new_second = second != self._last_second
        if changed:
            self._last_state = state
            self._reversals_seen &= self._reversal_keys(snap)
            self._revision += 1
            self.stateChanged.emit()
            self.noticesChanged.emit()
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
        for report in self._applied().track_controller.trains:
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
                   for r in self._applied().track_controller.trains}
        report = reports.get(train_id)
        order = self._orders(snap).get(train_id)
        suggestion = self._suggestions(snap).get(train_id)
        limit = {a.train_id: a for a in snap.authorities}.get(train_id)
        return {
            "train": train_id,
            "line": line,
            "block": report.block_id if report else NO_VALUE,
            "speed": _mph(report.speed_mps) if report else NO_VALUE,
            "speedLimit": (_mph(suggestion.suggested_speed_mps)
                           if suggestion else NO_VALUE),
            # The table's compact form; the readouts show the count
            # alone (a telemetry value is a short number and a unit).
            "authority": (f"{limit.blocks} (to {limit.end_block_id})"
                          if limit else NO_VALUE),
            "authorityBlocks": str(limit.blocks) if limit else NO_VALUE,
            "authorityEnd": (f"Block {limit.end_block_id}"
                             if limit else NO_VALUE),
            "authorityLimit": (_authority_limit(limit)
                               if limit else NO_VALUE),
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

    def _authority(self, train_id: str) -> TrainAuthority | None:
        snap = self._module.snapshot()
        return {a.train_id: a for a in snap.authorities}.get(train_id)

    @Slot(str, result="QVariantMap")
    def routeStates(self, train_id: str) -> dict[str, str]:  # noqa: N802
        """A train's route for the map: ``Line:block`` -> ``authority``
        (blocks it may still enter) or ``beyond`` (the rest of the way
        to its destination). Empty with no train, order or route."""
        limit = self._authority(train_id)
        if limit is None:
            return {}
        ahead = limit.route[1:]
        return {block_key(limit.line, block_id):
                ("authority" if i < limit.blocks else "beyond")
                for i, block_id in enumerate(ahead)}

    @Slot(str, result="QVariantMap")
    def routeDetail(self, train_id: str) -> dict[str, Any]:  # noqa: N802
        """A train's route for the Selected train panel.

        ``chips``: its own block, then the blocks within authority (the
        first ``ROUTE_CHIPS``, then ``{more: n}`` for the rest), then the
        block the authority stops before, if a block stops it; each
        ``{block, occupancy}`` for a TrackBlock (style guide 6.4).
        ``summary``: one line on the rest of the way.
        """
        limit = self._authority(train_id)
        if limit is None or not limit.route:
            return {"chips": [],
                    "summary": ("No route to its destination."
                                if limit else "")}
        snap = self._module.snapshot()
        applied = self._applied()
        line = limit.line
        track = applied.track_controller
        occupied = ({t.block_id for t in track.trains if t.line == line}
                    | {o.block_id for o in track.occupancy
                       if o.occupied and o.line == line})
        closed = {b.block_id
                  for b in snap.outputs.track_controller.closed_blocks
                  if b.line == line}
        failed = {f.block_id for f in track.failures if f.line == line}

        def occupancy(block_id: str) -> str:
            return ("failure" if block_id in failed
                    else "closed" if block_id in closed
                    else "occupied" if block_id in occupied else "free")

        ahead = limit.route[1:limit.blocks + 1]
        chips: list[dict[str, Any]] = [
            {"block": b, "occupancy": occupancy(b)}
            for b in (limit.route[0], *ahead[:ROUTE_CHIPS])]
        if len(ahead) > ROUTE_CHIPS:
            chips.append({"more": len(ahead) - ROUTE_CHIPS})
        if limit.reason in _BLOCKED_LABELS:
            chips.append({"block": limit.at,
                          "occupancy": occupancy(limit.at)})
        destination = limit.route[-1]
        remaining = len(limit.route) - 1 - limit.blocks
        if limit.blocks == 0 and remaining == 0:
            summary = f"At its destination, block {destination}."
        elif remaining == 0:
            summary = (f"Authority runs to its destination, block "
                       f"{destination}.")
        else:
            summary = (f"Authority ends at block {limit.end_block_id}; "
                       f"{remaining} more to its destination, block "
                       f"{destination}.")
        if limit.reverse_at:
            summary += (f" Getting round means reversing at block "
                        f"{limit.reverse_at}; the CTC does not reverse "
                        "trains, so it waits.")
        return {"chips": chips, "summary": summary}

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
        for block in _closed_only(snap):
            states[block_key(block.line, block.block_id)] = "closed"
        for failure in self._applied().track_controller.failures:
            states[block_key(failure.line, failure.block_id)] = "failure"
        return states

    @Property(list, notify=stateChanged)
    def mapTrains(self) -> list[dict[str, Any]]:  # noqa: N802
        """Trains to draw on the map: ``{train, line, block, fraction}``.

        A reported train sits at its offset into its block. A block
        reported occupied with no train reported on it gets an
        unnamed train at its middle, so occupancy always shows.
        """
        track = self._applied().track_controller
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
                for c in self._applied().track_controller.crossings}

    @Property(list, notify=stateChanged)
    def closures(self) -> list[dict[str, Any]]:
        """Closed, closing and failed blocks, for Active closures."""
        snap = self._module.snapshot()
        rows: list[dict[str, Any]] = []
        for block in _closed_only(snap):
            rows.append({"block": f"{block.line} {block.block_id}",
                         "state": "Closed", "line": block.line,
                         "blockId": block.block_id, "reopenable": True,
                         "pending": False})
        for block in snap.pending_closures:
            rows.append({"block": f"{block.line} {block.block_id}",
                         "state": "Closing \u2014 train in block",
                         "line": block.line, "blockId": block.block_id,
                         "reopenable": True, "pending": True})
        for failure in self._applied().track_controller.failures:
            rows.append({
                "block": f"{failure.line} {failure.block_id}",
                "state": _FAILURE_LABELS.get(failure.kind, failure.kind),
                "line": failure.line, "blockId": failure.block_id,
                "reopenable": False, "pending": False})
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
                    for s in self._applied().track_controller.switches}
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

    # -- Notices ------------------------------------------------------

    @Property(list, notify=noticesChanged)
    def notices(self) -> list[str]:
        """Messages for the dispatcher, newest last."""
        snap = self._module.snapshot()
        found = []
        if snap.inputs_staged and self._clock is not None \
                and self._clock.paused:
            found.append("Track Controller update staged \u2014 it "
                         "applies when the clock runs.")
        for cancelled in snap.cancelled_orders[self._cancelled_seen:]:
            found.append(
                f"Order for {cancelled.train_id} to {cancelled.line} "
                f"block {cancelled.destination_block_id} cancelled: "
                f"{cancelled.reason}.")
        return found

    @staticmethod
    def _reversal_keys(snap: CtcSnapshot) -> set[tuple[str, str, str]]:
        return {(a.train_id, a.line, a.reverse_at)
                for a in snap.authorities if a.reverse_at}

    def _blocked_by(self, limit: TrainAuthority) -> str:
        """What stops a held train, as a clause: "T5 is standing in
        block 28", "block 29 has failed"."""
        if limit.reason == "occupied":
            standing = [t.train_id
                        for t in self._applied().track_controller.trains
                        if (t.line, t.block_id) == (limit.line, limit.at)]
            if standing:
                return (f"{standing[0]} is standing in block {limit.at} "
                        "and is not moving")
            return f"block {limit.at} is occupied"
        return {
            "failed": f"block {limit.at} has failed",
            "closed": f"block {limit.at} is closed",
            "closing": f"block {limit.at} is closing",
            "reserved": f"block {limit.at} is held by {limit.held_by}",
            "switch": f"switch {limit.at} is not set for its route",
        }.get(limit.reason, "there is no route without reversing")

    @Property(list, notify=noticesChanged)
    def reversalAlerts(self) -> list[dict[str, str]]:  # noqa: N802
        """Trains the CTC holds because only reversing would get them
        round what blocks them: ``{train, line, reverseAt, destination,
        blockedBy}``. The CTC never reverses a train; the dispatcher
        decides."""
        snap = self._module.snapshot()
        orders = self._orders(snap)
        alerts = []
        for limit in snap.authorities:
            key = (limit.train_id, limit.line, limit.reverse_at)
            if not limit.reverse_at or key in self._reversals_seen:
                continue
            order = orders.get(limit.train_id)
            alerts.append({
                "train": limit.train_id,
                "line": limit.line,
                "reverseAt": limit.reverse_at,
                "destination": (order.destination_block_id
                                if order else ""),
                "blockedBy": self._blocked_by(limit),
            })
        return alerts

    @Slot(str)
    def dismissReversal(self, train_id: str) -> None:  # noqa: N802
        """Stop alerting about one train's reversal until it clears."""
        snap = self._module.snapshot()
        self._reversals_seen |= {key for key in self._reversal_keys(snap)
                                 if key[0] == train_id}
        self.noticesChanged.emit()

    @Slot()
    def dismissNotices(self) -> None:  # noqa: N802
        """Clear the cancelled-order notices (a staged update stays
        until it applies)."""
        self._cancelled_seen = len(self._module.snapshot().cancelled_orders)
        self.noticesChanged.emit()

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
        return self._module.snapshot().maintenance_mode

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
