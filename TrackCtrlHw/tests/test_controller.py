"""The module: scans, fail-safe holds, maintenance and the report."""

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
from track_ctrl_hw.wayside import speed_limit_whole_mps

from tests.support import inputs, keys, loaded, program_source, territory


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
                suggestions={k["3"].ref: Suggestion(-1, 2)})),
            replace(inputs(controller), ctc=CtcInputs(
                suggestions={k["3"].ref: Suggestion(5.5, 2)})),  # type: ignore
            # Five bits carry at most 31 m/s.
            replace(inputs(controller), ctc=CtcInputs(
                suggestions={k["3"].ref: Suggestion(32, 2)})),
            replace(inputs(controller), ctc=CtcInputs(
                switch_commands={k["12"].ref: "sideways"})),  # type: ignore
            # The CTC Office names blocks by BlockRef, not BlockKey.
            replace(inputs(controller), ctc=CtcInputs(
                closed_blocks=frozenset({k["3"]}))),  # type: ignore
        ]
        for case in bad:
            with self.subTest(case), self.assertRaises(InvalidInputError):
                controller.step(0.1, case)
        self.assertEqual(controller.snapshot(), before)

    def test_ignores_blocks_it_does_not_govern(self) -> None:
        controller = loaded(1)
        other = replace(keys(controller)["3"], line="Red").ref
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
            controller.load_program("7", "VAR_IN OCC_1\n", "x.plc")

    def test_samples_compile_cleanly(self) -> None:
        controller = loaded(1, 2, 3)
        for wayside in controller.snapshot().waysides:
            self.assertEqual(wayside.program.warnings, ())


class FailSafe(unittest.TestCase):
    def test_no_program_holds_everything(self) -> None:
        controller = loaded(1, programs=False)
        out, by_number = circuits(
            controller, suggestions={"3": (10, 4)}, occupied=["3"]
        )
        self.assertEqual(by_number["3"], TrackCircuitCommand(0, 0))
        signals = list(out.track_model.signal_commands.values())
        self.assertEqual(signals, ["red"])
        self.assertTrue(all(out.track_model.crossing_commands.values()))
        wayside = controller.snapshot().waysides[0]
        self.assertEqual(wayside.holding, "No PLC program is loaded.")

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
        circuits(controller, suggestions={"3": (10, 4)})
        self.assertEqual(controller.snapshot().waysides[0].holding, "")

    def test_channel_disagreement_is_a_latched_channel_fault(self) -> None:
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
        self.assertIn("AUTH_3", scan.channel_fault)
        # Latched: a healthy scan does not clear it...
        _, by_number = circuits(controller, suggestions={"3": (10, 4)})
        self.assertEqual(by_number["3"], TrackCircuitCommand(0, 0))
        # ...a new program does.
        controller.load_program("1", program_source(1), "fresh.plc")
        _, by_number = circuits(controller, suggestions={"3": (10, 4)})
        self.assertEqual(by_number["3"], TrackCircuitCommand(10, 4))


class NothingAboveTheProgram(unittest.TestCase):
    """The wayside drives the program's outputs as they are."""

    def test_a_closed_block_is_the_programs_to_honour(self) -> None:
        controller = loaded(1, programs=False)
        controller.load_program(
            "1", "VAR_OUT AUTH_3\nAUTH_3 := 1\n", "x.plc"
        )
        _, by_number = circuits(
            controller, closed=["3"], suggestions={"3": (10, 4)},
        )
        # Authority passes; no CMD_3 output, so speed 0.
        self.assertEqual(by_number["3"], TrackCircuitCommand(0, 4))

    def test_the_speed_limit_is_the_programs_to_honour(self) -> None:
        controller = loaded(1, programs=False)
        source = "VAR_IN SPD_3_0..4\nVAR_OUT CMD_3_0..4\n" + "".join(
            f"CMD_3_{bit} := SPD_3_{bit}\n" for bit in range(5)
        )
        controller.load_program("1", source, "x.plc")
        # 30 m/s on a 12 m/s block goes out as sent; AUTH_3 is 0.
        _, by_number = circuits(controller, suggestions={"3": (30, 4)})
        self.assertEqual(by_number["3"], TrackCircuitCommand(30, 0))

    def test_a_switch_moves_under_a_train_if_the_program_says(self) -> None:
        controller = loaded(1, programs=False)
        controller.load_program(
            "1", "VAR_OUT SW_12\nSW_12 := 1\n", "x.plc"
        )
        k = keys(controller)
        out, _ = circuits(controller, occupied=["12", "13"])
        self.assertEqual(out.track_model.switch_commands[k["12"]], "reverse")

    def test_a_crossing_follows_the_program(self) -> None:
        controller = loaded(1, programs=False)
        controller.load_program("1", "VAR_OUT XING_19\nXING_19 := 0\n",
                                "x.plc")
        k = keys(controller)
        out, _ = circuits(controller, occupied=["19"])
        self.assertFalse(out.track_model.crossing_commands[k["19"]])

    def test_signal_outputs_decode_in_a_fixed_order(self) -> None:
        controller = loaded(1, programs=False)
        k = keys(controller)
        for lit, expected in (
            ((), "red"),
            (("G", "SG"), "green"),
            (("R", "SG"), "red"),
            (("Y", "G"), "yellow"),
            (("SG",), "super_green"),
        ):
            source = "VAR_OUT SIG_12_R SIG_12_Y SIG_12_G SIG_12_SG\n"
            source += "".join(f"SIG_12_{suffix} := 1\n" for suffix in lit)
            controller.load_program("1", source, "sig.plc")
            circuits(controller)
            with self.subTest(lit=lit):
                out, _ = circuits(controller)
                self.assertEqual(
                    out.track_model.signal_commands[k["12"]], expected
                )


class SamplePrograms(unittest.TestCase):
    """The protections the wayside no longer applies, in the samples."""

    def test_separation(self) -> None:
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

    def test_every_speed_capped_on_every_block(self) -> None:
        controller = loaded(1, 2, 3)
        limits = {
            block.key.block_id: speed_limit_whole_mps(block.speed_limit_mps)
            for wayside in controller.snapshot().waysides
            for block in wayside.territory.blocks
        }
        for speed in range(32):
            _, by_number = circuits(
                controller,
                suggestions={n: (speed, 3) for n in limits},
            )
            for number, limit in limits.items():
                self.assertEqual(
                    by_number[number],
                    TrackCircuitCommand(min(speed, limit), 3),
                    f"block {number}, {speed} m/s",
                )

    def test_held_authority_sends_no_speed(self) -> None:
        controller = loaded(1)
        _, by_number = circuits(
            controller, occupied=["4"], suggestions={"3": (10, 4)}
        )
        self.assertEqual(by_number["3"], TrackCircuitCommand(0, 0))

    def test_closed_block_sends_zero(self) -> None:
        controller = loaded(1, 2, 3)
        for block in ("3", "13", "29", "77"):
            with self.subTest(block=block):
                _, by_number = circuits(
                    controller, closed=[block],
                    suggestions={block: (5, 4)},
                )
                self.assertEqual(by_number[block],
                                 TrackCircuitCommand(0, 0))

    def test_switch_moves_by_program_then_locks_under_a_train(self) -> None:
        controller = loaded(1)
        k = keys(controller)
        out, _ = circuits(controller, occupied=["1"])
        self.assertEqual(out.track_model.switch_commands[k["12"]], "reverse")
        # A train on the switch's own block holds it where it reports.
        out, _ = circuits(controller, occupied=["12"])
        self.assertEqual(out.track_model.switch_commands[k["12"]], "reverse")
        # Clear, the program returns it to normal.
        out, _ = circuits(controller)
        self.assertEqual(out.track_model.switch_commands[k["12"]], "normal")

    def test_disagreeing_switch_reddens_its_signal_and_route(self) -> None:
        controller = loaded(1)
        k = keys(controller)
        out, by_number = circuits(
            controller, reported={"12": "reverse"},
            suggestions={"13": (10, 3), "1": (10, 3), "5": (10, 3)},
        )
        self.assertEqual(out.track_model.signal_commands[k["12"]], "red")
        self.assertEqual(by_number["13"], TrackCircuitCommand(0, 0))
        self.assertEqual(by_number["1"], TrackCircuitCommand(0, 0))
        self.assertEqual(by_number["5"], TrackCircuitCommand(10, 3))
        state = controller.snapshot().waysides[0].switches[0]
        self.assertFalse(state.agreeing)

    def test_crossing_active_for_a_train_at_or_beside_it(self) -> None:
        controller = loaded(1)
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
    def test_the_program_obeys_ctc_switch_commands(self) -> None:
        controller = loaded(1)
        k = keys(controller)
        # On its own the program would reverse the switch for a train on
        # block 1; the sample program obeys the CTC Office instead.
        out, _ = circuits(controller, occupied=["1"],
                          switch_commands={"12": "normal"})
        self.assertEqual(out.track_model.switch_commands[k["12"]], "normal")
        out, _ = circuits(controller, switch_commands={"12": "reverse"})
        self.assertEqual(out.track_model.switch_commands[k["12"]], "reverse")
        wayside = controller.snapshot().waysides[0]
        self.assertEqual(wayside.switch_requests, {k["12"]: "reverse"})

    def test_commands_reach_the_program_as_inputs(self) -> None:
        controller = loaded(1, programs=False)
        # A program that ignores the CTC Office is not overridden.
        controller.load_program(
            "1", "VAR_IN CTCSW_12\nVAR_OUT SW_12\nSW_12 := 0\n", "x.plc"
        )
        k = keys(controller)
        out, _ = circuits(controller, switch_commands={"12": "reverse"})
        self.assertEqual(out.track_model.switch_commands[k["12"]], "normal")

    def test_ctc_command_still_locked_under_a_train(self) -> None:
        controller = loaded(1)
        k = keys(controller)
        out, _ = circuits(controller, occupied=["13"],
                          switch_commands={"12": "reverse"})
        self.assertEqual(out.track_model.switch_commands[k["12"]], "normal")

    def test_program_resumes_when_commands_end(self) -> None:
        controller = loaded(1)
        k = keys(controller)
        circuits(controller, switch_commands={"12": "reverse"})
        out, _ = circuits(controller)
        self.assertEqual(out.track_model.switch_commands[k["12"]], "normal")

    def test_closures_are_named_by_line_and_block(self) -> None:
        controller = loaded(1)
        k = keys(controller)
        _, by_number = circuits(controller, closed=["3"],
                                suggestions={"3": (10, 4)})
        self.assertEqual(by_number["3"], TrackCircuitCommand(0, 0))
        self.assertEqual(k["3"].ref.label, "Green:3")
        wayside = controller.snapshot().waysides[0]
        self.assertEqual(wayside.closed_blocks, frozenset({k["3"]}))


class Report(unittest.TestCase):
    def test_one_report_per_wayside_keyed_by_block(self) -> None:
        controller = loaded(1, 2, 3)
        k = keys(controller)
        out, _ = circuits(controller, time_s=3600.0, occupied=["4", "22"],
                          lit={"12": "yellow"})
        self.assertEqual([r.wayside_id for r in out.ctc_reports],
                         ["1", "2", "3"])
        first = out.ctc_reports[0]
        self.assertEqual(first.sent_at_s, 3600.0)
        self.assertEqual(first.line, "Green")
        self.assertTrue(first.ready)
        self.assertEqual(first.reason, "")
        self.assertEqual(len(first.blocks), 20)
        self.assertTrue(first.blocks[k["4"]].occupied)
        self.assertEqual(first.blocks[k["12"]].switch_position, "normal")
        self.assertIsNone(first.blocks[k["13"]].switch_position)
        self.assertIsNone(first.blocks[k["19"]].crossing_active)
        # The aspect the Track Model reports lit, only where a signal is.
        self.assertEqual(first.blocks[k["12"]].signal_aspect, "yellow")
        self.assertIsNone(first.blocks[k["13"]].signal_aspect)
        self.assertIsNone(
            out.ctc_reports[1].blocks[k["28"]].signal_aspect
        )
        self.assertTrue(out.ctc_reports[1].blocks[k["22"]].occupied)

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


class Ready(unittest.TestCase):
    def test_nothing_loaded_is_not_ready(self) -> None:
        controller = HwTrackController()
        snapshot = controller.snapshot()
        self.assertFalse(snapshot.ready)
        self.assertEqual(snapshot.not_ready,
                         ("No wayside database is loaded.",))
        out = controller.step(0.1, TrackControllerInputs(time_s=1.0))
        self.assertEqual(out.ctc_reports, ())
        self.assertFalse(out.ready)

    def test_a_wayside_without_a_program_is_not_ready(self) -> None:
        controller = loaded(1, programs=False)
        out, _ = circuits(controller)
        (report,) = out.ctc_reports
        self.assertFalse(report.ready)
        self.assertEqual(report.reason, "No PLC program is loaded.")
        self.assertEqual(controller.snapshot().not_ready,
                         ("Wayside 1: No PLC program is loaded.",))

    def test_the_line_stalls_until_every_wayside_is_ready(self) -> None:
        controller = loaded(1)
        controller.load_territory(territory(2))
        k = keys(controller)
        out, by_number = circuits(
            controller, occupied=["1", "19"], suggestions={"3": (10, 4)}
        )
        first, second = out.ctc_reports
        # Wayside 1 is started up, and says so, but holds fail-safe.
        self.assertTrue(first.ready)
        self.assertFalse(second.ready)
        self.assertFalse(out.ready)
        self.assertEqual(out.not_ready(), (second,))
        self.assertEqual(by_number["3"], TrackCircuitCommand(0, 0))
        self.assertEqual(out.track_model.switch_commands[k["12"]], "normal")
        self.assertTrue(out.track_model.crossing_commands[k["19"]])
        held = controller.snapshot().waysides[0].holding
        self.assertIn("Wayside 2 is not ready", held)
        # A program on wayside 2 starts the whole line.
        controller.load_program("2", program_source(2), "w2.plc")
        out, by_number = circuits(
            controller, occupied=["1"], suggestions={"3": (10, 4)}
        )
        self.assertTrue(all(r.ready for r in out.ctc_reports))
        self.assertTrue(out.ready)
        self.assertTrue(controller.snapshot().ready)
        self.assertEqual(by_number["3"], TrackCircuitCommand(10, 4))
        self.assertEqual(out.track_model.switch_commands[k["12"]], "reverse")

    def test_a_channel_fault_is_not_ready(self) -> None:
        controller = loaded(1)
        real = Program.scan_b

        def broken(program: Program, image: object) -> dict[str, bool]:
            values = real(program, image)  # type: ignore[arg-type]
            values["AUTH_3"] = not values["AUTH_3"]
            return values

        with mock.patch.object(Program, "scan_b", broken):
            out, _ = circuits(controller)
        self.assertFalse(out.ctc_reports[0].ready)
        self.assertIn("AUTH_3", out.ctc_reports[0].reason)

    def test_ready_survives_a_new_program_and_a_reset(self) -> None:
        controller = loaded(1)
        controller.load_program("1", program_source(1), "again.plc")
        self.assertTrue(controller.snapshot().ready)
        controller.reset()
        self.assertTrue(controller.snapshot().ready)

    def test_a_database_the_program_no_longer_fits_loses_ready(self) -> None:
        controller = loaded(1)
        smaller = parse_territory({
            "line": "Green", "wayside": "1",
            "blocks": [
                {"block_number": int(b.key.block_id), "section": b.key.section,
                 "length_m": b.length_m, "speed_limit_kmh": 45}
                for b in territory(1).blocks[10:]
            ],
        })
        controller.load_territory(smaller)
        self.assertFalse(controller.snapshot().ready)


if __name__ == "__main__":
    unittest.main()
