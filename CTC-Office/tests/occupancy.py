"""Test helpers: put trains where a test wants them, and report what
the Track Controller reports, which is occupancy only.

``ctc.tracking`` finds a train by its leaving the yard and follows it
from block to block. Most tests just need a train somewhere: ``step_at``
has the module follow each train at its block (``place_train``), then
steps with those blocks, and any others given, reported occupied. An
occupied block no train is in is inferred to have failed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ctc.interface import (
    BlockOccupancy,
    CrossingReport,
    CtcInputs,
    CtcOutputs,
    SwitchReport,
    TrackControllerInputs,
)
from ctc.model import StubCtcOffice

DT_S = 0.1


@dataclass(frozen=True, slots=True)
class At:
    """A train with its head in a block."""

    train_id: str
    line: str
    block_id: str


def at(train_id: str, block_id: str, line: str = "Green") -> At:
    return At(train_id, line, block_id)


def reports(*trains: At, occupied: Iterable[tuple[str, str]] = (),
            switches: Iterable[SwitchReport] = (),
            crossings: Iterable[CrossingReport] = (),
            ready: bool = True) -> CtcInputs:
    """The Track Controller's report with ``trains`` in their blocks and
    ``occupied`` ``(line, block)`` pairs occupied too. Ready unless
    told otherwise: until it is, the CTC sends it nothing."""
    blocks = {(t.line, t.block_id) for t in trains} | set(occupied)
    return CtcInputs(track_controller=TrackControllerInputs(
        occupancy=tuple(BlockOccupancy(line, block_id, True)
                        for line, block_id in sorted(blocks)),
        switches=tuple(switches), crossings=tuple(crossings),
        ready=ready))


def place(ctc: StubCtcOffice, *trains: At) -> None:
    """Have ``ctc`` follow each train at its block, unless it already
    has the train's head there."""
    heads = {t.train_id: (t.line, t.blocks[-1])
             for t in ctc.snapshot().trains}
    for train in trains:
        if heads.get(train.train_id) != (train.line, train.block_id):
            ctc.place_train(train.train_id, train.line, train.block_id)


def step_at(ctc: StubCtcOffice, *trains: At,
            occupied: Iterable[tuple[str, str]] = (),
            switches: Iterable[SwitchReport] = (),
            crossings: Iterable[CrossingReport] = (),
            dt: float = DT_S) -> CtcOutputs:
    """Place ``trains``, then step with their blocks and ``occupied``
    reported occupied."""
    place(ctc, *trains)
    return ctc.step(dt, reports(*trains, occupied=occupied,
                                switches=switches, crossings=crossings))
