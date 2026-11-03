"""One wayside controller: I/O image, scan cycle, report.

The wayside houses its PLC program. Each scan builds the Boolean input
image from the CTC Office's and the Track Model's inputs for this
wayside's blocks and runs the program on both channels. It then runs the
vital block (``track_ctrl_hw.vital``), generated from the territory, on
both channels over the same inputs and the program's outputs, and drives
the vital block's ``OUT_`` outputs. The vital block can only make an
output more restrictive; every other decision is the program's.

Outputs hold their fail-safe values (every signal red, every crossing
active, every track circuit sending speed 0 and authority 0, every
switch where it is) only while no program runs: none is loaded, a new
one has not scanned yet, or channels A and B have disagreed on either
the program or the vital block.

PLC names, for a block numbered ``n``:

==============  =====  ====================================================
Name            Kind   Meaning
==============  =====  ====================================================
``OCC_n``       in     Occupied: a train, or a failure the Track Model
                       reports as occupancy
``CLOSED_n``    in     Closed by the dispatcher
``SWREV_n``     in     The switch listed on block n reports reverse
``CTCSW_n``     in     The CTC Office commands the switch on block n (it
                       does so only in maintenance mode)
``CTCREV_n``    in     That command is reverse; 0 with no command
``SPD_n_b``     in     Bit b (0 to 4) of the CTC Office's speed for block
                       n, in whole m/s; 0 with no suggestion
``AUTH_n``      out    1 passes the CTC's authority down block n's track
                       circuit; 0 sends authority 0
``CMD_n_b``     out    Bit b (0 to 4) of the speed sent down block n's
                       track circuit, in whole m/s
``SW_n``        out    1 commands the switch on block n to reverse
``SIG_n_R``     out    The signal on block n shows red; likewise ``_Y``,
                       ``_G`` and ``_SG``. Read in that order: red if
                       ``_R`` is 1 or none is, else the first that is 1.
``XING_n``      out    1 activates the crossing on block n: lights on,
                       gates down
==============  =====  ====================================================

Speed is a number, so it crosses the I/O card as five bits, bit 0 being
1 m/s and bit 4 16 m/s: 0 to 31 m/s. The program decides the speed; the
vital block caps it at the block's limit. Authority stays outside the
program: the wayside sends the CTC Office's count when ``AUTH_n`` is 1.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Mapping

from track_ctrl_hw.errors import PlcError
from track_ctrl_hw.interface import (
    SIGNAL_ASPECTS,
    BlockKey,
    BlockReport,
    BlockRef,
    CtcInputs,
    CtcReport,
    ProgramInfo,
    ScanInfo,
    SignalAspect,
    Suggestion,
    Switch,
    SwitchPosition,
    SwitchState,
    Territory,
    TrackCircuitCommand,
    TrackModelInputs,
    VitalInfo,
    WaysideSnapshot,
)
from track_ctrl_hw.plc import Program, compile_program
from track_ctrl_hw.vital import (  # noqa: F401 (speed_limit_whole_mps)
    OUT,
    overrides,
    speed_limit_whole_mps,
    vital_source,
)

#: PLC suffix for each signal aspect, in ``SIGNAL_ASPECTS`` order.
ASPECT_SUFFIXES: tuple[str, ...] = ("R", "Y", "G", "SG")
#: Width of the speed in and out of the program.
SPEED_BITS = 5
#: The fastest speed the I/O card carries, in m/s.
MAX_SPEED_MPS = (1 << SPEED_BITS) - 1


def _neighbor_numbers(territory: Territory) -> frozenset[str]:
    """The adjacent block IDs whose state is shared read-only."""
    return frozenset(number for block in territory.blocks
                     for number in block.next_blocks if number != "yard")


def input_names(territory: Territory) -> frozenset[str]:
    """Every name this wayside feeds a PLC program."""
    names = set()
    for block in territory.blocks:
        number = block.key.block_id
        names.update((f"OCC_{number}", f"CLOSED_{number}"))
        names.update(_speed_names("SPD", number))
    for number in _neighbor_numbers(territory):
        names.update((f"OCC_{number}", f"CLOSED_{number}"))
    for switch in territory.switches:
        number = switch.switch_id
        names.update(
            (f"SWREV_{number}", f"CTCSW_{number}", f"CTCREV_{number}")
        )
    return frozenset(names)


def output_names(territory: Territory) -> frozenset[str]:
    """Every name this wayside reads back from a PLC program."""
    names = set()
    for block in territory.blocks:
        number = block.key.block_id
        names.add(f"AUTH_{number}")
        names.update(_speed_names("CMD", number))
    for switch in territory.switches:
        names.add(f"SW_{switch.switch_id}")
        names.update(_signal_names(switch))
    for crossing in territory.crossings:
        names.add(f"XING_{crossing.block_id}")
    return frozenset(names)


def _signal_names(switch: Switch) -> tuple[str, ...]:
    return tuple(
        f"SIG_{switch.switch_id}_{suffix}" for suffix in ASPECT_SUFFIXES
    )


def _speed_names(prefix: str, number: str) -> tuple[str, ...]:
    # Least significant bit first.
    return tuple(f"{prefix}_{number}_{bit}" for bit in range(SPEED_BITS))


def decode_aspect(values: Mapping[str, bool], switch: Switch) -> SignalAspect:
    """What a signal's four outputs light: the first that is 1 of red,
    yellow, green and super green, or red when none is."""
    for aspect, name in zip(SIGNAL_ASPECTS, _signal_names(switch)):
        if values[name]:
            return aspect
    return "red"


def check_program(
    program: Program, territory: Territory
) -> tuple[list[str], list[str]]:
    """Check a compiled program against a territory's I/O.

    Returns:
        The errors that stop it loading, then the warnings, as text.
    """
    errors = [str(diagnostic) for diagnostic in program.errors]
    warnings = [str(diagnostic) for diagnostic in program.warnings]
    inputs = input_names(territory)
    outputs = output_names(territory)
    wayside = f"wayside {territory.wayside_id}"
    for name in program.inputs:
        if name not in inputs:
            errors.append(f"Error: VAR_IN {name} is not an input of {wayside}")
    for name in program.outputs:
        if name not in outputs:
            errors.append(
                f"Error: VAR_OUT {name} is not an output of {wayside}"
            )
    for name in sorted(program.assigned - set(program.outputs)):
        if name in outputs:
            warnings.append(
                f"Warning: {name} is assigned but not declared VAR_OUT, so "
                "it never reaches the track"
            )
    return errors, warnings


@dataclass(frozen=True)
class WaysideScan:
    """What one scan of one wayside drives and reports."""

    track_circuits: dict[BlockKey, TrackCircuitCommand]
    switch_commands: dict[BlockKey, SwitchPosition]
    crossing_commands: dict[BlockKey, bool]
    signal_commands: dict[BlockKey, SignalAspect]
    report: CtcReport


class Wayside:
    """One wayside controller and the PLC program it runs."""

    def __init__(self, territory: Territory) -> None:
        self._territory = territory
        self._keys = frozenset(territory.keys)
        self._vital = compile_program(vital_source(territory))
        if self._vital.diagnostics:
            raise RuntimeError(
                f"Vital block for wayside {territory.wayside_id} does not "
                f"compile: {self._vital.diagnostics[0]}"
            )
        self._program: Program | None = None
        self._program_info: ProgramInfo | None = None
        self._clear_runtime()

    # -- configuration ---------------------------------------------

    @property
    def territory(self) -> Territory:
        """The blocks this wayside governs."""
        return self._territory

    @property
    def program(self) -> Program | None:
        """The program being scanned, or None."""
        return self._program

    def owns(self, key: BlockKey) -> bool:
        """Whether this wayside governs ``key``."""
        return key in self._keys

    @property
    def not_ready_reason(self) -> str:
        """Why this wayside is not ready, or "" when it is: a program
        is loaded and its channels agree."""
        if self._program is None:
            return "No PLC program is loaded."
        return self._scan_info.channel_fault

    def load_program(
        self, source: str, file_name: str, time_s: float | None
    ) -> ProgramInfo:
        """Compile and install a program; it runs from the next scan.

        Raises:
            PlcError: If the program has errors or does not fit.
        """
        program = compile_program(source)
        errors, warnings = check_program(program, self._territory)
        if errors:
            raise PlcError(
                f"{file_name} was not loaded: {len(errors)} problem(s).",
                tuple(errors),
            )
        self._program = program
        self._program_info = ProgramInfo(
            file_name=file_name,
            loaded_at_s=time_s,
            checksum=program.checksum,
            boolean_count=program.boolean_count,
            statement_count=len(program.statements),
            warnings=tuple(warnings),
        )
        # A new program starts from a clean bill of health, and holds
        # every output fail-safe until its first scan.
        self._scan_info = ScanInfo()
        self._hold_restrictive("A new program runs from the next scan.")
        return self._program_info

    def adopt_program(self, previous: Wayside) -> bool:
        """Keep another wayside's program if it fits this territory.

        Used when a wayside's database is reloaded. Returns whether the
        program was kept.
        """
        if previous.program is None or previous._program_info is None:
            return False
        errors, _ = check_program(previous.program, self._territory)
        if errors:
            return False
        self._program = previous.program
        self._program_info = previous._program_info
        return True

    def reset(self) -> None:
        """Forget every scan; keep the territory and the program."""
        self._clear_runtime()

    # -- scanning ----------------------------------------------------

    def scan(
        self,
        dt: float,
        time_s: float,
        ctc: CtcInputs,
        track_model: TrackModelInputs,
        stall: str = "",
    ) -> WaysideScan:
        """Run one scan cycle against this tick's inputs.

        ``stall`` is why another wayside of the line holds this one
        fail-safe, or "". A wayside that is not ready holds itself.
        """
        territory = self._territory
        keys = territory.keys
        occupied = frozenset(
            key for key in keys if key in track_model.occupied_blocks
        )
        closed = frozenset(
            key for key in keys if key.ref in ctc.closed_blocks
        )
        suggestions = {
            key: ctc.suggestions[key.ref]
            for key in keys
            if key.ref in ctc.suggestions
        }
        requests = {
            switch.key: ctc.switch_commands[switch.key.ref]
            for switch in territory.switches
            if switch.key.ref in ctc.switch_commands
        }

        started = time.perf_counter()
        if stall and not self.not_ready_reason:
            values, holding = None, stall
        else:
            values, holding = self._run_program(
                occupied, closed, suggestions, requests, track_model, ctc
            )
        duration = time.perf_counter() - started

        self._occupied = occupied
        self._closed = closed
        self._suggestions = suggestions
        self._switch_requests = requests
        if values is None:
            self._hold_restrictive(holding)
        else:
            self._drive(values)

        reason = self.not_ready_reason
        report = CtcReport(
            wayside_id=territory.wayside_id,
            line=territory.line,
            sent_at_s=time_s,
            ready=not reason,
            reason=reason,
            blocks={
                key: BlockReport(
                    occupied=key in occupied,
                    switch_position=(
                        track_model.switch_positions.get(key)
                        if key in self._switch_by_key
                        else None
                    ),
                    crossing_active=(
                        track_model.crossings_active.get(key)
                        if key in territory.crossings
                        else None
                    ),
                    signal_aspect=(
                        track_model.signal_aspects.get(key)
                        if key in self._switch_by_key
                        else None
                    ),
                )
                for key in keys
            },
        )

        info = self._scan_info
        self._scan_info = ScanInfo(
            scans=info.scans + 1,
            last_scan_s=time_s,
            interval_s=dt,
            last_duration_s=duration,
            overruns=info.overruns + (1 if duration > dt else 0),
            channels_agree=info.channels_agree,
            channel_fault=info.channel_fault,
        )
        self._report = report
        self._switch_reports = {
            switch.key: track_model.switch_positions.get(switch.key)
            for switch in territory.switches
        }
        self._signal_reports = {
            switch.key: track_model.signal_aspects[switch.key]
            for switch in territory.switches
            if switch.key in track_model.signal_aspects
        }
        self._crossing_reports = {
            key: track_model.crossings_active[key]
            for key in territory.crossings
            if key in track_model.crossings_active
        }
        return WaysideScan(
            track_circuits=dict(self._circuits),
            switch_commands=dict(self._commanded),
            crossing_commands=dict(self._crossing_commands),
            signal_commands=dict(self._signal_commands),
            report=report,
        )

    def _run_program(
        self,
        occupied: frozenset[BlockKey],
        closed: frozenset[BlockKey],
        suggestions: Mapping[BlockKey, Suggestion],
        requests: Mapping[BlockKey, SwitchPosition],
        track_model: TrackModelInputs,
        ctc: CtcInputs,
    ) -> tuple[dict[str, bool] | None, str]:
        # The program's outputs and "", or None and why no program runs.
        if self._scan_info.channel_fault:
            return None, self._scan_info.channel_fault
        if self._program is None:
            return None, "No PLC program is loaded."
        image: dict[str, bool] = {}
        for key in self._territory.keys:
            number = key.block_id
            image[f"OCC_{number}"] = key in occupied
            image[f"CLOSED_{number}"] = key in closed
            suggestion = suggestions.get(key)
            speed = 0 if suggestion is None else suggestion.speed_mps
            for bit, name in enumerate(_speed_names("SPD", number)):
                image[name] = bool(speed >> bit & 1)
        occupied_refs = {key.ref for key in track_model.occupied_blocks}
        for number in _neighbor_numbers(self._territory):
            ref = BlockRef(self._territory.line, number)
            image[f"OCC_{number}"] = ref in occupied_refs
            image[f"CLOSED_{number}"] = ref in ctc.closed_blocks
        for switch in self._territory.switches:
            number = switch.switch_id
            image[f"SWREV_{number}"] = (
                track_model.switch_positions.get(switch.key) == "reverse"
            )
            image[f"CTCSW_{number}"] = switch.key in requests
            image[f"CTCREV_{number}"] = requests.get(switch.key) == "reverse"
        channel_a = self._program.scan_a(image)
        channel_b = self._program.scan_b(image)
        if channel_a != channel_b:
            return None, self._channel_fault("", channel_a, channel_b)
        # Outputs the program does not declare read as 0.
        program = {name: False for name in output_names(self._territory)}
        program.update(channel_a)
        vital_image = {**image, **program}
        vital_a = self._vital.scan_a(vital_image)
        vital_b = self._vital.scan_b(vital_image)
        if vital_a != vital_b:
            return None, self._channel_fault("vital ", vital_a, vital_b)
        values = {name: vital_a[OUT + name] for name in program}
        self._overrides = overrides(program, values)
        return values, ""

    def _channel_fault(
        self, which: str, channel_a: Mapping[str, bool],
        channel_b: Mapping[str, bool],
    ) -> str:
        # Latch a disagreement; only a new program clears it.
        differing = sorted(
            name for name in channel_a if channel_a[name] != channel_b[name]
        )
        fault = (
            f"Channels A and B disagree on {which}"
            + ", ".join(differing[:3])
            + ("..." if len(differing) > 3 else "")
            + ". Outputs are held until a program is loaded."
        )
        self._scan_info = ScanInfo(
            scans=self._scan_info.scans,
            last_scan_s=self._scan_info.last_scan_s,
            interval_s=self._scan_info.interval_s,
            last_duration_s=self._scan_info.last_duration_s,
            overruns=self._scan_info.overruns,
            channels_agree=False,
            channel_fault=fault,
        )
        return fault

    def _drive(self, values: Mapping[str, bool]) -> None:
        # The program's outputs, onto the track as they are.
        territory = self._territory
        for switch in territory.switches:
            self._commanded[switch.key] = (
                "reverse" if values[f"SW_{switch.switch_id}"] else "normal"
            )
        self._signal_commands = {
            switch.key: decode_aspect(values, switch)
            for switch in territory.switches
        }
        self._crossing_commands = {
            key: values[f"XING_{key.block_id}"] for key in territory.crossings
        }
        circuits: dict[BlockKey, TrackCircuitCommand] = {}
        for key, suggestion in self._suggestions.items():
            number = key.block_id
            speed = sum(
                1 << bit
                for bit, name in enumerate(_speed_names("CMD", number))
                if values[name]
            )
            authority = (
                suggestion.authority_blocks
                if values[f"AUTH_{number}"]
                else 0
            )
            circuits[key] = TrackCircuitCommand(speed, authority)
        self._circuits = circuits
        self._holding = ""

    # -- state ---------------------------------------------------------

    def _clear_runtime(self) -> None:
        territory = self._territory
        self._switch_by_key = {s.key: s for s in territory.switches}
        self._commanded: dict[BlockKey, SwitchPosition] = {
            switch.key: "normal" for switch in territory.switches
        }
        self._scan_info = ScanInfo()
        self._occupied: frozenset[BlockKey] = frozenset()
        self._closed: frozenset[BlockKey] = frozenset()
        self._suggestions: dict[BlockKey, Suggestion] = {}
        self._switch_requests: dict[BlockKey, SwitchPosition] = {}
        self._switch_reports: dict[BlockKey, SwitchPosition | None] = {}
        self._signal_reports: dict[BlockKey, SignalAspect] = {}
        self._crossing_reports: dict[BlockKey, bool] = {}
        self._report: CtcReport | None = None
        self._overrides: tuple[str, ...] = ()
        self._hold_restrictive("No scan has run yet.")

    def _hold_restrictive(self, reason: str) -> None:
        # Fail-safe while no program runs: every signal red, every
        # crossing active, every track circuit that was sending told to
        # stop, and every switch left where it is.
        territory = self._territory
        self._signal_commands: dict[BlockKey, SignalAspect] = {
            switch.key: "red" for switch in territory.switches
        }
        self._crossing_commands: dict[BlockKey, bool] = {
            key: True for key in territory.crossings
        }
        self._circuits: dict[BlockKey, TrackCircuitCommand] = {
            key: TrackCircuitCommand(0, 0) for key in self._suggestions
        }
        self._overrides = ()
        self._holding = reason

    def snapshot(self) -> WaysideSnapshot:
        """Full observable state of this wayside."""
        territory = self._territory
        return WaysideSnapshot(
            territory=territory,
            program=self._program_info,
            scan=self._scan_info,
            switches=tuple(
                SwitchState(
                    switch=switch,
                    commanded=self._commanded[switch.key],
                    reported=self._switch_reports.get(switch.key),
                )
                for switch in territory.switches
            ),
            signal_commands=dict(self._signal_commands),
            signal_reports=dict(self._signal_reports),
            crossing_commands=dict(self._crossing_commands),
            crossing_reports=dict(self._crossing_reports),
            track_circuits=dict(self._circuits),
            occupied_blocks=self._occupied,
            closed_blocks=self._closed,
            suggestions=dict(self._suggestions),
            switch_requests=dict(self._switch_requests),
            holding=self._holding,
            report=self._report,
            vital=VitalInfo(
                checksum=self._vital.checksum,
                boolean_count=self._vital.boolean_count,
                statement_count=len(self._vital.statements),
            ),
            overrides=self._overrides,
        )
