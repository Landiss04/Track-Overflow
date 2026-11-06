"""The PLC language must be the one the HW Track Controller reads.

One program file has to run on either variant (REQ-INTF-009), so the two
implementations, written separately, must agree on the language. These
tests compile the same text with both and compare: what is an error, what
each name expands to, and what a scan produces. HW's own sample programs
must also compile cleanly against an equivalent software territory.

Run from ``TrackCtrlSW``::

    .venv/Scripts/python -m unittest discover -s tests -v
"""

from __future__ import annotations

import itertools
import json
import random
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "TrackCtrlHw"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from track_ctrl import plc as sw  # noqa: E402
from track_ctrl.controller import TrackController  # noqa: E402
from track_ctrl.layout import build_line, parse_layout  # noqa: E402
from track_ctrl_hw import plc as hw  # noqa: E402

_HW_DATA = _REPO / "TrackCtrlHw" / "data"
_NAMES = ["A", "B", "OCC_1", "OCC_2", "X_1", "Y"]
_JOINERS = ["AND", "OR", "XOR", "and", "or", "Xor"]
_SOUP = _NAMES + ["0", "1", "(", ")", "10", "2", "1A", ":=", "..", "@",
                  "VAR_IN", "NOT", "AND", "OR", "not", "xor"]


def _expression(rng: random.Random, depth: int = 0) -> str:
    chance = rng.random()
    if depth > 3 or chance < 0.3:
        return rng.choice(_NAMES + ["0", "1"])
    if chance < 0.5:
        return "NOT " + _expression(rng, depth + 1)
    if chance < 0.6:
        return "(" + _expression(rng, depth + 1) + ")"
    return (f"{_expression(rng, depth + 1)} {rng.choice(_JOINERS)} "
            f"{_expression(rng, depth + 1)}")


def _outputs(program: sw.Program, image: dict[str, bool]) -> dict[str, bool]:
    return program.scan(image).outputs(tuple(program.outputs))


def _hw_territory_controller(wayside_file: str) -> TrackController:
    """A software controller over the same blocks as one HW wayside."""
    data = json.loads((_HW_DATA / "waysides" / wayside_file).read_text())
    data.pop("wayside", None)
    parsed = parse_layout(data, wayside_file)
    # D014 wants two waysides per line; this territory is just the one.
    with mock.patch("track_ctrl.layout.MIN_CONTROLLERS", 1):
        line = build_line(parsed, 1)
    config = line.controllers[0]
    blocks = tuple(b for b in line.blocks if config.owns(b.block_id))
    return TrackController(config, blocks)


class SameLanguage(unittest.TestCase):
    def agree(self, source: str) -> None:
        theirs = hw.compile_program(source)
        ours = sw.compile_program(source)
        self.assertEqual(
            bool(theirs.errors), sw.has_errors(ours.diagnostics), source)
        if theirs.errors:
            return
        self.assertEqual(theirs.inputs, ours.inputs, source)
        self.assertEqual(theirs.outputs, ours.outputs, source)
        names = list(theirs.inputs)
        for bits in itertools.product([False, True],
                                      repeat=min(len(names), 4)):
            image = {name: False for name in names}
            image.update(zip(names, bits))
            self.assertEqual(
                theirs.scan_a(image), _outputs(ours, image), source)
            self.assertEqual(
                theirs.scan_b(image), _outputs(ours, image), source)

    def test_random_programs_mean_the_same_thing(self) -> None:
        rng = random.Random(7)
        for _ in range(600):
            lines = ["VAR_IN A B OCC_1 OCC_2", "VAR_OUT OUT_1 OUT_2"]
            for _ in range(rng.randint(1, 4)):
                target = rng.choice(["OUT_1", "OUT_2", "X_1", "Y"])
                lines.append(f"{target} := {_expression(rng)}")
            self.agree("\n".join(lines) + "\n")

    def test_malformed_statements_are_errors_in_both(self) -> None:
        rng = random.Random(11)
        for _ in range(600):
            soup = " ".join(
                rng.choice(_SOUP) for _ in range(rng.randint(1, 7)))
            self.agree(f"VAR_IN A B\nVAR_OUT Z\nZ := {soup}\n")

    def test_declarations_and_ranges_expand_the_same(self) -> None:
        for declaration in (
            "VAR_IN OCC_1 .. OCC_4", "VAR_IN OCC_1..4",
            "VAR_IN OCC_A .. OCC_D", "VAR_IN OCC_A..D", "VAR_IN OCC_4..1",
            "VAR_IN OCC_a..d", "VAR_IN OCC_A..d", "VAR_IN OCC_1 .. 3",
            "VAR_IN 1..3", "VAR_IN A..", "var_in A B", "VAR_IN",
            "VAR_OUT OCC_1..OCC_1", "VAR_IN OCC_1..OCC_3 OCC_2",
            "VAR_IN A..C D..F", "VAR_IN X1..X10", "VAR_IN AB..AD",
        ):
            self.agree(f"{declaration}\nVAR_OUT Z\nZ := 1\n")

    def test_odd_but_legal_programs(self) -> None:
        for source in (
            "VAR_IN A\nVAR_OUT Z\nz := a\n",
            "var_in A\nvar_out Z\nZ := a And A\n",
            "VAR_IN A\nVAR_OUT Z\nZ := A\nZ := 0\n",
            "VAR_IN A\nVAR_OUT Z\nA := 1\n",
            "VAR_IN A\nVAR_OUT Z\nZ :=\n",
            "VAR_IN A\nVAR_OUT Z\nZ = A\n",
            "VAR_IN A\nVAR_OUT Z\nT := A\nZ := T\n",
            "VAR_IN A\nVAR_OUT Z\nZ := T\nT := A\n",
            "VAR_IN A\nVAR_IN A\nVAR_OUT Z\nZ := A\n",
            "VAR_IN A\nVAR_OUT Z\n  Z := A  // tail\n",
            "VAR_IN A\nVAR_OUT Z\nZ:=A\n",
            "VAR_IN A\nVAR_OUT Z\nZ := NOT\n",
            "VAR_IN A\nVAR_OUT Z\nZ := ()\n",
            "VAR_IN A\nVAR_OUT Z\nZ := A A\n",
        ):
            self.agree(source)


class HwProgramsRunHere(unittest.TestCase):
    """HW's own sample programs, on an equivalent software territory."""

    def test_the_hw_wayside_1_program_has_no_diagnostics_here(self) -> None:
        controller = _hw_territory_controller("green_wayside_1.json")
        source = (_HW_DATA / "plc" / "green_wayside_1.plc").read_text()
        program = sw.compile_program(source)
        self.assertEqual(controller.diagnose(program), ())

    def test_the_hw_program_computes_the_same_outputs_in_both(self) -> None:
        source = (_HW_DATA / "plc" / "green_wayside_1.plc").read_text()
        theirs = hw.compile_program(source)
        ours = sw.compile_program(source)
        rng = random.Random(3)
        for _ in range(200):
            image = {name: rng.random() < 0.3 for name in theirs.inputs}
            self.assertEqual(theirs.scan_a(image), _outputs(ours, image))

    def test_the_hw_program_runs_through_the_attached_vital_code(self) -> None:
        controller = _hw_territory_controller("green_wayside_1.json")
        source = (_HW_DATA / "plc" / "green_wayside_1.plc").read_text()
        controller.commit(source, "green_wayside_1.plc")
        controller.set_all_suggestions(9, 2)
        controller.scan()
        self.assertTrue(controller.outputs.track_circuits)
        self.assertEqual(
            set(controller.outputs.aspects.values())
            - {"RED", "YELLOW", "GREEN", "SUPER GREEN"},
            set())

    def test_the_hw_error_and_warning_examples_are_still_flagged(self) -> None:
        errors = sw.compile_program(
            (_HW_DATA / "plc" / "examples" / "errors.plc").read_text())
        warnings = sw.compile_program(
            (_HW_DATA / "plc" / "examples" / "warnings.plc").read_text())
        self.assertTrue(sw.has_errors(errors.diagnostics))
        self.assertTrue(any(d.severity == "warning"
                            for d in warnings.diagnostics))
        self.assertFalse(sw.has_errors(warnings.diagnostics))


class SoftwareNamesMatchHw(unittest.TestCase):
    """The names a program may use are HW's."""

    def test_inputs_and_outputs_are_the_hw_names(self) -> None:
        from track_ctrl_hw import wayside as hw_wayside
        from track_ctrl_hw.territory import load_territory_file

        territory = load_territory_file(
            _HW_DATA / "waysides" / "green_wayside_1.json")
        controller = _hw_territory_controller("green_wayside_1.json")
        self.assertEqual(
            set(controller.input_names()),
            set(hw_wayside.input_names(territory)))
        self.assertEqual(
            set(controller.output_names()),
            set(hw_wayside.output_names(territory)))


if __name__ == "__main__":
    unittest.main()
