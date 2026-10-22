"""Harness end-of-tick time is displayed but cannot conceal physics lag."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication, QThread
from PySide6.QtTest import QTest

from common.harness.pacer import TickPacer
from train_model.state import TrainModelState
from tests.test_module_process import make_process, wire_inputs
from tests.test_contract import make_inputs
from utils.system_clock import SystemClock

DT = 0.1
START = 18_000.0


@pytest.fixture(autouse=True)
def app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


def advance(process, tick, trains, *, start=START, offset=0.0):
    return process.step(tick, DT, start + tick * DT + offset,
                        {"trains": trains})


def test_first_step_and_late_creation_align_without_rebasing() -> None:
    process, fleet = make_process()
    for tick in range(1, 46):
        trains = {"G1": wire_inputs()}
        if tick >= 22:
            trains["G2"] = wire_inputs()
        advance(process, tick, trains)
        for state in fleet:
            assert state.snapshot["clock"] == f"05:00:0{tick // 10}"
            checked = (tick // 15 * 15) or None
            if state.train_id == "G2" and tick < 30:
                checked = None
            assert state.snapshot["clock_drift_checked_tick"] == checked
            assert not state.snapshot["clock_drift_detected"]
            if checked is None:
                assert state.snapshot["clock_drift_s"] is None
            else:
                assert state.snapshot["clock_drift_s"] == pytest.approx(
                    0, abs=1e-6,
                )
    assert fleet.get("G1").elapsed_s == pytest.approx(4.5)
    assert fleet.get("G2").elapsed_s == pytest.approx(2.4)


def test_rejected_steps_lag_including_first_appearance_and_check_tick(
    capsys,
) -> None:
    process, fleet = make_process()
    for tick in range(1, 32):
        rejected = tick in (1, 15)
        reply = advance(process, tick, {
            "bad": wire_inputs(power_cmd_w=-1 if rejected else 100),
            "good": wire_inputs(),
        })
        bad = fleet.get("bad")
        checked = bad.snapshot["clock_drift_checked_tick"]
        assert checked == ((tick // 15 * 15) or None)
        if tick >= 15:
            assert bad.snapshot["clock_drift_s"] == pytest.approx(-0.2)
            assert bad.snapshot["clock_drift_detected"]
            assert fleet.get("good").snapshot["clock_drift_s"] == 0
        if tick == 15:
            assert "bad" in reply["rejected"]
        if tick == 30:
            assert bad.snapshot["clock"] == "05:00:03"
            assert bad.elapsed_s == pytest.approx(2.8)
    diagnostics = capsys.readouterr().err
    assert "train 'bad' clock drift -0.200000000 s at tick 15" in diagnostics
    assert "train 'good'" not in diagnostics


@pytest.mark.parametrize("offset,detected", [
    (0.5e-6, False), (-0.5e-6, False), (1.5e-6, True), (-1.5e-6, True),
])
def test_absolute_tolerance_and_later_healthy_check_clear_warning(
    offset: float, detected: bool,
) -> None:
    process, fleet = make_process()
    for tick in range(1, 31):
        advance(process, tick, {"G1": wire_inputs()},
                offset=offset if 15 <= tick < 30 else 0)
        snap = fleet.current.snapshot
        if 15 <= tick < 30:
            assert snap["clock_drift_s"] == pytest.approx(-offset)
            assert snap["clock_drift_detected"] is detected
            assert snap["clock_drift_checked_tick"] == 15
    assert fleet.current.snapshot["clock_drift_s"] == pytest.approx(
        0, abs=1e-6,
    )
    assert not fleet.current.snapshot["clock_drift_detected"]
    assert fleet.current.snapshot["clock_drift_checked_tick"] == 30
    assert fleet.current.elapsed_s == 3.0


def test_large_timestamps_use_absolute_tolerance() -> None:
    process, fleet = make_process()
    for tick in range(1, 16):
        advance(process, tick, {"G1": wire_inputs()}, start=1_000_000,
                offset=0.001 if tick == 15 else 0)
    assert fleet.current.snapshot["clock_drift_detected"]
    assert fleet.current.snapshot["clock_drift_s"] == pytest.approx(-0.001)


def test_retirement_empty_fleet_and_recreation_discard_old_timing() -> None:
    process, fleet = make_process()
    advance(process, 15, {"G1": wire_inputs(power_cmd_w=-1)})
    old = fleet.current
    assert old.snapshot["clock_drift_detected"]
    assert advance(process, 16, {}) == {"trains": {}}
    assert fleet.ids() == []
    assert process._epochs == {}
    assert fleet.current.snapshot["clock"] == "05:00:01"
    advance(process, 30, {})
    assert fleet.current.snapshot["clock"] == "05:00:03"
    assert fleet.current.snapshot["clock_drift_checked_tick"] is None
    advance(process, 31, {"G1": wire_inputs()})
    assert fleet.current is not old
    assert fleet.current.snapshot["clock_drift_s"] is None
    for tick in range(32, 46):
        advance(process, tick, {"G1": wire_inputs()})
    assert fleet.current.elapsed_s == 1.5
    assert fleet.current.snapshot["clock_drift_s"] == 0.0


def test_empty_fleet_first_timestamp_and_midnight_wrap() -> None:
    process, fleet = make_process()
    advance(process, 1, {}, start=86_399.8)
    assert fleet.current.snapshot["clock"] == "23:59:59"
    for tick in range(2, 31):
        advance(process, tick, {"G1": wire_inputs()}, start=86_399.8)
    assert fleet.current.snapshot["clock"] == "00:00:02"
    assert fleet.current.snapshot["clock_drift_s"] == pytest.approx(
        0, abs=1e-6,
    )
    # A whole day's physical lag must not disappear through display wrapping.
    process.step(45, DT, 172_802.8, {"trains": {"G1": wire_inputs()}})
    assert fleet.current.snapshot["clock_drift_detected"]
    assert fleet.current.snapshot["clock_drift_s"] < -86_399


def test_pause_and_rate_change_do_not_drive_checks_or_physics() -> None:
    results = []
    for speed in (1, 10):
        process, fleet = make_process()
        clock = SystemClock(speed=speed)
        now_s = [0.0]
        pacer = TickPacer(clock, now_s=lambda: now_s[0])
        clock.add_tick_listener(lambda sim_time_s, dt: process.step(
            clock.tick_count, dt, sim_time_s,
            {"trains": {"G1": wire_inputs()}},
        ))
        pacer.start()
        clock.resume()

        def paced_tick() -> None:
            now_s[0] += clock.tick_interval_s * 1.001
            pacer.poll()
            pacer.tick_finished()

        for _ in range(14):
            paced_tick()
        clock.pause()
        state = fleet.current
        before = state.snapshot
        for _ in range(30):
            now_s[0] += 1.0
            pacer.poll()
        # The existing idle timer may mark paused; it cannot check drift.
        QTest.qWait(550)
        assert state.snapshot == before
        assert not state.running
        assert state.elapsed_s == pytest.approx(1.4)
        assert state.snapshot["clock_drift_checked_tick"] is None
        clock.resume()
        paced_tick()
        assert state.snapshot["clock_drift_checked_tick"] == 15
        for _ in range(15):
            paced_tick()
        assert clock.tick_count == 30
        pacer.stop()
        results.append((state.snapshot, state.outputs(), state.elapsed_s))
    assert results[0] == results[1]


def test_snapshot_notifications_stay_on_owning_thread() -> None:
    process, fleet = make_process()
    advance(process, 1, {"G1": wire_inputs()})
    state = fleet.current
    threads = []
    state.snapshotChanged.connect(
        lambda: threads.append(QThread.currentThread())
    )
    advance(process, 15, {"G1": wire_inputs()})
    assert threads and all(thread == state.thread() for thread in threads)


def test_standalone_elapsed_clock_remains_available() -> None:
    state = TrainModelState()
    state.step(60.0, make_inputs())
    assert state.snapshot["clock"] == "00:01:00"
    assert state.elapsed_s == 60.0
    assert state.snapshot["clock_drift_s"] is None
    assert not state.snapshot["clock_drift_detected"]
