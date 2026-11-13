"""Red outbound and return through the existing seven-core harness helper."""

from common.harness.tests.test_harness_red_loop import RedLoop
from common.harness.modules import CTC_OFFICE


def test_red_return_routes_via_66_and_retires_at_9():
    loop = RedLoop()
    assert loop.run_until(loop.red_stopped, limit_s=240), loop.red_blocks
    assert loop.red_blocks == [str(n) for n in range(9, 17)]
    loop.ctc.return_to_yard("R1")
    retired = []
    for _ in range(24_000):
        loop.step()
        retired.extend(item["train_id"] for item in
                       loop.outputs[CTC_OFFICE].get("retired_trains", []))
        if retired:
            break
    expected = ([str(n) for n in range(9, 67)]
                + [str(n) for n in range(52, 8, -1)])
    assert loop.red_blocks == expected, loop.red_blocks
    assert retired == ["R1"]
    assert not [event for event in loop.events if event[1] in {
        "TICK_REJECTED", "TRAIN_LEFT_TRACK", "PROTOCOL_ERROR"}]
