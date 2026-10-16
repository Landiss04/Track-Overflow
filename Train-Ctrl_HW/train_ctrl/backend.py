"""The Qt bridge: one snapshot out to QML, one slot per operator action."""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

from PySide6.QtCore import Property, QObject, QTime, QTimer, Signal, Slot

from .constants import (ANNOUNCE_LOCKOUT_MS, ASPECTS, ASPECT_TEXT,
                        CABIN_MAX_F, CABIN_MIN_F, CONTROL_HZ, FAILURES,
                        FAILURE_TEXT, GAINS_HANDOVER_MS, LINES, MAX_POWER_W,
                        SIM_RATES, UI_HZ)
from .control import ControllerCore
from .fleet import TrainControllerFleet
from .inputs import _read_number, read_inputs
from .state import TrainModelCommands
from .units import MPS_TO_MPH, W_TO_KW, c_to_f, f_to_c


def normalize_block_letter(text: str) -> str:
    """Return the letter of a block typed by the operator.

    They type "a", "A", or whatever is quickest; the backend keeps
    identifiers in one case so comparisons elsewhere are not a trap
    (see identifiers.md).
    """
    letters = [c for c in str(text) if c.isalpha()]
    return letters[0].upper() if letters else "A"


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
        # One controller per train, each with its own toy plant here.
        # They all run; the console and the bench look at whichever
        # one is selected.
        self.fleet = TrainControllerFleet()
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
        if train_id in self.fleet:
            self.spawn_note = f"{train_id} is already running."
            return ""

        core = self.fleet.add(train_id, line)
        core.dt = self.sim_rate / CONTROL_HZ
        core.state.authority_target = normalize_block_letter(target)
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
        if train_id not in self.fleet:
            return False
        index = self.fleet.ids().index(train_id)
        self.fleet.remove(train_id)
        self.notes.pop(train_id, None)
        self.announcing.discard(train_id)
        self._last_commands.pop(train_id, None)
        if self.selected == train_id:
            remaining = self.fleet.ids()
            self.selected = (
                remaining[min(index, len(remaining) - 1)]
                if remaining else ""
            )
        self.spawn_note = f"{train_id} removed."
        self.roster_changed.emit()
        return True

    def _step_all(self) -> None:
        for core in self.fleet:
            train_id = core.state.train_id
            core.step()
            commands = core.commands()
            if self._last_commands.get(train_id) != commands:
                self._last_commands[train_id] = commands
                self.commands_changed.emit(
                    {"train_id": train_id, **asdict(commands)})

    @property
    def has_train(self) -> bool:
        """Whether a train is selected."""
        return self.selected in self.fleet

    @property
    def core(self) -> ControllerCore:
        """The train the console and the bench are pointed at."""
        return self.fleet.get(self.selected) if self.has_train else self.idle

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
        return [{"id": core.state.train_id,
                 "line": core.state.line,
                 "label": f"{core.state.train_id} · {core.state.line}"}
                for core in self.fleet]

    @Property("QVariantMap", notify=snapshot_changed)
    def snapshot(self) -> dict[str, Any]:
        """Every value the views read, rebuilt once per UI tick."""
        s = self.core.state
        return {
            "train_id": s.train_id,
            "has_train": self.has_train,
            "train_index": (
                self.fleet.ids().index(self.selected)
                if self.has_train else -1
            ),
            "train_count": len(self.fleet),
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
            # What the controller reads and acts on, so a lost Track
            # Signal shows as the zero it is driving to.
            "commanded_mph": self.core.commanded_mps * MPS_TO_MPH,
            # What the Track Model sent, before the pickup: the bench's
            # rows follow these.
            "track_commanded_mph": s.commanded_mps * MPS_TO_MPH,
            "target_mph": s.target_mps * MPS_TO_MPH,
            "limit_mph": s.speed_limit_mps * MPS_TO_MPH,
            # Shown in SI by the team's choice for this module, a
            # deliberate departure from units.md's ft/s^2.
            "accel_mps2": s.accel_mps2,
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
            # Detected and latched by this controller.
            "faulted": any(s.failures.values()),
            "fault_engine": s.failures["engine"],
            "fault_brake": s.failures["brake"],
            "fault_pickup": s.failures["signal_pickup"],
            # Injected into the toy plant from the bench (Murphy).
            "inject_engine": s.injected["engine"],
            "inject_brake": s.injected["brake"],
            "inject_pickup": s.injected["signal_pickup"],
            "fb_doors_left": s.fb_doors_left,
            "fb_doors_right": s.fb_doors_right,
            "fb_interior_lights": s.fb_interior_lights,
            "fb_exterior_lights": s.fb_exterior_lights,
            "fb_emergency_brake": s.fb_emergency_brake,
            "fb_service_brake": s.fb_service_brake,
            "beacon_station": s.beacon_station,
            "beacon_side": s.beacon_side,
            "beacon_underground": s.beacon_underground,
            "platform_left": self.core.platform_on("left"),
            "platform_right": self.core.platform_on("right"),
            "announcement": s.announcement,

            # Identifiers and counts, so they are shown as they are.
            "authority_blocks": self.core.authority_blocks,
            "track_authority_blocks": s.authority_blocks,
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
        if train_id in self.fleet:
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
        for core in self.fleet:
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
        train is stopped and no failure is latched.
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
        """Apply or release the driver's service brake request.

        Refused while a brake failure is latched: the service brake
        is the one that failed.
        """
        if not self.can_drive or self.core.state.failures["brake"]:
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
        if train in self.fleet:
            self.fleet.get(train).state.announcement = ""
        self._publish()

    # ------------------------------------------------- Train Model
    # Every signal the Train Model sends arrives through apply_inputs,
    # in SI and in the shapes truth signals/ gives, as one coherent
    # set rather than a slot per field. The bench reaches it through
    # apply_bench_inputs, which converts from the operator's units.

    @Slot("QVariantMap")
    def apply_inputs(self, values: dict) -> None:
        """Take a whole set of Train Model signals in one go, in SI.

        See read_inputs() for the keys. A set with one bad value
        changes nothing.
        """
        if not self.has_train:
            return
        self.core.apply_staged(read_inputs(values))
        self._publish()

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
        # The failure rows are Murphy injecting into the toy plant, not
        # a Train Model signal: the controller has to detect them.
        injected = {name: bool(values[f"failure_{name}"])
                    for name in FAILURES if f"failure_{name}" in values}
        groups = (
            ("brake_state",
             ("brake_state_emergency",),
             [s.fb_emergency_brake]),
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
        if "brake_state" in si:
            # The bench stands in for a passenger pull only; the
            # service element is what the controller itself commanded.
            si["brake_state"].append(s.fb_service_brake)
        commission = ("kp" in values or "ki" in values
                      ) and not self.core.armed
        if commission:
            kp = _read_number(values, "kp") if "kp" in values else s.kp
            ki = _read_number(values, "ki") if "ki" in values else s.ki
        self.apply_inputs(si)
        s.injected.update(injected)
        # Clearing a failure on the bench is what resolves it; setting
        # one only injects it, and the controller has to find it.
        for name, on in injected.items():
            if not on:
                self.core.clear_failure(name)
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