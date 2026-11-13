"""A refused TrainCore STEP leaves the whole fleet as it was."""

import pickle

import pytest
from common.hw_link.cores import TrainCore


def good(speed=1.0):
    return {
        "actual_speed": speed,
        "commanded_speed": 10.0,
        "authority_blocks": 3,
        "emergency_brake_state": False,
        "service_brake_state": False,
        "door_state": [False, False],
        "light_state": [False, False],
        "cabin_temperature": 22.0,
    }


def request(trains, tick=1, dt=0.1, time_s=18000.0):
    return {
        "dt": dt,
        "tick": tick,
        "sim_time_s": time_s,
        "inputs": {
            "trains": {
                key: {"line": "Red", "inputs": values}
                for key, values in trains.items()
            }
        },
    }


def fleet_bytes(core):
    return pickle.dumps(core.fleet)


@pytest.fixture
def core():
    core = TrainCore()
    core.step(request({"R1": good(), "R2": good(2.0), "R3": good(3.0)}))
    core.step(request({"R1": good(), "R2": good(2.0), "R3": good(3.0)}, 2))
    return core


def test_accepted_step_changes_the_fleet(core):
    before = fleet_bytes(core)
    core.step(request({"R1": good(), "R2": good(), "R3": good()}, 3))
    assert fleet_bytes(core) != before


def bad_input(trains):
    trains["R2"] = dict(good(), light_state=[False])
    return trains


def missing_signal(trains):
    del trains["R1"]["actual_speed"]
    return trains


# Each case changes the roster too (R3 leaves, R4 joins, R1 and R2 stay),
# so a rollback that forgot the roster would show.
@pytest.mark.parametrize(
    "break_it, kwargs",
    [
        (bad_input, {}),
        (missing_signal, {}),
        (lambda trains: trains, {"dt": 0.5}),
        (lambda trains: trains, {"time_s": -1.0}),
    ],
)
def test_refused_step_leaves_roster_order_and_every_train(
    core, break_it, kwargs
):
    before = fleet_bytes(core)
    order = core.fleet.ids()
    trains = break_it({"R2": good(), "R4": good(), "R1": good()})
    with pytest.raises(Exception):
        core.step(request(trains, 3, **kwargs))
    assert core.fleet.ids() == order
    assert fleet_bytes(core) == before


def test_the_next_good_step_after_a_refusal_matches_one_with_none(core):
    twin = pickle.loads(pickle.dumps(core))
    trains = {"R1": good(), "R2": good(2.5), "R3": good(), "R4": good()}
    with pytest.raises(Exception):
        core.step(request(bad_input(dict(trains)), 3))
    assert core.step(request(trains, 3)) == twin.step(request(trains, 3))
    assert core.view() == twin.view()
