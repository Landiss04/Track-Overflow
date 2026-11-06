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
from track_ctrl.interface import TrackControllerInputs  # noqa: E402
from track_ctrl.plc import compile_program  # noqa: E402
from track_ctrl.state import TrackControllerState  # noqa: E402
from track_ctrl.stimulus import (  # noqa: E402
    StimulusError,
    apply_user,
    build_snapshot,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rig import CONTROLLER, Rig, loaded_state  # noqa: E402


class UserInputTests(unittest.TestCase):
    """What the programmer can do, through the UI's own slots."""

    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self) -> None:
        self.state = loaded_state()
        # The CTC and Track Model, standing in; its steps drive the UI.
        self.rig = Rig(self.state.system, stepper=self.state.step)
        self.rig.settle()

    def user(self, op: str, **fields: object) -> str:
        return apply_user(self.state, {"type": "user", "op": op, **fields})

    def ctc_maintenance(self, active: bool) -> None:
        self.rig.dispatcher_in_maintenance(active)
        self.rig.tick()

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
            self.state.system.controller(CONTROLLER).switch_commands["12"])
        self.user("release_switch", switch="12")
        self.assertFalse(
            self.state.system.controller(CONTROLLER).switch_commands["12"])

    def test_maintenance_ending_takes_the_hand_set_switch_back(self) -> None:
        self.ctc_maintenance(True)
        self.user("set_switch", switch="12", reverse=True)
        self.ctc_maintenance(False)
        self.assertEqual(
            self.state.system.controller(CONTROLLER).manual_switches, {})

    def test_the_switch_dialog_reports_the_ctc_command(self) -> None:
        self.ctc_maintenance(True)
        self.rig.world.set_switch_command(self.rig.key("12"), "reverse")
        self.rig.tick()
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

    def test_the_attached_vital_code_can_be_read_not_edited(self) -> None:
        entry = next(f for f in self.state.files["rows"]
                     if f["name"] == "vital.plc")
        self.assertTrue(entry["readonly"])
        self.user("open_file", iteration=entry["iteration"])
        self.assertTrue(self.state.bufferReadOnly)
        self.assertIn("OUT_AUTH_1", self.state.buffer)
        with self.assertRaises(StimulusError):
            self.user("append_buffer", text="x")

    def test_oversized_append_is_refused(self) -> None:
        with self.assertRaises(StimulusError):
            self.user("append_buffer", text="x" * 5000)

    def test_the_views_show_speeds_in_mph(self) -> None:
        self.rig.settle()
        rows = {row["name"]: row["value"] for row in self.state.outputs["rows"]}
        # 12 m/s is the posted limit of block 1 and 4 blocks of authority.
        self.assertEqual(rows["TC_1"], "26.8 MPH · 4 BLK")
        suggestions = {r["name"]: r["value"] for r in self.state.suggestionRows["rows"]}
        # The stand-in CTC suggests under the posted limit, as the CTC must.
        self.assertEqual(suggestions["SUG_1"], "26.8 MPH · 4 BLK")


class CommitGateTests(unittest.TestCase):
    """Any warning, not only an error, keeps a program off the track."""

    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self) -> None:
        self.state = loaded_state()

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
            "VAR_IN OCC_1..20 FAULT_13\nVAR_OUT AUTH_1..20 SW_99\n"
        )
        messages = [d.message for d in controller.check_program(foreign)]
        self.assertTrue(any("FAULT_13 is not an input" in m for m in messages))
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

    def load(self, name: str) -> str:
        return self.state.load_track_config(str(self.folder / name))

    def test_the_ui_starts_with_no_track_and_an_empty_editor(self) -> None:
        state = self.state
        self.assertFalse(state.hasTrack)
        self.assertEqual(state.buffer, "")
        self.assertFalse(state.ready)
        self.assertEqual(state.notReadyReason, "no track is loaded")
        self.assertEqual(state.controller["mode"], "No track loaded")
        self.assertEqual([f["detail"] for f in state.files["rows"]],
                         ["NO TRACK"])
        self.assertEqual(state.outputs["rows"], [])
        self.assertEqual(state.lines["rows"], [])
        state.setBuffer("VAR_OUT X\nX := 1\n")
        state.run()
        self.assertFalse(state.canCommit)
        self.assertIn("load a track first", state.terminal["rows"][-1])
        state.commit()
        self.assertEqual(state.system.controllers, {})

    def test_inspecting_a_file_reports_the_fixed_wayside_count(self) -> None:
        info = self.state.inspect_track_config(str(self.folder / "green_line.json"))
        self.assertTrue(info["ok"])
        self.assertEqual(
            (info["line"], info["blocks"], info["switches"], info["crossings"]),
            ("Green Line", 150, 6, 2),
        )
        self.assertEqual(info["controllers"], 6)
        self.assertEqual(info["replaces"], 0)
        self.assertNotIn("min", info)
        self.assertNotIn("max", info)
        red = self.state.inspect_track_config(str(self.folder / "red_line.json"))
        self.assertEqual(red["controllers"], 5)
        self.load("green_line.json")
        again = self.state.inspect_track_config(
            str(self.folder / "green_line.json"))
        self.assertEqual(again["replaces"], 6)

    def test_inspecting_changes_nothing(self) -> None:
        self.state.inspect_track_config(str(self.folder / "green_line.json"))
        self.assertEqual(self.state.system.controllers, {})

    def test_loading_uses_the_waysides_the_track_is_built_with(self) -> None:
        self.assertEqual(self.load("green_line.json"), "")
        green = self.state.system.controllers_for("Green Line")
        self.assertEqual([c.config.controller_id for c in green],
                         [f"GTC-0{n}" for n in range(1, 7)])
        self.assertEqual(sum(len(c.blocks) for c in green), 150)
        self.assertEqual(self.load("red_line.json"), "")
        self.assertEqual(
            len(self.state.system.controllers_for("Red Line")), 5)
        self.assertEqual(
            len(self.state.system.controllers_for("Green Line")), 6)

    def test_a_loaded_track_has_no_programs_and_an_empty_editor(self) -> None:
        self.load("green_line.json")
        for controller in self.state.system.controllers_for("Green Line"):
            self.assertEqual(controller.iteration, 0)
            self.assertIsNone(controller.program)
        self.assertTrue(self.state.hasTrack)
        self.assertFalse(self.state.ready)
        self.assertIn("GTC-01", self.state.notReadyReason)
        self.assertEqual(self.state.buffer, "")
        live = self.state.files["rows"][0]
        self.assertEqual(live["detail"], "NOT COMMITTED")

    def test_new_gives_an_empty_buffer(self) -> None:
        self.load("green_line.json")
        self.state.setBuffer("VAR_OUT X\n")
        self.state.newFile()
        self.assertEqual(self.state.buffer, "")

    def test_loading_a_line_makes_a_ready_module_not_ready_again(self) -> None:
        self.load("green_line.json")
        self.load("red_line.json")
        self.state.system.load_starter_programs()
        self.assertTrue(self.state.ready)
        self.load("green_line.json")
        self.assertFalse(self.state.ready)
        # The other line keeps its programs.
        self.assertEqual(
            self.state.system.controller("RTC-01").iteration, 1)

    def test_reloading_a_line_replaces_its_programs(self) -> None:
        self.load("green_line.json")
        self.state.system.load_starter_programs()
        controller = self.state.system.controller(CONTROLLER)
        self.assertEqual(controller.iteration, 1)
        self.load("green_line.json")
        self.assertEqual(
            self.state.system.controller(CONTROLLER).iteration, 0)

    def test_the_programmer_is_taken_to_what_was_loaded(self) -> None:
        self.load("red_line.json")
        self.assertEqual(self.state.selectedLine, "Red Line")
        self.assertEqual(self.state.selectedController, "RTC-01")
        self.load("green_line.json")
        self.assertEqual(self.state.selectedLine, "Green Line")
        self.assertEqual(self.state.selectedController, "GTC-01")

    def test_a_wayside_database_is_refused_with_the_reason(self) -> None:
        path = (Path(__file__).resolve().parents[2] / "TrackCtrlHw" / "data"
                / "waysides" / "green_wayside_1.json")
        if not path.exists():
            self.skipTest("the HW wayside databases are not in this checkout")
        message = self.state.load_track_config(str(path))
        self.assertIn("wayside database", message)
        self.assertFalse(self.state.hasTrack)

    def test_a_file_that_is_not_a_layout_is_refused(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "junk.json"
            path.write_text("{ nope", encoding="utf-8")
            info = self.state.inspect_track_config(str(path))
            self.assertFalse(info["ok"])
            self.assertIn("not valid JSON", info["error"])
            self.assertIn("not valid JSON",
                          self.state.load_track_config(str(path)))

    def _purple(self, folder: str) -> Path:
        layout = {"line": "Purple", "blocks": [
            {"block_number": n, "section": "A", "length_m": 50,
             "speed_limit_kmh": 36} for n in range(1, 9)]}
        path = Path(folder) / "purple.json"
        path.write_text(json.dumps(layout), encoding="utf-8")
        return path

    def test_a_new_line_is_added_not_substituted(self) -> None:
        import tempfile

        self.load("green_line.json")
        self.load("red_line.json")
        with tempfile.TemporaryDirectory() as folder:
            path = self._purple(folder)
            info = self.state.inspect_track_config(str(path))
            self.assertEqual(info["replaces"], 0)
            # A line the system has no wayside count for gets the
            # fewest D014 allows.
            self.assertEqual(info["controllers"], 2)
            self.assertEqual(self.state.load_track_config(str(path)), "")
        self.assertEqual(
            [line.name for line in self.state.system.lines],
            ["Green Line", "Red Line", "Purple Line"],
        )
        self.assertEqual(self.state.selectedLine, "Purple Line")
        self.assertEqual(self.state.selectedController, "PTC-01")

    def test_a_loaded_line_works_with_a_wayside_that_owns_no_equipment(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            self.state.load_track_config(str(self._purple(folder)))
        self.state.system.load_starter_programs()
        controller = self.state.system.controller("PTC-01")
        self.assertEqual(controller.config.switches, {})
        self.assertEqual(controller.diagnose(
            compile_program(default_program_source(controller))), ())
        self.state.step(0.1, TrackControllerInputs(time_s=1.0))

    def test_the_test_ui_sees_the_new_topology(self) -> None:
        self.load("green_line.json")
        snapshot = json.loads(json.dumps(build_snapshot(self.state)))
        ids = [c["id"] for c in snapshot["controllers"]]
        self.assertEqual(ids, [f"GTC-0{n}" for n in range(1, 7)])

    def test_the_test_ui_snapshot_works_with_no_track(self) -> None:
        snapshot = json.loads(json.dumps(build_snapshot(self.state)))
        self.assertEqual(snapshot["controllers"], [])
        self.assertFalse(snapshot["ready"])


class SnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_snapshot_is_json_and_reflects_a_stimulus(self) -> None:
        state = loaded_state()
        rig = Rig(state.system, stepper=state.step)
        rig.world.set_occupancy(rig.key("3"), True)
        # Block 8 is nowhere near the train on 3, so it is not held.
        rig.world.set_suggestion(rig.key("8"), 7, 2)
        rig.settle()

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
        self.assertFalse(snapshot["maintenance"])
        self.assertEqual(len(snapshot["controllers"]), 11)
        self.assertIn("ui", snapshot)
        self.assertNotIn("standin", snapshot)

    def test_snapshot_describes_the_track_for_the_world(self) -> None:
        state = loaded_state()
        snapshot = build_snapshot(state)
        entry = next(c for c in snapshot["controllers"]
                     if c["id"] == CONTROLLER)
        self.assertEqual(entry["line_key"], "Green")
        self.assertEqual(entry["crossings"], ["19"])
        self.assertEqual(entry["signals"], ["12"])
        self.assertEqual(entry["switches"][0]["block_id"], "12")

    def test_snapshot_carries_switch_commands_and_maintenance(self) -> None:
        state = loaded_state()
        rig = Rig(state.system, stepper=state.step)
        rig.world.set_maintenance(True)
        rig.world.set_switch_command(rig.key("12"), "reverse")
        rig.settle()
        snapshot = build_snapshot(state)
        self.assertTrue(snapshot["maintenance"])
        entry = next(c for c in snapshot["controllers"]
                     if c["id"] == CONTROLLER)
        self.assertEqual(entry["switches"][0]["ctc_command"], "reverse")


class ClockTests(unittest.TestCase):
    """The module has no clock; it shows the time it is stepped at."""

    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_before_the_first_tick_there_is_no_time(self) -> None:
        state = TrackControllerState()
        self.assertEqual(state.clock, "--:--:--")
        self.assertTrue(state.clockPaused)
        self.assertEqual(state.clockSpeed, 1)

    def test_each_step_shows_and_stamps_the_time_it_carries(self) -> None:
        state = loaded_state()
        rig = Rig(state.system, stepper=state.step)
        rig.time_s = 5 * 3600.0 + 0.5
        for _ in range(10):
            rig.tick()
        self.assertEqual(state.clock, "05:00:01")
        self.assertEqual(state.system.snapshot().ticks, 10)
        controller = state.system.controller(CONTROLLER)
        self.assertEqual(controller.now_text(), "05:00:01")

    def test_the_senders_clock_state_is_only_shown(self) -> None:
        state = TrackControllerState()
        state.set_clock_status(False, 10)
        self.assertFalse(state.clockPaused)
        self.assertEqual(state.clockSpeed, 10)


if __name__ == "__main__":
    unittest.main()
