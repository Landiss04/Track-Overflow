"""One wayside controller: I/O image, scan cycle, vital layer, report.

Each scan builds the Boolean input image from the CTC Office's and the
Track Model's inputs for this wayside's blocks, runs the PLC program on
both channels, and decodes the outputs. A vital layer then checks the
result against the track. It can only make an output more restrictive:
it never raises a speed, grants an authority, lifts a crossing gate or
moves a switch the program held.

PLC names, for a block numbered ``n``:

==============  =====  ====================================================
Name            Kind   Meaning
==============  =====  ====================================================
``OCC_n``       in     Occupied; a failed track circuit reads occupied
``CLOSED_n``    in     Closed by the dispatcher
``FAIL_n``      in     A failure is reported on the block
``SWREV_n``     in     The switch listed on block n reports reverse
``MAINT``       in     The CTC Office has maintenance mode on
``AUTH_n``      out    1 passes the CTC's speed and authority down block n's
                       track circuit; 0 sends speed 0, authority 0
``SW_n``        out    1 commands the switch on block n to reverse
``SIG_n_R``     out    The signal on block n shows red; likewise ``_Y``,
                       ``_G`` and ``_SG``. Exactly one must be 1.
``XING_n``      out    1 activates the crossing on block n: lights on,
                       gates down
==============  =====  ====================================================

Numbers stay outside the program: it decides whether the CTC Office's
suggestion goes out, and the wayside sends the numbers.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Mapping

from track_ctrl_hw.errors import PlcError
from track_ctrl_hw.interface import (
    SIGNAL_ASPECTS,
    BlockKey,
    BlockReport,
    CtcInputs,
    CtcReport,
    FailureKind,
    Override,
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
    WaysideSnapshot,
)
from track_ctrl_hw.plc import Program, compile_program

#: PLC suffix for each signal aspect, in ``SIGNAL_ASPECTS`` order.
ASPECT_SUFFIXES: tuple[str, ...] = ("R", "Y", "G", "SG")

# A speed limit within this of a whole m/s counts as that whole number,
# so 36 km/h is 10 m/s rather than 9.999... after division.
_LIMIT_TOLERANCE = 1e-9


def input_names(territory: Territory) -> frozenset[str]:
    """Every name this wayside feeds a PLC program."""
    names = {"MAINT"}
    for block in territory.blocks:
        number = block.key.block_id
        names.update((f"OCC_{number}", f"CLOSED_{number}", f"FAIL_{number}"))
    for switch in territory.switches:
        names.add(f"SWREV_{switch.switch_id}")
    return frozenset(names)


def output_names(territory: Territory) -> frozenset[str]:
    """Every name this wayside reads back from a PLC program."""
    names = {f"AUTH_{block.key.block_id}" for block in territory.blocks}
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


def speed_limit_whole_mps(limit_mps: float) -> int:
    """The highest whole m/s that does not exceed a speed limit."""
    return int(math.floor(limit_mps + _LIMIT_TOLERANCE))


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
        self._index = {key: i for i, key in enumerate(territory.keys)}
        self._by_number = {key.block_id: key for key in territory.keys}
        self._blocks = {block.key: block for block in territory.blocks}
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
        # everything restrictive until its first scan.
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
    ) -> WaysideScan:
        """Run one scan cycle against this tick's inputs."""
        territory = self._territory
        keys = territory.keys
        failures = {
            key: track_model.failures[key]
            for key in keys
            if key in track_model.failures
        }
        occupied = frozenset(
            key
            for key in keys
            if key in track_model.occupied_blocks
            or failures.get(key) == "track_circuit"
        )
        closed = frozenset(key for key in keys if key in ctc.closed_blocks)
        suggestions = {
            key: ctc.suggestions[key] for key in keys if key in ctc.suggestions
        }
        maintenance = ctc.maintenance_mode
        overrides: list[Override] = []

        started = time.perf_counter()
        values = self._run_program(
            occupied, closed, failures, track_model, maintenance, overrides
        )
        duration = time.perf_counter() - started

        self._decide_switches(values, ctc, maintenance, occupied, overrides)
        disagreeing = {
            switch.key
            for switch in territory.switches
            if track_model.switch_positions.get(switch.key)
            != self._commanded[switch.key]
        }
        signals = self._decide_signals(values, disagreeing, overrides)
        crossings = self._decide_crossings(
            values, occupied, failures, overrides
        )
        circuits = self._decide_circuits(
            values, suggestions, closed, failures, disagreeing, overrides
        )

        report = CtcReport(
            wayside_id=territory.wayside_id,
            sent_at_s=time_s,
            blocks={
                key: BlockReport(
                    occupied=key in occupied,
                    failure=failures.get(key),
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
            vital_fault=info.vital_fault,
        )
        self._occupied = occupied
        self._closed = closed
        self._failures = failures
        self._suggestions = suggestions
        self._switch_requests = {
            switch.key: ctc.switch_commands[switch.key]
            for switch in territory.switches
            if switch.key in ctc.switch_commands
        }
        self._signal_commands = signals
        self._crossing_commands = crossings
        self._circuits = circuits
        self._overrides = tuple(overrides)
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
            track_circuits=dict(circuits),
            switch_commands=dict(self._commanded),
            crossing_commands=dict(crossings),
            signal_commands=dict(signals),
            report=report,
        )

    def _run_program(
        self,
        occupied: frozenset[BlockKey],
        closed: frozenset[BlockKey],
        failures: Mapping[BlockKey, FailureKind],
        track_model: TrackModelInputs,
        maintenance: bool,
        overrides: list[Override],
    ) -> dict[str, bool] | None:
        # The program's outputs, or None when every output must be held
        # restrictive: no program, or a vital fault.
        if self._scan_info.vital_fault:
            overrides.append(Override(
                "vital_fault", "ALL", self._scan_info.vital_fault
            ))
            return None
        if self._program is None:
            overrides.append(Override(
                "no_program", "ALL",
                "No PLC program is loaded: every signal shows red and "
                "every track circuit sends speed 0, authority 0.",
            ))
            return None
        image = {"MAINT": maintenance}
        for key in self._territory.keys:
            number = key.block_id
            image[f"OCC_{number}"] = key in occupied
            image[f"CLOSED_{number}"] = key in closed
            image[f"FAIL_{number}"] = key in failures
        for switch in self._territory.switches:
            image[f"SWREV_{switch.switch_id}"] = (
                track_model.switch_positions.get(switch.key) == "reverse"
            )
        channel_a = self._program.scan_a(image)
        channel_b = self._program.scan_b(image)
        if channel_a != channel_b:
            differing = sorted(
                name
                for name in channel_a
                if channel_a[name] != channel_b[name]
            )
            fault = (
                "Channels A and B disagree on "
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
                vital_fault=fault,
            )
            overrides.append(Override("vital_fault", "ALL", fault))
            return None
        # Outputs the program does not declare read as 0.
        values = {name: False for name in output_names(self._territory)}
        values.update(channel_a)
        return values

    def _decide_switches(
        self,
        values: Mapping[str, bool] | None,
        ctc: CtcInputs,
        maintenance: bool,
        occupied: frozenset[BlockKey],
        overrides: list[Override],
    ) -> None:
        faulted = bool(self._scan_info.vital_fault)
        for switch in self._territory.switches:
            current = self._commanded[switch.key]
            if faulted:
                wanted = current
            elif maintenance:
                # The dispatcher sets switches; one not commanded holds.
                wanted = ctc.switch_commands.get(switch.key, current)
            elif values is None:
                wanted = current
            else:
                wanted = (
                    "reverse" if values[f"SW_{switch.switch_id}"] else "normal"
                )
            self._set_by[switch.key] = "CTC" if maintenance else "PLC"
            if wanted != current:
                locked = [
                    key.label
                    for key in self._lock_blocks(switch)
                    if key in occupied
                ]
                if locked:
                    overrides.append(Override(
                        "switch_locked",
                        f"SW-{switch.switch_id}",
                        f"Held {current}: {', '.join(locked)} occupied.",
                    ))
                    continue
                self._commanded[switch.key] = wanted

    def _decide_signals(
        self,
        values: Mapping[str, bool] | None,
        disagreeing: set[BlockKey],
        overrides: list[Override],
    ) -> dict[BlockKey, SignalAspect]:
        aspects: dict[BlockKey, SignalAspect] = {}
        for switch in self._territory.switches:
            name = f"SIG-{switch.switch_id}"
            aspect: SignalAspect = "red"
            if values is not None:
                lit = [
                    candidate
                    for candidate, signal_name in zip(
                        SIGNAL_ASPECTS, _signal_names(switch)
                    )
                    if values[signal_name]
                ]
                if len(lit) == 1:
                    aspect = lit[0]
                else:
                    overrides.append(Override(
                        "signal_aspect", name,
                        f"{len(lit)} aspects lit; shown red.",
                    ))
            if aspect != "red" and switch.key in disagreeing:
                overrides.append(Override(
                    "switch_disagrees", name,
                    f"SW-{switch.switch_id} does not report its commanded "
                    f"position; {aspect.replace('_', ' ')} dropped to red.",
                ))
                aspect = "red"
            aspects[switch.key] = aspect
        return aspects

    def _decide_crossings(
        self,
        values: Mapping[str, bool] | None,
        occupied: frozenset[BlockKey],
        failures: Mapping[BlockKey, FailureKind],
        overrides: list[Override],
    ) -> dict[BlockKey, bool]:
        commands: dict[BlockKey, bool] = {}
        keys = self._territory.keys
        for key in self._territory.crossings:
            active = True if values is None else values[f"XING_{key.block_id}"]
            index = self._index[key]
            nearby = keys[max(0, index - 1):index + 2]
            cause = next((k for k in nearby if k in occupied), None)
            if not active and (cause is not None or key in failures):
                reason = (
                    f"{cause.label} occupied"
                    if cause is not None
                    else f"failure on {key.label}"
                )
                overrides.append(Override(
                    "crossing_protected", f"XING-{key.block_id}",
                    f"Activated: {reason}.",
                ))
                active = True
            commands[key] = active
        return commands

    def _decide_circuits(
        self,
        values: Mapping[str, bool] | None,
        suggestions: Mapping[BlockKey, Suggestion],
        closed: frozenset[BlockKey],
        failures: Mapping[BlockKey, FailureKind],
        disagreeing: set[BlockKey],
        overrides: list[Override],
    ) -> dict[BlockKey, TrackCircuitCommand]:
        # Blocks a route over a disagreeing switch would use.
        unsafe_route = {
            key
            for switch in self._territory.switches
            if switch.key in disagreeing
            for key in self._route_blocks(switch)
        }
        circuits: dict[BlockKey, TrackCircuitCommand] = {}
        for key in self._territory.keys:
            suggestion = suggestions.get(key)
            if suggestion is None:
                continue
            granted = values is not None and values[f"AUTH_{key.block_id}"]
            speed = suggestion.speed_mps if granted else 0
            authority = suggestion.authority_blocks if granted else 0
            limit = speed_limit_whole_mps(self._blocks[key].speed_limit_mps)
            if speed > limit:
                overrides.append(Override(
                    "speed_limit", key.label,
                    f"{speed} m/s clamped to the {limit} m/s limit.",
                ))
                speed = limit
            reason = (
                "closed" if key in closed
                else f"failed ({failures[key].replace('_', ' ')})"
                if key in failures
                else "on a route over a disagreeing switch"
                if key in unsafe_route
                else ""
            )
            if reason and (speed or authority):
                overrides.append(Override(
                    "block_unusable", key.label,
                    f"Block is {reason}; speed and authority held at 0.",
                ))
                speed = authority = 0
            if authority == 0:
                speed = 0
            circuits[key] = TrackCircuitCommand(speed, authority)
        return circuits

    def _lock_blocks(self, switch: Switch) -> list[BlockKey]:
        # A train here may be on the points, so the switch must not
        # move: the block it is listed on and its point. A train waiting
        # on a leg does not lock it, or it could never be routed.
        return self._keys_for((switch.switch_id, switch.point))

    def _route_blocks(self, switch: Switch) -> list[BlockKey]:
        # Every block whose route runs over the points: the two above
        # and each leg end that lies in this territory.
        return self._keys_for((
            switch.switch_id, switch.point, switch.normal_end,
            switch.reverse_end,
        ))

    def _keys_for(self, numbers: tuple[str, ...]) -> list[BlockKey]:
        found: list[BlockKey] = []
        for number in numbers:
            key = self._by_number.get(number)
            if key is not None and key not in found:
                found.append(key)
        return found

    # -- state ---------------------------------------------------------

    def _clear_runtime(self) -> None:
        territory = self._territory
        self._switch_by_key = {s.key: s for s in territory.switches}
        self._commanded: dict[BlockKey, SwitchPosition] = {
            switch.key: "normal" for switch in territory.switches
        }
        self._set_by: dict[BlockKey, str] = {
            switch.key: "PLC" for switch in territory.switches
        }
        self._scan_info = ScanInfo()
        self._occupied: frozenset[BlockKey] = frozenset()
        self._closed: frozenset[BlockKey] = frozenset()
        self._failures: dict[BlockKey, FailureKind] = {}
        self._suggestions: dict[BlockKey, Suggestion] = {}
        self._switch_requests: dict[BlockKey, SwitchPosition] = {}
        self._switch_reports: dict[BlockKey, SwitchPosition | None] = {}
        self._signal_reports: dict[BlockKey, SignalAspect] = {}
        self._crossing_reports: dict[BlockKey, bool] = {}
        self._report: CtcReport | None = None
        self._hold_restrictive("No scan has run yet.")

    def _hold_restrictive(self, reason: str) -> None:
        # Every signal red, every crossing active, every track circuit
        # that was sending told to stop.
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
        self._overrides: tuple[Override, ...] = (
            Override("holding", "ALL", reason),
        )

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
                    set_by=self._set_by[switch.key],
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
            failures=dict(self._failures),
            suggestions=dict(self._suggestions),
            switch_requests=dict(self._switch_requests),
            overrides=self._overrides,
            report=self._report,
        )
