"""Stub-only tests. Skipped once the real implementation lands."""

from __future__ import annotations

import pytest

from train_model.interface import FailureState, TrainConfig
from train_model.model import STUB, TrainModel
from tests.test_contract import DT_S, make_inputs

pytestmark = pytest.mark.skipif(not STUB, reason="real implementation")


def test_stub_returns_safe_values() -> None:
    """Check zeros, False, no beacon, echoed block ID, and full capacity."""
    config = TrainConfig()
    model = TrainModel(config)
    model.set_failures(FailureState(True, True, True))
    out = model.step(DT_S, make_inputs(block_id="B7"))
    ctl, trk = out.controller, out.track
    assert ctl.actual_speed_mps == 0.0
    assert ctl.cabin_temp_c == 0.0
    assert ctl.commanded_speed_mps == 0.0
    assert ctl.speed_limit_mps == 0.0
    assert ctl.authority_block_id is None
    assert ctl.beacon is None
    assert not any((ctl.emergency_brake_active, ctl.service_brake_active,
                    ctl.door_left_open, ctl.door_right_open,
                    ctl.interior_lights_on, ctl.exterior_lights_on))
    assert ctl.failures == FailureState()
    assert trk.block_id == "B7"
    assert trk.offset_m == 0.0
    assert trk.actual_speed_mps == 0.0
    assert trk.block_changed is False
    assert trk.passenger_capacity == config.capacity
