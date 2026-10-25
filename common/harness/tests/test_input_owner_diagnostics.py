"""INPUT-1 probes of membership semantics for owner review.

Synthetic snapshots run real edges, codecs and ready controller steps.
They do not establish freshness, physical completeness or Pi behavior.
"""

import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
for folder in (
    ROOT,
    ROOT / "TrackCtrlHw",
    ROOT / "TrackCtrlSW",
    ROOT / "TrackModel",
):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from common.harness import hw_wayside_edges as hw_edges  # noqa: E402
from common.harness import wayside_edges as sw_edges  # noqa: E402
from common.harness.track_devices import TrackDevices  # noqa: E402
from common.harness.track_edges import BlockNames  # noqa: E402
from track_ctrl import interface as sw_api  # noqa: E402
from track_ctrl import wire as sw_wire  # noqa: E402
from track_ctrl.controller import ControllerInputs  # noqa: E402
from track_ctrl.errors import WireFormatError as SwWireError  # noqa: E402
from track_ctrl.layout import build_default_system  # noqa: E402
from track_ctrl.module import SwTrackController  # noqa: E402
from track_ctrl.plc import compile_program  # noqa: E402
from track_ctrl_hw import interface as hw_api  # noqa: E402
from track_ctrl_hw import wire as hw_wire  # noqa: E402
from track_ctrl_hw.controller import HwTrackController  # noqa: E402
from track_ctrl_hw.errors import PlcError  # noqa: E402
from track_ctrl_hw.errors import WireFormatError as HwWireError  # noqa: E402
from track_ctrl_hw.territory import load_territory_file  # noqa: E402
from track_ctrl_hw.wayside import input_names, output_names  # noqa: E402
from track_model.interface import TrackConfig  # noqa: E402
from track_model.model import TrackModel  # noqa: E402
from track_model.module_process import layout_paths  # noqa: E402
from track_model.wire import decode_inputs, encode_outputs  # noqa: E402


def producer(occupancy):
    """Build the producer readback consumed by both edge variants."""
    return {
        "controller": {
            "block_occupancy": occupancy,
            "switch_states": {},
            "crossing_states": {},
            "signal_states": {},
        }
    }


@pytest.fixture
def edge_context():
    """Provide a small fixed name map and actual layout device mapping."""
    names = BlockNames()
    names.learn(("RED I-25", "RED X-76", "GREEN D-28", "GREEN Z-150"))
    return names, TrackDevices.load()


@pytest.mark.parametrize("edge", [hw_edges, sw_edges])
def test_member_omission_equals_false_but_whole_field_is_required(
    edge, edge_context
):
    names, devices = edge_context

    def mapped(occupancy):
        """Route one occupancy map through the selected real edge."""
        return edge.track_model_to_track_controller(
            producer(occupancy), "Red", names, devices
        )

    present = mapped({"RED I-25": True, "RED X-76": True})
    omitted = mapped({"RED X-76": True})
    explicit_false = mapped({"RED I-25": False, "RED X-76": True})
    assert omitted == explicit_false
    assert [entry["block_id"] for entry in present["occupied_blocks"]] == [
        "25",
        "76",
    ]
    assert [entry["block_id"] for entry in omitted["occupied_blocks"]] == [
        "76"
    ]
    assert mapped({})["occupied_blocks"] == []
    missing = producer({})
    del missing["controller"]["block_occupancy"]
    with pytest.raises(KeyError, match="block_occupancy"):
        edge.track_model_to_track_controller(missing, "Red", names, devices)


@pytest.mark.parametrize(
    "api,wire,error",
    [(hw_api, hw_wire, HwWireError), (sw_api, sw_wire, SwWireError)],
)
def test_missing_wire_fields_differ_from_valid_empty_lists(api, wire, error):
    valid = wire.inputs_to_wire(api.TrackControllerInputs(time_s=18000.0))
    decoded = wire.inputs_from_wire(valid)
    assert decoded.track_model.occupied_blocks == frozenset()
    assert decoded.ctc.closed_blocks == frozenset()
    for parent, field in (
        ("track_model", "occupied_blocks"),
        ("ctc", "closed_blocks"),
    ):
        missing = deepcopy(valid)
        del missing[parent][field]
        with pytest.raises(error):
            wire.inputs_from_wire(missing)


def test_normal_track_model_emits_every_loaded_block():
    model = TrackModel(TrackConfig(layout_paths(), ticket_probability=0.0))
    out = encode_outputs(
        model.step(
            0.1, decode_inputs({"controller": {}, "trains": {}}, 18000.1)
        )
    )
    occupancy = out["controller"]["block_occupancy"]
    assert set(occupancy) == {
        block.block_id for block in model.snapshot().blocks
    }
    assert len(occupancy) > 200
    assert all(value is False for value in occupancy.values())


def test_hw_owned_and_adjacent_members_reach_authority_through_edges(
    edge_context,
):
    names, devices = edge_context
    module = HwTrackController()
    territory = load_territory_file(
        ROOT / "TrackCtrlHw/data/waysides/red_wayside_2_integration_test.json"
    )
    module.load_territory(territory)
    assert {"OCC_25", "CLOSED_25", "OCC_76", "CLOSED_76"} <= input_names(
        territory
    )
    assert not {"OCC_80", "CLOSED_80"} & input_names(territory)
    assert not {"AUTH_76", "CMD_76_0"} & output_names(territory)
    with pytest.raises(PlcError) as rejected:
        module.load_program(
            "Red-2",
            "VAR_IN OCC_80\nVAR_OUT AUTH_25\nAUTH_25 := NOT OCC_80\n",
            "outside.plc",
        )
    assert any("OCC_80" in item for item in rejected.value.diagnostics)
    # Probe-only program: no production PLC or starter is changed.
    module.load_program(
        "Red-2",
        """VAR_IN OCC_25 CLOSED_25 OCC_76 CLOSED_76
VAR_OUT AUTH_25
AUTH_25 := NOT (OCC_25 OR CLOSED_25 OR OCC_76 OR CLOSED_76)
""",
        "input-owner-probe.plc",
    )
    authority = []
    cases = [
        ({}, []),
        ({"RED I-25": True}, []),
        ({"RED X-76": True}, []),
        ({}, ["25"]),
        ({}, ["76"]),
        ({"RED X-76": True}, []),
        ({"RED X-76": True}, []),
        ({}, []),
        ({"RED X-76": False}, []),
    ]
    for index, (occupied, closed) in enumerate(cases):
        ctc = {
            "track_controller": {
                "suggestions": [
                    {
                        "line": "Red",
                        "block_id": "25",
                        "suggested_speed_mps": 10,
                        "authority_blocks": 3,
                    }
                ],
                "closed_blocks": [
                    {"line": "Red", "block_id": block} for block in closed
                ],
                "switch_commands": [],
            }
        }
        inputs = hw_wire.inputs_from_wire(
            {
                "time_s": 18000.0 + index * 0.1,
                "ctc": hw_edges.ctc_to_track_controller(ctc, "Red"),
                "track_model": hw_edges.track_model_to_track_controller(
                    producer(occupied), "Red", names, devices
                ),
            }
        )
        out = module.step(0.1, inputs)
        assert out.ready
        circuits = {
            key.block_id: value
            for key, value in out.track_model.track_circuits.items()
        }
        assert "76" not in circuits
        authority.append(circuits["25"].authority_blocks)
    assert authority == [3, 0, 0, 0, 0, 0, 0, 3, 3]


def test_sw_own_members_replace_prior_snapshot_remote_namespace_unavailable(
    edge_context,
):
    names, devices = edge_context
    module = SwTrackController()
    for line in build_default_system():
        if line.key == "Green":
            module.load_track(line)
    module.load_starter_programs()
    card = next(
        card
        for card in module.controllers.values()
        if "28" in card.config.block_ids
    )
    assert card.config.controller_id == "GTC-02"
    assert {"OCC_28", "CLOSED_28"} <= card.input_names()
    assert not {"OCC_150", "CLOSED_150"} & card.input_names()
    diagnostics = card.check_program(
        compile_program(
            "VAR_IN OCC_150\nVAR_OUT AUTH_28\nAUTH_28 := NOT OCC_150\n"
        )
    )
    assert any(
        item.severity == "error" and "OCC_150" in item.message
        for item in diagnostics
    )
    bits = []
    for index, present in enumerate((True, True, False, False)):
        occupied = {"GREEN D-28": True, "GREEN Z-150": True} if present else {}
        ctc = {
            "track_controller": {
                "suggestions": [],
                "switch_commands": [],
                "closed_blocks": [
                    {"line": "Green", "block_id": block}
                    for block in (("28", "150") if present else ())
                ],
            }
        }
        inputs = sw_wire.inputs_from_wire(
            {
                "time_s": 18000.0 + index * 0.1,
                "ctc": sw_edges.ctc_to_track_controller(ctc, "Green"),
                "track_model": sw_edges.track_model_to_track_controller(
                    producer(occupied), "Green", names, devices
                ),
            }
        )
        assert module.step(0.1, inputs).ready
        image = card.build_scan_inputs(card.inputs)
        bits.append((image["OCC_28"], image["CLOSED_28"]))
        assert "OCC_150" not in image and "CLOSED_150" not in image
    assert bits == [(True, True), (True, True), (False, False), (False, False)]
    assert card.build_scan_inputs(
        ControllerInputs()
    ) == card.build_scan_inputs(
        ControllerInputs(occupancy={"28": False}, closed={"28": False})
    )
