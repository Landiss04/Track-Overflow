"""Real seven-module processes with two explicitly simulated Pi processes."""
from __future__ import annotations

import json

import pytest

from common.harness.tests.test_harness_system import wait_until
from common.harness.core import Harness
from common.harness.edges import SystemEdges
from common.harness.modules import (
    CTC_OFFICE, MODULE_NAMES, TRACK_CONTROLLER_SW, TRACK_CONTROLLER_HW,
    TRAIN_CONTROLLER_SW, TRAIN_CONTROLLER_HW, TRAIN_MODEL, system_specs,
)
from utils.event_log import EventLog


def run_hw_system(log_path, fault_module=None, fault_options=()):
    options = {
        CTC_OFFICE: ["--run-on-ready", "--speedup-at-tick", "0",
                     "--dispatch", "G1:Green:65", "--dispatch", "R1:Red:16"],
        TRACK_CONTROLLER_SW: ["--load-starters"],
        TRACK_CONTROLLER_HW: ["--test-pi", "process", "--load-starters",
                              "--pi-log", str(log_path.with_name("track-pi.jsonl"))],
        TRAIN_CONTROLLER_SW: ["--engineer-gains", "400000", "8000"],
        TRAIN_CONTROLLER_HW: ["--test-pi", "process", "--engineer-gains", "400000", "8000",
                              "--pi-log", str(log_path.with_name("train-pi.jsonl"))],
    }
    if fault_module:
        options[fault_module] += list(fault_options)
    events = []
    blocks = {"G1": [], "R1": []}
    final = {}
    stopped = set()
    with EventLog(log_path) as log:
        harness = Harness(system_specs(options), log,
                          SystemEdges())
        harness.eventLogged.connect(lambda source, event, detail:
                                    events.append((source, event, detail)))
        def on_tick(tick, duration):
            outputs = harness.outputs
            for train_id, target in (("G1", "65"), ("R1", "16")):
                report = outputs.get(TRAIN_MODEL, {}).get("trains", {}).get(train_id)
                if report:
                    block = report["track"]["block_id"]
                    if blocks[train_id][-1:] != [block]:
                        blocks[train_id].append(block)
                    feed = report["controller"]
                    assert not feed["emergency_brake_active"], (train_id, tick)
                    if (block == target and abs(feed["actual_speed_mps"]) < 0.1
                            and (feed["door_left_open"] or feed["door_right_open"])):
                        stopped.add(train_id)
            assert "R1" not in outputs.get(TRAIN_CONTROLLER_SW, {}).get("trains", {})
            assert "G1" not in outputs.get(TRAIN_CONTROLLER_HW, {}).get("trains", {})
            final.update(outputs)
        harness.tickCompleted.connect(on_tick)
        harness.start()
        try:
            assert wait_until(
                lambda: len(stopped) == 2 or bool(harness.down_modules),
                timeout_s=60,
            ), events
            assert len(stopped) == 2, events
        finally:
            exits = harness.stop()
    return events, blocks, exits, final


def test_all_seven_real_modules_with_explicit_simulated_pis(tmp_path, capfd):
    events, blocks, exits, _ = run_hw_system(tmp_path / "events.csv")
    assert blocks == {"G1": ["63", "64", "65"],
                      "R1": [str(number) for number in range(9, 17)]}
    assert exits == dict.fromkeys(MODULE_NAMES, 0)
    assert (TRACK_CONTROLLER_HW, "WAYSIDES_READY", "Red") in events
    faults = {"TICK_REJECTED", "INPUTS_FAILED", "EDGES_FAILED", "PROTOCOL_ERROR",
              "UNEXPECTED_REPLY", "REPLY_LATE", "MODULE_DISCONNECTED"}
    assert not [entry for entry in events if entry[1] in faults]
    assert capfd.readouterr().err == ""


@pytest.mark.parametrize("fault", ["--pi-reboot-at-tick", "--pi-drop-after"])
def test_pi_loss_holds_then_recovers_pending_step(tmp_path, capfd, fault):
    events, blocks, exits, _ = run_hw_system(
        tmp_path / "events.csv", TRACK_CONTROLLER_HW, (fault, "20"),
    )
    late = [entry for entry in events if entry[1] == "REPLY_LATE"]
    recovered = [entry for entry in events if entry[1] == "LATE_REPLY_RECEIVED"]
    assert len(late) == len(recovered) == 1
    assert late[0][0] == recovered[0][0] == TRACK_CONTROLLER_HW
    assert events.index(late[0]) < events.index(recovered[0])
    assert blocks["R1"] == [str(number) for number in range(9, 17)]
    assert exits == dict.fromkeys(MODULE_NAMES, 0)
    trail = (tmp_path / "track-pi.jsonl").read_text()
    for event in ("PI_LOST", "PI_HELLO", "PI_REPLAYED", "PI_RESEND_PENDING",
                  "PI_RECOVERED"):
        assert event in trail
    agent_log = (tmp_path / "track-pi.agent.log").read_text()
    assert "CACHE_HIT ('STEP'," in agent_log
    records = [json.loads(line) for line in
               (tmp_path / "track-pi.agent.jsonl").read_text().splitlines()]
    step_ticks = [record["request"]["tick"] for record in records
                  if record.get("request", {}).get("op") == "STEP"]
    assert step_ticks.count(20) == 1
    assert len(step_ticks) == len(set(step_ticks))
    assert not [entry for entry in events if entry[1] in {
        "TICK_REJECTED", "PROTOCOL_ERROR", "UNEXPECTED_REPLY", "MODULE_DISCONNECTED"
    }]
    assert capfd.readouterr().err == ""
