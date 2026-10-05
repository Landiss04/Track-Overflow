"""Tests for the track layout loader and the track map geometry.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ctc.track_layout import load_layout  # noqa: E402
from ctc_ui.track_map import (  # noqa: E402
    LABEL_POSITIONS,
    MAP_HEIGHT,
    MAP_WIDTH,
    SECTION_PATHS,
    TrackMapModel,
    build_map,
    place_on_block,
    split_polyline,
)


def _pairs(flat: list[float]) -> list[tuple[float, float]]:
    return list(zip(flat[0::2], flat[1::2]))


def _length(points: list[tuple[float, float]]) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


class TrackLayoutTest(unittest.TestCase):

    def test_layout_files_load(self) -> None:
        layout = load_layout()
        self.assertEqual(len(layout["Green"].blocks), 150)
        self.assertEqual(len(layout["Red"].blocks), 76)
        block = layout["Green"].blocks[0]
        self.assertIsInstance(block.block_id, str)   # IDs are strings


class TrackMapTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.layout = load_layout()
        cls.map = build_map(cls.layout)

    def test_every_block_drawn_once(self) -> None:
        for name, line in self.layout.items():
            drawn = [b["blockId"] for b in self.map["blocks"]
                     if b["line"] == name]
            self.assertEqual(sorted(drawn),
                             sorted(b.block_id for b in line.blocks))

    def test_every_section_has_path_and_label(self) -> None:
        for name, line in self.layout.items():
            self.assertEqual(set(line.sections()), set(SECTION_PATHS[name]))
            self.assertEqual(set(line.sections()),
                             set(LABEL_POSITIONS[name]))

    def test_blocks_continuous_and_sized_by_length(self) -> None:
        for name, line in self.layout.items():
            for letter, blocks in line.sections().items():
                path = SECTION_PATHS[name][letter]
                pieces = split_polyline(path, [b.length_m for b in blocks])
                for a, b in zip(pieces, pieces[1:]):
                    self.assertLess(math.dist(a[-1], b[0]), 1e-6)
                self.assertLess(math.dist(pieces[-1][-1], path[-1]), 1e-6)
                total_px = _length(path)
                total_m = sum(b.length_m for b in blocks)
                for piece, block in zip(pieces, blocks):
                    self.assertAlmostEqual(
                        _length(piece) / total_px, block.length_m / total_m,
                        places=6, msg=f"{name} {block.block_id}")

    def test_markers_match_layout(self) -> None:
        stations = sum(b.station is not None
                       for line in self.layout.values()
                       for b in line.blocks)
        crossings = sum(b.railway_crossing
                        for line in self.layout.values()
                        for b in line.blocks)
        self.assertEqual(len(self.map["stations"]), stations)
        self.assertEqual(len(self.map["crossings"]), crossings)

    def test_points_inside_drawing(self) -> None:
        for block in self.map["blocks"]:
            for x, y in _pairs(block["points"]):
                self.assertTrue(0 <= x <= 850 and 0 <= y <= 930)


class TrainPlacementTest(unittest.TestCase):

    def test_place_on_block(self) -> None:
        self.assertEqual(place_on_block([(0, 0), (10, 0)], 0.25),
                         (2.5, 0.0, 0.0))
        # Clamped to the block, and never upside down: a track running
        # left or up still gives an angle within (-90, 90].
        self.assertEqual(place_on_block([(10, 0), (0, 0)], 2.0),
                         (0.0, 0.0, 0.0))
        self.assertEqual(place_on_block([(0, 10), (0, 0)], 0.5),
                         (0.0, 5.0, 90.0))
        # Along a bend: the second segment's heading.
        self.assertEqual(place_on_block([(0, 0), (10, 0), (10, 10)], 0.75),
                         (10.0, 5.0, 90.0))

    def test_place_trains_on_the_map(self) -> None:
        model = TrackMapModel()
        placed = model.placeTrains([
            {"train": "T1", "line": "Green", "block": "62",
             "fraction": 0.5},
            {"train": "T9", "line": "Red", "block": "150",
             "fraction": 0.5}])                 # no such block: left out
        (train,) = placed
        self.assertEqual((train["train"], train["line"]), ("T1", "Green"))
        self.assertTrue(0 <= train["x"] <= MAP_WIDTH)
        self.assertTrue(0 <= train["y"] <= MAP_HEIGHT)
        self.assertTrue(-90 < train["angle"] <= 90)


if __name__ == "__main__":
    unittest.main()
