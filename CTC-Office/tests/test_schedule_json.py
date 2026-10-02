"""Tests for the schedule workbook to JSON converter.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import schedule_to_json as converter  # noqa: E402


class StationNameTest(unittest.TestCase):

    def test_names_cleaned(self) -> None:
        cases = {
            "STATION; PIONEER": "PIONEER",
            "STATION: SHADYSIDE": "SHADYSIDE",
            "STATION; CENTRAL; UNDERDROUND": "CENTRAL",
            "STATION;   CASTLE SHANNON": "CASTLE SHANNON",
            "STATION": None,
            "": None,
        }
        for cell, name in cases.items():
            with self.subTest(cell=cell):
                self.assertEqual(converter.station_name(cell), name)


class ScheduleJsonTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.document, cls.warnings = converter.convert()

    def test_committed_json_is_current(self) -> None:
        with open(converter.OUTPUT, encoding="utf-8") as committed:
            self.assertEqual(json.load(committed), self.document)

    def test_shape(self) -> None:
        self.assertEqual(self.document["time_unit"], "s")
        self.assertEqual(self.document["headway_s"], 180)
        lines = {line["line"]: line for line in self.document["lines"]}
        self.assertEqual(set(lines), {"Green", "Red"})
        for line in lines.values():
            self.assertEqual(len(line["trains"]), 10)
            for train in line["trains"]:
                self.assertIsInstance(train["train_id"], str)
                for stop in train["stops"]:
                    self.assertIsInstance(stop["block_id"], str)
                    self.assertIsInstance(stop["arrival_s"], int)

    def test_trains_are_one_headway_apart(self) -> None:
        for line in self.document["lines"]:
            trains = line["trains"]
            for a, b in zip(trains, trains[1:]):
                gaps = {sb["arrival_s"] - sa["arrival_s"]
                        for sa, sb in zip(a["stops"], b["stops"])}
                self.assertEqual(gaps, {180})

    def test_known_workbook_anomalies_reported(self) -> None:
        joined = "\n".join(self.warnings)
        self.assertIn("Green block 113", joined)
        self.assertIn("132 -> 141", joined)
        self.assertEqual(len(self.warnings), 2)


if __name__ == "__main__":
    unittest.main()
