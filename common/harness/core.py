"""The central harness: one clock, one tick at a time, every module.

The harness owns the system's one ``SystemClock`` (D017). On each tick
it sends every module ``dt``, the unwrapped simulation time and its
inputs, mapped from the outputs every module gave on the tick before,
and waits for every reply before the next tick (R1, R64). Each request
is answered once: a reply nobody is waiting for, or one that carries
the awaited request ID with another tick, is logged and ignored.

- A module that rejects a tick keeps its previous outputs, and the run
  goes on (R19).
- A module that has not replied after ``REPLY_SLOW_S`` is logged as
  slow, at most every ``SLOW_REPORT_INTERVAL_S`` per module, and shown
  as SLOW; the clock runs on.
- A module that has not replied after ``REPLY_TIMEOUT_S`` pauses the
  clock and is named. The clock resumes once the reply comes. A reply
  that does not decode, or is ignored, leaves the module waited on, so
  it too pauses the clock and names the module.
- A module that ends or drops its link holds the clock for the rest of
  the run, since modules are never restarted mid-run.

The clock runs only while every module is ready, none is late or down,
and the CTC Office asks it to run. The CTC Office's ``clock_paused``
and ``clock_speedup`` are read from its outputs and, while the clock is
paused, from its ``STATE`` (R3, R51).

Significant events go to the event log (R80), each also signalled as
``eventLogged``. Events, all from the harness's point of view:

- ``HARNESS_STARTED``, ``HARNESS_STOPPED``;
- ``MODULE_STARTED``, ``MODULE_READY``, ``ALL_READY``,
  ``STARTUP_TIMEOUT``;
- ``MODULE_DISCONNECTED``, ``MODULE_EXITED``, ``MODULE_KILLED``;
- ``CLOCK_PAUSED``, ``CLOCK_RESUMED``, ``SPEED_CHANGED``;
- ``TIME_SLIPPED``, ``TIME_SLIPPING``, ``TIME_SLIP_ENDED``: one slip
  behind real time, logged as an episode (``common.harness.slips``);
- ``TICK_REJECTED``, ``INPUTS_FAILED``, ``REPLY_SLOW``, ``REPLY_LATE``,
  ``LATE_REPLY_RECEIVED``, ``UNEXPECTED_REPLY``, ``PROTOCOL_ERROR``;
- ``EDGES_FAILED``, and whatever the edges report, such as
  ``TRAIN_ADDED`` and ``TRAIN_REMOVED`` (``common.harness.edges``).

The edges decide each module's inputs (D005). They see every tick's
new outputs once, when the tick is over, and build each module's
inputs from the outputs every module last gave.
"""

from __future__ import annotations

__all__ = [
    "PAUSED_KEY",
    "REPLY_SLOW_S",
    "REPLY_TIMEOUT_S",
    "SLOW_REPORT_INTERVAL_S",
    "SPEEDUP_KEY",
    "Edges",
    "Harness",
]

import time
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from PySide6.QtCore import QObject, QTimer, Signal

from common.harness.modules import CTC_OFFICE, ModuleSpec
from common.harness.pacer import TickPacer
from common.harness.slips import SlipEpisodes
from common.harness.stub_edges import StubEdges
from common.harness.supervisor import (
    QUIT_TIMEOUT_S,
    STARTUP_TIMEOUT_S,
    ModuleSupervisor,
)
from utils.event_log import EventLog
from utils.harness_protocol import (
    OUTPUTS,
    STATE,
    ProtocolError,
    show_message,
    step_message,
)
from utils.system_clock import SystemClock

#: Real seconds to wait for a reply before the clock pauses.
REPLY_TIMEOUT_S = 1.0
#: Real seconds without a reply before a module is logged as slow. The
#: clock runs on: this only warns before ``REPLY_TIMEOUT_S``.
REPLY_SLOW_S = 0.25
#: Fewest real seconds between two slow reports for one module.
SLOW_REPORT_INTERVAL_S = 10.0

#: The CTC Office's clock controls, in its outputs and its STATE
#: (``signals/clock-speedup``; ``clock-pause`` is pending).
PAUSED_KEY = "clock_paused"
SPEEDUP_KEY = "clock_speedup"

NORMAL_SPEED = 1
SPEEDUP_SPEED = 10
MILLISECONDS_PER_SECOND = 1000

HARNESS = "harness"


class Edges(Protocol):
    """How the harness builds each module's inputs (D005)."""

    def tick_completed(
        self,
        tick: int,
        sim_time_s: float,
        fresh: Mapping[str, Mapping[str, Any]],
    ) -> Sequence[tuple[str, str, str]]:
        """Take the outputs that came in on one tick, once.

        Args:
            tick: The tick that is over.
            sim_time_s: Its simulation time.
            fresh: The outputs each module replied with on that tick;
                a module that rejected the tick is absent.

        Returns:
            Events to log, as ``(source, event, detail)``.
        """

    def inputs_for(
        self,
        consumer: str,
        tick: int,
        sim_time_s: float,
        outputs: Mapping[str, Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        """Return one module's inputs for a tick.

        Args:
            consumer: The module about to step.
            tick: The tick it steps.
            sim_time_s: Simulation time at the end of the step.
            outputs: Every module's outputs from the last tick it
                completed.
        """


class Harness(QObject):
    """Run every module in step with one clock."""

    #: A tick is over: its number, and real seconds from the first
    #: ``STEP`` sent to the last reply.
    tickCompleted = Signal(int, float)
    #: Modules that have not replied in time.
    modulesLate = Signal(object)
    #: A module ended or dropped its link.
    moduleDown = Signal(str)
    #: Every module said ``READY``.
    allReady = Signal()
    #: An event was logged: source, event, detail.
    eventLogged = Signal(str, str, str)

    def __init__(
        self,
        specs: Sequence[ModuleSpec],
        log: EventLog,
        edges: Edges | None = None,
        *,
        reply_timeout_s: float = REPLY_TIMEOUT_S,
        reply_slow_s: float | None = REPLY_SLOW_S,
        slow_report_interval_s: float = SLOW_REPORT_INTERVAL_S,
        startup_timeout_s: float = STARTUP_TIMEOUT_S,
        parent: QObject | None = None,
    ) -> None:
        """Prepare a harness for ``specs``; ``start`` launches it.

        Args:
            specs: One per module.
            log: Where significant events go. The caller closes it.
            edges: Builds each module's inputs; by default each
                module gets its producers' outputs whole, as stubs
                expect.
            reply_timeout_s: Real seconds before a missing reply
                pauses the clock.
            reply_slow_s: Real seconds before a missing reply is
                logged as slow; None, or not under
                ``reply_timeout_s``, never warns.
            slow_report_interval_s: Fewest real seconds between two
                slow reports for one module.
            startup_timeout_s: Real seconds before modules that are
                not ready are reported.
            parent: Optional Qt parent.

        Raises:
            ValueError: If ``reply_slow_s`` is not positive.
        """
        super().__init__(parent)
        if reply_slow_s is not None and not reply_slow_s > 0:
            raise ValueError(
                f"reply_slow_s must be positive, got {reply_slow_s}"
            )
        if reply_slow_s is not None and reply_slow_s >= reply_timeout_s:
            reply_slow_s = None
        self._log = log
        self._log_path = str(log.path.resolve())
        self._edges: Edges = edges if edges is not None else StubEdges()
        self._reply_timeout_s = reply_timeout_s
        self._clock = SystemClock()
        self._pacer = TickPacer(self._clock, parent=self)
        self._slips = SlipEpisodes()
        self._supervisor = ModuleSupervisor(
            specs, startup_timeout_s=startup_timeout_s, parent=self
        )
        # Each module's outputs from the last tick it completed; a
        # module that rejects a tick keeps the ones before.
        self._outputs: dict[str, Mapping[str, Any]] = {}
        # Outputs that came in during the tick in flight. They become
        # inputs only on the next tick.
        self._tick_outputs: dict[str, Mapping[str, Any]] = {}
        # Request ID awaited from each module during the tick.
        self._pending: dict[str, int] = {}
        self._late: set[str] = set()
        # Modules slow to reply to the tick in flight, and for each,
        # when it was last reported and how many slow replies since.
        self._slow: set[str] = set()
        self._slow_reports: dict[str, tuple[float, int]] = {}
        self._reply_slow_s = reply_slow_s
        self._slow_report_interval_s = slow_report_interval_s
        self._down: set[str] = set()
        self._all_ready = False
        self._ctc_paused = True
        self._ctc_speedup = False
        self._next_request_id = 1
        self._tick_started_s = 0.0
        self._stopping = False
        self._exit_codes: dict[str, int | None] = {}
        self._pids: dict[str, int] = {}
        self._module_exits: dict[str, str] = {}
        self._startup_timed_out: tuple[str, ...] = ()
        self._reply_timer = QTimer(self)
        self._reply_timer.setSingleShot(True)
        self._reply_timer.setInterval(
            round(reply_timeout_s * MILLISECONDS_PER_SECOND)
        )
        self._reply_timer.timeout.connect(self._on_reply_timeout)
        self._slow_timer = QTimer(self)
        self._slow_timer.setSingleShot(True)
        if reply_slow_s is not None:
            self._slow_timer.setInterval(
                round(reply_slow_s * MILLISECONDS_PER_SECOND)
            )
        self._slow_timer.timeout.connect(self._on_reply_slow)
        self._clock.add_tick_listener(self._on_tick)
        self._clock.add_state_listener(self._broadcast_clock_state)
        self._pacer.backlogDropped.connect(self._on_backlog_dropped)
        supervisor = self._supervisor
        supervisor.moduleStarted.connect(self._on_module_started)
        supervisor.moduleReady.connect(self._on_module_ready)
        supervisor.allReady.connect(self._on_all_ready)
        supervisor.messageReceived.connect(self._on_message)
        supervisor.diagnosticReceived.connect(self._log_event)
        supervisor.protocolError.connect(self._on_protocol_error)
        supervisor.moduleDisconnected.connect(self._on_module_disconnected)
        supervisor.moduleExited.connect(self._on_module_exited)
        supervisor.moduleKilled.connect(self._on_module_killed)
        supervisor.startupTimedOut.connect(self._on_startup_timed_out)

    @property
    def clock(self) -> SystemClock:
        """The system's clock. Read it; the harness controls it."""
        return self._clock

    @property
    def server_name(self) -> str:
        """The local server modules connect to."""
        return self._supervisor.server_name

    @property
    def outputs(self) -> dict[str, Mapping[str, Any]]:
        """Each module's outputs from its last completed tick."""
        return dict(self._outputs)

    @property
    def ready_modules(self) -> tuple[str, ...]:
        """Modules that said ``READY`` and are still connected."""
        return self._supervisor.ready_modules

    @property
    def late_modules(self) -> frozenset[str]:
        """Modules the tick in flight is waiting on past the timeout."""
        return frozenset(self._late)

    @property
    def slow_modules(self) -> frozenset[str]:
        """Modules the tick in flight waits on past the slow warning."""
        return frozenset(self._slow)

    @property
    def down_modules(self) -> frozenset[str]:
        """Modules that ended or dropped their link."""
        return frozenset(self._down)

    @property
    def dropped_ticks(self) -> int:
        """Ticks real time earned that never ran.

        The run fell too far behind, paused with ticks owed, or ended
        with ticks owed; only the first two are a slip, logged as an
        episode. No module misses a tick; simulation time slips behind
        real time instead.
        """
        return self._pacer.dropped_ticks

    @property
    def actual_speed(self) -> float | None:
        """Simulated seconds per real second the run achieves.

        Measured over the last few seconds of running; None while the
        clock is paused or has only just started.
        """
        return self._pacer.actual_speed

    @property
    def lag_s(self) -> float:
        """Real seconds the run is behind real time, owed not dropped."""
        return self._pacer.lag_s

    @property
    def is_slipping(self) -> bool:
        """Whether a slip behind real time is going on."""
        return self._slips.is_slipping

    @property
    def log_path(self) -> str:
        """Return the CSV log's path."""
        return self._log_path

    @property
    def hold_reason(self) -> str | None:
        """Return why the clock is held, or None if it may run."""
        return self._hold_reason()

    @property
    def startup_timed_out_modules(self) -> tuple[str, ...]:
        """Return timed-out modules that are still not ready."""
        ready = self.ready_modules
        return tuple(n for n in self._startup_timed_out if n not in ready)

    @property
    def module_statuses(self) -> tuple[dict[str, Any], ...]:
        """Return independent rows describing each process and link.

        States are STARTING, READY, SLOW, LATE, DOWN or EXITED. An exit
        description retains the code, or explains why none exists.
        """
        ready = self.ready_modules
        rows = []
        for name in self._supervisor.module_names:
            state = "STARTING"
            if name in self._module_exits:
                state = "EXITED"
            elif name in self._down:
                state = "DOWN"
            elif name in self._late:
                state = "LATE"
            elif name in self._slow:
                state = "SLOW"
            elif name in ready:
                state = "READY"
            rows.append({
                "name": name,
                "state": state,
                "pid": self._pids.get(name),
                "exit": self._module_exits.get(name),
            })
        return tuple(rows)

    def show_window(self, module: str) -> bool:
        """Ask a connected module to reopen its window, without a tick.

        Return False if the run is stopping or the module is absent.
        """
        if self._stopping or module in self._down:
            return False
        return self._supervisor.send(
            module, show_message(self._clock.tick_count)
        )

    def start(self) -> None:
        """Start every module process; the clock waits for them.

        Raises:
            HarnessStartError: If the local server cannot listen.
        """
        names = self._supervisor.module_names
        self._log_event(
            HARNESS,
            "HARNESS_STARTED",
            f"{len(names)} modules; server {self.server_name}",
        )
        self._supervisor.start()
        self._pacer.start()

    def stop(
        self, timeout_s: float = QUIT_TIMEOUT_S
    ) -> dict[str, int | None]:
        """Stop the clock and end every module (R64).

        Blocks while modules quit. Calling it again does nothing more.

        Args:
            timeout_s: Real seconds modules have to quit before they
                are killed.

        Returns:
            Each module's exit code; None for one that crashed, was
            killed or never started.
        """
        if self._stopping:
            return dict(self._exit_codes)
        self._stopping = True
        self._reply_timer.stop()
        self._slow_timer.stop()
        self._pacer.stop()
        self._clock.pause()
        self._exit_codes = self._supervisor.stop(
            self._clock.tick_count, timeout_s
        )
        self._log_event(
            HARNESS,
            "HARNESS_STOPPED",
            "; ".join(
                f"{name} {_describe_exit(code)}"
                for name, code in self._exit_codes.items()
            ),
        )
        return dict(self._exit_codes)

    def _on_tick(self, sim_time_s: float, tick_s: float) -> None:
        # Fan out one tick: every ready module gets its inputs from the
        # outputs of the tick before, all at once.
        tick = self._clock.tick_count
        self._tick_outputs = {}
        self._pending = {}
        self._slow.clear()
        self._tick_started_s = time.perf_counter()
        for name in self._supervisor.ready_modules:
            try:
                inputs = self._edges.inputs_for(
                    name, tick, sim_time_s, self._outputs
                )
            except Exception as error:  # noqa: BLE001 - logged, run goes on
                # Like a rejection: the module skips the tick and keeps
                # its outputs.
                self._log_event(
                    name, "INPUTS_FAILED", f"{type(error).__name__}: {error}"
                )
                continue
            request_id = self._next_request_id
            self._next_request_id += 1
            message = step_message(
                request_id, tick, tick_s, sim_time_s, inputs
            )
            try:
                sent = self._supervisor.send(name, message)
            except ProtocolError as error:
                # Inputs JSON cannot carry, such as an infinity the
                # edges computed: as above, the module skips the tick,
                # and the modules after it still get theirs.
                self._log_event(name, "INPUTS_FAILED", str(error))
                continue
            if sent:
                self._pending[name] = request_id
        if self._pending:
            self._reply_timer.start()
            if self._reply_slow_s is not None:
                self._slow_timer.start()
        else:
            self._finish_tick()

    def _on_message(self, name: str, message: Mapping[str, Any]) -> None:
        # A reply to the tick in flight, or the CTC Office's STATE. A
        # reply must carry both the request ID and the tick it answers.
        if message["op"] == STATE:
            if name == CTC_OFFICE:
                self._read_clock_controls(message["state"])
                self._apply_clock_state()
            return
        if (
            self._pending.get(name) != message["id"]
            or message["tick"] != self._clock.tick_count
        ):
            self._log_event(
                name,
                "UNEXPECTED_REPLY",
                f"request {message['id']} of tick {message['tick']} "
                "is not awaited; ignored",
            )
            return
        del self._pending[name]
        self._slow.discard(name)
        if message["op"] == OUTPUTS:
            self._tick_outputs[name] = message["outputs"]
            if name == CTC_OFFICE:
                self._read_clock_controls(message["outputs"])
        else:
            self._log_event(name, "TICK_REJECTED", message["reason"])
        if name in self._late:
            self._late.discard(name)
            waited_s = time.perf_counter() - self._tick_started_s
            self._log_event(
                name, "LATE_REPLY_RECEIVED", f"after {waited_s:.2f} s"
            )
        if not self._pending:
            self._finish_tick()

    def _finish_tick(self) -> None:
        # Every reply is in: keep the outputs for the next tick, hand
        # the new ones to the edges once, apply the CTC Office's clock
        # controls, and let the next tick come.
        self._reply_timer.stop()
        self._slow_timer.stop()
        fresh, self._tick_outputs = self._tick_outputs, {}
        self._outputs.update(fresh)
        round_trip_s = time.perf_counter() - self._tick_started_s
        self._hand_to_edges(fresh)
        self._apply_clock_state()
        self.tickCompleted.emit(self._clock.tick_count, round_trip_s)
        self._pacer.tick_finished()
        if self._slips.is_slipping:
            self._log_slips(self._slips.ticked(
                time.perf_counter(),
                self._pacer.is_keeping_up,
                self._pacer.actual_speed,
            ))

    def _hand_to_edges(self, fresh: Mapping[str, Mapping[str, Any]]) -> None:
        # The edges see each tick's outputs exactly once, and say what
        # to log about them.
        try:
            events = self._edges.tick_completed(
                self._clock.tick_count, self._clock.sim_time_s, fresh
            )
        except Exception as error:  # noqa: BLE001 - logged, run goes on
            events = [
                (HARNESS, "EDGES_FAILED", f"{type(error).__name__}: {error}")
            ]
        for source, event, detail in events:
            self._log_event(source, event, detail)

    def _on_reply_slow(self) -> None:
        # Name every module not yet replied, at most once a report
        # interval each; the clock runs on.
        if self._stopping:
            return
        now_s = time.perf_counter()
        for name in self._supervisor.module_names:
            if name not in self._pending or name in self._late:
                continue
            self._slow.add(name)
            last_s, since = self._slow_reports.get(name, (None, 0))
            if (
                last_s is not None
                and now_s - last_s < self._slow_report_interval_s
            ):
                self._slow_reports[name] = (last_s, since + 1)
                continue
            detail = (
                f"no reply to tick {self._clock.tick_count} after "
                f"{self._reply_slow_s:.2f} s; the clock runs on"
            )
            if since:
                detail += (
                    f"; {since} more slow replies since the last report"
                )
            self._slow_reports[name] = (now_s, 0)
            self._log_event(name, "REPLY_SLOW", detail)

    def _on_reply_timeout(self) -> None:
        # Pause the clock and name every module not yet replied.
        late = [
            name
            for name in self._supervisor.module_names
            if name in self._pending
        ]
        self._late.update(late)
        self._slow.difference_update(late)
        for name in late:
            self._log_event(
                name,
                "REPLY_LATE",
                f"no reply to tick {self._clock.tick_count} "
                f"after {self._reply_timeout_s:.1f} s",
            )
        self._apply_clock_state()
        self.modulesLate.emit(late)

    def _read_clock_controls(self, values: Mapping[str, Any]) -> None:
        # Take the CTC Office's latest clock_paused and clock_speedup,
        # in the order its messages came.
        for key in (PAUSED_KEY, SPEEDUP_KEY):
            if key not in values:
                continue
            value = values[key]
            if not isinstance(value, bool):
                self._log_event(
                    CTC_OFFICE,
                    "PROTOCOL_ERROR",
                    f"{key} must be true or false, got {value!r}",
                )
            elif key == PAUSED_KEY:
                self._ctc_paused = value
            else:
                self._ctc_speedup = value

    def _send_clock_state(self, module: str) -> None:
        if self._stopping:
            return
        self._supervisor.send(module, {
            "op": "CLOCK_STATE", "id": 0, "tick": self._clock.tick_count,
            "state": {"clock_paused": self._clock.is_paused,
                      "clock_speedup": self._clock.speed == SPEEDUP_SPEED},
        })

    def _broadcast_clock_state(self) -> None:
        if self._stopping:
            return
        for module in self.ready_modules:
            if module in {"track-controller-hw", "train-controller-hw"}:
                self._send_clock_state(module)

    def _apply_clock_state(self) -> None:
        # Set the clock's speed, then run or hold it.
        if self._stopping:
            return
        speed = SPEEDUP_SPEED if self._ctc_speedup else NORMAL_SPEED
        if speed != self._clock.speed:
            self._clock.set_speed(speed)
            self._log_event(HARNESS, "SPEED_CHANGED", f"{speed}x")
        reason = self._hold_reason()
        if reason is None and self._clock.is_paused:
            self._clock.resume()
            self._log_event(HARNESS, "CLOCK_RESUMED", f"{speed}x")
        elif reason is not None and not self._clock.is_paused:
            self._clock.pause()
            self._log_slips(self._slips.held())
            self._log_event(HARNESS, "CLOCK_PAUSED", reason)

    def _hold_reason(self) -> str | None:
        # Why the clock must not run, or None if it may.
        if self._down:
            return "down: " + ", ".join(sorted(self._down))
        if self._late:
            return "waiting on " + ", ".join(sorted(self._late))
        if not self._all_ready:
            return "waiting for every module to be ready"
        if self._ctc_paused:
            return f"paused by {CTC_OFFICE}"
        return None

    def _mark_down(self, name: str) -> None:
        # A module is gone for the rest of the run. The tick in flight
        # finishes without it, and it keeps its last outputs.
        if self._stopping or name in self._down:
            return
        self._down.add(name)
        self._late.discard(name)
        self._slow.discard(name)
        awaited = self._pending.pop(name, None) is not None
        if awaited and not self._pending:
            self._finish_tick()
        else:
            self._apply_clock_state()
        self.moduleDown.emit(name)

    def _on_module_started(self, name: str, pid: int) -> None:
        # The process is up; READY comes once it can step.
        self._pids[name] = pid
        self._log_event(name, "MODULE_STARTED", f"pid {pid}")

    def _on_module_ready(self, name: str) -> None:
        # One more module can step.
        self._log_event(name, "MODULE_READY")
        if name in {"track-controller-hw", "train-controller-hw"}:
            self._send_clock_state(name)

    def _on_all_ready(self) -> None:
        # The clock may run from now on, once the CTC Office asks.
        self._all_ready = True
        self._log_event(HARNESS, "ALL_READY")
        self._apply_clock_state()
        self.allReady.emit()

    def _on_startup_timed_out(self, names: list[str]) -> None:
        # Name the stragglers; the harness keeps waiting for them.
        self._startup_timed_out = tuple(names)
        self._log_event(
            HARNESS, "STARTUP_TIMEOUT", "not ready: " + ", ".join(names)
        )

    def _on_protocol_error(self, source: str, text: str) -> None:
        # A bad line or message; whatever it was is ignored.
        self._log_event(source, "PROTOCOL_ERROR", text)

    def _on_module_disconnected(self, name: str) -> None:
        # A link closing on its own means the module is gone; during
        # shutdown it is expected, and the exit says the rest.
        if self._stopping:
            return
        self._log_event(name, "MODULE_DISCONNECTED")
        self._mark_down(name)

    def _on_module_exited(self, name: str, how: str) -> None:
        # Logged during shutdown too, for the exit code.
        self._module_exits[name] = how
        self._log_event(name, "MODULE_EXITED", how)
        self._mark_down(name)

    def _on_module_killed(self, name: str) -> None:
        # It did not quit in time.
        self._log_event(name, "MODULE_KILLED", "did not quit in time")

    def _on_backlog_dropped(self, count: int) -> None:
        # The run fell too far behind, or paused with ticks owed. Ticks
        # owed when the run ends are not a slip: nothing was behind.
        if self._stopping:
            return
        self._log_slips(self._slips.dropped(
            time.perf_counter(), count, self._pacer.actual_speed
        ))

    def _log_slips(self, events: Sequence[tuple[str, str]]) -> None:
        # What the slip tracker says, from the harness.
        for event, detail in events:
            self._log_event(HARNESS, event, detail)

    def _log_event(self, source: str, event: str, detail: str = "") -> None:
        # One row in the event log, stamped with the clock's time.
        self._log.write(
            sim_time_s=self._clock.sim_time_s,
            tick=self._clock.tick_count,
            source=source,
            event=event,
            detail=detail,
        )
        self.eventLogged.emit(source, event, detail)


def _describe_exit(code: int | None) -> str:
    # How a module ended, for the log. No code means it crashed, was
    # killed, or never started.
    if code is None:
        return "no exit code"
    return f"exit code {code}"
