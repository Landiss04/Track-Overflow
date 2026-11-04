"""The test bench, standing in for the central harness (OPEN_ISSUES.md #45).

Opened on its own (main.py --test). It holds one console backend per
variant, each with its own fleet, as the harness has them: HW for the
Red Line's trains, SW for the Green Line's (REQUIREMENTS.md M13).
Spawning a train opens its line's console, or brings it back, and the
bench steps both on one bench clock, as the harness does with its own
(M11). The bench edits any train; each console stays on the train its
operator picked.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Property, QObject, Qt, QTimer, Signal, Slot

from .backend import (ConsoleBackend, _clock_text, parse_time_of_day,
                      same_line)
from .constants import (CLOCK_START_S, SIM_RATES, TICK_S, UI_HZ,
                        VARIANT_LINES)


class BenchBackend(QObject):
    """What the bench's QML sees, as `controller`.

    The same snapshot and slots the bench reads from a console
    backend, so the bench's views are unchanged; each call goes to the
    console backend holding the train.
    """

    snapshot_changed = Signal()
    roster_changed = Signal()

    def __init__(self, open_console: Callable[[ConsoleBackend], None],
                 parent: QObject | None = None) -> None:
        """``open_console`` opens a backend's console, or shows it again."""
        super().__init__(parent)
        self._open_console = open_console
        self.backends = {
            variant: ConsoleBackend(self, variant=variant, line=line,
                                    bench_driven=True)
            for variant, line in VARIANT_LINES.items()}
        self.editing = ""
        # Every running train, in the order spawned, across both lines.
        self._order: list[str] = []
        self.sim_rate = 1
        self.paused = False
        self.bench_error = ""
        self.spawn_note = ""
        self.time_s = CLOCK_START_S
        # Starts at the first commissioning, on either line, and then
        # always runs (REQUIREMENTS.md M11).
        self._clock_started = False

        self._control = QTimer(self)
        self._control.setTimerType(Qt.TimerType.PreciseTimer)
        self._control.timeout.connect(self._step_all)
        self._control.start(self._tick_ms())
        self._ui = QTimer(self)
        self._ui.timeout.connect(self.snapshot_changed.emit)
        self._ui.start(int(1000 / UI_HZ))

    def _owner(self, train_id: str) -> ConsoleBackend | None:
        return next((b for b in self.backends.values()
                     if train_id in b.fleet), None)

    def _step_all(self) -> None:
        if self.paused:
            return
        if not self._clock_started:
            self._clock_started = any(
                core.armed for b in self.backends.values() for core in b.fleet)
        if self._clock_started:
            self.time_s += TICK_S
        for backend in self.backends.values():
            backend.step_fleet(self.time_s)

    def _tick_ms(self) -> int:
        return max(1, round(1000 * TICK_S / self.sim_rate))

    def _publish(self) -> None:
        self.snapshot_changed.emit()

    # ------------------------------------------------------ read side
    @Property("QVariantList", notify=roster_changed)
    def trains(self) -> list[dict[str, Any]]:
        """Every running train, both lines, in the order spawned."""
        listed = {train["id"]: train
                  for b in self.backends.values() for train in b.trains}
        return [listed[i] for i in self._order if i in listed]

    @Property("QVariantMap", notify=snapshot_changed)
    def snapshot(self) -> dict[str, Any]:
        """The train being edited, with the bench's own state."""
        owner = self._owner(self.editing) or self.backends["HW"]
        with owner.viewing(self.editing):
            values = dict(owner.snapshot)
        values.update(
            train_count=sum(len(b.fleet) for b in self.backends.values()),
            sim_rate=self.sim_rate,
            sim_rate_index=SIM_RATES.index(self.sim_rate),
            paused=self.paused,
            bench_error=self.bench_error,
            spawn_note=self.spawn_note,
            bench_clock=True,
            clock=_clock_text(self.time_s),
        )
        return values

    # ----------------------------------------------------- write side
    @Slot(int, str, str)
    def spawn_train(self, number: int, line: str, target: str) -> None:
        """Spawn a train on its line's console, and open that console.

        The bench stays on the train it edits; only the first train
        spawned is picked for it.
        """
        backend = next(b for b in self.backends.values()
                       if same_line(b.line, line))
        train_id = backend.add_train(number, line, target)
        self.spawn_note = backend.spawn_note
        if train_id:
            self._order.append(train_id)
            if not self._owner(self.editing):
                self.editing = train_id
            self._open_console(backend)
            self.roster_changed.emit()
        backend._publish()
        self._publish()

    @Slot(str)
    def select_train(self, train_id: str) -> None:
        """Edit another train; the consoles keep theirs."""
        if self._owner(train_id):
            self.editing = train_id
        self._publish()

    @Slot(str)
    def remove_train(self, train_id: str) -> None:
        """Take a train out; the bench moves to the next one, if any."""
        owner = self._owner(train_id)
        if owner is None:
            return
        ids = [t["id"] for t in self.trains]
        owner.drop_train(train_id)
        self._order.remove(train_id)
        self.spawn_note = owner.spawn_note
        if self.editing == train_id:
            left = [t["id"] for t in self.trains]
            index = min(ids.index(train_id), len(left) - 1)
            self.editing = left[index] if left else ""
        self.roster_changed.emit()
        owner._publish()
        self._publish()

    @Slot("QVariantMap")
    def apply_bench_inputs(self, values: dict) -> None:
        """Edit the simulation of the train being edited."""
        owner = self._owner(self.editing)
        if owner is None:
            return
        with owner.viewing(self.editing):
            owner.apply_bench_inputs(values)
        self.bench_error = owner.bench_error
        self._publish()

    @Slot()
    def bench_block_change(self) -> None:
        """The train being edited enters its next block."""
        owner = self._owner(self.editing)
        if owner is not None:
            with owner.viewing(self.editing):
                owner.bench_block_change()
        self._publish()

    @Slot(str)
    def set_bench_time(self, text: str) -> None:
        """Set the bench clock to a time of day, HH:MM or HH:MM:SS."""
        seconds = parse_time_of_day(text)
        if seconds is None:
            self.bench_error = (
                f"time must be HH:MM or HH:MM:SS, not {text!r}")
        else:
            day = int(self.time_s // 86400)
            self.time_s = day * 86400 + seconds
            self.bench_error = ""
        self._publish()

    @Slot(int)
    def set_sim_rate(self, index: int) -> None:
        """Run both lines at real time or ten times real time."""
        if 0 <= index < len(SIM_RATES):
            self.sim_rate = SIM_RATES[index]
            self._control.setInterval(self._tick_ms())
            for backend in self.backends.values():
                backend.sim_rate = self.sim_rate
        self._publish()

    @Slot(bool)
    def set_paused(self, paused: bool) -> None:
        """Hold or resume both lines and the clock."""
        self.paused = bool(paused)
        for backend in self.backends.values():
            backend.paused = self.paused
        self._publish()
