"""Faulty replies from module processes, played in the test process.

Each test runs the harness with three fake modules: local sockets in
this process that say ``READY`` and answer every ``STEP``, except where
a test scripts a raw reply instead. No module process starts, so a
test can send bytes no real module would: numbers JSON cannot carry,
text that is not valid Unicode, a line past the length limit, or a
reply for the wrong tick.

Whatever comes, the harness must log it, keep reading the link, and
never show the clock running while nothing advances: a missing reply
pauses the clock and names the module, as a late one does.

Run from the repository root with
``python -m unittest discover -s common/harness/tests``.
"""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer  # noqa: E402
from PySide6.QtNetwork import QLocalSocket  # noqa: E402

from common.harness.core import Harness  # noqa: E402
from common.harness.modules import (  # noqa: E402
    CTC_OFFICE,
    TRACK_MODEL,
    TRAIN_MODEL,
    ModuleSpec,
)
from common.harness.slips import SlipEpisodes  # noqa: E402
from common.harness.stub_edges import StubEdges  # noqa: E402
from utils.event_log import EventLog  # noqa: E402
from utils.harness_protocol import (  # noqa: E402
    MAX_LINE_BYTES,
    STEP,
    LineBuffer,
    ProtocolError,
    decode,
    encode,
    outputs_message,
    ready_message,
    rejected_message,
    state_message,
)

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])

# Start order; the tick's STEPs go out in this order.
NAMES = (CTC_OFFICE, TRAIN_MODEL, TRACK_MODEL)
# The tick a fault is scripted at.
FAULT_TICK = 3
WAIT_S = 10.0
# Long enough for the reply timer, set short below, to fire.
SETTLE_S = 0.8
REPLY_TIMEOUT_S = 0.3

# Builds the raw bytes a fake module sends for one STEP.
Script = Callable[[Mapping[str, Any]], bytes]


def wait_until(
    condition: Callable[[], bool], timeout_s: float = WAIT_S
) -> bool:
    """Run the event loop until ``condition`` holds or time runs out."""
    deadline = time.monotonic() + timeout_s
    while not condition():
        if time.monotonic() > deadline:
            return False
        _APP.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
    return True


def outputs_line(step: Mapping[str, Any], **outputs: Any) -> bytes:
    """Return a valid ``OUTPUTS`` line answering ``step``."""
    return encode(outputs_message(step["id"], step["tick"], outputs))


class _FakeModule:
    """One module's end of the link, answering from this process."""

    def __init__(self, name: str, server_name: str) -> None:
        self.name = name
        # Raw replies by tick, and how long to hold each back.
        self.scripts: dict[int, Script] = {}
        self.delay_ms: dict[int, int] = {}
        self._delayed: list[QTimer] = []
        self.steps: list[dict[str, Any]] = []
        self._buffer = LineBuffer()
        self._socket = QLocalSocket()
        self._socket.readyRead.connect(self._on_ready_read)
        self._socket.connectToServer(server_name)
        if not self._socket.waitForConnected(round(WAIT_S * 1000)):
            raise AssertionError(f"{name} could not connect")
        self.send(encode(ready_message(name)))

    def send(self, data: bytes) -> None:
        """Write raw bytes to the harness."""
        self._socket.write(data)
        self._socket.flush()

    def close(self) -> None:
        """Drop the link."""
        for timer in self._delayed:
            timer.stop()
        self._delayed.clear()
        self._socket.abort()
        self._socket.deleteLater()

    def _on_ready_read(self) -> None:
        # Answer every STEP: as scripted, or with plain outputs.
        for line in self._buffer.feed(bytes(self._socket.readAll().data())):
            assert not isinstance(line, ProtocolError), line
            message = decode(line)
            if message["op"] != STEP:
                continue
            self.steps.append(message)
            tick = message["tick"]
            script = self.scripts.get(tick, self._plain)
            data = script(message)
            delay_ms = self.delay_ms.get(tick)
            if delay_ms is None:
                self.send(data)
            else:
                timer = QTimer(self._socket)
                timer.setSingleShot(True)
                timer.timeout.connect(lambda payload=data: self.send(payload))
                self._delayed.append(timer)
                timer.start(delay_ms)

    def _plain(self, step: Mapping[str, Any]) -> bytes:
        # The CTC Office keeps the clock running.
        if self.name == CTC_OFFICE:
            return outputs_line(step, tick=step["tick"], clock_paused=False)
        return outputs_line(step, tick=step["tick"])


class _Run:
    """The harness, its fake modules and what it logged."""

    def __init__(self, edges: Any = None, **options: Any) -> None:
        self._folder = tempfile.TemporaryDirectory()
        self.log = EventLog(Path(self._folder.name) / "events.csv")
        self.harness = Harness(
            [ModuleSpec(name, ()) for name in NAMES],
            self.log,
            edges,
            reply_timeout_s=REPLY_TIMEOUT_S,
            **options,
        )
        # The fakes stand in for the processes.
        self.harness._supervisor._launch = (  # type: ignore[method-assign]
            lambda spec: None
        )
        self.events: list[tuple[int, str, str, str]] = []
        self.completed: list[int] = []
        self.harness.eventLogged.connect(self._on_event)
        self.harness.tickCompleted.connect(
            lambda tick, _s: self.completed.append(tick)
        )
        self.harness.start()
        self.fakes = {
            name: _FakeModule(name, self.harness.server_name)
            for name in NAMES
        }

    def _on_event(self, source: str, event: str, detail: str) -> None:
        self.events.append(
            (self.harness.clock.tick_count, source, event, detail)
        )

    def run(self) -> None:
        """Press Run, once every module is ready."""
        if not wait_until(lambda: len(self.harness.ready_modules) == 3):
            raise AssertionError(f"not ready: {self.events}")
        self.fakes[CTC_OFFICE].send(
            encode(state_message(0, {"clock_paused": False}))
        )

    def find(self, event: str) -> list[tuple[int, str, str, str]]:
        """Return every logged ``event``."""
        return [each for each in self.events if each[2] == event]

    def settle(self) -> None:
        """Run the event loop past the reply timeout."""
        wait_until(lambda: False, timeout_s=SETTLE_S)

    def clean_up(self) -> None:
        """Stop the harness, drop the fakes and remove the log."""
        self.harness.stop(timeout_s=0.5)
        for fake in self.fakes.values():
            fake.close()
        self.log.close()
        self._folder.cleanup()


class _FaultTest(unittest.TestCase):
    """One run per test, cleaned up after it."""

    edges: Any = None
    #: Further Harness options for each test's run.
    harness_options: dict[str, Any] = {}

    def setUp(self) -> None:
        self.run_ = _Run(self.edges, **self.harness_options)
        self.addCleanup(self.run_.clean_up)

    def assert_held_on(self, module: str) -> None:
        """The clock is paused, and the reason names ``module``."""
        harness = self.run_.harness
        self.assertTrue(harness.clock.is_paused, self.run_.events)
        self.assertIn(module, harness.hold_reason or "")
        self.assertIn(module, harness.late_modules)
        self.assertEqual(harness.clock.tick_count, FAULT_TICK)

    def assert_every_module_stepped_every_tick(self) -> None:
        """No module missed a tick that ran."""
        last = self.run_.harness.clock.tick_count
        for fake in self.run_.fakes.values():
            self.assertEqual(
                [step["tick"] for step in fake.steps],
                list(range(1, last + 1)),
                fake.name,
            )


class OverflowingNumberTest(_FaultTest):
    """A number JSON cannot carry never reaches another module."""

    def test_infinite_output_is_refused_and_names_the_module(self) -> None:
        # 1e999 is valid JSON text but no finite number. Accepted, it
        # broke the next STEP to every module fed from it, unlogged,
        # and the clock went on showing RUNNING.
        fake = self.run_.fakes[TRAIN_MODEL]
        fake.scripts[FAULT_TICK] = lambda step: (
            b'{"op":"OUTPUTS","id":%d,"tick":%d,"outputs":{"v":1e999}}\n'
            % (step["id"], step["tick"])
        )
        self.run_.run()
        self.run_.settle()
        errors = self.run_.find("PROTOCOL_ERROR")
        self.assertEqual([e[1] for e in errors], [TRAIN_MODEL])
        self.assertIn("out of range", errors[0][3])
        self.assertEqual(
            [e[1] for e in self.run_.find("REPLY_LATE")], [TRAIN_MODEL]
        )
        self.assert_held_on(TRAIN_MODEL)
        self.assert_every_module_stepped_every_tick()

    def test_huge_integer_output_is_refused(self) -> None:
        # Past the largest double: no consumer could use it as a number.
        fake = self.run_.fakes[TRAIN_MODEL]
        fake.scripts[FAULT_TICK] = lambda step: (
            b'{"op":"OUTPUTS","id":%d,"tick":%d,"outputs":{"v":%s}}\n'
            % (step["id"], step["tick"], b"9" * 400)
        )
        self.run_.run()
        self.run_.settle()
        self.assertEqual(
            [e[1] for e in self.run_.find("PROTOCOL_ERROR")], [TRAIN_MODEL]
        )
        self.assert_held_on(TRAIN_MODEL)


class _InfiniteEdges(StubEdges):
    """Edges whose mapping overflows for the Track Model at one tick."""

    def inputs_for(
        self,
        consumer: str,
        tick: int,
        sim_time_s: float,
        outputs: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        inputs = super().inputs_for(consumer, tick, sim_time_s, outputs)
        if consumer == TRAIN_MODEL and tick == FAULT_TICK:
            return {**inputs, "speed": 1e308 * 10}
        return inputs


class UnencodableInputsTest(_FaultTest):
    """Inputs the edges built but JSON cannot carry are logged."""

    edges = _InfiniteEdges()

    def test_module_skips_the_tick_and_the_rest_step_on(self) -> None:
        # The infinity raised out of the tick's fan-out: the modules
        # after it got no STEP, and nothing was logged.
        self.run_.run()
        self.assertTrue(wait_until(
            lambda: FAULT_TICK + 2 in self.run_.completed
        ), self.run_.events)
        failed = self.run_.find("INPUTS_FAILED")
        self.assertEqual(
            [(e[0], e[1]) for e in failed], [(FAULT_TICK, TRAIN_MODEL)]
        )
        for name in (CTC_OFFICE, TRACK_MODEL):
            ticks = [step["tick"] for step in self.run_.fakes[name].steps]
            self.assertIn(FAULT_TICK, ticks, name)
        train_ticks = [
            step["tick"] for step in self.run_.fakes[TRAIN_MODEL].steps
        ]
        self.assertNotIn(FAULT_TICK, train_ticks)
        self.assertIn(FAULT_TICK + 1, train_ticks)


class InvalidUnicodeTest(_FaultTest):
    """Text that is not valid Unicode is refused, not choked on."""

    def script_last_reply(self, data: Callable[[int, int], bytes]) -> None:
        # The Track Model replies last, so its reply ends the tick.
        fake = self.run_.fakes[TRACK_MODEL]
        fake.scripts[FAULT_TICK] = lambda step: data(
            step["id"], step["tick"]
        )
        fake.delay_ms[FAULT_TICK] = 50

    def test_lone_surrogate_is_refused_and_names_the_module(self) -> None:
        # Bytes that were not UTF-8, carried as an escaped surrogate,
        # as Python's surrogateescape makes them. Accepted, the event
        # log could not write the reason, the tick never ended, and
        # the clock went on showing RUNNING.
        self.script_last_reply(lambda request, tick: (
            b'{"op":"REJECTED","id":%d,"tick":%d,"reason":"bad \\udcff"}\n'
            % (request, tick)
        ))
        self.run_.run()
        self.run_.settle()
        errors = self.run_.find("PROTOCOL_ERROR")
        self.assertEqual([e[1] for e in errors], [TRACK_MODEL])
        self.assertIn("Unicode", errors[0][3])
        self.assert_held_on(TRACK_MODEL)

    def test_bytes_that_are_not_utf8_name_the_module(self) -> None:
        self.script_last_reply(lambda request, tick: (
            b'{"op":"OUTPUTS","id":%d,"tick":%d,"outputs":{"v":"\xff"}}\n'
            % (request, tick)
        ))
        self.run_.run()
        self.run_.settle()
        self.assertEqual(
            [e[1] for e in self.run_.find("PROTOCOL_ERROR")], [TRACK_MODEL]
        )
        self.assert_held_on(TRACK_MODEL)


class FramingTest(_FaultTest):
    """A bad line costs only itself; the lines after it still count."""

    def test_overlong_line_then_reply_in_one_write(self) -> None:
        # Past the length limit, the whole read was thrown away and
        # the link closed: the reply after it was lost, and the module
        # was taken for gone.
        filler = b"x" * (MAX_LINE_BYTES + 1)
        self.run_.fakes[TRAIN_MODEL].scripts[FAULT_TICK] = lambda step: (
            filler + b"\n" + outputs_line(step, tick=step["tick"])
        )
        self.run_.run()
        self.assertTrue(wait_until(
            lambda: FAULT_TICK + 2 in self.run_.completed
        ), self.run_.events)
        errors = self.run_.find("PROTOCOL_ERROR")
        self.assertEqual([e[1] for e in errors], [TRAIN_MODEL])
        self.assertIn("longer than the limit", errors[0][3])
        self.assertEqual(self.run_.find("MODULE_DISCONNECTED"), [])
        self.assertEqual(self.run_.harness.down_modules, frozenset())
        self.assertEqual(self.run_.find("REPLY_LATE"), [])

    def test_malformed_line_then_reply_in_one_write(self) -> None:
        self.run_.fakes[TRAIN_MODEL].scripts[FAULT_TICK] = lambda step: (
            b"{not json\n" + outputs_line(step, tick=step["tick"])
        )
        self.run_.run()
        self.assertTrue(wait_until(
            lambda: FAULT_TICK + 2 in self.run_.completed
        ), self.run_.events)
        self.assertEqual(
            [e[1] for e in self.run_.find("PROTOCOL_ERROR")], [TRAIN_MODEL]
        )
        self.assertEqual(self.run_.find("REPLY_LATE"), [])


class WrongTickTest(_FaultTest):
    """A reply must carry both the request ID and the tick it answers."""

    def test_reply_for_another_tick_is_not_taken(self) -> None:
        # The right request ID with the wrong tick was taken as the
        # tick's outputs.
        fake = self.run_.fakes[TRAIN_MODEL]
        fake.scripts[FAULT_TICK] = lambda step: encode(outputs_message(
            step["id"], step["tick"] + 7, {"bogus": True}
        ))
        self.run_.run()
        self.run_.settle()
        unexpected = self.run_.find("UNEXPECTED_REPLY")
        self.assertEqual([e[1] for e in unexpected], [TRAIN_MODEL])
        self.assertIn(f"tick {FAULT_TICK + 7}", unexpected[0][3])
        self.assertNotIn(
            "bogus", self.run_.harness.outputs.get(TRAIN_MODEL, {})
        )
        self.assert_held_on(TRAIN_MODEL)

    def test_correct_reply_after_a_wrong_one_ends_the_tick(self) -> None:
        fake = self.run_.fakes[TRAIN_MODEL]
        fake.scripts[FAULT_TICK] = lambda step: encode(rejected_message(
            step["id"], step["tick"] - 1, "stale"
        )) + outputs_line(step, tick=step["tick"])
        self.run_.run()
        self.assertTrue(wait_until(
            lambda: FAULT_TICK + 2 in self.run_.completed
        ), self.run_.events)
        self.assertEqual(
            [e[1] for e in self.run_.find("UNEXPECTED_REPLY")], [TRAIN_MODEL]
        )
        self.assertEqual(self.run_.find("TICK_REJECTED"), [])


class StopWithTicksOwedTest(_FaultTest):
    """Ticks owed when the run ends are dropped, but are not a slip."""

    def test_stopping_logs_no_time_slipped(self) -> None:
        run = self.run_
        harness = run.harness
        # The Train Model holds tick FAULT_TICK's reply past the stop,
        # so real time goes on earning ticks while it is in flight.
        run.fakes[TRAIN_MODEL].delay_ms[FAULT_TICK] = 5000
        run.run()
        # 10x: a tick falls due every 10 ms.
        run.fakes[CTC_OFFICE].send(encode(state_message(
            0, {"clock_paused": False, "clock_speedup": True}
        )))
        self.assertTrue(wait_until(
            lambda: harness.clock.tick_count == FAULT_TICK
        ), run.events)
        # Well inside the reply timeout, with several ticks owed.
        wait_until(lambda: False, timeout_s=REPLY_TIMEOUT_S / 2)
        self.assertFalse(harness.clock.is_paused, run.events)
        harness.stop(timeout_s=0.5)
        self.assertGreater(harness.dropped_ticks, 0)
        self.assertEqual(run.find("TIME_SLIPPED"), [])
        self.assertEqual(run.events[-1][2], "HARNESS_STOPPED")


class ReplyTimeoutRegressionTest(_FaultTest):
    """What the reply timeout does, which a soft warning must not change.

    Only a reply missing past ``REPLY_TIMEOUT_S`` pauses the clock and
    names the module; the clock resumes when it comes, and no module
    misses a tick either way.
    """

    def ticks_past_the_fault(self) -> None:
        """Run until three ticks after the scripted one are over."""
        self.assertTrue(wait_until(
            lambda: FAULT_TICK + 3 in self.run_.completed
        ), self.run_.events)

    def events_from(self, tick: int) -> list[tuple[str, str, str]]:
        """Every event logged at ``tick`` or later, without the tick."""
        return [
            (source, event, detail)
            for at, source, event, detail in self.run_.events
            if at >= tick
        ]

    def test_slow_reply_inside_the_limit_neither_pauses_nor_names(
        self,
    ) -> None:
        run = self.run_
        run.fakes[TRAIN_MODEL].delay_ms[FAULT_TICK] = 200
        run.run()
        self.ticks_past_the_fault()
        events = [event for _s, event, _d in self.events_from(1)]
        self.assertNotIn("REPLY_LATE", events)
        self.assertNotIn("CLOCK_PAUSED", events)
        self.assertNotIn("LATE_REPLY_RECEIVED", events)
        self.assertEqual(run.harness.late_modules, frozenset())
        self.assertIsNone(run.harness.hold_reason)
        self.assertEqual(
            run.harness.outputs[TRAIN_MODEL]["tick"],
            run.harness.clock.tick_count,
        )
        self.assert_every_module_stepped_every_tick()

    def test_reply_past_the_limit_pauses_names_then_resumes(self) -> None:
        run = self.run_
        run.fakes[TRAIN_MODEL].delay_ms[FAULT_TICK] = 600
        run.run()
        self.ticks_past_the_fault()
        at_fault = [
            (source, event)
            for source, event, _detail in self.events_from(FAULT_TICK)
            if event in (
                "REPLY_LATE", "CLOCK_PAUSED",
                "LATE_REPLY_RECEIVED", "CLOCK_RESUMED",
            )
        ]
        self.assertEqual(at_fault, [
            (TRAIN_MODEL, "REPLY_LATE"),
            ("harness", "CLOCK_PAUSED"),
            (TRAIN_MODEL, "LATE_REPLY_RECEIVED"),
            ("harness", "CLOCK_RESUMED"),
        ])
        late = run.find("REPLY_LATE")
        self.assertEqual(
            late[0][3],
            f"no reply to tick {FAULT_TICK} after {REPLY_TIMEOUT_S:.1f} s",
        )
        self.assertEqual(
            run.find("CLOCK_PAUSED")[-1][3], f"waiting on {TRAIN_MODEL}"
        )
        self.assertRegex(
            run.find("LATE_REPLY_RECEIVED")[0][3], r"^after 0\.\d\d s$"
        )
        self.assertEqual(run.harness.late_modules, frozenset())
        self.assertFalse(run.harness.clock.is_paused)
        self.assert_every_module_stepped_every_tick()

    def test_every_late_module_is_named(self) -> None:
        run = self.run_
        run.fakes[TRAIN_MODEL].delay_ms[FAULT_TICK] = 600
        run.fakes[TRACK_MODEL].delay_ms[FAULT_TICK] = 700
        run.run()
        self.ticks_past_the_fault()
        self.assertEqual(
            sorted(source for _t, source, _e, _d in run.find("REPLY_LATE")),
            sorted([TRAIN_MODEL, TRACK_MODEL]),
        )
        self.assertEqual(
            run.find("CLOCK_PAUSED")[-1][3],
            "waiting on " + ", ".join(sorted([TRACK_MODEL, TRAIN_MODEL])),
        )
        # The clock waits for the last of them.
        self.assertEqual(len(run.find("CLOCK_RESUMED")), 2)
        self.assert_every_module_stepped_every_tick()


class SlowReplyTest(_FaultTest):
    """A slow reply is named early, and the clock runs on."""

    harness_options = {"reply_slow_s": 0.1}

    def test_slow_reply_is_named_and_the_clock_runs_on(self) -> None:
        run = self.run_
        harness = run.harness
        run.fakes[TRAIN_MODEL].delay_ms[FAULT_TICK] = 250
        run.run()
        self.assertTrue(wait_until(
            lambda: TRAIN_MODEL in harness.slow_modules
        ), run.events)
        row = next(
            r for r in harness.module_statuses if r["name"] == TRAIN_MODEL
        )
        self.assertEqual(row["state"], "SLOW")
        self.assertFalse(harness.clock.is_paused)
        self.assertTrue(wait_until(
            lambda: FAULT_TICK + 3 in run.completed
        ), run.events)
        slow = run.find("REPLY_SLOW")
        self.assertEqual(slow, [(
            FAULT_TICK, TRAIN_MODEL, "REPLY_SLOW",
            f"no reply to tick {FAULT_TICK} after 0.10 s; "
            "the clock runs on",
        )])
        self.assertEqual(harness.slow_modules, frozenset())
        self.assertEqual(run.find("REPLY_LATE"), [])
        self.assertEqual(run.find("CLOCK_PAUSED"), [])
        self.assert_every_module_stepped_every_tick()

    def test_slow_replies_are_reported_at_most_once_an_interval(
        self,
    ) -> None:
        run = self.run_
        for tick in range(FAULT_TICK, FAULT_TICK + 5):
            run.fakes[TRAIN_MODEL].delay_ms[tick] = 150
        run.run()
        self.assertTrue(wait_until(
            lambda: FAULT_TICK + 6 in run.completed
        ), run.events)
        # Five slow replies inside one interval: one report.
        self.assertEqual(
            [e[1] for e in run.find("REPLY_SLOW")], [TRAIN_MODEL]
        )

    def test_a_module_that_replies_is_no_longer_slow(self) -> None:
        # Both slow; the Train Model replies first while the Track
        # Model is still awaited.
        run = self.run_
        harness = run.harness
        run.fakes[TRAIN_MODEL].delay_ms[FAULT_TICK] = 200
        run.fakes[TRACK_MODEL].delay_ms[FAULT_TICK] = 600
        seen: list[frozenset[str]] = []

        def after_reply(name: str, message: Mapping[str, Any]) -> None:
            # Connected after the harness's own slot, so it runs once
            # the harness has taken the reply.
            if name == TRAIN_MODEL and message.get("tick") == FAULT_TICK:
                seen.append(harness.slow_modules)

        harness._supervisor.messageReceived.connect(after_reply)
        run.run()
        self.assertTrue(wait_until(
            lambda: FAULT_TICK + 2 in run.completed
        ), run.events)
        self.assertEqual(seen, [frozenset({TRACK_MODEL})])

    def test_a_late_module_is_slow_first_then_late(self) -> None:
        run = self.run_
        harness = run.harness
        run.fakes[TRAIN_MODEL].delay_ms[FAULT_TICK] = 600
        run.run()
        self.assertTrue(wait_until(
            lambda: TRAIN_MODEL in harness.late_modules
        ), run.events)
        row = next(
            r for r in harness.module_statuses if r["name"] == TRAIN_MODEL
        )
        self.assertEqual(row["state"], "LATE")
        self.assertEqual(harness.slow_modules, frozenset())
        self.assertTrue(wait_until(
            lambda: FAULT_TICK + 2 in run.completed
        ), run.events)
        names = [
            event for _t, source, event, _d in run.events
            if source == TRAIN_MODEL
            and event in ("REPLY_SLOW", "REPLY_LATE", "LATE_REPLY_RECEIVED")
        ]
        self.assertEqual(
            names, ["REPLY_SLOW", "REPLY_LATE", "LATE_REPLY_RECEIVED"]
        )


class SlowReportIntervalTest(_FaultTest):
    """A slow module goes on being reported, with a count between."""

    harness_options = {"reply_slow_s": 0.05, "slow_report_interval_s": 0.4}

    def test_reports_repeat_with_what_was_held_back(self) -> None:
        run = self.run_
        for tick in range(FAULT_TICK, FAULT_TICK + 12):
            run.fakes[TRAIN_MODEL].delay_ms[tick] = 100
        run.run()
        self.assertTrue(wait_until(
            lambda: FAULT_TICK + 13 in run.completed
        ), run.events)
        slow = run.find("REPLY_SLOW")
        self.assertGreaterEqual(len(slow), 2, run.events)
        self.assertLess(len(slow), 12)
        self.assertNotIn("more slow replies", slow[0][3])
        self.assertRegex(
            slow[1][3], r"; \d+ more slow replies since the last report$"
        )
        self.assertEqual(run.find("CLOCK_PAUSED"), [])


class SlowWarningOffTest(_FaultTest):
    """With no soft limit, or one not under the timeout, no warning."""

    harness_options = {"reply_slow_s": None}

    def test_no_warning_without_a_soft_limit(self) -> None:
        run = self.run_
        run.fakes[TRAIN_MODEL].delay_ms[FAULT_TICK] = 250
        run.run()
        self.assertTrue(wait_until(
            lambda: FAULT_TICK + 2 in run.completed
        ), run.events)
        self.assertEqual(run.find("REPLY_SLOW"), [])

    def test_soft_limit_at_or_past_the_timeout_never_warns(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        log = EventLog(Path(folder.name) / "events.csv")
        self.addCleanup(log.close)
        harness = Harness(
            [ModuleSpec(name, ()) for name in NAMES], log,
            reply_timeout_s=0.3, reply_slow_s=0.3,
        )
        self.assertIsNone(harness._reply_slow_s)
        for bad in (0.0, -1.0):
            with self.subTest(reply_slow_s=bad):
                with self.assertRaises(ValueError):
                    Harness(
                        [ModuleSpec(name, ()) for name in NAMES], log,
                        reply_slow_s=bad,
                    )


class SlowModuleSlipTest(_FaultTest):
    """A module too slow for 10x slips the run; no module notices."""

    # Each slow reply is under the reply timeout, so the clock never
    # pauses, but together they leave the run far behind real time.
    SLOW_TICKS = range(FAULT_TICK, FAULT_TICK + 8)
    SLOW_MS = 200

    def test_slip_drops_real_time_not_ticks(self) -> None:
        run = self.run_
        harness = run.harness
        for tick in self.SLOW_TICKS:
            run.fakes[TRAIN_MODEL].delay_ms[tick] = self.SLOW_MS
        run.run()
        run.fakes[CTC_OFFICE].send(encode(state_message(
            0, {"clock_paused": False, "clock_speedup": True}
        )))
        last_slow = self.SLOW_TICKS[-1]
        self.assertTrue(wait_until(
            lambda: last_slow + 20 in run.completed
        ), run.events)
        # The run slipped and said so.
        self.assertGreater(harness.dropped_ticks, 0, run.events)
        slipped = run.find("TIME_SLIPPED")
        self.assertTrue(slipped, run.events)
        self.assertRegex(slipped[0][3], r"^\d+ ticks behind real time")
        # It did not pause: nothing was late.
        self.assertEqual(run.find("REPLY_LATE"), [])
        self.assertFalse(harness.clock.is_paused, run.events)
        # Every module saw every tick, with one dt and the clock's time.
        self.assert_every_module_stepped_every_tick()
        start_s = harness.clock.sim_time_s - harness.clock.elapsed_s
        for fake in run.fakes.values():
            for step in fake.steps:
                self.assertEqual(step["dt"], harness.clock.tick_s)
                self.assertAlmostEqual(
                    step["sim_time_s"],
                    start_s + step["tick"] * step["dt"],
                    places=6,
                )

    def test_a_slip_is_one_episode(self) -> None:
        run = self.run_
        harness = run.harness
        # Short enough to see a slip end within the test.
        quiet_s = 0.3
        harness._slips = SlipEpisodes(report_interval_s=60, quiet_s=quiet_s)
        slow_ticks = range(FAULT_TICK, FAULT_TICK + 12)
        for tick in slow_ticks:
            run.fakes[TRAIN_MODEL].delay_ms[tick] = self.SLOW_MS
        run.run()
        run.fakes[CTC_OFFICE].send(encode(state_message(
            0, {"clock_paused": False, "clock_speedup": True}
        )))
        self.assertTrue(wait_until(
            lambda: bool(run.find("TIME_SLIP_ENDED"))
        ), run.events)
        # One line to start it, one to end it, for several drops.
        self.assertEqual(len(run.find("TIME_SLIPPED")), 1, run.events)
        ended = run.find("TIME_SLIP_ENDED")
        self.assertEqual(len(ended), 1)
        self.assertRegex(
            ended[0][3],
            rf"^{harness.dropped_ticks} ticks dropped in \d+ batches",
        )
        self.assertFalse(harness.is_slipping)
        self.assertEqual(run.find("REPLY_LATE"), [])
        # Back to real time at 10x.
        self.assertTrue(wait_until(
            lambda: (harness.actual_speed or 0) > 9
        ), harness.actual_speed)
        self.assert_every_module_stepped_every_tick()


if __name__ == "__main__":
    unittest.main()
