"""The Pi replies before its journal fsync; the host keeps what is not yet durable."""

from __future__ import annotations

import json
import os
import threading
import time

import pytest
import common.hw_link.agent as agent
from common.hw_link import protocol as p
from common.hw_link.agent import PiLinkServer
from common.hw_link.relay import HardwareRelay
from common.hw_link.tests.test_protocol_agent import hello
from common.hw_link.tests.test_transports_recovery import request
from common.hw_link.transport import ByteTransport

MODULE = "train-controller-hw"


class Gate:
    """os.fsync stand-in that can be held shut, as a slow SD card is."""

    def __init__(self) -> None:
        self.open = threading.Event()
        self.open.set()
        self.threads: list[int] = []

    def __call__(self, fd: int) -> None:
        self.threads.append(threading.get_ident())
        assert self.open.wait(5), "fsync gate never opened"


@pytest.fixture
def gate(monkeypatch):
    value = Gate()
    monkeypatch.setattr(agent.os, "fsync", value)
    yield value
    value.open.set()


@pytest.fixture
def servers():
    made: list[PiLinkServer] = []
    yield made
    for server in made:
        server.close()


def make(servers, journal, **options) -> PiLinkServer:
    server = PiLinkServer(MODULE, journal, **options)
    servers.append(server)
    return server


def key(frame):
    return [frame["op"], frame["id"], frame["tick"]]


def test_step_reply_does_not_wait_for_fsync(tmp_path, gate, servers):
    journal = tmp_path / "journal"
    server = make(servers, journal)
    server.handle(hello())
    gate.open.clear()
    started = time.perf_counter()
    assert server.handle(request(1))[0]["op"] == "OUTPUTS"
    assert time.perf_counter() - started < 2
    # Already written: an agent crash, unlike a power cut, keeps it.
    assert len(journal.read_bytes().splitlines()) == 2
    gate.open.set()
    server.wait_durable()
    assert gate.threads[-1] != threading.get_ident()


def test_replies_report_what_is_durable(tmp_path, gate, servers):
    server = make(servers, tmp_path / "journal")
    server.handle(hello())
    gate.open.clear()
    server.handle(request(1))
    assert server.handle(request(2))[0]["durable"] is None
    gate.open.set()
    server.wait_durable()
    assert server.handle(request(3))[0]["durable"] == key(request(2))


def test_unsynced_backlog_is_bounded(tmp_path, gate, servers, monkeypatch):
    monkeypatch.setattr(agent, "MAX_UNSYNCED", 2)
    server = make(servers, tmp_path / "journal")
    server.handle(hello())
    gate.open.clear()
    done = []
    worker = threading.Thread(
        target=lambda: done.extend(
            server.handle(request(tick))[0] for tick in range(1, 6)
        )
    )
    worker.start()
    worker.join(0.3)
    assert worker.is_alive()
    gate.open.set()
    worker.join(5)
    assert [reply["tick"] for reply in done] == [1, 2, 3, 4, 5]


def test_hello_reports_last_applied_request(tmp_path, servers):
    journal = tmp_path / "journal"
    server = make(servers, journal)
    assert server.handle(hello())[0]["applied"] is None
    server.handle(request(1))
    server.handle(request(2))
    assert server.handle(hello())[0]["applied"] == key(request(2))
    server.wait_durable()
    rebooted = make(servers, journal)
    assert rebooted.handle(hello())[0]["applied"] == key(request(2))


def test_host_agent_never_fsyncs_and_reports_durable_at_once(
    tmp_path, gate, servers
):
    server = make(servers, tmp_path / "journal", durable=False)
    server.handle(hello())
    gate.threads.clear()
    server.handle(request(1))
    assert server.handle(request(2))[0]["durable"] == key(request(1))
    assert not gate.threads


@pytest.mark.parametrize(
    "tail",
    [b"", b'{"request":', b"\x00" * 300 + b"\n", b'{"request": 1}\n'],
)
def test_power_cut_restores_the_synced_prefix(tmp_path, gate, servers, tail):
    journal = tmp_path / "journal"
    server = make(servers, journal)
    server.handle(hello())
    for tick in range(1, 4):
        server.handle(request(tick))
    server.wait_durable()
    synced = journal.read_bytes()
    gate.open.clear()
    for tick in range(4, 6):
        server.handle(request(tick))
    # Power cut: what was synced survives, plus whatever was half-written.
    journal.write_bytes(synced + tail)
    gate.open.set()
    rebooted = make(servers, journal)
    assert rebooted.handle(hello())[0]["applied"] == key(request(3))
    assert journal.read_bytes() == synced


class Ready:
    """A relay past its first HELLO, writing to a recording transport."""

    def __init__(self) -> None:
        sent = self.sent = []

        class Recording(ByteTransport):
            def start(self):
                pass

            def write(self, data):
                sent.append(p.decode(p.unframe(data.rstrip(b"\n"))))

            def close(self):
                pass

        self.relay = HardwareRelay("track-controller-hw", Recording())
        self.relay._ever_ready = self.relay._online = True
        self.relay._ready = True
        self.relay._boot = "boot-1"

    def answer(self, durable=None, op="OUTPUTS"):
        current = self.relay._inflight
        fields = {"outputs": {}} if op == "OUTPUTS" else {"reason": "no"}
        self.relay._handle(
            p.message(
                op, current["id"], current["tick"], durable=durable, **fields
            )
        )

    def hello(self, applied, resumed=True):
        self.relay._handle(
            p.message(
                p.HELLO,
                1,
                protocol=p.VERSION,
                module=self.relay.module,
                session=self.relay.session,
                agent_version="1",
                agent_hash=self.relay.expected_agent_hash,
                boot="boot-2",
                resumed=resumed,
                applied=applied,
            )
        )


def ran_four_with_one_pending() -> Ready:
    ready = Ready()
    for tick in range(1, 5):
        ready.relay.submit_step(request(tick))
        ready.answer(durable=key(request(1)) if tick == 3 else None)
    ready.relay.submit_step(request(5))
    ready.relay._disconnected()
    ready.sent.clear()
    return ready


@pytest.mark.parametrize(
    "applied, replayed",
    [
        # The Pi kept step 3: only step 4 was lost with the power.
        (key(request(3)), [4]),
        # Steps the host already trimmed as durable are not resent.
        (key(request(1)), [2, 3, 4]),
        # It even ran the pending step: nothing to resend before it.
        (key(request(5)), []),
        # It kept every step the host saw answered.
        (key(request(4)), []),
    ],
)
def test_resumed_pi_is_resent_only_what_it_lost(applied, replayed):
    ready = ran_four_with_one_pending()
    ready.hello(applied)
    for _ in replayed:
        ready.answer()
    assert [frame["tick"] for frame in ready.sent] == [*replayed, 5]
    assert not ready.relay._recovering


def test_replaced_pi_gets_configuration_not_lost_steps():
    ready = ran_four_with_one_pending()
    ready.hello(None, resumed=False)
    assert [frame["tick"] for frame in ready.sent] == [5]
    assert not ready.relay._unsaved


def test_rejected_request_replays_as_rejected_without_holding_clock():
    ready = Ready()
    ready.relay.submit_step(request(1))
    ready.answer(op="REJECTED")
    ready.relay.submit_step(request(2))
    ready.answer()
    ready.relay._disconnected()
    ready.sent.clear()
    ready.hello(None)
    ready.answer(op="REJECTED")
    ready.answer()
    assert [frame["tick"] for frame in ready.sent] == [1, 2]
    assert not ready.relay._recovering


def test_power_cut_loses_no_step_the_host_saw_answered(
    tmp_path, gate, servers
):
    journal = tmp_path / "pi.jsonl"

    class Pi(ByteTransport):
        def __init__(self):
            super().__init__()
            self.server = make(servers, journal)

        def start(self):
            self.connected.emit()

        def write(self, data):
            for reply in self.server.feed(data):
                self.received.emit(reply)

        def close(self):
            pass

    transport = Pi()
    relay = HardwareRelay(MODULE, transport)
    replies, events = [], []
    relay.reply.connect(replies.append)
    relay.diagnosticEvent.connect(events.append)
    relay.set_clock_state({"clock_paused": False})
    relay.start()
    try:
        for tick in range(1, 4):
            relay.submit_step(request(tick))
        transport.server.wait_durable()
        synced = journal.read_bytes()
        gate.open.clear()
        for tick in range(4, 7):
            relay.submit_step(request(tick))
        transport.disconnected.emit()
        journal.write_bytes(synced)
        gate.open.set()
        transport.server = make(servers, journal)
        transport.start()
        assert any("PI_RECOVERED" in event for event in events), events
        relay.submit_step(request(7))
        assert [reply["tick"] for reply in replies] == list(range(1, 8))
        steps = [
            entry["request"]["tick"]
            for entry in map(json.loads, journal.read_text().splitlines()[1:])
            if entry["request"]["op"] == "STEP"
        ]
        assert steps == list(range(1, 8))
    finally:
        relay.close()
