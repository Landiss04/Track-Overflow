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

    def test_maintenance_does_not_hold_authority(self):
        # Maintenance changes who drives the switches, nothing else.
        result = self.scan(maintenance=True)
        self.assertEqual(result.track_circuits["2"].authority_blocks, 3)
        self.assertEqual(result.track_circuits["2"].speed_mps, 11)
        self.assertNotIn("maintenance_hold", [o.rule for o in result.overrides])

    def test_yellow_restriction_reports_its_reason(self):
        result = self.scan(values={"AUTH_2": True, "SIG_2_O": True})
        self.assertIn("aspect_speed_cap", [o.rule for o in result.overrides])

    def test_authority_passes_through_unchanged(self):
        # A wayside does not know the route or direction, so it does not
        # count blocks: the CTC Office stops authority before a hazard.
        for field in ("occupancy", "closed"):
            for hazard in ("3", "4", "6"):
                with self.subTest(field=field, hazard=hazard):
                    result = self.scan(**{field: {hazard: True}})
                    circuit = result.track_circuits["2"]
                    self.assertEqual(circuit.authority_blocks, 3)
                    self.assertNotIn("authority_truncated",
                                     [o.rule for o in result.overrides])

    def test_a_suggestion_is_never_raised(self):
        result = self.scan(suggestions={"2": Suggestion(11, 999999)})
        self.assertEqual(result.track_circuits["2"].authority_blocks, 999999)
        self.assertEqual(result.track_circuits["2"].speed_mps, 11)

    def test_a_switch_under_a_train_is_held_where_it_stands(self):
        config = ControllerConfig("TEST", "Test", self.config.block_ids,
                                  switches=(Switch("3", "3", "3", "4", "6"),))
        args = dict(config=config, values={"AUTH_3": True, "SW_3": True},
                    suggestions={"3": Suggestion(11, 2)}, current_switches={"3": False})
        self.assertTrue(self.scan(**args).switches["3"])
        held = self.scan(**args, occupancy={"3": True})
        self.assertFalse(held.switches["3"])
        self.assertEqual(held.track_circuits["3"].authority_blocks, 2)

    def test_restrictions_combine_without_restoring_speed_or_authority(self):
        args = dict(values={"AUTH_2": True, "SIG_2_O": True},
                    suggestions={"2": Suggestion(30, 3)})
        circuit = self.scan(**args).track_circuits["2"]
        # Posted limit 20 clamps first, then yellow halves it.
        self.assertEqual((circuit.speed_mps, circuit.authority_blocks), (10, 3))
        closed = self.scan(**args, closed={"2": True}).track_circuits["2"]
        self.assertEqual((closed.speed_mps, closed.authority_blocks), (0, 0))
