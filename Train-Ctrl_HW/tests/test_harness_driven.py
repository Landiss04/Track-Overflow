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

KP, KI = 400_000.0, 8_000.0


def report(
    emergency: bool = False,
    speed_mps: float = 0.0,
    commanded_mps: float = 10.0,
    service: bool = False,
) -> dict:
    """One tick's Train Model report, every key the fleet needs."""
    return {
        "commanded_speed": commanded_mps,
        "authority_blocks": 4,
        "actual_speed": speed_mps,
        "brake_state": [emergency, service],
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
        return self.fleet.step_all(TICK_S, {"G1": report(**values)})["G1"]

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

    def test_a_pull_after_the_echo_latches(self) -> None:
        self.brake_then_release()
        for _ in range(ECHO_TICKS):
            self.step(emergency=True)
        self.step(emergency=True)
        self.assertTrue(self.core.state.emergency_brake)

    def test_a_pull_while_running_latches_at_once(self) -> None:
        self.step(speed_mps=5.0)
        self.step(emergency=True, speed_mps=5.0)
        self.assertTrue(self.core.state.emergency_brake)

    def test_release_is_sent_once(self) -> None:
        self.brake_then_release()
        first = self.step(emergency=True)
        second = self.step(emergency=True)
        self.assertTrue(first.passenger_brake_release)
        self.assertFalse(first.emergency_brake)
        self.assertFalse(second.passenger_brake_release)

    def test_no_release_without_a_driver(self) -> None:
        commands = [self.step() for _ in range(5)]
        self.assertFalse(any(c.passenger_brake_release for c in commands))


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
        return self.fleet.step_all(TICK_S, {"G1": report(**values)})["G1"]

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
        fleet.step_all(TICK_S, {"G1": report(emergency=True)})
        self.assertTrue(core.release_emergency())
        fleet.step_all(TICK_S, {"G1": report(emergency=True)})
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
            "passenger_brake_release",
        })

    def test_engineer_option_commissions_each_new_train(self) -> None:
        reply = self.step({"G1": ("Green", report())})
        core = self.fleet.get("G1")
        self.assertTrue(core.armed)
        self.assertEqual((core.state.kp, core.state.ki), (KP, KI))
        self.assertGreater(reply["trains"]["G1"]["power_w"], 0.0)

    def test_bad_inputs_reject_the_tick(self) -> None:
        values = report()
        del values["brake_state"]
        with self.assertRaises(TickRejectedError):
            self.step({"G1": ("Green", values)})
        with self.assertRaises(TickRejectedError):
            self.process.step(1, TICK_S, 18_000.1, {"trains": []})


if __name__ == "__main__":
    unittest.main()
