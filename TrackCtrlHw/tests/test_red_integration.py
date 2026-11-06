"""Red integration copies: topology agreement and PLC safety behavior."""

from __future__ import annotations

import hashlib
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
        self.assertNotIn("yard", rows[9]["next_blocks"])
        self.assertIn("yard", rows[75]["next_blocks"])
        # Course source immediately before f27ba4e; byte-for-byte immutable.
        self.assertEqual(
            hashlib.sha256((ROOT / "TrackModel/red_line.json").read_bytes())
            .hexdigest(),
            "42afbb5505d4cb16e9efb8a3d995409973cd53fdafed4104be997a52c123ca33",
        )
        self.assertEqual(rows[9]["infrastructure"]["switch"], "75-yard")

    def test_every_red_switch_agrees_in_all_readers(self) -> None:
        controller = loaded_red()
        track = load_layout([ROOT / "TrackModel/red_line.json"])
        devices = TrackDevices.load()
        software = load_layout_file(ROOT / "TrackModel/red_line.json")
        # The SW reader keeps each switch as (point, normal end, reverse end).
        sw_by_id = software.switches
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
                self.assertEqual(
                    tuple(sw_by_id[switch.switch_id]),
                    (switch.point, switch.normal_end, switch.reverse_end),
                )
        for wayside in controller.snapshot().waysides:
            for block in wayside.territory.blocks:
                if block.key.block_id in {"9", "75"}:
                    self.assertEqual(
                        "yard" in block.next_blocks,
                        block.key.block_id == "9",
                    )
        yard = devices.by_switch("Red", "9")
        # Signals sit at switches (Braden, TM-2): its light is at 9.
        self.assertEqual((yard.point, yard.light), ("9", "9"))

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


class RedSwitchRouting(unittest.TestCase):
    # Listed switch ID, actual points, normal approach, reverse approach.
    ROUTES = (("27", "27", "28", "76"),
              ("15", "16", "15", "1"),
              ("32", "33", "32", "72"),
              ("38", "38", "39", "71"),
              ("43", "44", "43", "67"),
              ("52", "52", "53", "66"))

    def scan(self, key, **kwargs):
        controller = loaded_red()
        out = controller.step(0.1, inputs(controller, **kwargs))
        self.assertTrue(out.ready)
        return (
            {k.block_id: v for k, v in
             out.track_model.switch_commands.items()}[key],
            {k.block_id: v for k, v in
             out.track_model.signal_commands.items()}[key],
        )

    def test_reverse_approach_and_normal_closure_select_reverse(self):
        for key, point, normal, reverse in self.ROUTES:
            with self.subTest(switch=key):
                self.assertEqual(self.scan(key)[0], "normal")
                self.assertEqual(
                    self.scan(key, occupied=[reverse])[0], "reverse")
                self.assertEqual(
                    self.scan(key, closed=[normal])[0], "reverse")
                self.assertEqual(self.scan(
                    key, occupied=[reverse, normal])[0], "normal")
                self.assertEqual(self.scan(
                    key, occupied=[reverse], closed=[reverse])[0], "normal")

    def test_ctc_override_and_points_lock_every_switch(self):
        for key, point in (("9", "9"),) + tuple(
                (key, point) for key, point, _, _ in self.ROUTES):
            for requested in ("normal", "reverse"):
                opposite = "normal" if requested == "reverse" else "reverse"
                with self.subTest(switch=key, requested=requested):
                    self.assertEqual(self.scan(
                        key, switch_commands={key: requested})[0], requested)
                    self.assertEqual(self.scan(
                        key, occupied=[point], reported={key: opposite},
                        switch_commands={key: requested})[0], opposite)

    def test_signals_follow_reported_selected_route(self):
        for key, point, normal, reverse in self.ROUTES:
            for position, selected, unselected in (
                    ("normal", normal, reverse),
                    ("reverse", reverse, normal)):
                kwargs = dict(switch_commands={key: position},
                              reported={key: position})
                with self.subTest(switch=key, route=position):
                    self.assertNotEqual(self.scan(key, **kwargs)[1], "red")
                    self.assertEqual(self.scan(
                        key, closed=[selected], **kwargs)[1], "red")
                    self.assertEqual(self.scan(
                        key, occupied=[selected], **kwargs)[1], "red")
                    self.assertNotEqual(self.scan(
                        key, closed=[unselected], **kwargs)[1], "red")
                    self.assertEqual(self.scan(
                        key, occupied=[point], **kwargs)[1], "red")
            self.assertEqual(self.scan(
                key, switch_commands={key: "reverse"},
                reported={key: "normal"})[1], "red")

    def test_yard_switch_never_automatically_selects_yard(self):
        for kwargs in ({}, {"occupied": ["8"]}, {"closed": ["8"]}):
            self.assertEqual(self.scan("9", **kwargs)[0], "normal")
