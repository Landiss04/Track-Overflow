"""The Green line, end to end through the module.

The Green line is the main line in use, so its layout, devices and the
whole course route are checked here explicitly. Expected values come from
``green_line.json`` and the course route: out of the yard at 63, up to
100, back through 85 to 77, out along 101 to 150, down from 28 to 1, back
up from 13 to 57, and into the yard.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

import pytest

from track_model.interface import (
    SignalAspect,
    SwitchPosition,
    TrackControllerCommands,
    TrackModelOutputs,
)
from track_model.layout import Layout, load_layout
from track_model.model import TrackModel
from tests.helpers import MODULE_DIR, DT_S, make_inputs, make_model, report

GREEN_PATH = str(MODULE_DIR / "green_line.json")
FAR_M = 100_000.0           # past the end of any block

NORMAL = SwitchPosition.NORMAL
REVERSE = SwitchPosition.REVERSE

#: Switch positions the Track Controller sets for one full course loop.
#: 85 and 77 are each passed twice, once trailing; 28 and 13 likewise.
ROUTE_SWITCHES: dict[str, SwitchPosition] = {
    "GREEN N-85": NORMAL,     # 84 -> 86 on the way out
    "GREEN N-77": REVERSE,    # 78 -> 101 on the way back
    "GREEN F-28": NORMAL,     # 27 -> 29 after the loop through 1
    "GREEN D-13": NORMAL,     # 14 -> 12 down to 1
    "GREEN I-57": REVERSE,    # 56 -> yard at the end
}

#: Block numbers of the full course loop, from the yard back to it.
COURSE_ROUTE: list[int] = (
    list(range(63, 101))          # yard -> 63 ... 100
    + list(range(85, 76, -1))     # 100 -> 85 ... 77
    + list(range(101, 151))       # 77 -> 101 ... 150
    + list(range(28, 0, -1))      # 150 -> 28 ... 1
    + list(range(13, 58))         # 1 -> 13 ... 57
)


@pytest.fixture(scope="module")
def green() -> Layout:
    """Return the Green line alone."""
    return load_layout([GREEN_PATH])


def gid(green: Layout, number: int) -> str:
    """Return the block ID of a Green block number."""
    return next(b.block_id for b in green.blocks.values()
                if b.number == number)


def run_route(
    model: TrackModel,
    start: str,
    commands: TrackControllerCommands,
    max_ticks: int = 400,
) -> tuple[list[str], list[TrackModelOutputs]]:
    """Drive T1 from ``start`` one block per tick until it leaves.

    Acts as the Train Model: each tick it reports the block the feed
    named, with an offset past that block's end.
    """
    out = model.step(DT_S, make_inputs({"T1": report(start, 1.0)},
                                       commands))
    path, history = [start], [out]
    for _ in range(max_ticks):
        block = path[-1]
        out = model.step(DT_S, make_inputs({"T1": report(block, FAR_M)}))
        history.append(out)
        feed = out.train_feeds.get("T1")
        if feed is None:
            path.append("YARD")
            break
        path.append(feed.track_info.block_id)
    return path, history


# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #

def test_green_has_150_blocks_in_order(green: Layout) -> None:
    """Check the block count, numbering and total length."""
    numbers = [b.number for b in green.blocks.values()]
    assert numbers == list(range(1, 151))
    total = sum(b.length_m for b in green.blocks.values())
    assert total == pytest.approx(14_552.6)


@pytest.mark.parametrize("number, expected_id", [
    (1, "GREEN A-1"), (13, "GREEN D-13"), (28, "GREEN F-28"),
    (57, "GREEN I-57"), (63, "GREEN K-63"), (77, "GREEN N-77"),
    (100, "GREEN Q-100"), (101, "GREEN R-101"), (150, "GREEN Z-150"),
])
def test_green_block_ids(green: Layout, number: int, expected_id: str) -> None:
    """Check the block ID format on key Green blocks."""
    assert gid(green, number) == expected_id


@pytest.mark.parametrize("block_id, grade_pct, limit_kmh, length_m", [
    ("GREEN A-1", 0.5, 45, 100.0),
    ("GREEN D-13", 0.0, 70, 150.0),
    ("GREEN Q-100", 0.0, 25, 75.0),
    ("GREEN Z-150", 0.0, 20, 35.0),
])
def test_green_units_converted(
    green: Layout, block_id: str, grade_pct: float, limit_kmh: float,
    length_m: float,
) -> None:
    """Check grade % -> deg and km/h -> m/s on Green blocks."""
    block = green.blocks[block_id]
    assert block.grade_deg == pytest.approx(
        math.degrees(math.atan(grade_pct / 100)))
    assert block.speed_limit_mps == pytest.approx(limit_kmh / 3.6)
    assert block.length_m == length_m


GREEN_STATIONS = [
    ("GREEN A-2", "PIONEER", "L", False),
    ("GREEN C-9", "EDGEBROOK", "L", False),
    ("GREEN F-22", "WHITED", "LR", False),
    ("GREEN G-31", "SOUTH BANK", "L", False),
    ("GREEN I-39", "CENTRAL", "R", True),
    ("GREEN I-48", "INGLEWOOD", "R", True),
    ("GREEN I-57", "OVERBROOK", "R", True),
    ("GREEN K-65", "GLENBURY", "R", False),
    ("GREEN L-73", "DORMONT", "R", False),
    ("GREEN N-77", "MT LEBANON", "LR", False),
    ("GREEN O-88", "POPLAR", "L", False),
    ("GREEN P-96", "CASTLE SHANNON", "L", False),
    ("GREEN T-105", "DORMONT", "R", False),
    ("GREEN U-114", "GLENBURY", "R", False),
    ("GREEN W-123", "OVERBROOK", "R", True),
    ("GREEN W-132", "INGLEWOOD", "L", True),
    ("GREEN W-141", "CENTRAL", "R", True),
]


def test_green_station_list(green: Layout) -> None:
    """Check every Green station block, and no others."""
    found = sorted(b.block_id for b in green.blocks.values()
                   if b.station_name is not None)
    assert found == sorted(s[0] for s in GREEN_STATIONS)


@pytest.mark.parametrize("block_id, name, side, underground", GREEN_STATIONS)
def test_green_station(
    green: Layout, block_id: str, name: str, side: str, underground: bool,
) -> None:
    """Check one Green station's name, platform side and underground flag."""
    block = green.blocks[block_id]
    assert (block.station_name, block.platform_side, block.underground) == (
        name, side, underground)


@pytest.mark.parametrize("station_block", [s[0] for s in GREEN_STATIONS])
def test_green_station_neighbours_carry_its_beacon(
    green: Layout, station_block: str,
) -> None:
    """Check each neighbour of a station block broadcasts that station."""
    station = green.blocks[station_block]
    for neighbour in green.neighbours[station_block]:
        if green.blocks[neighbour].station_name is not None:
            continue
        beacon = green.beacons[neighbour]
        assert beacon.station_name == station.station_name


def test_mt_lebanon_beacon_reaches_the_101_branch(green: Layout) -> None:
    """Check the beacon follows the switch leg 77 -> 101 too."""
    assert green.beacons["GREEN R-101"].station_name == "MT LEBANON"


@pytest.mark.parametrize("point, normal, reverse, from_yard", [
    ("GREEN D-13", "GREEN C-12", "GREEN A-1", False),
    ("GREEN F-28", "GREEN G-29", "GREEN Z-150", False),
    ("GREEN I-57", "GREEN J-58", None, False),
    ("GREEN K-63", "GREEN J-62", None, True),
    ("GREEN N-77", "GREEN M-76", "GREEN R-101", False),
    ("GREEN N-85", "GREEN O-86", "GREEN Q-100", False),
])
def test_green_switches(
    green: Layout, point: str, normal: str, reverse: str | None,
    from_yard: bool,
) -> None:
    """Check each Green switch's legs (None = yard)."""
    switch = green.switches[point]
    assert (switch.normal_block_id, switch.reverse_block_id,
            switch.from_yard) == (normal, reverse, from_yard)


def test_green_has_exactly_six_switches(green: Layout) -> None:
    """Check no switch is missing or invented."""
    assert len(green.switches) == 6


def test_green_signals_stand_before_each_switch(green: Layout) -> None:
    """Check the six Green signal blocks."""
    assert set(green.signal_block_ids) == {
        "GREEN D-14", "GREEN F-27", "GREEN I-56",
        "GREEN K-64", "GREEN N-78", "GREEN N-84",
    }


def test_green_crossings() -> None:
    """Check the two Green crossings report as gates up at start."""
    out = make_model().step(DT_S, make_inputs())
    green = {k: v for k, v in out.controller.crossing_states.items()
             if k.startswith("GREEN")}
    assert green == {"GREEN E-19": False, "GREEN T-108": False}


@pytest.mark.parametrize("a, b", [(100, 101), (150, 1), (57, 63)])
def test_green_unjoined_ends(green: Layout, a: int, b: int) -> None:
    """Check blocks that are numbered near each other but not joined."""
    assert gid(green, b) not in green.neighbours[gid(green, a)]


# --------------------------------------------------------------------------- #
# The course route
# --------------------------------------------------------------------------- #

def test_full_green_loop_follows_the_course_route() -> None:
    """Drive yard -> 63 ... 57 -> yard with the route's switch settings."""
    model = make_model()
    path, _ = run_route(
        model, "GREEN K-63",
        TrackControllerCommands(switch_commands=ROUTE_SWITCHES))
    numbers = [int(b.rsplit("-", 1)[1]) for b in path[:-1]]
    assert numbers == COURSE_ROUTE
    assert path[-1] == "YARD"


def test_occupancy_follows_the_train_round_the_loop() -> None:
    """Check exactly the train's block is occupied at every tick."""
    model = make_model()
    path, history = run_route(
        model, "GREEN K-63",
        TrackControllerCommands(switch_commands=ROUTE_SWITCHES))
    for block, out in zip(path, history):
        occupied = [b for b, o in out.controller.block_occupancy.items()
                    if o]
        assert occupied == ([] if block == "YARD" else [block])


def test_polarity_flips_at_every_green_block_change() -> None:
    """Check polarity alternates, including across 1 -> 13 and 150 -> 28."""
    model = make_model()
    _, history = run_route(
        model, "GREEN K-63",
        TrackControllerCommands(switch_commands=ROUTE_SWITCHES))
    polarities = [out.train_feeds["T1"].track_info.polarity
                  for out in history if "T1" in out.train_feeds]
    assert all(a != b for a, b in zip(polarities, polarities[1:]))


def test_switch_positions_never_change_on_their_own() -> None:
    """Check every switch reads back as commanded the whole loop."""
    model = make_model()
    _, history = run_route(
        model, "GREEN K-63",
        TrackControllerCommands(switch_commands=ROUTE_SWITCHES))
    for out in history:
        for switch_id, position in ROUTE_SWITCHES.items():
            assert out.controller.switch_states[switch_id] is position


def test_57_normal_stays_on_the_line_and_rejoins_at_63() -> None:
    """Check 57 NORMAL runs 58 ... 62 and trails through 63 to 64."""
    model = make_model()
    commands = TrackControllerCommands(switch_commands={"GREEN I-57": NORMAL})
    path, _ = run_route(model, "GREEN I-55", commands, max_ticks=10)
    numbers = [int(b.rsplit("-", 1)[1]) for b in path]
    assert numbers[:11] == [55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65]


def test_77_normal_sends_the_return_trip_to_76() -> None:
    """Check the other leg of 77 when the Track Controller sets NORMAL."""
    model = make_model()
    commands = TrackControllerCommands(switch_commands={"GREEN N-77": NORMAL})
    path, _ = run_route(model, "GREEN K-63", commands, max_ticks=60)
    numbers = [int(b.rsplit("-", 1)[1]) for b in path]
    after_100 = numbers[numbers.index(100) + 1:][:10]
    assert after_100 == [85, 84, 83, 82, 81, 80, 79, 78, 77, 76]


def test_new_train_at_63_heads_out_of_the_yard() -> None:
    """Check a train placed at the yard entry heads to 64, not 62."""
    model = make_model()
    model.step(DT_S, make_inputs({"T1": report("GREEN K-63", 1.0)}))
    out = model.step(DT_S, make_inputs({"T1": report("GREEN K-63", FAR_M)}))
    assert out.train_feeds["T1"].track_info.block_id == "GREEN K-64"


def test_train_out_of_the_yard_does_not_roll_back_into_it() -> None:
    """Check rollback at 63, straight out of the yard, stays at 63."""
    model = make_model()
    model.step(DT_S, make_inputs({"T1": report("GREEN K-63", 1.0)}))
    out = model.step(DT_S, make_inputs({"T1": report("GREEN K-63", -1.0)}))
    assert out.train_feeds["T1"].track_info.block_id == "GREEN K-63"


# --------------------------------------------------------------------------- #
# Track circuit, signals and stations along the route
# --------------------------------------------------------------------------- #

def test_per_block_speed_and_authority_round_the_loop(green: Layout) -> None:
    """Command every Green block differently; check what the train gets.

    Each block's commanded speed is its speed limit in whole m/s, and its
    authority is the block five numbers on.
    """
    speeds: Mapping[str, int] = {
        b.block_id: int(b.speed_limit_mps) for b in green.blocks.values()
    }
    authority = {
        b.block_id: gid(green, (b.number + 4) % 150 + 1)
        for b in green.blocks.values()
    }
    model = make_model()
    path, history = run_route(model, "GREEN K-63", TrackControllerCommands(
        commanded_speed_mps=speeds,
        commanded_authority=authority,
        switch_commands=ROUTE_SWITCHES,
    ))
    for block, out in zip(path[:-1], history):
        signal = out.train_feeds["T1"].track_signal
        assert signal.commanded_speed_mps == speeds[block]
        assert isinstance(signal.commanded_speed_mps, int)
        assert signal.authority_block_id == authority[block]


def test_signals_seen_once_on_entry_round_the_loop(green: Layout) -> None:
    """Check signal_seen fires on each signal-block entry, and only then."""
    aspects = dict(zip(
        green.signal_block_ids,
        [SignalAspect.GREEN, SignalAspect.YELLOW, SignalAspect.RED,
         SignalAspect.SUPER_GREEN, SignalAspect.YELLOW, SignalAspect.GREEN],
    ))
    model = make_model()
    path, history = run_route(model, "GREEN K-63", TrackControllerCommands(
        signal_commands=aspects, switch_commands=ROUTE_SWITCHES))
    seen = [out.signal_seen.get("T1") for out in history[:-1]]
    expected = [aspects.get(block) for block in path[:-1]]
    assert seen == expected
    # Each signal block is entered on this route: 64 once, the rest twice.
    entries = [b for b in path if b in aspects]
    assert sorted(entries) == sorted(
        ["GREEN K-64", "GREEN I-56"]
        + ["GREEN D-14", "GREEN F-27", "GREEN N-78", "GREEN N-84"] * 2
    )


@pytest.mark.parametrize("block_id, station", [
    ("GREEN A-2", "PIONEER"),
    ("GREEN I-39", "CENTRAL"),
    ("GREEN P-96", "CASTLE SHANNON"),
])
def test_boarding_at_green_stations(block_id: str, station: str) -> None:
    """Check a stopped train boards at a Green station, up to capacity."""
    model = make_model(ticket_probability=1.0)
    for _ in range(5):
        model.step(DT_S, make_inputs())
    out = model.step(DT_S, make_inputs(
        {"T1": report(block_id, 1.0, speed_mps=0.0, capacity=3)}))
    assert out.train_feeds["T1"].passengers_boarded == 3
    assert out.train_feeds["T1"].track_info.station_name == station


def test_two_trains_on_green_get_their_own_blocks_signal() -> None:
    """Check two trains in different blocks read different circuits."""
    out = make_model().step(DT_S, make_inputs(
        {"T1": report("GREEN K-65", 1.0), "T2": report("GREEN O-88", 1.0)},
        TrackControllerCommands(
            commanded_speed_mps={"GREEN K-65": 12, "GREEN O-88": 6},
            commanded_authority={"GREEN K-65": "GREEN L-73",
                                 "GREEN O-88": "GREEN P-96"}),
    ))
    t1 = out.train_feeds["T1"].track_signal
    t2 = out.train_feeds["T2"].track_signal
    assert (t1.commanded_speed_mps, t1.authority_block_id) == (
        12, "GREEN L-73")
    assert (t2.commanded_speed_mps, t2.authority_block_id) == (
        6, "GREEN P-96")
    occupied = {b for b, o in out.controller.block_occupancy.items() if o}
    assert occupied == {"GREEN K-65", "GREEN O-88"}
