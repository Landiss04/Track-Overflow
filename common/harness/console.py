"""Present harness snapshots and batched events to the operator window.

Only the timer publishes QML changes. Tick and event handlers collect
bounded Python data, so the scene never updates at the tick rate.
"""

from __future__ import annotations

import json
import time
from collections import deque
from collections.abc import Mapping, Sequence
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QObject,
    Property,
    Qt,
    QTimer,
    Signal,
    Slot,
)

from common.harness.core import Harness

REFRESH_MS = 100
MILLISECONDS_PER_SECOND = 1000
OUTPUT_INTERVAL_S = 0.5
RECENT_INTERVAL_S = 5.0
MAX_EVENTS = 3000
MAX_OUTPUT_CHARS = 8000
EMPTY = "—"
WINDOW_TITLE = "Track Overflow — Central Harness"

MODULE_LABELS = {
    "ctc-office": "CTC Office",
    "track-controller-sw": "Track Controller — SW",
    "track-controller-hw": "Track Controller — HW",
    "track-model": "Track Model",
    "train-model": "Train Model",
    "train-controller-sw": "Train Controller — SW",
    "train-controller-hw": "Train Controller — HW",
}
FAULT_EVENTS = frozenset({
    "TICK_REJECTED",
    "REPLY_LATE",
    "MODULE_DISCONNECTED",
    "PROTOCOL_ERROR",
    "TIME_SLIPPED",
    "INPUTS_FAILED",
    "EDGES_FAILED",
    "MODULE_KILLED",
})


class EventModel(QAbstractListModel):
    """Keep a bounded, virtualized event list with batch insertion."""

    countChanged = Signal()
    _NAMES = ("time", "tick", "source", "eventName", "detail", "fault")
    _FIRST_ROLE = int(Qt.ItemDataRole.UserRole) + 1

    def __init__(self, parent: QObject | None = None) -> None:
        """Create an empty event model."""
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []

    def roleNames(self) -> dict[int, bytes]:
        """Return named roles for the QML ListView."""
        return {
            self._FIRST_ROLE + i: name.encode()
            for i, name in enumerate(self._NAMES)
        }

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the retained event count."""
        return 0 if parent.isValid() else len(self._rows)

    def data(
        self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        """Return one event field for a valid model index."""
        field = role - self._FIRST_ROLE
        if (
            not index.isValid()
            or not 0 <= index.row() < len(self._rows)
            or not 0 <= field < len(self._NAMES)
        ):
            return None
        return self._rows[index.row()][self._NAMES[field]]

    @Property(int, notify=countChanged)
    def count(self) -> int:
        """Return the number of retained events."""
        return len(self._rows)

    @Slot(int, result="QVariantMap")
    def row(self, index: int) -> dict[str, Any]:
        """Return a copy of a retained row for detail inspection."""
        if 0 <= index < len(self._rows):
            return dict(self._rows[index])
        return {}

    def append_batch(self, rows: Sequence[dict[str, Any]]) -> None:
        """Append a batch and evict rows that exceed the cap."""
        batch = list(rows[-MAX_EVENTS:])
        if not batch:
            return
        remove = max(0, len(self._rows) + len(batch) - MAX_EVENTS)
        if remove:
            self.beginRemoveRows(QModelIndex(), 0, remove - 1)
            del self._rows[:remove]
            self.endRemoveRows()
        start = len(self._rows)
        self.beginInsertRows(QModelIndex(), start, start + len(batch) - 1)
        self._rows.extend(batch)
        self.endInsertRows()
        self.countChanged.emit()


class HarnessConsole(QObject):
    """Expose the harness through periodic display snapshots."""

    snapshotChanged = Signal()
    modulesChanged = Signal()
    selectionChanged = Signal()
    outputChanged = Signal()
    endRunRequested = Signal()

    def __init__(
        self, harness: Harness, parent: QObject | None = None
    ) -> None:
        """Watch a harness before startup to retain its events."""
        super().__init__(parent)
        self._harness = harness
        self._events = EventModel(self)
        self._pending: deque[dict[str, Any]] = deque(maxlen=MAX_EVENTS)
        self._round_trips: deque[tuple[float, float]] = deque()
        self._snapshot: dict[str, Any] = {}
        self._modules: list[dict[str, Any]] = []
        self._selected = ""
        self._output = EMPTY
        self._output_module = ""
        self._next_output_s = 0.0
        harness.eventLogged.connect(self._collect_event)
        harness.tickCompleted.connect(self._collect_tick)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self.refresh()
        self._timer.start(REFRESH_MS)

    @Property(QObject, constant=True)
    def events(self) -> EventModel:
        """Return the virtualized event model."""
        return self._events

    @Property("QVariantMap", notify=snapshotChanged)
    def snapshot(self) -> dict[str, Any]:
        """Return the most recent display snapshot."""
        return dict(self._snapshot)

    @Property("QVariantList", notify=modulesChanged)
    def modules(self) -> list[dict[str, Any]]:
        """Return display rows in launch order."""
        return [dict(row) for row in self._modules]

    @Property(str, notify=selectionChanged)
    def selected_module(self) -> str:
        """Return the module selected for the output inspector."""
        return self._selected

    @Property(str, notify=outputChanged)
    def output_text(self) -> str:
        """Return pretty-printed, bounded outputs for the selection."""
        return self._output

    @Property(str, notify=outputChanged)
    def output_module(self) -> str:
        """Return which module produced the currently formatted text."""
        return self._output_module

    @Slot(str)
    def select_module(self, module: str) -> None:
        """Select a module; the output timer refreshes its text."""
        if module != self._selected and any(
            row["name"] == module for row in self._modules
        ):
            self._selected = module
            self.selectionChanged.emit()

    @Slot(str, result=bool)
    def show_window(self, module: str) -> bool:
        """Forward a window request through the harness."""
        return self._harness.show_window(module)

    @Slot()
    def end_run(self) -> None:
        """Request loop exit after QML has confirmed ending the run."""
        self.endRunRequested.emit()

    @Slot()
    def refresh(self) -> None:
        """Publish one snapshot and one event batch, about ten Hz."""
        now = time.monotonic()
        while self._round_trips and (
            now - self._round_trips[0][0] > RECENT_INTERVAL_S
        ):
            self._round_trips.popleft()
        rows = []
        for status in self._harness.module_statuses:
            row = dict(status)
            row["label"] = MODULE_LABELS.get(row["name"], row["name"])
            row["pid_text"] = str(row["pid"]) if row["pid"] else EMPTY
            row["exit_text"] = row["exit"] or EMPTY
            row["can_show"] = row["state"] in ("READY", "LATE")
            row["variant"] = {
                "READY": "ok", "LATE": "warning",
                "DOWN": "fault", "EXITED": "fault",
            }.get(row["state"], "idle")
            if row["exit"] == "exit code 0":
                row["variant"] = "idle"
            rows.append(row)
        if rows != self._modules:
            self._modules = rows
            self.modulesChanged.emit()
        clock = self._harness.clock
        trips = [value for _, value in self._round_trips]
        snapshot = {
            "time": clock.format_time_of_day(),
            "tick": str(clock.tick_count),
            "speed": f"{clock.speed}x",
            "state": "PAUSED" if clock.is_paused else "RUNNING",
            "hold": _display_reason(self._harness.hold_reason),
            "ready": len(self._harness.ready_modules),
            "total": len(rows),
            "startup_timeout": ", ".join(
                MODULE_LABELS.get(name, name)
                for name in self._harness.startup_timed_out_modules
            ),
            "mean_ms": (
                f"{sum(trips) / len(trips) * MILLISECONDS_PER_SECOND:.2f}"
                if trips else EMPTY
            ),
            "max_ms": (
                f"{max(trips) * MILLISECONDS_PER_SECOND:.2f}"
                if trips else EMPTY
            ),
            "slipped": str(self._harness.dropped_ticks),
            "log_path": self._harness.log_path,
        }
        if snapshot != self._snapshot:
            self._snapshot = snapshot
            self.snapshotChanged.emit()
        if self._pending:
            self._events.append_batch(list(self._pending))
            self._pending.clear()
        if now >= self._next_output_s:
            self._next_output_s = now + OUTPUT_INTERVAL_S
            values = self._harness.outputs.get(self._selected)
            output = _format_outputs(values) if values is not None else EMPTY
            if (
                output != self._output
                or self._selected != self._output_module
            ):
                self._output = output
                self._output_module = self._selected
                self.outputChanged.emit()

    def _collect_tick(self, _tick: int, round_trip_s: float) -> None:
        # Collect only; QML receives no notification here.
        self._round_trips.append((time.monotonic(), round_trip_s))

    def _collect_event(self, source: str, event: str, detail: str) -> None:
        # Timestamp at emission, before another tick changes the clock.
        clock = self._harness.clock
        fault = event in FAULT_EVENTS or (
            event == "MODULE_EXITED" and detail != "exit code 0"
        )
        self._pending.append({
            "time": clock.format_time_of_day(),
            "tick": str(clock.tick_count),
            "source": MODULE_LABELS.get(source, source),
            "eventName": event,
            "detail": detail or EMPTY,
            "fault": fault,
        })


def _display_reason(reason: str | None) -> str:
    # Keep the core's reason while displaying canonical module names.
    if reason is None:
        return "Clock controlled by the CTC Office"
    for name, label in MODULE_LABELS.items():
        reason = reason.replace(name, label)
    return reason[0].upper() + reason[1:]


def _format_outputs(values: Mapping[str, Any]) -> str:
    # Stop encoding once the visible budget is spent; do not build a
    # complete JSON string for a large array before truncating it.
    chunks = []
    remaining = MAX_OUTPUT_CHARS
    for chunk in json.JSONEncoder(
        indent=2, ensure_ascii=False
    ).iterencode(values):
        if len(chunk) > remaining:
            chunks.append(chunk[:remaining])
            chunks.append("\n… (truncated)")
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return "".join(chunks)
