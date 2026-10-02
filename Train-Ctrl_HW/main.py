"""HW Train Controller — driver / engineer console (ECE1140 Team 3).

Entry point for the module. Python owns hardware, control and state;
QML owns every pixel. The two meet at three context properties:

    theme        design tokens, from the shared ui/theme.py
    controller   ConsoleBackend: one snapshot out, slots in
    trainList    the trains the console can be pointed at

    HardwareInterface   lever + e-stop in, power + brakes out
    ControllerCore      PI speed law; safety enforced on a separate path
    ConsoleBackend      the Qt bridge; computes the snapshot, nothing else
    ui/                 the view; reads the snapshot, computes nothing

Run:

    python main.py                               stub hardware
    python main.py --real                        SPI + GPIO on the Pi
    python main.py --check [--shots DIR]         offscreen self-test

Units follow documents/units.md: the state and the control law are
metric SI, the operator reads imperial with power in kilowatts, and
the conversion happens once, in the snapshot ConsoleBackend builds.

Reusable QML components are not in this module. They live in the shared
repository-root ui/ library and are imported from each view with a
relative path; see ui/README.md in this folder for the depth table.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# The shared design tokens and window scaling live beside the shared QML
# components at the repository root, so put that root on the import path.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SHARED_UI = _REPO_ROOT / "ui"
sys.path.insert(0, str(_REPO_ROOT))

from PySide6.QtCore import (  # noqa: E402
    Property, QObject, QTime, QTimer, QUrl, Signal, Slot,
)
from PySide6.QtGui import QFont, QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow  # noqa: E402,F401  grabWindow()

from ui.aspect_lock import install_window_scaling  # noqa: E402
from ui.theme import build_theme  # noqa: E402

_MAIN_QML = Path(__file__).resolve().parent / "ui_parts" / "Main.qml"


def check_shared_library() -> bool:
    """Report, in words, a missing shared QML library.

    This module is a sibling of the repository-root ui/ folder and the
    views import it with a relative path. Moved out of the repository,
    every shared type goes unresolved and the window simply fails to
    load, so say so here instead.
    """
    if (_SHARED_UI / "ScaledWindow.qml").exists():
        return True
    print(f"Shared QML library not found at {_SHARED_UI}.\n"
          "This module has to sit beside it, in the repository root:\n"
          "    <repo>/ui/              shared components\n"
          "    <repo>/TrainControllerHW/main.py\n"
          "Copying ui/theme.py and ui/aspect_lock.py into this module\n"
          "satisfies the Python imports but not the QML ones.",
          file=sys.stderr)
    return False

CONTROL_HZ = 20
UI_HZ = 10
MAX_POWER_W = 120_000.0
ANNOUNCE_LOCKOUT_MS = 5000
GAINS_HANDOVER_MS = 1500

# ---------------------------------------------------------------- units
# documents/units.md. Everything stored, computed or passed across a
# module boundary is metric SI; everything the operator reads is
# imperial, except power, which is read in kilowatts. State and
# ControllerCore are SI throughout and never convert. ConsoleBackend is
# the display layer: every conversion in this program happens once, in
# the snapshot it hands to QML, and the views only round and format.
MPS_TO_MPH = 2.236936
M_TO_FT = 3.280840
MPS2_TO_FTPS2 = 3.280840
W_TO_KW = 0.001


def c_to_f(celsius: float) -> float:
    """Backend Celsius to displayed Fahrenheit."""
    return celsius * 9 / 5 + 32


def f_to_c(fahrenheit: float) -> float:
    """A Fahrenheit figure the operator set, back to Celsius."""
    return (fahrenheit - 32) * 5 / 9


#: Thermostat range, as the operator sets it (degrees F).
CABIN_MIN_F, CABIN_MAX_F = 60.0, 80.0

# --- plant model (toy, replaced by the Train Model) ---
MAX_ACCEL = 1.6         # m/s^2 at full power
DRAG_BASE = 0.30        # m/s^2 rolling resistance
DRAG_SPEED = 0.004      # m/s^2 per m/s, stands in for aero drag
SERVICE_DECEL = 1.2     # m/s^2
EBRAKE_DECEL = 2.7      # m/s^2
SERVICE_BAND = 0.15     # m/s over target before the service brake helps

# ---------------------------------------------------------------- DEMO ONLY
# Cycles the signal aspect so every state of the Next signal panel can be
# seen without the Wayside Controller connected. NOT real functionality.
# To remove: set DEMO_CYCLE_SIGNALS = False, or delete this constant and
# the _demo_cycle_signal method and its timer in ConsoleBackend.
DEMO_CYCLE_SIGNALS = True
DEMO_SIGNAL_PERIOD_MS = 3000
# -------------------------------------------------------------- END DEMO

ASPECTS = ["RED", "YELLOW", "GREEN", "SUPER GREEN"]
ASPECT_TEXT = {
    "RED": "Stop.",
    "YELLOW": "Slow down.",
    "GREEN": "Continue to cruise.",
    "SUPER GREEN": "All clear ahead.",
}

#: The trains this console can be pointed at. Replaced by the CTC roster.
TRAINS = [
    {"id": "T-114", "line": "GREEN LINE", "label": "T-114 \u00b7 GREEN LINE"},
    {"id": "T-142", "line": "GREEN LINE", "label": "T-142 \u00b7 GREEN LINE"},
    {"id": "R-301", "line": "RED LINE", "label": "R-301 \u00b7 RED LINE"},
]

# Tokens this console needs that the style guide does not define yet.
# Per guide section 1 a missing token is added to the guide first, then
# used; these are the open items, and they are listed in README.md.
#
#   size_hero    section 6.5 fixes telemetry at 28 px, which is right for
#                a dense readout but unreadable from a driving position.
#                The approved wireframe uses a much larger figure for the
#                four primary readouts. Contrast is unchanged: the same
#                --text-primary on --bg-sunken.
#   signal_*     a signal head has to read like a real signal head, so
#                the aspects are deliberately brighter than the semantic
#                --danger / --warning / --success. Super green is lighter
#                than green so the two never look alike.
#   brake_*      section 4.4 --danger is a deep signal red, right for
#                the emergency brake. The service brake is a routine
#                stop and must not read as the same control, so it is
#                the amber a cab brake handle uses. Contrast checked:
#                text-primary on brake_service is 11.2:1 (AAA).
#   scrim_*      the modal dim behind the gains dialog. QML has no
#                box-shadow, and section 5 defines no overlay token.
PENDING_TOKENS: dict[str, Any] = {
    "size_hero": 72,
    "brake_service": "#F2C037",
    "brake_service_active": "#D9A520",
    "signal_red": "#D62828",
    "signal_yellow": "#F2B90C",
    "signal_green": "#1E8E3E",
    "signal_super": "#4ADE80",
    "scrim_color": "#16202A",
    "scrim_opacity": 0.45,
}


def build_console_theme() -> dict[str, Any]:
    """Shared tokens plus the open items above, as one table."""
    theme = build_theme()
    theme.update(PENDING_TOKENS)
    return theme


# ================================================================ hardware
class HardwareInterface:
    """Stub hardware. Every I/O call in the program goes through here."""

    def read_lever(self) -> float:
        return 0.5

    def read_estop(self) -> bool:
        return False

    def write_power(self, w: float) -> None: ...

    def write_service_brake(self, on: bool) -> None: ...

    def write_emergency_brake(self, on: bool) -> None: ...

    def close(self) -> None: ...


class PiHardware(HardwareInterface):
    """Lever via SPI ADC, e-stop on GPIO.

    The only place spidev and gpiozero appear.
    """

    ADC_CHANNEL, ESTOP_PIN, SERVICE_PIN, EMERGENCY_PIN = 0, 17, 27, 22

    def __init__(self) -> None:
        import spidev
        from gpiozero import Button, OutputDevice
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 1_350_000
        self._estop = Button(self.ESTOP_PIN, pull_up=True)
        self._service = OutputDevice(self.SERVICE_PIN)
        self._emergency = OutputDevice(self.EMERGENCY_PIN)

    def read_lever(self) -> float:
        r = self.spi.xfer2([1, (8 + self.ADC_CHANNEL) << 4, 0])
        return (((r[1] & 3) << 8) + r[2]) / 1023.0

    def read_estop(self) -> bool:
        return bool(self._estop.is_pressed)

    def write_service_brake(self, on: bool) -> None:
        self._service.value = bool(on)

    def write_emergency_brake(self, on: bool) -> None:
        self._emergency.value = bool(on)

    def close(self) -> None:
        self.spi.close()


# ================================================================ state
@dataclass
class State:
    """Everything the console shows or the control law needs."""

    train_id: str = "T-114"
    line: str = "GREEN LINE"
    manual: bool = False

    actual_mps: float = 11.6
    commanded_mps: float = 24.6
    target_mps: float = 21.5
    speed_limit_mps: float = 31.3
    accel_mps2: float = 0.0
    # Authority itself is a block ID, not a measurement (units.md,
    # identifiers.md): authority_block below is the block the train may
    # run to. This is the distance left to the end of it, which is what
    # the safety path counts down and what the console shows.
    stop_distance_m: float = 20000.0

    power_w: float = 0.0
    service_brake: bool = False
    service_request: bool = False
    emergency_brake: bool = False
    faults: list = field(default_factory=list)

    cabin_temp_c: float = 21.1
    target_temp_c: float = 22.2
    doors_left: bool = False
    doors_right: bool = False
    lights: bool = True
    headlights: bool = True

    # The block the train is to stop at. An ID, never a distance.
    stop_block: str = "A"
    next_station: str = "CENTRAL"
    arrives: str = "14:46"
    platform_side: str = "right"
    next_signal: str = "YELLOW"
    signal_block: str = "GREEN J"
    authority_block: str = "GREEN J"
    current_block: str = "GREEN I"

    kp: float = 30000.0     # W per m/s of error
    ki: float = 6000.0      # W per (m/s x s) of accumulated error


# ================================================================ control
class ControllerCore:
    """The PI speed law, the safety path and the toy plant.

    No Qt, no view: this class is what the hardware demo has to prove
    correct, and it runs unchanged whether or not a console is open.
    """

    def __init__(self, hw: HardwareInterface) -> None:
        self.hw = hw
        self.state = State()
        self.dt = 1.0 / CONTROL_HZ
        self.integral = 0.0
        self.last_reasons: list[str] = []
        # The controller is inert until an engineer commissions the gains.
        self.armed = False

    def step(self) -> None:
        if not self.armed:
            return
        s = self.state
        if not s.manual:
            s.target_mps = min(s.commanded_mps, s.speed_limit_mps)

        error = s.target_mps - s.actual_mps
        self.integral += error * self.dt
        power = s.kp * error + s.ki * self.integral

        if power > MAX_POWER_W:
            power = MAX_POWER_W
            self.integral -= error * self.dt
        elif power < 0.0:
            power = 0.0
            self.integral -= error * self.dt

        s.power_w = power
        s.service_brake = (error < -SERVICE_BAND) or s.service_request

        self.enforce_safety()

        self.hw.write_power(s.power_w)
        self.hw.write_service_brake(s.service_brake)
        self.hw.write_emergency_brake(s.emergency_brake)
        self._plant()

    def enforce_safety(self) -> None:
        """Run after the PI law and override it.

        Gains change how the train drives; they can never change whether
        it stops.
        """
        s = self.state
        reasons = []
        if self.hw.read_estop():
            reasons.append("DRIVER E-STOP")
        if s.actual_mps > s.speed_limit_mps * 1.05:
            reasons.append("OVER SPEED LIMIT")
        if s.stop_distance_m <= 0.0:
            reasons.append("AUTHORITY EXCEEDED")
        if s.faults:
            reasons.append("EQUIPMENT FAULT")
        if reasons or s.emergency_brake:
            s.emergency_brake = True
            s.power_w = 0.0
            s.service_brake = True
            self.integral = 0.0
        self.last_reasons = reasons

    def engage_emergency(self) -> None:
        """Engage now, without waiting for the next control tick.

        Guide section 7 calls the emergency brake immediate, so the
        safety path runs and the outputs are written on the press
        rather than up to one control period later.
        """
        self.state.emergency_brake = True
        self.enforce_safety()
        self.hw.write_power(self.state.power_w)
        self.hw.write_service_brake(self.state.service_brake)
        self.hw.write_emergency_brake(True)

    def release_emergency(self) -> bool:
        """Latching. Release only when stopped with nothing still wrong."""
        s = self.state
        s.emergency_brake = False
        self.enforce_safety()
        if abs(s.actual_mps) < 0.1 and not self.last_reasons:
            s.emergency_brake = False
            return True
        s.emergency_brake = True
        return False

    def set_target_mps(self, mps: float) -> None:
        """Set the driver's target, in m/s, capped at the speed limit."""
        s = self.state
        if s.manual:
            s.target_mps = max(0.0, min(mps, s.speed_limit_mps))

    def _plant(self) -> None:
        """Toy physics until the Train Model is wired in.

        Rolling and aerodynamic drag matter here: without them a coasting
        train holds its speed forever, so it can never shed the last mph
        below the point where the controller stops commanding power.
        """
        s = self.state
        v = s.actual_mps
        drag = (DRAG_BASE + DRAG_SPEED * v) if v > 0 else 0.0
        a = (s.power_w / MAX_POWER_W) * MAX_ACCEL - drag
        if s.emergency_brake:
            a = -EBRAKE_DECEL
        elif s.service_brake:
            a = -SERVICE_DECEL
        if v <= 0.0 and a < 0.0:
            a = 0.0
        s.accel_mps2 = a
        s.actual_mps = max(0.0, v + a * self.dt)
        if s.actual_mps < 0.12 and s.target_mps < 0.12:
            s.actual_mps = 0.0          # settle cleanly at a stand
        s.stop_distance_m = max(
            0.0, s.stop_distance_m - s.actual_mps * self.dt)
        drift = s.target_temp_c - s.cabin_temp_c
        s.cabin_temp_c += max(-0.011, min(0.011, drift * 0.01))


# ================================================================ bridge
class ConsoleBackend(QObject):
    """What QML sees: one snapshot out, one slot per operator action.

    Every rule about who may do what lives here, not in the view. The
    view mirrors the rules by disabling controls, but a slot that is
    called anyway still refuses.
    """

    snapshotChanged = Signal()

    #: Roles, by the index the Operator toggle uses. -1 is signed out.
    ROLES = ("driver", "engineer")

    def __init__(self, core: ControllerCore,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.core = core
        self.operator: str = ""         # "" | "driver" | "engineer"
        self.gains_locked = False
        self.engineer_available = True
        self.announcing = False
        self.brake_note = ""
        self.gains_note = ""
        self.elapsed = QTime(0, 0, 0)
        self.train_index = 0

        self._control = QTimer(self)
        self._control.timeout.connect(self.core.step)
        self._control.start(int(1000 / CONTROL_HZ))

        self._ui = QTimer(self)
        self._ui.timeout.connect(self._tick)
        self._ui.start(int(1000 / UI_HZ))

        # ------------- DEMO ONLY: delete this block to remove ----------
        if DEMO_CYCLE_SIGNALS:
            self._demo = QTimer(self)
            self._demo.timeout.connect(self._demo_cycle_signal)
            self._demo.start(DEMO_SIGNAL_PERIOD_MS)
        # ---------------------------------------------- END DEMO -------

    # ------------------------------------------------------- read side
    @property
    def signed_in(self) -> bool:
        return self.operator != ""

    @property
    def can_drive(self) -> bool:
        """The driver may act only in Manual; Automatic locks the console.

        The emergency brake is the exception and stays live for any
        signed-in operator, in either mode (guide section 7).
        """
        return self.operator == "driver" and self.core.state.manual

    @Property("QVariantList", constant=True)
    def trains(self) -> list[dict[str, Any]]:
        """The roster the train selector shows."""
        return list(TRAINS)

    @Property("QVariantMap", notify=snapshotChanged)
    def snapshot(self) -> dict[str, Any]:
        """Every value the views read, rebuilt once per UI tick."""
        s = self.core.state
        return {
            "train_id": s.train_id,
            "line": s.line,
            "train_index": self.train_index,
            "operator": self.operator,
            "operator_index": (self.ROLES.index(self.operator)
                               if self.signed_in else -1),
            "signed_in": self.signed_in,
            "manual": s.manual,
            "mode_label": "Manual" if s.manual else "Automatic",
            "can_drive": self.can_drive,
            "armed": self.core.armed,
            "engineer_available": self.engineer_available,
            "gains_locked": self.gains_locked,
            "gains_note": self.gains_note,
            "clock": self.elapsed.toString("HH:mm:ss"),

            # Converted here and nowhere else. Keys carry the unit the
            # operator sees, so a reader can tell which side of the line
            # a value is on at a glance.
            "actual_mph": s.actual_mps * MPS_TO_MPH,
            "commanded_mph": s.commanded_mps * MPS_TO_MPH,
            "target_mph": s.target_mps * MPS_TO_MPH,
            "limit_mph": s.speed_limit_mps * MPS_TO_MPH,
            "accel_ftps2": s.accel_mps2 * MPS2_TO_FTPS2,
            "dial_hint": self._dial_hint(),
            "speed_source": "Driver" if s.manual else "From CTC",

            "power_kw": s.power_w * W_TO_KW,
            "max_power_kw": MAX_POWER_W * W_TO_KW,
            "service_brake": s.service_brake,
            "service_request": s.service_request,
            "emergency_brake": s.emergency_brake,
            "brake_note": self.brake_note,
            "faulted": bool(s.faults),

            # Identifiers, so they are shown as they are. The console
            # names the block to stop at; it does not count down a
            # distance, because authority is not a measurement.
            "stop_block": s.stop_block,
            "authority_block": s.authority_block,
            "current_block": s.current_block,

            "cabin_temp_f": c_to_f(s.cabin_temp_c),
            "target_temp_f": c_to_f(s.target_temp_c),
            "doors_left": s.doors_left,
            "doors_right": s.doors_right,
            "lights": s.lights,
            "headlights": s.headlights,

            "next_station": s.next_station.title(),
            "arrives": s.arrives,
            "platform_side": s.platform_side,
            "announcing": self.announcing,
            "announce_label": self._announce_label(),

            "next_signal": s.next_signal,
            "signal_index": ASPECTS.index(s.next_signal),
            "signal_text": ASPECT_TEXT[s.next_signal],
            "signal_block": s.signal_block,

            "kp": s.kp,
            "ki": s.ki,
        }

    def _dial_hint(self) -> str:
        if not self.core.armed:
            return "Waiting for the engineer to set the control gains."
        if self.core.state.manual:
            return "Drag the dial to set your target speed."
        return "Set by the CTC. Switch to Manual to take control."

    def _announce_label(self) -> str:
        if self.announcing:
            return "Announcing\u2026"
        if self.operator == "driver" and not self.core.state.manual:
            return "Announced automatically"
        return "Announce next station"

    # ------------------------------------------------------ write side
    @Slot(int)
    def selectOperator(self, index: int) -> None:
        """Sign in as driver (0) or engineer (1), or out (-1).

        The engineer role is spent once the gains are committed: the
        option stays visible but selecting it is refused, never hidden
        (guide section 8).
        """
        if index == 1 and not self.engineer_available:
            self._publish()
            return
        self.operator = self.ROLES[index] if 0 <= index < 2 else ""
        if self.operator == "engineer":
            self.gains_note = ""
        self._publish()

    @Slot(bool)
    def setManual(self, manual: bool) -> None:
        if not self.signed_in:
            return
        self.core.state.manual = manual
        self._publish()

    @Slot(str)
    def selectTrain(self, train_id: str) -> None:
        """Point the console at another train, by the id the roster uses."""
        if not self.signed_in:
            return
        for index, train in enumerate(TRAINS):
            if train["id"] == train_id:
                self.train_index = index
                self.core.state.train_id = train["id"]
                self.core.state.line = train["line"]
                break
        self._publish()

    @Slot(float)
    def setTargetMph(self, mph: float) -> None:
        """The dial speaks mph; the core is told m/s."""
        if not self.can_drive:
            return
        self.core.set_target_mps(mph / MPS_TO_MPH)
        self._publish()

    @Slot()
    def toggleEmergencyBrake(self) -> None:
        """One control engages and releases.

        Engagement is immediate and unconfirmed, the one exception the
        style guide grants (section 7). Release is refused unless the
        train is stopped and the reason is gone.
        """
        if not self.signed_in:
            return
        s = self.core.state
        if not s.emergency_brake:
            self.core.engage_emergency()
            self.brake_note = ("Emergency brake engaged. "
                               "Release it from the same control.")
        elif self.core.release_emergency():
            self.brake_note = ""
        else:
            why = (", ".join(self.core.last_reasons).lower()
                   or "the train is still moving")
            self.brake_note = f"Cannot release: {why}."
        self._publish()

    @Slot()
    def toggleServiceBrake(self) -> None:
        if not self.can_drive:
            return
        self.core.state.service_request = not self.core.state.service_request
        self._publish()

    @Slot(int)
    def setTargetTemp(self, fahrenheit: int) -> None:
        """The thermostat speaks Fahrenheit; the cabin is stored in C."""
        if not self.can_drive:
            return
        clamped = max(CABIN_MIN_F, min(CABIN_MAX_F, float(fahrenheit)))
        self.core.state.target_temp_c = f_to_c(clamped)
        self._publish()

    @Slot(str, bool)
    def setDoor(self, side: str, open_: bool) -> None:
        if not self.can_drive:
            return
        if side == "left":
            self.core.state.doors_left = open_
        else:
            self.core.state.doors_right = open_
        self._publish()

    @Slot(bool)
    def setLights(self, on: bool) -> None:
        if not self.can_drive:
            return
        self.core.state.lights = on
        self._publish()

    @Slot(bool)
    def setHeadlights(self, on: bool) -> None:
        if not self.can_drive:
            return
        self.core.state.headlights = on
        self._publish()

    @Slot()
    def announce(self) -> None:
        if not self.can_drive or self.announcing:
            return
        self.announcing = True
        QTimer.singleShot(ANNOUNCE_LOCKOUT_MS, self._announce_done)
        self._publish()

    def _announce_done(self) -> None:
        self.announcing = False
        self._publish()

    @Slot(float, float)
    def commissionGains(self, kp: float, ki: float) -> None:
        """Commission the gains once, at start-up, and start the run.

        Gains are frozen afterwards and the engineer role is handed back
        to the driver a moment later, so the confirmation can be read.
        """
        if self.gains_locked or self.operator != "engineer":
            return
        if not (math.isfinite(kp) and math.isfinite(ki)):
            self.gains_note = "Kp and Ki must be numbers."
            self._publish()
            return
        s = self.core.state
        s.kp = max(0.0, kp)
        s.ki = max(0.0, ki)
        self.core.integral = 0.0
        self.core.armed = True
        self.gains_locked = True
        self.gains_note = (f"Set to Kp {s.kp:.0f}, Ki {s.ki:.0f}. "
                           "Fixed for this run.")
        QTimer.singleShot(GAINS_HANDOVER_MS, self._retire_engineer)
        self._publish()

    def _retire_engineer(self) -> None:
        """Close the gains dialog and hand the console to the driver."""
        self.engineer_available = False
        self.operator = "driver"
        self._publish()

    # ----------------------------------------------------------- ticks
    def _tick(self) -> None:
        if self.core.armed:
            self.elapsed = self.elapsed.addMSecs(int(1000 / UI_HZ))
        if self.core.state.emergency_brake and not self.brake_note:
            self.brake_note = ("Emergency brake engaged. "
                               "Release it from the same control.")
        self._publish()

    def _publish(self) -> None:
        self.snapshotChanged.emit()

    # ------------- DEMO ONLY: delete this method to remove -------------
    def _demo_cycle_signal(self) -> None:
        """Step the aspect RED -> YELLOW -> GREEN -> SUPER GREEN.

        Replaced by the real aspect from the Wayside Controller.
        """
        i = ASPECTS.index(self.core.state.next_signal)
        self.core.state.next_signal = ASPECTS[(i + 1) % len(ASPECTS)]
    # ------------------------------------------------ END DEMO --------


# ================================================================ check
def _settle(app: QGuiApplication, ms: int) -> None:
    """Run the event loop for ms, so the timers above actually tick."""
    end = QTime.currentTime().addMSecs(ms)
    while QTime.currentTime() < end:
        app.processEvents()


def run_check(app: QGuiApplication, window: Any, backend: ConsoleBackend,
              warnings: list[str], shots: Path | None) -> int:
    """Walk the console offscreen and report anything that went wrong.

    Exits non-zero if QML logged a warning or the console let an
    operator do something the rules forbid.
    """
    problems: list[str] = []

    def expect(condition: bool, what: str) -> None:
        if not condition:
            problems.append(what)

    if shots:
        shots.mkdir(parents=True, exist_ok=True)

    _settle(app, 200)
    expect(not backend.snapshot["signed_in"], "console opened signed in")
    expect(not backend.core.armed, "controller armed before commissioning")
    if shots:
        window.grabWindow().save(str(shots / "01-signed-out.png"))

    # Signed out, nothing drives.
    backend.setTargetMph(40)
    backend.toggleServiceBrake()
    expect(not backend.core.state.service_request,
           "service brake answered a signed-out operator")

    # Engineer commissions the gains once; the role is then spent.
    backend.selectOperator(1)
    _settle(app, 200)
    expect(backend.snapshot["operator"] == "engineer", "engineer sign-in failed")
    if shots:
        window.grabWindow().save(str(shots / "02-gains.png"))
    backend.commissionGains(42000, 7000)
    expect(backend.core.armed, "commissioning did not arm the controller")
    _settle(app, GAINS_HANDOVER_MS + 400)
    expect(backend.snapshot["operator"] == "driver", "console not handed over")
    expect(not backend.snapshot["engineer_available"],
           "engineer role still offered after commissioning")
    backend.selectOperator(1)
    expect(backend.snapshot["operator"] == "driver",
           "engineer role re-entered after the gains were set")
    backend.commissionGains(1, 1)
    expect(backend.core.state.kp == 42000, "gains changed after being locked")

    # Automatic locks the console; Manual hands it to the driver.
    expect(not backend.can_drive, "driver could act in Automatic")
    backend.setManual(True)
    expect(backend.can_drive, "Manual did not unlock the console")
    backend.setTargetMph(35)
    _settle(app, 1500)
    expect(backend.core.state.actual_mps > 0, "train never moved")
    if shots:
        window.grabWindow().save(str(shots / "03-driving.png"))

    # The emergency brake stops the train and latches until it is stopped.
    backend.toggleEmergencyBrake()
    expect(backend.core.state.power_w == 0.0, "power stayed on under e-brake")
    _settle(app, 200)
    if shots:
        window.grabWindow().save(str(shots / "04-ebrake.png"))
    backend.toggleEmergencyBrake()
    expect(backend.core.state.emergency_brake,
           "e-brake released while the train was moving")
    _settle(app, 9000)
    backend.toggleEmergencyBrake()
    expect(not backend.core.state.emergency_brake,
           "e-brake would not release at a stand")
    if shots:
        window.grabWindow().save(str(shots / "04-stopped.png"))

    # The numbers drawer renders and closes again.
    drawer = window.findChild(QObject, "numbersDrawer")
    expect(drawer is not None, "numbers drawer missing")
    if drawer is not None:
        drawer.setProperty("expanded", True)
        _settle(app, 300)
        if shots:
            window.grabWindow().save(str(shots / "05-numbers.png"))
        drawer.setProperty("expanded", False)

    # Announcements lock out for their duration.
    backend.announce()
    expect(backend.snapshot["announcing"], "announcement did not start")
    _settle(app, ANNOUNCE_LOCKOUT_MS + 400)
    expect(not backend.snapshot["announcing"], "announcement never cleared")

    for message in warnings:
        print(f"QML warning: {message}", file=sys.stderr)
    for problem in problems:
        print(f"Behaviour: {problem}", file=sys.stderr)
    print(f"{len(warnings)} QML warnings, {len(problems)} behaviour problems")
    return 1 if warnings or problems else 0


# ================================================================ main
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real", action="store_true",
                        help="drive the Pi hardware over SPI and GPIO")
    parser.add_argument("--check", action="store_true",
                        help="run offscreen, exercise the console, report")
    parser.add_argument("--shots", metavar="DIR",
                        help="with --check, save screenshots to DIR")
    return parser.parse_args()


def main() -> int:
    """Create the app, load the QML views, and run the event loop."""
    args = _parse_args()
    if args.check:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import qInstallMessageHandler

    warnings: list[str] = []
    if args.check:
        qInstallMessageHandler(
            lambda kind, context, message: warnings.append(message))

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Train Controller")

    theme = build_console_theme()
    base_font = QFont()
    base_font.setFamily(theme["ui_family"])
    base_font.setPixelSize(theme["size_body"])
    app.setFont(base_font)

    hw: HardwareInterface = PiHardware() if args.real else HardwareInterface()
    core = ControllerCore(hw)
    # Keep Python-side references so the objects are not garbage collected
    # while QML holds only C++ pointers to them.
    backend = ConsoleBackend(core)

    if not check_shared_library():
        return 1

    engine = QQmlApplicationEngine()
    # Qt logs QML errors through the message handler, which a debugger
    # usually swallows. Keep our own copy so a failed load explains
    # itself on stderr.
    qml_errors: list[str] = []
    engine.warnings.connect(
        lambda issues: qml_errors.extend(i.toString() for i in issues))
    context = engine.rootContext()
    if context is None:
        print("Failed to obtain the QML root context.", file=sys.stderr)
        return 1
    context.setContextProperty("theme", theme)
    context.setContextProperty("controller", backend)

    engine.load(QUrl.fromLocalFile(str(_MAIN_QML)))
    if not engine.rootObjects():
        print(f"Failed to load {_MAIN_QML}.", file=sys.stderr)
        for issue in qml_errors:
            print(f"  {issue}", file=sys.stderr)
        return 1

    window = engine.rootObjects()[0]
    aspect_lock = install_window_scaling(window)  # noqa: F841  keep alive

    if args.check:
        shots = Path(args.shots) if args.shots else None
        code = run_check(app, window, backend, warnings, shots)
        qInstallMessageHandler(None)
        del engine
        hw.close()
        return code

    exit_code = app.exec()
    # Tear down QML before the objects it binds to, so bindings do not
    # re-evaluate against deleted objects during shutdown.
    del engine
    hw.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())