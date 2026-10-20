"""Edges between the Track Model and the trains (D005).

Pure functions on each module's JSON form, as in ``train_edges``. The
Track Model names a block its own way, ``"GREEN K-63"``: the line in
capitals, then the section and the number. Every other module names a
block by its line and number, ``("Green", "63")``
(``conventions/identifiers``), and the harness maps the Track Model's
``GREEN`` (R50). ``BlockNames`` translates between the two, learning
the Track Model's names from the blocks its outputs list, so nothing
here repeats the layout files.

Train Model -> Track Model, ``train_model_to_track_model``, one
train's report::

    track.block_id             -> block_id, in the Track Model's name
    track.offset_m             -> offset_m
    track.actual_speed_mps     -> actual_speed_mps
    track.block_changed        -> block_changed
    track.passenger_capacity   -> passenger_capacity
    controller.door_left_open,
    controller.door_right_open -> doors_open: either door open
                                  (signals/door-state)

Track Model -> Train Model, ``track_model_to_train_model``: one
train's feed becomes its ``track`` input, field for field, with the
block named by its number; the Train Model knows the train's line. A
beacon passes unchanged once its logical payload checks out
(``utils.beacon_codec``: platform side ``L``, ``R`` or ``LR``, and at
most 128 characters in all, never truncated).

Track Controller -> Track Model, ``block_commands_to_track_model``:
per-block commands keyed by block number on one line, keyed instead by
the Track Model's names. In Phase 2 they come from the scripted
wayside that stands in for the Track Controller (``wayside_script``).

A train the CTC Office releases enters at its line's yard exit block
(D022). Until its Train Model first reports it, ``placement_report``
stands in for that report, so the Track Model puts the train on the
block and starts its feed.

Track Model -> Train Controller: the light a train saw as it entered
a block with a signal (the Track Model's ``signal_seen``, on that tick
only), in the Train Controller's spelling
(``train_edges.aspect_to_train_controller``). The Train Controller
keeps the last light it was given.
"""

from __future__ import annotations

__all__ = [
    "TRACK_MODEL_LINES",
    "YARD_EXIT_BLOCKS",
    "BlockNames",
    "block_commands_to_track_model",
    "placement_report",
    "track_model_to_train_model",
    "train_model_to_track_model",
]

import re
from collections.abc import Iterable, Mapping
from typing import Any

from utils.beacon_codec import encode_beacon

#: The Track Model's spelling of each line in the system (D023: the
#: Blue Line is out of scope).
TRACK_MODEL_LINES: Mapping[str, str] = {"GREEN": "Green", "RED": "Red"}

#: Where a released train enters each line (D022).
YARD_EXIT_BLOCKS: Mapping[str, str] = {"Green": "63", "Red": "9"}

# The Track Model's block name: line, section, number.
_NAME = re.compile(r"^(?P<line>[A-Z]+) (?P<section>[A-Z]+)-(?P<number>\d+)$")


class BlockNames:
    """The Track Model's block names, against line and number."""

    def __init__(self) -> None:
        """Start knowing no block."""
        self._names: frozenset[str] = frozenset()
        self._by_block: dict[tuple[str, str], str] = {}
        self._by_name: dict[str, tuple[str, str]] = {}

    def __bool__(self) -> bool:
        """Whether any block is known yet."""
        return bool(self._by_name)

    def learn(self, names: Iterable[str]) -> None:
        """Take the Track Model's block names, as its outputs list them.

        A name not of the Track Model's form, or on a line outside the
        system, is left out. The same names again change nothing.
        """
        names = frozenset(names)
        if names == self._names:
            return
        self._names = names
        self._by_block = {}
        self._by_name = {}
        for name in names:
            match = _NAME.match(name)
            if match is None or match["line"] not in TRACK_MODEL_LINES:
                continue
            block = (TRACK_MODEL_LINES[match["line"]], match["number"])
            self._by_block[block] = name
            self._by_name[name] = block

    def track_model_name(self, line: str, number: str) -> str:
        """Return the Track Model's name for a block.

        Raises:
            KeyError: If the Track Model has no such block.
        """
        return self._by_block[(line, number)]

    def block(self, name: str) -> tuple[str, str]:
        """Return the line and number of a Track Model block name.

        Raises:
            KeyError: If the Track Model has no such block.
        """
        return self._by_name[name]


def block_commands_to_track_model(
    commands: Mapping[str, Mapping[str, Any]], line: str, names: BlockNames
) -> dict[str, dict[str, Any]]:
    """Key per-block commands by the Track Model's block names.

    Args:
        commands: Command maps by field, such as
            ``commanded_speed_mps``, each keyed by block number.
        line: The line the blocks are on.
        names: The Track Model's block names.

    Raises:
        KeyError: If a block is unknown.
    """
    return {
        field: {
            names.track_model_name(line, number): value
            for number, value in values.items()
        }
        for field, values in commands.items()
    }


def placement_report(name: str) -> dict[str, Any]:
    """Return a new train's report: at rest at the start of a block.

    It stands in for the train's Train Model, which has not reported
    it yet, so it has no room for passengers.

    Args:
        name: The block, in the Track Model's name.
    """
    return {
        "block_id": name,
        "offset_m": 0.0,
        "actual_speed_mps": 0.0,
        "block_changed": False,
        "passenger_capacity": 0,
        "doors_open": False,
    }


def train_model_to_track_model(
    outputs: Mapping[str, Any], line: str, names: BlockNames
) -> dict[str, Any]:
    """Map a train's Train Model outputs to its Track Model report.

    Args:
        outputs: The train's outputs, ``controller`` and ``track``.
        line: The train's line.
        names: The Track Model's block names.

    Raises:
        KeyError: If an output is missing, or the block is unknown.
    """
    track = outputs["track"]
    controller = outputs["controller"]
    return {
        "block_id": names.track_model_name(line, track["block_id"]),
        "offset_m": track["offset_m"],
        "actual_speed_mps": track["actual_speed_mps"],
        "block_changed": track["block_changed"],
        "passenger_capacity": track["passenger_capacity"],
        "doors_open": (
            controller["door_left_open"] or controller["door_right_open"]
        ),
    }


def track_model_to_train_model(
    feed: Mapping[str, Any], names: BlockNames
) -> dict[str, Any]:
    """Map a train's Track Model feed to its Train Model ``track``.

    Raises:
        KeyError: If a field is missing, or the block is unknown.
        ValueError: If the beacon's payload is malformed or too long.
    """
    info = feed["track_info"]
    signal = feed["track_signal"]
    beacon = feed["beacon"]
    _, number = names.block(info["block_id"])
    if beacon is not None:
        encode_beacon(
            beacon["station_name"], beacon["platform_side"],
            beacon["underground"],
        )
    return {
        "track_info": {
            "block_id": number,
            "grade_deg": info["grade_deg"],
            "elevation_m": info["elevation_m"],
            "speed_limit_mps": info["speed_limit_mps"],
            "polarity": info["polarity"],
            "station_name": info["station_name"],
        },
        "track_signal": {
            "commanded_speed_mps": signal["commanded_speed_mps"],
            "authority_blocks": signal["authority_blocks"],
        },
        "beacon": None if beacon is None else {
            "station_name": beacon["station_name"],
            "platform_side": beacon["platform_side"],
            "underground": beacon["underground"],
        },
        "passengers_boarded": feed["passengers_boarded"],
    }
