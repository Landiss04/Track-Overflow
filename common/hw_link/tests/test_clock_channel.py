"""Real harness-wire clock state classifies loss between train steps."""

from __future__ import annotations

import json
import uuid

import pytest
from PySide6.QtNetwork import QLocalServer

from common.hw_link.relay import HardwareRelay
from common.hw_link.tests.test_transports_recovery import request, until
from common.hw_link.transport import ProcessTransport
from utils.harness_protocol import decode, encode
from utils.module_link import ModuleLink


@pytest.mark.parametrize("paused_before_loss", [False, True])
def test_clock_wire_pause_between_steps_and_late_pause_loss_policy(
    tmp_path, paused_before_loss
):
    server = QLocalServer()
    name = "pi-clock-" + uuid.uuid4().hex
    assert server.listen(name)
    transport = ProcessTransport("train-controller-hw", tmp_path / "pi.jsonl")
    relay = HardwareRelay("train-controller-hw", transport)
    link = ModuleLink(
        "train-controller-hw",
        name,
        lambda *_args: {},
        deferred_handler=relay.submit_step,
    )
    states, replies, events, errors = [], [], [], []
    link.clockStateChanged.connect(states.append)
    link.clockStateChanged.connect(relay.set_clock_state)
    relay.ready.connect(link.announce_ready)
    relay.diagnosticEvent.connect(events.append)
    relay.reply.connect(replies.append)
    relay.reply.connect(
        lambda value: link.reply_outputs(
            value["id"], value["tick"], value["outputs"]
        )
    )
    transport.diagnostic.connect(errors.append)
    link.connect_to_harness()
    relay.start()
    peer = None
    try:
        until(server.hasPendingConnections)
        peer = server.nextPendingConnection()
        until(peer.canReadLine)
        assert decode(bytes(peer.readLine()))["op"] == "READY"

        def clock(paused):
            peer.write(
                encode(
                    {
                        "op": "CLOCK_STATE",
                        "id": 0,
                        "tick": link.tick,
                        "state": {
                            "clock_paused": paused,
                            "clock_speedup": True,
                        },
                    }
                )
            )
            peer.flush()
            count = len(states)
            until(lambda: len(states) > count)
            assert relay._clock_running is not paused

        # The initial paused status reaches the real host channel before
        # any STEP; a later transition also requires no tick to deliver it.
        clock(True)
        assert link.tick == 0
        clock(False)
        peer.write(encode(request(1)))
        peer.flush()
        until(lambda: len(replies) == 1)
        until(peer.canReadLine)
        assert decode(bytes(peer.readLine()))["op"] == "OUTPUTS"
        for field, value in (("kp", 120000), ("ki", 8000)):
            relay.call_action(
                "set_state",
                {
                    "train_id": "R1",
                    "field": field,
                    "value": value,
                },
            )
        relay.call_action(
            "set_core",
            {
                "train_id": "R1",
                "field": "armed",
                "value": True,
            },
        )
        if paused_before_loss:
            clock(True)  # User pause between steps, with no extra STEP.
            assert link.tick == 1
        transport.process.kill()
        until(lambda: any("PI_LOST" in item for item in events))
        if not paused_before_loss:
            # The harness's timeout pause arrives after the actual loss.
            # It must not reclassify that loss as a paused loss.
            clock(True)
        until(lambda: any("PI_RECOVERED" in item for item in events))
        relay.call_action(
            "set_state",
            {
                "train_id": "R1",
                "field": "target_temp_c",
                "value": 22,
            },
        )
        armed = relay._last_view["trains"]["R1"]["core"]["armed"]
        assert armed is not paused_before_loss
        expected = (
            "GAINS_WAIT_ENGINEER" if paused_before_loss else "GAINS_RESENT"
        )
        assert any(expected in item for item in events)
        entries = [
            json.loads(line)
            for line in (tmp_path / "pi.jsonl").read_text().splitlines()[1:]
        ]
        policies = [
            entry["request"]
            for entry in entries
            if entry["request"].get("action") == "recovery_gains"
        ]
        assert len(policies) == 1
        assert bool(policies[0]["args"]["trains"]) is not paused_before_loss
        assert link.tick == 1 and not errors
        if paused_before_loss:
            # No engineer has recommissioned after the paused reboot. A
            # subsequent running loss must not resurrect that old cache.
            clock(False)
            previous = sum("PI_RECOVERED" in item for item in events)
            transport.process.kill()
            until(
                lambda: sum("PI_RECOVERED" in item for item in events)
                > previous
            )
            relay.call_action(
                "set_state",
                {
                    "train_id": "R1",
                    "field": "target_temp_c",
                    "value": 23,
                },
            )
            assert not relay._last_view["trains"]["R1"]["core"]["armed"]
            assert relay._gains == {}
    finally:
        link.close()
        relay.close()
        if peer is not None:
            peer.abort()
        server.close()
