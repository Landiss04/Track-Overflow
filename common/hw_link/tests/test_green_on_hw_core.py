"""The Train HW core is not tied to the Red line: Green trains run the same."""

import json

from common.harness.tests.test_harness_train_loop import KI, KP, _Loop
from common.hw_link.cores import TrainCore
from common.hw_link.tests.test_train_step_rollback import good, request

GREEN_TICKS = 1500


def test_a_real_green_train_gets_the_same_commands_as_the_sw_controller():
    loop = _Loop()
    recorded = []
    sw_step = loop.controller.step

    def tap(tick, dt, now, inputs):
        outputs = sw_step(tick, dt, now, inputs)
        recorded.append(json.loads(json.dumps([tick, dt, now, inputs, outputs])))
        return outputs

    loop.controller.step = tap
    for _ in range(GREEN_TICKS):
        loop.step()
    assert any(r[3].get("trains") for r in recorded), "no Green train ran"
    assert {
        entry["line"]
        for r in recorded
        for entry in r[3].get("trains", {}).values()
    } == {"Green"}

    core = TrainCore()
    core.action("test_engineer_gains", {"kp": KP, "ki": KI})
    for tick, dt, now, inputs, outputs in recorded:
        reply = core.step(
            {"dt": dt, "tick": tick, "sim_time_s": now, "inputs": inputs}
        )
        assert json.loads(json.dumps(reply)) == outputs, tick


def send(core, trains, tick):
    """One STEP of ``{train: (line, speed)}`` to ``core``; its commands."""
    body = request({}, tick, time_s=18000.0 + tick / 10)
    body["inputs"] = {
        "trains": {
            key: {"line": line, "inputs": good(speed)}
            for key, (line, speed) in trains.items()
        }
    }
    return core.step(body)["trains"]


def test_green_and_red_trains_on_one_core_stay_independent():
    # G1 is there throughout, R1 joins at tick 3 and leaves at tick 7.
    plan = {
        tick: {
            "G1": ("Green", 1.0 + tick / 10),
            **({"R1": ("Red", 2.0 + tick / 10)} if 3 <= tick < 7 else {}),
        }
        for tick in range(1, 11)
    }
    mixed, red_only, green_only = TrainCore(), TrainCore(), TrainCore()
    for core in (mixed, red_only, green_only):
        core.action("test_engineer_gains", {"kp": KP, "ki": KI})
    for tick, trains in plan.items():
        both = send(mixed, trains, tick)
        green = send(green_only, {"G1": trains["G1"]}, tick)
        red = send(red_only, {k: v for k, v in trains.items() if k == "R1"}, tick)
        assert set(both) == set(trains)
        assert both["G1"] == green["G1"], tick
        if "R1" in trains:
            assert both["R1"] == red["R1"], tick
