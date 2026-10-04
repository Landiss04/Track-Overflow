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
def _settle(app: QGuiApplication, ms: int) -> None:
    """Run the event loop for ms, so the timers above actually tick."""
    end = QTime.currentTime().addMSecs(ms)
    while QTime.currentTime() < end:
        app.processEvents()


def run_check(app: QGuiApplication, window: Any, bench: Any,
              backend: Any, warnings: list[str],
              shots: Path | None) -> int:
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
    expect(not backend.snapshot["has_train"], "a train existed before spawning")
    expect(backend.snapshot["train_count"] == 0, "the roster started full")

    # Nothing to drive yet, and nothing crashes trying.
    backend.applyInputs({"commanded_speed": 12, "authority_blocks": 2})
    backend.toggleEmergencyBrake()

    backend.spawnTrain(114, "GREEN LINE", "GREEN K")
    expect(backend.snapshot["has_train"], "spawning did not produce a train")
    expect(backend.snapshot["train_id"] == "T-114",
           "the spawned train did not take the number asked for")
    expect(not backend.core.armed, "controller armed before commissioning")
    if shots:
        window.grabWindow().save(str(shots / "01-signed-out.png"))

    # Signed out, nothing drives.
    backend.setTargetMph(40)
    backend.toggleServiceBrake()
    expect(not backend.core.state.service_request,
           "service brake answered a signed-out operator")

    # Engineer commissions the gains once; the role is then spent.
    backend.selectOperator(1)
    _settle(app, 200)
    expect(backend.snapshot["operator"] == "engineer", "engineer sign-in failed")
    if shots:
        window.grabWindow().save(str(shots / "02-gains.png"))
    # The bench commissions by sending its inputs, with no separate
    # button for it.
    backend.applyInputs({"kp": 42000, "ki": 7000})
    expect(backend.core.armed, "commissioning did not arm the controller")
    _settle(app, mod.GAINS_HANDOVER_MS + 400)
    expect(backend.snapshot["operator"] == "driver", "console not handed over")
    expect(backend.snapshot["gains_locked"],
           "the gains did not lock after commissioning")
    backend.selectOperator(1)
    expect(backend.snapshot["operator"] == "driver",
           "engineer role re-entered after the gains were set")
    backend.commissionGains(1, 1)
    expect(backend.core.state.kp == 42000, "gains changed after being locked")

    # Automatic locks the console; Manual hands it to the driver.
    expect(not backend.can_drive, "driver could act in Automatic")
    backend.setManual(True)
    expect(backend.can_drive, "Manual did not unlock the console")
    backend.setTargetMph(35)
    _settle(app, 1500)
    expect(backend.core.state.actual_mps > 0, "train never moved")
    if shots:
        window.grabWindow().save(str(shots / "03-driving.png"))

    # The emergency brake stops the train and latches until it is stopped.
    backend.toggleEmergencyBrake()
    expect(backend.core.state.power_w == 0.0, "power stayed on under e-brake")
    _settle(app, 200)
    if shots:
        window.grabWindow().save(str(shots / "04-ebrake.png"))
    backend.toggleEmergencyBrake()
    expect(backend.core.state.emergency_brake,
           "e-brake released while the train was moving")
    _settle(app, 9000)
    backend.toggleEmergencyBrake()
    expect(not backend.core.state.emergency_brake,
           "e-brake would not release at a stand")
    if shots:
        window.grabWindow().save(str(shots / "04-stopped.png"))

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
    backend.applyInputs({"commanded_speed": 19})
    expect(abs(backend.core.state.commanded_mps - 19) < 1e-6,
           "the bench could not set commanded speed in m/s")
    expect(abs(backend.snapshot["commanded_mph"] - 19 * mod.MPS_TO_MPH) < 1e-3,
           "commanded speed not shown to the driver in mph")
    backend.applyInputs({"cabin_temperature": 20})
    expect(abs(backend.core.state.cabin_temp_c - 20.0) < 0.01,
           "cabin temperature not taken in Celsius")
    expect(abs(backend.snapshot["cabin_temp_f"] - 68.0) < 0.01,
           "cabin temperature not shown to the driver in Fahrenheit")

    # A staged set applies in one call.
    backend.applyInputs({"commanded_speed": 14, "beacon": "PLATFORM B",
                         "signal_light_ahead": "GREEN"})
    expect(backend.snapshot["beacon"] == "PLATFORM B",
           "staged inputs did not apply")
    expect(backend.snapshot["next_signal"] == "GREEN",
           "staged aspect did not apply")
    backend.applyInputs({"door_state_left": True, "light_state_cabin": False})
    _settle(app, 400)
    expect(backend.snapshot["fb_doors_left"],
           "the plant wrote over a door state the bench published")
    expect(not backend.snapshot["fb_lights"],
           "the plant wrote over a light state the bench published")

    # Another train, running its own plant, with its own gains.
    first = backend.selected
    backend.spawnTrain(301, "RED LINE", "f")
    second = backend.selected
    expect(second == "R-301", "spawning did not add the train asked for")
    expect(backend.cores[second].state.authority_target == "F",
           "a block typed in lower case did not come back capitalised")
    expect(backend.snapshot["train_count"] == 2, "roster did not grow")
    backend.spawnTrain(301, "RED LINE", "RED F")
    expect(backend.snapshot["train_count"] == 2,
           "spawning the same id twice added a second copy")
    expect(not backend.core.armed, "a new train came up commissioned")
    expect(backend.cores[first].armed, "spawning disarmed the first train")
    backend.selectTrain(first)
    expect(backend.selected == first, "could not go back to the first train")

    # Ten times real time moves the simulation, not the tick rate.
    before = backend.core.state.actual_mps
    backend.setSimRate(mod.SIM_RATES.index(10))
    expect(abs(backend.core.dt - 10 / mod.CONTROL_HZ) < 1e-9,
           "the simulation rate did not reach the plant")
    _settle(app, 500)
    backend.setSimRate(mod.SIM_RATES.index(1))
    expect(abs(backend.core.state.actual_mps - before) > 1e-6,
           "ten times real time did not move the train any faster")

    backend.applyInputs({"authority_blocks": 3,
                         "signal_light_ahead": "RED"})
    expect(backend.core.state.authority_blocks == 3,
           "authority not taken as a block count")
    expect(backend.snapshot["next_signal"] == "RED", "aspect not set")
    backend.applyInputs({"failure_brake": True})
    _settle(app, 300)
    expect(backend.core.state.emergency_brake,
           "an equipment failure did not stop the train")
    if shots:
        bench.grabWindow().save(str(shots / "06-test.png"))
    backend.applyInputs({"failure_brake": False})

    backend.toggleEmergencyBrake()
    _settle(app, 300)

    # Entering a block spends authority and steps the aspect on.
    before_blocks = backend.core.state.authority_blocks
    before_aspect = backend.snapshot["signal_index"]
    backend.core.enter_block()
    expect(backend.core.state.authority_blocks == before_blocks - 1,
           "entering a block did not spend authority")
    expect(backend.snapshot["signal_index"]
           == (before_aspect + 1) % len(mod.ASPECTS),
           "entering a block did not step the signal aspect")
    while backend.core.state.authority_blocks > 0:
        backend.core.enter_block()
    backend.core.enforce_safety()
    expect(backend.core.state.emergency_brake,
           "running out of authority did not stop the train")
    backend.applyInputs({"authority_blocks": 6})
    backend.toggleEmergencyBrake()
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