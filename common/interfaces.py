"""
Shared interface contracts for every module in the PAAC train control system.

Architecture signal flow (from Final Project vF.pdf, p. 8-9):
  CTC Office
      |-- Suggested Speed, Authority -------> SW Track Controller
      |<- Block Occupancy, Switch State ----- SW Track Controller
  SW Track Controller
      |-- Commanded Speed, Authority,
      |   Switch Positions, Lights ---------> Track Model
      |<- Block Occupancy, Switch State,
      |   Crossing State, Failures --------- Track Model
  Track Model
      |-- Commanded Speed, Authority,
      |   Beacon (track circuit) -----------> SW Train Controller
      |<- Train Position ------------------- Train Model
  SW Train Controller
      |-- Power Cmd, Brake Cmd, Doors,
      |   Lights, Temp Setpoint -----------> Train Model
      |<- Current Speed, Failures --------- Train Model
  MBO Overlay
      |-- Safe Authority ------------------> CTC Office
      |<- Train Position ------------------- Train Model
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Shared data types
# ---------------------------------------------------------------------------

class FailureMode(Enum):
    NONE = auto()
    BROKEN_RAIL = auto()
    TRACK_CIRCUIT = auto()
    POWER_FAILURE = auto()


class SwitchPosition(Enum):
    NORMAL = auto()
    REVERSE = auto()


@dataclass
class TrainPosition:
    block_id: str
    offset_m: float         # metres into the block from entry point


@dataclass
class Beacon:
    next_station: str
    platform_side: str      # "left" or "right"
    underground: bool


@dataclass
class TrackSignal:
    """Encoded track-circuit signal the Train Controller reads off the rail."""
    commanded_speed_mps: float
    authority_m: float
    beacon: Optional[Beacon] = None


@dataclass
class BlockState:
    block_id: str
    occupied: bool
    failure: FailureMode
    speed_limit_mps: float
    grade_deg: float
    elevation_m: float


@dataclass
class SwitchState:
    switch_id: str
    position: SwitchPosition


@dataclass
class CrossingState:
    crossing_id: str
    gate_closed: bool
    lights_on: bool


@dataclass
class TrainState:
    speed_mps: float
    acceleration_mps2: float
    position: TrainPosition
    passenger_count: int
    engine_failed: bool
    brake_failed: bool
    signal_pickup_failed: bool


# ---------------------------------------------------------------------------
# Module interfaces
# ---------------------------------------------------------------------------

class ITrackModel(ABC):
    """
    Physical track environment.

    Inputs  – commands from SW Track Controller, position from Train Model.
    Outputs – TrackSignal to SW Train Controller, occupancy/state to CTC and
              SW Track Controller.
    """

    @abstractmethod
    def update(self, dt: float) -> None:
        """Advance the simulation by dt seconds."""

    # -- Inputs from SW Track Controller --

    @abstractmethod
    def set_commanded_signal(
        self,
        block_id: str,
        speed_mps: float,
        authority_m: float,
    ) -> None:
        """Store the commanded speed and authority for a specific block."""

    @abstractmethod
    def set_switch_position(
        self, switch_id: str, position: SwitchPosition
    ) -> None:
        """Command a switch to normal or reverse."""

    @abstractmethod
    def set_signal_light(self, block_id: str, color: str) -> None:
        """Set the wayside signal light colour for a block."""

    # -- Input from Train Model --

    @abstractmethod
    def report_train_position(self, position: TrainPosition) -> None:
        """Receive the current train position for occupancy detection."""

    # -- Outputs to SW Train Controller --

    @abstractmethod
    def get_track_signal(self, block_id: str) -> TrackSignal:
        """Return the track-circuit signal present on a given block."""

    # -- Outputs to SW Track Controller / CTC --

    @abstractmethod
    def get_block_states(self) -> list[BlockState]:
        """Return occupancy, failure, and physical properties for every block."""

    @abstractmethod
    def get_switch_states(self) -> list[SwitchState]:
        """Return the current position of every switch."""

    @abstractmethod
    def get_crossing_states(self) -> list[CrossingState]:
        """Return the state of every railway crossing."""

    # -- Failure injection (test / Murphy UI) --

    @abstractmethod
    def inject_failure(self, block_id: str, mode: FailureMode) -> None:
        """Inject a failure on the specified block."""

    @abstractmethod
    def clear_failure(self, block_id: str) -> None:
        """Clear any active failure on the specified block."""

    # -- Environment --

    @abstractmethod
    def set_temperature_f(self, temp_f: float) -> None:
        """Set ambient temperature (°F) for track-heater logic."""


class ITrainModel(ABC):
    """
    Physical train simulator (Newton's-law point-mass model).

    Inputs  – commands from SW Train Controller, track signal from Track Model.
    Outputs – TrainState (speed, position, etc.) to SW Train Controller, MBO,
              and position to Track Model.
    """

    @abstractmethod
    def update(self, dt: float) -> None:
        """Advance the simulation by dt seconds."""

    # -- Inputs from SW Train Controller --

    @abstractmethod
    def set_power_command(self, power_w: float) -> None:
        """Set engine power output in watts."""

    @abstractmethod
    def set_service_brake(self, active: bool) -> None:
        """Engage or release the service brake."""

    @abstractmethod
    def set_emergency_brake(self, active: bool) -> None:
        """Engage or release the emergency brake (passenger-accessible)."""

    @abstractmethod
    def set_doors(self, left_open: bool, right_open: bool) -> None:
        """Command the left and right platform doors."""

    @abstractmethod
    def set_lights(self, cabin_on: bool, headlights_on: bool) -> None:
        """Control cabin and headlight state."""

    @abstractmethod
    def set_temperature_setpoint_f(self, temp_f: float) -> None:
        """Set the cabin temperature setpoint in °F."""

    # -- Input from Track Model --

    @abstractmethod
    def receive_track_signal(self, signal: TrackSignal) -> None:
        """Accept the current track-circuit signal."""

    @abstractmethod
    def receive_block_state(self, state: BlockState) -> None:
        """Accept grade, elevation and speed limit for the occupied block."""

    # -- Outputs --

    @abstractmethod
    def get_state(self) -> TrainState:
        """Return the full train state snapshot."""

    # -- Failure injection (Murphy UI) --

    @abstractmethod
    def inject_engine_failure(self) -> None:
        """Simulate engine failure."""

    @abstractmethod
    def inject_brake_failure(self) -> None:
        """Simulate brake failure."""

    @abstractmethod
    def inject_signal_pickup_failure(self) -> None:
        """Simulate loss of track-circuit pickup."""


class ISwTrainController(ABC):
    """
    Vital software train controller.

    Inputs  – driver setpoint, track signal from Track Model.
    Outputs – power/brake/door/light commands to Train Model.
    """

    @abstractmethod
    def update(self, dt: float) -> None:
        """Run one control tick."""

    # -- Driver inputs --

    @abstractmethod
    def set_driver_setpoint_mps(self, speed_mps: float) -> None:
        """Accept the operator's requested speed."""

    @abstractmethod
    def activate_emergency_brake(self) -> None:
        """Passenger or driver emergency brake activation."""

    # -- From Track Model --

    @abstractmethod
    def receive_track_signal(self, signal: TrackSignal) -> None:
        """Accept the decoded track-circuit signal."""

    # -- From Train Model (feedback) --

    @abstractmethod
    def receive_train_state(self, state: TrainState) -> None:
        """Accept the current train state for control-law calculation."""


class ISwTrackController(ABC):
    """
    Vital software PLC that controls wayside equipment.

    Inputs  – suggested authority from CTC, block states from Track Model.
    Outputs – commanded signals and switch positions to Track Model.
    """

    @abstractmethod
    def update(self, dt: float) -> None:
        """Run one PLC scan cycle."""

    # -- From CTC Office --

    @abstractmethod
    def receive_suggestion(
        self,
        block_id: str,
        suggested_speed_mps: float,
        authority_m: float,
    ) -> None:
        """Accept a speed/authority suggestion from the CTC for a block."""

    # -- From Track Model --

    @abstractmethod
    def receive_block_states(self, states: list[BlockState]) -> None:
        """Accept current occupancy and failure data for all blocks."""

    @abstractmethod
    def receive_switch_states(self, states: list[SwitchState]) -> None:
        """Accept current switch positions from the Track Model."""

    # -- Outputs to Track Model --

    @abstractmethod
    def get_commanded_signal(self, block_id: str) -> tuple[float, float]:
        """Return (commanded_speed_mps, authority_m) for a block."""

    @abstractmethod
    def get_switch_commands(self) -> list[SwitchState]:
        """Return the desired switch positions after PLC logic runs."""

    @abstractmethod
    def get_signal_light_commands(self) -> dict[str, str]:
        """Return mapping of block_id -> light colour."""


class ICtcOffice(ABC):
    """
    Centralized Traffic Control office.

    Inputs  – block/switch states from SW Track Controller, authority from MBO.
    Outputs – suggested speed and authority per block to SW Track Controller.
    """

    @abstractmethod
    def update(self, dt: float) -> None:
        """Run one dispatcher tick."""

    # -- From SW Track Controller --

    @abstractmethod
    def receive_block_states(self, states: list[BlockState]) -> None:
        """Accept occupancy reports from the wayside."""

    @abstractmethod
    def receive_switch_states(self, states: list[SwitchState]) -> None:
        """Accept switch positions from the wayside."""

    # -- From MBO --

    @abstractmethod
    def receive_mbo_authority(self, train_id: str, authority_m: float) -> None:
        """Accept a safe moving-block authority from the MBO overlay."""

    # -- Dispatcher actions --

    @abstractmethod
    def dispatch_train(self, train_id: str, destination_block: str) -> None:
        """Dispatch a train towards a destination block."""

    @abstractmethod
    def close_block(self, block_id: str) -> None:
        """Close a block for maintenance."""

    @abstractmethod
    def open_block(self, block_id: str) -> None:
        """Re-open a previously closed block."""

    # -- Outputs to SW Track Controller --

    @abstractmethod
    def get_suggestion(self, block_id: str) -> tuple[float, float]:
        """Return (suggested_speed_mps, authority_m) for a block."""


class IMboOverlay(ABC):
    """
    Moving Block Overlay — computes safe stopping distance per train.

    Inputs  – real-time position from each Train Model.
    Outputs – safe authority per train to CTC Office.
    """

    @abstractmethod
    def update(self, dt: float) -> None:
        """Recalculate safe authorities for all tracked trains."""

    # -- From Train Model --

    @abstractmethod
    def report_train_position(
        self, train_id: str, position: TrainPosition, speed_mps: float
    ) -> None:
        """Receive a vital position/speed report from a train."""

    # -- Outputs to CTC --

    @abstractmethod
    def get_safe_authority(self, train_id: str) -> float:
        """Return the safe stopping distance in metres for the given train."""
