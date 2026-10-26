"""The vital block: generated, read-only, and only ever more restrictive."""

from __future__ import annotations

import unittest
from unittest import mock

from track_ctrl_hw.interface import Territory, TrackCircuitCommand
from track_ctrl_hw.plc import Program, compile_program
from track_ctrl_hw.territory import load_territory_file
from track_ctrl_hw.vital import OUT, vital_source
from track_ctrl_hw.wayside import (
    input_names,
    output_names,
    speed_limit_whole_mps,
)

from tests.support import DATA, inputs, keys, loaded, territory

RED = tuple(f"red_wayside_{n}_integration_test" for n in (1, 2, 3))


def red(number: int) -> Territory:
    return load_territory_file(DATA / "waysides" / f"{RED[number - 1]}.json")


def permissive(t: Territory, *, speed: str = "1") -> str:
    """A program that drives every output to its least restrictive value."""
    lines = [
        "VAR_OUT " + " ".join(sorted(output_names(t))),
    ]
    if speed != "1":
        lines.insert(0, "VAR_IN " + " ".join(
            f"SPD_{b.key.block_id}_{bit}"
            for b in t.blocks for bit in range(5)))
    for b in t.blocks:
        n = b.key.block_id
        lines.append(f"AUTH_{n} := 1")
        for bit in range(5):
            value = "1" if speed == "1" else f"SPD_{n}_{bit}"
            lines.append(f"CMD_{n}_{bit} := {value}")
    for s in t.switches:
        lines.append(f"SW_{s.switch_id} := 1")
        for a in ("R", "Y", "G", "SG"):
            lines.append(f"SIG_{s.switch_id}_{a} := {int(a == 'SG')}")
    for c in t.crossings:
        lines.append(f"XING_{c.block_id} := 0")
    return "\n".join(lines) + "\n"


def run_permissive(t: Territory, **kwargs: object):
    from track_ctrl_hw.controller import HwTrackController

    controller = HwTrackController()
    controller.load_territory(t)
    controller.load_program(t.wayside_id, permissive(t), "open.plc")
    out = controller.step(0.1, inputs(controller, **kwargs))  # type: ignore
    return controller, out


def by_number(mapping):
    return {k.block_id: v for k, v in mapping.items()}


class Generated(unittest.TestCase):
    def test_compiles_cleanly_for_every_database(self) -> None:
        for t in [territory(n) for n in (1, 2, 3)] + [red(n)
                                                     for n in (1, 2, 3)]:
            with self.subTest(wayside=t.wayside_id):
                program = compile_program(vital_source(t))
                self.assertEqual(program.diagnostics, ())
                self.assertEqual(
                    set(program.outputs),
                    {OUT + name for name in output_names(t)},
                )
                self.assertLessEqual(
                    set(program.inputs), input_names(t) | output_names(t)
                )

    def test_snapshot_names_the_vital_block(self) -> None:
        controller = loaded(1)
        wayside = controller.snapshot().waysides[0]
        expected = compile_program(vital_source(wayside.territory))
        self.assertEqual(wayside.vital.checksum, expected.checksum)


class OverAPermissiveProgram(unittest.TestCase):
    """Every protection holds with a program that grants everything."""

    def test_closed_block_gets_no_authority(self) -> None:
        _, out = run_permissive(red(2), closed=["30"],
                                suggestions={"30": (10, 4), "31": (10, 4)})
        circuits = by_number(out.track_model.track_circuits)
        self.assertEqual(circuits["30"], TrackCircuitCommand(0, 0))
        self.assertNotEqual(circuits["31"], TrackCircuitCommand(0, 0))

    def test_every_speed_is_capped_on_every_block(self) -> None:
        from track_ctrl_hw.controller import HwTrackController

        for t in [territory(n) for n in (1, 2, 3)] + [red(n)
                                                     for n in (1, 2, 3)]:
            controller = HwTrackController()
            controller.load_territory(t)
            controller.load_program(
                t.wayside_id, permissive(t, speed="SPD"), "open.plc")
            limits = {
                b.key.block_id: speed_limit_whole_mps(b.speed_limit_mps)
                for b in t.blocks
            }
            # Let every switch the program reverses report there first.
            controller.step(0.1, inputs(controller))
            for speed in range(32):
                out = controller.step(0.1, inputs(
                    controller,
                    suggestions={n: (speed, 3) for n in limits}))
                for n, circuit in by_number(
                        out.track_model.track_circuits).items():
                    with self.subTest(wayside=t.wayside_id, block=n,
                                      speed=speed):
                        self.assertEqual(
                            circuit,
                            TrackCircuitCommand(min(speed, limits[n]), 3))

    def test_no_authority_beside_an_occupied_block(self) -> None:
        # Red is two-way: a train is held by a neighbour on either side.
        _, out = run_permissive(
            red(3), occupied=["60", "61"],
            suggestions={"60": (10, 3), "61": (10, 3), "58": (10, 3)},
        )
        circuits = by_number(out.track_model.track_circuits)
        self.assertEqual(circuits["60"], TrackCircuitCommand(0, 0))
        self.assertEqual(circuits["61"], TrackCircuitCommand(0, 0))
        self.assertEqual(circuits["58"].authority_blocks, 3)

    def test_one_way_blocks_hold_only_the_train_behind(self) -> None:
        # Green 4 runs into 3: the train on 3 keeps its authority.
        _, out = run_permissive(
            territory(1), occupied=["3", "4"],
            suggestions={"3": (10, 3), "4": (10, 3)},
        )
        circuits = by_number(out.track_model.track_circuits)
        self.assertEqual(circuits["3"].authority_blocks, 3)
        self.assertEqual(circuits["4"], TrackCircuitCommand(0, 0))

    def test_points_count_only_the_leg_the_switch_reports(self) -> None:
        # Switch 52 normal (52-53): a train on the reverse leg 66 does
        # not hold the train on the points; the points hold it.
        t = red(3)
        controller, out = run_permissive(
            t, occupied=["52", "66"], reported={"52": "normal"},
            switch_commands={"52": "normal"},
            suggestions={"52": (10, 3), "66": (10, 3)},
        )
        circuits = by_number(out.track_model.track_circuits)
        self.assertEqual(circuits["52"].authority_blocks, 3)
        self.assertEqual(circuits["66"], TrackCircuitCommand(0, 0))
        out = controller.step(0.1, inputs(
            controller, occupied=["52", "66"], reported={"52": "reverse"},
            switch_commands={"52": "reverse"},
            suggestions={"52": (10, 3), "66": (10, 3)}))
        circuits = by_number(out.track_model.track_circuits)
        self.assertEqual(circuits["52"], TrackCircuitCommand(0, 0))

    def test_ctc_command_wins_and_a_train_locks_the_switch(self) -> None:
        controller, out = run_permissive(
            red(2), switch_commands={"32": "normal"})
        # The program says reverse; the CTC Office says normal.
        self.assertEqual(
            by_number(out.track_model.switch_commands)["32"], "normal")
        for block in ("32", "33"):
            with self.subTest(block=block):
                out = controller.step(0.1, inputs(
                    controller, occupied=[block], reported={"32": "normal"},
                    switch_commands={"32": "reverse"}))
                self.assertEqual(
                    by_number(out.track_model.switch_commands)["32"],
                    "normal")

    def test_a_moving_switch_stops_its_points_and_listed_block(self) -> None:
        _, out = run_permissive(
            red(2), reported={"32": "normal"},
            suggestions={n: (10, 3) for n in ("31", "32", "33", "72")},
        )
        # The program commands reverse; the switch still reports normal.
        circuits = by_number(out.track_model.track_circuits)
        self.assertEqual(circuits["32"], TrackCircuitCommand(0, 0))
        self.assertEqual(circuits["33"], TrackCircuitCommand(0, 0))
        self.assertEqual(circuits["31"].authority_blocks, 3)
        signals = by_number(out.track_model.signal_commands)
        self.assertEqual(signals["32"], "red")

    def test_signal_needs_one_aspect_and_clear_points(self) -> None:
        from track_ctrl_hw.controller import HwTrackController

        t = territory(1)
        k12 = None
        for lit, occupied, expected in (
            ((), [], "red"),
            (("G", "SG"), [], "red"),
            (("R", "SG"), [], "red"),
            (("Y", "G"), [], "red"),
            (("SG",), [], "super_green"),
            (("G",), [], "green"),
            (("Y",), [], "yellow"),
            (("SG",), ["13"], "red"),
        ):
            controller = HwTrackController()
            controller.load_territory(t)
            source = "VAR_OUT SIG_12_R SIG_12_Y SIG_12_G SIG_12_SG\n"
            source += "".join(f"SIG_12_{a} := 1\n" for a in lit)
            controller.load_program("1", source, "sig.plc")
            k12 = keys(controller)["12"]
            out = controller.step(0.1, inputs(controller, occupied=occupied))
            with self.subTest(lit=lit, occupied=occupied):
                self.assertEqual(
                    out.track_model.signal_commands[k12], expected)

    def test_crossing_active_for_a_train_on_or_beside_it(self) -> None:
        for occupied, expected in (
            (["10"], True), (["11"], True), (["12"], True),
            (["9"], False), ([], False),
        ):
            with self.subTest(occupied=occupied):
                _, out = run_permissive(red(1), occupied=occupied)
                self.assertEqual(
                    by_number(out.track_model.crossing_commands)["11"],
                    expected)

    def test_overrides_are_reported(self) -> None:
        controller, _ = run_permissive(
            red(2), closed=["30"], suggestions={"30": (10, 4)})
        overrides = controller.snapshot().waysides[0].overrides
        self.assertIn("AUTH_30 1->0", overrides)


class Channels(unittest.TestCase):
    def test_vital_disagreement_is_a_latched_channel_fault(self) -> None:
        controller = loaded(1)
        real = Program.scan_b

        def broken(program: Program, image: object) -> dict[str, bool]:
            values = real(program, image)  # type: ignore[arg-type]
            if "OUT_AUTH_3" in values:
                values["OUT_AUTH_3"] = not values["OUT_AUTH_3"]
            return values

        with mock.patch.object(Program, "scan_b", broken):
            out = controller.step(0.1, inputs(
                controller, suggestions={"3": (10, 4)}))
        self.assertEqual(by_number(out.track_model.track_circuits)["3"],
                         TrackCircuitCommand(0, 0))
        scan = controller.snapshot().waysides[0].scan
        self.assertFalse(scan.channels_agree)
        self.assertIn("vital OUT_AUTH_3", scan.channel_fault)


class RedPrograms(unittest.TestCase):
    def test_compile_without_warnings_and_fit(self) -> None:
        from track_ctrl_hw.wayside import check_program

        for number, stem in enumerate(RED, start=1):
            with self.subTest(stem=stem):
                source = (DATA / "plc" / f"{stem}.plc").read_text()
                errors, warnings = check_program(
                    compile_program(source), red(number))
                self.assertEqual((errors, warnings), ([], []))


if __name__ == "__main__":
    unittest.main()
