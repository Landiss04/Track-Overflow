"""Tests for reading a track layout, dividing it, and units for display.

Run from ``TrackCtrlSW``::

    .venv/Scripts/python -m unittest discover -s tests -v

These need no Qt: the layout loader, the PLC and the unit conversions are
plain Python.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from track_ctrl.display import (  # noqa: E402
    format_mph,
    mph_to_mps,
    mps_to_mph,
    whole_mps_from_mph,
)
from track_ctrl.layout import (  # noqa: E402
    LayoutError,
    build_default_system,
    default_layout_dir,
    load_layout_file,
    parse_layout,
)

GREEN = default_layout_dir() / "green_line.json"
RED = default_layout_dir() / "red_line.json"


def tiny(**changes: object) -> dict[str, object]:
    """A small valid layout, with ``changes`` applied to the top level."""
    layout: dict[str, object] = {
        "line": "Purple",
        "blocks": [
            {"block_number": number, "section": "A", "length_m": 50,
             "grade_percent": 0, "speed_limit_kmh": 36}
            for number in range(1, 7)
        ],
    }
    layout.update(changes)
    return layout


class RealLayoutTests(unittest.TestCase):
    """The course layouts are what the system really starts with."""

    def test_green_has_the_blocks_switches_and_crossings_in_the_file(self) -> None:
        green = load_layout_file(GREEN)
        self.assertEqual(green.key, "Green")
        self.assertEqual(len(green.blocks), 150)
        self.assertEqual(
            list(green.switches),
            ["12", "28", "58", "62", "76", "85"],
        )
        self.assertEqual(green.crossings, ("19", "108"))

    def test_red_has_its_own_switches(self) -> None:
        red = load_layout_file(RED)
        self.assertEqual(len(red.blocks), 76)
        self.assertEqual(len(red.switches), 7)
        self.assertEqual(red.crossings, ("11", "47"))

    def test_blocks_are_in_block_number_order_with_real_limits(self) -> None:
        blocks = load_layout_file(GREEN).blocks
        self.assertEqual([b.index for b in blocks], list(range(1, 151)))
        self.assertAlmostEqual(blocks[0].speed_limit_mps, 45 / 3.6)
        self.assertEqual(blocks[0].whole_speed_limit_mps, 12)
        self.assertEqual(blocks[0].label, "A1")

    def test_switch_strings_are_read_normal_first_then_reverse(self) -> None:
        # Each is (point, normal end, reverse end).
        green = load_layout_file(GREEN).switches
        self.assertEqual(green["12"], ("13", "12", "1"))   # "12-13; 1-13"
        # "57-yard" lists only the diverging route, to the yard.
        self.assertEqual(green["58"], ("57", "58", "yard"))

    def test_the_direction_of_travel_is_read_and_shared_by_the_line(
        self,
    ) -> None:
        blocks = {b.block_id: b for b in load_layout_file(GREEN).blocks}
        self.assertEqual(blocks["77"].next_blocks, ("78", "101"))
        self.assertEqual(blocks["57"].next_blocks, ("58", "yard"))
        green = build_default_system()[0]
        # Every wayside carries the whole line's, for its starter.
        first = green.controllers[0]
        self.assertFalse(first.owns("150"))
        self.assertEqual(first.next_blocks("150"), ("28",))
        self.assertEqual(first.next_blocks("999"), ())

    def test_the_default_system_is_green_and_red_divided_into_waysides(self) -> None:
        green, red = build_default_system()
        self.assertEqual((green.name, red.name), ("Green Line", "Red Line"))
        self.assertEqual(len(green.controllers), 6)
        self.assertEqual(len(red.controllers), 5)
        self.assertEqual(green.controllers[0].controller_id, "GTC-01")
        self.assertEqual(red.controllers[0].controller_id, "RTC-01")

    def test_blue_is_refused_with_the_reason(self) -> None:
        with self.assertRaises(LayoutError) as caught:
            load_layout_file(default_layout_dir() / "blue_line.json")
        self.assertIn("yard", str(caught.exception))


class PartitionTests(unittest.TestCase):
    def test_every_block_belongs_to_exactly_one_controller(self) -> None:
        parsed = load_layout_file(GREEN)
        for count in (2, 3, 6, 7, 150):
            line = parsed.divide(count)
            owned = [b for c in line.controllers for b in c.block_ids]
            self.assertEqual(owned, [b.block_id for b in parsed.blocks], count)

    def test_territories_are_contiguous_and_nearly_equal(self) -> None:
        line = load_layout_file(GREEN).divide(7)
        sizes = [len(c.block_ids) for c in line.controllers]
        self.assertLessEqual(max(sizes) - min(sizes), 1)
        for config in line.controllers:
            numbers = [int(b) for b in config.block_ids]
            self.assertEqual(numbers, list(range(numbers[0], numbers[-1] + 1)))

    def test_a_switch_belongs_to_the_wayside_that_owns_its_block(self) -> None:
        line = load_layout_file(GREEN).divide(6)
        for config in line.controllers:
            for switch_id in config.switches:
                self.assertIn(switch_id, config.block_ids)
        # Block 76's switch leads to 101, which another wayside owns.
        owner = next(c for c in line.controllers
                     if "76" in c.switches)
        self.assertNotIn("101", owner.block_ids)

    def test_a_signal_stands_at_every_switch_and_nowhere_else(self) -> None:
        for config in build_default_system()[0].controllers:
            self.assertEqual(config.signals, tuple(config.switches))

    def test_a_crossing_is_armed_by_its_own_block_and_its_neighbours(self) -> None:
        line = load_layout_file(GREEN).divide(6)
        owner = next(c for c in line.controllers if "19" in c.crossings)
        self.assertEqual(owner.crossing_approach("19"), ("18", "19", "20"))

    def test_neighbours_follow_the_layout_not_the_block_numbers(self) -> None:
        line = load_layout_file(GREEN).divide(2)
        config = next(c for c in line.controllers if c.owns("77"))
        self.assertEqual(config.neighbours("77"), ("76", "78", "101"))
        self.assertIn("77", config.neighbours("101"))
        self.assertNotIn("100", config.neighbours("101"))
        self.assertNotIn("102", config.neighbours("77"))

    def test_the_wayside_count_is_limited_to_what_the_line_allows(self) -> None:
        parsed = load_layout_file(GREEN)
        for bad in (0, 1, 151, -3):
            with self.assertRaises(LayoutError):
                parsed.divide(bad)
        with self.assertRaises(LayoutError):
            parsed.divide(True)        # a flag is not a count
        with self.assertRaises(LayoutError):
            parsed.divide(2.5)         # type: ignore[arg-type]

    def test_plc_names_use_block_numbers(self) -> None:
        config = build_default_system()[0].controllers[0]
        switch, signal, crossing = (
            tuple(config.switches)[0], config.signals[0], config.crossings[0])
        self.assertEqual(config.switch_output(switch), "SW_12")
        self.assertEqual(config.aspect_outputs(signal)[0], "SIG_12_R")
        self.assertEqual(config.crossing_output(crossing), "XING_19")


class RefusalTests(unittest.TestCase):
    """A bad file is refused with a message and never half-read."""

    def refused(self, data: object, fragment: str) -> None:
        with self.assertRaises(LayoutError) as caught:
            parse_layout(data, "test.json")
        self.assertIn(fragment, str(caught.exception))

    def test_the_small_layout_used_here_is_valid(self) -> None:
        parsed = parse_layout(tiny())
        self.assertEqual((parsed.name, len(parsed.blocks)), ("Purple Line", 6))

    def test_shape_errors(self) -> None:
        self.refused([], "JSON object")
        self.refused(tiny(line=""), "line")
        self.refused(tiny(blocks=[]), "non-empty")
        self.refused(tiny(blocks="x"), "non-empty")

    def test_a_wayside_database_is_not_a_track_layout(self) -> None:
        self.refused(tiny(wayside="1"), "wayside database")

    def test_block_errors(self) -> None:
        def with_block(**changes: object) -> dict[str, object]:
            layout = copy.deepcopy(tiny())
            layout["blocks"][0].update(changes)      # type: ignore[index]
            return layout

        self.refused(with_block(block_number="abc"), "whole number")
        self.refused(with_block(block_number=True), "block_number")
        self.refused(with_block(speed_limit_kmh=0), "above zero")
        self.refused(with_block(speed_limit_kmh="fast"), "number")
        self.refused(with_block(speed_limit_kmh=float("inf")), "above zero")
        self.refused(with_block(length_m=-5), "above zero")
        self.refused(with_block(section=""), "section")
        self.refused(with_block(infrastructure="oops"), "infrastructure")
        self.refused(with_block(next_blocks=2), "next_blocks")
        self.refused(with_block(next_blocks=["two"]), "next_blocks")

    def test_a_duplicate_block_is_refused(self) -> None:
        layout = copy.deepcopy(tiny())
        layout["blocks"][1]["block_number"] = 1      # type: ignore[index]
        self.refused(layout, "twice")

    def test_switch_string_errors(self) -> None:
        def with_switch(text: object) -> dict[str, object]:
            layout = copy.deepcopy(tiny())
            layout["blocks"][2]["infrastructure"] = {"switch": text}  # type: ignore[index]
            return layout

        self.refused(with_switch(""), "not text")
        self.refused(with_switch("3-4; 5-6"), "share exactly one")
        self.refused(with_switch("3-4"), "yard")
        self.refused(with_switch("a-b; b-c"), "neither")
        self.refused(with_switch("1-2; 2-3; 3-4"), "one or two")

    def test_unreadable_files(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            missing = Path(folder) / "nope.json"
            with self.assertRaises(LayoutError) as caught:
                load_layout_file(missing)
            self.assertIn("Cannot read", str(caught.exception))

            broken = Path(folder) / "broken.json"
            broken.write_text("{ not json", encoding="utf-8")
            with self.assertRaises(LayoutError) as caught:
                load_layout_file(broken)
            self.assertIn("not valid JSON", str(caught.exception))

            good = Path(folder) / "purple.json"
            good.write_text(json.dumps(tiny()), encoding="utf-8")
            self.assertEqual(load_layout_file(good).key, "Purple")


class UnitTests(unittest.TestCase):
    """The system works in m/s; only the screen shows mph."""

    def test_the_factor_is_the_one_in_units_md(self) -> None:
        self.assertAlmostEqual(mps_to_mph(1.0), 2.236936)
        self.assertAlmostEqual(mph_to_mps(2.236936), 1.0)

    def test_display_text(self) -> None:
        self.assertEqual(format_mph(15), "33.6 MPH")
        self.assertEqual(format_mph(0), "0.0 MPH")

    def test_a_typed_speed_becomes_whole_mps_rounded_down(self) -> None:
        self.assertEqual(whole_mps_from_mph(35), 15)       # 15.65 m/s
        self.assertEqual(whole_mps_from_mph(33.6), 15)
        self.assertEqual(whole_mps_from_mph(33.5), 14)     # never rounds up
        self.assertEqual(whole_mps_from_mph(0), 0)

    def test_rounding_down_can_only_make_a_typed_speed_slower(self) -> None:
        for mph in (1, 5, 17.3, 27.9, 40, 55.5):
            self.assertLessEqual(whole_mps_from_mph(mph), mph_to_mps(mph))


if __name__ == "__main__":
    unittest.main()
