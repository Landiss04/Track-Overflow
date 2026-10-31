"""The Train Controller as the central harness drives it.

Covers what changes when the harness steps the fleet instead of the
console: the Train Model's reports of a command come back two ticks
late, a driver's release of the emergency brake must not be undone by
the report of the brake from before it, the release is passed on to
the Train Model once, and the module process follows the harness's
roster.

Run from this folder (``Train-Ctrl_HW``)::

    python -m pytest tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_HERE))
sys.path.insert(1, str(_HERE.parent))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from train_ctrl import (  # noqa: E402
    ECHO_TICKS,
    TICK_S,
    TrainControllerFleet,
)
from train_ctrl.control import ControllerCore  # noqa: E402
from train_ctrl.module_process import TrainControllerProcess  # noqa: E402
from utils.module_link import TickRejectedError  # noqa: E402

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])

#: The simulation time each step is at: the shared clock's start, 05:00
#: (truth D017).
_START_S = 5 * 3600.0

KP, KI = 400_000.0, 8_000.0


def report(
    emergency: bool = False,
    speed_mps: float = 0.0,
    commanded_mps: float | None = 10.0,
    service: bool = False,
    authority: int | None = 4,
) -> dict:
    """One tick's Train Model report, every key the fleet needs."""
    return {
        "commanded_speed": commanded_mps,
        "authority_blocks": authority,
        "actual_speed": speed_mps,
        "emergency_brake_state": emergency,
        "service_brake_state": service,
        "door_state": [False, False],
        "light_state": [True, True],
        "cabin_temperature": 21.0,
    }


def arm(core: ControllerCore) -> None:
    """Commission a train, as the engineer would."""
    core.state.kp, core.state.ki = KP, KI
    core.armed = True


class EchoTest(unittest.TestCase):
    """A report of the controller's own brake is not a passenger
    pull."""

    def setUp(self) -> None:
        self.fleet = TrainControllerFleet(echo_ticks=ECHO_TICKS)
        self.core = self.fleet.add("G1", "Green")
        arm(self.core)

    def step(self, **values: Any) -> Any:
        """Step the train on one report; return its commands."""
        return self.fleet.step_all(
            TICK_S, {"G1": report(**values)}, _START_S)["G1"]

    def brake_then_release(self) -> None:
        """Engage at a stand, let the brake show, then release it."""
        self.core.engage_emergency()
        for _ in range(3):
            self.step(emergency=True)
        self.assertTrue(self.core.release_emergency())

    def test_release_survives_the_echo_of_the_brake(self) -> None:
        self.brake_then_release()
        # The Train Model reports the brake for two more ticks: the
        # commands it acted on were sent before the release.
        for _ in range(ECHO_TICKS):
            self.step(emergency=True)
            self.assertFalse(self.core.state.emergency_brake)

    def test_a_new_pull_after_the_echo_latches(self) -> None:
        # A pull is the brake turning on while the controller is not
        # commanding it (control.py): clear once, then on again.
        self.brake_then_release()
        for _ in range(ECHO_TICKS):
            self.step(emergency=True)
        self.step()
        self.step(emergency=True)
        self.assertTrue(self.core.state.emergency_brake)

    def test_a_pull_while_running_latches_at_once(self) -> None:
        self.step(speed_mps=5.0)
        self.step(emergency=True, speed_mps=5.0)
        self.assertTrue(self.core.state.emergency_brake)

    # No passenger brake release is sent: the Train Model holds a pull
    # until the emergency brake command goes off (#25, closed).


class SignalPickupTest(unittest.TestCase):
    """A null Track Signal is a signal pickup failure; a valid 0 is
    not (Kevin Schillinger 2026-10-28; Braden's request 9)."""

    def setUp(self) -> None:
        self.fleet = TrainControllerFleet(echo_ticks=ECHO_TICKS)
        self.core = self.fleet.add("G1", "Green")
        arm(self.core)

    def step(self, **values: Any) -> Any:
        """Step the train on one report; return its commands."""
        return self.fleet.step_all(
            TICK_S, {"G1": report(**values)}, _START_S)["G1"]

    def test_a_valid_stop_is_not_a_pickup_failure(self) -> None:
        # Running with 4 blocks, then authority and speed cut to 0 at
        # once: a stop order, not a lost signal.
        for _ in range(3):
            self.step(speed_mps=8.0)
        for _ in range(3):
            self.step(speed_mps=8.0, commanded_mps=0.0, authority=0)
            self.assertFalse(self.core.state.failures["signal_pickup"])

    def test_null_is_a_pickup_failure(self) -> None:
        for key in ("commanded_mps", "authority"):
            with self.subTest(null=key):
                self.setUp()
                self.step(speed_mps=8.0)
                commands = self.step(speed_mps=8.0, **{key: None})
                self.assertTrue(self.core.state.failures["signal_pickup"])
                self.assertTrue(commands.emergency_brake)
                self.assertEqual(commands.power_w, 0.0)
                self.assertEqual((self.core.commanded_mps,
                                  self.core.authority_blocks), (0.0, 0))

    def test_pickup_failure_resolves_when_the_signal_returns(self) -> None:
        # Resolved on the first tick both arrive non-null (BUGS.md B1);
        # the emergency brake stays on until the driver releases it.
        self.step(speed_mps=8.0)
        self.step(speed_mps=8.0, commanded_mps=None, authority=None)
        self.step(speed_mps=0.0, commanded_mps=None)
        self.assertTrue(self.core.state.failures["signal_pickup"])
        commands = self.step(speed_mps=0.0, commanded_mps=6.0, authority=3)
        self.assertFalse(self.core.state.failures["signal_pickup"])
        self.assertEqual((self.core.commanded_mps,
                          self.core.authority_blocks), (6.0, 3))
        self.assertTrue(commands.emergency_brake)


class LowerLimitAheadTest(unittest.TestCase):
    """A train entering a slower block too fast brakes at once.

    The CTC Office does not slow a train ahead of a lower limit; the
    Train Controller slows it down as soon as it is in the slower
    block (Kevin Schillinger, 2026-10-21, Q-P4-4). The commanded speed
    carries the block's limit (REQUIREMENTS.md M1). Green 66 to 67:
    18 m/s commanded in 66, 10 m/s in 67 (40 km/h).
    """

    def setUp(self) -> None:
        self.fleet = TrainControllerFleet(echo_ticks=ECHO_TICKS)
        self.core = self.fleet.add("G1", "Green")
        arm(self.core)
        # Running in the faster block at its commanded speed.
        for _ in range(5):
            commands = self.step(speed_mps=17.9, commanded_mps=18.0)
        self.assertFalse(commands.service_brake)
        self.assertGreater(commands.power_w, 0.0)

    def step(self, **values: Any) -> Any:
        """Step the train on one report; return its commands."""
        return self.fleet.step_all(
            TICK_S, {"G1": report(**values)}, _START_S)["G1"]

    def test_brakes_on_the_first_tick_in_the_slower_block(self) -> None:
        commands = self.step(speed_mps=17.9, commanded_mps=10.0)
        self.assertTrue(commands.service_brake)
        self.assertEqual(commands.power_w, 0.0)
        self.assertFalse(commands.emergency_brake)

    def test_holds_the_service_brake_until_under_the_limit(self) -> None:
        speed = 17.9
        while speed > 10.0:
            commands = self.step(speed_mps=speed, commanded_mps=10.0,
                                 service=True)
            self.assertTrue(commands.service_brake)
            self.assertEqual(commands.power_w, 0.0)
            self.assertFalse(commands.emergency_brake)
            speed -= 1.2 * TICK_S
        commands = self.step(speed_mps=9.9, commanded_mps=10.0,
                             service=True)
        self.assertFalse(commands.service_brake)
        self.assertFalse(self.core.state.emergency_brake)


class ConsoleFleetTest(unittest.TestCase):
    """The console's own fleet reads reports as answering this step."""

    def test_a_report_right_after_a_release_latches(self) -> None:
        fleet = TrainControllerFleet()
        core = fleet.add("G1", "Green")
        arm(core)
        core.engage_emergency()
        fleet.step_all(TICK_S, {"G1": report(emergency=True)}, _START_S)
        self.assertTrue(core.release_emergency())
        fleet.step_all(TICK_S, {"G1": report()}, _START_S)
        fleet.step_all(TICK_S, {"G1": report(emergency=True)}, _START_S)
        self.assertTrue(core.state.emergency_brake)


class ModuleProcessTest(unittest.TestCase):
    """The process steps the fleet on the harness's roster."""

    def setUp(self) -> None:
        self.fleet = TrainControllerFleet(echo_ticks=ECHO_TICKS)
        self.process = TrainControllerProcess(
            self.fleet, "train-controller-sw", "unused",
            engineer_gains=(KP, KI),
        )
        self.addCleanup(self.process.deleteLater)

    def step(self, trains: dict[str, Any]) -> dict[str, Any]:
        """One STEP with these trains' reports."""
        return self.process.step(1, TICK_S, 18_000.1, {"trains": {
            train_id: {"line": line, "inputs": values}
            for train_id, (line, values) in trains.items()
        }})

    def test_roster_follows_the_inputs(self) -> None:
        self.step({"G1": ("Green", report()), "G2": ("Green", report())})
        self.assertEqual(self.fleet.ids(), ["G1", "G2"])
        self.step({"G2": ("Green", report())})
        self.assertEqual(self.fleet.ids(), ["G2"])

    def test_reply_carries_every_command(self) -> None:
        reply = self.step({"G1": ("Green", report())})
        self.assertEqual(set(reply["trains"]["G1"]), {
            "power_w", "service_brake", "emergency_brake", "door_command",
            "light_command", "temperature_setpoint_c", "announcement",
            "power_verified",
        })

    def test_engineer_option_commissions_each_new_train(self) -> None:
        reply = self.step({"G1": ("Green", report())})
        core = self.fleet.get("G1")
        self.assertTrue(core.armed)
        self.assertEqual((core.state.kp, core.state.ki), (KP, KI))
        self.assertGreater(reply["trains"]["G1"]["power_w"], 0.0)

    def test_bad_inputs_reject_the_tick(self) -> None:
        values = report()
        del values["service_brake_state"]
        with self.assertRaises(TickRejectedError):
            self.step({"G1": ("Green", values)})
        with self.assertRaises(TickRejectedError):
            self.process.step(1, TICK_S, 18_000.1, {"trains": []})


if __name__ == "__main__":
    unittest.main()
