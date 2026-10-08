"""Track Model boundary contract.

These are the Track Model's own boundary types. The central harness owns
one pure mapping function per producer-to-consumer edge, translating other
modules' types into these and back (D005). Other modules' struct layouts
do not appear here.

Every value is in its backend unit, per ``truth/conventions/units.md``:
m/s, m, deg, degrees Celsius. Every ID is a string, per
``truth/conventions/identifiers.md``; authority is a block ID.

Per-train data is keyed by train ID. Per-block data is keyed by block ID,
for example ``"GREEN D-13"``. A switch is keyed by the block ID of its
point block, and a signal by the block ID of the block it stands on.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Protocol


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #

class TrackModelError(Exception):
    """Base class for every error the Track Model raises."""


class InvalidInputError(TrackModelError):
    """An input or command was rejected; no state was changed."""


class UnknownIdError(InvalidInputError):
    """An input named a block, switch, crossing or signal that does not
    exist in the loaded layout."""


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #

class SwitchPosition(Enum):
    """Position of a switch machine."""

    NORMAL = "NORMAL"
    REVERSE = "REVERSE"


class SignalAspect(Enum):
    """Colour shown by a wayside signal light."""

    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    SUPER_GREEN = "SUPER_GREEN"


class TrackFailure(Enum):
    """Failure mode Murphy can inject on a block."""

    NONE = "NONE"
    BROKEN_RAIL = "BROKEN_RAIL"
    TRACK_CIRCUIT = "TRACK_CIRCUIT"
    POWER = "POWER"


#: Platform side at a station. ``"LR"`` is a station with platforms on
#: both sides; the layout files list several. Truth's beacon entry names
#: only L and R, so ``"LR"`` is an open question.
PlatformSide = Literal["L", "R", "LR"]


# --------------------------------------------------------------------------- #
# Static layout
# --------------------------------------------------------------------------- #

@dataclass(frozen=True, slots=True)
class Block:
    """One block of track, as loaded from the layout file."""

    block_id: str
    line: str
    section: str
    number: int
    length_m: float
    grade_deg: float                # positive uphill
    speed_limit_mps: float
    elevation_m: float
    station_name: str | None = None
    platform_side: PlatformSide | None = None
    underground: bool = False
    has_crossing: bool = False
    # Direction of travel, from the layout's next_blocks: the blocks a
    # train may move on to (None = the yard). Empty where the line is
    # not annotated.
    next_block_ids: tuple[str | None, ...] = ()
    # True where trains run both ways: an exit leads straight back here.
    bidirectional: bool = False

    @property
    def section_id(self) -> str:
        """The section this block is in, e.g. ``"GREEN B"``. Heaters and
        track temperature are per section."""
        return f"{self.line} {self.section}"


@dataclass(frozen=True, slots=True)
class Switch:
    """A switch machine. The Track Model never chooses its position."""

    switch_id: str                  # block ID of the point block
    line: str
    point_block_id: str
    # Block the rails lead to in each position. ``None`` is the yard.
    normal_block_id: str | None
    reverse_block_id: str | None
    # True where trains enter the line from the yard ("Yard-63"),
    # False where they leave for it ("57-yard") or there is no yard leg.
    from_yard: bool = False
    # The raw layout-file text, kept so a reader can check the parse.
    source: str = ""


@dataclass(frozen=True, slots=True)
class TrackConfig:
    """Construction-time configuration."""

    layout_paths: tuple[str, ...]
    # Chance, per station per tick, that one new ticket is sold.
    ticket_probability: float = 0.02
    seed: int = 0


# --------------------------------------------------------------------------- #
# Shared value types
# --------------------------------------------------------------------------- #

@dataclass(frozen=True, slots=True)
class Beacon:
    """Station data broadcast near a station. Fits 128 characters."""

    station_name: str
    platform_side: PlatformSide | None
    underground: bool


@dataclass(frozen=True, slots=True)
class TrackInfo:
    """Terrain for the block a train occupies. Cannot fail."""

    block_id: str
    grade_deg: float
    elevation_m: float
    speed_limit_mps: float
    # Reverses every time the train enters a new block.
    polarity: bool
    station_name: str | None


@dataclass(frozen=True, slots=True)
class TrackSignal:
    """Track circuit data of the occupied block: commanded speed and
    authority only."""

    commanded_speed_mps: int        # whole m/s
    authority_block_id: str | None  # None = no authority commanded


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #

@dataclass(frozen=True, slots=True)
class TrackControllerCommands:
    """From the Track Controller, every tick.

    A key that is absent keeps the last value commanded for it.
    Commanded speed and authority are per block: the Track Controller
    knows which blocks are occupied, not which train is in them, and the
    track circuit carries one signal for the whole block.
    """

    # Block ID -> whole m/s.
    commanded_speed_mps: Mapping[str, int] = field(default_factory=dict)
    # Block ID -> block ID up to which a train in that block may travel.
    commanded_authority: Mapping[str, str] = field(default_factory=dict)
    switch_commands: Mapping[str, SwitchPosition] = field(
        default_factory=dict
    )
    crossing_commands: Mapping[str, bool] = field(default_factory=dict)
    signal_commands: Mapping[str, SignalAspect] = field(default_factory=dict)
    # Section ID (e.g. "GREEN B") -> heaters on. Heaters are per section.
    heater_commands: Mapping[str, bool] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TrainReport:
    """From the Train Model, every tick, for one train."""

    block_id: str
    offset_m: float                 # into the block; negative on rollback
    actual_speed_mps: float         # signed
    block_changed: bool             # recorded only
    passenger_capacity: int


@dataclass(frozen=True, slots=True)
class TrackModelInputs:
    controller: TrackControllerCommands
    # A train absent from this mapping has left the track.
    trains: Mapping[str, TrainReport]
    ambient_temp_c: float


# --------------------------------------------------------------------------- #
# Outputs
# --------------------------------------------------------------------------- #

@dataclass(frozen=True, slots=True)
class TrackControllerOutputs:
    """To the Track Controller. The CTC Office reads these through it.

    Each value is the device's actual state, which a failure can make
    differ from what was commanded (see ``model.py``).
    """

    block_occupancy: Mapping[str, bool]
    switch_states: Mapping[str, SwitchPosition]
    crossing_states: Mapping[str, bool]          # True = gate closed
    signal_states: Mapping[str, SignalAspect]    # every light, every tick
    failure_status: Mapping[str, TrackFailure]
    heater_states: Mapping[str, bool]            # by section, actually on
    ticket_sales: Mapping[str, int]              # by station, this tick
    track_temp_c: Mapping[str, float] = field(   # by section
        default_factory=dict
    )


@dataclass(frozen=True, slots=True)
class TrainFeed:
    """To the Train Model, every tick, for one train."""

    track_info: TrackInfo
    track_signal: TrackSignal
    beacon: Beacon | None           # None when not over a beacon
    passengers_boarded: int


@dataclass(frozen=True, slots=True)
class TrackModelOutputs:
    controller: TrackControllerOutputs
    train_feeds: Mapping[str, TrainFeed]
    # To the Train Controller: the colour a train sees as it enters a
    # signal block, on that tick only; None on every other tick.
    signal_seen: Mapping[str, SignalAspect | None]


# --------------------------------------------------------------------------- #
# Snapshot (Track Model UI only)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True, slots=True)
class TrainView:
    """Where the Track Model believes one train is."""

    train_id: str
    block_id: str
    previous_block_id: str | None
    offset_m: float
    actual_speed_mps: float
    polarity: bool


@dataclass(frozen=True, slots=True)
class TrackModelSnapshot:
    """Full observable state for the Track Model UI. Not an output."""

    blocks: tuple[Block, ...]
    switches: tuple[Switch, ...]
    signal_block_ids: tuple[str, ...]
    beacons: Mapping[str, Beacon]                # by block ID
    trains: tuple[TrainView, ...]
    waiting_passengers: Mapping[str, int]
    ambient_temp_c: float
    elapsed_s: float
    outputs: TrackModelOutputs


@dataclass(frozen=True, slots=True)
class BlockEdit:
    """Test-only override of a block's loaded stats. None = unchanged."""

    length_m: float | None = None
    grade_deg: float | None = None
    speed_limit_mps: float | None = None
    elevation_m: float | None = None

    def values(self) -> tuple[float | None, ...]:
        """Return the fields in declaration order."""
        return (self.length_m, self.grade_deg, self.speed_limit_mps,
                self.elevation_m)


def is_finite(value: float) -> bool:
    """Return whether ``value`` is a finite real number."""
    return isinstance(value, (int, float)) and math.isfinite(value)


def is_whole(value: object) -> bool:
    """Return whether ``value`` is an int and not a bool."""
    return isinstance(value, int) and not isinstance(value, bool)


# --------------------------------------------------------------------------- #
# Module contract
# --------------------------------------------------------------------------- #

class TrackModel(Protocol):
    """Constructed as TrackModel(config: TrackConfig)."""

    config: TrackConfig

    def step(self, dt: float, inputs: TrackModelInputs) -> TrackModelOutputs:
        """Advance one tick.

        dt is fixed by the harness and must be finite and positive.
        Invalid inputs are rejected before any state is changed.
        """
        ...

    def snapshot(self) -> TrackModelSnapshot:
        """Return the current state for display. No side effects."""
        ...

    # Track Model UI action (Murphy). Not a cross-module input.

    def set_block_failure(self, block_id: str, failure: TrackFailure) -> None:
        """Inject or clear a failure on one block."""
        ...

    # Test-only commands. Never used at integration.

    def edit_block(self, block_id: str, edit: BlockEdit) -> None:
        """Override a block's loaded stats."""
        ...

    def reset(self) -> None:
        """Return to the freshly loaded state."""
        ...
