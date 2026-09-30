"""Physics tests for whatever sits at ``train_model.model.TrainModel``.

The model is treated as a black box: only the public protocol and the
``TrainConfig`` properties are consulted, never the implementation.
Expectations are computed from the configuration wherever possible; the
literals in test 1 and test 3 are the datasheet design values themselves.
"""

from __future__ import annotations

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


def make_inputs(
    power_w: float = 0.0,
    service: bool = False,
    emergency: bool = False,
    grade_percent: float = 0.0,
    boarded: int = 0,
    door_left: bool = False,
    polarity: bool = True,
) -> TrainModelInputs:
    """Return the standard input set with the named overrides applied."""
    return TrainModelInputs(
        controller=ControllerCommands(
            power_cmd_w=power_w,
            service_brake=service,
            emergency_brake=emergency,
            interior_lights=False,
            exterior_lights=False,
            door_left_open=door_left,
            door_right_open=False,
            temp_setpoint_f=70.0,
            announcement="",
        ),
        track=TrackInputs(
            track_info=TrackInfo(
                block_id="A1",
                grade_percent=grade_percent,
                elevation_m=0.0,
                speed_limit_mps=19.0,
                polarity=polarity,
            ),
            track_signal=TrackSignal(
                commanded_speed_mps=10.0,
                authority_block_id="A9",
            ),
            beacon=None,
            passengers_boarded=boarded,
        ),
    )


def board(model: TrainModel, n: int) -> None:
    """Board ``n`` passengers in a single unpowered tick."""
    model.step(DT_S, make_inputs(boarded=n))


def run_until_speed(
    model: TrainModel, target_mps: float, grade_percent: float = 0.0
) -> None:
    """Step at full power until the velocity reaches ``target_mps``."""
    for _ in range(5000):
        if model.snapshot().velocity_mps >= target_mps:
            return
        model.step(DT_S, make_inputs(
            power_w=model.config.p_max_w, grade_percent=grade_percent))
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
    assert config.m_ref_kg == pytest.approx(52_312, abs=1.0)
    assert config.f_max_n == pytest.approx(26_156, abs=1.0)
    assert config.f_service_n == pytest.approx(62_774, abs=1.0)
    assert config.f_emergency_n == pytest.approx(142_812, abs=1.0)


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
    """Check the full train creeps at 4.3 percent grade but not 4.5."""
    config = TrainConfig()
    model = TrainModel(config)
    board(model, config.capacity)
    for _ in range(200):
        model.step(DT_S, make_inputs(
            power_w=config.p_max_w, grade_percent=4.3))
    assert model.snapshot().velocity_mps > 0.0

    model = TrainModel(config)
    board(model, config.capacity)
    for _ in range(1000):
        model.step(DT_S, make_inputs(
            power_w=config.p_max_w, grade_percent=4.5))
        assert model.snapshot().velocity_mps == 0.0


def test_service_brake_holds_full_train_on_6_percent() -> None:
    """Check the service brake holds a full train on a 6 percent grade."""
    config = TrainConfig()
    model = TrainModel(config)
    board(model, config.capacity)
    for _ in range(1000):
        model.step(DT_S, make_inputs(service=True, grade_percent=6.0))
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
        model.step(DT_S, make_inputs(service=True, grade_percent=6.0))
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
        assert model_off.snapshot() == model_on.snapshot()
        assert model_off.snapshot().velocity_mps == 0.0


def test_all_failures_compose() -> None:
    """Check all three failures leave only rolling resistance acting."""
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
            power_w=config.p_max_w, service=True, emergency=True))
        accel = model.snapshot().acceleration_mps2
        assert accel == pytest.approx(expected_accel, rel=1e-9)
        assert outputs.controller.commanded_speed_mps == 0.0
        assert outputs.controller.authority_block_id is None
        assert outputs.controller.failures == FailureState(True, True, True)


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
        model.step(DT_S, make_inputs(door_left=False, boarded=50))
        check_bounds(model.snapshot())
    # Twenty uniform draws from a full train are all zero only by a
    # vanishingly unlikely seed; the reported capacity must move.
    assert disembarked


def test_brake_and_light_state_reported() -> None:
    """Check Brake State and Light State reflect each command."""
    model = TrainModel(TrainConfig())
    for service, emergency in [(False, False), (True, False),
                               (False, True), (True, True)]:
        out = model.step(DT_S, make_inputs(
            service=service, emergency=emergency)).controller
        assert out.service_brake_active is service
        assert out.emergency_brake_active is emergency

    base = make_inputs()
    for interior, exterior in [(True, False), (False, True)]:
        ctl = base.controller
        inputs = TrainModelInputs(
            controller=ControllerCommands(
                power_cmd_w=ctl.power_cmd_w,
                service_brake=ctl.service_brake,
                emergency_brake=ctl.emergency_brake,
                interior_lights=interior,
                exterior_lights=exterior,
                door_left_open=ctl.door_left_open,
                door_right_open=ctl.door_right_open,
                temp_setpoint_f=ctl.temp_setpoint_f,
                announcement=ctl.announcement,
            ),
            track=base.track,
        )
        out = model.step(DT_S, inputs).controller
        assert out.interior_lights_on is interior
        assert out.exterior_lights_on is exterior

    model.pull_passenger_emergency_brake()
    out = model.step(DT_S, make_inputs()).controller
    assert out.emergency_brake_active is True
    assert out.service_brake_active is False


def script_input(tick: int) -> TrainModelInputs:
    """Return the scripted input for one position in a 500-tick run."""
    power_w = 0.0
    grade_percent = 0.0
    door_left = False
    boarded = 0
    emergency = False
    if tick < 40:
        # Door cycles while boarding to capacity.
        door_left = tick % 2 == 0
        boarded = 56 if not door_left else 0
    elif tick < 200:
        power_w = TrainConfig().p_max_w
    elif tick < 400:
        # Braking to rest on a grade.
        grade_percent = 6.0
        emergency = True
    else:
        # Relaunch against the grade.
        power_w = TrainConfig().p_max_w
        grade_percent = 6.0
    return make_inputs(
        power_w=power_w, service=False, emergency=emergency,
        grade_percent=grade_percent, boarded=boarded, door_left=door_left)


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
