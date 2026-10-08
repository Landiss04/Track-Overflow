"""Tests for the physical and user stimulus a test UI can apply.

Run from ``TrackCtrlSW``::

    .venv/Scripts/python -m unittest discover -s tests -v

The physical-input tests need no Qt at all. The user-input tests build
the real ``TrackControllerState``, which needs a Qt application object
but no window.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from track_ctrl.qtenv import add_qt_dll_directory  # noqa: E402

add_qt_dll_directory()

from PySide6.QtCore import QCoreApplication  # noqa: E402

from track_ctrl.state import TrackControllerState  # noqa: E402
from track_ctrl.stimulus import (  # noqa: E402
    StimulusError,
    apply_physical,
    apply_user,
    build_snapshot,
)
from track_ctrl.system import TrackControllerSystem  # noqa: E402

CONTROLLER = "GTC-01"


def physical(op: str, **fields: object) -> dict[str, object]:
    return {"type": "physical", "op": op, "controller": CONTROLLER, **fields}


class PhysicalInputTests(unittest.TestCase):
    """What the CTC and Track Model can do to a controller."""

    def setUp(self) -> None:
        self.system = TrackControllerSystem()
        self.system.external_control = True
        self.controller = self.system.controller(CONTROLLER)
        self.controller.clear_occupancy()
        self.controller.scan()
        self.blocks = [b.block_id for b in self.controller.blocks]
        self.switch = self.controller.config.switches[0]
        self.signal = self.controller.config.signals[0]
        self.crossing = self.controller.config.crossings[0]

    def aspect(self) -> str:
        return self.controller.outputs.aspects[self.signal.signal_id]

    def test_occupancy_reaches_the_input_card(self) -> None:
        block = self.blocks[3]
        apply_physical(self.system, physical(
            "set_occupancy", block=block, value=True))
        self.assertTrue(self.controller.inputs.occupancy[block])
        self.assertEqual(self.controller.inputs.trains[block], "TEST")

        apply_physical(self.system, physical(
            "set_occupancy", block=block, value=False))
        self.assertFalse(self.controller.inputs.occupancy[block])
        self.assertNotIn(block, self.controller.inputs.trains)

    def test_occupancy_on_the_signal_block_turns_it_red(self) -> None:
        self.assertEqual(self.aspect(), "GREEN")
        apply_physical(self.system, physical(
            "set_occupancy", block=self.signal.block_id, value=True))
        self.assertEqual(self.aspect(), "RED")

    def test_occupancy_ahead_makes_the_program_show_orange(self) -> None:
        ordered = [b.block_id for b in self.controller.blocks]
        ahead = ordered[ordered.index(self.signal.block_id) + 1]
        apply_physical(self.system, physical(
            "set_occupancy", block=ahead, value=True))
        self.assertEqual(self.aspect(), "ORANGE")

    def test_crossing_arms_when_a_train_is_on_the_approach(self) -> None:
        crossing_id = self.crossing.crossing_id
        self.assertFalse(self.controller.outputs.crossings[crossing_id])
        apply_physical(self.system, physical(
            "set_occupancy",
            block=self.crossing.approach_block_ids[0],
            value=True))
        self.assertTrue(self.controller.outputs.crossings[crossing_id])

    def test_closing_a_block_truncates_authority(self) -> None:
        self.assertEqual(self.controller.outputs.commanded_authority_blocks, 4)
        apply_physical(self.system, physical(
            "set_block_closed", block=self.blocks[1], value=True))
        self.assertEqual(self.controller.outputs.commanded_authority_blocks, 1)
        apply_physical(self.system, physical(
            "set_block_closed", block=self.blocks[1], value=False))
        self.assertEqual(self.controller.outputs.commanded_authority_blocks, 4)

    def test_suggested_speed_and_authority_pass_through(self) -> None:
        apply_physical(self.system, physical(
            "set_suggested_speed", value=20))
        apply_physical(self.system, physical(
            "set_suggested_authority", value=2))
        self.assertEqual(self.controller.outputs.commanded_speed_mph, 20.0)
        self.assertEqual(self.controller.outputs.commanded_authority_blocks, 2)

    def test_suggestion_is_rounded_down_by_the_input_card(self) -> None:
        apply_physical(self.system, physical(
            "set_suggested_speed", value=24))
        self.assertEqual(self.controller.outputs.commanded_speed_mph, 20.0)

    def test_speed_limit_override_clamps_and_clears(self) -> None:
        apply_physical(self.system, physical(
            "set_suggested_speed", value=55))
        apply_physical(self.system, physical("set_speed_limit", value=15))
        self.assertEqual(self.controller.outputs.commanded_speed_mph, 15.0)
        self.assertIn("speed_limit", [
            o.rule for o in self.controller.outputs.overrides])
        apply_physical(self.system, physical("set_speed_limit", value=None))
        self.assertIsNone(self.controller.inputs.speed_limit_override_mph)

    def test_a_moving_switch_stops_the_train_even_if_the_plc_forgets(self) -> None:
        apply_physical(self.system, physical(
            "set_switch_moving", switch=self.switch.switch_id, value=True))
        self.assertEqual(self.controller.outputs.commanded_speed_mph, 0.0)

    def test_a_faulted_switch_drops_the_signal_to_red(self) -> None:
        apply_physical(self.system, physical(
            "set_switch_fault", switch=self.switch.switch_id, value=True))
        self.assertEqual(self.aspect(), "RED")

    def _commit_program_that_ignores_switch_state(self) -> None:
        """A program that passes the CTC through and never reads
        FAULT_* or MOVING_*, so only the vital layer can react."""
        red, orange, green, super_green = self.signal.aspect_signals
        # Light GREEN unconditionally. A program that left the signal
        # dark would be forced to RED and hide the rule under test.
        lines = ["VAR_IN  SUG_SPEED_0..3 SUG_AUTH_0..3",
                 "VAR_OUT CMD_SPEED_0..3 CMD_AUTH_0..3",
                 f"VAR_OUT {red} {orange} {green} {super_green}",
                 f"{green} := 1", f"{red} := 0", f"{orange} := 0",
                 f"{super_green} := 0"]
        for n in range(4):
            lines.append(f"CMD_SPEED_{n} := SUG_SPEED_{n}")
            lines.append(f"CMD_AUTH_{n} := SUG_AUTH_{n}")
        source = chr(10).join(lines) + chr(10)
        self.controller.commit(source, "bare.plc")
        self.controller.scan()

    def test_vital_zeroes_speed_for_a_moving_switch_unaided(self) -> None:
        self._commit_program_that_ignores_switch_state()
        self.assertGreater(self.controller.outputs.commanded_speed_mph, 0.0)
        apply_physical(self.system, physical(
            "set_switch_moving", switch=self.switch.switch_id, value=True))
        self.assertEqual(self.controller.outputs.commanded_speed_mph, 0.0)
        self.assertIn("switch_moving", [
            o.rule for o in self.controller.outputs.overrides])

    def test_vital_cuts_authority_at_a_faulted_switch_unaided(self) -> None:
        self._commit_program_that_ignores_switch_state()
        ordered = [b.block_id for b in self.controller.blocks]
        index = ordered.index(self.switch.block_id)
        apply_physical(self.system, physical(
            "set_suggested_authority", value=15))
        apply_physical(self.system, physical(
            "set_switch_fault", switch=self.switch.switch_id, value=True))
        self.assertEqual(
            self.controller.outputs.commanded_authority_blocks, index)
        self.assertIn("authority_truncated", [
            o.rule for o in self.controller.outputs.overrides])

    def test_a_faulted_switch_block_cuts_authority(self) -> None:
        ordered = [b.block_id for b in self.controller.blocks]
        index = ordered.index(self.switch.block_id)
        apply_physical(self.system, physical(
            "set_suggested_authority", value=15))
        apply_physical(self.system, physical(
            "set_switch_fault", switch=self.switch.switch_id, value=True))
        self.assertEqual(
            self.controller.outputs.commanded_authority_blocks, index)

    def test_clear_occupancy(self) -> None:
        for block in self.blocks[:3]:
            apply_physical(self.system, physical(
                "set_occupancy", block=block, value=True))
        apply_physical(self.system, physical("clear_occupancy"))
        self.assertFalse(any(self.controller.inputs.occupancy.values()))

    def test_external_control_stops_the_stand_in_world(self) -> None:
        block = self.blocks[5]
        apply_physical(self.system, physical(
            "set_occupancy", block=block, value=True))
        for _ in range(8):
            self.system.tick()
        self.assertTrue(self.controller.inputs.occupancy[block])
        self.assertEqual(self.controller.inputs.trains[block], "TEST")

    def test_standin_resumes_when_control_is_returned(self) -> None:
        block = self.blocks[5]
        apply_physical(self.system, physical(
            "set_occupancy", block=block, value=True))
        self.system.external_control = False
        self.system.tick()
        self.assertNotEqual(
            self.controller.inputs.trains.get(block), "TEST")


class RejectionTests(unittest.TestCase):
    """Bad input is refused and changes nothing (REQ-NFR-004)."""

    def setUp(self) -> None:
        self.system = TrackControllerSystem()
        self.system.external_control = True
        self.controller = self.system.controller(CONTROLLER)

    def refuses(self, **message: object) -> None:
        before = (
            dict(self.controller.inputs.occupancy),
            self.controller.inputs.suggested_speed_mph,
            self.controller.inputs.suggested_authority_blocks,
            self.controller.inputs.speed_limit_override_mph,
        )
        with self.assertRaises(StimulusError):
            apply_physical(self.system, physical(**message))
        after = (
            dict(self.controller.inputs.occupancy),
            self.controller.inputs.suggested_speed_mph,
            self.controller.inputs.suggested_authority_blocks,
            self.controller.inputs.speed_limit_override_mph,
        )
        self.assertEqual(before, after)

    def test_unknown_op(self) -> None:
        self.refuses(op="melt_the_rails")

    def test_block_owned_by_another_controller(self) -> None:
        other = self.system.controller("GTC-02").blocks[0].block_id
        self.refuses(op="set_occupancy", block=other, value=True)

    def test_unknown_block_and_switch(self) -> None:
        self.refuses(op="set_occupancy", block="NOPE", value=True)
        self.refuses(op="set_switch_fault", switch="NOPE", value=True)

    def test_value_must_be_a_real_flag(self) -> None:
        self.refuses(op="set_occupancy", block="G001", value="yes")
        self.refuses(op="set_occupancy", block="G001", value=1)

    def test_numbers_must_be_finite_and_non_negative(self) -> None:
        self.refuses(op="set_suggested_speed", value=-5)
        self.refuses(op="set_suggested_speed", value=float("inf"))
        self.refuses(op="set_suggested_authority", value=float("nan"))
        self.refuses(op="set_suggested_speed", value="fast")
        self.refuses(op="set_suggested_speed", value=True)
        self.refuses(op="set_speed_limit", value=0)

    def test_unknown_controller(self) -> None:
        with self.assertRaises(StimulusError):
            apply_physical(self.system, {
                "op": "clear_occupancy", "controller": "XTC-99"})


class UserInputTests(unittest.TestCase):
    """What the programmer can do, through the UI's own slots."""

    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self) -> None:
        self.state = TrackControllerState()
        self.state._timer.stop()

    def user(self, op: str, **fields: object) -> str:
        return apply_user(self.state, {"type": "user", "op": op, **fields})

    def test_selection_and_tabs(self) -> None:
        self.user("select_line", name="Red Line")
        self.assertEqual(self.state.selectedLine, "Red Line")
        self.user("select_controller", name="RTC-03")
        self.assertEqual(self.state.selectedController, "RTC-03")
        self.user("set_tab", index=1)
        self.assertEqual(self.state.activeTab, 1)

    def test_bad_selection_is_refused(self) -> None:
        with self.assertRaises(StimulusError):
            self.user("select_controller", name="XTC-99")
        with self.assertRaises(StimulusError):
            self.user("set_tab", index=7)

    def test_commit_is_gated_on_a_run_exactly_as_in_the_ui(self) -> None:
        before = self.state.controller["iteration"]
        self.user("commit")
        self.assertEqual(self.state.controller["iteration"], before)

        self.user("append_buffer", text="\n// edit\n")
        self.assertFalse(self.state.canCommit)
        self.user("run")
        self.assertTrue(self.state.canCommit)
        self.user("commit")
        self.assertEqual(self.state.controller["iteration"], before + 1)

    def test_manual_switch_needs_maintenance_mode(self) -> None:
        switch = self.state.switches[0]["id"]
        with self.assertRaises(StimulusError):
            self.user("set_switch", switch=switch, reverse=True)
        self.user("set_maintenance", value=True)
        self.user("set_switch", switch=switch, reverse=True)
        self.assertEqual(self.state.controller["commanded_authority"], 0)
        self.user("release_switch", switch=switch)
        self.user("set_maintenance", value=False)

    def test_history_is_read_only(self) -> None:
        self.user("append_buffer", text="\n// one\n")
        self.user("run")
        self.user("commit")
        history = [f for f in self.state.files if f["readonly"]]
        self.user("open_file", iteration=history[0]["iteration"])
        with self.assertRaises(StimulusError):
            self.user("append_buffer", text="x")

    def test_load_program_from_a_path(self) -> None:
        path = Path(__file__).with_name("_loaded.plc")
        path.write_text("VAR_OUT X\nX := 1\n", encoding="utf-8")
        try:
            self.user("load_program", path=str(path))
            self.assertEqual(self.state.bufferFile, "_loaded.plc")
        finally:
            path.unlink()

    def test_oversized_append_is_refused(self) -> None:
        with self.assertRaises(StimulusError):
            self.user("append_buffer", text="x" * 5000)


class SnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_snapshot_is_json_and_reflects_a_stimulus(self) -> None:
        state = TrackControllerState()
        state._timer.stop()
        state.system.external_control = True

        block = state.system.controller(CONTROLLER).blocks[2].block_id
        apply_physical(state.system, physical(
            "set_occupancy", block=block, value=True))

        snapshot = json.loads(json.dumps(build_snapshot(state)))
        entry = next(c for c in snapshot["controllers"]
                     if c["id"] == CONTROLLER)
        tile = next(b for b in entry["blocks"] if b["id"] == block)
        self.assertTrue(tile["occupied"])
        self.assertFalse(snapshot["standin"])
        self.assertEqual(len(snapshot["controllers"]), 11)
        self.assertIn("ui", snapshot)


if __name__ == "__main__":
    unittest.main()
