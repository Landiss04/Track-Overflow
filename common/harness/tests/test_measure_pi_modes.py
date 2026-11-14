"""measure --system: each hardware Pi is physical or simulated on its own."""

from __future__ import annotations

import pytest

from common.harness import measure
from common.harness.modules import TRACK_CONTROLLER_HW, TRAIN_CONTROLLER_HW


def _options(*argv):
    return measure._parse_args(["--system", *argv])


def test_default_waits_for_both_physical_pis():
    options = _options()
    assert options.pi_modes == {
        TRACK_CONTROLLER_HW: "physical",
        TRAIN_CONTROLLER_HW: "physical",
    }
    assert measure._pi_args(options) == {}


def test_global_flag_simulates_both_as_before():
    options = _options("--test-pi", "process")
    assert measure._pi_args(options) == {
        TRACK_CONTROLLER_HW: ["--test-pi", "process"],
        TRAIN_CONTROLLER_HW: ["--test-pi", "process"],
    }


def test_train_physical_and_track_simulated():
    options = _options(
        "--track-controller-pi", "process", "--train-controller-pi", "physical"
    )
    assert measure._pi_args(options) == {
        TRACK_CONTROLLER_HW: ["--test-pi", "process"]
    }


def test_track_physical_and_train_simulated():
    options = _options(
        "--track-controller-pi", "physical", "--train-controller-pi", "process"
    )
    assert measure._pi_args(options) == {
        TRAIN_CONTROLLER_HW: ["--test-pi", "process"]
    }


def test_one_module_flag_leaves_the_other_physical():
    assert measure._pi_args(_options("--train-controller-pi", "process")) == {
        TRAIN_CONTROLLER_HW: ["--test-pi", "process"]
    }


def test_a_physical_override_beats_the_global_flag():
    options = _options("--test-pi", "process", "--train-controller-pi", "physical")
    assert measure._pi_args(options) == {
        TRACK_CONTROLLER_HW: ["--test-pi", "process"]
    }


@pytest.mark.parametrize(
    "flag", ["--test-pi", "--track-controller-pi", "--train-controller-pi"]
)
def test_pi_options_need_system_mode(flag, capsys):
    with pytest.raises(SystemExit):
        measure._parse_args([flag, "process"])
    assert "require --system" in capsys.readouterr().err


def test_unknown_mode_is_a_usage_error(capsys):
    with pytest.raises(SystemExit):
        measure._parse_args(["--system", "--train-controller-pi", "usb"])
    assert "invalid choice" in capsys.readouterr().err


class _Stop(Exception):
    pass


@pytest.mark.parametrize(
    ("argv", "simulated"),
    [
        (["--track-controller-pi", "process"], {TRACK_CONTROLLER_HW}),
        (["--train-controller-pi", "process"], {TRAIN_CONTROLLER_HW}),
        (["--test-pi", "process"], {TRACK_CONTROLLER_HW, TRAIN_CONTROLLER_HW}),
        ([], set()),
    ],
)
def test_main_hands_test_pi_only_to_the_simulated_modules(
    argv, simulated, monkeypatch, capsys
):
    seen = {}

    def capture(module_options):
        seen.update(module_options)
        raise _Stop

    monkeypatch.setattr(measure, "system_specs", capture)
    with pytest.raises(_Stop):
        measure.main(["--system", "--seconds", "1", *argv])
    for name in (TRACK_CONTROLLER_HW, TRAIN_CONTROLLER_HW):
        assert ("--test-pi" in seen[name]) == (name in simulated), (name, seen[name])
    out = capsys.readouterr().out
    expected_waiting = sorted(
        {TRACK_CONTROLLER_HW, TRAIN_CONTROLLER_HW} - simulated
    )
    if expected_waiting:
        assert "Waiting for the assigned USB Pi(s): " + ", ".join(expected_waiting) in out
    else:
        assert "Waiting" not in out


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        ([], ["G1:Green:73"]),
        (["--dispatch", "R1:Red:16"], ["R1:Red:16"]),
        (["--dispatch", "G1:Green:65", "--dispatch", "R1:Red:16"],
         ["G1:Green:65", "R1:Red:16"]),
    ],
)
def test_main_sends_the_chosen_trains_to_the_ctc_office(argv, expected, monkeypatch):
    from common.harness.modules import CTC_OFFICE

    seen = {}

    def capture(module_options):
        seen.update(module_options)
        raise _Stop

    monkeypatch.setattr(measure, "system_specs", capture)
    with pytest.raises(_Stop):
        measure.main(["--system", "--test-pi", "process", "--seconds", "1", *argv])
    options = seen[CTC_OFFICE]
    assert options[0] == "--run-on-ready"
    sent = [options[i + 1] for i, value in enumerate(options) if value == "--dispatch"]
    assert sent == expected


def test_dispatch_needs_system_mode(capsys):
    with pytest.raises(SystemExit):
        measure._parse_args(["--dispatch", "R1:Red:16"])
    assert "require --system" in capsys.readouterr().err


def test_main_gives_the_engineer_gains_to_both_train_controllers(monkeypatch):
    from common.harness.modules import TRAIN_CONTROLLER_SW

    seen = {}

    def capture(module_options):
        seen.update(module_options)
        raise _Stop

    monkeypatch.setattr(measure, "system_specs", capture)
    with pytest.raises(_Stop):
        measure.main(["--system", "--test-pi", "process", "--seconds", "1"])
    gains = ["--engineer-gains", *measure.ENGINEER_GAINS]
    # The hardware controller needs them too, or a Red train waits (D024).
    for name in (TRAIN_CONTROLLER_SW, TRAIN_CONTROLLER_HW):
        assert seen[name][:3] == gains, (name, seen[name])
