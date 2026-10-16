"""The PLC language: grammar, diagnostics, and both scan channels."""

from __future__ import annotations

import random
import unittest
from typing import Any

from track_ctrl_hw.plc import ERROR, WARNING, compile_program

NAMES = ("A", "B", "C", "D")
# Binding strength: higher binds tighter.
_RANK = {"OR": 1, "XOR": 2, "AND": 3, "NOT": 4, "atom": 5}


def scan(source: str, **inputs: bool) -> dict[str, bool]:
    program = compile_program(source)
    assert not program.errors, program.errors
    a = program.scan_a(inputs)
    b = program.scan_b(inputs)
    assert a == b, (a, b)
    return a


def messages(source: str, severity: str) -> list[str]:
    return [d.message for d in compile_program(source).diagnostics
            if d.severity == severity]


class Grammar(unittest.TestCase):
    def test_precedence_not_and_xor_or(self) -> None:
        src = "VAR_IN A B C\nVAR_OUT X Y Z\n"
        out = scan(src + "X := A OR B AND C\n", A=True, B=False, C=False)
        self.assertTrue(out["X"])          # A OR (B AND C)
        out = scan(src + "X := NOT A AND B\n", A=False, B=True, C=False)
        self.assertTrue(out["X"])          # (NOT A) AND B
        out = scan(src + "X := A XOR B AND C\n", A=True, B=True, C=False)
        self.assertTrue(out["X"])          # A XOR (B AND C)
        out = scan(src + "X := A OR B XOR C\n", A=True, B=True, C=True)
        self.assertTrue(out["X"])          # A OR (B XOR C)

    def test_parentheses_constants_and_case(self) -> None:
        out = scan(
            "var_in A B\nvar_out X Y Z\n"
            "X := not (A or B)\nY := 1 and not 0\nZ := (A)\n",
            A=False, B=False,
        )
        self.assertEqual(out, {"X": True, "Y": True, "Z": False})

    def test_assignments_run_in_order_once(self) -> None:
        out = scan(
            "VAR_IN A\nVAR_OUT X Y\nT := NOT A\nX := T\nT := A\nY := T\n",
            A=True,
        )
        self.assertEqual(out, {"X": False, "Y": True})

    def test_ranges(self) -> None:
        program = compile_program(
            "VAR_IN OCC_1 .. OCC_3 SW_A..C\nVAR_OUT AUTH_9..11\n"
        )
        self.assertEqual(
            program.inputs,
            ("OCC_1", "OCC_2", "OCC_3", "SW_A", "SW_B", "SW_C"),
        )
        self.assertEqual(program.outputs, ("AUTH_9", "AUTH_10", "AUTH_11"))

    def test_undefined_read_is_zero(self) -> None:
        out = scan("VAR_IN A\nVAR_OUT X\nX := A OR GHOST\n", A=False)
        self.assertFalse(out["X"])

    def test_checksum_and_counts(self) -> None:
        program = compile_program("VAR_IN A B\nVAR_OUT X\nX := A AND B\n")
        self.assertRegex(program.checksum, r"^[0-9A-F]{4}-[0-9A-F]{4}$")
        self.assertEqual(program.boolean_count, 3)
        self.assertEqual(len(program.statements), 1)


class Diagnostics(unittest.TestCase):
    def test_errors(self) -> None:
        for source in (
            "VAR_IN A\nA := 1\n",                 # assign an input
            "X := A AND\n",                       # ends too soon
            "X := (A\n",                          # unclosed
            "X := A)\n",                          # unmatched
            "X := 2\n",                           # not a bit
            "X := A B\n",                         # missing operator
            "X := AND\n",                         # keyword as value
            "X = A\n",                            # not :=
            "X := A # B\n",                       # unknown character
            "VAR_IN 1A\n",                        # bad name
            "VAR_IN OCC_3 .. OCC_1\n",            # backwards range
            "X :=\n",                             # empty expression
        ):
            with self.subTest(source):
                self.assertTrue(
                    compile_program(source).errors, "expected an error"
                )

    def test_every_bad_line_is_reported(self) -> None:
        program = compile_program("X := (\nY := 1\nZ := ) \n")
        self.assertEqual([d.line for d in program.errors], [1, 3])

    def test_warnings(self) -> None:
        warnings = messages(
            "VAR_IN A\nVAR_IN A\nVAR_OUT X Y\nX := B\nX := A\n", WARNING
        )
        joined = " | ".join(warnings)
        self.assertIn("A is declared more than once", joined)
        self.assertIn("B is read before anything sets it", joined)
        self.assertIn("X is assigned again", joined)
        self.assertIn("output Y is never assigned", joined)
        self.assertEqual(
            messages("VAR_IN A\nVAR_OUT X\nX := A\n", ERROR), []
        )

    def test_comments_and_blank_lines(self) -> None:
        program = compile_program(
            "// header\n\nVAR_IN A // trailing\nVAR_OUT X\n  X := A\n"
        )
        self.assertFalse(program.diagnostics)


def _random_tree(rng: random.Random, depth: int) -> Any:
    if depth == 0 or rng.random() < 0.25:
        if rng.random() < 0.15:
            return ("bit", rng.choice("01"))
        return ("name", rng.choice(NAMES))
    if rng.random() < 0.25:
        return ("NOT", _random_tree(rng, depth - 1))
    return (
        rng.choice(("AND", "OR", "XOR")),
        _random_tree(rng, depth - 1),
        _random_tree(rng, depth - 1),
    )


def _rank(tree: Any) -> int:
    return _RANK["atom"] if tree[0] in ("bit", "name") else _RANK[tree[0]]


def _plc_text(tree: Any) -> str:
    # Write the tree with as few parentheses as precedence allows, so
    # the parsers' precedence and associativity are what is tested.
    kind = tree[0]
    if kind in ("bit", "name"):
        return tree[1]
    if kind == "NOT":
        inner = _plc_text(tree[1])
        if _rank(tree[1]) >= _RANK["NOT"]:
            return f"NOT {inner}"
        return f"NOT ({inner})"
    left, right = _plc_text(tree[1]), _plc_text(tree[2])
    if _rank(tree[1]) < _RANK[kind]:
        left = f"({left})"
    # Left-associative: an equal-rank right operand needs parentheses.
    if _rank(tree[2]) <= _RANK[kind]:
        right = f"({right})"
    return f"{left} {kind} {right}"


def _reference(tree: Any, values: dict[str, bool]) -> bool:
    kind = tree[0]
    if kind == "bit":
        return tree[1] == "1"
    if kind == "name":
        return values[tree[1]]
    if kind == "NOT":
        return not _reference(tree[1], values)
    left, right = _reference(tree[1], values), _reference(tree[2], values)
    return {"AND": left and right, "OR": left or right,
            "XOR": left != right}[kind]


class Channels(unittest.TestCase):
    def test_random_expressions_match_a_reference(self) -> None:
        rng = random.Random(1140)
        for case in range(3000):
            tree = _random_tree(rng, depth=5)
            text = _plc_text(tree)
            program = compile_program(
                f"VAR_IN {' '.join(NAMES)}\nVAR_OUT X\nX := {text}\n"
            )
            self.assertFalse(program.errors, text)
            for bits in range(16):
                values = {n: bool(bits >> i & 1) for i, n in enumerate(NAMES)}
                expected = _reference(tree, values)
                with self.subTest(case=case, text=text, values=values):
                    self.assertEqual(program.scan_a(values)["X"], expected)
                    self.assertEqual(program.scan_b(values)["X"], expected)


if __name__ == "__main__":
    unittest.main()
