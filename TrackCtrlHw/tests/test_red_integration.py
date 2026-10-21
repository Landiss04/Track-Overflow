"""Red integration copies: topology agreement and PLC safety behavior."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
for folder in (ROOT, ROOT / "TrackModel", ROOT / "TrackCtrlSW"):
    sys.path.insert(0, str(folder))

from common.harness.track_devices import TrackDevices  # noqa: E402
from track_model.layout import load_layout  # noqa: E402
from track_ctrl.layout import load_layout_file  # noqa: E402
from track_ctrl_hw.controller import HwTrackController  # noqa: E402
from track_ctrl_hw.territory import load_territory_file  # noqa: E402
from track_ctrl_hw.wire import (  # noqa: E402
    territory_from_wire,
    territory_to_wire,
)  # noqa: E402
from tests.support import DATA, inputs  # noqa: E402


def loaded_red() -> HwTrackController:
    controller = HwTrackController()
    for number in (1, 2, 3):
        stem = f"red_wayside_{number}_integration_test"
        controller.load_territory(
            load_territory_file(DATA / "waysides" / f"{stem}.json")
        )
        controller.load_program(
            f"Red-{number}",
            (DATA / "plc" / f"{stem}.plc").read_text(),
            f"{stem}.plc",
        )
    return controller


class RedIntegration(unittest.TestCase):
    def test_exact_cuts_and_single_ownership(self) -> None:
        layout = json.loads((ROOT / "TrackModel/red_line.json").read_text())
        rows = {row["block_number"]: row for row in layout["blocks"]}
        owners = {}
        for number in (1, 2, 3):
            path = (
                DATA
                / "waysides"
                / f"red_wayside_{number}_integration_test.json"
            )
            database = json.loads(path.read_text())
            self.assertTrue(database["integration_test_only"])
            for block in database["blocks"]:
                n = block["block_number"]
                self.assertNotIn(n, owners)
                owners[n] = number
                self.assertEqual(block, rows[n])
        self.assertEqual(set(owners), set(range(1, 77)))
        self.assertEqual(owners[9], owners[75])
        self.assertEqual(rows[9]["section"], "C")
        self.assertIn("yard", rows[9]["next_blocks"])
        self.assertNotIn("yard", rows[75]["next_blocks"])
        self.assertEqual(rows[9]["infrastructure"]["switch"], "75-yard")

    def test_every_red_switch_agrees_in_all_readers(self) -> None:
        controller = loaded_red()
        track = load_layout([ROOT / "TrackModel/red_line.json"])
        devices = TrackDevices.load()
        software = load_layout_file(ROOT / "TrackModel/red_line.json")
        sw_by_id = {s.switch_id: s for s in software.switches}
        for wayside in controller.snapshot().waysides:
            territory = wayside.territory
            self.assertEqual(
                territory_from_wire(territory_to_wire(territory)), territory
            )
            for switch in territory.switches:
                place = devices.by_switch("Red", switch.switch_id)
                self.assertEqual(place.point, switch.point)
                model = track.switches[
                    track._by_number[("RED", int(place.point))]
                ]

                def number(value):
                    return (
                        "yard"
                        if value is None
                        else str(track.blocks[value].number)
                    )

                self.assertEqual(
                    (switch.normal_end, switch.reverse_end),
                    (
                        number(model.normal_block_id),
                        number(model.reverse_block_id),
                    ),
                )
                sw = sw_by_id[switch.switch_id]
                self.assertEqual(
                    (sw.point, sw.normal_end, sw.reverse_end),
                    (switch.point, switch.normal_end, switch.reverse_end),
                )
        yard = devices.by_switch("Red", "9")
        self.assertEqual((yard.point, yard.light), ("9", "8"))

    def test_every_five_bit_speed_is_capped_for_every_block(self) -> None:
        controller = loaded_red()
        limits = {
            b.key: int(b.speed_limit_mps + 1e-9)
            for w in controller.snapshot().waysides
            for b in w.territory.blocks
        }
        for speed in range(32):
            out = controller.step(
                0.1,
                inputs(
                    controller,
                    suggestions={k.block_id: (speed, 10) for k in limits},
                ),
            )
            self.assertTrue(out.ready)
            self.assertEqual(len(out.track_model.track_circuits), 76)
            for key, circuit in out.track_model.track_circuits.items():
                with self.subTest(block=key.block_id, speed=speed):
                    self.assertEqual(
                        circuit.speed_mps, min(speed, limits[key])
                    )
                    self.assertEqual(circuit.authority_blocks, 10)

    def test_crossings_drop_for_either_neighbor_or_own_block(self) -> None:
        for crossing, neighbors in (
            ("11", ("10", "11", "12")),
            ("47", ("46", "47", "48")),
        ):
            for occupied in neighbors:
                controller = loaded_red()
                out = controller.step(
                    0.1, inputs(controller, occupied=[occupied])
                )
                states = {
                    k.block_id: v
                    for k, v in out.track_model.crossing_commands.items()
                }
                self.assertTrue(states[crossing])
        out = loaded_red()
        result = out.step(0.1, inputs(out))
        self.assertFalse(any(result.track_model.crossing_commands.values()))

    def test_cross_boundary_separation_and_empty_next_preload(self) -> None:
        # 24/25 belongs to Red-1/Red-2; 45/46 to Red-2/Red-3.
        for first, second in (("24", "25"), ("45", "46")):
            controller = loaded_red()
            suggestions = {first: (15, 3), second: (15, 2)}
            out = controller.step(
                0.1,
                inputs(controller, occupied=[first], suggestions=suggestions),
            )
            self.assertTrue(
                all(
                    c.authority_blocks > 0
                    for c in out.track_model.track_circuits.values()
                )
            )
            out = controller.step(
                0.1,
                inputs(
                    controller,
                    occupied=[first, second],
                    suggestions=suggestions,
                ),
            )
            self.assertTrue(
                all(
                    c.authority_blocks == c.speed_mps == 0
                    for c in out.track_model.track_circuits.values()
                )
            )

    def test_closure_correspondence_signal_and_switch_lock(self) -> None:
        controller = loaded_red()
        out = controller.step(
            0.1,
            inputs(
                controller,
                closed=["10"],
                suggestions={"10": (15, 3)},
                reported={"9": "reverse"},
            ),
        )
        self.assertEqual(
            {
                k.block_id: v
                for k, v in out.track_model.switch_commands.items()
            }["9"],
            "normal",
        )
        self.assertEqual(
            {
                k.block_id: v
                for k, v in out.track_model.signal_commands.items()
            }["9"],
            "red",
        )
        circuit = next(
            v
            for k, v in out.track_model.track_circuits.items()
            if k.block_id == "10"
        )
        self.assertEqual((circuit.speed_mps, circuit.authority_blocks), (0, 0))
        out = controller.step(
            0.1, inputs(controller, occupied=["9"], reported={"9": "reverse"})
        )
        self.assertEqual(
            {
                k.block_id: v
                for k, v in out.track_model.switch_commands.items()
            }["9"],
            "reverse",
        )
        self.assertEqual(
            {
                k.block_id: v
                for k, v in out.track_model.signal_commands.items()
            }["9"],
            "red",
        )
