"""Track Controller (hardware) boundary contract.

These are the module's own boundary types (decision D005). The central
harness owns one pure mapping function per producer-to-consumer edge
and translates other modules' types into these and back. No other
module's struct layout appears here, and ``common/interfaces.py`` is
not imported (decision D008).

The module is one line's set of wayside controllers: the hardware
Track Controller runs every wayside of its line, the software one the
other line. Each wayside governs a territory loaded from a database
file. Everything the module exchanges is keyed by block, because a
wayside knows the blocks it governs, never the trains on them. Nor does
it know failures: a broken rail, a dead track circuit or a power
failure reaches it only as an occupied block, and it reports that block
to the CTC Office as occupied.

Units are backend units per ``truth/conventions/units.md``: speed in
m/s, distance in m, time in s. Authority is a whole number of blocks.
Every ID is a string. A switch, its signal and a crossing are each
identified by the block they are listed on in the database.

What the CTC Office sends names a block as it does, by line and block
number with no section (``BlockRef``, written ``Green:13``). It sends
no maintenance flag: only the blocks it has closed and, while its
dispatcher is in maintenance mode, the switch positions it commands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Protocol

SwitchPosition = Literal["normal", "reverse"]
SignalAspect = Literal["red", "yellow", "green", "super_green"]

SWITCH_POSITIONS: tuple[SwitchPosition, ...] = ("normal", "reverse")
#: Most restrictive first; a signal falls back to the first entry.
SIGNAL_ASPECTS: tuple[SignalAspect, ...] = (
    "red",
    "yellow",
    "green",
    "super_green",
)


# ------------------------------------------------------------------ #
# Identity and territory
# ------------------------------------------------------------------ #

@dataclass(frozen=True, slots=True)
class BlockKey:
    """One block.

    Block numbers repeat across lines, so the line is part of the key.
    The section letter is carried for display and for the report to the
    CTC Office; within a line it follows from the block number.
    """

    line: str
    section: str
    block_id: str

    @property
    def label(self) -> str:
        """Section and number, as the UIs print it: ``C-12``."""
        return f"{self.section}-{self.block_id}"

    @property
    def ref(self) -> BlockRef:
        """The block as the CTC Office names it."""
        return BlockRef(self.line, self.block_id)


@dataclass(frozen=True, slots=True)
class BlockRef:
    """A block, or the switch listed on it, as the CTC Office names it:
    line and block number, no section."""

    line: str
    block_id: str

    @property
    def label(self) -> str:
        """The CTC Office's text form: ``Green:13``."""
        return f"{self.line}:{self.block_id}"


@dataclass(frozen=True, slots=True)
class Block:
    """One block of a wayside's territory, from its database."""

    key: BlockKey
    length_m: float
    speed_limit_mps: float
    # Declared adjacent blocks, including read-only occupancy across waysides.
    next_blocks: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Switch:
    """A switch machine and the signal at the same location.

    Normal is the first connection the database lists for the switch,
    reverse the second. ``point`` is the block both connections share;
    ``normal_end`` and ``reverse_end`` are the block numbers at the far
    end of each, or ``"yard"``. A leg end may lie outside the territory.
    """

    key: BlockKey
    point: str
    normal_end: str
    reverse_end: str

    @property
    def switch_id(self) -> str:
        """The block the switch is listed on."""
        return self.key.block_id


@dataclass(frozen=True, slots=True)
class Territory:
    """The blocks one wayside governs, in database order."""

    line: str
    wayside_id: str
    blocks: tuple[Block, ...]
    switches: tuple[Switch, ...] = ()
    # Blocks with a railway crossing.
    crossings: tuple[BlockKey, ...] = ()

    @property
    def keys(self) -> tuple[BlockKey, ...]:
        """Every block key, in database order."""
        return tuple(block.key for block in self.blocks)


# ------------------------------------------------------------------ #
# Inputs
# ------------------------------------------------------------------ #

@dataclass(frozen=True, slots=True)
class Suggestion:
    """Speed and authority the CTC Office suggests for one block."""

    speed_mps: int
    authority_blocks: int


@dataclass(frozen=True, slots=True)
class CtcInputs:
    """From the CTC Office, every tick, keyed as it names blocks."""

    # Blocks the dispatcher has closed, the full set every tick. A block
    # not listed is open.
    closed_blocks: frozenset[BlockRef] = frozenset()
    # Positions the dispatcher commands, by the switch's block. Sent only
    # while the dispatcher is in maintenance mode, and withdrawn when it
    # ends. They go to the PLC program, which decides whether to obey.
    switch_commands: Mapping[BlockRef, SwitchPosition] = field(
        default_factory=dict
    )
    # A block not listed has nothing to send down its track circuit.
    suggestions: Mapping[BlockRef, Suggestion] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TrackModelInputs:
    """From the Track Model, every tick."""

    # Blocks a train, or a failure, makes read as occupied. The module
    # cannot tell which.
    occupied_blocks: frozenset[BlockKey] = frozenset()
    # Actual positions of the switch machines, by the switch's block.
    switch_positions: Mapping[BlockKey, SwitchPosition] = field(
        default_factory=dict
    )
    # Actual crossing state: True while lights flash and gates are down.
    crossings_active: Mapping[BlockKey, bool] = field(default_factory=dict)
    # Aspect each signal lamp is actually showing, by the signal's block.
    signal_aspects: Mapping[BlockKey, SignalAspect] = field(
        default_factory=dict
    )


@dataclass(frozen=True, slots=True)
class TrackControllerInputs:
    """Everything one tick delivers to the module."""

    # Simulation time of this tick, in seconds since midnight.
    time_s: float
    ctc: CtcInputs = field(default_factory=CtcInputs)
    track_model: TrackModelInputs = field(default_factory=TrackModelInputs)


# ------------------------------------------------------------------ #
# Outputs
# ------------------------------------------------------------------ #

@dataclass(frozen=True, slots=True)
class TrackCircuitCommand:
    """Speed and authority sent down one block's track circuit."""

    speed_mps: int
    authority_blocks: int


@dataclass(frozen=True, slots=True)
class TrackModelOutputs:
    """To the Track Model, every tick."""

    # A block not listed transmits nothing.
    track_circuits: Mapping[BlockKey, TrackCircuitCommand] = field(
        default_factory=dict
    )
    switch_commands: Mapping[BlockKey, SwitchPosition] = field(
        default_factory=dict
    )
    # True: lights on and gates down.
    crossing_commands: Mapping[BlockKey, bool] = field(default_factory=dict)
    signal_commands: Mapping[BlockKey, SignalAspect] = field(
        default_factory=dict
    )


@dataclass(frozen=True, slots=True)
class BlockReport:
    """What a wayside reports to the CTC Office about one block."""

    # A train and a failure both read occupied.
    occupied: bool
    # None where the block has no switch, or none was reported.
    switch_position: SwitchPosition | None = None
    # None where the block has no crossing, or none was reported.
    crossing_active: bool | None = None
    # Aspect the Track Model reports lit. None where the block has no
    # signal, or none was reported.
    signal_aspect: SignalAspect | None = None


@dataclass(frozen=True, slots=True)
class CtcReport:
    """One wayside's report to the CTC Office: all of its blocks."""

    wayside_id: str
    line: str
    sent_at_s: float
    # Started up: a PLC program is loaded and running on both channels.
    # Every wayside of a line holds its fail-safe outputs while any one
    # is not ready, so a ready wayside may still be held.
    ready: bool
    blocks: Mapping[BlockKey, BlockReport] = field(default_factory=dict)
    # Why it is not ready, or "" when it is.
    reason: str = ""


@dataclass(frozen=True, slots=True)
class TrackControllerOutputs:
    """Everything one tick produces."""

    track_model: TrackModelOutputs = field(default_factory=TrackModelOutputs)
    # One report per wayside, in the order the waysides were loaded.
    ctc_reports: tuple[CtcReport, ...] = ()

    @property
    def ready(self) -> bool:
        """Whether the whole module is started up: derived, not sent.

        True only when at least one wayside reports and every one is
        ready.
        """
        return bool(self.ctc_reports) and all(
            report.ready for report in self.ctc_reports
        )

    def not_ready(self) -> tuple[CtcReport, ...]:
        """The reports of the waysides that are not ready."""
        return tuple(r for r in self.ctc_reports if not r.ready)


# ------------------------------------------------------------------ #
# Snapshot, for the Track Controller UI
# ------------------------------------------------------------------ #

@dataclass(frozen=True, slots=True)
class ProgramInfo:
    """The PLC program a wayside is running."""

    file_name: str
    loaded_at_s: float | None
    checksum: str
    boolean_count: int
    statement_count: int
    # Compiler warnings; a program with errors is never loaded.
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScanInfo:
    """Health of a wayside's scan cycle since its program was loaded."""

    scans: int = 0
    last_scan_s: float | None = None
    # Simulation time between scans: the time step of the last tick.
    interval_s: float | None = None
    # Wall-clock time the last scan took, in seconds.
    last_duration_s: float = 0.0
    overruns: int = 0
    # False once channels A and B disagree; cleared by a new program.
    channels_agree: bool = True
    # What they disagreed on, or "". Every output is held fail-safe
    # until a new program is loaded.
    channel_fault: str = ""


@dataclass(frozen=True, slots=True)
class SwitchState:
    """One switch as the UI shows it."""

    switch: Switch
    commanded: SwitchPosition
    reported: SwitchPosition | None

    @property
    def agreeing(self) -> bool:
        """Whether the machine reports the commanded position."""
        return self.reported == self.commanded


@dataclass(frozen=True, slots=True)
class WaysideSnapshot:
    """Full observable state of one wayside."""

    territory: Territory
    program: ProgramInfo | None
    scan: ScanInfo
    switches: tuple[SwitchState, ...]
    # Commanded and actual signal aspects, by the signal's block.
    signal_commands: Mapping[BlockKey, SignalAspect]
    signal_reports: Mapping[BlockKey, SignalAspect]
    crossing_commands: Mapping[BlockKey, bool]
    crossing_reports: Mapping[BlockKey, bool]
    track_circuits: Mapping[BlockKey, TrackCircuitCommand]
    occupied_blocks: frozenset[BlockKey]
    closed_blocks: frozenset[BlockKey]
    suggestions: Mapping[BlockKey, Suggestion]
    # Positions the dispatcher asked for, by the switch's block.
    switch_requests: Mapping[BlockKey, SwitchPosition]
    # Why every output is at its fail-safe value, or "" while the
    # program drives them.
    holding: str
    report: CtcReport | None


@dataclass(frozen=True, slots=True)
class TrackControllerSnapshot:
    """Full observable state of the module, for the UI."""

    line: str | None
    waysides: tuple[WaysideSnapshot, ...]
    # Simulation time of the last tick; None before the first.
    time_s: float | None
    ticks: int
    # Whether at least one wayside is loaded and every one is ready, and
    # if not, what is missing, one line per cause.
    ready: bool
    not_ready: tuple[str, ...]


# ------------------------------------------------------------------ #
# Module contract
# ------------------------------------------------------------------ #

class TrackController(Protocol):
    """One line's wayside controllers, stepped by the harness.

    Constructed with no arguments, and not ready; waysides are added by
    loading their databases from the Track Controller UI. A wayside is
    ready once a PLC program is loaded on it and running. While any
    wayside is not ready, every wayside holds its fail-safe outputs.
    """

    def step(
        self, dt: float, inputs: TrackControllerInputs
    ) -> TrackControllerOutputs:
        """Scan every wayside once and return what it drives.

        ``dt`` is the fixed time step and must be finite and positive.
        Inputs for blocks no wayside governs are ignored. Invalid
        inputs are rejected before any state changes.
        """
        ...

    def snapshot(self) -> TrackControllerSnapshot:
        """Current state for display. No side effects."""
        ...

    # Track Controller UI actions. Not cross-module inputs.

    def load_territory(self, territory: Territory) -> None:
        """Add a wayside, or replace the one with the same ID."""
        ...

    def load_program(
        self, wayside_id: str, source: str, file_name: str
    ) -> ProgramInfo:
        """Replace a wayside's PLC program.

        The new program takes effect at the next scan. Until then every
        signal of that wayside shows red and every track circuit sends
        speed 0, authority 0.
        """
        ...

    # Test UI only. The central harness never calls it.

    def reset(self) -> None:
        """Return every wayside to its state just after loading."""
        ...
