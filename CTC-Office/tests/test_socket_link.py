"""Tests for the CTC socket link: JSON round trip and two processes.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtNetwork import QLocalSocket  # noqa: E402

from ctc.interface import (  # noqa: E402
    BlockOccupancy,
    CrossingReport,
    CtcInputs,
    CtcSnapshot,
    SwitchReport,
    TrackControllerInputs,
    TrackFailureReport,
    TicketSales,
    TrackModelInputs,
    TrainReport,
)
from ctc.model import StubCtcOffice  # noqa: E402
from ctc.model import StubCtcOffice as _Module  # noqa: E402
from ctc.socket_link import (  # noqa: E402
    CtcLinkServer,
    LinkError,
    RemoteCtcError,
    SocketLink,
)
from ctc.wire import inputs_from_wire, snapshot_from_wire, to_wire  # noqa
from ctc_ui.test_harness import CtcTestHarness  # noqa: E402

HOST = Path(__file__).with_name("link_host.py")


def _green(tickets: int) -> TrackModelInputs:
    """Track Model inputs with Green line ticket sales."""
    return TrackModelInputs((TicketSales("Green", tickets),))


def _sold(snap: CtcSnapshot, line: str = "Green") -> int:
    """Tickets sold so far on one line."""
    return {t.line: t.tickets for t in snap.tickets_sold}[line]


class WireTest(unittest.TestCase):

    def test_inputs_round_trip(self) -> None:
        inputs = CtcInputs(
            track_controller=TrackControllerInputs(
                occupancy=(BlockOccupancy("Green", "1", True),),
                trains=(TrainReport("T1", "Green", "1", 12.5, 8.0),),
                switches=(SwitchReport("Green", "12", "reverse"),),
                crossings=(CrossingReport("Green", "19", "active"),),
                failures=(TrackFailureReport("Red", "5", "power"),),
            ),
            track_model=_green(3),
        )
        self.assertEqual(inputs_from_wire(to_wire(inputs)), inputs)

    def test_snapshot_round_trip(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "65", 30600.0)
        ctc.set_maintenance_mode(True)
        ctc.set_block_closed("Red", "2", True)
        ctc.set_switch("Green", "12", "reverse")
        ctc.set_clock_speedup(True)
        ctc.step(0.1, CtcInputs(track_model=_green(4)))
        snap = ctc.snapshot()
        self.assertEqual(snapshot_from_wire(to_wire(snap)), snap)


class SocketLinkTest(unittest.TestCase):
    """A real server in another process, as in the two windows."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self) -> None:
        self.name = f"trains-ctc-test-{os.getpid()}-{time.monotonic_ns()}"
        self.host = subprocess.Popen(
            [sys.executable, str(HOST), self.name, "1500"],
            stdout=subprocess.PIPE, text=True)
        self.assertEqual(self.host.stdout.readline().strip(), "ready")
        self.link = SocketLink(self.name)
        self._wait(lambda: self.link.connected)

    def tearDown(self) -> None:
        self.host.kill()
        self.host.wait()
        self.host.stdout.close()

    def _wait(self, condition, timeout_s: float = 5.0) -> None:
        deadline = time.monotonic() + timeout_s
        while not condition():
            self.assertLess(time.monotonic(), deadline, "timed out")
            self.app.processEvents()
            time.sleep(0.01)

    def test_requests_reach_the_remote_module(self) -> None:
        self.link.dispatch("T1", "Green", "65", 30600.0)
        self.link.set_maintenance_mode(True)
        self.link.set_block_closed("Red", "2", True)
        out = self.link.step(0.1, CtcInputs(track_model=_green(5)))
        (suggestion,) = out.track_controller.suggestions
        self.assertEqual(suggestion.authority_block_id, "65")
        # Still an int after the JSON round trip.
        self.assertIs(type(suggestion.suggested_speed_mps), int)
        snap = self.link.snapshot()
        self.assertEqual(_sold(snap), 5)
        self.assertEqual(snap.orders[0].arrival_s, 30600.0)
        self.assertEqual(
            snap.outputs.track_controller.closed_blocks[0].line, "Red")

    def test_set_inputs_without_a_clock_steps_once(self) -> None:
        # The headless host has no clock, so new inputs take one tick.
        self.link.set_inputs(CtcInputs(track_model=_green(3)))
        snap = self.link.snapshot()
        self.assertEqual(_sold(snap), 3)
        self.assertAlmostEqual(snap.elapsed_s, 0.1)

    def test_switch_commands_cross_the_link(self) -> None:
        with self.assertRaises(RemoteCtcError):
            self.link.set_switch("Green", "12", "reverse")
        self._wait(lambda: self.link.snapshot().outputs.track_controller
                   .maintenance_mode)
        self.link.set_switch("Green", "12", "reverse")
        (command,) = (self.link.snapshot().outputs.track_controller
                      .switch_commands)
        self.assertEqual((command.switch_id, command.position),
                         ("12", "reverse"))
        self.link.release_switch("Green", "12")
        self.assertEqual(self.link.snapshot().outputs.track_controller
                         .switch_commands, ())

    def test_clock_speedup_reaches_the_remote_module(self) -> None:
        self.link.set_clock_speedup(True)
        self.assertTrue(self.link.snapshot().outputs.clock_speedup)

    def test_attached_ui_owns_its_controls(self) -> None:
        harness = CtcTestHarness(self.link)
        names = {row["name"] for row in harness.dispatcherInputs}
        self.assertNotIn("maintenance_mode", names)
        self.assertNotIn("clock_speedup", names)

    def test_remote_rejection_is_reported(self) -> None:
        with self.assertRaises(RemoteCtcError):
            self.link.dispatch("T1", "Red", "150")

    def test_pushed_change_arrives(self) -> None:
        # The host turns maintenance mode on by itself after 1.5 s.
        self._wait(lambda: self.link.snapshot().outputs.track_controller
                   .maintenance_mode)

    def test_host_shutdown_with_client_is_silent(self) -> None:
        # Closing the CTC window with a test UI connected used to print
        # "Internal C++ object (QLocalSocket) already deleted". Errors
        # in Qt signal handlers only print, so the host must print
        # nothing.
        name = self.name + "-shutdown"
        host = subprocess.Popen(
            [sys.executable, str(HOST), name, "60000", "1500"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(host.stdout.readline().strip(), "ready")
        client = SocketLink(name)
        self._wait(lambda: client.connected)
        out, err = host.communicate(timeout=30)
        self.assertEqual(host.returncode, 0, err)
        self.assertEqual(err.strip(), "")

    def test_second_server_is_refused(self) -> None:
        # One CTC Office at a time: the name is taken.
        self.assertTrue(CtcLinkServer.is_running(self.name))
        self.assertFalse(CtcLinkServer.is_running(self.name + "-nobody"))
        self.assertFalse(CtcLinkServer(_Module(), name=self.name).listen())

    def _raw(self, payload: bytes) -> list[dict]:
        # Send raw bytes, then a snapshot request (id 99); return every
        # reply up to the snapshot's.
        sock = QLocalSocket()
        sock.connectToServer(self.name)
        self.assertTrue(sock.waitForConnected(2000))
        sock.write(payload + b'{"id": 99, "op": "snapshot"}\n')
        sock.flush()
        buffer, replies = b"", []
        deadline = time.monotonic() + 5
        while not any(r.get("id") == 99 for r in replies):
            self.assertLess(time.monotonic(), deadline, "no reply")
            if sock.waitForReadyRead(50):
                buffer += bytes(sock.readAll().data())
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                replies.append(json.loads(line))
        sock.abort()
        return [r for r in replies if r.get("op") == "error"]

    def test_malformed_requests_get_an_error_reply(self) -> None:
        for payload in (
                b"{not json\n",
                b"[1, 2]\n",
                b'{"id": 1, "op": "step", "args": {"dt": 0.1, '
                b'"inputs": []}}\n',
                b'{"id": 2, "op": "set_maintenance_mode", '
                b'"args": {"active": "false"}}\n'):
            with self.subTest(payload=payload):
                errors = self._raw(payload)
                self.assertEqual(len(errors), 1, errors)
        # "false" did not turn maintenance mode on.
        self.assertFalse(self.link._call("snapshot").outputs
                         .track_controller.maintenance_mode)

    def test_inputs_are_sent_again_after_a_restart(self) -> None:
        harness = CtcTestHarness(self.link)
        self._wait(lambda: harness.connected)
        harness.addEntry("occupied_blocks")
        harness.send()
        # The CTC Office goes away and comes back with a fresh module.
        self.host.kill()
        self.host.wait()
        self.host.stdout.close()
        self._wait(lambda: not harness.connected)
        self.host = subprocess.Popen(
            [sys.executable, str(HOST), self.name, "999999"],
            stdout=subprocess.PIPE, text=True)
        self.assertEqual(self.host.stdout.readline().strip(), "ready")
        self._wait(lambda: harness.connected)
        self.assertIn("sent again", harness.status)
        inputs = self.link._call("snapshot").inputs
        self.assertEqual(
            [(o.line, o.block_id)
             for o in inputs.track_controller.occupancy],
            [("Green", "1")])

    def test_status_says_connecting_then_not_running(self) -> None:
        harness = CtcTestHarness(SocketLink(self.name + "-nobody"))
        # Not an error while the first attempt is still being made.
        self.assertTrue(harness.status.startswith("Connecting"))
        self.assertFalse(harness.statusIsError)
        self._wait(lambda: harness.statusIsError)
        self.assertIn("not running", harness.status)

    def test_a_request_waits_for_the_connection(self) -> None:
        # Right after start the link is still connecting: a Send then
        # must not fail with "not running".
        fresh = SocketLink(self.name)
        self.assertEqual(fresh.snapshot().outputs.clock_speedup, False)

    def test_not_running_is_a_clear_error(self) -> None:
        orphan = SocketLink(self.name + "-nobody")
        self.app.processEvents()
        self.assertFalse(orphan.connected)
        with self.assertRaises(LinkError):
            orphan.snapshot()


if __name__ == "__main__":
    unittest.main()
