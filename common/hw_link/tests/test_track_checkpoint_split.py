"""A Track checkpoint holds what changes; the compiled programs are rebuilt."""

import pickle
from pathlib import Path

import pytest
from common.hw_link import agent, protocol as p
from common.hw_link.agent import PiLinkServer
from common.hw_link.cores import TrackCore
from track_ctrl_hw.territory import load_territory_file
from track_ctrl_hw.wire import territory_to_wire
from utils.harness_protocol import step_message

DATA = Path(__file__).resolve().parents[3] / "TrackCtrlHw" / "data"
BLOCK = {"line": "Red", "section": "C", "block_id": "9"}
WAYSIDES = sorted((DATA / "waysides").glob("red*.json"))


def loaded(with_programs=True):
    core = TrackCore()
    for path in WAYSIDES:
        territory = load_territory_file(path)
        core.action("load_territory", {"territory": territory_to_wire(territory)})
        if with_programs:
            program = DATA / "plc" / (path.stem + ".plc")
            core.action(
                "load_program",
                {
                    "wayside_id": territory.wayside_id,
                    "source": program.read_text(),
                    "file_name": program.name,
                },
            )
    return core


def inputs(tick):
    """Occupancy and a closure that come and go, so the state moves."""
    return {
        "time_s": 18000 + tick / 10,
        "ctc": {
            "closed_blocks": [BLOCK] if tick % 40 > 30 else [],
            "switch_commands": [],
            "route_requests": [],
            "suggestions": [],
        },
        "track_model": {
            "occupied_blocks": [BLOCK] if tick % 25 > 12 else [],
            "switch_positions": [],
            "crossings_active": [],
            "signal_aspects": [],
        },
    }


def step(core, tick):
    return core.step({"dt": 0.1, "sim_time_s": 18000 + tick / 10, "inputs": inputs(tick)})


def settled(view):
    """The view without the scan's wall-clock duration, which is never equal."""
    if isinstance(view, dict):
        return {
            key: settled(value)
            for key, value in view.items()
            if key != "last_duration_s"
        }
    if isinstance(view, list):
        return [settled(value) for value in view]
    return view


def test_checkpoint_leaves_out_the_compiled_programs():
    core = loaded()
    for tick in range(1, 60):
        step(core, tick)
    whole = len(pickle.dumps(core.controller))
    blob = pickle.dumps(core, protocol=pickle.HIGHEST_PROTOCOL)
    assert len(blob) < whole / 4
    assert b"track_ctrl_hw.plc" not in blob


def test_pickling_leaves_the_live_core_as_it_was():
    core = loaded()
    for tick in range(1, 30):
        step(core, tick)
    before = settled(core.view())
    pickle.dumps(core)
    for wayside in core.controller._waysides.values():
        assert wayside._program is not None and wayside._vital is not None
    assert settled(core.view()) == before
    step(core, 30)


def test_restored_core_steps_exactly_like_the_original():
    core = loaded()
    for tick in range(1, 120):
        step(core, tick)
    restored = pickle.loads(pickle.dumps(core))
    for wayside_id, wayside in core.controller._waysides.items():
        twin = restored.controller._waysides[wayside_id]
        assert twin._vital == wayside._vital
        assert twin._program == wayside._program
    assert settled(restored.view()) == settled(core.view())
    for tick in range(120, 400):
        assert step(restored, tick) == step(core, tick), f"tick {tick}"
    assert settled(restored.view()) == settled(core.view())


def test_a_wayside_with_no_program_loaded_round_trips():
    core = loaded(with_programs=False)
    for tick in range(1, 20):
        step(core, tick)
    restored = pickle.loads(pickle.dumps(core))
    for wayside in restored.controller._waysides.values():
        assert wayside._program is None and wayside._vital is not None
    for tick in range(20, 60):
        assert step(restored, tick) == step(core, tick)


def test_a_checkpoint_in_the_older_whole_core_form_still_restores():
    core = loaded()
    for tick in range(1, 20):
        step(core, tick)
    old = TrackCore.__new__(TrackCore)
    old.__setstate__({"controller": core.controller})
    assert old.controller is core.controller
    step(old, 20)


def test_agent_restart_from_a_lean_checkpoint_continues_the_run(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(agent, "CHECKPOINT_TICKS", 20)
    journal = tmp_path / "j.jsonl"
    module = "track-controller-hw"
    server = PiLinkServer(module, journal)
    server.handle(
        p.message(
            p.HELLO, 1, module=module, session="s", protocol=p.VERSION,
            agent_version="t", agent_hash="t",
        )
    )
    request_id = 1
    for path in WAYSIDES:
        territory = load_territory_file(path)
        request_id += 1
        server.handle(
            p.message(
                p.ACTION, request_id, action="load_territory",
                args={"territory": territory_to_wire(territory)},
            )
        )
        program = DATA / "plc" / (path.stem + ".plc")
        request_id += 1
        server.handle(
            p.message(
                p.ACTION, request_id, action="load_program",
                args={
                    "wayside_id": territory.wayside_id,
                    "source": program.read_text(),
                    "file_name": program.name,
                },
            )
        )
    for tick in range(1, 71):
        request_id += 1
        server.handle(
            step_message(request_id, tick, 0.1, 18000 + tick / 10, inputs(tick))
        )
    server.settle()
    server.wait_durable()
    server.close()

    restored = PiLinkServer(module, journal)
    # The checkpoint is the lean form, and the restart rebuilt the programs.
    assert restored._checkpoint_seq >= 1
    assert restored.core.controller._waysides
    for wayside in restored.core.controller._waysides.values():
        assert wayside._program is not None
    assert settled(restored.core.view()) == settled(server.core.view())
    restored.close()
