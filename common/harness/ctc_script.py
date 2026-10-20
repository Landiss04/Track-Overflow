"""A scripted CTC Office, standing in for its dispatch and suggestions.

Until the CTC Office is wired in (Phase 4), the harness plays the part
of it the Track Controller needs, for one scripted run: it releases one
train from the yard and suggests a speed and an authority for it on
every tick (``signals/suggested-speed``, ``suggested-authority``). It
answers in the CTC Office's own output form (``ctc.interface``), so its
suggestions reach the Track Controller over the edge the CTC Office will
use (``wayside_edges.ctc_to_track_controller``). The CTC Office's stub
still presses Run and sets the speed.

It reads what the CTC Office reads from the Track Controller
(``wayside_edges.track_controller_to_ctc``): occupancy, which is all it
learns of trains, and each wayside's readiness.

- **Readiness (R44, R70).** A line is ready once a wayside on it has
  reported and every wayside on it is ready. Until then the stand-in
  releases no train and sends nothing for the line. The clock runs on.
- **Release (R46, D022).** Once the line is ready and its yard exit
  block is clear, it releases the train, once, as a ``new_trains``
  event.
- **Following the train.** It finds the train on the route's first
  block, then moves it on one block whenever the block ahead is
  occupied and its own is not, as the CTC Office follows its trains
  from occupancy (``arbitration/train-tracking-from-occupancy``). A
  failed block reads occupied (R33, R69): one ahead of the train is not
  taken for it.
- **Suggestions (R49).** For the block the train is in: an authority
  that runs to the next stop not yet served, or to the destination
  (D013, D020), and stops short of any occupied block ahead
  (``arbitration/authority-stops-before-obstruction``); and the
  block's speed, or 0 with no authority. While the authority is at
  least 1, the next block too, with one block less, so the train finds
  its values there as it enters.
- **Stops.** A stop holds the train ``STOP_HOLD_S`` after it enters the
  block, as a schedule would: braking to a stand, then the 45 s dwell.
  The CTC Office schedules the dwell and the Train Controller enforces
  it (D007), so the train leaves no sooner than 45 s after its doors
  open, however soon its authority comes back.

Speeds are whole m/s (R38), at or below each block's limit
(``arbitration/suggested-speed-under-block-limit``). The stand-in
serves its one train once: it closes no block and sends no switch
command.
"""

from __future__ import annotations

__all__ = [
    "GREEN_YARD_TO_DORMONT",
    "STOP_HOLD_S",
    "CtcRoute",
    "RouteBlock",
    "ScriptedCtc",
]

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from common.harness.wayside_edges import line_ready

#: How long a stop holds a train after it enters the stop's block:
#: about 15 s to brake to a stand, then D007's 45 s dwell.
STOP_HOLD_S = 60.0


@dataclass(frozen=True)
class RouteBlock:
    """One block of a scripted route.

    Attributes:
        block_id: The block's number on the route's line.
        speed_mps: The suggested speed while the train may go on, in
            whole m/s.
        hold_s: For a stop, how long after the train enters the block
            it may leave; None for a block it runs through.
    """

    block_id: str
    speed_mps: int
    hold_s: float | None = None


@dataclass(frozen=True)
class CtcRoute:
    """The one run the stand-in makes.

    Attributes:
        train_id: The train's ID, as the CTC Office gives it.
        line: The line, as the CTC Office names it.
        blocks: The route in order: the line's yard exit block first
            (D022), the destination last.
    """

    train_id: str
    line: str
    blocks: Sequence[RouteBlock]


class ScriptedCtc:
    """One train's release and suggestions, from what the CTC reads."""

    def __init__(self, route: CtcRoute) -> None:
        """Keep the route, with the train still in the yard.

        Raises:
            ValueError: If the route is empty or names a block twice.
        """
        numbers = [block.block_id for block in route.blocks]
        if not numbers or len(set(numbers)) != len(numbers):
            raise ValueError("a route needs blocks, each named once")
        self._route = route
        self._released = False
        # The route index of the block the train is in; None until it
        # is first seen.
        self._at: int | None = None
        # When the train entered each stop, by the stop's index.
        self._entered_s: dict[int, float] = {}

    @property
    def line(self) -> str:
        """The line the route is on."""
        return self._route.line

    @property
    def released(self) -> bool:
        """Whether the train has been released from the yard."""
        return self._released

    def step(
        self, sim_time_s: float, inputs: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Return this tick's outputs, from what the CTC Office reads.

        Args:
            sim_time_s: The simulation time of this tick.
            inputs: The CTC Office's input from the Track Controller:
                ``occupancy`` and ``waysides``.

        Returns:
            The CTC Office's outputs: ``new_trains``, and
            ``track_controller`` with its ``suggestions``,
            ``closed_blocks`` and ``switch_commands``.
        """
        route = self._route
        occupied = {
            each["block_id"] for each in inputs.get("occupancy", ())
            if each["line"] == route.line and each["occupied"]
        }
        new_trains = []
        suggestions = []
        if line_ready(inputs.get("waysides", ()), route.line):
            if not self._released:
                if route.blocks[0].block_id not in occupied:
                    self._released = True
                    new_trains.append(
                        {"train_id": route.train_id, "line": route.line}
                    )
            else:
                self._follow(sim_time_s, occupied)
                if self._at is not None:
                    suggestions = self._suggest(sim_time_s, occupied)
        return {
            "new_trains": new_trains,
            "track_controller": {
                "suggestions": suggestions,
                "closed_blocks": [],
                "switch_commands": [],
            },
        }

    def _follow(self, sim_time_s: float, occupied: Collection[str]) -> None:
        # Find the train on the first block, then move it on one block
        # when the block ahead fills and its own empties.
        blocks = self._route.blocks
        if self._at is None:
            if blocks[0].block_id in occupied:
                self._enter(0, sim_time_s)
            return
        ahead = self._at + 1
        if (
            ahead < len(blocks)
            and blocks[self._at].block_id not in occupied
            and blocks[ahead].block_id in occupied
        ):
            self._enter(ahead, sim_time_s)

    def _enter(self, index: int, sim_time_s: float) -> None:
        # The train is now in block ``index``; a stop's hold starts.
        self._at = index
        if self._route.blocks[index].hold_s is not None:
            self._entered_s.setdefault(index, sim_time_s)

    def _suggest(
        self, sim_time_s: float, occupied: Collection[str]
    ) -> list[dict[str, Any]]:
        # The block the train is in, and the next one while it may go.
        assert self._at is not None
        here = self._at
        blocks_left = self._authority(here, sim_time_s, occupied)
        found = [self._suggestion(here, blocks_left)]
        if blocks_left >= 1:
            found.append(self._suggestion(here + 1, blocks_left - 1))
        return found

    def _authority(
        self, index: int, sim_time_s: float, occupied: Collection[str]
    ) -> int:
        # Blocks from here to the first stop not yet served, or to the
        # destination, and short of any occupied block on the way. A
        # stop is served once its hold is over.
        blocks = self._route.blocks
        end = len(blocks) - 1
        for ahead in range(index, end):
            hold_s = blocks[ahead].hold_s
            if hold_s is None:
                continue
            entered_s = self._entered_s.get(ahead)
            if entered_s is None or sim_time_s - entered_s < hold_s:
                end = ahead
                break
        for ahead in range(index + 1, end + 1):
            if blocks[ahead].block_id in occupied:
                return ahead - index - 1
        return end - index

    def _suggestion(self, index: int, blocks_left: int) -> dict[str, Any]:
        # One block's suggestion: its speed while the train may go on.
        block = self._route.blocks[index]
        return {
            "train_id": self._route.train_id,
            "line": self._route.line,
            "block_id": block.block_id,
            "suggested_speed_mps": block.speed_mps if blocks_left else 0,
            "authority_blocks": blocks_left,
        }


#: G1 out of the Green Line's yard exit block (63), a stop at GLENBURY
#: (65, platform on the right), and on to DORMONT (73, platform on the
#: right), where the route ends with the train at a stand. Speeds keep
#: at or below each block's limit, rounded down to whole m/s: 70 km/h
#: (19 m/s) to block 66, 40 km/h (11 m/s) after.
GREEN_YARD_TO_DORMONT = CtcRoute(
    train_id="G1",
    line="Green",
    blocks=(
        RouteBlock("63", 12),
        RouteBlock("64", 12),
        RouteBlock("65", 12, hold_s=STOP_HOLD_S),
        RouteBlock("66", 12),
        RouteBlock("67", 11),
        RouteBlock("68", 11),
        RouteBlock("69", 11),
        RouteBlock("70", 11),
        RouteBlock("71", 11),
        RouteBlock("72", 11),
        RouteBlock("73", 11),
    ),
)
