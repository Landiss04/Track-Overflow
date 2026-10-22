"""The Qt bridge: one snapshot out to QML, one slot per operator action."""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

<<<<<<< HEAD
from PySide6.QtCore import (Property, QObject, Qt, QTime, QTimer, Signal,
                            Slot)

from .constants import (ANNOUNCE_LOCKOUT_MS, ASPECTS, ASPECT_TEXT,
                        CABIN_MAX_F, CABIN_MIN_F, CLOCK_START, FAILURES,
                        FAILURE_TEXT, GAINS_HANDOVER_MS, LINES, MAX_POWER_W,
                        MAX_SPEED_MPS,
                        SIM_RATES, TICK_S, UI_HZ)
=======
from PySide6.QtCore import Property, QObject, Qt, QTimer, Signal, Slot

from .constants import (ASPECTS, ASPECT_TEXT,
                        CABIN_MAX_F, CABIN_MIN_F, CLOCK_START_S, FAILURES,
                        FAILURE_TEXT, GAINS_HANDOVER_MS, LINES, MAX_POWER_W,
                        MAX_SPEED_MPS,
                        SIM_RATES, TICK_S, UI_HZ)
from .bench_sim import SimTrain
>>>>>>> origin/Train_Ctrl_integration
from .control import ControllerCore
from .errors import InvalidInputError
from .fleet import TrainControllerFleet
from .inputs import _read_number, read_inputs
from .state import TrainModelCommands
from .units import MPS_TO_MPH, W_TO_KW, c_to_f, f_to_c


<<<<<<< HEAD
=======
def _clock_text(time_s: float) -> str:
    """Show a system time as the time of day, HH:mm:ss."""
    seconds = int(time_s) % 86400
    return (f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:"
            f"{seconds % 60:02d}")


>>>>>>> origin/Train_Ctrl_integration
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
<<<<<<< HEAD
=======
    DRIVER_INDEX = ROLES.index("driver")
>>>>>>> origin/Train_Ctrl_integration
    ENGINEER_INDEX = ROLES.index("engineer")

    def __init__(self, parent: QObject | None = None, *,
                 fleet: TrainControllerFleet | None = None) -> None:
        super().__init__(parent)
        # Standalone, the console owns its fleet and steps every train
        # with the toy plant. Given the central harness's fleet, the
        # harness adds, removes and steps the trains; the console only
        # shows them and takes the operator's actions.
        self._owns_fleet = fleet is None
        self.fleet = fleet if fleet is not None else TrainControllerFleet()
        self._roster: tuple[str, ...] = tuple(self.fleet.ids())
        self.selected = self._roster[0] if self._roster else ""
        self.notes: dict[str, str] = {}
<<<<<<< HEAD
        self.announcing: set[str] = set()
=======
>>>>>>> origin/Train_Ctrl_integration
        self.sim_rate = 1
        self.paused = False
        self.bench_error = ""
        self.spawn_note = ""
        self._last_commands: dict[str, TrainModelCommands] = {}
<<<<<<< HEAD

        self.operator: str = ""         # "" | "driver" | "engineer"
        self.gains_note = ""
        self.elapsed = QTime(*CLOCK_START)
=======
        # Standalone, the bench stands in for the rest of the system:
        # one simulated train per controller, and the bench clock.
        # Given a harness fleet there are none; the harness sends the
        # signals and the time (REQUIREMENTS.md M0, M11).
        self.sims: dict[str, SimTrain] = {}
        self.time_s = CLOCK_START_S
        # The bench clock starts when the first train is commissioned
        # and then always runs, whichever train is selected
        # (REQUIREMENTS.md M11).
        self._clock_started = False

        self.operator: str = ""         # "" | "driver" | "engineer"
        self.gains_note = ""
>>>>>>> origin/Train_Ctrl_integration

        # Nothing runs until somebody spawns it. This one is never
        # stepped and never shown: it exists so that the snapshot and
        # the views have a shape to read while the roster is empty,
        # rather than every binding needing a null check.
        self.idle = ControllerCore()

        if self._owns_fleet:
            # Precise, because at 10x a tick is every 10 ms.
            self._control = QTimer(self)
            self._control.setTimerType(Qt.TimerType.PreciseTimer)
            self._control.timeout.connect(self._step_all)
            self._control.start(self._tick_ms())

        self._ui = QTimer(self)
        self._ui.timeout.connect(self._tick)
        self._ui.start(int(1000 / UI_HZ))

    # ---------------------------------------------------------- fleet
    def add_train(self, number: int, line: str, target: str) -> str:
<<<<<<< HEAD
        """Put another train in the simulation and select it.
=======
        """Put another train in the simulation.
>>>>>>> origin/Train_Ctrl_integration

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
        core.state.authority_target = normalize_block_letter(target)
<<<<<<< HEAD
        self.notes[train_id] = ""
        self.selected = train_id
=======
        if self._owns_fleet:
            self.sims[train_id] = SimTrain()
        self.notes[train_id] = ""
        # The console stays on the train it shows; only the first train
        # is selected for it.
        if not self.has_train:
            self.selected = train_id
>>>>>>> origin/Train_Ctrl_integration
        self.spawn_note = f"{train_id} spawned on the {line.lower()}."
        self._sync_roster()
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
<<<<<<< HEAD
        self.announcing.discard(train_id)
        self._last_commands.pop(train_id, None)
=======
        self._last_commands.pop(train_id, None)
        self.sims.pop(train_id, None)
>>>>>>> origin/Train_Ctrl_integration
        if self.selected == train_id:
            remaining = self.fleet.ids()
            self.selected = (
                remaining[min(index, len(remaining) - 1)]
                if remaining else ""
            )
        self.spawn_note = f"{train_id} removed."
        self._sync_roster()
        return True
    
    def _sync_roster(self) -> None:
        # The harness changes the fleet without telling the console,
        # so the roster is compared once per UI tick.
        ids = tuple(self.fleet.ids())
        if ids == self._roster:
            return
        self._roster = ids
        if self.selected not in self.fleet:
            self.selected = ids[0] if ids else ""
        self.roster_changed.emit()

    def _step_all(self) -> None:
<<<<<<< HEAD
        if self.paused:
            return
        # The clock is simulated time, one step per tick, once the
        # selected train is running.
        if self.core.armed:
            self.elapsed = self.elapsed.addMSecs(round(TICK_S * 1000))
        for core in self.fleet:
            train_id = core.state.train_id
            core.step()
            commands = core.commands()
=======
        # The bench drives the fleet the way the harness does: every
        # train's signals from its simulation, one step_all with the
        # bench clock, and the commands back into the simulation.
        if self.paused:
            return
        # The bench clock is simulated time, one step per tick.
        if not self._clock_started:
            self._clock_started = any(core.armed for core in self.fleet)
        if self._clock_started:
            self.time_s += TICK_S
        inputs = {train_id: sim.outputs()
                  for train_id, sim in self.sims.items()}
        all_commands = self.fleet.step_all(TICK_S, inputs, self.time_s)
        for train_id, commands in all_commands.items():
            self.sims[train_id].step(commands)
>>>>>>> origin/Train_Ctrl_integration
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
<<<<<<< HEAD
=======
    def sim(self) -> SimTrain | None:
        """The bench's simulation of the selected train, if it has one."""
        return self.sims.get(self.selected)

    @property
>>>>>>> origin/Train_Ctrl_integration
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
        exception: see can_ebrake.
        """
        return (
            self.has_train
            and self.operator == "driver"
            and self.core.state.manual
        )

    @property
    def can_ebrake(self) -> bool:
        """Whether the emergency brake answers: the driver, any mode.

        Only the driver engages or releases it from the cab (the
        engineer only commissions the gains). A passenger pull still
        latches it through the Train Model, whoever is signed in.
        """
        return self.has_train and self.operator == "driver"

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
<<<<<<< HEAD
=======
        sim = self.sim
>>>>>>> origin/Train_Ctrl_integration
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
            "paused": self.paused,
            "bench_error": self.bench_error,
            "spawn_note": self.spawn_note,
            "operator": self.operator,
            "operator_index": (
                self.ROLES.index(self.operator) if self.signed_in else -1
            ),
            "signed_in": self.signed_in,
            "manual": s.manual,
            "mode_label": "Manual" if s.manual else "Automatic",
            "can_drive": self.can_drive,
            "can_ebrake": self.can_ebrake,
            "armed": self.core.armed,
            # Gains are commissioned once per train, so both of these
            # follow that train's controller rather than the console.
            "gains_locked": self.core.armed,
            "gains_note": self.gains_note,
<<<<<<< HEAD
            "clock": self.elapsed.toString("HH:mm:ss"),
=======
            # The system time the controller last received.
            "clock": _clock_text(s.time_s),
>>>>>>> origin/Train_Ctrl_integration

            # Converted here and nowhere else. Keys carry the unit the
            # operator sees, so a reader can tell which side of the
            # line a value is on at a glance.
            "actual_mph": s.actual_mps * MPS_TO_MPH,
            # What the controller reads and acts on, so a lost Track
            # Signal shows as the zero it is driving to.
            "commanded_mph": self.core.commanded_mps * MPS_TO_MPH,
            # A fixed full scale for the dial, whatever is commanded.
            "dial_max_mph": MAX_SPEED_MPS * MPS_TO_MPH,
<<<<<<< HEAD
            # What the Track Model sent, before the pickup: the bench's
            # rows follow these.
            "track_commanded_mph": s.commanded_mps * MPS_TO_MPH,
            "target_mph": s.target_mps * MPS_TO_MPH,
            # Shown in SI by the team's choice for this module, a
            # deliberate departure from units.md's ft/s^2.
            "accel_mps2": s.accel_mps2,
=======
            # What the bench sends as the Track Model's, before its
            # injected pickup failure; under a harness, what arrived.
            "track_commanded_mph": (
                sim.commanded_mps if sim else s.commanded_mps) * MPS_TO_MPH,
            "target_mph": s.target_mps * MPS_TO_MPH,
            # Shown in SI by the team's choice for this module, a
            # deliberate departure from units.md's ft/s^2. Not a signal
            # the controller receives: the bench simulation's, and 0
            # under a harness (debug drawer, REQUIREMENTS.md M12).
            "accel_mps2": sim.accel_mps2 if sim else 0.0,
>>>>>>> origin/Train_Ctrl_integration
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
<<<<<<< HEAD
            # Injected into the toy plant from the bench (Murphy).
            "inject_engine": s.injected["engine"],
            "inject_brake": s.injected["brake"],
            "inject_pickup": s.injected["signal_pickup"],
=======
            # Injected into the bench's simulation (Murphy).
            "inject_engine": bool(sim and sim.injected["engine"]),
            "inject_brake": bool(sim and sim.injected["brake"]),
            "inject_pickup": bool(sim and sim.injected["signal_pickup"]),
            "bench_at_station": bool(sim and sim.at_station),
            # Whether the bench keeps the clock (no harness).
            "bench_clock": self._owns_fleet,
>>>>>>> origin/Train_Ctrl_integration
            "fb_doors_left": s.fb_doors_left,
            "fb_doors_right": s.fb_doors_right,
            "fb_interior_lights": s.fb_interior_lights,
            "fb_exterior_lights": s.fb_exterior_lights,
            "fb_emergency_brake": s.fb_emergency_brake,
            "fb_service_brake": s.fb_service_brake,
            "beacon_station": s.beacon_station,
            "beacon_side": s.beacon_side,
            "beacon_underground": s.beacon_underground,
<<<<<<< HEAD
            "platform_left": self.core.platform_on("left"),
            "platform_right": self.core.platform_on("right"),
            "at_stand": self.core.at_stand,
=======
            "may_open_left": self.core.may_open("left"),
            "may_open_right": self.core.may_open("right"),
>>>>>>> origin/Train_Ctrl_integration
            "station_hold": self.core.station_hold,
            "announcement": s.announcement,

            # Identifiers and counts, so they are shown as they are.
            "authority_blocks": self.core.authority_blocks,
<<<<<<< HEAD
            "track_authority_blocks": s.authority_blocks,
=======
            "track_authority_blocks": (
                sim.authority_blocks if sim else s.authority_blocks),
>>>>>>> origin/Train_Ctrl_integration
            "authority_target": s.authority_target,

            "cabin_temp_f": c_to_f(s.cabin_temp_c),
            "target_temp_f": c_to_f(s.target_temp_c),
            "doors_left": s.doors_left,
            "doors_right": s.doors_right,
            "interior_lights": s.interior_lights,
            "exterior_lights": s.exterior_lights,

<<<<<<< HEAD
            "announcing": (self.selected in self.announcing
                           or bool(s.announcement)),
=======
            "announcing": bool(s.announcement),
            "can_announce": self.core.can_repeat,
>>>>>>> origin/Train_Ctrl_integration
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
<<<<<<< HEAD
        return (f"{names[0].upper()}{names[1:]}. Driving and brake "
                "release resume once it clears.")
=======
        return (f"{names[0].upper()}{names[1:]}. Driving resumes once "
                "it clears.")
>>>>>>> origin/Train_Ctrl_integration

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
        # The controller only sends the command; the Train Model
        # makes the announcement (REQUIREMENTS.md M7).
<<<<<<< HEAD
        if (self.selected in self.announcing
                or self.core.state.announcement):
            return "Announcement sent"
        if self.operator == "driver" and not self.core.state.manual:
            return "Sent automatically on approach"
        return "Send station announcement"
=======
        if self.core.state.announcement:
            return "Announcement sent"
        if self.operator == "driver" and not self.core.state.manual:
            return "Sending automatically"
        if not self.core.last_announcement:
            return "Nothing to repeat yet"
        return "Repeat last announcement"
>>>>>>> origin/Train_Ctrl_integration

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
<<<<<<< HEAD
=======
        # Nobody drives a train before its gains are set: the driver's
        # console stays hidden until the engineer commissions it.
        if index == self.DRIVER_INDEX and self.has_train \
                and not self.core.armed:
            self._publish()
            return
>>>>>>> origin/Train_Ctrl_integration
        in_range = 0 <= index < len(self.ROLES)
        self.operator = self.ROLES[index] if in_range else ""
        if self.operator == "engineer":
            self.gains_note = ""
        self._publish()

    @Slot(bool)
    def set_manual(self, manual: bool) -> None:
        """Switch the selected train between Manual and Automatic.

<<<<<<< HEAD
        Refused while a failure is up: the train is being stopped,
        and nothing may hand it back a speed until the failure clears.
        """
        if not self.has_train or not self.signed_in:
            return
        if self.core.failed:
            self._publish()
            return
=======
        Allowed during a failure too, so the driver can reach Manual to
        try the train, the service brake say, and see whether a failure
        has been resolved. The failure still holds the target at 0 and
        the emergency brake on in whichever mode the train is.
        """
        if not self.has_train or not self.signed_in:
            return
>>>>>>> origin/Train_Ctrl_integration
        self.core.state.manual = manual
        self._publish()

    @Slot(str)
    def select_train(self, train_id: str) -> None:
<<<<<<< HEAD
        """Point the console and the bench at another train."""
        if train_id in self.fleet:
            self.selected = train_id
=======
        """Point the console and the bench at another train.

        A train whose gains are not set yet signs the driver out: its
        console stays hidden until the engineer commissions it.
        """
        if train_id in self.fleet:
            self.selected = train_id
            if self.operator == "driver" and not self.core.armed:
                self.operator = ""
>>>>>>> origin/Train_Ctrl_integration
        self._publish()

    @Slot(int, str, str)
    def spawn_train(self, number: int, line: str, target: str) -> None:
<<<<<<< HEAD
        """Add a train to the simulation and select it.
=======
        """Add a train to the simulation, keeping the selection.
>>>>>>> origin/Train_Ctrl_integration

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

        The step never changes (TICK_S, truth D006 / D017); ten times
        real time runs ten times as many ticks a second.
        """
        if not 0 <= index < len(SIM_RATES):
            return
        self.sim_rate = SIM_RATES[index]
        if self._owns_fleet:
            self._control.setInterval(self._tick_ms())
        self._publish()

    @Slot(bool)
    def set_paused(self, paused: bool) -> None:
        """Hold or resume the whole simulation: every train, the clock.

        Commands pressed while paused are kept and act on the first
        tick after resuming.
        """
        self.paused = bool(paused)
        self._publish()

    def _tick_ms(self) -> int:
        # Wall-clock milliseconds between control ticks.
        return max(1, round(1000 * TICK_S / self.sim_rate))

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
<<<<<<< HEAD
        train is stopped and no failure is latched. The driver only.
=======
        train is stopped, and, with a failure latched, unless it is in
        Manual. The driver only.
>>>>>>> origin/Train_Ctrl_integration
        """
        if not self.can_ebrake:
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
<<<<<<< HEAD
        elif self.core.failed:
            names = ", ".join(FAILURE_TEXT[n] for n in self.core.failed)
            self.brake_note = f"Cannot release: {names} is still active."
        else:
            self.brake_note = "Cannot release: the train is still moving."
=======
        elif not self.core.at_stand:
            self.brake_note = "Cannot release: the train is still moving."
        else:
            names = ", ".join(FAILURE_TEXT[n] for n in self.core.failed)
            self.brake_note = f"Release it in Manual: {names} is still active."
>>>>>>> origin/Train_Ctrl_integration
        self._publish()

    @Slot()
    def toggle_service_brake(self) -> None:
        """Apply or release the driver's service brake request.

<<<<<<< HEAD
        Refused while a brake failure is latched: the service brake
        is the one that failed.
        """
        if not self.can_drive or self.core.state.failures["brake"]:
=======
        Also under a brake failure, so the driver can try the brake
        (REQUIREMENTS.md M4).
        """
        if not self.can_drive:
>>>>>>> origin/Train_Ctrl_integration
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
<<<<<<< HEAD
=======
        self._answer_press()
>>>>>>> origin/Train_Ctrl_integration
        self._publish()

    @Slot(bool)
    def set_interior_lights(self, on: bool) -> None:
        """Command the interior lights on or off."""
        if not self.can_drive:
            return
        self.core.command_lights(on, self.core.state.exterior_lights)
<<<<<<< HEAD
=======
        self._answer_press()
>>>>>>> origin/Train_Ctrl_integration
        self._publish()

    @Slot(bool)
    def set_exterior_lights(self, on: bool) -> None:
        """Command the exterior lights on or off."""
        if not self.can_drive:
            return
        self.core.command_lights(self.core.state.interior_lights, on)
<<<<<<< HEAD
        self._publish()

    @Slot()
    def announce(self) -> None:
        """Send the station announcement command, then lock out."""
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

=======
        self._answer_press()
        self._publish()

    def _answer_press(self) -> None:
        # The bench's train acts on a pressed tile even when the command
        # is unchanged, so a door or light state the bench published
        # never locks the driver out. A real Train Model follows the
        # command every tick.
        if self.sim is not None:
            self.sim.answer_next()

    @Slot()
    def announce(self) -> None:
        """Repeat the last automatic announcement, in Manual.

        Held for the lockout on system time, as the automatic ones are
        (REQUIREMENTS.md M7, M11).
        """
        if not self.can_drive:
            return
        self.core.repeat_announcement()
        self._publish()

    # ------------------------------------------------------- bench
    # The bench edits its simulation, never the controller: what it
    # sets reaches the controller on the next tick, through step_all,
    # as the harness's signals do (REQUIREMENTS.md M0).

    @Slot(str)
    def set_bench_time(self, text: str) -> None:
        """Set the bench clock to a time of day, HH:MM or HH:MM:SS.

        For testing what follows the time (REQUIREMENTS.md M8). Stays on
        the current simulated day; the controllers receive it on the
        next tick. Under a harness the harness's clock is the time, so
        this does nothing.
        """
        if not self._owns_fleet:
            return
        parts = str(text).strip().split(":")
        try:
            numbers = [int(part) for part in parts]
        except ValueError:
            numbers = []
        if (len(numbers) not in (2, 3) or not 0 <= numbers[0] < 24
                or not all(0 <= n < 60 for n in numbers[1:])):
            self.bench_error = f"time must be HH:MM or HH:MM:SS, not {text!r}"
            self._publish()
            return
        hours, minutes, seconds = (numbers + [0])[:3]
        day = int(self.time_s // 86400)
        self.time_s = day * 86400 + hours * 3600 + minutes * 60 + seconds
        self.bench_error = ""
        self._publish()

    @Slot()
    def bench_block_change(self) -> None:
        """Stand in for the Track Model as the train enters a block.

        Integrated, the Train Model reports the block change to the
        Track Model, which then sends the next block's authority; the
        controller only ever sees the new count. The bench sends the
        same from the next tick: one block fewer, never below 0
        (REQUIREMENTS.md M16).
        """
        if self.sim is not None:
            self.sim.block_change()
            self._publish()

>>>>>>> origin/Train_Ctrl_integration
    @Slot("QVariantMap")
    def apply_bench_inputs(self, values: dict) -> None:
        """Apply the bench's edited rows, or refuse them all and say why.

        A value that cannot be read leaves everything as it was and
        shows one message on the bench, in the shared Callout
        (REQ-INTF-004), rather than raising out of a Qt slot.
        """
        try:
            self._apply_bench(values)
        except InvalidInputError as error:
            self.bench_error = str(error)
        else:
            self.bench_error = ""
        self._publish()

    def _apply_bench(self, values: dict) -> None:
        """Take the bench's edited rows, convert, and apply them.

        The bench is a view, so it speaks the operator's units (mph,
        Fahrenheit) and one row per element. This converts once, here
<<<<<<< HEAD
        on the display side, and hands apply_inputs the SI signals in
        their truth shapes. Gains are not set here: the engineer's
        pop-up on the console commissions them.
        """
        if not self.has_train:
            return
        s = self.core.state
=======
        on the display side, checks the SI signals with read_inputs(),
        and hands them to the bench's simulation. Gains are not set
        here: the engineer's pop-up on the console commissions them.
        """
        sim = self.sim
        if sim is None:
            if self.has_train:
                raise InvalidInputError(
                    "the bench drives only trains it spawned, not a "
                    "harness's")
            return
>>>>>>> origin/Train_Ctrl_integration
        si: dict[str, Any] = {}
        for key in ("commanded_speed", "actual_speed"):
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
<<<<<<< HEAD
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
=======
        # The failure rows are Murphy injecting into the simulation,
        # not a signal: the controller has to detect them.
        injected = {name: bool(values[f"failure_{name}"])
                    for name in FAILURES if f"failure_{name}" in values}
        # Whether the train is at a station is the bench's: it decides
        # whether the beacon is heard (bench_sim.py).
        at_station = (bool(values["at_station"])
                      if "at_station" in values else sim.at_station)
        # The bench's emergency row is a passenger pull.
        if "emergency_brake_state" in values:
            si["emergency_brake_state"] = bool(
                values["emergency_brake_state"])
        groups = (
            ("door_state",
             ("door_state_left", "door_state_right"),
             [sim.door_left, sim.door_right]),
            ("light_state",
             ("light_state_interior", "light_state_exterior"),
             [sim.interior_lights, sim.exterior_lights]),
>>>>>>> origin/Train_Ctrl_integration
        )
        for signal, rows, current in groups:
            if any(row in values for row in rows):
                si[signal] = [bool(values.get(row, now))
                              for row, now in zip(rows, current)]
<<<<<<< HEAD
        if "brake_state" in si:
            # The bench stands in for a passenger pull only; the
            # service element is what the controller itself commanded.
            si["brake_state"].append(s.fb_service_brake)
        self.apply_inputs(si)
        s.injected.update(injected)
        # Clearing a failure on the bench is what resolves it; setting
        # one only injects it, and the controller has to find it.
=======
        sim.apply(read_inputs(si))
        sim.injected.update(injected)
        sim.at_station = at_station
        # Clearing a failure on the bench resolves it in the controller
        # too, until the controller can see resolution for itself
        # (REQUIREMENTS.md M5, OPEN_ISSUES.md #23).
>>>>>>> origin/Train_Ctrl_integration
        for name, on in injected.items():
            if not on:
                self.core.clear_failure(name)

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
        self._sync_roster()
<<<<<<< HEAD
        if not self._owns_fleet and self.core.armed and not self.paused:
            # An outside harness steps the trains; until it owns the
            # clock too (D017) the console estimates it from here.
            self.elapsed = self.elapsed.addMSecs(
                int(1000 / UI_HZ) * self.sim_rate)
=======
>>>>>>> origin/Train_Ctrl_integration
        if self.core.state.emergency_brake and not self.brake_note:
            self.brake_note = (
                "Emergency brake engaged. "
                "Release it from the same control."
            )
        self._publish()

    def _publish(self) -> None:
        self.snapshot_changed.emit()