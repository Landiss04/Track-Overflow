"""Existing window backends drive remote cores through adapters."""

from common.hw_link.tests.test_transports_recovery import (
    make_relay,
    request,
    until,
)
from common.hw_link.remote_train import RemoteTrainFleet
from common.hw_link.remote_track import RemoteTrackController
from common.hw_link.relay import HardwareRelay
from common.hw_link.transport import ProcessTransport
from common.hw_link.cores import ROOT
from utils.harness_protocol import step_message


def test_console_backend_direct_mutations_and_methods_reach_pi(tmp_path):
    from train_ctrl.backend import ConsoleBackend

    relay, replies, events, views, errors = make_relay(tmp_path)
    fleet = RemoteTrainFleet(relay)
    try:
        relay.submit_step(request(1))
        until(lambda: "R1" in fleet)
        backend = ConsoleBackend(fleet=fleet)
        backend.select_train("R1")
        backend.select_operator(1)
        backend.commission_gains(120000, 8000)
        assert fleet.get("R1").armed
        assert fleet.get("R1").state.kp == 120000
        backend.select_operator(0)
        backend.set_manual(True)
        backend.set_target_mph(10)
        backend.toggle_service_brake()
        backend.set_target_temp_f(75)
        backend.set_interior_lights(False)
        backend.set_exterior_lights(False)
        backend.toggle_emergency_brake()
        assert views[-1]["trains"]["R1"]["state"]["emergency_brake"]
        backend.toggle_emergency_brake()
        assert not views[-1]["trains"]["R1"]["state"]["emergency_brake"]
        state = views[-1]["trains"]["R1"]["state"]
        assert state["manual"] and state["service_request"]
        assert not state["interior_lights"] and not state["exterior_lights"]
        assert state["target_mps"] > 0
        # A station beacon is the Pi's input, then the driver's announcement
        # assignment and clear timer both traverse RemoteState.
        frame = request(2)
        frame["inputs"]["trains"]["R1"]["inputs"]["beacon_station"] = "TEST"
        relay.submit_step(frame)
        until(lambda: len(replies) == 2)
        relay.call_action(
            "set_state",
            {"train_id": "R1", "field": "announcement", "value": ""},
        )
        backend.announce()
        assert views[-1]["trains"]["R1"]["state"]["announcement"] == "TEST"
        backend._announce_done("R1")
        assert views[-1]["trains"]["R1"]["state"]["announcement"] == ""
        assert backend.snapshot["train_count"] == 1
        assert not errors
        backend._ui.stop()
    finally:
        relay.close()


def test_track_state_load_reload_report_and_maintenance(tmp_path):
    from track_ctrl_hw.state import TrackControllerState
    from track_ctrl_hw.territory import load_territory_file
    from track_ctrl_hw.wire import inputs_to_wire
    from track_ctrl_hw.interface import (
        TrackControllerInputs,
        CtcInputs,
        BlockRef,
    )

    transport = ProcessTransport(
        "track-controller-hw", tmp_path / "track.jsonl"
    )
    relay = HardwareRelay("track-controller-hw", transport)
    remote = RemoteTrackController(relay)
    state = TrackControllerState(controller=remote)
    ready, replies, errors = [], [], []
    relay.ready.connect(lambda: ready.append(True))
    relay.reply.connect(replies.append)
    transport.diagnostic.connect(errors.append)
    relay.start()
    try:
        until(lambda: bool(ready))
        path = (
            ROOT
            / "TrackCtrlHw/data/waysides/red_wayside_1_integration_test.json"
        )
        plc = ROOT / "TrackCtrlHw/data/plc" / (path.stem + ".plc")
        state.loadDatabase(str(path))
        state.loadProgram(str(plc))
        territory = load_territory_file(path)
        assert remote.snapshot().waysides[0].program is not None
        # Reload preserves a compatible program through the real UI slot.
        state.loadDatabase(str(path))
        assert remote.snapshot().waysides[0].program is not None
        inputs = TrackControllerInputs(
            18000.1,
            ctc=CtcInputs(switch_commands={BlockRef("Red", "9"): "reverse"}),
        )
        relay.submit_step(
            step_message(7, 1, 0.1, 18000.1, inputs_to_wire(inputs))
        )
        until(lambda: len(replies) == 1)
        # Force an ACK snapshot without an extra core scan.
        remote.load_program(territory.wayside_id, plc.read_text(), plc.name)
        snapshot = remote.snapshot()
        assert snapshot.ticks == 1
        assert snapshot.waysides[0].report is not None
        assert snapshot.waysides[0].switch_requests
        assert not errors
    finally:
        state.close()
        relay.close()
