"""Wire format, schematic layout, display units and the view model."""

from __future__ import annotations

import json
import unittest

from track_ctrl_hw import display, views
from track_ctrl_hw.errors import WireFormatError
from track_ctrl_hw.schematic import layout
from track_ctrl_hw.territory import parse_territory
from track_ctrl_hw.wire import (
    inputs_from_wire,
    inputs_to_wire,
    outputs_from_wire,
    outputs_to_wire,
    territory_from_wire,
    territory_to_wire,
)

from tests.support import inputs, keys, loaded, territory


class Wire(unittest.TestCase):
    def test_round_trips_through_json(self) -> None:
        controller = loaded(1, 2, 3)
        sent = inputs(
            controller, occupied=["4", "19"], closed=["30"],
            failures={"80": "power"}, suggestions={"4": (12, 3)},
            maintenance=True, switch_commands={"12": "reverse"},
            lit={"12": "green", "85": "super_green"},
        )
        wire = json.loads(json.dumps(inputs_to_wire(sent)))
        self.assertEqual(inputs_from_wire(wire), sent)
        out = controller.step(0.1, sent)
        self.assertEqual(
            out.ctc_reports[2].blocks[keys(controller)["85"]].signal_aspect,
            "super_green",
        )
        wire = json.loads(json.dumps(outputs_to_wire(out)))
        self.assertEqual(outputs_from_wire(wire), out)
        for number in (1, 2, 3):
            t = territory(number)
            wire = json.loads(json.dumps(territory_to_wire(t)))
            self.assertEqual(territory_from_wire(wire), t)

    def test_rejects_malformed_messages(self) -> None:
        good = inputs_to_wire(inputs(loaded(1), suggestions={"4": (12, 3)}))
        cases = []
        for path, value in (
            (("time_s",), "noon"),
            (("time_s",), True),
            (("ctc", "maintenance_mode"), "yes"),
            (("ctc", "closed_blocks"), {"line": "Green"}),
            (("ctc", "suggestions", 0, "speed_mps"), -1),
            (("ctc", "suggestions", 0, "speed_mps"), 1.5),
            (("ctc", "suggestions", 0, "block", "line"), ""),
            (("track_model", "failures"), [{"block": None, "kind": "power"}]),
        ):
            case = json.loads(json.dumps(good))
            target = case
            for step in path[:-1]:
                target = target[step]
            target[path[-1]] = value
            cases.append(case)
        cases.append("not an object")
        duplicated = json.loads(json.dumps(good))
        duplicated["ctc"]["suggestions"] *= 2
        cases.append(duplicated)
        for case in cases:
            with self.subTest(case=case), self.assertRaises(WireFormatError):
                inputs_from_wire(case)


class Schematic(unittest.TestCase):
    def test_loop_back_to_a_block_of_the_wayside(self) -> None:
        geometry = layout(territory(1))
        self.assertEqual((geometry["columns"], geometry["rowCount"]), (20, 1))
        (switch,) = geometry["switches"]
        # Points between 12 and 13; the reverse leg returns to block 1.
        self.assertEqual(switch["joint"], 12)
        self.assertEqual(switch["reverse"], {"kind": "loop", "col": 0,
                                             "level": 0})
        self.assertEqual(switch["signalCol"], 11.5)
        (crossing,) = geometry["crossings"]
        self.assertEqual(crossing["col"], 18.5)

    def test_legs_that_leave_the_wayside_are_stubs(self) -> None:
        first, second = layout(territory(3))["switches"]
        self.assertEqual(first["reverse"],
                         {"kind": "stub", "direction": -1, "label": "TO 101"})
        self.assertEqual(second["reverse"],
                         {"kind": "stub", "direction": 1, "label": "TO 100"})

    def test_a_y_branch_gets_its_own_row(self) -> None:
        blue = parse_territory({
            "line": "Blue", "wayside": "1",
            "blocks": [
                {"block_number": n, "section": "ABC"[(n - 1) // 5],
                 "length_m": 50, "speed_limit_kmh": 50,
                 **({"infrastructure": {"switch": "5-6; 5-11"}}
                    if n == 5 else {})}
                for n in range(1, 16)
            ],
        })
        geometry = layout(blue)
        self.assertEqual(geometry["rowCount"], 2)
        by_number = {b["number"]: b for b in geometry["blocks"]}
        self.assertEqual((by_number["10"]["row"], by_number["10"]["col"]),
                         (0, 9))
        # Leg C starts below, one column past the points.
        self.assertEqual((by_number["11"]["row"], by_number["11"]["col"]),
                         (1, 6))
        (switch,) = geometry["switches"]
        self.assertEqual(switch["reverse"], {"kind": "branch", "row": 1,
                                             "col": 6})


class Display(unittest.TestCase):
    def test_conversions_use_the_convention_factors(self) -> None:
        self.assertEqual(display.mph(12), "27 mph")       # 26.84
        self.assertEqual(display.mph(19.444444), "43 mph")
        self.assertEqual(display.feet(100), "328 ft")     # 328.08
        self.assertEqual(display.feet(86.6), "284 ft")    # 284.12
        self.assertEqual(display.blocks(1), "1 block")
        self.assertEqual(display.blocks(0), "0 blocks")

    def test_clock(self) -> None:
        self.assertEqual(display.clock(None), "--:--:--")
        self.assertEqual(display.clock(14 * 3600 + 32 * 60 + 7.9), "14:32:07")
        self.assertEqual(display.clock(86400 + 5), "00:00:05")


class Views(unittest.TestCase):
    def test_rows_show_display_units_and_states(self) -> None:
        controller = loaded(1)
        controller.step(0.1, inputs(
            controller, occupied=["4"], closed=["7"],
            failures={"9": "broken_rail"}, suggestions={"4": (12, 3)},
            lit={"12": "green"},
        ))
        wayside = controller.snapshot().waysides[0]
        rows = {row["block"]: row for row in views.block_rows(wayside)}
        self.assertEqual(rows["4"]["stateText"], "Occupied")
        self.assertEqual(rows["4"]["circuit"], "27 mph \u00b7 3 blocks")
        self.assertEqual(rows["7"]["badge"], "warning")
        self.assertEqual(rows["9"]["stateText"], "Broken rail")
        self.assertEqual(rows["1"]["circuit"], display.EM_DASH)
        self.assertEqual(rows["13"]["length"], "492 ft")
        office = views.office_rows(wayside)
        self.assertEqual(office, [{"block": "B-4", "speed": "27 mph",
                                   "authority": "3 blocks"}])
        (switch,) = views.switch_rows(wayside, maintenance=False)
        self.assertEqual(switch["commanded"], "Normal \u00b7 12\u201313")
        self.assertEqual(switch["agreeText"], "Agreeing")
        report = views.report_rows(wayside)
        self.assertEqual(len(report), 20)
        self.assertEqual(report[0]["key"], "Green \u00b7 A \u00b7 1")
        self.assertEqual(report[0]["signal"], display.EM_DASH)
        self.assertEqual(report[11]["signal"], "Green")

    def test_summary(self) -> None:
        wayside = loaded(3, programs=False).snapshot().waysides[0]
        self.assertEqual(views.territory_summary(wayside),
                         "Sections M\u2013O \u00b7 Blocks 74\u201388")


if __name__ == "__main__":
    unittest.main()
