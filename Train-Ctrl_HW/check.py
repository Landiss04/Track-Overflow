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
    QPoint,
    QPointF,
    Qt,
    QTime,
)
from PySide6.QtGui import QGuiApplication, QWheelEvent
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

import train_ctrl as mod
from train_ctrl.bench_sim import SimTrain


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
    problems: list[str] = []

    def expect(condition: bool, what: str) -> None:
        if not condition:
            problems.append(what)

    # Every visible text the views had to cut short, by text, with where
    # it was seen. Qt marks an elided Text as truncated.
    cut: dict[str, list[str]] = {}

    def scan(where: str) -> None:
        _settle(app, 50)
        for name, win in (("console", window), ("bench", bench)):
            def walk(item: Any) -> None:
                if not item.isVisible():
                    return
                text = item.property("text")
                if item.property("truncated"):
                    short = item.implicitWidth() - item.width()
                    cut.setdefault(str(text), []).append(
                        f"{name} {where}, {short:.0f} px short")
                elif text and item.property("contentWidth") is not None:
                    # Text drawn on past the right edge of its window,
                    # which Qt does not count as truncated.
                    edge = item.mapToScene(
                        QPointF(item.property("contentWidth"), 0)).x()
                    if edge > win.width() + 1:
                        cut.setdefault(str(text), []).append(
                            f"{name} {where}, past the window edge")
                for child in item.childItems():
                    walk(child)
            walk(win.contentItem())

    def tick() -> None:
        # One bench tick now, rather than waiting on the control timer:
        # a bench edit reaches the controller on the next tick, as a
        # harness signal does (REQUIREMENTS.md M0).
        backend._step_all()

    def send(values: dict) -> None:
        backend.apply_bench_inputs(values)
        tick()

    def full_inputs(**changes: Any) -> dict:
        # Every EVERY_TICK signal, in SI, as the harness sends it.
        values = {"actual_speed": 5.0, "commanded_speed": 10.0,
                  "authority_blocks": 5, "emergency_brake_state": False,
                  "service_brake_state": False,
                  "door_state": [False, False], "light_state": [True, True],
                  "cabin_temperature": 21.0}
        values.update(changes)
        return values

    def drive(core: Any, sim: SimTrain, seconds: float) -> None:
        # A controller and its simulated train, tick by tick, the way
        # step_all and the bench pair them.
        for _ in range(round(seconds / core.dt)):
            core.apply_staged(mod.read_inputs(sim.outputs()))
            core.step()
            sim.step(core.commands())

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
    expect(backend.snapshot["clock"] == "05:00:00",
           "the clock does not start at D017's 05:00:00")
    # Authority holds until a block change or a new count arrives
    # (REQUIREMENTS.md M16), so the drives below only need it above 0.
    # Commanded speed is the driver's ceiling (REQUIREMENTS.md M1), so
    # give that room too.
    backend.apply_bench_inputs({"authority_blocks": 200,
                                "commanded_speed": 43})
    scan("01-signed-out")
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
    # Only the driver touches the emergency brake (REQUIREMENTS.md M2).
    backend.toggle_emergency_brake()
    expect(not backend.core.state.emergency_brake,
           "the engineer engaged the emergency brake")
    scan("02-gains")
    if shots:
        window.grabWindow().save(str(shots / "02-gains.png"))
    # The engineer's pop-up commissions the gains; the bench cannot.
    backend.apply_bench_inputs({"kp": 1000, "ki": 10})
    expect(not backend.core.armed, "the bench commissioned the gains")
    backend.commission_gains(400000, 8000)
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
    expect(backend.sim.accel_mps2 > 0.3,
           "the train is not pulling anything like its rated "
           "acceleration")
    scan("03-driving")
    if shots:
        window.grabWindow().save(str(shots / "03-driving.png"))

    # Pause holds everything: no train moves and the clock stops
    # (REQUIREMENTS.md M11). The bench's button drives this slot.
    backend.set_paused(True)
    held = (backend.core.state.actual_mps, backend.snapshot["clock"])
    _settle(app, 600)
    expect(backend.snapshot["paused"]
           and (backend.core.state.actual_mps,
                backend.snapshot["clock"]) == held,
           "the train or the clock moved while paused")
    backend.set_paused(False)
    expect(_until(app, lambda: backend.core.state.actual_mps > held[0], 5),
           "the train did not move on after resuming")

    # The emergency brake stops the train and latches until it is
    # stopped.
    backend.toggle_emergency_brake()
    expect(backend.core.state.power_w == 0.0,
           "power stayed on under e-brake")
    expect(not backend.core.state.service_brake,
           "the emergency brake reported the service brake as applied "
           "too")
    _settle(app, 200)
    scan("04-ebrake")
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
    # Two ticks first, so the brake state the controller receives has
    # caught up with the driver's release: a pull is a turn on.
    tick()
    tick()
    send({"emergency_brake_state": True})
    expect(backend.core.state.emergency_brake,
           "a reported pull did not latch the emergency brake")
    send({"emergency_brake_state": False})
    expect(backend.core.state.emergency_brake,
           "a report of false released the emergency brake")
    backend.toggle_emergency_brake()
    expect(not backend.core.state.emergency_brake,
           "the driver could not release it at a stand")
    # The driver's release overrides a state still reported engaged
    # (REQUIREMENTS.md M2): only a turn on is a pull.
    held = mod.ControllerCore()
    held.apply_staged(mod.read_inputs({"emergency_brake_state": True}))
    expect(held.state.emergency_brake, "a pull did not latch the brake")
    expect(held.release_emergency(), "a stopped train could not release")
    held.apply_staged(mod.read_inputs({"emergency_brake_state": True}))
    expect(not held.state.emergency_brake,
           "a state still reported engaged undid the driver's release")
    held.apply_staged(mod.read_inputs({"emergency_brake_state": False}))
    held.apply_staged(mod.read_inputs({"emergency_brake_state": True}))
    expect(held.state.emergency_brake,
           "a new pull after the release did not latch the brake")
    scan("04-stopped")
    if shots:
        window.grabWindow().save(str(shots / "04-stopped.png"))

    # The speed law: up to the rated acceleration, then nothing left
    # over once the train is sitting on its target. Ten times real
    # time earns its keep here, because a train takes three quarters
    # of a minute to reach line speed.
    backend.set_manual(False)
    scan("automatic")
    backend.sim.commanded_mps = 12.0
    backend.set_sim_rate(mod.SIM_RATES.index(10))
    # 10x ticks ten times as often; the step stays truth's 0.1 s
    # (REQUIREMENTS.md M11).
    expect(backend.core.dt == mod.TICK_S == 0.1
           and backend._control.interval() == 10,
           "10x changed the step instead of the tick rate")
    pulling = _until(app, lambda: backend.core.state.actual_mps > 1.0, 20)
    expect(pulling, "the train did not pull away under power")
    # Wait on the gain rather than a stopwatch: offscreen rendering
    # can starve the control timer. A tick adds at most 0.05 m/s, so
    # 1 m/s takes twenty ticks: 0.2 s at 10x, 2 s at 1x, so a
    # one-second deadline still tells the rates apart.
    fast = backend.core.state.actual_mps
    faster = _until(
        app, lambda: backend.core.state.actual_mps - fast > 1.0, 1.0)
    expect(faster,
           "ten times real time did not move the train any faster")
    # Settled means on target and no longer pulling, not merely
    # passing through the right speed on the way up.
    settled = _until(app, lambda: (
        abs(backend.core.state.actual_mps - 12.0) < 0.1
        and abs(backend.sim.accel_mps2) < 0.02), 90)
    backend.set_sim_rate(mod.SIM_RATES.index(1))
    expect(settled, "the train never settled on its commanded speed")
    expect(not backend.core.state.service_brake,
           "the service brake is fighting the speed law at target")
    # Automatic locks the console but never the driver's e-brake.
    expect(backend.can_ebrake and not backend.can_drive,
           "Automatic took the emergency brake from the driver")
    backend.set_manual(True)

    # Slowing to a lower target ends on it, not a mile an hour above
    # it: the brake lets go within the narrow band.
    send({"commanded_speed": 43})
    backend.set_sim_rate(mod.SIM_RATES.index(10))
    backend.set_target_mph(35)
    expect(_until(app, lambda: backend.snapshot["actual_mph"] > 34.8, 60),
           "the train never reached 35 mph to slow down from")
    backend.set_target_mph(30)
    slowed = _until(app, lambda: (
        abs(backend.snapshot["actual_mph"] - 30.0) < 0.25
        and not backend.core.state.service_brake), 60)
    backend.set_sim_rate(mod.SIM_RATES.index(1))
    expect(slowed, "slowing to a lower target did not settle on it")

    # The numbers drawer renders and closes again.
    # The dial's dead zone (45 to 135 degrees, bottom of the face) is
    # zero across all of it, and the face itself still reaches the top.
    dial = window.findChild(QObject, "speedDial")
    expect(dial is not None, "speed dial missing")
    if dial is not None:
        def dial_value(degrees: float) -> float:
            got = QMetaObject.invokeMethod(
                dial, "valueFor", Q_RETURN_ARG("QVariant"),
                Q_ARG("QVariant", degrees))
            return got.toVariant() if hasattr(got, "toVariant") else got
        top = dial.property("limit")
        expect(dial_value(60) == 0 and dial_value(120) == 0,
               "part of the dial's dead zone asks for speed")
        expect(abs(dial_value(44) - top) < 0.01 * top,
               "the end of the dial's face does not reach its top")

        # A drag past the top stays at the top, through the whole dead
        # zone, rather than wrapping round to 0.
        def drag_value(degrees: float) -> float:
            got = QMetaObject.invokeMethod(
                dial, "valueAt", Q_RETURN_ARG("QVariant"),
                Q_ARG("QVariant", degrees), Q_ARG("QVariant", True))
            return got.toVariant() if hasattr(got, "toVariant") else got
        dial_value(30)
        expect(drag_value(60) == top and drag_value(120) == top,
               "dragging past the top of the dial wrapped to 0")

        # The scale is the car's 70 km/h whatever is commanded; only
        # the target is capped at the commanded speed.
        expect(abs(top - 70 / 3.6 * mod.MPS_TO_MPH) < 0.01,
               "the dial's full scale is not the car's 70 km/h")
        send({"commanded_speed": 20})
        _settle(app, 100)
        expect(dial.property("limit") == top,
               "the dial's scale moved with the commanded speed")
        send({"commanded_speed": 43})

    drawer = window.findChild(QObject, "numbersDrawer")
    expect(drawer is not None, "numbers drawer missing")
    if drawer is not None:
        drawer.setProperty("expanded", True)
        _settle(app, 300)
        scan("05-numbers")
        if shots:
            window.grabWindow().save(str(shots / "05-numbers.png"))
        drawer.setProperty("expanded", False)

    # The Train Model interface is SI, in the shapes truth gives.
    _settle(app, 300)
    si = mod.TrainControllerFleet()
    si.add("T-9")
    si.step_all(0.1, {"T-9": full_inputs(commanded_speed=10.0,
                                         actual_speed=-0.5)},
                mod.CLOCK_START_S)
    expect(si.get("T-9").state.commanded_mps == 10.0,
           "the Train Model interface did not take m/s")
    expect(si.get("T-9").state.actual_mps == -0.5,
           "a negative actual speed (rollback) was not kept signed")

    # The bench types what the console reads, and converts once on
    # the display side: in mph and Fahrenheit, out m/s and Celsius.
    send({"commanded_speed": 42.5})
    expect(abs(backend.core.state.commanded_mps - 42.5 / mod.MPS_TO_MPH)
           < 1e-6, "the bench's mph did not convert to m/s")
    expect(abs(backend.snapshot["commanded_mph"] - 42.5) < 1e-3,
           "commanded speed did not come back as it was typed")
    send({"cabin_temperature": 68})
    expect(abs(backend.core.state.cabin_temp_c - 20.0) < 0.01,
           "the bench's Fahrenheit did not convert to Celsius")
    expect(abs(backend.snapshot["cabin_temp_f"] - 68.0) < 0.01,
           "cabin temperature did not come back as it was typed")

    # A staged set applies in one call.
    send({
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
    send({"door_state_left": True,
          "light_state_interior": False,
          "emergency_brake_state": False})
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

    # The door interlock: a door commanded open while moving stays
    # shut (truth door-command.md).
    send({"door_state_left": False})
    backend.set_door("left", True)
    _settle(app, 300)
    expect(not backend.snapshot["fb_doors_left"],
           "a door opened while the train was moving")
    # Pressed again at a stand, the same command still opens it: the
    # tile re-sends a command the plant has already answered once.
    # The platform is on the right, but away from a station either
    # side opens (REQUIREMENTS.md M6).
    backend.toggle_emergency_brake()
    _until(app, lambda: backend.core.state.actual_mps == 0.0, 30)
    backend.set_door("left", True)
    _settle(app, 300)
    expect(backend.snapshot["fb_doors_left"],
           "re-pressing 'Open left' at a stand did not open the door")
    # An open door always closes.
    backend.set_door("left", False)
    expect(not backend.snapshot["doors_left"],
           "the open left door could not be closed")
    backend.toggle_emergency_brake()

    # Another train, running its own plant, with its own gains.
    # Spawning it leaves the console on the train it shows.
    first = backend.selected
    backend.spawn_train(301, "RED LINE", "f")
    second = "R-301"
    expect(second in backend.fleet, "spawning did not add the train asked for")
    expect(backend.selected == first,
           "spawning switched the console to the new train")
    expect(backend.fleet.get(second).state.authority_target == "F",
           "a block typed in lower case did not come back capitalised")
    expect(backend.snapshot["train_count"] == 2, "roster did not grow")
    backend.spawn_train(301, "RED LINE", "RED F")
    expect(backend.snapshot["train_count"] == 2,
           "spawning the same id twice added a second copy")
    expect(not backend.fleet.get(second).armed,
           "a new train came up commissioned")
    expect(backend.fleet.get(first).armed, "spawning disarmed the first train")
    # Nobody drives a train before its gains are set: picking it signs
    # the driver out, the Driver role is refused, and the console stays
    # behind the sign-in view until the engineer commissions it.
    backend.select_train(second)
    expect(backend.snapshot["operator"] == ""
           and not backend.snapshot["signed_in"],
           "the driver was handed a train with no gains")
    backend.select_operator(0)
    expect(backend.snapshot["operator"] == "",
           "the driver signed in to a train with no gains")
    scan("08-needs-gains")
    if shots:
        window.grabWindow().save(str(shots / "08-needs-gains.png"))
    backend.select_operator(1)
    backend.commission_gains(400000, 8000)
    _settle(app, mod.GAINS_HANDOVER_MS + 400)
    expect(backend.snapshot["operator"] == "driver",
           "the driver did not get the train once its gains were set")
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

    # A light state the bench published never locks the driver out: a
    # pressed tile is answered even when the command is unchanged.
    backend.set_manual(True)
    send({"light_state_interior": False})
    backend.set_interior_lights(not backend.snapshot["fb_interior_lights"])
    tick()
    tick()
    expect(backend.snapshot["fb_interior_lights"],
           "a light tile did not answer after the bench published a "
           "light state")
    # An underground beacon from the bench turns the lights on, in
    # either mode (REQUIREMENTS.md M8).
    send({"beacon_underground": False})
    backend.set_interior_lights(False)
    backend.set_exterior_lights(False)
    tick()
    send({"beacon_underground": True})
    expect(backend.snapshot["interior_lights"]
           and backend.snapshot["exterior_lights"],
           "an underground beacon from the bench did not turn the "
           "lights on")
    # The bench sets its clock to a time of day, which the controller
    # receives next tick: noon, then 18:00, turns the lights on.
    backend.set_bench_time("12:00")
    tick()
    backend.set_interior_lights(False)
    backend.set_exterior_lights(False)
    tick()
    backend.set_bench_time("18:00")
    tick()
    expect(backend.snapshot["clock"] == "18:00:00",
           "the controller did not receive the time the bench set")
    expect(backend.snapshot["interior_lights"]
           and backend.snapshot["exterior_lights"],
           "setting the bench clock to 18:00 did not turn the lights on")
    before = backend.time_s
    backend.set_bench_time("25:00")
    expect(backend.time_s == before and "HH:MM" in
           backend.snapshot["bench_error"],
           "the bench took a time that is not one, or said nothing")
    # The bench's time is picked on three wheels, hours 0-23 and
    # minutes and seconds 0-59, each scrolled a notch at a time or
    # dragged, then set with the button beside them.
    wheels = bench.findChild(QQuickItem, "benchTimeWheels")
    minutes = bench.findChild(QQuickItem, "minutesWheel")
    expect(wheels is not None and minutes is not None,
           "the bench's time wheels are missing")
    if wheels is not None and minutes is not None:
        counts = [bench.findChild(QQuickItem, name).property("count")
                  for name in ("hoursWheel", "minutesWheel",
                               "secondsWheel")]
        expect(counts == [24, 60, 60],
               f"the time wheels run {counts}, not 24 / 60 / 60")
        for name, value in (("hours", 18), ("minutes", 30),
                            ("seconds", 15)):
            wheels.setProperty(name, value)
        centre = minutes.mapToScene(
            QPointF(minutes.width() / 2, minutes.height() / 2))
        QGuiApplication.sendEvent(bench, QWheelEvent(
            centre, centre, QPoint(0, 0), QPoint(0, -120), Qt.NoButton,
            Qt.NoModifier, Qt.NoScrollPhase, False))
        _settle(app, 200)
        expect(minutes.property("currentIndex") == 31,
               "a scroll notch did not step the minutes by one")
        point = centre.toPoint()
        QTest.mousePress(bench, Qt.LeftButton, Qt.NoModifier, point)
        for rise in range(0, 60, 4):
            QTest.mouseMove(bench, QPoint(point.x(), point.y() - rise), 10)
        QTest.mouseRelease(bench, Qt.LeftButton, Qt.NoModifier,
                           QPoint(point.x(), point.y() - 60), 10)
        _settle(app, 1500)
        expect(minutes.property("currentIndex") != 31,
               "dragging the minutes wheel did not move it")
        wheels.setProperty("minutes", 30)
        picked = QMetaObject.invokeMethod(
            wheels, "timeText", Q_RETURN_ARG("QVariant"))
        picked = picked.toVariant() if hasattr(picked, "toVariant") \
            else picked
        expect(picked == "18:30:15",
               f"the wheels read {picked!r}, not '18:30:15'")
        backend.set_bench_time(picked)
        tick()
        expect(backend.snapshot["clock"] == "18:30:15",
               "the time on the wheels did not reach the controller")
    backend.set_bench_time("05:00")
    tick()
    # The beacon is heard at a station, every tick; away from one,
    # only once, when the bench sends a beacon row.
    send({"at_station": False})
    expect("beacon_station" not in backend.sim.outputs(),
           "the beacon was heard away from a station")
    backend.apply_bench_inputs({"beacon_station": "DORMONT"})
    expect("beacon_station" in backend.sim.outputs(),
           "a beacon row the bench sent was not heard")
    tick()
    expect("beacon_station" not in backend.sim.outputs(),
           "a beacon sent once was heard again")
    send({"at_station": True})
    tick()
    expect(backend.snapshot["bench_at_station"]
           and "beacon_station" in backend.sim.outputs(),
           "the beacon was not heard every tick at a station")
    send({"at_station": False})

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
    commanded = si.get("T-9").state.commanded_mps
    try:
        si.step_all(0.1, {"T-9": full_inputs(commanded_speed=commanded + 5,
                                             authority_blocks="abc")},
                    mod.CLOCK_START_S)
        expect(False, "a bad authority value was accepted")
    except mod.InvalidInputError:
        pass
    expect(si.get("T-9").state.commanded_mps == commanded,
           "a set with a bad value was half applied")
    backend.select_train(second)
    doors = backend.core.state.fb_doors_left
    backend.apply_bench_inputs({"door_state_left": not doors,
                                "failure_status": "x",
                                "commanded_speed": "fast"})
    expect(backend.core.state.fb_doors_left == doors,
           "a bad bench set was half applied")
    # Refused on the bench, with the reason, never raised from a slot;
    # the next good send clears it.
    expect("commanded_speed" in backend.snapshot["bench_error"],
           "the bench did not say why its set was refused")
    backend.apply_bench_inputs({"cabin_temperature": 70})
    expect(backend.snapshot["bench_error"] == "",
           "the bench's refusal outlived a good send")
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

    send({"authority_blocks": 3, "signal_light_ahead": "RED"})
    expect(backend.core.state.authority_blocks == 3,
           "authority not taken as a block count")
    expect(backend.snapshot["next_signal"] == "RED", "aspect not set")

    # The Train Model does not report its failures, so the bench
    # injects them into the plant and the controller has to detect
    # each one from what comes back (REQ-FUNC-038). A detected failure
    # applies and latches the emergency brake and stops the train
    # (REQ-FUNC-037.2), and refuses driving until the bench clears it;
    # once stopped, the driver may release the brake in Manual only
    # (REQUIREMENTS.md M2, M3). Ten times real time keeps the stops
    # short.
    backend.set_sim_rate(mod.SIM_RATES.index(10))
    state = backend.core.state

    def drive_off(why: str) -> None:
        backend.set_target_mph(30)
        expect(_until(app, lambda: state.actual_mps > 5.0, 20),
               f"the train did not move {why}")

    # A Failure Status sent the old way is not an input any more.
    expect(mod.read_inputs({"failure_status": [True, True, True]}) == {},
           "a failure status from the Train Model was still taken")

    for row, key in (("failure_engine", "engine"),
                     ("failure_signal_pickup", "signal_pickup"),
                     ("failure_brake", "brake")):
        name = mod.FAILURE_TEXT[key]
        send({"authority_blocks": 20, "commanded_speed": 30})
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
            expect(_until(app, lambda: state.fb_emergency_brake, 2),
                   "the emergency brake did not report applied during "
                   "a brake failure")
            expect(state.service_brake and state.service_request,
                   "the service brake stopped being commanded under a "
                   "brake failure")
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
        scan("06-failure")
        if key == "brake" and shots:
            window.grabWindow().save(str(shots / "06-failure.png"))
            bench.grabWindow().save(str(shots / "07-test.png"))

        # Latched while the bench still has it in: no target, no
        # service brake, still detected at a stand, and no release in
        # Automatic.
        _settle(app, 300)
        expect(state.failures[key],
               f"the {name} cleared by itself while still injected")
        # The mode still switches, both ways, so the driver can try the
        # train in Manual; the failure keeps it stopped either way.
        backend.set_manual(False)
        expect(not state.manual,
               f"the mode would not switch to Automatic during a {name}")
        backend.toggle_emergency_brake()
        expect(state.emergency_brake,
               f"the emergency brake released in Automatic during a "
               f"{name}")
        scan("06-failure-automatic-release")
        backend.set_manual(True)
        expect(state.manual,
               f"the mode would not switch to Manual during a {name}")
        backend.set_target_mph(30)
        expect(state.target_mps == 0.0,
               f"the driver set a target during a {name}")
        if key == "brake":
            # Still live under a brake failure, so the driver can try
            # it (REQUIREMENTS.md M4).
            asked = state.service_request
            backend.toggle_service_brake()
            expect(state.service_request != asked,
                   "the service brake could not be asked for under a "
                   "brake failure")
            if state.service_request:
                backend.toggle_service_brake()
        # In Manual, at a stand, the driver may release it with the
        # failure still latched, and the failure does not engage it
        # again.
        backend.toggle_emergency_brake()
        expect(not state.emergency_brake,
               f"the driver could not release the emergency brake in "
               f"Manual during a {name}")
        _settle(app, 300)
        expect(state.failures[key] and not state.emergency_brake,
               f"the {name}, still latched, engaged the emergency brake "
               "again after the driver's release")
        expect(state.target_mps == 0.0 and state.power_w == 0.0
               and state.actual_mps == 0.0,
               f"the train moved after the release during a {name}")

        # The bench resolves it; the brake is already off.
        backend.apply_bench_inputs({row: False})
        expect(not backend.core.failed,
               f"clearing the {name} on the bench did not resolve it")
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
    plant = SimTrain()
    plant.authority_blocks = 999
    plant.commanded_mps = 43 / mod.MPS_TO_MPH
    drive(cruise, plant, cruise.dt)
    cruise.set_target_mps(20 / mod.MPS_TO_MPH)
    drive(cruise, plant, 60)
    plant.injected["engine"] = True
    drive(cruise, plant, 10)
    expect(not cruise.failed,
           "an engine failure was claimed at a cruise needing no power")
    cruise.set_target_mps(30 / mod.MPS_TO_MPH)
    drive(cruise, plant, 5)
    expect(cruise.failed == ["engine"] and cruise.state.emergency_brake,
           "an engine failure at cruise was not found once speed was "
           "asked for")

    # A brake failure is concluded on the tick after the service brake
    # is commanded, when its state still reads off; a working brake is
    # never taken for one (REQUIREMENTS.md M4).
    for failed in (False, True):
        quick = mod.ControllerCore()
        quick.armed = True
        quick.state.manual = True
        plant = SimTrain()
        plant.authority_blocks = 999
        plant.commanded_mps = 20 / mod.MPS_TO_MPH
        drive(quick, plant, quick.dt)
        quick.set_target_mps(20 / mod.MPS_TO_MPH)
        drive(quick, plant, 20)
        plant.injected["brake"] = failed
        quick.state.service_request = True
        drive(quick, plant, quick.dt)
        expect(not quick.failed,
               "a brake failure was concluded before the Train Model "
               "could answer")
        drive(quick, plant, quick.dt)
        if failed:
            expect(quick.failed == ["brake"]
                   and quick.state.emergency_brake
                   and quick.state.service_brake,
                   "a brake failure was not concluded on the next tick, "
                   "with the service brake still commanded")
        else:
            drive(quick, plant, 5)
            expect(not quick.failed,
                   "a working service brake was taken for a failure")

    # Doors are the controller's (REQUIREMENTS.md M6): never opened
    # while moving; in Automatic, opened on the platform side at a new
    # station once stopped, closed when the Track Signal resumes, and
    # the train leaves only once Door State reports them closed.
    door = mod.ControllerCore()
    door.armed = True
    plant = SimTrain()
    plant.commanded_mps = plant.actual_mps = 10.0
    plant.authority_blocks = 999
    plant.beacon_side = "R"
    # Applied, not stepped: a step here would make the stop below a
    # Track Signal falling to 0 from 999 blocks, a pickup failure.
    door.apply_staged(mod.read_inputs(plant.outputs()))
    door.command_door("right", True)
    expect(not door.state.doors_right,
           "a door was commanded open while moving")

    def stopped() -> bool:
        return abs(door.state.actual_mps) < mod.STANDSTILL_MPS
    plant.beacon_station = "DORMONT"
    plant.at_station = True
    plant.commanded_mps, plant.authority_blocks = 0.0, 0
    drive(door, plant, 30)
    expect(stopped() and door.state.fb_doors_right
           and not door.state.fb_doors_left,
           "Automatic did not open the platform side at the station")
    # Fed by hand from here, so Door State says only what is sent.
    door.apply_staged(mod.read_inputs({"commanded_speed": 10.0,
                                       "authority_blocks": 3}))
    door.step()
    expect(not door.state.doors_right,
           "the doors were not closed when the Track Signal resumed")
    door.step()
    expect(door.state.target_mps == 0.0,
           "the train left before Door State reported the doors closed")
    door.apply_staged(mod.read_inputs({"door_state": [False, False]}))
    door.step()
    expect(door.state.target_mps > 0.0,
           "the train did not leave once the doors reported closed")
    plant.actual_mps = 5.0
    plant.at_station = False
    plant.commanded_mps, plant.authority_blocks = 0.0, 0
    drive(door, plant, 30)
    expect(stopped() and not door.state.doors_right,
           "the doors opened at a stop with no new station")

    # Manual, at a station: only the platform side opens
    # (REQUIREMENTS.md M6).
    door = mod.ControllerCore()
    door.armed = True
    door.state.manual = True
    plant = SimTrain()
    plant.commanded_mps = plant.actual_mps = 10.0
    plant.authority_blocks = 999
    plant.beacon_side = "R"
    door.apply_staged(mod.read_inputs(plant.outputs()))
    plant.beacon_station = "DORMONT"
    plant.at_station = True
    plant.commanded_mps, plant.authority_blocks = 0.0, 0
    drive(door, plant, 30)
    expect(stopped() and not door.command_door("left", True)
           and door.command_door("right", True),
           "at a station Manual did not open only the platform side")

    # The controller only commands (REQUIREMENTS.md M0): stepping it
    # sends power and moves nothing it receives.
    core = mod.ControllerCore()
    core.armed = True
    core.apply_staged(mod.read_inputs({"commanded_speed": 10.0,
                                       "authority_blocks": 5,
                                       "actual_speed": 0.0}))
    core.step()
    expect(core.commands().power_w > 0.0
           and core.state.actual_mps == 0.0,
           "stepping the controller moved the train itself")

    # The harness must send every train the full set each tick: one
    # missing signal refuses the whole tick and no train steps, so a
    # stale Brake State can never trip a false brake failure.
    fleet = mod.TrainControllerFleet()
    fleet.add("T-1").armed = True
    full = full_inputs()
    start = mod.CLOCK_START_S
    fleet.step_all(0.1, {"T-1": full}, start)
    before = fleet.get("T-1").state.actual_mps
    # Brake State is two signals (REQUIREMENTS.md M18), each required.
    short = {k: v for k, v in full.items() if k != "service_brake_state"}
    short["actual_speed"] = 9.0
    try:
        fleet.step_all(0.1, {"T-1": short}, start)
        expect(False, "a tick without the service brake state was "
               "accepted")
    except mod.InvalidInputError:
        pass
    expect(fleet.get("T-1").state.actual_mps == before,
           "a refused tick still changed the train")
    # The step is truth's fixed 0.1 s; any other dt is refused whole.
    try:
        fleet.step_all(0.05, {"T-1": dict(full, actual_speed=9.0)}, start)
        expect(False, "a step other than 0.1 s was accepted")
    except mod.InvalidInputError:
        pass
    expect(fleet.get("T-1").state.actual_mps == before,
           "a refused dt still changed the train")
    fleet.step_all(0.1, {"T-1": full}, start)
    # The time is the harness's, received each tick (REQUIREMENTS.md
    # M11); a time that cannot be one refuses the tick.
    fleet.step_all(0.1, {"T-1": full}, 18 * 3600.0)
    expect(fleet.get("T-1").state.time_s == 18 * 3600.0,
           "the controller did not take the harness's time")
    for bad in (-1.0, float("nan"), "18:00", True):
        try:
            fleet.step_all(0.1, {"T-1": full}, bad)
            expect(False, f"a time of {bad!r} was accepted")
        except mod.InvalidInputError:
            pass
    expect(fleet.get("T-1").state.time_s == 18 * 3600.0,
           "a refused time still reached the controller")

    # Announcements are commands (REQUIREMENTS.md M7), in both modes:
    # arriving soon at 3 blocks of authority; arrived once a station
    # beacon was heard and the train stands with none left; departing
    # once the doors report closed and the Track Signal resumes. Each
    # is held for the lockout, then cleared. In Manual the driver may
    # repeat the last one, not while one plays.
    for manual in (False, True):
        mode = "Manual" if manual else "Automatic"
        talk = mod.ControllerCore()
        talk.state.manual = manual
        talk.state.train_id = "T-9"

        def say(**values: Any) -> str:
            talk.apply_staged(mod.read_inputs(values))
            talk.step()
            return talk.commands().announcement
        say(commanded_speed=10.0, authority_blocks=4, actual_speed=10.0,
            door_state=[False, False])
        expect(not talk.repeat_announcement(),
               f"{mode} repeated an announcement before any was sent")
        expect(say(authority_blocks=3)
               == mod.ANNOUNCE_ARRIVING.format(train_id="T-9"),
               f"{mode} did not announce arriving soon at 3 blocks")
        say(beacon_station="DORMONT", beacon_side="R")
        say(authority_blocks=2)
        say(authority_blocks=1)
        arrived = mod.ANNOUNCE_ARRIVED.format(train_id="T-9",
                                              station="DORMONT")
        expect(say(commanded_speed=0.0, authority_blocks=0,
                   actual_speed=5.0) != arrived,
               f"{mode} announced the arrival while still moving")
        expect(say(actual_speed=0.0) == arrived,
               f"{mode} did not announce the arrival")
        said = say(commanded_speed=10.0, authority_blocks=5)
        expect(said == mod.ANNOUNCE_DEPARTING.format(train_id="T-9",
                                                     station="DORMONT"),
               f"{mode} did not announce the departure, said {said!r}")
        expect(not talk.repeat_announcement(),
               f"{mode} repeated an announcement while one played")
        for _ in range(round(mod.ANNOUNCE_LOCKOUT_MS / 1000 / talk.dt) + 1):
            talk.step()
        expect(talk.commands().announcement == "",
               f"{mode}'s announcement never cleared")
        expect(talk.repeat_announcement() == manual
               and talk.commands().announcement == (said if manual else ""),
               f"{mode} got the repeat of the last announcement wrong")

    # Automatic lights (REQUIREMENTS.md M8), in either mode: on with an
    # underground beacon and at 18:00; off with a later beacon saying
    # not underground, unless it is night, and at 06:00. Only those
    # changes act, so the driver's own choice stands in between.
    lamp = mod.ControllerCore()
    lamp.state.manual = True

    def lights() -> tuple[bool, bool]:
        return lamp.commands().light_command

    def lamp_tick(time_s: float, **values: Any) -> None:
        lamp.state.time_s = time_s
        lamp.apply_staged(mod.read_inputs(values))
        lamp.step()
    noon, dusk = 12 * 3600.0, 18 * 3600.0
    lamp_tick(noon)
    lamp.command_lights(False, False)
    lamp_tick(noon, beacon_station="A", beacon_underground=True)
    expect(lights() == (True, True),
           "an underground beacon did not turn the lights on")
    lamp.command_lights(False, True)
    lamp_tick(noon)
    expect(lights() == (False, True),
           "the automatic lights overrode the driver between changes")
    lamp_tick(noon, beacon_station="B", beacon_underground=False)
    expect(lights() == (False, False),
           "leaving underground by day did not turn the lights off")
    lamp_tick(dusk)
    expect(lights() == (True, True), "18:00 did not turn the lights on")
    lamp_tick(dusk, beacon_station="C", beacon_underground=True)
    lamp_tick(dusk, beacon_station="D", beacon_underground=False)
    expect(lights() == (True, True),
           "leaving underground at night turned the lights off")
    lamp_tick(30 * 3600.0)                  # 06:00 the next day
    expect(lights() == (False, False), "06:00 did not turn the lights off")

    # Authority is used as given (REQUIREMENTS.md M16): the bench's
    # simulation never spends it, however far the train travels. A
    # train coasting at 10 m/s for 25 s covers 250 m.
    coast = mod.ControllerCore()
    plant = SimTrain()
    plant.actual_mps = plant.commanded_mps = 10.0
    plant.authority_blocks = 3
    drive(coast, plant, 25.0)
    expect(coast.state.authority_blocks == 3,
           "authority was spent that nobody sent")
    # On the bench a block change stands in for the Track Model
    # sending the next block's count: one fewer, never below 0, and
    # the controller has it from the next tick.
    send({"authority_blocks": 2})
    backend.bench_block_change()
    expect(backend.snapshot["track_authority_blocks"] == 1,
           "a bench block change did not spend one block")
    tick()
    expect(backend.core.state.authority_blocks == 1,
           "the controller did not receive the block change's count")
    backend.bench_block_change()
    backend.bench_block_change()
    expect(backend.snapshot["track_authority_blocks"] == 0,
           "a bench block change took authority below 0")
    tick()
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
    # The commanded speed is the only cap, in both modes, with no
    # 70 km/h cap (REQUIREMENTS.md M1): in Manual it caps the driver's
    # setpoint, also when it drops later; in Automatic it is the target.
    send({"authority_blocks": 6, "commanded_speed": 40})
    backend.set_manual(True)
    backend.set_target_mph(55)
    expect(abs(backend.snapshot["target_mph"] - 40) < 0.5,
           "the driver's target was not capped at the commanded speed")
    send({"commanded_speed": 60})
    backend.set_target_mph(55)
    expect(abs(backend.snapshot["target_mph"] - 55) < 0.5,
           "the driver's target was capped below the commanded speed")
    send({"commanded_speed": 30})
    expect(abs(backend.snapshot["target_mph"] - 30) < 0.5,
           "the driver's target stayed above a lowered commanded speed")
    backend.set_manual(False)
    send({"commanded_speed": 30})
    expect(abs(backend.core.state.target_mps * mod.MPS_TO_MPH - 30) < 0.5,
           "Automatic did not take the commanded speed as its target")
    send({"commanded_speed": 60})
    expect(abs(backend.core.state.target_mps * mod.MPS_TO_MPH - 60) < 0.5,
           "Automatic did not target a commanded speed above 70 km/h")
    backend.set_manual(True)
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

    # In Manual the press repeats the last announcement, held for the
    # lockout on system time (REQUIREMENTS.md M7, M11).
    # The longest announcement the controller sends, on screen.
    longest = mod.ANNOUNCE_DEPARTING.format(train_id=backend.selected,
                                            station="DORMONT")
    backend.core._announce(longest)
    backend._publish()
    _settle(app, 300)
    expect(backend.snapshot["announcement"] == longest,
           "the long announcement was not on screen to check")
    scan("long announcement")
    if shots:
        bench.grabWindow().save(str(shots / "09-announcement.png"))
    expect(_until(app, lambda: not backend.snapshot["announcing"], 10),
           "announcement never cleared")
    scan("nothing announcing")
    backend.announce()
    scan("announcing")
    expect(backend.snapshot["announcing"], "announcement did not start")
    expect(backend.snapshot["announcement"] == longest,
           "the press did not repeat the last announcement")
    expect(_until(app, lambda: not backend.snapshot["announcing"], 10),
           "announcement never cleared")

    for text, seen in sorted(cut.items()):
        expect(False, f"text cut off: {text!r} ({', '.join(seen[:3])})")

    for message in warnings:
        print(f"QML warning: {message}", file=sys.stderr)
    for problem in problems:
        print(f"Behaviour: {problem}", file=sys.stderr)
    print(f"{len(warnings)} QML warnings, {len(problems)} behaviour "
          "problems")
    return 1 if warnings or problems else 0
