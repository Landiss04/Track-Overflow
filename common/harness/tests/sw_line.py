"""The Track Controller SW's Green Line, stepped one tick at a time.

A seeding helper for owner-boundary diagnostics (``test_green_follower``):
the module with its generated starter programs, fed occupancy, CTC
suggestions and switch commands, with the Track Model's switch read-back
following the last tick's commands.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

_SW = Path(__file__).resolve().parents[3] / "TrackCtrlSW"
if str(_SW) not in sys.path:
    sys.path.insert(0, str(_SW))

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

DT = 0.1


def _key(block: str) -> BlockKey:
    return BlockKey("Green", block)


class GreenLine:
    """The Green module with its starter programs, stepped by hand."""

    def __init__(self) -> None:
        self.module = SwTrackController()
        for line in build_default_system():
            if line.key == "Green":
                self.module.load_track(line)
        self.module.load_starter_programs()
        self.time_s = 0.0
        self.switches: dict[str, SwitchPosition] = {}

    def tick(
        self,
        occupied: Iterable[str] = (),
        suggested: Iterable[str] = (),
        commands: dict[str, SwitchPosition] | None = None,
    ) -> dict[str, SwitchPosition]:
        """Step once; return every switch's commanded position by ID."""
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
