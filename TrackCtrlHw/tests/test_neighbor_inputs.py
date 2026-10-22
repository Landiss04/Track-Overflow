"""Shared neighbor state is read-only, line-scoped and adjacency-scoped."""

from dataclasses import replace

import pytest

from track_ctrl_hw.controller import HwTrackController
from track_ctrl_hw.errors import PlcError
from track_ctrl_hw.interface import BlockKey, BlockRef
from track_ctrl_hw.territory import load_territory_file
from track_ctrl_hw.wayside import input_names, output_names
from tests.support import DATA, inputs


def red_two():
    controller = HwTrackController()
    territory = load_territory_file(
        DATA / "waysides/red_wayside_2_integration_test.json")
    controller.load_territory(territory)
    return controller, territory


def test_neighbor_occupancy_and_closure_use_the_same_readonly_scope():
    controller, territory = red_two()
    assert {"OCC_76", "CLOSED_76"} <= input_names(territory)
    assert "CLOSED_80" not in input_names(territory)
    assert not {"AUTH_76", "CMD_76_0"} & output_names(territory)
    controller.load_program("Red-2", """
VAR_IN OCC_76 CLOSED_76
VAR_OUT AUTH_25
AUTH_25 := NOT (OCC_76 OR CLOSED_76)
""", "neighbor.plc")
    for line, closed, occupied, expected in (
            ("Red", False, False, 3), ("Red", True, False, 0),
            ("Red", False, True, 0), ("Green", True, True, 3)):
        base = inputs(controller, suggestions={"25": (10, 3)})
        case = replace(
            base,
            ctc=replace(base.ctc, closed_blocks=frozenset(
                [BlockRef(line, "76")] if closed else [])),
            track_model=replace(base.track_model, occupied_blocks=frozenset(
                [BlockKey(line, "X", "76")] if occupied else [])))
        out = controller.step(0.1, case)
        assert out.ready
        circuits = {k.block_id: v for k, v in
                    out.track_model.track_circuits.items()}
        assert circuits["25"].authority_blocks == expected
        assert "76" not in circuits


@pytest.mark.parametrize("declaration", [
    "VAR_IN CLOSED_80", "VAR_OUT AUTH_76", "VAR_OUT CMD_76_0"])
def test_neighbor_scope_cannot_be_extended_by_program(declaration):
    controller, _ = red_two()
    with pytest.raises(PlcError):
        controller.load_program("Red-2", declaration + "\n", "neighbor.plc")
