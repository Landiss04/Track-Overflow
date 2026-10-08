"""Loopback tests for the stimulus link between the two processes.

The real deployment is two processes. These tests run the server and the
test UI's client in one process, over a real named pipe, which exercises
exactly the same framing, ownership and refusal paths without needing a
second interpreter.

Run from ``TrackCtrlSW``::

    .venv/Scripts/python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import time
import unittest
import uuid
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from track_ctrl.qtenv import add_qt_dll_directory  # noqa: E402

add_qt_dll_directory()

from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402

from track_ctrl.link import StimulusServer  # noqa: E402
from track_ctrl.state import TrackControllerState  # noqa: E402
from track_ctrl_test.client import TestClientState  # noqa: E402


def wait_for(condition: Callable[[], bool], seconds: float = 3.0) -> bool:
    """Pump Qt events until ``condition`` holds or time runs out."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    QCoreApplication.processEvents()
    return condition()


class LinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self) -> None:
        self.state = TrackControllerState()
        self.state._timer.stop()
        # A unique pipe name per test, so tests never see each other.
        self.name = f"track-ctrl-test-{uuid.uuid4().hex}"
        self.server = StimulusServer(self.state, self.name)
        self.assertTrue(self.server.start(), self.server.error_text())
        self.clients: list[TestClientState] = []

    def tearDown(self) -> None:
        for client in self.clients:
            client._retry.stop()
            client._socket.disconnectFromServer()
        wait_for(lambda: self.server.client_count == 0, 1.0)
        self.server.stop()
        # Delete now, not whenever Python's collector gets round to it:
        # a late Qt callback into a freed object is an access violation.
        for obj in (*self.clients, self.server, self.state):
            obj.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QCoreApplication.processEvents()

    def connect(self) -> TestClientState:
        client = TestClientState(self.name)
        self.clients.append(client)
        self.assertTrue(
            wait_for(lambda: client.connected and bool(client.controllerIds)),
            "client never received a snapshot",
        )
        return client

    # --- ownership ------------------------------------------------------

    def test_connecting_hands_the_inputs_to_the_test_ui(self) -> None:
        self.assertFalse(self.state.externalControl)
        client = self.connect()
        self.assertTrue(self.state.externalControl)
        self.assertFalse(client.standin)
        self.assertEqual(len(client.controllerIds), 11)

    def test_disconnecting_returns_the_inputs_to_the_stand_in(self) -> None:
        client = self.connect()
        self.assertTrue(self.state.externalControl)
        client._retry.stop()
        client._socket.disconnectFromServer()
        self.assertTrue(wait_for(lambda: not self.state.externalControl))

    def test_the_inputs_stay_external_until_the_last_client_leaves(self) -> None:
        first, second = self.connect(), self.connect()
        first._retry.stop()
        first._socket.disconnectFromServer()
        wait_for(lambda: self.server.client_count == 1)
        self.assertTrue(self.state.externalControl)
        second._retry.stop()
        second._socket.disconnectFromServer()
        self.assertTrue(wait_for(lambda: not self.state.externalControl))

    # --- physical inputs ------------------------------------------------

    def test_a_physical_input_changes_the_controller_and_comes_back(self) -> None:
        client = self.connect()
        client.selectTarget("GTC-01")
        block = "G013"          # GTC-01's signal block
        client.setOccupancy(block, True)

        controller = self.state.system.controller("GTC-01")
        self.assertTrue(wait_for(
            lambda: controller.inputs.occupancy[block]))
        self.assertTrue(wait_for(lambda: client.occupied.get(block) is True))
        self.assertTrue(wait_for(
            lambda: {r["label"]: r["value"] for r in client.outputs}.get(
                "Signal LT01") == "RED"))

    def test_the_programmer_ui_is_told_about_a_physical_input(self) -> None:
        client = self.connect()
        client.selectTarget("GTC-01")
        seen: list[bool] = []
        self.state.controllerChanged.connect(lambda: seen.append(True))
        client.setSuggestedSpeed(20)
        self.assertTrue(wait_for(lambda: bool(seen)))

    # --- user inputs ----------------------------------------------------

    def test_a_user_input_drives_the_programmer_ui(self) -> None:
        client = self.connect()
        client.setTab(1)
        client.selectController("GTC-03")
        self.assertTrue(wait_for(lambda: self.state.activeTab == 1))
        self.assertTrue(wait_for(
            lambda: self.state.selectedController == "GTC-03"))
        self.assertTrue(wait_for(
            lambda: client.ui.get("controller") == "GTC-03"))
        # A user input must not retarget the physical inputs.
        self.assertEqual(client.target, "GTC-01")

    def test_the_two_kinds_of_input_touch_different_things(self) -> None:
        client = self.connect()
        client.selectTarget("GTC-02")
        before = self.state.system.controller("GTC-02").inputs.suggested_speed_mph

        client.setTab(1)
        client.setMaintenance(True)
        wait_for(lambda: self.state.activeTab == 1)
        # User inputs left the physical inputs of the target alone.
        self.assertEqual(
            self.state.system.controller("GTC-02").inputs.suggested_speed_mph,
            before)

        client.setSuggestedSpeed(15)
        wait_for(lambda: self.state.system.controller(
            "GTC-02").inputs.suggested_speed_mph == 15.0)
        # And the physical input left the programmer's view alone.
        self.assertEqual(self.state.activeTab, 1)

    # --- refusals ---------------------------------------------------------

    def test_a_refused_user_input_comes_back_as_an_error(self) -> None:
        client = self.connect()
        client.setSwitchByHand("SW01", True)     # not in maintenance mode
        self.assertTrue(wait_for(lambda: client.replyIsError))
        self.assertIn("maintenance", client.reply)

    def test_a_bad_physical_input_changes_nothing(self) -> None:
        client = self.connect()
        client.selectTarget("GTC-01")
        controller = self.state.system.controller("GTC-01")
        before = controller.inputs.suggested_speed_mph
        client.setSuggestedSpeed(-40)
        self.assertTrue(wait_for(lambda: client.replyIsError))
        self.assertEqual(controller.inputs.suggested_speed_mph, before)

    def test_garbage_does_not_take_the_server_down(self) -> None:
        client = self.connect()
        client._socket.write(b"this is not json\n")
        client._socket.write(b"[1, 2, 3]\n")
        client._socket.write(b'{"type": "teleport"}\n')
        client._socket.flush()
        self.assertTrue(wait_for(lambda: client.replyIsError))

        # Still serving, and still applying valid stimuli.
        client.setTab(1)
        self.assertTrue(wait_for(lambda: self.state.activeTab == 1))

    def test_a_stimulus_with_no_client_connected_is_not_sent(self) -> None:
        client = self.connect()
        client._retry.stop()
        client._socket.disconnectFromServer()
        wait_for(lambda: not client.connected)
        client.setTab(1)
        self.assertTrue(client.replyIsError)
        self.assertEqual(self.state.activeTab, 0)


if __name__ == "__main__":
    unittest.main()
