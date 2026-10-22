"""Contract checks use the HW module's own decoder and encoder."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "TrackCtrlHw"))

from common.harness import hw_wayside_edges as hw  # noqa: E402
from common.harness.track_devices import TrackDevices  # noqa: E402
from common.harness.track_edges import BlockNames  # noqa: E402
from common.harness.wayside_edges import merge_ctc_inputs  # noqa: E402
from track_ctrl_hw import interface as api  # noqa: E402
from track_ctrl_hw.wire import inputs_from_wire, outputs_to_wire  # noqa: E402


def names():
    result = BlockNames()
    result.learn(["RED C-9", "RED D-10", "RED D-11", "GREEN K-63"])
    return result


def test_hw_input_contract():
    ctc = {
        "track_controller": {
            "suggestions": [
                {
                    "line": "Red",
                    "block_id": "9",
                    "suggested_speed_mps": 12,
                    "authority_blocks": 4,
                },
                {
                    "line": "Red",
                    "block_id": "9",
                    "suggested_speed_mps": 10,
                    "authority_blocks": 6,
                },
                {
                    "line": "Green",
                    "block_id": "63",
                    "suggested_speed_mps": 18,
                    "authority_blocks": 2,
                },
            ],
            "closed_blocks": [{"line": "Red", "block_id": "11"}],
            "switch_commands": [
                {"line": "Red", "switch_id": "9", "position": "normal"}
            ],
        }
    }
    model = {
        "controller": {
            "block_occupancy": {"RED C-9": True, "GREEN K-63": True},
            "switch_states": {},
            "crossing_states": {"RED D-11": True},
            "signal_states": {},
        }
    }
    decoded = inputs_from_wire(
        {
            "time_s": 18012.3,
            "ctc": hw.ctc_to_track_controller(ctc, "Red"),
            "track_model": hw.track_model_to_track_controller(
                model, "Red", names(), TrackDevices.load()
            ),
        }
    )
    assert decoded.time_s == 18012.3
    assert decoded.ctc.suggestions == {
        api.BlockRef("Red", "9"): api.Suggestion(10, 4)
    }
    assert decoded.ctc.switch_commands == {api.BlockRef("Red", "9"): "normal"}
    assert decoded.track_model.occupied_blocks == {
        api.BlockKey("Red", "C", "9")
    }
    assert decoded.track_model.crossings_active == {
        api.BlockKey("Red", "D", "11"): True
    }


def test_hw_output_contract_and_combined_ctc_report():
    key = api.BlockKey("Red", "C", "9")
    crossing = api.BlockKey("Red", "D", "11")
    encoded = outputs_to_wire(
        api.TrackControllerOutputs(
            track_model=api.TrackModelOutputs(
                track_circuits={key: api.TrackCircuitCommand(10, 4)},
                crossing_commands={crossing: True},
            ),
            ctc_reports=(
                api.CtcReport(
                    wayside_id="RTC-01",
                    line="Red",
                    sent_at_s=18012.3,
                    ready=True,
                    reason="",
                    blocks={key: api.BlockReport(occupied=True)},
                ),
            ),
        )
    )
    model = hw.track_controller_to_track_model(
        encoded, names(), TrackDevices.load()
    )
    assert model["commanded_speed_mps"] == {"RED C-9": 10.0}
    assert model["crossing_commands"] == {"RED D-11": True}
    red = hw.track_controller_to_ctc(encoded)
    green = {
        "occupancy": [],
        "switches": [],
        "crossings": [],
        "waysides": [
            {
                "wayside_id": "GTC-01",
                "line": "Green",
                "ready": True,
                "reason": "",
            }
        ],
    }
    joined = merge_ctc_inputs([green, red])
    assert [entry["line"] for entry in joined["waysides"]] == ["Green", "Red"]
    assert joined["occupancy"] == [
        {"line": "Red", "block_id": "9", "occupied": True}
    ]
