"""Physics tests for whatever sits at ``train_model.model.TrainModel``.

The model is treated as a black box: only the public protocol and the
``TrainConfig`` properties are consulted, never the implementation.
Expectations are computed from the configuration wherever possible; the
literals in test 1 and test 3 are the datasheet design values themselves.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from train_model.interface import (
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
from train_model.model import TrainModel

DT_S = 0.1


def pct_to_deg(grade_percent: float) -> float:
    """Return the angle in degrees of a grade given in percent."""
    return math.degrees(math.atan(grade_percent / 100.0))


def make_inputs(
    power_w: float = 0.0,
    service: bool = False,
    emergency: bool = False,
    grade_deg: float = 0.0,
    boarded: int = 0,
    door_left: bool = False,
    polarity: bool = True,
    interior: bool = False,
    exterior: bool = False,
    station: str | None = None,
) -> TrainModelInputs:
    """Return the standard input set with the named overrides applied."""
    return TrainModelInputs(
        controller=ControllerCommands(
            power_cmd_w=power_w,
            service_brake=service,
            emergency_brake=emergency,
            interior_lights=interior,
            exterior_lights=exterior,
            door_left_open=door_left,
            door_right_open=False,
            temp_setpoint_c=21.0,
            announcement="",
        ),
        track=TrackInputs(
            track_info=TrackInfo(
                block_id="A1",
                grade_deg=grade_deg,
                elevation_m=0.0,
                speed_limit_mps=19.0,
                polarity=polarity,
                station_name=station,
            ),
            track_signal=TrackSignal(
                commanded_speed_mps=10.0,
                authority_blocks=9,
            ),
            beacon=None,
            passengers_boarded=boarded,
        ),
    )


def board(model: TrainModel, n: int) -> None:
    """Board ``n`` passengers at a station, then close the door."""
    model.step(DT_S, make_inputs(boarded=n, door_left=True, station="S"))
    model.step(DT_S, make_inputs())


def run_until_speed(
    model: TrainModel, target_mps: float, grade_deg: float = 0.0
) -> None:
    """Step at full power until the velocity reaches ``target_mps``."""
    for _ in range(5000):
        if model.snapshot().velocity_mps >= target_mps:
            return
        model.step(DT_S, make_inputs(
            power_w=model.config.p_max_w, grade_deg=grade_deg))
    pytest.fail(f"never reached {target_mps} m/s within 5000 ticks")


def brake_to_stop(model: TrainModel, **kwargs: bool) -> None:
    """Brake with zero power until the velocity is exactly zero."""
    for _ in range(5000):
        model.step(DT_S, make_inputs(**kwargs))
        if model.snapshot().velocity_mps <= 0.0:
            return
    pytest.fail("never reached a full stop within 5000 ticks")


def expected_mass(config: TrainConfig, n_passengers: int) -> float:
    """Return the total train mass for a given passenger count."""
    n_people = config.n_crew + n_passengers
    return config.m_empty_kg + n_people * config.passenger_mass_kg


def test_design_constants() -> None:
    """Check the derived design constants match the datasheet values."""
    config = TrainConfig()
    # 2/3 of the datasheet load: 40.9 t empty, 56.7 t loaded.
    assert config.m_ref_kg == pytest.approx(51_433, abs=1.0)
    assert config.f_max_n == pytest.approx(25_717, abs=1.0)
    # The instructor's values: 51,433 kg x 1.2 and x 2.73.
    assert config.f_service_n == pytest.approx(61_720, abs=1.0)
    assert config.f_emergency_n == pytest.approx(140_413, abs=1.0)


def test_first_tick_acceleration_two_thirds_load() -> None:
    """Check first-tick acceleration at two-thirds load matches the balance."""
    config = TrainConfig()
    model = TrainModel(config)
    board(model, round(config.capacity * config.ref_load_fraction))
    model.step(DT_S, make_inputs(power_w=config.p_max_w))
    snap = model.snapshot()
    drag_n = config.c_rr * snap.mass_kg * config.g_mps2
    expected = (config.f_max_n - drag_n) / snap.mass_kg
    assert snap.acceleration_mps2 == pytest.approx(expected, rel=1e-9)


@pytest.mark.parametrize(
    ("n_passengers", "expected_m"),
    [(0, 55.0), (222, 77.0)],
)
def test_emergency_stop_distance(
    n_passengers: int, expected_m: float
) -> None:
    """Check the full-speed emergency stop distance meets the design value."""
    model = TrainModel(TrainConfig())
    board(model, n_passengers)
    run_until_speed(model, model.config.v_max_mps)
    start_m = model.snapshot().outputs.track.offset_m
    brake_to_stop(model, service=False, emergency=True)
    stop_m = model.snapshot().outputs.track.offset_m
    assert stop_m - start_m == pytest.approx(expected_m, abs=3.0)


def test_full_train_grade_threshold() -> None:
    """Check the full train creeps at 4.2 percent grade but not 4.4.

    The limit, F_max = m g (sin + c_rr cos), is about 4.29 percent.
    """
    config = TrainConfig()
    model = TrainModel(config)
    board(model, config.capacity)
    for _ in range(200):
        model.step(DT_S, make_inputs(
            power_w=config.p_max_w, grade_deg=pct_to_deg(4.2)))
    assert model.snapshot().velocity_mps > 0.0

    model = TrainModel(config)
    board(model, config.capacity)
    for _ in range(1000):
        model.step(DT_S, make_inputs(
            power_w=config.p_max_w, grade_deg=pct_to_deg(4.4)))
        assert model.snapshot().velocity_mps == 0.0


def test_service_brake_holds_full_train_on_6_percent() -> None:
    """Check the service brake holds a full train on a 6 percent grade."""
    config = TrainConfig()
    model = TrainModel(config)
    board(model, config.capacity)
    for _ in range(1000):
        model.step(DT_S, make_inputs(service=True, grade_deg=pct_to_deg(6.0)))
        assert model.snapshot().velocity_mps == 0.0


def test_brake_failure_rolls_back_on_6_percent() -> None:
    """Check a brake-failed train rolls back on a 6 percent grade."""
    config = TrainConfig()
    model = TrainModel(config)
    board(model, config.capacity)
    model.set_failures(FailureState(brake=True))
    # The spec does not fix the horizon; 500 ticks is long enough for any
    # rolling resistance to be overwhelmed by the grade.
    for _ in range(500):
        model.step(DT_S, make_inputs(service=True, grade_deg=pct_to_deg(6.0)))
    assert model.snapshot().velocity_mps < 0.0


@pytest.mark.parametrize("target_mps", [1.0, 5.0, 12.0, 19.0])
@pytest.mark.parametrize("brake", ["service", "emergency"])
def test_braking_never_reverses(target_mps: float, brake: str) -> None:
    """Check braking stops the train at exactly zero without reversing."""
    model = TrainModel(TrainConfig())
    run_until_speed(model, target_mps)
    kwargs = {"service": brake == "service", "emergency": brake == "emergency"}
    for _ in range(5000):
        model.step(DT_S, make_inputs(**kwargs))
        snap = model.snapshot()
        assert snap.velocity_mps >= 0.0
        if snap.velocity_mps == 0.0:
            break
    else:
        pytest.fail("never reached a full stop within 5000 ticks")
    for _ in range(100):
        model.step(DT_S, make_inputs(**kwargs))
        assert model.snapshot().velocity_mps == 0.0


def test_engine_failure_power_has_no_effect() -> None:
    """Check commanded power cannot move an engine-failed train."""
    model_off = TrainModel(TrainConfig())
    model_on = TrainModel(TrainConfig())
    failures = FailureState(engine=True)
    model_off.set_failures(failures)
    model_on.set_failures(failures)
    for _ in range(100):
        model_off.step(DT_S, make_inputs(power_w=0.0))
        model_on.step(DT_S, make_inputs(
            power_w=model_on.config.p_max_w))
        # Producer commands differ; the entire physical state must agree.
        assert replace(model_off.snapshot(), inputs=None) == replace(
            model_on.snapshot(), inputs=None
        )
        assert model_off.snapshot().velocity_mps == 0.0


def test_all_failures_compose() -> None:
    """Check all failures leave only rolling resistance under service."""
    config = TrainConfig()
    model = TrainModel(config)
    run_until_speed(model, 10.0)
    assert model.snapshot().velocity_mps > 0.0
    model.set_failures(FailureState(True, True, True))
    expected_accel = -config.c_rr * config.g_mps2
    # The train is coasting at ~10 m/s and decelerating at c_rr * g, so it
    # is still moving comfortably after this many ticks.
    for _ in range(500):
        assert model.snapshot().velocity_mps > 0.0
        outputs = model.step(DT_S, make_inputs(
            power_w=config.p_max_w, service=True))
        accel = model.snapshot().acceleration_mps2
        assert accel == pytest.approx(expected_accel, rel=1e-9)
        assert outputs.controller.commanded_speed_mps == 0.0
        assert outputs.controller.authority_blocks == 0
        assert model.snapshot().failures == FailureState(True, True, True)


def test_passenger_bounds_and_capacity() -> None:
    """Check the passenger count stays clamped between zero and capacity."""
    config = TrainConfig()
    model = TrainModel(config)

    def check_bounds(snap: TrainModelSnapshot) -> None:
        assert 0 <= snap.n_passengers <= config.capacity
        capacity_out = snap.outputs.track.passenger_capacity
        assert capacity_out == config.capacity - snap.n_passengers
        expected = expected_mass(config, snap.n_passengers)
        assert snap.mass_kg == pytest.approx(expected)

    board(model, 300)
    snap = model.snapshot()
    check_bounds(snap)
    assert snap.n_passengers == config.capacity
    assert snap.outputs.track.passenger_capacity == 0

    disembarked = False
    for _ in range(20):
        before = model.snapshot().n_passengers
        model.step(DT_S, make_inputs(door_left=True))
        snap = model.snapshot()
        check_bounds(snap)
        disembarked = disembarked or snap.n_passengers < before
        model.step(DT_S, make_inputs(
            door_left=True, boarded=50, station="S"))
        check_bounds(model.snapshot())
        model.step(DT_S, make_inputs(door_left=False))
    # Twenty uniform draws from a full train are all zero only by a
    # vanishingly unlikely seed; the reported capacity must move.
    assert disembarked


@pytest.mark.parametrize(
    ("service", "emergency", "pulled", "failed", "expected"),
    [
        # expected is Brake State: (emergency, service) engaged.
        (False, False, False, False, (False, False)),
        (True, False, False, False, (False, True)),
        (False, True, False, False, (True, False)),
        # The emergency brake supersedes the service brake.
        (True, True, False, False, (True, False)),
        (False, False, True, False, (True, False)),
        (True, False, True, False, (True, False)),
        # Brake failure blocks the service brake only.
        (True, False, False, True, (False, False)),
        (False, True, False, True, (True, False)),
        (False, False, True, True, (True, False)),
        (True, True, True, True, (True, False)),
    ],
)
def test_brake_state_reports_engaged_brakes(
    service: bool,
    emergency: bool,
    pulled: bool,
    failed: bool,
    expected: tuple[bool, bool],
) -> None:
    """Check Brake State reports the engaged brakes, not the commands."""
    model = TrainModel(TrainConfig())
    model.set_failures(FailureState(brake=failed))
    if pulled:
        model.pull_passenger_emergency_brake()
    out = model.step(DT_S, make_inputs(
        service=service, emergency=emergency)).controller
    assert (out.emergency_brake_active, out.service_brake_active) == expected


def test_brake_state_matches_applied_force() -> None:
    """Check a reported brake is the one decelerating a moving train."""
    cfg = TrainConfig()
    for service, emergency, failed in [(True, False, False),
                                       (False, True, False),
                                       (True, False, True),
                                       (True, True, True)]:
        model = TrainModel(cfg)
        while model.snapshot().velocity_mps < 10.0:
            model.step(DT_S, make_inputs(power_w=cfg.p_max_w))
        model.set_failures(FailureState(brake=failed))
        for _ in range(3):
            outputs = model.step(DT_S, make_inputs(
                service=service, emergency=emergency))
        decel = -model.snapshot().acceleration_mps2
        mass = model.snapshot().mass_kg
        ctl = outputs.controller
        if ctl.emergency_brake_active:
            f_expected = cfg.f_emergency_n
        elif ctl.service_brake_active:
            f_expected = cfg.f_service_n
        else:
            f_expected = 0.0
        f_roll = cfg.c_rr * mass * cfg.g_mps2
        assert decel * mass == pytest.approx(f_expected + f_roll)


def test_light_state_reported() -> None:
    """Check each Light State element follows its own command."""
    model = TrainModel(TrainConfig())
    for interior, exterior in [(True, False), (False, True)]:
        out = model.step(DT_S, make_inputs(
            interior=interior, exterior=exterior)).controller
        assert out.interior_lights_on is interior
        assert out.exterior_lights_on is exterior


def script_input(tick: int) -> TrainModelInputs:
    """Return the scripted input for one position in a 500-tick run."""
    power_w = 0.0
    grade_deg = 0.0
    door_left = False
    boarded = 0
    emergency = False
    if tick < 40:
        # Door cycles while boarding to capacity at a station.
        door_left = tick % 2 == 0
        boarded = 56 if door_left else 0
    elif tick < 200:
        power_w = TrainConfig().p_max_w
    elif tick < 400:
        # Braking to rest on a grade.
        grade_deg = pct_to_deg(6.0)
        emergency = True
    else:
        # Relaunch against the grade.
        power_w = TrainConfig().p_max_w
        grade_deg = pct_to_deg(6.0)
    return make_inputs(
        power_w=power_w, service=False, emergency=emergency,
        grade_deg=grade_deg, boarded=boarded, door_left=door_left,
        station="S" if tick < 40 else None)


def run_scripted(model: TrainModel) -> tuple[list[TrainModelOutputs],
                                            list[TrainModelSnapshot]]:
    """Step a model through the scripted 500-tick input sequence."""
    outputs: list[TrainModelOutputs] = []
    snapshots: list[TrainModelSnapshot] = []
    for tick in range(500):
        inputs = script_input(tick)
        outputs.append(model.step(DT_S, inputs))
        snapshots.append(model.snapshot())
    return outputs, snapshots


def test_determinism() -> None:
    """Check seeded models replaying identical inputs stay identical."""
    first = run_scripted(TrainModel(TrainConfig(seed=42)))
    second = run_scripted(TrainModel(TrainConfig(seed=42)))
    assert first == second
