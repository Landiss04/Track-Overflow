"""Seeded invariant fuzz of the Train Model's public protocol.

Random but reproducible tick sequences drive ``TrainModel`` through
its boundary only: steps, failures, passenger pulls and the test-only
latch clear, with most inputs held for a while so the train actually
moves, brakes, rolls back and stops. After every step the outputs and
snapshot must satisfy physical and contract invariants. Each failure
message names the seed and tick, so a failing case can be replayed.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, replace

import pytest

from train_model.interface import (
    ControllerCommands,
    FailureState,
    TrackInfo,
    TrackInputs,
    TrackSignal,
    TrainConfig,
    TrainModelInputs,
)
from train_model.model import (
    InvalidInputError,
    InvalidTimeStepError,
    TrainModel,
)

DT_S = 0.1
TICKS = 300
SEEDS = range(30)
CFG = TrainConfig()


@dataclass
class Tick:
    """One tick: actions taken before the step, then its inputs."""

    inputs: TrainModelInputs
    failures: FailureState | None
    pull: bool
    clear: bool


def _held(rng: random.Random, draw):
    """Yield draw()'s values, each held for 1 to 40 ticks."""
    while True:
        value = draw()
        for _ in range(rng.randint(1, 40)):
            yield value


def scenario(seed: int, ticks: int = TICKS) -> list[Tick]:
    """Return a reproducible random tick sequence for ``seed``."""
    rng = random.Random(seed)
    power = _held(rng, lambda: rng.choice([
        0.0,
        10 ** rng.uniform(-12, 0),
        rng.uniform(0, CFG.p_max_w),
        rng.uniform(CFG.p_max_w, 3 * CFG.p_max_w),
    ]))
    service = _held(rng, lambda: rng.random() < 0.15)
    emergency = _held(rng, lambda: rng.random() < 0.15)
    doors = _held(rng, lambda: (rng.random() < 0.1, rng.random() < 0.1))
    lights = _held(rng, lambda: (rng.random() < 0.5, rng.random() < 0.5))
    setpoint = _held(rng, lambda: rng.uniform(-40, 60))
    grade = _held(rng, lambda: 0.0 if rng.random() < 0.6
                  else rng.uniform(-8, 8))
    station = _held(rng, lambda: "Station B" if rng.random() < 0.2 else None)
    signal = _held(rng, lambda: (rng.uniform(0, 25), rng.randint(0, 10)))
    polarity = False
    out = []
    for _ in range(ticks):
        if rng.random() < 0.03:
            polarity = not polarity
        boarded = rng.randint(0, 400) if rng.random() < 0.1 else 0
        left, right = next(doors)
        interior, exterior = next(lights)
        commanded, authority = next(signal)
        inputs = TrainModelInputs(
            controller=ControllerCommands(
                power_cmd_w=next(power),
                service_brake=next(service),
                emergency_brake=next(emergency),
                interior_lights=interior,
                exterior_lights=exterior,
                door_left_open=left,
                door_right_open=right,
                temp_setpoint_c=next(setpoint),
                announcement="",
            ),
            track=TrackInputs(
                track_info=TrackInfo(
                    block_id="1",
                    grade_deg=next(grade),
                    elevation_m=0.0,
                    speed_limit_mps=13.9,
                    polarity=polarity,
                    station_name=next(station),
                ),
                track_signal=TrackSignal(
                    commanded_speed_mps=commanded,
                    authority_blocks=authority,
                ),
                beacon=None,
                passengers_boarded=boarded,
            ),
        )
        failures = None
        if rng.random() < 0.02:
            failures = FailureState(rng.random() < 0.5, rng.random() < 0.5,
                                    rng.random() < 0.5)
        out.append(Tick(inputs, failures, rng.random() < 0.02,
                        rng.random() < 0.02))
    return out


def apply_actions(model: TrainModel, tick: Tick) -> None:
    """Take a tick's UI and test actions, before its step."""
    if tick.failures is not None:
        model.set_failures(tick.failures)
    if tick.pull:
        model.pull_passenger_emergency_brake()
    if tick.clear:
        model.clear_passenger_brake_for_test()


def force_bound_n(mass_kg: float, grade_deg: float) -> float:
    """Largest net force any combination of inputs can produce."""
    gravity = mass_kg * CFG.g_mps2 * (
        abs(math.sin(math.radians(grade_deg))) + CFG.c_rr
    )
    return CFG.f_max_n + CFG.f_emergency_n + gravity


@pytest.mark.parametrize("seed", SEEDS)
def test_every_step_keeps_the_invariants(seed: int) -> None:
    """Check the invariants after every random step."""
    model = TrainModel(TrainConfig(seed=seed))
    for n, tick in enumerate(scenario(seed)):
        apply_actions(model, tick)
        before = model.snapshot()
        cmd, trk = tick.inputs.controller, tick.inputs.track
        grade = trk.track_info.grade_deg

        start = time.perf_counter()
        outputs = model.step(DT_S, tick.inputs)
        elapsed = time.perf_counter() - start
        snap = model.snapshot()
        ctl, out = outputs.controller, outputs.track
        v0, v = before.velocity_mps, snap.velocity_mps
        where = (f"seed {seed} tick {n}: v {v0!r} -> {v!r}, "
                 f"inputs {tick.inputs}")

        assert elapsed < 0.25, f"{where}: step took {elapsed:.3f} s"

        floats = (ctl.actual_speed_mps, ctl.cabin_temp_c, out.offset_m,
                  out.actual_speed_mps, snap.velocity_mps,
                  snap.acceleration_mps2, snap.mass_kg)
        assert all(math.isfinite(x) for x in floats), f"{where}: {floats}"

        assert 0 <= snap.n_passengers <= CFG.capacity, where
        assert out.passenger_capacity == (
            CFG.capacity - snap.n_passengers), where
        assert ctl.actual_speed_mps == out.actual_speed_mps == v, where

        # Door interlock, commented out with the model's pending the
        # course instructor (Kevin 2026-10-06):
        # if ctl.door_left_open or ctl.door_right_open:
        #     assert v == 0.0, f"{where}: a door is open while moving"

        # Brake failure blocks only the service brake.
        emergency = cmd.emergency_brake or snap.passenger_ebrake_pulled
        assert ctl.emergency_brake_active == emergency, where
        assert ctl.service_brake_active == (
            cmd.service_brake and not emergency and not snap.failures.brake
        ), where

        if snap.failures.signal_pickup:
            assert ctl.commanded_speed_mps == 0.0, where
            assert ctl.authority_blocks == 0, where
        else:
            assert ctl.commanded_speed_mps == (
                trk.track_signal.commanded_speed_mps), where
            assert ctl.authority_blocks == (
                trk.track_signal.authority_blocks), where

        bound = force_bound_n(snap.mass_kg, grade)
        assert abs(snap.acceleration_mps2) <= bound / snap.mass_kg + 1e-9, (
            f"{where}: a = {snap.acceleration_mps2}")
        mass = min(before.mass_kg, snap.mass_kg)
        assert abs(v - v0) <= DT_S * bound / mass + 1e-9, where

        braking = ctl.emergency_brake_active or ctl.service_brake_active
        if grade == 0.0 and braking:
            # Brakes stop the train; they never reverse it.
            if v0 > 0.0:
                assert v >= 0.0, f"{where}: braking reversed the train"
            if v0 < 0.0:
                assert v <= 0.0, f"{where}: braking reversed the train"
        if grade == 0.0 and before.failures.engine and v0 >= 0.0:
            assert v <= v0 + 1e-12, f"{where}: traction with a failed engine"
        if grade == 0.0 and cmd.power_cmd_w == 0.0 and not braking and v0 > 0:
            assert v <= v0 + 1e-12, f"{where}: coasting sped up"


def _moving_model() -> TrainModel:
    """A model partway through a run, moving on a grade."""
    model = TrainModel(TrainConfig(seed=7))
    for tick in scenario(7, ticks=120):
        apply_actions(model, tick)
        model.step(DT_S, tick.inputs)
    model.step(DT_S, _valid())
    return model


def _valid() -> TrainModelInputs:
    return scenario(3, ticks=1)[0].inputs


def _with(inputs: TrainModelInputs, **changes) -> TrainModelInputs:
    """Return ``inputs`` with controller or track fields changed."""
    controller, info, signal = {}, {}, {}
    for name, value in changes.items():
        if name in ControllerCommands.__dataclass_fields__:
            controller[name] = value
        elif name in TrackInfo.__dataclass_fields__:
            info[name] = value
        else:
            signal[name] = value
    track = inputs.track
    if "passengers_boarded" in signal:
        track = replace(track, passengers_boarded=signal.pop(
            "passengers_boarded"))
    return replace(
        inputs,
        controller=replace(inputs.controller, **controller),
        track=replace(
            track,
            track_info=replace(track.track_info, **info),
            track_signal=replace(track.track_signal, **signal),
        ),
    )


@pytest.mark.parametrize("dt, changes", [
    (DT_S, {"power_cmd_w": math.nan}),
    (DT_S, {"power_cmd_w": math.inf}),
    (DT_S, {"power_cmd_w": -1.0}),
    (DT_S, {"grade_deg": math.nan}),
    (DT_S, {"temp_setpoint_c": math.inf}),
    (DT_S, {"authority_blocks": -1}),
    (DT_S, {"passengers_boarded": 1.5}),
    (0.0, {}),
    (-0.1, {}),
    (math.nan, {}),
])
def test_invalid_inputs_change_nothing(dt: float, changes: dict) -> None:
    """Check a rejected step leaves the model exactly as it was."""
    model = _moving_model()
    before = model.snapshot()
    with pytest.raises((InvalidInputError, InvalidTimeStepError)):
        model.step(dt, _with(_valid(), **changes))
    assert model.snapshot() == before


def test_snapshot_has_no_side_effects() -> None:
    """Check reading the snapshot never changes what the model does."""
    watched = TrainModel(TrainConfig(seed=11))
    unwatched = TrainModel(TrainConfig(seed=11))
    for tick in scenario(11):
        for model in (watched, unwatched):
            apply_actions(model, tick)
        assert watched.snapshot() == watched.snapshot()
        watched.step(DT_S, tick.inputs)
        watched.snapshot()
        unwatched.step(DT_S, tick.inputs)
    assert watched.snapshot() == unwatched.snapshot()


def test_the_same_seed_and_inputs_give_the_same_run() -> None:
    """Check two models with one seed and one scenario end identical."""
    runs = []
    for _ in range(2):
        model = TrainModel(TrainConfig(seed=5))
        for tick in scenario(5):
            apply_actions(model, tick)
            model.step(DT_S, tick.inputs)
        runs.append(model.snapshot())
    assert runs[0] == runs[1]
