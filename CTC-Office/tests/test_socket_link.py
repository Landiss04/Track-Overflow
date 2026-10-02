"""Tests for the CTC socket link: JSON round trip and two processes.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from ctc.interface import (  # noqa: E402
    BlockOccupancy,
    CrossingReport,
    CtcInputs,
    SwitchReport,
    TrackControllerInputs,
    TrackFailureReport,
    TrackModelInputs,
    TrainReport,
)
from ctc.model import StubCtcOffice  # noqa: E402
from ctc.socket_link import LinkError, RemoteCtcError, SocketLink  # noqa
from ctc.wire import inputs_from_wire, snapshot_from_wire, to_wire  # noqa

HOST = Path(__file__).with_name("link_host.py")


class WireTest(unittest.TestCase):

    def test_inputs_round_trip(self) -> None:
        inputs = CtcInputs(
            track_controller=TrackControllerInputs(
                occupancy=(BlockOccupancy("A1", True),),
                trains=(TrainReport("T1", "A1", 12.5, 8.0),),
                switches=(SwitchReport("SW1", "reverse"),),
                crossings=(CrossingReport("X1", "active"),),
                failures=(TrackFailureReport("A5", "power"),),
            ),
            track_model=TrackModelInputs(3),
        )
        self.assertEqual(inputs_from_wire(to_wire(inputs)), inputs)

    def test_snapshot_round_trip(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "A9")
        ctc.set_block_closed("C2", True)
        ctc.step(0.1, CtcInputs(track_model=TrackModelInputs(4)))
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
        self.link.dispatch("T1", "A9")
        out = self.link.step(0.1, CtcInputs(track_model=TrackModelInputs(5)))
        (suggestion,) = out.track_controller.suggestions
        self.assertEqual(suggestion.authority_block_id, "A9")
        self.assertEqual(self.link.snapshot().tickets_sold_total, 5)

    def test_remote_rejection_is_reported(self) -> None:
        with self.assertRaises(RemoteCtcError):
            self.link.dispatch("", "A1")

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

    def test_not_running_is_a_clear_error(self) -> None:
        orphan = SocketLink(self.name + "-nobody")
        self.app.processEvents()
        self.assertFalse(orphan.connected)
        with self.assertRaises(LinkError):
            orphan.snapshot()


if __name__ == "__main__":
    unittest.main()
