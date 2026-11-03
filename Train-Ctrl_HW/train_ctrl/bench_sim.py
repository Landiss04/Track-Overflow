"""What the bench simulates in place of the rest of the system. No Qt.

The bench drives the controller the way the central harness does
(REQUIREMENTS.md M0): each tick it hands every train the input dict
read_inputs() takes, steps the fleet, and feeds the commands that come
back into this simulation. Nothing here is part of the controller: it
stands in for the Train Model (motion, Brake / Door / Light State,
cabin temperature, Murphy's failures) and the Track Model (Track
Signal, beacon, signal light, block changes), and the controller only
ever sees what outputs() returns.
"""

from __future__ import annotations

import math
from typing import Any

from .constants import (
    CABIN_DRIFT_FRACTION,
    CABIN_DRIFT_MAX_C,
    DEFAULT_CABIN_TEMP_C,
    EBRAKE_DECEL_MPS2,
    FAILURES,
    MASS_KG,
    MAX_FORCE_N,
    ROLLING_DECEL_MPS2,
    SERVICE_DECEL_MPS2,
    SETTLE_MPS,
    TICK_S,
    V_FLOOR_MPS,
)
from .state import TrainModelCommands

_BEACON = ("beacon_station", "beacon_side", "beacon_underground")

# read_inputs() key -> the attribute it sets here, for bench edits.
_EDITABLE = {
    "commanded_mps": "commanded_mps",
    "actual_mps": "actual_mps",
    "cabin_temp_c": "cabin_temp_c",
    "authority_blocks": "authority_blocks",
    "beacon_station": "beacon_station",
    "beacon_side": "beacon_side",
    "beacon_underground": "beacon_underground",
    "next_signal": "signal_light_ahead",
    "fb_doors_left": "door_left",
    "fb_doors_right": "door_right",
    "fb_interior_lights": "interior_lights",
    "fb_exterior_lights": "exterior_lights",
}


class SimTrain:
    """One train as the bench simulates it.

    The toy physics, in place of the Train Model:

        F = P / v     a = F / M     v = v + a dt

    No resistance term in normal running: a train with no power
    applied coasts forever, so the only ways down are the two brakes.
    An injected engine failure zeroes traction; an injected brake
    failure blocks the service brake only, and only then does rolling
    resistance act. An injected signal pickup failure sends null for
    commanded speed and authority, as the Train Model does.
    """

    def __init__(self) -> None:
        # Track Model stand-in: what the bench sends as the wayside's.
        self.commanded_mps = 0.0
        self.authority_blocks = 4
        self.beacon_station = ""
        self.beacon_side = "L"
        self.beacon_underground = False
        self.signal_light_ahead = "YELLOW"
        # The beacon is heard only near a station (truth beacon.md):
        # every tick while the bench says the train is at one, and
        # once after the bench edits it, as if a beacon were passed.
        self.at_station = False
        self._beacon_once = False

        # Train Model stand-in.
        self.actual_mps = 0.0
        self.accel_mps2 = 0.0
        self.cabin_temp_c = DEFAULT_CABIN_TEMP_C
        self.emergency_brake = False
        self.service_brake = False
        self.door_left = self.door_right = False
        self.interior_lights = self.exterior_lights = False
        # A passenger pull from the bench is reported for one tick;
        # how the real latch is released is open (OPEN_ISSUES.md #25).
        self._pull = False
        # Murphy's failures, which the controller has to detect.
        self.injected = {name: False for name in FAILURES}
        # Door and light commands are answered on their edge, so a
        # state the bench published stands until the next command.
        self._acted_doors: tuple[bool, bool] | None = None
        self._acted_lights: tuple[bool, bool] | None = None

    def outputs(self) -> dict[str, Any]:
        """This tick's signals to the controller, as from a harness."""
        pickup = self.injected["signal_pickup"]
        values = {
            "commanded_speed": None if pickup else self.commanded_mps,
            "authority_blocks": None if pickup else self.authority_blocks,
            "actual_speed": self.actual_mps,
            "emergency_brake_state": self.emergency_brake or self._pull,
            "service_brake_state": self.service_brake,
            "door_state": [self.door_left, self.door_right],
            "light_state": [self.interior_lights, self.exterior_lights],
            "cabin_temperature": self.cabin_temp_c,
            "signal_light_ahead": self.signal_light_ahead,
        }
        if self.at_station or self._beacon_once:
            values.update(beacon_station=self.beacon_station,
                          beacon_side=self.beacon_side,
                          beacon_underground=self.beacon_underground)
        return values

    def apply(self, staged: dict[str, Any]) -> None:
        """Take a bench edit, already checked by read_inputs()."""
        for key, value in staged.items():
            if key == "emergency_brake_state":
                self._pull = self._pull or bool(value)
            elif key in _EDITABLE:
                setattr(self, _EDITABLE[key], value)
        if any(key in staged for key in _BEACON):
            self._beacon_once = True

    def answer_next(self) -> None:
        """Answer the next door and light commands, changed or not.

        The driver pressed a tile, so the train acts on the command
        even if it is the one already sent: a state the bench
        published does not lock the driver out.
        """
        self._acted_doors = self._acted_lights = None

    def block_change(self) -> None:
        """The train enters the next block: one block less authority."""
        self.authority_blocks = max(0, self.authority_blocks - 1)

    def step(self, cmd: TrainModelCommands, dt: float = TICK_S) -> None:
        """Act on one tick's commands from the controller."""
        self._pull = False
        self._beacon_once = False
        service_works = not self.injected["brake"]
        power = 0.0 if self.injected["engine"] else cmd.power_w
        v = self.actual_mps
        force = min(MAX_FORCE_N, power / max(abs(v), V_FLOOR_MPS))
        a = force / MASS_KG
        decel = 0.0
        if cmd.emergency_brake:
            decel = EBRAKE_DECEL_MPS2
        elif service_works and cmd.service_brake:
            decel = SERVICE_DECEL_MPS2
        if decel:
            # A brake opposes the motion and never reverses it.
            a = -math.copysign(decel, v) if v else 0.0
        elif not service_works:
            # Resistance opposes the motion, holds the train at rest,
            # and never reverses it.
            a = (a - math.copysign(ROLLING_DECEL_MPS2, v) if v
                 else max(0.0, a - ROLLING_DECEL_MPS2))
        new_v = v + a * dt
        if v * new_v < 0.0:
            new_v = 0.0             # stopped, never reversed
        if abs(new_v) < SETTLE_MPS and power == 0.0:
            new_v = 0.0             # settle cleanly at a stand
        self.accel_mps2 = a
        self.actual_mps = new_v

        # Brake State: what is engaged, not what was commanded.
        self.emergency_brake = cmd.emergency_brake
        self.service_brake = cmd.service_brake and service_works

        # The Train Model's door interlock is commented out on
        # development, so Door State follows Door Command; the
        # controller is the interlock (REQUIREMENTS.md M6).
        if cmd.door_command != self._acted_doors:
            self.door_left, self.door_right = cmd.door_command
            self._acted_doors = cmd.door_command
        if cmd.light_command != self._acted_lights:
            self.interior_lights, self.exterior_lights = cmd.light_command
            self._acted_lights = cmd.light_command

        drift = cmd.temperature_setpoint_c - self.cabin_temp_c
        self.cabin_temp_c += max(
            -CABIN_DRIFT_MAX_C,
            min(CABIN_DRIFT_MAX_C, drift * CABIN_DRIFT_FRACTION),
        )
