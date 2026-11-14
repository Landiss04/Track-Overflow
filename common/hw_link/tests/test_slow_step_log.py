"""A reply or VIEW slower than SLOW_STEP_S is logged with where its time went."""

import threading
import time

import common.hw_link.agent as agent
from common.hw_link import protocol as p
from common.hw_link.agent import PiLinkServer
from common.hw_link.tests.test_protocol_agent import hello, step
from common.hw_link.tests.test_step_reply_order import (  # noqa: F401
    FakeCore,
    rig,
    wire,
)


def run_logged(rig, *chunks):
    log = rig.journal.parent / "agent.log"
    rig.run(*chunks, extra=("--log", str(log)))
    return log.read_text().splitlines() if log.exists() else []


def test_a_slow_step_is_logged_with_its_core_time(rig):
    # The fake core takes 125 ms a step, over the 10 ms limit.
    logged = run_logged(rig, wire(hello()) + wire(step(1)))
    assert len(logged) == 1
    assert logged[0].startswith("SLOW_STEP tick=1 total_ms=125.0 core_ms=")
    assert "disk_wait_ms=0.0" in logged[0]
    assert "ckpt_pickle_ms=0.0" in logged[0]


def test_steps_under_the_limit_log_nothing(rig, monkeypatch):
    monkeypatch.setattr(agent, "SLOW_STEP_S", 1.0)
    assert run_logged(rig, wire(hello()) + wire(step(1)) + wire(step(2))) == []


def test_a_slow_view_is_logged_apart_from_its_step(rig, monkeypatch):
    view = FakeCore.view

    def slow_view(self):
        result = view(self)
        self.clock[0] += 0.05
        return result

    monkeypatch.setattr(FakeCore, "view", slow_view)
    monkeypatch.setattr(agent, "SLOW_STEP_S", 0.04)
    logged = run_logged(rig, wire(hello()) + wire(step(1)))
    # The 125 ms step, then the 50 ms VIEW built after it.
    assert [line.split()[0] for line in logged] == ["SLOW_STEP", "SLOW_VIEW"]
    assert "total_ms=50.0" in logged[1]


def test_a_reply_held_for_the_disk_reports_the_wait(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "MAX_UNSYNCED", 1)
    shut, real = threading.Event(), agent.os.fsync
    monkeypatch.setattr(
        agent.os,
        "fsync",
        lambda fd: shut.wait(5) and real(fd),
    )
    server = PiLinkServer("train-controller-hw", tmp_path / "j")
    shut.set()
    server.handle(hello())
    shut.clear()
    thread = threading.Thread(
        target=lambda: [server.handle(step(t)) for t in (1, 2, 3)]
    )
    thread.start()
    time.sleep(0.3)
    shut.set()
    thread.join(5)
    server.close()
    assert not thread.is_alive()
    assert server.disk_wait_s >= 0.25


def test_the_checkpoint_pickle_time_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "CHECKPOINT_TICKS", 3)
    server = PiLinkServer("train-controller-hw", tmp_path / "j", durable=False)
    server.handle(hello())
    for tick in (1, 2):
        server.handle(step(tick))
    assert server.checkpoint_s == 0.0
    server.handle(step(3))
    server.settle()
    server.close()
    assert server.checkpoint_s > 0.0
