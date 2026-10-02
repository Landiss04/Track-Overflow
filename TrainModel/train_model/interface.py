"""Train Model boundary contract.

These are the Train Model's own boundary types. The central harness owns one
pure mapping function per producer-to-consumer edge, translating other
modules' types into these and back. Other modules' struct layouts do not
appear here.

Field names carry their backend units, per ``truth/conventions/units.md``:
temperature in degrees Celsius, grade in degrees, and authority as a block ID.
"""

from dataclasses import dataclass
from typing import Literal, Protocol


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

@dataclass(frozen=True, slots=True)
class TrainConfig:
    """Vehicle constants. Bombardier FLEXITY 2 (Blackpool), 5-module consist.

    Primitives only. Everything derived is a property, so the set stays
    consistent if a primitive changes.
    """

    # Vehicle (datasheet)
    m_empty_kg: float = 40_900.0
    m_loaded_kg: float = 56_700.0           # at 4 pass./m^2
    length_m: float = 32.2
    width_m: float = 2.65
    height_m: float = 3.42
    capacity: int = 222                     # 74 seated + 148 standing
    v_max_mps: float = 70.0 / 3.6

    # Occupants (customer Q&A)
    passenger_mass_kg: float = 77.1107      # 170 lb
    n_crew: int = 5                         # 1 per car x 5 modules

    # Propulsion
    p_max_w: float = 480_000.0              # 4 x 120 kW, provisional

    # Rated performance, all at 2/3 load (datasheet)
    ref_load_fraction: float = 2.0 / 3.0
    accel_ref_mps2: float = 0.5
    decel_service_mps2: float = 1.2
    decel_emergency_mps2: float = 2.73

    # Environment
    c_rr: float = 0.002                     # rolling resistance, assumed
    g_mps2: float = 9.81

    # Disembark RNG, one generator instance per train
    seed: int = 0

    @property
    def m_ref_kg(self) -> float:
        """2/3-load reference mass: 2/3 of the datasheet load, 51,433 kg."""
        load_kg = self.m_loaded_kg - self.m_empty_kg
        return self.m_empty_kg + self.ref_load_fraction * load_kg

    @property
    def f_max_n(self) -> float:
        return self.m_ref_kg * self.accel_ref_mps2

    @property
    def f_service_n(self) -> float:
        return self.m_ref_kg * self.decel_service_mps2

    @property
    def f_emergency_n(self) -> float:
        return self.m_ref_kg * self.decel_emergency_mps2


# --------------------------------------------------------------------------- #
# Shared value types
# --------------------------------------------------------------------------- #

PlatformSide = Literal["L", "R"]


@dataclass(frozen=True, slots=True)
class Beacon:
    """Received near stations only. Serialized form must fit 128 characters."""

    station_name: str
    platform_side: PlatformSide
    underground: bool


@dataclass(frozen=True, slots=True)
class FailureState:
    """Independent and composable. All three true at once is valid."""

    engine: bool = False
    signal_pickup: bool = False
    brake: bool = False


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #

@dataclass(frozen=True, slots=True)
class ControllerCommands:
    """From the Train Controller, every tick."""

    power_cmd_w: float
    service_brake: bool
    # Controller path only; a passenger pull is internal.
    emergency_brake: bool
    interior_lights: bool
    exterior_lights: bool
    door_left_open: bool
    door_right_open: bool
    temp_setpoint_c: float
    announcement: str


@dataclass(frozen=True, slots=True)
class TrackInfo:
    """From the Track Model, every tick.

    Terrain; unaffected by signal pickup failure.
    """

    block_id: str
    grade_deg: float                # positive uphill
    elevation_m: float
    speed_limit_mps: float
    polarity: bool
    # Station in this block; None where there is none. Boarding needs one.
    station_name: str | None = None


@dataclass(frozen=True, slots=True)
class TrackSignal:
    """Track circuit data. Ignored while signal pickup has failed."""

    commanded_speed_mps: float
    # Block the train may travel up to.
    authority_block_id: str


@dataclass(frozen=True, slots=True)
class TrackInputs:
    """From the Track Model, every tick."""

    track_info: TrackInfo
    track_signal: TrackSignal
    beacon: Beacon | None           # None when not over a beacon
    # 0 except when boarding; never exceeds last reported capacity.
    passengers_boarded: int


@dataclass(frozen=True, slots=True)
class TrainModelInputs:
    controller: ControllerCommands
    track: TrackInputs


# --------------------------------------------------------------------------- #
# Outputs
# --------------------------------------------------------------------------- #

@dataclass(frozen=True, slots=True)
class ControllerOutputs:
    """To the Train Controller."""

    actual_speed_mps: float
    # Brake State, bool[2]: emergency then service. Engaged, not
    # commanded: a brake failure blocks only the service brake.
    emergency_brake_active: bool    # controller or passenger
    service_brake_active: bool
    door_left_open: bool
    door_right_open: bool
    interior_lights_on: bool
    exterior_lights_on: bool
    cabin_temp_c: float
    # Passed through; zeros or stale under pickup failure, open.
    commanded_speed_mps: float
    authority_block_id: str | None  # passed through; None = no authority
    # Passed through from TrackInfo, provisional.
    speed_limit_mps: float
    beacon: Beacon | None           # between-beacon behaviour open
    failures: FailureState


@dataclass(frozen=True, slots=True)
class TrackOutputs:
    """To the Track Model."""

    block_id: str
    offset_m: float                # reference point on the 32.2 m train open
    actual_speed_mps: float         # negative during rollback
    # True on the tick polarity reverses; table says int.
    block_changed: bool
    # Remaining, computed after the disembark draw.
    passenger_capacity: int


@dataclass(frozen=True, slots=True)
class TrainModelOutputs:
    controller: ControllerOutputs
    track: TrackOutputs


@dataclass(frozen=True, slots=True)
class TrainModelSnapshot:
    """Full observable state for the Train Model UI."""

    mass_kg: float
    acceleration_mps2: float
    velocity_mps: float
    n_crew: int
    n_passengers: int
    passenger_ebrake_pulled: bool
    outputs: TrainModelOutputs
    inputs: TrainModelInputs | None = None
    elapsed_s: float = 0.0


# --------------------------------------------------------------------------- #
# Module contract
# --------------------------------------------------------------------------- #

class TrainModel(Protocol):
    """Constructed as TrainModel(config: TrainConfig)."""

    config: TrainConfig

    def step(self, dt: float, inputs: TrainModelInputs) -> TrainModelOutputs:
        """Advance one tick.

        dt is fixed by the harness and must be finite and positive.
        Numeric inputs must be finite; power must be nonnegative.
        Invalid inputs are rejected before any state is changed.
        """
        ...

    def snapshot(self) -> TrainModelSnapshot:
        """Current state for display. No side effects."""
        ...

    # Train Model UI actions. Not cross-module inputs.

    def set_failures(self, failures: FailureState) -> None:
        """Murphy fault injection."""
        ...

    def pull_passenger_emergency_brake(self) -> None:
        ...

    def clear_passenger_brake_for_test(self) -> None:
        """Test harness override only; normal UI release is undecided."""
        ...
