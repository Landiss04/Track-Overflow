"""Self-checks for the HW Train Controller.

Two of them, catching different kinds of breakage:

    check_snapshot_contract   every start-up, in milliseconds: do the
                              views and this backend still agree on
                              what the snapshot contains?
    run_check                 python main.py --check: drive a whole
                              session offscreen and report every QML
                              warning and every broken rule.

Neither imports main.py. run_check reads the constants it needs off
the module the backend came from, so there is no import cycle and no
second copy of the application module.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QTime
from PySide6.QtGui import QGuiApplication


# ========================================================== contract
def check_snapshot_contract(backend: Any, ui_dir: Path) -> bool:
    """Warn if the QML expects snapshot keys this file does not have.

    A view and a backend drift apart one copied file at a time, and
    the symptom is a wall of "Unable to assign [undefined]" with no
    hint as to which side is behind. This reads every s.<key> and
    snapshot.<key> out of the QML and names the missing ones.
    """
    import re

    have = set(backend.snapshot)
    pattern = re.compile(r"(?:\bs|snapshot)\.([a-z_][a-z0-9_]*)")
    missing: dict[str, set[str]] = {}
    for qml in sorted(ui_dir.rglob("*.qml")):
        wanted = set(pattern.findall(qml.read_text(encoding="utf-8")))
        gap = {k for k in wanted - have if not k.startswith("_")}
        if gap:
            missing[str(qml.relative_to(ui_dir))] = gap
    if not missing:
        return True

    print("This main.py is older than the QML beside it. These views "
          "read snapshot keys it does not provide:", file=sys.stderr)
    for name, keys in missing.items():
        print(f"  {name}: {', '.join(sorted(keys))}", file=sys.stderr)
    print("Copy the matching main.py, or revert the QML.", file=sys.stderr)
    return False


# ============================================================= check
def _until(app: QGuiApplication, ready, seconds: float = 60.0) -> bool:
    """Run the loop until something is true, or give up.

    A train accelerates at half a metre per second per second from a
    stand, so how long anything takes depends on the machine and on
    the simulation rate. Waiting on the condition keeps the test
    honest where waiting on a stopwatch made it flaky.
    """
    end = QTime.currentTime().addMSecs(int(seconds * 1000))
    while QTime.currentTime() < end:
        app.processEvents()
        if ready():
            return True
    return False


def _settle(app: QGuiApplication, ms: int) -> None:
    """Run the event loop for ms, so the timers above actually tick."""
    end = QTime.currentTime().addMSecs(ms)
    while QTime.currentTime() < end:
        app.processEvents()


def run_check(
    app: QGuiApplication,
    window: Any,
    bench: Any,
    backend: Any,
    warnings: list[str],
    shots: Path | None,
) -> int:
    """Walk the console offscreen and report anything that went wrong.

    Exits non-zero if QML logged a warning or the console let an
    operator do something the rules forbid.
    """
    mod = sys.modules[type(backend).__module__]
    problems: list[str] = []

    def expect(condition: bool, what: str) -> None:
        if not condition:
            problems.append(what)

    if shots:
        shots.mkdir(parents=True, exist_ok=True)

    _settle(app, 200)
    expect(not backend.snapshot["signed_in"], "console opened signed in")
    expect(not backend.snapshot["has_train"],
           "a train existed before spawning")
    expect(backend.snapshot["train_count"] == 0, "the roster started full")

    # Nothing to drive yet, and nothing crashes trying.
    backend.apply_inputs({"commanded_speed": 27, "authority_blocks": 2})
    backend.toggle_emergency_brake()

    backend.spawn_train(114, "GREEN LINE", "GREEN K")
    expect(backend.snapshot["has_train"], "spawning did not produce a train")
    expect(backend.snapshot["train_id"] == "T-114",
           "the spawned train did not take the number asked for")
    expect(not backend.core.armed, "controller armed before commissioning")
    if shots:
        window.grabWindow().save(str(shots / "01-signed-out.png"))

    # Signed out, nothing drives.
    backend.set_target_mph(40)
    backend.toggle_service_brake()
    expect(not backend.core.state.service_request,
           "service brake answered a signed-out operator")

    # Engineer commissions the gains once; the role is then spent.
    backend.select_operator(1)
    _settle(app, 200)
    expect(backend.snapshot["operator"] == "engineer",
           "engineer sign-in failed")
    if shots:
        window.grabWindow().save(str(shots / "02-gains.png"))
    # The bench commissions by sending its inputs, with no separate
    # button for it.
    backend.apply_inputs({"kp": 400000, "ki": 8000})
    expect(backend.core.armed, "commissioning did not arm the controller")
    _settle(app, mod.GAINS_HANDOVER_MS + 400)
    expect(backend.snapshot["operator"] == "driver", "console not handed over")
    expect(backend.snapshot["gains_locked"],
           "the gains did not lock after commissioning")
    backend.select_operator(1)
    expect(backend.snapshot["operator"] == "driver",
           "engineer role re-entered after the gains were set")
    backend.commission_gains(1, 1)
    expect(backend.core.state.kp == 400000,
           "gains changed after being locked")

    # Automatic locks the console; Manual hands it to the driver.
    expect(not backend.can_drive, "driver could act in Automatic")
    backend.set_manual(True)
    expect(backend.can_drive, "Manual did not unlock the console")
    backend.set_target_mph(35)
    moving = _until(app, lambda: backend.core.state.actual_mps > 2.0, 30)
    expect(moving, "train never got moving")
    expect(backend.core.state.accel_mps2 > 0.3,
           "the train is not pulling anything like its rated acceleration")
    if shots:
        window.grabWindow().save(str(shots / "03-driving.png"))

    # The emergency brake stops the train and latches until it is
    # stopped.
    backend.toggle_emergency_brake()
    expect(backend.core.state.power_w == 0.0, "power stayed on under e-brake")
    expect(not backend.core.state.service_brake,
           "the emergency brake reported the service brake as applied too")
    _settle(app, 200)
    if shots:
        window.grabWindow().save(str(shots / "04-ebrake.png"))
    backend.toggle_emergency_brake()
    expect(backend.core.state.emergency_brake,
           "e-brake released while the train was moving")
    stopped = _until(app, lambda: backend.core.state.actual_mps == 0.0, 30)
    expect(stopped, "the emergency brake never brought the train to a stand")
    expect(not backend.core.state.service_brake,
           "the e-brake reported the service brake engaged as well")
    backend.toggle_emergency_brake()
    expect(not backend.core.state.emergency_brake,
           "e-brake would not release at a stand")

    # Releasing a brake that is already released is not a refusal,
    # whether or not the train is moving. It used to engage one.
    expect(backend.core.release_emergency(),
           "releasing an already released brake was refused")
    expect(not backend.core.state.emergency_brake,
           "releasing an already released brake engaged it")

    # The Train Model's brake report drives the real brake, and the
    # train is stopped here, so it releases again cleanly.
    backend.apply_inputs({"ebrake_state": True})
    expect(backend.core.state.emergency_brake,
           "the bench's ebrake_state did not engage the brake")
    backend.apply_inputs({"ebrake_state": False})
    expect(not backend.core.state.emergency_brake,
           "the bench's ebrake_state did not release the brake")
    if shots:
        window.grabWindow().save(str(shots / "04-stopped.png"))

    # The speed law: up to the rated acceleration, then nothing left
    # over once the train is sitting on its target. Ten times real
    # time earns its keep here, because a train takes three quarters
    # of a minute to reach line speed.
    backend.set_manual(False)
    backend.apply_inputs({"commanded_speed": 12.0 * mod.MPS_TO_MPH})
    backend.set_sim_rate(mod.SIM_RATES.index(10))
    expect(abs(backend.core.dt - 10 / mod.CONTROL_HZ) < 1e-9,
           "the simulation rate did not reach the plant")
    pulling = _until(app, lambda: backend.core.state.actual_mps > 1.0, 20)
    expect(pulling, "the train did not pull away under power")
    # Wait on the gain rather than a stopwatch: offscreen rendering
    # can starve the control timer. At 10x a tick adds 0.25 m/s, so
    # 1 m/s takes about five ticks; at 1x it takes forty, two
    # seconds, so a one-second deadline still tells the rates apart.
    fast = backend.core.state.actual_mps
    faster = _until(
        app, lambda: backend.core.state.actual_mps - fast > 1.0, 1.0)
    expect(faster,
           "ten times real time did not move the train any faster")
    # Settled means on target and no longer pulling, not merely
    # passing through the right speed on the way up.
    settled = _until(app, lambda: (
        abs(backend.core.state.actual_mps - 12.0) < 0.1
        and abs(backend.core.state.accel_mps2) < 0.02), 90)
    backend.set_sim_rate(mod.SIM_RATES.index(1))
    expect(settled, "the train never settled on its commanded speed")
    expect(not backend.core.state.service_brake,
           "the service brake is fighting the speed law at target")
    backend.set_manual(True)

    # The numbers drawer renders and closes again.
    drawer = window.findChild(QObject, "numbersDrawer")
    expect(drawer is not None, "numbers drawer missing")
    if drawer is not None:
        drawer.setProperty("expanded", True)
        _settle(app, 300)
        if shots:
            window.grabWindow().save(str(shots / "05-numbers.png"))
        drawer.setProperty("expanded", False)

    # The bench drives the Train Model interface from its own window,
    # in one coherent set.
    _settle(app, 300)
    # The bench types what the console reads, and the backend keeps
    # SI: in mph and Fahrenheit, out m/s and Celsius.
    backend.apply_inputs({"commanded_speed": 42.5})
    expect(abs(backend.core.state.commanded_mps - 42.5 / mod.MPS_TO_MPH)
           < 1e-6, "the bench's mph did not convert to m/s")
    expect(abs(backend.snapshot["commanded_mph"] - 42.5) < 1e-3,
           "commanded speed did not come back as it was typed")
    backend.apply_inputs({"speed_limit": 60.0})
    expect(abs(backend.core.state.speed_limit_mps - 60.0 / mod.MPS_TO_MPH)
           < 1e-6, "the bench could not set the speed limit")
    backend.apply_inputs({"speed_limit": 43.5})
    backend.apply_inputs({"cabin_temperature": 68})
    expect(abs(backend.core.state.cabin_temp_c - 20.0) < 0.01,
           "the bench's Fahrenheit did not convert to Celsius")
    expect(abs(backend.snapshot["cabin_temp_f"] - 68.0) < 0.01,
           "cabin temperature did not come back as it was typed")

    # A staged set applies in one call.
    backend.apply_inputs({"commanded_speed": 31, "beacon": "PLATFORM B",
                         "signal_light_ahead": "GREEN"})
    expect(backend.snapshot["beacon"] == "PLATFORM B",
           "staged inputs did not apply")
    expect(backend.snapshot["next_signal"] == "GREEN",
           "staged aspect did not apply")
    # A moving train carrying ebrake_state false through every other
    # signal must not acquire an emergency brake on the way.
    expect(backend.core.state.actual_mps > 0.0,
           "this check needs a train that is moving")
    backend.apply_inputs({"door_state_left": True, "light_state_cabin": False,
                         "ebrake_state": False})
    expect(not backend.core.state.emergency_brake,
           "sending inputs to a moving train engaged the emergency brake")
    _settle(app, 400)
    expect(backend.snapshot["fb_doors_left"],
           "the plant wrote over a door state the bench published")
    # and the console is looking at the reported state, not the
    # command, so what the bench publishes reaches the driver's tiles
    expect(backend.snapshot["fb_doors_left"] != backend.snapshot["doors_left"],
           "the reported door state is just echoing the command")
    expect(not backend.snapshot["fb_lights"],
           "the plant wrote over a light state the bench published")

    # Another train, running its own plant, with its own gains.
    first = backend.selected
    backend.spawn_train(301, "RED LINE", "f")
    second = backend.selected
    expect(second == "R-301", "spawning did not add the train asked for")
    expect(backend.cores[second].state.authority_target == "F",
           "a block typed in lower case did not come back capitalised")
    expect(backend.snapshot["train_count"] == 2, "roster did not grow")
    backend.spawn_train(301, "RED LINE", "RED F")
    expect(backend.snapshot["train_count"] == 2,
           "spawning the same id twice added a second copy")
    expect(not backend.core.armed, "a new train came up commissioned")
    expect(backend.cores[first].armed, "spawning disarmed the first train")
    # A new train is stopped, so this engages and releases cleanly,
    # and the train beside it is not touched either way.
    backend.toggle_emergency_brake()
    expect(backend.core.state.emergency_brake, "the new train has no e-brake")
    expect(not backend.cores[first].state.emergency_brake,
           "one train's emergency brake reached another train")
    backend.toggle_emergency_brake()
    expect(not backend.core.state.emergency_brake,
           "the new train's e-brake would not release at a stand")
    backend.select_train(first)
    expect(backend.selected == first,
           "could not go back to the first train")

    backend.apply_inputs({"authority_blocks": 3,
                         "signal_light_ahead": "RED"})
    expect(backend.core.state.authority_blocks == 3,
           "authority not taken as a block count")
    expect(backend.snapshot["next_signal"] == "RED", "aspect not set")
    # A reported failure shows and does nothing else, for now: each
    # subsystem is to get its own response later.
    moving = backend.core.state.actual_mps
    backend.apply_inputs({"failure_brake": True})
    _settle(app, 300)
    expect(backend.snapshot["fault_brake"], "the failure was not recorded")
    expect(not backend.core.state.emergency_brake,
           "a reported failure pulled the emergency brake")
    expect(backend.core.state.actual_mps > 0 or moving == 0,
           "a reported failure stopped the train")
    if shots:
        bench.grabWindow().save(str(shots / "06-test.png"))
    backend.apply_inputs({"failure_brake": False})
    _settle(app, 200)
    expect(not backend.snapshot["fault_brake"], "the failure would not clear")

    # Authority is the count the Track Model sends; the controller
    # does not track blocks itself, so moving does not spend it.
    before_blocks = backend.core.state.authority_blocks
    _settle(app, 300)
    expect(backend.core.state.authority_blocks == before_blocks,
           "the controller spent authority on its own")
    backend.apply_inputs({"authority_blocks": 0})
    backend.core.enforce_safety()
    expect(not backend.core.state.emergency_brake,
           "running out of authority pulled the emergency brake")
    expect(backend.core.state.target_mps == 0.0,
           "a train with no authority still has a target to run to")
    backend.set_manual(True)
    backend.set_target_mph(30)
    expect(backend.core.state.target_mps == 0.0,
           "the driver could still ask a train with no authority to move")
    backend.set_manual(False)
    backend.set_manual(True)
    backend.set_target_mph(30)
    expect(backend.core.state.target_mps == 0.0,
           "the driver could set a target with no authority left")
    backend.apply_inputs({"authority_blocks": 6, "speed_limit": 40})
    expect(abs(backend.core.state.speed_limit_mps - 40 / mod.MPS_TO_MPH)
           < 1e-6, "the bench could not set the speed limit")

    # The line limit binds the target, and it may be above the car's
    # data-sheet 70 km/h if the line says so.
    backend.set_manual(True)
    backend.apply_inputs({"speed_limit": 60})
    backend.set_target_mph(55)
    expect(abs(backend.snapshot["target_mph"] - 55) < 0.5,
           "the target was capped below the line limit")
    _settle(app, 300)

    # Announcements lock out for their duration.
    backend.announce()
    expect(backend.snapshot["announcing"], "announcement did not start")
    _settle(app, mod.ANNOUNCE_LOCKOUT_MS + 400)
    expect(not backend.snapshot["announcing"], "announcement never cleared")

    for message in warnings:
        print(f"QML warning: {message}", file=sys.stderr)
    for problem in problems:
        print(f"Behaviour: {problem}", file=sys.stderr)
    print(f"{len(warnings)} QML warnings, {len(problems)} behaviour problems")
    return 1 if warnings or problems else 0
