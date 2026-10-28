"""The logical beacon bound includes JSON punctuation and ASCII escapes."""

from __future__ import annotations

import dataclasses
import json

import pytest

from common.harness.track_edges import (
    BlockNames,
    track_model_to_train_model,
)
from train_model.harness import TestHarnessState as HarnessState
from train_model.interface import Beacon, TrainConfig
from train_model.model import InvalidInputError, TrainModel
from train_model.track_stub import TrackBlock
from train_model.wire import decode_inputs, encode_outputs
from tests.test_physics_extended import DT_S, inp
from utils.beacon_codec import encode_beacon


@pytest.mark.parametrize("side", ["L", "R", "LR"])
@pytest.mark.parametrize("underground", [False, True])
@pytest.mark.parametrize("prefix", ["", '"\\', "é", "🚆"])
def test_exact_boundary_counts_the_complete_encoding(
    side: str, underground: bool, prefix: str,
) -> None:
    base = json.dumps([prefix, side, underground], ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False)
    name = prefix + "S" * (128 - len(base))
    payload = encode_beacon(name, side, underground)
    assert len(payload) == len(payload.encode("utf-8")) == 128
    assert payload.isascii()
    assert json.loads(payload) == [name, side, underground]
    model = TrainModel(TrainConfig())
    beacon = Beacon(name, side, underground)
    data = dataclasses.asdict(inp(beacon=beacon))
    # The array is logical encoding; the harness still carries named fields.
    assert isinstance(data["track"]["beacon"], dict)
    # Heard on the block before the station; reported on the station.
    assert model.step(DT_S, decode_inputs(data)).controller.beacon is None
    out = model.step(DT_S, inp(station=name, polarity=False))
    assert out.controller.beacon == beacon
    assert encode_outputs(out)["controller"]["beacon"] == (
        dataclasses.asdict(beacon)
    )
    assert model.step(DT_S, inp()).controller.beacon is None
    with pytest.raises(ValueError, match="129"):
        encode_beacon(name + "S", side, underground)
    with pytest.raises(InvalidInputError, match="129"):
        model.step(DT_S, inp(beacon=Beacon(name + "S", side, underground)))


def test_canonical_encoding() -> None:
    assert encode_beacon("Central", "LR", False) == '["Central","LR",false]'
    assert encode_beacon('é🚆"\\', "L", True) == (
        '["\\u00e9\\ud83d\\ude86\\\"\\\\","L",true]'
    )


@pytest.mark.parametrize("values", [
    (None, "L", False), (1, "L", False), ([], "L", False),
    ("S", None, False), ("S", [], False), ("S", 1, False),
    ("S", "", False), ("S", "Q", False), ("S", "l", False),
    ("S", "L", 0), ("S", "L", "false"), ("S", "L", None),
    ("S", "L", float("nan")),
])
def test_malformed_fields_are_rejected(values: tuple) -> None:
    with pytest.raises(ValueError, match="beacon"):
        encode_beacon(*values)
    model = TrainModel(TrainConfig())
    before = model.snapshot()
    with pytest.raises(InvalidInputError):
        model.step(DT_S, inp(beacon=Beacon(*values)))
    assert model.snapshot() == before


def test_rejection_preserves_state_latch_and_random_sequence() -> None:
    model = TrainModel(TrainConfig(seed=73))
    control = TrainModel(TrainConfig(seed=73))
    for train in (model, control):
        train.pull_passenger_emergency_brake()
        train.step(DT_S, inp(boarded=150, door_left=True))
    before = model.snapshot()
    invalid = inp(beacon=Beacon("S" * 114, "LR", False),
                  door_left=True, boarded=50, polarity=False)
    with pytest.raises(InvalidInputError, match="129"):
        model.step(DT_S, invalid)
    assert model.snapshot() == before
    for _ in range(5):
        for inputs in (inp(), inp(480_000.0), inp(emergency=True),
                       inp(emergency=True, door_left=True, boarded=50)):
            assert model.step(DT_S, inputs) == control.step(DT_S, inputs)
            assert model.snapshot() == control.snapshot()


def _edge_beacon(name: str) -> dict:
    # The harness's Track Model -> Train Model edge, on a feed whose
    # beacon carries ``name``. The edge passes it on unchecked.
    names = BlockNames()
    names.learn(["GREEN K-64"])
    feed = {
        "track_info": {
            "block_id": "GREEN K-64", "grade_deg": 0.0, "elevation_m": 0.0,
            "speed_limit_mps": 19.4, "polarity": False, "station_name": None,
        },
        "track_signal": {"commanded_speed_mps": 0.0, "authority_blocks": 0},
        "beacon": {"station_name": name, "platform_side": "L",
                   "underground": False},
        "passengers_boarded": 0,
    }
    return track_model_to_train_model(feed, names)["beacon"]


def test_the_harness_passes_a_beacon_for_the_model_to_check() -> None:
    # Kevin Schillinger, 2026-10-20: the harness passes the beacon on
    # and the Train Model rejects it, so only that train misses a tick.
    name = "S" * 115  # One past the bound: 129 characters in all.
    passed = _edge_beacon(name)
    assert passed["station_name"] == name
    model = TrainModel(TrainConfig())
    data = dataclasses.asdict(inp())
    data["track"]["beacon"] = passed
    with pytest.raises(InvalidInputError, match="129"):
        model.step(DT_S, decode_inputs(data))


def test_stand_ins_validate_without_importing_model_types() -> None:
    name = "S" * 114  # [name,"L",false] has 14 characters of overhead.
    assert TrackBlock("1", 50, 0, 0, 10, "", name).beacon_station == name
    with pytest.raises(ValueError, match="129"):
        TrackBlock("1", 50, 0, 0, 10, "", name + "S")
    values = {}
    # Build only the staged fields used before the remaining inputs are read.
    values.update(beacon_station=name + "S", beacon_platform_side="L",
                  beacon_underground=False)
    with pytest.raises(ValueError, match="129"):
        HarnessState._build_inputs(values)
