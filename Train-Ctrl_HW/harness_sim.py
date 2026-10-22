"""A stand-in central harness, for trying the fleet before D005 exists.

It owns a TrainControllerFleet, spawns and removes trains on a
schedule, and plays the Train Model: each tick it sends every train
its signals, takes back its commands, and turns them into motion.
The console window shows whatever trains it has.

    python harness_sim.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(1, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from train_ctrl import (  # noqa: E402
<<<<<<< HEAD
    EBRAKE_DECEL_MPS2, MASS_KG, MAX_FORCE_N, MPS_TO_MPH, SERVICE_DECEL_MPS2,
    TICK_S, V_FLOOR_MPS, TrainControllerFleet, TrainModelCommands, f_to_c,
=======
    CLOCK_START_S, EBRAKE_DECEL_MPS2, MASS_KG, MAX_FORCE_N, MPS_TO_MPH,
    SERVICE_DECEL_MPS2, TICK_S, V_FLOOR_MPS, TrainControllerFleet,
    TrainModelCommands, f_to_c,
>>>>>>> origin/Train_Ctrl_integration
)
from train_ctrl.app import run  # noqa: E402

DT_S = TICK_S                   # one harness tick, truth D017's 0.1 s
COMMANDED_MPS = 55 / MPS_TO_MPH     # 55 mph
CABIN_TEMP_C = f_to_c(75)           # 75 °F
AUTHORITY_BLOCKS = 20
SIGNAL_AHEAD = "GREEN"

class StandInHarness:
    """Spawns trains and plays a minimal Train Model for each."""

    def __init__(self, fleet: TrainControllerFleet) -> None:
        self.fleet = fleet
        self.speed: dict[str, float] = {}
        self.last: dict[str, TrainModelCommands] = {}
<<<<<<< HEAD
=======
        # Stands in for utils/system_clock.py: seconds since midnight,
        # from 05:00:00, one tick at a time.
        self.time_s = CLOCK_START_S
>>>>>>> origin/Train_Ctrl_integration

    def spawn(self, train_id: str) -> None:
        core = self.fleet.add(train_id, "GREEN LINE")
        self.speed[train_id] = 0.0
        print(f"spawned {train_id}: {len(self.fleet)} train controllers")

    def retire(self, train_id: str) -> None:
        self.fleet.remove(train_id)
        self.speed.pop(train_id, None)
        self.last.pop(train_id, None)
        print(f"removed {train_id}: {len(self.fleet)} train controllers")

    def tick(self) -> None:
        inputs = {}
        for train_id in self.fleet.ids():
            last = self.last.get(train_id)
            inputs[train_id] = {
                "commanded_speed": COMMANDED_MPS,
                "actual_speed": self.speed[train_id],
                # The key read_inputs() reads; "cabin_temp" was ignored.
                "cabin_temperature": CABIN_TEMP_C,
                "authority_blocks": AUTHORITY_BLOCKS,
                "signal_light_ahead": SIGNAL_AHEAD,
                # Echo the service brake so it is not taken for a
                # failure. Emergency is reported only for a passenger
                # pull, which this stand-in never makes.
<<<<<<< HEAD
                "brake_state": [False, bool(last and last.service_brake)],
=======
                "emergency_brake_state": False,
                "service_brake_state": bool(last and last.service_brake),
>>>>>>> origin/Train_Ctrl_integration
                # The fleet wants the full set every tick; doors and
                # lights simply do what they were last told.
                "door_state": (list(last.door_command) if last
                               else [False, False]),
                "light_state": (list(last.light_command) if last
                                else [True, True]),
            }
<<<<<<< HEAD
        commands = self.fleet.step_all(DT_S, inputs)
=======
        self.time_s += DT_S
        commands = self.fleet.step_all(DT_S, inputs, self.time_s)
>>>>>>> origin/Train_Ctrl_integration
        for train_id, cmd in commands.items():
            self.last[train_id] = cmd
            v = self.speed[train_id]
            if cmd.emergency_brake:
                a = -EBRAKE_DECEL_MPS2
            elif cmd.service_brake:
                a = -SERVICE_DECEL_MPS2
            else:
                a = min(MAX_FORCE_N, cmd.power_w / max(v, V_FLOOR_MPS)) / MASS_KG
            self.speed[train_id] = max(0.0, v + a * DT_S)


def main() -> int:
    app = QGuiApplication(sys.argv)  # noqa: F841  (run() reuses it)
    fleet = TrainControllerFleet()
    harness = StandInHarness(fleet)

    clock = QTimer()
    clock.timeout.connect(harness.tick)
    clock.start(int(DT_S * 1000))

    harness.spawn("T-1")
    QTimer.singleShot(5_000, lambda: harness.spawn("T-2"))
    QTimer.singleShot(10_000, lambda: harness.spawn("T-3"))
    QTimer.singleShot(30_000, lambda: harness.retire("T-1"))

    # The console only: the bench would spawn trains the harness does
    # not know about, and the next step_all would refuse them.
    return run(console=True, bench=False, fleet=fleet)


if __name__ == "__main__":
    raise SystemExit(main())