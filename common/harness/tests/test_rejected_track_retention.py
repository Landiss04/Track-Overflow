"""Bounded INPUT-1 fault probes using the existing local-socket runner.

Track occupancy comes from fake producer replies; routing and the barrier
are real. Closures belong to the CTC producer, independently of occupancy.
These checks establish retention and holds, not physical freshness.
"""

from PySide6.QtCore import QTimer

from common.harness.edges import SystemEdges
from common.harness.modules import (
    CTC_OFFICE,
    TRACK_CONTROLLER_SW,
    TRACK_MODEL,
    TRAIN_MODEL,
)
from common.harness.tests.test_harness_faults import (
    FAULT_TICK,
    _Run,
    outputs_line,
    wait_until,
)
from utils.harness_protocol import encode, rejected_message


def track_output(occupied=True):
    """Return a small valid Track Model controller readback."""
    return {
        "controller": {
            "block_occupancy": {"GREEN D-28": occupied},
            "switch_states": {},
            "crossing_states": {},
            "signal_states": {},
        },
        "train_feeds": {},
    }


class _ConsumerAdapter(SystemEdges):
    """Observe real SW inputs on the existing runner's Train Model socket.

    The runner has three fixed fake identities. Only this test socket's
    input consumer identity changes; output producers keep their names.
    """

    def __init__(self):
        super().__init__(wired=(CTC_OFFICE, TRACK_MODEL, TRACK_CONTROLLER_SW))

    def inputs_for(self, consumer, tick, sim_time_s, outputs):
        if consumer == TRAIN_MODEL:
            consumer = TRACK_CONTROLLER_SW
        return super().inputs_for(consumer, tick, sim_time_s, outputs)


def configured_run():
    """Reuse the fault runner with stable closures and occupied readback."""
    run = _Run(_ConsumerAdapter())
    for tick in range(1, FAULT_TICK + 2):
        run.fakes[TRACK_MODEL].scripts[tick] = lambda step: outputs_line(
            step, **track_output()
        )
        run.fakes[CTC_OFFICE].scripts[tick] = lambda step: outputs_line(
            step,
            clock_paused=step["tick"] >= FAULT_TICK + 1,
            track_controller={
                "suggestions": [],
                "switch_commands": [],
                "closed_blocks": [{"line": "Green", "block_id": "28"}],
            },
        )
    return run


def assert_membership(step):
    """Check occupancy and independently sourced CTC closure routing."""
    key = {"line": "Green", "block_id": "28"}
    assert step["inputs"]["track_model"]["occupied_blocks"] == [key]
    assert step["inputs"]["ctc"]["closed_blocks"] == [key]


def test_rejected_track_tick_retains_output_and_waits_for_other_replies():
    run = configured_run()
    try:
        track = run.fakes[TRACK_MODEL]
        track.scripts[FAULT_TICK] = lambda step: encode(
            rejected_message(
                step["id"], step["tick"], "injected track rejection"
            )
        )
        track.scripts[FAULT_TICK + 1] = lambda step: outputs_line(
            step, **track_output(False)
        )
        consumer = run.fakes[TRAIN_MODEL]
        # Hold a different module's reply after TRACK_MODEL rejects.
        consumer.delay_ms[FAULT_TICK] = 5000
        run.run()
        assert wait_until(
            lambda: bool(run.find("TICK_REJECTED"))
            and any(step["tick"] == FAULT_TICK for step in consumer.steps)
        ), run.events
        rejected = run.find("TICK_REJECTED")
        assert [(event[0], event[1], event[3]) for event in rejected] == [
            (FAULT_TICK, TRACK_MODEL, "injected track rejection")
        ]
        assert run.harness.outputs[TRACK_MODEL] == track_output()
        assert FAULT_TICK not in run.completed
        assert run.harness.clock.tick_count == FAULT_TICK
        assert TRAIN_MODEL in run.harness._pending
        assert TRACK_MODEL not in run.harness._pending
        assert all(step["tick"] <= FAULT_TICK for step in consumer.steps)
        owed = next(
            step for step in consumer.steps if step["tick"] == FAULT_TICK
        )
        consumer.send(outputs_line(owed))
        assert wait_until(lambda: FAULT_TICK + 1 in run.completed), run.events
        following = next(
            step for step in consumer.steps if step["tick"] == FAULT_TICK + 1
        )
        assert_membership(following)
        # A newly accepted clear output is committed only at tick 4 end.
        assert run.harness.outputs[TRACK_MODEL] == track_output(False)
        assert run.completed == [1, 2, 3, 4]
        assert run.find("REPLY_LATE") == []
        assert run.find("MODULE_DISCONNECTED") == []
        assert run.find("INPUTS_FAILED") == []
    finally:
        run.clean_up()


def test_late_track_reply_retains_output_but_holds_clock():
    run = configured_run()
    try:
        run.fakes[TRACK_MODEL].scripts[FAULT_TICK] = lambda step: b""
        run.run()
        assert wait_until(lambda: bool(run.find("REPLY_LATE"))), run.events
        assert [event[1] for event in run.find("REPLY_LATE")] == [TRACK_MODEL]
        assert run.harness.outputs[TRACK_MODEL] == track_output()
        assert run.harness.clock.is_paused
        assert run.harness.clock.tick_count == FAULT_TICK
        assert run.completed == [1, 2]
        assert TRACK_MODEL in run.harness.late_modules
        assert TRACK_MODEL in run.harness.hold_reason
        assert run.find("TICK_REJECTED") == []
        assert run.find("MODULE_DISCONNECTED") == []
        assert [step["tick"] for step in run.fakes[TRAIN_MODEL].steps] == [
            1,
            2,
            3,
        ]
        assert_membership(run.fakes[TRAIN_MODEL].steps[-1])
    finally:
        run.clean_up()


def test_disconnected_track_retains_output_but_holds_clock():
    run = configured_run()
    try:
        track = run.fakes[TRACK_MODEL]

        def disconnect(step):
            """Drop the link instead of replying to this tick."""
            QTimer.singleShot(0, track._socket.abort)
            return b""

        track.scripts[FAULT_TICK] = disconnect
        run.run()
        assert wait_until(
            lambda: bool(run.find("MODULE_DISCONNECTED"))
            and FAULT_TICK in run.completed
        ), run.events
        assert run.harness.outputs[TRACK_MODEL] == track_output()
        assert run.harness.clock.is_paused
        assert run.harness.clock.tick_count == FAULT_TICK
        # Unlike a late reply, disconnection completes this tick without
        # the lost module. The down-module hold prevents another tick.
        assert run.completed == [1, 2, 3]
        assert TRACK_MODEL in run.harness.down_modules
        assert TRACK_MODEL in run.harness.hold_reason
        assert run.find("TICK_REJECTED") == []
        assert run.find("REPLY_LATE") == []
        assert wait_until(
            lambda: len(run.fakes[TRAIN_MODEL].steps) == FAULT_TICK
        ), run.events
        assert all(
            step["tick"] <= FAULT_TICK
            for fake in run.fakes.values()
            for step in fake.steps
        )
        assert_membership(run.fakes[TRAIN_MODEL].steps[-1])
    finally:
        run.clean_up()
