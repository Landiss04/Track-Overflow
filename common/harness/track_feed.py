"""A fixed track feed, standing in for the Track Model in Phase 1.

Until the Track Model is wired in (Phase 2), the harness itself gives
each train's Train Model its track inputs, and its Train Controller the
light ahead, from a fixed script. The script is a list of segments,
each saying what a train finds from some time after it entered
service: the block it is in and that block's track info, the track
signal the Track Controller would send it, the beacon it passes, if
any, and the light ahead.

The script runs on time, not on where the train is: the blocks it
names are the train's as far as the Train Model is told. Polarity flips
at every block change, as a track circuit's does, so the Train Model
sees each change (``signals/block-change-event``). No passengers board.

``GREEN_STATION_STOP`` is the script the harness runs by default: out
of the Green Line's yard exit block, a stop at GLENBURY, and on, with
the blocks' real grade, length and speed limit from the layout file.
"""

from __future__ import annotations

__all__ = [
    "GREEN_STATION_STOP",
    "FeedBeacon",
    "FeedSegment",
    "FixedTrackFeed",
]

import bisect
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from utils.beacon_codec import encode_beacon

#: The light ahead, as the Track Model spells it
#: (``signals/signal-aspect-ahead``).
ASPECTS = ("RED", "YELLOW", "GREEN", "SUPER_GREEN")

KMH_PER_MPS = 3.6

# Segment starts within this of a train's elapsed time count as
# reached, so float sums of 0.1 s ticks land on the intended tick.
_TIME_TOLERANCE_S = 1e-6


@dataclass(frozen=True)
class FeedBeacon:
    """A station beacon (``signals/beacon``)."""

    station_name: str
    platform_side: str
    underground: bool = False

    def __post_init__(self) -> None:
        encode_beacon(self.station_name, self.platform_side, self.underground)


@dataclass(frozen=True)
class FeedSegment:
    """What a train finds from ``start_s`` after it entered service.

    Attributes:
        start_s: Simulation seconds since the train entered service.
        block_id: The block the train is in.
        commanded_speed_mps: The track signal's commanded speed.
        authority_blocks: The track signal's authority (D013).
        speed_limit_mps: The block's speed limit.
        grade_deg: The block's grade, positive uphill.
        elevation_m: The block's elevation.
        station_name: The block's station, if it has one.
        beacon: The beacon the train passes, if any.
        aspect_ahead: The next signal light ahead of the train.
    """

    start_s: float
    block_id: str
    commanded_speed_mps: float
    authority_blocks: int
    speed_limit_mps: float
    grade_deg: float = 0.0
    elevation_m: float = 0.0
    station_name: str | None = None
    beacon: FeedBeacon | None = None
    aspect_ahead: str = "GREEN"


class FixedTrackFeed:
    """Track inputs for any train, by time since it entered service."""

    def __init__(self, segments: Sequence[FeedSegment]) -> None:
        """Check and keep a script.

        Args:
            segments: The script, in time order, the first at 0 s.

        Raises:
            ValueError: If the script is empty, does not start at 0 s,
                is out of order, or names an unknown light.
        """
        if not segments or segments[0].start_s != 0.0:
            raise ValueError("a track feed must start at 0 s")
        starts = [segment.start_s for segment in segments]
        if any(a >= b for a, b in zip(starts, starts[1:])):
            raise ValueError("track feed segments must be in time order")
        for segment in segments:
            if segment.aspect_ahead not in ASPECTS:
                raise ValueError(f"no light {segment.aspect_ahead!r}")
        self._segments = tuple(segments)
        self._starts = starts
        # Polarity at each segment: it flips at every block change.
        self._polarity: list[bool] = []
        polarity = False
        for index, segment in enumerate(segments):
            if index and segment.block_id != segments[index - 1].block_id:
                polarity = not polarity
            self._polarity.append(polarity)

    def segment(self, elapsed_s: float) -> FeedSegment:
        """Return the segment a train is in at ``elapsed_s``."""
        return self._segments[self._index(elapsed_s)]

    def aspect_ahead(self, elapsed_s: float) -> str:
        """Return the light ahead of a train, in capitals."""
        return self.segment(elapsed_s).aspect_ahead

    def track_inputs(self, elapsed_s: float) -> dict[str, Any]:
        """Return a train's track inputs, in the Train Model's form.

        The form is ``train_model.interface.TrackInputs`` as JSON.
        """
        index = self._index(elapsed_s)
        segment = self._segments[index]
        beacon = segment.beacon
        return {
            "track_info": {
                "block_id": segment.block_id,
                "grade_deg": segment.grade_deg,
                "elevation_m": segment.elevation_m,
                "speed_limit_mps": segment.speed_limit_mps,
                "polarity": self._polarity[index],
                "station_name": segment.station_name,
            },
            "track_signal": {
                "commanded_speed_mps": segment.commanded_speed_mps,
                "authority_blocks": segment.authority_blocks,
            },
            "beacon": None if beacon is None else {
                "station_name": beacon.station_name,
                "platform_side": beacon.platform_side,
                "underground": beacon.underground,
            },
            "passengers_boarded": 0,
        }

    def _index(self, elapsed_s: float) -> int:
        # The last segment that has started.
        position = bisect.bisect_right(
            self._starts, elapsed_s + _TIME_TOLERANCE_S
        )
        return max(0, position - 1)


def _kmh(speed_kmh: float) -> float:
    # The layout files give speed limits in km/h.
    return speed_kmh / KMH_PER_MPS


#: Out of the Green Line's yard exit block (63, D022) at 45 km/h, a
#: stop at GLENBURY (block 65, platform on the right), a dwell of
#: about 50 s, and on into block 66. Authority counts down to the
#: stop, as a Track Controller's would: falling from 2 or more blocks
#: straight to none reads as a signal pickup failure
#: (``Train-Ctrl_HW/HARNESS_INTEGRATION.md``).
GREEN_STATION_STOP = (
    FeedSegment(0.0, "63", _kmh(45), 3, _kmh(70)),
    FeedSegment(25.0, "64", _kmh(45), 2, _kmh(70)),
    FeedSegment(
        40.0, "65", _kmh(45), 1, _kmh(70),
        station_name="GLENBURY",
        beacon=FeedBeacon("GLENBURY", "R"),
    ),
    FeedSegment(45.0, "65", 0.0, 0, _kmh(70), station_name="GLENBURY",
                aspect_ahead="RED"),
    FeedSegment(105.0, "65", _kmh(45), 3, _kmh(70),
                station_name="GLENBURY"),
    FeedSegment(125.0, "66", _kmh(45), 2, _kmh(70)),
)
