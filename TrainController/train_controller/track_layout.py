"""Track layout loading for the Train Controller.

Layout data comes from the course-provided JSON files in ``TrackModel/``
at startup (``truth/conventions/files-and-paths.md``). Each file names a
line and lists its blocks. Values are converted to backend units on read
(km/h to m/s), and block numbers are read as strings, because IDs are
never integers (``truth/conventions/identifiers.md``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from train_controller.units import kmh_to_mps

REPO_ROOT = Path(__file__).resolve().parents[2]
GREEN_LINE_PATH = REPO_ROOT / "TrackModel" / "green_line.json"

# Layout-file station sides mapped to the side the doors open on.
_PLATFORM_SIDES: dict[str, str] = {
    "Left": "LEFT",
    "Right": "RIGHT",
    "Left/Right": "BOTH",
}


@dataclass(frozen=True)
class TrackBlock:
    """One block of a line, in backend units."""

    block_id: str
    section: str
    length_m: float
    speed_limit_mps: float
    station_name: str = ""
    platform_side: str = ""

    @property
    def is_station(self) -> bool:
        """Whether this block has a station platform."""
        return self.station_name != ""


def load_line(
    path: Path = GREEN_LINE_PATH,
) -> tuple[str, tuple[TrackBlock, ...]]:
    """Return the line name and its blocks, in file order."""
    with open(path, encoding="utf-8") as layout_file:
        layout = json.load(layout_file)

    blocks = []
    for raw in layout["blocks"]:
        infrastructure = raw.get("infrastructure") or {}
        station_name = infrastructure.get("station") or ""
        platform_side = (
            _PLATFORM_SIDES.get(raw.get("station_side") or "", "")
            if station_name else ""
        )
        blocks.append(TrackBlock(
            block_id=str(raw["block_number"]),
            section=raw["section"],
            length_m=float(raw["length_m"]),
            speed_limit_mps=kmh_to_mps(raw["speed_limit_kmh"]),
            station_name=station_name,
            platform_side=platform_side,
        ))
    return layout["line"], tuple(blocks)


def route_between(
    blocks: tuple[TrackBlock, ...], first_id: str, last_id: str
) -> tuple[TrackBlock, ...]:
    """Return the contiguous run of blocks from ``first_id`` to ``last_id``.

    The run follows file order, which is ascending block number. Routing
    through switches is not modelled.
    """
    ids = [block.block_id for block in blocks]
    start = ids.index(first_id)
    end = ids.index(last_id)
    if end < start:
        raise ValueError(f"block {last_id} is not after block {first_id}")
    return blocks[start:end + 1]
