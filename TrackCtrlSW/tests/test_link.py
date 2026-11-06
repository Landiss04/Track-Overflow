"""Loopback tests for the link between the two processes.

The real deployment is two processes. These tests run the server and the
test UI's client in one process, over a real named pipe, which exercises
exactly the same framing, ownership and refusal paths without needing a
second interpreter.

The client owns the clock and the stand-in world and steps the module
over the pipe once per tick, so most of these wait for that to happen.

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

from track_ctrl.interface import BlockKey  # noqa: E402
from track_ctrl.link import StimulusServer  # noqa: E402
from track_ctrl.state import TrackControllerState  # noqa: E402
from track_ctrl_test.client import TestClientState  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rig import loaded_state  # noqa: E402


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
        self.state = loaded_state()
        # A unique pipe name per test, so tests never see each other.
        self.name = f"track-ctrl-test-{uuid.uuid4().hex}"
        self.server = StimulusServer(self.state, self.name)
        self.assertTrue(self.server.start(), self.server.error_text())
        self.clients: list[TestClientState] = []

    def tearDown(self) -> None:
        for client in self.clients:
            client._retry.stop()
            client._clock.pause()
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
        # The stand-in CTC sends nothing until the controller is ready.
        self.assertTrue(
            wait_for(lambda: client.controllerReady and bool(
                self.controller().inputs.suggestions)),
            "the controller never became ready",
        )
        return client

    def controller(self, controller_id: str = "GTC-01"):  # type: ignore[no-untyped-def]
        return self.state.system.controller(controller_id)

    def ticks(self) -> int:
        return self.state.system.snapshot().ticks

    def leave(self, client: TestClientState) -> None:
        client._retry.stop()
        client._socket.disconnectFromServer()

    # --- the test UI is the clock and the world -----------------------

    def test_the_test_ui_ticks_the_controller_with_its_clock(self) -> None:
        self.assertEqual(self.ticks(), 0)
        self.assertEqual(self.state.clock, "--:--:--")
        self.connect()
        self.assertTrue(wait_for(lambda: self.ticks() > 5),
                        "the module was never stepped")
        self.assertNotEqual(self.state.clock, "--:--:--")
        self.assertTrue(self.state.system.snapshot().time_s)

    def test_nothing_ticks_until_a_test_ui_connects(self) -> None:
        self.assertFalse(wait_for(lambda: self.ticks() > 0, 0.3))
        self.assertFalse(self.state.externalControl)

    def test_the_clock_state_reaches_the_programmers_header(self) -> None:
        client = self.connect()
        self.assertTrue(wait_for(lambda: not self.state.clockPaused))
        client.setClockSpeed(10)
        self.assertTrue(wait_for(lambda: self.state.clockSpeed == 10))
        client.pauseClock()
        self.assertTrue(wait_for(lambda: self.state.clockPaused))

    def test_a_paused_clock_stops_the_ticks(self) -> None:
        client = self.connect()
        self.assertTrue(wait_for(lambda: self.ticks() > 3))
        client.pauseClock()
        self.assertTrue(wait_for(lambda: self.state.clockPaused))
        wait_for(lambda: False, 0.2)             # let in-flight steps land
        held = self.ticks()
        self.assertFalse(wait_for(lambda: self.ticks() != held, 0.3))
        client.resumeClock()
        self.assertTrue(wait_for(lambda: self.ticks() > held))

    def test_trains_the_world_moves_reach_the_controller(self) -> None:
        client = self.connect()
        client.setClockSpeed(10)
        train = client._world.trains[0]
        start = train.block_index
        self.assertTrue(wait_for(lambda: train.block_index != start, 5.0),
                        "the world's trains never moved")

    def test_nothing_runs_until_the_controller_is_started_up(self) -> None:
        self.state.system.reset()                 # back to no programs
        client = TestClientState(self.name)
        self.clients.append(client)
        self.assertTrue(wait_for(
            lambda: client.connected and bool(client.controllerIds)))
        self.assertTrue(wait_for(lambda: self.ticks() > 5))
        # The module is being stepped, but it is stalled and says so, and
        # the stand-in CTC sends it nothing.
        self.assertFalse(self.state.ready)
        self.assertFalse(client.controllerReady)
        self.assertEqual(self.controller().inputs.suggestions, {})
        self.assertTrue(all(
            c.speed_mps == 0
            for each in self.state.system.controllers.values()
            for c in each.outputs.track_circuits.values()))
        # Starting it up, from the programmer's side, releases the stall.
        self.state.system.load_starter_programs()
        self.assertTrue(wait_for(lambda: client.controllerReady))
        self.assertTrue(wait_for(
            lambda: bool(self.controller().inputs.suggestions)))
        self.assertTrue(self.state.ready)
        self.assertEqual(self.state.notReadyReason, "")

    def test_a_slow_controller_is_not_buried_in_steps(self) -> None:
        client = self.connect()
        client.pauseClock()
        wait_for(lambda: client._step_id is None, 1.0)
        client._owe(10_000)
        self.assertLessEqual(client._owed, 50)

    # --- ownership ------------------------------------------------------

    def test_connecting_marks_the_controller_as_driven(self) -> None:
        self.assertFalse(self.state.externalControl)
        client = self.connect()
        self.assertTrue(self.state.externalControl)
        self.assertEqual(len(client.controllerIds), 11)

    def test_disconnecting_marks_it_idle_again(self) -> None:
        client = self.connect()
        self.assertTrue(self.state.externalControl)
        self.leave(client)
        self.assertTrue(wait_for(lambda: not self.state.externalControl))

    def test_a_second_test_ui_is_refused(self) -> None:
        first = self.connect()
        second = TestClientState(self.name)
        self.clients.append(second)
        self.assertTrue(wait_for(lambda: second.replyIsError))
        self.assertIn("already driving", second.reply)
        self.assertTrue(wait_for(lambda: not second.connected))
        self.assertEqual(self.server.client_count, 1)
        self.assertTrue(first.connected)
        self.assertTrue(self.state.externalControl)

    def test_a_new_test_ui_can_connect_after_the_first_leaves(self) -> None:
        first = self.connect()
        self.leave(first)
        self.assertTrue(wait_for(lambda: self.server.client_count == 0))
        self.connect()
        self.assertEqual(self.server.client_count, 1)

    # --- physical inputs ------------------------------------------------

    def test_vital_overrides_reach_the_ui(self) -> None:
        client = self.connect()
        client.setBlockClosed("7", True)
        self.assertTrue(wait_for(lambda: (
            self.controller().outputs.track_circuits["7"].authority_blocks
            == 0)))
        self.assertTrue(wait_for(lambda: any(
            row["rule"] == "closed_block"
            for row in client.overrides["rows"])))
        # Maintenance changes who drives the switches, not the circuits.
        client.setMaintenance(True)
        client.setSwitchCommand("12", "normal")
        self.assertTrue(wait_for(lambda: self.state.maintenance))
        self.assertEqual(
            self.controller().outputs.track_circuits["3"].authority_blocks, 4)

    def test_yellow_and_super_green_reach_the_test_ui_and_fail_safe(self) -> None:
        client = self.connect()
        controller = self.controller()
        for suffix, aspect in (("_Y", "YELLOW"), ("_SG", "SUPER GREEN")):
            with self.subTest(aspect=aspect):
                client.setOccupancy("12", False)
                lines = []
                for name in controller.output_names():
                    value = int(name.startswith("SIG_") and name.endswith(suffix))
                    lines.extend((f"VAR_OUT {name}", f"{name} := {value}"))
                controller.commit("\n".join(lines), "aspect-check.plc")

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

    def test_the_track_models_readback_returns_to_the_world(self) -> None:
        client = self.connect()
        client.setMaintenance(True)
        client.setSwitchCommand("12", "reverse")
        key = BlockKey("Green", "12")
        self.assertTrue(wait_for(
            lambda: client._world.switch_positions.get(key) == "reverse"))
        client.setOccupancy("18", True)
        self.assertTrue(wait_for(lambda: client._world.crossings_active.get(
            BlockKey("Green", "19")) is True))

    def test_a_switch_the_machine_will_not_follow_is_held(self) -> None:
        client = self.connect()
        controller = self.controller()
        lines = []
        for name in controller.output_names():
            value = int(name.startswith(("AUTH_", "SW_")) or name.endswith("_G"))
            lines.extend((f"VAR_OUT {name}", f"{name} := {value}"))
        client.setSwitchMoving("12", True)
        controller.commit(chr(10).join(lines), "throw.plc")
        self.assertTrue(wait_for(lambda: any(
            row["rule"] == "switch_moving"
            for row in client.overrides["rows"])))

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
        client.setSwitchCommand("12", "normal")
        self.assertTrue(wait_for(lambda: self.state.maintenance))
        self.assertTrue(wait_for(lambda: all(
            c.maintenance for c in self.state.system.controllers.values())))
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
        before = dict(client._world.suggestions)

        client.setTab(1)
        wait_for(lambda: self.state.activeTab == 1)
        # User inputs left the physical inputs of the target alone.
        self.assertEqual(client._world.suggestions, before)

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
        before = dict(client._world.suggestions)
        client.setSuggestedSpeed("5", -40.0)
        self.assertTrue(wait_for(lambda: client.replyIsError))
        self.assertEqual(client._world.suggestions, before)

    def test_a_block_the_target_does_not_own_is_refused(self) -> None:
        client = self.connect()
        client.selectTarget("GTC-01")
        client.setOccupancy("100", True)
        self.assertTrue(wait_for(lambda: client.replyIsError))
        self.assertIn("does not own", client.reply)

    def test_a_refused_step_comes_back_as_an_error_and_is_not_applied(
        self,
    ) -> None:
        client = self.connect()
        client.pauseClock()
        wait_for(lambda: client._step_id is None, 1.0)
        before = self.ticks()
        client._send({"type": "step", "dt": -1, "inputs": {}})
        self.assertTrue(wait_for(lambda: client.replyIsError))
        client._send({"type": "step", "dt": 0.1, "inputs": {"time_s": 1}})
        self.assertTrue(wait_for(lambda: "wrong keys" in client.reply))
        self.assertEqual(self.ticks(), before)

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
        self.leave(client)
        wait_for(lambda: not client.connected)
        client.setTab(1)
        self.assertTrue(client.replyIsError)
        self.assertEqual(self.state.activeTab, 0)

    # --- a new track configuration --------------------------------------------

    def test_loading_a_track_configuration_updates_a_connected_test_ui(self) -> None:
        from track_ctrl.layout import default_layout_dir

        client = self.connect()
        self.assertEqual(len(client.controllerIds), 11)
        # Reloading Green replaces its waysides: same count, since the
        # track fixes it, but no programs until they are loaded again.
        self.state.load_track_config(
            str(default_layout_dir() / "green_line.json"))
        self.assertTrue(wait_for(lambda: not client.controllerReady))
        self.assertEqual(len(client.controllerIds), 11)
        self.assertIn(client.target, client.controllerIds)
        self.assertEqual(len(client.blockIds), 25)
        # And the controller is still being stepped.
        before = self.ticks()
        self.assertTrue(wait_for(lambda: self.ticks() > before + 3))


if __name__ == "__main__":
    unittest.main()
