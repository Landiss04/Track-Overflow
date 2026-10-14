"""A module and a stand-in world wired together, for the tests.

``Rig`` does in a few lines what the test UI does every tick: build the
boundary inputs from the world, step the module, and give the outputs
back to the world as the Track Model's read-back. It needs no Qt.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from track_ctrl.controller import TrackController  # noqa: E402
from track_ctrl.interface import (  # noqa: E402
    BlockKey,
    TrackControllerInputs,
    TrackControllerOutputs,
)
from track_ctrl.layout import build_default_system  # noqa: E402
from track_ctrl.module import SwTrackController  # noqa: E402
from track_ctrl.stimulus import _describe  # noqa: E402
from track_ctrl_test.world import StandInWorld  # noqa: E402

#: The first Green wayside: blocks 1 to 25, switch 12, crossing 19.
CONTROLLER = "GTC-01"
LINE = "Green"
DT = 0.1


def topology(module: SwTrackController) -> list[dict[str, Any]]:
    """What the test UI learns about the track from a snapshot."""
    return [
        _describe(controller, module.line_key(controller_id))
        for controller_id, controller in module.controllers.items()
    ]


def default_module(programs: bool = True) -> SwTrackController:
    """A module with the default Green and Red lines loaded.

    Startup is not done until every wayside has a program, so by default
    the generated starter programs are committed too. Pass
    ``programs=False`` for a module that is still starting up.
    """
    module = SwTrackController()
    for line in build_default_system():
        module.load_track(line)
    if programs:
        module.load_starter_programs()
    return module


class Rig:
    """A module, a world around it, and a clock that only moves on tick."""

    def __init__(
        self,
        module: SwTrackController | None = None,
        trains: bool = False,
        stepper: Callable[
            [float, TrackControllerInputs], TrackControllerOutputs
        ] | None = None,
    ) -> None:
        """Wire a world to ``module``, or to a fresh default one.

        ``stepper`` is what a tick calls to step it; the Track Controller
        UI's ``state.step`` goes here to drive the UI instead.
        """
        self.module = module if module is not None else default_module()
        self._step = stepper if stepper is not None else self.module.step
        self.world = StandInWorld()
        self.world.load_topology(topology(self.module))
        if not trains:
            self.world.trains.clear()
        self.time_s = 0.0

    @property
    def controller(self) -> TrackController:
        return self.module.controller(CONTROLLER)

    @staticmethod
    def key(block_id: str, line: str = LINE) -> BlockKey:
        return BlockKey(line, block_id)

    def tick(self, dt: float = DT) -> TrackControllerOutputs:
        """One clock tick: move the world, step the module, read back."""
        self.time_s += dt
        self.world.advance(dt)
        outputs = self._step(dt, self.world.build_inputs(self.time_s))
        self.world.apply_outputs(outputs)
        return outputs

    def other_switch(self) -> BlockKey:
        """A Green switch that is not the first wayside's switch 12."""
        return next(
            key for key in self.world.switch_blocks
            if key.line == LINE and key.block_id != "12"
        )

    def dispatcher_in_maintenance(self, active: bool = True) -> None:
        """Put the stand-in CTC in, or take it out of, maintenance mode.

        The real CTC sends no mode flag: only switch commands, and only in
        maintenance. So the mode shows up at the controller only as a
        command in effect, and this commands a switch other than 12 to
        keep the first wayside's own switch free for the test.
        """
        self.world.set_maintenance(active)
        if active:
            self.world.set_switch_command(self.other_switch(), "normal")

    def settle(self, ticks: int = 3) -> None:
        """Tick enough for a command to reach the Track Model and back."""
        for _ in range(ticks):
            self.tick()
