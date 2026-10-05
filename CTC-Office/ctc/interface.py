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
  authority per train, closed blocks, switch commands and maintenance
  mode out.
- Track Model: sends ticket sales per line in.

It also sends the clock speedup command to the central harness.

Units are backend units per ``truth/conventions/units.md``: speeds in
m/s, distances in m. Every ID is a string, and authority is a block ID
(``truth/conventions/identifiers.md``). Block numbers repeat across
lines, so every block, switch and crossing reference carries its
``line`` too. A switch or crossing is identified by the block it is
listed on in the track layout file.
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

    line: str
    block_id: str
    occupied: bool


@dataclass(frozen=True, slots=True)
class TrainReport:
    """Where one train is and how fast it is moving."""

    train_id: str
    line: str
    block_id: str
    offset_m: float
    speed_mps: float


@dataclass(frozen=True, slots=True)
class SwitchReport:
    line: str
    switch_id: str
    position: SwitchPosition


@dataclass(frozen=True, slots=True)
class CrossingReport:
    line: str
    crossing_id: str
    state: CrossingState


@dataclass(frozen=True, slots=True)
class TrackFailureReport:
    line: str
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
class TicketSales:
    """Tickets sold on one line."""

    line: str
    tickets: int


@dataclass(frozen=True, slots=True)
class TrackModelInputs:
    """From the Track Model, every tick."""

    # Tickets sold since the previous tick, at most one entry per line.
    ticket_sales: tuple[TicketSales, ...] = ()


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
    line: str
    # Whole m/s: a target for safe spacing, not the train's own speed.
    suggested_speed_mps: int
    # Block on ``line`` the train may travel up to.
    authority_block_id: str


@dataclass(frozen=True, slots=True)
class BlockRef:
    """One block: block numbers repeat across lines."""

    line: str
    block_id: str


@dataclass(frozen=True, slots=True)
class SwitchCommand:
    """A switch position set by the dispatcher in maintenance mode.

    Normal is the first connection the layout file lists for the switch,
    reverse the second.
    """

    line: str
    switch_id: str
    position: SwitchPosition


@dataclass(frozen=True, slots=True)
class TrackControllerOutputs:
    """To the Track Controller, every tick."""

    suggestions: tuple[TrainSuggestion, ...] = ()
    # Blocks closed by the dispatcher. A block not listed is open.
    closed_blocks: tuple[BlockRef, ...] = ()
    # Only while maintenance_mode; cleared when it ends.
    switch_commands: tuple[SwitchCommand, ...] = ()
    maintenance_mode: bool = False


@dataclass(frozen=True, slots=True)
class CtcOutputs:
    track_controller: TrackControllerOutputs = TrackControllerOutputs()
    # Clock speedup command, for the central harness to relay to every
    # module so all run at one speed: True for 10x, False for 1x.
    clock_speedup: bool = False


@dataclass(frozen=True, slots=True)
class QueuedTrain:
    """A scheduled run that has not been dispatched yet."""

    line: str
    train_id: str
    # Due at its first stop, in seconds after the schedule start.
    departure_s: int
    first_block_id: str


@dataclass(frozen=True, slots=True)
class DispatchOrder:
    """A dispatcher's order for one train: where, and by when."""

    train_id: str
    line: str
    destination_block_id: str
    # Requested arrival, simulated seconds since midnight; None if the
    # dispatcher set only a destination.
    arrival_s: float | None = None


@dataclass(frozen=True, slots=True)
class CancelledOrder:
    """An order the CTC dropped on its own, and why."""

    train_id: str
    line: str
    destination_block_id: str
    # e.g. "block closed", "block closing", "track failure: power"
    reason: str


@dataclass(frozen=True, slots=True)
class CtcSnapshot:
    """Full observable state for the CTC UIs."""

    outputs: CtcOutputs
    inputs: CtcInputs | None = None
    elapsed_s: float = 0.0
    # Tickets sold since the simulation started, one entry per line.
    tickets_sold: tuple[TicketSales, ...] = ()
    # Runs from the loaded schedule still waiting, by departure time.
    queued_trains: tuple[QueuedTrain, ...] = ()
    # Dispatcher orders, by train ID.
    orders: tuple[DispatchOrder, ...] = ()
    # Closures waiting for a train to leave the block; they close by
    # themselves once it is clear.
    pending_closures: tuple[BlockRef, ...] = ()
    # Orders the CTC cancelled itself, oldest first (the last few).
    cancelled_orders: tuple[CancelledOrder, ...] = ()
    # Reports received while time was not passing (the clock paused);
    # they apply at the next step.
    inputs_staged: bool = False


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

    def validate_inputs(self, inputs: CtcInputs) -> None:
        """Raise if ``step`` would reject these inputs. No side effects."""
        ...

    def stage_inputs(self, inputs: CtcInputs) -> None:
        """Take reports that arrive while no time passes (the clock is
        paused). They change nothing until the next ``step``, but the
        dispatcher's safety checks use them at once. Rejects what
        ``step`` would reject."""
        ...

    # Dispatcher actions from the CTC UI. Not cross-module inputs.

    def dispatch(self, train_id: str, line: str,
                 destination_block_id: str,
                 arrival_s: float | None = None) -> None:
        """Send a train toward a destination block on its line.

        A train that already has an order is rerouted: the new order
        replaces the old one. Refused (safety) into a closed, closing or
        failed block, and onto a line other than the train's own.
        """
        ...

    def cancel_dispatch(self, train_id: str) -> None:
        """Drop a train's dispatch order, if it has one."""
        ...

    def set_block_closed(self, line: str, block_id: str,
                         closed: bool) -> None:
        """Close a block for maintenance, or reopen it. Maintenance
        mode only. An occupied block closes once the train has left it;
        orders into the block are cancelled at once."""
        ...

    def set_switch(self, line: str, switch_id: str,
                   position: SwitchPosition) -> None:
        """Command a switch position. Maintenance mode only, and
        refused (safety) while the switch's block is occupied."""
        ...

    def release_switch(self, line: str, switch_id: str) -> None:
        """Drop the command for one switch, if there is one."""
        ...

    def set_maintenance_mode(self, active: bool) -> None:
        """Enter or leave maintenance mode; leaving it drops every
        switch command."""
        ...

    def set_clock_speedup(self, active: bool) -> None:
        """Command the shared clock to 10x (True) or 1x (False)."""
        ...

    def load_schedule(self, schedule: Schedule) -> None:
        """Replace the schedule; its runs are queued for dispatch."""
        ...
