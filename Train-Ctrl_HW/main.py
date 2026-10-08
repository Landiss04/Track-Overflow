"""HW Train Controller — driver / engineer console (ECE1140 Team 3).

Entry point for the module. Python owns the control law and the
state; QML owns every pixel. The two meet at two context
properties:

    theme        design tokens, from the shared ui/theme.py
    controller   ConsoleBackend: one snapshot out, slots in

    ControllerCore      PI speed law; safety enforced on a separate path
    ConsoleBackend      the Qt bridge; computes the snapshot only
    ui_parts/           the view; reads the snapshot, computes nothing

Run, with the project virtual environment's interpreter
(truth conventions/toolchain.md):

    python main.py                         the driver's console
    python main.py --test                  the Train Model bench
    python main.py --both                  both windows, one backend
    python main.py --check [--shots DIR]   offscreen self-test

The console and the bench are separate windows with no way to
navigate between them: the home page launches one or the other. They
share a controller only when one process opens both, which is what
--both is for and how the bench drives the console.

Units follow truth conventions/units.md: the state and the control
law are metric SI, the operator reads imperial with power in
kilowatts, and the conversion happens once, in the snapshot
ConsoleBackend builds.

Reusable QML components are not in this module. They live in the
shared repository-root ui/ library and are imported from each view
with a relative path; see ui/README.md for the depth table.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    Property,
    QObject,
    QTime,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
# Imported for its side effect: it registers QQuickWindow, so the
# windows QML creates expose grabWindow() to the self-check.
from PySide6.QtQuick import QQuickWindow  # noqa: F401

# The shared design tokens and window scaling live beside the shared
# QML components at the repository root, so that root has to be on the
# import path before they can be imported.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SHARED_UI = _REPO_ROOT / "ui"
sys.path.insert(0, str(_REPO_ROOT))

from check import check_snapshot_contract, run_check  # noqa: E402
from ui.aspect_lock import install_window_scaling  # noqa: E402
from ui.theme import build_theme  # noqa: E402

_UI_DIR = Path(__file__).resolve().parent / "ui_parts"
_CONSOLE_QML = _UI_DIR / "ConsoleWindow.qml"
_TEST_QML = _UI_DIR / "TestWindow.qml"

CONTROL_HZ = 20
UI_HZ = 10
# The Flexity 2 data sheet's power figure, taken as the whole car's.
#
# Worth knowing what it costs. The same sheet quotes 0.5 m/s^2 from 0
# to 70 km/h, and 0.5 m/s^2 at 70 km/h on a 2/3-load car needs
# F x v = 500 kW. At 120 kW the car pulls its rated acceleration
# only to about 10 mph and tails off from there, taking roughly a
# minute and a half to reach 70 km/h. The sheet's two figures cannot
# both hold; this is the one the team picked.
MAX_POWER_W = 120_000.0
ANNOUNCE_LOCKOUT_MS = 5000
GAINS_HANDOVER_MS = 1500

# ---------------------------------------------------------------- units
# truth conventions/units.md. Everything stored, computed or passed
# across a module boundary is metric SI; everything the operator
# reads is imperial, except power, which is read in kilowatts. State
# and ControllerCore are SI throughout and never convert.
# ConsoleBackend is the display layer: every conversion in this
# program happens once, in the snapshot it hands to QML, and the
# views only round and format.
MPS_TO_MPH = 2.236936
M_TO_FT = 3.280840
W_TO_KW = 0.001
KMH_PER_MPS = 3.6


def c_to_f(celsius: float) -> float:
    """Convert a backend Celsius figure to displayed Fahrenheit."""
    return celsius * 9 / 5 + 32


def f_to_c(fahrenheit: float) -> float:
    """Convert a Fahrenheit figure the operator set back to Celsius."""
    return (fahrenheit - 32) * 5 / 9


#: Thermostat range, as the operator sets it (degrees F).
CABIN_MIN_F, CABIN_MAX_F = 60.0, 80.0
#: Where a new train's cabin starts, and what it is set to (Celsius).
DEFAULT_CABIN_TEMP_C = 21.1
DEFAULT_TARGET_TEMP_C = 22.2
# The toy cabin closes a hundredth of the gap each control tick,
# capped so a large step still warms or cools gradually.
CABIN_DRIFT_FRACTION = 0.01
CABIN_DRIFT_MAX_C = 0.011

# --- plant model (toy, replaced by the Train Model) ---
# The control law commands power, and the train turns power into
# motion the way the module diagram does:
#
#     F = P / v        a = F / M        v = v + a dt
#
# F = P / v is undefined at a stand, so the division uses a floor
# speed; below it the train pulls its full tractive effort, which is
# what a real train does from rest.
# Blackpool Flexity 2 data sheet: 0.5 m/s^2 medium acceleration from
# 0 to 70 km/h, 1.2 m/s^2 on the service brake, 2.73 on the
# emergency brake, 70 km/h maximum. Mass is 40.9 t empty and 56.7 t
# at 4 pass./m^2, and the acceleration figure is quoted at 2/3 load,
# so the plant runs at that mass.
MASS_KG = 51_433.0
MAX_ACCEL_MPS2 = 0.5            # and the car will not exceed it
MAX_FORCE_N = MASS_KG * MAX_ACCEL_MPS2
# The data sheet's 70 km/h. It is the default line limit a train
# spawns with, not a hard ceiling: raise speed_limit on the bench
# and the train will chase it.
MAX_SPEED_MPS = 70 / KMH_PER_MPS
V_FLOOR_MPS = 1.0               # below which F = P / v is capped
SERVICE_DECEL_MPS2 = 1.2
EBRAKE_DECEL_MPS2 = 2.73
# How far over target the train may drift before the brake helps.
# With no resistance in the model the brake is the only thing that
# can slow the train, so this is the band it is allowed to hold.
SERVICE_BAND_MPS = 0.5
# Rolling resistance, from truth modules/train-model.md. Applied only
# under a brake failure for now; see _plant().
ROLLING_RESISTANCE_COEFF = 0.002
GRAVITY_MPS2 = 9.81
ROLLING_DECEL_MPS2 = ROLLING_RESISTANCE_COEFF * GRAVITY_MPS2
# Below this the emergency brake may be released: the train is at a
# stand (D011: the Train Controller releases the emergency brake).
STANDSTILL_MPS = 0.1
# Below this, with nothing asked of it, the toy plant settles to an
# exact stand instead of creeping.
SETTLE_MPS = 0.12

# Defaults that pull the full 0.5 m/s^2 from a stand, reach 70 km/h
# in about three quarters of a minute, and then sit within a tenth of
# a mile an hour of target without the brake having to help. An
# engineer can still commission anything.
DEFAULT_KP = 400_000.0          # W per m/s of error
DEFAULT_KI = 8_000.0            # W per (m/s x s) of accumulated error

# One plant per train, and they all run. When the real Train Model
# arrives it publishes through apply_inputs exactly as the bench
# does, and ControllerCore._plant() is what it replaces.

ASPECTS = ["RED", "YELLOW", "GREEN", "SUPER GREEN"]
ASPECT_TEXT = {
    "RED": "Stop.",
    "YELLOW": "Slow down.",
    "GREEN": "Continue to cruise.",
    "SUPER GREEN": "All clear ahead.",
}

#: Failure Status, in the bool[3] order truth signals/failure-status.md
#: gives: engine, signal pickup, brake.
FAILURES = ("engine", "signal_pickup", "brake")
FAILURE_TEXT = {
    "engine": "engine failure",
    "signal_pickup": "signal pickup failure",
    "brake": "brake failure",
}

#: Beacon platform sides (truth signals/beacon.md).
BEACON_SIDES = ("L", "R")

#: Lines a train can be spawned on, and the id prefix each one uses.
LINES = {"GREEN LINE": "T", "RED LINE": "R"}

#: Real time per simulated second, as the bench offers it.
SIM_RATES = (1, 10)

# Tokens this console needs that the style guide does not define yet.
# Per guide section 1 a missing token is added to the guide first,
# then used; this one is proposed in truth/_inbox/Train-Ctrl_HW/.
#
#   brake_*   section 4.4 --danger is a deep signal red, right for
#             the emergency brake. The service brake is a routine
#             stop that only the Train Controller applies, and must
#             not read as the same control, so it is the amber a cab
#             brake handle uses. Contrast: text-primary on
#             brake_service is 11.2:1 (AAA).
PENDING_TOKENS: dict[str, Any] = {
    "brake_service": "#F2C037",
    "brake_service_active": "#D9A520",
}


class TrainControllerError(Exception):
    """Base class for every error this module raises."""


class InvalidInputError(TrainControllerError):
    """An input on the interface could not be read as its type."""


def check_shared_library() -> bool:
    """Report, in words, a missing shared QML library.

    This module is a sibling of the repository-root ui/ folder and
    the views import it with a relative path. Moved out of the
    repository, every shared type goes unresolved and the window
    simply fails to load, so say so here instead.
    """
    if (_SHARED_UI / "ScaledWindow.qml").exists():
        return True
    print(
        f"Shared QML library not found at {_SHARED_UI}.\n"
        "This module has to sit beside it, in the repository root:\n"
        "    <repo>/ui/              shared components\n"
        "    <repo>/Train-Ctrl_HW/main.py\n"
        "Copying ui/theme.py and ui/aspect_lock.py into this module\n"
        "satisfies the Python imports but not the QML ones.",
        file=sys.stderr,
    )
    return False


def normalize_block_letter(text: str) -> str:
    """Return the letter of a block typed by the operator.

    They type "a", "A", or whatever is quickest; the backend keeps
    identifiers in one case so comparisons elsewhere are not a trap
    (see identifiers.md).
    """
    letters = [c for c in str(text) if c.isalpha()]
    return letters[0].upper() if letters else "A"


def build_console_theme() -> dict[str, Any]:
    """Return the shared tokens plus the pending ones, as one table."""
    theme = build_theme()
    theme.update(PENDING_TOKENS)
    return theme


def _read_flags(values: dict, key: str, count: int) -> list[bool]:
    # A bool[N] signal arrives as a list; anything else, or a list of
    # the wrong length, is a caller error.
    flags = values[key]
    if not isinstance(flags, (list, tuple)) or len(flags) != count:
        raise InvalidInputError(
            f"{key} must be {count} flags, not {flags!r}")
    return [bool(flag) for flag in flags]


def _read_number(values: dict, key: str) -> float:
    # Bench values arrive from QML untyped; a value that is not a
    # number is a caller error, raised in this module's own terms.
    try:
        return float(values[key])
    except (TypeError, ValueError) as error:
        raise InvalidInputError(
            f"{key} must be a number, not {values[key]!r}"
        ) from error


# The physical panel is not wired yet, so there is no hardware layer
# in this file: the console is the whole interface. Putting one back
# means a small class with read_estop / write_power /
# write_service_brake / write_emergency_brake, constructed in main()
# and called from ControllerCore.step() and engage_emergency() where
# the outputs are already computed. Nothing else has to change, and
# the lever the old stub exposed was never read by anything.


# ================================================================ state
@dataclass
class State:
    """Everything the console shows or the control law needs."""

    train_id: str = "T-114"
    line: str = "GREEN LINE"
    manual: bool = False

    actual_mps: float = 0.0
    commanded_mps: float = 0.0
    target_mps: float = 0.0
    speed_limit_mps: float = MAX_SPEED_MPS
    accel_mps2: float = 0.0

    # Authority: how many blocks the train may still enter before it
    # has to stop, as the Track Model reports it, and the block it
    # stops at. A count and an ID, not a measurement, so neither is
    # ever converted. The controller does not track blocks itself:
    # the count it is sent is how far it may go.
    authority_blocks: int = 4
    authority_target: str = "GREEN K"

    power_w: float = 0.0
    service_brake: bool = False
    service_request: bool = False
    emergency_brake: bool = False

    # Failure Status from the Train Model, one flag per subsystem, in
    # the FAILURES order.
    failures: dict = field(
        default_factory=lambda: {name: False for name in FAILURES})

    # State reported back by the Train Model, as opposed to what this
    # controller commanded (truth door-state, light-state,
    # brake-state). With no Train Model attached the toy plant stands
    # in for it, and the bench can publish them too.
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


# ========================================================= control
class ControllerCore:
    """The PI speed law, the safety path and the toy plant.

    No Qt, no view: this class is what the hardware demo has to prove
    correct, and it runs unchanged whether or not a console is open.
    """

    def __init__(self) -> None:
        self.state = State()
        self.dt = 1.0 / CONTROL_HZ          # seconds of simulation
        self.integral = 0.0
        # Inert until an engineer commissions the gains.
        self.armed = False
        # The door and light commands the plant last acted on, so it
        # answers a command once, on its edge, and leaves a state the
        # bench published alone in between.
        self._acted_doors: tuple[bool, bool] | None = (False, False)
        self._acted_lights: tuple[bool, bool] | None = (True, True)

    @property
    def failed(self) -> list[str]:
        """The reported failures that are active, in FAILURES order."""
        return [name for name in FAILURES if self.state.failures[name]]

    @property
    def authority_blocks(self) -> int:
        """The authority the controller may act on.

        With signal pickup failed the Track Signal cannot be trusted,
        so it fails safe to none (truth failure-status.md).
        """
        s = self.state
        if s.failures["signal_pickup"]:
            return 0
        return s.authority_blocks

    def step(self) -> None:
        """Run one control period.

        Only the speed law waits for the gains. The brakes and the
        safety path run from the first tick, because a console that
        has not been commissioned yet still has to be able to stop
        the train and still has to report what the brakes are doing.
        """
        s = self.state
        if self.armed:
            if not s.manual:
                # In Automatic the CTC's commanded speed already
                # agrees with the signal ahead, so the only things
                # left to respect are the line limit and the car.
                s.target_mps = min(s.commanded_mps, s.speed_limit_mps)

            error = s.target_mps - s.actual_mps
            # A target of zero means stop, so the brake holds to a
            # stand rather than leaving the train creeping inside the
            # band with no resistance to bring it down.
            stopping = s.target_mps <= 0.0 and s.actual_mps > 0.0
            s.service_brake = (
                error < -SERVICE_BAND_MPS or s.service_request or stopping
            )
            if s.service_brake:
                # Traction is cut whenever a brake is applied, and
                # the integrator holds rather than winding up against
                # the brake (arbitration/traction-cut-under-braking).
                s.power_w = 0.0
            else:
                self.integral += error * self.dt
                power = s.kp * error + s.ki * self.integral
                if power > MAX_POWER_W:
                    power = MAX_POWER_W
                    self.integral -= error * self.dt
                elif power < 0.0:
                    power = 0.0
                    self.integral -= error * self.dt
                s.power_w = power
        else:
            s.power_w = 0.0
            s.service_brake = s.service_request

        self.respond_to_failures()
        self.enforce_safety()
        self._plant()

    def respond_to_failures(self) -> None:
        """Stop the train while any failure is reported.

        REQ-FUNC-037.2: the controller stops the train when a failure
        is detected. Every failure removes the target and the power;
        how the train then stops depends on what failed:

            engine         the emergency brake is applied and latched;
                           no traction is left to drive with
            signal pickup  the emergency brake is applied and latched;
                           commanded speed and authority cannot be
                           read from the track circuit, so they fail
                           safe to zero (the signal lights still read)
            brake          neither brake answers, so no brake is
                           commanded; with power cut, rolling
                           resistance coasts the train down

        The emergency brake cannot be released until the failure
        clears (release_emergency refuses while any is active).
        """
        if not self.failed:
            return
        s = self.state
        s.target_mps = 0.0
        s.power_w = 0.0
        self.integral = 0.0
        if ((s.failures["engine"] or s.failures["signal_pickup"])
                and not s.emergency_brake):
            self.engage_emergency()
        s.service_brake = False

    def enforce_safety(self) -> None:
        """Override the PI law with the safety rules.

        Gains change how the train drives; they can never change
        whether it stops.
        """
        s = self.state

        # No authority is not an emergency. The train may not move,
        # and it comes to a stand on the service brake the way a
        # driver would stop it, in either mode.
        if self.authority_blocks <= 0:
            s.target_mps = 0.0
            s.power_w = 0.0
            self.integral = 0.0
            if s.actual_mps > 0.0:
                s.service_brake = True

        # The emergency brake has two sources and no others: the
        # driver pulls it, or the Train Model reports it pulled.
        # Nothing in here pulls it on their behalf.
        if s.emergency_brake:
            s.power_w = 0.0
            self.integral = 0.0

    def engage_emergency(self) -> None:
        """Engage now, without waiting for the next control tick.

        Guide section 7 calls the emergency brake immediate, so the
        safety path runs on the press rather than up to one control
        period later.
        """
        self.state.emergency_brake = True
        self.enforce_safety()

    def release_emergency(self) -> bool:
        """Release the latched brake, at a stand with no failure.

        Asking a released brake to release is not a refusal: it is
        already where the caller wants it.
        """
        s = self.state
        if not s.emergency_brake:
            return True
        if self.failed or abs(s.actual_mps) >= STANDSTILL_MPS:
            return False
        s.emergency_brake = False
        return True

    def set_target_mps(self, mps: float) -> None:
        """Set the driver's target in m/s, capped at the limit."""
        s = self.state
        if s.manual and self.authority_blocks > 0 and not self.failed:
            s.target_mps = max(0.0, min(mps, s.speed_limit_mps))

    def command_door(self, side: str, open_: bool) -> None:
        """Command one side's doors, and have the plant answer it.

        The plant answers a command on its edge. Pressing a tile
        again with the same command, because the reported state still
        disagrees (the door interlock held it, say), has to be
        answered too, or the tile could never change anything.
        """
        s = self.state
        if side == "left":
            s.doors_left = open_
        else:
            s.doors_right = open_
        self._acted_doors = None

    def command_lights(self, interior: bool, exterior: bool) -> None:
        """Command the lights, and have the plant answer it."""
        s = self.state
        s.interior_lights, s.exterior_lights = interior, exterior
        self._acted_lights = None

    def commands(self) -> TrainModelCommands:
        """Return this tick's commands to the Train Model, in SI."""
        s = self.state
        return TrainModelCommands(
            power_w=s.power_w,
            service_brake=s.service_brake,
            emergency_brake=s.emergency_brake,
            door_command=(s.doors_left, s.doors_right),
            light_command=(s.interior_lights, s.exterior_lights),
            temperature_setpoint_c=s.target_temp_c,
            announcement=s.announcement,
        )

    def _plant(self) -> None:
        # Toy physics standing in for the Train Model until it is
        # wired in:
        #
        #     F = P / v     a = F / M     v = v + a dt
        #
        # No resistance term in normal running: the model is the block
        # diagram and nothing else. A train with no power applied
        # coasts forever, so the only ways down are the two brakes,
        # and the speed law holds its target from below rather than
        # settling onto it from both sides. The failures act here the
        # way truth failure-status.md says the Train Model applies
        # them. Under a brake failure, and only then for now, rolling
        # resistance (truth modules/train-model.md) is what slows the
        # train, so it coasts down to a stand instead of for ever.
        s = self.state
        brakes_work = not s.failures["brake"]
        power = 0.0 if s.failures["engine"] else s.power_w
        v = s.actual_mps
        force = min(MAX_FORCE_N, power / max(abs(v), V_FLOOR_MPS))
        a = force / MASS_KG
        decel = 0.0
        if brakes_work and s.emergency_brake:
            decel = EBRAKE_DECEL_MPS2
        elif brakes_work and s.service_brake:
            decel = SERVICE_DECEL_MPS2
        if decel:
            # A brake opposes the motion and never reverses it.
            a = -math.copysign(decel, v) if v else 0.0
        elif not brakes_work:
            # Resistance opposes the motion, holds the train at rest,
            # and never reverses it.
            a = (a - math.copysign(ROLLING_DECEL_MPS2, v) if v
                 else max(0.0, a - ROLLING_DECEL_MPS2))
        new_v = v + a * self.dt
        if v * new_v < 0.0:
            new_v = 0.0             # stopped, never reversed
        s.accel_mps2 = a
        s.actual_mps = new_v
        if abs(s.actual_mps) < SETTLE_MPS and s.target_mps < SETTLE_MPS:
            s.actual_mps = 0.0          # settle cleanly at a stand

        # Brake State reports what is actually engaged, so a failed
        # brake reads false whatever was commanded (truth
        # brake-state.md).
        s.fb_emergency_brake = s.emergency_brake and brakes_work
        s.fb_service_brake = s.service_brake and brakes_work

        # Door and light commands are answered on their edge. A door
        # only opens at a stand (the door interlock, truth
        # door-command.md); a command to open while moving is ignored.
        doors = (s.doors_left, s.doors_right)
        if doors != self._acted_doors:
            at_stand = abs(s.actual_mps) < STANDSTILL_MPS
            s.fb_doors_left = s.doors_left and at_stand
            s.fb_doors_right = s.doors_right and at_stand
            self._acted_doors = doors
        lights = (s.interior_lights, s.exterior_lights)
        if lights != self._acted_lights:
            s.fb_interior_lights, s.fb_exterior_lights = lights
            self._acted_lights = lights

        drift = s.target_temp_c - s.cabin_temp_c
        s.cabin_temp_c += max(
            -CABIN_DRIFT_MAX_C,
            min(CABIN_DRIFT_MAX_C, drift * CABIN_DRIFT_FRACTION),
        )


# ========================================================== bridge
class ConsoleBackend(QObject):
    """What QML sees: one snapshot out, one slot per operator action.

    Every rule about who may do what lives here, not in the view. The
    view mirrors the rules by disabling controls, but a slot that is
    called anyway still refuses.
    """

    snapshot_changed = Signal()
    # The roster changes only when a train is added or removed. It has
    # its own signal so the train lists are not rebuilt on every UI
    # tick, which reset their scroll and dropped clicks mid-pick.
    roster_changed = Signal()
    # The selected train's commands, as a plain dict with its id, each
    # time they change. The central harness (D005) connects here.
    commands_changed = Signal(dict)

    #: Roles, by the index the Operator toggle uses. -1 is signed out.
    ROLES = ("driver", "engineer")
    ENGINEER_INDEX = ROLES.index("engineer")

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # One plant per train. They all run; the console and the
        # bench look at whichever one is selected.
        self.cores: dict[str, ControllerCore] = {}
        self.order: list[str] = []
        self.selected = ""
        self.notes: dict[str, str] = {}
        self.announcing: set[str] = set()
        self.sim_rate = 1
        self.spawn_note = ""
        self._last_commands: dict[str, TrainModelCommands] = {}

        self.operator: str = ""         # "" | "driver" | "engineer"
        self.gains_note = ""
        self.elapsed = QTime(0, 0, 0)

        # Nothing runs until somebody spawns it. This one is never
        # stepped and never shown: it exists so that the snapshot and
        # the views have a shape to read while the roster is empty,
        # rather than every binding needing a null check.
        self.idle = ControllerCore()

        self._control = QTimer(self)
        self._control.timeout.connect(self._step_all)
        self._control.start(int(1000 / CONTROL_HZ))

        self._ui = QTimer(self)
        self._ui.timeout.connect(self._tick)
        self._ui.start(int(1000 / UI_HZ))

    # ---------------------------------------------------------- fleet
    def add_train(self, number: int, line: str, target: str) -> str:
        """Put another train in the simulation and select it.

        The number is the operator's to choose; the prefix follows
        the line, which is how the CTC roster reads. Returns the id,
        or an empty string if that one is already running.
        """
        prefix = LINES.get(line, "T")
        train_id = f"{prefix}-{int(number)}"
        if train_id in self.cores:
            self.spawn_note = f"{train_id} is already running."
            return ""

        core = ControllerCore()
        core.dt = self.sim_rate / CONTROL_HZ
        core.state.train_id = train_id
        core.state.line = line
        core.state.authority_target = normalize_block_letter(target)
        self.cores[train_id] = core
        self.order.append(train_id)
        self.notes[train_id] = ""
        self.selected = train_id
        self.spawn_note = f"{train_id} spawned on the {line.lower()}."
        self.roster_changed.emit()
        return train_id

    def drop_train(self, train_id: str) -> bool:
        """Take a train out of the simulation.

        Everything kept per train goes with it. If it was the
        selected one, selection moves to the next train in the
        roster, or to none. Returns whether there was such a train.
        """
        if train_id not in self.cores:
            return False
        index = self.order.index(train_id)
        del self.cores[train_id]
        self.order.remove(train_id)
        self.notes.pop(train_id, None)
        self.announcing.discard(train_id)
        self._last_commands.pop(train_id, None)
        if self.selected == train_id:
            remaining = len(self.order)
            self.selected = (
                self.order[min(index, remaining - 1)] if remaining else ""
            )
        self.spawn_note = f"{train_id} removed."
        self.roster_changed.emit()
        return True

    def _step_all(self) -> None:
        for train_id, core in self.cores.items():
            core.step()
            commands = core.commands()
            if self._last_commands.get(train_id) != commands:
                self._last_commands[train_id] = commands
                self.commands_changed.emit(
                    {"train_id": train_id, **asdict(commands)})

    @property
    def has_train(self) -> bool:
        """Whether a train is selected."""
        return self.selected in self.cores

    @property
    def core(self) -> ControllerCore:
        """The train the console and the bench are pointed at."""
        return self.cores[self.selected] if self.has_train else self.idle

    @property
    def brake_note(self) -> str:
        """The emergency-brake message for the selected train."""
        return self.notes.get(self.selected, "")

    @brake_note.setter
    def brake_note(self, text: str) -> None:
        self.notes[self.selected] = text

    # ------------------------------------------------------- read side
    @property
    def signed_in(self) -> bool:
        """Whether a driver or an engineer is at the console."""
        return self.operator != ""

    @property
    def can_drive(self) -> bool:
        """Whether the driver may act: Manual only.

        Automatic locks the console. The emergency brake is the
        exception and stays live for any signed-in operator, in
        either mode (guide section 7).
        """
        return (
            self.has_train
            and self.operator == "driver"
            and self.core.state.manual
        )

    @Property("QVariantList", notify=roster_changed)
    def trains(self) -> list[dict[str, Any]]:
        """The roster the train selectors show."""
        return [{"id": i,
                 "line": self.cores[i].state.line,
                 "label": f"{i} · {self.cores[i].state.line}"}
                for i in self.order]

    @Property("QVariantMap", notify=snapshot_changed)
    def snapshot(self) -> dict[str, Any]:
        """Every value the views read, rebuilt once per UI tick."""
        s = self.core.state
        return {
            "train_id": s.train_id,
            "has_train": self.has_train,
            "train_index": (
                self.order.index(self.selected) if self.has_train else -1
            ),
            "train_count": len(self.order),
            "sim_rate": self.sim_rate,
            "sim_rate_index": SIM_RATES.index(self.sim_rate),
            "spawn_note": self.spawn_note,
            "operator": self.operator,
            "operator_index": (
                self.ROLES.index(self.operator) if self.signed_in else -1
            ),
            "signed_in": self.signed_in,
            "manual": s.manual,
            "mode_label": "Manual" if s.manual else "Automatic",
            "can_drive": self.can_drive,
            "armed": self.core.armed,
            # Gains are commissioned once per train, so both of these
            # follow that train's controller rather than the console.
            "gains_locked": self.core.armed,
            "gains_note": self.gains_note,
            "clock": self.elapsed.toString("HH:mm:ss"),

            # Converted here and nowhere else. Keys carry the unit the
            # operator sees, so a reader can tell which side of the
            # line a value is on at a glance.
            "actual_mph": s.actual_mps * MPS_TO_MPH,
            "commanded_mph": s.commanded_mps * MPS_TO_MPH,
            "target_mph": s.target_mps * MPS_TO_MPH,
            "limit_mph": s.speed_limit_mps * MPS_TO_MPH,
            "accel_ftps2": s.accel_mps2 * M_TO_FT,
            "dial_hint": self._dial_hint(),
            # Automatic is the console locked: the CTC owns the
            # speed and the dial does nothing.
            "speed_source": "Driver" if s.manual else "Locked",

            "power_kw": s.power_w * W_TO_KW,
            "max_power_kw": MAX_POWER_W * W_TO_KW,
            "service_brake": s.service_brake,
            "service_request": s.service_request,
            "emergency_brake": s.emergency_brake,
            "brake_note": self.brake_note,
            "faulted": any(s.failures.values()),
            "fault_engine": s.failures["engine"],
            "fault_brake": s.failures["brake"],
            "fault_pickup": s.failures["signal_pickup"],
            "fb_doors_left": s.fb_doors_left,
            "fb_doors_right": s.fb_doors_right,
            "fb_interior_lights": s.fb_interior_lights,
            "fb_exterior_lights": s.fb_exterior_lights,
            "fb_emergency_brake": s.fb_emergency_brake,
            "fb_service_brake": s.fb_service_brake,
            "beacon_station": s.beacon_station,
            "beacon_side": s.beacon_side,
            "beacon_underground": s.beacon_underground,
            "announcement": s.announcement,

            # Identifiers and counts, so they are shown as they are.
            "authority_blocks": s.authority_blocks,
            "authority_target": s.authority_target,

            "cabin_temp_f": c_to_f(s.cabin_temp_c),
            "target_temp_f": c_to_f(s.target_temp_c),
            "doors_left": s.doors_left,
            "doors_right": s.doors_right,
            "interior_lights": s.interior_lights,
            "exterior_lights": s.exterior_lights,

            "announcing": self.selected in self.announcing,
            "announce_label": self._announce_label(),

            "next_signal": s.next_signal,
            "signal_index": ASPECTS.index(s.next_signal),
            "signal_text": ASPECT_TEXT[s.next_signal],

            "kp": s.kp,
            "ki": s.ki,
        }

    def _failure_note(self) -> str:
        failed = self.core.failed
        if not failed:
            return ""
        names = ", ".join(FAILURE_TEXT[name] for name in failed)
        # The panel callouts say what each failure is doing to the
        # train; this only says what is locked and until when.
        return (f"{names[0].upper()}{names[1:]}. Driving and brake "
                "release resume once it clears.")

    def _dial_hint(self) -> str:
        # While a failure is up, the hint says why the train is
        # stopping and what has to happen before it can be driven.
        if self.core.failed:
            return self._failure_note()
        if not self.core.armed:
            return "Waiting for the engineer to set the control gains."
        if self.core.state.manual:
            return "Drag the dial to set your target speed."
        return "Set by the CTC. Switch to Manual to take control."

    def _announce_label(self) -> str:
        if self.selected in self.announcing:
            return "Announcing…"
        if self.operator == "driver" and not self.core.state.manual:
            return "Announced automatically"
        return "Announce next station"

    # ------------------------------------------------------ write side
    @Slot(int)
    def select_operator(self, index: int) -> None:
        """Sign in as driver (0) or engineer (1), or out (-1).

        The engineer role is spent once the gains are committed: the
        option stays visible but selecting it is refused, never
        hidden (guide section 8).
        """
        if index == self.ENGINEER_INDEX and self.core.armed:
            self._publish()
            return
        in_range = 0 <= index < len(self.ROLES)
        self.operator = self.ROLES[index] if in_range else ""
        if self.operator == "engineer":
            self.gains_note = ""
        self._publish()

    @Slot(bool)
    def set_manual(self, manual: bool) -> None:
        """Switch the selected train between Manual and Automatic.

        Refused while a failure is up: the train is being stopped,
        and nothing may hand it back a speed until the failure clears.
        """
        if not self.has_train or not self.signed_in:
            return
        if self.core.failed:
            self._publish()
            return
        self.core.state.manual = manual
        self._publish()

    @Slot(str)
    def select_train(self, train_id: str) -> None:
        """Point the console and the bench at another train."""
        if train_id in self.cores:
            self.selected = train_id
        self._publish()

    @Slot(int, str, str)
    def spawn_train(self, number: int, line: str, target: str) -> None:
        """Add a train to the simulation and select it.

        It starts where every train starts: stopped, uncommissioned,
        with its own authority and destination, running its own
        plant from the next tick.
        """
        self.add_train(number, line, target)
        self._publish()

    @Slot(str)
    def remove_train(self, train_id: str) -> None:
        """Take a train out of the simulation, from the bench."""
        self.drop_train(train_id)
        self._publish()

    @Slot(int)
    def set_sim_rate(self, index: int) -> None:
        """Run at real time or ten times real time.

        The tick rate does not change; the simulated seconds each
        tick advances do, so the control law and the plant keep their
        timestep relationship and only the clock moves faster.
        """
        if not 0 <= index < len(SIM_RATES):
            return
        self.sim_rate = SIM_RATES[index]
        for core in self.cores.values():
            core.dt = self.sim_rate / CONTROL_HZ
        self._publish()

    @Slot(float)
    def set_target_mph(self, mph: float) -> None:
        """Set the driver's target from the dial, which speaks mph."""
        if not self.can_drive:
            return
        self.core.set_target_mps(mph / MPS_TO_MPH)
        self._publish()

    @Slot()
    def toggle_emergency_brake(self) -> None:
        """Engage or release the emergency brake from one control.

        Engagement is immediate and unconfirmed, the one exception the
        style guide grants (section 7). Release is refused unless the
        train is stopped and no failure is reported.
        """
        if not self.has_train or not self.signed_in:
            return
        s = self.core.state
        if not s.emergency_brake:
            self.core.engage_emergency()
            self.brake_note = (
                "Emergency brake engaged. "
                "Release it from the same control."
            )
        elif self.core.release_emergency():
            self.brake_note = ""
        elif self.core.failed:
            names = ", ".join(FAILURE_TEXT[n] for n in self.core.failed)
            self.brake_note = f"Cannot release: {names} is still active."
        else:
            self.brake_note = "Cannot release: the train is still moving."
        self._publish()

    @Slot()
    def toggle_service_brake(self) -> None:
        """Apply or release the driver's service brake request."""
        if not self.can_drive:
            return
        s = self.core.state
        s.service_request = not s.service_request
        self._publish()

    @Slot(int)
    def set_target_temp_f(self, fahrenheit: int) -> None:
        """Set the cabin setpoint from the thermostat, in Fahrenheit."""
        if not self.can_drive:
            return
        clamped = max(CABIN_MIN_F, min(CABIN_MAX_F, float(fahrenheit)))
        self.core.state.target_temp_c = f_to_c(clamped)
        self._publish()

    @Slot(str, bool)
    def set_door(self, side: str, open_: bool) -> None:
        """Command the left or right doors open or shut.

        Only the command changes here. Whether the door actually
        opens is the Train Model's to report (truth door-state.md).
        """
        if not self.can_drive:
            return
        self.core.command_door(side, open_)
        self._publish()

    @Slot(bool)
    def set_interior_lights(self, on: bool) -> None:
        """Command the interior lights on or off."""
        if not self.can_drive:
            return
        self.core.command_lights(on, self.core.state.exterior_lights)
        self._publish()

    @Slot(bool)
    def set_exterior_lights(self, on: bool) -> None:
        """Command the exterior lights on or off."""
        if not self.can_drive:
            return
        self.core.command_lights(self.core.state.interior_lights, on)
        self._publish()

    @Slot()
    def announce(self) -> None:
        """Play the station announcement, then lock out for a while."""
        if not self.can_drive or self.selected in self.announcing:
            return
        train = self.selected
        self.announcing.add(train)
        self.core.state.announcement = self.core.state.beacon_station
        QTimer.singleShot(ANNOUNCE_LOCKOUT_MS,
                          lambda: self._announce_done(train))
        self._publish()

    def _announce_done(self, train: str) -> None:
        self.announcing.discard(train)
        if train in self.cores:
            self.cores[train].state.announcement = ""
        self._publish()

    # ------------------------------------------------- Train Model
    # Every signal the Train Model sends arrives through apply_inputs,
    # in SI and in the shapes truth signals/ gives, as one coherent
    # set rather than a slot per field. The bench reaches it through
    # apply_bench_inputs, which converts from the operator's units.

    @Slot("QVariantMap")
    def apply_inputs(self, values: dict) -> None:
        """Take a whole set of Train Model signals in one go, in SI.

        Keys and shapes follow truth signals/: commanded_speed,
        speed_limit and actual_speed (m/s, actual signed),
        cabin_temperature (C), authority_blocks, signal_light_ahead,
        beacon_station / beacon_side / beacon_underground,
        failure_status bool[3] (engine, pickup, brake), brake_state
        bool[2] (emergency, service), door_state bool[2] (left,
        right) and light_state bool[2] (interior, exterior).

        Every value is read before any is applied, so a set with one
        bad value changes nothing. Raises InvalidInputError for a
        value that cannot be read as its type.
        """
        if not self.has_train:
            return
        staged = self._read_inputs(values)
        s = self.core.state
        failures = staged.pop("failure_status", None)
        brakes = staged.pop("brake_state", None)
        for attr, value in staged.items():
            setattr(s, attr, value)
        if failures is not None:
            s.failures.update(zip(FAILURES, failures))
        if brakes is not None:
            # A reported emergency brake that this controller did not
            # command is a passenger pull: latch it and cut power. A
            # report of false never releases it; only the driver does
            # (D011, arbitration/passenger-emergency-brake).
            emergency, service = brakes
            if emergency and not s.emergency_brake:
                self.core.engage_emergency()
            s.fb_emergency_brake, s.fb_service_brake = emergency, service
        self._publish()

    @staticmethod
    def _read_inputs(values: dict) -> dict[str, Any]:
        # Read and check the whole set, touching no state, so that
        # apply_inputs can refuse it outright.
        staged: dict[str, Any] = {}
        for key, attr in (("commanded_speed", "commanded_mps"),
                          ("speed_limit", "speed_limit_mps")):
            if key in values:
                staged[attr] = max(0.0, _read_number(values, key))
        if "actual_speed" in values:
            staged["actual_mps"] = _read_number(values, "actual_speed")
        if "cabin_temperature" in values:
            staged["cabin_temp_c"] = _read_number(
                values, "cabin_temperature")
        if "authority_blocks" in values:
            staged["authority_blocks"] = max(
                0, int(_read_number(values, "authority_blocks")))
        if "beacon_station" in values:
            staged["beacon_station"] = str(values["beacon_station"])
        if values.get("beacon_side") in BEACON_SIDES:
            staged["beacon_side"] = values["beacon_side"]
        if "beacon_underground" in values:
            staged["beacon_underground"] = bool(
                values["beacon_underground"])
        if values.get("signal_light_ahead") in ASPECTS:
            staged["next_signal"] = values["signal_light_ahead"]
        if "failure_status" in values:
            staged["failure_status"] = _read_flags(
                values, "failure_status", len(FAILURES))
        if "brake_state" in values:
            staged["brake_state"] = _read_flags(values, "brake_state", 2)
        if "door_state" in values:
            staged["fb_doors_left"], staged["fb_doors_right"] = (
                _read_flags(values, "door_state", 2))
        if "light_state" in values:
            (staged["fb_interior_lights"],
             staged["fb_exterior_lights"]) = _read_flags(
                values, "light_state", 2)
        return staged

    @Slot("QVariantMap")
    def apply_bench_inputs(self, values: dict) -> None:
        """Take the bench's edited rows, convert, and apply them.

        The bench is a view, so it speaks the operator's units (mph,
        Fahrenheit) and one row per element. This converts once, here
        on the display side, and hands apply_inputs the SI signals in
        their truth shapes. Gains ride along because sending the set
        is what commissions them; they are not a Train Model signal,
        and they are committed only once the rest of the set has
        applied, since commissioning cannot be undone.
        """
        if not self.has_train:
            return
        s = self.core.state
        si: dict[str, Any] = {}
        for key in ("commanded_speed", "speed_limit", "actual_speed"):
            if key in values:
                si[key] = _read_number(values, key) / MPS_TO_MPH
        if "cabin_temperature" in values:
            si["cabin_temperature"] = f_to_c(
                _read_number(values, "cabin_temperature"))
        for key in ("authority_blocks", "signal_light_ahead",
                    "beacon_station", "beacon_side",
                    "beacon_underground"):
            if key in values:
                si[key] = values[key]
        groups = (
            ("failure_status",
             ("failure_engine", "failure_signal_pickup", "failure_brake"),
             [s.failures[name] for name in FAILURES]),
            ("brake_state",
             ("brake_state_emergency", "brake_state_service"),
             [s.fb_emergency_brake, s.fb_service_brake]),
            ("door_state",
             ("door_state_left", "door_state_right"),
             [s.fb_doors_left, s.fb_doors_right]),
            ("light_state",
             ("light_state_interior", "light_state_exterior"),
             [s.fb_interior_lights, s.fb_exterior_lights]),
        )
        for signal, rows, current in groups:
            if any(row in values for row in rows):
                si[signal] = [bool(values.get(row, now))
                              for row, now in zip(rows, current)]
        commission = ("kp" in values or "ki" in values
                      ) and not self.core.armed
        if commission:
            kp = _read_number(values, "kp") if "kp" in values else s.kp
            ki = _read_number(values, "ki") if "ki" in values else s.ki
        self.apply_inputs(si)
        if commission:
            self.commission_gains(kp, ki)

    @Slot(float, float)
    def commission_gains(self, kp: float, ki: float) -> None:
        """Commission the gains once, at start-up, and start the run.

        Gains are frozen afterwards and the engineer role is handed
        back to the driver a moment later, so the confirmation can be
        read.
        """
        if not self.has_train:
            return
        if self.core.armed or self.operator != "engineer":
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
        self.gains_note = (
            f"Set to Kp {s.kp:.0f}, Ki {s.ki:.0f}. Fixed for this run."
        )
        QTimer.singleShot(GAINS_HANDOVER_MS, self._retire_engineer)
        self._publish()

    def _retire_engineer(self) -> None:
        # Close the gains dialog and hand the console to the driver.
        self.operator = "driver"
        self._publish()

    # ----------------------------------------------------------- ticks
    def _tick(self) -> None:
        if self.core.armed:
            self.elapsed = self.elapsed.addMSecs(
                int(1000 / UI_HZ) * self.sim_rate)
        if self.core.state.emergency_brake and not self.brake_note:
            self.brake_note = (
                "Emergency brake engaged. "
                "Release it from the same control."
            )
        self._publish()

    def _publish(self) -> None:
        self.snapshot_changed.emit()


# ================================================================ main
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--test", action="store_true",
        help="open the Train Model bench instead",
    )
    parser.add_argument(
        "--both", action="store_true",
        help="open the console and the bench together",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="run offscreen, exercise the console, report",
    )
    parser.add_argument(
        "--shots", metavar="DIR",
        help="with --check, save screenshots to DIR",
    )
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

    # Keep Python-side references so the objects are not garbage
    # collected while QML holds only C++ pointers to them.
    backend = ConsoleBackend()

    if not check_shared_library():
        return 1

    contract_ok = check_snapshot_contract(backend, _UI_DIR)

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

    wanted = []
    if args.both or args.check or not args.test:
        wanted.append(_CONSOLE_QML)
    if args.both or args.check or args.test:
        wanted.append(_TEST_QML)
    for qml in wanted:
        engine.load(QUrl.fromLocalFile(str(qml)))
    if len(engine.rootObjects()) != len(wanted):
        print("Failed to load "
              + ", ".join(str(q) for q in wanted), file=sys.stderr)
        for issue in qml_errors:
            print(f"  {issue}", file=sys.stderr)
        return 1

    # Each window scales on its own; the locks stay alive with them.
    locks = [install_window_scaling(w)  # noqa: F841
             for w in engine.rootObjects()]
    windows = {
        qml.stem: w for qml, w in zip(wanted, engine.rootObjects())
    }

    if args.check:
        shots = Path(args.shots) if args.shots else None
        code = run_check(
            app, windows["ConsoleWindow"], windows["TestWindow"],
            backend, warnings, shots,
        )
        code = code or (0 if contract_ok else 1)
        qInstallMessageHandler(None)
        del engine
        return code

    exit_code = app.exec()
    # Tear down QML before the objects it binds to, so bindings do not
    # re-evaluate against deleted objects during shutdown.
    del engine
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
