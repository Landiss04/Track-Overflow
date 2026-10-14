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

    def test_ctc_switch_command_only_obeyed_in_maintenance(self) -> None:
        module = _green()
        key = _switch_key(module)
        normal = _tick(module, track_model=TrackModelInputs()).track_model
        want: interface.SwitchPosition = (
            "reverse" if normal.switch_commands[key] == "normal"
            else "normal"
        )
        ignored = _tick(module, ctc=CtcInputs(
            switch_commands={key: want})).track_model
        self.assertEqual(
            ignored.switch_commands[key], normal.switch_commands[key]
        )
        obeyed = _tick(module, ctc=CtcInputs(
            maintenance_mode=True, switch_commands={key: want}
        )).track_model
        self.assertEqual(obeyed.switch_commands[key], want)
        self.assertTrue(module.snapshot().maintenance_mode)

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

    def test_one_missing_program_stalls_every_wayside(self) -> None:
        module = self.bare()
        ids = module.wayside_ids
        # Everything but the last wayside is programmed.
        for wayside_id in ids[:-1]:
            controller = module.controller(wayside_id)
            module.load_program(
                wayside_id, default_program_source(controller), "a.plc")
        self.assertEqual(
            module.not_ready_reasons(), (f"{ids[-1]} has no PLC program",))
        out = self._stalled_with_programs(module)
        self.assertFalse(out.ready)
        # The programmed waysides are held too: nothing runs.
        self.assertFalse(any(
            circuit.speed_mps for circuit in out.track_model.track_circuits.values()))

    def _stalled_with_programs(
        self, module: SwTrackController
    ) -> interface.TrackControllerOutputs:
        out = _tick(module, ctc=self.suggest_all())
        self.hold_is_total(out)
        return out

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

    def test_ready_crosses_the_wire(self) -> None:
        for ready in (False, True):
            out = interface.TrackControllerOutputs(ready=ready)
            text = json.dumps(wire.outputs_to_wire(out))
            self.assertEqual(wire.outputs_from_wire(json.loads(text)), out)
        bad = wire.outputs_to_wire(interface.TrackControllerOutputs())
        bad["ready"] = "yes"
        with self.assertRaises(WireFormatError):
            wire.outputs_from_wire(bad)
        del bad["ready"]
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
        source = module._waysides[wayside].controller.history[0].source
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
                maintenance_mode=True,
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
            lambda d: d["ctc"].update(maintenance_mode=1),
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


if __name__ == "__main__":
    unittest.main()
