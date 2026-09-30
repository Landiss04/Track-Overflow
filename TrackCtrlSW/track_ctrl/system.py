"""Every line and controller in the network, plus the simulation tick.

This module stands in for the Track Model and the CTC. Until those
modules are integrated it moves a handful of trains along each line and
issues a suggested speed and authority for them, so the wayside has
live inputs to react to and the Program tab shows a program doing
something rather than a frozen snapshot.

Everything here is behind :class:`TrackControllerSystem`, so replacing
it with the real inter-module interface means changing one class.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from track_ctrl.controller import (
    ControllerInputs,
    ScanReport,
    TrackController,
    default_program_source,
)
from track_ctrl.layout import LineLayout, build_default_system

#: Suggested speed the stand-in CTC issues, in mph.
DEFAULT_SUGGESTED_SPEED_MPH = 35.0

#: Suggested authority the stand-in CTC issues, in blocks.
DEFAULT_SUGGESTED_AUTHORITY = 4


@dataclass
class Train:
    """A train the stand-in Track Model walks along a line."""

    train_id: str
    line_name: str
    block_index: int
    #: Ticks between moves, so trains advance at different rates.
    period: int = 2
    _ticks: int = field(default=0, repr=False)

    def advance(self, block_count: int) -> None:
        """Step the train forward, wrapping at the end of the line."""
        self._ticks += 1
        if self._ticks < self.period:
            return
        self._ticks = 0
        self.block_index = self.block_index % block_count + 1


class TrackControllerSystem:
    """The whole wayside network: lines, controllers and the clock."""

    def __init__(self) -> None:
        self.lines: tuple[LineLayout, ...] = build_default_system()
        self.controllers: dict[str, TrackController] = {}
        self.trains: list[Train] = []
        self.tick_count = 0

        for line in self.lines:
            by_id = {block.block_id: block for block in line.blocks}
            for config in line.controllers:
                blocks = tuple(
                    by_id[block_id] for block_id in config.block_ids
                )
                controller = TrackController(config, blocks)
                # A wayside ships with a working program; an unloaded
                # controller would sit at its restrictive fallback and
                # show the programmer nothing to read.
                controller.commit(
                    default_program_source(controller), controller.file_name
                )
                self.controllers[config.controller_id] = controller

        self._seed_trains()
        self.tick()

    def _seed_trains(self) -> None:
        """Place a few trains so every line has visible occupancy."""
        for line_position, line in enumerate(self.lines):
            count = 3 if line_position == 0 else 2
            spacing = len(line.blocks) // (count + 1)
            for train_position in range(count):
                self.trains.append(
                    Train(
                        train_id=f"T-{100 + line_position * 10 + train_position:03d}",
                        line_name=line.name,
                        block_index=spacing * (train_position + 1),
                        period=2 + train_position,
                    )
                )

    def line(self, name: str) -> LineLayout:
        """Return one line by name."""
        for candidate in self.lines:
            if candidate.name == name:
                return candidate
        raise KeyError(f"unknown line: {name}")

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

    def set_block_closed(self, block_id: str, closed: bool) -> None:
        """Close or reopen a block, as the CTC would."""
        for controller in self.controllers.values():
            if controller.config.owns(block_id):
                controller.inputs.closed[block_id] = closed

    def tick(self) -> dict[str, ScanReport]:
        """Advance the stand-in world and scan every controller."""
        self.tick_count += 1

        for line in self.lines:
            for train in self.trains:
                if train.line_name == line.name:
                    train.advance(len(line.blocks))

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
        inputs: ControllerInputs = controller.inputs
        inputs.trains = {
            block_id: train_id
            for block_id, train_id in placed.items()
            if controller.config.owns(block_id)
        }
        for block in controller.blocks:
            inputs.occupancy[block.block_id] = block.block_id in inputs.trains

        # The stand-in CTC suggests a constant speed and authority; the
        # wayside is what turns that into something safe for the blocks
        # actually in front of the train.
        inputs.suggested_speed_mph = DEFAULT_SUGGESTED_SPEED_MPH
        inputs.suggested_authority_blocks = DEFAULT_SUGGESTED_AUTHORITY
