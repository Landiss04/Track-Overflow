"""Per-train state, and the commands sent to the Train Model. No Qt."""

from __future__ import annotations

from dataclasses import dataclass, field

from .constants import (
<<<<<<< HEAD
=======
    CLOCK_START_S,
>>>>>>> origin/Train_Ctrl_integration
    DEFAULT_CABIN_TEMP_C,
    DEFAULT_KI,
    DEFAULT_KP,
    DEFAULT_TARGET_TEMP_C,
    FAILURES,
)

@dataclass
class State:
    """Everything the console shows or the control law needs."""

    train_id: str = "T-114"
    line: str = "GREEN LINE"
    manual: bool = False

    actual_mps: float = 0.0
    commanded_mps: float = 0.0
    target_mps: float = 0.0
<<<<<<< HEAD
    accel_mps2: float = 0.0
=======

    # System time as last received: seconds since midnight of the
    # first simulated day, as utils/system_clock.py counts it, from
    # the harness or the bench clock (REQUIREMENTS.md M11).
    time_s: float = CLOCK_START_S
>>>>>>> origin/Train_Ctrl_integration

    # Authority: how many blocks the train may still enter before it
    # has to stop, as the Track Model reports it, and the block it
    # stops at. A count and an ID, not a measurement, so neither is
    # ever converted. The control law does not track blocks: the
<<<<<<< HEAD
    # count it is sent is how far it may go. Until the Track Model
    # sends that count, the toy plant spends it, one block per
    # BLOCK_LENGTH_M travelled, carrying the part-block here.
    authority_blocks: int = 4
    authority_target: str = "GREEN K"
    block_progress_m: float = 0.0
=======
    # count it is sent is how far it may go, used as given: it
    # changes only when a new count arrives (REQUIREMENTS.md M16).
    authority_blocks: int = 4
    authority_target: str = "GREEN K"
>>>>>>> origin/Train_Ctrl_integration

    power_w: float = 0.0
    service_brake: bool = False
    service_request: bool = False
    emergency_brake: bool = False

    # Failures this controller has detected, one flag per subsystem,
    # latched until the test bench clears them.
    failures: dict = field(
        default_factory=lambda: {name: False for name in FAILURES})
<<<<<<< HEAD
    # Failures injected into the toy plant from the bench (Murphy).
    # The controller never reads these; it has to detect them.
    injected: dict = field(
        default_factory=lambda: {name: False for name in FAILURES})

    # State reported back by the Train Model, as opposed to what this
    # controller commanded (truth door-state, light-state,
    # brake-state). With no Train Model attached the toy plant stands
    # in for it, and the bench can publish them too.
=======

    # State reported back by the Train Model, as opposed to what this
    # controller commanded (truth door-state, light-state,
    # brake-state), from the Train Model or the bench's simulation.
>>>>>>> origin/Train_Ctrl_integration
    fb_doors_left: bool = False
    fb_doors_right: bool = False
    fb_interior_lights: bool = False
    fb_exterior_lights: bool = False
    fb_emergency_brake: bool = False
    fb_service_brake: bool = False

    # Beacon: three fields, near a station only (truth beacon.md).
    beacon_station: str = ""
    beacon_side: str = "L"
    beacon_underground: bool = False
<<<<<<< HEAD
    # What the Announcement signal carries: the station name while an
    # announcement plays, empty otherwise.
=======
    # What the Announcement signal carries: the announcement while it
    # plays, empty otherwise (REQUIREMENTS.md M7).
>>>>>>> origin/Train_Ctrl_integration
    announcement: str = ""

    cabin_temp_c: float = DEFAULT_CABIN_TEMP_C
    target_temp_c: float = DEFAULT_TARGET_TEMP_C
    doors_left: bool = False
    doors_right: bool = False
<<<<<<< HEAD
    interior_lights: bool = True
    exterior_lights: bool = True
=======
    # A train spawns with nothing on; the first tick sets the lights
    # from the time of day (REQUIREMENTS.md M8).
    interior_lights: bool = False
    exterior_lights: bool = False
>>>>>>> origin/Train_Ctrl_integration

    next_signal: str = "YELLOW"

    kp: float = DEFAULT_KP
    ki: float = DEFAULT_KI


@dataclass(frozen=True)
class TrainModelCommands:
    """What this controller sends the Train Model, in SI.

    One field per truth signal: power-command, service-brake-command,
    emergency-brake-command, door-command, light-command,
<<<<<<< HEAD
    temperature-setpoint, announcement and passenger-brake-release.
    The central harness (D005) maps these onto the Train Model's own
    boundary types.
=======
    temperature-setpoint and announcement. The central harness (D005)
    maps these onto the Train Model's own boundary types.
>>>>>>> origin/Train_Ctrl_integration
    """

    power_w: float
    service_brake: bool
    emergency_brake: bool
    door_command: tuple[bool, bool]         # (left, right)
    light_command: tuple[bool, bool]        # (interior, exterior)
    temperature_setpoint_c: float
    announcement: str
<<<<<<< HEAD
    # One-shot: true on the tick after the driver releases the
    # emergency brake, which releases a passenger pull with it.
    passenger_brake_release: bool = False
=======
>>>>>>> origin/Train_Ctrl_integration
