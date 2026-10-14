"""The Track Controller (software) module, without Qt.

:class:`SwTrackController` is what the central harness steps. It holds
every wayside, takes one tick of boundary inputs, scans each wayside's
PLC program and returns the boundary outputs. Nothing here draws, ticks
a clock of its own or moves a pretend train: the harness owns the clock
and the world (D006), and the UI and the test UI sit on top of this.

It adapts between two vocabularies. The boundary speaks in
:class:`~track_ctrl.interface.BlockKey` and Literal strings. Each
:class:`~track_ctrl.controller.TrackController` underneath speaks in bare
block numbers and booleans, because the PLC program does. The line is
what tells two waysides' block ``12`` apart, so it is added on the way
out and stripped on the way in.

There is no maintenance-mode input: the CTC Office sends none. A CTC switch
command in effect on a switch this module governs is what maintenance mode
looks like from here, and drives ``MAINT`` and the UI's maintenance state.

What the Track Model reports back is used two ways. Where a switch's
actual position differs from the one commanded last scan, the switch is
mid-throw and the vital layer holds that block's speed at zero. Every
read-back (switch, crossing, signal) is also passed on to the CTC Office
in each wayside's report. Failures are not an input at all; they reach
this module as occupancy.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

from track_ctrl.controller import TrackController, default_program_source
from track_ctrl.errors import (
    InvalidInputError,
    InvalidProgramError,
    UnknownIdError,
)
from track_ctrl.interface import (
    SIGNAL_ASPECTS,
    SWITCH_POSITIONS,
    BlockKey,
    BlockReport,
    CtcReport,
    Override,
    ProgramInfo,
    SignalAspect,
    Suggestion,
    SwitchPosition,
    SwitchState,
    TrackCircuitCommand,
    TrackControllerInputs,
    TrackControllerOutputs,
    TrackControllerSnapshot,
    TrackModelInputs,
    TrackModelOutputs,
    WaysideSnapshot,
)
from track_ctrl.layout import LineLayout

_SECONDS_PER_DAY = 86_400


def clock_text(seconds: float) -> str:
    """Render simulated seconds since midnight as ``HH:MM:SS``."""
    whole = int(seconds) % _SECONDS_PER_DAY
    return f"{whole // 3600:02d}:{whole % 3600 // 60:02d}:{whole % 60:02d}"


def _aspect_to_wire(aspect: str) -> SignalAspect:
    """Map the vital layer's ``SUPER GREEN`` to the boundary's literal."""
    value = aspect.lower().replace(" ", "_")
    if value not in SIGNAL_ASPECTS:
        raise InvalidInputError(f"unknown signal aspect: {aspect}")
    return value


def _position(reverse: bool) -> SwitchPosition:
    return "reverse" if reverse else "normal"


def _whole_count(value: object, what: str) -> int:
    """Return ``value`` as a non-negative int, else reject it."""
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
    ):
        raise InvalidInputError(f"{what} must be a whole number, 0 or more")
    return value


@dataclass
class _Wayside:
    """One controller with the line it belongs to."""

    controller: TrackController
    line: str

    def key(self, block_id: str) -> BlockKey:
        return BlockKey(self.line, block_id)


class SwTrackController:
    """Every wayside the module governs, stepped from outside."""

    def __init__(self) -> None:
        self._lines: list[LineLayout] = []
        self._waysides: dict[str, _Wayside] = {}
        self._owner: dict[BlockKey, str] = {}
        self._readback = TrackModelInputs()
        self._maintenance = False
        self._time_s: float | None = None
        self._ticks = 0
        self._reports: dict[str, CtcReport] = {}

    # --- loading track -------------------------------------------------

    def load_track(self, line: LineLayout) -> list[str]:
        """Install a line, replacing any line of the same name.

        Returns the IDs of the waysides that were replaced. Their
        programs go with them: the territories they governed no longer
        exist. Every other line keeps its waysides and programs.
        """
        removed = [
            wayside_id for wayside_id, wayside in self._waysides.items()
            if wayside.line == line.key
        ]
        for wayside_id in removed:
            del self._waysides[wayside_id]
            self._reports.pop(wayside_id, None)
        self._owner = {
            key: owner for key, owner in self._owner.items()
            if owner not in removed
        }
        for position, each in enumerate(self._lines):
            if each.key == line.key:
                self._lines[position] = line
                break
        else:
            self._lines.append(line)
        self._install(line)
        # Put the waysides back in line order, so every list built from
        # them keeps the order the lines have.
        ordered: dict[str, _Wayside] = {}
        for each in self._lines:
            for wayside_id, wayside in self._waysides.items():
                if wayside.line == each.key:
                    ordered[wayside_id] = wayside
        self._waysides = ordered
        return removed

    def _install(self, line: LineLayout) -> None:
        """Create a controller, with a working program, for each wayside."""
        by_id = {block.block_id: block for block in line.blocks}
        for config in line.controllers:
            blocks = tuple(by_id[each] for each in config.block_ids)
            controller = TrackController(config, blocks)
            controller.time_text = (
                "" if self._time_s is None else clock_text(self._time_s)
            )
            # No program yet: startup is the programmer's. Until a
            # program is committed the wayside holds its fail-safe
            # outputs, and so does the whole module (see ``ready``).
            controller.scan()
            wayside = _Wayside(controller, line.key)
            self._waysides[config.controller_id] = wayside
            for block_id in config.block_ids:
                self._owner[wayside.key(block_id)] = config.controller_id

    def reset(self) -> None:
        """Return every wayside to its state just after loading."""
        self._readback = TrackModelInputs()
        self._maintenance = False
        self._time_s = None
        self._ticks = 0
        self._waysides = {}
        self._owner = {}
        self._reports = {}
        for line in self._lines:
            self._install(line)

    # --- startup -----------------------------------------------------------

    def not_ready_reasons(self) -> tuple[str, ...]:
        """What startup still needs, or an empty tuple when it is done."""
        if not self._waysides:
            return ("no track is loaded",)
        return tuple(
            f"{wayside_id} has no PLC program"
            for wayside_id, wayside in self._waysides.items()
            if wayside.controller.program is None
        )

    @property
    def ready(self) -> bool:
        """Whether a line is loaded and every wayside has a program.

        The module is vital, so it stalls until this holds: while it does
        not, no wayside runs its program and all of them drive their
        fail-safe outputs.
        """
        return not self.not_ready_reasons()

    def load_starter_programs(self) -> list[str]:
        """Commit a generated starter program to every wayside without one.

        A convenience for the demo and the tests, in place of committing
        each wayside by hand. Returns the IDs that were loaded.
        """
        loaded: list[str] = []
        for wayside_id, wayside in self._waysides.items():
            controller = wayside.controller
            if controller.program is None:
                controller.commit(
                    default_program_source(controller),
                    controller.file_name,
                )
                loaded.append(wayside_id)
        return loaded

    @property
    def wayside_ids(self) -> tuple[str, ...]:
        """The IDs of every wayside, in the order they were loaded."""
        return tuple(self._waysides)

    # --- lookup, for the UI ------------------------------------------------

    @property
    def lines(self) -> tuple[LineLayout, ...]:
        """Every loaded line, in the order they were loaded."""
        return tuple(self._lines)

    @property
    def controllers(self) -> dict[str, TrackController]:
        """Every wayside's controller by ID, in line order."""
        return {
            wayside_id: wayside.controller
            for wayside_id, wayside in self._waysides.items()
        }

    @property
    def maintenance(self) -> bool:
        """Whether a CTC switch command is in effect: maintenance mode."""
        return self._maintenance

    @property
    def time_s(self) -> float | None:
        """Simulation time of the last tick; None before the first."""
        return self._time_s

    def line(self, name: str) -> LineLayout:
        """Return one line by its display name, ``Green Line``."""
        for candidate in self._lines:
            if candidate.name == name:
                return candidate
        raise UnknownIdError(f"unknown line: {name}")

    def controller(self, controller_id: str) -> TrackController:
        """Return one controller by ID."""
        return self._wayside(controller_id).controller

    def controllers_for(self, line_name: str) -> list[TrackController]:
        """Return the controllers on one line, in configuration order."""
        return [
            wayside.controller for wayside in self._waysides.values()
            if wayside.controller.config.line_name == line_name
        ]

    def line_key(self, controller_id: str) -> str:
        """The boundary's name for a wayside's line, ``Green``."""
        return self._wayside(controller_id).line

    # --- the tick --------------------------------------------------------

    def step(
        self, dt: float, inputs: TrackControllerInputs
    ) -> TrackControllerOutputs:
        """Scan every wayside once and return what it drives."""
        self._validate(dt, inputs)
        ctc = inputs.ctc
        readback = inputs.track_model
        # The CTC Office sends no mode flag. It sends switch commands only
        # in maintenance mode, so a command in effect on a switch this
        # module governs is what maintenance mode looks like from here.
        switch_keys = {
            wayside.key(switch.block_id)
            for wayside in self._waysides.values()
            for switch in wayside.controller.config.switches
        }
        self._maintenance = any(
            key in switch_keys for key in ctc.switch_commands
        )

        reasons = self.not_ready_reasons()
        for wayside in self._waysides.values():
            self._apply(wayside, inputs)
            if reasons:
                wayside.controller.hold(
                    f"the module is not ready: {reasons[0]}"
                )
            else:
                wayside.controller.scan()

        self._readback = readback
        self._time_s = inputs.time_s
        self._ticks += 1
        return self._outputs(inputs.time_s)

    def _validate(self, dt: float, inputs: TrackControllerInputs) -> None:
        """Reject a bad tick before any state changes."""
        if (
            isinstance(dt, bool)
            or not isinstance(dt, (int, float))
            or not math.isfinite(dt)
            or dt <= 0
        ):
            raise InvalidInputError("dt must be finite and positive")
        time_s = inputs.time_s
        if (
            isinstance(time_s, bool)
            or not isinstance(time_s, (int, float))
            or not math.isfinite(time_s)
            or time_s < 0
        ):
            raise InvalidInputError("time_s must be finite and 0 or more")
        for key, suggestion in inputs.ctc.suggestions.items():
            _whole_count(suggestion.speed_mps, f"speed for {key.label}")
            _whole_count(
                suggestion.authority_blocks, f"authority for {key.label}"
            )
        for key, position in inputs.ctc.switch_commands.items():
            if position not in SWITCH_POSITIONS:
                raise InvalidInputError(
                    f"switch command for {key.label} is not a position"
                )
        for key, position in inputs.track_model.switch_positions.items():
            if position not in SWITCH_POSITIONS:
                raise InvalidInputError(
                    f"switch position for {key.label} is not a position"
                )
        for key, aspect in inputs.track_model.signal_aspects.items():
            if aspect not in SIGNAL_ASPECTS:
                raise InvalidInputError(
                    f"signal aspect for {key.label} is not an aspect"
                )

    def _apply(
        self, wayside: _Wayside, inputs: TrackControllerInputs
    ) -> None:
        """Write one tick's inputs onto a controller's input card."""
        controller = wayside.controller
        ctc = inputs.ctc
        readback = inputs.track_model
        controller.time_text = clock_text(inputs.time_s)

        if controller.maintenance != self._maintenance:
            controller.set_maintenance(self._maintenance)

        for block in controller.blocks:
            key = wayside.key(block.block_id)
            controller.set_occupancy(
                block.block_id, key in readback.occupied_blocks
            )
            controller.set_closed(block.block_id, key in ctc.closed_blocks)
            suggestion = ctc.suggestions.get(key)
            if suggestion is None:
                controller.clear_suggestion(block.block_id)
            else:
                controller.set_suggestion(
                    block.block_id,
                    suggestion.speed_mps,
                    suggestion.authority_blocks,
                )

        for switch in controller.config.switches:
            key = wayside.key(switch.block_id)
            command = ctc.switch_commands.get(key)
            controller.set_ctc_switch_command(
                switch.switch_id,
                None if command is None else command == "reverse",
            )
            # A switch whose machine is not where the last scan put it
            # is mid-throw. No report means nothing to compare.
            actual = readback.switch_positions.get(key)
            commanded = controller.outputs.switches.get(
                switch.switch_id, False
            )
            controller.set_switch_moving(
                switch.switch_id,
                actual is not None and (actual == "reverse") != commanded,
            )

    # --- outputs -----------------------------------------------------------

    def _outputs(self, time_s: float) -> TrackControllerOutputs:
        circuits: dict[BlockKey, TrackCircuitCommand] = {}
        switches: dict[BlockKey, SwitchPosition] = {}
        crossings: dict[BlockKey, bool] = {}
        signals: dict[BlockKey, SignalAspect] = {}
        reports: list[CtcReport] = []

        for wayside_id, wayside in self._waysides.items():
            controller = wayside.controller
            driven = controller.outputs
            config = controller.config
            for block_id, circuit in driven.track_circuits.items():
                circuits[wayside.key(block_id)] = TrackCircuitCommand(
                    circuit.speed_mps, circuit.authority_blocks
                )
            for switch in config.switches:
                switches[wayside.key(switch.block_id)] = _position(
                    driven.switches.get(switch.switch_id, False)
                )
            for crossing in config.crossings:
                crossings[wayside.key(crossing.block_id)] = (
                    driven.crossings.get(crossing.crossing_id, False)
                )
            for signal in config.signals:
                signals[wayside.key(signal.block_id)] = _aspect_to_wire(
                    driven.aspects.get(signal.signal_id, "RED")
                )
            report = self._report(wayside_id, wayside, time_s)
            self._reports[wayside_id] = report
            reports.append(report)

        return TrackControllerOutputs(
            ready=self.ready,
            track_model=TrackModelOutputs(
                track_circuits=circuits,
                switch_commands=switches,
                crossing_commands=crossings,
                signal_commands=signals,
            ),
            ctc_reports=tuple(reports),
        )

    def _report(
        self, wayside_id: str, wayside: _Wayside, time_s: float
    ) -> CtcReport:
        """Build the report one wayside sends the CTC Office."""
        controller = wayside.controller
        readback = self._readback
        switch_blocks = {
            switch.block_id for switch in controller.config.switches
        }
        crossing_blocks = {
            crossing.block_id for crossing in controller.config.crossings
        }
        signal_blocks = {
            signal.block_id for signal in controller.config.signals
        }
        blocks: dict[BlockKey, BlockReport] = {}
        for block in controller.blocks:
            key = wayside.key(block.block_id)
            blocks[key] = BlockReport(
                occupied=key in readback.occupied_blocks,
                switch_position=(
                    readback.switch_positions.get(key)
                    if block.block_id in switch_blocks else None
                ),
                crossing_active=(
                    readback.crossings_active.get(key)
                    if block.block_id in crossing_blocks else None
                ),
                signal_aspect=(
                    readback.signal_aspects.get(key)
                    if block.block_id in signal_blocks else None
                ),
            )
        return CtcReport(wayside_id, time_s, blocks)

    # --- programs ------------------------------------------------------------

    def load_program(
        self, wayside_id: str, source: str, file_name: str
    ) -> ProgramInfo:
        """Commit a PLC program to one wayside."""
        controller = self._wayside(wayside_id).controller
        try:
            controller.commit(source, file_name)
        except ValueError as error:
            raise InvalidProgramError(str(error)) from error
        return self._program_info(controller) or ProgramInfo(
            file_name, controller.iteration, "", 0, 0
        )

    def _wayside(self, wayside_id: str) -> _Wayside:
        try:
            return self._waysides[wayside_id]
        except KeyError:
            raise UnknownIdError(f"unknown wayside: {wayside_id}") from None

    @staticmethod
    def _program_info(controller: TrackController) -> ProgramInfo | None:
        program = controller.program
        if program is None or not controller.history:
            return None
        newest = controller.history[0]
        return ProgramInfo(
            file_name=controller.file_name,
            iteration=controller.iteration,
            checksum=hashlib.sha256(
                newest.source.encode("utf-8")
            ).hexdigest()[:12],
            boolean_count=program.boolean_count,
            statement_count=newest.line_count,
        )

    # --- snapshot ------------------------------------------------------------

    def snapshot(self) -> TrackControllerSnapshot:
        """Current state for display. No side effects."""
        readback = self._readback
        waysides: list[WaysideSnapshot] = []
        for wayside_id, wayside in self._waysides.items():
            controller = wayside.controller
            config = controller.config
            driven = controller.outputs
            keys = tuple(wayside.key(each) for each in config.block_ids)
            switches = tuple(
                SwitchState(
                    switch=wayside.key(switch.block_id),
                    commanded=_position(
                        driven.switches.get(switch.switch_id, False)
                    ),
                    reported=readback.switch_positions.get(
                        wayside.key(switch.block_id)
                    ),
                )
                for switch in config.switches
            )
            signal_keys = [
                wayside.key(signal.block_id) for signal in config.signals
            ]
            crossing_keys = [
                wayside.key(crossing.block_id)
                for crossing in config.crossings
            ]
            owned = set(keys)
            waysides.append(
                WaysideSnapshot(
                    wayside_id=wayside_id,
                    line=wayside.line,
                    blocks=keys,
                    program=self._program_info(controller),
                    switches=switches,
                    signal_commands={
                        wayside.key(signal.block_id): _aspect_to_wire(
                            driven.aspects.get(signal.signal_id, "RED")
                        )
                        for signal in config.signals
                    },
                    signal_reports={
                        key: readback.signal_aspects[key]
                        for key in signal_keys
                        if key in readback.signal_aspects
                    },
                    crossing_commands={
                        wayside.key(crossing.block_id): driven.crossings.get(
                            crossing.crossing_id, False
                        )
                        for crossing in config.crossings
                    },
                    crossing_reports={
                        key: readback.crossings_active[key]
                        for key in crossing_keys
                        if key in readback.crossings_active
                    },
                    track_circuits={
                        wayside.key(block_id): TrackCircuitCommand(
                            circuit.speed_mps, circuit.authority_blocks
                        )
                        for block_id, circuit in driven.track_circuits.items()
                    },
                    occupied_blocks=frozenset(
                        key for key in readback.occupied_blocks
                        if key in owned
                    ),
                    closed_blocks=frozenset(
                        wayside.key(block.block_id)
                        for block in controller.blocks
                        if controller.inputs.closed.get(block.block_id)
                    ),
                    suggestions={
                        wayside.key(block_id): Suggestion(
                            suggestion.speed_mps,
                            suggestion.authority_blocks,
                        )
                        for block_id, suggestion
                        in controller.inputs.suggestions.items()
                    },
                    overrides=tuple(
                        Override(each.rule, each.signal, each.message)
                        for each in driven.overrides
                    ),
                    report=self._reports.get(wayside_id),
                )
            )
        return TrackControllerSnapshot(
            waysides=tuple(waysides),
            maintenance_mode=self._maintenance,
            time_s=self._time_s,
            ticks=self._ticks,
            ready=self.ready,
            not_ready=self.not_ready_reasons(),
        )
