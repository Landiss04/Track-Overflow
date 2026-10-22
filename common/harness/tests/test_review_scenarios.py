"""Repeatable review runs through the existing seven-process harness.

The longer two/three-train automatic runs are explicitly opt-in.
"""

from __future__ import annotations

import json
import os

import pytest

from common.harness.core import Harness
from common.harness.edges import SystemEdges
from common.harness.modules import (
    CTC_OFFICE,
    MODULE_NAMES,
    TRACK_CONTROLLER_SW,
    TRACK_CONTROLLER_HW,
    TRAIN_CONTROLLER_SW,
    TRAIN_CONTROLLER_HW,
    TRAIN_MODEL,
    system_specs,
)
from common.harness.tests.test_harness_system import wait_until
from utils.event_log import EventLog

FAULTS = {
    "TICK_REJECTED",
    "INPUTS_FAILED",
    "EDGES_FAILED",
    "PROTOCOL_ERROR",
    "UNEXPECTED_REPLY",
    "REPLY_LATE",
    "MODULE_DISCONNECTED",
    "MODULE_KILLED",
    "TRAIN_LEFT_TRACK",
    "TIME_SLIPPED",
}


def review_schedule(count):
    """Actual CTC schedule format, 180 simulated seconds between releases."""
    return {
        "time_unit": "s",
        "lines": [
            {
                "line": line,
                "trains": [
                    {
                        "train_id": str(i + 1),
                        "stops": [
                            {
                                "block_id": block,
                                "station": station,
                                "arrival_s": 180 * i,
                            },
                        ],
                    }
                    for i in range(count)
                ],
            }
            for line, prefix, block, station in (
                ("Green", "G", "65", "GLENBURY"),
                ("Red", "R", "16", "HERRON AVE"),
            )
        ],
    }


def run_review(tmp_path, count=1, scheduled=False):
    """Observe every train's station dwell, separation, and clean shutdown."""
    ctc = ["--run-on-ready", "--speedup-at-tick", "0"]
    if scheduled:
        schedule = tmp_path / "schedule.json"
        schedule.write_text(json.dumps(review_schedule(count)))
        ctc += ["--schedule", str(schedule)]
    else:
        ctc += ["--dispatch", "G1:Green:65", "--dispatch", "R1:Red:16"]
    options = {
        CTC_OFFICE: ctc,
        TRACK_CONTROLLER_SW: ["--load-starters"],
        TRACK_CONTROLLER_HW: ["--load-starters", "--test-pi", "process"],
        TRAIN_CONTROLLER_SW: ["--engineer-gains", "400000", "8000"],
        TRAIN_CONTROLLER_HW: [
            "--test-pi",
            "process",
            "--engineer-gains",
            "400000",
            "8000",
        ],
    }
    expected = {
        f"{prefix}{i + 1}": target
        for prefix, target in (("G", "65"), ("R", "16"))
        for i in range(count)
    }
    opened, dwell, paths, previous_authority, events, problems = (
        {},
        {},
        {},
        {},
        [],
        [],
    )
    with EventLog(tmp_path / "events.csv") as log:
        harness = Harness(system_specs(options), log, SystemEdges())
        harness.eventLogged.connect(lambda *event: events.append(event))

        def observe(tick, _duration):
            # Collect failures instead of raising through a Qt callback.
            reports = harness.outputs.get(TRAIN_MODEL, {}).get("trains", {})
            occupied = set()
            for train_id, report in reports.items():
                block, feed = report["track"]["block_id"], report["controller"]
                key = (train_id[0], block)
                if key in occupied:
                    problems.append((tick, "shared block", key))
                occupied.add(key)
                path = paths.setdefault(train_id, [])
                if path[-1:] != [block]:
                    path.append(block)
                if feed["emergency_brake_active"]:
                    problems.append((tick, train_id, "emergency brake"))
                authority = feed["authority_blocks"]
                before = previous_authority.get(train_id, 0)
                if before >= 2 and authority == 0:
                    problems.append(
                        (tick, train_id, "authority discontinuity", before)
                    )
                previous_authority[train_id] = authority
                doors = feed["door_left_open"] or feed["door_right_open"]
                if (
                    block == expected[train_id]
                    and abs(feed["actual_speed_mps"]) < 0.1
                    and doors
                ):
                    opened.setdefault(train_id, tick)
                    dwell[train_id] = (tick - opened[train_id] + 1) * 0.1
                elif train_id in opened and dwell.get(train_id, 0) < 45.0:
                    problems.append((tick, train_id, "interrupted dwell"))

        harness.tickCompleted.connect(observe)
        harness.start()
        try:
            assert wait_until(
                lambda: (
                    all(dwell.get(train, 0) >= 45.0 for train in expected)
                    or bool(harness.down_modules)
                    or bool(problems)
                ),
                timeout_s=180,
            ), (paths, dwell, events[-20:])
        finally:
            exits = harness.stop()
    assert not problems, problems[:10]
    assert all(dwell.get(train, 0) >= 45.0 for train in expected), (
        paths,
        dwell,
    )
    assert not [event for event in events if event[1] in FAULTS]
    assert exits == dict.fromkeys(MODULE_NAMES, 0)
    assert {event[2] for event in events if event[1] == "WAYSIDES_READY"} == {
        "Green",
        "Red",
    }
    assert sum(event[1] == "TRAIN_ADDED" for event in events) == len(expected)
    return paths, dwell


def test_manual_review_both_lines(tmp_path):
    run_review(tmp_path)


def test_scheduled_review_both_lines(tmp_path):
    run_review(tmp_path, scheduled=True)


@pytest.mark.skipif(
    os.environ.get("TRACK_OVERFLOW_MULTI_TRAIN") != "1",
    reason="set TRACK_OVERFLOW_MULTI_TRAIN=1 for slow review runs",
)
@pytest.mark.parametrize("count", [2, 3])
def test_scheduled_multiple_trains_each_line(count):
    # The same seven cores and prior-tick edges, with direct snapshots to
    # inspect failure latches and every reserved block of each authority.
    from common.harness.tests.test_harness_red_loop import RedLoop
    from ctc.schedule import parse_schedule
    from ctc.module_process import CtcOfficeProcess

    loop = RedLoop()
    loop.ctc_process = CtcOfficeProcess(loop.ctc_host, "unused", dispatches=())
    loop.ctc.load_schedule(parse_schedule(review_schedule(count)))
    loop.ctc_host.setAutomaticMode(True)
    expected = {
        f"{prefix}{i + 1}": target
        for prefix, target in (("G", "65"), ("R", "16"))
        for i in range(count)
    }
    opened, completed = {}, set()
    max_active = {"G": 0, "R": 0}
    for _ in range(9000):
        loop.step()
        reports = loop.outputs.get(TRAIN_MODEL, {}).get("trains", {})
        for prefix in max_active:
            max_active[prefix] = max(
                max_active[prefix], sum(t.startswith(prefix) for t in reports)
            )
        occupied = set()
        for train_id, report in reports.items():
            block, feed = report["track"]["block_id"], report["controller"]
            key = (train_id[0], block)
            assert key not in occupied, (loop.tick, train_id, key)
            occupied.add(key)
            fleet = (
                loop.controller_fleet
                if train_id.startswith("G")
                else loop.red_fleet
            )
            core = fleet.get(train_id) if train_id in fleet else None
            if core is not None:
                assert not core.state.emergency_brake, (
                    loop.tick,
                    train_id,
                    core.failed,
                )
                assert not core.state.failures["signal_pickup"], (
                    loop.tick,
                    train_id,
                )
            at_stop = (
                block == expected[train_id]
                and abs(feed["actual_speed_mps"]) < 0.1
                and (feed["door_left_open"] or feed["door_right_open"])
            )
            if at_stop:
                opened.setdefault(train_id, loop.tick)
                if (loop.tick - opened[train_id] + 1) * 0.1 >= 45.0:
                    completed.add(train_id)
            elif train_id in opened and train_id not in completed:
                pytest.fail(
                    f"{train_id} interrupted station dwell at tick {loop.tick}"
                )
        reserved = {}
        for authority in loop.ctc.snapshot().authorities:
            for block in authority.route[: authority.blocks + 1]:
                key = authority.line, block
                assert key not in reserved, (
                    loop.tick,
                    authority,
                    reserved.get(key),
                )
                reserved[key] = authority.train_id
        if completed == set(expected):
            break
    assert completed == set(expected), (
        completed,
        max_active,
        {
            train: report["track"]["block_id"]
            for train, report in reports.items()
        },
        loop.ctc.snapshot().scheduled_runs,
    )
    assert max_active == {"G": count, "R": count}, max_active
    assert not [event for event in loop.events if event[1] in FAULTS]


def test_review_cli_forwards_schedule_and_engineer_gains():
    from common.harness.app import _parse_args, _specs

    specs, _ = _specs(
        _parse_args(
            [
                "--schedule",
                "/tmp/review.json",
                "--engineer-gains",
                "400000",
                "8000",
            ]
        )
    )
    args = {spec.name: spec.args for spec in specs}
    assert args[CTC_OFFICE][-2:] == ("--schedule", "/tmp/review.json")
    for name in (TRAIN_CONTROLLER_SW, TRAIN_CONTROLLER_HW):
        index = args[name].index("--engineer-gains")
        values = args[name][index + 1:index + 3]
        assert values == ("400000.0", "8000.0")


@pytest.mark.skipif(
    os.environ.get("TRACK_OVERFLOW_MULTI_TRAIN") != "1",
    reason="set TRACK_OVERFLOW_MULTI_TRAIN=1 for slow review runs",
)
@pytest.mark.parametrize("count", [2, 3])
def test_green_scheduled_multiple_trains(count):
    """Check Green separately from the Red scheduling question."""
    from common.harness.tests.test_harness_train_loop import _Loop
    from ctc.schedule import parse_schedule

    loop = _Loop(dispatches=())
    schedule = review_schedule(count)
    schedule["lines"] = schedule["lines"][:1]
    loop.ctc.load_schedule(parse_schedule(schedule))
    loop.ctc_host.setAutomaticMode(True)
    expected = {f"G{i + 1}" for i in range(count)}
    opened, completed, max_active = {}, set(), 0
    for _ in range(24000):
        loop.step()
        reports = loop.outputs.get(TRAIN_MODEL, {}).get("trains", {})
        max_active = max(max_active, len(reports))
        reserved = set()
        for authority in loop.ctc.snapshot().authorities:
            blocks = set(authority.route[: authority.blocks + 1])
            assert not reserved.intersection(blocks), (loop.tick, authority)
            reserved.update(blocks)
        occupied = set()
        for train_id, report in reports.items():
            block, feed = report["track"]["block_id"], report["controller"]
            assert block not in occupied, (loop.tick, train_id, block)
            occupied.add(block)
            if train_id in loop.controller_fleet:
                core = loop.controller_fleet.get(train_id)
                assert not core.state.emergency_brake, (loop.tick, train_id)
                assert not core.state.failures["signal_pickup"], (
                    loop.tick,
                    train_id,
                )
            at_stop = (
                block == "65"
                and abs(feed["actual_speed_mps"]) < 0.1
                and (feed["door_left_open"] or feed["door_right_open"])
            )
            if at_stop:
                opened.setdefault(train_id, loop.tick)
                if (loop.tick - opened[train_id] + 1) * 0.1 >= 45:
                    completed.add(train_id)
            elif train_id in opened and train_id not in completed:
                pytest.fail(
                    f"{train_id} interrupted dwell at tick {loop.tick}"
                )
        if completed == expected:
            break
    assert max_active == count
    assert completed == expected, (
        completed,
        max_active,
        {t: r["track"]["block_id"] for t, r in reports.items()},
    )
    assert not [event for event in loop.events if event[1] in FAULTS]
