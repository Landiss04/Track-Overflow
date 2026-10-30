"""Seven real cores on the same prior-tick barrier, without serial."""

from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path

from common.harness.tests.test_harness_train_loop import (
    DT_S,
    START_S,
    KP,
    KI,
    _Loop,
    _wire,
    Dispatch,
)
from common.harness.edges import SystemEdges
from common.harness.modules import (
    CTC_OFFICE,
    MODULE_NAMES,
    TRACK_CONTROLLER_HW,
    TRACK_CONTROLLER_SW,
    TRACK_MODEL,
    TRAIN_MODEL,
    TRAIN_CONTROLLER_HW,
    TRAIN_CONTROLLER_SW,
)
from train_ctrl import ECHO_TICKS, TrainControllerFleet
from train_ctrl.module_process import TrainControllerProcess

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "TrackCtrlHw"))
from track_ctrl_hw.controller import HwTrackController  # noqa: E402
from track_ctrl_hw.territory import load_territory_file  # noqa: E402
from track_ctrl_hw.wire import inputs_from_wire, outputs_to_wire  # noqa: E402


class RedLoop(_Loop):
    """Mixed Green/SW and Red/HW scenario with measured core calls."""

    def __init__(self):
        super().__init__(
            dispatches=(
                Dispatch("G1", "Green", "65"),
                Dispatch("R1", "Red", "16"),
            )
        )
        self.edges = SystemEdges(wired=MODULE_NAMES)
        self.hw = HwTrackController()
        files = sorted((_ROOT / "TrackCtrlHw/data/waysides").glob("red*.json"))
        assert len(files) == 3, "Red test databases are required"
        for path in files:
            territory = load_territory_file(path)
            self.hw.load_territory(territory)
            program = _ROOT / "TrackCtrlHw/data/plc" / (path.stem + ".plc")
            self.hw.load_program(
                territory.wayside_id, program.read_text(), program.name
            )
        self.red_fleet = TrainControllerFleet(echo_ticks=ECHO_TICKS)
        self.red_controller = TrainControllerProcess(
            self.red_fleet,
            TRAIN_CONTROLLER_HW,
            "unused",
            engineer_gains=(KP, KI),
        )
        self.costs = {name: [] for name in MODULE_NAMES}
        self.output_bytes = {name: [] for name in MODULE_NAMES}
        self.first_train = {}
        self.red_blocks = []
        self.events_at = []
        self.red_open_tick = None
        self.red_close_tick = None

    def step(self):
        self.tick += 1
        now = START_S + self.tick * DT_S
        fresh = {}
        handlers = {
            CTC_OFFICE: self.ctc_process.step,
            TRACK_CONTROLLER_SW: self.wayside.step,
            TRACK_CONTROLLER_HW: lambda tick, dt, now, inputs: outputs_to_wire(
                self.hw.step(dt, inputs_from_wire(inputs))
            ),
            TRACK_MODEL: self.track_model.step,
            TRAIN_MODEL: self.model.step,
            TRAIN_CONTROLLER_SW: self.controller.step,
            TRAIN_CONTROLLER_HW: self.red_controller.step,
        }
        for name, handler in handlers.items():
            inputs = _wire(
                self.edges.inputs_for(name, self.tick, now, self.outputs)
            )
            started = time.perf_counter()
            fresh[name] = _wire(handler(self.tick, DT_S, now, inputs))
            self.costs[name].append(time.perf_counter() - started)
            self.output_bytes[name].append(
                len(json.dumps(fresh[name], separators=(",", ":")).encode())
            )
            field = "train_feeds" if name == TRACK_MODEL else "trains"
            if "R1" in fresh[name].get(field, {}):
                self.first_train.setdefault(name, self.tick)
        self.outputs.update(fresh)
        events = self.edges.tick_completed(self.tick, now, fresh)
        self.events += events
        self.events_at += [(self.tick, event) for event in events]
        report = self.outputs.get(TRAIN_MODEL, {}).get("trains", {}).get("R1")
        if report:
            block = report["track"]["block_id"]
            if self.red_blocks[-1:] != [block]:
                self.red_blocks.append(block)
        if "R1" in self.red_fleet:
            commands = self.outputs[TRAIN_CONTROLLER_HW]["trains"]["R1"]
            opened = any(commands["door_command"])
            if opened and self.red_open_tick is None:
                self.red_open_tick = self.tick
            if (
                not opened
                and self.red_open_tick is not None
                and self.red_close_tick is None
            ):
                self.red_close_tick = self.tick
            core = self.red_fleet.get("R1")
            assert not core.state.emergency_brake, (self.tick, core.failed)
            assert not core.state.failures["signal_pickup"], self.tick
        assert "R1" not in self.outputs.get(TRAIN_CONTROLLER_SW, {}).get(
            "trains", {}
        )
        assert "G1" not in self.outputs.get(TRAIN_CONTROLLER_HW, {}).get(
            "trains", {}
        )

    def red_stopped(self):
        report = self.outputs.get(TRAIN_MODEL, {}).get("trains", {}).get("R1")
        return bool(
            report
            and report["track"]["block_id"] == "16"
            and abs(report["controller"]["actual_speed_mps"]) < 0.1
            and (
                report["controller"]["door_left_open"]
                or report["controller"]["door_right_open"]
            )
        )


class RedRunTest(unittest.TestCase):
    def test_mixed_lines_dispatch_route_and_dwell(self):
        loop = RedLoop()
        self.assertTrue(
            loop.run_until(loop.red_stopped, limit_s=240),
            (loop.red_blocks, loop.ctc.snapshot()),
        )
        self.assertEqual(
            loop.red_blocks, [str(number) for number in range(9, 17)]
        )
        ticks = [
            loop.first_train[name]
            for name in (TRACK_MODEL, TRAIN_MODEL, TRAIN_CONTROLLER_HW)
        ]
        self.assertEqual(ticks, list(range(ticks[0], ticks[0] + 3)))
        self.assertTrue(loop.at_rest_with_doors_open)
        self.assertFalse(loop.controller_fleet.get("G1").state.emergency_brake)
        self.assertIn(
            (TRACK_CONTROLLER_HW, "WAYSIDES_READY", "Red"), loop.events
        )
        # Ask to depart immediately; the core must still hold 45 seconds.
        loop.ctc.dispatch("R1", "Red", "21")
        self.assertTrue(
            loop.run_until(lambda: loop.red_close_tick is not None, limit_s=60)
        )
        self.assertGreaterEqual(
            (loop.red_close_tick - loop.red_open_tick) * DT_S, 45.0
        )
        print(
            "RED_DWELL="
            + json.dumps(
                {
                    "opened_tick": loop.red_open_tick,
                    "closed_tick": loop.red_close_tick,
                    "duration_s": (loop.red_close_tick - loop.red_open_tick)
                    * DT_S,
                }
            )
        )
        self.assertFalse(
            any(
                event[1] in {"TICK_REJECTED", "TRAIN_LEFT_TRACK"}
                for event in loop.events
            )
        )
        metrics = {
            name: {
                "ticks": len(loop.costs[name]),
                "mean_core_ms": 1000
                * sum(loop.costs[name])
                / len(loop.costs[name]),
                "max_core_ms": 1000 * max(loop.costs[name]),
                "p50_core_ms": 1000
                * sorted(loop.costs[name])[len(loop.costs[name]) // 2],
                "p95_core_ms": 1000
                * sorted(loop.costs[name])[int(len(loop.costs[name]) * 0.95)],
                "mean_output_bytes": sum(loop.output_bytes[name])
                / len(loop.output_bytes[name]),
                "max_output_bytes": max(loop.output_bytes[name]),
            }
            for name in MODULE_NAMES
        }
        print("RED_LOOP_METRICS=" + json.dumps(metrics, sort_keys=True))
