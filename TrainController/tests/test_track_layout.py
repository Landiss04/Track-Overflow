"""Unit tests for the Train Controller's track layout loader."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from train_controller.track_layout import (  # noqa: E402
    load_line,
    route_between,
)


class LoadLineTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.line_name, cls.blocks = load_line()
        cls.by_id = {block.block_id: block for block in cls.blocks}

    def test_line_name(self) -> None:
        self.assertEqual(self.line_name, "Green")

    def test_block_ids_are_strings(self) -> None:
        self.assertTrue(
            all(isinstance(block.block_id, str) for block in self.blocks))
        self.assertIn("65", self.by_id)

    def test_speed_limit_is_converted_to_mps(self) -> None:
        # Block 63 is 70 km/h in the layout file.
        self.assertAlmostEqual(self.by_id["63"].speed_limit_mps, 70 / 3.6)

    def test_station_and_platform_side(self) -> None:
        self.assertEqual(self.by_id["65"].station_name, "GLENBURY")
        self.assertEqual(self.by_id["65"].platform_side, "RIGHT")
        self.assertEqual(self.by_id["77"].platform_side, "BOTH")
        self.assertFalse(self.by_id["62"].is_station)

    def test_route_between_is_contiguous(self) -> None:
        route = route_between(self.blocks, "62", "76")
        self.assertEqual(route[0].block_id, "62")
        self.assertEqual(route[-1].block_id, "76")
        self.assertEqual(len(route), 15)

    def test_route_must_run_forward(self) -> None:
        with self.assertRaises(ValueError):
            route_between(self.blocks, "76", "62")


if __name__ == "__main__":
    unittest.main()
