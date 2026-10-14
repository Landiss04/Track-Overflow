"""Tests for the physical and user stimulus a test UI can apply.

Run from ``TrackCtrlSW``::

    .venv/Scripts/python -m unittest discover -s tests -v

The physical-input tests need no Qt at all. The user-input tests build
the real ``TrackControllerState``, which needs a Qt application object
but no window.

All of these use GTC-01, the first Green wayside. It owns blocks 1 to 25;
switch 12 (reverse leg to block 1), whose signal stands on block 12; and
crossing 19. Blocks 1 to 12 are posted at 12 m/s, 13 to 16 at 19 m/s.
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

from track_ctrl.controller import (  # noqa: E402
    TrackController,
    default_program_source,
)
from track_ctrl.plc import compile_program  # noqa: E402
from track_ctrl.state import TrackControllerState  # noqa: E402
from track_ctrl.stimulus import (  # noqa: E402
    StimulusError,
    apply_clock,
    apply_physical,
    apply_user,
    build_snapshot,
)
from track_ctrl.system import TrackControllerSystem  # noqa: E402
from utils.system_clock import SystemClock  # noqa: E402

CONTROLLER = "GTC-01"


def physical(op: str, **fields: object) -> dict[str, object]:
    return {"type": "physical", "op": op, "controller": CONTROLLER, **fields}


def bare_program(controller: TrackController, gate: bool = True) -> str:
    """A program that drives every output and reads no input.

    It passes every suggestion (``gate``), lights every signal GREEN and
    never throws a switch or arms a crossing, so it is a program that
    ignores the world. Only the vital layer can react to anything.
    """
    lines = []
    for name in controller.output_names():
        if name.startswith("AUTH_"):
            value = "1" if gate else "0"
        elif name.endswith("_G"):
            value = "1"
        else:
            value = "0"
        lines.append(f"VAR_OUT {name}")
        lines.append(f"{name} := {value}")
    return chr(10).join(lines) + chr(10)


class PhysicalInputTests(unittest.TestCase):
    """What the CTC and Track Model can do to a controller."""

    def setUp(self) -> None:
        self.system = TrackControllerSystem()
        self.system.external_control = True
        self.controller = self.system.controller(CONTROLLER)
        self.controller.clear_occupancy()
        self.controller.scan()

    def circuit(self, block: str) -> tuple[int, int]:
        found = self.controller.outputs.track_circuits[block]
        return found.speed_mps, found.authority_blocks

    def aspect(self) -> str:
        return self.controller.outputs.aspects["12"]

    def apply(self, op: str, **fields: object) -> str:
        return apply_physical(self.system, physical(op, **fields))

    # --- the Track Model ---

    def test_occupancy_reaches_the_input_card(self) -> None:
        self.apply("set_occupancy", block="3", value=True)
        self.assertTrue(self.controller.inputs.occupancy["3"])
        self.assertEqual(self.controller.inputs.trains["3"], "TEST")

        self.apply("set_occupancy", block="3", value=False)
        self.assertFalse(self.controller.inputs.occupancy["3"])
        self.assertNotIn("3", self.controller.inputs.trains)

    def test_occupancy_on_the_signal_block_turns_it_red(self) -> None:
        self.assertEqual(self.aspect(), "GREEN")
        self.apply("set_occupancy", block="12", value=True)
        self.assertEqual(self.aspect(), "RED")

    def test_occupancy_ahead_makes_the_program_show_yellow(self) -> None:
        self.apply("set_occupancy", block="13", value=True)
        self.assertEqual(self.aspect(), "YELLOW")

    def test_the_crossing_arms_when_a_train_is_beside_it(self) -> None:
        self.assertFalse(self.controller.outputs.crossings["19"])
        self.apply("set_occupancy", block="18", value=True)
        self.assertTrue(self.controller.outputs.crossings["19"])

    def test_a_train_holds_the_blocks_beside_it(self) -> None:
        self.assertEqual(self.circuit("5"), (12, 4))
        self.apply("set_occupancy", block="6", value=True)
        self.assertEqual(self.circuit("5"), (0, 0))
        self.assertEqual(self.circuit("7"), (0, 0))
        # Blocks 4 and 5 remain reachable; occupied block 6 is excluded.
        self.assertEqual(self.circuit("3"), (12, 2))

    def test_clear_occupancy(self) -> None:
        for block in ("3", "9", "20"):
            self.apply("set_occupancy", block=block, value=True)
        self.apply("clear_occupancy")
        self.assertFalse(any(self.controller.inputs.occupancy.values()))

    def test_a_moving_switch_stops_its_block_even_if_the_plc_forgets(self) -> None:
        self.controller.commit(bare_program(self.controller), "bare.plc")
        self.controller.scan()
        self.assertEqual(self.circuit("12"), (12, 4))
        self.apply("set_switch_moving", switch="12", value=True)
        self.assertEqual(self.circuit("12"), (0, 4))
        self.assertIn("switch_moving", [
            o.rule for o in self.controller.outputs.overrides])
        # Approaching trains must stop before entering the unusable block.
        self.assertEqual(self.circuit("11"), (0, 0))

    def test_a_faulted_switch_is_held_by_vital_without_the_plc(self) -> None:
        self.controller.commit(bare_program(self.controller), "bare.plc")
        self.apply("set_switch_fault", switch="12", value=True)
        self.assertEqual(self.circuit("12"), (0, 0))
        self.assertEqual(self.aspect(), "RED")
        rules = [o.rule for o in self.controller.outputs.overrides]
        self.assertIn("switch_fault", rules)
        self.assertIn("signal_protects_block", rules)

    def test_a_faulted_switch_is_noticed_by_the_starter_program_too(self) -> None:
        self.apply("set_switch_fault", switch="12", value=True)
        self.assertEqual(self.aspect(), "RED")
        self.assertEqual(self.circuit("12"), (0, 0))

    # --- the CTC Office ---

    def test_closing_a_block_zeroes_that_blocks_circuit_only(self) -> None:
        self.apply("set_block_closed", block="7", value=True)
        self.assertEqual(self.circuit("7"), (0, 0))
        self.assertEqual(self.circuit("9"), (12, 4))
        self.apply("set_block_closed", block="7", value=False)
        self.assertEqual(self.circuit("7"), (12, 4))

    def test_suggestions_are_per_block(self) -> None:
        self.apply("set_suggestion", block="3", speed_mps=9,
                   authority_blocks=2)
        self.assertEqual(self.circuit("3"), (9, 2))
        self.assertEqual(self.circuit("4"), (12, 4))      # untouched

    def test_one_part_of_a_suggestion_can_change_alone(self) -> None:
        self.apply("set_suggestion", block="3", speed_mps=8)
        self.assertEqual(self.circuit("3"), (8, 4))
        self.apply("set_suggestion", block="3", authority_blocks=1)
        self.assertEqual(self.circuit("3"), (8, 1))

    def test_suggestions_above_the_posted_limit_are_clamped(self) -> None:
        self.apply("set_suggestion", block="3", speed_mps=15)
        self.assertEqual(self.circuit("3"), (12, 4))      # limit is 12
        self.apply("set_suggestion", block="14", speed_mps=15)
        self.assertEqual(self.circuit("14"), (15, 4))     # limit is 19
        self.assertIn("speed_limit", [
            o.rule for o in self.controller.outputs.overrides])

    def test_a_suggestion_can_be_set_on_every_block_at_once(self) -> None:
        self.apply("set_all_suggestions", speed_mps=5, authority_blocks=3)
        self.assertEqual(
            {(s.speed_mps, s.authority_blocks)
             for s in self.controller.inputs.suggestions.values()},
            {(5, 3)},
        )
        self.assertEqual(self.circuit("3"), (5, 3))
        self.assertEqual(self.circuit("24"), (5, 1))
        self.assertEqual(self.circuit("25"), (0, 0))

    def test_a_block_with_no_suggestion_gets_no_track_circuit(self) -> None:
        self.apply("clear_suggestion", block="3")
        self.assertNotIn("3", self.controller.outputs.track_circuits)
        self.assertIn("4", self.controller.outputs.track_circuits)

    def test_zero_authority_means_zero_speed(self) -> None:
        self.apply("set_suggestion", block="3", speed_mps=9,
                   authority_blocks=0)
        self.assertEqual(self.circuit("3"), (0, 0))
        self.assertIn("no_authority", [
            o.rule for o in self.controller.outputs.overrides])

    def test_a_program_that_withholds_a_block_sends_it_nothing(self) -> None:
        self.controller.commit(bare_program(self.controller, gate=False),
                               "none.plc")
        self.controller.scan()
        self.assertEqual(self.circuit("5"), (0, 0))

    def test_speed_limit_override_replaces_the_posted_limit_and_clears(self) -> None:
        self.apply("set_speed_limit", value=5)
        self.assertEqual(self.circuit("14"), (5, 4))
        self.apply("set_speed_limit", value=None)
        self.assertIsNone(self.controller.inputs.speed_limit_override_mps)
        self.assertEqual(self.circuit("14"), (15, 4))

    def test_maintenance_mode_is_system_wide(self) -> None:
        message = {"type": "physical", "op": "set_maintenance", "value": True}
        apply_physical(self.system, message)
        self.assertTrue(self.system.maintenance)
        for controller in self.system.controllers.values():
            self.assertTrue(controller.maintenance, controller.config.controller_id)
        apply_physical(self.system, {**message, "value": False})
        self.assertFalse(any(
            c.maintenance for c in self.system.controllers.values()))

    def test_maintenance_holds_speed_and_authority(self) -> None:
        apply_physical(self.system, {"type": "physical",
                                     "op": "set_maintenance", "value": True})
        self.assertEqual(self.circuit("5"), (0, 0))
        self.assertIn("maintenance_hold", [o.rule for o in self.controller.outputs.overrides])

    def test_a_ctc_switch_command_is_obeyed_only_in_maintenance(self) -> None:
        self.apply("set_switch_command", switch="12", position="reverse")
        self.assertFalse(self.controller.outputs.switches["12"])
        apply_physical(self.system, {"type": "physical",
                                     "op": "set_maintenance", "value": True})
        self.assertTrue(self.controller.outputs.switches["12"])
        self.assertIn("ctc_switch_command", [
            o.rule for o in self.controller.outputs.overrides])

    def test_the_ctc_command_beats_a_hand_set_switch(self) -> None:
        apply_physical(self.system, {"type": "physical",
                                     "op": "set_maintenance", "value": True})
        self.apply("set_switch_command", switch="12", position="reverse")
        self.controller.manual_switches["12"] = False
        self.controller.scan()
        self.assertTrue(self.controller.outputs.switches["12"])

    def test_a_hand_set_switch_is_obeyed_when_the_ctc_has_not_commanded(self) -> None:
        apply_physical(self.system, {"type": "physical",
                                     "op": "set_maintenance", "value": True})
        self.controller.manual_switches["12"] = True
        self.controller.scan()
        self.assertTrue(self.controller.outputs.switches["12"])
        self.assertIn("manual_switch", [
            o.rule for o in self.controller.outputs.overrides])

    def test_ending_maintenance_releases_commands_and_hand_settings(self) -> None:
        apply_physical(self.system, {"type": "physical",
                                     "op": "set_maintenance", "value": True})
        self.apply("set_switch_command", switch="12", position="reverse")
        self.controller.manual_switches["12"] = True
        apply_physical(self.system, {"type": "physical",
                                     "op": "set_maintenance", "value": False})
        self.assertEqual(self.controller.inputs.ctc_switch_commands, {})
        self.assertEqual(self.controller.manual_switches, {})
        self.assertFalse(self.controller.outputs.switches["12"])

    def test_a_switch_under_a_train_does_not_move(self) -> None:
        self.apply("set_occupancy", block="12", value=True)
        apply_physical(self.system, {"type": "physical",
                                     "op": "set_maintenance", "value": True})
        self.apply("set_switch_command", switch="12", position="reverse")
        self.assertFalse(self.controller.outputs.switches["12"])
        self.assertIn("switch_locked_under_train", [
            o.rule for o in self.controller.outputs.overrides])

    # --- the stand-in world ---

    def test_external_control_preserves_only_explicit_occupancy(self) -> None:
        self.apply("set_occupancy", block="5", value=True)
        before = [t.block_index for t in self.system.trains]
        for _ in range(80):
            self.system.tick(0.1)
        self.assertNotEqual(before, [t.block_index for t in self.system.trains])
        self.assertTrue(self.controller.inputs.occupancy["5"])
        self.assertEqual(self.controller.inputs.trains["5"], "TEST")
        for line in self.system.lines:
            for block_id, train_id in self.system.occupancy_for(line).items():
                controller = next(c for c in self.system.controllers_for(line.name)
                                  if c.config.owns(block_id))
                self.assertTrue(controller.inputs.occupancy[block_id])
                self.assertEqual(controller.inputs.trains[block_id], train_id)

    def test_manual_clear_masks_only_its_block_until_disconnect(self) -> None:
        train = self.system.trains[0]
        line = self.system.line(train.line_name)
        block_id = line.blocks[train.block_index - 1].block_id
        controller = next(c for c in self.system.controllers_for(line.name)
                          if c.config.owns(block_id))
        apply_physical(self.system, {
            "op": "set_occupancy", "controller": controller.config.controller_id,
            "block": block_id, "value": False,
        })
        self.system.tick(0.1)
        self.assertFalse(controller.inputs.occupancy[block_id])
        self.assertNotIn(block_id, controller.inputs.trains)
        self.system.external_control = False
        self.system.tick(0.0)
        self.assertTrue(controller.inputs.occupancy[block_id])
        self.system.external_control = True
        self.system.tick(0.0)
        self.assertTrue(controller.inputs.occupancy[block_id])

    def test_ticks_preserve_test_ctc_suggestions_while_trains_move(self) -> None:
        self.apply("set_suggestion", block="5", speed_mps=3, authority_blocks=2)
        self.apply("clear_suggestion", block="6")
        self.system.tick(3.0)
        suggestion = self.controller.inputs.suggestions["5"]
        self.assertEqual((suggestion.speed_mps, suggestion.authority_blocks), (3, 2))
        self.assertNotIn("6", self.controller.inputs.suggestions)

    def test_the_stand_in_resumes_when_control_is_returned(self) -> None:
        self.apply("set_occupancy", block="5", value=True)
        self.system.external_control = False
        self.system.tick(0.1)
        self.assertNotEqual(self.controller.inputs.trains.get("5"), "TEST")

    def test_the_stand_in_suggests_for_every_block(self) -> None:
        self.system.external_control = False
        self.system.tick(0.1)
        self.assertEqual(
            len(self.controller.inputs.suggestions), len(self.controller.blocks))


class RejectionTests(unittest.TestCase):
    """Bad input is refused and changes nothing (REQ-NFR-004)."""

    def setUp(self) -> None:
        self.system = TrackControllerSystem()
        self.system.external_control = True
        self.controller = self.system.controller(CONTROLLER)

    def snapshot(self) -> object:
        inputs = self.controller.inputs
        return (
            dict(inputs.occupancy), dict(inputs.suggestions),
            inputs.speed_limit_override_mps, dict(inputs.ctc_switch_commands),
            self.system.maintenance,
        )

    def refuses(self, **message: object) -> None:
        before = self.snapshot()
        with self.assertRaises(StimulusError):
            apply_physical(self.system, physical(**message))
        self.assertEqual(before, self.snapshot())

    def test_unknown_op(self) -> None:
        self.refuses(op="melt_the_rails")

    def test_block_owned_by_another_controller(self) -> None:
        other = self.system.controller("GTC-02").blocks[0].block_id
        self.refuses(op="set_occupancy", block=other, value=True)
        self.refuses(op="set_suggestion", block=other, speed_mps=5)

    def test_unknown_block_switch_and_controller(self) -> None:
        self.refuses(op="set_occupancy", block="NOPE", value=True)
        self.refuses(op="set_switch_fault", switch="99", value=True)
        self.refuses(op="set_switch_command", switch="99", position="normal")
        with self.assertRaises(StimulusError):
            apply_physical(self.system, {
                "op": "clear_occupancy", "controller": "XTC-99"})

    def test_flags_must_be_real_booleans(self) -> None:
        self.refuses(op="set_occupancy", block="3", value="yes")
        self.refuses(op="set_occupancy", block="3", value=1)

    def test_speeds_and_authorities_are_whole_non_negative_numbers(self) -> None:
        for bad in (-1, 12.5, float("inf"), float("nan"), "fast", True):
            self.refuses(op="set_suggestion", block="3", speed_mps=bad)
        for bad in (-1, 1.5, float("nan"), True):
            self.refuses(op="set_suggestion", block="3", authority_blocks=bad)

    def test_a_suggestion_must_say_what_it_suggests(self) -> None:
        self.refuses(op="set_suggestion", block="3")
        self.refuses(op="set_all_suggestions")

    def test_a_bad_value_leaves_every_block_as_it_was(self) -> None:
        self.refuses(op="set_all_suggestions", speed_mps=5,
                     authority_blocks=-1)

    def test_the_speed_limit_cannot_be_zero(self) -> None:
        self.refuses(op="set_speed_limit", value=0)
        self.refuses(op="set_speed_limit", value=-3)

    def test_maintenance_and_switch_positions_are_validated(self) -> None:
        self.refuses(op="set_switch_command", switch="12", position="sideways")
        with self.assertRaises(StimulusError):
            apply_physical(self.system, {"type": "physical",
                                         "op": "set_maintenance",
                                         "value": "on"})
        self.assertFalse(self.system.maintenance)


class UserInputTests(unittest.TestCase):
    """What the programmer can do, through the UI's own slots."""

    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self) -> None:
        self.state = TrackControllerState()
        self.state.simulation_clock.pause()

    def user(self, op: str, **fields: object) -> str:
        return apply_user(self.state, {"type": "user", "op": op, **fields})

    def ctc_maintenance(self, active: bool) -> None:
        apply_physical(self.state.system, {
            "type": "physical", "op": "set_maintenance", "value": active})
        self.state.notify_external_change()

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

    def test_the_programmer_cannot_set_maintenance_mode(self) -> None:
        # It is the CTC Office's: there is no control for it and no user op.
        self.assertFalse(hasattr(self.state, "setMaintenance"))
        with self.assertRaises(StimulusError):
            self.user("set_maintenance", value=True)

    def test_maintenance_mode_is_shown_when_the_ctc_sets_it(self) -> None:
        self.assertFalse(self.state.maintenance)
        self.assertEqual(self.state.controller["mode"], "Automatic")
        self.ctc_maintenance(True)
        self.assertTrue(self.state.maintenance)
        self.assertEqual(self.state.controller["mode"], "Maintenance (CTC)")

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

    def test_manual_switch_needs_the_ctc_to_have_maintenance_on(self) -> None:
        with self.assertRaises(StimulusError) as refused:
            self.user("set_switch", switch="12", reverse=True)
        self.assertIn("maintenance", str(refused.exception))

        self.ctc_maintenance(True)
        self.user("set_switch", switch="12", reverse=True)
        self.assertTrue(
            self.state.system.controller(CONTROLLER).outputs.switches["12"])
        self.user("release_switch", switch="12")
        self.assertFalse(
            self.state.system.controller(CONTROLLER).outputs.switches["12"])

    def test_maintenance_ending_takes_the_hand_set_switch_back(self) -> None:
        self.ctc_maintenance(True)
        self.user("set_switch", switch="12", reverse=True)
        self.ctc_maintenance(False)
        self.assertEqual(
            self.state.system.controller(CONTROLLER).manual_switches, {})

    def test_the_switch_dialog_reports_the_ctc_command(self) -> None:
        self.ctc_maintenance(True)
        apply_physical(self.state.system, physical(
            "set_switch_command", switch="12", position="reverse"))
        row = self.state.switches["rows"][0]
        self.assertEqual(row["id"], "12")
        self.assertEqual(row["ctc_command"], "REVERSE")

    def test_history_is_read_only(self) -> None:
        self.user("append_buffer", text="\n// one\n")
        self.user("run")
        self.user("commit")
        history = [f for f in self.state.files["rows"] if f["readonly"]]
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

    def test_the_views_show_speeds_in_mph(self) -> None:
        rows = {row["name"]: row["value"] for row in self.state.outputs["rows"]}
        # 12 m/s is the posted limit of block 1 and 4 blocks of authority.
        self.assertEqual(rows["TC_1"], "26.8 MPH · 4 BLK")
        suggestions = {r["name"]: r["value"] for r in self.state.suggestionRows["rows"]}
        self.assertEqual(suggestions["SUG_1"], "33.6 MPH · 4 BLK")


class CommitGateTests(unittest.TestCase):
    """Any warning, not only an error, keeps a program off the track."""

    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self) -> None:
        self.state = TrackControllerState()
        self.state.simulation_clock.pause()

    def user(self, op: str, **fields: object) -> str:
        return apply_user(self.state, {"type": "user", "op": op, **fields})

    def test_every_starter_program_has_no_diagnostics(self) -> None:
        for controller in self.state.system.controllers.values():
            program = compile_program(default_program_source(controller))
            self.assertEqual(
                controller.diagnose(program), (),
                controller.config.controller_id,
            )

    def test_reading_an_undeclared_name_is_caught_at_compile_time(self) -> None:
        program = compile_program("VAR_OUT X\nX := GHOST\n")
        messages = [d.message for d in program.diagnostics]
        self.assertTrue(any("GHOST" in m for m in messages), messages)

    def test_a_warning_blocks_commit_like_an_error(self) -> None:
        before = self.state.controller["iteration"]
        self.user("append_buffer", text="\nSTRAY := UNDECLARED_INPUT\n")
        self.user("run")
        self.assertFalse(self.state.canCommit)
        self.assertTrue(any(
            d["severity"] == "warning" for d in self.state.diagnostics["rows"]))
        self.user("commit")
        self.assertEqual(self.state.controller["iteration"], before)
        self.assertIn("warning", self.state.terminal["rows"][-1])

    def test_an_unassigned_output_blocks_commit(self) -> None:
        self.user("append_buffer", text="\nVAR_OUT NEVER_SET\n")
        self.user("run")
        self.assertFalse(self.state.canCommit)

    def test_many_unassigned_outputs_are_one_message(self) -> None:
        program = compile_program("VAR_OUT A1..20\n")
        self.assertEqual(len(program.diagnostics), 1)
        self.assertIn("20 outputs", program.diagnostics[0].message)

    def test_fixing_the_warning_lets_it_commit(self) -> None:
        before = self.state.controller["iteration"]
        self.user("append_buffer", text="\nSTRAY := UNDECLARED_INPUT\n")
        self.user("run")
        self.assertFalse(self.state.canCommit)
        self.state.setBuffer(
            self.state.buffer.replace("STRAY := UNDECLARED_INPUT", ""))
        self.user("run")
        self.assertTrue(self.state.canCommit)
        self.user("commit")
        self.assertEqual(self.state.controller["iteration"], before + 1)

    def test_the_controller_itself_refuses_a_program_with_warnings(self) -> None:
        controller = self.state.system.controller(CONTROLLER)
        with self.assertRaises(ValueError):
            controller.commit("VAR_OUT X\nX := GHOST\n", "bad.plc")

    def test_a_program_for_another_wayside_is_flagged_against_this_one(self) -> None:
        controller = self.state.system.controller(CONTROLLER)
        foreign = compile_program(
            "VAR_IN OCC_1..20 FAIL_13\nVAR_OUT AUTH_1..20 SW_99\n"
        )
        messages = [d.message for d in controller.check_program(foreign)]
        self.assertTrue(any("FAIL_13 is not an input" in m for m in messages))
        self.assertTrue(any("SW_99 is not an output" in m for m in messages))
        # Blocks 21 to 25 were never given an AUTH.
        self.assertTrue(any("AUTH is not driven" in m for m in messages))
        self.assertTrue(any("SIG_12_R is not driven" in m for m in messages))

    def test_a_program_that_fits_another_controller_is_refused_here(self) -> None:
        other = self.state.system.controller("GTC-02")
        source = default_program_source(other)
        self.state.setBuffer(source)
        self.user("run")
        self.assertFalse(self.state.canCommit)
        self.assertGreater(self.state.diagnostics["rows"][0]["line"], 0)

    def test_the_controller_ui_cannot_close_blocks(self) -> None:
        # Closing a block is the CTC Office's permission.
        self.assertFalse(hasattr(self.state, "setBlockClosed"))
        self.assertFalse(hasattr(self.state.system, "set_block_closed"))


class TrackConfigTests(unittest.TestCase):
    """Loading a track layout divides it among waysides."""

    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self) -> None:
        from track_ctrl.layout import default_layout_dir

        self.folder = default_layout_dir()
        self.state = TrackControllerState()
        self.state.simulation_clock.pause()

    def test_inspecting_a_file_reports_what_loading_would_do(self) -> None:
        info = self.state.inspect_track_config(str(self.folder / "green_line.json"))
        self.assertTrue(info["ok"])
        self.assertEqual(
            (info["line"], info["blocks"], info["switches"], info["crossings"]),
            ("Green Line", 150, 6, 2),
        )
        self.assertEqual((info["min"], info["max"]), (2, 150))
        self.assertEqual(info["replaces"], 6)
        self.assertEqual(info["default"], 6)

    def test_inspecting_changes_nothing(self) -> None:
        before = list(self.state.system.controllers)
        self.state.inspect_track_config(str(self.folder / "green_line.json"))
        self.assertEqual(list(self.state.system.controllers), before)

    def test_loading_replaces_the_line_with_the_chosen_number_of_waysides(self) -> None:
        error = self.state.load_track_config(
            str(self.folder / "green_line.json"), 3)
        self.assertEqual(error, "")
        green = [c for c in self.state.system.controllers_for("Green Line")]
        self.assertEqual([c.config.controller_id for c in green],
                         ["GTC-01", "GTC-02", "GTC-03"])
        self.assertEqual([len(c.blocks) for c in green], [50, 50, 50])
        # Red is untouched.
        self.assertEqual(
            len(self.state.system.controllers_for("Red Line")), 5)
        self.assertEqual(len(self.state.system.controllers), 8)

    def test_the_new_waysides_start_with_working_programs(self) -> None:
        self.state.load_track_config(str(self.folder / "green_line.json"), 2)
        for controller in self.state.system.controllers_for("Green Line"):
            self.assertEqual(controller.iteration, 1)
            self.assertIsNotNone(controller.program)
            self.assertIn(
                "AUTH_" + controller.blocks[0].block_id,
                controller.program.source)               # type: ignore[union-attr]
            self.assertEqual(len(controller.outputs.track_circuits),
                             len(controller.blocks) if controller.inputs.suggestions
                             else 0)

    def test_loading_replaces_programs_the_old_waysides_held(self) -> None:
        controller = self.state.system.controller(CONTROLLER)
        self.state.user_edit = None                      # no-op marker
        controller.commit(
            default_program_source(controller) + "// edited\n", "mine.plc")
        self.assertEqual(controller.iteration, 2)
        self.state.load_track_config(str(self.folder / "green_line.json"), 6)
        self.assertEqual(
            self.state.system.controller(CONTROLLER).iteration, 1)

    def test_the_programmer_is_taken_to_what_was_loaded(self) -> None:
        self.state.selectLine("Red Line")
        self.state.selectController("RTC-03")
        self.state.load_track_config(str(self.folder / "green_line.json"), 4)
        self.assertEqual(self.state.selectedLine, "Green Line")
        self.assertEqual(self.state.selectedController, "GTC-01")
        self.assertIn("blocks 1..", self.state.buffer)

    def test_a_count_outside_the_range_is_refused_and_changes_nothing(self) -> None:
        before = [(c.config.controller_id, c.iteration)
                  for c in self.state.system.controllers.values()]
        for bad in (1, 0, 151):
            message = self.state.load_track_config(
                str(self.folder / "green_line.json"), bad)
            self.assertIn("controllers", message)
        after = [(c.config.controller_id, c.iteration)
                 for c in self.state.system.controllers.values()]
        self.assertEqual(before, after)

    def test_a_wayside_database_is_refused_with_the_reason(self) -> None:
        path = (Path(__file__).resolve().parents[2] / "TrackCtrlHw" / "data"
                / "waysides" / "green_wayside_1.json")
        if not path.exists():
            self.skipTest("the HW wayside databases are not in this checkout")
        message = self.state.load_track_config(str(path), 2)
        self.assertIn("wayside database", message)

    def test_a_file_that_is_not_a_layout_is_refused(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "junk.json"
            path.write_text("{ nope", encoding="utf-8")
            info = self.state.inspect_track_config(str(path))
            self.assertFalse(info["ok"])
            self.assertIn("not valid JSON", info["error"])
            self.assertIn("not valid JSON",
                          self.state.load_track_config(str(path), 2))

    def test_a_new_line_is_added_not_substituted(self) -> None:
        import tempfile

        layout = {"line": "Purple", "blocks": [
            {"block_number": n, "section": "A", "length_m": 50,
             "speed_limit_kmh": 36} for n in range(1, 9)]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "purple.json"
            path.write_text(json.dumps(layout), encoding="utf-8")
            info = self.state.inspect_track_config(str(path))
            self.assertEqual(info["replaces"], 0)
            self.assertEqual(self.state.load_track_config(str(path), 2), "")
        self.assertEqual(
            [line.name for line in self.state.system.lines],
            ["Green Line", "Red Line", "Purple Line"],
        )
        self.assertEqual(self.state.selectedLine, "Purple Line")
        self.assertEqual(self.state.selectedController, "PTC-01")

    def test_a_loaded_line_works_with_a_wayside_that_owns_no_equipment(self) -> None:
        import tempfile

        layout = {"line": "Purple", "blocks": [
            {"block_number": n, "section": "A", "length_m": 50,
             "speed_limit_kmh": 36} for n in range(1, 9)]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "purple.json"
            path.write_text(json.dumps(layout), encoding="utf-8")
            self.state.load_track_config(str(path), 2)
        controller = self.state.system.controller("PTC-01")
        self.assertEqual(controller.config.switches, ())
        self.assertEqual(controller.diagnose(
            compile_program(default_program_source(controller))), ())
        self.state.system.tick(0.1)           # scans without error

    def test_the_test_ui_sees_the_new_topology(self) -> None:
        self.state.load_track_config(str(self.folder / "green_line.json"), 3)
        snapshot = json.loads(json.dumps(build_snapshot(self.state)))
        ids = [c["id"] for c in snapshot["controllers"]]
        self.assertEqual(ids[:3], ["GTC-01", "GTC-02", "GTC-03"])
        self.assertEqual(len(ids), 8)


class SnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_snapshot_is_json_and_reflects_a_stimulus(self) -> None:
        state = TrackControllerState()
        state.simulation_clock.pause()
        state.system.external_control = True
        apply_physical(state.system, physical(
            "set_occupancy", block="3", value=True))
        # Block 8 is nowhere near the train on 3, so it is not held.
        apply_physical(state.system, physical(
            "set_suggestion", block="8", speed_mps=7, authority_blocks=2))

        snapshot = json.loads(json.dumps(build_snapshot(state)))
        entry = next(c for c in snapshot["controllers"]
                     if c["id"] == CONTROLLER)
        tile = next(b for b in entry["blocks"] if b["id"] == "3")
        self.assertTrue(tile["occupied"])
        eight = next(b for b in entry["blocks"] if b["id"] == "8")
        self.assertEqual(
            (eight["suggested_speed"], eight["suggested_authority"],
             eight["commanded_speed"], eight["commanded_authority"]),
            (7, 2, 7, 2),
        )
        self.assertTrue(snapshot["standin"])
        self.assertFalse(snapshot["maintenance"])
        self.assertEqual(len(snapshot["controllers"]), 11)
        self.assertIn("ui", snapshot)

    def test_snapshot_carries_switch_commands_and_maintenance(self) -> None:
        state = TrackControllerState()
        state.simulation_clock.pause()
        apply_physical(state.system, {"op": "set_maintenance", "value": True})
        apply_physical(state.system, physical(
            "set_switch_command", switch="12", position="reverse"))
        snapshot = build_snapshot(state)
        self.assertTrue(snapshot["maintenance"])
        entry = next(c for c in snapshot["controllers"]
                     if c["id"] == CONTROLLER)
        self.assertEqual(entry["switches"][0]["ctc_command"], "reverse")


class ClockTests(unittest.TestCase):
    """The module runs on the shared simulation clock (D017)."""

    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_standalone_creates_and_runs_its_own_clock(self) -> None:
        state = TrackControllerState()
        self.assertFalse(state.clockPaused)
        self.assertEqual(state.clock, "05:00:00")
        state.simulation_clock.pause()

    def test_an_injected_clock_is_used_and_not_driven(self) -> None:
        clock = SystemClock()
        state = TrackControllerState(clock=clock)
        self.assertIs(state.simulation_clock, clock)
        # The harness owns pause and resume; the module leaves it held.
        self.assertTrue(clock.is_paused)

    def test_each_clock_tick_scans_and_stamps_simulated_time(self) -> None:
        clock = SystemClock()
        state = TrackControllerState(clock=clock)
        before = state.system.tick_count
        for _ in range(10):
            clock.tick()
        self.assertEqual(state.system.tick_count, before + 10)
        self.assertEqual(state.clock, "05:00:01")
        controller = state.system.controller(CONTROLLER)
        self.assertEqual(controller.now_text(), "05:00:01")

    def test_stand_in_trains_move_by_simulated_time(self) -> None:
        system = TrackControllerSystem()
        train = system.trains[0]
        start = train.block_index
        system.tick(train.seconds_per_block - 0.01)
        self.assertEqual(train.block_index, start)
        system.tick(0.02)
        self.assertEqual(train.block_index, start + 1)

    def test_clock_messages_pause_resume_and_respeed(self) -> None:
        clock = SystemClock()
        apply_clock(clock, {"op": "resume"})
        self.assertFalse(clock.is_paused)
        apply_clock(clock, {"op": "set_speed", "speed": 10})
        self.assertEqual(clock.speed, 10)
        apply_clock(clock, {"op": "pause"})
        self.assertTrue(clock.is_paused)
        for bad in (3, "10", True):
            with self.assertRaises(StimulusError):
                apply_clock(clock, {"op": "set_speed", "speed": bad})
        with self.assertRaises(StimulusError):
            apply_clock(clock, {"op": "rewind"})


if __name__ == "__main__":
    unittest.main()
