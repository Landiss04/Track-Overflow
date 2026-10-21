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
                QTimer.singleShot(delay_ms, lambda: self.send(data))

    def _plain(self, step: Mapping[str, Any]) -> bytes:
        # The CTC Office keeps the clock running.
        if self.name == CTC_OFFICE:
            return outputs_line(step, tick=step["tick"], clock_paused=False)
        return outputs_line(step, tick=step["tick"])


class _Run:
    """The harness, its fake modules and what it logged."""

    def __init__(self, edges: Any = None) -> None:
        self._folder = tempfile.TemporaryDirectory()
        self.log = EventLog(Path(self._folder.name) / "events.csv")
        self.harness = Harness(
            [ModuleSpec(name, ()) for name in NAMES],
            self.log,
            edges,
            reply_timeout_s=REPLY_TIMEOUT_S,
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

    def setUp(self) -> None:
        self.run_ = _Run(self.edges)
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


if __name__ == "__main__":
    unittest.main()
