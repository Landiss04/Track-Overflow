"""Tests for the module registry, the Phase 0 edges, and the command
lines that start the harness, a module, or a stub.

Run from the repository root with
``python -m unittest discover -s common/harness/tests``.
"""

from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import track_overflow  # noqa: E402
from common.harness import stub_module  # noqa: E402
from common.harness.modules import (  # noqa: E402
    CTC_OFFICE,
    MODULE_NAMES,
    PRODUCERS,
    TRACK_MODEL,
    TRAIN_CONTROLLER_HW,
    TRAIN_MODEL,
    module_command,
    stub_specs,
)
from common.harness.stub_edges import stub_inputs  # noqa: E402


class RegistryTest(unittest.TestCase):
    """Every module is known once, with the edges of Appendix A."""

    def test_every_module_has_its_producers(self) -> None:
        self.assertEqual(set(PRODUCERS), set(MODULE_NAMES))
        for consumer, producers in PRODUCERS.items():
            with self.subTest(consumer=consumer):
                self.assertTrue(set(producers) <= set(MODULE_NAMES))
                self.assertNotIn(consumer, producers)

    def test_module_names_are_lowercase_keys(self) -> None:
        for name in MODULE_NAMES:
            self.assertRegex(name, r"^[a-z]+(-[a-z]+)*$")

    def test_a_stub_for_every_module(self) -> None:
        specs = stub_specs({TRAIN_MODEL: ["--reject-at-tick", "4"]})
        self.assertEqual([spec.name for spec in specs], list(MODULE_NAMES))
        train_model = specs[MODULE_NAMES.index(TRAIN_MODEL)]
        self.assertEqual(
            train_model.args,
            (
                "--module", "stub",
                "--as", TRAIN_MODEL,
                "--reject-at-tick", "4",
            ),
        )

    def test_stub_options_for_no_such_module_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            stub_specs({"train-modle": []})

    def test_module_command_runs_the_entry_script(self) -> None:
        program, args = module_command(["--module", "stub"])
        self.assertEqual(program, sys.executable)
        self.assertEqual(Path(args[0]).name, "track_overflow.py")
        self.assertEqual(args[1:], ["--module", "stub"])


class StubEdgesTest(unittest.TestCase):
    """A module reads its producers' outputs, and only theirs."""

    def test_producers_outputs_pass_whole(self) -> None:
        outputs = {
            TRAIN_MODEL: {"tick": 4, "speed_mps": 10.0},
            CTC_OFFICE: {"tick": 4},
        }
        self.assertEqual(
            stub_inputs(TRACK_MODEL, outputs),
            {TRAIN_MODEL: {"tick": 4, "speed_mps": 10.0}},
        )

    def test_nothing_before_the_first_outputs(self) -> None:
        self.assertEqual(stub_inputs(TRAIN_CONTROLLER_HW, {}), {})


class CommandLineTest(unittest.TestCase):
    """Wrong command lines are refused before anything starts."""

    def test_hw_launchers_are_registered_without_local_core_fallback(self) -> None:
        self.assertIn("track-controller-hw", track_overflow._MODULES)
        self.assertIn("train-controller-hw", track_overflow._MODULES)

    def test_staged_hardware_and_stubs_only_specs(self) -> None:
        from common.harness.app import _parse_args, _specs
        for args, expected in (([], False), (["--with-hardware"], True),
                               (["--with-hardware", "--stubs-only"], False)):
            specs, _ = _specs(_parse_args(args))
            for name in ("track-controller-hw", "train-controller-hw"):
                spec = next(spec for spec in specs if spec.name == name)
                self.assertEqual(spec.args[1] == name, expected)

    def test_unknown_module_is_refused(self) -> None:
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            code = track_overflow.main(["--module", "nonsense"])
        self.assertEqual(code, track_overflow.EXIT_USAGE)
        self.assertIn("nonsense", errors.getvalue())

    def test_ctc_options_are_refused_for_other_stubs(self) -> None:
        self.assert_stub_refused(
            ["--as", TRACK_MODEL, "--harness", "h", "--run-on-ready"]
        )

    def test_resume_needs_a_pause(self) -> None:
        self.assert_stub_refused(
            ["--as", CTC_OFFICE, "--harness", "h", "--resume-after-ms", "5"]
        )

    def test_negative_counts_are_refused(self) -> None:
        self.assert_stub_refused(
            ["--as", CTC_OFFICE, "--harness", "h", "--delay-ms", "-1"]
        )

    def assert_stub_refused(self, args: list[str]) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                stub_module.main(args)
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
