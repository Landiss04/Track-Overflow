"""A stable gadget pathname survives a real raw-tty disconnect/reopen."""

import os
import select
import subprocess
import sys
import time

import pytest
from common.hw_link import protocol as p
from common.hw_link.tests.test_protocol_agent import hello, step
from utils.harness_protocol import LineBuffer


@pytest.mark.skipif(sys.platform != "linux", reason="Linux raw tty")
def test_raw_device_reopens_same_session_without_traceback(tmp_path):
    import pty
    import tty

    master, slave = pty.openpty()
    tty.setraw(slave)
    gadget = tmp_path / "ttyGS0"
    gadget.symlink_to(os.ttyname(slave))
    child = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "common.hw_link.agent",
            "--module",
            "train-controller-hw",
            "--device",
            str(gadget),
            "--journal",
            str(tmp_path / "journal"),
            "--log",
            str(tmp_path / "agent.log"),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    def exchange(fd, frame):
        os.write(fd, p.encode(frame))
        buffer = LineBuffer()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            readable, _, _ = select.select([fd], [], [], 0.1)
            if readable:
                for line in buffer.feed(os.read(fd, 65536)):
                    value = p.decode(line)
                    if value["id"] == frame["id"]:
                        return value
        raise AssertionError("raw tty did not reply")

    try:
        first_hello = exchange(master, hello())
        first_reply = exchange(master, step())
        os.write(master, b'{"unfinished":')
        os.close(master)
        os.close(slave)
        master = slave = None
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            log_file = tmp_path / "agent.log"
            if (
                log_file.exists()
                and "DEVICE_RECONNECT_WAIT" in log_file.read_text()
            ):
                break
            time.sleep(0.02)
        master, slave = pty.openpty()
        tty.setraw(slave)
        replacement = tmp_path / "new-device"
        replacement.symlink_to(os.ttyname(slave))
        os.replace(replacement, gadget)
        second_hello = exchange(master, hello())
        assert second_hello["boot"] == first_hello["boot"]
        assert second_hello["resumed"]
        assert exchange(master, step()) == first_reply
    finally:
        child.terminate()
        _, stderr = child.communicate(timeout=3)
        for fd in (master, slave):
            if fd is not None:
                os.close(fd)
    assert stderr == b""
