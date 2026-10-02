"""Tests for the CTC clock link between the CTC Office and its test UI.

Each test runs a server and a client in this process over a uniquely
named local socket, so it never touches a CTC Office that is running.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import sys
import time
import unittest
import uuid
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PySide6.QtCore import (  # noqa: E402
    QCoreApplication,
    QEventLoop,
    QTimer,
)
from PySide6.QtNetwork import QLocalSocket  # noqa: E402

from ctc_ui.clock_link import (  # noqa: E402
    NO_TIME_TEXT,
    ClockLinkClient,
    ClockLinkServer,
)
from ctc_ui.sim_clock import SimulationClockBridge  # noqa: E402

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])

# Longest to wait for a message to cross the socket.
WAIT_LIMIT_S = 3.0


def _spin(ms: int) -> None:
    # Run the Qt event loop for ``ms`` milliseconds.
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _wait_until(condition: Callable[[], bool]) -> bool:
    # Run the event loop until ``condition`` holds or time runs out.
    deadline = time.perf_counter() + WAIT_LIMIT_S
    while not condition():
        if time.perf_counter() > deadline:
            return False
        _spin(10)
    return True


class ClockLinkTest(unittest.TestCase):
    """The test UI and the CTC Office share one clock over the link."""

    def setUp(self) -> None:
        """Start a CTC clock, its server, and a connected client."""
        self.name = f"TrackOverflow.test.{uuid.uuid4().hex}"
        self.clock = SimulationClockBridge()
        self.server = ClockLinkServer(self.clock)
        self.assertTrue(self.server.listen(self.name))
        self.client = ClockLinkClient(self.name)
        self.assertTrue(_wait_until(lambda: self.client.connected))
        # Servers started mid-test, closed in tearDown.
        self.extra_servers: list[ClockLinkServer] = []

    def tearDown(self) -> None:
        """Close the link and let Qt finish releasing its sockets."""
        self.client.close()
        for server in [self.server, *self.extra_servers]:
            server.close()
        _spin(50)

    def test_client_receives_state_on_connect(self) -> None:
        """Show the CTC's time, pause state and speed on connecting."""
        self.assertTrue(_wait_until(
            lambda: self.client.timeText == "05:00:00"))
        self.assertTrue(self.client.paused)
        self.assertEqual(self.client.speed, 1)

    def test_client_controls_the_ctc_clock(self) -> None:
        """Run, speed up, and pause the CTC clock from the test UI."""
        self.client.resume()
        self.assertTrue(_wait_until(lambda: not self.clock.paused))
        self.client.setSpeed(10)
        self.assertTrue(_wait_until(lambda: self.clock.speed == 10))
        self.client.pause()
        self.assertTrue(_wait_until(lambda: self.clock.paused))

    def test_ctc_changes_reach_the_client(self) -> None:
        """Mirror pause, speed and time changes made in the CTC."""
        self.clock.setSpeed(10)
        self.clock.resume()
        self.assertTrue(_wait_until(
            lambda: self.client.speed == 10 and not self.client.paused))
        self.assertTrue(_wait_until(
            lambda: self.client.timeText >= "05:00:02"))
        self.clock.pause()
        self.assertTrue(_wait_until(lambda: self.client.paused))
        _spin(100)
        self.assertEqual(self.client.timeText, self.clock.timeText)

    def test_clock_keeps_running_time_while_linked(self) -> None:
        """Keep real time at 10x when the client starts the clock."""
        self.client.setSpeed(10)
        self.client.resume()
        self.assertTrue(_wait_until(lambda: not self.clock.paused))
        started_s = self.clock.clock.elapsed_s
        _spin(1000)
        self.assertAlmostEqual(
            self.clock.clock.elapsed_s - started_s, 10.0, delta=0.6
        )

    def test_unsupported_commands_are_ignored(self) -> None:
        """Ignore garbage, unknown types, and unsupported speeds."""
        raw = QLocalSocket()
        raw.connectToServer(self.name)
        self.assertTrue(raw.waitForConnected(1000))
        for line in (
            b"not json\n",
            b"[1, 2]\n",
            b'{"type": "explode"}\n',
            b'{"type": "set_speed", "speed": 5}\n',
            b'{"type": "set_speed", "speed": true}\n',
            b'{"type": "set_speed", "speed": "10"}\n',
            b'{"type": "set_speed"}\n',
        ):
            raw.write(line)
        raw.flush()
        _spin(200)
        self.assertEqual(self.clock.speed, 1)
        self.assertTrue(self.clock.paused)
        # The link still works after the garbage.
        raw.write(b'{"type": "set_speed", "speed": 10}\n')
        raw.flush()
        self.assertTrue(_wait_until(lambda: self.clock.speed == 10))
        raw.disconnectFromServer()

    def test_client_reconnects_after_ctc_restarts(self) -> None:
        """Show dashes while the CTC is gone, then reconnect."""
        self.server.close()
        self.assertTrue(_wait_until(lambda: not self.client.connected))
        self.assertEqual(self.client.timeText, NO_TIME_TEXT)
        restarted = ClockLinkServer(self.clock)
        self.extra_servers.append(restarted)
        self.assertTrue(restarted.listen(self.name))
        self.assertTrue(_wait_until(lambda: self.client.connected))
        self.assertTrue(_wait_until(
            lambda: self.client.timeText != NO_TIME_TEXT))

    def test_commands_while_disconnected_are_dropped(self) -> None:
        """Send nothing when no CTC Office is running."""
        self.server.close()
        self.assertTrue(_wait_until(lambda: not self.client.connected))
        self.client.resume()
        _spin(100)
        self.assertTrue(self.clock.paused)


if __name__ == "__main__":
    unittest.main()
