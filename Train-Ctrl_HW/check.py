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

from PySide6.QtCore import (
    Q_ARG,
    Q_RETURN_ARG,
    QMetaObject,
    QObject,
    QTime,
)
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
    backend.apply_bench_inputs({"commanded_speed": 27, "authority_blocks": 2})
    backend.toggle_emergency_brake()

    backend.spawn_train(114, "GREEN LINE", "GREEN K")
    expect(backend.snapshot["has_train"], "spawning did not produce a train")
    expect(backend.snapshot["train_id"] == "T-114",
           "the spawned train did not take the number asked for")
    expect(not backend.core.armed, "controller armed before commissioning")
    # The toy plant spends a block of authority every 100 m, and the
    # drives below cover kilometres, so give them room; the countdown
    # has its own check further on.
    backend.apply_bench_inputs({"authority_blocks": 200})
    if shots:
        window.grabWindow().save(str(shots / "01-signed-out.png"))

    # Signed out, nothing drives.
    backend.set_target_mph(40)
    backend.toggle_service_brake()
    expect(not backend.core.state.service_request,
           "service brake answered a signed-out operator")

    # Nothing in the operator bar may move when the gains are set:
    # the badge's label changes, its slot and the toggles do not.
    def bar_geometry() -> list:
        found = []
        for name in ("modeField", "gainsSlot"):
            item = window.findChild(QObject, name)
            found.append(None if item is None else
                         (item.property("x"), item.property("width")))
        return found

    # Engineer commissions the gains once; the role is then spent.
    backend.select_operator(1)
    _settle(app, 200)
    bar_before = bar_geometry()
    expect(backend.snapshot["operator"] == "engineer",
           "engineer sign-in failed")
    if shots:
        window.grabWindow().save(str(shots / "02-gains.png"))
    # The bench commissions by sending its inputs, with no separate
    # button for it.
    backend.apply_bench_inputs({"kp": 400000, "ki": 8000})
    expect(backend.core.armed, "commissioning did not arm the controller")
    _settle(app, mod.GAINS_HANDOVER_MS + 400)
    expect(backend.snapshot["operator"] == "driver",
           "console not handed over")
    expect(backend.snapshot["gains_locked"],
           "the gains did not lock after commissioning")
    bar_after = bar_geometry()
    expect(None not in bar_before and bar_before == bar_after,
           f"the operator bar moved when the gains were set: "
           f"{bar_before} -> {bar_after}")
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
           "the train is not pulling anything like its rated "
           "acceleration")
    if shots:
        window.grabWindow().save(str(shots / "03-driving.png"))

    # The emergency brake stops the train and latches until it is
    # stopped.
    backend.toggle_emergency_brake()
    expect(backend.core.state.power_w == 0.0,
           "power stayed on under e-brake")
    expect(not backend.core.state.service_brake,
           "the emergency brake reported the service brake as applied "
           "too")
    _settle(app, 200)
    if shots:
        window.grabWindow().save(str(shots / "04-ebrake.png"))
    backend.toggle_emergency_brake()
    expect(backend.core.state.emergency_brake,
           "e-brake released while the train was moving")
    stopped = _until(app, lambda: backend.core.state.actual_mps == 0.0, 30)
    expect(stopped,
           "the emergency brake never brought the train to a stand")
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

    # A reported emergency brake (a passenger pull) latches the
    # controller's own; a report of false never releases it, only
    # the driver does (D011).
    backend.apply_inputs({"brake_state": [True, False]})
    expect(backend.core.state.emergency_brake,
           "a reported pull did not latch the emergency brake")
    backend.apply_inputs({"brake_state": [False, False]})
    expect(backend.core.state.emergency_brake,
           "a report of false released the emergency brake")
    backend.toggle_emergency_brake()
    expect(not backend.core.state.emergency_brake,
           "the driver could not release it at a stand")
    if shots:
        window.grabWindow().save(str(shots / "04-stopped.png"))

    # The speed law: up to the rated acceleration, then nothing left
    # over once the train is sitting on its target. Ten times real
    # time earns its keep here, because a train takes three quarters
    # of a minute to reach line speed.
    backend.set_manual(False)
    backend.apply_inputs({"commanded_speed": 12.0})
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

    # Slowing to a lower target ends on it, not a mile an hour above
    # it: the brake lets go within the narrow band.
    backend.set_sim_rate(mod.SIM_RATES.index(10))
    backend.set_target_mph(35)
    _until(app, lambda: backend.snapshot["actual_mph"] > 34.8, 60)
    backend.set_target_mph(30)
    slowed = _until(app, lambda: (
        abs(backend.snapshot["actual_mph"] - 30.0) < 0.25
        and not backend.core.state.service_brake), 60)
    backend.set_sim_rate(mod.SIM_RATES.index(1))
    expect(slowed, "slowing to a lower target did not settle on it")

    # The numbers drawer renders and closes again.
    drawer = window.findChild(QObject, "numbersDrawer")
    expect(drawer is not None, "numbers drawer missing")
    if drawer is not None:
        drawer.setProperty("expanded", True)
        _settle(app, 300)
        if shots:
            window.grabWindow().save(str(shots / "05-numbers.png"))
        drawer.setProperty("expanded", False)

    # The Train Model interface is SI, in the shapes truth gives.
    _settle(app, 300)
    actual = backend.core.state.actual_mps
    backend.apply_inputs({"commanded_speed": 10.0, "actual_speed": -0.5})
    expect(backend.core.state.commanded_mps == 10.0,
           "the Train Model interface did not take m/s")
    expect(backend.core.state.actual_mps == -0.5,
           "a negative actual speed (rollback) was not kept signed")
    backend.apply_inputs({"actual_speed": actual})

    # The bench types what the console reads, and converts once on
    # the display side: in mph and Fahrenheit, out m/s and Celsius.
    backend.apply_bench_inputs({"commanded_speed": 42.5})
    expect(abs(backend.core.state.commanded_mps - 42.5 / mod.MPS_TO_MPH)
           < 1e-6, "the bench's mph did not convert to m/s")
    expect(abs(backend.snapshot["commanded_mph"] - 42.5) < 1e-3,
           "commanded speed did not come back as it was typed")
    backend.apply_bench_inputs({"speed_limit": 60.0})
    expect(abs(backend.core.state.speed_limit_mps - 60.0 / mod.MPS_TO_MPH)
           < 1e-6, "the bench could not set the speed limit")
    backend.apply_bench_inputs({"speed_limit": 43.5})
    backend.apply_bench_inputs({"cabin_temperature": 68})
    expect(abs(backend.core.state.cabin_temp_c - 20.0) < 0.01,
           "the bench's Fahrenheit did not convert to Celsius")
    expect(abs(backend.snapshot["cabin_temp_f"] - 68.0) < 0.01,
           "cabin temperature did not come back as it was typed")

    # A staged set applies in one call.
    backend.apply_bench_inputs({
        "commanded_speed": 31,
        "beacon_station": "DORMONT",
        "beacon_side": "R",
        "beacon_underground": True,
        "signal_light_ahead": "GREEN",
    })
    expect(backend.snapshot["beacon_station"] == "DORMONT"
           and backend.snapshot["beacon_side"] == "R"
           and backend.snapshot["beacon_underground"],
           "the beacon's three fields did not apply")
    expect(backend.snapshot["next_signal"] == "GREEN",
           "staged aspect did not apply")
    # A moving train carrying a false emergency report through every
    # other signal must not acquire an emergency brake on the way.
    expect(backend.core.state.actual_mps > 0.0,
           "this check needs a train that is moving")
    backend.apply_bench_inputs({"door_state_left": True,
                                "light_state_interior": False,
                                "brake_state_emergency": False})
    expect(not backend.core.state.emergency_brake,
           "sending inputs to a moving train engaged the emergency brake")
    _settle(app, 400)
    expect(backend.snapshot["fb_doors_left"],
           "the plant wrote over a door state the bench published")
    # and the console is looking at the reported state, not the
    # command, so what the bench publishes reaches the driver's tiles
    expect(backend.snapshot["fb_doors_left"]
           != backend.snapshot["doors_left"],
           "the reported door state is just echoing the command")
    expect(not backend.snapshot["fb_interior_lights"],
           "the plant wrote over a light state the bench published")

    # Only the platform side opens (truth beacon.md). The beacon above
    # put the platform on the right, so the left doors stay shut, and
    # platforms on both sides open either.
    backend.set_door("left", True)
    expect(not backend.snapshot["doors_left"],
           "the left doors opened with the platform on the right")
    backend.apply_bench_inputs({"beacon_side": "LR"})
    expect(backend.snapshot["platform_left"]
           and backend.snapshot["platform_right"],
           "platforms on both sides did not allow both doors")

    # The door interlock: a door commanded open while moving stays
    # shut (truth door-command.md).
    backend.apply_bench_inputs({"door_state_left": False})
    backend.set_door("left", True)
    _settle(app, 300)
    expect(not backend.snapshot["fb_doors_left"],
           "a door opened while the train was moving")
    # Pressed again at a stand, the same command still opens it: the
    # tile re-sends a command the plant has already answered once.
    backend.toggle_emergency_brake()
    _until(app, lambda: backend.core.state.actual_mps == 0.0, 30)
    backend.set_door("left", True)
    _settle(app, 300)
    expect(backend.snapshot["fb_doors_left"],
           "re-pressing 'Open left' at a stand did not open the door")
    # Moved off the platform side, an open door still closes.
    backend.apply_bench_inputs({"beacon_side": "R"})
    backend.set_door("left", False)
    expect(not backend.snapshot["doors_left"],
           "an open door off the platform side could not be closed")
    backend.toggle_emergency_brake()

    # Another train, running its own plant, with its own gains.
    first = backend.selected
    backend.spawn_train(301, "RED LINE", "f")
    second = backend.selected
    expect(second == "R-301", "spawning did not add the train asked for")
    expect(backend.fleet.get(second).state.authority_target == "F",
           "a block typed in lower case did not come back capitalised")
    expect(backend.snapshot["train_count"] == 2, "roster did not grow")
    backend.spawn_train(301, "RED LINE", "RED F")
    expect(backend.snapshot["train_count"] == 2,
           "spawning the same id twice added a second copy")
    expect(not backend.core.armed, "a new train came up commissioned")
    expect(backend.fleet.get(first).armed, "spawning disarmed the first train")
    # A new train is stopped, so this engages and releases cleanly,
    # and the train beside it is not touched either way.
    backend.toggle_emergency_brake()
    expect(backend.core.state.emergency_brake,
           "the new train has no e-brake")
    expect(not backend.fleet.get(first).state.emergency_brake,
           "one train's emergency brake reached another train")
    backend.toggle_emergency_brake()
    expect(not backend.core.state.emergency_brake,
           "the new train's e-brake would not release at a stand")
    backend.select_train(first)
    expect(backend.selected == first,
           "could not go back to the first train")

    # The console's train picker narrows the roster as the operator
    # types, and a pick selects that train.
    picker = window.findChild(QObject, "trainPicker")
    expect(picker is not None, "the console train picker is missing")
    if picker is not None:
        picker.setProperty("query", "r-301")
        found = [t["id"] for t in picker.property("matches").toVariant()]
        expect(found == [second],
               f"searching 'r-301' found {found}, not [{second}]")
        QMetaObject.invokeMethod(picker, "choose", Q_ARG("QVariant", 0))
        expect(backend.selected == second,
               "picking a search result did not select that train")
        picker.setProperty("query", "")
        backend.select_train(first)

    # The roster only signals when a train is added or removed, so the
    # pickers' lists are not rebuilt on every UI tick.
    roster_signals = []
    backend.roster_changed.connect(lambda: roster_signals.append(1))
    _settle(app, 500)
    expect(not roster_signals,
           "the roster signalled without a train being added or removed")

    # A set with one bad value changes nothing, and commissioning,
    # which cannot be undone, waits for the rest to apply.
    commanded = backend.core.state.commanded_mps
    try:
        backend.apply_inputs({"commanded_speed": commanded + 5.0,
                              "authority_blocks": "abc"})
        expect(False, "a bad authority value was accepted")
    except mod.InvalidInputError:
        pass
    expect(backend.core.state.commanded_mps == commanded,
           "a set with a bad value was half applied")
    backend.select_train(second)
    backend.select_operator(1)
    try:
        backend.apply_bench_inputs({"kp": 1000, "ki": 10,
                                    "door_state_left": True,
                                    "failure_status": "x",
                                    "speed_limit": "fast"})
    except mod.InvalidInputError:
        pass
    expect(not backend.core.armed,
           "a bad bench set commissioned the gains anyway")
    backend.select_operator(0)
    backend.select_train(first)

    # The bench sends only the rows that were edited, never the
    # rounded or paused readings of the rest.
    inputs = bench.findChild(QObject, "testInputs")
    expect(inputs is not None, "the bench inputs panel is missing")
    if inputs is not None:
        QMetaObject.invokeMethod(inputs, "stage",
                                 Q_ARG("QVariant", "commanded_speed"),
                                 Q_ARG("QVariant", 20))
        sent = QMetaObject.invokeMethod(
            inputs, "payload", Q_RETURN_ARG("QVariant"))
        sent = sent.toVariant() if hasattr(sent, "toVariant") else sent
        expect(sorted(sent) == ["commanded_speed"],
               f"the bench would send {sorted(sent)}, not just the edit")
        QMetaObject.invokeMethod(inputs, "release")

    backend.apply_bench_inputs({"authority_blocks": 3,
                                "signal_light_ahead": "RED"})
    expect(backend.core.state.authority_blocks == 3,
           "authority not taken as a block count")
    expect(backend.snapshot["next_signal"] == "RED", "aspect not set")

    # The Train Model does not report its failures, so the bench
    # injects them into the plant and the controller has to detect
    # each one from what comes back (REQ-FUNC-038). A detected failure
    # applies and latches the emergency brake and stops the train
    # (REQ-FUNC-037.2), and refuses driving and brake release until
    # the bench clears it. Ten times real time keeps the stops short.
    backend.set_sim_rate(mod.SIM_RATES.index(10))
    state = backend.core.state

    def drive_off(why: str) -> None:
        backend.set_target_mph(30)
        expect(_until(app, lambda: state.actual_mps > 5.0, 20),
               f"the train did not move {why}")

    # A Failure Status sent the old way is not an input any more.
    backend.apply_inputs({"failure_status": [True, True, True]})
    expect(not backend.core.failed,
           "a failure status from the Train Model was still taken")

    for row, key in (("failure_engine", "engine"),
                     ("failure_signal_pickup", "signal_pickup"),
                     ("failure_brake", "brake")):
        name = mod.FAILURE_TEXT[key]
        backend.apply_bench_inputs({"authority_blocks": 20,
                                    "commanded_speed": 30})
        drive_off(f"before the {name} test")
        backend.apply_bench_inputs({row: True})
        expect(not state.failures[key],
               f"the {name} was known before it could be seen")
        if key == "brake":
            # Only the service brake fails, and it is only seen
            # failing when it is asked for: until then the train runs
            # on, with nothing detected and no brake applied.
            _settle(app, 300)
            expect(not backend.core.failed and not state.emergency_brake
                   and state.actual_mps > 5.0,
                   "a brake failure was acted on before the brake was "
                   "asked for")
            backend.toggle_service_brake()
            asked = state.actual_mps
            expect(_until(app, lambda: state.failures[key], 10),
                   "the brake failure was never detected")
            expect(not state.fb_service_brake,
                   "a failed service brake reported itself applied")
            expect(state.fb_emergency_brake,
                   "the emergency brake did not report applied during "
                   "a brake failure")
            expect(not state.service_brake and not state.service_request,
                   "the failed service brake was still commanded")
            expect(state.actual_mps <= asked,
                   "the train sped up on a brake failure")
        else:
            expect(_until(app, lambda: state.failures[key], 10),
                   f"the {name} was never detected")
        expect(state.emergency_brake and state.power_w == 0.0,
               f"a detected {name} did not apply the emergency brake")
        if key == "signal_pickup":
            # No Track Signal to show: the console says so with "--"
            # rather than a 0 that reads like a real command.
            _settle(app, 200)
            for readout in ("commandedReadout", "authorityReadout"):
                tile = window.findChild(QObject, readout)
                shown = tile.property("value") if tile else None
                expect(shown == "--",
                       f"{readout} showed {shown!r}, not '--', during "
                       "a signal pickup failure")
        expect(_until(app, lambda: state.actual_mps == 0.0, 20),
               f"a detected {name} did not stop the train")
        if key == "brake" and shots:
            window.grabWindow().save(str(shots / "06-failure.png"))
            bench.grabWindow().save(str(shots / "07-test.png"))

        # Latched while the bench still has it in: no release, no
        # target, no service brake, and still detected at a stand.
        _settle(app, 300)
        expect(state.failures[key],
               f"the {name} cleared by itself while still injected")
        backend.toggle_emergency_brake()
        expect(state.emergency_brake,
               f"the emergency brake released during a {name}")
        backend.set_target_mph(30)
        expect(state.target_mps == 0.0,
               f"the driver set a target during a {name}")
        if key == "brake":
            backend.toggle_service_brake()
            expect(not state.service_request,
                   "the service brake could be asked for while failed")

        # The bench resolves it; the driver then releases the brake.
        backend.apply_bench_inputs({row: False})
        expect(not backend.core.failed,
               f"clearing the {name} on the bench did not resolve it")
        backend.toggle_emergency_brake()
        expect(not state.emergency_brake,
               f"the brake would not release once the {name} cleared")
        if key == "brake":
            # The service brake answers again.
            drive_off("after the brake failure cleared")
            backend.toggle_service_brake()
            expect(_until(app, lambda: state.fb_service_brake, 10),
                   "the service brake did not work after the failure "
                   "cleared")
            expect(not backend.core.failed,
                   "a working service brake was taken for a failure")
            backend.toggle_service_brake()
    backend.set_sim_rate(mod.SIM_RATES.index(1))

    # An engine failure at a steady cruise shows only once traction is
    # needed: the toy plant has no resistance, so holding speed takes
    # no power and a dead engine changes nothing until the train is
    # asked to speed up (OPEN_ISSUES.md).
    cruise = mod.ControllerCore()
    cruise.armed = True
    cruise.state.manual = True
    cruise.state.authority_blocks = 999
    cruise.set_target_mps(20 / mod.MPS_TO_MPH)
    for _ in range(round(60 / cruise.dt)):
        cruise.step()
    cruise.state.injected["engine"] = True
    for _ in range(round(10 / cruise.dt)):
        cruise.step()
    expect(not cruise.failed,
           "an engine failure was claimed at a cruise needing no power")
    cruise.set_target_mps(30 / mod.MPS_TO_MPH)
    for _ in range(round(5 / cruise.dt)):
        cruise.step()
    expect(cruise.failed == ["engine"] and cruise.state.emergency_brake,
           "an engine failure at cruise was not found once speed was "
           "asked for")

    # The spawner: one controller per train ID, which whoever owns
    # dispatch adds, removes and steps together, all or nothing, with
    # no toy plant (the Train Model does the physics).
    fleet = mod.TrainControllerFleet()
    t1 = fleet.add("T-1", "GREEN LINE")
    t2 = fleet.add("T-2", "RED LINE")
    expect(fleet.ids() == ["T-1", "T-2"] and len(fleet) == 2
           and "T-1" in fleet and t1.state.line == "GREEN LINE",
           "the fleet did not hold one controller per train")
    for bad_call, error in ((lambda: fleet.add("T-1"),
                             mod.DuplicateTrainError),
                            (lambda: fleet.get("T-9"),
                             mod.UnknownTrainError),
                            (lambda: fleet.remove("T-9"),
                             mod.UnknownTrainError)):
        try:
            bad_call()
            expect(False, f"the fleet did not raise {error.__name__}")
        except error:
            pass
    for core in (t1, t2):
        core.armed = True
    running = {"actual_speed": 10.0, "commanded_speed": 15.0,
               "authority_blocks": 5}
    standing = {"actual_speed": 0.0, "commanded_speed": 0.0,
                "authority_blocks": 0}
    sent = fleet.step_all(0.05, {"T-1": running, "T-2": standing})
    expect(sent["T-1"].power_w > 0.0 and sent["T-2"].power_w == 0.0,
           "stepping the fleet did not keep the trains apart")
    expect(t1.state.actual_mps == 10.0,
           "the fleet ran the toy plant; the Train Model moves the train")
    for bad_set, error in (
            ({"T-1": dict(running, commanded_speed=20.0),
              "T-2": {"actual_speed": "fast"}}, mod.InvalidInputError),
            ({"T-1": running}, mod.TrainControllerError),
            ({"T-1": running, "T-2": standing, "T-9": standing},
             mod.UnknownTrainError)):
        try:
            fleet.step_all(0.05, bad_set)
            expect(False, f"a bad fleet step did not raise "
                          f"{error.__name__}")
        except error:
            pass
    expect(t1.state.commanded_mps == 15.0,
           "a fleet step with one bad train changed another train")
    fleet.remove("T-1")
    expect(fleet.ids() == ["T-2"], "removing a train left it in the fleet")

    # Until the Track Model sends the count, the toy plant spends one
    # block of authority per BLOCK_LENGTH_M travelled, part-blocks
    # carried over.
    # carried over. A fresh core coasting at a steady 10 m/s, with no
    # power and no brake, covers exactly two and a half blocks.
    plant = mod.ControllerCore()
    plant.state.actual_mps = plant.state.target_mps = 10.0
    plant.state.authority_blocks = 3
    for _ in range(round(2.5 * mod.BLOCK_LENGTH_M / 10.0 / plant.dt)):
        plant._plant()
    expect(plant.state.authority_blocks == 1
           and abs(plant.state.block_progress_m
                   - 0.5 * mod.BLOCK_LENGTH_M) < 1e-6,
           "two and a half blocks of travel did not spend two blocks")
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
    backend.apply_bench_inputs({"authority_blocks": 6, "speed_limit": 40})
    expect(abs(backend.core.state.speed_limit_mps - 40 / mod.MPS_TO_MPH)
           < 1e-6, "the bench could not set the speed limit")

    # The line limit binds the target, and it may be above the car's
    # data-sheet 70 km/h if the line says so.
    backend.set_manual(True)
    backend.apply_bench_inputs({"speed_limit": 60})
    backend.set_target_mph(55)
    expect(abs(backend.snapshot["target_mph"] - 55) < 0.5,
           "the target was capped below the line limit")
    _settle(app, 300)

    # Removing a train takes everything of it out and moves the
    # selection on; removing it twice changes nothing.
    backend.select_train(second)
    backend.remove_train(second)
    expect(second not in backend.fleet,
           "removing a train left it in the simulation")
    expect(backend.selected == first,
           "the selection did not move to the remaining train")
    backend.remove_train(second)
    expect(backend.snapshot["train_count"] == 1,
           "removing a missing train changed the roster")

    # Announcements lock out for their duration, and carry the
    # beacon's station while they play.
    backend.announce()
    expect(backend.snapshot["announcing"], "announcement did not start")
    expect(backend.snapshot["announcement"] == "DORMONT",
           "the announcement did not carry the beacon's station")
    _settle(app, mod.ANNOUNCE_LOCKOUT_MS + 400)
    expect(not backend.snapshot["announcing"], "announcement never cleared")

    for message in warnings:
        print(f"QML warning: {message}", file=sys.stderr)
    for problem in problems:
        print(f"Behaviour: {problem}", file=sys.stderr)
    print(f"{len(warnings)} QML warnings, {len(problems)} behaviour "
          "problems")
    return 1 if warnings or problems else 0
