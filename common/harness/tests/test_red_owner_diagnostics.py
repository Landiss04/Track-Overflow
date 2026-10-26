"""CTC-1 Red review plans and sequential seeded scheduler snapshots.

Real schedule loading and AutoDispatcher transitions are exercised here.
World heads are seeded; these tests establish neither continuous travel
nor physics/separation acceptance. They check the reservation rule Landis
decided on 2026-10-25: zone 9 (9…52) is reserved by direction, the loop
53…66 is one way, a turned train waits round the loop (at 65, clear of
switch 52) for its followers, and no train goes out while one waits to
come back or until a returning train has retired.
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
    QUEUED,
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


def _where(auto, train_id):
    """A run's status, leg, place along its path and place to wait."""
    progress = auto.progress[train_id]
    return progress.status, progress.leg, progress.at, progress.wait


def _holders(auto):
    """The runs on, or sent on, a pass through zone 9."""
    return [
        plan.train_id
        for plan in auto.plans
        if auto._held_spans(plan, ZONE)
    ]


@pytest.mark.parametrize("count", [2, 3])
def test_review_red_plans_out_and_back_over_zone_9(count):
    """Out 9…52, round the loop one way, back 52…9."""
    auto = _dispatcher(count)
    assert [plan.train_id for plan in auto.plans] == [
        f"R{number}" for number in range(1, count + 1)
    ]
    assert [plan.departure_s for plan in auto.plans] == [
        SIMULATION_START_S + 180 * index for index in range(count)
    ]
    assert auto.zones["Red"] == {str(block): ZONE for block in range(9, 53)}
    for plan in auto.plans:
        assert len(plan.path) == 102
        assert plan.path[:8] == tuple(str(n) for n in range(9, 17))
        assert plan.stop_indexes == (7,)
        assert plan.path[7] == plan.stops[0].block_id == "16"
        assert plan.path[44:58] == tuple(str(n) for n in range(53, 67))
        assert plan.yard_index == 101
        assert plan.path[101] == plan.yard_block_id == "9"
        assert auto._spans[plan.train_id] == ((ZONE, 0, 43), (ZONE, 58, 101))


@pytest.mark.parametrize("count", [2, 3])
def test_review_red_trains_go_out_together(count):
    """All due runs go out the same way; the lead waits round the loop."""
    auto = _dispatcher(count)
    lead, follower = auto.plans[:2]
    wait = lead.path.index("65")
    orders = {}

    # All departures are due and all go the same way: all are sent.
    actions = auto.step(_world(400, orders))
    assert actions == [
        Order(plan.train_id, "Red", "16", plan.stops[0].due_s)
        for plan in auto.plans
    ]
    _carry(orders, actions)
    assert all(
        progress == Progress(IN_YARD, leg=0, at=-1)
        for progress in auto.progress.values()
    )
    assert _holders(auto) == [plan.train_id for plan in auto.plans]

    actions = auto.step(_world(401, orders, {"R1": "16"}))
    assert actions == []
    assert auto.progress["R1"] == Progress(
        DWELLING, leg=0, dwell_until_s=SIMULATION_START_S + 446, at=7
    )

    # R1's dwell is up, but R2 is still on its way out behind it: R1 is
    # ordered on to the yard, with its authority stopping at 65, a block
    # short of the loop's end at 66 (by switch 52), where it waits.
    actions = auto.step(_world(446, orders, {"R1": "16", "R2": "12"}))
    assert actions == [Order("R1", "Red", "9", lead.stops[0].due_s + 45)]
    _carry(orders, actions)
    assert _where(auto, "R1") == (HELD, 1, 7, wait)
    assert auto.hold_at("R1") == "65"
    # On its way round, it is not yet waiting to come back.
    assert auto._waiting_span(lead) is None

    # Waiting there, it holds nothing; the order is not given again.
    actions = auto.step(_world(447, orders, {"R1": "65", "R2": "16"}))
    assert actions == []
    assert _where(auto, "R1") == (HELD, 1, wait, wait)
    assert auto._waiting_span(lead) == (ZONE, 58, 101)
    assert "R1" not in _holders(auto)
    assert "R2" in _holders(auto)

    # The followers are round the loop too: R1 comes back, and each
    # follower after it once it is at 65 in turn.
    for offset, plan in enumerate(auto.plans[1:], start=1):
        auto.progress[plan.train_id] = Progress(
            HELD, leg=1, at=wait - offset, wait=wait
        )
    heads = {
        plan.train_id: plan.path[wait - index]
        for index, plan in enumerate(auto.plans)
    }
    actions = auto.step(_world(600, orders, heads))
    assert actions == [Order("R1", "Red", "9", lead.stops[0].due_s + 45)]
    _carry(orders, actions)
    assert auto.progress["R1"].status == TO_YARD
    for step, plan in enumerate(auto.plans[1:], start=1):
        # Those already coming back are a block further on each step.
        heads = {
            ahead.train_id: ahead.path[wait + step - index]
            for index, ahead in enumerate(auto.plans[:step])
        }
        heads[plan.train_id] = "65"
        actions = auto.step(_world(600 + step, orders, heads))
        assert actions == [
            Order(plan.train_id, "Red", "9", plan.stops[0].due_s + 45)
        ]
        _carry(orders, actions)
        assert auto.progress[plan.train_id].status == TO_YARD
    assert follower.train_id in _holders(auto)


def test_review_red_no_train_out_while_one_waits_to_come_back():
    """R3 is due, but R1 waits round the loop: R3 stays in the yard."""
    auto = _dispatcher(3)
    lead = auto.plans[0]
    wait = lead.path.index("65")
    auto.progress["R1"] = Progress(HELD, leg=1, at=wait, wait=wait)
    auto.progress["R2"] = Progress(DWELLING, leg=0, at=7,
                                   dwell_until_s=SIMULATION_START_S + 900)
    orders = {"R1": "9", "R2": "16"}
    actions = auto.step(_world(400, orders, {"R1": "65", "R2": "16"}))
    assert actions == []
    assert auto.progress["R3"] == Progress(HELD, leg=0, at=-1)
    assert auto.progress["R1"].status == HELD


def test_review_red_yard_block_held_until_retired():
    """A returning train holds zone 9 inbound until it is back in the
    yard; only then does the next run go out."""
    auto = _dispatcher(2)
    lead, follower = auto.plans
    auto.progress["R1"] = Progress(TO_YARD, leg=1, at=lead.yard_index)
    orders = {"R1": "9"}
    actions = auto.step(_world(400, orders, {"R1": "9"}))
    assert actions == []
    assert auto.progress["R2"] == Progress(HELD, leg=0, at=-1)
    assert _holders(auto) == ["R1"]

    # Its block clears without a lost report: done, and R2 goes out.
    actions = auto.step(_world(401, orders))
    assert actions == [
        Cancel("R1"),
        Order("R2", "Red", "16", follower.stops[0].due_s),
    ]
    assert auto.progress["R1"] == Progress(DONE, leg=1, at=lead.yard_index)
    assert auto.progress["R2"] == Progress(IN_YARD, leg=0, at=-1)
    assert QUEUED not in {p.status for p in auto.progress.values()}
