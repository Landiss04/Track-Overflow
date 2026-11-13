"""The Green starter programs saved as .plc files (``programs/green``).

They are what a programmer loads at start-up, so they must still match
the generated starter and commit on their own waysides.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from track_ctrl.controller import default_program_source  # noqa: E402
from track_ctrl.layout import build_default_system  # noqa: E402
from track_ctrl.module import SwTrackController  # noqa: E402

PROGRAMS = Path(__file__).resolve().parents[1] / "programs" / "green"


def _green() -> SwTrackController:
    module = SwTrackController()
    for line in build_default_system():
        if line.key == "Green":
            module.load_track(line)
    return module


def _file(wayside_id: str) -> Path:
    return PROGRAMS / f"{wayside_id.lower().replace('-', '')}_starter.plc"


class GreenStarterFiles(unittest.TestCase):
    def test_every_wayside_has_a_file_matching_the_starter(self) -> None:
        module = _green()
        for wayside_id in module.wayside_ids:
            path = _file(wayside_id)
            self.assertTrue(path.exists(), path)
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                default_program_source(module.controller(wayside_id)),
                f"{path.name} is out of date: regenerate it from the starter",
            )

    def test_loading_every_file_makes_the_line_ready(self) -> None:
        module = _green()
        for wayside_id in module.wayside_ids:
            path = _file(wayside_id)
            module.load_program(
                wayside_id, path.read_text(encoding="utf-8"), path.name)
        self.assertTrue(module.ready)


if __name__ == "__main__":
    unittest.main()
