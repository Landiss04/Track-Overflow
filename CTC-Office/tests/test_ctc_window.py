"""The CTC Office window, loaded offscreen, redraws in place.

A redraw that moves trains or adds a sale updates the train cars and
the throughput history bars already drawn, where they belong, instead
of destroying and rebuilding every one of them, which was most of a
redraw's time at 10x (issue #66). ``window_probe.py`` runs the window
in its own process (it needs a QGuiApplication) and reports what it
shows after each of three redraws: T1 moving 3 -> 2, then T2 65 -> 66,
with 40 tickets sold at Glenbury in each of the last two.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

_PROBE = Path(__file__).resolve().parent / "window_probe.py"


class WindowRedrawTest(unittest.TestCase):
    """What the window shows after each redraw."""

    redraws: list[dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        done = subprocess.run(
            [sys.executable, str(_PROBE)], capture_output=True, text=True,
            timeout=120, check=False)
        if done.returncode != 0:
            raise AssertionError(
                f"window_probe failed ({done.returncode}):\n{done.stderr}")
        cls.redraws = json.loads(done.stdout.strip().splitlines()[-1])[
            "redraws"]

    def test_train_cars_are_drawn_where_the_map_places_them(self) -> None:
        for number, shown in enumerate(self.redraws):
            self.assertEqual(sorted(shown["cars"]), ["T1", "T2"])
            for train, car in shown["cars"].items():
                with self.subTest(redraw=number, train=train):
                    self.assertEqual([car["x"], car["y"]],
                                     car["expected"])

    def test_train_cars_move_in_place(self) -> None:
        first, *later = self.redraws
        # Each moved, and is the same item it was.
        self.assertNotEqual(later[0]["cars"]["T1"]["y"],
                            first["cars"]["T1"]["y"])
        self.assertNotEqual(later[1]["cars"]["T2"]["y"],
                            first["cars"]["T2"]["y"])
        for shown in later:
            for train in ("T1", "T2"):
                self.assertEqual(shown["cars"][train]["address"],
                                 first["cars"][train]["address"], train)

    def test_history_bars_update_in_place(self) -> None:
        first, *later = self.redraws
        # One chart per mode's view: Automatic, Manual, Maintenance.
        self.assertEqual(len(first["bars"]), 3)
        self.assertEqual({bar["height"] for bar in first["bars"]}, {0})
        self.assertEqual([shown["counts"] for shown in self.redraws],
                         [[0], [40], [80]])
        for shown in later:
            self.assertEqual([bar["address"] for bar in shown["bars"]],
                             [bar["address"] for bar in first["bars"]])
            self.assertTrue(all(bar["height"] > 0
                                for bar in shown["bars"]))


if __name__ == "__main__":
    unittest.main()
