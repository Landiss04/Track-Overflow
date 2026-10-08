"""The Train Model window's clock agrees with the test UI's.

The model adds each step's dt to its elapsed time. 0.1 s is not exact in
binary, so a plain running sum falls behind: after an hour it reads
3599.9999999978 s and the window's clock shows 00:59:59 while the test
UI, which multiplies its tick count by dt, shows 01:00:00.
"""

from __future__ import annotations

import math

from train_model.interface import TrainConfig
from train_model.model import TrainModel
from tests.test_physics import make_inputs

DT = 0.1


def clock_of(seconds: float) -> str:
    """Format elapsed seconds as the test UI does."""
    total = int(seconds + 1e-9)
    return f"{total // 3600:02d}:{total // 60 % 60:02d}:{total % 60:02d}"


def test_elapsed_time_is_the_exact_sum_of_the_steps() -> None:
    """Check two hours of 0.1 s steps sum to within an ulp of exact."""
    model = TrainModel(TrainConfig())
    inputs = make_inputs()
    for _ in range(72_000):
        model.step(DT, inputs)
    exact = math.fsum([DT] * 72_000)
    assert abs(model.snapshot().elapsed_s - exact) <= math.ulp(exact)


def test_the_window_clock_matches_the_test_ui_for_two_hours() -> None:
    """Check the two clocks agree on every tick of two hours."""
    from train_model.state import TrainModelState
    state = TrainModelState()
    inputs = make_inputs()
    mismatches = []
    for tick in range(1, 72_001):
        state.step(DT, inputs)
        if state.snapshot["clock"] != clock_of(tick * DT):
            mismatches.append(tick)
    assert not mismatches, (len(mismatches), mismatches[:3])
