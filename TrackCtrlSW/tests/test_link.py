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
        self.state.simulation_clock.pause()
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

    def controller(self, controller_id: str = "GTC-01"):  # type: ignore[no-untyped-def]
        return self.state.system.controller(controller_id)

    # --- ownership ------------------------------------------------------

    def test_connected_test_ui_keeps_occupancy_moving_until_paused(self) -> None:
        client = self.connect()
        train = self.state.system.trains[0]
        line = self.state.system.line(train.line_name)
        original = line.blocks[train.block_index - 1].block_id
        controller = next(c for c in self.state.system.controllers_for(line.name)
                          if c.config.owns(original))
        client.selectTarget(controller.config.controller_id)
        self.assertTrue(client.occupied[original])
        client.setClockSpeed(10)
        client.resumeClock()
        self.assertTrue(wait_for(lambda: not self.state.clockPaused))
        self.assertTrue(wait_for(
            lambda: client.occupied.get(original) is False),
            "connecting the test UI froze simulated occupancy")
        client.pauseClock()
        self.assertTrue(wait_for(lambda: self.state.clockPaused))
        ticks = self.state.simulation_clock.tick_count
        positions = [t.block_index for t in self.state.system.trains]
        self.assertFalse(wait_for(
            lambda: self.state.simulation_clock.tick_count != ticks, 0.15))
        self.assertEqual(positions,
                         [t.block_index for t in self.state.system.trains])

    def test_connecting_hands_the_inputs_to_the_test_ui(self) -> None:
        self.assertFalse(self.state.externalControl)
        client = self.connect()
        self.assertTrue(self.state.externalControl)
        self.assertTrue(client.standin)
        self.assertEqual(len(client.controllerIds), 11)

    def test_disconnecting_returns_the_inputs_to_the_stand_in(self) -> None:
        client = self.connect()
        self.assertTrue(self.state.externalControl)
        client._retry.stop()
        client._socket.disconnectFromServer()
        self.assertTrue(wait_for(lambda: not self.state.externalControl))

    def test_the_inputs_stay_external_until_the_last_client_leaves(self) -> None:
        first, second = self.connect(), self.connect()
        first.setOccupancy("5", True)
        self.assertTrue(wait_for(lambda: self.controller().inputs.occupancy["5"]))
        first._retry.stop()
        first._socket.disconnectFromServer()
        wait_for(lambda: self.server.client_count == 1)
        self.assertTrue(self.state.externalControl)
        self.state.system.tick(0.0)
        self.assertTrue(self.controller().inputs.occupancy["5"])
        second._retry.stop()
        second._socket.disconnectFromServer()
        self.assertTrue(wait_for(lambda: not self.state.externalControl))
        self.assertFalse(self.controller().inputs.occupancy["5"])

    def test_the_ctcs_maintenance_mode_does_not_outlive_the_test_ui(self) -> None:
        client = self.connect()
        client.setMaintenance(True)
        self.assertTrue(wait_for(lambda: self.state.maintenance))
        client._retry.stop()
        client._socket.disconnectFromServer()
        self.assertTrue(wait_for(lambda: not self.state.externalControl))
        self.assertFalse(self.state.maintenance)
        self.assertFalse(self.state.system.maintenance)

    # --- physical inputs ------------------------------------------------

    def test_vital_authority_and_maintenance_overrides_reach_the_ui(self) -> None:
        client = self.connect()
        client.setBlockClosed("7", True)
        self.assertTrue(wait_for(lambda:
            self.controller().outputs.track_circuits["3"].authority_blocks == 3))
        self.assertTrue(wait_for(lambda: any(
            row["rule"] == "authority_truncated" for row in client.overrides["rows"])))
        client.setMaintenance(True)
        self.assertTrue(wait_for(lambda: all(
            c.speed_mps == c.authority_blocks == 0
            for c in self.controller().outputs.track_circuits.values())))
        self.assertTrue(wait_for(lambda: any(
            row["rule"] == "maintenance_hold" for row in client.overrides["rows"])))

    def test_yellow_and_super_green_reach_the_test_ui_and_fail_safe(self) -> None:
        client = self.connect()
        controller = self.controller()
        for suffix, aspect in (("_O", "YELLOW"), ("_SG", "SUPER GREEN")):
            with self.subTest(aspect=aspect):
                controller.set_occupancy("12", False)
                lines = []
                for name in controller.output_names():
                    value = int(name.startswith("SIG_") and name.endswith(suffix))
                    lines.extend((f"VAR_OUT {name}", f"{name} := {value}"))
                controller.commit("\n".join(lines), "aspect-check.plc")
                controller.scan()
                self.state.notify_external_change()
                def shown() -> str:
                    return next((r["value"] for r in client.outputs["rows"]
                                 if r["name"] == "SIG_12"), "")
                self.assertTrue(wait_for(lambda: shown() == aspect))
                client.setOccupancy("12", True)
                self.assertTrue(wait_for(lambda: shown() == "RED"))

    def test_a_physical_input_changes_the_controller_and_comes_back(self) -> None:
        client = self.connect()
        client.selectTarget("GTC-01")
        client.setOccupancy("12", True)          # GTC-01's signal block

        self.assertTrue(wait_for(
            lambda: self.controller().inputs.occupancy["12"]))
        self.assertTrue(wait_for(lambda: client.occupied.get("12") is True))
        self.assertTrue(wait_for(
            lambda: {r["label"]: r["value"] for r in client.outputs["rows"]}.get(
                "Signal 12") == "RED"))

    def test_a_speed_typed_in_mph_arrives_as_whole_mps(self) -> None:
        client = self.connect()
        client.selectTarget("GTC-01")
        client.setSuggestedSpeed("5", 20.0)       # 8.94 m/s, rounded down
        client.setSuggestedAuthority("5", 2)
        suggestion = lambda: self.controller().inputs.suggestions["5"]  # noqa: E731
        self.assertTrue(wait_for(lambda: suggestion().speed_mps == 8))
        self.assertTrue(wait_for(lambda: suggestion().authority_blocks == 2))
        # And the client reads it back as mph.
        self.assertTrue(wait_for(
            lambda: client.suggestedMph.get("5") == 17.9))
        self.assertEqual(client.suggestedBlocks.get("5"), 2)

    def test_a_suggestion_can_be_sent_to_every_block_or_withheld(self) -> None:
        client = self.connect()
        client.selectTarget("GTC-01")
        client.setAllSuggestions(11.2, 3)          # 5 m/s
        self.assertTrue(wait_for(lambda: all(
            s.speed_mps == 5 and s.authority_blocks == 3
            for s in self.controller().inputs.suggestions.values())))
        client.clearSuggestion("9")
        self.assertTrue(wait_for(
            lambda: "9" not in self.controller().inputs.suggestions))
        self.assertTrue(wait_for(lambda: client.suggestedMph.get("9") == -1.0))

    def test_the_ctcs_maintenance_mode_reaches_every_controller(self) -> None:
        client = self.connect()
        client.setMaintenance(True)
        self.assertTrue(wait_for(lambda: self.state.maintenance))
        self.assertTrue(all(
            c.maintenance for c in self.state.system.controllers.values()))
        self.assertTrue(wait_for(lambda: client.maintenance))
        self.assertTrue(wait_for(lambda: client.ui.get("maintenance") is True))

    def test_a_ctc_switch_command_is_obeyed_in_maintenance(self) -> None:
        client = self.connect()
        client.selectTarget("GTC-01")
        client.setMaintenance(True)
        client.setSwitchCommand("12", "reverse")
        self.assertTrue(wait_for(
            lambda: self.controller().outputs.switches["12"]))
        self.assertTrue(wait_for(
            lambda: client.ctcCommand.get("12") == "reverse"))
        client.setSwitchCommand("12", "none")
        self.assertTrue(wait_for(
            lambda: not self.controller().outputs.switches["12"]))

    def test_the_programmer_ui_is_told_about_a_physical_input(self) -> None:
        client = self.connect()
        client.selectTarget("GTC-01")
        seen: list[bool] = []
        self.state.controllerChanged.connect(lambda: seen.append(True))
        client.setSuggestedSpeed("5", 20.0)
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
        before = dict(self.controller("GTC-02").inputs.suggestions)

        client.setTab(1)
        wait_for(lambda: self.state.activeTab == 1)
        # User inputs left the physical inputs of the target alone.
        self.assertEqual(self.controller("GTC-02").inputs.suggestions, before)

        block = self.controller("GTC-02").blocks[3].block_id
        client.setSuggestedSpeed(block, 11.2)          # 5 m/s
        wait_for(lambda: self.controller("GTC-02").inputs.suggestions[
            block].speed_mps == 5)
        # And the physical input left the programmer's view alone.
        self.assertEqual(self.state.activeTab, 1)

    # --- refusals ---------------------------------------------------------

    def test_a_refused_user_input_comes_back_as_an_error(self) -> None:
        client = self.connect()
        client.setSwitchByHand("12", True)     # the CTC has not set maintenance
        self.assertTrue(wait_for(lambda: client.replyIsError))
        self.assertIn("maintenance", client.reply)

    def test_a_bad_physical_input_changes_nothing(self) -> None:
        client = self.connect()
        client.selectTarget("GTC-01")
        before = dict(self.controller().inputs.suggestions)
        client.setSuggestedSpeed("5", -40.0)
        self.assertTrue(wait_for(lambda: client.replyIsError))
        self.assertEqual(self.controller().inputs.suggestions, before)

    def test_a_block_the_target_does_not_own_is_refused(self) -> None:
        client = self.connect()
        client.selectTarget("GTC-01")
        client.setOccupancy("100", True)
        self.assertTrue(wait_for(lambda: client.replyIsError))
        self.assertIn("does not own", client.reply)

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

    # --- a new track configuration --------------------------------------------

    def test_loading_a_track_configuration_updates_a_connected_test_ui(self) -> None:
        from track_ctrl.layout import default_layout_dir

        client = self.connect()
        self.assertEqual(len(client.controllerIds), 11)
        self.state.load_track_config(
            str(default_layout_dir() / "green_line.json"), 3)
        self.assertTrue(wait_for(lambda: len(client.controllerIds) == 8))
        self.assertEqual(client.controllerIds[:3],
                         ["GTC-01", "GTC-02", "GTC-03"])
        # The target survived: GTC-01 still exists on the new layout.
        self.assertIn(client.target, client.controllerIds)
        self.assertEqual(len(client.blockIds), 50)


if __name__ == "__main__":
    unittest.main()
