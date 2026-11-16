"""The CTC Office window, loaded offscreen, redraws in place.

A redraw that moves trains updates the train cars already drawn, where
they belong, instead of destroying and rebuilding every one of them,
which was most of a redraw's time at 10x (issue #66). Each switch's
signal light is drawn at the block the light stands on, its points,
shaped by its aspect. ``window_probe.py`` runs the window in its own
process (it needs a QGuiApplication) and reports what it shows after
each of three redraws: T1 moving 3 -> 2, then T2 65 -> 66, with 40
tickets sold at Glenbury in each of the last two; no signal reported
in the first, four reported in the second (Green 12 RED, Green 62
YELLOW, Red 15 GREEN, Red 9 SUPER_GREEN), Green 12 GREEN in the third.

``stop_list_probe.py`` works the Manual view's Dispatch panel with the
mouse (dispatch, queue, ▲ ▼, ×, drag) and reports the stop cards the
list shows after each action.

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
_STOPS_PROBE = Path(__file__).resolve().parent / "stop_list_probe.py"


def _probe(path: Path) -> dict[str, Any]:
    """Run a probe in its own process; the JSON it prints last."""
    done = subprocess.run(
        [sys.executable, str(path)], capture_output=True, text=True,
        encoding="utf-8", timeout=120, check=False)
    if done.returncode != 0:
        raise AssertionError(
            f"{path.name} failed ({done.returncode}):\n{done.stderr}")
    return json.loads(done.stdout.strip().splitlines()[-1])


class WindowRedrawTest(unittest.TestCase):
    """What the window shows after each redraw."""

    redraws: list[dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.redraws = _probe(_PROBE)["redraws"]

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

    def test_each_light_is_drawn_at_its_points_not_its_switch(
            self) -> None:
        # Agreed with the Track Model 2026-10-28: the light stands at
        # the switch's points (common/harness/track_devices.py).
        points = {"Green-12": "13", "Green-28": "28", "Green-58": "57",
                  "Green-62": "63", "Green-76": "77", "Green-85": "85",
                  "Red-9": "9", "Red-15": "16", "Red-27": "27",
                  "Red-32": "33", "Red-38": "38", "Red-43": "44",
                  "Red-52": "52"}
        for shown in self.redraws:
            self.assertEqual({name: light["drawnAt"]
                              for name, light in shown["lights"].items()},
                             points)
            self.assertTrue(all(light["visible"]
                                for light in shown["lights"].values()))

    def test_a_light_not_reported_is_hollow(self) -> None:
        first, second, _ = self.redraws
        for name, light in first["lights"].items():
            self.assertEqual(light["shapes"], ["hollow"], name)
        self.assertEqual(second["lights"]["Green-85"]["shapes"],
                         ["hollow"])

    def test_each_aspect_has_its_own_shape(self) -> None:
        # Readable without colour: the shape alone tells the aspect.
        _, second, third = self.redraws
        self.assertEqual(
            {name: (light["aspect"], light["shapes"])
             for name, light in second["lights"].items()
             if light["aspect"]},
            {"Green-12": ("RED", ["square"]),
             "Green-62": ("YELLOW", ["triangle"]),
             "Red-15": ("GREEN", ["circle"]),
             "Red-9": ("SUPER_GREEN", ["diamond"])})
        self.assertEqual(third["lights"]["Green-12"]["shapes"], ["circle"])

    def test_markers_change_in_place_and_keep_their_size(self) -> None:
        first, *later = self.redraws
        for shown in later:
            for name, light in shown["lights"].items():
                self.assertEqual(light["address"],
                                 first["lights"][name]["address"], name)
        for shown in self.redraws:
            for name, light in shown["lights"].items():
                # At the default Fit zoom, never under the 12 px floor.
                self.assertGreaterEqual(min(light["screenSize"]), 12, name)

    def test_the_signals_panels_show_the_same_aspects(self) -> None:
        # One Signals panel per mode's view: Automatic, Manual,
        # Maintenance.
        for shown in self.redraws:
            self.assertEqual(sorted(shown["rows"]),
                             sorted(shown["lights"]))
            for name, aspects in shown["rows"].items():
                self.assertEqual(
                    aspects, [shown["lights"][name]["aspect"]] * 3, name)


class StopListWindowTest(unittest.TestCase):
    """The Dispatch panel's stops in Manual mode, worked with the mouse
    (``stop_list_probe.py``): G1 dispatched to Glenbury (65), Dormont
    (73) and block 70 queued, the first moved down, the second removed,
    the second moved up, Mt Lebanon (77) queued, and the third dragged
    to the top."""

    steps: dict[str, dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.steps = {step["action"]: step
                     for step in _probe(_STOPS_PROBE)["steps"]}

    def _names(self, action: str) -> list[str]:
        # Each card's ordinal and stop name, as the list shows them.
        return [" ".join(card[:2]) for card in self.steps[action]["cards"]]

    def test_the_button_says_dispatch_then_queue(self) -> None:
        self.assertEqual(self.steps["picked"]["button"], "Dispatch train")
        self.assertEqual(self.steps["picked"]["cards"], [])
        for action in ("dispatched 65", "queued 73", "dragged 3 to 1"):
            self.assertEqual(self.steps[action]["button"], "Queue stop")

    def test_adding_stops_lists_a_card_each(self) -> None:
        self.assertEqual(self._names("dispatched 65"), ["1 Glenbury"])
        self.assertEqual(self._names("queued 73"),
                         ["1 Glenbury", "2 Dormont"])
        self.assertEqual(self._names("queued block 70"),
                         ["1 Glenbury", "2 Dormont", "3 Block 70"])
        first = self.steps["dispatched 65"]["cards"][0]
        self.assertIn("arr 05:10", first)
        self.assertIn("IN YARD", first)
        self.assertEqual(self.steps["queued block 70"]["stops"],
                         ["65", "73", "70"])

    def test_arrows_and_remove_change_the_stops(self) -> None:
        expected = {
            "moved 1 down": ["73", "65", "70"],
            "removed 2": ["73", "70"],
            "moved 2 up": ["70", "73"],
            "queued 77": ["70", "73", "77"],
        }
        for action, stops in expected.items():
            with self.subTest(action=action):
                self.assertEqual(self.steps[action]["stops"], stops)
                self.assertEqual(len(self.steps[action]["cards"]),
                                 len(stops))
        self.assertEqual(self._names("removed 2"),
                         ["1 Dormont", "2 Block 70"])

    def test_dragging_a_card_moves_its_stop(self) -> None:
        step = self.steps["dragged 3 to 1"]
        self.assertEqual(step["stops"], ["77", "70", "73"])
        self.assertEqual(self._names("dragged 3 to 1"),
                         ["1 Mt Lebanon", "2 Block 70", "3 Dormont"])
        self.assertEqual(step["message"], "G1's stops reordered.")


if __name__ == "__main__":
    unittest.main()
