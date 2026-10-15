"""Track Controller (software) boundary contract.

These are the module's own boundary types (decision D005). The central
harness owns one pure mapping function per producer-to-consumer edge and
translates other modules' types into these and back. No other module's
struct layout appears here, and ``common/interfaces.py`` is not imported
(decision D008).

What the module knows, and what it does not:

- It knows **blocks**. Speed and authority are per block, because a
  wayside sends down a track circuit and cannot address one train. It
  never learns a train's ID, position or speed, only whether a block is
  occupied.
- It does not know **failures**. A broken rail or a dead track circuit
  reaches it as an occupied block and nothing else.
- It does not drive **heaters**. The Track Model switches them on its
  own from the temperature.

Units are backend units per ``truth/conventions/units.md``: speed in
whole m/s, time in s, authority in whole blocks (D013). Every ID is a
string. A block is its line and its number together, because block
numbers repeat across lines (``truth/conventions/identifiers.md``). A
switch, its signal and a crossing are each identified by the block they
are listed on in the track layout. The section letter is not part of the
key: whether it should be is still open.
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
# Identity
# ------------------------------------------------------------------ #

@dataclass(frozen=True, slots=True)
class BlockKey:
    """One block: its line and its number, both strings."""

    line: str
    block_id: str

    @property
    def label(self) -> str:
        """The key as one string, ``Green 12``, for messages."""
        return f"{self.line} {self.block_id}"


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
    """From the CTC Office, every tick."""

    # Blocks the dispatcher has closed. A block not listed is open.
    closed_blocks: frozenset[BlockKey] = frozenset()
    # Positions the dispatcher commanded, by the switch's block: the
    # line and the switch's block, and the position. The CTC Office sends
    # them only in maintenance mode and withdraws them when it ends, and
    # sends no mode flag, so a command in effect is all this module is
    # told. A listed switch is obeyed.
    switch_commands: Mapping[BlockKey, SwitchPosition] = field(
        default_factory=dict
    )
    # A block not listed has nothing to send down its track circuit.
    suggestions: Mapping[BlockKey, Suggestion] = field(default_factory=dict)


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

    occupied: bool
    # The fields below are what the Track Model reported back, not what
    # this module commanded. None where the block has no such device, or
    # the Track Model reported none.
    switch_position: SwitchPosition | None = None
    crossing_active: bool | None = None
    signal_aspect: SignalAspect | None = None


@dataclass(frozen=True, slots=True)
class CtcReport:
    """One wayside's report to the CTC Office: all of its blocks."""

    wayside_id: str
    sent_at_s: float
    blocks: Mapping[BlockKey, BlockReport] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TrackControllerOutputs:
    """Everything one tick produces."""

    # The module has been started up: a line is loaded and every wayside
    # has a PLC program. Until then the module drives only its fail-safe
    # outputs, so the CTC Office must not dispatch a train or send a
    # speed or authority. It is the whole module's, not a wayside's.
    ready: bool = False
    track_model: TrackModelOutputs = field(default_factory=TrackModelOutputs)
    # One report per wayside, in the order the waysides were loaded.
    ctc_reports: tuple[CtcReport, ...] = ()


# ------------------------------------------------------------------ #
# Snapshot, for the Track Controller UI
# ------------------------------------------------------------------ #

@dataclass(frozen=True, slots=True)
class Override:
    """One vital-layer intervention on a scan: what it held, and why."""

    rule: str
    target: str
    message: str


@dataclass(frozen=True, slots=True)
class ProgramInfo:
    """The PLC program a wayside is running."""

    file_name: str
    iteration: int
    checksum: str
    boolean_count: int
    statement_count: int


@dataclass(frozen=True, slots=True)
class SwitchState:
    """One switch as the UI shows it."""

    switch: BlockKey
    commanded: SwitchPosition
    reported: SwitchPosition | None


@dataclass(frozen=True, slots=True)
class WaysideSnapshot:
    """Full observable state of one wayside."""

    wayside_id: str
    line: str
    blocks: tuple[BlockKey, ...]
    program: ProgramInfo | None
    switches: tuple[SwitchState, ...]
    # Commanded and reported signal aspects, by the signal's block.
    signal_commands: Mapping[BlockKey, SignalAspect]
    signal_reports: Mapping[BlockKey, SignalAspect]
    crossing_commands: Mapping[BlockKey, bool]
    crossing_reports: Mapping[BlockKey, bool]
    track_circuits: Mapping[BlockKey, TrackCircuitCommand]
    occupied_blocks: frozenset[BlockKey]
    closed_blocks: frozenset[BlockKey]
    suggestions: Mapping[BlockKey, Suggestion]
    overrides: tuple[Override, ...]
    report: CtcReport | None


@dataclass(frozen=True, slots=True)
class TrackControllerSnapshot:
    """Full observable state of the module, for the UI."""

    waysides: tuple[WaysideSnapshot, ...]
    # True while a CTC switch command is in effect on any switch: the only
    # sign this module gets that the dispatcher is in maintenance mode.
    maintenance_mode: bool
    # Simulation time of the last tick; None before the first.
    time_s: float | None
    ticks: int
    # Whether the module has been started up, and if not, what is missing.
    ready: bool
    not_ready: tuple[str, ...]


# ------------------------------------------------------------------ #
# Module contract
# ------------------------------------------------------------------ #

class TrackController(Protocol):
    """The wayside controllers of one line, stepped by the harness.

    Constructed with no arguments, and not ready. Startup is done from
    the Track Controller UI: a line is loaded, then a PLC program is
    committed to every wayside. The module is ``ready`` only when both
    are done, and until then every wayside drives its fail-safe outputs
    whatever the inputs say.
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

    def load_program(
        self, wayside_id: str, source: str, file_name: str
    ) -> ProgramInfo:
        """Commit a PLC program to one wayside.

        Raises ``InvalidProgramError``, changing nothing, if the program
        has an error or a warning, or does not fit the wayside.
        """
        ...

    # Test UI only. The central harness never calls it.

    def reset(self) -> None:
        """Return every wayside to its state just after loading."""
        ...
