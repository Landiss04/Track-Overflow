"""Red return diagnosis preserves the no-automatic-reversal rule."""

from ctc.routing import TrackGraph, authority, first_reversal, reversing_route
from ctc.scheduler import two_way_zones
from ctc.track_layout import load_layout
from ctc.tracking import YARD_ENTRIES, YARD_EXITS


def test_red_yard_metadata_matches_release_and_retirement():
    line = load_layout()["Red"]
    assert {b.block_id for b in line.blocks if b.to_yard} == {"9"}
    assert YARD_EXITS["Red"] == "9"
    assert YARD_ENTRIES["Red"] == {"9"}


def test_red_return_requires_real_switch_routing_or_manual_reversal():
    line = load_layout()["Red"]
    graph = TrackGraph(line)
    route = graph.route("16", "9", came_from="15")
    assert route is not None
    assert route[:3] == ("16", "17", "18")
    assert route[route.index("66"):route.index("66") + 3] == ("66", "52", "51")
    assert first_reversal(graph, route, came_from="15") == ""
    normal = {b.block_id: "normal" for b in line.blocks if b.switch}
    limit = authority(graph, "16", "9", {}, normal, route=route)
    assert (limit.end_block_id, limit.reason, limit.at) == (
        "66", "switch", "52",
    )
    assert graph.leg("52", "53").position == "normal"
    assert graph.leg("66", "52").position == "reverse"
    short = reversing_route(graph, "16", "9", came_from="15")
    assert short == tuple(str(n) for n in range(16, 8, -1))
    assert first_reversal(graph, short, came_from="15") == "16"
    outbound = graph.route("9", "16")
    assert outbound is not None
    zones = two_way_zones([outbound, route])
    # Out and back over 9 to 52 is one zone; the loop is one way.
    assert zones["9"] == zones["16"] == zones["52"]
    assert "66" not in zones
