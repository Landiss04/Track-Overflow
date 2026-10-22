"""Tests for a module's link to the harness in ``utils.module_link``.

The test plays the harness with a local server in this process.

Run from the repository root with ``python -m unittest discover utils``.
"""

from __future__ import annotations

import sys
import time
import unittest
import uuid
from collections.abc import Callable, Mapping
from typing import Any

from PySide6.QtCore import QCoreApplication, QEventLoop
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from utils.harness_protocol import (
    OUTPUTS,
    PROTOCOL_VERSION,
    READY,
    REJECTED,
    STATE,
    LineBuffer,
    decode,
    encode,
    quit_message,
    step_message,
    show_message,
)
from utils.module_link import ModuleLink, TickRejectedError

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])

WAIT_S = 5.0


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


class _FakeHarness:
    """A local server that records what one module sends."""

    def __init__(self) -> None:
        self.name = f"module-link-test-{uuid.uuid4().hex[:12]}"
        self.server = QLocalServer()
        self.server.listen(self.name)
        self.socket: QLocalSocket | None = None
        self.received: list[dict[str, Any]] = []
        self._buffer = LineBuffer()
        self.server.newConnection.connect(self._on_connection)

    def _on_connection(self) -> None:
        self.socket = self.server.nextPendingConnection()
        self.socket.readyRead.connect(self._on_ready_read)

    def _on_ready_read(self) -> None:
        data = bytes(self.socket.readAll().data())
        self.received.extend(decode(line) for line in self._buffer.feed(data))

    def send(self, message: Mapping[str, Any]) -> None:
        self.socket.write(encode(message))
        self.socket.flush()

    def close(self) -> None:
        if self.socket is not None:
            self.socket.abort()
        self.server.close()


class ModuleLinkTest(unittest.TestCase):
    """A module answers each STEP once, and quits only when told."""

    def setUp(self) -> None:
        self.harness = _FakeHarness()
        self.addCleanup(self.harness.close)
        self.steps: list[tuple[int, float, float, Mapping[str, Any]]] = []
        self.step_result: Callable[[], Mapping[str, Any]] = lambda: {
            "speed_mps": 12.5
        }
        self.link = ModuleLink("train-model", self.harness.name, self.step)
        self.addCleanup(self.link.close)
        self.quits: list[bool] = []
        self.losses: list[bool] = []
        self.link.quitRequested.connect(lambda: self.quits.append(True))
        self.link.harnessLost.connect(lambda: self.losses.append(True))

    def step(
        self,
        tick: int,
        dt: float,
        sim_time_s: float,
        inputs: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        self.steps.append((tick, dt, sim_time_s, inputs))
        return self.step_result()

    def connect_ready(self) -> None:
        self.link.announce_ready()
        self.link.connect_to_harness()
        self.assertTrue(wait_until(lambda: len(self.harness.received) == 1))

    def reply_to(self, message: Mapping[str, Any]) -> dict[str, Any]:
        count = len(self.harness.received)
        self.harness.send(message)
        self.assertTrue(
            wait_until(lambda: len(self.harness.received) > count)
        )
        return self.harness.received[-1]

    def test_deferred_reply_waits_and_matches_request_once(self) -> None:
        requests = []
        self.link._deferred_handler = requests.append
        self.connect_ready()
        message = step_message(42, 3, 0.1, 18000.3, {"held": [1]})
        self.harness.send(message)
        self.assertTrue(wait_until(lambda: bool(requests)))
        self.assertEqual(self.steps, [])
        self.assertEqual(len(self.harness.received), 1)
        copied = self.link.pending_request
        copied["inputs"]["held"].append(2)
        self.assertEqual(self.link.pending_request["inputs"]["held"], [1])
        self.assertFalse(self.link.reply_outputs(42, 4, {}))
        self.assertFalse(self.link.reply_outputs(41, 3, {}))
        self.assertTrue(self.link.reply_outputs(42, 3, {"done": True}))
        self.assertFalse(self.link.reply_outputs(42, 3, {}))
        self.assertTrue(wait_until(lambda: len(self.harness.received) == 2))
        self.assertEqual(self.harness.received[-1]["outputs"], {"done": True})
        self.assertIsNone(self.link.pending_request)

    def test_deferred_refusal_and_disconnect(self) -> None:
        requests = []
        self.link._deferred_handler = requests.append
        self.connect_ready()
        self.harness.send(step_message(43, 4, 0.1, 18000.4, {}))
        self.assertTrue(wait_until(lambda: bool(requests)))
        self.assertTrue(self.link.reply_rejected(43, 4, "not ready"))
        self.assertTrue(wait_until(lambda: len(self.harness.received) == 2))
        self.assertEqual(self.harness.received[-1]["reason"], "not ready")
        self.harness.send(step_message(44, 5, 0.1, 18000.5, {}))
        self.assertTrue(wait_until(lambda: len(requests) == 2))
        self.link.close()
        self.assertFalse(self.link.reply_outputs(44, 5, {}))
        self.assertIsNone(self.link.pending_request)

    def test_clock_state_is_delivered_between_steps_without_reply(self):
        states = []
        self.link.clockStateChanged.connect(states.append)
        self.connect_ready()
        for paused in (False, True):
            self.harness.send({
                "op": "CLOCK_STATE", "id": 0, "tick": 0,
                "state": {"clock_paused": paused, "clock_speedup": False},
            })
        self.assertTrue(wait_until(lambda: len(states) == 2))
        self.assertEqual([state["clock_paused"] for state in states],
                         [False, True])
        self.assertEqual(self.steps, [])
        self.assertEqual(self.link.tick, 0)
        self.assertEqual(len(self.harness.received), 1)

    def test_ready_waits_for_the_link_then_goes_once(self) -> None:
        self.link.announce_ready()
        self.link.announce_ready()
        self.link.push_state({"clock_paused": False})
        self.link.connect_to_harness()
        self.assertTrue(wait_until(lambda: len(self.harness.received) == 2))
        ready, state = self.harness.received
        self.assertEqual(ready["op"], READY)
        self.assertEqual(ready["module"], "train-model")
        self.assertEqual(ready["protocol"], PROTOCOL_VERSION)
        self.assertEqual(state["op"], STATE)
        self.assertEqual(state["state"], {"clock_paused": False})

    def test_step_is_answered_with_outputs(self) -> None:
        self.connect_ready()
        inputs = {"track-model": {"tick": 6}}
        reply = self.reply_to(step_message(41, 7, 0.1, 18000.7, inputs))
        self.assertEqual(self.steps, [(7, 0.1, 18000.7, inputs)])
        self.assertEqual(reply["op"], OUTPUTS)
        self.assertEqual((reply["id"], reply["tick"]), (41, 7))
        self.assertEqual(reply["outputs"], {"speed_mps": 12.5})
        self.assertEqual(self.link.tick, 7)
        self.assertEqual(self.link.last_reply, reply)

    def test_refused_tick_is_rejected_with_its_reason(self) -> None:
        self.connect_ready()

        def refuse() -> Mapping[str, Any]:
            raise TickRejectedError("grade out of range")

        self.step_result = refuse
        reply = self.reply_to(step_message(5, 2, 0.1, 18000.2, {}))
        self.assertEqual(reply["op"], REJECTED)
        self.assertEqual(reply["id"], 5)
        self.assertEqual(reply["reason"], "grade out of range")

    def test_failing_step_is_rejected_and_the_module_lives_on(self) -> None:
        self.connect_ready()

        def fail() -> Mapping[str, Any]:
            raise KeyError("blocks")

        self.step_result = fail
        reply = self.reply_to(step_message(5, 2, 0.1, 18000.2, {}))
        self.assertEqual(reply["op"], REJECTED)
        self.assertIn("KeyError", reply["reason"])
        self.step_result = lambda: {}
        reply = self.reply_to(step_message(6, 3, 0.1, 18000.3, {}))
        self.assertEqual(reply["op"], OUTPUTS)

    def test_outputs_that_cannot_be_sent_are_rejected(self) -> None:
        self.connect_ready()
        self.step_result = lambda: {"speed_mps": float("nan")}
        reply = self.reply_to(step_message(9, 4, 0.1, 18000.4, {}))
        self.assertEqual(reply["op"], REJECTED)

    def test_quit_is_signalled(self) -> None:
        self.connect_ready()
        self.harness.send(quit_message(3))
        self.assertTrue(wait_until(lambda: self.quits == [True]))
        self.assertEqual(self.losses, [])

    def test_show_signals_without_a_reply_or_a_step(self) -> None:
        self.connect_ready()
        shown = []
        self.link.showRequested.connect(lambda: shown.append(True))
        self.harness.send(show_message(15))
        self.assertTrue(wait_until(lambda: shown == [True]))
        self.assertEqual(self.steps, [])
        self.assertEqual(self.link.tick, 0)
        self.assertIsNone(self.link.last_reply)
        self.assertEqual(len(self.harness.received), 1)

    def test_losing_the_harness_is_signalled_once(self) -> None:
        self.connect_ready()
        self.harness.close()
        self.assertTrue(wait_until(lambda: self.losses == [True]))
        wait_until(lambda: False, timeout_s=0.1)
        self.assertEqual(self.losses, [True])

    def test_no_harness_is_signalled(self) -> None:
        link = ModuleLink("ctc-office", "no-such-harness", self.step)
        self.addCleanup(link.close)
        lost: list[bool] = []
        link.harnessLost.connect(lambda: lost.append(True))
        link.connect_to_harness()
        self.assertTrue(wait_until(lambda: lost == [True]))


if __name__ == "__main__":
    unittest.main()
