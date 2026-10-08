"""Shared fixtures: the sample waysides and a way to build inputs."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from track_ctrl_hw.controller import HwTrackController
from track_ctrl_hw.interface import (
    BlockKey,
    CtcInputs,
    Suggestion,
    Territory,
    TrackControllerInputs,
    TrackModelInputs,
)
from track_ctrl_hw.territory import load_territory_file

DATA = Path(__file__).resolve().parents[1] / "data"


def territory(number: int) -> Territory:
    """One of the sample Green line waysides."""
    return load_territory_file(
        DATA / "waysides" / f"green_wayside_{number}.json"
    )


def program_source(number: int) -> str:
    """The sample PLC program written for that wayside."""
    path = DATA / "plc" / f"green_wayside_{number}.plc"
    return path.read_text(encoding="utf-8")


def loaded(*numbers: int, programs: bool = True) -> HwTrackController:
    """A controller with sample waysides and, optionally, programs."""
    controller = HwTrackController()
    for number in numbers:
        controller.load_territory(territory(number))
        if programs:
            controller.load_program(
                str(number), program_source(number),
                f"green_wayside_{number}.plc",
            )
    return controller


def keys(controller: HwTrackController) -> dict[str, BlockKey]:
    """Every loaded block, by number."""
    return {
        key.block_id: key
        for wayside in controller.snapshot().waysides
        for key in wayside.territory.keys
    }


def inputs(
    controller: HwTrackController,
    *,
    time_s: float = 18000.0,
    occupied: Iterable[str] = (),
    closed: Iterable[str] = (),
    failures: dict[str, str] | None = None,
    suggestions: dict[str, tuple[int, int]] | None = None,
    maintenance: bool = False,
    switch_commands: dict[str, str] | None = None,
    reported: dict[str, str] | None = None,
    lit: dict[str, str] | None = None,
) -> TrackControllerInputs:
    """Inputs by block number. Every switch reports its commanded
    position unless ``reported`` says otherwise; ``lit`` gives the
    aspects the Track Model reports."""
    by_number = keys(controller)
    snapshot = controller.snapshot()
    commanded = {
        state.switch.key: state.commanded
        for wayside in snapshot.waysides
        for state in wayside.switches
    }
    positions = dict(commanded)
    for number, position in (reported or {}).items():
        positions[by_number[number]] = position  # type: ignore[assignment]
    return TrackControllerInputs(
        time_s=time_s,
        ctc=CtcInputs(
            maintenance_mode=maintenance,
            closed_blocks=frozenset(by_number[n] for n in closed),
            switch_commands={
                by_number[n]: p  # type: ignore[misc]
                for n, p in (switch_commands or {}).items()
            },
            suggestions={
                by_number[n]: Suggestion(*value)
                for n, value in (suggestions or {}).items()
            },
        ),
        track_model=TrackModelInputs(
            occupied_blocks=frozenset(by_number[n] for n in occupied),
            failures={
                by_number[n]: kind  # type: ignore[misc]
                for n, kind in (failures or {}).items()
            },
            switch_positions=positions,
            signal_aspects={
                by_number[n]: aspect  # type: ignore[misc]
                for n, aspect in (lit or {}).items()
            },
        ),
    )
