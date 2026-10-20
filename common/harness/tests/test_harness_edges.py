"""Tests for the harness's edges, roster and scripted wayside.

No process runs here: the edges are pure functions and plain objects,
fed the JSON forms the modules send.

Run from the repository root with
``python -m unittest discover -s common/harness/tests``.
"""

from __future__ import annotations

import sys
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from common.harness.edges import SystemEdges  # noqa: E402
from common.harness.modules import (  # noqa: E402
    CTC_OFFICE,
    TRACK_MODEL,
    TRAIN_CONTROLLER_HW,
    TRAIN_CONTROLLER_SW,
    TRAIN_MODEL,
)
from common.harness.roster import Roster  # noqa: E402
from common.harness.track_edges import (  # noqa: E402
    BlockNames,
    block_commands_to_track_model,
    placement_report,
    track_model_to_train_model,
    train_model_to_track_model,
)
from common.harness.train_edges import (  # noqa: E402
    INERT_COMMANDS,
    aspect_to_train_controller,
    train_controller_to_train_model,
    train_model_to_train_controller,
)
from common.harness.wayside_script import (  # noqa: E402
    GREEN_YARD_TO_DORMONT,
    STOP_HOLD_S,
    RouteBlock,
    ScriptedWayside,
    WaysideRoute,
)

SIM_TIME_S = 18_000.0
DT_S = 0.1

#: Some of the Track Model's block names, as its outputs list them.
TRACK_MODEL_BLOCKS = (
    "GREEN K-63", "GREEN K-64", "GREEN K-65", "GREEN K-66",
    "RED C-9", "BLUE A-1",
)


def commands(**changes: Any) -> dict[str, Any]:
    """A Train Controller's commands for one train."""
    return {
        "power_w": 1200.0,
        "service_brake": False,
        "emergency_brake": False,
        "door_command": [False, True],
        "light_command": [True, False],
        "temperature_setpoint_c": 22.2,
        "announcement": "GLENBURY",
        "passenger_brake_release": False,
        **changes,
    }


def report(**changes: Any) -> dict[str, Any]:
    """A Train Model's ``controller`` outputs for one train."""
    return {
        "actual_speed_mps": 4.5,
        "emergency_brake_active": True,
        "service_brake_active": False,
        "door_left_open": False,
        "door_right_open": True,
        "interior_lights_on": True,
        "exterior_lights_on": False,
        "cabin_temp_c": 21.5,
        "commanded_speed_mps": 12.5,
        "authority_blocks": 3,
        "speed_limit_mps": 19.4,
        "beacon": None,
        **changes,
    }


class TrainEdgesTest(unittest.TestCase):
    """Each field lands where the other module reads it."""

    def test_commands_to_the_train_model(self) -> None:
        mapped = train_controller_to_train_model(
            commands(passenger_brake_release=True)
        )
        self.assertEqual(mapped, {
            "power_cmd_w": 1200.0,
            "service_brake": False,
            "emergency_brake": False,
            "interior_lights": True,
            "exterior_lights": False,
            "door_left_open": False,
            "door_right_open": True,
            "temp_setpoint_c": 22.2,
            "announcement": "GLENBURY",
            "passenger_brake_release": True,
        })

    def test_report_to_the_train_controller(self) -> None:
        self.assertEqual(train_model_to_train_controller(report()), {
            "actual_speed": 4.5,
            "commanded_speed": 12.5,
            "authority_blocks": 3,
            "brake_state": [True, False],
            "door_state": [False, True],
            "light_state": [True, False],
            "cabin_temperature": 21.5,
        })

    def test_a_beacon_is_passed_on_while_reported(self) -> None:
        mapped = train_model_to_train_controller(report(beacon={
            "station_name": "GLENBURY",
            "platform_side": "R",
            "underground": False,
        }))
        self.assertEqual(
            (mapped["beacon_station"], mapped["beacon_side"],
             mapped["beacon_underground"]),
            ("GLENBURY", "R", False),
        )

    def test_a_missing_field_is_an_error(self) -> None:
        broken = commands()
        del broken["power_w"]
        with self.assertRaises(KeyError):
            train_controller_to_train_model(broken)

    def test_lights_ahead_in_the_controllers_spelling(self) -> None:
        self.assertEqual(
            aspect_to_train_controller("SUPER_GREEN"), "SUPER GREEN"
        )
        self.assertEqual(aspect_to_train_controller("RED"), "RED")
        with self.assertRaises(KeyError):
            aspect_to_train_controller("SUPER GREEN")

    def test_inert_commands_hold_the_train(self) -> None:
        self.assertEqual(INERT_COMMANDS["power_cmd_w"], 0.0)
        self.assertTrue(INERT_COMMANDS["service_brake"])
        self.assertFalse(INERT_COMMANDS["door_left_open"])
        self.assertFalse(INERT_COMMANDS["door_right_open"])


class RosterTest(unittest.TestCase):
    """Releases add trains and retirements remove them, once each."""

    def setUp(self) -> None:
        self.roster = Roster(CTC_OFFICE)

    def apply(
        self,
        released: Sequence[tuple[str, str]] = (),
        retired: Sequence[str] = (),
    ) -> list[tuple[str, str, str]]:
        """Apply one tick's events."""
        return self.roster.apply(
            {
                "new_trains": [
                    {"train_id": train_id, "line": line}
                    for train_id, line in released
                ],
                "retired_trains": [{"train_id": t} for t in retired],
            },
            SIM_TIME_S,
        )

    def test_release_and_retire(self) -> None:
        events = self.apply(released=[("G1", "Green"), ("R1", "Red")])
        self.assertEqual(
            [entry.train_id for entry in self.roster], ["G1", "R1"]
        )
        self.assertEqual(
            [event[1] for event in events], ["TRAIN_ADDED", "TRAIN_ADDED"]
        )
        self.assertEqual(self.apply(retired=["G1"]),
                         [("harness", "TRAIN_REMOVED", "G1")])
        self.assertEqual([entry.train_id for entry in self.roster], ["R1"])

    def test_bad_events_are_refused_and_logged(self) -> None:
        self.apply(released=[("G1", "Green")])
        events = self.apply(
            released=[
                ("G1", "Green"),
                ("B1", "Blue"),
                (" G2", "Green"),
                ("G" * 33, "Green"),
            ],
            retired=["G9"],
        )
        self.assertEqual(len(events), 5)
        self.assertTrue(all(
            event[:2] == (CTC_OFFICE, "PROTOCOL_ERROR") for event in events
        ))
        self.assertEqual(len(self.roster), 1)

    def test_events_that_are_not_lists_are_refused(self) -> None:
        events = self.roster.apply(
            {"new_trains": {"train_id": "G1"}}, SIM_TIME_S
        )
        self.assertEqual(events[0][1], "PROTOCOL_ERROR")
        self.assertEqual(len(self.roster), 0)

    def test_no_events_is_no_change(self) -> None:
        self.assertEqual(self.roster.apply({}, SIM_TIME_S), [])


def feed(block_id: str = "GREEN K-64", **changes: Any) -> dict[str, Any]:
    """The Track Model's feed for one train."""
    return {
        "track_info": {
            "block_id": block_id,
            "grade_deg": 0.0,
            "elevation_m": 0.0,
            "speed_limit_mps": 19.4,
            "polarity": True,
            "station_name": None,
        },
        "track_signal": {"commanded_speed_mps": 12.5, "authority_blocks": 1},
        "beacon": {
            "station_name": "GLENBURY",
            "platform_side": "R",
            "underground": False,
        },
        "passengers_boarded": 0,
        **changes,
    }


def track_outputs(**changes: Any) -> dict[str, Any]:
    """A Train Model's ``track`` outputs for one train."""
    return {
        "block_id": "64",
        "offset_m": 12.0,
        "actual_speed_mps": 4.5,
        "block_changed": False,
        "passenger_capacity": 200,
        **changes,
    }


def track_model_outputs(
    occupied: tuple[str, ...] = (),
    feeds: dict[str, Any] | None = None,
    seen: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The Track Model's outputs, with the blocks it lists."""
    return {
        "controller": {"block_occupancy": {
            name: name in occupied for name in TRACK_MODEL_BLOCKS
        }},
        "train_feeds": feeds or {},
        "signal_seen": seen or {},
    }


class TrackEdgesTest(unittest.TestCase):
    """Blocks are renamed, and each field lands where it is read."""

    def setUp(self) -> None:
        self.names = BlockNames()
        self.names.learn(TRACK_MODEL_BLOCKS)

    def test_block_names_both_ways(self) -> None:
        self.assertEqual(
            self.names.track_model_name("Green", "63"), "GREEN K-63"
        )
        self.assertEqual(self.names.block("RED C-9"), ("Red", "9"))
        # The Blue Line is out of scope (D023).
        with self.assertRaises(KeyError):
            self.names.block("BLUE A-1")
        with self.assertRaises(KeyError):
            self.names.track_model_name("Green", "1")

    def test_no_names_before_the_track_model_reports(self) -> None:
        self.assertFalse(BlockNames())
        self.assertTrue(self.names)

    def test_report_to_the_track_model(self) -> None:
        mapped = train_model_to_track_model(
            {"track": track_outputs(), "controller": report()},
            "Green", self.names,
        )
        self.assertEqual(mapped, {
            "block_id": "GREEN K-64",
            "offset_m": 12.0,
            "actual_speed_mps": 4.5,
            "block_changed": False,
            "passenger_capacity": 200,
            "doors_open": True,
        })

    def test_doors_open_means_either_door(self) -> None:
        for left, right, either in (
            (False, False, False), (True, False, True), (False, True, True),
        ):
            mapped = train_model_to_track_model(
                {"track": track_outputs(), "controller": report(
                    door_left_open=left, door_right_open=right)},
                "Green", self.names,
            )
            self.assertIs(mapped["doors_open"], either)

    def test_feed_to_the_train_model(self) -> None:
        mapped = track_model_to_train_model(feed(), self.names)
        self.assertEqual(mapped["track_info"]["block_id"], "64")
        self.assertEqual(mapped["track_signal"], {
            "commanded_speed_mps": 12.5, "authority_blocks": 1,
        })
        self.assertEqual(mapped["beacon"]["platform_side"], "R")
        self.assertIsNone(
            track_model_to_train_model(feed(beacon=None), self.names)[
                "beacon"]
        )

    def test_a_beacon_is_checked_and_passed_unchanged(self) -> None:
        for side in ("L", "R", "LR"):
            beacon = {"station_name": "MT LEBANON", "platform_side": side,
                      "underground": True}
            mapped = track_model_to_train_model(feed(beacon=beacon),
                                                self.names)
            self.assertEqual(mapped["beacon"], beacon)
        for bad in (
            {"platform_side": None},
            {"platform_side": "Q"},
            {"underground": "false"},
            {"station_name": "S" * 120},
        ):
            beacon = {"station_name": "GLENBURY", "platform_side": "R",
                      "underground": False, **bad}
            with self.assertRaises(ValueError):
                track_model_to_train_model(feed(beacon=beacon), self.names)

    def test_a_new_train_is_placed_at_rest(self) -> None:
        placed = placement_report("GREEN K-63")
        self.assertEqual(placed["block_id"], "GREEN K-63")
        self.assertEqual(placed["offset_m"], 0.0)
        self.assertFalse(placed["doors_open"])

    def test_block_commands_renamed(self) -> None:
        mapped = block_commands_to_track_model(
            {"commanded_authority": {"63": 2}, "signal_commands": {}},
            "Green", self.names,
        )
        self.assertEqual(mapped, {
            "commanded_authority": {"GREEN K-63": 2},
            "signal_commands": {},
        })


class WaysideScriptTest(unittest.TestCase):
    """Authority counts down to each stop, and the next block is ready."""

    def setUp(self) -> None:
        self.wayside = ScriptedWayside(WaysideRoute(
            line="Green",
            blocks=(
                RouteBlock("63", 10.0),
                RouteBlock("64", 10.0),
                RouteBlock("65", 10.0, hold_s=30.0),
                RouteBlock("66", 8.0),
                RouteBlock("67", 8.0),
            ),
            signals={"64": "GREEN"},
        ))

    def values(
        self, block: str, at_s: float = 0.0
    ) -> dict[str, tuple[float, int]]:
        """Each commanded block's speed and authority, train in one."""
        commands = self.wayside.step(SIM_TIME_S + at_s, [block])
        return {
            number: (speed, commands["commanded_authority"][number])
            for number, speed in commands["commanded_speed_mps"].items()
        }

    def test_nothing_commanded_without_a_train(self) -> None:
        commands = self.wayside.step(SIM_TIME_S, [])
        self.assertEqual(commands["commanded_speed_mps"], {})
        self.assertEqual(commands["commanded_authority"], {})
        self.assertEqual(commands["signal_commands"], {"64": "GREEN"})

    def test_authority_counts_down_to_the_stop(self) -> None:
        self.assertEqual(
            self.values("63"), {"63": (10.0, 2), "64": (10.0, 1)}
        )
        self.assertEqual(self.values("64"), {"64": (10.0, 1), "65": (0.0, 0)})
        self.assertEqual(self.values("65"), {"65": (0.0, 0)})

    def test_the_stop_holds_then_releases_to_the_destination(self) -> None:
        self.assertEqual(self.values("65", 0.0), {"65": (0.0, 0)})
        self.assertEqual(self.values("65", 29.9), {"65": (0.0, 0)})
        self.assertEqual(
            self.values("65", 30.0), {"65": (10.0, 2), "66": (8.0, 1)}
        )
        self.assertEqual(
            self.values("66", 40.0), {"66": (8.0, 1), "67": (0.0, 0)}
        )
        self.assertEqual(self.values("67", 50.0), {"67": (0.0, 0)})

    def test_blocks_off_the_route_are_left_alone(self) -> None:
        self.assertEqual(self.values("12"), {})

    def test_bad_routes_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            ScriptedWayside(WaysideRoute("Green", ()))
        with self.assertRaises(ValueError):
            ScriptedWayside(WaysideRoute(
                "Green", (RouteBlock("63", 1.0), RouteBlock("63", 1.0))
            ))

    def test_default_route_never_drops_two_blocks_of_authority_at_once(
        self,
    ) -> None:
        # The Train Controller reads a fall from 2 or more blocks
        # straight to none as a signal pickup failure.
        wayside = ScriptedWayside(GREEN_YARD_TO_DORMONT)
        blocks = [block.block_id for block in GREEN_YARD_TO_DORMONT.blocks]
        last: int | None = None
        for at_s, number in enumerate(blocks):
            # One block a second, past the stop's hold where it is.
            time_s = at_s + (STOP_HOLD_S if at_s > 2 else 0.0)
            authority = wayside.step(SIM_TIME_S + time_s, [number])[
                "commanded_authority"][number]
            if last is not None and authority == 0:
                self.assertLess(last, 2)
            last = authority
        self.assertEqual(last, 0)


class SystemEdgesTest(unittest.TestCase):
    """Real edges for the wired modules, stub edges for the rest."""

    def setUp(self) -> None:
        self.edges = SystemEdges(ScriptedWayside(GREEN_YARD_TO_DORMONT))
        self.tick = 1
        self.events = self.complete({
            CTC_OFFICE: {"new_trains": [
                {"train_id": "G1", "line": "Green"},
                {"train_id": "R1", "line": "Red"},
            ]},
            TRACK_MODEL: track_model_outputs(),
        })

    def complete(self, fresh: dict[str, Any]) -> list[Any]:
        """End the current tick with these new outputs."""
        events = self.edges.tick_completed(
            self.tick, SIM_TIME_S + self.tick * DT_S, fresh
        )
        self.tick += 1
        return events

    def inputs(self, consumer: str, outputs: dict) -> dict[str, Any]:
        """``consumer``'s inputs for the next tick."""
        return self.edges.inputs_for(
            consumer, self.tick, SIM_TIME_S + self.tick * DT_S, outputs
        )

    def test_release_is_logged(self) -> None:
        self.assertEqual(
            [event[1:] for event in self.events],
            [("TRAIN_ADDED", "G1 on Green"), ("TRAIN_ADDED", "R1 on Red")],
        )

    def test_track_model_places_each_train_at_its_yard_exit(self) -> None:
        inputs = self.inputs(TRACK_MODEL, {})
        self.assertEqual(inputs["trains"], {
            "G1": placement_report("GREEN K-63"),
            "R1": placement_report("RED C-9"),
        })
        # The wayside commands nothing before it knows the blocks.
        self.assertEqual(inputs["controller"], {})

    def test_track_model_takes_the_train_models_report(self) -> None:
        trains = self.inputs(TRACK_MODEL, {TRAIN_MODEL: {"trains": {
            "G1": {"track": track_outputs(), "controller": report()},
            "R1": {"track": track_outputs(block_id=""),
                   "controller": report()},
        }}})["trains"]
        self.assertEqual(trains["G1"]["block_id"], "GREEN K-64")
        self.assertTrue(trains["G1"]["doors_open"])
        # No block reported yet: still waiting where it was placed.
        self.assertEqual(trains["R1"], placement_report("RED C-9"))

    def test_wayside_commands_arrive_a_tick_after_the_occupancy(
        self,
    ) -> None:
        self.complete({TRACK_MODEL: track_model_outputs(("GREEN K-63",))})
        commands = self.inputs(TRACK_MODEL, {})["controller"]
        self.assertEqual(commands["commanded_authority"], {})
        self.complete({})
        commands = self.inputs(TRACK_MODEL, {})["controller"]
        self.assertEqual(
            commands["commanded_authority"],
            {"GREEN K-63": 2, "GREEN K-64": 1},
        )
        self.assertEqual(commands["signal_commands"], {"GREEN K-64": "GREEN"})

    def test_train_model_takes_a_train_once_fed(self) -> None:
        self.assertEqual(self.inputs(TRAIN_MODEL, {})["trains"], {})
        trains = self.inputs(TRAIN_MODEL, {
            TRACK_MODEL: track_model_outputs(feeds={"G1": feed()}),
            TRAIN_CONTROLLER_SW: {"trains": {"G2": commands()}},
        })["trains"]
        self.assertEqual(set(trains), {"G1"})
        self.assertEqual(trains["G1"]["line"], "Green")
        self.assertEqual(trains["G1"]["controller"], dict(INERT_COMMANDS))
        self.assertEqual(trains["G1"]["track"]["track_info"]["block_id"],
                         "64")

    def test_train_model_gets_each_trains_commands(self) -> None:
        trains = self.inputs(TRAIN_MODEL, {
            TRACK_MODEL: track_model_outputs(feeds={"G1": feed()}),
            TRAIN_CONTROLLER_SW: {"trains": {"G1": commands()}},
        })["trains"]
        self.assertEqual(trains["G1"]["controller"]["power_cmd_w"], 1200.0)

    def test_controller_takes_a_train_once_reported(self) -> None:
        self.assertEqual(
            self.inputs(TRAIN_CONTROLLER_SW, {})["trains"], {}
        )
        trains = self.inputs(TRAIN_CONTROLLER_SW, {
            TRAIN_MODEL: {"trains": {
                "G1": {"controller": report(), "track": {}},
                "R1": {"controller": report(), "track": {}},
            }},
            TRACK_MODEL: track_model_outputs(seen={"G1": "SUPER_GREEN"}),
        })["trains"]
        # Only the Green Line's train: the Red Line's goes to the HW.
        self.assertEqual(set(trains), {"G1"})
        self.assertEqual(trains["G1"]["line"], "Green")
        self.assertEqual(
            trains["G1"]["inputs"]["signal_light_ahead"], "SUPER GREEN"
        )
        self.assertEqual(trains["G1"]["inputs"]["actual_speed"], 4.5)

    def test_no_light_is_sent_on_a_tick_none_is_seen(self) -> None:
        trains = self.inputs(TRAIN_CONTROLLER_SW, {
            TRAIN_MODEL: {"trains": {"G1": {"controller": report()}}},
            TRACK_MODEL: track_model_outputs(seen={"G1": None}),
        })["trains"]
        self.assertNotIn("signal_light_ahead", trains["G1"]["inputs"])

    def test_a_train_that_leaves_the_track_leaves_every_input(
        self,
    ) -> None:
        self.complete({TRACK_MODEL: track_model_outputs(
            ("GREEN K-63",), feeds={"G1": feed()})})
        events = self.complete({TRACK_MODEL: track_model_outputs()})
        self.assertEqual(events, [("harness", "TRAIN_LEFT_TRACK", "G1")])
        self.assertEqual(self.complete({TRACK_MODEL: track_model_outputs()}),
                         [])
        outputs = {
            TRAIN_MODEL: {"trains": {"G1": {"controller": report(),
                                            "track": track_outputs()}}},
            TRACK_MODEL: track_model_outputs(feeds={"G1": feed()}),
        }
        self.assertNotIn("G1", self.inputs(TRACK_MODEL, outputs)["trains"])
        self.assertNotIn("G1", self.inputs(TRAIN_MODEL, outputs)["trains"])
        self.assertNotIn(
            "G1", self.inputs(TRAIN_CONTROLLER_SW, outputs)["trains"]
        )

    def test_stubs_get_their_producers_outputs_whole(self) -> None:
        outputs = {TRAIN_MODEL: {"tick": 1}, CTC_OFFICE: {"tick": 1}}
        self.assertEqual(
            self.inputs(TRAIN_CONTROLLER_HW, outputs),
            {TRAIN_MODEL: {"tick": 1}},
        )

    def test_one_trains_rejection_is_logged_by_name(self) -> None:
        events = self.complete({
            TRAIN_MODEL: {"trains": {}, "rejected": {"G1": "too fast"}},
        })
        self.assertEqual(
            events, [(TRAIN_MODEL, "TICK_REJECTED", "G1: too fast")]
        )

    def test_retired_trains_leave_every_input(self) -> None:
        self.complete({
            CTC_OFFICE: {"retired_trains": [{"train_id": "G1"}]},
        })
        self.assertEqual(
            set(self.inputs(TRACK_MODEL, {})["trains"]), {"R1"}
        )


if __name__ == "__main__":
    unittest.main()
