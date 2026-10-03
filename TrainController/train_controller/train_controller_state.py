"""Observable state and light simulation for the Train Controller cab.

The driver's cab (page 4) binds to one ``TrainControllerState``. State
is held in backend units (``truth/conventions/units.md``) and converted
to mph, ft and deg F only when the snapshot is built for QML.

The route is real Green Line track, loaded from the layout file at
startup. Authority is a block ID: the train may travel to the end of
that block and no further.

The simulation is deliberately light: a fixed-rate tick eases the speed
toward the target, applies brake deceleration, and counts distances
down. There is no PI control law and no Train Model physics yet; Kp and
Ki are stored and displayed only. Deviations from the wireframe are
recorded in ``TrainController/README.md``.
"""

from __future__ import annotations

import math
from enum import Enum
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from train_controller.track_layout import (
    GREEN_LINE_PATH,
    TrackBlock,
    load_line,
    route_between,
)
from train_controller.units import (
    c_to_f,
    f_to_c,
    m_to_ft,
    mph_to_mps,
    mps_to_mph,
)

TICK_INTERVAL_MS = 1000

# Rates for the light simulation. The emergency figure is the usual
# light-rail emergency deceleration; the others are comfortable values.
EMERGENCY_DECEL_MPS2 = 2.73
SERVICE_DECEL_MPS2 = 1.2
EASE_ACCEL_MPS2 = 0.5
CABIN_TEMP_DRIFT_F_PER_S = 0.1
STANDSTILL_MPS = 0.01

# Station stops in Automatic mode. The dwell is fixed by truth D007 and
# includes the time to open and close the doors, so the doors close
# DOOR_CLOSE_LEAD_S before departure. The train stops mid-platform.
STATION_DWELL_S = 45.0
DOOR_CLOSE_LEAD_S = 5.0
STOP_TOLERANCE_M = 0.5

TEMP_SETPOINT_MIN_F = 60
TEMP_SETPOINT_MAX_F = 80
ANNOUNCEMENT_DURATION_S = 5.0
GAIN_STEPS: tuple[float, ...] = (0.001, 0.010, 0.100, 1.000)
TRACK_AHEAD_SLOTS = 6

# Seed scenario: T-214 entering block 62 (section J) with authority to
# the end of block 76 (section M). Stations on the way are GLENBURY (65)
# and DORMONT (73), both with a right-side platform.
SEED_TRAIN_ID = "T-214"
SEED_START_BLOCK = "62"
SEED_AUTHORITY_BLOCK = "76"
SEED_SPEED_MPH = 15
SEED_CTC_SPEED_MPH = 17


class DriveMode(Enum):
    """Who sets the speed target: the driver or the CTC."""

    MANUAL = "Manual"
    AUTOMATIC = "Automatic"


class UserRole(Enum):
    """Who is at the console. Engineers may tune the gains."""

    DRIVER = "Driver"
    ENGINEER = "Engineer"


class SpeedSource(Enum):
    """Origin of the current target speed."""

    DRIVER = "DRIVER"
    CTC = "CTC"


class SignalAspect(Enum):
    """Wayside signal aspect for the block being entered."""

    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    SUPER_GREEN = "SUPER GREEN"


def _format_clock(seconds: float) -> str:
    whole = int(seconds) % 86400
    return f"{whole // 3600:02d}:{whole % 3600 // 60:02d}:{whole % 60:02d}"


def _approach(value: float, target: float, max_step: float) -> float:
    if value < target:
        return min(target, value + max_step)
    return max(target, value - max_step)


class TrainControllerState(QObject):
    """Everything the cab view displays, and every driver action."""

    snapshotChanged = Signal()

    def __init__(
        self,
        layout_path: Path = GREEN_LINE_PATH,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        line_name, line_blocks = load_line(layout_path)
        self.train_id = SEED_TRAIN_ID
        self.line = f"{line_name} Line"
        self.authority_block_id = SEED_AUTHORITY_BLOCK
        self.route = route_between(
            line_blocks, SEED_START_BLOCK, SEED_AUTHORITY_BLOCK)

        # Distance along the route at which each block starts.
        self._block_starts_m: list[float] = []
        start_m = 0.0
        for block in self.route:
            self._block_starts_m.append(start_m)
            start_m += block.length_m
        # The train may travel to the end of its authority block.
        self.authority_end_m = start_m

        self.clock_s = 21 * 3600 + 26 * 60 + 35
        self.mode = DriveMode.MANUAL
        self.user_role = UserRole.DRIVER
        # The signal aspect is a Track Model output. Until the Track
        # Model is connected, GREEN is a placeholder for display.
        self.signal_aspect = SignalAspect.GREEN
        self.signal_aspect_from_track_model = False

        self.distance_travelled_m = 0.0
        self.current_speed_mps = mph_to_mps(SEED_SPEED_MPH)
        self.ctc_speed_mps = mph_to_mps(SEED_CTC_SPEED_MPH)
        self.target_speed_mps = mph_to_mps(SEED_CTC_SPEED_MPH)
        self.target_source = SpeedSource.DRIVER

        self.service_brake = False
        self.emergency_brake = False
        self.left_door_open = False
        self.right_door_open = False
        self.cabin_light = True
        self.headlight = True
        self.temp_setpoint_c = f_to_c(68)
        self.cabin_temp_c = f_to_c(71)

        self.announcement = ""
        self._announcement_left_s = 0.0

        self.dwell_left_s = 0.0
        self._served_stations: set[str] = set()

        self.gain_step = GAIN_STEPS[0]
        self.kp_pending = 12.4
        self.ki_pending = 0.85
        self.kp_in_use = 12.4
        self.ki_in_use = 0.85

        self._timer = QTimer(self)
        self._timer.setInterval(TICK_INTERVAL_MS)
        self._timer.timeout.connect(self._on_timer)

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the fixed-rate simulation tick."""
        self._timer.start()

    def _on_timer(self) -> None:
        self.step(TICK_INTERVAL_MS / 1000)

    def step(self, dt: float) -> None:
        """Advance the cab simulation by ``dt`` seconds."""
        self.clock_s += dt

        if self.emergency_brake:
            decel_mps2 = EMERGENCY_DECEL_MPS2
        elif self.service_brake or self._must_stop(dt):
            decel_mps2 = SERVICE_DECEL_MPS2
        else:
            decel_mps2 = 0.0

        if decel_mps2 > 0:
            self.current_speed_mps = max(
                0.0, self.current_speed_mps - decel_mps2 * dt)
        else:
            self.current_speed_mps = _approach(
                self.current_speed_mps,
                self.effective_target_mps,
                EASE_ACCEL_MPS2 * dt,
            )

        # Euler position step; the train never passes its stop point
        # (the end of authority, or a platform in Automatic mode).
        stop_point_m = self.stop_point_m
        self.distance_travelled_m = min(
            stop_point_m,
            self.distance_travelled_m + self.current_speed_mps * dt,
        )
        if stop_point_m - self.distance_travelled_m <= 0:
            self.current_speed_mps = 0.0

        self._update_station_stop(dt)

        drift_c = CABIN_TEMP_DRIFT_F_PER_S * dt * 5 / 9
        self.cabin_temp_c = _approach(
            self.cabin_temp_c, self.temp_setpoint_c, drift_c)

        if self._announcement_left_s > 0:
            self._announcement_left_s -= dt
            if self._announcement_left_s <= 0:
                self.announcement = ""

        self.snapshotChanged.emit()

    def _must_stop(self, dt: float) -> bool:
        # Brake once the service-brake stopping distance, plus one tick
        # of travel, reaches the stop point.
        speed_mps = self.current_speed_mps
        braking_distance_m = speed_mps ** 2 / (2 * SERVICE_DECEL_MPS2)
        distance_left_m = self.stop_point_m - self.distance_travelled_m
        return distance_left_m <= braking_distance_m + speed_mps * dt

    def _update_station_stop(self, dt: float) -> None:
        # Automatic mode: on arriving mid-platform, open the platform-side
        # doors and dwell; close the doors near the end of the dwell.
        if self.is_dwelling:
            self.dwell_left_s = max(0.0, self.dwell_left_s - dt)
            if self.dwell_left_s <= DOOR_CLOSE_LEAD_S:
                self.left_door_open = False
                self.right_door_open = False
            if self.dwell_left_s == 0:
                self._served_stations.add(self.current_block.block_id)
            return

        index = self._next_station_stop_index()
        if (
            self.mode is DriveMode.AUTOMATIC
            and index == self.current_block_index
            and self.is_stopped
            and not self.emergency_brake
            and self.stop_point_m - self.distance_travelled_m
            < STOP_TOLERANCE_M
        ):
            self.dwell_left_s = STATION_DWELL_S
            side = self.route[index].platform_side
            self.left_door_open = side in ("LEFT", "BOTH")
            self.right_door_open = side in ("RIGHT", "BOTH")
            self.announceAgain()

    def _platform_stop_m(self, index: int) -> float:
        block = self.route[index]
        return self._block_starts_m[index] + block.length_m / 2

    def _next_station_stop_index(self) -> int | None:
        # The next station not yet served whose platform stop point is
        # still ahead of (or at) the train.
        for index in range(self.current_block_index, len(self.route)):
            block = self.route[index]
            if (
                block.is_station
                and block.block_id not in self._served_stations
                and self._platform_stop_m(index)
                >= self.distance_travelled_m - STOP_TOLERANCE_M
            ):
                return index
        return None

    # ------------------------------------------------------------------
    # Derived values
    # ------------------------------------------------------------------

    @property
    def is_stopped(self) -> bool:
        """Whether the train is at a standstill."""
        return self.current_speed_mps < STANDSTILL_MPS

    @property
    def any_door_open(self) -> bool:
        """Whether either side's doors are open."""
        return self.left_door_open or self.right_door_open

    @property
    def is_dwelling(self) -> bool:
        """Whether the train is in an automatic station dwell."""
        return self.dwell_left_s > 0

    @property
    def stop_point_m(self) -> float:
        """Where the train must next stop along the route.

        The end of the authority block, or in Automatic mode the middle
        of the next unserved station platform, whichever comes first.
        """
        stop_m = self.authority_end_m
        if self.mode is DriveMode.AUTOMATIC:
            index = self._next_station_stop_index()
            if index is not None:
                stop_m = min(stop_m, self._platform_stop_m(index))
        return stop_m

    @property
    def authority_left_m(self) -> float:
        """Distance remaining to the end of the authority block."""
        return max(0.0, self.authority_end_m - self.distance_travelled_m)

    @property
    def current_block_index(self) -> int:
        """Index in the route of the block the train occupies."""
        index = 0
        for position, start_m in enumerate(self._block_starts_m):
            if start_m <= self.distance_travelled_m:
                index = position
        return index

    @property
    def current_block(self) -> TrackBlock:
        """The block the train occupies."""
        return self.route[self.current_block_index]

    @property
    def speed_limit_mps(self) -> float:
        """Civil speed limit of the occupied block."""
        return self.current_block.speed_limit_mps

    @property
    def effective_target_mps(self) -> float:
        """The speed the train is actually allowed to approach."""
        if self.any_door_open:
            return 0.0
        if self.mode is DriveMode.AUTOMATIC:
            requested_mps = self.ctc_speed_mps
        else:
            requested_mps = self.target_speed_mps
        return min(requested_mps, self.speed_limit_mps)

    def next_station_index(self) -> int | None:
        """Route index of the occupied or next station block, if any."""
        for index in range(self.current_block_index, len(self.route)):
            if self.route[index].is_station:
                return index
        return None

    def platform_side(self) -> str:
        """Side the doors open at the next station, or ''."""
        index = self.next_station_index()
        return self.route[index].platform_side if index is not None else ""

    def can_open_door(self, side: str) -> bool:
        """Whether the driver may open the doors on ``side`` now.

        Only in Manual mode: in Automatic the controller opens the
        doors itself during the station dwell.
        """
        block = self.current_block
        return (
            self.mode is DriveMode.MANUAL
            and self.is_stopped
            and block.is_station
            and block.platform_side in (side, "BOTH")
        )

    @property
    def can_release_emergency_brake(self) -> bool:
        """Whether the driver may release the emergency brake now."""
        return self.emergency_brake and self.is_stopped

    # ------------------------------------------------------------------
    # QML-facing snapshot
    # ------------------------------------------------------------------

    @Property("QVariantMap", notify=snapshotChanged)
    def snapshot(self) -> dict[str, Any]:
        """Every display value, in display units, rebuilt per change."""
        current_index = self.current_block_index
        current_block = self.route[current_index]
        next_block = (
            self.route[current_index + 1]
            if current_index + 1 < len(self.route) else None
        )
        station_index = self.next_station_index()
        station = (
            self.route[station_index] if station_index is not None else None
        )
        station_distance_m = (
            max(0.0, self._block_starts_m[station_index]
                - self.distance_travelled_m)
            if station_index is not None else None
        )

        return {
            "train_id": self.train_id,
            "train_ids": [self.train_id],
            "line": self.line,
            "clock": _format_clock(self.clock_s),
            "mode": self.mode.value,
            "user_role": self.user_role.value,
            "current_block": current_block.block_id,
            "current_section": current_block.section,
            "next_block": next_block.block_id if next_block else "",
            "authority_block": self.authority_block_id,
            "signal_aspect": self.signal_aspect.value,
            "signal_aspect_source": (
                "track_model" if self.signal_aspect_from_track_model
                else "placeholder"
            ),
            "current_speed_mph": round(mps_to_mph(self.current_speed_mps)),
            "speed_limit_mph": round(mps_to_mph(self.speed_limit_mps)),
            "ctc_speed_mph": round(mps_to_mph(self.ctc_speed_mps)),
            "target_speed_mph": self._target_mph(),
            "target_set_by": self._displayed_source().value,
            "is_stopped": self.is_stopped,
            "service_brake": self.service_brake,
            "emergency_brake": self.emergency_brake,
            "can_release_emergency_brake": self.can_release_emergency_brake,
            "next_station": station.station_name if station else "",
            "station_block": station.block_id if station else "",
            "station_distance_ft": (
                round(m_to_ft(station_distance_m))
                if station_distance_m is not None else -1
            ),
            "station_arrival": self._arrival_text(station_distance_m),
            "at_station": current_block.is_station,
            "dwelling": self.is_dwelling,
            "dwell_left_s": math.ceil(self.dwell_left_s),
            "platform_side": self.platform_side(),
            "left_door": self.left_door_open,
            "right_door": self.right_door_open,
            "can_open_left": self.can_open_door("LEFT"),
            "can_open_right": self.can_open_door("RIGHT"),
            "cabin_light": self.cabin_light,
            "headlight": self.headlight,
            "temp_setpoint_f": round(c_to_f(self.temp_setpoint_c)),
            "cabin_temp_f": round(c_to_f(self.cabin_temp_c)),
            "announcement": self.announcement,
            "gain_step": self.gain_step,
            "gain_steps": list(GAIN_STEPS),
            "kp": self.kp_pending,
            "ki": self.ki_pending,
            "kp_in_use": self.kp_in_use,
            "ki_in_use": self.ki_in_use,
            "blocks": self._blocks_ahead(),
        }

    def _target_mph(self) -> int:
        if self.mode is DriveMode.AUTOMATIC:
            return round(mps_to_mph(self.ctc_speed_mps))
        return round(mps_to_mph(self.target_speed_mps))

    def _displayed_source(self) -> SpeedSource:
        if self.mode is DriveMode.AUTOMATIC:
            return SpeedSource.CTC
        return self.target_source

    def _arrival_text(self, station_distance_m: float | None) -> str:
        if station_distance_m is None or self.is_stopped:
            return ""
        eta_s = self.clock_s + station_distance_m / self.current_speed_mps
        return _format_clock(eta_s)[:5]

    def _blocks_ahead(self) -> list[dict[str, Any]]:
        """The occupied block and those ahead of it, farthest first."""
        current_index = self.current_block_index
        last_index = min(
            len(self.route), current_index + TRACK_AHEAD_SLOTS)
        tiles = []
        for index in range(current_index, last_index):
            block = self.route[index]
            is_current = index == current_index
            distance_ft = (
                -1 if is_current else round(m_to_ft(
                    self._block_starts_m[index] - self.distance_travelled_m))
            )
            tiles.append({
                "block_id": block.block_id,
                "section": block.section,
                "occupancy": "occupied" if is_current else "free",
                "station": block.station_name,
                "platform_side": block.platform_side,
                "distance_ft": distance_ft,
                "is_authority": block.block_id == self.authority_block_id,
            })
        tiles.reverse()
        return tiles

    # ------------------------------------------------------------------
    # Track Model inputs
    # ------------------------------------------------------------------

    def receive_signal_aspect(self, aspect: str) -> None:
        """Accept the signal aspect for the block ahead.

        The Track Model produces this value; the central harness will
        call this method with it. It is deliberately not a QML slot,
        because the driver cannot set a wayside signal. The aspect is
        displayed only and does not change speed, braking or authority.
        Raise ``ValueError`` for an aspect that is not recognised.
        """
        self.signal_aspect = SignalAspect(aspect)
        self.signal_aspect_from_track_model = True
        self.snapshotChanged.emit()

    # ------------------------------------------------------------------
    # Driver actions
    # ------------------------------------------------------------------

    @Slot()
    def slower(self) -> None:
        """Lower the driver's target speed by 1 mph."""
        self._nudge_target_mph(-1)

    @Slot()
    def faster(self) -> None:
        """Raise the driver's target speed by 1 mph, up to the limit."""
        self._nudge_target_mph(+1)

    def _nudge_target_mph(self, delta_mph: int) -> None:
        if self.mode is not DriveMode.MANUAL:
            return
        # Floor, so the target never rounds up past the block's limit.
        limit_mph = math.floor(mps_to_mph(self.speed_limit_mps))
        target_mph = round(mps_to_mph(self.target_speed_mps)) + delta_mph
        target_mph = max(0, min(limit_mph, target_mph))
        self.target_speed_mps = mph_to_mps(target_mph)
        self.target_source = SpeedSource.DRIVER
        self.snapshotChanged.emit()

    @Slot()
    def useCtcTarget(self) -> None:
        """Adopt the CTC's commanded speed as the target."""
        if self.mode is not DriveMode.MANUAL:
            return
        self.target_speed_mps = self.ctc_speed_mps
        self.target_source = SpeedSource.CTC
        self.snapshotChanged.emit()

    @Slot(bool)
    def setServiceBrake(self, engaged: bool) -> None:
        """Engage or release the service brake."""
        self.service_brake = engaged
        self.snapshotChanged.emit()

    @Slot()
    def pullEmergencyBrake(self) -> None:
        """Latch the emergency brake."""
        self.emergency_brake = True
        self.snapshotChanged.emit()

    @Slot()
    def releaseEmergencyBrake(self) -> None:
        """Release the emergency brake, once the train has stopped."""
        if not self.can_release_emergency_brake:
            return
        self.emergency_brake = False
        self.snapshotChanged.emit()

    @Slot()
    def toggleLeftDoor(self) -> None:
        """Open or close the left doors, if allowed.

        Ignored during an automatic station dwell, which runs the doors.
        """
        if self.is_dwelling:
            return
        if self.left_door_open:
            self.left_door_open = False
        elif self.can_open_door("LEFT"):
            self.left_door_open = True
        self.snapshotChanged.emit()

    @Slot()
    def toggleRightDoor(self) -> None:
        """Open or close the right doors, if allowed.

        Ignored during an automatic station dwell, which runs the doors.
        """
        if self.is_dwelling:
            return
        if self.right_door_open:
            self.right_door_open = False
        elif self.can_open_door("RIGHT"):
            self.right_door_open = True
        self.snapshotChanged.emit()

    @Slot()
    def cooler(self) -> None:
        """Lower the cabin temperature setpoint by 1 deg F."""
        self._nudge_setpoint_f(-1)

    @Slot()
    def warmer(self) -> None:
        """Raise the cabin temperature setpoint by 1 deg F."""
        self._nudge_setpoint_f(+1)

    def _nudge_setpoint_f(self, delta_f: int) -> None:
        setpoint_f = round(c_to_f(self.temp_setpoint_c)) + delta_f
        setpoint_f = max(TEMP_SETPOINT_MIN_F,
                         min(TEMP_SETPOINT_MAX_F, setpoint_f))
        self.temp_setpoint_c = f_to_c(setpoint_f)
        self.snapshotChanged.emit()

    @Slot(bool)
    def setCabinLight(self, on: bool) -> None:
        """Switch the cabin lights."""
        self.cabin_light = on
        self.snapshotChanged.emit()

    @Slot(bool)
    def setHeadlight(self, on: bool) -> None:
        """Switch the headlights."""
        self.headlight = on
        self.snapshotChanged.emit()

    @Slot()
    def announceAgain(self) -> None:
        """Replay the next-station announcement."""
        index = self.next_station_index()
        if index is None:
            self.announcement = "No station ahead."
        else:
            station = self.route[index]
            side = {
                "LEFT": "on the left",
                "RIGHT": "on the right",
                "BOTH": "on both sides",
            }.get(station.platform_side, "")
            self.announcement = (
                f"Next stop {station.station_name}. Doors open {side}.")
        self._announcement_left_s = ANNOUNCEMENT_DURATION_S
        self.snapshotChanged.emit()

    @Slot(str)
    def setMode(self, mode: str) -> None:
        """Switch between Manual and Automatic speed control.

        Leaving Automatic during a station dwell ends the dwell: the
        station counts as served and the doors stay as they are, under
        the driver's control.
        """
        new_mode = DriveMode(mode)
        if new_mode is DriveMode.MANUAL and self.is_dwelling:
            self._served_stations.add(self.current_block.block_id)
            self.dwell_left_s = 0.0
        self.mode = new_mode
        self.snapshotChanged.emit()

    @Slot(str)
    def setUser(self, role: str) -> None:
        """Switch the console user between Driver and Engineer."""
        self.user_role = UserRole(role)
        self.snapshotChanged.emit()

    # ------------------------------------------------------------------
    # Engineer actions (gains pop-up)
    # ------------------------------------------------------------------

    @Slot(float)
    def setGainStep(self, step: float) -> None:
        """Choose the increment used by the Kp and Ki steppers."""
        if self.user_role is not UserRole.ENGINEER:
            return
        self.gain_step = step
        self.snapshotChanged.emit()

    @Slot(int)
    def adjustKp(self, direction: int) -> None:
        """Step the pending Kp up (+1) or down (-1)."""
        if self.user_role is not UserRole.ENGINEER:
            return
        self.kp_pending = max(
            0.0, round(self.kp_pending + direction * self.gain_step, 3))
        self.snapshotChanged.emit()

    @Slot(int)
    def adjustKi(self, direction: int) -> None:
        """Step the pending Ki up (+1) or down (-1)."""
        if self.user_role is not UserRole.ENGINEER:
            return
        self.ki_pending = max(
            0.0, round(self.ki_pending + direction * self.gain_step, 3))
        self.snapshotChanged.emit()

    @Slot(float)
    def setKp(self, value: float) -> None:
        """Set the pending Kp to a typed value."""
        if self.user_role is not UserRole.ENGINEER:
            return
        self.kp_pending = max(0.0, round(value, 3))
        self.snapshotChanged.emit()

    @Slot(float)
    def setKi(self, value: float) -> None:
        """Set the pending Ki to a typed value."""
        if self.user_role is not UserRole.ENGINEER:
            return
        self.ki_pending = max(0.0, round(value, 3))
        self.snapshotChanged.emit()

    @Slot()
    def applyGains(self) -> None:
        """Put the pending Kp and Ki into use."""
        if self.user_role is not UserRole.ENGINEER:
            return
        self.kp_in_use = self.kp_pending
        self.ki_in_use = self.ki_pending
        self.snapshotChanged.emit()
