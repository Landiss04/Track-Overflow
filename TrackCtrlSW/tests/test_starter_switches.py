"""The starter program sets each Green switch for the train coming to it.

Run from ``TrackCtrlSW``::

    python -m unittest discover -s tests -v

A train runs the Green Line from the yard exit (63) all the way round to
the yard entry block (57). On the way it passes four switches that must
be set for it, and the CTC Office counts a train's authority only up to
a switch not reported set for its route
(``arbitration/authority-stops-before-obstruction``), trailing moves
included:

====== ===== ======================================= =================
switch point needs                                   seen by
====== ===== ======================================= =================
12     13    reverse for 1 -> 13; normal for 14 -> 12 GTC-01 (1..25)
28     28    reverse for 150 -> 28; normal for 27 -> 29 GTC-02 (26..50)
76     77    normal for 76 -> 78; reverse for 78 -> 101 GTC-04 (76..100)
85     85    reverse for 100 -> 84; normal for 84 -> 86 GTC-04
====== ===== ======================================= =================

A wayside sees only its own blocks: which are occupied, and which the
CTC Office sends a suggestion for. A block with a suggestion and no
train in it is the next block of the train about to enter it
(``signals/track-signal``). These tests drive the Green module at its
boundary, as the harness does, with the generated starter programs.
"""

from __future__ import annotations

import sys
import unittest
from collections.abc import Iterable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from track_ctrl.controller import default_program_source  # noqa: E402
from track_ctrl.interface import (  # noqa: E402
    BlockKey,
    CtcInputs,
    Suggestion,
    SwitchPosition,
    TrackControllerInputs,
    TrackModelInputs,
)
from track_ctrl.layout import build_default_system  # noqa: E402
from track_ctrl.module import SwTrackController  # noqa: E402
from track_ctrl.plc import compile_program  # noqa: E402

DT = 0.1


def _green() -> SwTrackController:
    module = SwTrackController()
    for line in build_default_system():
        if line.key == "Green":
            module.load_track(line)
    module.load_starter_programs()
    return module


def _key(block: str) -> BlockKey:
    return BlockKey("Green", block)


class _Line:
    """The Green module, stepped one tick at a time."""

    def __init__(self) -> None:
        self.module = _green()
        self.time_s = 0.0
        self.switches: dict[str, SwitchPosition] = {}

    def tick(
        self,
        occupied: Iterable[str] = (),
        suggested: Iterable[str] = (),
        commands: dict[str, SwitchPosition] | None = None,
    ) -> dict[str, SwitchPosition]:
        """Step once; return every switch's commanded position by ID.

        The Track Model's read-back follows the last tick's commands,
        as its switches do.
        """
        self.time_s += DT
        out = self.module.step(DT, TrackControllerInputs(
            time_s=self.time_s,
            ctc=CtcInputs(
                suggestions={
                    _key(block): Suggestion(10, 2) for block in suggested
                },
                switch_commands={
                    _key(block): position
                    for block, position in (commands or {}).items()
                },
            ),
            track_model=TrackModelInputs(
                occupied_blocks=frozenset(_key(b) for b in occupied),
                switch_positions={
                    _key(block): position
                    for block, position in self.switches.items()
                },
            ),
        ))
        self.switches = {
            key.block_id: position
            for key, position in out.track_model.switch_commands.items()
        }
        return self.switches


class AtRest(unittest.TestCase):
    """With no train near, each switch stands for the train it cannot
    see coming."""

    def test_switch_28_stands_reverse_for_a_train_from_150(self) -> None:
        # A train on 150 is in GTC-06; GTC-02 cannot see it, and the CTC
        # Office gives it no authority into 28 until 28 reads reverse.
        self.assertEqual(_Line().tick()["28"], "reverse")

    def test_the_others_stand_normal(self) -> None:
        switches = _Line().tick()
        self.assertEqual(
            {sid: switches[sid] for sid in ("12", "58", "62", "76", "85")},
            dict.fromkeys(("12", "58", "62", "76", "85"), "normal"),
        )


class Switch76(unittest.TestCase):
    """Points at 77: from 76 out to 78 (normal), from 78 on to 101
    (reverse). The reverse leg is in GTC-05."""

    def test_reverse_for_a_train_on_78_about_to_enter_77(self) -> None:
        line = _Line()
        self.assertEqual(
            line.tick(occupied={"78"}, suggested={"78", "77"})["76"],
            "reverse",
        )

    def test_a_train_on_78_going_the_other_way_leaves_it_normal(
        self,
    ) -> None:
        # Out from 77 toward 79: its next block is 79, not 77.
        line = _Line()
        self.assertEqual(
            line.tick(occupied={"78"}, suggested={"78", "79"})["76"],
            "normal",
        )

    def test_held_reverse_while_the_train_is_on_the_points(self) -> None:
        line = _Line()
        line.tick(occupied={"78"}, suggested={"78", "77"})
        # On 77, its next block (101) is another wayside's.
        for _ in range(3):
            self.assertEqual(
                line.tick(occupied={"77"}, suggested={"77"})["76"],
                "reverse",
            )
        # Gone on to 101: the points are clear, and nothing is coming.
        self.assertEqual(line.tick()["76"], "normal")

    def test_normal_for_a_train_about_to_enter_76(self) -> None:
        # The train is on 75, in GTC-03; GTC-04 sees 76 preloaded. 76 is
        # the block switch 76 is listed on, so the switch locks once the
        # train is in it: it must be normal before.
        line = _Line()
        line.tick(occupied={"78"}, suggested={"78", "77"})
        line.tick()
        line.tick(occupied={"78"}, suggested={"78", "77"})
        self.assertEqual(line.switches["76"], "reverse")
        self.assertEqual(line.tick(suggested={"76"})["76"], "normal")
        self.assertEqual(
            line.tick(occupied={"76"}, suggested={"76", "77"})["76"],
            "normal",
        )

    def test_held_normal_while_a_train_from_76_is_on_the_points(
        self,
    ) -> None:
        line = _Line()
        line.tick(suggested={"76"})
        line.tick(occupied={"76"}, suggested={"76", "77"})
        # On 77 with no authority on, so nothing is preloaded.
        self.assertEqual(line.tick(occupied={"77"}, suggested={"77"})["76"],
                         "normal")

    def test_two_trains_coming_for_both_legs_hold_it(self) -> None:
        line = _Line()
        self.assertEqual(
            line.tick(occupied={"78"}, suggested={"78", "77", "76"})["76"],
            "normal",
        )


class Switch28(unittest.TestCase):
    """Points at 28: from 150 on to 27 (reverse), from 27 out to 29
    (normal). The reverse leg is in GTC-06."""

    def test_normal_for_a_train_on_27_about_to_enter_28(self) -> None:
        line = _Line()
        self.assertEqual(
            line.tick(occupied={"27"}, suggested={"27", "28"})["28"],
            "normal",
        )
        # On 28 it is locked, and held, normal.
        self.assertEqual(
            line.tick(occupied={"28"}, suggested={"28", "29"})["28"],
            "normal",
        )
        self.assertEqual(line.tick(occupied={"29"}, suggested={"29"})["28"],
                         "reverse")

    def test_a_train_from_150_runs_on_through_27(self) -> None:
        line = _Line()
        line.tick()
        self.assertEqual(line.tick(occupied={"28"}, suggested={"28", "27"})
                         ["28"], "reverse")
        # On 27 going away from 28, its next block is 26.
        self.assertEqual(
            line.tick(occupied={"27"}, suggested={"27", "26"})["28"],
            "reverse",
        )


class Switch12(unittest.TestCase):
    """Points at 13: from 14 on to 12 (normal), from 1 out to 14
    (reverse)."""

    def test_reverse_for_a_train_on_1(self) -> None:
        line = _Line()
        self.assertEqual(
            line.tick(occupied={"2"}, suggested={"2", "1"})["12"],
            "normal",
        )
        self.assertEqual(line.tick(occupied={"1"}, suggested={"1"})["12"],
                         "reverse")

    def test_held_reverse_while_the_train_is_on_the_points(self) -> None:
        line = _Line()
        line.tick(occupied={"1"}, suggested={"1"})
        self.assertEqual(line.switches["12"], "reverse")
        # On 13 (the points; the switch is listed on 12), heading for 14.
        self.assertEqual(
            line.tick(occupied={"13"}, suggested={"13", "14"})["12"],
            "reverse",
        )
        self.assertEqual(line.tick(occupied={"14"}, suggested={"14"})["12"],
                         "normal")

    def test_normal_for_a_train_on_14_about_to_enter_13(self) -> None:
        line = _Line()
        line.tick(occupied={"1"}, suggested={"1"})
        line.tick()
        self.assertEqual(
            line.tick(occupied={"14"}, suggested={"14", "13"})["12"],
            "normal",
        )


class Switch85(unittest.TestCase):
    """Points at 85: from 100 on to 84 (reverse), from 84 out to 86
    (normal)."""

    def test_reverse_for_a_train_on_100(self) -> None:
        line = _Line()
        self.assertEqual(
            line.tick(occupied={"100"}, suggested={"100"})["85"],
            "reverse",
        )
        self.assertEqual(
            line.tick(occupied={"85"}, suggested={"85", "84"})["85"],
            "reverse",
        )
        self.assertEqual(line.tick(occupied={"84"}, suggested={"84"})["85"],
                         "normal")


class YardSwitches(unittest.TestCase):
    """The yard is a black box (D022): no route runs into or out of it,
    so its switches stay normal. A train is retired stopped at 57."""

    def test_a_train_stopping_at_57_leaves_58_normal(self) -> None:
        line = _Line()
        self.assertEqual(
            line.tick(occupied={"56"}, suggested={"56", "57"})["58"],
            "normal",
        )
        self.assertEqual(line.tick(occupied={"57"}, suggested={"57"})["58"],
                         "normal")


class Maintenance(unittest.TestCase):
    """In maintenance the program throws nothing reverse, as before, but
    it still moves no switch whose points are occupied."""

    def test_normal_unless_a_train_is_on_the_points(self) -> None:
        line = _Line()
        line.tick(occupied={"78"}, suggested={"78", "77"})
        line.tick(occupied={"77"}, suggested={"77"})
        self.assertEqual(line.switches["76"], "reverse")
        # The dispatcher sets switch 12: maintenance mode, system-wide.
        held = line.tick(occupied={"77"}, suggested={"77"},
                         commands={"12": "reverse"})
        self.assertEqual((held["12"], held["76"]), ("reverse", "reverse"))
        self.assertEqual(line.tick(commands={"12": "reverse"})["76"],
                         "normal")
        # Switch 28 stands normal too, until maintenance ends.
        self.assertEqual(line.switches["28"], "normal")
        self.assertEqual(line.tick()["28"], "reverse")


class InputImage(unittest.TestCase):
    """What the starter reads that it did not before."""

    def setUp(self) -> None:
        self.controller = _green().controller("GTC-04")

    def test_suggestion_and_switch_position_bits(self) -> None:
        names = self.controller.input_names()
        self.assertIn("SUG_77", names)
        self.assertIn("REV_76", names)
        self.assertNotIn("SUG_101", names)
        self.controller.set_suggestion("77", 10, 1)
        image = self.controller.build_scan_inputs(self.controller.inputs)
        self.assertTrue(image["SUG_77"])
        self.assertFalse(image["SUG_78"])
        self.assertFalse(image["REV_76"])

    def test_every_generated_program_compiles_clean(self) -> None:
        for line in build_default_system():
            module = SwTrackController()
            module.load_track(line)
            for wayside_id in module.wayside_ids:
                controller = module.controller(wayside_id)
                program = compile_program(default_program_source(controller))
                self.assertEqual(
                    controller.diagnose(program), (),
                    f"{line.key} {wayside_id}",
                )


if __name__ == "__main__":
    unittest.main()
