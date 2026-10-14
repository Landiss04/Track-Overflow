"""Every line and controller in the network, plus the simulation tick.

This module stands in for the Track Model and the CTC. Until those
modules are integrated it moves a handful of trains along each line and
issues a suggested speed and authority for every block, so the wayside
has live inputs to react to and the Program tab shows a program doing
something rather than a frozen snapshot.

The blocks are fixed by the track layout; the trains on them are not.
The stand-in therefore keys everything by block, as the real modules
will, and the trains exist only to make occupancy change.

Everything here is behind :class:`TrackControllerSystem`, so replacing
it with the real inter-module interface means changing one class.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from track_ctrl.controller import (
    ScanReport,
    TrackController,
    default_program_source,
)
from track_ctrl.layout import LineLayout, build_default_system
from track_ctrl.vital import Suggestion

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


@dataclass
class Train:
    """A train the stand-in Track Model walks along a line."""

    train_id: str
    line_name: str
    block_index: int
    #: Simulated seconds spent in each block, so trains advance at
    #: different rates and 10x runs them ten times as fast.
    seconds_per_block: float = 2.0
    _elapsed_s: float = field(default=0.0, repr=False)

    def advance(self, block_count: int, dt_s: float) -> None:
        """Move on by ``dt_s`` simulated seconds, wrapping at the end."""
        self._elapsed_s += dt_s
        while self._elapsed_s >= self.seconds_per_block:
            self._elapsed_s -= self.seconds_per_block
            self.block_index = self.block_index % block_count + 1


class TrackControllerSystem:
    """The whole wayside network: lines, controllers and the clock."""

    def __init__(
        self,
        time_text: str = "",
        layouts: tuple[LineLayout, ...] | None = None,
    ) -> None:
        """Build every line and controller.

        ``time_text`` is the shared clock's time of day at start, so the
        starter programs are committed in simulated time. ``layouts``
        replaces the default Green and Red layouts, for tests.
        """
        #: Simulated time of day, handed to every controller each tick.
        self.time_text = time_text
        self.lines: tuple[LineLayout, ...] = (
            layouts if layouts is not None else build_default_system()
        )
        self.controllers: dict[str, TrackController] = {}
        self.trains: list[Train] = []
        self.tick_count = 0
        #: A test UI owns CTC suggestions and explicitly edited occupancy.
        #: Stand-in trains continue advancing on the shared clock.
        self._external_control = False
        self._occupancy_overrides: dict[tuple[str, str], bool] = {}
        #: The CTC Office's maintenance mode, system-wide.
        self.maintenance = False
        self._next_train_number = 100

        for line in self.lines:
            self._install_line(line)
        self.tick(0.0)

    @property
    def external_control(self) -> bool:
        return self._external_control

    @external_control.setter
    def external_control(self, active: bool) -> None:
        self._external_control = active
        if not active:
            self._occupancy_overrides.clear()

    def set_occupancy(
        self, controller: TrackController, block_id: str, occupied: bool
    ) -> None:
        """Apply a test input, preserving only this block while connected."""
        controller.set_occupancy(block_id, occupied)
        if self.external_control:
            self._occupancy_overrides[(controller.config.controller_id,
                                       block_id)] = occupied

    # --- building ------------------------------------------------------

    def _install_line(self, line: LineLayout) -> None:
        """Create a controller for each wayside of ``line``."""
        by_id = {block.block_id: block for block in line.blocks}
        for config in line.controllers:
            blocks = tuple(by_id[block_id] for block_id in config.block_ids)
            controller = TrackController(config, blocks)
            controller.time_text = self.time_text
            controller.set_maintenance(self.maintenance)
            # A wayside ships with a working program; an unloaded
            # controller would sit at its restrictive fallback and
            # show the programmer nothing to read.
            controller.commit(
                default_program_source(controller), controller.file_name
            )
            self.controllers[config.controller_id] = controller
        self._seed_trains(line)

    def _seed_trains(self, line: LineLayout) -> None:
        """Place a few trains so the line has visible occupancy."""
        count = max(1, min(_MAX_TRAINS_PER_LINE,
                           len(line.blocks) // _BLOCKS_PER_TRAIN))
        spacing = max(1, len(line.blocks) // (count + 1))
        for position in range(count):
            self.trains.append(
                Train(
                    train_id=f"T-{self._next_train_number}",
                    line_name=line.name,
                    block_index=spacing * (position + 1),
                    seconds_per_block=2.0 + position,
                )
            )
            self._next_train_number += 1

    def load_line(self, line: LineLayout) -> list[str]:
        """Install a line, replacing any line with the same name.

        Returns the ids of the controllers that were removed. Their
        programs and history go with them: the territories they governed
        no longer exist, so nothing carries over.
        """
        removed: list[str] = []
        existing = [
            index for index, current in enumerate(self.lines)
            if current.name == line.name
        ]
        if existing:
            removed = [
                controller_id
                for controller_id, controller in self.controllers.items()
                if controller.config.line_name == line.name
            ]
            for controller_id in removed:
                del self.controllers[controller_id]
            self._occupancy_overrides = {
                key: value for key, value in self._occupancy_overrides.items()
                if key[0] not in removed
            }
            self.trains = [
                train for train in self.trains
                if train.line_name != line.name
            ]
            lines = list(self.lines)
            lines[existing[0]] = line
            self.lines = tuple(lines)
        else:
            self.lines = self.lines + (line,)

        self._install_line(line)
        # Controllers come back after the ones already there. Put them in
        # line order again, so every list built from this dict (the
        # controller picker, the test UI's snapshot) keeps the order the
        # lines have.
        ordered: dict[str, TrackController] = {}
        for each in self.lines:
            for controller in self.controllers_for(each.name):
                ordered[controller.config.controller_id] = controller
        self.controllers = ordered
        for controller in self.controllers_for(line.name):
            controller.scan()
        return removed

    # --- lookup ----------------------------------------------------------

    def line(self, name: str) -> LineLayout:
        """Return one line by name."""
        for candidate in self.lines:
            if candidate.name == name:
                return candidate
        raise KeyError(f"unknown line: {name}")

    def controller(self, controller_id: str) -> TrackController:
        """Return one controller by id."""
        try:
            return self.controllers[controller_id]
        except KeyError:
            raise KeyError(f"unknown controller: {controller_id}") from None

    def controllers_for(self, line_name: str) -> list[TrackController]:
        """Return the controllers on one line, in configuration order."""
        return [
            controller
            for controller in self.controllers.values()
            if controller.config.line_name == line_name
        ]

    def occupancy_for(self, line: LineLayout) -> dict[str, str]:
        """Return block id -> train id for every train on one line."""
        placed: dict[str, str] = {}
        for train in self.trains:
            if train.line_name != line.name:
                continue
            index = min(train.block_index, len(line.blocks)) - 1
            placed[line.blocks[index].block_id] = train.train_id
        return placed

    # --- the CTC's maintenance mode ----------------------------------------

    def set_maintenance(self, active: bool) -> None:
        """Apply the CTC Office's maintenance mode to every controller."""
        self.maintenance = active
        for controller in self.controllers.values():
            controller.set_maintenance(active)
            controller.scan()

    # --- the tick ----------------------------------------------------------

    def tick(self, dt_s: float) -> dict[str, ScanReport]:
        """Advance the stand-in world by ``dt_s`` and scan every controller.

        Called once per tick of the shared simulation clock; ``dt_s`` is
        the clock's tick length, never wall time (style guide 8).
        """
        self.tick_count += 1
        for controller in self.controllers.values():
            controller.time_text = self.time_text

        for line in self.lines:
            for train in self.trains:
                if train.line_name == line.name:
                    train.advance(len(line.blocks), dt_s)

        reports: dict[str, ScanReport] = {}
        for line in self.lines:
            placed = self.occupancy_for(line)
            for controller in self.controllers_for(line.name):
                self._refresh_inputs(controller, placed)
                reports[controller.config.controller_id] = controller.scan()
        return reports

    def _refresh_inputs(
        self, controller: TrackController, placed: dict[str, str]
    ) -> None:
        """Write this tick's Track Model and CTC values onto the card."""
        inputs = controller.inputs
        inputs.trains = {
            block_id: train_id
            for block_id, train_id in placed.items()
            if controller.config.owns(block_id)
        }
        for block in controller.blocks:
            inputs.occupancy[block.block_id] = block.block_id in inputs.trains
            key = (controller.config.controller_id, block.block_id)
            if self.external_control and key in self._occupancy_overrides:
                controller.set_occupancy(block.block_id,
                                         self._occupancy_overrides[key])

        if self.external_control:
            return

        # The stand-in CTC suggests the same speed and authority for
        # every block. The wayside is what turns that into something
        # safe for the blocks actually in front of each train.
        suggestion = Suggestion(
            DEFAULT_SUGGESTED_SPEED_MPS, DEFAULT_SUGGESTED_AUTHORITY
        )
        for block in controller.blocks:
            inputs.suggestions[block.block_id] = suggestion
