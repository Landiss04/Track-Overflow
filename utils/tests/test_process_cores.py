"""The Pi link processes get cores of their own; everything else shares the rest."""

import os
import subprocess
import sys

import pytest
from utils import process_cores


@pytest.mark.parametrize(
    "count, system, links",
    [
        (1, (0,), ()),
        (2, (0, 1), ()),
        (3, (0, 1, 2), ()),
        (4, (0, 1, 2), (3,)),
        (6, (0, 1, 2, 3), (4, 5)),
        (8, (0, 1, 2, 3, 4, 5), (6, 7)),
    ],
)
def test_split(count, system, links):
    assert process_cores.split(count) == (system, links)


class FakeKernel32:
    def __init__(self):
        self.masks = []

    def GetCurrentProcess(self):
        return -1

    def SetProcessAffinityMask(self, handle, mask):
        self.masks.append((handle, mask))
        return 1


def test_windows_mask_has_one_bit_per_core():
    kernel = FakeKernel32()
    assert process_cores._pin_windows((4, 5), kernel)
    assert kernel.masks == [(-1, 0b110000)]


@pytest.mark.skipif(
    not hasattr(os, "sched_setaffinity") or (os.cpu_count() or 1) < 4,
    reason="needs Linux affinity and four cores",
)
def test_pinning_a_process_and_its_children(tmp_path):
    code = (
        "import os, subprocess, sys\n"
        "from utils import process_cores as c\n"
        "assert c.pin_system()\n"
        "mine = sorted(os.sched_getaffinity(0))\n"
        "child = subprocess.run([sys.executable, '-c',"
        " 'import os; print(sorted(os.sched_getaffinity(0)))'],"
        " capture_output=True, text=True).stdout\n"
        "assert c.pin_links()\n"
        "print(mine, child.strip(), sorted(os.sched_getaffinity(0)))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()
    system, links = process_cores.split(os.cpu_count())
    assert out == f"{list(system)} {list(system)} {list(links)}"


def test_no_pin_switch(monkeypatch):
    monkeypatch.setenv(process_cores.NO_PIN_ENV, "1")
    assert not process_cores.pin_links()
    assert not process_cores.pin_system()
