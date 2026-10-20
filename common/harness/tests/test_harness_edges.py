"""Tests for the harness's edges, roster, switch places and CTC stand-in.

No process runs here: the edges are pure functions and plain objects,
fed the JSON forms the modules send. The switch places are checked
against both modules' own readings of the layout files.

Run from the repository root with
``python -m unittest discover -s common/harness/tests``.
"""

from __future__ import annotations

import json
import sys
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
for _folder in (_REPO, _REPO / "TrackModel", _REPO / "TrackCtrlSW"):
    if str(_folder) not in sys.path:
        sys.path.insert(0, str(_folder))

from common.harness.ctc_script import (  # noqa: E402
    GREEN_YARD_TO_DORMONT,
    STOP_HOLD_S,
    CtcRoute,
    RouteBlock,
    ScriptedCtc,
)
from common.harness.edges import SystemEdges  # noqa: E402
from common.harness.modules import (  # noqa: E402
    CTC_OFFICE,
    TRACK_CONTROLLER_SW,
    TRACK_MODEL,
    TRAIN_CONTROLLER_HW,
    TRAIN_CONTROLLER_SW,
    TRAIN_MODEL,
)
from common.harness.roster import Roster  # noqa: E402
from common.harness.track_devices import (  # noqa: E402
    LAYOUT_FILES,
    SwitchPlace,
    TrackDevices,
    layout_dir,
    switch_places,
)
from common.harness.track_edges import (  # noqa: E402
    BlockNames,
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
from common.harness.wayside_edges import (  # noqa: E402
    ctc_to_track_controller,
    line_ready,
    track_controller_to_ctc,
    track_controller_to_track_model,
    track_model_to_track_controller,
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
        "controller": {
            "block_occupancy": {
                name: name in occupied for name in TRACK_MODEL_BLOCKS
            },
            "switch_states": {},
            "crossing_states": {},
            "signal_states": {},
        },
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

    def test_a_beacon_passes_unchanged_even_when_malformed(self) -> None:
        # The Train Model checks it, and rejects only that train.
        for changes in (
            {}, {"platform_side": "LR"}, {"platform_side": None},
            {"underground": "false"}, {"station_name": "S" * 120},
        ):
            beacon = {"station_name": "GLENBURY", "platform_side": "R",
                      "underground": False, **changes}
            mapped = track_model_to_train_model(feed(beacon=beacon),
                                                self.names)
            self.assertEqual(mapped["beacon"], beacon)

    def test_a_new_train_is_placed_at_rest(self) -> None:
        placed = placement_report("GREEN K-63")
        self.assertEqual(placed["block_id"], "GREEN K-63")
        self.assertEqual(placed["offset_m"], 0.0)
        self.assertFalse(placed["doors_open"])


#: The Green Line's switches: ID, point and light (``track_devices``).
GREEN_SWITCHES = (
    ("12", "13", "14"), ("28", "28", "27"), ("58", "57", "56"),
    ("62", "63", "64"), ("76", "77", "78"), ("85", "85", "84"),
)


def _green(number: str) -> dict[str, str]:
    # One block in the Track Controller's form.
    return {"line": "Green", "block_id": number}


def wayside_outputs(
    ready: bool = True,
    occupied: tuple[str, ...] = (),
    circuits: Mapping[str, tuple[int, int]] | None = None,
    switches: Mapping[str, str] | None = None,
    lights: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """The Track Controller's outputs: one wayside, Green 62 to 66.

    Switch 62 stands on block 62 with its light, as the Track
    Controller names them, and block 65 holds a crossing, gates down.
    """
    return {
        "track_model": {
            "track_circuits": [
                {"block": _green(number),
                 "value": {"speed_mps": speed, "authority_blocks": blocks}}
                for number, (speed, blocks) in (circuits or {}).items()
            ],
            "switch_commands": [
                {"block": _green(number), "value": value}
                for number, value in (switches or {}).items()
            ],
            "crossing_commands": [],
            "signal_commands": [
                {"block": _green(number), "value": value}
                for number, value in (lights or {}).items()
            ],
        },
        "ctc_reports": [{
            "wayside_id": "GTC-03",
            "line": "Green",
            "sent_at_s": SIM_TIME_S,
            "ready": ready,
            "reason": "" if ready else "no PLC program",
            "blocks": [
                {"block": _green(number), "value": {
                    "occupied": number in occupied,
                    "switch_position": "normal" if number == "62" else None,
                    "crossing_active": True if number == "65" else None,
                    "signal_aspect": "red" if number == "62" else None,
                }}
                for number in ("62", "63", "64", "65", "66")
            ],
        }],
    }


def ctc_inputs(
    occupied: tuple[str, ...] = (), ready: bool = True
) -> dict[str, Any]:
    """What the CTC Office reads from the Track Controller: Green 60-74."""
    return {
        "occupancy": [
            {"line": "Green", "block_id": str(number),
             "occupied": str(number) in occupied}
            for number in range(60, 75)
        ],
        "switches": [],
        "crossings": [],
        "waysides": [{
            "wayside_id": "GTC-03", "line": "Green", "ready": ready,
            "reason": "" if ready else "no PLC program",
        }],
    }


def suggestion(block: str, speed: int, blocks: int) -> dict[str, Any]:
    """One of G1's suggestions, in the CTC Office's form."""
    return {"train_id": "G1", "line": "Green", "block_id": block,
            "suggested_speed_mps": speed, "authority_blocks": blocks}


class TrackDevicesTest(unittest.TestCase):
    """Each switch's ID, point and light, as both modules read them."""

    devices: TrackDevices

    @classmethod
    def setUpClass(cls) -> None:
        cls.devices = TrackDevices.load()

    def test_the_green_switches(self) -> None:
        self.assertEqual(
            [(place.switch_id, place.point, place.light)
             for place in self.devices.places("Green")],
            list(GREEN_SWITCHES),
        )

    def test_lookups_by_each_name(self) -> None:
        place = SwitchPlace("Green", "62", "63", "64")
        self.assertEqual(self.devices.by_switch("Green", "62"), place)
        self.assertEqual(self.devices.by_point("Green", "63"), place)
        self.assertEqual(self.devices.by_light("Green", "64"), place)
        with self.assertRaises(KeyError):
            self.devices.by_switch("Red", "62")

    def test_the_track_model_reads_the_same_points_and_lights(self) -> None:
        from track_model.layout import load_layout

        for line, file_name in LAYOUT_FILES.items():
            layout = load_layout([str(layout_dir() / file_name)])
            names = BlockNames()
            names.learn(layout.blocks)
            places = self.devices.places(line)
            self.assertEqual(
                {place.point for place in places},
                {names.block(switch.point_block_id)[1]
                 for switch in layout.switches.values()},
            )
            self.assertEqual(
                {place.light for place in places},
                {names.block(block)[1] for block in layout.signal_block_ids},
            )
            # Each light stands beside its own switch's point.
            for place in places:
                self.assertIn(
                    names.track_model_name(line, place.point),
                    layout.neighbours[
                        names.track_model_name(line, place.light)],
                )

    def test_the_track_controller_reads_the_same_ids_and_points(
        self,
    ) -> None:
        from track_ctrl.layout import load_layout_file

        for line, file_name in LAYOUT_FILES.items():
            parsed = load_layout_file(layout_dir() / file_name)
            self.assertEqual(
                {(switch.switch_id, switch.point)
                 for switch in parsed.switches},
                {(place.switch_id, place.point)
                 for place in self.devices.places(line)},
            )

    def test_a_switch_it_cannot_read_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            switch_places({"line": "Green", "blocks": [
                {"block_number": 1, "next_blocks": [2],
                 "infrastructure": {"switch": "1-2; 3-4"}},
                {"block_number": 2, "next_blocks": [1]},
            ]})


class WaysideEdgesTest(unittest.TestCase):
    """Into and out of the Track Controller, renamed both ways."""

    devices: TrackDevices

    @classmethod
    def setUpClass(cls) -> None:
        cls.devices = TrackDevices.load()

    def setUp(self) -> None:
        self.names = BlockNames()
        self.names.learn(TRACK_MODEL_BLOCKS)

    def test_suggestions_by_block_without_the_train(self) -> None:
        mapped = ctc_to_track_controller({"track_controller": {
            "suggestions": [
                suggestion("63", 12, 2),
                suggestion("64", 12, 1),
                {"train_id": "R1", "line": "Red", "block_id": "9",
                 "suggested_speed_mps": 8, "authority_blocks": 4},
            ],
            "closed_blocks": [
                {"line": "Green", "block_id": "70"},
                {"line": "Red", "block_id": "70"},
            ],
            "switch_commands": [
                {"line": "Green", "switch_id": "62", "position": "reverse"},
            ],
        }}, "Green")
        self.assertEqual(mapped, {
            "closed_blocks": [_green("70")],
            "switch_commands": [
                {"block": _green("62"), "value": "reverse"},
            ],
            "suggestions": [
                {"block": _green("63"),
                 "value": {"speed_mps": 12, "authority_blocks": 2}},
                {"block": _green("64"),
                 "value": {"speed_mps": 12, "authority_blocks": 1}},
            ],
        })

    def test_two_suggestions_for_one_block_take_the_lower_of_each(
        self,
    ) -> None:
        mapped = ctc_to_track_controller({"track_controller": {
            "suggestions": [
                suggestion("64", 12, 1),
                {**suggestion("64", 9, 3), "train_id": "G2"},
            ],
            "closed_blocks": [],
            "switch_commands": [],
        }}, "Green")
        self.assertEqual(mapped["suggestions"], [
            {"block": _green("64"),
             "value": {"speed_mps": 9, "authority_blocks": 1}},
        ])

    def test_the_track_models_read_back_by_the_controllers_names(
        self,
    ) -> None:
        mapped = track_model_to_track_controller({"controller": {
            "block_occupancy": {
                "GREEN K-63": True, "GREEN K-64": False, "RED C-9": True,
                "BLUE A-1": True,
            },
            # Switch Green 62 has its point on 63 and its light on 64.
            "switch_states": {"GREEN K-63": "REVERSE"},
            "crossing_states": {"GREEN K-65": True},
            "signal_states": {"GREEN K-64": "SUPER_GREEN"},
        }}, "Green", self.names, self.devices)
        self.assertEqual(mapped, {
            "occupied_blocks": [_green("63")],
            "switch_positions": [
                {"block": _green("62"), "value": "reverse"},
            ],
            "crossings_active": [{"block": _green("65"), "value": True}],
            "signal_aspects": [
                {"block": _green("62"), "value": "super_green"},
            ],
        })

    def test_commands_to_the_track_model_by_its_names(self) -> None:
        mapped = track_controller_to_track_model(wayside_outputs(
            circuits={"63": (12, 2), "64": (12, 1)},
            switches={"62": "normal"},
            lights={"62": "yellow"},
        ), self.names, self.devices)
        self.assertEqual(mapped, {
            "commanded_speed_mps": {"GREEN K-63": 12.0, "GREEN K-64": 12.0},
            "commanded_authority": {"GREEN K-63": 2, "GREEN K-64": 1},
            "switch_commands": {"GREEN K-63": "NORMAL"},
            "crossing_commands": {},
            "signal_commands": {"GREEN K-64": "YELLOW"},
        })
        # Commanded speed is a float on the track signal (R24).
        speed = mapped["commanded_speed_mps"]["GREEN K-63"]
        self.assertIsInstance(speed, float)

    def test_a_switch_no_layout_lists_is_an_error(self) -> None:
        with self.assertRaises(KeyError):
            track_controller_to_track_model(
                wayside_outputs(switches={"63": "normal"}),
                self.names, self.devices,
            )

    def test_reports_to_the_ctc_office(self) -> None:
        mapped = track_controller_to_ctc(
            wayside_outputs(ready=False, occupied=("64",))
        )
        self.assertEqual(mapped["waysides"], [{
            "wayside_id": "GTC-03", "line": "Green", "ready": False,
            "reason": "no PLC program",
        }])
        self.assertEqual(len(mapped["occupancy"]), 5)
        self.assertEqual(
            [each["block_id"] for each in mapped["occupancy"]
             if each["occupied"]],
            ["64"],
        )
        self.assertEqual(mapped["switches"], [
            {"line": "Green", "switch_id": "62", "position": "normal"},
        ])
        self.assertEqual(mapped["crossings"], [
            {"line": "Green", "crossing_id": "65", "state": "active"},
        ])

    def test_a_line_is_ready_once_every_wayside_on_it_is(self) -> None:
        def wayside(line: str, ready: bool) -> dict[str, Any]:
            return {"wayside_id": "X", "line": line, "ready": ready,
                    "reason": ""}

        self.assertFalse(line_ready([], "Green"))
        self.assertFalse(line_ready([wayside("Red", True)], "Green"))
        self.assertFalse(line_ready(
            [wayside("Green", True), wayside("Green", False)], "Green"
        ))
        self.assertTrue(line_ready(
            [wayside("Green", True), wayside("Red", False)], "Green"
        ))


class EdgeContractTest(unittest.TestCase):
    """What each edge makes, each module's own decoder accepts."""

    def setUp(self) -> None:
        self.names = BlockNames()
        self.names.learn(TRACK_MODEL_BLOCKS)
        self.devices = TrackDevices.load()

    def test_the_track_controller_takes_its_inputs(self) -> None:
        from track_ctrl.wire import inputs_from_wire, outputs_from_wire

        # The helper is a Track Controller's outputs, as its wire has it.
        outputs_from_wire(wayside_outputs(
            circuits={"63": (12, 2)}, switches={"62": "normal"},
            lights={"62": "green"},
        ))
        inputs = inputs_from_wire(json.loads(json.dumps({
            "time_s": SIM_TIME_S,
            "ctc": ctc_to_track_controller({"track_controller": {
                "suggestions": [suggestion("63", 12, 2)],
                "closed_blocks": [{"line": "Green", "block_id": "70"}],
                "switch_commands": [{"line": "Green", "switch_id": "62",
                                     "position": "reverse"}],
            }}, "Green"),
            "track_model": track_model_to_track_controller({"controller": {
                "block_occupancy": {"GREEN K-63": True},
                "switch_states": {"GREEN K-63": "NORMAL"},
                "crossing_states": {"GREEN K-65": False},
                "signal_states": {"GREEN K-64": "RED"},
            }}, "Green", self.names, self.devices),
        })))
        self.assertEqual(len(inputs.ctc.suggestions), 1)
        self.assertEqual(len(inputs.track_model.occupied_blocks), 1)

    def test_the_track_model_takes_its_commands(self) -> None:
        from track_model.wire import decode_inputs

        commands = track_controller_to_track_model(wayside_outputs(
            circuits={"63": (12, 2)}, switches={"62": "reverse"},
            lights={"62": "super_green"},
        ), self.names, self.devices)
        inputs = decode_inputs(json.loads(json.dumps(
            {"controller": commands, "trains": {}}
        )))
        self.assertEqual(inputs.controller.commanded_authority,
                         {"GREEN K-63": 2})

    def test_the_ctc_office_takes_its_input(self) -> None:
        sys.path.insert(0, str(_REPO / "CTC-Office"))
        try:
            from ctc.wire import inputs_from_wire
        finally:
            sys.path.remove(str(_REPO / "CTC-Office"))
        inputs = inputs_from_wire(json.loads(json.dumps({
            "track_controller": track_controller_to_ctc(
                wayside_outputs(occupied=("64",))
            ),
        })))
        self.assertEqual(len(inputs.track_controller.waysides), 1)
        self.assertEqual(inputs.track_controller.crossings[0].state,
                         "active")


class ScriptedCtcTest(unittest.TestCase):
    """Released once ready; authority to each stop, the next preloaded."""

    def setUp(self) -> None:
        self.ctc = ScriptedCtc(CtcRoute("G1", "Green", (
            RouteBlock("63", 10),
            RouteBlock("64", 10),
            RouteBlock("65", 10, hold_s=30.0),
            RouteBlock("66", 8),
            RouteBlock("67", 8),
        )))

    def step(
        self, occupied: tuple[str, ...] = (), at_s: float = 0.0
    ) -> dict[str, Any]:
        """The stand-in's outputs for one tick."""
        return self.ctc.step(SIM_TIME_S + at_s, ctc_inputs(occupied))

    def values(
        self, *occupied: str, at_s: float = 0.0
    ) -> dict[str, tuple[int, int]]:
        """Each suggested block's speed and authority."""
        sent = self.step(occupied, at_s)["track_controller"]["suggestions"]
        for each in sent:
            self.assertEqual((each["train_id"], each["line"]),
                             ("G1", "Green"))
        return {
            each["block_id"]: (each["suggested_speed_mps"],
                               each["authority_blocks"])
            for each in sent
        }

    def release(self) -> None:
        """Release G1 onto a clear yard exit block."""
        self.assertEqual(self.step()["new_trains"],
                         [{"train_id": "G1", "line": "Green"}])

    def test_nothing_until_the_line_is_ready(self) -> None:
        for inputs in ({}, ctc_inputs(ready=False)):
            out = self.ctc.step(SIM_TIME_S, inputs)
            self.assertEqual(out["new_trains"], [])
            self.assertEqual(out["track_controller"], {
                "suggestions": [], "closed_blocks": [],
                "switch_commands": [],
            })
        self.assertFalse(self.ctc.released)

    def test_released_once_when_the_exit_block_is_clear(self) -> None:
        self.assertEqual(self.step(("63",))["new_trains"], [])
        self.release()
        self.assertTrue(self.ctc.released)
        self.assertEqual(self.step()["new_trains"], [])

    def test_authority_counts_down_to_the_stop(self) -> None:
        self.release()
        self.assertEqual(self.values("63"), {"63": (10, 2), "64": (10, 1)})
        self.assertEqual(self.values("64"), {"64": (10, 1), "65": (0, 0)})
        self.assertEqual(self.values("65"), {"65": (0, 0)})

    def test_the_stop_holds_then_releases_to_the_destination(self) -> None:
        self.release()
        self.values("63")
        self.values("64")
        self.assertEqual(self.values("65", at_s=0.0), {"65": (0, 0)})
        self.assertEqual(self.values("65", at_s=29.9), {"65": (0, 0)})
        self.assertEqual(
            self.values("65", at_s=30.0), {"65": (10, 2), "66": (8, 1)}
        )
        self.assertEqual(
            self.values("66", at_s=40.0), {"66": (8, 1), "67": (0, 0)}
        )
        self.assertEqual(self.values("67", at_s=50.0), {"67": (0, 0)})

    def test_authority_stops_short_of_an_occupied_block(self) -> None:
        # A failed block reads occupied (R33): it is not taken for the
        # train, and the train's authority stops before it.
        self.release()
        self.values("63")
        self.assertEqual(self.values("63", "65"), {"63": (10, 1),
                                                   "64": (0, 0)})
        self.assertEqual(self.values("64", "65"), {"64": (0, 0)})
        self.assertEqual(self.values("64"), {"64": (10, 1), "65": (0, 0)})

    def test_nothing_suggested_until_the_train_is_seen(self) -> None:
        self.release()
        self.assertEqual(self.values(), {})
        self.assertEqual(self.values("12"), {})

    def test_bad_routes_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            ScriptedCtc(CtcRoute("G1", "Green", ()))
        with self.assertRaises(ValueError):
            ScriptedCtc(CtcRoute(
                "G1", "Green", (RouteBlock("63", 1), RouteBlock("63", 1))
            ))

    def test_default_route_never_drops_two_blocks_of_authority_at_once(
        self,
    ) -> None:
        # The Train Controller reads a fall from 2 or more blocks
        # straight to none as a signal pickup failure.
        ctc = ScriptedCtc(GREEN_YARD_TO_DORMONT)
        ctc.step(SIM_TIME_S, ctc_inputs())
        last: int | None = None
        for at_s, block in enumerate(GREEN_YARD_TO_DORMONT.blocks):
            # One block a second, past the stop's hold where it is.
            time_s = at_s + (STOP_HOLD_S if at_s > 2 else 0.0)
            sent = ctc.step(
                SIM_TIME_S + time_s, ctc_inputs((block.block_id,))
            )["track_controller"]["suggestions"]
            authority = next(
                each["authority_blocks"] for each in sent
                if each["block_id"] == block.block_id
            )
            if last is not None and authority == 0:
                self.assertLess(last, 2)
            last = authority
        self.assertEqual(last, 0)

    def test_default_speeds_are_whole_and_within_each_limit(self) -> None:
        # R38, arbitration/suggested-speed-under-block-limit.
        with open(layout_dir() / LAYOUT_FILES["Green"],
                  encoding="utf-8") as handle:
            limits = {
                str(row["block_number"]): row["speed_limit_kmh"] / 3.6
                for row in json.load(handle)["blocks"]
            }
        for block in GREEN_YARD_TO_DORMONT.blocks:
            self.assertIsInstance(block.speed_mps, int)
            self.assertLessEqual(block.speed_mps, limits[block.block_id])


class SystemEdgesTest(unittest.TestCase):
    """Real edges for the wired modules, stub edges for the rest."""

    def setUp(self) -> None:
        self.edges = SystemEdges(ScriptedCtc(GREEN_YARD_TO_DORMONT))
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
        # No Track Controller has replied: nothing is commanded.
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

    def test_track_model_takes_the_track_controllers_commands(
        self,
    ) -> None:
        controller = self.inputs(TRACK_MODEL, {
            TRACK_CONTROLLER_SW: wayside_outputs(
                circuits={"63": (12, 2)}, lights={"62": "green"}
            ),
        })["controller"]
        self.assertEqual(controller["commanded_authority"],
                         {"GREEN K-63": 2})
        self.assertEqual(controller["signal_commands"],
                         {"GREEN K-64": "GREEN"})
        self.assertNotIn("heater_commands", controller)

    def test_track_controller_takes_the_track_models_read_back(
        self,
    ) -> None:
        self.assertEqual(self.inputs(TRACK_CONTROLLER_SW, {}), {
            "ctc": {"closed_blocks": [], "switch_commands": [],
                    "suggestions": []},
            "track_model": {"occupied_blocks": [], "switch_positions": [],
                            "crossings_active": [], "signal_aspects": []},
        })
        inputs = self.inputs(TRACK_CONTROLLER_SW, {
            TRACK_MODEL: track_model_outputs(("GREEN K-64", "RED C-9")),
        })
        self.assertEqual(inputs["track_model"]["occupied_blocks"],
                         [_green("64")])

    def test_the_stand_in_waits_for_the_waysides_then_suggests(
        self,
    ) -> None:
        # Fresh edges: no release from the CTC Office's stub. The
        # stand-in steps on the Track Controller's outputs of the tick
        # before, so each answer comes a tick after what it answers.
        edges = SystemEdges(ScriptedCtc(GREEN_YARD_TO_DORMONT))

        def complete(tick: int, fresh: dict[str, Any]) -> list[Any]:
            return edges.tick_completed(tick, SIM_TIME_S + tick * DT_S,
                                        fresh)

        self.assertEqual(complete(1, {
            TRACK_MODEL: track_model_outputs(),
            TRACK_CONTROLLER_SW: wayside_outputs(ready=False),
        }), [])
        self.assertEqual(
            complete(2, {TRACK_CONTROLLER_SW: wayside_outputs()}),
            [(TRACK_CONTROLLER_SW, "WAYSIDES_NOT_READY",
              "Green: GTC-03: no PLC program")],
        )
        self.assertEqual(
            complete(3, {TRACK_CONTROLLER_SW: wayside_outputs(
                occupied=("63",))}),
            [(TRACK_CONTROLLER_SW, "WAYSIDES_READY", "Green"),
             ("harness", "TRAIN_ADDED", "G1 on Green")],
        )
        self.assertEqual(
            edges.inputs_for(TRACK_CONTROLLER_SW, 4, SIM_TIME_S, {})[
                "ctc"]["suggestions"],
            [],
        )
        self.assertEqual(complete(4, {}), [])
        self.assertEqual(
            edges.inputs_for(TRACK_CONTROLLER_SW, 5, SIM_TIME_S, {})[
                "ctc"]["suggestions"],
            [{"block": _green("63"),
              "value": {"speed_mps": 12, "authority_blocks": 2}},
             {"block": _green("64"),
              "value": {"speed_mps": 12, "authority_blocks": 1}}],
        )

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
