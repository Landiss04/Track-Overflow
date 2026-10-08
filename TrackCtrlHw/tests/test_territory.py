"""Wayside databases: parsing, switch strings and refusals."""

from __future__ import annotations

import json
import unittest

from track_ctrl_hw.errors import TerritoryError
from track_ctrl_hw.interface import BlockKey
from track_ctrl_hw.territory import parse_switch, parse_territory

from tests.support import DATA, territory


def database(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "line": "Green",
        "wayside": "9",
        "blocks": [
            {"block_number": 1, "section": "A", "length_m": 100,
             "speed_limit_kmh": 45},
            {"block_number": 2, "section": "A", "length_m": 50,
             "speed_limit_kmh": 36,
             "infrastructure": {"switch": "2-3; 1-2"}},
            {"block_number": 3, "section": "B", "length_m": 75,
             "speed_limit_kmh": 30,
             "infrastructure": {"railway_crossing": True}},
        ],
    }
    data.update(overrides)
    return data


class SampleWaysides(unittest.TestCase):
    def test_wayside_1(self) -> None:
        t = territory(1)
        self.assertEqual(
            (t.line, t.wayside_id, len(t.blocks)), ("Green", "1", 20)
        )
        (switch,) = t.switches
        self.assertEqual(
            (switch.switch_id, switch.point, switch.normal_end,
             switch.reverse_end),
            ("12", "13", "12", "1"),
        )
        self.assertEqual([k.label for k in t.crossings], ["E-19"])
        self.assertAlmostEqual(t.blocks[0].speed_limit_mps, 45 / 3.6)

    def test_wayside_2_leg_leaves_territory(self) -> None:
        (switch,) = territory(2).switches
        self.assertEqual(
            (switch.point, switch.normal_end, switch.reverse_end),
            ("28", "29", "150"),
        )

    def test_wayside_3_two_switches(self) -> None:
        switches = territory(3).switches
        self.assertEqual(
            [(s.switch_id, s.point, s.normal_end, s.reverse_end)
             for s in switches],
            [("76", "77", "76", "101"), ("85", "85", "86", "100")],
        )

    def test_samples_match_the_course_layout_file(self) -> None:
        with open(DATA.parents[1] / "TrackModel" / "green_line.json",
                  encoding="utf-8") as layout:
            line = {b["block_number"]: b for b in json.load(layout)["blocks"]}
        for number in (1, 2, 3):
            path = DATA / "waysides" / f"green_wayside_{number}.json"
            with open(path, encoding="utf-8") as sample:
                for block in json.load(sample)["blocks"]:
                    self.assertEqual(block, line[block["block_number"]])


class Parsing(unittest.TestCase):
    def test_ignores_fields_of_other_modules(self) -> None:
        data = database()
        data["blocks"][0].update(  # type: ignore[index]
            grade_percent=1.5, elevation_m=2, station_side="Left",
            infrastructure={"station": "PIONEER", "beacon": True},
        )
        t = parse_territory(data)
        self.assertEqual(len(t.blocks), 3)
        self.assertEqual([k.label for k in t.crossings], ["B-3"])

    def test_ids_are_strings(self) -> None:
        t = parse_territory(database(wayside=4))
        self.assertEqual(t.wayside_id, "4")
        self.assertEqual(t.blocks[0].key, BlockKey("Green", "A", "1"))

    def test_refusals(self) -> None:
        bad_cases = {
            "no wayside": {k: v for k, v in database().items()
                           if k != "wayside"},
            "no blocks": database(blocks=[]),
            "duplicate": database(blocks=[
                {"block_number": 1, "section": "A", "length_m": 1,
                 "speed_limit_kmh": 1}] * 2),
            "zero length": database(blocks=[
                {"block_number": 1, "section": "A", "length_m": 0,
                 "speed_limit_kmh": 1}]),
            "bool length": database(blocks=[
                {"block_number": 1, "section": "A", "length_m": True,
                 "speed_limit_kmh": 1}]),
            "crossing not bool": database(blocks=[
                {"block_number": 1, "section": "A", "length_m": 1,
                 "speed_limit_kmh": 1,
                 "infrastructure": {"railway_crossing": "yes"}}]),
            "not an object": ["line"],
        }
        for name, data in bad_cases.items():
            with self.subTest(name), self.assertRaises(TerritoryError):
                parse_territory(data)


class SwitchStrings(unittest.TestCase):
    ids = frozenset({"1", "5", "6", "11", "12", "13", "57", "58", "62",
                     "63", "76", "77", "85", "86"})

    def parse(self, text: str, listed: str) -> tuple[str, str, str]:
        switch = parse_switch(BlockKey("L", "S", listed), text, self.ids)
        return switch.point, switch.normal_end, switch.reverse_end

    def test_forms_in_the_course_files(self) -> None:
        self.assertEqual(self.parse("12-13; 1-13", "12"), ("13", "12", "1"))
        self.assertEqual(self.parse("76-77;77-101", "76"), ("77", "76", "101"))
        self.assertEqual(
            self.parse("85-86; 100-85", "85"), ("85", "86", "100")
        )
        self.assertEqual(self.parse("5 to 6; 5 to 11", "5"), ("5", "6", "11"))

    def test_yard_switches(self) -> None:
        self.assertEqual(self.parse("57-yard", "58"), ("57", "58", "yard"))
        self.assertEqual(self.parse("Yard-63", "62"), ("63", "62", "yard"))

    def test_refusals(self) -> None:
        for text, listed in (
            ("12-13; 14-15", "12"),     # no shared block
            ("12-13; 12-13", "12"),     # shared twice
            ("12-13", "12"),            # one connection, not the yard
            ("57-yard", "57"),          # normal route unknown
            ("12-12", "12"),            # a loop
            ("a-b", "12"),              # not numbers
            ("1-2; 2-3; 3-4", "2"),     # three connections
            ("40-41; 40-1", "40"),      # point outside the wayside
        ):
            with self.subTest(text), self.assertRaises(TerritoryError):
                parse_switch(BlockKey("L", "S", listed), text,
                             self.ids | {"1", "2", "3", "4", "14", "15"})


if __name__ == "__main__":
    unittest.main()
