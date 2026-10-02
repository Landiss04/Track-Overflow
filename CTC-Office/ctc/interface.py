"""CTC Office boundary contract.

These are the CTC Office's own boundary types (decision D005). The
central harness owns one pure mapping function per producer-to-consumer
edge, translating other modules' types into these and back; until the
modules are integrated, the CTC test UI stands in for the neighbors
through ``ctc.link``. Other modules' struct layouts do not appear here,
and ``common/interfaces.py`` is never imported (decision D008).

The CTC exchanges data with two modules:

- Track Controller: sends block occupancy, train reports, switch and
  crossing states and track failures in; receives suggested speed and
  authority per train, closed blocks and maintenance mode out.
- Track Model: sends ticket sales in.

Units are backend units per ``truth/conventions/units.md``: speeds in
m/s, distances in m. Every ID is a string, and authority is a block ID
(``truth/conventions/identifiers.md``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from ctc.schedule import Schedule

SwitchPosition = Literal["normal", "reverse"]
CrossingState = Literal["inactive", "active"]
TrackFailureKind = Literal["broken_rail", "track_circuit", "power"]


# ------------------------------------------------------------------ #
# Inputs
# ------------------------------------------------------------------ #

@dataclass(frozen=True, slots=True)
class BlockOccupancy:
    """Occupancy of one block, as detected by the Track Controller."""

    block_id: str
    occupied: bool


@dataclass(frozen=True, slots=True)
class TrainReport:
    """Where one train is and how fast it is moving."""

    train_id: str
    block_id: str
    offset_m: float
    speed_mps: float


@dataclass(frozen=True, slots=True)
class SwitchReport:
    switch_id: str
    position: SwitchPosition


@dataclass(frozen=True, slots=True)
class CrossingReport:
    crossing_id: str
    state: CrossingState


@dataclass(frozen=True, slots=True)
class TrackFailureReport:
    block_id: str
    kind: TrackFailureKind


@dataclass(frozen=True, slots=True)
class TrackControllerInputs:
    """From the Track Controller, every tick."""

    occupancy: tuple[BlockOccupancy, ...] = ()
    trains: tuple[TrainReport, ...] = ()
    switches: tuple[SwitchReport, ...] = ()
    crossings: tuple[CrossingReport, ...] = ()
    failures: tuple[TrackFailureReport, ...] = ()


@dataclass(frozen=True, slots=True)
class TrackModelInputs:
    """From the Track Model, every tick."""

    # Tickets sold since the previous tick.
    ticket_sales: int = 0


@dataclass(frozen=True, slots=True)
class CtcInputs:
    track_controller: TrackControllerInputs = TrackControllerInputs()
    track_model: TrackModelInputs = TrackModelInputs()


# ------------------------------------------------------------------ #
# Outputs
# ------------------------------------------------------------------ #

@dataclass(frozen=True, slots=True)
class TrainSuggestion:
    """Suggested speed and authority for one train."""

    train_id: str
    suggested_speed_mps: float
    # Block the train may travel up to.
    authority_block_id: str


@dataclass(frozen=True, slots=True)
class TrackControllerOutputs:
    """To the Track Controller, every tick."""

    suggestions: tuple[TrainSuggestion, ...] = ()
    # Blocks closed by the dispatcher. A block not listed is open.
    closed_block_ids: tuple[str, ...] = ()
    maintenance_mode: bool = False


@dataclass(frozen=True, slots=True)
class CtcOutputs:
    track_controller: TrackControllerOutputs = TrackControllerOutputs()


@dataclass(frozen=True, slots=True)
class QueuedTrain:
    """A scheduled run that has not been dispatched yet."""

    line: str
    train_id: str
    # Due at its first stop, in seconds after the schedule start.
    departure_s: int
    first_block_id: str


@dataclass(frozen=True, slots=True)
class CtcSnapshot:
    """Full observable state for the CTC UIs."""

    outputs: CtcOutputs
    inputs: CtcInputs | None = None
    elapsed_s: float = 0.0
    tickets_sold_total: int = 0
    # Runs from the loaded schedule still waiting, by departure time.
    queued_trains: tuple[QueuedTrain, ...] = ()


# ------------------------------------------------------------------ #
# Module contract
# ------------------------------------------------------------------ #

class CtcOffice(Protocol):
    """The CTC Office module, stepped by the harness."""

    def step(self, dt: float, inputs: CtcInputs) -> CtcOutputs:
        """Advance one tick.

        dt is fixed by the harness and must be finite and positive.
        Invalid inputs are rejected before any state is changed.
        """
        ...

    def snapshot(self) -> CtcSnapshot:
        """Current state for display. No side effects."""
        ...

    # Dispatcher actions from the CTC UI. Not cross-module inputs.

    def dispatch(self, train_id: str, destination_block_id: str) -> None:
        """Send a train toward a destination block."""
        ...

    def cancel_dispatch(self, train_id: str) -> None:
        """Drop a train's dispatch order, if it has one."""
        ...

    def set_block_closed(self, block_id: str, closed: bool) -> None:
        """Close a block for maintenance, or reopen it."""
        ...

    def set_maintenance_mode(self, active: bool) -> None:
        ...

    def load_schedule(self, schedule: Schedule) -> None:
        """Replace the schedule; its runs are queued for dispatch."""
        ...
