"""The module: scans, the vital layer, maintenance and the report."""

from __future__ import annotations

import math
import unittest
from dataclasses import replace
from unittest import mock

from track_ctrl_hw.controller import HwTrackController
from track_ctrl_hw.errors import (
    InvalidInputError,
    InvalidTimeStepError,
    PlcError,
    TerritoryError,
)
from track_ctrl_hw.interface import (
    CtcInputs,
    Suggestion,
    TrackCircuitCommand,
    TrackController,
    TrackControllerInputs,
)
from track_ctrl_hw.plc import Program
from track_ctrl_hw.territory import parse_territory

from tests.support import inputs, keys, loaded, program_source, territory

CLEAR_RUN = "VAR_IN MAINT\n"


def circuits(controller: HwTrackController, **kwargs: object):
    out = controller.step(0.1, inputs(controller, **kwargs))  # type: ignore
    by_number = {
        k.block_id: v for k, v in out.track_model.track_circuits.items()
    }
    return out, by_number


class Contract(unittest.TestCase):
    def test_satisfies_the_protocol(self) -> None:
        controller: TrackController = HwTrackController()
        self.assertIsNotNone(controller)
        for name in ("step", "snapshot", "load_territory", "load_program",
                     "reset"):
            self.assertTrue(callable(getattr(HwTrackController, name)))

    def test_rejects_bad_time_steps(self) -> None:
        controller = loaded(1)
        for dt in (0, -0.1, math.inf, math.nan, True, "0.1"):
            with self.subTest(dt=dt), self.assertRaises(InvalidTimeStepError):
                controller.step(dt, inputs(controller))  # type: ignore

    def test_rejects_bad_inputs_before_any_change(self) -> None:
        controller = loaded(1)
        k = keys(controller)
        before = controller.snapshot()
        bad = [
            replace(inputs(controller), time_s=-1),
            replace(inputs(controller), time_s=math.nan),
            replace(inputs(controller), ctc=CtcInputs(
                suggestions={k["3"]: Suggestion(-1, 2)})),
            replace(inputs(controller), ctc=CtcInputs(
                suggestions={k["3"]: Suggestion(5.5, 2)})),  # type: ignore
            replace(inputs(controller), ctc=CtcInputs(
                switch_commands={k["12"]: "sideways"})),  # type: ignore
            replace(inputs(controller), ctc=CtcInputs(
                maintenance_mode=1)),  # type: ignore
        ]
        for case in bad:
            with self.subTest(case), self.assertRaises(InvalidInputError):
                controller.step(0.1, case)
        self.assertEqual(controller.snapshot(), before)

    def test_ignores_blocks_it_does_not_govern(self) -> None:
        controller = loaded(1)
        other = replace(keys(controller)["3"], line="Red")
        step = TrackControllerInputs(
            time_s=1.0, ctc=CtcInputs(suggestions={other: Suggestion(5, 5)})
        )
        out = controller.step(0.1, step)
        self.assertEqual(out.track_model.track_circuits, {})


class Loading(unittest.TestCase):
    def test_one_line_only(self) -> None:
        controller = loaded(1, programs=False)
        red = replace(territory(2), line="Red")
        with self.assertRaises(TerritoryError):
            controller.load_territory(red)

    def test_a_block_belongs_to_one_wayside(self) -> None:
        controller = loaded(1, programs=False)
        clash = replace(territory(2), wayside_id="9",
                        blocks=territory(1).blocks[:2], switches=(),
                        crossings=())
        with self.assertRaises(TerritoryError):
            controller.load_territory(clash)

    def test_reload_keeps_a_program_that_fits(self) -> None:
        controller = loaded(1)
        self.assertEqual(controller.load_territory(territory(1)), ())
        self.assertIsNotNone(controller.snapshot().waysides[0].program)

    def test_reload_unloads_a_program_that_does_not_fit(self) -> None:
        controller = loaded(1)
        smaller = replace(territory(1), blocks=territory(1).blocks[10:])
        smaller = parse_territory({
            "line": "Green", "wayside": "1",
            "blocks": [
                {"block_number": int(b.key.block_id), "section": b.key.section,
                 "length_m": b.length_m, "speed_limit_kmh": 45}
                for b in smaller.blocks
            ],
        })
        notices = controller.load_territory(smaller)
        self.assertEqual(len(notices), 1)
        self.assertIsNone(controller.snapshot().waysides[0].program)

    def test_program_must_fit_the_wayside(self) -> None:
        controller = loaded(1, programs=False)
        for source in ("VAR_IN OCC_99\n", "VAR_OUT SW_13\n", "X := (\n"):
            with self.subTest(source), self.assertRaises(PlcError):
                controller.load_program("1", source, "bad.plc")
        with self.assertRaises(PlcError):
            controller.load_program("7", "VAR_IN MAINT\n", "x.plc")

    def test_samples_compile_cleanly(self) -> None:
        controller = loaded(1, 2, 3)
        for wayside in controller.snapshot().waysides:
            self.assertEqual(wayside.program.warnings, ())


class Restrictive(unittest.TestCase):
    def test_no_program_holds_everything(self) -> None:
        controller = loaded(1, programs=False)
        out, by_number = circuits(
            controller, suggestions={"3": (10, 4)}, occupied=["3"]
        )
        self.assertEqual(by_number["3"], TrackCircuitCommand(0, 0))
        signals = list(out.track_model.signal_commands.values())
        self.assertEqual(signals, ["red"])
        self.assertTrue(all(out.track_model.crossing_commands.values()))

    def test_new_program_holds_until_its_first_scan(self) -> None:
        controller = loaded(1)
        circuits(controller, suggestions={"3": (10, 4)})
        controller.load_program("1", program_source(1), "again.plc")
        wayside = controller.snapshot().waysides[0]
        self.assertEqual(set(wayside.signal_commands.values()), {"red"})
        self.assertEqual(
            {k.block_id: v for k, v in wayside.track_circuits.items()},
            {"3": TrackCircuitCommand(0, 0)},
        )

    def test_channel_disagreement_is_a_latched_vital_fault(self) -> None:
        controller = loaded(1)
        real = Program.scan_b

        def broken(program: Program, image: object) -> dict[str, bool]:
            values = real(program, image)  # type: ignore[arg-type]
            values["AUTH_3"] = not values["AUTH_3"]
            return values

        with mock.patch.object(Program, "scan_b", broken):
            _, by_number = circuits(controller, suggestions={"3": (10, 4)})
        self.assertEqual(by_number["3"], TrackCircuitCommand(0, 0))
        scan = controller.snapshot().waysides[0].scan
        self.assertFalse(scan.channels_agree)
        self.assertIn("AUTH_3", scan.vital_fault)
        # Latched: a healthy scan does not clear it...
        _, by_number = circuits(controller, suggestions={"3": (10, 4)})
        self.assertEqual(by_number["3"], TrackCircuitCommand(0, 0))
        # ...a new program does.
        controller.load_program("1", program_source(1), "fresh.plc")
        _, by_number = circuits(controller, suggestions={"3": (10, 4)})
        self.assertEqual(by_number["3"], TrackCircuitCommand(10, 4))


class VitalLayer(unittest.TestCase):
    def test_separation_from_the_sample_program(self) -> None:
        controller = loaded(1)
        _, by_number = circuits(
            controller, occupied=["3", "8", "9"],
            suggestions={"3": (12, 4), "8": (12, 2)},
        )
        self.assertEqual(by_number["3"], TrackCircuitCommand(12, 4))
        self.assertEqual(by_number["8"], TrackCircuitCommand(0, 0))

    def test_speed_clamped_to_the_whole_limit(self) -> None:
        controller = loaded(1)
        # 45 km/h is 12.5 m/s: 12 is the highest whole m/s allowed.
        _, by_number = circuits(controller, suggestions={"3": (30, 4)})
        self.assertEqual(by_number["3"], TrackCircuitCommand(12, 4))

    def test_closed_or_failed_block_sends_zero(self) -> None:
        controller = loaded(1)
        _, by_number = circuits(
            controller, closed=["3"], failures={"5": "power"},
            suggestions={"3": (10, 4), "5": (10, 4)},
        )
        self.assertEqual(by_number["3"], TrackCircuitCommand(0, 0))
        self.assertEqual(by_number["5"], TrackCircuitCommand(0, 0))

    def test_zero_authority_means_zero_speed(self) -> None:
        controller = loaded(1)
        _, by_number = circuits(controller, suggestions={"3": (10, 0)})
        self.assertEqual(by_number["3"], TrackCircuitCommand(0, 0))

    def test_failed_track_circuit_reads_occupied(self) -> None:
        controller = loaded(1)
        out, by_number = circuits(
            controller, failures={"4": "track_circuit"},
            suggestions={"3": (10, 4)},
        )
        self.assertEqual(by_number["3"], TrackCircuitCommand(0, 0))
        report = out.ctc_reports[0].blocks
        entry = report[keys(controller)["4"]]
        self.assertTrue(entry.occupied)
        self.assertEqual(entry.failure, "track_circuit")

    def test_switch_moves_by_program_then_locks_under_a_train(self) -> None:
        controller = loaded(1)
        k = keys(controller)
        out, _ = circuits(controller, occupied=["1"])
        self.assertEqual(out.track_model.switch_commands[k["12"]], "reverse")
        # A train on the switch's own block holds it where it is.
        out, _ = circuits(controller, occupied=["12"])
        self.assertEqual(out.track_model.switch_commands[k["12"]], "reverse")
        wayside = controller.snapshot().waysides[0]
        self.assertIn("switch_locked", {o.rule for o in wayside.overrides})
        # Clear, the program returns it to normal.
        out, _ = circuits(controller)
        self.assertEqual(out.track_model.switch_commands[k["12"]], "normal")

    def test_disagreeing_switch_reddens_its_signal_and_route(self) -> None:
        controller = loaded(1)
        k = keys(controller)
        out, by_number = circuits(
            controller, reported={"12": "reverse"},
            suggestions={"13": (10, 3), "5": (10, 3)},
        )
        self.assertEqual(out.track_model.signal_commands[k["12"]], "red")
        self.assertEqual(by_number["13"], TrackCircuitCommand(0, 0))
        self.assertEqual(by_number["5"], TrackCircuitCommand(10, 3))
        state = controller.snapshot().waysides[0].switches[0]
        self.assertFalse(state.agreeing)

    def test_signal_with_two_aspects_is_red(self) -> None:
        controller = loaded(1, programs=False)
        controller.load_program(
            "1",
            "VAR_OUT SIG_12_G SIG_12_SG\nSIG_12_G := 1\nSIG_12_SG := 1\n",
            "two.plc",
        )
        out, _ = circuits(controller)
        self.assertEqual(list(out.track_model.signal_commands.values()),
                         ["red"])

    def test_crossing_protected_whatever_the_program_says(self) -> None:
        controller = loaded(1, programs=False)
        controller.load_program("1", "VAR_OUT XING_19\nXING_19 := 0\n",
                                "x.plc")
        k = keys(controller)
        for occupied, expected in (
            (["18"], True), (["19"], True), (["20"], True),
            (["17"], False), ([], False),
        ):
            with self.subTest(occupied=occupied):
                out, _ = circuits(controller, occupied=occupied)
                self.assertEqual(
                    out.track_model.crossing_commands[k["19"]], expected
                )


class Maintenance(unittest.TestCase):
    def test_switches_obey_the_ctc_not_the_program(self) -> None:
        controller = loaded(1)
        k = keys(controller)
        # The program would reverse the switch for a train on block 1.
        out, _ = circuits(controller, occupied=["1"], maintenance=True,
                          switch_commands={"12": "normal"})
        self.assertEqual(out.track_model.switch_commands[k["12"]], "normal")
        out, _ = circuits(controller, maintenance=True,
                          switch_commands={"12": "reverse"})
        self.assertEqual(out.track_model.switch_commands[k["12"]], "reverse")
        self.assertEqual(
            controller.snapshot().waysides[0].switches[0].set_by, "CTC"
        )

    def test_ctc_command_still_locked_under_a_train(self) -> None:
        controller = loaded(1)
        k = keys(controller)
        out, _ = circuits(controller, occupied=["13"], maintenance=True,
                          switch_commands={"12": "reverse"})
        self.assertEqual(out.track_model.switch_commands[k["12"]], "normal")

    def test_program_resumes_when_maintenance_ends(self) -> None:
        controller = loaded(1)
        k = keys(controller)
        circuits(controller, maintenance=True,
                 switch_commands={"12": "reverse"})
        out, _ = circuits(controller)
        self.assertEqual(out.track_model.switch_commands[k["12"]], "normal")


class Report(unittest.TestCase):
    def test_one_report_per_wayside_keyed_by_block(self) -> None:
        controller = loaded(1, 2, 3)
        k = keys(controller)
        out, _ = circuits(controller, time_s=3600.0, occupied=["4"],
                          failures={"22": "broken_rail"})
        self.assertEqual([r.wayside_id for r in out.ctc_reports],
                         ["1", "2", "3"])
        first = out.ctc_reports[0]
        self.assertEqual(first.sent_at_s, 3600.0)
        self.assertEqual(len(first.blocks), 20)
        self.assertTrue(first.blocks[k["4"]].occupied)
        self.assertEqual(first.blocks[k["12"]].switch_position, "normal")
        self.assertIsNone(first.blocks[k["13"]].switch_position)
        self.assertIsNone(first.blocks[k["19"]].crossing_active)
        self.assertEqual(out.ctc_reports[1].blocks[k["22"]].failure,
                         "broken_rail")

    def test_reset_forgets_scans_but_keeps_programs(self) -> None:
        controller = loaded(1)
        circuits(controller, occupied=["1"])
        controller.reset()
        snapshot = controller.snapshot()
        self.assertEqual(snapshot.ticks, 0)
        wayside = snapshot.waysides[0]
        self.assertIsNone(wayside.report)
        self.assertIsNotNone(wayside.program)
        self.assertEqual(wayside.switches[0].commanded, "normal")


if __name__ == "__main__":
    unittest.main()
