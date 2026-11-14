"""A checkpoint's fsyncs and journal swap run beside the steps, not before a reply."""

import json
import threading

import pytest
from common.hw_link import agent, protocol as p
from common.hw_link.agent import PiLinkServer
from common.hw_link.tests.test_journal_handle import hello, step

MODULE = "train-controller-hw"


@pytest.fixture
def disk_stall(monkeypatch):
    """Once armed, block every fsync but the journal thread's, until released."""
    release = threading.Event()
    release.armed = threading.Event()
    real = agent.os.fsync

    def fsync(fd):
        if (
            release.armed.is_set()
            and threading.current_thread().name != "journal"
        ):
            assert release.wait(10), "stall never released"
        real(fd)

    monkeypatch.setattr(agent.os, "fsync", fsync)
    yield release
    release.set()


def run(server, ticks, done):
    for tick in ticks:
        server.handle(step(tick))
    done.set()


def test_steps_do_not_wait_for_the_checkpoint_disk(
    tmp_path, monkeypatch, disk_stall
):
    monkeypatch.setattr(agent, "CHECKPOINT_TICKS", 5)
    journal = tmp_path / "j.jsonl"
    server = PiLinkServer(MODULE, journal)
    server.handle(hello())
    disk_stall.armed.set()
    finished = threading.Event()
    # The 5th step starts a checkpoint; its fsyncs are stalled, and the
    # replies for the steps around it must still come back.
    threading.Thread(
        target=run, args=(server, range(1, 9), finished), daemon=True
    ).start()
    assert finished.wait(5), "a step waited for the checkpoint's disk"
    disk_stall.set()
    server.settle()
    server.close()

    # Steps 6-8 were written while the checkpoint was in flight; the new
    # journal starts from the snapshot and must hold them, in order.
    lines = journal.read_bytes().splitlines()
    assert json.loads(lines[0])["checkpoint"] == 1
    assert [json.loads(l)["request"]["tick"] for l in lines[1:]] == [6, 7, 8]
    restored = PiLinkServer(MODULE, journal)
    assert restored._applied == ["STEP", 18, 8]
    assert restored.core.fleet.time_s == server.core.fleet.time_s
    restored.close()


def test_durable_claim_never_runs_ahead_of_the_swapped_journal(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(agent, "CHECKPOINT_TICKS", 3)
    journal = tmp_path / "j.jsonl"
    server = PiLinkServer(MODULE, journal)
    server.handle(hello())
    for tick in range(1, 40):
        reply = server.handle(step(tick))[0]
        server.settle() if tick % 7 == 0 else None
        claimed = reply["durable"]
        # What the host is told is on disk is in the checkpoint (three
        # steps each) or in the journal file as it stands.
        if claimed:
            lines = journal.read_bytes().splitlines()
            covered = 3 * json.loads(lines[0])["checkpoint"] if json.loads(
                lines[0]
            )["checkpoint"] else 0
            ticks = [json.loads(l)["request"]["tick"] for l in lines[1:]]
            assert claimed[2] <= max([covered, *ticks]), (tick, claimed)
    server.wait_durable()
    server.settle()
    server.wait_durable()
    assert server._durable_key == ["STEP", 49, 39]
    server.close()
