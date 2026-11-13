"""Observable state and light simulation for the Train Controller cab.

The driver's cab (page 4) binds to one ``TrainControllerState``. State
is held in SI units (``common/Units.md`` backend units) and converted to
mph, ft and deg F only when the snapshot is built for QML.

The simulation is deliberately light: a fixed-rate tick eases the speed
toward the target, applies brake deceleration, and counts distances
down. There is no PI control law and no Train Model physics yet; Kp and
Ki are stored and displayed only. Deviations from the wireframe are
recorded in ``TrainController/README.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from train_controller.units import (
    c_to_f,
    f_to_c,
    ft_to_m,
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

TEMP_SETPOINT_MIN_F = 60
TEMP_SETPOINT_MAX_F = 80
ANNOUNCEMENT_DURATION_S = 5.0
GAIN_STEPS: tuple[float, ...] = (0.001, 0.010, 0.100, 1.000)


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


class BlockKind(Enum):
    """What the driver needs to know about a block ahead."""

    CLEAR = "clear"
    STATION = "station"
    STOP = "stop"
    CLOSED = "closed"


@dataclass(frozen=True)
class TrackBlock:
    """One block on the route, located by where it starts."""

    block_id: str
    start_m: float
    kind: BlockKind
    station_name: str = ""


# Seeded to match the page 4 wireframe. Distances are measured from the
# train's starting position at the entry of GREEN I.
_SEED_ROUTE: tuple[TrackBlock, ...] = (
    TrackBlock("GREEN I", ft_to_m(0), BlockKind.CLEAR),
    TrackBlock("GREEN J", ft_to_m(1320), BlockKind.CLEAR),
    TrackBlock("GREEN K", ft_to_m(2640), BlockKind.CLEAR),
    TrackBlock("GREEN L", ft_to_m(4224), BlockKind.STATION, "[STATION]"),
    TrackBlock("GREEN M", ft_to_m(10032), BlockKind.STOP),
    TrackBlock("GREEN N", ft_to_m(11352), BlockKind.CLOSED),
)


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

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.train_id = "T-214"
        self.line = "Green Line"
        self.route = _SEED_ROUTE
        self.authority_end_m = ft_to_m(10032)

        self.clock_s = 21 * 3600 + 26 * 60 + 35
        self.mode = DriveMode.MANUAL
        self.user_role = UserRole.DRIVER
        self.signal_aspect = SignalAspect.GREEN

        self.distance_travelled_m = 0.0
        self.current_speed_mps = mph_to_mps(32)
        self.speed_limit_mps = mph_to_mps(45)
        self.ctc_speed_mps = mph_to_mps(35)
        self.target_speed_mps = mph_to_mps(35)
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
        elif self.service_brake or self._must_stop_for_authority(dt):
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

        # Euler position step; the train never passes its authority.
        self.distance_travelled_m = min(
            self.authority_end_m,
            self.distance_travelled_m + self.current_speed_mps * dt,
        )
        if self.authority_left_m <= 0:
            self.current_speed_mps = 0.0

        drift_c = CABIN_TEMP_DRIFT_F_PER_S * dt * 5 / 9
        self.cabin_temp_c = _approach(
            self.cabin_temp_c, self.temp_setpoint_c, drift_c)

        if self._announcement_left_s > 0:
            self._announcement_left_s -= dt
            if self._announcement_left_s <= 0:
                self.announcement = ""

        self.snapshotChanged.emit()

    def _must_stop_for_authority(self, dt: float) -> bool:
        # Brake once the service-brake stopping distance, plus one tick
        # of travel, reaches the end of the authority.
        speed_mps = self.current_speed_mps
        braking_distance_m = speed_mps ** 2 / (2 * SERVICE_DECEL_MPS2)
        return self.authority_left_m <= braking_distance_m + speed_mps * dt

    # ------------------------------------------------------------------
    # Derived values
    # ------------------------------------------------------------------

    @property
    def is_stopped(self) -> bool:
        """Whether the train is at a standstill."""
        return self.current_speed_mps < 0.01

    @property
    def any_door_open(self) -> bool:
        """Whether either side's doors are open."""
        return self.left_door_open or self.right_door_open

    @property
    def authority_left_m(self) -> float:
        """Distance remaining to the stop point."""
        return max(0.0, self.authority_end_m - self.distance_travelled_m)

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

    @property
    def current_block_index(self) -> int:
        """Index in the route of the block the train occupies."""
        index = 0
        for position, block in enumerate(self.route):
            if block.start_m <= self.distance_travelled_m:
                index = position
        return index

    def next_station(self) -> TrackBlock | None:
        """Return the next station block ahead, if any."""
        for block in self.route[self.current_block_index:]:
            if block.kind is BlockKind.STATION:
                if block.start_m >= self.distance_travelled_m:
                    return block
        return None

    def platform_side(self) -> str:
        """Side the doors open at the next station: LEFT, RIGHT or ''."""
        # The beacon for the seeded station reports a left platform.
        return "LEFT" if self.next_station() is not None else ""

    def can_open_door(self, side: str) -> bool:
        """Whether the driver may open the doors on ``side`` now."""
        return self.is_stopped and self.platform_side() == side

    # ------------------------------------------------------------------
    # QML-facing snapshot
    # ------------------------------------------------------------------

    @Property("QVariantMap", notify=snapshotChanged)
    def snapshot(self) -> dict[str, Any]:
        """Every display value, in frontend units, rebuilt per change."""
        current_index = self.current_block_index
        current_block = self.route[current_index]
        next_block = (
            self.route[current_index + 1]
            if current_index + 1 < len(self.route) else None
        )
        station = self.next_station()
        station_distance_m = (
            station.start_m - self.distance_travelled_m
            if station is not None else None
        )

        return {
            "train_id": self.train_id,
            "train_ids": [self.train_id],
            "line": self.line,
            "clock": _format_clock(self.clock_s),
            "mode": self.mode.value,
            "user_role": self.user_role.value,
            "current_block": current_block.block_id,
            "next_block": next_block.block_id if next_block else "",
            "signal_aspect": self.signal_aspect.value,
            "current_speed_mph": round(mps_to_mph(self.current_speed_mps)),
            "speed_limit_mph": round(mps_to_mph(self.speed_limit_mps)),
            "ctc_speed_mph": round(mps_to_mph(self.ctc_speed_mps)),
            "target_speed_mph": self._target_mph(),
            "target_set_by": self._displayed_source().value,
            "authority_ft": round(m_to_ft(self.authority_left_m)),
            "is_stopped": self.is_stopped,
            "service_brake": self.service_brake,
            "emergency_brake": self.emergency_brake,
            "next_station": station.station_name if station else "",
            "station_distance_ft": (
                round(m_to_ft(station_distance_m))
                if station_distance_m is not None else -1
            ),
            "station_arrival": self._arrival_text(station_distance_m),
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
        """Blocks from the current one onward, farthest first."""
        current_index = self.current_block_index
        tiles = []
        for index, block in enumerate(self.route):
            if index < current_index:
                continue
            is_current = index == current_index
            if is_current:
                state, note = "current", f"{self.train_id} IS HERE"
            elif block.kind is BlockKind.CLOSED:
                state, note = "closed", "CLOSED"
            elif block.kind is BlockKind.STOP:
                state, note = "stop", "STOP IN THIS BLOCK"
            elif block.kind is BlockKind.STATION:
                state, note = "station", block.station_name
            else:
                state, note = "clear", "CLEAR"
            # Distances past the stop point are not useful to the driver.
            show_distance = (
                not is_current and block.kind is not BlockKind.CLOSED)
            distance_ft = (
                round(m_to_ft(block.start_m - self.distance_travelled_m))
                if show_distance else -1
            )
            tiles.append({
                "block_id": block.block_id,
                "state": state,
                "note": note,
                "distance_ft": distance_ft,
            })
        tiles.reverse()
        return tiles

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
        limit_mph = round(mps_to_mph(self.speed_limit_mps))
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
        """Latch the emergency brake. Only the office can release it."""
        self.emergency_brake = True
        self.snapshotChanged.emit()

    @Slot()
    def simulateOfficeRelease(self) -> None:
        """Test-only stand-in for the office releasing the e-brake."""
        self.emergency_brake = False
        self.snapshotChanged.emit()

    @Slot()
    def toggleLeftDoor(self) -> None:
        """Open or close the left doors, if allowed."""
        if self.left_door_open:
            self.left_door_open = False
        elif self.can_open_door("LEFT"):
            self.left_door_open = True
        self.snapshotChanged.emit()

    @Slot()
    def toggleRightDoor(self) -> None:
        """Open or close the right doors, if allowed."""
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
        station = self.next_station()
        if station is None:
            self.announcement = "No station ahead."
        else:
            self.announcement = (
                f"Next stop {station.station_name}. Doors open on the "
                f"{self.platform_side().lower()}."
            )
        self._announcement_left_s = ANNOUNCEMENT_DURATION_S
        self.snapshotChanged.emit()

    @Slot(str)
    def setMode(self, mode: str) -> None:
        """Switch between Manual and Automatic speed control."""
        self.mode = DriveMode(mode)
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

    @Slot()
    def applyGains(self) -> None:
        """Put the pending Kp and Ki into use."""
        if self.user_role is not UserRole.ENGINEER:
            return
        self.kp_in_use = self.kp_pending
        self.ki_in_use = self.ki_pending
        self.snapshotChanged.emit()
