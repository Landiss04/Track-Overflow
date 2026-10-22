"""One wayside track controller: I/O image, scan cycle, commit history.

The controller is the bridge between typed module signals and the
boolean-only PLC program. Everything it exchanges is keyed by block
(D015). The CTC Office suggests a speed and an authority for each block
it governs, in whole m/s and blocks. Numbers never enter the program:
the input card gives it one bit per block for occupancy and closure, and
the program answers with one bit per block, ``AUTH_n``, deciding whether
that block's suggestion is passed down its track circuit (1) or replaced
by speed 0 and authority 0 (0).

The program also drives the wayside's switches, signals and crossings,
all as bits. The vital code (:mod:`track_ctrl.vital`), PLC code too, is
attached to the end of every program: it reads the program's outputs and
writes the final ``OUT_`` bits, which can only be more restrictive.

The rest of this class is the OS: it decodes the inputs into bits for
the program and encodes the final bits into typed outputs. It decides
nothing. A wayside running no program transmits nothing at all.

Maintenance mode is the CTC Office's: this module receives it as an
input and obeys it. It has no control of its own to enter or leave it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from track_ctrl import vital
from track_ctrl.display import format_mph
from track_ctrl.layout import YARD, Block, ControllerConfig, Switch
from track_ctrl.plc import (
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    Diagnostic,
    Program,
    blocks_commit,
    compile_program,
)
from track_ctrl.vital import ControllerOutputs, Suggestion, TrackCircuit

#: Per-switch bits only the attached vital code reads: the CTC's command
#: and the hand-set position. A program cannot declare them.
VITAL_SWITCH_INPUTS = ("CTCCMD", "CTCREV", "HAND", "HANDREV")

#: How many committed programs stay readable in the history pane.
HISTORY_DEPTH = 5

#: Train id shown on a block whose occupancy was set from outside the
#: module rather than by a train the stand-in world is moving.
EXTERNAL_TRAIN_ID = "TEST"


def _whole(value: float, what: str) -> int:
    """Return ``value`` as a non-negative whole number.

    Raises:
        ValueError: For NaN, infinity, a negative, or a fraction. Speeds
            and authorities are whole numbers everywhere in the system.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{what} must be a number")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{what} must be zero or more")
    if value != int(value):
        raise ValueError(f"{what} must be a whole number")
    return int(value)


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
    #: The CTC Office's suggestion for each block. A block that is not
    #: listed sends nothing, and gets no track circuit.
    suggestions: dict[str, Suggestion] = field(default_factory=dict)
    #: Block id -> train id, for display only. Not visible to the PLC.
    trains: dict[str, str] = field(default_factory=dict)
    #: Switch id -> the Track Model's read-back, True for reverse. A
    #: switch with no report is decoded as normal.
    switch_reverse: dict[str, bool] = field(default_factory=dict)
    #: From the CTC Office, system-wide. Not a control of this module.
    maintenance: bool = False
    #: Switch id -> position the CTC Office commands, True for reverse.
    #: Sent only in maintenance mode.
    ctc_switch_commands: dict[str, bool] = field(default_factory=dict)

    def copy(self) -> "ControllerInputs":
        """Return an independent copy, for sandbox execution."""
        return ControllerInputs(
            occupancy=dict(self.occupancy),
            closed=dict(self.closed),
            suggestions=dict(self.suggestions),
            trains=dict(self.trains),
            switch_reverse=dict(self.switch_reverse),
            maintenance=self.maintenance,
            ctc_switch_commands=dict(self.ctc_switch_commands),
        )


@dataclass
class ScanReport:
    """The full result of one scan, live or sandboxed."""

    outputs: ControllerOutputs
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
        self.manual_switches: dict[str, bool] = {}
        self.history: list[Iteration] = []
        self.outputs: ControllerOutputs = vital.idle_outputs(
            "no program has been committed yet"
        )
        #: The vital code attached to every program on this wayside.
        self.vital_source = vital.vital_source(config, blocks)
        self._vital = compile_program(self.vital_source)
        if self._vital.diagnostics:
            raise RuntimeError(
                f"vital code for {config.controller_id} does not compile: "
                + self._vital.diagnostics[0].message
            )

        self._program: Program | None = None
        self._file_name = f"{config.controller_id.lower()}_main.plc".replace(
            "-", ""
        )
        self._iteration = 0
        #: Simulated time of day, set by the system on every tick so the
        #: controller's log and commit times agree with the shared
        #: clock. Empty until the first tick.
        self.time_text = ""

    def now_text(self) -> str:
        """Simulated time of day, or wall time before the first tick."""
        return self.time_text or datetime.now().strftime("%H:%M:%S")

    @property
    def maintenance(self) -> bool:
        """Whether the CTC Office has the system in maintenance mode."""
        return self.inputs.maintenance

    # --- the controller's I/O --------------------------------------------

    def input_names(self) -> frozenset[str]:
        """Every name a program may declare ``VAR_IN`` for."""
        names = {"MAINT"}
        for block in self.blocks:
            names.add(f"OCC_{block.block_id}")
            names.add(f"CLOSED_{block.block_id}")
            names.add(f"SUG_{block.block_id}")
        for switch in self.config.switches:
            names.add(f"FAULT_{switch.switch_id}")
            names.add(f"MOVING_{switch.switch_id}")
            names.add(f"REV_{switch.switch_id}")
        return frozenset(names)

    def output_names(self) -> tuple[str, ...]:
        """Every output the controller owns, in a stable order."""
        names = [f"AUTH_{block.block_id}" for block in self.blocks]
        names += [switch.output_signal for switch in self.config.switches]
        for signal in self.config.signals:
            names += list(signal.aspect_signals)
        names += [crossing.output_signal for crossing in self.config.crossings]
        return tuple(names)

    def check_program(self, program: Program) -> tuple[Diagnostic, ...]:
        """Check a compiled program against this controller's own I/O.

        The compiler knows the language but not the controller. A
        program written for another wayside, or for the hardware
        variant, can compile perfectly and still name inputs this
        controller does not have or leave outputs it owns undriven.
        Both are reported, because an undriven output does something
        other than what the programmer meant: a block never passes its
        suggestion, or a signal stays dark and is forced red.
        """
        found: list[Diagnostic] = []
        valid_inputs = self.input_names()
        valid_outputs = set(self.output_names())
        controller_id = self.config.controller_id

        for name in program.inputs:
            if name not in valid_inputs:
                found.append(
                    Diagnostic(
                        SEVERITY_ERROR,
                        program.declared_at.get(name, 0),
                        f"{name} is not an input of {controller_id}",
                    )
                )
        for name in program.outputs:
            if name not in valid_outputs:
                found.append(
                    Diagnostic(
                        SEVERITY_ERROR,
                        program.declared_at.get(name, 0),
                        f"{name} is not an output of {controller_id}",
                    )
                )

        declared = set(program.outputs)
        missing_gates = [
            block.block_id for block in self.blocks
            if f"AUTH_{block.block_id}" not in declared
        ]
        if missing_gates:
            shown = ", ".join(missing_gates[:6])
            more = len(missing_gates) - 6
            found.append(
                Diagnostic(
                    SEVERITY_WARNING,
                    0,
                    f"AUTH is not driven for block(s) {shown}"
                    + (f" and {more} more" if more > 0 else "")
                    + "; they will always send speed 0 and authority 0",
                )
            )
        for name in self.output_names():
            if name.startswith("AUTH_") or name in declared:
                continue
            found.append(
                Diagnostic(
                    SEVERITY_WARNING,
                    0,
                    f"{name} is not driven by this program; "
                    "an undriven output reads as 0",
                )
            )
        return tuple(found)

    def diagnose(self, program: Program) -> tuple[Diagnostic, ...]:
        """Every diagnostic a program has: its own, and its fit here."""
        return program.diagnostics + self.check_program(program)

    # --- committed program ------------------------------------------------

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

        The caller is responsible for having run it first. A program
        with any diagnostic, warning or error, is refused here as well,
        because a controller with no valid program falls back to
        restrictive outputs rather than running stale logic.
        """
        program = compile_program(source)
        diagnostics = self.diagnose(program)
        if blocks_commit(diagnostics):
            raise ValueError(
                "a program with errors or warnings cannot be committed: "
                + diagnostics[0].message
            )

        self._program = program
        self._file_name = file_name
        self._iteration += 1
        entry = Iteration(
            number=self._iteration,
            file_name=file_name,
            source=source,
            committed_at=self.now_text(),
            boolean_count=program.boolean_count,
            line_count=program.line_count,
        )
        # Newest first, and only the most recent few stay readable.
        self.history.insert(0, entry)
        del self.history[HISTORY_DEPTH:]
        return entry

    # --- scanning ----------------------------------------------------------

    def build_scan_inputs(self, inputs: ControllerInputs) -> dict[str, bool]:
        """Assemble the boolean input image for one scan.

        Occupancy and closure become one bit per owned block, named by
        the block number: ``OCC_12``, ``CLOSED_12``. Numbering the
        signals is what lets a declaration span a run of blocks as
        ``OCC_1..20``.

        ``SUG_12`` is set while the CTC Office sends a suggestion for
        block 12, whatever its value. A block with a suggestion and no
        train in it is the next block of the train about to enter it
        (truth ``signals/track-signal``). ``REV_s`` is set while switch
        ``s`` stands reverse as this controller last drove it: the
        position the vital layer locks a switch under a train at. It is
        not the Track Model's read-back, which arrives a tick later.
        """
        image: dict[str, bool] = {}
        for block in self.blocks:
            image[f"OCC_{block.block_id}"] = inputs.occupancy.get(
                block.block_id, False
            )
            image[f"CLOSED_{block.block_id}"] = inputs.closed.get(
                block.block_id, False
            )
            image[f"SUG_{block.block_id}"] = (
                block.block_id in inputs.suggestions
            )
        for switch in self.config.switches:
            sid = switch.switch_id
            image[f"SWREV_{sid}"] = inputs.switch_reverse.get(sid, False)
            image[f"CTCCMD_{sid}"] = sid in inputs.ctc_switch_commands
            image[f"CTCREV_{sid}"] = inputs.ctc_switch_commands.get(
                sid, False
            )
            image[f"MOVING_{switch.switch_id}"] = inputs.switch_moving.get(
                switch.switch_id, False
            )
            image[f"REV_{switch.switch_id}"] = self.outputs.switches.get(
                switch.switch_id, False
            )
        image["MAINT"] = inputs.maintenance
        return image

    def encode_outputs(
        self, values: Mapping[str, bool], inputs: ControllerInputs
    ) -> ControllerOutputs:
        """Turn the vital code's final bits into typed outputs.

        ``OUT_AUTH_n`` passes block *n*'s suggestion (halved where
        ``OUT_HALF_n`` is set) or sends 0. A block with no suggestion
        gets no track circuit. A signal is sent only when exactly one of
        its aspect bits is set; the vital code makes sure one is.
        """
        out = vital.OUT
        circuits: dict[str, TrackCircuit] = {}
        for block in self.blocks:
            n = block.block_id
            suggestion = inputs.suggestions.get(n)
            if suggestion is None:
                continue
            if values.get(f"{out}AUTH_{n}", False):
                speed = suggestion.speed_mps
                if values.get(f"{out}HALF_{n}", False):
                    speed //= 2
                circuits[n] = TrackCircuit(
                    speed, suggestion.authority_blocks
                )
            else:
                circuits[n] = TrackCircuit(0, 0)
        aspects: dict[str, str] = {}
        for signal in self.config.signals:
            lit = [
                aspect for aspect, name in zip(
                    vital.ASPECTS, signal.aspect_signals
                )
                if values.get(out + name, False)
            ]
            if len(lit) == 1:
                aspects[signal.signal_id] = lit[0]
        return ControllerOutputs(
            track_circuits=circuits,
            switches={
                switch.switch_id: values.get(
                    f"{out}SW_{switch.switch_id}", False
                )
                for switch in self.config.switches
            },
            aspects=aspects,
            crossings={
                crossing.crossing_id: values.get(
                    out + crossing.output_signal, False
                )
                for crossing in self.config.crossings
            },
        )

    def run_program(
        self, program: Program, inputs: ControllerInputs
    ) -> ScanReport:
        """Scan ``program``, then the vital code, without side effects.

        One scan: the program first, the attached vital code after it,
        reading the program's outputs. This is also what the Program
        tab's RUN uses: the controller's own committed program and live
        outputs are untouched, so a broken candidate cannot reach the
        track.
        """
        image = self.build_scan_inputs(inputs)
        result = program.scan(image)
        raw = {
            name: result.values.get(name, False)
            for name in self.output_names()
        }
        final = self._vital.scan({**image, **raw})
        outputs = self.encode_outputs(final.values, inputs)
        outputs.overrides = vital.report_overrides(
            self.config, self.blocks, final.values,
            list(inputs.suggestions),
        )
        return ScanReport(
            outputs=outputs,
            warnings=tuple(result.warnings),
            log=tuple(self._format_log(inputs, outputs, result.values)),
        )

    def idle(self, reason: str) -> ScanReport:
        """Run nothing and transmit nothing.

        A wayside with no program running has nothing to send: every
        output is absent, not a safe default.
        """
        self.outputs = vital.idle_outputs(reason)
        return ScanReport(outputs=self.outputs)

    def scan(self) -> ScanReport:
        """Run the committed program and drive the result to the track."""
        if self._program is None:
            return self.idle("no program is loaded on this controller")

        report = self.run_program(self._program, self.inputs)
        self.outputs = report.outputs
        return report

    # --- physical inputs ---------------------------------------------------
    #
    # These are the writes the Track Model and the CTC Office make onto
    # the input card. They validate here, at the module boundary, so a
    # bad value from outside is rejected before it can reach a scan.

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

    def clear_occupancy(self) -> None:
        """Mark every owned block clear."""
        for block in self.blocks:
            self.set_occupancy(block.block_id, False)

    def set_closed(self, block_id: str, closed: bool) -> None:
        """Open or close one owned block, from the CTC Office."""
        self._require_block(block_id)
        self.inputs.closed[block_id] = closed

    def set_switch_position(
        self, switch_id: str, reverse: bool | None
    ) -> None:
        """Record where the Track Model reports a switch actually is.

        ``None`` is no report, decoded as normal.
        """
        self._require_switch(switch_id)
        if reverse is None:
            self.inputs.switch_reverse.pop(switch_id, None)
        else:
            self.inputs.switch_reverse[switch_id] = reverse

    def set_suggestion(
        self,
        block_id: str,
        speed_mps: float | None = None,
        authority_blocks: float | None = None,
    ) -> None:
        """Set the CTC Office's suggestion for one block.

        Either part may be omitted to keep its current value. A block
        with no suggestion yet starts from zero for the part omitted.
        """
        self._require_block(block_id)
        current = self.inputs.suggestions.get(block_id, Suggestion(0, 0))
        speed = (
            current.speed_mps if speed_mps is None
            else _whole(speed_mps, "suggested speed")
        )
        authority = (
            current.authority_blocks if authority_blocks is None
            else _whole(authority_blocks, "suggested authority")
        )
        self.inputs.suggestions[block_id] = Suggestion(speed, authority)

    def set_all_suggestions(
        self,
        speed_mps: float | None = None,
        authority_blocks: float | None = None,
    ) -> None:
        """Set the same suggestion on every owned block."""
        # Validate once, before changing any block, so a bad value leaves
        # the whole territory as it was.
        if speed_mps is not None:
            _whole(speed_mps, "suggested speed")
        if authority_blocks is not None:
            _whole(authority_blocks, "suggested authority")
        for block in self.blocks:
            self.set_suggestion(block.block_id, speed_mps, authority_blocks)

    def clear_suggestion(self, block_id: str) -> None:
        """Remove a block's suggestion: the CTC Office sends nothing."""
        self._require_block(block_id)
        self.inputs.suggestions.pop(block_id, None)

    def set_maintenance(self, active: bool) -> None:
        """Apply the CTC Office's maintenance mode, system-wide.

        Ending it releases every hand-set switch and every CTC switch
        command: both exist only while maintenance lasts.
        """
        self.inputs.maintenance = active
        if not active:
            self.manual_switches.clear()
            self.inputs.ctc_switch_commands.clear()

    def set_ctc_switch_command(
        self, switch_id: str, reverse: bool | None
    ) -> None:
        """Set, or with ``None`` withdraw, the CTC's command for a switch."""
        self._require_switch(switch_id)
        if reverse is None:
            self.inputs.ctc_switch_commands.pop(switch_id, None)
        else:
            self.inputs.ctc_switch_commands[switch_id] = reverse

    # --- log ----------------------------------------------------------------

    def _format_log(
        self,
        inputs: ControllerInputs,
        outputs: ControllerOutputs,
        values: Mapping[str, bool],
    ) -> list[str]:
        """Render one scan as terminal lines, inputs then outputs."""
        stamp = self.now_text()
        occupied = [
            block.label for block in self.blocks
            if inputs.occupancy.get(block.block_id, False)
        ]
        closed = [
            block.label for block in self.blocks
            if inputs.closed.get(block.block_id, False)
        ]
        passing = sum(
            1 for block in self.blocks
            if values.get(f"AUTH_{block.block_id}", False)
            and block.block_id in inputs.suggestions
        )
        carried = [
            circuit for circuit in outputs.track_circuits.values()
            if circuit.speed_mps > 0
        ]
        fastest = max((c.speed_mps for c in carried), default=0)

        lines = [
            f"[{stamp}] IN   OCC = "
            f"{', '.join(occupied) if occupied else 'none'}",
            f"[{stamp}] IN   CLOSED = "
            f"{', '.join(closed) if closed else 'none'}",
            f"[{stamp}] IN   MAINT = {int(inputs.maintenance)}   "
            f"CTC suggestions for {len(inputs.suggestions)} block(s)",
            f"[{stamp}] PLC  AUTH passes {passing} of "
            f"{len(inputs.suggestions)} suggested block(s)",
        ]
        for override in outputs.overrides:
            lines.append(f"[{stamp}] {override.format()}")

        lines.append(
            f"[{stamp}] OUT  track circuits: {len(carried)} of "
            f"{len(outputs.track_circuits)} block(s) carry a speed "
            f"(fastest {format_mph(fastest)})"
        )
        if outputs.switches:
            rendered = "   ".join(
                f"SW_{name} = {'REVERSE' if state else 'NORMAL'}"
                for name, state in outputs.switches.items()
            )
            lines.append(f"[{stamp}] OUT  {rendered}")
        if outputs.aspects:
            rendered = "   ".join(
                f"SIG_{name} = {aspect}"
                for name, aspect in outputs.aspects.items()
            )
            lines.append(f"[{stamp}] OUT  {rendered}")
        if outputs.crossings:
            rendered = "   ".join(
                f"XING_{name} = {'ACTIVE' if state else 'CLEAR'}"
                for name, state in outputs.crossings.items()
            )
            lines.append(f"[{stamp}] OUT  {rendered}")
        if occupied:
            lines.append(
                f"[{stamp}] OUT  occupancy → CTC : {', '.join(occupied)}"
            )
        return lines


# --- the starter program ----------------------------------------------------

def _runs(numbers: list[int]) -> list[tuple[int, int]]:
    """Group sorted block numbers into contiguous ``(first, last)`` runs."""
    runs: list[tuple[int, int]] = []
    for number in numbers:
        if runs and number == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], number)
        else:
            runs.append((number, number))
    return runs


def _declare(keyword: str, prefix: str, numbers: list[int]) -> list[str]:
    """Declaration lines for ``prefix_n`` over ``numbers``, as ranges."""
    names = [
        f"{prefix}_{first}" if first == last else f"{prefix}_{first}..{last}"
        for first, last in _runs(numbers)
    ]
    return [f"{keyword:<8} {name}" for name in names]


def _switch_rule(
    config: ControllerConfig, switch: Switch, owned: set[int]
) -> list[str]:
    """The starter's lines for one switch: set it for the train coming.

    A train comes to a switch's points from its fixed side (facing) or
    from one of its legs (trailing). From the track chart, each way in
    needs one position: a facing train takes the one leg it may run on
    to, a trailing train needs the leg it comes from. The CTC Office
    counts authority only up to a switch not set for the route, trailing
    moves included (``arbitration/authority-stops-before-obstruction``),
    so the wayside sets it first, from what it sees of the train:

    - facing, from the fixed side: the train is on that block and the
      CTC Office has preloaded the points block, its next block
      (``SUG_p AND NOT OCC_p AND OCC_f``);
    - trailing, from a one-way leg: the train is on the leg (``OCC_l``).
      Where the leg is the block the switch is listed on, a train in it
      locks the switch, so the train about to enter it is seen too: the
      leg is preloaded (``SUG_l``), and where the block before it is
      this wayside's, that block is occupied.

    A way in this wayside cannot see (its block is another wayside's)
    is what the switch stands for while no train is seen. The switch is
    held where it stands while its points are occupied and while trains
    come for both positions. Otherwise it is normal in maintenance, as
    before: the CTC Office's command or the programmer's hand-set
    position drives it then (``vital.supervise``). The yard is not routed
    (D022): a train is retired stopped at the yard entry block, so no
    way in or out of it is set for.
    """
    sid = switch.switch_id
    out = switch.output_signal
    point = switch.point
    held = [f"{out} := REV_{sid}"]
    legs = {
        end: position
        for end, position in ((switch.normal_end, False),
                              (switch.reverse_end, True))
        if end != YARD
    }

    def after(block_id: str) -> set[str]:
        return set(config.next_blocks(block_id)) - {YARD}

    def mine(block_id: str) -> bool:
        return block_id.isdigit() and int(block_id) in owned

    title = (
        f"// Switch {sid}: points at {point}, normal to "
        f"{switch.normal_end}, reverse to {switch.reverse_end}."
    )
    if not mine(point):
        return [title, f"// Block {point} is another wayside's, so a train "
                       "on the points cannot be", "// seen: held where it "
                       "stands."] + held
    if not after(point):
        return [title, "// The layout gives no direction of travel: held "
                       "where it stands."] + held
    beside = (
        after(point)
        | {b for b, nexts in config.line_next_blocks if point in nexts}
    ) - set(legs)
    if len(beside) != 1:
        return [title, "// No one fixed side to the points: held where "
                       "it stands."] + held
    fixed = beside.pop()

    wants: dict[bool, list[str]] = {False: [], True: []}
    unseen: set[bool] = set()
    if point in after(fixed):
        exits = [leg for leg in legs if leg in after(point)]
        if len(exits) == 1:
            position = legs[exits[0]]
            if mine(fixed):
                wants[position].append(
                    f"SUG_{point} AND NOT OCC_{point} AND OCC_{fixed}"
                )
            else:
                unseen.add(position)
    if fixed in after(point):
        for leg, position in legs.items():
            if point not in after(leg):
                continue
            if mine(leg) and after(leg) == {point}:
                wants[position].append(_coming_off(config, switch, leg))
            else:
                unseen.add(position)
    rest_reverse = unseen == {True}

    def term(position: bool) -> str:
        found = wants[position]
        if not found:
            return "0"
        if len(found) == 1:
            return found[0]
        return " OR ".join(f"({each})" for each in found)

    name = {False: "normal", True: "reverse"}
    lines = [title]
    lines.append(
        f"// Stands {name[rest_reverse]} until a train is seen coming "
        "for the other position;"
    )
    lines.append(
        f"// held while {point} is occupied or trains come for both; "
        "normal in maintenance."
    )
    if unseen - {rest_reverse}:
        lines.append(
            "// A train coming from another wayside's block for "
            f"{name[not rest_reverse]} is not seen."
        )
    lines += [
        f"WANT_N_{sid} := {term(False)}",
        f"WANT_R_{sid} := {term(True)}",
        f"HOLD_{sid} := OCC_{point} OR (WANT_N_{sid} AND WANT_R_{sid})",
    ]
    move = f"NOT WANT_N_{sid}" if rest_reverse else f"WANT_R_{sid}"
    lines.append(
        f"{out} := (HOLD_{sid} AND REV_{sid}) OR "
        f"(NOT HOLD_{sid} AND NOT MAINT AND {move})"
    )
    return lines


def _coming_off(config: ControllerConfig, switch: Switch, leg: str) -> str:
    """The bits that show a train coming to the points off ``leg``."""
    if leg != switch.block_id:
        return f"OCC_{leg}"
    before = [
        block for block, nexts in config.line_next_blocks if leg in nexts
    ]
    if len(before) == 1 and config.owns(before[0]):
        return f"OCC_{leg} OR (SUG_{leg} AND OCC_{before[0]})"
    return f"OCC_{leg} OR SUG_{leg}"


def default_program_source(controller: TrackController) -> str:
    """Write a starter program for a controller from its own layout.

    Every wayside owns different blocks and devices, and some own no
    switch or crossing at all, so the starter program is generated
    rather than copied: opening a fresh controller shows code that
    already refers to the right names and compiles with no diagnostic.
    """
    config = controller.config
    numbers = sorted(int(block.block_id) for block in controller.blocks)
    owned = set(numbers)

    def occupied(candidates: list[int]) -> str:
        terms = [f"OCC_{n}" for n in candidates if n in owned]
        return " OR ".join(terms) if terms else "0"

    lines: list[str] = [
        f"// {config.controller_id}  {config.line_name}  "
        f"blocks {numbers[0]}..{numbers[-1]}",
        "// OCC_n and CLOSED_n report block n. AUTH_n passes the CTC "
        "Office's speed and",
        "// authority for block n to the train in it (1), or sends "
        "speed 0, authority 0 (0).",
        "",
    ]
    lines += _declare("VAR_IN", "OCC", numbers)
    lines += _declare("VAR_IN", "CLOSED", numbers)
    if config.switches:
        lines += _declare("VAR_IN", "SUG", numbers)
    lines.append("VAR_IN   MAINT")
    if config.switches:
        lines.append("VAR_IN   " + " ".join(
            f"FAULT_{s.switch_id} MOVING_{s.switch_id} REV_{s.switch_id}"
            for s in config.switches
        ))
    lines += _declare("VAR_OUT", "AUTH", numbers)
    if config.switches:
        lines.append("VAR_OUT  " + " ".join(
            s.output_signal for s in config.switches
        ))
    for signal in config.signals:
        lines.append("VAR_OUT  " + " ".join(signal.aspect_signals))
    if config.crossings:
        lines.append("VAR_OUT  " + " ".join(
            c.output_signal for c in config.crossings
        ))

    for switch in config.switches:
        lines.append("")
        lines += _switch_rule(config, switch, owned)

    for signal in config.signals:
        sid = signal.signal_id
        point = int(signal.block_id)
        red, yellow, green, super_green = signal.aspect_signals
        lines += [
            "",
            f"// Signal {sid}: red on a bad block or switch, else yellow "
            "if the route ahead is",
            "// busy, else green. Exactly one aspect is lit for every input.",
            f"AHEAD_{sid} := {occupied([point + 1, point + 2])}",
            f"{red} := OCC_{point} OR CLOSED_{point}",
            f"{yellow} := NOT {red} AND AHEAD_{sid}",
            f"{green} := NOT {red} AND NOT AHEAD_{sid}",
            f"{super_green} := 0",
        ]

    for crossing in config.crossings:
        near = [int(b) for b in crossing.approach_block_ids]
        lines += [
            "",
            f"// Crossing {crossing.crossing_id}: lights and gates while "
            "a train is on it or beside it.",
            f"{crossing.output_signal} := {occupied(near)}",
        ]

    # Only a block with a train in it is held. A block with no train
    # that still has a suggestion is the next block of the train beside
    # it, preloaded by the CTC Office so the train finds its values
    # there as it enters (truth signals/track-signal, suggested-speed).
    # Holding it for that train's own occupancy would send it speed 0
    # and authority 0 at every block it enters.
    lines += [
        "",
        "// Separation: hold a train whose neighbour is occupied. A block "
        "with no train",
        "// in it passes its suggestion: it is the next block of the train "
        "beside it.",
    ]
    switch_blocks = {s.block_id: s.switch_id for s in config.switches}
    for number in numbers:
        beside = [n for n in (number - 1, number + 1) if n in owned]
        if beside:
            others = (
                f"OCC_{beside[0]}" if len(beside) == 1
                else "(" + " OR ".join(f"OCC_{n}" for n in beside) + ")"
            )
            body = f"NOT (OCC_{number} AND {others})"
        else:
            body = "1"
        lines.append(f"AUTH_{number} := {body}")

    return "\n".join(lines) + "\n"
