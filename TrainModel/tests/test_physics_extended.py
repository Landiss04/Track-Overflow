"""Extended physics verification for ``train_model.model.TrainModel``.

Every expectation here is derived independently from first principles
(Newton's second law, the work-energy theorem, impulse-momentum, the
SRS Appendix B braking formula, and an RK4 reference integration) and
from the ``TrainConfig`` primitives. The implementation is never
consulted for an expected value.

Tests marked ``xfail(strict=True)`` record a confirmed defect or an
unphysical behaviour. They are strict so that a fix makes them fail,
prompting removal of the marker.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable
from typing import Any

import pytest

from train_model.interface import (
    Beacon,
    ControllerCommands,
    FailureState,
    TrackInfo,
    TrackInputs,
    TrackSignal,
    TrainConfig,
    TrainModelInputs,
    TrainModelOutputs,
    TrainModelSnapshot,
)
from train_model.model import InvalidTimeStepError, TrainModel

DT_S = 0.1
CFG = TrainConfig()
G = CFG.g_mps2
FULL = CFG.capacity
REF_LOAD = round(CFG.capacity * CFG.ref_load_fraction)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def pct(grade_percent: float) -> float:
    """Return the angle in degrees of a grade given in percent."""
    return math.degrees(math.atan(grade_percent / 100.0))


def inp(
    power_w: float = 0.0,
    *,
    service: bool = False,
    emergency: bool = False,
    grade_deg: float = 0.0,
    boarded: int = 0,
    door_left: bool = False,
    door_right: bool = False,
    polarity: bool = True,
    interior: bool = False,
    exterior: bool = False,
    setpoint_c: float = 21.0,
    block_id: str = "A1",
    speed_limit_mps: float = 19.0,
    cmd_speed_mps: float = 10.0,
    authority: str = "A9",
    beacon: Beacon | None = None,
) -> TrainModelInputs:
    """Return a fully populated input set with the named overrides."""
    return TrainModelInputs(
        controller=ControllerCommands(
            power_cmd_w=power_w,
            service_brake=service,
            emergency_brake=emergency,
            interior_lights=interior,
            exterior_lights=exterior,
            door_left_open=door_left,
            door_right_open=door_right,
            temp_setpoint_c=setpoint_c,
            announcement="",
        ),
        track=TrackInputs(
            track_info=TrackInfo(
                block_id=block_id,
                grade_deg=grade_deg,
                elevation_m=0.0,
                speed_limit_mps=speed_limit_mps,
                polarity=polarity,
            ),
            track_signal=TrackSignal(
                commanded_speed_mps=cmd_speed_mps,
                authority_block_id=authority,
            ),
            beacon=beacon,
            passengers_boarded=boarded,
        ),
    )


def mass_of(n_passengers: int, cfg: TrainConfig = CFG) -> float:
    """Return the operating mass: empty plus crew and passengers."""
    n_people = cfg.n_crew + n_passengers
    return cfg.m_empty_kg + n_people * cfg.passenger_mass_kg


def roll_n(mass_kg: float, grade_deg: float = 0.0) -> float:
    """Return the rolling resistance magnitude, normal to the grade."""
    return CFG.c_rr * mass_kg * G * math.cos(math.radians(grade_deg))


def fresh(n_passengers: int = 0, cfg: TrainConfig = CFG) -> TrainModel:
    """Return a model at rest with ``n_passengers`` boarded."""
    model = TrainModel(cfg)
    if n_passengers:
        model.step(DT_S, inp(boarded=n_passengers))
    return model


def vel(model: Any) -> float:
    """Return the model's velocity."""
    value: float = model.snapshot().velocity_mps
    return value


def acc(model: Any) -> float:
    """Return the model's acceleration."""
    value: float = model.snapshot().acceleration_mps2
    return value


def pos(model: Any) -> float:
    """Return the model's offset within its block."""
    value: float = model.snapshot().outputs.track.offset_m
    return value


def launch(
    model: Any,
    target_mps: float,
    power_w: float = CFG.p_max_w,
    grade_deg: float = 0.0,
) -> None:
    """Step at ``power_w`` until the velocity reaches ``target_mps``."""
    for _ in range(20_000):
        if vel(model) >= target_mps:
            return
        model.step(DT_S, inp(power_w, grade_deg=grade_deg))
    pytest.fail(f"never reached {target_mps} m/s")


def run_to_stop(
    model: TrainModel, make: Callable[[], TrainModelInputs]
) -> None:
    """Step until the velocity is exactly zero."""
    for _ in range(20_000):
        model.step(DT_S, make())
        if vel(model) == 0.0:
            return
    pytest.fail("never stopped")


def solve_grade(threshold: Callable[[float], float]) -> float:
    """Bisect for the grade in degrees where ``threshold`` crosses zero."""
    lo, hi = 0.0, 60.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if threshold(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


BRAKE_FORCE = {
    "service": CFG.f_service_n,
    "emergency": CFG.f_emergency_n,
}


def brake_inputs(
    kind: str, power_w: float = 0.0, grade_deg: float = 0.0
) -> TrainModelInputs:
    """Return inputs commanding the named brake."""
    return inp(power_w, service=kind == "service",
               emergency=kind == "emergency", grade_deg=grade_deg)


class Recorder:
    """Wrap a model and record ``(v, a, x)`` after every step."""

    def __init__(self, model: TrainModel) -> None:
        self.model = model
        self.history: list[tuple[float, float, float]] = []

    def step(self, dt: float, inputs: TrainModelInputs) -> TrainModelOutputs:
        """Step the wrapped model and record its state."""
        out = self.model.step(dt, inputs)
        self.history.append((vel(self.model), acc(self.model),
                             pos(self.model)))
        return out

    def snapshot(self) -> TrainModelSnapshot:
        """Return the wrapped model's snapshot."""
        return self.model.snapshot()


# --------------------------------------------------------------------------- #
# A. Configuration and derived constants
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("cfg", [
    TrainConfig(),
    TrainConfig(m_empty_kg=30_000.0),
    TrainConfig(capacity=150),
    TrainConfig(passenger_mass_kg=80.0),
], ids=["default", "lighter", "smaller", "heavier-people"])
def test_derived_forces_follow_primitives(cfg: TrainConfig) -> None:
    """Check derived values recompute from the primitives."""
    n_ref = round(cfg.capacity * cfg.ref_load_fraction)
    m_ref = cfg.m_empty_kg + n_ref * cfg.passenger_mass_kg
    assert cfg.m_ref_kg == pytest.approx(m_ref, rel=1e-12)
    assert cfg.f_max_n == pytest.approx(
        m_ref * cfg.accel_ref_mps2, rel=1e-12)
    assert cfg.f_service_n == pytest.approx(
        m_ref * cfg.decel_service_mps2, rel=1e-12)
    assert cfg.f_emergency_n == pytest.approx(
        m_ref * cfg.decel_emergency_mps2, rel=1e-12)


def test_passenger_mass_is_170_lb() -> None:
    """Check the mass per person is 170 lb in kilograms."""
    assert CFG.passenger_mass_kg == pytest.approx(
        170 * 0.45359237, abs=1e-4)


def test_max_speed_is_70_kmh() -> None:
    """Check the maximum speed is the datasheet 70 km/h."""
    assert CFG.v_max_mps == pytest.approx(70.0 / 3.6, rel=1e-12)


def test_capacity_is_seated_plus_standing() -> None:
    """Check capacity is 74 seated plus 148 standing."""
    assert CFG.capacity == 74 + 148


def test_config_is_immutable() -> None:
    """Check the vehicle constants cannot be changed at run time."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        CFG.p_max_w = 1.0  # type: ignore[misc]


@pytest.mark.parametrize(("force", "rate"), [
    ("f_max_n", "accel_ref_mps2"),
    ("f_service_n", "decel_service_mps2"),
    ("f_emergency_n", "decel_emergency_mps2"),
])
def test_rated_rate_at_reference_mass(force: str, rate: str) -> None:
    """Check each force gives its datasheet rate on the 2/3-load mass."""
    assert getattr(CFG, force) / CFG.m_ref_kg == pytest.approx(
        getattr(CFG, rate), rel=1e-12)


def test_base_speed_where_power_limit_takes_over() -> None:
    """Check P_max / F_max lies just below the maximum speed."""
    base = CFG.p_max_w / CFG.f_max_n
    assert 18.0 < base < CFG.v_max_mps


# --------------------------------------------------------------------------- #
# B. Mass
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("n", [0, 1, 37, REF_LOAD, FULL - 1, FULL])
def test_operating_mass_after_boarding(n: int) -> None:
    """Check operating mass counts crew and passengers."""
    model = fresh(n)
    assert model.snapshot().n_passengers == n
    assert model.snapshot().mass_kg == pytest.approx(mass_of(n), rel=1e-12)


@pytest.mark.parametrize("boarded", [FULL + 1, 300, 10_000])
def test_overboarding_clamps_to_capacity(boarded: int) -> None:
    """Check boarding beyond capacity stops at capacity."""
    model = fresh(boarded)
    assert model.snapshot().n_passengers == FULL
    assert model.snapshot().outputs.track.passenger_capacity == 0


def test_negative_boarding_is_ignored() -> None:
    """Check a negative boarding count removes nobody."""
    model = fresh(10)
    model.step(DT_S, inp(boarded=-5))
    assert model.snapshot().n_passengers == 10


def test_crew_in_operating_mass_not_in_reference_mass() -> None:
    """Check crew count toward operating mass but not reference mass."""
    model = fresh(REF_LOAD)
    crew_kg = CFG.n_crew * CFG.passenger_mass_kg
    assert model.snapshot().mass_kg - CFG.m_ref_kg == pytest.approx(
        crew_kg, rel=1e-9)


# --------------------------------------------------------------------------- #
# C. Traction
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("n", [0, FULL])
@pytest.mark.parametrize("power_w", [1.0, 1_000.0, 100_000.0, 480_000.0,
                                     2_000_000.0])
def test_first_tick_from_rest_uses_full_tractive_effort(
        power_w: float, n: int) -> None:
    """Check P/v saturates to F_max at v = 0 for any positive power."""
    model = fresh(n)
    x0 = pos(model)
    model.step(DT_S, inp(power_w))
    m = mass_of(n)
    a1 = (CFG.f_max_n - roll_n(m)) / m
    assert acc(model) == pytest.approx(a1, rel=1e-12)
    # Trapezoidal start from a_prev = 0: half the acceleration lands.
    assert vel(model) == pytest.approx(DT_S / 2 * a1, rel=1e-12)
    assert pos(model) - x0 == pytest.approx(
        DT_S / 2 * vel(model), rel=1e-12)


def test_zero_power_at_rest_stays_at_rest() -> None:
    """Check an unpowered train on flat track never moves."""
    model = fresh()
    for _ in range(100):
        model.step(DT_S, inp(0.0))
        assert vel(model) == 0.0
        assert acc(model) == 0.0
    assert pos(model) == 0.0


def test_power_above_pmax_is_capped() -> None:
    """Check a command above P_max gives the same force as P_max."""
    capped = fresh()
    over = fresh()
    launch(capped, 19.0)
    launch(over, 19.0)
    capped.step(DT_S, inp(CFG.p_max_w))
    over.step(DT_S, inp(10 * CFG.p_max_w))
    assert acc(over) == pytest.approx(acc(capped), rel=1e-12)


@pytest.mark.parametrize(("power_w", "v_target"), [
    (100_000.0, 5.0), (100_000.0, 10.0), (240_000.0, 15.0),
    (480_000.0, 19.0),
])
def test_constant_power_regime_accel(power_w: float, v_target: float) -> None:
    """Check F = min(P/v, F_max), taken at the previous velocity."""
    model = fresh()
    launch(model, v_target, power_w=power_w)
    v0 = vel(model)
    model.step(DT_S, inp(power_w))
    m = mass_of(0)
    expected = (min(power_w / v0, CFG.f_max_n) - roll_n(m)) / m
    assert acc(model) == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize("n", [0, REF_LOAD, FULL])
def test_traction_never_exceeds_force_or_power_limit(n: int) -> None:
    """Check implied traction stays within F_max and P_max every tick."""
    model = fresh(n)
    m = mass_of(n)
    for _ in range(600):
        v_prev = vel(model)
        model.step(DT_S, inp(CFG.p_max_w))
        f_trac = m * acc(model) + roll_n(m)
        assert f_trac <= CFG.f_max_n * (1 + 1e-12)
        assert f_trac * v_prev <= CFG.p_max_w * (1 + 1e-9)


def test_engine_failure_zeroes_traction_while_moving() -> None:
    """Check an engine-failed train only coasts under full power."""
    model = fresh()
    launch(model, 10.0)
    model.set_failures(FailureState(engine=True))
    model.step(DT_S, inp(CFG.p_max_w))
    assert acc(model) == pytest.approx(-CFG.c_rr * G, rel=1e-12)


def test_engine_failure_cleared_restores_traction() -> None:
    """Check clearing an engine failure lets power move the train."""
    model = fresh()
    model.set_failures(FailureState(engine=True))
    for _ in range(10):
        model.step(DT_S, inp(CFG.p_max_w))
    assert vel(model) == 0.0
    model.set_failures(FailureState())
    model.step(DT_S, inp(CFG.p_max_w))
    assert vel(model) > 0.0


@pytest.mark.parametrize("n", [0, 50, 100, 150, FULL])
def test_newton_second_law_force_limited_regime(n: int) -> None:
    """Check F = m a while moving below base speed, at every load."""
    model = fresh(n)
    launch(model, 5.0)
    model.step(DT_S, inp(CFG.p_max_w))
    m = mass_of(n)
    assert m * acc(model) == pytest.approx(
        CFG.f_max_n - roll_n(m), rel=1e-12)


# --------------------------------------------------------------------------- #
# D. Grade
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("grade_pct", [-6.0, -3.0, -1.0, 0.0, 1.0, 3.0, 6.0])
def test_grade_force_on_moving_train(grade_pct: float) -> None:
    """Check coasting a = -g sin - c_rr g cos, independent of mass."""
    model = fresh(100)
    launch(model, 10.0)
    model.step(DT_S, inp(0.0, grade_deg=pct(grade_pct)))
    th = math.radians(pct(grade_pct))
    expected = -G * math.sin(th) - CFG.c_rr * G * math.cos(th)
    assert acc(model) == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize("n", [0, 111, FULL])
def test_gravity_acceleration_is_mass_independent(n: int) -> None:
    """Check an unbraked start downhill accelerates the same at any load."""
    model = fresh(n)
    th = math.radians(pct(-4.0))
    model.step(DT_S, inp(0.0, grade_deg=pct(-4.0)))
    expected = -G * math.sin(th) - CFG.c_rr * G * math.cos(th)
    assert acc(model) == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize("grade_pct", [-0.1, 0.1])
def test_rolling_resistance_holds_on_shallow_grade(grade_pct: float) -> None:
    """Check static rolling resistance holds where |sin| < c_rr cos."""
    model = fresh()
    for _ in range(100):
        model.step(DT_S, inp(0.0, grade_deg=pct(grade_pct)))
        assert vel(model) == 0.0


@pytest.mark.parametrize("grade_pct", [-6.0, -2.0, -0.5, 0.5, 2.0, 6.0])
def test_unbraked_train_rolls_downhill(grade_pct: float) -> None:
    """Check an unbraked train rolls toward the low end of the grade."""
    model = fresh()
    for _ in range(50):
        model.step(DT_S, inp(0.0, grade_deg=pct(grade_pct)))
    assert vel(model) != 0.0
    assert math.copysign(1.0, vel(model)) == -math.copysign(1.0, grade_pct)


def test_rollback_mirrors_forward_roll() -> None:
    """Check rolling back up a grade mirrors rolling forward down it."""
    up = fresh()
    down = fresh()
    for _ in range(100):
        up.step(DT_S, inp(0.0, grade_deg=pct(3.0)))
        down.step(DT_S, inp(0.0, grade_deg=pct(-3.0)))
    assert vel(up) == pytest.approx(-vel(down), rel=1e-12)
    assert pos(up) == pytest.approx(-pos(down), rel=1e-12)


@pytest.mark.parametrize("n", [0, 74, REF_LOAD, FULL])
def test_full_power_start_threshold(n: int) -> None:
    """Check the start grade limit F_max = m g (sin + c_rr cos)."""
    m = mass_of(n)
    crit = solve_grade(lambda d: CFG.f_max_n - m * G * (
        math.sin(math.radians(d)) + CFG.c_rr * math.cos(math.radians(d))))
    below = fresh(n)
    above = fresh(n)
    for _ in range(100):
        below.step(DT_S, inp(CFG.p_max_w, grade_deg=crit * 0.98))
        above.step(DT_S, inp(CFG.p_max_w, grade_deg=crit * 1.02))
        assert vel(above) == 0.0
    assert vel(below) > 0.0


@pytest.mark.parametrize("grade_deg", [30.0, -30.0])
def test_rolling_resistance_uses_cosine_of_grade(grade_deg: float) -> None:
    """Check rolling resistance scales with the normal force."""
    model = fresh()
    launch(model, 10.0)
    model.step(DT_S, inp(0.0, grade_deg=grade_deg))
    th = math.radians(grade_deg)
    expected = -G * math.sin(th) - CFG.c_rr * G * math.cos(th)
    assert acc(model) == pytest.approx(expected, rel=1e-12)


# --------------------------------------------------------------------------- #
# E. Brakes
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("n", [0, REF_LOAD, FULL])
@pytest.mark.parametrize("kind", ["service", "emergency", "passenger"])
def test_brake_deceleration_while_moving(kind: str, n: int) -> None:
    """Check each brake decelerates by (F_brake + R) / m."""
    model = fresh(n)
    launch(model, 10.0)
    if kind == "passenger":
        model.pull_passenger_emergency_brake()
        model.step(DT_S, inp(0.0))
        force = CFG.f_emergency_n
    else:
        model.step(DT_S, brake_inputs(kind))
        force = BRAKE_FORCE[kind]
    m = mass_of(n)
    assert acc(model) == pytest.approx(-(force + roll_n(m)) / m, rel=1e-12)


def test_emergency_supersedes_service_not_additive() -> None:
    """Check service plus emergency brakes no harder than emergency."""
    both = fresh()
    only = fresh()
    launch(both, 10.0)
    launch(only, 10.0)
    both.step(DT_S, inp(0.0, service=True, emergency=True))
    only.step(DT_S, inp(0.0, emergency=True))
    assert acc(both) == acc(only)


def test_passenger_brake_latches_and_holds() -> None:
    """Check a passenger pull stops the train and holds it under power."""
    model = fresh()
    launch(model, 10.0)
    model.pull_passenger_emergency_brake()
    run_to_stop(model, lambda: inp(0.0))
    for _ in range(50):
        out = model.step(DT_S, inp(CFG.p_max_w))
        assert vel(model) == 0.0
        assert out.controller.emergency_brake_active is True
    assert model.snapshot().passenger_ebrake_pulled is True


@pytest.mark.parametrize("kind", ["service", "emergency", "passenger"])
def test_brake_failure_disables_every_brake(kind: str) -> None:
    """Check a brake failure leaves only rolling resistance."""
    model = fresh()
    launch(model, 10.0)
    model.set_failures(FailureState(brake=True))
    if kind == "passenger":
        model.pull_passenger_emergency_brake()
        model.step(DT_S, inp(0.0))
    else:
        model.step(DT_S, brake_inputs(kind))
    assert acc(model) == pytest.approx(-CFG.c_rr * G, rel=1e-12)


@pytest.mark.parametrize("v0", [5.0, 12.0, CFG.v_max_mps])
@pytest.mark.parametrize("n", [0, FULL])
@pytest.mark.parametrize("kind", ["service", "emergency"])
def test_stopping_distance_matches_srs_formula(
        kind: str, n: int, v0: float) -> None:
    """Check SRS Appendix B d = v^2 / (2a) to within one tick of travel."""
    model = fresh(n)
    launch(model, v0)
    v_start = vel(model)
    x0 = pos(model)
    run_to_stop(model, lambda: brake_inputs(kind))
    m = mass_of(n)
    a_b = (BRAKE_FORCE[kind] + roll_n(m)) / m
    expected = v_start ** 2 / (2 * a_b)
    assert pos(model) - x0 == pytest.approx(
        expected, abs=v_start * DT_S + 0.1)


@pytest.mark.parametrize("n", [0, FULL])
@pytest.mark.parametrize("kind", ["service", "emergency"])
def test_brake_holding_grade_threshold(kind: str, n: int) -> None:
    """Check a brake holds while m g sin <= F_brake + c_rr m g cos."""
    m = mass_of(n)
    force = BRAKE_FORCE[kind]
    crit = solve_grade(lambda d: force + roll_n(m, d)
                       - m * G * math.sin(math.radians(d)))
    held = fresh(n)
    slips = fresh(n)
    for _ in range(100):
        held.step(DT_S, brake_inputs(kind, grade_deg=crit * 0.95))
        slips.step(DT_S, brake_inputs(kind, grade_deg=crit * 1.05))
        assert vel(held) == 0.0
    assert vel(slips) < 0.0


@pytest.mark.parametrize("kind", ["service", "emergency"])
def test_brakes_arrest_a_rollback_without_reversing(kind: str) -> None:
    """Check brakes stop a rollback at zero, never driving forward."""
    model = fresh()
    for _ in range(30):
        model.step(DT_S, inp(0.0, grade_deg=pct(6.0)))
    assert vel(model) < 0.0
    for _ in range(200):
        model.step(DT_S, brake_inputs(kind, grade_deg=pct(6.0)))
        assert vel(model) <= 0.0
    assert vel(model) == 0.0


def test_service_brake_cannot_hold_full_train_on_steep_downgrade() -> None:
    """Check gravity beats the service brake on a 15 percent downgrade."""
    model = fresh(FULL)
    launch(model, 5.0)
    v_start = vel(model)
    for _ in range(20):
        model.step(DT_S, brake_inputs("service", grade_deg=pct(-15.0)))
    assert vel(model) > v_start


def test_emergency_brake_stops_full_train_on_downgrade() -> None:
    """Check the emergency brake stops a full train on 10 percent down."""
    model = fresh(FULL)
    launch(model, 10.0)
    downgrade = pct(-10.0)
    run_to_stop(model, lambda: brake_inputs("emergency", grade_deg=downgrade))
    for _ in range(50):
        model.step(DT_S, brake_inputs("emergency", grade_deg=downgrade))
        assert vel(model) == 0.0


@pytest.mark.parametrize("kind", ["service", "emergency"])
def test_traction_adds_to_braking_when_both_commanded(kind: str) -> None:
    """Check, as found, that traction is not cut while braking."""
    model = fresh()
    launch(model, 10.0)
    v0 = vel(model)
    model.step(DT_S, brake_inputs(kind, power_w=CFG.p_max_w))
    m = mass_of(0)
    f_trac = min(CFG.p_max_w / v0, CFG.f_max_n)
    expected = (f_trac - BRAKE_FORCE[kind] - roll_n(m)) / m
    assert acc(model) == pytest.approx(expected, rel=1e-12)


# --------------------------------------------------------------------------- #
# F. Integration and numerics
# --------------------------------------------------------------------------- #

def _scenario_launch(model: Recorder) -> None:
    """Accelerate at full power through both traction regimes."""
    for _ in range(250):
        model.step(DT_S, inp(CFG.p_max_w))


def _scenario_coast(model: Recorder) -> None:
    """Launch, then coast on rolling resistance alone."""
    launch(model, 12.0)
    for _ in range(200):
        model.step(DT_S, inp(0.0))


def _scenario_brake(model: Recorder) -> None:
    """Launch, then service brake to a stop."""
    launch(model, 15.0)
    for _ in range(40):
        model.step(DT_S, inp(0.0, service=True))


def _scenario_grade(model: Recorder) -> None:
    """Roll unbraked down a 2 percent grade."""
    for _ in range(200):
        model.step(DT_S, inp(0.0, grade_deg=pct(-2.0)))


@pytest.mark.parametrize("scenario", [
    _scenario_launch, _scenario_coast, _scenario_brake, _scenario_grade,
], ids=["launch", "coast", "brake", "grade"])
def test_trapezoidal_update_identity(
        scenario: Callable[[Recorder], None]) -> None:
    """Check dv = dt/2 (a_n + a_n-1) and dx = dt/2 (v_n + v_n-1)."""
    recorder = Recorder(fresh())
    scenario(recorder)
    history = recorder.history
    checked = 0
    for (v0, a0, x0), (v1, a1, x1) in zip(history, history[1:]):
        if v1 == 0.0 and a1 == 0.0:
            continue  # at rest, or the stop-clamp tick
        assert v1 - v0 == pytest.approx(DT_S / 2 * (a1 + a0), abs=1e-12)
        assert x1 - x0 == pytest.approx(DT_S / 2 * (v1 + v0), abs=1e-9)
        checked += 1
    assert checked > 30


@pytest.mark.parametrize("n_ticks", [1, 10, 50])
def test_constant_acceleration_closed_form(n_ticks: int) -> None:
    """Check v_N = (N - 1/2) a dt in the force-limited launch."""
    model = fresh()
    for _ in range(n_ticks):
        model.step(DT_S, inp(CFG.p_max_w))
    m = mass_of(0)
    a = (CFG.f_max_n - roll_n(m)) / m
    v_exact = [0.0] + [(k - 0.5) * a * DT_S for k in range(1, n_ticks + 1)]
    x_exact = sum(DT_S / 2 * (v_exact[k] + v_exact[k - 1])
                  for k in range(1, n_ticks + 1))
    assert vel(model) == pytest.approx(v_exact[-1], rel=1e-12)
    assert pos(model) == pytest.approx(x_exact, rel=1e-12)


def _rk4_reference(
    power_w: float, t_end: float, h: float = 1e-3
) -> tuple[float, float]:
    """Integrate m dv/dt = F_trac(v) - R with RK4, independently."""
    m = mass_of(0)
    r = roll_n(m)

    def a_of(v: float) -> float:
        f = CFG.f_max_n if v <= 0.0 else min(power_w / v, CFG.f_max_n)
        return (f - r) / m

    x = v = 0.0
    for _ in range(int(round(t_end / h))):
        k1v, k1x = a_of(v), v
        k2v, k2x = a_of(v + h / 2 * k1v), v + h / 2 * k1v
        k3v, k3x = a_of(v + h / 2 * k2v), v + h / 2 * k2v
        k4v, k4x = a_of(v + h * k3v), v + h * k3v
        v += h / 6 * (k1v + 2 * k2v + 2 * k3v + k4v)
        x += h / 6 * (k1x + 2 * k2x + 2 * k3x + k4x)
    return v, x


@pytest.mark.parametrize("power_w", [50_000.0, 100_000.0, 480_000.0])
def test_accuracy_against_rk4_reference(power_w: float) -> None:
    """Check a 60 s launch agrees with RK4 to 0.2 percent."""
    v_ref, x_ref = _rk4_reference(power_w, 60.0)
    model = fresh()
    for _ in range(600):
        model.step(DT_S, inp(power_w))
    assert vel(model) == pytest.approx(v_ref, rel=2e-3)
    assert pos(model) == pytest.approx(x_ref, rel=2e-3)


def test_integration_error_shrinks_with_dt() -> None:
    """Check the error against RK4 falls as dt falls."""
    v_ref, _ = _rk4_reference(100_000.0, 60.0)
    errors = []
    for dt in (0.2, 0.1, 0.05):
        model = fresh()
        for _ in range(int(round(60.0 / dt))):
            model.step(dt, inp(100_000.0))
        errors.append(abs(vel(model) - v_ref))
    assert errors[0] > errors[1] > errors[2]


@pytest.mark.parametrize("dt", [0.0, -0.1, -1e-12, -math.inf])
def test_non_positive_dt_rejected(dt: float) -> None:
    """Check a time step that is not positive raises."""
    model = fresh()
    with pytest.raises(InvalidTimeStepError):
        model.step(dt, inp(CFG.p_max_w))


def test_rejected_dt_leaves_state_untouched() -> None:
    """Check a rejected step changes nothing, boarding included."""
    model = fresh(20)
    launch(model, 5.0)
    before = model.snapshot()
    with pytest.raises(InvalidTimeStepError):
        model.step(-1.0, inp(CFG.p_max_w, boarded=50))
    assert model.snapshot() == before


@pytest.mark.xfail(strict=True, reason="DEFECT: NaN dt passes `dt <= 0` and "
                   "poisons velocity and position with NaN")
def test_nan_dt_rejected() -> None:
    """Check a NaN time step raises."""
    model = fresh()
    with pytest.raises(InvalidTimeStepError):
        model.step(math.nan, inp(CFG.p_max_w))


@pytest.mark.xfail(strict=True, reason="DEFECT: infinite dt is accepted")
def test_infinite_dt_rejected() -> None:
    """Check an infinite time step raises."""
    model = fresh()
    with pytest.raises(InvalidTimeStepError):
        model.step(math.inf, inp(CFG.p_max_w))


def test_halving_dt_changes_trajectory_little() -> None:
    """Check dt = 0.1 and dt = 0.05 agree to 1 percent over 30 s."""
    coarse = fresh()
    fine = fresh()
    for _ in range(300):
        coarse.step(0.1, inp(CFG.p_max_w))
    for _ in range(600):
        fine.step(0.05, inp(CFG.p_max_w))
    assert vel(coarse) == pytest.approx(vel(fine), rel=1e-2)
    assert pos(coarse) == pytest.approx(pos(fine), rel=1e-2)


# --------------------------------------------------------------------------- #
# G. Energy and momentum
# --------------------------------------------------------------------------- #

def test_work_energy_coasting_on_flat() -> None:
    """Check lost kinetic energy equals rolling resistance work."""
    model = fresh(60)
    launch(model, 10.0)
    model.step(DT_S, inp(0.0))  # flush a_prev from the launch
    v1, x1 = vel(model), pos(model)
    for _ in range(200):
        model.step(DT_S, inp(0.0))
    m = mass_of(60)
    d_ke = 0.5 * m * (vel(model) ** 2 - v1 ** 2)
    assert d_ke == pytest.approx(-roll_n(m) * (pos(model) - x1), rel=1e-9)


@pytest.mark.parametrize("grade_pct", [1.0, 3.0, 6.0])
def test_work_energy_coasting_uphill(grade_pct: float) -> None:
    """Check lost kinetic energy equals gravity plus rolling work."""
    g_deg = pct(grade_pct)
    model = fresh(60)
    launch(model, 10.0)
    model.step(DT_S, inp(0.0, grade_deg=g_deg))
    v1, x1 = vel(model), pos(model)
    for _ in range(40):
        model.step(DT_S, inp(0.0, grade_deg=g_deg))
    m = mass_of(60)
    d_ke = 0.5 * m * (vel(model) ** 2 - v1 ** 2)
    f_resist = m * G * math.sin(math.radians(g_deg)) + roll_n(m, g_deg)
    assert d_ke == pytest.approx(-f_resist * (pos(model) - x1), rel=1e-9)


def test_impulse_momentum_force_limited_launch() -> None:
    """Check the momentum gained equals the net impulse."""
    model = fresh(30)
    launch(model, 3.0)
    model.step(DT_S, inp(CFG.p_max_w))
    v1 = vel(model)
    for _ in range(50):
        model.step(DT_S, inp(CFG.p_max_w))
    m = mass_of(30)
    assert m * (vel(model) - v1) == pytest.approx(
        (CFG.f_max_n - roll_n(m)) * 50 * DT_S, rel=1e-9)


@pytest.mark.parametrize("n", [0, FULL])
def test_emergency_stop_dissipates_kinetic_energy(n: int) -> None:
    """Check the braking work over the stop equals the kinetic energy."""
    model = fresh(n)
    launch(model, CFG.v_max_mps)
    model.step(DT_S, inp(0.0, emergency=True))  # flush a_prev
    v1, x1 = vel(model), pos(model)
    run_to_stop(model, lambda: inp(0.0, emergency=True))
    m = mass_of(n)
    work_d = 0.5 * m * v1 ** 2 / (CFG.f_emergency_n + roll_n(m))
    assert pos(model) - x1 == pytest.approx(work_d, abs=0.05)


def test_power_limited_regime_energy_balance() -> None:
    """Check energy in at P_max equals kinetic gain plus rolling losses."""
    model = fresh()
    launch(model, 19.0)
    model.step(DT_S, inp(CFG.p_max_w))
    v1, x1 = vel(model), pos(model)
    ticks = 100
    for _ in range(ticks):
        model.step(DT_S, inp(CFG.p_max_w))
    m = mass_of(0)
    d_ke = 0.5 * m * (vel(model) ** 2 - v1 ** 2)
    work_in = CFG.p_max_w * ticks * DT_S
    assert d_ke + roll_n(m) * (pos(model) - x1) == pytest.approx(
        work_in, rel=5e-3)


# --------------------------------------------------------------------------- #
# H. Stopping behaviour
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("grade_pct", [-3.0, 0.0, 3.0])
@pytest.mark.parametrize("kind", ["service", "emergency"])
def test_braking_never_reverses_on_grades(kind: str, grade_pct: float) -> None:
    """Check braking on a grade stops the train and holds it at zero."""
    model = fresh()
    launch(model, 8.0)
    g_deg = pct(grade_pct)
    run_to_stop(model, lambda: brake_inputs(kind, grade_deg=g_deg))
    for _ in range(100):
        model.step(DT_S, brake_inputs(kind, grade_deg=g_deg))
        assert vel(model) == 0.0


def test_gravity_reverses_unbraked_train_after_it_stops() -> None:
    """Check an unbraked train coasting uphill stops, then rolls back."""
    model = fresh()
    launch(model, 3.0)
    seen_zero = False
    for _ in range(200):
        model.step(DT_S, inp(0.0, grade_deg=pct(6.0)))
        if vel(model) == 0.0:
            seen_zero = True
        if seen_zero and vel(model) < 0.0:
            return
    pytest.fail("train never rolled back after stopping on 6 percent")


@pytest.mark.xfail(strict=True, reason="DEFECT: on the stop tick dx is taken "
                   "from the overshot (negative) velocity before it is "
                   "clamped, so the offset steps backward up to ~1.6 cm")
def test_stop_tick_never_moves_train_backward() -> None:
    """Check the offset never decreases while braking forward."""
    for launch_ticks in range(1, 61):
        model = fresh()
        for _ in range(launch_ticks):
            model.step(DT_S, inp(CFG.p_max_w))
        last = pos(model)
        for _ in range(2000):
            model.step(DT_S, inp(0.0, emergency=True))
            assert pos(model) >= last, f"backward, launch={launch_ticks}"
            last = pos(model)
            if vel(model) == 0.0:
                break


# --------------------------------------------------------------------------- #
# I. Physical limits not enforced
# --------------------------------------------------------------------------- #

@pytest.mark.xfail(strict=True, reason="DEFECT: power is capped above but not "
                   "below; a negative command yields negative P/v traction, "
                   "an uncapped brake contrary to 'motors drive forward only'")
def test_negative_power_command_gives_no_traction() -> None:
    """Check a negative power command produces no force."""
    model = fresh()
    launch(model, 10.0)
    model.step(DT_S, inp(-CFG.p_max_w))
    assert acc(model) == pytest.approx(-CFG.c_rr * G, rel=1e-9)


@pytest.mark.xfail(strict=True, reason="PHYSICS: traction is zero for v < 0, "
                   "so full power cannot arrest a rollback even where it "
                   "could hold the train from rest")
def test_traction_can_arrest_a_rollback() -> None:
    """Check full power slows a rollback the motors could prevent."""
    model = fresh()
    for _ in range(20):
        model.step(DT_S, inp(0.0, grade_deg=pct(3.0)))
    v_back = vel(model)
    assert v_back < 0.0
    for _ in range(10):
        model.step(DT_S, inp(CFG.p_max_w, grade_deg=pct(3.0)))
    assert vel(model) > v_back


@pytest.mark.xfail(strict=True, reason="PHYSICS: no speed governing (OPEN(1)) "
                   "and no aerodynamic drag; sustained full power runs far "
                   "past v_max (about 78 m/s after 300 s)")
def test_speed_bounded_under_sustained_full_power() -> None:
    """Check 300 s of full power stays near the maximum speed."""
    model = fresh()
    for _ in range(3000):
        model.step(DT_S, inp(CFG.p_max_w))
    assert vel(model) <= 1.1 * CFG.v_max_mps


# --------------------------------------------------------------------------- #
# J. Position and block changes
# --------------------------------------------------------------------------- #

def test_offset_is_trapezoidal_distance() -> None:
    """Check the offset accumulates trapezoidal distance."""
    model = fresh()
    total = 0.0
    v_prev = 0.0
    for _ in range(300):
        model.step(DT_S, inp(CFG.p_max_w))
        total += DT_S / 2 * (vel(model) + v_prev)
        v_prev = vel(model)
    assert pos(model) == pytest.approx(total, rel=1e-12)


@pytest.mark.parametrize("flip_ticks", [
    (40,), (40, 80), (20, 40, 60, 80, 100)])
def test_polarity_flip_resets_offset(flip_ticks: tuple[int, ...]) -> None:
    """Check a polarity flip flags a block change and restarts the offset."""
    model = fresh()
    polarity = True
    for tick in range(120):
        if tick in flip_ticks:
            polarity = not polarity
        v_prev = vel(model)
        x_prev = pos(model)
        out = model.step(DT_S, inp(CFG.p_max_w, polarity=polarity))
        assert out.track.block_changed is (tick in flip_ticks)
        dx = DT_S / 2 * (vel(model) + v_prev)
        if tick in flip_ticks:
            assert out.track.offset_m == pytest.approx(dx, rel=1e-12)
        else:
            assert out.track.offset_m == pytest.approx(
                x_prev + dx, rel=1e-12)


@pytest.mark.parametrize("polarity", [True, False])
def test_first_tick_is_never_a_block_change(polarity: bool) -> None:
    """Check the first tick has no previous polarity to differ from."""
    out = TrainModel(CFG).step(DT_S, inp(polarity=polarity))
    assert out.track.block_changed is False


def test_steady_polarity_never_changes_block() -> None:
    """Check an unchanging polarity never flags a block change."""
    model = fresh()
    for _ in range(100):
        out = model.step(DT_S, inp(CFG.p_max_w))
        assert out.track.block_changed is False


def test_rollback_drives_offset_negative() -> None:
    """Check a rollback reports negative offset and speed."""
    model = fresh()
    for _ in range(50):
        out = model.step(DT_S, inp(0.0, grade_deg=pct(3.0)))
    assert out.track.offset_m < 0.0
    assert out.track.actual_speed_mps < 0.0
    assert out.controller.actual_speed_mps < 0.0


def test_track_and_controller_speeds_agree() -> None:
    """Check both outputs report the snapshot velocity every tick."""
    model = fresh()
    for tick in range(300):
        out = model.step(DT_S, inp(CFG.p_max_w if tick < 150 else 0.0,
                                   service=tick >= 150))
        assert out.track.actual_speed_mps == out.controller.actual_speed_mps
        assert out.controller.actual_speed_mps == vel(model)


def test_block_id_passes_through() -> None:
    """Check the reported block ID is the one received."""
    model = fresh()
    for block in ("A1", "A2", "B7", "YARD"):
        assert model.step(DT_S, inp(block_id=block)).track.block_id == block


# --------------------------------------------------------------------------- #
# K. Passengers
# --------------------------------------------------------------------------- #

def _onboard(model: TrainModel) -> int:
    """Return the passenger count."""
    return model.snapshot().n_passengers


def test_disembark_only_on_rising_door_edge() -> None:
    """Check doors held open do not draw again."""
    model = fresh(FULL)
    model.step(DT_S, inp(door_left=True))
    after_edge = _onboard(model)
    for _ in range(20):
        model.step(DT_S, inp(door_left=True))
        assert _onboard(model) == after_edge


def test_no_disembark_when_doors_open_while_moving() -> None:
    """Check nobody leaves through doors opened while moving."""
    model = fresh(FULL)
    launch(model, 2.0)
    model.step(DT_S, inp(door_left=True, door_right=True))
    assert _onboard(model) == FULL


@pytest.mark.parametrize("side", ["left", "right"])
def test_either_door_edge_triggers_disembark(side: str) -> None:
    """Check either side's door opening at rest draws a disembark."""
    changed = False
    for seed in range(10):
        model = fresh(FULL, TrainConfig(seed=seed))
        model.step(DT_S, inp(door_left=side == "left",
                             door_right=side == "right"))
        changed = changed or _onboard(model) < FULL
    assert changed


def test_disembark_draw_is_uniform_over_onboard() -> None:
    """Check the disembark draw spans 0..onboard with mean onboard/2."""
    draws = []
    for seed in range(300):
        model = fresh(FULL, TrainConfig(seed=seed))
        model.step(DT_S, inp(door_left=True))
        draws.append(FULL - _onboard(model))
    assert all(0 <= d <= FULL for d in draws)
    assert sum(draws) / len(draws) == pytest.approx(FULL / 2, abs=15)
    assert min(draws) < 30 and max(draws) > FULL - 30


@pytest.mark.parametrize("onboard", [0, 1, 5])
def test_disembark_bounded_by_onboard(onboard: int) -> None:
    """Check no more passengers leave than are aboard."""
    for seed in range(20):
        model = fresh(onboard, TrainConfig(seed=seed))
        model.step(DT_S, inp(door_left=True))
        assert 0 <= _onboard(model) <= onboard


def test_capacity_output_is_after_the_draw() -> None:
    """Check reported capacity reflects the disembark of the same tick."""
    model = fresh(FULL, TrainConfig(seed=3))
    out = model.step(DT_S, inp(door_left=True))
    assert out.track.passenger_capacity == FULL - _onboard(model)


def test_boarding_after_disembark_respects_capacity() -> None:
    """Check boarding fills the room the disembark left, no more."""
    model = fresh(FULL)
    out = model.step(DT_S, inp(door_left=True, boarded=FULL))
    assert _onboard(model) == FULL
    assert out.track.passenger_capacity == 0


def test_boarding_accepted_while_moving_with_doors_closed() -> None:
    """Check, as found, that boarding is not gated on doors or speed."""
    model = fresh()
    launch(model, 5.0)
    model.step(DT_S, inp(CFG.p_max_w, boarded=40))
    assert _onboard(model) == 40


# --------------------------------------------------------------------------- #
# L. Cabin temperature
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("setpoint", [10.0, 16.0, 20.0, 25.0, 30.0])
def test_cabin_temperature_first_order_lag(setpoint: float) -> None:
    """Check the gap shrinks by e after one 300 s time constant."""
    model = fresh()
    t0 = model.snapshot().outputs.controller.cabin_temp_c
    for _ in range(3000):
        out = model.step(DT_S, inp(setpoint_c=setpoint))
    expected = setpoint + (t0 - setpoint) * math.exp(-1.0)
    assert out.controller.cabin_temp_c == pytest.approx(expected, abs=1e-9)


def test_cabin_temperature_is_dt_invariant() -> None:
    """Check the exact discretisation gives the same result at any dt."""
    fine = fresh()
    coarse = fresh()
    for _ in range(3000):
        fine.step(0.1, inp(setpoint_c=28.0))
    for _ in range(300):
        coarse.step(1.0, inp(setpoint_c=28.0))
    t_fine = fine.snapshot().outputs.controller.cabin_temp_c
    t_coarse = coarse.snapshot().outputs.controller.cabin_temp_c
    assert t_fine == pytest.approx(t_coarse, abs=1e-9)


@pytest.mark.parametrize("setpoint", [10.0, 30.0])
def test_cabin_temperature_monotone_without_overshoot(
        setpoint: float) -> None:
    """Check the cabin approaches the setpoint without overshooting."""
    model = fresh()
    last = model.snapshot().outputs.controller.cabin_temp_c
    for _ in range(20_000):
        out = model.step(DT_S, inp(setpoint_c=setpoint))
        temp = out.controller.cabin_temp_c
        if setpoint > last:
            assert last <= temp <= setpoint
        else:
            assert setpoint <= temp <= last
        last = temp


def test_initial_cabin_temperature() -> None:
    """Check the cabin starts at 20 C."""
    model = TrainModel(CFG)
    assert model.snapshot().outputs.controller.cabin_temp_c == 20.0


def test_cabin_temperature_single_tick_exact() -> None:
    """Check one tick applies exp(-dt / 300) to the gap."""
    out = TrainModel(CFG).step(DT_S, inp(setpoint_c=30.0))
    expected = 30.0 + (20.0 - 30.0) * math.exp(-DT_S / 300.0)
    assert out.controller.cabin_temp_c == pytest.approx(expected, abs=1e-12)


# --------------------------------------------------------------------------- #
# M. Outputs and failures
# --------------------------------------------------------------------------- #

def test_track_signal_passes_through() -> None:
    """Check commanded speed and authority reach the controller."""
    out = fresh().step(DT_S, inp(cmd_speed_mps=13.5, authority="C12"))
    assert out.controller.commanded_speed_mps == 13.5
    assert out.controller.authority_block_id == "C12"


def test_signal_pickup_failure_blanks_only_the_track_signal() -> None:
    """Check pickup failure blanks the signal but not the track info."""
    model = fresh()
    model.set_failures(FailureState(signal_pickup=True))
    out = model.step(DT_S, inp(cmd_speed_mps=13.5, authority="C12",
                               speed_limit_mps=12.0, block_id="C3"))
    assert out.controller.commanded_speed_mps == 0.0
    assert out.controller.authority_block_id is None
    assert out.controller.speed_limit_mps == 12.0
    assert out.track.block_id == "C3"


@pytest.mark.parametrize("engine", [False, True])
@pytest.mark.parametrize("pickup", [False, True])
@pytest.mark.parametrize("brake", [False, True])
def test_failure_status_reported(engine: bool, pickup: bool,
                                 brake: bool) -> None:
    """Check every failure combination is reported as set."""
    model = fresh()
    state = FailureState(engine=engine, signal_pickup=pickup, brake=brake)
    model.set_failures(state)
    assert model.step(DT_S, inp()).controller.failures == state


@pytest.mark.parametrize(("left", "right"), [
    (False, False), (True, False), (False, True), (True, True)])
def test_door_state_reported(left: bool, right: bool) -> None:
    """Check each door's state follows its command."""
    out = fresh().step(DT_S, inp(door_left=left, door_right=right))
    assert out.controller.door_left_open is left
    assert out.controller.door_right_open is right


@pytest.mark.parametrize(("interior", "exterior"), [
    (False, False), (True, False), (False, True), (True, True)])
def test_light_state_reported(interior: bool, exterior: bool) -> None:
    """Check each light's state follows its command."""
    out = fresh().step(DT_S, inp(interior=interior, exterior=exterior))
    assert out.controller.interior_lights_on is interior
    assert out.controller.exterior_lights_on is exterior


def test_beacon_passes_through_only_on_its_tick() -> None:
    """Check a beacon is reported on its tick and None after."""
    model = fresh()
    beacon = Beacon("Dormont", "R", underground=True)
    assert model.step(DT_S, inp(beacon=beacon)).controller.beacon == beacon
    assert model.step(DT_S, inp()).controller.beacon is None


def test_failure_takes_effect_on_the_next_step() -> None:
    """Check a failure set between ticks applies on the next step."""
    model = fresh()
    model.step(DT_S, inp())
    model.set_failures(FailureState(engine=True))
    assert model.snapshot().outputs.controller.failures == FailureState()
    out = model.step(DT_S, inp(CFG.p_max_w))
    assert out.controller.failures == FailureState(engine=True)
    assert vel(model) == 0.0
