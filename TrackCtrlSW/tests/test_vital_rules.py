"""Safety restrictions must hold even when the PLC requests permission."""
import unittest

from track_ctrl.layout import Block, ControllerConfig, WaysideSignal, Switch
from track_ctrl.vital import Suggestion, supervise


class VitalRulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.blocks = tuple(Block(str(i), i, "A", 100, 0, 20)
                            for i in range(1, 7))
        self.config = ControllerConfig("TEST", "Test", tuple(str(i) for i in range(1, 7)),
                                       signals=(WaysideSignal("2", "2"),))

    def scan(self, **changes):
        arguments = dict(
            config=self.config, blocks=self.blocks,
            values={"AUTH_2": True, "SIG_2_G": True},
            suggestions={"2": Suggestion(11, 3)},
            occupancy={}, closed={}, maintenance=False,
            ctc_switch_commands={}, manual_switches={}, current_switches={},
        )
        arguments.update(changes)
        return supervise(**arguments)

    def test_yellow_halves_speed_after_limit_with_integer_rounding(self):
        for requested, expected in ((11, 5), (35, 10), (1, 0), (0, 0)):
            with self.subTest(requested=requested):
                result = self.scan(values={"AUTH_2": True, "SIG_2_O": True},
                                   suggestions={"2": Suggestion(requested, 3)})
                self.assertEqual(result.track_circuits["2"].speed_mps, expected)
                self.assertEqual(result.track_circuits["2"].authority_blocks, 3)
                self.assertEqual(result.aspects["2"], "YELLOW")

    def test_green_and_super_green_do_not_reduce_speed(self):
        for suffix in ("G", "SG"):
            result = self.scan(values={"AUTH_2": True, f"SIG_2_{suffix}": True})
            self.assertEqual(result.track_circuits["2"].speed_mps, 11)

    def test_maintenance_overrides_permissive_plc_and_resumes_after_release(self):
        result = self.scan(maintenance=True)
        self.assertEqual(result.track_circuits["2"].authority_blocks, 0)
        self.assertEqual(result.track_circuits["2"].speed_mps, 0)
        self.assertIn("maintenance_hold", [o.rule for o in result.overrides])
        self.assertEqual(self.scan().track_circuits["2"].authority_blocks, 3)

    def test_maintenance_does_not_invent_unsuggested_circuits(self):
        self.assertEqual(self.scan(maintenance=True, suggestions={}).track_circuits, {})

    def test_yellow_restriction_reports_its_reason(self):
        result = self.scan(values={"AUTH_2": True, "SIG_2_O": True})
        self.assertIn("aspect_speed_cap", [o.rule for o in result.overrides])

    def test_authority_excludes_first_occupied_or_closed_block(self):
        for field in ("occupancy", "closed"):
            for hazard, expected in (("3", 0), ("4", 1), ("5", 2), ("6", 3)):
                with self.subTest(field=field, hazard=hazard):
                    result = self.scan(**{field: {hazard: True}})
                    circuit = result.track_circuits["2"]
                    self.assertEqual(circuit.authority_blocks, expected)
                    self.assertEqual(circuit.speed_mps, 11 if expected else 0)
                    if expected < 3:
                        self.assertIn("authority_truncated", [o.rule for o in result.overrides])

    def test_current_block_occupancy_is_not_counted_as_a_block_ahead(self):
        result = self.scan(occupancy={"2": True})
        self.assertEqual(result.track_circuits["2"].authority_blocks, 3)

    def test_unknown_track_does_not_extend_authority(self):
        for start, expected in (("5", 1), ("6", 0)):
            result = self.scan(values={f"AUTH_{start}": True, "SIG_2_G": True},
                               suggestions={start: Suggestion(11, 999999)})
            self.assertEqual(result.track_circuits[start].authority_blocks, expected)
        result = self.scan(blocks=tuple(b for b in self.blocks if b.block_id != "4"))
        self.assertEqual(result.track_circuits["2"].authority_blocks, 1)

    def test_switch_check_uses_actual_held_position_after_occupancy_lock(self):
        config = ControllerConfig("TEST", "Test", self.config.block_ids,
                                  switches=(Switch("3", "3", "3", "4", "6"),))
        args = dict(config=config, values={"AUTH_3": True, "SW_3": True},
                    suggestions={"3": Suggestion(11, 2)}, current_switches={"3": False})
        reverse = self.scan(**args)
        self.assertEqual(reverse.track_circuits["3"].authority_blocks, 0)
        held = self.scan(**args, occupancy={"3": True})
        self.assertFalse(held.switches["3"])
        self.assertEqual(held.track_circuits["3"].authority_blocks, 2)

    def test_restrictions_combine_without_restoring_speed_or_authority(self):
        args = dict(values={"AUTH_2": True, "SIG_2_O": True}, closed={"5": True})
        result = self.scan(**args)
        circuit = result.track_circuits["2"]
        self.assertEqual((circuit.speed_mps, circuit.authority_blocks), (5, 2))
        held = self.scan(**args, maintenance=True).track_circuits["2"]
        self.assertEqual((held.speed_mps, held.authority_blocks), (0, 0))
