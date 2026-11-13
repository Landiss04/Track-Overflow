"""Check explicit, independent Pi selection at the launcher boundary."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest

from common.harness import app
from common.harness.modules import (
    MODULE_NAMES,
    TRACK_CONTROLLER_HW,
    TRAIN_CONTROLLER_HW,
)

HW_MODULES = (TRACK_CONTROLLER_HW, TRAIN_CONTROLLER_HW)
SAMPLE_CONFIG = Path(__file__).resolve().parents[3] / "config/pi-testing.json"


def _write_config(tmp_path, data):
    path = tmp_path / "pi-testing.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _module_args(argv):
    specs, edges = app._specs(app._parse_args(argv))
    assert [spec.name for spec in specs] == list(MODULE_NAMES)
    assert edges is not None
    return {spec.name: spec.args for spec in specs}


def _assert_modes(arguments, expected):
    for name, args in arguments.items():
        mode = expected.get(name)
        if mode is None:
            assert "--test-pi" not in args, (name, args)
        else:
            assert args.count("--test-pi") == 1, (name, args)
            index = args.index("--test-pi")
            assert args[index + 1] == mode, (name, args)


@pytest.mark.parametrize(
    "track_simulated,train_simulated",
    list(itertools.product((False, True), repeat=2)),
)
def test_each_boolean_combination_selects_only_its_hw_module(
    tmp_path, track_simulated, train_simulated
):
    """Map true to process simulation and false to physical hardware."""
    selections = dict(zip(HW_MODULES, (track_simulated, train_simulated)))
    path = _write_config(tmp_path, selections)
    _assert_modes(
        _module_args(["--pi-config", str(path)]),
        {name: "process" for name, enabled in selections.items() if enabled},
    )


@pytest.mark.parametrize("selected", [None, *HW_MODULES])
def test_missing_config_members_stay_physical(tmp_path, selected):
    """Permit an empty config or one independently selected module."""
    data = {} if selected is None else {selected: True}
    path = _write_config(tmp_path, data)
    expected = {} if selected is None else {selected: "process"}
    _assert_modes(_module_args(["--pi-config", str(path)]), expected)


def test_default_does_not_load_a_config_from_the_working_directory(
    tmp_path, monkeypatch
):
    """Require an explicit path even when a sample exists in the cwd."""
    folder = tmp_path / "config"
    folder.mkdir()
    (folder / "pi-testing.json").write_text(
        json.dumps(dict.fromkeys(HW_MODULES, True)), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    _assert_modes(_module_args([]), {})


def test_shipped_sample_explicitly_selects_both_process_pis():
    """Keep the checked-in example usable through the actual CLI."""
    _assert_modes(
        _module_args(["--pi-config", str(SAMPLE_CONFIG)]),
        dict.fromkeys(HW_MODULES, "process"),
    )


@pytest.mark.parametrize("mode", ["process", "pty"])
@pytest.mark.parametrize("with_config", [False, True])
def test_legacy_global_flag_overrides_config_for_both_modules(
    tmp_path, mode, with_config
):
    """An explicit global flag takes precedence over false config values."""
    argv = ["--test-pi", mode]
    if with_config:
        path = _write_config(tmp_path, dict.fromkeys(HW_MODULES, False))
        argv += ["--pi-config", str(path)]
    _assert_modes(_module_args(argv), dict.fromkeys(HW_MODULES, mode))


@pytest.mark.parametrize(
    "track_mode,train_mode,expected",
    [
        ("physical", "process", {TRAIN_CONTROLLER_HW: "process"}),
        ("pty", "physical", {TRACK_CONTROLLER_HW: "pty"}),
        (
            "process",
            "pty",
            {TRACK_CONTROLLER_HW: "process", TRAIN_CONTROLLER_HW: "pty"},
        ),
        ("physical", "physical", {}),
    ],
)
def test_per_module_flags_override_global_and_config(
    tmp_path, track_mode, train_mode, expected
):
    """Keep each module's final transport independent of the other."""
    path = _write_config(tmp_path, dict.fromkeys(HW_MODULES, True))
    argv = [
        "--pi-config",
        str(path),
        "--test-pi",
        "pty",
        "--track-controller-pi",
        track_mode,
        "--train-controller-pi",
        train_mode,
    ]
    _assert_modes(_module_args(argv), expected)


@pytest.mark.parametrize(
    "flag,module",
    [
        ("--track-controller-pi", TRACK_CONTROLLER_HW),
        ("--train-controller-pi", TRAIN_CONTROLLER_HW),
    ],
)
def test_one_module_override_does_not_enable_the_other(flag, module):
    """Leave the unselected hardware module physical by default."""
    _assert_modes(_module_args([flag, "process"]), {module: "process"})


@pytest.mark.parametrize(
    "flag,module",
    [
        ("--track-controller-pi", TRACK_CONTROLLER_HW),
        ("--train-controller-pi", TRAIN_CONTROLLER_HW),
    ],
)
def test_physical_override_preserves_other_global_simulation(flag, module):
    """Apply a physical override only to its named module."""
    expected = {name: "process" for name in HW_MODULES if name != module}
    _assert_modes(
        _module_args(["--test-pi", "process", flag, "physical"]), expected
    )


@pytest.mark.parametrize(
    "flag", ["--track-controller-pi", "--train-controller-pi", "--test-pi"]
)
def test_unknown_pi_transport_is_a_usage_error(flag, capsys):
    """Reject transport modes outside the explicit CLI choices."""
    with pytest.raises(SystemExit) as caught:
        app._parse_args([flag, "automatic"])
    assert caught.value.code == 2
    assert flag in capsys.readouterr().err


def test_pi_options_do_not_change_stubs_only_specs(tmp_path):
    """Keep all seven stub identities and avoid hardware launcher flags."""
    path = _write_config(tmp_path, dict.fromkeys(HW_MODULES, True))
    specs, edges = app._specs(
        app._parse_args(
            [
                "--stubs-only",
                "--pi-config",
                str(path),
                "--test-pi",
                "pty",
                "--track-controller-pi",
                "physical",
            ]
        )
    )
    assert edges is None
    assert [spec.name for spec in specs] == list(MODULE_NAMES)
    for spec in specs:
        assert spec.args[:4] == ("--module", "stub", "--as", spec.name)
        assert "--test-pi" not in spec.args


@pytest.mark.parametrize(
    "contents",
    [
        "{",
        "null",
        "[]",
        "true",
        "1",
        '"process"',
        '{"track-controller-sw": true}',
        '{"track-controller-hw": true, "unexpected": false}',
        '{"track-controller-hw": 1}',
        '{"train-controller-hw": 0}',
        '{"track-controller-hw": "true"}',
        '{"train-controller-hw": null}',
        '{"track-controller-hw": []}',
    ],
)
def test_invalid_config_exits_before_qt_or_process_start(
    tmp_path, monkeypatch, capsys, contents
):
    """Reject malformed inputs as CLI usage errors before starting Qt."""
    path = tmp_path / "invalid.json"
    path.write_text(contents, encoding="utf-8")
    _assert_usage_error_before_start(path, monkeypatch, capsys)


@pytest.mark.parametrize("kind", ["missing", "directory", "permission"])
def test_unreadable_config_is_a_usage_error(
    tmp_path, monkeypatch, capsys, kind
):
    """Report filesystem failures at the same pre-start CLI boundary."""
    path = tmp_path / "unreadable.json"
    if kind == "directory":
        path.mkdir()
    elif kind == "permission":
        path.write_text("{}", encoding="utf-8")
        original_open = Path.open

        def reject_selected_file(self, *args, **kwargs):
            if self == path:
                raise PermissionError("diagnostic permission denied")
            return original_open(self, *args, **kwargs)

        monkeypatch.setattr(Path, "open", reject_selected_file)
    _assert_usage_error_before_start(path, monkeypatch, capsys)


def _assert_usage_error_before_start(path, monkeypatch, capsys):
    def unexpected_start(*args, **kwargs):
        pytest.fail("invalid config reached Qt or process construction")

    class UnexpectedApplication:
        instance = staticmethod(unexpected_start)

    monkeypatch.setattr(app, "QCoreApplication", UnexpectedApplication)
    monkeypatch.setattr(app, "Harness", unexpected_start)
    with pytest.raises(SystemExit) as caught:
        app.main(["--headless", "--pi-config", str(path)])
    assert caught.value.code == 2
    error = capsys.readouterr().err
    assert "usage:" in error
    assert "--pi-config" in error
