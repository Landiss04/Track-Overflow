"""Tests for the module boundary: interface, Qt-free module, wire, errors.

Run from ``TrackCtrlSW``::

    .venv/Scripts/python -m unittest discover -s tests -v

None of these need Qt. They drive :class:`SwTrackController` exactly as
the central harness will: ``step(dt, inputs)`` and read the outputs.
"""

from __future__ import annotations

import dataclasses
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from track_ctrl import interface  # noqa: E402
from track_ctrl.errors import (  # noqa: E402
    InvalidInputError,
    InvalidProgramError,
    TrackControllerError,
    UnknownIdError,
    WireFormatError,
)
from track_ctrl.interface import (  # noqa: E402
    BlockKey,
    CtcInputs,
    Suggestion,
    TrackControllerInputs,
    TrackModelInputs,
)
from track_ctrl.controller import default_program_source  # noqa: E402
from track_ctrl.layout import LayoutError, build_default_system  # noqa: E402
from track_ctrl.module import SwTrackController  # noqa: E402
from track_ctrl import wire  # noqa: E402

DT = 0.1


def _green() -> SwTrackController:
    module = SwTrackController()
    for line in build_default_system():
        if line.key == "Green":
            module.load_track(line)
    module.load_starter_programs()
    return module


def _tick(
    module: SwTrackController,
    time_s: float = 1.0,
    ctc: CtcInputs | None = None,
    track_model: TrackModelInputs | None = None,
) -> interface.TrackControllerOutputs:
    return module.step(
        DT,
        TrackControllerInputs(
            time_s=time_s,
            ctc=ctc or CtcInputs(),
            track_model=track_model or TrackModelInputs(),
        ),
    )


def _switch_key(module: SwTrackController) -> BlockKey:
    for wayside in module.snapshot().waysides:
        if wayside.switches:
            return wayside.switches[0].switch
    raise AssertionError("no switch on the line")


class ContractShape(unittest.TestCase):
    """What the module does not know, it must not carry."""

    def test_no_failure_or_heater_field_crosses_the_boundary(self) -> None:
        names: set[str] = set()
        for each in vars(interface).values():
            if dataclasses.is_dataclass(each):
                names |= {field.name for field in dataclasses.fields(each)}
        for name in names:
            self.assertNotIn("failure", name)
            self.assertNotIn("heater", name)
            self.assertNotIn("train", name)

    def test_block_key_carries_the_line_not_the_section(self) -> None:
        self.assertEqual(
            [field.name for field in dataclasses.fields(BlockKey)],
            ["line", "block_id"],
        )
        self.assertNotEqual(BlockKey("Green", "12"), BlockKey("Red", "12"))

    def test_every_error_shares_one_base(self) -> None:
        for error in (
            InvalidInputError, UnknownIdError, InvalidProgramError,
            WireFormatError, LayoutError,
        ):
            self.assertTrue(issubclass(error, TrackControllerError))
        self.assertTrue(issubclass(InvalidProgramError, ValueError))
        self.assertTrue(issubclass(UnknownIdError, KeyError))


class Stepping(unittest.TestCase):
    def test_every_output_is_keyed_by_line_and_block(self) -> None:
        module = _green()
        key = _switch_key(module)
        suggestions = {key: Suggestion(10, 3)}
        out = _tick(module, ctc=CtcInputs(suggestions=suggestions))
        self.assertIn(key, out.track_model.switch_commands)
        self.assertIn(key, out.track_model.signal_commands)
        for each in out.track_model.track_circuits:
            self.assertEqual(each.line, "Green")

    def test_suggestion_per_block_reaches_that_blocks_circuit(self) -> None:
        module = _green()
        key = BlockKey("Green", "8")
        out = _tick(module, ctc=CtcInputs(
            suggestions={key: Suggestion(9, 2)}))
        self.assertEqual(list(out.track_model.track_circuits), [key])
        circuit = out.track_model.track_circuits[key]
        self.assertLessEqual(circuit.speed_mps, 9)
        self.assertLessEqual(circuit.authority_blocks, 2)

    def test_block_without_suggestion_sends_nothing(self) -> None:
        out = _tick(_green())
        self.assertEqual(out.track_model.track_circuits, {})

    def test_a_failure_is_just_an_occupied_block(self) -> None:
        module = _green()
        key = BlockKey("Green", "8")
        out = _tick(
            module,
            ctc=CtcInputs(suggestions={key: Suggestion(9, 2)}),
            track_model=TrackModelInputs(occupied_blocks=frozenset({key})),
        )
        report = next(
            each for each in out.ctc_reports if key in each.blocks
        )
        self.assertTrue(report.blocks[key].occupied)

    def test_report_carries_the_track_models_readback(self) -> None:
        module = _green()
        key = _switch_key(module)
        out = _tick(module, track_model=TrackModelInputs(
            switch_positions={key: "reverse"},
            signal_aspects={key: "yellow"},
        ))
        report = next(
            each for each in out.ctc_reports if key in each.blocks
        )
        self.assertEqual(report.blocks[key].switch_position, "reverse")
        self.assertEqual(report.blocks[key].signal_aspect, "yellow")
        other = next(
            block for block in report.blocks
            if block != key and report.blocks[block].switch_position is None
        )
        self.assertFalse(report.blocks[other].occupied)

    def test_one_report_per_wayside_in_load_order(self) -> None:
        module = _green()
        out = _tick(module)
        self.assertEqual(
            tuple(each.wayside_id for each in out.ctc_reports),
            module.wayside_ids,
        )
        self.assertEqual(out.ctc_reports[0].sent_at_s, 1.0)

    def test_a_ctc_switch_command_is_obeyed_and_is_maintenance(self) -> None:
        # The CTC sends no mode flag. A command in effect is obeyed, and
        # is how the module learns the dispatcher is in maintenance.
        module = _green()
        key = _switch_key(module)
        free = _tick(module, track_model=TrackModelInputs())
        self.assertFalse(module.snapshot().maintenance_mode)
        want: interface.SwitchPosition = (
            "reverse" if free.track_model.switch_commands[key] == "normal"
            else "normal"
        )
        obeyed = _tick(module, ctc=CtcInputs(
            switch_commands={key: want})).track_model
        self.assertEqual(obeyed.switch_commands[key], want)
        self.assertTrue(module.snapshot().maintenance_mode)
        self.assertTrue(module.maintenance)

    def test_withdrawing_the_command_ends_maintenance(self) -> None:
        module = _green()
        key = _switch_key(module)
        _tick(module, ctc=CtcInputs(switch_commands={key: "reverse"}))
        self.assertTrue(module.maintenance)
        _tick(module)
        self.assertFalse(module.maintenance)

    def test_a_command_for_a_switch_it_does_not_govern_is_not_maintenance(
        self,
    ) -> None:
        module = _green()
        _tick(module, ctc=CtcInputs(
            switch_commands={BlockKey("Red", "12"): "reverse"}))
        self.assertFalse(module.maintenance)

    def test_there_is_no_maintenance_flag_on_the_boundary(self) -> None:
        names = {field.name for field in dataclasses.fields(CtcInputs)}
        self.assertNotIn("maintenance_mode", names)

    def test_closed_block_holds_its_circuit_at_zero(self) -> None:
        module = _green()
        key = BlockKey("Green", "8")
        out = _tick(module, ctc=CtcInputs(
            closed_blocks=frozenset({key}),
            suggestions={key: Suggestion(9, 2)},
        ))
        circuit = out.track_model.track_circuits[key]
        self.assertEqual((circuit.speed_mps, circuit.authority_blocks),
                         (0, 0))

    def test_unknown_blocks_are_ignored(self) -> None:
        module = _green()
        stray = BlockKey("Blue", "3")
        out = _tick(module, ctc=CtcInputs(
            suggestions={stray: Suggestion(5, 1)},
            closed_blocks=frozenset({stray}),
        ), track_model=TrackModelInputs(occupied_blocks=frozenset({stray})))
        self.assertNotIn(stray, out.track_model.track_circuits)

    def test_snapshot_follows_the_last_tick(self) -> None:
        module = _green()
        self.assertEqual(module.snapshot().ticks, 0)
        self.assertIsNone(module.snapshot().time_s)
        _tick(module, time_s=5.0)
        snap = module.snapshot()
        self.assertEqual((snap.ticks, snap.time_s), (1, 5.0))
        self.assertTrue(all(each.program for each in snap.waysides))
        module.reset()
        self.assertEqual(module.snapshot().ticks, 0)


class StarterSeparation(unittest.TestCase):
    """The starter program holds a train beside another, nothing more.

    The CTC Office suggests for the block a train is in and preloads
    the next block on its route (truth ``signals/suggested-speed``). The
    next block has no train in it yet, so it passes its suggestion and
    the train finds its values there as it enters.
    """

    @staticmethod
    def circuits(
        occupied: set[str], suggested: dict[str, tuple[int, int]]
    ) -> dict[str, tuple[int, int]]:
        out = _tick(
            _green(),
            ctc=CtcInputs(suggestions={
                BlockKey("Green", block): Suggestion(*values)
                for block, values in suggested.items()
            }),
            track_model=TrackModelInputs(occupied_blocks=frozenset(
                BlockKey("Green", block) for block in occupied
            )),
        )
        return {
            key.block_id: (circuit.speed_mps, circuit.authority_blocks)
            for key, circuit in out.track_model.track_circuits.items()
        }

    def test_a_preloaded_next_block_passes_its_suggestion(self) -> None:
        self.assertEqual(
            self.circuits({"64"}, {"64": (12, 2), "65": (12, 1)}),
            {"64": (12, 2), "65": (12, 1)},
        )

    def test_a_train_behind_another_is_held_and_the_leader_is_not(
        self,
    ) -> None:
        # Block 64 leads to 65 on the Green Line. Only the train behind
        # is held: holding the leader too would stall both for good.
        self.assertEqual(
            self.circuits({"64", "65"}, {"64": (12, 2), "65": (12, 1)}),
            {"64": (0, 0), "65": (12, 1)},
        )

    def test_a_convoy_is_held_only_behind_its_leader(self) -> None:
        # Three trains in 62, 63 and 64: the two behind wait, the front
        # one moves, so the convoy can clear instead of deadlocking.
        self.assertEqual(
            self.circuits(
                {"62", "63", "64"},
                {"62": (12, 1), "63": (0, 0), "64": (12, 2)},
            ),
            {"62": (0, 0), "63": (0, 0), "64": (12, 2)},
        )


class Startup(unittest.TestCase):
    """A vital controller stalls until a line and every program are loaded."""

    @staticmethod
    def bare() -> SwTrackController:
        module = SwTrackController()
        for line in build_default_system():
            if line.key == "Green":
                module.load_track(line)
        return module

    def hold_is_total(self, out: interface.TrackControllerOutputs) -> None:
        self.assertFalse(out.ready)
        for circuit in out.track_model.track_circuits.values():
            self.assertEqual(
                (circuit.speed_mps, circuit.authority_blocks), (0, 0))
        self.assertTrue(
            all(each == "red" for each in out.track_model.signal_commands.values()))
        self.assertTrue(all(out.track_model.crossing_commands.values()))

    def suggest_all(self) -> CtcInputs:
        return CtcInputs(suggestions={
            BlockKey("Green", str(block)): Suggestion(10, 3)
            for block in range(1, 30)
        })

    def test_a_new_module_is_not_ready_and_says_why(self) -> None:
        module = SwTrackController()
        self.assertFalse(module.ready)
        self.assertEqual(module.not_ready_reasons(), ("no track is loaded",))
        out = _tick(module, ctc=self.suggest_all())
        self.assertFalse(out.ready)
        self.assertEqual(out.track_model.track_circuits, {})
        snap = module.snapshot()
        self.assertFalse(snap.ready)
        self.assertEqual(snap.not_ready, ("no track is loaded",))

    def test_a_loaded_line_without_programs_stalls(self) -> None:
        module = self.bare()
        self.assertEqual(
            len(module.not_ready_reasons()), len(module.wayside_ids))
        self.hold_is_total(_tick(module, ctc=self.suggest_all()))

    def test_a_wayside_with_a_program_runs_without_waiting_for_the_rest(
        self,
    ) -> None:
        module = self.bare()
        ids = module.wayside_ids
        # Everything but the last wayside is programmed.
        for wayside_id in ids[:-1]:
            controller = module.controller(wayside_id)
            module.load_program(
                wayside_id, default_program_source(controller), "a.plc")
        self.assertEqual(
            module.not_ready_reasons(), (f"{ids[-1]} has no PLC program",))
        out = _tick(module, ctc=self.suggest_all())
        self.assertFalse(out.ready)
        unprogrammed = {
            module.controller(ids[-1]).key(block_id)
            for block_id in module.controller(ids[-1]).config.block_ids
        }
        circuits = out.track_model.track_circuits
        # The programmed waysides transmit; the one without a program
        # transmits nothing.
        self.assertTrue(circuits)
        self.assertFalse(unprogrammed & set(circuits))

    def test_the_last_program_starts_the_module(self) -> None:
        module = self.bare()
        module.load_starter_programs()
        self.assertTrue(module.ready)
        out = _tick(module, ctc=self.suggest_all())
        self.assertTrue(out.ready)
        self.assertTrue(any(
            circuit.speed_mps for circuit in out.track_model.track_circuits.values()))
        self.assertEqual(module.not_ready_reasons(), ())

    def test_loading_the_last_program_by_hand_makes_it_ready(self) -> None:
        module = self.bare()
        for wayside_id in module.wayside_ids:
            self.assertFalse(module.ready)
            module.load_program(
                wayside_id,
                default_program_source(module.controller(wayside_id)),
                "a.plc",
            )
        self.assertTrue(module.ready)

    def test_a_new_line_or_a_reset_stalls_a_ready_module_again(self) -> None:
        module = self.bare()
        module.load_starter_programs()
        self.assertTrue(module.ready)
        for line in build_default_system():
            if line.key == "Red":
                module.load_track(line)
        self.assertFalse(module.ready)
        module.load_starter_programs()
        self.assertTrue(module.ready)
        module.reset()
        self.assertFalse(module.ready)

    def test_a_program_that_is_refused_does_not_start_the_module(self) -> None:
        module = self.bare()
        with self.assertRaises(InvalidProgramError):
            module.load_program(module.wayside_ids[0], "VAR_IN NOPE\n", "x.plc")
        self.assertFalse(module.ready)

    def test_each_wayside_reports_its_own_readiness(self) -> None:
        module = self.bare()
        ids = module.wayside_ids
        # Program every wayside but the second and the last.
        skipped = {ids[1], ids[-1]}
        for wayside_id in ids:
            if wayside_id not in skipped:
                module.load_program(
                    wayside_id,
                    default_program_source(module.controller(wayside_id)),
                    "a.plc",
                )
        out = _tick(module, ctc=self.suggest_all())
        self.assertFalse(out.ready)
        self.assertEqual(
            {report.wayside_id: report.ready for report in out.ctc_reports},
            {wayside_id: wayside_id not in skipped for wayside_id in ids},
        )
        self.assertEqual(
            {report.wayside_id for report in out.not_ready()}, skipped)
        for report in out.ctc_reports:
            self.assertEqual(report.line, "Green")
            self.assertEqual(
                report.reason,
                "" if report.ready else "no PLC program")

    def test_the_whole_is_ready_only_when_every_wayside_is(self) -> None:
        module = self.bare()
        self.assertFalse(interface.TrackControllerOutputs().ready)
        module.load_starter_programs()
        out = _tick(module, ctc=self.suggest_all())
        self.assertTrue(all(report.ready for report in out.ctc_reports))
        self.assertTrue(out.ready)
        self.assertEqual(out.not_ready(), ())

    def test_readiness_crosses_the_wire_per_wayside(self) -> None:
        module = self.bare()
        first = module.wayside_ids[0]
        module.load_program(
            first, default_program_source(module.controller(first)), "a.plc")
        out = _tick(module)
        text = json.dumps(wire.outputs_to_wire(out))
        back = wire.outputs_from_wire(json.loads(text))
        self.assertEqual(back, out)
        self.assertTrue(back.ctc_reports[0].ready)
        self.assertFalse(back.ctc_reports[1].ready)
        self.assertNotIn("ready", json.loads(text))
        bad = json.loads(text)
        bad["ctc_reports"][0]["ready"] = "yes"
        with self.assertRaises(WireFormatError):
            wire.outputs_from_wire(bad)
        del bad["ctc_reports"][0]["ready"]
        with self.assertRaises(WireFormatError):
            wire.outputs_from_wire(bad)


class Rejection(unittest.TestCase):
    def _bad(self, dt: float, inputs: TrackControllerInputs) -> None:
        module = _green()
        before = module.snapshot()
        with self.assertRaises(InvalidInputError):
            module.step(dt, inputs)
        self.assertEqual(module.snapshot(), before)

    def test_bad_dt(self) -> None:
        for dt in (0.0, -0.1, float("nan"), float("inf")):
            self._bad(dt, TrackControllerInputs(time_s=1.0))

    def test_bad_time(self) -> None:
        self._bad(DT, TrackControllerInputs(time_s=float("nan")))
        self._bad(DT, TrackControllerInputs(time_s=-1.0))

    def test_bad_suggestions(self) -> None:
        key = BlockKey("Green", "8")
        for bad in (Suggestion(-1, 1), Suggestion(1, -1),
                    Suggestion(1.5, 1), Suggestion(1, True)):  # type: ignore
            self._bad(DT, TrackControllerInputs(
                time_s=1.0, ctc=CtcInputs(suggestions={key: bad})))

    def test_bad_position_and_aspect(self) -> None:
        key = BlockKey("Green", "12")
        self._bad(DT, TrackControllerInputs(time_s=1.0, ctc=CtcInputs(
            switch_commands={key: "up"})))  # type: ignore[dict-item]
        self._bad(DT, TrackControllerInputs(
            time_s=1.0, track_model=TrackModelInputs(
                signal_aspects={key: "blue"})))  # type: ignore[dict-item]


class Programs(unittest.TestCase):
    def test_unknown_wayside(self) -> None:
        with self.assertRaises(UnknownIdError):
            _green().load_program("NOPE", "", "x.plc")

    def test_program_with_errors_is_refused(self) -> None:
        module = _green()
        wayside = module.wayside_ids[0]
        before = module.snapshot().waysides[0].program
        with self.assertRaises(InvalidProgramError):
            module.load_program(wayside, "VAR_IN NOT_A_NAME\n", "bad.plc")
        self.assertEqual(module.snapshot().waysides[0].program, before)

    def test_good_program_is_committed(self) -> None:
        module = _green()
        wayside = module.wayside_ids[0]
        source = module._waysides[wayside].history[0].source
        info = module.load_program(wayside, source, "again.plc")
        self.assertEqual(info.file_name, "again.plc")
        self.assertEqual(info.iteration, 2)
        self.assertEqual(module.snapshot().waysides[0].program, info)


class Wire(unittest.TestCase):
    def _busy_inputs(self) -> TrackControllerInputs:
        key = BlockKey("Green", "8")
        other = BlockKey("Green", "12")
        return TrackControllerInputs(
            time_s=12.5,
            ctc=CtcInputs(
                closed_blocks=frozenset({other}),
                switch_commands={other: "reverse"},
                suggestions={key: Suggestion(9, 2)},
            ),
            track_model=TrackModelInputs(
                occupied_blocks=frozenset({key}),
                switch_positions={other: "normal"},
                crossings_active={BlockKey("Green", "19"): True},
                signal_aspects={other: "super_green"},
            ),
        )

    def test_inputs_round_trip_through_json(self) -> None:
        inputs = self._busy_inputs()
        text = json.dumps(wire.inputs_to_wire(inputs))
        self.assertEqual(wire.inputs_from_wire(json.loads(text)), inputs)

    def test_outputs_round_trip_through_json(self) -> None:
        module = _green()
        outputs = _tick(module, ctc=CtcInputs(
            suggestions={BlockKey("Green", "8"): Suggestion(9, 2)}))
        text = json.dumps(wire.outputs_to_wire(outputs))
        self.assertEqual(wire.outputs_from_wire(json.loads(text)), outputs)

    def test_snapshot_is_json_ready(self) -> None:
        module = _green()
        _tick(module)
        json.dumps(wire.snapshot_to_wire(module.snapshot()))

    def test_decoding_is_strict(self) -> None:
        good = wire.inputs_to_wire(self._busy_inputs())

        def broken(change: object) -> dict[str, object]:
            copy = json.loads(json.dumps(good))
            change(copy)  # type: ignore[operator]
            return copy

        cases = [
            lambda d: d.pop("time_s"),
            lambda d: d.update(extra=1),
            lambda d: d.update(time_s="soon"),
            lambda d: d.update(time_s=float("nan")),
            lambda d: d["ctc"].update(maintenance_mode=True),
            lambda d: d["ctc"]["suggestions"][0]["value"].update(
                speed_mps=-1),
            lambda d: d["ctc"]["suggestions"][0]["value"].update(
                speed_mps=1.5),
            lambda d: d["ctc"]["switch_commands"][0].update(value="sideways"),
            lambda d: d["ctc"]["closed_blocks"].append({"line": "Green"}),
            lambda d: d["track_model"]["signal_aspects"][0].update(
                value="blue"),
            lambda d: d["track_model"]["occupied_blocks"].append(
                d["track_model"]["occupied_blocks"][0]) or
            d["ctc"].update(suggestions=d["ctc"]["suggestions"] * 2),
            lambda d: d.update(ctc=[]),
        ]
        for change in cases:
            with self.assertRaises(WireFormatError):
                wire.inputs_from_wire(broken(change))

    def test_outputs_decoding_is_strict(self) -> None:
        with self.assertRaises(WireFormatError):
            wire.outputs_from_wire({"track_model": {}, "ctc_reports": []})
        with self.assertRaises(WireFormatError):
            wire.outputs_from_wire("nothing")


class RouteRequests(unittest.TestCase):
    """The CTC Office's route requests: what a routed train needs a switch
    set to. Not a command: they do not set maintenance mode, and they reach
    only the program (REQSW_s, REQREV_s)."""

    @staticmethod
    def key(block: str) -> BlockKey:
        return BlockKey("Green", block)

    def position(
        self, ctc: CtcInputs, occupied: set[str] | None = None,
        positions: dict[str, str] | None = None,
    ) -> tuple[str, bool]:
        module = _green()
        out = _tick(
            module, ctc=ctc,
            track_model=TrackModelInputs(
                occupied_blocks=frozenset(
                    self.key(b) for b in (occupied or ())),
                switch_positions={
                    self.key(b): v for b, v in (positions or {}).items()},
            ),
        )
        return (
            out.track_model.switch_commands.get(self.key("12"), "?"),
            module.snapshot().maintenance_mode,
        )

    def test_a_request_moves_a_switch_and_is_not_maintenance(self) -> None:
        # Switch 12: points on 13, normal to 12, reverse to 1.
        ctc = CtcInputs(route_requests={self.key("12"): "reverse"})
        self.assertEqual(self.position(ctc), ("reverse", False))

    def test_a_maintenance_command_beats_a_request(self) -> None:
        ctc = CtcInputs(
            switch_commands={self.key("12"): "normal"},
            route_requests={self.key("12"): "reverse"},
        )
        self.assertEqual(self.position(ctc), ("normal", True))

    def test_a_train_on_the_points_locks_the_switch(self) -> None:
        # The request is for reverse, but a train on the points block
        # (13) holds the switch where the Track Model reports it.
        ctc = CtcInputs(route_requests={self.key("12"): "reverse"})
        position, _ = self.position(
            ctc, occupied={"13"}, positions={"12": "normal"})
        self.assertEqual(position, "normal")

    def test_a_request_never_moves_a_switch_into_a_closed_leg(self) -> None:
        ctc = CtcInputs(
            closed_blocks=frozenset({self.key("1")}),
            route_requests={self.key("12"): "reverse"},
        )
        position, _ = self.position(ctc)
        self.assertEqual(position, "normal")

    def test_a_program_can_read_the_request(self) -> None:
        controller = _green().controller("GTC-01")
        self.assertIn("REQSW_12", controller.input_names())
        self.assertIn("REQREV_12", controller.input_names())
        self.assertIn("REQSW_12", default_program_source(controller))

    def test_a_bad_request_position_is_refused(self) -> None:
        with self.assertRaises(InvalidInputError):
            _tick(_green(), ctc=CtcInputs(
                route_requests={self.key("12"): "sideways"}))  # type: ignore[dict-item]

    def test_requests_cross_the_wire_and_may_be_left_out(self) -> None:
        inputs = TrackControllerInputs(
            time_s=1.0,
            ctc=CtcInputs(route_requests={self.key("76"): "normal"}),
        )
        sent = wire.inputs_to_wire(inputs)
        self.assertEqual(
            sent["ctc"]["route_requests"],
            [{"block": {"line": "Green", "block_id": "76"},
              "value": "normal"}],
        )
        self.assertEqual(wire.inputs_from_wire(json.loads(json.dumps(sent))),
                         inputs)
        # A sender that predates the field leaves it out: none requested.
        del sent["ctc"]["route_requests"]
        self.assertEqual(
            wire.inputs_from_wire(sent).ctc.route_requests, {})


class LoopGuards(unittest.TestCase):
    """A loop that drains through a two-way section is let out first:
    while a train is in the loop's first blocks and another approaches
    the section from its other end, the approach is held and the switches
    are set for the loop's way out. The waysides tell each other the
    blocks over the link between track controllers (``PEER_OCC_n``)."""

    @staticmethod
    def key(block: str) -> BlockKey:
        return BlockKey("Green", block)

    def run_it(
        self, occupied: set[str], watched: tuple[str, ...],
        requests: dict[str, str] | None = None,
    ) -> tuple[dict[str, tuple[int, int]], dict[str, str]]:
        out = _tick(
            _green(),
            ctc=CtcInputs(
                suggestions={self.key(b): Suggestion(12, 4) for b in watched},
                route_requests={
                    self.key(s): p  # type: ignore[misc]
                    for s, p in (requests or {}).items()},
            ),
            track_model=TrackModelInputs(
                occupied_blocks=frozenset(self.key(b) for b in occupied)),
        )
        circuits = {
            k.block_id: (c.speed_mps, c.authority_blocks)
            for k, c in out.track_model.track_circuits.items()
            if k.block_id in watched
        }
        switches = {
            k.block_id: v
            for k, v in out.track_model.switch_commands.items()
        }
        return circuits, switches

    def test_each_wayside_is_told_the_blocks_it_needs(self) -> None:
        module = _green()
        peers = {
            wayside_id: module.controller(wayside_id).config.peer_blocks
            for wayside_id in module.wayside_ids
        }
        self.assertEqual(peers["GTC-03"], ())
        self.assertEqual(peers["GTC-04"], ())
        # GTC-01 and GTC-02 set the top loop's switches, so they are also
        # told the part of 13..28 the other owns.
        self.assertEqual(peers["GTC-01"][-3:], ("26", "27", "28"))
        self.assertEqual(peers["GTC-06"], ("12", "11", "10", "9", "8", "7"))
        self.assertEqual(peers["GTC-05"], ())
        self.assertIn("PEER_OCC_145",
                      module.controller("GTC-01").input_names())

    def test_the_top_loop_drains_the_same_way(self) -> None:
        circuits, switches = self.run_it({"10", "147"}, ("10", "147"))
        self.assertEqual(circuits["147"], (0, 0))
        self.assertEqual((switches["12"], switches["28"]),
                         ("reverse", "normal"))

    def test_the_top_loop_waits_for_13_to_28_to_clear(self) -> None:
        # 28 stands reverse at rest, for a train from 150.
        circuits, switches = self.run_it(
            {"10", "147", "20"}, ("10", "147"))
        self.assertEqual(circuits["147"], (0, 0))
        self.assertEqual((switches["12"], switches["28"]),
                         ("normal", "reverse"))



class CountGuardGtc04(unittest.TestCase):
    """GTC-04 tells GTC-03 how many of its blocks (76..100) are
    occupied; over 5, GTC-03 holds the train on 75."""

    @staticmethod
    def key(block: str) -> BlockKey:
        return BlockKey("Green", block)

    def block_75(self, occupied: set[str]) -> tuple[int, int]:
        out = _tick(
            _green(),
            ctc=CtcInputs(suggestions={self.key("75"): Suggestion(12, 4)}),
            track_model=TrackModelInputs(
                occupied_blocks=frozenset(self.key(b) for b in occupied)),
        )
        circuit = out.track_model.track_circuits[self.key("75")]
        return (circuit.speed_mps, circuit.authority_blocks)

    def test_gtc_03_reads_gtc_04s_count(self) -> None:
        controller = _green().controller("GTC-03")
        names = controller.input_names()
        self.assertIn("PEER_CNT_GTC04_0", names)
        self.assertIn("PEER_CNT_GTC04_4", names)
        self.assertNotIn("PEER_CNT_GTC04_5", names)

    def test_five_trains_in_gtc_04_hold_nothing(self) -> None:
        crowd = {"80", "86", "90", "94", "98"}
        self.assertGreater(self.block_75(crowd | {"75"})[1], 0)

    def test_six_trains_in_gtc_04_hold_the_train_on_75(self) -> None:
        crowd = {"80", "86", "90", "94", "98", "100"}
        self.assertEqual(self.block_75(crowd | {"75"}), (0, 0))

    def test_every_count_up_to_all_25_blocks(self) -> None:
        blocks = [str(n) for n in range(76, 101)]
        for count in range(0, 26):
            held = self.block_75(set(blocks[:count]) | {"75"})
            self.assertEqual(held == (0, 0), count > 5, count)


if __name__ == "__main__":
    unittest.main()
