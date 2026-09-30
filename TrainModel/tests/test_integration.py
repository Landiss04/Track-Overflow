"""Physical invariants and regressions at command and velocity changes."""

from dataclasses import replace
import math

import pytest

from train_model.interface import FailureState, TrainConfig
from train_model.model import (
    InvalidInputError,
    InvalidTimeStepError,
    TrainModel,
)
from tests.test_physics import make_inputs, pct_to_deg, run_until_speed


@pytest.mark.parametrize("load", [0, 148, 222])
@pytest.mark.parametrize("dt", [0.01, 0.1, 1.0])
def test_launch_matches_constant_force_kinematics(
    load: int, dt: float
) -> None:
    """A command applies for the entire tick, including the first one."""
    cfg = TrainConfig()
    model = TrainModel(cfg)
    model.step(dt, make_inputs(boarded=load))
    model.step(dt, make_inputs(power_w=cfg.p_max_w))
    snap = model.snapshot()
    acceleration = cfg.f_max_n / snap.mass_kg - cfg.c_rr * cfg.g_mps2
    assert snap.velocity_mps == pytest.approx(acceleration * dt)
    assert snap.outputs.track.offset_m == pytest.approx(
        0.5 * acceleration * dt**2
    )


@pytest.mark.parametrize("power", [1e-6, 0.001, 1, 100, 118000, 480000])
@pytest.mark.parametrize("dt", [0.01, 0.1, 1.0])
def test_traction_work_does_not_exceed_supplied_energy(
    power: float, dt: float
) -> None:
    """Check both kinetic energy and work lost to rolling resistance."""
    cfg = TrainConfig()
    model = TrainModel(cfg)
    for _ in range(30):
        before = model.snapshot()
        model.step(dt, make_inputs(power_w=power))
        after = model.snapshot()
        dx = after.outputs.track.offset_m - before.outputs.track.offset_m
        kinetic = 0.5 * after.mass_kg * (
            after.velocity_mps**2 - before.velocity_mps**2
        )
        rolling = cfg.c_rr * after.mass_kg * cfg.g_mps2 * dx
        assert dx >= 0.0
        assert kinetic + rolling <= power * dt * (1 + 1e-9) + 1e-12


@pytest.mark.parametrize("failure", [False, True])
def test_cut_power_coasts_immediately(failure: bool) -> None:
    """Neither zero power nor engine failure carries over acceleration."""
    cfg = TrainConfig()
    model = TrainModel(cfg)
    run_until_speed(model, 5.0)
    before = model.snapshot()
    model.set_failures(FailureState(engine=failure))
    model.step(0.1, make_inputs(power_w=cfg.p_max_w if failure else 0))
    after = model.snapshot()
    acceleration = -cfg.c_rr * cfg.g_mps2
    assert after.velocity_mps == pytest.approx(
        before.velocity_mps + acceleration * 0.1
    )
    assert after.outputs.track.offset_m == pytest.approx(
        before.outputs.track.offset_m
        + before.velocity_mps * 0.1 + 0.5 * acceleration * 0.1**2
    )


@pytest.mark.parametrize("load", [0, 222])
@pytest.mark.parametrize("brake", ["service", "emergency"])
@pytest.mark.parametrize("grade", [-6.0, 0.0, 6.0])
def test_stop_distance_and_position_are_exact(
    load: int, brake: str, grade: float
) -> None:
    """Constant braking ends at v²/(2a), without backward displacement."""
    cfg = TrainConfig()
    model = TrainModel(cfg)
    model.step(0.1, make_inputs(boarded=load))
    run_until_speed(model, 5.0)
    start = model.snapshot()
    angle = math.atan(grade / 100)
    force = cfg.f_service_n if brake == "service" else cfg.f_emergency_n
    decel = (
        force / start.mass_kg + cfg.g_mps2 * math.sin(angle)
        + cfg.c_rr * cfg.g_mps2 * math.cos(angle)
    )
    command = make_inputs(
        service=brake == "service", emergency=brake == "emergency",
        grade_deg=pct_to_deg(grade),
    )
    previous = start.outputs.track.offset_m
    for _ in range(200):
        result = model.step(0.1, command)
        assert result.track.offset_m >= previous
        previous = result.track.offset_m
        if result.track.actual_speed_mps == 0.0:
            break
    else:
        pytest.fail("train did not stop")
    assert previous - start.outputs.track.offset_m == pytest.approx(
        start.velocity_mps**2 / (2 * decel), abs=1e-10
    )
    for _ in range(5):
        result = model.step(0.1, command)
        assert result.track.offset_m == previous
        assert result.track.actual_speed_mps == 0.0


def test_braking_stops_rollback_without_forward_jump() -> None:
    """The stop event works with signed negative velocity as well."""
    cfg = TrainConfig()
    model = TrainModel(cfg)
    for _ in range(10):
        model.step(0.1, make_inputs(grade_deg=pct_to_deg(6)))
    before = model.snapshot()
    decel = cfg.f_emergency_n / before.mass_kg + cfg.c_rr * cfg.g_mps2
    result = model.step(1.0, make_inputs(emergency=True))
    assert result.track.actual_speed_mps == 0.0
    assert result.track.offset_m == pytest.approx(
        before.outputs.track.offset_m - before.velocity_mps**2 / (2 * decel)
    )


@pytest.mark.parametrize("dt", [0, -0.1, math.nan, math.inf, -math.inf])
def test_bad_timestep_preserves_state(dt: float) -> None:
    """Reject invalid time before passengers, RNG or state are changed."""
    model = TrainModel(TrainConfig())
    before = model.snapshot()
    with pytest.raises(InvalidTimeStepError):
        model.step(dt, make_inputs(boarded=10, door_left=True))
    assert model.snapshot() == before


@pytest.mark.parametrize("power", [-1, -1000, -1e9, math.nan, math.inf])
def test_bad_power_preserves_moving_state(power: float) -> None:
    """Negative power is not an implicit, unlimited brake command."""
    model = TrainModel(TrainConfig())
    run_until_speed(model, 5)
    before = model.snapshot()
    with pytest.raises(InvalidInputError):
        model.step(0.1, make_inputs(power_w=power, boarded=10))
    assert model.snapshot() == before


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("field", [
    "grade_deg", "elevation_m", "speed_limit_mps", "temp_setpoint_c",
    "commanded_speed_mps", "passengers_boarded",
])
def test_nonfinite_input_is_rejected_atomically(
    field: str, value: float
) -> None:
    """Every numeric boundary input is finite before mutation begins."""
    model = TrainModel(TrainConfig())
    good = make_inputs(boarded=20)
    model.step(0.1, good)
    before = model.snapshot()
    if field == "temp_setpoint_c":
        bad = replace(good, controller=replace(
            good.controller, temp_setpoint_c=value
        ))
    elif field == "passengers_boarded":
        bad = replace(good, track=replace(
            good.track, passengers_boarded=value
        ))
    elif field == "commanded_speed_mps":
        bad = replace(good, track=replace(
            good.track, track_signal=replace(
                good.track.track_signal, commanded_speed_mps=value
            )
        ))
    else:
        bad = replace(good, track=replace(
            good.track, track_info=replace(
                good.track.track_info, **{field: value}
            )
        ))
    with pytest.raises(InvalidInputError):
        model.step(0.1, bad)
    assert model.snapshot() == before
    model.step(0.1, make_inputs(door_left=True))
    control = TrainModel(TrainConfig())
    control.step(0.1, good)
    control.step(0.1, make_inputs(door_left=True))
    assert model.snapshot() == control.snapshot()


def test_speed_control_is_not_added_to_physics() -> None:
    """Zero speed commands do not substitute for controller braking."""
    cfg = TrainConfig()
    model = TrainModel(cfg)
    command = make_inputs(power_w=cfg.p_max_w)
    command = replace(command, track=replace(
        command.track,
        track_info=replace(command.track.track_info, speed_limit_mps=0),
        track_signal=replace(
            command.track.track_signal, commanded_speed_mps=0
        ),
    ))
    for _ in range(1000):
        model.step(0.1, command)
    assert model.snapshot().velocity_mps > cfg.v_max_mps


@pytest.mark.parametrize("power", [1e-320, 1e-300, 1e-100, 1e-12])
def test_tiny_power_approaches_force_equilibrium(power: float) -> None:
    """Subnormal products must not be mistaken for velocity reversals."""
    cfg = TrainConfig()
    model = TrainModel(cfg)
    model.step(0.1, make_inputs(power_w=power))
    snap = model.snapshot()
    equilibrium = power / (cfg.c_rr * snap.mass_kg * cfg.g_mps2)
    assert snap.velocity_mps == pytest.approx(equilibrium, rel=1e-10, abs=0)


def test_constant_power_speed_and_position_converge() -> None:
    """Compare with the analytic force-limited then constant-power run."""
    cfg = replace(TrainConfig(), c_rr=0)
    power = 100.0
    mass = cfg.m_empty_kg + cfg.n_crew * cfg.passenger_mass_kg
    transition_time = mass * power / cfg.f_max_n**2
    transition_speed = power / cfg.f_max_n
    speed = math.sqrt(
        transition_speed**2 + 2 * power * (1 - transition_time) / mass
    )
    distance = (
        0.5 * transition_speed * transition_time
        + mass * (speed**3 - transition_speed**3) / (3 * power)
    )
    errors = []
    for dt in [0.1, 0.05, 0.01]:
        model = TrainModel(cfg)
        for _ in range(round(1 / dt)):
            model.step(dt, make_inputs(power_w=power))
        snap = model.snapshot()
        assert snap.velocity_mps == pytest.approx(speed, rel=1e-10)
        errors.append(abs(snap.outputs.track.offset_m - distance))
    assert errors[2] < errors[1] < errors[0]
    assert errors[2] < 1e-5
