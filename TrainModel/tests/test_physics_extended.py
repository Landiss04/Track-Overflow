"""Extended physics verification for ``train_model.model.TrainModel``.

Every expectation here is derived independently from first principles
(Newton's second law, the work-energy theorem, impulse-momentum, the
SRS Appendix B braking formula, and a closed-form launch solution) and
from the ``TrainConfig`` primitives. The implementation is never
consulted for an expected value.

The integrator holds each tick's commands for the whole tick: constant
forces integrate exactly, power-limited traction is solved at the
midpoint velocity, and a stop is integrated to the exact stopping time.
Reported acceleration is the instantaneous value at the end of a tick.
"""

from __future__ import annotations

import dataclasses
import math
import random
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
from train_model.model import (
    InvalidInputError,
    InvalidTimeStepError,
    TrainModel,
)

DT_S = 0.1
CFG = TrainConfig()
G = CFG.g_mps2
FULL = CFG.capacity
REF_LOAD = round(CFG.capacity * CFG.ref_load_fraction)
STATION = "GLENBURY"


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
    station: str | None = None,
    speed_limit_mps: float = 19.0,
    cmd_speed_mps: float = 10.0,
    authority: int = 9,
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
                station_name=station,
            ),
            track_signal=TrackSignal(
                commanded_speed_mps=cmd_speed_mps,
                authority_blocks=authority,
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
    """Return a model at rest, doors closed, with passengers boarded."""
    model = TrainModel(cfg)
    if n_passengers:
        model.step(DT_S, inp(boarded=n_passengers, door_left=True,
                             station=STATION))
        model.step(DT_S, inp())
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


def onboard(model: TrainModel) -> int:
    """Return the passenger count."""
    return model.snapshot().n_passengers


def doors(out: TrainModelOutputs) -> tuple[bool, bool]:
    """Return the reported (left, right) door state."""
    return out.controller.door_left_open, out.controller.door_right_open


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
) -> TrainModelOutputs:
    """Step until the velocity is exactly zero; return the last outputs."""
    for _ in range(20_000):
        out = model.step(DT_S, make())
        if vel(model) == 0.0:
            return out
    pytest.fail("never stopped")


def next_stop(model: TrainModel) -> None:
    """Depart and stop again: a new stop, which draws a disembark."""
    model.step(DT_S, inp(CFG.p_max_w))
    run_to_stop(model, lambda: inp(0.0, service=True))


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


def analytic_launch(power_w: float, t_end: float) -> tuple[float, float]:
    """Return exact (v, x) after ``t_end`` s of a flat launch from rest.

    Force-limited at F_max up to v_b = P / F_max, then m dv/dt = P/v - R,
    integrated in closed form and inverted for v by bisection.
    """
    m = mass_of(0)
    r = roll_n(m)
    a_f = (CFG.f_max_n - r) / m
    v_b = power_w / CFG.f_max_n
    t_b = v_b / a_f
    if t_end <= t_b:
        return a_f * t_end, a_f * t_end ** 2 / 2.0

    def t_int(v: float) -> float:
        return -v / r - power_w / r ** 2 * math.log(power_w - r * v)

    def x_int(v: float) -> float:
        return (-v * v / (2 * r) - power_w * v / r ** 2
                - power_w ** 2 / r ** 3 * math.log(power_w - r * v))

    lo, hi = v_b, power_w / r
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_b + m * (t_int(mid) - t_int(v_b)) < t_end:
            lo = mid
        else:
            hi = mid
    v = (lo + hi) / 2.0
    return v, v_b ** 2 / (2 * a_f) + m * (x_int(v) - x_int(v_b))


class Recorder:
    """Wrap a model and record ``(v, a, x)`` and the power per step."""

    def __init__(self, model: TrainModel) -> None:
        self.model = model
        self.history: list[tuple[float, float, float]] = [
            (vel(model), acc(model), pos(model))]
        self.powers: list[float] = []

    def step(self, dt: float, inputs: TrainModelInputs) -> TrainModelOutputs:
        """Step the wrapped model and record its state."""
        out = self.model.step(dt, inputs)
        self.history.append((vel(self.model), acc(self.model),
                             pos(self.model)))
        self.powers.append(inputs.controller.power_cmd_w)
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
    TrainConfig(m_loaded_kg=60_000.0),
    TrainConfig(ref_load_fraction=0.5),
], ids=["default", "lighter", "heavier-load", "half-load"])
def test_derived_forces_follow_primitives(cfg: TrainConfig) -> None:
    """Check the reference mass and all forces recompute from primitives."""
    m_ref = cfg.m_empty_kg + cfg.ref_load_fraction * (
        cfg.m_loaded_kg - cfg.m_empty_kg)
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


def test_traction_gives_rated_rate_at_reference_mass() -> None:
    """Check F_max gives the datasheet 0.5 m/s^2 on the 2/3-load mass."""
    assert CFG.f_max_n / CFG.m_ref_kg == pytest.approx(0.5, rel=1e-12)


@pytest.mark.parametrize(("force", "expected_n"), [
    ("f_max_n", 25_717.0),
    ("f_service_n", 61_720.0),
    ("f_emergency_n", 140_413.0),
])
def test_forces_match_instructor_values(
        force: str, expected_n: float) -> None:
    """Check each force is the instructor's 51,433 kg figure, to 1 N."""
    assert getattr(CFG, force) == pytest.approx(expected_n, abs=1.0)


def test_reference_mass_is_two_thirds_of_datasheet_load() -> None:
    """Check m_ref = 40.9 t + 2/3 (56.7 t - 40.9 t) = 51,433 kg."""
    assert CFG.m_ref_kg == pytest.approx(
        40_900 + 2 / 3 * (56_700 - 40_900), rel=1e-12)


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
    assert onboard(model) == n
    assert model.snapshot().mass_kg == pytest.approx(mass_of(n), rel=1e-12)


@pytest.mark.parametrize("boarded", [FULL + 1, 300, 10_000])
def test_overboarding_clamps_to_capacity(boarded: int) -> None:
    """Check boarding beyond capacity stops at capacity."""
    model = fresh(boarded)
    assert onboard(model) == FULL
    assert model.snapshot().outputs.track.passenger_capacity == 0


def test_negative_boarding_is_rejected_without_side_effects() -> None:
    """Check a negative boarding count is refused (Kevin)."""
    model = TrainModel(CFG)
    at_station = {"door_left": True, "station": STATION}
    model.step(DT_S, inp(boarded=10, **at_station))
    before = model.snapshot()
    with pytest.raises(InvalidInputError, match="passengers_boarded"):
        model.step(DT_S, inp(boarded=-5, **at_station))
    assert model.snapshot() == before
    assert onboard(model) == 10


def test_crew_in_operating_mass_not_in_reference_mass() -> None:
    """Check crew and passenger mass move operating mass, not m_ref."""
    other = TrainConfig(n_crew=0, passenger_mass_kg=60.0)
    assert other.m_ref_kg == CFG.m_ref_kg
    assert fresh(REF_LOAD).snapshot().mass_kg == pytest.approx(
        CFG.m_empty_kg + (CFG.n_crew + REF_LOAD) * CFG.passenger_mass_kg)


# --------------------------------------------------------------------------- #
# C. Traction
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("n", [0, FULL])
@pytest.mark.parametrize("power_w", [100_000.0, 480_000.0, 2_000_000.0])
def test_force_limited_first_tick_is_exact(power_w: float, n: int) -> None:
    """Check a full tick of F_max: v = a dt and x = a dt^2 / 2."""
    model = fresh(n)
    x0 = pos(model)
    model.step(DT_S, inp(power_w))
    m = mass_of(n)
    a = (CFG.f_max_n - roll_n(m)) / m
    assert vel(model) == pytest.approx(a * DT_S, rel=1e-12)
    assert pos(model) - x0 == pytest.approx(a * DT_S ** 2 / 2, rel=1e-12)
    assert acc(model) == pytest.approx(a, rel=1e-12)


@pytest.mark.parametrize("n", [0, FULL])
@pytest.mark.parametrize("power_w", [1.0, 1_000.0])
def test_low_power_first_tick_respects_energy(power_w: float, n: int) -> None:
    """Check a low-power start moves, within the energy supplied."""
    model = fresh(n)
    x0 = pos(model)
    model.step(DT_S, inp(power_w))
    m = mass_of(n)
    v1 = vel(model)
    assert v1 > 0.0
    work = 0.5 * m * v1 ** 2 + roll_n(m) * (pos(model) - x0)
    assert work <= power_w * DT_S * (1 + 1e-9)
    expected = (min(power_w / v1, CFG.f_max_n) - roll_n(m)) / m
    assert acc(model) == pytest.approx(expected, rel=1e-9, abs=1e-12)


def test_zero_power_at_rest_stays_at_rest() -> None:
    """Check an unpowered train on flat track never moves."""
    model = fresh()
    for _ in range(100):
        model.step(DT_S, inp(0.0))
        assert vel(model) == 0.0
        assert acc(model) == 0.0
    assert pos(model) == 0.0


def test_power_above_pmax_is_capped() -> None:
    """Check a command above P_max gives the same motion as P_max."""
    capped = fresh()
    over = fresh()
    launch(capped, 19.0)
    launch(over, 19.0)
    capped.step(DT_S, inp(CFG.p_max_w))
    over.step(DT_S, inp(10 * CFG.p_max_w))
    assert vel(over) == pytest.approx(vel(capped), rel=1e-12)
    assert acc(over) == pytest.approx(acc(capped), rel=1e-12)


@pytest.mark.parametrize(("power_w", "v_target"), [
    (100_000.0, 5.0), (100_000.0, 10.0), (240_000.0, 15.0),
    (480_000.0, 19.0),
])
def test_reported_accel_is_instantaneous(
        power_w: float, v_target: float) -> None:
    """Check a = (min(P/v, F_max) - R) / m at the end-of-tick speed."""
    model = fresh()
    launch(model, v_target, power_w=power_w)
    model.step(DT_S, inp(power_w))
    v1 = vel(model)
    m = mass_of(0)
    expected = (min(power_w / v1, CFG.f_max_n) - roll_n(m)) / m
    assert acc(model) == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize("n", [0, REF_LOAD, FULL])
def test_traction_never_exceeds_force_or_power_limit(n: int) -> None:
    """Check implied traction stays within F_max and P_max every tick."""
    model = fresh(n)
    m = mass_of(n)
    for _ in range(600):
        model.step(DT_S, inp(CFG.p_max_w))
        f_trac = m * acc(model) + roll_n(m)
        assert f_trac <= CFG.f_max_n * (1 + 1e-12)
        assert f_trac * vel(model) <= CFG.p_max_w * (1 + 1e-9)


def test_engine_failure_zeroes_traction_while_moving() -> None:
    """Check an engine-failed train only coasts under full power."""
    model = fresh()
    launch(model, 10.0)
    model.set_failures(FailureState(engine=True))
    v0 = vel(model)
    model.step(DT_S, inp(CFG.p_max_w))
    assert acc(model) == pytest.approx(-CFG.c_rr * G, rel=1e-12)
    assert vel(model) == pytest.approx(v0 - CFG.c_rr * G * DT_S, rel=1e-12)


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


@pytest.mark.parametrize("power_w", [-1e-9, -1.0, -CFG.p_max_w])
def test_negative_power_is_rejected_without_side_effects(
        power_w: float) -> None:
    """Check negative power is refused, not applied as a hidden brake."""
    model = fresh(20)
    launch(model, 10.0)
    before = model.snapshot()
    with pytest.raises(InvalidInputError):
        model.step(DT_S, inp(power_w))
    assert model.snapshot() == before


def roll_back(model: TrainModel, grade_pct: float, seconds: float) -> None:
    """Let an unpowered, unbraked train roll back down an upgrade."""
    for _ in range(round(seconds / DT_S)):
        model.step(DT_S, inp(0.0, grade_deg=pct(grade_pct)))
    assert vel(model) < 0.0


def grade_and_roll_n(m: float, grade_pct: float) -> tuple[float, float]:
    """Return grade force and rolling resistance on ``grade_pct``."""
    th = math.radians(pct(grade_pct))
    return m * G * math.sin(th), CFG.c_rr * m * G * math.cos(th)


def test_traction_slows_a_rollback_then_drives_forward() -> None:
    """Check the motors push forward while rolling back.

    Below the base speed P/F_max the traction is the constant F_max, so
    the rollback slows at a constant rate, stops, and the train then
    drives forward up the grade.
    """
    model = fresh()
    roll_back(model, 3.0, 2.0)
    v0 = vel(model)
    assert -v0 < CFG.p_max_w / CFG.f_max_n
    m = mass_of(0)
    f_grade, f_roll = grade_and_roll_n(m, 3.0)
    expected = (CFG.f_max_n - f_grade + f_roll) / m
    model.step(DT_S, inp(CFG.p_max_w, grade_deg=pct(3.0)))
    assert acc(model) == pytest.approx(expected, rel=1e-12)
    assert vel(model) == pytest.approx(v0 + expected * DT_S, rel=1e-12)
    speeds = [vel(model)]
    for _ in range(60):
        model.step(DT_S, inp(CFG.p_max_w, grade_deg=pct(3.0)))
        speeds.append(vel(model))
    assert speeds[-1] > 0.0
    stopped = next(i for i, v in enumerate(speeds) if v >= 0.0)
    assert (stopped + 1) * DT_S == pytest.approx(-v0 / expected, abs=DT_S)


def test_traction_slows_a_rollback_it_cannot_stop() -> None:
    """Check the motors still help on a grade too steep for them."""
    model = fresh()
    roll_back(model, 8.0, 1.0)
    m = mass_of(0)
    f_grade, f_roll = grade_and_roll_n(m, 8.0)
    assert f_grade - f_roll > CFG.f_max_n
    model.step(DT_S, inp(CFG.p_max_w, grade_deg=pct(8.0)))
    assert acc(model) == pytest.approx(
        (CFG.f_max_n - f_grade + f_roll) / m, rel=1e-12)
    assert (f_roll - f_grade) / m < acc(model) < 0.0


def test_power_limited_traction_absorbs_exactly_the_commanded_power() -> None:
    """Check the energy balance of a power-limited rollback tick.

    Above the base speed the traction is P/|v| at the midpoint speed, so
    over a tick the motors take exactly P·dt out of the rollback.
    """
    power = 20_000.0
    model = fresh()
    roll_back(model, 6.0, 3.0)
    assert -vel(model) > power / CFG.f_max_n
    m = mass_of(0)
    f_grade, f_roll = grade_and_roll_n(m, 6.0)
    v0, x0 = vel(model), pos(model)
    model.step(DT_S, inp(power, grade_deg=pct(6.0)))
    v1, dx = vel(model), pos(model) - x0
    assert dx < 0.0 and -v1 > power / CFG.f_max_n
    kinetic = 0.5 * m * (v1 * v1 - v0 * v0)
    work = -power * DT_S - f_grade * dx + f_roll * dx
    assert kinetic == pytest.approx(work, rel=1e-9)


def test_a_fast_rollback_slows_through_the_base_speed_and_reverses() -> None:
    """Check a power-limited rollback slows, stops, goes forward."""
    power = 100_000.0
    v_base = power / CFG.f_max_n
    model = fresh()
    roll_back(model, 10.0, 7.0)
    assert -vel(model) > v_base
    m = mass_of(0)
    bound = (CFG.f_max_n + m * G) / m * DT_S
    last = vel(model)
    speeds = []
    for _ in range(200):
        model.step(DT_S, inp(power, grade_deg=pct(2.0)))
        assert math.isfinite(vel(model))
        assert abs(vel(model) - last) <= bound
        last = vel(model)
        speeds.append(last)
    assert min(speeds) < -v_base < 0.0 < speeds[-1]
    # It slows monotonically to the stop: the motors never let go.
    stop = next(i for i, v in enumerate(speeds) if v >= 0.0)
    assert all(a <= b for a, b in zip(speeds[:stop], speeds[1:stop + 1]))


def test_speed_is_not_governed_by_the_model() -> None:
    """Check, per the control boundary, that v_max is not a clamp."""
    model = fresh()
    for _ in range(1200):
        model.step(DT_S, inp(CFG.p_max_w))
    assert vel(model) > CFG.v_max_mps


# --------------------------------------------------------------------------- #
# D. Grade
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("grade_pct", [-6.0, -3.0, -1.0, 0.0, 1.0, 3.0, 6.0])
def test_grade_force_on_moving_train(grade_pct: float) -> None:
    """Check coasting a = -g sin - c_rr g cos, independent of mass."""
    model = fresh(100)
    launch(model, 10.0)
    v0 = vel(model)
    model.step(DT_S, inp(0.0, grade_deg=pct(grade_pct)))
    th = math.radians(pct(grade_pct))
    expected = -G * math.sin(th) - CFG.c_rr * G * math.cos(th)
    assert acc(model) == pytest.approx(expected, rel=1e-12)
    assert vel(model) == pytest.approx(v0 + expected * DT_S, rel=1e-12)


@pytest.mark.parametrize("n", [0, 111, FULL])
def test_gravity_acceleration_is_mass_independent(n: int) -> None:
    """Check an unbraked start downhill accelerates the same at any load."""
    model = fresh(n)
    th = math.radians(pct(-4.0))
    model.step(DT_S, inp(0.0, grade_deg=pct(-4.0)))
    expected = -G * math.sin(th) - CFG.c_rr * G * math.cos(th)
    assert acc(model) == pytest.approx(expected, rel=1e-12)
    assert vel(model) == pytest.approx(expected * DT_S, rel=1e-12)


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
    v0 = vel(model)
    if kind == "passenger":
        model.pull_passenger_emergency_brake()
        model.step(DT_S, inp(0.0))
        force = CFG.f_emergency_n
    else:
        model.step(DT_S, brake_inputs(kind))
        force = BRAKE_FORCE[kind]
    m = mass_of(n)
    decel = (force + roll_n(m)) / m
    assert acc(model) == pytest.approx(-decel, rel=1e-12)
    assert vel(model) == pytest.approx(v0 - decel * DT_S, rel=1e-12)


def test_emergency_supersedes_service_not_additive() -> None:
    """Check service plus emergency brakes no harder than emergency."""
    both = fresh()
    only = fresh()
    launch(both, 10.0)
    launch(only, 10.0)
    out = both.step(DT_S, inp(0.0, service=True, emergency=True))
    only.step(DT_S, inp(0.0, emergency=True))
    assert acc(both) == acc(only)
    assert vel(both) == vel(only)
    brake_state = (out.controller.emergency_brake_active,
                   out.controller.service_brake_active)
    assert brake_state == (True, False)


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


def test_test_override_releases_passenger_brake() -> None:
    """Check the test-only override clears the latch and the brake."""
    model = fresh()
    model.pull_passenger_emergency_brake()
    model.step(DT_S, inp(CFG.p_max_w))
    assert vel(model) == 0.0
    model.clear_passenger_brake_for_test()
    assert model.snapshot().passenger_ebrake_pulled is False
    out = model.step(DT_S, inp(CFG.p_max_w))
    assert out.controller.emergency_brake_active is False
    assert vel(model) > 0.0


def test_brake_failure_blocks_the_service_brake() -> None:
    """Check a failed service brake leaves only rolling resistance."""
    model = fresh()
    launch(model, 10.0)
    model.set_failures(FailureState(brake=True))
    v0 = vel(model)
    out = model.step(DT_S, brake_inputs("service"))
    assert acc(model) == pytest.approx(-CFG.c_rr * G, rel=1e-12)
    assert vel(model) == pytest.approx(v0 - CFG.c_rr * G * DT_S, rel=1e-12)
    assert out.controller.service_brake_active is False


@pytest.mark.parametrize("kind", ["emergency", "passenger"])
def test_brake_failure_leaves_the_emergency_brake(kind: str) -> None:
    """Check the emergency brake still brakes fully under brake failure."""
    model = fresh()
    launch(model, 10.0)
    model.set_failures(FailureState(brake=True))
    v0 = vel(model)
    if kind == "passenger":
        model.pull_passenger_emergency_brake()
        out = model.step(DT_S, inp(0.0))
    else:
        out = model.step(DT_S, brake_inputs(kind))
    m = mass_of(0)
    decel = (CFG.f_emergency_n + roll_n(m)) / m
    assert acc(model) == pytest.approx(-decel, rel=1e-12)
    assert vel(model) == pytest.approx(v0 - decel * DT_S, rel=1e-12)
    assert out.controller.emergency_brake_active is True


@pytest.mark.parametrize("v0", [5.0, 12.0, CFG.v_max_mps])
@pytest.mark.parametrize("n", [0, FULL])
@pytest.mark.parametrize("kind", ["service", "emergency"])
def test_stopping_distance_matches_srs_formula(
        kind: str, n: int, v0: float) -> None:
    """Check SRS Appendix B d = v^2 / (2a), exactly."""
    model = fresh(n)
    launch(model, v0)
    v_start = vel(model)
    x0 = pos(model)
    run_to_stop(model, lambda: brake_inputs(kind))
    m = mass_of(n)
    a_b = (BRAKE_FORCE[kind] + roll_n(m)) / m
    expected = v_start ** 2 / (2 * a_b)
    assert pos(model) - x0 == pytest.approx(expected, rel=1e-9)


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
    last = pos(model)
    for _ in range(200):
        model.step(DT_S, brake_inputs(kind, grade_deg=pct(6.0)))
        assert vel(model) <= 0.0
        assert pos(model) <= last
        last = pos(model)
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
    """Check traction is not cut while braking: the controller decides."""
    model = fresh()
    launch(model, 10.0)
    model.step(DT_S, brake_inputs(kind, power_w=CFG.p_max_w))
    v1 = vel(model)
    m = mass_of(0)
    f_trac = min(CFG.p_max_w / v1, CFG.f_max_n)
    expected = (f_trac - BRAKE_FORCE[kind] - roll_n(m)) / m
    assert acc(model) == pytest.approx(expected, rel=1e-12)


# --------------------------------------------------------------------------- #
# F. Integration and numerics
# --------------------------------------------------------------------------- #

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
    """Roll unbraked down a 2 percent grade from rest."""
    for _ in range(200):
        model.step(DT_S, inp(0.0, grade_deg=pct(-2.0)))


def _scenario_uphill(model: Recorder) -> None:
    """Launch, then coast up a 4 percent grade."""
    launch(model, 8.0)
    for _ in range(100):
        model.step(DT_S, inp(0.0, grade_deg=pct(4.0)))


@pytest.mark.parametrize("scenario", [
    _scenario_coast, _scenario_brake, _scenario_grade, _scenario_uphill,
], ids=["coast", "brake", "grade", "uphill"])
def test_unpowered_ticks_are_exact_kinematics(
        scenario: Callable[[Recorder], None]) -> None:
    """Check constant-force ticks: dv = a dt and dx = dt (v0 + v1) / 2."""
    recorder = Recorder(fresh())
    scenario(recorder)
    history = recorder.history
    checked = 0
    for power, (v0, _, x0), (v1, a1, x1) in zip(
            recorder.powers, history, history[1:]):
        if power > 0.0 or v1 == 0.0 or v0 * v1 < 0.0:
            continue  # traction, a stop, or a reversal
        assert v1 - v0 == pytest.approx(a1 * DT_S, rel=1e-9, abs=1e-12)
        assert x1 - x0 == pytest.approx(DT_S * (v0 + v1) / 2, rel=1e-9)
        checked += 1
    assert checked > 30


@pytest.mark.parametrize("grade_pct", [-2.0, 0.0, 2.0])
def test_power_limited_ticks_balance_energy(grade_pct: float) -> None:
    """Check KE gain + resistive work = P dt on every power-limited tick."""
    g_deg = pct(grade_pct)
    model = fresh()
    launch(model, 19.0)
    m = mass_of(0)
    resist = m * G * math.sin(math.radians(g_deg)) + roll_n(m, g_deg)
    for _ in range(100):
        v0, x0 = vel(model), pos(model)
        model.step(DT_S, inp(CFG.p_max_w, grade_deg=g_deg))
        v1, x1 = vel(model), pos(model)
        assert min(v0, v1) > CFG.p_max_w / CFG.f_max_n
        d_ke = 0.5 * m * (v1 ** 2 - v0 ** 2)
        assert d_ke + resist * (x1 - x0) == pytest.approx(
            CFG.p_max_w * DT_S, rel=1e-9)


def test_slowing_through_the_force_limit_caps_traction_work() -> None:
    """Check traction work stays below P dt while slowing below P/F_max.

    Below the base speed the motors are force-limited, so F_max v < P:
    the tick that slows through it must deliver less than P dt.
    """
    g_deg = pct(10.0)
    m = mass_of(FULL)
    resist = m * G * math.sin(math.radians(g_deg)) + roll_n(m, g_deg)
    v_base = CFG.p_max_w / CFG.f_max_n
    model = fresh(FULL)
    launch(model, 19.5)
    for _ in range(100):
        v0, x0 = vel(model), pos(model)
        model.step(1.0, inp(CFG.p_max_w, grade_deg=g_deg))
        v1, x1 = vel(model), pos(model)
        work = 0.5 * m * (v1 ** 2 - v0 ** 2) + resist * (x1 - x0)
        assert work <= CFG.p_max_w * 1.0 * (1 + 1e-9)
        if v0 > v_base > v1:
            assert work < CFG.p_max_w * 1.0 * (1 - 1e-3)
            return
    pytest.fail("never slowed through the base speed")


@pytest.mark.parametrize("n_ticks", [1, 10, 50])
def test_constant_acceleration_closed_form(n_ticks: int) -> None:
    """Check the force-limited launch: v = a t and x = a t^2 / 2."""
    model = fresh()
    for _ in range(n_ticks):
        model.step(DT_S, inp(CFG.p_max_w))
    m = mass_of(0)
    a = (CFG.f_max_n - roll_n(m)) / m
    t = n_ticks * DT_S
    assert vel(model) == pytest.approx(a * t, rel=1e-12)
    assert pos(model) == pytest.approx(a * t ** 2 / 2, rel=1e-12)


@pytest.mark.parametrize("power_w", [50_000.0, 100_000.0, 480_000.0])
@pytest.mark.parametrize("dt", [0.2, 0.1, 0.05])
def test_launch_matches_closed_form_solution(
        power_w: float, dt: float) -> None:
    """Check a 60 s launch matches the exact solution to 1e-5."""
    v_ref, x_ref = analytic_launch(power_w, 60.0)
    model = fresh()
    for _ in range(round(60.0 / dt)):
        model.step(dt, inp(power_w))
    assert vel(model) == pytest.approx(v_ref, rel=1e-5)
    assert pos(model) == pytest.approx(x_ref, rel=1e-5)


@pytest.mark.parametrize("power_w", [50_000.0, 100_000.0, 480_000.0])
def test_integration_is_second_order(power_w: float) -> None:
    """Check halving dt cuts the position error about fourfold."""
    _, x_ref = analytic_launch(power_w, 60.0)
    errors = []
    for dt in (0.2, 0.1, 0.05):
        model = fresh()
        for _ in range(round(60.0 / dt)):
            model.step(dt, inp(power_w))
        errors.append(abs(pos(model) - x_ref))
    assert 3.5 < errors[0] / errors[1] < 4.5
    assert 3.5 < errors[1] / errors[2] < 4.5


@pytest.mark.parametrize("dt", [
    0.0, -0.1, -1e-12, -math.inf, math.inf, math.nan])
def test_invalid_dt_rejected(dt: float) -> None:
    """Check a time step that is not finite and positive raises."""
    model = fresh()
    with pytest.raises(InvalidTimeStepError):
        model.step(dt, inp(CFG.p_max_w))


@pytest.mark.parametrize("dt", [-1.0, math.nan, math.inf])
def test_rejected_dt_leaves_state_untouched(dt: float) -> None:
    """Check a rejected step changes nothing, boarding included."""
    model = fresh(20)
    launch(model, 5.0)
    before = model.snapshot()
    with pytest.raises(InvalidTimeStepError):
        model.step(dt, inp(CFG.p_max_w, boarded=50, door_left=True,
                           station=STATION))
    assert model.snapshot() == before


def test_halving_dt_gives_the_same_trajectory() -> None:
    """Check dt = 0.1 and dt = 0.05 agree to 1e-6 over 30 s."""
    coarse = fresh()
    fine = fresh()
    for _ in range(300):
        coarse.step(0.1, inp(CFG.p_max_w))
    for _ in range(600):
        fine.step(0.05, inp(CFG.p_max_w))
    assert vel(coarse) == pytest.approx(vel(fine), rel=1e-6)
    assert pos(coarse) == pytest.approx(pos(fine), rel=1e-6)


# --------------------------------------------------------------------------- #
# G. Energy and momentum
# --------------------------------------------------------------------------- #

def test_work_energy_coasting_on_flat() -> None:
    """Check lost kinetic energy equals rolling resistance work."""
    model = fresh(60)
    launch(model, 10.0)
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
    v1, x1 = vel(model), pos(model)
    run_to_stop(model, lambda: inp(0.0, emergency=True))
    m = mass_of(n)
    work_d = 0.5 * m * v1 ** 2 / (CFG.f_emergency_n + roll_n(m))
    assert pos(model) - x1 == pytest.approx(work_d, rel=1e-9)


def test_power_limited_regime_energy_balance() -> None:
    """Check energy in at P_max equals kinetic gain plus rolling losses."""
    model = fresh()
    launch(model, 19.0)
    v1, x1 = vel(model), pos(model)
    ticks = 100
    for _ in range(ticks):
        model.step(DT_S, inp(CFG.p_max_w))
    m = mass_of(0)
    d_ke = 0.5 * m * (vel(model) ** 2 - v1 ** 2)
    work_in = CFG.p_max_w * ticks * DT_S
    assert d_ke + roll_n(m) * (pos(model) - x1) == pytest.approx(
        work_in, rel=1e-9)


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


def test_gravity_reverses_unbraked_train_within_the_tick() -> None:
    """Check stop and rollback within one tick match the kinematics."""
    th = math.radians(pct(6.0))
    a_up = G * math.sin(th) + CFG.c_rr * G * math.cos(th)
    a_down = G * math.sin(th) - CFG.c_rr * G * math.cos(th)
    model = fresh()
    launch(model, 3.0)
    for _ in range(200):
        v0, x0 = vel(model), pos(model)
        model.step(DT_S, inp(0.0, grade_deg=pct(6.0)))
        if vel(model) < 0.0:
            break
    else:
        pytest.fail("train never rolled back on 6 percent")
    t_stop = v0 / a_up
    t_back = DT_S - t_stop
    assert vel(model) == pytest.approx(-a_down * t_back, rel=1e-9)
    assert pos(model) == pytest.approx(
        x0 + v0 * t_stop / 2 - a_down * t_back ** 2 / 2, rel=1e-9)


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
# I. Position and block changes
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("flip_ticks", [
    (40,), (40, 80), (20, 40, 60, 80, 100)])
def test_polarity_flip_resets_offset(flip_ticks: tuple[int, ...]) -> None:
    """Check a polarity flip flags a block change and restarts the offset."""
    model = fresh()
    polarity = True
    for tick in range(120):
        if tick in flip_ticks:
            polarity = not polarity
        x_prev = pos(model)
        v_prev = vel(model)
        out = model.step(DT_S, inp(CFG.p_max_w, polarity=polarity))
        assert out.track.block_changed is (tick in flip_ticks)
        dx = DT_S * (v_prev + vel(model)) / 2
        if tick in flip_ticks:
            assert out.track.offset_m == pytest.approx(dx, rel=1e-9)
        else:
            assert out.track.offset_m == pytest.approx(
                x_prev + dx, rel=1e-9)


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
# J. Door interlock
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("side", ["left", "right", "both"])
def test_doors_open_at_rest(side: str) -> None:
    """Check a door commanded open at 0 mph opens."""
    left = side in ("left", "both")
    right = side in ("right", "both")
    out = fresh().step(DT_S, inp(door_left=left, door_right=right))
    assert doors(out) == (left, right)


@pytest.mark.parametrize("speed", [0.5, 5.0, 15.0])
@pytest.mark.parametrize("side", ["left", "right"])
def test_door_refuses_to_open_while_moving(speed: float, side: str) -> None:
    """Check the interlock holds a door closed while moving forward."""
    model = fresh()
    launch(model, speed)
    out = model.step(DT_S, inp(0.0, door_left=side == "left",
                               door_right=side == "right"))
    assert vel(model) > 0.0
    assert doors(out) == (False, False)


def test_door_refuses_to_open_during_rollback() -> None:
    """Check the interlock also holds while rolling backward."""
    model = fresh()
    for _ in range(10):
        model.step(DT_S, inp(0.0, grade_deg=pct(4.0)))
    assert vel(model) < 0.0
    out = model.step(DT_S, inp(0.0, grade_deg=pct(4.0), door_left=True,
                               door_right=True))
    assert doors(out) == (False, False)


def test_open_door_closes_once_the_train_moves() -> None:
    """Check an open door does not stay open after the train starts."""
    model = fresh()
    assert doors(model.step(DT_S, inp(door_left=True))) == (True, False)
    for _ in range(20):
        out = model.step(DT_S, inp(CFG.p_max_w, door_left=True))
        assert vel(model) > 0.0
        assert doors(out) == (False, False)


def test_brake_failure_rollback_closes_open_doors() -> None:
    """Check open doors close when a held train starts to roll."""
    model = fresh()
    held = brake_inputs("service", grade_deg=pct(6.0))
    opened = dataclasses.replace(held, controller=dataclasses.replace(
        held.controller, door_left_open=True, door_right_open=True))
    assert doors(model.step(DT_S, opened)) == (True, True)
    model.set_failures(FailureState(brake=True))
    out = model.step(DT_S, opened)
    assert vel(model) < 0.0
    assert doors(out) == (False, False)


def test_held_open_command_waits_for_the_stop() -> None:
    """Check a held open command takes effect only once stopped."""
    model = fresh()
    launch(model, 5.0)
    out = run_to_stop(model, lambda: inp(0.0, service=True, door_left=True))
    assert doors(out) == (False, False)
    out = model.step(DT_S, inp(0.0, service=True, door_left=True))
    assert doors(out) == (True, False)


def test_door_closes_on_command_at_rest() -> None:
    """Check a door commanded closed at rest closes."""
    model = fresh()
    model.step(DT_S, inp(door_right=True))
    assert doors(model.step(DT_S, inp())) == (False, False)


def test_disembark_waits_for_the_interlocked_door() -> None:
    """Check nobody leaves while moving; the draw happens at the stop."""
    changed = False
    for seed in range(10):
        model = fresh(FULL, TrainConfig(seed=seed))
        launch(model, 3.0)
        run_to_stop(model, lambda: inp(0.0, service=True, door_left=True))
        assert onboard(model) == FULL
        model.step(DT_S, inp(0.0, service=True, door_left=True))
        changed = changed or onboard(model) < FULL
    assert changed


def test_door_reported_open_only_at_zero_speed() -> None:
    """Check across a random run that an open door means 0 mph."""
    rng = random.Random(7)
    model = fresh(50)
    for _ in range(3000):
        out = model.step(DT_S, inp(
            rng.choice([0.0, 0.0, CFG.p_max_w]),
            service=rng.random() < 0.3,
            grade_deg=pct(rng.uniform(-5.0, 5.0)),
            door_left=rng.random() < 0.5, door_right=rng.random() < 0.5))
        if any(doors(out)):
            assert out.controller.actual_speed_mps == 0.0
            assert out.track.actual_speed_mps == 0.0


# --------------------------------------------------------------------------- #
# K. Passengers
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(("left", "right"), [
    (True, False), (False, True), (True, True)])
def test_boarding_at_a_station_with_a_door_open(
        left: bool, right: bool) -> None:
    """Check passengers board at a station through either door."""
    model = TrainModel(CFG)
    model.step(DT_S, inp(boarded=40, door_left=left, door_right=right,
                         station=STATION))
    assert onboard(model) == 40


@pytest.mark.parametrize("station", [None, ""])
def test_no_boarding_away_from_a_station(station: str | None) -> None:
    """Check an open door away from a station boards nobody."""
    model = TrainModel(CFG)
    model.step(DT_S, inp(boarded=40, door_left=True, station=station))
    assert onboard(model) == 0


def test_no_boarding_with_doors_closed_at_a_station() -> None:
    """Check closed doors at a station board nobody."""
    model = TrainModel(CFG)
    model.step(DT_S, inp(boarded=40, station=STATION))
    assert onboard(model) == 0


def test_no_boarding_while_moving_at_a_station() -> None:
    """Check boarding cannot happen while the interlock holds the doors."""
    model = fresh()
    launch(model, 3.0)
    model.step(DT_S, inp(boarded=40, door_left=True, station=STATION))
    assert onboard(model) == 0


def test_refused_boarding_count_is_not_deferred() -> None:
    """Check a refused count is dropped, not applied when a door opens."""
    model = TrainModel(CFG)
    model.step(DT_S, inp(boarded=40, station=STATION))
    model.step(DT_S, inp(door_left=True, station=STATION))
    assert onboard(model) == 0


def test_boarding_changes_mass_and_dynamics() -> None:
    """Check boarded passengers slow the next launch."""
    light = fresh()
    heavy = fresh(FULL)
    light.step(DT_S, inp(CFG.p_max_w))
    heavy.step(DT_S, inp(CFG.p_max_w))
    assert acc(heavy) == pytest.approx(
        (CFG.f_max_n - roll_n(mass_of(FULL))) / mass_of(FULL), rel=1e-12)
    assert acc(heavy) < acc(light)


def test_disembark_only_on_rising_door_edge() -> None:
    """Check doors held open do not draw again."""
    model = fresh(FULL)
    model.step(DT_S, inp(door_left=True))
    after_edge = onboard(model)
    for _ in range(20):
        model.step(DT_S, inp(door_left=True))
        assert onboard(model) == after_edge


def test_one_disembark_draw_per_stop() -> None:
    """Check a stop draws once, however its doors open (Kevin).

    Opening the other door, or closing and reopening one, draws nobody
    more; the next stop, once the train has moved, draws again.
    """
    drew_again = False
    for seed in range(10):
        model = fresh(FULL, TrainConfig(seed=seed))
        next_stop(model)
        model.step(DT_S, inp(door_left=True))
        first = onboard(model)
        for left, right in [(True, True), (False, False), (False, True),
                            (False, False), (True, False), (True, True)]:
            model.step(DT_S, inp(door_left=left, door_right=right))
            assert onboard(model) == first, f"seed {seed}"
        next_stop(model)
        model.step(DT_S, inp(door_right=True))
        drew_again = drew_again or onboard(model) < first
    assert drew_again


def test_no_disembark_when_doors_commanded_open_while_moving() -> None:
    """Check nobody leaves through doors commanded open while moving."""
    model = fresh(FULL)
    launch(model, 2.0)
    model.step(DT_S, inp(door_left=True, door_right=True))
    assert onboard(model) == FULL


@pytest.mark.parametrize("side", ["left", "right"])
def test_either_door_edge_triggers_disembark(side: str) -> None:
    """Check either side's door opening at rest draws a disembark."""
    changed = False
    for seed in range(10):
        model = fresh(FULL, TrainConfig(seed=seed))
        next_stop(model)
        model.step(DT_S, inp(door_left=side == "left",
                             door_right=side == "right"))
        changed = changed or onboard(model) < FULL
    assert changed


def test_disembark_draw_is_uniform_over_onboard() -> None:
    """Check the disembark draw spans 0..onboard with mean onboard/2."""
    draws = []
    for seed in range(300):
        model = fresh(FULL, TrainConfig(seed=seed))
        next_stop(model)
        model.step(DT_S, inp(door_left=True))
        draws.append(FULL - onboard(model))
    assert all(0 <= d <= FULL for d in draws)
    assert sum(draws) / len(draws) == pytest.approx(FULL / 2, abs=15)
    assert min(draws) < 30 and max(draws) > FULL - 30


@pytest.mark.parametrize("n_onboard", [0, 1, 5])
def test_disembark_bounded_by_onboard(n_onboard: int) -> None:
    """Check no more passengers leave than are aboard."""
    for seed in range(20):
        model = fresh(n_onboard, TrainConfig(seed=seed))
        next_stop(model)
        model.step(DT_S, inp(door_left=True))
        assert 0 <= onboard(model) <= n_onboard


def test_capacity_output_is_after_the_draw() -> None:
    """Check reported capacity reflects the disembark of the same tick."""
    model = fresh(FULL, TrainConfig(seed=3))
    next_stop(model)
    out = model.step(DT_S, inp(door_left=True))
    assert onboard(model) < FULL
    assert out.track.passenger_capacity == FULL - onboard(model)


def test_boarding_after_disembark_respects_capacity() -> None:
    """Check boarding fills the room the disembark left, no more."""
    model = fresh(FULL)
    out = model.step(DT_S, inp(door_left=True, boarded=FULL,
                               station=STATION))
    assert onboard(model) == FULL
    assert out.track.passenger_capacity == 0


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
    out = fresh().step(DT_S, inp(cmd_speed_mps=13.5, authority=12))
    assert out.controller.commanded_speed_mps == 13.5
    assert out.controller.authority_blocks == 12


@pytest.mark.parametrize("authority", [-1, 2.0, "3"])
def test_invalid_authority_is_rejected_without_side_effects(
        authority: object) -> None:
    """Check authority must be a nonnegative whole number of blocks."""
    model = fresh(20)
    launch(model, 10.0)
    before = model.snapshot()
    with pytest.raises(InvalidInputError, match="authority_blocks"):
        model.step(DT_S, inp(authority=authority))  # type: ignore[arg-type]
    assert model.snapshot() == before


@pytest.mark.parametrize(("field", "overrides"), [
    ("speed_limit_mps", {"speed_limit_mps": -0.1}),
    ("commanded_speed_mps", {"cmd_speed_mps": -1.0}),
    ("grade_deg", {"grade_deg": 90.0}),
    ("grade_deg", {"grade_deg": -90.0}),
    ("grade_deg", {"grade_deg": 135.0}),
    ("grade_deg", {"grade_deg": -270.0}),
])
def test_meaningless_inputs_are_rejected_without_side_effects(
        field: str, overrides: dict[str, Any]) -> None:
    """Check values with no physical meaning are refused (Kevin)."""
    model = fresh(20)
    launch(model, 10.0)
    before = model.snapshot()
    with pytest.raises(InvalidInputError, match=field):
        model.step(DT_S, inp(**overrides))
    assert model.snapshot() == before


@pytest.mark.parametrize(("field", "overrides"), [
    ("authority_blocks", {"authority": 2**31}),
    ("authority_blocks", {"authority": 2**70}),
    ("passengers_boarded", {"boarded": 2**31}),
])
def test_counts_too_large_to_carry_are_rejected(
        field: str, overrides: dict[str, Any]) -> None:
    """Check counts beyond a 32-bit int are refused (Kevin).

    Qt and QML carry counts as 32-bit ints; a larger one would break
    the views that show it.
    """
    model = fresh(20)
    before = model.snapshot()
    with pytest.raises(InvalidInputError, match=field):
        model.step(DT_S, inp(**overrides))
    assert model.snapshot() == before


@pytest.mark.parametrize("overrides", [
    {"authority": 2**31 - 1}, {"boarded": 2**31 - 1},
    {"speed_limit_mps": 0.0}, {"cmd_speed_mps": 0.0},
    {"grade_deg": 89.9}, {"grade_deg": -89.9},
])
def test_the_limits_themselves_are_accepted(
        overrides: dict[str, Any]) -> None:
    """Check zero speeds and any grade short of vertical still step."""
    fresh().step(DT_S, inp(**overrides))


def test_signal_pickup_failure_blanks_only_the_track_signal() -> None:
    """Check pickup failure blanks the signal but not the track info."""
    model = fresh()
    model.set_failures(FailureState(signal_pickup=True))
    out = model.step(DT_S, inp(cmd_speed_mps=13.5, authority=12,
                               speed_limit_mps=12.0, block_id="C3"))
    assert out.controller.commanded_speed_mps == 0.0
    assert out.controller.authority_blocks == 0
    assert out.controller.speed_limit_mps == 12.0
    assert out.track.block_id == "C3"


@pytest.mark.parametrize("engine", [False, True])
@pytest.mark.parametrize("pickup", [False, True])
@pytest.mark.parametrize("brake", [False, True])
def test_failure_status_is_not_sent_to_the_controller(
        engine: bool, pickup: bool, brake: bool) -> None:
    """Check every failure combination is held but never output."""
    model = fresh()
    state = FailureState(engine=engine, signal_pickup=pickup, brake=brake)
    model.set_failures(state)
    out = model.step(DT_S, inp())
    assert model.snapshot().failures == state
    assert not hasattr(out.controller, "failures")


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


def test_failure_shown_now_and_acts_on_the_next_step() -> None:
    """Check a failure is shown at once; its force acts next step."""
    model = fresh()
    launch(model, 5.0)
    before = model.snapshot()
    model.set_failures(FailureState(engine=True))
    snap = model.snapshot()
    assert snap.failures == FailureState(engine=True)
    assert snap.velocity_mps == before.velocity_mps
    assert snap.outputs.track.offset_m == before.outputs.track.offset_m
    model.step(DT_S, inp(CFG.p_max_w))
    assert acc(model) == pytest.approx(-CFG.c_rr * G, rel=1e-12)


# --------------------------------------------------------------------------- #
# N. Randomised invariants
# --------------------------------------------------------------------------- #

def test_random_runs_keep_physical_invariants() -> None:
    """Check finite state, monotone travel, interlock and boarding rules."""
    rng = random.Random(2026)
    for trial in range(40):
        model = TrainModel(TrainConfig(seed=trial))
        dt = rng.choice([0.01, 0.1, 0.5, 1.0])
        model.set_failures(FailureState(rng.random() < 0.2,
                                        rng.random() < 0.2,
                                        rng.random() < 0.2))
        for _ in range(rng.randint(20, 200)):
            station = rng.choice([None, STATION])
            before = model.snapshot()
            out = model.step(dt, inp(
                rng.choice([0.0, CFG.p_max_w, rng.uniform(0, 1e6)]),
                service=rng.random() < 0.25, emergency=rng.random() < 0.1,
                grade_deg=pct(rng.uniform(-12.0, 12.0)),
                boarded=rng.randint(0, 60), door_left=rng.random() < 0.3,
                station=station, polarity=rng.random() < 0.98))
            snap = model.snapshot()
            v0, v1 = before.velocity_mps, snap.velocity_mps
            x0 = 0.0 if out.track.block_changed else (
                before.outputs.track.offset_m)
            dx = out.track.offset_m - x0
            assert all(map(math.isfinite, (v1, dx, snap.acceleration_mps2)))
            if v0 >= 0.0 and v1 >= 0.0:
                assert dx >= 0.0
            if v0 <= 0.0 and v1 <= 0.0:
                assert dx <= 0.0
            if any(doors(out)):
                assert v1 == 0.0
            if snap.n_passengers > before.n_passengers:
                assert station and v0 == 0.0
            assert 0 <= snap.n_passengers <= CFG.capacity
            assert snap.mass_kg == pytest.approx(mass_of(snap.n_passengers))
