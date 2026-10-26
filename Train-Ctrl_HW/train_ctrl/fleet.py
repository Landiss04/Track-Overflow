"""One controller per running train, held by train ID. No Qt."""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping

from .constants import BENCH_ECHO_TICKS, TICK_S
from .control import ControllerCore
from .errors import (DuplicateTrainError, InvalidInputError,
                     TrainControllerError, UnknownTrainError)
from .inputs import EVERY_TICK, read_inputs
from .state import TrainModelCommands


class TrainControllerFleet:
    """One controller per running train, held by train ID.

    The spawner: whoever owns dispatch (the central harness once
    integrated) adds a train's controller when it enters service,
    removes it when it leaves, and steps them all once per tick. It
    mirrors the Train Model's TrainModelFleet on development, so the
    harness drives both the same way. No Qt: the console is only one
    of its users. Train IDs are opaque strings (identifiers.md).
    """

    def __init__(self, echo_ticks: int = BENCH_ECHO_TICKS) -> None:
        """Start with no trains.

        ``echo_ticks`` is passed to every train's ControllerCore: the
        ticks between a command and its report, BENCH_ECHO_TICKS for
        the bench and ECHO_TICKS when the central harness steps the
        fleet (OPEN_ISSUES.md #42).
        """
        # Insertion order is the roster order.
        self._cores: dict[str, ControllerCore] = {}
        self._echo_ticks = echo_ticks

    def add(self, train_id: str, line: str = "") -> ControllerCore:
        """Put a train's controller in service and return it."""
        if train_id in self._cores:
            raise DuplicateTrainError(f"train {train_id!r} already exists")
        core = ControllerCore(self._echo_ticks)
        core.state.train_id = train_id
        core.state.line = line
        self._cores[train_id] = core
        return core

    def remove(self, train_id: str) -> None:
        """Take a train's controller out of service."""
        self.get(train_id)
        del self._cores[train_id]

    def get(self, train_id: str) -> ControllerCore:
        """Return one train's controller."""
        try:
            return self._cores[train_id]
        except KeyError:
            raise UnknownTrainError(f"no train {train_id!r}") from None

    def ids(self) -> list[str]:
        """Every train's ID, in the order the trains were added."""
        return list(self._cores)

    def __contains__(self, train_id: object) -> bool:
        return train_id in self._cores

    def __len__(self) -> int:
        return len(self._cores)

    def __iter__(self) -> Iterator[ControllerCore]:
        return iter(list(self._cores.values()))

    def step_all(
        self, dt: float, inputs_by_id: Mapping[str, dict], time_s: float,
    ) -> dict[str, TrainModelCommands]:
        """Step every train's controller one tick, or none of them.

        ``inputs_by_id`` holds each train's signals in SI (the keys
        read_inputs() takes), exactly one entry per train. Every
        train's set is read before any train steps, so a set one train
        would refuse leaves the whole fleet unchanged. The physics is
        the Train Model's, or the bench simulation's. Returns each
        train's commands to its Train Model.

        ``dt`` must be TICK_S: the step is fixed at 0.1 s (truth D006 /
        D017) and faster simulation means more ticks, never longer
        ones. It is still passed, as TrainModelFleet takes it.

        ``time_s`` is the system time this tick, in seconds since
        midnight of the first simulated day, as utils/system_clock.py
        gives it: the harness clock, or the bench's own
        (REQUIREMENTS.md M11).
        """
        if dt != TICK_S:
            raise InvalidInputError(
                f"dt must be the fixed {TICK_S} s step, not {dt!r}")
        if (isinstance(time_s, bool) or not isinstance(time_s, (int, float))
                or not math.isfinite(time_s) or time_s < 0):
            raise InvalidInputError(
                f"time_s must be a time of at least 0 s, not {time_s!r}")
        unknown = sorted(set(inputs_by_id) - set(self._cores))
        if unknown:
            raise UnknownTrainError(f"inputs for unknown trains: {unknown}")
        missing = [i for i in self._cores if i not in inputs_by_id]
        if missing:
            raise TrainControllerError(f"no inputs for trains: {missing}")
        for train_id, values in inputs_by_id.items():
            short = [key for key in EVERY_TICK if key not in values]
            if short:
                raise InvalidInputError(
                    f"{train_id} is missing {short} this tick")
        staged = {train_id: read_inputs(inputs_by_id[train_id])
                  for train_id in self._cores}
        commands = {}
        for train_id, core in self._cores.items():
            core.state.time_s = float(time_s)
            core.apply_staged(staged[train_id])
            core.step()
            commands[train_id] = core.commands()
        return commands
