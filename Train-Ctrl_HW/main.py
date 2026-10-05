"""HW Train Controller — driver / engineer console (ECE1140 Team 3).

Entry point for the module. Python owns the control law and the
state;
QML owns every pixel. The two meet at three context properties:

    theme        design tokens, from the shared ui/theme.py
    controller   ConsoleBackend: one snapshot out, slots in
    trainList    the trains the console can be pointed at

    ControllerCore      PI speed law; safety enforced on a separate path
    ConsoleBackend      the Qt bridge; computes the snapshot, nothing else
    ui/                 the view; reads the snapshot, computes nothing

Run:

    python main.py                               the driver's console
    python main.py --test                        the Train Model bench
    python main.py --both                        both windows, one backend
    python main.py --check [--shots DIR]         offscreen self-test

The console and the bench are separate windows with no way to navigate
between them: the home page launches one or the other. They share a
controller only when one process opens both, which is what --both is
for and how the bench drives the console.

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

from check import check_snapshot_contract, run_check  # noqa: E402

_UI_DIR = Path(__file__).resolve().parent / "ui_parts"
_CONSOLE_QML = _UI_DIR / "ConsoleWindow.qml"
_TEST_QML = _UI_DIR / "TestWindow.qml"


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
# Motor power is 120 kW and the car has two powered bogies, so four
# motors: 480 kW at the wheel. One motor's worth cannot meet the car's
# own data sheet — 0.5 m/s^2 at 70 km/h needs 398 kW — and a train
# limited to 120 kW tops out around 30 km/h with the acceleration
# falling away the whole time, which is the bug this fixes. If the
# interface dictionary says the controller may command only 120 kW,
# that number and this one disagree and the team has to pick one.
MAX_POWER_W = 480_000.0
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
MAX_ACCEL = 0.5         # m/s^2, and the car will not exceed it
MAX_FORCE_N = MASS_KG * MAX_ACCEL
# The data sheet's 70 km/h. It is the default line limit a train
# spawns with, not a hard ceiling: raise speed_limit on the bench and
# the train will chase it.
MAX_SPEED_MPS = 70 / 3.6
V_FLOOR = 1.0           # m/s, below which F = P / v is capped
SERVICE_DECEL = 1.2     # m/s^2
EBRAKE_DECEL = 2.73     # m/s^2
# How far over target the train may drift before the brake helps.
# With no resistance in the model the brake is the only thing that
# can slow the train, so this is the band it is allowed to hold.
SERVICE_BAND = 0.5      # m/s over target before the service brake helps
BLOCK_LENGTH_M = 500.0  # until the Track Model supplies real lengths

# One plant per train, and they all run. When the real Train Model
# arrives it publishes through applyInputs exactly as the bench does,
# and ControllerCore._plant() is what it replaces.


ASPECTS = ["RED", "YELLOW", "GREEN", "SUPER GREEN"]
ASPECT_TEXT = {
    "RED": "Stop.",
    "YELLOW": "Slow down.",
    "GREEN": "Continue to cruise.",
    "SUPER GREEN": "All clear ahead.",
}

#: Lines a train can be spawned on, and the id prefix each one uses.
LINES = {"GREEN LINE": "T", "RED LINE": "R"}

#: Real time per simulated second, as the bench offers it.
SIM_RATES = (1, 10)

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


def block_letter(text: str) -> str:
    """Take a block as the operator typed it and return its letter.

    They type "a", "A", or whatever is quickest; the backend keeps
    identifiers in one case so comparisons elsewhere are not a trap
    (see identifiers.md).
    """
    letters = [c for c in str(text) if c.isalpha()]
    return letters[0].upper() if letters else "A"


def build_console_theme() -> dict[str, Any]:
    """Shared tokens plus the open items above, as one table."""
    theme = build_theme()
    theme.update(PENDING_TOKENS)
    return theme


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
    # has to stop, and the block it stops at. A count and an ID, not a
    # measurement, so neither is ever converted (units.md).
    authority_blocks: int = 4
    authority_target: str = "GREEN K"
    block_progress_m: float = 0.0

    power_w: float = 0.0
    service_brake: bool = False
    service_request: bool = False
    emergency_brake: bool = False

    # Failure status from the Train Model, one flag per subsystem.
    failures: dict = field(default_factory=lambda: {
        "engine": False, "brake": False, "signal_pickup": False})

    # State reported back by the Train Model, as opposed to what this
    # controller commanded. With no Train Model attached the toy plant
    # echoes the commands into these.
    fb_doors_left: bool = False
    fb_doors_right: bool = False
    fb_lights: bool = False
    fb_headlights: bool = False
    beacon: str = ""

    cabin_temp_c: float = 21.1
    target_temp_c: float = 22.2
    doors_left: bool = False
    doors_right: bool = False
    lights: bool = True
    headlights: bool = True

    next_signal: str = "YELLOW"
    current_block: str = "GREEN I"

    # Defaults that pull the full 0.5 m/s^2 from a stand, reach
    # 70 km/h in about three quarters of a minute, and then sit
    # within a tenth of a mile an hour of target without the brake
    # having to help. An engineer can still commission anything.
    kp: float = 400000.0    # W per m/s of error
    ki: float = 8000.0      # W per (m/s x s) of accumulated error


# ================================================================ control
class ControllerCore:
    """The PI speed law, the safety path and the toy plant.

    No Qt, no view: this class is what the hardware demo has to prove
    correct, and it runs unchanged whether or not a console is open.
    """

    def __init__(self) -> None:
        self.state = State()
        self.dt = 1.0 / CONTROL_HZ          # seconds of simulation
        self.integral = 0.0
        self.last_reasons: list[str] = []
        # The controller is inert until an engineer commissions the gains.
        self.armed = False

    def step(self) -> None:
        """One control period.

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
        else:
            s.power_w = 0.0
            s.service_brake = s.service_request

        self.enforce_safety()
        self._plant()

    def enforce_safety(self) -> None:
        """Run after the PI law and override it.

        Gains change how the train drives; they can never change whether
        it stops.
        """
        s = self.state

        # No authority is not an emergency. The train may not move,
        # and it comes to a stand on the service brake the way a
        # driver would stop it, in either mode.
        if s.authority_blocks <= 0:
            s.target_mps = 0.0
            s.power_w = 0.0
            self.integral = 0.0
            if s.actual_mps > 0.0:
                s.service_brake = True

        reasons = []
        if s.actual_mps > s.speed_limit_mps * 1.05:
            reasons.append("OVER SPEED LIMIT")
        if any(s.failures.values()):
            reasons.append("EQUIPMENT FAULT")
        if reasons or s.emergency_brake:
            s.emergency_brake = True
            s.power_w = 0.0
            self.integral = 0.0
        self.last_reasons = reasons

    def engage_emergency(self) -> None:
        """Engage now, without waiting for the next control tick.

        Guide section 7 calls the emergency brake immediate, so the
        safety path runs on the press rather than up to one control
        period later.
        """
        self.state.emergency_brake = True
        self.enforce_safety()

    def release_emergency(self) -> bool:
        """Latching. Release only when stopped with nothing still wrong.

        Asking a released brake to release is not a refusal: it is
        already where the caller wants it.
        """
        s = self.state
        if not s.emergency_brake:
            return True
        s.emergency_brake = False
        self.enforce_safety()
        if abs(s.actual_mps) < 0.1 and not self.last_reasons:
            s.emergency_brake = False
            return True
        s.emergency_brake = True
        return False

    def enter_block(self) -> None:
        """Spend one block of authority and step the signal ahead.

        The aspect the driver is running towards belongs to the next
        block, so entering one shows the next one's: red, yellow,
        green, super green, then round to red again. The Wayside
        Controller replaces this with the real aspect.
        """
        s = self.state
        s.authority_blocks = max(0, s.authority_blocks - 1)
        nxt = (ASPECTS.index(s.next_signal) + 1) % len(ASPECTS)
        s.next_signal = ASPECTS[nxt]

    def set_target_mps(self, mps: float) -> None:
        """Set the driver's target, in m/s, capped at the speed limit."""
        s = self.state
        if s.manual and s.authority_blocks > 0:
            s.target_mps = max(0.0, min(mps, s.speed_limit_mps))

    def _plant(self) -> None:
        """Toy physics until the Train Model is wired in.

            F = P / v     a = F / M     v = v + a dt

        No resistance term: the model is the block diagram and
        nothing else. One consequence worth knowing is that a train
        with no power applied coasts forever, so the only ways down
        are the two brakes, and the speed law holds its target from
        below rather than settling onto it from both sides.
        """
        # The door, brake and light states the Train Model reports are
        # not echoed from the commands here: with no Train Model
        # attached they are whatever the bench says they are, which is
        # the point of being able to disagree with the command.
        s = self.state
        v = s.actual_mps
        force = min(MAX_FORCE_N, s.power_w / max(v, V_FLOOR))
        a = force / MASS_KG
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

        # Distance only matters here as block progress: one block
        # entered is one block of authority spent.
        s.block_progress_m += s.actual_mps * self.dt
        while s.block_progress_m >= BLOCK_LENGTH_M:
            s.block_progress_m -= BLOCK_LENGTH_M
            self.enter_block()

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
    def spawn_train(self, number: int, line: str, target: str) -> str:
        """Put another train in the simulation and select it.

        The number is the operator's to choose; the prefix follows the
        line, which is how the CTC roster reads. Returns the id, or
        an empty string if that one is already running.
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
        core.state.authority_target = block_letter(target)
        self.cores[train_id] = core
        self.order.append(train_id)
        self.notes[train_id] = ""
        self.selected = train_id
        self.spawn_note = f"{train_id} spawned on the {line.lower()}."
        return train_id

    def _step_all(self) -> None:
        for core in self.cores.values():
            core.step()

    @property
    def has_train(self) -> bool:
        return self.selected in self.cores

    @property
    def core(self) -> ControllerCore:
        """The train the console and the bench are pointed at."""
        return self.cores[self.selected] if self.has_train else self.idle

    @property
    def brake_note(self) -> str:
        return self.notes.get(self.selected, "")

    @brake_note.setter
    def brake_note(self, text: str) -> None:
        self.notes[self.selected] = text

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
        return (self.has_train and self.operator == "driver"
                and self.core.state.manual)

    @Property("QVariantList", notify=snapshotChanged)
    def trains(self) -> list[dict[str, Any]]:
        """The roster the train selectors show."""
        return [{"id": i,
                 "line": self.cores[i].state.line,
                 "label": f"{i} \u00b7 {self.cores[i].state.line}"}
                for i in self.order]

    @Property("QVariantMap", notify=snapshotChanged)
    def snapshot(self) -> dict[str, Any]:
        """Every value the views read, rebuilt once per UI tick."""
        s = self.core.state
        return {
            "train_id": s.train_id,
            "has_train": self.has_train,
            "train_index": (self.order.index(self.selected)
                            if self.has_train else -1),
            "train_count": len(self.order),
            "sim_rate": self.sim_rate,
            "sim_rate_index": SIM_RATES.index(self.sim_rate),
            "spawn_note": self.spawn_note,
            "operator": self.operator,
            "operator_index": (self.ROLES.index(self.operator)
                               if self.signed_in else -1),
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
            # operator sees, so a reader can tell which side of the line
            # a value is on at a glance.
            # SI, for the Test view: these are the signals as they
            # cross the interface.
            "actual_mps": s.actual_mps,
            "commanded_mps": s.commanded_mps,

            "actual_mph": s.actual_mps * MPS_TO_MPH,
            "commanded_mph": s.commanded_mps * MPS_TO_MPH,
            "target_mph": s.target_mps * MPS_TO_MPH,
            "limit_mph": s.speed_limit_mps * MPS_TO_MPH,
            # Not a signal anybody sends or receives, just a number
            # to debug with, so it stays in SI (units.md).
            "accel_mps2": s.accel_mps2,
            "dial_hint": self._dial_hint(),
            "speed_source": "Driver" if s.manual else "From CTC",

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
            "fb_lights": s.fb_lights,
            "fb_headlights": s.fb_headlights,
            "beacon": s.beacon,

            # Identifiers, so they are shown as they are. The console
            # names the block to stop at; it does not count down a
            # distance, because authority is not a measurement.
            "authority_blocks": s.authority_blocks,
            "authority_target": s.authority_target,
            "current_block": s.current_block,

            "cabin_temp_f": c_to_f(s.cabin_temp_c),
            "target_temp_f": c_to_f(s.target_temp_c),
            # The Test view shows this interface in the unit it
            # travels in, which for temperature is Celsius.
            "cabin_temp_c": s.cabin_temp_c,
            "doors_left": s.doors_left,
            "doors_right": s.doors_right,
            "lights": s.lights,
            "headlights": s.headlights,

            "announcing": self.selected in self.announcing,
            "announce_label": self._announce_label(),

            "next_signal": s.next_signal,
            "signal_index": ASPECTS.index(s.next_signal),
            "signal_text": ASPECT_TEXT[s.next_signal],

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
        if self.selected in self.announcing:
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
        if index == 1 and self.core.armed:
            self._publish()
            return
        self.operator = self.ROLES[index] if 0 <= index < 2 else ""
        if self.operator == "engineer":
            self.gains_note = ""
        self._publish()

    @Slot(bool)
    def setManual(self, manual: bool) -> None:
        if not self.has_train:
            return
        if not self.signed_in:
            return
        self.core.state.manual = manual
        self._publish()

    @Slot(str)
    def selectTrain(self, train_id: str) -> None:
        """Point the console and the bench at another train."""
        if train_id in self.cores:
            self.selected = train_id
        self._publish()

    @Slot(int, str, str)
    def spawnTrain(self, number: int, line: str, target: str) -> None:
        """Add a train to the simulation and select it.

        It starts where every train starts: stopped, uncommissioned,
        with its own authority and destination, running its own plant
        from the next tick.
        """
        self.spawn_train(number, line, target)
        self._publish()

    @Slot(int)
    def setSimRate(self, index: int) -> None:
        """Run at real time or ten times real time.

        The tick rate does not change; the simulated seconds each tick
        advances do, so the control law and the plant keep their
        timestep relationship and only the clock moves faster.
        """
        if not 0 <= index < len(SIM_RATES):
            return
        self.sim_rate = SIM_RATES[index]
        for core in self.cores.values():
            core.dt = self.sim_rate / CONTROL_HZ
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
        if not self.has_train:
            return
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
        if not self.can_drive or self.selected in self.announcing:
            return
        train = self.selected
        self.announcing.add(train)
        QTimer.singleShot(ANNOUNCE_LOCKOUT_MS,
                          lambda: self._announce_done(train))
        self._publish()

    def _announce_done(self, train: str) -> None:
        self.announcing.discard(train)
        self._publish()

    # ------------------------------------------------- Train Model
    # Every signal the Train Model sends arrives through applyInputs,
    # as one coherent set rather than a slot per field. The bench
    # sends them in a batch, and so will the module.

    @Slot("QVariantMap")
    def applyInputs(self, values: dict) -> None:
        """Publish a whole set of staged inputs in one go.

        The Test view collects edits and sends them together, so the
        controller sees one coherent set of signals rather than a
        half-typed one. Each key is the signal name on the interface.
        """
        if not self.has_train:
            return
        s = self.core.state
        # The bench speaks the units the operator reads, like every
        # other view, and the conversion happens here with all the
        # others (documents/units.md). Counts and identifiers are not
        # measurements, so they arrive as they are.
        if "commanded_speed" in values:
            s.commanded_mps = max(0.0, float(values["commanded_speed"])
                                  / MPS_TO_MPH)
        if "speed_limit" in values:
            s.speed_limit_mps = max(0.0, float(values["speed_limit"])
                                    / MPS_TO_MPH)
        if "actual_speed" in values:
            s.actual_mps = max(0.0, float(values["actual_speed"])
                               / MPS_TO_MPH)
        if "cabin_temperature" in values:
            s.cabin_temp_c = f_to_c(float(values["cabin_temperature"]))
        if "authority_blocks" in values:
            s.authority_blocks = max(0, int(values["authority_blocks"]))
        # Gains come in with the rest of the set: sending the inputs
        # is what commissions them, so the bench needs no second
        # button for it. The engineer rule still holds, and they can
        # still only be set once.
        if ("kp" in values or "ki" in values) and not self.core.armed:
            self.commissionGains(float(values.get("kp", s.kp)),
                                 float(values.get("ki", s.ki)))
        if "beacon" in values:
            s.beacon = str(values["beacon"])
        for key, subsystem in (("failure_engine", "engine"),
                               ("failure_brake", "brake"),
                               ("failure_signal_pickup", "signal_pickup")):
            if key in values:
                s.failures[subsystem] = bool(values[key])
        if "signal_light_ahead" in values:
            aspect = str(values["signal_light_ahead"])
            if aspect in ASPECTS:
                s.next_signal = aspect
        if "ebrake_state" in values:
            wanted = bool(values["ebrake_state"])
            if wanted != s.emergency_brake:
                if wanted:
                    self.core.engage_emergency()
                else:
                    self.core.release_emergency()
        for key, attr in (("door_state_left", "fb_doors_left"),
                          ("door_state_right", "fb_doors_right"),
                          ("light_state_cabin", "fb_lights"),
                          ("light_state_headlights", "fb_headlights")):
            if key in values:
                setattr(s, attr, bool(values[key]))
        self._publish()


    @Slot(int)
    def setAuthorityBlocks(self, blocks: int) -> None:
        """Authority is how many blocks are left, not a length."""
        if not self.has_train:
            return
        self.core.state.authority_blocks = max(0, int(blocks))
        self._publish()

    @Slot(str)
    def setBeacon(self, text: str) -> None:
        if not self.has_train:
            return
        self.core.state.beacon = text
        self._publish()

    @Slot(str, bool)
    def setFailure(self, subsystem: str, failed: bool) -> None:
        if not self.has_train:
            return
        if subsystem in self.core.state.failures:
            self.core.state.failures[subsystem] = failed
        self._publish()

    @Slot(int)
    def setSignalAhead(self, index: int) -> None:
        if not self.has_train:
            return
        if 0 <= index < len(ASPECTS):
            self.core.state.next_signal = ASPECTS[index]
        self._publish()


    @Slot(str, bool)
    def setDoorState(self, side: str, open_: bool) -> None:
        if not self.has_train:
            return
        if side == "left":
            self.core.state.fb_doors_left = open_
        else:
            self.core.state.fb_doors_right = open_
        self._publish()

    @Slot(str, bool)
    def setLightState(self, which: str, on: bool) -> None:
        if not self.has_train:
            return
        if which == "headlights":
            self.core.state.fb_headlights = on
        else:
            self.core.state.fb_lights = on
        self._publish()

    @Slot(float, float)
    def commissionGains(self, kp: float, ki: float) -> None:
        """Commission the gains once, at start-up, and start the run.

        Gains are frozen afterwards and the engineer role is handed back
        to the driver a moment later, so the confirmation can be read.
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
        self.gains_note = (f"Set to Kp {s.kp:.0f}, Ki {s.ki:.0f}. "
                           "Fixed for this run.")
        QTimer.singleShot(GAINS_HANDOVER_MS, self._retire_engineer)
        self._publish()

    def _retire_engineer(self) -> None:
        """Close the gains dialog and hand the console to the driver."""
        self.operator = "driver"
        self._publish()

    # ----------------------------------------------------------- ticks
    def _tick(self) -> None:
        if self.core.armed:
            self.elapsed = self.elapsed.addMSecs(
                int(1000 / UI_HZ) * self.sim_rate)
        if self.core.state.emergency_brake and not self.brake_note:
            self.brake_note = ("Emergency brake engaged. "
                               "Release it from the same control.")
        self._publish()

    def _publish(self) -> None:
        self.snapshotChanged.emit()

# ================================================================ main
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true",
                        help="open the Train Model bench instead")
    parser.add_argument("--both", action="store_true",
                        help="open the console and the bench together")
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

    # Keep Python-side references so the objects are not garbage collected
    # while QML holds only C++ pointers to them.
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
    windows = {qml.stem: w
               for qml, w in zip(wanted, engine.rootObjects())}

    if args.check:
        shots = Path(args.shots) if args.shots else None
        code = run_check(app, windows["ConsoleWindow"],
                         windows["TestWindow"], backend, warnings, shots)
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