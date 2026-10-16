"""The stand-in world the test UI plays around the Track Controller.

Standing alone, the Track Controller has neighbours that are not there:
a CTC Office that suggests speeds and closes blocks, a Track Model that
holds trains and switch machines, and the clock. The test UI plays all
three. This module is the CTC and Track Model part, without Qt, so it
can be tested without a window.

Each tick it builds the module's boundary inputs from its own state and
takes the module's outputs back as the Track Model's read-back: a switch
machine goes where it was told, a crossing and a signal show what they
were commanded. A switch can be held stuck to see what the controller
does about a machine that does not follow.

Nothing here reaches into the controller. It speaks only the boundary
types in :mod:`track_ctrl.interface`, as the central harness will.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from track_ctrl.errors import InvalidInputError
from track_ctrl.interface import (
    BlockKey,
    CtcInputs,
    SignalAspect,
    Suggestion,
    SwitchPosition,
    TrackControllerInputs,
    TrackControllerOutputs,
    TrackModelInputs,
)

#: Speed the stand-in CTC suggests for every block, in whole m/s. It is
#: deliberately above some posted limits, so the vital layer's clamp is
#: visible in a running system.
DEFAULT_SUGGESTED_SPEED_MPS = 15

#: Authority the stand-in CTC suggests for every block, in blocks.
DEFAULT_SUGGESTED_AUTHORITY = 4

#: Trains the stand-in places on a line: one per this many blocks, but
#: at least one and no more than the cap.
_BLOCKS_PER_TRAIN = 25
_MAX_TRAINS_PER_LINE = 3


def _whole(value: float, what: str) -> int:
    """Return ``value`` as a non-negative whole number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidInputError(f"{what} must be a number")
    if not math.isfinite(value) or value < 0:
        raise InvalidInputError(f"{what} must be zero or more")
    if value != int(value):
        raise InvalidInputError(f"{what} must be a whole number")
    return int(value)


@dataclass
class Train:
    """A train the stand-in Track Model walks along a line."""

    train_id: str
    line: str
    block_index: int
    #: Simulated seconds spent in each block, so trains advance at
    #: different rates and 10x runs them ten times as fast.
    seconds_per_block: float = 2.0
    elapsed_s: float = field(default=0.0, repr=False)


class StandInWorld:
    """The CTC Office and Track Model of a standalone run."""

    def __init__(self) -> None:
        #: Blocks of each line in order, by the boundary's line name.
        self.lines: dict[str, list[BlockKey]] = {}
        self.switch_blocks: list[BlockKey] = []
        self.crossing_blocks: list[BlockKey] = []
        self.signal_blocks: list[BlockKey] = []
        self.trains: list[Train] = []

        #: What the controller last said about its startup. The CTC does
        #: not dispatch or suggest anything until it is ready.
        self.controller_ready = False

        # The CTC Office's side.
        self.maintenance = False
        self.closed: set[BlockKey] = set()
        #: ``None`` is a block the CTC sends nothing for.
        self.suggestions: dict[BlockKey, Suggestion | None] = {}
        self.switch_commands: dict[BlockKey, SwitchPosition] = {}

        # The Track Model's side.
        self.occupancy_overrides: dict[BlockKey, bool] = {}
        self.stuck_switches: set[BlockKey] = set()
        self.switch_positions: dict[BlockKey, SwitchPosition] = {}
        self.crossings_active: dict[BlockKey, bool] = {}
        self.signal_aspects: dict[BlockKey, SignalAspect] = {}

        self._topology: tuple[Any, ...] = ()
        self._next_train_number = 100

    # --- topology ------------------------------------------------------

    def load_topology(self, controllers: Sequence[Mapping[str, Any]]) -> bool:
        """Learn the track from the controller's description of it.

        Returns whether anything changed. A line that is unchanged keeps
        its trains and every setting; a line that was replaced starts
        again, and settings for blocks that no longer exist are dropped.
        """
        lines: dict[str, list[BlockKey]] = {}
        switches: list[BlockKey] = []
        crossings: list[BlockKey] = []
        signals: list[BlockKey] = []
        for entry in controllers:
            line = entry["line_key"]
            blocks = lines.setdefault(line, [])
            blocks.extend(BlockKey(line, b["id"]) for b in entry["blocks"])
            switches.extend(
                BlockKey(line, item["block_id"]) for item in entry["switches"]
            )
            crossings.extend(BlockKey(line, b) for b in entry["crossings"])
            signals.extend(BlockKey(line, b) for b in entry["signals"])

        fingerprint = (
            tuple((line, tuple(keys)) for line, keys in lines.items()),
            tuple(switches), tuple(crossings), tuple(signals),
        )
        if fingerprint == self._topology:
            return False

        previous = self.lines
        self._topology = fingerprint
        self.lines = lines
        self.switch_blocks = switches
        self.crossing_blocks = crossings
        self.signal_blocks = signals

        known = {key for keys in lines.values() for key in keys}
        self.closed &= known
        self.occupancy_overrides = {
            key: value for key, value in self.occupancy_overrides.items()
            if key in known
        }
        self.suggestions = {
            key: value for key, value in self.suggestions.items()
            if key in known
        }
        for key in known:
            self.suggestions.setdefault(
                key,
                Suggestion(
                    DEFAULT_SUGGESTED_SPEED_MPS, DEFAULT_SUGGESTED_AUTHORITY
                ),
            )
        self.switch_commands = {
            key: value for key, value in self.switch_commands.items()
            if key in switches
        }
        self.stuck_switches &= set(switches)
        self.switch_positions = {
            key: value for key, value in self.switch_positions.items()
            if key in switches
        }
        self.crossings_active = {
            key: value for key, value in self.crossings_active.items()
            if key in crossings
        }
        self.signal_aspects = {
            key: value for key, value in self.signal_aspects.items()
            if key in signals
        }

        self.trains = [
            train for train in self.trains
            if train.line in lines and previous.get(train.line) == lines[
                train.line
            ]
        ]
        for line, keys in lines.items():
            if not any(train.line == line for train in self.trains):
                self._seed_trains(line, len(keys))
        return True

    def _seed_trains(self, line: str, block_count: int) -> None:
        """Place a few trains so the line has visible occupancy."""
        count = max(1, min(_MAX_TRAINS_PER_LINE,
                           block_count // _BLOCKS_PER_TRAIN))
        spacing = max(1, block_count // (count + 1))
        for position in range(count):
            self.trains.append(
                Train(
                    train_id=f"T-{self._next_train_number}",
                    line=line,
                    block_index=min(spacing * (position + 1), block_count),
                    seconds_per_block=2.0 + position,
                )
            )
            self._next_train_number += 1

    # --- the tick ------------------------------------------------------

    def advance(self, dt_s: float) -> None:
        """Move every train on by ``dt_s`` simulated seconds."""
        for train in self.trains:
            count = len(self.lines[train.line])
            train.elapsed_s += dt_s
            while train.elapsed_s >= train.seconds_per_block:
                train.elapsed_s -= train.seconds_per_block
                train.block_index = train.block_index % count + 1

    def train_blocks(self) -> dict[BlockKey, str]:
        """Block -> train ID, for every train on the track."""
        placed: dict[BlockKey, str] = {}
        for train in self.trains:
            keys = self.lines[train.line]
            index = min(train.block_index, len(keys)) - 1
            placed[keys[index]] = train.train_id
        return placed

    def occupied(self) -> frozenset[BlockKey]:
        """Blocks that read as occupied: trains, as edited by hand."""
        occupied = set(self.train_blocks())
        for key, value in self.occupancy_overrides.items():
            if value:
                occupied.add(key)
            else:
                occupied.discard(key)
        return frozenset(occupied)

    def build_inputs(self, time_s: float) -> TrackControllerInputs:
        """One tick of boundary inputs from the world as it stands."""
        return TrackControllerInputs(
            time_s=time_s,
            ctc=CtcInputs(
                closed_blocks=frozenset(self.closed),
                # Only in maintenance mode, as the real CTC does; it
                # sends no flag, so the commands are the whole signal.
                switch_commands=(
                    dict(self.switch_commands) if self.maintenance else {}
                ),
                suggestions={
                    key: value for key, value in self.suggestions.items()
                    if value is not None and self.controller_ready
                },
            ),
            track_model=TrackModelInputs(
                occupied_blocks=self.occupied(),
                switch_positions=dict(self.switch_positions),
                crossings_active=dict(self.crossings_active),
                signal_aspects=dict(self.signal_aspects),
            ),
        )

    def apply_outputs(self, outputs: TrackControllerOutputs) -> None:
        """Take the controller's commands as the Track Model would.

        A switch machine moves to the commanded position unless it is
        held stuck. Crossings and signals show what they were told.
        """
        self.controller_ready = outputs.ready
        for key, position in outputs.track_model.switch_commands.items():
            if key in self.stuck_switches:
                self.switch_positions.setdefault(key, "normal")
            else:
                self.switch_positions[key] = position
        self.crossings_active.update(outputs.track_model.crossing_commands)
        self.signal_aspects.update(outputs.track_model.signal_commands)

    # --- the Track Model's inputs --------------------------------------

    def set_occupancy(self, key: BlockKey, occupied: bool) -> None:
        """Put a train on, or take it off, one block."""
        self._require_block(key)
        self.occupancy_overrides[key] = occupied

    def clear_occupancy(self, keys: Sequence[BlockKey]) -> None:
        """Clear every one of these blocks, trains and all."""
        for key in keys:
            self.set_occupancy(key, False)

    def set_switch_stuck(self, key: BlockKey, stuck: bool) -> None:
        """Hold a switch machine where it is, or let it follow again."""
        if key not in self.switch_blocks:
            raise InvalidInputError(f"no switch on {key.label}")
        if stuck:
            self.stuck_switches.add(key)
        else:
            self.stuck_switches.discard(key)

    # --- the CTC Office's inputs ---------------------------------------

    def set_closed(self, key: BlockKey, closed: bool) -> None:
        """Close or reopen one block."""
        self._require_block(key)
        if closed:
            self.closed.add(key)
        else:
            self.closed.discard(key)

    def set_suggestion(
        self,
        key: BlockKey,
        speed_mps: float | None = None,
        authority_blocks: float | None = None,
    ) -> None:
        """Set one block's suggestion; either part may be left as it is."""
        self._require_block(key)
        current = self.suggestions.get(key) or Suggestion(0, 0)
        speed = (
            current.speed_mps if speed_mps is None
            else _whole(speed_mps, "suggested speed")
        )
        authority = (
            current.authority_blocks if authority_blocks is None
            else _whole(authority_blocks, "suggested authority")
        )
        self.suggestions[key] = Suggestion(speed, authority)

    def set_all_suggestions(
        self,
        keys: Sequence[BlockKey],
        speed_mps: float | None = None,
        authority_blocks: float | None = None,
    ) -> None:
        """Set the same suggestion on every one of these blocks."""
        # Validate once, before changing any block, so a bad value
        # leaves the whole territory as it was.
        if speed_mps is not None:
            _whole(speed_mps, "suggested speed")
        if authority_blocks is not None:
            _whole(authority_blocks, "suggested authority")
        for key in keys:
            self.set_suggestion(key, speed_mps, authority_blocks)

    def clear_suggestion(self, key: BlockKey) -> None:
        """Send nothing for one block."""
        self._require_block(key)
        self.suggestions[key] = None

    def set_maintenance(self, active: bool) -> None:
        """Turn maintenance mode on or off; ending it drops the commands."""
        self.maintenance = active
        if not active:
            self.switch_commands.clear()

    def set_switch_command(
        self, key: BlockKey, position: SwitchPosition | None
    ) -> None:
        """Command a switch, or with ``None`` withdraw the command."""
        if key not in self.switch_blocks:
            raise InvalidInputError(f"no switch on {key.label}")
        if position is None:
            self.switch_commands.pop(key, None)
        elif position in ("normal", "reverse"):
            self.switch_commands[key] = position
        else:
            raise InvalidInputError("a position is normal or reverse")

    def _require_block(self, key: BlockKey) -> None:
        if key not in self.suggestions:
            raise InvalidInputError(f"no such block: {key.label}")
