"""Per-train state, and the commands sent to the Train Model. No Qt."""

from __future__ import annotations

from dataclasses import dataclass, field

from .constants import (
    CLOCK_START_S,
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

    # System time as last received: seconds since midnight of the
    # first simulated day, as utils/system_clock.py counts it, from
    # the harness or the bench clock (REQUIREMENTS.md M11).
    time_s: float = CLOCK_START_S

    # Authority: how many blocks the train may still enter before it
    # has to stop, as the Track Model reports it, and the block it
    # stops at. A count and an ID, not a measurement, so neither is
    # ever converted. The control law does not track blocks: the
    # count it is sent is how far it may go, used as given: it
    # changes only when a new count arrives (REQUIREMENTS.md M16).
    authority_blocks: int = 4
    authority_target: str = "GREEN K"

    power_w: float = 0.0
    service_brake: bool = False
    service_request: bool = False
    emergency_brake: bool = False

    # Failures this controller has detected, one flag per subsystem,
    # latched until the test bench clears them.
    failures: dict = field(
        default_factory=lambda: {name: False for name in FAILURES})

    # State reported back by the Train Model, as opposed to what this
    # controller commanded (truth door-state, light-state,
    # brake-state), from the Train Model or the bench's simulation.
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
    # What the Announcement signal carries: the station name while an
    # announcement plays, empty otherwise.
    announcement: str = ""

    cabin_temp_c: float = DEFAULT_CABIN_TEMP_C
    target_temp_c: float = DEFAULT_TARGET_TEMP_C
    doors_left: bool = False
    doors_right: bool = False
    interior_lights: bool = True
    exterior_lights: bool = True

    next_signal: str = "YELLOW"

    kp: float = DEFAULT_KP
    ki: float = DEFAULT_KI


@dataclass(frozen=True)
class TrainModelCommands:
    """What this controller sends the Train Model, in SI.

    One field per truth signal: power-command, service-brake-command,
    emergency-brake-command, door-command, light-command,
    temperature-setpoint and announcement. The central harness (D005)
    maps these onto the Train Model's own boundary types.
    """

    power_w: float
    service_brake: bool
    emergency_brake: bool
    door_command: tuple[bool, bool]         # (left, right)
    light_command: tuple[bool, bool]        # (interior, exterior)
    temperature_setpoint_c: float
    announcement: str
