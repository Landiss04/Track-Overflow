"""Tests for the harness's Phase 1 edges, roster and track feed.

No process runs here: the edges are pure functions and plain objects,
fed the JSON forms the modules send.

Run from the repository root with
``python -m unittest discover -s common/harness/tests``.
"""

from __future__ import annotations

import sys
import unittest
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
from common.harness.track_feed import (  # noqa: E402
    GREEN_STATION_STOP,
    FeedBeacon,
    FeedSegment,
    FixedTrackFeed,
)
from common.harness.train_edges import (  # noqa: E402
    INERT_COMMANDS,
    aspect_to_train_controller,
    train_controller_to_train_model,
    train_model_to_train_controller,
)

SIM_TIME_S = 18_000.0


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

    def apply(self, released=(), retired=()) -> list[tuple[str, str, str]]:
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


class TrackFeedTest(unittest.TestCase):
    """The script gives each train its track by time in service."""

    def setUp(self) -> None:
        self.feed = FixedTrackFeed([
            FeedSegment(0.0, "63", 10.0, 3, 19.4),
            FeedSegment(5.0, "64", 10.0, 2, 19.4),
            FeedSegment(
                8.0, "65", 0.0, 0, 19.4, station_name="GLENBURY",
                beacon=FeedBeacon("GLENBURY", "R"), aspect_ahead="RED",
            ),
            FeedSegment(9.0, "65", 10.0, 3, 19.4),
        ])

    def test_segments_by_time(self) -> None:
        self.assertEqual(self.feed.segment(0.0).block_id, "63")
        self.assertEqual(self.feed.segment(4.9).block_id, "63")
        # A sum of ticks a hair short of a start still reaches it.
        self.assertEqual(self.feed.segment(5.0 - 1e-9).block_id, "64")
        self.assertEqual(self.feed.aspect_ahead(8.5), "RED")
        self.assertEqual(self.feed.segment(100.0).authority_blocks, 3)

    def test_polarity_flips_at_each_block_change(self) -> None:
        polarity = [
            self.feed.track_inputs(t)["track_info"]["polarity"]
            for t in (0.0, 5.0, 8.0, 9.0)
        ]
        self.assertEqual(polarity, [False, True, False, False])

    def test_track_inputs_in_the_train_models_form(self) -> None:
        inputs = self.feed.track_inputs(8.0)
        self.assertEqual(inputs["track_signal"], {
            "commanded_speed_mps": 0.0, "authority_blocks": 0,
        })
        self.assertEqual(inputs["beacon"], {
            "station_name": "GLENBURY",
            "platform_side": "R",
            "underground": False,
        })
        self.assertEqual(inputs["track_info"]["station_name"], "GLENBURY")
        self.assertEqual(inputs["passengers_boarded"], 0)
        self.assertIsNone(self.feed.track_inputs(0.0)["beacon"])

    def test_bad_scripts_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            FixedTrackFeed([])
        with self.assertRaises(ValueError):
            FixedTrackFeed([FeedSegment(1.0, "63", 0.0, 0, 19.4)])
        with self.assertRaises(ValueError):
            FixedTrackFeed([
                FeedSegment(0.0, "63", 0.0, 0, 19.4),
                FeedSegment(0.0, "64", 0.0, 0, 19.4),
            ])
        with self.assertRaises(ValueError):
            FixedTrackFeed([
                FeedSegment(0.0, "63", 0.0, 0, 19.4, aspect_ahead="BLUE")
            ])

    def test_default_script_never_drops_authority_from_two_to_none(
        self,
    ) -> None:
        # A drop from 2 or more blocks straight to none reads as a
        # signal pickup failure in the Train Controller.
        for before, after in zip(GREEN_STATION_STOP, GREEN_STATION_STOP[1:]):
            dropped = after.authority_blocks == 0 and (
                after.commanded_speed_mps == 0.0
            )
            if dropped:
                self.assertLess(before.authority_blocks, 2)


class SystemEdgesTest(unittest.TestCase):
    """Real edges for the wired modules, stub edges for the rest."""

    def setUp(self) -> None:
        self.edges = SystemEdges(FixedTrackFeed([
            FeedSegment(0.0, "63", 10.0, 3, 19.4, aspect_ahead="SUPER_GREEN"),
        ]))
        self.events = self.edges.tick_completed(1, SIM_TIME_S, {
            CTC_OFFICE: {"new_trains": [
                {"train_id": "G1", "line": "Green"},
                {"train_id": "R1", "line": "Red"},
            ]},
        })

    def inputs(self, consumer: str, outputs: dict) -> dict[str, Any]:
        """``consumer``'s inputs a tick after the release."""
        return self.edges.inputs_for(consumer, 2, SIM_TIME_S + 0.1, outputs)

    def test_release_is_logged(self) -> None:
        self.assertEqual(
            [event[1:] for event in self.events],
            [("TRAIN_ADDED", "G1 on Green"), ("TRAIN_ADDED", "R1 on Red")],
        )

    def test_train_model_gets_every_train_held_until_commanded(self) -> None:
        trains = self.inputs(TRAIN_MODEL, {})["trains"]
        self.assertEqual(set(trains), {"G1", "R1"})
        self.assertEqual(trains["G1"]["line"], "Green")
        self.assertEqual(trains["G1"]["controller"], dict(INERT_COMMANDS))
        self.assertEqual(
            trains["G1"]["track"]["track_info"]["block_id"], "63"
        )

    def test_train_model_gets_each_trains_commands(self) -> None:
        trains = self.inputs(TRAIN_MODEL, {
            TRAIN_CONTROLLER_SW: {"trains": {"G1": commands()}},
        })["trains"]
        self.assertEqual(trains["G1"]["controller"]["power_cmd_w"], 1200.0)
        self.assertEqual(trains["R1"]["controller"], dict(INERT_COMMANDS))

    def test_controller_takes_a_train_once_reported(self) -> None:
        self.assertEqual(
            self.inputs(TRAIN_CONTROLLER_SW, {})["trains"], {}
        )
        trains = self.inputs(TRAIN_CONTROLLER_SW, {
            TRAIN_MODEL: {"trains": {
                "G1": {"controller": report(), "track": {}},
                "R1": {"controller": report(), "track": {}},
            }},
        })["trains"]
        # Only the Green Line's train: the Red Line's goes to the HW.
        self.assertEqual(set(trains), {"G1"})
        self.assertEqual(trains["G1"]["line"], "Green")
        self.assertEqual(
            trains["G1"]["inputs"]["signal_light_ahead"], "SUPER GREEN"
        )
        self.assertEqual(trains["G1"]["inputs"]["actual_speed"], 4.5)

    def test_stubs_get_their_producers_outputs_whole(self) -> None:
        outputs = {TRAIN_MODEL: {"tick": 1}, CTC_OFFICE: {"tick": 1}}
        self.assertEqual(
            self.inputs(TRACK_MODEL, outputs), {TRAIN_MODEL: {"tick": 1}}
        )
        self.assertEqual(
            self.inputs(TRAIN_CONTROLLER_HW, outputs),
            {TRAIN_MODEL: {"tick": 1}},
        )

    def test_one_trains_rejection_is_logged_by_name(self) -> None:
        events = self.edges.tick_completed(2, SIM_TIME_S + 0.1, {
            TRAIN_MODEL: {"trains": {}, "rejected": {"G1": "too fast"}},
        })
        self.assertEqual(
            events, [(TRAIN_MODEL, "TICK_REJECTED", "G1: too fast")]
        )

    def test_retired_trains_leave_every_input(self) -> None:
        self.edges.tick_completed(2, SIM_TIME_S + 0.1, {
            CTC_OFFICE: {"retired_trains": [{"train_id": "G1"}]},
        })
        self.assertEqual(
            set(self.inputs(TRAIN_MODEL, {})["trains"]), {"R1"}
        )


if __name__ == "__main__":
    unittest.main()
