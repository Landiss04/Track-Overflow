"""Bounded CTC-2 observations, not station/admission policy acceptance.

Run with TRACK_OVERFLOW_GREEN_OWNER_DIAGNOSTICS=1. The existing loop,
schedule and prior-tick wiring are unchanged. Only selected observations
are retained. This does not exercise process links or physical Pis.
"""

from __future__ import annotations

from dataclasses import asdict
import json
import os

import pytest

from common.harness.tests.test_harness_train_loop import DT_S, _Loop
from common.harness.tests.test_review_scenarios import FAULTS, review_schedule
from common.harness.modules import (  # noqa: E402
    CTC_OFFICE,
    TRAIN_MODEL,
    TRAIN_CONTROLLER_SW,
)
from ctc.schedule import parse_schedule  # noqa: E402
from ctc.scheduler import HELD, TO_YARD  # noqa: E402

MAX_TICKS = 24000
GRANT_PROPAGATION_TICKS = 3


def _observation(loop):
    """Read the current boundary; PLC replay has no live side effects.

    Fresh CTC outputs and the SW input image differ by one tick. Train
    Model snapshot.inputs is the input actually consumed, rather than a
    recomputed edge (which could advance edge bookkeeping).
    """
    auto = loop.ctc._auto
    plans = {plan.train_id: plan for plan in auto.plans}
    controller = loop.wayside_state.system.controllers["GTC-03"]
    image = controller.build_scan_inputs(controller.inputs)
    raw = controller.program.scan(image).values
    suggestions = loop.outputs[CTC_OFFICE]["track_controller"]["suggestions"]
    trains = {}
    reports = loop.outputs.get(TRAIN_MODEL, {}).get("trains", {})
    for train_id in ("G2", "G3"):
        if train_id not in reports or train_id not in loop.controller_fleet:
            continue
        report = reports[train_id]
        feed = report["controller"]
        inputs = loop.model_fleet.get(train_id)._model.snapshot().inputs
        core = loop.controller_fleet.get(train_id)
        commands = loop.outputs[TRAIN_CONTROLLER_SW]["trains"][train_id]
        trains[train_id] = {
            "front_block": report["track"]["block_id"],
            "front_offset_m": report["track"]["offset_m"],
            "speed_mps": feed["actual_speed_mps"],
            "model_signal": asdict(inputs.track.track_signal),
            "track_info": asdict(inputs.track.track_info),
            "beacon": (
                asdict(inputs.track.beacon) if inputs.track.beacon else None
            ),
            "retained_beacon": [
                core.state.beacon_station,
                core.state.beacon_side,
            ],
            "scheduled_station_block": plans[train_id].stops[0].block_id,
            "on_scheduled_station": report["track"]["block_id"] == "65",
            "door_commands": [
                inputs.controller.door_left_open,
                inputs.controller.door_right_open,
            ],
            "controller_door_commands": list(commands["door_command"]),
            "model_doors": [feed["door_left_open"], feed["door_right_open"]],
        }
    owners = {
        zone: [plan.train_id for plan in auto.plans if auto._holds(plan, zone)]
        for zone in sorted(set(auto.zones["Green"].values()))
    }
    return {
        "tick": loop.tick,
        "elapsed_s": loop.tick * DT_S,
        "phase": {
            train: progress.status for train, progress in auto.progress.items()
        },
        "zone_owners": owners,
        "g2_clear_to_yard": auto._clear(
            plans["G2"], auto.progress["G2"], plans["G2"].yard_index
        ),
        "ctc_suggestions": [
            entry
            for entry in suggestions
            if entry["block_id"] in ("64", "65", "66")
        ],
        "sw_suggestions": {
            block: asdict(value)
            for block, value in controller.inputs.suggestions.items()
            if block in ("64", "65", "66")
        },
        "sw_image": {
            f"OCC_{block}": image[f"OCC_{block}"]
            for block in ("64", "65", "66")
        },
        "sw_raw": {
            f"AUTH_{block}": raw[f"AUTH_{block}"]
            for block in ("64", "65", "66")
        },
        "sw_circuits": {
            block: asdict(controller.outputs.track_circuits[block])
            for block in ("64", "65", "66")
            if block in controller.outputs.track_circuits
        },
        "sw_overrides": [
            asdict(override) for override in controller.outputs.overrides
        ],
        "trains": trains,
    }


def capture_green_owner_diagnostics(max_ticks=MAX_TICKS):
    """Return a bounded packet of first-transition observations.

    Stop after the first subsequent CTC grant crosses the three prior-tick
    edges to the Train Model. No completion or policy fix is inferred.
    """
    assert 0 < max_ticks <= MAX_TICKS
    loop = _Loop(dispatches=())
    schedule = review_schedule(3)
    schedule["lines"] = schedule["lines"][:1]
    loop.ctc.load_schedule(parse_schedule(schedule))
    loop.ctc_host.setAutomaticMode(True)
    packet = {}
    previous = None
    opened, completed = {}, set()
    max_active = 0
    for _ in range(max_ticks):
        loop.step()
        reports = loop.outputs.get(TRAIN_MODEL, {}).get("trains", {})
        max_active = max(max_active, len(reports))
        reserved, occupied = set(), set()
        for authority in loop.ctc.snapshot().authorities:
            blocks = set(authority.route[: authority.blocks + 1])
            assert not reserved.intersection(blocks), (loop.tick, authority)
            reserved.update(blocks)
        for train_id, report in reports.items():
            block, feed = report["track"]["block_id"], report["controller"]
            assert block not in occupied, (loop.tick, train_id, block)
            occupied.add(block)
            assert not feed["emergency_brake_active"], (loop.tick, train_id)
            if train_id in loop.controller_fleet:
                core = loop.controller_fleet.get(train_id)
                assert not core.state.emergency_brake, (loop.tick, train_id)
                assert not core.state.failures["signal_pickup"], (
                    loop.tick,
                    train_id,
                )
            doors = feed["door_left_open"] or feed["door_right_open"]
            if doors:
                assert abs(feed["actual_speed_mps"]) < 0.1
                assert (
                    loop.outputs[TRAIN_CONTROLLER_SW]["trains"][train_id][
                        "power_w"
                    ]
                    == 0
                )
            # Preserve the existing Green probe's dwell assertion.
            # Approach-door eligibility remains an owner question, not a
            # newly accepted station-arrival interpretation.
            at_stop = (
                block == "65" and abs(feed["actual_speed_mps"]) < 0.1 and doors
            )
            if at_stop:
                opened.setdefault(train_id, loop.tick)
                if (loop.tick - opened[train_id] + 1) * DT_S >= 45:
                    completed.add(train_id)
            elif train_id in opened and train_id not in completed:
                pytest.fail(
                    f"{train_id} interrupted dwell at tick {loop.tick}"
                )
        # No need for detailed snapshots before G2 has a controller.
        if "G2" not in loop.controller_fleet:
            continue
        current = _observation(loop)
        if "reservation_hold" not in packet and current["phase"]["G2"] == HELD:
            packet["reservation_before"] = previous
            packet["reservation_hold"] = current
        pair = current["trains"]
        if (
            "first_hold" not in packet
            and set(pair) == {"G2", "G3"}
            and pair["G2"]["front_block"] == "65"
            and pair["G3"]["front_block"] == "64"
            and all(abs(train["speed_mps"]) < 0.01 for train in pair.values())
        ):
            packet["hold_before"] = previous
            packet["first_hold"] = current
        positive = any(
            entry["block_id"] == "65" and entry["authority_blocks"] > 0
            for entry in current["ctc_suggestions"]
        )
        if (
            "first_hold" in packet
            and "grant" not in packet
            and positive
            and current["phase"]["G2"] == TO_YARD
        ):
            packet["grant_before"] = previous
            packet["grant"] = current
        if "grant" in packet:
            since_grant = loop.tick - packet["grant"]["tick"]
            if since_grant in (1, 2):
                packet[f"grant_plus_{since_grant}"] = current
            if since_grant == GRANT_PROPAGATION_TICKS:
                packet["propagated_grant"] = current
                break
        previous = current
    assert set(packet) == {
        "reservation_before",
        "reservation_hold",
        "hold_before",
        "first_hold",
        "grant_before",
        "grant",
        "grant_plus_1",
        "grant_plus_2",
        "propagated_grant",
    }, (loop.tick, packet.keys())
    assert max_active == 3
    assert {"G1", "G2"} <= completed
    assert not [event for event in loop.events if event[1] in FAULTS]
    packet["bound_ticks"] = max_ticks
    return packet


@pytest.mark.skipif(
    os.environ.get("TRACK_OVERFLOW_GREEN_OWNER_DIAGNOSTICS") != "1",
    reason="set TRACK_OVERFLOW_GREEN_OWNER_DIAGNOSTICS=1 for CTC-2 capture",
)
def test_green_first_hold_and_grant_boundary(record_property):
    """Distinguish reservation waiting from the later starter denial."""
    packet = capture_green_owner_diagnostics()
    record_property(
        "green_owner_diagnostics", json.dumps(packet, sort_keys=True)
    )
    reservation = packet["reservation_hold"]
    assert packet["reservation_before"]["tick"] == reservation["tick"] - 1
    assert packet["reservation_before"]["phase"]["G2"] != HELD
    assert not reservation["g2_clear_to_yard"]
    assert "G1" in reservation["zone_owners"]["1"]
    hold = packet["first_hold"]
    assert packet["hold_before"]["tick"] == hold["tick"] - 1
    assert any(
        abs(train["speed_mps"]) >= 0.01
        for train in packet["hold_before"]["trains"].values()
    )
    assert hold["phase"]["G2"] == HELD
    grant = packet["grant"]
    assert hold["tick"] < grant["tick"]
    assert packet["grant_before"]["tick"] == grant["tick"] - 1
    assert not any(
        entry["block_id"] == "65" and entry["authority_blocks"] > 0
        for entry in packet["grant_before"]["ctc_suggestions"]
    )
    # The SW has not yet consumed the fresh CTC grant on its issue tick.
    assert grant["sw_suggestions"]["65"]["authority_blocks"] == 0
    assert packet["grant_plus_1"]["tick"] == grant["tick"] + 1
    assert (
        packet["grant_plus_1"]["sw_suggestions"]["65"]["authority_blocks"] > 0
    )
    settled = packet["propagated_grant"]
    assert settled["g2_clear_to_yard"]
    assert settled["zone_owners"] == {"1": ["G2"], "77": ["G2"]}
    assert settled["sw_suggestions"]["65"]["authority_blocks"] > 0
    assert settled["sw_image"] == {
        "OCC_64": True,
        "OCC_65": True,
        "OCC_66": False,
    }
    assert settled["sw_raw"]["AUTH_65"] is False
    assert settled["sw_raw"]["AUTH_66"] is True
    assert settled["sw_overrides"] == []
    assert settled["sw_circuits"]["65"] == {
        "speed_mps": 0,
        "authority_blocks": 0,
    }
    assert settled["sw_circuits"]["66"] == settled["sw_suggestions"]["66"]
    assert settled["trains"]["G2"]["model_signal"]["authority_blocks"] == 0
    assert settled["trains"]["G2"]["model_signal"]["commanded_speed_mps"] == 0
