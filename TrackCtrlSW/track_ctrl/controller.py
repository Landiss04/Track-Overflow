"""One wayside track controller: I/O image, scan cycle, commit history.

The controller is the bridge between typed module signals and the
boolean-only PLC program. Everything it exchanges is keyed by block
(D015). The CTC Office suggests a speed and an authority for each block
it governs, in whole m/s and blocks. Numbers never enter the user's
program: the input card gives it one bit per block for occupancy and
closure, and the program answers with one bit per block, ``AUTH_n``,
deciding whether that block's suggestion is passed down its track
circuit (1) or replaced by speed 0 and authority 0 (0). The suggested
speed reaches only the vital code, as bits the program cannot declare,
and the vital code clamps it to the block's posted limit.

The program also drives the wayside's switches, signals and crossings,
all as bits. The vital code (:mod:`track_ctrl.vital`), PLC code too, is
attached to the end of every program: it reads the program's outputs and
writes the final ``OUT_`` bits, which can only be more restrictive.

The rest of this class is the OS: it decodes the inputs into bits for
the program and encodes the final bits into typed outputs. It decides
nothing. A wayside running no program transmits nothing, except that
its crossings stay armed: that is their default state.

Maintenance mode is the CTC Office's: this module receives it as an
input and obeys it. It has no control of its own to enter or leave it.
"""

from __future__ import annotations

import copy
import math
from dataclasses import replace
from datetime import datetime
from typing import Iterable, Mapping

from track_ctrl import vital
from track_ctrl.display import format_mph
from track_ctrl.interface import BlockKey
from track_ctrl.layout import YARD, Block, ControllerConfig
from track_ctrl.plc import (
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    Diagnostic,
    Program,
    blocks_commit,
    compile_program,
)
from track_ctrl.vital import VitalOverride

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


class TrackController:
    """A single wayside controller and the program running on it.

    It holds its own input card and output state as attributes, so one
    object is the whole wayside: what it is told (the ``occupancy``,
    ``closed``, ``suggestions``, ``trains``, ``switch_reverse``,
    ``maintenance`` and ``ctc_switch_commands`` below), the program it
    runs, and what its last scan drove (``track_circuits``,
    ``switch_commands``, ``aspects``, ``crossing_commands``,
    ``overrides``, ``warnings`` and ``log``).

    A committed program is a :class:`~track_ctrl.plc.Program`, stamped
    with its iteration number, file name and commit time. ``history``
    keeps the last few, newest first.
    """

    def __init__(
        self,
        config: ControllerConfig,
        blocks: tuple[Block, ...],
        line: str = "",
    ) -> None:
        self.config = config
        self.blocks = blocks
        #: The key of the line this wayside is on (``Green``), which is
        #: what tells two waysides' block 12 apart at the boundary.
        self.line = line

        # --- the input card: what the wayside is told ---------------------
        self.occupancy: dict[str, bool] = {
            block.block_id: False for block in blocks
        }
        self.closed: dict[str, bool] = {
            block.block_id: False for block in blocks
        }
        #: The CTC Office's suggestion for each block, as ``(speed in
        #: m/s, authority in blocks)``. A block that is not listed sends
        #: nothing, and gets no track circuit.
        self.suggestions: dict[str, tuple[int, int]] = {}
        #: Block id -> train id, for display only. Not visible to the PLC.
        self.trains: dict[str, str] = {}
        #: Switch id -> the Track Model's read-back, True for reverse. A
        #: switch with no report is decoded as normal.
        self.switch_reverse: dict[str, bool] = {}
        #: From the CTC Office, system-wide. Not a control of this module.
        self.maintenance = False
        #: Switch id -> position the CTC Office commands, True for
        #: reverse. Sent only in maintenance mode.
        self.ctc_switch_commands: dict[str, bool] = {}
        self.manual_switches: dict[str, bool] = {}

        # --- the output state: what the last scan drove --------------------
        #: Only for blocks the CTC Office sent a suggestion for, as
        #: ``(speed in m/s, authority in blocks)``.
        self.track_circuits: dict[str, tuple[int, int]] = {}
        self.switch_commands: dict[str, bool] = {}
        self.aspects: dict[str, str] = {}
        self.crossing_commands: dict[str, bool] = {}
        #: Where the vital code changed the program's output.
        self.overrides: tuple[VitalOverride, ...] = ()
        self.warnings: tuple[Diagnostic, ...] = ()
        self.log: tuple[str, ...] = ()

        self.history: list[Program] = []
        self.idle("no program has been committed yet")
        #: The vital code attached to every program on this wayside.
        self.vital_source = vital.vital_source(config, blocks)
        self._speed_width = vital.speed_width(blocks)
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

    def key(self, block_id: str) -> BlockKey:
        """The boundary key of one of this wayside's blocks."""
        return BlockKey(self.line, block_id)

    # --- the controller's I/O --------------------------------------------

    def input_names(self) -> frozenset[str]:
        """Every name a program may declare ``VAR_IN`` for."""
        names = {"MAINT"}
        for block in self.blocks:
            names.add(f"OCC_{block.block_id}")
            names.add(f"CLOSED_{block.block_id}")
            names.add(f"FAIL_{block.block_id}")
        for switch_id in self.config.switches:
            names.add(f"SWREV_{switch_id}")
        return frozenset(names)

    def output_names(self) -> tuple[str, ...]:
        """Every output the controller owns, in a stable order."""
        names = [f"AUTH_{block.block_id}" for block in self.blocks]
        config = self.config
        names += [config.switch_output(s) for s in config.switches]
        for signal_id in config.signals:
            names += list(config.aspect_outputs(signal_id))
        names += [config.crossing_output(c) for c in config.crossings]
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

    def commit(self, source: str, file_name: str) -> Program:
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

        self._file_name = file_name
        self._iteration += 1
        entry = replace(
            program,
            number=self._iteration,
            file_name=file_name,
            committed_at=self.now_text(),
        )
        self._program = entry
        # Newest first, and only the most recent few stay readable.
        self.history.insert(0, entry)
        del self.history[HISTORY_DEPTH:]
        return entry

    # --- scanning ----------------------------------------------------------

    def build_scan_inputs(self) -> dict[str, bool]:
        """Assemble the boolean input image for one scan.

        Occupancy and closure become one bit per owned block, named by
        the block number: ``OCC_12``, ``CLOSED_12``. Numbering the
        signals is what lets a declaration span a run of blocks as
        ``OCC_1..20``.

        The names are HW's, so one program runs on both variants:
        ``FAIL_n`` is always 0 here (this wayside is told of no
        failures, a failed block reads occupied), and ``SWREV_s`` is the
        Track Model's read-back of switch ``s``. A program never sees a
        suggestion's numbers.
        """
        image: dict[str, bool] = {}
        for block in self.blocks:
            image[f"OCC_{block.block_id}"] = self.occupancy.get(
                block.block_id, False
            )
            image[f"CLOSED_{block.block_id}"] = self.closed.get(
                block.block_id, False
            )
            # HW's program language has FAIL_n so one program runs on
            # both variants. This wayside is told of no failures (a
            # failed block reads occupied), so it is always 0 here.
            image[f"FAIL_{block.block_id}"] = False
            # The suggested speed, for the vital code only: a user
            # program cannot declare these. Saturated to the bits it
            # has, which still clamps to every posted limit.
            suggestion = self.suggestions.get(block.block_id)
            speed = 0 if suggestion is None else min(
                suggestion[0], (1 << self._speed_width) - 1
            )
            for bit in range(self._speed_width):
                image[vital.speed_bit(block.block_id, bit)] = bool(
                    (speed >> bit) & 1
                )
        for sid in self.config.switches:
            image[f"SWREV_{sid}"] = self.switch_reverse.get(sid, False)
            image[f"CTCCMD_{sid}"] = sid in self.ctc_switch_commands
            image[f"CTCREV_{sid}"] = self.ctc_switch_commands.get(
                sid, False
            )
            image[f"HAND_{sid}"] = sid in self.manual_switches
            image[f"HANDREV_{sid}"] = self.manual_switches.get(sid, False)
        image["MAINT"] = self.maintenance
        return image

    def encode_outputs(self, values: Mapping[str, bool]) -> None:
        """Turn the vital code's final bits into this wayside's outputs.

        ``OUT_AUTH_n`` passes block *n*'s suggestion (halved where
        ``OUT_HALF_n`` is set) or sends 0. A block with no suggestion
        gets no track circuit. A signal is sent only when exactly one of
        its aspect bits is set; the vital code makes sure one is.
        """
        out = vital.OUT
        circuits: dict[str, tuple[int, int]] = {}
        for block in self.blocks:
            n = block.block_id
            suggestion = self.suggestions.get(n)
            if suggestion is None:
                continue
            if values.get(f"{out}AUTH_{n}", False):
                authority = suggestion[1]
                speed = sum(
                    1 << bit for bit in range(self._speed_width)
                    if values.get(f"{out}SPD_{n}_{bit}", False)
                )
                if values.get(f"{out}HALF_{n}", False):
                    speed //= 2
                circuits[n] = (speed, authority)
            else:
                circuits[n] = (0, 0)
        aspects: dict[str, str] = {}
        for signal_id in self.config.signals:
            lit = [
                aspect for aspect, name in zip(
                    vital.ASPECTS, self.config.aspect_outputs(signal_id)
                )
                if values.get(out + name, False)
            ]
            if len(lit) == 1:
                aspects[signal_id] = lit[0]
        self.track_circuits = circuits
        self.switch_commands = {
            switch_id: values.get(f"{out}SW_{switch_id}", False)
            for switch_id in self.config.switches
        }
        self.aspects = aspects
        self.crossing_commands = {
            crossing_id: values.get(
                out + self.config.crossing_output(crossing_id), False
            )
            for crossing_id in self.config.crossings
        }

    def _run(self, program: Program) -> None:
        """One scan of ``program`` and the vital code, onto the outputs.

        The program runs first, the attached vital code after it,
        reading the program's outputs. Decode, program, vital, encode:
        the OS decides nothing.
        """
        image = self.build_scan_inputs()
        result, warnings = program.scan(image)
        raw = {name: result.get(name, False) for name in self.output_names()}
        final, _ = self._vital.scan({**image, **raw})
        self.encode_outputs(final)
        self.overrides = vital.report_overrides(
            self.config, self.blocks, final, list(self.suggestions),
        )
        self.warnings = tuple(warnings)
        self.log = tuple(self._format_log(result))

    def trial(self, program: Program) -> "TrackController":
        """A copy of this wayside, with ``program`` scanned once on it.

        This is what the Program tab's RUN uses. The copy has its own
        input card and its own outputs, so the wayside's committed
        program, its live outputs and the track are untouched and a
        broken candidate cannot reach them. Read the result from the
        copy's output attributes.
        """
        candidate = copy.copy(self)
        for name in ("occupancy", "closed", "suggestions", "trains",
                     "switch_reverse", "ctc_switch_commands",
                     "manual_switches"):
            setattr(candidate, name, dict(getattr(self, name)))
        candidate.history = list(self.history)
        candidate._run(program)
        return candidate

    def idle(self, reason: str) -> None:
        """Run nothing and transmit nothing.

        A wayside with no program running has nothing to send, except
        that its crossings stay armed: every other output is absent, not
        a safe default.
        """
        self.track_circuits = {}
        self.switch_commands = {}
        self.aspects = {}
        # The default state of a crossing is armed, lights on and gates
        # down: it stays so until a program is running and says
        # otherwise. Nothing else is sent.
        self.crossing_commands = {c: True for c in self.config.crossings}
        self.overrides = (VitalOverride("not_running", "ALL", reason),)
        self.warnings = ()
        self.log = ()

    def scan(self) -> None:
        """Run the committed program and drive the result to the track."""
        if self._program is None:
            self.idle("no program is loaded on this controller")
            return
        self._run(self._program)

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
        if switch_id not in self.config.switches:
            raise KeyError(
                f"{self.config.controller_id} has no switch {switch_id}"
            )

    def set_occupancy(self, block_id: str, occupied: bool) -> None:
        """Set train presence on one owned block, from the Track Model."""
        self._require_block(block_id)
        self.occupancy[block_id] = occupied
        if occupied:
            self.trains.setdefault(block_id, EXTERNAL_TRAIN_ID)
        else:
            self.trains.pop(block_id, None)

    def clear_occupancy(self) -> None:
        """Mark every owned block clear."""
        for block in self.blocks:
            self.set_occupancy(block.block_id, False)

    def set_closed(self, block_id: str, closed: bool) -> None:
        """Open or close one owned block, from the CTC Office."""
        self._require_block(block_id)
        self.closed[block_id] = closed

    def set_switch_position(
        self, switch_id: str, reverse: bool | None
    ) -> None:
        """Record where the Track Model reports a switch actually is.

        ``None`` is no report, decoded as normal.
        """
        self._require_switch(switch_id)
        if reverse is None:
            self.switch_reverse.pop(switch_id, None)
        else:
            self.switch_reverse[switch_id] = reverse

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
        current = self.suggestions.get(block_id, (0, 0))
        speed = (
            current[0] if speed_mps is None
            else _whole(speed_mps, "suggested speed")
        )
        authority = (
            current[1] if authority_blocks is None
            else _whole(authority_blocks, "suggested authority")
        )
        self.suggestions[block_id] = (speed, authority)

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
        self.suggestions.pop(block_id, None)

    def set_maintenance(self, active: bool) -> None:
        """Apply the CTC Office's maintenance mode, system-wide.

        Ending it releases every hand-set switch and every CTC switch
        command: both exist only while maintenance lasts.
        """
        self.maintenance = active
        if not active:
            self.manual_switches.clear()
            self.ctc_switch_commands.clear()

    def set_ctc_switch_command(
        self, switch_id: str, reverse: bool | None
    ) -> None:
        """Set, or with ``None`` withdraw, the CTC's command for a switch."""
        self._require_switch(switch_id)
        if reverse is None:
            self.ctc_switch_commands.pop(switch_id, None)
        else:
            self.ctc_switch_commands[switch_id] = reverse

    # --- log ----------------------------------------------------------------

    def _format_log(self, values: Mapping[str, bool]) -> list[str]:
        """Render one scan as terminal lines, inputs then outputs."""
        stamp = self.now_text()
        occupied = [
            block.label for block in self.blocks
            if self.occupancy.get(block.block_id, False)
        ]
        closed = [
            block.label for block in self.blocks
            if self.closed.get(block.block_id, False)
        ]
        passing = sum(
            1 for block in self.blocks
            if values.get(f"AUTH_{block.block_id}", False)
            and block.block_id in self.suggestions
        )
        carried = [
            circuit for circuit in self.track_circuits.values()
            if circuit[0] > 0
        ]
        fastest = max((c[0] for c in carried), default=0)

        lines = [
            f"[{stamp}] IN   OCC = "
            f"{', '.join(occupied) if occupied else 'none'}",
            f"[{stamp}] IN   CLOSED = "
            f"{', '.join(closed) if closed else 'none'}",
            f"[{stamp}] IN   MAINT = {int(self.maintenance)}   "
            f"CTC suggestions for {len(self.suggestions)} block(s)",
            f"[{stamp}] PLC  AUTH passes {passing} of "
            f"{len(self.suggestions)} suggested block(s)",
        ]
        for override in self.overrides:
            lines.append(f"[{stamp}] {override.format()}")

        lines.append(
            f"[{stamp}] OUT  track circuits: {len(carried)} of "
            f"{len(self.track_circuits)} block(s) carry a speed "
            f"(fastest {format_mph(fastest)})"
        )
        if self.switch_commands:
            rendered = "   ".join(
                f"SW_{name} = {'REVERSE' if state else 'NORMAL'}"
                for name, state in self.switch_commands.items()
            )
            lines.append(f"[{stamp}] OUT  {rendered}")
        if self.aspects:
            rendered = "   ".join(
                f"SIG_{name} = {aspect}"
                for name, aspect in self.aspects.items()
            )
            lines.append(f"[{stamp}] OUT  {rendered}")
        if self.crossing_commands:
            rendered = "   ".join(
                f"XING_{name} = {'ACTIVE' if state else 'CLEAR'}"
                for name, state in self.crossing_commands.items()
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
    config: ControllerConfig, sid: str, owned: set[int]
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
      points block, its next block, is clear
      (``NOT OCC_p AND OCC_f``);
    - trailing, from a one-way leg: the train is on the leg (``OCC_l``).
      Where the leg is the block the switch is listed on, a train in it
      locks the switch, so the train about to enter it is seen too:
      where the block before the leg is this wayside's, that block
      occupied counts as well.

    The program reads only occupancy, closure, maintenance and the
    switch's read-back (``SWREV_s``): HW's names, so the same program
    runs on both variants. It never sees a suggestion.

    A way in this wayside cannot see (its block is another wayside's)
    is what the switch stands for while no train is seen. The switch is
    held where it stands while its points are occupied and while trains
    come for both positions. Otherwise it is normal in maintenance, as
    before: the CTC Office's command or the programmer's hand-set
    position drives it then (``vital.supervise``). The yard is not routed
    (D022): a train is retired stopped at the yard entry block, so no
    way in or out of it is set for.
    """
    out = config.switch_output(sid)
    point, normal_end, reverse_end = config.switches[sid]
    held = [f"{out} := SWREV_{sid}"]
    legs = {
        end: position
        for end, position in ((normal_end, False), (reverse_end, True))
        if end != YARD
    }

    def after(block_id: str) -> set[str]:
        return set(config.next_blocks(block_id)) - {YARD}

    def mine(block_id: str) -> bool:
        return block_id.isdigit() and int(block_id) in owned

    title = (
        f"// Switch {sid}: points at {point}, normal to "
        f"{normal_end}, reverse to {reverse_end}."
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
                    f"NOT OCC_{point} AND OCC_{fixed}"
                )
            else:
                unseen.add(position)
    if fixed in after(point):
        for leg, position in legs.items():
            if point not in after(leg):
                continue
            if mine(leg) and after(leg) == {point}:
                wants[position].append(_coming_off(config, sid, leg))
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
        f"{out} := (HOLD_{sid} AND SWREV_{sid}) OR "
        f"(NOT HOLD_{sid} AND NOT MAINT AND {move})"
    )
    return lines


def _coming_off(config: ControllerConfig, sid: str, leg: str) -> str:
    """The bits that show a train coming to the points off ``leg``."""
    if leg != sid:
        return f"OCC_{leg}"
    before = [
        block for block, nexts in config.line_next_blocks if leg in nexts
    ]
    if len(before) == 1 and config.owns(before[0]):
        return f"OCC_{leg} OR OCC_{before[0]}"
    return f"OCC_{leg}"


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

    def occupied(candidates: Iterable[str]) -> str:
        terms = [f"OCC_{n}" for n in candidates if n.isdigit()
                 and int(n) in owned]
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
    lines.append("VAR_IN   MAINT")
    if config.switches:
        lines.append("VAR_IN   " + " ".join(
            f"SWREV_{s}" for s in config.switches
        ))
    lines += _declare("VAR_OUT", "AUTH", numbers)
    if config.switches:
        lines.append("VAR_OUT  " + " ".join(
            config.switch_output(s) for s in config.switches
        ))
    for sid in config.signals:
        lines.append("VAR_OUT  " + " ".join(config.aspect_outputs(sid)))
    if config.crossings:
        lines.append("VAR_OUT  " + " ".join(
            config.crossing_output(c) for c in config.crossings
        ))

    for sid in config.switches:
        lines.append("")
        lines += _switch_rule(config, sid, owned)

    for sid in config.signals:
        point = int(sid)
        red, yellow, green, super_green = config.aspect_outputs(sid)
        lines += [
            "",
            f"// Signal {sid}: red on a bad block or switch, else yellow "
            "if the route ahead is",
            "// busy, else green. Exactly one aspect is lit for every input.",
            f"AHEAD_{sid} := {occupied(config.within(sid, 2))}",
            f"{red} := OCC_{point} OR CLOSED_{point}",
            f"{yellow} := NOT {red} AND AHEAD_{sid}",
            f"{green} := NOT {red} AND NOT AHEAD_{sid}",
            f"{super_green} := 0",
        ]

    for crossing_id in config.crossings:
        near = config.crossing_approach(crossing_id)
        lines += [
            "",
            f"// Crossing {crossing_id}: lights and gates while "
            "a train is on it or beside it.",
            f"{config.crossing_output(crossing_id)} := {occupied(near)}",
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
    for number in numbers:
        beside = [int(n) for n in config.neighbours(str(number))
                  if n.isdigit() and int(n) in owned]
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
