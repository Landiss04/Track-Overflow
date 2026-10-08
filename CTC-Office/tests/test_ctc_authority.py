"""Tests for authority as a count of blocks (D013) and how the CTC
Office shortens it for what lies ahead.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ctc.interface import (  # noqa: E402
    BlockOccupancy,
    CtcInputs,
    SwitchReport,
    TrackControllerInputs,
    TrackFailureReport,
    TrainAuthority,
    TrainReport,
)
from ctc.model import StubCtcOffice  # noqa: E402
from ctc.routing import (  # noqa: E402
    TrackGraph,
    authority,
    first_reversal,
    reversing_route,
)
from ctc.track_layout import Line, load_layout, load_line  # noqa: E402

DT_S = 0.1
_LAYOUT = load_layout()
_GREEN = TrackGraph(_LAYOUT["Green"])
_RED = TrackGraph(_LAYOUT["Red"])
# Green 30 to 37: ascending blocks with no switch between them.
_GREEN_30_TO_37 = tuple(str(n) for n in range(30, 38))


def _inputs(*trains: TrainReport, occupancy=(), switches=(),
            failures=()) -> CtcInputs:
    return CtcInputs(track_controller=TrackControllerInputs(
        trains=trains, occupancy=occupancy, switches=switches,
        failures=failures))


def _train(train_id: str, block_id: str, line: str = "Green") -> TrainReport:
    return TrainReport(train_id, line, block_id, 0.0, 0.0)


def _authority(ctc: StubCtcOffice, train_id: str = "T1") -> TrainAuthority:
    (found,) = [a for a in ctc.snapshot().authorities
                if a.train_id == train_id]
    return found


class TrackGraphTest(unittest.TestCase):
    """Connections read from the layout files."""

    def test_neighbouring_blocks_are_joined(self) -> None:
        self.assertEqual(_GREEN.neighbors("5"), ("4", "6"))

    def test_switches_join_their_connections(self) -> None:
        self.assertEqual(_GREEN.neighbors("13"), ("1", "12", "14"))
        self.assertEqual(_GREEN.neighbors("28"), ("27", "29", "150"))
        self.assertEqual(_RED.neighbors("27"), ("26", "28", "76"))

    def test_far_ends_of_switches_are_not_joined(self) -> None:
        # Green 100 joins 85 and 101 joins 77; they are not neighbours.
        self.assertEqual(_GREEN.neighbors("100"), ("85", "99"))
        self.assertEqual(_GREEN.neighbors("101"), ("77", "102"))
        self.assertEqual(_RED.neighbors("66"), ("52", "65"))
        self.assertEqual(_RED.neighbors("67"), ("44", "68"))
        self.assertEqual(_RED.neighbors("71"), ("38", "70"))
        self.assertEqual(_RED.neighbors("72"), ("33", "73"))

    def test_yard_connections_are_left_out(self) -> None:
        self.assertEqual(_GREEN.neighbors("57"), ("56", "58"))
        self.assertEqual(_GREEN.neighbors("63"), ("62", "64"))

    def test_switch_positions(self) -> None:
        normal, reverse = _GREEN.leg("12", "13"), _GREEN.leg("1", "13")
        assert normal is not None and reverse is not None
        self.assertEqual((normal.switch_id, normal.position),
                         ("12", "normal"))
        self.assertEqual((reverse.switch_id, reverse.position),
                         ("12", "reverse"))
        self.assertIsNone(_GREEN.leg("5", "6"))

    def test_a_route_never_turns_back_through_a_switch(self) -> None:
        # 12 -> 13 -> 1 would be shorter, but a train cannot pass from
        # one connection of switch 12 into the other.
        route = _GREEN.route("12", "1")
        assert route is not None
        self.assertEqual(route[:3], ("12", "11", "10"))
        self.assertEqual(route[-1], "1")


def _line_from(blocks: list[dict]) -> Line:
    """A line read from a layout file holding ``blocks``."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "line.json"
        path.write_text(json.dumps({"line": "Test", "blocks": [
            {"block_number": n, "section": "A", "length_m": 100,
             "speed_limit_kmh": 50, **extra}
            for n, extra in blocks]}), encoding="utf-8")
        return load_line("Test", path)


class NextBlocksTest(unittest.TestCase):
    """``next_blocks`` in the layout files."""

    def test_read_with_the_yard_apart(self) -> None:
        line = _line_from([(1, {"next_blocks": [2]}),
                           (2, {"next_blocks": [3, "yard"]}),
                           (3, {"next_blocks": []})])
        first, second, _ = line.blocks
        self.assertEqual(first.next_blocks, ("2",))
        self.assertEqual((second.next_blocks, second.to_yard),
                         (("3",), True))

    def test_only_listed_moves_are_run(self) -> None:
        graph = TrackGraph(_line_from([(1, {"next_blocks": [2]}),
                                       (2, {"next_blocks": [3]}),
                                       (3, {"next_blocks": []})]))
        self.assertEqual(graph.route("1", "3"), ("1", "2", "3"))
        self.assertIsNone(graph.route("3", "1"))

    def test_without_next_blocks_both_ways(self) -> None:
        graph = TrackGraph(_line_from([(1, {}), (2, {}), (3, {})]))
        self.assertEqual(graph.route("3", "1"), ("3", "2", "1"))

    def test_a_next_block_the_layout_does_not_join_is_refused(self) -> None:
        line = _line_from([(1, {"next_blocks": [3]}), (2, {}), (3, {})])
        with self.assertRaisesRegex(ValueError, "does not join"):
            TrackGraph(line)


class DirectionTest(unittest.TestCase):
    """Direction of travel from the layout files."""

    def test_switch_far_blocks_join_at_the_right_end(self) -> None:
        # Green 1 joins 13 where 12 does: 13's low end.
        self.assertEqual(_GREEN.end("13", "1"), "low")
        self.assertEqual(_GREEN.end("13", "12"), "low")
        self.assertEqual(_GREEN.end("28", "150"), "high")
        self.assertEqual(_GREEN.end("100", "85"), "high")
        self.assertEqual(_GREEN.end("101", "77"), "low")

    def test_one_way_blocks_run_one_way(self) -> None:
        # A to C run 12 -> 1 only, then on to 13.
        self.assertTrue(_GREEN.can_run("2", "1"))
        self.assertFalse(_GREEN.can_run("1", "2"))
        self.assertTrue(_GREEN.can_run("1", "13"))
        self.assertFalse(_GREEN.can_run("13", "1"))
        # Q runs into N at 85, never the other way.
        self.assertTrue(_GREEN.can_run("100", "85"))
        self.assertFalse(_GREEN.can_run("85", "100"))
        # D to F run both ways.
        self.assertTrue(_GREEN.can_run("20", "21"))
        self.assertTrue(_GREEN.can_run("21", "20"))

    def test_the_green_loop(self) -> None:
        route = _GREEN.route("63", "62")
        assert route is not None
        expected = [*range(63, 101), *range(85, 76, -1), *range(101, 151),
                    *range(28, 12, -1), *range(12, 0, -1),
                    *range(13, 63)]
        self.assertEqual(route, tuple(str(n) for n in expected))

    def test_no_way_back_against_one_way_track(self) -> None:
        # Green 1 to 6 runs all the way round, not 1 -> 2 -> ... 6.
        route = _GREEN.route("1", "6")
        assert route is not None
        self.assertEqual(route[:2], ("1", "13"))
        self.assertGreater(len(route), 150)

    def test_red_runs_both_ways(self) -> None:
        self.assertEqual(_RED.route("5", "3"), ("5", "4", "3"))
        self.assertEqual(_RED.route("3", "5"), ("3", "4", "5"))


class CountTest(unittest.TestCase):
    """``ctc.routing.authority`` on its own."""

    def test_counts_the_blocks_ahead_to_the_destination(self) -> None:
        limit = authority(_GREEN, "30", "37", {}, {})
        self.assertEqual((limit.blocks, limit.end_block_id, limit.reason),
                         (7, "37", "destination"))

    def test_zero_at_the_destination(self) -> None:
        limit = authority(_GREEN, "37", "37", {}, {})
        self.assertEqual((limit.blocks, limit.end_block_id), (0, "37"))

    def test_carries_the_route_it_counted_along(self) -> None:
        limit = authority(_GREEN, "30", "37", {"32": "occupied"}, {})
        self.assertEqual(limit.route, _GREEN_30_TO_37)
        self.assertEqual(authority(_GREEN, "30", "37", {}, {}).route,
                         _GREEN_30_TO_37)

    def test_stops_before_an_obstruction(self) -> None:
        limit = authority(_GREEN, "30", "37", {"32": "occupied"}, {})
        self.assertEqual((limit.blocks, limit.end_block_id, limit.reason,
                          limit.at), (1, "31", "occupied", "32"))

    def test_own_block_is_not_an_obstruction(self) -> None:
        limit = authority(_GREEN, "30", "37", {"30": "occupied"}, {})
        self.assertEqual(limit.blocks, 7)

    def test_stops_before_a_switch_not_set_for_the_route(self) -> None:
        # Green 26 to 30 runs 28 -> 29: switch 28's normal connection.
        for switches in ({}, {"28": "reverse"}):
            with self.subTest(switches=switches):
                limit = authority(_GREEN, "26", "30", {}, switches)
                self.assertEqual((limit.blocks, limit.end_block_id,
                                  limit.reason, limit.at),
                                 (2, "28", "switch", "28"))
        limit = authority(_GREEN, "26", "30", {}, {"28": "normal"})
        self.assertEqual((limit.blocks, limit.reason), (4, "destination"))


class StubAuthorityTest(unittest.TestCase):
    """The stub recomputes authority from the reports every step."""

    def test_a_train_ahead_shortens_authority_until_it_moves(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "37")
        out = ctc.step(DT_S, _inputs(_train("T1", "30"),
                                     _train("T2", "32")))
        (suggestion,) = out.track_controller.suggestions
        self.assertEqual(suggestion.authority_blocks, 1)
        self.assertEqual(_authority(ctc), TrainAuthority(
            "T1", "Green", 1, "31", "occupied", "32", _GREEN_30_TO_37))
        # T2 moves on, past the destination: the authority grows back.
        out = ctc.step(DT_S, _inputs(_train("T1", "30"),
                                     _train("T2", "38")))
        self.assertEqual(
            out.track_controller.suggestions[0].authority_blocks, 7)

    def test_occupancy_without_a_train_report_counts(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "37")
        ctc.step(DT_S, _inputs(_train("T1", "30"), occupancy=(
            BlockOccupancy("Green", "34", True),)))
        self.assertEqual(_authority(ctc).blocks, 3)

    def test_a_closed_block_shortens_authority_until_reopened(self) -> None:
        ctc = StubCtcOffice()
        ctc.set_maintenance_mode(True)
        ctc.dispatch("T1", "Green", "37")
        ctc.step(DT_S, _inputs(_train("T1", "30")))
        ctc.set_block_closed("Green", "35", True)
        self.assertEqual(_authority(ctc), TrainAuthority(
            "T1", "Green", 4, "34", "closed", "35", _GREEN_30_TO_37))
        self.assertEqual(ctc.snapshot().outputs.track_controller
                         .suggestions[0].authority_blocks, 4)
        ctc.set_block_closed("Green", "35", False)
        self.assertEqual(_authority(ctc).blocks, 7)

    def test_a_closing_block_shortens_authority(self) -> None:
        ctc = StubCtcOffice()
        ctc.set_maintenance_mode(True)
        ctc.dispatch("T1", "Green", "37")
        ctc.step(DT_S, _inputs(_train("T1", "30"), _train("T2", "33")))
        ctc.set_block_closed("Green", "33", True)
        limit = _authority(ctc)
        self.assertEqual((limit.blocks, limit.reason, limit.at),
                         (2, "closing", "33"))

    def test_a_failed_block_shortens_authority(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "37")
        ctc.step(DT_S, _inputs(_train("T1", "30"), failures=(
            TrackFailureReport("Green", "36", "broken_rail"),)))
        limit = _authority(ctc)
        self.assertEqual((limit.blocks, limit.reason, limit.at),
                         (5, "failed", "36"))

    def test_switches_count_only_as_reported(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "30")
        ctc.step(DT_S, _inputs(_train("T1", "26")))
        self.assertEqual(_authority(ctc).blocks, 2)
        # A command is not a report: still stops before the switch.
        ctc.set_maintenance_mode(True)
        ctc.set_switch("Green", "28", "normal")
        self.assertEqual(_authority(ctc).blocks, 2)
        ctc.step(DT_S, _inputs(_train("T1", "26"), switches=(
            SwitchReport("Green", "28", "normal"),)))
        self.assertEqual(_authority(ctc).blocks, 4)

    def test_zero_once_at_the_destination(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "37")
        ctc.step(DT_S, _inputs(_train("T1", "37")))
        self.assertEqual(_authority(ctc), TrainAuthority(
            "T1", "Green", 0, "37", "destination", route=("37",)))

    def test_zero_on_another_line_than_the_order(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "37")
        ctc.step(DT_S, _inputs(_train("T1", "37", line="Red")))
        self.assertEqual(_authority(ctc), TrainAuthority(
            "T1", "Red", 0, "37", "no route"))

    def test_no_authority_before_the_train_is_on_the_track(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "37")
        ctc.step(DT_S, CtcInputs())
        self.assertEqual(ctc.snapshot().authorities, ())


class ExclusiveAuthorityTest(unittest.TestCase):
    """No block within two trains' authorities (exclusive-authority)."""

    def _head_on(self) -> StubCtcOffice:
        # Green 20 to 24 and 28 to 24 face each other on F, which runs
        # both ways: both want 24.
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "24")
        ctc.dispatch("T2", "Green", "24")
        return ctc

    def test_a_contested_block_goes_to_one_train(self) -> None:
        ctc = self._head_on()
        ctc.step(DT_S, _inputs(_train("T1", "20"), _train("T2", "28")))
        t1, t2 = _authority(ctc, "T1"), _authority(ctc, "T2")
        # No arrival times: T1 first, by train ID.
        self.assertEqual((t1.blocks, t1.reason), (4, "destination"))
        self.assertEqual((t2.blocks, t2.reason, t2.at, t2.held_by),
                         (3, "reserved", "24", "T1"))
        ahead = set(t1.route[1:t1.blocks + 1])
        self.assertFalse(ahead & set(t2.route[1:t2.blocks + 1]))

    def test_the_train_most_behind_schedule_goes_first(self) -> None:
        ctc = self._head_on()
        ctc.dispatch("T2", "Green", "24", arrival_s=8 * 3600)
        ctc.step(DT_S, _inputs(_train("T1", "20"), _train("T2", "28")))
        self.assertEqual(_authority(ctc, "T2").blocks, 4)
        t1 = _authority(ctc, "T1")
        self.assertEqual((t1.blocks, t1.reason, t1.held_by),
                         (3, "reserved", "T2"))

    def test_less_slack_goes_first(self) -> None:
        ctc = self._head_on()
        ctc.dispatch("T1", "Green", "24", arrival_s=9 * 3600)
        ctc.dispatch("T2", "Green", "24", arrival_s=8 * 3600)
        ctc.step(DT_S, _inputs(_train("T1", "20"), _train("T2", "28")))
        self.assertEqual(_authority(ctc, "T2").reason, "destination")
        self.assertEqual(_authority(ctc, "T1").held_by, "T2")

    def test_a_granted_block_is_kept(self) -> None:
        ctc = self._head_on()
        reports = _inputs(_train("T1", "20"), _train("T2", "28"))
        ctc.step(DT_S, reports)
        # T2 becomes more urgent, but T1 already holds 21 to 24.
        ctc.dispatch("T2", "Green", "24", arrival_s=5 * 3600)
        ctc.step(DT_S, reports)
        self.assertEqual(_authority(ctc, "T1").blocks, 4)
        self.assertEqual(_authority(ctc, "T2").held_by, "T1")

    def test_blocks_passed_are_given_up(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "37")
        ctc.step(DT_S, _inputs(_train("T1", "30")))
        # T1 moves on to 34; T2 behind it can now run up to 33.
        ctc.dispatch("T2", "Green", "37")
        ctc.step(DT_S, _inputs(_train("T1", "34"), _train("T2", "29")))
        t2 = _authority(ctc, "T2")
        self.assertEqual(t2.route[1:t2.blocks + 1],
                         ("30", "31", "32", "33"))
        self.assertEqual((t2.reason, t2.at), ("occupied", "34"))


class RerouteTest(unittest.TestCase):
    """Routes go round unusable blocks and trains that are not moving,
    if the detour is not too long; otherwise the train waits."""

    # Red 27 -> 76 ... 72 -> 33 bypasses 28 to 32.
    _BYPASS = ("27", "76", "75", "74", "73", "72", "33")

    def _red(self, *trains: tuple[str, str], failures=(),
             switches=()) -> CtcInputs:
        return _inputs(*(_train(t, b, line="Red") for t, b in trains),
                       failures=tuple(TrackFailureReport("Red", b,
                                                         "power")
                                      for b in failures),
                       switches=tuple(SwitchReport("Red", s, p)
                                      for s, p in switches))

    def test_round_a_failed_block(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Red", "35")
        ctc.step(DT_S, self._red(("T1", "20"), failures=("30",)))
        route = _authority(ctc).route
        self.assertIn("76", route)
        self.assertNotIn("30", route)

    def test_round_a_train_that_is_not_moving(self) -> None:
        # T5 on 28 cannot move: 29 has failed. T4 goes round it.
        ctc = StubCtcOffice()
        ctc.dispatch("T4", "Red", "35")
        ctc.dispatch("T5", "Red", "45")
        reports = self._red(("T4", "20"), ("T5", "28"), failures=("29",))
        ctc.step(DT_S, reports)
        ctc.step(DT_S, reports)      # T5 had no authority: it is stuck
        t4 = _authority(ctc, "T4")
        self.assertEqual(t4.route[7:14], self._BYPASS)

    def test_not_round_a_train_that_is_moving(self) -> None:
        # T5 on 28 is on its way: T4 follows it rather than go round.
        ctc = StubCtcOffice()
        ctc.dispatch("T4", "Red", "35")
        ctc.dispatch("T5", "Red", "45")
        reports = self._red(("T4", "20"), ("T5", "28"),
                            switches=(("27", "normal"),))
        ctc.step(DT_S, reports)
        ctc.step(DT_S, reports)
        t4 = _authority(ctc, "T4")
        self.assertNotIn("76", t4.route)
        self.assertEqual((t4.reason, t4.at), ("occupied", "28"))

    def test_waits_rather_than_take_a_long_detour(self) -> None:
        # Red 31 is inside the bypassed stretch: reaching it round T5
        # would mean looping far round, so T4 waits behind T5.
        ctc = StubCtcOffice()
        ctc.dispatch("T4", "Red", "31")
        ctc.dispatch("T5", "Red", "45")
        reports = self._red(("T4", "20"), ("T5", "28"), failures=("29",),
                            switches=(("27", "normal"),))
        ctc.step(DT_S, reports)
        ctc.step(DT_S, reports)
        t4 = _authority(ctc, "T4")
        self.assertEqual(t4.route, tuple(str(n) for n in range(20, 32)))
        self.assertEqual((t4.reason, t4.at), ("occupied", "28"))


class ReversalTest(unittest.TestCase):
    """A train only reversing would get round is held, never reversed,
    and says where it would reverse."""

    def _held(self, t4_destination: str) -> StubCtcOffice:
        # T5 on Red 28 cannot move (29 has failed); T4 behind it on 20.
        ctc = StubCtcOffice()
        ctc.dispatch("T4", "Red", t4_destination)
        ctc.dispatch("T5", "Red", "45")
        reports = _inputs(
            _train("T4", "20", line="Red"), _train("T5", "28", line="Red"),
            failures=(TrackFailureReport("Red", "29", "power"),),
            switches=(SwitchReport("Red", "27", "normal"),))
        ctc.step(DT_S, reports)
        ctc.step(DT_S, reports)
        return ctc

    def test_reversing_route_and_where(self) -> None:
        route = reversing_route(_RED, "20", "31", {"28"})
        assert route is not None
        self.assertEqual(first_reversal(_RED, route), "33")
        self.assertEqual(route[-3:], ("33", "32", "31"))
        # A route that needs no reversal has none.
        plain = _RED.route("20", "31")
        assert plain is not None
        self.assertEqual(first_reversal(_RED, plain), "")

    def test_held_trains_say_where_they_would_reverse(self) -> None:
        ctc = self._held("31")
        t4, t5 = _authority(ctc, "T4"), _authority(ctc, "T5")
        self.assertEqual((t4.reverse_at, t4.reason, t4.at),
                         ("33", "occupied", "28"))
        self.assertEqual((t5.reverse_at, t5.reason, t5.at),
                         ("27", "failed", "29"))
        # Held, not reversed: T4 still runs toward T5 and stops short.
        self.assertEqual(t4.route[1:t4.blocks + 1],
                         tuple(str(n) for n in range(21, 28)))

    def test_no_reversal_when_a_detour_will_do(self) -> None:
        t4 = _authority(self._held("35"), "T4")
        self.assertEqual(t4.reverse_at, "")
        self.assertIn("76", t4.route)

    def test_no_reversal_when_only_waiting_on_a_moving_train(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "37")
        ctc.dispatch("T2", "Green", "40")
        reports = _inputs(_train("T1", "30"), _train("T2", "32"))
        ctc.step(DT_S, reports)
        ctc.step(DT_S, reports)
        self.assertEqual(_authority(ctc, "T1").reverse_at, "")


class SafeSpeedTest(unittest.TestCase):
    """Suggested speed lets the train stop within its authority."""

    def _speed(self, out) -> int:
        (suggestion,) = [s for s in out.track_controller.suggestions
                         if s.train_id == "T1"]
        return suggestion.suggested_speed_mps

    def test_capped_by_the_room_to_stop(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "70")
        # Green 63 is limited to 70 km/h (18 m/s suggested), but with
        # only block 64 (100 m) ahead: sqrt(2 * 1.2 * 100) = 15.
        out = ctc.step(DT_S, _inputs(_train("T1", "63"),
                                     _train("T2", "65")))
        self.assertEqual(self._speed(out), 15)
        out = ctc.step(DT_S, _inputs(_train("T1", "63"),
                                     _train("T2", "80")))
        self.assertEqual(self._speed(out), 18)

    def test_zero_with_no_authority(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "70")
        out = ctc.step(DT_S, _inputs(_train("T1", "63"),
                                     _train("T2", "64")))
        self.assertEqual(self._speed(out), 0)
        ctc.dispatch("T1", "Green", "63")
        self.assertEqual(self._speed(ctc.snapshot().outputs), 0)


if __name__ == "__main__":
    unittest.main()
