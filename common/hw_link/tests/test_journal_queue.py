"""A reply never waits on the journal file: records are queued and written beside it."""

import json
import threading
from pathlib import Path

import pytest
from common.hw_link import agent
from common.hw_link.agent import PiLinkServer
from common.hw_link.tests.test_background_journal import hello, request

MODULE = "train-controller-hw"


@pytest.fixture
def shut_file(monkeypatch):
    """Appends to any journal block in write() until released."""
    release = threading.Event()
    real = Path.open

    class Slow:
        def __init__(self, stream):
            self.stream = stream

        def write(self, data):
            assert release.wait(10), "file stall never released"
            return self.stream.write(data)

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.stream.close()

    def opening(self, mode="r", *args, **kwargs):
        stream = real(self, mode, *args, **kwargs)
        return Slow(stream) if mode == "ab" else stream

    monkeypatch.setattr(Path, "open", opening)
    yield release
    release.set()


def run(server, ticks, replies, done):
    for tick in ticks:
        replies.append(server.handle(request(tick))[0])
    done.set()


def ticks_in(journal):
    return [
        json.loads(line)["request"]["tick"]
        for line in journal.read_bytes().splitlines()[1:]
    ]


def test_replies_do_not_wait_for_the_file(tmp_path, shut_file):
    journal = tmp_path / "j"
    server = PiLinkServer(MODULE, journal)
    server.handle(hello())
    replies, done = [], threading.Event()
    threading.Thread(
        target=run, args=(server, range(1, 6), replies, done), daemon=True
    ).start()
    assert done.wait(5), "a reply waited for the journal file"
    # Nothing is on disk, and no reply claims it is.
    assert ticks_in(journal) == []
    assert [reply["durable"] for reply in replies] == [None] * 5
    shut_file.set()
    server.wait_durable()
    assert ticks_in(journal) == [1, 2, 3, 4, 5]
    server.close()


def test_a_checkpoint_swap_neither_drops_nor_repeats_queued_records(
    tmp_path, shut_file, monkeypatch
):
    monkeypatch.setattr(agent, "CHECKPOINT_TICKS", 3)
    journal = tmp_path / "j"
    server = PiLinkServer(MODULE, journal)
    server.handle(hello())
    # Steps 1-7 are queued with the file shut; checkpoints are taken at 3
    # and 6 while records are still waiting to be written.
    replies, done = [], threading.Event()
    threading.Thread(
        target=run, args=(server, range(1, 8), replies, done), daemon=True
    ).start()
    assert done.wait(5)
    shut_file.set()
    server.settle()
    server.wait_durable()
    server.settle()
    server.wait_durable()
    server.close()
    restored = PiLinkServer(MODULE, journal)
    # Whatever is in the checkpoint plus the journal restores step 7 once.
    assert restored._applied == ["STEP", 17, 7]
    ticks = ticks_in(journal)
    assert ticks == sorted(set(ticks))
    assert restored._checkpoint_seq * 3 + len(ticks) == 7
    restored.close()
