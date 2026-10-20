"""A scripted wayside, standing in for the Track Controller in Phase 2.

Until the Track Controller is wired in (Phase 3), the harness itself
gives the Track Model the commands a Track Controller would, for one
scripted route: each tick, per block, a commanded speed and an
authority (``signals/track-signal``), and the signal lights the route
needs. It reads only block occupancy, as a Track Controller does
(R33), and it stands in for the CTC Office's suggestions as well,
which reach the Track Controller from Phase 4.

The script is a route of blocks on one line, the first the line's yard
exit block (D022), the last the train's destination. Some blocks are
stops, where the wayside holds the train for a while after it enters,
as the CTC Office's schedule would: braking to a stand, then the 45 s
dwell. The CTC Office schedules the dwell and the Train Controller
enforces it (D007), so a train leaves no sooner than 45 s after its
doors open, however soon its authority comes back. For each occupied
block on the route the wayside commands:

- authority: the blocks left to the next stop not yet served, or to
  the destination (D013, D020: authority ends at a scheduled stop);
- commanded speed: the block's scripted speed, or 0 with no authority;
- the next block too, while the authority is at least 1, with one
  block less (``signals/suggested-speed``, R49), so a train entering a
  block finds its values already there.

Blocks are named by line and number (``conventions/identifiers``).
The harness maps them to the Track Model's names
(``track_edges.block_commands_to_track_model``).

The wayside serves one train, once: it commands every occupied block on
its route as if that train were in it, so a second train on the route
would be given authority into the first, and each stop holds a train
only the first time. A failed block reads occupied (R33), so the
wayside commands it too; its dead track circuit carries nothing anyway.
"""

from __future__ import annotations

__all__ = [
    "GREEN_YARD_TO_DORMONT",
    "RouteBlock",
    "ScriptedWayside",
    "WaysideRoute",
]

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

KMH_PER_MPS = 3.6

#: How long a stop holds a train after it enters the stop's block:
#: about 15 s to brake to a stand, then D007's 45 s dwell.
STOP_HOLD_S = 60.0


@dataclass(frozen=True)
class RouteBlock:
    """One block of a scripted route.

    Attributes:
        block_id: The block's number on the route's line.
        speed_mps: The commanded speed while the train may go on.
        hold_s: For a stop, how long after the train enters the block
            it may leave; None for a block it runs through.
    """

    block_id: str
    speed_mps: float
    hold_s: float | None = None


@dataclass(frozen=True)
class WaysideRoute:
    """A route for one train, and the lights it needs.

    Attributes:
        line: The line the route is on, as the CTC Office names it.
        blocks: The route in order: the line's yard exit block first,
            the destination last.
        signals: Lights to command on every tick, by block number:
            ``RED``, ``YELLOW``, ``GREEN`` or ``SUPER_GREEN``.
    """

    line: str
    blocks: Sequence[RouteBlock]
    signals: Mapping[str, str] = field(default_factory=dict)


class ScriptedWayside:
    """Per-block commands along one route, from occupancy alone."""

    def __init__(self, route: WaysideRoute) -> None:
        """Keep the route, with no train on it yet.

        Raises:
            ValueError: If the route is empty or names a block twice.
        """
        numbers = [block.block_id for block in route.blocks]
        if not numbers or len(set(numbers)) != len(numbers):
            raise ValueError("a route needs blocks, each named once")
        self._route = route
        self._index = {number: index for index, number in enumerate(numbers)}
        # When the train entered each stop, by the stop's index.
        self._entered_s: dict[int, float] = {}

    @property
    def line(self) -> str:
        """The line the route is on."""
        return self._route.line

    def step(
        self, sim_time_s: float, occupied: Collection[str]
    ) -> dict[str, dict[str, Any]]:
        """Return this tick's commands, from the blocks occupied.

        Args:
            sim_time_s: The simulation time of this tick.
            occupied: The numbers of the occupied blocks on the line.

        Returns:
            ``commanded_speed_mps``, ``commanded_authority`` and
            ``signal_commands``, each keyed by block number.
        """
        blocks = self._route.blocks
        here = sorted(
            self._index[number] for number in occupied
            if number in self._index
        )
        for index in here:
            if blocks[index].hold_s is not None:
                self._entered_s.setdefault(index, sim_time_s)
        speeds: dict[str, float] = {}
        authority: dict[str, int] = {}
        for index in here:
            blocks_left = self._authority(index, sim_time_s)
            self._command(index, blocks_left, speeds, authority)
            if blocks_left >= 1:
                # The next block, preloaded with one block less.
                self._command(index + 1, blocks_left - 1, speeds, authority)
        return {
            "commanded_speed_mps": speeds,
            "commanded_authority": authority,
            "signal_commands": dict(self._route.signals),
        }

    def _authority(self, index: int, sim_time_s: float) -> int:
        # Blocks from here to the first stop not yet served, or to the
        # destination. A stop is served once its hold is over.
        blocks = self._route.blocks
        last = len(blocks) - 1
        for ahead in range(index, last):
            hold_s = blocks[ahead].hold_s
            if hold_s is None:
                continue
            entered_s = self._entered_s.get(ahead)
            if entered_s is None or sim_time_s - entered_s < hold_s:
                return ahead - index
        return last - index

    def _command(
        self,
        index: int,
        blocks_left: int,
        speeds: dict[str, float],
        authority: dict[str, int],
    ) -> None:
        # One block's values: its speed while it may go on, else 0.
        block = self._route.blocks[index]
        speeds[block.block_id] = block.speed_mps if blocks_left else 0.0
        authority[block.block_id] = blocks_left


def _kmh(speed_kmh: float) -> float:
    # Speeds below are written in km/h, as the layout files give them.
    return speed_kmh / KMH_PER_MPS


#: Out of the Green Line's yard exit block (63), a stop at GLENBURY
#: (65, platform on the right), and on to DORMONT (73, platform on the
#: right), where the route ends with the train at a stand. Speeds keep
#: below each block's limit: 70 km/h to block 66, 40 km/h after. The
#: light on block 64 shows GREEN, the one light on the route.
GREEN_YARD_TO_DORMONT = WaysideRoute(
    line="Green",
    blocks=(
        RouteBlock("63", _kmh(45)),
        RouteBlock("64", _kmh(45)),
        RouteBlock("65", _kmh(45), hold_s=STOP_HOLD_S),
        RouteBlock("66", _kmh(45)),
        RouteBlock("67", _kmh(40)),
        RouteBlock("68", _kmh(40)),
        RouteBlock("69", _kmh(40)),
        RouteBlock("70", _kmh(40)),
        RouteBlock("71", _kmh(40)),
        RouteBlock("72", _kmh(40)),
        RouteBlock("73", _kmh(40)),
    ),
    signals={"64": "GREEN"},
)
