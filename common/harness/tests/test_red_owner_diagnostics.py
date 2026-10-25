"""CTC-1 Red review plans and sequential seeded scheduler snapshots.

Real schedule loading and AutoDispatcher transitions are exercised here.
World heads are seeded; these tests establish neither continuous travel
nor physics/separation acceptance, and change no scheduler policy.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
for folder in (ROOT, ROOT / "CTC-Office"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from common.harness.tests.test_review_scenarios import (  # noqa: E402
    review_schedule,
)
from ctc.model import StubCtcOffice  # noqa: E402
from ctc.schedule import parse_schedule  # noqa: E402
from ctc.scheduler import (  # noqa: E402
    Cancel,
    DONE,
    DWELLING,
    HELD,
    IN_YARD,
    Order,
    Progress,
    SIMULATION_START_S,
    TO_YARD,
    World,
)

ZONE = "9"


def _dispatcher(count):
    """Load the shared review schedule's Red half through the model."""
    red = next(
        line
        for line in review_schedule(count)["lines"]
        if line["line"] == "Red"
    )
    ctc = StubCtcOffice()
    ctc.load_schedule(parse_schedule({"time_unit": "s", "lines": [red]}))
    return ctc._auto


def _world(offset_s, orders, heads=None):
    """Create one ready Red snapshot with no train reported lost."""
    return World(
        now_s=SIMULATION_START_S + offset_s,
        ready_lines=frozenset({"Red"}),
        heads=dict(heads or {}),
        orders=dict(orders),
        lost=frozenset(),
    )


def _carry(orders, actions):
    """Apply returned dispatch actions to the next World's order map."""
    for action in actions:
        if isinstance(action, Order):
            orders[action.train_id] = action.block_id
        else:
            assert isinstance(action, Cancel)
            del orders[action.train_id]


def _assert_owner(auto, owner):
    """Supplement public actions with the current zone owner."""
    assert [
        plan.train_id for plan in auto.plans if auto._holds(plan, ZONE)
    ] == [owner]


@pytest.mark.parametrize("count", [2, 3])
def test_review_red_plans_share_one_zone_through_yard(count):
    """The review schedule's full outbound/return path is zone 9."""
    auto = _dispatcher(count)
    assert [plan.train_id for plan in auto.plans] == [
        f"R{number}" for number in range(1, count + 1)
    ]
    assert [plan.departure_s for plan in auto.plans] == [
        SIMULATION_START_S + 180 * index for index in range(count)
    ]
    assert auto.zones["Red"] == {str(block): ZONE for block in range(9, 67)}
    for plan in auto.plans:
        assert len(plan.path) == 102
        assert plan.stop_indexes == (7,)
        assert plan.path[7] == plan.stops[0].block_id == "16"
        assert plan.yard_index == 101
        assert plan.path[101] == plan.yard_block_id == "9"
        assert auto._spans[plan.train_id] == ((ZONE, 0, 101),)


@pytest.mark.parametrize("count", [2, 3])
def test_review_red_follower_released_only_after_lead_is_done(count):
    """Carry five Worlds forward without overwriting run progress."""
    auto = _dispatcher(count)
    lead, follower = auto.plans[:2]
    orders = {}
    assert all(progress == Progress() for progress in auto.progress.values())

    # All departures are due, but R1's release claims the whole zone.
    actions = auto.step(_world(400, orders))
    assert actions == [Order("R1", "Red", "16", lead.stops[0].due_s)]
    _carry(orders, actions)
    assert orders == {"R1": "16"}
    assert auto.progress["R1"] == Progress(IN_YARD, leg=0, at=-1)
    assert auto._released_to(lead, auto.progress["R1"]) == 7
    _assert_owner(auto, "R1")
    for plan in auto.plans[1:]:
        progress = auto.progress[plan.train_id]
        assert progress == Progress(HELD, leg=0, at=-1)
        assert not auto._clear(plan, progress, plan.stop_indexes[0])

    # Seed the head at 16; arrival at +401 starts a 45 s dwell to +446.
    actions = auto.step(_world(401, orders, {"R1": "16"}))
    assert actions == []
    _carry(orders, actions)
    assert auto.progress["R1"] == Progress(
        DWELLING, leg=0, dwell_until_s=SIMULATION_START_S + 446, at=7
    )
    _assert_owner(auto, "R1")
    assert all(
        auto.progress[plan.train_id] == Progress(HELD)
        for plan in auto.plans[1:]
    )

    actions = auto.step(_world(446, orders, {"R1": "16"}))
    assert actions == [Order("R1", "Red", "9", lead.stops[0].due_s + 45)]
    _carry(orders, actions)
    assert orders == {"R1": "9"}
    assert auto.progress["R1"] == Progress(TO_YARD, leg=1, at=7)
    assert auto._released_to(lead, auto.progress["R1"]) == 101
    _assert_owner(auto, "R1")
    assert all(
        auto.progress[plan.train_id] == Progress(HELD)
        for plan in auto.plans[1:]
    )

    # Forward location search must select the final 9, not index 0.
    actions = auto.step(_world(447, orders, {"R1": "9"}))
    assert actions == []
    _carry(orders, actions)
    assert auto.progress["R1"] == Progress(TO_YARD, leg=1, at=101)
    _assert_owner(auto, "R1")
    assert all(
        auto.progress[plan.train_id] == Progress(HELD)
        for plan in auto.plans[1:]
    )
    assert not auto._clear(follower, auto.progress["R2"], 7)

    # Absence without a lost report completes R1 and releases R2.
    actions = auto.step(_world(448, orders))
    assert actions == [
        Cancel("R1"),
        Order("R2", "Red", "16", follower.stops[0].due_s),
    ]
    _carry(orders, actions)
    assert orders == {"R2": "16"}
    assert auto.progress["R1"] == Progress(DONE, leg=1, at=101)
    assert auto.progress["R2"] == Progress(IN_YARD, leg=0, at=-1)
    assert auto._released_to(follower, auto.progress["R2"]) == 7
    _assert_owner(auto, "R2")
    assert auto._clear(follower, auto.progress["R2"], 7)
    if count == 3:
        assert auto.progress["R3"] == Progress(HELD, leg=0, at=-1)
        assert not auto._clear(auto.plans[2], auto.progress["R3"], 7)
