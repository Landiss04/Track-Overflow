"""One wayside track controller: I/O decode, scan cycle, commit history.

The controller is the bridge between typed module signals and the
boolean-only PLC program. Suggested speed arrives from the CTC as a
float and suggested authority as a block count; the input card encodes
both into bit vectors, the program reads and writes bits, and the
output card decodes the result back into typed values. That encode /
decode pair is the "decoded by OS" boundary on the architecture
diagram, and it is the only place in the module where a number becomes
a set of bits.

Both conversions round *down*. Truncating a speed or an authority is
always the safe direction, so a rounding error can only ever stop a
train short.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from track_ctrl import vital
from track_ctrl.layout import Block, ControllerConfig
from track_ctrl.plc import Diagnostic, Program, compile_program, has_errors
from track_ctrl.vital import ControllerOutputs

#: Width of the speed and authority bit vectors on the I/O cards.
SPEED_BITS = 4
AUTHORITY_BITS = 4

#: One step of the speed code, in mph. Four bits therefore span
#: 0..75 mph in 5 mph steps, which covers every posted limit.
SPEED_STEP_MPH = 5.0

#: How many committed programs stay readable in the history pane.
HISTORY_DEPTH = 5

#: Train id shown on a block whose occupancy was set from outside the
#: module rather than by a train the stand-in world is moving.
EXTERNAL_TRAIN_ID = "TEST"


def _non_negative(value: float, what: str) -> float:
    """Return ``value`` as a float, rejecting NaN, infinity and negatives."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{what} must be a number") from None
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{what} must be zero or more")
    return number


def encode_speed_mph(speed_mph: float) -> dict[str, bool]:
    """Encode a speed onto the ``SUG_SPEED_n`` input bits.

    Rounds down to the step below, so the program is never handed a
    higher speed than the CTC suggested.
    """
    steps = int(max(0.0, speed_mph) // SPEED_STEP_MPH)
    steps = min(steps, 2 ** SPEED_BITS - 1)
    return {
        f"SUG_SPEED_{bit}": bool(steps >> bit & 1) for bit in range(SPEED_BITS)
    }


def decode_speed_mph(values: Mapping[str, bool], prefix: str) -> float:
    """Decode a speed from ``<prefix>_n`` output bits."""
    steps = sum(
        (1 << bit)
        for bit in range(SPEED_BITS)
        if values.get(f"{prefix}_{bit}", False)
    )
    return steps * SPEED_STEP_MPH


def encode_authority_blocks(blocks: int) -> dict[str, bool]:
    """Encode an authority, in blocks, onto the ``SUG_AUTH_n`` bits."""
    count = min(max(0, blocks), 2 ** AUTHORITY_BITS - 1)
    return {
        f"SUG_AUTH_{bit}": bool(count >> bit & 1)
        for bit in range(AUTHORITY_BITS)
    }


def decode_authority_blocks(
    values: Mapping[str, bool], prefix: str
) -> int:
    """Decode an authority, in blocks, from ``<prefix>_n`` bits."""
    return sum(
        (1 << bit)
        for bit in range(AUTHORITY_BITS)
        if values.get(f"{prefix}_{bit}", False)
    )


@dataclass(frozen=True)
class Iteration:
    """One committed program, kept read-only for review."""

    number: int
    file_name: str
    source: str
    committed_at: str
    boolean_count: int
    line_count: int


@dataclass
class ControllerInputs:
    """Everything arriving on the input card for one scan."""

    occupancy: dict[str, bool] = field(default_factory=dict)
    closed: dict[str, bool] = field(default_factory=dict)
    suggested_speed_mph: float = 0.0
    suggested_authority_blocks: int = 0
    #: Block id -> train id, for display only. Not visible to the PLC.
    trains: dict[str, str] = field(default_factory=dict)
    #: Switch id -> physical fault / mid-throw flags from the Track Model.
    switch_fault: dict[str, bool] = field(default_factory=dict)
    switch_moving: dict[str, bool] = field(default_factory=dict)
    #: Posted-limit override from configuration. ``None`` keeps the
    #: per-block limits from the track layout.
    speed_limit_override_mph: float | None = None

    def copy(self) -> "ControllerInputs":
        """Return an independent copy, for sandbox execution."""
        return ControllerInputs(
            occupancy=dict(self.occupancy),
            closed=dict(self.closed),
            suggested_speed_mph=self.suggested_speed_mph,
            suggested_authority_blocks=self.suggested_authority_blocks,
            trains=dict(self.trains),
            switch_fault=dict(self.switch_fault),
            switch_moving=dict(self.switch_moving),
            speed_limit_override_mph=self.speed_limit_override_mph,
        )


@dataclass
class ScanReport:
    """The full result of one scan, live or sandboxed."""

    outputs: ControllerOutputs
    raw_speed_mph: float
    raw_authority_blocks: int
    warnings: tuple[Diagnostic, ...] = ()
    log: tuple[str, ...] = ()


class TrackController:
    """A single wayside controller and the program running on it."""

    def __init__(
        self, config: ControllerConfig, blocks: tuple[Block, ...]
    ) -> None:
        self.config = config
        self.blocks = blocks
        self.inputs = ControllerInputs(
            occupancy={block.block_id: False for block in blocks},
            closed={block.block_id: False for block in blocks},
        )
        self.maintenance = False
        self.manual_switches: dict[str, bool] = {}
        self.history: list[Iteration] = []
        self.outputs: ControllerOutputs = vital.restrictive_outputs(
            config, "no program has been committed yet"
        )

        self._program: Program | None = None
        self._file_name = f"{config.controller_id.lower()}_main.plc".replace(
            "-", ""
        )
        self._iteration = 0

    # --- committed program ------------------------------------------

    @property
    def program(self) -> Program | None:
        """The program currently executing, or ``None`` if unloaded."""
        return self._program

    @property
    def file_name(self) -> str:
        """Name of the file the committed program came from."""
        return self._file_name

    @property
    def iteration(self) -> int:
        """How many programs have been committed to this controller."""
        return self._iteration

    def commit(self, source: str, file_name: str) -> Iteration:
        """Promote a program to the live controller.

        The caller is responsible for having run it first; a program
        with compile errors is refused here as well, because a
        controller with no valid program falls back to restrictive
        outputs rather than running stale logic.
        """
        program = compile_program(source)
        if has_errors(program.diagnostics):
            raise ValueError("a program with errors cannot be committed")

        self._program = program
        self._file_name = file_name
        self._iteration += 1
        entry = Iteration(
            number=self._iteration,
            file_name=file_name,
            source=source,
            committed_at=datetime.now().strftime("%H:%M:%S"),
            boolean_count=program.boolean_count,
            line_count=program.line_count,
        )
        # Newest first, and only the most recent few stay readable.
        self.history.insert(0, entry)
        del self.history[HISTORY_DEPTH:]
        return entry

    # --- scanning ----------------------------------------------------

    def build_scan_inputs(
        self, inputs: ControllerInputs
    ) -> dict[str, bool]:
        """Assemble the boolean input image for one scan.

        Occupancy and closure become one bit per owned block, named by
        the block number: ``OCC_12``, ``CLOSED_12``. Numbering the
        signals rather than lettering them is what lets a declaration
        span a run of blocks as ``OCC_12 .. OCC_38``, including across
        a section boundary.
        """
        image: dict[str, bool] = {}
        for block in self.blocks:
            image[f"OCC_{block.index}"] = inputs.occupancy.get(
                block.block_id, False
            )
            image[f"CLOSED_{block.index}"] = inputs.closed.get(
                block.block_id, False
            )
        for switch in self.config.switches:
            image[f"FAULT_{switch.switch_id}"] = inputs.switch_fault.get(
                switch.switch_id, False
            )
            image[f"MOVING_{switch.switch_id}"] = inputs.switch_moving.get(
                switch.switch_id, False
            )
        image.update(encode_speed_mph(inputs.suggested_speed_mph))
        image.update(
            encode_authority_blocks(inputs.suggested_authority_blocks)
        )
        image["MAINT_HOLD"] = self.maintenance
        return image

    def run_program(
        self, program: Program, inputs: ControllerInputs
    ) -> ScanReport:
        """Scan ``program`` against ``inputs`` without side effects.

        This is what the Program tab's RUN uses: the controller's own
        committed program and live outputs are untouched, so a broken
        candidate program cannot reach the track.
        """
        image = self.build_scan_inputs(inputs)
        result = program.scan(image)

        raw_speed = decode_speed_mph(result.values, "CMD_SPEED")
        raw_authority = decode_authority_blocks(result.values, "CMD_AUTH")

        outputs = vital.supervise(
            config=self.config,
            blocks=self.blocks,
            values=result.values,
            commanded_speed_mph=raw_speed,
            commanded_authority_blocks=raw_authority,
            occupancy=inputs.occupancy,
            closed=inputs.closed,
            manual_switches=self.manual_switches,
            maintenance=self.maintenance,
            current_switches=self.outputs.switches,
            faulted_switches=inputs.switch_fault,
            moving_switches=inputs.switch_moving,
            speed_limit_override_mph=inputs.speed_limit_override_mph,
        )
        return ScanReport(
            outputs=outputs,
            raw_speed_mph=raw_speed,
            raw_authority_blocks=raw_authority,
            warnings=tuple(result.warnings),
            log=tuple(self._format_log(inputs, outputs, raw_speed,
                                       raw_authority)),
        )

    def scan(self) -> ScanReport:
        """Run the committed program and drive the result to the track."""
        if self._program is None:
            self.outputs = vital.restrictive_outputs(
                self.config, "no program is loaded on this controller"
            )
            return ScanReport(
                outputs=self.outputs,
                raw_speed_mph=0.0,
                raw_authority_blocks=0,
            )

        report = self.run_program(self._program, self.inputs)
        self.outputs = report.outputs
        return report

    # --- physical inputs --------------------------------------------
    #
    # These are the writes the Track Model and the CTC make onto the
    # input card. They validate here, at the module boundary, so a bad
    # value from outside is rejected before it can reach a scan.

    def _require_block(self, block_id: str) -> None:
        if not self.config.owns(block_id):
            raise KeyError(
                f"{self.config.controller_id} does not own block {block_id}"
            )

    def _require_switch(self, switch_id: str) -> None:
        if switch_id not in {s.switch_id for s in self.config.switches}:
            raise KeyError(
                f"{self.config.controller_id} has no switch {switch_id}"
            )

    def set_occupancy(self, block_id: str, occupied: bool) -> None:
        """Set train presence on one owned block, from the Track Model."""
        self._require_block(block_id)
        self.inputs.occupancy[block_id] = occupied
        if occupied:
            self.inputs.trains.setdefault(block_id, EXTERNAL_TRAIN_ID)
        else:
            self.inputs.trains.pop(block_id, None)

    def set_closed(self, block_id: str, closed: bool) -> None:
        """Open or close one owned block, from the CTC."""
        self._require_block(block_id)
        self.inputs.closed[block_id] = closed

    def set_switch_fault(self, switch_id: str, faulted: bool) -> None:
        """Flag a switch machine as faulted, from the Track Model."""
        self._require_switch(switch_id)
        self.inputs.switch_fault[switch_id] = faulted

    def set_switch_moving(self, switch_id: str, moving: bool) -> None:
        """Flag a switch machine as mid-throw, from the Track Model."""
        self._require_switch(switch_id)
        self.inputs.switch_moving[switch_id] = moving

    def set_suggestion(
        self,
        speed_mph: float | None = None,
        authority_blocks: float | None = None,
    ) -> None:
        """Set the CTC's suggested speed and/or authority."""
        if speed_mph is not None:
            self.inputs.suggested_speed_mph = _non_negative(
                speed_mph, "suggested speed"
            )
        if authority_blocks is not None:
            self.inputs.suggested_authority_blocks = int(
                _non_negative(authority_blocks, "suggested authority")
            )

    def set_speed_limit_override(self, limit_mph: float | None) -> None:
        """Override the posted limit for this controller, or clear it."""
        if limit_mph is None:
            self.inputs.speed_limit_override_mph = None
            return
        value = _non_negative(limit_mph, "speed limit")
        if value == 0.0:
            raise ValueError("speed limit must be above zero")
        self.inputs.speed_limit_override_mph = value

    def clear_occupancy(self) -> None:
        """Mark every owned block clear."""
        for block in self.blocks:
            self.set_occupancy(block.block_id, False)

    def _format_log(
        self,
        inputs: ControllerInputs,
        outputs: ControllerOutputs,
        raw_speed: float,
        raw_authority: int,
    ) -> list[str]:
        """Render one scan as terminal lines, inputs then outputs."""
        stamp = datetime.now().strftime("%H:%M:%S")
        occupied = [
            block.label
            for block in self.blocks
            if inputs.occupancy.get(block.block_id, False)
        ]
        closed = [
            block.label
            for block in self.blocks
            if inputs.closed.get(block.block_id, False)
        ]

        lines = [
            f"[{stamp}] IN   OCC = "
            f"{', '.join(occupied) if occupied else 'none'}",
            f"[{stamp}] IN   CLOSED = "
            f"{', '.join(closed) if closed else 'none'}",
            f"[{stamp}] IN   CTC suggests {inputs.suggested_speed_mph:.0f} MPH"
            f"   authority {inputs.suggested_authority_blocks} block(s)",
            f"[{stamp}] PLC  raw CMD_SPEED = {raw_speed:.0f} MPH"
            f"   raw CMD_AUTH = {raw_authority} block(s)",
        ]
        for override in outputs.overrides:
            lines.append(f"[{stamp}] {override.format()}")

        lines.append(
            f"[{stamp}] OUT  CMD_SPEED = {outputs.commanded_speed_mph:.0f} MPH"
            f"   CMD_AUTH = {outputs.commanded_authority_blocks} block(s)"
        )
        if outputs.switches:
            rendered = "   ".join(
                f"{name} = {'REVERSE' if state else 'NORMAL'}"
                for name, state in outputs.switches.items()
            )
            lines.append(f"[{stamp}] OUT  {rendered}")
        if outputs.aspects:
            rendered = "   ".join(
                f"{name} = {aspect}"
                for name, aspect in outputs.aspects.items()
            )
            lines.append(f"[{stamp}] OUT  {rendered}")
        if outputs.crossings:
            rendered = "   ".join(
                f"{name} = {'ACTIVE' if state else 'CLEAR'}"
                for name, state in outputs.crossings.items()
            )
            lines.append(f"[{stamp}] OUT  {rendered}")
        if occupied:
            lines.append(
                f"[{stamp}] OUT  occupancy → CTC : {', '.join(occupied)}"
            )
        return lines


def default_program_source(controller: TrackController) -> str:
    """Write a starter program for a controller from its own layout.

    Every controller gets a different set of blocks, switches, signals
    and crossings, so the starter program is generated rather than
    copied: opening a fresh controller shows code that already refers
    to the right signal names.
    """
    config = controller.config
    blocks = controller.blocks
    first, last = blocks[0].index, blocks[-1].index

    switch = config.switches[0]
    signal = config.signals[0]
    crossing = config.crossings[0]
    red, orange, green, super_green = signal.aspect_signals

    switch_block = next(
        block for block in blocks if block.block_id == switch.block_id
    )
    signal_block = next(
        block for block in blocks if block.block_id == signal.block_id
    )
    approach = [
        next(
            block for block in blocks if block.block_id == block_id
        ).index
        for block_id in crossing.approach_block_ids
    ]
    ahead = [
        block.index
        for block in blocks
        if block.index > signal_block.index
    ][:2] or [last]

    occupied_ahead = " OR ".join(f"OCC_{number}" for number in ahead)
    crossing_terms = " OR ".join(f"OCC_{number}" for number in approach)

    return f"""// {config.controller_id}  {config.line_name}  blocks {first}..{last}
// in:  OCC_*, CLOSED_*, SUG_SPEED_0..3, SUG_AUTH_0..3
// out: CMD_SPEED_0..3, CMD_AUTH_0..3, {switch.output_signal}, {red}.., \
{crossing.output_signal}

VAR_IN   OCC_{first} .. OCC_{last}
VAR_IN   SUG_SPEED_0..3
VAR_IN   SUG_AUTH_0..3
VAR_IN   FAULT_{switch.switch_id} MOVING_{switch.switch_id}
VAR_OUT  {switch.output_signal}
VAR_OUT  {red} {orange} {green} {super_green}
VAR_OUT  {crossing.output_signal}
VAR_OUT  CMD_SPEED_0..3
VAR_OUT  CMD_AUTH_0..3

// Switch {switch.switch_id} at block {switch_block.index}: hold normal
// unless the siding is called for and the points are clear.
{switch.output_signal} := OCC_{last} AND NOT OCC_{switch_block.index} \
AND NOT MAINT_HOLD

// Signal {signal.signal_id} at block {signal_block.index} reads ahead.
BUSY_AHEAD := {occupied_ahead}
{green}    := NOT BUSY_AHEAD AND NOT FAULT_{switch.switch_id}
{orange}   := BUSY_AHEAD AND NOT FAULT_{switch.switch_id}
{red}      := FAULT_{switch.switch_id}
{super_green} := 0

// Crossing {crossing.crossing_id}: arm on the approach, hold until clear.
{crossing.output_signal} := {crossing_terms}

// Pass the CTC's suggestion through, suppressed behind occupancy.
AUTH_OK      := NOT BUSY_AHEAD
SPEED_OK     := NOT MOVING_{switch.switch_id}
CMD_AUTH_0   := SUG_AUTH_0 AND AUTH_OK
CMD_AUTH_1   := SUG_AUTH_1 AND AUTH_OK
CMD_AUTH_2   := SUG_AUTH_2 AND AUTH_OK
CMD_AUTH_3   := SUG_AUTH_3 AND AUTH_OK

CMD_SPEED_0  := SUG_SPEED_0 AND AUTH_OK AND SPEED_OK
CMD_SPEED_1  := SUG_SPEED_1 AND AUTH_OK AND SPEED_OK
CMD_SPEED_2  := SUG_SPEED_2 AND AUTH_OK AND SPEED_OK
CMD_SPEED_3  := SUG_SPEED_3 AND AUTH_OK AND SPEED_OK
"""
