"""Click every Train Controller control through the real QML, per mode.

Run from ``TrainController/`` with the module's venv::

    .venv/Scripts/python tests/ui_click_check.py

It loads ``ui/Main.qml`` offscreen, clicks each control with the mouse
in Manual, Automatic and Engineer modes, checks the resulting state,
and exits non-zero on any failure or QML warning. Its name keeps it out
of ``unittest`` discovery, because it drives a real window.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform == "win32":
    # Qt's offscreen platform ships no fonts.
    os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
ROOT = str(Path(__file__).resolve().parents[1])
REPO = str(Path(ROOT).parent)
sys.path.insert(0, ROOT)
sys.path.insert(0, REPO)

from PySide6.QtCore import (  # noqa: E402
    QPoint,
    QPointF,
    Qt,
    QUrl,
    qInstallMessageHandler,
)
from PySide6.QtGui import QFont, QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow  # noqa: E402,F401
from PySide6.QtTest import QTest  # noqa: E402

from ui.theme import build_theme  # noqa: E402
from train_controller.train_controller_state import (  # noqa: E402
    TrainControllerState,
)

warnings = []
qInstallMessageHandler(lambda mode, ctx, msg: warnings.append(msg))

app = QGuiApplication(sys.argv)
theme = build_theme()
app.setFont(QFont(theme["ui_family"]))
c = TrainControllerState()
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("theme", theme)
engine.rootContext().setContextProperty("controller", c)
engine.load(QUrl.fromLocalFile(os.path.join(ROOT, "ui", "Main.qml")))
window = engine.rootObjects()[0]
window.resize(1440, 900)
app.processEvents()

results = []


def check(name, ok):
    results.append((name, bool(ok)))


def items(root=None):
    root = root or window.contentItem()
    for child in root.childItems():
        yield child
        yield from items(child)


def visible_chain(item):
    while item is not None:
        if not item.isVisible() or item.opacity() == 0:
            return False
        item = item.parentItem()
    return True


def find(text, column=None, buttons=True):
    """Visible items whose text is ``text``; optional x-range filter."""
    found = []
    for item in items():
        if item.property("text") != text or not visible_chain(item):
            continue
        # Buttons only: skip the Text label inside each button.
        if buttons and item.metaObject().indexOfSignal("clicked()") < 0:
            continue
        if not isinstance(item.property("enabled"), bool):
            continue
        centre = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
        if column and not (column[0] <= centre.x() <= column[1]):
            continue
        found.append((item, centre))
    found.sort(key=lambda pair: (pair[1].y(), pair[1].x()))
    return found


def control(text, column=None, index=0):
    matches = find(text, column)
    if not matches:
        raise LookupError(f"no visible control {text!r}")
    return matches[index]


def click(text, column=None, index=0):
    item, centre = control(text, column, index)
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier,
                     QPoint(int(centre.x()), int(centre.y())))
    app.processEvents()
    return item


def enabled(text, column=None, index=0):
    item, _ = control(text, column, index)
    # Walk up: a button inside a disabled parent is disabled too.
    while item is not None:
        if not item.isEnabled():
            return False
        item = item.parentItem()
    return True


def tick(seconds):
    for _ in range(seconds):
        c.step(1.0)
    app.processEvents()


LEFT, MID, RIGHT = (0, 575), (580, 1005), (1008, 1440)
s = lambda: c.snapshot  # noqa: E731

# ---- Manual, Driver -------------------------------------------------
click("Faster", MID)
check("Manual: Faster raises target", s()["target_speed_mph"] == 18)
click("Slower", MID)
click("Slower", MID)
check("Manual: Slower lowers target", s()["target_speed_mph"] == 16)
click("Use CTC target \u00B7 17 mph", MID)
check("Manual: Use CTC target", s()["target_set_by"] == "CTC"
      and s()["target_speed_mph"] == 17)

click("On", MID)
check("Service brake On", s()["service_brake"])
click("Off", MID)
check("Service brake Off", not s()["service_brake"])

click("EMERGENCY BRAKE", MID)
check("E-brake engages", s()["emergency_brake"])
check("E-brake release disabled while moving",
      not enabled("RELEASE EMERGENCY BRAKE", MID))
click("RELEASE EMERGENCY BRAKE", MID)
check("E-brake still on after click while moving", s()["emergency_brake"])
tick(6)
check("E-brake release enabled once stopped",
      enabled("RELEASE EMERGENCY BRAKE", MID))
click("RELEASE EMERGENCY BRAKE", MID)
check("E-brake released by driver", not s()["emergency_brake"])

check("Doors disabled away from platform",
      not enabled("Open right", MID) and not enabled("Open left", MID))
while c.current_block.block_id != "65":
    tick(1)
click("EMERGENCY BRAKE", MID)
tick(6)
click("RELEASE EMERGENCY BRAKE", MID)
check("Manual at GLENBURY: Open right enabled", enabled("Open right", MID))
check("Manual at GLENBURY: Open left disabled", not enabled("Open left", MID))
click("Open right", MID)
check("Manual: Open right opens", s()["right_door"])
click("Close right", MID)
check("Manual: Close right closes", not s()["right_door"])

click("Announce again", RIGHT)
check("Announce again", s()["announcement"] != "")
before = s()["temp_setpoint_f"]
click("Warmer", RIGHT)
check("Warmer", s()["temp_setpoint_f"] == before + 1)
click("Cooler", RIGHT)
click("Cooler", RIGHT)
check("Cooler", s()["temp_setpoint_f"] == before - 1)
click("Off", RIGHT, 0)
check("Cabin lights Off", not s()["cabin_light"])
click("Off", RIGHT, 1)
check("Headlights Off", not s()["headlight"])
click("On", RIGHT, 0)
click("On", RIGHT, 1)
check("Lights back On", s()["cabin_light"] and s()["headlight"])

# ---- Automatic, Driver ----------------------------------------------
click("Automatic")
check("Mode -> Automatic", s()["mode"] == "Automatic")
check("Auto: Slower/Faster/CTC locked",
      not enabled("Slower", MID) and not enabled("Faster", MID)
      and not enabled("CTC sets the speed in Automatic mode", MID))
target = s()["target_speed_mph"]
click("Faster", MID)
check("Auto: Faster click ignored", s()["target_speed_mph"] == target)
check("Auto: driver door buttons disabled",
      not enabled("Open right", MID) and not enabled("Open left", MID))
for _ in range(300):
    tick(1)
    if s()["dwelling"]:
        break
check("Auto: stops at next unserved station (GLENBURY) and dwells",
      s()["dwelling"] and s()["current_block"] == "65")
check("Auto: right doors opened automatically", s()["right_door"])
badge = f"DWELL {s()['dwell_left_s']} S"
check("Auto: dwell badge shown", bool(find(badge, buttons=False)))
check("Auto: Close right disabled during dwell",
      not enabled("Close right", MID))
click("On", MID)
check("Auto: service brake still usable", s()["service_brake"])
click("Off", MID)
tick(46)
check("Auto: doors closed and departed",
      not s()["right_door"] and not s()["dwelling"])
for _ in range(300):
    tick(1)
    if s()["dwelling"]:
        break
check("Auto: then stops at DORMONT", s()["dwelling"]
      and s()["current_block"] == "73")
tick(46)

# ---- Engineer pop-up (over Automatic) -------------------------------
click("Engineer")
check("Engineer pop-up opens", s()["user_role"] == "Engineer"
      and bool(find("Apply gains")))
check("Apply disabled until a change", not enabled("Apply gains"))
click("0.100")
check("Step size 0.100", abs(s()["gain_step"] - 0.1) < 1e-9)
click("+", None, 0)
check("Kp + step", abs(s()["kp"] - 12.5) < 1e-9)
click("\u2212", None, 1)
check("Ki - step", abs(s()["ki"] - 0.75) < 1e-9)
click("Apply gains")
check("Apply gains", abs(s()["kp_in_use"] - 12.5) < 1e-9
      and abs(s()["ki_in_use"] - 0.75) < 1e-9)
target = s()["temp_setpoint_f"]
QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(1080, 580))
app.processEvents()
check("Scrim blocks the cab behind", s()["temp_setpoint_f"] == target)
click("Close")
check("Close returns to Driver", s()["user_role"] == "Driver")
click("Engineer")
QTest.keyClick(window, Qt.Key_Escape)
app.processEvents()
check("Esc returns to Driver", s()["user_role"] == "Driver")

# ---- Back to Manual -------------------------------------------------
click("Manual")
check("Mode -> Manual; speed buttons unlocked",
      s()["mode"] == "Manual" and enabled("Faster", MID))

for name, ok in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
print(f"\n{sum(ok for _, ok in results)}/{len(results)} passed; "
      f"QML warnings: {len(warnings)}")
for message in warnings:
    print("  warning:", message)
sys.exit(0 if all(ok for _, ok in results) and not warnings else 1)
