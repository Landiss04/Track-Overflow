"""Tests for the stand-in world and what it does to a controller.

Run from ``TrackCtrlSW``::

    .venv/Scripts/python -m unittest discover -s tests -v

No Qt is needed. Each test drives the Qt-free module through the world,
exactly as the test UI does each tick, and reads the controller's input
card and outputs.

All of these use GTC-01, the first Green wayside. It owns blocks 1 to 25;
switch 12 (reverse leg to block 1), whose signal stands on block 12; and
crossing 19. Blocks 1 to 12 are posted at 12 m/s, 13 to 16 at 19 m/s.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rig import CONTROLLER, Rig  # noqa: E402
from track_ctrl.controller import TrackController  # noqa: E402
from track_ctrl.errors import InvalidInputError  # noqa: E402
from track_ctrl_test.world import (  # noqa: E402
    DEFAULT_SUGGESTED_AUTHORITY,
    DEFAULT_SUGGESTED_SPEED_MPS,
)


def bare_program(
    controller: TrackController,
    gate: bool = True,
    reverse_switch: bool = False,
) -> str:
    """A program that drives every output and reads no input.

    It passes every suggestion (``gate``), lights every signal GREEN and
    never arms a crossing, so it is a program that ignores the world.
    Only the vital layer can react to anything.
    """
    lines = []
    for name in controller.output_names():
        if name.startswith("AUTH_"):
            value = "1" if gate else "0"
        elif name.endswith("_G"):
            value = "1"
        elif name.startswith("SW_"):
            value = "1" if reverse_switch else "0"
        else:
            value = "0"
        lines.append(f"VAR_OUT {name}")
        lines.append(f"{name} := {value}")
    return chr(10).join(lines) + chr(10)


class WorldAndController(unittest.TestCase):
    """What the CTC and Track Model can do to a controller."""

    def setUp(self) -> None:
        self.rig = Rig()
        self.world = self.rig.world
        self.controller = self.rig.controller
        self.key = self.rig.key
        self.rig.settle()

    def circuit(self, block: str) -> tuple[int, int]:
        found = self.controller.outputs.track_circuits[block]
        return found.speed_mps, found.authority_blocks

    def aspect(self) -> str:
        return self.controller.outputs.aspects["12"]

    def rules(self) -> list[str]:
        return [item.rule for item in self.controller.outputs.overrides]

    def commit(self, source: str) -> None:
        self.controller.commit(source, "test.plc")
        self.rig.settle()

    # --- the Track Model ---

    def test_occupancy_reaches_the_input_card(self) -> None:
        self.world.set_occupancy(self.key("3"), True)
        self.rig.tick()
        self.assertTrue(self.controller.inputs.occupancy["3"])
        self.assertEqual(self.controller.inputs.trains["3"], "TEST")

        self.world.set_occupancy(self.key("3"), False)
        self.rig.tick()
        self.assertFalse(self.controller.inputs.occupancy["3"])
        self.assertNotIn("3", self.controller.inputs.trains)

    def test_occupancy_on_the_signal_block_turns_it_red(self) -> None:
        self.assertEqual(self.aspect(), "GREEN")
        self.world.set_occupancy(self.key("12"), True)
        self.rig.tick()
        self.assertEqual(self.aspect(), "RED")

    def test_occupancy_ahead_makes_the_program_show_yellow(self) -> None:
        self.world.set_occupancy(self.key("13"), True)
        self.rig.tick()
        self.assertEqual(self.aspect(), "YELLOW")

    def test_the_crossing_arms_when_a_train_is_beside_it(self) -> None:
        self.assertFalse(self.controller.outputs.crossings["19"])
        self.world.set_occupancy(self.key("18"), True)
        self.rig.tick()
        self.assertTrue(self.controller.outputs.crossings["19"])

    def test_a_train_holds_the_train_beside_it(self) -> None:
        # An empty block beside a train passes its suggestion: it is the
        # block the CTC Office preloads for the train about to enter it.
        self.world.set_occupancy(self.key("6"), True)
        self.rig.tick()
        self.assertEqual(self.circuit("5"), (12, 4))
        self.assertEqual(self.circuit("6"), (12, 4))
        self.assertEqual(self.circuit("7"), (12, 4))
        # A train in the block beside it holds both.
        self.world.set_occupancy(self.key("5"), True)
        self.rig.tick()
        self.assertEqual(self.circuit("5"), (0, 0))
        self.assertEqual(self.circuit("6"), (0, 0))
        self.assertEqual(self.circuit("7"), (12, 4))
        # The vital layer does not count blocks: a block farther away
        # keeps the authority the CTC suggested.
        self.assertEqual(self.circuit("3"), (12, 4))

    def test_clear_occupancy(self) -> None:
        keys = [self.key(each) for each in ("3", "9", "20")]
        for key in keys:
            self.world.set_occupancy(key, True)
        self.world.clear_occupancy(keys)
        self.rig.tick()
        self.assertFalse(any(self.controller.inputs.occupancy.values()))

    def test_a_failed_block_is_only_an_occupied_one(self) -> None:
        # There is no failure input: the Track Model reports a broken
        # rail as presence, and the controller reacts as to a train,
        # holding a train beside it.
        self.world.set_occupancy(self.key("6"), True)
        self.world.set_occupancy(self.key("5"), True)
        self.rig.tick()
        self.assertEqual(self.circuit("5"), (0, 0))

    def test_a_switch_that_will_not_follow_stops_its_block(self) -> None:
        # The program throws switch 12 and the machine does not follow,
        # so the controller sees it mid-throw: the block is held at
        # speed 0 whether or not the program remembers to hold it.
        self.world.set_switch_stuck(self.key("12"), True)
        self.commit(bare_program(self.controller, reverse_switch=True))
        self.assertEqual(self.circuit("12")[0], 0)
        self.assertIn("switch_moving", self.rules())

    def test_a_switch_that_follows_is_not_held(self) -> None:
        self.commit(bare_program(self.controller, reverse_switch=True))
        self.assertTrue(self.controller.outputs.switches["12"])
        self.assertEqual(self.world.switch_positions[self.key("12")], "reverse")
        self.assertNotIn("switch_moving", self.rules())

    def test_the_boundary_has_no_fault_but_vital_still_holds_one(self) -> None:
        # Nothing at the boundary can raise FAULT_; the vital rule is
        # still there for any caller that does, such as a future harness.
        self.commit(bare_program(self.controller))
        self.controller.set_switch_fault("12", True)
        self.controller.scan()
        self.assertEqual(self.circuit("12"), (0, 0))
        self.assertEqual(self.aspect(), "RED")
        self.assertIn("switch_fault", self.rules())

    def test_signals_and_crossings_come_back_as_readback(self) -> None:
        self.world.set_occupancy(self.key("18"), True)
        self.rig.settle()
        self.assertTrue(self.world.crossings_active[self.key("19")])
        self.assertEqual(self.world.signal_aspects[self.key("12")], "green")
        self.world.set_occupancy(self.key("12"), True)
        self.rig.settle()
        self.assertEqual(self.world.signal_aspects[self.key("12")], "red")

    # --- the CTC Office ---

    def test_closing_a_block_zeroes_that_blocks_circuit_only(self) -> None:
        self.world.set_closed(self.key("7"), True)
        self.rig.tick()
        self.assertEqual(self.circuit("7"), (0, 0))
        self.assertEqual(self.circuit("9"), (12, 4))
        self.world.set_closed(self.key("7"), False)
        self.rig.tick()
        self.assertEqual(self.circuit("7"), (12, 4))

    def test_suggestions_are_per_block(self) -> None:
        self.world.set_suggestion(self.key("3"), 9, 2)
        self.rig.tick()
        self.assertEqual(self.circuit("3"), (9, 2))
        self.assertEqual(self.circuit("4"), (12, 4))      # untouched

    def test_one_part_of_a_suggestion_can_change_alone(self) -> None:
        self.world.set_suggestion(self.key("3"), speed_mps=8)
        self.rig.tick()
        self.assertEqual(self.circuit("3"), (8, 4))
        self.world.set_suggestion(self.key("3"), authority_blocks=1)
        self.rig.tick()
        self.assertEqual(self.circuit("3"), (8, 1))

    def test_suggestions_above_the_posted_limit_are_clamped(self) -> None:
        self.world.set_suggestion(self.key("3"), speed_mps=15)
        self.world.set_suggestion(self.key("14"), speed_mps=15)
        self.rig.tick()
        self.assertEqual(self.circuit("3"), (12, 4))      # limit is 12
        self.assertEqual(self.circuit("14"), (15, 4))     # limit is 19
        self.assertIn("speed_limit", self.rules())

    def test_a_suggestion_can_be_set_on_every_block_at_once(self) -> None:
        keys = [self.key(block.block_id) for block in self.controller.blocks]
        self.world.set_all_suggestions(keys, 5, 3)
        self.rig.tick()
        self.assertEqual(
            {(s.speed_mps, s.authority_blocks)
             for s in self.controller.inputs.suggestions.values()},
            {(5, 3)},
        )
        self.assertEqual(self.circuit("3"), (5, 3))
        self.assertEqual(self.circuit("24"), (5, 3))

    def test_a_block_with_no_suggestion_gets_no_track_circuit(self) -> None:
        self.world.clear_suggestion(self.key("3"))
        self.rig.tick()
        self.assertNotIn("3", self.controller.outputs.track_circuits)
        self.assertIn("4", self.controller.outputs.track_circuits)

    def test_zero_authority_means_zero_speed(self) -> None:
        self.world.set_suggestion(self.key("3"), 9, 0)
        self.rig.tick()
        self.assertEqual(self.circuit("3"), (0, 0))
        self.assertIn("no_authority", self.rules())

    def test_a_program_that_withholds_a_block_sends_it_nothing(self) -> None:
        self.commit(bare_program(self.controller, gate=False))
        self.assertEqual(self.circuit("5"), (0, 0))

    def test_maintenance_mode_is_system_wide(self) -> None:
        self.rig.dispatcher_in_maintenance()
        self.rig.tick()
        self.assertTrue(self.rig.module.maintenance)
        for controller in self.rig.module.controllers.values():
            self.assertTrue(controller.maintenance)
        self.rig.dispatcher_in_maintenance(False)
        self.rig.tick()
        self.assertFalse(any(
            c.maintenance for c in self.rig.module.controllers.values()))

    def test_maintenance_does_not_hold_speed_or_authority(self) -> None:
        self.rig.dispatcher_in_maintenance()
        self.rig.tick()
        self.assertEqual(self.circuit("5"), (12, 4))
        self.assertNotIn("maintenance_hold", self.rules())

    def test_a_ctc_switch_command_is_obeyed_only_in_maintenance(self) -> None:
        self.world.set_switch_command(self.key("12"), "reverse")
        self.rig.tick()
        self.assertFalse(self.controller.outputs.switches["12"])
        self.world.set_maintenance(True)
        self.rig.tick()
        self.assertTrue(self.controller.outputs.switches["12"])
        self.assertIn("ctc_switch_command", self.rules())

    def test_the_ctc_command_beats_a_hand_set_switch(self) -> None:
        self.rig.dispatcher_in_maintenance()
        self.world.set_switch_command(self.key("12"), "reverse")
        self.controller.manual_switches["12"] = False
        self.rig.tick()
        self.assertTrue(self.controller.outputs.switches["12"])

    def test_a_hand_set_switch_is_obeyed_when_the_ctc_has_not_commanded(
        self,
    ) -> None:
        self.rig.dispatcher_in_maintenance()
        self.rig.tick()
        self.controller.manual_switches["12"] = True
        self.rig.tick()
        self.assertTrue(self.controller.outputs.switches["12"])
        self.assertIn("manual_switch", self.rules())

    def test_ending_maintenance_releases_commands_and_hand_settings(
        self,
    ) -> None:
        self.rig.dispatcher_in_maintenance()
        self.world.set_switch_command(self.key("12"), "reverse")
        self.rig.tick()
        self.controller.manual_switches["12"] = True
        self.rig.dispatcher_in_maintenance(False)
        self.rig.tick()
        self.assertEqual(self.controller.inputs.ctc_switch_commands, {})
        self.assertEqual(self.controller.manual_switches, {})
        self.assertFalse(self.controller.outputs.switches["12"])

    def test_a_switch_under_a_train_does_not_move(self) -> None:
        self.world.set_occupancy(self.key("12"), True)
        self.world.set_maintenance(True)
        self.world.set_switch_command(self.key("12"), "reverse")
        self.rig.tick()
        self.assertFalse(self.controller.outputs.switches["12"])
        self.assertIn("switch_locked_under_train", self.rules())

    def test_a_per_controller_speed_limit_override_still_works(self) -> None:
        # Not a boundary input; a configuration setting on the controller.
        self.controller.set_speed_limit_override(5)
        self.controller.scan()
        self.assertEqual(self.circuit("14"), (5, 4))
        self.controller.set_speed_limit_override(None)
        self.controller.scan()
        self.assertEqual(self.circuit("14"), (15, 4))


class TheWorldItself(unittest.TestCase):
    """The stand-in's own behaviour, apart from the controller."""

    def test_it_suggests_for_every_block_by_default(self) -> None:
        rig = Rig()
        rig.settle()
        controller = rig.controller
        self.assertEqual(
            len(controller.inputs.suggestions), len(controller.blocks))
        first = controller.inputs.suggestions["1"]
        self.assertEqual(
            (first.speed_mps, first.authority_blocks),
            (DEFAULT_SUGGESTED_SPEED_MPS, DEFAULT_SUGGESTED_AUTHORITY),
        )

    def test_trains_move_by_simulated_time(self) -> None:
        rig = Rig(trains=True)
        train = rig.world.trains[0]
        start = train.block_index
        rig.world.advance(train.seconds_per_block - 0.01)
        self.assertEqual(train.block_index, start)
        rig.world.advance(0.02)
        self.assertEqual(train.block_index, start + 1)

    def test_a_train_reaches_the_controller_as_occupancy(self) -> None:
        rig = Rig(trains=True)
        rig.tick()
        placed = rig.world.train_blocks()
        self.assertTrue(placed)
        for key in placed:
            owner = next(
                c for c in rig.module.controllers.values()
                if c.config.owns(key.block_id)
                and c.config.line_name.startswith(key.line)
            )
            # The boundary carries presence, never a train's identity.
            self.assertTrue(owner.inputs.occupancy[key.block_id])

    def test_hand_edits_survive_while_trains_move(self) -> None:
        rig = Rig(trains=True)
        rig.world.set_occupancy(rig.key("5"), True)
        rig.world.set_suggestion(rig.key("5"), 3, 2)
        rig.world.clear_suggestion(rig.key("6"))
        before = [t.block_index for t in rig.world.trains]
        for _ in range(80):
            rig.tick()
        self.assertNotEqual(before, [t.block_index for t in rig.world.trains])
        controller = rig.controller
        self.assertTrue(controller.inputs.occupancy["5"])
        suggestion = controller.inputs.suggestions["5"]
        self.assertEqual((suggestion.speed_mps, suggestion.authority_blocks),
                         (3, 2))
        self.assertNotIn("6", controller.inputs.suggestions)

    def test_a_hand_clear_masks_only_its_own_block(self) -> None:
        rig = Rig(trains=True)
        key = next(iter(rig.world.train_blocks()))
        rig.world.set_occupancy(key, False)
        self.assertNotIn(key, rig.world.occupied())
        others = set(rig.world.train_blocks()) - {key}
        self.assertTrue(others <= rig.world.occupied())

    def test_regrouping_the_waysides_keeps_the_world(self) -> None:
        from track_ctrl.layout import (
            build_line, default_layout_dir, load_layout_file,
        )
        from rig import topology

        rig = Rig(trains=True)
        trains = list(rig.world.trains)
        rig.world.set_closed(rig.key("7"), True)
        parsed = load_layout_file(default_layout_dir() / "green_line.json")
        rig.module.load_track(build_line(parsed, 3))
        # The same blocks under fewer waysides: nothing for the world to
        # relearn, so nothing moves and nothing is forgotten.
        self.assertFalse(rig.world.load_topology(topology(rig.module)))
        self.assertEqual(rig.world.trains, trains)
        self.assertIn(rig.key("7"), rig.world.closed)

    def test_a_line_that_changed_starts_again(self) -> None:
        from rig import topology

        rig = Rig(trains=True)
        red_trains = [t for t in rig.world.trains if t.line == "Red"]
        entries = [
            e for e in topology(rig.module)
            if not (e["line_key"] == "Green" and e["id"] == "GTC-06")
        ]
        rig.world.set_closed(rig.key("7"), True)
        self.assertTrue(rig.world.load_topology(entries))
        self.assertEqual(
            [t for t in rig.world.trains if t.line == "Red"], red_trains)
        green_blocks = len(rig.world.lines["Green"])
        self.assertLess(green_blocks, 150)
        self.assertIn(rig.key("7"), rig.world.closed)


class Rejection(unittest.TestCase):
    """Bad input is refused and changes nothing (REQ-NFR-004)."""

    def setUp(self) -> None:
        self.rig = Rig()
        self.world = self.rig.world
        self.key = self.rig.key

    def state(self) -> object:
        world = self.world
        return (
            dict(world.suggestions), set(world.closed),
            dict(world.occupancy_overrides), world.maintenance,
            dict(world.switch_commands), set(world.stuck_switches),
        )

    def refuses(self, action: object) -> None:
        before = self.state()
        with self.assertRaises(InvalidInputError):
            action()  # type: ignore[operator]
        self.assertEqual(before, self.state())

    def test_unknown_blocks_and_switches(self) -> None:
        stray = self.key("NOPE")
        self.refuses(lambda: self.world.set_occupancy(stray, True))
        self.refuses(lambda: self.world.set_closed(stray, True))
        self.refuses(lambda: self.world.set_suggestion(stray, 5))
        self.refuses(lambda: self.world.clear_suggestion(stray))
        self.refuses(
            lambda: self.world.set_switch_command(self.key("3"), "normal"))
        self.refuses(lambda: self.world.set_switch_stuck(self.key("3"), True))

    def test_a_block_on_no_line_is_unknown(self) -> None:
        self.refuses(
            lambda: self.world.set_occupancy(self.key("3", "Blue"), True))

    def test_speeds_and_authorities_are_whole_non_negative_numbers(
        self,
    ) -> None:
        key = self.key("3")
        for bad in (-1, 12.5, float("inf"), float("nan"), "fast", True):
            self.refuses(
                lambda: self.world.set_suggestion(key, speed_mps=bad))  # type: ignore[arg-type]
        for bad in (-1, 1.5, float("nan"), True):
            self.refuses(
                lambda: self.world.set_suggestion(key, authority_blocks=bad))

    def test_a_bad_value_leaves_every_block_as_it_was(self) -> None:
        keys = [self.key(each) for each in ("3", "4", "5")]
        self.refuses(
            lambda: self.world.set_all_suggestions(keys, 5, -1))

    def test_switch_positions_are_validated(self) -> None:
        self.refuses(
            lambda: self.world.set_switch_command(self.key("12"), "sideways"))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
